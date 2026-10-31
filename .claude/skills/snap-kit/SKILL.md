---
name: snap-kit
description: Design a multi-colour, fully printed snap-together scale model kit (PB94 MasterBuilds style) for a Bambu printer, reusing this repo's toolkit. Use when the user wants a new aircraft (or vehicle) kit, or to change the Halifax kit.
---

# Multi-colour snap kit

This repo holds finished kits (Handley Page Halifax B.II in the root `cad/`; BAE Hawk T.1A Red Arrows in `hawk/`) and the reusable pieces for the next one. Read `LESSONS.md` first: it has the workflow, the measured X2D tolerances, the pitfalls that cost time, and a start-of-aircraft checklist (end of the Hawk section).

## Starting a new aircraft

1. **Agree the brief.**
   - Type and mark (engines and variant decide the shape).
   - Span or scale.
   - Printer and bed size, and the colour limit per plate (5 here: AMS plus the auxiliary head).
   - Markings: squadron, codes, serial.
   - Display: gear, stand, or both.
2. **Get references.** Ask the user for kit instructions with plan views (Revell or Airfix PDFs), a 3-view, and a colour profile, **as files on disk**: images pasted into chat live in a temporary folder and can vanish. Copy everything into `ref/` (git-ignored) at once and render PDF pages at 400 dpi (pymupdf). Never commit reference images.
   - Check free disk space and set up the venv first (`requirements.txt`, Python 3.12; about 1.5 GB).
3. **Calibrate.** Add a view for each reference to `<aircraft>/tools/refs.json`: find the mm-per-px scale, the origin, and any tilt from features you can locate on both the drawing and the model. Calibrate every view separately (sheets mix scales) and check the drawing's symmetry.
   - `tools/silhouette.py` gives outline masks of shaded views; `tools/grid.py` gives gridded zooms to read points by hand; `tools/white_regions.py` traces white paint areas.
4. **New folder per aircraft.** Copy `hawk/` (for example to `spitfire/`): `cad/<aircraft>.py` (parameters → parts → poses), `cad/colour.py`, `cad/detail.py`, `tools/refs.json`, `README.md`. It appends the repo's `cad/` to `sys.path` for `kitlib`. Keep shapes as station tables, densified with `dense()` for ruled lofts. All booleans in manifold3d; CadQuery only for lofts and primitives.
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
   - Interference without the `key_*` STLs (keys are modelled at the origin); count inlays per side (they should match).
   - Renders with `tools/render.py` (works on macOS; `cad/render_colour.py` needs EGL) and `tools/closeup.py`. Send the renders.
10. **Write the 3MF** with `kitlib.write_3mf`. Group the plates by colour set and assert at most 5 colours per plate. Use the user's Bambu project settings as the template.
11. **Fit test first** (`cad/fit_test.py`) on a new printer or filament, then set `FIT`, `KEY_FIT` and `AXLE_HOLE_TIGHT`.

## Working habits

- Halifax: a full colour build takes about 40 min; run it in the background. Hawk-style pipeline: geometry about 10 s, colour about 2 min. Build single parts with `python cad/<aircraft>.py OUT name` (geometry) or `ONLY=name` (colour).
- Rebuild into a fresh output folder, so stale part files don't linger.
- Fold every new lesson into `LESSONS.md` and the README before handing over: the user is building a series of aircraft.
- Use manifold3d for heavy booleans. CadQuery is for the parametric solids only.
- When a CadQuery union silently drops a filleted spline solid, check the result volume and nudge the geometry (see `stand_parts`).
- Commit the STLs, the 3MF and the renders with each rebuild.
