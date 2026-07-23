"""SK-B corpus skb-1 generator + machine checker (arc 20260715-3, Claude4).

Authors the corpus deterministically and refuses to emit any case that fails:

  1. id uniqueness + domain-signature validation (h-outdomain's deliberate
     violation is declared in-file);
  2. ledger arithmetic from the pinned per-kind equation tables (explanatory
     net_count) AND numeric-Jacobian RANK verification of dof_strong (Codex3 B2);
  3. residual evaluation of every expected solved geometry, per canonical
     residual BLOCK (length_mm / direction / angle_deg, SCHEMA section 2b);
  4. executable skb-0: the checker RUNS the completion enumeration and asserts
     the emitted weak records are exactly the algorithm's output, each raising
     rank by one, reaching zero DoF (d-under, and permutation-invariance on
     i-permute whose arrays are reversed);
  5. executable strong-supersession (P3) on d-under: add strong radius(a1)=10,
     run the rank-based removal walk, assert canonicality vs completion-from-
     scratch;
  6. redundancy/conflict verification: e's c05 proven rank-redundant and
     consistent; f's {d01,d03} proven a dependent pair with nonzero residual;
  7. an evaluator-existence gate: every accepted (kind x signature) in the
     domain table MUST have a residual evaluator, or the generator fails;
  8. a coverage gate: every accepted signature and entity type MUST be
     exercised by at least one positive (well/under) case; the matrix is
     emitted to coverage.md and regressions fail the build.

Run:  python generate_corpus.py             (verify + write cases + coverage.md)
      python generate_corpus.py --verify    (read-only: verify + compare to disk)
"""

import json
import math
import os
import sys

OUT = os.path.dirname(os.path.abspath(__file__))
TOL_RES = 1e-9        # residual tolerance per block for expected solved fixtures
RANK_TOL = 1e-7       # pivot tolerance on unit-normalized rows
FD_STEP = 1e-6        # central-difference step (scaled by max(1,|x|))

# ---------------------------------------------------------------- catalogues

# canonical parameter catalogue: per entity type, (parameter, canonical unit)
PARAMS = {
    "point": [("x", "mm"), ("y", "mm")],
    "line": [],
    "circle": [("radius", "mm")],
    "arc": [("radius", "mm"), ("start_angle", "deg"), ("end_angle", "deg")],
}
ENTITY_DOF = {t: len(ps) for t, ps in PARAMS.items()}

CONSTRAINT_EQ = {
    "coincident": 2, "point_on": 1, "horizontal": 1, "vertical": 1,
    "parallel": 1, "perpendicular": 1, "tangent": 1, "tangent_at": 1,
    "equal": 1, "fix": 2, "fix_param": 1,
}
DIMENSION_EQ = {"distance": 1, "length": 1, "angle": 1, "radius": 1, "diameter": 1}

# kind -> accepted operand-type signatures (SORTED tuples; "aend" = arc endpoint)
DOMAIN = {
    "coincident": [("point", "point"), ("aend", "point")],
    "point_on": [("line", "point"), ("circle", "point"), ("arc", "point")],
    "horizontal": [("line",)], "vertical": [("line",)],
    "parallel": [("line", "line")], "perpendicular": [("line", "line")],
    "tangent": [("circle", "line"), ("arc", "line"), ("circle", "circle"),
                ("arc", "circle"), ("arc", "arc")],
    # endpoint tangency: the line is tangent to the arc AT that arc endpoint,
    # encoded as direction alignment. The naive coincident + supporting-curve
    # tangent encoding of a joined tangent joint is JACOBIAN-SINGULAR at the
    # solution (the joint slides along the circle to first order) -- measured
    # by this checker on the original b-slot; tangent_at is the sketcher-
    # standard transversal encoding (cf. FreeCAD TangentViaPoint).
    "tangent_at": [("aend", "line")],
    "equal": [("line", "line"), ("circle", "circle"), ("arc", "circle"),
              ("arc", "arc")],
    "fix": [("point",)],
    "distance": [("point", "point"), ("line", "point")],
    "length": [("line",)], "angle": [("line", "line")],
    "radius": [("circle",), ("arc",)], "diameter": [("circle",), ("arc",)],
}
# fix_param targets one catalogue parameter; covered via emitted weak records.
COVERAGE_KEYS = ([(k, s) for k, sigs in DOMAIN.items() for s in sigs]
                 + [("fix_param", ("param",))])


def arg_type(arg, ents):
    if "." in arg:
        base, member = arg.split(".", 1)
        if ents[base]["type"] == "arc" and member in ("start", "end"):
            return "aend"
        raise ValueError(f"unknown member ref {arg}")
    return ents[arg]["type"]


def signature(fact, ents):
    return tuple(sorted(arg_type(a, ents) for a in fact["args"]))


def domain_ok(fact, ents):
    kind, args = fact["kind"], fact["args"]
    if signature(fact, ents) not in [tuple(sorted(s)) for s in DOMAIN.get(kind, [])]:
        return False
    if kind in ("point_on", "distance") and len(args) == 2:
        pass  # mixed signatures resolved by the sorted tuple; arg roles below
    if kind == "point_on" and arg_type(args[0], ents) != "point":
        return False
    return True


# ------------------------------------------------------- geometry evaluation

def pt(cfg, ents, ref):
    if "." in ref:
        base, member = ref.split(".", 1)
        cx, cy = pt(cfg, ents, ents[base]["center"])
        r = cfg[f"{base}.radius"]
        ang = cfg[f"{base}.start_angle"] if member == "start" else cfg[f"{base}.end_angle"]
        return (cx + r * math.cos(math.radians(ang)), cy + r * math.sin(math.radians(ang)))
    return (cfg[f"{ref}.x"], cfg[f"{ref}.y"])


def line_pts(cfg, ents, lid):
    return pt(cfg, ents, ents[lid]["start"]), pt(cfg, ents, ents[lid]["end"])


def unit_dir(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    return (dx / L, dy / L), L


def signed_point_line(p, a, b):
    (ux, uy), _ = unit_dir(a, b)
    return (p[0] - a[0]) * uy - (p[1] - a[1]) * ux


def curve_center_r(cfg, ents, cid):
    return pt(cfg, ents, ents[cid]["center"]), cfg[f"{cid}.radius"]


def wrap_deg(d):
    d = d % 360.0
    return d - 360.0 if d > 180.0 else d


# Registry of implemented evaluator signatures -- gate 7 in the module docstring.
EVAL_SIGS = {
    ("coincident", ("point", "point")), ("coincident", ("aend", "point")),
    ("point_on", ("line", "point")), ("point_on", ("circle", "point")),
    ("point_on", ("arc", "point")),
    ("horizontal", ("line",)), ("vertical", ("line",)),
    ("parallel", ("line", "line")), ("perpendicular", ("line", "line")),
    ("tangent", ("circle", "line")), ("tangent", ("arc", "line")),
    ("tangent", ("circle", "circle")), ("tangent", ("arc", "circle")),
    ("tangent", ("arc", "arc")), ("tangent_at", ("aend", "line")),
    ("equal", ("line", "line")), ("equal", ("circle", "circle")),
    ("equal", ("arc", "circle")), ("equal", ("arc", "arc")),
    ("fix", ("point",)),
    ("distance", ("point", "point")), ("distance", ("line", "point")),
    ("length", ("line",)), ("angle", ("line", "line")),
    ("radius", ("circle",)), ("radius", ("arc",)),
    ("diameter", ("circle",)), ("diameter", ("arc",)),
}


def fact_residuals(fact, ents, cfg, nominal_of=None):
    """Canonical residual list [(block, value)] per SCHEMA section 2b.

    Corpus-wide pinned branch: every curve-curve tangency in skb-1 is EXTERNAL.
    """
    kind = fact["kind"]
    if kind == "fix_param":
        tgt = fact["target"]
        key = f"{tgt['entity']}.{tgt['parameter']}"
        block = "angle_deg" if fact["value"]["unit"] == "deg" else "length_mm"
        return [(block, cfg[key] - fact["value"]["magnitude"])]
    args = fact["args"]
    t = sorted(arg_type(a, ents) for a in args)

    if kind == "coincident":
        (x1, y1), (x2, y2) = pt(cfg, ents, args[0]), pt(cfg, ents, args[1])
        return [("length_mm", x1 - x2), ("length_mm", y1 - y2)]
    if kind == "point_on":
        p = pt(cfg, ents, args[0])
        ct = arg_type(args[1], ents)
        if ct == "line":
            a, b = line_pts(cfg, ents, args[1])
            return [("length_mm", signed_point_line(p, a, b))]
        c, r = curve_center_r(cfg, ents, args[1])
        return [("length_mm", math.dist(p, c) - r)]
    if kind == "horizontal":
        a, b = line_pts(cfg, ents, args[0])
        (_, uy), _ = unit_dir(a, b)
        return [("direction", uy)]
    if kind == "vertical":
        a, b = line_pts(cfg, ents, args[0])
        (ux, _), _ = unit_dir(a, b)
        return [("direction", ux)]
    if kind in ("parallel", "perpendicular"):
        a1, b1 = line_pts(cfg, ents, args[0]); a2, b2 = line_pts(cfg, ents, args[1])
        u1, _ = unit_dir(a1, b1); u2, _ = unit_dir(a2, b2)
        cross = u1[0] * u2[1] - u1[1] * u2[0]
        dot = u1[0] * u2[0] + u1[1] * u2[1]
        return [("direction", cross if kind == "parallel" else dot)]
    if kind == "tangent":
        if "line" in t:
            lid = args[0] if arg_type(args[0], ents) == "line" else args[1]
            cid = args[1] if lid == args[0] else args[0]
            a, b = line_pts(cfg, ents, lid)
            c, r = curve_center_r(cfg, ents, cid)
            return [("length_mm", abs(signed_point_line(c, a, b)) - r)]
        (c1, r1), (c2, r2) = curve_center_r(cfg, ents, args[0]), curve_center_r(cfg, ents, args[1])
        return [("length_mm", math.dist(c1, c2) - (r1 + r2))]  # external branch
    if kind == "tangent_at":
        aend = args[0] if "." in args[0] else args[1]
        lid = args[1] if aend == args[0] else args[0]
        base, member = aend.split(".", 1)
        ang = cfg[f"{base}.start_angle"] if member == "start" else cfg[f"{base}.end_angle"]
        td = (-math.sin(math.radians(ang)), math.cos(math.radians(ang)))
        a, b = line_pts(cfg, ents, lid)
        u, _ = unit_dir(a, b)
        return [("direction", u[0] * td[1] - u[1] * td[0])]
    if kind == "equal":
        if t == ["line", "line"]:
            (a1, b1), (a2, b2) = line_pts(cfg, ents, args[0]), line_pts(cfg, ents, args[1])
            return [("length_mm", math.dist(a1, b1) - math.dist(a2, b2))]
        return [("length_mm", cfg[f"{args[0]}.radius"] - cfg[f"{args[1]}.radius"])]
    if kind == "fix":
        nom = nominal_of[args[0]]
        return [("length_mm", cfg[f"{args[0]}.x"] - nom["x"]),
                ("length_mm", cfg[f"{args[0]}.y"] - nom["y"])]
    if kind == "fix_param":
        tgt = fact["target"]
        key = f"{tgt['entity']}.{tgt['parameter']}"
        block = "angle_deg" if fact["value"]["unit"] == "deg" else "length_mm"
        return [(block, cfg[key] - fact["value"]["magnitude"])]

    v = fact.get("value_mm", fact.get("value_deg"))
    if kind == "distance":
        if t == ["point", "point"]:
            return [("length_mm", math.dist(pt(cfg, ents, args[0]), pt(cfg, ents, args[1])) - v)]
        pid = args[0] if arg_type(args[0], ents) == "point" else args[1]
        lid = args[1] if pid == args[0] else args[0]
        a, b = line_pts(cfg, ents, lid)
        return [("length_mm", abs(signed_point_line(pt(cfg, ents, pid), a, b)) - v)]
    if kind == "length":
        a, b = line_pts(cfg, ents, args[0])
        return [("length_mm", math.dist(a, b) - v)]
    if kind == "angle":
        a1, b1 = line_pts(cfg, ents, args[0]); a2, b2 = line_pts(cfg, ents, args[1])
        u1, _ = unit_dir(a1, b1); u2, _ = unit_dir(a2, b2)
        theta = math.degrees(math.atan2(u1[0] * u2[1] - u1[1] * u2[0],
                                        u1[0] * u2[0] + u1[1] * u2[1])) % 360.0
        return [("angle_deg", wrap_deg(theta - v))]
    if kind == "radius":
        return [("length_mm", cfg[f"{args[0]}.radius"] - v)]
    if kind == "diameter":
        return [("length_mm", 2.0 * cfg[f"{args[0]}.radius"] - v)]
    raise ValueError(f"no residual evaluator for {kind}({t})")


# ------------------------------------------------------- rank machinery

def param_list(entities):
    keys = []
    for e in sorted(entities, key=lambda e: e["id"]):
        for pname, _unit in PARAMS[e["type"]]:
            keys.append(f"{e['id']}.{pname}")
    return keys


def system_rows(facts, ents, cfg, params, nominal_of):
    """Numeric Jacobian rows (central differences) + row->fact_id map."""
    rows, owners = [], []
    for fact in facts:
        n_res = len(fact_residuals(fact, ents, cfg, nominal_of))
        grads = [[0.0] * len(params) for _ in range(n_res)]
        for j, key in enumerate(params):
            x0 = cfg[key]
            h = FD_STEP * max(1.0, abs(x0))
            cfg[key] = x0 + h
            rp = [v for _, v in fact_residuals(fact, ents, cfg, nominal_of)]
            cfg[key] = x0 - h
            rm = [v for _, v in fact_residuals(fact, ents, cfg, nominal_of)]
            cfg[key] = x0
            for i in range(n_res):
                grads[i][j] = (rp[i] - rm[i]) / (2.0 * h)
        for i in range(n_res):
            rows.append(grads[i])
            owners.append(fact["id"])
    return rows, owners


def mat_rank(rows):
    m = []
    for r in rows:
        n = math.sqrt(sum(v * v for v in r))
        if n > 1e-14:
            m.append([v / n for v in r])
    if not m:
        return 0
    ncols = len(m[0])
    rank = 0
    for c in range(ncols):
        piv, best = None, RANK_TOL
        for i in range(rank, len(m)):
            if abs(m[i][c]) > best:
                piv, best = i, abs(m[i][c])
        if piv is None:
            continue
        m[rank], m[piv] = m[piv], m[rank]
        pr = m[rank]
        for i in range(len(m)):
            if i != rank and abs(m[i][c]) > 1e-15:
                f = m[i][c] / pr[c]
                m[i] = [a - f * b for a, b in zip(m[i], pr)]
        rank += 1
        if rank == len(m):
            break
    return rank


def rows_parallel(r1, r2):
    n1 = math.sqrt(sum(v * v for v in r1)); n2 = math.sqrt(sum(v * v for v in r2))
    dot = sum(a * b for a, b in zip(r1, r2)) / (n1 * n2)
    return abs(abs(dot) - 1.0) < 1e-6


def unit_row(params, key):
    r = [0.0] * len(params)
    r[params.index(key)] = 1.0
    return r


def run_skb0(strong_rows, params, cfg0, start_index=1):
    """Execute the skb-0 completion enumeration (SCHEMA section 4).

    Walk params in canonical order; accept fix_param(scalar=snapshot) iff the
    rank rises by one; stop at full rank. Returns (records, final_rows).
    """
    rows = [list(r) for r in strong_rows]
    rank = mat_rank(rows)
    records, n = [], start_index
    for key in params:
        if rank == len(params):
            break
        cand = rows + [unit_row(params, key)]
        if mat_rank(cand) == rank + 1:
            rows = cand
            rank += 1
            eid, pname = key.split(".")
            records.append((eid, pname, cfg0[key]))
            n += 1
    return records, rows, rank


def weak_record(idx, eid, pname, value, ents):
    unit = dict(PARAMS[ents[eid]["type"]])[pname]
    return {"id": f"w{idx:02d}", "kind": "fix_param",
            "target": {"entity": eid, "parameter": pname},
            "value": {"magnitude": value, "unit": unit},
            "strength": "weak", "role": "driving", "visibility": "internal",
            "origin": {"category": "computed_result", "policy": "skb-0",
                       "solver_contract": "skb-c0"}}


# ------------------------------------------------------- case construction

def P(eid, x, y):
    return {"id": eid, "type": "point", "nominal": {"x": x, "y": y}}


def K(eid, center, r):
    return {"id": eid, "type": "circle", "center": center, "nominal": {"radius": r}}


def A(eid, center, r, s_deg, e_deg):
    return {"id": eid, "type": "arc", "center": center,
            "nominal": {"radius": r, "start_angle": s_deg, "end_angle": e_deg}}


def L(eid, a, b):
    return {"id": eid, "type": "line", "start": a, "end": b}


def C(cid, kind, *args):
    a = sorted(args) if kind in ("coincident", "parallel", "perpendicular",
                                 "tangent", "equal") else list(args)
    return {"id": cid, "kind": kind, "args": a}


def D(did, kind, args, value, unit="mm"):
    d = {"id": did, "kind": kind, "args": list(args), "strength": "strong"}
    d["value_deg" if unit == "deg" else "value_mm"] = value
    return d


def nominal_cfg(entities):
    cfg = {}
    for e in entities:
        if e["type"] in ("point", "circle", "arc"):
            for k, v in e["nominal"].items():
                cfg[f"{e['id']}.{k}"] = float(v)
    return cfg


CASES = []
ANCHOR_P1 = [{"id": "n01", "kind": "fix", "args": ["p1"]}]


def case(case_id, title, entities, constraints, dimensions, anchors, expected, extra=None):
    c = {"corpus_version": "skb-1", "case_id": case_id, "title": title,
         "weak_policy": "skb-0", "solver_contract": "skb-c0",
         "entities": entities, "constraints": constraints,
         "dimensions": dimensions, "anchors": anchors, "expected": expected}
    if extra:
        c.update(extra)
    CASES.append(c)
    return c


def expected_block(classification, dof, solved, oracle=None, weak=None, diagnostics=None):
    solved_blocks = {"length_mm": 0.0, "direction": 0.0, "angle_deg": 0.0}
    return {"classification": classification,
            "dof_strong": dof,
            "weak_completion": weak or [],
            "solved": solved,
            "residual_max": solved_blocks if solved is not None else None,
            "branch_oracle": oracle,
            "diagnostics": diagnostics or [],
            "tolerance": {"length_mm": 1e-9, "direction": 1e-9, "angle_deg": 1e-9},
            "ledger": None}


# --- the original ten (a..j), migrated to catalogue naming -------------------

def rect_entities():
    return [P("p1", 0, 0), P("p2", 40, 0), P("p3", 40, 30), P("p4", 0, 30),
            L("l1", "p1", "p2"), L("l2", "p2", "p3"), L("l3", "p3", "p4"), L("l4", "p4", "p1")]


def rect_constraints():
    return [C("c01", "horizontal", "l1"), C("c02", "vertical", "l2"),
            C("c03", "horizontal", "l3"), C("c04", "vertical", "l4")]


def rect_dims():
    return [D("d01", "length", ["l1"], 40.0), D("d02", "length", ["l2"], 30.0)]


def slot_entities():
    return [A("a1", "p1", 10, 90, 270), A("a2", "p2", 10, 270, 90),
            L("l1", "p3", "p4"), L("l2", "p5", "p6"),
            P("p1", 0, 0), P("p2", 60, 0),
            P("p3", 0, 10), P("p4", 60, 10), P("p5", 60, -10), P("p6", 0, -10)]


def slot_constraints():
    # tangent_at (endpoint tangency), not coincident + supporting-curve tangent:
    # the latter pair is Jacobian-singular at the joined tangency point (the
    # joint slides along the circle to first order) -- caught by this checker.
    return [C("c01", "coincident", "p3", "a1.start"), C("c02", "coincident", "p4", "a2.end"),
            C("c03", "coincident", "p5", "a2.start"), C("c04", "coincident", "p6", "a1.end"),
            C("c05", "tangent_at", "l1", "a1.start"), C("c06", "tangent_at", "l1", "a2.end"),
            C("c07", "tangent_at", "l2", "a2.start"), C("c08", "tangent_at", "l2", "a1.end"),
            C("c09", "equal", "a1", "a2"), C("c10", "horizontal", "l1")]


def slot_dims():
    return [D("d01", "distance", ["p1", "p2"], 60.0), D("d02", "radius", ["a1"], 10.0)]


BRACKET_Y = math.sqrt(65.0**2 - 58.25**2)


def bracket_entities(seed_p2=(50, 0), seed_p3=(58, 29)):
    return [P("p1", 0, 0), P("p2", *seed_p2), P("p3", *seed_p3),
            L("l1", "p1", "p2"), L("l2", "p2", "p3")]


def bracket_dims():
    return [D("d01", "length", ["l1"], 50.0), D("d02", "length", ["l2"], 30.0),
            D("d03", "distance", ["p1", "p3"], 65.0)]


def bracket_solved(sign_y):
    s = nominal_cfg(bracket_entities())
    s["p2.x"], s["p2.y"] = 50.0, 0.0
    s["p3.x"], s["p3.y"] = 58.25, sign_y * BRACKET_Y
    return s


case("a-rect", "anchored rectangle, H/V on all four sides",
     rect_entities(), rect_constraints(), rect_dims(), list(ANCHOR_P1),
     expected_block("well", 0, nominal_cfg(rect_entities())))

case("b-slot", "straight slot: two tangent arcs + two lines, equal radii",
     slot_entities(), slot_constraints(), slot_dims(), list(ANCHOR_P1),
     expected_block("well", 0, nominal_cfg(slot_entities())))

case("c-bracket", "angled bracket via three distances: apex-above branch",
     bracket_entities(), [C("c01", "horizontal", "l1")], bracket_dims(), list(ANCHOR_P1),
     expected_block("well", 0, bracket_solved(+1),
                    oracle={"kind": "cross_sign", "of": ["p1", "p2", "p3"], "expected": 1}),
     extra={"perturb": {"envelope_mm": 2.0, "prng": "python-random-uniform",
                        "seed": 20260716, "order": "canonical-params"}})

D_UNDER_ENTS = slot_entities()
W01 = weak_record(1, "a1", "radius", 10.0, {e["id"]: e for e in D_UNDER_ENTS})
case("d-under", "b-slot without the radius dimension: weak completion closes 1 DoF",
     D_UNDER_ENTS, slot_constraints(), [slot_dims()[0]], list(ANCHOR_P1),
     expected_block("under", 1, nominal_cfg(slot_entities()), weak=[W01]),
     extra={"supersession_test": {
         "add_strong": {"id": "d90", "kind": "radius", "args": ["a1"],
                        "strength": "strong", "value_mm": 10.0},
         "expected_final_weak": []}})

case("e-over-redundant", "a-rect plus redundant parallel(l1,l3)",
     rect_entities(), rect_constraints() + [C("c05", "parallel", "l1", "l3")],
     rect_dims(), list(ANCHOR_P1),
     expected_block("over", 0, nominal_cfg(rect_entities()),
                    diagnostics=[{"kind": "redundant", "members": ["c05"]}]))

case("f-conflicting", "a-rect plus contradictory second length(l1)=45",
     rect_entities(), rect_constraints(),
     rect_dims() + [D("d03", "length", ["l1"], 45.0)], list(ANCHOR_P1),
     expected_block("over", None, None,
                    diagnostics=[{"kind": "conflicting", "members": ["d01", "d03"]}]))

# iteration_cap 0: ZERO update steps allowed (SCHEMA section 5) -- the seed
# violates tolerance, so EVERY candidate must report non-convergent. Fully
# deterministic and candidate-neutral; no escalation clause needed.
case("g-nonconv", "well-posed bracket, adversarial seed, pinned iteration_cap=0",
     bracket_entities(seed_p2=(-750, 620), seed_p3=(900, -1100)),
     [C("c01", "horizontal", "l1")], bracket_dims(), list(ANCHOR_P1),
     expected_block("well", 0, None,
                    diagnostics=[{"kind": "non-convergent", "members": ["g-nonconv"]}]),
     extra={"iteration_cap": 0})

case("h-outdomain", "b-slot plus equal(a1,l1): line-arc equal is outside the domain table",
     slot_entities(), slot_constraints() + [C("c11", "equal", "a1", "l1")],
     slot_dims(), list(ANCHOR_P1),
     expected_block("rejected", None, None,
                    diagnostics=[{"kind": "out-of-domain", "members": ["c11"]}]),
     extra={"deliberate_domain_violation": "c11"})

d_under = CASES[3]
case("i-permute", "d-under with entities/constraints/dimensions arrays reversed",
     list(reversed(d_under["entities"])), list(reversed(d_under["constraints"])),
     list(reversed(d_under["dimensions"])), list(ANCHOR_P1),
     expected_block("under", 1, dict(d_under["expected"]["solved"]),
                    weak=[json.loads(json.dumps(W01))]),
     extra={"permutation_of": "d-under", "permutation": "array-reversal (pinned)"})

case("j-branch-flip", "c-bracket with the seed mirrored below the base",
     bracket_entities(seed_p3=(58, -29)), [C("c01", "horizontal", "l1")],
     bracket_dims(), list(ANCHOR_P1),
     expected_block("well", 0, bracket_solved(-1),
                    oracle={"kind": "cross_sign", "of": ["p1", "p2", "p3"], "expected": -1}),
     extra={"perturb": {"envelope_mm": 2.0, "prng": "python-random-uniform",
                        "seed": 20260717, "order": "canonical-params"}})

# --- the coverage extension (k..n) -- Codex3 B1 ------------------------------

# k-gear: circle entity, tangent/equal circle-circle, diameter+radius on circle,
# point_on(point,line).
case("k-gear", "three externally tangent circles on a horizontal centerline",
     [P("p1", 0, 0), P("p2", 50, 0), P("p3", 110, 0), L("l1", "p1", "p3"),
      K("k1", "p1", 20), K("k2", "p2", 30), K("k3", "p3", 30)],
     [C("c01", "horizontal", "l1"), C("c02", "point_on", "p2", "l1"),
      C("c03", "tangent", "k1", "k2"), C("c04", "tangent", "k2", "k3"),
      C("c05", "equal", "k2", "k3")],
     [D("d01", "diameter", ["k1"], 40.0), D("d02", "radius", ["k2"], 30.0)],
     list(ANCHOR_P1),
     expected_block("well", 0, nominal_cfg(
         [P("p1", 0, 0), P("p2", 50, 0), P("p3", 110, 0),
          K("k1", "p1", 20), K("k2", "p2", 30), K("k3", "p3", 30)])))

# l-tee: coincident(point,point), perpendicular, equal(line,line),
# distance(point,line).
case("l-tee", "perpendicular equal-length tee with a point held off the base",
     [P("p1", 0, 0), P("p2", 40, 0), P("p3", 40, 0), P("p4", 40, 40), P("p5", 40, 25),
      L("l1", "p1", "p2"), L("l2", "p3", "p4")],
     [C("c01", "horizontal", "l1"), C("c02", "coincident", "p2", "p3"),
      C("c03", "perpendicular", "l1", "l2"), C("c04", "equal", "l1", "l2"),
      C("c05", "point_on", "p5", "l2")],
     [D("d01", "length", ["l1"], 40.0), D("d02", "distance", ["p5", "l1"], 25.0)],
     list(ANCHOR_P1),
     expected_block("well", 0, nominal_cfg(
         [P("p1", 0, 0), P("p2", 40, 0), P("p3", 40, 0), P("p4", 40, 40), P("p5", 40, 25)])))

# m-fan: angle dimension, tangent(line,circle), point_on(point,circle),
# positive parallel.
M_R = 25.0 * math.sqrt(3.0)          # radius solved by the tangency
M_P3 = (15.0, 15.0 * math.sqrt(3.0))  # 30 mm along the 60-degree ray


def m_fan_solved():
    s = nominal_cfg([P("p1", 0, 0), P("p2", 50, 0)])
    s.update({"p3.x": M_P3[0], "p3.y": M_P3[1],
              "p4.x": 50.0 - M_R, "p4.y": 0.0,
              "p5.x": M_P3[0], "p5.y": M_P3[1],
              "p6.x": M_P3[0] + 20.0, "p6.y": M_P3[1],
              "k1.radius": M_R})
    return s


case("m-fan", "60-degree ray, circle tangent to it, intersection point, parallel cap",
     [P("p1", 0, 0), P("p2", 50, 0), P("p3", 15, 26), P("p4", 7, 0),
      P("p5", 15, 26), P("p6", 35, 26),
      L("l1", "p1", "p2"), L("l2", "p1", "p3"), L("l3", "p5", "p6"),
      K("k1", "p2", 43)],
     [C("c01", "horizontal", "l1"), C("c02", "tangent", "k1", "l2"),
      C("c03", "point_on", "p4", "k1"), C("c04", "point_on", "p4", "l1"),
      C("c05", "parallel", "l1", "l3"), C("c06", "coincident", "p3", "p5")],
     [D("d01", "length", ["l1"], 50.0), D("d02", "angle", ["l1", "l2"], 60.0, "deg"),
      D("d03", "length", ["l2"], 30.0), D("d04", "length", ["l3"], 20.0)],
     list(ANCHOR_P1),
     expected_block("well", 0, m_fan_solved()))

# n-arcs: tangent arc-arc + circle-arc, equal circle-arc, diameter(arc),
# point_on(point,arc), supporting-line point_on beyond the segment (p9 vs l3).
def n_arcs_entities():
    return [A("a1", "p1", 20, 0, 90), A("a2", "p6", 30, 180, 90), K("k1", "p7", 20),
            L("l1", "p1", "p4"), L("l2", "p1", "p5"), L("l3", "p6", "p10"),
            L("l4", "p12", "p13"),
            P("p1", 0, 0), P("p2", 20, 0), P("p3", 0, 20), P("p4", 30, 0),
            P("p5", 0, 30), P("p6", 50, 0), P("p7", 0, -40), P("p8", 20, 0),
            P("p9", 50, 30), P("p10", 50, 25), P("p11", 16, 12),
            P("p12", 0, 20), P("p13", 15, 20)]


case("n-arcs", "two tangent arcs, a tangent equal circle, and a point on the arc",
     n_arcs_entities(),
     [C("c01", "horizontal", "l1"), C("c02", "vertical", "l2"), C("c03", "vertical", "l3"),
      C("c04", "coincident", "p2", "a1.start"), C("c05", "point_on", "p2", "l1"),
      C("c06", "coincident", "p3", "a1.end"), C("c07", "point_on", "p3", "l2"),
      C("c08", "coincident", "p8", "a2.start"), C("c09", "point_on", "p8", "l1"),
      C("c10", "coincident", "p9", "a2.end"), C("c11", "point_on", "p9", "l3"),
      C("c12", "tangent", "a1", "a2"), C("c13", "tangent", "a1", "k1"),
      C("c14", "equal", "a1", "k1"), C("c15", "point_on", "p7", "l2"),
      C("c16", "point_on", "p6", "l1"), C("c17", "point_on", "p11", "a1"),
      # supporting-curve line-arc tangency, NON-degenerate: l4's endpoints are
      # pinned elsewhere, no coincidence at the tangency point.
      C("c18", "tangent", "a1", "l4"), C("c19", "horizontal", "l4"),
      C("c20", "point_on", "p12", "l2")],
     [D("d01", "diameter", ["a1"], 40.0), D("d02", "radius", ["a2"], 30.0),
      D("d03", "length", ["l1"], 30.0), D("d04", "length", ["l2"], 30.0),
      D("d05", "length", ["l3"], 25.0), D("d06", "distance", ["p11", "l1"], 12.0),
      D("d07", "length", ["l4"], 15.0)],
     list(ANCHOR_P1),
     expected_block("well", 0, nominal_cfg(n_arcs_entities())))


# ------------------------------------------------------- verification

def strong_facts(c):
    violation = c.get("deliberate_domain_violation")
    return ([f for f in c["constraints"] if f["id"] != violation]
            + c["dimensions"] + c["anchors"])


def verify(c):
    cid = c["case_id"]
    ents = {e["id"]: e for e in c["entities"]}
    nominal_of = {e["id"]: e["nominal"] for e in c["entities"] if "nominal" in e}
    exp = c["expected"]
    errs = []

    ids = ([e["id"] for e in c["entities"]] + [x["id"] for x in c["constraints"]] +
           [x["id"] for x in c["dimensions"]] + [x["id"] for x in c["anchors"]] +
           [w["id"] for w in exp["weak_completion"]])
    if len(ids) != len(set(ids)):
        errs.append("duplicate ids")

    violation = c.get("deliberate_domain_violation")
    for fact in c["constraints"] + c["dimensions"]:
        ok = domain_ok(fact, ents)
        if fact["id"] == violation:
            if ok:
                errs.append(f"{fact['id']} declared out-of-domain but the table ALLOWS it")
        elif not ok:
            errs.append(f"{fact['id']} {fact['kind']}({fact['args']}) not in the domain table")

    entity_dof = sum(ENTITY_DOF[e["type"]] for e in c["entities"])
    cs = [f for f in c["constraints"] if f["id"] != violation]
    c_eq = sum(CONSTRAINT_EQ[x["kind"]] for x in cs)
    d_eq = sum(DIMENSION_EQ[x["kind"]] for x in c["dimensions"])
    a_eq = sum(CONSTRAINT_EQ[x["kind"]] for x in c["anchors"])
    net = entity_dof - c_eq - d_eq - a_eq
    exp["ledger"] = {"entity_dof": entity_dof, "constraint_eq": c_eq,
                     "dimension_eq": d_eq, "anchor_eq": a_eq, "net_count": net}

    cls = exp["classification"]
    if cls == "rejected":
        return errs  # domain rejection is the whole check

    params = param_list(c["entities"])
    cfg = dict(exp["solved"]) if exp["solved"] is not None else nominal_cfg(c["entities"])
    facts = strong_facts(c)
    rows, owners = system_rows(facts, ents, cfg, params, nominal_of)
    rank = mat_rank(rows)
    dof_rank = len(params) - rank

    if exp["dof_strong"] is not None and dof_rank != exp["dof_strong"]:
        errs.append(f"rank-based dof {dof_rank} != expected dof_strong {exp['dof_strong']}")
    if cls == "well" and (net != 0 or dof_rank != 0):
        errs.append(f"well requires net 0 and rank-dof 0 (net={net}, dof={dof_rank})")
    if cls == "under" and (net != dof_rank or dof_rank <= 0):
        errs.append(f"under requires net==rank-dof>0 (net={net}, dof={dof_rank})")
    if cls == "over" and net >= 0:
        errs.append(f"over requires net<0 (net={net})")

    for diag in exp["diagnostics"]:
        if diag["kind"] == "redundant":
            for mid in diag["members"]:
                keep = [r for r, o in zip(rows, owners) if o != mid]
                if mat_rank(keep) != rank:
                    errs.append(f"{mid} declared redundant but its removal drops rank")
                fact = next(f for f in facts if f["id"] == mid)
                if any(abs(v) > TOL_RES for _, v in fact_residuals(fact, ents, cfg, nominal_of)):
                    errs.append(f"{mid} declared redundant-consistent but violated at solved")
        if diag["kind"] == "conflicting":
            m1, m2 = diag["members"]
            keep = [r for r, o in zip(rows, owners) if o != m2]
            if mat_rank(keep) != rank:
                errs.append(f"{m2} declared conflict-dependent but its removal drops rank")
            r1 = next(r for r, o in zip(rows, owners) if o == m1)
            r2 = next(r for r, o in zip(rows, owners) if o == m2)
            if not rows_parallel(r1, r2):
                errs.append(f"{m1}/{m2} rows are not a dependent pair")
            f2 = next(f for f in facts if f["id"] == m2)
            if all(abs(v) <= TOL_RES for _, v in fact_residuals(f2, ents, cfg, nominal_of)):
                errs.append(f"{m2} declared conflicting but satisfied at the reference config")

    # executable skb-0 (Codex3 B2): the checker RUNS the enumeration.
    if cls == "under":
        recs, comp_rows, comp_rank = run_skb0(rows, params, cfg)
        got = [weak_record(i + 1, e, p, v, ents) for i, (e, p, v) in enumerate(recs)]
        if got != exp["weak_completion"]:
            errs.append(f"skb-0 output {got} != expected weak_completion")
        if comp_rank != len(params):
            errs.append("skb-0 did not reach zero DoF (completion-stuck)")

    # executable strong-supersession (P3): removal walk + canonicality.
    if "supersession_test" in c:
        st = c["supersession_test"]
        add = st["add_strong"]
        add_rows, _ = system_rows([add], ents, cfg, params, nominal_of)
        strong2 = rows + add_rows
        weak_rows = [(w, unit_row(params, f"{w['target']['entity']}.{w['target']['parameter']}"))
                     for w in exp["weak_completion"]]
        kept = list(weak_rows)
        for w, r in weak_rows:
            trial = [x for x in kept if x[0]["id"] != w["id"]]
            if mat_rank(strong2 + [x[1] for x in trial]) == mat_rank(strong2 + [x[1] for x in kept]):
                kept = trial
        recs, _, _ = run_skb0(strong2 + [x[1] for x in kept], params, cfg)
        final = [w for w, _ in kept] + [weak_record(i + 1 + len(kept), e, p, v, ents)
                                        for i, (e, p, v) in enumerate(recs)]
        scratch, _, _ = run_skb0(strong2, params, cfg)
        scratch_recs = [weak_record(i + 1, e, p, v, ents) for i, (e, p, v) in enumerate(scratch)]
        if [w["target"] for w in final] != [w["target"] for w in scratch_recs]:
            errs.append("supersession result is not canonical vs completion-from-scratch")
        if final != st["expected_final_weak"]:
            errs.append(f"supersession final weak set {final} != expected {st['expected_final_weak']}")

    # residual check of the expected solved geometry, per block.
    if exp["solved"] is not None:
        want = set(params)
        if set(exp["solved"]) != want:
            errs.append(f"solved keys mismatch: missing {want - set(exp['solved'])}, "
                        f"extra {set(exp['solved']) - want}")
        worst = {"length_mm": 0.0, "direction": 0.0, "angle_deg": 0.0}
        s = exp["solved"]
        for fact in facts + exp["weak_completion"]:
            for block, v in fact_residuals(fact, ents, s, nominal_of):
                worst[block] = max(worst[block], abs(v))
        for block, w in worst.items():
            if w > TOL_RES:
                errs.append(f"solved geometry violates its facts: {block} residual {w:.3e}")
        oracle = exp["branch_oracle"]
        if oracle and oracle["kind"] == "cross_sign":
            a, b, p = (pt(s, ents, x) for x in oracle["of"])
            cross = (b[0]-a[0])*(p[1]-b[1]) - (b[1]-a[1])*(p[0]-b[0])
            got = 1 if cross > 0 else -1
            if got != oracle["expected"]:
                errs.append(f"branch oracle mismatch: computed {got}, expected {oracle['expected']}")
    return errs


def coverage():
    """Signature coverage over positive (well/under) cases; fail on any gap."""
    hits = {key: [] for key in COVERAGE_KEYS}
    etypes = {t: [] for t in PARAMS}
    for c in CASES:
        if c["expected"]["classification"] not in ("well", "under"):
            continue
        ents = {e["id"]: e for e in c["entities"]}
        violation = c.get("deliberate_domain_violation")
        for e in c["entities"]:
            etypes[e["type"]].append(c["case_id"])
        for fact in c["constraints"] + c["dimensions"] + c["anchors"]:
            if fact["id"] == violation:
                continue
            key = (fact["kind"], signature(fact, ents))
            if key in hits:
                hits[key].append(c["case_id"])
        for w in c["expected"]["weak_completion"]:
            hits[("fix_param", ("param",))].append(c["case_id"])
    gaps = [k for k, v in hits.items() if not v] + \
           [("entity", (t,)) for t, v in etypes.items() if not v]
    lines = ["# skb-1 coverage matrix (generated -- do not edit)", "",
             "| kind | signature | positive cases |", "|---|---|---|"]
    for (kind, sig), cases_ in sorted(hits.items()):
        lines.append(f"| `{kind}` | `{','.join(sig)}` | {', '.join(sorted(set(cases_))) or '**GAP**'} |")
    for t, cases_ in sorted(etypes.items()):
        lines.append(f"| entity | `{t}` | {', '.join(sorted(set(cases_))) or '**GAP**'} |")
    return gaps, "\n".join(lines) + "\n"


def canonical_json(c):
    def clean(o):
        if isinstance(o, float):
            if math.isnan(o) or math.isinf(o):
                raise ValueError("NaN/Infinity forbidden in corpus serialization")
            return 0.0 if o == 0.0 else o  # canonicalize -0.0
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o
    return json.dumps(clean(c), indent=2, sort_keys=True, allow_nan=False) + "\n"


def main():
    verify_only = "--verify" in sys.argv
    missing_evals = set()
    for kind, sigs in DOMAIN.items():
        for sig in sigs:
            if (kind, tuple(sorted(sig))) not in EVAL_SIGS and kind not in ("fix",):
                if (kind, sig) not in EVAL_SIGS:
                    missing_evals.add((kind, sig))
    missing_evals = {(k, s) for (k, s) in missing_evals
                     if (k, tuple(sorted(s))) not in EVAL_SIGS}
    if missing_evals:
        print(f"FAIL  evaluator gate: no residual evaluator for {sorted(missing_evals)}")
        sys.exit(1)

    failures = 0
    for c in CASES:
        errs = verify(c)
        led = c["expected"]["ledger"]
        dof = c["expected"]["dof_strong"]
        line = (f"{c['case_id']:<18} {c['expected']['classification']:<9} "
                f"params={led['entity_dof']:>2} eq={led['constraint_eq']+led['dimension_eq']+led['anchor_eq']:>2} "
                f"net={led['net_count']:>2} rank-dof={dof if dof is not None else '-'}")
        if errs:
            failures += 1
            print(f"FAIL  {line}")
            for e in errs:
                print(f"      !! {e}")
        else:
            print(f"ok    {line}")

    gaps, matrix = coverage()
    if gaps:
        failures += 1
        print("FAIL  coverage gate: unexercised signatures:")
        for g in gaps:
            print(f"      !! {g}")

    if failures:
        print(f"\n{failures} failure group(s) -- nothing written.")
        sys.exit(1)

    if verify_only:
        drift = []
        for c in CASES:
            path = os.path.join(OUT, f"{c['case_id']}.json")
            with open(path, encoding="utf-8") as f:
                if f.read() != canonical_json(c):
                    drift.append(c["case_id"])
        print(f"\nverify-only: all checks green; disk drift: {drift or 'none'}")
        sys.exit(1 if drift else 0)

    for c in CASES:
        with open(os.path.join(OUT, f"{c['case_id']}.json"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(canonical_json(c))
    with open(os.path.join(OUT, "coverage.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(matrix)
    print(f"\nall {len(CASES)} cases verified and emitted; coverage.md written.")


if __name__ == "__main__":
    main()
