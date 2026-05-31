"""Bundle migrator per ADR/0003 §10 — deterministic + dry-run + idempotent.

Phase 1 ships the first concrete migrator: v0.19.0 → v0.20.0. The schema
extensions are all OPTIONAL (additive), so no canonical artifact data needs
migration — only the project pin `.aiadra/schemas.yaml` updates from old
bundle_version + digest to new bundle_version + digest.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


def plan_migration_v0_19_0_to_v0_20_0(
    workspace: Path, registry: BundleRegistry | None = None,
) -> MigrationPlan:
    """Compute what would change without writing anything (dry-run support).

    Raises MigrationError if the workspace is not v0.19.0-pinned or if the
    v0.20.0 bundle is missing from the packaged registry.
    """
    reg = registry or BundleRegistry()
    pin_path = workspace / ".aiadra" / "schemas.yaml"
    notes: list[str] = []

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

    try:
        target_bundle = reg.bundle("0.20.0")
    except KeyError:
        raise MigrationError("Packaged v0.20.0 bundle not found; cannot migrate.")

    new_pin_text = (
        '"bundle_version": "0.20.0"\n'
        f'"bundle_digest": "{target_bundle.bundle_digest}"\n'
    )

    notes.append(
        "v0.19.0 → v0.20.0 is a MINOR additive bump (5 new event types + "
        "optional manifest staging fields + optional Reservation rev_id fields). "
        "All existing canonical artifacts (sidecars / Revisions / events / "
        "Reservations / manifests) validate unchanged against v0.20.0; no data "
        "migration required."
    )
    notes.append(f"Project pin will update from v0.19.0 to v0.20.0.")
    notes.append(f"New bundle_digest: {target_bundle.bundle_digest}")

    return MigrationPlan(
        from_bundle_version="0.19.0",
        to_bundle_version="0.20.0",
        workspace=workspace,
        pin_path=pin_path,
        pin_will_change=True,
        new_pin_text=new_pin_text,
        notes=notes,
    )


def apply_migration_v0_19_0_to_v0_20_0(
    workspace: Path, registry: BundleRegistry | None = None,
) -> MigrationPlan:
    """Apply v0.19.0 → v0.20.0 migration. Idempotent: re-running on a v0.20.0
    workspace returns a no-op plan.
    """
    reg = registry or BundleRegistry()
    pin_path = workspace / ".aiadra" / "schemas.yaml"
    if pin_path.exists():
        pin = load_yaml(pin_path)
        if pin.get("bundle_version") == "0.20.0":
            # Already migrated; idempotent no-op
            target = reg.bundle("0.20.0")
            if pin.get("bundle_digest") != target.bundle_digest:
                raise BundleDigestMismatchError(
                    f"Already pinned v0.20.0 but digest stale: "
                    f"pinned {pin.get('bundle_digest')!r}, actual "
                    f"{target.bundle_digest!r}. Rewrite pin manually or with `--force`."
                )
            return MigrationPlan(
                from_bundle_version="0.20.0",
                to_bundle_version="0.20.0",
                workspace=workspace,
                pin_path=pin_path,
                pin_will_change=False,
                new_pin_text="",
                notes=["Already pinned v0.20.0; migration is a no-op."],
            )

    plan = plan_migration_v0_19_0_to_v0_20_0(workspace, reg)
    atomic_write_bytes(plan.pin_path, plan.new_pin_text.encode("utf-8"))
    return plan


# Phase 2 F1 SCN absorption arc 20260531-3 — v0.20.0 → v0.21.0 migrator.
# Same shape as v0.19.0 → v0.20.0: MINOR additive bump (new optional
# `new_fact_provenance` field on `parameter_changed` event payload); no data
# migration needed; project pin updates atomically.


def plan_migration_v0_20_0_to_v0_21_0(
    workspace: Path, registry: BundleRegistry | None = None,
) -> MigrationPlan:
    reg = registry or BundleRegistry()
    pin_path = workspace / ".aiadra" / "schemas.yaml"
    notes: list[str] = []
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
    try:
        target_bundle = reg.bundle("0.21.0")
    except KeyError:
        raise MigrationError("Packaged v0.21.0 bundle not found; cannot migrate.")

    new_pin_text = (
        '"bundle_version": "0.21.0"\n'
        f'"bundle_digest": "{target_bundle.bundle_digest}"\n'
    )
    notes.append(
        "v0.20.0 → v0.21.0 is a MINOR additive bump (optional "
        "`new_fact_provenance` field on `parameter_changed` event payload "
        "per F1 absorption). All existing canonical artifacts validate "
        "unchanged against v0.21.0; no data migration required."
    )
    notes.append("Project pin will update from v0.20.0 to v0.21.0.")
    notes.append(f"New bundle_digest: {target_bundle.bundle_digest}")
    return MigrationPlan(
        from_bundle_version="0.20.0",
        to_bundle_version="0.21.0",
        workspace=workspace,
        pin_path=pin_path,
        pin_will_change=True,
        new_pin_text=new_pin_text,
        notes=notes,
    )


def apply_migration_v0_20_0_to_v0_21_0(
    workspace: Path, registry: BundleRegistry | None = None,
) -> MigrationPlan:
    """Apply v0.20.0 → v0.21.0 migration. Idempotent."""
    reg = registry or BundleRegistry()
    pin_path = workspace / ".aiadra" / "schemas.yaml"
    if pin_path.exists():
        pin = load_yaml(pin_path)
        if pin.get("bundle_version") == "0.21.0":
            target = reg.bundle("0.21.0")
            if pin.get("bundle_digest") != target.bundle_digest:
                raise BundleDigestMismatchError(
                    f"Already pinned v0.21.0 but digest stale: "
                    f"pinned {pin.get('bundle_digest')!r}, actual "
                    f"{target.bundle_digest!r}. Rewrite pin manually or with `--force`."
                )
            return MigrationPlan(
                from_bundle_version="0.21.0",
                to_bundle_version="0.21.0",
                workspace=workspace,
                pin_path=pin_path,
                pin_will_change=False,
                new_pin_text="",
                notes=["Already pinned v0.21.0; migration is a no-op."],
            )
    plan = plan_migration_v0_20_0_to_v0_21_0(workspace, reg)
    atomic_write_bytes(plan.pin_path, plan.new_pin_text.encode("utf-8"))
    return plan
