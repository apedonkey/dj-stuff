# Dino stage generator for the Tribe XR mod kit (Blender 4.5, headless):
#   D:\Tools\blender-4.5.14-windows-x64\blender.exe -b --factory-startup --python dino_stage.py [-- --preview-only]
# Builds an outdoor night stage in the spirit of a dinosaur-themed festival main stage (our own design): two spine arches
# with giant horns rising to a skull above the DJ, a round "moon" screen, a curved red LED wall, bulb strings, a raised
# deck, the crowd field and a starry sky. Lighting is BAKED into textures on the GPU (Cycles) and everything ships with
# unlit materials: on Quest that costs nothing at runtime, and Tribe's own shipped unlit glTFRuntime material can show it
# (no custom shaders in the pak until the Meta-fork engine build is verified).
#
# Space: meters, Z up, DJ at the origin facing -Y (the crowd); the stage structure stands behind the DJ (+Y). The Unreal
# import (build_dino.py) checks where the screen landed and turns the level around if the FBX axis conversion mirrored Y.
# Output: Scripts/Blender/out/*.fbx (one mesh per material) + *.png textures + preview_*.png renders.
import math
import os
import random
import importlib
import json
import struct
import sys
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "grounds"))
import kit as gkit  # noqa: E402  (festival-grounds modules: grounds/*.py, contract in grounds/kit.py)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "crowd2"))
import crowd3 as crowd2  # noqa: E402  (crowd v3: the rave crowd, same API as v2's crowd2.py; see crowd2/README*.md)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from show import write_all as write_show  # noqa: E402  (the light show's cue table + laser program/library; `python
                                          # show.py` rewrites them alone)
import skull  # noqa: E402  (the T. rex head, v2: skull.build_skull_v2(), its lights skull.SKULL_LIGHTS; checks in skull_check.py)
import arch  # noqa: E402  (the arch, v2: spine wings, horns, spikes, bulbs and the screen outline; checks in arch_check.py)
CROWD2 = os.environ.get("DINO_CROWD2", "1") == "1"   # 0: the old static crowd (build_crowd) for comparison

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("DINO_OUT") or os.path.join(HERE, "out")    # DINO_OUT: test builds elsewhere (agents preview out/)
os.makedirs(OUT, exist_ok=True)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
BAKE_SAMPLES = 64
NIGHT = 0.5               # the user, 2026-10-05: "everything needs to be dark, it is way too light": every bake x0.5
FAST = "--fast" in ARGS   # pipeline test: tiny bakes (1/8 size, 4 samples); never ship its output
# Festival grounds around the field, one module each (grounds/<name>.py); DINO_GROUNDS=a,b overrides the list.
GROUND_MODULES = tuple(m for m in os.environ.get("DINO_GROUNDS", "vendors,infrastructure,landmarks,atmosphere,stagedeck")
                       .split(",") if m)   # stagedeck (v8): the DJ deck gear; a v9 bake without it dropped its gear,
                                           # 8 lights and 7 people (2026-10-08)
GROUND_SEED = 1234        # the seed grounds/preview.py uses: the full build shows what the module previews showed
STAGE_DROP = 1.0          # the set is modeled with the stage floor at z=0, then lowered: the DJ riser stays at Tribe's floor
# Booth table under Tribe's DJ gear (world m, before nothing: it is NOT dropped). Sized from the gear the mod measured
# on the headset ([ENV] gear ... bounds); the top sits just under the lowest piece so it never cuts into the decks.
# Measured 2026-10-05: BP_Rig_C sits at (-5, 31, 78) cm (the gear anchor); your head stands at about (-12, 66, 157) cm.
TABLE = {"x0": -0.95, "x1": 0.85, "y0": -0.05, "y1": 0.50, "top": 0.74}
random.seed(7)
np.random.seed(7)


def log(msg):
    print("[DINO] " + msg, flush=True)


# ---------------------------------------------------------------- PNG I/O (sRGB 8-bit, no Blender colorspace guessing)
def srgb(lin):
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


def write_png(path, rgb_lin_top_down):
    """rgb_lin_top_down: HxWx3 linear floats, row 0 = top of the image."""
    a = (srgb(rgb_lin_top_down) * 255.0 + 0.5).astype(np.uint8)
    h, w, _ = a.shape
    raw = b"".join(b"\x00" + a[y].tobytes() for y in range(h))
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    open(path, "wb").write(png)
    log(f"texture {os.path.basename(path)} {w}x{h}")


def tonemap(lin, exposure):
    x = lin * exposure
    return 1.0 - np.exp(-x)  # soft shoulder: keeps baked highlights from clipping to flat white


# ---------------------------------------------------------------- scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
# DINO_CPU=1: Cycles stays on the CPU (pipeline tests, e.g. --fast, while another session holds the GPU lock)
for dev_type in (("OPTIX", "CUDA") if os.environ.get("DINO_CPU") != "1" else ()):
    try:
        prefs.compute_device_type = dev_type
        prefs.refresh_devices()
        gpus = [d for d in prefs.devices if d.type == dev_type]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == dev_type
            scene.cycles.device = "GPU"
            log(f"Cycles on {dev_type}: {[d.name for d in gpus]}")
            break
    except Exception as e:  # noqa: BLE001
        log(f"{dev_type} unavailable: {e}")
scene.view_settings.view_transform = "Standard"
coll = scene.collection


def new_obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def set_smooth(ob, smooth=True):
    for p in ob.data.polygons:
        p.use_smooth = smooth


# ---------------------------------------------------------------- generators
def tube(bm, pts, radius_fn, segs=20, ridges=0, ridge_amp=0.0, cap0=True, tip=False):
    """Swept tube along polyline pts; radius_fn(u) with u in [0,1]; parallel-transported frame."""
    n = len(pts)
    tans = []
    for i in range(n):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, n - 1)]
        tans.append((b - a).normalized())
    t0 = tans[0]
    ref = Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((1, 0, 0))
    nrm = t0.cross(ref).normalized()
    rings = []
    for i in range(n):
        if i > 0:
            ax = tans[i - 1].cross(tans[i])
            if ax.length > 1e-7:
                nrm = (Matrix.Rotation(tans[i - 1].angle(tans[i]), 3, ax.normalized()) @ nrm).normalized()
        bin_ = tans[i].cross(nrm).normalized()
        u = i / (n - 1)
        r = radius_fn(u)
        ring = []
        for j in range(segs):
            th = 2 * math.pi * j / segs
            rr = r * (1 + ridge_amp * math.sin(ridges * th)) if ridges else r
            ring.append(bm.verts.new(pts[i] + (nrm * math.cos(th) + bin_ * math.sin(th)) * rr))
        rings.append(ring)
    for i in range(n - 1):
        a, c = rings[i], rings[i + 1]
        for j in range(segs):
            bm.faces.new((a[j], a[(j + 1) % segs], c[(j + 1) % segs], c[j]))
    if cap0:
        bm.faces.new(list(reversed(rings[0])))
    if tip:
        apex = bm.verts.new(pts[-1] + tans[-1] * radius_fn(1.0) * 2 + tans[-1] * 0.05)
        last = rings[-1]
        for j in range(segs):
            bm.faces.new((last[j], last[(j + 1) % segs], apex))
    else:
        bm.faces.new(rings[-1])


spine_point = arch.spine_point   # backbone of one wing (arch.py): t = 0 at the foot in the deck, 1 at the skull's neck


def build_structure():
    """The arch (arch.py: the right wing is built, then mirrored, so the wings are true mirror images), the skull, the
    moon's frame. Returns SM_DinoStructure (bone), SM_DinoBulbs, SM_DinoEyes (the skull's glow)."""
    bm = bmesh.new()
    bulbs = bmesh.new()
    eyes = bmesh.new()
    wing, wing_bulbs = bmesh.new(), bmesh.new()
    vs = [wing.verts.new(p) for ring in arch.spine_rings(1) for p in ring]
    for f in arch.spine_faces():                                    # the spine, its inner edge in the screen plane
        wing.faces.new([vs[i] for i in f])
    vs = [wing.verts.new(p) for ring in arch.lintel_rings() for p in ring]
    for f in arch.lintel_faces():                                   # half the lintel under the neck (the mirror adds
        wing.faces.new([vs[i] for i in f])                          # the other half; they share the ring at x = 0)
    for h in arch.horns(1):                                         # big horns, curling up toward the skull
        tube(wing, h["pts"], arch.horn_radius_fn(h["r0"]), segs=20, ridges=5, ridge_amp=0.14, tip=True)
    for s in arch.spikes(1):                                        # small back spikes between the horns
        tube(wing, s["pts"], arch.horn_radius_fn(s["r0"]), segs=12, tip=True)
    for p in arch.bulbs(1):                                         # bulb string along the screen's edge
        bmesh.ops.create_icosphere(wing_bulbs, subdivisions=1, radius=arch.BULB_R, matrix=Matrix.Translation(p))
    for dst, src in ((bm, wing), (bulbs, wing_bulbs)):              # right wing + its mirror image (x -> -x)
        left = src.copy()
        bmesh.ops.scale(left, vec=(-1.0, 1.0, 1.0), verts=left.verts)
        bmesh.ops.reverse_faces(left, faces=left.faces)
        bm_add(dst, src)
        bm_add(dst, left)
    sk, ey = skull.build_skull_v2()                                # the head + its glow (eyes, throat ember), pre-drop
    bm_add(bm, sk)
    bm_add(eyes, ey)
    ring = Matrix.Translation((0, 11.15, 7.2)) @ Matrix.Rotation(math.radians(90), 4, "X")   # round screen frame
    bmesh.ops.create_cone(bm, cap_ends=False, segments=64, radius1=5.9, radius2=5.9, depth=0.8, matrix=ring)
    bmesh.ops.create_cone(bm, cap_ends=False, segments=64, radius1=5.5, radius2=5.5, depth=0.8, matrix=ring)
    for i in range(48):                                             # bulbs around the screen
        a = 2 * math.pi * i / 48
        bmesh.ops.create_icosphere(bulbs, subdivisions=1, radius=0.14,
                                   matrix=Matrix.Translation((math.cos(a) * 6.25, 10.6, 7.2 + math.sin(a) * 6.25)))
    return new_obj("SM_DinoStructure", bm), new_obj("SM_DinoBulbs", bulbs), new_obj("SM_DinoEyes", eyes)


def bm_add(dst, src):
    """Append bmesh src into dst (vertices + faces)."""
    vmap = {}
    for v in src.verts:
        vmap[v] = dst.verts.new(v.co)
    for f in src.faces:
        try:
            dst.faces.new([vmap[v] for v in f.verts])
        except ValueError:
            pass
    src.free()


def limb(bm, a, b, r0, r1, segs, caps=True, squash=1.0):
    """Tapered cylinder from point a (radius r0) to point b (radius r1); squash flattens it front-to-back."""
    d = b - a
    if d.length < 1e-4:
        return
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    m = Matrix.Translation((a + b) / 2) @ rot @ Matrix.Diagonal(Vector((1.0, squash, 1.0, 1.0)))
    bmesh.ops.create_cone(bm, cap_ends=caps, segments=segs, radius1=r0, radius2=r1, depth=d.length, matrix=m)


CLOTHES = [(0.02, 0.02, 0.022)] * 4 + [(0.75, 0.75, 0.72), (0.55, 0.04, 0.04), (0.04, 0.12, 0.55), (0.08, 0.5, 0.1),
           (0.85, 0.25, 0.55), (0.85, 0.4, 0.04), (0.25, 0.25, 0.27), (0.7, 0.62, 0.06), (0.35, 0.08, 0.45)]
PANTS = [(0.04, 0.06, 0.14), (0.04, 0.06, 0.14), (0.02, 0.02, 0.02), (0.22, 0.19, 0.14), (0.12, 0.12, 0.13)]
SKIN = [(0.80, 0.58, 0.45), (0.62, 0.42, 0.30), (0.42, 0.27, 0.18), (0.24, 0.14, 0.09), (0.88, 0.70, 0.58)]
FLAGS = [(0.9, 0.1, 0.1), (0.1, 0.3, 0.9), (0.95, 0.8, 0.1), (0.1, 0.8, 0.3), (0.9, 0.3, 0.8), (0.95, 0.5, 0.05)]
HAIR = [(0.02, 0.015, 0.01)] * 5 + [(0.06, 0.035, 0.02)] * 3 + [(0.14, 0.08, 0.035)] * 2 + [(0.45, 0.33, 0.15),
        (0.5, 0.06, 0.25), (0.08, 0.3, 0.45), None]                     # None = bald / buzzed: skin
HATS = [(0.9, 0.85, 0.75), (0.85, 0.15, 0.1), (0.1, 0.2, 0.6), (0.9, 0.7, 0.1), (0.1, 0.5, 0.2), (0.6, 0.2, 0.7)]


def crowd_look(rng):
    """(shirt, pants, skin, hair, sleeves, hat) for one person: hair on most heads, sleeves on most raised arms, a few
    bucket hats - bare skin everywhere read as a field of beige mannequins (2026-10-05)."""
    skin = rng.choice(SKIN)
    hair = rng.choice(HAIR) or skin
    return (rng.choice(CLOTHES), rng.choice(PANTS), skin, hair, rng.random() < 0.6,
            rng.choice(HATS) if rng.random() < 0.09 else None)


def person(bm, px, py, z0, h, w, yaw, pose, detail, parts=None, look=None):
    """Low-poly human. detail 2 (front rows): legs, torso, round head, two-part arms; 1: one body, head, raised arms;
    0 (far): two boxes. Poses: down, up (both hands up), one (one hand up), hips (hands on hips)."""
    R = Matrix.Rotation(yaw, 3, "Z")

    def P(x, y, z):
        return Vector((px, py, z0)) + R @ Vector((x, y, z))
    hip, sh, head = h * 0.50, h * 0.80, h * 0.915
    shx = w * 0.47
    shirt, pants, skin = (look or ((0.05, 0.05, 0.05),) * 3)[:3]
    hair, sleeves, hat = (look[3:6] if look and len(look) >= 6 else (skin, False, None))
    def mark(f0, col):
        if parts is not None:
            parts.append((f0, len(bm.faces), col))
    f0 = len(bm.faces)
    if detail == 0:
        m = Matrix.Translation(P(0, 0, h * 0.41)) @ R.to_4x4()
        bmesh.ops.create_cube(bm, size=1.0, matrix=m @ Matrix.Diagonal(Vector((w, w * 0.55, h * 0.82, 1.0))))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(P(0, 0, h * 0.91)) @ R.to_4x4()
                              @ Matrix.Diagonal(Vector((0.22, 0.24, 0.26, 1.0))))
        mark(f0, shirt)
        if pose == "up":
            f1 = len(bm.faces)
            for s_ in (-1, 1):
                bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(P(s_ * w * 0.55, 0, h * 1.05)) @ R.to_4x4()
                                      @ Matrix.Diagonal(Vector((0.12, 0.12, 0.62, 1.0))))
            mark(f1, skin)
        return
    if detail == 2:
        for s_ in (-1, 1):
            limb(bm, P(s_ * 0.09, 0, 0.03), P(s_ * 0.1, 0, hip), 0.06, 0.085, 6)
        mark(f0, pants)
        f1 = len(bm.faces)
        limb(bm, P(0, 0, hip - 0.06), P(0, 0, sh), w * 0.34, w * 0.47, 8, squash=0.62)
        mark(f1, shirt)
    else:
        limb(bm, P(0, 0, 0.0), P(0, 0, sh), w * 0.30, w * 0.47, 6, squash=0.62)
        mark(f0, shirt)
    f1 = len(bm.faces)
    hc = P(0, 0, head)
    bmesh.ops.create_icosphere(bm, subdivisions=2 if (detail == 2 and py > -11) else 1, radius=0.115,
                               matrix=Matrix.Translation(hc) @ Matrix.Diagonal(Vector((1.0, 1.1, 1.2, 1.0))))
    if parts is not None:                                              # hair: crown + back of the head, face: skin
        parts.append((f1, len(bm.faces), {"skin": skin, "hair": hair, "c": hc.copy(), "front": R @ Vector((0, 1, 0))}))
    if hat is not None and detail == 2:                                # bucket hat: brim + crown
        f2 = len(bm.faces)
        limb(bm, hc + Vector((0, 0, 0.06)), hc + Vector((0, 0, 0.1)), 0.18, 0.17, 8, squash=1.0)
        limb(bm, hc + Vector((0, 0, 0.09)), hc + Vector((0, 0, 0.19)), 0.12, 0.1, 8, squash=1.0)
        mark(f2, hat)
    segs = 5 if detail == 2 else 4
    for s_ in (-1, 1):
        shoulder = P(s_ * shx, 0, sh - 0.04)
        up = pose == "up" or (pose == "one" and s_ == 1)
        if up:
            elbow, hand = P(s_ * (shx + 0.12), 0.04, sh + 0.32), P(s_ * (shx + 0.2), 0.08, h + 0.42)
        elif detail == 1:
            continue                                                   # far-ish people: lowered arms not worth it
        elif pose == "hips":
            elbow, hand = P(s_ * (shx + 0.22), -0.02, hip + 0.25), P(s_ * (shx * 0.8), 0.02, hip + 0.04)
        else:
            elbow, hand = P(s_ * (shx + 0.05), 0.02, hip + 0.18), P(s_ * (shx + 0.04), 0.06, hip - 0.12)
        f1 = len(bm.faces)
        limb(bm, shoulder, elbow, 0.055, 0.045, segs)
        mark(f1, shirt if (not up or sleeves) else skin)
        f1 = len(bm.faces)
        limb(bm, elbow, hand, 0.045, 0.04, segs)
        mark(f1, skin)


def build_crowd(target=2100, exclude=(), extra=()):
    """Static low-poly audience (detailed near the stage, simpler far away) and phone lights; bodies are baked.
    exclude: (x0, y0, x1, y1) rectangles nobody stands in (FOH, tower bases); extra: (x, y, yaw, pose) people placed by
    the grounds modules (queues at the vendors, the second stage's audience)."""
    bm, lights, flags = bmesh.new(), bmesh.new(), bmesh.new()
    fuv = flags.loops.layers.uv.new("UVMap")
    rng = random.Random(11)
    uvl = bm.loops.layers.uv.new("UVMap")
    col = bm.loops.layers.float_color.new("Col")                     # clothing/skin albedo, baked with the lighting
    parts = []
    people = []                                                        # (first face, end face, x, y, floor z, height)
    n, y = 0, -8.6
    while y > -90 and n < target:
        half = 14 + 0.5 * (-y)
        gap = 0.82 + 0.016 * (-y - 9)
        x = -half + rng.uniform(0, gap)
        while x < half and n < target:
            h, w, yaw = rng.uniform(1.55, 1.92), rng.uniform(0.38, 0.5), rng.uniform(-0.5, 0.5)
            px, py, z0 = x + rng.uniform(-0.25, 0.25), y + rng.uniform(-0.35, 0.35), -1.5
            if any(x0 <= px <= x1 and y0 <= py <= y1 for x0, y0, x1, y1 in exclude):
                x += gap * rng.uniform(0.85, 1.25)
                continue
            pose = rng.choices(("down", "up", "one", "hips"), weights=(0.45, 0.3, 0.17, 0.08))[0]
            detail = 2 if py > -14 else (1 if py > -34 else 0)
            f0 = len(bm.faces)
            look = crowd_look(rng)
            person(bm, px, py, z0, h, w, yaw, pose, detail, parts, look)
            top = h + 0.75
            if pose != "up" and -40 < py < -12 and rng.random() < 0.025:   # festival flags / totems on poles
                f1 = len(bm.faces)
                hx = px + 0.3
                limb(bm, Vector((hx, py, z0 + h * 0.75)), Vector((hx, py, z0 + 3.6)), 0.02, 0.02, 4, caps=False)
                parts.append((f1, len(bm.faces), (0.6, 0.6, 0.6)))
                fl = [flags.verts.new(c) for c in ((hx, py, z0 + 3.55), (hx + 1.1, py - 0.08, z0 + 3.5),
                                                     (hx + 1.1, py - 0.08, z0 + 2.85), (hx, py, z0 + 2.9))]
                f = flags.faces.new(fl)
                u = (rng.randrange(6) + 0.5) / 6                       # palette column (T_DinoFlags)
                for loop in f.loops:
                    loop[fuv].uv = (u, 0.5)
                top = 3.7
            if pose != "up" and rng.random() < 0.09:                   # phone held up: a light the stage can see
                bmesh.ops.create_icosphere(lights, subdivisions=0, radius=0.06,
                                           matrix=Matrix.Translation((px + 0.15, py, z0 + h + 0.35)))
            people.append((f0, len(bm.faces), px, py, z0, top - 0.75))
            n += 1
            x += gap * rng.uniform(0.85, 1.25)
        y -= 0.95 + 0.012 * (-y - 9)
    for e in extra:                                                    # (x, y, yaw, pose[, floor z]), like crowd3: an
        ex, ey, eyaw, epose = e[:4]                                    # optional 5th value stands the person on a floor
        ez = e[4] if len(e) > 4 else -1.5                              # at that (pre-drop) height, e.g. the deck z=0
        h, w = rng.uniform(1.55, 1.92), rng.uniform(0.38, 0.5)
        f0 = len(bm.faces)
        look = crowd_look(rng)
        person(bm, ex, ey, ez, h, w, eyaw, epose if epose in ("down", "up", "one", "hips") else "down",
               1 if math.hypot(ex, ey) < 70 else 0, parts, look)
        people.append((f0, len(bm.faces), ex, ey, ez, h))
    # UVs: one square cell per person, wrapped around them like a bottle label (angle -> u, height -> v); the seam
    # sits at the back. Generic unwrappers packed these little faces into <4% of the texture.
    bm.faces.ensure_lookup_table()
    for a, b, c in parts:
        for fi in range(a, b):
            f = bm.faces[fi]
            if isinstance(c, dict):                                    # a head: hair above the brow and at the back
                d = f.calc_center_median() - c["c"]
                c2 = c["hair"] if (d.z > 0.035 or (d.z > -0.07 and d.dot(c["front"]) < -0.03)) else c["skin"]
            else:
                c2 = c
            for loop in f.loops:
                loop[col] = (*c2, 1.0)
    cols = math.ceil(math.sqrt(len(people)))
    cs = 1.0 / cols
    pad = cs * 0.06
    for k, (f0, f1, px, py, z0, h) in enumerate(people):
        ox, oy = (k % cols) * cs + pad, (k // cols) * cs + pad
        span = cs - 2 * pad
        for fi in range(f0, f1):
            f = bm.faces[fi]
            c = f.calc_center_median()
            ac = math.atan2(c.x - px, -(c.y - py))                    # 0 = facing the stage (+Y); +-pi = the back
            for loop in f.loops:
                v = loop.vert.co
                a = math.atan2(v.x - px, -(v.y - py)) if math.hypot(v.x - px, v.y - py) > 1e-4 else ac
                if abs(a - ac) > math.pi:
                    a += 2 * math.pi if a < ac else -2 * math.pi
                u = min(max((a + math.pi) / (2 * math.pi), 0.0), 1.0)
                w_ = min(max((v.z - z0) / (h + 0.75), 0.0), 1.0)
                loop[uvl].uv = (ox + u * span, oy + w_ * span)
    log(f"crowd: {n} people + {len(extra)} from the grounds, {cols}x{cols} UV cells")
    return new_obj("SM_DinoCrowd", bm), new_obj("SM_DinoPhones", lights), new_obj("SM_DinoFlags", flags)


# v14 walkways into the crowd (the user, 2026-10-09: "i need a path to get into the crowd", then "do everything": both
# routes drawn for them). A: stairs off the deck's front edge at x 9.1..10.6, between the lip lights at x 8 and 11; B: on
# the right wing at x 15.5..16.7, east of the truss tower. Each: STAIR_N risers of STAIR_RISE m on STAIR_RUN m treads from
# the deck edge (y -4.5, z 0) down to the field (z -1.5), handrails on both sides, and a gate in the crowd barrier in
# line with it. grounds/... and the walking map (dino_collide.py) read WALKWAYS.
WALKWAYS = {"A": (9.1, 10.6), "B": (15.5, 16.7)}
STAIR_RISE, STAIR_RUN, STAIR_N = 0.1875, 0.3, 8
DECK_FRONT_Y, BARRIER_Y = -4.5, -7.5


def build_deck():
    bm = bmesh.new()
    def box(center, size):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(center) @ Matrix.Diagonal(Vector(size).to_4d()))
    box((0, 4.5, -0.75), (50.0, 18.0, 1.5))                          # stage deck: top flush with Tribe's floor (z=0)
    gaps = sorted(WALKWAYS.values())
    xs = [-30.0] + [v for g in gaps for v in g] + [30.0]
    for x0, x1 in zip(xs[0::2], xs[1::2]):                            # crowd barrier, a gate in line with each walkway
        box(((x0 + x1) / 2, BARRIER_Y, -0.9), (x1 - x0, 0.25, 1.2))
    for x in range(-29, 30, 2):                                       # barrier feet (none in the gates)
        if not any(g0 - 0.3 < x < g1 + 0.3 for g0, g1 in gaps):
            box((x, BARRIER_Y - 0.3, -1.45), (0.12, 0.8, 0.1))
    for g0, g1 in gaps:
        for gx in (g0 - 0.06, g1 + 0.06):                             # gate posts
            box((gx, BARRIER_Y, -0.85), (0.12, 0.35, 1.3))
        w, xc = g1 - g0, (g0 + g1) / 2
        for i in range(1, STAIR_N):                                   # the stairs: solid steps down to the field
            top = -STAIR_RISE * i
            box((xc, DECK_FRONT_Y - STAIR_RUN * (i - 0.5), (top - 1.5) / 2), (w, STAIR_RUN, top + 1.5))
        y_end = DECK_FRONT_Y - STAIR_RUN * (STAIR_N - 1)
        for hx in (g0 + 0.04, g1 - 0.04):                             # handrails: posts and a rail along the slope
            for (py, pz) in ((DECK_FRONT_Y - 0.05, 0.0), (y_end + 0.05, -STAIR_RISE * (STAIR_N - 1))):
                limb(bm, Vector((hx, py, pz)), Vector((hx, py, pz + 0.95)), 0.025, 0.025, 6)
            limb(bm, Vector((hx, DECK_FRONT_Y - 0.05, 0.95)),
                 Vector((hx, y_end + 0.05, -STAIR_RISE * (STAIR_N - 1) + 0.95)), 0.022, 0.022, 6)
    return new_obj("SM_DinoDeck", bm)


def truss(bm, a, b, size=0.6, step=1.0):
    """Box truss from a to b: four chords plus zig-zag lacing on every face."""
    d = b - a
    L, t = d.length, d.normalized()
    ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
    u = t.cross(ref).normalized()
    v = t.cross(u).normalized()
    hs = size / 2
    corners = [u * hs + v * hs, -u * hs + v * hs, -u * hs - v * hs, u * hs - v * hs]
    for c in corners:
        limb(bm, a + c, b + c, 0.035, 0.035, 6, caps=False)
    n = max(1, int(L / step))
    for i in range(n):
        p0, p1 = a + t * (L * i / n), a + t * (L * (i + 1) / n)
        for k in range(4):
            c0, c1 = corners[k], corners[(k + 1) % 4]
            limb(bm, p0 + (c0 if i % 2 == 0 else c1), p1 + (c1 if i % 2 == 0 else c0), 0.016, 0.016, 4, caps=False)


def moving_head(rig, lenses, base, pitch_deg, yaw_deg, lens_u, aim=None, mover=None):
    """A moving-head fixture: base, yoke, head; its lens is a separate glowing disc (color picked by lens_u).
    aim: a direction to point the head along instead of pitch/yaw (the lens center is then base+(0,0,0.42)+aim*0.205).
    mover (v13): {"bm": the moving mesh, "lays": its LASER_UV layers, "lens_lays": the lenses' ones, "uv": the five
    values (atmosphere.STAGE_MOVES, z dropped), "yoke": the same with tilt 0}: the yoke and head go to the moving mesh
    with that data (the yoke only pans), the lens disc carries it too; the base stays in the baked rig."""
    if aim is not None:
        a = Vector(aim).normalized()
        yaw_deg = math.degrees(math.atan2(a.x, -a.y))
        pitch_deg = math.degrees(-math.asin(max(-1.0, min(1.0, a.z))))
    R = Matrix.Rotation(math.radians(yaw_deg), 4, "Z")

    def box(c, sz, bm=rig):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(base) @ R @ Matrix.Translation(c)
                              @ Matrix.Diagonal(Vector((*sz, 1.0))))

    def stamp_new(bm, before, lays, vals):                             # the faces made since `before` get the data
        for f in [f for f in bm.faces if f not in before]:               # (not an index range: bmesh.ops reuse slots)
            for lp in f.loops:
                for lay, val in zip(lays, vals):
                    lp[lay].uv = val
    box((0, 0, 0.08), (0.42, 0.42, 0.16))
    moving = mover["bm"] if mover else rig
    n0 = set(moving.faces) if mover else None
    for s_ in (-1, 1):
        box((s_ * 0.22, 0, 0.36), (0.06, 0.12, 0.42), bm=moving)
    if mover:
        stamp_new(moving, n0, mover["lays"], mover["yoke"])
    head_c = base + (R @ Vector((0, 0, 0.42, 0))).to_3d()
    aim = (R @ Matrix.Rotation(math.radians(pitch_deg), 4, "X") @ Vector((0, -1, 0, 0))).to_3d().normalized()
    n0 = set(moving.faces) if mover else None
    limb(moving, head_c - aim * 0.22, head_c + aim * 0.2, 0.17, 0.2, 10)
    if mover:
        stamp_new(moving, n0, mover["lays"], mover["uv"])
    rot = Vector((0, 0, 1)).rotation_difference(aim).to_matrix().to_4x4()
    n0 = set(lenses.faces) if mover else None
    ret = bmesh.ops.create_circle(lenses, cap_ends=True, segments=12, radius=0.16,
                                  matrix=Matrix.Translation(head_c + aim * 0.205) @ rot)
    uv = lenses.loops.layers.uv.get("UVMap")
    for f in {f for v in ret["verts"] for f in v.link_faces}:
        for loop in f.loops:
            loop[uv].uv = (lens_u, 0.5)
    if mover:
        stamp_new(lenses, n0, mover["lens_lays"], mover["uv"])


LENS_U = {k: (i + 0.5) / 8 for i, k in enumerate(("white", "cyan", "magenta", "amber", "blue", "red", "green", "warm"))}


def build_rig(aims=None, colors=None, moves=None):
    """Metal: truss towers flying the line arrays, ground subs, fixtures on the deck lip and tower tops, the DJ booth.
    aims: 19 (lens position, direction) pairs (tower tops -13.9, -12.8, -11.7, 13.9, 12.8, 11.7, then the deck lip left
    to right) from grounds/atmosphere.py, so the heads point where its frozen beams go."""
    rig, lenses = bmesh.new(), bmesh.new()
    lenses.loops.layers.uv.new("UVMap")
    # v13: moves = atmosphere.STAGE_MOVES (19 x the five LASER_UV values): the yokes and heads go to a moving mesh
    moves = list(moves) if moves and len(moves) == 19 else None
    heads = bmesh.new() if moves else None
    lens_lays = [lenses.loops.layers.uv.new(n) for n in LASER_LAYERS[1:]] if moves else None
    head_lays = None
    if moves:
        heads.loops.layers.uv.new("UVMap")
        head_lays = [heads.loops.layers.uv.new(n) for n in LASER_LAYERS[1:]]
    fixture = list(aims) if aims and len(aims) == 19 else None
    if aims and fixture is None:
        log(f"STAGE_AIMS has {len(aims)} entries, expected 19: fixtures keep their default aim")
    colors = list(colors) if colors and len(colors) == 19 else None
    count = [0]

    def nxt(lens_u):
        """(aim, lens_u, mover) of the next fixture: the beam direction and lens color from grounds/atmosphere.py if
        given, and its motion data (v13)."""
        i = count[0]
        count[0] += 1
        if colors and colors[i] in LENS_U:
            lens_u = LENS_U[colors[i]]
        mv = None
        if moves:
            (px, py), (pz, ph), (pa, ta), cue, fix = moves[i]
            uv = ((px, py), (pz - STAGE_DROP, ph), (pa, ta), cue, fix)    # the pivots follow the stage drop
            mv = {"bm": heads, "lays": head_lays, "lens_lays": lens_lays, "uv": uv,
                  "yoke": (uv[0], uv[1], (pa, 0.0), cue, fix)}
        return (Vector(fixture[i][1]) if fixture else None), lens_u, mv
    for side in (-1, 1):
        x = side * 15.2
        truss(rig, Vector((x, -3.0, 0.0)), Vector((x, -3.0, 17.0)))             # tower
        truss(rig, Vector((x, -3.0, 16.4)), Vector((side * 11.8, -3.0, 16.4)))  # arm over the line array
        for k in range(9):                                                       # line array: 9 boxes curving into a J
            tilt = math.radians(0.75 * k * k)
            m = (Matrix.Translation((side * 12.5, -3.0 - 0.015 * k * k, 15.4 - 0.62 * k))
                 @ Matrix.Rotation(-tilt, 4, "X") @ Matrix.Diagonal(Vector((1.3, 0.85, 0.55, 1.0))))
            bmesh.ops.create_cube(rig, size=1.0, matrix=m)
        limb(rig, Vector((side * 12.5, -3.0, 16.3)), Vector((side * 12.5, -3.0, 15.7)), 0.03, 0.03, 4)
        for k in range(2):                                                       # ground subs, two high
            for zc in (0.65, 1.95):
                bmesh.ops.create_cube(rig, size=1.0, matrix=Matrix.Translation((side * (19.5 + 1.7 * k), -3.0, zc))
                                      @ Matrix.Diagonal(Vector((1.5, 1.2, 1.3, 1.0))))
        for k in range(3):                                                       # tower-top fixtures
            a, u, mv = nxt((k + (0 if side < 0 else 3) + 0.5) / 8)
            moving_head(rig, lenses, Vector((x - side * (1.3 + 1.1 * k), -3.0, 16.75)), 70, 0, u, aim=a, mover=mv)
    for i, x in enumerate(range(-19, 20, 3)):                                    # deck-lip fixtures, up and out
        a, u, mv = nxt(((i % 6) + 0.5) / 8)
        moving_head(rig, lenses, Vector((x, -4.3, 0.0)), 35 + 15 * (i % 3), x * 1.2, u, aim=a, mover=mv)
    build_props(rig)
    return (new_obj("SM_DinoRig", rig), new_obj("SM_DinoLenses", lenses),
            new_obj("SM_DinoMoverHeads", heads) if heads is not None else None)


def build_props(rig):
    """Festival gear on the deck (z=0 before the drop): CO2 cannons, flame units, road-case stacks, wedge monitors."""
    def box(c, sz, yaw=0.0):
        bmesh.ops.create_cube(rig, size=1.0, matrix=Matrix.Translation(c) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
                              @ Matrix.Diagonal(Vector((*sz, 1.0))))
    for x in (-17.5, -11.5, 11.5, 17.5):                               # CO2 cannons: tripod + tilted barrel
        for k in range(3):
            a = math.radians(120 * k)
            limb(rig, Vector((x + 0.32 * math.cos(a), -4.5 + 0.32 * math.sin(a), 0.0)), Vector((x, -4.5, 0.55)),
                 0.025, 0.025, 4)
        limb(rig, Vector((x, -4.4, 0.5)), Vector((x, -4.85, 1.25)), 0.13, 0.11, 10)
    for x in (-22.5, -14.5, 14.5, 22.5):                               # flame units: box + nozzle
        box((x, -4.4, 0.2), (0.55, 0.55, 0.4))
        limb(rig, Vector((x, -4.4, 0.4)), Vector((x, -4.4, 0.75)), 0.06, 0.045, 8)
    rng = random.Random(3)
    for cx, cy in ((-21.5, 8.5), (21.5, 8.5), (-9.0, 11.5), (9.0, 11.5), (-23.0, 2.0), (23.0, 2.0)):   # road cases
        z = 0.0
        for k in range(rng.randint(2, 3)):
            hgt = rng.uniform(0.6, 0.9)
            box((cx + rng.uniform(-0.1, 0.1), cy + rng.uniform(-0.1, 0.1), z + hgt / 2), (1.2, 0.65, hgt), rng.uniform(-8, 8))
            z += hgt
    for x in (-2.4, 2.4):                                               # wedge monitors facing the riser
        v = [rig.verts.new(c) for c in ((x - 0.35, -2.9, 0), (x + 0.35, -2.9, 0), (x + 0.35, -3.5, 0), (x - 0.35, -3.5, 0),
                                         (x - 0.35, -3.5, 0.45), (x + 0.35, -3.5, 0.45))]
        for f in ((0, 3, 2, 1), (3, 4, 5, 2), (0, 1, 5, 4), (0, 4, 3), (1, 2, 5)):
            rig.faces.new([v[i] for i in f])


def frond(bm, base, ang, length, lift_deg, rng):
    """One curved fern frond: a tapered strip arching up and drooping (two-sided material)."""
    d = Vector((math.cos(ang), math.sin(ang), math.tan(math.radians(lift_deg)))).normalized()
    side = Vector((-math.sin(ang), math.cos(ang), 0))
    pts, pos, n = [], base.copy(), 9
    for i in range(n + 1):
        pts.append(pos.copy())
        pos = pos + d * (length / n)
        d = (d + Vector((0, 0, -0.16))).normalized()
    prev = None
    for i, p_ in enumerate(pts):
        u = i / n
        w = 0.42 * math.sin(math.pi * min(u * 1.15, 1.0)) + 0.02
        pair = (bm.verts.new(p_ - side * w), bm.verts.new(p_ + side * w))
        if prev:
            bm.faces.new((prev[0], pair[0], pair[1], prev[1]))          # normal up: the bake sees the lit side
        prev = pair


def build_decor(bone_bm):
    """Jurassic decor at deck level: fern clusters (own two-sided mesh), egg clutches and loose ribs (bone)."""
    plants = bmesh.new()
    rng = random.Random(5)
    for x, y in ((-23.5, -4.8), (23.5, -4.8), (-6.2, -2.3), (6.2, -2.3), (-12.5, 6.5), (12.5, 6.5), (-19.5, 6.5),
                 (19.5, 6.5), (-4.0, 6.0), (4.0, 6.0)):
        for k in range(rng.randint(8, 12)):
            frond(plants, Vector((x + rng.uniform(-0.2, 0.2), y + rng.uniform(-0.2, 0.2), 0.0)),
                  rng.uniform(0, 2 * math.pi), rng.uniform(1.4, 2.6), rng.uniform(40, 70), rng)
    for cx, cy in ((-5.6, -3.4), (5.6, -3.4)):                         # egg clutches beside the riser front
        for k in range(3):
            a = math.radians(120 * k + 20)
            bmesh.ops.create_uvsphere(bone_bm, u_segments=16, v_segments=10, radius=1.0,
                                      matrix=Matrix.Translation((cx + 0.55 * math.cos(a), cy + 0.55 * math.sin(a), 0.62))
                                      @ Matrix.Rotation(math.radians(rng.uniform(-12, 12)), 4, "Y")
                                      @ Matrix.Diagonal(Vector((0.5, 0.5, 0.68, 1.0))))
    for k, (x, y, a) in enumerate(((-8.0, -3.6, 20), (8.3, -3.2, 160), (-2.0, 7.2, 80))):   # loose ribs on the deck
        c = Vector((x, y, 0.15))
        pts = [c + Vector((math.cos(math.radians(a)) * 1.6 * (t - 0.5) * 2, math.sin(math.radians(a)) * 1.6 * (t - 0.5) * 2,
                           0.9 * math.sin(math.pi * t))) for t in [i / 16 for i in range(17)]]
        tube(bone_bm, pts, lambda u: 0.12 * (1 - 0.6 * u) + 0.03, segs=8)
    return new_obj("SM_DinoPlants", plants)


def build_riser():
    """The DJ platform: NOT dropped, its top is Tribe's floor (z=0). Riser + stairs + the booth table under the gear,
    an LED face on the table front and the riser front (SM_DinoBooth), glowing edge strips (SM_DinoGlow)."""
    rz, led, glow = bmesh.new(), bmesh.new(), bmesh.new()
    uv = led.loops.layers.uv.new("UVMap")
    def box(b, c, sz):
        bmesh.ops.create_cube(b, size=1.0, matrix=Matrix.Translation(c) @ Matrix.Diagonal(Vector((*sz, 1.0))))
    box(rz, (0, 0.25, -STAGE_DROP / 2), (9.0, 5.5, STAGE_DROP))        # riser: y -2.5..3.0, deck level to z=0
    for s_ in (-1, 1):                                                   # stairs down to the deck at the back corners
        for k in range(4):
            t = (k + 1) * STAGE_DROP / 5                                 # step k: from the deck (z -DROP) up to z -t
            box(rz, (s_ * (4.5 + 0.35 * k + 0.175), 2.0, -(STAGE_DROP + t) / 2), (0.35, 1.8, STAGE_DROP - t))
    T = TABLE
    w, d, top = T["x1"] - T["x0"], T["y1"] - T["y0"], T["top"]
    cx, cy = (T["x0"] + T["x1"]) / 2, (T["y0"] + T["y1"]) / 2
    box(rz, (cx, cy, top / 2), (w, d, top))                            # booth table under the decks
    box(rz, (cx, cy, top - 0.02), (w + 0.12, d + 0.12, 0.04))          # table lip
    def quad(x0, x1, y, z0, z1):                                        # LED face toward the crowd (-Y), CCW seen from -Y
        vs = [led.verts.new(c) for c in ((x1, y, z0), (x0, y, z0), (x0, y, z1), (x1, y, z1))]
        f = led.faces.new(vs)
        for loop, uvc in zip(f.loops, ((1, 0), (0, 0), (0, 1), (1, 1))):
            loop[uv].uv = uvc
    quad(T["x0"] + 0.03, T["x1"] - 0.03, T["y0"] - 0.065, 0.06, top - 0.06)
    quad(-4.4, 4.4, -2.505, -STAGE_DROP + 0.08, -0.08)
    for x0, x1, y0, y1 in ((-4.5, 4.5, -2.53, -2.47), (-4.53, -4.47, -2.5, 3.0), (4.47, 4.53, -2.5, 3.0)):
        box(glow, ((x0 + x1) / 2, (y0 + y1) / 2, 0.01), (x1 - x0, y1 - y0, 0.03))   # edge strips on the riser top
    return new_obj("SM_DinoRiser", rz), new_obj("SM_DinoBooth", led), new_obj("SM_DinoGlow", glow)


def build_pillars():
    """LED pillars on the deck (dropped with the set)."""
    bm = bmesh.new()
    for x in (-9.5, 9.5, -21.0, 21.0):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((x, 0.5, 3.0)) @ Matrix.Diagonal(Vector((0.4, 0.4, 6.0, 1.0))))
    return new_obj("SM_DinoPillars", bm)


def build_screen():
    bm = bmesh.new()
    m = Matrix.Translation((0, 10.9, 7.2)) @ Matrix.Rotation(math.radians(90), 4, "X")
    ret = bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=5.5, matrix=m)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = (0.5 + co.x / 11.0, 0.5 + (co.z - 7.2) / 11.0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:                                                # face the crowd (-Y)
        if f.normal.y > 0:
            f.normal_flip()
    return new_obj("SM_DinoScreen", bm)


GROUND_HALF, GROUND_CY = 160.0, -60.0   # baked field: x -160..160, y -220..100 (grounds out to the woods)


# pre-drop m. The user (2026-10-06): "make the arches bigger ... wider" and "the screen to match that arch shape as
# well". The screen fills the arch opening: it stands in the arch's own plane, its edge 1.5 cm inside the innermost
# vertex line of the spine and the lintel under the neck (arch.screen_outline), so the bone frames it from every
# viewpoint and nothing crosses it. The moon and its bulb ring stand behind it and show when Tribe's visuals are off
# and Tribe hides the screen. "box" is the video box: the smallest 16:9 rectangle around the outline (arch.video_box),
# so the frame keeps its aspect and its top and bottom rows fall outside the arch.
VISUAL_SCREEN = {"y": arch.SCREEN_Y, "outline": arch.screen_outline(), "box": arch.video_box()}


def build_visual_screen():
    """The big screen for Tribe's own visuals (videos and GIFs from the media folder, text, NDI): one arch-shaped polygon
    facing the crowd (-Y), triangulated, with Tribe's back-wall UV layout (its SM_BackdropScreen_OldStyleUVs, which
    M_VideoBackdrop expects) over the video box (arch.screen_uv): U runs 1 -> 0 from the box's left to its right edge as
    seen from the crowd, and V uses only the lower half (UE V 0.5 at the box top, 1.0 at its bottom; in Blender V is up
    and the FBX import flips it, hence 0.5 at the top here and 0 at the bottom). The video shader samples at
    (1 - U, 2V - 1), so the frame lands the right way round. The mod finds the screen by its mesh name, registers it as
    the environment backdrop (BP_TribeVisualsManager_C.SetupEnvironmentBackdrop) after the level loads and sets Tribe's
    video mapping to fill it (StretchMode, one copy)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    y, box = VISUAL_SCREEN["y"], VISUAL_SCREEN["box"]
    f = bm.faces.new([bm.verts.new((x, y, z)) for x, z in VISUAL_SCREEN["outline"]])
    f.normal_update()                                                  # a new bmesh face's normal is zero until updated
    if f.normal.y > 0:                                                 # face the crowd
        f.normal_flip()
    bmesh.ops.triangulate(bm, faces=[f], quad_method="BEAUTY", ngon_method="BEAUTY")
    for f in bm.faces:
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = arch.screen_uv(co.x, co.z, box)
    return new_obj("SM_DinoVisualScreen", bm)


def build_ground():
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap")
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=GROUND_HALF, matrix=Matrix.Translation((0, GROUND_CY, -1.5)),
                          calc_uvs=True)
    near = new_obj("SM_DinoGround", bm)                               # the festival field (baked light pools)
    bm2 = bmesh.new()
    bmesh.ops.create_grid(bm2, x_segments=1, y_segments=1, size=600.0, matrix=Matrix.Translation((0, 0, -1.6)))
    return near, new_obj("SM_DinoFarGround", bm2)


def build_sky():
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=480.0)
    ob = new_obj("SM_DinoSky", bm)
    me = ob.data
    me.uv_layers.new(name="UVMap")
    uvl = me.uv_layers[0].data                                        # equirect UVs from the vertex direction
    for poly in me.polygons:
        lon_c = math.atan2(poly.center.y, poly.center.x)
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            lon = math.atan2(co.y, co.x) if math.hypot(co.x, co.y) > 1e-3 else lon_c   # poles take the face's longitude
            if abs(lon - lon_c) > math.pi:                            # seam: keep a face's UVs on one side
                lon += 2 * math.pi if lon < lon_c else -2 * math.pi
            lat = math.asin(max(-1.0, min(1.0, co.z / 480.0)))
            uvl[li].uv = ((lon + math.pi) / (2 * math.pi), 0.5 + lat / math.pi)
    for p in me.polygons:
        p.flip()                                                      # seen from inside
    return ob


# ---------------------------------------------------------------- procedural textures (linear RGB, top-down rows)
def tex_sky(w=4096, h=2048):
    v = (np.arange(h)[::-1] + 0.5) / h                                # top row = zenith
    lat = (v - 0.5) * np.pi
    lon = ((np.arange(w) + 0.5) / w) * 2 * np.pi - np.pi
    L, LON = np.meshgrid(lat, lon, indexing="ij")
    up = np.clip(np.sin(L), 0, 1)
    zen = np.array([0.0035, 0.0055, 0.016])
    hor = np.array([0.012, 0.009, 0.016])                              # night pass: horizon glow x0.4
    img = hor * (1 - up[..., None]) ** 2.2 + zen * (1 - (1 - up[..., None]) ** 2.2)
    stage_dir = np.cos(LON - np.pi / 2)                                # +Y (behind the stage): warm light pollution
    glow = np.clip(stage_dir, 0, 1) ** 3 * np.exp(-np.maximum(L, 0) / 0.18)
    img += glow[..., None] * np.array([0.04, 0.014, 0.008])          # town glow behind the stage x0.4
    img[L < 0] = np.array([0.004, 0.004, 0.006])                      # below the horizon: dark
    n = 9000                                                           # stars, uniform over the upper hemisphere
    s_lon = np.random.uniform(-np.pi, np.pi, n)
    s_lat = np.arcsin(np.random.uniform(0.04, 1.0, n))
    mag = np.random.exponential(0.12, n) + 0.02
    tint = np.random.uniform(0.75, 1.0, (n, 3)) * np.array([0.95, 0.97, 1.0])
    px = ((s_lon + np.pi) / (2 * np.pi) * w).astype(int) % w
    py = ((0.5 - s_lat / np.pi) * h).astype(int).clip(0, h - 1)
    for dy, dx, f in ((0, 0, 1.0), (0, 1, 0.35), (1, 0, 0.35), (0, -1, 0.35), (-1, 0, 0.35)):
        img[(py + dy).clip(0, h - 1), (px + dx) % w] += (mag[:, None] * f * np.cos(s_lat)[:, None] ** 0) * tint
    band = np.exp(-((L - 0.55 * np.sin(LON * 1.0 + 0.6)) / 0.16) ** 2) * (L > 0)   # faint milky band
    rnd = np.random.rand(h, w) ** 6
    img += (band * rnd)[..., None] * np.array([0.03, 0.03, 0.036])
    return img


def tex_lens(w=256, h=16):
    pal = np.array([(1.0, 1.0, 1.0), (0.2, 0.9, 1.0), (1.0, 0.2, 0.8), (1.0, 0.6, 0.15),
                    (0.3, 0.45, 1.0), (1.0, 0.15, 0.1), (0.3, 1.0, 0.4), (1.0, 0.95, 0.8)])
    idx = (np.arange(w) * len(pal) // w)
    return np.repeat(pal[idx][None, :, :], h, axis=0)


def tex_flags(w=96, h=8):
    pal = np.array([(0.55, 0.06, 0.06), (0.06, 0.18, 0.6), (0.6, 0.5, 0.06), (0.06, 0.45, 0.15), (0.55, 0.15, 0.5),
                    (0.6, 0.28, 0.03)])
    return np.repeat(pal[(np.arange(w) * len(pal) // w)][None, :, :], h, axis=0)


def tex_booth(w=1024, h=288):
    y = (np.arange(h) + 0.5) / h
    x = (np.arange(w) + 0.5) / w
    Y, X = np.meshgrid(y, x, indexing="ij")
    img = np.zeros((h, w, 3)) + np.array([0.02, 0.012, 0.01])
    bars = (np.sin(Y * np.pi * 9) > 0.55) * (0.35 + 0.65 * np.abs(np.sin(X * np.pi * 3)))
    img += bars[..., None] * np.array([1.0, 0.38, 0.06])
    edge = (np.minimum(np.minimum(X, 1 - X) * w / h, np.minimum(Y, 1 - Y)) < 0.05)
    img[edge] = np.array([1.0, 0.55, 0.15])
    for k in range(3):                                                 # center claw mark: three glowing slashes
        cx = 0.5 + (k - 1) * 0.045
        d = np.abs((X - cx) * w / h - (Y - 0.5) * 0.45)
        m = (d < 0.035) & (np.abs(Y - 0.5) < 0.38)
        img[m] = np.array([1.0, 0.85, 0.6])
    return img


def tex_moon(s=1024):
    c = (np.arange(s) + 0.5) / s - 0.5
    Y, X = np.meshgrid(c, c, indexing="ij")
    r = np.sqrt(X * X + Y * Y) / 0.5
    img = np.stack([np.ones_like(r), 0.93 - 0.35 * r ** 2, 0.82 - 0.6 * r ** 2], -1).clip(0, None)
    for _ in range(140):                                               # red speckles / craters
        cx, cy = np.random.uniform(-0.42, 0.42, 2)
        rad = np.random.uniform(0.004, 0.03)
        m = np.exp(-((X - cx) ** 2 + (Y - cy) ** 2) / (2 * rad * rad))
        img -= m[..., None] * np.array([0.0, 0.75, 0.8]) * np.random.uniform(0.4, 1.0)
    return img.clip(0, 1.2)


# ---------------------------------------------------------------- materials for baking / preview
def mat_bone():
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
    vor = N.new("ShaderNodeTexVoronoi")                                # cracks: thin lines along Voronoi cell edges
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
    ao = N.new("ShaderNodeAmbientOcclusion")                           # darker crevices between horns and vertebrae
    ao.samples = 16
    ao.inputs["Distance"].default_value = 1.5
    Ln.new(cmix.outputs["Color"], ao.inputs["Color"])
    amix = N.new("ShaderNodeMixRGB")
    amix.inputs["Fac"].default_value = 0.75
    Ln.new(cmix.outputs["Color"], amix.inputs["Color1"])
    Ln.new(ao.outputs["Color"], amix.inputs["Color2"])
    Ln.new(amix.outputs["Color"], bsdf.inputs["Base Color"])
    hsum = N.new("ShaderNodeMath")                                     # bump: crack grooves + fine grain
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


def mat_metal():
    m = bpy.data.materials.new("Metal")                                # painted black steel; bakes as diffuse
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.06, 0.06, 0.065, 1)
    ramp.color_ramp.elements[1].color = (0.16, 0.16, 0.17, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.5
    return m


def mat_crowd():
    m = bpy.data.materials.new("Crowd")                                # per-part colors from the "Col" attribute
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "Col"
    dim = nt.nodes.new("ShaderNodeMixRGB")                            # night: clothes read darker than their palette
    dim.blend_type = "MULTIPLY"
    dim.inputs["Fac"].default_value = 1.0
    dim.inputs["Color2"].default_value = (0.5, 0.5, 0.5, 1)
    nt.links.new(vc.outputs["Color"], dim.inputs["Color1"])
    nt.links.new(dim.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.8
    return m


def mat_plant():
    m = bpy.data.materials.new("Plant")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 4.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.02, 0.10, 0.02, 1)
    ramp.color_ramp.elements[1].color = (0.12, 0.38, 0.06, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def mat_flat(name, rgb, rough=0.8):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def mat_emit(name, rgb=None, strength=1.0, image=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    if image is not None:
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = image
        nt.links.new(tx.outputs["Color"], em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = (*rgb, 1)
    nt.links.new(em.outputs["Emission"], outn.inputs["Surface"])
    return m


def mat_emit_col(name, strength=1.0, layer="Col"):
    """Emission colored by the mesh's color attribute (crowd v2's glow parts carry their colors in "Col")."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = layer
    nt.links.new(at.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], outn.inputs["Surface"])
    return m


def assign(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)


def load_png(path):
    img = bpy.data.images.load(path, check_existing=False)
    img.colorspace_settings.name = "sRGB"
    return img


# ---------------------------------------------------------------- lights for the bake (removed from nothing: bake only)
def add_light(name, kind, pos, target, color, power, size=1.0, spot_deg=40):
    ld = bpy.data.lights.new(name, kind)
    ld.color = color
    ld.energy = power
    if kind == "AREA":
        ld.shape = "DISK"
        ld.size = size
    if kind == "SPOT":
        ld.spot_size = math.radians(spot_deg)
        ld.spot_blend = 0.6
        ld.shadow_soft_size = size
    ob = bpy.data.objects.new(name, ld)
    ob.location = pos
    ob.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(ob)


def stage_lights():
    w = bpy.data.worlds.new("Night")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.022, 0.045, 1)
    scene.world = w
    for side in (-1, 1):
        for k in range(7):                                             # amber uplights at each horn base
            t = 0.10 + 0.78 * k / 6
            p = spine_point(side, t)
            add_light(f"Up{side}{k}", "SPOT", p + Vector((side * -1.8, -2.5, -0.4)), p + Vector((side * 1.5, 0, 10)),
                      (1.0, 0.48, 0.12), 6000 + 8000 * t, size=0.6, spot_deg=50)
        add_light(f"Blue{side}", "SPOT", (side * 16, 6, 34), (side * 8, 2, 8), (0.22, 0.4, 1.0), 70000, size=2, spot_deg=70)
        for k, col in enumerate(((1.0, 0.15, 0.6), (0.2, 0.4, 1.0), (1.0, 0.55, 0.1))):   # colored pools on the crowd
            add_light(f"Pool{side}{k}", "SPOT", (side * (6 + 7 * k), -3, 14), (side * (8 + 10 * k), -28 - 9 * k, -1.5),
                      col, 120000, size=0.5, spot_deg=16)
        for k in range(4):                                             # stage-front washes on the first rows
            add_light(f"Wash{side}{k}", "SPOT", (side * (3 + 6 * k), -4.0, 2.5), (side * (4 + 8 * k), -16, -0.5),
                      (0.75, 0.8, 1.0), 1100, size=0.4, spot_deg=45)
    # Night set (the user, 2026-10-05: "the lighting in the crowd needs to be WAY darker"): the soft fills that lit the
    # whole audience evenly are cut ~4x; the colored pools, beams, phones and totems carry the crowd now.
    add_light("Front", "AREA", (0, -45, 14), (0, 6, 10), (0.3, 0.4, 1.0), 1400, size=30)
    add_light("CrowdGlow", "AREA", (0, -8, 9), (0, -45, 0), (1.0, 0.5, 0.35), 3200, size=25)    # stage glow on the audience
    for side, col in ((-1, (1.0, 0.3, 0.8)), (1, (0.3, 0.5, 1.0))):    # colored side fills: no pitch-black flanks
        add_light(f"SideFill{side}", "AREA", (side * 30, -10, 6), (side * -8, -40, 0), col, 1800, size=15)
    sun = bpy.data.lights.new("Moon", "SUN")                           # faint blue moonlight: rims every head/shoulder
    sun.color, sun.energy, sun.angle = (0.5, 0.6, 1.0), 0.25, math.radians(10)
    so = bpy.data.objects.new("Moon", sun)
    so.rotation_euler = (math.radians(35), math.radians(-25), math.radians(20))
    coll.objects.link(so)
    for spec in skull.SKULL_LIGHTS:                                    # key from above the front rows, under-jaw fill, rims
        add_light(*spec)


# ---------------------------------------------------------------- unwrap + bake
def unwrap(ob, margin=0.003, lightmap=False):
    """Smart UV project; lightmap=True gives every face its own square instead (many small parts: smart_project packed
    the 44k-face crowd into 0.3% of the texture)."""
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    if lightmap:
        bpy.ops.uv.lightmap_pack(PREF_CONTEXT="ALL_FACES", PREF_PACK_IN_ONE=True, PREF_NEW_UVLAYER=False,
                                 PREF_BOX_DIV=12, PREF_MARGIN_DIV=0.2)
    else:
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=margin, area_weight=0.0, correct_aspect=True)
        bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")
    uv = ob.data.uv_layers.active.data
    area = 0.0
    for p in ob.data.polygons:
        pts = [uv[li].uv for li in p.loop_indices]
        area += abs(sum(pts[i].x * pts[(i + 1) % len(pts)].y - pts[(i + 1) % len(pts)].x * pts[i].y for i in range(len(pts)))) / 2
    log(f"unwrap {ob.name}: UV coverage {area * 100:.1f}% of the texture")


def blur(img, passes=3, r=3):
    """Separable box blur (x3 ~ gaussian) for smooth, noisy bakes like floors."""
    for _ in range(passes):
        for ax in (0, 1):
            c = np.cumsum(np.pad(img, [(r + 1, r) if a == ax else (0, 0) for a in range(3)], mode="edge"), axis=ax)
            img = (np.take(c, range(2 * r + 1, c.shape[ax]), axis=ax) - np.take(c, range(0, c.shape[ax] - 2 * r - 1), axis=ax)) / (2 * r + 1)
    return img


def bake(ob, name, size, exposure, samples=BAKE_SAMPLES, margin=8, smooth=0):
    exposure *= NIGHT
    if FAST:
        size, samples, margin, smooth = max(128, size // 8), 4, max(1, margin // 4), min(smooth, 1)
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=True)
    for m in ob.data.materials:
        nt = m.node_tree
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = img
        for n in nt.nodes:
            n.select = False
        tx.select = True
        nt.nodes.active = tx
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    scene.cycles.samples = samples
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT", "COLOR"}, margin=margin, use_clear=True)
    px = np.empty(size * size * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    lin = px.reshape(size, size, 4)[::-1, :, :3]                       # Blender rows are bottom-up
    if smooth:
        lin = blur(lin, r=smooth)
    path = os.path.join(OUT, name + ".png")
    write_png(path, tonemap(lin, exposure))
    log(f"baked {ob.name} -> {name}.png (mean linear {lin.mean():.3f})")
    return path


def export_fbx(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, ob.name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"}, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",
                             mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False)
    log(f"fbx {os.path.basename(path)}: {len(ob.data.polygons)} faces")


def render_preview(name, cam_pos, target, lens=24):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_end = 2000
    cam = bpy.data.objects.new(name, cd)
    cam.location = cam_pos
    cam.rotation_euler = (Vector(target) - Vector(cam_pos)).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(cam)
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.cycles.samples = 24
    scene.render.filepath = os.path.join(OUT, f"preview_{name}.png")
    bpy.ops.render.render(write_still=True)
    log("preview " + scene.render.filepath)


# ---------------------------------------------------------------- main
def join(dst, others):
    bpy.ops.object.select_all(action="DESELECT")
    for o in others:
        o.select_set(True)
    dst.select_set(True)
    bpy.context.view_layer.objects.active = dst
    bpy.ops.object.join()
    return dst


def load_grounds():
    """Build each grounds module with the preview's seed: {name: (module, result dict)} (contract: grounds/kit.py)."""
    out = {}
    for name in GROUND_MODULES:
        if not os.path.exists(os.path.join(HERE, "grounds", name + ".py")):
            log(f"grounds: {name}.py not there, skipped")
            continue
        mod = importlib.import_module(name)
        if CROWD2 and hasattr(mod, "TOTEMS"):                         # crowd v2 carries its own totems
            mod.TOTEMS = False
        res = mod.build(random.Random(GROUND_SEED))
        out[name] = (mod, res)
        log(f"grounds {name}: lit {sum(gkit.tris(b) for b, _ in res.get('lit', []))} tris, "
            f"glow {sum(gkit.tris(b) for b in res.get('glow', []))} tris, beams {sum(len(b.faces) for b in res.get('beams', []))}"
            f" quads, halos {sum(len(b.faces) for b in res.get('halos', []))} quads, lights {len(res.get('lights', []))}, "
            f"exclude {len(res.get('exclude', []))}, people {len(res.get('people', []))}")
    return out


def bm_merge(dst, src):
    """Append bmesh src into dst keeping the UVMap layer (palette / beam / halo UVs)."""
    lay_d = dst.loops.layers.uv.get("UVMap") or dst.loops.layers.uv.new("UVMap")
    lay_s = src.loops.layers.uv.get("UVMap")
    vmap = {v: dst.verts.new(v.co) for v in src.verts}
    for f in src.faces:
        try:
            nf = dst.faces.new([vmap[v] for v in f.verts])
        except ValueError:
            continue
        if lay_s is not None:
            for ld, ls in zip(nf.loops, f.loops):
                ld[lay_d].uv = ls[lay_s].uv
    src.free()


LASER_LAYERS = ("UVMap", "LaserPivot", "LaserPivotZPhase", "LaserAmp", "LaserCue", "LaserFix")   # grounds/atmosphere.py
                                                                                                  # "lasers" contract (v9)


def bm_merge_layers(dst, src, names, zdrop=0.0):
    """Append src into dst keeping every named UV layer, in this order (FBX -> UE UV channels 0..n). zdrop: subtract
    from LaserPivotZPhase.x so the pivots follow the stage drop."""
    lays_d = [dst.loops.layers.uv.get(n) or dst.loops.layers.uv.new(n) for n in names]
    lays_s = [src.loops.layers.uv.get(n) for n in names]
    vmap = {v: dst.verts.new(v.co) for v in src.verts}
    for f in src.faces:
        try:
            nf = dst.faces.new([vmap[v] for v in f.verts])
        except ValueError:
            continue
        for ld, ls in zip(nf.loops, f.loops):
            for n, lay_d, lay_s in zip(names, lays_d, lays_s):
                if lay_s is None:
                    continue
                uv = ls[lay_s].uv.copy()
                if n == "LaserPivotZPhase":
                    uv.x -= zdrop
                ld[lay_d].uv = uv
    src.free()


_LIT_MATS = {}


def lit_material(key):
    if key not in _LIT_MATS:
        rgb, rough = gkit.LIT[key]
        _LIT_MATS[key] = mat_flat("G_" + key, rgb, rough)
    return _LIT_MATS[key]


def mat_alpha(name, image):
    """Preview of Tribe's alpha-blended unlit material: texture rgb over the background by texture alpha."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = image
    image.alpha_mode = "STRAIGHT"
    em = nt.nodes.new("ShaderNodeEmission")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tx.outputs["Color"], em.inputs["Color"])
    nt.links.new(tx.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], outn.inputs["Surface"])
    return m


grounds = load_grounds()
_atm_mod = grounds["atmosphere"][0] if "atmosphere" in grounds else None
stage_aims, stage_colors = getattr(_atm_mod, "STAGE_AIMS", None), getattr(_atm_mod, "STAGE_COLORS", None)
stage_moves = getattr(_atm_mod, "STAGE_MOVES", None)                   # v13: the moving heads move
structure, bulbs, eyes = build_structure()
deck = build_deck()
rig, lenses, heads = build_rig(stage_aims, stage_colors, stage_moves)
riser, booth, glow = build_riser()
pillars = build_pillars()
screen = build_screen()
vscreen = build_visual_screen()
ground, far = build_ground()
sky = build_sky()
_excl = [r for _, res in grounds.values() for r in res.get("exclude", [])]
_extra = [q for _, res in grounds.values() for q in res.get("people", [])]
if CROWD2:
    crowd, phones, _ = crowd2.build_crowd2(random.Random(11), exclude=_excl, extra=_extra)
    flags = None                                                       # flags/totems are in the crowd mesh now
else:
    crowd, phones, flags = build_crowd(exclude=_excl, extra=_extra)
decor_bm = bmesh.new()
plants = build_decor(decor_bm)
join(structure, [new_obj("Decor", decor_bm)])
# the stage drop: everything modeled on z=0 goes down; the riser/booth/glow (Tribe's floor) and the sky stay
for ob in [o for o in (structure, bulbs, eyes, deck, rig, lenses, heads, pillars, plants, screen, vscreen, ground, far,
                       crowd, phones, flags) if o is not None]:
    ob.data.transform(Matrix.Translation((0, 0, -STAGE_DROP)))
# festival grounds: one baked mesh per module (SM_DinoGrounds<Name>), one shared glow mesh on the palette texture, and
# the translucent beams/halos (kept out of the bakes: hide_render until the bakes are done)
grounds_lit, glow_bm, halo_bms, beam_bms, lasers_bm = [], bmesh.new(), [], [], bmesh.new()
movers_bm, mhalos_bm = bmesh.new(), bmesh.new()                       # v13: the moving heads' beams and lens glows
for gname, (gmod, gres) in grounds.items():
    parts = []
    for k, (gbm, key) in enumerate(gres.get("lit", [])):
        gob = new_obj(f"G_{gname}_{k}", gbm)
        assign(gob, lit_material(key))
        parts.append(gob)
    if parts:
        gob = join(parts[0], parts[1:]) if len(parts) > 1 else parts[0]
        gob.name = "SM_DinoGrounds" + gname.capitalize()
        gob.data.name = gob.name
        grounds_lit.append((gob, getattr(gmod, "BAKE_SIZE", 2048)))
    for gbm in gres.get("glow", []):
        bm_merge(glow_bm, gbm)
    beam_bms += [(gname, i, b) for i, b in enumerate(gres.get("beams", []))]
    for gbm in gres.get("lasers", []):                                  # sweeping lasers: pivot data in UV1-3
        bm_merge_layers(lasers_bm, gbm, LASER_LAYERS, zdrop=STAGE_DROP)
    for gbm in gres.get("movers", []):                                  # v13: moving heads, same data layers
        bm_merge_layers(movers_bm, gbm, LASER_LAYERS, zdrop=STAGE_DROP)
    for gbm in gres.get("mover_halos", []):
        bm_merge_layers(mhalos_bm, gbm, LASER_LAYERS, zdrop=STAGE_DROP)
    if gres.get("halos"):
        hb = bmesh.new()
        for gbm in gres["halos"]:
            bm_merge(hb, gbm)
        halo_bms.append((gname, hb))
grounds_extra = []                                                     # glow / beams / halos objects (exported too)
for gname, gbm in [("SM_DinoGroundsGlow", glow_bm), ("SM_DinoLasers", lasers_bm), ("SM_DinoMoverBeams", movers_bm),
                   ("SM_DinoMoverHalos", mhalos_bm)] + \
        [("SM_DinoHalos" + m.capitalize(), b) for m, b in halo_bms] +         [(f"SM_DinoBeams{k}", b) for k, (_, _, b) in enumerate(beam_bms)]:
    if len(gbm.faces):
        grounds_extra.append(new_obj(gname, gbm))
    else:
        gbm.free()
for gob in [o for o, _ in grounds_lit] + grounds_extra:
    gob.data.transform(Matrix.Translation((0, 0, -STAGE_DROP)))
gglow = bpy.data.objects.get("SM_DinoGroundsGlow")
with open(os.path.join(OUT, "show_groups.json"), "w") as jf:            # build_dino: mesh -> module beam group (cue rows)
    json.dump({**{f"SM_DinoBeams{k}": f"{m}:{i}" for k, (m, i, _) in enumerate(beam_bms)},
               **{"SM_DinoHalos" + m.capitalize(): m for m, _ in halo_bms}}, jf, indent=1)
gtrans = [o for o in grounds_extra if o.name.startswith(("SM_DinoBeams", "SM_DinoHalos", "SM_DinoLasers",
                                                         "SM_DinoMoverBeams", "SM_DinoMoverHalos"))]   # alpha-blended
for gob in gtrans:
    gob.hide_render = True
set_smooth(structure, True)
if not CROWD2:
    set_smooth(crowd, False)                                           # v2: smooth (flat would triple UE's VAT vertices)
for ob in (structure, bulbs, eyes, deck, crowd, phones, rig, lenses, *([heads] if heads else []), booth, riser, glow,
           pillars, plants, *[o for o, _ in grounds_lit], *grounds_extra):
    log(f"{ob.name}: {len(ob.data.polygons)} faces, {sum(len(p.vertices) - 2 for p in ob.data.polygons)} tris")

write_png(os.path.join(OUT, "T_DinoSky.png"), tex_sky())
write_png(os.path.join(OUT, "T_DinoMoon.png"), tex_moon())
write_png(os.path.join(OUT, "T_DinoLens.png"), tex_lens())
write_png(os.path.join(OUT, "T_DinoBooth.png"), tex_booth())
write_png(os.path.join(OUT, "T_DinoFlags.png"), tex_flags())
gkit.write_png(os.path.join(OUT, "T_DinoGroundsPal.png"), gkit.tex_palette())
write_show(OUT)                                                       # T_DinoCues, T_DinoLaserProg, T_DinoLaserLib
_atm = grounds["atmosphere"][0] if "atmosphere" in grounds else None
gkit.write_png(os.path.join(OUT, "T_DinoBeam.png"), (getattr(_atm, "tex_beam", None) or gkit.tex_beam)())
gkit.write_png(os.path.join(OUT, "T_DinoHalo.png"), (getattr(_atm, "tex_halo", None) or gkit.tex_halo)())

# bake setup: real light emitters + lit surfaces
assign(structure, mat_bone())
assign(deck, mat_flat("Deck", (0.025, 0.025, 0.03), 0.5))
assign(ground, mat_flat("Ground", (0.045, 0.045, 0.05)))
assign(far, mat_flat("Far", (0.01, 0.01, 0.012)))
assign(crowd, mat_crowd())
if flags is not None:
    assign(flags, mat_emit("FlagEmit", image=load_png(os.path.join(OUT, "T_DinoFlags.png")), strength=1.0))
assign(riser, mat_metal())
assign(plants, mat_plant())
assign(glow, mat_emit("GlowEmit", (0.2, 0.9, 1.0), 6.0))
assign(pillars, mat_emit("PillarEmit", (0.2, 0.9, 1.0), 6.0))
assign(screen, mat_emit("MoonEmit", image=load_png(os.path.join(OUT, "T_DinoMoon.png")), strength=4.0))
assign(vscreen, mat_emit("VisualScreen", (0.55, 0.3, 0.22), 1.5))   # stands in for the visuals' glow in the bakes
assign(bulbs, mat_emit("BulbEmit", (1.0, 0.75, 0.4), 6.0))
if CROWD2:                                                             # phones, glowsticks, LED frames: own colors
    assign(phones, mat_emit_col("PhoneEmit", 4.0))
else:
    assign(phones, mat_emit("PhoneEmit", (0.85, 0.9, 1.0), 4.0))
assign(eyes, mat_emit("EyeEmit", (1.0, 0.06, 0.02), 6.0))
assign(rig, mat_metal())
assign(lenses, mat_emit("LensEmit", image=load_png(os.path.join(OUT, "T_DinoLens.png")), strength=8.0))
assign(booth, mat_emit("BoothEmit", image=load_png(os.path.join(OUT, "T_DinoBooth.png")), strength=3.0))
assign(sky, mat_emit("SkyEmit", image=load_png(os.path.join(OUT, "T_DinoSky.png")), strength=1.0))
if gglow:                                                               # the palette glows light their surroundings
    assign(gglow, mat_emit("GroundsGlowEmit", image=load_png(os.path.join(OUT, "T_DinoGroundsPal.png")), strength=5.0))
if heads is not None:                                                   # v13: unlit in UE, dark metal in the bakes
    assign(heads, lit_material("metal_dark"))
for gob in gtrans:
    tex = "T_DinoHalo" if gob.name.startswith(("SM_DinoHalos", "SM_DinoMoverHalos")) else "T_DinoBeam"
    assign(gob, mat_alpha("A" + gob.name, load_png(os.path.join(OUT, tex + ".png"))))
stage_lights()
for _, gres in grounds.values():
    for spec in gres.get("lights", []):
        gkit.add_light(spec, coll)
for lt in [o for o in coll.objects if o.type == "LIGHT"]:              # the lights were placed for z=0: drop them too
    lt.location.z -= STAGE_DROP

if "--preview-only" not in ARGS:
    unwrap(structure, 0.002)
    unwrap(deck, 0.01)
    unwrap(rig, 0.002)
    unwrap(riser, 0.004)
    unwrap(plants, 0.003)
    pass                                                               # crowd: UV cells built in build_crowd()
    bake_struct = bake(structure, "T_DinoStructure", 4096, exposure=1.6, samples=96)
    bake_rig = bake(rig, "T_DinoRig", 2048, exposure=1.8, samples=96)
    bake_riser = bake(riser, "T_DinoRiser", 1024, exposure=1.8, samples=160, smooth=2)
    bake_plants = bake(plants, "T_DinoPlants", 1024, exposure=2.5, samples=96)
    bake_deck = bake(deck, "T_DinoDeck", 1024, exposure=1.3, samples=256, smooth=3)
    bake_ground = bake(ground, "T_DinoGround", 4096, exposure=2.2, samples=128, smooth=4)   # the grid's own 0-1 UVs
    bake_crowd = bake(crowd, "T_DinoCrowd", 4096 if CROWD2 else 2048, exposure=0.55 if CROWD2 else 0.9, samples=128,
                      margin=2)
    bake_grounds = []
    for gob, gsize in grounds_lit:
        unwrap(gob, 0.002)
        bake_grounds.append((gob, bake(gob, "T_" + gob.name[3:], gsize, exposure=1.8, samples=64)))
    # preview exactly what the Quest will show: every surface unlit (its texture or flat color as-is)
    for lt in [o for o in coll.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(lt)
    assign(structure, mat_emit("PStruct", image=load_png(bake_struct)))
    assign(deck, mat_emit("PDeck", image=load_png(bake_deck)))
    assign(rig, mat_emit("PRig", image=load_png(bake_rig)))
    assign(riser, mat_emit("PRiser", image=load_png(bake_riser)))
    assign(plants, mat_emit("PPlants", image=load_png(bake_plants)))
    assign(ground, mat_emit("PGround", image=load_png(bake_ground)))
    assign(crowd, mat_emit("PCrowd", image=load_png(bake_crowd)))
    assign(far, mat_emit("PFar", (0.004, 0.004, 0.006)))
    for gob, gpath in bake_grounds:
        assign(gob, mat_emit("P" + gob.name, image=load_png(gpath)))
    for ob in (screen, sky, bulbs, phones, eyes, lenses, booth, glow, pillars, *([gglow] if gglow else [])):
        ob.data.materials[0].node_tree.nodes["Emission"].inputs["Strength"].default_value = 1.0
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    for gob in gtrans:
        gob.hide_render = False
    for ob in [o for o in (structure, bulbs, eyes, deck, screen, vscreen, ground, far, sky, crowd, phones, rig, lenses,
                           heads, booth, riser, glow, pillars, plants, flags, *[o for o, _ in grounds_lit],
                           *grounds_extra)
               if o is not None]:
        export_fbx(ob)
    with open(os.path.join(OUT, "manifest.txt"), "w") as mf:              # build_dino.py imports exactly these
        names = [ob.name for ob in (structure, bulbs, eyes, deck, screen, vscreen, ground, far, sky, crowd, phones, rig,
                 lenses, heads, booth, riser, glow, pillars, plants, flags, *[o for o, _ in grounds_lit],
                 *grounds_extra)
                 if ob is not None]
        mf.write("\n".join(names) + "\n")

for gob in gtrans:                                                     # previews show the beams/halos
    gob.hide_render = False
if CROWD2:
    crowd2.pose_preview([crowd, phones], 0.31)                         # mid-dance (after the export: rest pose ships)
render_preview("crowd", (0, -48, 4.0), (0, 8, 10.5))
render_preview("dj_front", (0, 0.9, 1.7), (0, -40, -1.0), lens=18)
render_preview("dj_back", (0, -1.0, 1.7), (0, 10, 13), lens=16)
render_preview("stream", (0, -9, 3.5), (0, 6, 9), lens=16)
render_preview("dj_left", (0, -0.3, 1.65), (-45, -30, -1.0), lens=16)
render_preview("dj_right", (0, -0.3, 1.65), (45, -30, -1.0), lens=16)
render_preview("back", (0, -95, 12), (0, 0, 6), lens=24)
render_preview("aerial", (0, 25, 40), (0, -50, -2.5), lens=20)
log("done")
