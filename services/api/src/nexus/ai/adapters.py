"""One interface over every supported model provider.

Agents talk in a provider-neutral conversation:

    {"role": "user", "text": str}
    {"role": "assistant", "turn": Turn}          # echoed back in the provider's own format
    {"role": "tool_results", "results": [ToolResult, ...]}

and get back a `Turn` (text, tool calls, why it stopped, token usage). Each
adapter converts to and from its provider's API. Provider-native assistant
content is kept on the Turn and echoed back unchanged, which some providers
require (Claude thinking blocks, Gemini thought signatures).

Providers: Anthropic (Claude), OpenAI, Google (Gemini), and any
OpenAI-compatible endpoint (Azure OpenAI, OpenRouter, Groq, Ollama, vLLM,
and similar).
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

ANTHROPIC, OPENAI, GOOGLE, COMPATIBLE = "anthropic", "openai", "google", "openai_compatible"
KINDS = (ANTHROPIC, OPENAI, GOOGLE, COMPATIBLE)
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# List prices (USD per million tokens) used when a firm has not set its own.
# Only providers whose prices we track; anything else is "not priced".
DEFAULT_PRICES = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-fable-5-1": (10.00, 50.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


class ModelUnavailable(RuntimeError):
    """The model cannot be used: no credentials, rejected key, unknown model, unreachable.

    `str(exc)` is shown to lawyers; `technical` is for logs and the step detail.
    """

    def __init__(self, message: str, technical: str, admin: str | None = None):
        super().__init__(message)
        self.technical = technical
        # What to tell the administrator who is setting the provider up.
        self.admin = admin or message


@dataclass
class ModelRef:
    kind: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    label: str = ""
    id: str | None = None
    price_in: float | None = None
    price_out: float | None = None
    fallbacks: bool = True

    @property
    def priced(self) -> bool:
        return self.price_in is not None and self.price_out is not None


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict | None  # None when the model sent arguments that are not valid JSON


@dataclass
class ToolResult:
    id: str
    name: str
    content: str
    is_error: bool = False


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_read_tokens + self.cache_write_tokens

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.cost_usd += other.cost_usd


@dataclass
class Turn:
    text: str
    tool_calls: list[ToolCall]
    stop: str                      # "end" | "tool_use" | "max_tokens" | "refusal"
    usage: Usage
    model: str
    native: Any = None
    fallback: bool = False
    detail: dict = field(default_factory=dict)


@dataclass
class ToolSpec:
    name: str
    description: str
    schema: dict


def price(ref: ModelRef, usage: Usage) -> float:
    if not ref.priced:
        return 0.0
    cache_read_rate = 0.10 if ref.kind == ANTHROPIC else 1.0
    return (usage.input_tokens * ref.price_in
            + usage.cache_read_tokens * ref.price_in * cache_read_rate
            + usage.cache_write_tokens * ref.price_in * (1.25 if ref.kind == ANTHROPIC else 1.0)
            + usage.output_tokens * ref.price_out) / 1_000_000


def _unavailable(ref: ModelRef, exc: Exception, status: int | None) -> ModelUnavailable:
    who = ref.label or ref.kind
    if status in (401, 403):
        return ModelUnavailable(f"{who} rejected the API key. Ask your administrator to check it in Firm settings.",
                                f"{ref.kind} {status}: {exc}",
                                f"{who} rejected this API key. Check that it was copied in full and is active, "
                                "then save it again.")
    if status == 404:
        return ModelUnavailable(f"The model '{ref.model}' is not available from {who}. Ask your administrator to check it.",
                                f"{ref.kind} 404 for {ref.model}: {exc}",
                                f"{who} does not offer '{ref.model}' to this key. Pick a model from the list.")
    return ModelUnavailable(f"Could not reach {who}. Try again shortly; if it keeps happening, ask your administrator.",
                            f"{ref.kind} unreachable: {exc}",
                            f"Could not reach {who}. Check the endpoint address and that the service is running.")


# Anthropic ---------------------------------------------------------------

def _anthropic(ref: ModelRef, system: str, conversation: list, tools: list[ToolSpec], max_tokens: int,
               effort: str) -> Turn:
    import anthropic

    messages: list = []
    for item in conversation:
        if item["role"] == "user":
            messages.append({"role": "user", "content": item["text"]})
        elif item["role"] == "assistant":
            messages.append({"role": "assistant", "content": item["turn"].native})
        else:
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": r.id, "content": r.content, "is_error": r.is_error}
                for r in item["results"]]})
    params = dict(
        model=ref.model, max_tokens=max_tokens, system=system, messages=messages,
        thinking={"type": "adaptive"}, output_config={"effort": effort},
        cache_control={"type": "ephemeral"},
        tools=[{"name": t.name, "description": t.description, "input_schema": t.schema, "strict": True}
               for t in tools] or anthropic.NOT_GIVEN,
    )
    client = anthropic.Anthropic(api_key=ref.api_key, base_url=ref.base_url or None, max_retries=4)
    try:
        if ref.fallbacks and not ref.base_url:
            response = client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **params)
        else:
            response = client.messages.create(**params)
    except TypeError as exc:
        if "auth" in str(exc).lower() or "api_key" in str(exc):
            raise ModelUnavailable("The AI is not connected yet. Ask your administrator to add an AI key.",
                                   "No Anthropic credentials.") from exc
        raise
    except anthropic.APIStatusError as exc:
        if exc.status_code in (401, 403, 404):
            raise _unavailable(ref, exc, exc.status_code) from exc
        raise
    except anthropic.APIConnectionError as exc:
        raise _unavailable(ref, exc, None) from exc

    u = response.usage
    usage = Usage(u.input_tokens, u.output_tokens, getattr(u, "cache_read_input_tokens", 0) or 0,
                  getattr(u, "cache_creation_input_tokens", 0) or 0)
    iterations = getattr(u, "iterations", None) or []
    stop = {"tool_use": "tool_use", "max_tokens": "max_tokens", "refusal": "refusal"}.get(response.stop_reason, "end")
    return Turn(
        text="".join(b.text for b in response.content if b.type == "text"),
        tool_calls=[ToolCall(b.id, b.name, b.input if isinstance(b.input, dict) else None)
                    for b in response.content if b.type == "tool_use"],
        stop=stop, usage=usage, model=response.model or ref.model,
        native=[b for b in response.content if b.type != "fallback"],
        fallback=any(getattr(i, "type", "") == "fallback_message" for i in iterations),
    )


# OpenAI and OpenAI-compatible -------------------------------------------------

def _openai(ref: ModelRef, system: str, conversation: list, tools: list[ToolSpec], max_tokens: int,
            effort: str) -> Turn:
    import openai

    messages: list = [{"role": "system", "content": system}]
    for item in conversation:
        if item["role"] == "user":
            messages.append({"role": "user", "content": item["text"]})
        elif item["role"] == "assistant":
            messages.append(item["turn"].native)
        else:
            for r in item["results"]:
                messages.append({"role": "tool", "tool_call_id": r.id,
                                 "content": f"ERROR: {r.content}" if r.is_error else r.content})
    strict = ref.kind == OPENAI
    params: dict = dict(
        model=ref.model, messages=messages,
        tools=[{"type": "function", "function": {"name": t.name, "description": t.description,
                                                   "parameters": t.schema, **({"strict": True} if strict else {})}}
               for t in tools] or openai.NOT_GIVEN,
    )
    if ref.kind == OPENAI:
        params["max_completion_tokens"] = max_tokens
        if re.match(r"^(o\d|gpt-5)", ref.model):
            params["reasoning_effort"] = {"xhigh": "high", "max": "high"}.get(effort, effort)
    else:
        params["max_tokens"] = max_tokens
    # Self-hosted endpoints: fail fast rather than tie a worker up retrying a server that is down or hung.
    hosted = ref.kind == OPENAI
    client = openai.OpenAI(api_key=ref.api_key or "not-needed", base_url=ref.base_url or None,
                           max_retries=4 if hosted else 1, timeout=600 if hosted else 300)
    try:
        response = client.chat.completions.create(**params)
    except openai.APIStatusError as exc:
        if exc.status_code in (401, 403, 404):
            raise _unavailable(ref, exc, exc.status_code) from exc
        raise
    except openai.APIConnectionError as exc:
        raise _unavailable(ref, exc, None) from exc

    choice = response.choices[0]
    message = choice.message
    calls = []
    for c in message.tool_calls or []:
        try:
            args = json.loads(c.function.arguments or "{}")
            args = args if isinstance(args, dict) else None
        except json.JSONDecodeError:
            args = None
        calls.append(ToolCall(c.id or f"call_{uuid.uuid4().hex[:12]}", c.function.name, args))
    text = _THINK.sub("", message.content or "").strip()
    native: dict = {"role": "assistant", "content": message.content or ""}
    if calls:
        native["tool_calls"] = [{"id": c.id, "type": "function",
                                 "function": {"name": c.name, "arguments": json.dumps(c.input or {})}}
                                for c in calls]
    u = response.usage
    cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0 if u else 0
    usage = Usage((u.prompt_tokens - cached) if u else 0, u.completion_tokens if u else 0, cached)
    stop = ("tool_use" if calls else {"length": "max_tokens", "content_filter": "refusal"}
            .get(choice.finish_reason, "end"))
    return Turn(text, calls, stop, usage, response.model or ref.model, native)


# Google Gemini --------------------------------------------------------------

def _google(ref: ModelRef, system: str, conversation: list, tools: list[ToolSpec], max_tokens: int,
            effort: str) -> Turn:
    from google import genai
    from google.genai import errors, types

    contents: list = []
    for item in conversation:
        if item["role"] == "user":
            contents.append(types.Content(role="user", parts=[types.Part(text=item["text"])]))
        elif item["role"] == "assistant":
            contents.append(item["turn"].native)
        else:
            contents.append(types.Content(role="user", parts=[
                types.Part(function_response=types.FunctionResponse(
                    id=r.id, name=r.name, response={"error": r.content} if r.is_error else {"result": r.content}))
                for r in item["results"]]))
    config = types.GenerateContentConfig(
        system_instruction=system,
        max_output_tokens=max_tokens,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        tools=[types.Tool(function_declarations=[
            types.FunctionDeclaration(name=t.name, description=t.description, parameters_json_schema=t.schema)
            for t in tools])] if tools else None,
    )
    client = genai.Client(api_key=ref.api_key)
    try:
        response = client.models.generate_content(model=ref.model, contents=contents, config=config)
    except errors.ClientError as exc:
        if exc.code in (400, 401, 403) and "key" in str(exc).lower():
            raise _unavailable(ref, exc, 401) from exc
        if exc.code in (401, 403, 404):
            raise _unavailable(ref, exc, exc.code) from exc
        raise
    except (OSError, errors.ServerError) as exc:
        raise _unavailable(ref, exc, None) from exc

    blocked = getattr(response.prompt_feedback, "block_reason", None) if response.prompt_feedback else None
    candidate = response.candidates[0] if response.candidates else None
    parts = (candidate.content.parts if candidate and candidate.content and candidate.content.parts else [])
    calls = [ToolCall(p.function_call.id or f"call_{uuid.uuid4().hex[:12]}", p.function_call.name,
                      dict(p.function_call.args or {}))
             for p in parts if p.function_call]
    text = "".join(p.text for p in parts if p.text and not p.thought)
    reason = str(getattr(candidate, "finish_reason", "") or "")
    if blocked or any(k in reason for k in ("SAFETY", "PROHIBITED", "BLOCKLIST", "RECITATION")):
        stop = "refusal"
    elif calls:
        stop = "tool_use"
    elif "MAX_TOKENS" in reason:
        stop = "max_tokens"
    else:
        stop = "end"
    m = response.usage_metadata
    cached = (m.cached_content_token_count or 0) if m else 0
    usage = Usage(((m.prompt_token_count or 0) - cached) if m else 0,
                  ((m.candidates_token_count or 0) + (m.thoughts_token_count or 0)) if m else 0, cached)
    # Echo the model's content (including thought signatures) exactly as returned.
    native = candidate.content if candidate and candidate.content else types.Content(role="model", parts=[])
    return Turn(text, calls, stop, usage, ref.model, native)


_ADAPTERS = {ANTHROPIC: _anthropic, OPENAI: _openai, COMPATIBLE: _openai, GOOGLE: _google}


def complete(ref: ModelRef, *, system: str, conversation: list, tools: list[ToolSpec] | None = None,
             max_tokens: int = 16000, effort: str = "high") -> Turn:
    """One model call. Raises ModelUnavailable for configuration problems."""
    if ref.kind not in _ADAPTERS:
        raise ModelUnavailable("This AI provider is not supported.", f"unknown provider kind {ref.kind!r}")
    if ref.kind != COMPATIBLE and not ref.api_key and ref.kind != ANTHROPIC:
        raise ModelUnavailable("The AI is not connected yet. Ask your administrator to add an AI key.",
                               f"no key for {ref.kind}")
    turn = _ADAPTERS[ref.kind](ref, system, conversation, tools or [], max_tokens, effort)
    turn.usage.cost_usd = price(ref, turn.usage)
    return turn
