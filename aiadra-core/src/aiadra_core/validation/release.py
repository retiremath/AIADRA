"""Release-time validation invariants per N2 absorption arc 20260531-2.

`validate_release_staged_consistency` runs in TWO MODES per Codex3 N4:

- **draft mode**: called from Transaction validate-phase against in-memory
  proposed manifest + events + Reservation updates BEFORE any write.
- **replay mode**: called from `aiadra validate <workspace>` against on-disk
  state for every prior `release_staged` event in the event log.

Both modes check the same 7 invariants:

1. release_staged.manifest_hash matches actual canonical bytes of the named manifest.
2. release_staged.released_object_uuids set-equals object_uuids from per-Object
   <type>_released events emitted in the same Transaction.
3. Each released object_uuid appears in exactly one <type>_released event
   with rev_id == manifest.revisions[].revision_id for that uuid.
4. release_staged.stage_number == manifest.stage_number.
5. release_staged.final_stage == manifest.final_stage.
6. If prior_stage_manifest_ref present: prior manifest exists, hash matches,
   stage_number matches.
7. Every released rev_id appears in the Object's Reservation released_revision_ids[].
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..truth_model.event_log import read_events
from ..truth_model.manifest import (
    list_release_labels,
    load_manifest,
    manifest_path,
    serialize_manifest,
)
from ..truth_model.reservation import find_reservation_entry_by_uuid
from ..vault.interface import AttachmentIntegrityError
from ..vault.local_fs import LocalFSVaultAdapter
from .binding import EXECUTION_INSTANCE_TYPES, target_endpoint_uuid_rev
from .bundle_registry import BundleRegistry
from .schema import load_manifest_validated, load_reservation_validated, load_sidecar_validated


_ATTACHMENT_BEARING_TYPES = ("Drawing", "TestProcedure", "EvidenceArtifact", "TestExecution")
_LINEAGE_BEARING_TYPES = ("EvidenceArtifact", "TestExecution")


class ReleaseConsistencyError(ValueError):
    """N2 invariant violation."""


@dataclass
class ReleaseDraft:
    """In-memory release Transaction draft, for draft-mode validation.

    Carried by transaction/operations/release.py during the release Transaction.
    """
    release_label: str
    manifest: dict[str, Any]
    manifest_hash: str  # computed from serialize_manifest(manifest)
    release_staged_event: dict[str, Any]
    per_object_released_events: list[dict[str, Any]] = field(default_factory=list)
    reservation_updates: dict[str, dict[str, Any]] = field(default_factory=dict)
    # key = prefix; value = full proposed reservation dict (post-update)
    proposed_revisions: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    # key = (object_uuid, revision_id); value = proposed Revision content

    def _iter_proposed_revisions(self):
        """Yield ((obj_uuid, rev_id), content) pairs for same-stage proposed Revisions."""
        for key, content in self.proposed_revisions.items():
            yield key, content


def _check_release_staged_against(
    release_staged_payload: dict[str, Any],
    manifest: dict[str, Any],
    per_object_released_events: list[dict[str, Any]],
    reservation_resolver,
    manifest_hash_actual: str,
    prior_manifest_resolver,
    context: str,
) -> None:
    """Shared invariant checks for both draft and replay modes."""
    # Invariant 1: manifest_hash matches actual canonical bytes
    if release_staged_payload["manifest_hash"] != manifest_hash_actual:
        raise ReleaseConsistencyError(
            f"{context}: N2 invariant 1: release_staged.manifest_hash "
            f"{release_staged_payload['manifest_hash']!r} != actual manifest hash "
            f"{manifest_hash_actual!r}"
        )

    # Invariant 2: released_object_uuids set-equals per-Object release event uuids
    rs_uuids = set(release_staged_payload["released_object_uuids"])
    ev_uuids = {ev["payload"]["object_uuid"] for ev in per_object_released_events}
    if rs_uuids != ev_uuids:
        raise ReleaseConsistencyError(
            f"{context}: N2 invariant 2: release_staged.released_object_uuids "
            f"{sorted(rs_uuids)} != union of per-Object <type>_released events "
            f"{sorted(ev_uuids)}"
        )

    # Invariant 3: each released uuid → exactly one matching event AND matching manifest revision
    manifest_revs_by_uuid: dict[str, dict[str, Any]] = {}
    for rev in manifest.get("revisions", []):
        manifest_revs_by_uuid[rev["object_uuid"]] = rev
    for uuid in rs_uuids:
        events_for_uuid = [ev for ev in per_object_released_events if ev["payload"]["object_uuid"] == uuid]
        if len(events_for_uuid) != 1:
            raise ReleaseConsistencyError(
                f"{context}: N2 invariant 3: Object {uuid} has "
                f"{len(events_for_uuid)} <type>_released events in this release "
                f"(expected exactly 1)"
            )
        ev_rev_id = events_for_uuid[0]["payload"]["revision_id"]
        manifest_rev = manifest_revs_by_uuid.get(uuid)
        if manifest_rev is None:
            raise ReleaseConsistencyError(
                f"{context}: N2 invariant 3: Object {uuid} in release_staged but "
                f"absent from manifest.revisions[]"
            )
        if manifest_rev["revision_id"] != ev_rev_id:
            raise ReleaseConsistencyError(
                f"{context}: N2 invariant 3: Object {uuid} event rev_id "
                f"{ev_rev_id!r} != manifest rev_id {manifest_rev['revision_id']!r}"
            )

    # Invariant 4 + 5: stage_number + final_stage match
    if release_staged_payload["stage_number"] != manifest.get("stage_number"):
        raise ReleaseConsistencyError(
            f"{context}: N2 invariant 4: release_staged.stage_number "
            f"{release_staged_payload['stage_number']} != manifest.stage_number "
            f"{manifest.get('stage_number')}"
        )
    if release_staged_payload["final_stage"] != manifest.get("final_stage"):
        raise ReleaseConsistencyError(
            f"{context}: N2 invariant 5: release_staged.final_stage "
            f"{release_staged_payload['final_stage']} != manifest.final_stage "
            f"{manifest.get('final_stage')}"
        )

    # Invariant 6: prior_stage_manifest_ref agreement
    prior_ref = release_staged_payload.get("prior_stage_manifest_ref")
    manifest_prior_ref = manifest.get("prior_stage_manifest_ref")
    if prior_ref or manifest_prior_ref:
        if not (prior_ref and manifest_prior_ref):
            raise ReleaseConsistencyError(
                f"{context}: N2 invariant 6: release_staged.prior_stage_manifest_ref "
                f"vs manifest.prior_stage_manifest_ref disagreement on presence "
                f"({prior_ref!r} vs {manifest_prior_ref!r})"
            )
        if prior_ref["manifest_hash"] != manifest_prior_ref["manifest_hash"]:
            raise ReleaseConsistencyError(
                f"{context}: N2 invariant 6: prior_stage_manifest_ref hash mismatch"
            )
        # Resolve prior manifest; verify its hash + stage_number match
        prior_manifest_resolved = prior_manifest_resolver(prior_ref)
        if prior_manifest_resolved is None:
            raise ReleaseConsistencyError(
                f"{context}: N2 invariant 6: prior_stage_manifest_ref names "
                f"manifest_hash {prior_ref['manifest_hash']!r} but no such manifest "
                f"resolves"
            )
        prior_actual_hash, prior_manifest = prior_manifest_resolved
        if prior_actual_hash != prior_ref["manifest_hash"]:
            raise ReleaseConsistencyError(
                f"{context}: N2 invariant 6: prior manifest actual hash "
                f"{prior_actual_hash!r} != ref hash {prior_ref['manifest_hash']!r}"
            )
        if prior_manifest.get("stage_number") != prior_ref["stage_number"]:
            raise ReleaseConsistencyError(
                f"{context}: N2 invariant 6: prior manifest stage_number "
                f"{prior_manifest.get('stage_number')!r} != ref stage_number "
                f"{prior_ref['stage_number']!r}"
            )

    # Invariant 7: every released rev_id appears in Reservation released_revision_ids[]
    for ev in per_object_released_events:
        uuid = ev["payload"]["object_uuid"]
        rev_id = ev["payload"]["revision_id"]
        res_entry = reservation_resolver(uuid)
        if res_entry is None:
            raise ReleaseConsistencyError(
                f"{context}: N2 invariant 7: Object {uuid} released as rev_id "
                f"{rev_id!r} but no Reservation entry found"
            )
        if rev_id not in (res_entry.get("released_revision_ids") or []):
            raise ReleaseConsistencyError(
                f"{context}: N2 invariant 7: Object {uuid} released rev_id "
                f"{rev_id!r} not in Reservation released_revision_ids[] "
                f"({res_entry.get('released_revision_ids')!r})"
            )


def validate_release_draft(
    workspace: Path, bundle_dir: Path, draft: ReleaseDraft,
    registry: BundleRegistry | None = None,
) -> None:
    """Draft-mode: validate a proposed release Transaction BEFORE writes.

    `draft` carries the in-memory proposed manifest, the proposed
    release_staged event, the proposed per-Object <type>_released events,
    and the proposed Reservation updates (full post-update reservation dicts
    keyed by prefix).
    """
    # Resolver functions consult the proposed draft state (not on-disk).
    def reservation_resolver(obj_uuid: str) -> dict[str, Any] | None:
        for prefix, prop in draft.reservation_updates.items():
            for number, entry in prop.get("reservations", {}).items():
                if entry.get("object_uuid") == obj_uuid:
                    return entry
        # Fall back to on-disk Reservation (for Objects not updated by this draft)
        found = find_reservation_entry_by_uuid(workspace, obj_uuid)
        return found[2] if found else None

    def prior_manifest_resolver(prior_ref: dict[str, Any]):
        # Per B11 absorption arc 20260531-2 round-5: hash-authoritative
        # resolution. Walk every release on disk; match by manifest_hash.
        # release_label is optional convenience metadata.
        from ..truth_model.manifest import list_release_labels
        target_hash = prior_ref["manifest_hash"]
        for label in list_release_labels(workspace):
            try:
                pm = load_manifest_validated(workspace, label, registry=registry)
            except Exception:
                continue
            pm_path = manifest_path(workspace, label)
            pmh = "sha256:" + hashlib.sha256(pm_path.read_bytes()).hexdigest()
            if pmh == target_hash:
                return pmh, pm
        # Fallback: if label hint provided, try direct lookup
        label_hint = prior_ref.get("release_label")
        if label_hint:
            try:
                pm = load_manifest_validated(workspace, label_hint, registry=registry)
                pmh = "sha256:" + hashlib.sha256(
                    manifest_path(workspace, label_hint).read_bytes()
                ).hexdigest()
                if pmh == target_hash:
                    return pmh, pm
            except Exception:
                pass
        return None

    _check_release_staged_against(
        draft.release_staged_event["payload"],
        draft.manifest,
        draft.per_object_released_events,
        reservation_resolver,
        draft.manifest_hash,
        prior_manifest_resolver,
        f"draft release {draft.release_label!r}",
    )


def resolve_prior_stage_chain(
    workspace: Path, bundle_dir: Path,
    prior_stage_ref: dict[str, Any] | None,
    registry: BundleRegistry | None = None,
) -> list[dict[str, Any]]:
    """Per B14 absorption arc 20260531-2 round-6: walk the authoritative
    `prior_stage_manifest_ref` chain (NOT every release on disk).

    Returns a list of prior manifests in oldest-to-newest order. Empty list
    if no prior stage. Raises ReleaseConsistencyError if any prior manifest
    in the chain is unresolvable or fails hash verification.
    """
    if not prior_stage_ref:
        return []
    chain: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    current_ref: dict[str, Any] | None = prior_stage_ref
    while current_ref is not None:
        target_hash = current_ref["manifest_hash"]
        if target_hash in seen_hashes:
            raise ReleaseConsistencyError(
                f"Cycle in prior_stage_manifest_ref chain at hash {target_hash}"
            )
        seen_hashes.add(target_hash)
        # Find the manifest matching this hash; recompute by reading bytes
        found = None
        for label in list_release_labels(workspace):
            try:
                pm = load_manifest_validated(workspace, label, registry=registry)
            except Exception:
                continue
            pm_path = manifest_path(workspace, label)
            pmh = "sha256:" + hashlib.sha256(pm_path.read_bytes()).hexdigest()
            if pmh == target_hash:
                found = pm
                break
        if found is None:
            raise ReleaseConsistencyError(
                f"prior_stage_manifest_ref names manifest_hash {target_hash} "
                f"but no on-disk manifest matches"
            )
        chain.insert(0, found)  # build oldest-first
        current_ref = found.get("prior_stage_manifest_ref")
    return chain


def _load_revision_content(
    workspace: Path, obj_uuid: str, rev_id: str,
    registry: BundleRegistry | None = None,
) -> dict[str, Any] | None:
    """Load the released Revision file content (authoritative for prior-stage Objects)."""
    from ..truth_model.revision import load_revision
    try:
        return load_revision(workspace, obj_uuid, rev_id)
    except FileNotFoundError:
        return None


def validate_stage_dependency_closure(
    workspace: Path, bundle_dir: Path, draft: ReleaseDraft,
    registry: BundleRegistry | None = None,
) -> None:
    """B11 + B14 absorption: per ADR/0025 §7, a stage's release set must
    satisfy dependency closure — every Fixed endpoint of a same-stage released
    Object's PROPOSED Revision content must resolve to either:
      (a) the same stage's release set (matched by uuid + proposed rev_id), OR
      (b) a Revision released by a prior stage IN THE CHAIN (not unrelated
          releases elsewhere in the workspace).

    Raises ReleaseConsistencyError on violation.
    """
    same_stage_revs: dict[str, str] = {}  # uuid -> rev_id for this stage
    for rev in draft.manifest.get("revisions", []):
        same_stage_revs[rev["object_uuid"]] = rev["revision_id"]

    # Walk the prior_stage_manifest_ref chain (NOT every release label)
    prior_chain = resolve_prior_stage_chain(
        workspace, bundle_dir,
        draft.manifest.get("prior_stage_manifest_ref"),
        registry=registry,
    )
    prior_released: dict[str, set[str]] = {}
    for pm in prior_chain:
        for rev in pm.get("revisions", []):
            prior_released.setdefault(rev["object_uuid"], set()).add(rev["revision_id"])

    # For each same-stage released Object, walk relationships in the PROPOSED
    # Revision content (from draft.revision_writes), NOT the working sidecar.
    for (obj_uuid, rev_id), revision_content in draft._iter_proposed_revisions():
        for rel in revision_content.get("relationship", []):
            if rel.get("type") not in EXECUTION_INSTANCE_TYPES:
                continue
            if rel.get("binding") != "fixed":
                continue
            target_uuid, target_rev = target_endpoint_uuid_rev(rel)
            if not target_uuid or not target_rev:
                continue
            # (a) Same stage
            if same_stage_revs.get(target_uuid) == target_rev:
                continue
            # (b) Prior stage IN CHAIN
            if target_rev in prior_released.get(target_uuid, set()):
                continue
            raise ReleaseConsistencyError(
                f"Stage dependency closure: Object {obj_uuid} (proposed Revision "
                f"{rev_id}) has Fixed execution-instance relationship endpoint "
                f"(target={target_uuid}, revision_id={target_rev}) that resolves "
                f"neither to same-stage release set nor any prior-stage chain "
                f"released Revision. Stage must include the target or release it first."
            )


def _cumulative_released_revisions(
    workspace: Path, bundle_dir: Path, draft: ReleaseDraft,
    registry: BundleRegistry | None = None,
) -> dict[str, dict[str, Any]]:
    """Per B14 absorption arc 20260531-2 round-6: build the cumulative release
    graph by walking the prior_stage_manifest_ref chain (NOT every release
    label) + adding same-stage proposed Revisions.

    Returns dict {object_uuid → Revision content} where:
    - For same-stage Objects: content comes from draft.proposed_revisions
      (proposed Revision, NOT working sidecar).
    - For prior-stage Objects: content comes from the released Revision files
      named by prior-chain manifests (NOT working sidecars; those may have
      mutated after release).
    """
    cumulative: dict[str, dict[str, Any]] = {}

    # Prior-stage chain
    prior_chain = resolve_prior_stage_chain(
        workspace, bundle_dir,
        draft.manifest.get("prior_stage_manifest_ref"),
        registry=registry,
    )
    for pm in prior_chain:
        for rev in pm.get("revisions", []):
            content = _load_revision_content(
                workspace, rev["object_uuid"], rev["revision_id"], registry=registry,
            )
            if content is not None:
                cumulative[rev["object_uuid"]] = content

    # Same-stage proposed (overrides prior; though Objects shouldn't appear in both)
    for (obj_uuid, _rev_id), content in draft.proposed_revisions.items():
        cumulative[obj_uuid] = content

    return cumulative


def validate_final_stage_cardinality(
    workspace: Path, bundle_dir: Path, draft: ReleaseDraft,
    registry: BundleRegistry | None = None,
) -> list[dict[str, str]]:
    """B11 + B14: per ADR/0022 §3-§5 + ADR/0025 §7, final stage validates
    execution cardinality across the COMPLETE release graph (cumulative
    Revisions per B14 — chain manifests + proposed Revisions, not working
    sidecars).

    Hard-fails: executes == 1, executed_on >= 1.
    Diagnostic (NOT hard-fail): produces >= 1 for completed status.
    """
    outcomes: list[dict[str, str]] = []
    cumulative = _cumulative_released_revisions(workspace, bundle_dir, draft, registry=registry)

    for uuid, content in sorted(cumulative.items()):
        if content.get("object", {}).get("type") != "TestExecution":
            continue
        obj_number = content["object"]["number"]
        rels = content.get("relationship", [])
        executes = [r for r in rels if r.get("type") == "executes"]
        executed_on = [r for r in rels if r.get("type") == "executed_on"]
        produces = [r for r in rels if r.get("type") == "produces"]
        status = content.get("test_execution", {}).get("execution_status", "completed")

        if len(executes) != 1:
            raise ReleaseConsistencyError(
                f"Final-stage cardinality: {obj_number} executes count = {len(executes)} "
                f"(must be exactly 1 per ADR/0022 §3)"
            )
        if len(executed_on) < 1:
            raise ReleaseConsistencyError(
                f"Final-stage cardinality: {obj_number} executed_on count = "
                f"{len(executed_on)} (must be ≥1 per ADR/0022 §4)"
            )
        diag = ""
        if status == "completed" and len(produces) < 1:
            diag = (
                f"  DIAGNOSTIC (not hard-fail per ADR/0022 §5): completed TestExecution "
                f"with no produces records"
            )
        outcomes.append({
            "check_name": f"execution_cardinality({obj_number})",
            "result": "PASS",
            "details": f"executes=1; executed_on={len(executed_on)}; produces={len(produces)} ({status}){diag}",
        })
    return outcomes


# ---------------- B16: attachment integrity + lineage (per-stage) ----------------


def validate_attachment_integrity(
    workspace: Path, bundle_dir: Path, draft: ReleaseDraft,
    registry: BundleRegistry | None = None,
) -> list[dict[str, str]]:
    """B16 absorption arc 20260531-2 round-7: per ADR/0017 §2 + ADR/0024,
    every Attachment-bearing Object released in THIS stage must have its
    Vault bytes re-readable + matching the embedded content_hash.

    Operates on the same-stage Objects from draft.proposed_revisions (the
    authoritative content being released). Prior-stage attachments were
    verified when their stage was released and are skipped here.

    Returns one validation_outcomes entry per Attachment-bearing same-stage
    Object's attachment record. Raises AttachmentIntegrityError on mismatch.
    """
    outcomes: list[dict[str, str]] = []
    vault = LocalFSVaultAdapter(workspace)
    for (obj_uuid, _rev_id), content in draft.proposed_revisions.items():
        obj_type = content.get("object", {}).get("type")
        if obj_type not in _ATTACHMENT_BEARING_TYPES:
            continue
        obj_number = content["object"]["number"]
        for att in content.get("attachment", []):
            att_id = att["id"]
            content_hash = att["content_hash"]
            check_name = f"attachment_integrity({att_id})"
            try:
                vault.verify(content_hash)
            except AttachmentIntegrityError as e:
                raise AttachmentIntegrityError(
                    f"{obj_number}.attachment[{att_id}]: {e}"
                ) from e
            outcomes.append({
                "check_name": check_name,
                "result": "PASS",
                "details": (
                    f"Re-hashed Vault bytes for {att_id} match {obj_number} "
                    f"Revision embedded content_hash"
                ),
            })
    return outcomes


def validate_attachment_lineage(
    workspace: Path, bundle_dir: Path, draft: ReleaseDraft,
    registry: BundleRegistry | None = None,
) -> list[dict[str, str]]:
    """B16: port of Wedge-002 spike's two-tier validator per ADR/0017 §2
    D7-escape + ADR/0024 §"Pre-declared constraints honored":

    Universal scope (all 4 Attachment-bearing types):
    - ≥1 source_authoring attachment present at release;
    - derived-role attachment chain terminates at source_authoring without cycles.

    Lineage-specific scope (EvidenceArtifact + TestExecution only; NOT
    TestProcedure per ADR/0020 §4):
    - parameter→attachment lineage refs resolve to same-Revision attachment ids.

    Returns one validation_outcomes entry per Attachment-bearing same-stage
    Object. Raises AttachmentIntegrityError on violation (exit code 8).
    """
    outcomes: list[dict[str, str]] = []
    for (obj_uuid, _rev_id), content in draft.proposed_revisions.items():
        obj_type = content.get("object", {}).get("type")
        if obj_type not in _ATTACHMENT_BEARING_TYPES:
            continue
        obj_number = content["object"]["number"]
        attachments = content.get("attachment", [])
        att_by_id = {att["id"]: att for att in attachments}

        # Universal check 1: ≥1 source_authoring attachment
        source_authoring_atts = [a for a in attachments if a["role"] == "source_authoring"]
        if not source_authoring_atts:
            raise AttachmentIntegrityError(
                f"{obj_number}: released Attachment-bearing Revision has NO "
                f"source_authoring attachment (required per ADR/0017 §2 D7-escape; "
                f"inherited by ADR/0019/0020/0022)"
            )

        # Universal check 2: derived-role chains terminate at source_authoring; no cycles
        for att in attachments:
            if att["role"] == "source_authoring":
                continue
            visited: set[str] = set()
            current_id: str | None = att["id"]
            while current_id is not None:
                if current_id in visited:
                    raise AttachmentIntegrityError(
                        f"{obj_number}.attachment[{att['id']}]: derived_from chain "
                        f"has cycle (visited: {sorted(visited)})"
                    )
                visited.add(current_id)
                if current_id not in att_by_id:
                    raise AttachmentIntegrityError(
                        f"{obj_number}.attachment[{att['id']}]: derived chain link "
                        f"{current_id!r} not in same Revision"
                    )
                current = att_by_id[current_id]
                if current["role"] == "source_authoring":
                    break  # terminated correctly
                next_id = current.get("derived_from_attachment_id")
                if next_id is None:
                    raise AttachmentIntegrityError(
                        f"{obj_number}.attachment[{att['id']}]: derived chain does not "
                        f"terminate at source_authoring (broke at {current_id!r})"
                    )
                current_id = next_id

        # Lineage-specific check (EVD + TEX only)
        details_parts = [
            "source_authoring present",
            "derived-role attachment chain terminates at source_authoring without cycles",
        ]
        if obj_type in _LINEAGE_BEARING_TYPES:
            for param in content.get("parameter", []):
                pid = param.get("id")
                derived_from = param.get("fact_provenance", {}).get("derived_from", [])
                attachment_refs = [d for d in derived_from if d.startswith("attachment:")]
                if not attachment_refs:
                    raise AttachmentIntegrityError(
                        f"{obj_number}.parameter[{pid}]: no `attachment:<id>` lineage "
                        f"reference in fact_provenance.derived_from "
                        f"(required per ADR/0019 §4 / ADR/0022 §11)"
                    )
                for ref in attachment_refs:
                    att_id = ref[len("attachment:"):]
                    if att_id not in att_by_id:
                        raise AttachmentIntegrityError(
                            f"{obj_number}.parameter[{pid}]: lineage ref {ref!r} does "
                            f"not resolve to any attachment in same Revision "
                            f"(attachment ids: {sorted(att_by_id.keys())})"
                        )
            details_parts.append(
                "all parameter→attachment lineage refs resolve to same-Revision attachment records"
            )

        outcomes.append({
            "check_name": f"attachment_lineage({obj_number})",
            "result": "PASS",
            "details": "; ".join(details_parts),
        })
    return outcomes


# ---------------- B13: V&V chain integrity at final-stage release ----------------


def validate_final_stage_vv_chain_integrity(
    workspace: Path, bundle_dir: Path, draft: ReleaseDraft,
    registry: BundleRegistry | None = None,
) -> list[dict[str, str]]:
    """B13 absorption arc 20260531-2 round-6: port Wedge-002 spike's V&V chain
    integrity check to v0.20.0 runtime. Per ADR/0025 §7 + ADR/0024 Decision §D:
    every released Part with a `tested_against` relationship must have a
    complete chain closure
    `Part →tested_against→ TST ←executes← TEX →executed_on→ same-Part
                                     →produces→ EVD ←cites← REQ ←verifies← TST`.

    Uses cumulative release graph per B14 (Revisions, not working sidecars).
    Returns validation_outcomes entries. Hard-fails on broken chain when a
    Part has any tested_against; emits one outcome per chain Part-by-Part.
    """
    outcomes: list[dict[str, str]] = []
    cumulative = _cumulative_released_revisions(workspace, bundle_dir, draft, registry=registry)

    by_type: dict[str, list[dict[str, Any]]] = {}
    for uuid, content in cumulative.items():
        by_type.setdefault(content["object"]["type"], []).append(content)

    parts = by_type.get("Part", [])
    test_procs = {o["object"]["uuid"]: o for o in by_type.get("TestProcedure", [])}
    test_execs = by_type.get("TestExecution", [])
    evidences = {o["object"]["uuid"]: o for o in by_type.get("EvidenceArtifact", [])}
    reqs = {o["object"]["uuid"]: o for o in by_type.get("Requirement", [])}

    def _rels(sidecar, type_name):
        return [r for r in sidecar.get("relationship", []) if r.get("type") == type_name]

    any_tested_against = False
    complete_chains = 0
    chain_steps: list[str] = []

    for part in parts:
        part_uuid = part["object"]["uuid"]
        part_num = part["object"]["number"]
        for ta in _rels(part, "tested_against"):
            any_tested_against = True
            for ep in ta.get("endpoints", []):
                tp_uuid = ep["object_uuid"]
                if tp_uuid not in test_procs:
                    raise ReleaseConsistencyError(
                        f"V&V chain: {part_num} tested_against {tp_uuid} but "
                        f"TestProcedure not in cumulative release set"
                    )
                tp = test_procs[tp_uuid]
                tp_num = tp["object"]["number"]
                chain_steps.append(f"{part_num} →tested_against→ {tp_num}")

                executing_texs = [
                    tex for tex in test_execs
                    if any(
                        e["object_uuid"] == tp_uuid
                        for r in _rels(tex, "executes")
                        for e in r.get("endpoints", [])
                    )
                ]
                for tex in executing_texs:
                    tex_num = tex["object"]["number"]
                    eo_targets = {
                        e["object_uuid"]
                        for r in _rels(tex, "executed_on")
                        for e in r.get("endpoints", [])
                    }
                    if part_uuid not in eo_targets:
                        raise ReleaseConsistencyError(
                            f"V&V chain: {tex_num} executes {tp_num} but does NOT "
                            f"executed_on {part_num} (executed_on targets: "
                            f"{sorted(eo_targets)}) — chain not closed"
                        )
                    chain_steps.append(f"{tex_num} →executes→ {tp_num}")
                    chain_steps.append(f"{tex_num} →executed_on→ {part_num} (same Part ✓)")

                    produced = [
                        e["object_uuid"]
                        for r in _rels(tex, "produces")
                        for e in r.get("endpoints", [])
                    ]
                    for evd_uuid in produced:
                        if evd_uuid not in evidences:
                            raise ReleaseConsistencyError(
                                f"V&V chain: {tex_num} produces {evd_uuid} but "
                                f"EvidenceArtifact not in cumulative release set"
                            )
                        evd = evidences[evd_uuid]
                        evd_num = evd["object"]["number"]
                        chain_steps.append(f"{tex_num} →produces→ {evd_num}")

                        citing_reqs = [
                            req for req in reqs.values()
                            if any(
                                e["object_uuid"] == evd_uuid
                                for r in _rels(req, "cites")
                                for e in r.get("endpoints", [])
                            )
                        ]
                        for req in citing_reqs:
                            req_num = req["object"]["number"]
                            chain_steps.append(f"{req_num} →cites→ {evd_num}")

                            # Chain closure: TST verifies same Requirement
                            verifies_targets = []
                            for vr in _rels(tp, "verifies"):
                                for ve in vr.get("endpoints", []):
                                    verifies_targets.append(ve["object_uuid"])
                            if req["object"]["uuid"] not in verifies_targets:
                                raise ReleaseConsistencyError(
                                    f"V&V chain: not closed — {tp_num} does not verify "
                                    f"{req_num} which cites {evd_num} produced by {tex_num}"
                                )
                            chain_steps.append(f"{tp_num} →verifies→ {req_num} — CHAIN CLOSED")
                            complete_chains += 1

    if any_tested_against and complete_chains == 0:
        raise ReleaseConsistencyError(
            "V&V chain: cumulative release graph has tested_against relationship(s) "
            "but no complete chain found"
        )

    if complete_chains > 0:
        outcomes.append({
            "check_name": "vv_chain_integrity",
            "result": "PASS",
            "details": " | ".join(chain_steps),
        })
    return outcomes


def validate_release_replay(
    workspace: Path, bundle_dir: Path,
    registry: BundleRegistry | None = None,
) -> None:
    """Replay-mode: for every release_staged event in the event log, run the
    same invariants against on-disk manifest + Reservation state.
    """
    events = list(read_events(workspace, bundle_dir))
    for i, event in enumerate(events):
        if event["event_type"] != "release_staged":
            continue
        payload = event["payload"]
        tx_id = event["transaction_id"]
        label = payload["release_label"]

        # Manifest on disk
        try:
            manifest = load_manifest_validated(workspace, label, registry=registry)
        except FileNotFoundError as e:
            raise ReleaseConsistencyError(
                f"replay event {event['event_id']}: release_staged names "
                f"release_label {label!r} but manifest file missing: {e}"
            )

        # Manifest hash recomputed from canonical bytes
        manifest_path_actual = manifest_path(workspace, label)
        manifest_hash_actual = "sha256:" + hashlib.sha256(
            manifest_path_actual.read_bytes()
        ).hexdigest()

        # Per-Object <type>_released events emitted in the same Transaction
        per_obj_events = [
            ev for ev in events
            if ev.get("transaction_id") == tx_id
            and ev["event_type"].endswith("_released")
            and ev["event_type"] != "release_staged"
        ]

        def reservation_resolver(obj_uuid: str) -> dict[str, Any] | None:
            found = find_reservation_entry_by_uuid(workspace, obj_uuid)
            return found[2] if found else None

        def prior_manifest_resolver(prior_ref: dict[str, Any]):
            # Hash-authoritative per B11 absorption.
            from ..truth_model.manifest import list_release_labels
            target_hash = prior_ref["manifest_hash"]
            for plabel in list_release_labels(workspace):
                try:
                    pm = load_manifest_validated(workspace, plabel, registry=registry)
                except Exception:
                    continue
                pmh = "sha256:" + hashlib.sha256(
                    manifest_path(workspace, plabel).read_bytes()
                ).hexdigest()
                if pmh == target_hash:
                    return pmh, pm
            return None

        _check_release_staged_against(
            payload, manifest, per_obj_events,
            reservation_resolver, manifest_hash_actual,
            prior_manifest_resolver,
            f"replay event {event['event_id']} (release {label!r})",
        )
