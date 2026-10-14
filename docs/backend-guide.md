# Backend guide for the team

What the backend does today, what is still missing, and exactly how each role uses it.
The API contract is section 4 of [HANDOFF.md](../HANDOFF.md). Read the **"Proposed additions"** there as well: the backend already supports them.

---

## 1. Status (12 Oct, evening)

| Part | Status | Notes |
|---|---|---|
| Mock mode (`MOCK_MODE=1`), all endpoints | ✅ Done | Fake data, no setup. Use it for frontend work. |
| Scoring: sounds compared, accuracy, error type | ✅ Done | Pure functions, tested. |
| Text → sounds (espeak-ng) | ✅ Done | Bundled, so nothing to install. British English. |
| Debug mode through the real pipeline (`heard_text`) | ✅ Done | Typed answers are scored, saved and adapt the level. |
| Accounts: register / login / logout with a password, login tokens | ✅ Done | Each player sees only their own data. Real in both modes. |
| Guest play (no account) | ✅ Done | Fully personalised during the visit; deleted on logout or after 24 hours. |
| Progress saved per player (SQLite) + `/progress` | ✅ Done | Per day: word accuracy, phoneme accuracy, speed, errors. Filter by game. |
| Adaptive `/next-exercise` | ✅ Done for Word Flash | Needs a content file per game (see Content). |
| `/story` via vLLM | 🟡 Built, not tried on a real model | Needs the droplet. Returns `503` until then. |
| Audio → sounds (`speech.py`) | 🟡 Works on CPU | b/d and other consonants detected from real webm audio. Vowels need accent tuning on real clips. GPU on the droplet: Day 3. |
| Content for Sound Surgery and Echo Chain | ❌ Missing | Content. |
| Docker image | ✅ Builds and runs | Tested on Linux x86-64 (WSL): all 34 tests pass in the container. GPU support comes with `speech.py` (section 5). |
| HTTPS for the API, live URL for judges | ❌ Planned | HTTPS: AI & Infrastructure, Day 3. Vercel: Frontend, Day 4 (HANDOFF.md section 8.1). |
| Checking spoken Story Recall answers | ❌ Not designed | Needs a team decision (section 7). |

---

## 2. Running it

Set `MOCK_MODE` in `.env` (copy `.env.example` first):

- `MOCK_MODE=1`: fake data. Use this for building screens.
- `MOCK_MODE=0`: the real thing. Use this to check that your game really scores, saves and adapts. Typed answers work fully; audio and stories return `503` until the droplet is connected.

Start it (the README has full setup):
```bash
cd backend
uvicorn app.main:app --reload --env-file ../.env
```
Then open **http://localhost:8000/docs** to try every endpoint in the browser. `GET /health` shows the mode.

### Stories without the droplet: a local AI model
`/story` talks to the language model through the standard OpenAI-style API, so any compatible server works with **no code changes**. Until the droplet is up, anyone with a capable computer can use [Ollama](https://ollama.com) (version 0.5 or newer) on your own computer:

```bash
ollama pull qwen2.5:3b        # same model family as the droplet; ~2 GB. Strong machine: qwen2.5:7b
```

Then in your `.env` (never committed):
```
MOCK_MODE=0
VLLM_BASE_URL=http://localhost:11434/v1
VLLM_API_KEY=ollama
VLLM_MODEL=qwen2.5:3b
```

Run the backend with Python, not Docker: inside a container, `localhost` is the container, so it can't reach Ollama. This is **for development only**. The demo must use the AMD droplet, and a smaller model writes differently, so stories get checked again on the droplet (Day 3). Switching is only `.env`: put the droplet's `VLLM_BASE_URL`, `VLLM_API_KEY` and `VLLM_MODEL` in place of the Ollama values (get them from AI & Infrastructure privately, never in chat or git).

---

## 3. Frontend (member 3): shell, accounts, Word Flash, Sound Surgery

### Accounts: register, log in, log out
Players have an **account with a nickname and password**. Logging in gives a **token**. Send it with every request, and the backend only ever shows that player their own data.

```js
// Register (also logs you in)
let r = await fetch(`${API_BASE_URL}/players`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ name: "Sam", password: "at least 8 chars", interests: ["football"] }),
});
// 201 → { player_id, name, interests, token } · 409 → name taken (ignoring case) · 422 → see the rules below

// Log in
r = await fetch(`${API_BASE_URL}/login`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ name: "Sam", password: "…" }),
});
// 200 → { player_id, name, interests, token } · 401 → wrong name or password

const { player_id, token } = await r.json();
const auth = { Authorization: `Bearer ${token}` };   // add to EVERY request below

// Page reload: check the saved token still works and get the profile back
r = await fetch(`${API_BASE_URL}/me`, { headers: auth });  // 200 → { player_id, name, interests } · 401 → show login

// Log out
await fetch(`${API_BASE_URL}/logout`, { method: "POST", headers: auth });  // 204
```

- `name`: 1–30 characters, a **nickname** (no real names needed). `password`: 8–128 characters. `interests`: up to 5, each up to 40 characters.
- Keep `token` and `player_id` in `sessionStorage` (logged out when the tab closes) or `localStorage` (stays logged in). Logins expire after 30 days.
- There's **no list of players**: nobody can see who else has an account.
- **`401`** = not logged in, or the login expired → show the login screen. **`403`** = you sent another player's `player_id` → a frontend bug.
- Accounts are real in mock mode too, so the login flow works from Day 1. In mock mode, game data is still fake.
- Until the droplet API has HTTPS (Day 3), passwords travel unencrypted over the internet, so only use **throwaway test passwords**. On localhost this doesn't matter.
- There's no password reset or account deletion yet. Ask Backend if you need it.

### Play as a guest
A **"Play as guest"** button, for players who don't want an account and for judges who want to try the app fast:

```js
const r = await fetch(`${API_BASE_URL}/guest`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ interests: ["football"] }),   // optional, used for stories
});
const { player_id, token } = await r.json();          // 201, name is always "Guest"
```

- **Use it exactly like a login token.** Scoring, levels, practice on weak sounds, stories and progress all work during the visit.
- **Keep a guest's `token` in a JavaScript variable only**, never in `localStorage` or `sessionStorage`. Leaving or reloading the page then ends the guest visit, so the progress is gone, as intended.
- **The server deletes the guest's data** as soon as you call `POST /logout` with their token, and otherwise after 24 hours. Call `/logout` when the guest presses "Leave".
- Tell the player before they start: *"Guest progress isn't saved. Create an account to keep it."*
- A guest can't turn into an account later (their progress isn't carried over). Ask Backend if you need it.

### Sending an answer
Every answer goes to `POST /score` as `multipart/form-data`:

```js
const form = new FormData();
form.append("target", "dog");                 // what the player should say
form.append("game", "word_flash");            // lowercase letters and _ only
form.append("shown_at_ms", String(shownAt));  // Date.now() when the word appeared
form.append("audio", blob, "answer.webm");    // from MediaRecorder (Safari gives mp4: fine)
const result = await (await fetch(`${API_BASE_URL}/score`, { method: "POST", body: form, headers: auth })).json();
```
Logged in (`auth` header sent), the attempt is saved to that player. Without it, the answer is scored but not saved.

| Situation | Send |
|---|---|
| Mic answer | `audio` |
| Debug "✓ Said it right" | `heard_text` = the target (no `audio`) |
| Debug "✗ Said it wrong" | `heard_text` = what's typed in the box (no `audio`) |
| Word disappeared, player said nothing | neither, giving `error_type: "no_response"` |

What to show: `correct`, `heard` ("you said *bog*"), and `error_type` as friendly text, e.g. `letter_reversal` → "b and d are tricky!". The wording comes from `content/feedback.json` (Content, Day 1). Don't show `*_phonemes` to the player: they're IPA symbols.

### The round loop (Word Flash)
```
items = POST /next-exercise { player_id, game: "word_flash", history: [] }        (with the auth header)
loop:
    for each word in items: show it for display_ms, then hide it → record → POST /score → keep the result
    next = POST /next-exercise { player_id, game, history: <this round's /score results> }
```
The server decides the level and remembers it. `reason` ("practising d", "level up: …") is safe to show.

### Sound Surgery
`/score` already handles it: send the **answer** as `target`.
- "Say *cat* without the *c*" → `target: "at"`. If they still say "cat", they get `added_sound`.
- "Swap the *m* in *map* for *s*" → `target: "sap"`.

Agree with Content on how one item stores both the prompt and the answer. A simple suggestion: `"Say cat without the c|at"`, split on `|`. The backend treats items as plain strings, so any format works.

### Errors
All errors look like `{"detail": "..."}`.
- `401`: not logged in or the login expired → login screen. `403`: another player's `player_id`.
- `422`: bad input (the detail says which field).
- `404` on `/next-exercise`: no content file for that game yet.
- `503`: a model isn't connected yet. Fall back to the debug buttons.

### Typed client
With the backend running: `npx openapi-typescript http://localhost:8000/openapi.json -o src/api-types.ts`.
Read the base URL from config (`API_BASE_URL`). Vite only exposes variables that start with `VITE_`, so name it `VITE_API_BASE_URL` there.

---

## 4. Frontend (member 4): Echo Chain, Progress Dashboard, Story Recall

### Echo Chain
Send the **whole chain** as one target, separated by spaces: `target: "bah dee koo"`. The player's version is compared sound by sound, so `"bah bee koo"` → `letter_reversal`, accuracy 0.83.
Items come from `/next-exercise` with `game: "echo_chain"` once Content adds `content/echo_chain.json`. Until then, use mock mode. How the chain grows (one item per round) is up to the game.

**Open: playing the sounds.** Browser text-to-speech says isolated sounds badly. Agree with Content on recorded clips or syllable-only chains.

### Progress Dashboard
`GET /progress/{player_id}` (with the auth header, your own `player_id`) → one entry per day:
```json
{ "date": "2026-10-14", "accuracy": 0.72, "phoneme_accuracy": 0.86, "avg_response_ms": 1650, "errors": { "letter_reversal": 4, "missing_sound": 2 } }
```
- `accuracy` = share of words fully correct that day (0–1): **word accuracy**.
- `phoneme_accuracy` = average share of sounds said right (0–1): **how precisely** they read. It rises before `accuracy` does, so it shows progress early.
- `avg_response_ms` = average time from the word appearing to the answer arriving: **speed**. Lower is better.
- `avg_response_ms` can be **`null`** (no timed answers that day): draw a gap, not 0.
- `errors` lists only error types that happened. Treat a missing key as 0.
- An unknown player returns `{"sessions": []}`, so show an empty state.
- **One game only:** `GET /progress/{player_id}?game=word_flash`. Leave `game` out for all games together.

Mock mode returns 5 improving days, so you can build the charts now.

### Story Recall
`POST /story` with `{ "player_id": "…" }` and the auth header is enough: empty `weak_sounds` and `interests` are filled from the player's recorded attempts and profile. The reply is `{ story, questions: [{ q, answer }] }`. To read the story aloud, send it through `/score` one sentence at a time (`target` = the sentence). Checking spoken answers to the questions is still open (section 7). It returns `503` until the droplet's language model is connected: use mock mode until then.

---

## 5. AI, input and cloud (members 1 and 2)

### Speech scoring: `speech.recognize()` (done, runs on CPU now)
[backend/app/speech.py](../backend/app/speech.py) turns a recording into sounds with the phoneme model `facebook/wav2vec2-lv-60-espeak-cv-ft`:
- **Audio:** webm/opus (Chrome, Firefox), mp4 (Safari) or wav, decoded with PyAV (it bundles ffmpeg, nothing to install).
- **Device:** the AMD GPU when PyTorch's ROCm build is installed (it reports the GPU as `cuda`), otherwise the CPU. About 0.35 s per word on a laptop CPU.
- **The model loads in the background when the backend starts** (real mode). The first start downloads about 1.3 GB.
- **`heard`** is the target when the answer is right, and empty otherwise (the model gives sounds, not words), so the game shows the feedback message.
- **Under 0.2 s of audio** counts as no answer. **Unreadable audio** → `422`. **Speech packages not installed** → `503`, and games fall back to the debug buttons.

**Install** (not needed for mock mode or typed answers), from `backend/`:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu        # laptop; the droplet uses the ROCm build
pip install -r requirements-speech.txt
```
The Docker image doesn't include speech yet: the droplet image (ROCm PyTorch + GPU access) comes on Day 3.

**Known issue: accents.** Targets use British espeak, so a correct American "dog" (`d ɑ g`) currently scores as a vowel substitution. Consonants, including b/d, come through reliably. Tuning `scoring.normalize()` on the **real evaluation clips** fixes this (not on synthetic voices).

### Check that the sound symbols match (most important on Day 2)
Targets are converted with espeak-ng, British English:
```bash
cd backend
python -c "from app import g2p; print(g2p.phonemes('dog'))"   # ('d', 'ɒ', 'g')
```
Run your model on recorded clips of the starter words in `content/word_flash.json`. Compare its symbols with `g2p.phonemes()`. Report any systematic mismatch (e.g. the model writes `ɑ` where espeak writes `a`) to Backend: that's a one-line fix in `scoring.normalize()`.

### vLLM
- The backend reads `VLLM_BASE_URL` (ending in `/v1`), `VLLM_API_KEY` and `VLLM_MODEL` from `.env`, and never prints them.
- `/story` uses vLLM's JSON-schema structured output (`response_format: json_schema`). Check that your vLLM version and model accept it: call `/story` with `MOCK_MODE=0` once the droplet is up.
- Keep vLLM on `localhost` on the droplet (the backend calls it locally) and keep the API key on.

### Droplet, Docker, HTTPS
- On the droplet: `docker compose up -d --build`.
- The repo's `content/` folder is mounted into the container, and the SQLite file lives in `data/` (kept on the host).
- **Inside the container, `localhost` is the container itself, not the droplet.** `VLLM_BASE_URL=http://localhost:…` won't reach vLLM. On the droplet, either add `network_mode: host` to the backend service (vLLM can then stay bound to 127.0.0.1, which is the safest option), or put the backend and vLLM on one Docker network and use the vLLM container's name.
- **When `speech.py` loads models, the backend container needs the GPU:** a ROCm PyTorch base image instead of `python:3.12-slim`, plus `devices: [/dev/kfd, /dev/dri]` and `group_add: [video]` in compose. Keep `ffmpeg` and `requirements.txt`.
- Judges' browsers need **HTTPS** to the API (a Caddy reverse proxy or a Cloudflare tunnel). CORS is already open.
- Measure the GPU time per `/score` and per `/story` call: Content needs it for "cost per session" in the pitch.

---

## 6. Content and pitch (members 3 and 4; pitch: member 4)

### Word lists: one file per game, `content/<game>.json`
```json
{ "levels": [
    { "focus": "short a words", "display_ms": 2000, "items": ["cat", "hat", "map", "bat", "dad"] },
    { "focus": "short i words", "display_ms": 1700, "items": ["big", "dig", "pin", "sit", "lip"] }
] }
```
- Levels go easiest first (level 1 = first entry). Each level needs **at least 5 items** (one round).
- `focus` is shown to the player as the reason. `display_ms` should get shorter as levels go up.
- File names: `word_flash.json`, `sound_surgery.json`, `echo_chain.json`. A game without a file gets `404` in real mode.
- `content/word_flash.json` is a starter list: replace it with the real phonics progression. Keep plenty of b/d words; the demo relies on them.
- Edits are picked up on the next request, with no restart needed.

### Check how espeak reads your items
```bash
cd backend
python -c "from app import g2p; print(g2p.phonemes('kee'))"
```
Made-up syllables are read oddly ("ki" → `k aɪ`). Spell them the way they should sound ("kee" → `k i`, "bah" → `b ɑ`, "koo" → `k u`).

### Story prompt
`content/prompts/story.txt`. `$weak_sounds` (IPA symbols, e.g. `d, b`) and `$interests` get filled in. Keep the JSON reply format at the end, or `/story` fails.

### For the pitch (Track 4 requires these; see HANDOFF.md section 12)
- **What the AI decides:** the phoneme model scores each sound, the rules choose level and words, and the LLM writes the stories.
- **Quality control:** phoneme scoring is checked on recorded clips, word lists are fixed (the LLM never picks practice words), and story output is forced into a fixed JSON shape.
- **Cost per session:** GPU time from AI & Infrastructure × droplet price per hour.

---

## 7. Decisions needed on Day 1

1. Accept the contract's "Proposed additions" (HANDOFF.md section 4).
2. Sound Surgery item format (suggestion: `"prompt|answer"`).
3. Echo Chain audio: recorded clips, or syllables only?
4. Story Recall: spoken answers like "it was red" can't be checked by `/score`. Add an endpoint (Whisper + a loose match), or check answers with buttons?
5. Response time: keep `shown_at_ms` (includes upload time) or measure speech onset in the audio?
6. The plan gives HTTPS to AI & Infrastructure (Day 3) and Vercel to Frontend (Day 4). Agree? Keep the droplet up during judging?
7. Roles: members 3 + 4 on frontend, games and research (split by folder, member 4 also the pitch), members 1 + 2 on input, AI and cloud (HANDOFF.md sections 7 and 8.1).
