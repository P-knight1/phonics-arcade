# Backend guide for the team

What the backend does today, what is still missing, and how each part of the app uses it.
The API contract is section 4 of [HANDOFF.md](../HANDOFF.md), including its "Additions". The science is in [research.md](research.md).

---

## 1. Status (15 Nov)

| Part | Status | Notes |
|---|---|---|
| Mock mode (`MOCK_MODE=1`), all game endpoints | ✅ Done | Fake, schema-valid Arabic data. Use it for frontend work. |
| Text → sounds (`g2p.py`, espeak-ng) | ✅ Done | Bundled, nothing to install. Arabic (`ar`) or British English (`en-gb`), picked from the text's script. Arabic needs full vowel marks. |
| Scoring: sounds compared, accuracy, error type | ✅ Done | Pure functions, tested. Arabic keeps vowel length. |
| Arabic error types | ✅ Done | `dot_confusion`, `vowel_error`, `vowel_length`, `letter_position` (section 3). |
| Debug mode through the real pipeline (`heard_text`) | ✅ Done | Typed answers are scored, saved and adapt the level. |
| Accounts, login tokens, guest play | ✅ Done | Real in both modes. Each player sees only their own data. |
| Progress saved per player (SQLite) + `/progress` | ✅ Done | Per day: word accuracy, phoneme accuracy, speed, errors. Filter by game. |
| Adaptive learning (BKT) | ✅ Done | Mastery per sound from all saved attempts; `/next-exercise` and `/story` target the weakest sounds (section 4). |
| Adaptive `/next-exercise` | ✅ Done for Word Flash | Other games need a content file each (section 6). |
| Audio → sounds (`speech.py`) | 🟡 Works on CPU | Current model is multilingual; **its Arabic accuracy is being measured in `ml/`**. Our fine-tuned Arabic model replaces it (section 5). |
| `/story` | 🟡 Built, needs an LLM | Any OpenAI-compatible endpoint in `.env`. Returns `503` without one. Automatic checks of the generated text are planned. |
| Docker image | ✅ Builds and runs | Mock mode and typed answers. No speech packages in the image yet. |
| Content for Sound Surgery, Rhythmic Reading, Roots, Echo Chain | ❌ Missing | Content owner (HANDOFF.md section 7). |
| Checking spoken Story Recall answers | ❌ Not designed | Open question (section 8). |

---

## 2. Running it

Set `MOCK_MODE` in `.env` (copy `.env.example` first):

- `MOCK_MODE=1`: fake data. Use this for building screens.
- `MOCK_MODE=0`: the real thing. Use this to check that your game really scores, saves and adapts. Typed answers work fully; audio needs the speech packages (section 5) and stories need an LLM endpoint (section 4), otherwise those calls return `503`.

Start it (the README has full setup, including Windows):
```bash
cd backend
uvicorn app.main:app --reload --env-file ../.env
```
Then open **http://localhost:8000/docs** to try every endpoint in the browser. `GET /health` shows the mode.

---

## 3. Frontend: shell, accounts, games

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
- Accounts are real in mock mode too. In mock mode, game data is still fake.
- Over plain HTTP, passwords travel unencrypted. On localhost this doesn't matter; anywhere else, put the API behind HTTPS or use throwaway test passwords.
- There's no password reset or account deletion yet. Ask Backend if you need it.

### Play as a guest
A **"Play as guest"** button, for players who don't want an account and for anyone trying the demo:

```js
const r = await fetch(`${API_BASE_URL}/guest`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ interests: ["football"] }),   // optional, used for stories
});
const { player_id, token } = await r.json();          // 201, name is always "Guest"
```

- **Use it exactly like a login token.** Scoring, levels, practice on weak sounds, stories and progress all work during the visit.
- **Keep a guest's `token` in a JavaScript variable only**, never in `localStorage` or `sessionStorage`. Leaving or reloading the page then ends the guest visit, as intended.
- **The server deletes the guest's data** as soon as you call `POST /logout` with their token, and otherwise after 24 hours. Call `/logout` when the guest presses "Leave".
- Tell the player before they start that guest progress isn't saved.
- A guest can't turn into an account later (their progress isn't carried over).

### Sending an answer
Every answer goes to `POST /score` as `multipart/form-data`:

```js
const form = new FormData();
form.append("target", "حَبْلْ");               // what the player should say, fully vowelized
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

What to show: `correct`, `heard`, and `error_type` as friendly text from `frontend/src/shell/feedback.ts`. Don't show `*_phonemes` to the player: they're IPA symbols. With audio, `heard` is the target when the answer is right and empty otherwise (the model gives sounds, not words).

### Error types
The backend picks the most specific type first. Arabic types apply when the target contains Arabic letters.

| `error_type` | Example (target → read as) | Applies to |
|---|---|---|
| `none` | correct | both |
| `no_response` | nothing said | both |
| `letter_position` | كَتَبَ → كَبَتَ (two neighbouring letters swapped) | Arabic |
| `dot_confusion` | حَبْلْ → جَبْلْ (letters that differ only by dots: ب ت ث، ج ح خ، د ذ، ر ز، س ش، ص ض، ط ظ، ع غ، ف ق) | Arabic |
| `vowel_length` | كَاتِبْ → كَتِبْ (long vowel read short, or the reverse) | Arabic |
| `vowel_error` | قَمَرْ → قُمَرْ (wrong short vowel) | Arabic |
| `letter_reversal` | dog → bog (b/d), was → saw | English |
| `missing_sound` | بَابْ → بَا | both |
| `added_sound` | a sound added | both |
| `substitution` | any other change | both |

### Arabic targets: write them so espeak reads them right
- **Fully vowelized**, every letter with its mark. Unvowelized letters give only a consonant, so the target is wrong.
- **Write the pausal form**, the way a reader stops: the final consonant carries a sukun (قَمَرْ). A final vowel mark is a sound the player must say (كَتَبَ ends in `a`).
- **Tanwin is read as `-un`/`-an`/`-in`** (كِتَابٌ → `k i t aː b u n`), and **final ة is read as `t`**. Avoid both at the end of a word unless the player is meant to say them.
- Check any item before adding it:
  ```bash
  cd backend
  python -c "from app import g2p; print(g2p.phonemes('بَابْ'))"   # ('b', 'aː', 'b')
  ```
  On Windows, set `PYTHONIOENCODING=utf-8` first (PowerShell: `$env:PYTHONIOENCODING="utf-8"`) or the Arabic can't print.

### The round loop (Word Flash)
```
items = POST /next-exercise { player_id, game: "word_flash", history: [] }        (with the auth header)
loop:
    for each word in items: show it for display_ms, then hide it → record → POST /score → keep the result
    next = POST /next-exercise { player_id, game, history: <this round's /score results> }
```
The server decides the level and remembers it. `reason` is Arabic and safe to show (section 4).

### Sound Surgery
`/score` already handles it: send the **answer** as `target`.
- "Say كَتَبَ without the كـ" → `target` = what is left, fully vowelized. If they still say the whole word, they get `added_sound`.

Agree with the content owner on how one item stores both the prompt and the answer. A simple suggestion: `"prompt|answer"`, split on `|`. The backend treats items as plain strings, so any format works.

### Echo Chain
Send the **whole chain** as one target, separated by spaces (e.g. three vowelized syllables). The player's version is compared sound by sound. Items come from `/next-exercise` with `game: "echo_chain"` once `content/echo_chain.json` exists; until then, use mock mode.

### Progress Dashboard
`GET /progress/{player_id}` (with the auth header, your own `player_id`) → one entry per day:
```json
{ "date": "2026-11-14", "accuracy": 0.72, "phoneme_accuracy": 0.86, "avg_response_ms": 1650, "errors": { "dot_confusion": 4, "vowel_error": 2 } }
```
- `accuracy` = share of words fully correct that day (0–1): **word accuracy**.
- `phoneme_accuracy` = average share of sounds said right (0–1). It rises before `accuracy` does, so it shows progress early.
- `avg_response_ms` = average time from the word appearing to the answer arriving. Lower is better. It can be **`null`** (no timed answers that day): draw a gap, not 0.
- `errors` lists only error types that happened. Treat a missing key as 0.
- An unknown player returns `{"sessions": []}`, so show an empty state.
- **One game only:** `GET /progress/{player_id}?game=word_flash`. Leave `game` out for all games together.

Mock mode returns 5 improving days, so charts can be built now.

### Story Recall
`POST /story` with `{ "player_id": "…" }` and the auth header is enough: an empty `weak_sounds` is filled from the player's weakest sounds (section 4), an empty `interests` from their profile. The reply is `{ story, questions: [{ q, answer }] }`, fully vowelized Arabic. To read the story aloud, send it through `/score` one sentence at a time (`target` = the sentence, up to 300 characters). Checking spoken answers to the questions is still open (section 8).

### Errors
All errors look like `{"detail": "..."}`.
- `401`: not logged in or the login expired → login screen. `403`: another player's `player_id`.
- `413`: audio over 5 MB.
- `422`: bad input (the detail says which field), unreadable audio, or a target with no sounds.
- `404` on `/next-exercise`: no content file for that game yet.
- `503`: the speech packages or the LLM aren't available. Fall back to the debug buttons.

### Typed client
With the backend running: `npx openapi-typescript http://localhost:8000/openapi.json -o src/api-types.ts`.
Vite only exposes variables that start with `VITE_`, so the base URL is `VITE_API_BASE_URL` there.

---

## 4. Adaptive learning (`brain.py`)

- **Mastery per sound:** Bayesian Knowledge Tracing (Corbett & Anderson 1995). `mastery()` replays the player's saved attempts, oldest first, and gives P(mastered) for every sound they have been asked to read. A sound counts as practised correctly unless it was dropped or replaced.
- **Weak sounds:** `weakest()` returns the sounds below 0.6, lowest first (top 2).
- **`/next-exercise`:** the level moves up after a round with word accuracy ≥ 0.8 and down below 0.5 (at least 3 results). Words containing the weak sounds come first. If no attempts were saved (no token), this round's `history` is used instead.
- **`reason`** is Arabic and shows letters, never IPA, e.g. `"نتدرّب على: ح"`, `"مستوى أعلى: …"`.
- **`/story`** uses the weak sounds when `weak_sounds` is empty.

### The LLM for stories
`/story` talks to **any OpenAI-compatible endpoint** (vLLM, a hosted API, a local server). Set in `.env` (never committed):
```
MOCK_MODE=0
VLLM_BASE_URL=http://localhost:8001/v1
VLLM_API_KEY=change-me
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```
The names start with `VLLM_` for historical reasons. The backend never prints them.
- It asks for JSON-schema structured output; if the server rejects that, it retries without it and validates the JSON itself.
- The prompt is `content/prompts/story.txt` (Arabic). `$weak_sounds` and `$interests` get filled in. Keep the JSON reply format at the end, or `/story` fails.
- Inside Docker, `localhost` is the container itself, so a server on your machine isn't reachable at `localhost`. Run the backend with Python for a local LLM, or point `VLLM_BASE_URL` at an address the container can reach.
- Keep any self-hosted LLM endpoint behind an API key or firewall.

---

## 5. Speech scoring (`speech.py`)

[backend/app/speech.py](../backend/app/speech.py) turns a recording into sounds with a CTC phoneme model. Today `MODEL = "facebook/wav2vec2-lv-60-espeak-cv-ft"` (multilingual; Arabic coverage unknown, being measured).
- **Audio:** webm/opus (Chrome, Firefox), mp4 (Safari) or wav, decoded with PyAV (it bundles ffmpeg).
- **Device:** any GPU PyTorch reports as `cuda`, otherwise the CPU.
- **The model loads in the background when the backend starts** (real mode). The first start downloads about 1.3 GB.
- **Under 0.2 s of audio** counts as no answer. **Unreadable audio** → `422`. **Speech packages not installed** → `503`.
- For Arabic targets, vowel length (`ː`) is kept; for English it is dropped.

**Install** (not needed for mock mode or typed answers), from `backend/` with your virtual environment active:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu        # CPU; NVIDIA: see requirements-speech.txt
pip install -r requirements-speech.txt
```

### Plugging in our fine-tuned model
`ml/evaluate.py` measures phoneme error rate on Arabic (Iqra'Eval dev data or our own clips) for any model, so the current one and ours are compared on equal terms. When ours is better:
1. Set `MODEL` in `speech.py` to its Hugging Face name or local folder. Keep the `recognize()` interface.
2. **Match the symbols.** The backend compares the model's output with espeak IPA from `g2p.py`. `ml/` trains on the Iqra'Eval symbol set (`ml/arabic_phonemes.py`), so either map the model's output to espeak IPA in `speech.py`, or switch Arabic targets in `g2p.py` to `arabic_phonemes()` and update `DOT_FAMILIES`, `SHORT_VOWELS` and `LETTER_FOR` to the same symbols. Not done yet.
3. Run `python -m pytest` and re-check the error-type examples in section 3.

### Kuwaiti dialect tolerance
Regular Kuwaiti pronunciations (ق as `g`, ك as `tʃ`, ض as `ðˤ`, …) should be accepted, not flagged ([research.md](research.md) section 4.1). Not implemented yet: a native speaker checks the list first, then it goes into `scoring.normalize()`.

---

## 6. Content formats

### Word lists: one file per game, `content/<game>.json`
```json
{ "levels": [
    { "focus": "كَلِمَاتٌ قَصِيرَةٌ", "display_ms": 2000, "items": ["وَلَدْ", "قَمَرْ", "سَمَكْ", "مَلِكْ", "عَلَمْ"] },
    { "focus": "حُرُوفٌ تَخْتَلِفُ بِالنُّقَطِ: ب ت ث", "display_ms": 1800, "items": ["بَابْ", "تَاجْ", "ثَوْبْ", "تَمْرْ", "ثَلْجْ"] }
] }
```
- Levels go easiest first (level 1 = first entry). Each level needs **at least 5 items** (one round).
- `focus` is shown to the player as the reason. `display_ms` should get shorter as levels go up.
- Items follow the Arabic target rules in section 3 (fully vowelized, pausal form).
- File names: `word_flash.json`, `sound_surgery.json`, `echo_chain.json`, and so on. A game without a file gets `404` in real mode.
- `content/word_flash.json` is a starter list organised by letter families; the content owner replaces it.
- Edits are picked up on the next request, with no restart needed.

---

## 7. Docker

- `docker compose up --build` runs the backend on port 8000.
- `content/` is mounted into the container (edit without rebuilding), and the SQLite file lives in `data/` on the host.
- The image has no speech packages: audio scoring returns `503` there. Typed answers and mock mode work.

---

## 8. Open questions

From [research.md](research.md) section 9, plus integration questions:

1. **Competition rules:** judging criteria, submission format, whether a working demo is required. Ask KDA.
2. **Does the phoneme model hear Arabic?** Measure in `ml/`; if the current model is weak, fine-tune or start from an Iqra'Eval Apache-2.0 checkpoint.
3. **Dialect list:** a native Kuwaiti speaker checks [research.md](research.md) section 4.1 before we tune `scoring.normalize()`.
4. **Pilot paperwork:** information sheet and consent form ([research.md](research.md) section 7); fix the deletion date.
5. **Iqra'Eval phonetiser licence:** ask the authors, or keep our own `ml/arabic_phonemes.py` and espeak.
6. **Word lists:** vowelized, organised by letter families, syllable shapes and roots.
7. **Sound Surgery item format** (suggestion: `"prompt|answer"`).
8. **Story Recall:** spoken answers can't be checked by `/score` alone. Add an endpoint, or check answers with buttons?
9. **Response time:** keep `shown_at_ms` (includes upload time) or measure speech onset in the audio?
