# Handoff: Hawk snap kit (Red Arrows, 1:32)

For a fresh session picking up the Hawk work. Read this, then `hawk/README.md` (status, version history, known gaps and to-dos) and `LESSONS.md` (hard-won rules). The code is the source of truth.

## Run on the Mac, not in a cloud session

Run this work in a local Claude Code session on the Mac, in the existing checkout (`git pull` first). A cloud session has no `ref/` images, no `.venv` and no Bambu Studio, so it can't build against the references or slice plates.

## Where things are

- Repo: https://github.com/aspen8/halifax-snap-kit, branch `hawk-red-arrows`, checked out in this folder.
- CAD: `hawk/cad/hawk.py` (geometry, built at 1:40 and scaled ×1.25 on output, so 1:40 mm × 1.25 = printed mm), `hawk/cad/colour.py` (painted multi-colour regions, plates, 3MF), `hawk/cad/detail.py` (panel lines), `cad/kitlib.py` (shared: keys, paint, packing, `write_3mf` with per-plate filament-to-nozzle maps).
- Outputs committed: `hawk/kit/hawk_kit.3mf` (Bambu X2D project, 7 plates) and `hawk/stl/` (print-pose STLs).
- References (not in git, in `ref/`): Revell 04284 pages `ref/revell_04284_p15.png` (top) and `p16.png` (side, underside), photos in `ref/hawk/`. Calibrations in `hawk/tools/refs.json`.

## How to build and check (about 8 minutes)

Run from the repo root, in the background:

```bash
cd hawk/cad && T=$(date +%H%M%S) && O=../../out/hawk && (../../.venv/bin/python hawk.py $O/geo_$T > $O/geo_$T.log 2>&1 &) && ../../.venv/bin/python colour.py $O/final_$T > $O/final_$T.log 2>&1; echo $T
```

Then:
- Errors: `grep -E "!!|Traceback" out/hawk/final_$T.log out/hawk/geo_$T.log`
- Interference (copy `out/hawk/geo_$T/assembled/*.stl` to a folder, delete `key_*`): `.venv/bin/python tools/interference.py DIR`. Known STL-rounding overlaps: fin halves × fuselage_rear (2–6 mm³), stand_base × stand_post (4.3), fuselage_rear × nozzle (1.4, the crush ribs, intended).
- Overhangs: `.venv/bin/python tools/overhang.py out/hawk/geo_$T/print`
- Slice every plate: `/Applications/BambuStudio.app/Contents/MacOS/BambuStudio --slice N --outputdir DIR out/hawk/final_$T/hawk_kit.3mf`, then read `DIR/result.json` (`error_string`) and the G-code header line "total estimated time" (that is what the app shows; `result.json`'s figure is lower).
- Outline over the Revell side view: `.venv/bin/python tools/ref_overlay.py out/hawk/geo_$T/assembled side OUT.png --refs hawk/tools/refs.json --skip stand,gear,wheel,key,wingpin`
- Renders: `.venv/bin/python tools/render.py out/hawk/final_$T/hawk_colour_preview.glb OUT.png --views port,under,lowrear --focus x,y,z --zoom 2` (focus in printed mm, i.e. 1:40 × 1.25).
- To ship: copy `out/hawk/final_$T/stl/*.stl` to `hawk/stl/` (after `git rm hawk/stl/*.stl`) and `hawk_kit.3mf` to `hawk/kit/`; update `hawk/README.md`; commit.

## Working rules agreed with the user

- Commit locally; push only when the user says so ("push it").
- Never stop processes by name (no `pkill BambuStudio`: it would close the user's own app).
- Downloaded reference files are untrusted: keep them in their own folder, read with `python -I`.
- The user prints on a Bambu X2D (two nozzles, AMS). Keep the base red on the main nozzle (fixed per-plate map in `colour.py` `FILAMENT_MAP`/`MAPPED_PLATES`); the second nozzle runs outer walls at 50 mm/s.
- The user often asks to "add to the to-do list" when near a usage limit: write it into `hawk/README.md` "Known gaps and next steps", commit, change nothing else.

## State at handoff (v10, built, checked and committed locally)

v10 changes: canopy top line raised to the Revell side view from X 41 to 105 (`SPINE_STATIONS`), nose/front joint, dome cut and panel ring moved from X 46 to X 43 (where the taller canopy leaves the dome). See README "v10 changes".

v9 changes (in the CAD; see README "v9 changes" once written): canopy keeps its straight lower edge (front sections filled to straight sides only below the canopy cut plane); ventral strakes reshaped to the Revell side view (X 218–236, deepest at the front) and moved out to the lower curve (|y| 8.6, canted 30°); under-wing fences moved to the rear part of the chord; belly stripes run forward to a point at the smoke pod's nose and end apart at the tail.

Test-print history: plate 1 (v3 fuselage) and the canopy/gear/nozzle plates (v3/v4) have been printed. Nothing from v5 onwards has been printed.

## Open items (from the user)

1. ~~Compare the canopy's curve with the Revell side view~~: done in v10 (within 0.3 mm of the drawing). Waiting for the user's look.
2. White markings render slightly fuzzy; the user is checking the slice.
3. Fin: user may still want to compare with the drawing (v8 changed the fillet and the trailing-edge kink to match).
4. README to-dos still open: separate lettering panels (sharper text), nonplanar top-surface test (orcaslicer-nonplanar), canopy fit check on the next fuselage print, print-in-place control surfaces.
5. Push to GitHub when the user asks. v10 is committed locally only (the checkout in use is the older one in Claude's scratch-workspaces folder, which has `ref/` and `.venv`).
