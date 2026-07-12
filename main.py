from fastapi import FastAPI
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator

from config import APP_ENV, OTEL_ENDPOINT, REDIS_HOST, SERVICE_NAME
from routers import db_check, general, members
from telemetry import instrument_app, setup_telemetry

print(f"Starting {SERVICE_NAME}")
print(f"  APP_ENV:       {APP_ENV}")
print(f"  REDIS_HOST:    {REDIS_HOST}")
print(f"  OTEL_ENDPOINT: {OTEL_ENDPOINT}")

# Set up tracing, OTLP export, and log-to-trace correlation before the app
# starts handling requests.
tracer_provider = setup_telemetry()

app = FastAPI(title="DevOps Lab API", version="1.0.0")

# Auto-instrument FastAPI — creates a span for every request
instrument_app(app, tracer_provider)

# Expose /metrics endpoint for Prometheus to scrape.
# Default latency_lowr_buckets is (0.1, 0.5, 1) — too coarse for /slow, which
# can take up to ~3.5s, so most of its requests land in the +Inf bucket.
Instrumentator().instrument(
    app, latency_lowr_buckets=(0.1, 0.5, 1, 2, 3, 4, 5, 10)
).expose(app)

health_check_counter = Counter(
    "health_check_requests_total",
    "Total number of times /health has been called since the last restart",
)


@app.middleware("http")
async def count_health_checks(request, call_next):
    if request.url.path == "/health":
        health_check_counter.inc()
    return await call_next(request)


app.include_router(general.router)
app.include_router(db_check.router)
app.include_router(members.router)
