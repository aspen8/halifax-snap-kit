"""
Handley Page Halifax B Mk II Series IA, 1:60 scale (500 mm span).

Parametric airframe in CadQuery. Phase 1: clean outer shapes only.

Axes: X = distance aft from the nose tip, Y = span (+ = starboard),
Z = up. All units mm at model scale.

Proportions were taken from the full-size aircraft (98 ft 10 in span,
71 ft 7 in length for the Series IA) and cross-checked against the
reference mesh in this repo.
"""
import math
import sys
from pathlib import Path

import cadquery as cq

# ============================================================
# PARAMETERS
# ============================================================
SPAN = 500.0                 # mm, tip to tip
SCALE = 30120.0 / SPAN       # ~1:60.2

# --- Fuselage stations: (x, half_width, z_top, z_bottom, squareness)
# squareness: 2 = ellipse, higher = flatter sides (Halifax is slab-sided)
FUSE_STATIONS = [
    (0.0,   1.5, -15.0, -19.5, 2.0),   # perspex nose tip
    (3.0,   5.5, -10.0, -25.0, 2.2),
    (9.0,   8.8,  -5.5, -29.5, 2.5),
    (19.0, 11.4,  -1.5, -33.0, 2.8),
    (32.0, 12.8,   1.2, -35.0, 3.2),
    (46.0, 13.4,   3.6, -35.8, 3.5),
    (60.0, 13.5,   6.5, -36.0, 3.6),
    (72.0, 13.5,  10.2, -36.0, 3.8),
    (82.0, 13.5,  11.4, -36.0, 3.8),
    (190.0, 13.2, 11.4, -36.0, 3.8),
    (215.0, 12.8, 11.4, -35.0, 3.7),
    (240.0, 12.2, 11.4, -30.5, 3.5),
    (270.0, 11.6, 11.4, -25.5, 3.3),
    (305.0, 10.9, 11.2, -21.5, 3.0),
    (335.0, 10.0, 10.6, -17.5, 2.8),
    (352.0,  9.0,  9.6, -14.0, 2.5),
]
TAIL_TURRET_X = 352.0        # turret dome starts here
TAIL_TURRET_R = 9.0          # mm, dome radius
TAIL_TURRET_Z = -2.2         # mm, dome centre height

# --- Wing (one side), stations: (y, x_leading_edge, chord, z_chordline, t/c)
WING_STATIONS = [
    (0.0,   113.0, 76.0, -12.0, 0.180),
    (85.0,  116.0, 72.0, -11.0, 0.165),   # outboard of inner nacelle
    (245.0, 146.0, 22.0,   3.5, 0.110),
    (248.5, 150.0, 14.5,   3.8, 0.100),   # rounded tip
    (250.0, 154.0,  7.0,   3.9, 0.090),
]
WING_TE_MIN = 0.8            # mm, minimum trailing-edge thickness (printable)

# --- Nacelles: (y_centre, z_centre, x_front, length)
NACELLES = [
    (59.0,  -15.7, 86.0, 132.0),     # inner: runs past trailing edge (gear bay)
    (128.5, -11.0, 95.0, 100.0),     # outer
]
NACELLE_W = 22.0             # mm, max width
NACELLE_H_BODY = 21.0        # mm, max height of the main body (oval)
RADIATOR_X = 6.0             # mm, chin radiator start behind nacelle front
RADIATOR_LEN = 34.0          # mm
RADIATOR_R = 6.0             # mm
SPINNER_LEN = 7.0            # mm
SPINNER_R = 4.6              # mm, base radius

# --- Tailplane (one side): stations (y, x_le, chord, z, t/c)
TAIL_STATIONS = [
    (0.0,  293.0, 41.0, 5.8, 0.10),
    (82.0, 298.0, 36.0, 5.8, 0.09),
]

# --- Fins (rectangular Series IA type)
FIN_Y = 82.0                 # mm, spanwise position
FIN_X_LE = 297.0             # mm
FIN_CHORD = 39.0             # mm
FIN_Z_BOTTOM = -20.0         # mm
FIN_Z_TOP = 40.0             # mm
FIN_T = 3.6                  # mm, max thickness
FIN_CORNER_R = 9.0           # mm, rounding of the top corners

OUT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

# ============================================================
# HELPERS
# ============================================================
V = cq.Vector


def superellipse_wire(x, hw, z_top, z_bot, n, pts=48):
    """Closed spline cross-section in the YZ plane at station x."""
    zc = (z_top + z_bot) / 2
    hh = (z_top - z_bot) / 2
    p = []
    for i in range(pts):
        t = 2 * math.pi * i / pts
        c, s = math.cos(t), math.sin(t)
        y = hw * math.copysign(abs(c) ** (2 / n), c)
        z = hh * math.copysign(abs(s) ** (2 / n), s)
        p.append(V(x, y, zc + z))
    return cq.Wire.assembleEdges([cq.Edge.makeSpline(p, periodic=True)])


def naca230_coords(tc, chord, te_half, n=40):
    """NACA 230xx aerofoil. Returns (upper, lower) lists of (x, z) LE->TE."""
    m, k1 = 0.2025, 15.957
    upper, lower = [], []
    for i in range(n + 1):
        b = math.pi * i / n
        x = (1 - math.cos(b)) / 2
        yt = 5 * tc * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x**2
                       + 0.2843 * x**3 - 0.1036 * x**4)
        yt += x * te_half / chord           # open TE to printable thickness
        if x < m:
            yc = k1 / 6 * (x**3 - 3 * m * x**2 + m**2 * (3 - m) * x)
            dyc = k1 / 6 * (3 * x**2 - 6 * m * x + m**2 * (3 - m))
        else:
            yc = k1 * m**3 / 6 * (1 - x)
            dyc = -k1 * m**3 / 6
        th = math.atan(dyc)
        upper.append(((x - yt * math.sin(th)) * chord, (yc + yt * math.cos(th)) * chord))
        lower.append(((x + yt * math.sin(th)) * chord, (yc - yt * math.cos(th)) * chord))
    return upper, lower


def sym_coords(tc, chord, te_half, n=30):
    """Symmetric NACA 00xx section."""
    upper, lower = [], []
    for i in range(n + 1):
        x = (1 - math.cos(math.pi * i / n)) / 2
        yt = 5 * tc * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x**2
                       + 0.2843 * x**3 - 0.1036 * x**4) + x * te_half / chord
        upper.append((x * chord, yt * chord))
        lower.append((x * chord, -yt * chord))
    return upper, lower


def section_wire(upper, lower, place):
    """Aerofoil wire: one spline round the nose plus a straight TE edge."""
    pts = [place(*p) for p in reversed(upper)] + [place(*p) for p in lower[1:]]
    nose = cq.Edge.makeSpline(pts)
    te = cq.Edge.makeLine(pts[-1], pts[0])
    return cq.Wire.assembleEdges([nose, te])


def lofted_surface(stations, coords_fn, mirror=False):
    wires = []
    for (y, x_le, chord, z, tc) in stations:
        up, lo = coords_fn(tc, chord, WING_TE_MIN / 2)
        yy = -y if mirror else y
        wires.append(section_wire(up, lo, lambda px, pz, x_le=x_le, z=z, yy=yy:
                                  V(x_le + px, yy, z + pz)))
    solid = cq.Solid.makeLoft(wires, ruled=True)   # straight taper between stations
    return solid


# ============================================================
# MODEL
# ============================================================
def fuselage():
    wires = [superellipse_wire(*s) for s in FUSE_STATIONS]
    body = cq.Solid.makeLoft(wires, ruled=False)
    turret = cq.Solid.makeSphere(TAIL_TURRET_R, V(TAIL_TURRET_X, 0, TAIL_TURRET_Z))
    return cq.Workplane().add(body).union(cq.Workplane().add(turret))


def wing(side):
    w = cq.Workplane().add(lofted_surface(WING_STATIONS, naca230_coords, mirror=True))
    return w if side < 0 else w.mirror("XZ")


def nacelle(zc, x0, length):
    """Merlin nacelle on the centreline: oval body of revolution + chin radiator."""
    # radius profile along the nacelle (fraction of length, fraction of max radius)
    prof = [(0.0, 0.30), (0.02, 0.62), (0.06, 0.86), (0.13, 0.98), (0.25, 1.0),
            (0.45, 0.95), (0.70, 0.70), (0.90, 0.35), (1.0, 0.08)]
    r = NACELLE_W / 2
    pts = [(x0 + f * length, k * r) for f, k in prof]
    body = (cq.Workplane("XY")
            .moveTo(pts[0][0], 0).lineTo(*pts[0])
            .spline(pts[1:], includeCurrent=True)
            .lineTo(pts[-1][0], 0).close()
            .revolve(360, (0, 0, 0), (1, 0, 0)))
    # stretch vertically to the oval section
    m = cq.Matrix([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, NACELLE_H_BODY / NACELLE_W, 0]])
    body = cq.Workplane().add(body.val().transformGeometry(m))
    # chin radiator under the front of the nacelle
    rl = RADIATOR_LEN
    rad_pts = [(0.0, 0.25), (0.15, 0.85), (0.5, 1.0), (0.85, 0.85), (1.0, 0.2)]
    rp = [(x0 + RADIATOR_X + f * rl, k * RADIATOR_R) for f, k in rad_pts]
    rad = (cq.Workplane("XY")
           .moveTo(rp[0][0], 0).lineTo(*rp[0])
           .spline(rp[1:], includeCurrent=True)
           .lineTo(rp[-1][0], 0).close()
           .revolve(360, (0, 0, 0), (1, 0, 0))
           .translate((0, 0, -NACELLE_H_BODY / 2 + RADIATOR_R * 0.55)))
    spinner = cq.Solid.makeCone(SPINNER_R, 0.4, SPINNER_LEN,
                                pnt=V(x0 + 0.5, 0, 0), dir=V(-1, 0, 0))
    out = body.union(rad).union(cq.Workplane().add(spinner))
    return out.translate((0, 0, zc))


def nacelle_at(yc, zc, x0, length, side):
    return nacelle(zc, x0, length).translate((0, yc * side, 0))


def tailplane(side):
    t = cq.Workplane().add(lofted_surface(TAIL_STATIONS, sym_coords, mirror=True))
    return t if side < 0 else t.mirror("XZ")


def fin(side):
    up, lo = sym_coords(FIN_T / FIN_CHORD, FIN_CHORD, WING_TE_MIN / 2)
    pts = [(x, y) for x, y in reversed(up)] + [(x, y) for x, y in lo[1:]]
    height = FIN_Z_TOP - FIN_Z_BOTTOM
    prof = (cq.Workplane("XY").polyline(pts).close()
            .extrude(height)
            .translate((FIN_X_LE, FIN_Y * side, FIN_Z_BOTTOM)))
    # round the four corners in side view
    r = FIN_CORNER_R
    cutter = (cq.Workplane("XZ").rect(FIN_CHORD, height)
              .extrude(-FIN_T * 2, both=True)
              .edges("|Y").fillet(r)
              .translate((FIN_X_LE + FIN_CHORD / 2, FIN_Y * side,
                          FIN_Z_BOTTOM + height / 2)))
    return prof.intersect(cutter)


def parts():
    """Kit-level parts (not yet split for the bed)."""
    p = {"fuselage": fuselage()}
    for side, tag in ((1, "R"), (-1, "L")):
        p[f"wing_{tag}"] = wing(side)
        for i, (yc, zc, x0, length) in enumerate(NACELLES):
            p[f"nacelle_{tag}{i + 1}"] = nacelle_at(yc, zc, x0, length, side)
        p[f"tailplane_{tag}"] = tailplane(side)
        p[f"fin_{tag}"] = fin(side)
    return p


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    asm = cq.Assembly()
    for name, wp in parts().items():
        s = wp.val()
        assert s.isValid(), name
        cq.exporters.export(wp, str(OUT_DIR / f"{name}.stl"),
                            tolerance=0.02, angularTolerance=0.15)
        asm.add(wp, name=name)
        bb = s.BoundingBox()
        print(f"{name:12s} vol {s.Volume():8.0f} mm3  x[{bb.xmin:.0f},{bb.xmax:.0f}] "
              f"y[{bb.ymin:.0f},{bb.ymax:.0f}] z[{bb.zmin:.0f},{bb.zmax:.0f}]")
    asm.save(str(OUT_DIR / "halifax_phase1.step"))
