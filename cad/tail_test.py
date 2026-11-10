"""
Tail fit test, round 2: the tailplane and the fins (the fuselage slot passed round 1).

Run after the colour build:  python tail_test.py KIT_OUT_DIR [project_settings_template.json]

Round 1 (2026-11-10): the fins printed inner face down, so the 0.6 mm tip pocket and the tab
slot opened onto the bed and their roofs bridged the whole tip chord: rough and loose. The fins
now print outer face down (pocket and slot open upwards), with a 1.2 mm pocket and a 1.2 mm tab.

Plate 1 (0.24 mm, as the wing plate): the tailplane (the kit part).
Plate 2 (0.12 mm, as the kit's fins), plain fins in the kit pose:
  fin_stbd_kit, fin_port_kit:      pocket FIN_POCKET_FIT (0.15) a side, tab slot FIN_TAB_FIT (0.10)
  fin_stbd_tight, fin_port_tight:  pocket 0.10 a side, tab slot 0.10
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

VARIANTS = {"kit": (H.FIN_POCKET_FIT, H.FIN_TAB_FIT), "tight": (0.10, 0.10)}


def load(path):
    t = trimesh.load(path)
    return mf.Manifold(mf.Mesh(t.vertices.astype(np.float32), t.faces.astype(np.uint32)))


def test_fin(side, pocket_fit, tab_fit):
    keep = H.FIN_POCKET_FIT, H.FIN_TAB_FIT
    H.FIN_POCKET_FIT, H.FIN_TAB_FIT = pocket_fit, tab_fit
    try:
        f = H.fin(side)
    finally:
        H.FIN_POCKET_FIT, H.FIN_TAB_FIT = keep
    return C.to_manifold(H.mesh(f)).rotate([-90 * side, 0, 0])   # kit pose: outer face down


def main():
    out = Path(sys.argv[1])
    template = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).with_name("project_settings_template.json"))
    pieces = {"tailplane": (load(out / "stl" / "tailplane.stl"), "tailplane")}
    for v, (pf, tf) in VARIANTS.items():
        for tag, side in (("stbd", 1), ("port", -1)):
            pieces[f"fin_{tag}_{v}"] = (test_fin(side, pf, tf), f"fin_{tag}")
    groups = [("Tailplane (0.24 mm)", ["tailplane"]),
              ("Fins (0.12 mm)", [n for n in pieces if n.startswith("fin_")])]
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
            print(f"plate {pi + 1}: {n:18} from {kit:10} {st}")
    path = out / "halifax_tail_test.3mf"
    K.write_3mf(path, objects, names, template, C.FILAMENTS, "Halifax tail test 2", C.PRINT_OVERRIDES)
    print("wrote", path)


if __name__ == "__main__":
    main()
