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
1. **Test plate round 2: built, waiting for a print.** `kit/halifax_test_plate.3mf`, rebuilt with `cd cad && python test_plate.py OUT` (about 3 min). Sliced clean: plate 1 (inlays) 37 min, plate 2 (black) 1 h 25 min.
   - **Round 1 results (user, 2026-11-07), and what changed:**
     - Prop boss: a little tight, turns but doesn't spin freely. Neck radius 2.4 → 2.3 and axial gap 0.3 → 0.4 (`PROP_BOSS`).
     - Stub axles (main and tail) went through the wheel but didn't grip in the other fork half; the wheels spin freely. `STUB_GRIP` 0.55 → 0.2 on the diameter; `STUB_SPIN` unchanged.
     - Main gear fell out of its socket (it should stay: the socket holds the halves together); the tail gear stayed. The socket was FIT 0.15 per side plus the FIT gap between the fork halves. `gear_socket` now uses `GEAR_PLUG_FIT` 0.08 per side, measured from the closed fork, so it squeezes the halves. Main and tail both.
     - Flexing key (`KEY_NAC`): works well, unchanged.
     - Nacelle nose keys didn't grip. They were coupon-only plain 6 mm keys (too short for flex slots). Now 8 mm flexing keys. The kit's nacelle halves have no nose keys: the wing notch and the flexing lock hold them.
     - G: stays, could be tighter. Fin flash: fell out. Its peg hole (and every inlay peg hole) was +0.55, the same as the stubs that didn't grip. Now `PEG_GRIP` 0.2, `INLAY_FIT` 0.15 → 0.1, and the fin flash has two pegs (behind the red and the blue). Roundel peg holes 3.5 → 3.2 to match (roundels untested). If the fin flash still won't stay, fall back to painting it on the fin (multi-colour, more purge).
     - Wheels: flat inboard face (earlier today), no overhang.
   - **New: grip gauge** (`t6_gauge` plus `t6_peg`). Holes for the 5 mm and 3 mm stubs and the 2.5 mm peg at +0.1/+0.2/+0.3/+0.4 mm (1 to 4 dots above each column). Push the fork-half stubs and the peg tab in: the tightest hole that grips gives `STUB_GRIP` and `PEG_GRIP`, without another round.
   - Ask the user for: prop spin, stub grip, gear staying in both sockets, nose keys, G and fin flash, and the gauge column that grips for each row.
   - **Round 2 results (user, 2026-11-07):** prop spins; stubs grip; both gears stay in their sockets. So `PROP_BOSS`, `STUB_GRIP` 0.2 and `GEAR_PLUG_FIT` are settled. The 8 mm nose keys were too small and didn't grip, so the coupon now has **one KEY_NAC-size flexing key** at the nose centreline (x0 + 10.5, behind the prop-boss slot, coupon 16 mm long): round 3. G and fin flash both stay in (`PEG_GRIP` 0.2, `INLAY_FIT` 0.1, two pegs on the flash): settled, so the fins keep the inlay. The gauge isn't needed: the real parts confirmed every clearance it was there to pick.
   - **Gauge layout, for reading results:** the row nearest the dots is the 2.5 mm peg, then the 3 mm tail stub, then the 5 mm main stub. Columns: 1 dot = +0.1, 2 = +0.2, 3 = +0.3, 4 = +0.4 on the diameter.
   - The kit's nacelle halves have no nose key (the wing notch and the lock hold them). Whether to add one is open.
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
   - **Print the painted fuselage on the wing plate (user, 2026-11-07).** That gives one long plate with all the swaps, in place of a separate fuselage plate and spine plate. Fit checked against the current 3MF, using convex-hull outlines, the kit's 230 × 250 mm usable area and 9 mm between parts (6 mm brim plus 3):
     - both sections fit, standing on end in the strip behind the outer wings (y ≥ 184);
     - the prime tower still fits (for example at 50, 28);
     - with the spine painted back on, each section gets deeper by the spine's thickness, so put the two sections side by side in x (about 90 mm of the 230).
   - **Why it's cheap:** the wing plate already swaps colours twice per layer, every layer up to the outer wing tips at 170 mm (2129 swaps). The fuselage's camo below 170 mm shares those swaps. Only the 17 mm above the wing tips (the front section is 187 mm tall) adds about 210 swaps.
   - **Rough estimate, not sliced:** the combined plate takes about 77 h and 1.2 kg of purge. That replaces wing plate (67 h, 1.08 kg) + fuselage plate (4.5 h) + spine plate (10.5 h, 0.16 kg). A separate camo fuselage plate would have cost about another 1.1 kg.
   - Risk: one ~77 h print holds the wings and the fuselage, so a late failure loses both. Use the brims and watch the first layers.
   - Code: drop the `spine_*` pieces and their keys; paint the camo onto `fuselage_front`/`fuselage_rear` with `kitlib.paint` (the old pre-v2 approach); and change the plate grouping in `colour.py` so the fuselage joins the wing plate (≤ 5 colours: black, earth and green, so fine).
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
