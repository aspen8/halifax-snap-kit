---
name: snap-kit
description: Design a multi-colour, fully printed snap-together scale model kit (PB94 MasterBuilds style) for a Bambu printer, reusing this repo's toolkit. Use when the user wants a new aircraft (or vehicle) kit, or to change the Halifax kit.
---

# Multi-colour snap kit

This repo holds a finished kit (Handley Page Halifax B.II, `cad/`) and the reusable pieces for the next one. Read `LESSONS.md` first: it has the workflow, the measured X2D tolerances and the pitfalls that cost time.

## Starting a new aircraft

1. **Agree the brief.**
   - Type and mark (engines and variant decide the shape).
   - Span or scale.
   - Printer and bed size, and the colour limit per plate (5 here: AMS plus the auxiliary head).
   - Markings: squadron, codes, serial.
   - Display: gear, stand, or both.
2. **Get references.** Ask the user for kit instructions with plan views (Revell or Airfix PDFs), a 3-view, and a colour profile. Render PDF pages at 400 dpi into `ref/`, which is git-ignored. Never commit reference images.
3. **Calibrate.** Add a view for each reference to a refs JSON (copy `tools/refs.json`): find the mm-per-px scale, the origin, and any tilt from features you can locate on both the drawing and the model.
4. **New folder per aircraft.** For example `spitfire/cad/`. Copy `cad/halifax.py` as the template for parameters → parts → poses, and import `kitlib` (add `../../cad` to `sys.path` or move `kitlib.py` to a shared folder). Keep shapes as station tables: fuselage stations, planform, t/c, nacelles.
5. **Iterate the shape against the drawings** with `tools/ref_overlay.py` until the outline sits on the lines. Cross-check with a second source before showing the user.
6. **Split the kit and add the joints:**
   - Parts lie flat with no supports.
   - Printed keys use `kitlib.key_slots` and `connector_key`.
   - Use 1.8 mm printed pins.
   - Tongues and slots use `FIT`.
7. **Add detail** following `cad/detail.py`: 0.5 mm panel lines, sparse 0.7 mm rivets on structural lines only.
8. **Colour** with `kitlib.paint`:
   - Peel the regions in order. Later ones win.
   - Clip prisms to each part's bounds.
   - Keep camo to up-facing skins.
   - Roundels go in as `kitlib.make_inlay` discs.
9. **Check before every handover:**
   - `tools/interference.py`
   - `tools/overhang.py`
   - `tools/colour_check.py --from below`
   - Renders with `cad/render_colour.py` and `tools/closeup.py`. Send the renders.
10. **Write the 3MF** with `kitlib.write_3mf`. Group the plates by colour set and assert at most 5 colours per plate. Use the user's Bambu project settings as the template.
11. **Fit test first** (`cad/fit_test.py`) on a new printer or filament, then set `FIT`, `KEY_FIT` and `AXLE_HOLE_TIGHT`.

## Working habits

- A full colour build takes about 40 min. Run it in the background. Build single parts with `python cad/halifax.py OUT name` (geometry) or `ONLY=name` (colour).
- Use manifold3d for heavy booleans. CadQuery is for the parametric solids only.
- When a CadQuery union silently drops a filleted spline solid, check the result volume and nudge the geometry (see `stand_parts`).
- Commit the STLs, the 3MF and the renders with each rebuild.
