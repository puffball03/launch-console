from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.db import connect, init_db
from app.pipeline.draft_loop import FinalBriefing
from app.schemas import ReportIn

STATUSES = ("processing", "ready", "briefing_failed", "failed")


@dataclass(frozen=True)
class TraceRow:
    step: str
    kind: str  # "model" or "code"
    model: str | None
    status: str  # "ok", "fallback" or "error"
    input_tokens: int
    output_tokens: int
    cost_usd: str
    duration_ms: int
    input_preview: str | None
    output_preview: str | None
    error: str | None


def _report(row) -> dict:
    report = dict(row)
    checks = json.loads(report.pop("checks_json") or "{}")
    report["checks"] = checks.get("checks", [])
    report["prescreen_hits"] = checks.get("prescreen_hits", [])
    report["violations"] = json.loads(report.pop("violations_json") or "[]")
    # None until the checks have run: never screened is not the same as "not flagged".
    report["flagged"] = None if report["flagged"] is None else bool(report["flagged"])
    return report


def _valid_cost(cost: str) -> str:
    try:
        value = Decimal(cost)
    except InvalidOperation as exc:
        raise ValueError(f"Not a cost: {cost!r}") from exc
    if not value.is_finite() or value < 0:
        raise ValueError(f"A step cost must be finite and non-negative, got {cost!r}")
    return cost


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
        return _report(row) if row else None

    def list(self) -> list[dict]:
        with connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM reports ORDER BY created_at DESC, id DESC").fetchall()
        return [_report(row) for row in rows]

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

    def save_facts(
        self,
        report_id: int,
        *,
        verdict: str,
        violations: list[dict],
        subsystem: str,
        severity: str,
        effective_severity: str,
        brief_by_minutes: int,
        brief_by_at: str,
        flagged: bool,
        checks: list[dict],
        prescreen_hits: list[str],
    ) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE reports SET verdict = ?, violations_json = ?, subsystem = ?, severity = ?,
                    effective_severity = ?, brief_by_minutes = ?, brief_by_at = ?, flagged = ?, checks_json = ?
                WHERE id = ?
                """,
                (
                    verdict,
                    json.dumps(violations),
                    subsystem,
                    severity,
                    effective_severity,
                    brief_by_minutes,
                    brief_by_at,
                    int(flagged),
                    json.dumps({"checks": checks, "prescreen_hits": prescreen_hits}),
                    report_id,
                ),
            )

    def add_trace_step(self, report_id: int, row: TraceRow) -> None:
        _valid_cost(row.cost_usd)
        with connect(self.db_path) as conn:
            seq = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM trace_steps WHERE report_id = ?", (report_id,)
            ).fetchone()[0]
            conn.execute(
                """
                INSERT INTO trace_steps (report_id, seq, step, kind, model, status, input_tokens,
                    output_tokens, cost_usd, duration_ms, input_preview, output_preview, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (report_id, seq, *asdict(row).values()),
            )

    def list_trace(self, report_id: int) -> list[dict]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM trace_steps WHERE report_id = ? ORDER BY seq", (report_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def save_briefing(
        self,
        report_id: int,
        briefing: FinalBriefing,
        *,
        rounds: int,
        reviewer_satisfied: bool,
        final_feedback: str | None,
    ) -> None:
        content = asdict(briefing)
        content["brief_by_at"] = briefing.brief_by_at.isoformat()
        content.pop("status")
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO briefings (report_id, content_json, rounds, reviewer_satisfied, final_feedback, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
                """,
                (report_id, json.dumps(content), rounds, int(reviewer_satisfied), final_feedback),
            )

    def get_briefing(self, report_id: int) -> dict | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM briefings WHERE report_id = ?", (report_id,)).fetchone()
        if row is None:
            return None
        briefing = dict(row)
        briefing.update(json.loads(briefing.pop("content_json")))
        briefing["reviewer_satisfied"] = bool(briefing["reviewer_satisfied"])
        return briefing
