"""The consistency checks, and the order they run in.

Each check is a function taking the repository root, the layout, and the
reporter to write findings to, so that adding a check means adding one module
and one entry in :data:`CHECKS` -- the same shape
:mod:`kbdlayout.generators` uses for platforms.

A check resolves its own paths and reports its own missing files. Nothing about
which checks exist lives in the command line, so the test suite and the CLI run
exactly the same set.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..model import Layout
from ..report import Reporter
from . import assets, generated, readme, repo

Check = Callable[[Path, Layout, Reporter], None]

#: Every check, in the order they run.
CHECKS: dict[str, Check] = {
    "generated": generated.check,
    "readme": readme.check,
    "assets": assets.check,
    "repo": repo.check,
}

__all__ = ["CHECKS", "Check", "assets", "generated", "readme", "repo", "run_checks"]


def run_checks(root: Path, layout: Layout, reporter: Reporter | None = None) -> Reporter:
    """Run every registered check and return the reporter holding the findings."""
    reporter = reporter if reporter is not None else Reporter(root)
    for check in CHECKS.values():
        check(root, layout, reporter)
    return reporter
