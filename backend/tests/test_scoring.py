import pytest

from app.scoring import missed_phonemes, normalize, score, single


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
    ("H a b l", "j a b l", "dot_confusion"),           # حَبْل read as جَبْل
    ("b aa b", "t aa b", "dot_confusion"),             # بَاب read as تَاب
    ("S a b r", "D a b r", "dot_confusion"),           # ص / ض
    ("d u bb", "d u tt", "dot_confusion"),             # shadda on both sides
    ("d u bb", "d u t", "dot_confusion"),              # ب with shadda read as plain ت: still the dots
    ("f a t a H a", "f u t a H a", "vowel_error"),     # فَتَحَ with a wrong short vowel
    ("k aa t i b", "k a t i b", "vowel_length"),       # كَاتِب read as كَتِب
    ("k i t a b", "k i t aa b", "vowel_length"),       # and the other way
    ("k a t a b a", "k a b a t a", "letter_position"),  # كَتَبَ -> كَبَتَ
    ("H a b l", "H a l b", "letter_position"),
    ("b aa b", "b aa", "missing_sound"),
    ("b aa b", "b aa b t", "added_sound"),
    ("q a l a m", "k a l a m", "substitution"),        # not a dot pair
    ("b aa b", "d aa b", "substitution"),              # b/d is only a reversal in English
    ("d u bb", "d u b", "substitution"),               # shadda dropped
    ("b aa b", "b ii b", "substitution"),              # long vowels are letters (ا / ي)
])
def test_arabic_error_types(target, heard, err):
    assert score(target.split(), heard.split(), "كَلِمَة")["error_type"] == err


@pytest.mark.parametrize("target, heard", [
    ("k a t a b", "k a t a b a"),      # كَتَبَ read in full instead of in pause
    ("k i t aa b", "k i t aa b u n"),  # كِتَابٌ with its tanwin
    ("k i t aa b", "k i t aa b"),
])
def test_arabic_final_vowel_is_optional(target, heard):
    assert score(target.split(), heard.split(), "كَلِمَة")["correct"]


def test_arabic_final_vowel_tolerance_is_narrow():
    assert score("m i n".split(), "m i".split(), "مِنْ")["error_type"] == "missing_sound"
    assert score("b aa b".split(), "b aa t a".split(), "بَاب")["error_type"] == "dot_confusion"
    assert score("d a r s".split(), "d a r s a".split(), "dars")["error_type"] == "added_sound"  # English: no pause rule


def test_arabic_precedence():
    # swapped letters beat dot_confusion; dot_confusion beats vowel_error
    assert score("t a b".split(), "b a t".split(), "تَب")["error_type"] == "letter_position"  # not dot_confusion
    assert score("k a t a b".split(), "b a t a k".split(), "كَتَب")["error_type"] == "substitution"  # too far apart
    assert score("b a t a".split(), "t i t a".split(), "بَتَ")["error_type"] == "dot_confusion"


def test_english_unchanged_without_arabic_text():
    assert score("H a b l".split(), "j a b l".split(), "")["error_type"] == "substitution"


def test_normalize_leaves_arabic_symbols_alone():
    assert normalize(["k", "aa", "t", "bb", "$", "^", "<", "*"]) == ["k", "aa", "t", "bb", "$", "^", "<", "*"]


def test_single():
    assert [single(p) for p in ("bb", "b", "aa", "$$")] == ["b", "b", "aa", "$"]


def test_missed_phonemes_and_weak_sounds_arabic():
    from app.brain import weak_sounds
    assert missed_phonemes(["k", "aa", "t", "i", "b"], ["k", "a", "t", "i", "b"]) == ["aa"]
    results = [{"correct": False, "target_phonemes": t.split(), "heard_phonemes": h.split()}
               for t, h in [("H a b l", "j a b l"), ("H a j a r", "x a j a r"), ("b aa b", "b a b")]]
    assert weak_sounds(results) == ["H", "aa"]


def test_every_dot_letter_sound_has_a_letter_to_show():
    from app.brain import LETTER_FOR
    from app.scoring import DOT_FAMILIES
    assert set().union(*DOT_FAMILIES) <= LETTER_FOR.keys()


def test_letters_shown_for_sounds():
    from app.brain import letter
    assert [letter(p) for p in ("H", "bb", "aa", "a", "?")] == ["ح", "بّ", "ا", "الفتحة", "?"]
