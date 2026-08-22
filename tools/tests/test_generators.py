"""The generated files must match what is committed, and mean what we think.

The Windows test is the important one: the ``.klc`` this repository shipped
before the layout moved into TOML is reproduced byte for byte, which is what
proves the move lost nothing.
"""

import os
import re
import shutil
import subprocess
import unicodedata

import pytest

from kbdlayout import keysyms as keysyms_module
from kbdlayout import klc as klc_parser
from kbdlayout import source
from kbdlayout.build import as_bytes, render_all
from kbdlayout.generators import linux_xkb, windows_klc
from kbdlayout.keys import BY_SCAN_CODE
from kbdlayout.keysyms import LATIN1_KEYSYMS
from kbdlayout.model import FALLBACK_BASES
from kbdlayout.project import LAYOUT_SOURCE

KLC_NAME = "US International Scientific.klc"
STATE_TO_LEVEL = {0: "normal", 1: "shift", 2: "ctrl", 6: "altgr", 7: "altgr_shift"}


@pytest.fixture(scope="module")
def layout(repo_root):
    return source.load(repo_root / LAYOUT_SOURCE)


def test_every_generated_file_is_committed_and_current(repo_root, layout):
    for relative, content in render_all(layout, repo_root).items():
        path = repo_root / relative
        assert path.exists(), f"{relative} has never been generated"
        assert path.read_bytes() == as_bytes(content), f"{relative} is out of date"


def test_klc_matches_the_file_msklc_produced(repo_root, layout):
    """Byte-for-byte equality with the .klc as it was before the TOML existed."""
    assert windows_klc.to_bytes(layout) == (repo_root / KLC_NAME).read_bytes()


def test_klc_parses_back_into_the_same_layout(repo_root, layout):
    """A second, independent check: read the .klc and compare it to the source."""
    parsed = klc_parser.parse(repo_root / KLC_NAME)
    assert len(parsed.layout) == len(layout.keys)
    for row in parsed.layout:
        key = layout.key(BY_SCAN_CODE[row.scan_code].id)
        assert key is not None, f"scan code {row.scan_code:02x} is missing from the source"
        assert int(key.caps) == int(row.cap_flag)
        for state, cell in row.outputs.items():
            output = key.outputs.get(STATE_TO_LEVEL[state])
            if cell.code_point is None:
                assert output is None
                continue
            assert output is not None
            assert output.code_point == cell.code_point
            assert output.dead == cell.is_dead
    assert [d.root for d in parsed.dead_keys] == [
        d.root
        for d in layout.dead_keys_in_declaration_order(
            tuple(BY_SCAN_CODE[sc].id for sc in sorted(BY_SCAN_CODE))
        )
    ]
    for parsed_dead in parsed.dead_keys:
        dead_key = layout.dead_key(parsed_dead.root)
        assert dead_key is not None
        assert [(e.base, e.composite) for e in parsed_dead.entries] == dead_key.entries


def test_klc_is_utf16_with_a_bom_and_crlf(layout):
    data = windows_klc.to_bytes(layout)
    assert data[:2] == b"\xff\xfe"
    text = data.decode("utf-16")
    assert "\r\n" in text
    assert text.replace("\r\n", "").count("\n") == 0
    assert text.rstrip().endswith("ENDKBD")


def test_klc_cells_use_msklc_spelling():
    assert windows_klc._cell(ord("q"), False) == "q"
    assert windows_klc._cell(ord("1"), False) == "1"
    assert windows_klc._cell(ord("!"), False) == "0021"
    assert windows_klc._cell(0x0300, True) == "0300@"
    assert windows_klc._cell(None, False) == "-1"


# --------------------------------------------------------------------------
# Linux
# --------------------------------------------------------------------------

KEY_LINE = re.compile(r'key <(\w+)>\s+\{ type\[Group1\] = "([A-Z_0-9]+)", \[ ([^\]]*) \] \};')


def parse_symbols(text: str) -> dict[str, tuple[str, list[str]]]:
    return {
        key_id: (key_type, [s.strip() for s in symbols.split(",")])
        for key_id, key_type, symbols in KEY_LINE.findall(text)
    }


def test_xkb_lists_four_levels_in_the_documented_order(layout):
    keys = parse_symbols(linux_xkb.render_symbols(layout))
    reverse = {name: code for code, name in LATIN1_KEYSYMS.items()}
    dead = {linux_xkb.leader(d): d.root for d in layout.dead_keys if linux_xkb.leader(d)}

    def resolve(symbol: str) -> int | None:
        if symbol in dead:
            return dead[symbol]
        if re.fullmatch(r"U[0-9A-F]{4}", symbol):
            return int(symbol[1:], 16)
        return reverse.get(symbol)

    checked = 0
    for key in layout.keys:
        if key.id in linux_xkb.SKIP_KEYS:
            continue
        assert key.id in keys, f"{key.id} is missing from the symbols file"
        _key_type, symbols = keys[key.id]
        for index, level in enumerate(linux_xkb.XKB_LEVELS):
            output = key.outputs.get(level)
            if output is None:
                continue
            assert resolve(symbols[index]) == output.code_point, (
                f"{key.id} {level}: {symbols[index]}"
            )
            checked += 1
    assert checked > 150


def test_xkb_uses_the_alphabetic_type_exactly_for_letter_keys(layout):
    keys = parse_symbols(linux_xkb.render_symbols(layout))
    for key in layout.keys:
        if key.id in linux_xkb.SKIP_KEYS:
            continue
        key_type, _symbols = keys[key.id]
        expected = linux_xkb.ALPHABETIC_TYPE if key.caps else linux_xkb.PLAIN_TYPE
        assert key_type == expected, key.id


def test_xkb_uses_a_dead_keysym_wherever_one_exists(layout):
    text = linux_xkb.render_symbols(layout)
    for dead_key in layout.dead_keys:
        if linux_xkb.leader(dead_key):
            assert linux_xkb.leader(dead_key) in text, linux_xkb.leader(dead_key)


def test_compose_covers_every_dead_key_mapping(layout):
    text = linux_xkb.render_compose(layout)
    assert 'include "%L"' in text
    for dead_key in layout.dead_keys:
        leader = linux_xkb.leader(dead_key) or LATIN1_KEYSYMS.get(dead_key.root)
        assert leader, f"no leader keysym for U+{dead_key.root:04X}"
        for base, composite in dead_key.entries:
            sequence = f"<{leader}> <{LATIN1_KEYSYMS[base]}>"
            assert sequence in text, sequence
            assert f"U{composite:04X}" in text


def test_every_dead_key_base_has_a_keysym(layout):
    for dead_key in layout.dead_keys:
        for base, _composite in dead_key.entries:
            assert base in LATIN1_KEYSYMS, f"U+{base:04X} has no X11 keysym name"


# --------------------------------------------------------------------------
# Integration: does the generated XKB file actually compile?
# --------------------------------------------------------------------------

XKBCOMP = shutil.which("xkbcomp")

#: CI installs xkbcomp and sets this, so that the compile test failing to run
#: is itself a failure. Without it the test would quietly skip, and deleting
#: the separate CI job that used to compile the file would have lost the
#: coverage silently.
REQUIRE_XKBCOMP = os.environ.get("KBDLAYOUT_REQUIRE_XKBCOMP") == "1"
KEYMAP = """xkb_keymap {{
    xkb_keycodes  {{ include "evdev+aliases(qwerty)" }};
    xkb_types     {{ include "complete"              }};
    xkb_compat    {{ include "complete"              }};
    xkb_symbols   {{ include "pc+{symbols}"          }};
    xkb_geometry  {{ include "pc(pc105)"             }};
}};
"""


def _compile(tmp_path, symbols: str, include: str | None = None) -> tuple[int, str]:
    keymap = tmp_path / f"{symbols.replace('(', '_').replace(')', '')}.in"
    keymap.write_text(KEYMAP.format(symbols=symbols))
    command = [XKBCOMP]
    if include:
        command += [f"-I{include}"]
    command += ["-xkb", "-o", str(tmp_path / "out.xkb"), str(keymap)]
    finished = subprocess.run(command, capture_output=True, text=True)
    return finished.returncode, finished.stderr + finished.stdout


@pytest.mark.skipif(
    XKBCOMP is None and not REQUIRE_XKBCOMP,
    reason="xkbcomp is not installed (set KBDLAYOUT_REQUIRE_XKBCOMP=1 to demand it)",
)
def test_generated_xkb_compiles_as_cleanly_as_the_stock_us_layout(tmp_path, layout):
    assert XKBCOMP is not None, (
        "KBDLAYOUT_REQUIRE_XKBCOMP=1 is set but xkbcomp is not installed; "
        "install x11-xkb-utils and xkb-data"
    )
    include = tmp_path / "xkb"
    (include / "symbols").mkdir(parents=True)
    linux = layout.config("linux")
    name = linux.symbols_file
    (include / "symbols" / name).write_text(linux_xkb.render_symbols(layout))

    code, log = _compile(tmp_path, f"{name}({linux.variant})", str(include))
    assert code == 0, log

    baseline_code, baseline_log = _compile(tmp_path, "us")
    assert baseline_code == 0, baseline_log
    # The stock layout produces a page of "No symbols defined for <X>" notes about
    # keys no layout defines. Ours must not add anything to that list.
    assert sorted(log.splitlines()) == sorted(baseline_log.splitlines())


def test_compose_matches_windows_for_every_printable_base(layout):
    """Linux and Windows must agree on what every dead key + ASCII base produces.

    On Windows an unmapped base yields the dead key's root character followed by
    the base character. The Compose file has to say the same thing, both to match
    and to shadow whatever the system table defines for a borrowed dead keysym.
    """
    text = linux_xkb.render_compose(layout)
    defined: dict[tuple[str, str], str] = {}
    for line in text.splitlines():
        match = re.match(r'<(\S+)> <(\S+)>\s+: "((?:[^"\\]|\\.)*)"', line)
        if match:
            leader, base, result = match.groups()
            defined[(leader, base)] = result.replace('\\"', '"').replace("\\\\", "\\")

    from kbdlayout.keysyms import keysym

    missing, wrong = [], []
    for dead_key in layout.dead_keys:
        mapping = dead_key.mapping
        for base in FALLBACK_BASES:
            key = (linux_xkb.leader(dead_key), keysym(base))
            windows = chr(mapping[base]) if base in mapping else dead_key.root_char + chr(base)
            if key not in defined:
                missing.append(key)
            elif defined[key] != windows:
                wrong.append((key, defined[key], windows))
    assert not missing, missing[:5]
    assert not wrong, wrong[:5]


def test_every_dead_key_has_a_distinct_keysym_value(layout):
    """Names are not enough: dead_perispomeni *is* dead_tilde, value 0xFE53.

    Compose matches on the keysym value, so two dead keys whose names differ but
    whose values agree would be one dead key wearing two hats.
    """
    seen: dict[int, str] = {}
    for dead_key in layout.dead_keys:
        assert linux_xkb.leader(dead_key), f"U+{dead_key.root:04X} has no leader"
        value = keysyms_module.keysym_value(linux_xkb.leader(dead_key))
        assert value is not None, linux_xkb.leader(dead_key)
        assert value not in seen, (
            f"U+{dead_key.root:04X} ({linux_xkb.leader(dead_key)}) collides with "
            f"{seen[value]} at keysym 0x{value:04X}"
        )
        seen[value] = f"U+{dead_key.root:04X}"


def test_a_dead_key_never_shares_a_keysym_with_a_plain_character(layout):
    """`<` is typed plainly and is also a dead key root; they must differ on Linux."""
    dead = {
        keysyms_module.keysym_value(linux_xkb.leader(dead_key)) for dead_key in layout.dead_keys
    }
    for key in layout.keys:
        for level in ("normal", "shift"):
            output = key.outputs.get(level)
            if output is None:
                continue
            value = keysyms_module.keysym_value(keysyms_module.keysym(output.code_point))
            assert value not in dead, (
                f"{key.id} types U+{output.code_point:04X} plainly and it is also a dead key"
            )


def test_a_combining_mark_is_never_used_where_a_dead_keysym_belongs(layout):
    """U0300 is `combining_grave`, a different keysym from `dead_grave`.

    Emitting the combining mark would put a character on the key instead of a
    dead key, and no Compose rule would ever fire.
    """
    for dead_key in layout.dead_keys:
        leader = linux_xkb.leader(dead_key)
        if leader.startswith("U"):
            code_point = int(leader[1:], 16)
            assert unicodedata.category(chr(code_point)) not in ("Mn", "Me", "Mc"), (
                f"U+{dead_key.root:04X} leads with the combining mark {leader}"
            )


def test_the_capslock_difference_is_exactly_the_four_documented_characters(layout):
    """X11 cannot express the Windows Caps Lock rule exactly; pin what differs.

    If a layout change makes this list grow, that is a new user-visible
    difference between the platforms and belongs in the documentation.
    """
    differences = linux_xkb.capslock_differences(layout)
    assert [(key_id, level, char) for key_id, level, char, _upper in differences] == [
        ("AD02", "altgr", "ϵ"),
        ("AD08", "altgr", "ı"),
        ("AC02", "altgr", "ß"),
        ("AC04", "altgr", "ϝ"),
    ]
    header = linux_xkb.render_symbols(layout).split("xkb_symbols")[0]
    for key_id, _level, char, upper in differences:
        assert f"{key_id} " in header and f"{char} -> {upper}" in header


def test_no_compose_rule_is_a_prefix_of_another(layout):
    """Two rules where one extends the other make one of them unreachable."""
    sequences = set()
    for line in linux_xkb.render_compose(layout).splitlines():
        match = re.match(r"(<\S+> <\S+>)\s+:", line)
        if match:
            assert match.group(1) not in sequences, f"duplicate rule {match.group(1)}"
            sequences.add(match.group(1))
    assert len(sequences) == sum(len(FALLBACK_BASES) for _ in layout.dead_keys)
