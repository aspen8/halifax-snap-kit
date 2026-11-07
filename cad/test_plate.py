"""
Test plate: small coupons that check the new joints without printing the whole kit.

Run:  python test_plate.py OUT_DIR [project_settings_template.json]

Everything comes from the kit builders (halifax.py, colour.py), so the fits match the kit:
  1. Sprung prop boss: the nose of nacelle 1 (stbd), both halves, plus one prop. Two plain
     keys across the split hold the halves together (the wing does that in the kit).
  2. Code letter "G" (port) in a fuselage-wall coupon, with the floor peg and the hole in the inlay.
  3. Fin flash in a fin-skin coupon (stbd fin), with its peg and hole.
  4. Main gear: both fork halves and the wheel, plus a block with the nacelle's gear socket.
     Tail gear: the same, with the fuselage's tail-gear socket.
  5. A flexing nacelle key (KEY_NAC) and two blocks with its slot.

Writes OUT_DIR/halifax_test_plate.3mf, OUT_DIR/assembled/*.stl (for tools/interference.py),
OUT_DIR/print/*.stl (for tools/overhang.py) and OUT_DIR/test_plate_preview.glb.
About 5 min, most of it the nacelle.
"""
import sys
from pathlib import Path

import manifold3d as mf
import numpy as np
import trimesh

import colour as C
import detail as D
import halifax as H
import kitlib as K
from kitlib import mesh_of, pose_matrix, text_section, to_manifold

BLACK, RED = C.BLACK, C.RED
LAYER = "0.12"                  # one height for the whole plate (the prime tower needs that); the
                                # fine-detail height, as the kit's prop and gear plate
NOSE_KEY = (6.0, 5.0, 2.4)      # plain keys across the nacelle split: length (y), width (x), thickness (z)
NOSE_KEY_AT = (9.5, 5.5)        # x behind the nacelle nose, |z| from its centreline (clear of the intake)
NOSE_BACK = 13.0                # coupon ends this far behind the nacelle nose
MARGIN = 4.0                    # mm of skin round each inlay socket
FLOOR = 2.5                     # mm of wall behind the letter socket floor
BLOCK_WALL = 3.0                # mm round the gear sockets and key slots


def M(w):
    return to_manifold(H.mesh(w))


def bbox(x0, x1, y0, y1, z0, z1):
    return K.box(x0, x1, y0, y1, z0, z1)


def rot(m, rx=0, ry=0, rz=0):
    return m.rotate([rx, ry, rz])


# ============================================================
# COUPONS (assembled frame; each returns [(name, {colour: solid}, pose)])
# ============================================================
def prop_boss_coupon():
    side, idx = 1, 0
    yc, zc, x0, _ = H.NACELLES[idx]
    inner, outer, _ = H.wing_parts(side)
    inb, outb = H.nacelle_parts(idx, side, inner.union(outer))
    b = H.PROP_BOSS
    x_front = x0 - H.PROP_GAP - b["lip_t"] - b["gap"] - b["head_l"] - 2.0
    crop = H.box(x_front, x0 + NOSE_BACK, yc - 30, yc + 30, zc - 30, zc + 30)
    kx, kz = NOSE_KEY_AT
    pts = [(x0 + kx, yc, zc + s * kz) for s in (1, -1)]
    slots = H.key_slots(pts, "y", yc, NOSE_KEY, "x")
    out = []
    for tag, half, rx in (("inboard", inb, -90), ("outboard", outb, 90)):   # split face down, as the kit
        P = K.largest_piece(M(half.intersect(crop).cut(slots)))[0]
        out.append((f"t1_nose_{tag}", {BLACK: P}, lambda m, rx=rx: rot(m, rx=rx)))
    key = M(K.connector_key(NOSE_KEY, flex=False)).translate([0, 0, -NOSE_KEY[2] / 2])
    for i, p in enumerate(pts):                   # flat key turned so its length runs across the split
        out.append((f"t1_nose_key_{i + 1}", {BLACK: rot(key, rz=90).translate(list(p))},
                    lambda m: rot(m, rz=-90)))
    prop = M(H.propeller().translate((x0 - H.PROP_GAP - 1.0, yc, zc)))   # where build() puts it
    out.append(("t1_prop", {BLACK: prop}, lambda m: rot(m, ry=90)))
    return out


def code_letter_coupon():
    s = -1                                        # port "G"
    rx = C.FUSE_ROUNDEL[0]
    cx = C.AC_LETTER_X if s < 0 else 2 * rx - C.AC_LETTER_X
    letter = text_section(C.AC_LETTER, C.CODE_HEIGHT, cx, C.CODE_Z, s > 0).decompose()[0]
    lx0, lz0, lx1, lz1 = letter.bounds()
    _, hw, _, _, _ = H.interp(H.FUSE_STATIONS, (lx0 + lx1) / 2)
    big = 10.0                                    # detail on a larger crop, so the cut faces get no grooves
    P = M(H.fuselage_solid()) ^ bbox(lx0 - MARGIN - big, lx1 + MARGIN + big, -hw - 5, 0,
                                     lz0 - MARGIN - big, lz1 + MARGIN + big)
    P = D.apply("fuselage_rear_port", P) ^ bbox(lx0 - MARGIN, lx1 + MARGIN, -hw - 5, 0, lz0 - MARGIN, lz1 + MARGIN)
    P = K.largest_piece(P)[0]
    P, plug = K.make_section_inlay(P, letter, s, C.CODE_DEPTH, C.INLAY_FIT)
    (px, pz), _ = C.thickest_point(letter)
    P, plug = C.add_peg(P, plug, s, px, pz)
    floor = plug.bounding_box()[4]                # inner face of the inlay = socket floor (port: max y)
    P = K.largest_piece(P ^ bbox(lx0 - 50, lx1 + 50, -100, floor + FLOOR, lz0 - 50, lz1 + 50))[0]
    return [("t2_fuselage_wall", {BLACK: P}, lambda m: rot(m, rx=-90)),      # cut face down, socket up
            ("t2_code_G", {RED: plug}, lambda m: rot(m, rx=90 * s))]        # as colour.py: back down


def fin_flash_coupon():
    name = "fin_stbd"
    x0, z0, z1, w, ww = C.FIN_FLASH
    P = M(H.fin(1)) ^ bbox(x0 - MARGIN, x0 + 2 * w + ww + MARGIN, 0, 200, z0 - MARGIN, z1 + MARGIN)
    P = K.largest_piece(D.apply(name, P))[0]
    P, extra = C.inlays_for(name, P)
    (_, vols, r, _), = extra
    return [("t3_fin_skin", {BLACK: P}, lambda m: rot(m, rx=90)),            # inner face down, as the kit
            ("t3_fin_flash", vols, lambda m, r=r: m.rotate(r))]


def socket_block(x, yc, z_top, leg, plug, wheel_w):
    lx, ly = leg
    py, depth = plug
    y_out = wheel_w / 2 + 0.6 + ly
    a = lx / 2 + H.FIT + BLOCK_WALL
    blk = bbox(x - a, x + a, yc - y_out - BLOCK_WALL, yc + y_out + BLOCK_WALL, z_top, z_top + depth + 0.3 + BLOCK_WALL)
    return blk - M(H.gear_socket(x, yc, z_top, leg, plug, wheel_w))


def gear_coupons():
    out = []
    yc = H.NACELLES[0][0]
    z_top = H.nacelle_bottom(0, H.MAIN_AXLE_X)
    _, _, _, bot_t, _ = H.interp(H.FUSE_STATIONS, H.TAIL_AXLE_X)
    sets = (("main", H.MAIN_AXLE_X, yc, H.MAIN_AXLE_Z, z_top, H.MAIN_WHEEL_D, H.MAIN_WHEEL_W, H.MAIN_LEG, H.MAIN_PLUG),
            ("tail", H.TAIL_AXLE_X, 0.0, bot_t - H.TAIL_LEG_DROP, bot_t, H.TAIL_WHEEL_D, H.TAIL_WHEEL_W,
             H.TAIL_LEG, H.TAIL_PLUG))
    for tag, x, y, z_axle, top, d, w, leg, plug in sets:
        ga, gb = H.gear_fork_halves(x, y, z_axle, top, w, leg, plug, H.AXLE_STUB[tag])
        wh = H.wheel(x, y, z_axle, d, w, bore=H.AXLE_STUB[tag] + H.STUB_SPIN)
        out += [(f"t4_{tag}_gear_a", {BLACK: M(ga)}, lambda m: rot(m, rx=90)),     # as build()
                (f"t4_{tag}_gear_b", {BLACK: M(gb)}, lambda m: rot(m, rx=-90)),
                (f"t4_{tag}_wheel", {BLACK: M(wh)}, lambda m: rot(m, rx=90)),
                (f"t4_{tag}_socket", {BLACK: socket_block(x, y, top, leg, plug, w)},
                 lambda m: rot(m, rx=180))]                                       # mouth up
    return out


def key_coupon():
    length, width, thick = H.KEY_NAC
    a, b = width / 2 + H.KEY_FIT + BLOCK_WALL, thick / 2 + H.KEY_FIT + BLOCK_WALL
    h = length / 2 + H.KEY_END_GAP + BLOCK_WALL
    blk = bbox(-a, a, -b, b, 0, h) - M(H.key_slots([(0, 0, 0)], "z", h, H.KEY_NAC, "x"))
    key = M(H.connector_key(H.KEY_NAC))
    # assembled: block 1, key standing in it, block 2 upside down on top
    return [("t5_key_block_1", {BLACK: blk}, None),
            ("t5_key_block_2", {BLACK: rot(blk, rx=180).translate([0, 0, 2 * h])}, lambda m: rot(m, rx=180)),
            ("t5_key", {BLACK: rot(key.translate([0, 0, -thick / 2]), rx=90, ry=90).translate([0, 0, h])},
             lambda m: rot(rot(m, ry=-90), rx=-90))]           # flat on the bed, as the kit's keys


# ============================================================
# MAIN
# ============================================================
def single_piece(m):
    V, F = mesh_of(m)
    return len(trimesh.Trimesh(V, F).split(only_watertight=False))


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "out_test")
    template = sys.argv[2] if len(sys.argv) > 2 else None
    for d in ("assembled", "print"):
        (out / d).mkdir(parents=True, exist_ok=True)
    jobs = []
    for f in (key_coupon, gear_coupons, fin_flash_coupon, code_letter_coupon, prop_boss_coupon):
        jobs += f()
        print("built", f.__name__, flush=True)
    objs, preview, bad = {}, [], []
    for name, vols, pose in jobs:
        whole = None
        for v in vols.values():
            whole = v if whole is None else whole + v
        V, F = mesh_of(whole)
        trimesh.Trimesh(V, F).export(out / "assembled" / f"{name}.stl")
        for c, v in vols.items():
            preview.append((c, *mesh_of(v)))
        pose = pose or (lambda m: m)
        posed = {c: pose(v) for c, v in vols.items()}
        pw = pose(whole)
        lo = np.array(pw.bounding_box()[:3])
        hi = np.array(pw.bounding_box()[3:])
        posed = {c: v.translate(list(-lo)) for c, v in posed.items()}
        V, F = mesh_of(pw.translate(list(-lo)))
        trimesh.Trimesh(V, F).export(out / "print" / f"{name}.stl")
        n = single_piece(whole)
        if n != 1:
            bad.append(f"{name}: {n} pieces")
        objs[name] = {"name": name, "vols": posed, "size": (hi - lo)[:2]}
        ext = hi - lo
        print(f"{name:22s} {ext[0]:5.1f} x {ext[1]:5.1f} x {ext[2]:5.1f} mm  pieces {n}  "
              + ", ".join(f"{C.FILAMENTS[c][0]} {v.volume() / 1000:.2f}cc" for c, v in sorted(posed.items())),
              flush=True)
    assert not bad, "not single pieces: " + "; ".join(bad)

    names = sorted(objs, key=lambda n: -objs[n]["size"][0] * objs[n]["size"][1])
    plates = C.pack([(n, tuple(objs[n]["size"])) for n in names])
    assert len(plates) == 1, f"test parts need {len(plates)} plates"
    objects = []
    for n, x, y, rot90 in plates[0]:
        o = objs[n]
        vols = o["vols"]
        if rot90:
            sx, sy = o["size"]
            vols = {c: v.rotate([0, 0, 90]).translate([sy, 0, 0]) for c, v in vols.items()}
        objects.append({"name": n, "placement": (0, x, y), "settings": {"layer_height": LAYER},
                        "volumes": [(c, *mesh_of(v)) for c, v in sorted(vols.items())]})
    cols = sorted({c for o in objs.values() for c in o["vols"]})
    assert len(cols) <= C.MAX_COLOURS
    print("colours:", ", ".join(C.FILAMENTS[c][0] for c in cols))
    K.write_3mf(out / "halifax_test_plate.3mf", objects, ["Test plate"], template, C.FILAMENTS,
                "Halifax snap kit test plate", dict(C.PRINT_OVERRIDES, layer_height=LAYER))

    scene = trimesh.Scene()
    for i, (c, V, F) in enumerate(preview):
        m = trimesh.Trimesh(V, F)
        m.visual.face_colors = [int(C.FILAMENTS[c][1][k:k + 2], 16) for k in (1, 3, 5)] + [255]
        scene.add_geometry(m, node_name=f"v{i}")
    scene.export(out / "test_plate_preview.glb")
    print("wrote", out / "halifax_test_plate.3mf")
