"""Fine-tune a wav2vec2 CTC model into an Arabic phoneme recogniser (Iqra'Eval symbol set, see arabic_phonemes.py).

    python train.py --steps 7000 --minutes 25 --lr 1e-4    # short proof run (README: exact commands)
    python train.py --steps 60000 --minutes 600 --lr 1e-4  # overnight

Starts from facebook/wav2vec2-lv-60-espeak-cv-ft (already a multilingual phoneme recogniser) with a new
output layer for our 62 symbols. Each new output row starts as a copy of the nearest espeak IPA row, so the
model can already roughly read Arabic at step 0 and a short run is enough to show the PER drop.
Labels: the dataset's phoneme_ref (Iqra'Eval MSA phonetiser), emphatic vowels folded (fold()).
"""
import argparse
import json
import os
import random
import time

import numpy as np
import torch
from transformers import AutoModelForCTC, AutoProcessor, Wav2Vec2PhonemeCTCTokenizer, Wav2Vec2Processor
from transformers import get_linear_schedule_with_warmup

from arabic_phonemes import SYMBOLS
from common import RATE, load, per

BASE = "facebook/wav2vec2-lv-60-espeak-cv-ft"
# our symbol -> the espeak IPA token whose output row initialises it (geminates use the single consonant)
NEAREST_IPA = {"<": "ʔ", "E": "ʕ", "H": "ħ", "$": "ʃ", "^": "θ", "*": "ð", "j": "dʒ", "g": "ɣ", "S": "s", "D": "dˤ",
               "T": "t", "Z": "ð", "y": "j", "aa": "aː", "ii": "iː", "uu": "uː"}


def build_processor(out_dir):
    vocab = {"<pad>": 0, "<unk>": 1, **{s: i + 2 for i, s in enumerate(SYMBOLS)}}  # <pad> is the CTC blank
    os.makedirs(out_dir, exist_ok=True)
    with open(f"{out_dir}/vocab.json", "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False)
    tokenizer = Wav2Vec2PhonemeCTCTokenizer(f"{out_dir}/vocab.json", do_phonemize=False, pad_token="<pad>",
                                            unk_token="<unk>", bos_token=None, eos_token=None)
    return Wav2Vec2Processor(AutoProcessor.from_pretrained(BASE).feature_extractor, tokenizer)


def init_head(model, base_head, base_vocab, vocab):
    with torch.no_grad():
        for sym, i in vocab.items():
            if sym not in NEAREST_IPA and sym not in base_vocab:
                sym = sym[0]  # geminate "bb" -> "b"
            j = base_vocab.get(NEAREST_IPA.get(sym, sym))
            if j is not None:
                model.lm_head.weight[i] = base_head.weight[j]
                model.lm_head.bias[i] = base_head.bias[j]


def batches(data, batch_size, seed):
    """Shuffled batches of similar length (less padding = faster steps)."""
    rng = random.Random(seed)
    idx = list(range(len(data)))
    rng.shuffle(idx)
    groups = [sorted(idx[k:k + 50 * batch_size], key=lambda i: len(data[i][0])) for k in range(0, len(idx), 50 * batch_size)]
    out = [g[k:k + batch_size] for g in groups for k in range(0, len(g), batch_size)]
    rng.shuffle(out)
    return out


def transcribe(model, processor, data, device):
    hyps = []
    model.eval()
    for samples, _, _ in data:
        x = processor(samples, sampling_rate=RATE, return_tensors="pt").input_values.to(device)
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            hyps.append(processor.batch_decode(model(x).logits.argmax(-1))[0].split())
    model.train()
    return hyps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="models/arabic-phoneme")
    ap.add_argument("--steps", type=int, default=7000)
    ap.add_argument("--minutes", type=float, default=25, help="stop (and save) after this long, whatever --steps says")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--eval_every", type=int, default=250)
    ap.add_argument("--dev_n", type=int, default=300, help="same held-out sample as evaluate.py")
    args = ap.parse_args()
    torch.manual_seed(0)
    device = "cuda"

    t0 = time.time()
    train, dev = load("train", compact=True), load("dev", args.dev_n)
    print(f"{len(train)} train / {len(dev)} dev utterances, {sum(len(s) for s, _, _ in train) / RATE / 3600:.1f} h "
          f"train audio, loaded in {time.time() - t0:.0f}s", flush=True)

    processor = build_processor(args.out)
    vocab = processor.tokenizer.get_vocab()
    base = AutoModelForCTC.from_pretrained(BASE)
    model = AutoModelForCTC.from_pretrained(BASE, vocab_size=len(vocab), pad_token_id=0, ignore_mismatched_sizes=True,
                                            ctc_loss_reduction="mean", ctc_zero_infinity=True, layerdrop=0.05)
    init_head(model, base.lm_head, AutoProcessor.from_pretrained(BASE).tokenizer.get_vocab(), vocab)
    del base
    model.freeze_feature_encoder()  # the CNN front end is language-independent
    model.activation_checkpointing_enable()
    model.to(device).train()

    refs = [lab for _, lab, _ in dev]
    print("step 0 dev PER", per(refs, transcribe(model, processor, dev, device)), flush=True)

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=0.01)
    sched = get_linear_schedule_with_warmup(opt, min(500, args.steps // 10), args.steps)
    step, start, epoch, done = 0, time.time(), 0, False
    while not done:
        for b in batches(train, args.batch, epoch):
            feats = processor([train[i][0].astype(np.float32) for i in b], sampling_rate=RATE, return_tensors="pt", padding=True)
            labels = processor.tokenizer([" ".join(train[i][1]) for i in b], padding=True, return_tensors="pt")
            labels = labels.input_ids.masked_fill(labels.attention_mask == 0, -100)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                loss = model(feats.input_values.to(device), attention_mask=feats.attention_mask.to(device),
                             labels=labels.to(device)).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sched.step(); opt.zero_grad()
            step += 1
            if step % 50 == 0:
                print(f"step {step} loss {loss.item():.3f} lr {sched.get_last_lr()[0]:.2e} "
                      f"{(time.time() - start) / 60:.1f} min", flush=True)
            if step % args.eval_every == 0:
                print(f"step {step} dev PER", per(refs, transcribe(model, processor, dev, device)), flush=True)
                model.save_pretrained(args.out)  # a crash on a long run keeps the last checkpoint
                processor.save_pretrained(args.out)
            if step >= args.steps or time.time() - start > args.minutes * 60:
                done = True
                break
        epoch += 1

    print(f"stopped at step {step} (epoch {epoch}), {(time.time() - start) / 60:.1f} min training", flush=True)
    print(f"final dev PER", per(refs, transcribe(model, processor, dev, device)), flush=True)
    model.save_pretrained(args.out)
    processor.save_pretrained(args.out)
    print("saved", args.out)


if __name__ == "__main__":
    main()
