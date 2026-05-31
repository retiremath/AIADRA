"""Schema-validated load helpers — refactored to use BundleRegistry per ADR/0003 §7.

Per Codex2 B2 absorption (Phase 1 arc 20260531-2): every read-path validates the
artifact via its OWN `schema_version` (archival-aware) — the BundleRegistry
selects the matching packaged bundle. Pin verification still runs first
(`bundle_for_pin`); thereafter individual artifacts may validate against
older bundles than the project pin.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from ..truth_model.manifest import load_manifest, manifest_path
from ..truth_model.reservation import load_reservation, reservation_path
from ..truth_model.revision import load_revision, revision_path
from ..truth_model.sidecar import load_sidecar, working_sidecar_path
from .bundle_registry import (
    BundleHandle,
    BundleRegistry,
    SchemaValidationError,
)
from .profile import load_yaml

__all__ = [
    "SchemaValidationError",
    "BundleHandle",
    "BundleRegistry",
    "packaged_bundle_dir",  # Phase 0 back-compat alias
    "load_sidecar_validated",
    "load_revision_validated",
    "load_reservation_validated",
    "load_manifest_validated",
    "load_arbitrary_yaml_validated",
    "validate_event",
    "default_registry",
    "validate_against_schema",  # Phase 0 back-compat alias
    "load_index",  # Phase 0 back-compat alias
    "resolve_schema_path",  # Phase 0 back-compat alias
]


def load_index(bundle_dir: Path) -> dict[str, Any]:
    """Phase 0 back-compat. Loads `_index.json` from a bundle directory."""
    return json.loads((bundle_dir / "_index.json").read_text(encoding="utf-8"))


def resolve_schema_path(bundle_dir: Path, artifact_kind: str, discriminator: str) -> str:
    """Phase 0 back-compat. Resolves `(artifact_kind, discriminator) → schema_path`."""
    bundle = default_registry().bundle(load_index(bundle_dir)["bundle_version"])
    return bundle.resolve_schema_path(artifact_kind, discriminator)


@lru_cache(maxsize=1)
def default_registry() -> BundleRegistry:
    """Cached default BundleRegistry rooted at the packaged schemas/ dir."""
    return BundleRegistry()


def packaged_bundle_dir(version: str = "0.19.0") -> Path:
    """Phase 0 back-compat. Returns a packaged bundle's directory.

    Defaults to 0.19.0 to preserve Phase 0 test behavior. Phase 1+ code should
    use BundleRegistry directly.
    """
    return default_registry().bundle(version).bundle_dir


def _bundle_for_artifact(
    artifact: dict[str, Any], registry: BundleRegistry | None = None
) -> BundleHandle:
    """Resolve the artifact's schema_version → BundleHandle per ADR/0003 §7."""
    reg = registry or default_registry()
    sv = artifact.get("schema_version") or artifact.get("object", {}).get("schema_version")
    if not sv:
        raise SchemaValidationError(
            f"Artifact missing schema_version (top-level or object.schema_version): "
            f"cannot resolve archival bundle"
        )
    return reg.bundle_for_schema_version(sv)


# ---------------- validated load helpers ----------------


def load_sidecar_validated(
    workspace: Path, obj_uuid: str | UUID, bundle_dir: Path | None = None,
    registry: BundleRegistry | None = None,
) -> dict[str, Any]:
    """Load + Profile-lint + JSON-Schema-validate working sidecar.

    Per ADR/0003 §7: validates against the bundle matching the artifact's own
    `object.schema_version`. The `bundle_dir` parameter is retained for back-
    compat with Phase 0 call sites but is now derived from the registry.
    """
    data = load_sidecar(workspace, obj_uuid)
    if not isinstance(data, dict) or "object" not in data or "type" not in data.get("object", {}):
        raise SchemaValidationError(
            f"{working_sidecar_path(workspace, obj_uuid)}: not a sidecar (missing object.type)"
        )
    bundle = _bundle_for_artifact(data, registry)
    bundle.validate(data, "sidecar", data["object"]["type"])
    return data


def load_revision_validated(
    workspace: Path, obj_uuid: str | UUID, rev_id: str | UUID,
    bundle_dir: Path | None = None, registry: BundleRegistry | None = None,
) -> dict[str, Any]:
    data = load_revision(workspace, obj_uuid, rev_id)
    if not isinstance(data, dict) or "object" not in data or "type" not in data.get("object", {}):
        raise SchemaValidationError(
            f"{revision_path(workspace, obj_uuid, rev_id)}: not a Revision (missing object.type)"
        )
    bundle = _bundle_for_artifact(data, registry)
    bundle.validate(data, "revision", data["object"]["type"])
    return data


def load_reservation_validated(
    workspace: Path, prefix: str,
    bundle_dir: Path | None = None, registry: BundleRegistry | None = None,
) -> dict[str, Any]:
    data = load_reservation(workspace, prefix)
    bundle = _bundle_for_artifact(data, registry)
    bundle.validate(data, "reservation", prefix)
    return data


def load_manifest_validated(
    workspace: Path, release_label: str,
    bundle_dir: Path | None = None, registry: BundleRegistry | None = None,
) -> dict[str, Any]:
    data = load_manifest(workspace, release_label)
    bundle = _bundle_for_artifact(data, registry)
    bundle.validate(data, "manifest", data.get("manifest_type", "release"))
    return data


def load_arbitrary_yaml_validated(
    path: Path, bundle_dir: Path | None = None, artifact_kind: str | None = None,
    discriminator: str | None = None, registry: BundleRegistry | None = None,
) -> dict[str, Any]:
    """Load + validate any YAML by explicit (artifact_kind, discriminator).

    Used for one-off validation; resolves bundle via artifact's own schema_version.
    """
    data = load_yaml(path)
    if artifact_kind is None or discriminator is None:
        raise SchemaValidationError("artifact_kind and discriminator required for arbitrary YAML validation")
    bundle = _bundle_for_artifact(data, registry)
    bundle.validate(data, artifact_kind, discriminator)
    return data


def validate_event(
    event: dict[str, Any], bundle_dir: Path | None = None,
    registry: BundleRegistry | None = None,
) -> None:
    """Validate a single event against its per-event-type schema.

    Per ADR/0003 §7: uses the bundle matching the event's own `schema_version`.
    Phase 0's bundle_dir argument is retained for back-compat (ignored).
    """
    if not isinstance(event, dict) or "event_type" not in event:
        raise SchemaValidationError(f"Event missing event_type: {event!r}")
    bundle = _bundle_for_artifact(event, registry)
    bundle.validate(event, "event", event["event_type"])


def validate_against_schema(
    artifact: dict[str, Any], bundle_dir: Path | None = None,
    artifact_kind: str = "", discriminator: str = "",
    registry: BundleRegistry | None = None,
) -> None:
    """Phase 0 back-compat wrapper. Phase 1+ code should call BundleHandle.validate directly."""
    bundle = _bundle_for_artifact(artifact, registry)
    bundle.validate(artifact, artifact_kind, discriminator)
