from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.pipeline.run import run_pipeline
from app.pricing import total_cost
from app.schemas import ReportIn

router = APIRouter(prefix="/api/reports")


@router.post("", status_code=201)
def file_report(report: ReportIn, request: Request, background: BackgroundTasks) -> dict:
    state = request.app.state
    report_id = state.reports.create(report, now=datetime.now(UTC))
    status = state.reports.get(report_id)["status"]
    # Runs after the 201 is sent; the console polls GET /api/reports/{id} until it settles.
    background.add_task(
        run_pipeline,
        report_id,
        repo=state.reports,
        llm=state.llm,
        settings=state.settings,
        backoff=state.pipeline_backoff,
    )
    return {"id": report_id, "status": status}


@router.get("")
def list_reports(request: Request) -> list[dict]:
    return request.app.state.reports.list()


@router.get("/{report_id}")
def get_report(report_id: int, request: Request) -> dict:
    repo = request.app.state.reports
    report = repo.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    trace = repo.list_trace(report_id)
    total = total_cost(step["cost_usd"] for step in trace)
    return {
        **report,
        "briefing": repo.get_briefing(report_id),
        "trace": trace,
        "total_cost_usd": format(total.normalize(), "f"),
    }
