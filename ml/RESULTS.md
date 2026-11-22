# Arabic phoneme recogniser: results (15 Nov 2026)

How to reproduce: [README.md](README.md). All numbers: RTX 5070 Ti, PyTorch 2.11 + CUDA 12.8, Python 3.12.

## Held-out PER

300 fixed utterances from the Iqra'Eval dev split (Common Voice Arabic dev speakers, adults, read MSA;
0 sentences shared with the training shards). Targets = `arabic_phonemes(vowelized text)`.
PER = edits / target length; class columns count a substitution/deletion against the target symbol's class
and an insertion against the inserted symbol's class.

| Model | PER | short vowels (a i u) | long vowels (aa ii uu) | consonants |
|---|---|---|---|---|
| `facebook/wav2vec2-lv-60-espeak-cv-ft` (the starting model, IPA mapped to our set) | **34.2%** | 39.3% | 43.5% | 29.5% |
| **Ours, run 1:** 4 shards (10.8 h), 2000 steps, 6.6 min | 20.3% | 22.7% | 23.7% | 18.3% |
| **Ours, run 2:** 12 shards (32.5 h), 7000 steps, 21 min | 14.7% | 18.3% | 16.9% | 12.2% |
| **Ours, run 3 (in the backend):** all 29 shards (79 h, 71k utterances), 60000 steps (~7 passes), 3.1 h | **9.75%** | 14.9% | 9.7% | 6.9% |
| Iqra'Eval official baseline (`IqraEval/Iqra_wav2vec2_base`, s3prl) | 11.8% | 16.1% | 11.3% | 9.5% |

Against the dataset's own labels instead of our converter, run 2 gets 14.8% and the Iqra'Eval baseline 11.7%:
the converter costs nothing.

Training curve, run 3 (dev PER): step 0 39.5% → 5k 15.1% → 10k 13.3% → 20k 11.3% → 30k 10.7% → 40k 10.0% →
50k 9.6% → 60k 9.7%. Run 3 is the model saved at the last step, not the best step picked on dev.
Run 2 for comparison: 1k 21.0% → 3k 16.2% → 5k 15.3% → 7k 14.8%. Inference: ~0.02 s per utterance on the GPU.

**Reading the table**
- The starting model is not usable for Arabic scoring: one sound in three is wrong, and vowels, the
  thing our games score most, are worst (39–44%).
- Fine-tuning on all the data cuts PER from 34% to under 10%: about one sound in ten is wrong, consonants one in
  fifteen. Vowel-length errors drop from 44% to 10%.
- Run 3 beats the Iqra'Eval official baseline on every class, although the baseline also trained on 55k TTS
  utterances and its best checkpoint was picked on this same dev split. The curve flattened after ~45k steps, so
  more of the same training won't help much; more varied data would (Iqra_TTS, our own pilot recordings).
- Short vowels stay the hardest class for every model (15–18%): they are short and unstressed, and Common Voice
  readers often skip case endings that the vowelized text writes. Part of that "error" is the label, not the model.

## Phoneme set decision: the Iqra'Eval MSA symbol set, not espeak-ng IPA

Measured on all 2588 dev sentences against the Iqra'Eval labels (`g2p_check.py --espeak`):

| Text → phonemes | PER vs labels |
|---|---|
| `arabic_phonemes()` (ours) | **0.6%** |
| espeak-ng `ar` (what backend/app/g2p.py would use, IPA mapped) | 16.6% |

espeak-ng on vowelized MSA: it pronounces hamzat al-wasl inside sentences (فِي السَّمَاوَاتِ → `f iː ʔ a s s s a…`),
writes three s's for an assimilated sun letter, reads shadda on و/ي as a vowel (سَيِّدِي → `s a iː i d iː`), drops
the w in أُوَاجَهَ, pronounces tanwin and final vowels at a pause, and marks emphasis with odd tokens (`a.`, `s̪`).
The Iqra'Eval set handles all of these, has one token per sound (`aa` long vowel, `bb` shadda), and is what
every public Arabic phoneme dataset and baseline we found uses. So:

- **Symbols:** 28 consonants `b t ^ j H x d * r z s $ S D T Z E g f q k l m n h w y <`, their geminates (`bb`...),
  vowels `a i u aa ii uu`. 62 in total (`SYMBOLS` in `arabic_phonemes.py`).
- **Folded:** the labels' emphatic vowel allophones (`A I U AA II UU`) become lowercase. Context decides them,
  a reader can't choose them, so they can never be a reading mistake.
- **`arabic_phonemes(text)`** is our own code (the MSA_phonetiser repo has no licence, so nothing is copied),
  no dependencies, with a self-check. It expects vowelized text, reads the last word in pause (كِتَابٌ → `k i t aa b`),
  and keeps vowel length and shadda, which the `vowel_length` and shadda errors need.

## In the backend

`backend/app/speech.py` loads `ml/models/arabic-phoneme` (run 3) for Arabic targets, or the folder in
`ARABIC_SPEECH_MODEL`; `backend/app/arabic_phonemes.py` is a byte-identical copy of the converter (a test checks
it); `scoring.py` has the Arabic error types in this symbol set. Details: [docs/design.md](../docs/design.md).
The model is not in git (1.2 GB): copy the folder to each machine or the server. Same size as the starting model
(wav2vec2 large, 317M parameters), so GPU timings carry over.

## Data and licences

| What | Licence | Notes |
|---|---|---|
| IqraEval/Iqra_train (all 29 train shards + dev, 11.3 GB on disk) | CC BY-NC 4.0 | audio is Mozilla Common Voice Arabic (CC0); vowelized text + labels by Iqra'Eval. Public, no login |
| facebook/wav2vec2-lv-60-espeak-cv-ft (1.3 GB) | Apache-2.0 | starting point + baseline |
| IqraEval/Iqra_wav2vec2_base (0.6 GB) + facebook/wav2vec2-base (0.4 GB) | Apache-2.0 | official baseline; loaded with `weights_only=True` (no pickled code runs) |
| Iqra-Eval GitHub repos (interspeech_IqraEval, MSA_phonetiser) | no licence file | vocab file read at run time; nothing copied into ml/ |

## Risks

- **Licence:** the fine-tuned model inherits CC BY-NC 4.0 from Iqra_train in practice. Fine for research and this
  competition, not for a paid product. Fix: label Common Voice Arabic (CC0) ourselves with `arabic_phonemes()`
  after diacritizing (CATT/Mishkal), then re-run `train.py` on that.
- **Domain gap:** dev is adults reading full MSA sentences. The games score single words, and the intended readers
  are children with dyslexia. The adult pilot measured single words ([docs/research.md](../docs/research.md#4-adult-pilot));
  children are not measured yet.
- **Very short audio:** CTC models are weakest on sub-second clips, so recordings keep some silence around the word.
- **Label noise:** some Common Voice readers skip case endings or misread; the labels follow the text. That inflates
  short-vowel PER for every model and teaches the model a bit of "expected" rather than "said".
- **Pausal rule:** `arabic_phonemes()` drops the last word's final short vowel (normal reading). The backend also
  accepts the final vowel or tanwin read in full (`scoring._without_final_vowel`), since both are correct Arabic.
