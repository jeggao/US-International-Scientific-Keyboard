"""Checks for the hand-written parts of ``README.md``.

The key-mapping and dead-key tables used to be written by hand and checked
against the layout by roughly five hundred lines of table parsing. They are
generated now (:mod:`kbdlayout.generators.docs`), so
:mod:`kbdlayout.checks.generated` catches any drift in them and none of that
parsing is needed.

What is left here applies to the prose around those tables, which is still
written by hand and which nothing generates: invisible characters that got in
by accident, links to headings that do not exist, links to files that do not
exist, malformed tables, and the one sentence that counts the dead keys.
"""

from __future__ import annotations

import re
from pathlib import Path

from .. import markdown as md
from ..model import Layout
from ..project import README
from ..report import Reporter

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

#: Characters that must never appear in the source: they are invisible and only
#: ever get in by accident when copying text around.
STRAY_CHARACTERS = {
    0x200B: "ZERO WIDTH SPACE",
    0x200D: "ZERO WIDTH JOINER",
    0x00A0: "NO-BREAK SPACE",
    0xFEFF: "ZERO WIDTH NO-BREAK SPACE",
}


def check(root: Path, layout: Layout, reporter: Reporter) -> None:
    path = root / README
    if not path.exists():
        reporter.add("readme-missing", path, 0, f"{README} is missing")
        return
    lines = path.read_text(encoding="utf-8").split("\n")
    _check_stray_characters(path, lines, reporter)
    _check_table_shape(path, md.find_tables(lines), reporter)
    _check_anchors(path, lines, reporter)
    _check_relative_links(path, lines, reporter)
    _check_dead_key_count_prose(path, lines, layout, reporter)


def _check_stray_characters(path: Path, lines: list[str], reporter: Reporter) -> None:
    for index, line in enumerate(lines):
        for char in line:
            if ord(char) not in STRAY_CHARACTERS:
                continue
            # A line that spells out the code point is documenting the character
            # rather than accidentally containing it.
            if f"U+{ord(char):04X}" in line:
                continue
            reporter.add(
                "readme-stray-character",
                path,
                index + 1,
                f"stray invisible U+{ord(char):04X} {STRAY_CHARACTERS[ord(char)]}",
            )


def _check_table_shape(path: Path, tables: list[md.Table], reporter: Reporter) -> None:
    for table in tables:
        if len(table.rows) < 2:
            continue
        widths = {len(row.cells) for row in table.rows}
        if len(widths) > 1:
            expected = len(table.rows[0].cells)
            for row in table.rows:
                if len(row.cells) != expected:
                    reporter.add(
                        "readme-table-shape",
                        path,
                        row.line_no,
                        (
                            f"row has {len(row.cells)} cells but the table header has "
                            f"{expected}; a missing trailing '|' is the usual cause"
                        ),
                    )
        for row in table.rows:
            stripped = row.raw.rstrip()
            if not stripped.endswith("|"):
                reporter.add(
                    "readme-table-shape",
                    path,
                    row.line_no,
                    "table row does not end with '|'",
                )
            if row.raw != stripped:
                reporter.add(
                    "readme-table-shape",
                    path,
                    row.line_no,
                    "table row has trailing whitespace",
                    severity="warning",
                )
        if not md.is_separator_row(table.rows[1].cells):
            reporter.add(
                "readme-table-shape",
                path,
                table.rows[1].line_no,
                "table header is not followed by a delimiter row",
                severity="warning",
            )


def _check_anchors(path: Path, lines: list[str], reporter: Reporter) -> None:
    anchors = {anchor for _line, _text, anchor in md.headings(lines)}
    for index, line in enumerate(lines):
        for target in LINK_RE.findall(line):
            if not target.startswith("#"):
                continue
            if target[1:] not in anchors:
                reporter.add(
                    "readme-anchor",
                    path,
                    index + 1,
                    f"link target {target} does not match any heading",
                )


def _check_relative_links(path: Path, lines: list[str], reporter: Reporter) -> None:
    root = path.parent
    for index, line in enumerate(lines):
        for target in dict.fromkeys(LINK_RE.findall(line)):
            if target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            relative = target.lstrip("/").split("#")[0]
            if not (root / relative).exists():
                reporter.add(
                    "readme-link",
                    path,
                    index + 1,
                    f"relative link {target!r} does not resolve to a file in the repository",
                )
            elif target.startswith("/"):
                reporter.add(
                    "readme-link",
                    path,
                    index + 1,
                    (
                        f"relative link {target!r} starts with '/', which only resolves on "
                        f"github.com; use {relative!r}"
                    ),
                    severity="warning",
                )


def _check_dead_key_count_prose(
    path: Path, lines: list[str], layout: Layout, reporter: Reporter
) -> None:
    """The one number the prose repeats that the layout also knows."""
    pattern = re.compile(r"the (\d+) dead keys")
    for index, line in enumerate(lines):
        match = pattern.search(line)
        if match and int(match.group(1)) != len(layout.dead_keys):
            reporter.add(
                "readme-deadkey",
                path,
                index + 1,
                (
                    f"prose says {match.group(1)} dead keys but the layout defines "
                    f"{len(layout.dead_keys)}"
                ),
            )
