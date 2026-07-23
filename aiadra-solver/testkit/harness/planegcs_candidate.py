"""SK-B Gate 1 -- the PLANEGCS candidate harness (arc 20260715-3).

Runs the extracted PlaneGCS (planegcs.dll + aiadra_solver.pyd, MSVC x64)
against the accepted skb-1 gate through the SAME lane as the own baseline:
same case files, same canonical residual definitions (generate_corpus),
same comparator (own_baseline.compare_expectation), same DTO.

Division of labor per the contract:
  - PlaneGCS provides: solve (DogLeg, native convergence 1e-10), diagnose
    (dof / conflicting / redundant via fact tags), the update-step budget
    (System.maxIter; the g-nonconv cap-0 forced stop).
  - AIADRA owns above the candidate: domain validation, the skb-0 completion
    policy (shared rank machinery -- identical weak records for BOTH
    candidates), residual_max computed candidate-neutrally from solved values
    via the canonical section-2b evaluators, DTO emission, comparison.

Modes:  python planegcs_candidate.py            full Gate-1 run + evidence
        python planegcs_candidate.py --digest   single run, print corpus digest
"""

import hashlib
import json
import math
import os
import platform
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(os.path.dirname(HERE), "corpus")
# AIADRA_SOLVER_DIR overrides the binary location -- the Gate-2 swap-retest
# points this at the PACKAGED/REBUILT artifacts.
BUILD = os.environ.get("AIADRA_SOLVER_DIR") or os.path.join(
    os.path.dirname(HERE), "spike-planegcs", "build", "Release")
sys.path.insert(0, CORPUS)
sys.path.insert(0, HERE)
os.add_dll_directory(BUILD)
sys.path.insert(0, BUILD)

import generate_corpus as gc                                  # noqa: E402
import aiadra_solver                                          # noqa: E402
from own_baseline import (CASE_IDS, TOL_BLOCK, load_case,     # noqa: E402
                          canonical_result_bytes, compare_expectation,
                          block_worst)

DEFAULT_CAP = 200


def snap_angle(rad):
    for target in (0.0, math.pi, -math.pi):
        if abs(rad - target) < 1e-6:
            return target
    return rad  # evidence: an unsnapped seed angle would surface in results


class Builder:
    """Translates one corpus case into a planegcs System.

    seed_cfg (optional) overrides nominal seeds -- the persisted solved
    snapshot on replay (SCHEMA P2/P4)."""

    def __init__(self, case, weak=(), seed_cfg=None):
        self.sys = aiadra_solver.System()
        self.case = case
        self.ents = {e["id"]: e for e in case["entities"]}
        self.seed_full = gc.nominal_cfg(case["entities"])
        if seed_cfg:
            self.seed_full.update({k: v for k, v in seed_cfg.items()
                                   if k in self.seed_full})
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
            # FREE params seed from the (possibly replayed) snapshot; FIXED
            # params take their AUTHORITATIVE value -- fix anchors at the
            # nominal (SCHEMA section 2), weak fix_param at the record value.
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
                isx = self.sys.add_param(sx, True); isy = self.sys.add_param(sy, True)
                iex = self.sys.add_param(ex, True); iey = self.sys.add_param(ey, True)
                sp = self.sys.add_point(isx, isy)
                ep = self.sys.add_point(iex, iey)
                # diagnostic access to endpoint params (not part of the DTO)
                self.pmap[f"{e['id']}.__sx"] = isx; self.pmap[f"{e['id']}.__sy"] = isy
                self.pmap[f"{e['id']}.__ex"] = iex; self.pmap[f"{e['id']}.__ey"] = iey
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
                # planegcs ConstraintTangent(line, curve, ccw): empirically
                # (n-arcs/m-fan fixtures) ccw=True corresponds to the center on
                # the NEGATIVE side of the directed line -- determined against
                # the corpus, which is exactly what the gate is for.
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
            # measure planegcs's own angle at the (exactly satisfying) seed,
            # snap to 0/+-pi, pin it -- branch-from-seed, convention-safe
            s.set_param(iangle, snap_angle(s.constraint_error(tag)))
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
            for pname, unit in gc.PARAMS[e["type"]]:
                v = self.sys.get_param(self.pmap[f"{e['id']}.{pname}"])
                if unit == "deg":
                    v = math.degrees(v) % 360.0
                cfg[f"{e['id']}.{pname}"] = v
        return cfg


def solve_case(case, replay=None):
    """Solve one case; with `replay`, the persisted solved snapshot seeds the
    system and the weak completion is RE-APPLIED from the record (SCHEMA P2/P4)."""
    t0 = time.perf_counter()
    seed_cfg = replay["solved"] if replay is not None else None
    ents = {e["id"]: e for e in case["entities"]}
    nominal_of = {e["id"]: e["nominal"] for e in case["entities"] if "nominal" in e}
    result = {"case_id": case["case_id"], "corpus_version": case["corpus_version"],
              "solver_contract": case["solver_contract"], "classification": None,
              "dof_strong": None, "weak_completion": [], "solved": None,
              "residual_max": None, "branch_oracle_value": None, "diagnostics": []}
    telemetry = {"update_steps": None, "notes": "planegcs DogLeg via aiadra_solver.pyd"}

    bad = [f["id"] for f in case["constraints"] + case["dimensions"]
           if not gc.domain_ok(f, ents)]
    if bad:
        result["classification"] = "rejected"
        result["diagnostics"] = [{"kind": "out-of-domain", "members": sorted(bad)}]
        telemetry["wall_ms"] = (time.perf_counter() - t0) * 1000.0
        return result, telemetry

    b = Builder(case, seed_cfg=seed_cfg)
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
            telemetry["wall_ms"] = (time.perf_counter() - t0) * 1000.0
            return result, telemetry
        result["dof_strong"] = 0
    elif dof > 0:
        result["classification"] = "under"
        result["dof_strong"] = dof
        if replay is not None:  # re-APPLY the persisted record, never re-derive
            weak = [dict(w) for w in replay["weak_completion"]]
        else:
            # the SHARED skb-0 policy, identical for both candidates
            params = gc.param_list(case["entities"])
            cfg0 = gc.nominal_cfg(case["entities"])
            facts = case["constraints"] + case["dimensions"] + case["anchors"]
            rows, _ = gc.system_rows(facts, ents, dict(cfg0), params, nominal_of)
            recs, _, comp_rank = gc.run_skb0(rows, params, cfg0)
            if comp_rank != len(params):
                result["diagnostics"] = [{"kind": "completion-stuck",
                                          "members": [case["case_id"]]}]
                telemetry["wall_ms"] = (time.perf_counter() - t0) * 1000.0
                return result, telemetry
            weak = [gc.weak_record(i + 1, e, p, v, ents) for i, (e, p, v) in enumerate(recs)]
        result["weak_completion"] = weak
        b = Builder(case, weak, seed_cfg=seed_cfg)  # rebuild with the completion applied
        b.sys.declare_unknowns()
        b.sys.init_solution()
    else:
        result["classification"] = "well"
        result["dof_strong"] = 0

    cap = case.get("iteration_cap", DEFAULT_CAP)
    b.sys.set_max_iter(cap)
    status = b.sys.solve(2, True)  # DogLeg
    telemetry["update_steps"] = f"<= {cap} (planegcs-internal)"
    if status in (0, 1):
        b.sys.apply()
    cfg = b.solved_cfg()
    worst = block_worst([r for f in (case["constraints"] + case["dimensions"]
                                     + case["anchors"] + weak)
                         if f.get("id") != case.get("deliberate_domain_violation")
                         for r in gc.fact_residuals(f, ents, cfg, nominal_of)])
    if status not in (0, 1) or any(v > TOL_BLOCK for v in worst.values()):
        result["diagnostics"] = result["diagnostics"] + [
            {"kind": "non-convergent", "members": [case["case_id"]]}]
        telemetry["wall_ms"] = (time.perf_counter() - t0) * 1000.0
        return result, telemetry

    result["solved"] = cfg
    result["residual_max"] = worst
    oracle = case["expected"].get("branch_oracle")
    if oracle and oracle["kind"] == "cross_sign":
        a, bb, p = (gc.pt(cfg, ents, x) for x in oracle["of"])
        cross = (bb[0]-a[0])*(p[1]-bb[1]) - (bb[1]-a[1])*(p[0]-bb[0])
        result["branch_oracle_value"] = 1 if cross > 0 else -1
    telemetry["wall_ms"] = (time.perf_counter() - t0) * 1000.0
    return result, telemetry


def corpus_digest():
    h = hashlib.sha256()
    for cid in CASE_IDS:
        result, _ = solve_case(load_case(cid))
        h.update(canonical_result_bytes(result))
    return h.hexdigest()


def main():
    from own_baseline import handle_dump_mode, SERIALIZER_ID
    if "--digest" in sys.argv:
        print(corpus_digest())
        return
    if handle_dump_mode(solve_case):
        return

    env = {"candidate": "planegcs (extracted + 2 determinism patches, DogLeg)",
           "upstream_commit": "8d0078866c6fcefed3395d5d9fa36c683ea858ad",
           "patches": "spike-planegcs/patches/0001+0002 (deterministic assembly; "
                      "A/B causality in provenance.json patch_evidence)",
           "artifacts": "planegcs.dll + aiadra_solver.cp312-win_amd64.pyd (separate DLL form)",
           "os": platform.platform(), "arch": platform.machine(),
           "compiler_toolchain": "MSVC 19.40.33811, Visual Studio 17 2022 v143 "
                                 "toolset 14.40.33807, x64 Release",
           "compile_flags": "/O2 /Ob2 /MD /EHsc /bigobj /permissive- /fp:precise, "
                            "C++20, CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS, Sketcher_EXPORTS",
           "python": sys.version.split()[0],
           "python_abi": "cp312-win_amd64",
           "dependencies": "Eigen 3.4.0 (MPL-2.0, header-only), Boost 1.86.0 "
                           "(BSL-1.0, header-only), pybind11 3.0.4 (BSD-3-Clause)",
           "serializer_id": SERIALIZER_ID,
           "native_convergence": 1e-10, "solver_contract": "skb-c0",
           "corpus_version": "skb-1", "weak_policy": "skb-0 (shared AIADRA layer)"}

    evidence = {"environment": env, "cases": {}, "procedures": {}}
    failures = 0
    for cid in CASE_IDS:
        case = load_case(cid)
        result, telemetry = solve_case(case)
        errs = compare_expectation(result, case)
        status = "PASS" if not errs else "FAIL"
        failures += bool(errs)
        print(f"{status:<5} {cid:<18} {result['classification']:<9} "
              f"wall={telemetry['wall_ms']:7.1f}ms")
        for e in errs:
            print(f"      !! {e}")
        evidence["cases"][cid] = {"pass": not errs, "errors": errs,
                                  "classification": result["classification"],
                                  "wall_ms": round(telemetry["wall_ms"], 2)}

    from own_baseline import procedure_p2, procedure_p4, run_repeatability
    for cid in ("c-bracket", "j-branch-flip"):
        p2 = procedure_p2(solve_case, "planegcs", cid)
        failures += not p2["pass"]
        print(f"{'PASS' if p2['pass'] else 'FAIL'} P2 persisted branch round-trip {cid}: "
              f"persisted {p2['persisted']} -> replayed {p2['resolved']}")
        evidence["procedures"][f"p2:{cid}"] = p2

    ok_p4, p4_out = procedure_p4(solve_case, "planegcs")
    print(f"{'PASS' if ok_p4 else 'FAIL'} P4 serialize->reload->replay byte-identical "
          f"({len(p4_out)} solved-bearing cases)")
    evidence["procedures"]["p4"] = {"pass": ok_p4, "cases": p4_out}
    failures += not ok_p4

    rep = run_repeatability(solve_case, os.path.abspath(__file__), sys.executable)
    rep["determinism_provenance"] = {
        "status": "CONFIRMED by A/B (was: measured hypothesis in Claude5)",
        "cause": "SubSystem::redirectParams last-writer-wins over pointer-ordered "
                 "pmap with reduction-aliased pvals slots; see spike-planegcs/"
                 "patches/ and provenance.json patch_evidence for the full A/B",
        "unpatched": "82 distinct digests/100 same-process; 10/10 distinct fresh",
        "patched": "byte-identical (this run set)"}
    print(f"{'PASS' if rep['byte_identical'] else 'FAIL'} repeatability: 100 same-process "
          f"+ 10 fresh-process byte-identical "
          f"(distinct: {len(set(rep['same_process_digests']) | set(rep['fresh_process_digests']))})")
    evidence["procedures"]["repeatability"] = rep
    failures += not rep["byte_identical"]

    with open(os.path.join(HERE, "evidence-planegcs.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(evidence, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"\n{'GATE 1 (planegcs): ALL GREEN' if not failures else str(failures) + ' FAILURE GROUP(S)'}"
          f" -- evidence-planegcs.json written")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
