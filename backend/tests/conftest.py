import pytest
from fastapi.testclient import TestClient

from app import brain, main


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))


@pytest.fixture(autouse=True)
def stories_unlocked(monkeypatch):
    """Story tests don't play 20 rounds first; test_story_unlock.py sets the real threshold."""
    monkeypatch.setattr(brain, "STORY_UNLOCK", 0)


@pytest.fixture
def mock_client(monkeypatch):
    monkeypatch.setattr(main, "MOCK", True)
    return TestClient(main.app)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "MOCK", False)
    return TestClient(main.app)


@pytest.fixture
def login():
    """login(client, name) -> (player_id, auth headers). Registers the player the first time."""
    cache = {}

    def _login(client, name="p1"):
        if name not in cache:
            r = client.post("/players", json={"name": name, "password": "test-password"}).json()
            cache[name] = (r["player_id"], {"Authorization": f"Bearer {r['token']}"})
        return cache[name]

    return _login
