"""
Software renderer (numpy point splatting, no OpenGL: works on macOS) for any kit preview GLB.

  python tools/render.py preview.glb out.png [--views a,b,...] [--size 900x640]
  python tools/render.py STL_DIR out.png          (grey, all STLs in a folder)

Views: port34, stbd34, top, port, under, rear34, front, closeup_cockpit.
"""
import argparse
import glob
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

VIEWS = {
    "port34": ((-1.0, -1.15, 0.7), "Port 3/4"),
    "stbd34": ((-0.6, 1.2, 0.45), "Starboard 3/4"),
    "top": ((0.0001, 0.0, 1.0), "Top"),
    "port": ((0.0, -1.0, 0.02), "Port side"),
    "under": ((0.0001, 0.0, -1.0), "Underside"),
    "rear34": ((1.1, -0.9, 0.55), "Rear 3/4"),
    "front": ((-1.0, -0.25, 0.25), "Front"),
}


SKIP = []


def load(src):
    meshes = []
    p = Path(src)
    if p.is_dir():
        for f in sorted(glob.glob(str(p / "*.stl"))):
            m = trimesh.load(f)
            meshes.append((m.vertices, m.faces, np.array([200, 200, 205])))
    else:
        sc = trimesh.load(src)
        geoms = sc.geometry.values() if hasattr(sc, "geometry") else [sc]
        names = list(sc.geometry.keys()) if hasattr(sc, "geometry") else ["mesh"]
        for nm, g in zip(names, geoms):
            if SKIP and any(k in nm for k in SKIP):
                continue
            fc = np.asarray(g.visual.face_colors)[:, :3] if hasattr(g.visual, "face_colors") else None
            col = fc[0] if fc is not None and len(fc) else np.array([200, 200, 205])
            meshes.append((g.vertices, g.faces, col))
    return meshes


def render(meshes, d, size=(900, 640), up=(0, 0, 1), focus=None, zoom=1.0, density=2.2):
    """Point-splat renderer: every triangle is sampled ~density^2 times per covered pixel,
    projected, and z-buffered with numpy (fast enough for ~10^6 triangles)."""
    W, H = size
    allv = np.vstack([v for v, _, _ in meshes])
    lo, hi = allv.min(0), allv.max(0)
    c = (lo + hi) / 2 if focus is None else np.asarray(focus, float)
    d = np.asarray(d, float); d /= np.linalg.norm(d)
    up = np.asarray((1, 0, 0) if abs(d[2]) > 0.99 else up, float)
    f = -d
    s = np.cross(f, up); s /= np.linalg.norm(s)
    u = np.cross(s, f)
    R = np.linalg.norm(hi - lo) / 2 / zoom
    scale = min(W, H) / (2.05 * R)
    light = d * 0.55 + np.array([0.25, -0.35, 0.8]); light /= np.linalg.norm(light)
    rng = np.random.default_rng(0)
    xs, ys, zs, cols = [], [], [], []
    for V, F, col in meshes:
        T = V[F]                                            # (n, 3, 3)
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        nn = np.linalg.norm(n, axis=1) + 1e-12
        n = n / nn[:, None]
        P = T - c
        px = np.stack([P @ s, -(P @ u)], -1) * scale          # (n, 3, 2)
        e1, e2 = px[:, 1] - px[:, 0], px[:, 2] - px[:, 0]
        area = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
        k = np.minimum(np.ceil(area * density * density).astype(int) + 1, 4000)
        idx = np.repeat(np.arange(len(F)), k)
        r1, r2 = rng.random(len(idx)), rng.random(len(idx))
        flip = r1 + r2 > 1
        r1[flip], r2[flip] = 1 - r1[flip], 1 - r2[flip]
        pts = T[idx, 0] + (T[idx, 1] - T[idx, 0]) * r1[:, None] + (T[idx, 2] - T[idx, 0]) * r2[:, None]
        Q = pts - c
        xs.append(Q @ s * scale + W / 2); ys.append(-(Q @ u) * scale + H / 2); zs.append(Q @ f)   # distance from the eye
        shade = 0.35 + 0.65 * np.clip(np.abs(n @ light), 0, 1)
        cols.append(np.asarray(col, np.float32)[None, :] * shade[idx, None])
    x = np.concatenate(xs).astype(int); y = np.concatenate(ys).astype(int)
    z = np.concatenate(zs); col = np.concatenate(cols)
    ok = (x >= 0) & (x < W) & (y >= 0) & (y < H)
    x, y, z, col = x[ok], y[ok], z[ok], col[ok]
    pix = y * W + x
    order = np.lexsort((z, pix))
    pix, col = pix[order], col[order]
    first = np.r_[True, pix[1:] != pix[:-1]]
    img = np.full((H * W, 3), [238, 240, 244], np.float32)
    img[pix[first]] = col[first]
    return Image.fromarray(np.clip(img.reshape(H, W, 3), 0, 255).astype(np.uint8))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--views", default="port34,stbd34,top,port,under,rear34")
    ap.add_argument("--size", default="900x640")
    ap.add_argument("--focus", default=None, help="x,y,z to centre on")
    ap.add_argument("--zoom", type=float, default=1.0)
    ap.add_argument("--skip", default="", help="comma list of part-name fragments to leave out (GLB)")
    a = ap.parse_args()
    W, H = map(int, a.size.split("x"))
    SKIP.extend([k for k in a.skip.split(",") if k])
    meshes = load(a.src)
    focus = [float(v) for v in a.focus.split(",")] if a.focus else None
    tiles = [render(meshes, VIEWS[v][0], (W, H), focus=focus, zoom=a.zoom) for v in a.views.split(",")]
    cols = min(3, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (W * cols, H * rows), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * W, (i // cols) * H))
    sheet.save(a.out)
    print("saved", a.out)
