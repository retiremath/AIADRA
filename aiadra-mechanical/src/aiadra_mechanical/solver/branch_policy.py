"""`branch_policy: "skb-b0"` — the production implementation.

The NORMATIVE authority is `Docs/SolverContracts/skb-b0.md` (ADR/0044 A2.10);
this module implements it and the parity tests enforce COMPLETE-structure
correspondence — the constants, the local signature table, the WHOLE
G0/G1/G2 graph predicate, and the array-order law. skb-b0 freezes NO
witness measure (its catalog is empty; the draft prototypes live in
`witness_draft.py`, production-unconsumed). Any semantic divergence is a
defect HERE, never a fork of the contract.

The governing rule (skb-b0 preamble): *a list of safe equations is not yet a
safe system* — admission classifies complete fact GRAPHS. Under skb-b0 the
admitted universe is exactly G0/G1/G2 (the fixed-reference sketch grammar),
each single-root by closed-form elimination, deriving the exact EMPTY
witness set. Everything else refuses typed out-of-domain.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .contract import SOLVER_CONTRACT, WEAK_POLICY

POLICY_ID = "skb-b0"

# Versioned skb-b0 constants (doc §1; parity-checked). Codex23 B4: NO ε here
# — skb-b0's catalog is EMPTY, so no witness measure (and no degeneracy
# threshold) is normative under this id; the measure schemas live as DRAFT
# material for the first non-empty policy (see solver/witness_draft.py).
L_MIN_MM = 1e-9

CONSTANTS = {
    "policy_id": POLICY_ID,
    "solver_contract": SOLVER_CONTRACT,
    "weak_policy": WEAK_POLICY,
    "L_min_mm": L_MIN_MM,
}

# The COMPLETE machine-readable graph predicate (doc §3; parity-checked as a
# WHOLE structure — Codex23 B4: comparing keys alone would let a normative
# role/fact/weak/guard edit drift silently). `admit_graph` implements it;
# the semantic execution tests prove the implementation, this constant
# proves the correspondence with the document.
GRAPH_PREDICATE = {
    "G0": {
        "entities": [{"role": "O", "type": "point", "construction": True}],
        "strong_facts": [{"kind": "fix", "args": ["O"]}],
        "weak_completion": [],
        "guards": [],
    },
    "G1": {
        "entities": [
            {"role": "O", "type": "point", "construction": True},
            {"role": "PX", "type": "point", "construction": True},
            {"role": "AX", "type": "line", "construction": True,
             "start": "O", "end": "PX"},
        ],
        "strong_facts": [
            {"kind": "fix", "args": ["O"]},
            {"kind": "horizontal", "args": ["AX"]},
        ],
        "weak_completion": [{"target_role": "PX", "target_parameter": "x"}],
        "guards": [{"signed_displacement": ["PX.x", "O.x"],
                    "exceeds": "L_min_mm"}],
    },
    "G2": {
        "extends": "G1",
        "entities_add": [
            {"role": "PY", "type": "point", "construction": True},
            {"role": "AY", "type": "line", "construction": True,
             "start": "O", "end": "PY"},
        ],
        "strong_facts_add": [{"kind": "vertical", "args": ["AY"]}],
        "weak_completion_add": [{"target_role": "PY", "target_parameter": "y"}],
        "guards_add": [{"signed_displacement": ["PY.y", "O.y"],
                       "exceeds": "L_min_mm"}],
    },
}

# The array-order law (doc §3; parity-checked; Codex24 B1): entity/strong-
# fact arrays are semantically UNORDERED (admission and canonical identity
# both normalize), while the weak-completion — and any witness array under a
# later non-empty policy — is CANONICALLY ordered. `kernel._canonical_payload`
# sorts exactly the "unordered" collections; `admit_graph` enforces the
# canonical order of the rest. One machine-readable rule, three consumers.
ARRAY_ORDER = {
    "entities": "unordered",
    "constraints": "unordered",
    "dimensions": "unordered",
    "references": "unordered",
    "weak_completion": "canonical",
    "witnesses": "canonical",
}

# Layer 1 — the local signature table (doc §2; parity-checked). Necessary,
# never sufficient: passing it admits nothing by itself.
LOCAL_TABLE = {
    "entity_kinds": ["point", "line"],
    "construction_only": True,
    "fact_kinds": {
        "fix": {"signature": ["point"], "class": "strong"},
        "horizontal": {"signature": ["line"], "class": "strong"},
        "vertical": {"signature": ["line"], "class": "strong"},
        "fix_param": {"signature": ["parameter"], "class": "weak-completion-only"},
    },
    "dimension_kinds": {},
}

# NOTE (Codex23 B4): no witness KIND is normative under skb-b0 — the catalog
# derives the empty set for every admitted graph, so the measure schemas,
# the degeneracy threshold ε, and their golden vectors are NOT frozen by
# this id. They live as explicitly-DRAFT material in
# `solver/witness_draft.py` + `Docs/SolverContracts/witness-kinds-draft.md`
# and freeze only with the first non-empty branch policy, together with a
# scale-aware operand domain and an error bound proven against it.


# --------------------------------------------------- layer 2: the predicate

@dataclass(frozen=True)
class Admission:
    """An ACCEPTED graph: which shape matched and the role→entity-id binding."""

    shape: str  # "G0" | "G1" | "G2"
    roles: Mapping[str, str]


class OutOfDomain(ValueError):
    """Typed skb-b0 refusal — the graph is not admitted under this policy."""


def _fail(reason: str) -> None:
    raise OutOfDomain(f"branch_policy skb-b0: out-of-domain — {reason}")


def _is_number(v: Any) -> bool:
    """Strict JSON-number predicate (Codex23 B2): booleans are NOT numbers —
    Python's `bool` subclasses `int`, so `isinstance` checks silently admit
    `true`/`false` where TypeScript's `typeof === 'number'` refuses. The five
    surfaces must speak ONE language; this is it."""
    return type(v) in (int, float) and math.isfinite(v)


# Codex23 B2: the identity-bearing nested records are CLOSED shapes — an
# unknown nested key would enter recipe identity with no contract semantics.
_POINT_KEYS = {"id", "type", "construction", "nominal"}
_LINE_KEYS = {"id", "type", "construction", "start", "end"}
_CONSTRAINT_KEYS = {"id", "kind", "args"}
_NOMINAL_KEYS = {"x", "y"}
_WEAK_TARGET_KEYS = {"entity", "parameter"}


def _finite_nominal(e: Mapping[str, Any], eid: str) -> tuple[float, float]:
    nom = e.get("nominal")
    if not (isinstance(nom, Mapping) and set(nom.keys()) == _NOMINAL_KEYS):
        _fail(f"point {eid!r} has no well-formed nominal {{x, y}}")
    x, y = nom["x"], nom["y"]
    if not (_is_number(x) and _is_number(y)):
        _fail(f"point {eid!r} nominal is not strict finite numeric "
              "(booleans are not numbers)")
    return float(x), float(y)


def _validate_weak_record(w: Any, index: int,
                          expected_target: tuple[str, str]) -> float:
    """Full verbatim skb-0 record validation (Codex22 N1) — never target
    names alone. Returns the persisted magnitude (the EFFECTIVE value)."""
    if not isinstance(w, Mapping):
        _fail(f"weak record {index} is {type(w).__name__!s}, not a record")
    wid = w.get("id")
    want_id = f"w{index + 1:02d}"
    if wid != want_id:
        _fail(f"weak record {index} id {wid!r} != canonical {want_id!r}")
    if w.get("kind") != "fix_param":
        _fail(f"weak record {want_id} kind {w.get('kind')!r} != 'fix_param'")
    tgt = w.get("target")
    if not (isinstance(tgt, Mapping)
            and set(tgt.keys()) == _WEAK_TARGET_KEYS
            and (tgt["entity"], tgt["parameter"]) == expected_target):
        _fail(f"weak record {want_id} target {tgt!r} != expected {expected_target!r}")
    val = w.get("value")
    if not (isinstance(val, Mapping) and set(val.keys()) == {"magnitude", "unit"}
            and val.get("unit") == "mm"
            and _is_number(val.get("magnitude"))):
        _fail(f"weak record {want_id} value must be {{magnitude: strict finite "
              "number, unit: 'mm'}}")
    if w.get("strength") != "weak" or w.get("role") != "driving" \
            or w.get("visibility") != "internal":
        _fail(f"weak record {want_id} strength/role/visibility are not the "
              "verbatim skb-0 shape (weak/driving/internal)")
    origin = w.get("origin")
    if not (isinstance(origin, Mapping)
            and origin.get("category") == "computed_result"
            and origin.get("policy") == WEAK_POLICY
            and origin.get("solver_contract") == SOLVER_CONTRACT
            and set(origin.keys()) == {"category", "policy", "solver_contract"}):
        _fail(f"weak record {want_id} origin is not the verbatim skb-0 origin block")
    extra = set(w.keys()) - {"id", "kind", "target", "value", "strength",
                             "role", "visibility", "origin"}
    if extra:
        _fail(f"weak record {want_id} carries unknown fields {sorted(extra)}")
    return float(val["magnitude"])


def admit_graph(entities: Sequence[Mapping[str, Any]],
                constraints: Sequence[Mapping[str, Any]],
                dimensions: Sequence[Mapping[str, Any]],
                weak_completion: Sequence[Mapping[str, Any]]) -> Admission:
    """The total whole-fact-graph admission predicate (doc §3).

    Structural matching per the array-order law (Codex25 N1): entity and
    strong-fact array order is irrelevant; the weak-completion array is
    CANONICAL (`w01, w02, …` in canonical parameter order — a permuted weak
    array refuses); ids arbitrary; exact cardinalities. Raises
    :class:`OutOfDomain` for everything that is not exactly G0, G1, or G2 —
    including local-table violations, wrong weak sets, failed signed
    guards, and magnitude/nominal contradictions.
    """
    # ---- layer 1 (necessary) --------------------------------------------
    if dimensions:
        _fail("skb-b0 admits no dimensions")
    ents: dict[str, Mapping[str, Any]] = {}
    for e in entities:
        if not isinstance(e, Mapping):
            _fail(f"entity entry is {type(e).__name__!s}, not a record")
        eid = e.get("id")
        if not isinstance(eid, str) or not eid:
            _fail("entity without a non-empty string id")
        if eid in ents:
            _fail(f"duplicate entity id {eid!r}")
        if e.get("type") not in LOCAL_TABLE["entity_kinds"]:
            _fail(f"entity {eid!r} type {e.get('type')!r} is outside the local table")
        if e.get("construction") is not True:
            _fail(f"entity {eid!r} is not construction geometry "
                  "(skb-b0 admits construction references only)")
        # Codex23 B2: closed nested shapes — unknown keys never become
        # identity-bearing no-ops.
        want_keys = _POINT_KEYS if e["type"] == "point" else _LINE_KEYS
        extra = set(e.keys()) - want_keys
        if extra:
            _fail(f"entity {eid!r} carries unknown fields {sorted(extra)} "
                  "(the skb-b0 entity shapes are closed)")
        if e["type"] == "line":
            if not (isinstance(e.get("start"), str) and isinstance(e.get("end"), str)):
                _fail(f"line {eid!r} start/end must be entity-id strings")
        ents[eid] = e
    seen_cids: set[str] = set()
    for c in constraints:
        if not isinstance(c, Mapping):
            _fail(f"constraint entry is {type(c).__name__!s}, not a record")
        cid = c.get("id")
        if not isinstance(cid, str) or not cid or cid in seen_cids:
            _fail("constraint without a unique non-empty string id")
        seen_cids.add(cid)
        kind = c.get("kind")
        if kind not in ("fix", "horizontal", "vertical"):
            _fail(f"constraint {cid!r} kind {kind!r} is outside the local table")
        extra = set(c.keys()) - _CONSTRAINT_KEYS
        if extra:
            _fail(f"constraint {cid!r} carries unknown fields {sorted(extra)} "
                  "(the skb-b0 constraint shape is closed)")

    points = sorted(eid for eid, e in ents.items() if e["type"] == "point")
    lines = sorted(eid for eid, e in ents.items() if e["type"] == "line")

    # ---- layer 2 (the authority) ----------------------------------------
    fixes = [c for c in constraints if c["kind"] == "fix"]
    horizontals = [c for c in constraints if c["kind"] == "horizontal"]
    verticals = [c for c in constraints if c["kind"] == "vertical"]

    if len(fixes) != 1 or not (isinstance(fixes[0].get("args"), list)
                               and len(fixes[0]["args"]) == 1):
        _fail("exactly one fix(point) anchor is required")
    origin_id = fixes[0]["args"][0]
    if origin_id not in ents or ents[origin_id]["type"] != "point":
        _fail(f"fix names {origin_id!r}, which is not a point entity")
    o_x, o_y = _finite_nominal(ents[origin_id], origin_id)

    n_pts, n_lns = len(points), len(lines)
    if (n_pts, n_lns) == (1, 0):
        if horizontals or verticals or list(weak_completion):
            _fail("G0 admits no axis facts and an empty weak completion")
        return Admission("G0", {"O": origin_id})

    def _axis(cons: list[Mapping[str, Any]], kind: str) -> str:
        if len(cons) != 1 or not (isinstance(cons[0].get("args"), list)
                                  and len(cons[0]["args"]) == 1):
            _fail(f"exactly one {kind}(line) is required for this shape")
        lid = cons[0]["args"][0]
        if lid not in ents or ents[lid]["type"] != "line":
            _fail(f"{kind} names {lid!r}, which is not a line entity")
        line = ents[lid]
        if line.get("start") != origin_id:
            _fail(f"axis line {lid!r} must be DIRECTED from the fixed origin "
                  f"(start == {origin_id!r}); the reference axes are directed")
        end = line.get("end")
        if end not in ents or ents[end]["type"] != "point" or end == origin_id:
            _fail(f"axis line {lid!r} end {end!r} must be a distinct point entity")
        return lid

    weak = list(weak_completion)
    if (n_pts, n_lns) == (2, 1):
        if verticals:
            _fail("G1 has no vertical axis; a lone vertical axis is not an "
                  "admitted shape under skb-b0")
        ax = _axis(horizontals, "horizontal")
        px = ents[ax]["end"]
        px_x, _px_y = _finite_nominal(ents[px], px)
        if len(weak) != 1:
            _fail("G1 requires exactly one weak record (fix_param on the axis "
                  "endpoint's x)")
        magnitude = _validate_weak_record(weak[0], 0, (px, "x"))
        if magnitude != px_x:
            _fail(f"weak magnitude {magnitude!r} contradicts the authored "
                  f"nominal {px_x!r} for {px}.x")
        # Codex22 N1: the guard runs on EFFECTIVE values — the weak record's
        # persisted magnitude and the fix anchor's authored nominal — and it
        # is SIGNED: the +X direction is canonical.
        if not (magnitude - o_x > L_MIN_MM):
            _fail(f"signed guard failed: {px}.x − {origin_id}.x = "
                  f"{magnitude - o_x!r} must exceed L_min ({L_MIN_MM})")
        return Admission("G1", {"O": origin_id, "PX": px, "AX": ax})

    if (n_pts, n_lns) == (3, 2):
        ax = _axis(horizontals, "horizontal")
        ay = _axis(verticals, "vertical")
        if ax == ay:
            _fail("the horizontal and vertical axes must be distinct lines")
        px, py = ents[ax]["end"], ents[ay]["end"]
        if px == py:
            _fail("the two axis endpoints must be distinct point entities")
        px_x, _ = _finite_nominal(ents[px], px)
        _, py_y = _finite_nominal(ents[py], py)
        if len(weak) != 2:
            _fail("G2 requires exactly two weak records (fix_param on PX.x and PY.y)")
        # canonical parameter order: entity-id lexicographic × (x, y)
        expected = sorted([(px, "x"), (py, "y")])
        mags = [_validate_weak_record(w, i, expected[i]) for i, w in enumerate(weak)]
        by_target = dict(zip(expected, mags))
        if by_target[(px, "x")] != px_x:
            _fail(f"weak magnitude contradicts the authored nominal for {px}.x")
        if by_target[(py, "y")] != py_y:
            _fail(f"weak magnitude contradicts the authored nominal for {py}.y")
        if not (by_target[(px, "x")] - o_x > L_MIN_MM):
            _fail(f"signed guard failed: {px}.x − {origin_id}.x must exceed L_min")
        if not (by_target[(py, "y")] - o_y > L_MIN_MM):
            _fail(f"signed guard failed: {py}.y − {origin_id}.y must exceed L_min")
        return Admission("G2", {"O": origin_id, "PX": px, "AX": ax,
                                "PY": py, "AY": ay})

    _fail(f"entity census (points={n_pts}, lines={n_lns}) matches no admitted "
          "shape (G0: 1 point; G1: 2 points + 1 line; G2: 3 points + 2 lines)")
    raise AssertionError("unreachable")


def derive_witness_descriptors(admission: Admission) -> tuple:
    """Doc §6: the catalog is a TOTAL function to an EXACT set — ∅ for every
    admitted skb-b0 graph (an explicit result of the §4 single-root proofs,
    not a default)."""
    assert admission.shape in ("G0", "G1", "G2")
    return ()


def validate_witness_set(witnesses: Sequence[Mapping[str, Any]],
                         admission: Admission) -> None:
    """Exact-set enforcement: missing, duplicate, and EXTRA witnesses all
    refuse. Under skb-b0 the derived set is empty, so ANY present witness is
    extra — recipe identity can never be perturbed by a valid-looking
    addition."""
    derived = derive_witness_descriptors(admission)
    if len(witnesses) != len(derived):  # derived == () under skb-b0
        _fail(
            f"witness set mismatch: record carries {len(witnesses)} witness(es); "
            f"the skb-b0 catalog derives exactly {len(derived)} for shape "
            f"{admission.shape} — extra witnesses are rejected (exact-set rule)"
        )
