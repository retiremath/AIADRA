# NOTICE -- AIADRA sketch-solver package (SK-B spike)

## planegcs.dll  (LGPL-2.1-or-later)

Contains the PlaneGCS geometric constraint solver, extracted from FreeCAD
(https://github.com/FreeCAD/FreeCAD, commit 8d0078866c6fcefed3395d5d9fa36c683ea858ad,
subtree src/Mod/Sketcher/App/planegcs) and modified by two AIADRA determinism
patches (src/patches/). Complete corresponding source ships in src/ of this
package; src/BUILD.md is the exact, self-contained rebuild+swap procedure.
planegcs.dll is a SEPARATE, REPLACEABLE library: rebuild it from src/ and swap
the file. AIADRA-authored completion shims (src/shims/) are LGPL-2.1-or-later.

Compiled-in header-only third parties: Eigen 3.4.0 (MPL-2.0, VENDORED in
src/eigen), Boost 1.86.0 graph+math (BSL-1.0, locked acquisition via
src/fetch_boost.py).

## aiadra_solver.cp312-win_amd64.pyd  (AIADRA, AGPL-3.0-only)

The thin AIADRA-owned binding. Dynamically links planegcs.dll (LGPL library
boundary), python312.dll, and the Microsoft Visual C++ runtime. Built with
pybind11 3.0.4 (BSD-3-Clause, VENDORED in src/pybind11).

## License texts (licenses/)

LGPL-2.1.txt (planegcs) - AGPL-3.0.txt (binding) - MPL-2.0.txt (Eigen) -
BSL-1.0.txt (Boost) - BSD-3-Clause-pybind11.txt (pybind11)

## Runtime dependencies of the shipped pair (dumpbin /dependents)

planegcs.dll -> MSVCP140.dll, VCRUNTIME140.dll, VCRUNTIME140_1.dll,
                api-ms-win-crt-* (UCRT), KERNEL32.dll
aiadra_solver.pyd -> planegcs.dll, python312.dll, MSVCP140.dll,
                VCRUNTIME140.dll, VCRUNTIME140_1.dll, api-ms-win-crt-* (UCRT),
                KERNEL32.dll

Toolchain: MSVC 19.40.33811 (VS 2022 v143, tools 14.40.33807), x64 Release,
/O2 /Ob2 /MD /EHsc /bigobj /permissive- /fp:precise, C++20.
