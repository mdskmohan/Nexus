"""Which model a task runs on, and with which credentials.

Order of preference:
1. the model the lawyer chose for the task (if it is enabled for the firm);
2. the firm's default model;
3. any enabled model the firm has set up;
4. the platform's own Claude key (ANTHROPIC_API_KEY), if the operator set one.
"""

from nexus.ai import secrets
from nexus.ai.adapters import ANTHROPIC, DEFAULT_PRICES, ModelRef, ModelUnavailable
from nexus.config import settings
from nexus.db import row, rows, tenant

PLATFORM_ID = "platform"

_COLUMNS = """m.id, m.model, m.label, m.price_in_per_mtok, m.price_out_per_mtok, m.is_default,
              p.kind, p.base_url, p.api_key_enc, p.label AS provider_label"""


def _ref(firm_id: str, r: dict) -> ModelRef:
    api_key = secrets.decrypt(r["api_key_enc"], firm_id) if r["api_key_enc"] else None
    price_in, price_out = r["price_in_per_mtok"], r["price_out_per_mtok"]
    if price_in is None and price_out is None and r["model"] in DEFAULT_PRICES and r["kind"] == ANTHROPIC:
        price_in, price_out = DEFAULT_PRICES[r["model"]]
    return ModelRef(
        kind=r["kind"], model=r["model"], api_key=api_key, base_url=r["base_url"],
        label=f"{r['label']} ({r['provider_label']})", id=str(r["id"]),
        price_in=float(price_in) if price_in is not None else None,
        price_out=float(price_out) if price_out is not None else None,
        fallbacks=settings().model_fallbacks,
    )


def platform_model() -> ModelRef | None:
    cfg = settings()
    if not cfg.anthropic_api_key:
        return None
    price_in, price_out = DEFAULT_PRICES.get(cfg.model, (None, None))
    return ModelRef(kind=ANTHROPIC, model=cfg.model, api_key=cfg.anthropic_api_key, label=f"{cfg.model} (platform)",
                    id=PLATFORM_ID, price_in=price_in, price_out=price_out, fallbacks=cfg.model_fallbacks)


def available(firm_id: str) -> list[dict]:
    """Enabled models a lawyer can choose, default first."""
    with tenant(firm_id) as s:
        models = rows(
            s,
            f"""SELECT {_COLUMNS} FROM ai_models m JOIN ai_providers p ON p.id = m.provider_id
                WHERE m.enabled AND p.enabled ORDER BY m.is_default DESC, m.label""",
        )
    out = [{"id": str(m["id"]), "label": m["label"], "provider": m["provider_label"], "kind": m["kind"],
            "model": m["model"], "is_default": m["is_default"]} for m in models]
    if not out and platform_model():
        pm = platform_model()
        out.append({"id": PLATFORM_ID, "label": pm.model, "provider": "Nexus platform", "kind": ANTHROPIC,
                    "model": pm.model, "is_default": True})
    return out


def resolve(firm_id: str, model_id: str | None = None) -> ModelRef:
    with tenant(firm_id) as s:
        if model_id and model_id != PLATFORM_ID:
            chosen = row(
                s,
                f"""SELECT {_COLUMNS} FROM ai_models m JOIN ai_providers p ON p.id = m.provider_id
                    WHERE m.id = CAST(:m AS uuid) AND m.enabled AND p.enabled""",
                m=model_id,
            )
            if chosen is None:
                raise ModelUnavailable("The AI model chosen for this task is no longer available. Choose another.",
                                       f"model {model_id} missing or disabled")
            return _ref(firm_id, chosen)
        fallback = row(
            s,
            f"""SELECT {_COLUMNS} FROM ai_models m JOIN ai_providers p ON p.id = m.provider_id
                WHERE m.enabled AND p.enabled ORDER BY m.is_default DESC, m.created_at LIMIT 1""",
        )
    if fallback:
        return _ref(firm_id, fallback)
    platform = platform_model()
    if platform:
        return platform
    raise ModelUnavailable("The AI is not connected yet. Ask your administrator to add an AI model in Firm settings.",
                           "no firm models and no platform key")
