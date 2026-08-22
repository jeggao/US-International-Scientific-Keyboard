"""Cross-checks between ``README.md`` and the ``.klc`` source of truth."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from . import markdown as md
from .klc import Klc, unicode_name
from .report import Reporter

KBD_RE = re.compile(r"<kbd>(.*?)</kbd>")
CODE_POINT_RE = re.compile(r"U\+([0-9A-F]{4,6})\b")
UNICODE_CELL_RE = re.compile(r"^U\+([0-9A-F]{4,6})$")
ROOT_CELL_RE = re.compile(r"^U\+([0-9A-F]{4,6})\s+(.+?)\s*\((.+)\)$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

#: Characters that must never appear in the source: they are invisible and only
#: ever get in by accident when copying text around.
STRAY_CHARACTERS = {
    0x200B: "ZERO WIDTH SPACE",
    0x200D: "ZERO WIDTH JOINER",
    0x00A0: "NO-BREAK SPACE",
    0xFEFF: "ZERO WIDTH NO-BREAK SPACE",
}

#: Escape sequences a Markdown table cell may legitimately contain.
_MD_UNESCAPE = {"\\|": "|", "\\\\": "\\", "\\`": "`", "\\<": "<", "\\>": ">", "\\_": "_"}


def check(readme_path: Path, klc: Klc, reporter: Reporter) -> None:
    lines = readme_path.read_text(encoding="utf-8").split("\n")
    tables = md.find_tables(lines)
    _check_stray_characters(readme_path, lines, reporter)
    _check_table_shape(readme_path, tables, reporter)
    _check_anchors(readme_path, lines, reporter)
    _check_relative_links(readme_path, lines, reporter)
    _check_key_tables(readme_path, lines, tables, klc, reporter)
    _check_dead_key_tables(readme_path, lines, tables, klc, reporter)


def _unescape(text: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(text):
        pair = text[index : index + 2]
        if pair in _MD_UNESCAPE:
            out.append(_MD_UNESCAPE[pair])
            index += 2
            continue
        out.append(text[index])
        index += 1
    return "".join(out)


def _key_label(cell: str) -> str | None:
    match = KBD_RE.search(cell)
    if match is None:
        return None
    return _unescape(match.group(1))


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


def _heading_above(lines: list[str], line_no: int, prefix: str) -> str:
    for index in range(line_no - 1, 0, -1):
        if lines[index - 1].startswith(prefix):
            return lines[index - 1][len(prefix) :].strip()
    return ""


def _printable_key_index(klc: Klc) -> tuple[dict[str, object], dict[str, object]]:
    normal: dict[str, object] = {}
    shifted: dict[str, object] = {}
    for row in klc.layout:
        # OEM_102 duplicates OEM_5 for ISO keyboards and has no separate keycap
        # in the documentation.
        if row.virtual_key == "OEM_102":
            continue
        base = row.outputs.get(0)
        shift = row.outputs.get(1)
        if base is not None and base.code_point is not None:
            normal.setdefault(chr(base.code_point), row)
        if shift is not None and shift.code_point is not None:
            shifted.setdefault(chr(shift.code_point), row)
    return normal, shifted


def _check_key_tables(
    path: Path, lines: list[str], tables: list[md.Table], klc: Klc, reporter: Reporter
) -> None:
    normal, shifted = _printable_key_index(klc)
    documented: set[tuple[int, str]] = set()

    for table in tables:
        if not table.rows[0].cells or table.rows[0].cells[0].strip() != "Key":
            continue
        heading = _heading_above(lines, table.start_line, "#### ")
        state = 7 if "Shift" in heading else 6
        for row in table.rows[2:]:
            if len(row.cells) != 5:
                continue
            key_cell, char_cell, unicode_cell, name_cell, description = (
                cell.strip() for cell in row.cells
            )
            label = _key_label(key_cell)
            if label is None:
                reporter.add(
                    "readme-keymap", path, row.line_no, f"cannot read key cell {key_cell!r}"
                )
                continue
            documented.add((state, label))
            layout_row = (
                (shifted if state == 7 else normal).get(label)
                or normal.get(label)
                or shifted.get(label)
            )
            if layout_row is None:
                reporter.add(
                    "readme-keymap",
                    path,
                    row.line_no,
                    f"key {label!r} does not exist in the layout",
                )
                continue
            match = UNICODE_CELL_RE.match(unicode_cell)
            if match is None:
                reporter.add(
                    "readme-keymap",
                    path,
                    row.line_no,
                    f"cannot read code point cell {unicode_cell!r}",
                )
                continue
            code_point = int(match.group(1), 16)
            output = layout_row.outputs.get(state)
            actual = output.code_point if output is not None else None
            if actual is None:
                reporter.add(
                    "readme-keymap",
                    path,
                    row.line_no,
                    f"key {label!r} has no character in shift state {state}",
                )
                continue
            if actual != code_point:
                reporter.add(
                    "readme-keymap",
                    path,
                    row.line_no,
                    (
                        f"key {label!r} is documented as U+{code_point:04X} "
                        f"({unicode_name(code_point)}) but the layout produces "
                        f"U+{actual:04X} ({unicode_name(actual)})"
                    ),
                )
            expected_name = unicode_name(code_point)
            if name_cell.replace("&nbsp;", " ") != expected_name:
                reporter.add(
                    "readme-keymap",
                    path,
                    row.line_no,
                    (
                        f"key {label!r}: character name {name_cell!r} is not the Unicode "
                        f"name of U+{code_point:04X} ({expected_name!r})"
                    ),
                )
            _check_char_cell(path, row.line_no, label, char_cell, actual, klc, reporter)
            is_dead = output is not None and output.is_dead
            has_marker = "**Dead key" in description
            if is_dead and not has_marker:
                reporter.add(
                    "readme-keymap",
                    path,
                    row.line_no,
                    f"key {label!r} is a dead key but its description has no '**Dead key:**' note",
                )
            if has_marker and not is_dead:
                reporter.add(
                    "readme-keymap",
                    path,
                    row.line_no,
                    f"key {label!r} is documented as a dead key but the layout says otherwise",
                )

    _check_key_coverage(path, klc, documented, reporter)


def _check_char_cell(
    path: Path,
    line_no: int,
    label: str,
    char_cell: str,
    code_point: int,
    klc: Klc,
    reporter: Reporter,
) -> None:
    """The Char column shows a *renderable* stand-in for the character.

    For an ordinary key that is the character itself. For a dead key whose root is
    a combining mark it is the dead key's default character, which is the spacing
    form of the same diacritic. A bare combining mark is never acceptable: it
    attaches itself to the table's pipe character when rendered.
    """
    raw = char_cell.strip()
    shown = md.normalise_cluster(raw)
    if not shown:
        reporter.add("readme-keymap", path, line_no, f"key {label!r} has an empty Char cell")
        return
    if raw == shown and len(shown) == 1 and unicodedata.category(shown) in ("Mn", "Me"):
        reporter.add(
            "readme-keymap",
            path,
            line_no,
            (
                f"key {label!r}: Char cell is the bare combining mark U+{ord(shown):04X}, which "
                "renders on top of the table's pipe character; use the spacing form or prefix "
                "it with '◌'"
            ),
        )
        return
    allowed = {chr(code_point)}
    dead_key = klc.dead_key(code_point)
    if dead_key is not None and dead_key.default is not None:
        allowed.add(chr(dead_key.default))
    if shown in allowed:
        return
    reporter.add(
        "readme-keymap",
        path,
        line_no,
        (
            f"key {label!r}: Char cell shows {shown!r} but should show one of "
            f"{sorted(allowed)!r} (use '◌' before a lone combining mark)"
        ),
    )


def _check_key_coverage(
    path: Path, klc: Klc, documented: set[tuple[int, str]], reporter: Reporter
) -> None:
    for row in klc.layout:
        if row.virtual_key in ("OEM_102", "SPACE", "DECIMAL"):
            continue
        for state in (6, 7):
            output = row.outputs.get(state)
            if output is None or output.code_point is None:
                continue
            base = row.outputs.get(0 if state == 6 else 1)
            if base is None or base.code_point is None:
                continue
            label = chr(base.code_point)
            if (state, label) not in documented:
                reporter.add(
                    "readme-keymap",
                    path,
                    1,
                    (
                        f"key {label!r} in shift state {state} produces U+{output.code_point:04X} "
                        f"({unicode_name(output.code_point)}) but is not documented"
                    ),
                )


def _check_dead_key_tables(
    path: Path, lines: list[str], tables: list[md.Table], klc: Klc, reporter: Reporter
) -> None:
    dead_key_tables = [
        table
        for table in tables
        if table.rows[0].cells and table.rows[0].cells[0].strip() == "Category"
    ]
    if len(dead_key_tables) != len(klc.dead_keys):
        reporter.add(
            "readme-deadkey",
            path,
            dead_key_tables[0].start_line if dead_key_tables else 1,
            (
                f"README documents {len(dead_key_tables)} dead keys but the layout defines "
                f"{len(klc.dead_keys)}"
            ),
        )
    _check_dead_key_count_prose(path, lines, klc, reporter)

    seen_roots: set[int] = set()
    for table in dead_key_tables:
        category = table.rows[0].cells[1].strip() if len(table.rows[0].cells) > 1 else "?"
        root_row = table.cell("Root")
        if root_row is None or len(root_row.cells) < 2:
            reporter.add(
                "readme-deadkey", path, table.start_line, f"[{category}] table has no Root row"
            )
            continue
        match = ROOT_CELL_RE.match(root_row.cells[1].strip())
        if match is None:
            reporter.add(
                "readme-deadkey",
                path,
                root_row.line_no,
                f"[{category}] cannot read Root cell {root_row.cells[1]!r}",
            )
            continue
        root = int(match.group(1), 16)
        seen_roots.add(root)
        _check_named_cell(path, root_row.line_no, category, "Root", match, reporter)
        dead_key = klc.dead_key(root)
        if dead_key is None:
            reporter.add(
                "readme-deadkey",
                path,
                root_row.line_no,
                f"[{category}] U+{root:04X} is not a dead key in the layout",
            )
            continue
        _check_dead_key_trigger(path, table, category, root, klc, reporter)
        _check_dead_key_mappings(path, table, category, dead_key, klc, reporter)

    for dead_key in klc.dead_keys:
        if dead_key.root not in seen_roots:
            reporter.add(
                "readme-deadkey",
                path,
                1,
                f"dead key U+{dead_key.root:04X} ({unicode_name(dead_key.root)}) is not documented",
            )


def _check_dead_key_count_prose(path: Path, lines: list[str], klc: Klc, reporter: Reporter) -> None:
    pattern = re.compile(r"the (\d+) dead keys")
    for index, line in enumerate(lines):
        match = pattern.search(line)
        if match and int(match.group(1)) != len(klc.dead_keys):
            reporter.add(
                "readme-deadkey",
                path,
                index + 1,
                (
                    f"prose says {match.group(1)} dead keys but the layout defines "
                    f"{len(klc.dead_keys)}"
                ),
            )


def _check_named_cell(
    path: Path,
    line_no: int,
    category: str,
    label: str,
    match: re.Match[str],
    reporter: Reporter,
) -> None:
    code_point = int(match.group(1), 16)
    name = match.group(2).strip()
    shown = md.normalise_cluster(match.group(3).strip())
    expected = unicode_name(code_point)
    if name != expected:
        reporter.add(
            "readme-deadkey",
            path,
            line_no,
            f"[{category}] {label} name {name!r} is not the Unicode name of "
            f"U+{code_point:04X} ({expected!r})",
        )
    if shown != chr(code_point):
        reporter.add(
            "readme-deadkey",
            path,
            line_no,
            f"[{category}] {label} shows {shown!r} but U+{code_point:04X} is {chr(code_point)!r}",
        )


def _check_dead_key_trigger(
    path: Path, table: md.Table, category: str, root: int, klc: Klc, reporter: Reporter
) -> None:
    trigger_row = table.cell("Dead key")
    if trigger_row is None or len(trigger_row.cells) < 2:
        reporter.add(
            "readme-deadkey", path, table.start_line, f"[{category}] table has no 'Dead key' row"
        )
        return
    labels = [_unescape(part) for part in KBD_RE.findall(trigger_row.cells[1])]
    if len(labels) != 2 or labels[0] != "AltGr":
        reporter.add(
            "readme-deadkey",
            path,
            trigger_row.line_no,
            f"[{category}] cannot read key combination {trigger_row.cells[1]!r}",
        )
        return
    wanted = labels[1]
    for row in klc.layout:
        for state in (6, 7):
            output = row.outputs.get(state)
            if output is None or output.code_point != root or not output.is_dead:
                continue
            base = row.outputs.get(0 if state == 6 else 1)
            if base is None or base.code_point is None:
                continue
            if chr(base.code_point) == wanted:
                return
    reporter.add(
        "readme-deadkey",
        path,
        trigger_row.line_no,
        (
            f"[{category}] documented as AltGr + {wanted!r}, but U+{root:04X} is not the dead key "
            "on that key in the layout"
        ),
    )


def _check_dead_key_mappings(
    path: Path, table: md.Table, category: str, dead_key, klc: Klc, reporter: Reporter
) -> None:
    bases_row = table.cell("Bases")
    composites_row = table.cell("Composites")
    default_row = table.cell("Default")
    if bases_row is None or composites_row is None:
        reporter.add(
            "readme-deadkey",
            path,
            table.start_line,
            f"[{category}] table is missing a Bases or Composites row",
        )
        return

    bases_text = " ".join(md.code_span_contents(bases_row.cells[1])) or bases_row.cells[1]
    base_groups = md.character_groups(bases_text)
    composite_groups = md.character_groups(composites_row.cells[1])
    base_shape = [len(group) for group in base_groups]
    composite_shape = [len(group) for group in composite_groups]
    if base_shape != composite_shape:
        reporter.add(
            "readme-deadkey",
            path,
            composites_row.line_no,
            (
                f"[{category}] Bases and Composites do not line up: groups of "
                f"{base_shape} versus {composite_shape}"
            ),
        )

    mapping = dead_key.mapping
    flat_bases = [char for group in base_groups for char in group]
    flat_composites = [char for group in composite_groups for char in group]
    documented: set[int] = set()
    # Any length difference is already reported as a group-shape mismatch above.
    for base, composite in zip(flat_bases, flat_composites, strict=False):
        if len(base) != 1:
            reporter.add(
                "readme-deadkey",
                path,
                bases_row.line_no,
                f"[{category}] base {base!r} is not a single character",
            )
            continue
        documented.add(ord(base))
        expected = mapping.get(ord(base))
        if expected is None:
            reporter.add(
                "readme-deadkey",
                path,
                bases_row.line_no,
                f"[{category}] base {base!r} (U+{ord(base):04X}) is documented but not "
                "in the layout",
            )
        elif chr(expected) != composite:
            reporter.add(
                "readme-deadkey",
                path,
                composites_row.line_no,
                (
                    f"[{category}] base {base!r} is documented as producing {composite!r} but the "
                    f"layout produces {chr(expected)!r} (U+{expected:04X})"
                ),
            )
    for base in mapping:
        if base == 0x20 or base in documented:
            continue
        reporter.add(
            "readme-deadkey",
            path,
            bases_row.line_no,
            (
                f"[{category}] the layout maps base {chr(base)!r} (U+{base:04X}) to "
                f"{chr(mapping[base])!r} but it is not documented"
            ),
        )

    if default_row is None or len(default_row.cells) < 2:
        reporter.add(
            "readme-deadkey", path, table.start_line, f"[{category}] table has no Default row"
        )
        return
    match = ROOT_CELL_RE.match(default_row.cells[1].strip())
    if match is None:
        reporter.add(
            "readme-deadkey",
            path,
            default_row.line_no,
            f"[{category}] cannot read Default cell {default_row.cells[1]!r}",
        )
        return
    _check_named_cell(path, default_row.line_no, category, "Default", match, reporter)
    documented_default = int(match.group(1), 16)
    if dead_key.default is None:
        reporter.add(
            "readme-deadkey",
            path,
            default_row.line_no,
            f"[{category}] the layout gives this dead key no default character",
        )
    elif dead_key.default != documented_default:
        reporter.add(
            "readme-deadkey",
            path,
            default_row.line_no,
            (
                f"[{category}] default is documented as U+{documented_default:04X} but the layout "
                f"maps space to U+{dead_key.default:04X} ({unicode_name(dead_key.default)})"
            ),
        )
