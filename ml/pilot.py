"""Adult pilot: does the app judge a reading the way a human listener does?

    python pilot.py --check                 # pilot_items.csv: each 'said' gives its intended error (no audio)
    python pilot.py clips.csv               # agreement on recorded clips (uses the GPU if free)

clips.csv columns: path,target,said
    target  the vowelized word shown on screen
    said    what the reader actually said, written vowelized by the human listener (= target when read right)
The human label is scoring(target, said); the app's verdict is scoring(target, model(audio), gap), exactly as /score
does it (a "read it again" result is counted with its error type, as the app's second try would be, and reported). Keep recordings in ml/data/pilot/ (git-ignored) and follow docs/research.md section 7.
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from app import scoring  # noqa: E402  the backend's own scoring, so the pilot measures what players get
from app.arabic_phonemes import arabic_phonemes  # noqa: E402


def human(target, said):
    return scoring.score(arabic_phonemes(target), arabic_phonemes(said), target)


def agreement(rows, verdicts):
    """Flagging (right vs wrong) as a binary test where 'wrong' is positive, plus error-type agreement."""
    pairs = [(human(r["target"], r["said"]), v) for r, v in zip(rows, verdicts)]
    tp = sum(not h["correct"] and not v["correct"] for h, v in pairs)
    fp = sum(h["correct"] and not v["correct"] for h, v in pairs)
    fn = sum(not h["correct"] and v["correct"] for h, v in pairs)
    wrong = [(h, v) for h, v in pairs if not h["correct"]]
    return {
        "clips": len(pairs),
        "verdict_agreement": round(sum(h["correct"] == v["correct"] for h, v in pairs) / len(pairs), 3),
        "error_recall": round(tp / (tp + fn), 3) if tp + fn else None,       # real mistakes the app caught
        "error_precision": round(tp / (tp + fp), 3) if tp + fp else None,    # app's flags that were real mistakes
        "error_type_agreement": round(sum(h["error_type"] == v["error_type"] for h, v in wrong) / len(wrong), 3)
        if wrong else None,                                                  # among real mistakes
        "by_type": {t: f"{sum(v['error_type'] == t for h, v in wrong if h['error_type'] == t)}/"
                       f"{sum(h['error_type'] == t for h, _ in wrong)}" for t in sorted({h["error_type"] for h, _ in wrong})},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", nargs="?", help="CSV with columns path,target,said")
    ap.add_argument("--check", action="store_true", help="check pilot_items.csv instead")
    args = ap.parse_args()

    if args.check:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pilot_items.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        bad = [r for r in rows if human(r["target"], r["said"])["error_type"] != r["error"]]
        assert not bad, bad
        perfect = agreement(rows, [human(r["target"], r["said"]) for r in rows])
        assert perfect["verdict_agreement"] == perfect["error_recall"] == perfect["error_type_agreement"] == 1, perfect
        accept_all = agreement(rows, [human(r["target"], r["target"]) for r in rows])  # an app like "accept everything"
        assert accept_all["error_recall"] == 0 and accept_all["verdict_agreement"] == round(8 / 24, 3), accept_all
        print("ok")
        return

    from app import speech
    with open(args.clips, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    verdicts = []
    for r in rows:
        target = arabic_phonemes(r["target"])
        with open(r["path"], "rb") as audio:
            heard, gap = speech.recognize_fit(audio.read(), target)
        verdicts.append(scoring.score(target, heard, r["target"], gap=gap))
        v = verdicts[-1]
        print(r["target"], "| said:", r["said"], "| app:", " ".join(heard), f"gap={gap if gap is None else round(gap, 1)}",
              v["error_type"], "(read again)" if v["unclear"] else "")
    result = agreement(rows, verdicts)
    unclear = [h for h, v in ((human(r["target"], r["said"]), v) for r, v in zip(rows, verdicts)) if v["unclear"]]
    result["read_again"] = {"clips": len(unclear), "of_them_read_right": sum(h["correct"] for h in unclear)}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
