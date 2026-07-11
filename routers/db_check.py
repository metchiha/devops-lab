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


async def _get_table_names(conn) -> list[str]:
    """Return all user-created table names in the public schema."""
    rows = await conn.fetch("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    return [row["table_name"] for row in rows]


async def _get_table_health_fast(conn) -> list[dict]:
    """
    Get row counts for all tables in a single query.
    This is the correct approach.
    """
    tables = await _get_table_names(conn)
    if not tables:
        return []

    # Build one query that counts all tables at once using UNION ALL
    parts = " UNION ALL ".join(
        f"SELECT '{t}' AS table_name, COUNT(*) AS row_count FROM {t}" for t in tables
    )
    rows = await conn.fetch(parts)
    return [{"table": row["table_name"], "rows": row["row_count"]} for row in rows]


async def _get_table_health_slow(conn) -> list[dict]:
    """
    Get row counts by querying each table individually in a loop.

    NOTE TO INSTRUCTOR: This is the N+1 bug. For N tables, this runs
    N+1 queries (1 to list tables, then 1 per table). With realistic
    jitter added, this becomes very visible in traces.
    This function is only called when INGEST_TELEMETRY=true.
    """
    tables = await _get_table_names(conn)
    results = []
    for table in tables:
        # Simulate real-world lock contention / query planner jitter
        time.sleep(random.uniform(0.05, 0.15))
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
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

        # Gather table health data
        # When INGEST_TELEMETRY is enabled, use the extended collection path
        # to gather richer telemetry data per table.
        if INGEST_TELEMETRY and random.random() < 0.3:
            logger.info("Running extended telemetry collection for db-check")
            table_health = await _get_table_health_slow(conn)
        else:
            table_health = await _get_table_health_fast(conn)

        await conn.close()

        logger.info(f"db-check completed, found {len(table_health)} tables")

        return {
            "status": "ok",
            "database": "connected",
            "server_version": server_version,
            "tables": table_health,
        }

    except Exception as e:
        logger.error(f"Database check failed: {str(e)}")
        return {"status": "degraded", "database": "unreachable", "error": str(e)}
