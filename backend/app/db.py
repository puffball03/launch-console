import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

# Pipeline columns are nullable and filled in as each step finishes.
SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    engineer_name      TEXT    NOT NULL,
    station            TEXT    NOT NULL,
    wind_knots         REAL    NOT NULL,
    temp_c             REAL    NOT NULL,
    fuel_pct           REAL    NOT NULL,
    note               TEXT    NOT NULL,
    status             TEXT    NOT NULL,
    created_at         TEXT    NOT NULL,
    verdict            TEXT,
    violations_json    TEXT,
    subsystem          TEXT,
    severity           TEXT,
    effective_severity TEXT,
    brief_by_minutes   INTEGER,
    brief_by_at        TEXT,
    flagged            INTEGER,
    checks_json        TEXT
);

CREATE TABLE IF NOT EXISTS briefings (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id          INTEGER NOT NULL UNIQUE REFERENCES reports(id),
    content_json       TEXT    NOT NULL,
    rounds             INTEGER NOT NULL,
    reviewer_satisfied INTEGER NOT NULL,
    final_feedback     TEXT,
    status             TEXT    NOT NULL,
    decided_by         TEXT,
    decided_at         TEXT,
    reject_reason      TEXT
);

CREATE TABLE IF NOT EXISTS trace_steps (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id      INTEGER NOT NULL REFERENCES reports(id),
    seq            INTEGER NOT NULL,
    step           TEXT    NOT NULL,
    kind           TEXT    NOT NULL,
    model          TEXT,
    status         TEXT    NOT NULL,
    input_tokens   INTEGER NOT NULL,
    output_tokens  INTEGER NOT NULL,
    cost_usd       TEXT    NOT NULL,
    duration_ms    INTEGER NOT NULL,
    input_preview  TEXT,
    output_preview TEXT,
    error          TEXT,
    UNIQUE (report_id, seq)
);
"""


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def connect(db_path: str) -> Iterator[sqlite3.Connection]:
    """One short-lived connection per operation; commits on success."""
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        with conn:
            yield conn
