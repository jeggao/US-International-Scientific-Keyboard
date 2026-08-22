"""The generated .keylayout must be well formed and mean what the layout says.

None of this has been run on macOS -- see the warning in the generator. What
these tests can establish is that the file is structurally sound and that every
character and every dead key composition in it agrees with the layout source and
with the other two platforms.
"""

import re
import xml.etree.ElementTree as ET

import pytest

from kbdlayout import source
from kbdlayout.generators import linux_xkb, macos_keylayout
from kbdlayout.generators.windows_klc import MAX_CODE_POINT
from kbdlayout.keys import position
from kbdlayout.model import FALLBACK_BASES
from kbdlayout.project import LAYOUT_SOURCE

#: XML 1.0 forbids references to most C0 controls, and Python's parser applies
#: 1.0 rules whatever the declaration says. Apple's layouts use them anyway, so
#: swap them for a placeholder before parsing and remember what was there.
ILLEGAL = re.compile(r"&#x00(0[0-8BCEF]|1[0-9A-F]);", re.IGNORECASE)


@pytest.fixture(scope="module")
def layout(repo_root):
    return source.load(repo_root / LAYOUT_SOURCE)


@pytest.fixture(scope="module")
def text(layout):
    return macos_keylayout.render(layout)


@pytest.fixture(scope="module")
def tree(text):
    return ET.fromstring(ILLEGAL.sub(lambda m: f"[[{m.group(1)}]]", text))


def unescape(value: str) -> str:
    value = re.sub(r"\[\[([0-9A-Fa-f]{2})\]\]", lambda m: chr(int(m.group(1), 16)), value)
    return re.sub(r"&#x([0-9A-Fa-f]+);", lambda m: chr(int(m.group(1), 16)), value)


# --------------------------------------------------------------------------
# Structure
# --------------------------------------------------------------------------


def test_the_file_is_well_formed(tree):
    assert tree.tag == "keyboard"


def test_it_declares_xml_11_because_of_the_control_characters(text):
    assert text.startswith('<?xml version="1.1" encoding="UTF-8"?>')
    assert ILLEGAL.search(text), "the function keys should need XML 1.1"


def test_action_ids_are_unique(tree):
    ids = [action.get("id") for action in tree.iter("action")]
    assert len(ids) == len(set(ids))


def test_no_key_carries_both_an_output_and_an_action(tree):
    for key in tree.iter("key"):
        assert (key.get("output") is None) != (key.get("action") is None), key.attrib


def test_key_codes_are_unique_within_each_key_map(tree):
    for key_map in tree.iter("keyMap"):
        codes = [key.get("code") for key in key_map.findall("key")]
        assert len(codes) == len(set(codes)), key_map.get("index")


def test_every_dead_state_is_reachable_and_terminated(tree, layout):
    started = {
        when.get("next") for action in tree.iter("action") for when in action if when.get("next")
    }
    terminated = {when.get("state") for when in tree.find("terminators")}
    expected = {macos_keylayout.state_id(d.root) for d in layout.dead_keys}
    assert started == expected
    assert terminated == expected


def test_every_state_referenced_by_an_action_exists(tree, layout):
    known = {"none", *(macos_keylayout.state_id(d.root) for d in layout.dead_keys)}
    for action in tree.iter("action"):
        for when in action:
            assert when.get("state") in known, when.attrib


def test_maxout_covers_the_longest_output(tree):
    longest = max(
        len(unescape(when.get("output", ""))) for action in tree.iter("action") for when in action
    )
    assert int(tree.get("maxout")) >= longest


def test_the_terminator_is_the_root_character(tree, layout):
    terminators = {
        when.get("state"): unescape(when.get("output")) for when in tree.find("terminators")
    }
    for dead_key in layout.dead_keys:
        assert terminators[macos_keylayout.state_id(dead_key.root)] == dead_key.root_char


def test_the_modifier_maps_cover_caps_lock_and_control(tree):
    selects = tree.find("modifierMap").findall("keyMapSelect")
    assert len(selects) == len(macos_keylayout.MODIFIER_MAPS)
    modifiers = [" ".join(m.get("keys") for m in select.findall("modifier")) for select in selects]
    assert "caps" in modifiers[2], "Caps Lock needs a map or it falls back to plain"
    for index in (3, 4):
        assert "anyOption" in modifiers[index]
        # README tells users Ctrl+Alt also reaches the AltGr levels.
        assert "anyControl?" in modifiers[index]


# --------------------------------------------------------------------------
# Agreement with the layout
# --------------------------------------------------------------------------


def resolve(tree) -> dict[tuple[int, int], str]:
    """What each (key code, keyMap index) produces with no dead key pending."""
    plain = {
        action.get("id"): unescape(when.get("output", ""))
        for action in tree.iter("action")
        for when in action
        if when.get("state") == "none" and when.get("output") is not None
    }
    dead = {
        action.get("id"): when.get("next")
        for action in tree.iter("action")
        for when in action
        if when.get("next")
    }
    out: dict[tuple[int, int], str] = {}
    for key_map in tree.iter("keyMap"):
        index = int(key_map.get("index"))
        for key in key_map.findall("key"):
            code = int(key.get("code"))
            if key.get("output") is not None:
                out[(code, index)] = unescape(key.get("output"))
            elif key.get("action") in plain:
                out[(code, index)] = plain[key.get("action")]
            else:
                out[(code, index)] = f"<{dead[key.get('action')]}>"
    return out


def test_every_key_and_level_matches_the_layout(tree, layout):
    produced = resolve(tree)
    checked = 0
    for key in layout.keys:
        code = position(key.id).macos_key_code
        for index, (level, _modifiers) in enumerate(macos_keylayout.MODIFIER_MAPS):
            wanted = level
            if level == "caps":
                wanted = "shift" if key.caps else "normal"
            output = key.outputs.get(wanted)
            if output is None:
                assert (code, index) not in produced or wanted == "ctrl"
                continue
            expected = (
                f"<{macos_keylayout.state_id(output.code_point)}>" if output.dead else output.char
            )
            assert produced[(code, index)] == expected, (key.id, level)
            checked += 1
    assert checked > 200


def test_the_function_keys_are_present_in_every_map(tree):
    fixed = {code for code, _cp, _label in macos_keylayout.FUNCTION_KEYS}
    for key_map in tree.iter("keyMap"):
        codes = {int(key.get("code")) for key in key_map.findall("key")}
        assert fixed <= codes, key_map.get("index")


def test_arrow_keys_use_apples_codes_not_the_x11_tables(tree):
    """The X11 macintosh table puts the arrows at 59-62; Apple puts them at 123-126."""
    arrows = {
        code: code_point
        for code, code_point, label in macos_keylayout.FUNCTION_KEYS
        if "Arrow" in label
    }
    assert set(arrows) == {123, 124, 125, 126}
    assert set(arrows.values()) == {0x1C, 0x1D, 0x1E, 0x1F}


def test_every_composition_matches_the_layout(tree, layout):
    compositions: dict[str, dict[str, str]] = {}
    for action in tree.iter("action"):
        base = None
        for when in action:
            if when.get("state") == "none" and when.get("output") is not None:
                base = unescape(when.get("output"))
        if base is None:
            continue
        for when in action:
            state = when.get("state")
            if state == "none" or when.get("output") is None:
                continue
            compositions.setdefault(state, {})[base] = unescape(when.get("output"))

    checked = 0
    for dead_key in layout.dead_keys:
        state = macos_keylayout.state_id(dead_key.root)
        mapping = dead_key.mapping
        for base in FALLBACK_BASES:
            composite = mapping.get(base)
            expected = chr(composite) if composite is not None else dead_key.root_char + chr(base)
            assert compositions[state][chr(base)] == expected, (state, hex(base))
            checked += 1
    assert checked == len(layout.dead_keys) * len(FALLBACK_BASES)


def test_macos_and_linux_agree_on_every_dead_key_result(layout):
    """The two generated fallback tables are built independently; compare them."""
    compose = linux_xkb.render_compose(layout)
    linux: dict[tuple[str, str], str] = {}
    for line in compose.splitlines():
        match = re.match(r'<(\S+)> <(\S+)>\s+: "((?:[^"\\]|\\.)*)"', line)
        if match:
            leader, base, result = match.groups()
            linux[(leader, base)] = result.replace('\\"', '"').replace("\\\\", "\\")

    from kbdlayout.keysyms import keysym

    for dead_key in layout.dead_keys:
        mapping = dead_key.mapping
        for base in FALLBACK_BASES:
            composite = mapping.get(base)
            expected = chr(composite) if composite is not None else dead_key.root_char + chr(base)
            assert linux[(linux_xkb.leader(dead_key), keysym(base))] == expected


def test_every_output_is_inside_the_bmp(tree):
    for element in tree.iter():
        value = element.get("output")
        if value:
            for char in unescape(value):
                assert ord(char) <= MAX_CODE_POINT
