"""Content-addressed local-FS Vault Adapter (reference implementation).

Layout: `<workspace>/vault/<sha256-hex>/bytes`. Ported from Wedge-002's
`vault.py`. Spike-grade direct port; production-grade enhancements (concurrent
write coordination; size-limit enforcement; quota tracking) deferred to a
future focused arc.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .interface import AttachmentIntegrityError, VaultAdapter


def vault_root(workspace: Path) -> Path:
    return workspace / "vault"


def _content_dir(workspace: Path, content_hash: str) -> Path:
    if not content_hash.startswith("sha256:"):
        raise ValueError(f"Expected sha256:<hex> content_hash, got {content_hash!r}")
    return vault_root(workspace) / content_hash[len("sha256:"):]


def _bytes_path(workspace: Path, content_hash: str) -> Path:
    return _content_dir(workspace, content_hash) / "bytes"


class LocalFSVaultAdapter(VaultAdapter):
    """Workspace-local content-addressed Vault. No service; no network."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def store(self, data: bytes) -> tuple[str, str]:
        hex_ = hashlib.sha256(data).hexdigest()
        content_hash = f"sha256:{hex_}"
        cdir = _content_dir(self.workspace, content_hash)
        bytes_path = cdir / "bytes"
        vault_path = f"vault/{hex_}"
        if bytes_path.exists():
            return content_hash, vault_path
        cdir.mkdir(parents=True, exist_ok=True)
        bytes_path.write_bytes(data)
        return content_hash, vault_path

    def retrieve(self, content_hash: str) -> bytes:
        return _bytes_path(self.workspace, content_hash).read_bytes()

    def verify(self, content_hash: str) -> None:
        bytes_path = _bytes_path(self.workspace, content_hash)
        if not bytes_path.exists():
            raise AttachmentIntegrityError(
                f"Vault missing bytes for {content_hash} at {bytes_path}"
            )
        data = bytes_path.read_bytes()
        actual_hex = hashlib.sha256(data).hexdigest()
        expected = content_hash[len("sha256:"):]
        if actual_hex != expected:
            raise AttachmentIntegrityError(
                f"Vault bytes hash mismatch for {content_hash}: "
                f"on-disk hash sha256:{actual_hex} at {bytes_path}"
            )
