"""Pure scoring: target phonemes vs heard phonemes -> accuracy + error type. No GPU, no I/O."""
from difflib import SequenceMatcher

# Mirror-letter confusions as they show up in sound. p/q has no clean phoneme pair (q is /k/), so only b/d.
REVERSAL_PAIRS = {frozenset({"b", "d"})}


def phoneme_accuracy(target: list[str], heard: list[str]) -> float:
    if not target and not heard:
        return 1.0
    matched = sum(b.size for b in SequenceMatcher(a=target, b=heard, autojunk=False).get_matching_blocks())
    return round(matched / max(len(target), len(heard)), 2)


def error_type(target: list[str], heard: list[str]) -> str:
    if not heard:
        return "no_response"
    if heard == target:
        return "none"
    if len(target) > 1 and heard == target[::-1]:  # "was" read as "saw"
        return "letter_reversal"
    ops = [op for op in SequenceMatcher(a=target, b=heard, autojunk=False).get_opcodes() if op[0] != "equal"]
    for tag, i1, i2, j1, j2 in ops:
        if tag == "replace" and any(frozenset({t, h}) in REVERSAL_PAIRS for t, h in zip(target[i1:i2], heard[j1:j2])):
            return "letter_reversal"
    tags = {op[0] for op in ops}
    if tags == {"delete"}:
        return "missing_sound"
    if tags == {"insert"}:
        return "added_sound"
    return "substitution"


def score(target: list[str], heard: list[str]) -> dict:
    return {
        "correct": heard == target,
        "phoneme_accuracy": phoneme_accuracy(target, heard),
        "error_type": error_type(target, heard),
    }
