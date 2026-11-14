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
FIT = 0.15 * _P                 # sliding clearance per side (X2D fit test)
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
    (225.0, 18.9, 23.7, -15.0, 2.0),     # from here the body tapers and its top falls away under the
    (260.0, 17.8, 21.5, -15.0, 2.0),     # fin's long dorsal ridge, which keeps the top line level
    (300.0, 16.0, 18.0, -15.0, 2.0),     # (Airfix top view; XH558 Farnborough photo; user review)
    (330.0, 14.5, 15.0, -15.0, 2.0),
    (350.0, 13.5, 12.5, -15.0, 2.0),
    (365.0, 12.8, 11.0, -14.8, 2.0),
    (383.9, 11.6, 10.5, -14.2, 2.0),
    (395.5, 11.6, 8.0, -12.9, 2.0),
    (401.3, 10.6, 6.6, -12.2, 2.0),
    (407.0, 9.2, 5.2, -11.0, 2.0),
    (412.9, 6.5, 3.8, -9.6, 2.0),
    (418.7, 4.0, 1.5, -7.5, 2.0),
    (LENGTH, 0.8, -2.9, -3.9, 2.0),
]
# Under the wing the body is not a tube: its flat-bottomed keel (bomb bay and its fairing) runs level
# with the wing's lowest point from the nose gear bay back to the jet pipes (underside photos; the
# bomb doors would otherwise ride up the tube's sides). x, half-width, z bottom.
KEEL_STATIONS = [(116.0, 17.0, -15.0), (150.0, 22.5, -15.0), (320.0, 22.5, -15.0), (340.0, 18.0, -15.0),
                 (356.0, 13.5, -14.9)]
KEEL_TOP = -2.0
KEEL_N = 5.0
CANOPY_STATIONS = [             # x, half-width, z top: the small bubble over the flight deck
    (58.0, 4.0, 20.5), (62.0, 7.5, 25.6), (69.6, 9.5, 29.5), (77.4, 9.5, 29.5),
    (85.0, 9.0, 28.5), (93.0, 8.0, 27.6), (101.0, 6.0, 25.6), (110.0, 3.0, 24.2),
]
CANOPY_DEPTH = 12.0
CANOPY_N = 2.5
BLISTER = (70.0, -14.6, 12.0, 7.0, 3.5)   # bomb aimer's blister: x, z, radii along x, y, z
PROBE = (26.0, 2.0 * _P)        # refuelling probe: length ahead of the nose tip, diameter (2 mm printed: thicker than scale)
PROBE_PLUG = (7.0, 0.08 * _P)   # its plug into the radome tip: depth, fit per side

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
WING_ROOT_UP = [(0.0, 23.0), (14.0, 23.0), (28.0, 20.3), (42.0, 16.4), (57.0, 12.9), (70.0, 11.5)]
                                # (y, depth of the top above the split): a smooth (PCHIP) curve into the outer wing
WING_CREST = (0.09, 1.25)       # inboard: crest at this fraction of chord, then 1 - u^k to the trailing edge
WING_UNDER_RAMP = (0.30, 0.8)   # inboard underside: reaches full depth at this fraction of chord, exponent
WING_CREST_BLEND = (25.0, 80.0)  # the inboard profile fades into the plain aerofoil over this span
SPLIT_TIP_Z = -14.0
WING_JOINT_Y = 57.0             # centre body / outer wing joint (just outboard of the intakes and jet pipes)
RADOME_X = 24.0                 # the black radome is its own part ahead of this
FRONT_X = 105.0                 # front fuselage / centre body joint, at the wing root's leading edge
# The upper surface over the engines is smoothed: every concave crease on top (wing to fuselage,
# intake fairing to wing, jet pipe humps to wing and to each other) is filled as if a ball of this
# radius had been rolled over it (user: "seamlessly incorporating the engines").
BLEND_R = [(110.0, 4.0), (150.0, 4.0), (190.0, 12.0), (300.0, 12.0), (358.0, 2.0)]   # (x, radius): small
                                # by the intakes, a soft fillet along the fuselage, fading out at the trailing edge
BLEND_X = (112.0, 359.0)        # x range of the fill
BLEND_UNDER_R = [(112.0, 6.0), (190.0, 6.0), (210.0, 4.0), (330.0, 4.0), (358.0, 1.5)]   # the same underneath:
                                # behind the intakes' lower lips and round the jet pipe fairings
BLEND_UNDER_X = (112.0, 359.0)
BLEND_Y = 85.0                  # out to this span (the outer wing has no creases)
BLEND_STEP = (1.5, 0.3)         # grid: x, y
# Panel lines on the upper surface, starboard, as (x, y) polylines read off the Airfix scheme B top
# view on a 10 mm grid (ref airfix_b_top.png: 2.3026 px/mm, centreline col 592.5, nose row 28).
LINE_W, LINE_D = 0.5 * _P, 0.25 * _P        # panel lines: 0.5 mm wide, 0.25 mm deep, printed
HINGE_W, HINGE_D = 0.6 * _P, 0.4 * _P       # control surface edges
_EB = (22.0, 58.0)                          # engine bay: from the fuselage side to its outer edge
PANEL_LINES = (
    [[(x, _EB[0]), (x, _EB[1])] for x in (188, 208, 217, 226, 235, 244, 253, 262, 270, 278, 287, 302, 316)]
    + [[(160, 58), (360, 58)], [(188, 22), (345, 22)]]                 # the bay's outer and inner edges
    + [[(316, y), (358, y)] for y in (27.0, 37.0, 44.0, 54.0)]         # jet pipe panels
    + [[(126, 13), (190, 58), (250, 153)],                            # behind the leading edge panels
       [(250, 153), (290, 146), (345, 137)],                          # outer wing joint
       [(311, 58), (333, 137), (352, 221)],                           # rear spar
       [(320, 221), (382, 221)]]                                      # tip panel
    # skin stiffeners outboard of the engine bay: every other one of the sheet's
    + [[(x0, 58), (x0 + 0.80 * (y1 - 58), y1)] for x0, y1 in
       ((200, 148), (222, 146), (240, 144), (262, 140), (290, 98))]
)
HINGE_LINES = (
    [[(327, 58), (348, 137), (365, 221)]]                             # elevon hinge
    + [[(337, 97), (364.5, 97)], [(348, 137), (369.5, 137)], [(356.7, 180), (374.5, 180)]]   # elevon ends
)
# Underside lines, from the Airfix scheme B underside view (ref airfix_b_under.png: 2.3026 px/mm,
# centreline col 630.5, nose tip row 985, nose down; starboard on the right).
_STIFF = [[(x0, 58), (x0 + 0.80 * (y1 - 58), y1)] for x0, y1 in
          ((200, 148), (222, 146), (240, 144), (262, 140), (290, 98))]
UNDER_LINES = (
    [[(x, 22), (x, 57)] for x in (211, 231, 252, 275, 337.5)]          # engine doors
    + [[(211, 39.5), (275, 39.5)], [(205, 57), (360, 57)], [(205, 22), (205, 57)]]
    + [[(86, 6.5), (107, 6.5)], [(86, 0), (86, 6.5)], [(107, 0), (107, 6.5)]]   # crew hatch
    + [[(190, 58), (250, 153)], [(250, 153), (290, 146), (345, 137)],  # as on top: leading-edge line,
       [(311, 58), (333, 137), (352, 221)], [(320, 221), (382, 221)]]  # outer joint, rear spar, tip
    + _STIFF
)
UNDER_DOORS = (                                                        # cut deeper: doors
    [[(187, 0), (187, 21.5), (310, 21.5), (310, 0)], [(187, 0), (310, 0)]]      # bomb bay, 123 x 43 mm
    + [[(122, 0), (122, 8), (162, 8), (162, 0)], [(122, 0), (162, 0)]]          # nose gear doors
    + [[(184, 31), (204, 53), (204, 70), (186, 58), (184, 31)]]                 # main gear door
)
UNDER_STBD = [[(360, 32), (298, 32), (285, 39.5), (298, 47), (360, 47)]]        # plate under the starboard jet pipes
# Bays. Each is an opening in a lower shell with a ledge round it; a door panel cut from the shell's
# own skin drops in from below against the ledge (wheels up, bomb doors shut), or is left out.
# name: (part, outline (x, y) starboard or centred, ledge z, roof z, mirrored to port too?)
# name: (part, outline (x, y) starboard or centred, ledge z, roof z, mirrored to port too?, ledge width)
BAY_LEDGE_W = 1.4               # width of the bomb bay's ledge (the gear bays' are wider: they carry a frame)
BAYS = {
    "bomb": ("centre", [(187, -21.5), (187, 21.5), (310, 21.5), (310, -21.5)], -12.3, -6.0, False, 1.4),
    "nose": ("centre", [(117, -8), (117, 8), (160, 8), (160, -8)], -11.5, -6.0, False, 2.0),
    "main": ("wing", [(204, 60), (204, 71), (232, 75), (258, 75), (258, 60)], -12.5, -7.0, True, 2.0),
}

# Landing gear (Airfix side view on a 5 mm grid; instruction pages 22-23; photos). Ground at z -46.5.
# Each leg is two flat halves split on its own centre plane, printed lying on that plane with the
# wheels moulded on top: no loose axles (LESSONS: small pins snap). Legs are thicker than scale.
GROUND_Z = -46.5
GEAR_T = 4.4                    # leg thickness across the split (two halves of 1.65 mm printed)
GEAR_PLUG_FIT = 0.06 * _P       # plug to socket, per side: a firm push (socket sized from the closed halves)
GEAR_PLUG_TOP = 1.0             # the plugs run up through the bay roof into the upper shell, to this z
NOSE_GEAR = dict(
    yc=0.0, wheel=(120.0, -41.5),
    # leg outline (x, z), from the plug down to the axle block
    leg=[(117.7, GEAR_PLUG_TOP), (121.3, GEAR_PLUG_TOP), (121.3, -36.0), (122.2, -38.5), (122.2, -44.0),
         (117.8, -44.0), (117.8, -38.5), (117.7, -36.0)],
    struts=[((127.0, -6.3), (120.6, -27.0))],                 # retraction strut (clear of the roof)
    plug=(117.7, 121.3),
    wheel_profile=[(0.0, 3.0), (0.7, 3.0), (2.7, 5.0), (5.3, 5.0), (5.7, 4.4)],   # along the axle from the split: (pos, radius)
)
MAIN_GEAR = dict(
    yc=67.0, wheels=[(242.5, -42.0), (252.7, -42.0)],
    leg=[(246.3, GEAR_PLUG_TOP), (250.5, GEAR_PLUG_TOP), (250.5, -7.0), (246.8, -38.0), (254.0, -39.6),
         (254.0, -44.0), (241.2, -44.0), (241.2, -39.6), (243.0, -38.0), (246.3, -7.0)],
    struts=[((237.4, -9.0), (242.0, -29.0)), ((248.6, -25.0), (248.6, -39.0)), ((242.0, -29.0), (238.5, -33.5)),
            ((238.5, -33.5), (243.0, -37.0))],
    plug=(246.3, 250.5),
    wheel_profile=[(0.0, 2.9), (0.1, 2.9), (1.7, 4.5), (4.0, 4.5), (4.8, 3.7), (5.6, 4.5), (7.7, 4.5), (8.0, 4.2)],   # flares and the groove between the twin tyres at 45 degrees: no overhang
)
# Blue Steel stand-off missile (Airfix scheme A underside sheet: side and plan views; real length
# 10.7 m, body 1.27 m, wing span 3.96 m). Carried half sunk in the bomb bay: the kit part is the
# half below the belly, printed on its flat top face with the wings and foreplanes on the bed; it
# keys onto its own bomb door panel (door_bluesteel) in place of the plain doors.
BS_X = (166.0, 315.0)           # nose and tail: the nose runs 21 mm ahead of the bay
BS_Z = -15.0                    # centreline, on the belly
BS_PROFILE = [(0.0, 0.3), (6.0, 1.8), (16.0, 4.0), (30.0, 6.2), (48.0, 7.9), (66.0, 8.7), (80.0, 8.8),
              (133.0, 8.8), (141.0, 8.3), (146.0, 7.0), (149.0, 4.5)]      # distance from the nose, radius
BS_WING = [(102.0, 7.0), (131.0, 26.0), (136.0, 26.0), (136.0, 7.0)]      # (from the nose, y), starboard
BS_FORE = [(12.0, 2.0), (30.0, 15.4), (36.0, 15.4), (36.0, 5.0)]
BS_WING_T = 1.2 * _P            # wing and foreplane thickness (1.2 mm printed)
BS_KEYS = [(215.0, 285.0), (8.0, 3.0, 2.4)]   # x of the two keys on the door; length, width, height
# Stand (wheels up): a blade post with a square key that goes up through its own bomb door panel
# (door_bomb_stand) into the bay roof plate, and a tenon into a plinth. The aircraft sits nose-up.
STAND_X = 240.0                 # key position: near the balance point, inside the bomb bay
STAND_KEY = 8.0                 # key and post thickness (6 mm printed)
STAND_PITCH = 8.0               # degrees nose-up
STAND_HEIGHT = 107.0            # belly above the plinth at the key (80 mm printed)
STAND_SWEEP = 20.0              # the foot sits this far behind the key
STAND_SHOULDER = (22.0, 30.0)   # post width under the belly, and at the foot
STAND_TENON = (16.0, 8.0)       # tenon length along the plinth, depth into it
STAND_BASE = (200.0, 133.0, 10.7, 14.0)   # plinth length, width, thickness, corner radius (150 x 100 x 8 printed)
STAND_BASE_DX = -30.0           # plinth centre from the foot, along the plinth (forward)
# Joints. Every key is a flat plate standing on edge across the split surface, upright in the
# assembled frame, so all the upper shells go straight down onto the lower ones. The long ones also
# cross a joint between sections. Slot depth is found per key from the material there.
KEY_T = 3.0 * _P                # key thickness (3 mm printed)
KEY_FIT = 0.08 * _P             # per side across the thickness: a firm push (to be set from test coupons)
KEY_WALL = 1.0 * _P             # skin left beyond a slot's end
KEY_GAP = 0.3 * _P              # slot deeper than the key by this, each end
KEY_H = [h * _P for h in (5.0, 4.5, 4.0, 3.5, 3.0, 2.5, 2.0, 1.6)]   # half-heights tried, deepest first
# (parts' name prefixes, (x, y) centre, direction of the key's length, length), y mirrored when != 0
KEYS = (
    [(("front",), (x, 0.0), "x", 6.0 * _P) for x in (45.0, 80.0)]
    + [(("front", "centre"), (102.0, 9.0), "x", 18.0 * _P)]
    + [(("centre",), xy, "x", 6.0 * _P) for xy in ((172.0, 14.0), (201.0, 30.0), (250.0, 42.0), (330.0, 42.0),
                                                   (335.0, 0.0), (385.0, 0.0))]
    + [(("centre", "wing"), (x, WING_JOINT_Y), "y", 30.0 * _P) for x in (199.5, 300.0)]
    + [(("wing",), xy, "x", 6.0 * _P) for xy in ((245.0, 100.0), (310.0, 100.0), (285.0, 150.0), (305.0, 150.0))]
)
RADOME_TONGUE = (10.0, 5.0, 2.5)   # front shells' tongue into the radome: length, half-width, half-height
FIN_FIT = 0.10 * _P             # fin root in its slot, per side
STRUT_W = 1.7
DOOR_T = 1.6                    # open gear doors: 1.2 mm printed
NOSE_DOORS = (118.5, 158.5, 7.0)          # x range and how far the two doors hang below the belly
MAIN_DOOR = (212.0, 230.0, 16.0)          # the big door on the bay's outboard edge: x range, drop
BOMB_ROOF = (2.0, 2.0, 12.0, 1.2, 1.5)   # roof plate: thickness, margin round the bay, rib pitch, rib width, rib depth
BED = (230.0, 250.0)            # usable plate, printed mm (X2D; 256 mm beds are larger)
WING_Y = [0.0, 5.0, 10.0, 15.0, 19.8, 24.0, 29.0, 34.0, 39.0, 44.0, 49.8, 54.0, 57.0, 58.5, 63.0, 67.9, 72.0,
          77.8, 84.0, 90.0, 97.2, 116.5, 135.8, 155.2, 174.5,
          189.0, 193.9, 200.0, 206.9, 213.2, 219.0, 224.3, 229.0, 232.5, 233.5, 234.6, 234.8]

# Intakes: letterbox mouths in the swept inner leading edge, one per engine pair, split in two.
INTAKE_Y = (20.8, 59.0)         # span of the lip: its inner wall stands off the fuselage
INTAKE_GAP = (2.0, 16.0, -9.0)  # boundary-layer gap between the intake's inner wall and the fuselage
                                # skin: width, how far it runs back from the lip, and its floor (z);
                                # it is open at the top (XH558 photos; user: "almost a separation")
# The mouth, measured on the colour head-on photo (12.2 px per model mm; belly z -15 at the bottom
# of the fuselage): one opening a side, tall at its inner end (z -5.3 to 8.2 at y 23.8, a nearly
# upright inner edge with rounded corners) and tapering to a round outer end (y 56, z -2 to 3.7),
# with gently bowed top and bottom lips. A thick round lip runs all the way round it. In plan the
# lip follows the wing's leading edge, including the notch at y 50-58, which is its outer end.
INTAKE_INNER = (23.8, -5.3, 8.2, 2.5)     # y of the inner edge, z bottom, z top, corner radius
INTAKE_OUTER = (53.15, 0.85, 2.85)        # outer end: centre y, z, radius
INTAKE_BOW = (38.0, 6.8, -4.3)            # mid-span: y, z of the top lip, z of the bottom lip
INTAKE_LIP = 3.0                # lip thickness (2.25 mm printed): its nose is a half-round of this diameter
INTAKE_WALL_BOW = (5.5, 10.0)    # the inner wall's leading edge bows forward by this much at mid-height
                                # (side-on photo), fading out over this span outboard
INTAKE_FAIR = [(8.0, 0.6, 1.0), (22.0, 0.9, 1.0), (45.0, 0.0, 0.55)]   # behind the lip: distance, extra
                                # offset, height scale (the fairing sinks into the wing)
INTAKE_SPLIT = (24.0, 37.6, 1.8)  # the wall between the two engines' ducts: set back, y, thickness
INTAKE_DEPTH = 90.0             # (the ducts are cut off where the round tunnels start)
# Engine faces: each duct ends in a round tunnel with a compressor face at its end (hub and blades),
# a separate plate printed face up that drops into a slot between the centre shells.
# (y centre, z centre, x of the face): all four faces are the same distance back from the nose, deep
# in the wing (user review), so the inner ducts are long: 70 mm from the lip at the fuselage side.
ENGINES = [(30.2, 1.3, 192.0), (47.0, 1.0, 192.0)]
ENGINE_R = 5.5                  # tunnel radius (8.25 mm bore printed)
ENGINE_TUNNEL = 14.0            # length of the round tunnel ahead of the face
ENGINE_PLATE = (6.5, 2.0, -6.4, 8.4)   # plate: half-width, thickness, z bottom, z top
ENGINE_FAN = dict(blades=10, hub_r=1.7, hub_len=2.2, rim=0.5, depth=0.8, swirl=16.0)
INTAKE_PTS = 144

# Jet pipes: four, in pairs. Their fairings run under the wing from mid-chord (the side
# view's lowest line, about 3.5 mm below the belly) and the nozzles stand 6 mm behind the trailing edge.
JET_Y = (33.4, 45.9)
JET_Z = -7.5                    # the pipes straddle the trailing edge: their tops show as humps on the
                                # upper surface over the last 40 mm, their undersides as the long fairings below
JET_PROFILE = [(197.0, 1.5), (252.0, 5.0), (302.0, 6.3), (366.5, 6.5)]   # x, radius
JET_BORE = (5.4, 10.0)          # radius, depth

# Fin: leading and trailing edge lines (x at z), symmetric section, rounded front top corner.
FIN_LE = ((303.6, 23.7), (362.5, 69.0))
FIN_TE = ((376.0, 11.0), (406.0, 70.6))
FIN_Z = (5.0, 72.0)
FIN_TC = (0.08, 0.08)
FIN_TIP_ROUND = (7.0, 5.0)
FIN_RIDGE = (24.5, 222.0)       # below this z the fin runs forward to this x as a low dorsal ridge on the
                                # falling body (the ochre-tipped wedge in the Airfix top view)
FIN_FILLET = (31.7, 8.0, 17.0, 1.6)   # below this z the leading edge sweeps forward into the spine:
                                # over this height, by this much at the spine, with this exponent (Airfix side view)
FIN_CAP = [(362.0, 0.5, 71.6, 70.6), (366.0, 2.0, 72.8, 69.6), (404.0, 2.0, 72.8, 69.6),
           (409.5, 0.8, 72.0, 70.4)]   # x, half-width, z top, z bottom: the fairing on the fin top (XH558 fin photo)     # the leading edge rounds into the top over this height, by this much

BIG = 600.0
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
def intake_gap():
    """Slot between the intake's inner wall and the fuselage (starboard): a shell of the gap's
    width round the body, from ahead of the lip to INTAKE_GAP[1] behind it."""
    g, depth, z0 = INTAKE_GAP
    grown = ring_loft([x_ring(x, hw + g, zt + g, zb - g, n) for x, hw, zt, zb, n in dense(FUSE_STATIONS)])
    x0 = lip_x(INTAKE_Y[0])
    return (grown - body()) ^ K.box(x0 - 8.0, x0 + depth, 0.0, 60.0, z0, 60.0)


@cached
def keel():
    return ring_loft([x_ring(x, hw, KEEL_TOP, zb, KEEL_N) for x, hw, zb in dense(KEEL_STATIONS)])


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
        from scipy.interpolate import PchipInterpolator
        r = np.asarray(WING_ROOT_UP)
        du = float(PchipInterpolator(r[:, 0], r[:, 1])(ya))
    x = (1 - np.cos(np.pi * np.arange(n + 1) / n)) / 2
    f = 0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4
    f = f / f.max()
    p, k = WING_CREST
    fw = np.where(x < p, np.sqrt(np.clip(1 - (1 - x / p) ** 2, 0, 1)), 1 - np.clip((x - p) / (1 - p), 0, 1) ** k)
    w = float(np.clip((ya - WING_CREST_BLEND[0]) / (WING_CREST_BLEND[1] - WING_CREST_BLEND[0]), 0, 1))
    fu = (1 - w) * fw + w * f
    e = np.minimum(WING_TE_T, t) / 2 * x                  # half the trailing edge thickness, growing aft
    up = np.c_[x * c, fu * (du - e[-1]) + e][::-1]
    # underneath, inboard, the belly comes up to the intake's lower lip on a long ramp, not a blunt nose
    fr = np.where(x < WING_UNDER_RAMP[0], (x / WING_UNDER_RAMP[0]) ** WING_UNDER_RAMP[1], f)
    fl = (1 - w) * np.maximum(np.minimum(fr, f), 0.0) + w * f
    lo = np.c_[x * c, -(fl * (dl - e[-1]) + e)][1:]
    sec = np.vstack([up, lo])
    return np.c_[le + sec[:, 0], np.full(len(sec), y), zs + sec[:, 1]]


@cached
def wing():
    """Starboard panel from the centreline to the tip."""
    return ring_loft([wing_ring(y) for y in WING_Y])


def lip_x(y):
    return wing_le(y)


@cached
def mouth_outline():
    """The opening as INTAKE_PTS points (y, z), evenly spaced, anticlockwise from the outer end,
    with unit outward normals."""
    from shapely.geometry import Point, Polygon, MultiPoint
    yi, zb, zt, rc = INTAKE_INNER
    yo, zo, ro = INTAKE_OUTER
    ym, zmt, zmb = INTAKE_BOW
    pts = [(yi, zb), (yi, zt), (ym, zmt), (ym, zmb)] + list(Point(yo, zo).buffer(ro, 64).exterior.coords)
    poly = MultiPoint(pts).convex_hull.buffer(-rc, 32).buffer(rc, 32)
    ring = poly.exterior
    if not ring.is_ccw:
        ring = ring.reverse()
    start = ring.project(Point(yo + ro, zo))
    d = (start + np.arange(INTAKE_PTS) * ring.length / INTAKE_PTS) % ring.length
    p = np.array([ring.interpolate(t).coords[0] for t in d])
    tan = np.roll(p, -1, 0) - np.roll(p, 1, 0)
    nrm = np.c_[tan[:, 1], -tan[:, 0]]
    return p, nrm / np.linalg.norm(nrm, axis=1)[:, None]


def mouth_ring(s, offset, z_scale=1.0):
    """The mouth outline grown by `offset`, s behind the lip's nose, in the swept lip surface."""
    p, n = mouth_outline()
    q = p + offset * n
    yi, zb, zt, _ = INTAKE_INNER
    zc = (zb + zt) / 2
    if z_scale != 1.0:
        q[:, 1] = zc + (q[:, 1] - zc) * z_scale
    bow, span = INTAKE_WALL_BOW
    w = np.clip(1 - (q[:, 0] - yi) / span, 0, 1) ** 2 * np.clip(1 - ((q[:, 1] - zc) / ((zt - zb) / 2 + INTAKE_LIP)) ** 2, 0, 1)
    xl = np.array([lip_x(max(float(v), yi)) for v in p[:, 0]])
    return np.c_[xl + s - bow * w, q[:, 0], q[:, 1]]


_LIP_TH = np.radians([0.0, 20.0, 40.0, 60.0, 75.0, 90.0])


@cached
def intake_fairing():
    """The lip and the fairing behind it (solid; the duct is cut from it)."""
    t = INTAKE_LIP
    rings = [mouth_ring(t / 2 * (1 - math.cos(a)), t / 2 * (1 + math.sin(a))) for a in _LIP_TH]
    rings += [mouth_ring(sd, t + extra, zs) for sd, extra, zs in INTAKE_FAIR]
    return ring_loft(rings)


@cached
def intake_ducts():
    t = INTAKE_LIP
    rings = [mouth_ring(-2.0, t / 2 + 0.01)] + [mouth_ring(t / 2 * (1 - math.cos(a)), t / 2 * (1 - math.sin(a))) for a in _LIP_TH]
    rings.append(mouth_ring(INTAKE_DEPTH, 0.0))
    back, ys, tw = INTAKE_SPLIT
    wall = K.box(lip_x(ys) + back, 230.0, ys - tw / 2, ys + tw / 2, -30.0, 30.0)
    nose = M.cylinder(60.0, tw / 2, tw / 2, 24).translate([lip_x(ys) + back, ys, -30.0])
    (yi, zi, xi), (yo, zo, xo) = ENGINES
    cells = K.box(-BIG, xi - ENGINE_TUNNEL + 1.0, 0.0, ys, -BIG, BIG) + K.box(-BIG, xo - ENGINE_TUNNEL + 1.0, ys, BIG, -BIG, BIG)
    tunnels = union([M.cylinder(ENGINE_TUNNEL, ENGINE_R, ENGINE_R, 64).rotate([0, 90, 0]).translate([x - ENGINE_TUNNEL, y, z])
                     for y, z, x in ENGINES])
    return ((ring_loft(rings) ^ cells) + tunnels) - wall - nose


def engine_face(zc):
    """One compressor face at x 0, y 0, facing -x: the plate with its fan in relief, centred at zc."""
    hw, t, zb, zt = ENGINE_PLATE
    f = ENGINE_FAN
    r1 = ENGINE_R - 0.3
    plate = K.box(0.0, t, -hw, hw, zb, zt)
    blades = []
    n = f["blades"]
    for i in range(n):
        a0 = 2 * math.pi * i / n
        da = math.pi / n * 0.55
        sw = math.radians(f["swirl"])
        pts = [(f["hub_r"] * 0.8 * math.cos(a0 - da), f["hub_r"] * 0.8 * math.sin(a0 - da)),
               (r1 * math.cos(a0 - da + sw), r1 * math.sin(a0 - da + sw)),
               (r1 * math.cos(a0 + da + sw), r1 * math.sin(a0 + da + sw)),
               (f["hub_r"] * 0.8 * math.cos(a0 + da), f["hub_r"] * 0.8 * math.sin(a0 + da))]
        blades.append(K.cs([pts]))
    fan = mf.CrossSection.batch_boolean(blades, mf.OpType.Add).extrude(f["depth"])
    hub = M.cylinder(f["hub_len"], f["hub_r"], 0.5, 32)
    relief = (fan + hub).rotate([0, -90, 0])              # +z -> -x: stands out of the plate's front
    return plate + relief.translate([0, 0, zc])


def add_engines(parts):
    hw, t, zb, zt = ENGINE_PLATE
    for sgn in (1, -1):
        for i, (y, z, x) in enumerate(ENGINES):
            slot = K.box(x - KEY_FIT, x + t + KEY_FIT, sgn * y - hw - FIT, sgn * y + hw + FIT, zb - 0.3, zt + 0.3)
            for n in ("centre_upper", "centre_lower"):
                parts[n] = (parts[n][0] - slot, parts[n][1])
            tag = f"engine_face_{'stbd' if sgn > 0 else 'port'}_{'inner' if i == 0 else 'outer'}"
            parts[tag] = (engine_face(z).translate([x, sgn * y, 0]), lambda m: m.rotate([0, 90, 0]))


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
    zs = np.r_[np.linspace(FIN_Z[0], FIN_RIDGE[0] - 0.15, 8), np.linspace(FIN_RIDGE[0] + 0.15, FIN_Z[1] - span, 34), FIN_Z[1] - span * (1 - np.sin(np.linspace(0.15, 1, 9) * np.pi / 2))]
    for z in zs:
        le = xl0 + (z - zl0) * (xl1 - xl0) / (zl1 - zl0)
        te = xt0 + (z - zt0) * (xt1 - xt0) / (zt1 - zt0)
        u = max(0.0, (z - (FIN_Z[1] - span)) / span)
        le += cut * (1 - math.sqrt(max(0.0, 1 - u * u)))
        zf, hf, df, kf = FIN_FILLET
        le0 = le
        if z < FIN_RIDGE[0]:                         # dorsal ridge
            le = FIN_RIDGE[1]
        elif z < zf:                                 # root fillet: longer chord, same thickness
            le -= df * min(1.6, (zf - z) / hf) ** kf
        sec = aerofoil(FIN_TC[0] * (te - le0) / (te - le), te - le, WING_TE_T)
        rings.append(np.c_[le + sec[:, 0], sec[:, 1], np.full(len(sec), z)])
    cap = ring_loft([x_ring(x, hw, zt, zb, 3.0) for x, hw, zt, zb in dense(FIN_CAP, 1.5)])
    return ring_loft(rings) + cap


@cached
def probe():
    """(probe with its plug, the hole for it in the radome tip)."""
    length, d = PROBE
    depth, f = PROBE_PLUG
    rod = M.cylinder(length + depth, d / 2, d / 2, 32).rotate([0, 90, 0]).translate([-length, 0, 0])
    hole = M.cylinder(length + depth + 0.5, d / 2 + f, d / 2 + f, 32).rotate([0, 90, 0]).translate([-length, 0, 0])
    return rod, hole


def _closing(z, r, step):
    """Roll a ball of radius r over the height profile z (sampled every `step`): fills concave
    corners, leaves convex shapes and drop-offs alone."""
    k = int(r / step)
    if k < 1:
        return z
    d = np.arange(-k, k + 1) * step
    cap = np.sqrt(np.maximum(r * r - d * d, 0.0))
    n = len(z)
    pad = np.pad(z, k, constant_values=-1e3)
    win = np.lib.stride_tricks.sliding_window_view(pad, 2 * k + 1)
    up = (win + cap).max(1)
    pad = np.pad(up, k, constant_values=1e3)
    win = np.lib.stride_tricks.sliding_window_view(pad, 2 * k + 1)
    return np.maximum((win - cap).min(1), z)[:n]


def top_field(solid, xs, ys):
    """Height of the solid's upper surface on the grid (xs, ys); -1e3 where there is none."""
    turned = solid.transform(np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0]], float))   # (y, z, x)
    Z = np.full((len(xs), len(ys)), -1e3)
    for i, x in enumerate(xs):
        for poly in turned.slice(float(x)).to_polygons():
            a, b = poly, np.roll(poly, -1, axis=0)
            for (y1, z1), (y2, z2) in zip(a, b):
                if y1 > y2:
                    y1, z1, y2, z2 = y2, z2, y1, z1
                j0, j1 = np.searchsorted(ys, y1), np.searchsorted(ys, y2)
                if j1 > j0:
                    yy = ys[j0:j1]
                    Z[i, j0:j1] = np.maximum(Z[i, j0:j1], z1 + (z2 - z1) * (yy - y1) / (y2 - y1))
    return Z


def heightfield_solid(xs, ys, Z, z0):
    """Solid between the level z0 and the surface Z on the grid."""
    nx, ny = Z.shape
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    top = np.c_[X.ravel(), Y.ravel(), Z.ravel()]
    bot = np.c_[X.ravel(), Y.ravel(), np.full(nx * ny, z0)]
    idx = np.arange(nx * ny).reshape(nx, ny)
    a, b, c, d = idx[:-1, :-1].ravel(), idx[1:, :-1].ravel(), idx[1:, 1:].ravel(), idx[:-1, 1:].ravel()
    o = nx * ny
    faces = [np.c_[a, b, c], np.c_[a, c, d], np.c_[a + o, c + o, b + o], np.c_[a + o, d + o, c + o]]
    for edge, rev in ((idx[:, 0], False), (idx[:, -1], True), (idx[0, :], True), (idx[-1, :], False)):
        e0, e1 = edge[:-1], edge[1:]
        q = [np.c_[e0, e0 + o, e1 + o], np.c_[e0, e1 + o, e1]]
        faces += [f[:, ::-1] for f in q] if rev else q
    tm = trimesh.Trimesh(np.vstack([top, bot]), np.vstack(faces), process=False)
    if tm.volume < 0:
        tm.invert()
    m = K.to_manifold(tm)
    if m.status() != mf.Error.NoError:
        raise RuntimeError(f"height field not manifold: {m.status()}")
    return m


@cached
def surface_blend(under):
    """Fill for the creases in the upper surface over the engines (under=False), or in the
    underside round the jet pipe fairings (under=True); both sides of the aircraft."""
    solid = raw_airframe()
    if under:                                    # work on the solid turned over, then turn the fill back
        solid = solid.rotate([180, 0, 0])
    radii, (x0, x1) = (BLEND_UNDER_R, BLEND_UNDER_X) if under else (BLEND_R, BLEND_X)
    level = (-SPLIT_Z if under else SPLIT_Z) - 1.0
    sx, sy = BLEND_STEP
    xs = np.arange(x0 - 15.0, x1 + 15.0 + sx / 2, sx)
    ys = np.arange(-BLEND_Y - 25.0, BLEND_Y + 25.0 + sy / 2, sy)
    Z = top_field(solid, xs, ys)                 # -1e3 where there is no surface: a drop-off, never filled
    r = np.interp(xs, [p[0] for p in radii], [p[1] for p in radii])
    C = np.array([_closing(Z[i], r[i], sy) for i in range(len(xs))])          # across the span
    rm = float(np.min(r))
    C = np.maximum(C, np.array([_closing(C[:, j], rm, sx) for j in range(len(ys))]).T)   # along the chord
    keep = (xs >= x0) & (xs <= x1)
    ky = np.abs(ys) <= BLEND_Y
    C = np.where(Z > -900.0, C, -1e3)
    C, Z = np.maximum(C[keep][:, ky], level), np.maximum(Z[keep][:, ky], level)
    fill = heightfield_solid(xs[keep], ys[ky], C, level) ^ K.box(-BIG, BIG, -BIG, BIG, level + 1.01, BIG)
    fill = fill.simplify(0.02)                   # the 0.3 mm grid makes a very dense mesh: thin it
    print(f"{'under' if under else 'top'} blend: {(fill - solid).volume() / 1000:.2f} cm3 added, "
          f"deepest fill {float((C - Z).max()):.2f} mm")
    return fill.rotate([180, 0, 0]) if under else fill


@cached
def raw_airframe():
    """Body, wings, intake fairings and jet pipes as one solid, before blending and cuts."""
    pipes, _ = jet_pipes()
    half = wing() + intake_fairing() + pipes
    return union([body(), keel(), canopy(), blister(), half, mirror_y(half)])


@cached
def airframe():
    """Everything but the fin and the probe, as one solid."""
    _, bores = jet_pipes()
    cuts = intake_ducts() + bores + intake_gap()
    return (raw_airframe() + surface_blend(False) + surface_blend(True)) - cuts - mirror_y(cuts)


# ============================================================
# PARTS
# ============================================================


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


def _grooves(lines, w, sides=(1, -1)):
    """Prism through all z along the polylines (given as (x, y)), both sides of the aircraft."""
    secs = []
    for ln in lines:
        for a, b in zip(ln, ln[1:]):
            for sgn in sides:
                secs.append(K.band((a[0], sgn * a[1]), (b[0], sgn * b[1]), w))
    return K.prism_z(mf.CrossSection.batch_boolean(secs, mf.OpType.Add))


@cached
def top_grooves():
    return _grooves(PANEL_LINES, LINE_W), _grooves(HINGE_LINES, HINGE_W)


def engrave_top(part):
    """Cut the upper-surface panel lines into an upper shell: each groove is the part of its
    prism within the line's depth of the surface, measured straight down."""
    lines, hinges = top_grooves()
    cut = (lines ^ (part - part.translate([0, 0, -LINE_D]))) + (hinges ^ (part - part.translate([0, 0, -HINGE_D])))
    return part - cut


@cached
def under_grooves():
    lines = _grooves(UNDER_LINES, LINE_W) + _grooves(UNDER_STBD, LINE_W, sides=(1,))
    return lines, _grooves(UNDER_DOORS + HINGE_LINES, HINGE_W)


def engrave_under(part):
    """The same for a lower shell: grooves within the line's depth of the underside."""
    lines, doors = under_grooves()
    cut = (lines ^ (part - part.translate([0, 0, LINE_D]))) + (doors ^ (part - part.translate([0, 0, HINGE_D])))
    return part - cut


def flip(m):
    """Turn a lower shell over (a rotation about X: never a mirror)."""
    return m.rotate([180, 0, 0])


def _bay_cut(shell, outline, z_ledge, z_roof, side=1, ledge_w=BAY_LEDGE_W):
    """(shell with the bay cut, the door panel) for one bay."""
    sec = K.cs([[(x, side * y) for x, y in outline]])
    lo = K.box(-BIG, BIG, -BIG, BIG, -BIG, z_ledge)
    opening = K.prism_z(sec) ^ lo
    cavity = K.prism_z(sec.offset(-ledge_w, mf.JoinType.Miter, 2.0)) ^ K.box(-BIG, BIG, -BIG, BIG, -BIG, z_roof)
    door = shell ^ K.prism_z(sec.offset(-FIT, mf.JoinType.Miter, 2.0)) ^ lo
    return shell - opening - cavity, door


def _open_frame(shell, outline, z_ledge, ledge_w, side, door_edges, drop):
    """Gear-down insert for a bay: the rim that sits on the ledge (cut from the shell's skin, like
    the closed door) with the open doors standing down from it. door_edges: [((x, y), (x, y)), ...]
    along the outline; drop: how far they hang below the ledge."""
    sec = K.cs([[(x, side * y) for x, y in outline]])
    lo = K.box(-BIG, BIG, -BIG, BIG, -BIG, z_ledge)
    outer, inner = sec.offset(-FIT, mf.JoinType.Miter, 2.0), sec.offset(-ledge_w - 0.3, mf.JoinType.Miter, 2.0)
    rim = shell ^ K.prism_z(outer - inner) ^ lo
    doors = []
    for a, b in door_edges:
        band = K.band((a[0], side * a[1]), (b[0], side * b[1]), DOOR_T)
        doors.append(K.prism_z(band ^ outer) ^ K.box(-BIG, BIG, -BIG, BIG, z_ledge - drop, z_ledge))
    return rim + union(doors) if len(doors) > 1 else rim + doors[0]


def _plate_xz(polys, y0, y1):
    """Plate between y0 and y1 with the (x, z) outline(s) given."""
    sec = mf.CrossSection.batch_boolean([K.cs([p]) for p in polys], mf.OpType.Add)
    return sec.extrude(y1 - y0).rotate([90, 0, 0]).translate([0, y1, 0])


def _bar(p0, p1, w):
    d = np.subtract(p1, p0); n = np.array([-d[1], d[0]]) / np.linalg.norm(d) * w / 2
    return [tuple(np.add(p0, -n)), tuple(np.add(p1, -n)), tuple(np.add(p1, n)), tuple(np.add(p0, n))]


def gear_halves(g, side=1):
    """(half a, half b, socket) of a leg in the assembled frame; a is the half on the +y side of the
    leg's centre plane. side -1 gives the port leg."""
    yc = g["yc"]
    polys = [g["leg"]] + [_bar(p0, p1, STRUT_W) for p0, p1 in g["struts"]]
    plate = _plate_xz(polys, yc, yc + GEAR_T / 2)
    wheel = revolve_x(g["wheel_profile"]).rotate([0, 0, 90])               # axle along +y from the split
    centres = g.get("wheels") or [g["wheel"]]
    a = plate + union([wheel.translate([x, yc, z]) for x, z in centres] + [plate])
    b = a.mirror([0, 1, 0]).translate([0, 2 * yc, 0])
    f = GEAR_PLUG_FIT
    x0, x1 = g["plug"]
    socket = K.box(x0 - f, x1 + f, yc - GEAR_T / 2 - f, yc + GEAR_T / 2 + f, -30.0, GEAR_PLUG_TOP + 0.4)
    if side < 0:
        a, b, socket = (m.mirror([0, 1, 0]) for m in (b, a, socket))
    return a, b, socket


def gear_sockets():
    return union([gear_halves(NOSE_GEAR)[2], gear_halves(MAIN_GEAR, 1)[2], gear_halves(MAIN_GEAR, -1)[2]])


def blue_steel():
    """(the missile half, its slots' keys to add to the bomb door panel)."""
    x0 = BS_X[0]
    body = revolve_x([(x0 + d, r) for d, r in BS_PROFILE]).translate([0, 0, BS_Z])
    flats = []
    for outline in (BS_WING, BS_FORE):
        for sgn in (1, -1):
            flats.append(K.cs([[(x0 + d, sgn * y) for d, y in outline]]))
    wings = mf.CrossSection.batch_boolean(flats, mf.OpType.Add).extrude(BS_WING_T).translate([0, 0, BS_Z - BS_WING_T])
    kl, kw, kh = BS_KEYS[1]
    keys = union([K.box(x - kl / 2, x + kl / 2, -kw / 2, kw / 2, BS_Z - kh, BS_Z + 1.0) for x in BS_KEYS[0]])
    slots = union([K.box(x - kl / 2 - FIT, x + kl / 2 + FIT, -kw / 2 - FIT, kw / 2 + FIT, BS_Z - kh - 0.4, BS_Z + 1.0)
                   for x in BS_KEYS[0]])
    half = ((body + wings) ^ K.box(-BIG, BIG, -BIG, BIG, -BIG, BS_Z)) - slots
    return half, keys


def stand_parts():
    """(post, plinth, key hole for the door and roof, plinth's print pose), assembled frame."""
    th = math.radians(STAND_PITCH)
    d, n = np.array([math.cos(th), math.sin(th)]), np.array([-math.sin(th), math.cos(th)])   # along / up from the plinth, (x, z)
    k = STAND_KEY / 2
    belly = WING_UNDER_Z
    foot = np.array([STAND_X + STAND_SWEEP, belly - STAND_HEIGHT])
    w0, w1 = STAND_SHOULDER[0] / 2, STAND_SHOULDER[1] / 2
    tl, td = STAND_TENON
    outline = [(STAND_X - k, SPLIT_Z - 0.3), (STAND_X + k, SPLIT_Z - 0.3), (STAND_X + k, belly - 0.3),
               (STAND_X + w0, belly - 0.3), tuple(foot + w1 * d), tuple(foot + tl / 2 * d),
               tuple(foot + tl / 2 * d - td * n), tuple(foot - tl / 2 * d - td * n), tuple(foot - tl / 2 * d),
               tuple(foot - w1 * d), (STAND_X - w0, belly - 0.3), (STAND_X - k, belly - 0.3)]
    post = _plate_xz([outline], -k, k)
    hole = K.box(STAND_X - k - FIT, STAND_X + k + FIT, -k - FIT, k + FIT, belly - 1.0, SPLIT_Z + 0.01)
    L, W, T, R = STAND_BASE
    sec = K.cs([[(-L / 2 + R, -W / 2 + R), (L / 2 - R, -W / 2 + R), (L / 2 - R, W / 2 - R), (-L / 2 + R, W / 2 - R)]]).offset(R, mf.JoinType.Round, 2.0, 48)
    slab = sec.extrude(T).translate([STAND_BASE_DX, 0, -T])
    slot = K.box(-tl / 2 - FIT, tl / 2 + FIT, -k - FIT, k + FIT, -td - 0.4, 1.0)
    local = slab - slot

    def place(m):
        return m.rotate([0, -STAND_PITCH, 0]).translate([foot[0], 0, foot[1]])

    def unplace(m):
        return m.translate([-foot[0], 0, -foot[1]]).rotate([0, STAND_PITCH, 0])
    return post, place(local), hole, unplace


def key_plate(length, height, t):
    """A key lying flat (length x height on the bed), its insertion ends chamfered."""
    c = 0.5 * _P
    a = mf.CrossSection.square([length, height - 2 * c], True)
    b = mf.CrossSection.square([length - 2 * c, height], True)
    return mf.CrossSection.batch_boolean([a, b], mf.OpType.Add).hull().extrude(t)


def add_joints(parts):
    """Cut the key slots, the radome tongue and socket, the probe hole and the fin slot, and add the
    keys and fin halves to parts."""
    def solid(prefix, sgn):
        names = [n for n in parts if n.startswith(prefix) and n.endswith(("_upper", "_lower"))
                 and (prefix != "wing" or ("stbd" in n) == (sgn > 0))]
        return names

    sizes = {}
    for prefixes, (x, y0), direction, length in KEYS:
        for sgn in ((1, -1) if y0 else (1,)):
            y = sgn * y0
            names = [n for pf in prefixes for n in solid(pf, sgn)]
            whole = union([parts[n][0] for n in names])
            hx, hy = (length / 2, KEY_T / 2) if direction == "x" else (KEY_T / 2, length / 2)
            zs = split_z(y)
            for h in KEY_H:
                probe_box = K.box(x - hx - KEY_WALL, x + hx + KEY_WALL, y - hy - KEY_WALL, y + hy + KEY_WALL,
                                  zs - h - KEY_GAP - KEY_WALL, zs + h + KEY_GAP + KEY_WALL)
                if (probe_box ^ whole).volume() > 0.997 * probe_box.volume():
                    break
            else:
                print(f"!! no room for a key at ({x:.0f}, {y:.0f}) in {prefixes}")
                continue
            ex, ey = (0.15 * _P, KEY_FIT) if direction == "x" else (KEY_FIT, 0.15 * _P)
            slot = K.box(x - hx - ex, x + hx + ex, y - hy - ey, y + hy + ey, zs - h - KEY_GAP, zs + h + KEY_GAP)
            for n in names:
                parts[n] = (parts[n][0] - slot, parts[n][1])
            sizes.setdefault((round(length * PRINT_K, 1), round(2 * h * PRINT_K, 1)), []).append((x, y))
    n_keys = 0
    for (lp, hp), where in sorted(sizes.items()):
        for i in range(len(where)):
            parts[f"key_{lp:g}x{hp:g}_{i + 1}"] = (key_plate(lp * _P, hp * _P, KEY_T), lambda m: m)
            n_keys += 1
    print(f"keys: {n_keys} in {len(sizes)} sizes (length x height, printed): "
          + ", ".join(f"{len(w)} of {lp:g} x {hp:g}" for (lp, hp), w in sorted(sizes.items())))

    # radome: a tongue on the front shells (half on each, lying on the split plane) into a socket
    tl, tw, th = RADOME_TONGUE
    tongue = K.box(RADOME_X - tl, RADOME_X + 1.0, -tw, tw, SPLIT_Z - th, SPLIT_Z + th)
    socket = K.box(RADOME_X - tl - 0.5, RADOME_X + 0.01, -tw - FIT, tw + FIT, SPLIT_Z - th - FIT, SPLIT_Z + th + FIT)
    up = above_split(0)
    parts["front_upper"] = (parts["front_upper"][0] + (tongue ^ up), parts["front_upper"][1])
    parts["front_lower"] = (parts["front_lower"][0] + (tongue - up), parts["front_lower"][1])
    rod, hole = probe()
    parts["radome"] = (parts["radome"][0] - socket - hole, parts["radome"][1])
    parts["probe"] = (rod, lambda m: m)

    # fin: two halves printed on their split faces; the root sits in a slot of its own shape
    f = fin()
    grown = union([f.translate([dx, dy, 0]) for dx in (-FIN_FIT, FIN_FIT) for dy in (-FIN_FIT, FIN_FIT)]
                  + [f.translate([0, 0, -0.3])])
    parts["centre_upper"] = (parts["centre_upper"][0] - grown, parts["centre_upper"][1])
    half = K.box(-BIG, BIG, 0.0, BIG, -BIG, BIG)
    parts["fin_stbd"] = (f ^ half, lambda m: m.rotate([90, 0, 0]))
    parts["fin_port"] = (f - half, lambda m: m.rotate([-90, 0, 0]))


def bomb_roof():
    """(recess in the centre lower shell's top face, the ribbed roof plate that drops into it)."""
    t, margin, pitch, rw, rd = BOMB_ROOF
    _, outline, _, z_roof, _, _ = BAYS["bomb"]
    sec = K.cs([outline])

    def wedge(grow, top):
        """Slab from SPLIT_Z - t up to `top`, its edges sloping in at 45 degrees going down, so the
        recess has no ledge over the bed when the shell prints turned over."""
        a = K.prism_z(sec.offset(margin + grow, mf.JoinType.Miter, 2.0)) ^ K.box(-BIG, BIG, -BIG, BIG, SPLIT_Z - 0.02, top)
        b = K.prism_z(sec.offset(margin + grow - t, mf.JoinType.Miter, 2.0)) ^ K.box(-BIG, BIG, -BIG, BIG, SPLIT_Z - t, SPLIT_Z - t + 0.02)
        return (a + b).hull()
    recess = wedge(0.0, SPLIT_Z + 0.01)
    plate = wedge(-FIT, SPLIT_Z)
    x0, x1 = outline[0][0], outline[2][0]
    yh = outline[1][1] - BAY_LEDGE_W - 0.6
    ribs = union([K.box(x - rw / 2, x + rw / 2, -yh, yh, SPLIT_Z - t - rd, SPLIT_Z - t + 0.5)
                  for x in np.arange(x0 + pitch / 2, x1 - 1.0, pitch)]
                 + [K.box(x0 + 3, x1 - 3, -rw / 2, rw / 2, SPLIT_Z - t - rd, SPLIT_Z - t + 0.5)])
    return recess, plate + ribs


def build():
    """Returns {name: (Manifold in the assembled frame, pose function -> print pose)}."""
    a = airframe() - fin()
    sockets = gear_sockets()
    parts = {"radome": (a ^ region("radome"),
                        lambda m: m.rotate([0, 90, 0]))}             # on end, on its joint face
    for name, side in (("front", 0), ("centre", 0), ("wing_stbd", 1), ("wing_port", -1)):
        blk = a ^ region(name)
        up = above_split(side)
        level = (lambda m, s=side: rot_x(m, s * SPLIT_TILT, s * WING_JOINT_Y, SPLIT_Z)) if side else (lambda m: m)
        upper = blk ^ up
        if name != "front":
            upper = engrave_top(upper) - sockets
        parts[f"{name}_upper"] = (upper, level)
        lower = engrave_under(blk - up)
        under_pose = lambda m, lv=level: flip(lv(m))
        for bay, (where, outline, z_ledge, z_roof, both, ledge_w) in BAYS.items():
            if not name.startswith(where) or (side < 0 and not both):
                continue
            sfx = "" if not both else ("_stbd" if side > 0 else "_port")
            if side:                             # wing bays are cut square to the wing's own split plane
                unlevel = lambda m, s=side: rot_x(m, -s * SPLIT_TILT, s * WING_JOINT_Y, SPLIT_Z)
                whole = level(lower)
                x0, x1, drop = MAIN_DOOR
                edge = [((x0, 71 + (x0 - 204) / 7.0), (x1, 71 + (x1 - 204) / 7.0))]     # along the outboard edge
                frame = unlevel(_open_frame(whole, outline, z_ledge, ledge_w, side, [((a[0], a[1] - 1.0), (b[0], b[1] - 1.0)) for a, b in edge], drop))
                lower, door = (unlevel(m) for m in _bay_cut(whole, outline, z_ledge, z_roof, side, ledge_w))
                parts[f"doors_open_{bay}{sfx}"] = (frame, under_pose)
            else:
                if bay == "nose":
                    x0, x1, drop = NOSE_DOORS
                    yd = outline[1][1] - 1.0
                    parts["doors_open_nose"] = (_open_frame(lower, outline, z_ledge, ledge_w, 1,
                                                            [((x0, yd), (x1, yd)), ((x0, -yd), (x1, -yd))], drop), under_pose)
                lower, door = _bay_cut(lower, outline, z_ledge, z_roof, 1, ledge_w)
            parts[f"door_{bay}{sfx}"] = (door, under_pose)
            if bay == "bomb":
                missile, keys = blue_steel()
                parts["door_bluesteel"] = (door + (keys ^ K.box(-BIG, BIG, -BIG, BIG, -BIG, z_ledge)), under_pose)
                parts["blue_steel"] = (missile, flip)
        lower = lower - sockets
        if name == "centre":
            recess, roof = bomb_roof()
            lower = lower - recess
            post, plinth, hole, unplace = stand_parts()
            parts["bomb_bay_roof"] = (roof - hole, flip)
            parts["door_bomb_stand"] = (parts["door_bomb"][0] - hole, under_pose)
            parts["stand_post"] = (post, lambda m: m.rotate([90, 0, 0]))
            parts["stand_base"] = (plinth, unplace)
        parts[f"{name}_lower"] = (lower, under_pose)
    for tag, g, sd in (("nose_gear", NOSE_GEAR, 1), ("main_gear_stbd", MAIN_GEAR, 1), ("main_gear_port", MAIN_GEAR, -1)):
        ha, hb, _ = gear_halves(g, sd)
        parts[f"{tag}_a"] = (ha, lambda m: m.rotate([90, 0, 0]))       # +y half: split face down
        parts[f"{tag}_b"] = (hb, lambda m: m.rotate([-90, 0, 0]))
    add_engines(parts)
    add_joints(parts)
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
