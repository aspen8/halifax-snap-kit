"""
Avro Vulcan B.2 snap kit, 1:72 (470 mm span, 423 mm long without the probe).

  python vulcan/cad/vulcan.py OUT_DIR

v1: the outer shape only, as one solid in the assembled frame (OUT_DIR/assembled/), to check
against the drawings before the kit is split into parts. See vulcan/README.md.

Axes (assembled): X = distance aft of the nose tip (probe excluded), Y = span (+ starboard),
Z = up, 0 at the nose tip. Lengths are printed mm (SCALE = KIT_SCALE for now).

All shapes are tables of stations, lofted ruled as point rings straight into manifold3d
(no CadQuery in the shape: see LESSONS.md, "Smooth OCC lofts ... can twist and overshoot").
"""
import math
import sys
from pathlib import Path

import manifold3d as mf
import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kitlib as K  # noqa: E402

M = mf.Manifold

# ============================================================
# PARAMETERS
# ============================================================
SCALE = 72.0
KIT_SCALE = 72.0
PRINT_K = SCALE / KIT_SCALE
SPAN = 33830.0 / SCALE          # 469.9 mm
LENGTH = 30450.0 / SCALE        # 422.9 mm, nose tip to the end of the tail cone (no probe)

# Fuselage: x, half-width, z top, z bottom, superellipse exponent. A 40.6 mm (2.9 m) tube with
# its centre at z 4.7; the wing's underside is flush with its belly.
FUSE_STATIONS = [
    (0.0, 0.4, 0.4, -0.4, 2.0),
    (3.0, 3.6, 3.2, -3.4, 2.0),
    (10.0, 7.5, 6.5, -7.2, 2.0),
    (25.0, 12.3, 12.0, -12.5, 2.0),
    (40.0, 16.0, 16.5, -14.6, 2.0),
    (56.0, 18.8, 20.5, -15.5, 2.0),
    (70.0, 20.0, 23.5, -15.6, 2.0),
    (90.0, 20.3, 24.8, -15.6, 2.0),
    (113.0, 20.3, 25.0, -15.6, 2.0),
    (300.0, 20.3, 25.5, -15.6, 2.0),
    (340.0, 18.5, 24.0, -14.5, 2.0),
    (367.0, 16.0, 19.0, -13.0, 2.0),
    (385.0, 14.0, 14.5, -10.5, 2.0),
    (400.0, 12.5, 11.5, -8.0, 2.0),
    (412.0, 10.5, 9.0, -5.5, 2.0),
    (419.0, 7.5, 6.5, -2.5, 2.0),
    (LENGTH, 1.5, 3.5, 1.5, 2.0),
]
CANOPY_STATIONS = [             # x, half-width, z top: the small bubble over the flight deck
    (50.0, 2.0, 19.5), (58.0, 7.0, 24.5), (66.0, 9.5, 28.3), (74.0, 10.0, 29.3),
    (90.0, 9.5, 28.0), (105.0, 7.5, 26.3), (116.0, 4.0, 25.2),
]
CANOPY_DEPTH = 14.0
CANOPY_N = 2.5
BLISTER = (70.0, -15.2, 17.0, 8.5, 4.5)   # bomb aimer's blister: x, z, radii along x, y, z
PROBE = (23.0, 2.2)             # refuelling probe: length ahead of the nose tip, diameter

# Wing planform (starboard): leading edge (y, x) with the B.2's two kinks, straight trailing edge.
WING_LE = [(0.0, 100.2), (25.4, 127.7), (73.8, 180.1), (101.4, 211.5), (132.0, 235.0),
           (181.2, 271.0), (208.1, 302.3), (226.0, 325.8), (SPAN / 2, 337.4)]
WING_TE = (361.4, 57.0, 0.099)  # x at y, dx/dy: outboard of the engines
WING_TE_INNER = 340.0           # between the fuselage and y 57 the jet pipes stand out of a shorter trailing edge
WING_TC = [(0.0, 0.11), (57.0, 0.10), (101.0, 0.08), (181.0, 0.06), (SPAN / 2, 0.05)]
WING_TIP_ROUND = (9.0, 14.7)    # the leading edge rounds into the tip over this span, by this much
WING_UNDER_Z = [(0.0, -14.5), (57.0, -14.5), (SPAN / 2, -18.5)]   # (y, z) of each section's lowest
                                # point: flush with the belly inboard, drooping 4 mm to the tip
WING_TE_T = 0.9                 # trailing edge thickness
WING_Y = [0.0, 10.0, 20.0, 25.4, 40.0, 56.5, 57.5, 73.8, 88.0, 101.4, 116.0, 132.0, 150.0, 165.0,
          181.2, 195.0, 208.1, 218.0, 226.0, 229.0, 231.5, 233.5, 234.5, SPAN / 2]

# Intakes: letterbox mouths in the swept inner leading edge, one per engine pair, split in two.
INTAKE_Y = (22.0, 59.0)         # span of the blunt lip fairing
INTAKE_ZC = 0.0
INTAKE_RINGS = [(-1.5, 17.0, 7.0), (1.0, 18.5, 8.4), (6.0, 19.0, 8.8), (80.0, 19.0, 8.8),
                (120.0, 17.0, 6.0)]   # distance behind the lip line, half-width, half-height
INTAKE_MOUTHS = [(24.5, 39.5), (41.5, 57.0)]   # y range of each opening (splitter between them)
INTAKE_MOUTH_Z = (-5.8, 5.8)
INTAKE_DEPTH = 28.0
INTAKE_N = 4.0

# Jet pipes: four, in pairs behind the trailing edge.
JET_Y = (31.5, 47.0)
JET_Z = -4.0
JET_PROFILE = [(290.0, 2.0), (335.0, 7.5), (371.0, 7.2)]   # x, radius
JET_BORE = (6.0, 12.0)          # radius, depth

# Fin: leading and trailing edge lines (x at z), symmetric section, the B.2's cap fairing on top.
FIN_LE = ((306.0, 28.0), (359.0, 80.0))
FIN_TE = ((378.0, 16.0), (405.6, 80.7))
FIN_Z = (12.0, 80.7)
FIN_TC = (0.09, 0.08)
FIN_CAP = [(355.0, 0.6, 80.3, 79.3), (359.0, 2.4, 82.0, 77.5), (404.0, 2.4, 82.0, 77.5),
           (409.0, 0.8, 80.5, 79.0)]   # x, half-width, z top, z bottom

OUT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/vulcan")


# ============================================================
# HELPERS
# ============================================================
def ring_loft(rings):
    """Ruled loft through point rings (each N x 3, same N, same winding), flat end caps."""
    rings = [np.asarray(r, float) for r in rings]
    n, k = len(rings[0]), len(rings)
    verts = np.vstack(rings + [rings[0].mean(0)[None], rings[-1].mean(0)[None]])
    faces = []
    for r in range(k - 1):
        a, b = r * n, (r + 1) * n
        for i in range(n):
            j = (i + 1) % n
            faces += [(a + i, a + j, b + j), (a + i, b + j, b + i)]
    c0, c1, last = k * n, k * n + 1, (k - 1) * n
    for i in range(n):
        j = (i + 1) % n
        faces += [(c0, j, i), (c1, last + i, last + j)]
    tm = trimesh.Trimesh(verts, faces, process=False)
    if tm.volume < 0:
        tm.invert()
    m = K.to_manifold(tm)
    if m.status() != mf.Error.NoError:
        raise RuntimeError(f"loft not manifold: {m.status()}")
    return m


def dense(table, step=3.0):
    """Stations resampled every `step` with a shape-preserving (PCHIP) curve."""
    from scipy.interpolate import PchipInterpolator
    t = np.asarray(table, float)
    xs = np.unique(np.r_[np.linspace(t[0, 0], t[-1, 0], int((t[-1, 0] - t[0, 0]) / step) + 1), t[:, 0]])
    return [tuple([x] + [float(PchipInterpolator(t[:, 0], t[:, j])(x)) for j in range(1, t.shape[1])])
            for x in xs]


def superellipse(hw, hh, n, pts=72):
    """[(a, b)] round a superellipse of half-axes hw, hh."""
    t = 2 * np.pi * np.arange(pts) / pts
    c, s = np.cos(t), np.sin(t)
    return np.c_[hw * np.sign(c) * np.abs(c) ** (2 / n), hh * np.sign(s) * np.abs(s) ** (2 / n)]


def x_ring(x, hw, z_top, z_bot, n, yc=0.0, pts=72):
    se = superellipse(hw, (z_top - z_bot) / 2, n, pts)
    return np.c_[np.full(pts, x), yc + se[:, 0], (z_top + z_bot) / 2 + se[:, 1]]


def aerofoil(tc, chord, te_t, n=40):
    """Symmetric NACA 4-digit section: [(x, t)] from the upper trailing edge round the nose to
    the lower trailing edge, chord line on t = 0, nose at x = 0."""
    x = (1 - np.cos(np.pi * np.arange(n + 1) / n)) / 2
    yt = 5 * tc * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)
    yt = yt * chord + x * te_t / 2
    up = np.c_[x * chord, yt][::-1]
    lo = np.c_[x * chord, -yt][1:]
    return np.vstack([up, lo])


def revolve_x(profile, seg=64):
    """Solid of revolution about the X axis from [(x, r), ...]."""
    pts = np.array([(max(r, 1e-3), x) for x, r in profile])
    poly = np.vstack([[0.0, profile[0][0]], pts, [0.0, profile[-1][0]]])
    m = M.revolve(mf.CrossSection([poly]), seg)
    return m.transform(np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0]], float))


def union(ms):
    return M.batch_boolean(list(ms), mf.OpType.Add)


def mirror_y(m):
    return m.mirror([0, 1, 0])


def mesh_tm(m):
    v, f = K.mesh_of(m)
    return trimesh.Trimesh(v, f, process=False)


_CACHE = {}


def cached(fn):
    def f(*a):
        k = (fn.__name__,) + a
        if k not in _CACHE:
            _CACHE[k] = fn(*a)
        return _CACHE[k]
    f.__name__ = fn.__name__
    return f


# ============================================================
# OUTER SHAPE
# ============================================================
@cached
def body():
    return ring_loft([x_ring(*s) for s in dense(FUSE_STATIONS)])


@cached
def canopy():
    return ring_loft([x_ring(x, hw, zt, zt - CANOPY_DEPTH, CANOPY_N) for x, hw, zt in dense(CANOPY_STATIONS, 2.0)])


@cached
def blister():
    x, z, rx, ry, rz = BLISTER
    return M.sphere(1.0, 64).scale([rx, ry, rz]).translate([x, 0, z])


def wing_le(y):
    y = abs(y)
    t = np.asarray(WING_LE)
    x = float(np.interp(y, t[:, 0], t[:, 1]))
    span, cut = WING_TIP_ROUND
    y0 = SPAN / 2 - span
    if y > y0:                                   # quarter-ellipse corner into the tip
        u = min(1.0, (y - y0) / span)
        x += cut * (1 - math.sqrt(max(0.0, 1 - u * u)))
    return x


def wing_te(y):
    y = abs(y)
    return WING_TE_INNER if y < WING_TE[1] else WING_TE[0] + WING_TE[2] * (y - WING_TE[1])


def wing_tc(y):
    t = np.asarray(WING_TC)
    return float(np.interp(abs(y), t[:, 0], t[:, 1]))


def wing_ring(y):
    le, te = wing_le(y), wing_te(y)
    c = te - le
    sec = aerofoil(wing_tc(y), c, WING_TE_T)
    t = np.asarray(WING_UNDER_Z)
    zc = float(np.interp(abs(y), t[:, 0], t[:, 1])) + sec[:, 1].max()
    return np.c_[le + sec[:, 0], np.full(len(sec), y), zc + sec[:, 1]]


@cached
def wing():
    """Starboard panel from the centreline to the tip."""
    return ring_loft([wing_ring(y) for y in WING_Y])


def lip_x(y):
    (y0, x0), (y1, x1) = WING_LE[1], WING_LE[2]
    return x0 + (y - y0) * (x1 - x0) / (y1 - y0)


def _sheared_ring(s, y0, y1, z0, z1, n=INTAKE_N, pts=72):
    """Superellipse in (y, z), in a plane parallel to the swept intake lip, s behind it."""
    se = superellipse((y1 - y0) / 2, (z1 - z0) / 2, n, pts)
    y = (y0 + y1) / 2 + se[:, 0]
    return np.c_[lip_x(y) + s, y, (z0 + z1) / 2 + se[:, 1]]


@cached
def intake_fairing():
    yc = (INTAKE_Y[0] + INTAKE_Y[1]) / 2
    return ring_loft([_sheared_ring(s, yc - hw, yc + hw, INTAKE_ZC - hh, INTAKE_ZC + hh)
                      for s, hw, hh in INTAKE_RINGS])


@cached
def intake_ducts():
    z0, z1 = INTAKE_MOUTH_Z
    return union([ring_loft([_sheared_ring(s, y0, y1, z0, z1) for s in (-4.0, INTAKE_DEPTH)])
                  for y0, y1 in INTAKE_MOUTHS])


@cached
def jet_pipes():
    pipe = revolve_x(JET_PROFILE)
    x1 = JET_PROFILE[-1][0]
    bore = revolve_x([(x1 - JET_BORE[1], JET_BORE[0]), (x1 + 1.0, JET_BORE[0])])
    return (union([pipe.translate([0, y, JET_Z]) for y in JET_Y]),
            union([bore.translate([0, y, JET_Z]) for y in JET_Y]))


@cached
def fin():
    (xl0, zl0), (xl1, zl1) = FIN_LE
    (xt0, zt0), (xt1, zt1) = FIN_TE
    rings = []
    for z in np.linspace(FIN_Z[0], FIN_Z[1], 24):
        le = xl0 + (z - zl0) * (xl1 - xl0) / (zl1 - zl0)
        te = xt0 + (z - zt0) * (xt1 - xt0) / (zt1 - zt0)
        u = (z - FIN_Z[0]) / (FIN_Z[1] - FIN_Z[0])
        sec = aerofoil(FIN_TC[0] + u * (FIN_TC[1] - FIN_TC[0]), te - le, WING_TE_T)
        rings.append(np.c_[le + sec[:, 0], sec[:, 1], np.full(len(sec), z)])
    cap = ring_loft([x_ring(x, hw, zt, zb, 3.0) for x, hw, zt, zb in dense(FIN_CAP, 1.5)])
    return ring_loft(rings) + cap


@cached
def probe():
    length, d = PROBE
    return M.cylinder(length + 2.0, d / 2, d / 2, 32).rotate([0, 90, 0]).translate([-length, 0, 0])


@cached
def airframe():
    pipes, bores = jet_pipes()
    half = wing() + intake_fairing() + pipes
    cuts = intake_ducts() + bores
    solid = union([body(), canopy(), blister(), fin(), half, mirror_y(half)])
    return solid - cuts - mirror_y(cuts)


def build():
    return {"airframe": airframe(), "probe": probe()}


if __name__ == "__main__":
    (OUT_DIR / "assembled").mkdir(parents=True, exist_ok=True)
    for name, m in build().items():
        piece, dropped = K.largest_piece(m)
        if any(abs(v) > 1.0 for v in dropped):
            print(f"!! {name}: dropped pieces {[round(v, 1) for v in dropped]}")
        tm = mesh_tm(piece)
        tm.export(OUT_DIR / "assembled" / f"{name}.stl")
        lo, hi = tm.bounds
        print(f"{name:12s} {piece.volume() / 1000:8.1f} cm3   x {lo[0]:.1f}..{hi[0]:.1f}   "
              f"y {lo[1]:.1f}..{hi[1]:.1f}   z {lo[2]:.1f}..{hi[2]:.1f}")
    # planform area, to check against the real 368.3 m2
    ys = np.linspace(0, SPAN / 2, 400)
    area = 2 * np.trapezoid([wing_te(y) - wing_le(y) for y in ys], ys)
    print(f"wing area {area * SCALE**2 / 1e6:.1f} m2 (real 368.3), span {SPAN:.1f} mm, length {LENGTH:.1f} mm")
