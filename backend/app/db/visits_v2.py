"""Confirmed, person-linked V2 visits (Phase 5): the exactly-once save and the receipt lookup.

The save is one short transaction that re-checks authorisation *inside* the transaction:

1. `SELECT ... FOR SHARE` on the worker's login session, the user, the active territory
   assignment and the person (with its household). An admin ending the assignment, a logout or
   a deactivation is an UPDATE of one of those rows, so it serialises with this transaction:
   - if the revocation commits first, the re-checked WHERE no longer matches: the save is refused;
   - if the save holds the locks first, the revocation waits until the visit has committed.
2. The logical visit key (worker_id, client_visit_id) is looked up: the same payload returns the
   existing row (idempotent replay); a different payload under the same key is refused.
3. One INSERT. A concurrent insert of the same key hits UNIQUE and is resolved by re-reading.

No Gnani/Gemini call happens inside the transaction. Nothing but structured fields is stored.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import AuthSession, Household, Person, Territory, TerritoryAssignment, User, V2Visit
from app.safety import danger_signs
from app.schemas.visit import VisitRecord, VisitType

RULE_STATUS = "demo_only_pending_clinical_review"
UNIQUE_KEY = "uq_v2_visits_worker_client_visit"


class VisitSaveRefused(Exception):
    """The save must not happen. `code` is a stable, non-sensitive reason."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class VisitBinding:
    """The immutable subject of one voice session, fixed by the server at session start."""

    worker_id: uuid.UUID
    session_token_hash: str
    household_id: uuid.UUID
    person_id: uuid.UUID
    territory_id: uuid.UUID
    client_visit_id: uuid.UUID
    session_ref: str
    household_public_id: str
    person_public_id: str


@dataclass(frozen=True)
class VisitReceipt:
    visit_id: uuid.UUID
    person_public_id: str
    record_version: int
    confirmed_at: datetime
    idempotent_replay: bool


def ruleset_version() -> str:
    return "rules-" + hashlib.sha256(danger_signs.RULES_PATH.read_bytes()).hexdigest()[:12]


def subject_population(visit_type: VisitType) -> str:
    """Population of the bound person's visit (see services/voice_v2.DANGER_SCOPE): ANC and PNC are
    the mother's, newborn the baby's; immunisation and unknown stay unresolved."""
    return {VisitType.ANC: "maternal", VisitType.PNC: "maternal",
            VisitType.NEWBORN: "newborn"}.get(visit_type, "unresolved")


def payload_sha256(binding: VisitBinding, record: VisitRecord) -> str:
    """Canonical hash of who/whom/what was confirmed (detects a reused key with other content)."""
    canonical = {
        "worker_id": str(binding.worker_id), "household_id": str(binding.household_id),
        "person_id": str(binding.person_id), "client_visit_id": str(binding.client_visit_id),
        "record_version": record.record_version, "visit_type": record.visit_type.value,
        "weight_kg": record.weight_kg, "vaccinations_due": record.vaccinations_due,
        "next_visit_date": record.next_visit_date.isoformat() if record.next_visit_date else None,
        "danger_signs": sorted(record.danger_signs), "requires_phc_referral": record.requires_phc_referral,
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _receipt(row: V2Visit, person_public_id: str, replay: bool) -> VisitReceipt:
    return VisitReceipt(visit_id=row.id, person_public_id=person_public_id, record_version=row.record_version,
                        confirmed_at=row.confirmed_at, idempotent_replay=replay)


def check_binding(db: Session, binding: VisitBinding, *, lock: bool) -> None:
    """Raise VisitSaveRefused unless the session, worker, grant and membership are all still valid.

    With lock=True the rows are read FOR SHARE (call inside the save transaction)."""
    now = datetime.now(UTC)

    def q(stmt, *of):
        return stmt.with_for_update(read=True, of=list(of)) if lock else stmt

    if db.execute(q(select(AuthSession.token_hash).where(
            AuthSession.token_hash == binding.session_token_hash, AuthSession.user_id == binding.worker_id,
            AuthSession.revoked_at.is_(None), AuthSession.expires_at > now), AuthSession)).first() is None:
        raise VisitSaveRefused("AUTH_EXPIRED", "Your login session has ended. Sign in again; this visit was not saved.")
    if db.execute(q(select(User.id).where(User.id == binding.worker_id, User.active.is_(True),
                                          User.role == "worker"), User)).first() is None:
        raise VisitSaveRefused("AUTH_REVOKED", "Your account can no longer record visits; this visit was not saved.")
    if db.execute(q(select(TerritoryAssignment.id)
                    .join(Territory, Territory.id == TerritoryAssignment.territory_id)
                    .where(TerritoryAssignment.user_id == binding.worker_id,
                           TerritoryAssignment.territory_id == binding.territory_id,
                           TerritoryAssignment.ends_at.is_(None), Territory.active.is_(True)),
                    TerritoryAssignment)).first() is None:
        raise VisitSaveRefused("AUTH_REVOKED", "Access to this household changed; this visit was not saved.")
    if db.execute(q(select(Person.id).join(Household, Household.id == Person.household_id)
                    .where(Person.id == binding.person_id, Person.active.is_(True),
                           Person.household_id == binding.household_id,
                           Household.territory_id == binding.territory_id), Person)).first() is None:
        raise VisitSaveRefused("MEMBERSHIP_CHANGED", "This person is no longer in the selected household; not saved.")


def _existing(db: Session, binding: VisitBinding) -> V2Visit | None:
    return db.scalar(select(V2Visit).where(V2Visit.worker_id == binding.worker_id,
                                           V2Visit.client_visit_id == binding.client_visit_id))


def _resolve_existing(row: V2Visit, binding: VisitBinding, digest: str) -> VisitReceipt:
    if row.person_id != binding.person_id or row.payload_sha256 != digest:
        raise VisitSaveRefused("IDEMPOTENCY_KEY_CONFLICT",
                               "This visit key was already used for a different record; nothing was saved.")
    return _receipt(row, binding.person_public_id, replay=True)


def confirm_visit(engine: Engine, binding: VisitBinding, record: VisitRecord,
                  extraction_source: str = "deterministic") -> VisitReceipt:
    """Save exactly one confirmed visit for this logical visit key (see module docstring)."""
    if record.record_version < 1 or record.visit_type is None:
        raise VisitSaveRefused("INVALID_STATE", "Nothing confirmed to save.")
    digest = payload_sha256(binding, record)
    try:
        with Session(engine) as db, db.begin():
            check_binding(db, binding, lock=True)
            existing = _existing(db, binding)
            if existing is not None:
                return _resolve_existing(existing, binding, digest)
            is_demo = bool(db.scalar(select(Person.is_demo_data).where(Person.id == binding.person_id)))
            row = V2Visit(
                person_id=binding.person_id, household_id=binding.household_id, worker_id=binding.worker_id,
                territory_id=binding.territory_id, client_visit_id=binding.client_visit_id,
                session_ref=binding.session_ref, record_version=record.record_version,
                visit_type=record.visit_type.value, subject_population=subject_population(record.visit_type),
                weight_kg=record.weight_kg, vaccinations_due=record.vaccinations_due,
                next_visit_date=record.next_visit_date, danger_signs=list(record.danger_signs),
                requires_phc_referral=record.requires_phc_referral, ruleset_version=ruleset_version(),
                rule_status=RULE_STATUS, extraction_source=extraction_source, payload_sha256=digest,
                language=record.language, confirmed_at=func.now(), is_demo_data=is_demo,
            )
            db.add(row)
            db.flush()
            db.refresh(row)
            return _receipt(row, binding.person_public_id, replay=False)
    except IntegrityError as exc:
        if UNIQUE_KEY not in str(exc.orig):
            raise
    # Another request committed the same key first: return it if it is the same visit.
    with Session(engine) as db:
        existing = _existing(db, binding)
        if existing is None:
            raise VisitSaveRefused("PERSISTENCE_UNKNOWN", "Save status unknown; check the visit history.")
        return _resolve_existing(existing, binding, digest)


def find_receipt(db: Session, worker_id: uuid.UUID, client_visit_id: uuid.UUID) -> V2Visit | None:
    """The caller's own confirmed visit for a logical key (lost-acknowledgement recovery)."""
    return db.scalar(select(V2Visit).where(V2Visit.worker_id == worker_id,
                                           V2Visit.client_visit_id == client_visit_id))
