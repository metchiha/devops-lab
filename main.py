import logging
import os
import sys
import asyncpg
import re
import time
import random
import psycopg2

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from opentelemetry.trace import StatusCode
from dotenv import load_dotenv

load_dotenv()


# ── Member registration models ─────────────────────────────────────────────────

class MemberRegistration(BaseModel):
    name:          str
    email:         str
    referral_code: str | None = None


class RegistrationResult(BaseModel):
    status:    str
    member_id: int | None = None
    message:   str


# ── Member registration models ─────────────────────────────────────────────────

class MemberRegistration(BaseModel):
    name:          str
    email:         str
    referral_code: str | None = None


class RegistrationResult(BaseModel):
    status:    str
    member_id: int | None = None
    message:   str


# ── Validation helpers — each one creates its own span ────────────────────────

# Get a tracer for this module.
# The tracer name shows up in Tempo as the instrumentation scope.
tracer = trace.get_tracer("devops_lab.registration")


def validate_name(name: str) -> None:
    """
    Check that the name is non-empty and contains at least two words.
    Creates a span so we can see this step in the trace.
    """
    with tracer.start_as_current_span("validate_name") as span:
        # Attributes describe the input — useful for filtering traces
        span.set_attribute("validation.step", "name")
        span.set_attribute("validation.input_length", len(name))

        name = name.strip()

        if not name:
            span.set_status(StatusCode.ERROR, "Name is empty")
            span.record_exception(ValueError("Name cannot be empty"))
            raise ValueError("Name cannot be empty")

        parts = name.split()
        if len(parts) < 2:
            span.set_status(StatusCode.ERROR, "Name must contain at least two words")
            span.record_exception(ValueError(f"Invalid name format: '{name}'"))
            raise ValueError("Name must include both a first and last name")

        # Add an event — a discrete moment within the span
        span.add_event("name_validated", {"word_count": len(parts)})
        span.set_attribute("validation.passed", True)


def validate_email(email: str) -> str:
    """
    Check email format and extract the domain.
    Returns the normalised email (lowercased).
    """
    with tracer.start_as_current_span("validate_email") as span:
        span.set_attribute("validation.step", "email")

        email = email.strip().lower()
        span.set_attribute("validation.email_length", len(email))

        # Basic format check
        pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            span.set_status(StatusCode.ERROR, "Invalid email format")
            span.record_exception(ValueError(f"Email does not match expected format: {email}"))
            raise ValueError(f"Invalid email format: {email}")

        domain = email.split("@")[1]
        span.set_attribute("validation.email_domain", domain)

        # Flag disposable email domains — just a warning, not a hard failure
        disposable = {"mailinator.com", "guerrillamail.com", "trashmail.com"}
        if domain in disposable:
            span.add_event("disposable_email_detected", {"domain": domain})
            logger.warning(f"Disposable email domain used: {domain}")

        span.add_event("email_validated", {"domain": domain})
        span.set_attribute("validation.passed", True)

        return email



def check_email_unique(email: str, conn) -> None:
    """
    Check that this email is not already registered.
    This hits the database — the most expensive validation step.
    The artificial sleep simulates realistic query latency.
    """
    with tracer.start_as_current_span("check_email_unique") as span:
        span.set_attribute("validation.step", "email_uniqueness")
        span.set_attribute("db.operation", "SELECT")
        span.set_attribute("db.table", "members")

        # Simulate realistic database query time
        # In production this would be a real query — the span shows you how long it takes
        time.sleep(random.uniform(0.06, 0.12))

        span.add_event("db_query_started")

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM members WHERE email = %s",
                (email,)
            )
            count = cur.fetchone()[0]

        span.set_attribute("db.rows_examined", count)
        span.add_event("db_query_completed", {"rows_found": count})

        if count > 0:
            span.set_status(StatusCode.ERROR, "Email already registered")
            span.record_exception(ValueError(f"Duplicate email: {email}"))
            raise ValueError(f"Email already registered: {email}")

        span.set_attribute("validation.passed", True)


def validate_referral(referral_code: str | None, conn) -> int | None:
    """
    If a referral code was provided, look up the referring member.
    Returns the referring member's ID, or None if no code was given.
    """
    with tracer.start_as_current_span("validate_referral") as span:
        span.set_attribute("validation.step", "referral")
        span.set_attribute("validation.has_referral", referral_code is not None)

        if referral_code is None:
            span.add_event("no_referral_code_provided")
            return None

        span.set_attribute("validation.referral_code_length", len(referral_code))

        # Simulate DB lookup for the referral code
        time.sleep(random.uniform(0.03, 0.06))

        span.add_event("referral_lookup_started")

        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM members WHERE referral_code = %s",
                (referral_code,)
            )
            row = cur.fetchone()

        if row is None:
            span.set_status(StatusCode.ERROR, "Referral code not found")
            span.record_exception(ValueError(f"Unknown referral code: {referral_code}"))
            raise ValueError(f"Referral code not found: {referral_code}")

        referring_id = row[0]
        span.set_attribute("validation.referring_member_id", referring_id)
        span.add_event("referral_validated", {"referring_id": referring_id})
        span.set_attribute("validation.passed", True)

        return referring_id


def insert_member(name: str, email: str, referring_id: int | None, conn) -> int:
    """
    Insert the validated member record and return the new member's ID.
    """
    with tracer.start_as_current_span("insert_member") as span:
        span.set_attribute("db.operation", "INSERT")
        span.set_attribute("db.table", "members")
        span.set_attribute("member.has_referral", referring_id is not None)

        # Simulate insert latency
        time.sleep(random.uniform(0.015, 0.035))

        span.add_event("insert_started")

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO members (name, email, referring_member_id, joined_at)
                VALUES (%s, %s, %s, NOW())
                RETURNING id
                """,
                (name, email, referring_id)
            )
            member_id = cur.fetchone()[0]
        conn.commit()

        span.set_attribute("member.new_id", member_id)
        span.add_event("insert_completed", {"member_id": member_id})

        return member_id
    

def get_db_connection():
    """
    Establishes a synchronous connection to the PostgreSQL database
    using the injected DATABASE_URL environment variable.
    """
    if not DATABASE_URL:
        logger.error("DATABASE_URL environment variable is missing!")
        raise ValueError("DATABASE_URL is not set.")
    
    # Connects to the database using the URL injected from docker-compose
    return psycopg2.connect(DATABASE_URL)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: Required environment variable '{name}' is not set.")
        sys.exit(1)
    return value


APP_ENV = require_env("APP_ENV")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
OTEL_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "devops-lab-api")

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


# ── POST /members/register ─────────────────────────────────────────────────────

@app.post("/members/register", status_code=201)
def register_member(payload: MemberRegistration):
    """
    Register a new member. Runs a multi-step validation pipeline.
    Each step is instrumented with its own span so you can see the
    exact breakdown of time and the point of failure in Tempo.
    """
    logger.info(
        f"Registration attempt: name='{payload.name}' "
        f"email='{payload.email}' "
        f"has_referral={payload.referral_code is not None}"
    )

    try:
        conn = get_db_connection()

        # Run each validation step in order.
        # Each step creates a child span under this request's root span.
        validate_name(payload.name)
        email = validate_email(payload.email)
        check_email_unique(email, conn)
        referring_id = validate_referral(payload.referral_code, conn)
        member_id = insert_member(payload.name, email, referring_id, conn)

        conn.close()

        logger.info(f"Registration successful: member_id={member_id} email={email}")

        return RegistrationResult(
            status="registered",
            member_id=member_id,
            message=f"Welcome, {payload.name.split()[0]}!",
        )

    except ValueError as e:
        logger.warning(f"Registration rejected: {e}")
        # FastAPI will convert this to a 422 response
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        logger.error(f"Registration failed unexpectedly: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Internal error during registration")
