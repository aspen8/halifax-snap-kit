# Handoff (start here in a new session)

State on 2026-11-07, branch `phase1-airframe`: `kit/halifax_kit.3mf` is current and passed every check (single pieces, no clashes, ≤ 5 colours a plate, no bad overhangs). Read `LESSONS.md`, `TODO.md` and `.claude/skills/snap-kit/SKILL.md` before changing anything.

## How to build
- Full colour build plus checks, about 60 min: `cd cad && python -u colour.py OUT project_settings_template.json`. Then `python halifax.py OUT2` for the assembled geometry, `tools/interference.py OUT2/assembled --min 2`, `tools/overhang.py OUT/stl`, and a `trimesh` single-piece check on `OUT/stl/*.stl`.
- Fast previews (seconds): build one part from `halifax.py`, paint it with `colour.colour_part` or `colour.frames`, and render it with `tools/closeup.py`. Don't run full builds just to look at a change.
- Previous session's scratch scripts (may be gone): `final3.sh`, `nosecan.py` and `spinecamo.py` in the session scratchpad.

## Next up
1. **Test plates** (not built yet). One small 3MF that tests the new fits without a full print:
   - Sprung prop boss: the nose of one nacelle half-pair plus one prop.
   - A code letter in a fuselage-wall coupon, and a fin flash in a fin-skin coupon, both with the floor peg and the hole in the inlay.
   - Main gear: the two fork halves and the wheel. Tail gear: the two fork halves and the wheel.
   - A flexing key in a slot coupon.

   Make it a script, `cad/test_plate.py`, that reuses the `halifax.py` and `colour.py` builders: cut each part to a small box, then `kitlib.write_3mf`.
2. **User idea, to discuss first:** "put the fuselage and colours back together and print on the wing plate", to simplify the model. Ask what they mean before building. It could mean merging the spine pieces back into the black body as painted sections, or moving the fuselage onto the wing plate.

## Recent decisions (the details are in git log)
- **Camo:** the spine pieces are painted from the plan pattern (Revell trace, `cad/ref/camo_plan_green.png`). There are 6 pieces, cut where the colours mix and oriented for the fewest purges.
- **Canopy:** two silver-and-black-framed pieces, with camo frames, stepped side windows and a 5-pane windscreen. Nose glazing and turrets are black and silver.
- **Joints:**
  - Props: sprung mushroom boss on each nacelle nose.
  - Gear: two-piece forks with stub axles (5 mm main, 3 mm tail).
  - Inlays (fin flash, code letters): peg on the socket floor, gripping hole in the inlay.
  - Keys: flexing, waisted, Spitfire-style.
