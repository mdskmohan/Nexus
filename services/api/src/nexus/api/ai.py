"""Firm settings for AI models: providers, keys, models, and connection tests."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nexus import audit
from nexus.ai import catalog, registry, secrets
from nexus.ai.adapters import COMPATIBLE, KINDS, ModelRef, ModelUnavailable
from nexus.api.deps import Principal, db, found, principal, require
from nexus.db import row, rows, scalar

router = APIRouter(prefix="/api/ai", tags=["ai"])


class NewProvider(BaseModel):
    kind: str
    label: str = Field(min_length=1, max_length=100)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=2000)


class ProviderUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=2000)
    enabled: bool | None = None


class NewModel(BaseModel):
    provider_id: UUID
    model: str = Field(min_length=1, max_length=200)
    label: str = Field(default="", max_length=100)
    price_in_per_mtok: float | None = Field(default=None, ge=0)
    price_out_per_mtok: float | None = Field(default=None, ge=0)
    is_default: bool = False


class ModelUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    price_in_per_mtok: float | None = Field(default=None, ge=0)
    price_out_per_mtok: float | None = Field(default=None, ge=0)
    clear_price: bool = False
    enabled: bool | None = None
    is_default: bool | None = None


def _check_url(kind: str, base_url: str | None) -> str | None:
    url = (base_url or "").strip() or None
    if kind == COMPATIBLE and not url:
        raise HTTPException(422, "An OpenAI-compatible provider needs its endpoint URL.")
    if url and not url.startswith(("https://", "http://localhost", "http://127.0.0.1", "http://host.docker.internal")):
        raise HTTPException(422, "The endpoint must use https (or be on this machine).")
    return url


def _provider_ref(s: Session, firm_id: str, provider_id: UUID, model: str | None) -> ModelRef:
    p = found(row(s, "SELECT * FROM ai_providers WHERE id = :p", p=provider_id), "No such provider.")
    if not model:
        first = row(s, "SELECT model FROM ai_models WHERE provider_id = :p ORDER BY created_at LIMIT 1",
                    p=provider_id)
        model = first["model"] if first else None
    key = secrets.decrypt(p["api_key_enc"], firm_id) if p["api_key_enc"] else None
    return ModelRef(kind=p["kind"], model=model or "", api_key=key, base_url=p["base_url"], label=p["label"])


# Choosing a model (everyone) ------------------------------------------------

@router.get("/models")
def choosable_models(who: Principal = Depends(principal)) -> list[dict]:
    return registry.available(who.firm_id)


# Managing providers and models (admins) -------------------------------------

@router.get("/presets")
def presets(who: Principal = Depends(require("admin"))) -> list[dict]:
    return catalog.PRESETS


@router.get("/providers")
def list_providers(who: Principal = Depends(require("admin")), s: Session = Depends(db)) -> list[dict]:
    providers = rows(s, """SELECT id, kind, label, base_url, key_last4, api_key_enc IS NOT NULL AS has_key,
                                  enabled, last_test_ok, last_test_at, last_test_msg, created_at
                           FROM ai_providers ORDER BY created_at""")
    models = rows(s, """SELECT id, provider_id, model, label, price_in_per_mtok, price_out_per_mtok,
                               is_default, enabled FROM ai_models ORDER BY created_at""")
    for p in providers:
        p["models"] = [m for m in models if m["provider_id"] == p["id"]]
    return providers


@router.post("/providers", status_code=201)
def add_provider(body: NewProvider, who: Principal = Depends(require("admin")), s: Session = Depends(db)) -> dict:
    if body.kind not in KINDS:
        raise HTTPException(422, "Unknown provider type.")
    url = _check_url(body.kind, body.base_url)
    key = (body.api_key or "").strip() or None
    if body.kind != COMPATIBLE and not key:
        raise HTTPException(422, "This provider needs an API key.")
    try:
        encrypted = secrets.encrypt(key, who.firm_id) if key else None
    except secrets.SecretError as exc:
        raise HTTPException(503, "Nexus cannot store keys yet: the server's encryption key is not set. "
                                 "Contact whoever runs your Nexus installation.") from exc
    provider_id = scalar(
        s, """INSERT INTO ai_providers (firm_id, kind, label, base_url, api_key_enc, key_last4)
              VALUES (:f, :k, :l, :u, :e, :l4) RETURNING id""",
        f=who.firm_id, k=body.kind, l=body.label.strip(), u=url, e=encrypted,
        l4=secrets.last4(key) if key else None,
    )
    audit.record(s, who.firm_id, who.user_id, "ai.provider_added", "ai_provider", provider_id, kind=body.kind)
    return {"id": str(provider_id)}


@router.patch("/providers/{provider_id}")
def update_provider(provider_id: UUID, body: ProviderUpdate, who: Principal = Depends(require("admin")),
                    s: Session = Depends(db)) -> dict:
    p = found(row(s, "SELECT kind FROM ai_providers WHERE id = :p", p=provider_id), "No such provider.")
    key = (body.api_key or "").strip() or None
    url = _check_url(p["kind"], body.base_url) if body.base_url is not None else None
    try:
        encrypted = secrets.encrypt(key, who.firm_id) if key else None
    except secrets.SecretError as exc:
        raise HTTPException(503, "Nexus cannot store keys yet: the server's encryption key is not set.") from exc
    scalar(
        s, """UPDATE ai_providers SET label = coalesce(:l, label), base_url = coalesce(:u, base_url),
                     api_key_enc = coalesce(:e, api_key_enc), key_last4 = coalesce(:l4, key_last4),
                     enabled = coalesce(:en, enabled),
                     last_test_ok = CASE WHEN :e IS NULL AND :u IS NULL THEN last_test_ok END
              WHERE id = :p RETURNING id""",
        l=body.label, u=url, e=encrypted, l4=secrets.last4(key) if key else None, en=body.enabled, p=provider_id,
    )
    audit.record(s, who.firm_id, who.user_id, "ai.provider_updated", "ai_provider", provider_id,
                 key_changed=bool(key), enabled=body.enabled)
    return {"ok": True}


@router.delete("/providers/{provider_id}")
def delete_provider(provider_id: UUID, who: Principal = Depends(require("admin")), s: Session = Depends(db)) -> dict:
    found(scalar(s, "DELETE FROM ai_providers WHERE id = :p RETURNING id", p=provider_id), "No such provider.")
    audit.record(s, who.firm_id, who.user_id, "ai.provider_removed", "ai_provider", provider_id)
    return {"ok": True}


@router.get("/providers/{provider_id}/available-models")
def provider_models(provider_id: UUID, who: Principal = Depends(require("admin")),
                    s: Session = Depends(db)) -> list[str]:
    ref = _provider_ref(s, who.firm_id, provider_id, "")
    try:
        return catalog.list_models(ref)
    except ModelUnavailable as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/providers/{provider_id}/test")
def test_provider(provider_id: UUID, who: Principal = Depends(require("admin")), s: Session = Depends(db)) -> dict:
    ref = _provider_ref(s, who.firm_id, provider_id, None)
    if not ref.model:
        raise HTTPException(409, "Add a model to this provider first, then test it.")
    try:
        reply = catalog.test(ref)
        ok, message = True, f"Connected. {ref.model} replied: “{reply}”"
    except ModelUnavailable as exc:
        ok, message = False, str(exc)
    except Exception as exc:  # any other provider error is reported, not raised
        ok, message = False, f"The provider returned an error: {exc.__class__.__name__}."
    scalar(s, """UPDATE ai_providers SET last_test_ok = :ok, last_test_at = now(), last_test_msg = :m
                 WHERE id = :p RETURNING id""", ok=ok, m=message[:500], p=provider_id)
    audit.record(s, who.firm_id, who.user_id, "ai.provider_tested", "ai_provider", provider_id, ok=ok)
    return {"ok": ok, "message": message}


def _clear_default(s: Session) -> None:
    scalar(s, "UPDATE ai_models SET is_default = false WHERE is_default RETURNING 1")


@router.post("/models", status_code=201)
def add_model(body: NewModel, who: Principal = Depends(require("admin")), s: Session = Depends(db)) -> dict:
    found(row(s, "SELECT id FROM ai_providers WHERE id = :p", p=body.provider_id), "No such provider.")
    first = scalar(s, "SELECT count(*) FROM ai_models") == 0
    if body.is_default or first:
        _clear_default(s)
    try:
        with s.begin_nested():
            model_id = scalar(
                s, """INSERT INTO ai_models (firm_id, provider_id, model, label, price_in_per_mtok,
                                             price_out_per_mtok, is_default)
                      VALUES (:f, :p, :m, :l, :pi, :po, :d) RETURNING id""",
                f=who.firm_id, p=body.provider_id, m=body.model.strip(), l=body.label.strip() or body.model.strip(),
                pi=body.price_in_per_mtok, po=body.price_out_per_mtok, d=body.is_default or first,
            )
    except IntegrityError:
        raise HTTPException(409, "This model is already added for this provider.") from None
    audit.record(s, who.firm_id, who.user_id, "ai.model_added", "ai_model", model_id, model=body.model)
    return {"id": str(model_id)}


@router.patch("/models/{model_id}")
def update_model(model_id: UUID, body: ModelUpdate, who: Principal = Depends(require("admin")),
                 s: Session = Depends(db)) -> dict:
    found(row(s, "SELECT id FROM ai_models WHERE id = :m", m=model_id), "No such model.")
    if body.is_default:
        _clear_default(s)
    scalar(
        s, """UPDATE ai_models SET label = coalesce(:l, label),
                     price_in_per_mtok = CASE WHEN :clear THEN NULL ELSE coalesce(:pi, price_in_per_mtok) END,
                     price_out_per_mtok = CASE WHEN :clear THEN NULL ELSE coalesce(:po, price_out_per_mtok) END,
                     enabled = coalesce(:en, enabled), is_default = coalesce(:d, is_default)
              WHERE id = :m RETURNING id""",
        l=body.label, pi=body.price_in_per_mtok, po=body.price_out_per_mtok, clear=body.clear_price,
        en=body.enabled, d=body.is_default, m=model_id,
    )
    audit.record(s, who.firm_id, who.user_id, "ai.model_updated", "ai_model", model_id)
    return {"ok": True}


@router.delete("/models/{model_id}")
def delete_model(model_id: UUID, who: Principal = Depends(require("admin")), s: Session = Depends(db)) -> dict:
    was_default = found(row(s, "SELECT is_default FROM ai_models WHERE id = :m", m=model_id), "No such model.")
    scalar(s, "DELETE FROM ai_models WHERE id = :m RETURNING id", m=model_id)
    if was_default["is_default"]:
        scalar(s, """UPDATE ai_models SET is_default = true
                     WHERE id = (SELECT id FROM ai_models WHERE enabled ORDER BY created_at LIMIT 1) RETURNING id""")
    audit.record(s, who.firm_id, who.user_id, "ai.model_removed", "ai_model", model_id)
    return {"ok": True}
