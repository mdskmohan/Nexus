"""Sign-up, sign-in, and the firm's team."""

import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nexus import audit
from nexus.ai import registry
from nexus.api.deps import COOKIE, Principal, db, principal, require
from nexus.config import settings
from nexus.db import row, rows, scalar, tenant, unscoped
from nexus.playbooks import STARTERS
from nexus.security import MIN_PASSWORD_LENGTH, ROLES, hash_password, issue_token, verify_password

router = APIRouter(prefix="/api", tags=["auth"])


class SignUp(BaseModel):
    firm_name: str = Field(min_length=2, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=200)


class SignIn(BaseModel):
    # Not EmailStr: sign-in only needs to match an existing account, and a
    # format error here would tell people less than "email and password do not match".
    email: str = Field(max_length=320)
    password: str = Field(max_length=200)


class NewMember(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    role: str
    temporary_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=200)


class MemberUpdate(BaseModel):
    role: str | None = None
    disabled: bool | None = None


def _set_session(response: Response, user_id, firm_id, role: str) -> None:
    response.set_cookie(
        COOKIE, issue_token(user_id, firm_id, role), httponly=True, samesite="lax",
        secure=settings().cookie_secure, max_age=settings().session_hours * 3600, path="/",
    )


def seed_playbooks(session: Session, firm_id: str) -> None:
    """Give the firm any starter playbook it does not have yet (by slug). Idempotent."""
    for p in STARTERS:
        scalar(
            session,
            """INSERT INTO playbooks (firm_id, slug, name, description, document_type, positions, is_starter)
               VALUES (:f, :slug, :name, :desc, :dt, CAST(:pos AS jsonb), true)
               ON CONFLICT (firm_id, slug) DO NOTHING RETURNING id""",
            f=firm_id, slug=p["slug"], name=p["name"], desc=p["description"],
            dt=p["document_type"], pos=json.dumps(p["positions"]),
        )


@router.post("/auth/signup", status_code=201)
def signup(body: SignUp, response: Response) -> dict:
    firm_id = str(uuid4())
    try:
        with tenant(firm_id) as s:
            scalar(s, "INSERT INTO firms (id, name) VALUES (:id, :name) RETURNING id",
                   id=firm_id, name=body.firm_name.strip())
            user_id = scalar(
                s,
                """INSERT INTO users (firm_id, email, name, password_hash, role)
                   VALUES (:f, :e, :n, :h, 'admin') RETURNING id""",
                f=firm_id, e=body.email.lower(), n=body.name.strip(), h=hash_password(body.password),
            )
            seed_playbooks(s, firm_id)
            audit.record(s, firm_id, user_id, "firm.created", "firm", firm_id)
    except IntegrityError:
        raise HTTPException(409, "An account with this email already exists.") from None
    _set_session(response, user_id, firm_id, "admin")
    return {"ok": True}


@router.post("/auth/login")
def login(body: SignIn, response: Response) -> dict:
    with unscoped() as s:
        user = row(s, "SELECT * FROM auth_lookup(:e)", e=body.email)
    # Same message either way, so the form does not reveal which emails exist.
    if user is None or user["disabled"] or not verify_password(user["password_hash"], body.password):
        raise HTTPException(401, "That email and password do not match.")
    with tenant(user["firm_id"]) as s:
        audit.record(s, user["firm_id"], user["id"], "user.signed_in", "user", user["id"])
    _set_session(response, user["id"], user["firm_id"], user["role"])
    return {"ok": True}


@router.post("/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(who: Principal = Depends(principal), s: Session = Depends(db)) -> dict:
    firm = row(s, "SELECT id, name, preferences FROM firms WHERE id = :f", f=who.firm_id)
    return {"user": {"id": who.user_id, "name": who.name, "email": who.email, "role": who.role},
            "firm": firm, "model_configured": bool(registry.available(who.firm_id))}


@router.get("/team")
def team(s: Session = Depends(db)) -> list[dict]:
    return rows(s, "SELECT id, name, email, role, disabled, created_at FROM users ORDER BY created_at")


@router.post("/team", status_code=201)
def add_member(body: NewMember, who: Principal = Depends(require("admin")),
               s: Session = Depends(db)) -> dict:
    if body.role not in ROLES:
        raise HTTPException(422, f"Role must be one of {', '.join(ROLES)}.")
    try:
        with s.begin_nested():
            user_id = scalar(
                s,
                """INSERT INTO users (firm_id, email, name, password_hash, role)
                   VALUES (:f, :e, :n, :h, :r) RETURNING id""",
                f=who.firm_id, e=body.email.lower(), n=body.name.strip(),
                h=hash_password(body.temporary_password), r=body.role,
            )
    except IntegrityError:
        raise HTTPException(409, "An account with this email already exists.") from None
    audit.record(s, who.firm_id, who.user_id, "user.added", "user", user_id, role=body.role)
    return {"id": str(user_id)}


@router.patch("/team/{user_id}")
def update_member(user_id: str, body: MemberUpdate, who: Principal = Depends(require("admin")),
                  s: Session = Depends(db)) -> dict:
    if user_id == who.user_id:
        raise HTTPException(400, "You cannot change your own role or access.")
    if body.role is not None and body.role not in ROLES:
        raise HTTPException(422, f"Role must be one of {', '.join(ROLES)}.")
    updated = scalar(
        s,
        """UPDATE users SET role = coalesce(:r, role), disabled = coalesce(:d, disabled)
           WHERE id = CAST(:u AS uuid) RETURNING id""",
        r=body.role, d=body.disabled, u=user_id,
    )
    if updated is None:
        raise HTTPException(404, "No such team member.")
    audit.record(s, who.firm_id, who.user_id, "user.updated", "user", user_id,
                 role=body.role, disabled=body.disabled)
    return {"ok": True}
