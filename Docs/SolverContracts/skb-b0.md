# `branch_policy: "skb-b0"` — the v2 branch-identity contract (normative, immutable)

- **Status:** FROZEN (arc 20260717-2; Codex22 design signoff, scope corrected at the F2a gate — Codex23: witness measures/ε removed from the frozen content because an empty catalog freezes no measure; Codex24: the §3 array-order law stated explicitly and reconciled with ADR/0044 A2.2/A2.10 — all BEFORE any record stamped this id). This id is immutable from the F2a gate on: ANY semantic change to anything in this document is a NEW policy id in a NEW file (`skb-b1.md`), never an edit here. Records that stamp `skb-b0` are governed by this document forever.
- **Authority chain:** ADR/0044 Amendment A2 (A2.2, A2.6, A2.10) names this file as the single durable normative source of `skb-b0`. The production module `aiadra_mechanical.solver.branch_policy` IMPLEMENTS it; parity tests extract the machine-readable blocks below and enforce COMPLETE-structure correspondence (constants, the local table, the whole graph predicate). Drift anywhere is a red suite.
- **The governing rule:** *a list of safe equations is not yet a safe system.* Branch freedom is a property of complete fact GRAPHS, never of isolated constraint signatures (the fixed-circle + `point_on` + weak-x counterexample: every row individually branch-free, the composed system two-rooted). This policy therefore admits whole graphs only, and every admitted graph shape carries a single-root proof (§4) or required witness coverage (none in skb-b0 — §6).

## 1. Constants

<!-- skb-b0:constants -->
```json
{
  "policy_id": "skb-b0",
  "solver_contract": "skb-c0",
  "weak_policy": "skb-0",
  "L_min_mm": 1e-9
}
```

- `L_min_mm` — the length-domain floor for the admission displacement guards (strictly-greater passes). Versioned here.
- **There is NO degeneracy threshold ε under skb-b0** (Codex23 B4): this policy's catalog derives the EMPTY witness set for every admitted graph, so no witness measure is normative under this id. Measure schemas, ε, and their vectors are DRAFT material for the first non-empty policy — see §5.

## 2. Layer 1 — the local signature table (necessary, never sufficient)

<!-- skb-b0:local-table -->
```json
{
  "entity_kinds": ["point", "line"],
  "construction_only": true,
  "fact_kinds": {
    "fix": {"signature": ["point"], "class": "strong"},
    "horizontal": {"signature": ["line"], "class": "strong"},
    "vertical": {"signature": ["line"], "class": "strong"},
    "fix_param": {"signature": ["parameter"], "class": "weak-completion-only"}
  },
  "dimension_kinds": {}
}
```

Everything outside this table — every other entity kind, constraint kind, any dimension, any non-construction entity — is typed out-of-domain for `skb-b0`, refused at all five enforcement surfaces (§7). Passing layer 1 admits NOTHING by itself; layer 2 is the authority.

## 3. Layer 2 — the whole-fact-graph admission predicate

A v2 fact graph is admitted under `skb-b0` iff it structurally matches EXACTLY ONE of the three shapes below. Matching binds roles to actual record ids by STRUCTURE (ids are arbitrary); cardinalities are exact — extra or missing entities, facts, weak records, or guards refuse. **Array-order law (Codex24 B1)**: the ENTITY and STRONG-FACT arrays are semantically UNORDERED (every permutation of the same graph admits identically and hashes identically — canonical identity normalizes them); the WEAK-COMPLETION array — and any witness array under a later, non-empty policy — is CANONICALLY ORDERED (requirement 1: `w01, w02, …` in canonical parameter order; a permuted weak array refuses). The machine-readable form:

<!-- skb-b0:array-order -->
```json
{
  "entities": "unordered",
  "constraints": "unordered",
  "dimensions": "unordered",
  "references": "unordered",
  "weak_completion": "canonical",
  "witnesses": "canonical"
}
```

<!-- skb-b0:graph-predicate -->
```json
{
  "G0": {
    "entities": [{"role": "O", "type": "point", "construction": true}],
    "strong_facts": [{"kind": "fix", "args": ["O"]}],
    "weak_completion": [],
    "guards": []
  },
  "G1": {
    "entities": [
      {"role": "O", "type": "point", "construction": true},
      {"role": "PX", "type": "point", "construction": true},
      {"role": "AX", "type": "line", "construction": true, "start": "O", "end": "PX"}
    ],
    "strong_facts": [
      {"kind": "fix", "args": ["O"]},
      {"kind": "horizontal", "args": ["AX"]}
    ],
    "weak_completion": [{"target_role": "PX", "target_parameter": "x"}],
    "guards": [{"signed_displacement": ["PX.x", "O.x"], "exceeds": "L_min_mm"}]
  },
  "G2": {
    "extends": "G1",
    "entities_add": [
      {"role": "PY", "type": "point", "construction": true},
      {"role": "AY", "type": "line", "construction": true, "start": "O", "end": "PY"}
    ],
    "strong_facts_add": [{"kind": "vertical", "args": ["AY"]}],
    "weak_completion_add": [{"target_role": "PY", "target_parameter": "y"}],
    "guards_add": [{"signed_displacement": ["PY.y", "O.y"], "exceeds": "L_min_mm"}]
  }
}
```

Additional admission requirements (all refuse on violation):

1. **Weak records are FULL verbatim skb-0 records** (Codex22 N1) — validated field-by-field: sequential ids `w01, w02, …` in canonical parameter order (entity-id lexicographic × catalogue parameter order), exact `target {entity, parameter}`, `value {magnitude, unit: "mm"}`, `strength: "weak"`, `role: "driving"`, `visibility: "internal"`, `origin {category: "computed_result", policy: "skb-0", solver_contract: "skb-c0"}`. Target names alone are NOT validation.
2. **Magnitude equals the authored nominal**: each weak record's `value.magnitude` must equal the target entity's authored nominal coordinate exactly (IEEE-754 double equality of the decoded values). A weak record contradicting its nominal refuses.
3. **Guards run on EFFECTIVE values** (Codex22 N1): the guard displacement uses the weak record's persisted magnitude for the weak-fixed coordinate and the `fix` anchor's authored nominal for `O` — the values the solve will actually pin, not unvalidated nominals.
4. **Guards are SIGNED**: `PX.x − O.x > L_min` and `PY.y − O.y > L_min`. The reference axes are DIRECTED construction lines — the named positive-X / positive-Y directions are canonical (a sketch frame, not unoriented infinite axes). A negative or sub-floor displacement refuses admission.
5. **Every entity is `construction: true`**; the sketch carries no profile geometry under skb-b0.

## 4. The single-root proofs (why the empty firewall is justified)

- **G0**: `fix(O)` determines both scalar coordinates directly. Zero continuous or discrete freedom. ∎
- **G1**: `fix(O)` pins `O = (O.x, O.y)`. The weak record pins `PX.x` (its persisted magnitude; guard: `PX.x − O.x > L_min > 0`, so the line cannot collapse and the normalized direction is defined). The single remaining unknown is `PX.y`; `horizontal(AX)` demands unit-direction `u_y = 0`, i.e. `PX.y = O.y` — one linear equation, one root. The direction-flip family (`u = (−1, 0)`) would require `PX.x < O.x`, excluded by the SIGNED guard, and `PX.x` is not free to move there in any case because it is a persisted weak fact, not a solver unknown. Unique root. ∎
- **G2**: G1's argument, plus symmetrically: weak pins `PY.y` with `PY.y − O.y > L_min`; `vertical(AY)` gives the unique `PY.x = O.x`. The two sub-systems share only the fully-fixed `O`. Unique root. ∎

Consequence: the exact derived witness set for every admitted skb-b0 graph is **∅** (§6). Any future shape without such a proof requires witness coverage under a NEW policy id.

## 5. Witness kinds — NONE are normative under skb-b0 (Codex23 B4)

This policy's catalog derives the EMPTY witness set for every admitted graph (§4/§6), so **no witness kind, measure, degeneracy threshold, or golden vector is frozen by this id**. On a `skb-b0` record, ANY present witness is EXTRA and refuses (§6) — that exact-set rule is the whole of skb-b0's witness law.

The measure schemas drafted during this arc (`cross_sign`, `side_of_line`), their shared rules (canonical ordering, `bw` ids, sign-over-canonical-order, uniqueness), the draft ε, and the executable golden vectors live in [`witness-kinds-draft.md`](witness-kinds-draft.md) — **explicitly informative, not frozen**. They freeze only with the first NON-empty branch policy (its own Codex-gated id), which must additionally pin a **scale-aware operand domain** (including a positive lower bound for radius) and prove its ε against an error bound at the worst admitted scale — `L_min` alone does not establish operand scale, and a denominator just above `L_min` amplifies solver-scale coordinate noise by orders of magnitude.

## 6. The catalog — a total function to an EXACT set

For every admitted graph (G0/G1/G2): the derived witness-descriptor set is **∅** — an explicit result of §4's proofs, not a default. Decode and commit therefore reject on a `skb-b0` record: any present witness (EXTRA), any duplicate, and — vacuously here, executable under the first non-empty policy — any missing required descriptor. The exact-set rule is what makes "complete witness set" executable and keeps recipe identity unperturbable by valid-looking extras.

## 7. Enforcement

The five surfaces — mechanical **encode**, **decode**, **handler**, **evaluator**, and the Studio **decoder** — all consult this one policy (layer 1 + layer 2 + §6): out-of-table signatures, non-matching graphs, invalid weak records, failed guards, and witness-set violations refuse typed at every surface. Required negative fixtures include BOTH kinds: layer-1 failures (the fixed-circle + `point_on` + weak-x counterexample and variants) AND layer-2-only failures that PASS layer 1 (G1 + an extra construction point; a wrong weak target; a missing axis fact; an extra `horizontal` fact/line; G2 with an incomplete or swapped weak set) — proving layer 2 is real authority (Codex22 N2).


*skb-b0 ends. Three proved graphs, an empty witness catalog, and nothing else gets in under this id — every measure waits for the policy that can prove it.*
