"""bluerskill audit — score a Blender scene for 3D AI tells.

    blender -b scene.blend --python audit.py              # human report
    blender -b scene.blend --python audit.py -- --json    # machine-readable

Inside a live session (blender-mcp): exec this file, or `import audit; audit.run()`.
IDs match reference/ai-tells.md. Score = 100 - penalties (H=10, M=5, L=2), floor 0.
"""

import sys
import re
import json
import math
import colorsys

import bpy
import bmesh
from mathutils import Vector

WEIGHT = {"H": 10, "M": 5, "L": 2}
DEFAULT_NAME = re.compile(r"^(Cube|Sphere|Cylinder|Cone|Torus|Plane|Icosphere|Suzanne|Circle|Grid)(\.\d+)?$")
STARTUP_CAM = Vector((7.3589, -6.9258, 4.9583))
STARTUP_LIGHT = Vector((4.0762, 1.0055, 5.9039))


def _bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def _principled(mat):
    if not mat or not mat.node_tree:
        return None
    for n in mat.node_tree.nodes:
        if n.bl_idname == "ShaderNodeBsdfPrincipled":
            return n
    return None


def _edge_stats(o, depsgraph):
    """(sharp_edges, gentle_edges, total, all_flat) on the evaluated mesh."""
    ev = o.evaluated_get(depsgraph)
    me = ev.to_mesh()
    try:
        bm = bmesh.new()
        bm.from_mesh(me)
        sharp = gentle = 0
        edges = bm.edges
        step = max(1, len(edges) // 50000)
        for i, e in enumerate(edges):
            if i % step or len(e.link_faces) != 2:
                continue
            a = math.degrees(e.calc_face_angle(0.0))
            if a > 50:
                sharp += 1
            elif 5 < a < 25 and e.smooth:
                gentle += 1
            elif 5 < a < 25:
                gentle += 1
        all_flat = not any(p.use_smooth for p in me.polygons) if me.polygons else False
        total = len(edges)
        bm.free()
        return sharp, gentle, total, all_flat
    finally:
        ev.to_mesh_clear()


def run(as_json=False):
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    meshes = [o for o in sc.objects if o.type == "MESH" and not o.hide_render]
    lights = [o for o in sc.objects if o.type == "LIGHT" and not o.hide_render]
    findings = []

    def add(fid, sev, msg, objs=None, fix=""):
        findings.append({"id": fid, "sev": sev, "msg": msg,
                         "objects": sorted(set(objs or []))[:12], "fix": fix})

    # ---------------- Geometry ----------------
    razor, faceted, nonuni, odd_size, default_names = [], [], [], [], []
    for o in meshes:
        has_soft = any(m.type in {"BEVEL", "SUBSURF"} and m.show_render for m in o.modifiers)
        sharp, gentle, total, all_flat = _edge_stats(o, dg)
        if sharp >= 4 and not has_soft:
            razor.append(o.name)
        if all_flat and gentle >= 8:
            faceted.append(o.name)
        s = o.scale
        if max(s) / max(min(s), 1e-9) > 1.01:
            nonuni.append(o.name)
        size = max(o.dimensions)
        if size > 200 or (0 < size < 0.002):
            odd_size.append(o.name)
        if DEFAULT_NAME.match(o.name):
            default_names.append(o.name)
    if razor:
        add("G1", "H", f"{len(razor)} object(s) with razor-sharp edges and no bevel/subdivision", razor,
            "hz.bevel(obj, wear=WEAR)")
    if nonuni:
        add("G2", "H", "non-uniform / unapplied scale (stretches bevels & textures)", nonuni, "hz.apply_scale(obj)")
    if odd_size:
        add("G3", "H", "implausible real-world size", odd_size, "model at real dimensions (1 BU = 1 m)")
    if default_names:
        sev = "H" if any(n.startswith("Cube") for n in default_names) and len(meshes) <= 2 else "M"
        add("G4", sev, "primitive soup: default object names", default_names,
            "model real forms; name objects for what they are")
    if faceted:
        add("G5", "H", "faceted curved surfaces (flat shading on curvature)", faceted,
            "hz.shade_smooth(obj) + more segments / hz.subdivide(obj)")

    # Floating (bbox heuristic)
    if len(meshes) >= 2:
        floor = min(_bbox(o)[0].z for o in meshes)
        floating = []
        for o in meshes:
            if o.parent:
                continue
            mn, mx = _bbox(o)
            if mn.z <= floor + 1e-4:
                continue
            tops = []
            for p in meshes:
                if p is o:
                    continue
                pmn, pmx = _bbox(p)
                if pmn.x < mx.x and pmx.x > mn.x and pmn.y < mx.y and pmx.y > mn.y and pmx.z <= mn.z + 1e-3:
                    tops.append(pmx.z)
            support = max(tops) if tops else floor
            gap = mn.z - support
            if gap > max(0.001, 0.01 * max(o.dimensions)):
                floating.append(o.name)
        if floating:
            add("G6", "H", "object(s) appear to float above their support (bbox check)", floating,
                "hz.ground(obj)  — ignore if intentionally suspended")

    # Clone army / grid placement
    groups = {}
    for o in meshes:
        key = (o.data.name if o.data.users > 1 else None) or tuple(round(d, 3) for d in o.dimensions)
        groups.setdefault(key, []).append(o)
    clones = []
    for g in groups.values():
        if len(g) >= 3:
            rots = {tuple(round(r, 3) for r in o.rotation_euler) for o in g}
            scales = {tuple(round(s, 3) for s in o.scale) for o in g}
            if len(rots) == 1 and len(scales) == 1:
                clones += [o.name for o in g]
    if clones:
        add("G8", "M", "clone army: identical copies with identical rotation/scale", clones,
            "hz.jitter(objs) + per-instance material variation")
    if len(meshes) >= 3:
        def gridish(o):
            rot_ok = all(abs((math.degrees(r) + 1e-6) % 90) < 0.1 or abs(math.degrees(r) % 90 - 90) < 0.1
                         for r in o.rotation_euler)
            loc_ok = all(abs(v * 20 - round(v * 20)) < 1e-3 for v in o.location)
            return rot_ok and loc_ok
        g = [o.name for o in meshes if gridish(o)]
        if len(g) / len(meshes) >= 0.8:
            add("G9", "M", "grid placement: axis-aligned on round coordinates", g,
                "rotate a few degrees, offset, let objects touch/lean")

    # ---------------- Materials ----------------
    no_mat, default_mat, const_rough, saturated, albedo, half_metal = [], [], [], [], [], []
    mats_seen = {}
    for o in meshes:
        mats = [s.material for s in o.material_slots if s.material]
        if not mats:
            no_mat.append(o.name)
        for m in mats:
            mats_seen.setdefault(m.name, (m, []))[1].append(o.name)
    rough_consts = []
    for name, (m, users) in mats_seen.items():
        p = _principled(m)
        if not p:
            continue
        bc, ro, me = p.inputs["Base Color"], p.inputs["Roughness"], p.inputs["Metallic"]
        tw = p.inputs.get("Transmission Weight")
        is_glass = tw is not None and not tw.is_linked and tw.default_value > 0.5
        col = bc.default_value[:3]
        if not bc.is_linked and not ro.is_linked and all(abs(c - 0.8) < 0.02 for c in col) \
                and abs(ro.default_value - 0.5) < 0.01:
            default_mat.append(name)
        if not ro.is_linked:
            const_rough.append(name)
            rough_consts.append(ro.default_value)
        metallic = me.default_value if not me.is_linked else None
        if not bc.is_linked and not is_glass and (metallic is None or metallic < 0.5):
            if max(col) >= 0.95 and min(col) <= 0.02:
                saturated.append(name)
            elif max(col) > 0.9 or max(col) < 0.01:
                albedo.append(name)
        if metallic is not None and 0.1 < metallic < 0.9:
            half_metal.append(name)
    if no_mat:
        add("M1", "H", "mesh(es) with no material", no_mat, "hz.physical_material(preset)")
    if default_mat:
        add("M1", "H", "default 0.8 gray / 0.5 roughness material", default_mat,
            "hz.physical_material(preset) from reference/materials.md")
    if const_rough:
        sev = "H" if len(const_rough) == len(mats_seen) else "M"
        add("M2", sev, "constant roughness (no breakup)", const_rough, "hz.add_breakup(mat, size=hz.obj_size(obj))")
    if saturated:
        add("M3", "H", "pure saturated base color", saturated, "pick color from reference; ≤ ~0.85 saturation")
    if albedo:
        add("M4", "M", "non-metal albedo outside 0.01–0.9", albedo, "non-metals 0.03–0.85")
    if half_metal:
        add("M5", "M", "metallic between 0.1 and 0.9", half_metal, "metallic is 0 or 1; mask blends")
    if len(mats_seen) >= 2 and len(rough_consts) == len(mats_seen) and max(rough_consts) <= 0.25:
        add("M6", "M", "everything glossy: all roughness ≤ 0.25", list(mats_seen), "vary roughness families")

    # ---------------- Lighting ----------------
    w = sc.world
    bg = None
    if w and w.node_tree:
        bg = next((n for n in w.node_tree.nodes if n.bl_idname == "ShaderNodeBackground"), None)
    world_linked = bool(bg and bg.inputs["Color"].is_linked)
    world_strength = bg.inputs["Strength"].default_value if bg else 0
    if not lights and not world_linked:
        add("L1", "H", "no lights and no HDRI", fix='hz.light_rig("window", target=hero)')
    elif len(lights) == 1 and (lights[0].location - STARTUP_LIGHT).length < 0.01:
        add("L1", "H", "only the startup light", [lights[0].name], 'hz.light_rig("window", target=hero)')
    if lights:
        def white(l):
            d = l.data
            if getattr(d, "use_temperature", False) and abs(d.temperature - 6500) > 300:
                return False
            return all(abs(c - 1) < 0.02 for c in d.color)
        if all(white(l) for l in lights):
            add("L2", "M", "all lights pure white (no temperature contrast)", [l.name for l in lights],
                "warm key 2700–4500 K vs cool world/fill 6500–9000 K")
        if all(l.data.type == "POINT" for l in lights):
            add("L6", "L", "only point lights (small hard CG sources)", [l.name for l in lights],
                "area lights sized like real sources")
        neon = 0
        for l in lights:
            if getattr(l.data, "use_temperature", False):
                continue
            h, s, v = colorsys.rgb_to_hsv(*l.data.color)
            if s > 0.6 and (0.45 < h < 0.95):
                neon += 1
        if neon >= 2 and world_strength < 0.1:
            add("L5", "M", "neon purple/cyan lighting on a dark void (banned default look)",
                [l.name for l in lights], "motivated sources; see SKILL.md §3")
    if bg and not world_linked:
        c = bg.inputs["Color"].default_value[:3]
        if all(abs(x - 0.0509) < 0.005 for x in c):
            add("L4", "M", "default world color (0.05 gray)", fix="hz.world(...) or an HDRI")
    elif not w:
        add("L4", "M", "no world", fix="hz.world(...)")

    # ---------------- Camera ----------------
    cam = sc.camera
    if not cam:
        add("C1", "H", "no scene camera", fix="hz.camera_rig(hero)")
    else:
        if (cam.location - STARTUP_CAM).length < 0.01:
            add("C1", "H", "startup camera position", [cam.name], "hz.camera_rig(hero, lens=..., ...)")
        if not cam.data.dof.use_dof:
            add("C3", "L", "depth of field off", [cam.name], "real f-stop for the real distance")
        hero = None
        cands = [o for o in meshes if len(meshes) == 1 or max(o.dimensions[:2]) < 0.9 * max(
            max(m.dimensions[:2]) for m in meshes)] or meshes
        if cands:
            hero = max(cands, key=lambda o: o.dimensions.x * o.dimensions.y * o.dimensions.z)
        if hero:
            from bpy_extras.object_utils import world_to_camera_view
            mn, mx = _bbox(hero)
            p = world_to_camera_view(sc, cam, (mn + mx) / 2)
            if abs(p.x - 0.5) < 0.04 and abs(p.y - 0.5) < 0.04:
                add("C2", "L", f"hero '{hero.name}' dead-center in frame", [hero.name],
                    "frame_offset in hz.camera_rig (≈0.1–0.17)")
    if meshes:
        def supports_something(g):
            gmn, gmx = _bbox(g)
            dz, dxy = gmx.z - gmn.z, max(gmx.x - gmn.x, gmx.y - gmn.y)
            if dz > 0.25 * dxy:          # not a flat surface
                return False
            for o in meshes:
                if o is g:
                    continue
                omn, omx = _bbox(o)
                cx, cy = (omn.x + omx.x) / 2, (omn.y + omx.y) / 2
                if gmn.x < cx < gmx.x and gmn.y < cy < gmx.y and omn.z >= gmx.z - 0.01 * max(o.dimensions) - 1e-4:
                    return True
            return False
        if not any(supports_something(g) for g in meshes):
            add("C5", "M", "no ground / context surface under the subject", fix="hz.make_surface(...)")

    # ---------------- Render ----------------
    vs = sc.view_settings
    if vs.view_transform == "Standard":
        add("R1", "H", "view transform is Standard (clipped CG highlights)", fix="hz.color_management()")
    if sc.render.engine == "CYCLES" and sc.cycles.samples < 64 and not sc.cycles.use_denoising:
        add("R2", "M", "low samples without denoising", fix="hz.render_settings()")

    penalty = sum(WEIGHT[f["sev"]] for f in findings)
    score = max(0, 100 - penalty)
    result = {"score": score, "meshes": len(meshes), "lights": len(lights), "findings": findings}
    if as_json:
        print("BLUERSKILL_JSON " + json.dumps(result))
    else:
        print("\n=== bluerskill audit ===")
        print(f"score: {score}/100   (meshes {len(meshes)}, lights {len(lights)})   target ≥ 85")
        order = {"H": 0, "M": 1, "L": 2}
        for f in sorted(findings, key=lambda f: order[f["sev"]]):
            objs = f" [{', '.join(f['objects'])}]" if f["objects"] else ""
            print(f"  {f['sev']} {f['id']:<3} {f['msg']}{objs}")
            if f["fix"]:
                print(f"         fix: {f['fix']}")
        if not findings:
            print("  no automated tells found — now check the Story section by eye.")
        print("Automated checks can't judge story, shape rhythm, or reference fidelity: render and look.\n")
    return result


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    run(as_json="--json" in argv)
