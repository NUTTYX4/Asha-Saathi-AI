"""Enable PostGIS and create the Round 1 `visits` table on PostgreSQL.

Revision ID: 0001
Revises:
Create Date: 2026-11-21
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "visits",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("beneficiary_id", sa.String(64), nullable=False),
        sa.Column("visit_type", sa.String(32), nullable=False),
        sa.Column("weight_kg", sa.Float()),
        sa.Column("vaccinations_due", postgresql.JSONB(none_as_null=True)),
        sa.Column("next_visit_date", sa.Date()),
        sa.Column("danger_signs", postgresql.JSONB(none_as_null=True), nullable=False),
        sa.Column("requires_phc_referral", sa.Boolean(), nullable=False),
        sa.Column("language", sa.String(16)),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("record_version >= 0", name="ck_visits_record_version_nonneg"),
        sa.CheckConstraint("weight_kg IS NULL OR (weight_kg > 0 AND weight_kg < 250)", name="ck_visits_weight_range"),
    )
    op.create_index("ix_visits_next_visit_date", "visits", ["next_visit_date"])


def downgrade() -> None:
    # Drops the visits table (data loss). The PostGIS extension is left installed.
    op.drop_index("ix_visits_next_visit_date", table_name="visits")
    op.drop_table("visits")
