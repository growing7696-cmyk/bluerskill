# 3D AI tells — catalog and fixes

Each tell has an ID (used by `audit.py`), why it reads as fake, and the fix. Severity: **H** = always fix, **M** = fix unless intended, **L** = polish.

## Geometry

| ID | Tell | Why it reads fake | Fix |
|---|---|---|---|
| G1 H | Razor-sharp edges | Real objects have an edge radius that catches a highlight line. Without it, forms look like polygons, not objects. | Bevel modifier, angle-limited, 2–3 segments, harden normals. `hz.bevel` |
| G2 H | Unapplied / non-uniform scale | Bevels and textures stretch; physics, DOF, SSS all wrong. | Apply scale. `hz.apply_scale` |
| G3 H | Wrong real-world size | A 2 m "mug" lights and blurs like a building. | Model at real dimensions; check `obj.dimensions`. |
| G4 M | Primitive soup / default names (`Cube.003`, `Cylinder`) | Signals nothing was modeled, just dropped in. | Model actual forms; name objects for what they are. |
| G5 H | Faceted curves | 32-segment cylinder or UV sphere on a silhouette screams default. | More segments or subdivision; shade smooth. |
| G6 H | Floating objects | No contact = no weight. | `hz.ground`; leave 0 gap, or slight intersection for soft materials. |
| G7 M | Perfect symmetry everywhere | Handmade and used things aren't symmetrical. | Asymmetric details: a dent, a tilted lid, a worn side. |
| G8 M | Clone army | Identical copies with identical rotation/scale. | `hz.jitter` + per-instance material variation (object random). |
| G9 M | Grid placement | Everything axis-aligned on round coordinates. | Rotate a few degrees, offset, cluster, let objects touch and lean. |
| G10 L | Zero-thickness surfaces | Walls/leaves/paper with no edge read as cardboard. | Solidify; even paper gets 0.1 mm. |
| G11 M | Uniform detail density | Every area equally detailed = nothing is the focus. | Concentrate detail at the focal point; simplify periphery. |
| G12 H | Primitive assembly | Object = unmodified cubes/cylinders/spheres placed together; reads as a toy. | Rebuild with `shapes.py` builders matched to manufacture (`reference/modeling.md`). |
| G13 M | Plank cutout | Extruded parts with flat sides and tiny edge radius. | `crown` + larger `edge_round` on `profile_extrude`. |

## Materials

| ID | Tell | Fix |
|---|---|---|
| M1 H | No material / default 0.8 gray, 0.5 roughness | `hz.physical_material(preset)` from `materials.md`. |
| M2 H | Constant roughness on hero surface | `hz.add_breakup` (noise → ramp into roughness, subtle base color variation). |
| M3 H | Pure saturated colors `(1,0,0)` | Real pigments are never 100 % saturated in linear space. Keep saturation ≤ ~0.85; pick from reference. |
| M4 H | Albedo too bright (>0.9) or pure black (0) | Non-metals 0.03–0.85. Fresh snow ~0.85, charcoal ~0.04. |
| M5 M | Metallic between 0.1 and 0.9 | Physically a surface is metal or not. Use 0/1, blend with a mask for paint-over-metal. |
| M6 M | Everything glossy plastic | Vary roughness families across materials in a scene (e.g. 0.15 glaze, 0.45 wood, 0.7 fabric). |
| M7 M | No wear in crevices/edges at WEAR ≥ 3 | `hz.add_wear`: AO-driven grime in cavities, convex edge lightening/roughening. |
| M8 L | Obvious procedural at default scale | Noise texture at default Scale 5 on object coords is recognizable. Change scale, detail, distortion; layer 2 scales. |
| M9 L | Emission as fill light | Use real lights; emission only for things that actually glow. |

## Lighting

| ID | Tell | Fix |
|---|---|---|
| L1 H | Startup point light only / no lights | Motivated rig: `hz.light_rig`. |
| L2 M | All lights pure white | Warm key (2700–4500 K) vs. cool fill/sky (6500–9000 K). |
| L3 M | Flat front light, no shadow shape | Key from the side/back (45–120° off camera axis). Shadows define form. |
| L4 M | Default world (0.05 gray) or black void | Low-intensity tinted world or HDRI; even a studio has bounce. |
| L5 H | Neon purple/teal on void | Banned by default (SKILL.md §3). |
| L6 L | Lights too small → hard CG shadows | Area lights sized like the real source (window ~1×1.5 m, softbox ~0.6–1.2 m). |

## Camera & composition

| ID | Tell | Fix |
|---|---|---|
| C1 H | Startup camera position / 50 mm untouched | Choose lens and position deliberately. `hz.camera_rig`. |
| C2 M | Subject dead center, eye level, nothing in foreground | Rule of thirds, a reason for the height, foreground framing at CLUTTER ≥ 3. |
| C3 M | No DOF on close-up / extreme DOF on wide | Real f-stop for the real distance; f/2.8–5.6 product, f/8+ architecture. |
| C4 L | Perfect isometric 3/4 on everything | Pick the angle that explains the object's function. |
| C5 L | No ground / infinite void | Place the subject in a context surface, even if minimal. |

## Render & color

| ID | Tell | Fix |
|---|---|---|
| R1 H | View transform Standard | AgX. `hz.color_management` |
| R2 M | Too few samples, no denoise / noisy | Cycles 128–512 + denoise, or EEVEE with raytracing on. |
| R3 L | Perfect lens | Tiny vignette, subtle chromatic aberration only in compositor, never heavy. |
| R4 L | Clipped highlights / crushed blacks | Check exposure; AgX look "Medium High Contrast" or "Base Contrast". |

## Story (the tell no script can catch)

Ask: *what happened here 5 minutes ago, and 5 years ago?* A mug with a coffee ring, a chair pushed back at an angle, a sticker half peeled, a worn path on a floor. One or two story details beat a hundred procedural scratches. If the scene has no answer to that question, it will read as generated.
