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
import numpy as np

# ============================================================
# PARAMETERS
# ============================================================
SPAN = 500.0                 # mm, tip to tip
SCALE = 30120.0 / SPAN       # ~1:60.2

# --- Fit and printing
FIT = 0.15                   # mm, sliding clearance per side (X2D, PLA)
# Printed connector keys (flat, printed lying down). (length across the split,
# width, thickness) in mm; slots get KEY_FIT per side and END_GAP at each end.
KEY_FIT = 0.1                # mm, press fit per side
KEY_END_GAP = 0.3            # mm, slot is this much deeper than half a key
KEY_LR = (8.0, 10.0, 2.4)    # fuselage port/starboard halves (width along x)
KEY_FR = (12.0, 6.0, 2.4)    # front/rear fuselage joint (width along z)
KEY_NAC = (7.0, 6.0, 2.0)    # nacelle halves (width along x)

AXLE_HOLE_TIGHT = 1.80       # mm, printed 1.8 mm pins grip here (wheel forks, turret bases)
AXLE_HOLE_LOOSE = 2.05       # mm, ...and turn freely here (wheels, dorsal turret)
WALL = 1.6                   # mm, nose spigot inset from the skin

# --- Fuselage stations: (x, half_width, z_top, z_bottom, squareness)
# squareness: 2 = ellipse, higher = flatter sides (Halifax is slab-sided)
FUSE_STATIONS = [            # side profile: 51 Sqn profile (0.5905 mm/px); widths: Revell plan
    (0.0,   2.5, -15.5, -21.0, 2.0),   # perspex chin dome
    (2.0,   5.5, -14.8, -25.5, 2.2),
    (5.0,   7.2, -13.5, -28.0, 2.4),
    (8.5,   8.2,  -6.0, -30.0, 2.6),   # painted nose cap starts above the dome
    (12.5,  9.2,  -4.0, -31.7, 2.7),
    (19.5, 10.6,  -2.2, -34.0, 2.9),
    (30.0, 12.2,   0.2, -35.4, 3.2),
    (44.0, 13.2,   2.5, -36.3, 3.5),
    (49.0, 13.4,   3.1, -36.5, 3.6),   # windscreen base
    (54.0, 13.5,   7.3, -36.6, 3.7),
    (59.0, 13.5,   9.6, -36.7, 3.8),
    (72.5, 13.5,  11.4, -36.8, 3.8),   # roof line
    (160.0, 13.3, 11.4, -36.8, 3.8),
    (179.0, 13.1, 11.4, -35.2, 3.8),
    (202.0, 12.9, 11.4, -32.9, 3.7),
    (226.0, 12.4, 11.4, -29.9, 3.6),
    (250.0, 12.0, 11.4, -27.0, 3.4),
    (273.0, 11.5, 11.4, -24.0, 3.3),
    (297.0, 11.0, 11.3, -20.5, 3.1),
    (321.0, 10.4, 11.0, -17.5, 2.9),
    (344.0,  9.5, 10.2, -14.0, 2.6),
    (352.0,  9.0,  9.6, -13.0, 2.5),
]
FUSE_END_X = 352.0
NOSE_SPLIT_X = 13.0          # perspex chin dome ends here
NOSE_GLASS_TOP = -13.0       # mm, dome top; the painted nose cap is above it
NOSE_SPIGOT_BOX = (5.0, 6.0, -28.0, -16.0)   # length, half-width, z0, z1 of the dome's plug
FUSE_SPLIT_X = 215.0         # front / rear fuselage joint
JOINT_LIP = 7.0              # mm, length of the internal joining lip
NOSE_SPIGOT = 5.0            # mm

# Alignment bosses between port/starboard halves: (x, "top"|"bottom")
FUSE_BOSSES = [              # connector key positions between port/starboard halves
    (40, "top"), (140, "top"), (204, "top"), (235, "top"), (280, "top"),
    (40, "bottom"), (100, "bottom"), (190, "bottom"),
    (235, "bottom"), (290, "bottom"), (318, "bottom"),
]

# --- Cockpit canopy hump: (x, half_width, z_top)
CANOPY_CUT = (48.0, 75.0, 2.0)          # x0, x1, z floor (full width drop-in)
CANOPY_TAB = (55.0, 68.0, 3.0, -2.0)     # x0, x1, half-width, z bottom of the locating tab
H2S_RADOME = True            # ventral H2S blister (Revell Srs IA drawing)
RADOME = [(203.0, 6.0, 1.5), (208.0, 9.0, 4.0), (215.0, 10.0, 5.0), (225.0, 9.5, 5.0),
          (235.0, 7.0, 3.8), (243.0, 3.5, 2.0), (247.0, 1.0, 0.5)]   # x, half-width, depth
GEAR_BATH = [(110.0, -27.0, 7.5), (118.0, -34.5, 9.5), (128.0, -37.5, 10.2),
             (150.0, -37.5, 10.2), (162.0, -34.5, 9.0), (171.0, -28.0, 6.0)]  # x, bottom z, half-width

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
# Measured from the Revell 1/72 Halifax B/GR II Srs IA plan views, scaled to span:
# LE straight across the centre section, then swept; TE straight to the panel joint.
PLANFORM = [(0.0, 109.3, 82.7), (70.0, 109.8, 82.2), (80.0, 111.4, 80.6),
            (244.0, 137.9, 34.9), (248.0, 140.5, 30.0), (250.0, 145.0, 22.0)]
OUTER_SEG = 2                # PLANFORM index where the outer panel starts
WING_ROOT_Y = 13.3           # wing root face (fuselage side)
WING_JOINT_Y = 80.0          # inner/outer panel joint (TE kink)
DIHEDRAL = 5.0               # deg, outer panels
Z_FLOOR = -16.6              # flat underside of the inner panels
TC_INNER = 0.19             # nominal; the flattened underside takes ~3% off
TC_OUTER = [(80.0, 0.185), (244.0, 0.13), (250.0, 0.12)]
WING_FLAT_FROM = 0.15        # underside is flat from 15% chord to the TE
WING_TE = 0.8                # mm, trailing-edge thickness
WING_INCIDENCE = 2.0         # deg, root chord to fuselage datum (rigging: 2 deg)
WING_PITCH_X = 140.0         # mm, wing is pitched about this x (main spar)
# Spar tongues into the fuselage (x range), port forward / starboard aft
ROOT_TONGUE = {-1: (128.0, 142.0), 1: (146.0, 160.0)}
ROOT_TONGUE_Z = (1.4, 5.4)   # above the floor
JOINT_TONGUE = (0.26, 0.54, 1.6, 5.0, 12.0)  # chord fr. start/end, z0, z1, depth

# --- Nacelles: (y_centre, z_centre, x_front, length)
NACELLES = [
    (61.0,  -15.7, 77.1, 93.0),      # inner (spinner tip 41 mm ahead of the LE)
    (126.0, -11.0, 88.2, 62.0),      # outer
]
NACELLE_W = 22.0             # mm, max width
NACELLE_H = 21.0             # mm, max height of the body (oval)
RADIATOR_X = 6.0             # mm, chin radiator start behind nacelle front
RADIATOR_LEN = 30.0
RADIATOR_R = 6.0
NACELLE_PROFILE = [(0.0, 0.30), (0.02, 0.62), (0.06, 0.86), (0.13, 0.98), (0.25, 1.0),
                   (0.45, 0.95), (0.70, 0.70), (0.90, 0.35), (1.0, 0.08)]
NACELLE_PINS = [(0.13, -2.0), (0.6, -7.0)]   # (fraction of nacelle length, dz)

# --- Propellers: Rotol 3-blade, 12 ft 9 in
PROP_D = 3886.0 / SCALE      # ~64.5 mm
PROP_GAP = 1.2               # mm, prop backplate to nacelle front (thrust collar sits here)
# Printed prop shaft (after PB94): flange captured inside the nacelle halves,
# thrust collar outside, hex boss that the prop presses onto. Spins freely.
SHAFT_D, BORE_D = 2.4, 2.7         # mm
FLANGE_D, FLANGE_T, CAVITY_D = 4.0, 1.2, 4.6
COLLAR_D, COLLAR_T = 5.0, 0.8
HEX_AF, HEX_LEN, HEX_SOCKET_AF = 3.0, 2.5, 3.1
PIN_D = 1.8                  # mm, printed axle pins (wheels, turrets)

# --- Exhausts (after PB94: a separate bar of stacks plugged into a side slot)
EXH_X0 = 6.0                 # mm behind the nacelle front
EXH_LEN = 18.0               # mm, Merlin bank of six
EXH_H = 2.6                  # mm, bar height
EXH_Z = 0.8                  # mm above the nacelle centreline
EXH_DEPTH = 2.0              # mm into the nacelle
EXH_PROUD = 0.5              # mm proud of the widest nacelle point
EXH_STUBS = 6
# --- Radiator intake (recess + vanes at the front of each chin radiator)
RAD_INTAKE = (4.0, 3.2, 2.6, 2.2)        # depth, half-width, below/above centre
RAD_VANES = (0.9, 2.3)                   # |y| of the vanes, either side of centre
RAD_VANE_T = 0.5
# --- Astrodome (clear, plugs into the roof) and D/F loop fairing (moulded on)
ASTRODOME = (86.0, 3.2)                  # x, radius (Revell side view)
DF_LOOP = (122.0, 12.0, 3.6, 3.2)        # x, length, width, height of the fairing
PIN_HEAD = (4.0, 0.8)        # head diameter, thickness
SPINNER_LEN = 7.5
SPINNER_R = 4.8
BLADE_T = 1.2                # mm
BLADE_ROOT_W, BLADE_MAX_W, BLADE_TIP_W = 3.6, 5.2, 3.4

# --- Tailplane and fins
TAIL_ROOT = (301.6, 40.0)    # x_le, chord at centreline (Revell plan)
TAIL_TIP = (307.9, 34.0)     # at the fin inner face
TAIL_FLOOR = 4.0             # mm, flat underside of the tailplane
TAIL_TC = 0.11
TAIL_SLOT_H = 6.5            # mm, height of the fuselage slot above the floor
FIN_Y = 76.0                 # mm, fin mid-plane
FIN_X_LE = 305.0
FIN_CHORD = 36.0
FIN_Z_BOTTOM = -23.0
FIN_Z_TOP = 42.5             # ~31 mm above the roof line (side profile)
FIN_T = 3.6
FIN_CORNER_R = 9.0
FIN_POCKET = 1.5             # mm, tailplane tip sits this deep in the fin

# --- Landing gear (Messier main legs either side of the wheel; castoring tailwheel)
MAIN_AXLE_X = 120.0          # mm, just aft of the radiator (Revell side view)
MAIN_AXLE_Z = -51.0          # mm
MAIN_WHEEL_D = 26.0          # mm (~1.57 m)
MAIN_WHEEL_W = 9.0
MAIN_LEG = (4.0, 3.0)        # leg section: x (fore-aft), y
MAIN_PLUG = (8.0, 6.0)       # plug y-width, depth into the nacelle socket
TAIL_AXLE_X = 334.0
TAIL_LEG_DROP = 9.0          # mm, axle below the fuselage bottom
TAIL_WHEEL_D = 9.0
TAIL_WHEEL_W = 4.5
TAIL_LEG = (3.0, 2.0)
TAIL_PLUG = (5.0, 5.0)

# --- Display stand (in-flight pose, gear removed)
STAND_X = 165.0              # mm, socket under the fuselage, at the printed model's CG
STAND_KEY = 6.0              # mm, square key into the fuselage socket
STAND_KEY_DEPTH = 9.0
STAND_PITCH = 5.0            # deg, nose-up display attitude
STAND_HEIGHT = 95.0          # mm, fuselage bottom to base top
STAND_POST = (8.0, 6.0)      # mm, post section x, y
STAND_BASE = (170.0, 110.0, 5.0)
STAND_LABEL = "HALIFAX B.II Srs.IA"

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


def key_slots(points, axis, split, key, width_axis):
    """Rectangular slots for a printed key across the split plane at each point.
    The key's length runs along `axis`, its width along `width_axis`."""
    length, width, thick = key
    ext = {axis: length / 2 + KEY_END_GAP, width_axis: width / 2 + KEY_FIT}
    third = ({"x", "y", "z"} - {axis, width_axis}).pop()
    ext[third] = thick / 2 + KEY_FIT
    out = None
    for p in points:
        q = list(p)
        q["xyz".index(axis)] = split
        lo = [q[i] - ext[a] for i, a in enumerate("xyz")]
        hi = [q[i] + ext[a] for i, a in enumerate("xyz")]
        b = box(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])
        out = b if out is None else out.union(b)
    return out


def connector_key(key):
    """A printed key, lying flat (length x width on the bed), ends chamfered."""
    length, width, thick = key
    k = W().box(length, width, thick, centered=(True, True, False))
    return k.edges("|Y").chamfer(0.4)


KEY_COUNTS = {}              # filled by the part builders: name -> (key, count)


def radome():
    secs = []
    for x, hw, d in RADOME:
        _, _, _, bot, _ = interp(FUSE_STATIONS, x)
        secs.append(superellipse_wire(x, hw, bot + 3.0, bot - d, 2.4))
    return wp(cq.Solid.makeLoft(secs, ruled=False))


def fuselage_parts(wing_tongues):
    """Solid half-fuselages (printed split face down; slicer infill keeps them light)."""
    outer = fuselage_solid()
    body = outer

    # sockets and slots
    cx0, cx1, cz = CANOPY_CUT
    tx0, tx1, thw, tz = CANOPY_TAB
    if H2S_RADOME:
        outer = outer.union(radome())
        body = outer
    _, _, top_d, _, _ = interp(FUSE_STATIONS, DORSAL_X)
    body = body.cut(box(cx0, cx1, -30, 30, cz, 30))                          # canopy
    body = body.cut(box(tx0 - FIT, tx1 + FIT, -thw - FIT, thw + FIT, tz - 0.3, cz + 0.1))
    body = body.cut(cyl((DORSAL_X, 0, top_d - 3.0), 2 * DORSAL_R, 20, "z"))  # dorsal turret
    body = body.cut(cyl((DORSAL_X, 0, top_d - 3.0), AXLE_HOLE_TIGHT, -5, "z"))
    body = body.cut(tailplane_slot())
    body = body.union(df_loop_fairing()).cut(astrodome_socket())
    for pocket in wing_tongues:
        body = body.cut(pocket)
    _, _, _, bot_t, _ = interp(FUSE_STATIONS, TAIL_AXLE_X)
    body = body.cut(gear_socket(TAIL_AXLE_X, 0, bot_t, TAIL_LEG, TAIL_PLUG))
    _, _, _, bot_s, _ = interp(FUSE_STATIONS, STAND_X)
    k = STAND_KEY / 2 + FIT
    body = body.cut(box(STAND_X - k, STAND_X + k, -k, k, bot_s - 1, bot_s + STAND_KEY_DEPTH + 0.3))
    body = body.cut(cyl((FUSE_END_X + 0.1, 0, TAIL_TURRET_Z), AXLE_HOLE_TIGHT, -5, "x"))
    # socket for the nose spigot
    sl, shw, sz0, sz1 = NOSE_SPIGOT_BOX
    body = body.cut(box(NOSE_SPLIT_X - 0.1, NOSE_SPLIT_X + sl + 0.4, -shw - FIT, shw + FIT,
                        sz0 - FIT, sz1 + FIT))
    glass_zone = box(-5, NOSE_SPLIT_X, -50, 50, -60, NOSE_GLASS_TOP)
    body = body.cut(glass_zone)

    # port/stbd alignment pins (pins on the port half, pointing +y)
    pts = []
    for x, where in FUSE_BOSSES:
        _, hw, top, bot, _ = interp(FUSE_STATIONS, x)
        pts.append((x, 0, top - 4.5 if where == "top" else bot + 4.5))
    lr_holes = key_slots(pts, "y", 0.0, KEY_LR, "x")
    KEY_COUNTS["key_fuselage_halves"] = (KEY_LR, len(pts))

    # front/rear pins on the joint face (on the front sections, pointing aft)
    _, hw, top, bot, _ = interp(FUSE_STATIONS, FUSE_SPLIT_X)
    fr = [(0, y, z) for y in (-hw / 2, hw / 2) for z in (top - 6, bot + 6, (top + bot) / 2)]
    fr_holes = key_slots(fr, "x", FUSE_SPLIT_X, KEY_FR, "z")
    KEY_COUNTS["key_fuselage_joint"] = (KEY_FR, len(fr))

    port = box(-10, 400, -50, 0, -60, 60)
    stbd = box(-10, 400, 0, 50, -60, 60)
    front = box(-5, FUSE_SPLIT_X, -50, 50, -60, 60)
    rear = box(FUSE_SPLIT_X, 400, -50, 50, -60, 60)
    parts = {}
    for sec_name, sec in (("front", front), ("rear", rear)):
        for side_name, side in (("port", port), ("stbd", stbd)):
            p = body.intersect(sec).intersect(side).cut(lr_holes).cut(fr_holes)
            parts[f"fuselage_{sec_name}_{side_name}"] = p

    # perspex chin dome with a plug into the front section
    parts["nose_glazing"] = (outer.intersect(glass_zone)
                             .union(box(NOSE_SPLIT_X - 0.5, NOSE_SPLIT_X + sl, -shw, shw, sz0, sz1)))

    # cockpit glazing: full-width drop-in above the sill, plus a locating tab
    parts["canopy"] = (outer.intersect(box(cx0 + FIT, cx1 - FIT, -30, 30, cz + FIT, 30))
                       .union(box(tx0, tx1, -thw, thw, tz, cz + 0.5)))
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
    seg = PLANFORM[OUTER_SEG:]
    if yp < WING_JOINT_Y:            # extrapolate the outer leading edge inward
        a, b = PLANFORM[OUTER_SEG], PLANFORM[OUTER_SEG + 1]
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
    for y in (WING_ROOT_Y - 4, PLANFORM[1][0], WING_JOINT_Y + 5):  # root trimmed to fuselage
        _, x, c = interp(PLANFORM, y)
        st_in.append((y, x, c, TC_INNER))
    inner = panel(st_in)

    st_out = []
    for yp in [WING_JOINT_Y - 5] + [p[0] for p in PLANFORM[OUTER_SEG + 1:]]:
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
    z0, z1 = Z_FLOOR + ROOT_TONGUE_Z[0], Z_FLOOR + ROOT_TONGUE_Z[1]
    root_tongue = box(tx0, tx1, -reach, WING_ROOT_Y + 10, z0, z1)
    root_pocket = box(tx0 - FIT, tx1 + FIT, -reach - 0.5, WING_ROOT_Y + 10, z0 - FIT, z1 + FIT)

    # pitch the whole wing to the rigged incidence
    ax, d = pitch_axis(), -wing_pitch()
    inner, outer = inner.rotate(*ax, d), outer.rotate(*ax, d)
    root_tongue, root_pocket = root_tongue.rotate(*ax, d), root_pocket.rotate(*ax, d)
    inner = inner.cut(fuselage_solid()).union(root_tongue)

    if side < 0:
        inner, outer = inner.mirror("XZ"), outer.mirror("XZ")
        root_pocket = root_pocket.mirror("XZ")
    return inner, outer, root_pocket


def pitch_axis():
    return (WING_PITCH_X, 0, Z_FLOOR), (WING_PITCH_X, 1, Z_FLOOR)


def wing_pitch():
    """Nose-down rotation (deg) that brings the root chord to WING_INCIDENCE.

    Flattening the underside tilts the chord nose-up relative to the flat."""
    _, _, c = interp(PLANFORM, WING_ROOT_Y)
    nose, _, te_lo, te_up = flat_bottom_section(TC_INNER, c)
    le = min(nose, key=lambda p: p[0])
    te = ((te_lo[0] + te_up[0]) / 2, (te_lo[1] + te_up[1]) / 2)
    return math.degrees(math.atan2(le[1] - te[1], te[0] - le[0])) - WING_INCIDENCE


# ============================================================
# NACELLES AND PROPS
# ============================================================
def gear_bath(y, zc):
    secs = [superellipse_wire(x, hw, zc, bot, 2.4) for x, bot, hw in GEAR_BATH]
    return wp(cq.Solid.makeLoft(secs, ruled=False)).translate((0, y, 0))


def nacelle_body(zc, x0, length):
    r = NACELLE_W / 2
    body = revolve_profile([(x0 + f * length, k * r) for f, k in NACELLE_PROFILE])
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
    if index == 0:   # undercarriage housing under the inner nacelles
        body = body.union(gear_bath(yc * side, zc))
    # notch for the wing, with clearance top and bottom
    body = (body.cut(wing_panel)
            .cut(wing_panel.translate((0, 0, FIT)))
            .cut(wing_panel.translate((0, 0, -FIT))))
    if index == 0:   # main undercarriage socket
        body = body.cut(gear_socket(MAIN_AXLE_X, yc * side, nacelle_bottom(0, MAIN_AXLE_X),
                                    MAIN_LEG, MAIN_PLUG))
    # exhaust slots on both sides, and the radiator intake
    for face in (1, -1):
        body = body.cut(exhaust_bank(index, side, face, slot=True))
    d, hw, zlo, zhi = RAD_INTAKE
    zr = zc - NACELLE_H / 2 + RADIATOR_R * 0.55
    xr = x0 + RADIATOR_X
    Y = yc * side
    body = body.cut(box(xr - 1.5, xr + d, Y - hw, Y + hw, zr - zlo, zr + zhi))
    for vy in RAD_VANES:
        for sg in (1, -1):
            body = body.union(box(xr + 1.2, xr + d + 0.1, Y + sg * vy - RAD_VANE_T / 2,
                                  Y + sg * vy + RAD_VANE_T / 2, zr - zlo, zr + zhi)
                              .intersect(nacelle_body(zc, x0, length).translate((0, Y, 0))))
    # prop shaft bearing: bore through the nose, cavity for the captive flange
    body = body.cut(cyl((x0 - 1, yc * side, zc), BORE_D, 6.2, "x"))
    body = body.cut(cyl((x0 + 5.2, yc * side, zc), CAVITY_D, 1.6, "x"))
    # pins from the inboard half into the outboard half
    pts = [(x0 + f * length, 0, zc + dz) for f, dz in NACELLE_PINS]
    y = yc * side
    holes = key_slots(pts, "y", y, KEY_NAC, "x")
    n0 = KEY_COUNTS.get("key_nacelle", (KEY_NAC, 0))[1]
    KEY_COUNTS["key_nacelle"] = (KEY_NAC, n0 + len(pts))
    inboard = box(-10, 400, y - 50, y, -80, 80) if side > 0 else box(-10, 400, y, y + 50, -80, 80)
    outboard = box(-10, 400, y, y + 50, -80, 80) if side > 0 else box(-10, 400, y - 50, y, -80, 80)
    return body.intersect(inboard).cut(holes), body.intersect(outboard).cut(holes)


def nacelle_halfwidth(index, x):
    _, _, x0, length = NACELLES[index]
    _, k = interp(NACELLE_PROFILE, (x - x0) / length)
    return k * NACELLE_W / 2


def exhaust_bank(index, side, face, slot=False):
    """Bar of six stacks on one side of a nacelle (face=+1 is the +y side).
    slot=True returns the socket to cut instead (with FIT)."""
    yc, zc, x0, _ = NACELLES[index]
    Y = yc * side
    xs, xe = x0 + EXH_X0, x0 + EXH_X0 + EXH_LEN
    ws = [nacelle_halfwidth(index, x) for x in np.linspace(xs, xe, 12)]
    y_in, y_out = min(ws) - EXH_DEPTH, max(ws) + EXH_PROUD
    zm = zc + EXH_Z
    f = FIT if slot else 0.0
    y0, y1 = (y_in - (0.3 if slot else 0)), (y_out + 2 if slot else y_out)
    h = EXH_H + 2 * f
    a0, a1 = Y + face * y0, Y + face * y1
    lo, hi = min(a0, a1), max(a0, a1)
    bar = box(xs + h / 2 - f, xe - h / 2 + f, lo, hi, zm - h / 2, zm + h / 2)
    for xx in (xs + h / 2 - f, xe - h / 2 + f):
        bar = bar.union(cyl((xx, lo, zm), h, hi - lo, "y"))
    if slot:
        return bar
    pitch = EXH_LEN / EXH_STUBS
    for k in range(EXH_STUBS):
        xk = xs + (k + 0.5) * pitch
        yb = Y + face * (y_out - 0.05)
        yt = Y + face * (y_out + 1.4)
        def rect(x, y, w, hh):
            pts = [V(x - w / 2, y, zm - hh / 2), V(x + w / 2, y, zm - hh / 2),
                   V(x + w / 2, y, zm + hh / 2), V(x - w / 2, y, zm + hh / 2)]
            return cq.Wire.makePolygon(pts, close=True)
        stub = wp(cq.Solid.makeLoft([rect(xk, yb, 1.8, 2.0), rect(xk + 0.7, yt, 2.3, 2.5)], ruled=True))
        outlet = box(xk + 0.7 - 0.5, xk + 0.7 + 0.5, min(yt, yt - face * 0.6), max(yt, yt - face * 0.6),
                     zm - 0.8, zm + 0.8)
        bar = bar.union(stub).cut(outlet)
    return bar


def astrodome():
    x, r = ASTRODOME
    _, _, top, _, _ = interp(FUSE_STATIONS, x)
    dome = (wp(cq.Solid.makeSphere(r, V(x, 0, top - 0.3)))
            .intersect(box(x - 10, x + 10, -10, 10, top - 0.3, top + 10)))
    plug = cyl((x, 0, top - 1.8), 2 * (r - 0.8) - 2 * FIT, 1.6, "z")
    return dome.union(plug)


def astrodome_socket():
    x, r = ASTRODOME
    _, _, top, _, _ = interp(FUSE_STATIONS, x)
    return cyl((x, 0, top - 1.9), 2 * (r - 0.8), 3.0, "z")


def df_loop_fairing():
    x, L, w, h = DF_LOOP
    _, _, top, _, _ = interp(FUSE_STATIONS, x)
    m = cq.Matrix([[L / 2, 0, 0, 0], [0, w / 2, 0, 0], [0, 0, h / 2, 0]])
    tear = wp(cq.Solid.makeSphere(1.0).transformGeometry(m)).translate((x, 0, top + 2.4))
    mast = box(x - 1.2, x + 1.2, -0.7, 0.7, top - 0.5, top + 2.4)
    return tear.union(mast)


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
    # hex socket in the back of the hub: presses onto the shaft's hex boss
    hexs = (W("YZ").polygon(6, HEX_SOCKET_AF / math.cos(math.pi / 6))
            .extrude(HEX_LEN + 0.1).translate((1.0 - HEX_LEN - 0.1, 0, 0)))
    return prop.cut(hexs)


def prop_shaft(x0, y, zc):
    """Shaft along +x from the prop to the captive flange inside the nacelle."""
    f = cyl((x0 + 5.4, y, zc), FLANGE_D, FLANGE_T, "x")
    sh = cyl((x0 - 0.2, y, zc), SHAFT_D, 5.6, "x")
    col = cyl((x0 - 1.0, y, zc), COLLAR_D, COLLAR_T, "x")
    hx = (W("YZ").polygon(6, HEX_AF / math.cos(math.pi / 6)).extrude(HEX_LEN)
          .translate((x0 - 1.0 - HEX_LEN, y, zc)))
    return f.union(sh).union(col).union(hx)


def axle_pin(start, axis, sign, length, head=True):
    """Printed pin from `start` along sign*axis; optional head outside the start."""
    p = cyl(start, PIN_D, sign * length, axis)
    if head:
        q = list(start)
        q["xyz".index(axis)] -= sign * PIN_HEAD[1]
        p = p.union(cyl(q, PIN_HEAD[0], sign * PIN_HEAD[1], axis))
    return p


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
# LANDING GEAR AND STAND
# ============================================================
def nacelle_bottom(index, x):
    _, zc, x0, length = NACELLES[index]
    _, k = interp(NACELLE_PROFILE, (x - x0) / length)
    z = zc - k * NACELLE_H / 2
    if index == 0 and GEAR_BATH[0][0] <= x <= GEAR_BATH[-1][0]:
        z = min(z, interp(GEAR_BATH, x)[1])
    return z


def gear_socket(x, yc, z_top, leg, plug):
    lx, _ = leg
    py, depth = plug
    return box(x - lx / 2 - FIT, x + lx / 2 + FIT, yc - py / 2 - FIT, yc + py / 2 + FIT,
               z_top - 1, z_top + depth + 0.3)


def gear_fork(x, yc, z_axle, z_top, wheel_w, leg, plug):
    """Two legs either side of the wheel, a cross-bar and a plug (prints flat)."""
    lx, ly = leg
    py, depth = plug
    yo = wheel_w / 2 + 0.6 + ly / 2
    x0, x1 = x - lx / 2, x + lx / 2
    f = box(x0, x1, yc - yo - ly / 2, yc + yo + ly / 2, z_top - 3.0, z_top - 0.1)
    for s in (-1, 1):
        f = f.union(box(x0, x1, yc + s * yo - ly / 2, yc + s * yo + ly / 2,
                        z_axle - lx / 2, z_top - 0.1))
    f = f.union(box(x0, x1, yc - py / 2, yc + py / 2, z_top - 0.2, z_top + depth))
    return f.cut(cyl((x, yc - 20, z_axle), AXLE_HOLE_TIGHT, 40, "y"))


def wheel(x, yc, z_axle, d, w):
    t = W("XZ").circle(d / 2).extrude(w / 2, both=True)
    t = t.edges().fillet(min(2.5, w / 3))
    for s in (-1, 1):   # hub recess on both faces
        t = t.cut(cyl((0, s * (w / 2 + 0.1), 0), d * 0.55, -s * 0.9, "y"))
        t = t.union(cyl((0, s * (w / 2 - 0.8), 0), d * 0.22, s * 0.5, "y"))
    t = t.cut(cyl((0, -w, 0), AXLE_HOLE_LOOSE, 2 * w, "y"))
    return t.translate((x, yc, z_axle))


def stand_parts():
    """Post and base, built level then expressed in the model frame."""
    _, _, _, bot, _ = interp(FUSE_STATIONS, STAND_X)
    S = V(STAND_X, 0, bot)
    th = math.radians(STAND_PITCH)
    ax = ((STAND_X, 0, bot), (STAND_X, 1, bot))
    k = STAND_KEY / 2
    key = box(STAND_X - k, STAND_X + k, -k, k, bot - 2.5, bot + STAND_KEY_DEPTH).rotate(*ax, STAND_PITCH)
    px = S.x - 2.5 * math.sin(th)
    pz = S.z - 2.5 * math.cos(th)
    base_top = bot - STAND_HEIGHT
    hx, hy = STAND_POST[0] / 2, STAND_POST[1] / 2
    post = box(px - hx, px + hx, -hy, hy, base_top + 1.2, pz + 0.8).union(key)
    bl, bw, bt = STAND_BASE
    base = (W("XY").ellipse(bl / 2, bw / 2).extrude(-bt).edges(">Z").chamfer(1.2)
            .translate((px, 0, base_top)))
    base = base.union(box(px - hx - 4, px + hx + 4, -hy - 4, hy + 4, base_top - 0.5, base_top + 10))
    base = base.cut(box(px - hx - FIT, px + hx + FIT, -hy - FIT, hy + FIT, base_top + 1, base_top + 11))
    label = (W("XY").text(STAND_LABEL, 7.0, -0.6, halign="center", valign="center")
             .translate((px, -bw / 2 + 14, base_top)))
    base = base.cut(label)
    # express in the model frame (model is pitched nose-up STAND_PITCH on the stand)
    return post.rotate(*ax, -STAND_PITCH), base.rotate(*ax, -STAND_PITCH), ax


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
        unpitch = (lambda w: w.rotate(*pitch_axis(), wing_pitch()))
        poses[f"wing_inner_{tag}"] = unpitch
        pivot_y = WING_JOINT_Y * side
        poses[f"wing_outer_{tag}"] = (lambda w, s=side, py=pivot_y, u=unpitch:
                                      u(w).rotate((0, py, Z_FLOOR), (1, py, Z_FLOOR), -DIHEDRAL * s))
        for i in range(len(NACELLES)):
            pnl = inner.union(outer)          # tongue pocket must stay clear too
            inb, outb = nacelle_parts(i, side, pnl)
            parts[f"nacelle{i + 1}_{tag}_inboard"] = inb
            parts[f"nacelle{i + 1}_{tag}_outboard"] = outb
            poses[f"nacelle{i + 1}_{tag}_inboard"] = lambda w, s=side: rot(w, "x", -90 * s)
            poses[f"nacelle{i + 1}_{tag}_outboard"] = lambda w, s=side: rot(w, "x", 90 * s)
            yc, zc, x0, _ = NACELLES[i]
            parts[f"prop{i + 1}_{tag}"] = (propeller()
                                          .translate((x0 - PROP_GAP - 1.0, yc * side, zc)))
            poses[f"prop{i + 1}_{tag}"] = lambda w: rot(w, "y", 90)
            parts[f"prop_shaft{i + 1}_{tag}"] = prop_shaft(x0, yc * side, zc)
            poses[f"prop_shaft{i + 1}_{tag}"] = lambda w: rot(w, "y", 90)   # flange on the bed
        yc0 = NACELLES[0][0] * side
        parts[f"main_gear_{tag}"] = gear_fork(MAIN_AXLE_X, yc0, MAIN_AXLE_Z,
                                              nacelle_bottom(0, MAIN_AXLE_X), MAIN_WHEEL_W,
                                              MAIN_LEG, MAIN_PLUG)
        poses[f"main_gear_{tag}"] = lambda w: rot(w, "y", 90)
        parts[f"main_wheel_{tag}"] = wheel(MAIN_AXLE_X, yc0, MAIN_AXLE_Z, MAIN_WHEEL_D, MAIN_WHEEL_W)
        poses[f"main_wheel_{tag}"] = lambda w: rot(w, "x", 90)
        span = MAIN_WHEEL_W + 1.2 + 2 * MAIN_LEG[1]
        parts[f"pin_main_wheel_{tag}"] = axle_pin((MAIN_AXLE_X, yc0 + side * span / 2, MAIN_AXLE_Z),
                                                  "y", -side, span)
        poses[f"pin_main_wheel_{tag}"] = lambda w, s=side: rot(w, "x", -90 * s)   # head down
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

    _, _, _, bot_t, _ = interp(FUSE_STATIONS, TAIL_AXLE_X)
    parts["tail_gear"] = gear_fork(TAIL_AXLE_X, 0, bot_t - TAIL_LEG_DROP, bot_t,
                                   TAIL_WHEEL_W, TAIL_LEG, TAIL_PLUG)
    poses["tail_gear"] = lambda w: rot(w, "y", 90)
    parts["tail_wheel"] = wheel(TAIL_AXLE_X, 0, bot_t - TAIL_LEG_DROP, TAIL_WHEEL_D, TAIL_WHEEL_W)
    poses["tail_wheel"] = lambda w: rot(w, "x", 90)
    tspan = TAIL_WHEEL_W + 1.2 + 2 * TAIL_LEG[1]
    parts["pin_tail_wheel"] = axle_pin((TAIL_AXLE_X, tspan / 2, bot_t - TAIL_LEG_DROP), "y", -1, tspan)
    poses["pin_tail_wheel"] = lambda w: rot(w, "x", -90)
    _, _, top_d, _, _ = interp(FUSE_STATIONS, DORSAL_X)
    parts["pin_dorsal_turret"] = axle_pin((DORSAL_X, 0, top_d - 7.6), "z", 1, 9.0, head=False)
    poses["pin_dorsal_turret"] = lambda w: w
    parts["pin_tail_turret"] = axle_pin((FUSE_END_X - 4.6, 0, TAIL_TURRET_Z), "x", 1, 8.0, head=False)
    poses["pin_tail_turret"] = lambda w: rot(w, "y", 90)
    post, base, sax = stand_parts()
    parts["stand_post"], parts["stand_base"] = post, base
    poses["stand_post"] = lambda w: rot(w.rotate(*sax, STAND_PITCH), "x", 90)
    poses["stand_base"] = lambda w: w.rotate(*sax, STAND_PITCH)

    parts["tailplane"] = tailplane()
    poses["tailplane"] = lambda w: w
    # printed connector keys (one part per key, so the kit is complete)
    for kname, (key, n) in KEY_COUNTS.items():
        for i in range(n):
            parts[f"{kname}_{i + 1}"] = connector_key(key)
            poses[f"{kname}_{i + 1}"] = lambda w: w
    parts["astrodome"] = astrodome()
    poses["astrodome"] = lambda w: w
    for i in range(len(NACELLES)):
        for side, tag in ((1, "stbd"), (-1, "port")):
            for face, ftag in ((1, "a"), (-1, "b")):
                n = f"exhaust{i + 1}_{tag}_{'outboard' if face == side else 'inboard'}"
                parts[n] = exhaust_bank(i, side, face)
                poses[n] = lambda w, fc=face: rot(w, "x", 90 * fc)   # flat back on the bed
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
