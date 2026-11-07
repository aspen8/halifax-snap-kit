"""
Orthographic triangle rasteriser with a z-buffer (numpy only): a gap-free view of a kit preview
GLB, for checking paint edges where the point-splat renderer (tools/render.py) speckles.

  python tools/raster.py preview.glb out.png --view under [--px 0.25] [--box x0,x1,y0,y1]

Views look along an axis: under (from below, nose left, port at the top), top, port, stbd,
tail (from behind), head. --px is mm per pixel in the GLB's units; --box crops (view units).
Flat shading from the face normal, so edges between colours are exactly where the paint is.
"""
import argparse

import numpy as np
import trimesh
from PIL import Image

# view: (screen-u axis, screen-v axis (down the image), depth axis toward the viewer)
VIEWS = {
    "under": ((1, 0, 0), (0, 1, 0), (0, 0, -1)),
    "top": ((1, 0, 0), (0, -1, 0), (0, 0, 1)),
    "port": ((1, 0, 0), (0, 0, -1), (0, -1, 0)),
    "stbd": ((-1, 0, 0), (0, 0, -1), (0, 1, 0)),
    "tail": ((0, -1, 0), (0, 0, -1), (1, 0, 0)),
    "head": ((0, 1, 0), (0, 0, -1), (-1, 0, 0)),
}


def raster(meshes, view, px, box=None, light=(0.3, -0.4, 0.85)):
    U, V, D = (np.array(a, float) for a in VIEWS[view])
    allv = np.vstack([m[0] for m in meshes])
    u_all, v_all = allv @ U, allv @ V
    if box:
        u0, u1, v0, v1 = box
    else:
        u0, u1, v0, v1 = u_all.min() - 2, u_all.max() + 2, v_all.min() - 2, v_all.max() + 2
    W, Hh = int((u1 - u0) / px) + 1, int((v1 - v0) / px) + 1
    zbuf = np.full(Hh * W, -np.inf)
    img = np.full((Hh * W, 3), 238.0)
    L = np.array(light, float); L /= np.linalg.norm(L)
    for verts, faces, cols in meshes:
        t = verts[faces]                                       # (F, 3, 3)
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        nn = np.linalg.norm(n, axis=1); ok = nn > 0
        t, n, cols = t[ok], n[ok] / nn[ok, None], cols[ok]
        facing = n @ D > 0                                     # back faces hidden by front ones
        t, n, cols = t[facing], n[facing], cols[facing]
        # shade in view space: light fixed relative to the viewer
        nv = np.c_[n @ U, -(n @ V), n @ D]
        shade = 0.45 + 0.55 * np.clip(nv @ L, 0, 1)
        c = np.clip(cols * shade[:, None], 0, 255)
        pu = (t @ U - u0) / px; pv = (t @ V - v0) / px; pz = t @ D
        bu0 = np.floor(pu.min(1)).astype(int); bu1 = np.ceil(pu.max(1)).astype(int)
        bv0 = np.floor(pv.min(1)).astype(int); bv1 = np.ceil(pv.max(1)).astype(int)
        size = np.maximum(bu1 - bu0, bv1 - bv0) + 1
        for s in np.unique(np.minimum(np.ceil(np.log2(np.maximum(size, 1))), 12)):
            sel = np.nonzero(np.minimum(np.ceil(np.log2(np.maximum(size, 1))), 12) == s)[0]
            S = int(2 ** s) + 1
            oy, ox = np.mgrid[0:S, 0:S]
            ox, oy = ox.ravel(), oy.ravel()
            for ch in np.array_split(sel, max(1, len(sel) * S * S // 4_000_000 + 1)):
                if not len(ch):
                    continue
                X = bu0[ch, None] + ox[None]; Y = bv0[ch, None] + oy[None]
                cx, cy = X + 0.5, Y + 0.5
                a, b, cc = pu[ch], pv[ch], pz[ch]
                x0, y0, x1, y1, x2, y2 = a[:, 0, None], b[:, 0, None], a[:, 1, None], b[:, 1, None], a[:, 2, None], b[:, 2, None]
                den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
                den = np.where(np.abs(den) < 1e-12, 1e-12, den)
                l0 = ((y1 - y2) * (cx - x2) + (x2 - x1) * (cy - y2)) / den
                l1 = ((y2 - y0) * (cx - x2) + (x0 - x2) * (cy - y2)) / den
                l2 = 1 - l0 - l1
                e = -1e-4
                inside = (l0 >= e) & (l1 >= e) & (l2 >= e) & (X >= 0) & (X < W) & (Y >= 0) & (Y < Hh)
                z = l0 * cc[:, 0, None] + l1 * cc[:, 1, None] + l2 * cc[:, 2, None]
                fi = np.broadcast_to(np.arange(len(ch))[:, None], X.shape)[inside]
                idx = (Y * W + X)[inside]; z = z[inside]
                if not len(idx):
                    continue
                order = np.lexsort((-z, idx))                  # nearest first per pixel
                idx, z, fi = idx[order], z[order], fi[order]
                first = np.r_[True, idx[1:] != idx[:-1]]
                idx, z, fi = idx[first], z[first], fi[first]
                win = z > zbuf[idx]
                zbuf[idx[win]] = z[win]
                img[idx[win]] = c[ch][fi[win]]
    return img.reshape(Hh, W, 3).astype(np.uint8), (u0, v0, px)


def load(src, skip=()):
    sc = trimesh.load(src)
    out = []
    for nm, g in sc.geometry.items():
        if any(k in nm for k in skip):
            continue
        fc = np.asarray(g.visual.face_colors)[:, :3].astype(float)
        out.append((np.asarray(g.vertices, float), np.asarray(g.faces), fc))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--view", default="under")
    ap.add_argument("--px", type=float, default=0.25)
    ap.add_argument("--box", default=None)
    ap.add_argument("--skip", default="stand,gear,wheel", help="part-name fragments to leave out")
    a = ap.parse_args()
    box = [float(v) for v in a.box.split(",")] if a.box else None
    im, _ = raster(load(a.src, [k for k in a.skip.split(",") if k]), a.view, a.px, box)
    Image.fromarray(im).save(a.out)
    print(a.out, im.shape)
