"""The permanent skb-1 corpus regression floor (SK-C1 foundation, D5).

The 14 frozen corpus cases (``aiadra-solver/testkit/corpus`` — the accepted
SK-B gate reference, in git) run through the PRODUCTION typed API and must:

1. match every case expectation (classification, dof_strong, diagnostics,
   weak completion, branch oracle, solved scalars within skb-c0 tolerance);
2. reproduce the ACCEPTED Gate corpus digest byte-for-byte — the proof that
   the production port (canonical layer + engine) did not drift from the
   evidence that selected this solver.

Deliberately NOT here (Codex17 B2): the skb-replay-1 P2/P4 solved-snapshot
replay procedures. They are EVIDENCE MACHINERY and run only inside the
frozen ``aiadra-solver/testkit`` harnesses (exercised by every
``run_gate2.py`` pass); the production branch-recovery surface arrives
with the ADR/0044 A2 typed branch selector in Gate F2.

Skipped LOUDLY (never silently green) when the local native artifact is
absent: the binaries are deliberately not in git (Codex16 B1) — build them
per aiadra-solver/src/BUILD.md.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from aiadra_mechanical.solver import (
    TOL_BLOCK,
    TOL_SCALAR,
    SolverArtifactMissingError,
    load_solver,
    solve,
)

# The accepted SK-B Gate-1/2 corpus digest of the patched planegcs candidate
# (arc 20260715-3; also pinned in aiadra-solver/src/BUILD.md).
ACCEPTED_CORPUS_DIGEST = (
    "061fbdec5913ee88943ac1241cc237dbd0075e121621b66be055f32befeeb736"
)

CASE_IDS = ["a-rect", "b-slot", "c-bracket", "d-under", "e-over-redundant",
            "f-conflicting", "g-nonconv", "h-outdomain", "i-permute",
            "j-branch-flip", "k-gear", "l-tee", "m-fan", "n-arcs"]


def _corpus_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        cand = parent / "aiadra-solver" / "testkit" / "corpus"
        if cand.is_dir():
            return cand
    raise AssertionError("aiadra-solver/testkit/corpus not found above tests/")


def load_case(case_id: str) -> dict:
    return json.loads((_corpus_dir() / f"{case_id}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module", autouse=True)
def _require_artifact():
    try:
        load_solver()
    except SolverArtifactMissingError as exc:
        pytest.skip(f"native solver artifact not built locally: {exc}")


def compare_expectation(result_dict: dict, case: dict) -> list[str]:
    """Comparison lane 1 of the skb-1 gate (expectation vs candidate)."""
    exp = case["expected"]
    errs = []
    if result_dict["classification"] != exp["classification"]:
        errs.append(f"classification {result_dict['classification']} != {exp['classification']}")
    if exp["dof_strong"] is not None and result_dict["dof_strong"] != exp["dof_strong"]:
        errs.append(f"dof_strong {result_dict['dof_strong']} != {exp['dof_strong']}")
    if result_dict["diagnostics"] != exp["diagnostics"]:
        errs.append(f"diagnostics {result_dict['diagnostics']} != {exp['diagnostics']}")
    if result_dict["weak_completion"] != exp["weak_completion"]:
        errs.append("weak_completion mismatch")
    oracle = exp.get("branch_oracle")
    want_oracle = oracle["expected"] if oracle else None
    if result_dict["branch_oracle_value"] != want_oracle:
        errs.append(f"branch_oracle_value {result_dict['branch_oracle_value']} != {want_oracle}")
    if (exp["solved"] is None) != (result_dict["solved"] is None):
        errs.append(f"solved presence mismatch (expected {exp['solved'] is not None})")
    elif exp["solved"] is not None:
        missing = set(exp["solved"]) ^ set(result_dict["solved"])
        if missing:
            errs.append(f"solved key mismatch: {sorted(missing)}")
        else:
            for k, v in exp["solved"].items():
                if abs(result_dict["solved"][k] - v) > TOL_SCALAR:
                    errs.append(f"solved {k}: {result_dict['solved'][k]} vs {v}")
        for block, v in result_dict["residual_max"].items():
            if v > TOL_BLOCK:
                errs.append(f"residual block {block} = {v:.3e} > {TOL_BLOCK}")
    return errs


class TestCorpusExpectations:
    @pytest.mark.parametrize("case_id", CASE_IDS)
    def test_case(self, case_id):
        case = load_case(case_id)
        result = solve(case)
        errs = compare_expectation(result.canonical_dict(), case)
        assert not errs, f"{case_id}: " + "; ".join(errs)


class TestAcceptedDigest:
    def test_production_lane_reproduces_the_accepted_gate_digest(self):
        h = hashlib.sha256()
        for case_id in CASE_IDS:
            h.update(solve(load_case(case_id)).canonical_bytes())
        assert h.hexdigest() == ACCEPTED_CORPUS_DIGEST, (
            "the production solver lane DRIFTED from the accepted SK-B "
            "evidence — canonical layer, engine port, or artifact changed "
            "behavior"
        )


class TestTypedSurface:
    def test_solve_has_no_replay_surface(self):
        """Codex17 B2: the production API must not accept an evidence-replay
        mapping — branch recovery is an A2/F2 decision. A `replay` keyword
        (or any second positional input) must not exist."""
        import inspect
        params = inspect.signature(solve).parameters
        assert list(params) == ["case"]

    def test_two_axis_separation_redundant_over_still_solves(self):
        """The exact compression Codex16 B2 refused: redundant-over SOLVES."""
        result = solve(load_case("e-over-redundant"))
        assert result.classification == "over"
        assert [d.kind for d in result.diagnostics] == ["redundant"]
        assert result.solved_coordinates is not None
        assert result.dof_strong == 0

    def test_conflicting_over_does_not_solve(self):
        result = solve(load_case("f-conflicting"))
        assert result.classification == "over"
        assert any(d.kind == "conflicting" for d in result.diagnostics)
        assert result.solved_coordinates is None

    def test_under_carries_typed_weak_completion(self):
        result = solve(load_case("d-under"))
        assert result.classification == "under"
        assert result.dof_strong == 1
        (w,) = result.weak_completion
        assert (w.target_entity, w.target_parameter) == ("a1", "radius")
        assert w.magnitude == 10.0 and w.unit == "mm"
        assert w.raw["origin"] == {"category": "computed_result",
                                   "policy": "skb-0", "solver_contract": "skb-c0"}

    def test_rejected_carries_out_of_domain(self):
        result = solve(load_case("h-outdomain"))
        assert result.classification == "rejected"
        assert [d.kind for d in result.diagnostics] == ["out-of-domain"]
        assert result.diagnostics[0].members == ("c11",)

    def test_non_convergent_diagnostic(self):
        result = solve(load_case("g-nonconv"))
        assert result.classification == "well"
        assert any(d.kind == "non-convergent" for d in result.diagnostics)
        assert result.solved_coordinates is None

    def test_solved_coordinates_are_read_only_views(self):
        result = solve(load_case("a-rect"))
        with pytest.raises(TypeError):
            result.solved_coordinates["p1.x"] = 99.0  # type: ignore[index]
