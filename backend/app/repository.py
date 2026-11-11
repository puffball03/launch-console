from datetime import datetime

from app.db import connect, init_db
from app.schemas import ReportIn

STATUSES = ("processing", "ready", "briefing_failed", "failed")


class ReportRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        init_db(db_path)

    def create(self, report: ReportIn, *, now: datetime) -> int:
        with connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO reports
                    (engineer_name, station, wind_knots, temp_c, fuel_pct, note, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'processing', ?)
                """,
                (
                    report.engineer_name,
                    report.station,
                    report.wind_knots,
                    report.temp_c,
                    report.fuel_pct,
                    report.note,
                    now.isoformat(),
                ),
            )
            return cursor.lastrowid

    def get(self, report_id: int) -> dict | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        return dict(row) if row else None

    def list(self) -> list[dict]:
        with connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM reports ORDER BY created_at DESC, id DESC").fetchall()
        return [dict(row) for row in rows]

    def set_status(self, report_id: int, status: str) -> None:
        if status not in STATUSES:
            raise ValueError(f"Unknown report status {status!r}")
        with connect(self.db_path) as conn:
            conn.execute("UPDATE reports SET status = ? WHERE id = ?", (status, report_id))

    def fail_stale_processing(self) -> int:
        """On startup, a report still processing lost its pipeline in a restart."""
        with connect(self.db_path) as conn:
            return conn.execute(
                "UPDATE reports SET status = 'failed' WHERE status = 'processing'"
            ).rowcount
