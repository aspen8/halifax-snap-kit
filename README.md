# Halifax snap kit

Handley Page Halifax B Mk II Series IA (Merlin XX), 1:60 scale, 500 mm span.
A multi-part snap kit for the Bambu Lab X2D (256 x 256 mm bed). Each part prints flat with no supports.

Status: airframe, kit split, landing gear and display stand done. Panel lines and colour parts (camo, roundels, codes) are still to come.

## Files

- `cad/halifax.py`: the parametric CadQuery model. Every dimension is in the PARAMETERS block.
- `cad/fit_test.py`: tolerance test coupon.
- `stl/`: print-ready STLs, already placed in print orientation.
- `halifax.3mf`: the original AI-generated reference mesh (proportions only).

Rebuild:

```
pip install cadquery trimesh   # Python 3.10-3.12
python cad/halifax.py out
```

## Print first: fit test

Print `fit_test_plate` + `fit_test_tongue`.
- Find the hole that grips 1.75 mm filament firmly and set `DOWEL_HOLE` to it.
- Find the pocket the tongue pushes into snugly and set `FIT` to it.

The defaults are 1.85 mm and 0.15 mm.

## Parts (36)

| Group | Parts | Notes |
|---|---|---|
| Fuselage | front/rear x port/stbd | Solid halves, printed split face down. 15% infill keeps them light. |
| Nose | `nose_glazing` | Clear / translucent filament. Spigot down. |
| Canopy | `canopy` | Clear. Drops into the roof pocket. |
| Turrets | `turret_dorsal`, `turret_tail`, `guns_*` | The dorsal turret rotates on a filament pin. |
| Wings | inner + outer panel per side | Flat underside. Tongue joints set the 5 deg dihedral. |
| Nacelles | 2 halves per engine (8) | Clamp around the wing. |
| Props | 4 x 3-blade | Spin on 1.75 mm filament axles. |
| Tail | `tailplane`, `fin_port`, `fin_stbd` | Tailplane passes through the fuselage; fins slot onto its tips. |
| Gear | `main_gear_*`, `main_wheel_*`, `tail_gear`, `tail_wheel` | Plug into the nacelle and fuselage sockets. Wheels turn on filament axles. Sits tail-down at 8.8 deg. |
| Stand | `stand_post`, `stand_base` | In-flight display at 5 deg nose-up. The socket is under the model's CG. Leave the gear off. |

## Geometry notes

- Wing incidence is 2 deg at the root, from rigging figures. The underside is flat from 15% chord for printing, and the wing is pitched to compensate.
- Sections are NACA 230xx, after the real NACA 23021 root / 23007 tip.
- Main track is 118 mm (7.1 m), with the wheels under the inner nacelles. Jane's gives 25 ft 6 in (7.8 m) for the Mk III.
- Not verified: the fin height (from the reference mesh) gives about 4.2 m to the fin top tail-down, against the published 6.32 m overall height. It should be checked against a 3-view drawing.

## Assembly

1. Cut 1.75 mm filament into 7.5 mm dowels (about 26 needed).
2. Press the dowels into the port fuselage halves and the inboard nacelle halves.
3. Slide both inner wing panels' root tongues into the fuselage. Port goes forward, starboard aft. Add the canopy, the tailplane and the nose spigot, then close the fuselage halves.
4. Join the front and rear fuselage sections on their dowels.
5. Plug the outer wing panels onto the inner panels. The tongue sets the dihedral.
6. Clamp the nacelle halves around the wings.
7. Fit the props on 12 mm filament axles.
   For gear: put the wheels on 16 mm (main) and 9 mm (tail) filament axles, then plug the gear into its sockets. For the stand: push the post into the base, then the key into the socket under the fuselage.
8. Fit the fins onto the tailplane tips, then the turrets and gun packs.

The joints are designed as press fits. Use a drop of CA glue on any joint that comes out loose.
