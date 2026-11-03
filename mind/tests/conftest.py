import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))  # helpers, island, fakeworld
from fakeworld import FakeWorldServer  # noqa: E402


@pytest.fixture
def world_server():
    server = FakeWorldServer()
    yield server
    server.close()
