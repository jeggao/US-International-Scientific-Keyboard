"""Tools for the US-International Scientific keyboard layout.

``layout/us-intl-scientific.toml`` is the single source of truth. This package
loads it into a platform-neutral model (:mod:`kbdlayout.model`), generates the
file each platform needs from that model (:mod:`kbdlayout.generators`), and
checks that the documentation and the overview picture still describe the same
layout (:mod:`kbdlayout.checks`).
"""

from __future__ import annotations

__all__ = [
    "build",
    "checks",
    "cli",
    "generators",
    "keys",
    "keysyms",
    "klc",
    "markdown",
    "model",
    "project",
    "report",
    "source",
]
