# Light & camera reference

## Light rigs (`hz.light_rig(kind, target=obj)`)

| Kind | Sources | Temperatures | Use |
|---|---|---|---|
| `window` | Large area key from the side (1×1.5 m), weak cool world | key 5600 K, world bluish | Interiors, still life, product with a story |
| `overcast` | Huge soft top area + cool world | 6800–7500 K | Neutral, honest look; reveals form gently |
| `golden_hour` | Low sun (5–12° elevation) + cool sky world | sun 3200–3600 K, sky 9000 K | Exteriors, warmth, long shadows |
| `studio` | Key softbox 45°, large bounce fill opposite at ~25 %, rim from behind | key 5000 K, rim 6500 K | Product shots — but still add a surface and context |
| `night_practical` | Small warm practicals (lamp) + very dim blue world | 2700 K vs 10000 K | Mood, interiors at night |

Principles:
- **Motivated**: every light corresponds to something that could exist.
- **Ratio**: key:fill ≈ 3:1 to 8:1. Flat 1:1 is the CG default look.
- **Size**: soft sources are big; hard sources (sun, bare bulb) are small. Choose on purpose.
- **Temperature contrast**: warm vs cool between key and ambient is the cheapest realism win.
- Units: area light power in W; a window key for a 1 m scene ≈ 200–800 W in Cycles; sun 2–5 strength for daylight, with AgX.

## Camera (`hz.camera_rig(target, lens, distance, height, ...)`)

| Shot | Lens | f-stop (real) | Height |
|---|---|---|---|
| Interior / environment | 24–35 mm | f/5.6–f/11 | 1.2–1.6 m (standing eye) |
| Product hero | 50–85 mm | f/2.8–f/5.6 | Slightly above object top, ~10–25° down |
| Macro detail | 90–100 mm | f/4–f/8 (DOF is already thin) | At object |
| Character | 50–85 mm | f/2–f/4 | Chest/eye height of subject |

- Sensor 36 mm (full frame) so f-stops behave like real photography.
- Focus on the actual subject (`dof.focus_object`), not empty space.
- Rule of thirds: offset the subject using `shift_x/shift_y` or camera aim offset; `hz.camera_rig` has `frame_offset`.
- Verticals straight for architecture (camera level + shift_y), not tilted.
- Give the frame depth: foreground (out of focus), subject, background.

## Color management (`hz.color_management`)

- View transform: **AgX**. Look: "AgX - Base Contrast" (neutral) or "AgX - Medium High Contrast" (punchier product).
- Exposure to taste, but highlights should roll off, not clip.
- Never Standard for photoreal.
