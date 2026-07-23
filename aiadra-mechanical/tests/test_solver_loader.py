"""The fail-closed native-solver loader (SK-C1 foundation, Codex16 B2 +
Codex17 B1).

Every refusal branch of the compatibility protocol is proven here — with
fake binding modules for the verification steps (no broken artifact needs
to be fabricated), with the REAL artifact for the happy path when it is
present, and with a REAL wrong-origin preload regression in a subprocess
(a conforming same-named DLL from another directory must be refused even
though its handshake declaration is valid).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
import types
from pathlib import Path

import pytest

from aiadra_mechanical.solver import (
    SolverABIMismatchError,
    SolverArtifactMissingError,
    SolverContractMismatchError,
    SolverOriginMismatchError,
    load_solver,
    resolve_dist_dir,
)
from aiadra_mechanical.solver.loader import _parse_handshake, _verify_binding


def _fake_binding(**attrs):
    mod = types.ModuleType("aiadra_solver_fake")
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


GOOD = dict(
    BINDING_ABI="cp312-win_amd64",
    BINDING_SOLVER_CONTRACT="skb-c0",
    dll_handshake=lambda: "aiadra-planegcs-abi:1;solver-contract:skb-c0",
)


class TestResolution:
    def test_env_override_is_literal_and_must_exist(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AIADRA_SOLVER_DIST", str(tmp_path / "nope"))
        with pytest.raises(SolverArtifactMissingError, match="does not name a directory"):
            resolve_dist_dir()

    def test_env_override_wins(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AIADRA_SOLVER_DIST", str(tmp_path))
        assert resolve_dist_dir() == tmp_path

    def test_repo_layout_resolution_finds_aiadra_solver_dist(self, monkeypatch):
        monkeypatch.delenv("AIADRA_SOLVER_DIST", raising=False)
        dist = resolve_dist_dir()
        assert dist.name == "dist" and dist.parent.name == "aiadra-solver"

    def test_missing_binaries_refuse_loudly(self, monkeypatch, tmp_path):
        # an existing but EMPTY dist dir: resolution succeeds, loading refuses
        monkeypatch.setenv("AIADRA_SOLVER_DIST", str(tmp_path))
        with pytest.raises(SolverArtifactMissingError, match="missing"):
            load_solver()


class TestVerification:
    def test_good_declarations_pass(self):
        _verify_binding(_fake_binding(**GOOD))

    def test_binding_without_identity_cannot_be_trusted(self):
        with pytest.raises(SolverContractMismatchError, match="cannot identify"):
            _verify_binding(_fake_binding(dll_handshake=GOOD["dll_handshake"]))

    def test_binding_abi_mismatch(self):
        bad = dict(GOOD, BINDING_ABI="cp311-win_amd64")
        with pytest.raises(SolverABIMismatchError, match="cp311"):
            _verify_binding(_fake_binding(**bad))

    def test_binding_contract_mismatch(self):
        bad = dict(GOOD, BINDING_SOLVER_CONTRACT="skb-c1")
        with pytest.raises(SolverContractMismatchError, match="skb-c1"):
            _verify_binding(_fake_binding(**bad))

    def test_binding_without_handshake_surface(self):
        mod = _fake_binding(BINDING_ABI=GOOD["BINDING_ABI"],
                            BINDING_SOLVER_CONTRACT=GOOD["BINDING_SOLVER_CONTRACT"])
        with pytest.raises(SolverContractMismatchError, match="dll_handshake"):
            _verify_binding(mod)

    def test_dll_refusal_propagates_typed(self):
        def raises():
            raise RuntimeError("aiadra_solver: the loaded planegcs.dll exports no "
                               "aiadra_planegcs_handshake")
        bad = dict(GOOD, dll_handshake=raises)
        with pytest.raises(SolverContractMismatchError, match="exports no"):
            _verify_binding(_fake_binding(**bad))

    def test_dll_wrong_abi(self):
        bad = dict(GOOD, dll_handshake=lambda: "aiadra-planegcs-abi:2;solver-contract:skb-c0")
        with pytest.raises(SolverABIMismatchError, match="abi:2"):
            _verify_binding(_fake_binding(**bad))

    def test_dll_wrong_contract(self):
        bad = dict(GOOD, dll_handshake=lambda: "aiadra-planegcs-abi:1;solver-contract:other")
        with pytest.raises(SolverContractMismatchError, match="does not implement"):
            _verify_binding(_fake_binding(**bad))

    def test_dll_unparseable_handshake(self):
        bad = dict(GOOD, dll_handshake=lambda: "gibberish with no fields")
        with pytest.raises(SolverABIMismatchError):
            _verify_binding(_fake_binding(**bad))


class TestOriginBinding:
    """Codex17 B1: the declaration is only trusted from the SELECTED file."""

    EXPECTED = Path(r"C:\repo\aiadra-solver\dist\planegcs.dll")

    def _armed(self, origin):
        return _fake_binding(**GOOD, dll_origin=lambda: origin)

    def test_matching_origin_passes(self, tmp_path):
        dll = tmp_path / "planegcs.dll"
        dll.write_bytes(b"x")
        _verify_binding(self._armed(str(dll)), expected_dll=dll)

    def test_origin_comparison_is_canonical_not_textual(self, tmp_path):
        # case difference + relative segments must NOT defeat the match
        dll = tmp_path / "planegcs.dll"
        dll.write_bytes(b"x")
        weird = str(tmp_path / "sub" / ".." / "PLANEGCS.DLL").upper()
        _verify_binding(self._armed(weird), expected_dll=dll)

    def test_wrong_origin_refused(self, tmp_path):
        dll = tmp_path / "planegcs.dll"
        dll.write_bytes(b"x")
        other = tmp_path / "elsewhere" / "planegcs.dll"
        with pytest.raises(SolverOriginMismatchError, match="selected artifact"):
            _verify_binding(self._armed(str(other)), expected_dll=dll)

    def test_binding_without_origin_surface_refused_when_armed(self):
        with pytest.raises(SolverOriginMismatchError, match="dll_origin"):
            _verify_binding(_fake_binding(**GOOD), expected_dll=self.EXPECTED)

    def test_origin_query_failure_refused(self):
        def raises():
            raise RuntimeError("aiadra_solver: GetModuleFileNameW failed")
        mod = _fake_binding(**GOOD, dll_origin=raises)
        with pytest.raises(SolverOriginMismatchError, match="GetModuleFileNameW"):
            _verify_binding(mod, expected_dll=self.EXPECTED)

    def test_unarmed_verification_skips_origin(self):
        # expected_dll=None (pure declaration checks) never demands origin
        _verify_binding(_fake_binding(**GOOD), expected_dll=None)


class TestHandshakeParse:
    def test_fields(self):
        assert _parse_handshake("aiadra-planegcs-abi:1;solver-contract:skb-c0") == {
            "aiadra-planegcs-abi": "1", "solver-contract": "skb-c0"}

    def test_tolerates_whitespace_and_ignores_bare_segments(self):
        assert _parse_handshake(" a:1 ; junk ; b:x ") == {"a": "1", "b": "x"}


class TestRealArtifact:
    """Happy path against the actual built pair (skipped loudly when absent —
    the binaries are deliberately not in git; see aiadra-solver/src/BUILD.md)."""

    def test_load_handshake_and_origin(self, monkeypatch):
        monkeypatch.delenv("AIADRA_SOLVER_DIST", raising=False)
        try:
            mod = load_solver()
        except SolverArtifactMissingError as exc:
            pytest.skip(f"native solver artifact not built locally: {exc}")
        assert mod.BINDING_SOLVER_CONTRACT == "skb-c0"
        assert "solver-contract:skb-c0" in mod.dll_handshake()
        # Codex17 B1: the handshaking module IS the selected artifact
        from aiadra_mechanical.solver.loader import _canonical
        assert _canonical(mod.dll_origin()) == _canonical(
            resolve_dist_dir() / "planegcs.dll")
        # idempotence: the verified module is cached per artifact directory
        assert load_solver() is mod

    def test_preloaded_wrong_origin_same_name_dll_is_refused(self, tmp_path):
        """Codex17 B1.4 — the REAL leak, reproduced: a byte-identical
        planegcs.dll preloaded from ANOTHER directory satisfies name-based
        module resolution and a valid handshake, and must still be refused
        by the origin comparison. Runs in a subprocess because a loaded DLL
        cannot be evicted from this test process."""
        try:
            dist = resolve_dist_dir()
        except SolverArtifactMissingError as exc:
            pytest.skip(f"native solver artifact home absent: {exc}")
        dll = dist / "planegcs.dll"
        if not dll.is_file():
            pytest.skip("native solver artifact not built locally")
        wrong = tmp_path / "planegcs.dll"
        shutil.copy2(dll, wrong)
        script = textwrap.dedent(f"""
            import ctypes, sys
            ctypes.WinDLL({str(wrong)!r})  # wrong-origin preload, same name
            from aiadra_mechanical.solver import (
                SolverOriginMismatchError, load_solver)
            try:
                load_solver()
            except SolverOriginMismatchError as exc:
                print("REFUSED:", exc)
                sys.exit(0)
            print("ACCEPTED a wrong-origin preloaded DLL -- boundary leak")
            sys.exit(1)
        """)
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True,
            cwd=str(Path(__file__).resolve().parents[1] / "src"))
        assert proc.returncode == 0, (
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}")
        assert "REFUSED" in proc.stdout
        assert "planegcs.dll" in proc.stdout  # the refusal names the module
