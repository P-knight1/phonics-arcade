"""Pure scoring: target phonemes vs heard phonemes -> accuracy + error type. No GPU, no I/O."""
import re
from difflib import SequenceMatcher

ARABIC = re.compile(r"[\u0621-\u064a]")  # Arabic letters (hamza to yeh), not the vowel marks
# English: mirror-letter confusions as they show up in sound. p/q has no clean phoneme pair (q is /k/), so only b/d.
REVERSAL_PAIRS = {frozenset({"b", "d"})}
# Arabic letters that differ only by dots, in our Arabic symbol set (app/arabic_phonemes.py):
# ب ت ث، ج ح خ، د ذ، ر ز، س ش، ص ض، ط ظ، ع غ، ف ق.
DOT_FAMILIES = [{"b", "t", "^"}, {"j", "H", "x"}, {"d", "*"}, {"r", "z"}, {"s", "$"}, {"S", "D"}, {"T", "Z"}, {"E", "g"},
                {"f", "q"}]
SHORT_VOWELS = {"a", "i", "u"}
LONG_VOWELS = {"aa", "ii", "uu"}
# English only: stress, length and word-break marks; the phoneme model and espeak disagree on these.
_STRIP = str.maketrans("", "", "ˈˌː|")


def is_arabic(text: str) -> bool:
    return bool(ARABIC.search(text))


def normalize(phonemes) -> list[str]:
    """English: make target (espeak) and heard (phoneme model) phonemes comparable. Arabic symbols need nothing."""
    out = []
    for p in phonemes:
        p = p.translate(_STRIP).replace("ɡ", "g")  # espeak's IPA ɡ vs plain g
        if p:
            out.append(p)
    return out


def _diffs(target: list[str], heard: list[str]):
    return [op for op in SequenceMatcher(a=target, b=heard, autojunk=False).get_opcodes() if op[0] != "equal"]


def changes(target: list[str], heard: list[str]) -> list[tuple[str, list[str], list[str]]]:
    """[(tag, target part, heard part)] for every difference: tag is replace, delete or insert."""
    return [(tag, target[i1:i2], heard[j1:j2]) for tag, i1, i2, j1, j2 in _diffs(target, heard)]


def phoneme_accuracy(target: list[str], heard: list[str]) -> float:
    if not target and not heard:
        return 1.0
    matched = sum(b.size for b in SequenceMatcher(a=target, b=heard, autojunk=False).get_matching_blocks())
    return round(matched / max(len(target), len(heard)), 2)


def missed_phonemes(target: list[str], heard: list[str]) -> list[str]:
    """Target sounds the player dropped or replaced: the sounds to practise."""
    return [p for tag, i1, i2, _, _ in _diffs(target, heard) if tag in ("replace", "delete") for p in target[i1:i2]]


def single(p: str) -> str:
    """'bb' (shadda) -> 'b'. Long vowels ('aa') are not shadda and stay."""
    return p[0] if len(p) == 2 and p[0] == p[1] and p not in LONG_VOWELS else p


def _dot_pair(a: str, b: str) -> bool:
    pair = {single(a), single(b)}  # ب read as تّ is still a dot confusion
    return len(pair) == 2 and any(pair <= f for f in DOT_FAMILIES)


def _letters_swapped(target: list[str], heard: list[str]) -> bool:
    """Two neighbouring sounds swapped: side by side, or across the vowel between them (كَتَبَ read as كَبَتَ)."""
    diff = [i for i, (a, b) in enumerate(zip(target, heard)) if a != b]
    return (len(target) == len(heard) and len(diff) == 2 and diff[1] - diff[0] <= 2
            and target[diff[0]] == heard[diff[1]] and target[diff[1]] == heard[diff[0]])


def error_type(target: list[str], heard: list[str], target_text: str = "", heard_text: str = "") -> str:
    """Most specific first. English: letter_reversal. Arabic (target_text in Arabic letters): letter_position,
    dot_confusion, vowel_length, vowel_error. Then for both: missing_sound, added_sound, substitution."""
    if not heard:
        return "no_response"
    if heard == target:
        return "none"
    ops = _diffs(target, heard)
    pairs = [(a, b) for tag, i1, i2, j1, j2 in ops if tag == "replace" for a, b in zip(target[i1:i2], heard[j1:j2])]
    if is_arabic(target_text):
        if _letters_swapped(target, heard):
            return "letter_position"
        if any(_dot_pair(a, b) for a, b in pairs):
            return "dot_confusion"
        if any(a != b and a[0] == b[0] and {a, b} <= SHORT_VOWELS | LONG_VOWELS for a, b in pairs):  # a <-> aa
            return "vowel_length"
        if any(a != b and {a, b} <= SHORT_VOWELS for a, b in pairs):
            return "vowel_error"
    else:
        t, h = target_text.strip().lower(), heard_text.strip().lower()
        if len(t) > 1 and h == t[::-1]:  # "was" read as "saw": a spelling reversal, invisible in sounds
            return "letter_reversal"
        if len(target) > 1 and heard == target[::-1]:  # "pat" read as "tap"
            return "letter_reversal"
        if any(frozenset({a, b}) in REVERSAL_PAIRS for a, b in pairs):
            return "letter_reversal"
    tags = {op[0] for op in ops}
    if tags == {"delete"}:
        return "missing_sound"
    if tags == {"insert"}:
        return "added_sound"
    return "substitution"


def _without_final_vowel(target: list[str], heard: list[str]) -> list[str]:
    """Arabic targets end in pause (كَتَبَ -> k a t a b); reading the final vowel or tanwin in full is right too."""
    if target and target[-1] not in SHORT_VOWELS:
        for n in (2, 1):  # vowel + n (tanwin), then a lone vowel
            tail = heard[-n:]
            if len(heard) > n and heard[-n - 1] == target[-1] and tail[0] in SHORT_VOWELS and tail[1:] == ["n"][:n - 1]:
                return heard[:-n]
    return heard


def _without_cluster_vowel(target: list[str], heard: list[str]) -> list[str]:
    """A word ending in two consonants (حَبْلْ -> H a b l): speakers slip a short vowel between them (حَبِل).
    That is how the cluster is said, not a reading mistake."""
    vowels = SHORT_VOWELS | LONG_VOWELS
    if (len(target) >= 2 and len(heard) == len(target) + 1 and not {target[-2], target[-1]} & vowels
            and heard[-1] == target[-1] and heard[-3] == target[-2] and heard[-2] in SHORT_VOWELS):
        return heard[:-2] + heard[-1:]
    return heard


# How much worse the target fits the recording than the model's own reading (speech.recognize_fit), in nats.
# Calibrated on 300 Iqra'Eval dev recordings: at 3, 83% of right readings the model transcribed with one slip pass
# and no one-sound misreading did; between 3 and 6 some misreadings (mostly vowels) and the rest of the slips mix,
# so the player is asked to read again rather than told they were wrong.
FIT_RIGHT, FIT_UNSURE = 3.0, 6.0


def score(target: list[str], heard: list[str], target_text: str = "", heard_text: str = "",
          gap: float | None = None) -> dict:
    if is_arabic(target_text):
        heard = _without_cluster_vowel(target, _without_final_vowel(target, heard))
    if heard and heard != target and gap is not None and gap <= FIT_RIGHT:
        heard = target  # the recording fits the word: the transcript's difference is the model's slip
    return {
        "correct": heard == target,
        "phoneme_accuracy": phoneme_accuracy(target, heard),
        "error_type": error_type(target, heard, target_text, heard_text),
        "unclear": bool(heard) and heard != target and gap is not None and gap <= FIT_UNSURE,
    }
