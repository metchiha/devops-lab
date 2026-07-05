# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A modular FastAPI app used as a learning project for DevOps fundamentals: containerization, CI/CD, and observability (OpenTelemetry tracing + Prometheus metrics), backed by PostgreSQL and Redis.

## Commands

```bash
# Install dependencies
uv sync

# Run the app locally (reads config from .env via python-dotenv)
uv run uvicorn main:app --reload

# Run tests
APP_ENV=test uv run pytest -v

# Run a single test
APP_ENV=test uv run pytest -v test_main.py::test_register_member_missing_last_name

# Lint / format (as run in CI)
uvx ruff check .
uvx ruff format --check .

# Run via Docker Compose (app + redis + postgres)
docker compose up --build
```

There is no dedicated ruff config file — CI runs `ruff check`/`ruff format --check` with default settings.

## Architecture

Root-level modules (not a package — `uv run uvicorn main:app` and `from main import app` both rely on the project root being on `sys.path`):

- `main.py` — entrypoint. Loads config, runs `setup_telemetry()`, creates the `FastAPI` app, instruments it, and includes the routers. Keep this file thin; put logic in the modules below.
- `config.py` — loads `.env` and reads all environment variables (`APP_ENV`, `REDIS_HOST`, `OTEL_*`, `DATABASE_URL`). This is the single place env vars are read; other modules import from here rather than calling `os.environ` directly.
- `telemetry.py` — OTel `TracerProvider`/OTLP exporter setup and FastAPI auto-instrumentation (`setup_telemetry()`, `instrument_app()`).
- `models.py` — Pydantic request/response models (`MemberRegistration`, `RegistrationResult`).
- `db.py` — sync `psycopg2` connection helper (`get_db_connection()`).
- `registration.py` — the manually-instrumented validation pipeline (`validate_name`, `validate_email`, `check_email_unique`, `validate_referral`, `insert_member`) used by `/members/register`.
- `routers/` — `APIRouter`s grouped by concern: `general.py` (`/`, `/health`, `/version`, `/about`, `/slow`, `/error`), `db_check.py` (`/db-check`), `members.py` (`POST /members/register`). Add new endpoints as a new router module and `include_router` it in `main.py`, rather than growing an existing router file with unrelated routes.

Key behaviors to preserve when touching these modules:

- **Fail-fast env vars**: `config.require_env()` calls `sys.exit(1)` if a required variable (currently `APP_ENV`) is missing at import time. This means importing `main` (including for tests) requires `APP_ENV` to be set in the environment.
- **Two DB access styles coexist intentionally**: `routers/db_check.py` uses `asyncpg` (async) to demonstrate an async DB call in a trace; `registration.py`/`db.py` use `psycopg2` (sync) via `get_db_connection()`. Don't "fix" this inconsistency — it's deliberate, for comparing instrumentation of sync vs async DB calls.
- **Manual OTel instrumentation is the point of `registration.py`**: each function opens its own span via `tracer.start_as_current_span(...)`, set attributes/events, and calls `span.record_exception` + `span.set_status` on failure. When adding new validation/DB steps to this pipeline, follow the same per-step span pattern so the trace waterfall in Tempo stays meaningful. The `time.sleep(random.uniform(...))` calls in these functions are deliberate — they simulate realistic query latency for demo traces, not leftover debug code.
- **Observability wiring** (`telemetry.py`, called from `main.py` at import time): builds an OTel `Resource`/`TracerProvider`, exports spans via OTLP HTTP to `OTEL_EXPORTER_OTLP_ENDPOINT` (`/v1/traces`), instruments `logging` so every log line carries `trace_id`/`span_id` (log-to-trace correlation in Grafana), auto-instruments FastAPI for per-request spans, and exposes Prometheus metrics at `/metrics` via `prometheus-fastapi-instrumentator`.
- **Error handling convention** in routers: validation failures (`ValueError`) become HTTP 422; anything else becomes a generic HTTP 500 with details only logged server-side, not returned to the client (see `routers/members.py`).
- **Tests patch `asyncpg.connect` at its import site**: `test_main.py` mocks `routers.db_check.asyncpg.connect`, not `main.asyncpg.connect` — update the patch target if `db_check`'s async connection logic moves again.
- **`docker-compose.yml`** expects an external network named `observability-lab_default` (from a separate observability stack, e.g. Grafana/Tempo/OTel Collector) — the `app` service attaches to it in addition to its own default network. If that network doesn't exist, `docker compose up` will fail until the observability stack is started first or the network is created.
- **`.env.example` is stale**: it only lists `APP_ENV`/`PORT`, but the app and compose file also require `DB_USER`, `DB_PASSWORD`, `DB_NAME` (compose builds `DATABASE_URL` from these) and read optional `REDIS_HOST`, `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT`. Check `main.py` and `docker-compose.yml` for the full set actually in use, not just `.env.example`.

## CI/CD

- **CI** (`.github/workflows/ci.yml`): on push/PR to `main`, runs a `lint` job (`ruff check`, `ruff format --check`) and a `test` job with live Postgres + Redis service containers, then `uv run pytest -v`.
- **CD** (`.github/workflows/cd.yml`): on push to `main`, re-runs the test suite against Postgres/Redis service containers, then (only on success, and only for the push-to-main event) triggers a Coolify deploy via a signed webhook (`COOLIFY_WEBHOOK_SECRET`/`COOLIFY_WEBHOOK_URL` secrets).
