"""GRAVEYARD SHIFT stream intro: a preview video of the whole sequence (Blender 4.5, headless, EEVEE).

The stage as it ships (out_hw: the baked meshes on their textures, unlit, as the Quest shows them), the Horseman from
hw_rider.build() galloping along hw_intro_path's ride with the same camera rule the mod will use, then the showtime cut:
the wide shot from the front, the two crypt doors swinging out (v5; hw_materials.door_swing's rule, hw_intro_path.door_xy),
the user's avatar walking out to
the decks, the show's lights coming on.
v6: the Horseman is drawn as Unreal draws him by default: out_hw's SM_HwRider.fbx on its bake, every frame's vertices
decoded from T_HwRiderVAT.exr the way the material reads them (hw_rider.ue_decode, Unreal's V flip included).
v4/v5's preview rendered the Blender rig instead, which is how the broken VAT got past it. --live-rider: the old way.

Timeline (seconds): 0..14 the loop's last lap (press 1 at 4: he takes the exit at the loop's end), 14..26 the exit (the
camera stops following at hw_intro_path.CAM_HOLD_S, he vanishes round the nave), 26 press 2: the cut to the wide
shot, the door rises 27..31, the lights at 28.5, the walk 28.5..36.5, end at 38.

    blender -b --factory-startup --python hw_animatic.py -- [--out DIR] [--res 960x540] [--fps 30] [--from S] [--to S]
(under the GPU lock: ../run_blender_locked.sh <log> <this file> [args]); then ffmpeg makes hw_intro_preview.mp4
"""
import json
import math
import os
import subprocess
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
HERE = os.path.dirname(os.path.abspath(__file__))
STAGE = os.environ.get("HW_STAGE") or os.path.join(HERE, "..", "out_hw")   # HW_STAGE: preview another bake folder
sys.path.insert(0, HERE)
import hw_intro_path as ip  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import hw_rider as hr  # noqa: E402  (after the reset: its build() makes the rider in this scene)


def opt(name, default):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


OUT = opt("--out", os.path.join(HERE, "out_animatic"))
RES = tuple(int(v) for v in opt("--res", "960x540").split("x"))
FPS = int(opt("--fps", "30"))
T0, T1 = float(opt("--from", "0")), float(opt("--to", "39"))
TIMES = [float(v) for v in opt("--times", "").split(",") if v]     # render only these moments (a look check)
CAM_OVR = None                     # --cam X,Y,Z:TX,TY,TZ:LENS (Blender final frame): one camera for every frame rendered
if "--cam" in ARGS:
    _cp, _ct, _cl = opt("--cam", "").split(":")
    CAM_OVR = (tuple(float(v) for v in _cp.split(",")), tuple(float(v) for v in _ct.split(",")), float(_cl))
DOOR_OVR = [float(v) for v in opt("--door", "").split(",") if v]   # --door a,b,c: DoorOpen per --times moment
os.makedirs(OUT, exist_ok=True)
scene = bpy.context.scene
coll = scene.collection
STRIDE = ip.SPEED / hr.GALLOP_HZ
LOOP_START = 15.0                    # loop time at the video's start
T_PRESS2, T_LIGHTS, T_DOOR, T_WALK, T_END = 26.0, 27.5, 28.0, 30.0, 39.0   # the user: the press darkens
# the venue, then the visuals and the lights start (the deck plays); the door rises, they walk out


def log(msg):
    print(f"[ANIMATIC] {msg}", flush=True)


# ---------------------------------------------------------------- the stage as shipped (unlit, baked)
def ingame_rider():
    """v6: the rider exactly as Unreal draws it: SM_HwRider.fbx from out_hw, its bake (T_HwRider.png) as emission, and
    each frame's vertices from T_HwRiderVAT.exr through hw_rider.ue_decode (the UV channels as written, Unreal's V flip
    applied). -> state for ingame_pose(), or None when out_hw has no exported rider."""
    fbx, png = os.path.join(STAGE, "SM_HwRider.fbx"), os.path.join(STAGE, "T_HwRider.png")
    exr, js = os.path.join(STAGE, "T_HwRiderVAT.exr"), os.path.join(STAGE, "T_HwRiderVAT.json")
    if not all(os.path.exists(p) for p in (fbx, png, exr, js)):
        log("no exported rider in out_hw: the preview shows the Blender rig")
        return None
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=fbx, axis_forward="-Z", axis_up="Y")
    ob = next(o2 for o2 in bpy.data.objects if o2 not in before and o2.type == "MESH")
    for o2 in bpy.context.view_layer.objects:
        o2.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)   # mesh data = the rider's frame
    me = ob.data
    meta = json.load(open(js))
    n = len(me.vertices)
    if n != meta["vertices"]:
        raise RuntimeError(f"SM_HwRider.fbx has {n} vertices, the VAT {meta['vertices']}")
    written = {}
    for name in ("VatIndex", "VatRotScale", "VatScalePhase", "VatRate"):
        arr = np.zeros((n, 2))
        lay = me.uv_layers[name].data
        for poly in me.polygons:
            for li, v in zip(poly.loop_indices, poly.vertices):
                arr[v] = lay[li].uv
        written[name] = arr
    im = bpy.data.images.load(exr)
    im.colorspace_settings.name = "Non-Color"
    H, W = meta["height"], meta["width"]
    px = np.empty(W * H * 4, dtype=np.float32)
    im.pixels.foreach_get(px)
    tex = px.reshape(H, W, 4)[::-1].copy()                  # Blender's rows run bottom-up; the file's row 0 is the top
    base = np.empty(n * 3)
    me.vertices.foreach_get("co", base)
    me.uv_layers["UVMap"].active_render = True
    me.materials.clear()
    me.materials.append(emit_mat("A_SM_HwRider", image=bpy.data.images.load(png)))
    log(f"in-game rider: {n} verts, VAT {W}x{H}, {meta['frames_per_clip']} frames at {meta['loop_rate']} strides/s")
    return {"ob": ob, "me": me, "written": written, "tex": tex, "base": base.reshape(-1, 3), "meta": meta}


def ingame_pose(st, tau):
    m = st["meta"]
    p = (tau * m["loop_rate"]) % 1.0                      # the material plays on Time, not on the distance
    off = hr.ue_decode(st["written"], st["tex"], m["width"], m["rows_per_clip"], m["height"], p, m["frames_per_clip"])
    st["me"].vertices.foreach_set("co", (st["base"] + off).ravel())
    st["me"].update()


def emit_mat(name, image=None, rgb=(0, 0, 0), alpha=False, strength=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    if image is not None:
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = image
        nt.links.new(tx.outputs["Color"], em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = (*rgb, 1.0)
    if alpha and image is not None:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(tx.outputs["Alpha"], mix.inputs["Fac"])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
        m.blend_method = "BLEND"
        m.surface_render_method = "BLENDED"
    else:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def img(name):
    p = os.path.join(STAGE, name + ".png")
    return bpy.data.images.load(p, check_existing=True) if os.path.exists(p) else None


PAL = {"SM_HwGlow", "SM_HwWindows", "SM_HwEyes", "SM_HwLenses", "SM_HwClockFace", "SM_HwClockHands", "SM_HwBats",
       "SM_HwButton"}
ALPHA = {"SM_HwBeams": "T_HwBeam", "SM_HwSearch": "T_HwBeam", "SM_HwLasers": "T_HwBeam", "SM_HwHalos": "T_HwHalo"}
SKIP = {"SM_HwBolts", "SM_HwFire", "SM_HwFog", "SM_HwGhosts"}
SHOW_LIGHTS = []                     # beams, lasers, halos, searchlights, grounds beams: on at T_LIGHTS


STAGE_EMIT, SCREEN_EMIT = [], []      # emission nodes the showtime beat dims (the sky, moon and far ground stay)


def load_stage():
    names = [l.strip() for l in open(os.path.join(STAGE, "manifest.txt")) if l.strip()]
    objs = {}
    for n in names:
        if n in SKIP:
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=os.path.join(STAGE, n + ".fbx"), axis_forward="-Z", axis_up="Y")
        new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        if not new:
            continue
        ob = new[0]
        for o2 in bpy.context.view_layer.objects:
            o2.select_set(False)
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)   # mesh data = world (final frame)
        ob.data.materials.clear()
        if n in PAL:
            m = emit_mat("A_" + n, image=img("T_HwGlowPal"))
        elif n.startswith("SM_HwGroundsGlow"):
            m = emit_mat("A_" + n, image=img("T_HwGroundsPal"))
        elif n in ALPHA:
            m = emit_mat("A_" + n, image=img(ALPHA[n]), alpha=True)
            SHOW_LIGHTS.append(ob)
        elif n.startswith(("SM_HwGBeams", "SM_HwGHalos")):
            m = emit_mat("A_" + n, image=img("T_HwGroundsHalo" if "GHalos" in n else "T_HwGroundsBeam"), alpha=True)
            SHOW_LIGHTS.append(ob)                                # the grounds' beams (follow spots...) are show lights
        elif n == "SM_HwFarGround":
            m = emit_mat("A_" + n, rgb=(0.0015, 0.0015, 0.0025))
        elif n == "SM_HwPhones":
            m = emit_mat("A_" + n, rgb=(0.9, 0.55, 0.25))
        elif n == "SM_DinoVisualScreen":
            m = emit_mat("A_" + n, image=screen_image())
            me = ob.data
            xs = [v.co.x for v in me.vertices]
            zs = [v.co.z for v in me.vertices]
            uvl = me.uv_layers.active.data
            for poly in me.polygons:
                for li, vi in zip(poly.loop_indices, poly.vertices):
                    co = me.vertices[vi].co
                    uvl[li].uv = ((co.x - min(xs)) / (max(xs) - min(xs)), (co.z - min(zs)) / (max(zs) - min(zs)))
        else:
            t = img("T" + n[2:])
            m = emit_mat("A_" + n, image=t) if t is not None else emit_mat("A_" + n, rgb=(0.02, 0.02, 0.02))
        ob.data.materials.append(m)
        objs[n] = ob
        em = next((nd for nd in m.node_tree.nodes if nd.type == "EMISSION"), None)
        if em is not None and n not in ("SM_HwSky", "SM_HwMoon", "SM_HwFarGround"):
            (SCREEN_EMIT if n == "SM_DinoVisualScreen" else STAGE_EMIT).append(em)
    log(f"stage: {len(objs)} meshes from {STAGE}")
    return objs


def screen_image():
    """A frame of the GRAVEYARD SHIFT sting on the big screen (the intro song's visuals), else black."""
    deliver = "C:/Users/Chris/TribeUE/Visuals/halloween/deliver"
    png = os.path.join(OUT, "screen_frame.png")
    if not os.path.exists(png):
        stings = [f for f in os.listdir(deliver) if "Sting" in f or "sting" in f] if os.path.isdir(deliver) else []
        if stings:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "2.0", "-i", os.path.join(deliver, stings[0]),
                            "-frames:v", "1", png], check=False)
    return bpy.data.images.load(png) if os.path.exists(png) else None


# ---------------------------------------------------------------- the doors (door_swing's rule) and the walker
def gate_setup(ob):
    """Per vertex: its rest position and its leaf's side (UV 'GateData' u: -1 left, +1 right; else the side of x = 0),
    for gate_pose."""
    me = ob.data
    data = me.uv_layers["GateData"].data if "GateData" in me.uv_layers else None
    rest = np.array([v.co[:] for v in me.vertices])
    side = np.where(rest[:, 0] > 0, 1.0, -1.0)
    if data:
        for poly in me.polygons:
            for li, vi in zip(poly.loop_indices, poly.vertices):
                side[vi] = 1.0 if data[li].uv[0] > 0 else -1.0
    return rest, side


def gate_pose(ob, rest, side, d):
    """DoorOpen d: each leaf turns about its hinge (hw_intro_path.door_xy, hw_materials.door_swing)."""
    p = rest.copy()
    for s in (-1.0, 1.0):
        m = side == s
        a = math.radians(ip.door_turn_deg(s, d))
        hx, hy = s * ip.GATE_X, ip.GATE_Y
        dx, dy = rest[m, 0] - hx, rest[m, 1] - hy
        p[m, 0] = hx + dx * math.cos(a) - dy * math.sin(a)
        p[m, 1] = hy + dx * math.sin(a) + dy * math.cos(a)
    ob.data.vertices.foreach_set("co", p.ravel())
    ob.data.update()


WALK = [(-0.6, 9.2, -1.0), (-0.3, 7.2, -1.0), (-3.2, 4.6, -1.0), (-5.0, 2.4, -1.0), (-5.0, 1.6, -0.2), (-4.4, 1.3, 0.0),
        (-1.6, 1.0, 0.0), (0.0, 0.9, 0.0)]


STRIDE_W, HIP_W = 1.2, 0.92          # the walk: metres per full cycle (two steps); the hips' height over the floor


def walker():
    """The user's avatar with IK legs and arms (targets parented to it, in its local frame: it faces local -Y): the feet
    step along the floor, the hands swing opposite (the user asked for legs that walk, 2026-10-10)."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=hr.SKIN)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == "ARMATURE")
    for o in new:
        if o.type == "MESH" and not o.vertex_groups:
            bpy.data.objects.remove(o)
    targets = {}

    def emp(name, loc):
        e = bpy.data.objects.new(name, None)
        coll.objects.link(e)
        e.parent = arm
        e.location = loc
        return e
    for side, sx in (("Left", 1.0), ("Right", -1.0)):
        foot = emp(f"W_{side}Foot", (0.11 * sx, 0.0, -(HIP_W - 0.07)))
        knee = emp(f"W_{side}Knee", (0.12 * sx, -1.0, -0.45))
        c = arm.pose.bones[f"{side}Leg"].constraints.new("IK")
        c.target, c.pole_target, c.chain_count, c.pole_angle = foot, knee, 2, math.radians(-90)
        hand = emp(f"W_{side}Hand", (0.25 * sx, 0.0, -0.10))
        elbow = emp(f"W_{side}Elbow", (0.45 * sx, 0.6, 0.0))
        c = arm.pose.bones[f"{side}ForeArm"].constraints.new("IK")
        c.target, c.pole_target, c.chain_count, c.pole_angle = hand, elbow, 2, math.radians(-90)
        targets[side] = (foot, hand, sx)
    return arm, targets


def walk_pose(arm, u, t, targets=None):
    """u 0..1 along WALK (by length); the avatar's hips ride 0.95 m over the floor with a small step bob."""
    seg = [math.dist(WALK[i][:2], WALK[i + 1][:2]) + abs(WALK[i + 1][2] - WALK[i][2]) for i in range(len(WALK) - 1)]
    s = u * sum(seg)
    i = 0
    while i < len(seg) - 1 and s > seg[i]:
        s -= seg[i]
        i += 1
    a, b = Vector(WALK[i]), Vector(WALK[i + 1])
    f = min(1.0, s / seg[i]) if seg[i] else 0.0
    p = a.lerp(b, f)
    d = (b - a)
    yaw = math.atan2(d.x, -d.y) if d.length > 1e-6 and u < 0.999 else math.pi * 0.0
    moving = 0.0 < u < 1.0
    walked = u * sum(seg)
    phase = walked / STRIDE_W
    bob = 0.025 * abs(math.cos(2 * math.pi * phase)) if moving else 0.0
    arm.location = (p.x, p.y, p.z + (HIP_W if moving else 0.97) + bob)
    arm.rotation_euler = (0.0, 0.0, yaw)
    if targets:
        for side, (foot, hand, sx) in targets.items():
            a = 2 * math.pi * (phase + (0.0 if side == "Left" else 0.5))
            if moving:                                            # stance slides back under him, swing lifts forward
                foot.location = (0.11 * sx, -0.30 * math.sin(a), -(HIP_W - 0.07) + 0.11 * max(0.0, math.cos(a)))
                hand.location = (0.25 * sx, 0.13 * math.sin(a), -0.10)
            else:
                foot.location = (0.11 * sx, 0.0, -(0.97 - 0.07))
                hand.location = (0.25 * sx, 0.0, -0.10)


# ---------------------------------------------------------------- the ride: the mod's sample, the rider and the camera
(LOOP, LS), (EX, ES) = ip.path()
T_LOOP, T_EXIT, _, _ = ip.timing()


def ride_sample(tau):
    """(x, y, heading, distance travelled, camera blend 0 loop..1 exit, camera frozen?) at video time tau."""
    lt = LOOP_START + tau
    if lt < T_LOOP:
        x, y, d = ip.pose_at(LOOP, LS, ip.SPEED * lt)
        return x, y, d, ip.SPEED * lt, 0.0, False
    e = lt - T_LOOP
    s = ip.exit_s(min(e, T_EXIT))
    x, y, d = ip.pose_at(EX, ES, s)
    blend = min(1.0, e / 5.0)
    blend = blend * blend * (3 - 2 * blend)
    return x, y, d, ip.SPEED * T_LOOP + s, blend, e >= ip.CAM_HOLD_S


def frame_basis(d):
    f = Vector((d[0], d[1], 0.0)).normalized()
    left = Vector((0.0, 0.0, 1.0)).cross(f).normalized()
    return f, left


def cam_pose(x, y, d, blend):
    f, left = frame_basis(d)
    (c0, l0), (c1, l1) = ip.CAM_LOOP, ip.CAM_EXIT
    c = [c0[i] + (c1[i] - c0[i]) * blend for i in range(3)]
    lk = [l0[i] + (l1[i] - l0[i]) * blend for i in range(3)]
    base = Vector((x, y, ip.FIELD_Z))
    pos = base + f * c[0] + left * c[1] + Vector((0, 0, c[2]))
    tgt = base + f * lk[0] + left * lk[1] + Vector((0, 0, lk[2]))
    return pos, tgt


def aim(cam, pos, tgt):
    cam.location = pos
    cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()


# ---------------------------------------------------------------- main
objs = load_stage()
gate = objs.get("SM_HwGate")
g_rest, g_zc = gate_setup(gate) if gate else (None, None)
o = hr.build()
rig = o["rig"]
INGAME = None if "--live-rider" in ARGS else ingame_rider()
if INGAME:
    for _ob in o["parts"]:
        _ob.hide_render = True
for name, kind, parent_pos, power, col in (("RLantern", "POINT", o["lantern_c"], 70.0, (1.0, 0.62, 0.25)),
                                           ("RPumpkin", "POINT", o["pumpkin"].matrix_world.translation, 10.0,
                                            (1.0, 0.45, 0.1))):
    ld = bpy.data.lights.new(name, kind)
    ld.energy, ld.color, ld.shadow_soft_size = power, col, 0.05
    lo = bpy.data.objects.new(name, ld)
    coll.objects.link(lo)
    lo.location = parent_pos
    lo.parent = rig
    lo.matrix_parent_inverse = rig.matrix_world.inverted()
sun = bpy.data.lights.new("Moon", "SUN")
sun.energy, sun.color = 0.35, (0.55, 0.65, 1.0)
so = bpy.data.objects.new("Moon", sun)
coll.objects.link(so)
so.rotation_euler = Vector((0.3, -1.0, -0.6)).to_track_quat("-Z", "Y").to_euler()
walk_arm, walk_targets = walker()
spill = bpy.data.lights.new("GateSpill", "AREA")
spill.energy, spill.color, spill.size = 180.0, (1.0, 0.3, 0.1), 2.5
sp = bpy.data.objects.new("GateSpill", spill)
coll.objects.link(sp)
sp.location = (0.0, 8.6, 1.4)
sp.rotation_euler = Vector((0.0, -1.0, -0.3)).to_track_quat("-Z", "Y").to_euler()
front = bpy.data.lights.new("Front", "AREA")
front.energy, front.size = 60.0, 4.0
fo = bpy.data.objects.new("Front", front)
coll.objects.link(fo)
fo.location = (0.0, -2.0, 3.0)
fo.rotation_euler = Vector((0.0, 1.0, -0.4)).to_track_quat("-Z", "Y").to_euler()
w = bpy.data.worlds.new("Night")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.0, 0.0, 0.0, 1)
scene.world = w
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.eevee.taa_render_samples = 8
scene.render.resolution_x, scene.render.resolution_y = RES
scene.view_settings.view_transform = "Standard"
cd = bpy.data.cameras.new("cam")
cd.clip_start, cd.clip_end = 0.05, 2000.0
cam = bpy.data.objects.new("cam", cd)
coll.objects.link(cam)
scene.camera = cam
held = None
n0, n1 = int(T0 * FPS), int(T1 * FPS)
frames = [int(round(t * FPS)) for t in TIMES] if TIMES else list(range(n0, n1))
for k_fr, fi in enumerate(frames):
    tau = fi / FPS
    if tau < T_PRESS2:                                               # the woods: follow the rider
        x, y, d, dist, blend, freeze = ride_sample(tau)
        rig.location = (x, y, ip.FIELD_Z)
        rig.rotation_euler = (0.0, 0.0, math.atan2(d[0], -d[1]))
        lt = LOOP_START + tau
        moving = not (lt >= T_LOOP and lt - T_LOOP >= T_EXIT)
        hr.gallop(rig, (dist / STRIDE) % 1.0 if moving else 0.0)
        if INGAME:                                                   # in game he is hidden once the exit ends
            INGAME["ob"].location, INGAME["ob"].rotation_euler = rig.location, rig.rotation_euler
            INGAME["ob"].hide_render = not moving
            ingame_pose(INGAME, tau)
        if freeze and held is None:
            held = cam_pose(x, y, d, blend)
        pos, tgt = held if held else cam_pose(x, y, d, blend)
        cd.lens = 22
        walk_arm.location = (0.0, 9.2, -0.05)
        for ob in SHOW_LIGHTS:
            ob.hide_render = True
        for em in STAGE_EMIT + SCREEN_EMIT:
            em.inputs["Strength"].default_value = 1.0
        door = 0.0
    else:                                                            # showtime: the wide shot
        rig.location = (0.0, 0.0, -50.0)
        if INGAME:
            INGAME["ob"].hide_render = True
        (pos, tgt), cd.lens = ip.WIDE, 28
        up = min(1.0, max(0.0, (tau - T_LIGHTS) / 1.0))           # dark at the press, then the lights fade up
        for em in STAGE_EMIT:
            em.inputs["Strength"].default_value = 0.15 + 0.85 * up
        for em in SCREEN_EMIT:
            em.inputs["Strength"].default_value = up
        door = min(1.0, max(0.0, (tau - T_DOOR) / 4.0))
        door = door * door * (3 - 2 * door)
        u = min(1.0, max(0.0, (tau - T_WALK) / 8.0))
        walk_pose(walk_arm, u, tau, walk_targets)
        for ob in SHOW_LIGHTS:
            ob.hide_render = tau < T_LIGHTS
    if CAM_OVR:
        pos, tgt, cd.lens = CAM_OVR
    if DOOR_OVR:
        door = DOOR_OVR[min(k_fr, len(DOOR_OVR) - 1)]
    if gate is not None:
        gate_pose(gate, g_rest, g_zc, door)
    aim(cam, pos, tgt)
    bpy.context.view_layer.update()
    scene.render.filepath = os.path.join(OUT, f"frame_{fi:04d}.png")
    bpy.ops.render.render(write_still=True)
    if fi % 30 == 0:
        log(f"frame {fi} (t {tau:.1f} s)")
mp4 = os.path.join(OUT, "hw_intro_preview.mp4")
if not TIMES:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-start_number", str(n0), "-i",
                    os.path.join(OUT, "frame_%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", mp4],
                   check=False)
    log(f"video {mp4} ({n1 - n0} frames)")
log("done")
