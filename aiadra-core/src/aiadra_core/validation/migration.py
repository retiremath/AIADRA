"""Bundle migrator per ADR/0003 §10 — deterministic + dry-run + idempotent.

Phase 1 (arc 20260531-2): first flat migrator v0.19.0 → v0.20.0.
Phase 2 (arc 20260531-3): added flat v0.20.0 → v0.21.0.
Phase 3 W3 (arc 20260531-4): chain-aware refactor per Phase 2 close note —
adds `plan_migration(workspace, target_version)` / `apply_migration(...)`
that walk REGISTERED_STEPS from current pin to target. Multi-step chains
write the final pin ONCE atomically at end per Codex1 D8. Flat per-pair
functions retained as thin wrappers for backward-compat.

All registered W3-era migrators (v0.21.0 → v0.22.0 included) are pin-only:
the SCNs are MINOR additive (no data migration). The chain machinery is
designed so future migrators that DO mutate data plug in via a richer
MigrationStep.apply callable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..truth_model.atomic import atomic_write_bytes
from .bundle_registry import (
    BundleDigestMismatchError,
    BundleRegistry,
)
from .profile import load_yaml


class MigrationError(ValueError):
    """Bundle migration failure."""


@dataclass
class MigrationPlan:
    from_bundle_version: str
    to_bundle_version: str
    workspace: Path
    pin_path: Path
    pin_will_change: bool
    new_pin_text: str
    notes: list[str]


@dataclass
class MigrationStep:
    """One bundle transition. `apply` is a hook for non-pin-only migrations.

    For Phase 3 the registered steps are all pin-only (MINOR additive bumps),
    so `apply` is a no-op lambda. Future MAJOR-bump migrators inject data
    transforms via the `apply` callable.
    """
    from_version: str
    to_version: str
    notes: list[str]
    apply: Callable[[Path, BundleRegistry], None] = field(
        default=lambda workspace, registry: None
    )


def _noop_data_apply(workspace: Path, registry: BundleRegistry) -> None:
    """Pin-only migrations make no data changes; pin write happens at chain end."""
    return None


REGISTERED_STEPS: list[MigrationStep] = [
    MigrationStep(
        from_version="0.19.0",
        to_version="0.20.0",
        notes=[
            "v0.19.0 → v0.20.0 is a MINOR additive bump (5 new event types + "
            "optional manifest staging fields + optional Reservation rev_id fields). "
            "All existing canonical artifacts validate unchanged; no data migration."
        ],
        apply=_noop_data_apply,
    ),
    MigrationStep(
        from_version="0.20.0",
        to_version="0.21.0",
        notes=[
            "v0.20.0 → v0.21.0 is a MINOR additive bump (optional "
            "`new_fact_provenance` field on `parameter_changed` event payload "
            "per F1 absorption). All existing canonical artifacts validate "
            "unchanged; no data migration."
        ],
        apply=_noop_data_apply,
    ),
    MigrationStep(
        from_version="0.21.0",
        to_version="0.22.0",
        notes=[
            "v0.21.0 → v0.22.0 is a MINOR additive bump (W3 SCN: bundle-organization "
            "refactor — `lookups.relationship` namespace + `_base.schema.json` "
            "factor-out + per-Object source-allowed-list + Object-schema `oneOf` "
            "drop). No artifact data changes; existing sidecars / Revisions / "
            "events / manifests / Reservations validate unchanged."
        ],
        apply=_noop_data_apply,
    ),
    MigrationStep(
        from_version="0.22.0",
        to_version="0.23.0",
        notes=[
            "v0.22.0 → v0.23.0 is a MINOR additive bump (F2 SCN: optional "
            "`acceptance_criterion[].threshold_expression` primitive + new "
            "`requirement_changed` event with added-only `acceptance_criterion_delta` "
            "payload per Codex1 B1 + shared `_shared/acceptance_criterion_item.schema.json`). "
            "All existing canonical artifacts validate unchanged; no data migration."
        ],
        apply=_noop_data_apply,
    ),
    MigrationStep(
        from_version="0.23.0",
        to_version="0.24.0",
        notes=[
            "v0.23.0 → v0.24.0 is a MINOR pin-only bump (Phase A: aiadra_core.protocol "
            "submodule formalization per ADR/0026 §\"Sequencing\"). Bundle layout is "
            "byte-identical to v0.23.0 except for _index.json bundle_version + "
            "_digest.json. No artifact data changes; existing sidecars / Revisions / "
            "events / manifests / Reservations validate unchanged. New protocol Python "
            "API + new rollback Transaction terminal + locality/staleness kwarg surface "
            "(defaulted no-op). CLI behavior unchanged for existing users."
        ],
        apply=_noop_data_apply,
    ),
    MigrationStep(
        from_version="0.24.0",
        to_version="0.25.0",
        notes=[
            "v0.24.0 → v0.25.0 is a MINOR pin-only bump (Phase B: aiadra_core.protocol "
            "gains `query(workspace, *, kind, filter, locality, staleness) → list[ObjectView]` "
            "operation over cumulative release graph + working set, and unlocks non-default "
            "locality/staleness behavior on both `inspect` and `query` per ADR/0026 §4). "
            "Bundle layout is byte-identical to v0.24.0 except _index.json + _digest.json. "
            "No artifact data changes; existing canonical artifacts validate unchanged. "
            "ObjectView gains optional `source` / `revision_id` / `release_label` fields "
            "(defaulted; backward-compat for Phase A callers). New `NetworkUnreachableError` "
            "exception for git-fetch failure surfaces (timeout / no remote / auth failure)."
        ],
        apply=_noop_data_apply,
    ),
    MigrationStep(
        from_version="0.25.0",
        to_version="0.26.0",
        notes=[
            "v0.25.0 → v0.26.0 is a MINOR pin-only bump (Phase C: aiadra_core.protocol "
            "gains `propose(workspace, kind, **kwargs) → TransactionDraft` + `modify(draft, "
            "mutation_spec) → TransactionDraft` + `propose_kinds() → tuple[str, ...]` per "
            "ADR/0026 §\"Sequencing\"). Bundle layout is byte-identical to v0.25.0 except "
            "_index.json + _digest.json. No artifact data changes. TransactionDraft gains "
            "private `_lifecycle_state` (open/committed/rolled_back) for terminal-state "
            "discipline per Codex1 B3 absorption. transaction.operations.* functions gain "
            "optional `existing_draft=` kwarg with draft-aware reads per Codex1 B1. "
            "propose(kind=\"change_parameter\") rejects new_fact_provenance.category="
            "\"human_input\" by default (agent attestation discipline per ADR/0026 §5 + "
            "Codex1 B4); CLI binding passes actor=\"human\" for human-attestation path. "
            "modify rejects kind=init + kind=release per Codex1 B2."
        ],
        apply=_noop_data_apply,
    ),
    MigrationStep(
        from_version="0.26.0",
        to_version="0.27.0",
        notes=[
            "v0.26.0 → v0.27.0 is a MINOR pin-only bump (Phase D: aiadra_core.protocol "
            "gains `simulate(draft) → ValidationReport` + `explain(workspace, ref, *, depth) "
            "→ ExplanationTree` + `explain_failure(failure, *, depth) → ExplanationTree` "
            "per ADR/0026 §\"Sequencing\"; closes 9-of-9 ADR/0026 §2 contract surface). "
            "Bundle layout is byte-identical to v0.26.0 except _index.json + _digest.json. "
            "No artifact data changes. NEW failed-Transaction audit log emission per "
            "ADR/0026 §9 — `.aiadra/audit/YYYY-MM-DD/tx_NNNN-failed-<short>.jsonl`; "
            "diagnostic-only NOT truth; NOT bundle-validated. NEW `.aiadra/audit-config.yaml` "
            "for retention (defaults: max_entries_per_agent=100, max_age_days=30, "
            "max_total_mb=50). `git_repo_dirty_for_aiadra_paths()` gains carve-out for "
            "`.aiadra/audit/` PREFIX (audit-config.yaml at the `.aiadra/` ROOT remains "
            "guarded). TransactionDraft gains private `_audit_emitted` flag + "
            "`audit_failure()` method + `_emit_audit_once()` helper per Codex1 B3 "
            "(single-record semantics). validate() refactored to delegate to "
            "_validate_internal(collect_failures=) per Codex1 B1; commit path raises "
            "on first fail; simulate path collects all FAIL outcomes with structured "
            "ExplanationNode tree. ValidationOutcome extended with optional `tree` field."
        ],
        apply=_noop_data_apply,
    ),
    MigrationStep(
        from_version="0.27.0",
        to_version="0.28.0",
        notes=[
            "v0.27.0 → v0.28.0 is a MINOR additive bump (ADR/0029 Part authoring "
            "SCN arc 20260531-13). NEW `part_changed` event with feature_delta + "
            "geometry_ref_delta payload (full add/update/remove semantics with "
            "Codex1 B3 atomic conflict rules). NEW shared schemas: "
            "`_shared/feature_record.schema.json` + `_shared/geometry_ref_record.schema.json` "
            "+ `_shared/canonical_unit.schema.json`. Part Object schema gains "
            "OPTIONAL `feature` + `geometry_ref` namespaces (both arrays). All "
            "existing v0.27.0 sidecars / Revisions / events validate unchanged. "
            "Fold + proposed-state fold gain `_apply_part_changed` handler with "
            "DAG acyclicity check (Codex1 B6: depends_on_feature_ids) + "
            "cascade-reject (no dangling references after delta application) + "
            "provenance discipline cross-check (Codex1 B4: feature records carry "
            "actor-derived provenance; geometry_ref records cross-check "
            "derived_from_feature_ids vs canonical `feature:<id>` form in "
            "fact_provenance.derived_from). Pre-condition for `aiadra-mechanical` "
            "Wedge-003 implementation per ADR/0027 D17 + ADR/0028 D14 step 2."
        ],
        apply=_noop_data_apply,
    ),
]


def _registered_step(from_v: str, to_v: str) -> MigrationStep | None:
    for s in REGISTERED_STEPS:
        if s.from_version == from_v and s.to_version == to_v:
            return s
    return None


def _chain_from_to(from_v: str, to_v: str) -> list[MigrationStep]:
    """Resolve the chain of MigrationSteps walking from `from_v` to `to_v`.

    Raises MigrationError if no chain exists.
    """
    if from_v == to_v:
        return []
    chain: list[MigrationStep] = []
    cur = from_v
    visited = {cur}
    while cur != to_v:
        nxt = next(
            (s for s in REGISTERED_STEPS if s.from_version == cur),
            None,
        )
        if nxt is None:
            raise MigrationError(
                f"No registered migration step from {cur!r}; cannot reach {to_v!r} "
                f"from {from_v!r}."
            )
        if nxt.to_version in visited:
            raise MigrationError(
                f"Migration chain cycle detected at {nxt.to_version!r}."
            )
        visited.add(nxt.to_version)
        chain.append(nxt)
        cur = nxt.to_version
    return chain


def _pin_text(version: str, digest: str) -> str:
    return f'"bundle_version": "{version}"\n"bundle_digest": "{digest}"\n'


def plan_migration(
    workspace: Path,
    target_version: str,
    registry: BundleRegistry | None = None,
) -> MigrationPlan:
    """Chain-aware migration plan from current pin to `target_version`.

    Dry-run safe. Idempotent: if pin already at target, returns no-op plan.
    Raises MigrationError on missing pin, unknown target, or unresolvable chain.
    """
    reg = registry or BundleRegistry()
    pin_path = workspace / ".aiadra" / "schemas.yaml"
    if not pin_path.exists():
        raise MigrationError(
            f"Project pin missing: {pin_path}. Migration requires an existing "
            f"pinned workspace."
        )
    pin = load_yaml(pin_path)
    cur_v = pin.get("bundle_version")
    if not cur_v:
        raise MigrationError(
            f"Pin {pin_path} missing bundle_version; cannot resolve migration source."
        )
    try:
        target_bundle = reg.bundle(target_version)
    except KeyError:
        raise MigrationError(
            f"Packaged bundle v{target_version} not found; cannot migrate."
        )

    if cur_v == target_version:
        if pin.get("bundle_digest") != target_bundle.bundle_digest:
            raise BundleDigestMismatchError(
                f"Already pinned v{target_version} but digest stale: "
                f"pinned {pin.get('bundle_digest')!r}, actual "
                f"{target_bundle.bundle_digest!r}. Rewrite pin manually."
            )
        return MigrationPlan(
            from_bundle_version=cur_v,
            to_bundle_version=target_version,
            workspace=workspace,
            pin_path=pin_path,
            pin_will_change=False,
            new_pin_text="",
            notes=[f"Already pinned v{target_version}; migration is a no-op."],
        )

    chain = _chain_from_to(cur_v, target_version)
    notes: list[str] = []
    for s in chain:
        notes.extend(s.notes)
    notes.append(
        f"Multi-step chain: {' → '.join([cur_v] + [s.to_version for s in chain])}"
    )
    notes.append(
        f"Project pin will update from v{cur_v} to v{target_version} "
        f"(single atomic write at end of chain per ADR/0025 §9 absorption)."
    )
    notes.append(f"New bundle_digest: {target_bundle.bundle_digest}")

    return MigrationPlan(
        from_bundle_version=cur_v,
        to_bundle_version=target_version,
        workspace=workspace,
        pin_path=pin_path,
        pin_will_change=True,
        new_pin_text=_pin_text(target_version, target_bundle.bundle_digest),
        notes=notes,
    )


def apply_migration(
    workspace: Path,
    target_version: str,
    registry: BundleRegistry | None = None,
) -> MigrationPlan:
    """Chain-aware migration apply from current pin to `target_version`.

    For multi-step chains: runs each step's `apply` data hook in sequence,
    then writes the final pin ONCE atomically at end. Idempotent: re-running
    on a v{target}-pinned workspace returns a no-op plan.
    """
    reg = registry or BundleRegistry()
    plan = plan_migration(workspace, target_version, reg)
    if not plan.pin_will_change:
        return plan

    chain = _chain_from_to(plan.from_bundle_version, plan.to_bundle_version)
    for s in chain:
        s.apply(workspace, reg)

    atomic_write_bytes(plan.pin_path, plan.new_pin_text.encode("utf-8"))
    return plan


# ----------------------------------------------------------------------
# Flat per-pair wrappers — backward-compat for Phase 1+2 test suite +
# external callers from prior arcs. Delegate to the chain-aware functions.
# ----------------------------------------------------------------------


def plan_migration_v0_19_0_to_v0_20_0(
    workspace: Path, registry: BundleRegistry | None = None,
) -> MigrationPlan:
    """Phase 1 back-compat wrapper. Delegates to plan_migration(workspace, '0.20.0')."""
    reg = registry or BundleRegistry()
    pin_path = workspace / ".aiadra" / "schemas.yaml"
    if not pin_path.exists():
        raise MigrationError(
            f"Project pin missing: {pin_path}. Migration requires an existing "
            f"v0.19.0-pinned workspace."
        )
    pin = load_yaml(pin_path)
    if pin.get("bundle_version") != "0.19.0":
        raise MigrationError(
            f"Workspace pinned to {pin.get('bundle_version')!r}, not 0.19.0; "
            f"migrator v0.19.0 → v0.20.0 does not apply."
        )
    return plan_migration(workspace, "0.20.0", reg)


def apply_migration_v0_19_0_to_v0_20_0(
    workspace: Path, registry: BundleRegistry | None = None,
) -> MigrationPlan:
    """Phase 1 back-compat wrapper. Delegates to apply_migration(workspace, '0.20.0')."""
    reg = registry or BundleRegistry()
    pin_path = workspace / ".aiadra" / "schemas.yaml"
    if pin_path.exists():
        pin = load_yaml(pin_path)
        if pin.get("bundle_version") == "0.20.0":
            return apply_migration(workspace, "0.20.0", reg)
        if pin.get("bundle_version") != "0.19.0":
            raise MigrationError(
                f"Workspace pinned to {pin.get('bundle_version')!r}, not 0.19.0; "
                f"migrator v0.19.0 → v0.20.0 does not apply."
            )
    return apply_migration(workspace, "0.20.0", reg)


def plan_migration_v0_20_0_to_v0_21_0(
    workspace: Path, registry: BundleRegistry | None = None,
) -> MigrationPlan:
    """Phase 2 back-compat wrapper."""
    reg = registry or BundleRegistry()
    pin_path = workspace / ".aiadra" / "schemas.yaml"
    if not pin_path.exists():
        raise MigrationError(
            f"Project pin missing: {pin_path}. Migration requires a v0.20.0-pinned workspace."
        )
    pin = load_yaml(pin_path)
    if pin.get("bundle_version") != "0.20.0":
        raise MigrationError(
            f"Workspace pinned to {pin.get('bundle_version')!r}, not 0.20.0; "
            f"migrator v0.20.0 → v0.21.0 does not apply."
        )
    return plan_migration(workspace, "0.21.0", reg)


def apply_migration_v0_20_0_to_v0_21_0(
    workspace: Path, registry: BundleRegistry | None = None,
) -> MigrationPlan:
    """Phase 2 back-compat wrapper."""
    reg = registry or BundleRegistry()
    pin_path = workspace / ".aiadra" / "schemas.yaml"
    if pin_path.exists():
        pin = load_yaml(pin_path)
        if pin.get("bundle_version") == "0.21.0":
            return apply_migration(workspace, "0.21.0", reg)
        if pin.get("bundle_version") != "0.20.0":
            raise MigrationError(
                f"Workspace pinned to {pin.get('bundle_version')!r}, not 0.20.0; "
                f"migrator v0.20.0 → v0.21.0 does not apply."
            )
    return apply_migration(workspace, "0.21.0", reg)
