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
        "items": random.sample(["بَاب", "تَاج", "ثَوْب", "جَمَل", "حَبْل", "خُبْز", "دَار", "ذَهَب"], 5),
        "display_ms": {1: 2000, 2: 1500, 3: 1200}[level],
        "reason": "نتدرّب على: ب / ت / ث",
    }


def story(weak_sounds: list[str], interests: list[str]) -> dict:
    return {
        "story": "ذَهَبَ سَامِي إِلَى البَحْرِ. رَأَى سَمَكَةً كَبِيرَةً. فَرِحَ سَامِي كَثِيرًا.",
        "questions": [
            {"q": "إِلَى أَيْنَ ذَهَبَ سَامِي؟", "answer": "البَحْر"},
            {"q": "مَاذَا رَأَى سَامِي؟", "answer": "سَمَكَة"},
        ],
    }


def score_rhythm(texts: list[str], slot_ms: int) -> dict:
    words = []
    for text in texts:
        offset = random.randint(150, slot_ms + 300)
        words.append({**score(text, None), "target": text, "offset_ms": offset, "on_time": offset < slot_ms,
                      "response_ms": offset})
    return {"words": words, "steadiness_ms": random.randint(80, 400)}


def coach(kind: str) -> dict:
    if kind == "round":
        return {"text": "أَحْسَنْتَ فِي أَغْلَبِ الْكَلِمَاتِ. نَتَدَرَّبُ بَعْدَ ذَلِكَ عَلَى الْحُرُوفِ الَّتِي تَخْتَلِفُ بِالنُّقَطِ."}
    return {"text": "انْظُرْ إِلَى النُّقَطِ: الْجِيمُ لَهَا نُقْطَةٌ تَحْتَهَا، وَالْحَاءُ بِلَا نُقَطٍ."}


def progress(player_id: str) -> dict:
    today = date.today()
    return {"sessions": [
        {
            "date": (today - timedelta(days=4 - i)).isoformat(),
            "accuracy": round(0.55 + 0.06 * i, 2),
            "phoneme_accuracy": round(0.7 + 0.05 * i, 2),
            "avg_response_ms": 2200 - 150 * i,
            "errors": {"dot_confusion": 5 - i, "vowel_error": 4 - i, "missing_sound": 3 - i // 2},
        }
        for i in range(5)
    ]}
