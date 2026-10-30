"""
Close-up renders of the coloured preview: one tile per view.

  EGL_PLATFORM=surfaceless PYOPENGL_PLATFORM=egl \
    python tools/closeup.py preview.glb out.png "40,0,-5 : -0.3,-1,0.35 : 110" "135,61,-30 : 0,1,0.05 : 110"

Each view is "target x,y,z : direction from target to camera : distance" (mm).
Up to six views make a 3x2 sheet.
"""
import os
import sys

os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
import numpy as np  # noqa: E402
import pyrender  # noqa: E402
import trimesh  # noqa: E402
from PIL import Image  # noqa: E402

src, dst, specs = sys.argv[1], sys.argv[2], sys.argv[3:]
tm = trimesh.load(src)
scene = pyrender.Scene(bg_color=[0.93, 0.94, 0.96, 1], ambient_light=[0.4] * 3)
for g in tm.dump():
    scene.add(pyrender.Mesh.from_trimesh(g, smooth=False))


def look(eye, t, up=(0, 0, 1)):
    f = t - eye
    f /= np.linalg.norm(f)
    s = np.cross(f, up)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = s, u, -f, eye
    return M


r = pyrender.OffscreenRenderer(900, 640)
tiles = []
for spec in specs[:6]:
    t, d, dist = [p.strip() for p in spec.split(":")]
    t = np.array(t.split(","), float)
    d = np.array(d.split(","), float)
    d /= np.linalg.norm(d)
    eye = t + d * float(dist)
    up = (1, 0, 0) if abs(d[2]) > 0.99 else (0, 0, 1)
    cn = scene.add(pyrender.PerspectiveCamera(yfov=np.radians(28)), pose=look(eye, t, up))
    ln = scene.add(pyrender.DirectionalLight(intensity=3), pose=look(eye + np.array([0, 0, 40]), t, up))
    img, _ = r.render(scene)
    scene.remove_node(cn)
    scene.remove_node(ln)
    tiles.append(Image.fromarray(img))
W, H = tiles[0].size
cols = min(3, len(tiles))
sheet = Image.new("RGB", (W * cols, H * ((len(tiles) + cols - 1) // cols)), "white")
for i, tl in enumerate(tiles):
    sheet.paste(tl, ((i % cols) * W, (i // cols) * H))
sheet.save(dst)
print("saved", dst)
