# Modeling playbook — form before finish

Bad AI modeling has one root cause: it **stacks primitives at guessed sizes** and hopes materials fix it. They don't. A gray clay render of a good model already reads as the real thing; a bad model reads as a toy no matter how it's lit.

Work in this order. Don't skip ahead to materials.

## 1. Reference sheet (write it down before any code)

Put a dimension table in the build script's docstring, in meters, with a named origin and axis:

```
Reference sheet (bore axis = X, butt at x = 0, z = 0 at bore center)
    stock     x 0.00–0.735   depth 0.170 at butt   thickness 0.042
    barrel    x 0.545–1.100  Ø 0.029 → 0.017
```

- Use real numbers from the real object class (look them up or reason from human scale: hand width ≈ 0.09 m, grip circumference ≈ 0.13 m, step 0.18 m, seat 0.45 m, door 2.03 m).
- Every part's position is written relative to the sheet, not "about here".
- Verify with `shapes.check_dims(root, (x, y, z))` after building.

## 2. Silhouette first

Most objects are recognized by **one** view. Find it (a rifle by its side profile, a chair by its 3/4, a bottle by its side) and get that outline right first.

- Draw that outline as 2D points with per-corner radii → `shapes.profile_extrude`.
- Render `preview.py --views silhouette`. If it doesn't read as the object in flat black, stop and fix the outline. No material fixes a silhouette.
- Silhouette needs **rhythm**: big / medium / small shapes, tapers, and negative space (the hole in a handle, the gap under a fore-end). Uniform thickness and evenly spaced parts read as fake.

## 3. Pick the construction that matches manufacturing

| Real-world process | Builder | Typical parts |
|---|---|---|
| Sawn / cut from a sheet or blank | `profile_extrude` (+ `crown`) | gun stocks, knife blades, chair sides, brackets, signs, phone bodies |
| Turned on a lathe / spun / molded round | `lathe` | barrels, bottles, cups, knobs, lenses, table legs, cartridges, lamp bases |
| Bent rod, tube, wire, forged loop | `sweep` (with taper `radii`) | handles, trigger guards, frames, cables, pipes, hooks |
| Machined block | `rounded_box` | receivers, housings, buttons, bases, mounts |
| Drilled / milled feature | `cut` (boolean, beveled afterwards) | ports, slots, holes, grooves, vents |
| Fasteners | `screw` | anywhere parts are held together — they prove the scale |

Rules:
- **Profiles carry the detail.** A lathe profile with a chamfer, a lip, a groove and a recess beats a cylinder plus four extra objects.
- **`crown` on every extruded part that a hand touches** (stocks, handles, grips, bodies). Flat sides = plywood cutout. 8–15 % of thickness.
- **Edge radius scales with the part**: large rounds on hand-contact wood/plastic, tight radii on machined steel. Never zero.
- **Parts meet, they don't float.** Sink joins into each other (receiver into stock, handle ends into the wall). Use a contrasting cap, spacer or seam where real objects have one — joins are where craft shows.

## 4. Primary → secondary → tertiary

1. **Primary**: the 2–4 big masses that make the silhouette. Get proportions right here; check in silhouette.
2. **Secondary**: the parts that explain function — trigger guard, turrets, handle, hinges, lids.
3. **Tertiary**: screws, seams, spacers, vents, text plates, knurling. Small, sparse, concentrated at the focal area. Tertiary detail is what tells the eye "this is 30 cm, not 3 m".

Detail density follows attention: dense where the camera and story look, sparse elsewhere.

## 5. Check like an artist

- `preview.py --views silhouette,clay,beauty` and **open each image**.
- Clay: do surfaces have curvature and soft highlight roll-off, or flat planes and razor lines?
- Silhouette: is it recognizable at thumbnail size (`*_thumb.png`)?
- Reads the right way up? An object lying on its side can read upside-down from the camera side; move the camera, not the object.

## Common AI modeling failures → fix

| Failure | Fix |
|---|---|
| Cylinder + cube + sphere "assembled" object | Rebuild each part with the builder that matches its manufacture |
| Plank-like flat parts | `crown` + bigger `edge_round` |
| Mesh stretched by object scale | Build at real size; `hz.apply_scale` |
| Parts hovering 1 mm apart or randomly intersecting | Planned joins from the reference sheet; sink 1–3 mm |
| Rotations hinge around the world origin | Builders set origin at the attachment point (`sweep` uses its first point) |
| Faceted curves | More `segments` on lathe (64–96 for hero round parts) |
| Every part the same size | Size rhythm: big / medium / small; tapers |
| Gray "black" parts | Not the model: scene too bright (AgX compresses), or `add_wear` size too large on thin parts |
