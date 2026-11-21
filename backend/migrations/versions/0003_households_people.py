"""Households (PostGIS points), people, family relationships, programme enrolments and
limited household surveys. Renames is_demo -> is_demo_data on users/territories (no data loss).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-21
"""

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography

# Value lists frozen at this revision (later changes need a new migration).
SEXES = ("female", "male", "other", "not_recorded")
RELATIONSHIPS_TO_HEAD = (
    "head", "spouse", "son", "daughter", "father", "mother", "father_in_law", "mother_in_law",
    "son_in_law", "daughter_in_law", "grandson", "granddaughter", "brother", "sister", "other",
)
RESIDENCE_STATUSES = ("resident", "temporarily_away", "moved_out")
RELATIONSHIP_TYPES = ("mother_of", "father_of", "guardian_of", "spouse_of")
PROGRAMMES = ("ANC", "PNC", "NEWBORN", "IMMUNISATION", "NCD_FOLLOWUP")
ENROLMENT_STATUSES = ("active", "completed", "withdrawn")
RECORD_SOURCES = ("demo_seed", "worker_entry")
LOCATION_SOURCES = ("synthetic_demo", "gps", "manual")
WATER_SOURCES = ("piped", "tube_well", "public_tap", "tanker", "other", "not_recorded")

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _in(column: str, values) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.alter_column("users", "is_demo", new_column_name="is_demo_data")
    op.alter_column("territories", "is_demo", new_column_name="is_demo_data")

    op.create_table(
        "households",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("public_id", sa.String(16), nullable=False, unique=True),
        sa.Column("territory_id", sa.Uuid(), sa.ForeignKey("territories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("landmark", sa.String(200)),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("location_source", sa.String(16), nullable=False),
        sa.Column("location_accuracy_m", sa.Float()),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.CheckConstraint(r"public_id ~ '^H-[0-9]{3,}$'", name="ck_households_public_id"),
        sa.CheckConstraint(_in("location_source", LOCATION_SOURCES), name="ck_households_location_source"),
        sa.CheckConstraint("location_accuracy_m IS NULL OR location_accuracy_m >= 0",
                           name="ck_households_location_accuracy"),
    )
    op.create_index("ix_households_territory_id", "households", ["territory_id"])
    op.create_index("ix_households_location", "households", ["location"], postgresql_using="gist")

    op.create_table(
        "people",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("public_id", sa.String(16), nullable=False, unique=True),
        sa.Column("household_id", sa.Uuid(), sa.ForeignKey("households.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("sex", sa.String(16), nullable=False),
        sa.Column("date_of_birth", sa.Date()),
        sa.Column("recorded_age_years", sa.Integer()),
        sa.Column("age_recorded_on", sa.Date()),
        sa.Column("relationship_to_head", sa.String(24), nullable=False),
        sa.Column("residence_status", sa.String(24), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        _ts("created_at"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.CheckConstraint(r"public_id ~ '^P-[0-9]{3,}$'", name="ck_people_public_id"),
        sa.CheckConstraint(_in("sex", SEXES), name="ck_people_sex"),
        sa.CheckConstraint(_in("relationship_to_head", RELATIONSHIPS_TO_HEAD), name="ck_people_relationship_to_head"),
        sa.CheckConstraint(_in("residence_status", RESIDENCE_STATUSES), name="ck_people_residence_status"),
        sa.CheckConstraint("recorded_age_years IS NULL OR (recorded_age_years >= 0 AND recorded_age_years <= 120)",
                           name="ck_people_recorded_age_range"),
        sa.CheckConstraint("(recorded_age_years IS NULL) = (age_recorded_on IS NULL)",
                           name="ck_people_recorded_age_has_date"),
    )
    op.create_index("ix_people_household_id", "people", ["household_id"])

    op.create_table(
        "person_relationships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("related_person_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("relationship_type", sa.String(16), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("verified_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        _ts("created_at"),
        sa.UniqueConstraint("person_id", "related_person_id", "relationship_type", name="uq_person_relationships"),
        sa.CheckConstraint("person_id <> related_person_id", name="ck_person_relationships_not_self"),
        sa.CheckConstraint(_in("relationship_type", RELATIONSHIP_TYPES), name="ck_person_relationships_type"),
        sa.CheckConstraint(_in("source", RECORD_SOURCES), name="ck_person_relationships_source"),
    )
    op.create_index("ix_person_relationships_person_id", "person_relationships", ["person_id"])
    op.create_index("ix_person_relationships_related_person_id", "person_relationships", ["related_person_id"])

    op.create_table(
        "programme_enrolments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("programme", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("ended_on", sa.Date()),
        sa.Column("recorded_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        _ts("created_at"),
        sa.CheckConstraint(_in("programme", PROGRAMMES), name="ck_programme_enrolments_programme"),
        sa.CheckConstraint(_in("status", ENROLMENT_STATUSES), name="ck_programme_enrolments_status"),
        sa.CheckConstraint(_in("source", RECORD_SOURCES), name="ck_programme_enrolments_source"),
        sa.CheckConstraint("ended_on IS NULL OR ended_on >= started_on", name="ck_programme_enrolments_dates"),
    )
    op.create_index("ix_programme_enrolments_person_id", "programme_enrolments", ["person_id"])
    op.create_index("uq_programme_enrolments_active", "programme_enrolments", ["person_id", "programme"],
                    unique=True, postgresql_where=sa.text("status = 'active'"))

    op.create_table(
        "household_surveys",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("household_id", sa.Uuid(), sa.ForeignKey("households.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("survey_version", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("drinking_water_source", sa.String(16), nullable=False),
        sa.Column("has_toilet", sa.Boolean()),
        sa.Column("submitted_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("submitted_on", sa.Date(), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        _ts("created_at"),
        sa.UniqueConstraint("household_id", "survey_version", name="uq_household_surveys_version"),
        sa.CheckConstraint("status IN ('draft', 'confirmed')", name="ck_household_surveys_status"),
        sa.CheckConstraint(_in("drinking_water_source", WATER_SOURCES), name="ck_household_surveys_water"),
    )
    op.create_index("ix_household_surveys_household_id", "household_surveys", ["household_id"])


def downgrade() -> None:
    # Drops V2 household data (data loss). Take a pg_dump backup first (docs/v2/operations.md).
    op.drop_index("ix_household_surveys_household_id", table_name="household_surveys")
    op.drop_table("household_surveys")
    op.drop_index("uq_programme_enrolments_active", table_name="programme_enrolments")
    op.drop_index("ix_programme_enrolments_person_id", table_name="programme_enrolments")
    op.drop_table("programme_enrolments")
    op.drop_index("ix_person_relationships_related_person_id", table_name="person_relationships")
    op.drop_index("ix_person_relationships_person_id", table_name="person_relationships")
    op.drop_table("person_relationships")
    op.drop_index("ix_people_household_id", table_name="people")
    op.drop_table("people")
    op.drop_index("ix_households_location", table_name="households")
    op.drop_index("ix_households_territory_id", table_name="households")
    op.drop_table("households")
    op.alter_column("territories", "is_demo_data", new_column_name="is_demo")
    op.alter_column("users", "is_demo_data", new_column_name="is_demo")
