# Materials reference

Values are linear (what you type into Principled BSDF), not sRGB hex. When converting from a picked hex color, convert sRGB → linear first (`hz.srgb(hex)` does this).

## Albedo / roughness table (non-metals unless noted)

| Material | Base color (linear, approx.) | Roughness | Notes |
|---|---|---|---|
| Fresh snow | 0.80–0.85 | 0.6 | Brightest realistic non-metal |
| White paint / plaster | 0.65–0.75 | 0.6–0.85 | Not 1.0 |
| Paper | 0.6–0.7 | 0.7–0.8 | Sheen 0.1 |
| Glazed ceramic | per color, ≤ 0.75 | 0.05–0.2 | Coat 0.3–1.0 |
| Unglazed ceramic / terracotta | 0.25–0.45 warm | 0.7–0.9 | |
| Light wood (oak, pine) | ~(0.42, 0.28, 0.15) | 0.4–0.7 | Varnished → coat |
| Dark wood (walnut) | ~(0.12, 0.07, 0.04) | 0.4–0.6 | |
| Concrete | 0.25–0.4 | 0.75–0.95 | Strong breakup |
| Asphalt | 0.04–0.08 | 0.8–0.95 | |
| Rubber | 0.02–0.05 | 0.6–0.85 | |
| Fabric (cotton) | per color | 0.8–1.0 | Sheen 0.3–1.0 |
| Leather | per color | 0.35–0.6 | Coat light |
| Skin | (0.6, 0.4, 0.33) light | 0.35–0.5 | SSS weight 0.1–0.3, radius in mm |
| Plastic ABS | per color | 0.3–0.5 | Specular default |
| Glass | 1.0 (transmission) | 0.0–0.05 | Transmission 1, IOR 1.5 |
| Aluminum (metal) | (0.91, 0.92, 0.92) | 0.2–0.45 brushed | metallic 1, anisotropic for brushed |
| Steel (metal) | (0.56, 0.57, 0.58) | 0.2–0.5 | |
| Gold (metal) | (1.0, 0.77, 0.34) | 0.15–0.35 | |
| Copper (metal) | (0.95, 0.64, 0.54) | 0.2–0.45 | Patina in cavities |
| Brass (metal) | (0.91, 0.78, 0.42) | 0.2–0.45 | |

Presets with these values ship in `hz.PRESETS`.

## Breakup recipe (what `hz.add_breakup` builds)

```
TexCoord.Object → Noise(scale = 1/(object size) * k, detail 8, roughness 0.6, distortion 0.2)
  → ColorRamp(roughness ± spread) → Principled.Roughness
TexCoord.Object → Noise(larger scale, different seed offset)
  → Mix(base, base*0.9 shifted hue, factor 0.0–0.15) → Principled.Base Color
```
Rules: two scales minimum (large blotches + fine grain). Roughness spread ±0.05–0.15. Color variation 3–10 %, never more unless reference demands (e.g., weathered wood).

## Wear recipe (what `hz.add_wear` builds)

- **Cavity grime**: AmbientOcclusion (distance ≈ 2–5 % of object size) → ramp → darken base color up to 25 %, raise roughness.
- **Edge wear**: AmbientOcclusion `inside=True` (convexity) → ramp masked by noise → lighten / expose under-material, lower roughness on handled spots.
- Strength scales with WEAR dial: `strength = WEAR / 10`.

## Stylized (STYLIZATION ≥ 5)

Still: deliberate value structure (light / mid / dark groups), shape-language consistency, softened edges (bigger bevels), limited palette (3–5 hues), hand-painted feel via large-scale color variation rather than micro noise. Toon shading: Shader to RGB → ColorRamp constant with 2–3 steps; keep edge bevels so the outline catches.
