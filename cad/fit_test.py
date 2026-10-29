"""
Fit-test coupon: print this first (5 min) to tune FIT and DOWEL_HOLE in halifax.py.

Base plate: three dowel holes (1.80 / 1.85 / 1.90 mm) for 1.75 mm filament,
and three tongue pockets with 0.10 / 0.15 / 0.20 mm clearance per side.
Loose part: a tongue that matches the wing root tongue (14 x 4 mm).
Pick the hole and pocket that push together firmly by hand.

Run: python fit_test.py OUT_DIR
"""
import sys
from pathlib import Path

import cadquery as cq

HOLES = [1.80, 1.85, 1.90]       # mm
CLEARANCES = [0.10, 0.15, 0.20]  # mm per side
TONGUE = (14.0, 4.0)             # mm, width x height (as ROOT_TONGUE)
POCKET_DEPTH = 6.0
PLATE_T = 8.0

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out")
out.mkdir(parents=True, exist_ok=True)

plate = cq.Workplane("XY").box(70, 36, PLATE_T, centered=(True, True, False))
for i, d in enumerate(HOLES):
    plate = (plate.faces(">Z").workplane(centerOption="CenterOfBoundBox")
             .center(-22 + 22 * i, 10).hole(d, 6.0))
for i, c in enumerate(CLEARANCES):
    w, h = TONGUE[0] + 2 * c, TONGUE[1] + 2 * c
    pocket = (cq.Workplane("XY").box(w, h, POCKET_DEPTH, centered=(True, True, False))
              .translate((-22 + 22 * i, -6, PLATE_T - POCKET_DEPTH + 0.01)))
    plate = plate.cut(pocket)
    # engrave the clearance value under each pocket
    label = (cq.Workplane("XY").text(f"{c:.2f}", 3.5, -0.6, halign="center")
             .translate((-22 + 22 * i, -14.5, PLATE_T)))
    plate = plate.cut(label)
for i, d in enumerate(HOLES):
    label = (cq.Workplane("XY").text(f"{d:.2f}", 3.5, -0.6, halign="center")
             .translate((-22 + 22 * i, 15, PLATE_T)))
    plate = plate.cut(label)

tongue = cq.Workplane("XY").box(TONGUE[0], 20, TONGUE[1], centered=(True, True, False))

cq.exporters.export(plate, str(out / "fit_test_plate.stl"), tolerance=0.01, angularTolerance=0.1)
cq.exporters.export(tongue, str(out / "fit_test_tongue.stl"), tolerance=0.01, angularTolerance=0.1)
print("fit test written to", out)
