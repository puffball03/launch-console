# syntax=docker/dockerfile:1

# --- Front end: install deps and build the SPA ---
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Back end base: Python deps via uv ---
FROM python:3.12-slim AS backend-base
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./

# --- Runtime: API + built SPA on one port ---
FROM backend-base AS runtime
RUN uv sync --frozen --no-dev
COPY backend/app ./app
COPY --from=frontend /app/frontend/dist ./static
ENV DB_PATH=/data/mission.db
EXPOSE 8000
CMD [".venv/bin/uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

# --- Test: everything installed at build time so the run needs no network ---
FROM backend-base AS test
RUN uv sync --frozen
COPY --from=frontend /usr/local/bin/node /usr/local/bin/node
COPY backend/ ./
COPY --from=frontend /app/frontend /app/frontend
COPY scripts/test.sh /app/scripts/test.sh
CMD ["sh", "/app/scripts/test.sh"]
