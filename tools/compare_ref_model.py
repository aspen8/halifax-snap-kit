"""
Compare our model with another 3D model of the same aircraft (a 3MF or STL someone else made),
cross-section by cross-section. Use it as a measuring reference only; keep our own geometry.

  python tools/compare_ref_model.py REF.3mf|REF.stl OUT.png OUR_PART.stl [...]
      --axes=-z,x,y          how the reference's axes map to ours (X aft, Y span, Z up)
      --ends=-127.5,146.5    reference fuselage nose and tail x (after --axes), found with --probe
      --target=0.8,264.2     our fuselage nose and tail x: the reference is scaled to fit between them
      --zc=-31               reference z of the nose centre (moved to our z 0)
      --stations=40,70,100   x stations to plot
      --probe                print the reference's section sizes along x (to find --ends and --zc)

Writes OUT.png (our sections filled red, the reference outlined in black) and prints the
half-width of both at several heights per station.
"""
import argparse
import zipfile

import matplotlib
import numpy as np
import trimesh

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def load_ref(path):
    if path.lower().endswith(".3mf"):
        from lxml import etree
        z = zipfile.ZipFile(path)
        ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
        V, F, off = [], [], 0
        for name in z.namelist():
            if not name.endswith(".model"):
                continue
            x = etree.fromstring(z.read(name))
            for o in x.findall(".//m:object", ns):
                vs = o.findall(".//m:vertex", ns)
                if not vs:
                    continue
                v = np.array([[float(e.get(k)) for k in "xyz"] for e in vs])
                f = np.array([[int(e.get(k)) for k in ("v1", "v2", "v3")] for e in o.findall(".//m:triangle", ns)])
                V.append(v)
                F.append(f + off)
                off += len(v)
        return trimesh.Trimesh(np.vstack(V), np.vstack(F), process=True)
    return trimesh.load(path)


def remap(m, axes):
    cols = []
    for a in axes.split(","):
        s = -1.0 if a.startswith("-") else 1.0
        cols.append(s * m.vertices[:, "xyz".index(a[-1])])
    W = np.c_[tuple(cols)]
    flip = np.prod([(-1 if a.startswith("-") else 1) for a in axes.split(",")])
    perm = [("xyz".index(a[-1])) for a in axes.split(",")]
    parity = 1 if perm in ([0, 1, 2], [1, 2, 0], [2, 0, 1]) else -1
    F = m.faces if flip * parity > 0 else m.faces[:, ::-1]
    return trimesh.Trimesh(W, F, process=True)


def sections(m, x):
    p = m.section(plane_origin=[x, 0, 0], plane_normal=[1, 0, 0])
    return [] if p is None else [np.c_[e[:, 1], e[:, 2]] for e in p.discrete]


def half_width(m, x, z):
    out = []
    for e in sections(m, x):
        for a, b in zip(e[:-1], e[1:]):
            if (a[1] - z) * (b[1] - z) <= 0 and a[1] != b[1]:
                t = (z - a[1]) / (b[1] - a[1])
                out.append(abs(a[0] + t * (b[0] - a[0])))
    return max(out) if out else float("nan")


ap = argparse.ArgumentParser()
ap.add_argument("ref"); ap.add_argument("out"); ap.add_argument("ours", nargs="*")
ap.add_argument("--axes", default="x,y,z")
ap.add_argument("--ends"); ap.add_argument("--target"); ap.add_argument("--zc", type=float, default=0.0)
ap.add_argument("--stations", default="")
ap.add_argument("--probe", action="store_true")
a = ap.parse_args()

R = remap(load_ref(a.ref), a.axes)
if a.probe:
    lo, hi = R.bounds[:, 0]
    for x in np.linspace(lo, hi, 60):
        P = np.vstack(sections(R, x) or [np.full((1, 2), np.nan)])
        print(f"x {x:8.1f}  y {np.nanmin(P[:, 0]):7.1f} {np.nanmax(P[:, 0]):7.1f}  z {np.nanmin(P[:, 1]):7.1f} {np.nanmax(P[:, 1]):7.1f}")
    raise SystemExit
x0, x1 = map(float, a.ends.split(","))
t0, t1 = map(float, a.target.split(","))
k = (t1 - t0) / (x1 - x0)
R.apply_translation([-x0, 0, -a.zc])
R.apply_scale(k)
R.apply_translation([t0, 0, 0])
O = trimesh.util.concatenate([trimesh.load(f) for f in a.ours])
xs = [float(v) for v in a.stations.split(",")]
cols = (len(xs) + 1) // 2
fig, axs = plt.subplots(2, cols, figsize=(3.2 * cols, 7))
for ax, x in zip(axs.ravel(), xs):
    for e in sections(O, x):
        ax.fill(e[:, 0], e[:, 1], color=(0.85, 0.2, 0.25), alpha=0.35, lw=0)
    for e in sections(R, x):
        ax.plot(e[:, 0], e[:, 1], "k", lw=0.9)
    ax.set_aspect("equal"); ax.set_title(f"X {x:g}"); ax.grid(lw=0.3)
plt.tight_layout(); plt.savefig(a.out, dpi=75)
zs = (-4, 0, 4, 8, 12, 16, 20, 24, 28)
print("half-width at z", zs, f"(reference scaled x{k:.3f})")
for x in xs:
    print(f"X {x:5.0f} ref ", [round(half_width(R, x, z), 1) for z in zs])
    print(f"        ours", [round(half_width(O, x, z), 1) for z in zs])
