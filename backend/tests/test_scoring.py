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


@pytest.mark.parametrize("target, heard, err", [
    ("ħ a b l", "dʒ a b l", "dot_confusion"),          # حَبْل read as جَبْل
    ("b aː b", "t aː b", "dot_confusion"),             # بَاب read as تَاب
    ("s̪ a. b r", "dˤ a. b r", "dot_confusion"),        # ص / ض
    ("d u bː", "d u tː", "dot_confusion"),             # shadda kept on both sides
    ("f a t a ħ a", "f u t a ħ a", "vowel_error"),     # فَتَحَ with a wrong short vowel
    ("k aː t i b", "k a t i b", "vowel_length"),       # كَاتِب read as كَتِب
    ("t̪ a.ː r a", "t̪ a. r a", "vowel_length"),         # emphatic long a
    ("k a t a b a", "k a b a t a", "letter_position"),  # كَتَبَ -> كَبَتَ
    ("ħ a b l", "ħ a l b", "letter_position"),
    ("b aː b", "b aː", "missing_sound"),
    ("b aː b", "b aː b a", "added_sound"),
    ("q a l a m", "k a l a m", "substitution"),        # not a dot pair
    ("b aː b", "d aː b", "substitution"),              # b/d is only a reversal in English
    ("b u", "b u.", "substitution"),                   # emphasis only, not a vowel error
    ("d u bː", "d u b", "substitution"),               # shadda dropped
    ("b aː b", "b iː b", "substitution"),              # long vowels are letters (ا / ي)
])
def test_arabic_error_types(target, heard, err):
    assert score(target.split(), heard.split(), "كَلِمَة")["error_type"] == err


def test_arabic_precedence():
    # swapped letters beat dot_confusion; dot_confusion beats vowel_error
    assert score("t a b".split(), "b a t".split(), "تَب")["error_type"] == "letter_position"  # not dot_confusion
    assert score("k a t a b".split(), "b a t a k".split(), "كَتَب")["error_type"] == "substitution"  # too far apart
    assert score("b a t a".split(), "t i t a".split(), "بَتَ")["error_type"] == "dot_confusion"


def test_english_unchanged_without_arabic_text():
    assert score("ħ a b l".split(), "dʒ a b l".split(), "")["error_type"] == "substitution"


def test_normalize_keeps_length_for_arabic():
    assert normalize(["k", "aː", "t", "|", "bː"], keep_length=True) == ["k", "aː", "t", "bː"]


def test_missed_phonemes_and_weak_sounds_arabic():
    from app.brain import weak_sounds
    assert missed_phonemes(["k", "aː", "t", "i", "b"], ["k", "a", "t", "i", "b"]) == ["aː"]
    results = [{"correct": False, "target_phonemes": t.split(), "heard_phonemes": h.split()}
               for t, h in [("ħ a b l", "dʒ a b l"), ("ħ a dʒ a r", "χ a dʒ a r"), ("b aː b", "b a b")]]
    assert weak_sounds(results) == ["ħ", "aː"]


def test_every_dot_letter_sound_has_a_letter_to_show():
    from app.brain import LETTER_FOR
    from app.scoring import DOT_FAMILIES
    assert set().union(*DOT_FAMILIES) <= LETTER_FOR.keys()
