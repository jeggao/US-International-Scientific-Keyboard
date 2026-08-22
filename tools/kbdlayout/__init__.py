"""Tools for the US-International Scientific keyboard layout.

``layout/us-intl-scientific.toml`` is the single source of truth. This package
loads it into a platform-neutral model (:mod:`kbdlayout.model`), generates the
file each platform needs from that model (:mod:`kbdlayout.generators`), and
checks that the documentation and the overview picture still describe the same
layout (the ``checks_*`` modules).
"""

from __future__ import annotations

__all__ = [
    "checks_assets",
    "checks_generated",
    "checks_readme",
    "checks_repo",
    "generators",
    "keys",
    "keysyms",
    "klc",
    "markdown",
    "model",
    "report",
    "source",
]
