"""The adaptive brain.

Next exercise: plain rules over the content word lists (testable, never invents words outside the phonics
progression). Stories: an LLM served by vLLM on the AMD droplet, through the OpenAI-compatible API.
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
from .schemas import StoryResponse
from .scoring import missed_phonemes

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"  # repo root locally, /content in Docker
ROUND_SIZE = 5
MIN_RESULTS_TO_MOVE = 3  # don't change level on one lucky or unlucky word
LEVEL_UP, LEVEL_DOWN = 0.8, 0.5  # word accuracy of the round just played

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
            reason = f"level up: {levels[level - 1]['focus']}"
        elif accuracy < LEVEL_DOWN and level > 1:
            level -= 1
            reason = f"slowing down: {levels[level - 1]['focus']}"
    db.set_level(player_id, game, level)
    spec = levels[level - 1]
    weak = weak_sounds(history) or weak_sounds(db.recent_attempts(player_id))  # first round: earlier sessions
    if weak:
        reason = f"practising {'/'.join(weak)}"
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


def story(player_id: str, weak: list[str], interests: list[str]) -> dict:
    if not weak:  # frontend doesn't know the weak sounds; the recorded attempts do
        weak = weak_sounds(db.recent_attempts(player_id))
    if not interests and (player := db.get_player(player_id)):
        interests = player["interests"]
    template = Template((CONTENT_DIR / "prompts" / "story.txt").read_text(encoding="utf-8"))
    prompt = template.safe_substitute(weak_sounds=", ".join(weak) or "any", interests=", ".join(interests) or "animals")
    text = _complete(prompt)
    text = text[text.find("{"): text.rfind("}") + 1]  # models without schema output may wrap JSON in prose or ``` fences
    try:
        return StoryResponse.model_validate_json(text).model_dump()
    except ValidationError as e:
        raise LLMUnavailable("LLM returned a story in the wrong shape") from e
