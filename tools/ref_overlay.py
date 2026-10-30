"""
Draw the model's outline over a reference drawing, to check the shape.

  python tools/ref_overlay.py OUT_DIR/assembled side docs/overlay_side.png
  python tools/ref_overlay.py OUT_DIR/assembled plan docs/overlay_plan.png --skip stand,gear,wheel,prop

The view's image, calibration and crop come from tools/refs.json. To calibrate a
new drawing: pick two or three features you can locate both in the model (mm)
and on the page (px), solve for the 2x3 affine, then iterate on this overlay
until the outlines sit on the lines.
"""
import argparse
import glob
import json
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("stl_dir", help="folder of assembled-frame STLs")
ap.add_argument("view", help="key in refs.json")
ap.add_argument("out")
ap.add_argument("--only", default="", help="comma list: keep parts whose name contains one of these")
ap.add_argument("--skip", default="", help="comma list: drop parts whose name contains one of these")
ap.add_argument("--refs", default=str(ROOT / "tools" / "refs.json"))
a = ap.parse_args()

ref = json.load(open(a.refs))[a.view]
A = np.array(ref["affine"], float)
ax = ["xyz".index(c) for c in ref["axes"]]
im = Image.open(ROOT / ref["image"]).convert("RGB")
x0, y0, x1, y1 = ref["crop"]
im = im.crop((x0, y0, x1, y1))
d = ImageDraw.Draw(im)
only = [s for s in a.only.split(",") if s]
skip = [s for s in a.skip.split(",") if s]

polys = []
for f in sorted(glob.glob(f"{a.stl_dir}/*.stl")):
    n = Path(f).stem
    if (only and not any(s in n for s in only)) or any(s in n for s in skip):
        continue
    tri = trimesh.load(f).triangles[:, :, ax]
    ps = [Polygon(t) for t in tri]
    polys.append(unary_union([p.buffer(0.02) for p in ps if p.area > 1e-4]))
u = unary_union(polys)
for g in getattr(u, "geoms", [u]):
    hv = np.asarray(g.exterior.coords)
    uv = (A @ np.c_[hv, np.ones(len(hv))].T).T - [x0, y0]
    d.line([tuple(p) for p in uv], fill=(255, 0, 255), width=3)
im.save(a.out)
print("saved", a.out)
