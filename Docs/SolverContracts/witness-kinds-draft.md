# Witness kinds — DRAFT (informative; NOT normative, NOT frozen)

- **Status:** DRAFT (arc 20260717-2, Codex23 B4). Nothing here is part of any
  frozen branch-policy id. `skb-b0`'s catalog derives the EMPTY witness set
  for every admitted graph, so `skb-b0` freezes NO measure, NO degeneracy
  threshold, and NO golden vector. This document preserves the measure
  schemas drafted during the arc so the machinery does not rot; the
  executable prototype is `aiadra_mechanical.solver.witness_draft` (consumed
  by nothing in production; only the draft-parity tests run it).
- **What freezing requires** (the first NON-empty branch policy's own
  Codex-gated review): a **scale-aware operand DOMAIN** — including a
  positive lower bound for radius — and an **error bound proven against the
  worst admitted scale**, with boundary vectors matching that domain and
  solver evidence. `L_min` alone does not establish operand scale: a
  `cross_sign` denominator just above `L_min = 1e-9 mm` amplifies a
  `1e-10 mm` coordinate perturbation into an order-`1e-1` measure change,
  and `side_of_line` currently divides by ANY positive finite radius. The
  draft `ε = 1e-9` below is therefore a PLACEHOLDER, not an evidenced
  threshold.

## 1. Shared rules (draft)

- A witness is `{id, kind, of: [ordered operands], sign: +1 | -1, origin:
  {category: "computed_result", policy: <the freezing policy id>,
  solver_contract: "skb-c0"}}` — deeply immutable, no coordinates.
- **Operand validity precedes measure evaluation.** An operand-invalid,
  non-finite, or undefined measure at MINT refuses the commit (typed,
  naming the descriptor); at REGENERATION it is `branch-degenerate`.
- ε classifies only a DEFINED measure: `|m| <= ε` → mint refusal /
  `branch-degenerate`; defined `m` with the opposite committed sign →
  `branch-mismatch`. Nothing else exists.
- **Canonical ordering + ids**: witnesses sort kind-major (lexicographic
  kind name) then by ordered-operand ref tuple (lexicographic); ids
  `bw01, bw02, ...` assigned in that canonical order at every mint; the
  atomic authoring transaction replaces the WHOLE set.
- **The sign is defined over the canonical operand order**; no consumer
  reorders operands.
- **Uniqueness**: at most one witness per (kind, ordered-operand tuple);
  duplicates refuse.

## 2. Kind schemas (draft)

### 2.1 `cross_sign` — orientation of three points

- Operands: `[a, b, p]` — three **pairwise-distinct canonical point-valued
  refs** (a point entity id, or an arc endpoint sub-ref `<arc>.start` /
  `<arc>.end`; distinctness is over the canonical REF, not the owning
  entity).
- Measure: `m = cross(b − a, p − b) / (|b − a| · |p − b|)`, dimensionless.
- Domain (draft): DEFINED iff `|b − a| > L_min` and `|p − b| > L_min` and
  every coordinate a strict finite number. THE SCALE-AWARE DOMAIN IS
  UNRESOLVED — see the freezing requirements above.

### 2.2 `side_of_line` — which side of a directed line a curve center lies

- Operands: `[line, curve]` — a line entity id (direction = authored
  start → end) and a center-bearing curve entity id (circle or arc).
- Measure: `m = signed_point_line(center, line.start, line.end) / radius`,
  dimensionless (`signed_point_line(p, a, b) = (p.x − a.x)·u_y −
  (p.y − a.y)·u_x`, `u = (b − a)/|b − a|` — the skb-1 §2b construction).
- Domain (draft): DEFINED iff `|line.end − line.start| > L_min`, `radius` a
  strict finite number `> 0`, all coordinates strict finite numbers. A
  POSITIVE LOWER BOUND FOR RADIUS IS REQUIRED BEFORE FREEZING.

## 3. Golden vectors (executable; the draft-parity test runs the DRAFT equations on these)

Coordinates in mm; `"inf"` denotes IEEE-754 +infinity constructed by the test. `expect.m` is compared to the production result with absolute tolerance 1e-15 when present; `classification` is exact.

<!-- witness-draft:golden-vectors -->
```json
[
  {"kind": "cross_sign", "a": [0,0], "b": [10,0], "p": [10,10], "expect": {"m": 1.0, "classification": "+1"}},
  {"kind": "cross_sign", "a": [0,0], "b": [10,0], "p": [10,-10], "expect": {"m": -1.0, "classification": "-1"}},
  {"kind": "cross_sign", "a": [10,0], "b": [0,0], "p": [10,10], "expect": {"m": -0.7071067811865475, "classification": "-1"}, "note": "operand-order sensitivity: same points as vector 1 with a/b swapped"},
  {"kind": "cross_sign", "a": [0,0], "b": [10,0], "p": [20,0], "expect": {"m": 0.0, "classification": "degenerate"}},
  {"kind": "cross_sign", "a": [0,0], "b": [10,0], "p": [20,1e-8], "expect": {"m": 1e-9, "classification": "degenerate"}, "note": "exact +epsilon boundary: |m| <= eps refuses a sign"},
  {"kind": "cross_sign", "a": [0,0], "b": [10,0], "p": [20,2e-8], "expect": {"m": 2e-9, "classification": "+1"}, "note": "just outside +epsilon"},
  {"kind": "cross_sign", "a": [0,0], "b": [10,0], "p": [20,-2e-8], "expect": {"m": -2e-9, "classification": "-1"}, "note": "just outside -epsilon"},
  {"kind": "cross_sign", "a": [0,0], "b": [0,0], "p": [5,5], "expect": {"classification": "undefined"}, "note": "collapsed a-b segment"},
  {"kind": "cross_sign", "a": [0,0], "b": [5e-10,0], "p": [5,5], "expect": {"classification": "undefined"}, "note": "|b-a| <= L_min"},
  {"kind": "cross_sign", "a": [0,0], "b": [10,0], "p": ["inf",0], "expect": {"classification": "undefined"}, "note": "non-finite operand"},
  {"kind": "side_of_line", "line_a": [0,0], "line_b": [10,0], "center": [5,3], "radius": 3, "expect": {"m": -1.0, "classification": "-1"}, "note": "center on +y of the +x-directed line is NEGATIVE under the skb-1 signed_point_line construction"},
  {"kind": "side_of_line", "line_a": [0,0], "line_b": [10,0], "center": [5,-3], "radius": 3, "expect": {"m": 1.0, "classification": "+1"}},
  {"kind": "side_of_line", "line_a": [0,0], "line_b": [10,0], "center": [5,3], "radius": 2, "expect": {"m": -1.5, "classification": "-1"}},
  {"kind": "side_of_line", "line_a": [0,0], "line_b": [10,0], "center": [5,0], "radius": 5, "expect": {"m": 0.0, "classification": "degenerate"}},
  {"kind": "side_of_line", "line_a": [0,0], "line_b": [10,0], "center": [5,1e-8], "radius": 10, "expect": {"m": -1e-9, "classification": "degenerate"}, "note": "exact -epsilon boundary"},
  {"kind": "side_of_line", "line_a": [0,0], "line_b": [10,0], "center": [5,2e-8], "radius": 10, "expect": {"m": -2e-9, "classification": "-1"}, "note": "just outside -epsilon"},
  {"kind": "side_of_line", "line_a": [0,0], "line_b": [10,0], "center": [5,3], "radius": 0, "expect": {"classification": "undefined"}, "note": "non-positive radius"},
  {"kind": "side_of_line", "line_a": [0,0], "line_b": [10,0], "center": [5,3], "radius": -1, "expect": {"classification": "undefined"}},
  {"kind": "side_of_line", "line_a": [0,0], "line_b": [0,0], "center": [5,3], "radius": 3, "expect": {"classification": "undefined"}, "note": "collapsed directed line"},
  {"kind": "side_of_line", "line_a": [0,0], "line_b": [10,0], "center": [5,3], "radius": "inf", "expect": {"classification": "undefined"}, "note": "non-finite radius"}
]
```

*witness-kinds-draft ends. These equations are rehearsal, not law — the
first policy that needs them must first prove where they are allowed to
speak.*
