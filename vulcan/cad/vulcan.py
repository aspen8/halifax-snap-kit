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
WING_UNDER_Z = -15.0            # every section's lowest point: a flat underside, flush with the belly
WING_TE_T = 1.7 * _P            # trailing edge thickness (1.7 mm printed: two lines in each shell)
WING_MIN_T = 1.7 * _P           # no section is thinner than this (the tip)

# The kit splits into upper and lower shells, like a plastic kit, so the underside prints in one
# colour. The split surface holds the wing's leading and trailing edges: level at SPLIT_Z from
# the centreline to WING_JOINT_Y (the centre body), then a plane falling to SPLIT_TIP_Z at the
# tip (the outer wings). Sections are deeper above it than below inboard, so the underside stays
# flat and the top slopes down to the tip, as the drawings show.
SPLIT_Z = -4.0
# Inboard, over the engines, the wing's top is not an aerofoil hump: it climbs from the intake
# lip to its crest just behind it and then runs almost straight down to the trailing edge, so it
# meets the fuselage side on a straight line (Airfix side view, XH558 photos; user review).
WING_ROOT_UP = [(0.0, 23.0), (20.0, 23.0), (57.0, 12.9)]   # (y, depth of the top above the split)
WING_CREST = (0.12, 1.25)       # inboard: crest at this fraction of chord, then 1 - u^k to the trailing edge
WING_CREST_BLEND = (25.0, 80.0)  # the inboard profile fades into the plain aerofoil over this span
SPLIT_TIP_Z = -14.0
WING_JOINT_Y = 57.0             # centre body / outer wing joint (just outboard of the intakes and jet pipes)
RADOME_X = 24.0                 # the black radome is its own part ahead of this
FRONT_X = 105.0                 # front fuselage / centre body joint, at the wing root's leading edge
BED = (230.0, 250.0)            # usable plate, printed mm (X2D; 256 mm beds are larger)
WING_Y = [0.0, 10.0, 19.8, 34.0, 49.8, 54.0, 57.0, 58.5, 67.9, 77.8, 97.2, 116.5, 135.8, 155.2, 174.5,
          189.0, 193.9, 200.0, 206.9, 213.2, 219.0, 224.3, 229.0, 232.5, 233.5, 234.6, 234.8]

# Intakes: letterbox mouths in the swept inner leading edge, one per engine pair, split in two.
INTAKE_Y = (17.0, 55.0)         # span of the blunt lip fairing
INTAKE_ZC = 6.5
INTAKE_RINGS = [(-1.5, 17.0, 9.6), (1.0, 18.5, 11.0), (6.0, 19.0, 11.5), (40.0, 19.0, 11.5),
                (75.0, 17.0, 6.0)]   # distance behind the lip line, half-width, half-height
INTAKE_MOUTH = (20.5, 52.0)     # y range of the one letterbox mouth (head-on photo, 1982)
INTAKE_MOUTHS = [(20.5, 35.4), (37.1, 52.0)]   # the two ducts behind it, one per engine
INTAKE_SPLIT = 9.0              # the wall between the ducts starts this far behind the lip
INTAKE_MOUTH_Z = (-2.5, 15.0)
INTAKE_DEPTH = 28.0
INTAKE_N = 4.0
INTAKE_TAPER = (0.55, -4.5)     # at the outer end the lip is this fraction as tall and this much
                                # lower, so it runs into the thinner wing there (no ear above the skin)

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
FIN_TIP_ROUND = (7.0, 5.0)
FIN_CAP = [(362.0, 0.5, 71.6, 70.6), (366.0, 2.0, 72.8, 69.6), (404.0, 2.0, 72.8, 69.6),
           (409.5, 0.8, 72.0, 70.4)]   # x, half-width, z top, z bottom: the fairing on the fin top (XH558 fin photo)     # the leading edge rounds into the top over this height, by this much

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


def split_z(y):
    """Height of the split surface (and of the wing's leading and trailing edges) at span y."""
    y = abs(y)
    if y <= WING_JOINT_Y:
        return SPLIT_Z
    return SPLIT_Z + (SPLIT_TIP_Z - SPLIT_Z) * (y - WING_JOINT_Y) / (SPAN / 2 - WING_JOINT_Y)


SPLIT_TILT = math.degrees(math.atan2(SPLIT_Z - SPLIT_TIP_Z, SPAN / 2 - WING_JOINT_Y))   # 3.2 deg


def wing_ring(y, n=40):
    """Section at span y: edges on the split surface, depth below it set by the flat underside."""
    le, te = wing_le(y), wing_te(y)
    c = te - le
    t = max(wing_tc(y) * c, WING_MIN_T)
    zs = split_z(y)
    dl = min(zs - WING_UNDER_Z, 0.55 * t)
    du = t - dl
    ya = abs(y)
    if ya <= WING_JOINT_Y:
        r = np.asarray(WING_ROOT_UP)
        du = float(np.interp(ya, r[:, 0], r[:, 1]))
    x = (1 - np.cos(np.pi * np.arange(n + 1) / n)) / 2
    f = 0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4
    f = f / f.max()
    p, k = WING_CREST
    fw = np.where(x < p, np.sqrt(np.clip(1 - (1 - x / p) ** 2, 0, 1)), 1 - np.clip((x - p) / (1 - p), 0, 1) ** k)
    w = float(np.clip((ya - WING_CREST_BLEND[0]) / (WING_CREST_BLEND[1] - WING_CREST_BLEND[0]), 0, 1))
    fu = (1 - w) * fw + w * f
    e = np.minimum(WING_TE_T, t) / 2 * x                  # half the trailing edge thickness, growing aft
    up = np.c_[x * c, fu * (du - e[-1]) + e][::-1]
    lo = np.c_[x * c, -(f * (dl - e[-1]) + e)][1:]
    sec = np.vstack([up, lo])
    return np.c_[le + sec[:, 0], np.full(len(sec), y), zs + sec[:, 1]]


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
    u = np.clip((y - INTAKE_Y[0]) / (INTAKE_Y[1] - INTAKE_Y[0]), 0.0, 1.0)
    k, dz = 1 + u * (INTAKE_TAPER[0] - 1), u * INTAKE_TAPER[1]
    return np.c_[lip_x(y) + s, y, (z0 + z1) / 2 + dz + se[:, 1] * k]


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
    cap = ring_loft([x_ring(x, hw, zt, zb, 3.0) for x, hw, zt, zb in dense(FIN_CAP, 1.5)])
    return ring_loft(rings) + cap


@cached
def probe():
    length, d = PROBE
    return M.cylinder(length + 2.0, d / 2, d / 2, 32).rotate([0, 90, 0]).translate([-length, 0, 0])


@cached
def airframe():
    """Everything but the fin and the probe, as one solid."""
    pipes, bores = jet_pipes()
    half = wing() + intake_fairing() + pipes
    cuts = intake_ducts() + bores
    solid = union([body(), canopy(), blister(), half, mirror_y(half)])
    return solid - cuts - mirror_y(cuts)


# ============================================================
# PARTS
# ============================================================
BIG = 600.0


def box(x0, x1, y0, y1, z0, z1):
    return K.box(x0, x1, y0, y1, z0, z1)


def rot_x(m, deg, y0, z0):
    """Rotate about the line through (y0, z0) parallel to X."""
    return m.translate([0, -y0, -z0]).rotate([deg, 0, 0]).translate([0, y0, z0])


def above_split(side):
    """Half-space above the split surface: side 0 the centre body, +1 / -1 an outer wing."""
    up = box(-BIG, BIG, -BIG, BIG, SPLIT_Z, BIG)
    if side == 0:
        return up
    return rot_x(up, -side * SPLIT_TILT, side * WING_JOINT_Y, SPLIT_Z)


def region(name):
    """The block of space a part is cut from (before the upper / lower split)."""
    j = WING_JOINT_Y
    if name == "radome":
        return box(-BIG, RADOME_X, -BIG, BIG, -BIG, BIG)
    if name == "front":
        return box(RADOME_X, FRONT_X, -BIG, BIG, -BIG, BIG)
    if name == "centre":
        return box(FRONT_X, BIG, -j, j, -BIG, BIG)
    if name == "wing_stbd":
        return box(FRONT_X, BIG, j, BIG, -BIG, BIG)
    if name == "wing_port":
        return box(FRONT_X, BIG, -BIG, -j, -BIG, BIG)
    raise KeyError(name)


def flip(m):
    """Turn a lower shell over (a rotation about X: never a mirror)."""
    return m.rotate([180, 0, 0])


def build():
    """Returns {name: (Manifold in the assembled frame, pose function -> print pose)}."""
    a = airframe() - fin()
    parts = {"radome": (a ^ region("radome"),
                        lambda m: m.rotate([0, 90, 0]))}             # on end, on its joint face
    for name, side in (("front", 0), ("centre", 0), ("wing_stbd", 1), ("wing_port", -1)):
        blk = a ^ region(name)
        up = above_split(side)
        level = (lambda m, s=side: rot_x(m, s * SPLIT_TILT, s * WING_JOINT_Y, SPLIT_Z)) if side else (lambda m: m)
        parts[f"{name}_upper"] = (blk ^ up, level)
        parts[f"{name}_lower"] = (blk - up, lambda m, lv=level: flip(lv(m)))
    parts["fin"] = (fin(), lambda m: m.rotate([90, 0, 0]))            # (pose to come: two halves)
    parts["probe"] = (probe(), lambda m: m)
    return parts


if __name__ == "__main__":
    for d in ("assembled", "print"):
        (OUT_DIR / d).mkdir(parents=True, exist_ok=True)
    for name, (m, pose) in build().items():
        piece, dropped = K.largest_piece(m)
        if any(abs(v) > 1.0 for v in dropped):
            print(f"!! {name}: dropped pieces {[round(v, 1) for v in dropped]}")
        mesh_tm(piece).export(OUT_DIR / "assembled" / f"{name}.stl")       # at 1:72 (the checks' frame)
        pm = pose(piece).scale([PRINT_K] * 3)
        lo, hi = pm.bounding_box()[:3], pm.bounding_box()[3:]
        pm = pm.translate([-lo[0], -lo[1], -lo[2]])
        mesh_tm(pm).export(OUT_DIR / "print" / f"{name}.stl")              # print pose, printed size
        sx, sy, sz = (hi[i] - lo[i] for i in range(3))
        fits = (sx <= BED[0] and sy <= BED[1]) or (sy <= BED[0] and sx <= BED[1])
        print(f"{name:16s} {pm.volume() / 1000:7.1f} cm3   print {sx:6.1f} x {sy:6.1f} x {sz:5.1f} mm"
              f"{'' if fits else '   !! does not fit the bed'}")
    # planform area, to check against the real 368.3 m2
    ys = np.linspace(0, SPAN / 2, 400)
    area = 2 * np.trapezoid([wing_te(y) - wing_le(y) for y in ys], ys)
    print(f"wing area {area * SCALE**2 / 1e6:.1f} m2 (real 368.3); printed at 1:{KIT_SCALE:.0f}: span "
          f"{SPAN * PRINT_K:.1f} mm, length {LENGTH * PRINT_K:.1f} mm")
