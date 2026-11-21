"""Person-linked confirmed V2 visits (Phase 5). Additive only: the Round 1 `visits` table and
all Phase 1-4 tables are untouched.

One row per explicitly confirmed logical visit: UNIQUE (worker_id, client_visit_id) makes a
repeated or concurrent confirmation return the same row instead of inserting another. Only
confirmed structured fields are stored: never audio, transcripts, model prompts or drafts.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# Value lists frozen at this revision.
VISIT_TYPES = ("ANC", "PNC", "newborn", "immunisation", "unknown")
SUBJECT_POPULATIONS = ("maternal", "newborn", "unresolved")
EXTRACTION_SOURCES = ("deterministic", "deterministic+assist")

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _in(column: str, values) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "v2_visits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("household_id", sa.Uuid(), sa.ForeignKey("households.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("worker_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("territory_id", sa.Uuid(), sa.ForeignKey("territories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("client_visit_id", sa.Uuid(), nullable=False),
        sa.Column("session_ref", sa.String(32), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("visit_type", sa.String(16), nullable=False),
        sa.Column("subject_population", sa.String(16), nullable=False),
        sa.Column("weight_kg", sa.Float()),
        sa.Column("vaccinations_due", JSONB()),
        sa.Column("next_visit_date", sa.Date()),
        sa.Column("danger_signs", JSONB(), nullable=False),
        sa.Column("requires_phc_referral", sa.Boolean(), nullable=False),
        sa.Column("ruleset_version", sa.String(32), nullable=False),
        sa.Column("rule_status", sa.String(48), nullable=False),
        sa.Column("extraction_source", sa.String(32), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("language", sa.String(16)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("worker_id", "client_visit_id", name="uq_v2_visits_worker_client_visit"),
        sa.CheckConstraint("record_version >= 1", name="ck_v2_visits_record_version"),
        sa.CheckConstraint("weight_kg IS NULL OR (weight_kg > 0 AND weight_kg < 250)", name="ck_v2_visits_weight_range"),
        sa.CheckConstraint(_in("visit_type", VISIT_TYPES), name="ck_v2_visits_visit_type"),
        sa.CheckConstraint(_in("subject_population", SUBJECT_POPULATIONS), name="ck_v2_visits_subject_population"),
        sa.CheckConstraint(_in("extraction_source", EXTRACTION_SOURCES), name="ck_v2_visits_extraction_source"),
    )
    # Newest-first history scans this index backwards.
    op.create_index("ix_v2_visits_person_confirmed", "v2_visits", ["person_id", "confirmed_at", "id"])


def downgrade() -> None:
    # Drops confirmed V2 visits (data loss). Only on a disposable database, or after a backup.
    op.drop_index("ix_v2_visits_person_confirmed", table_name="v2_visits")
    op.drop_table("v2_visits")
