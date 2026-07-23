"""The canonical skb-c0 layer: domain table, residuals, rank, skb-0.

Ported VERBATIM (numerics untouched) from the accepted SK-B corpus
machinery (arc 20260715-3, ``corpus/generate_corpus.py`` +
``harness/own_baseline.py`` — both AIADRA-authored). The frozen originals
remain in ``aiadra-solver/testkit`` as the permanent gate reference; the
pytest floor asserts this production copy reproduces the accepted corpus
digest byte-for-byte, which is what keeps the two from drifting.

Everything here is AIADRA-owned and candidate-neutral: the residual
definitions are the meaning of a constraint under ``skb-c0``, not a
property of any particular numerical library.
"""
from __future__ import annotations

import json
import math

from .contract import FD_STEP, RANK_TOL

# canonical parameter catalogue: per entity type, (parameter, canonical unit)
PARAMS = {
    "point": [("x", "mm"), ("y", "mm")],
    "line": [],
    "circle": [("radius", "mm")],
    "arc": [("radius", "mm"), ("start_angle", "deg"), ("end_angle", "deg")],
}

# kind -> accepted operand-type signatures (SORTED tuples; "aend" = arc endpoint)
DOMAIN = {
    "coincident": [("point", "point"), ("aend", "point")],
    "point_on": [("line", "point"), ("circle", "point"), ("arc", "point")],
    "horizontal": [("line",)],
    "vertical": [("line",)],
    "parallel": [("line", "line")],
    "perpendicular": [("line", "line")],
    "tangent": [("circle", "line"), ("arc", "line"), ("circle", "circle"),
                ("arc", "circle"), ("arc", "arc")],
    "tangent_at": [("aend", "line")],
    "equal": [("line", "line"), ("circle", "circle"), ("arc", "circle"),
              ("arc", "arc")],
    "fix": [("point",)],
    "distance": [("point", "point"), ("line", "point")],
    "length": [("line",)],
    "angle": [("line", "line")],
    "radius": [("circle",), ("arc",)],
    "diameter": [("circle",), ("arc",)],
}


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


def fact_residuals(fact, ents, cfg, nominal_of=None):
    """Canonical residual list [(block, value)] per skb-1 SCHEMA section 2b.

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
        a1, b1 = line_pts(cfg, ents, args[0])
        a2, b2 = line_pts(cfg, ents, args[1])
        u1, _ = unit_dir(a1, b1)
        u2, _ = unit_dir(a2, b2)
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
        a1, b1 = line_pts(cfg, ents, args[0])
        a2, b2 = line_pts(cfg, ents, args[1])
        u1, _ = unit_dir(a1, b1)
        u2, _ = unit_dir(a2, b2)
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


def unit_row(params, key):
    r = [0.0] * len(params)
    r[params.index(key)] = 1.0
    return r


def run_skb0(strong_rows, params, cfg0, start_index=1):
    """Execute the skb-0 completion enumeration (skb-1 SCHEMA section 4).

    Walk params in canonical order; accept fix_param(scalar=snapshot) iff the
    rank rises by one; stop at full rank.
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


def nominal_cfg(entities):
    cfg = {}
    for e in entities:
        if e["type"] in ("point", "circle", "arc"):
            for k, v in e["nominal"].items():
                cfg[f"{e['id']}.{k}"] = float(v)
    return cfg


def block_worst(pairs):
    worst = {"length_mm": 0.0, "direction": 0.0, "angle_deg": 0.0}
    for block, v in pairs:
        worst[block] = max(worst[block], abs(v))
    return worst


def canonical_result_bytes(result):
    """The skb-canon-1 serializer (skb-1 SCHEMA section 5)."""
    def clean(o):
        if isinstance(o, float):
            if math.isnan(o) or math.isinf(o):
                raise ValueError("NaN/Infinity forbidden")
            return 0.0 if o == 0.0 else o
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o
    return json.dumps(clean(result), sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode()
