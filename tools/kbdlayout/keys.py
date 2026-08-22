"""The physical keys a layout may define, and how each platform names them.

Keys are identified by their ISO/IEC 9995 position name (``AE01``, ``AD01``,
``TLDE`` ...), which is what X11 uses and what the rest of this project uses as
the platform-neutral key id. The tables here translate that id into the names
Windows needs; the relationship is a property of PC keyboards, not of this
layout, so it lives in code rather than in the layout source.
"""

from __future__ import annotations

from dataclasses import dataclass

#: X11 keycodes are AT scan codes (set 1) plus the evdev offset. Verified for
#: all 50 keys against /usr/share/X11/xkb/keycodes/evdev.
EVDEV_OFFSET = 8


@dataclass(frozen=True)
class KeyPosition:
    """One key position, with the name each platform gives it."""

    id: str
    #: AT scan code set 1, as used by the ``.klc`` LAYOUT table.
    scan_code: int
    #: The Windows virtual key name, as written in the ``.klc`` VK_ column.
    virtual_key: str
    #: A short description, used in generated comments.
    label: str

    @property
    def x11_keycode(self) -> int:
        return self.scan_code + EVDEV_OFFSET


def _row(prefix: str, start: int, entries: list[tuple[str, str]]) -> list[KeyPosition]:
    return [
        KeyPosition(f"{prefix}{index + 1:02d}", start + index, virtual_key, label)
        for index, (virtual_key, label) in enumerate(entries)
    ]


#: Every key position this project can describe, in ``.klc`` scan code order.
KEY_POSITIONS: tuple[KeyPosition, ...] = (
    KeyPosition("TLDE", 0x29, "OEM_3", "grave/tilde"),
    *_row(
        "AE",
        0x02,
        [
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
            ("6", "6"),
            ("7", "7"),
            ("8", "8"),
            ("9", "9"),
            ("0", "0"),
            ("OEM_MINUS", "minus"),
            ("OEM_PLUS", "equals"),
        ],
    ),
    *_row(
        "AD",
        0x10,
        [
            ("Q", "Q"),
            ("W", "W"),
            ("E", "E"),
            ("R", "R"),
            ("T", "T"),
            ("Y", "Y"),
            ("U", "U"),
            ("I", "I"),
            ("O", "O"),
            ("P", "P"),
            ("OEM_4", "left bracket"),
            ("OEM_6", "right bracket"),
        ],
    ),
    *_row(
        "AC",
        0x1E,
        [
            ("A", "A"),
            ("S", "S"),
            ("D", "D"),
            ("F", "F"),
            ("G", "G"),
            ("H", "H"),
            ("J", "J"),
            ("K", "K"),
            ("L", "L"),
            ("OEM_1", "semicolon"),
            ("OEM_7", "apostrophe"),
        ],
    ),
    KeyPosition("BKSL", 0x2B, "OEM_5", "backslash"),
    *_row(
        "AB",
        0x2C,
        [
            ("Z", "Z"),
            ("X", "X"),
            ("C", "C"),
            ("V", "V"),
            ("B", "B"),
            ("N", "N"),
            ("M", "M"),
            ("OEM_COMMA", "comma"),
            ("OEM_PERIOD", "period"),
            ("OEM_2", "slash"),
        ],
    ),
    KeyPosition("SPCE", 0x39, "SPACE", "space bar"),
    KeyPosition("KPDL", 0x53, "DECIMAL", "numeric keypad decimal"),
    KeyPosition("LSGT", 0x56, "OEM_102", "ISO extra key"),
)

BY_ID: dict[str, KeyPosition] = {position.id: position for position in KEY_POSITIONS}
BY_SCAN_CODE: dict[int, KeyPosition] = {position.scan_code: position for position in KEY_POSITIONS}

#: The order the ``.klc`` LAYOUT table lists keys in: by scan code.
KLC_ORDER: tuple[str, ...] = tuple(
    position.id for position in sorted(KEY_POSITIONS, key=lambda p: p.scan_code)
)

#: The order the documentation and the generated XKB file walk the keyboard in:
#: the way a reader looks at it, row by row.
READING_ORDER: tuple[str, ...] = tuple(position.id for position in KEY_POSITIONS)


def position(key_id: str) -> KeyPosition:
    try:
        return BY_ID[key_id]
    except KeyError:
        raise KeyError(
            f"unknown key position {key_id!r}; expected one of {', '.join(sorted(BY_ID))}"
        ) from None
