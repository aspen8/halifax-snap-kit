"""
Handley Page Halifax B Mk II Series IA, 1:60 scale (500 mm span) snap kit.

Run:  python halifax.py OUT_DIR
Writes every kit part as an STL in print orientation (OUT_DIR/print/) and in
assembled position (OUT_DIR/assembled/), plus a STEP assembly.

Axes (assembled): X = distance aft of the nose tip, Y = span (+ = starboard),
Z = up. All units mm at model scale.

Kit layout (no supports needed except where noted):
  fuselage    4 hollow half-shells (front/rear x port/starboard), pinned
  nose        clear perspex nose (Series IA)
  canopy      cockpit glazing, drops into the roof
  turrets     dorsal (Type A) and tail (Type E) + separate gun packs
  wings       inner + outer panel per side, flat underside, tongue joints
  nacelles    clamshell halves that close around the wing
  props       4 x 3-blade, spin on a 1.75 mm filament axle
  tail        one-piece tailplane through the fuselage, two fins
"""
import math
import sys
from pathlib import Path

import cadquery as cq

# ============================================================
# PARAMETERS
# ============================================================
SPAN = 500.0                 # mm, tip to tip
SCALE = 30120.0 / SPAN       # ~1:60.2

# --- Fit and printing
FIT = 0.15                   # mm, sliding clearance per side (X2D, PLA)
DOWEL_HOLE = 1.85            # mm, press fit for 1.75 mm filament dowels
DOWEL_DEPTH = 4.0            # mm, hole depth each side (cut dowels to 7.5 mm)

AXLE_HOLE_TIGHT = 1.80       # mm, 1.75 mm filament axle grips here
AXLE_HOLE_LOOSE = 2.05       # mm, ...and spins freely here
WALL = 1.6                   # mm, nose spigot inset from the skin

# --- Fuselage stations: (x, half_width, z_top, z_bottom, squareness)
# squareness: 2 = ellipse, higher = flatter sides (Halifax is slab-sided)
FUSE_STATIONS = [
    (0.0,   1.5, -15.0, -19.5, 2.0),   # perspex nose tip
    (3.0,   5.5, -10.0, -25.0, 2.2),
    (9.0,   8.8,  -5.5, -29.5, 2.5),
    (19.0, 11.4,  -1.5, -33.0, 2.8),
    (32.0, 12.8,   1.2, -35.0, 3.2),
    (46.0, 13.4,   3.6, -35.8, 3.5),
    (60.0, 13.5,   6.5, -36.0, 3.6),
    (72.0, 13.5,  10.2, -36.0, 3.8),
    (82.0, 13.5,  11.4, -36.0, 3.8),
    (190.0, 13.2, 11.4, -36.0, 3.8),
    (215.0, 12.8, 11.4, -35.0, 3.7),
    (240.0, 12.2, 11.4, -30.5, 3.5),
    (270.0, 11.6, 11.4, -25.5, 3.3),
    (305.0, 10.9, 11.2, -21.5, 3.0),
    (335.0, 10.0, 10.6, -17.5, 2.8),
    (352.0,  9.0,  9.6, -14.0, 2.5),
]
FUSE_END_X = 352.0
NOSE_SPLIT_X = 26.0          # perspex nose ends here
FUSE_SPLIT_X = 215.0         # front / rear fuselage joint
JOINT_LIP = 7.0              # mm, length of the internal joining lip
NOSE_SPIGOT = 5.0            # mm

# Alignment bosses between port/starboard halves: (x, "top"|"bottom")
FUSE_BOSSES = [
    (40, "top"), (140, "top"), (204, "top"), (235, "top"), (280, "top"), (344, "top"),
    (40, "bottom"), (100, "bottom"), (190, "bottom"),
    (235, "bottom"), (290, "bottom"), (330, "bottom"),
]

# --- Cockpit canopy hump: (x, half_width, z_top)
CANOPY = [
    (62.0, 6.0, 8.0), (68.0, 8.0, 13.0), (74.0, 9.0, 15.6), (84.0, 9.5, 16.4),
    (96.0, 9.5, 16.2), (106.0, 8.5, 14.5), (116.0, 6.0, 12.0), (122.0, 3.0, 11.3),
]
CANOPY_CUT = (60.0, 124.0, 10.0, 5.0)   # x0, x1, half-width, z floor of the drop-in

# --- Turrets
DORSAL_X = 186.0             # Boulton Paul Type A Mk VIII, low profile
DORSAL_R = 8.0               # mm, hole radius in the roof
DORSAL_DOME_R = 9.0
DORSAL_GUN_Z = 2.5           # mm, gun pack height above the turret base
TAIL_TURRET_R = 9.0          # Boulton Paul Type E
TAIL_TURRET_Z = -2.2
GUN_D = 1.2                  # mm, barrel diameter (printable minimum)
GUN_LEN = 13.0               # mm, exposed barrel length
GUN_PITCH = 2.6              # mm, spacing of the four barrels
GUN_BLOCK = (4.0, 12.0, 2.4)  # breech block x, y, z

# --- Wing planform (projected): (y, x_leading_edge, chord)
PLANFORM = [(0.0, 113.0, 76.0), (85.0, 116.0, 72.0), (245.0, 146.0, 22.0),
            (248.5, 150.0, 14.5), (250.0, 154.0, 7.0)]
WING_ROOT_Y = 13.3           # wing root face (fuselage side)
WING_JOINT_Y = 85.0          # inner/outer panel joint
DIHEDRAL = 5.0               # deg, outer panels
Z_FLOOR = -16.6              # flat underside of the inner panels
TC_INNER = 0.19             # nominal; the flattened underside takes ~3% off
TC_OUTER = [(85.0, 0.185), (245.0, 0.13), (250.0, 0.12)]
WING_FLAT_FROM = 0.15        # underside is flat from 15% chord to the TE
WING_TE = 0.8                # mm, trailing-edge thickness
# Spar tongues into the fuselage (x range), port forward / starboard aft
ROOT_TONGUE = {-1: (128.0, 142.0), 1: (146.0, 160.0)}
ROOT_TONGUE_Z = (1.4, 5.4)   # above the floor
JOINT_TONGUE = (0.26, 0.54, 1.6, 5.0, 12.0)  # chord fr. start/end, z0, z1, depth

# --- Nacelles: (y_centre, z_centre, x_front, length)
NACELLES = [
    (59.0,  -15.7, 86.0, 132.0),     # inner: runs past trailing edge (gear bay)
    (128.5, -11.0, 95.0, 100.0),     # outer
]
NACELLE_W = 22.0             # mm, max width
NACELLE_H = 21.0             # mm, max height of the body (oval)
RADIATOR_X = 6.0             # mm, chin radiator start behind nacelle front
RADIATOR_LEN = 34.0
RADIATOR_R = 6.0
NACELLE_PINS = [(12.0, -2.0), (None, -7.0)]  # (dx from front | None = mid-chord, dz)

# --- Propellers: Rotol 3-blade, 12 ft 9 in
PROP_D = 3886.0 / SCALE      # ~64.5 mm
PROP_GAP = 0.6               # mm, prop backplate to nacelle front
SPINNER_LEN = 7.5
SPINNER_R = 4.8
BLADE_T = 1.2                # mm
BLADE_ROOT_W, BLADE_MAX_W, BLADE_TIP_W = 3.6, 5.2, 3.4

# --- Tailplane and fins
TAIL_ROOT = (293.0, 41.0)    # x_le, chord at centreline
TAIL_TIP = (298.0, 36.0)     # at the fin inner face
TAIL_FLOOR = 4.0             # mm, flat underside of the tailplane
TAIL_TC = 0.11
TAIL_SLOT_H = 6.5            # mm, height of the fuselage slot above the floor
FIN_Y = 82.0                 # mm, fin mid-plane
FIN_X_LE = 297.0
FIN_CHORD = 39.0
FIN_Z_BOTTOM = -20.0
FIN_Z_TOP = 40.0
FIN_T = 3.6
FIN_CORNER_R = 9.0
FIN_POCKET = 1.5             # mm, tailplane tip sits this deep in the fin

OUT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out")

# ============================================================
# HELPERS
# ============================================================
V = cq.Vector
W = cq.Workplane


def wp(shape):
    return W().add(shape)


def box(x0, x1, y0, y1, z0, z1):
    return W().box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def interp(table, x):
    """Linear interpolation (with end extrapolation) of a list of tuples on col 0."""
    for a, b in zip(table, table[1:]):
        if x <= b[0] or b is table[-1]:
            t = (x - a[0]) / (b[0] - a[0])
            return tuple(pa + t * (pb - pa) for pa, pb in zip(a, b))
    return table[-1]


def superellipse_wire(x, hw, z_top, z_bot, n, pts=48):
    zc, hh = (z_top + z_bot) / 2, (z_top - z_bot) / 2
    p = []
    for i in range(pts):
        t = 2 * math.pi * i / pts
        c, s = math.cos(t), math.sin(t)
        p.append(V(x, hw * math.copysign(abs(c) ** (2 / n), c),
                   zc + hh * math.copysign(abs(s) ** (2 / n), s)))
    return cq.Wire.assembleEdges([cq.Edge.makeSpline(p, periodic=True)])


def revolve_profile(pts):
    """Solid of revolution about X from a list of (x, r) points."""
    return (W("XY").moveTo(pts[0][0], 0).lineTo(*pts[0])
            .spline(pts[1:], includeCurrent=True)
            .lineTo(pts[-1][0], 0).close()
            .revolve(360, (0, 0, 0), (1, 0, 0)))


def cyl(p, d, length, axis):
    """Cylinder starting at point p, along axis 'x'|'y'|'z' (negative length ok)."""
    ax = {"x": V(1, 0, 0), "y": V(0, 1, 0), "z": V(0, 0, 1)}[axis]
    if length < 0:
        ax, length = ax * -1, -length
    return wp(cq.Solid.makeCylinder(d / 2, length, V(*p), ax))


# ============================================================
# FUSELAGE
# ============================================================
def fuselage_solid(offset=0.0, x0=None, x1=None):
    """Outer fuselage loft, or an inward offset of it (for shells and lips)."""
    st = FUSE_STATIONS
    if offset:
        x0 = 19.0 if x0 is None else x0
        x1 = FUSE_END_X - 3.0 if x1 is None else x1
        st = ([interp(st, x0)] + [s for s in st if x0 < s[0] < x1] + [interp(st, x1)])
        st = [(x, hw - offset, t - offset, b + offset, n) for x, hw, t, b, n in st]
    return wp(cq.Solid.makeLoft([superellipse_wire(*s) for s in st], ruled=False))


def dowel_holes(points, axis, split):
    """Holes for 1.75 mm filament dowels, DOWEL_DEPTH into each side of a split."""
    out = None
    for p in points:
        q = list(p)
        q["xyz".index(axis)] = split - DOWEL_DEPTH
        h = cyl(q, DOWEL_HOLE, 2 * DOWEL_DEPTH, axis)
        out = h if out is None else out.union(h)
    return out


def canopy_hump():
    wires = [superellipse_wire(x, hw, zt, 3.0, 3.0) for x, hw, zt in CANOPY]
    return wp(cq.Solid.makeLoft(wires, ruled=False))


def fuselage_parts(wing_tongues):
    """Solid half-fuselages (printed split face down; slicer infill keeps them light)."""
    outer = fuselage_solid()
    body = outer

    # sockets and slots
    cx0, cx1, chw, cz = CANOPY_CUT
    _, _, top_d, _, _ = interp(FUSE_STATIONS, DORSAL_X)
    body = body.cut(box(cx0, cx1, -chw, chw, cz, 30))                       # canopy
    body = body.cut(cyl((DORSAL_X, 0, top_d - 3.0), 2 * DORSAL_R, 20, "z"))  # dorsal turret
    body = body.cut(cyl((DORSAL_X, 0, top_d - 3.0), AXLE_HOLE_TIGHT, -5, "z"))
    body = body.cut(tailplane_slot())
    for t in wing_tongues:
        bb = t.val().BoundingBox()
        body = body.cut(box(bb.xmin - FIT, bb.xmax + FIT, bb.ymin - 0.5, bb.ymax + 0.5,
                            bb.zmin - FIT, bb.zmax + FIT))
    body = body.cut(cyl((FUSE_END_X + 0.1, 0, TAIL_TURRET_Z), AXLE_HOLE_TIGHT, -5, "x"))
    # socket for the nose spigot
    body = body.cut(fuselage_solid(WALL, NOSE_SPLIT_X - 1, NOSE_SPLIT_X + NOSE_SPIGOT + 2)
                    .intersect(box(NOSE_SPLIT_X - 1, NOSE_SPLIT_X + NOSE_SPIGOT + 0.4,
                                   -50, 50, -60, 60)))

    # port/stbd alignment pins (pins on the port half, pointing +y)
    pts = []
    for x, where in FUSE_BOSSES:
        _, hw, top, bot, _ = interp(FUSE_STATIONS, x)
        pts.append((x, 0, top - 4.5 if where == "top" else bot + 4.5))
    lr_holes = dowel_holes(pts, "y", 0.0)

    # front/rear pins on the joint face (on the front sections, pointing aft)
    _, hw, top, bot, _ = interp(FUSE_STATIONS, FUSE_SPLIT_X)
    fr = [(0, y, z) for y in (-hw / 2, hw / 2) for z in (top - 6, bot + 6, (top + bot) / 2)]
    fr_holes = dowel_holes(fr, "x", FUSE_SPLIT_X)

    port = box(-10, 400, -50, 0, -60, 60)
    stbd = box(-10, 400, 0, 50, -60, 60)
    front = box(NOSE_SPLIT_X, FUSE_SPLIT_X, -50, 50, -60, 60)
    rear = box(FUSE_SPLIT_X, 400, -50, 50, -60, 60)
    parts = {}
    for sec_name, sec in (("front", front), ("rear", rear)):
        for side_name, side in (("port", port), ("stbd", stbd)):
            p = body.intersect(sec).intersect(side).cut(lr_holes).cut(fr_holes)
            parts[f"fuselage_{sec_name}_{side_name}"] = p

    # perspex nose with a spigot into the front section
    parts["nose_glazing"] = (
        outer.intersect(box(-1, NOSE_SPLIT_X, -50, 50, -60, 60))
        .union(fuselage_solid(WALL + FIT, NOSE_SPLIT_X - 1, NOSE_SPLIT_X + NOSE_SPIGOT + 1)
               .intersect(box(NOSE_SPLIT_X - 1, NOSE_SPLIT_X + NOSE_SPIGOT, -50, 50, -60, 60))))

    # cockpit canopy: roof + hump, fills the roof pocket (FIT clearance)
    parts["canopy"] = (outer.union(canopy_hump())
                       .intersect(box(cx0 + FIT, cx1 - FIT, -chw + FIT, chw - FIT, cz + FIT, 30)))
    return parts


# ============================================================
# TURRETS AND GUNS
# ============================================================
def gun_pack():
    bx, by, bz = GUN_BLOCK
    g = box(0, bx, -by / 2, by / 2, 0, bz)
    for i in range(4):
        y = (i - 1.5) * GUN_PITCH
        g = g.union(cyl((bx - 0.2, y, GUN_D / 2), GUN_D, GUN_LEN + 0.2, "x"))
    return g


def gun_slot(at, direction):
    """Slot that receives a gun pack breech block. direction: +1 aft, -1 fwd."""
    bx, by, bz = GUN_BLOCK
    x, y, z = at
    if direction > 0:
        return box(x - bx - FIT, x + 2, y - by / 2 - FIT, y + by / 2 + FIT, z - FIT, z + bz + FIT)
    return box(x - 2, x + bx + FIT, y - by / 2 - FIT, y + by / 2 + FIT, z - FIT, z + bz + FIT)


def dorsal_turret():
    _, _, top, _, _ = interp(FUSE_STATIONS, DORSAL_X)
    base_z = top - 1.2                       # sits on the roof edges
    dome = (wp(cq.Solid.makeSphere(DORSAL_DOME_R, V(DORSAL_X, 0, base_z - 2.5)))
            .intersect(box(DORSAL_X - 20, DORSAL_X + 20, -20, 20, base_z, 40)))
    plug = cyl((DORSAL_X, 0, top - 3.0 + FIT), 2 * (DORSAL_R - FIT), base_z - top + 3.0, "z")
    t = dome.union(plug)
    # guns point aft out of a slot at the back of the dome
    t = t.cut(gun_slot((DORSAL_X + DORSAL_DOME_R - 2.0, 0, base_z + DORSAL_GUN_Z), +1))
    t = t.cut(fuselage_solid().cut(cyl((DORSAL_X, 0, top - 3.0), 2 * DORSAL_R, 20, "z")))
    # filament pin hole to the locating boss
    t = t.cut(cyl((DORSAL_X, 0, base_z - 2), AXLE_HOLE_LOOSE, 5, "z"))
    return t


def tail_turret():
    t = (wp(cq.Solid.makeSphere(TAIL_TURRET_R, V(FUSE_END_X, 0, TAIL_TURRET_Z), angleDegrees1=-90))
         .intersect(box(FUSE_END_X, FUSE_END_X + 20, -20, 20, -30, 30)))
    t = t.cut(gun_slot((FUSE_END_X + TAIL_TURRET_R - 1.5, 0, TAIL_TURRET_Z - 1.2), +1))
    t = t.cut(cyl((FUSE_END_X - 0.1, 0, TAIL_TURRET_Z), AXLE_HOLE_TIGHT, 4, "x"))
    return t


# ============================================================
# WINGS
# ============================================================
def flat_bottom_section(tc, chord, n=40):
    """NACA 230xx rotated so the underside is flat from max depth to the TE.

    Returns (nose_pts, flat_start, te_lower, te_upper) in local (x, z),
    floor at z = 0, leading edge near x = 0.
    """
    m, k1 = 0.2025, 15.957
    up, lo = [], []
    for i in range(n + 1):
        x = (1 - math.cos(math.pi * i / n)) / 2
        yt = 5 * tc * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x**2
                       + 0.2843 * x**3 - 0.1036 * x**4) + x * (WING_TE / 2) / chord
        if x < m:
            yc = k1 / 6 * (x**3 - 3 * m * x**2 + m**2 * (3 - m) * x)
            dyc = k1 / 6 * (3 * x**2 - 6 * m * x + m**2 * (3 - m))
        else:
            yc, dyc = k1 * m**3 / 6 * (1 - x), -k1 * m**3 / 6
        th = math.atan(dyc)
        up.append(((x - yt * math.sin(th)) * chord, (yc + yt * math.cos(th)) * chord))
        lo.append(((x + yt * math.sin(th)) * chord, (yc - yt * math.cos(th)) * chord))
    # rotate so the line from the lower surface at WING_FLAT_FROM to the TE is
    # horizontal, then flatten the underside onto it: prints flat, no supports
    k = min(range(1, len(lo) - 1), key=lambda i: abs(lo[i][0] / chord - WING_FLAT_FROM))
    xt, zt = lo[-1]
    a = -math.atan2(zt - lo[k][1], xt - lo[k][0])
    ca, sa = math.cos(a), math.sin(a)

    def rot(p):
        x, z = p[0] - xt, p[1] - zt
        return (xt + x * ca - z * sa, x * sa + z * ca)
    up = [rot(p) for p in up]
    lo = [(x, max(z, 0.0)) for x, z in (rot(p) for p in lo[:k + 1])]
    lo[-1] = (lo[-1][0], 0.0)
    nose = list(reversed(up)) + lo[1:]
    return nose, lo[-1], (xt, 0.0), up[-1]


def section_wire(tc, chord, place):
    nose, flat0, te_lo, te_up = flat_bottom_section(tc, chord)
    pts = [place(*p) for p in nose]
    e1 = cq.Edge.makeSpline(pts)
    e2 = cq.Edge.makeLine(place(*flat0), place(*te_lo))
    e3 = cq.Edge.makeLine(place(*te_lo), place(*te_up))
    return cq.Wire.assembleEdges([e1, e2, e3])


def panel(stations, z_floor=None):
    """stations: (y_local, x_le, chord, tc), flat underside at z_floor."""
    zf = Z_FLOOR if z_floor is None else z_floor
    wires = [section_wire(tc, c, lambda px, pz, x=x, y=y: V(x + px, y, zf + pz))
             for y, x, c, tc in stations]
    solid = cq.Solid.makeLoft(wires, ruled=True)
    if solid.Volume() < 0:                       # loft came out inside-out
        solid = cq.Solid.makeLoft(list(reversed(wires)), ruled=True)
    return wp(solid)


def outer_planform(y_local):
    """Planform/thickness of the outer panel at a local (unrotated) span."""
    cd = math.cos(math.radians(DIHEDRAL))
    yp = WING_JOINT_Y + (y_local - WING_JOINT_Y) * cd
    seg = PLANFORM[1:]
    if yp < WING_JOINT_Y:            # extrapolate the outer leading edge inward
        a, b = PLANFORM[1], PLANFORM[2]
        t = (yp - a[0]) / (b[0] - a[0])
        _, x, c = (0, a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2]))
    else:
        _, x, c = interp(seg, yp)
    return x, c, interp(TC_OUTER, max(yp, WING_JOINT_Y))[1]


def wing_parts(side):
    """Inner panel, outer panel and the root tongue for one side (side=+1 stbd)."""
    cd = math.cos(math.radians(DIHEDRAL))
    # inner panel: built to y=+90 then trimmed at the joint bisector
    st_in = []
    for y in (WING_ROOT_Y, WING_JOINT_Y + 5):
        _, x, c = interp(PLANFORM, y)
        st_in.append((y, x, c, TC_INNER))
    inner = panel(st_in)

    st_out = []
    for yp in (WING_JOINT_Y - 5, 245.0, 248.5, 250.0):
        yl = WING_JOINT_Y + (yp - WING_JOINT_Y) / cd
        x, c, tc = outer_planform(yl)
        st_out.append((yl, x, c, tc))
    outer = panel(st_out)

    # joint tongue (built in the outer panel's frame, at the bisector angle)
    fs, fe, z0, z1, depth = JOINT_TONGUE
    x, c, _ = outer_planform(WING_JOINT_Y)
    tongue = box(x + fs * c, x + fe * c, WING_JOINT_Y - depth, WING_JOINT_Y + 10,
                 Z_FLOOR + z0, Z_FLOOR + z1)
    pocket = box(x + fs * c - FIT, x + fe * c + FIT, WING_JOINT_Y - depth - 0.4,
                 WING_JOINT_Y + 1, Z_FLOOR + z0 - FIT, Z_FLOOR + z1 + FIT)

    pivot = ((0, WING_JOINT_Y, Z_FLOOR), (1, WING_JOINT_Y, Z_FLOOR))
    outer = outer.union(tongue.rotate(*pivot, -DIHEDRAL / 2)).rotate(*pivot, DIHEDRAL)
    pocket = pocket.rotate(*pivot, DIHEDRAL / 2)
    half = box(-100, 400, WING_JOINT_Y, WING_JOINT_Y + 300, Z_FLOOR - 50, Z_FLOOR + 50)
    half = half.rotate(*pivot, DIHEDRAL / 2)
    inner = inner.cut(half).cut(pocket)
    outer = outer.intersect(half.union(tongue.rotate(*pivot, DIHEDRAL / 2)))

    # root tongue into the fuselage
    tx0, tx1 = ROOT_TONGUE[side]
    reach = WING_ROOT_Y - WALL - 0.4           # stops short of the far wall
    root_tongue = box(tx0, tx1, -reach, WING_ROOT_Y + 10,
                      Z_FLOOR + ROOT_TONGUE_Z[0], Z_FLOOR + ROOT_TONGUE_Z[1])
    inner = inner.cut(fuselage_solid()).union(root_tongue)

    if side < 0:
        inner, outer = inner.mirror("XZ"), outer.mirror("XZ")
        root_tongue = root_tongue.mirror("XZ")
    return inner, outer, root_tongue


# ============================================================
# NACELLES AND PROPS
# ============================================================
def nacelle_body(zc, x0, length):
    prof = [(0.0, 0.30), (0.02, 0.62), (0.06, 0.86), (0.13, 0.98), (0.25, 1.0),
            (0.45, 0.95), (0.70, 0.70), (0.90, 0.35), (1.0, 0.08)]
    r = NACELLE_W / 2
    body = revolve_profile([(x0 + f * length, k * r) for f, k in prof])
    m = cq.Matrix([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, NACELLE_H / NACELLE_W, 0]])
    body = wp(body.val().transformGeometry(m))
    rad_pts = [(0.0, 0.25), (0.15, 0.85), (0.5, 1.0), (0.85, 0.85), (1.0, 0.2)]
    rad = (revolve_profile([(x0 + RADIATOR_X + f * RADIATOR_LEN, k * RADIATOR_R)
                            for f, k in rad_pts])
           .translate((0, 0, -NACELLE_H / 2 + RADIATOR_R * 0.55)))
    return body.union(rad).translate((0, 0, zc))


def nacelle_parts(index, side, wing_panel):
    yc, zc, x0, length = NACELLES[index]
    body = nacelle_body(zc, x0, length).translate((0, yc * side, 0))
    # notch for the wing, with clearance top and bottom
    body = (body.cut(wing_panel)
            .cut(wing_panel.translate((0, 0, FIT)))
            .cut(wing_panel.translate((0, 0, -FIT))))
    # filament axle hole for the prop
    body = body.cut(cyl((x0 - 1, yc * side, zc), AXLE_HOLE_TIGHT, 8, "x"))
    # pins from the inboard half into the outboard half
    _, le, c = interp(PLANFORM, yc)
    pts = [((x0 + dx) if dx is not None else (le + 0.5 * c), 0, zc + dz)
           for dx, dz in NACELLE_PINS]
    y = yc * side
    holes = dowel_holes(pts, "y", y)
    inboard = box(-10, 400, y - 50, y, -80, 80) if side > 0 else box(-10, 400, y, y + 50, -80, 80)
    outboard = box(-10, 400, y, y + 50, -80, 80) if side > 0 else box(-10, 400, y - 50, y, -80, 80)
    return body.intersect(inboard).cut(holes), body.intersect(outboard).cut(holes)


def propeller():
    """Prop on its own axis: X = thrust axis, backplate at x = 0 facing +x."""
    sp = revolve_profile([(-SPINNER_LEN, 0.6), (-SPINNER_LEN * 0.7, SPINNER_R * 0.62),
                          (-SPINNER_LEN * 0.35, SPINNER_R * 0.9), (0.0, SPINNER_R)])
    back = cyl((0, 0, 0), 2 * SPINNER_R, -1.0, "x").translate((1.0, 0, 0))
    hub = sp.union(back)
    R = PROP_D / 2
    # blade outline in its own plane (r along +Z, chord along Y)
    outline = [(-BLADE_ROOT_W / 2, 3.0), (-BLADE_MAX_W / 2, R * 0.45),
               (-BLADE_TIP_W / 2, R * 0.92), (0, R), (BLADE_TIP_W / 2, R * 0.92),
               (BLADE_MAX_W / 2, R * 0.45), (BLADE_ROOT_W / 2, 3.0)]
    blade = (W("YZ").workplane(offset=-BLADE_T + 1.0)
             .moveTo(*outline[0]).spline(outline[1:], includeCurrent=True).close()
             .extrude(BLADE_T))
    prop = hub
    for i in range(3):
        prop = prop.union(blade.rotate((0, 0, 0), (1, 0, 0), 120 * i))
    prop = prop.cut(cyl((1.1, 0, 0), AXLE_HOLE_LOOSE, -6.5, "x"))
    return prop


# ============================================================
# TAIL
# ============================================================
def tailplane():
    y_tip = FIN_Y - FIN_T / 2 + FIN_POCKET
    st = [(-y_tip, TAIL_TIP[0], TAIL_TIP[1], TAIL_TC), (0.0, TAIL_ROOT[0], TAIL_ROOT[1], TAIL_TC),
          (y_tip, TAIL_TIP[0], TAIL_TIP[1], TAIL_TC)]
    return panel(st[:2], TAIL_FLOOR).union(panel(st[1:], TAIL_FLOOR))


def tailplane_slot():
    return box(TAIL_ROOT[0] - FIT - 0.5, TAIL_ROOT[0] + TAIL_ROOT[1] + FIT + 0.5,
               -20, 20, TAIL_FLOOR - FIT, TAIL_FLOOR + TAIL_SLOT_H + FIT)


def fin(side):
    h = FIN_Z_TOP - FIN_Z_BOTTOM
    f = (W("XZ").center(FIN_X_LE + FIN_CHORD / 2, FIN_Z_BOTTOM + h / 2)
         .rect(FIN_CHORD, h).extrude(FIN_T / 2, both=True)
         .edges("|Y").fillet(FIN_CORNER_R)
         .faces("+Y or -Y").edges().fillet(1.2))
    f = f.translate((0, FIN_Y * side, 0))
    tp = tailplane()
    for dx, dz in ((0, 0), (FIT, 0), (-FIT, 0), (0, FIT), (0, -FIT)):
        f = f.cut(tp.translate((dx, 0, dz)))
    # tailplane tip sits in a shallow recess
    return f


# ============================================================
# ASSEMBLY + PRINT POSES
# ============================================================
def rot(w, axis, deg):
    a = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[axis]
    return w.rotate((0, 0, 0), a, deg)


def to_bed(w):
    bb = w.val().BoundingBox()
    return w.translate((-bb.xmin, -bb.ymin, -bb.zmin))


def build():
    parts, poses = {}, {}
    tongues = []
    wings = {}
    for side, tag in ((1, "stbd"), (-1, "port")):
        inner, outer, tongue = wing_parts(side)
        wings[side] = (inner, outer)
        tongues.append(tongue)
        parts[f"wing_inner_{tag}"] = inner
        parts[f"wing_outer_{tag}"] = outer
        poses[f"wing_inner_{tag}"] = lambda w: w
        pivot_y = WING_JOINT_Y * side
        poses[f"wing_outer_{tag}"] = (lambda w, s=side, py=pivot_y:
                                      w.rotate((0, py, Z_FLOOR), (1, py, Z_FLOOR), -DIHEDRAL * s))
        for i in range(len(NACELLES)):
            pnl = inner if i == 0 else outer
            inb, outb = nacelle_parts(i, side, pnl)
            parts[f"nacelle{i + 1}_{tag}_inboard"] = inb
            parts[f"nacelle{i + 1}_{tag}_outboard"] = outb
            poses[f"nacelle{i + 1}_{tag}_inboard"] = lambda w, s=side: rot(w, "x", -90 * s)
            poses[f"nacelle{i + 1}_{tag}_outboard"] = lambda w, s=side: rot(w, "x", 90 * s)
            yc, zc, x0, _ = NACELLES[i]
            parts[f"prop{i + 1}_{tag}"] = (propeller()
                                          .translate((x0 - PROP_GAP - 1.0, yc * side, zc)))
            poses[f"prop{i + 1}_{tag}"] = lambda w: rot(w, "y", 90)
        parts[f"fin_{tag}"] = fin(side)
        poses[f"fin_{tag}"] = lambda w: rot(w, "x", 90)

    fp = fuselage_parts(tongues)
    for k, v in fp.items():
        parts[k] = v
        if k.endswith("_port"):
            poses[k] = lambda w: rot(w, "x", -90)
        elif k.endswith("_stbd"):
            poses[k] = lambda w: rot(w, "x", 90)
        elif k == "nose_glazing":
            poses[k] = lambda w: rot(w, "y", 90)      # spigot down
        else:
            poses[k] = lambda w: w

    parts["tailplane"] = tailplane()
    poses["tailplane"] = lambda w: w
    parts["turret_dorsal"] = dorsal_turret()
    poses["turret_dorsal"] = lambda w: w
    parts["turret_tail"] = tail_turret()
    poses["turret_tail"] = lambda w: rot(w, "y", -90)
    _, _, top, _, _ = interp(FUSE_STATIONS, DORSAL_X)
    parts["guns_dorsal"] = gun_pack().translate(
        (DORSAL_X + DORSAL_DOME_R - 2.0 - GUN_BLOCK[0], 0, top - 1.2 + DORSAL_GUN_Z))
    parts["guns_tail"] = gun_pack().translate(
        (FUSE_END_X + TAIL_TURRET_R - 1.5 - GUN_BLOCK[0], 0, TAIL_TURRET_Z - 1.2))
    poses["guns_dorsal"] = poses["guns_tail"] = lambda w: w
    return parts, poses


def mesh(w, tol=0.02, ang=0.15):
    """Tessellate a part to a trimesh (exact bounds, unlike the B-rep box)."""
    import trimesh
    verts, tris = [], []
    for solid in w.vals():
        v, t = solid.tessellate(tol, ang)
        off = len(verts)
        verts += [(p.x, p.y, p.z) for p in v]
        tris += [(a + off, b + off, c + off) for a, b, c in t]
    m = trimesh.Trimesh(verts, tris, process=True)
    m.merge_vertices()
    return m


if __name__ == "__main__":
    only = set(sys.argv[2:])
    (OUT_DIR / "assembled").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "print").mkdir(parents=True, exist_ok=True)
    parts, poses = build()
    bed = 256.0
    for name, w in parts.items():
        if only and not any(o in name for o in only):
            continue
        s = w.val()
        if len(w.vals()) > 1:
            print(f"!! {name}: {len(w.vals())} separate solids")
        mesh(w).export(OUT_DIR / "assembled" / f"{name}.stl")
        pm = mesh(poses[name](w))
        lo, hi = pm.bounds
        pm.apply_translation(-lo)
        ext = hi - lo
        fits = "ok" if max(ext[0], ext[1]) <= bed and ext[2] <= 256 else "TOO BIG"
        pm.export(OUT_DIR / "print" / f"{name}.stl")
        print(f"{name:28s} valid={s.isValid()!s:5s} watertight={pm.is_watertight!s:5s} "
              f"{ext[0]:6.1f} x {ext[1]:6.1f} x {ext[2]:5.1f} mm  {fits}", flush=True)
