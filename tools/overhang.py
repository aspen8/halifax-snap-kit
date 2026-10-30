"""
Print-pose sanity check: bed contact area and downward-facing overhangs per part.

  python tools/overhang.py OUT_DIR/print [--angle 50]

Large overhang areas well above the bed mean the part needs a different pose,
a chamfer, or supports.
"""
import argparse
import glob
from pathlib import Path

import numpy as np
import trimesh

ap = argparse.ArgumentParser()
ap.add_argument("stl_dir")
ap.add_argument("--angle", type=float, default=50.0, help="overhang angle from vertical (deg)")
a = ap.parse_args()

lim = -np.cos(np.radians(90 - a.angle))
for f in sorted(glob.glob(f"{a.stl_dir}/*.stl")):
    m = trimesh.load(f)
    n, c, ar = m.face_normals, m.triangles_center, m.area_faces
    down = (n[:, 2] < lim) & (c[:, 2] > 0.25)
    bed = (n[:, 2] < -0.99) & (c[:, 2] <= 0.25)
    zmax = c[down, 2].max() if down.any() else 0.0
    print(f"{Path(f).stem:30s} bed {ar[bed].sum():7.0f} mm2   overhang {ar[down].sum():6.0f} mm2"
          f"   (highest at z {zmax:.1f})")
