from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from app.api import reports
from app.api.errors import validation_error_handler
from app.config import Settings, load_settings
from app.repository import ReportRepository

# The built SPA is served from the same port in Docker; absent during local dev and tests.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    """App factory. Run with `uvicorn app.main:create_app --factory`."""
    app = FastAPI(title="Mission Control")
    app.state.settings = settings or load_settings()
    app.state.reports = ReportRepository(app.state.settings.db_path)
    # Any report still processing lost its pipeline when the server stopped.
    app.state.reports.fail_stale_processing()

    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.include_router(reports.router)

    @app.get("/api/health")
    def health(request: Request) -> dict:
        return {"ok": True, "provider": request.app.state.settings.llm_provider}

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="spa")
    return app
