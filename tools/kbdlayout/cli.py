"""Command line entry point: ``python -m kbdlayout`` or ``tools/validate.py``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import checks_assets, checks_generated, checks_readme, checks_repo, source
from .model import LayoutError
from .report import Reporter

#: The single file that defines the layout. Everything else is generated from it
#: or checked against it.
LAYOUT_SOURCE = "layout/us-intl-scientific.toml"


def find_repository_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / LAYOUT_SOURCE).exists():
            return candidate
    raise SystemExit(f"could not find {LAYOUT_SOURCE!r} in {start} or any parent directory")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kbdlint",
        description=(
            "Check that the generated platform files, README.md and "
            "assets/keyboard-layout.json all agree with the layout source."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="repository root (default: search upwards from the current directory)",
    )
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args(argv)

    root = (args.root or find_repository_root(Path.cwd())).resolve()
    try:
        layout = source.load(root / LAYOUT_SOURCE)
    except LayoutError as error:
        print(error, file=sys.stderr)
        return 1

    reporter = Reporter(root)
    checks_generated.check(root, layout, reporter)
    readme = root / "README.md"
    if readme.exists():
        checks_readme.check(readme, layout, reporter)
    else:
        reporter.add("readme", readme, 0, "README.md is missing")
    assets = root / "assets"
    if assets.is_dir():
        checks_assets.check(assets, layout, reporter)
    checks_repo.check(root, reporter)

    reporter.emit()
    errors = len(reporter.errors)
    warnings = len(reporter.findings) - errors
    print(
        f"{len(layout.keys)} keys, {len(layout.dead_keys)} dead keys checked: "
        f"{errors} error(s), {warnings} warning(s)",
        file=sys.stderr,
    )
    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
