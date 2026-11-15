# ml/ — Arabic phoneme recogniser

Scripts to measure Arabic phoneme models and fine-tune our own, all on a local NVIDIA GPU.
Results and the decisions behind them: [RESULTS.md](RESULTS.md).

| File | What it does |
|---|---|
| `arabic_phonemes.py` | `arabic_phonemes(text)`: vowelized MSA → phonemes (Iqra'Eval symbol set). No dependencies; the backend can copy it verbatim. `python arabic_phonemes.py` runs its self-check |
| `common.py` | Reads the dataset shards, decodes audio (PyAV, as the backend does), computes PER with a short-vowel / long-vowel / consonant breakdown |
| `evaluate.py` | PER of any CTC phoneme model (Hugging Face id, local folder, or an Iqra'Eval `.ckpt`) on held-out data or on your own clips |
| `g2p_check.py` | Scores `arabic_phonemes()` and espeak-ng `ar` against the dataset's phoneme labels (the phoneme-set decision) |
| `iqra_baseline.py` | Runs the official Iqra'Eval s3prl baseline checkpoints without installing s3prl |
| `train.py` | Fine-tunes `facebook/wav2vec2-lv-60-espeak-cv-ft` into an Arabic phoneme recogniser |
| `pilot.py`, `pilot_items.csv` | Adult pilot: how often the app's verdict on a recording agrees with a human listener |

`ml/data/` (datasets, cloned repos) and `ml/models/` (checkpoints, logs) are git-ignored.

## Setup (Windows, NVIDIA RTX 50xx)

Blackwell GPUs need a CUDA 12.8+ PyTorch build. Python 3.12 (3.14 wheels were not needed, so not tried):

```bash
cd ml
py -3.12 -m venv .venv          # or: <path to>/Python312/python.exe -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name())"
```

Run every command below from `ml/`, with `PYTHONIOENCODING=utf-8` set in Git Bash (Arabic output).

## Data

Iqra'Eval training data (Common Voice Arabic with vowelized text and phoneme labels). Public, no login.
The short run uses the dev split plus 12 of the 29 train shards (5.2 GB); the full run uses all 29 (11.3 GB).

```bash
# SHARDS=12 for the short run, 29 for the overnight run
SHARDS=12 .venv/Scripts/python -c "
import os; from huggingface_hub import snapshot_download
snapshot_download('IqraEval/Iqra_train', repo_type='dataset', local_dir='data/iqra_train',
    allow_patterns=['data/dev-*'] + [f'data/train-{i:05d}-*' for i in range(int(os.environ['SHARDS']))])"
```

Optional, for the official baseline and its vocabulary:

```bash
git clone --depth 1 https://github.com/Iqra-Eval/interspeech_IqraEval data/src/interspeech_IqraEval
.venv/Scripts/hf download IqraEval/Iqra_wav2vec2_base wave2vec2_base.ckpt --local-dir models/iqra_baselines
```

| Dataset / model | Licence | Used for |
|---|---|---|
| [IqraEval/Iqra_train](https://huggingface.co/datasets/IqraEval/Iqra_train) (audio from Mozilla Common Voice Arabic, CC0) | **CC BY-NC 4.0** | training + held-out dev |
| [IqraEval/Iqra_wav2vec2_base](https://huggingface.co/IqraEval/Iqra_wav2vec2_base) | Apache-2.0 | baseline |
| [facebook/wav2vec2-lv-60-espeak-cv-ft](https://huggingface.co/facebook/wav2vec2-lv-60-espeak-cv-ft) | Apache-2.0 | baseline + starting point |
| [facebook/wav2vec2-base](https://huggingface.co/facebook/wav2vec2-base) | Apache-2.0 | frozen upstream of the Iqra'Eval baseline |
| [Bisher/wav2vec2-xls-r-300m-IqraEval-3](https://huggingface.co/Bisher/wav2vec2-xls-r-300m-IqraEval-3) | none stated | tried as a baseline: outputs only blanks |
| [Iqra-Eval/interspeech_IqraEval](https://github.com/Iqra-Eval/interspeech_IqraEval), [Iqra-Eval/MSA_phonetiser](https://github.com/Iqra-Eval/MSA_phonetiser) | **no licence file** | vocab file read at run time; phonetiser read for reference only, no code copied |

**Non-commercial:** a model fine-tuned on Iqra_train inherits CC BY-NC 4.0 in practice. Fine for the hackathon
and a research pilot; a paid product needs a commercial-friendly dataset (e.g. Common Voice Arabic itself, CC0,
labelled with `arabic_phonemes()` after diacritizing) — see RESULTS.md.

## Evaluate

Held-out set: a fixed sample of 300 dev utterances (Common Voice dev speakers; 0 sentences shared with train).
Targets are `arabic_phonemes(vowelized text)`, exactly what the backend would compute.

```bash
.venv/Scripts/python evaluate.py --model facebook/wav2vec2-lv-60-espeak-cv-ft      # before fine-tuning
.venv/Scripts/python evaluate.py --model models/iqra_baselines/wave2vec2_base.ckpt # official Iqra'Eval baseline
.venv/Scripts/python evaluate.py --model models/arabic-phoneme                     # ours
.venv/Scripts/python evaluate.py --model models/arabic-phoneme --csv clips.csv     # your clips: columns path,text
```

```bash
.venv/Scripts/python g2p_check.py --espeak   # needs: pip install phonemizer-fork==3.3.2 espeakng-loader==0.2.4
```

Flags: `--n 300` utterances, `--targets labels` scores against the dataset's own labels instead of `arabic_phonemes()`.

## Train

Short proof run (run 2 in RESULTS.md: 12 shards, 7000 steps, 21 min of training + ~5 min loading on an RTX 5070 Ti):

```bash
.venv/Scripts/python train.py --steps 7000 --minutes 25 --lr 1e-4 --eval_every 1000 > models/train_short.log 2>&1
```

Full run (run 3, the backend's model: 9.75% PER). Download all 29 shards first; loading 79 h of audio takes
~13 min and ~10 GB RAM, then 60000 steps take 3.1 h, about 7 passes over the data:

```bash
.venv/Scripts/python train.py --steps 60000 --minutes 600 --lr 1e-4 --eval_every 5000 --out models/arabic-phoneme-long > models/train_long.log 2>&1
.venv/Scripts/python evaluate.py --model models/arabic-phoneme-long
```

The model and its processor are saved to `--out` at every evaluation. The backend loads `models/arabic-phoneme`
by default: rename the new folder to that, or point `ARABIC_SPEECH_MODEL` at it.

## Adult pilot: agreement with a human listener

Consenting adults only; follow the checklist in [docs/research.md](../docs/research.md) section 7 first. The
information sheet and consent form, in Arabic and English, are in [docs/pilot-consent.md](../docs/pilot-consent.md).

1. **Items:** [pilot_items.csv](pilot_items.csv) has 24 cards: 8 read correctly and 16 with a deliberate error
   (5 dot letters, 3 short vowels, 3 vowel lengths, 3 swapped letters, 1 missing and 1 added sound).
   The participant sees the `said` word and reads it; the app scores it against `target`, as if `target` had been shown.
   `python pilot.py --check` confirms each `said` really gives its intended error.
2. **Record** each card as its own clip (phone voice memo, wav, webm or m4a; a second of silence either side)
   into `ml/data/pilot/` (git-ignored, never commit it), named by pseudonym and card, e.g. `p03_17.m4a`.
3. **Listen and write down** what was actually said, vowelized. Participants slip: if they read a card
   differently, the `said` column records what they really said, not what the card asked for.
4. **Score:** a CSV with columns `path,target,said`, then:
   ```bash
   .venv/Scripts/python pilot.py data/pilot/clips.csv
   ```
   It prints `verdict_agreement` (right/wrong matches the listener), `error_recall` (real mistakes caught),
   `error_precision` (flags that were real mistakes), `error_type_agreement` and a per-type breakdown.
   These are the numbers for the pitch, together with the phoneme error rate.
