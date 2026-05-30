"""Minimal local-FS content-addressed Vault Adapter per ADR/0024 §4.

Stores attachment bytes under `<workspace>/vault/<sha256-hex>/bytes`.
Idempotent — re-storing same bytes reuses existing dir.

Production-grade Vault Adapter (LFS / S3 / MinIO / IPFS per ADR/0001 §3 menu)
remains separate future ADR; this is the spike-grade minimum that makes
integrity claims TRUE per ADR/0017 (content_hash is authority for attachment
bytes).
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import NamedTuple


class AttachmentLocator(NamedTuple):
    content_hash: str  # "sha256:<hex>" (algorithm-qualified per ADR/0016)
    vault_path: str    # "vault/<sha256-hex>" (non-authoritative locator hint per ADR/0017 §2)


class AttachmentIntegrityError(ValueError):
    """Raised when Vault bytes do not match expected content_hash."""


def _vault_dir(workspace: Path) -> Path:
    return workspace / "vault"


def store_file(workspace: Path, source_path: Path) -> AttachmentLocator:
    """Read source_path bytes; compute SHA-256; copy to content-addressed
    location; return locator. Idempotent."""
    payload = source_path.read_bytes()
    hex_hash = hashlib.sha256(payload).hexdigest()
    target_dir = _vault_dir(workspace) / hex_hash
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "bytes"
    if not target.exists():
        target.write_bytes(payload)
    return AttachmentLocator(
        content_hash=f"sha256:{hex_hash}",
        vault_path=f"vault/{hex_hash}",
    )


def verify(workspace: Path, content_hash: str) -> None:
    """Re-read bytes from content-addressed location; re-hash; raise on
    mismatch or missing. Per ADR/0017 §"validation guidance": canonical chain
    is parameter → derived_from → attachment → content_hash → Vault bytes;
    this is the final link.
    """
    if not content_hash.startswith("sha256:"):
        raise AttachmentIntegrityError(f"Unsupported content_hash algorithm: {content_hash}")
    expected_hex = content_hash[len("sha256:"):]
    target = _vault_dir(workspace) / expected_hex / "bytes"
    if not target.exists():
        raise AttachmentIntegrityError(f"Vault bytes missing for {content_hash} at {target}")
    actual_hex = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual_hex != expected_hex:
        raise AttachmentIntegrityError(
            f"Vault integrity violation for {content_hash}: actual sha256:{actual_hex}"
        )
