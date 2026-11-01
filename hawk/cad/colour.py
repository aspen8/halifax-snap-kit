"""
Colour the Hawk kit (Red Arrows) and write a multi-colour Bambu Studio 3MF.

Run:  python colour.py OUT_DIR [project_settings_template.json]
      ONLY=name,name python colour.py OUT_DIR      (just some parts)

Scheme: Red Arrows Hawk T.1A, current Union-flag fin (traced from the HobbyBoss 81738 sheet).
  - Fuselage sections print red, on end. White cheat line, tail swoosh, belly stripes,
    "ROYAL AIR FORCE" and the fuselage roundels are press-in inlays (Halifax v2 style).
    Stripe shapes are traced from the Revell 04284 views (hawk/tools/white_regions.py,
    kept in ref/hawk_white/, not in git); the lettering is regenerated as text.
  - Wings print flat: the white underside chevrons are in the bottom skin (first layers).
    Roundels are through-discs, so they show above and below.
  - Fin halves print flat: the traced white swoosh and Union flag in the outer skin.
  - Canopy clear with black frames; cockpit black/grey; gear grey with black tyres.
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
SKIN = 0.8                   # mm, coloured skin depth
FIN_SKIN = 0.6               # the fin halves are thin
SKIN_OUT = 0.05              # skins reach just past the surface (no zero-thickness slivers)
INLAY_DEPTH = 1.2
INLAY_FIT = 0.15
LETTER_BOLD = 0.15           # mm, letters grown before cutting (thicker strokes print better)
LETTER_FIT = 0.12
STRIPE_MIN_W = 1.3           # mm, stripes are widened to at least this (printable inlays, as thin as the letters)
CHUNK = 38.0                 # mm, long stripes are split into inlays this long

FILAMENTS = {
    1: ("Red", "#C8102E"),
    2: ("White", "#F2F2F2"),
    3: ("Blue", "#1F2D6B"),
    4: ("Black", "#1C1C1C"),
    5: ("Clear", "#DDEBF2"),
    6: ("Grey", "#8C9096"),
}
RED, WHITE, BLUE, BLACK, CLEAR, GREY = range(1, 7)
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

BED = (230.0, 250.0)
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


def under_white():
    """White on the underside, (x, y): wing chevrons and belly stripes."""
    keep = []
    for r in rings("under"):
        a = 0.5 * abs(np.dot(r[:, 0], np.roll(r[:, 1], 1)) - np.dot(r[:, 1], np.roll(r[:, 0], 1)))
        cx, cy = r.mean(0)
        if a < 3.0:
            continue
        if math.hypot(cx - WING_ROUNDEL[0], abs(cy) - WING_ROUNDEL[1]) < WING_ROUNDEL[2] / 2 + 2:
            continue
        if cx < 60:                                     # labels by the nose
            continue
        keep.append(r)
    sec = close(cs(keep), 1.6)                         # bridge the drawing's panel lines
    return sec.offset(-0.7, mf.JoinType.Round).offset(0.7, mf.JoinType.Round).simplify(0.05)


def fuselage_plan(x0, x1, inset=0.0, n=160):
    xs = np.linspace(x0, x1, n)
    hw = np.array([max(H.fuse_at(x)[1] - inset, 0.1) for x in xs])
    return cs([np.r_[np.c_[xs, hw], np.c_[xs[::-1], -hw[::-1]]]])


# ============================================================
# INLAYS
# ============================================================
def z_inlay(P, sec, side, depth=INLAY_DEPTH, fit=INLAY_FIT):
    """Inlay of a flat shape (x, y) pressed into a top (side=+1) or bottom (side=-1) surface."""
    import trimesh
    V, F = mesh_of(P)
    tm = trimesh.Trimesh(V, F, process=False)
    x0, y0, x1, y1 = sec.bounds()
    A, B = np.meshgrid(np.linspace(x0, x1, 40), np.linspace(y0, y1, 12))
    o = np.c_[A.ravel(), B.ravel(), np.full(A.size, 500.0 * side)]
    d = np.tile([0, 0, -float(side)], (A.size, 1))
    loc, _, _ = tm.ray.intersects_location(o, d, multiple_hits=False)
    if not len(loc):
        return P, None
    flat = (loc[:, 2] * side).min() - depth
    keep = (mf.Manifold.cube([1000, 1000, 500]).translate([-500, -500, flat]) if side > 0 else
            mf.Manifold.cube([1000, 1000, 500]).translate([-500, -500, -flat - 500]))
    socket = prism_z(sec) ^ keep
    plug = K.largest_piece(P ^ prism_z(sec.offset(-fit, mf.JoinType.Round)) ^ keep)[0]
    return P - socket, plug


def y_inlay(P, sec, side, depth=INLAY_DEPTH, fit=INLAY_FIT):
    """Inlay of a flat shape (x, z) pressed into a side surface (side=+1 starboard, -1 port).
    Like kitlib.make_section_inlay, but samples inside the shape itself and skips shapes the
    part doesn't reach (a stripe chunk that misses the surface returns None)."""
    import trimesh
    if (P ^ prism_y(sec)).is_empty():
        return P, None
    V, F = mesh_of(P)
    tm = trimesh.Trimesh(V, F, process=False)
    x0, z0, x1, z1 = sec.bounds()
    A, B = np.meshgrid(np.linspace(x0, x1, 60), np.linspace(z0, z1, 12))
    o = np.c_[A.ravel(), np.full(A.size, 500.0 * side), B.ravel()]
    d = np.tile([0, -float(side), 0], (A.size, 1))
    loc, _, _ = tm.ray.intersects_location(o, d, multiple_hits=False)
    if not len(loc):
        return P, None
    flat = (loc[:, 1] * side).min() - depth
    keep = (mf.Manifold.cube([1000, 500, 1000]).translate([-500, flat, -500]) if side > 0 else
            mf.Manifold.cube([1000, 500, 1000]).translate([-500, -flat - 500, -500]))
    socket = prism_y(sec) ^ keep
    plug = K.largest_piece(P ^ prism_y(sec.offset(-fit, mf.JoinType.Round)) ^ keep)[0]
    if plug.is_empty():
        return P, None
    return P - socket, plug


def chunks(sec, x_edges):
    """Split a section at the given x positions (and every CHUNK mm), keeping only real pieces."""
    x0, _, x1, _ = sec.bounds()
    cuts = sorted(set([x0 - 1] + [x for x in x_edges if x0 < x < x1] + [x1 + 1]))
    out = []
    for a, b in zip(cuts, cuts[1:]):
        n = max(1, int(math.ceil((b - a) / CHUNK)))
        for i in range(n):
            lo, hi = a + (b - a) * i / n, a + (b - a) * (i + 1) / n
            piece = sec ^ mf.CrossSection.square([hi - lo, 400.0]).translate([lo, -200.0])  # exact (kitlib.clip pads 1 mm)
            for comp in piece.decompose():
                if comp.area() > 2.0:
                    out.append(comp)
    return out


INLAY_POSE = {("y", 1): [90, 0, 0], ("y", -1): [-90, 0, 0], ("z", 1): [0, 0, 0], ("z", -1): [180, 0, 0]}


def fuselage_inlays(name, P):
    """Sockets in a fuselage section/radome + its inlays: [(name, {colour: vol}, rot, whole)]."""
    out = []
    x0, _, _, x1, _, _ = P.bounding_box()
    tag = {"radome": "nose", "fuselage_front": "front", "fuselage_rear": "rear"}[name]
    edges = [H.INTAKE_STATIONS[0][0], H.NOSE_SPLIT_X, H.FUSE_SPLIT_X]
    for side, st in ((1, "stbd"), (-1, "port")):
        stripes = widen(side_stripes(side), STRIPE_MIN_W)
        k = 0
        # the radome's band is painted (colour_part), so it can wrap round the tip
        for piece in ([] if name == "radome" else chunks(clip(stripes, x0, -100, x1, 100), edges)):
            P, plug = y_inlay(P, piece, side)
            if plug is not None:
                k += 1
                out.append((f"inlay_stripe_{tag}_{st}_{k}", {WHITE: plug}, INLAY_POSE[("y", side)], plug))
        if name == "fuselage_front":
            for i, letter in enumerate(sorted(letters_section(side).decompose(),
                                              key=lambda c: c.bounds()[0] * (-side))):
                P, plug = y_inlay(P, letter, side, fit=LETTER_FIT)
                if plug is not None:
                    out.append((f"inlay_letter_{st}_{i + 1:02d}", {WHITE: plug}, INLAY_POSE[("y", side)], plug))
        if name == "fuselage_rear":
            x, z, d = FUSE_ROUNDEL
            P, vols, plug = K.make_inlay(P, (x, z), d, ROUNDEL(d), "y", side, INLAY_DEPTH, INLAY_FIT)
            out.append((f"roundel_fuselage_{st}", vols, INLAY_POSE[("y", side)], plug))
    if name in ("fuselage_rear", "fuselage_front"):
        belly = under_white() ^ fuselage_plan(max(x0, 150), x1, inset=1.0)
        k = 0
        for piece in chunks(belly, [H.FUSE_SPLIT_X]):
            if piece.area() < 4.0:
                continue
            P, plug = z_inlay(P, piece, -1)
            if plug is not None:
                k += 1
                out.append((f"inlay_belly_{tag}_{k}", {WHITE: plug}, INLAY_POSE[("z", -1)], plug))
    return P, out


def wing_roundel(P, side):
    """Through-disc roundel (shows top and bottom)."""
    x, y, d = WING_ROUNDEL
    y *= side
    r = d / 2
    socket = K.cyl_axis(x, y, r, "z")
    plug = K.largest_piece(P ^ K.cyl_axis(x, y, r - INLAY_FIT, "z"))[0]
    vols, prev = {}, None
    for colour, dd in reversed(ROUNDEL(d)):
        cyl = K.cyl_axis(x, y, dd / 2, "z")
        c = plug ^ (cyl if prev is None else cyl - prev)
        if c.volume() > 1e-3:
            vols[colour] = vols[colour] + c if colour in vols else c
        prev = cyl
    return P - socket, vols, plug


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


CANOPY_FRAMES_X = [(57.0, 2.6, RED),             # windscreen arch: body colour and thick (photos)
                   (84.0, 2.0, WHITE)]            # hoop between the cockpits, behind the front
                                                  # seat (cream on the aircraft; white is closest)
CANOPY_REAR_FRAME = 1.8                           # mm, frame along the slanted rear edge
CANOPY_SILL = 0.9                                 # mm of black along the canopy's bottom edge
NOSE_DOME = (4.0, 9.0, 36.0, 62.0)                # height above the sill at the centre, half-width,
                                                  # x range: the red nose top domes up into the
                                                  # windscreen, so the glass base is an arch
                                                  # (head-on photos), not a straight line


def nose_dome():
    """Region below an elliptical arch over the canopy sill, ahead of the windscreen arch."""
    h, w, x0, x1 = NOSE_DOME
    ws = []
    for x in np.arange(x0, x1 + 1e-6, 1.0):
        zs = H.canopy_sill_z(x)
        ws.append(H.egg_wire(x, w, zs + h, zs - 8.0, 6.0, zs, 2.0))
    return H.to_m(H.loft(ws, ruled=True))


def colour_part(name, P):
    if name.startswith("wing_"):
        S = skins(P)
        return paint(P, [(WHITE, S["down"] ^ prism_z(under_white()))])
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
        # Below the curved sill line the canopy part is fuselage: red. A black sill frame runs
        # above it, the windscreen arch and the rear frame are black on the shell.
        shell = P - K.inner_core(P, 0.7)
        xs = np.linspace(30.0, 140.0, 111)
        sill = [(x, H.canopy_sill_z(x)) for x in xs]
        under = cs([np.array(sill + [(140.0, -20.0), (30.0, -20.0)])])
        band = cs([np.array([(x, z + CANOPY_SILL) for x, z in sill] + [(x, z - 0.05) for x, z in sill[::-1]])])
        hoops = [(c, shell ^ K.slab("x", x, w)) for x, w, c in CANOPY_FRAMES_X]
        (ra, rza), (rb, rzb) = H.CANOPY_REAR
        ang = math.degrees(math.atan2(rb - ra, rza - rzb))
        keep = H.rot_about(K.box(ra - 200, ra - CANOPY_REAR_FRAME, -50, 50, rzb - 30, rza + 30), (ra, 0, rza), "y", -ang)
        rear = P - (P ^ keep)
        return paint(P, [(BLACK, (shell ^ prism_y(band)) + (shell ^ rear))] + hoops +
                     [(RED, P ^ prism_y(under)), (RED, P ^ nose_dome())], base=CLEAR)
    if name == "radome":
        # the cheat line painted into the skin: a side-on band that also crosses the front of
        # the nose, where both sides meet just above the probe boss
        _, _, _, bd, bl = H.PROBE
        probe = H.box(-60.0, 3.4, -bd / 2 - 0.15, bd / 2 + 0.15, -bd / 2 - 0.15, bd / 2 + 0.15)
        band = prism_y(cheat_front()) - K.inner_core(P, SKIN) - probe
        return paint(P, [(WHITE, band)])
    if name == "cockpit":
        cush = mf.Manifold()
        for xs, rise in H.SEATS:
            d, sw, sh = H.SEAT
            z0 = H.COCKPIT_CAVITY[3] + 1.6 + rise
            cush = cush + K.box(xs - d + 0.8, xs - 2.3, -sw / 2 + 2.4, sw / 2 - 2.4, z0 + 4.4, z0 + 6.0)
            cush = cush + K.box(xs - 3.6, xs - 2.3, -sw / 2 + 1.0, sw / 2 - 1.0, z0 + 6.3, z0 + sh * 0.69)
        return paint(P, [(GREY, cush)], base=BLACK)
    if name.startswith("wheel_"):
        x0, y0, z0, x1, y1, z1 = P.bounding_box()
        c = ((x0 + x1) / 2, (z0 + z1) / 2)
        d = x1 - x0
        hub = K.cyl_axis(c[0], c[1], d * 0.31, "y")
        return paint(P, [(GREY, hub)], base=BLACK)
    if name.startswith(("gear_", "pin_")):
        return {GREY: P}
    if name in ("cockpit",):
        return {BLACK: P}
    if name == "stand_base":
        return stand_paint(P)
    if name == "stand_post":
        return {BLACK: P}
    return {RED: P}


# ============================================================
# DISPLAY STAND (black plinth, raised white lettering, red/white/blue pinstripe)
# ============================================================
STAND_LINES = [("BAE SYSTEMS HAWK T.1A", 7.0), ("RED ARROWS", 9.0), ("ROYAL AIR FORCE AEROBATIC TEAM", 4.2)]
STAND_TEXT_Y = (-24.0, -36.0, -46.5)
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
    """Raised lettering on the plinth top (front edge, viewer on -y)."""
    lv = stand_level(P)
    x0, y0, z0, x1, y1, z1 = lv.bounding_box()
    xc = H.STAND_X + H.STAND_BASE_DX
    secs = mf.CrossSection()
    for (txt, h), y in zip(STAND_LINES, STAND_TEXT_Y):
        t = text_section(txt, h, 0, 0)
        a, b, c, d = t.bounds()
        if c - a > H.STAND_BASE[0] - 26:
            t = t.scale([(H.STAND_BASE[0] - 26) / (c - a), 1.0])
        secs = secs + t.translate([xc - 18.0, y + H.STAND_BASE[1] / 2 - 2])
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
    ("Fins, roundels and white inlays", lambda n: n.startswith(("fin_", "roundel_", "inlay_"))),
    ("Canopy and cockpit", lambda n: n in ("canopy", "cockpit")),
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
        extra = []
        if name in ("radome", "fuselage_front", "fuselage_rear"):
            P, extra = fuselage_inlays(name, P)
        if name.startswith("wing_"):
            s = 1 if name.endswith("stbd") else -1
            P, vols_r, plug = wing_roundel(P, s)
            extra.append((f"roundel_wing_{name.split('_')[-1]}", vols_r, None, plug))
        vols = colour_part(name, P)
        pose = poses[name]
        jobs = [(name, vols, pose, P)]
        for n, iv, rot, plug in extra:
            if rot is None:                                   # through-disc: print like its wing
                jobs.append((n, iv, pose, plug))
            else:
                jobs.append((n, iv, (lambda m, r=rot: m.rotate(r)), plug))
        for jname, jvols, pf, whole in jobs:
            for c, v in jvols.items():
                Vv, F = mesh_of(v)
                preview.append((c, Vv, F, jname))
            add_object(objs, jname, {c: pf(v) for c, v in jvols.items()}, out, pf(whole))
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
            objects.append({"name": n, "placement": (pi, x, y),
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
                    "BAE Hawk T.1A Red Arrows snap kit 1:40")
        print("wrote", out / "hawk_kit.3mf")
