"""
Colour the Halifax kit and write a multi-colour Bambu Studio 3MF.

Run:  python colour.py OUT_DIR [project_settings_template.json]

Each kit part becomes one object made of several volumes, one per colour.
Colour lives in a skin SKIN mm deep under the visible surface; the rest of
the part is the base colour, so the hidden interior never needs swaps.

Scheme: Bomber Command, Mk II Series IA, 1943.
  - Upper surfaces: Dark Earth / Dark Green. The pattern is traced from
    the Revell plan view (ref/camo_plan_green.png; same shapes as the
    Temperate Land Scheme) and wraps down the fuselage sides.
  - Fuselage sides below the demarcation, undersides, fins: night black.
  - Type B roundels on the upper wings, C1 roundels on the fuselage,
    C1 fin flashes, dull red squadron codes, yellow prop tips.
"""
import os
import sys
from pathlib import Path

import manifold3d as mf
import numpy as np
from PIL import Image

import detail as D
import halifax as H
import kitlib as K
from kitlib import (clip, cs, cyl_axis, mesh_of, pose_matrix, prism_y, prism_z,
                    raster_section, text_section, to_manifold)

# ============================================================
# PARAMETERS
# ============================================================
SKIN = 0.8                   # mm, depth of coloured skin
UNDERSIDE_CLEAR = 0.4        # mm of black kept under thin edges (no camo flecks below)

FILAMENTS = {                # slot: (name, hex colour)
    1: ("Black", "#1C1C1C"),
    2: ("Dark Earth", "#6B5638"),
    3: ("Dark Green", "#3F4B2E"),
    4: ("Red", "#9E2A24"),
    5: ("Blue", "#24386B"),
    6: ("Yellow", "#E3B21C"),
    7: ("White", "#EDEDED"),
    8: ("Silk Silver", "#C7CCD1"),   # canopies and turrets: silk silver display glazing (swap for clear if wanted)
}
BLACK, EARTH, GREEN, RED, BLUE, YELLOW, WHITE, CLEAR = range(1, 9)

# Codes (no particular aircraft yet; letters from the 51 Sqn profile)
# Markings presets (pick with MARKINGS or the HALIFAX_MARKINGS env var).
# Positions are model mm on the port side; starboard mirrors about the roundel.
PRESETS = {
    "NP-G": dict(     # 158 Sqn LV917 (profile supplied by the user)
        unit="158 SQN RAF", sqn="NP", letter="G", code_h=21.0, code_z=-12.3, sqn_x=212.9, letter_x=262.4,
        roundel=(240.3, -15.4, 23.7), serial=("LV917", 288.6, 0.5, 3.1),
        demarcation=[(0, -8.0), (25, -4.0), (45, -1.0), (70, 1.4), (330, 1.4), (360, 2.0)],
        wave=(0.7, 7.5), fin_stripes=True,
        side_camo="camo_side_npg.png"),   # fuselage band traced from the NP-G profile
    "MH-E": dict(     # 51 Sqn (first profile)
        unit="51 SQN RAF", sqn="MH", letter="E", code_h=20.0, code_z=-11.0, sqn_x=214.2, letter_x=273.4,
        roundel=(243.9, -11.0, 22.8), serial=None,
        demarcation=[(0, -8.0), (26, -6.0), (45, -3.0), (60, 0.5), (90, 1.5), (130, 0.0),
                     (170, -1.5), (210, 0.5), (250, -1.0), (290, 0.5), (330, 1.5), (360, 2.0)],
        wave=(0.0, 1.0), fin_stripes=False, side_camo=None),
}
MARKINGS = os.environ.get("HALIFAX_MARKINGS", "NP-G")
MK = PRESETS[MARKINGS]
SQN_CODE, AC_LETTER = MK["sqn"], MK["letter"]
CODE_HEIGHT, CODE_Z = MK["code_h"], MK["code_z"]
SQN_CODE_X, AC_LETTER_X = MK["sqn_x"], MK["letter_x"]
FUSE_ROUNDEL = MK["roundel"]
# 4 Group fin stripes: two yellow bands, (x, z) corners on the fin side
FIN_STRIPES = [[(304.0, 17.0), (342.0, 34.8), (342.0, 21.7), (304.0, 3.3)],
               [(304.0, -8.6), (342.0, 11.1), (342.0, -2.7), (304.0, -25.0)]]
WING_ROUNDEL = (154.3, 166.0, 37.0)     # x, |y|, diameter (84 in Type B)
FIN_FLASH = (309.0, 15.0, 33.0, 7.0, 1.5)  # x start, z0, z1, red/blue width, white width
FIN_FLASH_INLAY = False      # painted on the fin's bed face now (fins print outer face down)
PROP_TIP = 3.0               # mm of yellow at the prop tips
INLAY_DEPTH = 1.2            # mm, roundel inlay depth at its shallowest point
FLASH_DEPTH = 1.8            # mm, fin flash inlay (room for the peg's hole behind the face)
FLASH_PEG = (2.5, 1.0)       # peg on its back: diameter, length (grips in a hole PEG_GRIP larger)
PEG_GRIP = 0.2               # mm on the diameter: test print 1 had +0.55 (AXLE_HOLE_TIGHT) and the
                             # fin flash fell out; the stub axles didn't grip at +0.55 either
CODE_DEPTH = 1.8             # mm, code letter inlays (deeper than 1.2 for the peg's hole)
INLAY_FIT = 0.1              # mm, radial clearance (test print 1: the G stayed in at 0.15 but loosely)
FUSE_INLAY_DEPTH = 2.4       # fuselage roundels sit deeper, to take the locating peg
ROUNDEL_PEG = (4.0, 3.0, 3.0, 3.2, 1.4)   # off-centre peg (x, z offset), peg dia, hole dia (grip), length
WING_INLAY_DEPTH = 2.0       # wing roundels: a little deeper too, for their peg
BACK_MIRROR = {"z": True, 1: False, -1: True}   # so the L/R on each inlay's back reads correctly
WING_ROUNDEL_PEG = (-6.0, 3.0, 3.0, 3.2, 1.2)  # (x, y offset; toward the thicker leading edge) ...
C1_RINGS = lambda d: [(YELLOW, d), (BLUE, d * 0.889), (WHITE, d / 3 + 1.8), (RED, d / 3)]
B_RINGS = lambda d: [(BLUE, d), (RED, d * 0.4)]

# Plan-view camo raster (Revell plan, top view crop) -> model coordinates
CAMO_PNG = Path(__file__).with_name("ref") / "camo_plan_green.png"
CAMO_ORIGIN = (940, 900)     # crop origin in page px (400 dpi)
CAMO_SCALE = 0.253           # mm per page px
CAMO_NOSE_PY = 2397          # page y of the nose tip
CAMO_CL_PX = 1995            # page x of the centreline

# Demarcation (top of the black on the fuselage sides), from the profile
DEMARCATION = MK["demarcation"]

BED = (209.0, 250.0)         # packing area (the X2D bed is 256 square; its second nozzle reaches x 20.5-256)
BED_X0 = 27.5                # every plate starts here: past the second nozzle's 20.5 plus a 6 mm brim and
                             # 1 mm spare. Bambu prints a brim with whichever filament starts the first
                             # layer; when that was Dark Earth (second nozzle), a brim on a part at x 21
                             # reached x 15 and the plate would not slice (2026-11-09)
PLATE_GAP = 8.0
NOZZLE = {EARTH: 2}            # filament slot -> nozzle: Dark Earth alone on the second (auxiliary) nozzle,
                             # which takes one colour; black/earth swaps become nozzle changes, with no
                             # flush (2026-11-08)
WING_PLATE_LAYER = "0.24"    # wing plate (wings, fuselage, tailplane, D/F loop): as the Spitfire kit; fewer
                             # layers, so fewer colour swaps

# ============================================================
# GEOMETRY HELPERS
# ============================================================
ALL = mf.Manifold.cube([1000, 1000, 1000], True)


# ============================================================
# PATTERNS
# ============================================================
def plan_camo():
    g = np.asarray(Image.open(CAMO_PNG).convert("L")) > 127
    ox, oy = CAMO_ORIGIN

    def to_xy(r, c):
        return (CAMO_NOSE_PY - (r + oy)) * CAMO_SCALE, (CAMO_CL_PX - (c + ox)) * CAMO_SCALE
    green = raster_section(g, to_xy, smooth=0.6)
    return g, green


def demarcation_z(x):
    xs, zs = zip(*DEMARCATION)
    amp, period = MK["wave"]
    return np.interp(x, xs, zs) + amp * np.abs(np.sin(np.pi * np.asarray(x) / period)) * (
        np.asarray(x) > 60)                     # scalloped edge aft of the cockpit


def roof_section(inset=2.0):
    """Plan outline of the fuselage roof, inset from the sides."""
    xs = np.linspace(0, H.FUSE_END_X, 120)
    hw = np.array([max(H.interp(H.FUSE_STATIONS, x)[1] - inset, 0.2) for x in xs])
    return cs([np.r_[np.c_[xs, hw], np.c_[xs[::-1], -hw[::-1]]]])


def side_trace():
    """The scheme's side-profile camo trace, if it's here. ref/ is git-ignored and this one was
    never committed, so a fresh checkout lacks it. Only the old split-fuselage halves were painted
    from it; the current fuselage sections and canopies paint from the plan trace."""
    f = MK.get("side_camo")
    if f and not CAMO_PNG.with_name(f).exists():
        print(f"note: {f} not found; painting from the plan trace only", file=sys.stderr, flush=True)
        return False
    return bool(f)


def side_camo(g, side):
    """Green region on one fuselage side in (x, z): the plan pattern unfolded
    down the side, cut off at the demarcation line."""
    ox, oy = CAMO_ORIGIN
    xs = np.arange(-2, 365, 0.25)
    zs = np.arange(-40, 20, 0.25)
    X, Z = np.meshgrid(xs, zs)
    hw = np.array([H.interp(H.FUSE_STATIONS, x)[1] for x in xs])
    top = np.array([H.interp(H.FUSE_STATIONS, x)[2] for x in xs])
    Y = side * (hw[None, :] + np.clip(top[None, :] - Z, 0, None))
    col = np.round(CAMO_CL_PX - Y / CAMO_SCALE - ox).astype(int)
    row = np.round(CAMO_NOSE_PY - X / CAMO_SCALE - oy).astype(int)
    ok = (row >= 0) & (row < g.shape[0]) & (col >= 0) & (col < g.shape[1])
    val = np.zeros_like(X, bool)
    val[ok] = g[row[ok], col[ok]]
    if side_trace():                         # traced from the aircraft's own profile (same grid)
        val = np.asarray(Image.open(CAMO_PNG.with_name(MK["side_camo"])).convert("L"))[::-1] > 127
    above = Z > demarcation_z(X)
    to_xz = lambda r, c: (xs[0] + c * 0.25, zs[0] + r * 0.25)
    green = raster_section(val & above, to_xz, smooth=0.6).simplify(0.12)
    band = raster_section(above, to_xz).simplify(0.12)
    return green, band


def spine_plan(g, plan_green, inset=2.0):
    """Plan section of green for the spine pieces: the plan pattern across the roof, and outboard
    of the roof edge the colour at that edge, so each colour runs straight down the side to the
    black (mixing the plan roof with the side trace gave a harlequin look)."""
    ox, oy = CAMO_ORIGIN
    xs = np.arange(-2, 365, 0.25)
    hw = np.array([max(H.interp(H.FUSE_STATIONS, x)[1] - inset, 0.2) for x in xs])
    out = plan_green ^ roof_section(inset)
    for s in (1, -1):
        Y = s * (hw - 0.3)
        col = np.round(CAMO_CL_PX - Y / CAMO_SCALE - ox).astype(int)
        row = np.round(CAMO_NOSE_PY - xs / CAMO_SCALE - oy).astype(int)
        ok = (row >= 0) & (row < g.shape[0]) & (col >= 0) & (col < g.shape[1])
        v = np.zeros(len(xs), bool)
        v[ok] = g[row[ok], col[ok]]
        start = None
        for i, on in enumerate(list(v) + [False]):
            if on and start is None:
                start = i
            elif not on and start is not None:
                a, b = start, i - 1
                pts = [(xs[j], s * hw[j]) for j in range(a, b + 1)]
                pts += [(xs[b], s * 100.0), (xs[a], s * 100.0)]
                out = out + cs([np.array(pts if s > 0 else pts[::-1])])
                start = None
    return out


def roof_camo():
    """Plan section of green across the fuselage roof: the side trace's colour along the top
    edge, carried straight over the spine (None when the scheme has no side trace)."""
    if not side_trace():
        return None
    val = np.asarray(Image.open(CAMO_PNG.with_name(MK["side_camo"])).convert("L"))[::-1] > 127
    xs = np.arange(-2, 365, 0.25)
    zs = np.arange(-40, 20, 0.25)
    top = np.array([H.interp(H.FUSE_STATIONS, x)[2] for x in xs])
    rows = np.clip(np.round((top - 1.0 - zs[0]) / 0.25).astype(int), 0, len(zs) - 1)
    g = val[rows, np.arange(len(xs))]
    sec, start = mf.CrossSection(), None
    for i, v in enumerate(list(g) + [False]):
        if v and start is None:
            start = xs[i]
        elif not v and start is not None:
            x_end = xs[i] if i < len(xs) else xs[-1] + 0.25
            sec = sec + mf.CrossSection.square([x_end - start, 60.0]).translate([start, -30.0])
            start = None
    return sec


# ============================================================
# PAINTING
# ============================================================
SKIN_OUT = 0.05             # mm, skins reach just past the surface: no coplanar faces, so no
                             # zero-thickness slivers of the base colour left on the outside


def skins(P):
    return {
        "up": P.translate([0, 0, SKIN_OUT]) - P.translate([0, 0, -SKIN]),
        "+y": P.translate([0, SKIN_OUT, 0]) - P.translate([0, -SKIN, 0]),
        "-y": P.translate([0, -SKIN_OUT, 0]) - P.translate([0, SKIN, 0]),
    }


def socket_region(name):
    """Everything inside a roundel socket: painted black so the gap round the inlay reads black."""
    if name.startswith("wing_outer"):
        s = 1 if name.endswith("stbd") else -1
        x, y, d = WING_ROUNDEL
        return cyl_axis(x, s * y, d / 2 + 0.05, "z")
    if name.startswith("fuselage_rear"):
        x, z, d = FUSE_ROUNDEL
        return cyl_axis(x, z, d / 2 + 0.05, "y")
    return None


def spine_region():
    """Everything above the camo line on the fuselage (the old spine pieces' split)."""
    pts = [(float(x), float(H.spine_z(x))) for x in np.arange(-6.0, 401.0, 0.5)] + [(400.0, 80.0), (-6.0, 80.0)]
    return prism_y(cs([np.array(pts)]))


def exhaust_region(idx, side, P):
    """The exhaust bar and shroud on a nacelle half: whatever stands outside the bare nacelle
    body along the exhaust run."""
    yc, zc, x0, length = H.NACELLES[idx]
    body = to_manifold(H.mesh(H.nacelle_body(zc, x0, length).translate((0, yc * side, 0))))
    zm = zc + H.EXH_Z
    r = max(H.EXH_SHROUD_D, H.EXH_H) / 2 + 0.5
    zone = K.box(x0 + H.EXH_X0 - 1.0, x0 + H.EXH_X0 + H.EXH_LEN + 1.0, -400, 400, zm - r, zm + r)
    return (P - body) ^ zone


def colour_part(name, P, pat):
    S = skins(P)
    up = S["up"]
    x0, y0, z0, x1, y1, z1 = P.bounding_box()
    plan = prism_z(clip(pat["plan_green"], x0, y0, x1, y1))
    pat = dict(pat, side={s: tuple(clip(c, x0, z0, x1, z1) for c in v) for s, v in pat["side"].items()})
    if not name.startswith("fuselage_"):    # thin edges: keep camo off the underside
        up = up - (P - P.translate([0, 0, UNDERSIDE_CLEAR]))
    camo_up = [(EARTH, up), (GREEN, up ^ plan)]
    sock = socket_region(name)
    sock_op = [(BLACK, sock)] if sock is not None else []
    if name.startswith(("wing_", "tailplane")):
        return paint(P, list(camo_up) + sock_op)
    if name in H.FUSE_SECTIONS:                          # codes are inlays
        if H.SPINE_PIECES:
            return {BLACK: P}                           # black body; camo on the clip-on spine
        # camo painted on above the line, as the spine pieces were: the plan pattern across the
        # roof, each colour carried straight down the sides to the black
        skin = (up + S["+y"] + S["-y"]) ^ spine_region()
        return paint(P, [(EARTH, skin), (GREEN, skin ^ prism_z(pat["spine_plan"]))] + sock_op)
    if name.startswith("spine_"):
        # camo painted on (the purge is worth it): the plan pattern across the roof, each colour
        # carried straight down the sides to the black, so from above the colours cross the
        # fuselage at an angle and run on into the wings
        skin = up + S["+y"] + S["-y"]
        return paint(P, [(GREEN, skin ^ prism_z(pat["spine_plan"]))], base=EARTH)
    if name.startswith("fuselage_"):
        s = 1 if name.endswith("stbd") else -1
        side = S["+y"] if s > 0 else S["-y"]
        green_s, band = pat["side"][s]
        roof = up ^ prism_z(roof_section())         # roof only: keeps clear of the side skin
        roof_green = prism_z(pat["roof_green"]) if pat.get("roof_green") is not None else plan
        ops = [(EARTH, side ^ prism_y(band)), (GREEN, side ^ prism_y(green_s)),
               (EARTH, roof), (GREEN, roof ^ roof_green)]
        # codes read "MH (o) E" from both sides: squadron code aft on starboard
        rx = FUSE_ROUNDEL[0]
        mirror = s > 0
        sx = SQN_CODE_X if s < 0 else 2 * rx - SQN_CODE_X
        ax = AC_LETTER_X if s < 0 else 2 * rx - AC_LETTER_X
        for txt, cx in ((SQN_CODE, sx), (AC_LETTER, ax)):
            ops.append((RED, side ^ prism_y(text_section(txt, CODE_HEIGHT, cx, CODE_Z, mirror))))
        if MK["serial"]:
            txt, x, z, h = MK["serial"]
            ops.append((RED, side ^ prism_y(text_section(txt, h, x if s < 0 else x, z, mirror))))
        return paint(P, ops + sock_op)
    if name.startswith("nacelle"):
        idx = int(name[7]) - 1
        zc = H.NACELLES[idx][1]
        upper = mf.Manifold.cube([1000, 1000, 500]).translate([-500, -500, zc - 1.0])
        # the whole outer skin above the line, including the forward-facing cowling front
        # (up/side skins alone left the front black with a ragged edge)
        skin = (ALL - K.inner_core(P, SKIN)) ^ upper
        ops = [(EARTH, skin), (GREEN, skin ^ plan)]
        if not H.EXHAUST_SEPARATE:                 # exhaust shroud printed on: black, not camo
            ops.append((BLACK, exhaust_region(idx, 1 if "_stbd_" in name else -1, P)))
        return paint(P, ops)
    if name.startswith("fin_"):
        s = 1 if name.endswith("stbd") else -1
        side = (S["+y"] if s > 0 else S["-y"]) ^ H_box(-100, 500, *((H.FIN_Y, 200) if s > 0 else (-200, -H.FIN_Y)), -100, 100)
        # outer face only (the inner face and the dovetail rod stay black). The fins print outer face down, so the
        # stripes and the flash (over the yellow) are the first SKIN of layers: crisp on the bed,
        # and only a few layers of colour swaps (the flash was a snap-in inlay until 2026-11-10)
        ops = []
        if MK["fin_stripes"]:
            for quad in FIN_STRIPES:
                ops.append((YELLOW, side ^ prism_y(cs([quad]))))
        x0, z0, z1, w, ww = FIN_FLASH
        rect = lambda a, b: cs([[(a, z0), (b, z0), (b, z1), (a, z1)]])
        ops += [(RED, side ^ prism_y(rect(x0, x0 + 2 * w + ww))),
                (WHITE, side ^ prism_y(rect(x0 + w, x0 + w + ww))),
                (BLUE, side ^ prism_y(rect(x0 + w + ww, x0 + 2 * w + ww)))]
        return paint(P, ops)
    if name.startswith("prop") and not name.startswith("prop_shaft"):
        idx = int(name[4]) - 1
        yc, zc, x0, _ = H.NACELLES[idx]
        s = 1 if name.endswith("stbd") else -1
        r_in = H.PROP_D / 2 - PROP_TIP
        core = (mf.Manifold.cylinder(200, r_in, r_in, 96).rotate([0, 90, 0])
                .translate([-100, s * yc, zc]))
        return paint(P, [(YELLOW, P - core)])
    if name.startswith("df_loop"):      # one camo colour (Dark Earth), not black
        return {EARTH: P}
    if name in ("canopy", "canopy_side", "canopy_rear"):   # cockpit glazing: frames in the camo
        f = frames(name, P)
        return paint(P, [(EARTH, f), (GREEN, f ^ prism_z(pat["spine_plan"]))], base=CLEAR)
    if name in CLEAR_PARTS:
        return paint(P, [(BLACK, frames(name, P))], base=CLEAR)
    if name == "stand_base":
        return stand_paint(P, pat)
    return {BLACK: P}


# ============================================================
# DISPLAY STAND (plinth: camo top, yellow pinstripe, raised white badge and name)
# ============================================================
STAND_TITLE = "HANDLEY PAGE HALIFAX"
STAND_SUBTITLE = "B MK II  SERIES IA"
STAND_TEXT_H = (6.2, 4.6, 3.4)          # mm, the three lines (scaled with the smaller plinth)
STAND_TEXT_Y = (-19.8, -29.6, -37.6)    # line centres (y, viewer side is -y)
STAND_RELIEF = 0.6                      # mm, raised lettering and badge
STAND_STRIPE = (5.0, 1.2)               # pinstripe inset from the edge, width
STAND_BADGE = (-38.0, 16.0, 0.13, 25.0)   # x from base centre, y, scale, heading (deg)


def stand_lines():
    serial = MK["serial"][0] if MK["serial"] else ""
    third = "  \u00b7  ".join(t for t in (MK["unit"], f"{SQN_CODE}-{AC_LETTER}", serial) if t)
    return (STAND_TITLE, STAND_SUBTITLE, third)


def halifax_plan():
    """Top-view silhouette of the aircraft, from the shape tables (model x, y)."""
    out = mf.CrossSection()
    st = np.array([(r[0], r[1]) for r in H.FUSE_STATIONS])
    out = out + cs([np.r_[st, st[::-1] * [1, -1]]])
    pl = np.array(H.PLANFORM)
    for sg in (1, -1):
        le = np.c_[pl[:, 1], sg * pl[:, 0]]
        te = np.c_[pl[:, 1] + pl[:, 2], sg * pl[:, 0]]
        out = out + cs([np.r_[le, te[::-1]]])
        y_tip = H.FIN_Y
        (rx, rc), (tx, tc) = H.TAIL_ROOT, H.TAIL_TIP
        out = out + cs([np.array([(rx, 0), (tx, sg * y_tip), (tx + tc, sg * y_tip), (rx + rc, 0)])])
        out = out + cs([np.array([(H.FIN_X_LE, sg * (y_tip - 1.8)), (H.FIN_X_LE + H.FIN_CHORD, sg * (y_tip - 1.8)),
                                  (H.FIN_X_LE + H.FIN_CHORD, sg * (y_tip + 1.8)), (H.FIN_X_LE, sg * (y_tip + 1.8))])])
        for yc, _, x0, L in H.NACELLES:
            prof = np.array(H.NACELLE_PROFILE)
            x = x0 + prof[:, 0] * L
            hw = prof[:, 1] * H.NACELLE_W / 2
            out = out + cs([np.r_[np.c_[x, sg * yc + hw], np.c_[x[::-1], sg * yc - hw[::-1]]]])
    return out


def stand_level(M, sign=1):
    S, _, _ = H.stand_frame()
    c = [H.STAND_X, 0.0, S.z]
    return M.translate([-v for v in c]).rotate([0, sign * H.STAND_PITCH, 0]).translate(c)


def stand_regions():
    """Level-frame sections: (raised badge+text, pinstripe), placed on the plinth."""
    _, top, bcx = H.stand_frame()
    bl, bw, _ = H.STAND_BASE
    raised = mf.CrossSection()
    for txt, h, y in zip(stand_lines(), STAND_TEXT_H, STAND_TEXT_Y):
        raised = raised + text_section(txt, h, bcx, y)
    bx, by, k, hd = STAND_BADGE
    sil = halifax_plan()
    lo = np.array(sil.bounds()[:2]); hi = np.array(sil.bounds()[2:])
    ctr = (lo + hi) / 2
    # nose toward +y (flying away from the viewer), turned a little for movement
    sil = sil.translate(list(-ctr)).scale([k, k]).rotate(90 + hd).translate([bcx + bx, by])
    raised = raised + sil
    inset, w = STAND_STRIPE
    r = H.STAND_BASE_R - inset
    core = mf.CrossSection.square([bl - 2 * inset - 2 * r, bw - 2 * inset - 2 * r], True)
    outer = core.offset(r, mf.JoinType.Round, circular_segments=48)
    stripe = (outer - outer.offset(-w, mf.JoinType.Round, circular_segments=48)).translate([bcx, 0])
    return raised, stripe


def stand_decorate(P):
    """Add the raised badge and lettering to the plinth (model frame in, model frame out)."""
    _, top, _ = H.stand_frame()
    raised, _ = stand_regions()
    relief = raised.extrude(STAND_RELIEF + 0.2).translate([0, 0, top - 0.2])
    return P + stand_level(relief, -1)


def stand_paint(P, pat):
    _, top, _ = H.stand_frame()
    L = stand_level(P)
    raised, stripe = stand_regions()
    above = mf.Manifold.cube([1000, 1000, 50]).translate([-500, -500, top + 0.01])
    deck = (L.translate([0, 0, SKIN_OUT]) - L.translate([0, 0, -SKIN])) - above          # flat top skin of the plinth
    ops = [(GREEN, deck ^ prism_z(pat["plan_green"])),
           (YELLOW, deck ^ prism_z(stripe)),
           (WHITE, above ^ prism_z(raised.offset(0.05, mf.JoinType.Round)))]
    # no black on the plinth (sides and underside Dark Earth): it shares the props/gear plate
    return {c: stand_level(v, -1) for c, v in paint(L, ops, base=EARTH).items()}


# ============================================================
# GLAZING FRAMES (black frame lines through a clear skin)
# ============================================================
CLEAR_PARTS = ("canopy", "canopy_side", "canopy_rear", "nose_glazing", "turret_dorsal", "turret_tail", "astrodome")
FRAME_W = 0.6                # mm
# Pilot's canopy, measured from the Revell side and plan views (mm, assembled frame)
CANOPY_GLASS_X = (40.0, 72.1)               # rear rim at x1 (the front edge is the level bottom rail)
CANOPY_XFRAMES = [61.6]                     # hoop at the step (over the roof too)
CANOPY_ROOF_BARS = [(2.8, 53.0)]            # (|y|, x0): roof bars, from the screen's lower frame to the rear
# Windscreen lower frame seen from above (x, |y|): from the cant rail's front end, in to the
# roof bars, then the V notch to the apex. Every bar ends on another frame, as on the real thing.
# cockpit glazing (Revell side view, reference photos and the user's sketch): the front glazing has
# a level bottom edge; at the step it drops square to the two side windows, which come down below
# the camo line; cant rail at z 7.1 runs right round the front
CANOPY_HOOP = 7.1                            # cant rail
CANOPY_STEP_X = 61.6                         # front glazing / side windows: the square step
FRONT_GLASS_BOTTOM = 3.5                     # front glazing's bottom edge (level, = H.CANOPY_STEP z)
CANOPY_LOWER_XFRAMES = [67.0]                # upright between the two side windows
# windscreen: 5 panes wrapping round the front (a centre V, then two each side, the outer one back
# to the step). Dividers as angles round a vertical axis at x = WS_AXIS_X (0 = ahead), (bottom, top)
WS_AXIS_X = 60.0
WS_BOTTOM = FRONT_GLASS_BOTTOM
WS_DIVIDERS = [(5.0, 14.0), (45.0, 47.0)]
# Rear roof glazing (Revell plan, and the user's photo): centre panel with the astrodome,
# side panels split by diagonals from the rear outer corner to the front inner corner
REAR_GLASS_X = (73.6, 91.0)
REAR_BARS = 5.1                             # |y| of the centre-panel bars
REAR_EDGE = 10.4                            # |y| beyond this is frame (the sill of the panel)
NOSE_XFRAMES = [(12.4, None)]                # rear rim (NP-G profile, Wikipedia: no frame across the nose)
NOSE_ZFRAMES = [-18.3]                       # upper edge of the gun slot (horizontal)
# lower half: three oval windows (photos of the nose): a big one on the chin and a narrow
# upright one either side. Each: ray origin inside, outward direction, length, width (mm).
NOSE_TIP = (0.0, 0.0, -20.6)
NOSE_OVALS = [((6.0, 0.0, -21.0), (-0.75, 0.0, -0.65), 6.0, 4.0),     # chin oval
              ((6.0, 0.0, -21.0), (-0.50, 0.80, -0.35), 5.0, 2.2),     # side ovals, long axis aimed at the tip
              ((6.0, 0.0, -21.0), (-0.50, -0.80, -0.35), 5.0, 2.2)]
NOSE_HOOP = ((0.3, -18.3), (12.4, -23.5))   # second line: from the tip, down and aft round both sides


def oval_frame(P, origin, out, ln, wd, w, aim=None):
    """Oval frame ring where a ray from origin along out meets the part, projected along out."""
    import trimesh
    V, F = mesh_of(P)
    m = trimesh.Trimesh(V, F)
    o, d = np.array(origin, float), np.array(out, float)
    d /= np.linalg.norm(d)
    loc, ray, _ = m.ray.intersects_location([o], [d])
    c = loc[np.argmax((loc - o) @ d)]
    up = np.array(aim, float) - c if aim is not None else np.array([0.0, 0.0, 1.0])
    up = up - (up @ d) * d
    up /= np.linalg.norm(up)
    side = np.cross(up, d)
    core = mf.CrossSection.square([0.01, ln - wd], True).offset(wd / 2, mf.JoinType.Round, circular_segments=32)
    ring = core.offset(w / 2, mf.JoinType.Round) - core.offset(-w / 2, mf.JoinType.Round)
    pr = mf.Manifold.extrude(ring, 10.0).translate([0, 0, -5.0])
    R = np.column_stack([side, up, d, c])
    return pr.transform(R)


def windscreen_dividers(P, top_z, w):
    """Divider frames on the canopy's front band: planar slabs through a bottom and a top point on
    the surface (found by rays out from the axis), so each frame runs edge to edge."""
    import trimesh
    V, F = mesh_of(P)
    m = trimesh.Trimesh(V, F)

    def surf(deg, z):
        a = np.radians(deg)
        o = np.array([WS_AXIS_X, 0.0, z])
        d = np.array([-np.cos(a), np.sin(a), 0.0])
        loc, _, _ = m.ray.intersects_location([o], [d])
        return loc[np.argmax((loc - o) @ d)]

    out = mf.Manifold()
    band = H_box(-100, 400, -100, 100, WS_BOTTOM - w / 2, top_z + w / 2)
    for b_deg, t_deg in WS_DIVIDERS:
        for sg in (1, -1):
            B, T = surf(sg * b_deg, WS_BOTTOM + 0.7), surf(sg * t_deg, top_z)   # just above the bottom rail
            mid = (B + T) / 2
            radial = np.array([mid[0] - WS_AXIS_X, mid[1], 0.0])
            n = np.cross(T - B, radial)
            n /= np.linalg.norm(n)
            # slab: thin box along the plane, centred at mid, oriented by (T-B, radial, n)
            u = (T - B) / np.linalg.norm(T - B)
            r = np.cross(n, u)
            box = mf.Manifold.cube([40, 40, w], True)
            M = np.column_stack([u, r, n, mid])
            slab_ = box.transform(M)
            near = H_box(-100, 400, -100, 100, -100, 100) ^ mf.Manifold.cube([40, 40, 40], True).transform(
                np.column_stack([u, r, n, mid + r * 20 * np.sign(r @ radial)]))
            out = out + (slab_ ^ near ^ band)
    return out


def frames(name, P):
    sk = ALL - K.inner_core(P, 0.6)        # reaches past the surface: no clear slivers
    W = FRAME_W
    if name in ("canopy", "canopy_side"):
        g0, g1 = CANOPY_GLASS_X
        hz = CANOPY_HOOP
        sx = CANOPY_STEP_X
        f = H_box(-100, g0, -100, 100, -100, 100) + H_box(g1, 400, -100, 100, -100, 100)
        f = f + slab("z", hz)                                                 # cant rail, round the front
        for x in CANOPY_XFRAMES:
            f = f + slab("x", x)
        for x in CANOPY_LOWER_XFRAMES:
            f = f + (slab("x", x) ^ H_box(-100, 400, -100, 100, -100, hz))
        f = f + (H_box(-100, sx, -100, 100, -100, FRONT_GLASS_BOTTOM + 0.6))   # front glazing's bottom rail
        f = f + H_box(sx, 400, -100, 100, -100, H.CANOPY_FLOOR + 0.6)        # side windows' sill
        if name == "canopy":
            f = f + windscreen_dividers(P, hz, W)
        # roof bars, from the horizontal frame to the rear
        roof = mf.CrossSection()
        for yb, x0 in CANOPY_ROOF_BARS:
            for sg in (1, -1):
                roof = roof + D.band((x0, sg * yb), (g1, sg * yb), W)
        f = f + (D.prism_z(roof) ^ H_box(-100, 400, -100, 100, hz, 100))
        return sk ^ f
    if name == "canopy_rear":
        g0, g1 = REAR_GLASS_X
        f = (H_box(-100, g0, -100, 100, -100, 100) + H_box(g1, 400, -100, 100, -100, 100)
             + H_box(-100, 400, REAR_EDGE, 100, -100, 100) + H_box(-100, 400, -100, -REAR_EDGE, -100, 100))
        bars = mf.CrossSection()
        for sg in (1, -1):
            bars = bars + D.band((g0, sg * REAR_BARS), (g1, sg * REAR_BARS), W)
            bars = bars + D.band((g1, sg * (REAR_EDGE + 0.2)), (g0, sg * REAR_BARS), W)
        x, r = H.ASTRODOME                              # the astrodome on it stays clear
        return (sk ^ (f + D.prism_z(bars))) - cyl_axis(x, 0, r + 0.3, "z")
    if name == "nose_glazing":
        f = mf.Manifold()
        for x, zmin in NOSE_XFRAMES:
            f = f + (slab("x", x) if zmin is None else slab("x", x) ^ H_box(-100, 400, -100, 100, zmin, 100))
        for z in NOSE_ZFRAMES:
            f = f + slab("z", z)
        for o, d, ln, wd in NOSE_OVALS:
            f = f + oval_frame(P, o, d, ln, wd, W, aim=NOSE_TIP)
        f = f + D.prism_y(D.band(*NOSE_HOOP, W))
        return sk ^ f
    if name == "turret_dorsal":
        x = H.DORSAL_X
        _, _, top, _, _ = H.interp(H.FUSE_STATIONS, x)
        # Boulton Paul mid-upper (photo of LL505): deep black base band; on the gun side a big
        # clear sighting panel between black gun slots; the other half in "orange segment"
        # frames meeting at a hub on top. The guns point aft (+x), so +x is the gun side.
        base = top - 1.2
        f = H_box(-100, 400, -100, 100, -100, base + 3.0)
        for sg in (1, -1):                       # gun slots either side of the clear sighting panel
            f = f + H_box(x + 2.0, 400, *sorted((sg * 2.4, sg * 4.4)), -100, 100)
        rear = H_box(-100, x + 0.3, -100, 100, -100, 100)
        for ang in (90, 120, 150, 180, 210, 240, 270):                     # meridian frames
            bar = (mf.Manifold.cube([60, W, 60], True).translate([30, 0, 0]).rotate([0, 0, ang])
                   .translate([x, 0, base + 10]))
            f = f + (bar ^ rear)
        f = f + mf.Manifold.cylinder(60, 2.2, 2.2, 32).translate([x, 0, base])   # hub on top
        f = f - mf.Manifold.cylinder(60, 1.4, 1.4, 32).translate([x, 0, base])
        return sk ^ f
    if name == "turret_tail":
        # Type E frames (Revell side view): base ring, front post, waist rail, roof centre bar
        f = (H_box(-100, 400, -100, 100, -100, H.TT_FLOOR + 1.2) + slab("x", H.TT_X0 + 4.0)
             + (slab("z", H.TT_FLOOR + 8.0) ^ H_box(H.TT_X0 + 4.0, 400, -100, 100, -100, 100))
             + (slab("y", 0.0) ^ H_box(-100, 400, -100, 100, H.TT_FLOOR + 8.0, 100))
             + H_box(-100, H.TT_X0 + 1.2, -100, 100, -100, 100))
        return sk ^ f
    return mf.Manifold()


# ============================================================
# ROUNDEL INLAYS (separate multi-colour discs, as PB94 does)
# ============================================================
def thickest_point(sec):
    """Centre of the largest circle inside a flat section (where a peg fits best), and its radius."""
    from matplotlib.path import Path as MPath
    from scipy import ndimage as ndi
    x0, z0, x1, z1 = sec.bounds()
    h = 0.05
    X, Z = np.meshgrid(np.arange(x0 - 1, x1 + 1, h), np.arange(z0 - 1, z1 + 1, h))
    pts = np.c_[X.ravel(), Z.ravel()]
    inside = np.zeros(len(pts), bool)
    for poly in sec.to_polygons():
        inside ^= MPath(np.array(poly)).contains_points(pts)
    d = ndi.distance_transform_edt(inside.reshape(X.shape)) * h
    i = np.unravel_index(d.argmax(), d.shape)
    return (float(X[i]), float(Z[i])), float(d.max())


def add_peg(P, plug, floor, x, z):
    """Gripping peg standing square on the socket floor and a hole in the back of a side (y)
    inlay, as on the roundels: the inlay's back stays flat for the bed (its face follows the skin)."""
    pd, pl = FLASH_PEG
    peg, hole = K.peg_on_floor(floor, x, z, pd, pl, pd + PEG_GRIP, pl + 0.15)
    return P + peg, plug - hole


def inlays_for(name, P):
    """Returns (P, [(inlay_name, vols, rotation_to_print_pose)])."""
    out = []
    if name.startswith("wing_outer"):
        s = 1 if name.endswith("stbd") else -1
        x, y, d = WING_ROUNDEL
        hand = "R" if s > 0 else "L"
        # the mid-joint key runs under the roundel: its slot opens up into the socket and the
        # roundel's back is notched over it (hidden once pressed in), as on the Spitfire's wings
        cav = (to_manifold(H.mesh(H.wing_split(s)[1])), to_manifold(H.mesh(H.wing_split(s, slot_top=30.0)[1])))
        P, vols, plug, prot = K.make_inlay(P, (x, s * y), d, B_RINGS(d), "z", 1, WING_INLAY_DEPTH,
                                     INLAY_FIT, WING_ROUNDEL_PEG, (hand, 6.0, 6.0, -4.0, BACK_MIRROR["z"]), cav)
        out.append((f"roundel_wing_{name.split('_')[-1]}", vols, prot, plug))
    if name.startswith("fin_") and FIN_FLASH_INLAY:
        # fin flash (red/white/blue) as one snap-in inlay: press fit plus two gripping pegs on its
        # back, one behind the red and one behind the blue (one central peg let it fall out)
        s = 1 if name.endswith("stbd") else -1
        x0, z0, z1, w, ww = FIN_FLASH
        rect = lambda a, b: mf.CrossSection([np.array([[a, z0], [b, z0], [b, z1], [a, z1]])])
        P, plug, frot, floor = K.make_section_inlay(P, rect(x0, x0 + 2 * w + ww), s, FLASH_DEPTH, INLAY_FIT)
        for px in (x0 + w / 2, x0 + 1.5 * w + ww):
            P, plug = add_peg(P, plug, floor, px, (z0 + z1) / 2)
        vols = K.paint(plug, [(WHITE, prism_y(rect(x0 + w, x0 + w + ww))),
                              (BLUE, prism_y(rect(x0 + w + ww, x0 + 2 * w + ww)))], RED)
        out.append((f"flash_fin_{name.split('_')[-1]}", vols, frot, plug))
    if name == "fuselage_rear":
        for s, tag in ((-1, "port"), (1, "stbd")):
            x, z, d = FUSE_ROUNDEL
            hand = "R" if s > 0 else "L"
            P, vols, plug, prot = K.make_inlay(P, (x, z), d, C1_RINGS(d), "y", s, FUSE_INLAY_DEPTH,
                                         INLAY_FIT, ROUNDEL_PEG, (hand, 6.0, -4.0, -3.0, BACK_MIRROR[s]))
            out.append((f"roundel_fuselage_{tag}", vols, prot, plug))
            # squadron code and aircraft letter as red press-in inlays, read nose-to-tail
            rx = FUSE_ROUNDEL[0]
            sx = SQN_CODE_X if s < 0 else 2 * rx - SQN_CODE_X
            ax = AC_LETTER_X if s < 0 else 2 * rx - AC_LETTER_X
            n = 0
            for txt, cx in ((SQN_CODE, sx), (AC_LETTER, ax)):
                for letter in sorted(text_section(txt, CODE_HEIGHT, cx, CODE_Z, s > 0).decompose(),
                                     key=lambda q: q.bounds()[0]):
                    n += 1
                    P, plug, lrot, floor = K.make_section_inlay(P, letter, s, CODE_DEPTH, INLAY_FIT)
                    (px, pz), r = thickest_point(letter)
                    if r >= (FLASH_PEG[0] + PEG_GRIP) / 2 + 0.6:            # peg where the stroke is thickest
                        P, plug = add_peg(P, plug, floor, px, pz)
                    out.append((f"code_{tag}_{n}", {RED: plug}, lrot, plug))
    return P, out


def engrave_serial(name, P):
    """Serial number engraved 0.3 mm into the rear fuselage and spine (too small to inlay)."""
    if not MK["serial"] or not name.startswith(("fuselage_rear", "spine_")):
        return P
    txt, x, z, h = MK["serial"]
    for s in (1, -1):
        sk = D.skin(P, "y" if s > 0 else "-y", 0.3)
        P = P - (sk ^ prism_y(text_section(txt, h, x, z, s > 0)))
    return P


# ============================================================
# 3MF WRITER (Bambu Studio project layout)
# ============================================================
def paint(P, ops, base=None):
    return K.paint(P, ops, BLACK if base is None else base)


def H_box(x0, x1, y0, y1, z0, z1):
    return K.box(x0, x1, y0, y1, z0, z1)


def slab(axis, at, w=None):
    return K.slab(axis, at, FRAME_W if w is None else w)


def make_inlay(P, centre, d, rings, axis, side=1):
    return K.make_inlay(P, centre, d, rings, axis, side, INLAY_DEPTH, INLAY_FIT)


def pack(items):
    """Shelf-pack a group as it lies and turned 90 degrees; keep whichever needs fewer plates (the
    long nacelle halves only fit the 209 mm width two rows deep, turned)."""
    plain = K.pack(items, BED, PLATE_GAP)
    turned = K.pack([(n, (h, w)) for n, (w, h) in items], BED, PLATE_GAP)
    turned = [[(n, x, y, not r) for n, x, y, r in plate] for plate in turned]
    return turned if len(turned) < len(plain) else plain


# Print settings: the template is the X2D 0.20 mm Standard profile; these replace it
PRINT_OVERRIDES = {
    "layer_height": "0.16",
    "sparse_infill_pattern": "gyroid",
    "sparse_infill_density": "15%",
    "enable_support": "0",
    "brim_type": "auto_brim",
}
TALL_BRIM = {"brim_type": "outer_only", "brim_width": "6"}


def object_settings(name):
    """Per-object overrides, written into the 3MF next to each object."""
    s = {}
    if name in CLEAR_PARTS or name.startswith(("guns_", "prop", "exhaust", "main_gear", "main_wheel", "fin_", "stand_post",
                                              "tail_gear", "tail_wheel", "pin_", "wheel_up", "key_")):
        # fine detail and silk sheen; whole plates share one height (the prime tower needs that)
        s["layer_height"] = "0.12"
    if name in H.FUSE_SECTIONS:
        s.update(TALL_BRIM, wall_loops="3")
    if name.startswith(("wing_", "fuselage_", "tailplane", "df_loop")):
        s["layer_height"] = WING_PLATE_LAYER
    if name.startswith("spine_"):
        s.update(TALL_BRIM)                         # standing on an end face
    if name.startswith("wing_") and H.WING_POSE == "end":
        s.update(TALL_BRIM)
    if name.startswith("tailplane_"):               # halves stand on their root faces
        s.update(TALL_BRIM)
    return s


def write_3mf(path, objects, plates, template):
    for o in objects:
        o["settings"] = object_settings(o["name"])
    K.write_3mf(path, objects, plates, template, FILAMENTS, "Halifax B.II Srs IA snap kit 1:60",
                PRINT_OVERRIDES, nozzle_map=NOZZLE)


# ============================================================
# PAINT ONLY THE OUTSIDE (2026-11-11)
# ============================================================
# The skins above are taken from each part alone, so they also caught its internal faces: the
# joint faces between sections, key-slot floors, the wing-root tongues, the nacelle halves' split
# faces and wing notch, the fin-rod slot. Now paint is kept only within SKIN of the assembled
# aircraft's outside (every part in place, the fit gaps closed and the enclosed slots filled), with
# INNER_BLACK of black next to every internal face, so a thin wall (the skin over the fin-rod
# slot) shows black inside. A joint face keeps a SKIN-deep band of colour at its outer edge, so
# the colour runs on across the join. Nacelles are black wherever the wing is above them.
GAP_CLOSE = 0.18             # mm: closes fit gaps up to 0.36 between parts; 0.5 mm panel lines stay open
INNER_BLACK = 0.45           # mm of black kept next to an internal face (about one line width)
UNMASKED = ("stand_base", "spine_")   # no black base, or not on the aircraft


def leaf(P):
    """Evaluate a Manifold and keep only its points and triangles: drops the operation history
    and the per-triangle provenance. (Rebuilt straight from to_mesh(), with that provenance,
    painting fuselage_front against its neighbours needed over 100 GB.)"""
    V, F = mesh_of(P)
    return mf.Manifold(mf.Mesh(vert_properties=np.array(V, np.float32, order="C"),   # writable copies
                               tri_verts=np.array(F, np.uint32, order="C")))


def dilate(P, r):
    moves = ([r, 0, 0], [-r, 0, 0], [0, r, 0], [0, -r, 0], [0, 0, r], [0, 0, -r])
    return mf.Manifold.batch_boolean([P] + [P.translate(v) for v in moves], mf.OpType.Add)


def _overlaps(a, b, m=0.0):
    return all(a[i] - m <= b[i + 3] and b[i] - m <= a[i + 3] for i in range(3))


class Outside:
    """Works part by part (a whole-aircraft union of grown parts needed over 100 GB): each part
    with its neighbours, cut to a box just round it and grown by twice GAP_CLOSE to bridge the fit
    gaps, then the enclosed slots filled."""
    def __init__(self, built):
        self.solids = []
        for name, (P, extra) in built.items():
            if name.startswith("key_"):              # loose keys have no assembled place
                continue
            self.solids.append((name, P, P.bounding_box()))
            self.solids += [(n, plug, plug.bounding_box()) for n, *_, plug in extra]   # roundels, codes
        self.wings = {tag: mf.Manifold.batch_boolean(
            [P for n, (P, _) in built.items() if n.startswith("wing_") and n.endswith(tag)], mf.OpType.Add)
            for tag in ("stbd", "port")}

    def mask(self, name, P):
        bb = P.bounding_box()
        m = 2.0
        clip = K.box(bb[0] - m, bb[3] + m, bb[1] - m, bb[4] + m, bb[2] - m, bb[5] + m)
        near = [Q ^ clip for n, Q, qb in self.solids if n != name and _overlaps(bb, qb, m)]
        near = [Q for Q in near if Q.volume() > 1e-3]
        L = P if not near else mf.Manifold.batch_boolean(
            [P] + [dilate(Q, 2 * GAP_CLOSE) for Q in near], mf.OpType.Add)
        # enclosed slots (keys between joined parts) come out as negative shells: fill them
        L = mf.Manifold.batch_boolean([q for q in L.decompose() if q.volume() > 0], mf.OpType.Add)
        core_skin = K.inner_core(L, SKIN)
        core_in = K.inner_core(L, INNER_BLACK)
        near_inner = (P - K.inner_core(P, INNER_BLACK)) ^ core_in   # near P's faces, deep in the aircraft
        return (P - core_skin) - near_inner

    def wing_shadow(self, P, tag):
        """Everything under the wing over a nacelle half."""
        x0, y0, z0, x1, y1, z1 = P.bounding_box()
        w = self.wings[tag] ^ K.box(x0 - 1, x1 + 1, y0 - 1, y1 + 1, z0 - 1, z1 + 30)
        return mf.Manifold.batch_boolean([w.translate([0, 0, -k]) for k in np.arange(0.0, z1 - z0 + 1, 0.4)],
                                         mf.OpType.Add)

    def keep_paint_outside(self, name, vols, P):
        if name.startswith(UNMASKED) or name in CLEAR_PARTS or set(vols) <= {BLACK}:
            return vols
        m = self.mask(name, P)
        if name.startswith("nacelle"):
            m = m - self.wing_shadow(P, name.split("_")[1])
        out, black = {}, vols.get(BLACK)
        for c, v in vols.items():
            if c == BLACK:
                continue
            keep, lost = v ^ m, v - m
            if keep.volume() > 1e-3:
                out[c] = leaf(keep)
            if lost.volume() > 1e-3:
                black = lost if black is None else black + lost
        if black is not None:
            out[BLACK] = leaf(black)
        return out


# ============================================================
# MAIN
# ============================================================
def add_object(objs, name, posed, out, whole):
    """Register a posed multi-colour object; also write its single-colour STL
    (from the uncut solid: merging the colour pieces back is slow and fragile)."""
    import trimesh
    lo = np.min([v.bounding_box()[:3] for v in posed.values()], axis=0)
    hi = np.max([v.bounding_box()[3:] for v in posed.values()], axis=0)
    posed = {c: v.translate(list(-lo)) for c, v in posed.items()}
    V, F = mesh_of(whole.translate(list(-lo)))
    trimesh.Trimesh(V, F).export(out / "stl" / f"{name}.stl")
    objs[name] = {"name": name, "vols": posed, "size": (hi - lo)[:2]}
    print(f"{name:26s} " + ", ".join(f"{FILAMENTS[c][0]} {v.volume() / 1000:.1f}cc"
                                      for c, v in sorted(posed.items())), flush=True)


PLATE_GROUPS = [            # parts kept together by colour set (max 5 colours a plate)
    ("Fuselage", lambda n: H.SPINE_PIECES and n.startswith("fuselage")),
    ("Spine", lambda n: n.startswith("spine_") or (H.SPINE_PIECES and n.startswith("df_loop"))),
    # painted fuselage on the wing plate: the wings already swap colours on almost every layer
    # up to 170 mm, so the fuselage's camo mostly shares those swaps (one long plate)
    ("Wings and fuselage", lambda n: n.startswith(("wing_", "tailplane", "fuselage", "df_loop"))),
    ("Nacelles", lambda n: n.startswith("nacelle")),
    ("Fin flashes, roundels and codes", lambda n: n.startswith(("flash_", "roundel_", "code_"))),
    ("Canopies and turrets (silk silver)", lambda n: n in CLEAR_PARTS),
    ("Display plinth", lambda n: n == "stand_base"),
    ("Props, gear, fins, guns and stand blade", lambda n: True),
]
MAX_COLOURS = 5

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "out")
    template = sys.argv[2] if len(sys.argv) > 2 else None
    out.mkdir(parents=True, exist_ok=True)
    g, plan_green = plan_camo()
    pat = {"plan_green": plan_green, "side": {s: side_camo(g, s) for s in (1, -1)},
           "roof_green": roof_camo(), "spine_plan": spine_plan(g, plan_green)}
    parts, poses = H.build()
    objs = {}
    preview = []
    (out / "stl").mkdir(exist_ok=True)
    only = os.environ.get("ONLY", "")
    import time
    built = {}
    for name, w in parts.items():
        t0 = time.time()
        P = to_manifold(H.mesh(w))
        P = D.apply(name, P)                       # panel lines, hatches, rivets
        if name == "stand_base":
            P = stand_decorate(P)                  # raised badge and name
        P = engrave_serial(name, P)
        P, dropped = K.largest_piece(P)            # every part is one solid: drop islands and specks
        if any(v > 1.0 for v in dropped):
            print(f"  [{name}] dropped loose pieces: " + ", ".join(f"{v:.1f}" for v in dropped if v > 1.0) + " mm3",
                  file=sys.stderr, flush=True)
        t1 = time.time()
        P, extra = inlays_for(name, P)             # roundel sockets + inlay discs
        P = K.largest_piece(P)[0]                  # the socket cut can strand a rivet dot
        # keep a plain mesh: Manifold is lazy, and 80 parts' unevaluated histories (every detail
        # cut and skin) held until painting ran the Mac out of memory (over 100 GB)
        built[name] = (leaf(P), [(n, {c: leaf(v) for c, v in iv.items()}, r, leaf(plug))
                                 for n, iv, r, plug in extra])
        import resource
        print(f"  [{name}] detail {t1 - t0:.1f}s inlay {time.time() - t1:.1f}s, peak memory "
              f"{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**30:.1f} GB", file=sys.stderr, flush=True)
    t0 = time.time()
    outside = Outside(built)                       # the assembled aircraft: what's on the outside
    print(f"  [assembled envelope] {time.time() - t0:.1f}s", file=sys.stderr, flush=True)
    for name, (P, extra) in built.items():
        if only and not any(o in name for o in only.split(",")):
            continue
        t2 = time.time()
        vols = outside.keep_paint_outside(name, colour_part(name, P, pat), P)
        for v in vols.values():
            v.volume()                             # force evaluation for timing
        import resource
        print(f"  [{name}] colour {time.time() - t2:.1f}s, peak memory "
              f"{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**30:.1f} GB", file=sys.stderr, flush=True)
        M = pose_matrix(poses[name])
        jobs = [(name, vols, lambda v, M=M: v.transform(M[:3, :]), P)]
        jobs += [(n, iv, lambda v, r=r: v.rotate(r), plug) for n, iv, r, plug in extra]
        for jname, jvols, pose, whole in jobs:
            for c, v in jvols.items():             # assembled-frame colour preview
                if jname.startswith("key_"):         # loose keys have no assembled place (they sat at the nose)
                    continue
                V, F = mesh_of(v)
                preview.append((c, V, F))
            add_object(objs, jname, {c: pose(v) for c, v in jvols.items()}, out, pose(whole))
    # plates
    order, plates_all, seen = [], [], set()
    for gname, pred in PLATE_GROUPS:
        group = [n for n in objs if n not in seen and pred(n)]
        seen.update(group)
        group.sort(key=lambda n: -objs[n]["size"][0] * objs[n]["size"][1])
        for items in pack([(n, tuple(objs[n]["size"])) for n in group]):
            plates_all.append((gname, items))
    objects = []
    for pi, (gname, items) in enumerate(plates_all):
        for n, x, y, rot90 in items:
            o = objs[n]
            vols = o["vols"]
            if rot90:
                sx, sy = o["size"]
                vols = {c: v.rotate([0, 0, 90]).translate([sy, 0, 0]) for c, v in vols.items()}
            objects.append({"name": n, "placement": (pi, x + BED_X0, y),
                            "volumes": [(c, *mesh_of(v)) for c, v in sorted(vols.items())]})
    import trimesh
    scene = trimesh.Scene()
    for i, (c, V, F) in enumerate(preview):
        rgb = [int(FILAMENTS[c][1][k:k + 2], 16) for k in (1, 3, 5)]
        m = trimesh.Trimesh(V, F)
        m.visual.face_colors = rgb + [255]
        scene.add_geometry(m, node_name=f"v{i}")
    scene.export(out / "halifax_colour_preview.glb")
    names = [f"{g} {i + 1}" for i, (g, _) in enumerate(plates_all)]
    for i, (gname, items) in enumerate(plates_all):
        cols = sorted({c for n, *_ in items for c in objs[n]["vols"]})
        print(f"plate {i + 1} colours: " + ", ".join(FILAMENTS[c][0] for c in cols))
        assert len(cols) <= MAX_COLOURS, f"plate {i + 1} needs {len(cols)} colours"
    kit_name = "halifax_kit.3mf" if H.WING_POSE == "end" else "halifax_kit_wings_flat.3mf"
    write_3mf(out / kit_name, objects, names, template)
    for i, (gname, items) in enumerate(plates_all):
        print(f"plate {i + 1} ({gname}): " + ", ".join(n for n, *_ in items))
    print("wrote", out / kit_name)
