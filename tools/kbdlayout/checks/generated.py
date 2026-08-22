"""Check that the generated files on disk are what the layout source produces."""

from __future__ import annotations

import difflib
from pathlib import Path

from ..build import as_bytes, render_all
from ..model import Layout
from ..report import Reporter


def check(root: Path, layout: Layout, reporter: Reporter) -> None:
    for relative, content in render_all(layout).items():
        path = root / relative
        expected = as_bytes(content)
        if not path.exists():
            reporter.add(
                "generated-missing",
                path,
                0,
                "this file is generated from the layout source but does not exist; "
                "run `python3 tools/generate.py`",
            )
            continue
        actual = path.read_bytes()
        if actual == expected:
            continue
        reporter.add(
            "generated-stale",
            path,
            _first_difference(actual, expected),
            "this file no longer matches the layout source; run `python3 tools/generate.py`"
            + _summary(actual, expected),
        )


def _first_difference(actual: bytes, expected: bytes) -> int:
    """The 1-based line number where the two versions first diverge."""
    for line, (left, right) in enumerate(
        zip(_lines(actual), _lines(expected), strict=False), start=1
    ):
        if left != right:
            return line
    return min(len(_lines(actual)), len(_lines(expected))) + 1


def _lines(data: bytes) -> list[str]:
    for encoding in ("utf-8", "utf-16"):
        try:
            return data.decode(encoding).replace("\r\n", "\n").split("\n")
        except UnicodeDecodeError:
            continue
    return [repr(data)]


def _summary(actual: bytes, expected: bytes) -> str:
    diff = list(
        difflib.unified_diff(
            _lines(actual), _lines(expected), "on disk", "generated", lineterm="", n=0
        )
    )
    body = [line for line in diff[2:] if line[:1] in "+-"][:6]
    if not body:
        return ""
    return "\n    " + "\n    ".join(body)
