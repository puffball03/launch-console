from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ReportIn

router = APIRouter(prefix="/api/reports")


@router.post("", status_code=201)
def file_report(report: ReportIn, request: Request) -> dict:
    repo = request.app.state.reports
    report_id = repo.create(report, now=datetime.now(UTC))
    return {"id": report_id, "status": repo.get(report_id)["status"]}


@router.get("")
def list_reports(request: Request) -> list[dict]:
    return request.app.state.reports.list()


@router.get("/{report_id}")
def get_report(report_id: int, request: Request) -> dict:
    report = request.app.state.reports.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
