"""The command line: ``kbdlayout <command>``, or ``python -m kbdlayout``.

Every command shares one ``--root`` and one way of finding and loading the
layout, so the four scripts under ``tools/`` are now shims onto the
subcommands here rather than four copies of the same preamble.

Findings and reports go to **stdout**; summaries and anything that stopped the
run go to **stderr**.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import build, source
from .checks import run_checks
from .generators import picture
from .model import Layout, LayoutError
from .project import ProjectError, find_repository_root, layout_path
from .report import FORMATS


def _load(args: argparse.Namespace) -> tuple[Path, Layout]:
    root = (args.root or find_repository_root()).resolve()
    return root, source.load(layout_path(root))


# ---------------------------------------------------------------- check ----


def check(args: argparse.Namespace) -> int:
    """Check the generated files, README.md and the picture against the source."""
    root, layout = _load(args)
    reporter = run_checks(root, layout)
    reporter.emit(style=args.format)

    errors = len(reporter.errors)
    warnings = len(reporter.warnings)
    print(
        f"{len(layout.keys)} keys, {len(layout.dead_keys)} dead keys checked: "
        f"{errors} error(s), {warnings} warning(s)",
        file=sys.stderr,
    )
    return 1 if errors or (args.strict and warnings) else 0


# ------------------------------------------------------------- generate ----


def generate(args: argparse.Namespace) -> int:
    """Write every platform file from the layout source."""
    root, layout = _load(args)
    outcomes = build.sync(root, layout, write=not args.check)

    stale = [outcome for outcome in outcomes if outcome.is_stale]
    for outcome in outcomes:
        stream = sys.stderr if outcome.is_stale else sys.stdout
        label = "STALE" if outcome.is_stale else outcome.status
        print(f"  {label:<10} {outcome.relative}", file=stream)

    if stale:
        print(
            f"\n{len(stale)} generated file(s) are out of date; run `kbdlayout generate`",
            file=sys.stderr,
        )
        return 1
    return 0


# --------------------------------------------------------------- render ----


def render(args: argparse.Namespace) -> int:
    """Rasterise the generated SVG into the PNG README.md shows."""
    from . import rasterise

    root, layout = _load(args)
    svg = picture.render_svg(layout)
    svg_path = root / rasterise.SVG_PATH
    committed = svg_path.read_text(encoding="utf-8") if svg_path.exists() else ""
    if committed != svg:
        print(
            f"{rasterise.SVG_PATH} is out of date; run `kbdlayout generate`",
            file=sys.stderr,
        )
        return 1

    chromium = rasterise.find_chromium()
    if chromium is None:
        # Reporting success here would make a green CI job mean nothing: the
        # picture would go unrendered and unchecked, and no one would know.
        print(
            "no Chromium found, so the picture cannot be rebuilt. Install one with\n"
            "  pip install playwright && playwright install chromium\n"
            "or leave the picture to CI, which rebuilds it on every push.",
            file=sys.stderr,
        )
        return 1
    print(f"rendering with {chromium}")

    width, height = picture.size(layout)
    rendered = rasterise.render(svg, width, height, chromium)

    target = root / rasterise.PNG_PATH
    current = target.read_bytes() if target.exists() else b""
    drift = rasterise.difference(current, rendered) if current else 1.0
    if not current:
        print(f"{rasterise.PNG_PATH}: creating")
    else:
        print(f"{rasterise.PNG_PATH}: {drift:.4%} of pixels differ")

    if args.check:
        if drift > args.tolerance:
            print(
                f"the picture is stale: {drift:.4%} of pixels differ, which is more than "
                f"the {args.tolerance:.4%} allowed. Run `kbdlayout render`.",
                file=sys.stderr,
            )
            return 1
        return 0

    if drift == 0.0 and current:
        print("unchanged")
        return 0
    target.write_bytes(rendered)
    print(f"wrote {rasterise.PNG_PATH} ({len(rendered)} bytes)")
    return 0


# ---------------------------------------------------------- subset-font ----


def subset_font(args: argparse.Namespace) -> int:
    """Rebuild the font subset the overview picture embeds."""
    from . import fontsubset

    root, layout = _load(args)
    return fontsubset.rebuild(root, layout)


# ----------------------------------------------------------------- main ----

COMMANDS = {
    "check": check,
    "generate": generate,
    "render": render,
    "subset-font": subset_font,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kbdlayout",
        description="Build and check the US-International Scientific keyboard layout.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="repository root (default: search upwards from the current directory)",
    )
    subparsers = parser.add_subparsers(dest="command")

    checker = subparsers.add_parser("check", help=check.__doc__)
    checker.add_argument("--strict", action="store_true", help="treat warnings as errors")
    checker.add_argument(
        "--format",
        choices=sorted(FORMATS),
        default=None,
        help=(
            "how to print findings on stdout (default: github inside GitHub "
            "Actions, else text). The summary always goes to stderr."
        ),
    )

    generator = subparsers.add_parser("generate", help=generate.__doc__)
    generator.add_argument(
        "--check",
        action="store_true",
        help="do not write anything; exit non-zero if a file is out of date",
    )

    renderer = subparsers.add_parser("render", help=render.__doc__)
    renderer.add_argument(
        "--check",
        action="store_true",
        help="do not write; report how far the committed picture has drifted",
    )
    renderer.add_argument(
        "--tolerance",
        type=float,
        default=0.002,
        help="fraction of pixels allowed to differ before --check fails",
    )

    subparsers.add_parser("subset-font", help=subset_font.__doc__)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(sys.stderr)
        return 2
    try:
        return COMMANDS[args.command](args)
    except (LayoutError, ProjectError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
