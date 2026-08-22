"""Regression tests for the checks themselves.

Each case takes the real repository, reintroduces one of the defects the checks
were written for, and asserts that it is reported. A check that cannot fail is
not a check.
"""

import json
from pathlib import Path

import pytest
from conftest import KLC_NAME, edit, edit_klc

from kbdlayout import source
from kbdlayout.checks import CHECKS, run_checks
from kbdlayout.model import LayoutError
from kbdlayout.project import LAYOUT_SOURCE


def run(root: Path) -> list[str]:
    """Every finding, using the same orchestration the command line uses.

    Going through :func:`run_checks` rather than calling the check modules by
    hand is deliberate: a check that is registered but not wired up here would
    otherwise leave every test in this file passing without running it.
    """
    layout = source.load(root / LAYOUT_SOURCE)
    return [f.format_text() for f in run_checks(root, layout).findings]


def test_repository_is_clean(repo_root):
    assert run(repo_root) == []


def test_every_registered_check_runs(repo_root, monkeypatch):
    """run_checks must call each entry in CHECKS, not a hand-written subset."""
    called: list[str] = []
    for name in CHECKS:
        monkeypatch.setitem(
            CHECKS, name, lambda _root, _layout, _reporter, n=name: called.append(n)
        )
    layout = source.load(repo_root / LAYOUT_SOURCE)
    run_checks(repo_root, layout)
    assert called == list(CHECKS)


# The key-mapping and dead-key tables are generated now, so the defects these
# used to hunt for are reported as staleness -- README.md is a generated file
# like any other -- or cannot be expressed in the source at all.


@pytest.mark.parametrize(
    "old, new",
    [
        pytest.param("|U+2032|PRIME|", "|U+2033|PRIME|", id="code-point"),
        pytest.param("|U+221E|INFINITY|", "|U+221E|INFINITY SIGN|", id="character-name"),
        pytest.param("|Composites|àèìòùỳǹẁ", "|Composites|àèìòùỳǹẁx", id="composite"),
        pytest.param(
            "|Default|U+00B4 ACUTE ACCENT (´)|",
            "|Default|U+0060 GRAVE ACCENT (`)|",
            id="dead-key-default",
        ),
        pytest.param("|<kbd>*</kbd>|˙   |", "|<kbd>*</kbd>|̇   |", id="bare-combining-mark"),
    ],
)
def test_a_hand_edited_table_is_reported_as_stale(sandbox, old, new):
    edit(sandbox / "README.md", old, new)
    assert any("generated-stale" in f and "README.md" in f for f in run(sandbox))


def test_a_dead_key_base_the_documentation_omits_is_rejected_at_load(sandbox):
    """doc_bases must cover the mapping, so this cannot reach a generator."""
    edit(
        sandbox / LAYOUT_SOURCE,
        'doc_bases = ["aeiouynw AEIOUYNW"]',
        'doc_bases = ["aeiouyn AEIOUYNW"]',
    )
    with pytest.raises(LayoutError, match="doc_bases does not list it"):
        source.load(sandbox / LAYOUT_SOURCE)


def test_a_documented_base_the_layout_does_not_compose_is_rejected(sandbox):
    edit(
        sandbox / LAYOUT_SOURCE,
        'doc_bases = ["aeiouynw AEIOUYNW"]',
        'doc_bases = ["aeiouynwq AEIOUYNW"]',
    )
    with pytest.raises(LayoutError, match="which it does not compose"):
        source.load(sandbox / LAYOUT_SOURCE)


def test_a_key_without_its_reason_is_rejected(sandbox):
    edit(sandbox / LAYOUT_SOURCE, 'altgr_doc = "Math: first (1) derivative."\n', "")
    with pytest.raises(LayoutError, match="has no altgr_doc saying why"):
        source.load(sandbox / LAYOUT_SOURCE)


def test_a_dead_key_marker_on_a_plain_key_is_rejected(sandbox):
    edit(
        sandbox / LAYOUT_SOURCE,
        'altgr_doc = "Math: first (1) derivative."',
        'altgr_doc = "**Dead key: nonsense.**"',
    )
    with pytest.raises(LayoutError, match="described as a dead key but is not one"):
        source.load(sandbox / LAYOUT_SOURCE)


def test_a_missing_generated_block_is_reported(sandbox):
    edit(sandbox / "README.md", "<!-- generated: keys AE altgr -->", "")
    assert any("generated-unbuildable" in f for f in run(sandbox))


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


def test_a_hand_edited_picture_source_is_reported_as_stale(sandbox):
    edit(sandbox / "assets/keyboard-layout.json", "#e5abab", "#e4abab")
    assert any("generated-stale" in f for f in run(sandbox))


def test_a_corrupted_picture_source_is_reported_as_stale(sandbox):
    (sandbox / "assets/keyboard-layout.json").write_text("[", encoding="utf-8")
    assert any("generated-stale" in f for f in run(sandbox))


def test_a_picture_of_the_wrong_size_is_reported(sandbox):
    Image = pytest.importorskip(
        "PIL.Image", reason="pillow is an optional extra", exc_type=ImportError
    )

    path = sandbox / "assets/keyboard-layout.png"
    Image.open(path).crop((0, 0, 100, 100)).save(path)
    assert any("assets-picture" in f for f in run(sandbox))


def test_the_generated_dist_files_are_covered_by_the_hygiene_check(repo_root):
    """They have no recognisable suffix, so the old extension allowlist skipped them."""
    from kbdlayout.checks.repo import iter_text_files

    covered = {str(path.relative_to(repo_root)) for path, _data in iter_text_files(repo_root)}
    assert {
        "dist/linux/symbols/us_intl_sci",
        "dist/linux/us_intl_sci.XCompose",
        "dist/macos/US-International Scientific.keylayout",
    } <= covered
    # ...and the files that are deliberately not LF text are still left alone.
    assert KLC_NAME not in covered
    assert "assets/keyboard-layout.png" not in covered
