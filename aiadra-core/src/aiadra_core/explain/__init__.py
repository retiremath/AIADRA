"""AIADRA Ring 2 ExplanationTree — structured representation of objects,
relationships, events, and validation errors.

Per [ADR/0026 §"Sequencing" Phase D](../../../Docs/ADR/0026-ai-action-protocol-scope.md):
"Structured validation-error tree replaces stringly-typed errors." One
representation, three consumers:

1. `protocol.explain(workspace, ref)` — object/relationship history walk.
2. `protocol.explain_failure(failure)` — failure-tree walk.
3. `audit` records — `validation_errors` field serializes `ExplanationNode`
   dicts (per ADR/0026 §9 "structured per Phase D's ExplanationTree shape").

Per Codex1 B4 absorption (arc 20260531-10): each `kind` value has a minimum
canonical detail-key set so JSONL audit records and CLI rendering stay
deterministic across versions. Factory functions enforce the contract.

Per Codex1 B1 absorption: `_classify_exception(e)` maps known exception
classes to the 6 `reason_classification` enum values from ADR/0026 §9
(schema_validation / profile_violation / fold_inconsistency /
binding_violation / release_consistency / other). Shared by `simulate()`'s
FAIL-outcome construction AND audit-record emission.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---- Canonical kind values + reason classifications -------------------------


KIND_OBJECT = "object"
KIND_RELATIONSHIP = "relationship"
KIND_EVENT = "event"
KIND_VALIDATION_ERROR = "validation_error"

# Per ADR/0026 §9 verbatim
REASON_CLASSIFICATIONS: frozenset[str] = frozenset({
    "schema_validation",
    "profile_violation",
    "fold_inconsistency",
    "binding_violation",
    "release_consistency",
    "other",
})


# ---- Frozen recursive dataclass --------------------------------------------


@dataclass(frozen=True)
class ExplanationNode:
    """One node in an `ExplanationTree`. Recursive via `children` tuple.

    Per Codex1 B4 absorption (arc 20260531-10): `details` carries a minimum
    canonical key set per `kind`:

      - `kind="object"`: `number`, `uuid`, `type`, `source` (one of
        `"working"` or `"released_revision"`).
      - `kind="relationship"`: `source_uuid`, `relationship_id`, `type`,
        `endpoints` (list of dicts with `object_uuid` + optional `revision_id`).
      - `kind="event"`: `event_id`, `event_type`, `timestamp`, `transaction_id`.
      - `kind="validation_error"`: `error_type`, `classification` (one of
        REASON_CLASSIFICATIONS), `check_name`, `message`.

    Additional keys allowed and forward-compatible; consumers MUST tolerate
    them. Use the factory functions below to construct instances with the
    canonical keys filled in.
    """
    kind: str
    ref: str
    label: str
    details: dict[str, Any]
    children: tuple["ExplanationNode", ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExplanationTree:
    """Top-level container — wraps a root `ExplanationNode` with bundle
    metadata. Frozen + serializable.
    """
    root: ExplanationNode
    bundle_version: str


# ---- Factory functions per Codex1 B4 ---------------------------------------


def object_node(
    *,
    number: str,
    uuid: str,
    type: str,
    source: str = "working",
    label: str | None = None,
    extra: dict[str, Any] | None = None,
    children: tuple[ExplanationNode, ...] = (),
) -> ExplanationNode:
    """Build an `ExplanationNode(kind="object")` with the canonical details
    per Codex1 B4. `source` must be one of `"working"` | `"released_revision"`."""
    if source not in ("working", "released_revision"):
        raise ValueError(
            f"object_node source must be 'working' or 'released_revision'; got {source!r}"
        )
    details: dict[str, Any] = {
        "number": number, "uuid": uuid, "type": type, "source": source,
    }
    if extra:
        details.update(extra)
    return ExplanationNode(
        kind=KIND_OBJECT, ref=uuid,
        label=label or f"{type} {number}",
        details=details, children=children,
    )


def relationship_node(
    *,
    source_uuid: str,
    relationship_id: str,
    type: str,
    endpoints: list[dict[str, Any]],
    label: str | None = None,
    extra: dict[str, Any] | None = None,
    children: tuple[ExplanationNode, ...] = (),
) -> ExplanationNode:
    """Build an `ExplanationNode(kind="relationship")` with the canonical
    details per Codex1 B4."""
    details: dict[str, Any] = {
        "source_uuid": source_uuid,
        "relationship_id": relationship_id,
        "type": type,
        "endpoints": list(endpoints),
    }
    if extra:
        details.update(extra)
    return ExplanationNode(
        kind=KIND_RELATIONSHIP,
        ref=f"{source_uuid}:relationship:{relationship_id}",
        label=label or f"{type} {relationship_id}",
        details=details, children=children,
    )


def event_node(
    event: dict[str, Any],
    *,
    label: str | None = None,
    extra: dict[str, Any] | None = None,
    children: tuple[ExplanationNode, ...] = (),
) -> ExplanationNode:
    """Build an `ExplanationNode(kind="event")` with canonical details
    pulled from an event dict (events.jsonl record). Required keys:
    event_id, event_type. timestamp + transaction_id are recorded if present."""
    event_id = event.get("event_id", "")
    event_type = event.get("event_type", "")
    details: dict[str, Any] = {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": event.get("timestamp"),
        "transaction_id": event.get("transaction_id"),
    }
    if extra:
        details.update(extra)
    return ExplanationNode(
        kind=KIND_EVENT, ref=event_id,
        label=label or event_type,
        details=details, children=children,
    )


def validation_error_node(
    *,
    error_type: str,
    classification: str,
    check_name: str,
    message: str,
    label: str | None = None,
    extra: dict[str, Any] | None = None,
    children: tuple[ExplanationNode, ...] = (),
) -> ExplanationNode:
    """Build an `ExplanationNode(kind="validation_error")` with canonical
    details per Codex1 B4. `classification` must be one of `REASON_CLASSIFICATIONS`."""
    if classification not in REASON_CLASSIFICATIONS:
        raise ValueError(
            f"validation_error_node classification must be one of "
            f"{sorted(REASON_CLASSIFICATIONS)}; got {classification!r}"
        )
    details: dict[str, Any] = {
        "error_type": error_type,
        "classification": classification,
        "check_name": check_name,
        "message": message,
    }
    if extra:
        details.update(extra)
    return ExplanationNode(
        kind=KIND_VALIDATION_ERROR, ref=check_name,
        label=label or error_type,
        details=details, children=children,
    )


# ---- Exception classification per Codex1 B1 / Q6 absorption -----------------


def classify_exception(e: BaseException) -> str:
    """Map a known validation exception class to a `reason_classification`
    enum value (one of `REASON_CLASSIFICATIONS`).

    Per Codex Q6 absorption (arc 20260531-10): helper that callers use; the
    audit emitter MUST NOT silently invent precise classifications from
    arbitrary text — fall back to `"other"` for unknown exception types.
    """
    # Import locally to avoid cycles in module init.
    from ..validation.schema import SchemaValidationError
    from ..validation.profile import ProfileViolationError
    from ..validation.binding import RevisionBindingError
    from ..validation.reservation_integrity import ReservationIntegrityError
    from ..validation.release import ReleaseConsistencyError
    from ..validation.fold import FoldInconsistencyError

    if isinstance(e, SchemaValidationError):
        return "schema_validation"
    if isinstance(e, ProfileViolationError):
        return "profile_violation"
    if isinstance(e, FoldInconsistencyError):
        return "fold_inconsistency"
    if isinstance(e, (RevisionBindingError, ReservationIntegrityError)):
        return "binding_violation"
    if isinstance(e, ReleaseConsistencyError):
        return "release_consistency"
    return "other"


# ---- Serialization helpers -------------------------------------------------


def node_to_dict(node: ExplanationNode) -> dict[str, Any]:
    """Recursive JSON-serializable dict for one node. Children flatten."""
    return {
        "kind": node.kind,
        "ref": node.ref,
        "label": node.label,
        "details": dict(node.details),
        "children": [node_to_dict(c) for c in node.children],
    }


def tree_to_dict(tree: ExplanationTree) -> dict[str, Any]:
    return {
        "root": node_to_dict(tree.root),
        "bundle_version": tree.bundle_version,
    }


__all__ = [
    "ExplanationNode",
    "ExplanationTree",
    "KIND_OBJECT",
    "KIND_RELATIONSHIP",
    "KIND_EVENT",
    "KIND_VALIDATION_ERROR",
    "REASON_CLASSIFICATIONS",
    "object_node",
    "relationship_node",
    "event_node",
    "validation_error_node",
    "classify_exception",
    "node_to_dict",
    "tree_to_dict",
]
