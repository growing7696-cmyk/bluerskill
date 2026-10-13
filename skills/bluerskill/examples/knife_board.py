"""Worked example: organic + soft forms — loft, drape, weave, scratches, HDRI reflections.

    blender -b --factory-startup --python knife_board.py -- --out knife.blend

READ:  chef's knife on a maple board after prep, photoreal kitchen still life, quiet late morning
REFS:  21 cm German-pattern chef's knife (full tang, three brass-free steel rivets, oiled walnut
       handle, satin stainless blade with a polished edge bevel); edge-grain maple board, years of
       knife marks; washed linen tea towel with a woven red stripe, dropped over the board's corner;
       honed dark concrete counter; small glazed salt dish
DIALS: WEAR 4 / STYLIZATION 0 / CLUTTER 3
SCALE: knife 0.335 m overall, board 0.40 × 0.28 × 0.03 m

Reference sheet (meters, knife built along +X, blade face = XZ plane, heel of edge at origin):
    blade     x 0.000–0.212   heel height 0.048   spine 0.0024, ground to ~0.0003 at the edge
    bolster   x -0.012–0.002  height 0.040   thickness 0.012
    handle    x -0.125–-0.010 height 0.022–0.028  width 0.016–0.020, palm swell at x ≈ -0.07
    rivets    Ø 0.0048 at x = -0.030, -0.062, -0.095
    board     0.40 × 0.28 × 0.03, edge-grain strips 0.04 wide
    towel     0.42 × 0.30 linen, ~0.6 mm thread

Construction choice per part:
    blade = profile_extrude (cut from sheet, then ground: thickness tapers toward the edge)
    handle = loft (shaped by hand: section changes along its length — a lathe or extrusion can't)
    bolster = profile_extrude + crown   rivets = lathe   salt dish = lathe
    towel = drape (cloth sim onto board + counter)   board = make_surface(planks=...)
"""

import os
import sys
import math

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import humanize as hz  # noqa: E402
import shapes as sh  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else "knife.blend"


def materials():
    steel = hz.physical_material("stainless", name="Blade_steel", roughness=0.24)
    hz.add_breakup(steel, size=0.1, amount=0.0, rough_spread=0.03)
    hz.add_scratches(steel, size=0.08, density=0.5, strength=0.3)     # sharpening + board contact
    hz.add_bump(steel, feature=0.0004, kind="noise", strength=0.2)

    walnut = hz.physical_material("oiled_walnut", color="#4a3022", name="Handle_walnut")
    hz.add_grain(walnut, spacing=0.0016, along="X", contrast=0.5, late_wood=(0.35, 0.22, 0.15))
    hz.add_breakup(walnut, size=0.08, amount=0.06)
    hz.add_wear(walnut, strength=0.35, size=0.02, edge_tint=hz.srgb("#7a5338"))  # palm polish
    hz.add_bump(walnut, feature=0.0005, kind="pores", along="X")

    rivet = hz.physical_material("stainless", name="Rivet_steel", roughness=0.3)
    hz.add_breakup(rivet, size=0.01, amount=0.0)
    hz.add_bump(rivet, feature=0.0003, kind="noise", strength=0.3)

    glaze = hz.physical_material("glazed_ceramic", color="#3f5d63", name="Dish_glaze")
    hz.add_breakup(glaze, size=0.06, amount=0.1)
    hz.add_bump(glaze, feature=0.004, kind="orange_peel")

    salt = hz.physical_material("white_paint", color="#e9e6df", name="Salt", roughness=0.55)
    hz.add_breakup(salt, size=0.05, amount=0.03)
    hz.add_bump(salt, feature=0.0009, kind="hammered", depth=0.0003)   # crystals

    linen = hz.physical_material("linen", color="#cbc3b2", name="Towel_linen")
    stripe(linen)
    hz.add_weave(linen, thread=0.0006, fuzz=0.35, uv=True)
    hz.add_breakup(linen, size=0.3, amount=0.06)
    return dict(steel=steel, walnut=walnut, rivet=rivet, glaze=glaze, salt=salt, linen=linen)


def stripe(mat):
    """Woven red stripe near one end of the towel, in UV meters so it bends with the folds."""
    nt = mat.node_tree
    p = hz.principled(mat)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["UV"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")   # x position (m) -> stripe mask
    e = ramp.color_ramp.elements
    ramp.color_ramp.interpolation = "LINEAR"
    e[0].position, e[0].color = 0.0, (0, 0, 0, 1)
    e[1].position, e[1].color = 1.0, (0, 0, 0, 1)
    for pos, v in ((0.840, 0), (0.843, 1), (0.900, 1), (0.903, 0), (0.915, 0), (0.918, 1), (0.930, 1), (0.933, 0)):
        el = e.new(pos)
        el.color = (v, v, v, 1)
    off = nt.nodes.new("ShaderNodeMath")        # UV x is -0.21..0.21 m -> 0..1 along the towel
    off.operation = "MULTIPLY_ADD"
    off.inputs[1].default_value = 1 / 0.42
    off.inputs[2].default_value = 0.5
    nt.links.new(sep.outputs["X"], off.inputs[0])
    nt.links.new(off.outputs[0], ramp.inputs["Fac"])
    mix = hz._mix_rgba(nt)
    nt.links.new(ramp.outputs["Color"], hz._sock(mix.inputs, "Factor_Float"))
    hz._sock(mix.inputs, "A_Color").default_value = p.inputs["Base Color"].default_value[:]
    hz._sock(mix.inputs, "B_Color").default_value = hz.srgb("#9b3a2e")
    nt.links.new(hz._sock(mix.outputs, "Result_Color"), p.inputs["Base Color"])


# handle stations along the knife: (center, width across, height, squareness)
HANDLE = [
    ((-0.010, 0, 0.0320), 0.0150, 0.0300, 0.65),
    ((-0.035, 0, 0.0315), 0.0180, 0.0240, 0.55),
    ((-0.070, 0, 0.0310), 0.0200, 0.0262, 0.50),
    ((-0.105, 0, 0.0320), 0.0190, 0.0275, 0.55),
    ((-0.124, 0, 0.0345), 0.0170, 0.0250, 0.62),
]


def build_knife(M):
    parts = []
    # ---- Blade: side silhouette, then grind the thickness down toward the edge
    blade_pts = [(0.000, 0.000), (0.110, 0.000), (0.160, 0.003), (0.192, 0.010), (0.212, 0.021),
                 (0.185, 0.030), (0.120, 0.042), (0.040, 0.048), (0.000, 0.048)]
    blade_r = [0.0015, 0.08, 0.06, 0.02, 0.0012, 0.08, 0.1, 0.03, 0.001]
    # a whisper of crown just to tessellate the flat sides, so the grind below can taper them
    blade = sh.profile_extrude("Blade", blade_pts, 0.0024, radii=blade_r, segments=10, edge_round=0.0004,
                               edge_segments=2, crown=0.00001, crown_width=0.004)
    edge_z = lambda x: 0.0 if x < 0.11 else 0.021 * ((x - 0.11) / 0.102) ** 2.2
    for v in blade.data.vertices:   # full-height flat grind: thick at the spine, ~0.3 mm at the edge
        x, z = v.co.x, v.co.z
        t = max(0.0, min(1.0, (z - edge_z(x)) / max(0.048 - edge_z(x), 1e-4)))
        v.co.y *= 0.12 + 0.88 * t ** 0.8
        if x > 0.15:   # distal taper: the tip is thinner than the heel
            v.co.y *= 1 - 0.45 * (x - 0.15) / 0.062
    hz.assign(blade, M["steel"])
    parts.append(blade)

    bolster = sh.profile_extrude("Bolster", [(-0.012, 0.016), (0.003, 0.006), (0.003, 0.048), (-0.012, 0.046)],
                                 0.012, radii=[0.003, 0.004, 0.002, 0.003], edge_round=0.003, crown=0.0015,
                                 crown_width=0.004)
    hz.assign(bolster, M["steel"])
    parts.append(bolster)

    # ---- Handle: loft — palm swell, narrower at the bolster, flared butt that tips upward
    handle = sh.loft("Handle", HANDLE, ring=40, end_round=(0.0, 0.5))
    hz.assign(handle, M["walnut"])
    parts.append(handle)
    # full tang: a steel plate through the handle, proud by 0.3 mm, so it shows as a line on top/bottom
    top = [(x, z + h / 2 + 0.0003) for (x, _, z), _, h, _ in HANDLE[:-1]]
    bot = [(x, z - h / 2 - 0.0003) for (x, _, z), _, h, _ in HANDLE[:-1]]
    tang = sh.profile_extrude("Tang", top + bot[::-1], 0.0024, radii=0.002, edge_round=0.0003, edge_segments=2)
    hz.assign(tang, M["rivet"])
    parts.append(tang)
    for i, x in enumerate((-0.030, -0.062, -0.095)):
        r = sh.lathe(f"Rivet_{i}", [(0, -0.0104), (0.0024, -0.0104), (0.0024, 0.0104), (0, 0.0104)],
                     segments=32, axis="Y", location=(x, 0, 0.0315), edge_round=0.0003)
        hz.assign(r, M["rivet"])
        parts.append(r)
    return sh.group(parts, "Knife")


def build_dish(M):
    dish = sh.lathe("Salt_dish", [(0, 0), (0.028, 0), (0.030, 0.002), (0.034, 0.012), (0.038, 0.026),
                                  (0.0395, 0.0285), (0.037, 0.029), (0.033, 0.014), (0.027, 0.006), (0, 0.006)],
                    segments=72)
    hz.assign(dish, M["glaze"])
    salt = sh.lathe("Salt", [(0, 0.0125), (0.012, 0.0122), (0.025, 0.0105), (0.031, 0.009), (0.031, 0.006),
                             (0, 0.006)], segments=48)
    hz.assign(salt, M["salt"])
    return sh.group([dish, salt], "Salt_dish_group")


def scene():
    hz.remove_startup()
    M = materials()
    counter = hz.make_surface(2.2, 1.4, 0.04, "concrete", color="#3b3a38", name="Counter", wear=3,
                              location=(0.1, 0.3))
    board = hz.make_surface(0.40, 0.28, 0.03, "end_grain_maple", color="#b48a5c", name="Board",
                            wear=5, planks=0.04, glued=True, z_top=0.03, location=(0.0, 0.0), seed=4)
    board.rotation_euler.z = math.radians(-7)

    # towel first, so it lands on the board and spills over its front-right corner onto the counter
    towel = sh.drape("Towel", (0.42, 0.30), location=(0.20, -0.13, 0.075), colliders=[board, counter],
                     subdiv=(84, 60), frames=80, thickness=0.0012, stiffness=0.8, crumple=0.15,
                     rotation_deg=24, seed=3)
    hz.assign(towel, M["linen"])

    knife = build_knife(M)
    sh.check_dims(knife, (0.336, 0.020, 0.048), tol=0.12)
    # lying on its flat side; tilted so the tip and the handle's side both touch the board
    knife.rotation_euler = (math.radians(90), math.radians(1.6), math.radians(-18))
    knife.location = (-0.07, 0.03, 0)
    sh.ground_assembly(knife, floor_z=0.03)

    dish = build_dish(M)
    dish.location = (-0.33, 0.20, 0)
    sh.ground_assembly(dish, floor_z=0.0)

    # key near the blade's mirror angle (camera azimuth + 180°): the flat of the blade catches the
    # window as one soft highlight — that is what tells you it's polished steel and not gray paint
    hz.light_rig("window", target=board, key_azimuth=118)
    hz.camera_rig(board, lens=60, azimuth_deg=-75, elevation_deg=34, fstop=4.0,
                  frame_offset=(0.06, 0.02), fill=0.72)
    cam = bpy.context.scene.camera
    cam.data.dof.focus_object = bpy.data.objects["Blade"]   # focus on the blade, not the board center
    hz.color_management("AgX - Medium High Contrast", exposure=0.2)
    hz.render_settings(samples=192, resolution=(1600, 1000))


scene()
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OUT))
print("saved", os.path.abspath(OUT))
