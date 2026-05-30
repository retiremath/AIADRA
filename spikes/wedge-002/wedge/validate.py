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


# ---------------- Wedge-002 V&V validators ----------------


class VVChainIntegrityError(ValueError):
    pass


class AttachmentIntegrityError(ValueError):
    pass


class ExecutionCardinalityError(ValueError):
    pass


def _rels_of_type(sidecar: dict[str, Any], type_name: str) -> list[dict[str, Any]]:
    return [r for r in sidecar.get("relationship", []) if r.get("type") == type_name]


_ATTACHMENT_BEARING_TYPES = ("TestProcedure", "EvidenceArtifact", "TestExecution")
_LINEAGE_BEARING_TYPES = ("EvidenceArtifact", "TestExecution")


def validate_attachment_lineage(
    released_objects_by_uuid: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Per ADR/0024 §"Pre-declared constraints honored" + ADR/0017 §2 Attachment-
    bearing template (inherited by ADR/0019 / ADR/0020 / ADR/0022).

    Release-time validation of the canonical chain

        parameter -> derived_from -> attachment -> content_hash -> vault bytes

    plus the inherited ADR/0017 D7-escape invariant (every released Attachment-
    bearing Revision MUST have at least one `source_authoring` attachment; all
    derived-role attachments terminate the `derived_from_attachment_id` chain
    at a `source_authoring` record without cycles).

    Two-tier scope (per Codex3 B1 absorption arc 20260530-3):

    - **Universal (all three Attachment-bearing Wedge-002 types — TestProcedure
      / EvidenceArtifact / TestExecution):** source_authoring presence at
      release; derived-role chain termination + no cycles.
    - **Parameter-lineage-bearing (EvidenceArtifact + TestExecution only,
      per ADR/0019 §4 + ADR/0022 §11; TestProcedure parameters are nominal
      design facts with NO derived_from discipline per ADR/0020 §4):** every
      parameter's `fact_provenance.derived_from` contains ≥1 `attachment:<id>`
      reference that resolves to a same-Revision attachment.

    Raises AttachmentIntegrityError on any violation (exit code 8). Emits one
    `attachment_lineage(<object_number>)` validation_outcomes entry per
    Attachment-bearing Object whose lineage validates.
    """
    outcomes: list[dict[str, Any]] = []
    for uuid, sidecar in released_objects_by_uuid.items():
        obj_type = sidecar["object"]["type"]
        if obj_type not in _ATTACHMENT_BEARING_TYPES:
            continue
        obj_number = sidecar["object"]["number"]
        attachments = sidecar.get("attachment", [])
        att_by_id = {att["id"]: att for att in attachments}

        # Universal check 1 (per ADR/0017 §2 D7-escape; inherited by ADR/0019
        # /0020 /0022): every released Attachment-bearing Revision MUST have
        # at least one source_authoring attachment.
        source_authoring_atts = [a for a in attachments if a["role"] == "source_authoring"]
        if not source_authoring_atts:
            raise AttachmentIntegrityError(
                f"{obj_number}: released Attachment-bearing Revision has NO "
                f"source_authoring attachment (required per ADR/0017 §2 D7-escape; "
                f"inherited by ADR/0019/0020/0022)"
            )

        # Universal check 2: derived-role attachment chains terminate at
        # source_authoring without cycles.
        for att in attachments:
            if att["role"] == "source_authoring":
                continue
            visited: set[str] = set()
            current_id: str | None = att["id"]
            while current_id is not None:
                if current_id in visited:
                    raise AttachmentIntegrityError(
                        f"{obj_number}.attachment[{att['id']}]: derived_from chain has cycle "
                        f"(visited: {sorted(visited)})"
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

        # Lineage-specific check (EvidenceArtifact + TestExecution only):
        # parameter -> derived_from -> attachment same-Revision resolution.
        # TestProcedure SKIPS this check because its parameters are nominal
        # design facts with no derived_from lineage discipline per ADR/0020 §4.
        details_parts = [
            "source_authoring present",
            "derived-role attachment chain terminates at source_authoring without cycles",
        ]
        if obj_type in _LINEAGE_BEARING_TYPES:
            for param in sidecar.get("parameter", []):
                pid = param.get("id")
                derived_from = param.get("fact_provenance", {}).get("derived_from", [])
                attachment_refs = [d for d in derived_from if d.startswith("attachment:")]
                if not attachment_refs:
                    raise AttachmentIntegrityError(
                        f"{obj_number}.parameter[{pid}]: no `attachment:<id>` lineage reference "
                        f"in fact_provenance.derived_from (required per ADR/0019 §4 / ADR/0022 §11)"
                    )
                for ref in attachment_refs:
                    att_id = ref[len("attachment:"):]
                    if att_id not in att_by_id:
                        raise AttachmentIntegrityError(
                            f"{obj_number}.parameter[{pid}]: lineage ref {ref!r} does not "
                            f"resolve to any attachment in same Revision "
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


def verify_attachment_integrity(
    workspace: Path,
    released_objects_by_uuid: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """For each attachment record in each released Revision, re-read Vault
    bytes and verify SHA-256 matches embedded content_hash. Returns
    validation_outcomes entries (per Codex1 N3 absorption from arc 20260530-2:
    attachment hashes are transitively pinned via Revision content;
    `attachment_integrity` lands as validation_outcomes entries, NOT a new
    top-level manifest section).
    """
    from . import vault

    outcomes: list[dict[str, Any]] = []
    for uuid, sidecar in released_objects_by_uuid.items():
        obj_number = sidecar["object"]["number"]
        for att in sidecar.get("attachment", []):
            att_id = att["id"]
            content_hash = att["content_hash"]
            check_name = f"attachment_integrity({att_id})"
            try:
                vault.verify(workspace, content_hash)
                outcomes.append({
                    "check_name": check_name,
                    "result": "PASS",
                    "details": (
                        f"Re-hashed Vault bytes for {att_id} match {obj_number} "
                        f"Revision embedded content_hash"
                    ),
                })
            except vault.AttachmentIntegrityError as e:
                raise AttachmentIntegrityError(str(e)) from e
    return outcomes


def validate_execution_cardinality(
    released_objects_by_uuid: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Per ADR/0022 §8: `executes` exactly 1; `executed_on` >=1; `produces`
    >=0 globally with `completed` SHOULD >=1 diagnostic. The `executes==1`
    and `executed_on>=1` are hard-fail; the status-sensitive `produces` for
    `completed` is a DIAGNOSTIC, not hard-fail (per ADR/0022 §5)."""
    outcomes: list[dict[str, Any]] = []
    for uuid, sidecar in released_objects_by_uuid.items():
        if sidecar["object"]["type"] != "TestExecution":
            continue
        tex_number = sidecar["object"]["number"]
        executes_rels = _rels_of_type(sidecar, "executes")
        executed_on_rels = _rels_of_type(sidecar, "executed_on")
        produces_rels = _rels_of_type(sidecar, "produces")
        status = sidecar.get("test_execution", {}).get("execution_status", "completed")

        if len(executes_rels) != 1:
            raise ExecutionCardinalityError(
                f"{tex_number}: executes cardinality must be exactly 1, found {len(executes_rels)}"
            )
        if len(executed_on_rels) < 1:
            raise ExecutionCardinalityError(
                f"{tex_number}: executed_on cardinality must be >=1, found {len(executed_on_rels)}"
            )
        produces_msg = f"produces=={len(produces_rels)}"
        diagnostic = ""
        if status == "completed" and len(produces_rels) < 1:
            diagnostic = (
                f"  DIAGNOSTIC (not hard-fail per ADR/0022 §5): completed TestExecution "
                f"with no produces records; verify execution-evidence linkage is intended"
            )
        outcomes.append({
            "check_name": f"execution_cardinality({tex_number})",
            "result": "PASS",
            "details": (
                f"executes==1 ✓; executed_on>={len(executed_on_rels)} ✓; "
                f"{produces_msg} ({status}){diagnostic}"
            ),
        })
    return outcomes


def _resolve_criterion_ref(ref: str, requirement_sidecar: dict[str, Any]) -> None:
    """Spike-local helper — verify `acceptance_criterion:ac_<id>` reference
    resolves to an actual acceptance_criterion id on the Requirement. Raises
    SchemaValidationError on dangling reference per [ADR/0021 §6]."""
    if not ref.startswith("acceptance_criterion:"):
        raise SchemaValidationError(f"Bad criterion ref format: {ref!r}")
    ac_id = ref[len("acceptance_criterion:"):]
    ac_ids = {ac["id"] for ac in requirement_sidecar.get("acceptance_criterion", [])}
    if ac_id not in ac_ids:
        raise SchemaValidationError(
            f"Dangling criterion ref {ref!r}: Requirement "
            f"{requirement_sidecar['object']['number']} has no acceptance_criterion "
            f"with id {ac_id!r}"
        )


def validate_v_and_v_chain_integrity(
    released_objects_by_uuid: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """V&V chain integrity check per ADR/0024 Decision §D + Codex1 B5 absorption.

    For each released Part:
      Part →tested_against→ TestProcedure
           ←executes← TestExecution →executed_on→ same Part   (B5 same-Part check)
                                   →produces→ EvidenceArtifact
                                               ←cites← Requirement
           ←verifies← TestProcedure                            (chain closure)

    Plus Layer-2 criterion-level dangling-ref resolution for `verifies`
    (target-side endpoints[].fact_ref) and `cites` (source-side
    source_fact_ref) per ADR/0021 §6.

    Per Codex1 B5 absorption: the Wedge-002 demo MUST have at least one
    complete chain; "no chain" is not PASS for this release path.
    """
    parts = [o for o in released_objects_by_uuid.values() if o["object"]["type"] == "Part"]
    test_procs = {o["object"]["uuid"]: o for o in released_objects_by_uuid.values() if o["object"]["type"] == "TestProcedure"}
    test_execs = [o for o in released_objects_by_uuid.values() if o["object"]["type"] == "TestExecution"]
    evidences = {o["object"]["uuid"]: o for o in released_objects_by_uuid.values() if o["object"]["type"] == "EvidenceArtifact"}
    reqs = {o["object"]["uuid"]: o for o in released_objects_by_uuid.values() if o["object"]["type"] == "Requirement"}

    chain_steps: list[str] = []
    complete_chains = 0

    for part in parts:
        part_uuid = part["object"]["uuid"]
        part_num = part["object"]["number"]
        for ta in _rels_of_type(part, "tested_against"):
            for ep in ta.get("endpoints", []):
                tp_uuid = ep["object_uuid"]
                if tp_uuid not in test_procs:
                    raise VVChainIntegrityError(
                        f"{part_num} tested_against {tp_uuid} but TestProcedure not in release set"
                    )
                tp = test_procs[tp_uuid]
                tp_num = tp["object"]["number"]
                chain_steps.append(f"{part_num} →tested_against→ {tp_num}")

                executing_texs = [
                    tex for tex in test_execs
                    if any(
                        e["object_uuid"] == tp_uuid
                        for r in _rels_of_type(tex, "executes")
                        for e in r.get("endpoints", [])
                    )
                ]
                for tex in executing_texs:
                    tex_num = tex["object"]["number"]
                    eo_targets = {
                        e["object_uuid"]
                        for r in _rels_of_type(tex, "executed_on")
                        for e in r.get("endpoints", [])
                    }
                    # B5: same-Part check
                    if part_uuid not in eo_targets:
                        raise VVChainIntegrityError(
                            f"{tex_num} executes {tp_num} but does NOT executed_on {part_num} "
                            f"(executed_on targets: {sorted(eo_targets)}) — chain not closed for this Part"
                        )
                    chain_steps.append(f"{tex_num} →executes→ {tp_num}")
                    chain_steps.append(f"{tex_num} →executed_on→ {part_num} (same Part ✓)")

                    produced = [
                        e["object_uuid"]
                        for r in _rels_of_type(tex, "produces")
                        for e in r.get("endpoints", [])
                    ]
                    for evd_uuid in produced:
                        if evd_uuid not in evidences:
                            raise VVChainIntegrityError(
                                f"{tex_num} produces {evd_uuid} but EvidenceArtifact not in release set"
                            )
                        evd = evidences[evd_uuid]
                        evd_num = evd["object"]["number"]
                        chain_steps.append(f"{tex_num} →produces→ {evd_num}")

                        citing_reqs = [
                            req for req in reqs.values()
                            if any(
                                e["object_uuid"] == evd_uuid
                                for r in _rels_of_type(req, "cites")
                                for e in r.get("endpoints", [])
                            )
                        ]
                        for req in citing_reqs:
                            req_num = req["object"]["number"]
                            # cites source_fact_ref dangling check
                            for cr in _rels_of_type(req, "cites"):
                                if "source_fact_ref" in cr:
                                    _resolve_criterion_ref(cr["source_fact_ref"], req)
                            chain_steps.append(f"{req_num} →cites→ {evd_num}")

                            # Chain closure: TestProcedure →verifies→ same Requirement
                            verifies_targets = []
                            for vr in _rels_of_type(tp, "verifies"):
                                for ve in vr.get("endpoints", []):
                                    verifies_targets.append(ve["object_uuid"])
                                    # Target-side fact_ref dangling check
                                    if "fact_ref" in ve and ve["object_uuid"] == req["object"]["uuid"]:
                                        _resolve_criterion_ref(ve["fact_ref"], req)
                            if req["object"]["uuid"] not in verifies_targets:
                                raise VVChainIntegrityError(
                                    f"Chain not closed: {tp_num} does not verify {req_num} "
                                    f"which cites {evd_num} produced by {tex_num}"
                                )
                            chain_steps.append(
                                f"{tp_num} →verifies→ {req_num} — CHAIN CLOSED"
                            )
                            complete_chains += 1

    if complete_chains == 0:
        # B5: require at least one complete chain for Wedge-002 demo release.
        raise VVChainIntegrityError(
            "Wedge-002 release requires at least one complete V&V chain; "
            "none found among released Objects"
        )

    return {
        "check_name": "vv_chain_integrity",
        "result": "PASS",
        "details": " | ".join(chain_steps),
    }
