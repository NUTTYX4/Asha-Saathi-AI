"""Structured extraction providers (deterministic default, mock Gemini, and fail-safe Gemini).

Gemini is strictly optional and disabled by default (`GEMINI_EXTRACTION_ENABLED=false`).
Model outputs are treated as untrusted candidate data, validated with Pydantic, grounded
against the normalized transcript, and safely fall back to deterministic extraction on
any failure. Prompts, raw responses, transcripts and API keys are never logged or saved.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.gemini_extraction import GeminiCandidate, candidate_to_extraction
from app.schemas.visit import VisitType
from app.services.extraction import (
    EXPLICIT_CORRECTION_WORDS,
    GREETING_ONLY,
    NO_CHANGE_WORDS,
    NONE_OF_THESE_WORDS,
    Extraction,
    Intent,
    extract as deterministic_extract,
)
from app.services.numbers import normalize_numbers

log = logging.getLogger(__name__)

_OTHER_FAMILY_RE = re.compile(
    r"\b(?:husband|wife|sister|brother|neighbor|neighbour|father-in-law|mother-in-law)\b"
    r"|ಗಂಡ|ಹೆಂಡತಿ|ಅಕ್ಕ|ತಂಗಿ|ಅಣ್ಣ|ತಮ್ಮ|ನೆರೆಯ",
    re.I,
)
_UNCLEAR_DATE_RE = re.compile(r"\b(?:soon|later|sometime|maybe|tbd)\b|ನಂತರ ನೋಡೋಣ|ಯಾವಾಗಲಾದರೂ", re.I)
_WEIGHT_WORD_RE = re.compile(r"\bweight\b|\bwt\b|ತೂಕ", re.I)
_WEIGHT_MENTION_RE = re.compile(
    r"(?:\bweight\b|\bwt\b|ತೂಕ)\D{0,16}?(\d{1,3}(?:\.\d)?)"
    r"|(\d{1,3}(?:\.\d)?)\s*(?:kg|kgs|kilo|kilos|kilogram|ಕಿಲೋ|ಕೆಜಿ|ಕೆ\.ಜಿ)",
    re.I,
)

_SYSTEM_INSTRUCTION = (
    "Extract only explicitly stated visit form fields from the health-worker utterance into the "
    "strict JSON schema. Never invent measurements, diagnoses, danger signs, clinical advice, "
    "person IDs, or confirmation actions. Set weight or next_visit_date to null and mark "
    "contradiction_detected=true if conflicting values appear in the same utterance. Set "
    "mentions_other_person=true if the speaker attributes measurements to a different person."
)


@dataclass(frozen=True)
class ExtractionContext:
    text: str
    today: date
    expecting_date: bool = False
    expecting_visit_type: bool = False
    current_visit_type: VisitType = VisitType.UNKNOWN


@dataclass(frozen=True)
class ExtractionOutcome:
    extraction: Extraction
    used_assist: bool
    fallback_reason: str | None = None


class ExtractionProvider(Protocol):
    name: str

    async def extract(self, ctx: ExtractionContext) -> ExtractionOutcome: ...


class DeterministicExtractionProvider:
    name = "deterministic"

    async def extract(self, ctx: ExtractionContext) -> ExtractionOutcome:
        result = deterministic_extract(
            ctx.text,
            ctx.today,
            expecting_date=ctx.expecting_date,
            expecting_visit_type=ctx.expecting_visit_type,
        )
        return ExtractionOutcome(extraction=result, used_assist=False)


def _default_mock_responder(ctx: ExtractionContext) -> str:
    """Offline deterministic-parity simulator returning strict `GeminiCandidate` JSON."""
    norm = normalize_numbers(ctx.text)
    baseline = deterministic_extract(
        ctx.text,
        ctx.today,
        expecting_date=ctx.expecting_date,
        expecting_visit_type=ctx.expecting_visit_type,
    )

    if _OTHER_FAMILY_RE.search(norm):
        return json.dumps({
            "mentions_other_person": True,
            "referred_beneficiary_id": baseline.beneficiary_id,
            "needs_clarification": True,
            "clarification_field": "subject",
        })

    weight_vals = {float(a or b) for a, b in _WEIGHT_MENTION_RE.findall(norm) if (a or b)}
    has_correction = bool(
        re.search(r"\b(?:no|not|wrong|change|correct)\b|ಇಲ್ಲ|ಅಲ್ಲ|ತಪ್ಪು|ಬದಲಾಯಿಸ", norm, re.I)
    )
    if len(weight_vals) > 1 and not has_correction:
        return json.dumps({
            "contradiction_detected": True,
            "needs_clarification": True,
            "clarification_field": "contradiction",
        })

    if baseline.next_visit_date is None and _UNCLEAR_DATE_RE.search(norm) and not baseline.fields:
        return json.dumps({
            "needs_clarification": True,
            "clarification_field": "next_visit_date",
        })

    if baseline.weight_kg is None and _WEIGHT_WORD_RE.search(norm) and not re.search(r"\d", norm):
        return json.dumps({
            "needs_clarification": True,
            "clarification_field": "weight_kg",
        })

    payload: dict[str, object] = {
        "intent": baseline.intent.value,
        "is_correction": baseline.is_correction,
        "wants_correction": baseline.wants_correction,
        "is_negative_answer": baseline.is_negative_answer,
        "referred_beneficiary_id": baseline.beneficiary_id,
    }
    if baseline.visit_type is not None and baseline.visit_type != VisitType.UNKNOWN:
        payload["visit_type"] = baseline.visit_type.value
    if baseline.weight_kg is not None:
        payload["weight"] = {"value": baseline.weight_kg, "unit": "kg"}
    if baseline.next_visit_date is not None:
        payload["next_visit_date"] = baseline.next_visit_date.isoformat()
    if baseline.vaccinations_due is not None:
        payload["vaccinations_due"] = list(baseline.vaccinations_due)
    if not baseline.fields and GREETING_ONLY.match(norm):
        payload["intent"] = Intent.GREETING.value
    elif not baseline.fields and NO_CHANGE_WORDS.search(norm):
        payload["intent"] = Intent.NO_CHANGE.value
    elif not baseline.fields and NONE_OF_THESE_WORDS.search(norm):
        payload["is_negative_answer"] = True
        payload["intent"] = Intent.NONE.value
    elif not baseline.fields and baseline.intent == Intent.REJECT and EXPLICIT_CORRECTION_WORDS.search(norm):
        payload["wants_correction"] = True
    return json.dumps(payload)


class _AssistedProviderBase:
    """Shared validation, grounding, cancellation and fail-safe fallback wrapper."""

    def __init__(self, *, timeout_s: float, max_input_chars: int) -> None:
        self._timeout_s = timeout_s
        self._max_input_chars = max_input_chars
        self._fallback = DeterministicExtractionProvider()

    async def _raw_extract(self, ctx: ExtractionContext, bounded_text: str) -> str:
        raise NotImplementedError

    async def extract(self, ctx: ExtractionContext) -> ExtractionOutcome:
        bounded_text = ctx.text[: self._max_input_chars]
        baseline = deterministic_extract(
            bounded_text,
            ctx.today,
            expecting_date=ctx.expecting_date,
            expecting_visit_type=ctx.expecting_visit_type,
        )
        try:
            raw_json = await asyncio.wait_for(self._raw_extract(ctx, bounded_text), timeout=self._timeout_s)
            if not raw_json or not raw_json.strip():
                raise ValueError("empty structured response")
            merged, used_assist = candidate_to_extraction(
                raw_json,
                today=ctx.today,
                expecting_date=ctx.expecting_date,
                baseline=baseline,
            )
            return ExtractionOutcome(extraction=merged, used_assist=used_assist)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            log.warning("Extraction provider %s timed out after %.1fs; using deterministic fallback", self.name, self._timeout_s)
            return ExtractionOutcome(extraction=baseline, used_assist=False, fallback_reason="timeout")
        except (ValidationError, ValueError) as exc:
            log.warning("Extraction provider %s rejected output (%s); using deterministic fallback", self.name, type(exc).__name__)
            return ExtractionOutcome(extraction=baseline, used_assist=False, fallback_reason="invalid_output")
        except Exception as exc:
            log.warning("Extraction provider %s failed (%s); using deterministic fallback", self.name, type(exc).__name__)
            return ExtractionOutcome(extraction=baseline, used_assist=False, fallback_reason="provider_error")


class MockGeminiExtractionProvider(_AssistedProviderBase):
    name = "gemini_mock"

    def __init__(
        self,
        responder: Callable[[ExtractionContext], Awaitable[str] | str] | None = None,
        *,
        timeout_s: float = 6.0,
        max_input_chars: int = 1000,
    ) -> None:
        super().__init__(timeout_s=timeout_s, max_input_chars=max_input_chars)
        self._responder = responder or _default_mock_responder

    async def _raw_extract(self, ctx: ExtractionContext, bounded_text: str) -> str:
        bounded_ctx = ExtractionContext(
            text=bounded_text,
            today=ctx.today,
            expecting_date=ctx.expecting_date,
            expecting_visit_type=ctx.expecting_visit_type,
            current_visit_type=ctx.current_visit_type,
        )
        result = self._responder(bounded_ctx)
        if asyncio.iscoroutine(result) or isinstance(result, Awaitable):
            return await result  # type: ignore[misc]
        return result


class GeminiExtractionProvider(_AssistedProviderBase):
    name = "gemini"

    def __init__(self, settings: Settings, *, client_factory: Callable | None = None) -> None:
        super().__init__(timeout_s=settings.gemini_timeout_s, max_input_chars=settings.gemini_max_input_chars)
        self._api_key = settings.require_gemini_key()
        self._model = settings.gemini_model
        self._max_output_tokens = settings.gemini_max_output_tokens
        self._client_factory = client_factory
        self._client = None

    def __repr__(self) -> str:
        return f"GeminiExtractionProvider(model={self._model!r}, timeout_s={self._timeout_s})"

    def _get_client(self):
        if self._client is None:
            from google import genai
            from google.genai import types

            http_opts = types.HttpOptions(
                timeout=max(100, int(self._timeout_s * 1000)),
                retry_options=types.HttpRetryOptions(attempts=1),
            )
            if self._client_factory is not None:
                self._client = self._client_factory(api_key=self._api_key, http_options=http_opts)
            else:
                self._client = genai.Client(api_key=self._api_key, http_options=http_opts)
        return self._client

    def build_config(self):
        from google.genai import types

        return types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            temperature=0.0,
            max_output_tokens=self._max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            response_mime_type="application/json",
            response_schema=GeminiCandidate,
        )

    @staticmethod
    def build_prompt(ctx: ExtractionContext, bounded_text: str) -> str:
        return (
            f"reference_date={ctx.today.isoformat()}\n"
            f"current_visit_type={ctx.current_visit_type.value}\n"
            f"expecting_date={ctx.expecting_date}\n"
            f"expecting_visit_type={ctx.expecting_visit_type}\n"
            f"utterance={bounded_text}"
        )

    async def _raw_extract(self, ctx: ExtractionContext, bounded_text: str) -> str:
        client = self._get_client()
        response = await client.aio.models.generate_content(
            model=self._model,
            contents=self.build_prompt(ctx, bounded_text),
            config=self.build_config(),
        )
        return getattr(response, "text", None) or ""


def build_extraction_provider(settings: Settings) -> ExtractionProvider:
    """Return the configured extraction provider; deterministic whenever disabled or unconfigured."""
    if not settings.gemini_extraction_enabled:
        return DeterministicExtractionProvider()
    if settings.extraction_provider_mode == "deterministic":
        return DeterministicExtractionProvider()
    if settings.extraction_provider_mode == "gemini_mock":
        return MockGeminiExtractionProvider(
            timeout_s=settings.gemini_timeout_s,
            max_input_chars=settings.gemini_max_input_chars,
        )
    if not settings.gemini_configured:
        log.warning("GEMINI_EXTRACTION_ENABLED is true without GEMINI_API_KEY; falling back to deterministic.")
        return DeterministicExtractionProvider()
    return GeminiExtractionProvider(settings)
