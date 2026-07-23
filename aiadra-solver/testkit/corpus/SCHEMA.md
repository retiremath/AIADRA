# SK-B corpus `skb-1` — the normative executable contract

Arc 20260715-3 · Claude4 revision (absorbing Codex3 B1–B4). This file + `generate_corpus.py` + the emitted case files + `coverage.md` ARE the acceptance contract. The generator is now a real checker: it computes numeric Jacobians, verifies rank-based DoF, EXECUTES the `skb-0` completion enumeration and the strong-supersession walk, proves declared redundancy/conflict rank facts, evaluates every solved geometry's residuals per canonical block, enforces evaluator existence for every accepted signature, and fails the build on any coverage regression. Hand-counted ledgers and hand-asserted ranks no longer exist in this arc.

## 1. The entity model and canonical parameter catalogue

| type | parameters (canonical order) | canonical unit | DoF |
|---|---|---|---|
| point | `x`, `y` | mm | 2 |
| line | — (refs `start`/`end` POINT ids) | — | 0 |
| circle | `radius` (+ ref `center` point id) | mm | 1 |
| arc | `radius`, `start_angle`, `end_angle` (+ ref `center`) | mm, deg, deg | 3 |

- **Stable parameter identity** = `{entity, parameter}` with parameter names from this catalogue — never a suffixed path. Units are fixed BY THE CATALOGUE, never per case; every numeric value in nominal/solved data is a plain number in the parameter's canonical unit. Dimension values keep field-typed units (`value_mm` / `value_deg`).
- Canonical entity order = lexicographic on `id`; canonical scalar order = entity order × the catalogue's parameter order. Solved maps are keyed `<entity>.<parameter>` (a DTO reporting path over the same identities).
- Arc endpoints `<arc>.start` / `<arc>.end` are DERIVED points (center + radius + angle).

## 2. The constraint domain table

| kind | operand signatures | eq | semantics |
|---|---|---|---|
| `coincident` | point,point · point,arc-endpoint | 2 | coordinate equality |
| `point_on` | point,line · point,circle · point,arc | 1 | on the SUPPORTING curve (infinite line / full circle); boundedness NOT constrained — `n-arcs` deliberately exercises a point beyond the segment |
| `horizontal` / `vertical` | line | 1 | normalized direction component = 0 |
| `parallel` / `perpendicular` | line,line | 1 | cross / dot of UNIT directions = 0 |
| `tangent` | line,circle · line,arc · circle,circle · circle,arc · arc,arc | 1 | SUPPORTING-curve tangency; side / internal-vs-external is BRANCH. Corpus-wide pin: every skb-1 curve-curve tangency is EXTERNAL (residual `|c₁c₂| − (r₁+r₂)`) |
| `tangent_at` | line,arc-endpoint | 1 | ENDPOINT tangency: the line direction is aligned with the arc's tangent direction at that endpoint (cross of unit direction and `(−sin θ, cos θ)`). **Why it exists (measured):** encoding a joined tangent joint as `coincident` + supporting-curve `tangent` is JACOBIAN-SINGULAR at the solution — the joint slides along the circle to first order (the original b-slot measured rank 14/18). `tangent_at` is the transversal sketcher-standard encoding (cf. FreeCAD's tangent-via-point) and is REQUIRED at joined tangent joints |
| `equal` | line,line (length) · circle,circle · circle,arc · arc,arc (radius) | 1 | mixed line×curve is OUT OF DOMAIN |
| `fix` | point | 2 | anchor class; fixes AT the point's nominal coordinates (the anchored frame = normalization frame) |
| `fix_param` | one catalogue parameter | 1 | the completion vocabulary — see §4; engine-INTERNAL, not one of the public user constraints |

Symmetric kinds (`coincident`, `parallel`, `perpendicular`, `tangent`, `equal`) store args sorted lexicographically; `point_on`, `tangent_at`, and `angle` keep authored order. Any (kind, signature) outside this table is rejected before solve with `out-of-domain(<id>)`.

## 2b. Canonical residual blocks (Codex3 B4)

Every residual belongs to exactly one block; both harnesses and the corpus checker use these definitions:

| block | unit | members | normalization |
|---|---|---|---|
| `length_mm` | mm | coincident components, point_on (signed line distance / `\|p−c\|−r`), tangent, equal, fix, fix_param on mm-parameters, distance, length, radius, diameter | none needed — all mm-commensurate |
| `direction` | dimensionless | horizontal/vertical (unit-direction component), parallel (cross of unit dirs), perpendicular (dot of unit dirs), tangent_at | line directions UNIT-NORMALIZED — scale-invariant by construction |
| `angle_deg` | deg | the `angle` dimension (CCW angle from dir(arg1) to dir(arg2), value ∈ [0,360), residual wrapped to (−180,180]), fix_param on deg-parameters | wrapping pinned |

`residual_max` is reported PER BLOCK: `{"length_mm": …, "direction": …, "angle_deg": …}`; the contract tolerance (1e-10 per block; corpus expected-geometry tolerance 1e-9 per block) applies blockwise. A max over raw heterogeneous equations does not exist anywhere in the contract.

## 3. The dimension table

| kind | operands | eq | semantics |
|---|---|---|---|
| `distance` | point,point · point,line | 1 | Euclidean / unsigned perpendicular distance to the supporting line; side & mirror are BRANCH |
| `length` | line | 1 | endpoint distance; direction sign is BRANCH |
| `angle` | line,line | 1 | see §2b; authored order semantic; no mirror branch from the dimension itself |
| `radius` / `diameter` | circle · arc | 1 | `value_mm` > 0; distinct kinds |

All corpus dimensions are `strength: "strong"`; weak facts are emitted only by the policy.

## 4. `weak_policy: "skb-0"` — the completion algorithm (checker-EXECUTED)

1. **Enumeration:** walk scalars in canonical order (§1).
2. **Acceptance:** tentatively add `fix_param(scalar = snapshot)` (snapshot = the branch-selected current geometry — in corpus terms the case's reference configuration); accept iff numeric Jacobian rank rises by exactly 1 (rank tolerance pinned: unit-normalized rows, pivot 1e-7).
3. **Termination:** stop at zero DoF; a full pass accepting nothing while DoF > 0 → typed `completion-stuck`.
4. **The persisted record** (Codex3 B3 — a valid persisted fact, not a path):

```json
{"id": "w01", "kind": "fix_param",
 "target": {"entity": "a1", "parameter": "radius"},
 "value": {"magnitude": 10.0, "unit": "mm"},
 "strength": "weak", "role": "driving", "visibility": "internal",
 "origin": {"category": "computed_result", "policy": "skb-0", "solver_contract": "skb-c0"}}
```

- `target` = stable parameter identity per the catalogue (ADR/0044 D3/D7); `value` is typed and its `unit` MUST equal the catalogue unit for that parameter (checker-enforced by construction).
- `origin` is the ADR/0044 D3 provenance (category from the ADR/0026 enum: `computed_result`), never rewritten; policy + solver-contract versions ride with it.
- `visibility: "internal"` pins the boundary Codex3 requested: `fix_param` IS the persisted completion fact (option b) but it is an ENGINE-INTERNAL completion constraint — it never extends the public user-constraint vocabulary; users author the seven public constraints + anchors, and completion output appears in persisted recipes as policy product. (`fix` remains public as the anchor.)

5. **Branch preservation:** fix-at-snapshot keeps the selected configuration by construction; P2 proves it at harness time.
6. **Strong supersession (checker-EXECUTED on d-under):** add the strong fact → walk existing weak additions in id order, remove each whose removal does not reduce rank → re-run 1–3 → the result must equal completion-from-scratch on the strong system (canonicality asserted by the generator).

## 5. The result DTO — canonical payload vs telemetry

```json
{
  "result": {
    "case_id": "…", "corpus_version": "skb-1", "solver_contract": "skb-c0",
    "classification": "well|under|over|rejected",
    "dof_strong": 0,
    "weak_completion": [ …records per §4… ],
    "solved": { "<entity>.<parameter>": number, … },
    "residual_max": {"length_mm": 0.0, "direction": 0.0, "angle_deg": 0.0},
    "branch_oracle_value": 1,
    "diagnostics": [ {"kind": "redundant|conflicting|non-convergent|out-of-domain|completion-stuck", "members": ["…"]} ]
  },
  "telemetry": { "wall_ms": …, "update_steps": …, "notes": "…" }
}
```

- **`dof_strong` is RANK-based** (numeric-Jacobian rank at the reference configuration); the raw arithmetic lives in `expected.ledger.net_count` as explanation only. Both are generator-verified.
- **Only `result` is compared.** Canonical serialization: keys sorted; numbers as Python's shortest round-trip representation with NO quantization (one rule across generator and both harnesses — Codex4 note 1; tolerance lives exclusively in the expectation comparison below); `-0.0` canonicalized to `0.0`; NaN/Infinity REJECTED by the serializer. The comparator FAILS on any field not in this schema.
- **Two distinct comparisons (Codex4 note 2):** (1) *expectation comparison* — candidate result vs corpus expectation: exact classification/diagnostics/weak-records/oracle, per-scalar solved tolerance 1e-9, per-block `residual_max` ≤ 1e-10; (2) *repeatability comparison* — repeat runs of the SAME candidate compared byte-for-byte on canonical `result` bytes (or under the predeclared variance envelope). Candidate floating-point geometry is never required to byte-match the corpus's decimal oracle.
- **`branch_oracle_value` is a required NULLABLE field** — `null` for non-branch fixtures (Codex4 note 3); the corpus's `branch_oracle: null` on such cases is the matching expectation.
- **Per-classification applicability:** `solved`/`residual_max`/`branch_oracle_value` required for `well`/`under`; MUST be null for conflicting `over`, `rejected`, and any result whose diagnostics include `non-convergent`; `over` with only `redundant` diagnostics still solves. `weak_completion` is `[]` unless classification is `under`.
- **Unsupported = failure:** a candidate that cannot express a case emits an in-schema rejection and FAILS that case unless the corpus expects rejection (only `h-outdomain`). Omitting a case fails the gate.
- **Repeatability:** 100 same-process + 10 fresh-process runs, byte-identical canonical `result`. The bounded-variance escape hatch is pinned up front: per-scalar drift ≤ max(1e-15 absolute, 1e-12 relative) across ALL 110 runs plus a written cause — never an after-the-fact waiver.
- **Environment record per run set:** OS/arch, compiler + toolset version, floating-point flags, dependency versions (Eigen etc.), Python/pybind11 ABI, serialization/rounding algorithm id.
- **The numeric solver contract `skb-c0`:** convergence tolerance 1e-10 per residual block (§2b); default `iteration_cap: 200`. **The counted event is the UPDATE STEP**: one accepted update of the full unknown vector followed by residual re-evaluation, enforced at the candidate-neutral harness boundary as a forced-stop budget (outer iterations for LM/DogLeg-class solvers). **`g-nonconv` pins `iteration_cap: 0`** — zero update steps allowed; since its pinned adversarial seed violates tolerance, EVERY candidate deterministically reports `non-convergent`. No escalation clause is needed; the case certifies the reporting path, which is its declared purpose. (The former 3-vs-2 inconsistency is resolved by this pin.)

## 6. Harness procedures

- **P1 permutation** *(checker-executed now)*: `i-permute` = pinned array-reversal of the underconstrained `d-under`; the generator runs `skb-0` on it and asserts the identical `w01` record.
- **P2 branch round-trip** *(harness-time — needs a live solver)*: for `c-bracket`/`j-branch-flip`: solve → persist `{branch_oracle_value, weak_completion, solved snapshot}` → perturb every nominal coordinate within the pinned in-file envelope (±2 mm, `python-random-uniform`, pinned seed, canonical-param order) → reload → re-solve → same oracle value.
- **P3 strong supersession** *(checker-executed now)*: d-under's in-file `supersession_test` — the generator performs the §4.6 walk and asserts the expected final weak set and canonicality.
- **P4 reload** *(harness-time)*: serialize → reload → re-solve every `well` case: byte-identical canonical `result`.

## 7. Coverage and terminal outcomes

- **Coverage gate:** `coverage.md` is generated from the domain tables; every accepted signature and entity type must be exercised by at least one positive (`well`/`under`) case; the generator FAILS on any gap. 14 cases currently; case count is not an architectural constraint.
- **Gate 2** (accepted by Codex3 as written): exact upstream revision + per-file content digests, modification set with patch history, file-level SPDX/copyright audit, the complete distributed-pair inventory (pybind11/Python ABI, compiler runtime, wheel, Eigen, Boost, anything else present), notices + corresponding source byte-matched to the distributed bytes, and a clean-machine rebuild→swap→corpus-retest against the PACKAGED artifact. Static-with-relink fallback carries its own evidence package + conditional decision. Attorney item release-gated.
- **Terminal outcomes:** `select PlaneGCS` · `select own-bounded` · `select hybrid` · `reject candidate <X>` · `conditional pending named evidence` (MANDATORY if Linux second-platform evidence is deferred; such an outcome may not claim ADR/0044 D4's full envelope and the ADR amendment must say so on its face). Rejected extraction work preserved with provenance. `wall_ms`/`update_steps` stay telemetry.
