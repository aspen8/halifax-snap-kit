"""
Render the coloured preview GLB from colour.py to PNG views.

Run:  PYOPENGL_PLATFORM=egl python render_colour.py preview.glb out.png
"""
import os
import sys

os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
import numpy as np
import pyrender
import trimesh
from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
crop = sys.argv[3] if len(sys.argv) > 3 else None   # optional "x0,x1" to zoom on a range
tm = trimesh.load(src)
scene = pyrender.Scene(bg_color=[0.93, 0.94, 0.96, 1.0], ambient_light=[0.35, 0.35, 0.35])
for g in tm.geometry.values():
    m = pyrender.Mesh.from_trimesh(g, smooth=False)
    scene.add(m)
lo, hi = tm.bounds
if crop:
    a, b = map(float, crop.split(","))
    lo = np.array([a, lo[1], lo[2]])
    hi = np.array([b, hi[1], hi[2]])
c = (lo + hi) / 2
R = np.linalg.norm(hi - lo) / 2


def look(eye, target, up=(0, 0, 1)):
    f = target - eye
    f /= np.linalg.norm(f)
    s = np.cross(f, up)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = s, u, -f, eye
    return M


views = {
    "Port 3/4 from above": np.array([-1.0, -1.1, 0.75]),
    "Starboard 3/4": np.array([-0.6, 1.2, 0.5]),
    "Top": np.array([0.0001, 0.0, 1.0]),
    "Port side": np.array([0.0, -1.0, 0.05]),
    "Underside": np.array([0.0001, 0.0, -1.0]),
    "Rear 3/4": np.array([1.1, -0.9, 0.6]),
}
r = pyrender.OffscreenRenderer(900, 640)
tiles = []
for title, d in views.items():
    d = d / np.linalg.norm(d)
    eye = c + d * R * 2.4
    up = (1, 0, 0) if abs(d[2]) > 0.99 else (0, 0, 1)
    cam = pyrender.PerspectiveCamera(yfov=np.radians(28))
    cn = scene.add(cam, pose=look(eye, c, up))
    ln = scene.add(pyrender.DirectionalLight(intensity=3.2), pose=look(eye + np.array([0, 0, R]), c, up))
    ln2 = scene.add(pyrender.DirectionalLight(intensity=1.2), pose=look(c + np.array([0, 0, 3 * R]), c, (1, 0, 0)))
    img, _ = r.render(scene)
    scene.remove_node(cn)
    scene.remove_node(ln)
    scene.remove_node(ln2)
    tiles.append(Image.fromarray(img))
W, Hh = tiles[0].size
sheet = Image.new("RGB", (W * 3, Hh * 2), "white")
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % 3) * W, (i // 3) * Hh))
sheet.save(dst)
print("saved", dst)
