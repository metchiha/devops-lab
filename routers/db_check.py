import logging

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


@router.get("/db-check")
async def db_check():
    logger.info("Database check requested")
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
