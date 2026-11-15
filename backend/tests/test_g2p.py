import pytest

from app import g2p


def test_matches_contract_example():
    assert g2p.phonemes("dog") == ("d", "ɒ", "g")


def test_multi_letter_phonemes_stay_whole():
    assert g2p.phonemes("chip") == ("tʃ", "ɪ", "p")


def test_punctuation_and_empty():
    assert g2p.phonemes("dog!") == g2p.phonemes("dog")
    assert g2p.phonemes("") == ()


@pytest.mark.parametrize("word, expected", [
    # espeak-ng 'ar' output, as checked by hand. Length (ː) is kept for Arabic.
    ("بَاب", "b aː b"), ("كَتَبَ", "k a t a b a"), ("كَاتِب", "k aː t i b"),
    ("تَاج", "t aː dʒ"), ("ثَوْب", "θ a u b"),                    # ت ث; و after fatha is a diphthong "a u"
    ("جَمَل", "dʒ a m a l"), ("حَبْل", "ħ a b l"), ("خُبْز", "χ u b z"),
    ("ذَهَب", "ð a h a b"), ("رَمْل", "r a m l"), ("زَيْت", "z a i t"), ("شَمْس", "ʃ a m s"),
    ("عَيْن", "ʕ a i n"), ("غَيْم", "ɣ a i m"), ("قَلَم", "q a l a m"), ("فِيل", "f iː l"), ("نُور", "n uː r"),
    # emphatics: the vowel after them is marked with "."; ظ is ð like ذ
    ("صَبَرَ", "s̪ a. b a r a"), ("ضَرَبَ", "dˤ a. r a b a"), ("طِين", "t̪ i.ː n"), ("ظُفْر", "ð u. f r"),
    ("سُكَّر", "s u kː a r"), ("حَمَّام", "ħ a m m aː m"),          # shadda: sometimes ː, sometimes doubled
    ("كِتَابٌ", "k i t aː b u n"), ("قَلَمًا", "q a l a m a n"),    # tanween
    ("مَدْرَسَة", "m a d r a s a t"),                              # taa marbuta always t
    ("اَلْقَمَرُ", "ʔ a l q a m a r u"), ("الشَّمْسُ", "ʔ a ʃ ʃ a m s u"),  # moon / sun letter (alif lam unmarked)
    ("فَأْر", "f a ʔ r"),
])
def test_arabic(word, expected):
    assert g2p.phonemes(word) == tuple(expected.split())


def test_arabic_vowel_before_shadda_is_kept():
    # espeak drops the fatha when it is typed before the shadda (the Unicode NFC order); g2p reorders it
    shadda_first = "سُكّ" + "َ" + "ر"
    vowel_first = "سُك" + "َ" + "ّ" + "ر"
    assert g2p.phonemes(vowel_first) == g2p.phonemes(shadda_first) == ("s", "u", "kː", "a", "r")
