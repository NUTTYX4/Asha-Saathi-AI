"""Deterministic danger-sign detection over transcript text.

Rules live in rules.json with a cited source. An LLM is never the authority for
escalation. Matching is conservative: a rule fires on any keyword unless that
occurrence is explicitly negated ("no fever", "ಜ್ವರ ಇಲ್ಲ").

Scoping: a rule applies only to its population (maternal / newborn). The population
comes from the visit type, narrowed by who the worker named ("ಮಗುವಿಗೆ" = the baby,
"ತಾಯಿಗೆ" = the mother). When that is still uncertain, rules for both populations are
checked (a missed sign is worse than an extra referral) and the result is marked
`context_certain=False` so callers do not present a guessed patient category.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.schemas.visit import VisitType

RULES_PATH = Path(__file__).with_name("rules.json")

POPULATIONS_BY_VISIT: dict[VisitType, frozenset[str]] = {
    VisitType.ANC: frozenset({"maternal"}),
    VisitType.PNC: frozenset({"maternal", "newborn"}),  # PNC covers mother and baby
    VisitType.NEWBORN: frozenset({"newborn"}),
    VisitType.IMMUNISATION: frozenset({"newborn"}),
    VisitType.UNKNOWN: frozenset({"maternal", "newborn"}),
}

# Words that name who the note is about. Not clinical rules: they only select which
# population's (cited) rules apply.
SUBJECT_CUES: dict[str, tuple[str, ...]] = {
    "newborn": ("baby", "newborn", "new born", "infant", "ಮಗು", "ಮಗುವ", "ಶಿಶು", "ಹಸುಗೂಸು", "ನವಜಾತ"),
    "maternal": ("mother", "pregnant", "pregnancy", "ತಾಯಿ", "ಗರ್ಭಿಣಿ", "ಬಾಣಂತಿ", "ಅಮ್ಮ"),
}

_EN_NEGATION_BEFORE = re.compile(r"\b(no|without|denies|nil)\s+(\w+\s+){0,1}$")
_KN_NEGATION_AFTER = re.compile(r"^\s*(\S+\s+){0,1}(ಇಲ್ಲ|ಇಲ್ಲಾ|illa|ಆಗಿಲ್ಲ|ಬಂದಿಲ್ಲ)")


@dataclass(frozen=True)
class DangerRule:
    id: str
    population: str
    label: dict[str, str]
    keywords: tuple[str, ...]
    source: str


@dataclass(frozen=True)
class DangerMatch:
    rule_id: str
    population: str
    label: dict[str, str]
    keyword: str
    start: int
    end: int


@dataclass
class Assessment:
    matches: list[DangerMatch] = field(default_factory=list)
    populations: frozenset[str] = frozenset()
    context_certain: bool = True


@lru_cache
def load_rules() -> tuple[tuple[DangerRule, ...], dict]:
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    rules = tuple(
        DangerRule(
            id=r["id"],
            population=r["population"],
            label=r["label"],
            keywords=tuple(k.lower() for k in r["keywords"]),
            source=r["source"],
        )
        for r in data["rules"]
    )
    return rules, data["referral_message"]


def rule_population(rule_id: str) -> str | None:
    rules, _ = load_rules()
    return next((r.population for r in rules if r.id == rule_id), None)


@lru_cache
def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    # Latin keywords need word boundaries ("fits" must not match "benefits").
    # Kannada keywords are stems ("ರಕ್ತ ಹೋಗ" matches ಹೋಗುತ್ತಿದೆ / ಹೋಗ್ತಿದೆ).
    if keyword.isascii():
        return re.compile(rf"\b{re.escape(keyword)}\b")
    return re.compile(re.escape(keyword))


def _is_negated(text: str, start: int, end: int) -> bool:
    return bool(_EN_NEGATION_BEFORE.search(text[:start]) or _KN_NEGATION_AFTER.match(text[end:]))


def named_subjects(text: str, allowed: frozenset[str]) -> set[str]:
    lowered = text.lower()
    return {
        population
        for population, cues in SUBJECT_CUES.items()
        if population in allowed and any(_keyword_pattern(c).search(lowered) for c in cues)
    }


def assess(text: str, visit_type: VisitType) -> Assessment:
    """Match rules for the visit's populations.

    A named subject only chooses between a maternal and a newborn rule triggered by
    the SAME spoken phrase ("ಮಗುವಿಗೆ ತುಂಬಾ ಜ್ವರ" -> newborn fever only). A sign whose
    rule exists for one population is never dropped because the other was named
    ("bleeding and baby fever" keeps the bleeding flag).
    """
    lowered = text.lower()
    base = POPULATIONS_BY_VISIT[visit_type]
    rules, _ = load_rules()
    matches: list[DangerMatch] = []
    for rule in rules:
        if rule.population not in base:
            continue
        for keyword in rule.keywords:
            hit = next(
                (m for m in _keyword_pattern(keyword).finditer(lowered)
                 if not _is_negated(lowered, m.start(), m.end())),
                None,
            )
            if hit:
                matches.append(DangerMatch(rule.id, rule.population, rule.label, keyword, hit.start(), hit.end()))
                break

    if len(base) == 1:
        return Assessment(matches=matches, populations=base, context_certain=True)

    named = named_subjects(text, base)
    kept: list[DangerMatch] = []
    for group in evidence_groups(matches):
        if len({m.population for m in group}) > 1 and len(named) == 1:
            kept.extend(m for m in group if m.population in named)
        else:
            kept.extend(group)
    certain = len(named) == 1 and all(m.population in named for m in kept)
    return Assessment(matches=kept, populations=base, context_certain=certain)


def detect(text: str, visit_type: VisitType) -> list[DangerMatch]:
    """Return rules whose keywords appear un-negated in `text`."""
    return assess(text, visit_type).matches


def evidence_groups(matches: list[DangerMatch]) -> list[list[DangerMatch]]:
    """Group matches whose keyword spans overlap: one spoken phrase ("ತುಂಬಾ ಜ್ವರ")
    can match a maternal and a newborn rule at once."""
    groups: list[list[DangerMatch]] = []
    for match in sorted(matches, key=lambda m: m.start):
        if groups and match.start < max(m.end for m in groups[-1]):
            groups[-1].append(match)
        else:
            groups.append([match])
    return groups


def referral_message(match_labels: list[str], language: str = "kn-IN") -> str:
    _, templates = load_rules()
    template = templates.get(language, templates["kn-IN"])
    return template.format(label=", ".join(match_labels))
