# Slicing results

Sliced on 2026-11-08 with the Bambu Studio 02.08.02.61 command line on macOS, using the settings embedded in each 3MF (Bambu Lab X2D 0.4 nozzle, 0.20 mm Standard @BBL X2D template, with the kit's per-object overrides). Regenerate everything here with:

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

## Full kit (`kit/halifax_kit.3mf`, rebuilt 2026-11-08): 7 plates, 50 h 06 m

Half the time and a third of the purge of the 2026-11-07 kit (102 h 39 m, 1439 g), from three changes on the wing plate:

- **Shorter parts.** Both outer wings and both fuselage sections are split once more, so nothing on plate 1 stands taller than 105 mm (it was 187). A plate swaps colours about twice per layer wherever camo shows, so fewer layers means fewer swaps.
- **0.24 mm layers on plate 1**, as the Spitfire kit: 439 layers instead of 1170.
- **Dark Earth alone on the second (auxiliary) nozzle**, which takes one colour on the user's X2D. Black and Dark Green stay on the main nozzle. Swaps to or from Earth become nozzle changes, with no flush. Every plate packs from x = 21 mm, where the second nozzle reaches.

| Plate | Time | Layers | Layer mm | Filament on the model (g) | Model g | Flush + tower g | Changes |
|---|---|---|---|---|---|---|---|
| 1 wings, tailplane, fuselage | 25h 20m | 439 | 0.24 | Black 232.7, Dark Earth 23.1, Dark Green 20.4 | 276.2 | 262.0 | 439 |
| 2 nacelles | 5h 45m | 89 | 0.16 | Black 42.2, Dark Earth 4.9, Dark Green 3.6 | 50.8 | 40.5 | 68 |
| 3 markings | 3h 22m | 30 | 0.16 | Red 5.6, Blue 7.1, Yellow 0.8, White 0.4 | 13.9 | 45.7 | 90 |
| 4 glazing | 8h 11m | 144 | 0.12/0.2 | Black 1.1, Dark Earth 0.1, Dark Green 0.6, Silk Silver 7.9 | 9.8 | 124.3 | 236 |
| 5 stand base | 3h 47m | 81 | 0.16/0.2 | Dark Earth 50.8, Dark Green 3.5, Yellow 0.5, White 1.0 | 55.8 | 7.0 | 6 |
| 6 small parts | 2h 38m | 80 | 0.12/0.2 | Black 32.1, Yellow 1.9 | 34.0 | 14.4 | 28 |
| 7 small parts | 1h 03m | 139 | 0.12 | Black 13.6 | 13.6 | 0.0 | 0 |
| **All sliced** | **50h 06m** | | | | **454.1** | **493.9** | **867** |

Slicer messages from the command line (all non-critical; every plate slices). The app showed fewer on the previous build: on plate 1 only the D/F loop, which is now in two halves.

- plate 1: `fuselage_front` floating cantilever and `fuselage_rear` floating regions: the joint key-slot ceilings (2.7 mm bridges), the wing-root pockets and the stand socket, all short bridges.
- plate 4: turret_dorsal floating regions. Plate 6: stand_post cantilever. Plate 7: both gun packs cantilever. As before.
- Gone since the first 2026-11-08 build: the tailplane's "ZFiller" note, the D/F loop (now two halves), the wing tips' and wing roundels' floating regions (the roundel sockets and the wing joint's key slot no longer meet).

Notes:

- **Plate 1:** 25h 20m, 262 g of purge and tower, 439 colour changes (was 76 h 50 m, 1157 g, 2286). The underside detail added a few minutes.
- **For comparison, the Spitfire kit's wings-and-fuselage plate** (Elite Squadron, MasterBuilds) slices at 30 h 21 m on the user's X2D at 0.24 mm, with 306 g of purge and tower and 792 changes. Its plate is 84 mm tall.
- **Plate 3 (markings):** 3 h 21 m and 46 g of purge (3 h 40 m and 43 g on 2026-11-07). The inlays are thinner now that their sockets follow the skin, which offsets the four colours all staying on the main nozzle (the second nozzle holds Dark Earth for the whole kit).
- **Nozzle grouping is Manual** (`colour.NOZZLE`, `filament_map_mode`). On "Auto For Flush" the command line put every filament on the main nozzle.

### Joint test (`kit/halifax_joint_test.3mf`), round 3

`cad/joint_test.py`: a slice from each side of the three new joints, cut from the kit parts, at 0.24 mm, and their keys at 0.12 mm. Black only. Round 1 (2026-11-08): the nose joint was good; the tail joint wanted to be tighter; the wing key, at 10–29 % chord and 8 mm deep, peeled open from the trailing edge. Round 2: the wing key is 24 × 21.9 × 3 mm across 20–55 % chord, 12 mm into each piece, under the roundel (whose back is notched over it); the fuselage keys go 9 mm into each piece (8 at the tail), and the tail joint's slots are 0.10 a side. Round 2 (2026-11-09): the tail joint is right at 0.10; the nose and wing joints were a touch loose at 0.15, so they are now 0.10 a side too (round 3).

| Plate | Time | Layers | Layer mm | Filament on the model (g) | Model g | Flush + tower g | Changes |
|---|---|---|---|---|---|---|---|
| 1 joint slices | 1h 08m | 67 | 0.24 | Black 35.7 | 35.7 | 0.0 | 0 |
| 2 keys | 22m | 24 | 0.12 | Black 5.2 | 5.2 | 0.0 | 0 |
| **All sliced** | **1h 30m** | | | | **40.9** | **0.0** | **0** |

## 2026-11-07: before the splits (one nozzle, 0.16 mm)

Plate 1 76 h 50 m with 1157 g of purge; the kit 102 h 39 m, 444 g of model and 1439 g of purge over 7 plates. See git history (11378db) for the full table.

## Before 2026-11-07: the 9-plate kit

As committed in 8ee28d8, 4 of 9 plates failed to slice: the template's 3 tower positions put towers on parts (plates 3 and 8) or let Bambu's default tower run off the bed (plates 5 and 6). With the towers moved on a scratch copy it sliced at 107 h 22 m, 455.5 g of model and 1513.4 g of purge, of which plate 3 (wings on end) was 66 h 46 m and 1077.7 g. See git history for the full table.
