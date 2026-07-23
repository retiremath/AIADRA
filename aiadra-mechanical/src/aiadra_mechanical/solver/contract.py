"""The ``skb-c0`` solver contract — the ONE immutable numeric authority.

Codex16 B3: normalization, residual-block tolerances, rank tolerance,
update-step semantics, and the default iteration cap belong NORMATIVELY to
``skb-c0``. They live here once; they are never copied as ambient mutable
values into individual records, and a change to any of them is a NEW solver
contract id, never an edit of this one.

The values are verbatim from the accepted SK-B evidence
(arc 20260715-3: corpus ``skb-1``, the ``skb-1`` machine-checked gate, and
the Gate-2 packaged candidate).
"""
from __future__ import annotations

# The numeric solver contract this module implements. The loaded native
# artifact pair must declare EXACTLY this id through the DLL handshake.
SOLVER_CONTRACT = "skb-c0"

# The AIADRA-owned weak-completion policy (SK-A/ADR-0044): AIADRA chooses the
# weak dimensions deterministically; the numerical library only solves the
# supplied system. Persisted separately from SOLVER_CONTRACT (Codex16 A2).
WEAK_POLICY = "skb-0"

# The native artifact ABI this loader speaks (the DLL-side handshake's first
# field). Bump only with a breaking change to the DLL export surface.
SOLVER_ABI = "aiadra-planegcs-abi:1"

# The Python-extension ABI the binding is built for.
BINDING_ABI = "cp312-win_amd64"

# --- normative numerics (skb-c0) -------------------------------------------
# Canonical units: mm, degrees, dimensionless direction blocks (skb-1 SCHEMA
# section 2b). Residual blocks are typed per block, never one scalar soup.
RESIDUAL_BLOCKS = ("length_mm", "direction", "angle_deg")

# Per-block convergence tolerance (solver contract skb-c0).
TOL_BLOCK = 1e-10

# Expectation comparison tolerance per solved scalar (evidence comparisons).
TOL_SCALAR = 1e-9

# The native solve convergence handed to the library (DogLeg, fine).
NATIVE_CONVERGENCE = 1e-10

# Default update-step budget; a case may pin its own ``iteration_cap``.
DEFAULT_ITERATION_CAP = 200

# Rank tolerance on unit-normalized Jacobian rows (classification + skb-0).
RANK_TOL = 1e-7

# Central-difference step for the numeric Jacobian (scaled by max(1, |x|)).
FD_STEP = 1e-6

# The canonical result serializer contract (skb-1 SCHEMA section 5).
SERIALIZER_ID = (
    "skb-canon-1: json keys sorted, compact separators, shortest "
    "round-trip float repr, no quantization, -0.0 canonicalized, "
    "NaN/Infinity rejected"
)
