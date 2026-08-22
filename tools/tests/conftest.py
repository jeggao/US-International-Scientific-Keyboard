import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT
