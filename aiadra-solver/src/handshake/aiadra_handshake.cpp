// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 AIADRA
//
// The DLL-side compatibility handshake (arc 20260717-2 Codex16 B2).
//
// planegcs.dll is the separately-replaceable LGPL artifact: a legitimately
// rebuilt replacement has different PE bytes while implementing the same
// declared ABI and solver contract. Binary digests are therefore provenance
// evidence only -- runtime compatibility must be DECLARED BY THE DLL ITSELF.
// This export is that declaration. The AIADRA binding (aiadra_solver.pyd)
// resolves it by name at runtime and fails closed when it is absent or names
// a different ABI/contract; the Python loader treats that refusal as typed.
//
// This file is deliberately licensed LGPL-2.1-or-later so the DLL remains a
// uniformly-LGPL artifact (same compliance story the SK-B audit accepted).
// A replacement build MUST implement this export with truthful values; the
// string below is part of the declared ABI, not decoration.
//
//   aiadra-planegcs-abi:1      -- the C ABI of this DLL's export surface
//                                 (the GCS:: classes consumed by the binding
//                                 via CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS plus
//                                 this handshake). Bump on any breaking
//                                 change to that surface.
//   solver-contract:skb-c0     -- the numeric solver contract this build
//                                 executes: DogLeg default, native
//                                 convergence 1e-10, the two determinism
//                                 patches (0001 deterministic subsystem
//                                 assembly, 0002 deterministic heuristic
//                                 traversal) APPLIED. A build without the
//                                 patches does not satisfy skb-c0 and must
//                                 not claim it.

extern "C" __declspec(dllexport) const char* aiadra_planegcs_handshake(void)
{
    return "aiadra-planegcs-abi:1;solver-contract:skb-c0";
}
