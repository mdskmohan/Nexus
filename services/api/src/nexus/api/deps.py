"""Request authentication and per-request database scope."""

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from nexus.db import row, tenant
from nexus.security import can, read_token

COOKIE = "nexus_session"
# Mutating requests must carry this header. Browsers will not add a custom
# header to a cross-site request without a CORS preflight, which we never
# approve, so this blocks cross-site request forgery.
CLIENT_HEADER = "x-nexus-client"


@dataclass(frozen=True)
class Principal:
    user_id: str
    workspace_id: str
    role: str
    name: str
    email: str


def principal(request: Request) -> Principal:
    claims = read_token(request.cookies.get(COOKIE, ""))
    if not claims:
        raise HTTPException(401, "Please sign in.")
    if request.method not in ("GET", "HEAD", "OPTIONS") and not request.headers.get(CLIENT_HEADER):
        raise HTTPException(403, "Missing client header.")
    with tenant(claims["workspace"]) as s:
        user = row(s, "SELECT id, name, email, role, disabled FROM users WHERE id = :u", u=claims["sub"])
    if user is None or user["disabled"]:
        raise HTTPException(401, "Your account is no longer active.")
    return Principal(str(user["id"]), claims["workspace"], user["role"], user["name"], user["email"])


def db(who: Principal = Depends(principal)) -> Iterator[Session]:
    with tenant(who.workspace_id, who.user_id) as session:
        yield session


def require(permission: str):
    def check(who: Principal = Depends(principal)) -> Principal:
        if not can(who.role, permission):
            raise HTTPException(403, "Your role does not allow this. Ask an administrator.")
        return who

    return check


def found(value, what: str = "Not found"):
    if value is None:
        raise HTTPException(404, what)
    return value

