import os
import time

from fastapi import FastAPI, File, Form, HTTPException, Path, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import brain, db, g2p, mock, scoring, speech
from .schemas import NextExerciseRequest, NextExerciseResponse, ProgressResponse, ScoreResponse, StoryRequest, StoryResponse

MOCK = os.getenv("MOCK_MODE") == "1"
MAX_AUDIO_BYTES = 5_000_000  # ~5 min of webm/opus; a word is a few KB

app = FastAPI(title="Phonics Arcade API")
# Browser game runs on another origin (localhost dev server, Vercel) than the API.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"ok": True, "mock": MOCK}


@app.post("/score", response_model=ScoreResponse)
def score(
    target: str = Form(..., min_length=1, max_length=100),
    audio: UploadFile | None = File(None),
    shown_at_ms: int | None = Form(None),
    # Optional additions, proposed in HANDOFF.md section 4: record progress / score typed text in debug mode.
    player_id: str | None = Form(None, min_length=1, max_length=64),
    game: str = Form("", pattern=r"^[a-z_]{0,32}$"),
    heard_text: str | None = Form(None, max_length=100),
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
        heard_ph = scoring.normalize(heard_ph)

    result = {
        "heard": heard,
        "target_phonemes": target_ph,
        "heard_phonemes": heard_ph,
        # shortcut: includes upload time and assumes browser and server clocks agree; move to speech onset later.
        "response_ms": None if shown_at_ms is None else max(0, round(received_ms - shown_at_ms)),
        **scoring.score(target_ph, heard_ph, target, heard),
    }
    if player_id:
        db.save_attempt(player_id, game, target, result)
    return result


@app.post("/next-exercise", response_model=NextExerciseResponse)
def next_exercise(req: NextExerciseRequest):
    if MOCK:
        return mock.next_exercise(req.game, req.history)
    try:
        return brain.next_exercise(req.player_id, req.game, [h.model_dump() for h in req.history])
    except brain.ContentMissing:
        raise HTTPException(404, f"No content for game '{req.game}' yet (content/{req.game}.json)")


@app.post("/story", response_model=StoryResponse)
def story(req: StoryRequest):
    if MOCK:
        return mock.story(req.weak_sounds, req.interests)
    try:
        return brain.story(req.player_id, req.weak_sounds, req.interests)
    except brain.LLMUnavailable as e:
        raise HTTPException(503, f"Story service unavailable: {e}")


@app.get("/progress/{player_id}", response_model=ProgressResponse)
def progress(player_id: str = Path(..., min_length=1, max_length=64)):
    if MOCK:
        return mock.progress(player_id)
    return {"sessions": db.sessions(player_id)}
