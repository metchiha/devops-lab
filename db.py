import logging

import psycopg2

from config import DATABASE_URL

logger = logging.getLogger(__name__)


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
