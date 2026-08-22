"""macOS back end: a ``.keylayout`` bundle file.

macOS models a layout as XML: a ``keyMap`` per modifier combination, an
``action`` per key whose meaning depends on a pending dead key, and a ``state``
per dead key.

Two things this generator does deliberately, because they decide behaviour that
Apple's documentation leaves to the implementation:

* Every dead key gets an explicit ``<when>`` for **every printable ASCII base**,
  not only the ones it composes. An unmapped base therefore produces the root
  character followed by the base character -- the same thing Windows does, and
  the same thing the generated Compose file does on Linux -- instead of
  depending on how macOS treats a missing ``<when>``.
* ``<terminators>`` holds each dead key's **root** character, so that a dead key
  abandoned by a key outside that ASCII range still leaves the root behind
  rather than the default character.

.. warning::

   Nothing here has been run on macOS. The key codes for the graphic keys are
   derived from a local X11 table and agree with Apple's published constants;
   the non-graphic keys in :data:`FUNCTION_KEYS` are the conventional values and
   are the part most likely to need correcting. See CONTRIBUTING.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..keys import READING_ORDER, position
from ..model import FALLBACK_BASES, Layout, unicode_name
from ..xml_text import escape_attribute

#: The ``[layout.macos]`` table. macOS needs no per-dead-key data of its own.
CONFIG_TABLE = "macos"
KEY_FIELDS: tuple[str, ...] = ()
DEAD_KEY_FIELDS: tuple[str, ...] = ()


@dataclass
class MacosConfig:
    #: macOS identifies a layout by a signed 16-bit number; third-party layouts
    #: use a negative one. Keep it fixed across releases, or macOS treats the
    #: layout as a brand new input source.
    id: int
    #: Where the generated ``.keylayout`` is written.
    output_path: str
    group: int = 126


def escape_numeric(text: str) -> str:
    """Attribute escaping with numeric references, which is all this file uses."""
    return escape_attribute(text, numeric_references=True)


def parse_config(table: dict[str, Any]) -> MacosConfig:
    return MacosConfig(**table)


def constraints(layout: Layout) -> list[str]:
    """macOS imposes none of its own that the model does not already cover."""
    return []


#: The five modifier combinations this layout distinguishes, in ``keyMap`` order.
#: ``caps`` is a map of its own because a ``keyMapSelect`` that matches nothing
#: falls back to ``defaultIndex``, which would quietly disable Caps Lock.
#:
#: ``anyControl?`` appears on the Option maps so that Control+Option reaches
#: them: README.md tells users the AltGr states are also reachable by holding
#: Ctrl and Alt together, which is how the Windows build behaves.
MODIFIER_MAPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("normal", ("command?",)),
    ("shift", ("anyShift caps? command?",)),
    ("caps", ("caps",)),
    ("altgr", ("anyOption caps? command? anyControl?",)),
    ("altgr_shift", ("anyOption anyShift caps? command? anyControl?",)),
)

#: Keys that carry no character from this layout but must still appear, because
#: a key missing from a ``keyMap`` produces nothing at all.
#:
#: The codes come from the same X11 table as the graphic keys except for the
#: four arrows, where that table disagrees with Apple: it puts the arrows at
#: 59-62 and the right-hand modifiers at 123-126, while Apple's kVK constants
#: have the arrows at 123-126. Apple's values are used here because a
#: ``.keylayout`` is read by macOS, and the modifiers never appear in a keyMap
#: either way. This is the part of the file that most needs checking on a Mac.
FUNCTION_KEYS: tuple[tuple[int, int, str], ...] = (
    (36, 0x000D, "Return"),
    (48, 0x0009, "Tab"),
    (51, 0x0008, "Delete"),
    (53, 0x001B, "Escape"),
    (71, 0x001B, "Keypad Clear"),
    (76, 0x0003, "Keypad Enter"),
    (114, 0x0005, "Help"),
    (115, 0x0001, "Home"),
    (116, 0x000B, "Page Up"),
    (117, 0x007F, "Forward Delete"),
    (119, 0x0004, "End"),
    (121, 0x000C, "Page Down"),
    (123, 0x001C, "Left Arrow"),
    (124, 0x001D, "Right Arrow"),
    (125, 0x001F, "Down Arrow"),
    (126, 0x001E, "Up Arrow"),
)

#: Keypad keys, which do carry characters. The decimal separator is not here:
#: it is one of the layout's own keys (KPDL) and follows what the layout says.
KEYPAD_KEYS: tuple[tuple[int, str, str], ...] = (
    (67, "*", "Keypad *"),
    (69, "+", "Keypad +"),
    (75, "/", "Keypad /"),
    (78, "-", "Keypad -"),
    (81, "=", "Keypad ="),
    (82, "0", "Keypad 0"),
    (83, "1", "Keypad 1"),
    (84, "2", "Keypad 2"),
    (85, "3", "Keypad 3"),
    (86, "4", "Keypad 4"),
    (87, "5", "Keypad 5"),
    (88, "6", "Keypad 6"),
    (89, "7", "Keypad 7"),
    (91, "8", "Keypad 8"),
    (92, "9", "Keypad 9"),
)

#: The function keys, which all report the same character.
FUNCTION_ROW: tuple[int, ...] = (
    122,
    120,
    99,
    118,
    96,
    97,
    98,
    100,
    101,
    109,
    103,
    111,
    105,
    107,
    113,
)
FUNCTION_ROW_OUTPUT = 0x0010


def state_id(root: int) -> str:
    return f"dead{root:04X}"


def dead_action_id(root: int) -> str:
    return f"start{root:04X}"


def base_action_id(code_point: int) -> str:
    return f"base{code_point:04X}"


def _base_characters(layout: Layout) -> list[int]:
    """Characters that need an action because a dead key can precede them."""
    typed: set[int] = set()
    for key in layout.keys:
        for level in ("normal", "shift"):
            output = key.outputs.get(level)
            if output is not None and not output.dead:
                typed.add(output.code_point)
    return sorted(typed & set(FALLBACK_BASES))


def _cell(layout: Layout, key_id: str, level: str, bases: set[int]) -> str | None:
    key = layout.key(key_id)
    if key is None:
        return None
    output = key.outputs.get(level)
    if output is None:
        return None
    code = position(key_id).macos_key_code
    if output.dead:
        return f'      <key code="{code}" action="{dead_action_id(output.code_point)}"/>'
    if output.code_point in bases:
        return f'      <key code="{code}" action="{base_action_id(output.code_point)}"/>'
    return f'      <key code="{code}" output="{escape_numeric(output.char)}"/>'


def _fixed_keys() -> list[str]:
    """The keys every keyMap repeats: they are the same in all five."""
    rows: list[str] = []
    for code, code_point, label in FUNCTION_KEYS:
        rows.append(f'      <key code="{code}" output="&#x{code_point:04X};"/>  <!-- {label} -->')
    for code, char, label in KEYPAD_KEYS:
        rows.append(f'      <key code="{code}" output="{escape_numeric(char)}"/>  <!-- {label} -->')
    for index, code in enumerate(FUNCTION_ROW, start=1):
        rows.append(
            f'      <key code="{code}" output="&#x{FUNCTION_ROW_OUTPUT:04X};"/>  <!-- F{index} -->'
        )
    return rows


def render(layout: Layout) -> str:
    macos: MacosConfig = layout.config(CONFIG_TABLE)
    bases = _base_characters(layout)
    base_set = set(bases)
    dead_keys = layout.dead_keys
    fixed = _fixed_keys()

    outputs = [
        output.char for key in layout.keys for output in key.outputs.values() if not output.dead
    ]
    longest = max(len(text) for text in [*outputs, *(f"{chr(d.root)}x" for d in dead_keys)])

    lines: list[str] = [
        '<?xml version="1.1" encoding="UTF-8"?>',
        '<!DOCTYPE keyboard SYSTEM "file://localhost/System/Library/DTDs/KeyboardLayout.dtd">',
        f"<!-- {layout.name} {layout.version}",
        "     Generated from layout/us-intl-scientific.toml by tools/generate.py.",
        "     Do not edit this file; edit the layout source and regenerate.",
        "",
        "     Install to ~/Library/Keyboard Layouts/ and add it under",
        "     System Settings > Keyboard > Input Sources.",
        "",
        "     AltGr is Option here, and Option+Shift for the fourth level."
        f" {len(dead_keys)} dead keys.",
        "-->",
        f'<keyboard group="{macos.group}" id="{macos.id}"'
        f' name="{escape_numeric(layout.description)}" maxout="{longest}">',
        "",
        "  <layouts>",
        '    <layout first="0" last="255" modifiers="modifiers" mapSet="scientific"/>',
        "  </layouts>",
        "",
        '  <modifierMap id="modifiers" defaultIndex="0">',
    ]
    for index, (level, modifiers) in enumerate(MODIFIER_MAPS):
        lines.append(f'    <keyMapSelect mapIndex="{index}">  <!-- {level} -->')
        for modifier in modifiers:
            lines.append(f'      <modifier keys="{modifier}"/>')
        lines.append("    </keyMapSelect>")
    lines += ["  </modifierMap>", "", '  <keyMapSet id="scientific">']

    for index, (level, _modifiers) in enumerate(MODIFIER_MAPS):
        lines.append(f'    <keyMap index="{index}">  <!-- {level} -->')
        for key_id in READING_ORDER:
            key = layout.key(key_id)
            if key is None:
                continue
            # Caps Lock repeats whichever of the first two levels the layout's
            # own Caps flag selects.
            wanted = level
            if level == "caps":
                wanted = "shift" if key.caps else "normal"
            row = _cell(layout, key_id, wanted, base_set)
            if row is not None:
                lines.append(row)
        lines.extend(fixed)
        lines.append("    </keyMap>")
    lines += ["  </keyMapSet>", "", "  <actions>"]

    for dead_key in dead_keys:
        lines.append(
            f'    <action id="{dead_action_id(dead_key.root)}">'
            f"  <!-- {dead_key.category or dead_key.root_name} -->"
        )
        lines.append(f'      <when state="none" next="{state_id(dead_key.root)}"/>')
        lines.append("    </action>")

    for code_point in bases:
        lines.append(f'    <action id="{base_action_id(code_point)}">')
        lines.append(f'      <when state="none" output="{escape_numeric(chr(code_point))}"/>')
        for dead_key in dead_keys:
            composite = dead_key.mapping.get(code_point)
            result = (
                chr(composite) if composite is not None else dead_key.root_char + chr(code_point)
            )
            lines.append(
                f'      <when state="{state_id(dead_key.root)}" output="{escape_numeric(result)}"/>'
            )
        lines.append("    </action>")
    lines += ["  </actions>", "", "  <terminators>"]

    for dead_key in dead_keys:
        lines.append(
            f'    <when state="{state_id(dead_key.root)}"'
            f' output="{escape_numeric(dead_key.root_char)}"/>'
            f"  <!-- U+{dead_key.root:04X} {unicode_name(dead_key.root)} -->"
        )
    lines += ["  </terminators>", "", "</keyboard>", ""]
    return "\n".join(lines)


def generate(layout: Layout, root: Path) -> dict[str, str | bytes]:
    return {layout.config(CONFIG_TABLE).output_path: render(layout)}
