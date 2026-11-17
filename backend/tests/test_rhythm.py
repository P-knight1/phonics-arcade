import json

from app import g2p, rhythm, speech

WORDS = ["بَابْ", "حَبْلْ", "قَمَرْ"]
TARGETS = [list(g2p.phonemes(w)) for w in WORDS]


def run(said: str, **timing):
    return rhythm.score_run(WORDS, TARGETS, list(g2p.phonemes(said)), **timing)


def test_each_word_gets_its_own_verdict():
    words = run("بَابْ جَبْلْ قَمَرْ")["words"]
    assert [w["error_type"] for w in words] == ["none", "dot_confusion", "none"]
    assert [w["correct"] for w in words] == [True, False, True]


def test_a_missing_word_does_not_shift_the_others():
    words = run("بَابْ قَمَرْ")["words"]
    assert [w["error_type"] for w in words] == ["none", "no_response", "none"]


def test_final_vowels_read_in_full_stay_with_their_word():
    words = run("بَابُ حَبْلُ قَمَرُ")["words"]
    assert all(w["correct"] for w in words)


def test_timing_on_the_beat():
    heard = list(g2p.phonemes("بَابْ حَبْلْ قَمَرْ"))
    # word k appears at 2000 + 1500k; the reader starts 300, 400 and 1700 ms after each word appears
    starts = [2300, 2400, 2500, 3900, 4000, 4100, 4200, 6700, 6800, 6900, 7000, 7100]
    out = rhythm.score_run(WORDS, TARGETS, heard, starts, slot_ms=1500, first_word_ms=2000)
    assert [w["offset_ms"] for w in out["words"]] == [300, 400, 1700]
    assert [w["on_time"] for w in out["words"]] == [True, True, False]  # the last one spilled into the next slot
    assert out["steadiness_ms"] == 638  # spread of 300, 400, 1700


def test_typed_answers_have_no_timing():
    out = run("بَابْ حَبْلْ قَمَرْ")
    assert out["steadiness_ms"] is None and all(w["on_time"] is None for w in out["words"])


def test_silence():
    assert all(w["error_type"] == "no_response" for w in run("")["words"])


def post(client, said=None, auth=None, **extra):
    data = {"targets": json.dumps(WORDS, ensure_ascii=False), "slot_ms": 1500, "first_word_ms": 2000, **extra}
    if said is not None:
        data["heard_text"] = said
    return client.post("/score-rhythm", data=data, headers=auth or {})


def test_score_rhythm_typed_and_saved(client, login):
    pid, auth = login(client)
    r = post(client, "بَابْ جَبْلْ قَمَرْ", auth)
    assert r.status_code == 200
    assert [w["error_type"] for w in r.json()["words"]] == ["none", "dot_confusion", "none"]
    days = client.get(f"/progress/{pid}?game=rhythmic_reading", headers=auth).json()["sessions"]
    assert days[0]["errors"] == {"dot_confusion": 1}


def test_score_rhythm_audio_uses_timed_model(client, monkeypatch):
    heard = list(g2p.phonemes("بَابْ حَبْلْ قَمَرْ"))
    monkeypatch.setattr(speech, "recognize_timed", lambda audio, arabic: [(p, 2300 + 100 * i) for i, p in enumerate(heard)])
    r = client.post("/score-rhythm", data={"targets": json.dumps(WORDS), "slot_ms": 1500, "first_word_ms": 2000},
                    files={"audio": ("run.webm", b"x" * 100, "audio/webm")})
    words = r.json()["words"]
    assert all(w["correct"] for w in words) and words[0]["offset_ms"] == 300


def test_score_rhythm_rejects_bad_targets(client):
    assert post(client, "x", targets="not json").status_code == 422
    assert post(client, "x", targets=json.dumps(["بَابْ"] * 9)).status_code == 422


def test_score_rhythm_mock(mock_client):
    r = post(mock_client, "بَابْ")
    assert r.status_code == 200 and len(r.json()["words"]) == 3


def test_timing_test_returns_raw_sounds(client, monkeypatch):
    monkeypatch.setattr(speech, "recognize_timed", lambda audio: [("b", 1020), ("aa", 1080)])
    r = client.post("/timing-test", files={"audio": ("t.webm", b"x" * 100, "audio/webm")})
    assert r.json() == {"sounds": [{"phoneme": "b", "ms": 1020}, {"phoneme": "aa", "ms": 1080}], "heard_text": "بَا"}


def test_timing_test_real_words(client, monkeypatch):
    heard = list(g2p.phonemes("بَابْ جَبْلْ"))
    monkeypatch.setattr(speech, "recognize_timed", lambda audio: [(p, 2200 + 100 * i) for i, p in enumerate(heard)])
    r = client.post("/timing-test", data={"targets": json.dumps(["بَابْ", "حَبْلْ"]), "slot_ms": 2000, "first_word_ms": 2000},
                    files={"audio": ("t.webm", b"x" * 100, "audio/webm")})
    words = r.json()["words"]
    assert [w["heard_text"] for w in words] == ["بَاب", "جَبل"]
    assert [w["error_type"] for w in words] == ["none", "dot_confusion"]


def test_spell_round_trips_sounds():
    assert g2p.spell(["k", "i", "t", "aa", "b"]) == "كِتَاب"
    assert g2p.spell(["$$", "a", "m", "s"]) == "شَّمس"  # shadda, then fatha


def test_onset_just_before_the_word_counts_as_on_time():
    texts = ["بَابْ", "حَبْلْ"]
    targets = [list(g2p.phonemes(w)) for w in texts]
    heard = [p for t in targets for p in t]
    starts = [1950] * len(targets[0]) + [3300] * len(targets[1])  # word 1 heard 50 ms early, word 2 200 ms early
    out = rhythm.score_run(texts, targets, heard, starts, slot_ms=1500, first_word_ms=2000)
    assert [w["on_time"] for w in out["words"]] == [True, False]
