"""Command line entry point: ``python -m kbdlint`` or ``tools/validate.py``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import checks_assets, checks_klc, checks_readme, checks_repo
from . import klc as klc_module
from .report import Reporter

DEFAULT_KLC = "US International Scientific.klc"


def find_repository_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / DEFAULT_KLC).exists():
            return candidate
    raise SystemExit(f"could not find {DEFAULT_KLC!r} in {start} or any parent directory")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kbdlint",
        description=(
            "Check that README.md and assets/keyboard-layout.json agree with the "
            "keyboard layout defined in the .klc file."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="repository root (default: search upwards from the current directory)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as errors",
    )
    args = parser.parse_args(argv)

    root = (args.root or find_repository_root(Path.cwd())).resolve()
    reporter = Reporter(root)
    layout = klc_module.parse(root / DEFAULT_KLC)

    checks_klc.check(layout, reporter)
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
    summary = (
        f"{len(layout.layout)} keys, {len(layout.dead_keys)} dead keys checked: "
        f"{errors} error(s), {warnings} warning(s)"
    )
    print(summary, file=sys.stderr)
    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
