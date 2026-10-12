import os

os.environ["MOCK_MODE"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.schemas import NextExerciseResponse, ProgressResponse, ScoreResponse, StoryResponse  # noqa: E402

client = TestClient(app)


def test_score():
    for _ in range(20):  # mock is random; hit every branch
        r = client.post("/score", data={"target": "dog", "shown_at_ms": "0"}, files={"audio": ("a.webm", b"x", "audio/webm")})
        assert r.status_code == 200
        ScoreResponse.model_validate(r.json())


def test_score_requires_audio():
    assert client.post("/score", data={"target": "dog"}).status_code == 422


def test_next_exercise():
    hist = [{"heard": "bog", "target_phonemes": ["d"], "heard_phonemes": ["b"], "correct": False,
             "phoneme_accuracy": 0.0, "response_ms": 1000, "error_type": "letter_reversal"}]
    r = client.post("/next-exercise", json={"player_id": "p1", "game": "word_flash", "history": hist})
    assert r.status_code == 200
    NextExerciseResponse.model_validate(r.json())


def test_story():
    r = client.post("/story", json={"player_id": "p1", "weak_sounds": ["b", "d"], "interests": ["football"]})
    assert r.status_code == 200
    StoryResponse.model_validate(r.json())


def test_progress():
    r = client.get("/progress/p1")
    assert r.status_code == 200
    assert ProgressResponse.model_validate(r.json()).sessions
