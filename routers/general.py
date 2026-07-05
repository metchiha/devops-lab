import logging
import time

from fastapi import APIRouter

from config import APP_ENV

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
def root():
    logger.info("Root endpoint called")
    return {"message": "Welcome to the DevOps Lab", "status": "running"}


@router.get("/health")
def health_check():
    logger.info("Health check requested")
    return {"status": "ok", "version": "1.0.0", "environment": APP_ENV}


@router.get("/version")
def version_specification():
    logger.info("Version specification requested")
    return {"version": "1.0.102", "environment": "development"}


@router.get("/about")
def about():
    logger.info("About endpoint called")
    return {
        "name": "DevOps Lab API",
        "description": "A learning project for DevOps fundamentals",
        "environment": APP_ENV,
    }


@router.get("/slow")
def slow_endpoint():
    """A deliberately slow endpoint — useful for seeing latency in Grafana."""
    logger.info("Slow endpoint called — sleeping for 500ms")
    time.sleep(0.5)
    logger.info("Slow endpoint finished")
    return {"status": "done", "note": "This endpoint is intentionally slow"}


@router.get("/error")
def error_endpoint():
    """A deliberately broken endpoint — useful for seeing errors in Grafana."""
    logger.error("Error endpoint called — raising intentional exception")
    raise ValueError("This is an intentional error for observability testing")
