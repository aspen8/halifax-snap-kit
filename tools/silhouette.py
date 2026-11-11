"""Silhouette masks from the Revell painting-guide views (grey stipple fill).

  python tools/silhouette.py PAGE_PNG x0 y0 x1 y1 OUT_PREFIX [--thresh 215] [--blur 5]

Writes OUT_PREFIX_mask.png (largest filled component) and prints its pixel bounds.
"""
import argparse
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage as ndi

ap = argparse.ArgumentParser()
ap.add_argument("page"); ap.add_argument("box", nargs=4, type=int); ap.add_argument("out")
ap.add_argument("--thresh", type=int, default=215); ap.add_argument("--blur", type=float, default=5)
ap.add_argument("--close", type=int, default=6)
a = ap.parse_args()
im = Image.open(a.page).convert("L").crop(tuple(a.box))
g = np.asarray(im.filter(ImageFilter.GaussianBlur(a.blur)))
m = g < a.thresh
m = ndi.binary_closing(m, iterations=a.close)
lab, n = ndi.label(m)
sizes = ndi.sum(m, lab, range(1, n + 1))
big = lab == (1 + int(np.argmax(sizes)))
big = ndi.binary_fill_holes(big)
big = ndi.binary_opening(big, iterations=2)
Image.fromarray((big * 255).astype(np.uint8)).save(a.out + "_mask.png")
ys, xs = np.nonzero(big)
print("bounds px (in crop): x", xs.min(), xs.max(), " y", ys.min(), ys.max(), " offset", a.box[:2])
over = np.stack([np.asarray(im)] * 3, -1).copy()
edge = big ^ ndi.binary_erosion(big, iterations=3)
over[edge] = [255, 0, 255]
Image.fromarray(over).reduce(3).save(a.out + "_check.png")
