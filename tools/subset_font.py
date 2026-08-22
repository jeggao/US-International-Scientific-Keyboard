#!/usr/bin/env python3
"""Rebuild the font subset the overview picture embeds.

A shim onto ``kbdlayout subset-font``, kept so the paths in CONTRIBUTING.md and
CI keep working. Python puts this directory on ``sys.path`` itself, so the
checks still run straight from a clone with nothing installed.
"""

import sys

from kbdlayout.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["subset-font", *sys.argv[1:]]))
