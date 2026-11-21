import json
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, Path, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import brain, db, g2p, mock, rhythm, scoring, speech
from .schemas import (
    CoachRequest, CoachResponse, GuestStart, RhythmResponse, StoryStatus, Login, LoginResponse, NextExerciseRequest, NextExerciseResponse, Player, ProgressResponse, Register, ScoreResponse,
    StoryRequest, StoryResponse,
)

MOCK = os.getenv("MOCK_MODE") == "1"
MAX_AUDIO_BYTES = 5_000_000  # ~5 min of webm/opus; a word is a few KB

@asynccontextmanager
async def lifespan(_app):
    if not MOCK:
        threading.Thread(target=speech.warm_up, daemon=True).start()  # load the model before the first player speaks
    yield


app = FastAPI(title="Phonics Arcade API", lifespan=lifespan)
# Browser game runs on another origin (localhost dev server, hosted frontend) than the API.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer(auto_error=False)  # "Authorization: Bearer <token>"; also adds the Authorize button to /docs


def optional_player(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str | None:
    """None when no token is sent; 401 when a token is sent but is wrong or expired."""
    if creds is None:
        return None
    player = db.player_for_token(creds.credentials)
    if player is None:
        raise HTTPException(401, "Login expired, please log in again")
    return player


def logged_in(player: str | None = Depends(optional_player)) -> str:
    if player is None:
        raise HTTPException(401, "Log in first")
    return player


def own_data(player: str, player_id: str) -> None:
    if player_id != player:
        raise HTTPException(403, "That is another player's data")


@app.get("/health")
def health():
    return {"ok": True, "mock": MOCK}


@app.post("/score", response_model=ScoreResponse)
def score(
    target: str = Form(..., min_length=1, max_length=300),  # up to one story sentence
    audio: UploadFile | None = File(None),
    shown_at_ms: int | None = Form(None),
    # Optional: tag the attempt with its game, or score typed text instead of audio (debug mode).
    game: str = Form("", pattern=r"^[a-z_]{0,32}$"),
    heard_text: str | None = Form(None, max_length=300),
    second_try: bool = Form(False),  # the reading after an unclear one: always gets a verdict
    player: str | None = Depends(optional_player),  # logged in: the attempt is saved to this player
):
    received_ms = time.time() * 1000
    if audio is None:  # no recording and nothing typed (forms send "" as missing): the player didn't answer
        heard_text = heard_text or ""
    if MOCK:
        return mock.score(target, shown_at_ms, heard_text)

    target_ph = list(g2p.phonemes(target))
    if not target_ph:
        raise HTTPException(422, "target has no sounds to say")
    gap = None
    if heard_text is not None:
        heard, heard_ph = heard_text, list(g2p.phonemes(heard_text))
    else:
        data = audio.file.read(MAX_AUDIO_BYTES + 1)
        if len(data) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "Audio too large")
        try:
            if scoring.is_arabic(target):
                heard, (heard_ph, gap) = "", speech.recognize_fit(data, target_ph)
            else:
                heard, heard_ph = speech.recognize(data, audio.content_type or "", arabic=False)
        except speech.SpeechUnavailable as e:
            raise HTTPException(503, str(e))
        except speech.BadAudio as e:
            raise HTTPException(422, str(e))
        heard_ph = scoring.normalize(heard_ph)

    result = {
        "heard": heard,
        "target_phonemes": target_ph,
        "heard_phonemes": heard_ph,
        # shortcut: includes upload time and assumes browser and server clocks agree; move to speech onset later.
        "response_ms": None if shown_at_ms is None else max(0, round(received_ms - shown_at_ms)),
        **scoring.score(target_ph, heard_ph, target, heard, gap),
    }
    if heard_text is None and scoring.is_arabic(target):  # the phoneme model gives sounds: show them as letters
        result["heard"] = target if result["correct"] else g2p.spell(heard_ph)
    elif result["correct"] and not heard:
        result["heard"] = target
    result["unclear"] = result["unclear"] and not second_try
    if result["correct"] and gap is not None:
        result["heard_phonemes"] = target_ph  # judged right on fit: don't count the transcript's slip against a sound
    if player and not result["unclear"]:  # an unclear reading is read again; the second one counts
        db.save_attempt(player, game, target, result)
    return result


@app.post("/score-rhythm", response_model=RhythmResponse)
def score_rhythm(
    targets: str = Form(..., max_length=2000),  # JSON list of the words, in the order they were shown
    slot_ms: int = Form(..., ge=400, le=5000),  # time between words
    first_word_ms: int = Form(..., ge=0, le=20000),  # when the first word appeared, from the start of the recording
    audio: UploadFile | None = File(None),
    heard_text: str | None = Form(None, max_length=600),  # debug mode: the whole run typed, words separated by spaces
    game: str = Form("rhythmic_reading", pattern=r"^[a-z_]{1,32}$"),
    player: str | None = Depends(optional_player),
):
    try:
        texts = json.loads(targets)
        assert isinstance(texts, list) and 1 <= len(texts) <= 8 and all(isinstance(w, str) and 0 < len(w) <= 40 for w in texts)
    except (ValueError, AssertionError):
        raise HTTPException(422, "targets must be a JSON list of 1 to 8 words")
    if MOCK:
        return mock.score_rhythm(texts, slot_ms)
    target_ph = [list(g2p.phonemes(w)) for w in texts]
    if not all(target_ph):
        raise HTTPException(422, "every target needs sounds to say")
    starts = None
    if audio is None:  # typed, or nothing at all (the reader stayed silent)
        heard = list(g2p.phonemes(heard_text or ""))
    else:
        data = audio.file.read(MAX_AUDIO_BYTES + 1)
        if len(data) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "Audio too large")
        try:
            timed = speech.recognize_timed(data, arabic=all(scoring.is_arabic(w) for w in texts))
        except speech.SpeechUnavailable as e:
            raise HTTPException(503, str(e))
        except speech.BadAudio as e:
            raise HTTPException(422, str(e))
        heard, starts = [p for p, _ in timed], [ms for _, ms in timed]
    result = rhythm.score_run(texts, target_ph, heard, starts, slot_ms, first_word_ms)
    if player:
        for word in result["words"]:
            db.save_attempt(player, game, word["target"], word)
    return result


@app.post("/timing-test")
def timing_test(
    audio: UploadFile = File(...),
    # Optional, for the real-word check: the words shown, and when, as in /score-rhythm.
    targets: str | None = Form(None, max_length=2000),
    slot_ms: int = Form(2000, ge=400, le=5000),
    first_word_ms: int = Form(0, ge=0, le=20000),
):
    """Mic check, outside the games: every sound the model heard and when it started, written back as Arabic.
    With targets, also each word's result and timing. Nothing is saved."""
    texts = None
    if targets is not None:
        try:
            texts = json.loads(targets)
            assert isinstance(texts, list) and 1 <= len(texts) <= 8 and all(isinstance(w, str) and 0 < len(w) <= 40 for w in texts)
        except (ValueError, AssertionError):
            raise HTTPException(422, "targets must be a JSON list of 1 to 8 words")
    if MOCK:
        raise HTTPException(503, "the timing test needs the real speech model")
    data = audio.file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio too large")
    try:
        timed = speech.recognize_timed(data)
    except speech.SpeechUnavailable as e:
        raise HTTPException(503, str(e))
    except speech.BadAudio as e:
        raise HTTPException(422, str(e))
    heard = [p for p, _ in timed]
    out = {"sounds": [{"phoneme": p, "ms": ms} for p, ms in timed], "heard_text": g2p.spell(heard)}
    if texts:
        result = rhythm.score_run(texts, [list(g2p.phonemes(w)) for w in texts], heard, [ms for _, ms in timed],
                                  slot_ms, first_word_ms)
        out["words"] = [{**w, "heard_text": g2p.spell(w["heard_phonemes"])} for w in result["words"]]
        out["steadiness_ms"] = result["steadiness_ms"]
    return out


@app.post("/next-exercise", response_model=NextExerciseResponse)
def next_exercise(req: NextExerciseRequest, player: str = Depends(logged_in)):
    own_data(player, req.player_id)
    if MOCK:
        return mock.next_exercise(req.game, req.history)
    try:
        return brain.next_exercise(req.player_id, req.game, [h.model_dump() for h in req.history])
    except brain.ContentMissing:
        raise HTTPException(404, f"No content for game '{req.game}' yet (content/{req.game}.json)")


@app.post("/story", response_model=StoryResponse)
def story(req: StoryRequest, player: str = Depends(logged_in)):
    own_data(player, req.player_id)
    if MOCK:
        return mock.story(req.weak_sounds, req.interests)
    try:
        return brain.story(req.player_id, req.weak_sounds, req.interests)
    except brain.StoryLocked as e:
        raise HTTPException(409, str(e))
    except brain.LLMUnavailable as e:
        raise HTTPException(503, f"Story service unavailable: {e}")


@app.get("/story/status/{player_id}", response_model=StoryStatus)
def story_status(player_id: str = Path(..., min_length=1, max_length=64), player: str = Depends(logged_in)):
    own_data(player, player_id)
    if MOCK:
        return {"unlocked": True, "attempts": brain.STORY_UNLOCK, "needed": brain.STORY_UNLOCK}
    return brain.story_status(player_id)


@app.post("/coach", response_model=CoachResponse)
def coach(req: CoachRequest, player: str = Depends(logged_in)):
    own_data(player, req.player_id)
    if MOCK:
        return mock.coach(req.kind)
    try:
        return {"text": brain.coach(req.player_id, req.kind, [a.model_dump() for a in req.attempts])}
    except brain.LLMUnavailable as e:
        raise HTTPException(503, f"Coach unavailable: {e}")


@app.get("/progress/{player_id}", response_model=ProgressResponse)
def progress(
    player_id: str = Path(..., min_length=1, max_length=64),
    game: str | None = Query(None, pattern=r"^[a-z_]{1,32}$"),  # one game only; omit for all games
    player: str = Depends(logged_in),
):
    own_data(player, player_id)
    if MOCK:
        return mock.progress(player_id)
    return {"sessions": db.sessions(player_id, game)}


# Accounts are plain storage (no AI to wait for), so they are real in mock mode too.
@app.post("/players", response_model=LoginResponse, status_code=201)
def register(req: Register):
    try:
        player = db.create_account(req.name, req.password, req.interests)
    except db.NameTaken:
        raise HTTPException(409, "That name is already taken")
    return {**player, "token": db.start_login(player["player_id"])}


@app.post("/login", response_model=LoginResponse)
def login(req: Login):
    player = db.check_password(req.name, req.password)
    if player is None:
        raise HTTPException(401, "Wrong name or password")
    return {**player, "token": db.start_login(player["player_id"])}


@app.post("/guest", response_model=LoginResponse, status_code=201)
def guest(req: GuestStart | None = None):
    """Play without an account. Everything is deleted on logout, or GUEST_HOURS after starting."""
    player = db.create_guest(req.interests if req else [])
    return {**player, "token": db.start_login(player["player_id"])}


@app.post("/logout", status_code=204)
def logout(creds: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if creds:
        db.end_login(creds.credentials)


@app.get("/me", response_model=Player)
def me(player: str = Depends(logged_in)):
    return db.get_player(player)
