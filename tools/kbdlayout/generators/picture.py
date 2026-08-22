"""The overview picture, in two forms.

The picture in README.md used to be drawn by hand on
keyboard-layout-editor.com and exported by hand, which is how it came to
disagree with the layout. Both forms are now generated from the same model:

* ``assets/keyboard-layout.json`` -- keyboard-layout-editor source, so the
  picture can still be opened and edited there;
* ``assets/keyboard-layout.svg`` -- a self-contained drawing, which
  ``tools/render.py`` turns into the PNG the README shows.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from ..model import Layout
from ..xml_text import escape_attribute, escape_content
from ._picture_font import WOFF2_BASE64

#: The picture draws itself from the layout alone, so it reads no config table
#: and claims no dead key fields.
CONFIG_TABLE: str | None = None
KEY_FIELDS: tuple[str, ...] = ()
DEAD_KEY_FIELDS: tuple[str, ...] = ()


def parse_config(table: dict) -> None:  # pragma: no cover - never called
    raise ValueError("the picture target takes no configuration")


def constraints(layout: Layout) -> list[str]:
    """Anything drawable is anything the model allows."""
    return []


# --------------------------------------------------------------------------
# The palette, which README.md's legend describes
# --------------------------------------------------------------------------

PLAIN_CAP = "#cccccc"
DEAD_CAP = "#e5abab"
CONTROL_CAP = "#98b2d1"

TEXT = "#000000"
DEAD_TEXT = "#ff0000"
ROOT_TEXT = "#9b00ff"

#: Where a label sits on the keycap. The names are this module's; the numbers
#: are keyboard-layout-editor's twelve label positions.
POSITIONS = {"tl": 0, "bl": 1, "tr": 2, "br": 3, "c": 8, "bc": 10}

#: Which shift state each corner shows. The legend key in the top row spells
#: this out for readers of the picture.
CORNERS = (("tl", "shift"), ("bl", "normal"), ("tr", "altgr_shift"), ("br", "altgr"))

#: Characters that have no glyph worth drawing, and what to write instead.
WORD_LABELS = {
    0x200D: "zwj",
    0x200B: "Zero Width Space",
    0x00A0: "No-Break Space",
}


@dataclass
class Cap:
    """One keycap in the picture."""

    width: float = 1.0
    background: str = PLAIN_CAP
    labels: dict[str, str] = field(default_factory=dict)
    colours: dict[str, str] = field(default_factory=dict)
    #: Horizontal gap before this cap, in key units.
    gap: float = 0.0


@dataclass
class Row:
    caps: list[Cap] = field(default_factory=list)
    #: Vertical gap before this row, in key units.
    gap: float = 0.0


def _show(code_point: int) -> str:
    """What to draw for a character."""
    if code_point in WORD_LABELS:
        return WORD_LABELS[code_point]
    char = chr(code_point)
    if unicodedata.category(char) in ("Mn", "Me", "Mc"):
        # A lone combining mark latches on to whatever precedes it.
        return "◌" + char
    return char


def shows_root(layout: Layout, code_point: int) -> bool:
    """Whether a dead key's root is worth drawing next to its default.

    Only when the root is something the dead key can actually produce, and is
    not a diacritic whose spacing form already stands for it. For the dead keys
    whose root is a placeholder -- the Fraktur, double-struck and script fonts --
    drawing it would advertise a character the key never emits.
    """
    dead_key = layout.dead_key(code_point)
    if dead_key is None or dead_key.default is None:
        return False
    if dead_key.default == dead_key.root:
        return False
    if unicodedata.category(dead_key.root_char) in ("Mn", "Me", "Mc"):
        return False
    return dead_key.root in {composite for _base, composite in dead_key.entries}


def _key_cap(layout: Layout, key_id: str) -> Cap:
    key = layout.key(key_id)
    cap = Cap()
    if any(output.dead for output in key.outputs.values()):
        cap.background = DEAD_CAP
    for corner, level in CORNERS:
        output = key.outputs.get(level)
        if output is None:
            continue
        if output.dead:
            dead_key = layout.dead_key(output.code_point)
            shown = dead_key.default if dead_key.default is not None else output.code_point
            if shows_root(layout, output.code_point):
                # Root first, then default, as README.md's legend describes.
                cap.labels[corner] = f"{_show(dead_key.root)} {_show(shown)}"
                cap.colours[corner] = ROOT_TEXT
            else:
                cap.labels[corner] = _show(shown)
                cap.colours[corner] = DEAD_TEXT
        else:
            cap.labels[corner] = _show(output.code_point)
            cap.colours[corner] = TEXT
    return cap


def _fixed(width: float, text: str, background: str = PLAIN_CAP, gap: float = 0.0) -> Cap:
    return Cap(width=width, background=background, labels={"tl": text}, gap=gap)


def build(layout: Layout) -> list[Row]:
    """The picture, as rows of keycaps."""

    def cap(key_id: str) -> Cap:
        return _key_cap(layout, key_id)

    number = [cap("TLDE")] + [cap(f"AE{i:02d}") for i in range(1, 13)]
    qwerty = [cap(f"AD{i:02d}") for i in range(1, 13)] + [cap("BKSL")]
    asdf = [cap(f"AC{i:02d}") for i in range(1, 12)]
    zxcv = [cap(f"AB{i:02d}") for i in range(1, 11)]

    space = cap("SPCE")
    space.width = 6.25
    # The space bar's characters are words, and there is room for them.
    space.labels = {
        "bl": "Space",
        "tr": WORD_LABELS[0x200B],
        "br": WORD_LABELS[0x00A0],
    }
    space.colours = {"bl": TEXT, "tr": TEXT, "br": TEXT}
    space.background = PLAIN_CAP

    legend_gap = 0.5
    return [
        Row(
            caps=[
                *number,
                _fixed(2, "Backspace"),
                Cap(
                    width=2,
                    gap=legend_gap,
                    labels={
                        "tl": "Shift",
                        "tr": "AltGr+Shift",
                        "bl": "Normal",
                        "br": "AltGr",
                    },
                    colours=dict.fromkeys(("tl", "tr", "bl", "br"), TEXT),
                    background="#ffffff",
                ),
            ]
        ),
        Row(
            caps=[
                _fixed(1.5, "Tab"),
                *qwerty,
                _fixed(1, "Dead", DEAD_CAP, gap=legend_gap),
                _fixed(1, "Control", CONTROL_CAP),
            ]
        ),
        Row(caps=[_fixed(1.75, "Caps Lock"), *asdf, _fixed(2.25, "Enter")]),
        Row(
            caps=[
                _fixed(2.25, "Shift", CONTROL_CAP),
                *zxcv,
                _fixed(2.75, "Shift", CONTROL_CAP),
            ]
        ),
        Row(
            caps=[
                _fixed(1.25, "Ctrl"),
                _fixed(1.25, "Win"),
                _fixed(1.25, "Alt"),
                space,
                _fixed(1.25, "AltGr", CONTROL_CAP),
                _fixed(1.25, "Win"),
                _fixed(1.25, "Menu"),
                _fixed(1.25, "Ctrl"),
            ]
        ),
    ]


# --------------------------------------------------------------------------
# keyboard-layout-editor.com source
# --------------------------------------------------------------------------


def characters(layout: Layout) -> set[str]:
    """Every character the picture draws, so the font subset can cover them."""
    used: set[str] = set()
    for row in build(layout):
        for cap in row.caps:
            for text in cap.labels.values():
                used |= set(text)
    return used


def render_kle(layout: Layout) -> str:
    """Return the keyboard-layout-editor JSON for the picture."""
    out: list[object] = [{"name": f"{layout.name} keyboard layout"}]
    for row in build(layout):
        items: list[object] = []
        current = {"c": "", "t": ""}
        for cap in row.caps:
            props: dict[str, object] = {}
            if cap.gap:
                props["x"] = cap.gap
            if cap.background != current["c"]:
                props["c"] = cap.background
                current["c"] = cap.background
            colours = _kle_colours(cap)
            if colours != current["t"]:
                props["t"] = colours
                current["t"] = colours
            if cap.width != 1.0:
                props["w"] = cap.width
            if any(_visual_length(text) > 2 for text in cap.labels.values()):
                props["f"] = 3
            if props:
                items.append(props)
            items.append(_kle_labels(cap))
        out.append(items)
    return json.dumps(out, indent=2, ensure_ascii=False) + "\n"


def _slots(cap: Cap) -> list[str]:
    slots = [""] * 12
    for name, text in cap.labels.items():
        slots[POSITIONS[name]] = text
    return slots


def _kle_labels(cap: Cap) -> str:
    return "\n".join(_slots(cap)).rstrip("\n")


def _kle_colours(cap: Cap) -> str:
    slots = [""] * 12
    for name, colour in cap.colours.items():
        slots[POSITIONS[name]] = colour
    if not any(slots):
        return ""
    return "\n".join(slots).rstrip("\n")


# --------------------------------------------------------------------------
# SVG
# --------------------------------------------------------------------------

#: Pixels per key unit. The finished picture is about 1700 pixels wide, which
#: is what README.md has always shown.
UNIT = 96
#: Gap between keycaps, and the inset of the lighter face inside the cap.
GAP = 6
FACE_INSET = (8, 4, 8, 12)  # left, top, right, bottom
CAP_RADIUS = 10
FACE_RADIUS = 7
PADDING = 11
MARGIN = 8

CHARACTER_SIZE = 30
#: For a label that is two or three characters, such as a dead key drawn as its
#: root next to its default.
PAIR_SIZE = 20
WORD_SIZE = 16

#: The lighter face of each keycap, matching the picture this replaces.
FACE = {
    PLAIN_CAP: "#fcfcfc",
    DEAD_CAP: "#ffd6d6",
    CONTROL_CAP: "#c1dbfb",
    "#ffffff": "#ffffff",
}

#: Where each label sits on the face, and how it is anchored.
ANCHORS = {
    "tl": ("start", "hanging", 0.0, 0.0),
    "tr": ("end", "hanging", 1.0, 0.0),
    "bl": ("start", "auto", 0.0, 1.0),
    "br": ("end", "auto", 1.0, 1.0),
    "c": ("middle", "middle", 0.5, 0.5),
    "bc": ("middle", "auto", 0.5, 1.0),
}


def size(layout: Layout) -> tuple[int, int]:
    """The picture's size in pixels."""
    rows = build(layout)
    width = max(sum(cap.width + cap.gap for cap in row.caps) for row in rows)
    height = sum(1 + row.gap for row in rows)
    return round(width * UNIT) + 2 * MARGIN, round(height * UNIT) + 2 * MARGIN


def render_svg(layout: Layout) -> str:
    """Return a self-contained SVG drawing of the layout."""
    rows = build(layout)
    pixel_width, pixel_height = size(layout)

    out: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{pixel_width}"'
        f' height="{pixel_height}" viewBox="0 0 {pixel_width} {pixel_height}"'
        f' role="img" aria-label="{escape_attribute(layout.name)} keyboard layout">',
        f"  <title>{escape_content(layout.name)} {layout.version}</title>",
        "  <defs><style>",
        "    @font-face {",
        '      font-family: "Keyboard";',
        f'      src: url(data:font/woff2;base64,{WOFF2_BASE64}) format("woff2");',
        "    }",
        '    text { font-family: "Keyboard", "DejaVu Sans", sans-serif; }',
        "  </style></defs>",
    ]

    top = MARGIN
    for row in rows:
        top += round(row.gap * UNIT)
        left = MARGIN
        for cap in row.caps:
            left += round(cap.gap * UNIT)
            out.extend(_draw(cap, left, top))
            left += round(cap.width * UNIT)
        top += UNIT
    out.append("</svg>")
    out.append("")
    return "\n".join(out)


def _visual_length(text: str) -> int:
    """Characters that take up room; a combining mark rides on the one before."""
    return sum(1 for char in text if unicodedata.category(char) not in ("Mn", "Me", "Mc"))


def _font_size(text: str) -> int:
    length = _visual_length(text)
    if length <= 1:
        return CHARACTER_SIZE
    if length <= 3:
        return PAIR_SIZE
    return WORD_SIZE


def _draw(cap: Cap, left: int, top: int) -> list[str]:
    width = round(cap.width * UNIT) - GAP
    height = UNIT - GAP
    inset_left, inset_top, inset_right, inset_bottom = FACE_INSET
    face_left = left + inset_left
    face_top = top + inset_top
    face_width = width - inset_left - inset_right
    face_height = height - inset_top - inset_bottom

    out = [
        "  <g>",
        f'    <rect x="{left}" y="{top}" width="{width}" height="{height}"'
        f' rx="{CAP_RADIUS}" fill="{cap.background}"/>',
        f'    <rect x="{face_left}" y="{face_top}" width="{face_width}"'
        f' height="{face_height}" rx="{FACE_RADIUS}" fill="{FACE[cap.background]}"/>',
    ]
    for name, text in cap.labels.items():
        size = _font_size(text)
        anchor, baseline, fx, fy = ANCHORS[name]
        x = face_left + PADDING + (face_width - 2 * PADDING) * fx
        y = face_top + PADDING + (face_height - 2 * PADDING) * fy
        colour = cap.colours.get(name, TEXT)
        out.append(
            f'    <text x="{x:.0f}" y="{y:.0f}" font-size="{size}" fill="{colour}"'
            f' text-anchor="{anchor}" dominant-baseline="{baseline}">{escape_content(text)}</text>'
        )
    out.append("  </g>")
    return out


def generate(layout: Layout, root: Path) -> dict[str, str | bytes]:
    return {
        "assets/keyboard-layout.json": render_kle(layout),
        "assets/keyboard-layout.svg": render_svg(layout),
    }
