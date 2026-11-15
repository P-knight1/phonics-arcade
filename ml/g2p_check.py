"""Which text->phoneme converter gives cleaner Arabic labels? Both are scored against the Iqra'Eval dev labels.

    python g2p_check.py            # arabic_phonemes() only
    python g2p_check.py --espeak   # also espeak-ng 'ar' (pip install phonemizer-fork==3.3.2 espeakng-loader==0.2.4)
"""
import argparse
import glob

import pyarrow.parquet as pq

from arabic_phonemes import arabic_phonemes, fold
from common import DATA, per

ap = argparse.ArgumentParser()
ap.add_argument("--espeak", action="store_true")
ap.add_argument("--show", type=int, default=3)
args = ap.parse_args()

rows = pq.read_table(glob.glob(f"{DATA}/dev-*.parquet")[0], columns=["phoneme_ref", "tashkeel_sentence"]).to_pylist()
refs = [fold(r["phoneme_ref"].split()) for r in rows]
texts = [r["tashkeel_sentence"] for r in rows]
systems = {"arabic_phonemes": [arabic_phonemes(t) for t in texts]}

if args.espeak:
    import espeakng_loader
    from phonemizer.backend import EspeakBackend
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    from phonemizer.separator import Separator

    from evaluate import from_ipa

    EspeakWrapper.set_library(espeakng_loader.get_library_path())
    EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
    espeak = EspeakBackend("ar", with_stress=False, language_switch="remove-flags")  # as backend/app/g2p.py, Arabic
    out = espeak.phonemize(texts, separator=Separator(phone=" ", word=" | "), strip=True)
    systems["espeak-ng ar"] = [from_ipa(o.replace("|", " ").split()) for o in out]

for name, hyps in systems.items():
    print(name, len(rows), "sentences, PER vs Iqra'Eval labels:", per(refs, hyps))
    for t, r, h in list(zip(texts, refs, hyps))[: args.show]:
        print(f"  {t}\n    labels: {' '.join(r)}\n    {name}: {' '.join(h)}")
