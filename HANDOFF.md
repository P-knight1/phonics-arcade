# Project Handoff: Arabic reading practice for dyslexia (KDA AI competition)

> Read this whole file before writing code. It is the source of truth for scope, architecture, the API contract and team roles. The science behind every feature is in [docs/research.md](docs/research.md); how to use the backend is in [docs/backend-guide.md](docs/backend-guide.md).

## 1. Context

- **Competition:** the Kuwait Dyslexia Association (KDA) AI competition: AI projects that address dyslexia (practice tools or screening). It requires a **substantial use of AI**. **Deadline: 30 November 2026.** We aim to submit on 29 November.
- **Team:** 4 people.
- **What we build:** a working demo and proof of concept of an **Arabic reading-practice tool**. The player reads vowelized Modern Standard Arabic aloud; our own Arabic phoneme model hears which sounds they actually said; the app recognises Arabic-specific dyslexic error patterns (short vowels, letters that differ only by dots, vowel length, letter order) and adapts the practice to them.
- **Users:** children with dyslexia are the target users. **The pilot is with consenting adults only**; children are not tested or recorded in this project.
- **One-liner for judges:** *Google Read Along accepts; we notice.* Precise, kind feedback on the errors that define Arabic dyslexia, built on Arabic reading research.

## 2. Hard requirements (do not break these)

1. **AI must be central and visible** (section 3): our fine-tuned Arabic phoneme model, error profiling, adaptive learning, generated vowelized texts, Arabic speech synthesis.
2. **No medical claims.** This is a practice and support tool. Never use "diagnose" or "diagnosis". A screening module may appear only as *future work, designed but not validated*.
3. **Science first:** every game and claim maps to a source in `docs/research.md`. Say "based on evidence from other languages" where the evidence isn't Arabic yet (e.g. rhythmic reading).
4. **Pilot ethics:** adults only, written consent, recordings stored privately and **never committed to git**, deleted on request (checklist in `docs/research.md` section 7).
5. **Never commit secrets.** Keys and tokens go in `.env` (git-ignored); `.env.example` has placeholders.
6. **Arabic first:** right-to-left UI, fully vowelized MSA content, dyslexia-friendly typography (generous spacing, large marks).
7. **License:** MIT. Original work.

## 3. Architecture and where AI is used

```
Browser (React, RTL Arabic UI, microphone)
        │  HTTP (JSON + audio)
        ▼
Backend: FastAPI (Python)
        ├── speech.py   our Arabic phoneme model (fine-tuned wav2vec2 family; GPU if present, else CPU)
        ├── g2p.py      target text → phonemes (espeak-ng 'ar' for Arabic, 'en-gb' for English; picked by script)
        ├── scoring.py  phoneme comparison + Arabic error types
        ├── brain.py    adaptive next exercise; vowelized stories from an LLM (any OpenAI-compatible endpoint)
        └── db.py       SQLite: accounts, guests, attempts, levels
ml/                     training and evaluation of the phoneme model (data and models git-ignored)
```

| # | AI component | Status |
|---|---|---|
| 1 | **Arabic phoneme recognition**: our fine-tuned model | Baseline + fine-tuning in progress (`ml/`) |
| 2 | **Error profiling**: Arabic error types per attempt, weak sounds per player | Done (`scoring.py`, `brain.py`) |
| 3 | **Adaptive learning**: mastery per sound (Bayesian Knowledge Tracing) picks what to practise; level rules set difficulty | Done (`brain.py`) |
| 4 | **Generative AI**: short stories using only mastered letters, fully vowelized, checked automatically | Prompt done; validation planned |
| 5 | **Arabic speech synthesis** for listening games | Planned (open model or recorded prompts) |

**Important technical note:** general speech-to-text writes the *intended* word, not what was said. Scoring uses the **phoneme model**, never plain transcription.

## 4. API contract (change only with whole-team agreement)

All endpoints are JSON unless noted. Base URL comes from `API_BASE_URL` in `.env` (frontend: `VITE_API_BASE_URL`). Arabic targets must be fully vowelized; the language is picked from the text's script.

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
`error_type` is one of: `none`, `letter_reversal` (b/d, p/q), `missing_sound`, `added_sound`, `substitution`, `no_response`, and for Arabic targets `dot_confusion` (ب/ت/ث, ج/ح/خ, …), `vowel_error` (wrong short vowel), `vowel_length` (long ↔ short vowel), `letter_position` (two neighbouring letters swapped).

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

### Additions (part of the contract; the backend and frontend use them)

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

The backend has a **mock mode** implementing every endpoint above with fake but schema-valid data (random `correct`, fixed story, etc.). Frontend work must never wait on real AI.

Every game must also support **placeholder input**: under the mic button, show "✓ Said it right" / "✗ Said it wrong" buttons and a text box for typing what was "heard". When real scoring works, the mic becomes primary and the buttons remain as a debug mode (toggle via `?debug=1` or an env flag).

## 6. Games (scope)

Each game maps to evidence in `docs/research.md` section 2. Do not drift into generic brain training.

| Priority | Game | What it does | Evidence |
|---|---|---|---|
| 1 | **Word Flash** | A vowelized word appears briefly, then hides; the player reads it aloud. Display time adapts; words follow a progression by letter families. Later: vowel marks fade as the player masters them | Reading fluency; speech-recognition reading tutors; short-vowel teaching |
| 1 | **Sound Surgery** | "Say كَتَبَ without the كـ", "swap the first sound": phonemic awareness in Arabic | Phonological training (several small Arabic studies, strong international evidence) |
| 1 | **Rhythmic Reading** | Read syllables in time with a beat; timing and sounds scored from the voice | Rhythmic Reading Training (Italy, small trials) and a music-training RCT (Flaugnacco 2015); **not yet tested in Arabic** |
| 2 | **Roots** | Find and read words from one root (ك ت ب → كَتَبَ، كاتِب، مَكتَب) | Morphological awareness: the strongest predictor of Arabic comprehension |
| 2 | **Echo Chain** | Repeat a growing chain of syllables | Phonological working memory |
| 3 | **Story Recall** | A generated, fully vowelized story with the player's weak sounds and interests, then questions | Engagement and personalisation |
| — | **Progress Dashboard** | Word accuracy, phoneme accuracy, speed, error types over sessions | Shows progress in the demo |

## 7. Team roles

| # | Role | Owns |
|---|---|---|
| 1 | Speech model & data | `ml/`: datasets, evaluation, fine-tuning, the adult pilot's recording and labelling pipeline |
| 2 | Backend & scoring | `backend/`: scoring, Arabic error types, adaptive learning, stories, integrating the model, Docker, README |
| 3 | Frontend & games A | `frontend/src/shell/`, the shared game screen, RTL Arabic UI, Word Flash, Sound Surgery, Rhythmic Reading |
| 4 | Frontend & games B + **pitch** | Echo Chain, Roots, Story Recall, Dashboard, `content/` (vowelized word lists, feedback wording), the pitch (slides, demo video, science page, submission), KDA contact |

**Frontend split by folder:** each member owns their own game folders; shared files (`api.ts`, `App.tsx`, `styles.css`) change only after agreeing.

## 8. Timeline (15–30 November)

| By | Milestone | Who |
|---|---|---|
| Mon 17 | Arabic scoring and content in the backend (done). Phoneme model baseline measured on Arabic; first fine-tune. RTL Arabic UI; Word Flash in Arabic | 1, 2, 3 |
| Thu 20 | Fine-tuned model inside the backend. Sound Surgery and Rhythmic Reading playable. Consent form ready; **adult pilot starts** (correct readings + deliberate errors, labelled) | all |
| Mon 24 | Pilot result: agreement between the model and human labels. Roots and Echo Chain playable. Dashboard on real data | 1, 2, 3, 4 |
| Wed 26 | **Feature freeze.** Only bug fixes after this | all |
| Fri 28 | Demo video, slides, science page, submission text final | 4 (all help) |
| Sat 29 | Submit (a day before the deadline) | 4 |

**Fallback:** if the phoneme model is unreliable on Arabic by 24 November, demo with typed answers (debug mode) for the weak parts and present the model's measured accuracy honestly.

## 9. Repo structure

```
/
├── HANDOFF.md, README.md, LICENSE, .env.example, docker-compose.yml
├── backend/          FastAPI app (app/), tests/, requirements.txt, requirements-speech.txt, Dockerfile
├── frontend/         React + Vite (src/shell, src/games/<game>, src/api.ts)
├── ml/               phoneme model: README.md, RESULTS.md, scripts (data/ and models/ are git-ignored)
├── content/          vowelized word lists per game, prompts
└── docs/             research.md (science), backend-guide.md (integration)
```

## 10. Conventions

- Backend: Python 3.11+, FastAPI, Pydantic models matching section 4. `MOCK_MODE=1` fakes every AI-dependent endpoint.
- LLM access: the standard `openai` client pointed at any OpenAI-compatible endpoint (`VLLM_BASE_URL`, `VLLM_API_KEY`, `VLLM_MODEL` in `.env`; the names are historical).
- Frontend: one API client (`api.ts`), no hard-coded URLs.
- Git: one branch per person or feature, merge to `main` daily, keep `main` runnable and tests green.
- Recordings and datasets never go into git.

## 11. Competition: KDA AI competition

- Organiser: the Kuwait Dyslexia Association. Scope: AI solutions for dyslexia (practice tools or screening). Requirement: substantial use of AI. Deadline: 30 November 2026.
- **To fill in when known:** official rules, judging criteria, submission format, presentation length. Keep `docs/research.md` sections 8 and 9 in sync.
