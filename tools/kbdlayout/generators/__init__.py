"""Platform back ends.

Each generator turns a :class:`kbdlayout.model.Layout` into the file (or files)
one platform needs. A generator is a function taking the layout and returning a
mapping of repository-relative path to file content, so that adding a platform
means adding one module and one entry in :data:`GENERATORS`.

``bytes`` content is written verbatim; ``str`` content is written as UTF-8 with
LF line endings.
"""

from __future__ import annotations

from collections.abc import Callable

from ..model import Layout
from . import linux_xkb, windows_klc

#: Every supported target, in the order ``tools/generate.py`` writes them.
GENERATORS: dict[str, Callable[[Layout], dict[str, str | bytes]]] = {
    "windows": windows_klc.generate,
    "linux": linux_xkb.generate,
}

__all__ = ["GENERATORS", "linux_xkb", "windows_klc"]
