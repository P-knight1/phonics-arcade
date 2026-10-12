from app import g2p


def test_matches_contract_example():
    assert g2p.phonemes("dog") == ("d", "ɒ", "g")


def test_multi_letter_phonemes_stay_whole():
    assert g2p.phonemes("chip") == ("tʃ", "ɪ", "p")


def test_punctuation_and_empty():
    assert g2p.phonemes("dog!") == g2p.phonemes("dog")
    assert g2p.phonemes("") == ()
