---
name: aiadra-manifesto
status: draft
version: 0.5
last_updated: 2026-07-28
---

# AIADRA Manifesto

> An open-source AI-native platform for product engineering.
> Probabilistic AI proposes. A deterministic core validates and records. Humans approve.

## What AIADRA is

AIADRA is an open-source platform for engineering real products — mechanical, electrical, software, procurement, verification, documentation — around a single source of truth designed from the ground up for AI-agent access.

AIADRA is an **AIAD platform** — AI-Augmented Design — a distinct system category from CAD. In CAD the computer is a tool; in AIAD, AI is a structural engineering participant (AI proposes; deterministic core validates; humans approve per P2 + P5). "Design" here is category-language for the whole product-engineering authoring loop, not CAD/drawing-only scope. See [ADR/0027](ADR/0027-aiad-positioning-and-native-engine-posture.md) for the full positioning.

AIADRA implements its own AIAD-native authoring engines per domain. These **Native Engines** use third-party kernels and libraries (OCCT for mechanical geometry; KiCad's reusable libraries for electrical; etc.) as dependencies, but never wrap third-party applications. The Product Truth Model owns truth; Native Engines produce content against it. Truth lives in the project's own Git repo and a pluggable blob vault; AIADRA Core runs locally and operates no shared services of its own. Existing tools like FreeCAD-the-application, KiCad-the-application, and Solvespace are studied as research material — for years of friction they have already resolved — but are not implementation dependencies.

The AI is treated as an engineering participant, not a chat panel. It inspects, queries, proposes, and explains through stable structured contracts. It never mutates released truth silently. A human always approves.

## Audience

Mechanical, electrical, and systems engineers; makers and small manufacturers; students; open-source hardware contributors; AI/design researchers; engineers who want scriptable, inspectable, transparent design tools. **Not** aimed at enterprise PLM replacement.

The **deliberate first community** is the open-source / DIY / 3D-print maker community (see Strategic horizons below): many of its members are engineers and technicians in their professional lives, and open tools have historically entered industry bottom-up through exactly this door.

## Principles (load-bearing)

1. **Single source of truth lives in AIADRA.** Tools synchronize with it; they do not own truth.
2. **AI proposes. Deterministic core decides.** Probabilistic output and engineering record are never mixed.
3. **Identity is UUID.** Filenames are storage, not truth.
4. **Design intent is first-class data.** Not "hole removed from cylinder" but "M8 clearance for MTR-0007 per REQ-014."
5. **Every AI action is a transaction.** Preview → validate → human approval → commit-or-rollback.
6. **AI modifies named engineering parameters first; raw geometry last.**
7. **Every fact carries provenance and uncertainty.** Released vs. computed vs. AI inference vs. assumption is always knowable.
8. **Released truth is immutable.** Changes require new revision + change order + impact analysis + approval.
9. **Geometry access is layered.** Engineering features → parametric features → sketch constraints → topological references → raw BRep, in that order of preference.
10. **History is event-based; current state is flat.** Sidecars hold current authoritative object state. Events record approved transitions and provenance. If they disagree, validation fails — neither silently wins.
11. **AIADRA Core hosts nothing.** Projects own their truth, infrastructure, identity, and access control. Future hosted services (registries, validators, shared libraries) belong to separate ecosystem projects, not to the core.
12. **Three-tier separation, on Git.** AIADRA inherits Windchill's Commonspace / Vault / Workspace separation, realized on Git (Commonspace) and pluggable blob storage (Vault). The developer's local clone plus live Native Engine sessions and Data Adapter processes form the Workspace.
13. **AI is Workspace-native.** It reads from the Workspace's local mirror of Commonspace, syncing first when staleness is unacceptable. It writes to Commonspace only through the change-order pipeline.

## Scale targets

AIADRA must be **architecturally compatible with large open-source product projects (Tier L) from day one**, and **operationally smooth at small-team scale (Tier M)**. The Wedge proves the architecture at solo scale (Tier S). Enterprise PLM (Tier XL) is out of scope by non-goal.

| Tier | Description | Examples |
|---|---|---|
| **S — Solo** | 1 developer, tens of parts | Maker designing a 3D-printed Arduino enclosure |
| **M — Small team** | 5–20 contributors, hundreds to thousands of parts | Most open-source hardware projects today |
| **L — Large OSS** | 50–500 contributors, tens of thousands of parts | Open-source EV, robotic arm, satellite, drone platform |
| **XL — Enterprise** | Out of scope — see Non-goals | Windchill / Teamcenter territory |

Scale-sensitive decisions fall into three buckets:

- **Decide early, validate with scale probes.** Settled in Ring 0; stress-tested against synthetic Tier-M / Tier-L data before committing in production. Examples: canonical on-disk format, UUID encoding and shardability, schema-versioning discipline.
- **Design with scale in mind; must not preclude.** The Ring 0–1 architecture must remain compatible with scale-time refinements. Examples: directory sharding by UUID prefix, event-log sharding strategy, acceleration cache structure, role-based change-order gating, Vault adapter pluggability.
- **Defer with acknowledgement.** Real Tier-L concerns; not blockers for Ring 0–4. Examples: distributed validation, multi-agent conflict resolution at high contributor counts, advanced cross-100k-object search, cryptographic signing of releases, derivation-graph queries at scale.

## Strategic horizons

Two horizons, one strategy (Petre's frame, 2026-07-28).

**Horizon 1 — geometry authoring for the maker beachhead (current phase).** AIADRA builds competent AIAD-native modeling — one feature at a time, benchmarked against the best interactive CAD — because users and AI agents both deserve real tools, and because nobody adopts an integration platform whose own modeling feels broken. The geometry breadth a maker needs (sketches, extrudes, revolves, holes, rounds; printable single parts and small assemblies) is reachable; the openness, the git-native substrate, and the AI participation are the draw no incumbent offers. This horizon imposes concrete obligations: painless install, honest STL/3MF/STEP export, and a print-minded workflow.

**Horizon 2 — the integrator.** AIADRA does not bet on out-modeling geometry kernels built over decades at billion-dollar cost. The long-term differentiator is **assemblies and mechanisms built from parts of many origins, exchanged as STEP**. Today every CAD system imports a STEP file as a "dumb" solid — a frozen shape stripped of interfaces, function, and intent — and every engineer re-derives, by hand, knowledge the original author already had. AIADRA's job is to make imported models **progressively less dumb**: schema-governed **interface facts** layered onto neutral geometry (mating surfaces, axes, thread specifications, kinematic pairs, connection semantics — at many levels), with provenance, so that human and AI participants assemble *function* rather than click faces. The analogy is what IFC/BIM did for architecture and what footprints-plus-netlists did for electronics: the semantic layer mechanical engineering never got. AI participation is what makes the layer affordable — recognizing threads, seats, and mating candidates on imported geometry is exactly the annotation labor that has kept such layers from existing.

**Claim discipline.** AIADRA does **not** promise parametric feature-tree interchange between CAD systems — a goal that has failed for forty years and is treated here as intractable. The claim is narrower and achievable: geometry travels neutral (STEP, as it already does); function, interfaces, and assembly semantics travel as AIADRA facts. A semantic envelope around neutral geometry — never a converter.

**The flywheel.** The two horizons are one strategy: makers assemble bought components — steppers, bearings, extrusions, fasteners — whose downloaded STEP models are semantically dead today. A community library of interface-annotated components is simultaneously the maker community's killer feature and the bootstrap of the interchange language. The beachhead feeds the layer; the layer rewards the beachhead.

Mechanism decisions for Horizon 2 (the interface-fact taxonomy, recognition contracts, the exchange-package profile) are **not** made in this document — each arrives through its own ADR when its ring is reached. The reference-import lane, the exchange-package design (arc 20260728-5), and cross-project identity (ADR/0008) are its first seeds.

## Non-goals

- **Not a Creo or SolidWorks clone.** Inspired by, not imitating.
- **Not "better FreeCAD UI."** A reskin would not justify this project's existence.
- **Not enterprise PLM.** Practical, open, understandable; not Windchill.
- **Not a chatbot bolted onto CAD.** Native structured AI access, not natural-language scraping.
- **Not a wrapper around any third-party application (modified or unmodified).** AIADRA implements its own AIAD-native authoring runtimes (Native Engines) per [ADR/0027](ADR/0027-aiad-positioning-and-native-engine-posture.md); third-party engineering applications are research material, not implementation dependencies. Third-party libraries and kernels (OCCT, KiCad libs) are dependencies via clean library APIs only.
- **Not silent AI mutation of models.** Every change is observable, reversible, and approved.

## About this document

This is a **working manifesto**, not a final text. It evolves as ADRs are written and prototypes meet reality. When this document and an ADR disagree, the ADR is canonical and the manifesto is stale until updated. Open architectural questions live in [OpenQuestions.md](OpenQuestions.md); resolved decisions live in `ADR/NNNN-*.md`.

Terms in this document (UUID, Released Truth, AIAD, Native Engine, Data Adapter, Commonspace, Vault, Workspace, etc.) are defined in [Glossary.md](Glossary.md).

Significant changes increment the version recorded in the frontmatter above; rationale lives in the relevant ADR.
