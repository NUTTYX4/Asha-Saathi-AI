"""Strict Pydantic schema and grounding validator for optional Gemini structured extraction.

Model responses are treated as untrusted candidate data. Only supported V2 visit fields,
strict enums, bounded weights and grounded dates are accepted; clinical danger signs,
referrals, diagnoses, free-text advice, identity changes and confirmation state are forbidden.
"""

from __future__ import annotations

import math
import re
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.visit import VisitType
from app.services.extraction import MONTHS, NEXT_VISIT_CUE, Extraction, Intent

AllowedVisitType = Literal["ANC", "PNC", "newborn", "immunisation", "routine"]
AllowedVaccine = Literal[
    "TT",
    "Td",
    "BCG",
    "OPV",
    "Pentavalent",
    "Hepatitis B",
    "Rotavirus",
    "IPV",
    "PCV",
    "MR",
    "DPT",
    "Vitamin A",
    "JE",
]
ClarificationField = Literal["visit_type", "weight_kg", "next_visit_date", "subject", "contradiction"]

MAX_FOLLOWUP_DAYS = 730
_MONTH_RE = re.compile("|".join(sorted((re.escape(m) for m in MONTHS), key=len, reverse=True)), re.I)
_SPECIFIC_RELATIVE_RE = re.compile(
    r"\b(?:today|tomorrow|yesterday|day after|next week|next month)\b|ನಾಳೆ|ನಾಡಿದ್ದು|ಮುಂದಿನ\s*ವಾರ|ಮುಂದಿನ\s*ತಿಂಗಳು",
    re.I,
)
_NUMERIC_DATE_RE = re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b|\b\d{1,2}[/-]\d{1,2}\b")
_RELATIVE_UNIT_RE = re.compile(r"\b\d{1,3}\s*(?:days?|weeks?|months?)\b|\d{1,3}\s*(?:ದಿನ|ವಾರ|ತಿಂಗಳ)", re.I)
_PREGNANCY_MONTH_RE = re.compile(r"ಗರ್ಭಿಣಿ|pregnant", re.I)
_VACCINE_CUE_RE = re.compile(
    r"vaccin|ಲಸಿಕೆ|injection|\btt\b|\btd\b|\bbcg\b|\bopv\b|\bpolio\b|penta|hep|"
    r"rota|\bipv\b|\bpcv\b|\bmr\b|measles|\bdpt\b|vitamin|\bje\b|ಟಿಟಿ|ಬಿಸಿಜಿ|ಪೋಲಿಯೋ|ಪೆಂಟಾ|ದಡಾರ",
    re.I,
)
_UNCLEAR_WEIGHT_RE = re.compile(r"\b(?:not checked|not taken|not measured|around|approx|normal)\b|ಗೊತ್ತಿಲ್ಲ|ಇಲ್ಲ", re.I)
_WEIGHT_GROUNDING_RE = re.compile(
    r"(?:\bweight\b|\bwt\b|ತೂಕ)\D{0,25}\d|\d\s*(?:kg|kgs|kilo|kilos|kilogram|ಕಿಲೋ|ಕೆಜಿ|ಕೆ\.ಜಿ|\bg\b|\bgm\b|grams?|ಗ್ರಾಂ)",
    re.I,
)


class WeightObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float
    unit: Literal["kg", "g"] = "kg"

    @field_validator("value")
    @classmethod
    def _check_positive_bound(cls, v: float) -> float:
        if not math.isfinite(v) or not (0.0 < v < 250000.0):
            raise ValueError("weight value must be in (0, 250000)")
        return v

    def to_kg(self) -> float:
        kg = self.value / 1000.0 if self.unit == "g" else float(self.value)
        if not math.isfinite(kg) or not (0.0 < kg < 250.0):
            raise ValueError("weight_kg out of bounds (0, 250)")
        return round(kg, 3) if self.unit == "g" else kg


class GeminiCandidate(BaseModel):
    """Strict structured output contract for Gemini extraction assist."""

    model_config = ConfigDict(extra="forbid")

    visit_type: AllowedVisitType | None = None
    weight: WeightObservation | None = None
    next_visit_date: date | None = None
    vaccinations_due: list[AllowedVaccine] | None = None
    intent: Literal["none", "confirm", "reject", "no_change", "greeting"] = "none"
    is_correction: bool = False
    wants_correction: bool = False
    is_negative_answer: bool = False
    mentions_other_person: bool = False
    referred_beneficiary_id: str | None = None
    needs_clarification: bool = False
    clarification_field: ClarificationField | None = None
    contradiction_detected: bool = False

    @field_validator("vaccinations_due")
    @classmethod
    def _cap_vaccines(cls, v: list[AllowedVaccine] | None) -> list[AllowedVaccine] | None:
        if v is not None and len(v) > 10:
            raise ValueError("too many vaccinations_due entries")
        return v

    @field_validator("referred_beneficiary_id")
    @classmethod
    def _cap_beneficiary_len(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 32:
            raise ValueError("referred_beneficiary_id too long")
        return v


def _clean_beneficiary_id(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = re.sub(r"[\s-]+", "", raw.strip()).upper()
    if len(cleaned) < 2 or len(cleaned) > 16:
        return None
    if not re.fullmatch(r"[A-Z]?\d{2,14}", cleaned):
        return None
    return cleaned


def _weight_grounded(norm_text: str) -> bool:
    return bool(_WEIGHT_GROUNDING_RE.search(norm_text))


def _date_grounded(norm_text: str, candidate_date: date, today: date, expecting_date: bool) -> bool:
    if candidate_date < today or candidate_date > today + timedelta(days=MAX_FOLLOWUP_DAYS):
        return False
    if _MONTH_RE.search(norm_text) or _NUMERIC_DATE_RE.search(norm_text) or _SPECIFIC_RELATIVE_RE.search(norm_text):
        return True
    if _RELATIVE_UNIT_RE.search(norm_text):
        if _PREGNANCY_MONTH_RE.search(norm_text) and not NEXT_VISIT_CUE.search(norm_text):
            return False
        return expecting_date or bool(NEXT_VISIT_CUE.search(norm_text))
    return False


def _vaccines_grounded(norm_text: str) -> bool:
    return bool(_VACCINE_CUE_RE.search(norm_text))


def candidate_to_extraction(
    raw_json: str,
    *,
    today: date,
    expecting_date: bool,
    baseline: Extraction,
) -> tuple[Extraction, bool]:
    """Validate `raw_json` against `GeminiCandidate`, enforce grounding, and map to `Extraction`."""
    candidate = GeminiCandidate.model_validate_json(raw_json)
    norm = baseline.normalized_text

    # Conflict / wrong-person safeguard: never retain or apply observations from another subject.
    if candidate.mentions_other_person or candidate.clarification_field == "subject":
        ref_id = _clean_beneficiary_id(candidate.referred_beneficiary_id) or baseline.beneficiary_id
        return (
            Extraction(
                beneficiary_id=ref_id,
                subject_conflict=True,
                normalized_text=norm,
            ),
            True,
        )

    # Contradictory utterances must not guess between conflicting measurements or dates.
    if candidate.contradiction_detected or candidate.clarification_field == "contradiction":
        return Extraction(normalized_text=norm, intent=Intent.NONE), True

    beneficiary_id = _clean_beneficiary_id(candidate.referred_beneficiary_id)
    if beneficiary_id is None:
        beneficiary_id = baseline.beneficiary_id

    visit_type = VisitType(candidate.visit_type) if candidate.visit_type is not None else baseline.visit_type

    weight_kg: float | None = None
    if candidate.weight is not None and not (
        candidate.needs_clarification and candidate.clarification_field == "weight_kg"
    ):
        if _weight_grounded(norm):
            weight_kg = candidate.weight.to_kg()
    elif baseline.weight_kg is not None and not (
        candidate.needs_clarification and candidate.clarification_field == "weight_kg"
    ):
        if not _UNCLEAR_WEIGHT_RE.search(norm) or _weight_grounded(norm):
            weight_kg = baseline.weight_kg

    next_visit_date: date | None = None
    if candidate.next_visit_date is not None and not (
        candidate.needs_clarification and candidate.clarification_field == "next_visit_date"
    ):
        if _date_grounded(norm, candidate.next_visit_date, today, expecting_date):
            next_visit_date = candidate.next_visit_date
    elif baseline.next_visit_date is not None and not (
        candidate.needs_clarification and candidate.clarification_field == "next_visit_date"
    ):
        next_visit_date = baseline.next_visit_date

    vaccinations_due: list[str] | None = None
    if candidate.vaccinations_due is not None and _vaccines_grounded(norm):
        vaccinations_due = list(dict.fromkeys(candidate.vaccinations_due))
    elif baseline.vaccinations_due is not None:
        vaccinations_due = list(baseline.vaccinations_due)

    fields = [
        name
        for name, val in (
            ("beneficiary_id", beneficiary_id),
            ("visit_type", visit_type),
            ("weight_kg", weight_kg),
            ("vaccinations_due", vaccinations_due),
            ("next_visit_date", next_visit_date),
        )
        if val is not None
    ]

    if fields:
        intent = Intent.NONE
        wants_correction = False
        is_negative_answer = False
    else:
        intent = Intent(candidate.intent) if candidate.intent != "none" else baseline.intent
        wants_correction = bool(candidate.wants_correction and intent == Intent.REJECT) or (
            baseline.wants_correction and intent == Intent.REJECT
        )
        is_negative_answer = candidate.is_negative_answer or baseline.is_negative_answer

    result = Extraction(
        beneficiary_id=beneficiary_id,
        visit_type=visit_type,
        weight_kg=weight_kg,
        vaccinations_due=vaccinations_due,
        next_visit_date=next_visit_date,
        is_correction=candidate.is_correction or baseline.is_correction,
        wants_correction=wants_correction,
        is_negative_answer=is_negative_answer,
        subject_conflict=False,
        intent=intent,
        normalized_text=norm,
        fields=fields,
    )
    return result, True
