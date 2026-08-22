"""Reading and writing the TOML file that defines the layout.

The format is documented in CONTRIBUTING.md. In short:

* a character is written either as itself (``"q"``, ``"÷"``) or, when it is
  invisible or would not survive being pasted around -- a space, a control
  character, a combining mark -- as ``"U+XXXX"``;
* a shift state that starts a dead key is written ``{ dead = "U+0300" }``
  instead of a bare string;
* a shift state a key does not use is simply omitted.
"""

from __future__ import annotations

import tomllib
import unicodedata
from pathlib import Path
from typing import Any

from .keys import READING_ORDER, position
from .model import (
    LEVELS,
    DeadKey,
    Key,
    Layout,
    LayoutError,
    LinuxTarget,
    Output,
    WindowsTarget,
    unicode_name,
)

CODE_POINT_PREFIX = "U+"


def decode_char(value: str, where: str) -> int:
    """Turn one TOML character value into a code point."""
    if not isinstance(value, str):
        raise LayoutError(f"{where}: expected a string, got {value!r}")
    if value.startswith(CODE_POINT_PREFIX):
        try:
            return int(value[len(CODE_POINT_PREFIX) :], 16)
        except ValueError:
            raise LayoutError(f"{where}: {value!r} is not a valid code point") from None
    if len(value) != 1:
        raise LayoutError(
            f"{where}: {value!r} is not a single character; write it as U+XXXX "
            "if you meant a code point"
        )
    return ord(value)


def encode_char(code_point: int) -> str:
    """Turn a code point into the most readable TOML value for it."""
    char = chr(code_point)
    category = unicodedata.category(char)
    if category[0] in ("C", "Z") or category in ("Mn", "Me", "Mc"):
        return f"{CODE_POINT_PREFIX}{code_point:04X}"
    return char


def _decode_output(value: Any, where: str) -> Output:
    if isinstance(value, dict):
        extra = set(value) - {"dead"}
        if extra:
            raise LayoutError(f"{where}: unknown key(s) {sorted(extra)}")
        if "dead" not in value:
            raise LayoutError(f'{where}: expected {{ dead = "..." }}')
        return Output(decode_char(value["dead"], where), dead=True)
    return Output(decode_char(value, where))


def loads(text: str, origin: str = "<string>") -> Layout:
    return _build(tomllib.loads(text), origin)


def load(path: str | Path) -> Layout:
    path = Path(path)
    with path.open("rb") as handle:
        return _build(tomllib.load(handle), str(path))


def _build(data: dict[str, Any], origin: str) -> Layout:
    try:
        meta = data["layout"]
    except KeyError:
        raise LayoutError(f"{origin}: missing [layout] table") from None

    windows = WindowsTarget(**meta["windows"])
    linux = LinuxTarget(**meta["linux"])

    keys: list[Key] = []
    for index, entry in enumerate(data.get("key", [])):
        where = f"{origin}: [[key]] #{index + 1}"
        try:
            key_id = entry["id"]
        except KeyError:
            raise LayoutError(f"{where} has no id") from None
        position(key_id)  # raises for an unknown position
        outputs = {
            level: _decode_output(entry[level], f"{where} ({key_id}.{level})")
            for level in LEVELS
            if level in entry
        }
        unknown = set(entry) - {"id", "caps", *LEVELS}
        if unknown:
            raise LayoutError(f"{where} ({key_id}): unknown field(s) {sorted(unknown)}")
        keys.append(Key(id=key_id, outputs=outputs, caps_override=entry.get("caps")))

    dead_keys: list[DeadKey] = []
    for index, entry in enumerate(data.get("dead_key", [])):
        where = f"{origin}: [[dead_key]] #{index + 1}"
        root = decode_char(entry["root"], f"{where} (root)")
        entries: list[tuple[int, int]] = []
        for pair in entry.get("map", []):
            if not isinstance(pair, list) or len(pair) != 2:
                raise LayoutError(
                    f"{where}: every map entry must be [base, composite], got {pair!r}"
                )
            base = decode_char(pair[0], f"{where} (base)")
            composite = decode_char(pair[1], f"{where} (composite for {pair[0]!r})")
            entries.append((base, composite))
        dead_keys.append(
            DeadKey(
                root=root,
                category=entry.get("category", ""),
                xkb_leader=entry.get("xkb_leader"),
                entries=entries,
            )
        )

    layout = Layout(
        name=meta["name"],
        version=meta["version"],
        copyright=meta["copyright"],
        company=meta["company"],
        windows=windows,
        linux=linux,
        keys=keys,
        dead_keys=dead_keys,
    )
    problems = layout.validate()
    if problems:
        raise LayoutError(f"{origin} is not a usable layout:\n  " + "\n  ".join(problems))
    return layout


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def dumps(layout: Layout) -> str:
    """Serialise a layout back to the TOML source format."""
    out: list[str] = []
    add = out.append

    add(f"# {layout.name} keyboard layout, version {layout.version}.")
    add("#")
    add("# This file is the source of truth. Every shipped file -- the Windows .klc, the")
    add("# Linux XKB and Compose files -- is generated from it by tools/generate.py, and")
    add("# README.md is checked against it by tools/validate.py.")
    add("#")
    add("# A character is written either as itself or, when it is invisible or does not")
    add("# survive being pasted around (a space, a control character, a combining mark),")
    add('# as "U+XXXX". A shift state that starts a dead key is written { dead = "..." }.')
    add("")
    add("[layout]")
    add(f"name = {_toml_string(layout.name)}")
    add(f"version = {_toml_string(layout.version)}")
    add(f"copyright = {_toml_string(layout.copyright)}")
    add(f"company = {_toml_string(layout.company)}")
    add("")
    add("[layout.windows]")
    add(f"dll_name = {_toml_string(layout.windows.dll_name)}")
    add(f"locale_name = {_toml_string(layout.windows.locale_name)}")
    add(f"locale_id = {_toml_string(layout.windows.locale_id)}")
    add(f"language_name = {_toml_string(layout.windows.language_name)}")
    add(f"klc_version = {_toml_string(layout.windows.klc_version)}")
    add("")
    add("[layout.linux]")
    add(f"symbols_file = {_toml_string(layout.linux.symbols_file)}")
    add(f"variant = {_toml_string(layout.linux.variant)}")
    add(f"description = {_toml_string(layout.linux.description)}")
    add("")
    add("")
    add("# ---------------------------------------------------------------------------")
    add("# Keys, named by their ISO/IEC 9995 position, in reading order.")
    add("# ---------------------------------------------------------------------------")

    order = {key_id: index for index, key_id in enumerate(READING_ORDER)}
    for key in sorted(layout.keys, key=lambda k: order[k.id]):
        add("")
        add(f"[[key]]  # {position(key.id).label}")
        add(f'id = "{key.id}"')
        if key.caps_override is not None:
            add(f"caps = {str(key.caps_override).lower()}")
        for level in LEVELS:
            output = key.outputs.get(level)
            if output is None:
                continue
            value = _toml_string(encode_char(output.code_point))
            rendered = f"{{ dead = {value} }}" if output.dead else value
            add(f"{level} = {rendered}  # {output.name}")

    add("")
    add("")
    add("# ---------------------------------------------------------------------------")
    add("# Dead keys, in the order the keys above declare them. Each maps U+0020 to its")
    add("# default character.")
    add("# ---------------------------------------------------------------------------")

    for dead_key in layout.dead_keys_in_declaration_order(READING_ORDER):
        add("")
        add(f"[[dead_key]]  # {dead_key.category or dead_key.root_name}")
        add(f'root = "{encode_char(dead_key.root)}"  # {dead_key.root_name}')
        if dead_key.category:
            add(f"category = {_toml_string(dead_key.category)}")
        if dead_key.xkb_leader:
            add(f"xkb_leader = {_toml_string(dead_key.xkb_leader)}")
        add("map = [")
        width = max(
            (len(_toml_string(encode_char(base))) for base, _ in dead_key.entries),
            default=0,
        )
        for base, composite in dead_key.entries:
            left = _toml_string(encode_char(base)).ljust(width)
            right = _toml_string(encode_char(composite))
            add(f"  [{left}, {right}],  # {unicode_name(composite)}")
        add("]")

    add("")
    return "\n".join(out)
