"""
Avro Vulcan B.2 snap kit, 1:96 (352 mm span, 317 mm long without the probe).

  python vulcan/cad/vulcan.py OUT_DIR

v1: the outer shape only, as one solid in the assembled frame (OUT_DIR/assembled/), to check
against the drawings before the kit is split into parts. See vulcan/README.md.

Axes (assembled): X = distance aft of the nose tip (probe excluded), Y = span (+ starboard),
Z = up, 0 at the nose tip. Lengths are mm at 1:72, the scale the drawings were measured at
(SCALE); parts are scaled by PRINT_K when written for printing. Give fits and pin sizes as
printed mm times _P, so they come out at their tested size (LESSONS.md, "Build at the
measuring scale and scale at the end").

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
SCALE = 72.0                    # shape scale: all lengths below are at 1:72
KIT_SCALE = 96.0                # print scale: 352 mm span, about a 1:32 Spitfire's (user)
PRINT_K = SCALE / KIT_SCALE     # 0.75: every part is scaled by this when written out
_P = 1.0 / PRINT_K              # print-size lengths (fits, pins, walls) are given as printed mm times this
SPAN = 33830.0 / SCALE          # 469.9 mm at 1:72 (352.4 mm printed)
LENGTH = 422.5                  # nose tip to the end of the tail cone, no probe (316.9 mm printed):
                                # 30.42 m, the published 99 ft 11 in (Airfix A12011 plan and side views)

# Fuselage: x, half-width, z top, z bottom, superellipse exponent (z 0 = the nose tip). From
# the Airfix A12011 painting guide (scheme A): side view for the top and bottom lines, plan
# view for the widths. A 38 mm tube, centre z 4.35; the wing's underside is flush with its belly.
FUSE_STATIONS = [
    (0.0, 0.5, 0.5, -0.5, 2.0),
    (1.0, 3.4, 1.8, -2.6, 2.0),
    (3.9, 5.3, 3.9, -5.2, 2.0),
    (7.7, 7.6, 6.3, -8.2, 2.0),
    (15.5, 10.6, 10.2, -10.5, 2.0),
    (23.2, 12.6, 12.1, -12.1, 2.0),
    (30.9, 14.3, 15.0, -13.0, 2.0),
    (38.7, 15.4, 16.9, -14.0, 2.0),
    (46.4, 16.7, 18.9, -15.0, 2.0),
    (54.1, 17.5, 19.8, -15.0, 2.0),
    (62.8, 17.9, 20.8, -15.0, 2.0),
    (74.5, 18.4, 22.3, -15.0, 2.0),
    (86.1, 18.9, 23.2, -15.0, 2.0),
    (108.0, 18.9, 23.7, -15.0, 2.0),
    (300.0, 18.9, 23.7, -15.0, 2.0),
    (330.0, 17.5, 20.0, -15.0, 2.0),
    (350.0, 15.0, 14.0, -15.0, 2.0),
    (365.0, 13.0, 11.0, -14.8, 2.0),
    (383.9, 11.6, 10.5, -14.2, 2.0),
    (395.5, 11.6, 8.0, -12.9, 2.0),
    (401.3, 10.6, 6.6, -12.2, 2.0),
    (407.0, 9.2, 5.2, -11.0, 2.0),
    (412.9, 6.5, 3.8, -9.6, 2.0),
    (418.7, 4.0, 1.5, -7.5, 2.0),
    (LENGTH, 0.8, -2.9, -3.9, 2.0),
]
CANOPY_STATIONS = [             # x, half-width, z top: the small bubble over the flight deck
    (58.0, 4.0, 20.5), (62.0, 7.5, 25.6), (69.6, 9.5, 29.5), (77.4, 9.5, 29.5),
    (85.0, 9.0, 28.5), (93.0, 8.0, 27.6), (101.0, 6.0, 25.6), (110.0, 3.0, 24.2),
]
CANOPY_DEPTH = 12.0
CANOPY_N = 2.5
BLISTER = (70.0, -14.6, 12.0, 7.0, 3.5)   # bomb aimer's blister: x, z, radii along x, y, z
PROBE = (26.0, 2.0)             # refuelling probe: length ahead of the nose tip, diameter

# Wing planform (starboard), from the Airfix plan view (the Commons silhouette agrees within
# about 3 mm): leading edge (y, x) with the intake notch at y 50-58, the B.2's two kinks
# (y 97 and 180) and the rounded tip; a nearly straight trailing edge.
WING_LE = [(0.0, 88.3), (19.8, 116.0), (49.8, 157.6), (58.5, 161.5), (77.8, 184.7), (97.2, 205.9),
           (116.5, 221.4), (135.8, 235.9), (155.2, 250.4), (174.5, 264.9), (189.0, 278.5),
           (193.9, 284.3), (206.9, 302.6), (213.2, 310.4), (224.3, 326.8), (232.5, 344.2),
           (233.5, 351.0), (234.6, 365.0), (SPAN / 2, 375.2)]
WING_TE = (360.7, 58.5, 0.1167)  # x at y, dx/dy outboard of it
WING_TE_INNER = 360.2           # inboard of that y
WING_TC = [(0.0, 0.14), (30.0, 0.14), (57.0, 0.12), (105.0, 0.11), (152.0, 0.085), (200.0, 0.075),
           (SPAN / 2, 0.06)]
WING_TIP_ROUND = (9.0, 0.0)     # (the tip's rounding is in WING_LE now)
WING_UNDER_Z = [(0.0, -15.0), (58.0, -15.0), (SPAN / 2, -17.0)]   # (y, z) of each section's lowest
                                # point: flush with the belly inboard, drooping 2 mm to the tip
WING_TE_T = 0.9 * _P            # trailing edge thickness (0.9 mm printed)
WING_Y = [0.0, 10.0, 19.8, 34.0, 49.8, 54.0, 58.5, 67.9, 77.8, 97.2, 116.5, 135.8, 155.2, 174.5,
          189.0, 193.9, 200.0, 206.9, 213.2, 219.0, 224.3, 229.0, 232.5, 233.5, 234.6, 234.8]

# Intakes: letterbox mouths in the swept inner leading edge, one per engine pair, split in two.
INTAKE_Y = (17.0, 55.0)         # span of the blunt lip fairing
INTAKE_ZC = 3.5
INTAKE_RINGS = [(-1.5, 17.0, 7.6), (1.0, 18.5, 9.0), (6.0, 19.0, 9.5), (80.0, 19.0, 9.5),
                (120.0, 17.0, 6.0)]   # distance behind the lip line, half-width, half-height
INTAKE_MOUTH = (20.5, 52.0)     # y range of the one letterbox mouth (head-on photo, 1982)
INTAKE_MOUTHS = [(20.5, 35.4), (37.1, 52.0)]   # the two ducts behind it, one per engine
INTAKE_SPLIT = 9.0              # the wall between the ducts starts this far behind the lip
INTAKE_MOUTH_Z = (-2.5, 9.5)
INTAKE_DEPTH = 28.0
INTAKE_N = 4.0

# Jet pipes: four, in pairs. Their fairings run under the wing from mid-chord (the side
# view's lowest line, about 3.5 mm below the belly) and the nozzles stand 6 mm behind the trailing edge.
JET_Y = (33.4, 45.9)
JET_Z = -12.3
JET_PROFILE = [(197.0, 1.5), (252.0, 6.0), (302.0, 6.7), (366.5, 6.2)]   # x, radius
JET_BORE = (5.1, 10.0)          # radius, depth

# Fin: leading and trailing edge lines (x at z), symmetric section, rounded front top corner.
FIN_LE = ((303.6, 23.7), (362.5, 69.0))
FIN_TE = ((376.0, 11.0), (406.0, 70.6))
FIN_Z = (5.0, 72.0)
FIN_TC = (0.08, 0.08)
FIN_TIP_ROUND = (7.0, 5.0)      # the leading edge rounds into the top over this height, by this much

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
    mouth = ring_loft([_sheared_ring(s, *INTAKE_MOUTH, z0, z1) for s in (-4.0, INTAKE_SPLIT)])
    return union([mouth] + [ring_loft([_sheared_ring(s, y0, y1, z0, z1) for s in (INTAKE_SPLIT - 1.0, INTAKE_DEPTH)])
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
    span, cut = FIN_TIP_ROUND
    rings = []
    zs = np.r_[np.linspace(FIN_Z[0], FIN_Z[1] - span, 16), FIN_Z[1] - span * (1 - np.sin(np.linspace(0.15, 1, 9) * np.pi / 2))]
    for z in zs:
        le = xl0 + (z - zl0) * (xl1 - xl0) / (zl1 - zl0)
        te = xt0 + (z - zt0) * (xt1 - xt0) / (zt1 - zt0)
        u = max(0.0, (z - (FIN_Z[1] - span)) / span)
        le += cut * (1 - math.sqrt(max(0.0, 1 - u * u)))
        sec = aerofoil(FIN_TC[0], te - le, WING_TE_T)
        rings.append(np.c_[le + sec[:, 0], sec[:, 1], np.full(len(sec), z)])
    return ring_loft(rings)


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
    print(f"wing area {area * SCALE**2 / 1e6:.1f} m2 (real 368.3); printed at 1:{KIT_SCALE:.0f}: span "
          f"{SPAN * PRINT_K:.1f} mm, length {LENGTH * PRINT_K:.1f} mm")
