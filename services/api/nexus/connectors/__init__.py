"""Connectors: one module per external system Nexus reads."""

from nexus.connectors.base import Connector, ConnectorResult
from nexus.connectors.spec import (
    Category,
    ConnectionField,
    ConnectionTestResult,
    ConnectorSpec,
    FieldType,
    redact,
)

__all__ = [
    "Category",
    "ConnectionField",
    "ConnectionTestResult",
    "Connector",
    "ConnectorResult",
    "ConnectorSpec",
    "FieldType",
    "redact",
]
