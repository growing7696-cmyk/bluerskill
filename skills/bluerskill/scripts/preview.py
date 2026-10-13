"""bluerskill preview — render check images you then LOOK at (Read tool).

    blender -b scene.blend --python preview.py -- --out ./renders [--views silhouette,clay,beauty,wire]
                                                  [--res 900] [--samples 48] [--engine CYCLES|EEVEE]

silhouette : flat black on white — judges the shape alone. If it doesn't read here, no material will save it.
clay   : neutral material override — judges silhouette, shape rhythm, bevel highlights, contact.
beauty : final materials and lights at preview quality.
wire   : wireframe override — judges topology density and faceting.
Also writes <view>_thumb.png at 160 px: if it doesn't read at thumbnail size, the composition fails.
After a beauty render, runs look.py on the pixels (value range, clipping, subject separation, framing,
highlights) using the silhouette as subject mask, and writes look.json. Pass --look 0 to skip.
Does not save the .blend.
"""

import os
import sys
import json

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {"out": "./renders", "views": "clay,beauty", "res": "900", "samples": "48", "engine": "CYCLES",
            "look": "1"}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--") and i + 1 < len(argv):
            opts[argv[i][2:]] = argv[i + 1]
            i += 2
        else:
            i += 1
    return opts


def _clay():
    m = bpy.data.materials.get("bz_clay") or bpy.data.materials.new("bz_clay")
    if not m.node_tree:
        m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (0.42, 0.40, 0.38, 1)
    p.inputs["Roughness"].default_value = 0.55
    return m


def _wire():
    m = bpy.data.materials.get("bz_wire") or bpy.data.materials.new("bz_wire")
    if not m.node_tree:
        m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.bl_idname != "ShaderNodeOutputMaterial":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    wf = nt.nodes.new("ShaderNodeWireframe")
    wf.use_pixel_size = True
    wf.inputs["Size"].default_value = 1.0
    a = nt.nodes.new("ShaderNodeBsdfPrincipled")
    a.inputs["Base Color"].default_value = (0.6, 0.6, 0.6, 1)
    b = nt.nodes.new("ShaderNodeEmission")
    b.inputs["Color"].default_value = (0.02, 0.02, 0.02, 1)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(wf.outputs[0], mix.inputs[0])
    nt.links.new(a.outputs[0], mix.inputs[1])
    nt.links.new(b.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m


def _black():
    m = bpy.data.materials.get("bz_black") or bpy.data.materials.new("bz_black")
    if not m.node_tree:
        m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.bl_idname != "ShaderNodeOutputMaterial":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0, 0, 0, 1)
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def _white_world():
    w = bpy.data.worlds.get("bz_white") or bpy.data.worlds.new("bz_white")
    if not w.node_tree:
        w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.bl_idname == "ShaderNodeBackground")
    bg.inputs["Color"].default_value = (1, 1, 1, 1)
    bg.inputs["Strength"].default_value = 1.0
    return w


def _support_surfaces(sc):
    """Floors, tables, walls, mats: big flat meshes. Hidden in the silhouette pass so the subject shows."""
    meshes = [o for o in sc.objects if o.type == "MESH" and not o.hide_render]
    if len(meshes) < 2:
        return []
    def flat(o):
        d = sorted(o.dimensions)
        return d[0] < 0.08 * d[2] and d[1] >= 0.25 * d[2]
    biggest = max(max(o.dimensions) for o in meshes)
    subject = max((max(o.dimensions) for o in meshes if not flat(o)), default=0)

    def bbox(o):
        pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
        return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])

    def carries(g):   # something rests on top of it (boards, trays, mats under the subject)
        gmn, gmx = bbox(g)
        for o in meshes:
            if o == g or flat(o):
                continue
            omn, omx = bbox(o)
            c = (omn + omx) / 2
            if gmn.x < c.x < gmx.x and gmn.y < c.y < gmx.y and omn.z >= gmx.z - 0.006:
                return True
        return False
    # big flat slabs, slabs larger than any single subject part (mats, coasters, tabletops),
    # and slabs that carry the subject (cutting boards, trays)
    return [o for o in meshes if flat(o) and (max(o.dimensions) >= 0.6 * biggest
                                              or max(o.dimensions) > subject or carries(o))]


def _thumb(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    img.scale(160, max(1, int(160 * h / w)))
    tp = path.replace(".png", "_thumb.png")
    img.filepath_raw = tp
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return tp


def run(out="./renders", views=("clay", "beauty"), res=900, samples=48, engine="CYCLES", look=True):
    sc = bpy.context.scene
    if not sc.camera:
        raise SystemExit("bluerskill preview: scene has no camera — run hz.camera_rig first")
    out = os.path.abspath(out)
    os.makedirs(out, exist_ok=True)
    r = sc.render
    saved = (r.engine, r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath,
             sc.view_layers[0].material_override)
    aspect = r.resolution_y / r.resolution_x
    r.engine = "BLENDER_EEVEE" if engine.upper().startswith("EEVEE") else "CYCLES"
    r.resolution_x, r.resolution_y, r.resolution_percentage = res, int(res * aspect), 100
    r.image_settings.file_format = "PNG"
    if r.engine == "CYCLES":
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
    else:
        sc.eevee.taa_render_samples = samples
        if hasattr(sc.eevee, "use_raytracing"):   # without it EEVEE reflects the world through occluders
            sc.eevee.use_raytracing = True
    written = []
    vl = sc.view_layers[0]
    world, vt, look = sc.world, sc.view_settings.view_transform, sc.view_settings.look
    supports = _support_surfaces(sc)
    render_views = list(views)
    if look and "beauty" in views and "silhouette" not in views:
        render_views.append("_mask")      # subject mask for look.py, not a deliverable
    for v in render_views:
        mask_only = v == "_mask"
        if mask_only:
            v = "silhouette"
            if r.engine == "CYCLES":
                sc.cycles.samples = 8
        vl.material_override = {"clay": _clay, "wire": _wire, "silhouette": _black}.get(v, lambda: None)()
        if v == "silhouette":
            sc.world, sc.view_settings.view_transform = _white_world(), "Standard"
            for o in supports:
                o.hide_render = True
        path = os.path.join(out, "_mask.png" if mask_only else f"{v}.png")
        r.filepath = path
        bpy.ops.render.render(write_still=True)
        if v == "silhouette":
            for o in supports:
                o.hide_render = False
            sc.world, sc.view_settings.view_transform = world, vt
            try:
                sc.view_settings.look = look
            except TypeError:
                pass
        if not mask_only:
            written += [path, _thumb(path)]
    r.engine, r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath, vl.material_override = saved
    print("BLUERSKILL_PREVIEW " + " ".join(written))
    if look and "beauty" in views:
        import look as lk
        mask = os.path.join(out, "silhouette.png" if "silhouette" in views else "_mask.png")
        res = lk.analyze(os.path.join(out, "beauty.png"), mask)
        lk.report(res, os.path.join(out, "beauty.png"))
        with open(os.path.join(out, "look.json"), "w") as f:
            json.dump(res, f, indent=1, default=float)
    return written


if __name__ == "__main__":
    o = _args()
    run(o["out"], [v.strip() for v in o["views"].split(",") if v.strip()], int(o["res"]), int(o["samples"]),
        o["engine"], o["look"] not in ("0", "false", "no"))
