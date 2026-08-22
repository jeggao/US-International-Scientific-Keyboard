"""The overview picture has to say the same thing as the layout."""

import json
import re

import pytest

from kbdlayout import source
from kbdlayout.checks.assets import png_size
from kbdlayout.generators import picture
from kbdlayout.generators._picture_font import WOFF2_BASE64
from kbdlayout.project import LAYOUT_SOURCE


@pytest.fixture(scope="module")
def layout(repo_root):
    return source.load(repo_root / LAYOUT_SOURCE)


def _caps(layout):
    return [cap for row in picture.build(layout) for cap in row.caps]


def test_every_key_of_the_layout_is_drawn(layout):
    drawn = "".join(text for cap in _caps(layout) for text in cap.labels.values())
    for key in layout.keys:
        if key.id in ("LSGT", "KPDL"):
            # The picture draws an ANSI keyboard, which has neither.
            continue
        for level in ("normal", "shift", "altgr", "altgr_shift"):
            output = key.outputs.get(level)
            if output is None:
                continue
            expected = output.char
            if output.dead:
                dead_key = layout.dead_key(output.code_point)
                expected = chr(dead_key.default)
            if ord(expected) in picture.WORD_LABELS or key.id == "SPCE":
                continue
            assert expected in drawn, (key.id, level, expected)


def test_a_dead_key_is_drawn_in_red_and_a_plain_one_in_black(layout):
    for row in picture.build(layout):
        for cap in row.caps:
            for name, colour in cap.colours.items():
                assert colour in (picture.TEXT, picture.DEAD_TEXT, picture.ROOT_TEXT), name


def test_the_keycap_is_pink_exactly_when_the_key_carries_a_dead_key(layout):
    caps = picture.build(layout)
    number_row = caps[0].caps
    tilde = number_row[0]  # TLDE: two dead keys
    assert tilde.background == picture.DEAD_CAP
    one = number_row[1]  # AE01: no dead key
    assert one.background == picture.PLAIN_CAP


def test_the_root_is_drawn_only_where_it_is_reachable_and_not_a_diacritic(layout):
    shown = {
        f"U+{dead_key.root:04X}"
        for dead_key in layout.dead_keys
        if picture.shows_root(layout, dead_key.root)
    }
    # ¦ for the ligatures, ϶ for set membership, ɐ for set inclusion. Ħ, Ƶ and µ
    # are placeholders their dead key never emits, so drawing them would mislead.
    assert shown == {"U+00A6", "U+03F6", "U+0250"}


def test_the_kle_source_is_valid_json_with_a_row_per_keyboard_row(layout):
    data = json.loads(picture.render_kle(layout))
    assert isinstance(data[0], dict) and "name" in data[0]
    assert len(data) - 1 == len(picture.build(layout))


def test_the_svg_is_self_contained(layout):
    svg = picture.render_svg(layout)
    assert svg.startswith("<?xml")
    assert "data:font/woff2;base64," in svg, "the font has to travel with the picture"
    assert "http://" not in svg.replace("http://www.w3.org/2000/svg", "")


def test_the_embedded_font_covers_every_character_drawn(layout):
    """If this fails, run `python3 tools/subset_font.py`."""
    import base64
    import io

    from fontTools.ttLib import TTFont

    font = TTFont(io.BytesIO(base64.b64decode(WOFF2_BASE64)), fontNumber=0, lazy=True)
    covered: set[int] = set()
    for table in font["cmap"].tables:
        covered |= set(table.cmap)
    missing = {char for char in picture.characters(layout) if ord(char) not in covered}
    assert not missing, sorted(missing)


def test_the_svg_declares_the_size_the_committed_png_has(layout, repo_root):
    svg = picture.render_svg(layout)
    width = int(re.search(r'width="(\d+)"', svg).group(1))
    height = int(re.search(r'height="(\d+)"', svg).group(1))
    assert (width, height) == picture.size(layout)
    assert png_size((repo_root / "assets" / "keyboard-layout.png").read_bytes()) == (
        width,
        height,
    )


def test_a_combining_mark_is_drawn_on_a_dotted_circle(layout):
    """A lone combining mark would otherwise latch on to whatever precedes it."""
    import unicodedata

    found = 0
    for cap in _caps(layout):
        for text in cap.labels.values():
            for index, char in enumerate(text):
                if unicodedata.category(char) in ("Mn", "Me", "Mc"):
                    assert index > 0 and text[index - 1] == "◌", text
                    found += 1
    assert found, "the picture should draw at least one combining mark"


def test_render_fails_when_there_is_no_browser(monkeypatch, repo_root, capsys):
    """A green picture job has to mean the picture was actually rendered."""
    from kbdlayout import rasterise
    from kbdlayout.cli import main

    monkeypatch.setattr(rasterise, "find_chromium", lambda: None)
    assert main(["--root", str(repo_root), "render"]) == 1
    assert main(["--root", str(repo_root), "render", "--check"]) == 1
    assert "no Chromium found" in capsys.readouterr().err
