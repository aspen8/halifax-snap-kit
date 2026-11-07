# Handoff (start here in a new session)

State on 2026-11-07, branch `phase1-airframe`: `kit/halifax_kit.3mf` is current and passed every check (single pieces, no clashes, ≤ 5 colours a plate, no bad overhangs). Read `LESSONS.md`, `TODO.md` and `.claude/skills/snap-kit/SKILL.md` before changing anything.

## How to build
- Full colour build plus checks, about 60 min: `cd cad && python -u colour.py OUT project_settings_template.json`. The template is `cad/project_settings_template.json`: the user's Bambu X2D 0.20 mm Standard project settings, taken from `halifax.3mf` (`Metadata/project_settings.config`). The overrides in `colour.py` (`PRINT_OVERRIDES`, `object_settings`) go on top of it. Then `python halifax.py OUT2` for the assembled geometry, `tools/interference.py OUT2/assembled --min 2`, `tools/overhang.py OUT/stl`, and a `trimesh` single-piece check on `OUT/stl/*.stl`.
- Fast previews (seconds): build one part from `halifax.py`, paint it with `colour.colour_part` or `colour.frames`, and render it with `tools/closeup.py`. Don't run full builds just to look at a change.
- Previous session's scratch scripts (may be gone): `final3.sh`, `nosecan.py` and `spinecamo.py` in the session scratchpad.

## Next up
1. **Test plate: built, waiting for a print.** `kit/halifax_test_plate.3mf`, two plates as in the full build: the code letter and fin flash (red, white, blue) alone, the other 18 parts in black. Each part keeps the print settings of its kit part (0.12 mm for prop, gear, fin and keys; 0.16 mm and 3 walls as the nacelle and fuselage). Rebuild with `cd cad && python test_plate.py OUT [project_settings_template.json]` (about 3 min). It contains:
   - the nacelle 1 nose halves with the sprung boss (two plain keys hold the halves together), plus a prop;
   - the port "G" in a fuselage-wall coupon, and the stbd fin flash in a fin coupon, both with peg and hole;
   - main and tail gear fork halves and wheels, each with a block carrying its gear socket;
   - a flexing nacelle key with two slot blocks.
   Checks passed: single pieces, no interference, overhangs as in the kit. Render: `docs/test_plate_closeup.png`. Feed the print results back into `LESSONS.md` and the TODO decision on the code letters.
2. **User idea, to discuss first:** "put the fuselage and colours back together and print on the wing plate", to simplify the model. Ask what they mean before building. It could mean merging the spine pieces back into the black body as painted sections, or moving the fuselage onto the wing plate.

## Recent decisions (the details are in git log)
- **Camo:** the spine pieces are painted from the plan pattern (Revell trace, `cad/ref/camo_plan_green.png`). There are 6 pieces, cut where the colours mix and oriented for the fewest purges.
- **Canopy:** two silver-and-black-framed pieces, with camo frames, stepped side windows and a 5-pane windscreen. Nose glazing and turrets are black and silver.
- **Joints:**
  - Props: sprung mushroom boss on each nacelle nose.
  - Gear: two-piece forks with stub axles (5 mm main, 3 mm tail).
  - Inlays (fin flash, code letters): peg on the socket floor, gripping hole in the inlay.
  - Keys: flexing, waisted, Spitfire-style.
