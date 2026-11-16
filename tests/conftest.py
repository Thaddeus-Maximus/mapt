import shutil
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "shop"


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "shop"
    shutil.copytree(FIXTURE, r, ignore=shutil.ignore_patterns(".mapt", ".trash"))
    return r


@pytest.fixture
def index(root):
    from mapt.index import Index
    return Index(root)
