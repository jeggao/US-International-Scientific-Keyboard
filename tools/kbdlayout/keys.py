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


#: Apple's virtual key codes for the keys this layout defines, derived from
#: the "old" section of /usr/share/X11/xkb/keycodes/macintosh minus the same
#: evdev offset. All 50 agree with Apple's published kVK_ANSI_* constants.
#: The non-graphic keys a .keylayout must also carry live in the macOS
#: generator, because only that platform needs them.
MACOS_KEY_CODES: dict[str, int] = {
    "TLDE": 50,
    "AE01": 18,
    "AE02": 19,
    "AE03": 20,
    "AE04": 21,
    "AE05": 23,
    "AE06": 22,
    "AE07": 26,
    "AE08": 28,
    "AE09": 25,
    "AE10": 29,
    "AE11": 27,
    "AE12": 24,
    "AD01": 12,
    "AD02": 13,
    "AD03": 14,
    "AD04": 15,
    "AD05": 17,
    "AD06": 16,
    "AD07": 32,
    "AD08": 34,
    "AD09": 31,
    "AD10": 35,
    "AD11": 33,
    "AD12": 30,
    "AC01": 0,
    "AC02": 1,
    "AC03": 2,
    "AC04": 3,
    "AC05": 5,
    "AC06": 4,
    "AC07": 38,
    "AC08": 40,
    "AC09": 37,
    "AC10": 41,
    "AC11": 39,
    "BKSL": 42,
    "AB01": 6,
    "AB02": 7,
    "AB03": 8,
    "AB04": 9,
    "AB05": 11,
    "AB06": 45,
    "AB07": 46,
    "AB08": 43,
    "AB09": 47,
    "AB10": 44,
    "SPCE": 49,
    "KPDL": 65,
    "LSGT": 10,
}


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

    @property
    def macos_key_code(self) -> int:
        return MACOS_KEY_CODES[self.id]


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
