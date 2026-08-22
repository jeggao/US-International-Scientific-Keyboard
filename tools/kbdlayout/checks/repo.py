"""Repository hygiene checks for the text files in the project.

Which files count as text is decided by exclusion, not by a list of extensions
to include. An allowlist fails open: it silently exempted three of the six
generated files -- the XKB symbols file, the Compose file and the
``.keylayout``, none of which has a matching suffix -- and would exempt any new
kind of file too. A denylist means a file has to be *named* as binary to escape
the check.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

from ..model import Layout
from ..report import Reporter

#: Files that are deliberately not LF-terminated UTF-8. The ``.klc`` is UTF-16
#: with CRLF because MSKLC writes it that way and refuses to open anything
#: else; the rest are binary formats.
BINARY_SUFFIXES = frozenset(
    {".klc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2", ".ttf", ".zip"}
)

SKIP_DIRECTORIES = frozenset(
    {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "venv", "node_modules"}
)

#: How much of a file to look at when deciding whether it is binary.
SNIFF_BYTES = 8192


def tracked_files(root: Path) -> list[Path] | None:
    """The files git tracks, or ``None`` when this is not a git checkout.

    Asking git rather than walking the tree keeps build output and anything
    ignored out of the check without a second copy of ``.gitignore``.
    """
    try:
        finished = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    names = finished.stdout.decode("utf-8").split("\0")
    return [root / name for name in names if name]


def iter_text_files(root: Path) -> Iterator[tuple[Path, bytes]]:
    """Every text file in the repository, with its contents."""
    paths = tracked_files(root)
    if paths is None:  # pragma: no cover - only outside a git checkout
        paths = [path for path in root.rglob("*") if path.is_file()]
    for path in sorted(paths):
        if not path.is_file():
            continue
        if SKIP_DIRECTORIES & set(path.relative_to(root).parts):
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        data = path.read_bytes()
        if b"\x00" in data[:SNIFF_BYTES]:
            continue
        yield path, data


def check(root: Path, layout: Layout, reporter: Reporter) -> None:
    for path, data in iter_text_files(root):
        if not data:
            continue
        line_count = data.count(b"\n") + 1
        if not data.endswith(b"\n"):
            reporter.add("repo-newline", path, line_count, "file does not end with a newline")
        elif data.endswith(b"\n\n"):
            reporter.add(
                "repo-newline",
                path,
                line_count,
                "file ends with more than one newline",
                severity="warning",
            )
        if b"\r" in data:
            reporter.add(
                "repo-line-endings",
                path,
                data.split(b"\r")[0].count(b"\n") + 1,
                "file contains a carriage return; use LF line endings",
            )
