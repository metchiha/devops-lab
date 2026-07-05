import logging
import random
import re
import time

from opentelemetry import trace
from opentelemetry.trace import StatusCode

logger = logging.getLogger(__name__)

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
        pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, email):
            span.set_status(StatusCode.ERROR, "Invalid email format")
            span.record_exception(
                ValueError(f"Email does not match expected format: {email}")
            )
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
            cur.execute("SELECT COUNT(*) FROM members WHERE email = %s", (email,))
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
                "SELECT id FROM members WHERE referral_code = %s", (referral_code,)
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
                (name, email, referring_id),
            )
            member_id = cur.fetchone()[0]
        conn.commit()

        span.set_attribute("member.new_id", member_id)
        span.add_event("insert_completed", {"member_id": member_id})

        return member_id
