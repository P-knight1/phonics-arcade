# Sawt Al-Huruf: Arabic reading practice for dyslexia

A web app in which a child reads vowelized Arabic aloud and gets precise, kind feedback on the mistakes typical of
Arabic dyslexia: a wrong short vowel, letters that differ only by their dots (ح read as ج), a long vowel read short,
two letters swapped. Practice then adapts to the sounds that reader finds hard.

Built for the Kuwait Dyslexia Association AI competition (November 2026). It is a practice and support tool and makes
no clinical claims. The intended users are children; testing so far has been with consenting adults only.

## Why

Most reading apps accept close-enough pronunciations, and speech-to-text writes the word the reader *meant*. Both
hide the errors a reader with dyslexia needs to hear about. This app compares sounds instead of words, using its own
Arabic phoneme model, so it can tell قَمَر from قُمَر and حَبْل from جَبْل.

## Activities

| Activity | The reader... |
|---|---|
| Word Flash | reads a word before it disappears; the display time follows the reader's pace |
| Sound Surgery | says a word with a sound removed or swapped for its dot twin (phonemic awareness) |
| Rhythmic Reading | reads words aloud in time with a beat |
| My Story | reads a short story built from their own weak letters and misread words, up to three times, then answers questions |
| Progress | sees accuracy, speed and error types over time |

The interface is Arabic and right to left, with large text and wide spacing. The research behind each activity is in
[docs/research.md](docs/research.md).

## Where AI is used

| Part | What it does | Result |
|---|---|---|
| Phoneme recognition | A wav2vec2 model fine-tuned on 79 hours of Arabic speech hears which sounds were said | 9.75% phoneme error rate on held-out speech, against 34.2% before fine-tuning and 11.8% for the Iqra'Eval baseline model ([ml/RESULTS.md](ml/RESULTS.md)) |
| Error detection | Aligns what was said with the target word and names the Arabic error type | Adult pilot: agreed with a human listener on 84% of 96 recordings and caught 83% of real errors ([docs/research.md](docs/research.md#4-adult-pilot)) |
| Adaptive practice | Bayesian Knowledge Tracing estimates mastery of each sound and picks the next words | |
| Reading coach | A language model explains each scored mistake in one or two Arabic sentences; it never hears audio or decides right and wrong | |
| Stories | A language model writes short vowelized stories around the reader's weak letters and interests | |

How the pieces fit together is in [docs/design.md](docs/design.md).

## Running it

Requirements: Python 3.11+ and Node 20+. No GPU needed.

```bash
cp .env.example .env

# backend
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt          # macOS/Linux: .venv/bin/pip
.venv/Scripts/python -m uvicorn app.main:app --reload --env-file ../.env

# frontend, in a second terminal
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. With `MOCK_MODE=1` in `.env` the app runs without the speech model or a language model.
Add `?debug=1` to the address to type answers instead of speaking.

To score real speech, install the speech packages and point `ARABIC_SPEECH_MODEL` at the trained model (1.2 GB,
not in the repository; [ml/README.md](ml/README.md) explains how to train it):

```bash
.venv/Scripts/pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/pip install -r requirements-speech.txt
```

The coach and stories need a language model key (`ANTHROPIC_API_KEY`, or any OpenAI-compatible endpoint) in `.env`.
The root `Dockerfile` builds a single image with the API, the speech runtime and the frontend for hosting.

Tests: `cd backend` then `.venv/Scripts/python -m pytest`.

## Layout

```
backend/app/     API, speech recognition, scoring, adaptive practice, database
backend/tests/   tests
frontend/src/    React app: shared shell and one folder per activity
content/         vowelized word lists and prompts
ml/              training and evaluation of the phoneme model, pilot scoring
docs/            design.md (how it works), research.md (the evidence), pilot-consent.md
```

## Data and ethics

- The phoneme model is trained on IqraEval/Iqra_train (CC BY-NC 4.0), so it is for non-commercial use.
- Pilot recordings come from consenting adults, are kept privately and are never committed.
- No keys or passwords are in the repository; they go in `.env`, which is not tracked.

## Licence

MIT, see [LICENSE](LICENSE). Third-party models and data keep their own licences ([ml/README.md](ml/README.md)).
