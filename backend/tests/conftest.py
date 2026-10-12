import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))


@pytest.fixture
def mock_client(monkeypatch):
    monkeypatch.setattr(main, "MOCK", True)
    return TestClient(main.app)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "MOCK", False)
    return TestClient(main.app)
