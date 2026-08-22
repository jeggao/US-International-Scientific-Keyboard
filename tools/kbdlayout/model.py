"""The platform-neutral description of a keyboard layout.

Everything the repository ships -- the Windows ``.klc``, the Linux XKB and
Compose files, the macOS ``.keylayout``, the documentation -- is derived from a
:class:`Layout`.

Nothing in this module knows about any particular platform, and that is
enforced rather than hoped for: a target's configuration is an opaque object
kept in :attr:`Layout.targets`, per-dead-key data a target needs lives in
:attr:`DeadKey.extra` under a name only that target understands, and every
constraint that comes from a platform's file format is asked of the target
itself (see :mod:`kbdlayout.generators`). :meth:`Layout.validate` checks only
what is true of any keyboard layout on any system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .unicode_names import unicode_name

#: The shift states this project supports, in the order the documentation and
#: every generated file use them.
LEVELS = ("normal", "shift", "ctrl", "altgr", "altgr_shift")

#: Human-readable names for the levels, used in diagnostics.
LEVEL_NAMES = {
    "normal": "unmodified",
    "shift": "Shift",
    "ctrl": "Ctrl",
    "altgr": "AltGr",
    "altgr_shift": "AltGr + Shift",
}

#: The base characters every platform gives a dead key an explicit answer for.
#:
#: This is a cross-platform behavioural contract, not a platform detail: each
#: back end emits a rule for every one of these, so that a base a dead key does
#: not compose produces the root character followed by the base character
#: everywhere, rather than whatever that platform would otherwise fall back to.
#: It lives here because it is the thing that makes the three builds agree.
FALLBACK_BASES: tuple[int, ...] = tuple(range(0x20, 0x7F))


class LayoutError(ValueError):
    """Raised when a layout description is not usable."""


__all__ = [
    "FALLBACK_BASES",
    "LEVELS",
    "LEVEL_NAMES",
    "DeadKey",
    "Key",
    "Layout",
    "LayoutError",
    "Output",
    "unicode_name",
]


@dataclass(frozen=True)
class Output:
    """One character a key produces in one shift state."""

    code_point: int
    dead: bool = False

    @property
    def char(self) -> str:
        return chr(self.code_point)

    @property
    def name(self) -> str:
        return unicode_name(self.code_point)

    def __str__(self) -> str:  # pragma: no cover - diagnostics only
        return f"U+{self.code_point:04X}{'@' if self.dead else ''}"


@dataclass
class Key:
    """One physical key, addressed by its ISO/IEC 9995 position name."""

    id: str
    outputs: dict[str, Output] = field(default_factory=dict)
    #: Set on the few keys whose source file pins the value rather than letting
    #: it be derived from the unmodified/Shift pair.
    caps_override: bool | None = None

    def output(self, level: str) -> Output | None:
        return self.outputs.get(level)

    @property
    def caps(self) -> bool:
        """Whether Caps Lock acts as Shift for this key.

        True exactly for the keys whose unmodified and Shift characters are the
        lower- and upper-case forms of one letter.
        """
        if self.caps_override is not None:
            return self.caps_override
        normal, shift = self.outputs.get("normal"), self.outputs.get("shift")
        if normal is None or shift is None:
            return False
        return (
            normal.char.isalpha()
            and normal.char.upper() == shift.char
            and normal.code_point != shift.code_point
        )


@dataclass
class DeadKey:
    """A dead key: a root character plus the characters it composes."""

    root: int
    #: The heading this dead key is documented under in README.md.
    category: str = ""
    entries: list[tuple[int, int]] = field(default_factory=list)
    #: Per-target data this dead key carries, keyed by the field name the
    #: target declares. The model stores it and ascribes it no meaning; only
    #: the target that declared the field knows what it says.
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def root_char(self) -> str:
        return chr(self.root)

    @property
    def root_name(self) -> str:
        return unicode_name(self.root)

    @property
    def mapping(self) -> dict[int, int]:
        return dict(self.entries)

    @property
    def default(self) -> int | None:
        """The composite produced by the space bar."""
        return self.mapping.get(0x20)


@dataclass
class Layout:
    name: str
    version: str
    copyright: str
    company: str
    #: Each target's parsed configuration, keyed by target name. The model
    #: never looks inside these; see :meth:`config`.
    targets: dict[str, Any] = field(default_factory=dict)
    keys: list[Key] = field(default_factory=list)
    dead_keys: list[DeadKey] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._reindex()

    def _reindex(self) -> None:
        """Rebuild the lookup indexes.

        :class:`Key` and :class:`DeadKey` stay mutable, so anything that edits
        ``keys`` or ``dead_keys`` after construction must call this. The loader
        builds a layout once and does not, which is why this is not a
        ``cached_property``.
        """
        self._by_key_id = {key.id: key for key in self.keys}
        self._by_root = {dead_key.root: dead_key for dead_key in self.dead_keys}

    @property
    def description(self) -> str:
        """The name Windows shows on the taskbar, and the ``.klc`` description."""
        return f"{self.name} ({self.version})"

    def config(self, target: str) -> Any:
        """The parsed configuration for one target."""
        try:
            return self.targets[target]
        except KeyError:
            raise LayoutError(
                f"the layout has no [layout.{target}] table, which the {target} target needs"
            ) from None

    def key(self, key_id: str) -> Key | None:
        return self._by_key_id.get(key_id)

    def dead_key(self, root: int) -> DeadKey | None:
        return self._by_root.get(root)

    @property
    def dead_key_roots(self) -> list[int]:
        return [dead_key.root for dead_key in self.dead_keys]

    def declared_dead_roots(
        self, key_order: list[str] | tuple[str, ...] | None = None
    ) -> list[int]:
        """Dead key roots, in the order the keys declare them.

        Which order that is depends on the order the keys are walked in, so each
        generator passes the order its own file uses; the default is the order
        the source file lists them in.
        """
        keys = self.keys
        if key_order is not None:
            rank = {key_id: index for index, key_id in enumerate(key_order)}
            keys = sorted(keys, key=lambda k: rank.get(k.id, len(rank)))
        roots: list[int] = []
        for key in keys:
            for level in LEVELS:
                output = key.outputs.get(level)
                if output is not None and output.dead and output.code_point not in roots:
                    roots.append(output.code_point)
        return roots

    def dead_keys_in_declaration_order(
        self, key_order: list[str] | tuple[str, ...] | None = None
    ) -> list[DeadKey]:
        """The dead keys, ordered by where the keys that start them appear."""
        by_root = self._by_root
        ordered = [by_root[root] for root in self.declared_dead_roots(key_order) if root in by_root]
        seen = {dead_key.root for dead_key in ordered}
        ordered.extend(d for d in self.dead_keys if d.root not in seen)
        return ordered

    def key_producing(self, code_point: int, level: str) -> Key | None:
        for key in self.keys:
            output = key.outputs.get(level)
            if output is not None and output.code_point == code_point:
                return key
        return None

    def validate(self) -> list[str]:
        """Every reason this is not a well-formed layout, on any platform.

        Limits that come from one platform's file format are not checked here;
        each target reports its own (see ``constraints`` in
        :mod:`kbdlayout.generators`).
        """
        problems: list[str] = []
        seen_ids: set[str] = set()
        for key in self.keys:
            if key.id in seen_ids:
                problems.append(f"key {key.id} is defined more than once")
            seen_ids.add(key.id)
            for level in key.outputs:
                if level not in LEVELS:
                    problems.append(f"key {key.id} uses unknown shift state {level!r}")

        declared = set(self.declared_dead_roots())
        defined = self.dead_key_roots
        for root in sorted(declared):
            if root not in defined:
                problems.append(
                    f"U+{root:04X} is marked as a dead key but has no [[dead_key]] table"
                )
        for root in defined:
            if root not in declared:
                problems.append(f"dead key U+{root:04X} is never reachable from any key")
        if len(set(defined)) != len(defined):
            problems.append("a dead key root has more than one [[dead_key]] table")

        for dead_key in self.dead_keys:
            seen_bases: set[int] = set()
            for base, _composite in dead_key.entries:
                if base in seen_bases:
                    problems.append(f"dead key U+{dead_key.root:04X} maps base U+{base:04X} twice")
                seen_bases.add(base)
            if dead_key.default is None:
                problems.append(
                    f"dead key U+{dead_key.root:04X} has no U+0020 entry, so it has no "
                    "default character"
                )
        return problems
