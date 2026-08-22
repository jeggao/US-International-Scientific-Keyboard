"""Repository hygiene checks for the plain-text files in the project."""

from __future__ import annotations

from pathlib import Path

from .report import Reporter

#: Everything except the ``.klc``, which MSKLC writes as UTF-16 with CRLF.
TEXT_GLOBS = (
    "*.md",
    "*.json",
    "*.svg",
    "*.ipynb",
    "*.toml",
    "*.txt",
    "*.yml",
    "*.yaml",
    "*.py",
    ".gitignore",
)

SKIP_DIRECTORIES = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".venv"}


def iter_text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if SKIP_DIRECTORIES & set(path.relative_to(root).parts):
            continue
        if any(path.match(pattern) for pattern in TEXT_GLOBS):
            yield path


def check(root: Path, reporter: Reporter) -> None:
    for path in iter_text_files(root):
        data = path.read_bytes()
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
