"""
Colour the Hawk kit (Red Arrows) and write a multi-colour Bambu Studio 3MF.

Run:  python colour.py OUT_DIR [project_settings_template.json]   (default: cad/bambu_x2d_project_settings.json)
      ONLY=name,name python colour.py OUT_DIR      (just some parts)

Scheme: Red Arrows Hawk T.1A, current Union-flag fin (traced from close-up photos of each side, v14).
  - Fuselage sections print red, on end. The white cheat line, tail swoosh, belly stripes,
    "ROYAL AIR FORCE" and the roundels are painted into the skin (multi-colour, no inlays).
    The lettering is regenerated as text; the stripes are drawn from lines fitted to the
    Revell 04284 views (hawk/tools/white_regions.py, kept in ref/hawk_white/, not in git).
  - Wings print flat: the white underside chevrons and the lower roundels are in the bottom
    skin (first layers), the upper roundels in the top skin.
  - Fin halves print flat: the traced white swoosh and Union flag in the outer skin.
  - Canopy opaque with black frames, no red; gear grey with black tyres.
Everything is built at 1:40 (the shape's measuring scale) and scaled by H.PRINT_K to 1:32
when written out.
"""
import json
import math
import os
import sys
from pathlib import Path

import manifold3d as mf
import numpy as np

import detail as D
import hawk as H
import kitlib as K
from kitlib import clip, cs, mesh_of, prism_y, prism_z, text_section

ROOT = Path(__file__).resolve().parents[2]

# ============================================================
# PARAMETERS
# ============================================================
SKIN = 0.8                   # mm at 1:40 (1.0 printed), coloured skin depth
UNDER_SKIN = 0.36            # wing underside paint (0.45 printed, ~2 layers): the wing is
                             # under 1 mm thick near the trailing edge, so a full SKIN came through
TOP_CLEAR = 0.4              # ...and it never comes within this of the top surface (2 red layers)
FIN_SKIN = 0.6               # the fin halves are thin
SKIN_OUT = 0.05              # skins reach just past the surface (no zero-thickness slivers)
LETTER_BOLD = 0.15           # mm, letters grown (thicker strokes print better)
STRIPE_MIN_W = 1.0           # mm at 1:40 (1.25 printed), stripes are widened to at least this

FILAMENTS = {
    1: ("Red", "#C8102E"),
    2: ("White", "#F2F2F2"),
    3: ("Blue", "#1F2D6B"),
    4: ("Black", "#1C1C1C"),
    5: ("Canopy", "#3B4652"),     # opaque: load any canopy colour (smoke grey, dark blue...)
    6: ("Grey", "#8C9096"),
}
RED, WHITE, BLUE, BLACK, CANOPY, GREY = range(1, 7)
FILAMENT_MAP = {RED: 1, WHITE: 2, BLUE: 1, BLACK: 1, CANOPY: 1, GREY: 1}
                             # X2D nozzle per filament on the red plates: the base red on the main
                             # nozzle (200 mm/s outer walls), white on the second (50 mm/s). "Auto"
                             # once put red on the second nozzle (+4 h). Other plates stay on Auto:
                             # with 4-5 colours one fixed map makes them swap on every layer
MAPPED_PLATES = ("Fuselage", "Tailplanes and small parts", "Wing tops", "Wing undersides")
ROUNDEL = lambda d: [(BLUE, d), (WHITE, d * 2 / 3), (RED, d / 3)]

FUSE_ROUNDEL = (185.0, 4.6, 10.6)        # x, z, diameter: level with the lettering and just behind
                                         # its last letter (side photos)
WING_ROUNDEL = (162.2, 94.8, 15.0)       # x, |y|, diameter (Revell top view)
LETTERS = ("ROYAL AIR FORCE", 143.8, 4.6, 61.0, 5.2)   # text, x centre, z centre, length, height:
                                                         # half way up the side pod (photos), so the cheat
                                                         # line runs nearly level from the nose
# Cheat line (photos): thin at the nose, thickening to the lettering's height on the side pod,
# broken for "ROYAL AIR FORCE", resumed behind the roundel and swept up onto the fin in one curve.
CHEAT_NOSE = (1.8, 1.75, 1.1)      # x, lower edge z, width at the nose tip: the band starts right
                                   # at the tip, just above the probe boss, so the two sides join
                                   # across the front of the nose (head-on photo)
CHEAT_POD_X = 95.0                 # full letter height reached here (on the pod)
CHEAT_GAP = 2.0                    # mm of red between the band and the lettering
# Where the swoosh meets the fin flag, per side (+1 starboard, -1 port): x, z of its centre line,
# direction, width there. Set so that at the seam (FIN_FLAG_ABOVE over the fuselage line) it
# covers exactly the flag's white in front of the small blue triangle, with the white's edge angle
# (v17 trace from the clean reference renders, 0.6 mm over the fuselage line: port X 219.3-229.5,
# starboard X 221.8-231.4).
# The flag is mirrored, so its white sits differently on each side. Re-measure after re-tracing
# the flag (intersect both with lines just above the fuselage line).
SWOOSH_TOP = {-1: (223.49, 25.0, 0.482, 0.876, 8.94),
              +1: (225.88, 25.0, 0.447, 0.894, 8.59)}
SWOOSH_UP = 0.8                    # the swoosh runs this far above the flag's lower edge, under its
                                   # ragged traced base (the flag paints over it)
FLAG_TE_FILL = 1.0                 # mm: the flag is carried aft up to the trailing edge over gaps this
                                   # wide (the trace loses the drawing's outline line there)
FLAG_TE_FILL_FROM = 4.0            # ...but only from this far above the kink corner up
FLAG_MIN_ISLAND = 10.0             # mm2: smaller separate white/blue islands in the photo trace are
                                   # watermarks or specks (the real flag's pieces are all larger)
FLAG_BASE_FILL = 0.8               # mm: colours carried down over the ragged traced base...
FLAG_BASE_X1 = {-1: 241.8, 1: 240.1}   # ...ahead of this x, where the red diagonal reaches the root
RUDDER_FOOT_X = {-1: 242.3, 1: 240.5}  # the rudder's bottom edge runs forward from the TE's kink
                                   # corner to here (photos: 8.7 mm port, 10.5 mm starboard); red below
FLAG_EDGE_SMOOTH = 5               # traced outlines are smoothed over this many vertices (~1.5 mm)


def smooth_ring(r):
    """Soften a traced outline: a closed weighted moving average over FLAG_EDGE_SMOOTH vertices
    (vertices are ~0.3 mm apart). Removes the trace's pixel steps and the photo's wobble."""
    n = FLAG_EDGE_SMOOTH // 2
    w = np.r_[np.arange(1, n + 2), np.arange(n, 0, -1)].astype(float)
    w /= w.sum()
    out = np.zeros_like(r)
    for i, wi in enumerate(w):
        out += wi * np.roll(r, i - n, axis=0)
    return out
FIN_FLAG_ABOVE = 0.4               # mm above the fuselage top line where the fin flag starts
WHITE_DIR = ROOT / "ref" / "hawk_white"

BED = (168.0, 236.0)         # packing area, x from BED_MARGIN: x > 190 is left for the prime tower
BED_MARGIN = (22.0, 10.0)    # the X2D's right nozzle can't reach x < 20.5, and brims need room
PLATE_GAP = 8.0

# ============================================================
# WHITE AREAS FROM THE DRAWINGS
# ============================================================
def rings(view):
    p = WHITE_DIR / f"{view}.json"
    if not p.exists():
        raise SystemExit(f"missing {p}: run hawk/tools/white_regions.py {view} {p}")
    return [np.array(r) for r in json.load(open(p))["rings"]]


def close(sec, r):
    return sec.offset(r, mf.JoinType.Round).offset(-r, mf.JoinType.Round)


def _ribbon(c, w):
    """Band along a centreline c (N, 2) with widths w (N): its outline as one polygon."""
    t = np.gradient(c, axis=0)
    t /= np.linalg.norm(t, axis=1)[:, None]
    nrm = np.c_[-t[:, 1], t[:, 0]] * (np.asarray(w)[:, None] / 2)
    return cs([np.vstack([c + nrm, (c - nrm)[::-1]])])


def cheat_front():
    """Nose to the lettering: lower edge rising gently, width growing to the letter height."""
    x0, zl0, w0 = CHEAT_NOSE
    _, xc, zc, length, h = LETTERS
    x_end = xc - length / 2 - CHEAT_GAP
    xs = np.linspace(x0, x_end, 140)
    t = np.clip((xs - x0) / (CHEAT_POD_X - x0), 0, 1)
    ease = t * t * (3 - 2 * t) * 0.35 + t * 0.65            # gradual, settling onto the pod
    lo = zl0 + (zc - h / 2 - zl0) * ease
    w = w0 + (h - w0) * ease
    c = np.c_[xs, lo + w / 2]
    return _ribbon(c, w) + mf.CrossSection.circle(w0 / 2, 16).translate([x0, zl0 + w0 / 2])


def cheat_rear(side):
    """From behind the roundel, level at the letter height, then one smooth curve up onto the fin
    (a cubic Bezier into the flag's white at the fin root), widening as it climbs."""
    _, xc, zc, length, h = LETTERS
    rx, rz, rd = FUSE_ROUNDEL
    x3, z3, dx, dz, w3 = SWOOSH_TOP[1 if side > 0 else -1]
    P = np.array([(rx, zc), (rx + 20.0, zc), (x3 - dx * 13.0, z3 - dz * 13.0), (x3, z3)])
    u = np.linspace(0, 1, 120)[:, None]
    c = ((1 - u) ** 3 * P[0] + 3 * (1 - u) ** 2 * u * P[1] + 3 * (1 - u) * u * u * P[2] + u ** 3 * P[3])
    c = np.vstack([c, [x3 + dx * 12.0, z3 + dz * 12.0]])   # runs on past the fin root line (clipped there)
    s = np.clip((np.r_[u[:, 0], 1.0] - 0.3) / 0.7, 0, 1)
    w = h + (w3 - h) * s
    sec = _ribbon(c, w)
    return sec - mf.CrossSection.circle(rd / 2 + 0.6, 64).translate([rx, rz])


def side_stripes(side):
    """White on the fuselage side, (x, z): the cheat line in front of the lettering, and the band
    behind the roundel that sweeps up onto the fin. The cheat line is the same on both sides;
    the swoosh's end differs, to meet each side's flag."""
    return cheat_front() + cheat_rear(side)


def widen(sec, wmin):
    """Grow thin stripes to at least wmin wide (an opening by wmin/2 finds the thin parts)."""
    thick = sec.offset(-wmin / 2 + 0.05, mf.JoinType.Round).offset(wmin / 2 - 0.05, mf.JoinType.Round)
    thin = sec - thick
    return sec + thin.offset(max(0.0, (wmin - 1.2) / 2), mf.JoinType.Round) if not thin.is_empty() else sec


def letters_section(side):
    txt, xc, zc, length, h = LETTERS
    t = text_section(txt, h, 0.0, 0.0, mirror=side > 0)
    x0, z0, x1, z1 = t.bounds()
    t = t.scale([length / (x1 - x0), 1.0]).translate([xc, zc])
    return t.offset(LETTER_BOLD, mf.JoinType.Round)


# Underside white (v17: lines fitted to the clean straight-up reference render
# ref/hawk/renders/ref_under_straight.png, calibrated on the wing's own leading and trailing
# edges, which match the model's planform within 1 mm): on each wing a band from beside the
# centre pod out to the trailing edge, and a narrow strip along the trailing edge from the
# band's tip in to the belly; two stripes along the belly from there to the tail, joined in a U.
CHEVRON_OUT = ((110.0, 17.40), 0.7068)   # outer edge of the band: point (x, |y|), slope d|y|/dx
CHEVRON_IN = ((118.0, 16.27), 0.5095)    # inner edge of the band
CHEVRON_FRONT = (90.6, 3.2)              # the band starts at this x, beside the centre pod (|y|)
TE_STRIP_W = 7.3                         # trailing-edge strip, measured forward from the TE
BELLY_STRIPE = ((-0.0989, 25.62), (-0.0975, 28.64), 255.2)
                                         # belly stripes: inner and outer edge |y| = k x + c, and
                                         # the x of the U that joins them under the jet pipe
BELLY_CORNER_UP = 1.6                    # they wrap this far up the corner
BELLY_REAR_X, BELLY_REAR_UP = 165.0, 7.0  # behind this x the stripes may climb this far above the
                                         # bottom line (the rear belly is rounded; no pods there)
WHITE_WING_FINS = [3]                    # indices into hawk.WING_FINS of fins painted white (the
                                         # one near the leading edge at |y| 39: rear reference render)


def _rect(a0, b0, a1, b1):
    return mf.CrossSection.square([a1 - a0, b1 - b0]).translate([a0, b0])


def _halfplane(pt, slope, below):
    (x0, y0) = pt
    f = lambda x: y0 + slope * (x - x0)
    far = -300.0 if below else 300.0
    return cs([np.array([(40.0, f(40.0)), (300.0, f(300.0)), (300.0, far), (40.0, far)])])


def under_white():
    """White on the underside, (x, y), both sides."""
    (ki, ci), (ko, co), xu = BELLY_STRIPE
    x0, y0 = CHEVRON_FRONT
    outer = _halfplane(*CHEVRON_OUT, True)
    ys = np.linspace(6.0, H.SPAN / 2, 120)
    te = np.array([sum(H.wing_plan(y)[:2]) for y in ys])
    ahead = cs([np.r_[[(40.0, 0.0), (te[0] + 3.0, 0.0)], np.c_[te + 3.0, ys], [(40.0, ys[-1])]]])
    band = outer ^ _halfplane(*CHEVRON_IN, False) ^ _rect(x0, y0, 300.0, 300.0) ^ ahead
    y_in = ki * 170.0 + ci                                   # belly stripe's inner edge at the TE
    strip = cs([np.r_[np.c_[te - TE_STRIP_W, ys], np.c_[te[::-1] + 3.0, ys[::-1]]]]) \
        ^ _rect(100.0, y_in, 300.0, 300.0) ^ outer          # 3.0: past the TE (paint overshoots)
    xs = np.linspace(te[0] - TE_STRIP_W + 0.5, xu, 60)       # from inside the TE strip
    belly = cs([np.r_[np.c_[xs, ki * xs + ci], np.c_[xs[::-1], (ko * xs + co)[::-1]]]])
    cap = _rect(xu - (co - ci + 0.3) - 0.0, 0.0, xu, ko * xu + co)   # the U, as wide as a stripe
    half = band + strip + belly + cap
    return half + half.mirror([0.0, 1.0])


def near_bottom(x0, x1, dz, n=120):
    """Everything below the fuselage's bottom line raised by dz, (x, z) prism through y."""
    xs = np.linspace(x0 - 1.0, x1 + 1.0, n)
    zb = np.array([H.fuse_at(min(max(x, 0.8), H.FUSE_END_X))[3] + dz for x in xs])
    return prism_y(cs([np.r_[[(xs[0], -100.0), (xs[-1], -100.0)], np.c_[xs[::-1], zb[::-1]]]]))


def fuselage_plan(x0, x1, inset=0.0, n=160):
    xs = np.linspace(x0, x1, n)
    hw = np.array([max(H.fuse_at(x)[1] - inset, 0.1) for x in xs])
    return cs([np.r_[np.c_[xs, hw], np.c_[xs[::-1], -hw[::-1]]]])


# ============================================================
# MARKINGS (painted into the outer skin)
# ============================================================
def roundel_ops(x, c, d, axis, region):
    """Roundel rings painted into region (a skin): [(colour, volume)], outer ring first."""
    return [(colour, region ^ K.cyl_axis(x, c, dd / 2, axis)) for colour, dd in ROUNDEL(d)]


def fuselage_markings(P):
    """Paint ops for any fuselage section: cheat line, swoosh, lettering, roundels and belly
    stripes (each lands only where the section has skin). The stripes go right through in y,
    so at the nose tip the band crosses the front, just above the probe boss (head-on photo)."""
    # regions reach past the surface and stop at the inner core: ending them exactly on the
    # surface leaves thin sheets of base red over the paint (LESSONS.md)
    core = K.inner_core(P, SKIN)
    x0, _, _, x1, _, _ = P.bounding_box()
    _, _, _, bd, bl = H.PROBE
    probe = K.box(-60.0, 3.4, -bd / 2 - 0.15, bd / 2 + 0.15, -bd / 2 - 0.15, bd / 2 + 0.15)
    ops = [(WHITE, (prism_y(widen(cheat_front(), STRIPE_MIN_W)) - core) - probe)]
    for side in (1, -1):
        sk = K.box(-50.0, 400.0, 0.0 if side > 0 else -100.0, 100.0 if side > 0 else 0.0, -100.0, 100.0) - core
        ops.append((WHITE, sk ^ prism_y(widen(cheat_rear(side), STRIPE_MIN_W))))   # swoosh: per side
        ops.append((WHITE, sk ^ prism_y(letters_section(side))))
        x, z, d = FUSE_ROUNDEL
        ops += roundel_ops(x, z, d, "y", sk)
    # the bottom and its corners only: near any downward face, but no higher than just above the
    # fuselage's bottom line (the pods' tapering undersides face down too)
    down = (P - P.translate([0, 0, BELLY_CORNER_UP])) - core
    low = down ^ near_bottom(x0, x1, BELLY_CORNER_UP + 0.4)
    if x1 > 150.0:
        # behind the wing the belly stripes wrap up the rounded belly further than the 2 mm
        # band allows (they showed patchy), and there are no pod undersides there to catch
        rear = down ^ near_bottom(x0, x1, BELLY_REAR_UP) ^ K.box(BELLY_REAR_X, 400.0, -100.0, 100.0, -100.0, 100.0)
        ops.append((WHITE, (low + rear) ^ prism_z(under_white() ^ fuselage_plan(max(x0, 150.0), x1, inset=-2.0))))
    if x0 < 162.0 and x1 > 86.0:                       # the stripes' forward run to the pod's nose
        ops.append((WHITE, low ^ prism_z(under_white() ^ fuselage_plan(max(x0, 86.0), min(x1, 162.0), inset=-2.0))))
    return ops


# ============================================================
# PAINT (colour in the skin)
# ============================================================
def skins(P, d=SKIN):
    o = SKIN_OUT
    return {
        "up": P.translate([0, 0, o]) - P.translate([0, 0, -d]),
        "down": P.translate([0, 0, -o]) - P.translate([0, 0, d]),
        "+y": P.translate([0, o, 0]) - P.translate([0, -d, 0]),
        "-y": P.translate([0, -o, 0]) - P.translate([0, d, 0]),
    }


def fin_outline(z0=None):
    (lx0, lz0), (lx1, lz1) = H.FIN_LE
    (tx0, tz0), (tx1, tz1) = H.FIN_TE
    zb = H.FIN_ROOT_Z - 2 if z0 is None else z0
    le = lambda z: lx0 + (z - lz0) * (lx1 - lx0) / (lz1 - lz0)
    te = lambda z: tx0 + (z - tz0) * (tx1 - tx0) / (tz1 - tz0)
    return [(le(zb) - 30, zb), (te(zb) + 3, zb), (te(H.FIN_TOP) + 3, H.FIN_TOP + 2), (le(H.FIN_TOP) - 3, H.FIN_TOP + 2)]


def fin_flag(side):
    """Union-flag fin traced from the clean reference renders of each side (v17; tools/trace_colours.py,
    specs in hawk/tools/fin_flag_*.json, fitted through the trailing edge's top and kink
    corners). Returns [(colour, section)] in (x, z)."""
    from matplotlib.path import Path as MPath
    tag = "stbd" if side > 0 else "port"
    p = WHITE_DIR / f"fin_{tag}.json"
    if not p.exists():
        raise SystemExit(f"missing {p}: run tools/trace_colours.py hawk/tools/fin_flag_{tag}.json {p}")
    cls = json.load(open(p))["classes"]
    secs = []
    for name, colour in (("white", WHITE), ("blue", BLUE)):
        rings = [np.array(r) for r in cls.get(name, [])]
        area = [0.5 * abs(np.dot(r[:, 0], np.roll(r[:, 1], 1)) - np.dot(r[:, 1], np.roll(r[:, 0], 1)))
                for r in rings]
        keep = []
        for i, r in enumerate(rings):
            cx, cz = r.mean(0)
            hole = any(j != i and area[j] > area[i] and MPath(rings[j]).contains_point(r[0])
                       for j in range(len(rings)))
            # islands under FLAG_MIN_ISLAND mm2 are photo watermarks and specks; holes (red
            # cut-outs in the white) stay. Also drop anything on the fuselage ahead of the fin.
            if (not hole and area[i] < FLAG_MIN_ISLAND) or area[i] < 0.5 or (cx < 212.0 and cz < 32.0):
                continue
            keep.append(smooth_ring(r))
        if keep:
            secs.append((colour, cs(keep) ^ fin_surface()))
    # Carry each colour straight aft (x only) over the thin red gaps the trace leaves along the
    # trailing edge, but only into what would otherwise be red, and only near the edge. Then clip
    # the whole flag to the straight trailing-edge line: the angled piece below the kink, which
    # sweeps back over the jet pipe, stays red (photos). No fill near the kink: there the flag's
    # red diagonal meets the fin's bottom edge and runs on into the red below, and sweeping the
    # white strip above it aft would push white down over it.
    (tx0, tz0), (tx1, tz1) = H.FIN_TE
    te = lambda z: tx0 + (z - tz0) * (tx1 - tx0) / (tz1 - tz0)
    zk = H.FIN_TE_KINK[0][1] + FLAG_TE_FILL_FROM
    near_te = cs([np.array([(te(zk) - FLAG_TE_FILL - 0.3, zk), (te(zk) + 3.0, zk),
                            (te(90.0) + 3.0, 90.0), (te(90.0) - FLAG_TE_FILL - 0.3, 90.0)])])
    ahead_te = cs([np.array([(150.0, 0.0), (te(0.0) + 0.3, 0.0), (te(120.0) + 0.3, 120.0),
                             (150.0, 120.0)])])        # 0.3: through the trailing-edge face itself
    # The photo's flag base is ragged just above the fuselage line: carry the colours straight
    # down over it (z only, into red only), ahead of where the red diagonal reaches the root.
    d, x1 = FLAG_BASE_FILL, FLAG_BASE_X1[1 if side > 0 else -1]
    base = (above_fuselage(FIN_FLAG_ABOVE - 0.3) - above_fuselage(FIN_FLAG_ABOVE + d + 0.3)) \
        ^ cs([np.array([(150.0, 0.0), (x1, 0.0), (x1, 120.0), (150.0, 120.0)])])
    # Below the rudder's bottom edge (level with the kink corner, running forward from the
    # trailing edge) the photos show the red fairing: no flag there.
    xf = RUDDER_FOOT_X[1 if side > 0 else -1]
    zf = H.FIN_TE_KINK[0][1]
    foot = cs([np.array([(xf, 0.0), (300.0, 0.0), (300.0, zf), (xf, zf)])])
    taken = None
    for _, sec in secs:
        taken = sec if taken is None else taken + sec
    ops = []
    for colour, sec in secs:
        sweep = sec
        for k in range(1, 6):
            sweep = sweep + sec.translate([FLAG_TE_FILL * k / 5, 0.0])
        add = (sweep ^ near_te) - taken
        taken = taken + add
        down = sec
        for k in range(1, 5):
            down = down + sec.translate([0.0, -d * k / 4])
        add2 = (down ^ base) - taken
        taken = taken + add2
        sec = sec - foot
        add, add2 = add - foot, add2 - foot
        ops.append((colour, (sec + add + add2) ^ ahead_te))
    return ops


def above_fuselage(off, x0=170.0, x1=270.0):
    """(x, z) region above the fuselage top line, raised by off."""
    xs = np.linspace(x0, x1, 120)
    line = [(x, H.fuse_at(x)[2] + off) for x in xs]
    return cs([np.array(line + [(x1, 120.0), (x0, 120.0)])])


def fin_surface():
    """Where the fin itself shows: above the fuselage line and behind the fin's straight leading
    edge. The flag stays off the spine cap and the red dorsal fillet."""
    (lx0, lz0), (lx1, lz1) = H.FIN_LE
    k = (lx1 - lx0) / (lz1 - lz0)
    le = lambda z: lx0 + (z - lz0) * k + 0.8
    behind = cs([np.array([(le(0.0), 0.0), (300.0, 0.0), (300.0, 120.0), (le(120.0), 120.0)])])
    return above_fuselage(FIN_FLAG_ABOVE) ^ behind


def paint(P, ops, base=RED):
    return K.paint(P, ops, base)


CANOPY_FRAMES_X = [(58.0, 1.3, -24.0, RED),     # windscreen arch: x at the sill, width, lean (deg,
                                                  # + = top aft), colour. v17: a slim tube leaning
                                                  # forward at the top (reference renders: ~1.3 mm)
                   (75.7, 3.6, 35.0, WHITE)]      # hoop between the cockpits: v17 from the long-shot
                                                  # side render, 3.6 mm thick, centred at X 75.7 at the
                                                  # sill and leaning back 35 deg (was 2.0 at X 84, 19 deg)
CANOPY_REAR_FRAME = 1.8                           # mm, frame along the slanted rear edge
CANOPY_SILL = 0.9                                 # mm of black along the canopy's bottom edge
                                                  # (the red nose dome is hawk.nose_dome, on the fuselage)


_WING_DET = {}
P_plain = {}                 # part name -> the part before detail.apply (panel lines, hinges)


def wing_detailed(side):
    """The whole wing with its panel lines (gear socket, key slot and pin holes filled)."""
    if side not in _WING_DET:
        _WING_DET[side] = D.apply("wing_stbd" if side > 0 else "wing_port", H.wing_outer(side))
    return _WING_DET[side]


def colour_part(name, P):
    if name.startswith(("wingtop_", "wingbot_")):
        side = 1 if name.endswith("stbd") else -1
        # skins from the whole wing before its panel and hinge grooves are cut (no split face, no
        # sockets): the paint fills the grooves, so they don't cut red lines through the white
        whole = H.wing_outer(side)
        S = skins(whole)
        x, y, d = WING_ROUNDEL
        y *= side
        if name.startswith("wingtop_"):
            return paint(P, roundel_ops(x, y, d, "z", S["up"]))
        uw = under_white()
        # line the gear socket and wheel-well recess in the colour around them: inside the lower
        # half only (its split face is hidden), so they don't show as red squares in the white
        holes = (H.main_socket(side) + H.gear_bay(side)).project().offset(0.6, mf.JoinType.Round)
        lining = prism_z(holes ^ uw)
        ops = [(WHITE, (S["down"] + lining) ^ prism_z(uw))]
        for i in WHITE_WING_FINS:                           # fins painted white all over
            eta, f0, f1, _ = H.WING_FINS[i]
            yy = eta * H.SPAN / 2
            le, c, _ = H.wing_plan(yy)
            blk = H.wing_flat_to_assembled(H.box(le + f0 * c - 1.0, le + f1 * c + 1.0, yy - 1.5, yy + 1.5,
                                                 -40.0, 40.0), side)
            ops.append((WHITE, blk - H.wing_assembled(side)))
        return paint(P, ops + roundel_ops(x, y, d, "z", S["down"]))
    if name.startswith("fin_"):
        # skins from the fin half before its hinge and panel grooves are cut: the paint then
        # fills the grooves (their walls and floor), so a groove through the flag doesn't show
        # as a line of bare red
        S = skins(P_plain.get(name, P), FIN_SKIN)
        side = S["+y"] if name.endswith("stbd") else S["-y"]
        # the swoosh runs up to the fin root line, where the flag's white takes over
        sw = (side_stripes(1 if name.endswith("stbd") else -1)
              ^ cs([np.array([(176, H.FIN_ROOT_Z - 1), (240, H.FIN_ROOT_Z - 1), (240, 60.0), (176, 60.0)])])
              ) - above_fuselage(FIN_FLAG_ABOVE + SWOOSH_UP)
        ops = [(WHITE, side ^ prism_y(sw))]
        for colour, sec in fin_flag(1 if name.endswith("stbd") else -1):
            ops.append((colour, side ^ prism_y(sec)))
        return paint(P, ops)
    if name == "canopy":
        # Opaque canopy colour with the red windscreen arch and the white hoop. No black frame
        # (v7: the sill line and rear frame cost a colour swap on most layers with the canopy
        # printed standing on its rear face). The part is cut above the sill: no fuselage red.
        shell = P - K.inner_core(P, 0.7)
        hoops = [(c, shell ^ H.rot_about(K.slab("x", x, w), (x, 0.0, H.canopy_sill_z(x)), "y", a))
                 for x, w, a, c in CANOPY_FRAMES_X]
        return paint(P, hoops, base=CANOPY)
    if name.startswith("fuselage_"):
        # markings measured from the section before its panel lines are cut, so the paint fills
        # the grooves (the belly stripes showed broken where panel and door lines crossed them)
        return paint(P, fuselage_markings(P_plain.get(name, P)))
    if name == "nozzle":
        # grey metal outside and on the rim, black inside the void
        n = H.NOZZLE
        inside = H.cyl((H.FUSE_END_X - 10.0, 0, H.JET_PIPE[2]), 2 * (n["r"] - n["wall"] + 0.5), 20.0, "x", 96)   # black lining 0.6 mm printed
        return paint(P, [(BLACK, inside)], base=GREY)
    if name.startswith("wheel_"):
        x0, y0, z0, x1, y1, z1 = P.bounding_box()
        c = ((x0 + x1) / 2, (z0 + z1) / 2)
        d = x1 - x0
        hub = K.cyl_axis(c[0], c[1], d * 0.31, "y")
        return paint(P, [(GREY, hub)], base=BLACK)
    if name.startswith(("gear_", "pin_")):
        return {GREY: P}
    if name == "stand_base":
        return stand_paint(P)
    if name == "stand_post":
        return {BLACK: P}
    return {RED: P}


# ============================================================
# DISPLAY STAND (black plinth, raised white lettering, red/white/blue pinstripe)
# ============================================================
STAND_LINES = [("RED ARROWS", 8.0), ("BAE SYSTEMS HAWK T.1A", 5.0), ("ROYAL AIR FORCE AEROBATIC TEAM", 3.6)]
STAND_TEXT = (11.0, 2.6, 64.0, -16.0)   # last line's distance from the front edge, line gap, max line
                                         # length, centre x from the plinth centre (clear of the blade boss)
STAND_RELIEF = 0.6


def stand_level(m, sign=1):
    return H.rot_about(m, STAND_PIV, "y", sign * H.STAND_PITCH)


STAND_PIV = None


def deck_z():
    """Plinth deck height in the levelled stand frame (not the bbox top: the boss stands higher)."""
    _, zc = H.pod_geom()
    r = max(r for _, r in H.POD_PROFILE)
    return zc - r - H.STAND_HEIGHT


STAND_TEXT_SEC = [None]


def stand_decorate(P):
    """Raised lettering on the plinth top, in the strip in front of the blade (viewer on -y):
    reading lines run along x, first line furthest back."""
    lv = stand_level(P)
    bl, bw, _ = H.STAND_BASE
    edge, gap, wmax, dx = STAND_TEXT
    xc = H.STAND_X + H.STAND_BASE_DX + dx
    secs = mf.CrossSection()
    y = -bw / 2 + edge
    for txt, h in reversed(STAND_LINES):
        t = text_section(txt, h, 0, 0)
        a, b, c, d = t.bounds()
        if c - a > wmax:
            t = t.scale([wmax / (c - a), 1.0])
        secs = secs + t.translate([xc, y + h / 2])
        y += h + gap
    top = deck_z()
    raised = secs.extrude(STAND_RELIEF + 0.05).translate([0, 0, top - 0.05])
    lv = lv + raised
    STAND_TEXT_SEC[0] = secs
    return stand_level(lv, -1), raised


def stand_paint(P):
    lv = stand_level(P)
    x0, y0, z0, x1, y1, z1 = lv.bounding_box()
    top = deck_z()
    text = K.box(-1000, 1000, -1000, 1000, top + 0.01, top + 5) ^ prism_z(STAND_TEXT_SEC[0].offset(0.3, mf.JoinType.Round))
    bl, bw, _ = H.STAND_BASE
    xc = H.STAND_X + H.STAND_BASE_DX
    ring = lambda inset, w: (K.rect_outline(xc - bl / 2 + inset, -bw / 2 + inset, xc + bl / 2 - inset,
                                            bw / 2 - inset, w))
    deck = K.box(-1000, 1000, -1000, 1000, top - SKIN, top + 0.05)
    ops = [(RED, deck ^ prism_z(ring(5.0, 1.0))), (WHITE, deck ^ prism_z(ring(6.4, 0.8))),
           (BLUE, deck ^ prism_z(ring(7.6, 1.0))), (WHITE, text)]
    vols = K.paint(lv, ops, BLACK)
    return {c: stand_level(v, -1) for c, v in vols.items()}


# ============================================================
# MAIN
# ============================================================
def add_object(objs, name, posed, out, whole):
    import trimesh
    lo = np.min([v.bounding_box()[:3] for v in posed.values()], axis=0)
    hi = np.max([v.bounding_box()[3:] for v in posed.values()], axis=0)
    posed = {c: v.translate(list(-lo)) for c, v in posed.items()}
    Vv, F = mesh_of(whole.translate(list(-lo)))
    trimesh.Trimesh(Vv, F).export(out / "stl" / f"{name}.stl")
    objs[name] = {"name": name, "vols": posed, "size": (hi - lo)[:2], "height": (hi - lo)[2]}
    print(f"{name:28s} " + ", ".join(f"{FILAMENTS[c][0]} {v.volume() / 1000:.2f}cc"
                                      for c, v in sorted(posed.items())), flush=True)


PLATE_GROUPS = [            # parts kept together by colour set (max 5 colours a plate)
    ("Fuselage", lambda n: n.startswith(("fuselage", "smoke_pod"))),
    ("Tailplanes and small parts", lambda n: n.startswith(("tailplane", "aerial", "probe", "key_", "wingpin"))),
    ("Wing tops", lambda n: n.startswith("wingtop_")),
    ("Wing undersides", lambda n: n.startswith("wingbot_")),
    ("Fins and canopy", lambda n: n.startswith("fin_") or n == "canopy"),
    ("Display stand", lambda n: n.startswith("stand")),
    ("Gear", lambda n: True),
]
MAX_COLOURS = 5

if __name__ == "__main__":
    import time
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "out")
    template = sys.argv[2] if len(sys.argv) > 2 else None
    out.mkdir(parents=True, exist_ok=True)
    (out / "stl").mkdir(exist_ok=True)
    parts, poses = H.build()
    _, _, STAND_PIV = H.stand_parts()
    only = [o for o in os.environ.get("ONLY", "").split(",") if o]
    objs, preview = {}, []
    for name, P in parts.items():
        if only and not any(o in name for o in only):
            continue
        t0 = time.time()
        P, dropped = K.largest_piece(P)
        if any(v > 1.0 for v in dropped):
            print(f"!! {name}: dropped loose pieces {[round(v, 1) for v in dropped if v > 1.0]} mm3")
        if name.startswith(("wingtop_", "wingbot_")):     # panel lines from the whole wing, then split
            side = 1 if name.endswith("stbd") else -1
            P = (wing_detailed(side) ^ H.wing_half_region(side, name.startswith("wingtop_"))) \
                - H.wing_key_slot(side) - H.main_socket(side) - H.wing_pins(side, H.WING_PIN_FIT) \
                - H.gear_bay(side)
            P, _ = K.largest_piece(P)
        else:
            P_plain[name] = P                 # before panel lines and hinge grooves
            P = D.apply(name, P)
        if name == "stand_base":
            P, _ = stand_decorate(P)
        vols = colour_part(name, P)
        pf = lambda m, pose=poses[name]: pose(m).scale([H.PRINT_K] * 3)     # print pose, at 1:32
        for c, v in vols.items():
            Vv, F = mesh_of(v.scale([H.PRINT_K] * 3))
            preview.append((c, Vv, F, name))
        add_object(objs, name, {c: pf(v) for c, v in vols.items()}, out, pf(P))
        print(f"  [{name}] {time.time() - t0:.1f}s", file=sys.stderr, flush=True)
    # plates
    plates_all, seen = [], set()
    for gname, pred in PLATE_GROUPS:
        group = [n for n in objs if n not in seen and pred(n)]
        seen.update(group)
        group.sort(key=lambda n: -objs[n]["size"][0] * objs[n]["size"][1])
        for items in K.pack([(n, tuple(objs[n]["size"])) for n in group], BED, PLATE_GAP):
            plates_all.append((gname, items))
    objects = []
    for pi, (gname, items) in enumerate(plates_all):
        for n, x, y, rot90 in items:
            o = objs[n]
            vols = o["vols"]
            if rot90:
                sx, sy = o["size"]
                vols = {c: v.rotate([0, 0, 90]).translate([sy, 0, 0]) for c, v in vols.items()}
            objects.append({"name": n, "placement": (pi, x + BED_MARGIN[0], y + BED_MARGIN[1]),
                            "volumes": [(c, *mesh_of(v)) for c, v in sorted(vols.items())]})
    import trimesh
    scene = trimesh.Scene()
    for i, (c, Vv, F, pname) in enumerate(preview):
        rgb = [int(FILAMENTS[c][1][k:k + 2], 16) for k in (1, 3, 5)]
        m = trimesh.Trimesh(Vv, F)
        m.visual.face_colors = rgb + [255]
        scene.add_geometry(m, node_name=f"{pname}__{i}", geom_name=f"{pname}__{i}")
    scene.export(out / "hawk_colour_preview.glb")
    names = [f"{g} {i + 1}" for i, (g, _) in enumerate(plates_all)]
    for i, (gname, items) in enumerate(plates_all):
        cols = sorted({c for n, *_ in items for c in objs[n]["vols"]})
        print(f"plate {i + 1} ({gname}): " + ", ".join(FILAMENTS[c][0] for c in cols)
              + " | " + ", ".join(n for n, *_ in items))
        assert len(cols) <= MAX_COLOURS, f"plate {i + 1} needs {len(cols)} colours"
    if not only:
        K.write_3mf(out / "hawk_kit.3mf", objects, names, template, FILAMENTS,
                    "BAE Hawk T.1A Red Arrows snap kit 1:32",
                    [FILAMENT_MAP if g in MAPPED_PLATES else None for g, _ in plates_all])
        print("wrote", out / "hawk_kit.3mf")
