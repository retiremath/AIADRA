"""Bundle digest computation + project-pin verification.

Per ADR/0003 §9: every project carries `.aiadra/schemas.yaml` with the active
bundle pin (`bundle_version` + `bundle_digest`). Digest mismatch is a hard
reject before any read (per Codex1 B1 absorption arc 20260531-1).

The digest is a canonical SHA-256 over the bundle's normative files:
- `_index.json` (the bundle's lookup map)
- every JSON Schema file under the bundle directory (sorted by relative path)

Sorted-relative-path iteration makes the digest reproducible across machines
regardless of filesystem enumeration order. Files are read as raw bytes (no
text normalization) so newline behavior cannot change the digest.

The digest does NOT include `_digest.json` itself (that's the output) nor any
hidden / non-schema files in the bundle directory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..validation.profile import load_yaml


class BundleDigestMismatchError(ValueError):
    """Project-pinned bundle_digest does not match the packaged bundle's digest."""


def compute_bundle_digest(bundle_dir: Path) -> str:
    """Compute the canonical SHA-256 of the bundle's normative files.

    Returns "sha256:<hex>". Iterates *.json files sorted by relative POSIX path
    to guarantee reproducibility. Skips `_digest.json` (output) and hidden files.
    """
    h = hashlib.sha256()
    files: list[Path] = []
    for p in bundle_dir.rglob("*.json"):
        rel = p.relative_to(bundle_dir).as_posix()
        if rel == "_digest.json":
            continue
        if rel.startswith("."):
            continue
        files.append(p)
    for p in sorted(files, key=lambda f: f.relative_to(bundle_dir).as_posix()):
        rel = p.relative_to(bundle_dir).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(p.read_bytes())
        h.update(b"\x00")
    return f"sha256:{h.hexdigest()}"


def write_digest_file(bundle_dir: Path) -> str:
    """Compute + write `_digest.json` to bundle_dir. Returns the digest string."""
    digest = compute_bundle_digest(bundle_dir)
    index = json.loads((bundle_dir / "_index.json").read_text(encoding="utf-8"))
    payload = {
        "bundle_version": index["bundle_version"],
        "bundle_digest": digest,
    }
    (bundle_dir / "_digest.json").write_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return digest


def load_project_pin(workspace: Path) -> dict:
    """Load `.aiadra/schemas.yaml` project pin.

    Raises FileNotFoundError if the pin does not exist — production-grade
    workspaces MUST carry it per ADR/0003 §9.
    """
    pin_path = workspace / ".aiadra" / "schemas.yaml"
    if not pin_path.exists():
        raise FileNotFoundError(
            f"Project pin missing: {pin_path}. Production workspaces MUST carry "
            f".aiadra/schemas.yaml per ADR/0003 §9."
        )
    return load_yaml(pin_path)


def verify_project_pin(workspace: Path, bundle_dir: Path) -> tuple[str, str]:
    """Load the project pin, compute the packaged bundle's digest, compare.

    Returns (bundle_version, bundle_digest) on success.
    Raises BundleDigestMismatchError on mismatch.
    """
    pin = load_project_pin(workspace)
    pinned_version = pin["bundle_version"]
    pinned_digest = pin["bundle_digest"]
    index = json.loads((bundle_dir / "_index.json").read_text(encoding="utf-8"))
    if pinned_version != index["bundle_version"]:
        raise BundleDigestMismatchError(
            f"Project pin requires bundle {pinned_version!r}, packaged is "
            f"{index['bundle_version']!r}"
        )
    actual = compute_bundle_digest(bundle_dir)
    if actual != pinned_digest:
        raise BundleDigestMismatchError(
            f"Bundle digest mismatch for {pinned_version}: "
            f"pinned {pinned_digest}, actual {actual}"
        )
    return pinned_version, actual
