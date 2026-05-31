"""Bundle registry per ADR/0003 §7 archival-read + project-pin write discipline.

Per Codex1 B2 + Codex2 retraction arc 20260531-2: replaces Phase 0's single-bundle
`packaged_bundle_dir()` shortcut. Phase 1 ships both v0.19.0 + v0.20.0 bundles
side-by-side; read-path validates each artifact via its own `schema_version`;
write-path uses the project-pinned bundle.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .profile import load_yaml


class SchemaValidationError(ValueError):
    """JSON Schema validation failure or bundle-index lookup miss."""


class BundleNotFoundError(KeyError):
    """No packaged bundle matches the requested version."""


class BundleDigestMismatchError(ValueError):
    """Project-pinned bundle_digest does not match the packaged bundle's digest."""


@dataclass
class BundleHandle:
    """One packaged bundle. Pre-built referencing.Registry attached."""
    bundle_version: str
    bundle_dir: Path
    bundle_digest: str
    index: dict[str, Any]
    registry: Registry

    def resolve_schema_path(self, artifact_kind: str, discriminator: str) -> str:
        lookups = self.index.get("lookups", {})
        if artifact_kind not in lookups:
            raise SchemaValidationError(
                f"Bundle {self.bundle_version!r} has no lookups for "
                f"artifact_kind={artifact_kind!r}"
            )
        by_disc = lookups[artifact_kind]
        if discriminator not in by_disc:
            raise SchemaValidationError(
                f"Bundle {self.bundle_version!r} has no schema for "
                f"(artifact_kind={artifact_kind!r}, discriminator={discriminator!r})"
            )
        return by_disc[discriminator]

    def schema(self, artifact_kind: str, discriminator: str) -> dict[str, Any]:
        rel = self.resolve_schema_path(artifact_kind, discriminator)
        return json.loads((self.bundle_dir / rel).read_text(encoding="utf-8"))

    def validate(
        self, artifact: dict[str, Any], artifact_kind: str, discriminator: str
    ) -> None:
        """Schema-validate an in-memory artifact against the bundle-resolved schema.

        Carries Phase 0 schema.py pattern: inject $id matching the schema's file URI
        so relative $refs resolve through the bundle Registry.
        """
        rel = self.resolve_schema_path(artifact_kind, discriminator)
        schema = json.loads((self.bundle_dir / rel).read_text(encoding="utf-8"))
        schema_uri = (self.bundle_dir / rel).resolve().as_uri()
        schema_with_id = {"$id": schema_uri, **schema}
        validator = Draft202012Validator(schema_with_id, registry=self.registry)
        errors = sorted(validator.iter_errors(artifact), key=lambda e: str(e.path))
        if errors:
            msgs = [
                f"{'/'.join(str(p) for p in e.absolute_path)}: {e.message}"
                for e in errors
            ]
            raise SchemaValidationError(
                f"Schema validation failed against {rel} (bundle {self.bundle_version}, "
                f"artifact_kind={artifact_kind!r}, discriminator={discriminator!r}):\n  - "
                + "\n  - ".join(msgs)
            )


def _compute_bundle_digest(bundle_dir: Path) -> str:
    """Canonical SHA-256 over all bundle JSON files (sorted-relative-path)."""
    h = hashlib.sha256()
    files: list[Path] = []
    for p in bundle_dir.rglob("*.json"):
        rel = p.relative_to(bundle_dir).as_posix()
        if rel == "_digest.json":
            continue
        if rel.startswith("."):
            continue
        files.append(p)
    for p in sorted(files, key=lambda f: f.relative_to(bundle_dir).as_posix()):
        rel = p.relative_to(bundle_dir).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(p.read_bytes())
        h.update(b"\x00")
    return f"sha256:{h.hexdigest()}"


def _build_registry_for_bundle(bundle_dir: Path) -> Registry:
    resources: list[tuple[str, Resource]] = []
    for p in bundle_dir.rglob("*.json"):
        if p.name in ("_index.json", "_digest.json"):
            continue
        contents = json.loads(p.read_text(encoding="utf-8"))
        uri = p.resolve().as_uri()
        resource = Resource.from_contents(contents, default_specification=DRAFT202012)
        resources.append((uri, resource))
    return Registry().with_resources(resources)


@lru_cache(maxsize=1)
def _default_schemas_root() -> Path:
    return Path(__file__).parent.parent / "schemas"


class BundleRegistry:
    """Multi-bundle resolver per ADR/0003 §7.

    Pre-loads every packaged bundle. Provides:
    - `bundle(version)` — return a BundleHandle by version
    - `bundle_for_pin(workspace)` — load `.aiadra/schemas.yaml`; verify digest; return BundleHandle
    - `bundle_for_schema_version(schema_version)` — return BundleHandle for archival read
    - `versions()` — list packaged bundle versions
    - `default_write_bundle()` — set explicitly via constructor or pin
    """

    def __init__(self, schemas_root: Path | None = None) -> None:
        self.schemas_root = schemas_root or _default_schemas_root()
        self._bundles: dict[str, BundleHandle] = {}
        if not self.schemas_root.exists():
            return
        for vdir in sorted(self.schemas_root.iterdir()):
            if not vdir.is_dir() or not vdir.name.startswith("v"):
                continue
            try:
                index_path = vdir / "_index.json"
                if not index_path.exists():
                    continue
                index = json.loads(index_path.read_text(encoding="utf-8"))
                version = index["bundle_version"]
                registry = _build_registry_for_bundle(vdir)
                digest = _compute_bundle_digest(vdir)
                self._bundles[version] = BundleHandle(
                    bundle_version=version,
                    bundle_dir=vdir,
                    bundle_digest=digest,
                    index=index,
                    registry=registry,
                )
            except (KeyError, json.JSONDecodeError):
                continue

    def versions(self) -> list[str]:
        return sorted(self._bundles.keys())

    def bundle(self, version: str) -> BundleHandle:
        if version not in self._bundles:
            raise BundleNotFoundError(
                f"No packaged bundle v{version}; available: {self.versions()}"
            )
        return self._bundles[version]

    def bundle_for_schema_version(self, schema_version: str) -> BundleHandle:
        """Per ADR/0003 §7 archival-mode: artifact's own schema_version selects bundle."""
        return self.bundle(schema_version)

    def bundle_for_pin(self, workspace: Path) -> BundleHandle:
        """Load `.aiadra/schemas.yaml`; verify digest; return BundleHandle.

        Raises FileNotFoundError if pin missing; BundleNotFoundError if pin
        names an unknown bundle; BundleDigestMismatchError on digest mismatch.
        """
        pin_path = workspace / ".aiadra" / "schemas.yaml"
        if not pin_path.exists():
            raise FileNotFoundError(
                f"Project pin missing: {pin_path}. Production workspaces MUST carry "
                f".aiadra/schemas.yaml per ADR/0003 §9."
            )
        pin = load_yaml(pin_path)
        pinned_version = pin["bundle_version"]
        pinned_digest = pin["bundle_digest"]
        bundle = self.bundle(pinned_version)
        if bundle.bundle_digest != pinned_digest:
            raise BundleDigestMismatchError(
                f"Bundle digest mismatch for {pinned_version}: "
                f"pinned {pinned_digest}, actual {bundle.bundle_digest}"
            )
        return bundle

    def latest(self) -> BundleHandle:
        """Return highest-version bundle (default write bundle for fresh inits)."""
        if not self._bundles:
            raise BundleNotFoundError("No packaged bundles found")
        latest_v = sorted(self._bundles.keys(), key=lambda v: tuple(int(x) for x in v.split(".")))[-1]
        return self._bundles[latest_v]
