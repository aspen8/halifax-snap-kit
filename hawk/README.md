# Hawk snap kit

BAE Systems Hawk T.1A of the Red Arrows, 1:40 scale: 235 mm span, 299 mm long with the probe.
Fully printed multi-colour snap kit for the Bambu Lab X2D, built the Halifax v2 way: red fuselage sections printed on end with no centre seam, and the white markings as press-in inlays.

![colour render](docs/colour_render.png)

| On the stand | Gear down |
|---|---|
| ![on stand](docs/on_stand.png) | ![on gear](docs/on_gear.png) |

![fin close-up](docs/fin_closeup.png)

> **Status: v1, not yet test-printed.** The geometry passes the three checks in `LESSONS.md` (single pieces, interference, overhangs). The fits use the Halifax fit-test numbers. Print the fuselage joint, one wing root and a few letter inlays first.

## Print it

Open `kit/hawk_kit.3mf` in Bambu Studio. Its 6 plates have the filaments already assigned.

| Plate | Parts | Filaments |
|---|---|---|
| Fuselage and red parts | Front and rear fuselage on end (brim), radome on its back face (probe up), tailplanes, smoke pod halves, aerials, keys | Red |
| Wings | Both wings flat; white underside chevrons in the first layers | Red, White |
| Fins, roundels and white inlays | Fin halves (Union flag in the skin), roundels, cheat-line, belly-stripe and letter inlays | Red, White, Blue |
| Canopy and cockpit | Solid canopy (print at 100% infill for clarity), tandem cockpit tub | Clear, Black, Grey |
| Display stand | Plinth with red/white/blue pinstripe and raised lettering, swept blade | Black, Red, White, Blue |
| Gear | Nose and main legs, wheels, axle pins | Grey, Black |

Suggested settings: PLA, 0.16 mm layers for the inlay and gear plates and 0.2 mm elsewhere, 2 walls, 15% gyroid infill, no supports. Use a brim on the front fuselage section, which stands 159 mm tall.

## Kit contents (92 parts)

- **Airframe:**
  - radome with pitot probe
  - front and rear fuselage sections
  - 2 fin halves, which carry the spine cap and the dorsal fillet
  - 2 wings
  - 2 tailplanes with 10° anhedral
  - smoke pod (2 halves)
  - 3 aerials
- **Cockpit:**
  - solid clear canopy with black frames
  - tandem tub with the raised rear seat, side consoles, 2 seats (headboxes, firing handles, grey cushions), 2 instrument panels with coamings, and control columns
- **White inlays:**
  - cheat line in 8 pieces
  - tail swoosh, 2 pieces per side
  - 9 belly-stripe pieces
  - 26 letters ("ROYAL AIR FORCE" on each side)
- **Roundels:**
  - 2 on the fuselage
  - 2 wing roundels that pass right through the wing, so one disc shows above and below
- **Gear:** nose leg, 2 main legs, 3 wheels with grey hubs, headed axle pins.
- **Keys:**
  - 5 at the fuselage joint
  - 1 radome key
  - 3 joining the fin halves (1 full key in the spine cap, 2 short ones lower in the fin)
  - 3 joining the pod halves
  - 2 pod-to-belly
- **Stand:** a swept blade on a 170 × 110 mm plinth. The model sits 6° nose-up on a key that passes through the smoke pod.

**Surface detail:**
- 0.5 mm panel lines, with deeper hinge lines on the flaps, ailerons and rudder (top and bottom).
- Access panels and a fuel filler cap.
- Rivet rows on the spars.
- Intake ducts with a boundary-layer splitter gap.
- A recessed jet pipe with its cone.

## Assembly

1. **Cockpit and canopy.** Drop the cockpit tub into the front section. The canopy then sits on it: the seat headboxes and coamings nest into pockets under the canopy, which locates it.
2. **Fuselage.**
   - Join the front and rear sections on the 5 joint keys.
   - Key the radome on.
   - Press in the white inlays and the roundels. Letters are numbered in reading order on each side: `inlay_letter_port_01` and `inlay_letter_stbd_01` are both the R.
3. **Fin.** Join the halves on their 3 keys: the full key goes in the spine cap, the 2 short ones in the fin. Then push the fin's root tongue into the slot in the spine.
4. **Wings and tailplanes.** Slide the root tongues into the side pockets. On both the wings and the tailplanes, the port tongue goes forward and the starboard tongue aft. Press the wing roundels into their through-holes.
5. **Smoke pod.** Join the halves on 3 keys and push them onto the 2 belly keys.
6. **Display.** Either fit the gear (wheels on the headed pins, legs into their sockets) or use the stand: push the blade's tenon into the plinth and lower the model onto the key.

## Accuracy

The shape is measured from the Revell 04284 Hawk T.1A (Red Arrows) instruction sheet, pages 15 and 16, rendered at 400 dpi. The calibration is in `tools/refs.json`, and the overlays are `docs/overlay_revell_*.png`.

- Scaled by the real span of 9.39 m. As cross-checks, the wing area comes out at 16.8 m² (real 16.69), the root chord at 2.66 m (real 2.65), and the length including the probe at 11.96 m.
- The side views on the sheet are drawn about 12% larger than the plan views, so each view has its own calibration.
- The plan view's wings sit about 20 px off the fuselage centreline, and its two halves differ by 5%. The model uses the average of the two halves.
- The undersides are flat from 15% chord, so the wings and tailplanes print without supports.

## Markings

The scheme is the current one, with the Union-flag fin. It combines two sheets:

- **Fin flag and tail swoosh:** traced from the HobbyBoss 81738 side views with `tools/trace_colours.py`, one trace per side. The specs are `tools/fin_flag_*.json` and `tools/side_white_*.json`.
  - Each view is fitted to the model through its fin corners and the nose tip, so the flag lands exactly on our fin.
  - That fit drifts by 2–4 mm lower down the fuselage. So the swoosh is warped vertically to meet the roundel at its lower end, while it still joins the fin's white band at the root.
- **Cheat line, lettering and roundels:** follow the Revell sheet.
  - The cheat line is a constant-width stripe along the Revell trace.
  - The lettering is regenerated as text, so it reads correctly on both sides.
  - The roundels are Type D (red, white and blue in thirds).
- **Underside chevrons and belly stripes:** traced from the Revell underside view (`tools/white_regions.py`).
- **Where the traces live:** in `ref/hawk_white/`, which is git-ignored. Re-run the trace commands below to regenerate them.

## Rebuild

From the repo root, with `requirements.txt` installed:

```
.venv/bin/python tools/white_regions.py side  ref/hawk_white/side.json  --refs hawk/tools/refs.json
.venv/bin/python tools/white_regions.py under ref/hawk_white/under.json --refs hawk/tools/refs.json
for s in port stbd; do
  .venv/bin/python tools/trace_colours.py hawk/tools/fin_flag_$s.json   ref/hawk_white/fin_$s.json
  .venv/bin/python tools/trace_colours.py hawk/tools/side_white_$s.json ref/hawk_white/side_hb_$s.json --res 0.12
done
cd hawk/cad
../../.venv/bin/python hawk.py ../../out/hawk/geo        # geometry only, about 10 s
../../.venv/bin/python colour.py ../../out/hawk/col      # colour, inlays, 3MF, about 2 min
ONLY=wing_stbd ../../.venv/bin/python colour.py ../../out/hawk/col   # one part
cd ../..
.venv/bin/python tools/render.py out/hawk/col/hawk_colour_preview.glb hawk/docs/colour_render.png --skip gear_,wheel_,pin_,stand --zoom 1.5
```

Checks: run `tools/interference.py` on the assembled STLs without the `key_*` files (keys are modelled at the origin), and `tools/overhang.py` on `out/hawk/geo/print`.

## Files

- `cad/hawk.py`: station tables, parts, joints, print poses. CadQuery only makes the lofts and primitives; every boolean runs in manifold3d.
- `cad/colour.py`: the Red Arrows scheme, the inlays, and the plates and 3MF.
- `cad/detail.py`: panel lines, hinge lines, access panels and rivets.
- `tools/refs.json`: calibration of the Revell views. `tools/fin_flag_*.json` and `tools/side_white_*.json` hold the HobbyBoss trace specs. `tools/measure.py` is the diagnostic profile dump.
- `stl/`, `kit/`, `docs/`: outputs, as for the Halifax.

## Reference images (not in git)

| File in `ref/` | Source | Used for |
|---|---|---|
| `CM_04284.pdf` | Revell 04284 BAe Hawk T.1A Red Arrows instructions | Shape (pages 15–16), white areas |
| `revell_04284_p15.png`, `revell_04284_p16.png` | Those pages rendered at 400 dpi | Calibrated views |
| `hawk/hobbyboss_81738_sheet2.webp` | HobbyBoss 81738 marking sheet II (current scheme) | Union-flag fin and tail swoosh, both sides |
| `hawk/hobbyboss_81738_sheets1_2.webp` | HobbyBoss 81738 sheets I and II, small | The older blue-fin scheme, for a future variant |
| `hawk/photo_red_arrows_port_xx253.png` | Red Arrows Hawk in flight, port side | Detail checks |

## Known gaps and next steps

- Add the older blue-fin scheme (HobbyBoss sheet I, Revell 2010) as an option.
- Add the ventral strakes, the airbrake outline, the canopy detonating-cord (MDC) lines and the intake auxiliary doors.
- Add gear doors for the gear-down display.
- Print a fit coupon for the letter inlays: their strokes are about 1 mm, which is at the printable limit.
