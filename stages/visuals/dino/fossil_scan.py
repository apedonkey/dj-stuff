"""FOSSIL SCAN - Dino Stage VJ loop (intro). 8 bars, seamless, tempo from vjkit (--bpm).

The stage's own roaring T. rex skull (TribeXR/Scripts/Blender/skull.py, skull v2) as a laser-scanned hologram: glowing
contour slices on black bone, turning slowly between two views. Once per bar a scan plane sweeps down through it; the
slices it crosses flare in the scan color and cool back. The eyes swell on toward bar 5's downbeat and fade out over
bar 8. Each kick lifts the slices slightly; a dim radar backdrop rings out once per bar.
Variants: cyan (three-quarter view from below), amber (profile, dense slices), uv (head-on, slices + meridians).

  blender.exe -b --factory-startup --python fossil_scan.py -- --variant cyan --frames 0,113,225 [--pct 50]
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
from vjkit import AMBER, CYAN, GREEN, MAGENTA, ORANGE, RED, UV  # noqa: E402

STAGE_BLENDER = r"C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender"
sys.dont_write_bytecode = True                   # read-only use of the stage scripts: no __pycache__ under TribeXR
sys.path.insert(0, STAGE_BLENDER)
import skull as stage_skull  # noqa: E402

# slices (m apart), meridians (m apart, 0 = none); camera as (azimuth deg, elevation deg, distance m, lens mm) aimed at
# the skull's middle + aim (m up); the skull turns as base yaw +- swing (deg) over the loop. The distances keep the
# turning skull inside the Dino Stage's arch window (frame rows ~200-880; check with --arch Skull,Eyes): closer, its
# crest and jaw left the screen
VARIANTS = {
    "cyan": dict(line=CYAN, scan=AMBER, back=UV, slice=0.13, meridian=0.0, cam=(-38, -8, 19.0, 40), aim=0.2,
                 yaw=(0, 28)),
    "amber": dict(line=ORANGE, scan=CYAN, back=RED, slice=0.085, meridian=0.0, cam=(-90, 4, 17.8, 40), aim=0.0,
                  yaw=(0, 22)),
    "uv": dict(line=UV, scan=GREEN, back=CYAN, slice=0.16, meridian=0.32, cam=(0, 6, 19.0, 40), aim=-0.3,
               yaw=(0, 34)),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))
LENGTH = 6.5                                     # the skull is scaled to this length (m), snout to neck


def clean_bm(bm, name):
    """bmesh -> mesh object (the stage generator's bmeshes)."""
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def build_skull():
    """The stage skull, centered on its bounding box and scaled to LENGTH, under a pivot empty that turns it."""
    skull_bm, eyes_bm = stage_skull.build_skull_v2()
    pts = [v.co.copy() for v in skull_bm.verts]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c, size = (lo + hi) / 2, hi - lo
    M = Matrix.Scale(LENGTH / max(size.x, size.y), 4) @ Matrix.Translation(-c)
    for bm in (skull_bm, eyes_bm):
        bm.transform(M)
    pivot = vj.new_empty("Pivot")
    bone = clean_bm(skull_bm, "Skull")
    eyes = clean_bm(eyes_bm, "Eyes")
    bone.parent = eyes.parent = pivot
    return pivot, bone, eyes, (size.z * LENGTH / max(size.x, size.y)) / 2


# ------------------------------------------------------------------ materials
def lines(s, v, spacing, half_w):
    t = s.math("FRACT", s.madd(v, 1.0 / spacing, 0.5))
    dist = s.mul(s.math("ABSOLUTE", s.math("SUBTRACT", t, 0.5)), spacing)
    return s.math("SUBTRACT", 1.0, s.smooth(dist, half_w, half_w * 2.2))


def bone_mat():
    s = vj.Shader("Bone")
    geo = s.node("ShaderNodeNewGeometry")
    _, _, z = s.xyz(geo.outputs["Position"])
    g = lines(s, z, V["slice"], V["slice"] * 0.055)
    if V["meridian"]:
        tc = s.node("ShaderNodeTexCoord")
        lx, _, _ = s.xyz(tc.outputs["Object"])                    # meridians ride with the skull as it turns
        g = s.math("MAXIMUM", g, s.mul(lines(s, lx, V["meridian"], V["meridian"] * 0.05), 0.8))
    lw = s.node("ShaderNodeLayerWeight")
    face = s.smooth(s.math("SUBTRACT", 1.0, lw.outputs["Facing"]), 0.04, 0.35)   # slices bunch up at the rim
    dz = s.math("SUBTRACT", z, s.c("ScanZ"))
    band = s.gauss(z, s.c("ScanZ"), 0.05)                           # the scan plane's cut through the bone
    above = s.math("GREATER_THAN", dz, 0.0)
    trail = s.mul(s.exp(s.mul(dz, -1.0 / 0.45)), above)             # scanned slices cool back over ~0.45 m
    heat = s.mul(s.math("MAXIMUM", band, s.mul(trail, 0.7)), s.c("ScanAmt"))
    col = s.mix(s.smooth(heat, 0.3, 0.7), V["line"], V["scan"])    # a short switch: a blend of opposite hues is grey
    lift = s.add(0.8, s.mul(s.c("Kick"), 0.3), s.mul(heat, 0.5))
    strength = s.add(s.mul(g, face, lift), s.mul(band, s.c("ScanAmt"), 0.7))
    return s.emit(col, s.mul(strength, 1.6 * GAIN))


def eye_mat():
    s = vj.Shader("Eyes")
    return s.emit(RED, s.mul(s.c("Eye"), 5.0 * GAIN))


def backdrop_mat(radius):
    """A dim polar grid behind the skull; a ring sweeps out from the center once per bar."""
    s = vj.Shader("Radar")
    tc = s.node("ShaderNodeTexCoord")
    x, _, z = s.xyz(tc.outputs["Object"])
    r = s.math("SQRT", s.add(s.mul(x, x), s.mul(z, z)))
    rings = lines(s, r, 2.0, 0.025)
    ang = s.mul(s.math("ARCTAN2", z, x), 12 / math.pi)              # 24 spokes
    spokes = s.mul(lines(s, ang, 1.0, 0.012), s.smooth(r, 2.5, 6.0))
    sweep = s.gauss(r, s.mul(s.c("BarPhase"), radius), 0.11)
    fade = s.math("SUBTRACT", 1.0, s.smooth(r, radius * 0.4, radius * 0.9))
    g = s.add(s.mul(s.math("MAXIMUM", rings, spokes), 0.18), s.mul(sweep, s.c("SweepAmt")))
    return s.emit(V["back"], s.mul(g, fade, 0.9 * GAIN, s.add(1.0, s.mul(s.c("Kick"), 0.25))))


def scanline_mat():
    s = vj.Shader("ScanLine")
    return s.additive(V["scan"], s.mul(s.c("ScanAmt"), 0.6 * GAIN))


# ------------------------------------------------------------------ timing
def signals(f, z_top, z_bot):
    c = vj.clock(f)
    bar = c["bar"]
    b0, b1 = vj.BEAT_F[4 * bar], vj.BEAT_F[4 * bar + 4]
    u = (c["f"] - b0) / (b1 - b0)                                   # 0 -> 1 through the bar
    amt = vj.ease(u / 0.06) * (1.0 - vj.ease((u - 0.82) / 0.18))    # the scan fades in at the top, out at the bottom
    eye = 0.0                                                       # swell into bar 5, hold, fade out over bar 8
    if bar == 3 and c["beat"] >= 2:
        eye = ((c["f"] - vj.BEAT_F[14]) / (vj.BEAT_F[16] - vj.BEAT_F[14])) ** 2
    elif 4 <= bar <= 6:
        eye = 1.0 - 0.3 * vj.ease((c["f"] - vj.BEAT_F[16]) / vj.FPB)
    elif bar == 7:
        eye = 0.7 * (1.0 - vj.ease(u))
    return {"Kick": c["kick"], "ScanZ": z_top - u * (z_top - z_bot), "ScanAmt": amt, "Eye": eye,
            "BarPhase": u, "SweepAmt": 0.25 * (1.0 - vj.ease(u))}


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    pivot, bone, eyes, half_h = build_skull()
    z_top, z_bot = half_h + 0.4, -half_h - 0.4
    frames = list(range(vj.FRAMES + 1))
    sig = [signals(f, z_top, z_bot) for f in frames]
    vj.build_clock({k: [s[k] for s in sig] for k in sig[0]})
    bone.data.materials.append(bone_mat())
    eyes.data.materials.append(eye_mat())

    az, el, dist, lens = V["cam"]
    eye_dir = Vector((math.sin(math.radians(az)) * math.cos(math.radians(el)),
                      -math.cos(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))))
    cam_pos = eye_dir * dist
    facing = (-eye_dir).to_track_quat("-Y", "Z").to_euler()          # local -Y toward the camera
    rad = 15.0                                                       # backdrop: a disc behind the skull
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(p) for p in reversed(vj.circle_pts(Vector((0, 0, 0)), rad, 96))])
    disc = vj.new_obj("Radar", bm, backdrop_mat(rad))
    disc.location, disc.rotation_euler = -eye_dir * 7.0, facing
    bm = bmesh.new()                                                 # the scan line: a thin bar across the frame,
    w, t = 40.0, 0.018                                               # behind the skull, riding the scan height
    bm.faces.new([bm.verts.new(p) for p in ((-w, 0, -t), (w, 0, -t), (w, 0, t), (-w, 0, t))])
    line = vj.new_obj("ScanLine", bm, scanline_mat())
    line.rotation_euler = facing
    vj.animate(line, "location", [(f, tuple(-eye_dir * 3.0 + Vector((0, 0, sig[f]["ScanZ"]))))
                                  for f in frames], interp="LINEAR")

    yaw0, swing = V["yaw"]
    vj.animate(pivot, "rotation_euler",
               [(f, (0.0, 0.0, math.radians(yaw0 + swing * math.sin(2 * math.pi * f / vj.FRAMES))))
                for f in range(-2, vj.FRAMES + 3)], interp="LINEAR")

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens, cam_data.sensor_width, cam_data.sensor_fit = lens, 36.0, "HORIZONTAL"
    cam_data.clip_start, cam_data.clip_end = 0.1, 200.0
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = cam_pos
    cam.rotation_euler = (Vector((0, 0, V["aim"])) - cam_pos).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    return scene


scene = build()
vj.setup_render(scene, samples=int(vj.arg("--samples", 16)), pct=int(vj.arg("--pct", 100)),
                bloom=tuple(float(x) for x in vj.arg("--bloom", "1.0,0.6,0.4").split(",")), mblur=vj.flag("--mblur"))
vj.finish(scene, f"fossil_scan_{VNAME}")
