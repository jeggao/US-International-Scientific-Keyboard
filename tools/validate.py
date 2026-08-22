#!/usr/bin/env python3
"""Run every layout consistency check.

A shim onto ``kbdlayout check``, kept so the paths in CONTRIBUTING.md and
CI keep working. Python puts this directory on ``sys.path`` itself, so the
checks still run straight from a clone with nothing installed.
"""

import sys

from kbdlayout.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["check", *sys.argv[1:]]))
