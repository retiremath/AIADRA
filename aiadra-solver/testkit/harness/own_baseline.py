"""SK-B Gate 1 -- the OWN-BASELINE candidate harness (arc 20260715-3).

A pure-Python Levenberg-Marquardt candidate run against the accepted skb-1
executable gate. Consumes the emitted case FILES (never the generator's
in-memory cases); shares the canonical residual/rank definitions of
corpus/generate_corpus.py exactly as SCHEMA section 2b requires of every
harness. No third-party dependencies; fully deterministic.

Pipeline per case: domain validation -> rank classification (numeric Jacobian)
-> dependency scan in canonical fact order (redundant vs conflicting)
-> skb-0 completion for underconstrained systems -> LM solve under the
update-step budget -> DTO emission per SCHEMA section 5.

Comparator implements the TWO comparisons of SCHEMA section 5 (Codex4 note 2):
expectation comparison (exact discrete fields + tolerances) and repeatability
comparison (byte-identity of canonical result bytes).

Modes:
  python own_baseline.py            full run: compare vs expectations, run
                                    P2 (branch round-trip) + P4 (reload),
                                    100x in-process repeatability, write
                                    evidence-own-baseline.json
  python own_baseline.py --digest   single silent run, print corpus digest
                                    (for the 10 fresh-process repeats)
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
sys.path.insert(0, CORPUS)
import generate_corpus as gc  # canonical residuals/rank/policy -- the shared contract

TOL_BLOCK = 1e-10   # solver contract skb-c0 convergence, per residual block
TOL_SCALAR = 1e-9   # expectation comparison, per solved scalar
DEFAULT_CAP = 200   # update steps, solver contract skb-c0

CASE_IDS = ["a-rect", "b-slot", "c-bracket", "d-under", "e-over-redundant",
            "f-conflicting", "g-nonconv", "h-outdomain", "i-permute",
            "j-branch-flip", "k-gear", "l-tee", "m-fan", "n-arcs"]

# canonical result serialization contract (SCHEMA section 5)
SERIALIZER_ID = ("skb-canon-1: json keys sorted, compact separators, shortest "
                 "round-trip float repr, no quantization, -0.0 canonicalized, "
                 "NaN/Infinity rejected")


def load_case(case_id):
    with open(os.path.join(CORPUS, f"{case_id}.json"), encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------ LM solver

def lin_solve(A, b):
    n = len(A)
    m = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda i: abs(m[i][c]))
        if abs(m[piv][c]) < 1e-300:
            return None
        m[c], m[piv] = m[piv], m[c]
        for i in range(n):
            if i != c and m[i][c] != 0.0:
                f = m[i][c] / m[c][c]
                m[i] = [a - f * bb for a, bb in zip(m[i], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def block_worst(pairs):
    worst = {"length_mm": 0.0, "direction": 0.0, "angle_deg": 0.0}
    for block, v in pairs:
        worst[block] = max(worst[block], abs(v))
    return worst


def lm_solve(facts, ents, params, cfg_seed, nominal_of, budget):
    """Returns (cfg, update_steps, converged, block_residuals).

    An UPDATE STEP is one ACCEPTED update of the full unknown vector followed
    by residual re-evaluation (SCHEMA section 5); rejected damping trials do
    not count. budget=0 means evaluate-only at the seed.
    """
    cfg = dict(cfg_seed)

    def resid(c):
        out = []
        for f in facts:
            out.extend(gc.fact_residuals(f, ents, c, nominal_of))
        return out

    pairs = resid(cfg)
    steps, lam = 0, 1e-3
    while True:
        worst = block_worst(pairs)
        if all(v <= TOL_BLOCK for v in worst.values()):
            return cfg, steps, True, worst
        if steps >= budget:
            return cfg, steps, False, worst
        J = []
        for f in facts:
            rows, _ = gc.system_rows([f], ents, cfg, params, nominal_of)
            J.extend(rows)
        R = [v for _, v in pairs]
        n = len(params)
        A = [[sum(J[k][i] * J[k][j] for k in range(len(J))) for j in range(n)]
             for i in range(n)]
        g = [sum(J[k][i] * R[k] for k in range(len(J))) for i in range(n)]
        sq = sum(v * v for v in R)
        improved = False
        for _trial in range(60):
            M = [[A[i][j] + (lam * A[i][i] + 1e-12 if i == j else 0.0)
                  for j in range(n)] for i in range(n)]
            delta = lin_solve(M, [-x for x in g])
            if delta is not None:
                trial = dict(cfg)
                for j, key in enumerate(params):
                    trial[key] = cfg[key] + delta[j]
                tp = resid(trial)
                if sum(v * v for _, v in tp) < sq - 1e-30:
                    cfg, pairs = trial, tp
                    steps += 1
                    lam = max(lam / 3.0, 1e-15)
                    improved = True
                    break
            lam *= 10.0
            if lam > 1e14:
                break
        if not improved:  # least-squares floor (inconsistent system) or stall
            return cfg, steps, False, block_worst(pairs)


# ------------------------------------------------------------------ candidate

def solve_case(case, replay=None):
    """Solve one case; with `replay`, consume a PERSISTED record (SCHEMA P2/P4):
    the solver seed comes from the persisted solved snapshot and the weak
    completion is RE-APPLIED from the record, never re-derived."""
    t0 = time.perf_counter()
    ents = {e["id"]: e for e in case["entities"]}
    nominal_of = {e["id"]: e["nominal"] for e in case["entities"] if "nominal" in e}
    result = {"case_id": case["case_id"], "corpus_version": case["corpus_version"],
              "solver_contract": case["solver_contract"], "classification": None,
              "dof_strong": None, "weak_completion": [], "solved": None,
              "residual_max": None, "branch_oracle_value": None, "diagnostics": []}
    telemetry = {"wall_ms": None, "update_steps": 0, "notes": "own-baseline pure-python LM"}

    # 1. domain validation (before any numerics)
    bad = [f["id"] for f in case["constraints"] + case["dimensions"]
           if not gc.domain_ok(f, ents)]
    if bad:
        result["classification"] = "rejected"
        result["diagnostics"] = [{"kind": "out-of-domain", "members": sorted(bad)}]
        telemetry["wall_ms"] = (time.perf_counter() - t0) * 1000.0
        return result, telemetry

    facts = case["constraints"] + case["dimensions"] + case["anchors"]
    params = gc.param_list(case["entities"])
    cfg0 = gc.nominal_cfg(case["entities"])
    if replay is not None:  # the persisted solved snapshot is the seed authority
        cfg0.update({k: v for k, v in replay["solved"].items() if k in cfg0})
    budget = case.get("iteration_cap", DEFAULT_CAP)

    # 2. rank classification + dependency scan in canonical fact order
    acc, acc_rank, flagged = [], 0, []
    fact_rows = {}
    for fact in facts:
        rows, _ = gc.system_rows([fact], ents, cfg0, params, nominal_of)
        fact_rows[fact["id"]] = rows
        new_rank = gc.mat_rank(acc + rows)
        if new_rank == acc_rank:
            flagged.append(fact)
        acc, acc_rank = acc + rows, new_rank
    dof = len(params) - acc_rank

    weak = []
    if flagged:
        result["classification"] = "over"
    elif dof > 0:
        result["classification"] = "under"
        result["dof_strong"] = dof
        if replay is not None:  # re-APPLY the persisted record, never re-derive
            weak = [dict(w) for w in replay["weak_completion"]]
        else:
            strong_rows = [r for rs in fact_rows.values() for r in rs]
            recs, _, comp_rank = gc.run_skb0(strong_rows, params, cfg0)
            if comp_rank != len(params):
                result["diagnostics"] = [{"kind": "completion-stuck",
                                          "members": [case["case_id"]]}]
                telemetry["wall_ms"] = (time.perf_counter() - t0) * 1000.0
                return result, telemetry
            weak = [gc.weak_record(i + 1, e, p, v, ents) for i, (e, p, v) in enumerate(recs)]
        result["weak_completion"] = weak
    else:
        result["classification"] = "well"
        result["dof_strong"] = 0

    # 3. solve under the update-step budget
    cfg, steps, converged, worst = lm_solve(facts + weak, ents, params, cfg0,
                                            nominal_of, budget)
    telemetry["update_steps"] = steps

    if result["classification"] == "over":
        # redundant vs conflicting: judge each flagged fact at the LS solution
        diags = []
        for fact in flagged:
            res = [v for _, v in gc.fact_residuals(fact, ents, cfg, nominal_of)]
            if all(abs(v) <= 1e-8 for v in res):
                diags.append({"kind": "redundant", "members": [fact["id"]]})
            else:
                partner = None
                for other in facts:
                    if other["id"] == fact["id"]:
                        break
                    r1, r2 = fact_rows[other["id"]], fact_rows[fact["id"]]
                    if len(r1) == 1 and len(r2) == 1 and gc.rows_parallel(r1[0], r2[0]):
                        partner = other["id"]
                        break
                members = sorted([m for m in (partner, fact["id"]) if m])
                diags.append({"kind": "conflicting", "members": members})
        result["diagnostics"] = diags
        if any(d["kind"] == "conflicting" for d in diags):
            telemetry["wall_ms"] = (time.perf_counter() - t0) * 1000.0
            return result, telemetry  # solved fields stay null (applicability)
        result["dof_strong"] = 0  # redundant-consistent still solves

    if not converged:
        result["diagnostics"] = result["diagnostics"] + [
            {"kind": "non-convergent", "members": [case["case_id"]]}]
        result["solved"] = None
        result["residual_max"] = None
        telemetry["wall_ms"] = (time.perf_counter() - t0) * 1000.0
        return result, telemetry

    result["solved"] = {k: cfg[k] for k in params}
    result["residual_max"] = worst
    oracle = case["expected"].get("branch_oracle")
    if oracle and oracle["kind"] == "cross_sign":
        a, b, p = (gc.pt(cfg, ents, x) for x in oracle["of"])
        cross = (b[0]-a[0])*(p[1]-b[1]) - (b[1]-a[1])*(p[0]-b[0])
        result["branch_oracle_value"] = 1 if cross > 0 else -1
    telemetry["wall_ms"] = (time.perf_counter() - t0) * 1000.0
    return result, telemetry


# ------------------------------------------------------------------ comparator

def canonical_result_bytes(result):
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


def compare_expectation(result, case):
    """Comparison lane 1: candidate result vs corpus expectation."""
    exp = case["expected"]
    errs = []
    if result["classification"] != exp["classification"]:
        errs.append(f"classification {result['classification']} != {exp['classification']}")
    if exp["dof_strong"] is not None and result["dof_strong"] != exp["dof_strong"]:
        errs.append(f"dof_strong {result['dof_strong']} != {exp['dof_strong']}")
    if result["diagnostics"] != exp["diagnostics"]:
        errs.append(f"diagnostics {result['diagnostics']} != {exp['diagnostics']}")
    if result["weak_completion"] != exp["weak_completion"]:
        errs.append("weak_completion mismatch")
    oracle = exp.get("branch_oracle")
    want_oracle = oracle["expected"] if oracle else None
    if result["branch_oracle_value"] != want_oracle:
        errs.append(f"branch_oracle_value {result['branch_oracle_value']} != {want_oracle}")
    if (exp["solved"] is None) != (result["solved"] is None):
        errs.append(f"solved presence mismatch (expected {exp['solved'] is not None})")
    elif exp["solved"] is not None:
        missing = set(exp["solved"]) ^ set(result["solved"])
        if missing:
            errs.append(f"solved key mismatch: {sorted(missing)}")
        else:
            for k, v in exp["solved"].items():
                if abs(result["solved"][k] - v) > TOL_SCALAR:
                    errs.append(f"solved {k}: {result['solved'][k]} vs {v}")
        for block, v in result["residual_max"].items():
            if v > TOL_BLOCK:
                errs.append(f"residual block {block} = {v:.3e} > {TOL_BLOCK}")
    return errs


# ---------------------------------------------- persistence (candidate-neutral)
# The production-shaped replay boundary (SCHEMA P2/P4, Codex5 B1): a persisted
# record is SERIALIZED TO DISK and replay consumes the RELOADED BYTES only.

REPLAY_DIR = os.path.join(HERE, "replay")
REPLAY_SCHEMA = "skb-replay-1"


def make_persisted_record(result):
    return {"schema": REPLAY_SCHEMA, "case_id": result["case_id"],
            "branch_oracle_value": result["branch_oracle_value"],
            "weak_completion": result["weak_completion"],
            "solved": result["solved"]}


def save_persisted(record, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(data)
    return hashlib.sha256(data.encode()).hexdigest()


def load_persisted(path):
    with open(path, encoding="utf-8") as f:
        data = f.read()
    record = json.loads(data)
    if record.get("schema") != REPLAY_SCHEMA:
        raise ValueError(f"unknown replay schema in {path}")
    return record, hashlib.sha256(data.encode()).hexdigest()


def perturbed_case(case_id):
    case = load_case(case_id)
    pb = case["perturb"]
    rng = random.Random(pb["seed"])
    for e in case["entities"]:
        if e["type"] == "point":
            e["nominal"]["x"] += rng.uniform(-pb["envelope_mm"], pb["envelope_mm"])
            e["nominal"]["y"] += rng.uniform(-pb["envelope_mm"], pb["envelope_mm"])
    return case


def procedure_p2(solve_fn, candidate, case_id):
    """P2 literal sequence: solve -> persist {oracle, weak, solved snapshot} to
    DISK -> perturb nominal geometry -> RELOAD the persisted bytes -> re-solve
    consuming the reloaded record -> same oracle."""
    r1, _ = solve_fn(load_case(case_id))
    path = os.path.join(REPLAY_DIR, f"{candidate}-p2-{case_id}.json")
    digest = save_persisted(make_persisted_record(r1), path)
    loaded, load_digest = load_persisted(path)
    r2, _ = solve_fn(perturbed_case(case_id), replay=loaded)
    same = (r2["branch_oracle_value"] == loaded["branch_oracle_value"]
            and digest == load_digest)
    return {"pass": same, "persisted": loaded["branch_oracle_value"],
            "resolved": r2["branch_oracle_value"], "record_file": path,
            "record_sha256": digest}


def procedure_p4(solve_fn, candidate):
    """P4 literal sequence per solved-bearing case: solve -> serialize to disk
    -> reload -> re-solve FROM the reloaded record -> byte-identical result."""
    outcomes = {}
    for cid in CASE_IDS:
        r1, _ = solve_fn(load_case(cid))
        if r1["solved"] is None:
            continue
        path = os.path.join(REPLAY_DIR, f"{candidate}-p4-{cid}.json")
        digest = save_persisted(make_persisted_record(r1), path)
        loaded, _ = load_persisted(path)
        r2, _ = solve_fn(load_case(cid), replay=loaded)
        outcomes[cid] = {"pass": canonical_result_bytes(r2) == canonical_result_bytes(r1),
                         "record_sha256": digest}
    return all(v["pass"] for v in outcomes.values()), outcomes


def envelope_ok(spread):
    """The declared variance envelope, per scalar: max(1e-15 abs, 1e-12 rel)."""
    worst = 0.0
    for (lo, hi) in spread.values():
        allowed = max(1e-15, 1e-12 * max(abs(lo), abs(hi)))
        worst = max(worst, (hi - lo) / allowed if allowed else 0.0)
    return worst <= 1.0, worst


def corpus_scalars(solve_fn):
    """One full corpus run: (digest, {case:scalar -> value}) -- the fresh-worker
    payload so the variance envelope aggregates ALL 110 runs (Codex6 N1)."""
    h = hashlib.sha256()
    scalars = {}
    for cid in CASE_IDS:
        result, _ = solve_fn(load_case(cid))
        h.update(canonical_result_bytes(result))
        if result["solved"]:
            for k, v in result["solved"].items():
                scalars[f"{cid}:{k}"] = v
    return h.hexdigest(), scalars


def run_repeatability(solve_fn, harness_file, python_exe):
    """100 same-process + 10 fresh-process runs; returns the full evidence dict
    (every digest recorded; per-scalar extrema aggregated across ALL 110 runs
    including the fresh workers' dumped scalar payloads -- Codex6 N1)."""
    import subprocess
    import tempfile
    digests, spread = [], {}

    def merge(scalars):
        for key, v in scalars.items():
            lo, hi = spread.get(key, (v, v))
            spread[key] = (min(lo, v), max(hi, v))

    for _ in range(100):
        digest, scalars = corpus_scalars(solve_fn)
        digests.append(digest)
        merge(scalars)
    fresh = []
    for _ in range(10):
        fd, dump = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        subprocess.run([python_exe, harness_file, "--dump", dump],
                       capture_output=True, text=True, check=True)
        with open(dump, encoding="utf-8") as f:
            data = json.load(f)
        os.remove(dump)
        fresh.append(data["digest"])
        merge(data["scalars"])
    env_ok, env_worst = envelope_ok(spread)
    drift = sorted(((hi - lo, k) for k, (lo, hi) in spread.items()), reverse=True)[:5]
    return {"same_process_digests": digests, "fresh_process_digests": fresh,
            "byte_identical": len(set(digests) | set(fresh)) == 1,
            "max_abs_drift": drift[0][0] if drift else 0.0,
            "top_drift_scalars": [{"scalar": k, "abs_drift": d} for d, k in drift if d > 0],
            "variance_envelope": "per-scalar max(1e-15 abs, 1e-12 rel), "
                                 "aggregated across all 110 runs incl. fresh workers",
            "envelope_pass": env_ok, "envelope_worst_ratio": env_worst,
            "serializer_id": SERIALIZER_ID,
            "command": f"{os.path.basename(harness_file)} --dump (x10 fresh) + 100 in-process"}


def handle_dump_mode(solve_fn):
    """Shared --dump handling for fresh workers; returns True if handled."""
    if "--dump" in sys.argv:
        path = sys.argv[sys.argv.index("--dump") + 1]
        digest, scalars = corpus_scalars(solve_fn)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"digest": digest, "scalars": scalars}, f)
        return True
    return False


def corpus_digest():
    h = hashlib.sha256()
    for cid in CASE_IDS:
        result, _ = solve_case(load_case(cid))
        h.update(canonical_result_bytes(result))
    return h.hexdigest()


def main():
    if "--digest" in sys.argv:
        print(corpus_digest())
        return
    if handle_dump_mode(solve_case):
        return

    env = {"candidate": "own-baseline (pure-python LM)",
           "os": platform.platform(), "arch": platform.machine(),
           "python": sys.version.split()[0],
           "implementation": platform.python_implementation(),
           "compiler_toolchain": "none (pure python)",
           "fp_flags": "IEEE-754 double via CPython",
           "dependencies": "stdlib only",
           "serializer_id": SERIALIZER_ID,
           "solver_contract": "skb-c0", "corpus_version": "skb-1",
           "weak_policy": "skb-0"}

    evidence = {"environment": env, "cases": {}, "procedures": {}}
    failures = 0
    for cid in CASE_IDS:
        case = load_case(cid)
        result, telemetry = solve_case(case)
        errs = compare_expectation(result, case)
        status = "PASS" if not errs else "FAIL"
        failures += bool(errs)
        print(f"{status:<5} {cid:<18} {result['classification']:<9} "
              f"steps={telemetry['update_steps']:>3} wall={telemetry['wall_ms']:7.1f}ms")
        for e in errs:
            print(f"      !! {e}")
        evidence["cases"][cid] = {"pass": not errs, "errors": errs,
                                  "classification": result["classification"],
                                  "update_steps": telemetry["update_steps"],
                                  "wall_ms": round(telemetry["wall_ms"], 2)}

    for cid in ("c-bracket", "j-branch-flip"):
        p2 = procedure_p2(solve_case, "own", cid)
        failures += not p2["pass"]
        print(f"{'PASS' if p2['pass'] else 'FAIL'} P2 persisted branch round-trip {cid}: "
              f"persisted {p2['persisted']} -> replayed {p2['resolved']}")
        evidence["procedures"][f"p2:{cid}"] = p2

    ok_p4, p4_out = procedure_p4(solve_case, "own")
    print(f"{'PASS' if ok_p4 else 'FAIL'} P4 serialize->reload->replay byte-identical "
          f"({len(p4_out)} solved-bearing cases)")
    evidence["procedures"]["p4"] = {"pass": ok_p4, "cases": p4_out}
    failures += not ok_p4

    rep = run_repeatability(solve_case, os.path.abspath(__file__), sys.executable)
    print(f"{'PASS' if rep['byte_identical'] else 'FAIL'} repeatability: 100 same-process "
          f"+ 10 fresh-process byte-identical "
          f"(distinct: {len(set(rep['same_process_digests']) | set(rep['fresh_process_digests']))})")
    evidence["procedures"]["repeatability"] = rep
    failures += not rep["byte_identical"]

    with open(os.path.join(HERE, "evidence-own-baseline.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(evidence, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"\n{'GATE 1 (own-baseline): ALL GREEN' if not failures else str(failures) + ' FAILURE GROUP(S)'}"
          f" -- evidence-own-baseline.json written")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
