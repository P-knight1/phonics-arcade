# Arabic reading practice for dyslexia: team guide

> **For the team while we build.** We rewrite this into a public README before submitting (29 Nov 2026).
> Scope, the API contract, roles and the timeline are in **[HANDOFF.md](HANDOFF.md)**. The science behind every feature is in **[docs/research.md](docs/research.md)**. Read both first.

A voice-based reading-practice tool for Arabic readers with dyslexia, built for the Kuwait Dyslexia Association (KDA) AI competition (deadline 30 Nov 2026). It is a practice and support tool, not a medical one: make no medical claims anywhere (HANDOFF.md section 2 lists the banned words).

## 0. The project at a glance

### What it is
A web app of short reading games that you play **with your voice**. The player reads a fully vowelized Modern Standard Arabic (MSA) word or sentence aloud. Our Arabic phoneme model works out which **sounds** they actually said, the backend compares them with the target, and names the mistake (a short vowel, a dot-letter like ح read as ج, a long vowel read short, two letters swapped). The app tracks which sounds each player has mastered and picks the next words, and later stories, to practise the weak ones.

### Who it's for
- **Target users:** children with dyslexia learning to read Arabic.
- **Pilot:** consenting adults only. Children are not tested or recorded in this project. The pilot checks usability and scoring accuracy, not learning outcomes (ethics checklist: [docs/research.md](docs/research.md) section 7).

### Why it's new
- *Google Read Along accepts; we notice.* Read Along is designed to lean towards accepting a pronunciation. That hides exactly the errors a dyslexic reader needs feedback on.
- We score sound by sound with a phoneme model. Plain speech-to-text writes the word you *meant*, not what you said.
- Error types made for Arabic: `vowel_error`, `vowel_length`, `dot_confusion`, `letter_position`. Each maps to a described pattern of Arabic dyslexia ([docs/research.md](docs/research.md) sections 1 and 5).
- No Arabic dyslexia app that scores reading aloud was found in Kuwait or the Gulf ([docs/research.md](docs/research.md) section 3).

### What the player sees
1. **Log in, register, or play as a guest.** An account (nickname, password, interests) keeps progress, and each player sees only their own. A guest plays straight away, fully personalised, but loses the progress on leaving the page.
2. **Game menu**, then **in a game:** a large vowelized word, a mic button, and instant, kind feedback.
3. **Right-to-left Arabic UI** with dyslexia-friendly typography (generous spacing, large vowel marks). *Status: the frontend shell and Word Flash work today with English UI text; the RTL Arabic UI is in progress.*

| Game | Player does | Priority |
|---|---|---|
| Word Flash | Reads a vowelized word before it hides; display time adapts; words follow letter families | 1 |
| Sound Surgery | "Say كَتَبَ without the كـ", "swap the first sound" | 1 |
| Rhythmic Reading | Reads syllables in time with a beat | 1 |
| Roots | Finds and reads words from one root (ك ت ب → كَتَبَ، كاتِب، مَكتَب) | 2 |
| Echo Chain | Repeats a growing chain of syllables | 2 |
| Story Recall | Reads a generated, fully vowelized story built on their weak sounds and interests, then answers questions | 3 |
| Progress Dashboard | Word accuracy, phoneme accuracy, speed and error types over sessions | — |

### How it fits together
```
Browser (React, RTL Arabic UI, microphone)
        │  HTTP (JSON + audio)
        ▼
Backend: FastAPI (Python)
        ├── speech.py   Arabic phoneme model (GPU if present, else CPU)
        ├── g2p.py      target text → phonemes (espeak-ng, bundled)
        ├── scoring.py  phoneme comparison + Arabic error types
        ├── brain.py    mastery per sound (Bayesian Knowledge Tracing), next exercise, stories from an LLM
        └── db.py       SQLite: accounts, guests, attempts, levels
ml/                     training and evaluation of our Arabic phoneme model
```
Stories use **any OpenAI-compatible LLM endpoint** (settings `VLLM_BASE_URL`, `VLLM_API_KEY`, `VLLM_MODEL`; the names are historical).

### Requirements
- **Must:** AI is central and visible: our fine-tuned phoneme model, error profiling, adaptive practice.
- **Must:** no medical claims; every game and claim maps to a source in [docs/research.md](docs/research.md).
- **Must:** pilot with consenting adults only; recordings never go into git.
- **Must:** every game is playable with debug buttons when the AI is down (mock mode).
- **Must:** MIT licence, original work, no secrets in git, a README that runs, Docker.
- **Should:** the mic is the main input; feedback in about 2 s after the player stops speaking.

### Expected results by 30 November
- A working demo: a player reads vowelized Arabic words into the mic and gets sound-level feedback with Arabic error types.
- Two different players get different practice from the same app, driven by their own weak sounds.
- A measured result for our phoneme model on Arabic: agreement with human labels on the adult pilot's recordings.
- The dashboard shows each player's accuracy, speed and error types over sessions.
- A science page, slides and a demo video for KDA.

## 1. Get the code

```bash
gh repo clone P-knight1/phonics-arcade
cd phonics-arcade
cp .env.example .env        # Windows PowerShell: copy .env.example .env
```

## 2. Run the backend (no GPU needed)

Two modes, set by `MOCK_MODE` in `.env`:

| `MOCK_MODE` | What you get | Use it for |
|---|---|---|
| `1` (default) | Fake data on every game endpoint, no setup. Accounts are real | Frontend work |
| `0` | **Real** scoring, progress, mastery and levels, saved in SQLite. Typed answers (`heard_text`) work fully. Audio scoring needs the speech packages ([docs/backend-guide.md](docs/backend-guide.md) section 5), stories need an LLM endpoint in `.env`; without them those calls return `503` | Integration, backend work |

**With Docker**
```bash
docker compose up --build
```
The image runs mock mode and typed answers out of the box. It does not include the speech packages yet.

**Without Docker** (Python 3.11+)

macOS / Linux:
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --env-file ../.env
```

Windows PowerShell (one line at a time; `&&` does not work there):
```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --env-file ..\.env
```

Then open **http://localhost:8000/docs**. You can try every endpoint from that page. `GET /health` shows which mode is running.

## 2a. Run the frontend (Node 20+)

With the backend running (section 2):

```bash
cd frontend
npm install
npm run dev
```

On Windows PowerShell, use `npm.cmd install` and `npm.cmd run dev` if PowerShell blocks `npm` with a script-execution error.

Then open http://localhost:5173. Add `?debug=1` for the placeholder answer buttons, e.g. http://localhost:5173/?debug=1.

The API address comes from `VITE_API_BASE_URL` (`frontend/.env.development` points at `http://localhost:8000`). To use another backend, put that variable in `frontend/.env.local` (git-ignored).

Adding a game: build it as a page under `frontend/src/games/<name>/` and swap it in for its `ComingSoon` route in `frontend/src/App.tsx`. Use `api.ts` for every backend call, `usePlayer()` for the logged-in player, and `useRecorder()` + `MicButton` + `DebugPanel` from `frontend/src/shell/` for answers ([WordFlash.tsx](frontend/src/games/word-flash/WordFlash.tsx) shows all of them together).

## 3. Run the tests

```bash
cd backend
python -m pytest
```
Windows PowerShell with the virtual environment from section 2: `.venv\Scripts\python -m pytest`.

## 4. How your part plugs into the backend

**Read [docs/backend-guide.md](docs/backend-guide.md).** It covers what's built, what's missing, Arabic content rules, the error types, and how each part of the app uses the API.

## 5. Rules for working together

- **Never commit secrets.** API keys, tokens and server addresses go in `.env` only (it is git-ignored). Never paste them into code, the README, issues or PRs. If one leaks, tell the team and rotate it straight away.
- **Never commit recordings or datasets.** Pilot audio stays on the team's private, encrypted drive.
- **One branch per person or feature.** Merge into `main` at least once a day. `main` must always run, and tests must pass.
- **The API contract (HANDOFF.md section 4) changes only with whole-team agreement**, because frontend and backend both depend on it.
- **Frontend code uses one API client** (`frontend/src/api.ts`) that reads the base URL from config. No hard-coded URLs.
- **Every game supports debug mode** (`?debug=1`): "✓ Said it right" / "✗ Said it wrong" buttons and a box for typing what was heard.

## 6. Where things live

```
backend/app/main.py      routes; MOCK_MODE=1 switches the game endpoints to mock data
backend/app/mock.py      fake responses
backend/app/scoring.py   phoneme comparison, error types incl. Arabic ones (pure functions)
backend/app/g2p.py       text -> phonemes (espeak-ng 'ar' or 'en-gb', picked by script; bundled, no install)
backend/app/speech.py    audio -> phonemes: the phoneme model plugs in here (MODEL)
backend/app/brain.py     mastery per sound (BKT), next exercise (rules), stories (LLM)
backend/app/db.py        SQLite: accounts, logins, attempts and levels (file in backend/data/, git-ignored)
backend/app/schemas.py   Pydantic models = the API contract
content/                 vowelized word lists per game, story prompt
frontend/                game UI: React + TypeScript on Vite (see section 2a)
ml/                      phoneme model: evaluation and fine-tuning scripts (data and models stay out of git)
docs/research.md         the science: Arabic dyslexia, evidence per game, competitors, ethics
docs/backend-guide.md    how to use the backend
```

## 7. Open questions for the team

Listed in section 7 of [docs/backend-guide.md](docs/backend-guide.md) and in section 9 of [docs/research.md](docs/research.md).
