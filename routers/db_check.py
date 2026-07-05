import logging

import asyncpg
from fastapi import APIRouter

from config import DATABASE_URL

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/db-check")
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
