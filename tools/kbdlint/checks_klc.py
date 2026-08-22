"""Internal consistency checks for the ``.klc`` source file."""

from __future__ import annotations

from .klc import Klc, unicode_name
from .report import Reporter

#: MSKLC 1.4 cannot build a dead key whose root is above this code point, and it
#: cannot emit any character outside the Basic Multilingual Plane. Both limits are
#: documented in README.md ("Notes on MSKLC 1.4").
MAX_DEAD_KEY_ROOT = 0x0FFF
MAX_CODE_POINT = 0xFFFF

REQUIRED_SECTIONS = (
    "SHIFTSTATE",
    "LAYOUT",
    "KEYNAME",
    "KEYNAME_EXT",
    "KEYNAME_DEAD",
    "DESCRIPTIONS",
    "LANGUAGENAMES",
    "ENDKBD",
)


def check(klc: Klc, reporter: Reporter) -> None:
    _check_file_shape(klc, reporter)
    _check_header(klc, reporter)
    _check_layout_comments(klc, reporter)
    _check_layout_order(klc, reporter)
    _check_code_point_limits(klc, reporter)
    _check_dead_key_agreement(klc, reporter)
    _check_dead_key_bodies(klc, reporter)


def _add(reporter: Reporter, klc: Klc, line: int, message: str, check_name: str) -> None:
    reporter.add(check_name, klc.path, line, message)


def _check_file_shape(klc: Klc, reporter: Reporter) -> None:
    if not klc.had_bom:
        _add(reporter, klc, 1, "file is missing its byte order mark", "klc-encoding")
    if klc.line_endings != {"crlf"}:
        _add(
            reporter,
            klc,
            1,
            f"expected CRLF line endings throughout, found {sorted(klc.line_endings)}",
            "klc-encoding",
        )
    for section in REQUIRED_SECTIONS:
        if section not in klc.section_lines:
            _add(reporter, klc, 1, f"missing {section} section", "klc-structure")


def _check_header(klc: Klc, reporter: Reporter) -> None:
    kbd = klc.header.get("KBD")
    if kbd is None:
        _add(reporter, klc, 1, "missing KBD header line", "klc-structure")
        return
    parts = kbd.value.split(None, 1)
    if len(parts) != 2:
        _add(reporter, klc, kbd.line_no, f"malformed KBD line: {kbd.value!r}", "klc-structure")
        return
    dll_name, description = parts[0], parts[1].strip().strip('"')
    if not dll_name.startswith("KBD"):
        _add(
            reporter,
            klc,
            kbd.line_no,
            f"layout DLL name {dll_name!r} should start with 'KBD'",
            "klc-naming",
        )
    for entry in klc.descriptions:
        if entry.value != description:
            _add(
                reporter,
                klc,
                entry.line_no,
                f"DESCRIPTIONS text {entry.value!r} differs from the KBD line {description!r}",
                "klc-version",
            )
    locale = klc.header.get("LOCALEID")
    if locale is not None:
        for entry in klc.descriptions + klc.language_names:
            if entry.key.lower() != locale.value[-4:].lower():
                _add(
                    reporter,
                    klc,
                    entry.line_no,
                    f"language id {entry.key!r} does not match LOCALEID {locale.value!r}",
                    "klc-structure",
                )


def _check_layout_comments(klc: Klc, reporter: Reporter) -> None:
    for row in klc.layout:
        expected = []
        for state in klc.shift_states:
            output = row.outputs.get(state)
            if output is None:
                continue
            expected.append(
                "<none>" if output.code_point is None else unicode_name(output.code_point)
            )
        if row.comment is None:
            _add(
                reporter,
                klc,
                row.line_no,
                f"LAYOUT row {row.virtual_key} has no trailing name comment",
                "klc-comment",
            )
            continue
        if row.comment_names != expected:
            _add(
                reporter,
                klc,
                row.line_no,
                (
                    f"LAYOUT row {row.virtual_key} comment lists "
                    f"{row.comment_names} but the row produces {expected}"
                ),
                "klc-comment",
            )


def _check_layout_order(klc: Klc, reporter: Reporter) -> None:
    seen_scan: dict[int, int] = {}
    seen_vk: dict[str, int] = {}
    previous = -1
    for row in klc.layout:
        if row.scan_code in seen_scan:
            _add(
                reporter,
                klc,
                row.line_no,
                f"duplicate scan code {row.scan_code:02x} "
                f"(first seen on line {seen_scan[row.scan_code]})",
                "klc-layout",
            )
        if row.virtual_key in seen_vk:
            _add(
                reporter,
                klc,
                row.line_no,
                f"duplicate virtual key {row.virtual_key} "
                f"(first seen on line {seen_vk[row.virtual_key]})",
                "klc-layout",
            )
        seen_scan[row.scan_code] = row.line_no
        seen_vk[row.virtual_key] = row.line_no
        if row.scan_code < previous:
            _add(
                reporter,
                klc,
                row.line_no,
                f"scan code {row.scan_code:02x} is out of order (previous row was {previous:02x})",
                "klc-layout",
            )
        previous = row.scan_code
        if len(row.outputs) != len(klc.shift_states):
            _add(
                reporter,
                klc,
                row.line_no,
                (
                    f"row {row.virtual_key} declares {len(row.outputs)} shift-state columns "
                    f"but SHIFTSTATE declares {len(klc.shift_states)}"
                ),
                "klc-layout",
            )


def _check_code_point_limits(klc: Klc, reporter: Reporter) -> None:
    for row in klc.layout:
        for state, output in row.outputs.items():
            if output.code_point is None:
                continue
            if output.code_point > MAX_CODE_POINT:
                _add(
                    reporter,
                    klc,
                    row.line_no,
                    f"U+{output.code_point:04X} is outside the BMP (shift state {state})",
                    "klc-limits",
                )
            if output.is_dead and output.code_point > MAX_DEAD_KEY_ROOT:
                _add(
                    reporter,
                    klc,
                    row.line_no,
                    (
                        f"dead key root U+{output.code_point:04X} exceeds the MSKLC limit of "
                        f"U+{MAX_DEAD_KEY_ROOT:04X}"
                    ),
                    "klc-limits",
                )
    for dead_key in klc.dead_keys:
        for entry in dead_key.entries:
            if entry.composite > MAX_CODE_POINT:
                _add(
                    reporter,
                    klc,
                    entry.line_no,
                    f"composite U+{entry.composite:04X} is outside the BMP",
                    "klc-limits",
                )
            if entry.base > MAX_DEAD_KEY_ROOT:
                _add(
                    reporter,
                    klc,
                    entry.line_no,
                    (
                        f"dead key base U+{entry.base:04X} exceeds the MSKLC limit of "
                        f"U+{MAX_DEAD_KEY_ROOT:04X}"
                    ),
                    "klc-limits",
                )


def _check_dead_key_agreement(klc: Klc, reporter: Reporter) -> None:
    declared = klc.declared_dead_roots
    defined = klc.dead_key_roots
    named = [int(entry.key, 16) for entry in klc.key_names_dead]

    for root in declared:
        if root not in defined:
            row = klc.row_for_output(root, 6) or klc.row_for_output(root, 7)
            _add(
                reporter,
                klc,
                row.line_no if row else 1,
                f"U+{root:04X} is marked '@' in LAYOUT but has no DEADKEY section",
                "klc-deadkey",
            )
    for root in defined:
        if root not in declared:
            section = klc.dead_key(root)
            _add(
                reporter,
                klc,
                section.line_no if section else 1,
                f"DEADKEY U+{root:04X} is never referenced from LAYOUT",
                "klc-deadkey",
            )
    if declared != named:
        _add(
            reporter,
            klc,
            klc.section_lines.get("KEYNAME_DEAD", 1),
            (
                "KEYNAME_DEAD does not list the dead keys in LAYOUT order: "
                f"{[f'U+{r:04X}' for r in named]} vs {[f'U+{r:04X}' for r in declared]}"
            ),
            "klc-deadkey",
        )
    if declared != defined:
        _add(
            reporter,
            klc,
            klc.section_lines.get("DEADKEY", 1),
            (
                "DEADKEY sections are not in LAYOUT order: "
                f"{[f'U+{r:04X}' for r in defined]} vs {[f'U+{r:04X}' for r in declared]}"
            ),
            "klc-deadkey",
        )
    for entry in klc.key_names_dead:
        root = int(entry.key, 16)
        expected = unicode_name(root)
        if entry.value != expected:
            _add(
                reporter,
                klc,
                entry.line_no,
                f"KEYNAME_DEAD for U+{root:04X} says {entry.value!r}, expected {expected!r}",
                "klc-deadkey",
            )


def _check_dead_key_bodies(klc: Klc, reporter: Reporter) -> None:
    for dead_key in klc.dead_keys:
        seen: dict[int, int] = {}
        for entry in dead_key.entries:
            if entry.base in seen:
                _add(
                    reporter,
                    klc,
                    entry.line_no,
                    (
                        f"dead key U+{dead_key.root:04X} maps base U+{entry.base:04X} twice "
                        f"(first on line {seen[entry.base]})"
                    ),
                    "klc-deadkey",
                )
            seen[entry.base] = entry.line_no
            _body, separator, comment = entry.raw.partition("//")
            expected = f" {entry.base_char} -> {entry.composite_char}"
            if separator and comment != expected:
                _add(
                    reporter,
                    klc,
                    entry.line_no,
                    f"dead key comment {comment!r} does not match {expected!r}",
                    "klc-comment",
                )
        if 0x20 not in seen:
            _add(
                reporter,
                klc,
                dead_key.line_no,
                (
                    f"dead key U+{dead_key.root:04X} has no U+0020 mapping, so it has no "
                    "default character"
                ),
                "klc-deadkey",
            )
