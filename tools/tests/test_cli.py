"""The command line itself: exit codes, writing, and refusing to write.

``generate`` is the command contributors run most and the one CI depends on to
notice drift, and none of it used to be exercised at all.
"""

import json

import pytest
from conftest import KLC_NAME, edit

from kbdlayout import build, source
from kbdlayout.cli import main
from kbdlayout.project import LAYOUT_SOURCE
from kbdlayout.report import ERROR, WARNING, Reporter

GENERATED_XKB = "dist/linux/symbols/us_intl_sci"


# ------------------------------------------------------------- generate ----


def test_generate_reports_every_file_as_unchanged(sandbox, capsys):
    assert main(["--root", str(sandbox), "generate"]) == 0
    out = capsys.readouterr().out
    assert out.count("unchanged") == 6
    assert KLC_NAME in out


def test_generate_check_fails_on_a_stale_file(sandbox, capsys):
    target = sandbox / GENERATED_XKB
    before = target.read_bytes()
    edit(target, "us_intl_sci", "tampered")

    assert main(["--root", str(sandbox), "generate", "--check"]) == 1
    err = capsys.readouterr().err
    assert "STALE" in err
    assert "out of date" in err
    # --check must not repair what it is reporting on.
    assert target.read_bytes() != before


def test_generate_rewrites_a_stale_file(sandbox):
    target = sandbox / GENERATED_XKB
    before = target.read_bytes()
    edit(target, "us_intl_sci", "tampered")

    assert main(["--root", str(sandbox), "generate"]) == 0
    assert target.read_bytes() == before


def test_generate_recreates_a_deleted_file(sandbox, capsys):
    target = sandbox / GENERATED_XKB
    target.unlink()

    assert main(["--root", str(sandbox), "generate"]) == 0
    assert "created" in capsys.readouterr().out
    assert target.exists()


def test_generate_check_leaves_a_deleted_file_deleted(sandbox):
    target = sandbox / GENERATED_XKB
    target.unlink()
    assert main(["--root", str(sandbox), "generate", "--check"]) == 1
    assert not target.exists()


def test_sync_reports_one_outcome_per_generated_file(sandbox):
    layout = source.load(sandbox / LAYOUT_SOURCE)
    outcomes = build.sync(sandbox, layout, write=False)
    assert {outcome.relative for outcome in outcomes} == set(build.render_all(layout))
    assert not any(outcome.is_stale for outcome in outcomes)


# ---------------------------------------------------------------- check ----


def test_check_passes_on_the_real_repository(repo_root):
    assert main(["--root", str(repo_root), "check", "--strict"]) == 0


def test_check_fails_and_names_the_defect(sandbox, capsys):
    edit(sandbox / "README.md", "U+2032", "U+2033")
    assert main(["--root", str(sandbox), "check"]) == 1
    assert "readme-keymap" in capsys.readouterr().out


def test_strict_turns_a_warning_into_a_failure(sandbox, capsys):
    # A second trailing newline is the repository's one warning-level finding.
    readme = sandbox / "README.md"
    readme.write_bytes(readme.read_bytes() + b"\n")

    assert main(["--root", str(sandbox), "check"]) == 0
    assert main(["--root", str(sandbox), "check", "--strict"]) == 1
    assert "warning" in capsys.readouterr().out


def test_check_reports_a_broken_layout_source_rather_than_raising(sandbox, capsys):
    (sandbox / LAYOUT_SOURCE).write_text("[layout]\n", encoding="utf-8")
    assert main(["--root", str(sandbox), "check"]) == 1
    assert capsys.readouterr().err


def test_json_output_is_parseable(sandbox, capsys):
    edit(sandbox / "README.md", "U+2032", "U+2033")
    assert main(["--root", str(sandbox), "check", "--format", "json"]) == 1
    findings = json.loads(capsys.readouterr().out)
    assert any(finding["check"] == "readme-keymap" for finding in findings)
    assert {"check", "path", "line", "severity", "message"} == set(findings[0])


def test_no_command_prints_help(capsys):
    assert main([]) == 2
    assert "usage" in capsys.readouterr().err


def test_an_unfindable_repository_is_reported(tmp_path, capsys):
    assert main(["--root", str(tmp_path), "check"]) == 1
    assert capsys.readouterr().err


# --------------------------------------------------------------- report ----


def test_a_misspelt_severity_is_rejected(tmp_path):
    reporter = Reporter(tmp_path)
    with pytest.raises(ValueError, match="unknown severity"):
        reporter.add("x", tmp_path / "f", 1, "m", severity="warn")


def test_errors_and_warnings_are_counted_separately(tmp_path):
    reporter = Reporter(tmp_path)
    reporter.add("a", tmp_path / "f", 1, "m", severity=ERROR)
    reporter.add("b", tmp_path / "f", 2, "m", severity=WARNING)
    assert len(reporter.errors) == 1
    assert len(reporter.warnings) == 1


def test_the_github_style_is_chosen_by_the_environment_at_call_time(monkeypatch):
    from kbdlayout import report

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert report.default_style() == "github"
    monkeypatch.delenv("GITHUB_ACTIONS")
    assert report.default_style() == "text"
