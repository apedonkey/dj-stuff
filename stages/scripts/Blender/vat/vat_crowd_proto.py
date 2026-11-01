# VAT (vertex animation texture) prototype for the Dino Stage crowd (Blender 4.5, headless):
#   D:\Tools\blender-4.5.14-windows-x64\blender.exe -b --factory-startup --python vat_crowd_proto.py [-- --frame 17 --no-preview]
#
# One low-poly festival-goer in the style of dino_stage.person() (detail 2), an 11-bone rig, two procedurally keyed
# 1-second loops ("jump": hands up, two hops; "pump": right fist pump on both beats), baked into a VAT: per-vertex
# position OFFSETS from the rest pose, one texel column per vertex, one texel row per frame. Writes into ./out:
#   T_VAT_Person.exr        RGBA half-float VAT (what ships: Unreal stores it bit-exact with Compression = HDR)
#   T_VAT_Person_16.png     the same offsets normalized to 16-bit (fallback; decode with the min/max in the JSON)
#   SM_VatPerson.fbx        the static rest mesh; UV1.x = the vertex's VAT column
#   SM_VatCrowdTest.fbx     5x5 people carrying the per-person data the real merged crowd would use (UV1..UV3)
#   VAT_Person.json         everything the material needs (sizes, frames, rows, decode ranges, UV layout, bounds)
#   vat_person.blend        rig + the two actions, for hand-editing the dances
#   preview_vat_frames.png  contact sheet decoded FROM the written EXR (rows = clips, columns = every 3rd frame)
#   verify_report.json      the measured verification numbers
# and VERIFIES: every frame decoded from the written files (via Blender's own EXR/PNG readers) against the evaluated
# armature-deformed mesh, a fresh re-evaluation of frame N, and the test crowd (re-imported from its FBX) pushed through
# a numpy copy of the Unreal material graph in DESIGN.md against the expected per-person positions.
#
# Space: canonical person in meters, feet on z=0, facing +Y (the stage), the person's right hand on +X.
import json
import math
import os
import random
import struct
import sys
import time
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
CHECK_FRAME = int(ARGS[ARGS.index("--frame") + 1]) if "--frame" in ARGS else 17
PREVIEW = "--no-preview" not in ARGS

FPS = 30
FRAMES = 30                     # frames per clip: 1.0 s = 2 beats at the authored 120 BPM
ROWS = FRAMES + 1               # each clip also stores a copy of its frame 0, so the material's lerp never wraps
CLIPS = ("jump", "pump")
AUTHORED_BPM, BEATS_PER_CLIP = 120.0, 2
H, W = 1.75, 0.44               # canonical body (dino_stage draws h 1.55-1.92, w 0.38-0.5 per person)
HIP, SH, HEAD = H * 0.50, H * 0.80, H * 0.915
SHX = W * 0.47
SHIRT, PANTS, SKIN = (0.55, 0.04, 0.04), (0.04, 0.06, 0.14), (0.80, 0.58, 0.45)
UE_AXIS = (100.0, -100.0, 100.0)  # Blender m -> Unreal cm; the FBX path mirrors Y (build_dino.log: y +10.9 m -> -1090 cm)
UE_FLIPS_V = True                  # Unreal's legacy FBX importer stores 1 - V; if a UE test shows it does not, set False
T0 = time.time()


def log(msg):
    print("[VAT] " + msg, flush=True)


def V3(x, y, z):
    return Vector((x, y, z))


# ---------------------------------------------------------------- file writers (no Blender colour management involved)
def write_exr(path, rgba, half=True):
    """Uncompressed scanline OpenEXR. rgba: HxWx4 floats, row 0 = TOP of the image (Unreal's V = 0)."""
    h, w, _ = rgba.shape
    dt = np.dtype("<f2") if half else np.dtype("<f4")

    def attr(name, typ, data):
        return name.encode() + b"\0" + typ.encode() + b"\0" + struct.pack("<i", len(data)) + data
    chl = b"".join(c.encode() + b"\0" + struct.pack("<iBBBBii", 1 if half else 2, 0, 0, 0, 0, 1, 1) for c in "ABGR") + b"\0"
    hdr = struct.pack("<ii", 20000630, 2)
    hdr += attr("channels", "chlist", chl)
    hdr += attr("compression", "compression", b"\0")                     # NO_COMPRESSION
    hdr += attr("dataWindow", "box2i", struct.pack("<iiii", 0, 0, w - 1, h - 1))
    hdr += attr("displayWindow", "box2i", struct.pack("<iiii", 0, 0, w - 1, h - 1))
    hdr += attr("lineOrder", "lineOrder", b"\0")                         # INCREASING_Y: first line stored = top row
    hdr += attr("pixelAspectRatio", "float", struct.pack("<f", 1.0))
    hdr += attr("screenWindowCenter", "v2f", struct.pack("<ff", 0.0, 0.0))
    hdr += attr("screenWindowWidth", "float", struct.pack("<f", 1.0))
    hdr += b"\0"
    line = w * 4 * dt.itemsize
    first = len(hdr) + 8 * h
    out = bytearray(hdr) + struct.pack(f"<{h}Q", *[first + y * (8 + line) for y in range(h)])
    for y in range(h):
        px = rgba[y].astype(dt)
        out += struct.pack("<ii", y, line) + b"".join(px[:, c].tobytes() for c in (3, 2, 1, 0))  # channels A,B,G,R
    open(path, "wb").write(out)


def write_png16(path, rgba16):
    """16-bit RGBA PNG. rgba16: HxWx4 uint16, row 0 = top."""
    h, w, _ = rgba16.shape
    raw = b"".join(b"\x00" + rgba16[y].astype(">u2").tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 16, 6, 0, 0, 0))
    open(path, "wb").write(png + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def read_with_blender(path):
    """Decode an image with Blender's own readers (an implementation independent of the writers above)."""
    img = bpy.data.images.load(path, check_existing=False)
    img.colorspace_settings.name = "Non-Color"
    img.reload()
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    is_float = img.is_float
    bpy.data.images.remove(img)
    return buf.reshape(h, w, 4)[::-1], is_float                        # Blender rows are bottom-up


# ---------------------------------------------------------------- scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 0, FRAMES
coll = scene.collection


def link(ob):
    coll.objects.link(ob)
    return ob


# ---------------------------------------------------------------- the person (style of dino_stage.person, detail 2)
J = {}
for _s, _side in ((1, "R"), (-1, "L")):                                # facing +Y: the right hand is on +X
    J["foot." + _side] = V3(_s * 0.09, 0, 0.03)
    J["knee." + _side] = V3(_s * 0.095, 0, 0.45)
    J["hip." + _side] = V3(_s * 0.10, 0, HIP)
    J["shoulder." + _side] = V3(_s * SHX, 0, SH - 0.04)                 # person(): arms in the "down" pose
    J["elbow." + _side] = V3(_s * (SHX + 0.05), 0.02, HIP + 0.18)
    J["hand." + _side] = V3(_s * (SHX + 0.04), 0.06, HIP - 0.12)
WAIST, NECK = V3(0, 0, 0.92), V3(0, 0, SH + 0.05)
BONES = [("pelvis", V3(0, 0, HIP), V3(0, 0, HIP + 0.1), None),          # name, head, tail, parent
         ("spine", WAIST, V3(0, 0, SH - 0.05), "pelvis"),
         ("head", NECK, V3(0, 0, H + 0.02), "spine")]
for _side in "RL":
    BONES += [(f"upperarm.{_side}", J[f"shoulder.{_side}"], J[f"elbow.{_side}"], "spine"),
              (f"forearm.{_side}", J[f"elbow.{_side}"], J[f"hand.{_side}"], f"upperarm.{_side}"),
              (f"thigh.{_side}", J[f"hip.{_side}"], J[f"knee.{_side}"], "pelvis"),
              (f"shin.{_side}", J[f"knee.{_side}"], J[f"foot.{_side}"], f"thigh.{_side}")]


def limb(bm, a, b, r0, r1, segs, caps=True, squash=1.0):
    """Verbatim from dino_stage.py: tapered cylinder from a (radius r0) to b (radius r1)."""
    d = b - a
    if d.length < 1e-4:
        return
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    m = Matrix.Translation((a + b) / 2) @ rot @ Matrix.Diagonal(Vector((1.0, squash, 1.0, 1.0)))
    bmesh.ops.create_cone(bm, cap_ends=caps, segments=segs, radius1=r0, radius2=r1, depth=d.length, matrix=m)


def ring_tube(bm, pts, radii, segs, cap_first, cap_last):
    """Tube with one vertex ring per point (so a joint ring can be shared by two bones); returns the rings."""
    rings = []
    for i, (p, r) in enumerate(zip(pts, radii)):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        e1 = (Vector((1, 0, 0)) - t * t.x).normalized()
        e2 = t.cross(e1)
        rings.append([bm.verts.new(p + (e1 * math.cos(2 * math.pi * j / segs) + e2 * math.sin(2 * math.pi * j / segs)) * r)
                      for j in range(segs)])
    for a, b in zip(rings, rings[1:]):
        for j in range(segs):
            bm.faces.new((a[j], a[(j + 1) % segs], b[(j + 1) % segs], b[j]))   # CCW about t: outward normals
    if cap_first:
        bm.faces.new(list(reversed(rings[0])))
    if cap_last:
        bm.faces.new(rings[-1])
    return rings


def build_person():
    """Returns (bmesh, per-vertex {bone: weight}, per-face albedo). Legs get a knee (a shared ring, 50/50 skinned) so
    they can bend; torso: bottom ring on the pelvis, top ring on the spine; head and the two-part arms are rigid."""
    bm = bmesh.new()
    part_v, ring_v = bm.verts.layers.int.new("part"), bm.verts.layers.int.new("ring")
    part_f = bm.faces.layers.int.new("part")
    parts = []                                       # part id -> (albedo, weight_of(vert, ring) -> {bone: weight})

    def add(make, col, weight_of):
        """Tags what make() creates with a part id. BMesh iteration order is NOT creation order (ops free and reuse
        element slots), so parts are found by tag, never by index ranges."""
        for e in (*bm.verts, *bm.faces):
            e.tag = True
        made = make()
        pid = len(parts)
        parts.append((col, weight_of))
        for e, layer in [(v, part_v) for v in bm.verts] + [(f, part_f) for f in bm.faces]:
            if not e.tag:
                e[layer], e.tag = pid, True
        return made
    for side in "RL":                                                  # ring 0 = foot, 1 = knee, 2 = hip
        rings = add(lambda: ring_tube(bm, [J[f"foot.{side}"], J[f"knee.{side}"], J[f"hip.{side}"]], [0.06, 0.072, 0.085],
                                      6, True, False),                 # the top end hides inside the torso
                    PANTS, lambda v, r, side=side: ({f"shin.{side}": 1.0}, {f"shin.{side}": 0.5, f"thigh.{side}": 0.5},
                                                    {f"thigh.{side}": 1.0})[r])
        for r, ring in enumerate(rings):
            for v in ring:
                v[ring_v] = r
    mid = (HIP - 0.06 + SH) / 2
    add(lambda: limb(bm, V3(0, 0, HIP - 0.06), V3(0, 0, SH), W * 0.34, W * 0.47, 8, squash=0.62), SHIRT,
        lambda v, r: {"pelvis": 1.0} if v.co.z < mid else {"spine": 1.0})
    add(lambda: bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.115,      # 20 tris, like every person() head
                                           matrix=Matrix.Translation(V3(0, 0, HEAD)) @ Matrix.Diagonal(Vector((1.0, 1.1, 1.2, 1.0)))),
        SKIN, lambda v, r: {"head": 1.0})
    for side in "RL":
        add(lambda: limb(bm, J[f"shoulder.{side}"], J[f"elbow.{side}"], 0.055, 0.045, 5), SHIRT,
            lambda v, r, side=side: {f"upperarm.{side}": 1.0})
        add(lambda: limb(bm, J[f"elbow.{side}"], J[f"hand.{side}"], 0.045, 0.04, 5), SKIN,
            lambda v, r, side=side: {f"forearm.{side}": 1.0})
    bm.verts.index_update()
    bm.faces.index_update()
    for f in bm.faces:                                                 # a face never mixes parts
        if any(v[part_v] != f[part_f] for v in f.verts):
            raise RuntimeError("part tagging is inconsistent")
    weights = [parts[v[part_v]][1](v, v[ring_v]) for v in bm.verts]     # final (mesh) order
    colors = [parts[f[part_f]][0] for f in bm.faces]
    bm.verts.layers.int.remove(part_v)
    bm.verts.layers.int.remove(ring_v)
    bm.faces.layers.int.remove(part_f)
    return bm, weights, colors


def label_uvs(uvl, faces, px, py, z0, h, cell, cols):
    """dino_stage.build_crowd's per-person UV cell: wrapped like a bottle label (angle -> u, height -> v)."""
    cs = 1.0 / cols
    pad = cs * 0.06
    ox, oy = (cell % cols) * cs + pad, (cell // cols) * cs + pad
    span = cs - 2 * pad
    for f in faces:
        c = f.calc_center_median()
        ac = math.atan2(c.x - px, -(c.y - py))
        for loop in f.loops:
            v = loop.vert.co
            a = math.atan2(v.x - px, -(v.y - py)) if math.hypot(v.x - px, v.y - py) > 1e-4 else ac
            if abs(a - ac) > math.pi:
                a += 2 * math.pi if a < ac else -2 * math.pi
            u = min(max((a + math.pi) / (2 * math.pi), 0.0), 1.0)
            w_ = min(max((v.z - z0) / (h + 0.75), 0.0), 1.0)
            loop[uvl].uv = (ox + u * span, oy + w_ * span)


bm, WEIGHTS, FACE_COLS = build_person()
col_layer = bm.loops.layers.float_color.new("Col")
uv0 = bm.loops.layers.uv.new("UVMap")
bm.faces.ensure_lookup_table()
for f, c in zip(bm.faces, FACE_COLS):
    for loop in f.loops:
        loop[col_layer] = (*c, 1.0)
label_uvs(uv0, bm.faces, 0.0, 0.0, 0.0, H, 0, 1)
FACES = [[v.index for v in f.verts] for f in bm.faces]                 # loop order, canonical vertex ids
person_me = bpy.data.meshes.new("VatPerson")
bm.to_mesh(person_me)
bm.free()
for p in person_me.polygons:
    p.use_smooth = True       # unlit material: normals are unused, smooth export = fewer split vertices in Unreal
person = link(bpy.data.objects.new("VatPerson", person_me))
NV = len(person_me.vertices)
REST = np.array([v.co[:] for v in person_me.vertices], dtype=np.float64)
person_me.calc_loop_triangles()
NTRI = len(person_me.loop_triangles)
log(f"person: {NV} verts, {NTRI} tris, {len(person_me.polygons)} faces")

# ---------------------------------------------------------------- rig
arm_data = bpy.data.armatures.new("VatRig")
rig = link(bpy.data.objects.new("VatRig", arm_data))
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
for name, head, tail, parent in BONES:
    eb = arm_data.edit_bones.new(name)
    eb.head, eb.tail, eb.roll = head, tail, 0.0
    if parent:
        eb.parent = arm_data.edit_bones[parent]
        eb.use_connect = False
bpy.ops.object.mode_set(mode="OBJECT")
B_REST = {b.name: b.matrix_local.copy() for b in arm_data.bones}
for name, *_ in BONES:
    person.vertex_groups.new(name=name)
for i, wd in enumerate(WEIGHTS):
    for bone, w in wd.items():
        person.vertex_groups[bone].add([i], w, "REPLACE")
mod = person.modifiers.new("Armature", "ARMATURE")
mod.object = rig


# ---------------------------------------------------------------- procedural dances
# Every bone gets G = its rest->pose deformation in armature space (posed point = G @ rest point). The keyed local
# basis is then B_rest^-1 @ G_parent^-1 @ G @ B_rest (Blender: pose = parent_pose @ parent_rest^-1 @ rest @ basis).
def Tm(v):
    return Matrix.Translation(v)


def about(pivot, r3):
    return Tm(pivot) @ r3.to_4x4() @ Tm(-pivot)


def Rx(deg):
    return Matrix.Rotation(math.radians(deg), 3, "X")


def Ry(deg):
    return Matrix.Rotation(math.radians(deg), 3, "Y")


def Rz(deg):
    return Matrix.Rotation(math.radians(deg), 3, "Z")


def leg_ik(side, g_pelvis, foot_lift):
    """Two-bone IK: hip joint follows the pelvis, the foot goes to its rest spot lifted by foot_lift, knee bends +Y."""
    hip0, knee0, foot0 = J[f"hip.{side}"], J[f"knee.{side}"], J[f"foot.{side}"]
    hip1, foot1 = g_pelvis @ hip0, foot0 + V3(0, 0, foot_lift)
    l1, l2 = (knee0 - hip0).length, (foot0 - knee0).length
    dv = foot1 - hip1
    d = min(dv.length, l1 + l2 - 1e-5)
    u = dv.normalized()
    a = math.acos(max(-1.0, min(1.0, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d))))
    knee1 = hip1 + (Matrix.Rotation(a, 3, u.cross(V3(0, 1, 0)).normalized()) @ u) * l1
    rt = (knee0 - hip0).normalized().rotation_difference((knee1 - hip1).normalized()).to_matrix()
    rs = (foot0 - knee0).normalized().rotation_difference((foot1 - knee1).normalized()).to_matrix()
    return Tm(hip1) @ rt.to_4x4() @ Tm(-hip0), Tm(knee1) @ rs.to_4x4() @ Tm(-knee0)


def arm(g, side, s, elev, splay, flex):
    """elev: raise the arm forward/up about X (0 = hanging, 180 = straight up); splay: outward about Y; flex: elbow."""
    gu = g["spine"] @ about(J[f"shoulder.{side}"], Ry(s * splay) @ Rx(elev))
    return gu, gu @ about(J[f"elbow.{side}"], Rx(flex))


def pose(clip, p):
    """G per bone at loop position p in [0, 1); each clip is two beats, q = position inside the beat."""
    q = (2.0 * p) % 1.0
    g = {}
    if clip == "jump":                                                 # hands up, hop on every beat
        air_part = 0.45
        if q < air_part:
            air, crouch, tuck = 0.20 * math.sin(math.pi * q / air_part), 0.0, 0.07 * math.sin(math.pi * q / air_part)
        else:
            air, crouch, tuck = 0.0, 0.11 * math.sin(math.pi * (q - air_part) / (1 - air_part)), 0.0
        k = crouch / 0.11
        g["pelvis"] = Tm(V3(0, -0.25 * crouch, air - crouch))
        g["spine"] = g["pelvis"] @ about(WAIST, Rx(-(10 * k - 3 * air / 0.2)))     # lean in, arch in the air
        g["head"] = g["spine"] @ about(NECK, Rx(-6 * k))
        for side, s in (("R", 1), ("L", -1)):
            g[f"upperarm.{side}"], g[f"forearm.{side}"] = arm(g, side, s, 150 + 12 * math.sin(2 * math.pi * q), 18, 25 + 25 * k)
        foot_lift = air + tuck
    else:                                                              # right fist pump on the beat, knee bounce
        pump = (0.5 + 0.5 * math.cos(2 * math.pi * (q - 0.12))) ** 3
        bounce = 0.045 * (0.5 + 0.5 * math.cos(2 * math.pi * q)) ** 2
        g["pelvis"] = Tm(V3(0, -0.2 * bounce, -bounce))
        g["spine"] = g["pelvis"] @ about(WAIST, Rz(6 * pump) @ Rx(4 * pump))       # pumping shoulder forward, lean back
        g["head"] = g["spine"] @ about(NECK, Rx(-(4 + 8 * pump)))
        g["upperarm.R"], g["forearm.R"] = arm(g, "R", 1, 95 + 70 * pump, 12 + 6 * pump, 100 - 85 * pump)
        g["upperarm.L"], g["forearm.L"] = arm(g, "L", -1, 12 + 6 * pump, 4, 20 + 5 * pump)
        foot_lift = 0.0
    for side in "RL":
        g[f"thigh.{side}"], g[f"shin.{side}"] = leg_ik(side, g["pelvis"], foot_lift)
    return g


def use_action(act):
    ad = rig.animation_data or rig.animation_data_create()
    ad.action = act
    if hasattr(ad, "action_slot") and ad.action_slot is None and len(getattr(act, "slots", [])):
        ad.action_slot = act.slots[0]                                  # Blender 4.4+ slotted actions


ACTIONS = {}
for clip in CLIPS:
    act = bpy.data.actions.new(f"VAT_{clip}")
    act.use_fake_user = True
    use_action(act)
    prev = {}
    for f in range(FRAMES + 1):                                        # frame FRAMES == frame 0: seamless loop
        g = pose(clip, (f % FRAMES) / FRAMES)
        for name, _h, _t, parent in BONES:
            pb = rig.pose.bones[name]
            pb.rotation_mode = "QUATERNION"
            basis = B_REST[name].inverted() @ (g[parent].inverted() if parent else Matrix.Identity(4)) @ g[name] @ B_REST[name]
            loc, rot, scl = basis.decompose()
            if name in prev and rot.dot(prev[name]) < 0:
                rot.negate()                                           # keep quaternions continuous for scrubbing
            prev[name] = rot
            pb.location, pb.rotation_quaternion, pb.scale = loc, rot, (1.0, 1.0, 1.0)
            pb.keyframe_insert("location", frame=f, group=name)
            pb.keyframe_insert("rotation_quaternion", frame=f, group=name)
    ACTIONS[clip] = act
log(f"keyed {len(CLIPS)} actions x {FRAMES + 1} keys, {len(BONES)} bones")


# ---------------------------------------------------------------- bake (evaluate the deformed mesh every frame)
def evaluated_positions(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    a = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", a)
    ev.to_mesh_clear()
    return a.reshape(-1, 3)


W_MAT = np.zeros((NV, len(BONES)))
BONE_IDX = {b[0]: i for i, b in enumerate(BONES)}
for i, wd in enumerate(WEIGHTS):
    for bone, w in wd.items():
        W_MAT[i, BONE_IDX[bone]] = w
POS = {}
rig_err_bone = rig_err_lbs = 0.0
for clip in CLIPS:
    use_action(ACTIONS[clip])
    POS[clip] = np.zeros((FRAMES + 1, NV, 3))
    for f in range(FRAMES + 1):
        scene.frame_set(f)
        POS[clip][f] = evaluated_positions(person)
        g = pose(clip, (f % FRAMES) / FRAMES)                          # independent check of the rig itself
        dg = bpy.context.evaluated_depsgraph_get()
        rig_ev = rig.evaluated_get(dg)
        for name, *_ in BONES:
            rig_err_bone = max(rig_err_bone, max(abs(a - b) for ra, rb in zip(rig_ev.pose.bones[name].matrix, g[name] @ B_REST[name])
                                                 for a, b in zip(ra, rb)))
        lbs = np.zeros((NV, 3))
        for name, *_ in BONES:
            m = np.array(g[name])
            lbs += W_MAT[:, BONE_IDX[name], None] * (REST @ m[:3, :3].T + m[:3, 3])
        rig_err_lbs = max(rig_err_lbs, float(np.abs(lbs - POS[clip][f]).max()))
log(f"rig check: bone matrices vs procedural pose max {rig_err_bone:.2e}; mesh vs numpy skinning max {rig_err_lbs * 100:.5f} cm")
if rig_err_lbs > 1e-4:
    raise RuntimeError("the armature does not deform the mesh the way the procedural pose says")

OFF = np.stack([POS[c] - REST[None] for c in CLIPS])                   # clips x (FRAMES+1) x NV x 3, meters
TEX_W = 1 << (NV - 1).bit_length()
TEX_H = 1 << (len(CLIPS) * ROWS - 1).bit_length()
tex = np.zeros((TEX_H, TEX_W, 4), dtype=np.float32)
tex[..., 3] = 1.0
for ci in range(len(CLIPS)):
    tex[ci * ROWS:(ci + 1) * ROWS, :NV, :3] = OFF[ci]
EXR_PATH = os.path.join(OUT, "T_VAT_Person.exr")
write_exr(EXR_PATH, tex, half=True)
omin, omax = OFF.reshape(-1, 3).min(0), OFF.reshape(-1, 3).max(0)
rng_ = np.maximum(omax - omin, 1e-6)
norm = np.clip((tex[..., :3] - omin) / rng_, 0.0, 1.0)                # padding texels decode to offset 0 as well
png = np.empty((TEX_H, TEX_W, 4), dtype=np.uint16)
png[..., :3] = np.round(norm * 65535.0).astype(np.uint16)
png[..., 3] = 65535
PNG_PATH = os.path.join(OUT, "T_VAT_Person_16.png")
write_png16(PNG_PATH, png)
log(f"VAT {TEX_W}x{TEX_H}: EXR half {os.path.getsize(EXR_PATH)} B, PNG16 {os.path.getsize(PNG_PATH)} B; "
    f"offset range m min {np.round(omin, 3).tolist()} max {np.round(omax, 3).tolist()}")


# ---------------------------------------------------------------- static meshes for Unreal
def export_fbx(ob, name):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"}, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",
                             mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False, use_mesh_modifiers=False)
    return path


def person_data_uvs(vid, clip, yaw, sx, sz, mirror, phase):
    """The per-vertex data layout (Blender side). V is stored PRE-FLIPPED (1 - value) because Unreal's FBX importer
    writes 1 - V; Unreal then reads exactly: UV1 = (vertex, clip), UV2 = (sx cos yaw, sx sin yaw), UV3 = (+-sz, phase)."""
    f = (lambda x: 1.0 - x) if UE_FLIPS_V else (lambda x: x)
    return ((vid, f(clip)), (sx * math.cos(yaw), f(sx * math.sin(yaw))), (mirror * sz, f(phase)))


DATA_UV_NAMES = ("VatIndex", "VatRotScale", "VatScalePhase")
CROWD_PEOPLE = []


def build_static(name, people):
    """Merged static mesh: one copy of the rest person per entry (pos, yaw, sx, sz, mirror, clip, phase)."""
    bm2 = bmesh.new()
    uvs = [bm2.loops.layers.uv.new("UVMap")] + [bm2.loops.layers.uv.new(n) for n in DATA_UV_NAMES]
    colx = bm2.loops.layers.float_color.new("Col")
    cols = math.ceil(math.sqrt(len(people)))
    for k, (pos, yaw, sx, sz, mirror, clip, phase) in enumerate(people):
        m = np.array(Matrix.Translation(pos) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Diagonal(Vector((sx * mirror, sx, sz, 1.0))))
        world = REST @ m[:3, :3].T + m[:3, 3]
        verts = [bm2.verts.new(c) for c in world]
        faces = []
        for fv, c in zip(FACES, FACE_COLS):
            ids = list(reversed(fv)) if mirror < 0 else fv             # mirrored copy: flip the winding
            f = bm2.faces.new([verts[i] for i in ids])
            for loop, vid in zip(f.loops, ids):                        # loops follow the vertex list order
                for layer, uv in zip(uvs[1:], person_data_uvs(vid, clip, yaw, sx, sz, mirror, phase)):
                    loop[layer].uv = uv
                loop[colx] = (*c, 1.0)
            faces.append(f)
        label_uvs(uvs[0], faces, pos[0], pos[1], pos[2], H * sz, k, cols)
    me = bpy.data.meshes.new(name)
    bm2.to_mesh(me)
    bm2.free()
    for p in me.polygons:
        p.use_smooth = True
    return link(bpy.data.objects.new(name, me))


rnd = random.Random(5)
for k in range(25):                                                    # 5 x 5 test crowd, 1.1 m apart
    CROWD_PEOPLE.append((V3((k % 5 - 2) * 1.1, (k // 5 - 2) * 1.1, 0.0), rnd.uniform(-0.5, 0.5),
                         rnd.uniform(0.38, 0.5) / W, rnd.uniform(1.55, 1.92) / H, rnd.choice((1.0, -1.0)),
                         k % 2, rnd.random()))
single = build_static("SM_VatPerson", [(V3(0, 0, 0), 0.0, 1.0, 1.0, 1.0, 0, 0.0)])
crowd = build_static("SM_VatCrowdTest", CROWD_PEOPLE)
FBX_PERSON = export_fbx(single, "SM_VatPerson")
FBX_CROWD = export_fbx(crowd, "SM_VatCrowdTest")
crowd.data.calc_loop_triangles()
log(f"FBX: SM_VatPerson ({len(single.data.polygons)} faces), SM_VatCrowdTest ({len(CROWD_PEOPLE)} people, "
    f"{len(crowd.data.loop_triangles)} tris)")

# render-vertex estimate: Unreal splits a vertex wherever its corners differ (UV0 seam here; normals are smooth)
_uv = np.empty(len(single.data.loops) * 2, dtype=np.float32)
single.data.uv_layers["UVMap"].data.foreach_get("uv", _uv)
_vi = np.empty(len(single.data.loops), dtype=np.int64)
single.data.loops.foreach_get("vertex_index", _vi)
UE_VERTS_SMOOTH = len({(int(v), round(float(a), 6), round(float(b), 6)) for v, (a, b) in zip(_vi, _uv.reshape(-1, 2))})
UE_VERTS_FLAT = len(single.data.loops)

ANIM = (REST[None, None] + OFF).reshape(-1, 3)
META = {
    "what": "VAT position offsets from the rest pose of SM_VatPerson (all clips stacked vertically)",
    "textures": {"exr": "T_VAT_Person.exr", "exr_pixel_type": "half (RGBA16F, linear, A = 1)",
                 "png16": "T_VAT_Person_16.png", "width": TEX_W, "height": TEX_H},
    "layout": "texel x = vertex index (UV1.x), y = clip * rows_per_clip + frame; y = 0 is the TOP row of the file "
              "(Unreal V = 0); RGB = offset in meters (Blender object space), A = 1",
    "vertex_count": NV, "triangles": NTRI, "ue_render_verts_estimate": {"smooth_export": UE_VERTS_SMOOTH,
                                                                          "flat_export": UE_VERTS_FLAT},
    "fps": FPS, "frames_per_clip": FRAMES, "rows_per_clip": ROWS, "clip_seconds": FRAMES / FPS,
    "authored_bpm": AUTHORED_BPM, "beats_per_clip": BEATS_PER_CLIP,
    "loop_rate_for_bpm": "LoopRate (loops/s) = BPM / (60 * beats_per_clip) = BPM / %g; 1.0 = the authored tempo"
                         % (60 * BEATS_PER_CLIP),
    "clips": [{"name": c, "index": i, "row_start": i * ROWS, "rows": ROWS} for i, c in enumerate(CLIPS)],
    "space": "meters; X = the person's right, Y = forward (toward the stage), Z = up; feet on z = 0",
    "to_unreal": {"axis_scale": list(UE_AXIS),
                  "why": "Blender m -> UE cm with Y mirrored, as observed for the dino FBXs (screen y +10.9 m -> -1090 cm)"},
    "png16_decode": {"min": omin.tolist(), "max": omax.tolist(), "formula": "offset = min + png / 65535 * (max - min)"},
    "rest_bounds_m": {"min": REST.min(0).tolist(), "max": REST.max(0).tolist()},
    "animated_bounds_m": {"min": ANIM.min(0).tolist(), "max": ANIM.max(0).tolist()},
    "uv_channels_as_unreal_reads_them": {
        "UV0 UVMap": "per-person baked-lighting cell (dino_stage bottle-label layout)",
        "UV1 VatIndex": "x = VAT column (integer vertex index), y = clip index (integer)",
        "UV2 VatRotScale": "x = sx * cos(yaw), y = sx * sin(yaw)  (yaw/scale of the person, Blender space)",
        "UV3 VatScalePhase": "x = mirror(+-1) * sz, y = phase in [0, 1)",
        "note": ("in Blender/FBX every V is stored as 1 - value; Unreal's FBX importer flips V back" if UE_FLIPS_V
                 else "V stored as-is (UE_FLIPS_V = False)")},
    "material_params": {"TexW": TEX_W, "TexH": TEX_H, "FramesPerClip": FRAMES, "RowsPerClip": ROWS,
                        "LoopRate": 1.0, "AxisScale": list(UE_AXIS), "ClipOffset": 0.0},
    "test_crowd_people": [{"pos": list(p[0]), "yaw": p[1], "sx": p[2], "sz": p[3], "mirror": p[4], "clip": CLIPS[p[5]],
                           "phase": p[6]} for p in CROWD_PEOPLE],
}
json.dump(META, open(os.path.join(OUT, "VAT_Person.json"), "w"), indent=1)
bpy.context.preferences.filepaths.save_version = 0                    # no vat_person.blend1 backups in out/
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "vat_person.blend"), compress=True)

# ---------------------------------------------------------------- verification
REPORT = {}
exr, exr_float = read_with_blender(EXR_PATH)
png_back, png_float = read_with_blender(PNG_PATH)
REPORT["readback"] = {"exr_size": list(exr.shape[:2]), "png_size": list(png_back.shape[:2]),
                      "png16_reader_max_dev_from_source": float(np.abs(png_back[..., :3] - png[..., :3] / 65535.0).max()),
                      "png_loaded_as_float": bool(png_float)}


def decode(texels, ci, f):
    return texels[ci * ROWS + f, :NV, :3].astype(np.float64)


png_off = omin + png_back[..., :3].astype(np.float64) * rng_                   # PNG route, as decoded by Blender
png_half = omin + (png_back[..., :3].astype(np.float16).astype(np.float64)) * rng_   # ... after UE's TC_HDR (RGBA16F)
err = {"exr_half": 0.0, "png16": 0.0, "png16_as_rgba16f": 0.0, "half_quantization_bound_cm": 0.0}
for ci, clip in enumerate(CLIPS):
    for f in range(FRAMES + 1):
        truth = POS[clip][f]
        err["exr_half"] = max(err["exr_half"], float(np.abs(REST + decode(exr, ci, f) - truth).max()))
        err["png16"] = max(err["png16"], float(np.abs(REST + png_off[ci * ROWS + f, :NV] - truth).max()))
        err["png16_as_rgba16f"] = max(err["png16_as_rgba16f"], float(np.abs(REST + png_half[ci * ROWS + f, :NV] - truth).max()))
err["half_quantization_bound_cm"] = float(np.spacing(np.float16(np.abs(OFF).max())).astype(np.float64) / 2)
seam = max(float(np.abs(OFF[ci, FRAMES] - OFF[ci, 0]).max()) for ci in range(len(CLIPS)))
fresh = {}
for ci, clip in enumerate(CLIPS):                                      # frame N, freshly re-evaluated from the rig
    use_action(ACTIONS[clip])
    scene.frame_set(CHECK_FRAME)
    truth = evaluated_positions(person)
    fresh[clip] = float(np.abs(REST + decode(exr, ci, CHECK_FRAME) - truth).max() * 100)
REPORT["vat_max_error_cm_all_frames"] = {k: v * 100 for k, v in err.items()}
REPORT["vat_max_error_cm_frame_%d_fresh_eval" % CHECK_FRAME] = fresh
REPORT["loop_seam_cm"] = seam * 100
REPORT["rig_check"] = {"bone_matrix_max_dev": rig_err_bone, "skinning_max_dev_cm": rig_err_lbs * 100}
REPORT["max_offset_m"] = float(np.abs(OFF).max())


def material_wpo(uv1, uv2, uv3, t, vat, loop_rate=1.0, clip_offset=0.0):
    """numpy copy of the Unreal material graph (DESIGN.md), float32 like the GPU. uv1..uv3 = (N, 2) as UNREAL reads
    them; vat = the texture (row 0 = top). Returns the World Position Offset in Unreal local space (cm), N x 3."""
    f32 = np.float32
    uv1, uv2, uv3 = (np.asarray(a, dtype=f32) for a in (uv1, uv2, uv3))
    p = np.mod(f32(t) * f32(loop_rate) + uv3[:, 1], f32(1.0))                     # Frac(Time * LoopRate + phase)
    fr = p * f32(FRAMES)
    f0 = np.floor(fr)
    a = (fr - f0)[:, None]
    row = (uv1[:, 1] + f32(clip_offset)) * f32(ROWS) + f0
    u = (uv1[:, 0] + f32(0.5)) / f32(TEX_W)
    v0 = (row + f32(0.5)) / f32(TEX_H)
    v1 = v0 + f32(1.0) / f32(TEX_H)

    def fetch(uu, vv):                                                 # nearest filter, clamp addressing
        x = np.clip(np.floor(uu * TEX_W).astype(int), 0, TEX_W - 1)
        y = np.clip(np.floor(vv * TEX_H).astype(int), 0, TEX_H - 1)
        return vat[y, x, :3].astype(f32)
    o = fetch(u, v0) * (f32(1.0) - a) + fetch(u, v1) * a              # Lerp(frame, next frame, Frac)
    ox = o[:, 0] * np.sign(uv3[:, 0])                                  # mirror
    c, s = uv2[:, 0], uv2[:, 1]
    rx, ry, rz = c * ox - s * o[:, 1], s * ox + c * o[:, 1], np.abs(uv3[:, 0]) * o[:, 2]   # yaw + scale
    return np.stack([rx, ry, rz], 1) * np.asarray(UE_AXIS, dtype=f32)  # Blender m -> Unreal cm (Y mirrored)


# re-import the test crowd FBX: positions + UV channels exactly as they come out of the file
before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=FBX_CROWD)
imp = [o for o in bpy.data.objects if o not in before and o.type == "MESH"][0]
ime = imp.data
nvi = len(ime.vertices)
co = np.empty(nvi * 3)
ime.vertices.foreach_get("co", co)
mw = np.array(imp.matrix_world)
base_bl = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]                 # Blender world space, meters
vi = np.empty(len(ime.loops), dtype=np.int64)
ime.loops.foreach_get("vertex_index", vi)
REPORT["fbx_uv_layers"] = [l.name for l in ime.uv_layers]
uv_v = {}
for name in DATA_UV_NAMES:
    raw = np.empty(len(ime.loops) * 2, dtype=np.float64)
    ime.uv_layers[name].data.foreach_get("uv", raw)
    raw = raw.reshape(-1, 2)
    per_v = np.zeros((nvi, 2))
    per_v[vi] = raw
    if np.abs(raw - per_v[vi]).max() > 1e-6:
        raise RuntimeError(name + ": a vertex has different data UVs on different corners")
    uv_v[name] = per_v
assert nvi == len(CROWD_PEOPLE) * NV and np.array_equal(uv_v["VatIndex"][:, 0], np.tile(np.arange(NV), len(CROWD_PEOPLE)))


def to_ue(p):
    return p * np.asarray(UE_AXIS)


def ue_import_uv(uv, half):
    """What Unreal stores: V -> 1 - V (FBX importer), then 16-bit float unless 'Use Full Precision UVs'."""
    out = np.stack([uv[:, 0], (1.0 - uv[:, 1]) if UE_FLIPS_V else uv[:, 1]], 1).astype(np.float32)
    return out.astype(np.float16).astype(np.float32) if half else out


crowd_err = {}
for half in (False, True):
    worst = 0.0
    uvs_ue = [ue_import_uv(uv_v[n], half) for n in DATA_UV_NAMES]
    for t in (0.0, 0.37, 1.234, 7.891, 123.456):
        wpo = material_wpo(*uvs_ue, t, exr)
        shown = to_ue(base_bl) + wpo                                   # what the GPU would draw (UE local cm)
        for k, (pos, yaw, sx, sz, mirror, clip, phase) in enumerate(CROWD_PEOPLE):
            pp = (t + phase) % 1.0 * FRAMES                            # exact phase, float64
            f0 = min(int(math.floor(pp)), FRAMES - 1)
            a = pp - f0
            canon = REST + (1 - a) * OFF[clip, f0] + a * OFF[clip, f0 + 1]
            m = np.array(Matrix.Translation(pos) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Diagonal(Vector((sx * mirror, sx, sz, 1.0))))
            expect = to_ue(canon @ m[:3, :3].T + m[:3, 3])
            worst = max(worst, float(np.abs(shown[k * NV:(k + 1) * NV] - expect).max()))
    crowd_err["full_precision_uvs" if not half else "default_16bit_uvs"] = worst
REPORT["test_crowd_material_emulation_max_error_cm"] = crowd_err
bpy.data.objects.remove(imp)

# ---------------------------------------------------------------- preview: a contact sheet decoded from the EXR
if PREVIEW:
    for ob in (person, rig, single, crowd):
        ob.hide_render = True
    cols_f = list(range(0, FRAMES, 3))
    pmat = bpy.data.materials.new("Preview")
    for ci, clip in enumerate(CLIPS):
        for j, f in enumerate(cols_f):
            me = bpy.data.meshes.new(f"P_{clip}_{f}")
            pts = REST + decode(exr, ci, f) + np.array([-j * 0.95, 0.0, -ci * 2.7])   # -X = screen right
            me.from_pydata(pts.tolist(), [], FACES)
            ca = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
            for poly, c in zip(me.polygons, FACE_COLS):
                for li in poly.loop_indices:
                    ca.data[li].color = (*c, 1.0)
            me.color_attributes.active_color = ca
            me.materials.append(pmat)
            link(bpy.data.objects.new(me.name, me))
        gme = bpy.data.meshes.new(f"Ground_{clip}")                    # floor line: shows the feet leaving it
        x0, x1, z = -(len(cols_f) - 1) * 0.95 - 0.6, 0.6, -ci * 2.7
        gme.from_pydata([(x0, -0.6, z), (x1, -0.6, z), (x1, 0.6, z), (x0, 0.6, z)], [], [(0, 1, 2, 3)])
        link(bpy.data.objects.new(gme.name, gme))
    world = bpy.data.worlds.new("PreviewWorld")
    world.color = (0.03, 0.03, 0.04)
    scene.world = world
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light, sh.color_type, sh.show_backface_culling = "STUDIO", "VERTEX", True
    sh.show_shadows = True
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.type, cam.data.ortho_scale = "ORTHO", 10.2
    target = V3(-(len(cols_f) - 1) * 0.95 / 2, 0.0, -1.35 + 0.9)
    cam.location = target + V3(3.0, 12.0, 3.2)
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    link(cam)
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = 1800, 980
    scene.render.filepath = os.path.join(OUT, "preview_vat_frames.png")
    try:
        bpy.ops.render.render(write_still=True)
        REPORT["preview"] = "preview_vat_frames.png"
    except Exception as e:  # noqa: BLE001
        REPORT["preview"] = "failed: " + repr(e)
    log("preview: " + REPORT["preview"])

REPORT["sizes"] = {"verts": NV, "tris": NTRI, "tex_w": TEX_W, "tex_h": TEX_H, "rgba16f_bytes": TEX_W * TEX_H * 8,
                   "ue_render_verts_smooth": UE_VERTS_SMOOTH, "ue_render_verts_flat": UE_VERTS_FLAT}
REPORT["seconds"] = round(time.time() - T0, 1)
json.dump(REPORT, open(os.path.join(OUT, "verify_report.json"), "w"), indent=1)
log("VERIFY " + json.dumps(REPORT))
ok = (err["exr_half"] * 100 < 0.1 and err["png16"] * 100 < 0.01 and max(fresh.values()) < 0.1 and seam < 1e-6
      and crowd_err["full_precision_uvs"] < 0.1 and crowd_err["default_16bit_uvs"] < 0.5)
log(("PASS" if ok else "FAIL") + f" ({REPORT['seconds']} s)")
if not ok:
    sys.exit(1)
