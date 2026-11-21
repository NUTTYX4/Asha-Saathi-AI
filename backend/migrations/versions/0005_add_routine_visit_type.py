"""Add `routine` to v2_visits.visit_type check constraint. Additive only; preserves existing rows.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-22
"""

from alembic import op

OLD_VISIT_TYPES = ("ANC", "PNC", "newborn", "immunisation", "unknown")
NEW_VISIT_TYPES = ("ANC", "PNC", "newborn", "immunisation", "routine", "unknown")

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.drop_constraint("ck_v2_visits_visit_type", "v2_visits", type_="check")
    op.create_check_constraint("ck_v2_visits_visit_type", "v2_visits", _in("visit_type", NEW_VISIT_TYPES))


def downgrade() -> None:
    op.drop_constraint("ck_v2_visits_visit_type", "v2_visits", type_="check")
    op.create_check_constraint("ck_v2_visits_visit_type", "v2_visits", _in("visit_type", OLD_VISIT_TYPES))
