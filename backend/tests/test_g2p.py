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
    # Arabic goes through app/arabic_phonemes.py (its own self-check covers the reading rules)
    ("بَاب", "b aa b"), ("كَتَبَ", "k a t a b"), ("كَاتِب", "k aa t i b"),   # last word read in pause
    ("حَبْل", "H a b l"), ("ثَوْب", "^ a w b"), ("ذَهَب", "* a h a b"), ("شَمْس", "$ a m s"),
    ("صَبَرَ", "S a b a r"), ("ضَرَبَ", "D a r a b"), ("طِين", "T ii n"), ("ظُفْر", "Z u f r"),
    ("سُكَّر", "s u kk a r"),                                    # shadda = doubled symbol
    ("كِتَابٌ", "k i t aa b"),                                    # tanwin dropped in pause
    ("الشَّمْسُ", "< a $$ a m s"),                                # sun letter
])
def test_arabic(word, expected):
    assert g2p.phonemes(word) == tuple(expected.split())


def test_arabic_converter_matches_ml_copy():
    from pathlib import Path
    ml = Path(__file__).resolve().parents[2] / "ml" / "arabic_phonemes.py"
    if ml.exists():  # the backend copy must stay identical to the one the model was trained with
        assert ml.read_bytes() == (Path(g2p.__file__).parent / "arabic_phonemes.py").read_bytes()
