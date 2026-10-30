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
from kitlib import (clip, cs, mesh_of, pose_matrix, prism_y, prism_z,
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
    8: ("Clear", "#DDEBF2"),
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
        wave=(0.7, 7.5), fin_stripes=True),
    "MH-E": dict(     # 51 Sqn (first profile)
        unit="51 SQN RAF", sqn="MH", letter="E", code_h=20.0, code_z=-11.0, sqn_x=214.2, letter_x=273.4,
        roundel=(243.9, -11.0, 22.8), serial=None,
        demarcation=[(0, -8.0), (26, -6.0), (45, -3.0), (60, 0.5), (90, 1.5), (130, 0.0),
                     (170, -1.5), (210, 0.5), (250, -1.0), (290, 0.5), (330, 1.5), (360, 2.0)],
        wave=(0.0, 1.0), fin_stripes=False),
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
PROP_TIP = 3.0               # mm of yellow at the prop tips
INLAY_DEPTH = 1.2            # mm, roundel inlay depth at its shallowest point
INLAY_FIT = 0.1              # mm, radial clearance (press fit)
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

BED = (230.0, 250.0)         # usable plate area (dual-nozzle X limit on the X2D)
PLATE_GAP = 8.0

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
    above = Z > demarcation_z(X)
    to_xz = lambda r, c: (xs[0] + c * 0.25, zs[0] + r * 0.25)
    green = raster_section(val & above, to_xz, smooth=0.6).simplify(0.12)
    band = raster_section(above, to_xz).simplify(0.12)
    return green, band


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


def colour_part(name, P, pat):
    S = skins(P)
    up = S["up"]
    x0, y0, z0, x1, y1, z1 = P.bounding_box()
    plan = prism_z(clip(pat["plan_green"], x0, y0, x1, y1))
    pat = dict(pat, side={s: tuple(clip(c, x0, z0, x1, z1) for c in v) for s, v in pat["side"].items()})
    if not name.startswith("fuselage_"):    # thin edges: keep camo off the underside
        up = up - (P - P.translate([0, 0, UNDERSIDE_CLEAR]))
    camo_up = [(EARTH, up), (GREEN, up ^ plan)]
    if name.startswith(("wing_", "tailplane")):
        return paint(P, list(camo_up))
    if name.startswith("fuselage_"):
        s = 1 if name.endswith("stbd") else -1
        side = S["+y"] if s > 0 else S["-y"]
        green_s, band = pat["side"][s]
        roof = up ^ prism_z(roof_section())         # roof only: keeps clear of the side skin
        ops = [(EARTH, side ^ prism_y(band)), (GREEN, side ^ prism_y(green_s)),
               (EARTH, roof), (GREEN, roof ^ plan)]
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
        return paint(P, ops)
    if name.startswith("nacelle"):
        idx = int(name[7]) - 1
        zc = H.NACELLES[idx][1]
        upper = mf.Manifold.cube([1000, 1000, 500]).translate([-500, -500, zc - 1.0])
        skin = (S["up"] + S["+y"] + S["-y"]) ^ upper
        return paint(P, [(EARTH, skin), (GREEN, skin ^ plan)])
    if name.startswith("fin_"):
        s = 1 if name.endswith("stbd") else -1
        side = S["+y"] if s > 0 else S["-y"]
        x0, z0, z1, w, ww = FIN_FLASH
        rect = lambda a, b: mf.CrossSection([np.array([[a, z0], [b, z0], [b, z1], [a, z1]])])
        ops = [(RED, side ^ prism_y(rect(x0, x0 + w))),
               (WHITE, side ^ prism_y(rect(x0 + w, x0 + w + ww))),
               (BLUE, side ^ prism_y(rect(x0 + w + ww, x0 + 2 * w + ww)))]
        if MK["fin_stripes"]:
            both = S["+y"] + S["-y"]
            for quad in FIN_STRIPES:
                ops.append((YELLOW, both ^ prism_y(cs([quad]))))
        return paint(P, ops)
    if name.startswith("prop") and not name.startswith("prop_shaft"):
        idx = int(name[4]) - 1
        yc, zc, x0, _ = H.NACELLES[idx]
        s = 1 if name.endswith("stbd") else -1
        r_in = H.PROP_D / 2 - PROP_TIP
        core = (mf.Manifold.cylinder(200, r_in, r_in, 96).rotate([0, 90, 0])
                .translate([-100, s * yc, zc]))
        return paint(P, [(YELLOW, P - core)])
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
STAND_TEXT_H = (9.0, 6.0, 4.2)          # mm, the three lines
STAND_TEXT_Y = (-25.0, -37.5, -47.5)    # line centres (y, viewer side is -y)
STAND_RELIEF = 0.6                      # mm, raised lettering and badge
STAND_STRIPE = (5.0, 1.2)               # pinstripe inset from the edge, width
STAND_BADGE = (-48.0, 20.0, 0.16, 25.0)   # x from base centre, y, scale, heading (deg)


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
    foot = H.STAND_X + H.STAND_FOOT_DX
    sl, sw, _ = H.STAND_BOSS
    boss = prism_z(mf.CrossSection.square([sl + 2, sw + 2], True).translate([foot, 0]))
    ops = [(EARTH, deck), (GREEN, deck ^ prism_z(pat["plan_green"])),
           (YELLOW, deck ^ prism_z(stripe)), (BLACK, boss),
           (WHITE, above ^ prism_z(raised.offset(0.05, mf.JoinType.Round)))]
    return {c: stand_level(v, -1) for c, v in paint(L, ops).items()}


# ============================================================
# GLAZING FRAMES (black frame lines through a clear skin)
# ============================================================
CLEAR_PARTS = ("canopy", "nose_glazing", "turret_dorsal", "turret_tail", "astrodome")
FRAME_W = 0.6                # mm
# Pilot's canopy, measured from the Revell side and plan views (mm, assembled frame)
CANOPY_GLASS_X = (52.9, 72.1)               # glazing between these; the rims outside are frame
CANOPY_XFRAMES = [60.7]                     # windscreen rear frame (full hoop)
CANOPY_SIDE_XFRAMES = [66.8]                # splits the two side windows (below the cant rail)
CANOPY_RAILS = [(2.4, 52.6, 72.4), (8.0, 56.0, 72.4)]   # (z, x0, x1): sill and cant rail
CANOPY_ROOF_BARS = [(2.8, 56.5)]            # (|y|, x0): roof glazing bars to the rear frame
CANOPY_SCREEN_V = (60.7, 10.3)              # windscreen V seen from above: from (x, +-y) to the apex
CANOPY_SCREEN_DIAG = ((57.6, 8.0), (53.4, 2.6))         # side quarter-light frame (x, z)
NOSE_XFRAMES = [(6.0, -18.1), (12.4, None)]  # (x, only above z): vertical frame, rear rim
NOSE_ZFRAMES = [-18.1, -21.2]                # gun-slot band across the dome


def frames(name, P):
    sk = ALL - K.inner_core(P, 0.6)        # reaches past the surface: no clear slivers
    W = FRAME_W
    if name == "canopy":
        g0, g1 = CANOPY_GLASS_X
        f = H_box(-100, g0, -100, 100, -100, 100) + H_box(g1, 400, -100, 100, -100, 100)
        for x in CANOPY_XFRAMES:
            f = f + slab("x", x)
        for x in CANOPY_SIDE_XFRAMES:
            f = f + (slab("x", x) ^ H_box(-100, 400, -100, 100, -100, CANOPY_RAILS[1][0]))
        for z, x0, x1 in CANOPY_RAILS:
            f = f + (slab("z", z) ^ H_box(x0, x1, -100, 100, -100, 100))
        top = H_box(-100, 400, -100, 100, 5.0, 100)
        roof = mf.CrossSection()
        for yb, x0 in CANOPY_ROOF_BARS:
            for sg in (1, -1):
                roof = roof + D.band((x0, sg * yb), (g1, sg * yb), W)
        vx, vy = CANOPY_SCREEN_V
        for sg in (1, -1):
            roof = roof + D.band((vx, sg * vy), (g0 - 0.3, 0.0), W)
        f = f + (D.prism_z(roof) ^ top)
        f = f + D.prism_y(D.band(*CANOPY_SCREEN_DIAG, W))
        return sk ^ f
    if name == "nose_glazing":
        f = mf.Manifold()
        for x, zmin in NOSE_XFRAMES:
            f = f + (slab("x", x) if zmin is None else slab("x", x) ^ H_box(-100, 400, -100, 100, zmin, 100))
        for z in NOSE_ZFRAMES:
            f = f + slab("z", z)
        return sk ^ f
    if name == "turret_dorsal":
        x = H.DORSAL_X
        _, _, top, _, _ = H.interp(H.FUSE_STATIONS, x)
        return sk ^ (slab("x", x) + slab("y", 0.0) + slab("z", top + 2.0))
    if name == "turret_tail":
        return sk ^ (slab("y", 0.0) + slab("z", H.TAIL_TURRET_Z) + slab("x", H.FUSE_END_X + 5.0))
    return mf.Manifold()


# ============================================================
# ROUNDEL INLAYS (separate multi-colour discs, as PB94 does)
# ============================================================
def inlays_for(name, P):
    """Returns (P, [(inlay_name, vols, rotation_to_print_pose)])."""
    out = []
    if name.startswith("wing_outer"):
        s = 1 if name.endswith("stbd") else -1
        x, y, d = WING_ROUNDEL
        P, vols, plug = make_inlay(P, (x, s * y), d, B_RINGS(d), "z")
        out.append((f"roundel_wing_{name.split('_')[-1]}", vols, [0, 0, 0], plug))
    if name.startswith("fuselage_rear"):
        s = 1 if name.endswith("stbd") else -1
        x, z, d = FUSE_ROUNDEL
        P, vols, plug = make_inlay(P, (x, z), d, C1_RINGS(d), "y", s)
        out.append((f"roundel_fuselage_{name.split('_')[-1]}", vols, [90 * s, 0, 0], plug))
    return P, out


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
    return K.pack(items, BED, PLATE_GAP)


def write_3mf(path, objects, plates, template):
    K.write_3mf(path, objects, plates, template, FILAMENTS, "Halifax B.II Srs IA snap kit 1:60")


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
    ("Fuselage", lambda n: n.startswith("fuselage")),
    ("Wings", lambda n: n.startswith(("wing_", "tailplane"))),
    ("Nacelles", lambda n: n.startswith("nacelle")),
    ("Fins and roundels", lambda n: n.startswith(("fin_", "roundel_"))),
    ("Clear and guns", lambda n: n in CLEAR_PARTS or n.startswith("guns")),
    ("Display stand", lambda n: n.startswith("stand")),
    ("Props and gear", lambda n: True),
]
MAX_COLOURS = 5

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "out")
    template = sys.argv[2] if len(sys.argv) > 2 else None
    out.mkdir(parents=True, exist_ok=True)
    g, plan_green = plan_camo()
    pat = {"plan_green": plan_green, "side": {s: side_camo(g, s) for s in (1, -1)}}
    parts, poses = H.build()
    objs = {}
    preview = []
    (out / "stl").mkdir(exist_ok=True)
    only = os.environ.get("ONLY", "")
    import time
    for name, w in parts.items():
        if only and not any(o in name for o in only.split(",")):
            continue
        t0 = time.time()
        P = to_manifold(H.mesh(w))
        P = D.apply(name, P)                       # panel lines, hatches, rivets
        if name == "stand_base":
            P = stand_decorate(P)                  # raised badge and name
        t1 = time.time()
        P, extra = inlays_for(name, P)             # roundel sockets + inlay discs
        t2 = time.time()
        vols = colour_part(name, P, pat)
        for v in vols.values():
            v.volume()                             # force evaluation for timing
        t3 = time.time()
        print(f"  [{name}] detail {t1 - t0:.1f}s inlay {t2 - t1:.1f}s colour {t3 - t2:.1f}s",
              file=sys.stderr, flush=True)
        M = pose_matrix(poses[name])
        jobs = [(name, vols, lambda v, M=M: v.transform(M[:3, :]), P)]
        jobs += [(n, iv, lambda v, r=r: v.rotate(r), plug) for n, iv, r, plug in extra]
        for jname, jvols, pose, whole in jobs:
            for c, v in jvols.items():             # assembled-frame colour preview
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
            objects.append({"name": n, "placement": (pi, x, y),
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
    write_3mf(out / "halifax_kit.3mf", objects, names, template)
    for i, (gname, items) in enumerate(plates_all):
        print(f"plate {i + 1} ({gname}): " + ", ".join(n for n, *_ in items))
    print("wrote", out / "halifax_kit.3mf")
