from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Mission Control")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


# The built SPA is served from the same port in Docker; absent during local dev and tests.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="spa")
