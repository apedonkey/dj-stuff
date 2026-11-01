"""Preview the v2 arch skull (skull.py) in the shipped stage context (Blender 4.5, headless, Cycles GPU).

  D:\\Tools\\blender-4.5.14-windows-x64\\blender.exe -b --factory-startup --python skull_preview.py --
        [--views crowd,crowd_near,stream,overview,dj_up,q34,crowd_dark] [--res 1280x720] [--samples 32]
        [--bake-size 2048] [--lights stage|recommended] [--show]

- Context = out/SM_Dino*.fbx with their baked textures, unlit (as the Quest shows them). The old skull is cut out of
  SM_DinoStructure (its loose parts: cranium, jaw, teeth, brow horns, brow bosses) and the old SM_DinoEyes is skipped.
  The 16 x 9 m visual screen is added (dino_stage VISUAL_SCREEN, showing T_DinoLED).
- The new skull is BAKED like dino_stage bakes the structure: mat_bone, the stage's bake lights (stage_lights(), or
  skull.SKULL_LIGHTS in place of SkullKey with --lights recommended), the context emitters at their bake strengths,
  DIFFUSE bake, tonemap 1 - exp(-x * 1.6 * NIGHT); then shown unlit. The eyes/throat glow ship unlit red.
- crowd_dark: between hits (the show's wash row at 0.12): set, deck, crowd and skull x0.12, emitters as they are.
- --show adds the translucent beams, halos and lasers (rest pose).
Writes out/skull_preview/<view>[_rec].png (+ the bake texture) and prints [SKULL] stats.
"""
import math
import os
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
PREVIEW = os.path.join(OUT, "skull_preview")          # this script's renders and bake (kept out of the build's out/)
os.makedirs(PREVIEW, exist_ok=True)
sys.path.insert(0, HERE)
import skull  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


VIEWS = opt("--views", "crowd,crowd_near,stream,overview,dj_up,q34,crowd_dark").split(",")
RES = tuple(int(v) for v in opt("--res", "1280x720").split("x"))
SAMPLES = int(opt("--samples", "32"))
BAKE_SIZE = int(opt("--bake-size", "2048"))
LIGHTS = opt("--lights", "stage")
SHOW = "--show" in ARGS
STAGE_DROP, NIGHT, EXPOSURE = 1.0, 0.5, 1.6          # dino_stage: the drop, the night factor, the structure's exposure
CAMS = {   # post-drop world (Tribe's floor z=0 = the DJ riser): position, target, lens
    "crowd": ((0, -24, 2.0), (0, 2, 14.0), 22),            # mid-crowd, in front of the FOH tower
    "crowd_near": ((-6, -14, 1.0), (0, 2, 16), 18),
    "stream": ((0, -95, 12), (0, 0, 6), 24),
    "overview": ((0, 25, 40), (0, -50, -2.5), 20),
    "dj_up": ((0, -0.3, 1.65), (0, 4, 16), 16),
    "q34": ((-22, -30, 6), (0, 2, 15), 28),
    "crowd_dark": ((0, -24, 2.0), (0, 2, 14.0), 22),
}
STAGE = {   # mesh -> texture (or flat color), shown unlit; bake strength of emitters (dino_stage's assign(...))
    "SM_DinoStructure": ("T_DinoStructure", None), "SM_DinoDeck": ("T_DinoDeck", None),
    "SM_DinoGround": ("T_DinoGround", None), "SM_DinoCrowd": ("T_DinoCrowd", None), "SM_DinoLED": ("T_DinoLED", 2.5),
    "SM_DinoScreen": ("T_DinoMoon", 4.0), "SM_DinoSky": ("T_DinoSky", None), "SM_DinoBulbs": ((1.0, 0.78, 0.45), 6.0),
    "SM_DinoPhones": ((0.85, 0.9, 1.0), 4.0), "SM_DinoFarGround": ((0.008, 0.008, 0.011), None),
    "SM_DinoRig": ("T_DinoRig", None), "SM_DinoLenses": ("T_DinoLens", 8.0), "SM_DinoBooth": ("T_DinoBooth", 3.0),
    "SM_DinoRiser": ("T_DinoRiser", None), "SM_DinoGlow": ((0.2, 0.9, 1.0), 6.0),
    "SM_DinoPillars": ((0.2, 0.9, 1.0), 6.0), "SM_DinoPlants": ("T_DinoPlants", None),
    "SM_DinoGroundsVendors": ("T_DinoGroundsVendors", None),
    "SM_DinoGroundsInfrastructure": ("T_DinoGroundsInfrastructure", None),
    "SM_DinoGroundsLandmarks": ("T_DinoGroundsLandmarks", None),
    "SM_DinoGroundsAtmosphere": ("T_DinoGroundsAtmosphere", None),
    "SM_DinoGroundsGlow": ("T_DinoGroundsPal", 5.0),
}
TRANSLUCENT = {"SM_DinoLasers": "T_DinoBeam", "SM_DinoHalosAtmosphere": "T_DinoHalo",
               **{f"SM_DinoBeams{k}": "T_DinoBeam" for k in range(5)}}
DIMMED = ("SM_DinoStructure", "SM_DinoDeck", "SM_DinoCrowd", "SM_DinoGround", "SkullV2")   # the "wash" row


def log(msg):
    print("[SKULL] " + msg, flush=True)


# ------------------------------------------------------------------ scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
coll = scene.collection
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
for dev_type in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = dev_type
        prefs.get_devices()
        if [d for d in prefs.devices if d.type == dev_type]:
            for d in prefs.devices:
                d.use = d.type == dev_type
            scene.cycles.device = "GPU"
            break
    except Exception:
        pass
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 3
scene.cycles.transparent_max_bounces = 16
scene.render.resolution_x, scene.render.resolution_y = RES
scene.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("Night")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.022, 0.045, 1)
scene.world = world


def load_png(name, folder=OUT):
    img = bpy.data.images.load(os.path.join(folder, name + ".png"), check_existing=True)
    img.colorspace_settings.name = "sRGB"
    img.alpha_mode = "STRAIGHT"
    return img


def emit_mat(name, src, bake_strength=None, alpha=False, folder=OUT):
    """Unlit: emission of a texture or color. bake_strength: what the bake's rays see (the camera sees 1)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tex = None
    if isinstance(src, str):
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = load_png(src, folder)
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = (*src, 1)
    mul = nt.nodes.new("ShaderNodeMath")                 # strength = camera ? 1 : bake strength; x dim (wash level)
    mul.operation = "MULTIPLY"
    mul.name = "Dim"
    mul.inputs[1].default_value = 1.0
    if bake_strength is not None:
        lp = nt.nodes.new("ShaderNodeLightPath")
        ma = nt.nodes.new("ShaderNodeMath")
        ma.operation = "MULTIPLY_ADD"
        nt.links.new(lp.outputs["Is Camera Ray"], ma.inputs[0])
        ma.inputs[1].default_value = 1.0 - bake_strength
        ma.inputs[2].default_value = bake_strength
        nt.links.new(ma.outputs[0], mul.inputs[0])
    else:
        mul.inputs[0].default_value = 1.0
    nt.links.new(mul.outputs[0], em.inputs["Strength"])
    shader = em.outputs["Emission"]
    if alpha and tex is not None:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
        nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
        nt.links.new(shader, mix.inputs[2])
        shader = mix.outputs["Shader"]
    nt.links.new(shader, out.inputs["Surface"])
    return m


def import_fbx(name):
    path = os.path.join(OUT, name + ".fbx")
    if not os.path.exists(path):
        return None
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path, axis_forward="-Z", axis_up="Y")
    obs = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    return obs[0] if obs else None


def cut_old_skull(ob):
    """Delete the old skull's loose parts from the structure: the metaball cranium and jaw, 32 teeth (57 faces each),
    2 brow horns (157) and 2 brow bosses (149), all inside the old skull's box. Horns (541), back spikes (133) and the
    484-face horn-base parts stay."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    mw = ob.matrix_world
    bm.verts.ensure_lookup_table()
    seen, kill, removed = set(), [], {}
    for v0 in bm.verts:
        if v0.index in seen:
            continue
        stack, comp = [v0], []
        seen.add(v0.index)
        while stack:
            v = stack.pop()
            comp.append(v)
            for e in v.link_edges:
                w = e.other_vert(v)
                if w.index not in seen:
                    seen.add(w.index)
                    stack.append(w)
        faces = {f for v in comp for f in v.link_faces}
        pts = [mw @ v.co for v in comp]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        in_box = lo.x > -8.0 and hi.x < 8.0 and lo.y > -2.5 and hi.y < 11.5 and lo.z > 11.9 and hi.z < 26.5
        if in_box and len(faces) not in (133, 484, 541):
            kill += comp
            removed[len(faces)] = removed.get(len(faces), 0) + 1
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    log(f"old skull cut from the structure: parts by face count {dict(sorted(removed.items()))}")


# ------------------------------------------------------------------ context
t0 = time.time()
context = {}
for name, (src, bstr) in STAGE.items():
    ob = import_fbx(name)
    if ob is None:
        continue
    if name == "SM_DinoStructure":
        cut_old_skull(ob)
    ob.data.materials.clear()
    ob.data.materials.append(emit_mat("C_" + name, src, bstr))
    context[name] = ob
if SHOW:
    for name, tex in TRANSLUCENT.items():
        ob = import_fbx(name)
        if ob is not None:
            ob.data.materials.clear()
            ob.data.materials.append(emit_mat("T_" + name, tex, alpha=True))
            ob.hide_render = True                          # out of the bake; shown for the renders
            context[name] = ob
vs_bm = bmesh.new()                                        # the visual screen (dino_stage VISUAL_SCREEN), post-drop
uvl = vs_bm.loops.layers.uv.new("UVMap")
w_, h_, y_, cz = 16.0, 9.0, 10.3, 7.2 - STAGE_DROP
f = vs_bm.faces.new([vs_bm.verts.new(c) for c in ((-w_ / 2, y_, cz - h_ / 2), (w_ / 2, y_, cz - h_ / 2),
                                                   (w_ / 2, y_, cz + h_ / 2), (-w_ / 2, y_, cz + h_ / 2))])
if f.normal.y > 0:
    f.normal_flip()
for lp in f.loops:
    lp[uvl].uv = ((lp.vert.co.x + w_ / 2) / w_, (lp.vert.co.z - (cz - h_ / 2)) / h_)
vs_me = bpy.data.meshes.new("SM_DinoVisualScreen")
vs_bm.to_mesh(vs_me)
vs_ob = bpy.data.objects.new("SM_DinoVisualScreen", vs_me)
coll.objects.link(vs_ob)
vs_me.materials.append(emit_mat("C_VisualScreen", "T_DinoLED", 1.0))
log(f"context: {len(context)} meshes + visual screen ({time.time() - t0:.0f} s)")

# ------------------------------------------------------------------ the new skull
t1 = time.time()
sk_bm, eye_bm = skull.build_skull_v2()
drop = Matrix.Translation((0, 0, -STAGE_DROP))
sk_tris, eye_tris = sum(len(f.verts) - 2 for f in sk_bm.faces), sum(len(f.verts) - 2 for f in eye_bm.faces)
sk_bm.transform(drop)
eye_bm.transform(drop)
sk_me = bpy.data.meshes.new("SkullV2")
sk_bm.to_mesh(sk_me)
sk_bm.free()
sk_ob = bpy.data.objects.new("SkullV2", sk_me)
coll.objects.link(sk_ob)
eye_me = bpy.data.meshes.new("SkullV2Eyes")
eye_bm.to_mesh(eye_me)
eye_bm.free()
eye_ob = bpy.data.objects.new("SkullV2Eyes", eye_me)
coll.objects.link(eye_ob)
eye_me.materials.append(emit_mat("EyeEmit", (1.0, 0.06, 0.02), 6.0))
log(f"skull v2: {sk_tris} tris, eyes {eye_tris} tris, built in {time.time() - t1:.1f} s")


def mat_bone():
    """dino_stage.mat_bone(): noise color, Voronoi cracks, AO, bump (copied)."""
    m = bpy.data.materials.new("Bone")
    m.use_nodes = True
    nt = m.node_tree
    N, Ln = nt.nodes, nt.links
    bsdf = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord")
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.9
    noise.inputs["Detail"].default_value = 8.0
    Ln.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.16, 0.09, 0.03, 1)
    ramp.color_ramp.elements[1].color = (0.80, 0.58, 0.25, 1)
    Ln.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    vor = N.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 4.5
    Ln.new(tc.outputs["Object"], vor.inputs["Vector"])
    crack = N.new("ShaderNodeMapRange")
    crack.inputs["From Min"].default_value = 0.0
    crack.inputs["From Max"].default_value = 0.018
    Ln.new(vor.outputs["Distance"], crack.inputs["Value"])
    cmix = N.new("ShaderNodeMixRGB")
    cmix.inputs["Color1"].default_value = (0.10, 0.065, 0.03, 1)
    Ln.new(crack.outputs["Result"], cmix.inputs["Fac"])
    Ln.new(ramp.outputs["Color"], cmix.inputs["Color2"])
    ao = N.new("ShaderNodeAmbientOcclusion")
    ao.samples = 16
    ao.inputs["Distance"].default_value = 1.5
    Ln.new(cmix.outputs["Color"], ao.inputs["Color"])
    amix = N.new("ShaderNodeMixRGB")
    amix.inputs["Fac"].default_value = 0.75
    Ln.new(cmix.outputs["Color"], amix.inputs["Color1"])
    Ln.new(ao.outputs["Color"], amix.inputs["Color2"])
    Ln.new(amix.outputs["Color"], bsdf.inputs["Base Color"])
    hsum = N.new("ShaderNodeMath")
    hsum.operation = "ADD"
    n2 = N.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 6.0
    Ln.new(tc.outputs["Object"], n2.inputs["Vector"])
    Ln.new(crack.outputs["Result"], hsum.inputs[0])
    Ln.new(n2.outputs["Fac"], hsum.inputs[1])
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.45
    Ln.new(hsum.outputs["Value"], bump.inputs["Height"])
    Ln.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.65
    return m


def add_light(name, kind, pos, target, color, power, size=1.0, spot_deg=40):
    """dino_stage.add_light(), then dropped like dino_stage drops every bake light."""
    ld = bpy.data.lights.new(name, kind)
    ld.color, ld.energy = color, power
    if kind == "AREA":
        ld.shape, ld.size = "DISK", size
    if kind == "SPOT":
        ld.spot_size, ld.spot_blend, ld.shadow_soft_size = math.radians(spot_deg), 0.6, size
    ob = bpy.data.objects.new(name, ld)
    ob.location = Vector(pos) - Vector((0, 0, STAGE_DROP))
    ob.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(ob)


def spine_point(side, t):
    return Vector((side * (23.0 * (1 - t) ** 1.15 + 2.2 * t), -3.5 + 12.5 * t ** 1.6,
                   0.6 + 16.5 * math.sin(t * math.pi / 2) ** 1.25))


def stage_lights():
    """dino_stage.stage_lights() (copied), with SkullKey or skull.SKULL_LIGHTS."""
    for side in (-1, 1):
        for k in range(7):
            t = 0.10 + 0.78 * k / 6
            p = spine_point(side, t)
            add_light(f"Up{side}{k}", "SPOT", p + Vector((side * -1.8, -2.5, -0.4)), p + Vector((side * 1.5, 0, 10)),
                      (1.0, 0.48, 0.12), 6000 + 8000 * t, size=0.6, spot_deg=50)
        add_light(f"Blue{side}", "SPOT", (side * 16, 6, 34), (side * 8, 2, 8), (0.22, 0.4, 1.0), 70000, size=2, spot_deg=70)
        for k, col in enumerate(((1.0, 0.15, 0.6), (0.2, 0.4, 1.0), (1.0, 0.55, 0.1))):
            add_light(f"Pool{side}{k}", "SPOT", (side * (6 + 7 * k), -3, 14), (side * (8 + 10 * k), -28 - 9 * k, -1.5),
                      col, 120000, size=0.5, spot_deg=16)
        for k in range(4):
            add_light(f"Wash{side}{k}", "SPOT", (side * (3 + 6 * k), -4.0, 2.5), (side * (4 + 8 * k), -16, -0.5),
                      (0.75, 0.8, 1.0), 1100, size=0.4, spot_deg=45)
    add_light("Front", "AREA", (0, -45, 14), (0, 6, 10), (0.3, 0.4, 1.0), 1400, size=30)
    add_light("CrowdGlow", "AREA", (0, -8, 9), (0, -45, 0), (1.0, 0.5, 0.35), 3200, size=25)
    for side, col in ((-1, (1.0, 0.3, 0.8)), (1, (0.3, 0.5, 1.0))):
        add_light(f"SideFill{side}", "AREA", (side * 30, -10, 6), (side * -8, -40, 0), col, 1800, size=15)
    sun = bpy.data.lights.new("Moon", "SUN")
    sun.color, sun.energy, sun.angle = (0.5, 0.6, 1.0), 0.25, math.radians(10)
    so = bpy.data.objects.new("Moon", sun)
    so.rotation_euler = (math.radians(35), math.radians(-25), math.radians(20))
    coll.objects.link(so)
    if LIGHTS == "recommended" and hasattr(skull, "SKULL_LIGHTS"):
        for spec in skull.SKULL_LIGHTS:
            add_light(*spec)
    else:
        add_light("SkullKey", "SPOT", (0, -3, 9), (0, 5.5, 18), (1.0, 0.62, 0.3), 70000, size=1, spot_deg=34)


def write_png(path, rgb_lin_top_down):
    lin = np.clip(rgb_lin_top_down, 0.0, 1.0)
    s = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
    a = (s * 255.0 + 0.5).astype(np.uint8)
    h, w, _ = a.shape
    raw = b"".join(b"\x00" + a[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    open(path, "wb").write(png)


# ------------------------------------------------------------------ bake the skull like dino_stage bakes the structure
t2 = time.time()
stage_lights()
sk_me.materials.append(mat_bone())
for p in sk_me.polygons:
    p.use_smooth = True                                    # dino_stage: set_smooth(structure, True)
bpy.ops.object.select_all(action="DESELECT")
sk_ob.select_set(True)
bpy.context.view_layer.objects.active = sk_ob
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.002, area_weight=0.0, correct_aspect=True)
bpy.ops.uv.pack_islands(rotate=True, margin=0.002)
bpy.ops.object.mode_set(mode="OBJECT")
img = bpy.data.images.new("SkullBake", BAKE_SIZE, BAKE_SIZE, alpha=False, float_buffer=True)
nt = sk_me.materials[0].node_tree
tx = nt.nodes.new("ShaderNodeTexImage")
tx.image = img
for n in nt.nodes:
    n.select = False
tx.select = True
nt.nodes.active = tx
scene.cycles.samples = 64
bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT", "COLOR"}, margin=8, use_clear=True)
px = np.empty(BAKE_SIZE * BAKE_SIZE * 4, dtype=np.float32)
img.pixels.foreach_get(px)
lin = px.reshape(BAKE_SIZE, BAKE_SIZE, 4)[::-1, :, :3]
bake_path = os.path.join(PREVIEW, f"T_SkullV2_{LIGHTS}.png")
write_png(bake_path, 1.0 - np.exp(-lin * EXPOSURE * NIGHT))
log(f"baked skull ({LIGHTS} lights) -> {os.path.basename(bake_path)}, mean linear {lin.mean():.3f} "
    f"({time.time() - t2:.0f} s)")
for lt in [o for o in coll.objects if o.type == "LIGHT"]:
    bpy.data.objects.remove(lt)
sk_me.materials.clear()
sk_me.materials.append(emit_mat("SkullBaked", f"T_SkullV2_{LIGHTS}", folder=PREVIEW))
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
for name in TRANSLUCENT:
    if name in context:
        context[name].hide_render = False


def dim(level):
    for ob in [context.get(n) for n in DIMMED[:-1]] + [sk_ob]:
        if ob is not None:
            ob.data.materials[0].node_tree.nodes["Dim"].inputs[1].default_value = level


# ------------------------------------------------------------------ renders
scene.cycles.samples = SAMPLES
for v in VIEWS:
    if v not in CAMS:
        log(f"unknown view {v}")
        continue
    pos, tgt, lens = CAMS[v]
    dim(0.12 if v == "crowd_dark" else 1.0)
    cd = bpy.data.cameras.new(v)
    cd.lens, cd.clip_end = lens, 2000
    co = bpy.data.objects.new(v, cd)
    co.location = pos
    co.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(co)
    scene.camera = co
    scene.render.filepath = os.path.join(PREVIEW, f"{v}{'' if LIGHTS == 'stage' else '_rec'}.png")
    t3 = time.time()
    bpy.ops.render.render(write_still=True)
    log(f"render {v}: {scene.render.filepath} ({time.time() - t3:.0f} s)")
log("done")
