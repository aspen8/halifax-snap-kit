# Halifax snap kit

Handley Page Halifax B Mk II Series IA (Merlin XX), 1:60 scale, 500 mm span.
A fully printed multi-colour snap kit in the style of PB94's MasterBuilds, for the Bambu Lab X2D: no glue, no filament pins, at most 5 colours on any plate.

![colour render](docs/colour_render.png)

## Print it

Open `kit/halifax_kit.3mf` in Bambu Studio. Every part is placed for printing, with the filaments assigned.

The wings print standing on end, like the fuselage. Layer lines then run along the span and barely show, and the leading edges come out smooth. Printed flat, the leading-edge undersides are rough overhangs. The cost is more colour changes and purge on the wing plate. The flat layout can still be generated with `HALIFAX_WING_POSE=flat`, for reference.

1. Print the fit test first (`stl/fit_test_*`), then adjust `AXLE_HOLE_TIGHT`, `KEY_FIT` and `FIT` in `cad/halifax.py` if needed. The X2D values are already set.
2. Load the filaments for each plate. The X2D's AMS holds 4 and the auxiliary head adds a 5th.

| Plate | Parts | Filaments |
|---|---|---|
| Fuselage | Front and rear body sections, standing on end (use a brim) | Black |
| Spine (Dark Green) | 4 camo spine pieces, on end | Dark Green |
| Spine (Dark Earth) | 4 camo spine pieces (the nose piece lies flat) | Dark Earth |
| Wings | Inner and outer panels, tailplane | Black, Dark Earth, Dark Green |
| Nacelles | 8 nacelle halves | Black, Dark Earth, Dark Green |
| Fins, roundels and codes | Fins, roundel inlays, NP-G code letters | Black, Red, Blue, Yellow, White |
| Canopies and turrets | Canopy, rear roof glazing, nose, turrets, astrodome, gun packs | Black, Silk Silver |
| Display stand | Camo plinth with badge and name, swept blade | Black, Dark Earth, Dark Green, Yellow, White |
| Props and gear | Props, prop shafts, exhausts, gear, wheels, pins, keys | Black, Yellow |

Print settings are already in the files, set up for the X2D 0.4 mm nozzle:

- **Layers:** 0.16 mm, or 0.12 mm on the canopy plate and the props, gear and keys plate.
- **Infill and supports:** gyroid 15% infill, no supports.
- **Brim:** a 6 mm brim on everything that stands on end. The fuselage sections also get 3 walls.

Filament presets are left as PLA Basic. In Bambu Studio, pick your own preset for each slot (matte for the camo, silk for the canopies) so the temperatures match. The canopy and turret slot is set to **silk silver** for a display finish. Swap it for clear PETG if you want see-through glazing, and print the black frames in PETG on that plate too.

The single-colour STLs are in `stl/`, in print orientation.

## Kit contents (102 parts)

- **Fuselage (Lancaster-style):**
  - 2 full-width black body sections, printed on end so there's no seam along the spine.
  - 8 single-colour camo spine pieces that sit on the scalloped demarcation line, cut where the NP-G profile changes colour.
- **Airframe:** 4 wing panels, 8 nacelle halves, tailplane, 2 fins.
- **Colour inlays:**
  - Type B wing roundels and C1 fuselage roundels.
  - The NP-G code letters in red.
  - All press into black-lined sockets.
- **Clear parts:** perspex nose, cockpit canopy, rear roof glazing, astrodome, dorsal and tail turrets, all with black frame lines. Plus 2 gun packs.
- **Engines:** 4 props with yellow tips, 4 prop shafts with captive flanges (the props spin), 8 exhaust banks.
- **Gear:** 2 main gear forks and wheels, tailwheel and printed axle pins. For display on the stand there are 2 wheels-up inserts that show the retracted main wheels.
- **Connector keys:**
  - 10 spine to body.
  - 6 at the front/rear joint.
  - 2 at the inner/outer wing joints.
  - 8 in the nacelles.
  - 2 at the tailplane tips into the fins.
- **Display stand:**
  - A swept "swan-neck" blade that prints flat on its side.
  - A plinth (190 × 120 mm, bevelled underside) with a Dark Earth/Dark Green camo top and a yellow pinstripe.
  - A raised white Halifax silhouette, and the name in raised white: HANDLEY PAGE HALIFAX / B MK II SERIES IA / 158 SQN RAF · NP-G · LV917.

**Surface detail** (sized like PB94's):
- 0.5 mm panel lines and deeper hinge lines.
- Fuel filler caps, the dinghy hatch, the crew door, roof hatches and nose windows.
- Paired rivet rows along the spars and the lower fuselage seam.
- Radiator intakes with vanes and the D/F loop fairing.

## Assembly

1. **Fuselage.**
   - Join the front and rear body sections on the 6 joint keys.
   - Drop the canopy and rear roof glazing over their locating bosses, and press in the astrodome and the nose spigot.
   - Slide both inner wing root tongues into their side pockets, port forward and starboard aft.
   - Lay the tailplane on its seat.
   - Press the spine pieces on, nose to tail, on their keys. The piece over the tail holds the tailplane down, and the piece over the joint locks the two sections together.
   - Press in the red code letters and the roundels.
2. **Wings.** Join each outer panel to its inner panel with a wing key. The joint faces set the 5° dihedral. Press the wing roundels into their sockets.
3. **Nacelles.** Push the exhaust banks into their side slots. Drop a prop shaft into the inboard half, with its flange in the pocket. Close the outboard half around the wing on the nacelle keys, then press the prop onto the hex boss.
4. **Tail.** Push a key into each tailplane tip and press the fins on.
5. **Turrets.** Fit the gun packs into the turrets. Pin the turrets on: the dorsal turret rotates.
6. **Display.** Either fit the gear (wheels on the headed pins, forks into their sockets) or put the model on the stand. With the gear down it sits tail-down at 8.7°. For the stand, push the blade's tenon into the plinth, fit the wheels-up inserts, and lower the model onto the key at the blade tip: it sits 5° nose-up.

## Files

- `cad/kitlib.py`: the reusable toolkit for any snap kit: colour painting, inlays, printed keys, text, the Bambu 3MF writer. Nothing in it is Halifax-specific.
- `cad/halifax.py`: parametric airframe and kit split (CadQuery).
- `cad/detail.py`: panel lines, hatches and rivets.
- `cad/colour.py`: colour scheme, roundel inlays and the Bambu 3MF writer.
- `cad/fit_test.py`: tolerance test coupon.
- `cad/render_colour.py`: colour preview renders.
- `cad/ref/camo_plan_green.png`: camo pattern traced from the Revell plan view.
- `stl/`: single-colour STLs in print orientation, with surface detail.
- `kit/halifax_kit.3mf`: the multi-colour kit.
- `docs/`: renders, the side view and the plan overlay.
- `tools/`: checks used while building:
  - `ref_overlay.py`: model outline over a reference drawing, calibrated in `tools/refs.json`.
  - `interference.py`: overlapping parts.
  - `overhang.py`: printability of the print poses.
  - `colour_check.py`: stray colours, e.g. camo on the underside.
  - `closeup.py`: close-up renders.
- `LESSONS.md`: the workflow, X2D tolerances and pitfalls. Read it before starting the next aircraft.

To rebuild (Python 3.10–3.12):

```
pip install cadquery trimesh manifold3d scikit-image matplotlib shapely lxml
python cad/colour.py out [project_settings.json]
```

## Accuracy

Geometry was measured from the Revell 1/72 Halifax B/GR II Srs IA plan views and a 51 Sqn side profile.

- Wing planform, nacelle positions and tail match the plans to about 1 mm. Wing area works out at 116.6 m² full size.
- Wing incidence is 2° at the root. The undersides are flat from 15% chord so they print without supports.
- The camo on the wings, tailplane and nacelles is the Revell plan-view pattern. For NP-G, the fuselage band is traced from the aircraft's own profile and carried over the roof, above a scalloped demarcation line.
- Nose dome, cockpit, turret, astrodome and D/F loop come from the Revell side elevation, cross-checked against the Wikipedia Mk II Srs IA drawing (overlay in `docs/overlay_revell_side.png`).
- Markings default to 158 Sqn NP-G (LV917): scalloped demarcation and 4 Group yellow fin stripes. To use 51 Sqn MH-E instead, set `HALIFAX_MARKINGS=MH-E` before running `cad/colour.py`.
- No H2S radome: that's a Mk III / GR.II feature. Set `H2S_RADOME = True` in `cad/halifax.py` to add it.

## Reference images (not in git)

The shape and markings depend on reference drawings. They're copyrighted, so they're not committed: keep them in `ref/` (git-ignored) or a private repo. Without them `tools/ref_overlay.py` can't redraw the overlays, though everything measured from them is already in the code and `tools/refs.json`.

| File in `ref/` | Source | Used for |
|---|---|---|
| `revell_04394_p14.png` | Revell 04394 Halifax B/GR II Srs IA instructions, page 14, rendered at 400 dpi | Side and plan shape, camo pattern, glazing frames |
| `wikipedia_halifax_3view.png` | Wikipedia Halifax 3-view (Mk I to Mk III side views) | Cross-check of the side profile |
| `profile_158sqn_NP-G.jpg` | 158 Sqn LV917 NP-G colour profile | Markings (default) |
| `profile_51sqn_MH-E.jpg` | 51 Sqn MH-E colour profile | Alternative markings |

