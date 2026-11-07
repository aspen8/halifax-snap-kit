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

## State at handoff (v22, built, checked and committed locally)

v22 changes: snap-fit wheels and tailplanes (`GEAR_SNAP`, `TAIL_SNAP`, `snap_boss`, `snap_socket`, one-piece `nose_gear`, `wheel_m(inb)`, `LEG_T_IN`, `tail_side_y`); smoke pod oval with a long S-curve taper (`POD_W`, `POD_TUBE_END`, `POD_TAIL_END`, trimmed to `outer()`); chevron to a point (`CHEVRON_FRONT`), pod paint ahead of the wing only (`POD_PAINT_X1`); lettering from the render (`LETTER_BOXES`, `_glyph`); kink behind the canopy (`SPINE_STATIONS` 119-142, `FUSE_STATIONS` 117/124 eggs, 140 top); fin up-facing paint below `FIN_FILLET_Z`; aerials black at render positions (5), probe grey, on the gear plate; rear belly stripes full skin depth. Wing pins stay separate (both halves print split face down): ask the user what "print them on end" meant. Fins and canopy plate is now 5.4 h.

v21 changes: white ring round the fuselage roundel (`FUSE_ROUNDEL_RING` in colour.py); pod top line flatter, running out at the ring's top (`INTAKE_STATIONS` from X 150).

v20 changes: the pod top runs straight from its peak (X 142) to the roundel top (`INTAKE_STATIONS` from X 150); `tools/raster.py --light 0,1,0.35` shows the pod crease.

v19 changes: pod top line lower at the lip and highest mid-length (`INTAKE_STATIONS`), canopy cut in two straight runs (`CANOPY_PLANE` now three points, `canopy_plane_z`, `canopy_angle(run)`, `canopy_zone`), nozzle 0.4 higher (`JET_PIPE`). If the pod height still looks off, ask for a straight side-on shot of the pod (Revell says 19.5 at the peak, the render about 18; 18.8 used).

v18 changes: pod undersides painted (`pod_at`, `POD_UNDER_UP` in colour.py); lettering, roundel and cheat line refitted to the Revell side view (`LETTERS`, `LETTER_TILT`, `FUSE_ROUNDEL`, `CHEAT_LO`/`CHEAT_HI`, `SWOOSH_START`); side pods run straight to the roundel (`INTAKE_STATIONS`); rear fuselage boxy above and round below (`FUSE_STATIONS` n_lo/n_up from X 208); smoke pod blunter (`POD_X0`, `POD_NOSE`, `POD_TAIL_END`, tail loft); nozzle rim 6.0 (`NOZZLE["rim"]`). `tools/raster.py` renders the preview GLB without speckle. Still open: squadron badge, serial and aerial detail; lettering font is DejaVu Sans Bold (the real one is narrower, with "AIRFORCE" closer set).

v17 changes: the user found a source of clean renders from any angle (`ref/hawk/renders/`); v17 reworks the underside white (`under_white`), canopy hoops (`CANOPY_FRAMES_X`), wing fins and leading-edge fences (`WING_FINS`, `WING_LE_FENCES` in hawk.py, `WHITE_WING_FINS` in colour.py) and the fin flag trace against them, and paints the wings and fuselage from their shape before the panel grooves (`P_plain`). Open from the review, not done: the rear fuselage looks boxier from behind than the reference; lettering slightly larger and higher in the reference; the reference's small aerials, squadron badge and serial are not modelled. The user can supply more angles on request.

v16 changes (paint, plus the rudder top groove): glyph-only watermark mask with majority smoothing (`tools/trace_colours.py`), no flag below the rudder's bottom edge (`RUDDER_FOOT_X`), fin skins taken before the grooves (`P_plain` in `colour.py`), rudder top groove stops 1 mm short of the TE (`RUDDER_TOP_STOP` in `detail.py`), traced outlines smoothed (`FLAG_EDGE_SMOOTH`).

v15 changes (paint only): the port photo's watermark glyphs are masked out of the trace (`mask` in `hawk/tools/fin_flag_port.json`, new optional key in `tools/trace_colours.py`). The user confirmed starboard looks right.

v14 changes (paint only): the fin flag is traced from the two close-up photos instead of the HobbyBoss sheet (`hawk/tools/fin_flag_*.json`; the photo file names are swapped: `photo_fin_stbd_closeup.webp` is the port side). Re-run `tools/trace_colours.py` per side to regenerate `ref/hawk_white/fin_*.json`, then re-check the swoosh/flag seam (`SWOOSH_TOP`) and the trailing-edge corner. The user asked for the flag to match the reference photos; v13's red-corner tweak is superseded by what the photos show. See README "v14 changes".

v13 changes (paint only): the flag's lower-aft fit point is at (te(30), 30) in `hawk/tools/fin_flag_*.json`, so the flag's red diagonal crosses the TE's bottom corner and runs into the angled piece (user: "should flow seamlessly into the red part of the flag"); the flag's lowest 10 mm is stretched down to the fuselage line (`FLAG_BASE_STRETCH`); the swoosh re-matched (`SWOOSH_TOP`). After any re-trace, re-check the TE corner colours and the swoosh/flag seam. See README "v13 changes".

v12 changes (paint only): flag carried aft to the trailing edge, clipped to the straight TE line so the angled lower TE piece is red; the swoosh's end is set per side (`SWOOSH_TOP` in `colour.py`) to meet each side's flag white at the fin root; no "60" markings (user). See README "v12 changes".

v11 changes: fin LE, TE, tip and fillet fitted to the Revell side view (`FIN_LE`, `FIN_TE`, `FIN_TIP_R` 22 mm rounded tip, `FIN_FILLET_Z`/`FIN_SPINE_Z`); the flag trace refitted to the new corners (`hawk/tools/fin_flag_*.json`, re-run `tools/trace_colours.py` to regenerate `ref/hawk_white/fin_*.json`). See README "v11 changes".

v10 changes: canopy top line raised to the Revell side view from X 41 to 105 (`SPINE_STATIONS`), nose/front joint, dome cut and panel ring moved from X 46 to X 43 (where the taller canopy leaves the dome). See README "v10 changes".

v9 changes (in the CAD; see README "v9 changes" once written): canopy keeps its straight lower edge (front sections filled to straight sides only below the canopy cut plane); ventral strakes reshaped to the Revell side view (X 218–236, deepest at the front) and moved out to the lower curve (|y| 8.6, canted 30°); under-wing fences moved to the rear part of the chord; belly stripes run forward to a point at the smoke pod's nose and end apart at the tail.

Test-print history: plate 1 (v3 fuselage) and the canopy/gear/nozzle plates (v3/v4) have been printed. Nothing from v5 onwards has been printed.

## Open items (from the user)

1. ~~Compare the canopy's curve with the Revell side view~~: done in v10 (within 0.3 mm of the drawing). Waiting for the user's look.
2. White markings render slightly fuzzy; the user is checking the slice.
3. ~~Fin against the drawing~~: done in v11 (outline within about 0.4 mm of the Revell side view, rounded tip). Waiting for the user's look.
4. README to-dos still open: separate lettering panels (sharper text), nonplanar top-surface test (orcaslicer-nonplanar), canopy fit check on the next fuselage print, print-in-place control surfaces.
5. ~~Rudder hinge groove red line and TE speck~~: fixed in v16.
6. Push to GitHub when the user asks. v10 to v21 are pushed; v22 is committed locally only (the checkout in use is the older one in Claude's scratch-workspaces folder, which has `ref/` and `.venv`).
