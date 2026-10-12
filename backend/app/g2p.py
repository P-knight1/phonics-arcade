"""Text -> phonemes with espeak-ng: the same phoneme set the wav2vec2 espeak model outputs, so they compare."""
import threading
from functools import lru_cache

import espeakng_loader
from phonemizer.backend import EspeakBackend
from phonemizer.backend.espeak.wrapper import EspeakWrapper
from phonemizer.separator import Separator

from .scoring import normalize

# Bundled espeak-ng library: no system install on Windows, macOS or Linux.
EspeakWrapper.set_library(espeakng_loader.get_library_path())
EspeakWrapper.set_data_path(espeakng_loader.get_data_path())

LANGUAGE = "en-gb"  # matches the contract example ("dog" -> d ɒ g)
_SEPARATOR = Separator(phone=" ", word=" | ", syllable="")  # normalize() drops the "|"
_backend = EspeakBackend(LANGUAGE, with_stress=False, language_switch="remove-flags")
_lock = threading.Lock()  # espeak-ng is not thread-safe; FastAPI runs sync routes in a thread pool


@lru_cache(maxsize=4096)
def phonemes(text: str) -> tuple[str, ...]:
    """'dog' -> ('d', 'ɒ', 'g'). Punctuation is dropped; empty text gives ()."""
    with _lock:
        out = _backend.phonemize([text], separator=_SEPARATOR, strip=True)[0]
    return tuple(normalize(out.split()))
