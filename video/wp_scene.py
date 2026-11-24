"""Weed Puller WP-1: production-look Blender scene builder.

Builds the robot, materials, studio and field environments with bpy (Blender 5.x
as a Python module). Shots in shots.py import this and add camera + animation.
Units are metres, +X is the robot's forward direction, +Z is up.
"""
import math
import random
import bpy
import bmesh
from mathutils import Vector, Matrix

FONT_BOLD = "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"
FONT_MED = "/usr/share/fonts/opentype/inter/InterDisplay-Medium.otf"

# ------------------------------------------------------------------ utilities

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def P(mat):
    return mat.node_tree.nodes["Principled BSDF"]


def setin(node, name, value):
    if name in node.inputs:
        node.inputs[name].default_value = value


def material(name, color, rough=0.5, metal=0.0, **kw):
    m = bpy.data.materials.new(name)
    b = P(m)
    setin(b, "Base Color", (*color, 1.0))
    setin(b, "Roughness", rough)
    setin(b, "Metallic", metal)
    for k, v in kw.items():
        setin(b, k.replace("_", " "), v)
    return m


def link(obj, parent=None):
    bpy.context.scene.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def mesh_obj(name, bm, mat=None, parent=None, bevel=0.0, seg=3, smooth=True, angle=35):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    ob = bpy.data.objects.new(name, me)
    if mat:
        me.materials.append(mat)
    link(ob, parent)
    if bevel > 0:
        md = ob.modifiers.new("bevel", "BEVEL")
        md.width = bevel
        md.segments = seg
        md.limit_method = "ANGLE"
        md.angle_limit = math.radians(angle)
        md.harden_normals = True
    return ob


def bm_box(sx, sy, sz, loc=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    bmesh.ops.translate(bm, vec=loc, verts=bm.verts)
    return bm


def bm_cyl(r1, r2, depth, seg=48, loc=(0, 0, 0), axis="Z"):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r1, radius2=r2, depth=depth)
    if axis == "Y":
        bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"), verts=bm.verts)
    elif axis == "X":
        bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"), verts=bm.verts)
    bmesh.ops.translate(bm, vec=loc, verts=bm.verts)
    return bm


def bm_sphere(r, loc=(0, 0, 0), scale=(1, 1, 1), seg=32, rings=16):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    bmesh.ops.translate(bm, vec=loc, verts=bm.verts)
    return bm


def bm_torus(R, r, loc=(0, 0, 0), seg=48, rseg=12, axis="Z"):
    bm = bmesh.new()
    verts = []
    for i in range(seg):
        a = i / seg * 2 * math.pi
        ring = []
        for j in range(rseg):
            b = j / rseg * 2 * math.pi
            x = (R + r * math.cos(b)) * math.cos(a)
            y = (R + r * math.cos(b)) * math.sin(a)
            z = r * math.sin(b)
            ring.append(bm.verts.new((x, y, z)))
        verts.append(ring)
    for i in range(seg):
        for j in range(rseg):
            a, b = verts[i][j], verts[(i + 1) % seg][j]
            c, d = verts[(i + 1) % seg][(j + 1) % rseg], verts[i][(j + 1) % rseg]
            bm.faces.new((a, b, c, d))
    if axis == "Y":
        bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"), verts=bm.verts)
    bmesh.ops.translate(bm, vec=loc, verts=bm.verts)
    return bm


def empty(name, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    e.location = loc
    return link(e, parent)


def key(obj, path, frame, value, index=-1):
    if index >= 0:
        getattr(obj, path)[index] = value
        obj.keyframe_insert(path, index=index, frame=frame)
    else:
        setattr(obj, path, value)
        obj.keyframe_insert(path, frame=frame)


def ease_all(obj, interp="BEZIER", easing="EASE_IN_OUT"):
    ad = obj.animation_data
    if not ad or not ad.action:
        return
    try:
        curves = ad.action.fcurves
    except AttributeError:  # layered actions (4.4+)
        curves = []
        for layer in ad.action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    curves.extend(bag.fcurves)
    for fc in curves:
        for kp in fc.keyframe_points:
            kp.interpolation = interp
            kp.easing = easing


def text_obj(name, body, size, mat, font=FONT_BOLD, extrude=0.0008, parent=None, align="CENTER"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = bpy.data.fonts.load(font, check_existing=True)
    cu.size = size
    cu.extrude = extrude
    cu.align_x = align
    cu.align_y = "CENTER"
    ob = bpy.data.objects.new(name, cu)
    ob.data.materials.append(mat)
    return link(ob, parent)


# ------------------------------------------------------------------ materials

def make_materials():
    M = {}
    M["orange"] = material("PowderOrange", (0.92, 0.11, 0.006), rough=0.4, Coat_Weight=0.35, Coat_Roughness=0.16)
    M["graphite"] = material("Graphite", (0.022, 0.024, 0.027), rough=0.46, metal=0.25)
    M["graphite_matte"] = material("GraphiteMatte", (0.018, 0.019, 0.021), rough=0.72)
    M["alu"] = material("BrushedAlu", (0.86, 0.87, 0.89), rough=0.27, metal=1.0, Anisotropic=0.55)
    M["steel"] = material("Steel", (0.9, 0.9, 0.9), rough=0.13, metal=1.0)
    M["rubber"] = material("Rubber", (0.016, 0.016, 0.017), rough=0.82)
    M["lens"] = material("Lens", (0.0, 0.0, 0.0), rough=0.02, Coat_Weight=1.0, Coat_Roughness=0.0)
    M["white"] = material("WhitePlastic", (0.82, 0.83, 0.82), rough=0.35, Coat_Weight=0.2)
    M["red"] = material("EStopRed", (0.6, 0.02, 0.02), rough=0.3, Coat_Weight=0.5)
    M["yellow"] = material("EStopYellow", (0.85, 0.55, 0.02), rough=0.4)
    M["smoke"] = material("SmokedPoly", (0.55, 0.55, 0.55), rough=0.04, Transmission_Weight=1.0, IOR=1.49)
    M["sand"] = material("Sand", (0.72, 0.56, 0.34), rough=0.95)
    M["led"] = material("LED", (0.6, 0.9, 1.0), rough=0.3, Emission_Color=(0.55, 0.88, 1.0, 1.0), Emission_Strength=6.0)
    M["status"] = material("StatusLED", (0.3, 1.0, 0.5), rough=0.3, Emission_Color=(0.25, 1.0, 0.45, 1.0), Emission_Strength=5.0)
    M["decal"] = material("DecalWhite", (0.9, 0.9, 0.88), rough=0.5)
    M["decal_dark"] = material("DecalDark", (0.02, 0.02, 0.02), rough=0.5)
    M["root"] = material("Root", (0.62, 0.5, 0.33), rough=0.8, Subsurface_Weight=0.2)
    M["hole"] = material("HoleSoil", (0.035, 0.024, 0.015), rough=1.0)
    # sand gets a fine grain bump
    sb = P(M["sand"]); nt = M["sand"].node_tree
    noise = nt.nodes.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 900
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.4
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"]); nt.links.new(bump.outputs["Normal"], sb.inputs["Normal"])
    # brushed aluminium gets a subtle streak
    return M


# ------------------------------------------------------------------ robot

HOP_X = -0.18
HUB_REST = 0.33
TINE_L = 0.16


def build_robot(M):
    R = {}
    root = empty("WP1")
    R["root"] = root

    # lower chassis + two-tone shell
    mesh_obj("Frame", bm_box(0.56, 0.38, 0.035, (0, 0, 0.16)), M["graphite"], root, bevel=0.008)
    mesh_obj("Skirt", bm_box(0.585, 0.405, 0.05, (0, 0, 0.195)), M["graphite"], root, bevel=0.02, seg=4)
    shell = mesh_obj("Shell", bm_box(0.58, 0.40, 0.095, (0, 0, 0.265)), M["orange"], root, bevel=0.035, seg=6)
    R["shell"] = shell
    mesh_obj("Deck", bm_box(0.5, 0.33, 0.01, (0, 0, 0.315)), M["graphite_matte"], root, bevel=0.004)
    # panel seam on shell sides
    for s in (1, -1):
        mesh_obj("Seam", bm_box(0.46, 0.002, 0.004, (0, s * 0.2025, 0.262)), M["graphite"], root, smooth=False)

    # wheels
    R["wheels"] = []
    for (x, y) in [(0.215, 0.26), (0.215, -0.26), (-0.215, 0.26), (-0.215, -0.26)]:
        w = empty("Wheel", (x, y, 0.11), root)
        mesh_obj("Tyre", bm_cyl(0.11, 0.11, 0.09, 64, axis="Y"), M["rubber"], w, bevel=0.016, seg=5)
        bm = bmesh.new()
        for i in range(30):
            a = i / 30 * 2 * math.pi
            t = bm_box(0.014, 0.034, 0.008)
            tmp = bpy.data.meshes.new("t"); t.to_mesh(tmp); t.free()
            bm.from_mesh(tmp)
            bpy.data.meshes.remove(tmp)
        # place lugs (chevron offset by alternating y)
        verts_per = 8
        for i in range(30):
            a = i / 30 * 2 * math.pi
            vs = bm.verts[:] if hasattr(bm.verts, "__getitem__") else list(bm.verts)
        bm.verts.ensure_lookup_table()
        for i in range(30):
            a = i / 30 * 2 * math.pi
            vs = [bm.verts[i * verts_per + k] for k in range(verts_per)]
            off = 0.017 if i % 2 else -0.017
            bmesh.ops.translate(bm, vec=(0, off, 0.108), verts=vs)
            bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(a, 3, "Y"), verts=vs)
        mesh_obj("Lugs", bm, M["rubber"], w, bevel=0.003, seg=2)
        side = 1 if y > 0 else -1
        mesh_obj("Rim", bm_cyl(0.068, 0.068, 0.07, 48, (0, side * 0.012, 0), axis="Y"), M["alu"], w, bevel=0.006)
        mesh_obj("RimDish", bm_cyl(0.05, 0.04, 0.02, 48, (0, side * 0.05, 0), axis="Y"), M["graphite"], w, bevel=0.004)
        mesh_obj("Cap", bm_cyl(0.018, 0.018, 0.012, 32, (0, side * 0.06, 0), axis="Y"), M["alu"], w, bevel=0.003)
        for k in range(5):
            a = k / 5 * 2 * math.pi
            mesh_obj("Bolt", bm_cyl(0.005, 0.005, 0.01, 12, (math.cos(a) * 0.032, side * 0.058, math.sin(a) * 0.032), axis="Y"), M["steel"], w)
        R["wheels"].append(w)

    # front bumper + vision hood
    mesh_obj("Bumper", bm_box(0.035, 0.44, 0.05, (0.315, 0, 0.2)), M["rubber"], root, bevel=0.016, seg=4)
    mesh_obj("HoodArm", bm_box(0.08, 0.16, 0.02, (0.35, 0, 0.27)), M["graphite"], root, bevel=0.006)
    mesh_obj("Hood", bm_box(0.13, 0.22, 0.075, (0.40, 0, 0.235)), M["graphite_matte"], root, bevel=0.018, seg=4)
    mesh_obj("HoodBrush", bm_box(0.13, 0.22, 0.03, (0.40, 0, 0.183)), M["rubber"], root, bevel=0.004)
    R["led_ring"] = mesh_obj("LEDRing", bm_torus(0.034, 0.005, (0.40, 0, 0.197)), M["led"], root)
    mesh_obj("VisionLens", bm_cyl(0.018, 0.018, 0.01, 32, (0.40, 0, 0.2)), M["lens"], root)
    t = text_obj("HoodLogo", "VISION", 0.018, M["decal"], FONT_MED, 0.0003, root)
    t.location = (0.4675, 0, 0.245); t.rotation_euler = (math.pi / 2, 0, math.pi / 2)

    # stereo cams + status strip
    mesh_obj("StereoBar", bm_box(0.035, 0.18, 0.04, (0.29, 0, 0.345)), M["graphite"], root, bevel=0.012, seg=4)
    for y in (-0.055, 0.055):
        mesh_obj("StereoLens", bm_cyl(0.012, 0.012, 0.01, 32, (0.309, y, 0.345), axis="X"), M["lens"], root)
    mesh_obj("StatusStrip", bm_box(0.004, 0.24, 0.006, (0.3045, 0, 0.292)), M["status"], root)

    # LiDAR puck
    mesh_obj("LidarBase", bm_cyl(0.045, 0.048, 0.035, 48, (0.2, 0, 0.338)), M["graphite"], root, bevel=0.006)
    R["lidar"] = mesh_obj("LidarWindow", bm_cyl(0.04, 0.04, 0.03, 48, (0.2, 0, 0.37)), M["lens"], root)
    mesh_obj("LidarCap", bm_cyl(0.044, 0.044, 0.012, 48, (0.2, 0, 0.391)), M["graphite"], root, bevel=0.005)

    # sand hopper: smoked clear wall, orange collar, graphite lid
    hx = HOP_X
    mesh_obj("HopperBase", bm_cyl(0.09, 0.09, 0.02, 64, (hx, 0, 0.33)), M["orange"], root, bevel=0.006)
    mesh_obj("HopperWall", bm_cyl(0.085, 0.085, 0.12, 64, (hx, 0, 0.40)), M["smoke"], root)
    R["sand"] = mesh_obj("HopperSand", bm_cyl(0.08, 0.08, 0.075, 64, (hx, 0, 0.3775)), M["sand"], root)
    mesh_obj("HopperCollar", bm_cyl(0.09, 0.09, 0.018, 64, (hx, 0, 0.465)), M["orange"], root, bevel=0.006)
    mesh_obj("HopperLid", bm_cyl(0.088, 0.082, 0.016, 64, (hx, 0, 0.482)), M["graphite"], root, bevel=0.006)
    mesh_obj("LidKnob", bm_cyl(0.022, 0.022, 0.016, 24, (hx, 0, 0.497)), M["alu"], root, bevel=0.003)
    # fill marks on the window
    for i in range(4):
        mesh_obj("Tick", bm_box(0.002, 0.018, 0.0015, (hx + 0.0855, 0, 0.36 + i * 0.025)), M["decal"], root, smooth=False)
    mesh_obj("Nozzle", bm_cyl(0.015, 0.009, 0.07, 24, (hx, 0, 0.11)), M["alu"], root, bevel=0.002)

    # RTK mast (rear right)
    mx, my = -0.255, -0.15
    mesh_obj("MastHinge", bm_cyl(0.018, 0.018, 0.04, 24, (mx, my, 0.33), axis="Y"), M["graphite"], root, bevel=0.004)
    mesh_obj("Mast", bm_cyl(0.01, 0.01, 0.2, 24, (mx, my, 0.43)), M["alu"], root)
    mesh_obj("GnssBase", bm_cyl(0.05, 0.05, 0.015, 48, (mx, my, 0.535)), M["graphite"], root, bevel=0.004)
    mesh_obj("GnssDome", bm_sphere(0.05, (mx, my, 0.542), (1, 1, 0.42)), M["white"], root)

    # e-stop
    mesh_obj("EStopBase", bm_cyl(0.024, 0.024, 0.022, 32, (-0.265, 0.15, 0.33)), M["yellow"], root, bevel=0.003)
    mesh_obj("EStop", bm_cyl(0.028, 0.03, 0.02, 32, (-0.265, 0.15, 0.352)), M["red"], root, bevel=0.007)

    # rear weed bin
    mesh_obj("Bin", bm_box(0.09, 0.32, 0.12, (-0.335, 0, 0.245)), M["graphite"], root, bevel=0.014, seg=4)
    mesh_obj("BinLid", bm_box(0.095, 0.325, 0.012, (-0.335, 0, 0.31)), M["graphite_matte"], root, bevel=0.005)
    mesh_obj("BinLatch", bm_box(0.004, 0.05, 0.02, (-0.381, 0, 0.29)), M["alu"], root, bevel=0.002)

    # hot-swap battery (left side)
    mesh_obj("Battery", bm_box(0.2, 0.025, 0.07, (0.04, 0.214, 0.235)), M["graphite"], root, bevel=0.01, seg=3)
    mesh_obj("BattLatch", bm_box(0.045, 0.01, 0.012, (0.04, 0.228, 0.262)), M["alu"], root, bevel=0.003)
    for i in range(4):
        mesh_obj("BattLED", bm_box(0.008, 0.003, 0.003, (0.0 + i * 0.013, 0.2275, 0.215)), M["status"], root, smooth=False)

    # carry handles: brushed tube with rubber grip
    for s in (1, -1):
        cu = bpy.data.curves.new("HandleCurve", "CURVE")
        cu.dimensions = "3D"
        sp = cu.splines.new("BEZIER")
        pts = [(0.15, s * 0.185, 0.318), (0.115, s * 0.192, 0.392), (-0.115, s * 0.192, 0.392), (-0.15, s * 0.185, 0.318)]
        sp.bezier_points.add(len(pts) - 1)
        for bp, p in zip(sp.bezier_points, pts):
            bp.co = p
            bp.handle_left_type = bp.handle_right_type = "AUTO"
        cu.bevel_depth = 0.011
        cu.bevel_resolution = 6
        cu.resolution_u = 24
        h = bpy.data.objects.new("Handle", cu)
        cu.materials.append(M["alu"])
        link(h, root)
        mesh_obj("Grip", bm_cyl(0.016, 0.016, 0.13, 32, (0, s * 0.192, 0.392), axis="X"), M["rubber"], root, bevel=0.006)
        for x in (0.15, -0.15):
            mesh_obj("HandleFoot", bm_cyl(0.02, 0.02, 0.012, 24, (x, s * 0.185, 0.322)), M["graphite"], root, bevel=0.003)

    # strap points
    for (x, y) in [(0.25, 0.19), (0.25, -0.19), (-0.24, 0.19), (-0.24, -0.19)]:
        mesh_obj("Strap", bm_torus(0.012, 0.003, (x, y, 0.333), 24, 8, axis="Y"), M["alu"], root)

    # branding
    for s in (1, -1):
        t = text_obj("Logo", "WP-1", 0.05, M["decal_dark"], FONT_BOLD, 0.0006, root, "LEFT")
        t.location = (0.06 if s > 0 else -0.06, s * 0.2245, 0.272)
        t.rotation_euler = (math.pi / 2, 0, 0 if s < 0 else math.pi)
        t2 = text_obj("Brand", "WEED PULLER", 0.016, M["decal_dark"], FONT_MED, 0.0004, root, "LEFT")
        t2.location = (-0.21 if s < 0 else 0.21, s * 0.2245, 0.276)
        t2.rotation_euler = (math.pi / 2, 0, 0 if s < 0 else math.pi)
    t3 = text_obj("RearLogo", "WP-1", 0.03, M["decal"], FONT_BOLD, 0.0004, root)
    t3.location = (-0.3815, 0, 0.245); t3.rotation_euler = (math.pi / 2, 0, -math.pi / 2)

    # extraction head
    mesh_obj("Turret", bm_cyl(0.045, 0.045, 0.12, 48, (0, 0, 0.38)), M["graphite"], root, bevel=0.008)
    mesh_obj("TurretRing", bm_cyl(0.0455, 0.0455, 0.01, 48, (0, 0, 0.42)), M["orange"], root)
    mesh_obj("TurretCap", bm_cyl(0.04, 0.036, 0.014, 48, (0, 0, 0.447)), M["alu"], root, bevel=0.004)
    head = empty("Head", (0, 0, HUB_REST), root)
    R["head"] = head
    mesh_obj("Shaft", bm_cyl(0.009, 0.009, 0.05, 24, (0, 0, 0.085)), M["steel"], head)
    mesh_obj("Motor", bm_cyl(0.03, 0.03, 0.06, 40, (0, 0, 0.05)), M["graphite"], head, bevel=0.005)
    mesh_obj("MotorBand", bm_cyl(0.0305, 0.0305, 0.008, 40, (0, 0, 0.07)), M["orange"], head)
    spin = empty("Spin", (0, 0, 0), head)
    R["spin"] = spin
    mesh_obj("Hub", bm_cyl(0.04, 0.036, 0.016, 40, (0, 0, 0)), M["alu"], spin, bevel=0.004)
    R["tines"] = []
    for i in range(4):
        a = i * math.pi / 2 + math.pi / 4
        pv = empty("TinePivot", (math.cos(a) * 0.03, math.sin(a) * 0.03, -0.008), spin)
        pv.rotation_euler = (0, 0, a)
        mesh_obj("Knuckle", bm_sphere(0.008), M["alu"], pv)
        mesh_obj("Tine", bm_cyl(0.0045, 0.0003, TINE_L, 24, (0, 0, -TINE_L / 2)), M["steel"], pv)
        R["tines"].append(pv)
    set_tines(R, 0.3)
    return R


def set_tines(R, open_amt, frame=None):
    """open 1 = splayed outward, 0 = tips converge under the crown."""
    th = -0.18 + open_amt * 0.42
    for pv in R["tines"]:
        # rotate about the pivot's local Y so the tip swings radially
        pv.rotation_euler = (0, -th, pv.rotation_euler[2])
        if frame is not None:
            pv.keyframe_insert("rotation_euler", index=1, frame=frame)


def spin_wheels(R, frame, distance):
    for w in R["wheels"]:
        w.rotation_euler[1] = distance / 0.11
        w.keyframe_insert("rotation_euler", index=1, frame=frame)


# ------------------------------------------------------------------ plants

def leaf_bm(length, width, lobes=4, lift=0.25, serr=0.35, seed=0):
    rnd = random.Random(seed)
    n = 24
    bm = bmesh.new()
    left, right = [], []
    for i in range(n + 1):
        t = i / n
        w = width * math.sin(math.pi * min(1, t * 1.05)) ** 0.8 * (1 - 0.3 * t)
        if lobes:
            w *= 1 - serr * (0.5 + 0.5 * math.cos(t * lobes * 2 * math.pi))
        x = t * length
        z = math.sin(t * math.pi * 0.5) * lift * length - t * t * 0.15 * length
        left.append(bm.verts.new((x, w, z)))
        right.append(bm.verts.new((x, -w * (0.95 + rnd.random() * 0.1), z)))
    mid = [bm.verts.new((i / n * length, 0, math.sin(i / n * math.pi * 0.5) * lift * length - (i / n) ** 2 * 0.15 * length + 0.0008)) for i in range(n + 1)]
    for i in range(n):
        bm.faces.new((mid[i], mid[i + 1], left[i + 1], left[i]))
        bm.faces.new((mid[i], right[i], right[i + 1], mid[i + 1]))
    return bm


def leaf_material(name, color):
    m = material(name, color, rough=0.85, Specular_IOR_Level=0.08)
    return m


def build_dandelion(M, name="Dandelion", seed=1, flower=True, scale=1.0):
    rnd = random.Random(seed)
    g = empty(name)
    lm = M.setdefault("leaf", leaf_material("Leaf", (0.035, 0.13, 0.01)))
    for i in range(10):
        bm = leaf_bm(0.07 + rnd.random() * 0.03, 0.012, lobes=5, lift=0.18 + rnd.random() * 0.15, seed=seed * 31 + i)
        bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(i / 10 * 2 * math.pi + rnd.random() * 0.3, 3, "Z"), verts=bm.verts)
        bmesh.ops.translate(bm, vec=(0, 0, 0.004), verts=bm.verts)
        ob = mesh_obj("Leaf", bm, lm, g)
        ob.modifiers.new("solid", "SOLIDIFY").thickness = 0.0008
    if flower:
        fm = M.setdefault("petal", material("Petal", (0.95, 0.55, 0.01), rough=0.75, Specular_IOR_Level=0.1))
        sm = M.setdefault("stem", material("Stem", (0.2, 0.3, 0.08), rough=0.5))
        h = 0.06 + rnd.random() * 0.02
        cu = bpy.data.curves.new("Stem", "CURVE"); cu.dimensions = "3D"
        sp = cu.splines.new("BEZIER"); sp.bezier_points.add(1)
        sp.bezier_points[0].co = (0, 0, 0); sp.bezier_points[1].co = (0.01, 0.004, h)
        for bp in sp.bezier_points: bp.handle_left_type = bp.handle_right_type = "AUTO"
        cu.bevel_depth = 0.0024; cu.bevel_resolution = 3
        st = bpy.data.objects.new("Stem", cu); cu.materials.append(sm); link(st, g)
        bm = bmesh.new()
        for ring, (n, L, tilt) in enumerate([(44, 0.021, 0.25), (38, 0.018, 0.55), (30, 0.014, 0.85), (22, 0.010, 1.15), (14, 0.006, 1.4)]):
            for k in range(n):
                a = k / n * 2 * math.pi + ring * 0.37 + rnd.random() * 0.08
                tilt_k = tilt + (rnd.random() - 0.5) * 0.25
                p = bm_box(L * (0.85 + rnd.random() * 0.3), 0.0022, 0.0005, (L / 2, 0, 0))
                tmp = bpy.data.meshes.new("t"); p.to_mesh(tmp); p.free()
                start = len(bm.verts); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
                bm.verts.ensure_lookup_table()
                vs = bm.verts[start:]
                bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(-tilt_k, 3, "Y"), verts=vs)
                bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(a, 3, "Z"), verts=vs)
        bmesh.ops.translate(bm, vec=(0.01, 0.004, h + 0.004), verts=bm.verts)
        mesh_obj("Flower", bm, fm, g)
        mesh_obj("Sepal", bm_sphere(0.007, (0.01, 0.004, h), (1, 1, 0.6), 16, 8), sm, g)
    # taproot (below ground, revealed on extraction)
    rm = M["root"]
    mesh_obj("Taproot", bm_cyl(0.0075, 0.0008, 0.13, 16, (0, 0, -0.065)), rm, g)
    for i in range(6):
        a = rnd.random() * 6.28
        cu = bpy.data.curves.new("Rootlet", "CURVE"); cu.dimensions = "3D"
        sp = cu.splines.new("POLY"); sp.points.add(2)
        z0 = -0.02 - i * 0.015
        sp.points[0].co = (0, 0, z0, 1)
        sp.points[1].co = (math.cos(a) * 0.015, math.sin(a) * 0.015, z0 - 0.01, 1)
        sp.points[2].co = (math.cos(a) * 0.028, math.sin(a) * 0.028, z0 - 0.03, 1)
        cu.bevel_depth = 0.0006
        o = bpy.data.objects.new("Rootlet", cu); cu.materials.append(rm); link(o, g)
    # soil clinging to the root ball
    mesh_obj("RootBall", bm_sphere(0.016, (0, 0, -0.012), (1, 1, 0.8), 16, 8), M["hole"], g)
    g.scale = (scale, scale, scale)
    return g


# ------------------------------------------------------------------ environments

def render_settings(w=1280, h=720, samples=40, fps=24):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.04
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 6
    sc.cycles.transparent_max_bounces = 8
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.blur_glossy = 1.0
    sc.render.use_persistent_data = True
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.fps = fps
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Punchy"
    except Exception:
        try:
            sc.view_settings.view_transform = "Filmic"
        except Exception:
            pass
    sc.render.film_transparent = False
    sc.view_settings.exposure = 0.0


def world_sky(elev=32, az=-35, strength=0.75, energy=4.0):
    """az: compass direction toward the sun, degrees CCW from +X."""
    w = bpy.data.worlds.new("Sky")
    bpy.context.scene.world = w
    nt = w.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    for k, v in (("sun_elevation", math.radians(elev)), ("sun_rotation", math.radians(90 - az)), ("sun_disc", False), ("altitude", 50.0)):
        try:
            setattr(sky, k, v)
        except Exception:
            pass
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = energy
    sun.angle = math.radians(1.5)
    sun.color = (1.0, 0.93, 0.82)
    so = bpy.data.objects.new("Sun", sun)
    e, a = math.radians(elev), math.radians(az)
    to_sun = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
    so.rotation_euler = (-to_sun).to_track_quat("-Z", "Y").to_euler()
    link(so)
    return so


def world_studio():
    w = bpy.data.worlds.new("Studio")
    bpy.context.scene.world = w
    nt = w.node_tree
    bg = nt.nodes.get("Background") or nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0.006, 0.007, 0.008, 1)
    bg.inputs["Strength"].default_value = 1.0
    out = nt.nodes.get("World Output") or nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    # seamless cyclorama sweep
    bm = bmesh.new()
    prof = []
    for i in range(21):
        t = i / 20
        a = t * math.pi / 2
        prof.append((-3.0 - 0.0, 0))
    rows = []
    R = 1.2
    pts = [(x, 0.0) for x in [6, 4, 2, 0, -1.5]]
    for i in range(1, 13):
        a = i / 12 * math.pi / 2
        pts.append((-1.5 - math.sin(a) * R, R - math.cos(a) * R))
    pts.append((-2.7, 3.5))
    for (x, z) in pts:
        rows.append((bm.verts.new((x, -6, z)), bm.verts.new((x, 6, z))))
    for i in range(len(rows) - 1):
        a, b = rows[i]; c, d = rows[i + 1]
        bm.faces.new((a, b, d, c))
    floor_m = material("CycFloor", (0.035, 0.036, 0.04), rough=0.32)
    cyc = mesh_obj("Cyclorama", bm, floor_m)
    cyc.rotation_euler = (0, 0, math.radians(200))

    def area(name, loc, rot, size, energy, color=(1, 1, 1), shape="RECTANGLE", sy=None):
        L = bpy.data.lights.new(name, "AREA")
        L.shape = shape
        L.size = size
        if sy:
            L.size_y = sy
        L.energy = energy
        L.color = color
        o = bpy.data.objects.new(name, L)
        o.location = loc
        o.rotation_euler = rot
        link(o)
        return o

    def aim(o, target=(0, 0, 0.25)):
        d = Vector(target) - o.location
        o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

    key_l = area("Key", (1.6, 1.4, 1.6), (0, 0, 0), 1.6, 260, (1.0, 0.97, 0.93)); aim(key_l)
    rim1 = area("RimL", (-1.4, 1.2, 0.9), (0, 0, 0), 0.25, 160, (0.85, 0.92, 1.0), "RECTANGLE", 1.6); aim(rim1)
    rim2 = area("RimR", (-1.2, -1.5, 0.8), (0, 0, 0), 0.25, 140, (0.85, 0.92, 1.0), "RECTANGLE", 1.6); aim(rim2)
    top = area("Top", (0, 0, 2.2), (0, 0, 0), 2.0, 90); aim(top)
    fill = area("Fill", (0.8, -1.8, 0.5), (0, 0, 0), 1.0, 35, (1.0, 0.95, 0.9)); aim(fill)
    return {"key": key_l, "rim1": rim1, "rim2": rim2}


def build_field(M, patch=(3.0, 3.0), center=(0, 0), hair=45000, clear=(), length=0.045):
    """Lawn: soil ground plane + particle-hair grass on a patch around the action.
    `clear` = list of (x, y, r) circles kept free of grass (weed crowns, holes)."""
    soil = material("Soil", (0.09, 0.065, 0.04), rough=0.95)
    nt = soil.node_tree; b = P(soil)
    noise = nt.nodes.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 40; noise.inputs["Detail"].default_value = 8
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.05, 0.035, 0.02, 1)
    ramp.color_ramp.elements[1].color = (0.16, 0.16, 0.06, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"]); nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.5
    n2 = nt.nodes.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 300
    nt.links.new(n2.outputs["Fac"], bump.inputs["Height"]); nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])

    far = mesh_obj("Ground", bm_box(500, 500, 0.001, (0, 0, -0.0005)), soil, smooth=False)
    # distant lawn colour so the horizon reads as grass under DOF
    farm = material("FarLawn", (0.05, 0.12, 0.02), rough=1.0, Specular_IOR_Level=0.15)
    fn = farm.node_tree; fb = P(farm)
    v = fn.nodes.new("ShaderNodeTexNoise"); v.inputs["Scale"].default_value = 3
    r2 = fn.nodes.new("ShaderNodeValToRGB")
    r2.color_ramp.elements[0].color = (0.03, 0.08, 0.015, 1); r2.color_ramp.elements[1].color = (0.08, 0.14, 0.03, 1)
    fn.links.new(v.outputs["Fac"], r2.inputs["Fac"]); fn.links.new(r2.outputs["Color"], fb.inputs["Base Color"])
    far.data.materials.clear(); far.data.materials.append(farm)

    # distant tree line so the horizon isn't bare (blurred by DOF)
    tm = material("Trees", (0.025, 0.05, 0.02), rough=0.9)
    tn = tm.node_tree; tb = P(tm)
    tv = tn.nodes.new("ShaderNodeTexNoise"); tv.inputs["Scale"].default_value = 2.5
    tr = tn.nodes.new("ShaderNodeValToRGB")
    tr.color_ramp.elements[0].color = (0.05, 0.075, 0.06, 1); tr.color_ramp.elements[1].color = (0.09, 0.12, 0.08, 1)
    tn.links.new(tv.outputs["Fac"], tr.inputs["Fac"]); tn.links.new(tr.outputs["Color"], tb.inputs["Base Color"])
    from mathutils import noise as mnoise
    rnd = random.Random(4)
    bm = bmesh.new()
    for i in range(520):
        a = i / 520 * 2 * math.pi + rnd.random() * 0.02
        d = 120 + rnd.random() * 25
        r = 4.5 + rnd.random() * 4.0
        part = bmesh.new()
        bmesh.ops.create_icosphere(part, subdivisions=3, radius=r)
        c = Vector((math.cos(a) * d, math.sin(a) * d, r * 0.8 + rnd.random() * 3))
        for v in part.verts:
            n = v.co.normalized()
            disp = mnoise.fractal(v.co * (1.3 / r) + Vector((i * 7.1, 0, 0)), 0.6, 2.0, 4)
            v.co = v.co * (1.0 + 0.28 * disp) * Vector((1, 1, 1.15)) + c
        tmp = bpy.data.meshes.new("t"); part.to_mesh(tmp); part.free(); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
    mesh_obj("TreeLine", bm, tm)

    # grass patch
    sx, sy = patch
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=int(sx * 60), y_segments=int(sy * 60), size=0.5)
    bmesh.ops.scale(bm, vec=(sx, sy, 1), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(center[0], center[1], 0.0005), verts=bm.verts)
    lawn = mesh_obj("LawnPatch", bm, soil, smooth=False)
    vg = lawn.vertex_groups.new(name="dens")
    for vtx in lawn.data.vertices:
        x, y = vtx.co.x, vtx.co.y
        w = 1.0
        ex = max(abs(x - center[0]) / (sx / 2), abs(y - center[1]) / (sy / 2))
        if ex > 0.85:
            w = max(0.0, (1 - ex) / 0.15)
        for (cx, cy, r) in clear:
            d = math.hypot(x - cx, y - cy)
            if d < r:
                w = 0.0
            elif d < r * 1.6:
                w = min(w, (d - r) / (r * 0.6))
        vg.add([vtx.index], w, "REPLACE")
    lawn.data.materials.append(soil)
    gm = material("Grass", (0.05, 0.16, 0.02), rough=0.55)
    gn = gm.node_tree; gb = P(gm)
    hi = gn.nodes.new("ShaderNodeHairInfo")
    ramp = gn.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.035, 0.075, 0.008, 1)
    ramp.color_ramp.elements[1].color = (0.26, 0.36, 0.05, 1)
    gn.links.new(hi.outputs["Intercept"], ramp.inputs["Fac"])
    mix = gn.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.inputs["Factor"].default_value = 0.35
    gn.links.new(ramp.outputs["Color"], mix.inputs[6])
    rn = gn.nodes.new("ShaderNodeValToRGB")
    rn.color_ramp.elements[0].color = (0.13, 0.17, 0.03, 1); rn.color_ramp.elements[1].color = (0.06, 0.18, 0.02, 1)
    gn.links.new(hi.outputs["Random"], rn.inputs["Fac"])
    gn.links.new(rn.outputs["Color"], mix.inputs[7])
    gn.links.new(mix.outputs[2], gb.inputs["Base Color"])
    lawn.data.materials.append(gm)

    mod = lawn.modifiers.new("grass", "PARTICLE_SYSTEM")
    ps = mod.particle_system
    s = ps.settings
    s.type = "HAIR"
    s.count = hair
    s.hair_length = 0.055
    s.emit_from = "FACE"
    s.use_emit_random = True
    s.distribution = "RAND"
    s.material_slot = gm.name
    s.child_type = "INTERPOLATED"
    s.child_percent = 5
    s.rendered_child_count = 5
    s.child_length = 0.95
    s.child_length_threshold = 0.4
    s.roughness_1 = 0.008
    s.roughness_2 = 0.02
    s.roughness_2_size = 0.5
    s.roughness_endpoint = 0.012
    s.clump_factor = 0.0
    s.root_radius = 1.0
    s.tip_radius = 0.0
    s.radius_scale = 0.0035
    s.use_close_tip = True
    s.factor_random = 0.004
    s.tangent_factor = 0.0
    s.phase_factor_random = 2.0
    s.brownian_factor = 0.0
    s.display_step = 3
    s.render_step = 3
    s.hair_length = length
    ps.vertex_group_density = "dens"
    ps.vertex_group_length = "dens"
    try:
        s.use_hair_bspline = True
    except Exception:
        pass
    return lawn


def camera(name="Cam", lens=50, fstop=4.0, focus=None):
    c = bpy.data.cameras.new(name)
    c.lens = lens
    c.sensor_width = 36
    c.dof.use_dof = True
    c.dof.aperture_fstop = fstop
    if focus is not None:
        c.dof.focus_object = focus
    o = bpy.data.objects.new(name, c)
    link(o)
    bpy.context.scene.camera = o
    return o


def look(cam, target):
    d = Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def cam_key(cam, frame, loc, target):
    cam.location = loc
    look(cam, target)
    cam.keyframe_insert("location", frame=frame)
    cam.keyframe_insert("rotation_euler", frame=frame)
