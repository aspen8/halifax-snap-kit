"""
Tail fit test, round 3: dovetail rods on the fins, tailplane in two halves.

Run after the colour build:  python tail_test.py KIT_OUT_DIR [project_settings_template.json]

Rounds 1-2 (2026-11-10): a pocket and a small tab were never enough to hold a fin on. Now each fin
carries a dovetail rod (2.3 mm tall, 8-10 mm wide, 16 mm long, with a slit and two click teeth)
that slides into a slot along the underside of its tailplane half; the halves join on the
centreline with one flexing key, inside the fuselage slot.

Plate 1 (0.24 mm, as the wing plate), each half on end, root down as in the kit:
  tailplane_stbd:           the kit half, rod slot FIN_ROD_FIT (0.10) a side
  tailplane_port_fit015:    the port half with the rod slot at 0.15 a side, to compare
Plate 2 (0.12 mm, as the kit's fins and keys): fin_stbd, fin_port, key_tailplane_1 (kit parts).
Everything in black. Writes KIT_OUT_DIR/halifax_tail_test.3mf.
"""
import sys
from pathlib import Path

import manifold3d as mf
import numpy as np
import trimesh

import colour as C
import halifax as H
import kitlib as K

LOOSE_FIT = 0.15


def load(path):
    t = trimesh.load(path)
    return mf.Manifold(mf.Mesh(t.vertices.astype(np.float32), t.faces.astype(np.uint32)))


def main():
    out = Path(sys.argv[1])
    template = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).with_name("project_settings_template.json"))
    stl = out / "stl"
    pieces = {
        "tailplane_stbd": (load(stl / "tailplane_stbd.stl"), "tailplane_stbd"),
        "tailplane_port_fit015": (C.to_manifold(H.mesh(H.tail_half(-1, LOOSE_FIT))).rotate([-90, 0, 0]),
                                  "tailplane_port"),
        "fin_stbd": (load(stl / "fin_stbd.stl"), "fin_stbd"),
        "fin_port": (load(stl / "fin_port.stl"), "fin_port"),
        "key_tailplane_1": (load(stl / "key_tailplane_1.stl"), "key_tailplane_1"),
    }
    groups = [("Tailplane halves (0.24 mm)", ["tailplane_stbd", "tailplane_port_fit015"]),
              ("Fins and key (0.12 mm)", ["fin_stbd", "fin_port", "key_tailplane_1"])]
    objects, names = [], []
    for pi, (gname, group) in enumerate(groups):
        items = []
        for n in group:
            S = pieces[n][0]
            bx0, by0, bz0, *_ = S.bounding_box()
            S = S.translate([-bx0, -by0, -bz0])
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
            st = C.object_settings(kit)
            objects.append({"name": n, "placement": (pi, x + C.BED_X0, y), "settings": st,
                            "volumes": [(C.BLACK, *K.mesh_of(S))]})
            print(f"plate {pi + 1}: {n:22} from {kit:16} {st}")
    path = out / "halifax_tail_test.3mf"
    K.write_3mf(path, objects, names, template, C.FILAMENTS, "Halifax tail test 3", C.PRINT_OVERRIDES)
    print("wrote", path)


if __name__ == "__main__":
    main()
