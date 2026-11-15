"""Vowelized MSA text -> phonemes in the Iqra'Eval symbol set (Buckwalter-style, one token per sound).

Written from scratch (the Iqra'Eval MSA_phonetiser repo has no licence, so we don't copy it), but it
emits the same symbols as its labels so our model, trained on those labels, compares 1:1 with targets.
Self-contained on purpose: the backend can copy this file verbatim.

Symbols: consonants  b t ^(ث) j H(ح) x(خ) d *(ذ) r z s $(ش) S(ص) D(ض) T(ط) Z(ظ) E(ع) g(غ) f q k l m n h w y <(hamza)
         geminate (shadda) = doubled symbol, e.g. "bb"
         vowels      a i u (short), aa ii uu (long)
The Iqra'Eval labels also write emphatic allophones A I U AA II UU; we fold them to lowercase (fold()):
a speaker can't choose them, so they are never a reading error.

Rules (fully vowelized input; unvowelized letters just give their consonant):
- the last word is read in pause: its final short vowel is dropped; tanwin -un/-in is always dropped (as in the labels)
- hamzat al-wasl is silent; only the article opening a sentence is read "< a" (as in the labels)
- sun letters: an unmarked ل before a letter with shadda is assimilated (الشَّمْس -> $$ a m s)
- ا ى after fatha, و after damma, ي after kasra lengthen the vowel; ة is t before a vowel, silent in pause
"""
import re

LETTERS = dict(zip("بتثجحخدذرزسشصضطظعغفقكلمنهويءأإؤئ",
                   "b t ^ j H x d * r z s $ S D T Z E g f q k l m n h w y < < < < <".split()))
FATHA, DAMMA, KASRA = "َ", "ُ", "ِ"
FATHATAN, DAMMATAN, KASRATAN = "ً", "ٌ", "ٍ"
SUKUN, SHADDA, DAGGER_ALIF = "ْ", "ّ", "ٰ"
VOWEL = {FATHA: "a", DAMMA: "u", KASRA: "i"}
LONG = {"a": "aa", "u": "uu", "i": "ii"}
SYMBOLS = sorted(set(LETTERS.values()) | {c + c for c in LETTERS.values()} | set(VOWEL.values()) | set(LONG.values()))
TANWIN_OR_VOWEL = {FATHA, DAMMA, KASRA, FATHATAN, DAMMATAN, KASRATAN}
HIDDEN_ALIF = {"هذا", "هذه", "هذان", "هذين", "ذلك", "ذلكم", "لكن", "لكنه", "هؤلاء"}  # long first vowel, alif not written
_KEEP = re.compile(r"[^ء-غف-ْٰٱ\s]")  # Arabic letters + harakat; drops punctuation, digits, tatweel


def fold(phonemes):
    """Iqra'Eval labels -> our set: emphatic vowel allophones (A, II, ...) to lowercase."""
    return [p.lower() if p[0] in "AIU" else p for p in phonemes]


def _units(word):
    """'كَتَبَ' -> [('ك', {fatha}), ('ت', {fatha}), ('ب', {fatha})]"""
    units = []
    for ch in word:
        if FATHATAN <= ch <= SUKUN or ch == DAGGER_ALIF:
            if units:
                units[-1][1].add(ch)
        else:
            units.append((ch, set()))
    return units


def _word(units, first, last):
    out = []
    for k, (ch, marks) in enumerate(units):
        nxt = units[k + 1] if k + 1 < len(units) else None
        prev = out[-1] if out else None
        vowel = next((VOWEL[m] for m in marks if m in VOWEL), None)
        if ch in "اٱ" and (k == 0 or k <= 2 and nxt and nxt[0] == "ل" and all(u[0] in "وفبك" for u in units[:k])):
            if first and k == 0 and nxt and nxt[0] == "ل":  # hamzat al-wasl: silent, except the article opening a sentence
                out += ["<", "a"]
            continue
        if ch == "ا" and nxt is None and units[k - 1][0] == "و" and prev != "uu":
            continue  # silent alif after plural -w (تَوَلَّوْا)
        if ch in "اى":
            if prev in LONG:
                out[-1] = LONG[prev]
            elif prev not in ("aa", "ii", "uu"):  # unvowelized text, or tanwin alif after fathatan (handled below)
                out.append("aa")
            continue
        if ch == "آ":
            out += ["<", "aa"]
            continue
        if ch == "ة":
            if vowel and not last:
                out += ["t", vowel]
            continue
        if ch in "وي" and (not marks & TANWIN_OR_VOWEL or SHADDA in marks) and prev == ("u" if ch == "و" else "i"):
            out[-1] = LONG[prev]  # madd letter
            if SHADDA not in marks:
                continue
            marks = marks - {SHADDA}  # uww -> uu w (as the labels write it)
        if ch == "ل" and not marks and nxt and SHADDA in nxt[1]:
            continue  # sun-letter assimilation
        if ch not in LETTERS:
            continue
        c = LETTERS[ch]
        out.append(c + c if SHADDA in marks else c)
        if ch == "إ" and not vowel:
            vowel = "i"
        if vowel:
            out.append(vowel)
        elif FATHATAN in marks:
            out.append("aa" if nxt and nxt[0] == "ا" else "a")
        if DAGGER_ALIF in marks:  # هٰذَا: the small alif lengthens fatha
            if out[-1] == "a":
                out[-1] = "aa"
            else:
                out.append("aa")
    if last and out and out[-1] in ("a", "i", "u") and units[-1][0] != "ة":
        out.pop()  # pause
    if "".join(u[0] for u in units) in HIDDEN_ALIF and "a" in out:
        out[out.index("a")] = "aa"
    return out


def arabic_phonemes(text: str) -> list[str]:
    """'كِتَاب' -> ['k', 'i', 't', 'aa', 'b']. Expects vowelized MSA; empty text gives []."""
    words = _KEEP.sub("", text).split()
    return [p for i, w in enumerate(words) for p in _word(_units(w), i == 0, i == len(words) - 1)]


if __name__ == "__main__":  # self-check
    cases = {
        "بَاب": "b aa b",
        "كَتَبَ": "k a t a b",
        "كِتَابٌ": "k i t aa b",
        "مَدْرَسَةٌ": "m a d r a s a",
        "الشَّمْسُ": "< a $$ a m s",
        "ذَهَبَ النَّاسُ": "* a h a b a nn aa s",
        "قَدِ اسْتَوْعَبْتُهَا": "q a d i s t a w E a b t u h aa",
        "سَيِّدِي": "s a yy i d ii",
        "زُوِّجَت": "z uu w i j a t",
        "أَتَى": "< a t aa",
        "هَذَا وَالْكِتَابُ": "h aa * aa w a l k i t aa b",
        "تَوَلَّوْا": "t a w a ll a w",
        "نَائِيًا": "n aa < i y aa",
        "مَعَاشِرًا عُرْرًا": "m a E aa $ i r aa E u r r aa",
    }
    for text, want in cases.items():
        got = " ".join(arabic_phonemes(text))
        assert got == want, (text, got, want)
    assert all(p in SYMBOLS for text in cases for p in arabic_phonemes(text))
    assert fold(["q", "A", "d", "AA"]) == ["q", "a", "d", "aa"]
    print("ok")
