"""Reservation rev-id history canonical-state invariants per N3 absorption
arc 20260531-2.

Three invariants enforced as Layer-2 release-time + replay validations:

1. Every `released_revision_ids[]` entry corresponds to an actual released
   Revision file + matching `<type>_released` event.
2. Every Fixed relationship endpoint citing a Reservation rev_id resolves to
   either a released revision OR a B6-protected current_revision_id.
3. No `released_revision_ids[]` entry may be reused as `current_revision_id`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..truth_model.event_log import read_events
from ..truth_model.reservation import (
    list_reservation_prefixes,
    find_reservation_entry_by_uuid,
)
from ..truth_model.revision import revision_path
from ..truth_model.sidecar import list_working_sidecar_uuids
from .binding import EXECUTION_INSTANCE_TYPES, target_endpoint_uuid_rev
from .bundle_registry import BundleRegistry
from .schema import load_reservation_validated, load_sidecar_validated


class ReservationIntegrityError(ValueError):
    """N3 invariant violation."""


def validate_reservation_rev_id_history(
    workspace: Path, bundle_dir: Path, registry: BundleRegistry | None = None,
) -> None:
    """Run all three N3 invariants. Raises ReservationIntegrityError on any."""
    _invariant_1_released_revisions_exist(workspace, bundle_dir, registry)
    _invariant_2_fixed_endpoints_resolve(workspace, bundle_dir, registry)
    _invariant_3_no_rev_id_reuse(workspace, bundle_dir, registry)


def _invariant_1_released_revisions_exist(
    workspace: Path, bundle_dir: Path, registry: BundleRegistry | None = None,
) -> None:
    """Every released_revision_ids[] entry must:
       (a) have a matching `<type>_released` event with that revision_id;
       (b) have a Revision file on disk at the expected path.

    Backward-compatible with v0.19.0 workspaces: the entry is OPTIONAL on
    pre-v0.20.0 Reservation schemas, so this invariant only triggers when
    the entry is actually present (post-v0.20.0 migrations / fresh inits).
    """
    # Collect released (object_uuid, revision_id) pairs from events.
    event_released: set[tuple[str, str]] = set()
    for event in read_events(workspace, bundle_dir):
        if event["event_type"].endswith("_released") and event["event_type"] != "release_staged":
            event_released.add((event["payload"]["object_uuid"], event["payload"]["revision_id"]))

    for prefix in list_reservation_prefixes(workspace):
        res = load_reservation_validated(workspace, prefix, registry=registry)
        for number, entry in res.get("reservations", {}).items():
            obj_uuid = entry.get("object_uuid")
            released_history = entry.get("released_revision_ids") or []
            if not released_history:
                continue  # v0.19.0 Reservation; nothing to check
            for released_rev_id in released_history:
                if (obj_uuid, released_rev_id) not in event_released:
                    raise ReservationIntegrityError(
                        f"N3 invariant 1: Reservation {prefix}/{number} carries "
                        f"released_revision_ids entry {released_rev_id!r} but no "
                        f"matching <type>_released event exists for object_uuid={obj_uuid!r}"
                    )
                rp = revision_path(workspace, obj_uuid, released_rev_id)
                if not rp.exists():
                    raise ReservationIntegrityError(
                        f"N3 invariant 1: Reservation {prefix}/{number} carries "
                        f"released_revision_ids entry {released_rev_id!r} but Revision "
                        f"file is missing on disk at {rp}"
                    )


def _invariant_2_fixed_endpoints_resolve(
    workspace: Path, bundle_dir: Path, registry: BundleRegistry | None = None,
) -> None:
    """Every Fixed relationship endpoint citing a Reservation rev_id must resolve.

    For each execution-instance relationship in the working sidecars, the
    endpoint's (object_uuid, revision_id) MUST be one of:
      (a) in the target Object's Reservation released_revision_ids[] (v0.20.0+);
      (b) equal to the target Object's Reservation current_revision_id (v0.20.0+);
      (c) referenced as a released Revision in any Release Manifest (v0.19.0+
          backward-compat — works even when Reservation lacks the v0.20.0
          rev-id-history fields).

    Condition (b)'s mutation-after-binding scan is enforced by
    `validation/binding.py::find_mutation_after_binding_violations`.
    """
    # Build (object_uuid -> set of released rev_ids) from manifests on disk
    # (v0.19.0-backward-compat resolution).
    from ..truth_model.manifest import list_release_labels, load_manifest
    manifest_released: dict[str, set[str]] = {}
    for label in list_release_labels(workspace):
        try:
            m = load_manifest(workspace, label)
        except Exception:
            continue
        for rev in m.get("revisions", []):
            manifest_released.setdefault(rev["object_uuid"], set()).add(rev["revision_id"])

    for uuid in list_working_sidecar_uuids(workspace):
        sidecar = load_sidecar_validated(workspace, uuid, registry=registry)
        for rel in sidecar.get("relationship", []):
            if rel.get("type") not in EXECUTION_INSTANCE_TYPES:
                continue
            if rel.get("binding") != "fixed":
                continue
            target_uuid, target_rev = target_endpoint_uuid_rev(rel)
            if not target_uuid or not target_rev:
                continue
            # (c) Manifest-derived released
            if target_rev in manifest_released.get(target_uuid, set()):
                continue
            target_entry = find_reservation_entry_by_uuid(workspace, target_uuid)
            if target_entry is None:
                raise ReservationIntegrityError(
                    f"N3 invariant 2: Object {uuid} has Fixed execution-instance "
                    f"relationship targeting Object {target_uuid} but no Reservation "
                    f"entry exists for target"
                )
            _, _, entry = target_entry
            released = set(entry.get("released_revision_ids", []) or [])
            current = entry.get("current_revision_id")
            # (a) Reservation released
            if target_rev in released:
                continue
            # (b) Reservation current
            if target_rev == current:
                continue
            raise ReservationIntegrityError(
                f"N3 invariant 2: Object {uuid} Fixed execution-instance relationship "
                f"endpoint revision_id {target_rev!r} resolves neither to released "
                f"Reservation ({sorted(released)}) nor current Reservation "
                f"({current!r}) nor any Release Manifest for target {target_uuid}"
            )


def _invariant_3_no_rev_id_reuse(
    workspace: Path, bundle_dir: Path, registry: BundleRegistry | None = None,
) -> None:
    """No Reservation may carry `current_revision_id` equal to any
    `released_revision_ids[]` entry. Once a rev_id is released, it is terminal."""
    for prefix in list_reservation_prefixes(workspace):
        res = load_reservation_validated(workspace, prefix, registry=registry)
        for number, entry in res.get("reservations", {}).items():
            current = entry.get("current_revision_id")
            released = entry.get("released_revision_ids", []) or []
            if current and current in released:
                raise ReservationIntegrityError(
                    f"N3 invariant 3: Reservation {prefix}/{number} has "
                    f"current_revision_id {current!r} that already appears in "
                    f"released_revision_ids[] (rev_id reuse forbidden)"
                )
