"""
Fit-test coupon: print this first to tune the kit tolerances in halifax.py.

Base plate, three rows (values engraved next to each feature):
  1. Pin holes 1.75 / 1.80 / 1.85 / 2.05 mm for the printed 1.8 mm pin.
     Pick the tightest hole the pin pushes into firmly -> AXLE_HOLE_TIGHT.
     The pin should spin freely in 2.05 -> AXLE_HOLE_LOOSE.
  2. Connector-key slots with 0.05 / 0.10 / 0.15 mm clearance per side.
     Pick the one the key presses into and stays -> KEY_FIT.
  3. Tongue pockets with 0.10 / 0.15 / 0.20 mm clearance per side.
     Pick the one the tongue slides into with a light push -> FIT.
Loose parts: tongue, two pins (print head down, as in the kit), one key (flat).

Run: python fit_test.py OUT_DIR
"""
import sys
from pathlib import Path

import cadquery as cq

PIN_D, PIN_LEN, PIN_HEAD = 1.8, 8.0, (4.0, 0.8)   # as halifax.py
KEY = (8.0, 10.0, 2.4)                            # KEY_LR: length (inserted), width, thickness
KEY_END_GAP = 0.3
TONGUE = (14.0, 4.0)                              # width x height (as ROOT_TONGUE)

HOLES = [1.75, 1.80, 1.85, 2.05]   # mm
KEY_FITS = [0.05, 0.10, 0.15]      # mm per side
CLEARANCES = [0.10, 0.15, 0.20]    # mm per side
POCKET_DEPTH = 6.0
PLATE_T = 8.0
PLATE = (88.0, 58.0)
COLS = [-30.0, -10.0, 10.0, 30.0]
ROW_Y = {"pin": 19.0, "key": 1.0, "tongue": -17.0}

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out")
out.mkdir(parents=True, exist_ok=True)


def label(text, x, y):
    return (cq.Workplane("XY").text(text, 3.2, -0.6, halign="center", valign="center")
            .translate((x, y, PLATE_T)))


def pocket(w, h, depth, x, y):
    return (cq.Workplane("XY").box(w, h, depth, centered=(True, True, False))
            .translate((x, y, PLATE_T - depth + 0.01)))


plate = cq.Workplane("XY").box(PLATE[0], PLATE[1], PLATE_T, centered=(True, True, False))
for x, d in zip(COLS, HOLES):
    y = ROW_Y["pin"]
    plate = plate.cut(cq.Workplane("XY").circle(d / 2).extrude(6.0)
                      .translate((x, y, PLATE_T - 6.0 + 0.01)))
    plate = plate.cut(label(f"{d:.2f}", x, y + 6.0))
for x, f in zip(COLS, KEY_FITS):
    y = ROW_Y["key"]
    plate = plate.cut(pocket(KEY[1] + 2 * f, KEY[2] + 2 * f, KEY[0] / 2 + KEY_END_GAP, x, y))
    plate = plate.cut(label(f"{f:.2f}", x, y + 5.0))
for x, c in zip(COLS, CLEARANCES):
    y = ROW_Y["tongue"]
    plate = plate.cut(pocket(TONGUE[0] + 2 * c, TONGUE[1] + 2 * c, POCKET_DEPTH, x, y))
    plate = plate.cut(label(f"{c:.2f}", x, y - 6.5))

tongue = cq.Workplane("XY").box(TONGUE[0], 20, TONGUE[1], centered=(True, True, False))

pins = None
for dx in (-4.0, 4.0):
    p = (cq.Workplane("XY").circle(PIN_HEAD[0] / 2).extrude(PIN_HEAD[1])
         .faces(">Z").workplane().circle(PIN_D / 2).extrude(PIN_LEN)
         .translate((dx, 0, 0)))
    pins = p if pins is None else pins.union(p)

key = (cq.Workplane("XY").box(KEY[0], KEY[1], KEY[2], centered=(True, True, False))
       .edges("|Y").chamfer(0.4))

for name, part in (("plate", plate), ("tongue", tongue), ("pins", pins), ("key", key)):
    cq.exporters.export(part, str(out / f"fit_test_{name}.stl"), tolerance=0.01, angularTolerance=0.1)
print("fit test written to", out)
