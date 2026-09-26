"""The single place Nexus talks to the model.

Every call goes through `call()`, which applies the platform defaults
(model, adaptive thinking, effort, prompt caching, refusal fallbacks) and
returns token usage and cost so each run can be metered.
"""

from dataclasses import dataclass
from functools import lru_cache

import anthropic

from nexus.config import settings

# USD per million tokens: (input, output). Cache reads bill at 10% of input,
# cache writes (5-minute) at 125%.
PRICES = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-fable-5-1": (10.00, 50.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ModelUnavailable(RuntimeError):
    """No credentials, or the provider rejected the request outright.

    The message is shown to lawyers; `technical` is for logs and step detail.
    """

    def __init__(self, message: str, technical: str):
        super().__init__(message)
        self.technical = technical


_ASK_ADMIN = "The AI is not connected. Ask your administrator to check the AI key."


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.cost_usd += other.cost_usd


@lru_cache
def client() -> anthropic.Anthropic:
    # An explicit key from settings wins; otherwise the SDK resolves credentials itself.
    return anthropic.Anthropic(api_key=settings().anthropic_api_key, max_retries=4)


def usage_of(response, model: str) -> Usage:
    u = response.usage
    read = getattr(u, "cache_read_input_tokens", 0) or 0
    write = getattr(u, "cache_creation_input_tokens", 0) or 0
    price_in, price_out = PRICES.get(model, PRICES["claude-opus-5"])
    cost = (
        u.input_tokens * price_in
        + read * price_in * 0.10
        + write * price_in * 1.25
        + u.output_tokens * price_out
    ) / 1_000_000
    return Usage(u.input_tokens, u.output_tokens, read, write, cost)


def call(*, system: str, messages: list, tools: list | None = None, max_tokens: int | None = None,
         model: str | None = None, effort: str | None = None):
    """One model request with platform defaults. Returns (response, usage)."""
    cfg = settings()
    model = model or cfg.model
    params = dict(
        model=model,
        max_tokens=max_tokens or cfg.agent_max_output_tokens,
        system=system,
        messages=messages,
        thinking={"type": "adaptive"},
        output_config={"effort": effort or cfg.effort},
        # Auto-caching: the stable prefix (system prompt, tools, earlier turns) is
        # re-read at a tenth of the price on every later step of an agent loop.
        cache_control={"type": "ephemeral"},
    )
    if tools:
        params["tools"] = tools
    try:
        if cfg.model_fallbacks:
            response = client().beta.messages.create(
                betas=[FALLBACK_BETA], fallbacks="default", **params
            )
        else:
            response = client().messages.create(**params)
    except anthropic.AuthenticationError as exc:
        raise ModelUnavailable(_ASK_ADMIN, "Anthropic rejected ANTHROPIC_API_KEY (401).") from exc
    except anthropic.PermissionDeniedError as exc:
        raise ModelUnavailable(_ASK_ADMIN, f"API key lacks permission for model {model} (403).") from exc
    except anthropic.NotFoundError as exc:
        raise ModelUnavailable(_ASK_ADMIN, f"Model {model} not found (404); check NEXUS_MODEL.") from exc
    except TypeError as exc:
        # Raised by the SDK when no credentials can be resolved at all.
        if "api_key" in str(exc) or "auth" in str(exc).lower():
            raise ModelUnavailable("The AI is not connected yet. Ask your administrator to add the AI key.",
                                   "No credentials: set ANTHROPIC_API_KEY in .env.") from exc
        raise
    return response, usage_of(response, response.model or model)


def echo_content(response) -> list:
    """Assistant content to append to the conversation for the next turn.

    Thinking blocks are passed back unchanged (required for tool use with
    thinking). `fallback` blocks are audit markers only, and are dropped.
    """
    return [block for block in response.content if block.type != "fallback"]


def served_by_fallback(response) -> bool:
    iterations = getattr(response.usage, "iterations", None) or []
    return any(getattr(i, "type", "") == "fallback_message" for i in iterations)
