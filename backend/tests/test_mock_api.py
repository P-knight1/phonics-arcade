from app.schemas import NextExerciseResponse, ProgressResponse, ScoreResponse, StoryResponse

AUDIO = {"audio": ("a.webm", b"x", "audio/webm")}


def test_score(mock_client):
    for _ in range(20):  # mock is random; hit every branch
        r = mock_client.post("/score", data={"target": "dog", "shown_at_ms": "0"}, files=AUDIO)
        assert r.status_code == 200
        ScoreResponse.model_validate(r.json())


def test_score_heard_text_is_deterministic(mock_client):
    r = mock_client.post("/score", data={"target": "dog", "heard_text": "bog"})
    assert r.json()["error_type"] == "letter_reversal" and r.json()["heard"] == "bog"


def test_score_without_audio_or_text_is_no_response(mock_client):
    assert mock_client.post("/score", data={"target": "dog"}).json()["error_type"] == "no_response"


def test_next_exercise(mock_client, login):
    pid, auth = login(mock_client)
    hist = [{"heard": "bog", "target_phonemes": ["d"], "heard_phonemes": ["b"], "correct": False,
             "phoneme_accuracy": 0.0, "response_ms": 1000, "error_type": "letter_reversal"}]
    r = mock_client.post("/next-exercise", json={"player_id": pid, "game": "word_flash", "history": hist}, headers=auth)
    assert r.status_code == 200
    NextExerciseResponse.model_validate(r.json())


def test_story(mock_client, login):
    pid, auth = login(mock_client)
    r = mock_client.post("/story", json={"player_id": pid, "weak_sounds": ["b", "d"], "interests": ["football"]},
                         headers=auth)
    assert r.status_code == 200
    StoryResponse.model_validate(r.json())


def test_progress(mock_client, login):
    pid, auth = login(mock_client)
    r = mock_client.get(f"/progress/{pid}", headers=auth)
    assert r.status_code == 200
    assert ProgressResponse.model_validate(r.json()).sessions
