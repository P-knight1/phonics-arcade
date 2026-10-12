"""Pure scoring: target phonemes vs heard phonemes -> accuracy + error type. No GPU, no I/O."""
from difflib import SequenceMatcher

# Mirror-letter confusions as they show up in sound. p/q has no clean phoneme pair (q is /k/), so only b/d.
REVERSAL_PAIRS = {frozenset({"b", "d"})}
# Stress, length and word-break marks: the phoneme model and espeak disagree on these, the player can't hear them.
_STRIP = str.maketrans("", "", "ˈˌː|")


def normalize(phonemes) -> list[str]:
    """Make target (espeak) and heard (phoneme model) phonemes comparable."""
    out = []
    for p in phonemes:
        p = p.translate(_STRIP).replace("ɡ", "g")  # espeak's IPA ɡ vs plain g
        if p:
            out.append(p)
    return out


def _diffs(target: list[str], heard: list[str]):
    return [op for op in SequenceMatcher(a=target, b=heard, autojunk=False).get_opcodes() if op[0] != "equal"]


def phoneme_accuracy(target: list[str], heard: list[str]) -> float:
    if not target and not heard:
        return 1.0
    matched = sum(b.size for b in SequenceMatcher(a=target, b=heard, autojunk=False).get_matching_blocks())
    return round(matched / max(len(target), len(heard)), 2)


def missed_phonemes(target: list[str], heard: list[str]) -> list[str]:
    """Target sounds the player dropped or replaced: the sounds to practise."""
    return [p for tag, i1, i2, _, _ in _diffs(target, heard) if tag in ("replace", "delete") for p in target[i1:i2]]


def error_type(target: list[str], heard: list[str], target_text: str = "", heard_text: str = "") -> str:
    if not heard:
        return "no_response"
    if heard == target:
        return "none"
    t, h = target_text.strip().lower(), heard_text.strip().lower()
    if len(t) > 1 and h == t[::-1]:  # "was" read as "saw": a spelling reversal, invisible in sounds
        return "letter_reversal"
    if len(target) > 1 and heard == target[::-1]:  # "pat" read as "tap"
        return "letter_reversal"
    ops = _diffs(target, heard)
    for tag, i1, i2, j1, j2 in ops:
        if tag == "replace" and any(frozenset({a, b}) in REVERSAL_PAIRS for a, b in zip(target[i1:i2], heard[j1:j2])):
            return "letter_reversal"
    tags = {op[0] for op in ops}
    if tags == {"delete"}:
        return "missing_sound"
    if tags == {"insert"}:
        return "added_sound"
    return "substitution"


def score(target: list[str], heard: list[str], target_text: str = "", heard_text: str = "") -> dict:
    return {
        "correct": heard == target,
        "phoneme_accuracy": phoneme_accuracy(target, heard),
        "error_type": error_type(target, heard, target_text, heard_text),
    }
