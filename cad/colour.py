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
import json
import math
import sys
import uuid
import zipfile
from pathlib import Path

import manifold3d as mf
import numpy as np
from PIL import Image

import halifax as H
import cadquery as cq

# ============================================================
# PARAMETERS
# ============================================================
SKIN = 0.8                   # mm, depth of coloured skin

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
SQN_CODE = "MH"
AC_LETTER = "E"
CODE_HEIGHT = 20.0           # mm (48 in letters)
CODE_Z = -11.7               # mm, centre height on the fuselage side
SQN_CODE_X = 211.0           # mm, centre of squadron code (port side)
AC_LETTER_X = 272.0          # mm, centre of aircraft letter (port side)

FUSE_ROUNDEL = (241.5, -11.7, 22.8)     # x, z, outer diameter (54 in C1)
WING_ROUNDEL = (154.3, 166.0, 37.0)     # x, |y|, diameter (84 in Type B)
FIN_FLASH = (309.0, 15.0, 33.0, 7.0, 1.5)  # x start, z0, z1, red/blue width, white width
PROP_TIP = 3.0               # mm of yellow at the prop tips

# Plan-view camo raster (Revell plan, top view crop) -> model coordinates
CAMO_PNG = Path(__file__).with_name("ref") / "camo_plan_green.png"
CAMO_ORIGIN = (940, 900)     # crop origin in page px (400 dpi)
CAMO_SCALE = 0.253           # mm per page px
CAMO_NOSE_PY = 2397          # page y of the nose tip
CAMO_CL_PX = 1995            # page x of the centreline

# Demarcation (top of the black on the fuselage sides), from the profile
DEMARCATION = [(0, -8.0), (26, -6.0), (45, -3.0), (60, 0.5), (90, 1.5), (130, 0.0),
               (170, -1.5), (210, 0.5), (250, -1.0), (290, 0.5), (330, 1.5), (360, 2.0)]

BED = (230.0, 250.0)         # usable plate area (dual-nozzle X limit on the X2D)
PLATE_GAP = 8.0

# ============================================================
# GEOMETRY HELPERS
# ============================================================
ALL = mf.Manifold.cube([1000, 1000, 1000], True)


def to_manifold(tm):
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(tm.vertices, np.float32),
                               tri_verts=np.asarray(tm.faces, np.uint32)))


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
    return np.interp(x, xs, zs)


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
    green = raster_section(val & above, to_xz, smooth=0.6)
    band = raster_section(above, to_xz)
    return green, band


# ============================================================
# PAINTING
# ============================================================
def skins(P):
    return {
        "up": P - P.translate([0, 0, -SKIN]),
        "+y": P - P.translate([0, -SKIN, 0]),
        "-y": P - P.translate([0, SKIN, 0]),
    }


def paint(P, ops, base=BLACK):
    """ops: list of (colour, region); later ops win. Returns {colour: Manifold}."""
    out = {}
    claimed = mf.Manifold()
    for colour, region in reversed(ops):
        r = (P ^ region) - claimed
        if r.volume() > 1e-3:
            out[colour] = out[colour] + r if colour in out else r
            claimed = claimed + r
    rest = P - claimed
    if rest.volume() > 1e-3:
        out[base] = out[base] + rest if base in out else rest
    return out


def colour_part(name, P, pat):
    S = skins(P)
    up = S["up"]
    camo_up = [(EARTH, up), (GREEN, up ^ prism_z(pat["plan_green"]))]
    if name.startswith(("wing_", "tailplane")):
        ops = list(camo_up)
        if name.startswith("wing_outer"):
            x, y, d = WING_ROUNDEL
            s = 1 if name.endswith("stbd") else -1
            ops += [(BLUE, up ^ prism_z(disc(x, s * y, d))),
                    (RED, up ^ prism_z(disc(x, s * y, d * 0.4)))]
        return paint(P, ops)
    if name.startswith("fuselage_"):
        s = 1 if name.endswith("stbd") else -1
        side = S["+y"] if s > 0 else S["-y"]
        green_s, band = pat["side"][s]
        ops = [(EARTH, side ^ prism_y(band)), (GREEN, side ^ prism_y(green_s)),
               (EARTH, up ^ prism_y(band)), (GREEN, up ^ prism_y(band) ^ prism_z(pat["plan_green"]))]
        x, z, d = FUSE_ROUNDEL
        for colour, dd in ((YELLOW, d), (BLUE, d * 0.889), (WHITE, d / 3 + 1.8), (RED, d / 3)):
            ops.append((colour, side ^ prism_y(disc(x, z, dd))))
        # codes read "MH (o) E" from both sides: squadron code aft on starboard
        rx = FUSE_ROUNDEL[0]
        mirror = s > 0
        sx = SQN_CODE_X if s < 0 else 2 * rx - SQN_CODE_X
        ax = AC_LETTER_X if s < 0 else 2 * rx - AC_LETTER_X
        for txt, cx in ((SQN_CODE, sx), (AC_LETTER, ax)):
            ops.append((RED, side ^ prism_y(text_section(txt, CODE_HEIGHT, cx, CODE_Z, mirror))))
        return paint(P, ops)
    if name.startswith("nacelle"):
        idx = int(name[7]) - 1
        zc = H.NACELLES[idx][1]
        upper = mf.Manifold.cube([1000, 1000, 500]).translate([-500, -500, zc - 1.0])
        skin = (S["up"] + S["+y"] + S["-y"]) ^ upper
        return paint(P, [(EARTH, skin), (GREEN, skin ^ prism_z(pat["plan_green"]))])
    if name.startswith("fin_"):
        s = 1 if name.endswith("stbd") else -1
        side = S["+y"] if s > 0 else S["-y"]
        x0, z0, z1, w, ww = FIN_FLASH
        rect = lambda a, b: mf.CrossSection([np.array([[a, z0], [b, z0], [b, z1], [a, z1]])])
        return paint(P, [(RED, side ^ prism_y(rect(x0, x0 + w))),
                         (WHITE, side ^ prism_y(rect(x0 + w, x0 + w + ww))),
                         (BLUE, side ^ prism_y(rect(x0 + w + ww, x0 + 2 * w + ww)))])
    if name.startswith("prop"):
        idx = int(name[4]) - 1
        yc, zc, x0, _ = H.NACELLES[idx]
        s = 1 if name.endswith("stbd") else -1
        r_in = H.PROP_D / 2 - PROP_TIP
        core = (mf.Manifold.cylinder(200, r_in, r_in, 96).rotate([0, 90, 0])
                .translate([-100, s * yc, zc]))
        return paint(P, [(YELLOW, P - core)])
    if name in ("canopy", "nose_glazing", "turret_dorsal", "turret_tail"):
        return {CLEAR: P}
    return {BLACK: P}


# ============================================================
# 3MF WRITER (Bambu Studio project layout)
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


def mesh_of(m):
    mm = m.to_mesh()
    return np.asarray(mm.vert_properties)[:, :3], np.asarray(mm.tri_verts)


def pack(items):
    """Shelf-pack (name, (w, h)) onto plates. Returns [[(name, x, y, rot90)], ...]."""
    plates = []
    for name, (w, h) in items:
        rot = w > BED[0] >= h
        if rot:
            w, h = h, w
        for p in plates:
            if p["x"] + w <= BED[0] and p["y"] + h <= BED[1]:
                pass
            elif p["y"] + p["row"] + PLATE_GAP + h <= BED[1]:
                p["y"] += p["row"] + PLATE_GAP
                p["x"], p["row"] = 0.0, 0.0
            else:
                continue
            p["items"].append((name, p["x"], p["y"], rot))
            p["x"] += w + PLATE_GAP
            p["row"] = max(p["row"], h)
            break
        else:
            plates.append({"x": w + PLATE_GAP, "y": 0.0, "row": h, "items": [(name, 0.0, 0.0, rot)]})
    return [p["items"] for p in plates]


def project_settings(template):
    d = json.load(open(template))
    n0 = len(d["filament_colour"])
    n = len(FILAMENTS)
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
    d["filament_colour"] = [FILAMENTS[i][1] for i in range(1, n + 1)]
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


def write_3mf(path, objects, plates, template):
    """objects: list of dict(name, volumes=[(colour, V, F)], placement=(plate, x, y))"""
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
            vs = "".join(f'<vertex x="{x:.4f}" y="{y:.4f}" z="{zz:.4f}"/>' for x, y, zz in V)
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
            f'      <metadata key="name" value="{obj["name"]}_{FILAMENTS[colour][0].replace(" ", "_")}"/>\n'
            '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
            f'      <metadata key="extruder" value="{colour}"/>\n'
            f'      <mesh_stat face_count="{n}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n'
            '    </part>\n' for vid, colour, n in vol_ids)
        settings.append(f'  <object id="{oid}">\n    <metadata key="name" value="{obj["name"]}"/>\n'
                        f'    <metadata key="extruder" value="{vol_ids[0][1]}"/>\n'
                        f'    <metadata face_count="{faces}"/>\n{parts}  </object>\n')
    z.writestr("3D/3dmodel.model", f'<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" {ns}>\n'
               ' <metadata name="Application">BambuStudio-02.08.02.61</metadata>\n'
               ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
               ' <metadata name="Title">Halifax B.II Srs IA snap kit 1:60</metadata>\n'
               f' <resources>\n{"".join(main_res)} </resources>\n <build>\n{"".join(build)} </build>\n</model>\n')
    z.writestr("3D/_rels/3dmodel.model.rels", '<?xml version="1.0" encoding="UTF-8"?>\n'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
               + "".join(rels) + '</Relationships>\n')
    plate_xml = []
    nfil = len(FILAMENTS)
    for pi, items in enumerate(plates):
        inst = "".join(f'    <model_instance>\n      <metadata key="object_id" value="{o["oid"]}"/>\n'
                       '      <metadata key="instance_id" value="0"/>\n'
                       f'      <metadata key="identify_id" value="{1000 + o["oid"]}"/>\n    </model_instance>\n'
                       for o in objects if o["placement"][0] == pi)
        plate_xml.append(f'  <plate>\n    <metadata key="plater_id" value="{pi + 1}"/>\n'
                         f'    <metadata key="plater_name" value="{items}"/>\n'
                         '    <metadata key="locked" value="false"/>\n'
                         '    <metadata key="filament_map_mode" value="Auto For Flush"/>\n'
                         f'    <metadata key="filament_maps" value="{" ".join(["1"] * nfil)}"/>\n'
                         f'{inst}  </plate>\n')
    z.writestr("Metadata/model_settings.config", '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
               + "".join(settings) + "".join(plate_xml) + '</config>\n')
    if template:
        z.writestr("Metadata/project_settings.config", project_settings(template))
    z.writestr("Metadata/slice_info.config", '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n  <header>\n'
               '    <header_item key="X-BBL-Client-Type" value="slicer"/>\n'
               '    <header_item key="X-BBL-Client-Version" value="02.08.02.61"/>\n  </header>\n</config>\n')
    z.close()


# ============================================================
# MAIN
# ============================================================
PLATE_GROUPS = [            # parts kept together, in this order, by colour set
    ("Fuselage", lambda n: n.startswith("fuselage")),
    ("Wings", lambda n: n.startswith(("wing_", "tailplane"))),
    ("Nacelles & fins", lambda n: n.startswith(("nacelle", "fin_"))),
    ("Clear", lambda n: n in ("canopy", "nose_glazing", "turret_dorsal", "turret_tail")),
    ("Black & props", lambda n: True),
]

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "out")
    template = sys.argv[2] if len(sys.argv) > 2 else None
    out.mkdir(parents=True, exist_ok=True)
    g, plan_green = plan_camo()
    pat = {"plan_green": plan_green, "side": {s: side_camo(g, s) for s in (1, -1)}}
    parts, poses = H.build()
    objs = {}
    for name, w in parts.items():
        P = to_manifold(H.mesh(w))
        vols = colour_part(name, P, pat)
        M = pose_matrix(poses[name])
        posed = {c: v.transform(M[:3, :]) for c, v in vols.items()}
        lo = np.min([v.bounding_box()[:3] for v in posed.values()], axis=0)
        hi = np.max([v.bounding_box()[3:] for v in posed.values()], axis=0)
        posed = {c: v.translate(list(-lo)) for c, v in posed.items()}
        objs[name] = {"name": name, "vols": posed, "size": (hi - lo)[:2]}
        print(f"{name:26s} " + ", ".join(f"{FILAMENTS[c][0]} {v.volume() / 1000:.1f}cc"
                                          for c, v in sorted(vols.items())), flush=True)
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
    names = [f"{g} {i + 1}" for i, (g, _) in enumerate(plates_all)]
    write_3mf(out / "halifax_kit.3mf", objects, names, template)
    for i, (gname, items) in enumerate(plates_all):
        print(f"plate {i + 1} ({gname}): " + ", ".join(n for n, *_ in items))
    print("wrote", out / "halifax_kit.3mf")
