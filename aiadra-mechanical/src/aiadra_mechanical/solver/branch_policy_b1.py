"""`branch_policy: "skb-b1"` — the production implementation.

The NORMATIVE authority is `Docs/SolverContracts/skb-b1.md` (ADR/0044 A4);
this module implements it and the parity tests enforce COMPLETE-structure
correspondence — constants, the local signature table, the array-order law,
the reference + profile predicates, the joint rules, and the equality-class
construction. Any semantic divergence is a defect HERE, never a fork of the
contract.

skb-b1 = skb-b0's anchored reference frame (restated verbatim, never
incorporated by reference — policy ids are self-contained) PLUS a
count-parameterized PROFILE family: non-construction points, segments and
bare circles, with `horizontal`/`vertical` admitted on profile segments
under UNSIGNED non-collapse guards. Every admitted member is single-root by
the full-column-rank argument (doc §5), so the witness catalog is EMPTY
everywhere and this policy freezes NO measure and NO epsilon.

Deliberately NOT a b0 import: this module is written to stand alone so a
future edit here can never silently change skb-b0's frozen behavior.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .contract import SOLVER_CONTRACT, WEAK_POLICY

POLICY_ID = "skb-b1"

# Versioned skb-b1 constants (doc §1; parity-checked). NO epsilon: the
# catalog is empty everywhere, so no witness measure is normative here.
L_MIN_MM = 1e-9
R_MIN_MM = 1e-9

CONSTANTS = {
    "policy_id": POLICY_ID,
    "solver_contract": SOLVER_CONTRACT,
    "weak_policy": WEAK_POLICY,
    "L_min_mm": L_MIN_MM,
    "R_min_mm": R_MIN_MM,
}

LOCAL_TABLE = {
    "entity_kinds": ["point", "line", "circle"],
    "construction_only": False,
    "blocks": ["reference", "profile"],
    "fact_kinds": {
        "fix": {"signature": ["point"], "class": "strong", "blocks": ["reference"]},
        "horizontal": {"signature": ["line"], "class": "strong",
                       "blocks": ["reference", "profile"]},
        "vertical": {"signature": ["line"], "class": "strong",
                     "blocks": ["reference", "profile"]},
        "fix_param": {"signature": ["parameter"], "class": "weak-completion-only"},
    },
    "dimension_kinds": {},
}

ARRAY_ORDER = {
    "entities": "unordered",
    "constraints": "unordered",
    "dimensions": "unordered",
    "references": "unordered",
    "weak_completion": "canonical",
    "witnesses": "canonical",
}

REFERENCE_PREDICATE = {
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
        "guards": [{"signed_displacement": ["PX.x", "O.x"], "exceeds": "L_min_mm"}],
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
        "guards_add": [{"signed_displacement": ["PY.y", "O.y"], "exceeds": "L_min_mm"}],
    },
}

PROFILE_PREDICATE = {
    "entities": {
        "points": {"type": "point", "construction": False, "count": "K >= 0"},
        "segments": {"type": "line", "construction": False, "count": "M >= 0",
                     "refs": {"start": "profile point", "end": "profile point"}},
        "circles": {"type": "circle", "construction": False, "count": "C >= 0",
                    "refs": {"center": "profile point"}, "parameters": ["radius"]},
    },
    "strong_facts": {
        "axis": {"kinds": ["horizontal", "vertical"],
                 "signature": ["profile segment"], "max_per_segment": 1},
    },
    "rules": [
        "presence: M + C >= 1",
        "reference_integrity: every segment start/end and every circle center resolves to a declared profile point",
        "no_orphans: every profile point is a segment endpoint or a circle center",
        "topological_distinctness: a segment's start and end refs are different entity ids",
        "geometric_non_collapse_segment: effective euclidean length > L_min_mm for EVERY segment (constrained or not)",
        "geometric_non_collapse_circle: effective radius > R_min_mm for EVERY circle",
        "no_duplicate_edges: an unordered endpoint-id pair appears at most once",
        "branch_vertices_admitted: a profile point may have any incidence degree",
        "exact_canonical_completion: the weak set equals the exact skb-0 enumeration for the admitted strong graph",
    ],
}

JOINT_RULES = [
    "block_independence: no entity is shared between blocks and no fact references entities from both blocks",
    "single_anchor: exactly one fix in the whole graph, naming a reference point",
    "no_dimensions: the dimension array is empty",
    "weak_targets_are_free_scalars: every weak record targets a scalar of the graph and no scalar is targeted twice",
    "empty_witness_set: any present witness is EXTRA and refuses",
]

EQUALITY_CLASSES = {
    "scalars": "for each profile point by entity id: x then y; for each profile circle by entity id: radius",
    "unions": {
        "horizontal": "P.y ~ Q.y for the segment's endpoints P,Q",
        "vertical": "P.x ~ Q.x for the segment's endpoints P,Q",
    },
    "singletons": "every circle radius is its own class",
    "class_order": "by the lexicographically smallest member scalar id (<entity_id>.<parameter>)",
    "basis_vector": "the integer indicator of the class members",
    "cross_check": "the number of classes MUST equal the number of committed weak-completion records",
}


class OutOfDomain(ValueError):
    """Typed skb-b1 refusal — the graph is not admitted under this policy."""


def _fail(reason: str) -> None:
    raise OutOfDomain(f"branch_policy skb-b1: out-of-domain — {reason}")


def _is_number(v: Any) -> bool:
    """Strict JSON-number predicate: booleans are NOT numbers (Python's bool
    subclasses int, so a naive isinstance admits true/false where the wire
    language refuses). The five surfaces speak ONE language; this is it."""
    return type(v) in (int, float) and math.isfinite(v)


# Closed nested shapes — an unknown nested key would enter recipe identity
# with no contract semantics.
_POINT_KEYS = {"id", "type", "construction", "nominal"}
_LINE_KEYS = {"id", "type", "construction", "start", "end"}
_CIRCLE_KEYS = {"id", "type", "construction", "center", "radius"}
_CONSTRAINT_KEYS = {"id", "kind", "args"}
_NOMINAL_KEYS = {"x", "y"}
_WEAK_TARGET_KEYS = {"entity", "parameter"}
_WEAK_KEYS = {"id", "kind", "target", "value", "strength", "role",
              "visibility", "origin"}

# Canonical parameter order per entity kind (solver SCHEMA.md §1).
_PARAM_ORDER = {"point": ("x", "y"), "circle": ("radius",), "line": ()}


@dataclass(frozen=True)
class Admission:
    """An admitted skb-b1 graph: the reference shape, the profile counts, the
    reference role binding, and the canonical profile equality classes (the
    exact ker(A) basis the annotation authority consumes)."""

    shape: str                       # always "B1"
    reference_shape: str             # "G0" | "G1" | "G2"
    roles: Mapping[str, str]         # reference role -> entity id
    counts: Mapping[str, int]        # K, M, C, A
    classes: tuple                   # tuple[tuple[str, ...], ...] — scalar ids per class
    effective: Mapping[str, float]   # scalar id -> the value the solve pins


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _scalar(entity_id: str, parameter: str) -> str:
    return f"{entity_id}.{parameter}"


def _finite_nominal(e: Mapping[str, Any], eid: str) -> tuple[float, float]:
    nom = e.get("nominal")
    if not (isinstance(nom, Mapping) and set(nom.keys()) == _NOMINAL_KEYS):
        _fail(f"point {eid!r} nominal must be exactly {{x, y}}")
    x, y = nom.get("x"), nom.get("y")
    if not (_is_number(x) and _is_number(y)):
        _fail(f"point {eid!r} nominal is not strict finite numeric "
              "(booleans are not numbers)")
    return float(x), float(y)


def _validate_weak_record(w: Any, index: int,
                          expected_target: tuple[str, str],
                          unit: str) -> float:
    """Full verbatim skb-0 record validation — never target names alone.
    Returns the persisted magnitude (the EFFECTIVE value)."""
    if not isinstance(w, Mapping):
        _fail(f"weak record {index} is {type(w).__name__!s}, not a record")
    want_id = f"w{index + 1:02d}"
    if w.get("id") != want_id:
        _fail(f"weak record {index} id {w.get('id')!r} != canonical {want_id!r}")
    if w.get("kind") != "fix_param":
        _fail(f"weak record {want_id} kind {w.get('kind')!r} != 'fix_param'")
    tgt = w.get("target")
    if not (isinstance(tgt, Mapping)
            and set(tgt.keys()) == _WEAK_TARGET_KEYS
            and (tgt["entity"], tgt["parameter"]) == expected_target):
        _fail(f"weak record {want_id} target {tgt!r} != the canonical "
              f"completion's expected target {expected_target!r}")
    val = w.get("value")
    if not (isinstance(val, Mapping) and set(val.keys()) == {"magnitude", "unit"}
            and val.get("unit") == unit
            and _is_number(val.get("magnitude"))):
        _fail(f"weak record {want_id} value must be {{magnitude: strict finite "
              f"number, unit: {unit!r}}}")
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
    extra = set(w.keys()) - _WEAK_KEYS
    if extra:
        _fail(f"weak record {want_id} carries unknown fields {sorted(extra)}")
    return float(val["magnitude"])


class _Union:
    """Union-find over scalar ids (doc §4)."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, s: str) -> None:
        self._parent.setdefault(s, s)

    def find(self, s: str) -> str:
        root = s
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[s] != root:  # path compression
            self._parent[s], s = root, self._parent[s]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        # deterministic: the lexicographically smaller root wins
        lo, hi = (ra, rb) if ra < rb else (rb, ra)
        self._parent[hi] = lo

    def classes(self, members: Iterable[str]) -> tuple:
        buckets: dict[str, list[str]] = {}
        for s in members:
            buckets.setdefault(self.find(s), []).append(s)
        out = [tuple(sorted(v)) for v in buckets.values()]
        out.sort(key=lambda cls: cls[0])
        return tuple(out)


# ---------------------------------------------------------------------------
# admission
# ---------------------------------------------------------------------------


def admit_graph(entities: Sequence[Mapping[str, Any]],
                constraints: Sequence[Mapping[str, Any]],
                dimensions: Sequence[Mapping[str, Any]],
                weak_completion: Sequence[Mapping[str, Any]]) -> Admission:
    """The total whole-fact-graph admission predicate (doc §3).

    Raises :class:`OutOfDomain` for everything outside the admitted family —
    local-table violations, malformed blocks, failed guards, duplicate edges,
    orphan points, cross-block facts, and any weak set that is not the EXACT
    canonical skb-0 completion.
    """
    # ---- layer 1 (necessary) --------------------------------------------
    if dimensions:
        _fail("skb-b1 admits no dimensions")

    ents: dict[str, Mapping[str, Any]] = {}
    for e in entities:
        if not isinstance(e, Mapping):
            _fail(f"entity entry is {type(e).__name__!s}, not a record")
        eid = e.get("id")
        if not isinstance(eid, str) or not eid:
            _fail("entity without a non-empty string id")
        if eid in ents:
            _fail(f"duplicate entity id {eid!r}")
        etype = e.get("type")
        if etype not in LOCAL_TABLE["entity_kinds"]:
            _fail(f"entity {eid!r} type {etype!r} is outside the local table")
        if not isinstance(e.get("construction"), bool):
            _fail(f"entity {eid!r} must carry an explicit boolean construction flag")
        want = {"point": _POINT_KEYS, "line": _LINE_KEYS, "circle": _CIRCLE_KEYS}[etype]
        extra = set(e.keys()) - want
        if extra:
            _fail(f"entity {eid!r} carries unknown fields {sorted(extra)} "
                  "(the skb-b1 entity shapes are closed)")
        if etype == "line":
            if not (isinstance(e.get("start"), str) and isinstance(e.get("end"), str)):
                _fail(f"line {eid!r} start/end must be entity-id strings")
        if etype == "circle":
            if not isinstance(e.get("center"), str):
                _fail(f"circle {eid!r} center must be an entity-id string")
            if not _is_number(e.get("radius")):
                _fail(f"circle {eid!r} radius must be a strict finite number")
        ents[eid] = e

    seen_cids: set[str] = set()
    for c in constraints:
        if not isinstance(c, Mapping):
            _fail(f"constraint entry is {type(c).__name__!s}, not a record")
        cid = c.get("id")
        if not isinstance(cid, str) or not cid or cid in seen_cids:
            _fail("constraint without a unique non-empty string id")
        seen_cids.add(cid)
        if c.get("kind") not in ("fix", "horizontal", "vertical"):
            _fail(f"constraint {cid!r} kind {c.get('kind')!r} is outside the local table")
        extra = set(c.keys()) - _CONSTRAINT_KEYS
        if extra:
            _fail(f"constraint {cid!r} carries unknown fields {sorted(extra)} "
                  "(the skb-b1 constraint shape is closed)")
        args = c.get("args")
        if not (isinstance(args, list) and len(args) == 1
                and isinstance(args[0], str)):
            _fail(f"constraint {cid!r} args must be a single entity-id string")
        if args[0] not in ents:
            _fail(f"constraint {cid!r} names unknown entity {args[0]!r}")

    # ---- block split -----------------------------------------------------
    ref_ids = {eid for eid, e in ents.items() if e["construction"] is True}
    pro_ids = {eid for eid, e in ents.items() if e["construction"] is False}

    def _block_of(eid: str) -> str:
        return "reference" if eid in ref_ids else "profile"

    # Structural refs must not cross blocks (joint rule 1).
    for eid, e in ents.items():
        refs = ([e["start"], e["end"]] if e["type"] == "line"
                else [e["center"]] if e["type"] == "circle" else [])
        for r in refs:
            if r not in ents:
                _fail(f"entity {eid!r} references unknown entity {r!r}")
            if _block_of(r) != _block_of(eid):
                _fail(f"entity {eid!r} references {r!r} across the "
                      "reference/profile block boundary")

    # ---- reference block: exactly G0 | G1 | G2 ---------------------------
    ref_pts = sorted(i for i in ref_ids if ents[i]["type"] == "point")
    ref_lns = sorted(i for i in ref_ids if ents[i]["type"] == "line")
    if any(ents[i]["type"] == "circle" for i in ref_ids):
        _fail("the reference block admits no circles")

    fixes = [c for c in constraints if c["kind"] == "fix"]
    if len(fixes) != 1:
        _fail("exactly one fix(point) anchor is required in the whole graph")
    origin_id = fixes[0]["args"][0]
    if origin_id not in ref_ids or ents[origin_id]["type"] != "point":
        _fail(f"fix names {origin_id!r}, which is not a reference point")

    ref_axis = [c for c in constraints
                if c["kind"] in ("horizontal", "vertical")
                and c["args"][0] in ref_ids]
    pro_axis = [c for c in constraints
                if c["kind"] in ("horizontal", "vertical")
                and c["args"][0] in pro_ids]

    roles: dict[str, str] = {"O": origin_id}
    n_rp, n_rl = len(ref_pts), len(ref_lns)
    if (n_rp, n_rl) == (1, 0):
        reference_shape = "G0"
        if ref_axis:
            _fail("G0 admits no reference axis facts")
    elif (n_rp, n_rl) == (2, 1):
        reference_shape = "G1"
    elif (n_rp, n_rl) == (3, 2):
        reference_shape = "G2"
    else:
        _fail(f"the reference block is neither G0, G1 nor G2 "
              f"({n_rp} point(s), {n_rl} line(s))")

    if reference_shape in ("G1", "G2"):
        hs = [c for c in ref_axis if c["kind"] == "horizontal"]
        vs = [c for c in ref_axis if c["kind"] == "vertical"]
        want_v = 1 if reference_shape == "G2" else 0
        if len(hs) != 1 or len(vs) != want_v:
            _fail(f"{reference_shape} requires exactly one horizontal reference "
                  f"axis and {want_v} vertical")
        ax = hs[0]["args"][0]
        if ents[ax]["type"] != "line" or ents[ax]["start"] != origin_id:
            _fail("the horizontal reference axis must start at the fixed origin")
        roles["AX"] = ax
        roles["PX"] = ents[ax]["end"]
        if reference_shape == "G2":
            ay = vs[0]["args"][0]
            if ents[ay]["type"] != "line" or ents[ay]["start"] != origin_id:
                _fail("the vertical reference axis must start at the fixed origin")
            roles["AY"] = ay
            roles["PY"] = ents[ay]["end"]
        named = {roles[k] for k in roles}
        if named != set(ref_ids):
            _fail("the reference block carries entities outside the "
                  f"{reference_shape} shape")

    # ---- profile block ---------------------------------------------------
    pro_pts = sorted(i for i in pro_ids if ents[i]["type"] == "point")
    pro_segs = sorted(i for i in pro_ids if ents[i]["type"] == "line")
    pro_circles = sorted(i for i in pro_ids if ents[i]["type"] == "circle")

    if len(pro_segs) + len(pro_circles) < 1:
        _fail("skb-b1 requires a non-empty profile block (M + C >= 1); a "
              "reference-only graph is a skb-b0 record")

    incident: dict[str, int] = {p: 0 for p in pro_pts}
    edges: set[frozenset] = set()
    for sid in pro_segs:
        s, e2 = ents[sid]["start"], ents[sid]["end"]
        if s not in incident or e2 not in incident:
            _fail(f"segment {sid!r} endpoints must be profile points")
        if s == e2:
            _fail(f"segment {sid!r} start and end are the same entity "
                  "(topological distinctness)")
        key = frozenset((s, e2))
        if key in edges:
            _fail(f"segment {sid!r} duplicates an existing edge between "
                  f"{s!r} and {e2!r} (duplicate and reversed-duplicate edges refuse)")
        edges.add(key)
        incident[s] += 1
        incident[e2] += 1
    for cid_ in pro_circles:
        ctr = ents[cid_]["center"]
        if ctr not in incident:
            _fail(f"circle {cid_!r} center must be a profile point")
        incident[ctr] += 1
    orphans = [p for p, n in incident.items() if n == 0]
    if orphans:
        _fail(f"orphan profile point(s) {orphans} — every profile point must be "
              "a segment endpoint or a circle centre")

    per_segment: dict[str, int] = {}
    for c in pro_axis:
        tgt = c["args"][0]
        if ents[tgt]["type"] != "line":
            _fail(f"axis fact {c['id']!r} targets {tgt!r}, which is not a segment")
        per_segment[tgt] = per_segment.get(tgt, 0) + 1
        if per_segment[tgt] > 1:
            _fail(f"segment {tgt!r} carries more than one axis fact")

    # ---- equality classes + the exact canonical completion ---------------
    uf = _Union()
    scalars: list[str] = []
    for p in pro_pts:
        for prm in _PARAM_ORDER["point"]:
            s = _scalar(p, prm)
            scalars.append(s)
            uf.add(s)
    for c_ in pro_circles:
        s = _scalar(c_, "radius")
        scalars.append(s)
        uf.add(s)
    for c in pro_axis:
        sid = c["args"][0]
        p, q = ents[sid]["start"], ents[sid]["end"]
        prm = "y" if c["kind"] == "horizontal" else "x"
        uf.union(_scalar(p, prm), _scalar(q, prm))
    classes = uf.classes(scalars)

    # The canonical completion accepts exactly one scalar per class — the
    # first member reached in canonical scalar order, which IS the class's
    # lexicographically smallest member (doc §4/§5 step 2).
    scalar_order = {s: i for i, s in enumerate(scalars)}
    profile_targets = sorted((cls[0] for cls in classes),
                             key=lambda s: scalar_order[s])

    # Reference-block completion is the frozen shape: G0 none, G1 PX.x,
    # G2 PX.x + PY.y.
    ref_targets: list[str] = []
    if reference_shape in ("G1", "G2"):
        ref_targets.append(_scalar(roles["PX"], "x"))
    if reference_shape == "G2":
        ref_targets.append(_scalar(roles["PY"], "y"))

    # The persisted weak array is canonically ordered over the WHOLE graph.
    all_targets = sorted(ref_targets + profile_targets,
                         key=lambda s: (s.rsplit(".", 1)[0], s.rsplit(".", 1)[1]))
    if len(weak_completion) != len(all_targets):
        _fail(f"weak completion has {len(weak_completion)} record(s); the exact "
              f"canonical skb-0 completion for this graph has {len(all_targets)}")

    magnitudes: dict[str, float] = {}
    for i, target in enumerate(all_targets):
        eid, prm = target.rsplit(".", 1)
        unit = "mm"
        magnitudes[target] = _validate_weak_record(
            weak_completion[i], i, (eid, prm), unit)

    # cross-check (doc §4): one class <-> one profile weak record
    if len(classes) != len(profile_targets):
        _fail("internal inconsistency: profile equality classes and profile "
              "weak records disagree")

    # ---- effective values + guards ---------------------------------------
    effective: dict[str, float] = {}
    for eid in ref_pts:
        x, y = _finite_nominal(ents[eid], eid)
        effective[_scalar(eid, "x")] = x
        effective[_scalar(eid, "y")] = y
    for p in pro_pts:
        x, y = _finite_nominal(ents[p], p)
        effective[_scalar(p, "x")] = x
        effective[_scalar(p, "y")] = y
    for c_ in pro_circles:
        effective[_scalar(c_, "radius")] = float(ents[c_]["radius"])
    # weak magnitudes override, and propagate across each equality class —
    # the values the solve will ACTUALLY pin.
    for target, mag in magnitudes.items():
        effective[target] = mag
    for cls in classes:
        rep = cls[0]
        if rep in magnitudes:
            for member in cls:
                effective[member] = magnitudes[rep]
    # reference determined members: a class containing a fixed scalar takes it
    if reference_shape in ("G1", "G2"):
        effective[_scalar(roles["PX"], "y")] = effective[_scalar(origin_id, "y")]
    if reference_shape == "G2":
        effective[_scalar(roles["PY"], "x")] = effective[_scalar(origin_id, "x")]

    # reference guards are SIGNED
    if reference_shape in ("G1", "G2"):
        d = effective[_scalar(roles["PX"], "x")] - effective[_scalar(origin_id, "x")]
        if not d > L_MIN_MM:
            _fail(f"reference X axis signed displacement {d!r} does not exceed "
                  f"L_min_mm={L_MIN_MM!r}")
    if reference_shape == "G2":
        d = effective[_scalar(roles["PY"], "y")] - effective[_scalar(origin_id, "y")]
        if not d > L_MIN_MM:
            _fail(f"reference Y axis signed displacement {d!r} does not exceed "
                  f"L_min_mm={L_MIN_MM!r}")

    # profile guards are UNSIGNED, and apply to EVERY segment
    for sid in pro_segs:
        p, q = ents[sid]["start"], ents[sid]["end"]
        dx = effective[_scalar(q, "x")] - effective[_scalar(p, "x")]
        dy = effective[_scalar(q, "y")] - effective[_scalar(p, "y")]
        if not math.hypot(dx, dy) > L_MIN_MM:
            _fail(f"segment {sid!r} effective length does not exceed "
                  f"L_min_mm={L_MIN_MM!r} (geometric non-collapse)")
    for c_ in pro_circles:
        if not effective[_scalar(c_, "radius")] > R_MIN_MM:
            _fail(f"circle {c_!r} effective radius does not exceed "
                  f"R_min_mm={R_MIN_MM!r}")

    return Admission(
        shape="B1",
        reference_shape=reference_shape,
        roles=dict(roles),
        counts={"K": len(pro_pts), "M": len(pro_segs),
                "C": len(pro_circles), "A": len(pro_axis)},
        classes=classes,
        effective=effective,
    )


def derive_witness_descriptors(admission: Admission) -> tuple:
    """Doc §6: the catalog is a TOTAL function to an EXACT set — ∅ for every
    admitted skb-b1 graph (an explicit result of the §5 single-root proofs,
    not a default)."""
    assert admission.shape == "B1"
    return ()


def validate_witness_set(witnesses: Sequence[Mapping[str, Any]],
                         admission: Admission) -> None:
    """Exact-set enforcement: missing, duplicate, and EXTRA witnesses all
    refuse. Under skb-b1 the derived set is empty, so ANY present witness is
    extra — recipe identity can never be perturbed by a valid-looking
    addition."""
    derived = derive_witness_descriptors(admission)
    if len(witnesses) != len(derived):
        _fail(
            f"witness set mismatch: record carries {len(witnesses)} witness(es); "
            f"the skb-b1 catalog derives exactly {len(derived)} — extra "
            "witnesses are rejected (exact-set rule)"
        )
