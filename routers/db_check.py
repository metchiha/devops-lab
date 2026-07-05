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

        conn = await asyncpg.connect(DATABASE_URL)

        server_version = await conn.fetchval("SHOW server_version;")

        await conn.close()

        return {
            "status": "ok",
            "database": "connected",
            "server_version": f"PostgreSQL {server_version}",
        }

    except Exception as e:
        logger.error(f"Database check failed: {str(e)}")
        return {"status": "degraded", "database": "unreachable", "error": str(e)}
