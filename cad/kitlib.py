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


def surface_extreme(P, centre, r, axis, side):
    """Deepest point of the outer surface under the disc, measured along the inlay axis
    (z: lowest top surface; y: the side surface point closest to the centreline)."""
    import trimesh
    V, F = mesh_of(P)
    tm = trimesh.Trimesh(V, F, process=False)
    a = np.linspace(-r, r, 25)
    A, B = np.meshgrid(a, a)
    m = A ** 2 + B ** 2 <= r * r
    A, B = A[m] + centre[0], B[m] + centre[1]
    if axis == "z":
        o = np.c_[A, B, np.full(A.size, 500.0)]
        d = np.tile([0, 0, -1.0], (A.size, 1))
        loc, _, _ = tm.ray.intersects_location(o, d, multiple_hits=False)
        return loc[:, 2].min()
    o = np.c_[A, np.full(A.size, 500.0 * side), B]
    d = np.tile([0, -float(side), 0], (A.size, 1))
    loc, _, _ = tm.ray.intersects_location(o, d, multiple_hits=False)
    return (loc[:, 1] * side).min()          # distance outward from the centreline


def make_inlay(P, centre, d, rings, axis, side=1, depth=1.2, fit=0.1):
    """Cut a socket in P for a multi-ring inlay (e.g. a roundel).
    rings: [(colour, diameter)], outermost first. depth: inlay depth at the shallowest
    point of the surface; fit: radial press-fit clearance.
    Returns (P_with_socket, {colour: inlay volume}, whole_plug)."""
    r = d / 2
    flat = surface_extreme(P, centre, r, axis, side) - depth
    if axis == "z":
        keep = mf.Manifold.cube([1000, 1000, 500]).translate([-500, -500, flat])
    elif side > 0:
        keep = mf.Manifold.cube([1000, 500, 1000]).translate([-500, flat, -500])
    else:
        keep = mf.Manifold.cube([1000, 500, 1000]).translate([-500, -flat - 500, -500])
    socket = cyl_axis(*centre, r, axis) ^ keep         # a plain cylinder: no sheets left on the surface
    plug = P ^ cyl_axis(*centre, r - fit, axis) ^ keep
    # Each ring is the plug cut by a tube (cylinder minus the previous cylinder). Subtracting
    # the inner ring solids instead leaves zero-thickness sheets on the surface, where their
    # top faces coincide with the plug's.
    vols, prev = {}, None
    for colour, dd in reversed(rings):               # innermost first
        cyl = cyl_axis(*centre, dd / 2, axis)
        c = plug ^ (cyl if prev is None else cyl - prev)
        if c.volume() > 1e-3:
            vols[colour] = vols[colour] + c if colour in vols else c
        prev = cyl
    return P - socket, vols, plug


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


def connector_key(key, chamfer=0.4):
    """A printed key lying flat (length x width on the bed), ends chamfered."""
    length, width, thick = key
    k = cq.Workplane().box(length, width, thick, centered=(True, True, False))
    return k.edges("|Y").chamfer(chamfer)


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


def project_settings(template, filaments):
    d = json.load(open(template))
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
    if "filament_map" in d:
        d["filament_map"] = ["1"] * n
    for k in ("filament_nozzle_map", "filament_volume_map"):
        if k in d:
            d[k] = ["0"] * n
    return json.dumps(d, indent=4)


def write_3mf(path, objects, plates, template, filaments, title):
    """Write a Bambu Studio project 3MF.
    objects: [dict(name, volumes=[(filament_slot, V, F)], placement=(plate, x, y))]
    plates: plate names; template: Bambu project_settings JSON (or None);
    filaments: {slot: (name, hex)}; title: model title."""
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
                        f'    <metadata face_count="{faces}"/>\n{parts}  </object>\n')
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
    for pi, items in enumerate(plates):
        inst = "".join(f'    <model_instance>\n      <metadata key="object_id" value="{o["oid"]}"/>\n'
                       '      <metadata key="instance_id" value="0"/>\n'
                       f'      <metadata key="identify_id" value="{1000 + o["oid"]}"/>\n    </model_instance>\n'
                       for o in objects if o["placement"][0] == pi)
        plate_xml.append(f'  <plate>\n    <metadata key="plater_id" value="{pi + 1}"/>\n'
                         f'    <metadata key="plater_name" value={quoteattr(items)}/>\n'
                         '    <metadata key="locked" value="false"/>\n'
                         '    <metadata key="filament_map_mode" value="Auto For Flush"/>\n'
                         f'    <metadata key="filament_maps" value="{" ".join(["1"] * nfil)}"/>\n'
                         f'{inst}  </plate>\n')
    z.writestr("Metadata/model_settings.config", '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
               + "".join(settings) + "".join(plate_xml) + '</config>\n')
    if template:
        z.writestr("Metadata/project_settings.config", project_settings(template, filaments))
    z.writestr("Metadata/slice_info.config", '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n  <header>\n'
               '    <header_item key="X-BBL-Client-Type" value="slicer"/>\n'
               '    <header_item key="X-BBL-Client-Version" value="02.08.02.61"/>\n  </header>\n</config>\n')
    z.close()
