"""
BAE Systems Hawk T.1A, Red Arrows, 1:32 scale (293.4 mm span) snap kit.

Run:  python hawk.py OUT_DIR [PART ...]
Writes every kit part as an STL in print orientation at 1:32 (OUT_DIR/print/) and in
assembled position at 1:40 (OUT_DIR/assembled/, the frame the checks and colour.py work in).

Axes (assembled): X = distance aft of the nose tip (probe excluded), Y = span
(+ = starboard), Z = up, Z = 0 at the nose tip. Units: mm at 1:40, the scale the shape was
measured at. Every part is scaled by PRINT_K (1:40 -> 1:32) when it is written out, so fit
clearances and pin sizes below are divided by PRINT_K to come out at their tested print size.

Shape from the Revell 04284 Hawk T.1A plan and side views (hawk/tools/refs.json),
scaled to the real span of 9.39 m. Checks: wing area 16.8 m2 (real 16.69),
root chord 2.66 m (real 2.65), length with probe 11.96 m.

Kit layout (Halifax v2 / Lancaster style; no supports):
  fuselage     nose (with the radome and a short, stout probe), middle and rear full-width red
               sections, printed on end (no centre seam)
  fin          two halves split on the centreline, printed flat (Union flag in the skin)
  canopy       opaque, solid, flat underneath; drops onto 2 tabs moulded on the fuselage
  nozzle       separate jet nozzle with a deep void and exhaust cone, plugs into the tail
  wings        one per side, flat underside (white underside chevrons print face down)
  tailplane    one per side (10 deg anhedral)
  smoke pod    centreline pod keyed into the belly
  markings     cheat line, swoosh, lettering, stripes and roundels painted into the parts
  gear         nose leg and 2 main legs with wheels (or fly it on the stand)
  stand        swept blade on a plinth

Geometry: CadQuery makes the lofts and primitives; all booleans run in manifold3d
(LESSONS.md: OCC booleans on these lofts are slow and fragile).
"""
import math
import sys
from pathlib import Path

import cadquery as cq
import manifold3d as mf
import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[2] / "cad"))   # kitlib (append: hawk/cad wins)
import kitlib as K  # noqa: E402

# ============================================================
# PARAMETERS
# ============================================================
SCALE = 40.0                 # shape scale: all lengths below are at 1:40
KIT_SCALE = 32.0             # print scale
PRINT_K = SCALE / KIT_SCALE  # 1.25: every part is scaled by this when written out
SPAN = 9390.0 / SCALE        # 234.75 mm at 1:40 (293.4 mm printed)
_P = 1.0 / PRINT_K           # print-size lengths (fits, pins) are given at print size times this

# --- Fit and printing (X2D, PLA; Halifax fit test, see LESSONS.md), at print size
FIT = 0.15 * _P              # mm, sliding clearance per side
KEY_FIT = 0.15 * _P          # printed key press fit per side
KEY_END_GAP = 0.3 * _P
AXLE_HOLE_TIGHT = 2.35 * _P  # printed 1.8 mm pins grip here
AXLE_HOLE_LOOSE = 2.65 * _P  # ...and spin here
PIN_D = 1.8 * _P
PIN_HEAD = (3.6 * _P, 0.8 * _P)
# Keys are few and big (about 17 x 9 x 4 mm printed): small ones were fiddly to handle.
KEY_FR = (14.0, 7.0, 3.0)    # fuselage joint keys: length across the split, width (z), thickness (y)
KEY_FIN = (10.0, 7.0, 2.6)   # fin halves, in the spine cap (across the split, along x, thickness z)

# --- Fuselage main body: (x, half_width, z_top, z_bottom, squareness)
# Plan half-widths from the Revell top view (the fuselage edge itself, about 11.5 behind the
# cockpit, not the wing-root and pod outline outside it); top/bottom lines from the side view.
# z_top is the shoulder/deck line: the canopy and dorsal spine are a separate loft.
FUSE_STATIONS = [
    # x, half_width, z_top, z_bottom, squareness  (front: symmetric superellipse; top = deck line)
    (0.8,   1.6,   0.6,  -0.6, 2.0),
    (2.4,   4.6,   2.0,  -2.0, 2.0),
    (5.4,   7.2,   3.9,  -3.4, 2.1),
    (8.4,   8.0,   5.2,  -4.4, 2.2),
    (11.3,  8.6,   6.1,  -5.0, 2.2),
    (17.3, 10.0,   8.2,  -6.2, 2.3),
    (23.3, 10.9,   9.9,  -7.0, 2.4),
    (29.2, 11.4,  11.4,  -7.4, 2.5),
    (38.5, 11.3,  13.6,  -7.7, 2.7),
    (53.0, 11.4,  15.4,  -7.9, 3.0),
    (70.0, 11.4,  17.5,  -8.2, 3.0),
    (90.0, 11.5,  20.0,  -8.4, 3.0),
    (110.0, 11.7, 22.0,  -8.5, 3.0),
    (124.0, 11.8, 23.0,  -8.3, 2.9),
    # behind the cockpit the body takes the whole top line (no separate spine): an "egg"
    # section, widest at z_w, rounder above (n_up) than below. x, hw, top, bottom, n_lo, z_w, n_up
    (134.0, 11.8, 33.6,  -8.0, 2.6, 13.0, 2.7),     # upright sides behind the canopy (photos):
    (140.0, 11.7, 35.5,  -7.9, 2.6, 13.0, 2.7),     # widest higher up and squarer above, so
    (152.6, 11.6, 33.6,  -7.4, 2.5, 12.5, 2.6),     # the side runs up flat and only rounds
    (166.7, 11.6, 32.4,  -6.7, 2.5, 12.0, 2.5),     # over near the top
    (180.9, 11.6, 31.2,  -5.2, 2.4, 11.0, 2.35),
    (195.0, 11.6, 29.2,  -3.9, 2.4, 9.5, 2.15),
    (208.0, 11.5, 27.6,  -3.0, 2.3, 8.0, 2.0),
    (226.0, 11.2, 25.9,  -2.0, 2.2, 8.0, 2.0),
    (240.0, 10.8, 24.6,  -1.3, 2.3, 8.0, 2.5),
    (252.0, 10.0, 23.0,  -0.6, 2.5, 8.0, 3.2),     # nearly level to the end (Revell side view),
    (264.2,  8.8, 20.2,   1.0, 2.7, 7.8, 3.8),     # squared off: flat top edge at the end (photos)
]
FUSE_END_X = 264.2
# Canopy and dorsal spine: (x, half_width, z_top); bottom is buried 6 mm in the body
SPINE_STATIONS = [            # canopy and the fairing just behind it (aft of x 140 the body takes over)
    (37.0,  8.6, 13.0),
    (41.0,  9.4, 15.6),
    (47.0, 10.0, 19.4),
    (59.7, 10.4, 24.2),
    (68.0, 10.6, 28.6),
    (76.6, 10.7, 32.4),
    (90.8, 10.7, 36.0),
    (105.0, 10.7, 37.3),
    (112.0, 10.6, 37.3),
    (126.1, 10.2, 36.2),
    (138.8,  9.6, 35.2),
    (142.0,  9.0, 34.4),
]
SPINE_N = 2.3
NOSE_SPLIT_X = 86.0          # nose/middle section joint (the radome is part of the nose section)
NOSE_KEYS = [(0.0, -1.5), (0.0, 9.5)]   # (y, z) of the KEY_FR keys on that joint
PROBE = (24.0, 2.4, 1.6, 3.6, 3.0)    # length, base d, tip d, boss d, boss length: shorter and
                                      # thicker than scale (34 x 1.6) so it survives handling
FUSE_SPLIT_X = 179.5         # middle/rear section joint: between the lettering and the roundel
FR_KEYS = [(-5.5, 5.0), (5.5, 5.0), (0.0, 19.0)]   # (y, z) on the joint face (below the fin cap at z 24)

# --- Intakes: D-section fairings each side, (x, y_outer, z_top, z_bottom)
INTAKE_STATIONS = [            # x, y_outer, z_top, z_bottom: the side pods (intake trunks)
    # boxy D-section pods (cross-sections checked against a reference Hawk model). Side views:
    # the top edge climbs quickly behind the inlet, then runs nearly level and sweeps back
    # into the fuselage side below the spine; the outer side tapers in over the same length.
    (89.0, 20.0, 12.0, -3.6),      # rounded lip (head-on photo)
    (89.6, 20.5, 12.5, -4.1),
    (90.5, 20.9, 12.9, -4.5),
    (92.5, 21.4, 13.5, -5.2),
    (98.0, 21.7, 14.2, -6.0),      # top climbs a little behind the inlet, staying well clear of
    (104.0, 21.8, 14.6, -6.4),     # the canopy sill (head-on photo). Widest here, then the
    (110.0, 21.3, 14.9, -6.4),     # sides turn in at once (convex shoulder, reference model)...
    (118.0, 20.0, 15.1, -6.3),     # behind the wing LE the pod sits on the wing:
    (126.0, 18.4, 15.1, -6.0),     # keep its bottom above the wing underside (no slivers)
    (134.0, 16.8, 14.8, -5.4),     # ...and taper almost straight back...
    (142.0, 15.2, 14.2, -4.4),
    (150.0, 13.8, 13.4, -2.6),     # ...easing into the body side (concave): the bottom rises up
    (158.0, 12.6, 12.4, 0.0),      # the fuselage side as the pod tapers in, so nothing sticks
    (166.0, 11.9, 11.2, 3.0),      # out below
    (174.0, 11.4, 10.0, 6.0),
]
INTAKE_Y_IN = 10.8           # inner edge of the pods, just inside the body side: their rounded
                             # inner top corner leaves a notch, so they read as separate at the inlet
INTAKE_N = 3.0               # boxy pods (reference model cross-sections)
INTAKE_MOUTH = (91.0, 18.0)  # x of the lip, depth of the duct (deep: reads dark)
INTAKE_OPENING = (0.6, 2.2, 8.6, -0.7, 2.5)   # inner lip (outside the splitter gap), outer lip,
                             # z top, z bottom, superellipse exponent. Head-on photo: the opening
                             # is a rounded oval, ~2/3 of the pod's visible width and ~1/2 its
                             # height, with a thick outer lip and deep lips above and below
SPLITTER_GAP = 0.6           # mm, boundary-layer gap between the lip and the fuselage

# --- Canopy (cut with a sloping plane through these two (x, z) points)
CANOPY_X = (36.0, 140.0)
CANOPY_PLANE = ((36.0, 13.3), (126.0, 27.6))     # through the ends of the sill line, so the whole
                                                 # sill lies on or below it: the canopy part has no
                                                 # red, and its bottom edge is straight
CANOPY_REAR = ((122.0, 40.0), (125.0, 21.0))     # rear frame of the glazing, nearly upright (HobbyBoss)
# Visible lower edge of the glazing (x, z): level under the front cockpit, curving up under the
# rear seat (HobbyBoss side view, shifted to our windscreen base). The part is cut on the flat
# CANOPY_PLANE just above it (it prints on it), and that cut is the visible bottom edge: the
# fuselage stays red below it. The sill line still places the frames and the nose dome.
CANOPY_SILL = [(36.0, 13.3), (49.8, 14.7), (68.3, 16.0), (81.7, 18.0), (95.1, 20.7),
               (108.5, 23.4), (122.0, 26.7), (126.0, 27.6)]
CANOPY_TABS = [(64.0, 78.0), (96.0, 112.0)]   # x ranges of the tabs moulded on the fuselage
                                              # (one per section), which the canopy drops onto
CANOPY_TAB = (5.0, 4.0)      # width (y), height above the sill plane; the aft end is chamfered
                             # (the sections print nose up, so it would overhang)

# --- Wing planform (Revell top view, both halves averaged):
# LE x = 102.8 + 55.8 eta, TE x = 169.3 + 12.3 eta, y = eta * SPAN/2
WING_LE = (102.8, 55.8)
WING_TE = (169.3, 12.3)
WING_TIP_ROUND = 3.0
TC_ROOT, TC_TIP = 0.109, 0.090
Z_FLOOR = -7.6               # wing underside at the centreline
DIHEDRAL = 2.0               # deg
WING_FLAT_FROM = 0.15
WING_LE_ANGLE = 50.0         # degrees: the underside rises no shallower than this to the leading edge
WING_TE_T = 0.6
WING_ROOT_Y = 6.0            # panel starts here (inside the fuselage, trimmed by it)
ROOT_TONGUE = {-1: (117.0, 131.0), 1: (137.0, 151.0)}   # port forward, starboard aft
ROOT_TONGUE_Z = (1.5, 4.9)   # above the floor
WALL = 1.6

# --- Tailplane (10 deg anhedral)
TAIL_LE = (220.4, 38.9)      # LE x = a + b eta
TAIL_TE = (260.1, 12.7)
TAIL_SEMISPAN = 53.7
TAIL_ROOT_Y = 8.5            # pivot line at the fuselage side
TAIL_FLOOR = 15.2            # underside at the root
TAIL_ANHEDRAL = 10.0
TAIL_TC = 0.10
TAIL_TONGUE = {-1: (231.0, 240.0), 1: (244.0, 253.0)}
TAIL_TONGUE_Z = (0.8, 3.1)

# --- Fin (separate, two halves): straight LE/TE lines from the side view
FIN_LE = ((206.3, 32.6), (245.9, 70.2))
FIN_TE = ((250.9, 24.9), (260.0, 70.8))
FIN_TOP = 70.5
FIN_ROOT_Z = 24.0            # fin root (the spine is cut flat here to take it)
FIN_TC = 0.10               # real ~8.5%; 10% leaves wall round the half keys
FIN_TONGUE = (210.0, 244.0, 4.0)   # x0, x1, depth of the root tongue into the spine
FIN_KEYS = [(189.0, 26.5), (201.0, 26.5)]   # keys in the thick spine cap: (x, z)

# --- Jet pipe
JET_PIPE = (7.0, 5.4, 6.8)   # (old blind pipe) depth, radius, z centre: the nozzle part replaces it
# Jet nozzle (separate part, plugs into the tail): radius of the visible ring, how far it stands
# out of the tail, wall, spigot radius and length into the fuselage, depth of the void.
NOZZLE = dict(r=5.0, out=3.0, wall=1.0, spig_r=4.0, spig_len=8.0, void=10.0)   # r 5.0 keeps 0.7 mm
                                                                                 # of tail below the socket

# --- Smoke pod (centreline): (fraction of length, radius) profile
POD_X0, POD_LEN = 92.0, 95.0
POD_PROFILE = [(0.0, 0.8), (0.03, 2.6), (0.10, 4.2), (0.22, 5.0), (0.75, 5.0), (0.92, 4.4), (1.0, 3.0)]
POD_PYLON = (8.0, 2.6, 3.0)   # fore/aft inset, half-width, height
POD_KEYS = [0.116, 0.72]     # pylon pegs: the front one sits ahead of the port wing tongue (X 117-124)
POD_KEY = 4.0

# --- Landing gear
NOSE_GEAR_X = 40.0           # photos: the nose wheel sits well forward
MAIN_GEAR = (150.0, 43.0)    # x, |y| of the main leg socket (rear spar); track 3.47 m
MAIN_TRAIL = 18.0            # mm the axle trails behind the socket (wheels sit near the wing TE)
MAIN_PLUG_DEPTH = 2.6        # the wing is 4.1 mm thick here: keep >= 0.8 mm above the socket
MAIN_WHEEL = (15.0, 5.0)     # diameter, width
NOSE_WHEEL = (11.0, 4.0)
GEAR_DROP = 22.0

# --- Display stand
STAND_X = 134.0              # between the port and starboard wing tongues
STAND_KEY = 5.0
STAND_KEY_DEPTH = 8.0
STAND_PITCH = 6.0
STAND_HEIGHT = 85.0
STAND_BASE = (120.0, 80.0, 10.0)   # length, width, thickness at 1:40 (150 x 100 mm printed)
STAND_BASE_DX = 18.0
STAND_BASE_R = 10.0
STAND_BASE_BEVEL = 3.0
STAND_FOOT_DX = 50.0
STAND_BLADE = (16.0, 8.0, 6.5)
STAND_TENON = (11.0, 4.0, 8.0)
STAND_BOSS = (32.0, 15.0, 3.0)

OUT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out")

# ============================================================
# HELPERS (CadQuery for lofts, manifold3d for booleans)
# ============================================================
V = cq.Vector
W = cq.Workplane
M = mf.Manifold


def interp(table, x):
    for a, b in zip(table, table[1:]):
        if x <= b[0] or b is table[-1]:
            t = (x - a[0]) / (b[0] - a[0])
            return tuple(pa + t * (pb - pa) for pa, pb in zip(a, b))
    return table[-1]


def to_m(w, tol=0.02, ang=0.12):
    """CadQuery Workplane/Shape -> Manifold (via a tessellated mesh)."""
    import trimesh
    shapes = w.vals() if hasattr(w, "vals") else [w]
    verts, tris = [], []
    for s in shapes:
        v, t = s.tessellate(tol, ang)
        off = len(verts)
        verts += [(p.x, p.y, p.z) for p in v]
        tris += [(a + off, b + off, c + off) for a, b, c in t]
    tm = trimesh.Trimesh(verts, tris, process=True)
    tm.merge_vertices()
    if tm.volume < 0:
        tm.invert()
    m = K.to_manifold(tm)
    if m.status() != mf.Error.NoError:
        raise RuntimeError(f"not manifold: {m.status()}")
    return m


def box(x0, x1, y0, y1, z0, z1):
    return K.box(x0, x1, y0, y1, z0, z1)


def cyl(p, d, length, axis, seg=48):
    """Cylinder from point p along +axis (negative length goes the other way)."""
    if length < 0:
        p = list(p)
        p["xyz".index(axis)] += length
        length = -length
    c = M.cylinder(length, d / 2, d / 2, seg)
    if axis == "x":
        c = c.rotate([0, 90, 0])
    elif axis == "y":
        c = c.rotate([-90, 0, 0])
    return c.translate(list(p))


def cone_x(x0, d0, x1, d1, y=0.0, z=0.0, seg=32):
    return M.cylinder(x1 - x0, d0 / 2, d1 / 2, seg).rotate([0, 90, 0]).translate([x0, y, z])


def rot_about(m, axis_pt, axis, deg):
    """Rotate a Manifold by deg about a line through axis_pt parallel to axis ('x'|'y'|'z')."""
    r = [0, 0, 0]
    r["xyz".index(axis)] = deg
    return m.translate([-a for a in axis_pt]).rotate(r).translate(list(axis_pt))


def union(ms):
    ms = [m for m in ms if m is not None]
    return M.batch_boolean(ms, mf.OpType.Add) if len(ms) > 1 else ms[0]


def superellipse_pts(x, yc, hw, z_top, z_bot, n, pts=64):
    zc, hh = (z_top + z_bot) / 2, (z_top - z_bot) / 2
    out = []
    for i in range(pts):
        t = 2 * math.pi * i / pts
        c, s = math.cos(t), math.sin(t)
        out.append(V(x, yc + hw * math.copysign(abs(c) ** (2 / n), c),
                     zc + hh * math.copysign(abs(s) ** (2 / n), s)))
    return out


def superellipse_wire(x, hw, z_top, z_bot, n, yc=0.0):
    p = superellipse_pts(x, yc, hw, z_top, z_bot, n)
    return cq.Wire.assembleEdges([cq.Edge.makeSpline(p, periodic=True)])


def egg_wire(x, hw, z_top, z_bot, n_lo, z_w=None, n_up=None, pts=64):
    """Section widest at z_w: upper half a superellipse of exponent n_up up to z_top,
    lower half exponent n_lo down to z_bot (z_w=None: the symmetric superellipse)."""
    if z_w is None:
        return superellipse_wire(x, hw, z_top, z_bot, n_lo)
    out = []
    for i in range(pts):
        t = 2 * math.pi * i / pts
        c, s_ = math.cos(t), math.sin(t)
        n = n_up if s_ >= 0 else n_lo
        h = (z_top - z_w) if s_ >= 0 else (z_w - z_bot)
        out.append(V(x, hw * math.copysign(abs(c) ** (2 / n), c), z_w + h * math.copysign(abs(s_) ** (2 / n), s_)))
    return cq.Wire.assembleEdges([cq.Edge.makeSpline(out, periodic=True)])


def loft(wires, ruled=False):
    s = cq.Solid.makeLoft(wires, ruled)
    if s.Volume() < 0:
        s = cq.Solid.makeLoft(list(reversed(wires)), ruled)
    return s


def _revolve_x(profile, seg=64):
    """Solid of revolution about the X axis from [(x, r), ...]."""
    pts = np.array([(max(r, 1e-3), x) for x, r in profile])
    poly = np.vstack([[0.0, profile[0][0]], pts, [0.0, profile[-1][0]]])
    m = M.revolve(mf.CrossSection([poly]), seg)          # about Y, then Y becomes Z
    return m.transform(np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0]], float))


def mesh_tm(m):
    import trimesh
    Vv, F = K.mesh_of(m)
    return trimesh.Trimesh(Vv, F, process=False)


KEY_COUNTS = {}

# ============================================================
# OUTER SHAPE
# ============================================================
def fuse_at(x):
    """(x, half_width, z_top, z_bottom, n) at x (z_top: the body top line)."""
    a = [s[:5] for s in FUSE_STATIONS]
    return interp(a, x)


def spine_top(x):
    return interp(SPINE_STATIONS, x)[2] if x <= SPINE_STATIONS[-1][0] else fuse_at(x)[2]


_CACHE = {}


def cached(fn):
    def f(*a):
        k = (fn.__name__,) + a
        if k not in _CACHE:
            _CACHE[k] = fn(*a)
        return _CACHE[k]
    f.__name__ = fn.__name__
    return f


@cached
def body():
    return to_m(loft([egg_wire(*s) for s in FUSE_STATIONS]))


def canopy_line(step=2.0):
    """The canopy top line as one continuous curve: a smoothing spline through the measured
    points (they wobble by a few tenths), resampled densely, so the ruled loft follows it exactly."""
    from scipy.interpolate import UnivariateSpline
    t = np.array(SPINE_STATIONS, float)
    xs = np.arange(t[0, 0], t[-1, 0] + 1e-6, step)
    sz = UnivariateSpline(t[:, 0], t[:, 2], k=3, s=len(t) * 0.12)
    sw = UnivariateSpline(t[:, 0], t[:, 1], k=3, s=len(t) * 0.02)
    return [(x, float(sw(x)), float(sz(x))) for x in xs]


CANOPY_BULGE = (1.03, 2.5)     # width factor, height of the widest point above the sill
CANOPY_BULGE_X = (118.0, 134.0)   # bulge eases out over this x range (behind the glazing)
CANOPY_BULGE_X0 = (48.0, 62.0)    # and eases in over this one (behind the windscreen base)
CANOPY_N = (3.0, 2.15)         # egg exponents: below / above the widest point
WINDSCREEN_NOSE = (38.5, 10.5)   # x of the windscreen tip, length of its rounded front (Revell plan view)


def windscreen_k(x):
    """Plan-view width factor: the windscreen front is a rounded U, not a full-width sliver."""
    x0, L = WINDSCREEN_NOSE
    t = (x - x0) / L
    return 1.0 if t >= 1.0 else math.sqrt(max(0.0, 1.0 - (1.0 - t) ** 2))


@cached
def spine():
    ws = []
    x0, L = WINDSCREEN_NOSE
    for x, hw, top in canopy_line(1.0):
        if x < x0 + 0.4:
            continue
        bot = min(fuse_at(x)[2], 24.0) - 6.0
        # over the cockpit the glazing bulges out just above the sill and rounds over the top
        # (head-on photo): an egg section, widest CANOPY_BULGE[1] mm above the sill. Behind the
        # canopy it eases back to the plain spine section.
        t = float(np.clip((x - CANOPY_BULGE_X[0]) / (CANOPY_BULGE_X[1] - CANOPY_BULGE_X[0]), 0, 1))
        zw = (1 - t) * (canopy_sill_z(x) + CANOPY_BULGE[1]) + t * (top + bot) / 2
        zw = min(zw, top - 3.0)
        t0 = float(np.clip((x - CANOPY_BULGE_X0[0]) / (CANOPY_BULGE_X0[1] - CANOPY_BULGE_X0[0]), 0, 1))
        hw = max(0.6, hw * windscreen_k(x) * (1 + (CANOPY_BULGE[0] - 1) * (1 - t) * t0))
        if t0 < 1.0:                     # windscreen: widest point eases down from mid-height
            zw = t0 * zw + (1 - t0) * (top + bot) / 2
        ws.append(egg_wire(x, hw, top, bot, CANOPY_N[0], zw, CANOPY_N[1]))
    return to_m(loft(ws, ruled=True))


def dense(table, step=3.0):
    """Stations resampled every `step` mm with a shape-preserving (PCHIP) curve: ruled lofts through
    these never overshoot, unlike smooth lofts through sparse, unevenly spaced stations."""
    from scipy.interpolate import PchipInterpolator
    t = np.asarray(table, float)
    xs = np.unique(np.r_[np.arange(t[0, 0], t[-1, 0], step), t[:, 0]])
    return [tuple([x] + [float(PchipInterpolator(t[:, 0], t[:, j])(x)) for j in range(1, t.shape[1])])
            for x in xs]


@cached
def intake_fairing(side):
    ws = []
    for x, yo, zt, zb in dense(INTAKE_STATIONS):
        yc = (yo + INTAKE_Y_IN) / 2
        ws.append(superellipse_wire(x, (yo - INTAKE_Y_IN) / 2, zt, zb, INTAKE_N, yc * side))
    return to_m(loft(ws, ruled=True))


@cached
def intake_mouth(side):
    """Duct recess behind the lip: a rounded oval well inside the pod front (thick lips)."""
    x0, depth = INTAKE_MOUTH
    lip_in, lip_out, zt, zb, n = INTAKE_OPENING
    yo = INTAKE_STATIONS[3][1] - lip_out
    ws = []
    for x in (x0 - 2.0, x0 + depth):
        yi = fuse_at(x0)[1] + SPLITTER_GAP + lip_in
        ws.append(superellipse_wire(x, (yo - yi) / 2, zt, zb, n, side * (yo + yi) / 2))
    return to_m(loft(ws, ruled=True))


def splitter_gap(side):
    """Slot between the intake lip and the body (boundary-layer splitter), 6 mm deep."""
    x0 = INTAKE_MOUTH[0]
    _, yo, zt, zb = INTAKE_STATIONS[3]
    yi = fuse_at(x0)[1]
    y0, y1 = sorted((side * (yi - 0.2), side * (yi + SPLITTER_GAP)))
    return box(x0 - 3.0, x0 + 6.0, y0, y1, zb + 1.0, zt - 1.0)


BLEND_R = ((80.0, 92.0, 118.0, 145.0, 165.0), (6.0, 1.2, 1.5, 2.5, 6.0))   # fillet radius vs x: soft at the canopy,
                             # tight at the inlet (pods nearly separate), soft again where they fade
BLEND_X = (34.0, 192.0)      # x range of the blend (from ahead of the windscreen to behind the pods)
BLEND_ZC = 4.0               # z of the polar centre used to resample each section
BLEND_N = 144                # points per section
BELLY_Z = 2.0                # below this z each section is filled to its hull (flush pod undersides)
BELLY_R = 6.5                # mm, radius of the pods' lower outer corners


HULL_X0 = 60.0               # from just behind the windscreen frame: convex sections above the pods
HULL_DZ = 0.6                # mm above the pod top where the hull starts


def _section_x(m, x):
    """CrossSection (y, z) of a manifold at x."""
    r = m.translate([-x, 0, 0]).rotate([0, -90, 0])      # x -> z
    sec = r.slice(0.0)
    return sec                                            # coords: (-z, y) after the rotation


@cached
def pod_blend():
    """Body + canopy + pods, section by section, with the concave creases closed (offset +r
    then -r), resampled radially and lofted ruled: the pods and the canopy blend into the
    fuselage with no seam or ledge."""
    import shapely.geometry as sg
    base = union([body(), spine(), intake_fairing(1), intake_fairing(-1)])
    nose = union([body(), spine()])        # ahead of the intake lip: no pods (a ruled step into
                                           # them would plug the front of the intakes)
    ws = []
    th = np.linspace(0, 2 * math.pi, BLEND_N, endpoint=False)
    for x in np.arange(BLEND_X[0], BLEND_X[1] + 1e-6, 1.5):
        sec = _section_x(base if x >= INTAKE_MOUTH[0] else nose, x)
        # flush underside: below BELLY_Z the section is filled to its convex hull, so the pod
        # bottoms run straight into the belly (no dip between pod and fuselage)
        lo = sec ^ mf.CrossSection.square([60.0, 80.0]).translate([-BELLY_Z, -40.0])
        if not lo.is_empty():
            sec = sec + lo.hull()
            # round the pods' lower outer corners with a large radius, so their sides flow
            # into the belly instead of ending at a hard edge (below BELLY_Z only)
            rounded = sec.offset(-BELLY_R, mf.JoinType.Round, circular_segments=48).offset(
                BELLY_R, mf.JoinType.Round, circular_segments=48)
            low = mf.CrossSection.square([60.0, 80.0]).translate([-BELLY_Z, -40.0])
            sec = (sec - low) + (rounded ^ low)
        if x >= HULL_X0:
            # convex upper fuselage (photos): above the pod tops each section is filled to its
            # hull, so canopy, spine and body meet with flat, upright sides and no waist or groove;
            # the pods and the notch beside them (below) are left alone
            zc = float(np.interp(x, [s_[0] for s_ in INTAKE_STATIONS], [s_[2] for s_ in INTAKE_STATIONS])) + HULL_DZ
            up = sec ^ mf.CrossSection.square([80.0, 80.0]).translate([-zc - 80.0, -40.0])
            if not up.is_empty():
                sec = sec + up.hull()
        r = float(np.interp(x, BLEND_R[0], BLEND_R[1]))
        sec = sec.offset(r, mf.JoinType.Round, circular_segments=48).offset(
            -r, mf.JoinType.Round, circular_segments=48)
        polys = sec.to_polygons()
        P = max((sg.Polygon(np.asarray(p)) for p in polys), key=lambda q: q.area)
        pts = []
        for t in th:
            # section coords are (u, v) = (-z, y): centre at u = -BLEND_ZC
            d = np.array([-math.sin(t), math.cos(t)])      # direction for (y=cos, z=sin)
            c = np.array([-BLEND_ZC, 0.0])
            ray = sg.LineString([c, c + d * 80.0])
            hit = ray.intersection(P.exterior)
            ptsh = [hit] if hit.geom_type == "Point" else list(getattr(hit, "geoms", []))
            far = max(ptsh, key=lambda q: (q.x - c[0]) ** 2 + (q.y - c[1]) ** 2)
            u, v = far.x, far.y
            pts.append(V(x, v, -u))
        ws.append(cq.Wire.makePolygon(pts, close=True))
    return to_m(loft(ws, ruled=True))


@cached
def outer():
    """Body, canopy/spine and side pods (blended), without fin, wings, tail."""
    return union([body(), spine(), intake_fairing(1), intake_fairing(-1), pod_blend()])


# ============================================================
# WINGS AND TAILPLANE
# ============================================================
def flat_bottom_section(tc, chord, te_t=WING_TE_T, n=40, camber=0.012):
    """Cambered NACA 4-digit section, rotated so the underside is flat from WING_FLAT_FROM
    to the TE. Returns (nose_pts, flat_start, te_lower, te_upper); floor z=0, LE near x=0."""
    m, p = camber, 0.4
    up, lo = [], []
    for i in range(n + 1):
        x = (1 - math.cos(math.pi * i / n)) / 2
        yt = 5 * tc * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x**2
                       + 0.2843 * x**3 - 0.1036 * x**4) + x * (te_t / 2) / chord
        if m:
            yc = m / p**2 * (2 * p * x - x * x) if x < p else m / (1 - p)**2 * ((1 - 2 * p) + 2 * p * x - x * x)
            dyc = 2 * m / p**2 * (p - x) if x < p else 2 * m / (1 - p)**2 * (p - x)
        else:
            yc = dyc = 0.0
        th = math.atan(dyc)
        up.append(((x - yt * math.sin(th)) * chord, (yc + yt * math.cos(th)) * chord))
        lo.append(((x + yt * math.sin(th)) * chord, (yc - yt * math.cos(th)) * chord))
    k = min(range(1, len(lo) - 1), key=lambda i: abs(lo[i][0] / chord - WING_FLAT_FROM))
    xt, zt = lo[-1]
    a = -math.atan2(zt - lo[k][1], xt - lo[k][0])
    ca, sa = math.cos(a), math.sin(a)

    def rr(pp):
        x, z = pp[0] - xt, pp[1] - zt
        return (xt + x * ca - z * sa, x * sa + z * ca)
    up = [rr(pp) for pp in up]
    lo = [(x, max(z, 0.0)) for x, z in (rr(pp) for pp in lo[:k + 1])]
    lo[-1] = (lo[-1][0], 0.0)
    # Printability: the parts print on this flat underside, and the nose's lower curve rose
    # off the bed too gently (under 45 degrees) over the front 15% of chord. From the leading
    # edge it now drops at WING_LE_ANGLE to the bed and stays flat from there.
    xle, zle = lo[0]
    sl = math.tan(math.radians(WING_LE_ANGLE))
    lo = [lo[0]] + [(x, max(0.0, zle - sl * (x - xle))) for x, _ in lo[1:]]
    return list(reversed(up)) + lo[1:], lo[-1], (xt, 0.0), up[-1]


def section_wire(tc, chord, place, te_t=WING_TE_T):
    nose, flat0, te_lo, te_up = flat_bottom_section(tc, chord, te_t)
    pts = [place(*p) for p in nose]
    return cq.Wire.assembleEdges([cq.Edge.makeSpline(pts), cq.Edge.makeLine(place(*flat0), place(*te_lo)),
                                  cq.Edge.makeLine(place(*te_lo), place(*te_up))])


def panel(stations, zf, te_t=WING_TE_T):
    wires = [section_wire(tc, c, lambda px, pz, x=x, y=y: V(x + px, y, zf + pz), te_t)
             for y, x, c, tc in stations]
    return to_m(loft(wires, ruled=True))


def wing_plan(y):
    eta = y / (SPAN / 2)
    le = WING_LE[0] + WING_LE[1] * eta
    te = WING_TE[0] + WING_TE[1] * eta
    return le, te - le, TC_ROOT + (TC_TIP - TC_ROOT) * eta


@cached
def wing_flat():
    """Flat (no dihedral) starboard panel, floor at Z_FLOOR."""
    st = []
    tip = SPAN / 2
    for y in (WING_ROOT_Y, 40.0, 80.0, tip - WING_TIP_ROUND, tip - 1.2, tip):
        le, c, tc = wing_plan(y)
        if y > tip - WING_TIP_ROUND + 0.1:          # rounded LE corner at the tip
            t = (y - (tip - WING_TIP_ROUND)) / WING_TIP_ROUND
            cut = WING_TIP_ROUND * (1 - math.sqrt(max(0.0, 1 - t * t))) * 1.8
            le, c = le + cut, c - cut
        st.append((y, le, c, tc))
    return panel(st, Z_FLOOR)


DIHEDRAL_PT = (0.0, 0.0, Z_FLOOR)


def wing_assembled(side):
    w = rot_about(wing_flat(), DIHEDRAL_PT, "x", DIHEDRAL)
    return w if side > 0 else w.mirror([0, 1, 0])


def wing_tongue(side, grow=0.0):
    tx0, tx1 = ROOT_TONGUE[side]
    reach = 5.5                 # stops short of the other wing's root (it shows under the rounded belly)
    z0, z1 = Z_FLOOR + ROOT_TONGUE_Z[0], Z_FLOOR + ROOT_TONGUE_Z[1]
    g = grow
    b = box(tx0 - g, tx1 + g, -reach - (0.5 if g else 0), 18.0, z0 - g, z1 + g)
    return b if side > 0 else b.mirror([0, 1, 0])


@cached
def wing(side):
    return (wing_assembled(side) - body()) + wing_tongue(side)


def tail_plan(eta):
    le = TAIL_LE[0] + TAIL_LE[1] * eta
    te = TAIL_TE[0] + TAIL_TE[1] * eta
    return le, te - le


TAIL_PT = (0.0, TAIL_ROOT_Y, TAIL_FLOOR)


@cached
def tail_flat():
    st = []
    for y in (2.0, TAIL_ROOT_Y, 30.0, TAIL_SEMISPAN - 1.5, TAIL_SEMISPAN):
        le, c = tail_plan(y / TAIL_SEMISPAN)
        if y >= TAIL_SEMISPAN - 1.6:
            le, c = (le + 0.5, c - 1.0) if y < TAIL_SEMISPAN else (le + 2.0, c - 4.0)
        st.append((y, le, c, TAIL_TC))
    return panel(st, TAIL_FLOOR, te_t=0.5)


def tail_tongue(side, grow=0.0):
    tx0, tx1 = TAIL_TONGUE[side]
    z0, z1 = TAIL_FLOOR + TAIL_TONGUE_Z[0], TAIL_FLOOR + TAIL_TONGUE_Z[1]
    g = grow
    b = box(tx0 - g, tx1 + g, -5.0 - (0.5 if g else 0), TAIL_ROOT_Y + 4.0, z0 - g, z1 + g)
    b = rot_about(b, TAIL_PT, "x", -TAIL_ANHEDRAL)           # follows the panel
    return b if side > 0 else b.mirror([0, 1, 0])


@cached
def tailplane(side):
    t = tail_flat() ^ box(0, 400, TAIL_ROOT_Y - 3.0, 100, -50, 100)
    t = rot_about(t, TAIL_PT, "x", -TAIL_ANHEDRAL)
    if side < 0:
        t = t.mirror([0, 1, 0])
    return (t - body()) + tail_tongue(side)


# ============================================================
# FIN (two halves)
# ============================================================
FIN_FILLET_Z = 36.0          # below this the leading edge sweeps forward into the dorsal fillet
FIN_FILLET_K = (1.05, 1.3)    # LE offset forward = k * (FIN_FILLET_Z - z) ** p


def fin_le(z):
    (lx0, lz0), (lx1, lz1) = FIN_LE
    le = lx0 + (z - lz0) * (lx1 - lx0) / (lz1 - lz0)
    if z < FIN_FILLET_Z:
        k, pw = FIN_FILLET_K
        le -= k * (FIN_FILLET_Z - z) ** pw
    return le


def fin_te(z):
    (tx0, tz0), (tx1, tz1) = FIN_TE
    return tx0 + (z - tz0) * (tx1 - tx0) / (tz1 - tz0)


def fin_section(z):
    """Symmetric NACA 00xx section at height z. The fillet's long chords keep the thickness of
    the fin at FIN_FILLET_Z, so the fillet is a thin swept extension, not a fat wedge."""
    le, te = fin_le(z), fin_te(z)
    c = te - le
    c_t = min(c, fin_te(FIN_FILLET_Z) - fin_le(FIN_FILLET_Z))
    up, lo = [], []
    n = 36
    for i in range(n + 1):
        x = (1 - math.cos(math.pi * i / n)) / 2
        yt = 5 * FIN_TC * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x**2
                           + 0.2843 * x**3 - 0.1036 * x**4) * c_t + x * 0.25
        up.append(V(le + x * c, yt, z))
        lo.append(V(le + x * c, -yt, z))
    return cq.Wire.assembleEdges([cq.Edge.makeSpline(up), cq.Edge.makeLine(up[-1], lo[-1]),
                                  cq.Edge.makeSpline(list(reversed(lo)))])


FIN_X0 = 182.0               # fin part starts here (behind the section joint)


def fin_cap():
    """The rear fuselage top above the fin root plane: printed with the fin, cut from the fuselage."""
    return outer() ^ box(FIN_X0, 262.0, -30.0, 30.0, FIN_ROOT_Z, 80.0)


def fin_tongue(grow=0.0):
    x0, x1, depth = FIN_TONGUE
    g = grow
    return box(x0 - g, x1 + g, -1.3 - g, 1.3 + g, FIN_ROOT_Z - depth - (0.3 if g else 0), FIN_ROOT_Z + (1 if g else 0.01))


@cached
def fin_whole():
    zs = list(np.arange(FIN_ROOT_Z - 1.0, FIN_FILLET_Z, 1.0)) + [FIN_FILLET_Z, FIN_TOP]
    f = to_m(loft([fin_section(z) for z in zs], ruled=True))     # dense ruled loft: smooth fillet
    whole = (f + fin_cap()) ^ box(FIN_X0, 300, -30, 30, FIN_ROOT_Z, 100)
    return whole + fin_tongue()


def fin_seat():
    return fin_cap() + fin_tongue(FIT)


@cached
def fin_halves():
    f = fin_whole()
    pts = [(x, 0.0, z) for x, z in FIN_KEYS]
    slots = to_m(K.key_slots(pts, "y", 0.0, KEY_FIN, "x", KEY_FIT, KEY_END_GAP))
    KEY_COUNTS["key_fin"] = (KEY_FIN, len(pts))
    return f ^ box(0, 400, 0, 20, -50, 100), (f ^ box(0, 400, -20, 0, -50, 100)), slots


# ============================================================
# CANOPY
# ============================================================
@cached
def canopy_region(grow=0.0):
    """The glazing: inside the canopy bubble's plan footprint (so the deck beside it stays
    fuselage) and inside canopy_zone."""
    foot = spine().project().offset(grow, mf.JoinType.Round)
    return canopy_zone(grow) ^ K.prism_z(foot)


def canopy_sill_z(x):
    """Visible glazing edge (the painted sill line), smooth through CANOPY_SILL."""
    from scipy.interpolate import PchipInterpolator
    t = np.array(CANOPY_SILL)
    return float(PchipInterpolator(t[:, 0], t[:, 1])(np.clip(x, t[0, 0], t[-1, 0])))


def canopy_plane_z(x):
    (xa, za), (xb, zb) = CANOPY_PLANE
    return za + (x - xa) * (zb - za) / (xb - xa)


def canopy_angle():
    (xa, za), (xb, zb) = CANOPY_PLANE
    return math.degrees(math.atan2(zb - za, xb - xa))


def canopy_zone(grow=0.0):
    """Above the sill plane, behind the windscreen base and ahead of the slanted rear edge."""
    (xa, za), _ = CANOPY_PLANE
    x0, x1 = CANOPY_X
    blk = box(x0 - 20, x1 + 20, -30, 30, za - grow, za + 50)
    blk = rot_about(blk, (xa, 0, za), "y", -canopy_angle())
    (ra, rza), (rb, rzb) = CANOPY_REAR
    ang = math.degrees(math.atan2(rb - ra, rza - rzb))           # lean of the rear edge from vertical
    rear = rot_about(box(ra - 200, ra + grow, -30, 30, rzb - 30, rza + 30), (ra, 0, rza), "y", -ang)
    return blk ^ box(x0 - grow, x1 + grow, -30, 30, -10, 60) ^ rear


def canopy_tabs(grow=0.0):
    """Tabs standing on the sill plane, made level and tipped onto the plane. grow > 0: the
    canopy's pockets for them (clearance all round and 0.3 mm over the top)."""
    (xa, za), _ = CANOPY_PLANE
    w, h = CANOPY_TAB
    g = grow
    tabs = []
    for x0, x1 in CANOPY_TABS:
        prof = np.array([(x0 - g, za - 1.0), (x1 + g, za - 1.0), (x1 + g, za + 0.2),
                         (x1 - 0.9 * h + g, za + h + (0.3 if g else 0.0)), (x0 - g, za + h + (0.3 if g else 0.0))])
        tabs.append(K.cs([prof]).extrude(w + 2 * g).translate([0, 0, -(w / 2 + g)]).rotate([90, 0, 0]))
    return rot_about(union(tabs), (xa, 0, za), "y", -canopy_angle())


@cached
def canopy():
    """Solid and opaque, flat underneath, with pockets for the fuselage's tabs."""
    c = outer() ^ canopy_region(-FIT)
    c = c - canopy_tabs(FIT)
    return K.largest_piece(c)[0]


# ============================================================
# SMOKE POD, AERIALS, GEAR
# ============================================================
def pod_geom():
    zb = min(fuse_at(POD_X0 + f * POD_LEN)[3] for f in (0.25, 0.5, 0.75))
    r = max(r for _, r in POD_PROFILE)
    return zb, zb - POD_PYLON[2] - r


POD_PEG = (7.0, 3.2, 4.0)       # pegs moulded on the pylon top into the belly: length (x), width (y), height
POD_HALF_KEYS = [0.3, 0.7]      # pod halves keys (fraction of length)
KEY_POD_HALF = (7.0, 6.0, 2.5)


def pod_key_points():
    return [(POD_X0 + f * POD_LEN, 0.0, fuse_at(POD_X0 + f * POD_LEN)[3]) for f in POD_KEYS]


def pod_pegs(grow=0.0):
    """Pegs on the pod's pylon top (split down the middle with the pod halves, so each half
    prints its share flat); grow > 0 gives the belly sockets."""
    L, w, h = POD_PEG
    g = grow
    return union([box(x - L / 2 - g, x + L / 2 + g, -w / 2 - g, w / 2 + g, z - 2.0, z + h + (0.3 if g else 0.0))
                  for x, _, z in pod_key_points()])


def pod_key_slots():
    return pod_pegs(FIT)


@cached
def smoke_pod():
    """Pod (body of revolution) on a short pylon; two halves split on the centreline."""
    zb, zc = pod_geom()
    pod = _revolve_x([(POD_X0 + f * POD_LEN, rr) for f, rr in POD_PROFILE]).translate([0, 0, zc])
    i0, hw, _ = POD_PYLON
    pylon = box(POD_X0 + i0, POD_X0 + POD_LEN - i0, -hw, hw, zc, zb + 4.0)
    p = (pod + pylon) - body()
    k = STAND_KEY / 2 + FIT
    p = (p + pod_pegs()) - box(STAND_X - k, STAND_X + k, -k, k, zc - 20, zb + 1)
    pts = [(POD_X0 + f * POD_LEN, 0.0, zc) for f in POD_HALF_KEYS]
    slots = to_m(K.key_slots(pts, "y", 0.0, KEY_POD_HALF, "x", KEY_FIT, KEY_END_GAP))
    KEY_COUNTS["key_pod"] = (KEY_POD_HALF, len(pts))
    return (p ^ box(0, 400, 0, 50, -100, 100)) - slots, (p ^ box(0, 400, -50, 0, -100, 100)) - slots


def pod_sockets():
    return pod_key_slots()


AERIALS = [  # x, top|bottom, height, chord, sweep
    (143.0, "top", 6.0, 6.5, 3.0),     # UHF blade behind the canopy
    (68.0, "bottom", 4.5, 5.0, 2.0),   # under the nose
    (205.0, "bottom", 4.0, 5.0, 2.0),  # under the rear fuselage
]
AERIAL_T = 1.0


def aerial_base(a):
    x, where, *_ = a
    return spine_top(x + 3.0) if where == "top" else fuse_at(x + 3.0)[3]


def aerial(a, slot=False):
    x, where, h, c, sweep = a
    zs = aerial_base(a)
    sg = 1 if where == "top" else -1
    if slot:
        g = FIT
        z0, z1 = sorted((zs - sg * 3.3, zs + sg * 0.5))
        return box(x - g, x + c + g, -AERIAL_T / 2 - g, AERIAL_T / 2 + g, z0, z1)
    pts = np.array([(x, zs - sg * 3.0), (x + c, zs - sg * 3.0), (x + c, zs + sg * 0.3),
                    (x + c * 0.5 + sweep, zs + sg * h), (x + c * 0.15 + sweep, zs + sg * h), (x, zs + sg * 0.3)])
    if sg < 0:
        pts = pts[::-1]
    return K.cs([pts]).extrude(AERIAL_T).translate([0, 0, -AERIAL_T / 2]).rotate([90, 0, 0])


def gear_socket_nose():
    zb = fuse_at(NOSE_GEAR_X)[3]
    return box(NOSE_GEAR_X - 2.2 - FIT, NOSE_GEAR_X + 2.2 + FIT, -2.2 - FIT, 2.2 + FIT, zb - 1, zb + 6.3)


def wheel_m(x, yc, z_axle, d, w):
    tyre = cq.Workplane("XZ").circle(d / 2).extrude(w / 2, both=True).edges().fillet(min(1.5, w / 3))
    t = to_m(tyre)
    for s in (-1, 1):
        t = t - cyl((0, s * (w / 2 + 0.1), 0), d * 0.58, -s * 0.7, "y")
        t = t + cyl((0, s * (w / 2 - 0.6), 0), d * 0.26, s * 0.45, "y")
    t = t - cyl((0, -w, 0), AXLE_HOLE_LOOSE, 2 * w, "y")
    return t.translate([x, yc, z_axle])


def nose_gear():
    zb = fuse_at(NOSE_GEAR_X)[3]
    d, w = NOSE_WHEEL
    x = NOSE_GEAR_X + 3.0
    z_axle = zb - GEAR_DROP + 1.0 + d / 2
    yo = w / 2 + 0.5 + 1.2
    f = union([box(NOSE_GEAR_X - 2.0, NOSE_GEAR_X + 2.0, -2.0, 2.0, z_axle + d / 2 + 1.0, zb - 0.1),   # oleo
               box(NOSE_GEAR_X - 2.2, NOSE_GEAR_X + 2.2, -2.2, 2.2, zb - 0.2, zb + 6.0),                # plug
               box(NOSE_GEAR_X - 2.0, x + 2.0, -yo - 1.2, yo + 1.2, z_axle + d / 2 + 0.3, z_axle + d / 2 + 2.6)]
              + [box(x - 2.0, x + 2.0, s * yo - 1.2, s * yo + 1.2, z_axle - 2.0, z_axle + d / 2 + 2.6)
                 for s in (1, -1)])
    f = f - cyl((x, -20, z_axle), AXLE_HOLE_TIGHT, 40, "y", 24)
    return f, (x, z_axle, yo + 1.2)


def wing_underside_z(y):
    return Z_FLOOR + abs(y) * math.tan(math.radians(DIHEDRAL))


def main_gear(side):
    x, y = MAIN_GEAR
    y *= side
    zb = wing_underside_z(y)
    d, w = MAIN_WHEEL
    z_axle = zb - GEAR_DROP + d / 2
    xa = x + MAIN_TRAIL
    L = math.hypot(xa - x, zb - z_axle)
    ang = math.degrees(math.atan2(xa - x, zb - z_axle))                     # leg raked aft
    leg = rot_about(box(x - 2.0, x + 2.0, y - 2.0, y + 2.0, zb - L - 2.0, zb - 0.1), (x, y, zb), "y", -ang)
    leg = leg - box(x - 20, x + 40, y - 10, y + 10, zb - 0.1, zb + 20)   # trimmed flush under the wing
    f = union([leg,
               box(x - 2.2, x + 2.2, y - 2.2, y + 2.2, zb - 0.2, zb + MAIN_PLUG_DEPTH),   # plug
               box(xa - 2.6, xa + 2.6, y - 2.0, y + 2.0, z_axle - 2.6, z_axle + 2.6)])  # axle boss
    f = f - cyl((xa, y - 20, z_axle), AXLE_HOLE_TIGHT, 40, "y", 24)
    axle_y = y + side * (2.0 + 0.5 + w / 2)
    return f, (xa, axle_y, z_axle)


def main_socket(side):
    x, y = MAIN_GEAR
    y *= side
    zb = wing_underside_z(y)
    return box(x - 2.2 - FIT, x + 2.2 + FIT, y - 2.2 - FIT, y + 2.2 + FIT, zb - 1, zb + MAIN_PLUG_DEPTH + 0.3)


def axle_pin(start, axis, sign, length, head=True):
    p = cyl(start, PIN_D, sign * length, axis, 20)
    if head:
        q = list(start)
        q["xyz".index(axis)] -= sign * PIN_HEAD[1]
        p = p + cyl(q, PIN_HEAD[0], sign * PIN_HEAD[1], axis, 24)
    return p


# ============================================================
# FUSELAGE SECTIONS
# ============================================================
def jet_pipe_cut():
    """Socket in the tail for the nozzle's spigot, countersunk for its chamfered flange."""
    n, zc = NOZZLE, JET_PIPE[2]
    r = n["spig_r"] + FIT
    sock = cyl((FUSE_END_X - n["spig_len"] - 0.4, 0, zc), 2 * r, n["spig_len"] + 1.4, "x", 64)
    cham = n["r"] - n["spig_r"]
    return sock + cone_x(FUSE_END_X - cham - 0.01, 2 * r, FUSE_END_X + 0.01, 2 * (n["r"] + FIT), 0, zc)


@cached
def nozzle():
    """Jet nozzle: a ring standing out of the tail with a deep void, a stepped inner pipe, an
    exhaust cone and 6 struts at the bottom; a spigot plugs it into the tail. The flange's
    underside is chamfered at 45 degrees so it prints spigot-down without overhangs."""
    n, zc = NOZZLE, JET_PIPE[2]
    X = FUSE_END_X
    r, out, wall = n["r"], n["out"], n["wall"]
    sr, sl = n["spig_r"] - FIT, n["spig_len"]
    cham = r - sr                                                   # 45 degrees
    body = (cyl((X - sl, 0, zc), 2 * sr, sl + 0.01, "x", 64)
            + cone_x(X - cham, 2 * sr, X + 0.01, 2 * r, 0, zc)
            + cyl((X, 0, zc), 2 * r, out, "x", 96))
    lip = cone_x(X + out - 0.6, 2 * (r - wall), X + out + 0.01, 2 * (r - wall * 0.45), 0, zc)  # thin exit lip
    void = (cyl((X, 0, zc), 2 * (r - wall), out + 0.01, "x", 96)                # wide exit (not into
                                                                                 # the flange: too thin)
            + cyl((X + out - n["void"], 0, zc), 2 * (sr - 0.9), n["void"] - 3.9, "x", 64))   # deeper pipe
    floor = X + out - n["void"]
    cone = cone_x(floor - 0.01, 2 * (sr - 1.4), floor + 6.5, 0.6, 0, zc)        # exhaust cone
    struts = union([rot_about(box(floor - 0.01, floor + 1.6, -0.35, 0.35, zc, zc + sr), (0, 0, zc), "x", a)
                    for a in range(0, 360, 60)])
    ring = (cyl((X - 0.01, 0, zc), 2 * (r - wall), 0.6, "x", 96)                      # step ring at the
            - cyl((X - 5, 0, zc), 2 * (r - wall - 0.9), 20, "x", 96))                 # bottom of the exit
    return (body - void - lip) + cone + (struts ^ cyl((floor - 1, 0, zc), 2 * (sr - 0.6), 4, "x", 64)) + ring


# --- Small ram-air scoops on the spine shoulders, just behind the canopy (side photos)
SPINE_DUCT = (130.0, 144.0, 32.5, 3.6, 1.8)   # x front, x rear, z where it sits, width, height proud
SPINE_DUCT_MOUTH = (2.2, 1.0, 3.0)            # opening width, height, depth


def _surface_point(m, x, z):
    """(y, normal angle in degrees) where the starboard surface of m crosses height z at x."""
    import shapely.geometry as sg
    sec = _section_x(m, x)
    P = max((sg.Polygon(np.asarray(p)) for p in sec.to_polygons()), key=lambda q: q.area)
    hit = sg.LineString([(-z, 0.0), (-z, 80.0)]).intersection(P.exterior)
    pts = [hit] if hit.geom_type == "Point" else list(hit.geoms)
    y = max(q.y for q in pts)
    dz = 0.4
    hit = sg.LineString([(-(z + dz), 0.0), (-(z + dz), 80.0)]).intersection(P.exterior)
    ya = max(q.y for q in ([hit] if hit.geom_type == "Point" else list(hit.geoms)))
    return y, math.degrees(math.atan2(-(ya - y), dz))   # outward normal, degrees from +y


@cached
def spine_ducts():
    """Two teardrop scoops, blunt front with a forward-facing opening, tapering aft into the skin."""
    x0, x1, zc, w, h = SPINE_DUCT
    mw, mh, md = SPINE_DUCT_MOUTH
    o = outer()
    y0, phi = _surface_point(o, (x0 + x1) / 2, zc)
    ws = []
    for t in np.linspace(0.0, 1.0, 12):
        x = x0 + t * (x1 - x0)
        f = 0.85 + 0.15 * min(1.0, t / 0.2) if t < 0.2 else 1.0 - 0.85 * ((t - 0.2) / 0.8) ** 1.3
        ws.append(superellipse_wire(x, w / 2 * f, h * f, -2.0, 2.6, 0.0))
    body_ = to_m(loft(ws, ruled=True))
    mouth = box(x0 - 1.0, x0 + md, -mw / 2, mw / 2, h - mh - 0.35, h - 0.35)
    out = mf.Manifold()
    for side in (1, -1):
        d = (body_ - mouth).rotate([phi - 90.0, 0, 0]).translate([0, y0, zc])
        out = out + (d if side > 0 else d.mirror([0, 1, 0]))
    return out


@cached
def fuselage_body():
    """The whole fuselage (all sections) with every socket, pocket and cut."""
    b = outer() + spine_ducts()
    for s in (1, -1):                                   # intakes sit on the wing
        w = wing_assembled(s)
        b = b - w - w.translate([0, 0, FIT]) - w.translate([0, 0, -FIT])
    b = b - canopy_region() + canopy_tabs()
    for s in (1, -1):
        b = b - intake_mouth(s) - splitter_gap(s)
        b = b - wing_tongue(s, FIT) - tail_tongue(s, FIT)
    b = b - jet_pipe_cut()
    b = b - fin_seat()
    b = b - pod_sockets()
    zb = fuse_at(STAND_X)[3]
    k = STAND_KEY / 2 + FIT
    b = b - box(STAND_X - k, STAND_X + k, -k, k, zb - 1, zb + STAND_KEY_DEPTH + 0.3)
    b = b - gear_socket_nose()
    for a in AERIALS:
        b = b - aerial(a, slot=True)
    return b


@cached
def fuselage_sections():
    b = fuselage_body()
    nk = to_m(K.key_slots([(NOSE_SPLIT_X, y, z) for y, z in NOSE_KEYS], "x", NOSE_SPLIT_X, KEY_FR, "z",
                          KEY_FIT, KEY_END_GAP))
    L, d0, d1, bd, bl = PROBE
    probe = cyl((-bl + 0.4, 0, 0), bd, bl + 2.6, "x", 24) + cone_x(-bl - L + 0.4, d1, -bl + 1.4, d0)
    pts = [(FUSE_SPLIT_X, y, z) for y, z in FR_KEYS]
    keys = to_m(K.key_slots(pts, "x", FUSE_SPLIT_X, KEY_FR, "z", KEY_FIT, KEY_END_GAP))
    KEY_COUNTS["key_fuselage"] = (KEY_FR, len(pts) + len(NOSE_KEYS))
    nose = ((b ^ box(-5, NOSE_SPLIT_X, -60, 60, -60, 100)) + probe) - nk
    mid = (b ^ box(NOSE_SPLIT_X, FUSE_SPLIT_X, -60, 60, -60, 100)) - nk - keys
    rear = (b ^ box(FUSE_SPLIT_X, 400, -60, 60, -60, 100)) - keys
    return nose, mid, rear


# ============================================================
# DISPLAY STAND
# ============================================================
def bezier(p, n=48):
    t = np.linspace(0, 1, n)[:, None]
    p = [np.asarray(q, float) for q in p]
    return ((1 - t) ** 3 * p[0] + 3 * (1 - t) ** 2 * t * p[1] + 3 * (1 - t) * t ** 2 * p[2] + t ** 3 * p[3])


def stand_parts():
    zb_pod, zc = pod_geom()
    r = max(r for _, r in POD_PROFILE)
    Sz = zc - r
    zb = fuse_at(STAND_X)[3]
    base_top = Sz - STAND_HEIGHT
    bcx = STAND_X + STAND_BASE_DX
    k = STAND_KEY / 2
    key = box(STAND_X - k, STAND_X + k, -k, k, Sz - 3.0, zb + STAND_KEY_DEPTH)   # vertical in the model frame
    foot = (STAND_X + STAND_FOOT_DX, base_top + STAND_BOSS[2])
    top = (STAND_X, Sz - 2.0)
    w0, w1, t = STAND_BLADE
    h = top[1] - foot[1]
    spn = bezier([foot, (foot[0], foot[1] + 0.5 * h), (top[0], top[1] - 0.45 * h), top], 40)
    d = np.gradient(spn, axis=0)
    d /= np.linalg.norm(d, axis=1)[:, None]
    nrm = np.c_[-d[:, 1], d[:, 0]]
    wv = np.linspace(w0, w1, len(spn))[:, None] / 2
    poly = np.vstack([spn + nrm * wv, (spn - nrm * wv)[::-1]])
    blade = K.cs([poly]).extrude(t).translate([0, 0, -t / 2]).rotate([90, 0, 0])
    tx, ty, td = STAND_TENON
    tenon = box(foot[0] - tx / 2, foot[0] + tx / 2, -ty / 2, ty / 2, foot[1] - td, foot[1] + 1.0)
    post = blade + tenon
    bl, bw, bt = STAND_BASE
    base = to_m(W("XY").rect(bl, bw).extrude(-bt).edges("|Z").fillet(STAND_BASE_R)
                .edges("<Z").chamfer(STAND_BASE_BEVEL).edges(">Z").fillet(1.5)).translate([bcx, 0, base_top])
    sl, sw, sh = STAND_BOSS
    boss = to_m(W("XY").slot2D(sl, sw).extrude(sh).edges(">Z").fillet(1.0)).translate([foot[0], 0, base_top - 0.01])
    base = (base + boss) - box(foot[0] - tx / 2 - FIT, foot[0] + tx / 2 + FIT, -ty / 2 - FIT, ty / 2 + FIT,
                               foot[1] - td - 0.4, foot[1] + 1)
    piv = (STAND_X, 0, Sz)
    post = rot_about(post, piv, "y", -STAND_PITCH) + key      # key added after: straight up into its socket
    return post, rot_about(base, piv, "y", -STAND_PITCH), piv


# ============================================================
# ASSEMBLY + PRINT POSES
# ============================================================
def R(rx=0, ry=0, rz=0):
    return lambda m: m.rotate([rx, ry, rz])


def build():
    """Returns {name: Manifold (assembled frame)}, {name: pose function -> print pose}."""
    parts, poses = {}, {}
    nose, mid, rear = fuselage_sections()
    parts["fuselage_nose"], poses["fuselage_nose"] = nose, R(ry=90)    # joint face down, probe up
    parts["fuselage_mid"], poses["fuselage_mid"] = mid, R(ry=90)       # aft joint face down
    parts["fuselage_rear"], poses["fuselage_rear"] = rear, R(ry=-90)   # joint face down, tail up
    parts["nozzle"], poses["nozzle"] = nozzle(), R(ry=-90)             # spigot down
    fs, fp, fslots = fin_halves()
    parts["fin_stbd"], poses["fin_stbd"] = fs - fslots, R(rx=90)       # split face down
    parts["fin_port"], poses["fin_port"] = fp - fslots, R(rx=-90)
    for side, tag in ((1, "stbd"), (-1, "port")):
        parts[f"wing_{tag}"] = wing(side) - main_socket(side)
        poses[f"wing_{tag}"] = lambda m, s=side: rot_about(m, DIHEDRAL_PT, "x", -DIHEDRAL * s)
        parts[f"tailplane_{tag}"] = tailplane(side)
        poses[f"tailplane_{tag}"] = (lambda m, s=side: rot_about(m, (0, s * TAIL_ROOT_Y, TAIL_FLOOR), "x",
                                                                 TAIL_ANHEDRAL * s))
    parts["canopy"] = canopy()
    (xa, za), _ = CANOPY_PLANE
    poses["canopy"] = lambda m: rot_about(m, (xa, 0, za), "y", canopy_angle())
    ps, pp = smoke_pod()
    parts["smoke_pod_stbd"], poses["smoke_pod_stbd"] = ps, R(rx=90)
    parts["smoke_pod_port"], poses["smoke_pod_port"] = pp, R(rx=-90)
    for i, a in enumerate(AERIALS):
        parts[f"aerial_{i + 1}"], poses[f"aerial_{i + 1}"] = aerial(a), R(rx=90)
    ng, (nx, nz, nyo) = nose_gear()
    parts["gear_nose"], poses["gear_nose"] = ng, R(rx=90)
    d, w = NOSE_WHEEL
    parts["wheel_nose"], poses["wheel_nose"] = wheel_m(nx, 0, nz, d, w), R(rx=90)
    parts["pin_nose_wheel"] = axle_pin((nx, nyo + 0.1, nz), "y", -1, 2 * nyo + 0.2)
    poses["pin_nose_wheel"] = R(rx=-90)
    for side, tag in ((1, "stbd"), (-1, "port")):
        g, (gx, gy, gz) = main_gear(side)
        parts[f"gear_main_{tag}"], poses[f"gear_main_{tag}"] = g, R(ry=90)
        d, w = MAIN_WHEEL
        parts[f"wheel_main_{tag}"], poses[f"wheel_main_{tag}"] = wheel_m(gx, gy, gz, d, w), R(rx=90)
        y0 = gy + side * (w / 2 + 0.9)
        L = w + 0.9 + 0.5 + 4.0 + 1.5
        parts[f"pin_main_wheel_{tag}"] = axle_pin((gx, y0, gz), "y", -side, L)
        poses[f"pin_main_wheel_{tag}"] = R(rx=-90 * side)
    post, base, piv = stand_parts()
    parts["stand_post"] = post
    poses["stand_post"] = lambda m: rot_about(m, piv, "y", STAND_PITCH).rotate([90, 0, 0])
    parts["stand_base"] = base
    poses["stand_base"] = lambda m: rot_about(m, piv, "y", STAND_PITCH)
    for kname, (key, n) in KEY_COUNTS.items():
        for i in range(n):
            parts[f"{kname}_{i + 1}"] = to_m(K.connector_key(key))
            poses[f"{kname}_{i + 1}"] = R()
    return parts, poses


def check_single(name, m):
    comps = m.decompose()
    if len(comps) > 1:
        vols = sorted((c.volume() for c in comps), reverse=True)
        print(f"!! {name}: {len(comps)} pieces, volumes {[round(v, 2) for v in vols[:6]]}")


if __name__ == "__main__":
    import time
    only = set(sys.argv[2:])
    (OUT_DIR / "assembled").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "print").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    parts, poses = build()
    print(f"built in {time.time() - t0:.0f}s", flush=True)
    for name, m in parts.items():
        if only and not any(o in name for o in only):
            continue
        m, dropped = K.largest_piece(m)
        if any(v > 1.0 for v in dropped):
            print(f"!! {name}: dropped loose pieces {[round(v, 1) for v in dropped if v > 1.0]} mm3")
        mesh_tm(m).export(OUT_DIR / "assembled" / f"{name}.stl")      # at 1:40 (the checks' frame)
        pm = mesh_tm(poses[name](m).scale([PRINT_K] * 3))               # at print scale
        lo, hi = pm.bounds
        pm.apply_translation(-lo)
        ext = hi - lo
        a, b = sorted(ext[:2])
        fits = "ok" if a <= 230 and b <= 250 and ext[2] <= 250 else "TOO BIG"
        pm.export(OUT_DIR / "print" / f"{name}.stl")
        print(f"{name:24s} watertight={pm.is_watertight!s:5s} {ext[0]:6.1f} x {ext[1]:6.1f} x {ext[2]:5.1f} mm"
              f"  {m.volume() * PRINT_K ** 3 / 1000:6.2f} cc  {fits}", flush=True)
