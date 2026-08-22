"""Linux back end: an XKB symbols file and a Compose file.

Linux splits the job the ``.klc`` does in one file across two:

* the **XKB symbols** file says which keysym each key produces at each of the
  four levels (unmodified, Shift, AltGr, AltGr+Shift);
* the **Compose** file says what a dead key produces when it is followed by
  each base character.

Both are generated from the same :class:`~kbdlayout.model.Layout`, so they
cannot disagree with each other or with the Windows build.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..keys import READING_ORDER
from ..keysyms import keysym, keysym_value
from ..model import FALLBACK_BASES, DeadKey, Layout, unicode_name

#: The ``[layout.linux]`` table, and the ``[[dead_key]]`` field only Linux
#: understands: the X11 keysym the key emits, which every Compose sequence for
#: that dead key also starts with.
CONFIG_TABLE = "linux"
DEAD_KEY_FIELDS: tuple[str, ...] = ("xkb_leader",)


@dataclass
class LinuxConfig:
    symbols_file: str
    variant: str
    description: str


def parse_config(table: dict[str, Any]) -> LinuxConfig:
    return LinuxConfig(**table)


def leader(dead_key: DeadKey) -> str | None:
    """The keysym this dead key leads with, or ``None`` if it declares none.

    It is a ``dead_*`` name where one fits the diacritic, and otherwise the
    ``U<hex>`` form of a code point nothing else in the layout produces.
    """
    return dead_key.extra.get("xkb_leader")


def constraints(layout: Layout) -> list[str]:
    """Check the keysym each dead key leads its Compose sequences with.

    Compose matches on the keysym alone, so two dead keys sharing one -- or a
    dead key sharing one with a character the layout types plainly -- makes
    both unusable. Names are not enough to tell: ``dead_perispomeni`` and
    ``dead_tilde`` are two names for keysym 0xFE53, so values are compared.
    """
    problems: list[str] = []
    by_value: dict[int, str] = {}
    for dead_key in layout.dead_keys:
        name = leader(dead_key)
        if name is None:
            problems.append(
                f"dead key U+{dead_key.root:04X} has no xkb_leader, so Linux has no "
                "keysym to put on the key"
            )
            continue
        value = keysym_value(name)
        if value is None:
            problems.append(f"dead key U+{dead_key.root:04X} uses the unknown keysym {name!r}")
            continue
        if value in by_value:
            problems.append(
                f"dead keys U+{dead_key.root:04X} and {by_value[value]} both resolve to "
                f"keysym 0x{value:04X} ({name!r}); they would be indistinguishable"
            )
        by_value[value] = f"U+{dead_key.root:04X}"

    for key in layout.keys:
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


#: Levels of an XKB key, in order, and the layout level each one comes from.
XKB_LEVELS = ("normal", "shift", "altgr", "altgr_shift")

#: X11 type for a key whose unmodified and Shift symbols are a case pair, so
#: that Caps Lock acts as Shift on levels 1 and 2. This is what the ``.klc``
#: "Cap" flag means on Windows.
#:
#: It is the closest of the stock types, not an exact match. It selects the right
#: level for Caps Lock + AltGr, but it also preserves the Lock modifier, so the
#: application upper-cases the result. That only shows up on a character which
#: has an upper-case form -- see :func:`capslock_differences`. The alternative,
#: FOUR_LEVEL_ALPHABETIC, does not preserve Lock but sends Caps Lock + AltGr to
#: level 4, which would be wrong on every key that has one.
ALPHABETIC_TYPE = "FOUR_LEVEL_SEMIALPHABETIC"
PLAIN_TYPE = "FOUR_LEVEL"

#: Keys XKB configures elsewhere and that this layout does not need to change.
#: The numeric keypad's decimal separator comes from the keypad configuration,
#: which is a user preference on Linux rather than part of a layout.
SKIP_KEYS = frozenset({"KPDL"})

NO_SYMBOL = "NoSymbol"


def capslock_differences(layout: Layout) -> list[tuple[str, str, str, str]]:
    """Where Caps Lock + AltGr gives a different character than it does on Windows.

    Returns ``(key id, level, character, what X11 produces instead)`` for each
    affected shift state. Windows applies Caps Lock only to the unmodified and
    Shift columns, so every one of these is a difference between the two builds.
    """
    out: list[tuple[str, str, str, str]] = []
    for key in layout.keys:
        if not key.caps:
            # Only the keys typed with ALPHABETIC_TYPE preserve the Lock modifier.
            continue
        for level in ("altgr", "altgr_shift"):
            output = key.outputs.get(level)
            if output is None or output.dead:
                continue
            upper = output.char.upper()
            if upper != output.char:
                out.append((key.id, level, output.char, upper))
    return out


def _levels(layout: Layout, key_id: str) -> list[str] | None:
    key = layout.key(key_id)
    if key is None:
        return None
    symbols: list[str] = []
    for level in XKB_LEVELS:
        output = key.outputs.get(level)
        if output is None:
            symbols.append(NO_SYMBOL)
            continue
        dead_key = layout.dead_key(output.code_point) if output.dead else None
        if dead_key is not None:
            symbols.append(leader(dead_key))
        else:
            symbols.append(keysym(output.code_point))
    while symbols and symbols[-1] == NO_SYMBOL:
        symbols.pop()
    return symbols or None


def render_symbols(layout: Layout) -> str:
    """Return the XKB symbols file."""
    linux: LinuxConfig = layout.config(CONFIG_TABLE)
    name = linux.symbols_file
    header = [
        f"// {linux.description}",
        "//",
        f"// {layout.name} {layout.version}",
        "// Generated from layout/us-intl-scientific.toml by tools/generate.py.",
        "// Do not edit this file; edit the layout source and regenerate.",
        "//",
        "// To try it without installing anything system-wide:",
        f"//     mkdir -p ~/.xkb/symbols && cp {name} ~/.xkb/symbols/",
        f"//     setxkbmap -I$HOME/.xkb {name} -print | xkbcomp -I$HOME/.xkb - $DISPLAY",
        "//",
        "// The dead keys need the Compose file generated alongside this one.",
    ]
    differences = capslock_differences(layout)
    if differences:
        header += [
            "//",
            "// Known difference from the Windows build: X11's four-level key types keep",
            "// the Caps Lock modifier on the AltGr levels, so with Caps Lock on these",
            "// give the upper-case form, where Windows leaves them alone:",
            *(
                f"//     {key_id} {level:<11} {char} -> {upper}"
                for key_id, level, char, upper in differences
            ),
        ]

    lines = [
        *header,
        "",
        "default partial alphanumeric_keys modifier_keys",
        f'xkb_symbols "{linux.variant}" {{',
        "",
        '    include "us(basic)"',
        '    include "level3(ralt_switch)"',
        "",
        f'    name[Group1] = "{linux.description}";',
        "",
    ]

    width = max(len(key_id) for key_id in READING_ORDER)
    previous_row = None
    for key_id in READING_ORDER:
        if key_id in SKIP_KEYS:
            continue
        symbols = _levels(layout, key_id)
        if symbols is None:
            continue
        key = layout.key(key_id)
        row = key_id[:2]
        if previous_row is not None and row != previous_row:
            lines.append("")
        previous_row = row
        key_type = ALPHABETIC_TYPE if key.caps else PLAIN_TYPE
        body = ", ".join(f"{symbol:>16}" for symbol in symbols)
        lines.append(
            f"    key <{key_id}>{' ' * (width - len(key_id))} "
            f'{{ type[Group1] = "{key_type}", [ {body} ] }};'
        )

    lines.append("};")
    lines.append("")
    return "\n".join(lines)


def render_compose(layout: Layout) -> str:
    """Return the Compose file holding every dead key's sequences."""
    lines: list[str] = [
        f"# {layout.name} {layout.version} -- dead key sequences",
        "#",
        "# Generated from layout/us-intl-scientific.toml by tools/generate.py.",
        "# Do not edit this file; edit the layout source and regenerate.",
        "#",
        "# Install as ~/.XCompose, or point XCOMPOSEFILE at it, then restart the",
        "# applications that should pick it up.",
        "",
        "# Keep everything the locale already defines.",
        'include "%L"',
        "",
    ]
    for dead_key in layout.dead_keys:
        name = leader(dead_key)
        if name is None:
            raise ValueError(
                f"dead key U+{dead_key.root:04X} has no xkb_leader; Linux needs a keysym "
                "to put on the key and to lead its Compose sequences"
            )
        lines.append(
            f"# {dead_key.category or dead_key.root_name} "
            f"-- AltGr dead key, root U+{dead_key.root:04X} {dead_key.root_name}"
        )
        mapping = dead_key.mapping
        for base, composite in dead_key.entries:
            lines.append(_sequence(name, base, chr(composite), unicode_name(composite)))
        unmapped = [base for base in FALLBACK_BASES if base not in mapping]
        if unmapped:
            lines.append(
                f"# Anything else this dead key is followed by yields "
                f"{dead_key.root_char!r} and that character, as it does on Windows."
            )
            for base in unmapped:
                lines.append(_sequence(name, base, dead_key.root_char + chr(base), "fallback"))
        lines.append("")
    return "\n".join(lines)


def _sequence(leader_name: str, base: int, result: str, comment: str) -> str:
    sequence = f"<{leader_name}> <{keysym(base)}>"
    escaped = result.replace("\\", "\\\\").replace('"', '\\"')
    code_points = " ".join(f"U{ord(char):04X}" for char in result)
    return f'{sequence:<48}: "{escaped}"\t{code_points}\t# {comment}'


#: Where the two generated Linux files go. The name inside each comes from the
#: layout's own ``symbols_file``, so only the directory is fixed here.
OUTPUT_DIR = "dist/linux"


def generate(layout: Layout) -> dict[str, str | bytes]:
    name = layout.config(CONFIG_TABLE).symbols_file
    return {
        f"{OUTPUT_DIR}/symbols/{name}": render_symbols(layout),
        f"{OUTPUT_DIR}/{name}.XCompose": render_compose(layout),
    }
