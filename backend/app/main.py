from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.config import Settings, load_settings

# The built SPA is served from the same port in Docker; absent during local dev and tests.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Mission Control")
    app.state.settings = settings or load_settings()

    @app.get("/api/health")
    def health(request: Request) -> dict:
        return {"ok": True, "provider": request.app.state.settings.llm_provider}

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="spa")
    return app


app = create_app()
