"""File storage for uploaded documents and generated files.

Files are stored under a firm-scoped key. The local-disk backend is what runs
in development; a production deployment swaps in object storage with the same
three calls (see docs/technical/deployment.md).
"""

from pathlib import Path
from uuid import UUID, uuid4

from nexus.config import settings


def _path(key: str) -> Path:
    root = settings().storage_dir.resolve()
    path = (root / key).resolve()
    if root not in path.parents:
        raise ValueError("storage key escapes the storage root")
    return path


def put(firm_id: UUID | str, kind: str, data: bytes, suffix: str = "") -> str:
    key = f"{firm_id}/{kind}/{uuid4().hex}{suffix}"
    path = _path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return key


def get(key: str) -> bytes:
    return _path(key).read_bytes()


def delete(key: str) -> None:
    _path(key).unlink(missing_ok=True)
