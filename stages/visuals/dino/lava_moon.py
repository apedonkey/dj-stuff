"""LAVA MOON - Dino Stage VJ loop (outro / breakdown). 8 bars, seamless, tempo from vjkit (--bpm).

The Dino Stage itself in silhouette (its two spine arches with their big horns and the roaring skull on top) against a
huge lava moon: churning cracks, a 48-bulb ring chasing on the beat, uplight beams swinging once per 2 bars behind the
arch, faint stars. The camera drifts in and back over the loop. The moon and the beams swell softly into bars 1 and 5.
Variants: amber (the classic lava moon), blood (a crimson moon, magenta beams, from lower down), eclipse (a dark moon
with a corona, UV beams, a wider view with more sky).
Our own design: the spines and horns follow TribeXR/Scripts/Blender/dino_stage.py (spine_point, the horn layout), the
skull is skull v2 from TribeXR/Scripts/Blender/skull.py (imported read-only).

  blender.exe -b --factory-startup --python lava_moon.py -- --variant amber --frames 0,113,225 [--pct 50]
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
from vjkit import AMBER, CYAN, MAGENTA, ORANGE, RED, UV  # noqa: E402

STAGE_BLENDER = r"C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender"
sys.dont_write_bytecode = True                   # read-only use of the stage scripts: no __pycache__ under TribeXR
sys.path.insert(0, STAGE_BLENDER)
import skull as stage_skull  # noqa: E402

# lava ramp (heat -> color), the moon's brightness, rim and bulb colors, beam color, corona (0 = none);
# camera as (position, look-at, lens mm): wide enough that the whole moon and its bulb ring sit inside the Dino Stage's
# arch window (frame rows ~200-880; check with --arch Moon); at 38-42 mm its top ran off the screen
LAVA = [(0.0, (0.02, 0.0, 0.0)), (0.3, (0.28, 0.01, 0.0)), (0.6, (1.0, 0.15, 0.0)), (0.85, (1.0, 0.4, 0.03)),
        (1.0, (1.0, 0.72, 0.3))]
BLOOD = [(0.0, (0.015, 0.0, 0.005)), (0.35, (0.22, 0.0, 0.02)), (0.65, (0.9, 0.02, 0.06)), (0.9, (1.0, 0.1, 0.25)),
         (1.0, (1.0, 0.45, 0.55))]
ECLIPSE = [(0.0, (0.0, 0.0, 0.0)), (0.5, (0.04, 0.0, 0.03)), (0.8, (0.25, 0.02, 0.12)), (1.0, (0.6, 0.1, 0.4))]
VARIANTS = {
    "amber": dict(lava=LAVA, moon=1.0, rim=AMBER, bulb=(1.0, 0.55, 0.2), beam=AMBER, corona=0.0,
                  cam=((0, -60, 5.0), (0, 8, 16.0), 28)),
    "blood": dict(lava=BLOOD, moon=1.1, rim=RED, bulb=(1.0, 0.1, 0.3), beam=MAGENTA, corona=0.0,
                  cam=((-16, -52, 2.0), (0, 250, 60.0), 29)),       # from low left, aimed at the moon's center
    "eclipse": dict(lava=ECLIPSE, moon=1.0, rim=UV, bulb=(0.2, 0.7, 1.0), beam=UV, corona=1.0,
                    cam=((0, -56, 8.0), (0, 8, 18.0), 27)),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))
MOON_C, MOON_R = Vector((0.0, 250.0, 60.0)), 57.0          # high and huge: the stage's silhouette cuts across it
BEAM_LEN = 60.0


# ------------------------------------------------------------------ the stage in silhouette (dino_stage.py's shapes)
def spine_point(side, t):
    """Backbone of one wing: from the front corner of the stage up and back to just below the skull."""
    x = side * (23.0 * (1 - t) ** 1.15 + 2.2 * t)
    y = -3.5 + 12.5 * t ** 1.6
    z = 0.6 + 16.5 * math.sin(t * math.pi / 2) ** 1.25
    return Vector((x, y, z))


def stage_silhouette():
    bm = bmesh.new()
    for side in (-1, 1):
        vj.tube(bm, [spine_point(side, i / 70) for i in range(71)],
                lambda u: (1.25 - 0.5 * u) * (1 + 0.38 * max(0.0, math.sin(u * 26 * math.pi)) ** 4), segs=16)
        out = Vector((side, 0, 0))
        for k in range(7):                                             # big horns, growing toward the skull
            t = 0.10 + 0.78 * k / 6
            p = spine_point(side, t)
            tang = (spine_point(side, t + 0.01) - p).normalized()
            d = (Vector((0, 0, 1)) + out * (0.55 - 0.35 * t) + Vector((0, -0.18, 0))).normalized()
            vj.horn(bm, p, d, 6.0 + 9.0 * t, 1.15 + 0.9 * t, tang.cross(d) * -side, 28 + 20 * t, segs=12, steps=20)
        for k in range(14):                                            # small back spikes between the horns
            t = 0.05 + 0.88 * k / 13
            p = spine_point(side, t)
            vj.horn(bm, p, (Vector((0, 0.35, 1)) + out * 0.25).normalized(), 1.6 + 1.6 * t, 0.42,
                    Vector((1, 0, 0)), 18, segs=8, steps=8)
    skull_bm, eyes_bm = stage_skull.build_skull_v2()
    eyes_bm.free()
    tmp = bpy.data.meshes.new("tmp")
    skull_bm.to_mesh(tmp)
    skull_bm.free()
    bm.from_mesh(tmp)
    bpy.data.meshes.remove(tmp)
    return bm


# ------------------------------------------------------------------ materials
def black_mat():
    m = bpy.data.materials.new("Silhouette")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Strength"].default_value = 0.0
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    return m


def moon_coords(s):
    tc = s.node("ShaderNodeTexCoord")
    x, _, z = s.xyz(tc.outputs["Object"])
    qx, qz = s.mul(x, 1.0 / MOON_R), s.mul(z, 1.0 / MOON_R)
    return qx, qz, s.math("SQRT", s.add(s.mul(qx, qx), s.mul(qz, qz)))


def moon_mat():
    """Lava: dark crust plates with glowing cracks, churning on a circle in noise space (seamless)."""
    s = vj.Shader("LavaMoon")
    qx, qz, r = moon_coords(s)
    cz, cw = s.mul(s.c("LoopCos"), 0.5), s.mul(s.c("LoopSin"), 0.5)
    noise = s.node("ShaderNodeTexNoise", noise_dimensions="4D")
    s.put(noise.inputs["Vector"], s.vec(s.mul(qx, 2.2), s.mul(qz, 2.2), cz))
    s.put(noise.inputs["W"], cw)
    noise.inputs["Scale"].default_value = 1.6
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.55
    noise.inputs["Distortion"].default_value = 0.6
    n = noise.outputs["Fac"]
    warp = s.mul(s.math("SUBTRACT", n, 0.5), 0.9)
    vor = s.node("ShaderNodeTexVoronoi", voronoi_dimensions="4D", feature="DISTANCE_TO_EDGE")
    s.put(vor.inputs["Vector"], s.vec(s.madd(qx, 4.0, warp), s.madd(qz, 4.0, warp), s.mul(cz, 1.4)))
    s.put(vor.inputs["W"], s.mul(cw, 1.4))
    crack = s.math("SUBTRACT", 1.0, s.smooth(vor.outputs["Distance"], 0.0, 0.055))
    heat = s.add(s.mul(crack, 0.8), s.mul(s.math("POWER", n, 3.0), 0.9))
    ramp = s.node("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    stops = V["lava"]
    els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1)
    els[1].position, els[1].color = stops[-1][0], (*stops[-1][1], 1)
    for p, c in stops[1:-1]:
        els.new(p).color = (*c, 1)
    s.put(ramp.inputs["Fac"], heat)
    limb = s.smooth(r, 0.75, 1.0)
    pulse = s.add(1.0, s.mul(s.c("Kick"), 0.12), s.mul(s.c("Swell"), 0.3))
    return s.emit(ramp.outputs["Color"], s.mul(s.madd(limb, 0.6, 0.5), pulse, 1.1 * V["moon"] * GAIN))


def corona_mat():
    """Eclipse: a thin bright ring hugging the moon's edge and a short soft falloff outside it."""
    s = vj.Shader("Corona")
    _, _, r = moon_coords(s)
    ring = s.gauss(r, 1.015, 0.012)
    halo = s.mul(s.exp(s.mul(s.math("MAXIMUM", s.math("SUBTRACT", r, 1.0), 0.0), -14.0)), 0.18)
    outside = s.math("GREATER_THAN", r, 0.99)
    lift = s.add(1.0, s.mul(s.c("Kick"), 0.15), s.mul(s.c("Swell"), 0.4))
    return s.additive(V["rim"], s.mul(s.add(ring, halo), outside, lift, 3.0 * GAIN))


def rim_mat():
    s = vj.Shader("MoonRim")
    return s.emit(V["rim"], s.mul(s.add(1.0, s.mul(s.c("Kick"), 0.3), s.mul(s.c("Swell"), 0.4)), 2.2 * GAIN,
                                  s.core()))


def bulb_mat():
    s = vj.Shader("MoonBulbs")
    tc = s.node("ShaderNodeTexCoord")
    x, _, z = s.xyz(tc.outputs["Object"])
    idx = s.mul(s.math("ARCTAN2", z, x), 48 / (2 * math.pi))
    chase = s.math("COSINE", s.mul(s.math("SUBTRACT", s.mul(idx, 0.25), s.c("BeatPos")), 2 * math.pi))
    lit = s.smooth(chase, 0.35, 0.95)                                 # every 4th bulb, 4 bulbs per beat
    level = s.add(0.15, lit, s.mul(s.c("Kick"), 0.2), s.mul(s.c("Swell"), 0.3))
    return s.emit(V["bulb"], s.mul(level, 3.2 * GAIN))


def beam_mat():
    """Uplight beams: additive, brightest at the lamp and fading up the beam and toward its edges."""
    s = vj.Shader("Beam")
    tc = s.node("ShaderNodeTexCoord")
    _, _, z = s.xyz(tc.outputs["Object"])                             # meters up the beam from the lamp
    along = s.exp(s.mul(z, -2.2 / BEAM_LEN))
    lw = s.node("ShaderNodeLayerWeight")
    edge = s.math("POWER", s.math("SUBTRACT", 1.0, lw.outputs["Facing"]), 2.0)
    lift = s.add(0.8, s.mul(s.c("Kick"), 0.15), s.mul(s.c("Swell"), 0.35))
    return s.additive(V["beam"], s.mul(along, edge, lift, 0.22 * GAIN))


def star_mat():
    """Faint stars twinkling slowly: a 4D noise of their position, walked round a circle over the loop (seamless)."""
    s = vj.Shader("Stars")
    geo = s.node("ShaderNodeNewGeometry")
    noise = s.node("ShaderNodeTexNoise", noise_dimensions="4D")
    x, y, z = s.xyz(geo.outputs["Position"])
    s.put(noise.inputs["Vector"], s.vec(s.add(s.mul(x, 0.02), s.c("LoopCos")), s.mul(y, 0.02), s.mul(z, 0.02)))
    s.put(noise.inputs["W"], s.c("LoopSin"))
    noise.inputs["Scale"].default_value = 3.0
    tw = s.smooth(noise.outputs["Fac"], 0.3, 0.7)
    return s.emit((0.75, 0.8, 1.0), s.mul(s.madd(tw, 0.7, 0.2), 0.7 * GAIN))


# ------------------------------------------------------------------ timing
def signals(f):
    c = vj.clock(f)
    swell = 0.0                                                       # into bars 1 and 5, peaking on the downbeat
    if c["bar"] in (3, 7) and c["beat"] >= 2:
        f0, f1 = vj.BEAT_F[4 * c["bar"] + 2], vj.BEAT_F[4 * c["bar"] + 4]
        swell = ((c["f"] - f0) / (f1 - f0)) ** 2
    elif c["bar"] in (0, 4):
        swell = math.exp(-(c["f"] - vj.BEAT_F[4 * c["bar"]]) / (2 * vj.FPB))
    return {"Kick": c["kick"], "Swell": swell, "BeatPos": c["beatpos"],
            "LoopCos": math.cos(2 * math.pi * c["loop"]), "LoopSin": math.sin(2 * math.pi * c["loop"])}


def beam_bm(length=BEAM_LEN, r0=0.35, r1=4.5, segs=16):
    bm = bmesh.new()
    vj.tube(bm, [Vector((0, 0, length * t)) for t in (0.0, 0.5, 1.0)], lambda u: r0 + (r1 - r0) * u, segs=segs)
    return bm


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    frames = list(range(vj.FRAMES + 1))
    sig = [signals(f) for f in frames]
    vj.build_clock({k: [s[k] for s in sig] for k in sig[0]})

    vj.new_obj("Stage", stage_silhouette(), black_mat())
    ground = bmesh.new()
    bmesh.ops.create_grid(ground, x_segments=1, y_segments=1, size=400.0)
    vj.new_obj("Ground", ground, black_mat())

    bm = bmesh.new()                                                  # discs and rings lie in the XZ plane, facing -Y
    bm.faces.new([bm.verts.new(p) for p in reversed(vj.circle_pts(Vector((0, 0, 0)), MOON_R, 160))])
    vj.new_obj("Moon", bm, moon_mat()).location = MOON_C
    if V["corona"]:
        bm = bmesh.new()
        bm.faces.new([bm.verts.new(p) for p in reversed(vj.circle_pts(Vector((0, 0, 0)), MOON_R * 1.5, 160))])
        vj.new_obj("Corona", bm, corona_mat()).location = MOON_C + Vector((0, -0.5, 0))
    rim = bmesh.new()
    vj.tube(rim, vj.circle_pts(Vector((0, 0, 0)), MOON_R * 1.03, 200), lambda u: 0.35, segs=8, closed=True)
    vj.new_obj("MoonRim", rim, rim_mat()).location = MOON_C + Vector((0, -1, 0))
    bulbs = bmesh.new()
    for p in vj.circle_pts(Vector((0, 0, 0)), MOON_R * 1.08, 48):
        bmesh.ops.create_icosphere(bulbs, subdivisions=2, radius=0.9, matrix=Matrix.Translation(p))
    vj.new_obj("MoonBulbs", bulbs, bulb_mat()).location = MOON_C + Vector((0, -1, 0))

    stars = bmesh.new()                                               # a fixed scatter of faint stars
    rnd = random.Random(11)
    for _ in range(260):
        a, e = rnd.uniform(-70, 70), rnd.uniform(4, 40)
        p = Vector((math.sin(math.radians(a)), math.cos(math.radians(a)), math.tan(math.radians(e)))) * 600
        if (Vector((p.x, 0, p.z)) - Vector((0, 0, MOON_C.z * 600 / MOON_C.y))).length < MOON_R * 600 / MOON_C.y * 1.2:
            continue
        bmesh.ops.create_icosphere(stars, subdivisions=1, radius=rnd.uniform(0.5, 1.1), matrix=Matrix.Translation(p))
    vj.new_obj("Stars", stars, star_mat())

    beam = beam_mat()                                                 # uplights behind the arch, swinging per 2 bars
    for i, x in enumerate((-15, -9, -3, 3, 9, 15)):
        ob = vj.new_obj(f"Beam{i}", beam_bm(), beam)
        ob.location = (x, 20.0, 0.0)
        ph = 0.5 * (i % 2)
        keys = []
        for f in range(-2, vj.FRAMES + 3):
            a = 2 * math.pi * (f / (vj.FRAMES / 4) + ph)              # 4 swings per loop = one per 2 bars
            keys.append((f, (math.radians(-12), math.radians(22 * math.sin(a) + 6 * (x / 15)), 0.0)))
        vj.animate(ob, "rotation_euler", keys, interp="LINEAR")

    (pos, look, lens) = V["cam"]
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens, cam_data.sensor_width, cam_data.sensor_fit = lens, 36.0, "HORIZONTAL"
    cam_data.clip_start, cam_data.clip_end = 0.5, 3000.0
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    keys_loc, keys_rot = [], []
    for f in range(-2, vj.FRAMES + 3):
        a = 2 * math.pi * f / vj.FRAMES
        p = Vector(pos) + Vector((1.2 * math.sin(a), 3.0 * (1 - math.cos(a)), 0.5 * math.sin(2 * a)))   # drift in/out
        keys_loc.append((f, tuple(p)))
        keys_rot.append((f, tuple((Vector(look) - p).to_track_quat("-Z", "Y").to_euler())))
    vj.animate(cam, "location", keys_loc, interp="LINEAR")
    vj.animate(cam, "rotation_euler", keys_rot, interp="LINEAR")
    return scene


scene = build()
vj.setup_render(scene, samples=int(vj.arg("--samples", 16)), pct=int(vj.arg("--pct", 100)),
                bloom=tuple(float(x) for x in vj.arg("--bloom", "1.0,0.6,0.4").split(",")), mblur=vj.flag("--mblur"))
vj.finish(scene, f"lava_moon_{VNAME}")
