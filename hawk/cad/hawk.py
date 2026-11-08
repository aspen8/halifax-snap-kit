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
  wings        one piece per side, printed standing on the flat root (tip up, brim);
               underside fins moulded on (45 deg inboard faces), leading-edge fences separate
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
    (38.5, 11.3,  13.6,  -7.7, 3.2),
    (53.0, 11.4,  15.4,  -7.9, 3.6),
    (70.0, 11.4,  17.5,  -8.2, 3.8),
    (90.0, 11.5,  20.0,  -8.4, 3.8),
    (110.0, 11.7, 22.0,  -8.5, 3.6),
    (117.0, 11.75, 25.5, -8.4, 3.0, 13.0, 3.4),     # v22: the body's upper sides rise out from
    (124.0, 11.8, 28.0,  -8.3, 3.0, 13.0, 3.4),     # under the canopy fairing gradually (its top
                                                    # went 23 -> 33.6 over X 124-134: a step in the
                                                    # side, seen as a kink behind the canopy)
    # behind the cockpit the body takes the whole top line (no separate spine): an "egg"
    # section, widest at z_w, rounder above (n_up) than below. x, hw, top, bottom, n_lo, z_w, n_up
    (134.0, 11.8, 33.6,  -8.0, 2.6, 13.0, 3.4),     # upright sides behind the canopy (photos):
    (140.0, 11.7, 34.6,  -7.9, 2.6, 13.0, 3.8),     # widest higher up and squarer above, so
    (152.6, 11.6, 33.6,  -7.4, 2.5, 12.5, 3.3),     # the side runs up flat and only rounds
    (166.7, 11.6, 32.4,  -6.7, 2.6, 12.0, 2.9),     # over near the top. v22: squarer shoulders
                                                    # (n_up) from X 134 to 167, so they carry on
                                                    # behind the canopy fairing (it ends at X 142)
                                                    # instead of dropping 3 mm: a waist there
    (180.9, 11.6, 31.2,  -5.2, 2.8, 11.0, 2.8),
    (195.0, 11.6, 29.2,  -3.9, 3.1, 9.5, 4.5),
    (208.0, 11.5, 27.6,  -3.0, 3.2, 8.0, 6.5),
    (226.0, 11.2, 25.9,  -2.0, 2.8, 8.0, 6.0),      # v18: boxy above the widest line, round below
    (240.0, 10.8, 24.6,  -1.3, 2.4, 8.0, 5.5),      # it, the bottom going cylindrical round the jet
    (252.0, 10.0, 23.0,  -0.6, 2.15, 8.0, 5.0),     # pipe (reference from behind); the change of
    (264.2,  8.8, 20.2,   1.0, 2.0, 7.8, 5.0),      # curve at z_w reads as a faint waist line
]
FUSE_END_X = 264.2
# (v7: the upper squareness n_up rose to 10 from X 226 back; v18 softens it to 5-6, which matches
# the reference from behind, and rounds the bottom (n_lo 2.0 at the end, was 4.2))
# Canopy and dorsal spine: (x, half_width, z_top); bottom is buried 6 mm in the body
SPINE_STATIONS = [            # canopy and the fairing just behind it (aft of x 140 the body takes over)
    # v10: heights from X 41 to 105 traced off the Revell side view, one convex arc from the
    # windscreen (v9 ran nearly straight here and sat up to 2.9 mm low at X 60-65)
    (37.0,  8.6, 13.0),
    (41.0,  9.4, 16.4),
    (47.0, 10.0, 20.5),
    (53.5, 10.2, 24.6),
    (59.7, 10.4, 27.9),
    (68.0, 10.6, 31.5),
    (76.6, 10.7, 34.2),
    (84.0, 10.7, 35.8),
    (90.8, 10.7, 36.7),
    (98.0, 10.7, 37.3),
    (105.0, 10.7, 37.5),
    (112.0, 10.6, 37.3),
    (119.0, 10.7, 36.8),          # v22: behind the canopy the fairing widens steadily to the body's
    (126.1, 10.9, 36.2),          # width at that height, instead of narrowing to 9.0: it pinched in
    (132.0, 11.1, 35.7),          # and the body stepped out behind it (a waist and kink at X 126-134)
    (138.8, 11.2, 35.0),
    (142.0, 11.1, 34.4),
]
SPINE_N = 2.3
FRONT_SPLIT_X = 43.0         # nose/front joint, on the dome's vertical cut (DOME_CUT_X): the dome face
                             # was an overhang ledge part way up the nose section, now it is the bed face
FRONT_KEYS = [(5.0, 2.0), (-5.0, 2.0)]   # (y, z): beside the nose gear socket (x 38-42, y +-2.4)
NOSE_SPLIT_X = 86.0          # nose/middle section joint (the radome is part of the nose section)
NOSE_KEYS = [(0.0, -1.5), (0.0, 9.5)]   # (y, z) of the KEY_FR keys on that joint
PROBE = (24.0, 2.4, 1.6, 4.2, 3.0)    # length, base d, tip d, boss d, boss length: shorter and
                                      # thicker than scale (34 x 1.6) so it survives handling
PROBE_CUT_X = 0.9            # the probe is its own part from here forward (the nose tip is
                             # inside the boss), so a broken one is a quick reprint
PROBE_PLUG = (2.4, 4.0)      # d, length of its plug into the nose (3.0 x 5.0 printed)
PROBE_FIT = 0.1 * _P         # per side: a firm push fit
FUSE_SPLIT_X = 179.5         # middle/rear section joint: between the lettering and the roundel
FR_KEYS = [(-5.5, 5.0), (5.5, 5.0), (0.0, 19.0)]   # (y, z) on the joint face (below the fin cap at z 24)

# --- Intakes: D-section fairings each side, (x, y_outer, z_top, z_bottom)
INTAKE_STATIONS = [            # x, y_outer, z_top, z_bottom: the side pods (intake trunks)
    # boxy D-section pods (cross-sections checked against a reference Hawk model); the outer
    # side tapers in behind the wing LE. v19 top line (Revell side view's pod line, peaking at
    # z 19.5 near X 135, and the clean side render, ~18 there, with the lettering midway up the
    # pod side): a lower lip, a long climb to its highest at mid-length, then down to blend into
    # the fuselage at the roundel. Was 12.0 at the lip, level at 15 from X 110 to 134.
    (89.0, 20.0, 11.2, -3.6),      # rounded lip (head-on photo)
    (89.6, 20.5, 11.7, -4.1),
    (90.5, 20.9, 12.1, -4.5),
    (92.5, 21.4, 12.9, -5.2),
    (98.0, 21.7, 14.4, -6.0),
    (104.0, 21.8, 15.7, -6.4),     # widest here, then the sides turn in at once
    (110.0, 21.3, 16.8, -6.4),
    (118.0, 20.0, 17.8, -6.3),     # behind the wing LE the pod sits on the wing:
    (126.0, 18.4, 18.5, -6.0),     # keep its bottom above the wing underside (no slivers)
    (134.0, 16.8, 18.8, -5.4),
    (142.0, 15.2, 18.8, -4.4),
    # rear: a long fade into the fuselage side, the underside staying down on the wing to its
    # trailing edge (v6); the side stays just proud of the body until the roundel (v18). The top
    # runs in a straight line from its highest point to the top of the roundel's white ring (z 14.25
    # at X 186.8), where it disappears (v21; v20 ran to the blue's top, a touch steeper)
    (150.0, 13.8, 18.0, -4.6),
    (158.0, 13.0, 17.2, -4.4),
    (166.0, 12.5, 16.4, -3.8),
    (174.0, 12.2, 15.6, -2.8),
    (182.0, 12.0, 14.7, -1.6),
    (188.0, 11.8, 14.1, -0.9),
    (192.0, 11.6, 13.7, -0.5),
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
CANOPY_PLANE = ((36.0, 13.3), (60.0, 15.6), (126.0, 29.8))   # v19: the canopy's cut, and visible
                                                 # bottom edge, in two straight runs (clean side render
                                                 # and the Revell sill): nearly level (5.5 deg) from the
                                                 # windscreen tip to the red windscreen arch, then
                                                 # steeper (12 deg) back to the rear frame. It was one
                                                 # 9 deg plane. The canopy prints on its rear face, so
                                                 # its bottom needn't be flat; the tabs sit on the rear run
CANOPY_REAR = ((116.5, 41.0), (111.0, 22.0))     # rear frame of the glazing, leaning back at the top
                                                  # (Revell side view, v8; was X 122-125 from HobbyBoss,
                                                  # which put the canopy too far aft)
# Visible lower edge of the glazing (x, z): level under the front cockpit, curving up under the
# rear seat (HobbyBoss side view, shifted to our windscreen base). The part is cut on the flat
# CANOPY_PLANE just above it (it prints on it), and that cut is the visible bottom edge: the
# fuselage stays red below it. The sill line still places the frames and the nose dome.
CANOPY_SILL = [(36.0, 13.3), (48.0, 14.45), (60.0, 15.6), (75.0, 18.83), (90.0, 22.06),
               (105.0, 25.3), (126.0, 29.8)]   # v19: on the two-run cut (CANOPY_PLANE)
NOSE_DOME = (4.0, 9.0, 36.0, 62.0)   # height above the sill at the centre, half-width, x range:
                                     # the red nose top domes up into the windscreen (head-on photos)
DOME_CUT_X = 43.0            # the canopy's front is cut off on this vertical plane, where its glass
                             # first reaches outside the dome (measured: (outer ^ canopy_region)
                             # - nose_dome() starts at X 43.0; X 46.0 before the v10 canopy line,
                             # re-measure after any change to SPINE_STATIONS or NOSE_DOME). Ahead of it the canopy region is all
                             # dome and stays red on the nose section; behind it is all canopy, so
                             # the canopy needs no recess and its underside stays flat.
CANOPY_TABS = [(64.0, 78.0), (92.0, 106.0)]   # x ranges of the tabs moulded on the fuselage
                                              # (one per section), which the canopy drops onto
CANOPY_TAB = (5.0, 4.0)      # width (y), height above the sill plane; the aft end is chamfered
                             # (the sections print nose up, so it would overhang)

# --- Wing planform (Revell top view, both halves averaged):
# LE x = 102.8 + 55.8 eta, TE x = 169.3 + 12.3 eta, y = eta * SPAN/2
WING_LE = (102.8, 55.8)
WING_TE = (169.3, 12.3)
WING_TIP_ROUND = 3.0
TC_ROOT, TC_TIP = 0.109, 0.090
WING_CAMBER = 0.012
WING_SPLIT_TE_T = 1.2        # trailing edge thickness (from the split wing; kept: 1.5 mm printed)
WING_CHORD_DZ = 3.7          # chord plane above Z_FLOOR: the root's underside sits about 1.8 mm
                             # (2.25 printed) above the fuselage's lowest point, so some fuselage
                             # shows below the wing (photos)
WING_ROOT_CUT = 11.0         # |y| of the flat wing root (v23): each wing is one piece printed standing
                             # on this face (Halifax style). The fuselage covers the wing's top out
                             # to |y| 12 or more along the whole chord, so the joint only shows
                             # underneath; the stub inboard of it is moulded on the fuselage
WING_ROOT_GAP = 0.05         # glue gap at the root joint
WING_FENCE_SEAT = (0.22, 0.16)   # v28: each leading-edge fence has a tongue in a groove under the
                             # wing and (new) on top, these fractions of the local wing thickness
                             # deep (about 0.95 / 0.7 mm printed on the big fence; v27 had 0.5 mm
                             # under only and the test fence was still loose). No glue (user)
WING_FENCE_FIT = 0.04 * _P   # v28: per side, fence in its grooves: a snug push fit (was FIT, 0.15)
WING_FIN_LEDGE = 0.5         # v24: the underside fins are moulded on again, with their inboard face
                             # sloping at 45 deg (it faces down when the wing prints on end) out to
                             # this far from the tip, which prints as a short unsupported ledge
Z_FLOOR = -7.6               # wing underside at the centreline
DIHEDRAL = 2.0               # deg
WING_FLAT_FROM = 0.15
WING_LE_ANGLE = 50.0         # degrees: the underside rises no shallower than this to the leading edge
WING_TE_T = 0.6
WING_ROOT_Y = 6.0            # panel starts here (inside the fuselage, trimmed by it)
ROOT_TONGUE = {-1: (117.0, 131.0), 1: (132.5, 146.5)}   # wing key x ranges: port forward, starboard aft
                             # (starboard ends at 146.5: further aft its slot broke the thinning root skin)
ROOT_TONGUE_Z = (2.5, 5.9)   # above the floor (the wing sits 1.0 higher than the v4 flat-bottom wing)
# The wing root joint is a separate flat key in slots in the fuselage and the wing (where the
# tongue used to be): an integral tongue floated 1.5 mm above the bed in the wing's print pose,
# and the belly is too shallow there to lower it.
KEY_WING = (14.8, 14.0, 3.4)   # length (y, from ROOT_KEY_Y0 outboard), width (x), thickness (z)
ROOT_KEY_Y0 = 3.2              # inboard end: clear of the stand's socket on the centreline at X 134
WALL = 1.6

# --- Tailplane (10 deg anhedral)
TAIL_LE = (220.4, 38.9)      # LE x = a + b eta
TAIL_TE = (260.1, 12.7)
TAIL_SEMISPAN = 53.7
TAIL_ROOT_Y = 8.5            # root station at the fuselage side
TAIL_FLOOR = 15.2            # underside at the root
TAIL_ANHEDRAL = 10.0
TAIL_TC = 0.10
TAIL_PLUG_Y0 = 2.0           # each tailplane's own section runs on into the fuselage to here (no
                             # tongue): the fuselage has a socket the shape of the root section
TAIL_PLUG_FIT = 0.10 * _P    # v26: fixed tailplanes again (user: the snap boss was weak and turned
                             # too freely); the root plug is a firm push fit in its socket, glued

# --- Fin (separate, two halves): straight LE/TE lines from the side view
# v11: both lines fitted to the Revell side view (centre of the drawn line). The LE is at 45 deg
# and 1.4-3 mm further forward than v10's; the TE moved by under 0.5 mm.
FIN_LE = ((205.1, 32.6), (242.7, 70.2))
FIN_TE = ((250.5, 24.9), (260.5, 70.8))
FIN_TOP = 70.5
FIN_TIP_R = 22.0             # the LE rounds into the top on this radius (Revell side view, fin photo)
FIN_TIP_T_CHORD = 14.0       # sections are never thinner than a 14 mm chord's (each printed half
                             # keeps at least 2 lines at the tip)
FIN_ROOT_Z = 24.0            # fin root (the spine is cut flat here to take it)
FIN_TC = 0.10               # real ~8.5%; 10% leaves wall round the half keys
FIN_TONGUE = (210.0, 244.0, 4.0)   # x0, x1, depth of the root tongue into the spine
FIN_KEYS = [(189.0, 26.5), (201.0, 26.5)]   # keys in the thick spine cap: (x, z)

# --- Jet pipe
JET_PIPE = (7.0, 5.4, 7.2)   # (old blind pipe) depth, radius, z centre: the nozzle part replaces it
                             # (v19: centre 0.4 higher, Revell side view and the render from behind)
# Jet nozzle (separate part, plugs into the tail): radius of the visible ring, how far it stands
# out of the tail, wall, spigot radius and length into the fuselage, depth of the void.
NOZZLE_FIT = 0.04 * _P       # spigot to socket, per side (FIT let it fall out)
NOZZLE_RIB = 0.15 * _P       # 4 crush ribs along the spigot stand this proud: they grip
NOZZLE = dict(r=5.0, out=3.0, wall=1.0, spig_r=4.0, spig_len=8.0, void=10.0, rim=6.0)
                             # r 5.0 at the tail face keeps 0.7 mm of tail below the socket; behind
                             # the face the ring flares out at 45 degrees to rim (v18: the reference
                             # from behind shows a bigger nozzle, about 6.2)

# --- Smoke pod (centreline): (fraction of length, radius) profile
POD_X0, POD_LEN = 87.0, 95.0  # v22 (clean straight-down render): the nose at X 87, just behind the
                             # point where the underside white chevron meets
POD_NOSE = 0.116             # tangent-ogive nose this fraction of the length
POD_TUBE_END = 150.0         # full section to here, then a long taper (render: the sides narrow from
POD_TAIL_END = 195.0         # about X 150 to a point near X 195); the underside sweeps up from X 160
                             # in one S-curve, tangent into the belly at the end (v22b: it stopped at
                             # mid-height and then rounded up again, a bulb on the tail)
POD_W = 4.8                  # half-width (render: ~9.6 across); POD_R is the half-height (an oval:
                             # deeper than wide, as from behind)
POD_R = 5.6                  # photos: a fat tube, round blunt nose, long tail cone, hung close under the belly
def _ogive(n=14):
    L, R = POD_NOSE * 95.0, POD_R
    rho = (R * R + L * L) / (2 * R)
    out = []
    for t in np.linspace(0.0, 1.0, n):
        x = L * t
        r = math.sqrt(max(rho * rho - (L - x) ** 2, 0.0)) + R - rho
        out.append((x / 95.0, max(r, 0.6)))
    return out


POD_PROFILE = _ogive() + [((POD_TUBE_END - POD_X0) / POD_LEN, POD_R)]
POD_PYLON = (8.0, 2.6, 0.6)   # (inset unused since v7), half-width, gap pod top to belly
POD_TAIL_N = 19  # fore/aft inset, half-width, height
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
# Wheel snap fit: a boss on the leg, split by a spring slot, with a mushroom head. All sizes in
# PRINTED mm (the clearances come from the printer, not the model), so they are multiplied by _P
# where used. neck/head/bore are diameters.
GEAR_SNAP = dict(neck=5.0, head=6.6, head_len=1.5, cham=0.8, slot=1.2, slot_in=3.0,
                 bore=5.6, bore_cham=0.4, dish=0.7, end_gap=0.3, gap=0.3)
                             # v27 (test print: the v22 boss's prongs, 1.55 mm thick and 3.4 mm
                             # free, snapped off as the wheel went on): the boss now runs right
                             # through the wheel's bore and its head clips over the floor of the
                             # outboard hub dish, standing out like a hub cap. Prongs 1.9 mm thick
                             # and about 8 mm free; running clearance 0.3 a side (bore 5.6 on a
                             # 5.0 neck), retention 0.5 a side (head 6.6), slot 1.2 (the head
                             # closes to 5.4, under the bore), 0.3 end gap and leg-wheel gap
LEG_T_IN = 1.0               # main legs are this much thicker on their inner (bed) face, so the
                             # spring slot can run 4 mm in

# --- Display stand
STAND_X = 134.0              # between the port and starboard wing tongues
STAND_KEY = 5.0
STAND_KEY_DEPTH = 8.0         # (old: through the pod into the belly)
STAND_SOCKET_TOP = 2.0        # the stand's socket is blind, in the smoke pod only: it stops this far
                              # above the pod's axis (7 mm into the pod; no hole through to the belly)
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


def egg_wire(x, hw, z_top, z_bot, n_lo, z_w=None, n_up=None, pts=None):
    """Section widest at z_w: upper half a superellipse of exponent n_up up to z_top,
    lower half exponent n_lo down to z_bot (z_w=None: the symmetric superellipse)."""
    if z_w is None:
        return superellipse_wire(x, hw, z_top, z_bot, n_lo)
    pts = pts or (160 if max(n_lo, n_up) > 5 else 64)    # square corners need more points
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


BLEND_R = ((80.0, 92.0, 118.0, 145.0, 165.0, 185.0), (6.0, 1.2, 1.5, 2.5, 7.0, 9.0))   # fillet radius vs x: soft at the canopy,
                             # tight at the inlet (pods nearly separate), soft again where they fade
BLEND_X = (34.0, 200.0)      # x range of the blend (from ahead of the windscreen to behind the pods)
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
        if x < INTAKE_MOUTH[0]:
            # ahead of the intakes: below the canopy's cut plane the section is filled to its
            # hull, so the sides run straight down from the sill to the curve of the underside
            # (no waist). Above the plane it is left alone: filling there put fuselage red up the
            # canopy's sides and bent its straight lower edge
            zp = canopy_plane_z(x) if x >= CANOPY_X[0] else 100.0
            low = mf.CrossSection.square([80.0, 80.0]).translate([-zp, -40.0])
            sec = (sec - low) + (sec ^ low).hull()
        elif x >= HULL_X0:
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


def cambered_section(tc, chord, te_t=WING_SPLIT_TE_T, n=48, camber=WING_CAMBER):
    """Cambered NACA 4-digit section, chord line on z=0, LE at x=0: [(x, z)] from the upper TE
    round the LE to the lower TE (both skins curved: the wing prints as two halves split on
    the chord plane, each lying on its split face)."""
    m, p = camber, 0.4
    up, lo = [], []
    for i in range(n + 1):
        x = (1 - math.cos(math.pi * i / n)) / 2
        yt = 5 * tc * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x**2
                       + 0.2843 * x**3 - 0.1036 * x**4) + x * (te_t / 2) / chord
        yc = m / p**2 * (2 * p * x - x * x) if x < p else m / (1 - p)**2 * ((1 - 2 * p) + 2 * p * x - x * x)
        dyc = 2 * m / p**2 * (p - x) if x < p else 2 * m / (1 - p)**2 * (p - x)
        th = math.atan(dyc)
        up.append(((x - yt * math.sin(th)) * chord, (yc + yt * math.cos(th)) * chord))
        lo.append(((x + yt * math.sin(th)) * chord, (yc - yt * math.cos(th)) * chord))
    return list(reversed(up)) + lo[1:]


def cambered_panel(stations, zc):
    wires = []
    for y, x, c, tc in stations:
        pts = [V(x + px, y, zc + pz) for px, pz in cambered_section(tc, c)]
        wires.append(cq.Wire.assembleEdges([cq.Edge.makeSpline(pts), cq.Edge.makeLine(pts[-1], pts[0])]))
    return to_m(loft(wires, ruled=True))


WING_CHORD_Z = Z_FLOOR + WING_CHORD_DZ


@cached
def wing_flat():
    """Flat (no dihedral) starboard panel, chord plane at WING_CHORD_Z."""
    st = []
    tip = SPAN / 2
    for y in (WING_ROOT_Y, 40.0, 80.0, tip - WING_TIP_ROUND, tip - 1.2, tip):
        le, c, tc = wing_plan(y)
        if y > tip - WING_TIP_ROUND + 0.1:          # rounded LE corner at the tip
            t = (y - (tip - WING_TIP_ROUND)) / WING_TIP_ROUND
            cut = WING_TIP_ROUND * (1 - math.sqrt(max(0.0, 1 - t * t))) * 1.8
            le, c = le + cut, c - cut
        st.append((y, le, c, tc))
    return cambered_panel(st, WING_CHORD_Z)


DIHEDRAL_PT = (0.0, 0.0, Z_FLOOR)


def wing_assembled(side):
    w = rot_about(wing_flat(), DIHEDRAL_PT, "x", DIHEDRAL)
    return w if side > 0 else w.mirror([0, 1, 0])


WING_KEY_FIT = (0.08 * _P, 0.04 * _P)   # v26: per side, (in the wing, in the fuselage). Both
                             # were KEY_FIT (0.15) and the test print found the key loose in both,
                             # looser in the fuselage (printed on end)


@cached
def wing_key_z(side):
    """z centre of the wing key: midway between the highest underside and the lowest top skin
    over the key's footprint in the wing (v26: at Z_FLOOR + ROOT_TONGUE_Z its slot came within
    0.3 mm of the underside at the outer end and broke through on the test print)."""
    tx0, tx1 = ROOT_TONGUE[side]
    L, w, t = KEY_WING
    ys = [side * y for y in np.linspace(WING_ROOT_CUT + 0.5, ROOT_KEY_Y0 + L, 4)]
    xs = np.linspace(tx0 - 0.3, tx1 + 0.3, 5)
    lo = max(wing_underside_z(y, x) for x in xs for y in ys)
    hi = min(wing_top_z(y, x) for x in xs for y in ys)
    return (lo + hi) / 2


def wing_key_slot(side, g=None):
    """Slot for the wing root key, cut through the fuselage and the wing alike (g: fit per side)."""
    tx0, tx1 = ROOT_TONGUE[side]
    L, w, t = KEY_WING
    xc, zc = (tx0 + tx1) / 2, wing_key_z(side)
    g = KEY_FIT if g is None else g
    e = KEY_END_GAP
    b = box(xc - w / 2 - g, xc + w / 2 + g, ROOT_KEY_Y0 - e, ROOT_KEY_Y0 + L + e, zc - t / 2 - g, zc + t / 2 + g)
    KEY_COUNTS["key_wing"] = (KEY_WING, 2)
    return b if side > 0 else b.mirror([0, 1, 0])


WING_GLOVE_Y = 24.0           # the glove runs out to here (past the intake pods, which sit on the wing)


@cached
def wing_glove_flat():
    """Filler ahead of the wing root's leading edge, inside the pods: a wedge whose two faces
    touch the top and bottom skins at 45 degrees. The pod section above the wing prints on
    end (forward up), and over the round leading edge its socket was a flat ceiling. Now it
    is a pointed 45 degree arch: the wing part takes the filler, so nothing shows but a
    pointed seam ahead of the leading edge."""
    pts = []
    for y in (WING_ROOT_Y, WING_GLOVE_Y):
        le, c, tc = wing_plan(y)
        sec = np.array(cambered_section(tc, c))
        k = int(np.argmin(sec[:, 0]))
        up, lo = sec[:k + 1], sec[k:]
        x0u = float(np.min(up[:, 0] - up[:, 1]))          # top line z = x - x0u
        x0l = float(np.min(lo[:, 0] + lo[:, 1]))          # bottom line z = x0l - x
        tu = up[int(np.argmin(up[:, 0] - up[:, 1]))]
        tl = lo[int(np.argmin(lo[:, 0] + lo[:, 1]))]
        apex = ((x0u + x0l) / 2, (x0l - x0u) / 2)
        for px, pz in (apex, tuple(tu), tuple(tl), (max(tu[0], tl[0]), 0.0)):
            pts.append((le + px, y, WING_CHORD_Z + pz))
    return M.hull_points(pts)


def wing_glove(side):
    g = rot_about(wing_glove_flat(), DIHEDRAL_PT, "x", DIHEDRAL)
    return g if side > 0 else g.mirror([0, 1, 0])


WING_FINS = [(0.2156, 0.61, 0.88, 2.4), (0.5529, 0.50, 0.88, 3.2), (0.7046, 0.38, 0.86, 1.6),
             (0.3306, 0.13, 0.30, 3.0)]
             # v17, from the clean reference renders (straight up and from behind): three slim
             # fairings under the rear of the chord at |y| 25, 65 and 83, ending short of the
             # trailing edge, and a deeper fin near the leading edge at |y| 39 (white, colour.py
             # WHITE_WING_FINS). eta, chord fraction from, to, depth below the skin
WING_LE_FENCES = [(0.6645, 2.0, 0.35, 0.175, 2.3, 1.7), (0.8264, 1.2, 0.18, 0.09, 1.4, 1.0)]
             # v17: fences on the leading edge (|y| 78 and 97), wrapping round it above and
             # below and standing proud of it: eta, mm ahead of the LE, chord fraction they run
             # back to on top and underneath, height above and below the skin (v24: taller above
             # than below, as in the view along the leading edge; v25: twice as long on top as
             # underneath, user; the top run matches the top-view render, about 0.37 chord)
WING_FIN_T = 0.9


WING_FENCE_T = 1.3            # v26: fence thickness (1.6 mm printed; at WING_FIN_T they were thin
                             # and floppy on the test print)
WING_FENCE_CURVE = 0.35      # v26: each arm's outer edge curves in towards its rear end, to this
                             # fraction of its height lower than at the front (user: slightly curved)


def _fin_slab(prof, y, grow=0.0, t0=WING_FIN_T):
    c = K.cs([prof])
    if grow:
        c = c.offset(grow, mf.JoinType.Round)
    t = t0 + 2 * grow
    return c.extrude(t).translate([0, 0, -t / 2]).rotate([90, 0, 0]).translate([0, y, WING_CHORD_Z])


@cached
def wing_fence_plates(grow=0.0):
    """Leading-edge fences (flat starboard frame), one slab each."""
    from shapely.geometry import Polygon, box as sbox
    from shapely.ops import unary_union
    out = []
    for eta, ahead, f_top, f_bot, up, down in WING_LE_FENCES:
        y = eta * SPAN / 2
        le, c, tc = wing_plan(y)
        sec = Polygon(np.array(cambered_section(tc, c)) + [le, 0.0]).buffer(0)
        r = 0.6                                              # rounding of the outline
        steps = np.linspace(-(down - r), up - r, 14)
        swept = unary_union([Polygon(np.array(sec.exterior.coords) + [0.0, dz]) for dz in steps])
        # the top runs back to f_top, the underside to f_bot (the step between them, on the
        # chord plane, is inside the wing); each arm's outer edge curves in towards its end
        sa = np.array(cambered_section(tc, c))
        k = int(np.argmin(sa[:, 0]))
        upper, lower = sa[:k + 1][::-1], sa[k:]           # both from the LE aft
        def edge(f, h, skin, sgn):
            xs = np.linspace(-ahead - 1.0, f * c, 40)
            u = np.clip(xs / (f * c), 0.0, 1.0)
            z = np.interp(np.maximum(xs, 0.0), skin[:, 0], skin[:, 1]) + sgn * h * (1 - WING_FENCE_CURVE * u * u)
            return np.c_[le + xs, z]
        grown = max(ahead, r)                              # the outline is grown by this too
        top = edge(f_top, up + grown, upper, 1.0)
        bot = edge(f_bot, down + grown, lower, -1.0)
        env = Polygon(np.r_[top, [(le + f_top * c, 0.0), (le - ahead - 1.0, 0.0)]]).buffer(0) | \
            Polygon(np.r_[bot, [(le + f_bot * c, 0.0), (le - ahead - 1.0, 0.0)]]).buffer(0)
        prof = swept.buffer(max(ahead, r)) & env
        prof = prof.buffer(-0.3).buffer(0.3)              # round the arms' rear corners
        if prof.geom_type != "Polygon":
            prof = max(prof.geoms, key=lambda g: g.area)
        prof = np.array(prof.exterior.coords)[:-1]
        if K.cs([prof]).area() < 0:
            prof = prof[::-1]
        out.append(_fin_slab(prof, y, grow, WING_FENCE_T))
    return out


@cached
def _fin_profiles():
    """Underside fins' side outlines (x, z above the chord plane) and their y (flat frame)."""
    out = []
    for eta, f0, f1, h in WING_FINS:
        y = eta * SPAN / 2
        le, c, tc = wing_plan(y)
        sec = np.array(cambered_section(tc, c))
        k = int(np.argmin(sec[:, 0]))
        lo = sec[k:]
        xs = np.linspace(f0 * c, min(f1, 0.995) * c, 12)
        u = (xs - xs[0]) / (xs[-1] - xs[0])
        d = h * np.clip(np.sin(np.pi * np.clip(u * 1.3, 0, 1)) ** 0.6, 0.15, 1.0)   # deepest a third along
        bottom = [(le + x, float(np.interp(x, lo[:, 0], lo[:, 1])) - dd) for x, dd in zip(xs, d)]
        prof = np.array(bottom + [(le + xs[-1], 0.0), (le + xs[0], 0.0)])
        if K.cs([prof]).area() < 0:
            prof = prof[::-1]
        out.append((prof, y))
    return out


@cached
def wing_fin_plates(grow=0.0):
    """Underside fins (flat starboard frame), one slab each."""
    return [_fin_slab(prof, y, grow) for prof, y in _fin_profiles()]


@cached
def wing_fin_keels():
    """v24: a 45-degree fillet on each fin's inboard face (flat starboard frame), so the fin can
    be moulded on a wing that prints standing on its root: at distance e inboard of the fin the
    keel reaches to within e + WING_FIN_LEDGE of the fin's tip. Built as 0.1 mm steps in y,
    finer than a print layer."""
    st = 0.1
    out = []
    for prof, y in _fin_profiles():
        c0 = K.cs([prof])
        e = st
        while True:
            reg = c0 ^ c0.translate([0.0, e + WING_FIN_LEDGE])
            if reg.area() < 1e-3:
                break
            out.append(reg.extrude(st + 0.01).rotate([90, 0, 0])
                       .translate([0, y - WING_FIN_T / 2 - e + st, WING_CHORD_Z]))
            e += st
    return union(out)


@cached
def _fence_tongue_boxes():
    """Per fence (flat frame): (y, [(x_t, z_t, sgn)]) for its two tongues. Underneath (sgn -1)
    the tongue fills the wing below the lower skin's lowest point within the fence's chord,
    raised by the seat, and ahead of that point; on top (sgn +1) above the upper skin's highest
    point lowered by the seat. Both grooves open to the front, so the collar slides back onto
    the leading edge with its tongues running in them, and then can't rock or lift off."""
    out = []
    for eta, ahead, f_top, f_bot, up, down in WING_LE_FENCES:
        y = eta * SPAN / 2
        le, c, tc = wing_plan(y)
        sec = np.array(cambered_section(tc, c))
        k = int(np.argmin(sec[:, 0]))
        lo, hi = sec[k:], sec[:k + 1][::-1]
        t = float(np.max(np.interp(lo[:, 0], hi[:, 0], hi[:, 1]) - lo[:, 1]))   # max thickness
        ml, mh = lo[:, 0] <= f_bot * c, hi[:, 0] <= f_top * c
        i, j = int(np.argmin(lo[ml, 1])), int(np.argmax(hi[mh, 1]))
        sb, st = WING_FENCE_SEAT
        out.append((y, [(le + lo[ml][i, 0], WING_CHORD_Z + lo[ml][i, 1] + sb * t, -1),
                        (le + hi[mh][j, 0], WING_CHORD_Z + hi[mh][j, 1] - st * t, 1)]))
    return out


def _tongue_box(y, xt, zt, sgn, g=0.0):
    z0, z1 = (-60, zt + g) if sgn < 0 else (zt - g, 60)
    return box(-50, xt + g, y - 5, y + 5, z0, z1)


def wing_fence_parts(side):
    """Separate leading-edge fences, assembled frame: collars that wrap the leading edge and slide
    back onto it, with a tongue in a groove under the wing and on top (they print flat; on a wing
    printed on end they would be shelves in mid-air). A snug fit holds them without glue."""
    w = wing_flat()
    g = WING_FENCE_FIT                               # clear of the skin outside the grooves too
    wg = union([w] + [w.translate([a, 0, c]) for a, c in ((g, 0), (-g, 0), (0, g), (0, -g))])
    out = []
    for p, (y, tongues) in zip(wing_fence_plates(), _fence_tongue_boxes()):
        keep = union([_tongue_box(y, *t) for t in tongues])
        out.append(wing_flat_to_assembled(K.largest_piece(p - (wg - (keep ^ w)))[0], side))
    return out


@cached
def wing_fence_grooves(side):
    w = wing_flat()
    g = [p ^ w ^ union([_tongue_box(y, *t, g=WING_FENCE_FIT) for t in tongues])
         for p, (y, tongues) in zip(wing_fence_plates(WING_FENCE_FIT), _fence_tongue_boxes())]
    return wing_flat_to_assembled(union(g), side)


WING_TE_FILLET = (4.0, 8.8)  # v24: radius, and |y| of the fuselage side just behind the trailing edge
                             # at its height (the side pod's lower flank): in plan the trailing edge
                             # curves aft into the fuselage side instead of meeting it in a corner
                             # (user's photo). Inboard of WING_ROOT_CUT, so it is moulded on the
                             # middle fuselage section


def wing_te_fillet(side):
    """Plan-view fillet between the wing's trailing edge and the fuselage side, as thick as the
    trailing edge at the root (on the fuselage)."""
    r, ys = WING_TE_FILLET
    le, c, _ = wing_plan(ys + r / 2)
    te = le + c
    zb, zt = wing_underside_z(ys + r / 2, te - 0.4), wing_top_z(ys + r / 2, te - 0.4)
    y1 = min(ys + r, WING_ROOT_CUT)
    sq = mf.CrossSection.square([r + 1.0, y1 - (ys - 3.0)]).translate([te - 1.0, ys - 3.0])
    plan = sq - mf.CrossSection.circle(r, 64).translate([te + r, ys + r])
    f = plan.extrude(zt - zb).translate([0, 0, zb])
    return f if side > 0 else f.mirror([0, 1, 0])


def wing_root_box(side, inboard, gap=0.0):
    y0, y1 = (-1.0, WING_ROOT_CUT) if inboard else (WING_ROOT_CUT + gap, 200.0)
    b = box(0, 400, y0, y1, -60, 60)
    return b if side > 0 else b.mirror([0, 1, 0])


@cached
def wing_outer(side):
    """The whole wing's outside shape, root stub and underside fins included (no sockets, slots
    or fences): what the paint is measured from."""
    fins = wing_flat_to_assembled(union(wing_fin_plates()) + wing_fin_keels(), side)
    return (wing_assembled(side) + fins + (wing_glove(side) ^ outer())) - body()


@cached
def wing(side):
    return wing_outer(side) - wing_key_slot(side)


def wing_cuts(side):
    """Everything cut into the wing part: root key slot, gear socket, wheel bay, fence grooves."""
    # the wheel-well recess stops at the fins (one runs across it; cut through, it floated)
    fins = wing_flat_to_assembled(union(wing_fin_plates()) + wing_fin_keels(), side)
    return (wing_key_slot(side, WING_KEY_FIT[0]) + main_socket(side) + (gear_bay(side) - fins)
            + wing_fence_grooves(side))


def wing_part(side):
    """The wing as printed: one piece outboard of the root cut (v23; it was two halves split on
    the chord plane, pinned)."""
    return (wing_outer(side) ^ wing_root_box(side, False, WING_ROOT_GAP)) - wing_cuts(side)


def wing_flat_to_assembled(m, side):
    m = rot_about(m, DIHEDRAL_PT, "x", DIHEDRAL)
    return m if side > 0 else m.mirror([0, 1, 0])


def wing_half_region(side, top):
    z0, z1 = (WING_CHORD_Z, 60.0) if top else (-60.0, WING_CHORD_Z)
    return wing_flat_to_assembled(box(0, 400, -5, 200, z0, z1), side)


GEAR_BAY = (152.0, 27.0, 16.0, 5.0, 0.5)   # main wheel bay in the underside (the wheels retract
                             # inwards): wheel well centre x, |y|, diameter, leg channel width, depth


def gear_bay(side):
    """Shallow recess for the main wheel well and the leg's channel out to the leg socket."""
    xc, yc, d, cw, depth = GEAR_BAY
    gx, gy = MAIN_GEAR
    well = mf.CrossSection.circle(d / 2, 48).translate([xc, yc])
    ang = math.atan2(gy - yc, gx - xc)
    L = math.hypot(gx - xc, gy - yc) + cw / 2
    ch = mf.CrossSection.square([L, cw]).translate([0, -cw / 2]).rotate(math.degrees(ang)).translate([xc, yc])
    plan = well + ch
    if side < 0:
        plan = plan.mirror([0.0, 1.0])
    w = wing_assembled(side)
    under = w - w.translate([0, 0, depth])            # within depth above the underside
    return under ^ K.prism_z(plan)


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


def _tail_to_assembled(m, side):
    m = rot_about(m, TAIL_PT, "x", -TAIL_ANHEDRAL)
    return m if side > 0 else m.mirror([0, 1, 0])


@cached
def tailplane(side):
    """Fixed tailplane (v26, as v4): the whole panel from TAIL_PLUG_Y0 outboard. The part inside
    the fuselage is the root plug, the tailplane's own aerofoil, so nothing shows on the surface,
    the underside stays flat for printing and the whole root chord grips."""
    t = tail_flat() ^ box(0, 400, TAIL_PLUG_Y0, 100, -50, 100)
    t = _tail_to_assembled(t, 1)
    return t if side > 0 else t.mirror([0, 1, 0])


def tail_socket(side):
    """The tailplane grown by TAIL_PLUG_FIT all round its section and at its inboard end (a
    Minkowski sum approximated by 8 offsets in the x-z plane), cut from the fuselage."""
    t = tailplane(side)
    g = TAIL_PLUG_FIT
    d = g / math.sqrt(2)
    offs = [(g, 0), (-g, 0), (0, g), (0, -g), (d, d), (d, -d), (-d, d), (-d, -d)]
    return union([t] + [t.translate([a, 0, c]) for a, c in offs] + [t.translate([0, -side * g, 0])])


# ============================================================
# FIN (two halves)
# ============================================================
FIN_FILLET_Z = 35.5          # below this the leading edge curves into the spine (Revell side view,
FIN_SPINE_Z = 28.9           # ...meeting the spine top tangentially at this height; v11 refit to the new LE)
FIN_TE_KINK = ((251.0, 27.0), (263.5, 20.0))   # below the kink the trailing edge sweeps back at a
                             # shallower angle onto the top of the tail cone (Revell side view)


def _fin_le_line(z):
    (lx0, lz0), (lx1, lz1) = FIN_LE
    return lx0 + (z - lz0) * (lx1 - lx0) / (lz1 - lz0)


def fin_tip_arc():
    """The convex arc (radius FIN_TIP_R) tangent to the LE line and to the flat top:
    returns (centre x, centre z, z where it leaves the LE line)."""
    (lx0, lz0), (lx1, lz1) = FIN_LE
    th = math.atan2(lz1 - lz0, lx1 - lx0)                      # LE angle above horizontal
    t = FIN_TIP_R / math.tan((math.pi - th) / 2)               # tangent length from the corner
    return _fin_le_line(FIN_TOP) + t, FIN_TOP - FIN_TIP_R, FIN_TOP - t * math.sin(th)


def fin_le(z):
    """Straight leading edge; below FIN_FILLET_Z a circular arc tangent to it and to the spine
    (a concave dorsal fillet, not an angled kink); at the top a convex arc into the flat tip."""
    cx, cz, z_t = fin_tip_arc()
    if z > z_t:
        return cx - math.sqrt(max(FIN_TIP_R ** 2 - (min(z, FIN_TOP) - cz) ** 2, 0.0))
    if z >= FIN_FILLET_Z:
        return _fin_le_line(z)
    (lx0, lz0), (lx1, lz1) = FIN_LE
    th = math.atan2(lz1 - lz0, lx1 - lx0)                      # LE angle above horizontal
    xi = _fin_le_line(FIN_SPINE_Z)                             # where the LE line meets the spine
    t = (FIN_FILLET_Z - FIN_SPINE_Z) / math.sin(th)            # tangent length
    R = t * math.tan((math.pi - th) / 2)
    cx, cz = xi - t, FIN_SPINE_Z + R
    if z >= FIN_SPINE_Z:
        return cx + math.sqrt(max(R * R - (cz - z) ** 2, 0.0))
    return cx - 3.0 * (FIN_SPINE_Z - z)                        # inside the spine: runs on forward


def fin_te(z):
    (kx, kz), (ex, ez) = FIN_TE_KINK
    if z < kz:
        return kx + (kz - z) * (ex - kx) / (kz - ez)
    (tx0, tz0), (tx1, tz1) = FIN_TE
    return tx0 + (z - tz0) * (tx1 - tx0) / (tz1 - tz0)


def fin_section(z):
    """Symmetric NACA 00xx section at height z. The fillet's long chords keep the thickness of
    the fin at FIN_FILLET_Z, so the fillet is a thin swept extension, not a fat wedge."""
    le, te = fin_le(z), fin_te(z)
    c = te - le
    c_t = min(c, fin_te(FIN_FILLET_Z) - fin_le(FIN_FILLET_Z))
    c_t = max(c_t, FIN_TIP_T_CHORD)      # the rounded tip keeps the thickness of v10's square tip
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
    z_t = fin_tip_arc()[2]
    zs = (list(np.arange(FIN_TE_KINK[1][1] - 0.5, FIN_FILLET_Z, 0.75)) + [FIN_FILLET_Z]
          + list(np.linspace(z_t, FIN_TOP, 13)))          # dense through the rounded tip
    f = to_m(loft([fin_section(z) for z in zs], ruled=True))     # dense ruled loft: smooth fillet
    whole = (f + fin_cap()) ^ box(FIN_X0, 300, -30, 30, FIN_ROOT_Z, 100)
    return whole + fin_tongue()


@cached
def fin_tail_fairing():
    """The swept lower trailing edge below the fin root plane, where the tail top drops under
    it: part of the rear fuselage, so the fin's trailing edge runs down onto the tail cone."""
    zs = list(np.arange(FIN_TE_KINK[1][1] - 0.5, FIN_ROOT_Z + 0.6, 0.75))
    f = to_m(loft([fin_section(z) for z in zs], ruled=True))
    return f ^ box(240.0, 300.0, -30, 30, -50, FIN_ROOT_Z)


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
    """Height of the canopy's cut (two straight runs, extended at the ends)."""
    (xa, za), (xk, zk), (xb, zb) = CANOPY_PLANE
    if x <= xk:
        return za + (x - xa) * (zk - za) / (xk - xa)
    return zk + (x - xk) * (zb - zk) / (xb - xk)


def canopy_angle(run=1):
    """Angle (deg) of the cut's front (run 0) or rear (run 1) run."""
    (xa, za), (xb, zb) = CANOPY_PLANE[run], CANOPY_PLANE[run + 1]
    return math.degrees(math.atan2(zb - za, xb - xa))


def canopy_zone(grow=0.0):
    """Above the sill plane, behind the windscreen base and ahead of the slanted rear edge."""
    x0, x1 = CANOPY_X
    blk = None
    for run in (0, 1):                     # above both runs (the cut is convex: its slope steepens)
        xa, za = CANOPY_PLANE[run]
        b = rot_about(box(x0 - 60, x1 + 60, -30, 30, za - grow, za + 80), (xa, 0, za), "y", -canopy_angle(run))
        blk = b if blk is None else blk ^ b
    (ra, rza), (rb, rzb) = CANOPY_REAR
    ang = math.degrees(math.atan2(rb - ra, rza - rzb))           # lean of the rear edge from vertical
    rear = rot_about(box(ra - 200, ra + grow, -30, 30, rzb - 30, rza + 30), (ra, 0, rza), "y", -ang)
    return blk ^ box(x0 - grow, x1 + grow, -30, 30, -10, 60) ^ rear


def nose_dome(grow=0.0):
    """The red nose top that domes up into the windscreen: under an elliptical arch over the
    canopy sill."""
    h, w, x0, x1 = NOSE_DOME
    ws = []
    for x in np.linspace(x0 - grow, x1 + grow, int(round(x1 - x0)) + 1):   # ends exactly at x0, x1
        zs = canopy_sill_z(x)
        ws.append(egg_wire(x, w + grow, zs + h + grow, zs - 8.0, 6.0, zs, 2.0))
    return to_m(loft(ws, ruled=True))


CANOPY_TAB_FIT_Y = 0.03 * _P   # pockets snug across the tabs (FIT all round let the canopy lift)


def canopy_tabs(grow=0.0, grow_y=None):
    """Tabs standing on the sill plane, made level and tipped onto the plane. grow > 0: the
    canopy's pockets for them (clearance all round and 0.3 mm over the top)."""
    xa, za = CANOPY_PLANE[1]
    w, h = CANOPY_TAB
    g = grow
    gy = g if grow_y is None else grow_y
    tabs = []
    for x0, x1 in CANOPY_TABS:
        prof = np.array([(x0 - g, za - 1.0), (x1 + g, za - 1.0), (x1 + g, za + 0.2),
                         (x1 - 0.9 * h + g, za + h + (0.3 if g else 0.0)), (x0 - g, za + h + (0.3 if g else 0.0))])
        tabs.append(K.cs([prof]).extrude(w + 2 * gy).translate([0, 0, -(w / 2 + gy)]).rotate([90, 0, 0]))
    return rot_about(union(tabs), (xa, 0, za), "y", -canopy_angle())


@cached
def canopy():
    """Solid and opaque, flat underneath, with pockets for the fuselage's tabs; its front is a
    vertical face at DOME_CUT_X, against the red nose dome."""
    c = outer() ^ canopy_region(-FIT) ^ box(DOME_CUT_X + FIT, 400, -60, 60, -60, 100)
    c = c - canopy_tabs(FIT, CANOPY_TAB_FIT_Y)
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
    front = POD_PROFILE
    pod = _revolve_x([(POD_X0 + f * POD_LEN, rr) for f, rr in front]).scale([1, POD_W / POD_R, 1]).translate([0, 0, zc])
    # tail: from the end of the tube the sides taper in a long curve to a point at POD_TAIL_END;
    # the underside sweeps up in one S-curve from X 160 into the belly; the top stays level to
    # X 175, then eases into the belly
    top0, bot0 = zc + POD_R, zc - POD_R
    x0, x1 = POD_TUBE_END, POD_TAIL_END
    zbel = fuse_at(x1)[3]
    tail = []
    for t in np.linspace(0.0, 1.0, POD_TAIL_N):
        x = x0 + t * (x1 - x0)
        u = min(max((x - 160.0) / (x1 - 160.0), 0.0), 1.0)
        bot = bot0 + (zbel + 0.4 - bot0) * u * u * (3 - 2 * u)
        v = min(max((x - 175.0) / (x1 - 175.0), 0.0), 1.0)
        top = top0 + (zbel + 1.2 - top0) * v * v * (3 - 2 * v)
        hw_ = max(0.5, POD_W * (1 - t * t))
        tail.append((x, hw_, top, bot))
    pod = pod + to_m(loft([superellipse_wire(x, h, tp, bt, 2.0) for x, h, tp, bt in tail], ruled=True))
    # pylon: the whole length, so there is no gap to the belly anywhere; it narrows with the pod
    _, hw, _ = POD_PYLON
    pw = [(POD_X0 + f * POD_LEN, min(hw, 0.55 * rr), zc) for f, rr in POD_PROFILE if f >= 0.03]
    pw += [(x, min(hw, 0.55 * h), (tp + bt) / 2) for x, h, tp, bt in tail[1:]]
    pylon = to_m(loft([superellipse_wire(x, h, zb + 4.0, z0, 6.0) for x, h, z0 in pw], ruled=True))
    p = (pod + pylon) - outer()           # the finished outer shape: body() sits up to 0.6 above
                                          # the belly ahead of the wing (v22: the pylon cut into it)
    k = STAND_KEY / 2 + FIT
    p = (p + pod_pegs()) - box(STAND_X - k, STAND_X + k, -k, k, zc - 20, zc + STAND_SOCKET_TOP)
    pts = [(POD_X0 + f * POD_LEN, 0.0, zc) for f in POD_HALF_KEYS]
    slots = to_m(K.key_slots(pts, "y", 0.0, KEY_POD_HALF, "x", KEY_FIT, KEY_END_GAP))
    KEY_COUNTS["key_pod"] = (KEY_POD_HALF, len(pts))
    return (p ^ box(0, 400, 0, 50, -100, 100)) - slots, (p ^ box(0, 400, -50, 0, -100, 100)) - slots


def pod_sockets():
    return pod_key_slots()


AERIALS = [  # x, top|bottom, height, chord, sweep (v22: placed from the clean side render; black)
    (143.0, "top", 6.0, 6.5, 3.0),     # UHF blade behind the canopy
    (16.0, "top", 3.0, 3.5, 1.5),      # small blade on top of the nose
    (48.0, "bottom", 2.5, 3.5, 1.5),   # under the nose, just behind the nose leg
    (75.0, "bottom", 4.5, 5.0, 2.0),   # under the nose, below the cockpit
    (243.0, "bottom", 2.5, 3.5, 1.5),  # small blade under the tail, behind the ventral bulge
]
AERIAL_T = 1.0
AERIAL_FIT = 0.05 * _P        # along the chord only; the thickness is line-for-line (holes print small)
STRAKES = (218.0, 236.0, 6.5, 3.5, 8.6, 0.8, 30.0)   # ventral strakes (Revell side view): x front,
                             # x rear, depth at the front and rear (seen from the side), |y| on the
                             # fuselage's lower curve, thickness, cant from vertical


VENTRAL_BULGE = (234.0, 15.0, 2.4, 1.4)   # small radome between the strakes: x centre, length,
                                          # half-width, depth below the belly


def ventral_bulge():
    xc, L, hw, d = VENTRAL_BULGE
    zb = fuse_at(xc)[3]
    return M.sphere(1.0, 48).scale([L / 2, hw, d + 0.6]).translate([xc, 0, zb + 0.6])


def strakes():
    """Two blades on the rear fuselage's lower curve, canted out: deepest at the front, with a
    steep rounded front edge and an upright rear edge (Revell side view)."""
    x0, x1, d0, d1, yy, t, cant = STRAKES
    o = outer()
    out = mf.Manifold()
    k = 1.0 / math.cos(math.radians(cant))                  # blade length for the side-view depth
    for side in (1, -1):
        def zs(x):                                          # surface height at (x, |y|=yy)
            return (o ^ box(x - 0.3, x + 0.3, side * yy - 0.3, side * yy + 0.3, -50, 50)).bounding_box()[2]
        za, zb_ = zs(x0 + 1.0), zs(x1 - 1.0)
        prof = np.array([(x1, zb_ + 1.5), (x0 + 1.0, za + 1.5), (x0, za - 0.5), (x0 + 0.6, za - 0.5 - d0 * k * 0.55),
                         (x0 + 2.2, za - d0 * k), (x1, zb_ - d1 * k)])
        blade = K.cs([prof]).extrude(t).translate([0, 0, -t / 2]).rotate([90, 0, 0])
        blade = rot_about(blade.translate([0, side * yy, 0]), (0, side * yy, (za + zb_) / 2), "x", side * cant)
        out = out + blade
    return out


def aerial_base(a):
    x, where, *_ = a
    if where == "top":
        return spine_top(x + 3.0) if x + 3.0 >= SPINE_STATIONS[0][0] else fuse_at(x + 3.0)[2]
    return fuse_at(x + 3.0)[3]


def aerial(a, slot=False):
    x, where, h, c, sweep = a
    zs = aerial_base(a)
    sg = 1 if where == "top" else -1
    if slot:
        g = AERIAL_FIT                 # press fit: with FIT all round two of the three fell out
        z0, z1 = sorted((zs - sg * 3.3, zs + sg * 0.5))
        return box(x - g, x + c + g, -AERIAL_T / 2, AERIAL_T / 2, z0, z1)
    pts = np.array([(x, zs - sg * 3.0), (x + c, zs - sg * 3.0), (x + c, zs + sg * 0.3),
                    (x + c * 0.5 + sweep, zs + sg * h), (x + c * 0.15 + sweep, zs + sg * h), (x, zs + sg * 0.3)])
    if sg < 0:
        pts = pts[::-1]
    return K.cs([pts]).extrude(AERIAL_T).translate([0, 0, -AERIAL_T / 2]).rotate([90, 0, 0])


def _frame(p, a, n):
    """3x4 matrix taking local (x along n, z along a) to the assembled frame at p."""
    a = np.asarray(a, float); a /= np.linalg.norm(a)
    n = np.asarray(n, float); n -= a * (n @ a); n /= np.linalg.norm(n)
    b = np.cross(a, n)
    return np.c_[n, b, a, np.asarray(p, float)]


def snap_boss(p, a, n, S, gap, length=None):
    """(boss, slot) for a snap fit: the boss stands on its parent's face at p, pointing along a;
    the spring slot (cut from the boss and the parent) lies across n. Returns both to add/cut.
    length: what the head clips over (model mm; default S's lip thickness)."""
    k = _P
    rn, rh, hl, ch = S["neck"] / 2 * k, S["head"] / 2 * k, S["head_len"] * k, S["cham"] * k
    length = S.get("lip_t", 0.0) * k if length is None else length
    zh = gap + length + S["end_gap"] * k                           # the head's shoulder
    neck = M.cylinder(zh + 1.0 + 0.01, rn, rn, 48).translate([0, 0, -1.0])   # from inside the parent
    head = M.cylinder(hl - ch, rh, rh, 64).translate([0, 0, zh]) \
        + M.cylinder(ch + 0.02, rh, rh - ch, 64).translate([0, 0, zh + hl - ch - 0.02])   # lead-in (overlaps:
                                                                       # faces that only touch stay apart)
    w = S["slot"] * k
    slot = box(-w / 2, w / 2, -rh - 1, rh + 1, -S["slot_in"] * k, zh + hl + 1)
    T = _frame(p, a, n)
    return (neck + head).transform(T), slot.transform(T)


def gear_socket_nose():
    zb = fuse_at(NOSE_GEAR_X)[3]
    return box(NOSE_GEAR_X - 2.2 - FIT, NOSE_GEAR_X + 2.2 + FIT, -2.2 - FIT, 2.2 + FIT, zb - 1, zb + 6.3)


def wheel_bearing(w):
    """Length the snap boss runs through a wheel of width w: inboard face to the dish floor."""
    return w - GEAR_SNAP["dish"] * _P


def wheel_m(x, yc, z_axle, d, w, inb=-1):
    """Wheel with a plain bore right through (v27): the leg's snap boss passes through it and its
    head clips over the floor of the outboard hub dish. The inboard face is plain and flat with a
    small chamfer, as it prints on it; tyre rounding outboard."""
    S, k = GEAR_SNAP, _P
    tyre = cq.Workplane("XZ").circle(d / 2).extrude(w / 2, both=True)
    tyre = tyre.edges(">Y" if inb < 0 else "<Y").fillet(min(1.5, w / 3))
    tyre = tyre.faces("<Y" if inb < 0 else ">Y").edges().chamfer(0.3 * _P)
    t = to_m(tyre)
    s = -inb                                                    # outboard
    t = t - cyl((0, s * (w / 2 + 0.1), 0), d * 0.58, -s * (S["dish"] * k + 0.1), "y")   # hub dish
    rb = S["bore"] / 2 * k
    t = t - cyl((0, -s * (w / 2 + 1), 0), 2 * rb, s * (w + 2), "y", 48)            # bore
    lc = S["bore_cham"] * k                                     # lead-in at the inboard face
    lead = M.cylinder(lc + 0.01, rb + lc, rb, 48).translate([0, 0, -0.01])
    t = t - lead.transform(_frame((0, inb * w / 2, 0), (0, -inb, 0), (1, 0, 0)))
    return t.translate([x, yc, z_axle])


def nose_gear():
    """Nose leg in one part: plug, oleo, fork top and one (left) arm carrying the snap boss the
    wheel pushes onto (v22; it was a stub axle into a press-on right arm). The arm is thick
    enough on its outer (bed) face for the spring slot. Returns (leg, (x, z_axle))."""
    zb = fuse_at(NOSE_GEAR_X)[3]
    d, w = NOSE_WHEEL
    x = NOSE_GEAR_X + 3.0
    z_axle = zb - GEAR_DROP + 1.0 + d / 2
    gap = GEAR_SNAP["gap"] * _P
    yi = -(w / 2 + gap)                                                # arm's inner face (boss face)
    yb = yi - 4.4                                                      # its outer face, on the bed
    zc0 = z_axle + d / 2 + 0.3                                         # underside of the fork top
    leg = union([box(NOSE_GEAR_X - 2.0, NOSE_GEAR_X + 2.0, -2.0, 2.0, z_axle + d / 2 + 1.0, zb - 0.1),   # oleo
                 box(NOSE_GEAR_X - 2.2, NOSE_GEAR_X + 2.2, -2.2, 2.2, zb - 0.2, zb + 6.0),                 # plug
                 box(NOSE_GEAR_X - 2.0, x + 2.0, yb, w / 2 + 0.6, zc0, z_axle + d / 2 + 2.6),               # fork top
                 box(x - 2.4, x + 2.4, yb, yi, z_axle - 2.6, zc0 + 0.01)])                                # arm
    boss, slot = snap_boss((x, yi, z_axle), (0, 1, 0), (1, 0, 0), GEAR_SNAP, gap, wheel_bearing(w))
    return (leg + boss) - slot, (x, z_axle)


def wing_underside_z(y, x=None):
    """Underside of the assembled wing at (x, y): probed, as both skins are curved."""
    if x is None:
        x = MAIN_GEAR[0]
    w = wing_assembled(1 if y >= 0 else -1)
    return (w ^ box(x - 0.3, x + 0.3, y - 0.3, y + 0.3, -60, 60)).bounding_box()[2]


def wing_top_z(y, x):
    w = wing_assembled(1 if y >= 0 else -1)
    return (w ^ box(x - 0.3, x + 0.3, y - 0.3, y + 0.3, -60, 60)).bounding_box()[5]


def main_gear(side):
    """Main leg with a stub axle moulded on its boss, through the wheel into a press-on retainer
    (the outer half). Returns (leg, retainer, (x, wheel y, z_axle))."""
    x, y = MAIN_GEAR
    y *= side
    zb = wing_underside_z(y)
    d, w = MAIN_WHEEL
    z_axle = zb - GEAR_DROP + d / 2
    xa = x + MAIN_TRAIL
    L = math.hypot(xa - x, zb - z_axle)
    ang = math.degrees(math.atan2(xa - x, zb - z_axle))                     # leg raked aft
    t = 2.2                                                                 # half-thickness: one flat
                                                                            # face for printing on its side
    ya, yb_ = sorted((y - side * (t + LEG_T_IN), y + side * t))             # thicker on the bed face
    leg = rot_about(box(x - 2.0, x + 2.0, ya, yb_, zb - L - 2.0, zb - 0.1), (x, y, zb), "y", -ang)
    leg = leg - box(x - 20, x + 40, y - 10, y + 10, zb - 0.1, zb + 20)   # trimmed flush under the wing
    y0 = y + side * t                                                       # boss face, towards the wheel
    gap = GEAR_SNAP["gap"] * _P
    f = union([leg,
               box(x - 2.2, x + 2.2, ya, yb_, zb - 0.2, zb + MAIN_PLUG_DEPTH),         # plug
               box(xa - 2.8, xa + 2.8, ya, yb_, z_axle - 2.8, z_axle + 2.8)])          # axle boss
    boss, slot = snap_boss((xa, y0, z_axle), (0, side, 0), (1, 0, 0), GEAR_SNAP, gap, wheel_bearing(w))
    return (f + boss) - slot, (xa, y0 + side * (gap + w / 2), z_axle)


def main_socket(side):
    x, y = MAIN_GEAR
    y *= side
    zb = wing_underside_z(y)
    ya, yb_ = sorted((y - side * (2.2 + LEG_T_IN), y + side * 2.2))
    return box(x - 2.2 - FIT, x + 2.2 + FIT, ya - FIT, yb_ + FIT, zb - 1, zb + MAIN_PLUG_DEPTH + 0.3)


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
    r = n["spig_r"] + NOZZLE_FIT
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
    sr, sl = n["spig_r"], n["spig_len"]
    cham = r - sr                                                   # 45 degrees
    rim = n.get("rim", r)
    flare = rim - r                                                 # 45 degrees out from the tail face
    body = (cyl((X - sl, 0, zc), 2 * sr, sl + 0.01, "x", 64)
            + cone_x(X - cham, 2 * sr, X + 0.01, 2 * r, 0, zc)
            + cone_x(X, 2 * r, X + flare + 0.01, 2 * rim, 0, zc)
            + cyl((X + flare, 0, zc), 2 * rim, out - flare, "x", 96))
    lip = cone_x(X + out - 0.6, 2 * (rim - wall), X + out + 0.01, 2 * (rim - wall * 0.45), 0, zc)  # thin exit lip
    void = (cyl((X, 0, zc), 2 * (r - wall), out + 0.01, "x", 96)                # exit (not into the
                                                                                 # flange: too thin)
            + cyl((X + flare, 0, zc), 2 * (rim - wall), out - flare + 0.01, "x", 96)   # wider behind the flare
            + cyl((X + out - n["void"], 0, zc), 2 * (sr - 0.9), n["void"] - out + 0.1, "x", 64))   # deeper pipe,
                                                                                 # open into the exit
    floor = X + out - n["void"]
    cone = cone_x(floor - 0.01, 2 * (sr - 1.4), floor + 6.5, 0.6, 0, zc)        # exhaust cone
    struts = union([rot_about(box(floor - 0.01, floor + 1.6, -0.35, 0.35, zc, zc + sr), (0, 0, zc), "x", a)
                    for a in range(0, 360, 60)])
    ring = (cyl((X - 0.01, 0, zc), 2 * (r - wall), 0.6, "x", 96)                      # step ring at the
            - cyl((X - 5, 0, zc), 2 * (r - wall - 0.9), 20, "x", 96))                 # bottom of the exit
    ribs = union([rot_about(box(X - sl + 0.6, X - cham - 0.2, -0.3, 0.3, zc + sr - 0.3, zc + sr + NOZZLE_RIB),
                            (0, 0, zc), "x", a) for a in range(0, 360, 90)])
    return (body - void - lip) + ribs + cone + (struts ^ cyl((floor - 1, 0, zc), 2 * (sr - 0.6), 4, "x", 64)) + ring


# --- Small ram-air scoops on the spine shoulders, just behind the canopy (side photos)
SPINE_DUCT = (129.0, 145.0, 32.5, 4.8, 2.6)   # x front, x rear, z where it sits, width, height proud
SPINE_DUCT_MOUTH = (3.2, 1.6, 3.5)            # opening width, height, depth


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
    b = outer() + spine_ducts() + strakes() + ventral_bulge() + fin_tail_fairing()
    for s in (1, -1):                                   # intakes sit on the wing
        w = (wing_assembled(s) + wing_glove(s)) ^ wing_root_box(s, False)
        b = b - w - w.translate([0, 0, FIT]) - w.translate([0, 0, -FIT])
        b = b + (wing_outer(s) ^ wing_root_box(s, True))   # the wing's root stub (v23)
        b = b + wing_te_fillet(s)                          # and its trailing-edge fillet (v24)
    b = b - (canopy_region() ^ box(DOME_CUT_X, 400, -60, 60, -60, 100)) + canopy_tabs()   # dome stays
    for s in (1, -1):
        b = b - intake_mouth(s) - splitter_gap(s)
        b = b - wing_key_slot(s, WING_KEY_FIT[1]) - tail_socket(s)
    b = b - jet_pipe_cut()
    b = b - fin_seat()
    b = b - pod_sockets()
    b = b - gear_socket_nose()
    for a in AERIALS:
        b = b - aerial(a, slot=True)
    return b


@cached
def fuselage_sections():
    b = fuselage_body()
    def slots(x, yz):
        return to_m(K.key_slots([(x, y, z) for y, z in yz], "x", x, KEY_FR, "z", KEY_FIT, KEY_END_GAP))
    fk = slots(FRONT_SPLIT_X, FRONT_KEYS)
    nk = slots(NOSE_SPLIT_X, NOSE_KEYS)
    keys = slots(FUSE_SPLIT_X, FR_KEYS)
    KEY_COUNTS["key_fuselage"] = (KEY_FR, len(FRONT_KEYS) + len(NOSE_KEYS) + len(FR_KEYS))
    _, _, _, bd, bl = PROBE
    pd, pl = PROBE_PLUG
    boss_aft = cyl((PROBE_CUT_X, 0, 0), bd, bl + 2.6 - (PROBE_CUT_X + bl - 0.4), "x", 32)   # to x 3.0
    recess = (cyl((PROBE_CUT_X - 0.1, 0, 0), pd + 2 * PROBE_FIT, pl + 0.4, "x", 24)
              + cone_x(PROBE_CUT_X - 0.1, pd + 2 * PROBE_FIT + 0.6, PROBE_CUT_X + 0.3, pd + 2 * PROBE_FIT, seg=24))   # lead-in
    nose = ((b ^ box(PROBE_CUT_X, FRONT_SPLIT_X, -60, 60, -60, 100)) + boss_aft) - recess - fk
    front = (b ^ box(FRONT_SPLIT_X, NOSE_SPLIT_X, -60, 60, -60, 100)) - fk - nk
    mid = (b ^ box(NOSE_SPLIT_X, FUSE_SPLIT_X, -60, 60, -60, 100)) - nk - keys
    rear = (b ^ box(FUSE_SPLIT_X, 400, -60, 60, -60, 100)) - keys
    return nose, front, mid, rear


def probe():
    """Pitot probe: cone, boss and a plug that pushes into the nose tip. Prints standing on
    the plug (tip up: use a brim); the boss's step over the plug is 1 mm."""
    L, d0, d1, bd, bl = PROBE
    pd, pl = PROBE_PLUG
    p = (cyl((-bl + 0.4, 0, 0), bd, PROBE_CUT_X + bl - 0.4, "x", 32)
         + cone_x(-bl - L + 0.4, d1, -bl + 1.4, d0)
         + cyl((PROBE_CUT_X - 0.05, 0, 0), pd, pl + 0.05, "x", 24))   # full-width end: it is the bed face
    return p


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
    key = box(STAND_X - k, STAND_X + k, -k, k, Sz - 3.0, zc + STAND_SOCKET_TOP - 0.3)   # vertical in the model frame
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
    nose, front, mid, rear = fuselage_sections()
    parts["fuselage_nose"], poses["fuselage_nose"] = nose, R(ry=90)    # dome face down, tip up
    parts["fuselage_front"], poses["fuselage_front"] = front, R(ry=90)  # aft joint face down
    parts["probe"], poses["probe"] = probe(), R(ry=90)                  # on its plug, tip up
    parts["fuselage_mid"], poses["fuselage_mid"] = mid, R(ry=90)       # aft joint face down
    parts["fuselage_rear"], poses["fuselage_rear"] = rear, R(ry=-90)   # joint face down, tail up
    parts["nozzle"], poses["nozzle"] = nozzle(), R(ry=-90)             # spigot down
    fs, fp, fslots = fin_halves()
    parts["fin_stbd"], poses["fin_stbd"] = fs - fslots, R(rx=90)       # split face down
    parts["fin_port"], poses["fin_port"] = fp - fslots, R(rx=-90)
    for side, tag in ((1, "stbd"), (-1, "port")):
        parts[f"wing_{tag}"], poses[f"wing_{tag}"] = wing_part(side), R(rx=90 * side)   # on its root, tip up
        flat = lambda m, s=side: rot_about(m, DIHEDRAL_PT, "x", -DIHEDRAL * s)
        for i, fence in enumerate(wing_fence_parts(side)):
            parts[f"wingfence_{tag}_{i + 1}"] = fence
            poses[f"wingfence_{tag}_{i + 1}"] = lambda m, f=flat: f(m).rotate([90, 0, 0])  # flat on its side
        parts[f"tailplane_{tag}"] = tailplane(side)
        poses[f"tailplane_{tag}"] = (lambda m, s=side: rot_about(m, (0, s * TAIL_ROOT_Y, TAIL_FLOOR), "x",
                                                                 TAIL_ANHEDRAL * s).rotate([90 * s, 0, 0]))
                                     # v28: on end, standing on its root plug's end, tip up (user):
                                     # both skins print as walls, no contour steps on top
    parts["canopy"] = canopy()
    (ra, rza), (rb, rzb) = CANOPY_REAR
    n = np.array([rza - rzb, rb - ra], float)        # outward normal of the rear face (x, z)
    n /= np.linalg.norm(n)
    poses["canopy"] = R(ry=math.degrees(math.atan2(n[0], -n[1])))   # on its rear face (test print 2:
                                                                    # smooth top, fewer colour changes)
    ps, pp = smoke_pod()
    parts["smoke_pod_stbd"], poses["smoke_pod_stbd"] = ps, R(rx=90)
    parts["smoke_pod_port"], poses["smoke_pod_port"] = pp, R(rx=-90)
    for i, a in enumerate(AERIALS):
        parts[f"aerial_{i + 1}"], poses[f"aerial_{i + 1}"] = aerial(a), R(rx=90)
    ng, (nx, nz) = nose_gear()
    parts["gear_nose"], poses["gear_nose"] = ng, R(rx=90)               # on its arm's outer face, boss up
    d, w = NOSE_WHEEL
    parts["wheel_nose"], poses["wheel_nose"] = wheel_m(nx, 0, nz, d, w, -1), R(rx=90)   # on its inboard face
    for side, tag in ((1, "stbd"), (-1, "port")):
        g, (gx, gy, gz) = main_gear(side)
        parts[f"gear_main_{tag}"], poses[f"gear_main_{tag}"] = g, R(rx=90 * side)    # on its side, boss up
        d, w = MAIN_WHEEL
        parts[f"wheel_main_{tag}"], poses[f"wheel_main_{tag}"] = wheel_m(gx, gy, gz, d, w, -side), R(rx=90 * side)
    post, base, piv = stand_parts()
    parts["stand_post"] = post
    poses["stand_post"] = lambda m: rot_about(m, piv, "y", STAND_PITCH).rotate([90, 0, 0])
    parts["stand_base"] = base
    poses["stand_base"] = lambda m: rot_about(m, piv, "y", STAND_PITCH)
    for kname, (key, n) in KEY_COUNTS.items():
        for i in range(n):
            parts[f"{kname}_{i + 1}"] = K.spring_key(key)      # split ends: easy in, still grips
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
