"""Diagnostic: lift each iso HLR segment back to 3D and print endpoints (not shipped)."""
import json
import sys
from pathlib import Path

name = sys.argv[1] if len(sys.argv) > 1 else "iso"
d = json.load(open(Path(__file__).parent.parent / "dev-fixtures" / f"hlr-{name}.json"))
view = d["views"][0]
p = view["projector"]
O, R, U = p["origin"], p["right"], p["up"]
print("projector origin", O, "right", R, "up", U, "direction", p["direction"])
for i, s in enumerate(view["segments"]):
    pts = s["polyline_2d"]
    n = len(pts) // 2
    def lift(k):
        u, v = pts[2 * k], pts[2 * k + 1]
        return tuple(round(O[j] + u * R[j] + v * U[j], 2) for j in range(3))
    src = s["source"]
    tag = src.get("edge_id") or f"outline:{src.get('face_id')}#{src.get('index')}"
    print(f"[{i:2d}] {s['visibility']:7s} {s['edge_class']:7s} pts={n:3d} "
          f"start={lift(0)} end={lift(n - 1)}  {tag[:60]}")
