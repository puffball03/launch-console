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
