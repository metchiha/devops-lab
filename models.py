from pydantic import BaseModel


class MemberRegistration(BaseModel):
    name: str
    email: str
    referral_code: str | None = None


class RegistrationResult(BaseModel):
    status: str
    member_id: int | None = None
    message: str
