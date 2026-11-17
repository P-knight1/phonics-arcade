import json

import pytest

from app import brain, g2p


def attempt(target, said, error_type, correct=False):
    return {"target": target, "target_phonemes": list(g2p.phonemes(target.split("|")[-1])),
            "heard_phonemes": list(g2p.phonemes(said)), "correct": correct, "error_type": error_type}


@pytest.fixture
def llm(monkeypatch):
    """Replaces the LLM; records prompts. Set llm.reply to change the answer."""
    class Fake:
        reply = json.dumps({"text": "انْظُرْ إِلَى النُّقَطِ."})
        prompts = []

        def __call__(self, prompt, schema=None):
            self.prompts.append(prompt)
            return self.reply
    fake = Fake()
    monkeypatch.setattr(brain, "_complete", fake)
    return fake


def ask(client, auth, pid, kind, attempts):
    return client.post("/coach", json={"player_id": pid, "kind": kind, "attempts": attempts}, headers=auth)


def test_what_happened_names_letters_not_symbols():
    assert brain.what_happened(attempt("حَبْلْ", "جَبْلْ", "dot_confusion")) == "قُرئ ح كأنه ج"
    assert brain.what_happened(attempt("كَتَبَ", "كَبَتَ", "letter_position")) == "تبادل ت وب مكانيهما"
    assert brain.what_happened(attempt("قَلَمْ", "قَمْ", "missing_sound")) == "سقط ل الفتحة"
    assert brain.what_happened(attempt("قَلَمْ", "قَلَمْ", "none", correct=True)) == "قرأها صحيحة"


def test_word_coach_prompt_carries_the_mistake(client, login, llm):
    pid, auth = login(client)
    r = ask(client, auth, pid, "word", [attempt("حَبْلْ", "جَبْلْ", "dot_confusion")])
    assert r.status_code == 200 and r.json() == {"text": "انْظُرْ إِلَى النُّقَطِ."}
    assert "حَبْلْ: قُرئ ح كأنه ج (حرفان يختلفان بالنقاط)" in llm.prompts[0]
    assert " H " not in llm.prompts[0]  # no phoneme symbols reach the LLM


def test_round_coach_lists_every_attempt(client, login, llm):
    pid, auth = login(client)
    attempts = [attempt("قَمَرْ", "قَمَرْ", "none", correct=True), attempt("قُلْ «دَرَسَ» بِدُونِ «دَ»|رَسْ", "دَرَسْ", "added_sound")]
    assert ask(client, auth, pid, "round", attempts).status_code == 200
    assert "- قَمَرْ: قرأها صحيحة" in llm.prompts[0] and "- رَسْ: أُضيف د الفتحة" in llm.prompts[0]


@pytest.mark.parametrize("reply", [
    "not json",
    json.dumps({"text": ""}),
    json.dumps({"text": "Look at the dots."}),            # not Arabic
    json.dumps({"text": "هذا يدل على اضطراب في القراءة."}),  # clinical wording
    json.dumps({"text": "انظر " * 100}),                   # too long
])
def test_bad_coach_text_is_503(client, login, llm, reply):
    pid, auth = login(client)
    llm.reply = reply
    assert ask(client, auth, pid, "word", [attempt("حَبْلْ", "جَبْلْ", "dot_confusion")]).status_code == 503


def test_coach_needs_own_login(client, login):
    pid, auth = login(client)
    other, _ = login(client, "p2")
    body = [attempt("حَبْلْ", "جَبْلْ", "dot_confusion")]
    assert client.post("/coach", json={"player_id": pid, "kind": "word", "attempts": body}).status_code == 401
    assert ask(client, auth, other, "word", body).status_code == 403


def test_coach_mock_mode(mock_client, login):
    pid, auth = login(mock_client)
    r = ask(mock_client, auth, pid, "round", [attempt("حَبْلْ", "جَبْلْ", "dot_confusion")])
    assert r.status_code == 200 and g2p.is_arabic(r.json()["text"])
