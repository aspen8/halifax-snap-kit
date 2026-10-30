"""
Surface detail for the Halifax kit: engraved panel lines, control-surface
hinge lines, hatches and sparse raised rivet rows.

Sizes follow the PB94 MasterBuilds convention measured from their Spitfire:
panel lines ~0.5 mm wide x 0.25 mm deep, fastener dots ~0.7 mm raised 0.2 mm,
placed sparingly along the main structural lines.

Layout is symmetric and structural, guided by the Revell 1/72 Halifax
B/GR II Srs IA plan views. Everything works on manifold3d meshes in the
assembled frame (see halifax.py axes).
"""
import math

import manifold3d as mf
import numpy as np

import halifax as H

# ============================================================
# PARAMETERS
# ============================================================
GROOVE_W = 0.5               # mm, panel line width
GROOVE_D = 0.25              # mm, panel line depth
HINGE_D = 0.4                # mm, control-surface hinge lines read a little deeper
RIVET_D = 0.7                # mm
RIVET_H = 0.2                # mm, raised
RIVET_PITCH = 10.0           # mm along a row
RIVET_OFFSET = 0.9           # mm, row offset from its panel line

# Wing lines as fractions of local chord: (fraction, s_from, s_to, kind)
WING_SPANWISE = [
    (0.12, None, 244.0, "panel"),          # leading-edge skin joint (clear of the nose curve)
    (0.20, None, 244.0, "spar"),           # front spar
    (0.58, None, 244.0, "spar"),           # rear spar
    (0.74, None, 50.0, "hinge"),           # inner flap
    (0.74, 72.0, 150.0, "hinge"),          # outer flap
    (0.70, 150.0, 238.0, "hinge"),         # aileron
]
WING_CHORDWISE = [           # (s, chord fraction from, to, kind)
    (42.0, 0.0, 0.74, "panel"), (105.0, 0.0, 0.74, "panel"),
    (150.0, 0.0, 1.0, "hinge"), (195.0, 0.0, 0.70, "panel"),
    (50.0, 0.74, 1.0, "hinge"), (72.0, 0.74, 1.0, "hinge"), (238.0, 0.70, 1.0, "hinge"),
]
WING_FILLERS = [(30.0, 0.40, 2.2), (95.0, 0.40, 2.2), (175.0, 0.38, 1.8)]  # s, chord frac, diameter
DINGHY_HATCH = (-1, 28.0, 0.30, 12.0, 9.0)   # side, s, chord frac (centre), span, chord

TAIL_HINGE = 0.65            # elevator hinge, fraction of tailplane chord
TRIM_TAB = (14.0, 30.0, 0.86)   # |y| from, to, chord fraction (to TE)
RUDDER_HINGE = 0.55          # fraction of fin chord

FUSE_RINGS = [32.0, 48.0, 140.0, 165.0, 200.0, 245.0, 280.0, 315.0, 342.0]
FUSE_SEAMS = [(1.5, 30.0, 350.0), (-24.0, 30.0, 340.0)]     # (z, x from, x to) side seams
CREW_DOOR = (-1, 252.0, 264.0, -30.0, -8.0)    # side, x0, x1, z0, z1 (port, rear fuselage)
ROOF_HATCHES = [(150.0, 9.0, 7.0), (232.0, 9.0, 7.0)]       # x centre, length, width
NOSE_WINDOWS = [(54.0, 61.0, -10.3, -2.6),     # navigator's D-window (Revell side view)
                (61.3, 71.7, -1.3, 0.9)]       # strip window under the canopy; x0, x1, z0, z1
NOSE_PORTS = [(16.8, -15.6, 4.1)]              # round side window: x, z, diameter
NACELLE_RINGS = [0.20, 0.36]  # fractions of nacelle length (cowling joints)


# ============================================================
# 2D HELPERS
# ============================================================
def band(p0, p1, w):
    """Rectangle of width w along the segment p0-p1."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    n = np.array([-d[1], d[0]]) / (np.linalg.norm(d) + 1e-12) * w / 2
    return mf.CrossSection([np.array([p0 - n, p1 - n, p1 + n, p0 + n])])


def ring(cx, cy, d, w):
    return (mf.CrossSection.circle(d / 2 + w / 2, 64) - mf.CrossSection.circle(d / 2 - w / 2, 64)
            ).translate([cx, cy])


def rect_outline(a0, b0, a1, b1, w):
    pts = [(a0, b0), (a1, b0), (a1, b1), (a0, b1)]
    out = mf.CrossSection()
    for i in range(4):
        out = out + band(pts[i], pts[(i + 1) % 4], w)
    return out


def dots_along(p0, p1, offset, pitch=RIVET_PITCH):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    L = np.linalg.norm(d)
    if L < pitch:
        return mf.CrossSection()
    u = d / L
    n = np.array([-u[1], u[0]]) * offset
    out = mf.CrossSection()
    for t in np.arange(pitch / 2, L - pitch / 2 + 1e-6, pitch):
        c = p0 + u * t + n
        out = out + mf.CrossSection.circle(RIVET_D / 2, 16).translate(list(c))
    return out


def prism_z(sec):
    return sec.extrude(400.0).translate([0, 0, -200.0])


def prism_y(sec_xz):
    return sec_xz.extrude(400.0).translate([0, 0, -200.0]).rotate([90, 0, 0])


def slab_x(x, w):
    return mf.Manifold.cube([w, 1000, 1000]).translate([x - w / 2, -500, -500])


# ============================================================
# LAYOUTS (plan view, model coords: (x, y))
# ============================================================
def wing_point(s, f, side):
    _, le, c = H.interp(H.PLANFORM, s)
    return (le + f * c, side * s)


def wing_layout(side):
    """Returns dict kind -> list of (p0, p1) segments in plan, plus fillers/hatches."""
    segs = {"panel": [], "spar": [], "hinge": []}
    s_root = H.WING_ROOT_Y - 1.0
    for f, s0, s1, kind in WING_SPANWISE:
        s0 = s_root if s0 is None else s0
        # split at the panel joint so each piece is straight in its own panel
        cuts = [s0] + [s for s in (H.PLANFORM[1][0], H.WING_JOINT_Y) if s0 < s < s1] + [s1]
        for a, b in zip(cuts, cuts[1:]):
            segs[kind].append((wing_point(a, f, side), wing_point(b, f, side)))
    for s, f0, f1, kind in WING_CHORDWISE:
        segs[kind].append((wing_point(s, f0 - 0.02, side), wing_point(s, min(f1 + 0.02, 1.02), side)))
    return segs


def tail_layout():
    y_tip = H.FIN_Y - H.FIN_T / 2
    segs = {"hinge": [], "panel": []}
    for sd in (1, -1):
        def tp(y, f):
            t = y / y_tip
            le = H.TAIL_ROOT[0] + t * (H.TAIL_TIP[0] - H.TAIL_ROOT[0])
            c = H.TAIL_ROOT[1] + t * (H.TAIL_TIP[1] - H.TAIL_ROOT[1])
            return (le + f * c, sd * y)
        segs["hinge"].append((tp(9.0, TAIL_HINGE), tp(y_tip - 0.5, TAIL_HINGE)))
        a, b, f = TRIM_TAB
        segs["hinge"] += [(tp(a, f), tp(b, f)), (tp(a, f), tp(a, 1.02)), (tp(b, f), tp(b, 1.02))]
        segs["panel"].append((tp(9.0, 0.25), tp(y_tip - 0.5, 0.25)))
    return segs


# ============================================================
# APPLY
# ============================================================
def skin(P, axis, depth):
    """Material within `depth` of the surfaces facing +axis ('z', 'y', '-y', '-z')."""
    v = {"z": [0, 0, -depth], "-z": [0, 0, depth], "y": [0, -depth, 0], "-y": [0, depth, 0]}[axis]
    return P - P.translate(v)


def raised(P, axis, height=RIVET_H):
    v = {"z": [0, 0, height], "y": [0, height, 0], "-y": [0, -height, 0]}[axis]
    return P.translate(v) - P


def apply(name, P):
    """Return P with grooves cut and rivets added (or P unchanged)."""
    cuts, adds = [], []

    def groove(sec_prism, axis, depth):
        cuts.append(skin(P, axis, depth) ^ sec_prism)

    if name.startswith("wing_"):
        side = 1 if name.endswith("stbd") else -1
        segs = wing_layout(side)
        for kind, depth in (("panel", GROOVE_D), ("spar", GROOVE_D), ("hinge", HINGE_D)):
            sec = mf.CrossSection()
            for p0, p1 in segs[kind]:
                sec = sec + band(p0, p1, GROOVE_W)
            groove(prism_z(sec), "z", depth)
        circ = mf.CrossSection()
        for s, f, d in WING_FILLERS:
            circ = circ + ring(*wing_point(s, f, side), d, GROOVE_W)
        hs, s, f, span, ch = DINGHY_HATCH
        if hs == side:
            cx, cy = wing_point(s, f, side)
            circ = circ + rect_outline(cx - ch / 2, cy - span / 2, cx + ch / 2, cy + span / 2, GROOVE_W)
        groove(prism_z(circ), "z", GROOVE_D)
        dots = mf.CrossSection()
        for p0, p1 in segs["spar"]:
            dots = dots + dots_along(p0, p1, RIVET_OFFSET) + dots_along(p0, p1, -RIVET_OFFSET)
        adds.append(raised(P, "z") ^ prism_z(dots))
    elif name == "tailplane":
        segs = tail_layout()
        for kind, depth in (("panel", GROOVE_D), ("hinge", HINGE_D)):
            sec = mf.CrossSection()
            for p0, p1 in segs[kind]:
                sec = sec + band(p0, p1, GROOVE_W)
            groove(prism_z(sec), "z", depth)
    elif name.startswith("fin_"):
        x = H.FIN_X_LE + RUDDER_HINGE * H.FIN_CHORD
        sec = band((x, H.FIN_Z_BOTTOM + 2), (x, H.FIN_Z_TOP - 2), GROOVE_W)
        for axis in ("y", "-y"):
            groove(prism_y(sec), axis, HINGE_D)
    elif name.startswith("fuselage_"):
        side = 1 if name.endswith("stbd") else -1
        sax = "y" if side > 0 else "-y"
        outer = skin(P, "z", GROOVE_D) + skin(P, sax, GROOVE_D) + skin(P, "-z", GROOVE_D)
        rings = mf.Manifold()
        for x in FUSE_RINGS:
            rings = rings + slab_x(x, GROOVE_W)
        cuts.append(outer ^ rings)
        sec = mf.CrossSection()
        for z, x0, x1 in FUSE_SEAMS:
            sec = sec + band((x0, z), (x1, z), GROOVE_W)
        ds, x0, x1, z0, z1 = CREW_DOOR
        if ds == side:
            sec = sec + rect_outline(x0, z0, x1, z1, GROOVE_W)
        groove(prism_y(sec), sax, GROOVE_D)
        win = mf.CrossSection()
        for x0, x1, z0, z1 in NOSE_WINDOWS:
            win = win + mf.CrossSection.square([x1 - x0, z1 - z0]).translate([x0, z0])
        for x, z, dd in NOSE_PORTS:
            win = win + mf.CrossSection.circle(dd / 2, 32).translate([x, z])
        groove(prism_y(win), sax, 0.5)
        hat = mf.CrossSection()
        for x, L, w in ROOF_HATCHES:
            hat = hat + rect_outline(x - L / 2, -w / 2, x + L / 2, w / 2, GROOVE_W)
        groove(prism_z(hat), "z", GROOVE_D)
        dots = mf.CrossSection()
        for z, x0, x1 in FUSE_SEAMS[:1]:
            dots = dots + dots_along((x0, z), (x1, z), RIVET_OFFSET)
        adds.append(raised(P, sax) ^ prism_y(dots))
    elif name.startswith("nacelle"):
        idx = int(name[7]) - 1
        _, _, x0, L = H.NACELLES[idx]
        outer = skin(P, "z", GROOVE_D) + skin(P, "y", GROOVE_D) + skin(P, "-y", GROOVE_D) + skin(P, "-z", GROOVE_D)
        rings = mf.Manifold()
        for f in NACELLE_RINGS:
            rings = rings + slab_x(x0 + f * L, GROOVE_W)
        cuts.append(outer ^ rings)
    else:
        return P
    out = P
    for c in cuts:
        out = out - c
    for a in adds:
        out = out + a
    return out
