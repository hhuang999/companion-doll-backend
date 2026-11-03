import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from companion.core.config import Config
from companion.store import Store


@pytest.fixture
def config():
    return Config()


@pytest.fixture
def store(tmp_path):
    value = Store(tmp_path / "test.db")
    yield value
    value.close()
