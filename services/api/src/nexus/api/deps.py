"""Request authentication and per-request database scope."""

from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from nexus.db import row, tenant
from nexus.security import at_least, read_token

COOKIE = "nexus_session"
# Mutating requests must carry this header. Browsers will not add a custom
# header to a cross-site request without a CORS preflight, which we never
# approve, so this blocks cross-site request forgery.
CLIENT_HEADER = "x-nexus-client"


@dataclass(frozen=True)
class Principal:
    user_id: str
    firm_id: str
    role: str
    name: str
    email: str


def principal(request: Request) -> Principal:
    claims = read_token(request.cookies.get(COOKIE, ""))
    if not claims:
        raise HTTPException(401, "Please sign in.")
    if request.method not in ("GET", "HEAD", "OPTIONS") and not request.headers.get(CLIENT_HEADER):
        raise HTTPException(403, "Missing client header.")
    with tenant(claims["firm"]) as s:
        user = row(s, "SELECT id, name, email, role, disabled FROM users WHERE id = :u", u=claims["sub"])
    if user is None or user["disabled"]:
        raise HTTPException(401, "Your account is no longer active.")
    return Principal(str(user["id"]), claims["firm"], user["role"], user["name"], user["email"])


def db(who: Principal = Depends(principal)) -> Iterator[Session]:
    with tenant(who.firm_id, who.user_id) as session:
        yield session


def require(role: str):
    def check(who: Principal = Depends(principal)) -> Principal:
        if not at_least(who.role, role):
            raise HTTPException(403, f"Only a {role} or above can do this.")
        return who

    return check


def found(value, what: str = "Not found"):
    if value is None:
        raise HTTPException(404, what)
    return value


def attachment(filename: str) -> dict:
    """A Content-Disposition header that is safe for any filename."""
    ascii_name = filename.encode("ascii", "ignore").decode().replace('"', "").replace("\\", "") or "download"
    return {"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"}
