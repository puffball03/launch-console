# Mission Control: Go/No-Go Launch Console

Engineers file anomaly reports; a pipeline checks launch limits in code, sorts and screens the report with a model, and drafts a briefing that only the Flight Director can approve.

## Run

Requires Docker.

```bash
docker compose up --build
```

Open http://localhost:8000. Without an API key in `.env`, the app runs on the fake model.

## Test

```bash
docker compose run --rm test
```

Runs the back-end (pytest) and front-end (Vitest) suites with no network and no API key.

See `Implementation_plan.md` for the design.
