"""Small helpers for reading the hand-written Markdown tables in ``README.md``.

Only the subset of GitHub Flavoured Markdown that the README actually uses is
supported: pipe tables, ``\\|`` escapes, code spans and ``<br>``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

#: U+25CC, conventionally used to display a combining mark on its own.
DOTTED_CIRCLE = "◌"

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


@dataclass
class TableRow:
    line_no: int
    raw: str
    cells: list[str]


@dataclass
class Table:
    start_line: int
    rows: list[TableRow]

    @property
    def header(self) -> TableRow:
        return self.rows[0]

    def cell(self, label: str) -> TableRow | None:
        for row in self.rows:
            if row.cells and row.cells[0].strip().lower() == label.lower():
                return row
        return None


def split_cells(line: str) -> list[str]:
    """Split one Markdown table row into cells, honouring ``\\|`` escapes."""
    cells: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(line):
        char = line[index]
        if char == "\\" and index + 1 < len(line) and line[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if char == "|":
            cells.append("".join(current))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    cells.append("".join(current))
    # A row written as ``|a|b|`` yields empty leading and trailing cells.
    if cells and not cells[0].strip():
        cells = cells[1:]
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    return cells


def is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{1,}:?", cell.strip()) for cell in cells)


def find_tables(lines: list[str]) -> list[Table]:
    """Return every pipe table in ``lines`` (1-based line numbers)."""
    tables: list[Table] = []
    current: list[TableRow] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|"):
            current.append(TableRow(index + 1, line, split_cells(stripped)))
            continue
        if current:
            tables.append(Table(current[0].line_no, current))
            current = []
    if current:
        tables.append(Table(current[0].line_no, current))
    return tables


def code_span_contents(text: str) -> list[str]:
    """Return the contents of every code span in ``text``, in order."""
    spans: list[str] = []
    index = 0
    while index < len(text):
        if text[index] != "`":
            index += 1
            continue
        run = 0
        while index + run < len(text) and text[index + run] == "`":
            run += 1
        closer = _find_closing_run(text, index + run, run)
        if closer is None:
            index += run
            continue
        content = text[index + run : closer]
        if len(content) > 2 and content[0] == " " and content[-1] == " " and content.strip():
            content = content[1:-1]
        spans.append(content)
        index = closer + run
    return spans


def _find_closing_run(text: str, start: int, run: int) -> int | None:
    index = start
    while index < len(text):
        if text[index] != "`":
            index += 1
            continue
        length = 0
        while index + length < len(text) and text[index + length] == "`":
            length += 1
        if length == run:
            return index
        index += length
    return None


def clusters(text: str) -> list[str]:
    """Split ``text`` into base-plus-combining-mark clusters."""
    out: list[str] = []
    for char in text:
        if unicodedata.category(char) in ("Mn", "Me", "Mc") and out:
            out[-1] += char
        else:
            out.append(char)
    return out


def normalise_cluster(cluster: str) -> str:
    """Strip the display carrier from a lone combining mark."""
    if len(cluster) > 1 and cluster[0] in (DOTTED_CIRCLE, " ", " "):
        return cluster[1:]
    return cluster


def character_groups(text: str) -> list[list[str]]:
    """Split ``text`` into space-separated groups of normalised clusters."""
    groups: list[list[str]] = []
    current: list[str] = []
    for cluster in clusters(text.replace("<br>", " ")):
        if cluster == " ":
            if current:
                groups.append(current)
                current = []
            continue
        current.append(normalise_cluster(cluster))
    if current:
        groups.append(current)
    return groups


def anchor(heading: str) -> str:
    """Reproduce GitHub's heading-to-anchor transformation."""
    text = heading.strip().lower()
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def headings(lines: list[str]) -> list[tuple[int, str, str]]:
    """Return ``(line_no, text, anchor)`` for every ATX heading."""
    out: list[tuple[int, str, str]] = []
    in_fence = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if match:
            out.append((index + 1, match.group(2), anchor(match.group(2))))
    return out
