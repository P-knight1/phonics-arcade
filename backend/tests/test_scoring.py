import pytest

from app.scoring import score


@pytest.mark.parametrize("target, heard, correct, acc, err", [
    ("d ɒ g", "d ɒ g", True, 1.0, "none"),
    ("d ɒ g", "b ɒ g", False, 0.67, "letter_reversal"),   # contract example
    ("w ɒ z", "z ɒ w", False, 0.33, "letter_reversal"),   # was -> saw
    ("k æ t", "æ t", False, 0.67, "missing_sound"),
    ("k æ t", "k æ t s", False, 0.75, "added_sound"),
    ("k æ t", "k ɪ t", False, 0.67, "substitution"),
    ("k æ t", "", False, 0.0, "no_response"),
])
def test_score(target, heard, correct, acc, err):
    assert score(target.split(), heard.split()) == {"correct": correct, "phoneme_accuracy": acc, "error_type": err}
