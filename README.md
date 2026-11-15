# Arabic reading practice for dyslexia

A web app where a reader practises vowelized Arabic aloud and gets precise, kind feedback on the mistakes that
characterise Arabic dyslexia: a wrong short vowel, letters that differ only by their dots (ح read as ج), a long
vowel read short, two letters swapped. It then adapts what comes next to the sounds that reader finds hard.

Built for the Kuwait Dyslexia Association AI competition (November 2026). It is a practice tool, not a medical
one: it makes no clinical claims. The intended users are children; the pilot is run with consenting adults only.

## Why

Existing reading apps accept close-enough pronunciations, and speech-to-text writes the word you *meant*. Both hide
the errors a dyslexic reader needs to hear about. This app scores sound by sound with its own Arabic phoneme model,
so it can tell قَمَر from قُمَر and حَبْل from جَبْل. The research behind each feature is in
[docs/research.md](docs/research.md).

## Where AI is used

| Part | What it does | Status |
|---|---|---|
| Phoneme recognition | A wav2vec2 model fine-tuned on 79 hours of Arabic speech hears which sounds were said | 9.75% phoneme error rate on held-out speech, vs 34.2% before fine-tuning and 11.8% for the published Iqra'Eval baseline ([ml/RESULTS.md](ml/RESULTS.md)) |
| Error profiling | Aligns what was said with the target and names the Arabic error type | Done |
| Adaptive practice | Bayesian Knowledge Tracing estimates mastery of every sound and picks the next words | Done |
| Generated stories | An LLM writes short vowelized stories around the reader's weak letters and interests; unvowelized output is rejected | Done |

## Games

| Game | The reader... | Status |
|---|---|---|
| Word Flash | reads a vowelized word before it disappears; display time adapts | Playable |
| Sound Surgery | says a word with its first syllable or last sound removed, or its first letter swapped for its dot twin (phonemic awareness) | Playable |
| Story Recall | reads a generated story sentence by sentence, then answers questions | Playable with an LLM endpoint |
| Progress | sees word accuracy, sound accuracy, speed and error types over time | Done |

The interface is Arabic and right to left, with large practice text in a naskh face and wide line spacing.

Designed but not built: rhythmic reading, root-and-pattern games, fading vowel marks as letters are mastered,
tolerance for Kuwaiti pronunciations. See [docs/design.md](docs/design.md) section 8 for known limits.

## Running it

Requirements: Python 3.11+, Node 20+. No GPU needed.

```bash
cp .env.example .env
```

**Backend**

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # macOS/Linux: .venv/bin/pip
.venv/Scripts/python -m uvicorn app.main:app --reload --env-file ../.env
```

API reference: http://localhost:8000/docs. `MOCK_MODE=1` in `.env` serves fake game data; `MOCK_MODE=0` runs the
real pipeline. For scoring from audio, also install the speech packages and the model:

```bash
.venv/Scripts/pip install torch --index-url https://download.pytorch.org/whl/cpu   # or a CUDA build
.venv/Scripts/pip install -r requirements-speech.txt
```

The Arabic model (1.2 GB) is not in the repository. Train it with [ml/README.md](ml/README.md), or set
`ARABIC_SPEECH_MODEL` to a folder that has it. Without it, typed answers still go through the whole pipeline.

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Add `?debug=1` to answer by typing instead of speaking.

**Docker** (backend only, mock mode and typed answers): `docker compose up --build`.

**Tests**

```bash
cd backend
.venv/Scripts/python -m pytest
```

## Layout

```
backend/app/     FastAPI: speech.py, g2p.py + arabic_phonemes.py, scoring.py, brain.py, db.py, main.py
backend/tests/   pytest suite
frontend/src/    React app: shell/ (login, menu, mic, debug input), games/<game>/
content/         vowelized word lists per game, story prompt
ml/              phoneme model: training, evaluation, adult-pilot scoring
docs/            design.md (how it works), research.md (the evidence), pilot-consent.md
```

## Data and ethics

- The phoneme model is trained on IqraEval/Iqra_train (CC BY-NC 4.0), so it is for non-commercial use.
- Pilot recordings come from consenting adults, are stored privately and are never committed.
  The checklist is in [docs/research.md](docs/research.md) section 7.
- No secrets in the repository: keys go in `.env`, which is git-ignored.

## License

MIT, see [LICENSE](LICENSE). Third-party models and data keep their own licences
([ml/README.md](ml/README.md)).
