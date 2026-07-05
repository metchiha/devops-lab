import os
import sys

from dotenv import load_dotenv

load_dotenv()


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

# Retrieve the connection string injected by Docker Compose
DATABASE_URL = os.getenv("DATABASE_URL")
