"""Audio -> what the player actually said, with a phoneme model (GPU when available, otherwise CPU).

Interface main.py relies on (keep it):

    recognize(audio: bytes, content_type: str, arabic: bool = False) -> tuple[str, list[str]]
        returns (heard_text, heard_phonemes), e.g. ("", ["k", "i", "t", "aa", "b"])
        heard_phonemes  one phoneme per item, raw from the model; main.py normalises them.
        heard_text      empty for now: main.py shows the target when the answer is right.
        Silence gives ("", []). Raises SpeechUnavailable without the speech packages, BadAudio for unreadable audio.

    recognize_timed(audio: bytes, arabic: bool = True) -> list[tuple[str, int]]
        the same phonemes with the time each one starts, in ms from the start of the recording (Rhythmic Reading).

    recognize_fit(audio: bytes, target: list[str]) -> tuple[list[str], float | None]
        Arabic: the heard phonemes, and how much worse the target fits the recording than the model's own reading
        (the "gap", in nats; 0 when they agree). scoring.py uses it so one shaky sound doesn't fail a word.

Each model outputs the symbols app/g2p.py gives that language's targets, so they compare:
Arabic: our fine-tuned model (ml/, Iqra'Eval symbols). English: the espeak IPA model it was fine-tuned from.
"""
import io
import os
import threading
from functools import lru_cache
from pathlib import Path

ENGLISH_MODEL = "facebook/wav2vec2-lv-60-espeak-cv-ft"
# A local folder (ml/models/..., git-ignored) or a Hugging Face repo id. Trained on CC BY-NC data: non-commercial.
ARABIC_MODEL = os.getenv("ARABIC_SPEECH_MODEL") or str(Path(__file__).resolve().parents[2] / "ml/models/arabic-phoneme")
RATE = 16_000  # the model was trained on 16 kHz mono
MIN_SECONDS = 0.2  # shorter than this is a tap, not an answer

_lock = threading.Lock()  # one inference at a time keeps memory bounded


class SpeechUnavailable(Exception):
    pass


class BadAudio(Exception):
    pass


def _decode(audio: bytes):
    """webm/opus (Chrome, Firefox), mp4 (Safari) or wav -> 16 kHz mono float32. PyAV bundles ffmpeg."""
    try:
        import av
        import numpy as np
    except ImportError as e:
        raise SpeechUnavailable("speech packages not installed: see backend/requirements-speech.txt") from e
    try:
        with av.open(io.BytesIO(audio)) as container:
            resampler = av.AudioResampler(format="flt", layout="mono", rate=RATE)
            chunks = [r.to_ndarray().reshape(-1) for frame in container.decode(audio=0) for r in resampler.resample(frame)]
            chunks += [r.to_ndarray().reshape(-1) for r in resampler.resample(None)]
    except (av.error.FFmpegError, IndexError, ValueError) as e:  # IndexError: the file has no audio stream
        raise BadAudio("Could not read the recording") from e
    return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)


@lru_cache(maxsize=2)
def _load(name: str):
    try:
        import torch
        from transformers import AutoModelForCTC, AutoProcessor
    except ImportError as e:
        raise SpeechUnavailable("speech packages not installed: see backend/requirements-speech.txt") from e
    if name == ARABIC_MODEL and not os.path.isdir(name) and not os.getenv("ARABIC_SPEECH_MODEL"):
        raise SpeechUnavailable("Arabic speech model not found: train it (ml/README.md) or set ARABIC_SPEECH_MODEL")
    device = "cuda" if torch.cuda.is_available() else "cpu"  # NVIDIA, and AMD via PyTorch's ROCm build, both report as "cuda"
    processor = AutoProcessor.from_pretrained(name)
    model = AutoModelForCTC.from_pretrained(name).to(device).eval()
    return torch, processor, model, device


def warm_up() -> None:
    """Load the Arabic model before the first player speaks. English loads on its first use."""
    try:
        _load(ARABIC_MODEL)
    except SpeechUnavailable:
        pass


def _logits(samples, arabic: bool):
    """Scores for every token per 20 ms frame, and the processor that names them."""
    torch, processor, model, device = _load(ARABIC_MODEL if arabic else ENGLISH_MODEL)
    inputs = processor(samples, sampling_rate=RATE, return_tensors="pt")
    with _lock, torch.inference_mode():
        return model(inputs.input_values.to(device)).logits, processor


def _frames(samples, arabic: bool):
    """Best token id per 20 ms frame, and the processor that names them."""
    logits, processor = _logits(samples, arabic)
    return logits.argmax(-1), processor


def recognize(audio: bytes, content_type: str, arabic: bool = False) -> tuple[str, list[str]]:
    samples = _decode(audio)
    if len(samples) < MIN_SECONDS * RATE:
        return "", []
    ids, processor = _frames(samples, arabic)
    return "", processor.batch_decode(ids)[0].split()


def recognize_timed(audio: bytes, arabic: bool = True) -> list[tuple[str, int]]:
    """[(phoneme, start_ms)] from the start of the recording: CTC's greedy decode, keeping where each run starts."""
    samples = _decode(audio)
    if len(samples) < MIN_SECONDS * RATE:
        return []
    ids, processor = _frames(samples, arabic)
    ids = ids[0].tolist()
    tokenizer = processor.tokenizer
    skip = {tokenizer.pad_token_id, *tokenizer.all_special_ids, tokenizer.convert_tokens_to_ids("|")}
    ms_per_frame = len(samples) / RATE * 1000 / len(ids)
    return [(tokenizer.convert_ids_to_tokens(i), round(f * ms_per_frame))
            for f, i in enumerate(ids) if i not in skip and (f == 0 or ids[f - 1] != i)]


def recognize_fit(audio: bytes, target: list[str]) -> tuple[list[str], float | None]:
    """Goodness of pronunciation (Witt & Young 2000, here with CTC): compare how likely the recording is as the
    target with how likely it is as the model's own reading. A word read right but transcribed with one slip fits
    the target almost as well; a real misreading fits it much worse. None: a target sound the model doesn't know."""
    samples = _decode(audio)
    if len(samples) < MIN_SECONDS * RATE:
        return [], None
    torch, *_ = _load(ARABIC_MODEL)
    logits, processor = _logits(samples, arabic=True)
    log_probs = logits.float().log_softmax(-1)[0].cpu()
    tokenizer = processor.tokenizer
    blank, vocab = tokenizer.pad_token_id, tokenizer.get_vocab()
    ids = log_probs.argmax(-1).tolist()
    heard_ids = [i for f, i in enumerate(ids) if i != blank and (f == 0 or ids[f - 1] != i)]
    heard = tokenizer.convert_ids_to_tokens(heard_ids)
    if not heard_ids or any(p not in vocab for p in target):
        return heard, None

    def nll(seq):
        return torch.nn.functional.ctc_loss(log_probs.unsqueeze(1), torch.tensor([seq]), [len(ids)], [len(seq)],
                                            blank=blank, reduction="sum").item()

    return heard, nll([vocab[p] for p in target]) - nll(heard_ids)

