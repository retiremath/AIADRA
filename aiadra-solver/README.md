# aiadra-solver — the replaceable native sketch-solver artifact

This directory is the production home of the SK-B-selected planar
geometric-constraint solver: the pinned FreeCAD **PlaneGCS** extraction
(LGPL-2.1-or-later) plus AIADRA's thin binding, packaged so the LGPL
artifact stays **separately replaceable** (ADR/0044 Amendment A1;
ADR/0034).

## The boundary is the ARTIFACT, not the directory

The directory is only the organizational expression of an artifact-level
seam (arc 20260717-2, Codex16 B1). What establishes the seam is the whole
set: the loadable `planegcs.dll`, its corresponding source
(`src/extraction` + the two determinism patches in `src/patches`), the
notices and license texts, the locked rebuild material, and the replacement
procedure (`src/BUILD.md` + `testkit/run_gate2.py`). AIADRA's engine never
compiles any of this — `aiadra-mechanical` **loads** the replaceable binary
behind its own typed API (`aiadra_mechanical.solver`) and verifies, at
runtime, the DLL's own contract declaration (the
`aiadra_planegcs_handshake` export). Binary digests are provenance
evidence; the handshake is the compatibility authority — a legitimately
rebuilt LGPL replacement has different bytes while implementing the same
declared ABI and solver contract (`skb-c0`).

## What is (and is not) in git

| in git | not in git |
|---|---|
| extraction sources + determinism patches | `dist/*.dll`, `dist/*.pyd` (binary distribution is legal-gated: ADR/0034 artifact-compliance inventory + ADR/0044-A1 attorney review) |
| AIADRA binding + CMake + shims + handshake | `src/boost/` (acquired by the locked `src/fetch_boost.py`) |
| vendored `src/eigen` (MPL-2.0) + `src/pybind11` (BSD-3-Clause), exact manifested bytes | `build/`, `testkit/output/`, `testkit-output/` |
| licenses, NOTICE, SPDX audit, provenance + binary digests, package manifests | |
| the frozen Gate-2 testkit (corpus + harness + runner) | |

A fresh clone rebuilds the pair per [src/BUILD.md](src/BUILD.md) (VS 2022 +
CMake + Python 3.12; Boost via the locked fetcher). The frozen
clean-machine kit (`testkit/run_gate2.py`) remains the release-gated
replacement-retest authority; the living pytest regression floor lives in
`aiadra-mechanical/tests/test_solver_corpus.py` and must reproduce the
accepted corpus digest
`061fbdec5913ee88943ac1241cc237dbd0075e121621b66be055f32befeeb736`.

## Manifests

- `package-manifest-accepted-gate2.txt` — the ACCEPTED SK-B package
  manifest, frozen provenance (arc 20260715-3 Gate 2).
- `package-manifest.txt` — the adopted tree, SOURCE form (accepted package
  + the handshake delta; see the spdx-audit.md addendum). The gitignored
  binaries and `dist/dev-build-digests.txt` are per-build evidence and are
  deliberately not manifested — `testkit/run_gate2.py` hashes the rebuilt
  and swapped pair itself in its retained run manifests.
- `dist/dev-build-digests.txt` — sha256 of the local dev build.
