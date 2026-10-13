"""Worked example: a hard-surface hero prop built the bluerskill way.

    blender -b --factory-startup --python rifle_prop.py -- --out rifle.blend

READ:  generic walnut-stocked bolt-action hunting rifle as a still-life prop, photoreal
REFS:  classic sporter stock (straight comb, rounded pistol grip, schnabel-less fore-end);
       blued steel round receiver + tapered sporter barrel; 1" matte scope; .308-class cartridges;
       resting on a canvas gun mat on a workbench, window light
DIALS: WEAR 3 / STYLIZATION 0 / CLUTTER 3
SCALE: overall length ≈ 1.10 m, barrel 0.56 m, length of pull ≈ 0.34 m

Reference sheet (meters, bore axis = X, z = 0 at bore center, butt at x = 0):
    stock     x 0.00–0.735   depth 0.170 at butt   thickness 0.042
    receiver  x 0.315–0.545  Ø 0.033
    barrel    x 0.545–1.100  Ø 0.029 → 0.017 at muzzle
    scope     x 0.29–0.63    tube Ø 0.0254, objective bell Ø 0.050, axis z = 0.048

Construction choice per part (how the real thing is made):
    stock = profile_extrude (sawn from a blank, edges rounded)   barrel/scope/receiver = lathe (turned)
    trigger guard / bolt handle / trigger = sweep (bent and forged rod)
    floorplate / ring bases = rounded_box (machined)   ejection port = cut   ring screws = screw
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
OUT = argv[argv.index("--out") + 1] if "--out" in argv else "rifle.blend"


def materials():
    walnut = hz.physical_material("dark_wood", color="#4d3727", name="Walnut", roughness=0.42)
    p = hz.principled(walnut)
    p.inputs["Coat Weight"].default_value = 0.35
    p.inputs["Coat Roughness"].default_value = 0.18
    hz.add_grain(walnut, spacing=0.004, along="X", contrast=0.65, late_wood=(0.32, 0.2, 0.13))
    hz.add_breakup(walnut, size=0.4, amount=0.05)
    hz.add_wear(walnut, strength=0.25, size=0.15, edge_tint=hz.srgb("#8a6040"))
    hz.add_bump(walnut, feature=0.0007, kind="pores", along="X")       # open pores under the oil finish

    blued = hz.physical_material("steel", color="#30343b", name="Blued_steel", roughness=0.3)
    hz.add_breakup(blued, size=0.3, amount=0.05)
    hz.add_wear(blued, strength=0.3, size=0.05, grime=(0.03, 0.025, 0.02), edge_tint=(0.55, 0.56, 0.57, 1))
    hz.add_scratches(blued, size=0.12, density=0.4, strength=0.35)       # holster/handling marks
    hz.add_bump(blued, feature=0.0015, kind="noise", strength=0.3)

    anod = hz.physical_material("plastic", color="#141516", name="Anodized_black", roughness=0.32)
    hz.principled(anod).inputs["Specular IOR Level"].default_value = 0.15
    hz.add_breakup(anod, size=0.2, amount=0.03)
    # thin convex tube: keep the wear size small or the whole surface counts as "edge" and turns gray
    hz.add_wear(anod, strength=0.15, size=0.006, edge_tint=hz.srgb("#3a3b3d"))
    hz.add_bump(anod, feature=0.0006, kind="noise", strength=0.25)      # bead-blasted before anodizing

    ebony = hz.physical_material("dark_wood", color="#140e0b", name="Ebony", roughness=0.38)
    hz.principled(ebony).inputs["Coat Weight"].default_value = 0.0
    hz.add_breakup(ebony, size=0.05, amount=0.08)
    hz.add_bump(ebony, feature=0.0005, kind="pores", along="X", strength=0.5)
    spacer = hz.physical_material("plastic", color="#e6e1d6", name="Spacer_white", roughness=0.35)
    hz.add_breakup(spacer, size=0.05, amount=0.04)
    hz.add_bump(spacer, feature=0.003, kind="orange_peel")
    rubber = hz.physical_material("rubber", name="Butt_pad_rubber")
    hz.add_breakup(rubber, size=0.1, amount=0.05)
    hz.add_bump(rubber, feature=0.0012, kind="leather")                 # stippled recoil pad

    lens = hz.physical_material("glass", name="Lens")
    hz.principled(lens).inputs["Thin Film Thickness"].default_value = 320  # coated-lens tint
    hz.add_breakup(lens, size=0.04, amount=0.0, rough_spread=0.02)  # faint smudges

    brass = hz.physical_material("brass", name="Brass", roughness=0.22)
    hz.add_breakup(brass, size=0.05, amount=0.08)
    hz.add_scratches(brass, size=0.04, density=0.6, strength=0.4)      # chambered once: extractor marks
    copper = hz.physical_material("copper", name="Copper_jacket", roughness=0.25)
    hz.add_breakup(copper, size=0.05, amount=0.06)
    hz.add_bump(copper, feature=0.001, kind="noise", strength=0.3)
    return dict(ebony=ebony, spacer=spacer, walnut=walnut, blued=blued, anod=anod, rubber=rubber, lens=lens, brass=brass, copper=copper)


def build_rifle(M):
    parts = []

    # ---- Stock: side silhouette with per-corner radii, then rounded edges
    stock_pts = [
        (0.000, -0.030), (0.205, -0.019), (0.300, -0.012), (0.700, -0.012), (0.700, -0.042),
        (0.520, -0.047), (0.470, -0.051), (0.330, -0.050), (0.300, -0.068),
        (0.284, -0.118), (0.246, -0.124), (0.222, -0.096), (0.175, -0.088), (0.000, -0.170),
    ]
    stock_r = [0.004, 0.06, 0.02, 0, 0, 0.03, 0.01, 0.012, 0.035, 0.007, 0.012, 0.03, 0.09, 0.004]
    # edge_round ≈ 43 % of thickness: rounded cross-section, not a plank cutout
    stock = sh.profile_extrude("Stock", stock_pts, 0.042, radii=stock_r, segments=10, edge_round=0.011,
                               edge_segments=6, crown=0.0045, crown_width=0.016)
    hz.assign(stock, M["walnut"])
    parts.append(stock)
    # contrasting fore-end tip and white-line spacers: the joins are where craft shows
    tip = sh.profile_extrude("Forend_tip", [(0.699, -0.0125), (0.722, -0.0125), (0.737, -0.025),
                                            (0.723, -0.0415), (0.699, -0.0415)],
                             0.039, radii=[0, 0.004, 0.012, 0.01, 0], edge_round=0.01, edge_segments=6,
                             crown=0.003, crown_width=0.008)
    hz.assign(tip, M["ebony"])
    parts.append(tip)
    spacer = sh.rounded_box("Pad_spacer", (0.0022, 0.040, 0.139), radius=0.0009, location=(-0.0011, 0, -0.1))
    pad = sh.rounded_box("Butt_pad", (0.019, 0.042, 0.141), radius=0.012, location=(-0.0115, 0, -0.1))
    hz.assign(spacer, M["spacer"])
    hz.assign(pad, M["rubber"])
    parts += [spacer, pad]

    # ---- Receiver: turned cylinder with chamfered ends + ejection port + tang
    L = 0.23
    rec = sh.lathe("Receiver", [(0, 0), (0.0145, 0), (0.0165, 0.003), (0.0165, L - 0.004), (0.015, L),
                                (0, L)], segments=64, axis="X", location=(0.315, 0, 0))
    port = sh.rounded_box("port", (0.07, 0.03, 0.022), radius=0.003, location=(0.47, 0.016, 0.004))
    sh.cut(rec, port)
    hz.assign(rec, M["blued"])
    parts.append(rec)

    bolt = sh.lathe("Bolt_body", [(0, 0), (0.0085, 0), (0.0085, 0.08), (0, 0.08)], segments=32, axis="X",
                    location=(0.44, 0.0, 0.004))
    hz.assign(bolt, M["blued"])
    parts.append(bolt)
    handle = sh.sweep("Bolt_handle", [(0.405, 0.012, 0.002), (0.400, 0.032, -0.004), (0.388, 0.047, -0.020),
                                      (0.382, 0.052, -0.030)], 0.0046, radii=[1.0, 0.85, 0.75, 0.7])
    knob = sh.lathe("Bolt_knob", [(0, -0.009), (0.005, -0.0085), (0.0085, -0.004), (0.0092, 0.001),
                                  (0.0075, 0.006), (0.004, 0.0085), (0, 0.009)], segments=32,
                    location=(0.381, 0.054, -0.034))
    knob.rotation_euler.x = math.radians(25)
    for o in (handle, knob):
        hz.assign(o, M["blued"])
        parts.append(o)

    # ---- Barrel: tapered, with muzzle crown and bore
    B0, BL = 0.545, 0.555
    barrel = sh.lathe("Barrel", [
        (0, 0), (0.0145, 0), (0.0145, 0.03), (0.0125, 0.075), (0.0112, 0.2), (0.0092, BL - 0.004),
        (0.0085, BL), (0.0060, BL), (0.0042, BL - 0.0015), (0.0035, BL - 0.0015), (0.0035, BL - 0.04),
        (0, BL - 0.04)], segments=64, axis="X", location=(B0, 0, 0))
    hz.assign(barrel, M["blued"])
    parts.append(barrel)

    # ---- Trigger guard, trigger, floorplate
    guard = sh.sweep("Trigger_guard", [(0.402, 0, -0.050), (0.398, 0, -0.072), (0.375, 0, -0.084),
                                       (0.345, 0, -0.078), (0.328, 0, -0.060), (0.326, 0, -0.050)], 0.0032)
    guard.scale.y = 2.2
    hz.apply_scale(guard)
    trigger = sh.sweep("Trigger", [(0.372, 0, -0.046), (0.370, 0, -0.060), (0.362, 0, -0.072)], 0.0028,
                       radii=[1.0, 0.85, 0.7])
    trigger.scale.y = 1.6
    hz.apply_scale(trigger)
    floor = sh.rounded_box("Floorplate", (0.12, 0.028, 0.005), radius=0.002, location=(0.465, 0, -0.050))
    for o in (guard, trigger, floor):
        hz.assign(o, M["blued"])
        parts.append(o)

    # ---- Sling swivels (stud + loop)
    for i, (x, z) in enumerate([(0.085, -0.130), (0.655, -0.045)]):
        stud = sh.lathe(f"Swivel_stud_{i}", [(0, 0), (0.004, 0), (0.0035, -0.008), (0, -0.008)], segments=24,
                        location=(x, 0, z + 0.002))
        loop = sh.sweep(f"Swivel_loop_{i}", [(x - 0.012, 0, z - 0.008), (x - 0.010, 0, z - 0.018),
                                             (x, 0, z - 0.021), (x + 0.010, 0, z - 0.018),
                                             (x + 0.012, 0, z - 0.008)], 0.0016)
        loop.rotation_euler.x = math.radians(18 if i == 0 else -12)  # hanging, not posed
        for o in (stud, loop):
            hz.assign(o, M["blued"])
            parts.append(o)

    # ---- Scope: tube, bells, turrets, lens; rings with screws
    SZ = 0.048
    scope = sh.lathe("Scope", [
        (0, 0), (0.0175, 0), (0.0195, 0.002), (0.0195, 0.045), (0.0127, 0.085), (0.0127, 0.235),
        (0.0245, 0.29), (0.025, 0.336), (0.0235, 0.34), (0.021, 0.34), (0.021, 0.335), (0, 0.335)],
        segments=96, axis="X", location=(0.29, 0, SZ))
    hz.assign(scope, M["anod"])
    parts.append(scope)
    glass = sh.lathe("Objective_lens", [(0, 0), (0.0208, 0), (0.0208, 0.002), (0, 0.003)], segments=64,
                     axis="X", location=(0.29 + 0.333, 0, SZ))
    eyepiece = sh.lathe("Ocular_lens", [(0, 0.003), (0.0165, 0.002), (0.0165, 0), (0, 0)], segments=64,
                        axis="X", location=(0.288, 0, SZ))
    for o in (glass, eyepiece):
        hz.assign(o, M["lens"])
        parts.append(o)
    for name, axis, loc in [("Turret_elev", "Z", (0.455, 0, SZ + 0.012)),
                            ("Turret_wind", "Y", (0.455, 0.012, SZ))]:
        t = sh.lathe(name, [(0, 0), (0.0115, 0), (0.0115, 0.006), (0.012, 0.0065), (0.012, 0.016),
                            (0.0105, 0.018), (0, 0.018)], segments=48, axis=axis, location=loc)
        hz.assign(t, M["anod"])
        parts.append(t)
    for i, x in enumerate([0.375, 0.515]):
        ring = sh.lathe(f"Scope_ring_{i}", [(0.0127, 0), (0.0172, 0), (0.0178, 0.001), (0.0178, 0.011),
                                            (0.0172, 0.012), (0.0127, 0.012)], segments=64, axis="X",
                        location=(x, 0, SZ))
        base = sh.rounded_box(f"Ring_base_{i}", (0.012, 0.02, 0.022), radius=0.002,
                              location=(x + 0.006, 0, 0.026))
        scr = sh.screw(f"Ring_screw_{i}", location=(x + 0.006, 0.0177, SZ + 0.0115), normal=(0, 1, 0),
                       radius=0.0022)
        for o in (ring, base, scr):
            hz.assign(o, M["anod"])
            parts.append(o)

    return sh.group(parts, "Rifle")


def cartridge(name, M, location, rot):
    """.308-class cartridge: brass case (rim, extractor groove, shoulder, neck) + copper bullet."""
    case = sh.lathe(name + "_case", [
        (0, 0), (0.0059, 0), (0.0060, 0.0005), (0.0060, 0.0013), (0.0050, 0.0018), (0.0050, 0.0030),
        (0.0059, 0.0040), (0.0058, 0.039), (0.0053, 0.0415), (0.0044, 0.0435), (0.0044, 0.0515),
        (0.0040, 0.0515), (0, 0.0515)], segments=48)
    bullet = sh.lathe(name + "_bullet", [
        (0, 0.048), (0.0039, 0.048), (0.0039, 0.057), (0.0033, 0.064), (0.0019, 0.0695), (0.0006, 0.0712),
        (0, 0.0713)], segments=48)
    hz.assign(case, M["brass"])
    hz.assign(bullet, M["copper"])
    g = sh.group([case, bullet], name)
    g.location = location
    g.rotation_euler = rot
    return g


def scene():
    hz.remove_startup()
    M = materials()
    bench = hz.make_surface(2.6, 1.5, 0.05, "light_wood", color="#7a5f48", name="Workbench", wear=5, planks=0.15)
    mat = hz.make_surface(1.3, 0.42, 0.006, "canvas", color="#4f4d38", name="Canvas_mat", wear=4,
                          location=(0.04, -0.03), z_top=0.006)
    mat.rotation_euler.z = math.radians(-3)

    rifle = build_rifle(M)
    sh.check_dims(rifle, (1.11, 0.09, 0.245), tol=0.15)
    # lie it on its left side (bolt handle up), slightly angled on the mat
    rifle.rotation_euler = (math.radians(90), 0, math.radians(16))
    rifle.location = (-0.52, 0.02, 0)
    sh.ground_assembly(rifle, floor_z=0.006)

    rounds = [cartridge(f"Round_{i}", M, loc, rot) for i, (loc, rot) in enumerate([
        ((0.27, 0.13, 0.006), (0, 0, 0)),
        ((0.305, 0.15, 0.006), (0, 0, 0)),
        ((0.345, 0.11, 0.0125), (math.radians(90), 0, math.radians(-35))),  # one lying down
    ])]
    for r in rounds:
        sh.ground_assembly(r, floor_z=0.006)
    hz.jitter([rounds[0], rounds[1]], rot_deg=(0, 0, 30), seed=4)

    # camera on the bolt-handle side: grip down, scope up — the rifle reads the right way up
    # key ~50° off the camera, from behind the stock: the barrel and scope catch the window as a
    # highlight line, the stock's crown shades from light to dark across its width
    hz.light_rig("window", target=rifle, key_azimuth=120, intensity=1.4)
    hz.camera_rig(rifle, lens=85, azimuth_deg=70, elevation_deg=30, fstop=5.6,
                  frame_offset=(0.0, 0.0), fill=1.05)
    hz.color_management("AgX - High Contrast", exposure=0.2)   # look.py: R5 cleared, not washed out
    hz.render_settings(samples=160, resolution=(1800, 1000))


scene()
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OUT))
print("saved", os.path.abspath(OUT))
