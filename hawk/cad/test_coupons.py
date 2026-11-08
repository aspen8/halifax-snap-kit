"""
Test coupons for the Hawk's new joints, cut from the real kit parts (same fits, paint and print
poses), on one plate. Print this before the full kit.

Run:  python test_coupons.py OUT_DIR       (writes OUT_DIR/hawk_test_coupons.3mf and stl/)

  1 wheel snap      the starboard main leg and its wheel, whole (the gear plate's fit)
  2 tailplane snap  the starboard tailplane's root and a block of the rear fuselage round its socket
  3 wing root       the starboard wing's root, on end as in the kit, a block of the middle
                    fuselage round the root joint (key slot, root stub, pods over the wing) and a key
  4 wing fins       one underside fin (its slot is in the wing-root coupon) and one leading-edge
                    fence with the piece of leading edge it clips round
"""
import sys
from pathlib import Path

import numpy as np

import colour as C
import hawk as H
import kitlib as K

GAP = H.WING_ROOT_GAP


def flat_tail_box(y1):
    """Box over the tailplane's root in its flat frame (cut face square to its print bed)."""
    return H._tail_to_assembled(H.box(150, 330, 0, y1, -50, 100), 1)


def coupons():
    """[(coupon name, kit part name, crop region or None)]"""
    s = H.tail_socket(1).bounding_box()             # tail socket (assembled frame)
    tail_block = H.box(s[0] - 5, s[3] + 5, 0, 14, s[2] - 5, s[5] + 5)
    yr = H.WING_ROOT_CUT
    y_fence = H.WING_LE_FENCES[0][0] * H.SPAN / 2
    le, c, _ = H.wing_plan(y_fence)
    return [
        ("t1_gear_leg", "gear_main_stbd", None),
        ("t1_wheel", "wheel_main_stbd", None),
        ("t2_tailplane_root", "tailplane_stbd", flat_tail_box(H.TAIL_ROOT_Y + 15)),
        ("t2_tail_socket_block", "fuselage_rear", tail_block),
        # the root's first 19 mm (24 printed) of span, with the inner fin's slot (|y| 25)
        ("t3_wing_root", "wing_stbd", H.box(0, 400, yr, 30.0, -60, 60)),
        # the fuselage round the joint: key slot (X 132.5-146.5), stub and the pods' floor
        ("t3_fuselage_block", "fuselage_mid", H.box(124.0, 156.0, 0.0, 22.0, -9.0, 4.0)),
        ("t3_key", "key_wing_1", None),
        ("t4_fin", "wingfin_stbd_1", None),
        ("t4_fence", f"wingfin_stbd_{len(H.WING_FINS) + 1}", None),
        ("t4_fence_le", "wing_stbd", H.box(le - 4.0, le + 0.45 * c, y_fence - 4.0, y_fence + 4.0, -60, 60)),
    ]


def finished(name, P):
    """A kit part as colour.py finishes it: panel lines, then paint. {colour: volume}"""
    P, _ = K.largest_piece(P)
    if name.startswith("wing_"):
        side = 1 if name.endswith("stbd") else -1
        P = (C.wing_detailed(side) ^ H.wing_root_box(side, False, GAP)) - H.wing_cuts(side)
        P, _ = K.largest_piece(P)
    else:
        C.P_plain[name] = P
        P = C.D.apply(name, P)
    return C.colour_part(name, P)


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "out")
    (out / "stl").mkdir(parents=True, exist_ok=True)
    parts, poses = H.build()
    done = {}
    objs = {}
    for cname, pname, region in coupons():
        if pname not in done:
            done[pname] = finished(pname, parts[pname])
        vols = done[pname]
        if region is not None:
            # crop; paint crumbs the cut leaves (under 1 mm3) go back into the base red
            cut, crumbs = {}, []
            for col, v in vols.items():
                keep = [p for p in (v ^ region).decompose() if p.volume() > 1.0 or col == C.RED]
                crumbs += [p for p in (v ^ region).decompose() if p.volume() <= 1.0 and col != C.RED]
                if keep:
                    cut[col] = H.union(keep)
            if crumbs:
                cut[C.RED] = H.union([cut[C.RED]] + crumbs)
            vols = cut
        whole = H.union(list(vols.values()))
        big = [p for p in whole.decompose() if p.volume() > 1.0]
        if len(big) > 1:
            print(f"!! {cname}: {len(big)} pieces")
        whole = K.largest_piece(whole)[0]
        pf = lambda m, pose=poses[pname]: pose(m).scale([H.PRINT_K] * 3)
        C.add_object(objs, cname, {col: pf(v) for col, v in vols.items()}, out, pf(whole))
    # two plates: the red parts with red on the main nozzle (as the kit's red plates), and the
    # black and grey gear on its own (mixed, every layer changed colour: 4.7 h)
    groups = [("Test coupons: airframe", lambda n: not n.startswith("t1_"), C.FILAMENT_MAP),
              ("Test coupons: wheel snap", lambda n: n.startswith("t1_"), None)]
    plates, names, fmaps = [], [], []
    for gname, pred, fmap in groups:
        items = [(n, tuple(objs[n]["size"])) for n in objs if pred(n)]
        items.sort(key=lambda it: -it[1][0] * it[1][1])
        for its in K.pack(items, C.BED, C.PLATE_GAP):
            plates.append(its); names.append(gname); fmaps.append(fmap)
    objects = []
    for pi, its in enumerate(plates):
        for n, x, y, rot90 in its:
            o = objs[n]
            vols = o["vols"]
            if rot90:
                sx, sy = o["size"]
                vols = {col: v.rotate([0, 0, 90]).translate([sy, 0, 0]) for col, v in vols.items()}
            objects.append({"name": n, "placement": (pi, x + C.BED_MARGIN[0], y + C.BED_MARGIN[1]),
                            "volumes": [(col, *C.mesh_of(v)) for col, v in sorted(vols.items())]})
    for name, its in zip(names, plates):
        cols = sorted({col for n, *_ in its for col in objs[n]["vols"]})
        print(f"{name}: " + ", ".join(C.FILAMENTS[col][0] for col in cols) + " | " + ", ".join(n for n, *_ in its))
        assert len(cols) <= C.MAX_COLOURS
    K.write_3mf(out / "hawk_test_coupons.3mf", objects, names, None, C.FILAMENTS,
                "BAE Hawk T.1A snap kit: test coupons", fmaps)
    print("wrote", out / "hawk_test_coupons.3mf")
