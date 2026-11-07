"""
Trace flat colour areas (e.g. a fin flag) from a colour painting guide onto a model region.

  python tools/trace_colours.py SPEC.json OUT.json [--res 0.15]

SPEC (JSON):
  image:   path (relative to the repo root)
  points:  [[[x, z], [u, v]], ...]   three or more model (h, v) -> image px pairs; an affine
           is fitted through them, so the drawing is stretched onto the model's own outline
  region:  [[x, z], ...]              model polygon to trace inside (e.g. the fin outline)
  palette: {"red": [r, g, b], "white": [...], "blue": [...]}   reference colours
  keep:    ["white", "blue"]          classes to write (the rest is the part's base colour)
  smooth:  mm, closing/opening radius that removes the drawing's thin lines (default 0.4)
  mask:    [[u0, v0, u1, v1], ...]    optional image boxes to ignore (watermarks, labels); they
           are filled from the nearest colour outside them

Writes {"classes": {name: [[[x, z], ...], ...]}} in model mm, and OUT.png for checking.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from matplotlib.path import Path as MP
from PIL import Image
from scipy import ndimage as ndi
from skimage import measure

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("spec"); ap.add_argument("out")
ap.add_argument("--res", type=float, default=0.15)
a = ap.parse_args()
S = json.load(open(a.spec))
im = np.asarray(Image.open(ROOT / S["image"]).convert("RGB")).astype(float)
P = np.array([p[0] for p in S["points"]], float)
Q = np.array([p[1] for p in S["points"]], float)
A, *_ = np.linalg.lstsq(np.c_[P, np.ones(len(P))], Q, rcond=None)      # (3, 2): [x z 1] @ A = [u v]
reg = np.array(S["region"], float)
x0, z0 = reg.min(0)
x1, z1 = reg.max(0)
r = a.res
X, Z = np.meshgrid(np.arange(x0, x1, r), np.arange(z0, z1, r))
inside = MP(reg).contains_points(np.c_[X.ravel(), Z.ravel()]).reshape(X.shape)
UV = np.c_[X.ravel(), Z.ravel(), np.ones(X.size)] @ A
u = np.clip(np.round(UV[:, 0]).astype(int), 0, im.shape[1] - 1)
v = np.clip(np.round(UV[:, 1]).astype(int), 0, im.shape[0] - 1)
pix = im[v, u].reshape(X.shape + (3,))
names = list(S["palette"])
pal = np.array([S["palette"][n] for n in names], float)
d = np.linalg.norm(pix[..., None, :] - pal[None, None], axis=-1)
cls = np.argmin(d, -1)
# optional "mask": [[u0, v0, u1, v1], ...] image boxes holding watermarks or labels. Inside each
# box only the pixels that stand out from their surroundings (the glyph itself) are ignored, so a
# colour edge running through the box keeps its shape; each ignored sample takes the class of
# the nearest sample that isn't ignored
if S.get("mask"):
    glyph = np.zeros(im.shape[:2], bool)
    for mu0, mv0, mu1, mv1 in S["mask"]:
        g = 18                                                 # context around the box
        a0, b0 = max(int(mv0) - g, 0), max(int(mu0) - g, 0)
        win = im[a0:int(mv1) + g + 1, b0:int(mu1) + g + 1]
        med = np.stack([ndi.median_filter(win[..., c], size=31) for c in range(3)], -1)
        diff = np.abs(win - med).sum(-1) > 45
        diff = ndi.binary_dilation(diff, iterations=2)
        sub = glyph[a0:a0 + win.shape[0], b0:b0 + win.shape[1]]
        vv, uu = np.mgrid[a0:a0 + win.shape[0], b0:b0 + win.shape[1]]
        sub |= diff & (uu >= mu0) & (uu <= mu1) & (vv >= mv0) & (vv <= mv1)
    bad = glyph[v, u].reshape(X.shape)
    _, (ii, jj) = ndi.distance_transform_edt(bad, return_indices=True)
    cls = cls[ii, jj]
    # nearest-filling leaves a step where a colour edge crosses the glyph: smooth the filled
    # area (and a margin round it) by a majority vote over about 1.2 mm
    near = ndi.binary_dilation(bad, iterations=6)
    w = max(3, int(round(1.2 / r)) | 1)
    votes = np.stack([ndi.uniform_filter((cls == i).astype(float), size=w) for i in range(len(pal))])
    cls = np.where(near, votes.argmax(0), cls)
k = max(1, int(round(S.get("smooth", 0.4) / r)))
out, over = {}, (pix * 0.4).astype(np.uint8)
for i, n in enumerate(names):
    if n not in S["keep"]:
        continue
    m = (cls == i) & inside
    m = ndi.binary_closing(m, iterations=k)
    m = ndi.binary_opening(m, iterations=k) & inside
    rings = []
    for c in measure.find_contours(np.pad(m.astype(float), 1), 0.5):
        rr, kk = c[:, 0] - 1, c[:, 1] - 1
        ring = np.c_[x0 + kk * r, z0 + rr * r][::2]
        if len(ring) >= 4:
            rings.append(ring.round(3).tolist())
    out[n] = rings
    over[m] = pal[i].astype(np.uint8)
json.dump({"classes": out, "spec": a.spec}, open(a.out, "w"))
Image.fromarray(over[::-1]).resize((over.shape[1] * 2, over.shape[0] * 2)).save(Path(a.out).with_suffix(".png"))
print({n: len(v) for n, v in out.items()}, "->", a.out)
