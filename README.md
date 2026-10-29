# Halifax snap kit

Handley Page Halifax B Mk II Series IA (Merlin XX), 1:60 scale, 500 mm span.
A multi-part snap kit for the Bambu Lab X2D (256 x 256 mm bed). Each part prints flat with no supports.

Status: airframe and kit split done. Landing gear, panel lines and colour parts (camo, roundels, codes) are still to come.

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

## Parts (29)

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

## Assembly

1. Cut 1.75 mm filament into 7.5 mm dowels (about 26 needed).
2. Press the dowels into the port fuselage halves and the inboard nacelle halves.
3. Slide both inner wing panels' root tongues into the fuselage. Port goes forward, starboard aft. Add the canopy, the tailplane and the nose spigot, then close the fuselage halves.
4. Join the front and rear fuselage sections on their dowels.
5. Plug the outer wing panels onto the inner panels. The tongue sets the dihedral.
6. Clamp the nacelle halves around the wings.
7. Fit the props on 12 mm filament axles.
8. Fit the fins onto the tailplane tips, then the turrets and gun packs.

The joints are designed as press fits. Use a drop of CA glue on any joint that comes out loose.
