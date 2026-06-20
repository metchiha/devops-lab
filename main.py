import os
import socket
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()


APP_ENV = os.environ.get("APP_ENV")
if not APP_ENV:
    raise RuntimeError(
        "APP_ENV environment variable is not set. "
        "Set it to 'development', 'staging', or 'production'."
    )

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")

app = FastAPI(title="DevOps Lab API", version="1.0.0")


def check_redis_connection() -> bool:
    """Try to open a TCP connection to Redis. Returns True if reachable."""
    try:
        with socket.create_connection((REDIS_HOST, 6379), timeout=1):
            return True
    except OSError:
        return False


@app.get("/")
def root():
    return {"message": "Welcome to the DevOps Lab", "status": "running"}


@app.get("/health")
def health_check():
    redis_ok = check_redis_connection()
    if not redis_ok:
        print(f"WARNING: Cannot reach Redis at {REDIS_HOST}:6379")
    return {
        "status": "ok",
        "version": "1.0.0",
        "environment": APP_ENV,
        "redis": "connected" if redis_ok else "unreachable",
    }


@app.get("/version")
def version_specification():
    return {"version": "1.0.101", "environment": "development"}


@app.get("/about")
def about():
    return {
        "name": "DevOps Lab API",
        "description": "A learning project for DevOps fundamentals",
        "environment": APP_ENV,
    }
