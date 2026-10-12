import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import mock
from .schemas import NextExerciseRequest, NextExerciseResponse, ProgressResponse, ScoreResponse, StoryRequest, StoryResponse

MOCK = os.getenv("MOCK_MODE") == "1"

app = FastAPI(title="Dyslexia reading games API")
# Browser game runs on another origin (localhost dev server) than the API on the droplet.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def not_ready():
    raise HTTPException(501, "Real implementation not ready yet; run with MOCK_MODE=1")


@app.get("/health")
def health():
    return {"ok": True, "mock": MOCK}


@app.post("/score", response_model=ScoreResponse)
async def score(target: str = Form(...), audio: UploadFile = File(...), shown_at_ms: int | None = Form(None)):
    if MOCK:
        return mock.score(target, shown_at_ms)
    not_ready()


@app.post("/next-exercise", response_model=NextExerciseResponse)
def next_exercise(req: NextExerciseRequest):
    if MOCK:
        return mock.next_exercise(req.game, req.history)
    not_ready()


@app.post("/story", response_model=StoryResponse)
def story(req: StoryRequest):
    if MOCK:
        return mock.story(req.weak_sounds, req.interests)
    not_ready()


@app.get("/progress/{player_id}", response_model=ProgressResponse)
def progress(player_id: str):
    if MOCK:
        return mock.progress(player_id)
    not_ready()
