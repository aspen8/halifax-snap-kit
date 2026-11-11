"""Zoomed crop of a reference page with a labelled pixel grid (page coordinates).
  python tools/grid.py PAGE x0 y0 x1 y1 OUT [--step 50] [--scale 0.5]"""
import argparse
from PIL import Image, ImageDraw
ap = argparse.ArgumentParser()
ap.add_argument("page"); ap.add_argument("box", nargs=4, type=int); ap.add_argument("out")
ap.add_argument("--step", type=int, default=50); ap.add_argument("--scale", type=float, default=0.5)
a = ap.parse_args()
x0, y0, x1, y1 = a.box
im = Image.open(a.page).convert("RGB").crop((x0, y0, x1, y1))
im = im.resize((int(im.width * a.scale), int(im.height * a.scale)), Image.LANCZOS)
d = ImageDraw.Draw(im)
s = a.scale
for x in range((x0 // a.step + 1) * a.step, x1, a.step):
    major = x % (2 * a.step) == 0
    d.line([((x - x0) * s, 0), ((x - x0) * s, im.height)], fill=(0, 160, 255) if major else (170, 220, 255), width=1)
    if major: d.text(((x - x0) * s + 2, 2), str(x), fill=(0, 0, 255))
for y in range((y0 // a.step + 1) * a.step, y1, a.step):
    major = y % (2 * a.step) == 0
    d.line([(0, (y - y0) * s), (im.width, (y - y0) * s)], fill=(255, 120, 0) if major else (255, 210, 170), width=1)
    if major: d.text((2, (y - y0) * s + 2), str(y), fill=(200, 60, 0))
im.save(a.out)
