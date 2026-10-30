"""
Pin fit coupon, round 2: wider range of holes for the printed 1.8 mm pin.

Plate: eight holes, 1.95 to 2.60 mm, values engraved, 0.3 mm entry chamfer.
Pins: three 1.8 mm pins (print head down), tips chamfered 0.3 mm.

Find the tightest hole the pin pushes into firmly (-> AXLE_HOLE_TIGHT)
and the smallest it spins freely in (-> AXLE_HOLE_LOOSE).

Run: python fit_test_pins.py OUT_DIR
"""
import sys
from pathlib import Path

import cadquery as cq

PIN_D, PIN_LEN, PIN_HEAD = 1.8, 8.0, (4.0, 0.8)
HOLES = [1.95, 2.05, 2.15, 2.25, 2.35, 2.45, 2.55, 2.65]
PLATE_T = 7.0
DEPTH = 6.0
CHAMFER = 0.3

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out")
out.mkdir(parents=True, exist_ok=True)

plate = cq.Workplane("XY").box(88.0, 26.0, PLATE_T, centered=(True, True, False))
for i, d in enumerate(HOLES):
    x = -38.5 + 11.0 * i
    hole = (cq.Workplane("XY").circle(d / 2).extrude(DEPTH)
            .translate((x, 4.0, PLATE_T - DEPTH + 0.01)))
    cone = (cq.Workplane("XY").circle(d / 2).workplane(offset=CHAMFER + 0.01)
            .circle(d / 2 + CHAMFER + 0.01).loft().translate((x, 4.0, PLATE_T - CHAMFER)))
    label = (cq.Workplane("XY").text(f"{d:.2f}", 2.8, -0.6, halign="center", valign="center")
             .translate((x, -6.5, PLATE_T)))
    plate = plate.cut(hole).cut(cone).cut(label)

pins = None
for dx in (-6.0, 0.0, 6.0):
    p = (cq.Workplane("XY").circle(PIN_HEAD[0] / 2).extrude(PIN_HEAD[1])
         .faces(">Z").workplane().circle(PIN_D / 2).extrude(PIN_LEN)
         .faces(">Z").edges().chamfer(CHAMFER)
         .translate((dx, 0, 0)))
    pins = p if pins is None else pins.union(p)

cq.exporters.export(plate, str(out / "fit_test_pins2_plate.stl"), tolerance=0.01, angularTolerance=0.1)
cq.exporters.export(pins, str(out / "fit_test_pins2.stl"), tolerance=0.01, angularTolerance=0.1)
print("written to", out)
