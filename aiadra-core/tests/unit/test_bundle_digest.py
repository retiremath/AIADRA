"""Bundle digest reproducibility + project-pin verification.

Per ADR/0003 §9 + Codex1 B1 absorption arc 20260531-1.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from aiadra_core.validation.digest import (
    BundleDigestMismatchError,
    compute_bundle_digest,
    load_project_pin,
    verify_project_pin,
)
from aiadra_core.validation.schema import packaged_bundle_dir


def test_bundle_digest_is_reproducible():
    bundle = packaged_bundle_dir("0.19.0")
    d1 = compute_bundle_digest(bundle)
    d2 = compute_bundle_digest(bundle)
    assert d1 == d2
    assert d1.startswith("sha256:")


def test_packaged_digest_file_matches_recompute():
    bundle = packaged_bundle_dir("0.19.0")
    recomputed = compute_bundle_digest(bundle)
    pinned = json.loads((bundle / "_digest.json").read_text(encoding="utf-8"))
    assert pinned["bundle_digest"] == recomputed
    assert pinned["bundle_version"] == "0.19.0"


def test_fixture_project_pins_match_packaged_bundle():
    bundle = packaged_bundle_dir("0.19.0")
    for fix in ["wedge_001", "wedge_002"]:
        workspace = Path(__file__).parent.parent / "fixtures" / fix
        v, d = verify_project_pin(workspace, bundle)
        assert v == "0.19.0"
        assert d.startswith("sha256:")


def test_missing_project_pin_raises(tmp_path: Path):
    bundle = packaged_bundle_dir("0.19.0")
    with pytest.raises(FileNotFoundError):
        load_project_pin(tmp_path)
    with pytest.raises(FileNotFoundError):
        verify_project_pin(tmp_path, bundle)


def test_mismatched_pin_raises(tmp_path: Path):
    bundle = packaged_bundle_dir("0.19.0")
    pin_dir = tmp_path / ".aiadra"
    pin_dir.mkdir()
    (pin_dir / "schemas.yaml").write_bytes(
        b'"bundle_version": "0.19.0"\n'
        b'"bundle_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000"\n'
    )
    with pytest.raises(BundleDigestMismatchError):
        verify_project_pin(tmp_path, bundle)
