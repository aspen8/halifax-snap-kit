# Slicing results

Sliced on 2026-11-07 with the Bambu Studio 02.08.02.61 command line on macOS, using the settings embedded in each 3MF (Bambu Lab X2D 0.4 nozzle, 0.20 mm Standard @BBL X2D template, with the kit's per-object overrides). Regenerate everything here with:

```
python tools/slice.py kit/halifax_test_plate.3mf kit/halifax_kit.3mf --md
```

The G-code, Bambu's `result.json` and the slicer log for each plate go to `out/slice/<3mf name>/plate_N/`.

- "Model g" is filament that ends up in the parts.
- "Flush + tower g" is the waste: total used minus model.
- Times are Bambu's total estimate, including filament changes.

The command line can treat some settings differently from the app (filament-to-nozzle mapping in particular, see below), so open the app to confirm anything that matters before printing.

## Test plate (`kit/halifax_test_plate.3mf`, round 2): slices cleanly

Round 2 adds the grip gauge and peg tab to plate 2 (13 min more).

| Plate | Time | Layers | Layer mm | Filament on the model (g) | Model g | Flush + tower g | Changes |
|---|---|---|---|---|---|---|---|
| 1 inlays | 37m | 39 | 0.16 | Red 1.3, Blue 0.3, White 0.1 | 1.6 | 6.7 | 11 |
| 2 test parts | 1h 24m | 184 | 0.04/0.08/0.12/0.16 | Black 24.1 | 24.1 | 0.0 | 0 |
| **All** | **2h 01m** | | | | **25.7** | **6.7** | **11** |

- **Plate 2 mixes 0.12 and 0.16 mm parts and slices without complaint.** Bambu interleaves the two heights: where they don't line up, it adds 0.04 and 0.08 mm steps, which gives 183 layers in all. So it doesn't need splitting.
- **Plate 1 is mostly purge.** It uses 6.7 g of flush and tower for 1.6 g of inlays, and about 17 of its 37 minutes are flushing.
- **No warnings since the wheels got a flat side.** The first slice warned that "t4_main_wheel has floating regions": the rounded tyre edge lifted off the bed (175 mm² of overhang). The wheels now have a flat inboard face that prints on the bed, and the warning has gone. The kit's wheels don't get the warning either.

## Full kit (`kit/halifax_kit.3mf`, rebuilt 2026-11-08): all 7 plates slice

The camo is painted onto the fuselage, and both fuselage sections print on the wing plate. Each plate's prime tower is placed in clear space by `kitlib.place_towers`, at least 9 mm from every part's outline and at x ≥ 22. The exhausts print with the nacelles.

| Plate | Time | Layers | Layer mm | Filament on the model (g) | Model g | Flush + tower g | Changes |
|---|---|---|---|---|---|---|---|
| 1 wings, tailplane, fuselage | 76h 49m | 1170 | 0.16 | Black 224.2, Dark Earth 23.7, Dark Green 20.8 | 268.7 | 1156.7 | 2286 |
| 2 nacelles | 6h 51m | 89 | 0.16 | Black 42.2, Dark Earth 4.9, Dark Green 3.6 | 50.7 | 69.4 | 137 |
| 3 markings | 3h 40m | 71 | 0.16 | Red 8.8, Blue 8.8, Yellow 1.0, White 0.4 | 19.0 | 43.1 | 78 |
| 4 glazing | 9h 02m | 144 | 0.12/0.2 | Black 1.1, Dark Earth 0.1, Dark Green 0.6, Silk Silver 7.9 | 9.8 | 141.4 | 277 |
| 5 stand base | 2h 57m | 81 | 0.16/0.2 | Dark Earth 50.8, Dark Green 3.5, Yellow 0.5, White 1.0 | 55.8 | 13.8 | 23 |
| 6 small parts | 2h 54m | 139 | 0.12/0.2 | Black 34.8, Yellow 1.9 | 36.8 | 14.4 | 28 |
| 7 small parts | 25m | 80 | 0.12 | Black 3.5 | 3.5 | 0.0 | 0 |
| **All sliced** | **102h 39m** | | | | **444.3** | **1438.8** | **2829** |

Slicer messages (all non-critical; the slice succeeds):

- plate 1 error: ZFiller: encounter idx from clip: 7. This comes from the tailplane since its leading-edge fill (2026-11-08); it shows up on every run. It's a note from Bambu's polygon clipping, not a failed slice: every layer of the tailplane prints and its filament matches its volume. Look at the tailplane's first layers in the app's preview.
- plate 1 warning: It seems object df_loop has floating regions. Please re-orient the object or enable support generation.
- plate 1 warning: It seems object fuselage_rear has floating cantilever. Please re-orient the object or enable support generation.
- plate 4 warning: It seems object turret_dorsal has floating regions. Please re-orient the object or enable support generation.
- plate 6 warning: It seems object stand_post has floating cantilever. Please re-orient the object or enable support generation.
- plate 7 warning: It seems object guns_dorsal has floating cantilever. Please re-orient the object or enable support generation.
- plate 7 warning: It seems object guns_tail has floating cantilever. Please re-orient the object or enable support generation.
- **The tailplane's "floating cantilever" warning has gone.** The tailplane prints flat, and its underside curved up into the leading edge at about 7° from flat over the front 11 mm of the whole span, 800 mm² hanging in air. Under the nose it's now filled to 45° (`TAIL_NOSE_RAMP`). That leaves a 1.2–1.4 mm chamfer under the leading edge; the fuselage slot and the fins are cut from the same shape.


- **Plate 1 is the long one:** 76 h 50 m, with 1157 g of purge and 2286 colour changes. The wings print on end, so black↔camo swaps happen on nearly every layer up to 170 mm, and the fuselage's camo shares those swaps. The earlier estimate was 77 h and 1.2 kg.
- **Purge is 3.2× the model** (1.44 kg for 0.44 kg), down from 1.51 kg over 107 h for the 9-plate kit.
- **Only one nozzle is used.** `kitlib.write_3mf` writes `filament_map = 1` for every filament, and a flat 350 mm³ flush for every colour pair. In the app, "Auto For Flush" may spread the filaments over both nozzles, so check there.
- **The second nozzle can't reach the leftmost 20.5 mm of the bed** (`extruder_printable_area`). The packer places parts from x = 0, so the coloured parts would need packing at x ≥ 21 to use it.

## Before 2026-11-07: the 9-plate kit

As committed in 8ee28d8, 4 of 9 plates failed to slice: the template's 3 tower positions put towers on parts (plates 3 and 8) or let Bambu's default tower run off the bed (plates 5 and 6). With the towers moved on a scratch copy it sliced at 107 h 22 m, 455.5 g of model and 1513.4 g of purge, of which plate 3 (wings on end) was 66 h 46 m and 1077.7 g. See git history for the full table.
