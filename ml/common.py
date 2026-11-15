"""Shared by evaluate.py and train.py: read Iqra'Eval parquet shards, decode audio, score PER."""
import glob
import io

import av
import numpy as np
import pyarrow.parquet as pq

from arabic_phonemes import fold

RATE = 16_000
DATA = "data/iqra_train/data"
SHORT, LONG = {"a", "i", "u"}, {"aa", "ii", "uu"}


def decode(audio: bytes) -> np.ndarray:
    """mp3/webm/wav bytes -> 16 kHz mono float32 (same decoding as backend/app/speech.py)."""
    with av.open(io.BytesIO(audio)) as container:
        resampler = av.AudioResampler(format="flt", layout="mono", rate=RATE)
        chunks = [r.to_ndarray().reshape(-1) for f in container.decode(audio=0) for r in resampler.resample(f)]
        chunks += [r.to_ndarray().reshape(-1) for r in resampler.resample(None)]
    return np.concatenate(chunks) if chunks else np.zeros(0, np.float32)


def load(split: str, limit: int | None = None, seed: int = 0, max_seconds: float = 15.0, compact: bool = False):
    """split 'dev' or 'train' -> list of (samples float32, folded label phonemes, vowelized text).

    dev: a fixed random sample of `limit` rows (same rows every run). train: every downloaded shard.
    compact: keep samples as float16 (half the RAM: all 29 shards are ~80 h of audio, 18 GB as float32).
    """
    files = sorted(glob.glob(f"{DATA}/{split}-*.parquet"))
    assert files, f"no {split} shards in {DATA}: see README 'Data'"
    out = []
    for f in files:  # one shard at a time: all mp3 bytes at once would be 12 GB
        rows = pq.read_table(f, columns=["audio", "phoneme_ref", "tashkeel_sentence"]).to_pylist()
        if limit:  # per shard; dev is a single shard
            rows = [rows[i] for i in np.random.default_rng(seed).permutation(len(rows))[:limit]]
        for r in rows:
            samples = decode(r["audio"]["bytes"])
            if 0 < len(samples) <= max_seconds * RATE:
                out.append((samples.astype(np.float16) if compact else samples, fold(r["phoneme_ref"].split()),
                            r["tashkeel_sentence"]))
    return out


def _align(ref, hyp):
    """Levenshtein alignment -> list of (ref_symbol | None, hyp_symbol | None)."""
    d = np.zeros((len(ref) + 1, len(hyp) + 1), dtype=np.int32)
    d[:, 0], d[0, :] = range(len(ref) + 1), range(len(hyp) + 1)
    for i in range(1, len(ref) + 1):
        for j in range(1, len(hyp) + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]))
    pairs, i, j = [], len(ref), len(hyp)
    while i or j:
        if i and j and d[i, j] == d[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]):
            pairs.append((ref[i - 1], hyp[j - 1])); i -= 1; j -= 1
        elif i and d[i, j] == d[i - 1, j] + 1:
            pairs.append((ref[i - 1], None)); i -= 1
        else:
            pairs.append((None, hyp[j - 1])); j -= 1
    return pairs


def _cls(p):
    return "short_vowel" if p in SHORT else "long_vowel" if p in LONG else "consonant"


def per(refs, hyps) -> dict:
    """PER = edits / reference length, overall and per class. A substitution or deletion counts against
    the reference symbol's class, an insertion against the inserted symbol's class."""
    errors, counts = {}, {}
    for ref, hyp in zip(refs, hyps):
        for r in ref:
            counts[_cls(r)] = counts.get(_cls(r), 0) + 1
        for r, h in _align(ref, hyp):
            if r != h:
                c = _cls(r if r is not None else h)
                errors[c] = errors.get(c, 0) + 1
    out = {c: round(errors.get(c, 0) / counts[c], 4) for c in ("short_vowel", "long_vowel", "consonant") if counts.get(c)}
    out["all"] = round(sum(errors.values()) / sum(counts.values()), 4)
    return out


if __name__ == "__main__":  # self-check
    assert per([["k", "i", "t", "aa", "b"]], [["k", "i", "t", "aa", "b"]])["all"] == 0
    r = per([["k", "i", "t", "aa", "b"]], [["k", "a", "t", "a", "b", "u"]])  # 2 vowel subs + 1 insertion
    assert r == {"short_vowel": 2.0, "long_vowel": 1.0, "consonant": 0.0, "all": 0.6}, r
    print("ok")
