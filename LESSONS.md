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
| Printed key press fit (`KEY_FIT`) | 0.10 mm per side | Confirm with fit test |
| Printed 1.8 mm pin: grips | 1.80 mm hole | Confirm with fit test |
| Printed 1.8 mm pin: spins | 2.05 mm hole | |
| Roundel inlay radial fit | 0.10 mm | |
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

