"""API request and response models.

These are the contract the web client codes against. Secrets travel *in* on
requests and never travel *out*: no response model here carries a secret field,
which is enforced by construction rather than by remembering to strip them.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nexus.connectors.spec import ConnectorSpec


class FieldSchema(BaseModel):
    """One configuration field, as the UI needs to render it."""

    model_config = ConfigDict(frozen=True)

    name: str
    label: str
    type: str
    required: bool
    help: str | None = None
    placeholder: str | None = None
    options: list[str] = Field(default_factory=list)
    default: str | None = None


class ConnectorSchema(BaseModel):
    """One platform available to connect to."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    category: str
    description: str
    docs_url: str | None = None
    #: False when this connector has not yet been exercised against a real account.
    verified: bool
    #: False when the server lacks the driver, which is a different problem from
    #: bad credentials and needs a different message in the UI.
    driver_available: bool
    driver_package: str | None = None
    fields: list[FieldSchema]

    @classmethod
    def from_spec(cls, spec: ConnectorSpec, driver_available: bool) -> ConnectorSchema:
        return cls(
            id=spec.id,
            name=spec.name,
            category=spec.category.value,
            description=spec.description,
            docs_url=spec.docs_url,
            verified=spec.verified,
            driver_available=driver_available,
            driver_package=spec.driver_package,
            fields=[
                FieldSchema(
                    name=f.name,
                    label=f.label,
                    type=f.type.value,
                    required=f.required,
                    help=f.help,
                    placeholder=f.placeholder,
                    options=list(f.options),
                    default=f.default,
                )
                for f in spec.fields
            ],
        )


class ConnectionTestRequest(BaseModel):
    """A configuration to probe. Carries secrets; never logged, never echoed."""

    connector_id: str
    config: dict[str, Any]


class ConnectionTestResponse(BaseModel):
    """The outcome of a probe.

    ``details`` carries evidence that something was genuinely read — a version, a
    table count — so a pass means more than "a socket opened".
    """

    model_config = ConfigDict(frozen=True)

    ok: bool
    message: str
    details: dict[str, str] = Field(default_factory=dict)
