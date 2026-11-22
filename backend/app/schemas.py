"""Pydantic models: the API shapes (docs/design.md section 2)."""
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

ErrorType = Literal["none", "letter_reversal", "missing_sound", "added_sound", "substitution", "no_response",
                    "dot_confusion", "vowel_error", "vowel_length", "letter_position"]  # last 4: Arabic
PlayerId = Annotated[str, Field(min_length=1, max_length=64)]
Game = Annotated[str, Field(pattern=r"^[a-z_]{1,32}$")]  # also a content file name: no paths
Interest = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class ScoreResponse(BaseModel):
    heard: str
    target_phonemes: list[str]
    heard_phonemes: list[str]
    correct: bool
    phoneme_accuracy: float
    response_ms: int | None  # null when shown_at_ms was not sent
    error_type: ErrorType
    unclear: bool = False  # the model can't tell if the word was right: ask for another reading, save nothing


class RhythmWord(ScoreResponse):
    target: str
    offset_ms: int | None  # from the moment the word appeared until the reader started it; null for typed answers
    on_time: bool | None  # started before the next word appeared


class RhythmResponse(BaseModel):
    words: list[RhythmWord]
    steadiness_ms: int | None  # spread of the delays: lower is a steadier rhythm


class NextExerciseRequest(BaseModel):
    player_id: PlayerId
    game: Game
    history: list[ScoreResponse] = Field(default=[], max_length=50)


class NextExerciseResponse(BaseModel):
    game: str
    level: int
    items: list[str]
    display_ms: int
    reason: str


class StoryRequest(BaseModel):
    player_id: PlayerId
    weak_sounds: list[Annotated[str, Field(max_length=8)]] = Field(default=[], max_length=5)
    interests: list[Interest] = Field(default=[], max_length=5)


class StoryStatus(BaseModel):
    unlocked: bool
    attempts: int  # word-game attempts so far
    needed: int


class Question(BaseModel):
    q: str
    answer: str


class StoryResponse(BaseModel):
    story: str
    questions: list[Question]


class CoachAttempt(BaseModel):
    target: Annotated[str, Field(min_length=1, max_length=300)]
    target_phonemes: list[Annotated[str, Field(max_length=8)]] = Field(max_length=300)
    heard_phonemes: list[Annotated[str, Field(max_length=8)]] = Field(max_length=300)
    correct: bool
    error_type: ErrorType


class CoachRequest(BaseModel):
    """kind "word": explain one attempt. kind "round": sum up a round's attempts."""
    player_id: PlayerId
    kind: Literal["word", "round"]
    attempts: list[CoachAttempt] = Field(min_length=1, max_length=20)


class CoachResponse(BaseModel):
    text: str


class Session(BaseModel):
    date: str
    accuracy: float
    phoneme_accuracy: float  # mean share of sounds said right: how precisely they read
    avg_response_ms: int | None  # null when no attempt that day had a response time
    errors: dict[ErrorType, int]


class ProgressResponse(BaseModel):
    sessions: list[Session]


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]  # a nickname
Password = Annotated[str, Field(min_length=8, max_length=128)]


class GuestStart(BaseModel):
    interests: list[Interest] = Field(default=[], max_length=5)


class Login(BaseModel):
    name: Name
    password: Password


class Register(Login):
    interests: list[Interest] = Field(default=[], max_length=5)


class Player(BaseModel):
    player_id: str
    name: str
    interests: list[str]


class LoginResponse(Player):
    token: str  # send as "Authorization: Bearer <token>"
