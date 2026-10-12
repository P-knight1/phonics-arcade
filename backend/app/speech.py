"""Audio -> what the player actually said. Owned by AI & Infrastructure (role 1); runs on the AMD droplet.

Interface main.py relies on (keep it):

    recognize(audio: bytes, content_type: str) -> tuple[str, list[str]]
        returns (heard_text, heard_phonemes)
        heard_text      the word to show the player, e.g. "bog". Whisper tends to write the *intended*
                        word ("dog"), so derive this from the phonemes where you can.
        heard_phonemes  one IPA phoneme per item, e.g. ["b", "ɒ", "ɡ"] (the phoneme model's output split on
                        spaces). main.py normalises stress/length marks and ɡ->g, so pass them through raw.
        Return ("", []) for silence. Raise SpeechUnavailable while models are not loaded.

Audio arrives as webm/opus (Chrome, Firefox) or mp4 (Safari). ffmpeg is in the Docker image for decoding.
Targets are phonemised by app/g2p.py (espeak-ng, en-gb): run a few through it to check your model's output
uses the same symbols.
"""


class SpeechUnavailable(Exception):
    pass


def recognize(audio: bytes, content_type: str) -> tuple[str, list[str]]:
    raise SpeechUnavailable("speech recognition is not connected yet; use heard_text (debug mode) or MOCK_MODE=1")
