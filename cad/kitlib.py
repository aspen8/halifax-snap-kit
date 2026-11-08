"""
kitlib: reusable pieces for multi-colour printed snap kits (Bambu, PB94 style).

Nothing here knows about a particular aircraft. Geometry is manifold3d
(Manifold / CrossSection) in model millimetres; colours are filament slot numbers.

  Sections and prisms  cs, prism_z, prism_y, raster_section, text_section, disc, clip,
                       band, ring, rect_outline, dots_along
  Solids               box, slab, outer_skin, cyl_axis, to_manifold, mesh_of
  Colour               paint (peel regions into per-colour volumes), make_inlay
  Printed joints       key_slots, connector_key (CadQuery)
  Output               pose_matrix, pack (shelf packing), write_3mf (+ project_settings)

See LESSONS.md in the repo root for the workflow and the pitfalls.
"""
import json
import math
import uuid
import zipfile
from xml.sax.saxutils import escape, quoteattr

import cadquery as cq
import manifold3d as mf
import numpy as np


# ============================================================
# SECTIONS AND PRISMS
# ============================================================
def cs(contours):
    """CrossSection from a list of (N,2) rings, even-odd fill (holes ok)."""
    rings = [np.asarray(c, np.float64) for c in contours if len(c) >= 3]
    return mf.CrossSection(rings, mf.FillRule.EvenOdd)


def prism_z(section):
    """Extrude an XY section through all Z."""
    return section.extrude(400.0).translate([0, 0, -200.0])


def prism_y(section_xz):
    """Extrude a section given in (x, z) coordinates through all Y."""
    return section_xz.extrude(400.0).translate([0, 0, -200.0]).rotate([90, 0, 0])


def raster_section(mask, to_xy, smooth=0.0):
    """Polygonise a boolean raster; to_xy maps (row, col) arrays to model (a, b)."""
    from skimage import measure
    m = np.pad(mask.astype(float), 1)
    rings = []
    for c in measure.find_contours(m, 0.5):
        r, k = c[:, 0] - 1, c[:, 1] - 1
        a, b = to_xy(r, k)
        rings.append(np.c_[a, b])
    sec = cs(rings).simplify(0.05)
    return sec.offset(smooth, mf.JoinType.Round).offset(-smooth, mf.JoinType.Round) if smooth else sec


def text_section(text, height, x_centre, z_centre, mirror=False):
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath
    tp = TextPath((0, 0), text, size=100, prop=FontProperties(family="DejaVu Sans", weight="bold"))
    rings = [np.asarray(p) for p in tp.to_polygons()]
    allp = np.vstack(rings)
    lo, hi = allp.min(0), allp.max(0)
    k = height / (hi[1] - lo[1])
    out = []
    for r in rings:
        x = (r[:, 0] - (lo[0] + hi[0]) / 2) * k
        z = (r[:, 1] - (lo[1] + hi[1]) / 2) * k
        out.append(np.c_[x_centre + (-x if mirror else x), z_centre + z])
    return cs(out)


def disc(cx, cy, d):
    return mf.CrossSection.circle(d / 2, 96).translate([cx, cy])


def clip(section, a0, b0, a1, b1):
    """Crop a section to a rectangle (keeps prisms small and booleans fast)."""
    box2 = mf.CrossSection.square([a1 - a0 + 2, b1 - b0 + 2]).translate([a0 - 1, b0 - 1])
    return section ^ box2


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


def dots_along(p0, p1, offset, pitch, dot_d):
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
        out = out + mf.CrossSection.circle(dot_d / 2, 16).translate(list(c))
    return out


# ============================================================
# SOLIDS
# ============================================================
def box(x0, x1, y0, y1, z0, z1):
    return mf.Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def slab(axis, at, w):
    size = [1000.0, 1000.0, 1000.0]
    i = "xyz".index(axis)
    size[i] = w
    off = [-500.0, -500.0, -500.0]
    off[i] = at - w / 2
    return mf.Manifold.cube(size).translate(off)


def inner_core(P, d):
    """P eroded by d along the six axis directions."""
    core = P
    for v in ([d, 0, 0], [-d, 0, 0], [0, d, 0], [0, -d, 0], [0, 0, d], [0, 0, -d]):
        core = core ^ P.translate(v)
    return core


def outer_skin(P, d):
    """The outer d mm of P. To paint it, prefer (region - inner_core(P, d)): a region that
    reaches past the surface leaves no zero-thickness sheets behind."""
    return P - inner_core(P, d)


def cyl_axis(cx, cy, r, axis):
    c = mf.Manifold.cylinder(400.0, r, r, 128).translate([cx, cy, -200.0])
    return c if axis == "z" else c.rotate([90, 0, 0])      # 'y': centre (cx, z=cy)


def to_manifold(tm):
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(tm.vertices, np.float32),
                               tri_verts=np.asarray(tm.faces, np.uint32)))


def largest_piece(M):
    """(the largest connected solid of M, [volumes of the pieces dropped])."""
    comps = sorted(M.decompose(), key=lambda c: -c.volume())
    return (comps[0] if comps else M), [c.volume() for c in comps[1:]]


def mesh_of(m):
    mm = m.to_mesh()
    return np.asarray(mm.vert_properties)[:, :3], np.asarray(mm.tri_verts)


# ============================================================
# COLOUR
# ============================================================
def paint(P, ops, base):
    """ops: list of (colour, region); later ops win. Returns {colour: Manifold}.
    Works by peeling regions off what is left (no growing unions: much faster)."""
    out = {}
    remaining = P
    for colour, region in reversed(ops):
        r = remaining ^ region
        if r.volume() > 1e-3:
            out[colour] = out[colour] + r if colour in out else r
            remaining = remaining - region
    if remaining.volume() > 1e-3:
        out[base] = out[base] + remaining if base in out else remaining
    return out


INLAY_FACING = 0.6     # surface counts toward an inlay's depth only where it faces out this much
                       # (normal component along the inlay axis): ignores the turn under a hull
INLAY_FLOOR = 0.8      # mm of part left between any socket and a downward-facing surface


def surface_hits(P, centre, r, axis, side, facing=INLAY_FACING):
    """Outer-surface points under the disc, seen along the inlay axis, keeping only those that
    face out (normal along the axis >= facing). Returns (points, normals)."""
    import trimesh
    V, F = mesh_of(P)
    tm = trimesh.Trimesh(V, F, process=False)
    a = np.linspace(-r, r, 25)
    A, B = np.meshgrid(a, a)
    m = A ** 2 + B ** 2 <= r * r
    A, B = A[m] + centre[0], B[m] + centre[1]
    if axis == "z":
        o, d, k = np.c_[A, B, np.full(A.size, 500.0)], [0, 0, -1.0], 2
    else:
        o, d, k = np.c_[A, np.full(A.size, 500.0 * side), B], [0, -float(side), 0], 1
    loc, _, tri = tm.ray.intersects_location(o, np.tile(d, (A.size, 1)), multiple_hits=False)
    n = tm.face_normals[tri]
    ok = n[:, k] * (side if axis != "z" else 1) >= facing
    return loc[ok], n[ok]


def surface_extreme(P, centre, r, axis, side, facing=INLAY_FACING):
    """Deepest outward-facing point of the surface under the disc, measured along the inlay axis
    (z: lowest top surface; y: the side surface point closest to the centreline)."""
    loc, _ = surface_hits(P, centre, r, axis, side, facing)
    return loc[:, 2].min() if axis == "z" else (loc[:, 1] * side).min()


def under_band(P, t=INLAY_FLOOR):
    """Material within t above any downward-facing surface: sockets stay out of it, so an inlay
    never shows from below and never breaks through."""
    return P - P.translate([0, 0, t])


def _z_to(n):
    """Euler angles (x then y, degrees) turning the unit vector n onto +z."""
    th = math.degrees(math.atan2(n[1], n[2]))
    nz = math.hypot(n[1], n[2])
    ph = math.degrees(math.atan2(-n[0], nz))
    return th, ph


def _along(M, n, point):
    """M built along +z at the origin, turned so +z points along n, moved to point."""
    th, ph = _z_to(n)
    return M.rotate([0, -ph, 0]).rotate([-th, 0, 0]).translate(list(point))


def floor_plane(loc, axis, side, depth, cu, cv):
    """Flat, tilted socket floor `depth` below every outward-facing surface point `loc`: the plane
    that best fits the surface, moved in. axis 'z' (a wing top) or 'y' (a side, side=+1/-1).
    Returns (n outward unit normal, floor_at(u, v) -> xyz point, coeffs) with (u, v) = (x, y) on z
    and (x, z) on y."""
    if axis == "z":
        U, Vv, Wv = loc[:, 0], loc[:, 1], loc[:, 2]
    else:
        U, Vv, Wv = loc[:, 0], loc[:, 2], loc[:, 1] * side
    A = np.c_[U - cu, Vv - cv, np.ones(len(U))]
    (a, b, c), *_ = np.linalg.lstsq(A, Wv, rcond=None)
    w0 = c + (Wv - A @ np.array([a, b, c])).min() - depth
    nl = np.array([-a, -b, 1.0]) / math.sqrt(a * a + b * b + 1)
    return _plane(axis, side, nl, (a, b, w0), cu, cv)


def _plane(axis, side, nl, coeffs, cu, cv):
    a, b, w0 = coeffs
    if axis == "z":
        n = nl
        at = lambda u, v: np.array([u, v, w0 + a * (u - cu) + b * (v - cv)])
    else:
        n = np.array([nl[0], side * nl[2], nl[1]])
        at = lambda u, v: np.array([u, side * (w0 + a * (u - cu) + b * (v - cv)), v])
    return n, at, (a, b, w0)


def halfspace(n, point):
    """Everything on the n side of the plane through point."""
    return _along(mf.Manifold.cube([1000, 1000, 500]).translate([-500, -500, 0]), n, point)


def make_inlay(P, centre, d, rings, axis, side=1, depth=1.2, fit=0.1, peg=None, label=None):
    """Cut a socket in P for a multi-ring inlay (e.g. a roundel).
    rings: [(colour, diameter)], outermost first. depth: inlay depth at the shallowest
    outward-facing point of the surface; fit: radial press-fit clearance.
    The socket floor is flat, so the inlay prints flat-back down. On a z surface (a wing) the
    floor is tilted to the plane that best fits the surface, so the depth stays even over a
    cambered, sloping wing; on y it is upright. Sockets keep INLAY_FLOOR clear of any underside.
    Returns (P_with_socket, {colour: inlay volume}, whole_plug, rotation_to_print)."""
    r = d / 2
    loc, _ = surface_hits(P, centre, r, axis, side)
    n, floor_at, (a, b, w0) = floor_plane(loc, axis, side, depth, centre[0], centre[1])
    if axis == "z":       # lift the whole floor if it would come within INLAY_FLOOR of the underside
        import trimesh
        tm = trimesh.Trimesh(*mesh_of(P), process=False)
        g = np.linspace(-r, r, 61)                 # dense grid and the rim: the guard must never trim
        G = np.array([(u, v) for u in g for v in g if u * u + v * v <= r * r])
        t = np.linspace(0, 2 * np.pi, 240, endpoint=False)
        q = np.r_[G, np.c_[r * np.cos(t), r * np.sin(t)]] + np.array(centre)
        lo, ray, _ = tm.ray.intersects_location(np.c_[q, np.full(len(q), -500.0)],
                                                np.tile([0, 0, 1.0], (len(q), 1)), multiple_hits=False)
        if len(lo):
            need = max(lo[i, 2] + INLAY_FLOOR + 0.15 - floor_at(*q[ray[i]])[2] for i in range(len(lo)))
            if need > 0:
                n, floor_at, _ = _plane(axis, side, n, (a, b, w0 + need), centre[0], centre[1])
    keep = halfspace(n, floor_at(*centre))
    th, ph = _z_to(n)
    rot = [th, ph, 0]
    guard = under_band(P)
    socket = (cyl_axis(*centre, r, axis) ^ keep) - guard     # a plain cylinder: no sheets left on the surface
    plug = largest_piece((P ^ cyl_axis(*centre, r - fit, axis) ^ keep) - guard)[0]   # no stray rivet specks
    peg_solid = None
    if peg:   # (offset a, offset b, peg dia, hole dia, peg length): an off-centre peg on the
              # socket floor keys the inlay's rotation and grips it like a printed pin
        oa, ob, pd, hd, pl = peg
        fp = floor_at(centre[0] + oa, centre[1] + ob)
        peg_solid = _along(mf.Manifold.cylinder(pl + 0.5, pd / 2, pd / 2, 32).translate([0, 0, -0.5]), n, fp)
        hole = _along(mf.Manifold.cylinder(pl + 0.3, hd / 2, hd / 2, 32).translate([0, 0, -0.01]), n, fp)
        plug = plug - hole
    # Each ring is the plug cut by a tube (cylinder minus the previous cylinder). Subtracting
    # the inner ring solids instead leaves zero-thickness sheets on the surface, where their
    # top faces coincide with the plug's.
    if label:   # (text, height, offset a, offset b, mirror): engraved 0.4 mm into the inlay's back
        txt, lh, la, lb, lmirror = label
        sec = text_section(txt, lh, centre[0] + la, centre[1] + lb, lmirror)
        back = _along(mf.Manifold.cube([1000, 1000, 0.41]).translate([-500, -500, -0.01]), n,
                      floor_at(*centre))
        plug = plug - ((prism_z(sec) if axis == "z" else prism_y(sec)) ^ back)
    vols, prev = {}, None
    for colour, dd in reversed(rings):               # innermost first
        cyl = cyl_axis(*centre, dd / 2, axis)
        c = plug ^ (cyl if prev is None else cyl - prev)
        if c.volume() > 1e-3:
            vols[colour] = vols[colour] + c if colour in vols else c
        prev = cyl
    P = P - socket
    if peg_solid is not None:
        P = P + peg_solid
    return P, vols, plug, rot


def make_section_inlay(P, sec, side, depth=1.2, fit=0.15):
    """Inlay of any flat shape (e.g. a code letter) pressed into a side (y) surface.
    sec: CrossSection in (x, z); side: +1 starboard / -1 port. The socket floor is a flat plane
    fitted to the skin under the shape and moved `depth` in, so the depth stays even on a curving
    hull (a level floor made deep pockets where the hull bulged, and deep counters that print as
    hanging posts). Kept INLAY_FLOOR clear of any underside.
    Returns (P_with_socket, plug, rotation_to_print, (n, floor_at)) for add_peg."""
    import trimesh
    V, F = mesh_of(P)
    tm = trimesh.Trimesh(V, F, process=False)
    x0, z0, x1, z1 = sec.bounds()
    A, B = np.meshgrid(np.linspace(x0, x1, 30), np.linspace(z0, z1, 30))
    o = np.c_[A.ravel(), np.full(A.size, 500.0 * side), B.ravel()]
    d = np.tile([0, -float(side), 0], (A.size, 1))
    loc, _, tri = tm.ray.intersects_location(o, d, multiple_hits=False)
    ok = tm.face_normals[tri][:, 1] * side >= INLAY_FACING   # not where the hull turns under
    n, floor_at, _ = floor_plane(loc[ok], "y", side, depth, (x0 + x1) / 2, (z0 + z1) / 2)
    keep = halfspace(n, floor_at((x0 + x1) / 2, (z0 + z1) / 2))
    guard = under_band(P)
    socket = (prism_y(sec) ^ keep) - guard
    plug = largest_piece((P ^ prism_y(sec.offset(-fit, mf.JoinType.Round)) ^ keep) - guard)[0]
    th, ph = _z_to(n)
    return P - socket, plug, [th, ph, 0], (n, floor_at)


def peg_on_floor(floor, u, v, peg_d, peg_l, hole_d, hole_l):
    """(peg, hole): a peg standing square on a tilted socket floor at (u, v) and the matching hole
    into the back of the inlay."""
    n, floor_at = floor
    fp = floor_at(u, v)
    peg = _along(mf.Manifold.cylinder(peg_l + 0.5, peg_d / 2, peg_d / 2, 32).translate([0, 0, -0.5]), n, fp)
    hole = _along(mf.Manifold.cylinder(hole_l + 0.5, hole_d / 2, hole_d / 2, 32).translate([0, 0, -0.5]), n, fp)
    return peg, hole


# ============================================================
# PRINTED JOINTS (CadQuery solids)
# ============================================================
def key_slots(points, axis, split, key, width_axis, fit=0.1, end_gap=0.3):
    """Union of rectangular slots for printed keys across a split plane.
    key: (length along axis, width along width_axis, thickness)."""
    length, width, thick = key
    ext = {axis: length / 2 + end_gap, width_axis: width / 2 + fit}
    third = ({"x", "y", "z"} - {axis, width_axis}).pop()
    ext[third] = thick / 2 + fit
    out = None
    for p in points:
        q = list(p)
        q["xyz".index(axis)] = split
        lo = [q[i] - ext[a] for i, a in enumerate("xyz")]
        hi = [q[i] + ext[a] for i, a in enumerate("xyz")]
        b = cq.Workplane().add(cq.Solid.makeBox(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2],
                                                cq.Vector(*lo)))
        out = b if out is None else out.union(b)
    return out


def connector_key(key, chamfer=0.4, flex=True, slot_w=1.2, prong=2.4, waist=0.4, lead=0.8):
    """A printed key lying flat (length x width on the bed), ends chamfered.
    flex (after the PB94 Spitfire keys): U-slots in from each end turn the edges into springs, so
    the key squeezes into a snug slot; angled corners lead it in. Like the Spitfire's, the key is
    narrower in the middle (`waist` each side, at the joint line): the springy ends do the
    gripping, and the relieved middle clears the slot mouths, so it pushes in easily. A narrow key gets one central slot each end;
    a wide one gets a slot near each edge, leaving springy strips about `prong` wide."""
    length, width, thick = key
    if not flex:
        k = cq.Workplane().box(length, width, thick, centered=(True, True, False))
        return k.edges("|Y").chamfer(chamfer)
    k = cq.Workplane().box(length, width, thick, centered=(True, True, False))
    k = k.edges("|Y").chamfer(chamfer)
    for sx in (1, -1):                     # lead-in on the four end corners (in the bed plane)
        for sy in (1, -1):
            tri = (cq.Workplane().polyline([(sx * length / 2, sy * width / 2),
                                           (sx * (length / 2 - lead), sy * width / 2),
                                           (sx * length / 2, sy * (width / 2 - lead))]).close()
                   .extrude(thick + 1).translate((0, 0, -0.5)))
            k = k.cut(tri)
    span = length * 0.4                    # shallow arcs cut into both long sides at the middle
    r = (span ** 2 / 4 + waist ** 2) / (2 * waist)
    for sy in (1, -1):
        arc = (cq.Workplane().circle(r).extrude(thick + 1)
               .translate((0, sy * (width / 2 + r - waist), -0.5)))
        k = k.cut(arc)
    depth = length / 2 - max(1.5, length * 0.12)          # slot reaches to just short of the middle
    if depth < 1.5:
        return k
    if width <= 2 * prong + slot_w + 2.0:
        ys = [0.0]
    else:
        ys = [s * (width / 2 - prong - slot_w / 2) for s in (1, -1)]
    for sx in (1, -1):
        for y in ys:
            s = (cq.Workplane().box(depth, slot_w, thick + 1, centered=(False, True, False))
                 .edges("|Z and <X").fillet(slot_w / 2 - 0.01)
                 .translate((length / 2 - depth, y, -0.5)))
            if sx < 0:
                s = s.mirror("YZ")
            k = k.cut(s)
    return k


# ============================================================
# OUTPUT (Bambu Studio 3MF)
# ============================================================
def pose_matrix(pose):
    pts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
    w = cq.Workplane().add([cq.Vertex.makeVertex(*p) for p in pts])
    q = [v.toTuple() for v in pose(w).vals()]
    o = np.array(q[0])
    M = np.eye(4)
    M[:3, :3] = np.array([np.array(q[i]) - o for i in (1, 2, 3)]).T
    M[:3, 3] = o
    return M


def pack(items, bed, gap=8.0):
    """First-fit shelf packing of (name, (w, h)) onto plates.
    Returns [[(name, x, y, rot90)], ...]."""
    plates = []                       # each: list of shelves [y, height, x_used] + items
    for name, (w, h) in items:
        rot = w > bed[0] >= h
        if rot:
            w, h = h, w
        placed = False
        for p in plates:
            for sh in p["shelves"]:                 # an existing shelf with room
                if h <= sh[1] and sh[2] + w <= bed[0]:
                    p["items"].append((name, sh[2], sh[0], rot))
                    sh[2] += w + gap
                    placed = True
                    break
            if placed:
                break
            top = sum(sh[1] + gap for sh in p["shelves"])
            if top + h <= bed[1]:                   # a new shelf on this plate
                p["shelves"].append([top, h, w + gap])
                p["items"].append((name, 0.0, top, rot))
                placed = True
                break
        if not placed:
            plates.append({"shelves": [[0.0, h, w + gap]], "items": [(name, 0.0, 0.0, rot)]})
    return [p["items"] for p in plates]


TOWER = 35.0            # prime tower width (template prime_tower_width); depth taken as the same
TOWER_CLEAR = 9.0       # from every part's outline: a 6 mm brim plus 3
TOWER_X_MIN = 22.0      # the X2D's second nozzle can't reach x < 20.5


def place_towers(objects, n_plates, area=(230.0, 250.0), bed=(256.0, 256.0)):
    """Lower-left corner of a prime tower on each plate, in clear space: TOWER_CLEAR from every
    part's convex outline, x >= TOWER_X_MIN, inside `area` if possible (else the whole bed), as
    close to the parts as it can (short travel). The template's three positions came from an old
    3-plate project and put towers on parts or off the bed."""
    from shapely.geometry import MultiPoint, box as sbox
    from shapely.ops import unary_union
    out = []
    for pi in range(n_plates):
        shapes = []
        for o in objects:
            p, px, py = o["placement"]
            if p != pi:
                continue
            pts = np.vstack([V[:, :2] for _, V, _ in o["volumes"]]) + [px, py]
            shapes.append(MultiPoint(pts[::max(1, len(pts) // 4000)]).convex_hull.buffer(TOWER_CLEAR))
        if not shapes:
            out.append((TOWER_X_MIN, 10.0))
            continue
        busy = unary_union(shapes)
        c = busy.centroid
        best = None
        for lim in (area, bed):
            for x in np.arange(TOWER_X_MIN, lim[0] - TOWER - 1.0, 2.0):
                for y in np.arange(2.0, lim[1] - TOWER - 1.0, 2.0):
                    t = sbox(x, y, x + TOWER, y + TOWER)
                    if not t.intersects(busy):
                        d = t.centroid.distance(c)
                        if best is None or d < best[0]:
                            best = (d, float(x), float(y))
            if best:
                break
        if best is None:
            print(f"WARNING: no clear spot for the prime tower on plate {pi + 1}", flush=True)
            best = (0, TOWER_X_MIN, 10.0)
        out.append(best[1:])
    return out


def project_settings(template, filaments, overrides=None, towers=None, nozzle_map=None):
    d = json.load(open(template))
    d.update(overrides or {})
    n0 = len(d["filament_colour"])
    n = len(filaments)
    for k, v in list(d.items()):
        if not isinstance(v, list) or k in ("flush_volumes_matrix", "different_settings_to_system"):
            continue
        if len(v) == n0 or (k.startswith("filament_") and len(v) % n0 == 0 and len(v) > 0):
            b = len(v) // n0
            blocks = [v[i * b:(i + 1) * b] for i in range(n0)]
            blocks += [blocks[0]] * (n - n0)
            d[k] = [x for blk in blocks[:n] for x in blk]
    if "filament_self_index" in d:
        b = len(d["filament_self_index"]) // n
        d["filament_self_index"] = [str(i + 1) for i in range(n) for _ in range(b)]
    d["filament_colour"] = [filaments[i][1] for i in range(1, n + 1)]
    if "default_filament_colour" in d:
        d["default_filament_colour"] = [""] * n
    nozzles = len(d.get("nozzle_diameter", ["0.4"]))
    d["flush_volumes_matrix"] = [("0" if i == j else "350") for _ in range(nozzles)
                                 for i in range(n) for j in range(n)]
    if "flush_volumes_vector" in d:
        d["flush_volumes_vector"] = ["140"] * (2 * n)
    if "different_settings_to_system" in d:
        v = d["different_settings_to_system"]
        d["different_settings_to_system"] = [v[0]] + [""] * n + [v[-1]]
    if "filament_map" in d:                     # nozzle per filament (1 = main); set by hand when given
        d["filament_map"] = [str((nozzle_map or {}).get(i, 1)) for i in range(1, n + 1)]
        d["filament_map_mode"] = "Manual" if nozzle_map else "Auto For Flush"
    if towers:                                  # one prime tower position per plate
        d["wipe_tower_x"] = [f"{x:.1f}" for x, _ in towers]
        d["wipe_tower_y"] = [f"{y:.1f}" for _, y in towers]
    for k in ("filament_nozzle_map", "filament_volume_map"):
        if k in d:
            d[k] = ["0"] * n
    return json.dumps(d, indent=4)


def safe_name(s):
    """Drop the characters Bambu Studio refuses in object and plate names."""
    return "".join(ch for ch in s if ch not in '<>:/\\|?*"')


def write_3mf(path, objects, plates, template, filaments, title, overrides=None, nozzle_map=None):
    """Write a Bambu Studio project 3MF.
    objects: [dict(name, volumes=[(filament_slot, V, F)], placement=(plate, x, y))]
    plates: plate names; template: Bambu project_settings JSON (or None);
    overrides: print settings replacing the template's (e.g. {"layer_height": "0.16"});
    an object may carry "settings": {key: value} for per-object overrides (layer height, brim...);
    filaments: {slot: (name, hex)}; title: model title.
    nozzle_map: {slot: nozzle} pins filaments to nozzles (Manual grouping; others on nozzle 1). Without
    it every filament is on nozzle 1 and Bambu may regroup (Auto For Flush)."""
    plates = [safe_name(p) for p in plates]       # Bambu Studio rejects <>:/\|?*" in names
    ns = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
          'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
          'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
          'requiredextensions="p"')
    z = zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED)
    z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
               '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
               ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
               ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
               ' <Default Extension="png" ContentType="image/png"/>\n</Types>')
    z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?>\n'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
               ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" '
               'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>')
    main_res, build, rels, settings = [], [], [], []
    plate_step = 256 * 1.2
    cols = max(1, math.ceil(math.sqrt(len(plates))))
    next_id = 1
    for oi, obj in enumerate(objects):
        sub = f"3D/Objects/object_{oi + 1}.model"
        vol_ids, body = [], []
        for colour, V, F in obj["volumes"]:
            vid = next_id
            next_id += 1
            vol_ids.append((vid, colour, len(F)))
            vs = "".join(f'<vertex x="{x:.3f}" y="{y:.3f}" z="{zz:.3f}"/>' for x, y, zz in V)
            ts = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in F)
            body.append(f' <object id="{vid}" p:UUID="{uuid.uuid4()}" type="model">\n'
                        f'  <mesh><vertices>{vs}</vertices><triangles>{ts}</triangles></mesh>\n </object>\n')
        z.writestr(sub, f'<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" {ns}>\n'
                   f' <metadata name="BambuStudio:3mfVersion">1</metadata>\n <resources>\n{"".join(body)} </resources>\n <build/>\n</model>\n')
        rels.append(f' <Relationship Target="/{sub}" Id="rel-{oi + 1}" '
                    'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n')
        oid = next_id
        next_id += 1
        obj["oid"] = oid
        comps = "".join(f'    <component p:path="/{sub}" objectid="{vid}" p:UUID="{uuid.uuid4()}" '
                        'transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n' for vid, _, _ in vol_ids)
        main_res.append(f'  <object id="{oid}" p:UUID="{uuid.uuid4()}" type="model">\n   <components>\n{comps}   </components>\n  </object>\n')
        pi, px, py = obj["placement"]
        ox = (pi % cols) * plate_step
        oy = -(pi // cols) * plate_step
        build.append(f'  <item objectid="{oid}" p:UUID="{uuid.uuid4()}" '
                     f'transform="1 0 0 0 1 0 0 0 1 {ox + px:.4f} {oy + py:.4f} 0" printable="1"/>\n')
        faces = sum(n for _, _, n in vol_ids)
        parts = "".join(
            f'    <part id="{vid}" subtype="normal_part">\n'
            f'      <metadata key="name" value="{obj["name"]}_{filaments[colour][0].replace(" ", "_")}"/>\n'
            '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
            f'      <metadata key="extruder" value="{colour}"/>\n'
            f'      <mesh_stat face_count="{n}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n'
            '    </part>\n' for vid, colour, n in vol_ids)
        settings.append(f'  <object id="{oid}">\n    <metadata key="name" value={quoteattr(obj["name"])}/>\n'
                        f'    <metadata key="extruder" value="{vol_ids[0][1]}"/>\n'
                        + "".join(f'    <metadata key="{sk}" value={quoteattr(str(sv))}/>\n'
                                  for sk, sv in obj.get("settings", {}).items())
                        + f'    <metadata face_count="{faces}"/>\n{parts}  </object>\n')
    z.writestr("3D/3dmodel.model", f'<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" {ns}>\n'
               ' <metadata name="Application">BambuStudio-02.08.02.61</metadata>\n'
               ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
               f' <metadata name="Title">{escape(title)}</metadata>\n'
               f' <resources>\n{"".join(main_res)} </resources>\n <build>\n{"".join(build)} </build>\n</model>\n')
    z.writestr("3D/_rels/3dmodel.model.rels", '<?xml version="1.0" encoding="UTF-8"?>\n'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
               + "".join(rels) + '</Relationships>\n')
    plate_xml = []
    nfil = len(filaments)
    fmaps = " ".join(str((nozzle_map or {}).get(i, 1)) for i in range(1, nfil + 1))
    fmode = "Manual" if nozzle_map else "Auto For Flush"
    for pi, items in enumerate(plates):
        inst = "".join(f'    <model_instance>\n      <metadata key="object_id" value="{o["oid"]}"/>\n'
                       '      <metadata key="instance_id" value="0"/>\n'
                       f'      <metadata key="identify_id" value="{1000 + o["oid"]}"/>\n    </model_instance>\n'
                       for o in objects if o["placement"][0] == pi)
        plate_xml.append(f'  <plate>\n    <metadata key="plater_id" value="{pi + 1}"/>\n'
                         f'    <metadata key="plater_name" value={quoteattr(items)}/>\n'
                         '    <metadata key="locked" value="false"/>\n'
                         f'    <metadata key="filament_map_mode" value="{fmode}"/>\n'
                         f'    <metadata key="filament_maps" value="{fmaps}"/>\n'
                         f'{inst}  </plate>\n')
    z.writestr("Metadata/model_settings.config", '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
               + "".join(settings) + "".join(plate_xml) + '</config>\n')
    if template:
        towers = place_towers(objects, len(plates))
        for i, (x, y) in enumerate(towers):
            print(f"plate {i + 1}: prime tower at x {x:.0f}, y {y:.0f}", flush=True)
        z.writestr("Metadata/project_settings.config", project_settings(template, filaments, overrides, towers, nozzle_map))
    z.writestr("Metadata/slice_info.config", '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n  <header>\n'
               '    <header_item key="X-BBL-Client-Type" value="slicer"/>\n'
               '    <header_item key="X-BBL-Client-Version" value="02.08.02.61"/>\n  </header>\n</config>\n')
    z.close()
