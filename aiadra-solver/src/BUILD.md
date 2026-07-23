# Rebuild + swap + retest procedure (self-contained)

Start from THIS package's root directory (the one containing dist/ and src/).
Everything needed is inside the package or acquired by the locked script below.

> Adoption note (arc 20260717-2 Gate F1): this tree is the accepted SK-B
> package adopted at `aiadra-solver/` plus ONE addition — the DLL-side
> compatibility handshake (`src/handshake/aiadra_handshake.cpp`, compiled
> into planegcs.dll; see spdx-audit.md addendum). A conforming replacement
> DLL must implement the `aiadra_planegcs_handshake` export truthfully.
> The dist/ binaries are NOT in git (binary distribution is legal-gated,
> ADR/0034 + ADR/0044-A1) — a fresh clone runs this procedure to produce
> them; digests of the local dev build live in dist/dev-build-digests.txt.

## Requirements (bootstrap on a clean machine)

- Visual Studio 2022 with the "Desktop development with C++" workload
  (v143 tools; evidenced build used MSVC 19.40.33811 / tools 14.40.33807)
- CMake >= 3.20 (the VS-bundled CMake is sufficient)
- Python 3.12.x for x64 Windows (the binding targets ABI cp312-win_amd64)
- No pip installs are required: pybind11 3.0.4 is VENDORED at src/pybind11

## 1. Acquire Boost (locked)

    python src/fetch_boost.py

Downloads https://archives.boost.io/release/1.86.0/source/boost_1_86_0.tar.gz
verifies archive sha256 2575e74ffc3ef1cd0babac2c1ee8bdb5782a0ee672b1912da40e5b4b591ca01f,
extracts archive member boost_1_86_0/boost to src/boost, and verifies the
BSL-1.0 license text. Eigen and pybind11 are already vendored (exact bytes,
manifested).

## 2. Rebuild

    cmake -S src/binding -B build -G "Visual Studio 17 2022" -A x64 ^
          -Dpybind11_DIR=%CD%\src\pybind11\share\cmake\pybind11
    cmake --build build --config Release

Products: build/Release/planegcs.dll and build/Release/aiadra_solver.*.pyd.

## 3. Swap

Copy build/Release/planegcs.dll over dist/planegcs.dll (or into a copy of
dist/). The ORIGINAL dist/aiadra_solver.*.pyd stays untouched -- that is the
LGPL replaceability point.

## 4. Retest against the frozen gate

The immutable test kit (harness + skb-1 corpus, digests in its own manifest)
is distributed alongside this package as testkit/. Run:

    python testkit/run_gate2.py --package <this package root>

The full 14-case gate must pass and the corpus digest must equal
061fbdec5913ee88943ac1241cc237dbd0075e121621b66be055f32befeeb736
(the accepted Gate-1 digest of the patched candidate). The runner retains the
build transcript, rebuilt-artifact hashes, swapped-pair manifest, and the
complete harness output under testkit-output/<machine>/.
