# Project Handoff — Voice-Based Reading Games for Dyslexia (AMD Hackathon)

> Read this whole file before writing code. It is the source of truth for scope, architecture, the API contract, and team roles.

## 1. Context

- **Event:** AMD Developer Hackathon: ACT III (lablab.ai). Online build 12–18 October 2026.
- **Team:** 5 people working in parallel for 5 days (Tue 13 – Sat 17 Oct). Submit on Sat 17 Oct, a day before the deadline.
- **Track:** Track 4, "Create a New Kind of Experience" (Health & Wellbeing is the fallback).
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

**Important technical note:** Whisper tends to output the *intended* word, not what was actually said (a child reading "bog" for "dog" may still be transcribed as "dog"). Use Whisper only for general understanding. Use the **phoneme model** for scoring.

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
| 3 | **Beat Reader** | Say syllables on the beat. Only if time allows. | Rhythm-based reading training |
| — | **Progress Dashboard** | Accuracy, response time, error types over sessions. | Shows "improvement" in demo |

**Metrics tracked:** word accuracy, phoneme accuracy, response time, error types, progress across sessions.

## 7. Team roles (all start Day 1 in parallel)

| # | Role | Owns | Day-1 deliverable |
|---|---|---|---|
| 1 | AI & Infrastructure | AMD droplet (vLLM Quick Start image), Whisper + phoneme model, SSH access for teammates, real `/score` | Droplet up, vLLM answering, models tested on recorded clips |
| 2 | Backend & Scoring | FastAPI app, mock endpoints, scoring logic (phoneme comparison, error classification), adaptive brain prompts | Mock API pushed and runnable |
| 3 | Frontend A | Game shell (menus, player select, mic recording), Word Flash, Sound Surgery | Shell + one game playable with placeholder buttons |
| 4 | Frontend B | Echo Chain, Beat Reader (optional), Progress Dashboard | Echo Chain playable with placeholder buttons |
| 5 | Content, Research & Pitch | Word lists per phonics level, sound pairs, syllable sequences, LLM prompt templates, research slide, deck, demo script, submission text | Content JSON v1 in `content/` |

## 8. Timeline

| Day | Goal |
|---|---|
| 1 (Tue 13) | Agree API (this file). Mock API live. Droplet running. |
| 2 (Wed 14) | Games 1–3 playable with placeholders. Real scoring works on recorded clips. Content lists done. |
| 3 (Thu 15) | **Integration:** swap mocks for real AMD endpoints, mic replaces buttons. |
| 4 (Fri 16) | Adaptive brain + stories connected. Dashboard on real data. **Feature freeze in the evening.** |
| 5 (Sat 17) | Record demo (two different players, game adapting differently). Submit. |

**Fallback:** if speech scoring is unreliable by Thursday night, demo Word Flash with the real mic and keep button input for the others.

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
