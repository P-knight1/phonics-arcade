# Design

How the app works, from the microphone to the next exercise. The science behind each choice is in
[research.md](research.md); the speech model's training and numbers are in [ml/RESULTS.md](../ml/RESULTS.md).

## 1. Overview

```
Browser (React + Vite, microphone)
   │  JSON and audio over HTTP, bearer token
   ▼
FastAPI backend
   ├── speech.py           audio → phonemes (our fine-tuned wav2vec2 CTC model)
   ├── g2p.py              target text → phonemes (arabic_phonemes.py)
   ├── scoring.py          compare the two, name the error
   ├── brain.py            mastery per sound, next exercise, generated stories
   └── db.py               SQLite: accounts, guests, attempts, levels
ml/                        training and evaluation of the phoneme model
content/                   vowelized word lists and the story prompt
```

The key decision: scoring compares **phonemes**, not words. A speech-to-text system writes the word the reader
meant, which hides exactly the errors we care about. A phoneme recogniser reports the sounds that were said.

One request, end to end: the player reads حَبْلْ aloud. `g2p` turns the target into `H a b l`, the model hears
`j a b l`, `scoring` aligns the two, finds ح→ج inside one dot family and returns `dot_confusion`. The attempt is
saved, the player's mastery of `H` drops, and the next round puts more words with ح first.

## 2. API

Interactive reference with every schema: `http://localhost:8000/docs` while the backend runs.
Shapes live in [backend/app/schemas.py](../backend/app/schemas.py); the frontend's client is
[frontend/src/api.ts](../frontend/src/api.ts).

| Endpoint | Purpose |
|---|---|
| `POST /players` | Register `{name, password, interests}` → `201 {player_id, name, interests, token}`; `409` if the name is taken (case-insensitive) |
| `POST /login` | `{name, password}` → same shape; `401` if wrong |
| `POST /guest` | Play without an account; data deleted on `/logout` or after 24 h |
| `GET /me`, `POST /logout` | Profile; end the login (logins last 30 days) |
| `POST /score` | Score one answer (below) |
| `POST /next-exercise` | `{player_id, game, history}` → `{game, level, items, display_ms, reason}` |
| `POST /story` | `{player_id, weak_sounds?, interests?}` → `{story, questions: [{q, answer}]}` |
| `GET /progress/{player_id}?game=` | One entry per day: word accuracy, phoneme accuracy, average response time, error counts |
| `GET /health` | `{ok, mock}` |

Every request sends `Authorization: Bearer <token>`. `/next-exercise`, `/story` and `/progress` need it (`401`)
and only accept the caller's own `player_id` (`403`). Names are nicknames (1–30 characters), passwords 8–128,
up to 5 interests. Passwords are stored as salted scrypt hashes and tokens as hashes; there is no list of players.

**`/score`** takes `multipart/form-data`:

| Field | Meaning |
|---|---|
| `target` | What the player should say, fully vowelized (up to 300 characters, one story sentence) |
| `audio` | The recording: webm/opus, mp4 (Safari) or wav, up to 5 MB |
| `heard_text` | Debug mode: typed text scored instead of audio, through the same pipeline |
| `shown_at_ms` | `Date.now()` when the prompt appeared, for response time |
| `game` | Stored with the attempt, used by `/progress?game=` |

No `audio` and no `heard_text` means the player didn't answer (`no_response`). Logged in, the attempt is saved;
without a token it is scored only. The reply:

```json
{ "heard": "", "target_phonemes": ["H","a","b","l"], "heard_phonemes": ["j","a","b","l"],
  "correct": false, "phoneme_accuracy": 0.75, "response_ms": 1840, "error_type": "dot_confusion" }
```

Errors are `{"detail": "..."}`: `413` audio too large, `422` bad input or unreadable audio, `404` no content for
that game, `503` model or LLM unavailable (the UI then falls back to the typed-answer buttons).

## 3. Scoring

### Arabic targets

[backend/app/arabic_phonemes.py](../backend/app/arabic_phonemes.py) turns vowelized Modern Standard Arabic into
the Iqra'Eval symbol set, the same converter the model was trained with (a test keeps the `ml/` and `backend/`
copies identical). Consonants `b t ^ j H x d * r z s $ S D T Z E g f q k l m n h w y <` (`^` ث, `*` ذ, `$` ش,
`E` ع, `g` غ, `<` hamza, capitals are emphatics); shadda doubles the symbol (`bb`); vowels `a i u`, long `aa ii uu`.

- Targets must be fully vowelized. An unmarked letter yields only its consonant.
- Sun letters, hamzat al-wasl and long vowels follow normal reading rules: الشَّمْسُ → `< a $$ a m s`.
- The last word is read in pause: كِتَابٌ → `k i t aa b`. Reading the final vowel or tanwin in full is also
  correct Arabic, so `scoring` accepts it too.

Check an item: `python -c "from app import g2p; print(g2p.phonemes('بَابْ'))"` from `backend/`
(on Windows set `PYTHONIOENCODING=utf-8` first).

### Error types

The two sequences are aligned with `difflib.SequenceMatcher`; the most specific label wins.

| `error_type` | Example (target → read as) | Rule |
|---|---|---|
| `letter_position` | كَتَبَ → كَبَتَ | Two neighbouring sounds swapped, directly or across one vowel |
| `dot_confusion` | حَبْلْ → جَبْلْ | Substitution inside one dot family: ب ت ث، ج ح خ، د ذ، ر ز، س ش، ص ض، ط ظ، ع غ، ف ق |
| `vowel_length` | كَاتِبْ → كَتِبْ | `a↔aa`, `i↔ii`, `u↔uu` |
| `vowel_error` | قَمَرْ → قُمَرْ | Substitution among `a i u` |
| `missing_sound` / `added_sound` | قَلَمْ → قَمْ | Only deletions / only insertions |
| `substitution` | | Anything else |
| `none` / `no_response` | | Correct / nothing said |

`phoneme_accuracy` is matched phonemes over the longer sequence. English targets still work (espeak-ng `en-gb`,
plus `letter_reversal` for b/d and was/saw); they are a leftover from before the switch to Arabic.

## 4. Adaptive practice (`brain.py`)

- **Mastery per sound:** Bayesian Knowledge Tracing (Corbett & Anderson 1995), replayed over the player's saved
  attempts. A sound counts as read correctly unless it was dropped or replaced. Sounds below 0.6 are weak.
- **Level:** after a round of at least 3 answers, word accuracy ≥ 0.8 moves up a level, below 0.5 moves down.
  The level is stored per player and game.
- **Items:** words containing the two weakest sounds come first, the rest are shuffled in.
- **`reason`** is shown to the player in Arabic and names letters, never phoneme symbols (`نتدرّب على: ح`).

## 5. Generated stories

`/story` asks an LLM for a short story with questions, using the player's weak letters and interests. Any
OpenAI-compatible endpoint works (`VLLM_BASE_URL`, `VLLM_API_KEY`, `VLLM_MODEL` in `.env`; the names are
historical). The prompt is [content/prompts/story.txt](../content/prompts/story.txt).

- It requests JSON-schema output and falls back to plain output, validated with Pydantic, when the server
  doesn't support schemas.
- A story is read aloud and scored, so it must be vowelized: if fewer than 90% of its letters carry a mark, the
  backend asks once more, then returns `503`.
- To read a story, the frontend sends it to `/score` one sentence at a time.

## 6. Speech model (`speech.py`)

- **Arabic:** our model, fine-tuned from `facebook/wav2vec2-lv-60-espeak-cv-ft` on Iqra'Eval data: 9.75% phoneme
  error rate on held-out Arabic speech. Loaded from `ARABIC_SPEECH_MODEL`, default `ml/models/arabic-phoneme`
  (1.2 GB, not in git; train it with [ml/README.md](../ml/README.md)). It loads in the background at startup.
- **English:** `facebook/wav2vec2-lv-60-espeak-cv-ft`, downloaded on first use.
- Audio is decoded with PyAV. Under 0.2 s counts as no answer. Runs on a CUDA GPU if PyTorch sees one, else CPU.
- Install: `pip install torch` (CPU or CUDA build), then `pip install -r requirements-speech.txt` in `backend/`.

To try a new model, measure it with `ml/evaluate.py`, then point `ARABIC_SPEECH_MODEL` at it. It must output the
symbols in `SYMBOLS`; `ml/train.py` guarantees that.

## 7. Modes and content

- `MOCK_MODE=1` returns fake but valid game data, so the UI runs without a model or an LLM. Accounts are real.
- `MOCK_MODE=0` is the real pipeline. Without the speech packages audio returns `503`, but typed answers
  (`heard_text`) still go through scoring, progress and levels.
- Every game has a debug mode (`?debug=1`): "said it right", "said it wrong" and a box for what was heard.
- Word lists: `content/<game>.json`, levels easiest first, at least 5 items each, read on every request:

```json
{ "levels": [ { "focus": "كَلِمَاتٌ قَصِيرَةٌ", "display_ms": 2000, "items": ["وَلَدْ", "قَمَرْ", "سَمَكْ", "مَلِكْ", "عَلَمْ"] } ] }
```

- Sound Surgery items store prompt and answer as `"prompt|answer"`; `/score` gets the answer as `target`.

## 8. Known limits

- The model was trained on adults reading full MSA sentences. Accuracy on single words read by people with
  dyslexia is measured by the adult pilot (`ml/pilot.py`), not yet.
- No tolerance for Kuwaiti pronunciations yet (ق as `g`, ك as `tʃ`): the symbol set has no `g`-for-ق, and the
  list in research.md section 4.1 needs a native speaker's check first.
- Response time includes upload time; speech onset is not detected.
- Spoken answers to story questions are not checked.
- The training data is CC BY-NC 4.0, so the model is for non-commercial use.
- Docker runs mock mode and typed answers; the image has no speech packages.
