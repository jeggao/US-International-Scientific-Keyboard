"""Windows back end: the MSKLC 1.4 ``.klc`` source file.

The output is byte-for-byte what Microsoft Keyboard Layout Creator 1.4 writes,
so the generated file can be opened in MSKLC and built into a ``.dll`` without
any manual step. That equivalence is what ``tools/tests/test_generators.py``
pins down.
"""

from __future__ import annotations

from ..keys import KLC_ORDER, position
from ..model import Layout, unicode_name

#: The file is UTF-16LE with a byte order mark and CRLF line endings; MSKLC
#: refuses to open anything else.
ENCODING = "utf-16-le"
BOM = "\ufeff"
NEWLINE = "\r\n"

#: The LAYOUT table has one column per shift state, in this order. The numbers
#: are MSKLC's: 0 = unmodified, 1 = Shift, 2 = Ctrl, 6 = Ctrl+Alt (AltGr),
#: 7 = Ctrl+Alt+Shift.
SHIFT_STATES: tuple[tuple[int, str], ...] = (
    (0, "normal"),
    (1, "shift"),
    (2, "ctrl"),
    (6, "altgr"),
    (7, "altgr_shift"),
)

#: Tab stops in the LAYOUT table; the virtual key column is padded out to here.
TAB_WIDTH = 8
VK_COLUMN_END = 24

#: MSKLC writes the same key names into every en-US layout it produces.
KEYNAME_BLOCK = """\
01	Esc
0e	Backspace
0f	Tab
1c	Enter
1d	Ctrl
2a	Shift
36	"Right Shift"
37	"Num *"
38	Alt
39	Space
3a	"Caps Lock"
3b	F1
3c	F2
3d	F3
3e	F4
3f	F5
40	F6
41	F7
42	F8
43	F9
44	F10
45	Pause
46	"Scroll Lock"
47	"Num 7"
48	"Num 8"
49	"Num 9"
4a	"Num -"
4b	"Num 4"
4c	"Num 5"
4d	"Num 6"
4e	"Num +"
4f	"Num 1"
50	"Num 2"
51	"Num 3"
52	"Num 0"
53	"Num Del"
54	"Sys Req"
57	F11
58	F12
7c	F13
7d	F14
7e	F15
7f	F16
80	F17
81	F18
82	F19
83	F20
84	F21
85	F22
86	F23
87	F24
"""

KEYNAME_EXT_BLOCK = """\
1c	"Num Enter"
1d	"Right Ctrl"
35	"Num /"
37	"Prnt Scrn"
38	"Right Alt"
45	"Num Lock"
46	Break
47	Home
48	Up
49	"Page Up"
4b	Left
4d	Right
4f	End
50	Down
51	"Page Down"
52	Insert
53	Delete
54	<00>
56	Help
5b	"Left Windows"
5c	"Right Windows"
5d	Application
"""


def _tabs(start: int, target: int) -> str:
    """Tabs needed to move from column ``start`` to column ``target``."""
    count = 0
    while start < target:
        start = start + TAB_WIDTH - (start % TAB_WIDTH)
        count += 1
    return "\t" * count


def _cell(code_point: int | None, dead: bool) -> str:
    """Render one LAYOUT cell the way MSKLC does.

    Alphanumeric ASCII is written as the character itself, everything else as a
    four digit lower-case hexadecimal code point, and a dead key gets a ``@``.
    """
    if code_point is None:
        return "-1"
    char = chr(code_point)
    body = char if char.isascii() and char.isalnum() else f"{code_point:04x}"
    return body + ("@" if dead else "")


def _layout_row(layout: Layout, key_id: str) -> str | None:
    key = layout.key(key_id)
    if key is None:
        return None
    where = position(key_id)
    cells: list[str] = []
    names: list[str] = []
    for _state, level in SHIFT_STATES:
        output = key.outputs.get(level)
        cells.append(
            _cell(None if output is None else output.code_point, output.dead if output else False)
        )
        names.append("<none>" if output is None else unicode_name(output.code_point))

    prefix = f"{where.scan_code:02x}\t"
    padding = _tabs(TAB_WIDTH + len(where.virtual_key), VK_COLUMN_END)
    body = "\t".join(cells)
    return f"{prefix}{where.virtual_key}{padding}{int(key.caps)}\t{body}\t\t// {', '.join(names)}"


def render(layout: Layout) -> str:
    """Return the ``.klc`` text, with LF newlines and no byte order mark."""
    lines: list[str] = []
    add = lines.append

    add(f'KBD\t{layout.windows.dll_name}\t"{layout.description}"')
    add("")
    add(f'COPYRIGHT\t"{layout.copyright}"')
    add("")
    add(f'COMPANY\t"{layout.company}"')
    add("")
    add(f'LOCALENAME\t"{layout.windows.locale_name}"')
    add("")
    add(f'LOCALEID\t"{layout.windows.locale_id}"')
    add("")
    add(f"VERSION\t{layout.windows.klc_version}")
    add("")
    add("SHIFTSTATE")
    add("")
    add("0\t//Column 4")
    add("1\t//Column 5 : Shft")
    add("2\t//Column 6 :       Ctrl")
    add("6\t//Column 7 :       Ctrl Alt")
    add("7\t//Column 8 : Shft  Ctrl Alt")
    add("")
    add("LAYOUT\t\t;an extra '@' at the end is a dead key")
    add("")
    add("//SC\tVK_\t\tCap\t0\t1\t2\t6\t7")
    add("//--\t----\t\t----\t----\t----\t----\t----\t----")
    add("")
    for key_id in KLC_ORDER:
        row = _layout_row(layout, key_id)
        if row is not None:
            add(row)
    add("")

    dead_keys = layout.dead_keys_in_declaration_order(KLC_ORDER)
    for dead_key in dead_keys:
        add("")
        add(f"DEADKEY\t{dead_key.root:04x}")
        add("")
        for base, composite in dead_key.entries:
            add(f"{base:04x}\t{composite:04x}\t// {chr(base)} -> {chr(composite)}")

    add("")
    add("")
    add("KEYNAME")
    add("")
    add(KEYNAME_BLOCK.rstrip("\n"))
    add("")
    add("KEYNAME_EXT")
    add("")
    add(KEYNAME_EXT_BLOCK.rstrip("\n"))
    add("")
    add("KEYNAME_DEAD")
    add("")
    for dead_key in dead_keys:
        add(f'{dead_key.root:04x}\t"{dead_key.root_name}"')
    add("")
    add("")
    add("DESCRIPTIONS")
    add("")
    add(f"{layout.windows.locale_id[-4:]}\t{layout.description}")
    add("")
    add("LANGUAGENAMES")
    add("")
    add(f"{layout.windows.locale_id[-4:]}\t{layout.windows.language_name}")
    add("")
    add("ENDKBD")
    add("")
    return "\n".join(lines)


def to_bytes(layout: Layout) -> bytes:
    """Return the ``.klc`` exactly as MSKLC would write it to disk."""
    text = render(layout).replace("\n", NEWLINE)
    return (BOM + text).encode(ENCODING)


def generate(layout: Layout) -> dict[str, str | bytes]:
    return {f"{layout.name.replace('-', ' ')}.klc": to_bytes(layout)}
