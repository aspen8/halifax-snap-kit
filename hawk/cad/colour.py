"""
Colour the Hawk kit (Red Arrows) and write a multi-colour Bambu Studio 3MF.

Run:  python colour.py OUT_DIR [project_settings_template.json]   (default: cad/bambu_x2d_project_settings.json)
      ONLY=name,name python colour.py OUT_DIR      (just some parts)

Scheme: Red Arrows Hawk T.1A, current Union-flag fin (traced from the HobbyBoss 81738 sheet).
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
ROUNDEL = lambda d: [(BLUE, d), (WHITE, d * 2 / 3), (RED, d / 3)]

FUSE_ROUNDEL = (187.3, 9.0, 10.6)        # x, z, diameter (Revell side view)
WING_ROUNDEL = (162.2, 94.8, 15.0)       # x, |y|, diameter (Revell top view)
LETTERS = ("ROYAL AIR FORCE", 143.0, 8.2, 60.0, 5.2)   # letters sit on the cheat line   # text, x centre, z centre, length, height:
                                                         # kept below the side pod's top edge (HobbyBoss)
# Cheat line (photos): thin at the nose, thickening to the lettering's height on the side pod,
# broken for "ROYAL AIR FORCE", resumed behind the roundel and swept up onto the fin in one curve.
CHEAT_NOSE = (1.8, 1.75, 1.1)      # x, lower edge z, width at the nose tip: the band starts right
                                   # at the tip, just above the probe boss, so the two sides join
                                   # across the front of the nose (head-on photo)
CHEAT_POD_X = 95.0                 # full letter height reached here (on the pod)
CHEAT_GAP = 2.0                    # mm of red between the band and the lettering
SWOOSH_TOP = (223.5, 25.0, 0.57, 0.82, 8.0)   # x, z where it meets the fin flag, direction, width there
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


def cheat_rear():
    """From behind the roundel, level at the letter height, then one smooth curve up onto the fin
    (a cubic Bezier into the flag's white at the fin root), widening as it climbs."""
    _, xc, zc, length, h = LETTERS
    rx, rz, rd = FUSE_ROUNDEL
    x3, z3, dx, dz, w3 = SWOOSH_TOP
    P = np.array([(rx, zc), (rx + 20.0, zc), (x3 - dx * 13.0, z3 - dz * 13.0), (x3, z3)])
    u = np.linspace(0, 1, 120)[:, None]
    c = ((1 - u) ** 3 * P[0] + 3 * (1 - u) ** 2 * u * P[1] + 3 * (1 - u) * u * u * P[2] + u ** 3 * P[3])
    c = np.vstack([c, [x3 + dx * 6.0, z3 + dz * 6.0]])     # runs on to the fin root line
    s = np.clip((np.r_[u[:, 0], 1.0] - 0.3) / 0.7, 0, 1)
    w = h + (w3 - h) * s
    sec = _ribbon(c, w)
    return sec - mf.CrossSection.circle(rd / 2 + 0.6, 64).translate([rx, rz])


def side_stripes(side):
    """White on the fuselage side, (x, z): the cheat line in front of the lettering, and the band
    behind the roundel that sweeps up onto the fin. The same on both sides."""
    return cheat_front() + cheat_rear()


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


# Underside white (Revell 04284 under view, lines fitted to the traced areas in ref/hawk_white/
# under.json): a chevron on each wing - a band along the leading-edge side, widening outboard,
# and a strip along the trailing edge - running into two stripes along the belly that meet in
# a U under the jet pipe. Straight lines, so the drawing's panel lines leave no gaps.
CHEVRON_OUT = ((110.0, 16.9), 0.825)     # outer edge: point (x, |y|), slope d|y|/dx
CHEVRON_IN = ((118.0, 16.1), 0.547)      # inner edge of the band
CHEVRON_TE_X = 161.5                     # inner edge of the trailing-edge strip
BELLY_LO = ((161.5, 9.6), (256.0, 1.0))  # belly stripe inner edge (x, |y|)
BELLY_HI = ((161.5, 12.4), (256.0, 3.4)) # ...outer edge
BELLY_END = (253.4, 256.9)               # x range of the bar joining the two stripes


def _rect(a0, b0, a1, b1):
    return mf.CrossSection.square([a1 - a0, b1 - b0]).translate([a0, b0])


def _halfplane(pt, slope, below):
    (x0, y0) = pt
    f = lambda x: y0 + slope * (x - x0)
    far = -300.0 if below else 300.0
    return cs([np.array([(40.0, f(40.0)), (300.0, f(300.0)), (300.0, far), (40.0, far)])])


def under_white():
    """White on the underside, (x, y), both sides."""
    band = (_halfplane(*CHEVRON_OUT, True)
            ^ (_halfplane(*CHEVRON_IN, False) + _rect(CHEVRON_TE_X, -300.0, 300.0, 300.0))
            ^ _rect(95.0, 4.0, 200.0, 200.0)
            ^ H.wing(1).project())                                    # on the wing only
    (a0, l0), (a1, l1) = BELLY_LO
    (_, h0), (_, h1) = BELLY_HI
    belly = cs([np.array([(a0, l0), (a1, l1), (a1, h1), (a0, h0)])])
    belly = belly + _rect(CHEVRON_TE_X, l0, 171.5, h0 + 1.0)       # joins the trailing-edge strip
    half = band + belly
    sec = half + half.mirror([0.0, 1.0])
    e0, e1 = BELLY_END
    return sec + _rect(e0, -h1, e1, h1)


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


def fuselage_markings(name, P):
    """Paint ops for a fuselage section: cheat line, swoosh, lettering, roundels, belly stripes."""
    # regions reach past the surface and stop at the inner core: ending them exactly on the
    # surface leaves thin sheets of base red over the paint (LESSONS.md)
    core = K.inner_core(P, SKIN)
    x0, _, _, x1, _, _ = P.bounding_box()
    ops = []
    for side in (1, -1):
        half = K.box(-50.0, 400.0, 0.0 if side > 0 else -100.0, 100.0 if side > 0 else 0.0, -100.0, 100.0)
        sk = half - core
        if name != "radome":                   # the radome's band is painted in colour_part
            ops.append((WHITE, sk ^ prism_y(widen(side_stripes(side), STRIPE_MIN_W))))
        if name == "fuselage_front":
            ops.append((WHITE, sk ^ prism_y(letters_section(side))))
        if name == "fuselage_rear":
            x, z, d = FUSE_ROUNDEL
            ops += roundel_ops(x, z, d, "y", sk)
    if name in ("fuselage_front", "fuselage_rear"):
        below = K.box(-50.0, 400.0, -100.0, 100.0, -100.0, 0.0)
        ops.append((WHITE, (below - core) ^ prism_z(under_white() ^ fuselage_plan(max(x0, 150.0), x1))))
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
    """Union-flag fin traced from the HobbyBoss 81738 side views (tools/trace_colours.py,
    specs in hawk/tools/fin_flag_*.json). Returns [(colour, section)] in (x, z)."""
    tag = "stbd" if side > 0 else "port"
    p = WHITE_DIR / f"fin_{tag}.json"
    if not p.exists():
        raise SystemExit(f"missing {p}: run tools/trace_colours.py hawk/tools/fin_flag_{tag}.json {p}")
    cls = json.load(open(p))["classes"]
    ops = []
    for name, colour in (("white", WHITE), ("blue", BLUE)):
        keep = []
        for r in cls.get(name, []):
            r = np.array(r)
            a = 0.5 * abs(np.dot(r[:, 0], np.roll(r[:, 1], 1)) - np.dot(r[:, 1], np.roll(r[:, 0], 1)))
            cx, cz = r.mean(0)
            if a < 1.0 or (cx < 212.0 and cz < 32.0):      # specks, and page background by the fillet
                continue
            keep.append(r)
        if keep:
            ops.append((colour, cs(keep) ^ fin_surface()))
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


CANOPY_FRAMES_X = [(59.5, 2.6, -23.0, RED),     # windscreen arch: x at the sill, width, lean (deg,
                                                  # + = top aft), colour. Body colour, thick, leaning
                                                  # forward at the top (side photo, Revell side view)
                   (84.0, 2.0, 19.0, WHITE)]      # hoop between the cockpits, leaning back at the top
                                                  # (side photo; cream on the aircraft, white is closest)
CANOPY_REAR_FRAME = 1.8                           # mm, frame along the slanted rear edge
CANOPY_SILL = 0.9                                 # mm of black along the canopy's bottom edge
                                                  # (the red nose dome is hawk.nose_dome, on the fuselage)


def colour_part(name, P):
    if name.startswith("wing_"):
        S = skins(P)
        x, y, d = WING_ROUNDEL
        y *= 1 if name.endswith("stbd") else -1
        return paint(P, [(WHITE, S["down"] ^ prism_z(under_white()))]
                     + roundel_ops(x, y, d, "z", S["up"]) + roundel_ops(x, y, d, "z", S["down"]))
    if name.startswith("fin_"):
        S = skins(P, FIN_SKIN)
        side = S["+y"] if name.endswith("stbd") else S["-y"]
        # the swoosh runs up to the fin root line, where the flag's white takes over
        sw = (side_stripes(1 if name.endswith("stbd") else -1)
              ^ cs([np.array([(176, H.FIN_ROOT_Z - 1), (240, H.FIN_ROOT_Z - 1), (240, 60.0), (176, 60.0)])])
              ) - above_fuselage(FIN_FLAG_ABOVE + 0.3)
        ops = [(WHITE, side ^ prism_y(sw))]
        for colour, sec in fin_flag(1 if name.endswith("stbd") else -1):
            ops.append((colour, side ^ prism_y(sec)))
        return paint(P, ops)
    if name == "canopy":
        # Opaque canopy colour; black sill frame and rear frame, the red windscreen arch and the
        # white hoop. The part is cut above the sill, so it carries no fuselage red.
        shell = P - K.inner_core(P, 0.7)
        xs = np.linspace(30.0, 140.0, 111)
        # the canopy's bottom edge is its flat cut (the fuselage stays red below it): the sill
        # frame runs along that edge
        sill = [(x, H.canopy_plane_z(x) + H.FIT) for x in xs]
        band = cs([np.array([(x, z + CANOPY_SILL) for x, z in sill] + [(x, z - 1.0) for x, z in sill[::-1]])])
        hoops = [(c, shell ^ H.rot_about(K.slab("x", x, w), (x, 0.0, H.canopy_sill_z(x)), "y", a))
                 for x, w, a, c in CANOPY_FRAMES_X]
        (ra, rza), (rb, rzb) = H.CANOPY_REAR
        ang = math.degrees(math.atan2(rb - ra, rza - rzb))
        keep = H.rot_about(K.box(ra - 200, ra - CANOPY_REAR_FRAME, -50, 50, rzb - 30, rza + 30), (ra, 0, rza), "y", -ang)
        rear = P - (P ^ keep)
        return paint(P, [(BLACK, (shell ^ prism_y(band)) + (shell ^ rear))] + hoops, base=CANOPY)
    if name == "radome":
        # the cheat line painted into the skin: a side-on band that also crosses the front of
        # the nose, where both sides meet just above the probe boss
        _, _, _, bd, bl = H.PROBE
        probe = H.box(-60.0, 3.4, -bd / 2 - 0.15, bd / 2 + 0.15, -bd / 2 - 0.15, bd / 2 + 0.15)
        band = prism_y(cheat_front()) - K.inner_core(P, SKIN) - probe
        return paint(P, [(WHITE, band)])
    if name in ("fuselage_front", "fuselage_rear"):
        return paint(P, fuselage_markings(name, P))
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
    ("Fuselage and red parts", lambda n: n.startswith(("fuselage", "radome", "tailplane", "smoke_pod",
                                                        "aerial", "key_"))),
    ("Wings", lambda n: n.startswith("wing_")),
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
                    "BAE Hawk T.1A Red Arrows snap kit 1:32")
        print("wrote", out / "hawk_kit.3mf")
