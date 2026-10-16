"""Opening a workspace's warehouse connections. Secret settings are stored
encrypted (bound to the workspace, like AI keys) and only decrypted here."""

import json

from nexus.ai import secrets
from nexus.connectors import KINDS, Warehouse


def seal(values: dict, workspace_id: str) -> str | None:
    return secrets.encrypt(json.dumps(values), workspace_id) if values else None


def unseal(token: str | None, workspace_id: str) -> dict:
    return json.loads(secrets.decrypt(token, workspace_id)) if token else {}


def open_warehouse(workspace_id: str, conn: dict) -> Warehouse:
    """A warehouse for a connection row; use it as a context manager."""
    return KINDS[conn["kind"]](conn["config"], unseal(conn["secrets_enc"], str(workspace_id)))
