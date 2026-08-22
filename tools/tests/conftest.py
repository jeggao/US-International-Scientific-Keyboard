"""Shared fixtures.

``tools/`` is put on ``sys.path`` by ``pythonpath`` in pyproject.toml, so no
path juggling is needed here.
"""

import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

KLC_NAME = "US International Scientific.klc"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def sandbox(tmp_path, repo_root) -> Path:
    """A throwaway copy of the repository, for tests that break things on purpose."""
    for name in (KLC_NAME, "README.md", "CONTRIBUTING.md"):
        shutil.copy2(repo_root / name, tmp_path / name)
    for directory in ("assets", "layout", "dist"):
        shutil.copytree(repo_root / directory, tmp_path / directory)
    return tmp_path


def edit(path: Path, old: str, new: str) -> None:
    """Replace the first occurrence of ``old``, asserting it was there."""
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not found in {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def edit_klc(path: Path, old: str, new: str) -> None:
    """The same, through the ``.klc``'s UTF-16 encoding."""
    text = path.read_bytes().decode("utf-16")
    assert old in text, f"{old!r} not found in the .klc"
    path.write_bytes(("﻿" + text.lstrip("﻿").replace(old, new, 1)).encode("utf-16-le"))
