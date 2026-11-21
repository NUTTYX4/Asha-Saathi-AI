"""Visit persistence. Refuses anything that is not an explicitly confirmed record.

Same interface as Round 1; now backed by SQLAlchemy so it runs on PostgreSQL (V2) and SQLite.
"""

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.db.models import Visit
from app.schemas.visit import FollowUpItem, RecordStatus, SavedVisit, VisitRecord, VisitType


class UnconfirmedRecordError(ValueError):
    pass


class VisitRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @property
    def engine(self) -> Engine:
        return self._engine

    def save_confirmed(self, record: VisitRecord) -> int:
        if record.status != RecordStatus.CONFIRMED:
            raise UnconfirmedRecordError("Only explicitly confirmed records can be saved")
        if not record.beneficiary_id or record.visit_type == VisitType.UNKNOWN:
            raise UnconfirmedRecordError("Confirmed record is missing required fields")
        row = Visit(
            beneficiary_id=record.beneficiary_id,
            visit_type=record.visit_type.value,
            weight_kg=record.weight_kg,
            vaccinations_due=record.vaccinations_due,
            next_visit_date=record.next_visit_date,
            danger_signs=list(record.danger_signs),
            requires_phc_referral=record.requires_phc_referral,
            language=record.language,
            record_version=record.record_version,
        )
        with Session(self._engine) as session, session.begin():
            session.add(row)
            session.flush()
            return int(row.id)

    def list_visits(self, limit: int = 100) -> list[SavedVisit]:
        with Session(self._engine) as session:
            rows = session.scalars(select(Visit).order_by(Visit.id.desc()).limit(limit)).all()
            return [self._to_saved(r) for r in rows]

    def list_followups(self) -> list[FollowUpItem]:
        """Referral-flagged visits first, then upcoming visits by date."""
        stmt = (
            select(Visit)
            .where((Visit.next_visit_date.is_not(None)) | (Visit.requires_phc_referral.is_(True)))
            .order_by(
                Visit.requires_phc_referral.desc(),
                Visit.next_visit_date.is_(None),
                Visit.next_visit_date,
            )
        )
        with Session(self._engine) as session:
            return [
                FollowUpItem(
                    visit_id=r.id,
                    beneficiary_id=r.beneficiary_id,
                    visit_type=VisitType(r.visit_type),
                    due_date=r.next_visit_date,
                    vaccinations_due=r.vaccinations_due,
                    requires_phc_referral=bool(r.requires_phc_referral),
                    danger_signs=list(r.danger_signs or []),
                )
                for r in session.scalars(stmt).all()
            ]

    @staticmethod
    def _to_saved(r: Visit) -> SavedVisit:
        return SavedVisit(
            id=r.id,
            beneficiary_id=r.beneficiary_id,
            visit_type=VisitType(r.visit_type),
            weight_kg=r.weight_kg,
            vaccinations_due=r.vaccinations_due,
            next_visit_date=r.next_visit_date,
            danger_signs=list(r.danger_signs or []),
            requires_phc_referral=bool(r.requires_phc_referral),
            language=r.language,
            record_version=r.record_version,
            created_at=r.created_at,
        )
