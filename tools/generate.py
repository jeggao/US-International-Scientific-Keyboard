#!/usr/bin/env python3
"""Write every platform file from the layout source.

A shim onto ``kbdlayout generate``, kept so the paths in CONTRIBUTING.md and
CI keep working. Python puts this directory on ``sys.path`` itself, so the
checks still run straight from a clone with nothing installed.
"""

import sys

from kbdlayout.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["generate", *sys.argv[1:]]))
