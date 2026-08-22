from kbdlint import markdown as md


def test_split_cells_unescapes_pipes():
    assert md.split_cells(r"|Bases|`a\|b`|") == ["Bases", "`a|b`"]


def test_split_cells_keeps_backslashes():
    assert md.split_cells(r"|Bases|`a\\|b`|") == ["Bases", r"`a\|b`"]


def test_code_span_contents_handles_double_backticks():
    text = "``a `b` c``"
    assert md.code_span_contents(text) == ["a `b` c"]


def test_code_span_contents_returns_each_span():
    assert md.code_span_contents("`one`<br>`two`") == ["one", "two"]


def test_clusters_attach_combining_marks():
    assert md.clusters("áb") == ["á", "b"]


def test_normalise_cluster_strips_dotted_circle():
    assert md.normalise_cluster("◌́") == "́"
    assert md.normalise_cluster("◌") == "◌"


def test_character_groups_splits_on_spaces_and_br():
    groups = md.character_groups("ab cd<br>e")
    assert groups == [["a", "b"], ["c", "d"], ["e"]]


def test_character_groups_keeps_carried_combining_marks_together():
    # A combining mark shown on a dotted circle is one entry, not two.
    assert md.character_groups("◌̇◌̈") == [["̇", "̈"]]


def test_anchor_matches_github_rules():
    assert md.anchor("Update / Uninstallation Guide") == "update--uninstallation-guide"
    assert md.anchor("Notes on MSKLC 1.4") == "notes-on-msklc-14"


def test_headings_skips_fenced_code():
    lines = ["# Title", "```", "# not a heading", "```", "## Second"]
    assert [text for _line, text, _anchor in md.headings(lines)] == ["Title", "Second"]
