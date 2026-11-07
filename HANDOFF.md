# Handoff (start here in a new session)

State on 2026-11-07, branch `phase1-airframe`. The work moves from a cloud session to the user's Mac. `kit/halifax_kit.3mf` is current and passed every check (single pieces, no clashes, ≤ 5 colours a plate, no bad overhangs). Read `LESSONS.md`, `TODO.md` and `.claude/skills/snap-kit/SKILL.md` before changing anything.

## How to build
- Full colour build plus checks, about 60 min: `cd cad && python -u colour.py OUT project_settings_template.json`. The template is `cad/project_settings_template.json`: the user's Bambu X2D 0.20 mm Standard project settings, taken from `halifax.3mf` (`Metadata/project_settings.config`). The overrides in `colour.py` (`PRINT_OVERRIDES`, `object_settings`) go on top of it. Then `python halifax.py OUT2` for the assembled geometry, `tools/interference.py OUT2/assembled --min 2`, `tools/overhang.py OUT/stl`, and a `trimesh` single-piece check on `OUT/stl/*.stl`.
- Fast previews (seconds): build one part from `halifax.py`, paint it with `colour.colour_part` or `colour.frames`, and render it with `tools/closeup.py`. Don't run full builds just to look at a change.

## Setting up on the Mac
- Clone or pull the branch: `git checkout phase1-airframe && git pull`. Everything needed is committed; no files were left in cloud scratchpads.
- Python 3.13 worked in the cloud with: cadquery 2.8, manifold3d, trimesh 5.2, numpy, scipy, shapely, pillow, matplotlib, pyrender, PyOpenGL. In a venv: `pip install cadquery manifold3d trimesh numpy scipy shapely pillow matplotlib pyrender PyOpenGL rtree`.
- `tools/closeup.py` defaults to `PYOPENGL_PLATFORM=egl`, which is Linux-only. Not tested on macOS: try running it with `PYOPENGL_PLATFORM=` set empty, and if that fails, change the `setdefault` line so pyrender uses its default (pyglet) backend.
- Bambu Studio is now available locally, so slice the 3MFs from the command line to check them. Something like `/Applications/BambuStudio.app/Contents/MacOS/BambuStudio --slice 0 --outputdir out/slice kit/halifax_test_plate.3mf`, but check the flags with `--help` first. Look for slicer errors and note print time, filament and purge per plate. Command-line slicing can treat per-object settings differently from the app, so confirm anything odd in the app.
- Build times measured in the cloud (4 cores): geometry only (`halifax.build()`) about 13 min, test plate about 3 min, full colour build about 60 min.

## Next up
1. **Test plate: built, waiting for a print.** `kit/halifax_test_plate.3mf`, two plates as in the full build: the code letter and fin flash (red, white, blue) alone, the other 18 parts in black. Each part keeps the print settings of its kit part (0.12 mm for prop, gear, fin and keys; 0.16 mm and 3 walls as the nacelle and fuselage). Rebuild with `cd cad && python test_plate.py OUT` (about 3 min; it uses `project_settings_template.json`, as the full build). It contains:
   - the nacelle 1 nose halves with the sprung boss (two plain keys hold the halves together), plus a prop;
   - the port "G" in a fuselage-wall coupon, and the stbd fin flash in a fin coupon, both with peg and hole;
   - main and tail gear fork halves and wheels, each with a block carrying its gear socket;
   - a flexing nacelle key with two slot blocks.
   Checks passed: single pieces, no interference, overhangs as in the kit. Render: `docs/test_plate_closeup.png`. Feed the print results back into `LESSONS.md` and the TODO decision on the code letters.
   - Open point: plate 2 mixes 0.12 and 0.16 mm parts, while every full-build plate uses one height. It's a single colour (no prime tower), so Bambu Studio should accept it. If the user wants an exact match, split it into a 0.12 mm plate and a 0.16 mm plate (`PLATE_GROUPS` in `cad/test_plate.py`).
   - Slice it locally first (see above) before printing.
2. **User idea, to discuss first:** "put the fuselage and colours back together and print on the wing plate", to simplify the model. Ask what they mean before building. It could mean merging the spine pieces back into the black body as painted sections, or moving the fuselage onto the wing plate.

## Recent decisions (the details are in git log)
- **Camo:** the spine pieces are painted from the plan pattern (Revell trace, `cad/ref/camo_plan_green.png`). There are 6 pieces, cut where the colours mix and oriented for the fewest purges.
- **Canopy:** two silver-and-black-framed pieces, with camo frames, stepped side windows and a 5-pane windscreen. Nose glazing and turrets are black and silver.
- **Joints:**
  - Props: sprung mushroom boss on each nacelle nose.
  - Gear: two-piece forks with stub axles (5 mm main, 3 mm tail).
  - Inlays (fin flash, code letters): peg on the socket floor, gripping hole in the inlay.
  - Keys: flexing, waisted, Spitfire-style.
