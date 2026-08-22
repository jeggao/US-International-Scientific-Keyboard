"""Where things live in the repository, and how to find them.

This is the bottom of the dependency graph: the command line, the generators
and the checks all need to know where the layout source is, and none of them
should have to import the command line to find out.
"""

from __future__ import annotations

from pathlib import Path

#: The single file that defines the layout. Everything else is generated from
#: it or checked against it.
LAYOUT_SOURCE = "layout/us-intl-scientific.toml"

#: The documentation that restates the layout, and the directory holding the
#: overview picture.
README = "README.md"
ASSETS = "assets"


class ProjectError(Exception):
    """Raised when the repository is not laid out the way the tools expect."""


def find_repository_root(start: Path | None = None) -> Path:
    """Find the repository root by searching upwards for the layout source."""
    start = (start or Path.cwd()).resolve()
    for candidate in [start, *start.parents]:
        if (candidate / LAYOUT_SOURCE).exists():
            return candidate
    raise ProjectError(f"could not find {LAYOUT_SOURCE!r} in {start} or any parent directory")


def layout_path(root: Path) -> Path:
    return root / LAYOUT_SOURCE
