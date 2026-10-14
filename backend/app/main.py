import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, Path, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import brain, db, g2p, mock, scoring, speech
from .schemas import (
    GuestStart, Login, LoginResponse, NextExerciseRequest, NextExerciseResponse, Player, ProgressResponse, Register, ScoreResponse,
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
# Browser game runs on another origin (localhost dev server, Vercel) than the API.
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
    # Optional additions, proposed in HANDOFF.md section 4: tag the game / score typed text in debug mode.
    game: str = Form("", pattern=r"^[a-z_]{0,32}$"),
    heard_text: str | None = Form(None, max_length=300),
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
    if heard_text is not None:
        heard, heard_ph = heard_text, list(g2p.phonemes(heard_text))
    else:
        data = audio.file.read(MAX_AUDIO_BYTES + 1)
        if len(data) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "Audio too large")
        try:
            heard, heard_ph = speech.recognize(data, audio.content_type or "")
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
        **scoring.score(target_ph, heard_ph, target, heard),
    }
    if result["correct"] and not heard:  # the phoneme model gives sounds, not words
        result["heard"] = target
    if player:
        db.save_attempt(player, game, target, result)
    return result


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
    except brain.LLMUnavailable as e:
        raise HTTPException(503, f"Story service unavailable: {e}")


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
