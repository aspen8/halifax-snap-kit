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


## What the Hawk added (1:40 jet, v2 style, built from a scanned kit sheet)

The Hawk was the second kit, and the first built from scratch on the v2 approach. `hawk/` is the cleaner template for the next aircraft: copy it rather than the Halifax.

### Setup
- **Python 3.10–3.12 only.** CadQuery has no 3.13 wheels. `uv venv --python 3.12 .venv` fetches a suitable Python. Then `pip install -r requirements.txt`, which includes `rtree` (trimesh ray casting needs it) and `pymupdf` (to render the reference PDFs).
- **Disk.** CadQuery, OCP and VTK take about 1.5 GB installed. Check free space first: a half-finished install on a full disk wastes time.
- **macOS has no EGL.** `cad/render_colour.py` (pyrender) won't run there. `tools/render.py` is a numpy point-splat renderer: about 5 s for 400k triangles, and `--skip gear_,stand` gives flight views.

### References
- **Copy every reference into `ref/` the moment it arrives.** Images pasted into a chat sit in a temporary folder and were lost mid-build. Ask for files on disk.
- **Scanned instruction sheets are fine.** `tools/silhouette.py` makes the outline mask (blur, threshold, largest component, fill holes). Leader lines and part numbers pollute side views, so read those outlines by hand from `tools/grid.py` zooms instead.
- **Each view on a sheet has its own scale.** The Revell Hawk side view is drawn 12% larger than the plan view. Calibrate the plan by the span and the side by the length.
- **Check the drawing's symmetry.** The Hawk plan view's wings sit 20 px off the fuselage centreline, and its two half-spans differ by 5%, in both the top and underside views. Average the halves, each normalised by its own half-span.
- **Cross-check against real data.** Wing area, root chord, and overall length including the probe all came within 1%, which confirmed the calibration.
- **Paint can be traced too.** `tools/white_regions.py` keeps what is inside the silhouette and still paper-white after a small blur. The underside chevrons and belly stripes came out clean. Side views need the canopy glass, labels and roundel rings filtered out, and long stripes are better redrawn as a smooth parametric band along the traced path.
- **Regenerate lettering as text,** with `text_section`, mirrored on starboard. A traced word would read backwards on the other side.

### Geometry pipeline
- **Booleans in manifold3d only.** CadQuery makes the lofts and primitives, and `to_m()` tessellates them. The Hawk build went from more than 10 minutes, unfinished, in OCC to 8 s.
- **`mf.CrossSection([pts])` uses the Positive fill rule.** A clockwise outline silently gives an empty solid, and `A + empty` came out empty too: the fin vanished. Always build sections with `kitlib.cs` (even-odd).
- **Smooth OCC lofts through sparse, unevenly spaced stations can twist and overshoot.** The intake fairing reached the far side of the aircraft. Resample the stations every 3 mm with PCHIP (`dense()`), use ruled lofts, and print each loft's bounding box.
- **Overlap joined primitives by about 1 mm.** Faces that only touch become separate pieces: the probe cone and its boss did.
- **A fairing sitting on a wing must not reach below the wing's underside.** Otherwise the wing cut leaves slivers hanging under it.
- **Print poses must rotate, never mirror.** Mirroring a port part makes it a starboard part.
- **Keep a cached function per sub-solid** (`@cached`). Parts reuse the body, the wing and the canopy zone many times.

### Joints
- **Low wings show under a rounded belly.** Root tongues reaching past the centreline ran into the other wing's root. Stop them about 5 mm past the centreline, and alternate them fore and aft.
- **Stand key.** Build it straight in the model frame and join it to the blade after rotating the stand to its pitch. A key tilted with the pitch rubs its straight sockets. Keep it clear of the tongue pockets.
- **Locators on the print face break the pose.** Pegs under the canopy made it stand on their tips. Locate it from a mating part instead: the cockpit insert's headboxes and coamings nest into pockets in the solid canopy.
- **A fin printed as two flat halves** carries the spine cap (everything above a flat root plane) and the dorsal fillet. The fuselage keeps a flat seat and a tongue slot.
- **A body of revolution such as a pod or tank** prints as two halves split on the centreline, with keys. Use separate keys into the belly, never pegs on a curved face.

### Colour, v2 style
- **Long thin stripes become chunked inlays.** Cut them at section joints, at steps in the surface (the intake lip), and every 38 mm. `kitlib.clip` pads its box by 1 mm, which is right for cropping prisms but wrong for chunking, because the chunks overlap. Use an exact rectangle.
- **Widen stripes to at least 1.8 mm.** Make letters 0.15 mm bolder, with a 0.12 mm fit, so the plug strokes stay about 1 mm.
- **Through-disc roundels.** On a wing printed flat, one disc coloured right through shows on both surfaces.
- **Colour that's on the print-bed face is nearly free.** Only the first layers change colour. The Hawk's underside chevrons and the Union flag on the fin halves (a thin part) are painted into the skin this way.
- **Find a plinth's deck height from the geometry, not the bounding box.** The raised boss at the blade foot was taller than the deck, and the lettering and pinstripe came out empty.

### Tracing colour artwork
- **Fit the drawing locally to the part being traced.** The HobbyBoss side views were fitted through the fin's corners (`tools/trace_colours.py`, a least-squares affine over several point pairs), so the flag lands exactly on our fin. Fitting by overlap of the outline failed: the white parts of the flag are the same colour as the paper.
- **Different sheets disagree by a few mm.** That fit drifted 2–4 mm lower down the fuselage, and the two side views disagreed with each other. Don't mix positions from two sheets. Keep one source per region, and warp the joining piece to meet both ends: the swoosh is pinned to the Revell roundel at its foot and to the HobbyBoss fin at the root.
- **Trace the port and starboard views separately.** Then check that they agree in (x, z): on the Hawk they do, because the flag is reversed on the starboard side, hoist forward.
- **Sheets show different years.** The Revell 2010 sheet has the blue fin, the HobbyBoss sheet II the Union flag. Check which scheme the user wants before tracing.

### Thin parts
- **Keys across a thin split break through the skin.** The first fin-half keys were 6 mm across in a 2 mm half. Check every slot against a 0.3 mm outer layer: `(slot ^ (P - P.translate(-0.3 * n))).volume()` must be 0. Use full keys only where the part is thick (the spine cap), short keys about 2.2 mm across at 30% chord elsewhere, and thicken the section slightly if needed (fin thickness from 8.5% to 10% of chord).
- **STL interference has rounding noise.** Coplanar seats (the fin on the spine) showed up as 18 mm³ "overlaps" in the float32 STLs but 0 on the exact manifolds. Confirm anything small on the manifolds before changing geometry.

### Shape details that looked wrong in renders (user review)
- **Don't model a spine as a narrow loft on a flat-topped body.** It reads as a ridge on a shelf. Behind the cockpit, use one body section that takes the whole top line: an "egg" superellipse that is widest at z_w, with a rounder upper half (`egg_wire`, n_up ≈ 2.0–2.3).
- **A fin fillet is part of the fin.** A flat plate glued ahead of the fin looked kinked. Instead, sweep the fin's leading edge forward below a height (offset ∝ (z0 − z)^1.3), cap the thickness at the fin's own, and loft densely (ruled). It then rises out of the spine smoothly.
- **Canopy:**
  - Limit the glazing to the canopy bubble's plan footprint (`spine().project()`). Otherwise, where the sill plane dips under the deck, a full-width slice of fuselage becomes "glass".
  - End the canopy with a slanted rear cut where the real frame is, not where the drawing's top line fades into the spine.
  - Put the seats where the pilots sit (about 40% and 75% along a tandem canopy), and check headroom: `(cockpit.translate(z + wall) ^ canopy_zone) - outer` must be empty. A headbox poking through the solid canopy showed up as a black block.
- **Lettering belongs on the panel it is painted on.** Check the side pod's top edge against the letter height along their whole length. Raise or extend the pod (within the plan-view widths) rather than shrinking the text.
- **Ask for photos.** Red Arrows photos are easy to get, and the user offered more. Side-on, top-down and 3/4 views of the canopy and the fin root settle shapes that kit sheets draw loosely.

### Using photos (second review)
- **Render the model from the photo's viewpoint and put the two side by side.** `tools/render.py` has `stbd`, `port` and `head` views, and `--focus` and `--zoom` for framing. That's how the photos showed the continuous cheat line, the gear positions and the round intakes.
- **A curve the eye follows (canopy, spine) must be one smooth curve.** Measured points wobble by a few tenths. Fit a smoothing spline (`UnivariateSpline`, small `s`), resample every 2 mm, and loft ruled. Then check that the second difference doesn't change sign.
- **Settle a disagreement by counting sources.** On fuselage depth, Revell and the side-on photo agreed and HobbyBoss didn't. A low camera and a long lens make an aircraft look deeper, so measure photos on a grid against the nose tip and the length.
- **Gear sockets need wall too.** Moving the main leg aft put its socket at 80% chord, where the wing is 2.4 mm thick. Measure the local thickness, put the socket where it leaves at least 0.6 mm above, and rake the leg to put the wheel where the photo shows it.
- **Any helper that casts rays must handle a miss.** `kitlib.make_section_inlay` crashed on a stripe chunk whose sample rays missed the surface. The Hawk's `y_inlay` samples inside the shape and returns nothing when nothing is hit.

### Checks that caught real bugs on the Hawk
- **Interference:** run it without the `key_*` STLs, which are modelled at the origin. It found the tongue clash, the tilted stand key and a fin-cap sliver.
- **Overhang:** found the canopy standing on its pegs.
- **Largest-piece report:** found the floating probe and the intake slivers.
- **Count the inlays per side:** an asymmetric count gave away the padded `clip`.
- **Rebuild into a fresh output folder,** or old part files linger next to the new ones.

### Starting the next aircraft: checklist
1. Brief: type and mark, span or scale, markings, display (gear, stand or both), colours per plate.
2. Free disk space, set up the venv, then copy `hawk/` to `<aircraft>/`.
3. References into `ref/`. Render the PDF pages at 400 dpi, then get outlines (`silhouette.py`, `grid.py`) and calibrate each view in `<aircraft>/tools/refs.json`.
4. Station tables, then `tools/ref_overlay.py --refs <aircraft>/tools/refs.json`, iterating until the outline sits on the lines. Check against real dimensions.
5. Split for printing (sections on end, flat panels, halves for round parts), with keys and shaped sockets.
6. Colour: inlays for anything that would cost colour changes on many layers, skin paint for bed-face colour.
7. Checks (single pieces, interference without keys, overhangs, inlay counts), renders, 3MF.
8. Fold what you learned back into this file and the README.
