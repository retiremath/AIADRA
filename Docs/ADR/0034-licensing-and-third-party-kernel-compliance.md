# ADR/0034 — Licensing & third-party-kernel compliance

## Frontmatter

- **Status:** Accepted (strategic decision) — 2026-06-04 (arc 20260603-4; two-round convergence Claude1 + Codex1 / Claude2). **Decision/scope ADR.** Per Codex1 N4, the close-state is explicit: **strategic decision ACCEPTED; legal text PENDING; repository implementation PENDING; CI enforcement PENDING.** The file/CI/legal implementation is a **defined follow-up arc**.
- **What it is:** AIADRA's open-source **licensing posture** — public license, contributor agreement, dependency-license policy, and the third-party-kernel (OCCT/LGPL) compliance framework. Informed by a verified deep-research pass (25 claims, 0 refuted, all 3-0).
- **NOT final legal advice.** Carries an explicit OSS-attorney-review list (§ Attorney review).
- **Driven by Petre's goals** (priority order): (1) maximize free/open adoption; (2) prevent large CAD vendors appropriating AIADRA into proprietary/SaaS products without giving back (the stack is trivially SaaS-adaptable); (3) preserve the owner's ability to relicense/sell a proprietary version or accept an acquisition, unblocked by dependency licenses.
- **Gating:** this decision **clears the Display & UX rendering-foundation gate** ([ADR/0033](0033-studio-display-ux-vision.md) D11). No schema/bundle/`aiadra-core`-version/Glossary change.

## §0 — Verified facts (deep-research; sources in References)
OCCT = **LGPL-2.1-only + "OCCT Exception 1.0"**, no "or later" (exception = a narrow header-file permission; OCCT binaries stay LGPL-2.1). **`occt-import-js` is itself LGPL-2.1** (not permissive). **`cadquery-ocp`/OCP = Apache-2.0 wrapper bundling LGPL OCCT.** **AGPLv3 can lawfully link LGPL-2.1** (LGPLv2.1 is GPLv3-compatible). **AGPL + CLA dual-licensing is legally sound.** **Permissive + LGPL-only dependencies preserve a future proprietary product**; a GPL/AGPL dependency would foreclose it. **AGPL §13 deters but does not fully foreclose SaaS appropriation** (only *modified* network deployments must offer source).

## Decisions

### D1. Public license: **`AGPL-3.0-only`** (SPDX-pinned), uniform across AIADRA-owned packages
The strongest available network-copyleft; §13 is the lever against modified-SaaS appropriation. **Pinned `AGPL-3.0-only`** (not `-or-later`) for stewardship/relicensing control (Codex1 N2; counsel may revisit `-or-later` for future-version flexibility). Uniform across `aiadra-core` + the engine/Studio packages — a permissive-core split is **rejected** (weaker protection; the dependency policy D3 already preserves sellability).

**Honest framing (Codex1 N1):** AGPL deters proprietary *modified* network services and preserves public-source reciprocity; it does **not** prevent someone hosting an *unmodified* AGPL service. The **CLA + commercial-license path (D2) is the stronger practical lever** against vendor appropriation — a vendor embedding AIADRA proprietarily must buy a commercial license regardless.

### D2. Contributor agreement: **non-exclusive license-back CLA (Qt-style)**; assignment is the documented fallback
Every contributor grants the AIADRA steward (Petre / a holding entity) a **broad, irrevocable, non-exclusive copyright license to relicense their contributions under any terms**, while the contributor **keeps ownership**. This enables selling proprietary commercial licenses (the dual-license model + the protection lever) and a typical acquisition. **Copyright assignment** is documented as the fallback *only if* exclusive-title acquisition value is judged to outweigh contributor friction (Codex1 N3) — recommended default is **license-back**. **Petre confirms license-back vs assignment by the implementation arc; Claude recommends license-back.** **No external code contributions are accepted until the entity, CLA text, signing/record process, and contributor workflow are in place** (Codex1 N3).

### D3. Dependency-license policy: **SPDX/category-based and graph-validated** (absorbs Codex1 B1)
The prose "MIT/BSD/Apache/LGPL only" is replaced — it didn't match the real tree (the Studio lockfile already carries `ISC`, `BlueOak-1.0.0`, `CC-BY-4.0`, `(MIT OR CC0-1.0)`; e.g. `minimatch`=BlueOak, `type-fest`=(MIT OR CC0-1.0), `caniuse-lite`=CC-BY-4.0). The policy is an **SPDX table** over two axes:
- **Dependency classes:** `runtime` · `bundled` · `dev/build` · `test` · `data-only` (compliance obligations follow what is *shipped/linked*, not dev-only tooling).
- **SPDX buckets:** `allowed` · `allowed-with-notice` · `needs-review` · `denied`.

**Principle:** *permissive + weak-copyleft dependencies only; no strong-copyleft (GPL/AGPL) in shipped or linked dependency graphs without explicit owner/legal approval.* (Note: AIADRA's *own* code being AGPL is fine — this constrains *dependencies*.)

**Initial classifications** (to finalize in the implementation arc): MIT/BSD/Apache-2.0/ISC/0BSD/Unlicense/CC0-1.0/BlueOak-1.0.0 → `allowed`; **LGPL-2.1/-3.0 → `allowed-with-notice`** (carries the relink/NOTICE obligation, D4); CC-BY-4.0 → `allowed-with-notice` for `data-only` deps (e.g. `caniuse-lite`), `needs-review` if it ever reaches linked code; **GPL/AGPL/SSPL → `denied`** in shipped/linked graphs; unknown/`needs-review` → block until classified.

**Enforceable artifact (implementation arc):** the SPDX table + a **graph scan of npm AND Python, direct + transitive**, generating a reviewable **license report / SBOM + NOTICE inputs**, with **CI that fails only on `denied` or unreviewed** licenses (not on harmless spelling/category differences).

### D4. OCCT/LGPL compliance: **artifact-level** (absorbs Codex1 B2)
"Point to source + reproducible build" is **not** a blanket answer; compliance follows the **distributed artifact**. Enumerate each distribution form and its obligations:

| Distribution form | Conveys LGPL/combined? | Compliance materials required |
|---|---|---|
| **Source repo (GitHub)** | refers to deps, doesn't convey binaries | THIRD-PARTY-NOTICES + license texts + version pins |
| **npm / dev build** | dev `occt-import-js` (LGPL WASM) | NOTICE + source link; dev-only, but documented |
| **Packaged Electron desktop** | **yes — bundles `occt-import-js` LGPL WASM (static)** | notices + exact source/mirror + build scripts + toolchain versions + any patches + **relink/rebuild materials** + replacement instructions |
| **Python package / wheel** | OCCT shared libs via `cadquery-ocp` (dynamic) | notices + source links + **confirm OCCT libs remain user-replaceable in the SHIPPED form**, not just a dev venv |
| **Bundled installer / archive** | inherits the above | the union of the above, per bundled artifact |

**Static WASM is the high-risk case** (static combination can trigger relink obligations differing from dynamic linking). **Do NOT assert the planned static-WASM `occt-import-js` posture is sufficient until attorney review confirms the concrete source/relink package** (Codex1 B2 / Q4). OCCT is used **unmodified** as a library (if ever modified, those changes are LGPL).

### D5. The kernel boundary contains the obligations (reinforced, unchanged)
OCCT lives only in the kernel-using packages (`aiadra-mechanical`, `aiadra-studio`), never in `aiadra-core` (kernel-neutral per [ADR/0027](0027-aiad-positioning-and-native-engine-posture.md)/[ADR/0028](0028-native-engine-implementation-contract.md)). LGPL obligations are contained to those packages; `aiadra-core` is AGPL with no LGPL deps. **Native-engine-boundary watch (Codex1):** the dependency policy (D3) must *prove* `aiadra-core` stays kernel-neutral, and each shipped artifact must carry its own LGPL compliance package (D4).

### D6. Implementation is a defined follow-up arc (Codex1 Q5/N4)
This arc closes the **strategic decision**. A follow-up **"Licensing implementation"** arc delivers, with B1/B2 preserved as its close conditions: the SPDX policy table + npm/Python graph scan + SBOM + NOTICE + the SPDX-aware CI check; the per-artifact compliance materials (D4) + the **attorney confirmation** of the static-WASM package; the root `LICENSE` (`AGPL-3.0-only`) + SPDX headers + `THIRD-PARTY-NOTICES` + `CONTRIBUTING.md`/CLA; and the **copyright-holding entity setup** (before any external contribution lands). Legal text precedes the repository files (N4).

### D7. Gating resolution
ADR/0034 (decision) **clears the Display rendering-foundation gate.** The foundation's canonical lane is **engine-side OCCT (`cadquery-ocp`, dynamic-link — the cleaner LGPL case)** per ADR/0033 D4; `occt-import-js` static-WASM is already shipped (its artifact-level compliance + attorney confirmation are tracked in the D6 follow-up). **Attorney confirmation of the static-WASM package is a prerequisite for public distribution/release, not a blocker on starting the foundation build.**

## Attorney review (mandatory before binding the choice; carry verbatim)
1. `occt-import-js` exact license/version + LGPL variant ("or later"?).
2. Static-WASM LGPL **relink artifacts** — the minimum concrete package for the packaged Electron desktop.
3. **License-back vs assignment** + the copyright-holding **entity setup** (for a clean acquisition / exclusive title).
4. The **AGPL §13 unmodified-SaaS gap** — confirm acceptable given the commercial-license lever.
5. The **CLA text + signing/record process** (use a vetted template).
6. **Commercial/proprietary KB-pack distribution + the data-not-code / AGPL posture** (added 2026-07-11 per [ADR/0041 D4](0041-kb-interchange-and-ecosystem.md)) — confirm that a KB pack consumed **as data** by the AGPL engine may carry its **own independent license** (incl. commercial/proprietary) without triggering copyleft, and pin the **threshold at which pack contents become "code"** requiring D3 dependency-policy review (executable validators/generators/templates/plugins are out of data-only scope). A **release-prerequisite confirmation**, not a build blocker.

## Consequences
- AIADRA's public license is **`AGPL-3.0-only`** with a **license-back CLA** — open + adoption-friendly, protective (modified-SaaS reciprocity + the commercial-license lever), and **sale/acquisition-optional**.
- The dependency policy becomes an **SPDX-category, graph-validated, CI-enforced** artifact (not a literal short list) — preserving the proprietary-relicense path while matching the real tree.
- OCCT/LGPL compliance is **per-distributed-artifact**, with the **static-WASM desktop package the explicit attorney-gated item**.
- A **Licensing implementation arc** follows (files/CI/SBOM/entity/attorney); the rendering foundation is **unblocked to build** in the meantime.

## Alternatives rejected
- **Permissive/weak-copyleft `aiadra-core` + AGPL engines** (per-component split) — rejected (D1): weaker protection, no benefit the dependency policy doesn't already give.
- **Copyright assignment CLA as default** — rejected as default (D2): adoption-hostile; license-back preserves the same commercial lane. Kept as a documented fallback.
- **A literal "MIT/BSD/Apache/LGPL only" dependency list** — rejected (D3): doesn't match the real tree; would fail CI or breed exception sprawl.
- **"Point to source + reproducible build" as a blanket LGPL answer** — rejected (D4): compliance must follow each distributed artifact; static-WASM needs attorney-confirmed packaging.
- **GPL/AGPL dependencies** — denied (D3): would foreclose the proprietary-relicense path.

## References
- Deep-research sources: SPDX `OCCT-exception-1.0`; `Open-Cascade-SAS/OCCT` `OCCT_LGPL_EXCEPTION.txt`; `dev.opencascade.org/resources/licensing`; `npmjs.com/package/occt-import-js` + `kovacsv/occt-import-js`; `github.com/CadQuery/OCP` + `pypi.org/project/cadquery-ocp`; `gnu.org/licenses/gpl-faq.html`, `license-list.html`, `agpl-3.0.en.html`; `qt.io/community/legal-contribution-agreement-qt`; `spdx.org/licenses`.
- [ADR/0027](0027-aiad-positioning-and-native-engine-posture.md) (third-party kernels as libraries) · [ADR/0028](0028-native-engine-implementation-contract.md) (kernel-using ecosystem packages) · [ADR/0033](0033-studio-display-ux-vision.md) (the gated Display strand) · [Manifesto](../Manifesto.md) P11.
