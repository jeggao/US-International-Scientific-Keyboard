"""Documentation back end: the tables in ``README.md``.

README.md used to restate the whole layout by hand -- 364 of its 641 lines were
table rows -- and a 638-line checker existed to notice when those tables and
the layout source disagreed. Every column of them except one is mechanical, so
they are generated here instead, and the drift they were checked for cannot
happen.

The one column that is not mechanical is the prose: *why* a character is on a
key, and the notes under a dead key. That is the most valuable text in the
project, and it was the only part of the layout's definition living outside the
source of truth. It now lives in ``layout/us-intl-scientific.toml`` beside the
mapping it justifies, as ``altgr_doc`` / ``altgr_shift_doc`` on a ``[[key]]``
and ``notes`` on a ``[[dead_key]]``.

``doc_bases`` is there for the same reason. A dead key's bases are documented
in an order and a grouping the author chose -- ``aeiouynv AEIOUYNV -=`` reads
better than the order the mapping happens to be written in, and the groups
carry meaning -- so the grouping is data, not something to re-derive. The
composites are then looked up from the mapping, which is what used to be
checked and is now simply true.

Everything else in README.md is hand-written and stays that way: this target
reads the committed file and rewrites only the regions between
``<!-- generated: ... -->`` and ``<!-- /generated -->``.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from ..model import DeadKey, Key, Layout, unicode_name
from ..project import README

#: The documentation draws itself from the layout and the prose in it.
CONFIG_TABLE: str | None = None
KEY_FIELDS: tuple[str, ...] = ("altgr_doc", "altgr_shift_doc")
DEAD_KEY_FIELDS: tuple[str, ...] = ("doc_bases", "notes")

#: The two shift states the Key Mappings tables document.
DOCUMENTED_LEVELS = ("altgr", "altgr_shift")

#: Which ``[[key]]`` field holds the prose for which level.
DOC_FIELD = {"altgr": "altgr_doc", "altgr_shift": "altgr_shift_doc"}

#: Keys the documentation gives no row of its own. LSGT is the extra key on ISO
#: keyboards, which repeats the backslash key; KPDL is the numeric keypad. The
#: space bar has a section of prose rather than a table row.
UNDOCUMENTED_KEYS = frozenset({"LSGT", "KPDL", "SPCE"})

#: The keyboard rows the Key Mappings section is divided into, and the key
#: positions each one covers, in the order the tables list them.
ROW_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("AE", ("TLDE", *(f"AE{i:02d}" for i in range(1, 13)))),
    ("AD", (*(f"AD{i:02d}" for i in range(1, 13)), "BKSL")),
    ("AC", tuple(f"AC{i:02d}" for i in range(1, 12))),
    ("AB", tuple(f"AB{i:02d}" for i in range(1, 11))),
)

#: U+25CC, which carries a combining mark that would otherwise attach itself to
#: the table's pipe character.
DOTTED_CIRCLE = "◌"

#: What a Markdown table cell needs escaped. A pipe would end the cell; a
#: backslash and a backtick would be read as an escape and a code span.
_MD_ESCAPE = {"|": "\\|", "`": "\\`", "\\": "\\\\"}

#: Prose is written as it should read, so only the table's own delimiter needs
#: escaping. A backslash in prose is literal -- descriptions contain things
#: like ``\cdot`` -- and backticks open code spans that must survive.
_PROSE_ESCAPE = {"|": "\\|"}

#: How wide the Char column is padded, matching the committed tables.
CHAR_WIDTH = 4

HEADER = "|Key|Char|Unicode|Character&nbsp;name|Description|"
SEPARATOR = "|:-:|:--:|:-----:|--------------|-----------|"
DEAD_SEPARATOR = "|:------:|---|"

BEGIN = "<!-- generated: {name} -->"
END = "<!-- /generated -->"
BLOCK_RE = re.compile(
    r"<!-- generated: (?P<name>[^>]+?) -->\n.*?\n<!-- /generated -->",
    re.DOTALL,
)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def _escape(text: str) -> str:
    """Escape a character this generator is placing into a cell."""
    return "".join(_MD_ESCAPE.get(char, char) for char in text)


def _escape_prose(text: str) -> str:
    """Escape hand-written prose, which is already Markdown."""
    return "".join(_PROSE_ESCAPE.get(char, char) for char in text)


def _code_span(text: str) -> str:
    """Wrap ``text`` in a code span, widening the fence if it holds a backtick."""
    if "`" in text:
        return f"`` {text} ``"
    return f"`{text}`"


def _shown(char: str) -> str:
    """A renderable stand-in: a lone combining mark rides on a dotted circle."""
    if unicodedata.category(char) in ("Mn", "Me", "Mc"):
        return DOTTED_CIRCLE + char
    return char


def _char_cell(layout: Layout, code_point: int, dead: bool) -> str:
    """What the Char column shows: a *renderable* stand-in for the character.

    For an ordinary key that is the character itself, and for a dead key it is
    the root -- which is what the key stands for. The exception is a root that
    is a combining mark, which would attach itself to the pipe beside it; there
    the dead key's default is shown instead, and it is the spacing form of the
    same diacritic.
    """
    if dead and unicodedata.category(chr(code_point)) in ("Mn", "Me", "Mc"):
        dead_key = layout.dead_key(code_point)
        if dead_key is not None and dead_key.default is not None:
            code_point = dead_key.default
    return _shown(chr(code_point)).ljust(CHAR_WIDTH)


def _key_label(key: Key, level: str) -> str:
    """The character the reader presses: unmodified for AltGr, Shift for the rest."""
    output = key.outputs.get("normal" if level == "altgr" else "shift")
    return "" if output is None else output.char


def key_table(layout: Layout, positions: tuple[str, ...], level: str) -> list[str]:
    """One Key Mappings table."""
    lines = [HEADER, SEPARATOR]
    for key_id in positions:
        key = layout.key(key_id)
        if key is None or key.id in UNDOCUMENTED_KEYS:
            continue
        output = key.outputs.get(level)
        if output is None:
            continue
        label = _escape(_key_label(key, level))
        char = _char_cell(layout, output.code_point, output.dead)
        description = key.extra.get(DOC_FIELD[level], "")
        lines.append(
            f"|<kbd>{label}</kbd>|{char}|U+{output.code_point:04X}|"
            f"{unicode_name(output.code_point)}|{_escape_prose(description)} |"
        )
    return lines


def _named(code_point: int) -> str:
    """``U+XXXX NAME (char)``, as the Root and Default rows are written."""
    return f"U+{code_point:04X} {unicode_name(code_point)} ({_shown(chr(code_point))})"


def _trigger(layout: Layout, dead_key: DeadKey) -> str:
    """The key combination that starts this dead key."""
    for key in layout.keys:
        for level in DOCUMENTED_LEVELS:
            output = key.outputs.get(level)
            if output is None or not output.dead or output.code_point != dead_key.root:
                continue
            return f"<kbd>AltGr</kbd> + <kbd>{_escape(_key_label(key, level))}</kbd>"
    return ""


def dead_key_table(layout: Layout, dead_key: DeadKey) -> list[str]:
    """One dead key's table.

    ``doc_bases`` is a list of *lines*: spaces inside a line separate groups,
    and the lines themselves are laid out one above another with ``<br>``. Most
    dead keys are one line; the three with a lot of bases -- superscripts,
    strokes and the Greek alphabet -- read far better broken up.
    """
    doc_lines: list[str] = list(dead_key.extra.get("doc_bases", []))
    mapping = dead_key.mapping
    composite_lines = [
        "".join(" " if char == " " else _shown(chr(mapping[ord(char)])) for char in doc_line)
        for doc_line in doc_lines
    ]
    bases_cell = "<br>".join(_code_span(_escape_prose(line)) for line in doc_lines)
    composites_cell = "<br>".join(_escape_prose(line) for line in composite_lines)
    lines = [
        f"|Category|{dead_key.category}|",
        DEAD_SEPARATOR,
        f"|Dead key|{_trigger(layout, dead_key)}|",
        f"|Root|{_named(dead_key.root)}|",
        f"|Bases|{bases_cell}|",
        f"|Composites|{composites_cell}|",
    ]
    default = dead_key.default
    lines.append(f"|Default|{_named(default) if default is not None else ''}|")
    notes = dead_key.extra.get("notes", "")
    if notes:
        lines.append(f"|Notes|{_escape_prose(notes)} |")
    return lines


def blocks(layout: Layout) -> dict[str, list[str]]:
    """Every generated region, keyed by the name in its marker comment."""
    out: dict[str, list[str]] = {}
    for prefix, positions in ROW_GROUPS:
        for level in DOCUMENTED_LEVELS:
            out[f"keys {prefix} {level}"] = key_table(layout, positions, level)
    for dead_key in layout.dead_keys:
        out[f"dead U+{dead_key.root:04X}"] = dead_key_table(layout, dead_key)
    return out


def render(layout: Layout, readme: str) -> str:
    """Rewrite every generated region of ``readme`` from the layout."""
    available = blocks(layout)
    seen: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        seen.add(name)
        try:
            body = available[name]
        except KeyError:
            raise ValueError(
                f"README.md has a generated block named {name!r}, which the layout does not produce"
            ) from None
        return "\n".join([BEGIN.format(name=name), *body, END])

    rewritten = BLOCK_RE.sub(replace, readme)
    missing = sorted(set(available) - seen)
    if missing:
        raise ValueError(
            "README.md has no generated block for: "
            + ", ".join(missing)
            + f". Add `{BEGIN.format(name=missing[0])}` ... `{END}` where it belongs."
        )
    return rewritten


# --------------------------------------------------------------------------
# Target protocol
# --------------------------------------------------------------------------


def parse_config(table: dict) -> None:  # pragma: no cover - never called
    raise ValueError("the docs target takes no configuration")


def constraints(layout: Layout) -> list[str]:
    """Everything the documentation needs in order to be generated at all.

    These are the checks ``checks_readme`` used to make against the prose. They
    are cheaper here: instead of parsing the README to find out whether it
    agrees, the layout is asked whether it can produce a README at all.
    """
    problems: list[str] = []
    for key in layout.keys:
        if key.id in UNDOCUMENTED_KEYS:
            continue
        for level in DOCUMENTED_LEVELS:
            output = key.outputs.get(level)
            field = DOC_FIELD[level]
            if output is None:
                if key.extra.get(field):
                    problems.append(f"key {key.id} has {field} but produces nothing with {level}")
                continue
            description = key.extra.get(field)
            if not description:
                problems.append(
                    f"key {key.id} produces U+{output.code_point:04X} with {level} but "
                    f"has no {field} saying why"
                )
                continue
            marked = "**Dead key" in description
            if output.dead and not marked:
                problems.append(
                    f"key {key.id} {level} is a dead key but its {field} has no "
                    "'**Dead key:**' note"
                )
            if marked and not output.dead:
                problems.append(f"key {key.id} {level} is described as a dead key but is not one")
        for field in KEY_FIELDS:
            if field in key.extra and not isinstance(key.extra[field], str):
                problems.append(f"key {key.id}: {field} must be a string")

    for dead_key in layout.dead_keys:
        groups = dead_key.extra.get("doc_bases")
        if not groups:
            problems.append(
                f"dead key U+{dead_key.root:04X} has no doc_bases, so its table has nothing to list"
            )
            continue
        if not isinstance(groups, list) or not all(isinstance(g, str) for g in groups):
            problems.append(f"dead key U+{dead_key.root:04X}: doc_bases must be a list of strings")
            continue
        documented = [char for line in groups for char in line if char != " "]
        if len(documented) != len(set(documented)):
            problems.append(f"dead key U+{dead_key.root:04X} documents a base twice in doc_bases")
        mapped = {base for base, _ in dead_key.entries if base != 0x20}
        listed = {ord(char) for char in documented}
        for extra in sorted(listed - mapped):
            problems.append(
                f"dead key U+{dead_key.root:04X}: doc_bases lists {chr(extra)!r} "
                f"(U+{extra:04X}), which it does not compose"
            )
        for missing in sorted(mapped - listed):
            problems.append(
                f"dead key U+{dead_key.root:04X} composes {chr(missing)!r} "
                f"(U+{missing:04X}) but doc_bases does not list it"
            )
        if not _trigger(layout, dead_key):
            problems.append(
                f"dead key U+{dead_key.root:04X} is not reachable from any documented "
                "AltGr level, so its table has no key combination to show"
            )
    return problems


def generate(layout: Layout, root: Path) -> dict[str, str | bytes]:
    readme = root / README
    if not readme.exists():
        return {}
    return {README: render(layout, readme.read_text(encoding="utf-8"))}


__all__ = [
    "CONFIG_TABLE",
    "DEAD_KEY_FIELDS",
    "KEY_FIELDS",
    "blocks",
    "constraints",
    "dead_key_table",
    "generate",
    "key_table",
    "parse_config",
    "render",
]
