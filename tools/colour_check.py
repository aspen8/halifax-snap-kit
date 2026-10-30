"""
Check that a surface seen from one direction shows only the expected colours,
e.g. no camo flecks on a black underside.

  python tools/colour_check.py OUT_DIR/halifax_colour_preview.glb --from below --expect 1C1C1C
  python tools/colour_check.py preview.glb --from above --expect 6B5638,3F4B2E --skip stand

Casts a grid of rays at the coloured preview (from colour.py) and reports which
colours the first hit lands on. Stray hits in small numbers usually sit on joint
faces hidden after assembly; check where they are before chasing them.
"""
import argparse

import numpy as np
import trimesh

ap = argparse.ArgumentParser()
ap.add_argument("glb")
ap.add_argument("--from", dest="side", choices=["below", "above", "port", "starboard"], default="below")
ap.add_argument("--expect", required=True, help="comma list of hex colours allowed")
ap.add_argument("--step", type=float, default=0.5, help="ray spacing (mm)")
a = ap.parse_args()

scene = trimesh.load(a.glb)
meshes, cols = [], []
for g in scene.dump():
    meshes.append(g)
    cols.append("%02X%02X%02X" % tuple(g.visual.main_color[:3]))
allm = trimesh.util.concatenate(meshes)
owner = np.concatenate([np.full(len(m.faces), i) for i, m in enumerate(meshes)])
lo, hi = allm.bounds
axis, sign = {"below": (2, -1), "above": (2, 1), "port": (1, -1), "starboard": (1, 1)}[a.side]
others = [i for i in range(3) if i != axis]
g0 = np.arange(lo[others[0]], hi[others[0]], a.step)
g1 = np.arange(lo[others[1]], hi[others[1]], a.step)
A, B = np.meshgrid(g0, g1)
o = np.zeros((A.size, 3))
o[:, others[0]], o[:, others[1]] = A.ravel(), B.ravel()
o[:, axis] = (hi if sign > 0 else lo)[axis] + sign * 10
d = np.zeros_like(o)
d[:, axis] = -sign
tri, ray = allm.ray.intersects_id(o, d, multiple_hits=False)[:2]
hit = np.array([cols[owner[t]] for t in tri])
expect = {c.strip().upper().lstrip("#") for c in a.expect.split(",")}
u, n = np.unique(hit, return_counts=True)
for c, k in zip(u, n):
    print(f"#{c}  {k:7d} rays  {'ok' if c in expect else 'UNEXPECTED'}")
bad = ~np.isin(hit, list(expect))
print(f"{bad.sum()} of {len(hit)} rays ({100 * bad.mean():.3f}%) hit an unexpected colour")
