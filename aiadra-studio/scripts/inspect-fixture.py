"""Quick diagnostic: list edge polylines in the dev fixture (not shipped)."""
import json
from pathlib import Path

d = json.load(open(Path(__file__).parent.parent / "dev-fixtures" / "display.json"))
for e in d["render"]["edges"]:
    p = e["polyline"]
    n = len(p) // 3
    print(f"{e['edge_id']:48s} kind={e['kind']:8s} pts={n:3d} "
          f"first=({p[0]:.1f},{p[1]:.1f},{p[2]:.1f}) last=({p[-3]:.1f},{p[-2]:.1f},{p[-1]:.1f})")
print("faces:", [f["face_id"] for f in d["render"]["faces"]])
