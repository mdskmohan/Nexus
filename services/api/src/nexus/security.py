"""Passwords and session tokens."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from nexus.config import settings

_hasher = PasswordHasher()

# Roles in order of authority. Admins manage the firm; partners approve work.
ROLES = ("paralegal", "associate", "partner", "admin")
MIN_PASSWORD_LENGTH = 10


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def issue_token(user_id: UUID, firm_id: UUID, role: str) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "firm": str(firm_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=settings().session_hours),
    }
    return jwt.encode(claims, settings().jwt_secret, algorithm="HS256")


def read_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def at_least(role: str, required: str) -> bool:
    return ROLES.index(role) >= ROLES.index(required)
