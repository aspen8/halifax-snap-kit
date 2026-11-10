"""
Tail fit test: the tailplane through the tail fuselage, held by the two fins.

Run after the colour build:  python tail_test.py KIT_OUT_DIR [project_settings_template.json]

Plate 1 (0.24 mm, as the wing plate):
  tailplane (the kit part) and the bottom of fuselage_tail, up to just past the tailplane slot
Plate 2 (0.12 mm, as the kit's fins):
  fin_stbd, fin_port: the kit fins, tab slot KEY_FIT (0.15) a side
  fin_stbd_tight, fin_port_tight: the same fins with the tab slot at 0.10 a side (the fit the
  other joints settled on), plain (no panel lines or flash socket): try both, keep the better
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

TAIL_SLICE = H.TAIL_ROOT[0] + H.TAIL_ROOT[1] + 4.0 - H.FUSE_CUTS[-1]   # posed height: past the slot's TE
TIGHT_FIT = 0.10


def load(path):
    t = trimesh.load(path)
    return mf.Manifold(mf.Mesh(t.vertices.astype(np.float32), t.faces.astype(np.uint32)))


def tight_fin(side):
    keep = H.KEY_FIT
    H.KEY_FIT = TIGHT_FIT                       # fin() cuts its tab slot with KEY_FIT
    try:
        f = H.fin(side)
    finally:
        H.KEY_FIT = keep
    P = C.to_manifold(H.mesh(f)).rotate([90 * side, 0, 0])   # kit pose: inner face down
    return P


def main():
    out = Path(sys.argv[1])
    template = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).with_name("project_settings_template.json"))
    stl = out / "stl"
    pieces = {"tailplane": (load(stl / "tailplane.stl"), "tailplane")}
    P = load(stl / "fuselage_tail.stl")
    x0, y0, z0, x1, y1, z1 = P.bounding_box()
    S, _ = K.largest_piece(P ^ K.box(x0 - 1, x1 + 1, y0 - 1, y1 + 1, z0, z0 + TAIL_SLICE))
    pieces["fuselage_tail_slot"] = (S, "fuselage_tail")
    for tag, side in (("stbd", 1), ("port", -1)):
        pieces[f"fin_{tag}"] = (load(stl / f"fin_{tag}.stl"), f"fin_{tag}")
        pieces[f"fin_{tag}_tight"] = (tight_fin(side), f"fin_{tag}")
    groups = [("Tailplane and slot (0.24 mm)", ["tailplane", "fuselage_tail_slot"]),
              ("Fins (0.12 mm)", ["fin_stbd", "fin_port", "fin_stbd_tight", "fin_port_tight"])]
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
            st = {k: v for k, v in C.object_settings(kit).items() if k not in ("brim_type", "brim_width")}
            objects.append({"name": n, "placement": (pi, x + C.BED_X0, y), "settings": st,
                            "volumes": [(C.BLACK, *K.mesh_of(S))]})
            print(f"plate {pi + 1}: {n:20} from {kit:14} {st}")
    path = out / "halifax_tail_test.3mf"
    K.write_3mf(path, objects, names, template, C.FILAMENTS, "Halifax tail test", C.PRINT_OVERRIDES)
    print("wrote", path)


if __name__ == "__main__":
    main()
