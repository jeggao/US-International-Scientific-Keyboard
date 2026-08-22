import pytest

from kbdlayout import source
from kbdlayout.model import LayoutError

MINIMAL = """
[layout]
name = "Test"
version = "1.0.0"
copyright = "(c) 2024 Nobody"
company = "Nobody"

[layout.windows]
dll_name = "KBDTEST"
locale_name = "en-US"
locale_id = "00000409"
language_name = "English (United States)"

[layout.linux]
symbols_file = "test"
variant = "test"
description = "Test"

[[key]]
id = "AD01"
normal = "q"
shift = "Q"
altgr = "÷"
altgr_shift = { dead = "U+0301" }

[[dead_key]]
root = "U+0301"
category = "Acute"
xkb_leader = "dead_acute"
map = [["a", "á"], ["U+0020", "U+00B4"]]
"""


def test_minimal_layout_loads():
    layout = source.loads(MINIMAL)
    assert layout.description == "Test (1.0.0)"
    assert layout.key("AD01").outputs["altgr"].code_point == 0x00F7
    assert layout.key("AD01").outputs["altgr_shift"].dead is True
    assert layout.dead_key(0x0301).default == 0x00B4


def test_caps_is_derived_from_the_letter_pair():
    layout = source.loads(MINIMAL)
    assert layout.key("AD01").caps is True


def test_caps_can_be_pinned():
    layout = source.loads(MINIMAL.replace('id = "AD01"', 'id = "AD01"\ncaps = false'))
    assert layout.key("AD01").caps is False


@pytest.mark.parametrize(
    ("value", "expected"),
    [("q", 0x71), ("U+0301", 0x301), ("U+00B4", 0xB4), ("÷", 0xF7)],
)
def test_decode_char(value, expected):
    assert source.decode_char(value, "test") == expected


@pytest.mark.parametrize(
    ("code_point", "expected"),
    [(0x71, "q"), (0x20, "U+0020"), (0x0301, "U+0301"), (0x2032, "′")],
)
def test_encode_char_spells_out_what_would_not_survive_copying(code_point, expected):
    assert source.encode_char(code_point) == expected


def test_a_two_character_value_is_rejected():
    with pytest.raises(LayoutError, match="not a single character"):
        source.loads(MINIMAL.replace('altgr = "÷"', 'altgr = "ab"'))


def test_an_unknown_key_position_is_rejected():
    with pytest.raises(KeyError, match="unknown key position"):
        source.loads(MINIMAL.replace('id = "AD01"', 'id = "ZZ99"'))


def test_an_unknown_field_is_rejected():
    with pytest.raises(LayoutError, match="unknown field"):
        source.loads(MINIMAL.replace('normal = "q"', 'normal = "q"\nnromal = "q"'))


def test_a_dead_key_without_a_table_is_rejected():
    with pytest.raises(LayoutError, match="has no \\[\\[dead_key\\]\\] table"):
        source.loads(MINIMAL.replace('altgr = "÷"', 'altgr = { dead = "U+0302" }'))


def test_a_dead_key_with_no_space_entry_is_rejected():
    with pytest.raises(LayoutError, match="default character"):
        source.loads(MINIMAL.replace(', ["U+0020", "U+00B4"]', ""))


def test_a_character_outside_the_bmp_is_rejected():
    with pytest.raises(LayoutError, match="Basic Multilingual Plane"):
        source.loads(MINIMAL.replace('altgr = "÷"', 'altgr = "U+1D7D9"'))


def test_a_dead_key_root_above_the_msklc_limit_is_rejected():
    text = MINIMAL.replace('{ dead = "U+0301" }', '{ dead = "U+2032" }')
    text = text.replace('root = "U+0301"', 'root = "U+2032"')
    with pytest.raises(LayoutError, match="above the MSKLC limit"):
        source.loads(text)


def test_the_repository_source_round_trips(repo_root):
    """Rewriting the layout must reproduce the committed file exactly."""
    path = repo_root / "layout" / "us-intl-scientific.toml"
    layout = source.load(path)
    assert source.dumps(layout) == path.read_text(encoding="utf-8")
