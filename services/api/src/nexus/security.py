"""Passwords and session tokens."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from nexus.config import settings

_hasher = PasswordHasher()

# Roles are sets of permissions, not a ladder: the people who approve are not
# always the people who build.
ROLES = ("admin", "steward", "developer", "analyst", "viewer")
PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({"manage_workspace", "manage_people", "manage_ai", "manage_connections",
                        "approve_graph", "approve_runs", "build_agents", "run_agents", "use_apps",
                        "view_audit"}),
    "steward": frozenset({"approve_graph", "approve_runs", "run_agents", "use_apps", "view_audit"}),
    "developer": frozenset({"build_agents", "approve_runs", "run_agents", "use_apps"}),
    "analyst": frozenset({"run_agents", "use_apps"}),
    "viewer": frozenset({"use_apps"}),
}
MIN_PASSWORD_LENGTH = 10


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def issue_token(user_id: UUID, workspace_id: UUID, role: str) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "workspace": str(workspace_id),
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


def can(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, frozenset())
