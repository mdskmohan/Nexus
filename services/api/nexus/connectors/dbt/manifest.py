"""dbt manifest reader.

``manifest.json`` is the highest-leverage artifact in the whole estate: it is a
file on disk, needs no credentials, and describes the full model DAG, every
model's SQL, its tests, its declared freshness, and its column documentation.
Parsing it recovers most of the environment graph before we authenticate to
anything.

What it deliberately does NOT contain: when anything runs (that is the
orchestrator's business), who is on call, or what actually happened on the last
run. A graph built from dbt alone is therefore structurally complete and
operationally blind, which is why the Airflow connector exists.

Supports manifest schema v7 onward (dbt 1.3+). Unknown fields are ignored
rather than rejected, because dbt adds keys in minor releases and a hard failure
on an unrecognised manifest would take the product down on a customer upgrade.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nexus.connectors.base import ConnectorResult
from nexus.errors import NexusError
from nexus.graph.entities import Edge, EdgeKind, Node, NodeKind

SYSTEM = "dbt"

#: Minimum manifest schema version we can read. Below this the node shape differs
#: enough that silently misparsing is a real risk.
_MIN_SCHEMA_VERSION = 7

#: dbt expresses freshness as {"count": 6, "period": "hour"}.
_PERIOD_SECONDS = {"minute": 60, "hour": 3600, "day": 86400}


class ManifestError(NexusError):
    """The manifest could not be read or is too old to interpret safely."""


def _namespaced(unique_id: str) -> str:
    """Namespace a dbt unique_id so it cannot collide with another system's."""
    return f"{SYSTEM}:{unique_id}"


def _schema_version(manifest: dict[str, Any]) -> int:
    """Extract the integer schema version from the manifest metadata URL.

    dbt records it as a URL ending in ``.../manifest/v12.json``.
    """
    raw = manifest.get("metadata", {}).get("dbt_schema_version", "")
    tail = raw.rstrip(".json").rsplit("/v", 1)
    if len(tail) != 2 or not tail[1].isdigit():
        raise ManifestError(f"could not determine manifest schema version from {raw!r}")
    return int(tail[1])


def _freshness_seconds(spec: dict[str, Any] | None) -> int | None:
    """Convert a dbt freshness threshold to seconds, or None if unset."""
    if not spec:
        return None
    period = spec.get("period")
    count = spec.get("count")
    if period not in _PERIOD_SECONDS or not isinstance(count, int):
        return None
    return count * _PERIOD_SECONDS[period]


class DbtManifestConnector:
    """Reads a dbt ``manifest.json`` into graph entities."""

    system = SYSTEM

    def __init__(self, manifest_path: Path | str) -> None:
        self.manifest_path = Path(manifest_path)

    def collect(self) -> ConnectorResult:
        """Parse the manifest and emit every node and edge it describes."""
        manifest = self._load()
        version = _schema_version(manifest)
        if version < _MIN_SCHEMA_VERSION:
            raise ManifestError(
                f"manifest schema v{version} is older than the supported minimum "
                f"v{_MIN_SCHEMA_VERSION}; refusing to guess at its shape"
            )

        result = ConnectorResult()
        self._collect_sources(manifest, result)
        self._collect_nodes(manifest, result)
        self._collect_exposures(manifest, result)
        self._warn_on_dangling_edges(result)
        return result

    def _load(self) -> dict[str, Any]:
        try:
            with self.manifest_path.open() as fh:
                loaded: Any = json.load(fh)
        except FileNotFoundError as exc:
            raise ManifestError(f"no manifest at {self.manifest_path}") from exc
        except json.JSONDecodeError as exc:
            raise ManifestError(f"manifest at {self.manifest_path} is not valid JSON: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ManifestError("manifest root must be an object")
        return loaded

    def _collect_sources(self, manifest: dict[str, Any], result: ConnectorResult) -> None:
        """Emit a node per declared source, carrying its freshness policy."""
        for unique_id, src in manifest.get("sources", {}).items():
            freshness = src.get("freshness") or {}
            warn = _freshness_seconds(freshness.get("warn_after"))
            error = _freshness_seconds(freshness.get("error_after"))

            attributes: dict[str, str] = {
                "source_name": str(src.get("source_name", "")),
                "identifier": str(src.get("identifier") or src.get("name", "")),
                "database": str(src.get("database") or ""),
                "schema": str(src.get("schema") or ""),
            }
            if warn is not None:
                attributes["freshness_warn_seconds"] = str(warn)
            if error is not None:
                attributes["freshness_error_seconds"] = str(error)
            if loaded_at := src.get("loaded_at_field"):
                attributes["loaded_at_field"] = str(loaded_at)
            else:
                # Without this column dbt cannot evaluate freshness at all, so a
                # declared policy here is decorative — worth surfacing.
                if warn or error:
                    result.warnings.append(
                        f"source {unique_id} declares freshness but has no loaded_at_field; "
                        "the policy cannot be evaluated"
                    )

            result.nodes.append(
                Node(
                    id=_namespaced(unique_id),
                    kind=NodeKind.SOURCE,
                    name=f"{src.get('source_name', '')}.{src.get('name', '')}".strip("."),
                    system=SYSTEM,
                    attributes=attributes,
                )
            )

    def _collect_nodes(self, manifest: dict[str, Any], result: ConnectorResult) -> None:
        """Emit models and tests, plus their dependency edges."""
        for unique_id, node in manifest.get("nodes", {}).items():
            resource_type = node.get("resource_type")

            if resource_type in ("model", "snapshot", "seed"):
                config = node.get("config") or {}
                attributes = {
                    "materialized": str(config.get("materialized") or "view"),
                    "database": str(node.get("database") or ""),
                    "schema": str(node.get("schema") or ""),
                    "resource_type": str(resource_type),
                }
                # raw_code is the authored SQL; compiled_code only exists after a
                # run, so it is recorded when present but never required.
                if raw := node.get("raw_code"):
                    attributes["raw_code"] = str(raw)
                if compiled := node.get("compiled_code"):
                    attributes["compiled_code"] = str(compiled)
                if desc := node.get("description"):
                    attributes["description"] = str(desc)
                if owner := (node.get("meta") or {}).get("owner"):
                    attributes["owner"] = str(owner)

                result.nodes.append(
                    Node(
                        id=_namespaced(unique_id),
                        kind=NodeKind.MODEL,
                        name=str(node.get("name", unique_id)),
                        system=SYSTEM,
                        attributes=attributes,
                    )
                )
                self._emit_dependencies(unique_id, node, result, EdgeKind.DEPENDS_ON)

            elif resource_type == "test":
                meta = node.get("test_metadata") or {}
                attributes = {"test_name": str(meta.get("name") or "custom")}
                if column := (meta.get("kwargs") or {}).get("column_name"):
                    attributes["column"] = str(column)

                result.nodes.append(
                    Node(
                        id=_namespaced(unique_id),
                        kind=NodeKind.TEST,
                        name=str(node.get("name", unique_id)),
                        system=SYSTEM,
                        attributes=attributes,
                    )
                )
                # A test edge points at what it asserts on, so a failing test
                # resolves directly to the node whose contract it guards.
                self._emit_dependencies(unique_id, node, result, EdgeKind.TESTS)

    def _collect_exposures(self, manifest: dict[str, Any], result: ConnectorResult) -> None:
        """Emit exposures as consumers.

        Exposures are how impact analysis reaches past the warehouse to a
        dashboard someone will notice is wrong.
        """
        for unique_id, exposure in manifest.get("exposures", {}).items():
            attributes = {"exposure_type": str(exposure.get("type") or "unknown")}
            owner = exposure.get("owner") or {}
            if name := (owner.get("name") or owner.get("email")):
                attributes["owner"] = str(name)
            if url := exposure.get("url"):
                attributes["url"] = str(url)

            result.nodes.append(
                Node(
                    id=_namespaced(unique_id),
                    kind=NodeKind.CONSUMER,
                    name=str(exposure.get("label") or exposure.get("name", unique_id)),
                    system=SYSTEM,
                    attributes=attributes,
                )
            )
            self._emit_dependencies(unique_id, exposure, result, EdgeKind.READS)

    def _emit_dependencies(
        self,
        unique_id: str,
        node: dict[str, Any],
        result: ConnectorResult,
        kind: EdgeKind,
    ) -> None:
        """Emit one edge per upstream node this entity depends on."""
        for parent in (node.get("depends_on") or {}).get("nodes", []):
            result.edges.append(
                Edge(source=_namespaced(parent), target=_namespaced(unique_id), kind=kind)
            )

    def _warn_on_dangling_edges(self, result: ConnectorResult) -> None:
        """Report edges pointing at nodes the manifest never defined.

        Ephemeral models and disabled nodes legitimately produce these. They are
        recorded rather than dropped silently, because a gap in the graph shows
        up later as a diagnosis that cannot explain itself.
        """
        known = {n.id for n in result.nodes}
        dangling = sorted({e.source for e in result.edges if e.source not in known})
        for node_id in dangling:
            result.warnings.append(f"edge references unknown node {node_id}")
