"""The production solve pipeline over the verified native artifact.

Ported from the accepted SK-B Gate-1/2 planegcs harness
(arc 20260715-3, ``harness/planegcs_candidate.py``) with the numerics
UNTOUCHED — the pytest floor proves this port reproduces the accepted
corpus digest byte-for-byte. Division of labor per the skb-c0 contract:

- the native library provides solve (DogLeg, native convergence 1e-10),
  diagnose (DoF / conflicting / redundant via fact tags), and the
  update-step budget;
- AIADRA owns everything above it: domain validation, the skb-0
  completion policy, candidate-neutral residual evaluation from solved
  values, classification, and the typed DTO.

Deliberately NO replay surface here (Codex17 B2): the SK-B ``skb-replay-1``
solved-snapshot replay is EVIDENCE MACHINERY and lives only in the frozen
``aiadra-solver/testkit`` harnesses. How production recovers a discrete
branch is an ADR/0044 Amendment A2 decision (a typed branch-selector fact
plus persisted weak facts — never a field of derived solved coordinates);
until F2 lands that schema, this module solves from nominal geometry only.
"""
from __future__ import annotations

import math
import time
from typing import Any, Mapping

from . import canonical as gc
from .contract import DEFAULT_ITERATION_CAP
from .loader import load_solver
from .result import SolveResult, SolveTelemetry


def _snap_angle(rad: float) -> float:
    for target in (0.0, math.pi, -math.pi):
        if abs(rad - target) < 1e-6:
            return target
    return rad  # an unsnapped seed angle would surface in results


class _Builder:
    """Translates one skb-1-shaped system into a native solver System.

    Seeds are the NOMINAL geometry only. There is deliberately no
    seed-override input on the production surface (Codex17 B2) — branch
    recovery arrives with the A2 typed branch selector in F2.
    """

    def __init__(self, case, weak=()):
        native = load_solver()
        self.sys = native.System()
        self.case = case
        self.ents = {e["id"]: e for e in case["entities"]}
        self.seed_full = gc.nominal_cfg(case["entities"])
        fixed_points = {a["args"][0] for a in case["anchors"] if a["kind"] == "fix"}
        fixed_params = {(w["target"]["entity"], w["target"]["parameter"]) for w in weak}
        weak_values = {(w["target"]["entity"], w["target"]["parameter"]):
                       w["value"]["magnitude"] for w in weak}
        self.pmap = {}    # "eid.param" -> binding param index
        self.points = {}  # point entity id -> binding point index
        self.lines = {}
        self.circles = {}
        self.arcs = {}    # arc id -> dict(idx, start_pt, end_pt)

        def par(eid, pname, value, unit="mm"):
            free = not ((eid, pname) in fixed_params
                        or (eid in fixed_points and pname in ("x", "y")))
            # FREE params seed from the nominal snapshot; FIXED params take
            # their AUTHORITATIVE value — fix anchors at the nominal
            # (SCHEMA section 2), weak fix_param at the record value.
            v = self.seed_full.get(f"{eid}.{pname}", value) if free else value
            v = weak_values.get((eid, pname), v)
            if unit == "deg":
                v = math.radians(v)
            idx = self.sys.add_param(float(v), free)
            self.pmap[f"{eid}.{pname}"] = idx
            return idx

        for e in case["entities"]:  # file order (permutation-meaningful)
            if e["type"] == "point":
                ix = par(e["id"], "x", e["nominal"]["x"])
                iy = par(e["id"], "y", e["nominal"]["y"])
                self.points[e["id"]] = self.sys.add_point(ix, iy)
        for e in case["entities"]:
            if e["type"] == "line":
                self.lines[e["id"]] = self.sys.add_line(
                    self.points[e["start"]], self.points[e["end"]])
            elif e["type"] == "circle":
                ir = par(e["id"], "radius", e["nominal"]["radius"])
                self.circles[e["id"]] = self.sys.add_circle(
                    self.points[e["center"]], ir)
            elif e["type"] == "arc":
                nom = e["nominal"]
                ir = par(e["id"], "radius", nom["radius"])
                isa = par(e["id"], "start_angle", nom["start_angle"], "deg")
                iea = par(e["id"], "end_angle", nom["end_angle"], "deg")
                sx, sy = gc.pt(self.seed_full, self.ents, f"{e['id']}.start")
                ex, ey = gc.pt(self.seed_full, self.ents, f"{e['id']}.end")
                isx = self.sys.add_param(sx, True)
                isy = self.sys.add_param(sy, True)
                iex = self.sys.add_param(ex, True)
                iey = self.sys.add_param(ey, True)
                sp = self.sys.add_point(isx, isy)
                ep = self.sys.add_point(iex, iey)
                # diagnostic access to endpoint params (not part of the DTO)
                self.pmap[f"{e['id']}.__sx"] = isx
                self.pmap[f"{e['id']}.__sy"] = isy
                self.pmap[f"{e['id']}.__ex"] = iex
                self.pmap[f"{e['id']}.__ey"] = iey
                self.arcs[e["id"]] = {"idx": self.sys.add_arc(
                    self.points[e["center"]], sp, ep, isa, iea, ir),
                    "start": sp, "end": ep}

        self.tag_to_fact = {}
        facts = case["constraints"] + case["dimensions"]
        for i, fact in enumerate(facts):
            tag = i + 1
            self.tag_to_fact[tag] = fact["id"]
            self._add(fact, tag)

    def _endpoint(self, ref):
        base, member = ref.split(".", 1)
        return self.arcs[base]["start" if member == "start" else "end"]

    def _value_param(self, fact):
        if "value_deg" in fact:
            return self.sys.add_param(math.radians(fact["value_deg"]), False)
        return self.sys.add_param(float(fact["value_mm"]), False)

    def _add(self, fact, tag):
        s, k, args = self.sys, fact["kind"], fact["args"]
        ents = self.ents
        t = sorted(gc.arg_type(a, ents) for a in args)
        cfg = self.seed_full
        if k == "horizontal":
            s.horizontal(self.lines[args[0]], tag)
        elif k == "vertical":
            s.vertical(self.lines[args[0]], tag)
        elif k == "parallel":
            s.parallel(self.lines[args[0]], self.lines[args[1]], tag)
        elif k == "perpendicular":
            s.perpendicular(self.lines[args[0]], self.lines[args[1]], tag)
        elif k == "coincident":
            idx = []
            for a in args:
                idx.append(self._endpoint(a) if "." in a else self.points[a])
            s.p2p_coincident(idx[0], idx[1], tag)
        elif k == "point_on":
            p = self.points[args[0]]
            ct = gc.arg_type(args[1], ents)
            if ct == "line":
                s.point_on_line(p, self.lines[args[1]], tag)
            elif ct == "circle":
                s.point_on_circle(p, self.circles[args[1]], tag)
            else:
                s.point_on_arc(p, self.arcs[args[1]]["idx"], tag)
        elif k == "tangent":
            if "line" in t:
                lid = args[0] if gc.arg_type(args[0], ents) == "line" else args[1]
                cid = args[1] if lid == args[0] else args[0]
                a, b = gc.line_pts(cfg, ents, lid)
                center = gc.pt(cfg, ents, ents[cid]["center"])
                # native ConstraintTangent(line, curve, ccw): pinned against
                # the corpus (n-arcs/m-fan) — ccw=True corresponds to the
                # center on the NEGATIVE side of the directed line.
                ccw = gc.signed_point_line(center, a, b) < 0
                if gc.arg_type(cid, ents) == "circle":
                    s.tangent_lc(self.lines[lid], self.circles[cid], ccw, tag)
                else:
                    s.tangent_la(self.lines[lid], self.arcs[cid]["idx"], ccw, tag)
            elif t == ["arc", "arc"]:
                s.tangent_aa(self.arcs[args[0]]["idx"], self.arcs[args[1]]["idx"], tag)
            elif t == ["circle", "circle"]:
                s.tangent_cc(self.circles[args[0]], self.circles[args[1]], tag)
            else:
                cid = args[0] if gc.arg_type(args[0], ents) == "circle" else args[1]
                aid = args[1] if cid == args[0] else args[0]
                s.tangent_ca(self.circles[cid], self.arcs[aid]["idx"], tag)
        elif k == "tangent_at":
            aend = args[0] if "." in args[0] else args[1]
            lid = args[1] if aend == args[0] else args[0]
            base, _ = aend.split(".", 1)
            iangle = self.sys.add_param(0.0, False)
            s.angle_via_point_la(self.lines[lid], self.arcs[base]["idx"],
                                 self._endpoint(aend), iangle, tag)
            # measure the native angle at the (exactly satisfying) seed,
            # snap to 0/+-pi, pin it — branch-from-seed, convention-safe
            s.set_param(iangle, _snap_angle(s.constraint_error(tag)))
        elif k == "equal":
            if t == ["line", "line"]:
                s.equal_length(self.lines[args[0]], self.lines[args[1]], tag)
            elif t == ["circle", "circle"]:
                s.equal_radius_cc(self.circles[args[0]], self.circles[args[1]], tag)
            elif t == ["arc", "arc"]:
                s.equal_radius_aa(self.arcs[args[0]]["idx"], self.arcs[args[1]]["idx"], tag)
            else:
                cid = args[0] if gc.arg_type(args[0], ents) == "circle" else args[1]
                aid = args[1] if cid == args[0] else args[0]
                s.equal_radius_ca(self.circles[cid], self.arcs[aid]["idx"], tag)
        elif k == "distance":
            if t == ["point", "point"]:
                s.p2p_distance(self.points[args[0]], self.points[args[1]],
                               self._value_param(fact), tag)
            else:
                pid = args[0] if gc.arg_type(args[0], ents) == "point" else args[1]
                lid = args[1] if pid == args[0] else args[0]
                s.p2l_distance(self.points[pid], self.lines[lid],
                               self._value_param(fact), tag)
        elif k == "length":
            line = self.ents[args[0]]
            s.p2p_distance(self.points[line["start"]], self.points[line["end"]],
                           self._value_param(fact), tag)
        elif k == "angle":
            s.l2l_angle(self.lines[args[0]], self.lines[args[1]],
                        self._value_param(fact), tag)
        elif k == "radius":
            if gc.arg_type(args[0], ents) == "circle":
                s.circle_radius(self.circles[args[0]], self._value_param(fact), tag)
            else:
                s.arc_radius(self.arcs[args[0]]["idx"], self._value_param(fact), tag)
        elif k == "diameter":
            if gc.arg_type(args[0], ents) == "circle":
                s.circle_diameter(self.circles[args[0]], self._value_param(fact), tag)
            else:
                s.arc_diameter(self.arcs[args[0]]["idx"], self._value_param(fact), tag)
        else:
            raise ValueError(f"unmapped kind {k}")

    def solved_cfg(self):
        cfg = {}
        for e in self.case["entities"]:
            for pname, _unit in gc.PARAMS[e["type"]]:
                v = self.sys.get_param(self.pmap[f"{e['id']}.{pname}"])
                if _unit == "deg":
                    v = math.degrees(v) % 360.0
                cfg[f"{e['id']}.{pname}"] = v
        return cfg


def solve_feasible(case: Mapping[str, Any]) -> dict | None:
    """Solve the STRONG system ONLY and return the feasible configuration
    nearest the authored nominals — or None if it does not converge.

    ADDITIVE capability (arc 20260730-1, defect D-1). It changes NOTHING
    about `skb-0` (the completion algorithm) or `skb-c0` (the numeric
    contract): it runs the same DogLeg solve over the same residual blocks,
    simply without weak facts, and reports the intermediate the contract
    already computes conceptually.

    Why it exists: `skb-0` evaluates its rank test at the configuration it
    is handed. At AUTHORED nominals that do not yet satisfy the strong
    constraints (any hand-drawn rectangle), a slightly off-axis constraint
    row still looks independent, so completion pins BOTH scalars of one
    equality class and the system becomes contradictory. Completion must
    therefore run at the FEASIBLE solution. Per Petre's ruling (2026-07-30)
    the drawn coordinates nevertheless persist as the authored nominals —
    committing solved output as nominals would be an implicit rebaseline,
    and ADR/0044 A2.5/A2.9 require a rebaseline to be an explicit
    authoring transaction.
    """
    ents = {e["id"]: e for e in case["entities"]}
    nominal_of = {e["id"]: e["nominal"] for e in case["entities"] if "nominal" in e}

    bad = [f["id"] for f in case["constraints"] + case["dimensions"]
           if not gc.domain_ok(f, ents)]
    if bad:
        return None

    b = _Builder(case)                       # strong facts + anchors only
    b.sys.declare_unknowns()
    b.sys.init_solution()
    cap = case.get("iteration_cap", DEFAULT_ITERATION_CAP)
    b.sys.set_max_iter(cap)
    status = b.sys.solve(2, True)            # DogLeg, exactly as `solve`
    if status in (0, 1):
        b.sys.apply()
    cfg = b.solved_cfg()

    from .contract import TOL_BLOCK
    worst = gc.block_worst([
        r for f in (case["constraints"] + case["dimensions"] + case["anchors"])
        for r in gc.fact_residuals(f, ents, cfg, nominal_of)
    ])
    if status not in (0, 1) or any(v > TOL_BLOCK for v in worst.values()):
        return None
    return cfg


def solve(case: Mapping[str, Any]) -> SolveResult:
    """Solve one skb-1-shaped system; return the typed two-axis result."""
    t0 = time.perf_counter()
    ents = {e["id"]: e for e in case["entities"]}
    nominal_of = {e["id"]: e["nominal"] for e in case["entities"] if "nominal" in e}
    result = {"case_id": case["case_id"], "corpus_version": case["corpus_version"],
              "solver_contract": case["solver_contract"], "classification": None,
              "dof_strong": None, "weak_completion": [], "solved": None,
              "residual_max": None, "branch_oracle_value": None, "diagnostics": []}
    notes = "planegcs DogLeg via the verified aiadra-solver artifact"

    def finish(update_steps=None):
        return SolveResult.from_canonical(result, SolveTelemetry(
            wall_ms=(time.perf_counter() - t0) * 1000.0,
            update_steps=update_steps, notes=notes))

    bad = [f["id"] for f in case["constraints"] + case["dimensions"]
           if not gc.domain_ok(f, ents)]
    if bad:
        result["classification"] = "rejected"
        result["diagnostics"] = [{"kind": "out-of-domain", "members": sorted(bad)}]
        return finish()

    b = _Builder(case)
    b.sys.declare_unknowns()
    b.sys.init_solution()
    b.sys.diagnose(2)
    dof = b.sys.dofs()
    conflicting = sorted(b.tag_to_fact[t] for t in b.sys.conflicting() if t > 0)
    redundant = sorted(b.tag_to_fact[t] for t in b.sys.redundant() if t > 0)

    weak = []
    if conflicting or redundant:
        result["classification"] = "over"
        diags = []
        for rid in redundant:
            diags.append({"kind": "redundant", "members": [rid]})
        if conflicting:
            diags.append({"kind": "conflicting", "members": conflicting})
        result["diagnostics"] = diags
        if conflicting:
            return finish()
        result["dof_strong"] = 0
    elif dof > 0:
        result["classification"] = "under"
        result["dof_strong"] = dof
        # the AIADRA-owned skb-0 policy (identical for every candidate)
        params = gc.param_list(case["entities"])
        cfg0 = gc.nominal_cfg(case["entities"])
        facts = case["constraints"] + case["dimensions"] + case["anchors"]
        rows, _ = gc.system_rows(facts, ents, dict(cfg0), params, nominal_of)
        recs, _, comp_rank = gc.run_skb0(rows, params, cfg0)
        if comp_rank != len(params):
            result["diagnostics"] = [{"kind": "completion-stuck",
                                      "members": [case["case_id"]]}]
            return finish()
        weak = [gc.weak_record(i + 1, e, p, v, ents)
                for i, (e, p, v) in enumerate(recs)]
        result["weak_completion"] = weak
        b = _Builder(case, weak)  # rebuild with the completion applied
        b.sys.declare_unknowns()
        b.sys.init_solution()
    else:
        result["classification"] = "well"
        result["dof_strong"] = 0

    cap = case.get("iteration_cap", DEFAULT_ITERATION_CAP)
    b.sys.set_max_iter(cap)
    status = b.sys.solve(2, True)  # DogLeg
    update_steps = f"<= {cap} (planegcs-internal)"
    if status in (0, 1):
        b.sys.apply()
    cfg = b.solved_cfg()
    worst = gc.block_worst([r for f in (case["constraints"] + case["dimensions"]
                                        + case["anchors"] + weak)
                            if f.get("id") != case.get("deliberate_domain_violation")
                            for r in gc.fact_residuals(f, ents, cfg, nominal_of)])
    from .contract import TOL_BLOCK
    if status not in (0, 1) or any(v > TOL_BLOCK for v in worst.values()):
        result["diagnostics"] = result["diagnostics"] + [
            {"kind": "non-convergent", "members": [case["case_id"]]}]
        return finish(update_steps)

    result["solved"] = cfg
    result["residual_max"] = worst
    oracle = case.get("expected", {}).get("branch_oracle")
    if oracle and oracle["kind"] == "cross_sign":
        a, bb, p = (gc.pt(cfg, ents, x) for x in oracle["of"])
        cross = (bb[0] - a[0]) * (p[1] - bb[1]) - (bb[1] - a[1]) * (p[0] - bb[0])
        result["branch_oracle_value"] = 1 if cross > 0 else -1
    return finish(update_steps)
