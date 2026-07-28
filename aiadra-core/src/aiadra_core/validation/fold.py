"""Sidecar/event invariant per ADR/0001 §4.

**Bidirectional check** (per Codex1 B3 absorption arc 20260531-1):

1. Every folded UUID has a matching on-disk working sidecar with identical state.
2. Every on-disk `revisions/<uuid>/working.yaml` UUID is present in the folded
   state (i.e., no stray sidecars not derivable from events).

The spike implementation only verified (1). Carrying that forward would preserve
a known hole — a handwritten or stale working.yaml not derivable from events
would silently pass validation, violating "sidecars and events must agree;
neither silently wins."
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..truth_model.event_log import read_events
from ..truth_model.sidecar import list_working_sidecar_uuids
from .schema import load_sidecar_validated


class FoldInconsistencyError(ValueError):
    """Sidecar/event invariant violation."""


_ATTACHMENT_CHANGED_EVENTS = (
    "drawing_changed",
    "test_procedure_changed",
    "test_execution_changed",
    "evidence_artifact_changed",
)


def _apply_part_changed(
    state: dict[str, dict[str, Any]],
    payload: dict[str, Any],
    actor: str,
) -> None:
    """Apply a `part_changed` event to fold state per ADR/0029.

    Codex1 B3 atomic delta rules (arc 20260531-13):
      Within ONE delta object (feature_delta OR geometry_ref_delta):
      - No duplicate ids in any single array (added/updated/removed).
      - The same id cannot appear in more than one of added/updated/removed.
      - added[].id MUST NOT pre-exist on the sidecar.
      - updated[].id and removed[] entries MUST exist on the sidecar.
      - updated[].new_record.id MUST equal updated[].id.
      Apply the FULL delta atomically, then enforce post-conditions:
      - depends_on_feature_ids acyclic per Codex1 B6 (DAG, not tree).
      - No dangling references after removals (cascade-rejects).
      - Provenance discipline per Codex1 B4: feature records' fact_provenance
        matches actor; geometry_ref records' computed_result + derived_from
        cross-checks derived_from_feature_ids via the canonical `feature:<id>`
        address form.
    """
    uuid = payload["object_uuid"]
    if uuid not in state:
        raise FoldInconsistencyError(
            f"part_changed for unknown Object {uuid!r} (no part_created event)"
        )

    if "feature_delta" in payload:
        _apply_feature_delta(state[uuid], payload["feature_delta"], actor, uuid)
    if "geometry_ref_delta" in payload:
        _apply_geometry_ref_delta(state[uuid], payload["geometry_ref_delta"], uuid)

    # Post-conditions over the post-delta sidecar:
    _enforce_feature_dependency_acyclicity(state[uuid], uuid)
    _enforce_no_dangling_feature_references(state[uuid], uuid)


def _apply_feature_delta(
    sidecar: dict[str, Any],
    delta: dict[str, Any],
    actor: str,
    uuid: str,
) -> None:
    added = delta.get("added", [])
    updated = delta.get("updated", [])
    removed = delta.get("removed", [])

    added_ids = [r["id"] for r in added]
    updated_ids = [u["id"] for u in updated]
    removed_ids = list(removed)

    # Intra-array duplicates.
    for label, ids in (("added", added_ids), ("updated", updated_ids), ("removed", removed_ids)):
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise FoldInconsistencyError(
                f"part_changed.feature_delta.{label}: duplicate id(s) within array: {dupes}"
            )

    # Cross-array overlap.
    union_buckets = {"added": set(added_ids), "updated": set(updated_ids), "removed": set(removed_ids)}
    for a, b in (("added", "updated"), ("added", "removed"), ("updated", "removed")):
        overlap = union_buckets[a] & union_buckets[b]
        if overlap:
            raise FoldInconsistencyError(
                f"part_changed.feature_delta: id(s) {sorted(overlap)} appear in both {a!r} and {b!r}"
            )

    features = sidecar.setdefault("feature", [])
    by_id = {f["id"]: i for i, f in enumerate(features)}

    # added: ids MUST NOT pre-exist.
    pre_existing_added = sorted(set(added_ids) & set(by_id))
    if pre_existing_added:
        raise FoldInconsistencyError(
            f"part_changed.feature_delta.added: id(s) {pre_existing_added} already present on Part {uuid}"
        )
    # updated + removed: ids MUST exist.
    missing_updated = sorted(set(updated_ids) - set(by_id))
    if missing_updated:
        raise FoldInconsistencyError(
            f"part_changed.feature_delta.updated: id(s) {missing_updated} not present on Part {uuid}"
        )
    missing_removed = sorted(set(removed_ids) - set(by_id))
    if missing_removed:
        raise FoldInconsistencyError(
            f"part_changed.feature_delta.removed: id(s) {missing_removed} not present on Part {uuid}"
        )

    # updated[].new_record.id MUST equal updated[].id.
    for u in updated:
        if u["new_record"]["id"] != u["id"]:
            raise FoldInconsistencyError(
                f"part_changed.feature_delta.updated: new_record.id {u['new_record']['id']!r} "
                f"!= wrapper id {u['id']!r}"
            )

    # Per Codex1 B4 provenance discipline: feature records carry caller provenance.
    expected_cat = "ai_proposal" if actor == "agent" else "human_input"
    for rec in added:
        cat = rec.get("fact_provenance", {}).get("category")
        if cat != expected_cat:
            raise FoldInconsistencyError(
                f"part_changed.feature_delta.added[{rec['id']}].fact_provenance.category "
                f"= {cat!r}; actor={actor!r} requires {expected_cat!r} per ADR/0028 D8"
            )
    for u in updated:
        cat = u["new_record"].get("fact_provenance", {}).get("category")
        if cat != expected_cat:
            raise FoldInconsistencyError(
                f"part_changed.feature_delta.updated[{u['id']}].new_record.fact_provenance.category "
                f"= {cat!r}; actor={actor!r} requires {expected_cat!r} per ADR/0028 D8"
            )

    # Apply atomically: removes first, then updates, then adds.
    if removed_ids:
        features[:] = [f for f in features if f["id"] not in set(removed_ids)]
    if updated_ids:
        by_id = {f["id"]: i for i, f in enumerate(features)}
        for u in updated:
            features[by_id[u["id"]]] = json.loads(json.dumps(u["new_record"]))
    if added_ids:
        for rec in added:
            features.append(json.loads(json.dumps(rec)))


def _apply_geometry_ref_delta(
    sidecar: dict[str, Any],
    delta: dict[str, Any],
    uuid: str,
) -> None:
    added = delta.get("added", [])
    updated = delta.get("updated", [])
    removed = delta.get("removed", [])

    added_ids = [r["id"] for r in added]
    updated_ids = [u["id"] for u in updated]
    removed_ids = list(removed)

    for label, ids in (("added", added_ids), ("updated", updated_ids), ("removed", removed_ids)):
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise FoldInconsistencyError(
                f"part_changed.geometry_ref_delta.{label}: duplicate id(s) within array: {dupes}"
            )

    union_buckets = {"added": set(added_ids), "updated": set(updated_ids), "removed": set(removed_ids)}
    for a, b in (("added", "updated"), ("added", "removed"), ("updated", "removed")):
        overlap = union_buckets[a] & union_buckets[b]
        if overlap:
            raise FoldInconsistencyError(
                f"part_changed.geometry_ref_delta: id(s) {sorted(overlap)} appear in both {a!r} and {b!r}"
            )

    geoms = sidecar.setdefault("geometry_ref", [])
    by_id = {g["id"]: i for i, g in enumerate(geoms)}

    pre_existing_added = sorted(set(added_ids) & set(by_id))
    if pre_existing_added:
        raise FoldInconsistencyError(
            f"part_changed.geometry_ref_delta.added: id(s) {pre_existing_added} already present on Part {uuid}"
        )
    missing_updated = sorted(set(updated_ids) - set(by_id))
    if missing_updated:
        raise FoldInconsistencyError(
            f"part_changed.geometry_ref_delta.updated: id(s) {missing_updated} not present on Part {uuid}"
        )
    missing_removed = sorted(set(removed_ids) - set(by_id))
    if missing_removed:
        raise FoldInconsistencyError(
            f"part_changed.geometry_ref_delta.removed: id(s) {missing_removed} not present on Part {uuid}"
        )

    for u in updated:
        if u["new_record"]["id"] != u["id"]:
            raise FoldInconsistencyError(
                f"part_changed.geometry_ref_delta.updated: new_record.id {u['new_record']['id']!r} "
                f"!= wrapper id {u['id']!r}"
            )

    # Codex1 B4 + Codex2 B2 provenance discipline: geometry_ref records are
    # computed_result; the fold enforces STRICT set-equality (NOT subset coverage)
    # between declared geometric inputs and provenance-attested inputs.
    # Cross-Object address form `<uuid>:feature:<id>` is REJECTED in v0.28.0
    # (reserved for future SCN when cross-Part geometry derivation lands).
    for rec in added + [u["new_record"] for u in updated]:
        if rec.get("role") == "authoring_geometry":
            _enforce_authoring_geometry_provenance_consistency(rec, uuid)
        elif rec.get("role") == "derived_export":
            _enforce_derived_export_provenance_consistency(rec, uuid)

    if removed_ids:
        geoms[:] = [g for g in geoms if g["id"] not in set(removed_ids)]
    if updated_ids:
        by_id = {g["id"]: i for i, g in enumerate(geoms)}
        for u in updated:
            geoms[by_id[u["id"]]] = json.loads(json.dumps(u["new_record"]))
    if added_ids:
        for rec in added:
            geoms.append(json.loads(json.dumps(rec)))


_INTRA_PART_FEATURE_ADDRESS_RE = re.compile(r"^feature:(feat_\d{4})$")
_INTRA_PART_GEOMETRY_ADDRESS_RE = re.compile(r"^geometry_ref:(geom_\d{4})$")


def _enforce_authoring_geometry_provenance_consistency(rec: dict[str, Any], uuid: str) -> None:
    """Codex1 B4 + Codex2 B2: STRICT set-equality between
    `derived_from_feature_ids` and the intra-Part `feature:<id>` entries in
    `fact_provenance.derived_from`.

    Rules (per ADR/0029 D6 + Codex2 B2 absorption):
    - Cross-Object form `<uuid>:feature:<feat_id>` REJECTED in v0.28.0
      (reserved for future SCN).
    - Every entry in `fact_provenance.derived_from` MUST match
      `^feature:feat_\\d{4}$` (intra-Part canonical address form).
    - The set of feature ids extracted from `fact_provenance.derived_from`
      MUST EQUAL the set in `derived_from_feature_ids` — neither
      under-covering (missing) nor over-attesting (dangling extras) allowed.
    """
    declared = set(rec.get("derived_from_feature_ids", []))
    provenance_entries = rec.get("fact_provenance", {}).get("derived_from", [])

    addressed_ids: set[str] = set()
    for s in provenance_entries:
        if not isinstance(s, str):
            raise FoldInconsistencyError(
                f"part_changed: geometry_ref {rec['id']!r} on Part {uuid}: "
                f"fact_provenance.derived_from entry {s!r} is not a string"
            )
        m = _INTRA_PART_FEATURE_ADDRESS_RE.match(s)
        if not m:
            raise FoldInconsistencyError(
                f"part_changed: geometry_ref {rec['id']!r} on Part {uuid}: "
                f"fact_provenance.derived_from entry {s!r} not in canonical "
                f"`feature:<feat_NNNN>` form (cross-Object `<uuid>:feature:<id>` "
                f"form reserved for future SCN per ADR/0029 D14 item 6)"
            )
        addressed_ids.add(m.group(1))

    missing = sorted(declared - addressed_ids)
    extras = sorted(addressed_ids - declared)
    if missing or extras:
        problems = []
        if missing:
            problems.append(f"missing {missing} (declared in derived_from_feature_ids but not attested in fact_provenance.derived_from)")
        if extras:
            problems.append(f"extras {extras} (attested in fact_provenance.derived_from but not declared in derived_from_feature_ids)")
        raise FoldInconsistencyError(
            f"part_changed: geometry_ref {rec['id']!r} on Part {uuid}: "
            f"set mismatch — {'; '.join(problems)} (per ADR/0029 D6 STRICT set-equality)"
        )


def _enforce_derived_export_provenance_consistency(rec: dict[str, Any], uuid: str) -> None:
    """Codex2 B2 absorption (recommended extension to derived_export):
    STRICT set-equality between geom-to-geom `derived_from` (ADR/0005 D7
    lineage) and the intra-Part `geometry_ref:<id>` entries in
    `fact_provenance.derived_from`.

    Cross-Object address form `<uuid>:geometry_ref:<geom_id>` REJECTED in
    v0.28.0 (reserved for future SCN, symmetric to feature-address discipline).
    """
    declared = set(rec.get("derived_from", []))  # geom-to-geom lineage per ADR/0005 D7
    provenance_entries = rec.get("fact_provenance", {}).get("derived_from", [])

    addressed_ids: set[str] = set()
    for s in provenance_entries:
        if not isinstance(s, str):
            raise FoldInconsistencyError(
                f"part_changed: geometry_ref {rec['id']!r} on Part {uuid}: "
                f"fact_provenance.derived_from entry {s!r} is not a string"
            )
        m = _INTRA_PART_GEOMETRY_ADDRESS_RE.match(s)
        if not m:
            raise FoldInconsistencyError(
                f"part_changed: geometry_ref {rec['id']!r} (derived_export) on Part {uuid}: "
                f"fact_provenance.derived_from entry {s!r} not in canonical "
                f"`geometry_ref:<geom_NNNN>` form (cross-Object form "
                f"reserved for future SCN per ADR/0029 D14 item 6)"
            )
        addressed_ids.add(m.group(1))

    missing = sorted(declared - addressed_ids)
    extras = sorted(addressed_ids - declared)
    if missing or extras:
        problems = []
        if missing:
            problems.append(f"missing {missing} (declared in derived_from but not attested in fact_provenance.derived_from)")
        if extras:
            problems.append(f"extras {extras} (attested in fact_provenance.derived_from but not declared in derived_from)")
        raise FoldInconsistencyError(
            f"part_changed: geometry_ref {rec['id']!r} (derived_export) on Part {uuid}: "
            f"set mismatch — {'; '.join(problems)} (per ADR/0029 D6 STRICT set-equality)"
        )


def _enforce_feature_dependency_acyclicity(sidecar: dict[str, Any], uuid: str) -> None:
    """Codex1 B6 + ADR/0029 D9: depends_on_feature_ids forms a DAG.

    Detects cycles via Kahn-style topological walk. O(V+E) over the feature set
    of a single Part.
    """
    features = sidecar.get("feature", [])
    if not features:
        return
    ids = {f["id"] for f in features}
    deps = {f["id"]: set(f.get("depends_on_feature_ids", [])) for f in features}
    # First check: every depends_on_feature_id must reference an existing feature.
    for fid, ds in deps.items():
        dangling = ds - ids
        if dangling:
            raise FoldInconsistencyError(
                f"part_changed: feature {fid!r} on Part {uuid} depends_on_feature_ids "
                f"{sorted(dangling)} which do not exist on the Part"
            )
    # Topological walk via Kahn's algorithm.
    in_count = {fid: 0 for fid in ids}
    for fid, ds in deps.items():
        for d in ds:
            in_count[fid] += 1  # fid depends on d, so fid has an incoming edge from d
    # Actually we want in-degree based on inverted edges. Use reverse map:
    out: dict[str, set[str]] = {fid: set() for fid in ids}
    for fid, ds in deps.items():
        for d in ds:
            out[d].add(fid)  # edge d -> fid
    in_deg = {fid: len(deps[fid]) for fid in ids}
    queue = [fid for fid in ids if in_deg[fid] == 0]
    removed_count = 0
    while queue:
        fid = queue.pop()
        removed_count += 1
        for succ in out[fid]:
            in_deg[succ] -= 1
            if in_deg[succ] == 0:
                queue.append(succ)
    if removed_count != len(ids):
        cyclic = sorted(fid for fid, d in in_deg.items() if d > 0)
        raise FoldInconsistencyError(
            f"part_changed: feature dependency cycle on Part {uuid} involving features {cyclic} "
            f"(depends_on_feature_ids must form a DAG per ADR/0029 D9)"
        )


def _enforce_no_dangling_feature_references(sidecar: dict[str, Any], uuid: str) -> None:
    """ADR/0029 D12 + Codex1 B3 + Codex2 B2 cascade rule: after applying the FULL
    delta atomically, no surviving record may reference a removed id.

    Checks:
    - feature.depends_on_feature_ids ⊆ surviving feature ids
    - authoring_geometry.derived_from_feature_ids ⊆ surviving feature ids
    - derived_export.derived_from ⊆ surviving geometry_ref ids
    """
    feature_ids = {f["id"] for f in sidecar.get("feature", [])}
    geometry_ids = {g["id"] for g in sidecar.get("geometry_ref", [])}

    # Surviving features must not depend on removed features.
    for f in sidecar.get("feature", []):
        dangling = set(f.get("depends_on_feature_ids", [])) - feature_ids
        if dangling:
            raise FoldInconsistencyError(
                f"part_changed: feature {f['id']!r} on Part {uuid} "
                f"depends_on_feature_ids {sorted(dangling)} not present on Part after delta "
                f"(cascade-reject per ADR/0029 D12)"
            )

    for g in sidecar.get("geometry_ref", []):
        if g.get("role") == "authoring_geometry":
            dangling = set(g.get("derived_from_feature_ids", [])) - feature_ids
            if dangling:
                raise FoldInconsistencyError(
                    f"part_changed: geometry_ref {g['id']!r} on Part {uuid} "
                    f"derived_from_feature_ids {sorted(dangling)} not present on Part after delta "
                    f"(cascade-reject per ADR/0029 D12)"
                )
        elif g.get("role") == "derived_export":
            dangling = set(g.get("derived_from", [])) - geometry_ids
            if dangling:
                raise FoldInconsistencyError(
                    f"part_changed: geometry_ref {g['id']!r} (derived_export) on Part {uuid} "
                    f"derived_from {sorted(dangling)} not present on Part after delta "
                    f"(cascade-reject per ADR/0029 D12; Codex2 B2 absorption)"
                )


def _apply_attachment_delta(
    state: dict[str, dict[str, Any]],
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Apply a `<type>_changed.attachment_delta` event to fold state.

    Per B5 absorption (Phase 1 arc 20260531-2): enforces add/update/remove
    semantic invariants — add MUST fail if id exists; update/remove MUST fail
    if id missing; record.id MUST equal attachment_id.
    """
    uuid = payload["object_uuid"]
    delta = payload["attachment_delta"]
    op = delta["operation"]
    att_id = delta["attachment_id"]
    if uuid not in state:
        raise FoldInconsistencyError(
            f"{event_type} for unknown Object {uuid!r} (no <type>_created event)"
        )
    sidecar_attachments = state[uuid].setdefault("attachment", [])
    by_id = {a["id"]: i for i, a in enumerate(sidecar_attachments)}

    if op == "add":
        if att_id in by_id:
            raise FoldInconsistencyError(
                f"{event_type} add attachment_id {att_id!r} but already present on {uuid}"
            )
        rec = delta.get("attachment_record")
        if not rec:
            raise FoldInconsistencyError(
                f"{event_type} add missing attachment_record"
            )
        if rec.get("id") != att_id:
            raise FoldInconsistencyError(
                f"{event_type} attachment_record.id {rec.get('id')!r} != "
                f"attachment_id {att_id!r}"
            )
        sidecar_attachments.append(json.loads(json.dumps(rec)))
    elif op == "update":
        if att_id not in by_id:
            raise FoldInconsistencyError(
                f"{event_type} update attachment_id {att_id!r} but not present on {uuid}"
            )
        rec = delta.get("attachment_record")
        if not rec:
            raise FoldInconsistencyError(
                f"{event_type} update missing attachment_record"
            )
        if rec.get("id") != att_id:
            raise FoldInconsistencyError(
                f"{event_type} attachment_record.id {rec.get('id')!r} != "
                f"attachment_id {att_id!r}"
            )
        sidecar_attachments[by_id[att_id]] = json.loads(json.dumps(rec))
    elif op == "remove":
        if att_id not in by_id:
            raise FoldInconsistencyError(
                f"{event_type} remove attachment_id {att_id!r} but not present on {uuid}"
            )
        sidecar_attachments[:] = [a for a in sidecar_attachments if a["id"] != att_id]


def fold_events_to_state(workspace: Path, bundle_dir: Path) -> dict[str, dict[str, Any]]:
    """Replay validated events; build current working-state by UUID.

    Handles generic `<type>_created` events (Wedge-002 round-1 B1 pattern:
    `et.endswith('_created') + initial_sidecar payload`), `relationship_created`,
    `parameter_changed`, `<type>_changed` (W2 absorption — attachment_delta with
    B5 invariants), `release_staged` (audit-oriented; no working-state mutation),
    and `<type>_released` (no working-state mutation — Revisions are separate
    immutable artifacts per ADR/0001 §3).
    """
    state: dict[str, dict[str, Any]] = {}
    for event in read_events(workspace, bundle_dir):  # validated iterator
        et = event["event_type"]
        if et.endswith("_created") and et != "relationship_created":
            uuid = event["payload"]["uuid"]
            state[uuid] = json.loads(json.dumps(event["payload"]["initial_sidecar"]))
        elif et == "relationship_created":
            src = event["payload"]["source_uuid"]
            rec = event["payload"]["relationship_record"]
            state[src].setdefault("relationship", []).append(json.loads(json.dumps(rec)))
        elif et == "parameter_changed":
            uuid = event["payload"]["object_uuid"]
            pid = event["payload"]["parameter_id"]
            new_value = event["payload"]["new_value"]
            # F1 absorption Phase 2 (arc 20260531-3): if new_fact_provenance
            # present, replace the parameter's fact_provenance dict wholesale.
            # If absent, fact_provenance unchanged (backward-compat with v0.20.0).
            new_fp = event["payload"].get("new_fact_provenance")
            for p in state[uuid].get("parameter", []):
                if p.get("id") == pid:
                    p["value"] = new_value
                    if new_fp is not None:
                        p["fact_provenance"] = json.loads(json.dumps(new_fp))
                    break
        elif et in _ATTACHMENT_CHANGED_EVENTS:
            _apply_attachment_delta(state, et, event["payload"])
        elif et == "requirement_changed":
            # F2 absorption Phase 4 (arc 20260531-5; Codex1 B1): added-only delta.
            # Reject duplicate criterion ids; append each new criterion to the
            # Requirement's acceptance_criterion[] list. updated/removed deltas
            # are schema-rejected and never reach this branch.
            uuid = event["payload"]["object_uuid"]
            added = event["payload"]["acceptance_criterion_delta"]["added"]
            existing = state[uuid].setdefault("acceptance_criterion", [])
            existing_ids = {c["id"] for c in existing if isinstance(c, dict)}
            for crit in added:
                if crit["id"] in existing_ids:
                    raise FoldInconsistencyError(
                        f"requirement_changed.added: criterion id {crit['id']!r} "
                        f"already exists on Requirement {uuid}"
                    )
                existing.append(json.loads(json.dumps(crit)))
                existing_ids.add(crit["id"])
        elif et == "part_changed":
            # ADR/0029 Part authoring SCN (arc 20260531-13): apply full
            # add/update/remove deltas for feature + geometry_ref namespaces,
            # then enforce atomic post-conditions (DAG acyclicity, no dangling
            # references, provenance discipline per actor).
            _apply_part_changed(state, event["payload"], event["actor"])
        elif et == "release_staged":
            # Audit-oriented per B1 absorption; no working-state mutation.
            pass
        elif et == "object_deleted":
            # ADR/0004 SCN (arc 20260728-3 B3): deletion removes the uuid from
            # working state. The uuid MUST exist — deleting an unknown Object
            # is fold inconsistency, never a silent no-op.
            uuid = event["payload"]["uuid"]
            if uuid not in state:
                raise FoldInconsistencyError(
                    f"object_deleted: uuid {uuid} not present in folded working "
                    f"state; nothing to delete"
                )
            state.pop(uuid)
        # <type>_released and <type>_retired events do not mutate working state.
    return state


def validate_fold(workspace: Path, bundle_dir: Path) -> None:
    """Verify the sidecar/event invariant — bidirectionally.

    Raises FoldInconsistencyError on either direction's violation.
    """
    folded = fold_events_to_state(workspace, bundle_dir)
    on_disk_uuids = set(list_working_sidecar_uuids(workspace))
    folded_uuids = set(folded.keys())

    # Direction 1: every folded UUID has matching on-disk sidecar with
    # identical state (the spike's existing check).
    for uuid, expected in folded.items():
        if uuid not in on_disk_uuids:
            raise FoldInconsistencyError(
                f"Events derive Object {uuid}; on-disk working sidecar missing"
            )
        on_disk = load_sidecar_validated(workspace, uuid, bundle_dir)
        if json.dumps(on_disk, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise FoldInconsistencyError(
                f"Sidecar/event invariant violated for {uuid}: "
                f"on-disk working sidecar does not match event fold"
            )

    # Direction 2: every on-disk working sidecar UUID is present in the
    # folded state (per Codex1 B3 absorption arc 20260531-1). A working.yaml
    # not derivable from events is a disagreement — "neither silently wins."
    extra_uuids = on_disk_uuids - folded_uuids
    if extra_uuids:
        raise FoldInconsistencyError(
            f"On-disk working sidecar(s) not derivable from events "
            f"(no corresponding creation event found): {sorted(extra_uuids)}"
        )
