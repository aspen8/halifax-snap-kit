"""
Joint test: the three joints added on 2026-11-08 (outer wing mid joint, fuselage nose and tail
joints), cut from the built kit parts so the slots match the kit exactly.

Run after the colour build:  python joint_test.py KIT_OUT_DIR [project_settings_template.json]

Plate 1 (0.24 mm, as the wing plate): a slice from each side of each joint, as each part stands
on the plate (so each slot prints as in the kit):
  wing_mid_stbd top 12 mm / wing_outer_stbd bottom 12 mm      (one key_wing_split)
  fuselage_nose bottom 10 mm / fuselage_front top 10 mm       (two key_fuselage_nose)
  fuselage_rear top 10 mm / fuselage_tail bottom 10 mm        (two key_fuselage_tail)
Plate 2 (0.12 mm, as the kit's keys): the five keys.
Everything in black. Writes KIT_OUT_DIR/halifax_joint_test.3mf.
"""
import sys
from pathlib import Path

import manifold3d as mf
import numpy as np
import trimesh

import colour as C
import kitlib as K

SLICES = [  # (test name, kit part, from top?, thickness)
    ("j1_wing_mid", "wing_mid_stbd", True, 12.0),
    ("j1_wing_tip", "wing_outer_stbd", False, 12.0),
    ("j2_nose", "fuselage_nose", False, 10.0),
    ("j2_front", "fuselage_front", True, 10.0),
    ("j3_rear", "fuselage_rear", True, 10.0),
    ("j3_tail", "fuselage_tail", False, 10.0),
]
KEYS = ["key_wing_split_1", "key_fuselage_nose_1", "key_fuselage_nose_2",
        "key_fuselage_tail_1", "key_fuselage_tail_2"]


def load(path):
    t = trimesh.load(path)
    return mf.Manifold(mf.Mesh(t.vertices.astype(np.float32), t.faces.astype(np.uint32)))


def main():
    out = Path(sys.argv[1])
    template = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).with_name("project_settings_template.json"))
    stl = out / "stl"
    pieces = {}
    for name, part, top, t in SLICES:
        P = load(stl / f"{part}.stl")
        x0, y0, z0, x1, y1, z1 = P.bounding_box()
        a, b = (z1 - t, z1) if top else (z0, z0 + t)
        S, dropped = K.largest_piece(P ^ K.box(x0 - 1, x1 + 1, y0 - 1, y1 + 1, a, b))
        pieces[name] = (S, part)
    for k in KEYS:
        pieces[k] = (load(stl / f"{k}.stl"), k)
    groups = [("Joint slices (0.24 mm)", [n for n, *_ in SLICES]), ("Keys", KEYS)]
    objects, names = [], []
    for pi, (gname, group) in enumerate(groups):
        items = []
        for n in group:
            S = pieces[n][0]
            x0, y0, z0, *_ = S.bounding_box()
            S = S.translate([-x0, -y0, -z0])
            pieces[n] = (S, pieces[n][1])
            bb = S.bounding_box()
            items.append((n, (bb[3], bb[4])))
        packed = K.pack(sorted(items, key=lambda it: -it[1][0] * it[1][1]), C.BED, 12.0)
        assert len(packed) == 1, gname
        names.append(gname)
        for n, x, y, rot in packed[0]:
            S, kit = pieces[n]
            if rot:
                w = S.bounding_box()[4]
                S = S.rotate([0, 0, 90]).translate([w, 0, 0])
            st = {k: v for k, v in C.object_settings(kit).items() if k not in ("brim_type", "brim_width")}
            objects.append({"name": n, "placement": (pi, x + C.BED_X0, y), "settings": st,
                            "volumes": [(C.BLACK, *K.mesh_of(S))]})
            print(f"plate {pi + 1}: {n:22} from {kit:20} {st}")
    path = out / "halifax_joint_test.3mf"
    K.write_3mf(path, objects, names, template, C.FILAMENTS, "Halifax joint test", C.PRINT_OVERRIDES)
    print("wrote", path)


if __name__ == "__main__":
    main()
