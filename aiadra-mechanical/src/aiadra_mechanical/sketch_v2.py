"""The v2 constrained-sketch codec — adapter series 0.2.x (ADR/0044 A2).

Gate F2a scope: ENCODE, DECODE, VALIDATE, and REFUSE — no authoring, no
solver in any path here, no v2 write exists anywhere. The five enforcement
surfaces (A2.6.3) share this module: encode/decode directly, the evaluator
and topology signature via :func:`refuse_v2_at_evaluation`, the handlers via
the targeted consume/adjust guards, and the Studio decoder mirrors the same
rules in TypeScript.

A v2 sketch record:

- `adapter_schema_version: "0.2.0"` (the concrete first-writer version;
  A2.4 — the sketch family admits {0.1.x, 0.2.x}; every other family
  refuses 0.2.x);
- `adapter_payload` carries the FULL constrained contract (A2.5): plane,
  id-addressed entities/constraints/dimensions/references, the verbatim
  skb-0 weak completion, the witness set, `sketch_model: 2`, and the three
  contract ids. The payload's SEMANTIC content participates in canonical
  recipe identity (A2.7): `kernel._canonical_payload` sorts the four
  semantically-unordered collections by id (one identity for one graph —
  Codex23 B1) and hashes the policy-ordered weak/witness arrays verbatim;
  `adapter_schema_version` stays excluded — v1 hashes untouched.

Admission is graph-level under `branch_policy` (skb-b0: exactly G0/G1/G2);
weak records are validated as FULL verbatim skb-0 records; nested `origin`
blocks are cross-checked against the record's top-level contract ids
(A2.8 — a contradiction never becomes identity-bearing); the witness set
must equal the catalog's exact derived set (∅ under skb-b0 — any present
witness is EXTRA and refuses). Decoded values are DEEPLY immutable.
"""
from __future__ import annotations

import copy
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from aiadra_core.transaction.boundary import TransactionError

from .recipe import validate_plane_record
from .solver import branch_policy
from .solver.contract import SOLVER_CONTRACT, WEAK_POLICY

SKETCH_V2_ADAPTER_VERSION = "0.2.0"
SKETCH_MODEL_V2 = 2

_OP = "mechanical.sketch_v2"

_PAYLOAD_KEYS = {
    "sketch_model", "solver_contract", "weak_policy", "branch_policy",
    "plane", "entities", "constraints", "dimensions", "references",
    "weak_completion", "witnesses",
}


def _fail(reason: str) -> None:
    raise TransactionError(f"{_OP}: {reason}")


def is_v2_series(version: Any) -> bool:
    return isinstance(version, str) and version.startswith("0.2.")


def _deep_freeze(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return MappingProxyType({k: _deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        return tuple(_deep_freeze(v) for v in obj)
    return obj


def validate_v2_sketch_record(record: Mapping[str, Any]) -> branch_policy.Admission:
    """Validate one v2 sketch feature record completely; return the admission.

    Every failure is a typed loud refusal. This is the ONE rule set behind
    encode and decode; nothing interprets a v2 payload without it.
    """
    # Codex23 B2: this is the MECHANICAL codec — a foreign-engine record
    # coincidentally stamped 0.2.x is never interpreted here (the evaluator
    # guard leaves foreign engines opaque; direct callers refuse loudly).
    if record.get("engine") != "mechanical":
        _fail(
            f"feature {record.get('id')!r} belongs to engine "
            f"{record.get('engine')!r} — the mechanical v2 codec interprets "
            "mechanical records only"
        )
    if record.get("feature_type") != "sketch":
        _fail(
            f"feature {record.get('id')!r} ({record.get('feature_type')!r}) "
            f"carries adapter series 0.2.x, but only the SKETCH family has "
            f"defined 0.2 semantics (ADR/0044 A2.4) — refuse"
        )
    version = record.get("adapter_schema_version")
    if version != SKETCH_V2_ADAPTER_VERSION:
        _fail(
            f"sketch {record.get('id')!r} carries {version!r}; the only "
            f"defined v2 writer version is {SKETCH_V2_ADAPTER_VERSION!r} "
            "(an unknown 0.2.x minor refuses rather than guessing)"
        )
    payload = record.get("adapter_payload")
    if not isinstance(payload, Mapping):
        _fail(f"sketch {record.get('id')!r} has no object adapter_payload")

    keys = set(payload.keys())
    if keys != _PAYLOAD_KEYS:
        missing = _PAYLOAD_KEYS - keys
        extra = keys - _PAYLOAD_KEYS
        _fail(
            f"v2 payload key set mismatch — missing {sorted(missing)}, "
            f"unknown {sorted(extra)} (the v2 contract is closed; A2.5)"
        )

    if payload["sketch_model"] != SKETCH_MODEL_V2:
        _fail(f"sketch_model {payload['sketch_model']!r} != {SKETCH_MODEL_V2}")
    ids = (payload["solver_contract"], payload["weak_policy"], payload["branch_policy"])
    want = (SOLVER_CONTRACT, WEAK_POLICY, branch_policy.POLICY_ID)
    if ids != want:
        _fail(f"contract ids {ids!r} != the supported {want!r}")

    validate_plane_record(payload["plane"], op_kind=_OP)

    for name in ("entities", "constraints", "dimensions", "references",
                 "weak_completion", "witnesses"):
        if not isinstance(payload[name], Sequence) or isinstance(payload[name], (str, bytes)):
            _fail(f"payload {name} must be an array")
        # Codex24 B2: every array ENTRY must be an object — a malformed
        # record fails through the typed boundary, never as an interpreter
        # AttributeError (checked for all six collections, including the
        # ones skb-b0 requires empty).
        for i, entry in enumerate(payload[name]):
            if not isinstance(entry, Mapping):
                _fail(
                    f"payload {name}[{i}] is {type(entry).__name__!s}, not an "
                    "object — every v2 collection entry is a record"
                )

    if list(payload["references"]):
        _fail("references must be empty under skb-b0 (body-edge projection "
              "is SK-E; the fixed references ARE the construction entities)")

    # A2.8: nested origin blocks cross-check the record's TOP-LEVEL ids.
    for w in payload["weak_completion"]:
        origin = w.get("origin") if isinstance(w, Mapping) else None
        if isinstance(origin, Mapping):
            if origin.get("policy") not in (None, payload["weak_policy"]) or \
               origin.get("solver_contract") not in (None, payload["solver_contract"]):
                _fail(
                    f"weak record {w.get('id')!r} origin "
                    f"({origin.get('policy')!r}/{origin.get('solver_contract')!r}) "
                    f"contradicts the record's top-level ids — refuse "
                    "(a contradiction never becomes identity-bearing)"
                )
    for wit in payload["witnesses"]:
        origin = wit.get("origin") if isinstance(wit, Mapping) else None
        if isinstance(origin, Mapping):
            if origin.get("policy") not in (None, payload["branch_policy"]) or \
               origin.get("solver_contract") not in (None, payload["solver_contract"]):
                _fail(
                    f"witness {wit.get('id')!r} origin contradicts the "
                    "record's top-level ids — refuse"
                )

    try:
        admission = branch_policy.admit_graph(
            payload["entities"], payload["constraints"],
            payload["dimensions"], payload["weak_completion"],
        )
        branch_policy.validate_witness_set(payload["witnesses"], admission)
    except branch_policy.OutOfDomain as exc:
        _fail(str(exc))
    return admission


def decode_v2_sketch(record: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate + return a DEEPLY immutable view of the v2 record (A2.8).

    Every nested mapping becomes a read-only proxy and every array a tuple —
    including operand/reference lists and origin blocks; there is no mutable
    interior to corrupt after decode.
    """
    admission = validate_v2_sketch_record(record)
    frozen = _deep_freeze(dict(record))
    return MappingProxyType({
        "record": frozen,
        "shape": admission.shape,
        "roles": MappingProxyType(dict(admission.roles)),
    })


def encode_v2_sketch(*, feature_id: str, name: str, plane: Mapping[str, Any],
                     entities: Sequence[Mapping[str, Any]],
                     constraints: Sequence[Mapping[str, Any]],
                     weak_completion: Sequence[Mapping[str, Any]],
                     fact_provenance: Mapping[str, Any]) -> dict[str, Any]:
    """Build a canonical v2 sketch feature record — and VALIDATE it.

    F2a has no writer: this exists for the codec's own round-trip proofs and
    for the F2b authoring transaction to consume later. Encoding an
    inadmissible graph refuses exactly like decoding one.
    """
    # Codex23 B2: DEEP copies — a caller mutating its input objects after
    # encode must never alter the already-encoded record (the codec boundary
    # is trustworthy before F2b consumes it).
    record = {
        "id": feature_id,
        "name": name,
        "feature_type": "sketch",
        "engine": "mechanical",
        "adapter_schema_version": SKETCH_V2_ADAPTER_VERSION,
        "adapter_payload": {
            "sketch_model": SKETCH_MODEL_V2,
            "solver_contract": SOLVER_CONTRACT,
            "weak_policy": WEAK_POLICY,
            "branch_policy": branch_policy.POLICY_ID,
            "plane": copy.deepcopy(dict(plane)),
            "entities": [copy.deepcopy(dict(e)) for e in entities],
            "constraints": [copy.deepcopy(dict(c)) for c in constraints],
            "dimensions": [],
            "references": [],
            "weak_completion": [copy.deepcopy(dict(w)) for w in weak_completion],
            "witnesses": [],
        },
        "fact_provenance": copy.deepcopy(dict(fact_provenance)),
    }
    validate_v2_sketch_record(record)
    return record


# ---------------------------------------------------------------------------
# Gate F2b (Codex25 signoff): solver-backed authoring + read-side regeneration.
# The A2.9 lifecycles, disjoint by construction:
#   - AUTHORING (write): build the graph → PREVIEW solve → take skb-0's weak
#     completion VERBATIM from the solver lane → derive the (empty) witness
#     set → validate → return one whole record. Any failure = nothing exists.
#   - REGENERATION (read): solve from committed nominals + facts only,
#     validate the committed weak set EQUALS the derived one and every
#     committed witness (none under skb-b0), then hand back DERIVED solved
#     coordinates for display. Never remints, never rebases, never writes.
# ---------------------------------------------------------------------------


def _corpus_case(feature_id: str, entities: Sequence[Mapping[str, Any]],
                 constraints: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Translate an admitted v2 graph into the skb-1-shaped system the typed
    solver API consumes. Construction flags are v2 semantics (the solver
    case has no such axis); `fix` travels as an anchor per the corpus
    grammar."""
    ents: list[dict[str, Any]] = []
    for e in entities:
        if e["type"] == "point":
            ents.append({"id": e["id"], "type": "point",
                         "nominal": dict(e["nominal"])})
        else:
            ents.append({"id": e["id"], "type": "line",
                         "start": e["start"], "end": e["end"]})
    cons: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    for c in constraints:
        target = anchors if c["kind"] == "fix" else cons
        target.append({"id": c["id"], "kind": c["kind"], "args": list(c["args"])})
    return {"corpus_version": "skb-1", "case_id": feature_id,
            "weak_policy": WEAK_POLICY, "solver_contract": SOLVER_CONTRACT,
            "entities": ents, "constraints": cons, "dimensions": [],
            "anchors": anchors}


_AXES_SHAPES = {"none": "G0", "x": "G1", "xy": "G2"}


def author_reference_sketch(*, feature_id: str, name: str,
                            plane: Mapping[str, Any], axes: str,
                            x_axis_mm: float, y_axis_mm: float,
                            fact_provenance: Mapping[str, Any]) -> dict[str, Any]:
    """The A2.9 authoring transaction for the slice-1 REFERENCES sketch.

    Builds the canonical G0/G1/G2 construction frame (origin at (0, 0);
    directed +X/+Y axes), preview-solves it through the verified solver
    artifact, takes the skb-0 weak completion VERBATIM from the solve
    result (never hand-built), derives the empty witness set, and returns
    ONE validated record. Every failure raises before anything exists —
    the caller stages atomically or not at all.
    """
    if axes not in _AXES_SHAPES:
        _fail(f"axes must be one of {sorted(_AXES_SHAPES)}, got {axes!r}")
    for label, v in (("x_axis_mm", x_axis_mm), ("y_axis_mm", y_axis_mm)):
        if not (type(v) in (int, float) and v > 0.0):
            _fail(f"{label} must be a strictly positive number, got {v!r}")

    entities: list[dict[str, Any]] = [
        {"id": "skp_0001", "type": "point", "construction": True,
         "nominal": {"x": 0.0, "y": 0.0}},
    ]
    constraints: list[dict[str, Any]] = [
        {"id": "c01", "kind": "fix", "args": ["skp_0001"]},
    ]
    if axes in ("x", "xy"):
        entities.append({"id": "skp_0002", "type": "point", "construction": True,
                         "nominal": {"x": float(x_axis_mm), "y": 0.0}})
        entities.append({"id": "skp_0004", "type": "line", "construction": True,
                         "start": "skp_0001", "end": "skp_0002"})
        constraints.append({"id": "c02", "kind": "horizontal", "args": ["skp_0004"]})
    if axes == "xy":
        entities.append({"id": "skp_0003", "type": "point", "construction": True,
                         "nominal": {"x": 0.0, "y": float(y_axis_mm)}})
        entities.append({"id": "skp_0005", "type": "line", "construction": True,
                         "start": "skp_0001", "end": "skp_0003"})
        constraints.append({"id": "c03", "kind": "vertical", "args": ["skp_0005"]})

    from .solver import solve

    result = solve(_corpus_case(feature_id, entities, constraints))
    expected = "well" if axes == "none" else "under"
    if result.classification != expected or result.diagnostics \
            or result.solved_coordinates is None:
        diags = [d.kind for d in result.diagnostics]
        _fail(
            f"the preview solve refused the reference frame: classification "
            f"{result.classification!r} (expected {expected!r}), diagnostics "
            f"{diags} — nothing was authored"
        )
    weak = [w.to_record() for w in result.weak_completion]

    record = encode_v2_sketch(
        feature_id=feature_id, name=name, plane=plane, entities=entities,
        constraints=constraints, weak_completion=weak,
        fact_provenance=fact_provenance,
    )
    return record


def regenerate_v2_sketch(record: Mapping[str, Any]) -> Mapping[str, float]:
    """The A2.9 READ lifecycle: validate + solve from committed Truth only.

    Returns the DERIVED solved coordinates (mm, sketch-plane u/v keyed
    `<entity>.<parameter>`) for display. Refuses typed on any solve
    diagnostic, on a committed weak set differing from the derived one
    (regeneration never remints), and — under later non-empty policies —
    on witness disagreement. Never mutates the record.
    """
    decoded = decode_v2_sketch(record)
    payload = record["adapter_payload"]

    from .solver import solve

    result = solve(_corpus_case(record["id"], payload["entities"],
                                payload["constraints"]))
    expected = "well" if decoded["shape"] == "G0" else "under"
    if result.classification != expected or result.diagnostics \
            or result.solved_coordinates is None:
        diags = [d.kind for d in result.diagnostics]
        _fail(
            f"regeneration refused for sketch {record.get('id')!r}: "
            f"classification {result.classification!r} (expected "
            f"{expected!r}), diagnostics {diags}"
        )
    derived_weak = [w.to_record() for w in result.weak_completion]
    committed_weak = [dict(w) for w in payload["weak_completion"]]
    if derived_weak != committed_weak:
        _fail(
            f"regeneration refused for sketch {record.get('id')!r}: the "
            f"committed weak completion differs from the skb-0 derivation — "
            "regeneration never remints (A2.9); recovery is a new accepted "
            "authoring transaction"
        )
    # Witness validation: iterate every committed witness against the
    # policy-derived set. Under skb-b0 both are empty by admission (the
    # exact-set rule already refused extras at decode); the loop exists so
    # the read lifecycle is structurally complete for non-empty policies.
    assert len(payload["witnesses"]) == 0
    return dict(result.solved_coordinates)


def process_v2_at_evaluation(
    features: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, float]]:
    """The evaluator-side v2 lane (F2b replaces the F2a blanket refusal).

    A mechanical 0.2.x non-sketch still refuses out-of-family; a malformed
    v2 sketch still gets its specific refusal; a VALID v2 sketch now
    REGENERATES (read lifecycle) and contributes its derived solved
    coordinates — it never contributes solid geometry (construction only).
    Foreign-engine records stay opaque.
    """
    solved: dict[str, Mapping[str, float]] = {}
    for f in features:
        if not is_v2_series(f.get("adapter_schema_version")):
            continue
        if f.get("engine") != "mechanical":
            continue
        solved[str(f.get("id"))] = regenerate_v2_sketch(f)
    return solved


def validate_v2_records(features: Sequence[Mapping[str, Any]]) -> None:
    """Structural validation WITHOUT solving — the signature path and the
    mutating-handler preflight (pure; the signature must never run the
    native solver). Refuses 0.2.x non-sketch and malformed v2 sketches;
    valid v2 sketches pass."""
    for f in features:
        if not is_v2_series(f.get("adapter_schema_version")):
            continue
        if f.get("engine") != "mechanical":
            continue
        validate_v2_sketch_record(f)


# NOTE: the F2a-era `refuse_v2_at_evaluation` blanket guard is GONE (Gate
# F2b): the evaluator runs `process_v2_at_evaluation` (read lifecycle) and
# the pure surfaces run `validate_v2_records` — valid v2 sketches evaluate,
# sign, and coexist; every refusal that was not "valid v2 exists" survives
# verbatim.
