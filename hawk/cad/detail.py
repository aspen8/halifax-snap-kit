"""
Surface detail for the Hawk kit: engraved panel lines, control-surface hinge lines,
access panels and sparse raised fasteners. Sizes as the Halifax (PB94 convention):
panel lines 0.5 x 0.25 mm, hinge lines 0.4 mm deep, fastener dots 0.7 mm raised 0.2 mm.

Layout follows the panel lines drawn on the Revell 04284 plan and side views.
Everything works on manifold3d meshes in the assembled frame (hawk.py axes).
"""
import manifold3d as mf

import hawk as H
from kitlib import band, dots_along, rect_outline, prism_y, prism_z

GROOVE_W = 0.5
GROOVE_D = 0.25
HINGE_D = 0.4
RIVET_D = 0.7
RIVET_H = 0.2
RIVET_PITCH = 6.0

# Fuselage rings (x) and side panels (x0, x1, z0, z1), both sides
FUSE_RINGS = [31.0, 46.0, 92.5, 160.0, 197.0, 232.0, 252.0]
SIDE_PANELS = [(24.0, 36.0, -4.0, 6.0),       # avionics bay door
               (48.0, 62.0, -5.5, 8.5),       # forward equipment bay
               (196.0, 214.0, -1.0, 13.0),    # engine access
               (234.0, 249.0, 1.0, 12.0)]     # rear fuselage access
SEAMS = [(-4.5, 22.0, 90.0)]                  # (z, x0, x1) lower side seam
TOP_PANELS = [(145.0, 160.0, 4.5), (164.0, 176.0, 4.0)]   # spine access hatches: x0, x1, half-width
BELLY_PANELS = [(196.0, 232.0, 6.0)]          # engine bay doors: x0, x1, half-width
BELLY_SEAM = (100.0, 250.0)                   # centreline seam along the belly (rear section)

# Wing lines as fractions of local chord: (fraction, eta from, eta to, kind)
WING_SPANWISE = [
    (0.12, 0.08, 0.97, "panel"),     # LE skin joint
    (0.18, 0.08, 0.95, "spar"),      # front spar
    (0.64, 0.08, 0.95, "spar"),      # rear spar
    (0.72, 0.10, 0.55, "hinge"),     # flap
    (0.75, 0.58, 0.93, "hinge"),     # aileron
]
WING_CHORDWISE = [(0.10, 0.72, 1.0, "hinge"), (0.55, 0.72, 1.0, "hinge"), (0.58, 0.75, 1.0, "hinge"),
                  (0.93, 0.75, 1.0, "hinge"), (0.35, 0.18, 0.64, "panel"), (0.75, 0.18, 0.64, "panel"),
                  (0.97, 0.0, 1.0, "panel")]
WING_FILLER = (0.45, 0.40, 2.2)      # eta, chord fraction, diameter (fuel filler)
TAIL_LINES = [(0.25, 0.1, 0.95), (0.70, 0.1, 0.95)]   # chord fraction, eta from, to
RUDDER = (0.70, 27.0, 60.0)          # chord fraction of the hinge, z from, to


def skin(P, axis, depth):
    v = {"z": [0, 0, -depth], "-z": [0, 0, depth], "y": [0, -depth, 0], "-y": [0, depth, 0]}[axis]
    return P - P.translate(v)


def raised(P, axis, height=RIVET_H):
    v = {"z": [0, 0, height], "-z": [0, 0, -height], "y": [0, height, 0], "-y": [0, -height, 0]}[axis]
    return P.translate(v) - P


def slab_x(x, w):
    return mf.Manifold.cube([w, 1000, 1000]).translate([x - w / 2, -500, -500])


def wing_pt(eta, f, side):
    y = eta * H.SPAN / 2
    le, c, _ = H.wing_plan(y)
    return (le + f * c, side * y)


def tail_pt(eta, f, side):
    le, c = H.tail_plan(eta)
    return (le + f * c, side * eta * H.TAIL_SEMISPAN * 0.985)


def lines(segs, w=GROOVE_W):
    sec = mf.CrossSection()
    for p0, p1 in segs:
        sec = sec + band(p0, p1, w)
    return sec


def apply(name, P):
    cuts, adds = [], []

    def groove(prism, axis, depth=GROOVE_D):
        cuts.append(skin(P, axis, depth) ^ prism)

    if name.startswith("wing_"):
        side = 1 if name.endswith("stbd") else -1
        segs = {"panel": [], "spar": [], "hinge": []}
        for f, e0, e1, kind in WING_SPANWISE:
            segs[kind].append((wing_pt(e0, f, side), wing_pt(e1, f, side)))
        for e, f0, f1, kind in WING_CHORDWISE:
            segs[kind].append((wing_pt(e, f0 - 0.01, side), wing_pt(e, min(f1 + 0.02, 1.03), side)))
        for kind, depth in (("panel", GROOVE_D), ("spar", GROOVE_D), ("hinge", HINGE_D)):
            sec = lines(segs[kind])
            groove(prism_z(sec), "z", depth)
            if kind == "hinge":
                groove(prism_z(sec), "-z", depth)          # control surfaces show underneath too
        e, f, d = WING_FILLER
        cx, cy = wing_pt(e, f, side)
        groove(prism_z(mf.CrossSection.circle(d / 2 + GROOVE_W / 2, 32) - mf.CrossSection.circle(d / 2 - GROOVE_W / 2, 32)
                       ).translate([cx, cy, 0]), "z")
        dots = mf.CrossSection()
        for p0, p1 in segs["spar"]:
            dots = dots + dots_along(p0, p1, 0.8, RIVET_PITCH, RIVET_D)
        adds.append(raised(P, "z") ^ prism_z(dots))
    elif name.startswith("tailplane_"):
        side = 1 if name.endswith("stbd") else -1
        sec = lines([(tail_pt(e0, f, side), tail_pt(e1, f, side)) for f, e0, e1 in TAIL_LINES])
        groove(prism_z(sec), "z")
    elif name.startswith("fin_"):
        f, z0, z1 = RUDDER
        def x_at(z):
            (lx0, lz0), (lx1, lz1) = H.FIN_LE
            (tx0, tz0), (tx1, tz1) = H.FIN_TE
            le = lx0 + (z - lz0) * (lx1 - lx0) / (lz1 - lz0)
            te = tx0 + (z - tz0) * (tx1 - tx0) / (tz1 - tz0)
            return le + f * (te - le)
        sec = band((x_at(z0), z0), (x_at(z1), z1), GROOVE_W) + band((x_at(z1), z1), (H.FIN_TE[0][0] + 20, z1 + 2), GROOVE_W)
        axis = "y" if name.endswith("stbd") else "-y"
        groove(prism_y(sec), axis, HINGE_D)
    elif name.startswith(("fuselage_", "radome")):
        outer = skin(P, "z", GROOVE_D) + skin(P, "y", GROOVE_D) + skin(P, "-y", GROOVE_D) + skin(P, "-z", GROOVE_D)
        rings = mf.Manifold()
        for x in FUSE_RINGS:
            rings = rings + slab_x(x, GROOVE_W)
        cuts.append(outer ^ rings)
        sec = mf.CrossSection()
        for x0, x1, z0, z1 in SIDE_PANELS:
            sec = sec + rect_outline(x0, z0, x1, z1, GROOVE_W)
        for z, x0, x1 in SEAMS:
            sec = sec + band((x0, z), (x1, z), GROOVE_W)
        for axis in ("y", "-y"):
            groove(prism_y(sec), axis)
        top = mf.CrossSection()
        for x0, x1, hw in TOP_PANELS:
            top = top + rect_outline(x0, -hw, x1, hw, GROOVE_W)
        groove(prism_z(top), "z")
        bot = band((BELLY_SEAM[0], 0), (BELLY_SEAM[1], 0), GROOVE_W)
        for x0, x1, hw in BELLY_PANELS:
            bot = bot + rect_outline(x0, -hw, x1, hw, GROOVE_W)
        groove(prism_z(bot), "-z")
    else:
        return P
    out = P
    for c in cuts:
        out = out - c
    for a in adds:
        out = out + a
    return out
