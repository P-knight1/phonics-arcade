# Project Handoff — Voice-Based Reading Games for Dyslexia (AMD Hackathon)

> Read this whole file before writing code. It is the source of truth for scope, architecture, the API contract, and team roles.

## 1. Context

- **Event:** AMD Developer Hackathon: ACT III (lablab.ai). Online build 12–18 October 2026.
- **Team:** 4 people (one member left on Day 1) working in parallel for 5 days (Tue 13 – Sat 17 Oct). Submit on Sat 17 Oct, a day before the deadline.
- **Track:** Track 4, "Create a New Kind of Experience". (Health & Wellbeing is NOT a good fallback: it is about the patient journey — intake, discharge, records. See section 12.)
- **One-liner:** A set of voice-controlled reading games for people with dyslexia. The player reads aloud, AI running on AMD GPUs scores their speech at the sound level, and an adaptive "brain" personalises the next exercises and stories for each player.

## 2. Hard requirements (do not break these)

1. **AMD must power a meaningful part of the working product.** All AI inference (speech recognition, phoneme scoring, LLM) runs on an AMD Developer Cloud GPU droplet (MI300X, ROCm). The demo must visibly use it.
2. **No medical claims.** This is NOT a diagnostic tool. Never use the words "diagnose" or "diagnosis" in UI, README, or pitch. Use "practice", "support", "builds reading and memory skills". Do not claim the game "improves memory" as a proven outcome.
3. **Submission requirements:** public GitHub repo, containerised app (Docker), a README that runs, demo video, slide deck, cover image.
4. **License:** MIT. Submissions must be original.
5. **Never commit secrets.** API keys, droplet IPs and tokens go in `.env` (git-ignored). Provide `.env.example`.
6. **Secure the vLLM endpoint** (API key or firewall). Do not leave it open on a public IP.

## 3. Architecture

```
Browser (game UI + microphone)          ← runs anywhere, no GPU needed
        │  HTTP (JSON + audio)
        ▼
Backend API — FastAPI (Python)           ← deployed on the AMD droplet
        ├── Speech: Whisper (general transcription)
        ├── Scoring: phoneme recognition model (e.g. facebook/wav2vec2-lv-60-espeak-cv-ft)
        └── LLM: open model (e.g. Llama / Qwen) served by vLLM, OpenAI-compatible API
```

**Important technical note:** Whisper tends to output the *intended* word, not what was actually said (a player reading "bog" for "dog" may still be transcribed as "dog"). Use Whisper only for general understanding. Use the **phoneme model** for scoring.

**Nobody needs ROCm locally.** ROCm lives on the droplet. Everyone (including the Mac user) develops locally and talks to the droplet over HTTP/SSH.

## 4. API contract (FROZEN — change only with whole-team agreement)

All endpoints are JSON unless noted. Base URL comes from `API_BASE_URL` in `.env`.

### `POST /score`
Request: `multipart/form-data`
- `target` (string) — the word or sound sequence the player should say
- `audio` (file, webm/wav)
- `shown_at_ms` (int, optional) — when the prompt appeared, for response time

Response:
```json
{
  "heard": "bog",
  "target_phonemes": ["d", "ɒ", "g"],
  "heard_phonemes": ["b", "ɒ", "g"],
  "correct": false,
  "phoneme_accuracy": 0.67,
  "response_ms": 1840,
  "error_type": "letter_reversal"
}
```
`error_type` is one of: `none`, `letter_reversal` (b/d, p/q), `missing_sound`, `added_sound`, `substitution`, `no_response`.

### `POST /next-exercise`
Request:
```json
{ "player_id": "p1", "game": "word_flash", "history": [ /* recent /score results */ ] }
```
Response:
```json
{ "game": "word_flash", "level": 3, "items": ["bat", "dad", "bed"], "display_ms": 1200, "reason": "practising b/d" }
```

### `POST /story`
Request:
```json
{ "player_id": "p1", "weak_sounds": ["b", "d"], "interests": ["football"] }
```
Response:
```json
{ "story": "...", "questions": [ { "q": "...", "answer": "..." } ] }
```

### `GET /progress/{player_id}`
Response:
```json
{ "sessions": [ { "date": "2026-10-14", "accuracy": 0.72, "avg_response_ms": 1650, "errors": { "letter_reversal": 4, "missing_sound": 2 } } ] }
```

### Proposed additions (backward compatible; the backend already supports them; confirm on Day 1)
Nothing above changes. Clients that ignore these keep working.

- **Accounts:** `POST /players` `{ "name": "Sam", "password": "…", "interests": ["football"] }` registers (`201`; `409` if the name is taken, ignoring case). `POST /login` `{ "name", "password" }` logs in (`401` if wrong). Both return `{ "player_id", "name", "interests", "token" }`. `GET /me` returns the profile. `POST /logout` ends the login. Logins expire after 30 days.
- **Guest play:** `POST /guest` (optional body `{ "interests": [...] }`) → `201 { "player_id", "name": "Guest", "interests", "token" }`. It works exactly like a login during the visit. The frontend keeps the token in memory only, so leaving the page ends it. The server deletes all guest data on `/logout`, or 24 hours after the guest started.
- **Every request sends `Authorization: Bearer <token>`.** `/next-exercise`, `/story` and `/progress` require it (`401` without it), and their `player_id` must be the logged-in player's own (`403` otherwise). `/score` saves the attempt to the logged-in player, and without a token it scores but doesn't save.
- `/score` takes 2 **optional** form fields:
  - `game`: e.g. `word_flash`, stored with the attempt.
  - `heard_text`: debug mode. The typed text is scored instead of audio, so the whole pipeline (scoring, progress, levels) works with no mic and no GPU.
- `/score` with **no `audio` and no `heard_text`** means the player didn't answer (e.g. the word disappeared): `error_type: "no_response"`.
- `response_ms` is `null` when `shown_at_ms` isn't sent. `shown_at_ms` is the browser's `Date.now()` when the prompt appeared. `avg_response_ms` in `/progress` is `null` on a day with no response times.
- `/next-exercise` `history` = the `/score` results of **the round just played** (empty on the first call). The server remembers each player's level per game.
- `/story` with an empty `weak_sounds` uses the player's weak sounds from their recorded attempts. An empty `interests` uses the player's profile.
- `/progress` sessions also include `phoneme_accuracy` (average share of sounds said right that day). `GET /progress/{player_id}?game=word_flash` limits it to one game.
- `accuracy` in `/progress` = word accuracy (share of attempts fully correct) per day. `errors` counts only mistakes.

## 5. Mock-first rule

Day 1 priority for the backend is a **mock server** implementing every endpoint above with fake but schema-valid data (random `correct`, fixed story, etc.). Frontend work must never wait on real AI.

Every game must also support **placeholder input**: under the mic button, show "✓ Said it right" / "✗ Said it wrong" buttons and a text box for typing what was "heard". When real scoring works, the mic becomes primary and the buttons remain as a debug mode (toggle via `?debug=1` or an env flag).

## 6. Games (scope)

Each game is grounded in established dyslexia research. Do not drift into generic brain-training.

| Priority | Game | What it does | Research basis |
|---|---|---|---|
| 1 | **Sound Surgery** | "Say *cat* without the *c*", "swap the first sound of *map* with *s*" | Phonemic awareness training (strongest evidence) |
| 1 | **Word Flash** | Word appears briefly, then disappears; player reads it aloud. Display time shortens on success, slows and repeats patterns on struggle. Words follow a phonics progression, not random. | Fluency/automaticity; speech-recognition reading tutors (Project LISTEN) |
| 1 | **Echo Chain** | Game shows/plays a sequence of **sounds and syllables** (not random words); player repeats in order; chain grows by one. | Phonological working memory (framed as phonological practice, not general memory training) |
| 2 | **Story Recall** | LLM writes a short story using the player's weak sounds + interests; read aloud; player answers questions by voice. | Engagement/personalisation layer |
| — | ~~Beat Reader~~ | **Cut** (team of 4). Say syllables on the beat. | Rhythm-based reading training |
| — | **Progress Dashboard** | Accuracy, response time, error types over sessions. | Shows "improvement" in demo |

**Metrics tracked:** word accuracy, phoneme accuracy, response time, error types, progress across sessions.

## 7. Team roles

Two pairs: **members 3 and 4 build what the player sees** (games, research, content), **members 1 and 2 build what listens and thinks** (audio input, AI, cloud).

| # | Role | Owns |
|---|---|---|
| 1 | AI & Cloud | AMD credits (chase them), droplet, vLLM, HTTPS for the API, GPU timings, judging uptime, `infra/setup_droplet.sh` |
| 2 | Backend, Input & AI | Backend (done), **`speech.recognize()`** (audio → sounds; on CPU first, AMD GPU once the droplet is up), evaluation script, `scoring.normalize()` tuning, frontend `Dockerfile` + compose, public README |
| 3 | Frontend & games A | `frontend/src/shell/` (login, guest, menus, mic), **the shared game screen**, Word Flash, Sound Surgery: the research behind these games and their `content/` files |
| 4 | Frontend & games B + **pitch** | Echo Chain, Story Recall, Progress Dashboard: their research and `content/` files, plus `feedback.json`, the story prompt and demo personas. **Owns the pitch:** business case, deck, demo script and video, submission text, team admin (lablab.ai registration, deadline) |

**Frontend split by folder:** member 3 owns `frontend/src/shell/` and the Word Flash and Sound Surgery folders; member 4 owns the Echo Chain, Story Recall and dashboard folders. Neither edits the other's folders; changes to shared files (`api.ts`, `App.tsx`, `styles.css`) are agreed first.

## 8. Timeline

| Day | Goal |
|---|---|
| 1 (Tue 13) | Agree API (this file). Mock API live. Droplet running. |
| 2 (Wed 14) | Games 1–3 playable with placeholders. Real scoring works on recorded clips. Content lists done. |
| 3 (Thu 15) | **Integration:** swap mocks for real AMD endpoints, mic replaces buttons. |
| 4 (Fri 16) | Adaptive brain + stories connected. Dashboard on real data. **Feature freeze in the evening.** |
| 5 (Sat 17) | Record demo (two different players, game adapting differently). Submit. |

**Fallback:** if speech scoring is unreliable by Thursday night, demo Word Flash with the real mic and keep button input for the others.

### 8.1 Deliverables by day

**Rules:**
- A deliverable may only need things delivered on an **earlier** day. That's what the "Needs" column shows.
- Everything is merged to `main` **by the end of its day**, so the next day can rely on it.
- Two same-day steps are on purpose: the **D3 evening fallback decision**, and the **D5 submission** (after that morning's recording).
- The AMD credits are outside our control. Until they arrive, speech runs on CPU and frontends use mock mode or typed answers (`heard_text`).

R1 = AI & Cloud · R2 = Backend, Input & AI · R3 = Frontend & games A · R4 = Frontend & games B + pitch

**Days 0–1 — Mon 12, Tue 13 (done)**

| Who | Deliverable | Needs |
|---|---|---|
| R2 | Mock API, real scoring + text-to-sound conversion, SQLite progress, accounts + guest play, adaptive `/next-exercise`, `/story` code, Docker image built and tested, `docs/backend-guide.md` | — |
| R3 | Frontend scaffold (React + Vite), `api.ts`, login / register / guest, menu, mic recorder, Word Flash with debug buttons | Backend (D0) |

**Day 2 — Wed 14**

| Who | Deliverable | Needs |
|---|---|---|
| All | **Record evaluation clips** (about 10 minutes each, adults on the team): the starter words read correctly and with deliberate mistakes (bog/dog, dropped sounds). Audio stays outside git | Starter list (D0) |
| R1 | Chase the AMD credits (organisers on Discord, every member applies). The moment they arrive: droplet, vLLM on localhost with an API key, backend running there in Docker | Backend image (D0) |
| R2 | Merge the frontend branch. **`speech.recognize()` working on CPU** (ffmpeg decode → phoneme model), tested on your own recordings | `speech.py` interface (D0) |
| R3 | **Shared game screen** (show → answer → score → feedback → round summary) extracted from Word Flash, with Word Flash rebuilt on it. Review fixes: no logout when the server is unreachable on reload, "✗ Said it wrong" needs text, clear message for a too-long interest. Research for Word Flash and Sound Surgery → `word_flash.json` v1 | Shell + Word Flash (D1) |
| R4 | Research for Echo Chain and Story Recall → `echo_chain.json` (syllables checked with `g2p.phonemes()`). `feedback.json`, two demo personas, `labels.csv` for the clips. **Team admin:** lablab.ai registration, deadline into section 12. **Progress Dashboard** on mock data | Mock API + formats (D0) |

**Day 3 — Thu 15 (integration)**

| Who | Deliverable | Needs |
|---|---|---|
| R1 | **HTTPS for the droplet API.** Measure GPU seconds per `/score` and per `/story`. Plan for keeping the droplet up during judging. `infra/setup_droplet.sh` | Droplet (D2) |
| R2 | Speech running on the droplet's GPU. **Evaluation script** run on the labelled clips → agreement %, sent to R4 for the deck. Tune `scoring.normalize()` from the mismatches. Fix integration bugs | `recognize()` (D2), droplet (D2), clips + labels (D2) |
| R3 | **Sound Surgery** on the shared screen (`sound_surgery.json`). **Mic replaces buttons** in Word Flash and Sound Surgery, against the droplet | Shared screen (D2), droplet (D2) |
| R4 | **Echo Chain** on the shared screen, with the mic. Dashboard on real data. Story prompt checked on the droplet's model for both personas. Business case + deck draft | Shared screen (D2), droplet (D2), personas (D2), dashboard (D2) |
| All | **The two demo personas each play one short round on the real system**, and again on D4 and D5, so the dashboard shows real progress over 3 days | Droplet (D2), personas (D2) |
| All | **Fallback decision tonight:** is mic scoring reliable enough to demo every game? | Integration (D3) |

**Day 4 — Fri 16 (feature freeze in the evening)**

| Who | Deliverable | Needs |
|---|---|---|
| R1 | Droplet stable. Judging budget confirmed. Help R3 with Vercel + HTTPS | Plan + HTTPS (D3) |
| R2 | Tune level-up/level-down thresholds from real play. Frontend `Dockerfile` + `docker-compose.yml`. Draft the public README | Real play (D3), frontend (D3) |
| R3 | **Frontend live on Vercel**, calling the HTTPS API. Polish. Test R4's games | HTTPS (D3), games (D3) |
| R4 | **Story Recall** (first thing to cut if time runs out). Deck final with **cost per session** and the evaluation result. Demo script, rehearsed. Submission text (title ≤ 50 characters, short ≤ 255, long ≥ 100 words). Test R3's games | GPU timings + evaluation (D3), deck draft (D3), games (D3) |

**Day 5 — Sat 17 (submit)**

| Who | Deliverable | Needs |
|---|---|---|
| All | Record the demo: two players, the game adapting differently. MP4, ≤ 5 minutes | Frozen app (D4), script (D4) |
| R2 | Public README final. Clean `docker compose up` from a fresh clone | Frozen app (D4) |
| R4 | Slides as PDF. Submit on lablab.ai with the repo, live URL, video, deck and cover image | Everything above |

## 9. Suggested repo structure

```
/
├── HANDOFF.md           ← this file
├── README.md            ← setup + run instructions (must actually work)
├── LICENSE              ← MIT
├── .env.example
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py      ← FastAPI, routes
│   │   ├── mock.py      ← mock responses (MOCK_MODE=1)
│   │   ├── speech.py    ← Whisper + phoneme model
│   │   ├── scoring.py   ← phoneme comparison, error classification
│   │   ├── brain.py     ← LLM calls via OpenAI client → vLLM
│   │   └── schemas.py   ← Pydantic models matching section 4
│   ├── tests/
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── shell/       ← menus, player select, mic recorder
│   │   ├── games/       ← word-flash, sound-surgery, echo-chain, story-recall, beat-reader
│   │   ├── dashboard/
│   │   └── api.ts       ← single API client, reads API_BASE_URL
│   └── Dockerfile
├── content/             ← word lists, sound pairs, syllable sequences, prompts (JSON)
└── infra/
    └── setup_droplet.sh ← rebuild the droplet from scratch quickly
```

## 10. Conventions

- Backend: Python 3.11+, FastAPI, Pydantic models that match section 4 exactly. `MOCK_MODE=1` env var switches every endpoint to mock data.
- LLM access: the standard `openai` Python client pointed at the vLLM base URL (`VLLM_BASE_URL`, `VLLM_API_KEY`, `VLLM_MODEL` in `.env`).
- Frontend: one API client file. No hard-coded URLs.
- Git: one branch per person/feature, merge to `main` at least daily. Keep `main` runnable.
- Push often. The droplet's data is lost if credits run out, so it must be rebuildable from `infra/setup_droplet.sh`.
- Shut the droplet down when nobody is using it.

## 11. First tasks

1. Scaffold the repo structure in section 9, with MIT license, `.env.example`, `.gitignore` (including `.env`), and a README skeleton.
2. Implement `backend/app/schemas.py` exactly matching section 4.
3. Implement the mock server (`MOCK_MODE=1`) for all endpoints, with a test per endpoint validating the schema.
4. Implement `scoring.py` as pure functions (target phonemes vs heard phonemes → accuracy + error_type), with unit tests. No GPU needed.
5. Write `docker-compose.yml` running backend (mock mode) + frontend locally.
6. Then continue with whichever role's tasks the current user is working on (ask them).

## 12. Event rules & judging (checked 12 Oct 2026, re-check at kickoff)

Sources: [event page](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii), [rule book](https://lablab.ai/hackathon-rules), [submission guidelines](https://lablab.ai/ai-articles/hackathon-guidelines). Breaking the submission guidelines can mean lower scores or disqualification.

**Eligibility**
- Teams of 1–6. **Every member** must be in the AMD AI Developer Program and sign up with AMD (new members get $100 of AMD credit).
- The AMD component must be part of the **working product judges see**, not only a slide.
- Must be original work and MIT-compliant. Plagiarism means immediate disqualification.
- Submission deadline: **not published yet** ("to be announced"). Get it from the kickoff or Discord. Manual submission is possible for 6 hours afterwards, but only with organiser approval.

**Judged on:** Presentation · Business value · Application of technology · Originality (no weights published).

**Track 4 asks every team to explain the following (put each one in the deck, the video and the long description):**
1. What we created.
2. What the models generated or decided: phoneme scoring, story generation, and the choice of next exercise.
3. How we control quality and consistency, e.g. phoneme scoring checked on recorded clips, stories limited to word lists and reading level.
4. **Cost per generated experience** (GPU-seconds per session × droplet $/hour).
5. **Who would pay, and why** (e.g. adult learners, tutors, adult-education and dyslexia support services).
6. How the experience **changes for at least two audiences or inputs**: our demo with two different players.
7. Why this wasn't practical before generative AI.

**Submission checklist**
- [ ] Title ≤ 50 characters. Short description ≤ 255 characters. Long description ≥ 100 words.
- [ ] Track, technology tags (AMD Developer Cloud, ROCm, vLLM, …), and the "Additional information" field: how it scales beyond the hackathon.
- [ ] Cover image: PNG or JPG, 16:9.
- [ ] Video: **MP4, ≤ 5 minutes, < 300 MB**.
- [ ] Slides: **PDF**.
- [ ] Public GitHub repo, a README that runs, a containerised app (Docker), no secrets committed.
- [ ] **Live application URL** for judges to try. The rule book names Streamlit, Replit or Vercel as demo platforms.

**Consequences for our architecture**
- A live URL means the frontend goes on Vercel (HTTPS). Browsers block calls from an https page to plain-http APIs, and the mic only works on https, so **the droplet API needs HTTPS** too (a Caddy reverse proxy with a domain, or a Cloudflare tunnel).
- Judging happens **after** the deadline. Either the droplet stays up (budget credits for it), or the demo URL must fail gracefully. Decide this by Thursday.
