"""Vault Adapter interface.

Per ADR/0001 (Vault as pluggable blob store) + ADR/0017 §2 (content_hash is
authority; vault_path is non-authoritative locator hint).

Phase 0 ships one concrete implementation: `LocalFSVaultAdapter`. Future
focused arcs add S3 / MinIO / IPFS / NAS backends as optional extras per
ADR/0025 §2 dependency posture.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class AttachmentIntegrityError(ValueError):
    """Vault byte-hash mismatch — content does not match the embedded content_hash."""


class VaultAdapter(ABC):
    """Pluggable Vault Adapter contract.

    `content_hash` strings are algorithm-qualified (`"sha256:<hex>"`) per
    ADR/0016 + ADR/0017 §2.
    """

    @abstractmethod
    def store(self, data: bytes) -> tuple[str, str]:
        """Store bytes content-addressed. Returns (content_hash, vault_path).

        Idempotent: if the same bytes are stored twice, the second call returns
        the same locator without rewriting.
        """

    @abstractmethod
    def retrieve(self, content_hash: str) -> bytes:
        """Read bytes back by content hash. Raises FileNotFoundError if missing."""

    @abstractmethod
    def verify(self, content_hash: str) -> None:
        """Re-read bytes + re-hash + compare against `content_hash`.

        Raises AttachmentIntegrityError on mismatch.
        """
