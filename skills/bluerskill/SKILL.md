---
name: bluerskill
description: Anti-slop 3D for Blender. Use whenever building, editing, lighting, texturing, or rendering a Blender scene (bpy scripts, blender-mcp, .blend files, product shots, props, environments, stylized scenes) so the result looks authored by a 3D artist instead of AI/procedural-default. Triggers on Blender, bpy, 3D modeling, 3D render, lookdev, "make it look less CG / less fake / less AI". Covers modeling (silhouette, reference dimensions, lathe/extrude/sweep construction) as well as materials, lighting and camera. Not for game-engine shader code, CAD tolerancing, or 2D image generation.
metadata:
  short-description: Make Blender output look hand-made, not AI-generated.
---

# bluerskill — anti-slop 3D for Blender

`taste` stops web pages from looking AI-generated. **bluerskill does the same for 3D.**

A Blender scene reads as "AI made this" for the same reason a landing page does: every decision was left at its default, everything is perfect, and nothing has a history. Primitive soup, razor edges, 0.8-gray plastic, one white point light, the camera that shipped with the startup file. This skill replaces defaults with **decisions**, and perfection with **plausible imperfection**.

**Form comes first.** Most AI 3D fails before materials or light: it stacks cubes and cylinders at guessed sizes. A good model reads as the real thing in a flat gray clay render. Follow §4 (Modeling) and `reference/modeling.md` before touching materials.

Files in this skill (paths relative to this SKILL.md):

| File | Use |
|---|---|
| `reference/modeling.md` | **Read first for any modeling.** Reference sheet → silhouette → construction choice → primary/secondary/tertiary detail. |
| `reference/ai-tells.md` | Full catalog of 3D AI tells, with the fix for each. Read before starting any non-trivial scene. |
| `reference/materials.md` | Physically plausible albedo/roughness table and breakup recipes. |
| `reference/light-camera.md` | Lighting rigs, color temperature, lens and composition rules. |
| `scripts/shapes.py` | Modeling builders: `profile_extrude` (with `crown`), `lathe`, `sweep`, `rounded_box`, `cut`/`union`, `screw`, `group`, `check_dims`. |
| `scripts/humanize.py` | Finishing library: bevel, ground, jitter, physical materials, breakup, wear, wood grain, light rigs, camera, color management. |
| `scripts/audit.py` | Scores a scene 0–100 for AI tells and prints fixes. Run it, don't eyeball it. |
| `scripts/preview.py` | Renders silhouette / clay / beauty / wire check images so you can *look* at the result. |
| `examples/mug_still_life.py` | Simple scene: same brief built the AI-default way (`--slop`, audit 0) and the bluerskill way (audit 100). |
| `examples/rifle_prop.py` | **Hard-surface hero prop** (~35 parts) built from a reference sheet with every builder. Copy its structure for any prop. |

---

## 0. How you drive Blender

Prefer, in order:

1. **blender-mcp** (if an MCP server exposing `execute_blender_code` or similar is connected): run code live in the user's open session. `exec(open("<skill>/scripts/humanize.py").read())` or add `scripts/` to `sys.path` and `import humanize`.
2. **Headless CLI** (always available if `blender` is on PATH):
   ```bash
   blender -b scene.blend --python build.py            # build / modify
   blender -b scene.blend --python <skill>/scripts/audit.py            # score
   blender -b scene.blend --python <skill>/scripts/preview.py -- --out ./renders   # look
   ```
   In `build.py`, put `sys.path.insert(0, "<skill>/scripts")` then `import shapes as sh, humanize as hz`. Save with `bpy.ops.wm.save_as_mainfile(filepath=...)`.

Target Blender **4.2+ / 5.x** API (Principled v2 socket names like `Specular IOR Level`, `Coat Weight`, `Emission Color`; no `use_auto_smooth`; `Material.use_nodes` is deprecated and always on). Check `bpy.app.version` before using anything version-specific.

## 1. Output header

Post this before writing any bpy code:

```text
READ:     <subject> for <purpose>, <style family>, <mood>
REFS:     <2-3 concrete real-world references: object, era, place, material>
DIALS:    WEAR <0-10> / STYLIZATION <0-10> / CLUTTER <0-10>
SCALE:    metric, hero object ≈ <real size>
ENGINE:   CYCLES | EEVEE, AgX <look>
```

`REFS` is mandatory. "A coffee mug" is a prompt; "a 1990s diner mug, thick ironstone, chipped glaze at the rim, coffee ring inside" is a reference. Every downstream decision comes from the reference, not from Blender defaults.

### Dials

- **WEAR** — 0 new-in-box, 3 lightly used (default), 6 daily-use years, 9 derelict. Drives bevel softness, edge wear, grime, roughness breakup, jitter.
- **STYLIZATION** — 0 photoreal, 4 "Pixar-real" (default for stylized asks), 8 toon/flat. Stylized ≠ lazy: stylized work still has deliberate shape language, edge softness, and value design.
- **CLUTTER** — 0 isolated product, 3 hero + 2–4 supporting props (default), 7 lived-in environment.

Baselines: product shot `2/1/1` · stylized prop `3/5/2` · interior archviz `3/0/5` · game-ready prop `4/3/0` · narrative environment `6/2/7`.

## 2. Hard rules (never ship these)

1. **No razor edges.** Every hard-surface mesh gets a bevel (modifier or modeled). Width ≈ 0.5–2 % of the object's smallest dimension at WEAR 0–3, larger with wear/stylization. `hz.bevel(obj)`.
2. **Real-world scale, applied.** 1 BU = 1 m. Mug ≈ 0.095 m tall, door 2.03 m, table 0.74 m. Scale applied (`hz.apply_scale`). Wrong scale breaks DOF, SSS, bevels, lighting falloff.
3. **Nothing floats, nothing clips.** Objects rest on something (`hz.ground`). Contact is where realism lives.
4. **No default material.** No 0.8 gray / 0.5 roughness. Every material has a real-world reference, albedo inside 0.03–0.85 (non-metals), metallic exactly 0 or 1.
5. **No constant roughness on a hero surface.** Roughness gets breakup (`hz.add_breakup`). Real surfaces are never uniform.
6. **No startup camera, no startup light.** Delete or move them. Never ship 50 mm from (7.36, -6.93, 4.96).
7. **AgX (or Filmic), never Standard.** Standard clips highlights into flat CG white.
8. **No clone armies.** Repeated objects get per-instance variation in rotation, scale, and ideally material (`hz.jitter`).
9. **Verify by looking.** Run `audit.py` (target ≥ 85) and `preview.py`, then open the PNGs with the Read tool before claiming done. Don't report a score you didn't run.
10. **No primitive assembly.** Don't build an object by placing unmodified cubes/cylinders/spheres. Every part is made with the `shapes.py` builder that matches how the real part is manufactured (§4).

## 3. Default bans (override only when the user asks)

These are the 3D equivalent of purple gradients and glassmorphism — instant "AI made this" signals:

- Neon purple/teal or pink/cyan lighting on a dark void.
- Glossy chrome or iridescent blobs/torus/spheres floating on a gradient backdrop.
- Pastel clay "isometric tiny room" with every object the same softness and saturation.
- Hero object dead-center on an infinite seamless backdrop with a single soft shadow.
- Everything brand new, symmetrical, axis-aligned, and placed on round-number coordinates.
- Emission used as lighting instead of lights; bloom as a style instead of a consequence.
- Huge f/1.2 bokeh on a scene that isn't macro, or zero DOF on a close-up.
- UV sphere / 32-vertex cylinder with visible faceting on a silhouette.

## 4. Modeling (the part AI is worst at)

1. **Reference sheet** in the script docstring: real dimensions in meters, origin and axis named. Look up or reason from human scale. Verify with `sh.check_dims`.
2. **Silhouette**: find the one view that identifies the object; draw that outline as 2D points with per-corner radii. Render `--views silhouette` — if it doesn't read in flat black, fix the outline before anything else.
3. **Construction = manufacturing**: sawn → `profile_extrude` (+ `crown` on anything a hand touches), turned → `lathe` (put chamfers, lips, grooves in the profile), bent rod → `sweep`, machined block → `rounded_box`, drilled → `cut`, fasteners → `screw`.
4. **Primary → secondary → tertiary**: 2–4 masses for the silhouette, then functional parts, then sparse small detail (screws, seams, spacers) concentrated where the camera looks.
5. **Joins**: parts sink into each other per the sheet; add a cap, spacer or seam where real objects have one. Group with `sh.group` and move the assembly as one.
6. **Clay check**: surfaces should show curvature and soft highlight roll-off, not flat planes. Check it reads the right way up from the camera.

```python
stock = sh.profile_extrude("Stock", outline_pts, 0.042, radii=corner_radii, edge_round=0.011, crown=0.0045)
barrel = sh.lathe("Barrel", [(0, 0), (0.0145, 0), (0.0112, 0.2), (0.0085, 0.555), (0, 0.555)], axis="X")
guard = sh.sweep("Trigger_guard", [(0.40, 0, -0.05), (0.375, 0, -0.084), (0.326, 0, -0.05)], 0.0032)
```

## 5. Workflow

1. **Header** (§1). Pick dials. Name references.
2. **Units & scale**: metric, scale 1.0. Block out at real dimensions.
3. **Model** per §4: reference sheet → silhouette → builders → detail tiers → clay check. Break perfect symmetry on anything used or handmade.
4. **Edges**: builders round edges by default; anything else gets `hz.bevel`. Shade smooth + harden normals.
5. **Materials**: start from `hz.physical_material(preset)`, then `hz.add_breakup` and, for WEAR ≥ 3, `hz.add_wear` (pass `size` ≈ the feature size; on thin tubes use ~radius/2). Wood gets `hz.add_grain`. Colors come from reference, desaturated a notch from what feels right.
6. **Placement**: `hz.ground`, `hz.jitter`; nothing on round coordinates; objects relate to each other (touching, leaning, overlapping in depth).
7. **Light**: motivated sources only (window, lamp, sun, practical). Warm/cool contrast via color temperature. `hz.light_rig("window" | "overcast" | "golden_hour" | "studio" | "night_practical")`.
8. **Camera**: chosen lens (35 mm environment, 50–85 mm product, 100 mm macro), eye height that a person would actually stand at, rule-of-thirds subject, foreground element when CLUTTER ≥ 3. `hz.camera_rig`.
9. **Color & render**: `hz.color_management`, `hz.render_settings`.
10. **Audit → preview → look → fix**, loop until audit ≥ 85 and the renders hold up at thumbnail size.

Read `reference/modeling.md` before modeling, `reference/ai-tells.md` for the full tell → fix catalog and `reference/materials.md` / `reference/light-camera.md` when doing that stage.

## 6. Pre-flight (answer each before saying done)

- [ ] Header posted; references are concrete; reference sheet with dimensions in the script.
- [ ] Silhouette render recognizable at thumbnail size; no part built from an unmodified primitive.
- [ ] `audit.py` run; score ≥ 85; every remaining FAIL justified in one line.
- [ ] Clay render: silhouette reads; shapes have size rhythm; no faceting.
- [ ] Beauty render viewed with Read: edges catch highlights; contact shadows exist; no clipped whites.
- [ ] At least one sign of history (wear, use, dust, asymmetry) proportional to WEAR.
- [ ] Nothing in §3 present unless the user asked for it.
- [ ] Dark materials actually look dark (if not: lower exposure / light intensity — AgX compresses range).

Report: final audit score, render paths, and any deliberate deviations.
