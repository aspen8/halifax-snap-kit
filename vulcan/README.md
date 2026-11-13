# Avro Vulcan B.2 snap kit

Avro Vulcan B.2 at 1:96: 352 mm span, 317 mm long (336 mm with the refuelling probe), about the span of a 1:32 Spitfire. To be a fully printed, multi-colour snap kit like the Halifax and the Hawk.

## Brief (agreed 2026-11-13)

- **Scale:** 1:96, chosen for a span close to the user's 1:32 Spitfire kit (351 mm if that kit is 1:32: its file is not in this repo, so the figure is from the real span, 11.23 m). The shape is built at 1:72 (`SCALE`) and scaled by `PRINT_K` 0.75 on output.
- **Two print files:** anti-flash white (Airfix scheme B, XM602, 1963), and camouflage. For the camouflage, to be agreed: XM594 in 1966 (Airfix scheme A: grey and green on top only, white underneath, Blue Steel) or XH558 (camouflage wrapped round the underside).
- **Display:** stand with the wheels up, and gear down, both in the kit; a bomb bay that can be built open, with a Blue Steel missile as an alternative load.
- **For MakerWorld:** a single-colour version for printers without an AMS; plates that fit 256 mm beds; no supports, no glue.

![shape in grey](docs/shape_grey.png)

> **Status: v4, outer shape only.** One solid in the assembled frame, fitted to the Airfix A12011 plan and side views. Not yet split into parts; no joints, colour or print file.

Intakes (v3): one letterbox mouth a side with the wall between the two engine ducts set back 9 mm, after the 1982 head-on photo. Still to do: the lip fairing's outer end stands proud of the wing as a small ear, and there is no splitter plate at the fuselage.

![intakes](docs/intakes_v3.png)

## Build

```bash
.venv/bin/python vulcan/cad/vulcan.py out/vulcan/NAME        # about 10 s
.venv/bin/python common/tools/ref_overlay.py out/vulcan/NAME/assembled plan OUT.png --refs vulcan/tools/refs.json   # also: side, front
.venv/bin/python common/tools/render.py out/vulcan/NAME/assembled OUT.png --views high34,lowfront,highrear --zoom 1.5
```

`vulcan/cad/vulcan.py` holds the shape as station tables. Lofts are ruled point rings built straight in manifold3d (`ring_loft`); CadQuery is not used.

## Shape and references

- **Main drawings:** the Airfix A12011 painting guide, scheme A (XM594, Scampton 1966): flat upper plan, underside plan and both side views, with panel lines, at about 0.97 mm per pixel at 1:72 (a screenshot; a sharper copy would help). Calibrated in `tools/refs.json` as `plan` and `side`. The outline sits on both.
- **Other sources:** the Commons silhouette (`sil_plan`, `sil_front`; sharper, 0.51 mm per pixel, and its wing agrees within about 3 mm, but its tail cone is 17 mm short) and the aerospaceweb.org 3-view (`aw_plan`).
- **Length:** 422.5 mm at 1:72 from nose tip to tail cone: the published 99 ft 11 in (30.45 m), without the probe. With the probe 448.5 mm (32.3 m; published 105 ft 6 in).
- **Check:** the model's wing area is 367.4 m², against the real 368.3 m².
- **Photos (in `ref/vulcan/`, not in git):** XH558 from below with the bomb bay open (camouflage wraps round the underside), a head-on photo from 1982 (intakes, nose, probe), a top view of a camouflaged Vulcan on a runway (2024, airframe not identified), XH558's fin (fin flash without white, Union flag, shield, serial, fin cap, jet pipes), and model photos from aircraftinplastic.com.
- The trailing edge is the outermost line of a plan view. The line inboard of it is the elevon hinge line.

## Known gaps and next steps

1. Still wanted: sharper copies of the Airfix A12011 painting guides (scheme A, and scheme B: XM602 in anti-flash white, 1963, which the user showed in chat but which did not reach the disk), and for XH558 a straight-down view of its upper camouflage.
2. Shape still to do: the fin root fillet and fin cap, the drooped outer leading edge, the nose gear and main gear bays, the bomb bay, the ECM plate between the starboard jet pipes, the terrain-following radar thimble on the nose.
3. The wing's height on the fuselage, its root thickness and the intake lips come from a silhouette and one head-on photo: check them against more photos. The intakes are plain slots so far (the real lips are rounded, with a splitter plate at the fuselage).
4. Agree the brief (markings, display, colours per plate), then split into parts, add joints, colour and the 3MF.
