import sys, time, math
sys.path.insert(0, "/home/user/Weed-puller/video")
import wp_scene as W
import bpy
from mathutils import Vector
OUT = "/tmp/claude-0/-home-user-Weed-puller/571bce08-90d0-5b92-a2f2-2f45f5138329/scratchpad/vid/"
mode = sys.argv[-1]
W.reset(); M = W.make_materials(); R = W.build_robot(M)
W.render_settings(1280, 720, 16)
if mode == "studio":
    W.world_studio()
    cam = W.camera(lens=50, fstop=5.6); cam.location = (1.55, 1.25, 0.62); W.look(cam, (0, 0, 0.22))
    cam.data.dof.focus_distance = (cam.location - Vector((0, 0, 0.22))).length
else:
    W.world_sky()
    d = W.build_dandelion(M, seed=3); d.location = (0.75, 0.05, 0)
    W.build_field(M, (3.0, 3.0), (0.3, 0), hair=45000, clear=[(0.75, 0.05, 0.05)])
    cam = W.camera(lens=45, fstop=2.8); cam.location = (1.75, -0.75, 0.2); W.look(cam, (0.35, 0, 0.16))
    cam.data.dof.focus_distance = 1.6
t = time.time()
bpy.context.scene.render.filepath = OUT + "test_" + mode + ".png"
bpy.ops.render.render(write_still=True)
print("RENDER_SECONDS", round(time.time() - t, 1))
