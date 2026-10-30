"""
Report overlapping parts in the assembled model (and any non-manifold meshes).

  python tools/interference.py OUT_DIR/assembled [--min 0.5]

Anything above a few mm3 means two parts won't go together; fix by cutting one
from the other in the CAD.
"""
import argparse
import glob
import itertools
from pathlib import Path

import manifold3d as mf
import numpy as np
import trimesh

ap = argparse.ArgumentParser()
ap.add_argument("stl_dir")
ap.add_argument("--min", type=float, default=0.5, help="report overlaps above this (mm3)")
a = ap.parse_args()

M = {}
for f in sorted(glob.glob(f"{a.stl_dir}/*.stl")):
    m = trimesh.load(f)
    m.merge_vertices()
    man = mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices, np.float32),
                              tri_verts=np.asarray(m.faces, np.uint32)))
    if man.status() != mf.Error.NoError:
        print("NOT MANIFOLD", f, man.status())
    M[Path(f).stem] = (man, m.bounds)
for p, q in itertools.combinations(M, 2):
    (ma, ba), (mb, bb) = M[p], M[q]
    if np.any(ba[1] < bb[0]) or np.any(bb[1] < ba[0]):
        continue
    v = (ma ^ mb).volume()
    if v > a.min:
        print(f"{p:30s} x {q:30s} overlap {v:8.1f} mm3")
print("checked", len(M), "parts")
