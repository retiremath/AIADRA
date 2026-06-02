# aiadra-mechanical

The first **shippable AIADRA Native Engine** — mechanical Part authoring backed
by a real OCCT kernel (via the [`cadquery-ocp`](https://pypi.org/project/cadquery-ocp/)
binding). Scoped by [ADR/0031](../Docs/ADR/0031-aiadra-mechanical-v0.0.1-scope.md);
the destination of the Wedge spike series.

> **v0.0.1 is a minimal real-kernel mirror** of the Wedge-003 authoring loop:
> sketch → extrude → adjust depth → (remove) → release. It proves real-kernel
> integration, cross-platform packaging, and geometric **validity-gating** —
> not feature breadth.

## Install precondition (important)

`aiadra-core` is **not yet published to PyPI**, so it cannot be declared as a
pip dependency ([ADR/0031 D11]; Wedge-003 FRICTION_LOG §1). Install it
(editable) into your venv **first**, then install this package:

```bash
# from the AIADRA repo root, in a venv that already has aiadra-core installed:
python -m pip install -e ./aiadra-core            # the precondition
python -m pip install -e ./aiadra-mechanical      # pulls cadquery-ocp via wheel
```

`cadquery-ocp==7.9.3.1.1` is pinned (selected + frozen during the packaging
smoke test on win_amd64 / CPython 3.12). It ships prebuilt wheels for
manylinux / macOS / Windows. If a platform lacks a usable OCP wheel, that gap
is recorded as packaging friction and follows the ADR/0031 D4 fallback route —
**never** a silent swap to another binding.

## Engine + operations

- **engine_id:** `mechanical` (entry-point group `aiadra.native_engines`).
- **Operations** (driven via `aiadra_core.protocol.propose` / `modify`):
  - `mechanical.add_sketch_feature` — rectangle outer profile + optional circle hole
  - `mechanical.add_extrude_feature` — prism the sketch (depth is a canonical-unit `feature.parameters[]` record)
  - `mechanical.adjust_feature_parameter` — change a parameter (e.g. `depth_mm`); recomputes geometry
  - `mechanical.remove_feature` — remove feature(s) (batched-cascade capable)

```python
from aiadra_core.protocol import propose
propose(ws, kind="create_part", params={"number": "P-000001", "name": "Bracket"}).commit()
propose(ws, kind="mechanical.add_sketch_feature", params={"part_number": "P-000001",
    "primitives": [{"type": "rectangle", "x_mm": 0, "y_mm": 0, "width_mm": 20, "height_mm": 10},
                   {"type": "circle", "cx_mm": 5, "cy_mm": 5, "radius_mm": 2}]}).commit()
propose(ws, kind="mechanical.add_extrude_feature", params={"part_number": "P-000001",
    "sketch_feature_id": "feat_0001", "depth_mm": 5.0, "direction": "z+"}).commit()
```

## Geometry identity (ADR/0031 D6)

`geometry_ref.vault_ref` addresses the **canonical feature-recipe JSON bytes**
(sha256), stable across OCCT versions/platforms — NOT the evaluated BREP. OCCT
is a **validity gate**: it evaluates the recipe to a real solid and rejects
geometric garbage, but the evaluated solid is a per-process cache only
(`cache.py`), never persisted as Truth. Persisting evaluated artifacts (via the
schema's `derived_export` role) is a named v0.0.2 concern.

**Failure classes:** domain/payload errors (`depth_mm <= 0`, a circle outside
the rectangle, …) raise `TransactionError`; genuine kernel failures surface to
callers as `NativeEngineKernelError` (constructed by aiadra-core's dispatch
adapter, not this package).

## Tests

```bash
python -m pip install pytest
python -m pytest ./aiadra-mechanical/tests -q
```

See [FINDINGS.md](FINDINGS.md) for the v0.0.1 real-kernel findings (packaging,
tolerance, cache, recompute timing) that seed the v0.0.2 scope.
