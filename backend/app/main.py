from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from app.api import briefings, reports
from app.api.errors import validation_error_handler
from app.config import Settings, load_settings
from app.llm.base import LLMClient, LLMResult
from app.llm.fake import FakeLLM
from app.repository import ReportRepository

# The built SPA is served from the same port in Docker; absent during local dev and tests.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class FoundryNotReady:
    """Stands in for the Foundry client until NAT-31: every call fails clearly, so reports end
    briefing_failed with a readable error on the trace instead of crashing."""

    async def complete(self, **kwargs) -> LLMResult:
        raise RuntimeError("The Foundry client is not built yet (NAT-31); run without a key for the fake model.")


def default_llm(settings: Settings) -> LLMClient:
    return FakeLLM.demo() if settings.llm_provider == "fake" else FoundryNotReady()


def create_app(
    settings: Settings | None = None,
    llm: LLMClient | None = None,
    *,
    pipeline_backoff: float = 0.5,
) -> FastAPI:
    """App factory. Run with `uvicorn app.main:create_app --factory`."""
    app = FastAPI(title="Mission Control")
    app.state.settings = settings or load_settings()
    app.state.llm = llm or default_llm(app.state.settings)
    app.state.pipeline_backoff = pipeline_backoff
    app.state.reports = ReportRepository(app.state.settings.db_path)
    # Any report still processing lost its pipeline when the server stopped.
    app.state.reports.fail_stale_processing()

    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.include_router(reports.router)
    app.include_router(briefings.router)

    @app.get("/api/health")
    def health(request: Request) -> dict:
        return {"ok": True, "provider": request.app.state.settings.llm_provider}

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="spa")
    return app
