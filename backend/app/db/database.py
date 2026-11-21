"""SQLite connection and schema. Only confirmed structured fields are stored:
no audio and no transcripts."""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS visits (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    beneficiary_id        TEXT    NOT NULL,
    visit_type            TEXT    NOT NULL,
    weight_kg             REAL,
    vaccinations_due      TEXT,             -- JSON array or NULL (not mentioned)
    next_visit_date       TEXT,             -- ISO date or NULL
    danger_signs          TEXT    NOT NULL, -- JSON array of rule IDs
    requires_phc_referral INTEGER NOT NULL,
    language              TEXT,
    record_version        INTEGER NOT NULL,
    created_at            TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


def connect(db_file: Path) -> sqlite3.Connection:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_file, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
