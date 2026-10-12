"""Fake but schema-valid responses for MOCK_MODE=1, so the frontend never waits on real AI."""
import random
from datetime import date, timedelta

from . import scoring

# shortcut: one letter = one phoneme, so mock mode needs no espeak. Real mode uses g2p.py.
def fake_phonemes(word: str) -> list[str]:
    return list(word.lower().replace(" ", ""))


def score(target: str, shown_at_ms: int | None, heard_text: str | None = None) -> dict:
    target_ph = fake_phonemes(target)
    heard_ph = fake_phonemes(heard_text) if heard_text is not None else random.choice([
        target_ph,                                                  # correct
        [{"b": "d", "d": "b"}.get(p, p) for p in target_ph],        # b/d swap
        target_ph[1:],                                              # dropped first sound
        target_ph + ["s"],                                          # added sound
        [],                                                         # silence
    ])
    return {
        "heard": heard_text if heard_text is not None else "".join(heard_ph),
        "target_phonemes": target_ph,
        "heard_phonemes": heard_ph,
        "response_ms": random.randint(600, 3000) if shown_at_ms is not None else None,
        **scoring.score(target_ph, heard_ph, target, heard_text or ""),
    }


def next_exercise(game: str, history: list) -> dict:
    recent = history[-5:]
    acc = sum(h.correct for h in recent) / len(recent) if recent else 0.5
    level = 3 if acc >= 0.8 else 2 if acc >= 0.5 else 1
    return {
        "game": game,
        "level": level,
        "items": random.sample(["bat", "dad", "bed", "dog", "big", "dip", "bud", "dab"], 5),
        "display_ms": {1: 2000, 2: 1500, 3: 1200}[level],
        "reason": "practising b/d",
    }


def story(weak_sounds: list[str], interests: list[str]) -> dict:
    return {
        "story": "Ben the dog had a big red ball. He ran to the bed and dug a deep den.",
        "questions": [
            {"q": "What colour was the ball?", "answer": "red"},
            {"q": "Where did Ben run?", "answer": "the bed"},
        ],
    }


def progress(player_id: str) -> dict:
    today = date.today()
    return {"sessions": [
        {
            "date": (today - timedelta(days=4 - i)).isoformat(),
            "accuracy": round(0.55 + 0.06 * i, 2),
            "avg_response_ms": 2200 - 150 * i,
            "errors": {"letter_reversal": 5 - i, "missing_sound": 3 - i // 2},
        }
        for i in range(5)
    ]}
