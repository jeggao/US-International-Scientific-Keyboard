"""The official Unicode name for a code point.

Control characters have no name of their own; Unicode gives them formal
aliases instead, and those are what MSKLC's generated comments and this
project's documentation use, so they are resolved here too.

One table, one function: the ``.klc`` parser and the model used to carry a
copy each, which is exactly the kind of pair that drifts.
"""

from __future__ import annotations

import unicodedata

#: The C0/C1 control aliases that appear in a ``.klc``.
CONTROL_NAMES: dict[int, str] = {
    0x00: "NULL",
    0x08: "BACKSPACE",
    0x09: "CHARACTER TABULATION",
    0x0A: "LINE FEED",
    0x0D: "CARRIAGE RETURN",
    0x1B: "ESCAPE",
    0x1C: "INFORMATION SEPARATOR FOUR",
    0x1D: "INFORMATION SEPARATOR THREE",
    0x1E: "INFORMATION SEPARATOR TWO",
    0x1F: "INFORMATION SEPARATOR ONE",
    0x7F: "DELETE",
}


def unicode_name(code_point: int) -> str:
    """Return the official Unicode name for ``code_point``."""
    try:
        return unicodedata.name(chr(code_point))
    except ValueError:
        return CONTROL_NAMES.get(code_point, f"<U+{code_point:04X}>")
