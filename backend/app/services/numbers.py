"""Spoken-number handling for Kannada and English.

- `normalize_numbers`: rewrites spoken numbers in a transcript as digits
  ("ಐವತ್ತೆರಡು" -> "52", "two point eight" -> "2.8").
- `to_kannada_words`: digits -> Kannada words for TTS read-back (Timbre docs ask
  for numbers as spoken words).
"""

from __future__ import annotations

import re

KN_UNITS = ["ಸೊನ್ನೆ", "ಒಂದು", "ಎರಡು", "ಮೂರು", "ನಾಲ್ಕು", "ಐದು", "ಆರು", "ಏಳು", "ಎಂಟು", "ಒಂಬತ್ತು"]
KN_TEENS = {
    10: "ಹತ್ತು", 11: "ಹನ್ನೊಂದು", 12: "ಹನ್ನೆರಡು", 13: "ಹದಿಮೂರು", 14: "ಹದಿನಾಲ್ಕು",
    15: "ಹದಿನೈದು", 16: "ಹದಿನಾರು", 17: "ಹದಿನೇಳು", 18: "ಹದಿನೆಂಟು", 19: "ಹತ್ತೊಂಬತ್ತು",
}
# Tens stems end in "ತ" (inherent vowel); compounds attach a vowel sign or drop it.
KN_TENS_STEM = {
    20: "ಇಪ್ಪತ್ತ", 30: "ಮೂವತ್ತ", 40: "ನಲವತ್ತ", 50: "ಐವತ್ತ",
    60: "ಅರವತ್ತ", 70: "ಎಪ್ಪತ್ತ", 80: "ಎಂಬತ್ತ", 90: "ತೊಂಬತ್ತ",
}
_VOWEL_SIGN = {"ಒ": "ೊ", "ಎ": "ೆ", "ಐ": "ೈ", "ಆ": "ಾ", "ಏ": "ೇ"}


def _kn_compound(stem: str, unit: int) -> str:
    word = KN_UNITS[unit]
    first = word[0]
    if first in _VOWEL_SIGN:  # ಇಪ್ಪತ್ತ + ೊಂದು -> ಇಪ್ಪತ್ತೊಂದು
        return stem + _VOWEL_SIGN[first] + word[1:]
    return stem[:-1] + word  # ಇಪ್ಪತ್ + ಮೂರು -> ಇಪ್ಪತ್ಮೂರು


def _build_kn_words() -> dict[int, str]:
    words = {i: w for i, w in enumerate(KN_UNITS)}
    words.update(KN_TEENS)
    for tens, stem in KN_TENS_STEM.items():
        words[tens] = stem + "ು"
        for unit in range(1, 10):
            words[tens + unit] = _kn_compound(stem, unit)
    return words


KN_WORDS: dict[int, str] = _build_kn_words()

EN_WORDS: dict[str, int] = {
    w: i for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen "
        "fourteen fifteen sixteen seventeen eighteen nineteen".split()
    )
}
EN_WORDS.update({"oh": 0, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
                 "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90})

WORD_TO_NUMBER: dict[str, int] = {**{w: n for n, w in KN_WORDS.items()}, **EN_WORDS}
WORD_TO_NUMBER.update({"ನೂರು": 100, "hundred": 100})
POINT_WORDS = {"point", "ಪಾಯಿಂಟ್", "ದಶಮಾಂಶ"}

_TOKEN = re.compile(r"\d+(?:\.\d+)?|[^\s\d.,!?;:]+|[.,!?;:]")


def _token_value(token: str) -> int | float | None:
    if re.fullmatch(r"\d+(?:\.\d+)?", token):
        return float(token) if "." in token else int(token)
    return WORD_TO_NUMBER.get(token.lower())


def normalize_numbers(text: str) -> str:
    """Replace spoken number sequences with digits. Digit-by-digit runs stay separate
    tokens ("ಒಂದು ಎರಡು" -> "1 2") so IDs can be joined later."""
    tokens = _TOKEN.findall(text)
    out: list[str] = []
    i = 0
    while i < len(tokens):
        value = _token_value(tokens[i])
        if value is None:
            out.append(tokens[i])
            i += 1
            continue
        # hundreds: "ನೂರು" / "one hundred" (+ optional tens/units)
        if value == 100 or (i + 1 < len(tokens) and _token_value(tokens[i + 1]) == 100 and isinstance(value, int) and value < 10):
            if value != 100:
                i += 1
                value = value * 100
            nxt = _token_value(tokens[i + 1]) if i + 1 < len(tokens) else None
            if isinstance(nxt, int) and nxt < 100:
                value += nxt
                i += 1
        # tens + unit spoken separately: "twenty eight", "ಇಪ್ಪತ್ತು ಎಂಟು"
        elif isinstance(value, int) and value % 10 == 0 and 20 <= value <= 90 and i + 1 < len(tokens):
            nxt = _token_value(tokens[i + 1])
            if isinstance(nxt, int) and 1 <= nxt <= 9:
                value += nxt
                i += 1
        # decimal: "<n> point <d>"
        if i + 2 < len(tokens) and tokens[i + 1].lower() in POINT_WORDS:
            frac = _token_value(tokens[i + 2])
            if isinstance(frac, int) and 0 <= frac <= 9:
                out.append(f"{value}.{frac}")
                i += 3
                continue
        out.append(str(value))
        i += 1
    return " ".join(out)


def to_kannada_words(value: int | float) -> str:
    """Kannada words for read-back; decimals read digit-wise after 'ಪಾಯಿಂಟ್'."""
    if isinstance(value, float) and not value.is_integer():
        whole, frac = f"{value}".split(".")
        return f"{to_kannada_words(int(whole))} ಪಾಯಿಂಟ್ " + " ".join(KN_UNITS[int(d)] for d in frac)
    n = int(value)
    if n < 100:
        return KN_WORDS[n]
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        prefix = "ನೂರು" if hundreds == 1 else f"{KN_UNITS[hundreds]} ನೂರು"
        return prefix if rest == 0 else f"{prefix} {KN_WORDS[rest]}"
    return " ".join(KN_UNITS[int(d)] for d in str(n))


def digits_to_kannada(code: str) -> str:
    """Read an ID character by character: '1204' -> 'ಒಂದು ಎರಡು ಸೊನ್ನೆ ನಾಲ್ಕು'."""
    return " ".join(KN_UNITS[int(c)] if c.isdigit() else c for c in code)
