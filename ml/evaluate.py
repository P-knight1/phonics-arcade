"""Phoneme error rate of a CTC phoneme model on Arabic speech.

    python evaluate.py --model facebook/wav2vec2-lv-60-espeak-cv-ft        # held-out Iqra'Eval dev sample
    python evaluate.py --model models/arabic-phoneme --csv my_clips.csv   # your own clips: columns path,text
    python evaluate.py --model models/iqra_baselines/wave2vec2_base.ckpt  # official Iqra'Eval baseline

Targets come from arabic_phonemes(vowelized text), as the backend will compute them. Model output is
mapped into the same symbol set first (IPA models via IPA_MAP), so every model is scored on equal terms.
"""
import argparse
import csv
import json
import time

import torch
from transformers import AutoModelForCTC, AutoProcessor

from arabic_phonemes import SYMBOLS, arabic_phonemes, fold
from common import RATE, decode, load, per

# espeak IPA (facebook/wav2vec2-lv-60-espeak-cv-ft) -> our symbols. Vowel qualities collapse to a/i/u:
# Arabic has 3 vowel qualities, the colour (ɑ, æ, ɛ...) depends on neighbouring consonants.
IPA_MAP = {
    "ʔ": "<", "ʕ": "E", "ħ": "H", "χ": "x", "ʃ": "$", "θ": "^", "ð": "*", "dʒ": "j", "ʒ": "j", "ɡ": "j", "g": "j",
    "ɣ": "g", "ʁ": "g", "sˤ": "S", "dˤ": "D", "tˤ": "T", "ðˤ": "Z", "zˤ": "Z", "ɾ": "r", "ɫ": "l", "c": "k",
    **{v: "a" for v in ["ɑ", "æ", "ɐ", "ʌ", "ə", "ɛ", "e", "a"]},
    **{v + "ː": "aa" for v in ["ɑ", "æ", "ɐ", "ʌ", "ə", "ɛ", "e", "a"]},
    "ɪ": "i", "ɨ": "i", "i": "i", "iː": "ii", "ʊ": "u", "o": "u", "ɔ": "u", "u": "u", "uː": "uu", "oː": "uu", "ɔː": "uu",
    "j": "y", "s̪": "s", "t̪": "t", "t[": "t", "d[": "d", "ɯ": "u", "ɹ": "r", "ŋ": "n", "p": "b", "v": "f", "ɬ": "l",
    "aɪ": "a y", "aʊ": "a w",  # diphthongs are two sounds in Arabic
}


def from_ipa(tokens):
    out = []
    for t in tokens:
        t = t.replace("ˈ", "").replace("ˌ", "").replace(".", "")  # stress; espeak "a." = pharyngealised
        geminate = t.endswith("ː") and t not in IPA_MAP
        p = IPA_MAP.get(t.rstrip("ː") if geminate else t, t.rstrip("ː") if geminate else t)
        p = p + p if geminate else p
        for p in p.split():
            if out and p == out[-1] and p not in ("a", "i", "u", "aa", "ii", "uu"):
                out[-1] = p + p  # CTC often writes a geminate as two tokens
            else:
                out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Hugging Face id or local folder of a CTC phoneme model")
    ap.add_argument("--n", type=int, default=300, help="held-out utterances (fixed sample of the dev split)")
    ap.add_argument("--csv", help="evaluate your own clips instead: CSV with columns path,text (vowelized)")
    ap.add_argument("--targets", choices=["g2p", "labels"], default="g2p", help="labels = the dataset's phoneme_ref")
    ap.add_argument("--vocab", default="data/src/interspeech_IqraEval/vocab/sws_arabic.txt", help="for .ckpt baselines")
    ap.add_argument("--show", type=int, default=5, help="print this many examples")
    args = ap.parse_args()

    if args.csv:
        with open(args.csv, encoding="utf-8") as f:
            data = [(decode(open(r["path"], "rb").read()), None, r["text"]) for r in csv.DictReader(f)]
    else:
        data = load("dev", args.n)
    refs = [lab if args.targets == "labels" else arabic_phonemes(text) for _, lab, text in data]

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if args.model.endswith(".ckpt"):  # official Iqra'Eval s3prl baseline
        from iqra_baseline import IqraBaseline
        baseline = IqraBaseline(args.model, args.vocab, device)
        recognize, ipa = baseline.recognize, False
    else:
        processor = AutoProcessor.from_pretrained(args.model)
        model = AutoModelForCTC.from_pretrained(args.model).to(device).eval()
        vocab = processor.tokenizer.get_vocab()
        ipa = "aː" in vocab or "ʔ" in vocab

        def recognize(samples):
            inputs = processor(samples, sampling_rate=RATE, return_tensors="pt")
            with torch.inference_mode(), torch.autocast(device, dtype=torch.bfloat16, enabled=device == "cuda"):
                ids = model(inputs.input_values.to(device)).logits.argmax(-1)
            return processor.batch_decode(ids)[0].split()

    hyps, start = [], time.time()
    for samples, _, _ in data:  # one at a time: no padding effects, and it's how the backend calls it
        tokens = recognize(samples)
        hyps.append(from_ipa(tokens) if ipa else fold(tokens))
    seconds = time.time() - start

    result = {"model": args.model, "utterances": len(data), "targets": args.targets, "per": per(refs, hyps),
              "out_of_set_symbols": sorted({p for h in hyps for p in h} - set(SYMBOLS)),
              "seconds_per_utterance": round(seconds / len(data), 3), "device": device}
    for (_, _, text), ref, hyp in list(zip(data, refs, hyps))[: args.show]:
        print(f"{text}\n  target: {' '.join(ref)}\n  model:  {' '.join(hyp)}")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
