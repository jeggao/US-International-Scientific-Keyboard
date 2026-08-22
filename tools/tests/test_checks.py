"""Regression tests for the checks themselves.

Each case takes the real repository, reintroduces one of the defects the checks
were written for, and asserts that it is reported. A check that cannot fail is
not a check.
"""

import json
import shutil
from pathlib import Path

import pytest

from kbdlayout import (
    checks_assets,
    checks_generated,
    checks_readme,
    checks_repo,
    source,
)
from kbdlayout.cli import LAYOUT_SOURCE
from kbdlayout.report import Reporter

KLC_NAME = "US International Scientific.klc"


@pytest.fixture
def sandbox(tmp_path, repo_root):
    for name in (KLC_NAME, "README.md"):
        shutil.copy2(repo_root / name, tmp_path / name)
    for directory in ("assets", "layout", "dist"):
        shutil.copytree(repo_root / directory, tmp_path / directory)
    return tmp_path


def run(root: Path) -> list[str]:
    reporter = Reporter(root)
    layout = source.load(root / LAYOUT_SOURCE)
    checks_generated.check(root, layout, reporter)
    checks_readme.check(root / "README.md", layout, reporter)
    checks_assets.check(root / "assets", layout, reporter)
    checks_repo.check(root, reporter)
    return [f.format_text() for f in reporter.findings]


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not found in {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def edit_klc(path: Path, old: str, new: str) -> None:
    text = path.read_bytes().decode("utf-16")
    assert old in text, f"{old!r} not found in the .klc"
    path.write_bytes(("﻿" + text.lstrip("﻿").replace(old, new, 1)).encode("utf-16-le"))


def test_repository_is_clean(repo_root):
    assert run(repo_root) == []


def test_wrong_code_point_in_a_key_table(sandbox):
    edit(sandbox / "README.md", "|U+2032|PRIME|", "|U+2033|PRIME|")
    findings = run(sandbox)
    assert any("U+2033" in f and "readme-keymap" in f for f in findings)


def test_wrong_character_name_in_a_key_table(sandbox):
    edit(sandbox / "README.md", "|U+221E|INFINITY|", "|U+221E|INFINITY SIGN|")
    assert any("INFINITY SIGN" in f for f in run(sandbox))


def test_dead_key_composite_out_of_step(sandbox):
    edit(sandbox / "README.md", "|Composites|àèìòùỳǹẁ", "|Composites|àèìòùỳǹẁx")
    findings = run(sandbox)
    assert any("readme-deadkey" in f for f in findings)


def test_dead_key_default_mismatch(sandbox):
    edit(
        sandbox / "README.md",
        "|Default|U+00B4 ACUTE ACCENT (´)|",
        "|Default|U+0060 GRAVE ACCENT (`)|",
    )
    assert any("default is documented as U+0060" in f for f in run(sandbox))


def test_undocumented_dead_key_base(sandbox):
    edit(sandbox / "README.md", "|Bases|`CHIRZ`|", "|Bases|`CHIR`|")
    assert any("is not documented" in f or "do not line up" in f for f in run(sandbox))


def test_bare_combining_mark_in_a_key_table(sandbox):
    edit(sandbox / "README.md", "|<kbd>*</kbd>|˙   |", "|<kbd>*</kbd>|̇   |")
    assert any("bare combining mark" in f for f in run(sandbox))


def test_stray_zero_width_joiner(sandbox):
    edit(sandbox / "README.md", "|<kbd>*</kbd>|", "|‍<kbd>*</kbd>|")
    assert any("readme-stray-character" in f for f in run(sandbox))


def test_broken_table_row(sandbox):
    edit(sandbox / "README.md", "|Default|U+02C7 CARON (ˇ)|", "|Default|U+02C7 CARON (ˇ)")
    assert any("does not end with '|'" in f for f in run(sandbox))


def test_dangling_anchor(sandbox):
    edit(sandbox / "README.md", "(#quick-start-guide)", "(#quick-start)")
    assert any("readme-anchor" in f for f in run(sandbox))


def test_missing_relative_asset(sandbox):
    (sandbox / "assets" / "check.svg").unlink()
    assert any("readme-link" in f for f in run(sandbox))


def test_dead_key_count_in_prose(sandbox):
    edit(sandbox / "README.md", "the 28 dead keys", "the 27 dead keys")
    assert any("prose says 27 dead keys" in f for f in run(sandbox))


def test_json_caption_disagrees_with_the_layout(sandbox):
    path = sandbox / "assets" / "keyboard-layout.json"
    edit(path, '"Q\\n\\n\u2261\\n\u00f7"', '"Q\\n\\n\u2261\\n\u00d7"')
    assert any("assets-json" in f for f in run(sandbox))


def test_json_palette_typo(sandbox):
    path = sandbox / "assets" / "keyboard-layout.json"
    edit(path, '"#e5abab"', '"#e4abab"')
    assert any("assets-palette" in f for f in run(sandbox))


def test_json_must_parse(sandbox):
    path = sandbox / "assets" / "keyboard-layout.json"
    path.write_text("[", encoding="utf-8")
    assert any("invalid JSON" in f for f in run(sandbox))


def test_json_is_valid_and_newline_terminated(repo_root):
    """The file is hand-edited, so keep it in a stable, diff-friendly shape."""
    text = (repo_root / "assets" / "keyboard-layout.json").read_text(encoding="utf-8")
    assert text.endswith("\n")
    json.loads(text)


def test_missing_final_newline_is_reported(sandbox):
    path = sandbox / "assets" / "keyboard-layout.json"
    path.write_bytes(path.read_bytes().rstrip(b"\n"))
    assert any("does not end with a newline" in f for f in run(sandbox))


def test_hand_edited_klc_is_reported_as_stale(sandbox):
    edit_klc(
        sandbox / KLC_NAME,
        "// DIGIT ONE, EXCLAMATION MARK",
        "// DIGIT TWO, EXCLAMATION MARK",
    )
    assert any("generated-stale" in f and KLC_NAME in f for f in run(sandbox))


def test_hand_edited_xkb_file_is_reported_as_stale(sandbox):
    edit(sandbox / "dist/linux/symbols/us_intl_sci", "dead_grave", "dead_acute")
    assert any("generated-stale" in f for f in run(sandbox))


def test_deleted_generated_file_is_reported(sandbox):
    (sandbox / "dist/linux/us_intl_sci.XCompose").unlink()
    assert any("generated-missing" in f for f in run(sandbox))


def test_changing_the_source_makes_every_target_stale(sandbox):
    edit(sandbox / LAYOUT_SOURCE, 'altgr = "′"', 'altgr = "U+2033"')
    findings = run(sandbox)
    assert any("generated-stale" in f and KLC_NAME in f for f in findings)
    assert any("generated-stale" in f and "us_intl_sci" in f for f in findings)
