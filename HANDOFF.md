# Handoff (start here in a new session)

State on 2026-11-07, branch `phase1-airframe`, worked on the user's Mac. **`kit/halifax_kit.3mf` is rebuilt and ready to print: 7 plates, all slice with no errors** (102 h 41 m, 444 g of model, 1.44 kg of purge; `docs/slicing.md`). It passes the geometry checks: single pieces, no clashes, ≤ 5 colours a plate, overhangs as before. Read `LESSONS.md`, `TODO.md` and `.claude/skills/snap-kit/SKILL.md` before changing anything.

## How to build
- Full colour build: `cd cad && python -u colour.py OUT project_settings_template.json` (11 min on the Mac). The template is `cad/project_settings_template.json`: the user's Bambu X2D 0.20 mm Standard project settings, taken from `halifax.3mf`. The overrides in `colour.py` (`PRINT_OVERRIDES`, `object_settings`) go on top of it. `write_3mf` places a prime tower on every plate (`kitlib.place_towers`) and prints where.
- Checks: `python halifax.py OUT2` (assembled geometry, 10 min), `tools/interference.py OUT2/assembled --min 2` (the loose keys all sit at the origin, so ignore key-against-key overlaps), `tools/overhang.py OUT/stl`, and a single-piece check on `OUT/stl/*.stl`. Use manifold3d's `decompose()` for that, not trimesh's `split()`: the STLs carry zero-volume slivers from rounding, which trimesh counts as pieces.
- Slice: `python tools/slice.py kit/halifax_kit.3mf [--md]` (about 1 min), after copying `OUT/halifax_kit.3mf` to `kit/`.
- Test plate: `cd cad && python test_plate.py OUT` (3 min).
- Fast previews (seconds): build one part from `halifax.py`, paint it with `colour.colour_part`, render with `tools/closeup.py`. If pyrender can't find a screen (Mac display asleep: "IndexError" in pyglet's `get_default_screen`), use a software painter's render with matplotlib from the preview GLB.

## Setting up on the Mac (done 2026-11-07)
- Python 3.13 venv in `.venv/` (git-ignored): `python3.13 -m venv .venv && .venv/bin/pip install cadquery manifold3d trimesh numpy scipy shapely pillow matplotlib pyrender PyOpenGL rtree scikit-image` (scikit-image is needed by the colour build: `kitlib.raster_section`).
- `cad/ref/` is git-ignored except `camo_plan_green.png`. The side-profile trace `camo_side_npg.png` was never committed; the build now skips it (`colour.side_trace`), since only the old split-fuselage halves were painted from it.
- The Mac's OCC meshes curved faces slightly differently from the cloud's, so a rebuild changes the 3MF bytes without changing the design. Only commit a rebuilt 3MF when the design changed.
- `tools/closeup.py` uses EGL on Linux only; on macOS, pyrender's default pyglet backend.

## What changed in the 2026-11-07 full build
- **Camo painted on the fuselage** (`SPINE_PIECES = False`): no separate spine pieces, pegs or nose keel. The camo is a 0.8 mm skin above the old spine line (`colour.spine_region`), from the plan pattern, carried straight down the sides; black below. The canopy bosses stand on the fuselage.
- **Fuselage on the wing plate:** plate 1 is wings, tailplane, both fuselage sections and the D/F loop. It slices at 76 h 50 m with 1157 g of purge and 2286 changes; the estimate was 77 h and 1.2 kg. 9 plates became 7.
- **Prime towers** placed per plate in clear space (9 mm from every part's outline, x ≥ 22, inside the 230 × 250 area). Before this, 4 of 9 plates failed to slice.
- **Nose key in every nacelle** (`NOSE_KEY_X`, `NOSE_KEY_FIT` 0.1): one KEY_NAC flexing key across the split behind the prop boss; 4 more `key_nacelle_nose_*` parts. Before this, nothing held the halves together at the nose.
- **Exhausts printed with the nacelle halves** (`EXHAUST_SEPARATE = False`), painted black (`colour.exhaust_region`). No separate exhaust parts or sockets.
- **Fits from the test prints** (below) and **flat-faced wheels**.

## Test print results (settled fits, X2D, PLA)
- Prop boss: neck 2.3, axial gap 0.4 (`PROP_BOSS`): spins.
- Stub axles: grip hole +0.2 (`STUB_GRIP`); wheel bore +0.85 spins.
- Gear socket sized from the closed fork halves, 0.08 per side (`GEAR_PLUG_FIT`): both gears stay in.
- Inlays: `INLAY_FIT` 0.1, peg hole +0.2 (`PEG_GRIP`), two pegs on the fin flash: the G and the fin flash stay in.
- Keys: the full-size flexing key (`KEY_NAC`) holds; plain and small (8 mm) keys don't. Nose key at 0.1 per side.
- Details in `LESSONS.md`.

## Next up
1. **Print the kit.** Plate 1 is one 77 h print holding the wings and the fuselage, so a late failure loses both: use the brims and watch the first layers. Look at these non-critical slicer warnings in the app's preview first: `fuselage_rear` and `tailplane` floating cantilever, `df_loop` and `turret_dorsal` floating regions, `stand_post` and both gun packs cantilever. Most are the small overhangs `tools/overhang.py` already accepts.
2. **For later (user): panel lines and detail on the wing undersides.** They're plain because the wings used to print flat. Now they print on end, so the underside can carry detail like the top (see `cad/detail.py`).
3. **Purge (1.44 kg for 0.44 kg of model)**, options not yet decided:
   - Use the X2D's second nozzle: `write_3mf` puts every filament on nozzle 1, and the second nozzle can't reach x < 20.5, so coloured parts would need packing at x ≥ 21.
   - Check in the app whether "Auto For Flush" already spreads filaments over both nozzles.
   - Ship the flat wing pose too.
   - Use real flush volumes in place of the flat 350 mm³.
   - A purge-sink "bomb" was considered and rejected: it doesn't pay on the wing plate.
4. The test plate (`kit/halifax_test_plate.3mf`) is rebuilt with the kit's nose key slot (0.1 fit). It still carries the grip gauge, which isn't needed any more.

## Recent decisions (the details are in git log)
- **Camo:** painted from the plan pattern (Revell trace, `cad/ref/camo_plan_green.png`).
- **Canopy:** two silver-and-black-framed pieces, with camo frames, stepped side windows and a 5-pane windscreen. Nose glazing and turrets are black and silver.
- **Joints:** sprung mushroom boss for the props; two-piece forks with stub axles (5 mm main, 3 mm tail); inlays with a peg on the socket floor and a gripping hole in the inlay; flexing, waisted, Spitfire-style keys.
