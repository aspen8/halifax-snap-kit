# Avro Vulcan B.2 snap kit

Avro Vulcan B.2 at 1:96: 352 mm span, 317 mm long (334 mm with the refuelling probe), about the span of a 1:32 Spitfire. To be a fully printed, multi-colour snap kit like the Halifax and the Hawk.

## Brief (agreed 2026-11-13)

- **Scale:** 1:96, chosen for a span close to the user's 1:32 Spitfire kit (351 mm if that kit is 1:32: its file is not in this repo, so the figure is from the real span, 11.23 m). The shape is built at 1:72 (`SCALE`) and scaled by `PRINT_K` 0.75 on output.
- **Two print files:** anti-flash white, and XH558's camouflage (grey and green over light grey; check every detail against photos).
- **Display:** stand with the wheels up, and gear down, both in the kit; a bomb bay that can be built open, with a Blue Steel missile as an alternative load.
- **For MakerWorld:** a single-colour version for printers without an AMS; plates that fit 256 mm beds; no supports, no glue.

![shape in grey](docs/shape_grey.png)

> **Status: v3, outer shape only.** One solid in the assembled frame, fitted to the Commons silhouette. Not yet split into parts; no joints, colour or print file.

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

- **Main drawing:** the Wikimedia Commons silhouette "Avro Vulcan B.2 three-view silhouette.png" (1920 px, about 0.51 mm per pixel at 1:72), calibrated in `tools/refs.json` (`plan`, `side`, `front`). The outline sits on it in plan and side view. Its head-on view is drawn about 12% taller than its side view, so use it for spans only.
- **Second source:** the aerospaceweb.org 3-view (`aw_plan`, 1.5 mm per pixel). It agrees on the planform.
- **Length:** the published 99 ft 11 in (30.45 m) includes the refuelling probe. Both drawings give nose tip to tail cone as 0.86 of the span (29.2 m), and the Airfix 1:72 kit is 426 mm long overall. The model is 405 mm at 1:72 without the probe, 426.6 mm with it.
- **Check:** the model's wing area is 365.5 m², against the real 368.3 m² (0.8% low).
- **Photos (in `ref/vulcan/`, not in git):** XH558 from below with the bomb bay open (camouflage wraps round the underside; jet pipe fairings, gear doors, bomb bay), a head-on photo from 1982 (intakes, nose, probe), and model photos from aircraftinplastic.com (underside detail in white).
- The trailing edge is the outermost line of a plan view. The line inboard of it is the elevon hinge line (the first trace took it for the trailing edge and the area came out 13% low).

## Known gaps and next steps

1. Still wanted: a line drawing with panel lines and sections (the Commons vector 3-view "Avro Vulcan B.2 3-view line drawing.svg", or the Airfix A12011 instruction sheets), and a straight-down photo of XH558's upper camouflage. Commons rate-limits the cloud session, and Scalemates and vulcantothesky.org refuse automated access: the user uploads these.
2. Shape still to do: the fin root fillet and fin cap, the drooped outer leading edge, the nose gear and main gear bays, the bomb bay, the ECM plate between the starboard jet pipes, the terrain-following radar thimble on the nose.
3. The wing's height on the fuselage, its root thickness and the intake lips come from a silhouette and one head-on photo: check them against more photos. The intakes are plain slots so far (the real lips are rounded, with a splitter plate at the fuselage).
4. Agree the brief (markings, display, colours per plate), then split into parts, add joints, colour and the 3MF.
