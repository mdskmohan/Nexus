"""Talking to a provider outside an agent run: list its models, test a connection."""

from nexus.ai.adapters import (
    ANTHROPIC,
    COMPATIBLE,
    GOOGLE,
    OPENAI,
    ModelRef,
    ModelUnavailable,
    _unavailable,
    complete,
)

# Shown in settings to help admins fill in the form. Endpoints are the
# providers' documented ones; the admin can change them.
PRESETS = [
    {"kind": ANTHROPIC, "label": "Anthropic (Claude)", "base_url": None, "needs_key": True,
     "hint": "Create a key at console.anthropic.com."},
    {"kind": OPENAI, "label": "OpenAI (GPT)", "base_url": None, "needs_key": True,
     "hint": "Create a key at platform.openai.com."},
    {"kind": GOOGLE, "label": "Google (Gemini)", "base_url": None, "needs_key": True,
     "hint": "Create a key at aistudio.google.com."},
    {"kind": COMPATIBLE, "label": "Ollama (on this server)", "base_url": "http://localhost:11434/v1",
     "needs_key": False, "hint": "Runs models on your own machine. Nothing leaves your network."},
    {"kind": COMPATIBLE, "label": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "needs_key": True,
     "hint": "One key for many providers' models."},
    {"kind": COMPATIBLE, "label": "Other OpenAI-compatible endpoint", "base_url": "", "needs_key": True,
     "hint": "Azure OpenAI, Groq, a self-hosted vLLM server, or any endpoint that speaks the OpenAI API."},
]


def list_models(ref: ModelRef) -> list[str]:
    """Model ids the provider offers to this key, newest first where the API says."""
    try:
        if ref.kind == ANTHROPIC:
            import anthropic

            client = anthropic.Anthropic(api_key=ref.api_key, base_url=ref.base_url or None)
            return [m.id for m in client.models.list(limit=100)]
        if ref.kind in (OPENAI, COMPATIBLE):
            import openai

            client = openai.OpenAI(api_key=ref.api_key or "not-needed", base_url=ref.base_url or None, timeout=30)
            ids = [m.id for m in client.models.list()]
            return sorted(ids)
        if ref.kind == GOOGLE:
            from google import genai

            client = genai.Client(api_key=ref.api_key)
            return [m.name.removeprefix("models/") for m in client.models.list()
                    if "generateContent" in (m.supported_actions or [])]
    except ModelUnavailable:
        raise
    except Exception as exc:  # each SDK has its own error types; all mean "could not list"
        status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        raise _unavailable(ref, exc, status if isinstance(status, int) else None) from exc
    return []


def test(ref: ModelRef) -> str:
    """A tiny real request. Returns the model's reply; raises ModelUnavailable on failure."""
    turn = complete(ref, system="You are a connection test.",
                    conversation=[{"role": "user", "text": "Reply with the single word: ready"}],
                    max_tokens=2000, effort="low")
    return turn.text.strip()[:200] or "(empty reply)"
