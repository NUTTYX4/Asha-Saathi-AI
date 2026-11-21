"""Deterministic field extraction from one transcript segment.

Returns only fields actually mentioned; nothing is guessed. Works on Prisma
`codemix` output (Kannada script with English terms in Latin script).
Keyword lists are PENDING native-speaker review (docs/danger-sign-sources.md
covers safety; this module covers form fields).
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from app.schemas.visit import VisitType
from app.services.numbers import normalize_numbers


class Intent(str, Enum):
    CONFIRM = "confirm"
    REJECT = "reject"
    NO_CHANGE = "no_change"
    GREETING = "greeting"
    NONE = "none"


@dataclass
class Extraction:
    beneficiary_id: str | None = None
    visit_type: VisitType | None = None
    weight_kg: float | None = None
    vaccinations_due: list[str] | None = None
    next_visit_date: date | None = None
    is_correction: bool = False
    wants_correction: bool = False
    is_negative_answer: bool = False
    subject_conflict: bool = False
    intent: Intent = Intent.NONE
    normalized_text: str = ""
    fields: list[str] = field(default_factory=list)

    @property
    def has_fields(self) -> bool:
        return bool(self.fields)


# ---------- keyword tables ----------
# Prisma sometimes writes spelled-out abbreviations in Kannada script (observed live:
# "ANC" -> "ಎನ್ ಸಿ"). PNC is checked first so "ಪಿ ಎನ್ ಸಿ" is not read as ANC.
VISIT_KEYWORDS: list[tuple[VisitType, tuple[str, ...]]] = [
    (VisitType.PNC, ("pnc", "postnatal", "post natal", "ಹೆರಿಗೆ ನಂತರ", "delivery ನಂತರ", "ಬಾಣಂತಿ",
                     "ಪಿ ಎನ್ ಸಿ", "ಪಿಎನ್ ಸಿ", "ಪಿಎನ್‌ಸಿ", "ಪಿಎನ್ಸಿ")),
    (VisitType.ANC, ("anc", "antenatal", "pregnant", "pregnancy", "ಗರ್ಭಿಣಿ",
                     "ಎ ಎನ್ ಸಿ", "ಏ ಎನ್ ಸಿ", "ಎಎನ್ ಸಿ", "ಎಎನ್‌ಸಿ", "ಎಎನ್ಸಿ", "ಎನ್ ಸಿ")),
    (VisitType.NEWBORN, ("newborn", "new born", "ನವಜಾತ", "ಹಸುಗೂಸು", "ಶಿಶು")),
    (VisitType.IMMUNISATION, ("immunisation", "immunization", "vaccination visit", "ಲಸಿಕೆ ಭೇಟಿ")),
    (VisitType.ROUTINE, ("routine visit", "general visit", "normal visit", "regular visit",
                         "general checkup", "normal checkup", "routine",
                         "ಸಾಮಾನ್ಯ ಭೇಟಿ", "ನಾರ್ಮಲ್ ಭೇಟಿ", "ನಾರ್ಮಲ್ ವಿಸಿಟ್", "ರೂಟೀನ್")),
]
ROUTINE_SHORT_KEYWORDS: tuple[str, ...] = ("normal", "general", "regular", "ಸಾಮಾನ್ಯ", "ನಾರ್ಮಲ್")

VACCINES: list[tuple[str, str]] = [
    ("TT", r"\btt\b|ಟಿಟಿ|ಟಿ ಟಿ"),
    ("Td", r"\btd\b"),
    ("BCG", r"\bbcg\b|ಬಿಸಿಜಿ"),
    ("OPV", r"\bopv\b|\bpolio\b|ಪೋಲಿಯೋ"),
    ("Pentavalent", r"\bpenta(valent)?\b|ಪೆಂಟಾ"),
    ("Hepatitis B", r"\bhep(atitis)? ?b\b"),
    ("Rotavirus", r"\brota(virus)?\b|ರೋಟಾ"),
    ("IPV", r"\bipv\b"),
    ("PCV", r"\bpcv\b"),
    ("MR", r"\bmr\b|\bmeasles\b|ದಡಾರ"),
    ("DPT", r"\bdpt\b"),
    ("Vitamin A", r"\bvitamin a\b"),
    ("JE", r"\bje\b"),
]

ID_CUE = r"(?:beneficiary\s*id|\bid\b|ಐಡಿ|ಐ\s?ಡಿ|ಫಲಾನುಭವಿ(?:\s*ಸಂಖ್ಯೆ)?|number|ನಂಬರ್|ಸಂಖ್ಯೆ)"
WEIGHT_CUE = r"(?:weight|\bwt\b|ತೂಕ)"
WEIGHT_UNIT = r"(?:kg|kgs|kilo|kilos|kilogram|ಕಿಲೋ|ಕೆಜಿ|ಕೆ\.ಜಿ)"
NEXT_VISIT_CUE = re.compile(
    r"next visit|next checkup|follow ?up|ಮುಂದಿನ|ಭೇಟಿ|ಬರಬೇಕು|ಬರ್ತೀನಿ|ಬರುತ್ತೇನೆ|ನಂತರ|after|later|again", re.I
)

# `\b` is unreliable after Kannada vowel signs, so end-of-word is a lookahead.
CORRECTION_CUE = re.compile(
    r"^\s*(no|not|wrong|sorry|change|ಇಲ್ಲ|ಇಲ್ಲಾ|ಅಲ್ಲ|illa|alla|ತಪ್ಪು|ಬದಲಾಯಿಸಿ)(?=[\s,.!?]|$)", re.I
)
CONFIRM_WORDS = re.compile(
    r"\b(yes|yeah|correct|confirm|save|ok|okay|right)\b|ಹೌದು|ಸರಿ|ಸೇವ್|ಓಕೆ|haudu|sari", re.I
)
NEGATION_WORDS = re.compile(r"\b(no|not|wrong|don'?t)\b|ಇಲ್ಲ|ಅಲ್ಲ|ಬೇಡ|ತಪ್ಪು|illa|alla|beda", re.I)
GREETING_ONLY = re.compile(
    r"^\s*(?:hello|hi|hey|namaste|namaskara|ನಮಸ್ಕಾರ|ಹಲೋ|ಹಾಯ್)[\s,.!?]*$", re.I
)
NO_CHANGE_WORDS = re.compile(
    r"\b(?:no changes?|nothing to change|nothing else|all good)\b"
    r"|^\s*nothing[\s,.!?]*$"
    r"|ಯಾವುದೂ ಬದಲಾವಣೆ ಇಲ್ಲ|ಯಾವುದೇ ಬದಲಾವಣೆ ಇಲ್ಲ|ಬದಲಾವಣೆ ಇಲ್ಲ|ಏನೂ ಬದಲಾವಣೆ ಇಲ್ಲ|ಯಾವುದೂ ಇಲ್ಲ|ಏನೂ ಇಲ್ಲ",
    re.I,
)
NONE_OF_THESE_WORDS = re.compile(
    r"\b(?:none of (?:these|them|those|the above)|neither)\b|ಯಾವುದೂ ಅಲ್ಲ|ಯಾವುದೇ ಅಲ್ಲ|ಅದು ಅಲ್ಲ",
    re.I,
)
EXPLICIT_CORRECTION_WORDS = re.compile(
    r"\b(?:wrong|incorrect|change|correct|edit|fix|mistake)\b|ಸರಿ ಇಲ್ಲ|ತಪ್ಪು|ಬದಲಾಯಿಸ|ತಿದ್ದುಪಡಿ",
    re.I,
)

MONTHS: dict[str, int] = {}
for _num in range(1, 13):
    MONTHS[calendar.month_name[_num].lower()] = _num
    MONTHS[calendar.month_abbr[_num].lower()] = _num
MONTHS.update({
    "ಜನವರಿ": 1, "ಫೆಬ್ರವರಿ": 2, "ಮಾರ್ಚ್": 3, "ಏಪ್ರಿಲ್": 4, "ಮೇ": 5, "ಜೂನ್": 6,
    "ಜುಲೈ": 7, "ಆಗಸ್ಟ್": 8, "ಸೆಪ್ಟೆಂಬರ್": 9, "ಅಕ್ಟೋಬರ್": 10, "ನವೆಂಬರ್": 11, "ಡಿಸೆಂಬರ್": 12,
})
_MONTH_ALT = "|".join(sorted((re.escape(m) for m in MONTHS), key=len, reverse=True))


# ---------- field extractors ----------
def _beneficiary_id(text: str) -> str | None:
    match = re.search(ID_CUE + r"\s*(?:is|ಅಂದರೆ|:)?\s*((?:[a-z]?\s?\d[\s-]*){2,12})", text, re.I)
    if not match:
        return None
    code = re.sub(r"[\s-]", "", match.group(1)).upper()
    return code if sum(c.isdigit() for c in code) >= 2 else None


def find_visit_type(text: str, expecting_visit_type: bool = False) -> VisitType | None:
    """Visit type explicitly named in `text`, if any."""
    lowered = text.lower()
    for visit_type, keywords in VISIT_KEYWORDS:
        for keyword in keywords:
            pattern = rf"\b{re.escape(keyword)}\b" if keyword.isascii() else re.escape(keyword)
            if re.search(pattern, lowered):
                return visit_type
    if expecting_visit_type and not re.search(r"\bweight\b|ತೂಕ", lowered):
        for keyword in ROUTINE_SHORT_KEYWORDS:
            pattern = rf"\b{re.escape(keyword)}\b" if keyword.isascii() else re.escape(keyword)
            if re.search(pattern, lowered):
                return VisitType.ROUTINE
    return None


def _weight(text: str) -> float | None:
    patterns = (
        WEIGHT_CUE + r"\D{0,20}?(\d{1,3}(?:\.\d)?)",
        r"(\d{1,3}(?:\.\d)?)\s*" + WEIGHT_UNIT,
    )
    matches: list[tuple[int, float]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            value = float(match.group(1))
            if 0 < value < 250:
                matches.append((match.start(1), value))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    distinct = {val for _, val in matches}
    if len(distinct) > 1:
        has_correction_cue = bool(
            CORRECTION_CUE.search(text)
            or EXPLICIT_CORRECTION_WORDS.search(text)
            or NEGATION_WORDS.search(text)
        )
        if not has_correction_cue:
            return None
        return matches[-1][1]
    return matches[0][1]


def _vaccinations(text: str) -> list[str] | None:
    lowered = text.lower()
    found = [name for name, pattern in VACCINES if re.search(pattern, lowered)]
    if found:
        return found
    if re.search(r"vaccin|ಲಸಿಕೆ|injection", lowered) and NEGATION_WORDS.search(lowered):
        return []  # explicitly none due
    return None


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year, month = start.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def _next_visit_date(text: str, today: date, expecting_date: bool) -> date | None:
    lowered = text.lower()
    # Absolute: "28 november" / "november 28" / "ನವೆಂಬರ್ 28"
    abs_matches = list(
        re.finditer(rf"(\d{{1,2}})\s*(?:st|nd|rd|th)?\s*({_MONTH_ALT})\b", lowered)
    ) + list(re.finditer(rf"({_MONTH_ALT})\s*(\d{{1,2}})\b", lowered))
    if abs_matches:
        parsed_dates: list[tuple[int, date]] = []
        for match in abs_matches:
            a, b = match.groups()
            day, month = (int(a), MONTHS[b]) if a.isdigit() else (int(b), MONTHS[a])
            resolved: date | None = None
            for year in (today.year, today.year + 1):
                try:
                    candidate = date(year, month, day)
                except ValueError:
                    break
                if candidate >= today:
                    resolved = candidate
                    break
            if resolved is not None:
                parsed_dates.append((match.start(), resolved))
        if not parsed_dates:
            return None
        parsed_dates.sort(key=lambda item: item[0])
        if len({d for _, d in parsed_dates}) > 1:
            has_correction_cue = bool(
                CORRECTION_CUE.search(text)
                or EXPLICIT_CORRECTION_WORDS.search(text)
                or NEGATION_WORDS.search(text)
            )
            if not has_correction_cue:
                return None
            return parsed_dates[-1][1]
        return parsed_dates[0][1]

    # Relative expressions need a follow-up cue, or the agent must have asked for
    # the date: "7 ತಿಂಗಳು ಗರ್ಭಿಣಿ" (7 months pregnant) is not a visit date.
    if not (expecting_date or NEXT_VISIT_CUE.search(lowered)):
        return None
    if re.search(r"day after tomorrow|ನಾಡಿದ್ದು", lowered):
        return today + timedelta(days=2)
    if re.search(r"tomorrow|ನಾಳೆ", lowered):
        return today + timedelta(days=1)
    if re.search(r"next week|ಮುಂದಿನ ವಾರ", lowered):
        return today + timedelta(days=7)
    if re.search(r"next month|ಮುಂದಿನ ತಿಂಗಳು", lowered):
        return _add_months(today, 1)
    match = re.search(r"(\d{1,3})\s*(days?|ದಿನ|weeks?|ವಾರ|months?|ತಿಂಗಳ)", lowered)
    if match:
        n, unit = int(match.group(1)), match.group(2)
        if unit.startswith(("day", "ದಿನ")):
            return today + timedelta(days=n)
        if unit.startswith(("week", "ವಾರ")):
            return today + timedelta(weeks=n)
        return _add_months(today, n)
    return None


def _intent(text: str, has_fields: bool) -> tuple[Intent, bool, bool]:
    words = re.findall(r"\S+", text)
    if has_fields:
        return Intent.NONE, False, False
    if GREETING_ONLY.match(text):
        return Intent.GREETING, False, False
    if NO_CHANGE_WORDS.search(text):
        return Intent.NO_CHANGE, False, False
    if NONE_OF_THESE_WORDS.search(text):
        return Intent.NONE, False, True
    if NEGATION_WORDS.search(text):
        return Intent.REJECT, bool(EXPLICIT_CORRECTION_WORDS.search(text)), True
    if CONFIRM_WORDS.search(text) and len(words) <= 6:
        return Intent.CONFIRM, False, False
    return Intent.NONE, False, False


def extract(
    text: str,
    today: date,
    expecting_date: bool = False,
    expecting_visit_type: bool = False,
) -> Extraction:
    normalized = normalize_numbers(text)
    result = Extraction(normalized_text=normalized)
    result.beneficiary_id = _beneficiary_id(normalized)
    result.visit_type = find_visit_type(normalized, expecting_visit_type=expecting_visit_type)
    result.weight_kg = _weight(normalized)
    result.vaccinations_due = _vaccinations(normalized)
    result.next_visit_date = _next_visit_date(normalized, today, expecting_date)
    result.fields = [
        name for name in ("beneficiary_id", "visit_type", "weight_kg", "vaccinations_due", "next_visit_date")
        if getattr(result, name) is not None
    ]
    result.is_correction = bool(CORRECTION_CUE.search(normalized))
    result.intent, result.wants_correction, result.is_negative_answer = _intent(normalized, result.has_fields)
    return result
