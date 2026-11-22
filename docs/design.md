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
| `POST /score-rhythm` | One recording of a Rhythmic Reading run → a result and a timing per word (section 3) |
| `POST /timing-test` | Microphone check page (`/mic-test`): shows every sound heard and its timing; nothing saved |
| `POST /next-exercise` | `{player_id, game, history}` → `{game, level, items, display_ms, reason}` |
| `GET /story/status/{player_id}` | `{unlocked, attempts, needed}`: stories open after 20 word-game attempts |
| `POST /story` | `{player_id, weak_sounds?, interests?}` → `{story, questions: [{q, answer}]}` |
| `POST /coach` | `{player_id, kind: "word" \| "round", attempts}` → `{text}`: the reading coach (section 5) |
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
the Iqra'Eval symbol set, the same converter the model was trained with. Consonants
`b t ^ j H x d * r z s $ S D T Z E g f q k l m n h w y <` (`^` ث, `*` ذ, `$` ش, `E` ع, `g` غ, `<` hamza, capitals
are emphatics); shadda doubles the symbol (`bb`); vowels `a i u`, long `aa ii uu`.

- Targets must be fully vowelized. An unmarked letter yields only its consonant.
- Sun letters, hamzat al-wasl and long vowels follow normal reading rules: الشَّمْسُ → `< a $$ a m s`.
- The last word is read in pause: كِتَابٌ → `k i t aa b`. Reading the final vowel or tanwin in full is also
  correct Arabic, so `scoring` accepts it too.
- A word ending in two consonants (حَبْلْ) is often said with a short vowel slipped between them (حَبِل). That is
  how the cluster is pronounced, not a misreading, so `scoring` accepts it.

### Close calls: does the recording fit the word?

The model gets about one sound in ten wrong, so a word of four or five sounds read perfectly would still be
marked wrong roughly a third of the time if the transcript had to match exactly. For Arabic audio,
`speech.recognize_fit` therefore also asks how well the recording fits the word the reader was asked to say: the
CTC likelihood of the target against that of the model's own transcript (goodness of pronunciation, Witt and
Young 2000). The difference, the gap, is in nats; 0 means the target is as likely as the transcript.

| Gap | Verdict | Why |
|---|---|---|
| up to 3 | right | the transcript's difference is the model's slip |
| 3 to 6 | "read it again" (`unclear`), nothing saved | slips and some real misreadings (mostly vowels) overlap here |
| over 6 | the normal error type | a real misreading |

The second reading of a word always gets a verdict (`second_try`), so a reader is never stuck. The thresholds come
from 300 Iqra'Eval dev recordings with each label's true reading as the target, and the same label with one sound
changed (dot twin, another short vowel, a dropped consonant) as a simulated misreading. At 3, 83% of right readings
transcribed with a single slip passed and no misreading did. On 30 other dev recordings sent through `/score` as
whole sentences, correct readings marked right rose from 8 to 17 (4 more were asked to read again) and none of the
30 one-letter misreadings was accepted. The recordings are adults reading sentences. On single words in the adult
pilot ([research.md](research.md#4-adult-pilot)) the check let through 10 real errors, nearly all one short vowel,
that the model had transcribed correctly; asking for a second reading there is the next change to test.

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

`phoneme_accuracy` is matched phonemes over the longer sequence.

### Rhythmic Reading

One recording covers the whole run: a 4-beat count-in, then one word every two beats (the word shows on the first
beat). `/score-rhythm` takes the words, the slot length and when the first word appeared. `speech.recognize_timed`
returns each phoneme with the time it started (CTC frames are 20 ms). `rhythm.py` aligns the whole run against all
the words at once and gives each heard sound to a word, so a missed word doesn't shift the others and an extra final
vowel stays with its word. Each word is then scored like `/score`, plus `offset_ms` (from the word appearing to the
reader starting it), `on_time` (started before the next word appeared), and `steadiness_ms` for the run (the spread
of the offsets: lower is steadier). Every word is saved as its own attempt. Typed answers give no timing.

## 4. Adaptive practice (`brain.py`)

- **Mastery per sound:** Bayesian Knowledge Tracing (Corbett & Anderson 1995), replayed over the player's saved
  attempts. A sound counts as read correctly unless it was dropped or replaced. Sounds below 0.6 are weak.
- **Level:** after a round of at least 3 answers, word accuracy ≥ 0.8 moves up a level, below 0.5 moves down.
  The level is stored per player and game.
- **Items:** words containing the two weakest sounds come first, the rest are shuffled in.
- **`reason`** is shown to the player in Arabic and names letters, never phoneme symbols (`نتدرّب على: ح`).

## 5. Generated stories

`/story` asks an LLM for a short story with questions, built from the player's weakest letters, the real words they
misread lately in Word Flash and Rhythmic Reading, and their interests. Stories unlock after 20 word-game attempts
(`/story` returns `409` before that), so there is enough data to target. The reader reads the same story up to three
times, sentence by sentence, and sees sound accuracy and time for each reading, then answers the questions. The
prompt is [content/prompts/story.txt](../content/prompts/story.txt).

With `ANTHROPIC_API_KEY` set, the coach and stories use the Anthropic API (`LLM_MODEL` changes the
model); otherwise any OpenAI-compatible endpoint works (`VLLM_BASE_URL`, `VLLM_API_KEY`, `VLLM_MODEL`). Each player
gets at most 80 coach notes and 8 stories a day, and the whole site 1,000 coach notes and 100 stories.

- Replies are structured JSON, validated before use.
- A story is read aloud and scored, so it must be vowelized: if fewer than 90% of its letters carry a mark, the
  backend asks once more, then returns `503`.
- To read a story, the frontend sends it to `/score` one sentence at a time.

### Reading coach

`/coach` asks the same LLM to explain a mistake (`word`) or sum up a round (`round`) in one to three kind
sentences. The LLM never hears audio and never decides right or wrong: the backend rewrites each scored attempt as
letters (`حَبْلْ: قُرئ ح كأنه ج`), adds the player's weak letters, and fills
[content/prompts/coach_word.txt](../content/prompts/coach_word.txt) or `coach_round.txt`. A reply must be Arabic,
short (300 or 600 characters) and free of clinical words, or the request returns `503`. The frontend shows its
fixed feedback first and adds the coach's note when it arrives, so a slow or missing LLM changes nothing.

## 6. Speech model (`speech.py`)

- **Arabic:** our model, fine-tuned from `facebook/wav2vec2-lv-60-espeak-cv-ft` on Iqra'Eval data: 9.75% phoneme
  error rate on held-out Arabic speech. Loaded from `ARABIC_SPEECH_MODEL`, default `ml/models/arabic-phoneme`
  (1.2 GB, not in git; train it with [ml/README.md](../ml/README.md)). It loads in the background at startup.
- Audio is decoded with PyAV. Under 0.2 s counts as no answer. Runs on a CUDA GPU if PyTorch sees one, else CPU.

## 7. Modes and content

- `MOCK_MODE=1` returns fake but valid game data, so the UI runs without a model or an LLM. Accounts are real.
- `MOCK_MODE=0` is the real pipeline. Without the speech packages audio returns `503`, but typed answers
  (`heard_text`) still go through scoring, progress and levels.
- Every game has a debug mode (`?debug=1`): "said it right", "said it wrong" and a box for what was heard.
- Frontend: one folder per activity under `frontend/src/games/`, shared pieces (login, menu, microphone, answer
  controls) in `frontend/src/shell/`.
- Word lists: `content/<game>.json`, levels easiest first, at least 5 items each, read on every request:

```json
{ "levels": [ { "focus": "كَلِمَاتٌ قَصِيرَةٌ", "display_ms": 2000, "items": ["وَلَدْ", "قَمَرْ", "سَمَكْ", "مَلِكْ", "عَلَمْ"] } ] }
```

- Sound Surgery items are stored as `"prompt|answer"`. A test checks every content file.

## 8. Known limits

- The model was trained on adults reading full MSA sentences. On single words read by four adults it matched a
  human listener in 84% of recordings. Children and readers with dyslexia are not measured yet.
- No tolerance yet for dialect pronunciations such as ق said as `g` (in the pilot, an Egyptian reader's ق as `g`
  was marked wrong).
- Response time includes upload time; speech onset is not detected.
- Spoken answers to story questions are not checked.
- The training data is CC BY-NC 4.0, so the model is for non-commercial use.
- `docker compose` runs the backend only, in mock mode with typed answers; the root `Dockerfile` is the full image.
