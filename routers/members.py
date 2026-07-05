import logging

from fastapi import APIRouter, HTTPException

from db import get_db_connection
from models import MemberRegistration, RegistrationResult
from registration import (
    check_email_unique,
    insert_member,
    validate_email,
    validate_name,
    validate_referral,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/members/register", status_code=201)
def register_member(payload: MemberRegistration):
    """
    Register a new member. Runs a multi-step validation pipeline.
    Each step is instrumented with its own span so you can see the
    exact breakdown of time and the point of failure in Tempo.
    """
    logger.info(
        f"Registration attempt: name='{payload.name}' "
        f"email='{payload.email}' "
        f"has_referral={payload.referral_code is not None}"
    )

    try:
        conn = get_db_connection()

        # Run each validation step in order.
        # Each step creates a child span under this request's root span.
        validate_name(payload.name)
        email = validate_email(payload.email)
        check_email_unique(email, conn)
        referring_id = validate_referral(payload.referral_code, conn)
        member_id = insert_member(payload.name, email, referring_id, conn)

        conn.close()

        logger.info(f"Registration successful: member_id={member_id} email={email}")

        return RegistrationResult(
            status="registered",
            member_id=member_id,
            message=f"Welcome, {payload.name.split()[0]}!",
        )

    except ValueError as e:
        logger.warning(f"Registration rejected: {e}")
        # FastAPI will convert this to a 422 response
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        logger.error(f"Registration failed unexpectedly: {e}")
        raise HTTPException(
            status_code=500, detail="Internal error during registration"
        )
