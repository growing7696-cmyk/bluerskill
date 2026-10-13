"""Worked example: the same brief built the "AI default" way and the bluerskill way.

    blender -b --factory-startup --python mug_still_life.py -- --out mug.blend          # bluerskill
    blender -b --factory-startup --python mug_still_life.py -- --out slop.blend --slop  # typical AI output

READ:  diner coffee mug on a cafe table for a mood still, photoreal, quiet morning
REFS:  1990s American diner ironstone mug (thick wall, cream glaze, chipped rim);
       cork coaster; oiled oak table top; low window light from the left
DIALS: WEAR 4 / STYLIZATION 0 / CLUTTER 3
SCALE: mug 0.095 m tall, Ø 0.084 m
"""

import os
import sys
import math

import bpy
import bmesh

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import humanize as hz  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else "mug.blend"
SLOP = "--slop" in argv


def _profile_radius(t, radius):
    """Outer radius at normalized height t: slight belly, narrower foot. Real mugs aren't cylinders."""
    return radius * (0.9 + 0.1 * math.sin(math.pi * min(t * 1.6, 1) / 2) + 0.025 * math.sin(math.pi * t))


def build_mug(radius=0.042, height=0.095, wall=0.0055, segments=64):
    """Lathed mug body with a flat foot ring + bisected handle, modeled at real size (origin at the base)."""
    rings = 18
    prof = [(0.0, 0.0), (radius * 0.72, 0.0), (radius * 0.80, 0.0015)]
    prof += [(_profile_radius(i / rings, radius), 0.003 + (height - 0.003) * i / rings) for i in range(1, rings + 1)]
    bm = bmesh.new()
    verts = [bm.verts.new((r, 0, z)) for r, z in prof]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi,
                   steps=segments, use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("Mug")
    bm.to_mesh(me)
    bm.free()
    body = bpy.data.objects.new("Mug", me)
    bpy.context.scene.collection.objects.link(body)
    hz.solidify(body, wall)
    hz.bevel(body, width=0.0018, segments=3, angle_deg=40)   # rounded rim + foot, no subsurf shrink

    z_mid = height * 0.52
    r_mid = _profile_radius(z_mid / height, radius)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.024, minor_radius=0.0062, major_segments=48,
                                     minor_segments=16, location=(r_mid + 0.011, 0, z_mid),
                                     rotation=(math.radians(90), 0, 0))
    handle = bpy.context.active_object
    handle.name = "Mug_handle"
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bm = bmesh.new()
    bm.from_mesh(handle.data)
    for v in bm.verts:  # oval grip, slightly asymmetric top/bottom
        v.co.z *= 1.18 if v.co.z > 0 else 1.08
    # clean planar cut so the open ends sit inside the wall instead of a sawtooth of deleted verts
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                           plane_co=(r_mid - wall * 0.5 - handle.location.x, 0, 0), plane_no=(1, 0, 0),
                           clear_inner=True)
    bm.to_mesh(handle.data)
    bm.free()
    hz.shade_smooth(handle)
    handle.parent = body

    bpy.ops.mesh.primitive_cylinder_add(vertices=segments, depth=0.002, location=(0, 0, height * 0.8),
                                        radius=_profile_radius(0.8, radius) - wall * 1.05)
    coffee = bpy.context.active_object
    coffee.name = "Coffee"
    coffee.parent = body
    hz.shade_smooth(coffee)
    return body, handle, coffee


def bluerskill():
    hz.remove_startup()
    table = hz.make_surface(0.9, 0.6, 0.035, "light_wood", color="#8a6c52", name="Table", wear=4)
    table.rotation_euler.z = math.radians(4)
    # context: a plaster wall behind, so the frame isn't an infinite void
    wall = hz.make_surface(2.0, 1.3, 0.04, "plaster", color="#cfc6b8", name="Wall", wear=2)
    wall.rotation_euler.x = math.radians(90)
    wall.location = (0.1, 0.55, 0.62)

    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.05, depth=0.004, location=(-0.04, 0.03, 0))
    coaster = bpy.context.active_object
    coaster.name = "Coaster"
    hz.bevel(coaster, wear=4)
    cork = hz.physical_material("terracotta", color="#8f6440", name="Cork", roughness=0.9)
    hz.assign(coaster, cork)
    hz.add_breakup(cork, size=0.01, amount=0.18)
    hz.add_bump(cork, feature=0.0008, kind="leather", strength=0.6)   # granulated cork
    hz.ground(coaster)

    body, handle, coffee = build_mug()
    body.location = (-0.035, 0.035, 0)
    body.rotation_euler = (math.radians(0.6), math.radians(-0.4), math.radians(28))
    glaze = hz.physical_material("glazed_ceramic", color="#e3d6bd", name="Ironstone_glaze")
    for o in (body, handle):
        hz.assign(o, glaze)
    hz.add_breakup(glaze, size=0.1, amount=0.06)
    hz.add_wear(glaze, strength=0.4, size=0.1)
    hz.add_bump(glaze, feature=0.005, kind="orange_peel")            # dipped glaze ripple
    brew = hz.physical_material("plastic", color="#2a170c", name="Coffee", roughness=0.04)
    hz.assign(coffee, brew)
    hz.bevel(coffee, width=0.0008, segments=2)          # meniscus, not a razor disc
    hz.add_breakup(brew, size=0.05, amount=0.0, rough_spread=0.03)  # faint surface film
    hz.add_bump(brew, feature=0.012, kind="noise", depth=0.00005)    # barely-there ripple
    bpy.context.view_layer.update()
    hz.ground(body, others=[coaster])

    # sugar cubes: a few, not a row; each one different
    cubes = []
    for i, (x, y) in enumerate([(0.045, -0.055), (0.062, -0.041), (0.03, -0.072)]):
        bpy.ops.mesh.primitive_cube_add(size=0.013, location=(x, y, 0.0065))
        c = bpy.context.active_object
        c.name = f"Sugar_{i}"
        hz.bevel(c, wear=6, segments=2)
        cubes.append(c)
    hz.jitter(cubes, rot_deg=(4, 4, 40), scale=0.08, seed=3)
    cubes[2].rotation_euler.x += math.radians(90)  # one tipped over
    sugar = hz.physical_material("paper", color="#efeae0", name="Sugar", roughness=0.8)
    hz.add_breakup(sugar, size=0.013, amount=0.05)
    hz.add_bump(sugar, feature=0.0006, kind="hammered", depth=0.0002)  # pressed crystals
    for c in cubes:
        hz.assign(c, sugar)
    bpy.context.view_layer.update()
    for c in cubes:
        hz.ground(c, others=[table])

    hz.light_rig("window", target=body)
    hz.camera_rig(body, lens=70, azimuth_deg=-70, elevation_deg=17, fstop=3.2,
                  frame_offset=(0.12, 0.06), fill=0.42)
    hz.color_management("AgX - Medium High Contrast")
    hz.render_settings(samples=128, resolution=(1600, 1200))


def slop():
    """What a typical first-pass AI bpy script produces. Do not imitate."""
    bpy.ops.mesh.primitive_plane_add(size=4)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=1.2, location=(0, 0, 0.6))
    mug = bpy.context.active_object
    m = bpy.data.materials.new("Red")
    principled = next(n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    principled.inputs["Base Color"].default_value = (1, 0, 0, 1)
    mug.data.materials.append(m)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.3, minor_radius=0.06, location=(0.55, 0, 0.6),
                                     rotation=(math.radians(90), 0, 0))
    for i in range(3):
        bpy.ops.mesh.primitive_cube_add(size=0.2, location=(1.2, -0.6 + i * 0.4, 0.1))
    bpy.context.scene.view_settings.view_transform = "Standard"


slop() if SLOP else bluerskill()
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OUT))
print("saved", os.path.abspath(OUT))
