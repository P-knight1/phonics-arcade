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
                        "correct": False, "phoneme_accuracy": 0.67, "response_ms": None, "error_type": "letter_reversal",
                        "unclear": False}


def test_score_response_ms(client):
    import time
    r = say(client, "dog", "dog", shown_at_ms=str(int(time.time() * 1000) - 1500))
    assert 1400 <= r.json()["response_ms"] < 5000


def test_score_no_answer(client):
    for data in ({"target": "dog"}, {"target": "dog", "heard_text": ""}):  # timed out / "wrong" with empty box
        r = client.post("/score", data=data).json()
        assert (r["heard"], r["heard_phonemes"], r["error_type"]) == ("", [], "no_response")


def test_score_audio_without_speech_packages_is_503(client, monkeypatch):
    def unavailable(audio, ctype, arabic):
        raise speech.SpeechUnavailable("speech packages not installed")

    monkeypatch.setattr(speech, "recognize", unavailable)
    r = client.post("/score", data={"target": "dog"}, files={"audio": ("a.webm", b"x", "audio/webm")})
    assert r.status_code == 503


def wav(seconds):
    import io
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(b"\0\0" * int(16000 * seconds))
    return buf.getvalue()


def test_unreadable_audio_is_422(client):
    pytest.importorskip("av")
    r = client.post("/score", data={"target": "dog"}, files={"audio": ("a.webm", b"not audio", "audio/webm")})
    assert r.status_code == 422


def test_a_tap_on_the_mic_is_no_answer(client):
    pytest.importorskip("av")  # decoded, but too short to need the model
    r = client.post("/score", data={"target": "dog"}, files={"audio": ("a.wav", wav(0.1), "audio/wav")})
    assert r.json()["error_type"] == "no_response"


def test_right_answer_shows_the_target_as_heard(client, monkeypatch):
    monkeypatch.setattr(speech, "recognize", lambda audio, ctype, arabic: ("", ["d", "ɒ", "ɡ"]))
    r = client.post("/score", data={"target": "dog"}, files={"audio": ("a.webm", b"x", "audio/webm")})
    assert (r.json()["correct"], r.json()["heard"]) == (True, "dog")


def test_score_audio_uses_speech_module(client, monkeypatch):
    monkeypatch.setattr(speech, "recognize", lambda audio, ctype, arabic: ("bog", ["b", "ˈɒ", "ɡ"]))
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
    assert (up["level"], up["display_ms"], up["reason"]) == (2, 1500, "مستوى أعلى: two")
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
    assert r["reason"] == "نتدرّب على: د"
    assert r["items"][:2] == ["dad", "dig"] or r["items"][:2] == ["dig", "dad"]  # only two level-1 words have /d/


def test_first_round_uses_recorded_weak_sounds(client, levels, login):
    p3 = login(client, "p3")
    say(client, "dad", "bab", p3)
    assert ask(client, [], p3).json()["reason"] == "نتدرّب على: د"
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
    assert "والحركات: د" in prompts[0] and "الاهتمامات: football" in prompts[0]  # letters, not phoneme symbols


def test_story_must_be_vowelized(client, monkeypatch, login):
    pid, auth = login(client)
    replies = iter(["ذهب الولد إلى السوق", "ذَهَبَ الْوَلَدُ إِلَى السُّوقِ"])
    calls = []

    def fake_llm(prompt):
        calls.append(prompt)
        return json.dumps({"story": next(replies), "questions": [{"q": "مَنْ ذَهَبَ؟", "answer": "الْوَلَدُ"}]})

    monkeypatch.setattr(brain, "_complete", fake_llm)
    r = client.post("/story", json={"player_id": pid}, headers=auth)
    assert r.status_code == 200 and len(calls) == 2  # the unvowelized story was asked for again
    monkeypatch.setattr(brain, "_complete", lambda prompt: json.dumps({"story": "ذهب الولد", "questions": []}))
    assert client.post("/story", json={"player_id": pid}, headers=auth).status_code == 503


def test_vowelized_share():
    assert brain.vowelized_share("كَمْ كُرْبَةٍ ضَاقَ صَدْرِي") == 1.0
    assert brain.vowelized_share("ذهب الولد") == 0.0
    assert brain.vowelized_share("Ben the dog") == 1.0  # nothing Arabic to check


def test_story_bad_llm_output_is_503(client, monkeypatch, login):
    pid, auth = login(client)
    monkeypatch.setattr(brain, "_complete", lambda prompt: "not json")
    assert client.post("/story", json={"player_id": pid}, headers=auth).status_code == 503


def test_story_without_vllm_config_is_503(client, monkeypatch, login):
    pid, auth = login(client)
    monkeypatch.delenv("VLLM_BASE_URL", raising=False)
    r = client.post("/story", json={"player_id": pid}, headers=auth)
    assert r.status_code == 503 and "not set" in r.json()["detail"]


def test_score_arabic_heard_text(client):
    r = say(client, "حَبْل", "جَبْل").json()
    assert (r["target_phonemes"], r["heard_phonemes"], r["error_type"]) == (["H", "a", "b", "l"], ["j", "a", "b", "l"],
                                                                         "dot_confusion")


def test_score_arabic_audio_uses_the_arabic_model(client, monkeypatch):
    monkeypatch.setattr(speech, "recognize_fit", lambda audio, target: (["k", "a", "t", "i", "b"], 12.0))
    r = client.post("/score", data={"target": "كَاتِب"}, files={"audio": ("a.webm", b"x", "audio/webm")}).json()
    assert (r["target_phonemes"], r["error_type"]) == (["k", "aa", "t", "i", "b"], "vowel_length")


def test_bkt_moves_towards_the_evidence():
    p = brain.P_INIT
    assert brain.bkt(p, True) > p > brain.bkt(p, False)
    for _ in range(20):
        p = brain.bkt(p, True)
    assert 0.95 < p <= 1


def test_mastery_tracks_each_sound():
    tries = [{"target_phonemes": ["d", "a", "d"], "heard_phonemes": ["b", "a", "b"]}] * 3
    known = brain.mastery(tries)
    assert known["d"] < brain.WEAK < known["a"]


def test_practice_follows_mastery_not_one_bad_round(client, levels, login):
    p = login(client, "steady")
    for _ in range(4):
        say(client, "dig", "big", p)   # d keeps going wrong
    for _ in range(4):
        say(client, "dad", "dad", p)   # ...until it is mastered
    assert ask(client, [], p).json()["reason"] != "نتدرّب على: د"


def test_wrong_arabic_answer_shows_what_was_heard_as_letters(client, monkeypatch):
    monkeypatch.setattr(speech, "recognize_fit", lambda audio, target: (["j", "a", "b", "l"], 15.0))
    r = client.post("/score", data={"target": "حَبْلْ"}, files={"audio": ("a.webm", b"x", "audio/webm")})
    assert (r.json()["error_type"], r.json()["heard"]) == ("dot_confusion", "جَبل")


def fit(client, monkeypatch, heard, gap, auth=None, **extra):
    monkeypatch.setattr(speech, "recognize_fit", lambda audio, target: (heard, gap))
    return client.post("/score", data={"target": "قَلَمْ", "game": "word_flash", **extra},
                       files={"audio": ("a.webm", b"x", "audio/webm")}, headers=auth or {}).json()


def test_word_that_fits_is_right_despite_a_transcript_slip(client, monkeypatch, login):
    pid, auth = login(client)
    r = fit(client, monkeypatch, ["q", "a", "l", "a", "n"], 1.2, auth)
    assert (r["correct"], r["unclear"], r["heard"], r["heard_phonemes"]) == (True, False, "قَلَمْ", ["q", "a", "l", "a", "m"])
    assert brain.weakest(pid) == []  # the slip doesn't count against م


def test_borderline_reading_is_read_again_and_not_saved(client, monkeypatch, login):
    pid, auth = login(client)
    r = fit(client, monkeypatch, ["q", "a", "l", "a", "n"], 4.5, auth)
    assert (r["correct"], r["unclear"]) == (False, True)
    assert client.get(f"/progress/{pid}", headers=auth).json()["sessions"] == []
    again = fit(client, monkeypatch, ["q", "a", "l", "a", "n"], 4.5, auth, second_try="true")
    assert (again["correct"], again["unclear"], again["error_type"]) == (False, False, "substitution")
    assert client.get(f"/progress/{pid}", headers=auth).json()["sessions"][0]["errors"] == {"substitution": 1}


def test_clear_misreading_stays_wrong(client, monkeypatch):
    r = fit(client, monkeypatch, ["k", "a", "l", "a", "m"], 14.0)
    assert (r["correct"], r["unclear"]) == (False, False)


def test_built_frontend_is_served_with_the_api(tmp_path, monkeypatch):
    import importlib
    from fastapi.testclient import TestClient
    from app import main
    (tmp_path / "index.html").write_text("<html>app</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "a.js").write_text("js")
    (tmp_path.parent / "secret.txt").write_text("no")
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    try:
        c = TestClient(importlib.reload(main).app)
        assert c.get("/assets/a.js").text == "js"
        assert c.get("/games/word-flash").text == "<html>app</html>"      # browser routes get the app
        assert c.get("/../secret.txt").text != "no" and c.get("/%2e%2e/secret.txt").text != "no"
        assert c.get("/health").json()["ok"]                              # the API still wins
        page = c.get("/")
        assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
        assert page.headers["x-content-type-options"] == "nosniff"
        assert c.get("/openapi.json").text == "<html>app</html>"         # no API map on the public site
        assert "access-control-allow-origin" not in c.get("/health", headers={"Origin": "https://evil.example"}).headers
    finally:
        monkeypatch.delenv("STATIC_DIR")
        importlib.reload(main)


def test_login_attempts_are_limited_per_address(client):
    for _ in range(10):
        assert client.post("/login", json={"name": "nobody", "password": "wrong-password"}).status_code == 401
    assert client.post("/login", json={"name": "nobody", "password": "wrong-password"}).status_code == 429
    other = {"X-Forwarded-For": "203.0.113.9"}  # another caller is not blocked
    assert client.post("/login", json={"name": "nobody", "password": "wrong-password"}, headers=other).status_code == 401
