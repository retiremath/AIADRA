"""Layer-2 validator subset for Wedge-001: schema validation, satisfies check,
fold invariant, schema-validated load helpers.

Per [ADR/0001 §4] sidecar/event invariant. Per [ADR/0002 §1] + [ADR/0023 §3]
JSON Schema validation at every read.

Spike-local threshold parsing: per Codex1 B2 absorption, the canonical
ADR/0006 Requirement schema does NOT carry threshold-expression primitives;
the spike validator parses acceptance_criterion.criterion.text using a
spike-local regex convention to derive the threshold check. Production-grade
would need either a Schema Change Note adding canonical threshold-expression
primitives OR a richer criterion DSL. Documented in FRICTION_LOG.md.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterator

from jsonschema import Draft202012Validator, RefResolver

from .sidecar import load_yaml


class SchemaValidationError(ValueError):
    pass


class FoldInconsistencyError(ValueError):
    pass


class IntegrityError(ValueError):
    pass


SCHEMA_DIR = Path(__file__).parent / "schemas"
_BUNDLE_CACHE: dict[str, Any] = {}


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _bundle() -> dict[str, Any]:
    if "data" not in _BUNDLE_CACHE:
        _BUNDLE_CACHE["data"] = _load_schema("_bundle_v0.19.0.json")
    return _BUNDLE_CACHE["data"]


def _schema_path_from_bundle(artifact_kind: str, discriminator: str) -> str:
    """Resolve `(artifact_kind, discriminator) -> schema_path` via bundle index.

    Per [ADR/0003 §2]. Spike-grade: ignores bundle_version since the spike runs
    at exactly one version (0.19.0).
    """
    lookups = _bundle()["lookups"]
    if artifact_kind not in lookups:
        raise SchemaValidationError(f"Bundle has no lookup for artifact_kind={artifact_kind!r}")
    by_disc = lookups[artifact_kind]
    if discriminator not in by_disc:
        raise SchemaValidationError(
            f"Bundle has no schema for (artifact_kind={artifact_kind!r}, discriminator={discriminator!r})"
        )
    return by_disc[discriminator]


def _resolver() -> RefResolver:
    base_uri = SCHEMA_DIR.resolve().as_uri() + "/"
    return RefResolver(base_uri=base_uri, referrer={})


def validate_against_schema(artifact: dict[str, Any], schema_name: str) -> None:
    schema = _load_schema(schema_name)
    validator = Draft202012Validator(schema, resolver=_resolver())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: str(e.path))
    if errors:
        msgs = [f"{'/'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in errors]
        raise SchemaValidationError(
            f"Schema validation failed against {schema_name}:\n  - " + "\n  - ".join(msgs)
        )


# ---------------- schema-validated load helpers (per Codex2 B3) ----------------


def load_sidecar_validated(path: Path) -> dict[str, Any]:
    """Load + Profile-lint + JSON-Schema-validate a Part or Requirement sidecar.

    Picks the right schema from the bundle index via the `(sidecar, <Type>)`
    lookup. Validates the loaded artifact. Raises SchemaValidationError on
    any violation. Used by every spike read path per [ADR/0002 §1] +
    [ADR/0023 §3] "JSON Schema validation at every read".
    """
    data = load_yaml(path)
    if not isinstance(data, dict) or "object" not in data or "type" not in data.get("object", {}):
        raise SchemaValidationError(f"{path}: not a sidecar (missing object.type)")
    obj_type = data["object"]["type"]
    schema_name = _schema_path_from_bundle("sidecar", obj_type)
    validate_against_schema(data, schema_name)
    return data


def load_revision_validated(path: Path) -> dict[str, Any]:
    """Load + Profile-lint + schema-validate a Revision file.

    Spike-grade: revision and sidecar share schemas in the bundle index.
    """
    data = load_yaml(path)
    if not isinstance(data, dict) or "object" not in data or "type" not in data.get("object", {}):
        raise SchemaValidationError(f"{path}: not a Revision (missing object.type)")
    obj_type = data["object"]["type"]
    schema_name = _schema_path_from_bundle("revision", obj_type)
    validate_against_schema(data, schema_name)
    return data


def load_reservation_validated(path: Path, prefix: str) -> dict[str, Any]:
    """Load + Profile-lint + schema-validate a Reservation file."""
    data = load_yaml(path)
    schema_name = _schema_path_from_bundle("reservation", prefix)
    validate_against_schema(data, schema_name)
    return data


def load_manifest_validated(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    schema_name = _schema_path_from_bundle("manifest", "release")
    validate_against_schema(data, schema_name)
    return data


def validate_event(event: dict[str, Any]) -> None:
    """Validate a single event dict against event.schema.json."""
    validate_against_schema(event, "event.schema.json")


# ---------------- satisfies check (spike-local threshold parser) ----------------


_RE_THRESHOLD = re.compile(r"^(?P<param>[a-z][a-z0-9_]*)\s+shall be at least\s+(?P<value>-?\d+(?:\.\d+)?)\s*$")


def parse_threshold(criterion_text: str) -> tuple[str, float] | None:
    """Spike-local: extract (parameter_name, min_value) from criterion text.

    Returns None if text does not match the spike-local pattern. See
    FRICTION_LOG.md for the production-grade Schema-Change-Note candidate.
    """
    m = _RE_THRESHOLD.match(criterion_text)
    if not m:
        return None
    return m.group("param"), float(m.group("value"))


def validate_satisfies(part_sidecar: dict[str, Any], requirement_sidecar: dict[str, Any]) -> dict[str, Any]:
    """Check that the Part's parameters satisfy all spike-parseable acceptance criteria."""
    part_number = part_sidecar["object"]["number"]
    req_number = requirement_sidecar["object"]["number"]
    check_name = f"satisfies({part_number},{req_number})"

    params_by_name = {p["name"]: p["value"] for p in part_sidecar.get("parameter", [])}

    fails: list[str] = []
    passes: list[str] = []
    skipped: list[str] = []
    for ac in requirement_sidecar.get("acceptance_criterion", []):
        ac_id = ac["id"]
        text = ac["criterion"]["text"]
        parsed = parse_threshold(text)
        if parsed is None:
            skipped.append(f"{ac_id} (criterion text not spike-parseable: {text!r})")
            continue
        pname, threshold = parsed
        if pname not in params_by_name:
            fails.append(f"{ac_id}: parameter {pname!r} not present on Part")
            continue
        actual = params_by_name[pname]
        if actual >= threshold:
            passes.append(f"{ac_id} ({pname}={actual} >= {threshold})")
        else:
            fails.append(f"{ac_id} ({pname}={actual} < {threshold})")

    if fails:
        return {
            "check_name": check_name,
            "result": "FAIL",
            "details": "; ".join(fails),
        }
    detail_parts = []
    if passes:
        detail_parts.append("PASS: " + "; ".join(passes))
    if skipped:
        detail_parts.append("SKIPPED (spike-grade): " + "; ".join(skipped))
    return {
        "check_name": check_name,
        "result": "PASS",
        "details": " | ".join(detail_parts) if detail_parts else "no criteria",
    }


# ---------------- fold invariant ----------------


def validate_fold(workspace: Path) -> None:
    """Verify event-log fold matches on-disk working sidecars + each event
    validates against the event schema.

    Per [ADR/0001 §4]. Raises FoldInconsistencyError on sidecar mismatch and
    SchemaValidationError on any malformed event record.
    """
    from .event_log import fold_state, read_events

    # 1. Validate every event record on the way through
    for evt in read_events(workspace):
        validate_event(evt)

    # 2. Fold + compare
    folded = fold_state(workspace)
    rev_dir = workspace / "revisions"
    if not rev_dir.exists():
        if folded:
            raise FoldInconsistencyError(f"events derive {len(folded)} object(s); no revisions/ dir on disk")
        return
    for uuid, expected in folded.items():
        working_path = rev_dir / uuid / "working.yaml"
        if not working_path.exists():
            raise FoldInconsistencyError(f"events derive {uuid}; on-disk working.yaml missing at {working_path}")
        on_disk = load_sidecar_validated(working_path)
        if json.dumps(on_disk, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise FoldInconsistencyError(
                f"sidecar/event invariant violated for {uuid}: on-disk does not match event fold"
            )


# ---------------- release-time integrity check (per Codex2 B2) ----------------


def verify_revision_hashes(workspace: Path, revisions: list[dict[str, Any]]) -> None:
    """Re-read every Revision file, hash its bytes, verify the recorded
    revision_hash matches. Raises IntegrityError on mismatch.

    Spike-grade defence-in-depth on top of materialize_revision()'s
    hash-from-bytes guarantee, so reviewers can re-verify by running this
    helper independently.
    """
    from .transaction import revision_path

    for rev in revisions:
        rpath = revision_path(workspace, rev["object_uuid"], rev["revision_id"])
        actual = "sha256:" + hashlib.sha256(rpath.read_bytes()).hexdigest()
        if actual != rev["revision_hash"]:
            raise IntegrityError(
                f"Revision hash mismatch for {rev['object_number']}: "
                f"recorded {rev['revision_hash']}, actual {actual} at {rpath}"
            )
