"""Connection specifications.

Every connector declares the credentials it needs as typed fields. The UI renders
its configuration form from this declaration rather than hard-coding a form per
platform, and the API validates against it, so adding a platform is one spec plus
one connector — never a change to the form layer.

Secret handling is a property of the spec, not of the caller's discipline: a field
marked ``SECRET`` is redacted by ``redact`` and must never be returned by an API
response, written to a log, or included in an error message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FieldType(StrEnum):
    """How the UI should render a configuration field."""

    TEXT = "text"
    SECRET = "secret"
    NUMBER = "number"
    SELECT = "select"
    TEXTAREA = "textarea"
    BOOLEAN = "boolean"


class Category(StrEnum):
    """Groups platforms in the connections UI."""

    WAREHOUSE = "warehouse"
    LAKEHOUSE = "lakehouse"
    TRANSFORMATION = "transformation"
    ORCHESTRATION = "orchestration"
    VERSION_CONTROL = "version_control"
    LINEAGE = "lineage"
    DATABASE = "database"


@dataclass(frozen=True, slots=True)
class ConnectionField:
    """One credential or setting a connector needs."""

    name: str
    label: str
    type: FieldType = FieldType.TEXT
    required: bool = True
    help: str | None = None
    placeholder: str | None = None
    #: Allowed values when type is SELECT.
    options: tuple[str, ...] = ()
    default: str | None = None

    @property
    def is_secret(self) -> bool:
        return self.type is FieldType.SECRET


@dataclass(frozen=True, slots=True)
class ConnectorSpec:
    """Everything the UI and API need to configure one platform."""

    id: str
    name: str
    category: Category
    description: str
    fields: tuple[ConnectionField, ...]
    #: Python package required to talk to this platform, if any. Connectors are
    #: optional extras so a deployment only installs drivers it actually uses.
    driver_package: str | None = None
    docs_url: str | None = None
    #: False while a connector has not yet been exercised against a real account.
    verified: bool = False

    def secret_fields(self) -> frozenset[str]:
        return frozenset(f.name for f in self.fields if f.is_secret)

    def required_fields(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields if f.required)

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Return human-readable problems with a configuration, empty if valid.

        Errors name the field's label rather than its key, because this text is
        shown directly to whoever is filling in the form.
        """
        problems: list[str] = []
        by_name = {f.name: f for f in self.fields}

        for spec_field in self.fields:
            value = config.get(spec_field.name)
            missing = value is None or (isinstance(value, str) and not value.strip())
            if spec_field.required and missing:
                problems.append(f"{spec_field.label} is required")
                continue
            if missing:
                continue
            if spec_field.type is FieldType.NUMBER and not str(value).strip().isdigit():
                problems.append(f"{spec_field.label} must be a number")
            if spec_field.options and str(value) not in spec_field.options:
                allowed = ", ".join(spec_field.options)
                problems.append(f"{spec_field.label} must be one of: {allowed}")

        for key in config:
            if key not in by_name:
                problems.append(f"unknown field {key!r}")

        return problems


#: Placeholder shown in place of any secret value.
REDACTED = "••••••••"


def redact(spec: ConnectorSpec, config: dict[str, Any]) -> dict[str, Any]:
    """Return a copy safe to log or return over the API.

    Secrets are replaced rather than removed so the caller can still see that a
    value is present — "configured" and "missing" are different states, and a UI
    that cannot distinguish them will ask users to re-enter working credentials.
    """
    secrets = spec.secret_fields()
    return {
        key: (REDACTED if key in secrets and value else value)
        for key, value in config.items()
    }


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    """The outcome of probing a configured connection.

    ``details`` carries evidence the connection genuinely worked — a server
    version, a table count — so a green tick means something was actually read,
    not merely that a socket opened. It must never contain credentials.
    """

    ok: bool
    message: str
    details: dict[str, str] = field(default_factory=dict)

    @classmethod
    def success(cls, message: str, **details: str) -> ConnectionTestResult:
        return cls(ok=True, message=message, details=details)

    @classmethod
    def failure(cls, message: str, **details: str) -> ConnectionTestResult:
        return cls(ok=False, message=message, details=details)
