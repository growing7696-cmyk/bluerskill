"""bluerskill modeling library — build real forms instead of stacking primitives.

Every hard-surface object is one of a few constructions. Pick the one that matches how the
real thing is manufactured, and you get a believable silhouette for free:

    profile_extrude  flat-silhouette parts: stocks, blades, brackets, tools, furniture panels
    lathe            turned / round parts: barrels, bottles, cups, knobs, lenses, cartridges
    sweep            tubes and bent rod: handles, trigger guards, cables, pipes, frames
    rounded_box      machined blocks: receivers, housings, buttons, bases
    cut / union      boolean details: ports, slots, holes, grooves (always beveled afterwards)
    screw            tertiary detail that sells scale

    import sys; sys.path.insert(0, "<skill>/scripts")
    import shapes as sh, humanize as hz

Units are meters. All builders return a mesh object with scale applied.
"""

import math

import bpy
import bmesh
from mathutils import Vector, Matrix

_AXIS_ROT = {
    "Z": Matrix.Identity(4),
    "X": Matrix.Rotation(math.radians(90), 4, "Y"),   # local +Z -> world +X
    "Y": Matrix.Rotation(math.radians(-90), 4, "X"),  # local +Z -> world +Y
}


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


def _link(name, me, location=(0, 0, 0)):
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    return obj


def _smooth(me, angle_deg=35):
    """Smooth shading with crisp edges above angle_deg (Blender 4.1+ / fallback)."""
    if hasattr(me, "shade_smooth"):
        me.shade_smooth()
    else:
        for p in me.polygons:
            p.use_smooth = True
    if hasattr(me, "set_sharp_from_angle"):
        me.set_sharp_from_angle(angle=math.radians(angle_deg))


def _active(obj):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


# --------------------------------------------------------------------------- #
# 2D helpers
# --------------------------------------------------------------------------- #


def fillet_polygon(points, radii=0.0, segments=6):
    """Round the corners of a closed 2D polygon.

    points: [(u, v), ...] in order. radii: one float for all corners or a list per corner
    (0 keeps the corner sharp). Radii are clamped so arcs never overlap.
    """
    n = len(points)
    if not isinstance(radii, (list, tuple)):
        radii = [radii] * n
    pts = [Vector(p) for p in points]
    out = []
    for i in range(n):
        p, a, b = pts[i], pts[i - 1], pts[(i + 1) % n]
        r = radii[i]
        d1, d2 = (a - p), (b - p)
        l1, l2 = d1.length, d2.length
        if r <= 0 or l1 < 1e-9 or l2 < 1e-9:
            out.append(p.copy())
            continue
        d1.normalize()
        d2.normalize()
        theta = d1.angle(d2)
        if theta < 1e-3 or abs(theta - math.pi) < 1e-3:
            out.append(p.copy())
            continue
        t = r / math.tan(theta / 2)
        t_max = 0.48 * min(l1, l2)
        if t > t_max:
            t = t_max
            r = t * math.tan(theta / 2)
        t1, t2 = p + d1 * t, p + d2 * t
        bis = (d1 + d2).normalized()
        c = p + bis * (r / math.sin(theta / 2))
        a1 = math.atan2((t1 - c).y, (t1 - c).x)
        a2 = math.atan2((t2 - c).y, (t2 - c).x)
        da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        for k in range(segments + 1):
            ang = a1 + da * k / segments
            out.append(c + Vector((math.cos(ang), math.sin(ang))) * r)
    return [(v.x, v.y) for v in out]


def smooth_path(points, samples=6):
    """Catmull-Rom resample of an open 2D/3D polyline — turns a few control points into a curve."""
    pts = [Vector(p) for p in points]
    if len(pts) < 3:
        return [tuple(p) for p in pts]
    out = []
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for s in range(samples):
            t = s / samples
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1])
    return [tuple(p) for p in out]


def _seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return (a + ab * t - p).length


def _crown(bm, pts2, plane, half, crown, width):
    """Bulge both flat caps: refine them into small triangles, then push each vertex outward by a
    smoothstep of its distance to the outline. Robust on concave, filleted outlines (no insets)."""
    ui, vi, wi = {"XZ": (0, 2, 1), "XY": (0, 1, 2), "YZ": (1, 2, 0)}[plane]
    poly = [Vector(p) for p in pts2]
    segs = [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]
    thr = width * 0.45
    for side in (-half, half):
        def cap_faces():
            return [f for f in bm.faces if all(abs(v.co[wi] - side) < 1e-9 for v in f.verts)]
        bmesh.ops.triangulate(bm, faces=cap_faces(), quad_method="BEAUTY", ngon_method="BEAUTY")
        for _ in range(10):
            faces = cap_faces()
            long_edges = list({e for f in faces for e in f.edges if e.calc_length() > thr})
            if not long_edges:
                break
            bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=1, use_grid_fill=False)
            bmesh.ops.triangulate(bm, faces=[f for f in cap_faces() if len(f.verts) > 3],
                                  quad_method="BEAUTY", ngon_method="BEAUTY")
        faces = cap_faces()
        fset = set(faces)
        interior = [v for v in {v for f in faces for v in f.verts} if all(lf in fset for lf in v.link_faces)]
        for _ in range(4):  # relax triangle shapes in-plane
            bmesh.ops.smooth_vert(bm, verts=interior, factor=0.5, use_axis_x=ui == 0 or vi == 0,
                                  use_axis_y=ui == 1 or vi == 1, use_axis_z=ui == 2 or vi == 2)
        inner_edges = list({e for f in faces for e in f.edges if all(lf in fset for lf in e.link_faces)})
        bmesh.ops.beautify_fill(bm, faces=faces, edges=inner_edges)
        sign = 1 if side > 0 else -1
        for v in interior:
            p = Vector((v.co[ui], v.co[vi]))
            d = min(_seg_dist(p, a, b) for a, b in segs)
            t = min(d / width, 1.0)
            v.co[wi] = side + sign * crown * t * t * (3 - 2 * t)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #


def profile_extrude(name, points, depth, plane="XZ", radii=0.0, segments=6,
                    location=(0, 0, 0), edge_round=None, edge_segments=4, crown=0.0, crown_width=None):
    """Draw the side silhouette, extrude it to thickness. The workhorse for hard-surface props.

    plane: "XZ" (side view, extrude along Y), "XY" (top view, along Z), "YZ" (front view, along X).
    edge_round: bevel width for the extruded edges (None = 25 % of depth, capped).
    crown: how far (m) each flat side bulges outward. Real stocks, handles, grips and bodies are
           convex in cross-section; a flat side is what makes a prop read as a plywood cutout.
           Typical: 8–15 % of depth. crown_width: band over which the bulge rises (None = 35 % of depth).
    """
    pts2 = fillet_polygon(points, radii, segments)
    bm = bmesh.new()
    half = depth / 2
    def to3(u, v, w):
        return {"XZ": (u, w, v), "XY": (u, v, w), "YZ": (w, u, v)}[plane]
    front = [bm.verts.new(to3(u, v, -half)) for u, v in pts2]
    back = [bm.verts.new(to3(u, v, half)) for u, v in pts2]
    n = len(front)
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((front[i], front[j], back[j], back[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if crown > 0:
        _crown(bm, pts2, plane, half, crown, crown_width if crown_width is not None else depth * 0.35)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    _smooth(me, 40)
    obj = _link(name, me, location)
    w = edge_round if edge_round is not None else min(depth * 0.25, 0.02)
    if w > 0:
        mod = obj.modifiers.new("bz_bevel", "BEVEL")
        mod.width = w
        mod.segments = edge_segments
        mod.limit_method = "ANGLE"
        mod.angle_limit = math.radians(40 if crown > 0 else 50)
        mod.use_clamp_overlap = True
        mod.harden_normals = False
        mod.profile = 0.5
    return obj


def lathe(name, profile, segments=64, axis="Z", location=(0, 0, 0), sharp_deg=35, edge_round=None):
    """Spin a (radius, height) profile around an axis. Start/end at radius 0 to close the ends.

    Include real features in the profile: chamfers, lips, grooves, crowns, recesses.
    edge_round: bevel width for remaining hard corners (None = 4 % of max radius, 0 = off).
    """
    bm = bmesh.new()
    verts = [bm.verts.new((r, 0, h)) for r, h in profile]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 0, 1),
                   angle=2 * math.pi, steps=segments, use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.transform(_AXIS_ROT[axis])
    _smooth(me, sharp_deg)
    obj = _link(name, me, location)
    w = edge_round if edge_round is not None else min(max(max(r for r, _ in profile) * 0.04, 0.0002), 0.003)
    if w > 0:
        mod = obj.modifiers.new("bz_bevel", "BEVEL")
        mod.width, mod.segments, mod.limit_method = w, 2, "ANGLE"
        mod.angle_limit = math.radians(40)
        mod.use_clamp_overlap = True
        mod.harden_normals = True
    return obj


def sweep(name, points, radius, radii=None, resolution=10, cyclic=False, samples=6, caps=True):
    """Tube along a path (3D control points, smoothed). radii: per-control-point multipliers for taper."""
    path = smooth_path(points, samples) if len(points) > 2 else [tuple(p) for p in points]
    if radii:
        rr = smooth_path([(r, 0, 0) for r in radii], samples) if len(radii) > 2 else radii
        rr = [r[0] if isinstance(r, tuple) else r for r in rr]
    else:
        rr = [1.0] * len(path)
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = max(2, resolution // 2)
    cu.use_fill_caps = caps
    cu.twist_mode = "MINIMUM"
    sp = cu.splines.new("POLY")
    sp.points.add(len(path) - 1)
    for p, co, r in zip(sp.points, path, rr):
        p.co = (*co, 1)
        p.radius = r
    sp.use_cyclic_u = cyclic
    tmp = _link(name + "_curve", cu)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)
    me.name = name
    pivot = Vector(points[0])
    me.transform(Matrix.Translation(-pivot))   # origin at the attachment end, so rotations hinge there
    _smooth(me, 60)
    obj = _link(name, me, pivot)
    if caps:  # soften the cut ends of the rod
        mod = obj.modifiers.new("bz_bevel", "BEVEL")
        mod.width, mod.segments, mod.limit_method = radius * 0.3, 2, "ANGLE"
        mod.angle_limit = math.radians(50)
        mod.use_clamp_overlap = True
    return obj


def rounded_box(name, size, radius=None, location=(0, 0, 0), segments=4):
    """Machined block with real edge radius (default 12 % of the smallest side)."""
    sx, sy, sz = size
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= sx
        v.co.y *= sy
        v.co.z *= sz
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    _smooth(me)
    obj = _link(name, me, location)
    r = radius if radius is not None else min(size) * 0.12
    if r <= 0:
        return obj
    mod = obj.modifiers.new("bz_bevel", "BEVEL")
    mod.width = r
    mod.segments = segments
    mod.use_clamp_overlap = True
    mod.harden_normals = True
    return obj


def _boolean(target, tool, op):
    _active(target)
    mod = target.modifiers.new("bz_bool", "BOOLEAN")
    mod.operation = op
    mod.solver = "EXACT"
    mod.object = tool
    bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(tool, do_unlink=True)
    _smooth(target.data)
    return target


def cut(target, cutter):
    """Boolean difference, applied under any existing bevel so the cut edges get rounded too."""
    return _boolean(target, cutter, "DIFFERENCE")


def union(target, other):
    return _boolean(target, other, "UNION")


def screw(name, location, normal=(0, 0, 1), radius=0.003, slot=True):
    """Domed slotted screw head — tertiary detail that tells the eye the true scale."""
    h = radius * 0.45
    prof = [(0, -h * 0.5), (radius, -h * 0.5)]
    prof += [(radius * math.cos(math.radians(a)), h * math.sin(math.radians(a))) for a in range(0, 76, 15)]
    prof += [(0, h)]
    obj = lathe(name, prof, segments=24)
    if slot:
        cut(obj, rounded_box(name + "_slot", (radius * 2.4, radius * 0.28, h * 1.4), radius=0,
                             location=(0, 0, h)))
    n = Vector(normal).normalized()
    obj.rotation_euler = Vector((0, 0, 1)).rotation_difference(n).to_euler()
    obj.location = location
    return obj


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #


def group(objs, name, location=(0, 0, 0)):
    """Parent parts to an Empty so the whole assembly moves/rotates as one."""
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.location = location
    for o in objs:
        mw = o.matrix_world.copy()
        o.parent = e
        o.matrix_parent_inverse = e.matrix_world.inverted()
        o.matrix_world = mw
    return e


def assembly_bbox(root):
    bpy.context.view_layer.update()
    objs = [root] if root.type == "MESH" else [o for o in root.children_recursive if o.type == "MESH"]
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def ground_assembly(root, floor_z=0.0):
    mn, _ = assembly_bbox(root)
    root.location.z += floor_z - mn.z
    bpy.context.view_layer.update()


def check_dims(obj, expected, tol=0.15):
    """Compare world dimensions to a reference sheet (meters). Returns list of problems."""
    mn, mx = assembly_bbox(obj)
    got = mx - mn
    bad = []
    for axis, g, e in zip("XYZ", got, expected):
        if e and abs(g - e) / e > tol:
            bad.append(f"{obj.name}.{axis}: {g:.3f} m vs reference {e:.3f} m")
    for b in bad:
        print("BLUERSKILL_DIMS", b)
    return bad
