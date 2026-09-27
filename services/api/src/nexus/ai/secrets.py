"""Encryption for firms' AI provider keys.

AES-256-GCM with a platform master key (NEXUS_SECRET_KEY, 32 bytes as
base64). Ciphertexts carry a version prefix so the master key can be rotated.
The firm id is bound in as associated data, so a ciphertext copied into
another firm's row does not decrypt.
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from nexus.config import settings

VERSION = "v1"


class SecretError(RuntimeError):
    pass


def _key() -> bytes:
    raw = settings().secret_key
    if not raw:
        raise SecretError("NEXUS_SECRET_KEY is not set; it is needed to store AI provider keys.")
    try:
        key = base64.b64decode(raw)
    except ValueError as exc:
        raise SecretError("NEXUS_SECRET_KEY must be base64.") from exc
    if len(key) != 32:
        raise SecretError("NEXUS_SECRET_KEY must decode to 32 bytes (openssl rand -base64 32).")
    return key


def encrypt(plaintext: str, firm_id: str) -> str:
    nonce = os.urandom(12)
    sealed = AESGCM(_key()).encrypt(nonce, plaintext.encode(), firm_id.encode())
    return f"{VERSION}:{base64.b64encode(nonce + sealed).decode()}"


def decrypt(token: str, firm_id: str) -> str:
    version, _, body = token.partition(":")
    if version != VERSION:
        raise SecretError(f"Unknown key format {version!r}.")
    data = base64.b64decode(body)
    return AESGCM(_key()).decrypt(data[:12], data[12:], firm_id.encode()).decode()


def last4(plaintext: str) -> str:
    return plaintext[-4:] if len(plaintext) >= 8 else ""
