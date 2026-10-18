"""Sign-up, sign-in, the workspace's team, and its audit trail."""

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
from nexus.security import (
    MIN_PASSWORD_LENGTH,
    PERMISSIONS,
    ROLES,
    hash_password,
    issue_token,
    verify_password,
)

router = APIRouter(prefix="/api", tags=["auth"])


class SignUp(BaseModel):
    workspace_name: str = Field(min_length=2, max_length=200)
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


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    # Changing the password needs the current one, so a session left open cannot be used to take the account.
    current_password: str | None = Field(default=None, max_length=200)
    new_password: str | None = Field(default=None, min_length=MIN_PASSWORD_LENGTH, max_length=200)


class WorkspaceUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=200)


def _set_session(response: Response, user_id, workspace_id, role: str) -> None:
    response.set_cookie(
        COOKIE, issue_token(user_id, workspace_id, role), httponly=True, samesite="lax",
        secure=settings().cookie_secure, max_age=settings().session_hours * 3600, path="/",
    )


@router.post("/auth/signup", status_code=201)
def signup(body: SignUp, response: Response) -> dict:
    workspace_id = str(uuid4())
    try:
        with tenant(workspace_id) as s:
            scalar(s, "INSERT INTO workspaces (id, name) VALUES (:id, :name) RETURNING id",
                   id=workspace_id, name=body.workspace_name.strip())
            user_id = scalar(
                s,
                """INSERT INTO users (workspace_id, email, name, password_hash, role)
                   VALUES (:f, :e, :n, :h, 'admin') RETURNING id""",
                f=workspace_id, e=body.email.lower(), n=body.name.strip(), h=hash_password(body.password),
            )
            audit.record(s, workspace_id, user_id, "workspace.created", "workspace", workspace_id)
    except IntegrityError:
        raise HTTPException(409, "An account with this email already exists.") from None
    _set_session(response, user_id, workspace_id, "admin")
    return {"ok": True}


@router.post("/auth/login")
def login(body: SignIn, response: Response) -> dict:
    with unscoped() as s:
        user = row(s, "SELECT * FROM auth_lookup(:e)", e=body.email)
    # Same message either way, so the form does not reveal which emails exist.
    if user is None or user["disabled"] or not verify_password(user["password_hash"], body.password):
        raise HTTPException(401, "That email and password do not match.")
    with tenant(user["workspace_id"]) as s:
        audit.record(s, user["workspace_id"], user["id"], "user.signed_in", "user", user["id"])
    _set_session(response, user["id"], user["workspace_id"], user["role"])
    return {"ok": True}


@router.post("/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(who: Principal = Depends(principal), s: Session = Depends(db)) -> dict:
    workspace = row(s, "SELECT id, name FROM workspaces WHERE id = :w", w=who.workspace_id)
    return {"user": {"id": who.user_id, "name": who.name, "email": who.email, "role": who.role},
            "workspace": workspace, "permissions": sorted(PERMISSIONS[who.role]),
            "model_configured": bool(registry.available(who.workspace_id))}


@router.patch("/me")
def update_me(body: ProfileUpdate, who: Principal = Depends(principal), s: Session = Depends(db)) -> dict:
    if body.new_password is not None:
        current = row(s, "SELECT password_hash FROM users WHERE id = :u", u=who.user_id)
        if not body.current_password or not verify_password(current["password_hash"], body.current_password):
            raise HTTPException(400, "Your current password is not correct.")
        scalar(s, "UPDATE users SET password_hash = :h WHERE id = :u RETURNING id",
               h=hash_password(body.new_password), u=who.user_id)
        audit.record(s, who.workspace_id, who.user_id, "user.password_changed", "user", who.user_id)
    if body.name is not None and body.name.strip() != who.name:
        scalar(s, "UPDATE users SET name = :n WHERE id = :u RETURNING id", n=body.name.strip(), u=who.user_id)
        audit.record(s, who.workspace_id, who.user_id, "user.profile_updated", "user", who.user_id)
    return {"ok": True}


@router.patch("/workspace")
def update_workspace(body: WorkspaceUpdate, who: Principal = Depends(require("manage_workspace")),
                     s: Session = Depends(db)) -> dict:
    scalar(s, "UPDATE workspaces SET name = :n WHERE id = :w RETURNING id", n=body.name.strip(), w=who.workspace_id)
    audit.record(s, who.workspace_id, who.user_id, "workspace.renamed", "workspace", who.workspace_id)
    return {"ok": True}


@router.get("/team")
def team(s: Session = Depends(db)) -> list[dict]:
    return rows(s, "SELECT id, name, email, role, disabled, created_at FROM users ORDER BY created_at")


@router.post("/team", status_code=201)
def add_member(body: NewMember, who: Principal = Depends(require("manage_people")),
               s: Session = Depends(db)) -> dict:
    if body.role not in ROLES:
        raise HTTPException(422, f"Role must be one of {', '.join(ROLES)}.")
    try:
        with s.begin_nested():
            user_id = scalar(
                s,
                """INSERT INTO users (workspace_id, email, name, password_hash, role)
                   VALUES (:f, :e, :n, :h, :r) RETURNING id""",
                f=who.workspace_id, e=body.email.lower(), n=body.name.strip(),
                h=hash_password(body.temporary_password), r=body.role,
            )
    except IntegrityError:
        raise HTTPException(409, "An account with this email already exists.") from None
    audit.record(s, who.workspace_id, who.user_id, "user.added", "user", user_id, role=body.role)
    return {"id": str(user_id)}


@router.patch("/team/{user_id}")
def update_member(user_id: str, body: MemberUpdate, who: Principal = Depends(require("manage_people")),
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
    audit.record(s, who.workspace_id, who.user_id, "user.updated", "user", user_id,
                 role=body.role, disabled=body.disabled)
    return {"ok": True}


@router.get("/audit")
def audit_trail(who: Principal = Depends(require("view_audit")), s: Session = Depends(db)) -> list[dict]:
    return audit.recent(s)
