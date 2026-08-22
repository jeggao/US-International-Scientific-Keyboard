"""Checks for the files under ``assets/``.

The keyboard-layout-editor source and the SVG are generated, so they cannot
disagree with the layout and :mod:`kbdlayout.checks_generated` already fails if
either is out of date. What is left to check is the PNG, which is rasterised
from the SVG by ``tools/render.py`` and therefore *can* be stale.
"""

from __future__ import annotations

import struct
from pathlib import Path

from .generators import picture
from .model import Layout
from .report import Reporter

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_size(data: bytes) -> tuple[int, int] | None:
    """Read a PNG's dimensions out of its IHDR chunk."""
    if not data.startswith(PNG_SIGNATURE) or len(data) < 24:
        return None
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def check(assets_dir: Path, layout: Layout, reporter: Reporter) -> None:
    png = assets_dir / "keyboard-layout.png"
    if not png.exists():
        reporter.add(
            "assets-picture",
            png,
            0,
            "the overview picture is missing; run `python3 tools/render.py`",
        )
        return

    size = png_size(png.read_bytes())
    if size is None:
        reporter.add("assets-picture", png, 0, "this is not a PNG file")
        return

    expected = picture.size(layout)
    if size != expected:
        reporter.add(
            "assets-picture",
            png,
            0,
            (
                f"the picture is {size[0]}x{size[1]} but the layout draws to "
                f"{expected[0]}x{expected[1]}; run `python3 tools/render.py`"
            ),
        )
