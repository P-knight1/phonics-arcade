import pytest

from app.scoring import missed_phonemes, normalize, score


@pytest.mark.parametrize("target, heard, correct, acc, err", [
    ("d ɒ g", "d ɒ g", True, 1.0, "none"),
    ("d ɒ g", "b ɒ g", False, 0.67, "letter_reversal"),   # contract example
    ("p a t", "t a p", False, 0.33, "letter_reversal"),   # pat -> tap
    ("k a t", "a t", False, 0.67, "missing_sound"),
    ("k a t", "k a t s", False, 0.75, "added_sound"),
    ("k a t", "k ɪ t", False, 0.67, "substitution"),
    ("k a t", "", False, 0.0, "no_response"),
])
def test_score(target, heard, correct, acc, err):
    assert score(target.split(), heard.split()) == {"correct": correct, "phoneme_accuracy": acc, "error_type": err}


def test_spelling_reversal_uses_text():
    # was = w ɒ z, saw = s ɔ: the reversal only shows in the spelling
    assert score(["w", "ɒ", "z"], ["s", "ɔ"], "was", "saw")["error_type"] == "letter_reversal"


def test_normalize():
    assert normalize(["ˈd", "ɑː", "ɡ", "|", ""]) == ["d", "ɑ", "g"]


def test_missed_phonemes():
    assert missed_phonemes(["d", "ɒ", "g"], ["b", "ɒ", "g"]) == ["d"]
    assert missed_phonemes(["k", "a", "t"], ["a", "t", "s"]) == ["k"]
    assert missed_phonemes(["k", "a", "t"], ["k", "a", "t"]) == []
