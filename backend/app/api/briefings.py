from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ApproveIn, RejectIn

router = APIRouter(prefix="/api/briefings")


def _decide(request: Request, briefing_id: int, status: str, approver: str, reason: str | None = None) -> dict:
    repo = request.app.state.reports
    if repo.get_briefing_by_id(briefing_id) is None:
        raise HTTPException(status_code=404, detail="Briefing not found")
    decided = repo.decide_briefing(
        briefing_id, status=status, decided_by=approver, decided_at=datetime.now(UTC), reason=reason
    )
    if not decided:
        raise HTTPException(
            status_code=409, detail="Only a pending briefing on a ready report can be approved or rejected"
        )
    return repo.get_briefing_by_id(briefing_id)


@router.post("/{briefing_id}/approve")
def approve(briefing_id: int, decision: ApproveIn, request: Request) -> dict:
    return _decide(request, briefing_id, "approved", decision.approver_name)


@router.post("/{briefing_id}/reject")
def reject(briefing_id: int, decision: RejectIn, request: Request) -> dict:
    return _decide(request, briefing_id, "rejected", decision.approver_name, decision.reason or None)
