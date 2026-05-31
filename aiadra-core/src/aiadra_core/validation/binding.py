"""Revision-binding helpers per B6 absorption arc 20260531-2 + N5 endpoint helper.

B6 Option C: mutation prohibition until release for any Object whose unreleased
`current_revision_id` has been referenced by a Fixed execution-instance
relationship endpoint. Derive-at-validate from the event log; no extra
Reservation field needed.

N5: isolate `endpoints[0]` lookup behind a small helper rather than scattering
through the code — eases future W3 (Phase 3) per-relationship-type dispatch.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from ..truth_model.event_log import read_events
from .bundle_registry import BundleRegistry


EXECUTION_INSTANCE_TYPES = ("executes", "executed_on", "produces")


def relationship_target_endpoint(relationship_record: dict[str, Any]) -> dict[str, Any] | None:
    """Return the primary target endpoint for a relationship record.

    Per N5: Phase 1's execution-instance relationships (`executes`,
    `executed_on`, `produces`) carry exactly one target endpoint at
    `endpoints[0]`. This helper centralizes the access so W3 Phase 3
    relationship dispatch can extend without code-scattered changes.
    """
    endpoints = relationship_record.get("endpoints") or []
    if not endpoints:
        return None
    return endpoints[0]


def target_endpoint_uuid_rev(relationship_record: dict[str, Any]) -> tuple[str, str | None]:
    """Return (object_uuid, revision_id) of a relationship's target endpoint.

    revision_id may be None for Float-bound or unpinned endpoints.
    """
    ep = relationship_target_endpoint(relationship_record) or {}
    return ep.get("object_uuid", ""), ep.get("revision_id")


class RevisionBindingError(ValueError):
    """B6: mutating Transaction rejected because target Object is bound by an
    unreleased Fixed execution-instance relationship."""


def _iter_fixed_execution_bindings(
    workspace: Path, bundle_dir: Path, registry: BundleRegistry | None = None,
) -> Iterator[tuple[str, str, str]]:
    """Yield (target_uuid, target_rev_id, binding_event_id) for every Fixed
    execution-instance relationship in the event log.

    "Fixed" here means the relationship record's `binding == 'fixed'` AND the
    endpoint has a concrete `revision_id` (always true for execution-instance
    relationships per ADR/0022 §6).
    """
    for event in read_events(workspace, bundle_dir):
        if event["event_type"] != "relationship_created":
            continue
        rec = event["payload"]["relationship_record"]
        if rec.get("type") not in EXECUTION_INSTANCE_TYPES:
            continue
        if rec.get("binding") != "fixed":
            continue
        target_uuid, target_rev = target_endpoint_uuid_rev(rec)
        if not target_uuid or not target_rev:
            continue
        yield target_uuid, target_rev, event.get("event_id", "")


def is_revision_bound(
    workspace: Path, bundle_dir: Path, obj_uuid: str, rev_id: str,
    registry: BundleRegistry | None = None,
) -> bool:
    """Per B6: True if `(obj_uuid, rev_id)` is the target of any unreleased
    Fixed execution-instance relationship.

    A rev_id is "released" if it appears in the Object's Reservation
    `released_revision_ids[]`. A bound rev_id that IS released is NOT a
    prohibition trigger (historical pinning, content is immutable in the
    released Revision).
    """
    # Load Reservation for the Object to check released_revision_ids[]
    from .schema import load_reservation_validated
    from ..truth_model.reservation import list_reservation_prefixes

    released_for_uuid: set[str] = set()
    for prefix in list_reservation_prefixes(workspace):
        try:
            res = load_reservation_validated(workspace, prefix, registry=registry)
        except Exception:
            continue
        for number, entry in res.get("reservations", {}).items():
            if entry.get("object_uuid") == obj_uuid:
                released_for_uuid.update(entry.get("released_revision_ids", []) or [])
                break

    if rev_id in released_for_uuid:
        return False

    for target_uuid, target_rev, _ in _iter_fixed_execution_bindings(workspace, bundle_dir, registry):
        if target_uuid == obj_uuid and target_rev == rev_id:
            return True
    return False


def find_mutation_after_binding_violations(
    workspace: Path, bundle_dir: Path,
    registry: BundleRegistry | None = None,
) -> list[str]:
    """B6 final-release scan: walk event log; flag any mutation event whose
    target Object had an unreleased Fixed execution-instance binding at the
    time the mutation was emitted.

    Returns a list of human-readable violation descriptions (empty if clean).
    """
    events = list(read_events(workspace, bundle_dir))

    # Build: for each (target_uuid, target_rev_id), the event_index at which
    # the binding was created.
    bindings: dict[tuple[str, str], int] = {}
    # Build: for each (uuid, rev_id), the event_index at which it was released.
    releases: dict[tuple[str, str], int] = {}

    for i, event in enumerate(events):
        et = event["event_type"]
        if et == "relationship_created":
            rec = event["payload"]["relationship_record"]
            if rec.get("type") in EXECUTION_INSTANCE_TYPES and rec.get("binding") == "fixed":
                tu, tr = target_endpoint_uuid_rev(rec)
                if tu and tr:
                    bindings.setdefault((tu, tr), i)
        elif et.endswith("_released"):
            uuid = event["payload"]["object_uuid"]
            rev_id = event["payload"]["revision_id"]
            releases[(uuid, rev_id)] = i

    violations: list[str] = []
    for i, event in enumerate(events):
        et = event["event_type"]
        mutated_uuid: str | None = None
        if et == "parameter_changed":
            mutated_uuid = event["payload"]["object_uuid"]
        elif et in (
            "drawing_changed", "test_procedure_changed",
            "test_execution_changed", "evidence_artifact_changed",
        ):
            mutated_uuid = event["payload"]["object_uuid"]
        if mutated_uuid is None:
            continue
        # Find any binding for this Object whose event_index is BEFORE i AND
        # the bound rev_id was NOT released before i.
        for (tu, tr), bind_i in bindings.items():
            if tu != mutated_uuid:
                continue
            if bind_i >= i:
                continue
            release_i = releases.get((tu, tr))
            if release_i is not None and release_i < i:
                continue  # released before mutation; allowed
            violations.append(
                f"Mutation event {event.get('event_id', '?')} ({et}) at index {i} "
                f"targets Object {mutated_uuid} which had an unreleased Fixed "
                f"execution-instance binding to rev_id {tr!r} created at event index "
                f"{bind_i} (event_id {events[bind_i].get('event_id', '?')})."
            )
    return violations
