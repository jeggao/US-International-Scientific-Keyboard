"""Consistency checks for the US-International Scientific keyboard layout.

The ``.klc`` file is the single source of truth for the layout. Everything else
in the repository -- the documentation tables in ``README.md`` and the
keyboard-layout-editor source used to draw the overview picture -- describes the
same mappings a second time, so they can drift. These checks keep them honest.
"""

from __future__ import annotations

__all__ = [
    "checks_assets",
    "checks_klc",
    "checks_readme",
    "checks_repo",
    "klc",
    "markdown",
    "report",
]
