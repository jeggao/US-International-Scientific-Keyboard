import pytest

from kbdlint import klc as klc_module

LAYOUT_ROW = (
    "10\tQ\t\t1\tq\tQ\t-1\t00f7\t0301@\t\t"
    "// LATIN SMALL LETTER Q, LATIN CAPITAL LETTER Q, <none>, DIVISION SIGN, "
    "COMBINING ACUTE ACCENT"
)

SAMPLE = f"""KBD\tKBDTEST\t"Test (1.0.0)"

COPYRIGHT\t"(c) 2024 Nobody"

COMPANY\t"Nobody"

LOCALENAME\t"en-US"

LOCALEID\t"00000409"

VERSION\t1.0

SHIFTSTATE

0\t//Column 4
1\t//Column 5 : Shft
2\t//Column 6 :       Ctrl
6\t//Column 7 :       Ctrl Alt
7\t//Column 8 : Shft  Ctrl Alt

LAYOUT

//SC\tVK_\t\tCap\t0\t1\t2\t6\t7
//--\t----\t\t----\t----\t----\t----\t----\t----

{LAYOUT_ROW}

DEADKEY\t0301

0061\t00e1\t// a -> á
0020\t00b4\t//   -> ´

KEYNAME

01\tEsc

KEYNAME_EXT

1c\t"Num Enter"

KEYNAME_DEAD

0301\t"COMBINING ACUTE ACCENT"

DESCRIPTIONS

0409\tTest (1.0.0)

LANGUAGENAMES

0409\tEnglish (United States)

ENDKBD
"""


@pytest.fixture
def sample(tmp_path):
    path = tmp_path / "sample.klc"
    path.write_bytes(("﻿" + SAMPLE.replace("\n", "\r\n")).encode("utf-16-le"))
    return klc_module.parse(path)


def test_reads_bom_and_line_endings(sample):
    assert sample.had_bom is True
    assert sample.line_endings == {"crlf"}


def test_header_is_parsed(sample):
    assert sample.header["LOCALEID"].value == "00000409"
    assert sample.header["COMPANY"].value == "Nobody"


def test_layout_row_decodes_every_shift_state(sample):
    (row,) = sample.layout
    assert row.scan_code == 0x10
    assert row.virtual_key == "Q"
    assert row.outputs[0].char == "q"
    assert row.outputs[2].code_point is None
    assert row.outputs[6].code_point == 0x00F7
    assert row.outputs[7].is_dead is True


def test_dead_key_mapping_and_default(sample):
    dead_key = sample.dead_key(0x0301)
    assert dead_key is not None
    assert dead_key.mapping == {0x61: 0xE1, 0x20: 0xB4}
    assert dead_key.default == 0x00B4


def test_declared_dead_roots_match_sections(sample):
    assert sample.declared_dead_roots == sample.dead_key_roots == [0x0301]


def test_unicode_name_resolves_control_aliases():
    assert klc_module.unicode_name(0x001B) == "ESCAPE"
    assert klc_module.unicode_name(0x2014) == "EM DASH"


def test_parse_rejects_a_file_without_a_layout(tmp_path):
    path = tmp_path / "empty.klc"
    path.write_bytes('﻿KBD\tX\t"y"\r\n'.encode("utf-16-le"))
    with pytest.raises(klc_module.KlcParseError):
        klc_module.parse(path)
