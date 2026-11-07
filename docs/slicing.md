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

## Test plate (`kit/halifax_test_plate.3mf`): slices cleanly

| Plate | Time | Layers | Layer mm | Filament on the model (g) | Model g | Flush + tower g | Changes |
|---|---|---|---|---|---|---|---|
| 1 inlays | 37m | 39 | 0.16 | Red 1.3, Blue 0.3, White 0.1 | 1.6 | 6.7 | 11 |
| 2 test parts | 1h 12m | 183 | 0.04/0.08/0.12/0.16 | Black 20.3 | 20.3 | 0.0 | 0 |
| **All** | **1h 49m** | | | | **21.9** | **6.7** | **11** |

- **Plate 2 mixes 0.12 and 0.16 mm parts and slices without complaint.** Bambu interleaves the two heights: where they don't line up, it adds 0.04 and 0.08 mm steps, which gives 183 layers in all. So it doesn't need splitting.
- **Plate 1 is mostly purge.** It uses 6.7 g of flush and tower for 1.6 g of inlays, and about 17 of its 37 minutes are flushing.
- **Warning on plate 2:** "t4_main_wheel has floating regions". `tools/overhang.py` agrees: the wheel has 175 mm² of overhang, all below z 0.8 mm. It's the curve of the tyre lifting off the bed. It's the same wheel as the kit's, which gets the same warning on kit plate 8. Watch the wheel's underside on the test print.

## Full kit (`kit/halifax_kit.3mf`): 4 of 9 plates fail

As committed, the kit fails on plates 3, 5, 6 and 8. All four failures come from the **prime tower position**:
- **Where the positions come from:** `write_3mf` copies `wipe_tower_x/y` unchanged from the project template, which was taken from the original 3-plate `halifax.3mf`. It only has positions for plates 1–3, and they don't match the kit's layout.
- **Plates 4–9:** they get Bambu's default spot in the back-left corner.

| Plate | Result | Cause |
|---|---|---|
| 3 wings + tailplane | **fails** | Tower (48.6, 163.7, from the template) sits on `wing_outer_stbd` |
| 5 markings | **fails** (unprintable, code 5) | Default back-left tower grows past the back edge of the bed (y ≈ 265 on a 256 mm bed) |
| 6 glazing | **fails** (unprintable, code 4) | Same, y ≈ 268 |
| 8 small parts | **fails** | Default tower sits on `fin_stbd` |
| 1, 2, 4, 7, 9 | slice | |

With `--slice 0`, Bambu stops at the first failing plate, so `tools/slice.py` slices each plate on its own.

### With the towers moved (scratch copy, not committed)

To check the cause, and to get numbers for every plate, I moved each tower into clear space on a scratch copy of the 3MF. The clearance was 9 mm from every part's bounding box (its 6 mm brim plus 3 mm), and every tower sits at x ≥ 22 so both nozzles can reach it. Tower lower-left positions:

| Plate | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| x, y (mm) | 208, 148 | 208, 174 | 204, 54 | 22, 192 | 194, 88 | 182, 192 | 38, 192 | 204, 42 | 196, 54 |

With those positions every plate slices, with no errors:

| Plate | Time | Layers | Layer mm | Filament on the model (g) | Model g | Flush + tower g | Changes |
|---|---|---|---|---|---|---|---|
| 1 fuselage | 4h 34m | 1170 | 0.16 | Black 103.2 | 103.2 | 0.0 | 0 |
| 2 camo spine | 10h 30m | 418 | 0.16 | Dark Earth 28.0, Dark Green 5.4 | 33.4 | 156.1 | 305 |
| 3 wings + tailplane | **66h 46m** | 1065 | 0.16 | Black 107.9, Dark Earth 18.5, Dark Green 16.3 | 142.7 | **1077.7** | **2130** |
| 4 nacelles | 6h 33m | 68 | 0.16 | Black 39.9, Dark Earth 5.2, Dark Green 3.8 | 48.9 | 68.9 | 136 |
| 5 markings | 3h 39m | 71 | 0.16 | Red 8.6, Blue 8.7, Yellow 1.0, White 0.4 | 18.8 | 43.1 | 78 |
| 6 glazing | 9h 03m | 144 | 0.12 | Black 1.1, Dark Earth 0.1, Dark Green 0.6, Silk Silver 7.9 | 9.8 | 141.4 | 277 |
| 7 stand base | 2h 57m | 81 | 0.16 | Dark Earth 50.8, Dark Green 3.5, Yellow 0.5, White 1.0 | 55.8 | 13.8 | 23 |
| 8 small parts | 2h 48m | 139 | 0.12 | Black 34.7, Yellow 1.9 | 36.6 | 12.4 | 24 |
| 9 small parts | 31m | 80 | 0.12 | Black 6.3 | 6.3 | 0.0 | 0 |
| **All** | **107h 22m** | | | | **455.5** | **1513.4** | **2973** |

(Plate names are by content. Layer mm leaves out the 0.2 mm first layer and bridges.)

### What stands out

- **Purge is 3.3× the model.** 1.5 kg of waste for 0.46 kg of kit, and plate 3 alone is 1.08 kg of it. On plate 3, 50 of the 67 hours are flushing: the wings print on end, so there are two black↔camo changes on almost every one of their 1065 layers.
- **Only one nozzle is used.** `kitlib.write_3mf` writes `filament_map = 1` for every filament, which puts them all on one nozzle of the X2D. It also writes a flat 350 mm³ flush for every colour pair. In the app, "Auto For Flush" may spread the filaments over both nozzles when you slice, so plate 3 could come out much cheaper in the GUI than here. Check it in the app.
- **The second nozzle can't reach the leftmost 20.5 mm of the bed** (`extruder_printable_area`). The packer places parts from x = 0, so mapping Black or the camo colours to the second nozzle fails on plate 3: "G-code in unprintable area of multi-extruder printers". Using both nozzles needs the coloured parts packed at x ≥ 21.
- **Floating-region and cantilever warnings** (non-critical) on: fuselage_front, fuselage_rear, df_loop, spine_02_camo, tailplane, turret_dorsal, stand_post, both main wheels, guns_tail, guns_dorsal. Most are the expected small overhangs that `tools/overhang.py` already accepts. Look at them in the app's preview before a full print.
