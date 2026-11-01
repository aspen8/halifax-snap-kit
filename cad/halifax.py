"""
Handley Page Halifax B Mk II Series IA, 1:60 scale (500 mm span) snap kit.

Run:  python halifax.py OUT_DIR
Writes every kit part as an STL in print orientation (OUT_DIR/print/) and in
assembled position (OUT_DIR/assembled/), plus a STEP assembly.

Axes (assembled): X = distance aft of the nose tip, Y = span (+ = starboard),
Z = up. All units mm at model scale.

Kit layout (no supports needed except where noted):
  fuselage    2 full-width black sections printed on end, keyed; camo spine in 9 clip-on pieces
  nose        clear perspex nose (Series IA)
  canopy      cockpit glazing, drops into the roof
  turrets     dorsal (Type A) and tail (Type E) + separate gun packs
  wings       inner + outer panel per side, flat underside, tongue joints
  nacelles    clamshell halves that close around the wing
  props       4 x 3-blade, spin on a 1.75 mm filament axle
  tail        one-piece tailplane through the fuselage, two fins
"""
import math
import os
import sys
from pathlib import Path

import cadquery as cq
import numpy as np

import kitlib as K

# ============================================================
# PARAMETERS
# ============================================================
SPAN = 500.0                 # mm, tip to tip
SCALE = 30120.0 / SPAN       # ~1:60.2

# --- Fit and printing
FIT = 0.15                   # mm, sliding clearance per side (X2D, PLA)
# Printed connector keys (flat, printed lying down). (length across the split,
# width, thickness) in mm; slots get KEY_FIT per side and END_GAP at each end.
KEY_FIT = 0.15               # mm, press fit per side (fit test on the X2D)
KEY_END_GAP = 0.3            # mm, slot is this much deeper than half a key
KEY_LR = (8.0, 10.0, 2.4)    # fuselage port/starboard halves (width along x)
KEY_FR = (12.0, 6.0, 2.4)    # front/rear fuselage joint (width along z)
KEY_NAC = (11.0, 6.0, 3.0)   # nacelle lock: upright (length z), straddles the halves (thickness y),
                             # top 4 mm in a pocket in the wing underside, 7 mm down into the nacelle
NACELLE_TAIL_FROM = (0.70, 0.62)   # where the lower tail fairing starts, fraction of nacelle length
NACELLE_TAIL_START = ((10.0, 8.0), (7.0, 7.0))   # its depth below the wing and half-width there
NACELLE_KEY_AT = (0.30, 0.06)   # chord fraction of the lock for each nacelle (deep wing and nacelle body)
KEY_NAC_OUTER = (8.0, 6.0, 3.0)  # the outer nacelles are shallower: 3.5 mm up into the wing, 4.5 mm down
NACELLE_KEY_UP = (4.0, 3.5)      # how far each lock goes up into the wing
KEY_FIN = (4.0, 6.0, 1.6)    # tailplane tip into fin: length along y, width along x, thickness z
FIN_KEY_AT = (0.24,)         # one key at the thickest part of the tip (mid-chord broke through)

AXLE_HOLE_TIGHT = 3.05       # mm, printed 2.5 mm pins grip here (fit-test clearance +0.55)
AXLE_HOLE_LOOSE = 3.35       # mm, ...and spin freely here (fit-test clearance +0.85)
WALL = 1.6                   # mm, nose spigot inset from the skin

# --- Fuselage stations: (x, half_width, z_top, z_bottom, squareness)
# squareness: 2 = ellipse, higher = flatter sides (Halifax is slab-sided)
FUSE_STATIONS = [            # measured from the Revell Srs IA side and plan views
    (0.0,   3.0, -19.3, -22.0, 2.0),   # perspex nose dome
    (1.2,   5.0, -15.1, -23.8, 2.1),
    (2.5,   5.9, -12.6, -25.9, 2.2),
    (4.9,   6.7,  -9.8, -28.0, 2.3),
    (8.6,   7.7,  -7.2, -30.7, 2.5),
    (12.3,  8.6,  -5.4, -32.8, 2.6),
    (18.4,  9.7,  -3.5, -34.9, 2.8),
    (25.7, 11.0,  -1.5, -36.0, 3.0),
    (32.9, 12.0,  -0.2, -36.5, 3.2),
    (42.1, 12.65,  1.5, -36.6, 3.4),
    (51.3, 13.0,   3.5, -36.6, 3.6),   # windscreen base
    (54.3, 13.1,   6.7, -36.6, 3.7),
    (57.4, 13.2,   9.5, -36.6, 3.8),
    (60.4, 13.3,  10.5, -36.7, 3.8),
    (63.5, 13.3,  11.1, -36.7, 3.8),
    (67.0, 13.3,  11.4, -36.7, 3.8),   # roof line
    (160.0, 13.3, 11.4, -36.7, 3.8),
    (179.0, 13.1, 11.4, -35.4, 3.8),
    (199.0, 12.9, 11.4, -33.6, 3.7),
    (226.0, 12.4, 11.4, -31.0, 3.6),
    (248.0, 12.0, 11.4, -28.0, 3.5),
    (272.0, 11.5, 11.4, -24.2, 3.3),
    (297.0, 11.0, 11.3, -20.4, 3.1),
    (321.0, 10.4, 11.0, -17.5, 2.9),
    (344.0,  9.5, 10.2, -14.0, 2.6),
    (352.0,  9.0,  9.6, -13.0, 2.5),
]
FUSE_END_X = 352.0
NOSE_SPLIT_X = 12.8          # perspex nose dome ends at this frame (Revell)
NOSE_GLASS_TOP = 50.0        # mm, dome covers the full section
NOSE_SPIGOT_BOX = (5.0, 6.0, -28.0, -16.0)   # length, half-width, z0, z1 of the dome's plug
FUSE_SPLIT_X = 196.0         # front / rear fuselage joint (just ahead of the codes and roundel)
# Fuselage printed Lancaster-style: full-width black sections on end, with the camouflaged
# spine as separate single-colour pieces sitting on the demarcation line.
SPINE_LINE = [(0, -14.2), (52.3, 2.0), (75, 2.0), (85, 1.4), (290, 1.4),  # one straight line to the windscreen: the nose piece is ~5 mm thick with a flat underside
              (299, 4.0), (360, 4.0)]   # x, z: body/spine split (tail: the tailplane floor)
SPINE_WAVE = (0.7, 7.5, 85.0, 290.0)    # scallop amplitude, period, from x, to x
SPINE_CUTS = [(13.0, 52.3, "earth"), (72.8, 100.0, "green"),
              (100.0, 150.2, "earth"), (150.2, 204.5, "green"), (204.5, 230.0, "earth"),
              (230.0, 288.0, "green"), (288.0, 360.0, "earth")]   # x at SPINE_REF_Z
# camo edges lean aft going up (NP-G profile): slope dx/dz of each boundary plane, by its x
SPINE_SLANT = {100.0: 0.15, 150.2: 0.24, 204.5: 0.44, 230.0: 0.57, 288.0: 0.24}   # 204.5: just aft of the turret opening, under the dome
SPINE_REF_Z = 6.5            # height at which the boundary x values are measured
SPINE_GAP = 0.1              # mm, end clearance between neighbouring spine pieces
KEY_CAP = (7.0, 6.0, 2.0)    # spine to body keys: length along z, width along x, thickness y
JOINT_LIP = 7.0              # mm, length of the internal joining lip
NOSE_SPIGOT = 5.0            # mm

# Alignment bosses between port/starboard halves: (x, "top"|"bottom")
FUSE_BOSSES = [              # connector key positions between port/starboard halves
    (40, "top"), (140, "top"), (208, "top"), (235, "top"), (280, "top"),
    (40, "bottom"), (100, "bottom"), (190, "bottom"),
    (235, "bottom"), (290, "bottom"), (318, "bottom"),
]

# --- Cockpit canopy hump: (x, half_width, z_top)
CANOPY_CUT = (52.3, 72.8, 2.0)          # x0, x1, z floor: just the glazed area (Revell); full-width drop-in
CANOPY_KEY = (55.0, 68.0, 3.0, 2.5)      # boss on the fuselage floor: x0, x1, half-width, height
CANOPY_REAR = (72.8, 91.8, 7.0)          # rear roof glazing (Revell plan): x0, x1, z floor
CANOPY_REAR_KEY = (76.0, 82.0, 3.0, 2.0)  # its locating boss
H2S_RADOME = False           # ventral H2S blister (Revell GR.II only; not on the B.II Srs IA)
RADOME = [(202.0, 6.0, 0.5), (206.0, 8.5, 5.0), (211.0, 9.8, 8.8), (217.0, 10.0, 10.3),
          (224.0, 9.4, 9.8), (231.0, 7.6, 7.5), (238.0, 5.0, 3.8), (243.0, 2.5, 1.0),
          (246.0, 0.8, 0.2)]   # x, half-width, depth below the fuselage (Revell side + plan)
WHEEL_UP_X = 147.0           # retracted main wheel, protruding below the nacelle (stand display)
WHEEL_UP_PROUD = 6.0         # mm below the housing
WHEEL_UP_PLUG = (4.0, 9.0, 5.0)   # x, y, depth of the plug into the housing
GEAR_BATH = [(104.0, -27.5, 6.5), (110.0, -33.0, 8.0), (115.0, -34.5, 8.5),
             (157.0, -34.5, 8.5), (160.5, -31.5, 8.0), (163.5, -26.5, 6.5)]  # x, bottom z, half-width: flat-bottomed slab-sided box (Revell side view)

# --- Turrets
DORSAL_X = 195.0             # Boulton Paul Type A Mk VIII (Revell side view)
DORSAL_R = 8.0               # mm, hole radius in the roof
DORSAL_DOME_R = 9.0
DORSAL_DOME_DROP = 0.3       # sphere centre below the base: ~7.5 mm tall above the roof
DORSAL_COLLAR = 2.5          # mm, cylindrical collar under the dome: taller turret (photos)
DORSAL_GUN_Z = 3.0           # mm, gun pack height above the turret base
TAIL_TURRET_R = 9.0          # (old hemisphere turret, unused)
TAIL_TURRET_Z = -2.2
# Boulton Paul Type E rear turret (Revell side and plan views): a tall glazed turret on a flat
# floor, on top of the lower fuselage, which carries on underneath as a tapering cone
TT_X0, TT_REAR, TT_FLOOR, TT_TOP, TT_HW = 345.0, 362.3, -3.0, 14.4, 8.4
TT_PIVOT = TT_REAR - TT_HW              # centre of the rounded rear: pin position
TT_TOP_R = 9.0                          # rounded rear-top edge (side view)
TT_GUN_Z = 3.8                          # gun pack height
TT_TOP_FILLET = 4.5                     # rounding of the turret's top edges
TT_BOSS = (9.0, 3.0)                    # diameter, height of the boss the turret presses over (no pin)
TAIL_CONE = [(344.0, 9.5, 2.0, -14.0, 2.6), (352.0, 9.0, 1.0, -13.0, 2.5), (356.0, 8.4, 0.0, -10.5, 2.4),
             (359.0, 7.2, -1.0, -8.0, 2.3), (361.0, 5.2, -1.6, -5.4, 2.1), (362.0, 2.8, -2.2, -4.0, 2.0)]
TT_FAIRING = [(336.0, 2.5, 10.8, 6.0, 2.2), (341.0, 4.5, 12.6, 6.0, 2.4), (345.2, 6.0, 14.0, 6.0, 2.6)]
GUN_D = 1.2                  # mm, barrel diameter (printable minimum)
GUN_LEN = 13.0               # mm, exposed barrel length
GUN_PITCH = 2.4              # mm, vertical spacing of each stacked pair
GUN_BLOCK = (4.0, 9.0, 4.2)   # breech block x, y, z (two stacked pairs)
GUN_SIDE = 3.2               # mm, each pair this far either side of the centreline

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
ROOT_TONGUE_Z = (0.0, 4.0)   # above the floor: flush with the flat underside, so it prints on the bed
JOINT_TONGUE = (0.26, 0.54, 4.3, 7.7, 12.0)  # joint key: chord fr. start/end, z0, z1 (mid-thickness: >=3.4 mm wall), depth each side
WING_POSE = os.environ.get("HALIFAX_WING_POSE", "end")    # wings stand on their joint faces ('flat' kept for reference:
                                                           # it leaves the leading-edge undersides rough)

# --- Nacelles: (y_centre, z_centre, x_front, length)
NACELLES = [
    (61.0,  -15.7, 77.1, 93.0),      # inner (spinner tip 41 mm ahead of the LE)
    (126.0, -11.0, 88.2, 62.0),      # outer
]
NACELLE_W = 22.0             # mm, max width
NACELLE_H = 21.0             # mm, max height of the body (oval)
RADIATOR_X = 1.5             # mm, chin radiator starts right behind the spinner (photos)
RADIATOR_LEN = 30.0
RADIATOR_R = 6.0
NACELLE_PROFILE = [(0.0, 0.30), (0.02, 0.62), (0.06, 0.86), (0.13, 0.98), (0.25, 1.0),
                   (0.45, 0.95), (0.70, 0.70), (0.90, 0.35), (1.0, 0.08)]

# --- Propellers: Rotol 3-blade, 12 ft 9 in
PROP_D = 3886.0 / SCALE      # ~64.5 mm
PROP_GAP = 1.2               # mm, prop backplate to nacelle front (thrust collar sits here)
# Printed prop shaft (after PB94): flange captured inside the nacelle halves,
# thrust collar outside, hex boss that the prop presses onto. Spins freely.
SHAFT_D, BORE_D = 3.2, 3.9         # mm (2.4 mm snapped; bore keeps the +0.7 spin clearance)
FLANGE_D, FLANGE_T, CAVITY_D = 5.2, 1.2, 6.1
COLLAR_D, COLLAR_T = 6.0, 0.8
HEX_AF, HEX_LEN, HEX_SOCKET_AF = 3.6, 2.5, 4.0   # socket: press fit, scaled from the pin test
PIN_D = 2.5                  # mm, printed axle pins (1.8 mm snapped coming off the plate)

# --- Exhausts (after PB94: a separate bar of stacks plugged into a side slot)
EXH_X0 = 5.0                 # mm behind the nacelle front
EXH_LEN = 26.0               # mm, flame-damper shroud running back to the wing leading edge
EXH_H = 2.6                  # mm, bar height
EXH_Z = 0.8                  # mm above the nacelle centreline
EXH_DEPTH = 2.0              # mm into the nacelle
EXH_SHROUD_D = 3.4             # mm, flame-damper tube diameter (Halifax II photos)
EXH_PROUD = 0.5              # mm proud of the widest nacelle point
EXH_STUBS = 0                # (stub stacks replaced by a shroud tube)
# --- Radiator intake (recess + vanes at the front of each chin radiator)
RAD_INTAKE = (5.0, 3.6, 3.0, 2.4)        # depth, half-width, below/above centre: intake under the prop
RAD_VANES = (0.9, 2.3)                   # |y| of the vanes, either side of centre
RAD_VANE_T = 0.5
# --- Astrodome (clear, plugs into the roof) and D/F loop fairing (moulded on)
ASTRODOME = (87.6, 4.6)                  # x, radius (Revell side view)
DF_LOOP = (117.3, 14.1, 4.0, 4.5)        # nose x, length, width, depth of the teardrop housing (Revell side)
DF_MAST = (0.41, 2.8, 2.0)              # mast position (fraction of length from the nose), x-length, width
DF_PROFILE = [(0.0, 0.05), (0.04, 0.55), (0.12, 0.85), (0.3, 1.0), (0.55, 0.85), (0.8, 0.45), (1.0, 0.04)]
DF_TOP = 7.9                 # mm, fairing top above the roof (stalk + housing)
PIN_HEAD = (5.5, 1.0)        # head diameter, thickness
SPINNER_LEN = 7.5
SPINNER_R = 4.8
BLADE_T = 1.2                # mm
BLADE_ROOT_W, BLADE_MAX_W, BLADE_TIP_W = 3.6, 5.2, 3.4

# --- Tailplane and fins
TAIL_ROOT = (301.6, 40.0)    # x_le, chord at centreline (Revell plan)
TAIL_TIP = (307.9, 34.0)     # at the fin inner face
TAIL_FLOOR = 4.0             # mm, flat underside of the tailplane
TAIL_TC = 0.11
FIN_Y = 76.0                 # mm, fin mid-plane
FIN_X_LE = 305.0
FIN_CHORD = 36.0
FIN_Z_BOTTOM = -23.0
FIN_Z_TOP = 42.5             # ~31 mm above the roof line (side profile)
FIN_T = 3.6
FIN_CORNER_R = 9.0
FIN_POCKET = 0.6             # mm, tailplane tip sits this deep in the fin (seats it; keys hold it)

# --- Landing gear (Messier main legs either side of the wheel; castoring tailwheel)
MAIN_AXLE_X = 120.0          # mm, just aft of the radiator (Revell side view)
MAIN_AXLE_Z = -51.0          # mm
MAIN_WHEEL_D = 26.0          # mm (~1.57 m)
MAIN_WHEEL_W = 9.0
MAIN_LEG = (6.0, 3.0)        # leg section: x (fore-aft), y; ~1.5 mm walls round the axle hole
MAIN_PLUG = (8.0, 6.0)       # plug y-width, depth into the nacelle socket
TAIL_AXLE_X = 334.0
TAIL_LEG_DROP = 9.0          # mm, axle below the fuselage bottom
TAIL_WHEEL_D = 9.0
TAIL_WHEEL_W = 4.5
TAIL_LEG = (5.5, 2.5)        # leg section; ~1.2 mm walls round the axle hole
TAIL_PLUG = (5.0, 5.0)

# --- Display stand (in-flight pose, gear removed)
STAND_X = 165.0              # mm, socket under the fuselage, at the printed model's CG
STAND_KEY = 6.0              # mm, square key into the fuselage socket
STAND_KEY_DEPTH = 9.0
STAND_PITCH = 5.0            # deg, nose-up display attitude
STAND_HEIGHT = 95.0          # mm, fuselage bottom to base top
STAND_BASE = (190.0, 120.0, 12.0)   # mm: length (x), width (y), thickness; display plinth
STAND_BASE_DX = 20.0         # base centre is this far aft of STAND_X (balances the blade)
STAND_BASE_R = 14.0          # plan corner radius
STAND_BASE_BEVEL = 3.5       # underside chamfer (the base looks like it floats)
STAND_FOOT_DX = 60.0         # blade foot this far aft of STAND_X: a swept "swan neck"
STAND_BLADE = (18.0, 9.0, 7.0)    # blade width at the foot, at the top; thickness (y)
STAND_TENON = (12.0, 4.0, 9.0)    # blade tenon into the base: x, y, depth
STAND_BOSS = (34.0, 16.0, 3.0)    # raised stadium around the blade foot: length, width, height

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
    """Slots for a printed key across the split plane at each point (see kitlib)."""
    return K.key_slots(points, axis, split, key, width_axis, KEY_FIT, KEY_END_GAP)


def connector_key(key):
    return K.connector_key(key)


KEY_COUNTS = {}              # filled by the part builders: name -> (key, count)


def radome():
    secs = []
    for x, hw, d in RADOME:
        _, _, _, bot, _ = interp(FUSE_STATIONS, x)
        secs.append(superellipse_wire(x, hw, bot + 3.0, bot - d, 2.4))
    return wp(cq.Solid.makeLoft(secs, ruled=False))


def spine_z(x):
    """Height of the body/spine split (the camouflage demarcation line) at x.
    Rounded scallops (sin^2): no cusps for the B-rep booleans."""
    xs, zs = zip(*SPINE_LINE)
    amp, period, w0, w1 = SPINE_WAVE
    x = np.asarray(x, float)
    wave = amp * np.sin(np.pi * x / period) ** 2 * ((x > w0) & (x < w1))
    return np.interp(x, xs, zs) + wave


def spine_upper():
    """Solid region above the split line (a smooth spline, extruded across the whole width)."""
    pts = [(float(x), float(spine_z(x))) for x in np.arange(-6.0, 401.0, 1.0)]
    return (W("XZ").moveTo(*pts[0]).spline(pts[1:], includeCurrent=True)
            .lineTo(400.0, 80.0).lineTo(-6.0, 80.0).close().extrude(60, both=True))


def spine_end_pose(piece):
    """Pose that stands a spine piece on one of its flat (possibly slanted) end faces:
    whichever leaves less overhang."""
    m = mesh(piece)
    n, a = m.face_normals, m.area_faces
    best = None
    for sgn in (-1, 1):                # front (-x) or rear (+x) end
        sel = (n[:, 0] * sgn > 0.8)
        if not sel.any():
            continue
        # the end plane is the biggest group of faces sharing one slant (ignore slot walls etc.)
        ang = np.degrees(np.arctan2(n[sel, 2], np.abs(n[sel, 0])))
        bins = np.round(ang)
        vals = np.unique(bins)
        main = vals[np.argmax([a[sel][bins == v].sum() for v in vals])]
        grp = np.zeros(len(n), bool)
        grp[np.where(sel)[0][np.abs(ang - main) < 1.5]] = True
        nrm = (n[grp] * a[grp, None]).sum(0)
        nrm /= np.linalg.norm(nrm)
        th = math.degrees(math.atan2(nrm[2], nrm[0]))
        for t in [th + 90, th - 90, -th + 90, -th - 90]:
            M = K.pose_matrix(lambda w, t=t: rot(w, "y", t))
            if (M[:3, :3] @ nrm)[2] > -0.99:
                continue
            pm = m.copy()
            pm.apply_transform(M)
            zmin = pm.bounds[0][2]
            pn, pc = pm.face_normals, pm.triangles_center
            over = pm.area_faces[(pn[:, 2] < -0.64) & (pc[:, 2] > zmin + 0.3)].sum()
            bed = pm.area_faces[(pn[:, 2] < -0.98) & (pc[:, 2] < zmin + 0.2)].sum()
            score = over - 0.2 * bed
            if best is None or score < best[0]:
                best = (score, t)
    return lambda w, t=best[1]: rot(w, "y", t)


def fuselage_parts(wing_tongues):
    """Full-width black body sections (printed on end) and single-colour spine pieces."""
    outer = fuselage_solid()
    body = outer

    # sockets and slots
    cx0, cx1, cz = CANOPY_CUT
    rx0, rx1, rz = CANOPY_REAR
    if H2S_RADOME:
        outer = outer.union(radome())
        body = outer
    # rear: turret seat (flat floor), lower tail cone under the turret, fairing up into its front
    body = body.cut(box(TT_X0, 400, -30, 30, TT_FLOOR, 40))   # cone and fairing are added as meshes below
    _, _, top_d, _, _ = interp(FUSE_STATIONS, DORSAL_X)
    body = body.cut(box(cx0, cx1, -30, 30, cz, 30))                          # canopy
    body = body.cut(box(rx0, rx1, -30, 30, rz, 30))                          # rear roof glazing
    for (k0, k1, khw, kh), z in ((CANOPY_KEY, cz), (CANOPY_REAR_KEY, rz)):  # locating bosses
        body = body.union(box(k0, k1, -khw, khw, z - 0.5, z + kh))
    body = body.cut(cyl((DORSAL_X, 0, top_d - 3.0), 2 * DORSAL_R, 20, "z"))  # dorsal turret
    for c in tailplane_slot_cuts():
        body = body.cut(c)
    body = body.union(df_loop_fairing()).cut(astrodome_socket())
    for pocket in wing_tongues:
        body = body.cut(pocket)
    _, _, _, bot_t, _ = interp(FUSE_STATIONS, TAIL_AXLE_X)
    body = body.cut(gear_socket(TAIL_AXLE_X, 0, bot_t, TAIL_LEG, TAIL_PLUG))
    _, _, _, bot_s, _ = interp(FUSE_STATIONS, STAND_X)
    k = STAND_KEY / 2 + FIT
    body = body.cut(box(STAND_X - k, STAND_X + k, -k, k, bot_s - 1, bot_s + STAND_KEY_DEPTH + 0.3))
    # nose locator: a wide peg standing out of the fuselage nose face; the glazing slots over it
    # (the fuselage prints on end, so the peg builds straight up; the glazing prints flat-back down)
    sl, shw, sz0, sz1 = NOSE_SPIGOT_BOX
    glass_zone = box(-5, NOSE_SPLIT_X, -50, 50, -60, NOSE_GLASS_TOP)
    body = body.cut(glass_zone)
    body = body.union(box(NOSE_SPLIT_X - sl, NOSE_SPLIT_X + 0.5, -shw, shw, sz0, sz1))

    # spine (camo) pieces above the split line; full-width black body below it.
    # The split is done with mesh booleans (manifold3d): OCC fails on this cut.
    def M(w):
        return K.to_manifold(mesh(w))

    def T(man):
        import trimesh
        V, F = K.mesh_of(man)
        return trimesh.Trimesh(V, F)

    def mbox(x0, x1, y0, y1, z0, z1):
        return K.box(x0, x1, y0, y1, z0, z1)

    B = M(body) + M(tail_cone()) + M(tail_fairing())        # OCC's union of these isn't watertight
    B = B + M(cyl((TT_PIVOT, 0, TT_FLOOR - 0.5), TT_BOSS[0], TT_BOSS[1] + 0.5, "z"))   # turret boss
    pts = [(float(x), float(spine_z(x))) for x in np.arange(-6.0, 401.0, 0.5)] + [(400.0, 80.0), (-6.0, 80.0)]
    upper = K.prism_y(K.cs([np.array(pts)]))
    cap, Bb = B ^ upper, B - upper
    # the canopy's locating boss rises above the split line where there is no spine piece
    # (the canopy fills that gap), so it stays on the body
    k0, k1, khw, kh = CANOPY_KEY
    Bb = Bb + mbox(k0, k1, -khw, khw, cz - 0.5, cz + kh)
    # front/rear keys on the joint face, below the spine line
    _, hw, top, bot, _ = interp(FUSE_STATIONS, FUSE_SPLIT_X)
    zs = float(spine_z(FUSE_SPLIT_X))
    fr = [(0, y, z) for y in (-hw / 2, hw / 2) for z in (bot + 6, (bot + zs) / 2, zs - 6)]
    fr_holes = M(key_slots(fr, "x", FUSE_SPLIT_X, KEY_FR, "z"))
    KEY_COUNTS["key_fuselage_joint"] = (KEY_FR, len(fr))
    # spine-to-body keys: one or two per piece, clear of the tailplane tunnel
    cap_holes = K.box(0, 0.001, 0, 0.001, 0, 0.001)
    n_keys = 0
    def thick(x):
        return interp(FUSE_STATIONS, x)[2] - float(spine_z(x))
    tail = (TAIL_ROOT[0] - 3 - KEY_CAP[1] / 2, TAIL_ROOT[0] + TAIL_ROOT[1] + 3 + KEY_CAP[1] / 2)
    for x0, x1, _ in SPINE_CUTS:
        n = 2 if x1 - x0 >= 45 else 1
        for i in range(n):           # in each share of the piece, the thickest spot clear of the tail
            a = x0 + (x1 - x0) * i / n + KEY_CAP[1] + 6 * SPINE_SLANT.get(x0, 0.0)
            b = x0 + (x1 - x0) * (i + 1) / n - KEY_CAP[1] - 6 * SPINE_SLANT.get(x1, 0.0)
            cand = [x for x in np.linspace(a, b, 25) if not tail[0] < x < tail[1]]
            if not cand:
                continue
            x = max(cand, key=thick)
            z = float(spine_z(x))
            cap_holes = cap_holes + M(key_slots([(x, 0, z)], "z", z, KEY_CAP, "x"))
            n_keys += 1
    KEY_COUNTS["key_spine"] = (KEY_CAP, n_keys)

    parts = {}
    for sec_name, (a, b) in (("front", (-5, FUSE_SPLIT_X)), ("rear", (FUSE_SPLIT_X, 400))):
        parts[f"fuselage_{sec_name}"] = T(K.largest_piece((Bb ^ mbox(a, b, -50, 50, -60, 60))
                                                          - fr_holes - cap_holes)[0])
    def behind(xb, gap):
        """Half-space aft of the slanted boundary plane x = xb + k (z - ref) (+ gap)."""
        k = SPINE_SLANT.get(xb, 0.0)
        z0, z1 = -100.0, 100.0
        x = lambda z: xb + gap + k * (z - SPINE_REF_Z)
        return K.prism_y(K.cs([np.array([(x(z0), z0), (500.0, z0), (500.0, z1), (x(z1), z1)])]))

    for i, (x0, x1, col) in enumerate(SPINE_CUTS):
        piece = (cap ^ behind(x0, SPINE_GAP / 2)) - behind(x1, -SPINE_GAP / 2) - cap_holes
        parts[f"spine_{i + 1:02d}_{col}"] = T(K.largest_piece(piece)[0])

    # perspex chin dome with a plug into the front section
    parts["nose_glazing"] = (outer.intersect(glass_zone)
                             .cut(box(NOSE_SPLIT_X - sl - 0.4, NOSE_SPLIT_X + 1, -shw - KEY_FIT, shw + KEY_FIT,
                                      sz0 - KEY_FIT, sz1 + KEY_FIT)))

    # glazing: drop-ins with flat bottoms (print flat), recessed over the fuselage bosses
    def recess(key, z):
        k0, k1, khw, kh = key
        return box(k0 - FIT, k1 + FIT, -khw - FIT, khw + FIT, z - 1, z + kh + 0.3)
    parts["canopy"] = (outer.intersect(box(cx0 + FIT, cx1 - FIT, -30, 30, cz + FIT, 30))
                       .cut(recess(CANOPY_KEY, cz)))
    parts["canopy_rear"] = (outer.intersect(box(rx0 + FIT, rx1 - FIT, -30, 30, rz + FIT, 30))
                            .cut(recess(CANOPY_REAR_KEY, rz)).cut(astrodome_socket()))
    return parts


# ============================================================
# TURRETS AND GUNS
# ============================================================
def gun_pack():
    """Breech block with four barrels: a vertically stacked pair either side (Boulton Paul)."""
    bx, by, bz = GUN_BLOCK
    g = box(0, bx, -by / 2, by / 2, 0, bz)
    for y in (-GUN_SIDE, GUN_SIDE):
        for z in (bz / 2 - GUN_PITCH / 2, bz / 2 + GUN_PITCH / 2):
            g = g.union(cyl((bx - 0.2, y, z), GUN_D, GUN_LEN + 0.2, "x"))
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
    dome = (wp(cq.Solid.makeSphere(DORSAL_DOME_R, V(DORSAL_X, 0, base_z + DORSAL_COLLAR - DORSAL_DOME_DROP)))
            .intersect(box(DORSAL_X - 20, DORSAL_X + 20, -20, 20, base_z + DORSAL_COLLAR, 40)))
    r_c = (DORSAL_DOME_R ** 2 - DORSAL_DOME_DROP ** 2) ** 0.5
    dome = dome.union(cyl((DORSAL_X, 0, base_z), 2 * r_c, DORSAL_COLLAR + 0.01, "z"))
    plug = cyl((DORSAL_X, 0, top - 3.0 + FIT), 2 * (DORSAL_R - FIT), base_z - top + 3.0, "z")
    t = dome.union(plug)
    # guns point aft out of a slot at the back of the dome
    t = t.cut(gun_slot((DORSAL_X + DORSAL_DOME_R - 2.0, 0, base_z + DORSAL_GUN_Z), +1))
    t = t.cut(fuselage_solid().cut(cyl((DORSAL_X, 0, top - 3.0), 2 * DORSAL_R, 20, "z")))
    # no pin: the wide plug turns in the roof hole
    return t


def tail_cone():
    """Lower rear fuselage carried on under the turret, flat on top (the turret floor)."""
    secs = [superellipse_wire(x, hw, top, bot, n) for x, hw, top, bot, n in TAIL_CONE]
    cone = wp(cq.Solid.makeLoft(secs, ruled=True))      # ruled: no bulge below the fuselage line
    return cone.intersect(box(TAIL_CONE[0][0], 400, -30, 30, -40, TT_FLOOR))


def tail_fairing():
    """Fairing from the spine up into the turret front."""
    secs = [superellipse_wire(x, hw, top, bot, n) for x, hw, top, bot, n in TT_FAIRING]
    return wp(cq.Solid.makeLoft(secs, ruled=False))


def tail_turret():
    """Type E turret: plan = rounded rear, side = rounded rear-top; sits on the tail cone floor."""
    plan = (W("XY").moveTo(TT_X0 + 0.3, -TT_HW).lineTo(TT_PIVOT, -TT_HW)
            .threePointArc((TT_REAR, 0), (TT_PIVOT, TT_HW)).lineTo(TT_X0 + 0.3, TT_HW).close()
            .extrude(TT_TOP - TT_FLOOR + 2).translate((0, 0, TT_FLOOR - 1)))
    r = TT_TOP_R
    side = (W("XZ").moveTo(TT_X0 + 0.3, TT_FLOOR).lineTo(TT_REAR + 1, TT_FLOOR)
            .lineTo(TT_REAR + 1, TT_TOP - r).threePointArc((TT_REAR - r * (1 - 0.7071) + 0.6, TT_TOP - r * (1 - 0.7071)),
                                                       (TT_REAR - r + 1, TT_TOP))
            .lineTo(TT_X0 + 0.3, TT_TOP).close().extrude(30, both=True))
    t = plan.intersect(side)
    t = t.faces(">Z").edges().fillet(TT_TOP_FILLET)   # domed top all round (photos)
    t = t.cut(gun_slot((TT_REAR - 1.5, 0, TT_GUN_Z), +1))
    t = t.cut(cyl((TT_PIVOT, 0, TT_FLOOR - 0.1), TT_BOSS[0] + 2 * KEY_FIT, TT_BOSS[1] + 0.3, "z"))   # sits over the boss
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

    # inner/outer joint: flat faces at the dihedral bisector and a printed connector key
    # (flat ends let both panels print standing on end)
    fs, fe, z0, z1, depth = JOINT_TONGUE
    x, c, _ = outer_planform(WING_JOINT_Y)
    slot = box(x + fs * c - KEY_FIT, x + fe * c + KEY_FIT,
               WING_JOINT_Y - depth - KEY_END_GAP, WING_JOINT_Y + depth + KEY_END_GAP,
               Z_FLOOR + z0 - KEY_FIT, Z_FLOOR + z1 + KEY_FIT)
    KEY_COUNTS["key_wing"] = ((2 * depth, round((fe - fs) * c, 1), z1 - z0), 2)
    pivot = ((0, WING_JOINT_Y, Z_FLOOR), (1, WING_JOINT_Y, Z_FLOOR))
    slot = slot.rotate(*pivot, DIHEDRAL / 2)
    outer = outer.rotate(*pivot, DIHEDRAL)
    half = box(-100, 400, WING_JOINT_Y, WING_JOINT_Y + 300, Z_FLOOR - 50, Z_FLOOR + 50)
    half = half.rotate(*pivot, DIHEDRAL / 2)
    inner = inner.cut(half).cut(slot)
    outer = outer.intersect(half).cut(slot)

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
    secs = [superellipse_wire(x, hw, zc, bot, 4.0) for x, bot, hw in GEAR_BATH]
    return wp(cq.Solid.makeLoft(secs, ruled=True)).translate((0, y, 0))


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


def nacelle_lock_slot(index, side, wing_panel):
    """Slot for the nacelle lock key: 4 mm up into the wing underside, 7 mm down into the nacelle,
    centred on the nacelle split plane (half of its thickness in each half)."""
    yc = NACELLES[index][0] * side
    s = abs(yc)
    if s <= PLANFORM[1][0] or s < WING_JOINT_Y:
        _, le, c = interp(PLANFORM, s)
    else:
        le, c, _ = outer_planform(s)
    x = le + NACELLE_KEY_AT[index] * c
    probe = wing_panel.intersect(box(x - 0.05, x + 0.05, yc - 0.05, yc + 0.05, -100, 100))
    wb = probe.val().BoundingBox().zmin            # wing underside at the key
    key = KEY_NAC if index == 0 else KEY_NAC_OUTER
    zc = wb + NACELLE_KEY_UP[index] - key[0] / 2
    return key_slots([(x, yc, zc)], "z", zc, key, "x")


def wing_underside(wing_panel, x, y):
    probe = wing_panel.intersect(box(x - 0.05, x + 0.05, y - 0.05, y + 0.05, -100, 100))
    return probe.val().BoundingBox().zmin


def nacelle_tail(index, side, wing_panel):
    """Lower nacelle fairing carried on under the wing to the trailing edge (Revell side view,
    photos): starts inside the nacelle body and tapers to a point under the trailing edge."""
    yc, zc, x0, length = NACELLES[index]
    y = yc * side
    s = abs(y)
    if s < WING_JOINT_Y:
        _, le, c = interp(PLANFORM, s)
    else:
        le, c, _ = outer_planform(s)
    te = le + c - 1.0
    xa = x0 + NACELLE_TAIL_FROM[index] * length
    depth0, hw0 = NACELLE_TAIL_START[index]
    secs = []
    for f in np.linspace(0, 1, 6):
        x = xa + f * (te - xa)
        wb = wing_underside(wing_panel, x, y)
        hw = 1.5 + (hw0 - 1.5) * (1 - f) ** 0.7       # broad "boat" tail, blunt end
        dp = 1.0 + (depth0 - 1.0) * (1 - f) ** 1.0
        secs.append(superellipse_wire(x, hw, wb + 1.5, wb - dp, 2.6))
    return wp(cq.Solid.makeLoft(secs, ruled=False)).translate((0, y, 0))


def nacelle_parts(index, side, wing_panel):
    yc, zc, x0, length = NACELLES[index]
    body = nacelle_body(zc, x0, length).translate((0, yc * side, 0))
    if index == 0:   # undercarriage housing under the inner nacelles
        body = body.union(gear_bath(yc * side, zc))
    body = body.union(nacelle_tail(index, side, wing_panel))   # lower fairing back to the trailing edge
    # notch for the wing, with clearance top and bottom
    body = (body.cut(wing_panel)
            .cut(wing_panel.translate((0, 0, FIT)))
            .cut(wing_panel.translate((0, 0, -FIT))))
    if index == 0:   # socket for the wheels-up insert (stand display)
        px, py, pd = WHEEL_UP_PLUG
        zb = nacelle_bottom(0, WHEEL_UP_X)
        body = body.cut(box(WHEEL_UP_X - px / 2 - FIT, WHEEL_UP_X + px / 2 + FIT,
                            yc * side - py / 2 - FIT, yc * side + py / 2 + FIT, zb - 1, zb + pd + 0.3))
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
    # one upright lock: joins the two halves and pins the nacelle into a pocket in the wing
    y = yc * side
    holes = nacelle_lock_slot(index, side, wing_panel)
    kname, key = ("key_nacelle", KEY_NAC) if index == 0 else ("key_nacelle_outer", KEY_NAC_OUTER)
    KEY_COUNTS[kname] = (key, KEY_COUNTS.get(kname, (key, 0))[1] + 1)
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
    # flame-damper shroud: a tube along the bar, rounded front, tapered tail
    r = EXH_SHROUD_D / 2
    yt = Y + face * (y_out + r - 0.6)
    tube = cyl((xs + r, yt, zm), EXH_SHROUD_D, EXH_LEN - r - 5.0, "x")
    tail = wp(cq.Solid.makeCone(r, 0.7, 5.0, V(xe - 5.0, yt, zm), V(1, 0, 0)))
    nose = wp(cq.Solid.makeSphere(r, V(xs + r, yt, zm)))
    shroud = tube.union(tail).union(nose)
    shroud = shroud.intersect(box(xs - 1, xe + 1, min(lo, hi) - 10, max(lo, hi) + 10, zm - r - 1, zm + r + 1))
    bar = bar.union(shroud)
    pitch = EXH_LEN / max(EXH_STUBS, 1)
    for k in range(EXH_STUBS):   # (none: kept for reference)
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
    skirt = cyl((x, 0, top - 0.3), 2 * r, 0.7, "z")
    dome = (wp(cq.Solid.makeSphere(r, V(x, 0, top + 0.4)))
            .intersect(box(x - 10, x + 10, -10, 10, top + 0.4, top + 10)))
    plug = cyl((x, 0, top - 1.9), 2 * (r - 0.8) - 2 * FIT, 2.6, "z")   # overlaps the dome: one solid
    # skirt conforms to the curved roof (only the plug goes below the surface)
    return skirt.union(dome).cut(fuselage_solid()).union(plug)


def astrodome_socket():
    x, r = ASTRODOME
    _, _, top, _, _ = interp(FUSE_STATIONS, x)
    return cyl((x, 0, top - 1.9), 2 * (r - 0.8), 3.0, "z")


def df_loop_fairing():
    """D/F loop housing: a teardrop (round nose forward, pointed tail) on a short mast."""
    x0, L, w, d = DF_LOOP
    f, mx, mw = DF_MAST
    xm = x0 + f * L
    _, _, top, _, _ = interp(FUSE_STATIONS, xm)
    zc = top + DF_TOP - d / 2
    tear = revolve_profile([(x0 + a * L, k * d / 2) for a, k in DF_PROFILE])
    tear = wp(tear.val().transformGeometry(cq.Matrix([[1, 0, 0, 0], [0, w / d, 0, 0], [0, 0, 1, 0]])))
    tear = tear.translate((0, 0, zc))
    mast = box(xm - mx / 2, xm + mx / 2, -mw / 2, mw / 2, top - 0.5, zc)
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


def tailplane_slot_cuts():
    """The tailplane's own aerofoil, grown by FIT: the halves close round it and keep a solid
    roof above it (a plain box slot broke through the tapering top and left a loose strip)."""
    tp = tailplane().intersect(box(TAIL_ROOT[0] - 5, TAIL_ROOT[0] + TAIL_ROOT[1] + 5, -20, 20, -50, 50))
    return [tp.translate((dx, 0, dz)) for dx, dz in
            ((0, 0), (FIT, 0), (-FIT, 0), (0, FIT), (0, -FIT), (FIT, FIT), (-FIT, FIT))]


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
    # tailplane tip sits in a shallow recess, held by two printed keys
    return f.cut(fin_key_slots(side))


def fin_key_slots(side):
    """Key slots across the tailplane-tip / fin joint (cut into both parts)."""
    y_tip = FIN_Y - FIN_T / 2 + FIN_POCKET
    x0, c = TAIL_TIP
    pts = [(x0 + f * c, 0, TAIL_FLOOR + 0.46 * TAIL_TC * c) for f in FIN_KEY_AT]   # mid-thickness
    KEY_COUNTS["key_fin"] = (KEY_FIN, 2 * len(pts))
    return key_slots(pts, "y", side * y_tip, KEY_FIN, "x")


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


def wheel_up_insert(side):
    """Black tyre segment that shows below the inner nacelle with the gear up."""
    yc = NACELLES[0][0] * side
    zb = nacelle_bottom(0, WHEEL_UP_X)
    r = MAIN_WHEEL_D / 2
    zc = zb - WHEEL_UP_PROUD + r
    tyre = cyl((WHEEL_UP_X, yc - MAIN_WHEEL_W / 2, zc), MAIN_WHEEL_D, MAIN_WHEEL_W, "y")
    seg = tyre.intersect(box(WHEEL_UP_X - 20, WHEEL_UP_X + 20, yc - 10, yc + 10, zb - 10, zb))
    _, zcn, x0, length = NACELLES[0]
    seg = seg.cut(nacelle_body(zcn, x0, length).translate((0, yc, 0))).cut(gear_bath(yc, zcn))
    px, py, pd = WHEEL_UP_PLUG
    plug = box(WHEEL_UP_X - px / 2, WHEEL_UP_X + px / 2, yc - py / 2, yc + py / 2, zb - 0.1, zb + pd)
    return seg.union(plug)


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


def stand_frame():
    """Level-frame numbers shared with colour.py: (support point S, base top z, base centre x)."""
    _, _, _, bot, _ = interp(FUSE_STATIONS, STAND_X)
    return V(STAND_X, 0, bot), bot - STAND_HEIGHT, STAND_X + STAND_BASE_DX


def bezier(p, n=48):
    t = np.linspace(0, 1, n)[:, None]
    p = [np.asarray(q, float) for q in p]
    return ((1 - t) ** 3 * p[0] + 3 * (1 - t) ** 2 * t * p[1]
            + 3 * (1 - t) * t ** 2 * p[2] + t ** 3 * p[3])


def stand_blade(foot, top, top_dir):
    """Tapered swept blade in the XZ plane (prints flat on its side), edges rounded."""
    w0, w1, t = STAND_BLADE
    h = top[1] - foot[1]
    spine = bezier([foot, (foot[0], foot[1] + 0.5 * h),
                    (top[0] - top_dir[0] * 0.45 * h, top[1] - top_dir[1] * 0.45 * h), top], 24)
    d = np.gradient(spine, axis=0)
    d /= np.linalg.norm(d, axis=1)[:, None]
    nrm = np.c_[-d[:, 1], d[:, 0]]
    w = np.linspace(w0, w1, len(spine))[:, None] / 2
    left, right = spine + nrm * w, spine - nrm * w
    pts = [tuple(p) for p in left] + [tuple(p) for p in right[::-1]]
    blade = (W("XZ").moveTo(*left[0]).spline(pts[1:len(left)], includeCurrent=True)
             .lineTo(*right[-1]).spline(pts[len(left) + 1:], includeCurrent=True).close()
             .extrude(t / 2, both=True))
    return blade.faces(">Y or <Y").edges().fillet(1.5)   # 24-point splines keep this valid


def stand_parts():
    """Swept blade and display plinth, built level then expressed in the model frame."""
    S, base_top, bcx = stand_frame()
    th = math.radians(STAND_PITCH)
    ax = ((STAND_X, 0, S.z), (STAND_X, 1, S.z))
    k = STAND_KEY / 2
    key = box(STAND_X - k, STAND_X + k, -k, k, S.z - 2.5, S.z + STAND_KEY_DEPTH).rotate(*ax, STAND_PITCH)
    top = (S.x - 2.5 * math.sin(th), S.z - 2.5 * math.cos(th))
    foot = (STAND_X + STAND_FOOT_DX, base_top + STAND_BOSS[2])
    tx, ty, td = STAND_TENON
    tenon = box(foot[0] - tx / 2, foot[0] + tx / 2, -ty / 2, ty / 2, foot[1] - td, foot[1] + 1.0)
    # OCC sometimes drops the spline blade from the union; nudge the tip until it holds
    for eps in np.arange(0.0, 1.0, 0.05):
        blade = stand_blade(foot, (top[0] - 0.8 * math.sin(th), top[1] + (0.8 + eps) * math.cos(th)),
                            (math.sin(th), math.cos(th)))
        post = blade.union(tenon).union(key)
        if post.val().isValid() and post.val().Volume() > blade.val().Volume():
            break
    else:
        raise RuntimeError("stand blade union failed")
    # plinth: rounded slab, bevelled underside, rounded top edge, raised boss round the foot
    bl, bw, bt = STAND_BASE
    base = (W("XY").rect(bl, bw).extrude(-bt).edges("|Z").fillet(STAND_BASE_R)
            .edges("<Z").chamfer(STAND_BASE_BEVEL).edges(">Z").fillet(1.5)
            .translate((bcx, 0, base_top)))
    sl, sw, sh = STAND_BOSS
    boss = (W("XY").slot2D(sl, sw).extrude(sh).edges(">Z").fillet(1.0)
            .translate((foot[0], 0, base_top - 0.01)))
    base = base.union(boss)
    base = base.cut(box(foot[0] - tx / 2 - FIT, foot[0] + tx / 2 + FIT, -ty / 2 - FIT, ty / 2 + FIT,
                        foot[1] - td - 0.4, foot[1] + 1))
    base = base.cut(post)                    # the blade's foot seats flush in the boss
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
        pivot_y = WING_JOINT_Y * side
        jp = ((0, pivot_y, Z_FLOOR), (1, pivot_y, Z_FLOOR))
        if WING_POSE == "end":     # stand each panel on its joint face (the bisector plane)
            poses[f"wing_inner_{tag}"] = (lambda w, s=side, jp=jp, u=unpitch:
                                          rot(u(w).rotate(*jp, -DIHEDRAL / 2 * s), "x", -90 * s))
            poses[f"wing_outer_{tag}"] = (lambda w, s=side, jp=jp, u=unpitch:
                                          rot(u(w).rotate(*jp, -DIHEDRAL / 2 * s), "x", 90 * s))
        else:
            poses[f"wing_inner_{tag}"] = unpitch
            poses[f"wing_outer_{tag}"] = (lambda w, s=side, jp=jp, u=unpitch:
                                          u(w).rotate(*jp, -DIHEDRAL * s))
        for i in range(len(NACELLES)):
            pnl = inner.union(outer)          # tongue pocket must stay clear too
            inb, outb = nacelle_parts(i, side, pnl)
            lock = nacelle_lock_slot(i, side, pnl)     # matching pocket in the wing underside
            parts[f"wing_inner_{tag}"] = parts[f"wing_inner_{tag}"].cut(lock)
            parts[f"wing_outer_{tag}"] = parts[f"wing_outer_{tag}"].cut(lock)
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
        parts[f"wheel_up_{tag}"] = wheel_up_insert(side)
        poses[f"wheel_up_{tag}"] = lambda w: rot(w, "x", 90)               # flat side down
        parts[f"fin_{tag}"] = fin(side)
        poses[f"fin_{tag}"] = lambda w, s=side: rot(w, "x", 90 * s)   # inner (fuselage-facing) face down on both

    fp = fuselage_parts(tongues)
    for k, v in fp.items():
        parts[k] = v
        if k == "fuselage_front":
            poses[k] = lambda w: rot(w, "y", 90)      # on end, standing on the joint face
        elif k == "fuselage_rear":
            poses[k] = lambda w: rot(w, "y", -90)
        elif k.startswith("spine_"):
            i = int(k.split("_")[1]) - 1
            if SPINE_CUTS[i][1] <= 55:       # nose piece: lie on its flat, sloping underside
                (x0, z0), (x1, z1) = SPINE_LINE[0], SPINE_LINE[1]
                tilt = math.degrees(math.atan2(z1 - z0, x1 - x0))
                poses[k] = lambda w, t=tilt: rot(w, "y", t)
            else:                             # others stand on their bigger (slanted) end face
                poses[k] = spine_end_pose(v)
        elif k == "nose_glazing":
            poses[k] = lambda w: rot(w, "y", 90)      # flat back face down, dome up
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
    post, base, sax = stand_parts()
    parts["stand_post"], parts["stand_base"] = post, base
    poses["stand_post"] = lambda w: rot(w.rotate(*sax, STAND_PITCH), "x", 90)
    poses["stand_base"] = lambda w: w.rotate(*sax, STAND_PITCH)

    parts["tailplane"] = tailplane().cut(fin_key_slots(1)).cut(fin_key_slots(-1))
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
    poses["turret_tail"] = lambda w: w               # upright on its flat floor
    _, _, top, _, _ = interp(FUSE_STATIONS, DORSAL_X)
    parts["guns_dorsal"] = gun_pack().translate(
        (DORSAL_X + DORSAL_DOME_R - 2.0 - GUN_BLOCK[0], 0, top - 1.2 + DORSAL_GUN_Z))
    parts["guns_tail"] = gun_pack().translate(
        (TT_REAR - 1.5 - GUN_BLOCK[0], 0, TT_GUN_Z))
    poses["guns_dorsal"] = poses["guns_tail"] = lambda w: w
    return parts, poses


def mesh(w, tol=0.02, ang=0.15):
    """Tessellate a part to a trimesh (exact bounds, unlike the B-rep box)."""
    import trimesh
    if isinstance(w, trimesh.Trimesh):          # parts made with mesh booleans pass through
        return w.copy()
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
        am = mesh(w)
        if hasattr(w, "vals"):
            valid = w.val().isValid()
            if len(w.vals()) > 1:
                print(f"!! {name}: {len(w.vals())} separate solids")
        else:
            valid = am.is_watertight
        am.export(OUT_DIR / "assembled" / f"{name}.stl")
        pm = am.copy()
        pm.apply_transform(K.pose_matrix(poses[name]))
        lo, hi = pm.bounds
        pm.apply_translation(-lo)
        ext = hi - lo
        fits = "ok" if max(ext[0], ext[1]) <= bed and ext[2] <= 256 else "TOO BIG"
        pm.export(OUT_DIR / "print" / f"{name}.stl")
        print(f"{name:28s} valid={valid!s:5s} watertight={pm.is_watertight!s:5s} "
              f"{ext[0]:6.1f} x {ext[1]:6.1f} x {ext[2]:5.1f} mm  {fits}", flush=True)
