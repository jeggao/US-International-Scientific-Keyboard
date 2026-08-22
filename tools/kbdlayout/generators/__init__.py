"""Platform back ends.

A **target** owns everything about one platform:

* ``CONFIG_TABLE`` -- the ``[layout.<name>]`` table it reads its settings from,
  or ``None`` if it needs none;
* ``KEY_FIELDS`` and ``DEAD_KEY_FIELDS`` -- the ``[[key]]`` and
  ``[[dead_key]]`` fields only it understands, which the loader stashes in
  :attr:`kbdlayout.model.Key.extra` and :attr:`kbdlayout.model.DeadKey.extra`
  for it;
* ``parse_config(table)`` -- turn that table into whatever object it wants;
* ``constraints(layout)`` -- every reason this layout could not be built *for
  this platform*, so a limit of one file format never becomes a limit of the
  model;
* ``generate(layout, root)`` -- a mapping of repository-relative path to file
  content. Most targets draw everything from the layout and ignore ``root``;
  the documentation target reads the hand-written prose it splices into.

A module satisfies the protocol structurally, so a target is one module plus
one entry in :data:`TARGETS` -- and that really is the whole list: the model,
the loader and the command line all work off the registry.

``bytes`` content is written verbatim; ``str`` content is written as UTF-8 with
LF line endings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ..model import Layout
from . import docs, linux_xkb, macos_keylayout, picture, windows_klc


@runtime_checkable
class Target(Protocol):
    """What a platform back end must provide."""

    #: The ``[layout.<name>]`` table this target reads, or ``None``.
    CONFIG_TABLE: str | None
    #: ``[[key]]`` field names this target claims.
    KEY_FIELDS: tuple[str, ...]
    #: ``[[dead_key]]`` field names this target claims.
    DEAD_KEY_FIELDS: tuple[str, ...]

    def parse_config(self, table: dict[str, Any]) -> Any: ...

    def constraints(self, layout: Layout) -> list[str]: ...

    def generate(self, layout: Layout, root: Path) -> dict[str, str | bytes]: ...


#: Every supported target, in the order ``kbdlayout generate`` writes them.
TARGETS: dict[str, Target] = {
    "windows": windows_klc,
    "linux": linux_xkb,
    "macos": macos_keylayout,
    "picture": picture,
    "docs": docs,
}


def _claimed(attribute: str, what: str) -> dict[str, str]:
    claimed: dict[str, str] = {}
    for name, target in TARGETS.items():
        for field in getattr(target, attribute):
            if field in claimed:
                raise ValueError(f"both {claimed[field]} and {name} claim the {what} {field!r}")
            claimed[field] = name
    return claimed


def key_fields() -> dict[str, str]:
    """Every ``[[key]]`` field any target claims, mapped to its target."""
    return _claimed("KEY_FIELDS", "key field")


def dead_key_fields() -> dict[str, str]:
    """Every ``[[dead_key]]`` field any target claims, mapped to its target."""
    return _claimed("DEAD_KEY_FIELDS", "dead key field")


def constraints(layout: Layout) -> list[str]:
    """Every target's reasons this layout could not be built."""
    problems: list[str] = []
    for target in TARGETS.values():
        problems.extend(target.constraints(layout))
    return problems


__all__ = [
    "TARGETS",
    "Target",
    "constraints",
    "dead_key_fields",
    "docs",
    "key_fields",
    "linux_xkb",
    "macos_keylayout",
    "picture",
    "windows_klc",
]
