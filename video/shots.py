"""Render the WP-1 sales video shots.

usage: python shots.py <shot> [preview|full] [frame]
Frames land in $OUT/<shot>/0001.png. Field shots run at 12 fps (interpolated
to 24 in the edit), studio shots at 24 fps. Re-running `full` skips frames
that already exist, so a long render can resume.
"""
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402
import wp_scene as W  # noqa: E402

OUT = os.environ.get("WP_OUT", "/tmp/wp_frames")


def focus_on(cam, obj):
    cam.data.dof.focus_object = obj


def drive(R, f0, x0, f1, x1, y=0.0):
    root = R["root"]
    for f, x in ((f0, x0), (f1, x1)):
        root.location = (x, y, 0)
        root.keyframe_insert("location", frame=f)
        W.spin_wheels(R, f, x)


def lidar_spin(R, n):
    o = R["lidar"]
    o.rotation_euler = (0, 0, 0); o.keyframe_insert("rotation_euler", index=2, frame=1)
    o.rotation_euler = (0, 0, n * 0.6); o.keyframe_insert("rotation_euler", index=2, frame=n)
    for fc in _fcurves(o):
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"


def _fcurves(obj):
    ad = obj.animation_data
    if not ad or not ad.action:
        return []
    try:
        return list(ad.action.fcurves)
    except AttributeError:
        out = []
        for layer in ad.action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    out.extend(bag.fcurves)
        return out


def ease(obj):
    for fc in _fcurves(obj):
        for k in fc.keyframe_points:
            k.interpolation = "BEZIER"
            k.handle_left_type = k.handle_right_type = "AUTO_CLAMPED"


# --------------------------------------------------------------------- shots

def s1_open(M):
    """Macro of a dandelion in the lawn, slow push. No robot."""
    W.world_sky(elev=16, az=150, strength=0.8, energy=4.5)
    d = W.build_dandelion(M, seed=3, scale=1.5)
    d2 = W.build_dandelion(M, "Flatweed", seed=8, scale=1.0); d2.location = (-0.55, 0.35, 0)
    d3 = W.build_dandelion(M, "Dandelion2", seed=5, flower=False, scale=1.1); d3.location = (-0.9, -0.4, 0)
    W.build_field(M, (2.6, 2.0), (-0.3, 0), hair=40000, clear=[(0, 0, 0.08), (-0.55, 0.35, 0.06), (-0.9, -0.4, 0.07)], length=0.04)
    cam = W.camera(lens=70, fstop=2.2)
    fe = W.empty("Focus", (0.01, 0, 0.06)); focus_on(cam, fe)
    W.cam_key(cam, 1, (0.72, -0.5, 0.13), (0, 0, 0.075))
    W.cam_key(cam, 42, (0.55, -0.38, 0.11), (0, 0, 0.07))
    ease(cam)
    return 12, 42


def s2_arrive(M):
    R = W.build_robot(M)
    W.world_sky(elev=30, az=-50, strength=0.75, energy=4.2)
    w = W.build_dandelion(M, seed=11, scale=1.2); w.location = (0.15, 0.18, 0)
    W.build_field(M, (4.2, 2.2), (-0.9, 0.0), hair=60000, clear=[(0.15, 0.18, 0.1)])
    drive(R, 1, -2.1, 60, -0.35)
    ease(R["root"]); [ease(x) for x in R["wheels"]]
    lidar_spin(R, 60)
    cam = W.camera(lens=50, fstop=1.6)
    fe = W.empty("Focus", (0.1, 0, 0.25), R["root"]); focus_on(cam, fe)
    W.cam_key(cam, 1, (0.95, -0.62, 0.13), (-1.4, 0.0, 0.22))
    W.cam_key(cam, 60, (0.9, -0.66, 0.15), (-0.45, 0.0, 0.25))
    ease(cam)
    return 12, 60


def s3_orbit(M):
    R = W.build_robot(M)
    W.world_studio()
    lidar_spin(R, 156)
    cam = W.camera(lens=50, fstop=5.6)
    fe = W.empty("Focus", (0, 0, 0.25)); focus_on(cam, fe)
    n = 156
    for f in range(1, n + 1, 6):
        t = (f - 1) / (n - 1)
        a = math.radians(-35 + 95 * t)
        r = 1.85 - 0.15 * t
        W.cam_key(cam, f, (math.cos(a) * r, math.sin(a) * r, 0.55 + 0.08 * t), (0, 0, 0.24))
    W.cam_key(cam, n, (math.cos(math.radians(60)) * 1.7, math.sin(math.radians(60)) * 1.7, 0.63), (0, 0, 0.24))
    for fc in _fcurves(cam):
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"
    return 24, n


def s4_vision(M):
    R = W.build_robot(M)
    W.world_studio()
    lidar_spin(R, 120)
    led = M["led"].node_tree.nodes["Principled BSDF"]
    led.inputs["Emission Strength"].default_value = 1.0
    led.inputs["Emission Strength"].keyframe_insert("default_value", frame=1)
    led.inputs["Emission Strength"].default_value = 14.0
    led.inputs["Emission Strength"].keyframe_insert("default_value", frame=40)
    cam = W.camera(lens=70, fstop=2.8)
    fe = W.empty("Focus", (0.44, 0, 0.24)); focus_on(cam, fe)
    W.cam_key(cam, 1, (1.15, -0.55, 0.16), (0.36, 0.02, 0.24))
    W.cam_key(cam, 120, (0.98, -0.3, 0.2), (0.36, 0.0, 0.25))
    ease(cam)
    return 24, 120


def s5_extract(M):
    R = W.build_robot(M)
    W.world_sky(elev=34, az=-70, strength=0.75, energy=4.2)
    weed = W.build_dandelion(M, seed=3, scale=1.15)
    W.build_field(M, (2.2, 1.8), (0, 0), hair=40000, clear=[(0, 0, 0.11)], length=0.035)
    hole = W.mesh_obj("Hole", W.bm_cyl(0.03, 0.026, 0.02, 32, (0, 0, -0.0095)), M["hole"])
    hole.scale = (0.01, 0.01, 1); hole.keyframe_insert("scale", frame=41)
    hole.scale = (1, 1, 1); hole.keyframe_insert("scale", frame=46)
    head, spin = R["head"], R["spin"]
    HUB_DOWN = 0.06
    LIFT = 0.15

    def hk(f, z):
        head.location = (0, 0, z); head.keyframe_insert("location", index=2, frame=f)

    hk(1, W.HUB_REST); hk(12, W.HUB_REST); hk(30, HUB_DOWN); hk(42, HUB_DOWN); hk(74, HUB_DOWN + LIFT); hk(96, HUB_DOWN + LIFT)
    W.set_tines(R, 0.3, 1); W.set_tines(R, 0.3, 12); W.set_tines(R, 1.0, 19); W.set_tines(R, 1.0, 31); W.set_tines(R, 0.0, 40)
    for f, a in ((1, 0), (42, 0), (52, -0.52), (96, -0.52)):
        spin.rotation_euler = (0, 0, a); spin.keyframe_insert("rotation_euler", index=2, frame=f)
        weed.rotation_euler = (0, 0, a); weed.keyframe_insert("rotation_euler", index=2, frame=f)
    for f, z in ((1, 0), (42, 0), (74, LIFT), (96, LIFT)):
        weed.location = (0, 0, z); weed.keyframe_insert("location", index=2, frame=f)
    for o in [head, spin, weed, hole] + R["tines"]:
        ease(o)
    lidar_spin(R, 96)
    cam = W.camera(lens=60, fstop=4.0)
    fe = W.empty("Focus", (0, 0, 0.08)); focus_on(cam, fe)
    W.cam_key(cam, 1, (0.08, -0.92, 0.14), (0, 0, 0.085))
    W.cam_key(cam, 96, (0.03, -0.8, 0.13), (0, 0, 0.09))
    ease(cam)
    return 12, 96


def s6_backfill(M):
    R = W.build_robot(M)
    W.world_sky(elev=34, az=-150, strength=0.75, energy=4.2)
    W.build_field(M, (2.4, 1.8), (0, 0), hair=40000, clear=[(0, 0, 0.045)], length=0.03)
    W.mesh_obj("Hole", W.bm_cyl(0.03, 0.026, 0.02, 32, (0, 0, -0.0095)), M["hole"])
    mound = W.mesh_obj("SandFill", W.bm_sphere(0.031, (0, 0, 0), (1, 1, 0.22), 32, 12), M["sand"])
    mound.location = (0, 0, -0.012); mound.scale = (0.4, 0.4, 0.4); mound.keyframe_insert("scale", frame=1); mound.keyframe_insert("location", frame=1)
    mound.keyframe_insert("scale", frame=22); mound.keyframe_insert("location", frame=22)
    mound.location = (0, 0, 0.0); mound.scale = (1, 1, 1); mound.keyframe_insert("scale", frame=48); mound.keyframe_insert("location", frame=48)
    drive(R, 1, 0.0, 18, -W.HOP_X)
    # sand stream from the nozzle tip (z 0.075) to the hole
    stream = W.mesh_obj("Stream", W.bm_cyl(0.0035, 0.005, 1.0, 16, (0, 0, -0.5)), M["sand"])
    stream.location = (0, 0, 0.075)
    for f, sz in ((1, 0.0), (20, 0.0), (24, 0.075), (44, 0.075), (48, 0.0)):
        stream.scale = (1, 1, max(sz, 0.0001)); stream.keyframe_insert("scale", index=2, frame=f)
    grains = []
    import random
    rnd = random.Random(2)
    for i in range(36):
        g = W.mesh_obj("Grain", W.bm_sphere(0.0016, seg=8, rings=6), M["sand"])
        x, y = rnd.uniform(-0.006, 0.006), rnd.uniform(-0.006, 0.006)
        start = 21 + i % 24
        g.location = (x, y, 0.07); g.scale = (0, 0, 0); g.keyframe_insert("location", frame=start - 1); g.keyframe_insert("scale", frame=start - 1)
        g.scale = (1, 1, 1); g.keyframe_insert("scale", frame=start)
        g.location = (x * 2.5, y * 2.5, 0.0); g.keyframe_insert("location", frame=start + 2)
        g.scale = (0, 0, 0); g.keyframe_insert("scale", frame=start + 3)
    for o in (mound, R["root"], *R["wheels"]):
        ease(o)
    lidar_spin(R, 60)
    cam = W.camera(lens=60, fstop=4.0)
    fe = W.empty("Focus", (0, 0, 0.03)); focus_on(cam, fe)
    W.cam_key(cam, 1, (-0.66, -0.2, 0.25), (0, 0, 0.02))
    W.cam_key(cam, 60, (-0.6, -0.17, 0.235), (0, 0, 0.015))
    ease(cam)
    return 12, 60


def s7_aerial(M):
    R = W.build_robot(M)
    W.world_sky(elev=40, az=-120, strength=0.75, energy=4.2)
    W.build_field(M, (4.4, 2.8), (0.2, 0), hair=70000)
    for i, (x, y) in enumerate([(1.3, 0.55), (-1.1, -0.7), (1.6, -0.6)]):
        w = W.build_dandelion(M, "W%d" % i, seed=20 + i, scale=1.2); w.location = (x, y, 0)
    drive(R, 1, -1.0, 54, 0.75)
    for fc in _fcurves(R["root"]) + sum([_fcurves(w) for w in R["wheels"]], []):
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"
    lidar_spin(R, 54)
    cam = W.camera(lens=32, fstop=8.0)
    fe = W.empty("Focus", (0, 0, 0.2), R["root"]); focus_on(cam, fe)
    W.cam_key(cam, 1, (-0.6, -0.9, 2.3), (-0.3, 0, 0))
    W.cam_key(cam, 54, (0.6, -0.85, 2.2), (0.6, 0, 0))
    for fc in _fcurves(cam):
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"
    return 12, 54


def s8_carry(M):
    R = W.build_robot(M)
    W.world_studio()
    cam = W.camera(lens=45, fstop=5.6)
    fe = W.empty("Focus", (0, 0, 0.3)); focus_on(cam, fe)
    W.cam_key(cam, 1, (1.15, 1.25, 1.2), (0.02, 0.0, 0.2))
    W.cam_key(cam, 144, (0.95, 1.08, 1.05), (0.02, 0.0, 0.22))
    ease(cam)
    lidar_spin(R, 144)
    return 24, 144


def s9_end(M):
    R = W.build_robot(M)
    lights = W.world_studio()
    lidar_spin(R, 180)
    cam = W.camera(lens=50, fstop=4.0)
    fe = W.empty("Focus", (0.1, 0, 0.26)); focus_on(cam, fe)
    W.cam_key(cam, 1, (1.75, -1.0, 0.26), (0.0, 0.05, 0.27))
    W.cam_key(cam, 180, (1.45, -0.86, 0.3), (0.0, 0.0, 0.28))
    ease(cam)
    # rim light sweep for a sheen across the shell
    rl = lights["rim2"].data
    rl.energy = 40; rl.keyframe_insert("energy", frame=1)
    rl.energy = 220; rl.keyframe_insert("energy", frame=90)
    rl.energy = 150; rl.keyframe_insert("energy", frame=180)
    return 24, 180


SHOTS = {"s1": s1_open, "s2": s2_arrive, "s3": s3_orbit, "s4": s4_vision, "s5": s5_extract,
         "s6": s6_backfill, "s7": s7_aerial, "s8": s8_carry, "s9": s9_end}

# points to project for post overlays (robot-space)
TRACK = {
    "s7": {"robot": (0.0, 0.0, 0.3)},
    "s8": {"len_a": (-0.385, 0.36, 0.0), "len_b": (0.47, 0.36, 0.0),
           "wid_a": (0.52, -0.305, 0.0), "wid_b": (0.52, 0.305, 0.0),
           "grip": (0.0, -0.192, 0.41)},
    "s5": {"tip": (0.0, 0.0, 0.0)},
}


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    shot = args[0]
    mode = args[1] if len(args) > 1 else "full"
    W.reset()
    M = W.make_materials()
    fps, n = SHOTS[shot](M)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, n
    if mode == "preview":
        W.render_settings(640, 360, 10)
        f = int(args[2]) if len(args) > 2 else n // 2
        sc.frame_set(f)
        sc.render.filepath = os.path.join(OUT, "preview", f"{shot}_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        return
    W.render_settings(1280, 720, 16)
    d = os.path.join(OUT, shot)
    os.makedirs(d, exist_ok=True)
    if shot in TRACK:
        cam = sc.camera
        root = bpy.data.objects.get("WP1")
        track = {}
        for f in range(1, n + 1):
            sc.frame_set(f)
            pts = {}
            for k, p in TRACK[shot].items():
                wp = (root.matrix_world @ Vector(p)) if root else Vector(p)
                v = world_to_camera_view(sc, cam, wp)
                pts[k] = [v.x, 1 - v.y]
            track[f] = pts
        json.dump({"fps": fps, "n": n, "track": track}, open(os.path.join(d, "track.json"), "w"))
    json.dump({"fps": fps, "n": n}, open(os.path.join(d, "meta.json"), "w"))
    for f in range(1, n + 1):
        path = os.path.join(d, f"{f:04d}.png")
        if os.path.exists(path):
            continue
        t = time.time()
        sc.frame_set(f)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print(f"FRAME {shot} {f}/{n} {time.time() - t:.1f}s", flush=True)


if __name__ == "__main__":
    main()
