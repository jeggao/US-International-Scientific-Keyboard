"""Parser for Microsoft Keyboard Layout Creator (MSKLC) ``.klc`` source files.

The ``.klc`` is generated from ``layout/us-intl-scientific.toml`` rather than
edited, so nothing depends on this parser to build the layout. It exists to read
the file back: the test suite parses the shipped ``.klc`` and compares it to the
layout source, which checks the Windows generator by a route that does not go
through the generator itself. It is also what an import of somebody else's
``.klc`` would start from.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

#: Byte order mark that MSKLC writes at the start of every ``.klc`` file.
BOM = "﻿"

#: Shift state numbers used by MSKLC, in the column order used by the LAYOUT table.
#: 0 = none, 1 = Shift, 2 = Ctrl, 6 = Ctrl+Alt (AltGr), 7 = Ctrl+Alt+Shift.
SHIFT_STATE_NAMES = {
    0: "normal",
    1: "shift",
    2: "ctrl",
    6: "altgr",
    7: "altgr+shift",
}

#: Sections that appear at most once, in this order, in a well formed file.
SECTION_ORDER = [
    "SHIFTSTATE",
    "LAYOUT",
    "DEADKEY",
    "KEYNAME",
    "KEYNAME_EXT",
    "KEYNAME_DEAD",
    "DESCRIPTIONS",
    "LANGUAGENAMES",
    "ENDKBD",
]

#: Single-token header directives at the top of the file.
HEADER_KEYS = ("KBD", "COPYRIGHT", "COMPANY", "LOCALENAME", "LOCALEID", "VERSION")


class KlcParseError(ValueError):
    """Raised when a ``.klc`` file cannot be parsed at all."""


def unicode_name(code_point: int) -> str:
    """Return the official Unicode name for ``code_point``.

    Control characters have no name of their own; Unicode gives them formal
    aliases instead and MSKLC's generated comments use those aliases, so they
    are resolved here too.
    """
    char = chr(code_point)
    try:
        return unicodedata.name(char)
    except ValueError:
        pass
    for alias in _control_aliases(char):
        return alias
    return f"<U+{code_point:04X}>"


def _control_aliases(char: str) -> list[str]:
    # ``unicodedata`` exposes no public alias API, so fall back to the small
    # table of C0/C1 control names that MSKLC actually emits.
    return _CONTROL_NAMES.get(ord(char), [])


_CONTROL_NAMES: dict[int, list[str]] = {
    0x00: ["NULL"],
    0x08: ["BACKSPACE"],
    0x09: ["CHARACTER TABULATION"],
    0x0A: ["LINE FEED"],
    0x0D: ["CARRIAGE RETURN"],
    0x1B: ["ESCAPE"],
    0x1C: ["INFORMATION SEPARATOR FOUR"],
    0x1D: ["INFORMATION SEPARATOR THREE"],
    0x1E: ["INFORMATION SEPARATOR TWO"],
    0x1F: ["INFORMATION SEPARATOR ONE"],
    0x7F: ["DELETE"],
}


@dataclass(frozen=True)
class KeyOutput:
    """One cell of the LAYOUT table."""

    raw: str
    #: ``None`` when the cell is ``-1`` (no character assigned).
    code_point: int | None
    is_dead: bool

    @property
    def char(self) -> str | None:
        return None if self.code_point is None else chr(self.code_point)

    @property
    def name(self) -> str | None:
        return None if self.code_point is None else unicode_name(self.code_point)


@dataclass
class LayoutRow:
    line_no: int
    raw: str
    scan_code: int
    virtual_key: str
    cap_flag: str
    outputs: dict[int, KeyOutput]
    comment: str | None

    @property
    def comment_names(self) -> list[str]:
        if self.comment is None:
            return []
        return [part.strip() for part in self.comment.split(",")]


@dataclass
class DeadKeyEntry:
    line_no: int
    raw: str
    base: int
    composite: int

    @property
    def base_char(self) -> str:
        return chr(self.base)

    @property
    def composite_char(self) -> str:
        return chr(self.composite)


@dataclass
class DeadKey:
    line_no: int
    root: int
    entries: list[DeadKeyEntry] = field(default_factory=list)

    @property
    def root_char(self) -> str:
        return chr(self.root)

    @property
    def mapping(self) -> dict[int, int]:
        return {entry.base: entry.composite for entry in self.entries}

    @property
    def default(self) -> int | None:
        """Composite produced by the space bar, i.e. the dead key's default."""
        return self.mapping.get(0x20)


@dataclass
class NamedEntry:
    line_no: int
    key: str
    value: str


@dataclass
class Klc:
    path: Path
    text: str
    lines: list[str]
    header: dict[str, NamedEntry]
    shift_states: list[int]
    layout: list[LayoutRow]
    dead_keys: list[DeadKey]
    key_names: list[NamedEntry]
    key_names_ext: list[NamedEntry]
    key_names_dead: list[NamedEntry]
    descriptions: list[NamedEntry]
    language_names: list[NamedEntry]
    section_lines: dict[str, int]
    had_bom: bool
    line_endings: set[str]

    @property
    def dead_key_roots(self) -> list[int]:
        return [dk.root for dk in self.dead_keys]

    @property
    def declared_dead_roots(self) -> list[int]:
        """Code points marked with a trailing ``@`` in the LAYOUT table."""
        roots: list[int] = []
        for row in self.layout:
            for _state, output in sorted(row.outputs.items()):
                if output.is_dead and output.code_point is not None:
                    roots.append(output.code_point)
        return roots

    def dead_key(self, root: int) -> DeadKey | None:
        for dk in self.dead_keys:
            if dk.root == root:
                return dk
        return None

    def row_for_output(self, code_point: int, state: int) -> LayoutRow | None:
        for row in self.layout:
            output = row.outputs.get(state)
            if output is not None and output.code_point == code_point:
                return row
        return None


def _parse_output(token: str) -> KeyOutput:
    is_dead = token.endswith("@")
    body = token[:-1] if is_dead else token
    if body == "-1":
        return KeyOutput(raw=token, code_point=None, is_dead=is_dead)
    if body == "%%":
        # MSKLC's ligature marker; no single code point.
        return KeyOutput(raw=token, code_point=None, is_dead=is_dead)
    if len(body) == 1:
        return KeyOutput(raw=token, code_point=ord(body), is_dead=is_dead)
    try:
        return KeyOutput(raw=token, code_point=int(body, 16), is_dead=is_dead)
    except ValueError as exc:  # pragma: no cover - defensive
        raise KlcParseError(f"cannot decode LAYOUT cell {token!r}") from exc


def read_text(path: str | Path) -> tuple[str, bool, set[str]]:
    """Decode a ``.klc`` file, reporting its BOM and line-ending styles."""
    raw = Path(path).read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16")
        had_bom = True
    elif raw[:3] == b"\xef\xbb\xbf":
        text = raw.decode("utf-8-sig")
        had_bom = True
    else:
        text = raw.decode("utf-8")
        had_bom = False
    endings: set[str] = set()
    if "\r\n" in text:
        endings.add("crlf")
    if text.replace("\r\n", "").count("\n"):
        endings.add("lf")
    if text.replace("\r\n", "").count("\r"):
        endings.add("cr")
    return text.replace("\r\n", "\n").lstrip(BOM), had_bom, endings


def parse(path: str | Path) -> Klc:
    """Parse ``path`` into a :class:`Klc` model."""
    path = Path(path)
    text, had_bom, endings = read_text(path)
    lines = text.split("\n")

    header: dict[str, NamedEntry] = {}
    shift_states: list[int] = []
    layout: list[LayoutRow] = []
    dead_keys: list[DeadKey] = []
    key_names: list[NamedEntry] = []
    key_names_ext: list[NamedEntry] = []
    key_names_dead: list[NamedEntry] = []
    descriptions: list[NamedEntry] = []
    language_names: list[NamedEntry] = []
    section_lines: dict[str, int] = {}

    named_sections = {
        "KEYNAME": key_names,
        "KEYNAME_EXT": key_names_ext,
        "KEYNAME_DEAD": key_names_dead,
        "DESCRIPTIONS": descriptions,
        "LANGUAGENAMES": language_names,
    }

    section: str | None = None
    current_dead: DeadKey | None = None

    for index, raw_line in enumerate(lines):
        line_no = index + 1
        line = raw_line.rstrip()
        if not line.strip():
            continue

        head = line.split(None, 1)[0]

        if head in HEADER_KEYS and section is None:
            _, _, rest = line.partition(head)
            header[head] = NamedEntry(line_no, head, _unquote(rest.strip()))
            continue

        if head == "DEADKEY":
            section = "DEADKEY"
            section_lines.setdefault("DEADKEY", line_no)
            root_token = line.split()[1]
            current_dead = DeadKey(line_no=line_no, root=int(root_token, 16))
            dead_keys.append(current_dead)
            continue

        if head in (
            "SHIFTSTATE",
            "LAYOUT",
            "KEYNAME",
            "KEYNAME_EXT",
            "KEYNAME_DEAD",
            "DESCRIPTIONS",
            "LANGUAGENAMES",
            "ATTRIBUTES",
            "LIGATURE",
            "ENDKBD",
        ):
            section = head
            section_lines.setdefault(head, line_no)
            current_dead = None
            continue

        if line.lstrip().startswith("//") or line.lstrip().startswith(";"):
            continue

        if section == "SHIFTSTATE":
            shift_states.append(int(line.split()[0]))
            continue

        if section == "LAYOUT":
            layout.append(_parse_layout_row(line_no, line, shift_states))
            continue

        if section == "DEADKEY" and current_dead is not None:
            body, _, _comment = line.partition("//")
            parts = body.split()
            if len(parts) < 2:
                continue
            current_dead.entries.append(
                DeadKeyEntry(
                    line_no=line_no,
                    raw=line,
                    base=int(parts[0], 16),
                    composite=int(parts[1], 16),
                )
            )
            continue

        if section in named_sections:
            key, _, value = line.partition("\t")
            if not value:
                key, _, value = line.partition(" ")
            named_sections[section].append(
                NamedEntry(line_no, key.strip(), _unquote(value.strip()))
            )
            continue

    if not layout:
        raise KlcParseError(f"{path}: no LAYOUT section found")

    return Klc(
        path=path,
        text=text,
        lines=lines,
        header=header,
        shift_states=shift_states,
        layout=layout,
        dead_keys=dead_keys,
        key_names=key_names,
        key_names_ext=key_names_ext,
        key_names_dead=key_names_dead,
        descriptions=descriptions,
        language_names=language_names,
        section_lines=section_lines,
        had_bom=had_bom,
        line_endings=endings,
    )


def _parse_layout_row(line_no: int, line: str, shift_states: list[int] | None = None) -> LayoutRow:
    body, sep, comment = line.partition("//")
    parts = body.split()
    if len(parts) < 4:
        raise KlcParseError(f"line {line_no}: malformed LAYOUT row {line!r}")
    scan_code = int(parts[0], 16)
    virtual_key = parts[1]
    cap_flag = parts[2]
    cells = parts[3:]
    # The LAYOUT columns follow the order declared by the SHIFTSTATE section.
    states = list(shift_states or [0, 1, 2, 6, 7])[: len(cells)]
    outputs = {state: _parse_output(cell) for state, cell in zip(states, cells, strict=False)}
    return LayoutRow(
        line_no=line_no,
        raw=line,
        scan_code=scan_code,
        virtual_key=virtual_key,
        cap_flag=cap_flag,
        outputs=outputs,
        comment=comment.strip() if sep else None,
    )


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value
