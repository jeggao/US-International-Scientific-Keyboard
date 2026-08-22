"""The platform-neutral description of a keyboard layout.

Everything the repository ships -- the Windows ``.klc``, the Linux XKB and
Compose files, the documentation -- is derived from a :class:`Layout`. Nothing
in this module knows about any particular platform; that belongs in
:mod:`kbdlayout.generators`.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

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

#: MSKLC 1.4 cannot build a dead key whose root is above this code point, and it
#: cannot emit any character outside the Basic Multilingual Plane. Both limits
#: are documented in README.md ("Notes on MSKLC 1.4"). They are the tightest of
#: the three platforms, so the model enforces them for every target.
MAX_DEAD_KEY_ROOT = 0x0FFF
MAX_CODE_POINT = 0xFFFF

_CONTROL_NAMES: dict[int, str] = {
    0x00: "NULL",
    0x08: "BACKSPACE",
    0x09: "CHARACTER TABULATION",
    0x0A: "LINE FEED",
    0x0D: "CARRIAGE RETURN",
    0x1B: "ESCAPE",
    0x1C: "INFORMATION SEPARATOR FOUR",
    0x1D: "INFORMATION SEPARATOR THREE",
    0x1E: "INFORMATION SEPARATOR TWO",
    0x1F: "INFORMATION SEPARATOR ONE",
    0x7F: "DELETE",
}


class LayoutError(ValueError):
    """Raised when a layout description is not usable."""


def unicode_name(code_point: int) -> str:
    """Return the official Unicode name for ``code_point``.

    Control characters have no name of their own; Unicode gives them formal
    aliases instead, and those are what MSKLC's comments and this project's
    documentation use.
    """
    try:
        return unicodedata.name(chr(code_point))
    except ValueError:
        return _CONTROL_NAMES.get(code_point, f"<U+{code_point:04X}>")


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
    #: The X11 keysym this dead key uses on Linux: the key emits it, and every
    #: Compose sequence for this dead key starts with it. It is a ``dead_*`` name
    #: where one fits the diacritic, and otherwise the ``U<hex>`` form of a code
    #: point that nothing else in the layout produces.
    xkb_leader: str | None = None
    entries: list[tuple[int, int]] = field(default_factory=list)

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
class WindowsTarget:
    dll_name: str
    locale_name: str
    locale_id: str
    language_name: str
    klc_version: str = "1.0"


@dataclass
class LinuxTarget:
    symbols_file: str
    variant: str
    description: str


@dataclass
class Layout:
    name: str
    version: str
    copyright: str
    company: str
    windows: WindowsTarget
    linux: LinuxTarget
    keys: list[Key] = field(default_factory=list)
    dead_keys: list[DeadKey] = field(default_factory=list)

    @property
    def description(self) -> str:
        """The name Windows shows on the taskbar, and the ``.klc`` description."""
        return f"{self.name} ({self.version})"

    def key(self, key_id: str) -> Key | None:
        for key in self.keys:
            if key.id == key_id:
                return key
        return None

    def dead_key(self, root: int) -> DeadKey | None:
        for dead_key in self.dead_keys:
            if dead_key.root == root:
                return dead_key
        return None

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
        by_root = {dead_key.root: dead_key for dead_key in self.dead_keys}
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
        """Return every reason this layout could not be built for a platform."""
        problems: list[str] = []
        seen_ids: set[str] = set()
        for key in self.keys:
            if key.id in seen_ids:
                problems.append(f"key {key.id} is defined more than once")
            seen_ids.add(key.id)
            for level, output in key.outputs.items():
                if level not in LEVELS:
                    problems.append(f"key {key.id} uses unknown shift state {level!r}")
                if output.code_point > MAX_CODE_POINT:
                    problems.append(
                        f"key {key.id} {level} emits U+{output.code_point:04X}, "
                        "which is outside the Basic Multilingual Plane"
                    )
                if output.dead and output.code_point > MAX_DEAD_KEY_ROOT:
                    problems.append(
                        f"key {key.id} {level} is a dead key with root "
                        f"U+{output.code_point:04X}, above the MSKLC limit of "
                        f"U+{MAX_DEAD_KEY_ROOT:04X}"
                    )

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
            for base, composite in dead_key.entries:
                if base in seen_bases:
                    problems.append(f"dead key U+{dead_key.root:04X} maps base U+{base:04X} twice")
                seen_bases.add(base)
                if base > MAX_DEAD_KEY_ROOT:
                    problems.append(
                        f"dead key U+{dead_key.root:04X} has base U+{base:04X}, above the "
                        f"MSKLC limit of U+{MAX_DEAD_KEY_ROOT:04X}"
                    )
                if composite > MAX_CODE_POINT:
                    problems.append(
                        f"dead key U+{dead_key.root:04X} produces U+{composite:04X}, "
                        "which is outside the Basic Multilingual Plane"
                    )
            if dead_key.default is None:
                problems.append(
                    f"dead key U+{dead_key.root:04X} has no U+0020 entry, so it has no "
                    "default character"
                )
        problems.extend(self._leader_problems())
        return problems

    def _leader_problems(self) -> list[str]:
        """Check the Linux keysym each dead key leads its sequences with.

        Compose matches on the keysym alone, so two dead keys sharing one -- or a
        dead key sharing one with a character the layout types plainly -- makes
        both unusable. Names are not enough to tell: ``dead_perispomeni`` and
        ``dead_tilde`` are two names for keysym 0xFE53.
        """
        from .keysyms import keysym, keysym_value

        problems: list[str] = []
        by_value: dict[int, str] = {}
        for dead_key in self.dead_keys:
            leader = dead_key.xkb_leader
            if leader is None:
                problems.append(
                    f"dead key U+{dead_key.root:04X} has no xkb_leader, so Linux has no "
                    "keysym to put on the key"
                )
                continue
            value = keysym_value(leader)
            if value is None:
                problems.append(
                    f"dead key U+{dead_key.root:04X} uses the unknown keysym {leader!r}"
                )
                continue
            if value in by_value:
                problems.append(
                    f"dead keys U+{dead_key.root:04X} and {by_value[value]} both resolve to "
                    f"keysym 0x{value:04X} ({leader!r}); they would be indistinguishable"
                )
            by_value[value] = f"U+{dead_key.root:04X}"

        for key in self.keys:
            for level in ("normal", "shift"):
                output = key.outputs.get(level)
                if output is None:
                    continue
                value = keysym_value(keysym(output.code_point))
                if value is not None and value in by_value:
                    problems.append(
                        f"key {key.id} types U+{output.code_point:04X} plainly, but that is "
                        f"also the Linux keysym of dead key {by_value[value]}; the plain "
                        "character would start a dead key sequence"
                    )
        return problems
