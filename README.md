# Phonics Arcade — team guide

> **For the team during the hackathon.** We rewrite this into a public README before submitting (Sat 17 Oct).
> Scope, the API contract, roles, timeline and the event rules are all in **[HANDOFF.md](HANDOFF.md)**. Read it first.

Voice-controlled reading practice games for people with dyslexia. AI models running on an AMD MI300X GPU score each spoken word one sound at a time. This is a practice tool, not a medical one: never write "diagnose" or "diagnosis" anywhere.

## 0. The project at a glance

### What it is
A web app of short reading games that you play **with your voice**. The player reads a word or sound aloud. The backend on the AMD GPU works out which **sounds** they actually said, compares them with the target, and names the mistake (e.g. "b/d swap", "missed a sound"). An adaptive "brain" then picks the next words and writes short personalised stories, so two players get two different experiences.

**Who it's for:** children and adults with dyslexia who want to practise reading, plus the parents, tutors and schools who support them (and would pay for it).

**Why it's new:** ordinary speech-to-text "corrects" what you say (you read *bog*, it writes *dog*). Scoring sound by sound with a phoneme model, plus stories generated for each player, wasn't practical before modern AI on large GPUs.

### What the player sees
1. **Player select:** pick or create a player (name and interests, e.g. football).
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
| Beat Reader | Syllables on a beat | Cut unless there is spare time |

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

## 2. Run the mock API (no GPU needed)

The mock API returns fake data that matches the contract, so frontend work never waits on the real AI.

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
MOCK_MODE=1 uvicorn app.main:app --reload
```

Windows PowerShell (one line at a time; `&&` does not work there):
```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
$env:MOCK_MODE="1"; .venv\Scripts\python -m uvicorn app.main:app --reload
```

Then open **http://localhost:8000/docs**. You can call every endpoint from that page.

| Endpoint | What it does (mock) |
|---|---|
| `GET /health` | `{"ok": true, "mock": true}` |
| `POST /score` | Form fields `target` and `audio` (any file), optional `shown_at_ms`. Returns a random right or wrong result. |
| `POST /next-exercise` | Picks the level from recent history and returns words |
| `POST /story` | Returns a fixed story with questions |
| `GET /progress/{player_id}` | Returns 5 fake sessions that improve over time |

## 3. Run the tests

```bash
cd backend
python -m pytest
```

## 4. Rules for working together

- **Never commit secrets.** API keys, tokens, droplet IPs and SSH keys go in `.env` only (it is git-ignored). Never paste them into code, the README, issues, PRs or Discord. If one leaks, tell the team and rotate it straight away.
- **One branch per person or feature.** Merge into `main` at least once a day. `main` must always run.
- **The API contract (HANDOFF.md section 4) is frozen.** Changing it needs the whole team to agree, because frontend and backend both depend on it.
- **Frontend code uses one API client** (`frontend/src/api.ts`) that reads the base URL from config. No hard-coded URLs.
- **Every game supports debug mode** (`?debug=1`): "✓ Said it right" / "✗ Said it wrong" buttons and a box for typing what was heard.

## 5. Where things live

```
backend/app/main.py      routes (MOCK_MODE=1 switches to mock data)
backend/app/mock.py      fake responses
backend/app/scoring.py   phoneme comparison and error types (pure functions, tested)
backend/app/schemas.py   Pydantic models = the API contract
content/                 word lists, sound pairs, syllables, prompt templates (JSON)
frontend/                game UI (framework still to be picked by Frontend A)
infra/                   droplet setup script
```

## 6. Open questions for the team (decide on Day 1)

1. Add an optional `player_id` (and `game`) to `/score` so the server can record progress?
2. Add an optional `heard_text` field to `/score` so debug mode runs through the real scoring code?
3. Have the server measure response time from the audio (speech onset) instead of using `shown_at_ms`?
4. Judges need a live URL: frontend on Vercel, droplet API behind HTTPS. Who owns this?
5. Keep the droplet up during judging (credit budget), or make the app fail gracefully?
