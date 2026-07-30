# `branch_policy: "skb-b1"` — the linear profile-family branch contract (normative, immutable)

- **Status:** FROZEN (arc 20260730-1; Codex5 I1 design signoff after five review rounds — the square-system proof of round 1 was REPLACED by full column rank (Codex1 B3), the graph grammar was closed (Codex1 B2), and the same-id structural survival law was pinned (Codex4 B1), all BEFORE any record stamped this id). This id is immutable from its gate on: ANY semantic change to anything in this document is a NEW policy id in a NEW file (`skb-b2.md`), never an edit here. Records that stamp `skb-b1` are governed by this document forever.
- **Authority chain:** ADR/0044 Amendment A4 names this file as the single durable normative source of `skb-b1`. The production module `aiadra_mechanical.solver.branch_policy_b1` IMPLEMENTS it; parity tests extract the machine-readable blocks below and enforce COMPLETE-structure correspondence (constants, the local table, the array-order law, the whole-graph predicate, the equality-class construction). Drift anywhere is a red suite.
- **Self-contained by rule:** a policy id never incorporates another by reference. The reference-frame shapes G0/G1/G2 are RESTATED here verbatim in `skb-b1`'s own terms; `skb-b0` records remain governed by `skb-b0` forever and nothing here changes them.
- **The governing rule, inherited unchanged:** *a list of safe equations is not yet a safe system.* Branch freedom is a property of complete fact GRAPHS, never of isolated constraint signatures. This policy therefore admits whole graphs only, and every admitted graph carries a single-root proof (§5) — deriving, for every admitted member, the EXACT EMPTY witness set (§6).
- **What is new versus `skb-b0`:** non-construction PROFILE geometry (points, segments, bare circles) in a count-parameterized family, with `horizontal`/`vertical` admitted on profile segments under UNSIGNED non-collapse guards. What is NOT new: no dimensions, no witness measures, no ε — the catalog is still empty everywhere.

## 1. Constants

<!-- skb-b1:constants -->
```json
{
  "policy_id": "skb-b1",
  "solver_contract": "skb-c0",
  "weak_policy": "skb-0",
  "L_min_mm": 1e-9,
  "R_min_mm": 1e-9
}
```

- `L_min_mm` — the length-domain floor for every non-collapse guard (strictly-greater passes), applied to reference axes AND to every profile segment.
- `R_min_mm` — the positive floor for a circle radius (strictly-greater passes). It is `skb-b1`'s OWN valid-circle domain: the numeric floor below which a positive radius is indistinguishable from collapse, exactly parallel to `L_min_mm` for displacements. It is **not** a witness-error threshold and carries no forward-compatibility claim — a later policy admitting curve CONSTRAINTS must establish its own evidenced, scale-aware domain.
- **There is NO degeneracy threshold ε under `skb-b1`**: this policy's catalog derives the EMPTY witness set for every admitted graph (§5/§6), so no witness measure is normative under this id. Measure schemas, ε, and their vectors remain DRAFT material for the first non-empty policy — see [`witness-kinds-draft.md`](witness-kinds-draft.md).

## 2. Layer 1 — the local signature table (necessary, never sufficient)

<!-- skb-b1:local-table -->
```json
{
  "entity_kinds": ["point", "line", "circle"],
  "construction_only": false,
  "blocks": ["reference", "profile"],
  "fact_kinds": {
    "fix": {"signature": ["point"], "class": "strong", "blocks": ["reference"]},
    "horizontal": {"signature": ["line"], "class": "strong", "blocks": ["reference", "profile"]},
    "vertical": {"signature": ["line"], "class": "strong", "blocks": ["reference", "profile"]},
    "fix_param": {"signature": ["parameter"], "class": "weak-completion-only"}
  },
  "dimension_kinds": {}
}
```

Block membership is carried by the per-entity `construction` flag: `construction: true` entities form the REFERENCE block, `construction: false` entities the PROFILE block. Everything outside this table — every other entity kind, constraint kind, any dimension — is typed out-of-domain for `skb-b1` and refused at all five enforcement surfaces (§7). Passing layer 1 admits NOTHING by itself; layer 2 is the authority.

## 3. Layer 2 — the whole-fact-graph admission predicate

An admitted graph is a REFERENCE block (§3.1) plus a non-empty PROFILE block (§3.2) satisfying the joint rules (§3.3). The array-order law:

<!-- skb-b1:array-order -->
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

ENTITY and STRONG-FACT arrays are semantically UNORDERED — every permutation of the same **id-addressed** graph admits identically and hashes identically (canonical identity normalizes them). The WEAK-COMPLETION array is CANONICALLY ORDERED (`w01, w02, …` in canonical parameter order); a permuted weak array refuses. This law governs PERSISTED, id-addressed graphs only; it makes no claim about id ALLOCATION for a request that carries client keys instead of ids (see A4's allocation order).

### 3.1 The reference block (restated verbatim in `skb-b1`'s terms)

<!-- skb-b1:reference-predicate -->
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

Reference-block guards are SIGNED (`PX.x − O.x > L_min_mm`, `PY.y − O.y > L_min_mm`): the reference axes are DIRECTED construction lines whose named positive directions are canonical. Exactly one `fix` exists in the whole graph and it names a reference point.

### 3.2 The profile block — a count-parameterized family

<!-- skb-b1:profile-predicate -->
```json
{
  "entities": {
    "points":   {"type": "point",  "construction": false, "count": "K >= 0"},
    "segments": {"type": "line",   "construction": false, "count": "M >= 0",
                 "refs": {"start": "profile point", "end": "profile point"}},
    "circles":  {"type": "circle", "construction": false, "count": "C >= 0",
                 "refs": {"center": "profile point"}, "parameters": ["radius"]}
  },
  "strong_facts": {
    "axis": {"kinds": ["horizontal", "vertical"], "signature": ["profile segment"],
             "max_per_segment": 1}
  },
  "rules": [
    "presence: M + C >= 1",
    "reference_integrity: every segment start/end and every circle center resolves to a declared profile point",
    "no_orphans: every profile point is a segment endpoint or a circle center",
    "topological_distinctness: a segment's start and end refs are different entity ids",
    "geometric_non_collapse_segment: effective euclidean length > L_min_mm for EVERY segment (constrained or not)",
    "geometric_non_collapse_circle: effective radius > R_min_mm for EVERY circle",
    "no_duplicate_edges: an unordered endpoint-id pair appears at most once",
    "branch_vertices_admitted: a profile point may have any incidence degree",
    "exact_canonical_completion: the weak set equals the exact skb-0 enumeration for the admitted strong graph"
  ]
}
```

Guards run on EFFECTIVE values — the weak record's persisted magnitude for a weak-fixed coordinate and the authored nominal otherwise: the values the solve will actually pin, never unvalidated nominals. Profile guards are **UNSIGNED** (`|Δ| > L_min_mm`): a drawn segment has no canonical direction, and §5 shows uniqueness does not require one. Segment `start`/`end` order remains identity-bearing payload that canonicalization never reorders.

**Closure is NOT a policy concern.** Open polylines, branch vertices, multiple components, and self-intersecting profiles are all ADMITTED here: this policy answers whether the constrained graph regenerates uniquely. Whether a profile is a valid extrudable contour is a downstream CONSUMER predicate, evaluated at the consumption gate.

### 3.3 Joint rules

<!-- skb-b1:joint-rules -->
```json
[
  "block_independence: no entity is shared between blocks and no fact references entities from both blocks",
  "single_anchor: exactly one fix in the whole graph, naming a reference point",
  "no_dimensions: the dimension array is empty",
  "weak_targets_are_free_scalars: every weak record targets a scalar of the graph and no scalar is targeted twice",
  "empty_witness_set: any present witness is EXTRA and refuses"
]
```

## 4. The equality-class construction (normative; supports §5 and the rank cross-check)

<!-- skb-b1:equality-classes -->
```json
{
  "scalars": "for each profile point by entity id: x then y; for each profile circle by entity id: radius",
  "unions": {
    "horizontal": "P.y ~ Q.y for the segment's endpoints P,Q",
    "vertical":   "P.x ~ Q.x for the segment's endpoints P,Q"
  },
  "singletons": "every circle radius is its own class",
  "class_order": "by the lexicographically smallest member scalar id (<entity_id>.<parameter>)",
  "basis_vector": "the integer indicator of the class members",
  "cross_check": "the number of classes MUST equal the number of committed weak-completion records"
}
```

This is an exact, deterministic, integer basis of `ker(A)` for this family — no SVD/QR and no implementation-chosen basis anywhere. The cross-check is a real drift detector: disagreement is a typed internal-inconsistency refusal, never a silently different result.

## 5. The single-root proofs

**Reference block.** `G0`: `fix(O)` determines both coordinates; zero freedom. `G1`: `fix(O)` pins `O`; the weak record pins `PX.x` with the signed guard `PX.x − O.x > L_min > 0`, so the direction is defined and cannot flip; `horizontal(AX)` demands unit-direction `u_y = 0`, i.e. the single unknown `PX.y = O.y` — one linear equation, one root. `G2`: G1's argument plus, symmetrically, `PY.y` weak-pinned with its signed guard and `vertical(AY)` giving the unique `PY.x = O.x`; the two sub-systems share only the fully-fixed `O`. Unique root. ∎

**Profile block (uniform in K, M, C, |A|).** Let `x ∈ R^n` be the profile scalars (`2K` point coordinates plus one `radius` per circle), `A x = 0` the exact incidence equations of the admitted axis facts, and `E x = c` the coordinate rows selected by `skb-0`.

1. At a valid solved snapshot each normalized axis residual row has the same local row space as its incidence row: the guarded denominator is finite and non-zero there, so `(Q.y − P.y)/‖Q − P‖ = 0 ⟺ Q.y − P.y = 0` (and symmetrically for `vertical`). This is the safe ONE-WAY implication — no claim is made that the normalized residual is total over every live solver iterate.
2. `skb-0` accepts a coordinate row only when the rank rises by exactly one and stops at zero DoF, hence `rank([A; E]) = n`: **FULL COLUMN RANK**, regardless of redundant strong rows. Axis facts need NOT be independent — three `horizontal` segments `P-Q`, `Q-R`, `R-P` contribute three rows of rank two — and the theorem does not require them to be.
3. The accepted snapshot satisfies `[A; E] x = [0; c]`; a consistent system of full column rank has EXACTLY ONE solution.
4. Every DEFINED root of the original normalized residual system also satisfies `A x = 0` and the committed weak coordinate rows, so any such root IS that unique snapshot; the snapshot satisfies the geometric guards. ∎

**Composition.** Block independence (§3.3) makes the Jacobian block-diagonal in the unknowns: two uniquely-solvable blocks sharing no unknowns compose to a uniquely-solvable system. ∎

**Circles.** A bare circle introduces only its `radius` scalar plus its referenced centre point and NO nonlinear strong equation; exact completion pins all three scalars, so the same argument applies unchanged and the family stays linear in the sense §5 requires.

**Where this proof stops (the boundary, stated so widening is never accidental).** Any of the following leaves the regime and requires a NEW policy id with a real (non-empty) catalog: any `length`/`distance`/`angle`/`radius` DIMENSION (quadratic — the mirror pair); `point_on` against a circle or arc; `tangent` / `tangent_at`; `equal`; arc entities; `coincident` to an arc endpoint; `parallel`/`perpendicular` between two free lines (bilinear in two unknown directions). `point_on` against a FULLY-FIXED line remains linear and is the cheapest future widening — named, not taken.

## 6. The catalog — a total function to an EXACT set

For every admitted graph the derived witness-descriptor set is **∅** — an explicit result of §5's proofs, not a default. Decode and commit therefore reject on a `skb-b1` record: any present witness (EXTRA), any duplicate, and — vacuously here — any missing required descriptor. The exact-set rule is what makes "complete witness set" executable and keeps recipe identity unperturbable by valid-looking extras.

## 7. Enforcement

The five surfaces — mechanical **encode**, **decode**, **handler**, **evaluator**, and the Studio **decoder** — all consult this one policy (layer 1 + layer 2 + §6): out-of-table signatures, non-matching graphs, invalid weak records, failed guards, and witness-set violations refuse typed at every surface. Required negative fixtures include BOTH kinds: layer-1 failures (a dimension; an arc; a `tangent`) AND layer-2-only failures that PASS layer 1 — an empty profile block; a segment whose endpoints are the same id; a zero-length UNCONSTRAINED segment; a circle with `radius <= R_min_mm`; an orphan profile point; a duplicate (and reversed-duplicate) edge; two axis facts on one segment; a fact spanning both blocks; a weak set that is not the exact canonical completion; a present witness. Required POSITIVE fixtures include the redundant chain and cycle (`P-Q`, `Q-R`, `R-P` all horizontal; a closed rectangle) so strong-row independence is never assumed.

*skb-b1 ends. One anchored reference frame, an unbounded family of drawn lines and circles that snap only to the axes, every remaining coordinate pinned by the frozen completion — and still not one measure worth freezing.*
