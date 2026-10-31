# Lessons for the next kit

What the Halifax taught us, so the next aircraft starts from a working pipeline.

## Workflow that worked

1. **References first.** Get a good kit-instruction plan (Revell or Airfix PDFs are usually the most accurate) plus one or two independent 3-views, and a colour profile for the markings. Render the PDF page at 400 dpi.
2. **Calibrate each view** in `tools/refs.json`: find the mm-per-pixel scale and origin from known features (nose tip, wing leading edge, fuselage datum). Check the drawing isn't slightly rotated: the Revell side view was tilted by 0.77°.
3. **Shape as tables of stations.** Fuselage: (x, half-width, top z, bottom z, superellipse exponent). Wings: planform (span, LE x, chord) and t/c. Edit the numbers, rebuild, and overlay with `tools/ref_overlay.py` until the outline sits on the drawing lines.
4. **Cross-check with a second drawing.** The 51 Sqn profile artwork was off by several mm at the nose and missed the turret; the Revell plans and the Wikipedia 3-view agreed to about 2 mm.
5. **Split for printing.** Each piece lies flat with no supports. Joints use printed keys and pins, never glue or filament.
6. **Colour last.** `kitlib.paint` peels regions (camo, codes, stripes) into per-filament volumes. Roundels are separate press-fit inlays (`kitlib.make_inlay`).
7. **Check:**
   - `tools/interference.py`: parts must not overlap.
   - `tools/overhang.py`: printable poses.
   - `tools/colour_check.py`: no stray colour on surfaces that should be plain.
   - `tools/closeup.py`: render the details that matter.
8. **Write the 3MF.** `kitlib.write_3mf` groups parts onto plates by colour set, with at most 5 colours a plate (one AMS plus the auxiliary head).

## Printer numbers (Bambu X2D, PLA)

| Setting | Value | Status |
|---|---|---|
| Usable plate | 230 × 250 mm (dual-nozzle X limit) | |
| Sliding fit (`FIT`) | 0.15 mm per side | Confirmed by fit test |
| Printed key press fit (`KEY_FIT`) | 0.15 mm per side | Confirmed by fit test |
| Printed 1.8 mm pin: grips | 2.35 mm hole | Confirmed by fit test (small holes print about 0.5 mm tight) |
| Printed 1.8 mm pin: spins | 2.65 mm hole | Confirmed by fit test |
| Roundel inlay radial fit | 0.15 mm | Matches the key press fit |
| Prop shaft 2.4 mm in bore | 3.1 mm bore, hex socket 3.4 mm across flats for a 3.0 mm hex | Scaled from the pin test; check on the first print |
| Inlay depth | 1.2 mm | |
| Colour skin depth | 0.8 mm | |
| Panel lines | 0.5 mm wide × 0.25 mm deep | |
| Hinge lines | 0.4 mm deep | |
| Rivets | 0.7 mm dots, raised 0.2 mm, 10 mm pitch, structural rows only | Matches PB94 |

Print `cad/fit_test.py` first on any new printer or filament.

## Pitfalls and fixes

**Booleans and colour:**
- **Slow colour booleans.** Painting by growing unions took about 110 s per part. Peeling (`remaining ^ region`, then `remaining - region`) takes about 1 s.
- **Overlapping colour regions blow up memory.** Roof camo plus side camo plus a wavy demarcation band produced millions of slivers on the fuselage. Restrict each region to its own zone (`roof_section` inset) and simplify sections (`.simplify(0.1)`).
- **Re-merging colour pieces into one STL segfaulted.** Export the single-colour STL from the uncut solid instead.
- **CadQuery union of all parts fails.** Keep parts separate. Use manifold3d for heavy booleans.

**Geometry:**
- **Inverted lofts.** Reverse the wire order when the volume comes out negative.
- **The B-rep bounding box is loose.** Use mesh bounds for placement.
- **A flat-bottomed wing tilts the chord nose-up.** Flattening the underside for supportless printing changes the incidence. Re-pitch the wing so the root chord matches the real incidence (`wing_pitch()`).
- **Shapes look "big and curvy" when lofted with smooth splines.** Real fairings, such as the gear housings, are often slab-sided boxes. Use ruled lofts and boxier superellipse exponents (n ≈ 4).

**Printing and fit:**
- **Pins lying across a split stop the part lying flat.** Use printed keys in slots on both halves instead.
- **Spinning props (after PB94).** A printed shaft has a captive flange trapped between the nacelle halves, a thrust collar outside and a hex boss. The prop presses onto the hex.
- **Camo flecks on the underside.** Camo prisms extruded through everything reach the lower skin. Intersect them with an "up-facing skin" only, and check from below with `colour_check.py`.

**3MF:**
- **XML breaks** on "&" in plate names. Always use `quoteattr` and `escape`.

**Process:**
- **Don't trust one source.** Every shape complaint so far was a reference problem, not a CAD problem.
- **Build time.** The full kit, 88 parts in colour, takes about 40 min. To iterate on one part, build only it: `python cad/halifax.py out PART` for geometry, or set `ONLY=name` for colour.

## Reference images

These are not in git (copyright). Keep them in `ref/` locally or in a private repo. Without them the overlays can't be redrawn, but the calibrated numbers in `tools/refs.json` and the station tables in `cad/halifax.py` hold everything measured from them.

## Colour skins must overshoot the surface

When a colour region's outer face is exactly coplanar with the part's surface, manifold booleans can leave zero-thickness sheets of the base colour lying on the outside. They show up as black streaks in renders and in Bambu Studio. Build skins as `P.translate(+0.05) - P.translate(-SKIN)` (see `SKIN_OUT` in `cad/colour.py`). On the stand plinth this cut stray black on the top from 6450 to 159 mm².

The same applies to anything cut by subtracting a solid that shares the part's surface:
- **Roundel rings.** Cut each ring as `plug ^ (cylinder - previous cylinder)`, not `plug - inner rings`.
- **Glazing frames.** Use `frame slabs - inner_core(P)`, not `outer_skin(P) ^ frames`.
- **Raised lettering.** Paint it with a region above the deck, not `P ^ region`.

Rule of thumb: every paint region should be a prism or slab that pokes out through the surface, so the boolean never compares two copies of the same face.

## Markings and glazing

- **Underwing roundels.** Bomber Command night bombers had none, so the Halifax wing inlays are top-only, 1.2 mm deep. For an aircraft with roundels top and bottom, PB94 uses a double-sided press-in disc. Do that with a through-socket and an inlay coloured on both faces.
- **Canopy part = glazed area only.** Frames and fuselage paint outside the glass belong to the fuselage, so the canopy plate (black and clear) doesn't need camo.
- **Side-view lines also show up in plan view.** On a rounded section, a cant rail at z and a roof bar at |y| can be the same line. Check both views before adding frames, or you get doubled lines.
- **`pkill -f` can kill your own shell** when the pattern appears in the command line. Use `TaskStop`, or a pattern that can't match itself.

## Small holes

On the X2D, a printed 1.8 mm pin needs a 2.35 mm hole to grip and 2.65 mm to spin. My first guesses (1.80 and 2.05) didn't fit at all. Size every small hole from the fit test, and leave at least 1 mm of wall round it; the gear legs had to grow to manage that.


## Slots through tapering parts

The tailplane slot was a plain box. Where the rear fuselage tapers, it broke through the top, and a panel line then cut off a loose strip of roof. Cut slots with the mating part's own shape grown by `FIT` (as the fins do); it also locates the part. After every geometry change, check each part is still a single piece (`trimesh` `split()`). Every joint needs a positive locator, either keys or a shaped socket, not just a butt joint.

## Final checks before handing over a kit

Run all three on the full build. Every one caught something on the Halifax that the renders hid:
1. Every STL is a single piece (`trimesh` `split()`). This caught the nacelle islands left in the wing-tongue pocket, an astrodome plug that only touched its dome, and loose rivet dots.
2. Assembled interference over all parts (`tools/interference.py`). It must be clean apart from intended press fits.
3. Overhangs in print pose (`tools/overhang.py`). This caught the canopy floating on its tab.

`colour.py` now keeps only the largest solid of each part and reports anything above 1 mm3 it drops. Read those reports: a dropped piece can mean a real geometry bug.


## Ideas borrowed from the grafitomi Lancaster (used on the Halifax from v2)

- **Fuselage as full-width sections printed on end.** No seam along the spine, and layer lines run around the body where they barely show. Use a brim on tall parts.
- **Camo spine as single-colour clip-on pieces** on the demarcation line, keyed to a black body. The fuselage plates then need no colour changes and the colour edges are crisp. Cut the pieces at the profile's colour changes, kept clear of glazing, turrets and the tailplane.
  - Give every piece a flat face to print on.
  - Make every piece at least about 5 mm thick, so a straight split line may be needed on a low nose.
  - Put each key where its piece is thickest.
- **Code letters as press-in inlays** (`kitlib.make_section_inlay`), like the roundels. Engrave text that's too small to inlay.
- **Wing joint with a separate key and flat faces** at the dihedral bisector, so the panels can also print standing on end. Ship both wing poses and let the builder choose: on end hides layer lines but costs more colour changes.
- **Do awkward booleans with mesh tools.** The scalloped body/spine split failed in OCC (the CAD kernel); doing that one cut in manifold3d fixed it. Parts in `build()` can be trimesh meshes.
- **A fine-layer plate for small detail parts** (exhausts, wheels, props, gear). Not done on the Halifax yet.

