# Slicing results

Sliced on 2026-11-07 with the Bambu Studio 02.08.02.61 command line on macOS, using the settings embedded in each 3MF (Bambu Lab X2D 0.4 nozzle, 0.20 mm Standard @BBL X2D template, with the kit's per-object overrides). Regenerate everything here with:

```
python tools/slice.py kit/halifax_test_plate.3mf kit/halifax_kit.3mf kit/halifax_joint_test.3mf --md
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

## Full kit (`kit/halifax_kit.3mf`, rebuilt 2026-11-08): 7 plates, 50 h 43 m

Half the time and a third of the purge of the 2026-11-07 kit (102 h 39 m, 1439 g), from three changes on the wing plate:

- **Shorter parts.** Both outer wings and both fuselage sections are split once more, so nothing on plate 1 stands taller than 105 mm (it was 187). A plate swaps colours about twice per layer wherever camo shows, so fewer layers means fewer swaps.
- **0.24 mm layers on plate 1**, as the Spitfire kit: 439 layers instead of 1170.
- **Dark Earth alone on the second (auxiliary) nozzle**, which takes one colour on the user's X2D. Black and Dark Green stay on the main nozzle. Swaps to or from Earth become nozzle changes, with no flush. Every plate packs from x = 21 mm, where the second nozzle reaches.

| Plate | Time | Layers | Layer mm | Filament on the model (g) | Model g | Flush + tower g | Changes |
|---|---|---|---|---|---|---|---|
| 1 wings, tailplane, fuselage | 24h 56m | 439 | 0.24 | Black 228.8, Dark Earth 23.0, Dark Green 20.3 | 272.1 | 262.0 | 439 |
| 2 nacelles | 5h 45m | 89 | 0.16 | Black 42.2, Dark Earth 4.9, Dark Green 3.6 | 50.8 | 40.5 | 68 |
| 3 markings | 4h 30m | 71 | 0.16 | Red 8.8, Blue 8.9, Yellow 1.0, White 0.4 | 19.2 | 61.0 | 120 |
| 4 glazing | 8h 11m | 144 | 0.12/0.2 | Black 1.1, Dark Earth 0.1, Dark Green 0.6, Silk Silver 7.9 | 9.8 | 124.3 | 236 |
| 5 stand base | 3h 47m | 81 | 0.16/0.2 | Dark Earth 50.8, Dark Green 3.5, Yellow 0.5, White 1.0 | 55.8 | 7.0 | 6 |
| 6 small parts | 2h 48m | 139 | 0.12/0.2 | Black 33.2, Yellow 1.9 | 35.2 | 14.4 | 28 |
| 7 small parts | 46m | 80 | 0.12 | Black 9.2 | 9.2 | 0.0 | 0 |
| **All sliced** | **50h 43m** | | | | **452.1** | **509.2** | **897** |

Slicer messages (all non-critical; every plate slices):

- plate 1 error: ZFiller: encounter idx from clip: 49. From the tailplane since its leading-edge fill, as before: a note from Bambu's polygon clipping, not a failed slice.
- plate 1 warnings: df_loop floating regions, as before. New at 0.24 mm: `wing_outer_*` floating regions (the roundel socket and its peg, about 2 mm deep, on a part standing on end), `fuselage_front` and `fuselage_rear` floating cantilever (the wing-root pockets, the stand socket and the key slots: 4 mm bridges). These are the same features as the 0.16 mm kit; the coarser layers trip the warning.
- plate 4: turret_dorsal floating regions. Plate 6: stand_post cantilever. Plate 7: both gun packs cantilever. As before.

Notes:

- **Plate 1:** 24 h 56 m, 262 g of purge and tower, 439 colour changes (was 76 h 50 m, 1157 g, 2286).
- **For comparison, the Spitfire kit's wings-and-fuselage plate** (Elite Squadron, MasterBuilds) slices at 30 h 21 m on the user's X2D at 0.24 mm, with 306 g of purge and tower and 792 changes. Its plate is 84 mm tall.
- **Plate 3 (markings) went up** from 3 h 40 m and 43 g to 4 h 30 m and 61 g. Its four colours all stay on the main nozzle now that the grouping is set by hand; with "Auto For Flush" Bambu seems to have moved some to the second nozzle. The second nozzle holds Dark Earth for the whole kit, so that's the right call.
- **Nozzle grouping is Manual** (`colour.NOZZLE`, `filament_map_mode`). On "Auto For Flush" the command line put every filament on the main nozzle.

### Joint test (`kit/halifax_joint_test.3mf`)

`cad/joint_test.py`: a slice from each side of the three new joints, cut from the kit parts, at 0.24 mm, and their keys at 0.12 mm. Black only.

| Plate | Time | Layers | Layer mm | Filament on the model (g) | Model g | Flush + tower g | Changes |
|---|---|---|---|---|---|---|---|
| 1 joint slices | 56m | 50 | 0.24 | Black 28.9 | 28.9 | 0.0 | 0 |
| 2 keys | 18m | 24 | 0.12 | Black 3.5 | 3.5 | 0.0 | 0 |
| **All sliced** | **1h 14m** | | | | **32.4** | **0.0** | **0** |


## 2026-11-07: before the splits (one nozzle, 0.16 mm)

Plate 1 76 h 50 m with 1157 g of purge; the kit 102 h 39 m, 444 g of model and 1439 g of purge over 7 plates. See git history (11378db) for the full table.

## Before 2026-11-07: the 9-plate kit

As committed in 8ee28d8, 4 of 9 plates failed to slice: the template's 3 tower positions put towers on parts (plates 3 and 8) or let Bambu's default tower run off the bed (plates 5 and 6). With the towers moved on a scratch copy it sliced at 107 h 22 m, 455.5 g of model and 1513.4 g of purge, of which plate 3 (wings on end) was 66 h 46 m and 1077.7 g. See git history for the full table.
