"""
Extract the white paint areas from a Revell painting-guide view and save them as
model-space polygons (mm), for colour.py.

  python tools/white_regions.py VIEW OUT.json --refs hawk/tools/refs.json [--erode 5]

VIEW is a key in the refs JSON (default tools/refs.json). White = inside the aircraft silhouette and plain
paper-white after a small blur (the stipple is grey). Writes {"rings": [[[h, v], ...], ...]}
in the view's model axes, plus OUT.png showing the mask over the drawing.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage as ndi
from skimage import measure

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("view"); ap.add_argument("out")
ap.add_argument("--erode", type=int, default=5, help="px kept clear of the outline")
ap.add_argument("--min-area", type=float, default=1.5, help="mm2; smaller blobs are dropped")
ap.add_argument("--thresh", type=int, default=228)
ap.add_argument("--refs", default=str(Path(__file__).resolve().parents[1] / "tools" / "refs.json"))
a = ap.parse_args()
ref = json.load(open(a.refs))[a.view]
A = np.array(ref["affine"], float)
x0, y0, x1, y1 = ref["crop"]
im = Image.open(ROOT / ref["image"]).convert("L").crop((x0, y0, x1, y1))
g = np.asarray(im.filter(ImageFilter.GaussianBlur(3.0)))
dark = np.asarray(im.filter(ImageFilter.GaussianBlur(5.0))) < 215
dark = ndi.binary_closing(dark, iterations=6)
lab, n = ndi.label(dark)
sil = lab == (1 + int(np.argmax(ndi.sum(dark, lab, range(1, n + 1)))))
sil = ndi.binary_fill_holes(sil)
inner = ndi.binary_erosion(sil, iterations=a.erode)
white = (g > a.thresh) & inner
white = ndi.binary_opening(white, iterations=1)
white = ndi.binary_closing(white, iterations=2)
# page px -> model (h, v)
Ainv = np.linalg.inv(np.vstack([A, [0, 0, 1]]))
mmpp = 1.0 / abs(A[0][0] or A[0][1])
rings = []
for c in measure.find_contours(np.pad(white.astype(float), 1), 0.5):
    r, k = c[:, 0] - 1 + y0, c[:, 1] - 1 + x0
    hv = (Ainv @ np.vstack([k, r, np.ones_like(k)]))[:2].T
    area = 0.5 * abs(np.dot(hv[:, 0], np.roll(hv[:, 1], 1)) - np.dot(hv[:, 1], np.roll(hv[:, 0], 1)))
    if area >= a.min_area:
        rings.append(hv[::2].round(3).tolist())
json.dump({"view": a.view, "axes": ref["axes"], "rings": rings}, open(a.out, "w"))
over = np.stack([np.asarray(im)] * 3, -1).copy()
over[white] = [255, 60, 60]
Image.fromarray(over).reduce(2).save(Path(a.out).with_suffix(".png"))
print(f"{len(rings)} rings -> {a.out}")
