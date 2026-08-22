"""Rasterise the generated SVG into the PNG that README.md shows.

Rasterising needs a browser, which is why this is not part of the ordinary
generate step: the SVG and the keyboard-layout-editor source are pure text and
are generated everywhere, while the PNG is only rebuilt where a Chromium is
available. CI has one, and rebuilds the picture on every push.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

SVG_PATH = "assets/keyboard-layout.svg"
PNG_PATH = "assets/keyboard-layout.png"

#: Where a headless Chromium may be found, in the order they are tried. The
#: Playwright download is what CI installs; the rest are ordinary packages.
CHROMIUM_CANDIDATES = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "chrome",
)


def find_chromium() -> str | None:
    """Locate a headless-capable Chromium, however it was installed."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as play:
            path = play.chromium.executable_path
            if path and Path(path).is_file():
                return path
    except Exception:
        pass

    for name in CHROMIUM_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found

    roots = [
        Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")),
        Path.home() / ".cache" / "ms-playwright",
    ]
    patterns = (
        "chromium-*/chrome-linux/chrome",
        "chromium_headless_shell-*/chrome-linux/headless_shell",
    )
    for root in roots:
        if not root.is_dir():
            continue
        for pattern in patterns:
            for candidate in sorted(root.glob(pattern), reverse=True):
                if candidate.is_file():
                    return str(candidate)
    return None


#: Headless Chromium paints less than the window it is given -- measurably about
#: 87 pixels less -- so the shot is taken in a taller window and cropped back.
VIEWPORT_SLACK = 240

#: How far one colour channel may move before a pixel counts as changed.
CHANNEL_TOLERANCE = 8


def render(svg: str, width: int, height: int, chromium: str) -> bytes:
    """Screenshot an SVG at its natural size."""
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        # A wrapper page pins the size and removes the default margin, so the
        # screenshot is exactly the drawing.
        (work / "page.html").write_text(
            "<!doctype html><meta charset='utf-8'>"
            "<style>html,body{margin:0;padding:0;background:transparent}"
            "img{display:block}</style>"
            f"<img src='picture.svg' width='{width}' height='{height}'>",
            encoding="utf-8",
        )
        (work / "picture.svg").write_text(svg, encoding="utf-8")
        output = work / "shot.png"
        command = [
            chromium,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--default-background-color=00000000",
            "--force-device-scale-factor=1",
            f"--window-size={width},{height + VIEWPORT_SLACK}",
            f"--screenshot={output}",
            "--allow-file-access-from-files",
            str(work / "page.html"),
        ]
        finished = subprocess.run(command, capture_output=True, text=True)
        if not output.exists():
            raise SystemExit(
                "chromium did not produce a screenshot:\n"
                + (finished.stderr or finished.stdout)[-2000:]
            )
        return _crop(output.read_bytes(), width, height)


def _crop(data: bytes, width: int, height: int) -> bytes:
    import io

    from PIL import Image

    image = Image.open(io.BytesIO(data)).convert("RGBA")
    if image.size == (width, height):
        return data
    if image.size[0] < width or image.size[1] < height:
        raise SystemExit(f"chromium produced {image.size}, smaller than {(width, height)}")
    buffer = io.BytesIO()
    image.crop((0, 0, width, height)).save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def difference(left: bytes, right: bytes) -> float:
    """Fraction of pixels that differ, or 1.0 if the two are not comparable."""
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return 0.0 if left == right else 1.0
    import io

    first = Image.open(io.BytesIO(left)).convert("RGBA")
    second = Image.open(io.BytesIO(right)).convert("RGBA")
    if first.size != second.size:
        return 1.0
    # A pixel counts as changed when any channel moves by more than the
    # threshold. Thresholding each band and combining them keeps this to whole
    # image operations rather than walking a million Python tuples, and avoids
    # getdata(), which Pillow is retiring.
    mask = None
    for band in ImageChops.difference(first, second).split():
        marked = band.point(lambda value: 255 if value > CHANNEL_TOLERANCE else 0)
        mask = marked if mask is None else ImageChops.lighter(mask, marked)
    return mask.histogram()[255] / (first.size[0] * first.size[1])
