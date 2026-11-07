# Handoff (start here in a new session)

State on 2026-11-07, branch `phase1-airframe`, now worked on the user's Mac. `kit/halifax_kit.3mf` passes the geometry checks (single pieces, no clashes, ≤ 5 colours a plate, no bad overhangs), but **4 of its 9 plates don't slice** because of prime tower positions (see "Slicing" below and `docs/slicing.md`). The test plate slices cleanly and is ready to print. Read `LESSONS.md`, `TODO.md` and `.claude/skills/snap-kit/SKILL.md` before changing anything.

## How to build
- Full colour build plus checks, about 60 min: `cd cad && python -u colour.py OUT project_settings_template.json`. The template is `cad/project_settings_template.json`: the user's Bambu X2D 0.20 mm Standard project settings, taken from `halifax.3mf` (`Metadata/project_settings.config`). The overrides in `colour.py` (`PRINT_OVERRIDES`, `object_settings`) go on top of it. Then `python halifax.py OUT2` for the assembled geometry, `tools/interference.py OUT2/assembled --min 2`, `tools/overhang.py OUT/stl`, and a `trimesh` single-piece check on `OUT/stl/*.stl`.
- Fast previews (seconds): build one part from `halifax.py`, paint it with `colour.colour_part` or `colour.frames`, and render it with `tools/closeup.py`. Don't run full builds just to look at a change.

## Setting up on the Mac (done 2026-11-07)
- Python 3.13 venv in `.venv/` (git-ignored): `python3.13 -m venv .venv && .venv/bin/pip install cadquery manifold3d trimesh numpy scipy shapely pillow matplotlib pyrender PyOpenGL rtree`. That gives cadquery 2.8, trimesh 5.2 and pyglet 2.1, and it all works.
- Smoke test passed: `cd cad && ../.venv/bin/python test_plate.py ../out/test_plate` (3 min on the Mac) gives 20 single-piece parts on 2 plates. `tools/interference.py` is clean, and `tools/overhang.py` matches the kit.
- The Mac's OCC meshes curved faces slightly differently from the cloud's (a few triangles per part, e.g. 776 vs 770 faces), so a rebuild changes the 3MF bytes without changing the design. Only commit a rebuilt 3MF when the design changed.
- `tools/closeup.py` now uses EGL on Linux only. On macOS, pyrender's default pyglet backend works with no settings: `docs/test_plate_closeup.png` was regenerated here and matches the cloud render.
- Slicing: `python tools/slice.py kit/halifax_test_plate.3mf kit/halifax_kit.3mf [--md]` drives the Bambu Studio CLI (02.08.02.61) one plate at a time and prints time, layers, filament per colour, flush waste and every slicer message per plate. Output goes to `out/slice/`. The whole kit takes about 1 min. The command line can map filaments to nozzles differently from the app, so confirm anything odd in the app.
- Build times: geometry only (`halifax.build()`) about 13 min in the cloud, test plate 3 min (both), full colour build about 60 min in the cloud (not yet run on the Mac).

## Next up
1. **Test plate: built, waiting for a print.** `kit/halifax_test_plate.3mf`, two plates as in the full build: the code letter and fin flash (red, white, blue) alone, the other 18 parts in black. Each part keeps the print settings of its kit part (0.12 mm for prop, gear, fin and keys; 0.16 mm and 3 walls as the nacelle and fuselage). Rebuild with `cd cad && python test_plate.py OUT` (about 3 min; it uses `project_settings_template.json`, as the full build). It contains:
   - the nacelle 1 nose halves with the sprung boss (two plain keys hold the halves together), plus a prop;
   - the port "G" in a fuselage-wall coupon, and the stbd fin flash in a fin coupon, both with peg and hole;
   - main and tail gear fork halves and wheels, each with a block carrying its gear socket;
   - a flexing nacelle key with two slot blocks.
   Checks passed: single pieces, no interference, overhangs as in the kit. Render: `docs/test_plate_closeup.png`. Feed the print results back into `LESSONS.md` and the TODO decision on the code letters.
   - **Sliced locally: clean.** Plate 1 (inlays) 37 min, 1.6 g of parts plus 6.7 g of purge. Plate 2 (black) 1 h 12 min, 20.3 g. Plate 2's mix of 0.12 and 0.16 mm parts slices without complaint (Bambu interleaves the heights), so it wasn't split. One non-critical warning: `t4_main_wheel` has floating regions, which is the tyre curve near the bed; the kit wheels get the same. Watch its underside on the print.
2. **Fix the kit's prime towers (4 of 9 plates fail to slice).** `kitlib.write_3mf` copies `wipe_tower_x/y` from the template, which only has 3 positions, from the old 3-plate `halifax.3mf`.
   - Plates 3 and 8: the tower lands on a part (`wing_outer_stbd`, `fin_stbd`).
   - Plates 5 and 6: Bambu's default tower runs off the back of the bed.
   - Fix: have `write_3mf` place a tower per plate in clear space, using the part footprints, a 9 mm clearance and x ≥ 22. A scratch copy patched that way sliced all 9 plates; the positions are in `docs/slicing.md`. Then do a full rebuild (60 min) and re-slice. Not done yet: it's a kit change, waiting for the user's go-ahead.
3. **Purge on the kit is 1.5 kg for 0.46 kg of model** (107 h in all, from the patched copy). Plate 3 (wings on end) alone is 1.08 kg and 67 h, with two black↔camo changes on nearly every layer. Options, for the user to weigh:
   - Use the X2D's second nozzle. `write_3mf` puts every filament on nozzle 1; the second nozzle can't reach x < 20.5, so pack coloured parts at x ≥ 21.
   - Check in the app whether "Auto For Flush" already does this when slicing in the GUI.
   - Ship the flat wing pose too, as LESSONS suggests.
   - Use real flush volumes in place of the flat 350 mm³.
4. **Decided (2026-11-07): put the camo paint back on the fuselage. Start after the test print results are in.** The user wants to drop the separate clip-on spine pieces, paint the camo onto the black fuselage sections, and accept the long print and purge that come with it.
   - Expect plate 1 to look like the wing plate: on end, with two colour changes on most layers.
   - Fix the prime towers (item 2) in the same rebuild, then re-slice.
   - **Purge bomb: considered and rejected.** The idea was a 1000 lb GP bomb set to "flush into this object" to take the purge. On the wing plate it doesn't pay:
     - at 15% infill a 60 × 168 mm sink takes only its own weight (121 g);
     - solid, it takes about 460 g of the 1078 g purge but adds about 25 h and about 80 g of filament in total.
     - Bambu won't let the prime tower itself take another shape.

## Recent decisions (the details are in git log)
- **Camo:** the spine pieces are painted from the plan pattern (Revell trace, `cad/ref/camo_plan_green.png`). There are 6 pieces, cut where the colours mix and oriented for the fewest purges.
- **Canopy:** two silver-and-black-framed pieces, with camo frames, stepped side windows and a 5-pane windscreen. Nose glazing and turrets are black and silver.
- **Joints:**
  - Props: sprung mushroom boss on each nacelle nose.
  - Gear: two-piece forks with stub axles (5 mm main, 3 mm tail).
  - Inlays (fin flash, code letters): peg on the socket floor, gripping hole in the inlay.
  - Keys: flexing, waisted, Spitfire-style.
