---
name: aiadra-manifesto
status: draft
version: 0.2
last_updated: 2026-05-17
---

# AIADRA Manifesto

> An open-source AI-native platform for product engineering.
> Probabilistic AI proposes. A deterministic core validates and records. Humans approve.

## What AIADRA is

AIADRA is an open-source platform for engineering real products — mechanical, electrical, software, procurement, verification, documentation — around a single source of truth designed from the ground up for AI-agent access.

Existing open-source tools provide the authoring substrate: FreeCAD/OpenCascade for mechanical, KiCad (planned) for electrical, Git for software, standard formats for the rest. AIADRA does not wrap these tools loosely. It modifies them so they expose their kernels natively and synchronize with AIADRA's Product Truth Model.

The AI is treated as an engineering participant, not a chat panel. It inspects, queries, proposes, and explains through stable structured contracts. It never mutates released truth silently. A human always approves.

## Audience

Mechanical, electrical, and systems engineers; makers and small manufacturers; students; open-source hardware contributors; AI/design researchers; engineers who want scriptable, inspectable, transparent design tools. **Not** aimed at enterprise PLM replacement.

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
10. **History is event-based.** Engineering decisions, lifecycle transitions, and approved changes are recorded as structured events. Current state remains directly inspectable.

## Non-goals

- **Not a Creo or SolidWorks clone.** Inspired by, not imitating.
- **Not "better FreeCAD UI."** A reskin would not justify this project's existence.
- **Not enterprise PLM.** Practical, open, understandable; not Windchill.
- **Not a chatbot bolted onto CAD.** Native structured AI access, not natural-language scraping.
- **Not an integration wrapper around unmodified tools.** Tools are modified to expose their kernels.
- **Not silent AI mutation of models.** Every change is observable, reversible, and approved.

## About this document

This is a **working manifesto**, not a final text. It is expected to evolve as ADRs are written and as prototypes meet reality. When this document and an ADR disagree, the ADR is canonical and this document is stale until updated.

Terms in this document (UUID, Released Truth, Domain Engine, etc.) are defined in [Glossary.md](Glossary.md).

The version above is `0.1`. Significant changes increment the version; the rationale lives in the ADR log.
