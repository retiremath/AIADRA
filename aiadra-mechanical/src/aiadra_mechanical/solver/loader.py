"""The fail-closed native-solver loader (Codex16 B2 + Codex17 B1).

Deterministic compatibility protocol, in order, every check loud and typed:

1. resolve the EXPLICIT packaged artifact location (``AIADRA_SOLVER_DIST``
   override, else the repository's ``aiadra-solver/dist``) — never an
   arbitrary module or DLL found on ``PATH``/``sys.path``;
2. verify the running interpreter matches the binding ABI (cp312-win_amd64)
   BEFORE any import is attempted;
3. import the binding from that explicit path only, retaining the DLL
   search-directory handle for the cached module's lifetime;
4. verify the binding's OWN declared identity (``BINDING_ABI`` +
   ``BINDING_SOLVER_CONTRACT``);
5. demand the DLL-side handshake: the replaceable ``planegcs.dll`` must
   itself export ``aiadra_planegcs_handshake`` and declare the ABI + solver
   contract it executes. A DLL that cannot identify its supported contract
   is refused. Binary digests are provenance evidence, NEVER this check — a
   legitimately rebuilt LGPL replacement has different PE bytes while
   implementing the same declared ABI and contract;
6. prove the handshaking module IS the selected artifact (Codex17 B1): the
   binding reports the loaded DLL's absolute path (``GetModuleFileNameW``
   on the same ``HMODULE`` the handshake used) and the loader compares it,
   canonicalized, to ``<selected dist>/planegcs.dll``. A conforming but
   wrong-origin/preloaded same-name DLL is refused with a typed origin
   error — the declaration is only trusted from the file the loader
   actually selected.

Every refusal derives from :class:`SolverUnavailableError`.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

from .contract import BINDING_ABI, SOLVER_ABI, SOLVER_CONTRACT

_PYD_NAME = "aiadra_solver.cp312-win_amd64.pyd"
_DLL_NAME = "planegcs.dll"

_ENV_OVERRIDE = "AIADRA_SOLVER_DIST"


class SolverUnavailableError(RuntimeError):
    """Base refusal: the native solver artifact cannot be used."""


class SolverArtifactMissingError(SolverUnavailableError):
    """The packaged artifact location or a required file is absent."""


class SolverABIMismatchError(SolverUnavailableError):
    """Interpreter/binding/DLL ABI does not match the declared contract."""


class SolverContractMismatchError(SolverUnavailableError):
    """The artifact cannot identify — or names a different — solver contract."""


class SolverOriginMismatchError(SolverUnavailableError):
    """The handshaking DLL is not the explicitly selected artifact file."""


# (dist, module, dll-directory handle) — the handle is deliberately retained
# so the search-path cookie lives at least as long as the cached module
# (Codex17 B1.1).
_cached: tuple[str, ModuleType, object] | None = None


def resolve_dist_dir() -> Path:
    """Resolve the explicit artifact directory; never search ``PATH``.

    ``AIADRA_SOLVER_DIST`` (when set) is taken literally and must exist.
    Otherwise the repository layout authority applies: walk up from this
    file to the first ancestor containing ``aiadra-solver/dist``.
    """
    override = os.environ.get(_ENV_OVERRIDE)
    if override:
        cand = Path(override)
        if not cand.is_dir():
            raise SolverArtifactMissingError(
                f"{_ENV_OVERRIDE}={override!r} does not name a directory — "
                "the override is taken literally and must exist"
            )
        return cand
    for parent in Path(__file__).resolve().parents:
        cand = parent / "aiadra-solver" / "dist"
        if cand.is_dir():
            return cand
    raise SolverArtifactMissingError(
        "no aiadra-solver/dist directory found above aiadra_mechanical — "
        "the native solver artifact home is absent (build it per "
        "aiadra-solver/src/BUILD.md, or set AIADRA_SOLVER_DIST)"
    )


def _require_interpreter_abi() -> None:
    ok = (
        sys.implementation.name == "cpython"
        and sys.version_info[:2] == (3, 12)
        and sys.platform == "win32"
        and sys.maxsize > 2**32
    )
    if not ok:
        raise SolverABIMismatchError(
            "the packaged binding targets CPython 3.12 x64 Windows "
            f"({BINDING_ABI}); this interpreter is "
            f"{sys.implementation.name} {sys.version.split()[0]} on {sys.platform}"
        )


def _parse_handshake(declared: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for segment in declared.split(";"):
        key, sep, value = segment.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def _canonical(path: Path | str) -> str:
    """One comparison form for Windows paths: resolved + case-folded."""
    return os.path.normcase(str(Path(path).resolve()))


def load_solver() -> ModuleType:
    """Load and VERIFY the native solver; return the binding module.

    Idempotent per artifact directory. Raises a typed
    :class:`SolverUnavailableError` subclass on every failure mode named in
    Codex16 B2 and Codex17 B1 — binding ABI mismatch, native DLL ABI
    mismatch, absence of the requested solver contract, a DLL that cannot
    identify its supported contract, or a handshaking DLL that is not the
    selected artifact file.
    """
    global _cached
    dist = resolve_dist_dir()
    if _cached is not None and _cached[0] == str(dist):
        return _cached[1]

    pyd = dist / _PYD_NAME
    dll = dist / _DLL_NAME
    missing = [p.name for p in (pyd, dll) if not p.is_file()]
    if missing:
        raise SolverArtifactMissingError(
            f"native solver artifact incomplete under {dist}: missing "
            f"{', '.join(missing)} (the binaries are deliberately not in "
            "git — build them per aiadra-solver/src/BUILD.md)"
        )

    _require_interpreter_abi()

    dll_dir_handle = os.add_dll_directory(str(dist))
    spec = importlib.util.spec_from_file_location("aiadra_solver", pyd)
    if spec is None or spec.loader is None:
        raise SolverABIMismatchError(
            f"the binding at {pyd} is not importable as a CPython extension"
        )
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ImportError as exc:
        raise SolverABIMismatchError(
            f"the binding at {pyd} failed to load — native DLL/extension "
            f"ABI mismatch: {exc}"
        ) from exc

    _verify_binding(module, expected_dll=dll)

    _cached = (str(dist), module, dll_dir_handle)
    return module


def _verify_binding(module: ModuleType, expected_dll: Path | None = None) -> None:
    """Steps 4–6 of the compatibility protocol, on an already-loaded binding.

    Separated so every refusal branch is provable without fabricating a
    broken native artifact. ``expected_dll`` (when given) arms the Codex17
    B1 origin check: the loaded DLL's reported absolute path must be the
    selected artifact file.
    """
    binding_abi = getattr(module, "BINDING_ABI", None)
    binding_contract = getattr(module, "BINDING_SOLVER_CONTRACT", None)
    if binding_abi is None or binding_contract is None:
        raise SolverContractMismatchError(
            "the loaded binding declares no BINDING_ABI/"
            "BINDING_SOLVER_CONTRACT — it predates the handshake surface "
            "and cannot identify its supported contract; refuse it"
        )
    if binding_abi != BINDING_ABI:
        raise SolverABIMismatchError(
            f"binding ABI {binding_abi!r} != required {BINDING_ABI!r}"
        )
    if binding_contract != SOLVER_CONTRACT:
        raise SolverContractMismatchError(
            f"binding solver contract {binding_contract!r} != required "
            f"{SOLVER_CONTRACT!r}"
        )

    try:
        declared = module.dll_handshake()
    except AttributeError as exc:
        raise SolverContractMismatchError(
            "the loaded binding exposes no dll_handshake() — it cannot "
            "prove what the native DLL executes; refuse it"
        ) from exc
    except RuntimeError as exc:
        # The binding's own loud refusals: DLL not loaded, export absent,
        # empty declaration. All mean the DLL cannot identify its contract.
        raise SolverContractMismatchError(str(exc)) from exc

    fields = _parse_handshake(declared)
    abi_key, _, abi_want = SOLVER_ABI.partition(":")
    if fields.get(abi_key) != abi_want:
        raise SolverABIMismatchError(
            f"planegcs.dll declares {declared!r}; required ABI {SOLVER_ABI!r}"
        )
    if fields.get("solver-contract") != SOLVER_CONTRACT:
        raise SolverContractMismatchError(
            f"planegcs.dll declares {declared!r}; it does not implement the "
            f"requested solver contract {SOLVER_CONTRACT!r}"
        )

    if expected_dll is not None:
        try:
            origin = module.dll_origin()
        except AttributeError as exc:
            raise SolverOriginMismatchError(
                "the loaded binding exposes no dll_origin() — the "
                "handshaking DLL's filesystem origin cannot be proven; "
                "refuse it"
            ) from exc
        except RuntimeError as exc:
            raise SolverOriginMismatchError(str(exc)) from exc
        if _canonical(origin) != _canonical(expected_dll):
            raise SolverOriginMismatchError(
                f"the handshaking planegcs.dll is {origin!r}, not the "
                f"selected artifact {str(expected_dll)!r} — a same-named "
                "module from another origin is loaded in this process; "
                "its declaration is not trusted"
            )
