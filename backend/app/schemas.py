"""Pydantic models for the frozen API contract (HANDOFF.md section 4)."""
from typing import Literal

from pydantic import BaseModel

ErrorType = Literal["none", "letter_reversal", "missing_sound", "added_sound", "substitution", "no_response"]


class ScoreResponse(BaseModel):
    heard: str
    target_phonemes: list[str]
    heard_phonemes: list[str]
    correct: bool
    phoneme_accuracy: float
    response_ms: int | None
    error_type: ErrorType


class NextExerciseRequest(BaseModel):
    player_id: str
    game: str
    history: list[ScoreResponse] = []


class NextExerciseResponse(BaseModel):
    game: str
    level: int
    items: list[str]
    display_ms: int
    reason: str


class StoryRequest(BaseModel):
    player_id: str
    weak_sounds: list[str] = []
    interests: list[str] = []


class Question(BaseModel):
    q: str
    answer: str


class StoryResponse(BaseModel):
    story: str
    questions: list[Question]


class Session(BaseModel):
    date: str
    accuracy: float
    avg_response_ms: int
    errors: dict[ErrorType, int]


class ProgressResponse(BaseModel):
    sessions: list[Session]
