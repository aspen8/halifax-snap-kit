# Avro Vulcan B.2 snap kit

Avro Vulcan B.2 at 1:96: 352 mm span, 317 mm long (336 mm with the refuelling probe), about the span of a 1:32 Spitfire. To be a fully printed, multi-colour snap kit like the Halifax and the Hawk.

## Brief (agreed 2026-11-13)

- **Scale:** 1:96, chosen for a span close to the user's 1:32 Spitfire kit (351 mm if that kit is 1:32: its file is not in this repo, so the figure is from the real span, 11.23 m). The shape is built at 1:72 (`SCALE`) and scaled by `PRINT_K` 0.75 on output.
- **Print files:** anti-flash white (Airfix scheme B: XM602, No. 12 Squadron, 1963), and camouflage on top with a plain underside (Airfix scheme A: XM594, Scampton, 1966: grey and green over white). Camouflage wrapped round the underside (as XH558 flew) is an option: alternative lower shells.
- **Display:** stand with the wheels up, and gear down, both in the kit; a bomb bay that can be built open, and a Blue Steel missile option (user, confirmed).
- **For MakerWorld:** a single-colour version for printers without an AMS; plates that fit 256 mm beds; no supports, no glue.

![shape in grey](docs/shape_grey.png)

> **Status: v7: shape fitted to the Airfix A12011 plan and side views, and split into shells.** No joints, colour or print file yet. Not yet split into parts; no joints, colour or print file.

Intakes and wing root (v7, user review): one letterbox mouth a side, tall at the fuselage (about 60% of its depth, from the XH558 photos) and tapering outboard, with the wall between the two engine ducts set back 9 mm. Over the engines the wing's top is not an aerofoil hump: it reaches its crest just behind the intake lip and runs almost straight to the trailing edge, so it meets the fuselage on a straight line, as in the Airfix side view (`WING_ROOT_UP`, `WING_CREST`). Still to do: the splitter plate at the fuselage.

![intakes](docs/intakes_v3.png)

## Parts (v6: first split, no joints yet)

Upper and lower shells, as in a plastic kit, so every underside part prints in one colour and both skins print as top layers. The split surface holds the wing's leading and trailing edges: level at z -4 (1:72) across the centre body, then a plane falling 3.2 degrees to the tip on each outer wing. Upper shells print standing on the split face; lower shells are turned over onto it.

![parts, exploded](docs/parts_exploded.png)

| Part | Printed size (mm) |
|---|---|
| `radome` (on end) | 18 x 19 x 18 |
| `front_upper`, `front_lower` (x 24 to 105: flight deck, canopy, blister) | 61 x 28 x 25, 61 x 26 x 11 |
| `centre_upper`, `centre_lower` (fuselage, intakes, inner wing, tail cone) | 238 x 86 x 22, 238 x 86 x 11 |
| `wing_stbd_upper/lower`, `wing_port_upper/lower` (outboard of y 57) | 165 x 134 x 9, 165 x 134 x 8 |
| `fin` (to become two halves), `probe` | |

All fit a 230 x 250 mm plate. Overhang check (`common/tools/overhang.py`): 0 on the wings and front shells; 943 mm2 on `centre_upper` and 534 mm2 on `centre_lower` (intake duct roofs and jet pipe bores, to be dealt with).

Still to do on the split: joints (keys between the shells, a spar key across each wing joint, plugs at the front and radome joints), the fin as two halves in a slot, separate jet nozzles, gear and bays, bomb bay doors and the Blue Steel, the stand.

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
- **Photos (in `ref/vulcan/`, not in git):** XH558 from below with the bomb bay open (camouflage wraps round the underside), a head-on photo from 1982 (intakes, nose, probe), a top view of a camouflaged Vulcan on a runway (2024, airframe not identified), a straight-down top view (watermarked stock photo: measure only, mind the watermarks when tracing), a top-view camouflage illustration, a wrapped-camouflage underside in flight, XH558's nose and intakes (roundel, badge, lettering, nose gear), XH558's fin (fin flash without white, Union flag, shield, serial, fin cap, jet pipes), and model photos from aircraftinplastic.com.
- The trailing edge is the outermost line of a plan view. The line inboard of it is the elevon hinge line.

## Known gaps and next steps

1. Still wanted: sharper copies of the Airfix A12011 painting guides (scheme A, and scheme B: XM602 in anti-flash white, 1963; both are in `ref/vulcan/` as screenshots), and for XH558 a straight-down view of its upper camouflage.
2. Shape still to do: the fin root fillet, the drooped outer leading edge, the nose gear and main gear bays, the bomb bay, the ECM plate between the starboard jet pipes, the terrain-following radar thimble on the nose.
3. The wing's height on the fuselage, its root thickness and the intake lips come from a silhouette and one head-on photo: check them against more photos. The intakes are plain slots so far (the real lips are rounded, with a splitter plate at the fuselage).
4. Agree the brief (markings, display, colours per plate), then split into parts, add joints, colour and the 3MF.
