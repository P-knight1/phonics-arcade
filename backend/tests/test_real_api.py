"""Real mode (MOCK_MODE off): everything that doesn't need the GPU. Speech and the LLM are faked at their seams."""
import json

import pytest

from app import brain, speech


def say(client, target, heard, auth=None, game="word_flash", **extra):
    """auth = (player_id, headers) from the login fixture; None = anonymous (scored, not saved)."""
    data = {"target": target, "heard_text": heard, "game": game, **extra}
    return client.post("/score", data=data, headers=auth[1] if auth else None)


def test_score_heard_text(client):
    r = say(client, "dog", "bog")
    assert r.status_code == 200
    assert r.json() == {"heard": "bog", "target_phonemes": ["d", "ɒ", "g"], "heard_phonemes": ["b", "ɒ", "g"],
                        "correct": False, "phoneme_accuracy": 0.67, "response_ms": None, "error_type": "letter_reversal"}


def test_score_response_ms(client):
    import time
    r = say(client, "dog", "dog", shown_at_ms=str(int(time.time() * 1000) - 1500))
    assert 1400 <= r.json()["response_ms"] < 5000


def test_score_no_answer(client):
    for data in ({"target": "dog"}, {"target": "dog", "heard_text": ""}):  # timed out / "wrong" with empty box
        r = client.post("/score", data=data).json()
        assert (r["heard"], r["heard_phonemes"], r["error_type"]) == ("", [], "no_response")


def test_score_audio_waits_for_speech_module(client):
    r = client.post("/score", data={"target": "dog"}, files={"audio": ("a.webm", b"x", "audio/webm")})
    assert r.status_code == 503


def test_score_audio_uses_speech_module(client, monkeypatch):
    monkeypatch.setattr(speech, "recognize", lambda audio, ctype: ("bog", ["b", "ˈɒ", "ɡ"]))
    r = client.post("/score", data={"target": "dog"}, files={"audio": ("a.webm", b"x", "audio/webm")})
    assert r.json()["heard_phonemes"] == ["b", "ɒ", "g"] and r.json()["error_type"] == "letter_reversal"


def test_score_rejects_bad_input(client):
    assert say(client, "!!!", "dog").status_code == 422                      # nothing to say
    assert say(client, "dog", "dog", game="../etc").status_code == 422        # game is a file name later
    big = {"audio": ("a.webm", b"x" * 5_000_001, "audio/webm")}
    assert client.post("/score", data={"target": "dog"}, files=big).status_code == 413


def test_progress_from_recorded_attempts(client, login):
    p1 = login(client, "p1")
    say(client, "dog", "dog", p1)
    say(client, "dog", "bog", p1)
    say(client, "cat", "at", p1)
    say(client, "dog", "dog", login(client, "someone_else"))
    say(client, "dog", "dog")  # not logged in: scored, not recorded
    sessions = client.get(f"/progress/{p1[0]}", headers=p1[1]).json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["accuracy"] == 0.33
    assert sessions[0]["avg_response_ms"] is None
    assert sessions[0]["errors"] == {"letter_reversal": 1, "missing_sound": 1}
    fresh = login(client, "fresh")
    assert client.get(f"/progress/{fresh[0]}", headers=fresh[1]).json() == {"sessions": []}


@pytest.fixture
def levels(tmp_path, monkeypatch):
    (tmp_path / "word_flash.json").write_text(json.dumps({"levels": [
        {"focus": "one", "display_ms": 2000, "items": ["cat", "hat", "dad", "mat", "sat", "dig"]},
        {"focus": "two", "display_ms": 1500, "items": ["bed", "red", "pen", "net", "den", "web"]},
    ]}), encoding="utf-8")
    monkeypatch.setattr(brain, "CONTENT_DIR", tmp_path)


def result(client, target, heard):
    return say(client, target, heard).json()


def ask(client, history, who):
    pid, headers = who
    return client.post("/next-exercise", json={"player_id": pid, "game": "word_flash", "history": history},
                       headers=headers)


def test_next_exercise_levels_up_down_and_remembers(client, levels, login):
    p1 = login(client, "p1")
    first = ask(client, [], p1).json()
    assert (first["level"], first["display_ms"], first["reason"]) == (1, 2000, "one")
    assert len(first["items"]) == 5 and set(first["items"]) <= {"cat", "hat", "dad", "mat", "sat", "dig"}

    good = [result(client, w, w) for w in ("cat", "hat", "mat")]
    up = ask(client, good, p1).json()
    assert (up["level"], up["display_ms"], up["reason"]) == (2, 1500, "level up: two")
    assert ask(client, good, p1).json()["level"] == 2  # top level: stays
    assert ask(client, [], p1).json()["level"] == 2    # remembered between calls

    bad = [result(client, w, "") for w in ("bed", "red", "pen")]
    assert ask(client, bad, p1).json()["level"] == 1
    assert ask(client, [], login(client, "p2")).json()["level"] == 1  # per player


def test_next_exercise_needs_three_results_to_move(client, levels, login):
    assert ask(client, [result(client, "cat", "cat")] * 2, login(client)).json()["level"] == 1


def test_next_exercise_targets_weak_sounds(client, levels, login):
    history = [result(client, "dad", "bab"), result(client, "dig", "big"), result(client, "cat", "cat")]
    r = ask(client, history, login(client)).json()
    assert r["reason"] == "practising d"
    assert r["items"][:2] == ["dad", "dig"] or r["items"][:2] == ["dig", "dad"]  # only two level-1 words have /d/


def test_first_round_uses_recorded_weak_sounds(client, levels, login):
    p3 = login(client, "p3")
    say(client, "dad", "bab", p3)
    assert ask(client, [], p3).json()["reason"] == "practising d"
    assert ask(client, [], login(client, "p4")).json()["reason"] == "one"  # a different player, a different round


def test_next_exercise_unknown_game(client, login):
    pid, auth = login(client)
    r = client.post("/next-exercise", json={"player_id": pid, "game": "beat_reader", "history": []}, headers=auth)
    assert r.status_code == 404


def test_story_uses_llm_and_recorded_weak_sounds(client, monkeypatch, login):
    p1 = login(client)
    prompts = []

    def fake_llm(prompt):
        prompts.append(prompt)
        return json.dumps({"story": "Ben the dog.", "questions": [{"q": "Who?", "answer": "Ben"}]})

    monkeypatch.setattr(brain, "_complete", fake_llm)
    say(client, "dog", "bog", p1)
    r = client.post("/story", json={"player_id": p1[0], "weak_sounds": [], "interests": ["football"]}, headers=p1[1])
    assert r.status_code == 200 and r.json()["questions"][0]["answer"] == "Ben"
    assert "sounds (IPA symbols): d" in prompts[0] and "interests: football" in prompts[0]


def test_story_bad_llm_output_is_503(client, monkeypatch, login):
    pid, auth = login(client)
    monkeypatch.setattr(brain, "_complete", lambda prompt: "not json")
    assert client.post("/story", json={"player_id": pid}, headers=auth).status_code == 503


def test_story_without_vllm_config_is_503(client, monkeypatch, login):
    pid, auth = login(client)
    monkeypatch.delenv("VLLM_BASE_URL", raising=False)
    r = client.post("/story", json={"player_id": pid}, headers=auth)
    assert r.status_code == 503 and "not set" in r.json()["detail"]
