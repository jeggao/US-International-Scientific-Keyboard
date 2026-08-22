"""Shared fixtures.

``tools/`` is put on ``sys.path`` by ``pythonpath`` in pyproject.toml, so no
path juggling is needed here.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT
