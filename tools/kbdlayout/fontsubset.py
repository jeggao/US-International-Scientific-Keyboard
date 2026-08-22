"""Rebuild the font subset the overview picture embeds.

Run this when the layout gains a character the picture does not already draw;
``pytest`` says so when that happens. Needs fonttools, brotli and DejaVu Sans.
"""

from __future__ import annotations

import base64
import io
import subprocess
import textwrap
from pathlib import Path

from .generators import picture
from .model import Layout

FAMILY = "DejaVu Sans"
TARGET = "kbdlayout/generators/_picture_font.py"


def rebuild(root: Path, layout: Layout) -> int:
    """Rewrite the embedded font subset to cover exactly what the picture draws."""
    characters = picture.characters(layout)

    font_path = subprocess.run(
        ["fc-match", "-f", "%{file}", FAMILY], capture_output=True, text=True, check=True
    ).stdout.strip()
    if not font_path:
        raise SystemExit(f"{FAMILY} is not installed")

    from fontTools import subset

    options = subset.Options(flavor="woff2", desubroutinize=True)
    options.drop_tables += ["GSUB", "GPOS", "GDEF", "morx", "kern"]
    font = subset.load_font(font_path, options)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text="".join(sorted(characters)))
    subsetter.subset(font)
    buffer = io.BytesIO()
    subset.save_font(font, buffer, options)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    body = "\n".join(f'    "{line}"' for line in textwrap.wrap(encoded, 88))
    target = root / "tools" / TARGET
    target.write_text(
        '"""The font the overview picture embeds, so that it renders the same anywhere.\n'
        "\n"
        f"A subset of {FAMILY}, covering exactly the characters the picture\n"
        "draws. Regenerate with ``python3 tools/subset_font.py``.\n"
        '"""\n'
        "\n"
        "WOFF2_BASE64 = (\n" + body + "\n)\n",
        encoding="utf-8",
    )
    print(
        f"{target.relative_to(root)}: {len(buffer.getvalue())} bytes, {len(characters)} characters"
    )
    return 0
