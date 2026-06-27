import logging
import os
import sys
import asyncpg

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator
from dotenv import load_dotenv

load_dotenv()

def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: Required environment variable '{name}' is not set.")
        sys.exit(1)
    return value

APP_ENV = require_env("APP_ENV")
REDIS_HOST    = os.environ.get("REDIS_HOST", "localhost")
OTEL_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
SERVICE_NAME  = os.environ.get("OTEL_SERVICE_NAME", "devops-lab-api")

print(f"Starting {SERVICE_NAME}")
print(f"  APP_ENV:       {APP_ENV}")
print(f"  REDIS_HOST:    {REDIS_HOST}")
print(f"  OTEL_ENDPOINT: {OTEL_ENDPOINT}")

# ── OpenTelemetry setup ────────────────────────────────────────────────────────
# 1. Define the resource (who is sending this telemetry?)
resource = Resource.create({"service.name": SERVICE_NAME})

# 2. Set up the tracer provider
tracer_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(tracer_provider)

# 3. Add the OTLP exporter — sends traces to the OTel Collector
otlp_exporter = OTLPSpanExporter(
    endpoint=f"{OTEL_ENDPOINT}/v1/traces",
)
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

# 4. Instrument logging — injects trace_id and span_id into every log line
#    This is what enables log-to-trace correlation in Grafana
LoggingInstrumentor().instrument(set_logging_format=True)

# 5. Set up structured logging
logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s %(levelname)s [%(name)s] "
        "[trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] "
        "%(message)s"
    ),
)
logger = logging.getLogger(__name__)

# Retrieve the connection string injected by Docker Compose
DATABASE_URL = os.getenv("DATABASE_URL")

# ── FastAPI app 

app = FastAPI(title="DevOps Lab API", version="1.0.0")

# Instrument FastAPI — auto-creates a span for every request
FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)

# Expose /metrics endpoint for Prometheus to scrape
Instrumentator().instrument(app).expose(app)

# ── Routes
@app.get("/")
def root():
    logger.info("Root endpoint called")
    return {"message": "Welcome to the DevOps Lab", "status": "running"}


@app.get("/health")
def health_check():
    logger.info("Health check requested")
    return {"status": "ok", "version": "1.0.0", "environment": APP_ENV}


@app.get("/version")
def version_specification():
    logger.info("Version specification requested")
    return {"version": "1.0.102", "environment": "development"}


@app.get("/about")
def about():
    logger.info("About endpoint called")
    return {
        "name": "DevOps Lab API",
        "description": "A learning project for DevOps fundamentals",
        "environment": APP_ENV,
    }


@app.get("/db-check")
async def db_check():
    logger.info("Database check requested")
    try:
        # Establish a quick connection to the database
        conn = await asyncpg.connect(DATABASE_URL)

        # Run a simple query to fetch the Postgres server version
        server_version = await conn.fetchval("SHOW server_version;")

        # Always close the connection
        await conn.close()

        return {
            "status": "ok",
            "database": "connected",
            "server_version": f"PostgreSQL {server_version}",
        }

    except Exception as e:
        # Capture the error and return the degraded status response gracefully
        logger.error(f"Database check failed: {str(e)}")
        return {"status": "degraded", "database": "unreachable", "error": str(e)}
    
    
@app.get("/slow")
def slow_endpoint():
    """A deliberately slow endpoint — useful for seeing latency in Grafana."""
    import time
    logger.info("Slow endpoint called — sleeping for 500ms")
    time.sleep(0.5)
    logger.info("Slow endpoint finished")
    return {"status": "done", "note": "This endpoint is intentionally slow"}


@app.get("/error")
def error_endpoint():
    """A deliberately broken endpoint — useful for seeing errors in Grafana."""
    logger.error("Error endpoint called — raising intentional exception")
    raise ValueError("This is an intentional error for observability testing")

