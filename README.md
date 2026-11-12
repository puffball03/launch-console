# Mission Control: Go/No-Go Launch Console

An engineer files an anomaly report: name, station, three readings (wind, temperature, fuel) and a free-text note. The app then:

1. **checks the launch limits in plain code** and sets the verdict (wind ≤ 25 kt, temperature ≥ 4 °C, fuel 98–100 %; any reading outside its limit means NO-GO)
2. **sorts the report with a model** by subsystem and severity, checked against a schema in code
3. **sets a brief-by time** of 5, 15 or 30 minutes for high, medium or low severity (any limit violation counts as high)
4. **runs three model checks at the same time**: hidden instructions in the note, missing details, and panic in the tone
5. **drafts a briefing with a model** and has a second model call review it, for up to three rounds
6. **shows the Flight Director** the reports, the briefing, the verdict, the cost and a trace of every step. Only a person can approve or reject.

## Run

Requires Docker.

```bash
docker compose up --build
```

Then open http://localhost:8000.

With no `.env`, the app runs on a built-in **fake model**: no key, no network calls and no cost, and the console shows a **FAKE MODEL** badge. To use Claude on Microsoft Foundry instead, copy `.env.example` to `.env` and fill in:

| Variable | Value |
|---|---|
| `ANTHROPIC_FOUNDRY_API_KEY` | your Foundry API key |
| `ANTHROPIC_FOUNDRY_RESOURCE` | the resource name: the part before `.services.ai.azure.com` in your endpoint |
| `MODEL_FAST` | your Claude Haiku 5.5 deployment name (default `claude-haiku-5-5`) |
| `MODEL_SMART` | your Claude Sonnet 5.5 deployment name (default `claude-sonnet-5-5`) |

Leave `LLM_PROVIDER` blank: a key selects Foundry automatically, and `LLM_PROVIDER=fake` forces the fake model even when a key is set. Reports are stored in SQLite on the `mission-data` Docker volume, so they survive restarts. `docker compose down -v` deletes them.

## Test

```bash
docker compose run --rm test
```

Runs the back-end (pytest) and front-end (Vitest) suites in a container with **no network**, and without reading `.env`. Every model call goes through one interface (`LLMClient`), and the tests use a fake, so no API key is needed.

## Using the console

- **File a report** with the form at the top. Bad input is rejected with a message next to the field.
- **Reports** are listed with a GO / NO-GO chip and a countdown to the brief-by time. Reports still processing come first, then pending briefings by soonest deadline, then decided ones.
- **Select a report** to see:
  - the verdict and any violations
  - a banner if the note was flagged for review
  - the briefing, with a "Reviewer not satisfied" tag if review never passed it
  - the trace: one card per step, with its tokens, cost and duration, and the report's total cost
- **Approve or reject** by typing your name. The buttons stay disabled until you do, and only a pending briefing on a finished report can be decided.

## Rubric evidence

| Criterion | Where to look |
|---|---|
| One command to start, one to test | This README; `docker-compose.yml`, `Dockerfile`, `scripts/test.sh` |
| Tool choices explained | [`TOOL_CHOICES.md`](TOOL_CHOICES.md) |
| Filing reports | Form: `frontend/src/components/ReportForm.tsx` (tests: `frontend/src/__tests__/ReportForm.test.tsx`)<br>Validation: `backend/app/schemas.py`, `backend/app/api/errors.py`<br>Restart test: `test_reports_are_still_there_after_a_restart` in `backend/tests/test_reports_api.py` |
| Launch limits in plain code | `backend/app/rules/limits.py`<br>Edge tests (exactly on each limit and just past it): `backend/tests/test_limits.py`, including a test that the module imports no model or pipeline code |
| Brief-by time | `backend/app/rules/brief_by.py`; `backend/tests/test_brief_by.py` |
| Sorting with a model | `backend/app/pipeline/sort.py` (schema checked in code, falls back to `unknown` / `high`); `backend/tests/test_sort.py` |
| Three checks and hidden instructions | Checks run with `asyncio.gather`: `backend/app/pipeline/checks.py`<br>Code pre-screen: `backend/app/rules/injection.py`<br>Concurrency test: `test_three_checks_run_at_the_same_time`<br>Hidden-instruction note: `test_hidden_instruction_note_is_flagged_and_cannot_change_the_verdict` (`backend/tests/test_checks.py`) and `test_hidden_instruction_note_end_to_end` (`backend/tests/test_pipeline_api.py`) |
| Draft, review and approval | Loop: `backend/app/pipeline/draft_loop.py` (`test_loop_stops_after_three_rounds_without_a_pass`, `test_pass_in_round_two_uses_round_one_feedback`)<br>Approval API: `backend/app/api/briefings.py`, including `test_only_the_approve_and_reject_endpoints_can_change_a_briefings_status` |
| Trace and cost | Cards: `frontend/src/components/TracePanel.tsx` (tests: `TracePanel.test.tsx`)<br>Cost in code: `backend/app/pricing.py` (`backend/tests/test_pricing.py`)<br>Per-step trace: `backend/app/pipeline/run.py` (`backend/tests/test_run_pipeline.py`) |
| Tests with no network and no key | `LLMClient` in `backend/app/llm/base.py`, fake in `backend/app/llm/fake.py`<br>The network is blocked in tests (`backend/tests/test_network_blocked.py`) and in the test container (`network_mode: none`) |

## Project layout

```
backend/    FastAPI app: rules/ (limits, brief-by, injection pre-screen), pipeline/ (sort, checks,
            draft loop, runner), llm/ (interface, fake, Foundry client), api/, pricing, storage
frontend/   React + Vite + TypeScript console
```

The design, decisions and ticket breakdown are in [`Implementation_plan.md`](Implementation_plan.md).
