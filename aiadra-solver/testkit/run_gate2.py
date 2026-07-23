# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 AIADRA
"""SK-B Gate-2 clean-machine runner (arc 20260715-3, Codex7 B1/B3).

ONE command executes the frozen sequence with FULL artifact retention:

  verify package+kit manifests (immutable inputs)
  -> locked Boost acquisition (src/fetch_boost.py)
  -> cmake configure + build (full transcript retained)
  -> hash the rebuilt pair (rebuilt-manifest)
  -> SWAP the rebuilt planegcs.dll under the ORIGINAL binding (swapped-pair
     manifest names all three binary identities explicitly)
  -> run the FULL skb-1 gate against the swapped pair (stdout + evidence
     retained; corpus digest asserted against the frozen Gate-1 constant)
  -> write gate2-run-evidence.json GENERATED FROM the retained artifacts

Everything lands under testkit/output/<hostname>-<timestamp>/ .

Usage:  python run_gate2.py [--package <package-root>]
"""
import argparse
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys

KIT = os.path.dirname(os.path.abspath(__file__))
EXPECTED_DIGEST = "061fbdec5913ee88943ac1241cc237dbd0075e121621b66be055f32befeeb736"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest(root, manifest_name):
    bad = []
    path = os.path.join(root, manifest_name)
    with open(path, encoding="utf-8") as f:
        for line in f:
            digest, rel = line.strip().split("  ", 1)
            p = os.path.join(root, rel)
            if not os.path.isfile(p) or sha256(p) != digest:
                bad.append(rel)
    return bad


def find_cmake():
    for c in (os.environ.get("AIADRA_CMAKE"),
              r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7"
              r"\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe",
              r"C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7"
              r"\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe",
              "cmake"):
        if not c:
            continue
        try:
            subprocess.run([c, "--version"], capture_output=True, check=True)
            return c
        except (OSError, subprocess.CalledProcessError):
            continue
    raise SystemExit("no cmake found (set AIADRA_CMAKE)")


def run_logged(cmd, log_path, env=None, cwd=None):
    with open(log_path, "a", encoding="utf-8", newline="\n") as log:
        log.write(f"\n$ {' '.join(cmd)}\n")
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=cwd)
        log.write(proc.stdout or "")
        log.write(proc.stderr or "")
        log.write(f"\n[exit {proc.returncode}]\n")
    return proc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", default=os.path.join(os.path.dirname(KIT), "package"))
    args = ap.parse_args()
    pkg = os.path.abspath(args.package)

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = os.path.join(KIT, "output", f"{platform.node()}-{stamp}")
    logs = os.path.join(out, "logs")
    os.makedirs(logs)

    machine = {"hostname": platform.node(), "os": platform.platform(),
               "arch": platform.machine(), "python": sys.version,
               "cpu": platform.processor()}

    # 1. immutable inputs
    pkg_bad = verify_manifest(pkg, "package-manifest.txt")
    kit_bad = verify_manifest(KIT, "testkit-manifest.txt")
    if pkg_bad or kit_bad:
        raise SystemExit(f"manifest verification FAILED: pkg={pkg_bad} kit={kit_bad}")
    print("inputs verified: package + testkit manifests match")

    # 2. locked third-party acquisition
    r = run_logged([sys.executable, os.path.join(pkg, "src", "fetch_boost.py")],
                   os.path.join(logs, "acquire.log"))
    if r.returncode != 0:
        raise SystemExit("boost acquisition failed (see logs/acquire.log)")
    print("boost acquired + verified")

    # 3. rebuild (full transcript)
    cmake = find_cmake()
    build = os.path.join(out, "build")
    pyb = os.path.join(pkg, "src", "pybind11", "share", "cmake", "pybind11")
    blog = os.path.join(logs, "build.log")
    r = run_logged([cmake, "-S", os.path.join(pkg, "src", "binding"), "-B", build,
                    "-G", "Visual Studio 17 2022", "-A", "x64",
                    f"-Dpybind11_DIR={pyb}"], blog)
    if r.returncode != 0:
        raise SystemExit("cmake configure failed (see logs/build.log)")
    r = run_logged([cmake, "--build", build, "--config", "Release"], blog)
    if r.returncode != 0:
        raise SystemExit("build failed (see logs/build.log)")
    rel = os.path.join(build, "Release")
    pyd_name = next(f for f in os.listdir(rel) if f.endswith(".pyd"))
    rebuilt = {"planegcs.dll": sha256(os.path.join(rel, "planegcs.dll")),
               pyd_name: sha256(os.path.join(rel, pyd_name))}
    with open(os.path.join(out, "rebuilt-manifest.txt"), "w", encoding="utf-8",
              newline="\n") as f:
        for k, v in sorted(rebuilt.items()):
            f.write(f"{v}  build/Release/{k}\n")
    print(f"rebuilt: planegcs.dll {rebuilt['planegcs.dll'][:16]}...")

    # 4. swap: rebuilt DLL under the ORIGINAL binding, originals untouched
    run_dist = os.path.join(out, "run-dist")
    shutil.copytree(os.path.join(pkg, "dist"), run_dist,
                    ignore=shutil.ignore_patterns("licenses"))
    orig_dll = sha256(os.path.join(run_dist, "planegcs.dll"))
    shutil.copy2(os.path.join(rel, "planegcs.dll"),
                 os.path.join(run_dist, "planegcs.dll"))
    orig_pyd = next(f for f in os.listdir(run_dist) if f.endswith(".pyd"))
    swapped = {"original_distributed_dll": orig_dll,
               "rebuilt_replacement_dll": rebuilt["planegcs.dll"],
               "original_untouched_binding": sha256(os.path.join(run_dist, orig_pyd)),
               "note": "the retest pair = rebuilt DLL + ORIGINAL distributed binding"}
    with open(os.path.join(out, "swapped-pair-manifest.json"), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(swapped, f, indent=2)

    # 5. the FULL gate against the swapped pair (stdout retained)
    env = dict(os.environ, AIADRA_SOLVER_DIR=run_dist)
    harness = os.path.join(KIT, "harness", "planegcs_candidate.py")
    glog = os.path.join(logs, "gate-run.log")
    r = run_logged([sys.executable, harness], glog, env=env)
    gate_pass = r.returncode == 0
    d = subprocess.run([sys.executable, harness, "--digest"], capture_output=True,
                       text=True, env=env)
    digest = d.stdout.strip()
    for ev in ("evidence-planegcs.json",):
        src_ev = os.path.join(KIT, "harness", ev)
        if os.path.isfile(src_ev):
            shutil.copy2(src_ev, out)

    # 6. evidence GENERATED from the retained artifacts
    evidence = {"machine": machine,
                "inputs": {"package_root": pkg,
                           "package_manifest_sha256": sha256(os.path.join(pkg, "package-manifest.txt")),
                           "testkit_manifest_sha256": sha256(os.path.join(KIT, "testkit-manifest.txt"))},
                "rebuilt_manifest": open(os.path.join(out, "rebuilt-manifest.txt"),
                                         encoding="utf-8").read().splitlines(),
                "swapped_pair": swapped,
                "gate_run": {"full_gate_pass": gate_pass,
                             "stdout_log": "logs/gate-run.log",
                             "harness_evidence": "evidence-planegcs.json",
                             "corpus_digest": digest,
                             "expected_digest": EXPECTED_DIGEST,
                             "digest_match": digest == EXPECTED_DIGEST},
                "retained": ["logs/acquire.log", "logs/build.log", "logs/gate-run.log",
                             "rebuilt-manifest.txt", "swapped-pair-manifest.json",
                             "run-dist/ (the exercised swapped pair)",
                             "build/Release/ (the rebuilt artifacts, kept)"]}
    with open(os.path.join(out, "gate2-run-evidence.json"), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(evidence, f, indent=2)

    ok = gate_pass and digest == EXPECTED_DIGEST
    print(f"gate run: {'PASS' if gate_pass else 'FAIL'}; digest "
          f"{'MATCH' if digest == EXPECTED_DIGEST else 'MISMATCH: ' + digest}")
    print(f"retained evidence: {out}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
