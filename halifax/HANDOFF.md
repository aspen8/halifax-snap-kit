# Handoff (start here in a new session)

State on 2026-11-11, repo `aspen8/snap-kits` (renamed from `halifax-snap-kit`; the old URL redirects), branch `main`, worked on the user's Mac. **Ready for the full print: `halifax/kit/halifax_kit.3mf`, 7 plates, all slice, 50 h 29 m in total** (458 g of model, 495 g of purge; the wing plate is 25 h 35 m). All joints fit-tested (joint tests 1-3, tail tests 1-3). Geometry checks pass: single pieces, no clashes. Read `LESSONS.md` (repo root, both kits), `halifax/TODO.md` and `.claude/skills/snap-kit/SKILL.md` before changing anything.

## Repo layout and workflow (from 2026-11-11)
- The Halifax lives in `halifax/`: `cad/` (scripts, `kitlib.py`, `project_settings_template.json`), `kit/` (3MFs), `stl/`, `docs/`, `tools/refs.json` (reference calibrations). Shared tools are in `common/tools/`; run them from the repo root. The Hawk (another session's kit) is in `hawk/` with its own kitlib and Bambu settings: don't edit those for the Halifax. `phase1-airframe` is merged into `main` and retired.
- **Work on short branches off `main`; commit locally only, and push only when the user says.**
- Build output (`halifax/cad/OUT`, `OUT2`) stays out of git (`out/` in `.gitignore` matches `OUT` on the Mac's case-insensitive disk; `OUT2` is just untracked). `ref/` and `out/` at the root stay untracked.
- `halifax/stl/` is out of date (it still has the separate exhausts): refresh it from the next build.

## How to build
- Full colour build: `cd halifax/cad && python -u colour.py OUT project_settings_template.json` (20 min on the Mac, about 3 GB). The template is `halifax/cad/project_settings_template.json`: the user's Bambu X2D 0.20 mm Standard project settings, taken from `halifax.3mf`. The overrides in `colour.py` (`PRINT_OVERRIDES`, `object_settings`) go on top of it. `write_3mf` places a prime tower on every plate (`kitlib.place_towers`) and prints where.
- Checks (from `halifax/cad`; tools by path, e.g. `python ../../common/tools/interference.py`): `python halifax.py OUT2` (assembled geometry, 10 min), `common/tools/interference.py OUT2/assembled --min 2` (the loose keys all sit at the origin, so ignore key-against-key overlaps), `common/tools/overhang.py OUT/stl`, and a single-piece check on `OUT/stl/*.stl`. Use manifold3d's `decompose()` for that, not trimesh's `split()`: the STLs carry zero-volume slivers from rounding, which trimesh counts as pieces.
- Slice: `python common/tools/slice.py halifax/kit/halifax_kit.3mf [--md]` (about 1 min), from the repo root, after copying `halifax/cad/OUT/halifax_kit.3mf` to `halifax/kit/`.
- Test plate: `cd halifax/cad && python test_plate.py OUT` (3 min).
- Joint test (the 2026-11-08 joints): after the colour build, `cd halifax/cad && python joint_test.py OUT` (seconds; it cuts slices from `OUT/stl`). Tail test: `python tail_test.py OUT`.
- Fast previews (seconds): build one part from `halifax.py`, paint it with `colour.colour_part`, render with `common/tools/closeup.py`. If pyrender can't find a screen (Mac display asleep: "IndexError" in pyglet's `get_default_screen`), use a software painter's render with matplotlib from the preview GLB.

## Setting up on the Mac (done 2026-11-07)
- Python 3.13 venv in `.venv/` (git-ignored): `python3.13 -m venv .venv && .venv/bin/pip install cadquery manifold3d trimesh numpy scipy shapely pillow matplotlib pyrender PyOpenGL rtree scikit-image` (scikit-image is needed by the colour build: `kitlib.raster_section`).
- `halifax/cad/ref/` is git-ignored except `camo_plan_green.png`. The side-profile trace `camo_side_npg.png` was never committed; the build now skips it (`colour.side_trace`), since only the old split-fuselage halves were painted from it.
- The Mac's OCC meshes curved faces slightly differently from the cloud's, so a rebuild changes the 3MF bytes without changing the design. Only commit a rebuilt 3MF when the design changed.
- `common/tools/closeup.py` uses EGL on Linux only; on macOS, pyrender's default pyglet backend.

## What changed on 2026-11-11 (branch `halifax-paint-fixes-guns`)
- **Paint only on the outside** (`colour.Outside`): the user found camo on internal faces (joint faces, key slots, wing-root tongues, the fin-rod slots, the nacelle halves' split faces and wing notch, nacelle parts under the wing). Paint is now kept within `SKIN` of the assembled aircraft's outside, worked part by part (each part with its neighbours clipped to a box round it, grown 0.36 to bridge fit gaps, enclosed slots filled), with `INNER_BLACK` 0.45 of black next to internal faces; nacelles are black under the wing (`wing_shadow`). Joint faces keep a SKIN-wide band of colour at their outer edge. Paint on the parts' bed and top faces (mostly joint faces): nacelle halves 350-405 mm2 to about 32, inner wings 635 to 136, tailplane halves 60 to 3.5. Check with `halifax/cad/OUT/facepaint.py` (untracked; copy it out before a clean).
- **Gun packs in two halves** (`halifax.gun_half`): barrels at 3.0 pitch touch the block's faces, so both halves print with the barrels on the bed (the upper flipped); two 1.4 mm pegs join them (`GUN_PEG`). The guns' cantilever warnings are gone.
- **Astrodome printed on the rear roof glazing** (`astrodome_dome`), no longer a plug-in; its frame paint is kept off the dome.
- Kit: 7 plates, 50 h 12 m, all slice. Build peak memory 3.1 GB, 20 min.

## What changed on 2026-11-10 (later: tail redesign)
- **Tail test 2: a pocket and small tab will never hold a fin.** New design (`halifax.fin_rod`, `fin_rod_slot`, `tail_half`): each fin has a dovetail rod on its inner face (2.3 mm tall, 8 mm wide at the floor, 10 at the top, 16 mm long, with a 1.2 mm slit and a 0.3 mm click tooth each side near its free end). It slides into a slot along the underside of its **tailplane half**; the rod's underside is part of the tailplane's flat underside. Fits: `FIN_ROD_FIT` 0.15 (tail test 3: 0.10 and 0.15 both held once the teeth clicked; 0.15 goes in more easily). The tailplane is now **two halves** (`tailplane_stbd`, `tailplane_port`), each printed on end root down on the wing plate (brim), joined on the centreline inside the fuselage slot by one flexing key (`TAIL_KEY` 20 x 6 x 1.8, `TAIL_KEY_X` 311, fit 0.10; about 0.8 mm walls). The fin flash and stripes stay painted on the fins' bed face; the rod and inner face are black.
- **Tail test 3** (`halifax/kit/halifax_tail_test.3mf`, `halifax/cad/tail_test.py`): both halves (port with the rod slot at 0.15 to compare), both fins, the centre key.

- **Fuselage bomb doors**: engraved under the belly, x 95-198, 15 mm wide, split on the centreline (`detail.FUSE_BOMB_BAY`; positions approximate). Ends ahead of the H2S radome.
- **Tail fit test 1**: the fuselage slot is fine. The fins were bad: printed inner face down, the tip pocket and tab slot opened onto the bed and their roofs bridged the whole tip chord.
- **Fins now print outer face down** (pose `rot x -90*s`): pocket and slot open upwards. Pocket 1.2 mm deep (`FIN_POCKET`, was 0.6; the tailplane is 0.6 longer each side), tab 1.2 into the fin (`FIN_TAB`, was 1.8: 0.9 mm of fin stays outside its slot), tab slot 0.10 a side (`FIN_TAB_FIT`), pocket `FIN_POCKET_FIT` 0.15. **The fin flash is painted** on the outer (bed) face over the yellow, not an inlay (`FIN_FLASH_INLAY = False`): colour swaps only in the first 0.8 mm.
- **Prime towers** are placed with room for 35 x 50 mm and 12 mm clear (`kitlib.TOWER_DEPTH`, `TOWER_CLEAR`): with five colours the props/fins plate failed with "G-code conflicts" at 35 x 35. Kit: 7 plates, 50 h 06 m.
- **Tail fit test 2** (`halifax/kit/halifax_tail_test.3mf`, `halifax/cad/tail_test.py`): the tailplane, and plain fins at the kit fit (pocket 0.15, tab 0.10) and tight (both 0.10). Set `FIN_POCKET_FIT` from the result.

## What changed on 2026-11-09 (after joint test 2)
- **Fuselage "fillet" fixed**: the curved skins were meshed too coarsely (flat bands up to 0.5 mm deep, seen by the code letters on the starboard rear and tail). `halifax.mesh` now uses 0.05 rad (falls back to 0.15 for a part that won't close). Sides now match to 0.03 mm. The kit 3MF is 39 MB and the build takes 16 minutes.
- **Parts start at x 27.5** (`BED_X0`): Bambu printed the fuselage nose brim with Dark Earth, which put the second nozzle at x 15 and failed plate 1.
- **Tail joint right at 0.10 a side. Nose and wing joints a touch loose at 0.15**: both now 0.10 a side (`FUSE_KEY_FIT[0]`, `WING_SPLIT_FIT`). The middle fuselage joint stays at `KEY_FIT` (good in round 1).

## What changed on 2026-11-08 (third round, after joint test 1)
- **Nose joint good. Tail joint: tighter**, 0.10 a side (`FUSE_KEY_FIT`). **Wing key peeled open from the trailing edge** at 10–29 % chord, 8 mm deep: now 20–55 % chord, 12 mm into each piece (24 × 21.9 × 3 mm, as the inner/outer key), running under the roundel. The roundel's socket opens into the slot and its back is notched over the key (`make_inlay(..., cavity=)`), as on the Spitfire's wings.
- **Fuselage keys deeper:** 9 mm into each piece (8 at the tail, which stops 0.8 mm short of the starboard "P"); they were 6 (`FUSE_KEY_LEN`). Leverage against peeling comes from depth.

## What changed on 2026-11-08 (second round, after the user's slicer review)
- **Inlay sockets have flat, tilted floors** (`kitlib.floor_plane`): the plane that best fits the skin under the marking, moved in by the depth. The level floors were 2–7 mm deep on the cambered wing and broke through the wing underside under the roundels; on the hull's curve they made the starboard code letters up to 9.6 mm deep. Wing roundels are now about 3 mm thick, codes 2.3–4.6 mm, fuselage roundels about 4.8 mm. Each inlay is turned flat-back down to print (`make_inlay`/`make_section_inlay` return the rotation), and pegs stand square to the floor (`peg_on_floor`).
- **No socket within 0.8 mm of an underside** (`kitlib.under_band`, `INLAY_FLOOR`), and the depth is measured only where the skin faces out (`INLAY_FACING`). Where a letter runs round under the hull, its lower edge stops there, so no red shows from below. The wing roundel floor is lifted whole rather than trimmed, so its back stays flat.
- **Wing mid-joint key moved forward** to 10–29 % chord to clear the roundel; reversed in the third round (it peeled).
- **D/F loop in two halves** (`df_loop_a`, `df_loop_b`), split on the centreline: each lies on its cut face, so nothing hangs (whole, its narrow mast floated). The roof socket holds the two plug halves together; a dab of glue if they splay.
- **Wing and tailplane underside detail** (`detail.py`): the top's spars, panel joints and flap/aileron hinge lines, the spar rivet rows, and three bomb-cell doors a side in the centre section (`WING_BOMB_CELLS`, approximate). The strips under the nacelles are left plain (`nacelle_zones`) so the nacelles still clamp. The tailplane's hinge and panel lines go on its underside too (its bed face: 0.25 mm deep).

## What changed on 2026-11-08: the wing plate from 77 h to 25 h
- **Why it was slow:** a plate swaps colour about twice per layer wherever camo shows. The wing plate stood 187 mm tall at 0.16 mm (1170 layers, 2286 swaps, about 1.7 min each on the X2D). The Spitfire kit's plate is 84 mm tall at 0.24 mm, and slices at 30 h on the user's X2D.
- **More joints, shorter parts:** the fuselage is 4 sections (`FUSE_CUTS` 102, 196, 297.5: `fuselage_nose`, `_front`, `_rear`, `_tail`), and each outer wing is two (`WING_SPLIT_Y` 145: `wing_mid_*` and the tip, still called `wing_outer_*` because it carries the roundel). Every marking stays on one piece. Each new fuselage joint has two tall flexing keys like the 196 joint (`key_fuselage_nose`, `key_fuselage_tail`); each wing joint one 16 × 17.5 × 3 mm flexing key low in the section (`key_wing_split`, clear of the roundel socket). Plate 1's tallest part is now the wing tip, 105 mm.
- **0.24 mm layers on the wing plate** (`colour.WING_PLATE_LAYER`). The other plates are unchanged.
- **Dark Earth on the second nozzle** (`colour.NOZZLE`; Manual grouping). On the user's X2D the auxiliary nozzle takes one colour. Every plate is packed from x = 21 (`BED_X0`) so the second nozzle reaches; the packer now also tries each group turned 90 degrees (the nacelle halves only fit that way).
- **Tailplane leading edge filled underneath to 45°** (`TAIL_NOSE_RAMP`): it prints flat and the old curve hung in air along the whole span.
- **Not yet printed:** the new joints and the 0.24 mm wing plate. The tailplane slot and wing-root pockets were fit-tested at 0.16 mm; they have the sliding clearance (0.15 a side), so 0.24 should be fine, but check them in the first wing plate.

## What changed in the 2026-11-07 full build
- **Camo painted on the fuselage** (`SPINE_PIECES = False`): no separate spine pieces, pegs or nose keel. The camo is a 0.8 mm skin above the old spine line (`colour.spine_region`), from the plan pattern, carried straight down the sides; black below. The canopy bosses stand on the fuselage.
- **Fuselage on the wing plate:** plate 1 is wings, tailplane, both fuselage sections and the D/F loop. It slices at 76 h 50 m with 1157 g of purge and 2286 changes; the estimate was 77 h and 1.2 kg. 9 plates became 7.
- **Prime towers** placed per plate in clear space (9 mm from every part's outline, x ≥ 22, inside the 230 × 250 area). Before this, 4 of 9 plates failed to slice.
- **Nose key in every nacelle** (`NOSE_KEY_X`, `NOSE_KEY_FIT` 0.1): one KEY_NAC flexing key across the split behind the prop boss; 4 more `key_nacelle_nose_*` parts. Before this, nothing held the halves together at the nose.
- **Exhausts printed with the nacelle halves** (`EXHAUST_SEPARATE = False`), painted black (`colour.exhaust_region`). No separate exhaust parts or sockets.
- **Fits from the test prints** (below) and **flat-faced wheels**.
- **Tailplane leading edge filled underneath to 45°** (2026-11-08, `TAIL_NOSE_RAMP`, `panel(..., ramp=)`): it prints flat, and the old 7° curve into the leading edge hung in air along the whole span (Bambu: "floating cantilever"). The wings are unchanged; they print on end.

## Test print results (settled fits, X2D, PLA)
- Prop boss: neck 2.3, axial gap 0.4 (`PROP_BOSS`): spins.
- Stub axles: grip hole +0.2 (`STUB_GRIP`); wheel bore +0.85 spins.
- Gear socket sized from the closed fork halves, 0.08 per side (`GEAR_PLUG_FIT`): both gears stay in.
- Inlays: `INLAY_FIT` 0.1, peg hole +0.2 (`PEG_GRIP`): the G stays in. (The fin flash was an inlay with two pegs until 2026-11-10; it is painted on the fins now.)
- Keys: the full-size flexing key (`KEY_NAC`) holds; plain and small (8 mm) keys don't. Nose key at 0.1 per side.
- Details in `LESSONS.md`.

## Next up
1. **Full print.** Every joint has now been fit-tested (joint tests 1-3, tail tests 1-3). `halifax/kit/halifax_kit.3mf`: 7 plates, 50 h 29 m, all slice. Start with plate 1 (wings, fuselage, tailplane halves; 25 h 35 m) and watch the brims' first layers. Expected non-critical slicer notes: `fuselage_rear` floating regions (key-slot ceilings and pockets), `turret_dorsal`, `stand_post`, the gun packs.
2. Checks before it (2026-11-11): assembled clash check clean apart from a <= 0.06 mm mesh sliver where each wing root sits flush on the fuselage (two meshes of one surface); every part a single solid.
3. In the app, check that the Filament Grouping panel shows Dark Earth under the auxiliary nozzle.
4. Later: real flush volumes in place of the flat 350 mm3 (purge 495 g for 458 g of model); the ideas in `TODO.md`.

## Recent decisions (the details are in git log)
- **Camo:** painted from the plan pattern (Revell trace, `halifax/cad/ref/camo_plan_green.png`).
- **Canopy:** two silver-and-black-framed pieces, with camo frames, stepped side windows and a 5-pane windscreen. Nose glazing and turrets are black and silver.
- **Joints:** sprung mushroom boss for the props; two-piece forks with stub axles (5 mm main, 3 mm tail); inlays with a peg on the socket floor and a gripping hole in the inlay; flexing, waisted, Spitfire-style keys.
