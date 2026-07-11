import logging
import os
import random
import time
import asyncpg
from fastapi import APIRouter

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from config import DATABASE_URL

logger = logging.getLogger(__name__)

# Get a tracer for this module.
# The tracer name shows up in Tempo as the instrumentation scope.
tracer = trace.get_tracer(__name__)

router = APIRouter()

INGEST_TELEMETRY = os.environ.get("INGEST_TELEMETRY", "false").lower() == "true"


def _get_table_names(conn) -> list[str]:
    """Return all user-created table names in the public schema."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        return [row[0] for row in cur.fetchall()]


def _get_table_health_fast(conn) -> list[dict]:
    """
    Get row counts for all tables in a single query.
    This is the correct approach.
    """
    tables = _get_table_names(conn)
    if not tables:
        return []

    # Build one query that counts all tables at once using UNION ALL
    parts = " UNION ALL ".join(
        f"SELECT '{t}' AS table_name, COUNT(*) AS row_count FROM {t}" for t in tables
    )
    with conn.cursor() as cur:
        cur.execute(parts)
        return [{"table": row[0], "rows": row[1]} for row in cur.fetchall()]


def _get_table_health_slow(conn) -> list[dict]:
    """
    Get row counts by querying each table individually in a loop.

    NOTE TO INSTRUCTOR: This is the N+1 bug. For N tables, this runs
    N+1 queries (1 to list tables, then 1 per table). With realistic
    jitter added, this becomes very visible in traces.
    This function is only called when INGEST_TELEMETRY=true.
    """
    tables = _get_table_names(conn)
    results = []
    for table in tables:
        # Simulate real-world lock contention / query planner jitter
        time.sleep(random.uniform(0.05, 0.15))
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
        results.append({"table": table, "rows": count})
    return results


@router.get("/db-check")
async def db_check():
    logger.info("db-check endpoint called")
    try:
        conn = await asyncpg.connect(DATABASE_URL)

        with tracer.start_as_current_span("postgres.query") as span:
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("db.statement", "SHOW server_version;")
            try:
                server_version = await conn.fetchval("SHOW server_version;")
            except Exception as e:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
                raise

        await conn.close()

        return {
            "status": "ok",
            "database": "connected",
            "server_version": f"PostgreSQL {server_version}",
        }

    except Exception as e:
        logger.error(f"Database check failed: {str(e)}")
        return {"status": "degraded", "database": "unreachable", "error": str(e)}
