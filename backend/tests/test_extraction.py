"""Unit tests for numbers, field extraction and danger-sign rules (synthetic text only)."""

from datetime import date

import pytest

from app.safety.danger_signs import detect
from app.schemas.visit import VisitType
from app.services.extraction import Intent, extract
from app.services.numbers import digits_to_kannada, normalize_numbers, to_kannada_words

TODAY = date(2026, 11, 21)


@pytest.mark.parametrize(
    ("spoken", "expected"),
    [
        ("ತೂಕ ಐವತ್ತೆರಡು ಕಿಲೋ", "ತೂಕ 52 ಕಿಲೋ"),
        ("ಇಪ್ಪತ್ಮೂರು", "23"),
        ("weight two point eight kilo", "weight 2.8 kilo"),
        ("ಎರಡು ಪಾಯಿಂಟ್ ಎಂಟು", "2.8"),
        ("twenty eight november", "28 november"),
        ("ಒಂದು ಎರಡು ಮೂರು ನಾಲ್ಕು", "1 2 3 4"),
        ("ನೂರು ಹತ್ತು", "110"),
    ],
)
def test_normalize_numbers(spoken, expected):
    assert normalize_numbers(spoken) == expected


def test_kannada_words_roundtrip():
    assert to_kannada_words(52) == "ಐವತ್ತೆರಡು"
    assert to_kannada_words(2.8) == "ಎರಡು ಪಾಯಿಂಟ್ ಎಂಟು"
    assert digits_to_kannada("1204") == "ಒಂದು ಎರಡು ಸೊನ್ನೆ ನಾಲ್ಕು"
    for n in range(100):
        assert normalize_numbers(to_kannada_words(n)) == str(n)


def test_full_anc_note_codemix():
    text = (
        "ಫಲಾನುಭವಿ ಐಡಿ ಒಂದು ಎರಡು ಮೂರು ನಾಲ್ಕು. ANC checkup ಮಾಡಿದೆ. "
        "ತೂಕ ಐವತ್ತೆರಡು ಕಿಲೋ. TT injection ಕೊಡಬೇಕು. ಮುಂದಿನ ಭೇಟಿ 28 November."
    )
    r = extract(text, TODAY)
    assert r.beneficiary_id == "1234"
    assert r.visit_type == VisitType.ANC
    assert r.weight_kg == 52
    assert r.vaccinations_due == ["TT"]
    assert r.next_visit_date == date(2026, 11, 28)
    assert r.intent == Intent.NONE


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Exact live Prisma output where "ANC" came back in Kannada script
        ("ಫಲಾನುಭವಿ ID ಒಂದು ಎರಡು ಮೂರು ನಾಲ್ಕು ಎನ್ ಸಿ ಚೆಕ್ ಅಪ್ ಮಾಡಿದೆ ತೂಕ ಐವತ್ತೆರಡು ಕಿಲೋ.", VisitType.ANC),
        ("ಎ ಎನ್ ಸಿ ಚೆಕಪ್", VisitType.ANC),
        ("ಪಿ ಎನ್ ಸಿ ಭೇಟಿ", VisitType.PNC),
        ("ANC ಚೆಕ್ ಅಪ್", VisitType.ANC),
    ],
)
def test_visit_type_kannada_script_abbreviations(text, expected):
    assert extract(text, TODAY).visit_type == expected


def test_correction_only_touches_weight():
    r = extract("no, weight is 2.8 kilo", TODAY)
    assert r.is_correction
    assert r.fields == ["weight_kg"]
    assert r.weight_kg == 2.8


def test_kannada_correction_cue():
    r = extract("ತಪ್ಪು, ತೂಕ ಎರಡು ಪಾಯಿಂಟ್ ಎಂಟು ಕಿಲೋ", TODAY)
    assert r.is_correction and r.weight_kg == 2.8


def test_pregnancy_months_is_not_visit_date():
    r = extract("ಏಳು ತಿಂಗಳು ಗರ್ಭಿಣಿ", TODAY)
    assert r.next_visit_date is None
    assert r.visit_type == VisitType.ANC


def test_relative_date_when_expected():
    assert extract("ಎರಡು ವಾರ", TODAY, expecting_date=True).next_visit_date == date(2026, 12, 5)
    assert extract("next visit after 10 days", TODAY).next_visit_date == date(2026, 12, 1)
    assert extract("ಮುಂದಿನ ತಿಂಗಳು", TODAY).next_visit_date == date(2026, 12, 21)


def test_missing_id_not_guessed():
    r = extract("ANC visit, weight 60 kg", TODAY)
    assert r.beneficiary_id is None


@pytest.mark.parametrize("text", ["ಹೌದು", "ಹೌದು ಸರಿ ಇದೆ", "yes save it", "ok confirm"])
def test_confirm_intent(text):
    assert extract(text, TODAY).intent == Intent.CONFIRM


@pytest.mark.parametrize("text", ["ಇಲ್ಲ", "ಸರಿ ಇಲ್ಲ", "no that is wrong"])
def test_reject_intent(text):
    assert extract(text, TODAY).intent == Intent.REJECT


def test_vaccinations_explicit_none():
    assert extract("ಲಸಿಕೆ ಏನೂ ಇಲ್ಲ", TODAY).vaccinations_due == []


def test_benefits_not_fits():
    assert detect("discussed scheme benefits", VisitType.ANC) == []


@pytest.mark.parametrize(
    ("text", "visit", "rule"),
    [
        ("ಗರ್ಭಿಣಿಗೆ ರಕ್ತಸ್ರಾವ ಆಗ್ತಿದೆ", VisitType.ANC, "MAT_VAGINAL_BLEEDING"),
        ("she has bleeding since morning", VisitType.ANC, "MAT_VAGINAL_BLEEDING"),
        ("ಮಗುವಿಗೆ ತುಂಬಾ ಜ್ವರ ಇದೆ", VisitType.NEWBORN, "NB_FEVER"),
        ("baby has high fever", VisitType.NEWBORN, "NB_FEVER"),
        ("ಮಗು ಹಾಲು ಕುಡಿಯುತ್ತಿಲ್ಲ", VisitType.NEWBORN, "NB_NOT_FEEDING"),
        ("baby is not feeding", VisitType.UNKNOWN, "NB_NOT_FEEDING"),
    ],
)
def test_danger_sign_detected(text, visit, rule):
    assert rule in [m.rule_id for m in detect(text, visit)]


@pytest.mark.parametrize(
    ("text", "visit"),
    [
        ("no fever", VisitType.NEWBORN),
        ("ಜ್ವರ ಇಲ್ಲ", VisitType.NEWBORN),
        ("no bleeding", VisitType.ANC),
        ("ರಕ್ತಸ್ರಾವ ಇಲ್ಲ", VisitType.ANC),
    ],
)
def test_negated_danger_sign_not_flagged(text, visit):
    assert detect(text, visit) == []


def test_unknown_visit_checks_all_populations():
    ids = [m.rule_id for m in detect("bleeding and baby fever", VisitType.UNKNOWN)]
    assert "MAT_VAGINAL_BLEEDING" in ids and "NB_FEVER" in ids
