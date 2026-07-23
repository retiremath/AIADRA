"""The AIADRA-owned typed sketch-solver API (SK-C1 foundation, Gate F1).

Arc 20260717-2 Claude16 D3 as corrected by Codex16 B2. PlaneGCS is a
REPLACEABLE numerical library behind this vocabulary: no PlaneGCS or FreeCAD
type, name, or convention leaks through the surface below. AIADRA owns the
DTO, the classification, the skb-0 weak-completion policy, the canonical
residual definitions, and the persisted recipe vocabulary; the native
artifact pair (``planegcs.dll`` + ``aiadra_solver`` binding) only solves the
system it is handed.

Public surface:

- :func:`load_solver` / typed refusals — the fail-closed artifact loader
  (explicit ``aiadra-solver/dist`` resolution, binding-ABI + solver-contract
  verification, and the DLL-side handshake demanded by Codex16 B2);
- :func:`solve` — one skb-1-shaped system in, one :class:`SolveResult` out
  (the signed two-axis contract: classification/DoF separated from solve
  diagnostics);
- the ``skb-c0`` contract constants in :mod:`.contract` — normative,
  immutable, never copied per-record into Product Truth.

No Truth writes happen here: solved coordinates are DERIVED output, and the
v2 sketch adapter (Gate F2, ADR/0044 Amendment A2) is the only place recipe
persistence will be defined.
"""
from __future__ import annotations

from .contract import (
    DEFAULT_ITERATION_CAP,
    NATIVE_CONVERGENCE,
    SOLVER_ABI,
    SOLVER_CONTRACT,
    TOL_BLOCK,
    TOL_SCALAR,
    WEAK_POLICY,
)
from .engine import solve
from .loader import (
    SolverABIMismatchError,
    SolverArtifactMissingError,
    SolverContractMismatchError,
    SolverOriginMismatchError,
    SolverUnavailableError,
    load_solver,
    resolve_dist_dir,
)
from .result import CompletionFact, Diagnostic, SolveResult, SolveTelemetry

__all__ = [
    "DEFAULT_ITERATION_CAP",
    "NATIVE_CONVERGENCE",
    "SOLVER_ABI",
    "SOLVER_CONTRACT",
    "TOL_BLOCK",
    "TOL_SCALAR",
    "WEAK_POLICY",
    "CompletionFact",
    "Diagnostic",
    "SolveResult",
    "SolveTelemetry",
    "SolverABIMismatchError",
    "SolverArtifactMissingError",
    "SolverContractMismatchError",
    "SolverOriginMismatchError",
    "SolverUnavailableError",
    "load_solver",
    "resolve_dist_dir",
    "solve",
]
