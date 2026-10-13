# Phonics Arcade — team guide

> **For the team during the hackathon.** We rewrite this into a public README before submitting (Sat 17 Oct).
> Scope, the API contract, roles, timeline and the event rules are all in **[HANDOFF.md](HANDOFF.md)**. Read it first.

Voice-controlled reading practice games for people with dyslexia. AI models running on an AMD MI300X GPU score each spoken word one sound at a time. This is a practice tool, not a medical one: never write "diagnose" or "diagnosis" anywhere.

## 0. The project at a glance

### What it is
A web app of short reading games that you play **with your voice**. The player reads a word or sound aloud. The backend on the AMD GPU works out which **sounds** they actually said, compares them with the target, and names the mistake (e.g. "b/d swap", "missed a sound"). An adaptive "brain" then picks the next words and writes short personalised stories, so two players get two different experiences.

**Who it's for:** adults with dyslexia who want to practise reading, plus the tutors and support services who work with them (and would pay for it).

**Why it's new:** ordinary speech-to-text "corrects" what you say (you read *bog*, it writes *dog*). Scoring sound by sound with a phoneme model, plus stories generated for each player, wasn't practical before modern AI on large GPUs.

### What the player sees
1. **Log in, register, or play as a guest:** an account (nickname, password, interests) keeps your progress, and each player only sees their own. A guest plays straight away, fully personalised, but loses the progress on leaving the page.
2. **Game menu:** Word Flash · Sound Surgery · Echo Chain · Story Recall · Progress.
3. **In a game:** a big word or prompt, a mic button, and instant feedback (✓, or "you said *bog*, try *d*"). It gets faster when you succeed and slower, repeating patterns, when you struggle.
4. **Progress dashboard:** charts of accuracy, response time and error types across sessions.

| Game | Player does | Priority |
|---|---|---|
| Word Flash | Reads a word that disappears quickly; speed adapts | Must |
| Sound Surgery | "Say *cat* without the *c*", "swap the *m* in *map* for *s*" | Must |
| Echo Chain | Repeats a growing chain of sounds or syllables | Must |
| Story Recall | Reads an AI story built from their weak sounds and interests, then answers questions by voice | Should |
| Progress Dashboard | Sees improvement over sessions | Must |
| Beat Reader | Syllables on a beat | Cut |

### How it fits together
```
Browser (Vercel, HTTPS)  ──HTTPS──▶  FastAPI on AMD droplet (MI300X, ROCm)
 game UI + microphone                  ├─ phoneme model  → scoring (what sounds were said)
                                       ├─ Whisper        → free speech (Story Recall answers)
                                       └─ LLM via vLLM   → stories (localhost only, never public)
```

### Requirements
- **Must:** all AI runs on the AMD droplet, and the demo visibly uses it · Docker · public MIT repo · README that runs · no secrets in git · no medical claims · a live URL for judges.
- **Must:** every game is playable with debug buttons even when the AI is down (mock mode).
- **Should:** the mic is the main input; feedback appears in about 2 s or less after the player stops speaking.
- **Submission:** MP4 video (≤ 5 min), PDF slides, 16:9 cover image (see HANDOFF.md section 12).

### Expected results (what "done" looks like on Saturday)
- A judge opens the live URL, picks a player, reads words into the mic, and sees sound-level feedback scored on AMD hardware.
- The demo video shows **two players** getting **different** exercises and stories from the same app (a Track 4 requirement).
- The dashboard shows each player's accuracy, response time and error types over sessions.
- The deck answers what we built, what the AI decides, how we control quality, **cost per session**, and who pays.

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
| `1` (default) | Fake data on every endpoint, no setup | Frontend work |
| `0` | **Real** scoring, progress and adaptive levels, saved in SQLite. Typed answers (`heard_text`) work fully. Audio scoring and stories return `503` until the AMD droplet is connected. | Integration, backend work |

**With Docker**
```bash
docker compose up --build
```

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

Then open http://localhost:5173. Add `?debug=1` for the placeholder answer buttons, e.g. http://localhost:5173/?debug=1.

The API address comes from `VITE_API_BASE_URL` (`frontend/.env.development` points at `http://localhost:8000`). To use another backend, put that variable in `frontend/.env.local` (git-ignored).

Adding a game: build it as a page under `frontend/src/games/<name>/` and swap it in for its `ComingSoon` route in `frontend/src/App.tsx`. Use `api.ts` for every backend call, `usePlayer()` for the logged-in player, and `useRecorder()` + `MicButton` + `DebugPanel` from `frontend/src/shell/` for answers ([WordFlash.tsx](frontend/src/games/word-flash/WordFlash.tsx) shows all of them together).

## 3. Run the tests

```bash
cd backend
python -m pytest
```

## 4. How your part plugs into the backend

**Read [docs/backend-guide.md](docs/backend-guide.md).** It covers what's built, what's missing, and step-by-step instructions with examples for each role.

## 5. Rules for working together

- **Never commit secrets.** API keys, tokens, droplet IPs and SSH keys go in `.env` only (it is git-ignored). Never paste them into code, the README, issues, PRs or Discord. If one leaks, tell the team and rotate it straight away.
- **One branch per person or feature.** Merge into `main` at least once a day. `main` must always run, and tests must pass.
- **The API contract (HANDOFF.md section 4) is frozen.** Changing it needs the whole team to agree, because frontend and backend both depend on it.
- **Frontend code uses one API client** (`frontend/src/api.ts`) that reads the base URL from config. No hard-coded URLs.
- **Every game supports debug mode** (`?debug=1`): "✓ Said it right" / "✗ Said it wrong" buttons and a box for typing what was heard.

## 6. Where things live

```
backend/app/main.py      routes; MOCK_MODE=1 switches every endpoint to mock data
backend/app/mock.py      fake responses
backend/app/scoring.py   phoneme comparison, error types, weak sounds (pure functions)
backend/app/g2p.py       text -> phonemes (espeak-ng, bundled; no install needed)
backend/app/speech.py    audio -> phonemes: AI & Infrastructure plugs in here
backend/app/brain.py     adaptive next exercise (rules) + stories (LLM on vLLM)
backend/app/db.py        SQLite: accounts, logins, attempts and levels (file in backend/data/, git-ignored)
backend/app/schemas.py   Pydantic models = the API contract
content/                 word lists and prompts (owned by Content)
frontend/                game UI: React + TypeScript on Vite (see section 2a)
infra/                   droplet setup script
```

## 7. Open questions for the team

Listed in section 7 of [docs/backend-guide.md](docs/backend-guide.md). Decide them on Day 1.
