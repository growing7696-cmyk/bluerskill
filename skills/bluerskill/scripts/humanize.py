"""bluerskill helper library — replace Blender defaults with decisions.

Usage (inside Blender's Python):
    import sys; sys.path.insert(0, "<skill>/scripts")
    import humanize as hz

    hz.remove_startup()
    mug = ...                                   # your modeling
    hz.apply_scale(mug); hz.bevel(mug, wear=3)
    mat = hz.physical_material("glazed_ceramic", color="#d9cbb3")
    hz.assign(mug, mat); hz.add_breakup(mat, size=hz.obj_size(mug)); hz.add_wear(mat, 0.3, hz.obj_size(mug))
    table = hz.make_surface(0.9, 0.6, 0.03, "light_wood")
    hz.ground(mug)
    hz.light_rig("window", target=mug)
    hz.camera_rig(mug, lens=70, frame_offset=(0.12, 0.0))
    hz.color_management(); hz.render_settings()

Targets Blender 4.2+ / 5.x.
"""

import math
import random
import colorsys

import bpy
import bmesh
from mathutils import Vector, Euler

# --------------------------------------------------------------------------- #
# Color utilities
# --------------------------------------------------------------------------- #


def _srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb(value):
    """'#rrggbb' or (r,g,b) in 0-1 sRGB -> linear RGBA tuple for Blender sockets."""
    if isinstance(value, str):
        h = value.lstrip("#")
        value = tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    r, g, b = (_srgb_to_linear(c) for c in value[:3])
    return (r, g, b, 1.0)


def kelvin(k):
    """Approximate blackbody color for temperature k (Kelvin) -> linear RGBA."""
    t = k / 100.0
    if t <= 66:
        r = 255
        g = 99.4708025861 * math.log(t) - 161.1195681661
        b = 0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    else:
        r = 329.698727446 * ((t - 60) ** -0.1332047592)
        g = 288.1221695283 * ((t - 60) ** -0.0755148492)
        b = 255
    clamp = lambda v: max(0.0, min(255.0, v)) / 255.0
    return srgb((clamp(r), clamp(g), clamp(b)))


def _desaturate(rgba, amount):
    h, s, v = colorsys.rgb_to_hsv(*rgba[:3])
    return (*colorsys.hsv_to_rgb(h, s * (1 - amount), v), 1.0)


# --------------------------------------------------------------------------- #
# Object utilities
# --------------------------------------------------------------------------- #


def world_bbox(obj):
    """World-space bbox. For an Empty that parents an assembly, covers all child meshes."""
    objs = [obj]
    if obj.type == "EMPTY":
        objs = [o for o in obj.children_recursive if o.type == "MESH"] or [obj]
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def obj_size(obj):
    """Largest world-space dimension in meters."""
    mn, mx = world_bbox(obj)
    return max(mx - mn)


def obj_center(obj):
    mn, mx = world_bbox(obj)
    return (mn + mx) / 2


def _select_only(obj):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply_scale(obj):
    """Apply scale (and rotation is left alone). Hard rule #2."""
    if obj.type != "MESH" or obj.data.users > 1:
        return obj
    _select_only(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def shade_smooth(obj):
    if obj.type == "MESH":
        if hasattr(obj.data, "shade_smooth"):
            obj.data.shade_smooth()
        else:
            for p in obj.data.polygons:
                p.use_smooth = True
    return obj


def bevel(obj, width=None, segments=3, angle_deg=30, wear=3, harden=True):
    """Angle-limited bevel sized from the object's real dimensions.

    width default: 0.6 % of the smallest dimension at WEAR 0, up to ~2 % at WEAR 10.
    """
    if obj.type != "MESH":
        return None
    dims = [d for d in obj.dimensions if d > 1e-6] or [0.1]
    if width is None:
        width = min(dims) * (0.006 + 0.0014 * wear)
    shade_smooth(obj)
    mod = obj.modifiers.get("bz_bevel") or obj.modifiers.new("bz_bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(angle_deg)
    mod.harden_normals = harden
    mod.use_clamp_overlap = True
    try:
        mod.miter_outer = "MITER_ARC"
    except Exception:
        pass
    return mod


def subdivide(obj, levels=2, render_levels=None):
    shade_smooth(obj)
    mod = obj.modifiers.get("bz_subd") or obj.modifiers.new("bz_subd", "SUBSURF")
    mod.levels = levels
    mod.render_levels = render_levels if render_levels is not None else levels
    return mod


def solidify(obj, thickness):
    mod = obj.modifiers.get("bz_solid") or obj.modifiers.new("bz_solid", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = -1
    return mod


def ground(obj, floor_z=None, others=None, sink=0.0):
    """Drop obj so it rests on the highest surface below it (bbox-based).

    sink: meters to push into the surface (use ~0.5-2 mm for soft things like fabric).
    """
    mn, mx = world_bbox(obj)
    if floor_z is None:
        floor_z = 0.0 if others is None else None
        candidates = others if others is not None else [
            o for o in bpy.context.scene.objects if o.type == "MESH" and o is not obj]
        best = None
        for o in candidates:
            omn, omx = world_bbox(o)
            overlap = omn.x < mx.x and omx.x > mn.x and omn.y < mx.y and omx.y > mn.y
            if overlap and omx.z <= mn.z + 0.5 * (mx.z - mn.z):
                best = omx.z if best is None else max(best, omx.z)
        floor_z = best if best is not None else 0.0
    obj.location.z += (floor_z - mn.z) - sink
    return floor_z


def jitter(objs, rot_deg=(0.0, 0.0, 6.0), loc=0.0, scale=0.03, seed=7):
    """Break clone armies: per-object random rotation/location/scale."""
    rng = random.Random(seed)
    if isinstance(rot_deg, (int, float)):
        rot_deg = (0.0, 0.0, rot_deg)
    for o in objs:
        o.rotation_euler.x += math.radians(rng.uniform(-rot_deg[0], rot_deg[0]))
        o.rotation_euler.y += math.radians(rng.uniform(-rot_deg[1], rot_deg[1]))
        o.rotation_euler.z += math.radians(rng.uniform(-rot_deg[2], rot_deg[2]))
        if loc:
            o.location.x += rng.uniform(-loc, loc)
            o.location.y += rng.uniform(-loc, loc)
        if scale:
            s = 1 + rng.uniform(-scale, scale)
            o.scale = (o.scale.x * s, o.scale.y * s, o.scale.z * s)
    return objs


def remove_startup():
    """Delete the startup Cube / Light / Camera if they are still at their default spots."""
    defaults = {
        "Cube": Vector((0, 0, 0)),
        "Light": Vector((4.0762, 1.0055, 5.9039)),
        "Camera": Vector((7.3589, -6.9258, 4.9583)),
    }
    for name, loc in defaults.items():
        o = bpy.data.objects.get(name)
        if o and (o.location - loc).length < 0.01:
            bpy.data.objects.remove(o, do_unlink=True)


def make_surface(width=1.2, depth=0.8, thickness=0.03, preset="light_wood",
                 color=None, z_top=0.0, location=(0, 0), name="Surface", wear=3):
    """A real slab (table top, floor board, plinth) instead of an infinite plane."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0], location[1], z_top - thickness / 2))
    slab = bpy.context.active_object
    slab.name = name
    slab.scale = (width, depth, thickness)
    apply_scale(slab)
    bevel(slab, wear=wear)
    mat = physical_material(preset, color=color, name=f"{name}_mat")
    assign(slab, mat)
    add_breakup(mat, size=max(width, depth), amount=0.08)
    if "wood" in preset:
        add_grain(mat, spacing=max(0.0025, width * 0.004), along="X")  # wider grain on big boards
    return slab


# --------------------------------------------------------------------------- #
# Materials
# --------------------------------------------------------------------------- #

# (base color linear, roughness, metallic, extras)
PRESETS = {
    "white_paint":     ((0.70, 0.69, 0.66), 0.70, 0.0, {}),
    "plaster":         ((0.62, 0.60, 0.56), 0.85, 0.0, {}),
    "paper":           ((0.65, 0.63, 0.58), 0.75, 0.0, {"Sheen Weight": 0.1}),
    "glazed_ceramic":  ((0.62, 0.58, 0.50), 0.12, 0.0, {"Coat Weight": 0.6, "Coat Roughness": 0.05}),
    "terracotta":      ((0.38, 0.16, 0.08), 0.85, 0.0, {}),
    "light_wood":      ((0.42, 0.28, 0.15), 0.55, 0.0, {}),
    "dark_wood":       ((0.12, 0.07, 0.04), 0.50, 0.0, {"Coat Weight": 0.25, "Coat Roughness": 0.2}),
    "concrete":        ((0.32, 0.31, 0.29), 0.88, 0.0, {}),
    "asphalt":         ((0.06, 0.06, 0.06), 0.90, 0.0, {}),
    "rubber":          ((0.03, 0.03, 0.03), 0.75, 0.0, {}),
    "cotton":          ((0.45, 0.42, 0.38), 0.92, 0.0, {"Sheen Weight": 0.6, "Sheen Roughness": 0.4}),
    "leather":         ((0.18, 0.09, 0.05), 0.45, 0.0, {"Coat Weight": 0.15}),
    "plastic":         ((0.40, 0.40, 0.40), 0.40, 0.0, {}),
    "glass":           ((1.00, 1.00, 1.00), 0.02, 0.0, {"Transmission Weight": 1.0, "IOR": 1.5}),
    "aluminum":        ((0.91, 0.92, 0.92), 0.30, 1.0, {}),
    "brushed_aluminum": ((0.91, 0.92, 0.92), 0.35, 1.0, {"Anisotropic": 0.6}),
    "steel":           ((0.56, 0.57, 0.58), 0.35, 1.0, {}),
    "gold":            ((1.00, 0.77, 0.34), 0.25, 1.0, {}),
    "copper":          ((0.95, 0.64, 0.54), 0.30, 1.0, {}),
    "brass":           ((0.91, 0.78, 0.42), 0.30, 1.0, {}),
    "skin":            ((0.60, 0.40, 0.33), 0.42, 0.0, {"Subsurface Weight": 0.2,
                                                       "Subsurface Radius": (1.0, 0.35, 0.2)}),
}


def principled(mat):
    for n in mat.node_tree.nodes:
        if n.bl_idname == "ShaderNodeBsdfPrincipled":
            return n
    raise ValueError(f"{mat.name}: no Principled BSDF")


def physical_material(preset="plastic", color=None, name=None, roughness=None):
    """Material with physically plausible values. color: hex/sRGB tuple overrides base color."""
    base, rough, metal, extras = PRESETS[preset]
    mat = bpy.data.materials.new(name or preset)
    if not mat.node_tree:  # Blender < 5
        mat.use_nodes = True
    p = principled(mat)
    col = srgb(color) if color is not None else (*base, 1.0)
    if metal == 0.0:  # clamp non-metal albedo into the plausible band
        col = tuple(min(max(c, 0.03), 0.85) for c in col[:3]) + (1.0,)
    p.inputs["Base Color"].default_value = col
    p.inputs["Roughness"].default_value = rough if roughness is None else roughness
    p.inputs["Metallic"].default_value = metal
    for k, v in extras.items():
        if k in p.inputs:
            p.inputs[k].default_value = v
    return mat


def assign(obj, mat):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return mat


def _sock(sockets, identifier):
    for s in sockets:
        if s.identifier == identifier:
            return s
    raise KeyError(identifier)


def _source(nt, socket):
    """Output socket feeding `socket`, or None."""
    for l in nt.links:
        if l.to_socket == socket:
            return l.from_socket
    return None


def _noise(nt, scale, seed, detail=8.0, x=-1100, y=0):
    tc = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeTexCoord"), None) or nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (x - 300, y)
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.location = (x, y)
    nz.noise_dimensions = "4D"
    nz.inputs["W"].default_value = seed * 3.17
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = detail
    nz.inputs["Roughness"].default_value = 0.6
    if "Distortion" in nz.inputs:
        nz.inputs["Distortion"].default_value = 0.25
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    return nz


def _ramp(nt, a, b, pa=0.35, pb=0.7, x=-800, y=0):
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.location = (x, y)
    e = r.color_ramp.elements
    e[0].position, e[1].position = pa, pb
    e[0].color = a if len(a) == 4 else (*a, 1)
    e[1].color = b if len(b) == 4 else (*b, 1)
    return r


def _mix_rgba(nt, blend="MIX", x=-300, y=200):
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = "RGBA"
    m.blend_type = blend
    m.location = (x, y)
    return m


def add_breakup(mat, size=0.2, amount=0.1, rough_spread=None, seed=1):
    """Two-scale breakup: roughness variation + subtle base-color variation (M2)."""
    nt = mat.node_tree
    p = principled(mat)
    rough_in = p.inputs["Roughness"]
    base_in = p.inputs["Base Color"]

    # Roughness: fine + large noise multiplied, mapped around current value.
    if _source(nt, rough_in) is None:
        r0 = rough_in.default_value
        spread = rough_spread if rough_spread is not None else max(0.05, min(0.15, r0 * 0.35))
        fine = _noise(nt, 1.0 / max(size * 0.08, 1e-4), seed, x=-1100, y=-300)
        big = _noise(nt, 1.0 / max(size * 0.5, 1e-4), seed + 11, detail=3, x=-1100, y=-550)
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.location = (-850, -400)
        nt.links.new(fine.outputs["Fac"], mul.inputs[0])
        nt.links.new(big.outputs["Fac"], mul.inputs[1])
        lo, hi = max(r0 - spread, 0.0), min(r0 + spread, 1.0)
        ramp = _ramp(nt, (lo, lo, lo), (hi, hi, hi), 0.12, 0.42, x=-600, y=-400)
        nt.links.new(mul.outputs[0], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], rough_in)

    # Base color: large-scale variation toward a darker, slightly shifted tone.
    if amount > 0:
        src = _source(nt, base_in)
        base = base_in.default_value[:]
        h, s, v = colorsys.rgb_to_hsv(*base[:3])
        alt = (*colorsys.hsv_to_rgb((h + 0.015) % 1, min(s * 1.08, 1), v * 0.82), 1)
        nz = _noise(nt, 1.0 / max(size * 0.35, 1e-4), seed + 23, detail=4, x=-1100, y=300)
        fac = _ramp(nt, (0, 0, 0), (amount, amount, amount), 0.35, 0.75, x=-800, y=300)
        nt.links.new(nz.outputs["Fac"], fac.inputs["Fac"])
        mix = _mix_rgba(nt, x=-350, y=250)
        nt.links.new(fac.outputs["Color"], _sock(mix.inputs, "Factor_Float"))
        if src is not None:
            nt.links.new(src, _sock(mix.inputs, "A_Color"))
        else:
            _sock(mix.inputs, "A_Color").default_value = base
        _sock(mix.inputs, "B_Color").default_value = alt
        nt.links.new(_sock(mix.outputs, "Result_Color"), base_in)
    return mat


def add_grain(mat, spacing=0.0025, along="X", contrast=0.18, seed=2, late_wood=(0.45, 0.33, 0.25)):
    """Wood grain: distorted wave bands darkening base color, slightly rougher in late wood."""
    nt = mat.node_tree
    p = principled(mat)
    base_in, rough_in = p.inputs["Base Color"], p.inputs["Roughness"]
    tc = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeTexCoord"), None) or nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")   # stretch noise along the grain direction
    mp.location = (-1300, -800)
    # Growth rings whose center lies outside the board: slicing them gives flat-sawn arcs
    # and uneven spacing instead of evenly spaced procedural stripes.
    stretch = 0.12
    mp.inputs["Scale"].default_value = (stretch, 1, 1) if along == "X" else (1, stretch, 1)
    mp.inputs["Location"].default_value = (0.0, 0.08 + 0.03 * seed, 0.05) if along == "X" else (0.08 + 0.03 * seed, 0.0, 0.05)
    mp.inputs["Rotation"].default_value = (math.radians(0.7), math.radians(1.3), 0)
    # domain warp: wobble the coordinates so rings meander instead of running parallel
    warp = nt.nodes.new("ShaderNodeTexNoise")
    warp.location = (-1500, -1000)
    warp.inputs["Scale"].default_value = 1.0 / (spacing * 60)
    warp.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], warp.inputs["Vector"])
    centered = nt.nodes.new("ShaderNodeVectorMath")
    centered.operation = "SUBTRACT"
    centered.location = (-1300, -1000)
    centered.inputs[1].default_value = (0.5, 0.5, 0.5)
    nt.links.new(warp.outputs["Color"], centered.inputs[0])
    scaled = nt.nodes.new("ShaderNodeVectorMath")
    scaled.operation = "SCALE"
    scaled.location = (-1150, -1000)
    scaled.inputs["Scale"].default_value = spacing * 8
    nt.links.new(centered.outputs[0], scaled.inputs[0])
    warped = nt.nodes.new("ShaderNodeVectorMath")
    warped.operation = "ADD"
    warped.location = (-1000, -900)
    nt.links.new(tc.outputs["Object"], warped.inputs[0])
    nt.links.new(scaled.outputs[0], warped.inputs[1])
    nt.links.new(warped.outputs[0], mp.inputs["Vector"])
    wv = nt.nodes.new("ShaderNodeTexWave")
    wv.location = (-1100, -800)
    wv.wave_type = "RINGS"
    wv.rings_direction = "X" if along == "X" else "Y"
    wv.wave_profile = "SAW"
    wv.inputs["Scale"].default_value = 1.0 / spacing / 12.0
    wv.inputs["Distortion"].default_value = 9.0
    wv.inputs["Detail"].default_value = 6.0
    wv.inputs["Detail Scale"].default_value = 0.6
    wv.inputs["Detail Roughness"].default_value = 0.65
    wv.inputs["Phase Offset"].default_value = seed
    nt.links.new(mp.outputs["Vector"], wv.inputs["Vector"])
    ramp = _ramp(nt, (0, 0, 0), (contrast, contrast, contrast), 0.25, 0.85, x=-850, y=-800)
    nt.links.new(wv.outputs["Fac"], ramp.inputs["Fac"])
    mix = _mix_rgba(nt, "MULTIPLY", x=-150, y=450)
    nt.links.new(ramp.outputs["Color"], _sock(mix.inputs, "Factor_Float"))
    src = _source(nt, base_in)
    if src is not None:
        nt.links.new(src, _sock(mix.inputs, "A_Color"))
    else:
        _sock(mix.inputs, "A_Color").default_value = base_in.default_value[:]
    _sock(mix.inputs, "B_Color").default_value = (*late_wood, 1)
    nt.links.new(_sock(mix.outputs, "Result_Color"), base_in)
    rsrc = _source(nt, rough_in)
    ma = nt.nodes.new("ShaderNodeMath")
    ma.operation = "MULTIPLY_ADD"
    ma.use_clamp = True
    ma.location = (-150, -600)
    nt.links.new(ramp.outputs["Color"], ma.inputs[0])
    ma.inputs[1].default_value = 0.3
    if rsrc is not None:
        nt.links.new(rsrc, ma.inputs[2])
    else:
        ma.inputs[2].default_value = rough_in.default_value
    nt.links.new(ma.outputs[0], rough_in)
    return mat


def add_wear(mat, strength=0.3, size=0.2, grime=(0.05, 0.04, 0.03), edge_tint=None, seed=5):
    """AO-driven cavity grime + noise-masked convex edge wear (M7). strength ≈ WEAR/10.

    size = the feature size the wear should respect, NOT the object length. On thin convex parts
    (tubes, rods, scopes, cables) use ~ their radius/2, or the whole surface reads as "edge" and
    gets tinted. Check the beauty render: if a dark part looks gray, this is usually why.
    """
    nt = mat.node_tree
    p = principled(mat)
    base_in, rough_in = p.inputs["Base Color"], p.inputs["Roughness"]
    dist = max(size * 0.04, 0.002)

    cav = nt.nodes.new("ShaderNodeAmbientOcclusion")
    cav.location = (-800, 650)
    cav.inputs["Distance"].default_value = dist
    cav_mask = _ramp(nt, (1, 1, 1), (0, 0, 0), 0.4, 0.95, x=-600, y=650)  # 1 in cavities
    nt.links.new(cav.outputs["AO"], cav_mask.inputs["Fac"])

    edge = nt.nodes.new("ShaderNodeAmbientOcclusion")
    edge.location = (-800, 900)
    edge.inside = True
    edge.inputs["Distance"].default_value = dist * 0.5
    edge_mask = _ramp(nt, (1, 1, 1), (0, 0, 0), 0.55, 0.9, x=-600, y=900)  # 1 on convex edges
    nt.links.new(edge.outputs["AO"], edge_mask.inputs["Fac"])
    breaker = _noise(nt, 1.0 / max(size * 0.05, 1e-4), seed, x=-800, y=1150)
    brk = _ramp(nt, (0, 0, 0), (1, 1, 1), 0.45, 0.6, x=-600, y=1150)
    nt.links.new(breaker.outputs["Fac"], brk.inputs["Fac"])
    emul = nt.nodes.new("ShaderNodeMath")
    emul.operation = "MULTIPLY"
    emul.location = (-400, 1000)
    nt.links.new(edge_mask.outputs["Color"], emul.inputs[0])
    nt.links.new(brk.outputs["Color"], emul.inputs[1])

    # Color chain: current -> grime (multiply) -> edge lighten
    cur = _source(nt, base_in)
    base_val = base_in.default_value[:]
    g = _mix_rgba(nt, "MULTIPLY", x=-200, y=650)
    gs = nt.nodes.new("ShaderNodeMath")
    gs.operation = "MULTIPLY"
    gs.location = (-400, 650)
    gs.inputs[1].default_value = min(strength * 0.9, 0.9)
    nt.links.new(cav_mask.outputs["Color"], gs.inputs[0])
    nt.links.new(gs.outputs[0], _sock(g.inputs, "Factor_Float"))
    if cur is not None:
        nt.links.new(cur, _sock(g.inputs, "A_Color"))
    else:
        _sock(g.inputs, "A_Color").default_value = base_val
    _sock(g.inputs, "B_Color").default_value = (*grime, 1)

    e = _mix_rgba(nt, "MIX", x=0, y=800)
    es = nt.nodes.new("ShaderNodeMath")
    es.operation = "MULTIPLY"
    es.location = (-200, 1000)
    es.inputs[1].default_value = min(strength, 1.0)
    nt.links.new(emul.outputs[0], es.inputs[0])
    nt.links.new(es.outputs[0], _sock(e.inputs, "Factor_Float"))
    nt.links.new(_sock(g.outputs, "Result_Color"), _sock(e.inputs, "A_Color"))
    tint = edge_tint or _desaturate(tuple(min(c * 1.35 + 0.04, 0.85) for c in base_val[:3]) + (1,), 0.3)
    _sock(e.inputs, "B_Color").default_value = tint
    nt.links.new(_sock(e.outputs, "Result_Color"), base_in)

    # Roughness: cavities rougher.
    rsrc = _source(nt, rough_in)
    ma = nt.nodes.new("ShaderNodeMath")
    ma.operation = "MULTIPLY_ADD"
    ma.use_clamp = True
    ma.location = (-150, -250)
    nt.links.new(cav_mask.outputs["Color"], ma.inputs[0])
    ma.inputs[1].default_value = 0.25 * strength
    if rsrc is not None:
        nt.links.new(rsrc, ma.inputs[2])
    else:
        ma.inputs[2].default_value = rough_in.default_value
    nt.links.new(ma.outputs[0], rough_in)
    return mat


# --------------------------------------------------------------------------- #
# World, light, camera, render
# --------------------------------------------------------------------------- #


def world(color=(0.6, 0.7, 0.85), strength=0.3, temperature=None):
    w = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    if not w.node_tree:
        w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.bl_idname == "ShaderNodeBackground")
    bg.inputs["Color"].default_value = kelvin(temperature) if temperature else (*color[:3], 1)
    bg.inputs["Strength"].default_value = strength
    return w


def _aim(obj, target_point):
    d = Vector(target_point) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def _area(name, size, power, temp, loc, aim_at, size_y=None, shape="RECTANGLE"):
    data = bpy.data.lights.new(name, "AREA")
    data.shape = shape
    data.size = size
    data.size_y = size_y or size
    data.energy = power
    if hasattr(data, "use_temperature"):
        data.use_temperature = True
        data.temperature = temp
        data.color = (1, 1, 1)
    else:
        data.color = kelvin(temp)[:3]
    o = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    _aim(o, aim_at)
    return o


def _sph(center, dist, azim_deg, elev_deg):
    a, e = math.radians(azim_deg), math.radians(elev_deg)
    return center + Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))) * dist


def light_rig(kind="window", target=None, clear=True, intensity=1.0):
    """Motivated lighting rigs. See reference/light-camera.md."""
    sc = bpy.context.scene
    if clear:
        for o in [o for o in sc.objects if o.type == "LIGHT"]:
            bpy.data.objects.remove(o, do_unlink=True)
    c = obj_center(target) if target else Vector((0, 0, 0.5))
    s = max(obj_size(target), 0.1) if target else 1.0
    made = []
    if kind == "window":
        d = s * 3.0
        made.append(_area("Window", s * 1.6, 26 * d * d * intensity, 5600, _sph(c, d, 160, 28), c, size_y=s * 2.4))
        made.append(_area("Bounce", s * 2.0, 4 * d * d * intensity, 4200, _sph(c, d, -20, 10), c))
        world(strength=0.25 * intensity, temperature=9000)
    elif kind == "overcast":
        d = s * 3.5
        made.append(_area("Sky", s * 5, 30 * d * d * intensity, 7000, c + Vector((0, 0, d)), c))
        world(strength=0.6 * intensity, temperature=8000)
    elif kind == "golden_hour":
        data = bpy.data.lights.new("Sun", "SUN")
        data.energy = 3.5 * intensity
        data.angle = math.radians(1.5)
        if hasattr(data, "use_temperature"):
            data.use_temperature, data.temperature = True, 3400
        else:
            data.color = kelvin(3400)[:3]
        o = bpy.data.objects.new("Sun", data)
        sc.collection.objects.link(o)
        o.location = _sph(c, s * 5, 150, 9)
        _aim(o, c)
        made.append(o)
        world(strength=0.5 * intensity, temperature=10000)
    elif kind == "studio":
        d = s * 3.0
        made.append(_area("Key", s * 1.4, 45 * d * d * intensity, 5000, _sph(c, d, -130, 35), c))
        made.append(_area("Fill", s * 2.5, 9 * d * d * intensity, 5600, _sph(c, d, -20, 15), c))
        made.append(_area("Rim", s * 0.8, 40 * d * d * intensity, 6800, _sph(c, d, 100, 40), c, size_y=s * 2))
        world(strength=0.08 * intensity, temperature=6500)
    elif kind == "night_practical":
        data = bpy.data.lights.new("Practical", "POINT")
        data.energy = 40 * intensity
        data.shadow_soft_size = 0.04
        if hasattr(data, "use_temperature"):
            data.use_temperature, data.temperature = True, 2700
        else:
            data.color = kelvin(2700)[:3]
        o = bpy.data.objects.new("Practical", data)
        sc.collection.objects.link(o)
        o.location = _sph(c, s * 2, 140, 35)
        made.append(o)
        world(strength=0.03 * intensity, temperature=12000)
    else:
        raise ValueError(kind)
    return made


def camera_rig(target, lens=60, distance=None, azimuth_deg=-62, elevation_deg=16,
               fstop=4.0, frame_offset=(0.1, 0.03), fill=0.55, name="Camera"):
    """Deliberate camera: real lens, real f-stop, off-center framing.

    frame_offset: where the subject sits relative to frame center, in fractions of frame width
                  (0.167 ≈ rule-of-thirds line). fill: fraction of frame width the subject spans.
    """
    sc = bpy.context.scene
    old = bpy.data.objects.get(name)
    if old and old.type == "CAMERA":
        bpy.data.objects.remove(old, do_unlink=True)
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam_data.sensor_width = 36
    cam = bpy.data.objects.new(name, cam_data)
    sc.collection.objects.link(cam)
    c = obj_center(target)
    s = obj_size(target)
    if distance is None:
        half_fov = math.atan(18.0 / lens)
        distance = (s / fill) / 2 / math.tan(half_fov)
    cam.location = _sph(c, distance, azimuth_deg, elevation_deg)
    _aim(cam, c)
    cam_data.shift_x = -frame_offset[0]
    cam_data.shift_y = -frame_offset[1]
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = (c - cam.location).length
    cam_data.dof.aperture_fstop = fstop
    sc.camera = cam
    return cam


def color_management(look="AgX - Base Contrast", exposure=0.0):
    vs = bpy.context.scene.view_settings
    vs.view_transform = "AgX"
    for candidate in (look, look.replace("AgX - ", ""), "None"):
        try:
            vs.look = candidate
            break
        except TypeError:
            continue
    vs.exposure = exposure


def render_settings(engine="CYCLES", samples=192, resolution=(1600, 1200), denoise=True, gpu=True):
    sc = bpy.context.scene
    sc.render.engine = engine
    sc.render.resolution_x, sc.render.resolution_y = resolution
    sc.render.resolution_percentage = 100
    if engine == "CYCLES":
        sc.cycles.samples = samples
        sc.cycles.use_denoising = denoise
        sc.cycles.use_adaptive_sampling = True
        if gpu:
            try:
                prefs = bpy.context.preferences.addons["cycles"].preferences
                for dev_type in ("METAL", "OPTIX", "CUDA", "HIP", "ONEAPI"):
                    try:
                        prefs.compute_device_type = dev_type
                        prefs.get_devices()
                        if any(d.type != "CPU" for d in prefs.devices):
                            for d in prefs.devices:
                                d.use = True
                            sc.cycles.device = "GPU"
                            break
                    except TypeError:
                        continue
            except Exception:
                pass
    else:
        sc.eevee.taa_render_samples = samples
        if hasattr(sc.eevee, "use_raytracing"):
            sc.eevee.use_raytracing = True
    return sc
