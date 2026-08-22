"""Escaping text for XML, in the two places this project writes it.

Both XML back ends -- the macOS ``.keylayout`` and the SVG the picture is drawn
into -- carried an escape table each, and the two had drifted: one escaped the
double quote and the other did not. That difference was not arbitrary, though.
Escaping depends on where the text lands:

* inside a **double-quoted attribute** the quote must be escaped, or it closes
  the attribute early;
* inside **element content** it must not be, or the file gains ``&quot;`` where
  a reader expects ``"``.

The macOS generator writes attributes, the picture writes mostly content. What
was actually wrong was that the picture used its content escaper for the SVG's
``aria-label`` attribute too, which would have broken the file the first time a
layout was named with a quote in it. So: one table, two functions, and each
back end says which context it is in.
"""

from __future__ import annotations

import unicodedata

#: The three that are never safe unescaped, wherever the text lands.
CONTENT_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}

#: Those three plus the double quote, for a double-quoted attribute value. The
#: apostrophe is absent deliberately: nothing here is written inside a
#: single-quoted attribute.
ATTRIBUTE_ESCAPES = {**CONTENT_ESCAPES, '"': "&quot;"}


def _escape(text: str, table: dict[str, str], numeric_references: bool) -> str:
    out: list[str] = []
    for char in text:
        if char in table:
            out.append(table[char])
        elif not numeric_references or char == " ":
            out.append(char)
        elif unicodedata.category(char)[0] in ("C", "Z", "M"):
            out.append(f"&#x{ord(char):04X};")
        else:
            out.append(char)
    return "".join(out)


def escape_content(text: str, numeric_references: bool = False) -> str:
    """Escape ``text`` for XML element content."""
    return _escape(text, CONTENT_ESCAPES, numeric_references)


def escape_attribute(text: str, numeric_references: bool = False) -> str:
    """Escape ``text`` for a double-quoted XML attribute value.

    With ``numeric_references``, a character that is invisible or would not
    survive being pasted around -- a control character, a separator, a
    combining mark -- is written as ``&#xXXXX;`` as well. An ordinary space
    stays a space: Apple's own layouts write it that way and it reads better.
    """
    return _escape(text, ATTRIBUTE_ESCAPES, numeric_references)
