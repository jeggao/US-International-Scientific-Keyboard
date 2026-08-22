"""Checks for the files under ``assets/``.

``keyboard-layout.json`` is the keyboard-layout-editor.com source for the
overview picture, so its key captions have to agree with the layout source.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from . import markdown as md
from .model import LEVEL_NAMES, Key, Layout, unicode_name
from .report import Reporter

#: Label indices used by this layout's keyboard-layout-editor source. The legend
#: key in the top row spells the same convention out for readers.
LABEL_SHIFT = 0
LABEL_NORMAL = 1
LABEL_ALTGR_SHIFT = 2
LABEL_ALTGR = 3
LEGEND_LABEL = "Shift\nNormal\nAltGr+Shift\nAltGr"

#: The four colours the README legend defines. Anything else is a typo: the
#: near-misses (#ff0202, #e4abab, #9900ff) are invisible to the eye but make the
#: source impossible to search.
PALETTE = {
    "#000000": "normal legend text",
    "#ff0000": "dead key text",
    "#9b00ff": "dead key root/default text",
    "#cccccc": "plain keycap",
    "#e5abab": "keycap with a dead key",
    "#98b2d1": "shift-state control keycap",
}

#: Captions that are words rather than characters produced by the layout.
WORD_LABELS = {
    "zwj": 0x200D,
    "Zero Width Space": 0x200B,
    "No-Break Space": 0x00A0,
}


def check(assets_dir: Path, layout: Layout, reporter: Reporter) -> None:
    layout_json = assets_dir / "keyboard-layout.json"
    if not layout_json.exists():
        reporter.add("assets", assets_dir, 0, "assets/keyboard-layout.json is missing")
        return
    try:
        data = json.loads(layout_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        reporter.add("assets-json", layout_json, exc.lineno, f"invalid JSON: {exc.msg}")
        return
    _check_shape(layout_json, data, reporter)
    _check_palette(layout_json, data, reporter)
    _check_labels(layout_json, data, layout, reporter)


def _iter_labels(data) -> list[str]:
    labels: list[str] = []
    for row in data[1:]:
        if not isinstance(row, list):
            continue
        labels.extend(item for item in row if isinstance(item, str))
    return labels


def _check_shape(path: Path, data, reporter: Reporter) -> None:
    if not isinstance(data, list) or not data:
        reporter.add("assets-json", path, 1, "expected a keyboard-layout-editor array")
        return
    if not isinstance(data[0], dict) or "name" not in data[0]:
        reporter.add("assets-json", path, 1, "first element should be the metadata object")
    if LEGEND_LABEL not in _iter_labels(data):
        reporter.add(
            "assets-json",
            path,
            1,
            f"the legend key spelling out the label order ({LEGEND_LABEL!r}) is missing",
        )


def _check_palette(path: Path, data, reporter: Reporter) -> None:
    seen: dict[str, int] = {}

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("c", "t") and isinstance(value, str):
                    for colour in value.split("\n"):
                        if colour:
                            seen[colour] = seen.get(colour, 0) + 1
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    for colour in sorted(seen):
        if colour in PALETTE:
            continue
        nearest = _nearest_palette_colour(colour)
        reporter.add(
            "assets-palette",
            path,
            1,
            (
                f"colour {colour} is not part of the documented legend palette"
                + (f"; did you mean {nearest} ({PALETTE[nearest]})?" if nearest else "")
            ),
        )


def _nearest_palette_colour(colour: str) -> str | None:
    try:
        value = int(colour.lstrip("#"), 16)
    except ValueError:
        return None
    best, best_distance = None, None
    for candidate in PALETTE:
        other = int(candidate.lstrip("#"), 16)
        distance = sum(
            abs(((value >> shift) & 0xFF) - ((other >> shift) & 0xFF)) for shift in (0, 8, 16)
        )
        if best_distance is None or distance < best_distance:
            best, best_distance = candidate, distance
    return best if best_distance is not None and best_distance <= 24 else None


#: Keys the picture does not draw: the ISO extra key, which an ANSI keyboard
#: does not have, and the numeric keypad.
UNDRAWN_KEYS = frozenset({"LSGT", "KPDL"})


def _check_labels(path: Path, data, layout: Layout, reporter: Reporter) -> None:
    by_shift: dict[str, Key] = {}
    by_normal: dict[str, Key] = {}
    for key in layout.keys:
        if key.id in UNDRAWN_KEYS:
            continue
        shift = key.outputs.get("shift")
        normal = key.outputs.get("normal")
        if shift is not None:
            by_shift.setdefault(shift.char, key)
        if normal is not None:
            by_normal.setdefault(normal.char, key)

    covered: set[str] = set()
    for label in _iter_labels(data):
        parts = label.split("\n")
        if len(parts) < 4:
            continue
        label = parts[LABEL_SHIFT].strip() or parts[LABEL_NORMAL].strip()
        key = by_shift.get(label) or by_normal.get(label)
        if key is None:
            continue
        covered.add(key.id)
        for index, level in ((LABEL_ALTGR_SHIFT, "altgr_shift"), (LABEL_ALTGR, "altgr")):
            caption = parts[index] if index < len(parts) else ""
            output = key.outputs.get(level)
            if output is None:
                continue
            _check_caption(path, label, level, caption, output.code_point, layout, reporter)

    for key in layout.keys:
        if key.id in UNDRAWN_KEYS or key.id == "SPCE":
            continue
        if key.id not in covered:
            reporter.add("assets-json", path, 1, f"key {key.id} has no caption in the picture")


def _check_caption(
    path: Path,
    key: str,
    level: str,
    caption: str,
    code_point: int,
    layout: Layout,
    reporter: Reporter,
) -> None:
    dead_key = layout.dead_key(code_point)
    allowed = {chr(code_point)}
    if dead_key is not None and dead_key.default is not None:
        allowed.add(chr(dead_key.default))

    if caption in WORD_LABELS:
        if chr(WORD_LABELS[caption]) not in allowed:
            reporter.add(
                "assets-json",
                path,
                1,
                (
                    f"key {key!r} in the {LEVEL_NAMES[level]} shift state: caption "
                    f"{caption!r} names U+{WORD_LABELS[caption]:04X}, which this key "
                    "does not produce"
                ),
            )
        return
    raw = caption.strip()
    shown = md.normalise_cluster(raw)
    if not shown:
        reporter.add(
            "assets-json",
            path,
            1,
            (
                f"key {key!r} in the {LEVEL_NAMES[level]} shift state has no caption, but the "
                f"layout produces U+{code_point:04X} ({unicode_name(code_point)})"
            ),
        )
        return
    if raw == shown and len(shown) == 1 and unicodedata.category(shown) in ("Mn", "Me"):
        reporter.add(
            "assets-json",
            path,
            1,
            (
                f"key {key!r} in the {LEVEL_NAMES[level]} shift state: caption is the bare "
                f"combining mark U+{ord(shown):04X}, which renders on top of neighbouring "
                "text; use the spacing form or prefix it with '◌'"
            ),
        )
        return
    if shown not in allowed:
        reporter.add(
            "assets-json",
            path,
            1,
            (
                f"key {key!r} in the {LEVEL_NAMES[level]} shift state: caption {shown!r} "
                f"does not match the layout (expected one of {sorted(allowed)!r})"
            ),
        )
