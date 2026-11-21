"""Visit persistence. Refuses anything that is not an explicitly confirmed record."""

import json
import sqlite3
import threading
from datetime import date, datetime

from app.schemas.visit import FollowUpItem, RecordStatus, SavedVisit, VisitRecord, VisitType


class UnconfirmedRecordError(ValueError):
    pass


class VisitRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.Lock()

    def save_confirmed(self, record: VisitRecord) -> int:
        if record.status != RecordStatus.CONFIRMED:
            raise UnconfirmedRecordError("Only explicitly confirmed records can be saved")
        if not record.beneficiary_id or record.visit_type == VisitType.UNKNOWN:
            raise UnconfirmedRecordError("Confirmed record is missing required fields")
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """INSERT INTO visits (beneficiary_id, visit_type, weight_kg, vaccinations_due,
                   next_visit_date, danger_signs, requires_phc_referral, language, record_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.beneficiary_id,
                    record.visit_type.value,
                    record.weight_kg,
                    None if record.vaccinations_due is None else json.dumps(record.vaccinations_due),
                    record.next_visit_date.isoformat() if record.next_visit_date else None,
                    json.dumps(record.danger_signs),
                    int(record.requires_phc_referral),
                    record.language,
                    record.record_version,
                ),
            )
            return int(cursor.lastrowid)

    def list_visits(self, limit: int = 100) -> list[SavedVisit]:
        rows = self._conn.execute(
            "SELECT * FROM visits ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._to_saved(r) for r in rows]

    def list_followups(self) -> list[FollowUpItem]:
        """Upcoming visits first; referral-flagged visits are always included."""
        rows = self._conn.execute(
            """SELECT * FROM visits
               WHERE next_visit_date IS NOT NULL OR requires_phc_referral = 1
               ORDER BY requires_phc_referral DESC, next_visit_date IS NULL, next_visit_date"""
        ).fetchall()
        return [
            FollowUpItem(
                visit_id=r["id"],
                beneficiary_id=r["beneficiary_id"],
                visit_type=VisitType(r["visit_type"]),
                due_date=date.fromisoformat(r["next_visit_date"]) if r["next_visit_date"] else None,
                vaccinations_due=json.loads(r["vaccinations_due"]) if r["vaccinations_due"] else None,
                requires_phc_referral=bool(r["requires_phc_referral"]),
                danger_signs=json.loads(r["danger_signs"]),
            )
            for r in rows
        ]

    @staticmethod
    def _to_saved(r: sqlite3.Row) -> SavedVisit:
        return SavedVisit(
            id=r["id"],
            beneficiary_id=r["beneficiary_id"],
            visit_type=VisitType(r["visit_type"]),
            weight_kg=r["weight_kg"],
            vaccinations_due=json.loads(r["vaccinations_due"]) if r["vaccinations_due"] else None,
            next_visit_date=date.fromisoformat(r["next_visit_date"]) if r["next_visit_date"] else None,
            danger_signs=json.loads(r["danger_signs"]),
            requires_phc_referral=bool(r["requires_phc_referral"]),
            language=r["language"],
            record_version=r["record_version"],
            created_at=datetime.fromisoformat(r["created_at"]),
        )
