#!/usr/bin/env python3
"""Rasterise the generated SVG into the PNG that README.md shows.

A shim onto ``kbdlayout render``, kept so the paths in CONTRIBUTING.md and
CI keep working. Python puts this directory on ``sys.path`` itself, so the
checks still run straight from a clone with nothing installed.
"""

import sys

from kbdlayout.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["render", *sys.argv[1:]]))
