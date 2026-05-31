"""Bundle-index dispatch + schema-validated load helpers.

Per ADR/0003 §2: schema lookup is `(bundle_version, artifact_kind, discriminator)
→ schema_path`. Phase 0 reads the bundle's `_index.json` for the nested
`lookups[artifact_kind][discriminator] → schema_path` map (per Codex1 N2 arc
20260531-1; matches the spike's existing nested shape).

Per ADR/0023 + ADR/0025 disposition: "JSON Schema validation at every read." The
load_*_validated helpers are the single entry points for read paths.

Bundle-aware per Codex1 N3 arc 20260531-1: every function takes a `bundle_dir`
argument so Phase 1+ extensions to historical-bundle support stay open.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from ..truth_model.manifest import load_manifest, manifest_path
from ..truth_model.reservation import load_reservation, reservation_path
from ..truth_model.revision import load_revision, revision_path
from ..truth_model.sidecar import load_sidecar, working_sidecar_path
from .profile import load_yaml


class SchemaValidationError(ValueError):
    """JSON Schema validation failure or bundle-index lookup miss."""


def packaged_bundle_dir(version: str = "0.19.0") -> Path:
    """Return the path to a bundle directory packaged inside aiadra_core."""
    return Path(__file__).parent.parent / "schemas" / f"v{version}"


@lru_cache(maxsize=8)
def _load_index(bundle_dir_str: str) -> dict[str, Any]:
    p = Path(bundle_dir_str) / "_index.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_index(bundle_dir: Path) -> dict[str, Any]:
    return _load_index(str(bundle_dir))


@lru_cache(maxsize=128)
def _load_schema(bundle_dir_str: str, rel_path: str) -> dict[str, Any]:
    return json.loads((Path(bundle_dir_str) / rel_path).read_text(encoding="utf-8"))


def resolve_schema_path(
    bundle_dir: Path, artifact_kind: str, discriminator: str
) -> str:
    """Resolve `(artifact_kind, discriminator) → schema_path` via _index.json
    `lookups` map. Raises SchemaValidationError on lookup miss.
    """
    index = load_index(bundle_dir)
    lookups = index.get("lookups", {})
    if artifact_kind not in lookups:
        raise SchemaValidationError(
            f"Bundle {index.get('bundle_version')!r} has no lookups for "
            f"artifact_kind={artifact_kind!r}"
        )
    by_disc = lookups[artifact_kind]
    if discriminator not in by_disc:
        raise SchemaValidationError(
            f"Bundle {index.get('bundle_version')!r} has no schema for "
            f"(artifact_kind={artifact_kind!r}, discriminator={discriminator!r})"
        )
    return by_disc[discriminator]


def resolve_schema(bundle_dir: Path, artifact_kind: str, discriminator: str) -> dict[str, Any]:
    rel = resolve_schema_path(bundle_dir, artifact_kind, discriminator)
    return _load_schema(str(bundle_dir), rel)


@lru_cache(maxsize=8)
def _build_registry(bundle_dir_str: str) -> Registry:
    """Pre-load every bundle schema into a referencing.Registry keyed by URI.

    Per Codex2 B2 absorption arc 20260531-1: migrated from the deprecated
    `jsonschema.RefResolver` (jsonschema 4.18+) to the canonical
    `referencing.Registry`. The Registry resolves cross-schema $refs
    in-memory and supports both relative refs (resolved against the
    validating schema's URI) and absolute URIs.
    """
    bundle_dir = Path(bundle_dir_str)
    resources: list[tuple[str, Resource]] = []
    for p in bundle_dir.rglob("*.json"):
        if p.name in ("_index.json", "_digest.json"):
            continue
        contents = json.loads(p.read_text(encoding="utf-8"))
        uri = p.resolve().as_uri()
        resource = Resource.from_contents(contents, default_specification=DRAFT202012)
        resources.append((uri, resource))
    return Registry().with_resources(resources)


def validate_against_schema(
    artifact: dict[str, Any], bundle_dir: Path, artifact_kind: str, discriminator: str
) -> None:
    """Schema-validate an in-memory artifact against the bundle-resolved schema.

    Per Codex2 B2 absorption: uses referencing.Registry; injects the schema's
    file URI as `$id` so relative `$ref`s (e.g. `_base.schema.json` from a
    per-event-type schema, or `../_shared/attachment_record.schema.json` from
    an Object schema) resolve against the registry.
    """
    rel = resolve_schema_path(bundle_dir, artifact_kind, discriminator)
    schema = _load_schema(str(bundle_dir), rel)
    schema_uri = (bundle_dir / rel).resolve().as_uri()
    # Inject $id matching the bundle path so relative $refs have a base URI
    # the validator + registry can resolve against. The cached schema dict is
    # not mutated — we shallow-copy + add $id for this validation call.
    schema_with_id = {"$id": schema_uri, **schema}
    registry = _build_registry(str(bundle_dir))
    validator = Draft202012Validator(schema_with_id, registry=registry)
    errors = sorted(validator.iter_errors(artifact), key=lambda e: str(e.path))
    if errors:
        msgs = [
            f"{'/'.join(str(p) for p in e.absolute_path)}: {e.message}"
            for e in errors
        ]
        raise SchemaValidationError(
            f"Schema validation failed against {rel} "
            f"(artifact_kind={artifact_kind!r}, discriminator={discriminator!r}):\n  - "
            + "\n  - ".join(msgs)
        )


# ---------------- validated load helpers ----------------


def load_sidecar_validated(
    workspace: Path, obj_uuid: str | UUID, bundle_dir: Path
) -> dict[str, Any]:
    data = load_sidecar(workspace, obj_uuid)
    if not isinstance(data, dict) or "object" not in data or "type" not in data.get("object", {}):
        raise SchemaValidationError(
            f"{working_sidecar_path(workspace, obj_uuid)}: not a sidecar (missing object.type)"
        )
    obj_type = data["object"]["type"]
    validate_against_schema(data, bundle_dir, "sidecar", obj_type)
    return data


def load_revision_validated(
    workspace: Path, obj_uuid: str | UUID, rev_id: str | UUID, bundle_dir: Path
) -> dict[str, Any]:
    data = load_revision(workspace, obj_uuid, rev_id)
    if not isinstance(data, dict) or "object" not in data or "type" not in data.get("object", {}):
        raise SchemaValidationError(
            f"{revision_path(workspace, obj_uuid, rev_id)}: not a Revision (missing object.type)"
        )
    obj_type = data["object"]["type"]
    validate_against_schema(data, bundle_dir, "revision", obj_type)
    return data


def load_reservation_validated(
    workspace: Path, prefix: str, bundle_dir: Path
) -> dict[str, Any]:
    data = load_reservation(workspace, prefix)
    validate_against_schema(data, bundle_dir, "reservation", prefix)
    return data


def load_manifest_validated(
    workspace: Path, release_label: str, bundle_dir: Path
) -> dict[str, Any]:
    data = load_manifest(workspace, release_label)
    manifest_type = data.get("manifest_type", "release")
    validate_against_schema(data, bundle_dir, "manifest", manifest_type)
    return data


def load_arbitrary_yaml_validated(
    path: Path, bundle_dir: Path, artifact_kind: str, discriminator: str
) -> dict[str, Any]:
    """Load + validate any YAML file by explicit (artifact_kind, discriminator)."""
    data = load_yaml(path)
    validate_against_schema(data, bundle_dir, artifact_kind, discriminator)
    return data


def validate_event(event: dict[str, Any], bundle_dir: Path) -> None:
    """Validate a single event against its per-event-type schema.

    Phase 0 splits the spike's single-file event.schema.json `oneOf` into
    per-event-type files. Dispatch by `event.event_type` per the bundle's
    `lookups.event[<event_type>]` namespace.
    """
    if not isinstance(event, dict) or "event_type" not in event:
        raise SchemaValidationError(
            f"Event missing event_type: {event!r}"
        )
    et = event["event_type"]
    validate_against_schema(event, bundle_dir, "event", et)
