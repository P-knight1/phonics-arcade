"""The adaptive brain.

Next exercise: plain rules over the content word lists (testable, never invents words outside the phonics
progression). Stories: an LLM behind any OpenAI-compatible API (vLLM, a hosted service, ...).
"""
import json
import os
import random
from collections import Counter
from pathlib import Path
from string import Template

from openai import BadRequestError, OpenAI, OpenAIError
from pydantic import ValidationError

from . import db, g2p
from .arabic_phonemes import LETTERS, SHADDA
from .schemas import StoryResponse
from .scoring import missed_phonemes, single

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"  # repo root locally, /content in Docker
ROUND_SIZE = 5
# Arabic phonemes -> what the player sees, so a reason never shows phoneme symbols. Unknown sounds show as they are.
LETTER_FOR = {**{sym: ch for ch, sym in LETTERS.items() if ch not in "أإؤئ"},
              "a": "الفتحة", "i": "الكسرة", "u": "الضمة", "aa": "ا", "ii": "ي", "uu": "و"}


def letter(p: str) -> str:
    """'b' -> 'ب', 'bb' -> 'بّ' (shadda)."""
    base = single(p)
    return LETTER_FOR.get(base, p) + (SHADDA if base != p else "")


MIN_RESULTS_TO_MOVE = 3  # don't change level on one lucky or unlucky word
LEVEL_UP, LEVEL_DOWN = 0.8, 0.5  # word accuracy of the round just played
MIN_VOWELIZED = 0.9  # share of letters with a vowel mark a story needs (stories are read aloud and scored)

STORY_SCHEMA = {
    "type": "object",
    "properties": {
        "story": {"type": "string"},
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"q": {"type": "string"}, "answer": {"type": "string"}},
                "required": ["q", "answer"],
            },
        },
    },
    "required": ["story", "questions"],
}


class ContentMissing(Exception):
    pass


class LLMUnavailable(Exception):
    pass


def load_levels(game: str) -> list[dict]:
    """content/<game>.json -> [{"focus": str, "display_ms": int, "items": [str, ...]}, ...], easiest first."""
    path = CONTENT_DIR / f"{game}.json"
    if not path.is_file():
        raise ContentMissing(game)
    return json.loads(path.read_text(encoding="utf-8"))["levels"]


def weak_sounds(results: list[dict], top: int = 2) -> list[str]:
    counts = Counter(
        p for r in results if not r["correct"] for p in missed_phonemes(r["target_phonemes"], r["heard_phonemes"])
    )
    return [p for p, _ in counts.most_common(top)]


# Bayesian Knowledge Tracing (Corbett & Anderson 1995): the chance each sound is mastered, updated per attempt.
P_INIT, P_LEARN, P_SLIP, P_GUESS = 0.3, 0.1, 0.1, 0.2
WEAK = 0.6  # below this a sound still needs practice


def bkt(p: float, correct: bool) -> float:
    if correct:
        p = p * (1 - P_SLIP) / (p * (1 - P_SLIP) + (1 - p) * P_GUESS)
    else:
        p = p * P_SLIP / (p * P_SLIP + (1 - p) * (1 - P_GUESS))
    return p + (1 - p) * P_LEARN


def mastery(attempts: list[dict]) -> dict[str, float]:
    """attempts oldest first -> {sound: P(mastered)} for every sound the player has been asked to read."""
    known: dict[str, float] = {}
    for a in attempts:
        missed = set(missed_phonemes(a["target_phonemes"], a["heard_phonemes"]))
        for sound in set(a["target_phonemes"]):
            known[sound] = bkt(known.get(sound, P_INIT), sound not in missed)
    return known


def weakest(player_id: str, top: int = 2) -> list[str]:
    known = mastery(db.recent_attempts(player_id, limit=300)[::-1])
    return sorted((s for s, p in known.items() if p < WEAK), key=known.get)[:top]


def pick_items(items: list[str], weak: list[str]) -> list[str]:
    """Words containing the player's weak sounds first, then the rest, shuffled."""
    targeted = [w for w in items if set(weak) & set(g2p.phonemes(w))]
    rest = [w for w in items if w not in targeted]
    random.shuffle(targeted)
    random.shuffle(rest)
    return (targeted + rest)[:ROUND_SIZE]


def next_exercise(player_id: str, game: str, history: list[dict]) -> dict:
    """history = the /score results of the round just played (empty on the first call)."""
    levels = load_levels(game)
    level = min(db.get_level(player_id, game), len(levels))
    reason = levels[level - 1]["focus"]
    if len(history) >= MIN_RESULTS_TO_MOVE:
        accuracy = sum(h["correct"] for h in history) / len(history)
        if accuracy >= LEVEL_UP and level < len(levels):
            level += 1
            reason = f"مستوى أعلى: {levels[level - 1]['focus']}"
        elif accuracy < LEVEL_DOWN and level > 1:
            level -= 1
            reason = f"نُبطئ قليلًا: {levels[level - 1]['focus']}"
    db.set_level(player_id, game, level)
    spec = levels[level - 1]
    weak = weakest(player_id) or weak_sounds(history)  # history only counts here when its attempts weren't saved
    if weak:
        reason = "نتدرّب على: " + " / ".join(letter(p) for p in weak)
    return {"game": game, "level": level, "items": pick_items(spec["items"], weak),
            "display_ms": spec["display_ms"], "reason": reason}


def _complete(prompt: str) -> str:
    base_url, api_key, model = (os.getenv(k) for k in ("VLLM_BASE_URL", "VLLM_API_KEY", "VLLM_MODEL"))
    if not (base_url and model):
        raise LLMUnavailable("VLLM_BASE_URL / VLLM_MODEL are not set")
    client = OpenAI(base_url=base_url, api_key=api_key or "none", timeout=60)
    request = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 800}
    try:
        try:
            # vLLM structured output: the model can only produce JSON in this shape.
            resp = client.chat.completions.create(
                **request, response_format={"type": "json_schema", "json_schema": {"name": "story", "schema": STORY_SCHEMA}})
        except BadRequestError:  # some hosted dev APIs lack schema output; the prompt asks for JSON and story() checks it
            resp = client.chat.completions.create(**request)
    except OpenAIError as e:
        raise LLMUnavailable(f"LLM request failed: {type(e).__name__}") from e
    return resp.choices[0].message.content or ""


def vowelized_share(text: str) -> float:
    """Share of Arabic letters carrying a mark. Madd letters (ا و ي ى) are skipped: they are often unmarked."""
    letters = [k for k, ch in enumerate(text) if "ء" <= ch <= "ي" and ch not in "اويى"]
    marked = [k for k in letters if k + 1 < len(text) and "ً" <= text[k + 1] <= "ْ"]
    return len(marked) / len(letters) if letters else 1.0


def _parse_story(text: str) -> dict:
    text = text[text.find("{"): text.rfind("}") + 1]  # models without schema output may wrap JSON in prose or ``` fences
    try:
        return StoryResponse.model_validate_json(text).model_dump()
    except ValidationError as e:
        raise LLMUnavailable("LLM returned a story in the wrong shape") from e


def story(player_id: str, weak: list[str], interests: list[str]) -> dict:
    if not weak:  # frontend doesn't know the weak sounds; the recorded attempts do
        weak = weakest(player_id)
    if not interests and (player := db.get_player(player_id)):
        interests = player["interests"]
    template = Template((CONTENT_DIR / "prompts" / "story.txt").read_text(encoding="utf-8"))
    prompt = template.safe_substitute(weak_sounds="، ".join(letter(p) for p in weak) or "أي حروف",
                                      interests="، ".join(interests) or "الحيوانات")
    for _ in range(2):  # a story without its vowel marks can't be read by a beginner: ask once more
        result = _parse_story(_complete(prompt))
        text = result["story"] + " ".join(q["q"] + " " + q["answer"] for q in result["questions"])
        if vowelized_share(text) >= MIN_VOWELIZED:
            return result
    raise LLMUnavailable("LLM story was not fully vowelized")
