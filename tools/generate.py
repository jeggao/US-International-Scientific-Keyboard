#!/usr/bin/env python3
"""Write every platform file from the layout source.

Usage::

    python3 tools/generate.py            # write the files
    python3 tools/generate.py --check    # fail if any of them is out of date
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kbdlayout import source
from kbdlayout.checks_generated import as_bytes, render_all
from kbdlayout.cli import LAYOUT_SOURCE, find_repository_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="generate", description=__doc__)
    parser.add_argument("--root", type=Path, default=None, help="repository root")
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write anything; exit non-zero if a file is out of date",
    )
    args = parser.parse_args(argv)

    root = (args.root or find_repository_root(Path.cwd())).resolve()
    layout = source.load(root / LAYOUT_SOURCE)
    files = render_all(layout)

    stale: list[str] = []
    for relative, content in sorted(files.items()):
        path = root / relative
        expected = as_bytes(content)
        current = path.read_bytes() if path.exists() else None
        if current == expected:
            print(f"  unchanged  {relative}")
            continue
        if args.check:
            stale.append(relative)
            print(f"  STALE      {relative}", file=sys.stderr)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
        print(f"  {'updated' if current is not None else 'created'}    {relative}")

    if stale:
        print(
            f"\n{len(stale)} generated file(s) are out of date; run `python3 tools/generate.py`",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
