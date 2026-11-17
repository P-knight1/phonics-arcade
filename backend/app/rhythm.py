"""Rhythmic Reading: one recording of several words read on a beat -> a score and a timing for each word.

The whole run is aligned once against all the words, so a slip in one word doesn't shift the others. No I/O."""
from difflib import SequenceMatcher
from statistics import pstdev

from . import scoring

# Mic test runs showed onsets up to ~75 ms before the beat: people following a steady beat anticipate it, and
# timestamps come in 20 ms frames. Speaking on the beat is the goal, so an onset that close counts as on time.
EARLY_MS = 100


def split_heard(targets: list[list[str]], heard: list[str]) -> list[list[int]]:
    """For each target word, the indices of the heard phonemes that belong to it."""
    owner_of_target = [w for w, phonemes in enumerate(targets) for _ in phonemes]
    flat = [p for phonemes in targets for p in phonemes]
    owner: list[int | None] = [None] * len(heard)
    for tag, i1, i2, j1, j2 in SequenceMatcher(a=flat, b=heard, autojunk=False).get_opcodes():
        for j in range(j1, j2):
            if tag == "equal":
                i = i1 + j - j1
            elif tag == "replace":  # spread the heard sounds over the target sounds they replace
                i = i1 + (j - j1) * (i2 - i1) // (j2 - j1)
            else:  # insert: an extra sound belongs with the sound before it (a final vowel read in full)
                i = max(i1 - 1, 0)
            owner[j] = owner_of_target[min(i, len(flat) - 1)] if flat else None
    return [[j for j, o in enumerate(owner) if o == w] for w in range(len(targets))]


def score_run(texts: list[str], targets: list[list[str]], heard: list[str], starts_ms: list[int] | None = None,
              slot_ms: int = 0, first_word_ms: int = 0) -> dict:
    """starts_ms: when each heard phoneme began (from speech.recognize_timed); None for typed answers.
    Word k is shown at first_word_ms + k * slot_ms and should be read before the next word appears."""
    words = []
    for k, (text, target, idx) in enumerate(zip(texts, targets, split_heard(targets, heard))):
        said = [heard[j] for j in idx]
        offset = None if starts_ms is None or not idx else starts_ms[idx[0]] - (first_word_ms + k * slot_ms)
        result = scoring.score(target, said, text)
        words.append({
            "target": text,
            "heard": text if result["correct"] else "",
            "target_phonemes": target,
            "heard_phonemes": said,
            "response_ms": None if offset is None else max(0, offset),
            "offset_ms": offset,  # from the moment the word appeared; negative = said before it showed
            "on_time": None if offset is None else -EARLY_MS <= offset < slot_ms,
            **result,
        })
    offsets = [w["offset_ms"] for w in words if w["offset_ms"] is not None]
    # How evenly spaced the words were: the spread of their delays. Lower is steadier.
    return {"words": words, "steadiness_ms": round(pstdev(offsets)) if len(offsets) >= 2 else None}
