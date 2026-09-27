"""Bring-your-own AI: providers, encrypted keys, model choice. Live checks use a
local Ollama model when one is running (no paid key, nothing leaves the machine)."""

import pytest
from cryptography.exceptions import InvalidTag
from sqlalchemy import text

from nexus.ai import registry, secrets
from nexus.ai.adapters import COMPATIBLE, ModelRef, ModelUnavailable, ToolSpec, complete
from nexus.db import row, tenant
from tests.conftest import OLLAMA_MODEL, OLLAMA_URL, add_local_model, ollama_ready, signup

FAKE_KEY = "sk-test-not-a-real-key-1234"


def test_keys_are_encrypted_bound_to_the_firm_and_never_returned(client):
    signup(client)
    firm = client.get("/api/me").json()["firm"]["id"]
    r = client.post("/api/ai/providers", json={"kind": "openai", "label": "OpenAI", "api_key": FAKE_KEY})
    assert r.status_code == 201
    listed = client.get("/api/ai/providers").json()[0]
    assert listed["key_last4"] == "1234" and listed["has_key"] is True
    assert FAKE_KEY not in str(listed)
    with tenant(firm) as s:
        stored = row(s, "SELECT api_key_enc FROM ai_providers")["api_key_enc"]
    assert FAKE_KEY not in stored and stored.startswith("v1:")
    assert secrets.decrypt(stored, firm) == FAKE_KEY
    with pytest.raises(InvalidTag):  # the ciphertext is useless under another firm's id
        secrets.decrypt(stored, "00000000-0000-4000-8000-000000000000")


def test_only_admins_manage_models_but_everyone_can_choose(client):
    signup(client)
    add_local_model(client)
    client.post("/api/team", json={"name": "A", "email": "a@madiraju.example", "role": "partner",
                                   "temporary_password": "temporary password"})
    client.cookies.clear()
    client.post("/api/auth/login", json={"email": "a@madiraju.example", "password": "temporary password"})
    assert client.get("/api/ai/providers").status_code == 403
    assert client.post("/api/ai/providers", json={"kind": "openai", "label": "x", "api_key": FAKE_KEY}).status_code == 403
    choices = client.get("/api/ai/models").json()
    assert [c["label"] for c in choices] == ["Qwen3 4B (local)"] and choices[0]["is_default"]


def test_one_default_and_it_moves_when_removed(client):
    signup(client)
    first = add_local_model(client)
    second = client.post("/api/ai/models", json={"provider_id": first["provider_id"], "model": "llama3.2:3b",
                                                "label": "Llama"}).json()
    models = {m["id"]: m for m in client.get("/api/ai/models").json()}
    assert models[first["model_id"]]["is_default"] and not models[second["id"]]["is_default"]
    client.patch(f"/api/ai/models/{second['id']}", json={"is_default": True})
    models = {m["id"]: m for m in client.get("/api/ai/models").json()}
    assert models[second["id"]]["is_default"] and not models[first["model_id"]]["is_default"]
    client.delete(f"/api/ai/models/{second['id']}")
    assert client.get("/api/ai/models").json()[0]["is_default"]


def test_validation(client):
    signup(client)
    assert client.post("/api/ai/providers", json={"kind": "openai", "label": "x"}).status_code == 422
    assert client.post("/api/ai/providers", json={"kind": "openai_compatible", "label": "x"}).status_code == 422
    assert client.post("/api/ai/providers", json={"kind": "openai_compatible", "label": "x",
                                                  "base_url": "http://evil.example/v1"}).status_code == 422
    assert client.post("/api/ai/providers", json={"kind": "nope", "label": "x", "api_key": FAKE_KEY}).status_code == 422


def test_a_task_cannot_pick_another_firms_model(client):
    signup(client)
    theirs = add_local_model(client)
    client.cookies.clear()
    signup(client, firm="Other", email="o@other.example")
    firm = client.get("/api/me").json()["firm"]["id"]
    with pytest.raises(ModelUnavailable):
        registry.resolve(firm, theirs["model_id"])
    with tenant(firm) as s:
        assert s.execute(text("SELECT count(*) FROM ai_models")).scalar() == 0


def test_real_provider_rejects_a_bad_key_with_a_plain_message():
    """A real call to OpenAI with an invalid key: proves the wiring up to authentication."""
    ref = ModelRef(kind="openai", model="gpt-4o-mini", api_key=FAKE_KEY, label="OpenAI")
    try:
        complete(ref, system="test", conversation=[{"role": "user", "text": "hi"}], max_tokens=20)
    except ModelUnavailable as exc:
        assert "rejected the API key" in str(exc)
    except Exception as exc:  # no network in this environment
        pytest.skip(f"network unavailable: {exc.__class__.__name__}")
    else:
        pytest.fail("an invalid key was accepted")


live = pytest.mark.skipif(not ollama_ready(), reason=f"Ollama with {OLLAMA_MODEL} is not running")
LOCAL = ModelRef(kind=COMPATIBLE, model=OLLAMA_MODEL, base_url=OLLAMA_URL, label="local")


@live
def test_live_tool_call_round_trip():
    tool = ToolSpec("add", "Add two integers.", {"type": "object", "additionalProperties": False,
                                                 "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                                                 "required": ["a", "b"]})
    turn = complete(LOCAL, system="Use the add tool to do arithmetic. /no_think",
                    conversation=[{"role": "user", "text": "What is 1234 plus 4321?"}], tools=[tool], max_tokens=800)
    assert turn.tool_calls and turn.tool_calls[0].name == "add"
    assert turn.tool_calls[0].input == {"a": 1234, "b": 4321}


@live
def test_live_connection_test_endpoint(client):
    signup(client)
    ids = add_local_model(client)
    result = client.post(f"/api/ai/providers/{ids['provider_id']}/test").json()
    assert result["ok"], result
    assert OLLAMA_MODEL in client.get(f"/api/ai/providers/{ids['provider_id']}/available-models").json()
