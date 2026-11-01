"""DINO STAGE STING - Dino Stage VJ loop (act changes / station ID). 8 bars, seamless, tempo from vjkit (--bpm).

The words DINO / STAGE in our own stroke letterforms (no font), every stroke a neon bone with knobbed ends, flanked by
the stage's big horns. The bones fly in during the last two beats and snap together exactly on bar 1's downbeat (a
swell peak with a brief RGB split, no flicker), hold through bar 6 with a soft pulse per beat and a highlight sweeping
across once per bar, then drift apart over bars 7-8 and fly back for the next downbeat (the loop's seam).
Variants: amber (amber bones, cyan horns, head-on), cyan (cyan bones, magenta horns, from below left),
uv (UV bones, magenta horns, a slow orbit).

  blender.exe -b --factory-startup --python sting.py -- --variant amber --frames 0,60,400,430 [--pct 50]
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
from vjkit import AMBER, CYAN, MAGENTA, UV  # noqa: E402

VARIANTS = {
    "amber": dict(bone=AMBER, horn=CYAN, sweep=(1.0, 0.75, 0.4), cam=(0, 0, 19.0), orbit=0.0),
    "cyan": dict(bone=CYAN, horn=MAGENTA, sweep=(0.6, 0.9, 1.0), cam=(-16, -9, 19.0), orbit=0.0),
    "uv": dict(bone=UV, horn=MAGENTA, sweep=(1.0, 0.5, 1.0), cam=(0, 4, 20.0), orbit=14.0),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))
R = 0.055                                        # bone radius for a cap height of 1
AIM_Z = 0.5                                      # the camera looks at the logo's vertical middle (DINO top 2.55, STAGE
                                                 # bottom -1.55): on the Dino Stage's arch screen only frame rows
                                                 # ~190-890 show, and at -0.25 the letter tops touched its edge


# ------------------------------------------------------------------ letterforms: strokes in a 1-high box, x to the right
def arc(cx, cy, rx, ry, a0, a1, n=14):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


GLYPHS = {
    "D": (0.62, [[(0, 0), (0, 1)], [(0, 1), (0.2, 1)] + arc(0.2, 0.5, 0.42, 0.5, 90, -90)[1:] + [(0, 0)]]),
    "I": (0.36, [[(0.18, 0), (0.18, 1)], [(0, 1), (0.36, 1)], [(0, 0), (0.36, 0)]]),
    "N": (0.62, [[(0, 0), (0, 1)], [(0, 1), (0.62, 0)], [(0.62, 0), (0.62, 1)]]),
    "O": (0.66, [arc(0.33, 0.5, 0.33, 0.5, 90, 270), arc(0.33, 0.5, 0.33, 0.5, -90, 90)]),
    "S": (0.58, [arc(0.29, 0.75, 0.29, 0.25, 15, 270, 12) + arc(0.29, 0.25, 0.29, 0.25, 90, -165, 12)[1:]]),
    "T": (0.62, [[(0, 1), (0.62, 1)], [(0.31, 1), (0.31, 0)]]),
    "A": (0.66, [[(0, 0), (0.33, 1)], [(0.33, 1), (0.66, 0)], [(0.15, 0.4), (0.51, 0.4)]]),
    "G": (0.64, [arc(0.33, 0.5, 0.33, 0.5, 40, 340, 18), [(0.38, 0.42), (0.64, 0.42), (0.64, 0.16)]]),
    "E": (0.54, [[(0, 0), (0, 1)], [(0, 1), (0.54, 1)], [(0, 0.5), (0.42, 0.5)], [(0, 0), (0.54, 0)]]),
}


def word(text, height, y, track):
    """Strokes of a centered line of text, in world meters on the XZ plane (z up)."""
    widths = [GLYPHS[ch][0] for ch in text]
    total = sum(widths) + track * (len(text) - 1)
    x, out = -total / 2, []
    for ch, w in zip(text, widths):
        for stroke in GLYPHS[ch][1]:
            out.append([Vector(((x + px) * height, 0.0, y + py * height)) for px, py in stroke])
        x += w + track
    return out


def bone_bm(pts, r):
    """A neon bone: a tube along the stroke with a knob at each end."""
    bm = bmesh.new()
    dense = []
    for a, b in zip(pts, pts[1:]):
        n = max(1, int((b - a).length / (r * 2)))
        dense += [a.lerp(b, i / n) for i in range(n)]
    dense.append(pts[-1])
    c = sum(dense, Vector()) / len(dense)
    vj.tube(bm, [p - c for p in dense], lambda u: r, segs=10)
    for p in (dense[0], dense[-1]):
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r * 1.7,
                                   matrix=Matrix.Translation(p - c))
    return bm, c


# ------------------------------------------------------------------ materials
def neon_mat(name, col, base):
    s = vj.Shader(name)
    geo = s.node("ShaderNodeNewGeometry")
    x, _, _ = s.xyz(geo.outputs["Position"])
    sweep = s.mul(s.gauss(x, s.c("SweepX"), 0.9), s.c("SweepAmt"))   # a highlight crossing the logo once per bar
    lift = s.add(0.6, s.mul(s.c("Kick"), 0.2), s.mul(s.c("Swell"), 0.55), s.mul(sweep, 0.6))
    c = s.mix(s.mul(s.smooth(s.core(0.0, 1.0), 0.8, 1.0), 0.4), col, (1.0, 1.0, 1.0))   # white-hot core line
    c = s.mix(s.mul(sweep, 0.5), c, V["sweep"])
    return s.emit(c, s.mul(s.c("Glow"), lift, s.core(), base * GAIN))


# ------------------------------------------------------------------ timing
SNAP = 2.0                                        # beats the bones take to fly back in
DRIFT = (25, 30)                                  # beats when they break apart and drift out


def fly_in(p, pa=0.5, pb=0.9):
    """0..1 over the snap: accelerate until pa, fly at full speed until pb, brake to rest at 1 (2-3 frames). The
    brake keeps the seam step (the lock on the downbeat) from being the loop's biggest jump."""
    vm = 2.0 / (1.0 + pb - pa)
    if p <= pa:
        return vm * p * p / (2 * pa)
    if p <= pb:
        return vm * (pa / 2 + p - pa)
    q = p - pb
    return vm * (pa / 2 + pb - pa + q - q * q / (2 * (1.0 - pb)))


def scatter(f):
    """0 = assembled .. 1 = fully scattered, at frame f (any integer: periodic)."""
    k = (f % vj.FRAMES) / vj.FPB                                     # beats into the loop
    if k < DRIFT[0]:
        return 0.0
    if k < DRIFT[1]:
        return vj.ease((k - DRIFT[0]) / (DRIFT[1] - DRIFT[0]))
    if k < 32 - SNAP:
        return 1.0
    return 1.0 - fly_in((k - (32 - SNAP)) / SNAP)                     # flying in, locking on the downbeat


def signals(f):
    c = vj.clock(f)
    k = (c["f"]) / vj.FPB
    swell = math.exp(-k / 1.5) if k < 8 else (((k - (32 - SNAP)) / SNAP) ** 2 if k >= 32 - SNAP else 0.0)
    bar_u = (c["f"] - vj.BEAT_F[4 * c["bar"]]) / (vj.BEAT_F[4 * c["bar"] + 4] - vj.BEAT_F[4 * c["bar"]])
    held = 1.0 - scatter(f)
    return {"Kick": c["kick"] * held, "Swell": swell, "Glow": 0.45 + 0.55 * held,
            "SweepX": -7.0 + 14.0 * bar_u, "SweepAmt": held * math.sin(math.pi * bar_u) ** 2,
            "Split": max(swell - 0.55, 0.0) / 0.45}


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    frames = list(range(vj.FRAMES + 1))
    ext = list(range(-2, vj.FRAMES + 3))
    sig = [signals(f) for f in frames]
    vj.build_clock({k: [s[k] for s in sig] for k in sig[0] if k != "Split"})
    bone_m = neon_mat("Bones", V["bone"], 1.2)            # 3.0 clipped the letters to white: 1 m2 blocks at 0.83
    horn_m = neon_mat("Horns", V["horn"], 1.35)
    rnd = random.Random(5)
    strokes = word("DINO", 2.4, 0.15, 0.22) + word("STAGE", 1.15, -1.55, 0.45)
    pieces = []
    for pts in strokes:
        pieces.append((bone_bm(pts, R * 2.4 if pts[0].z > 0 else R * 1.9), bone_m))
    for side in (-1, 1):                                              # the stage's horns flanking the logo
        hb = bmesh.new()
        vj.horn(hb, Vector((side * 3.6, 0, -0.4)), Vector((side * 0.55, 0, 1.0)), 3.4, 0.24,
                Vector((0, -side, 0)), -55, segs=12, steps=20)
        c = sum((v.co for v in hb.verts), Vector()) / len(hb.verts)
        bmesh.ops.translate(hb, vec=-c, verts=hb.verts)
        pieces.append(((hb, c), horn_m))
    for i, ((bm, home), mat) in enumerate(pieces):
        ob = vj.new_obj(f"Bone{i}", bm, mat)
        off = Vector((rnd.uniform(-1, 1) * 9, rnd.uniform(-6, 3), rnd.uniform(-1, 1) * 5))
        rot = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * math.pi
        lag = rnd.uniform(0.0, 3.0)                                   # frames: a ragged break, a clean lock
        keys_l, keys_r = [], []
        for f in ext:
            sc = scatter(f - lag * scatter(f))
            keys_l.append((f, tuple(home + off * sc)))
            keys_r.append((f, tuple(Euler(tuple(rot * sc)))))
        ob.rotation_mode = "XYZ"
        vj.animate(ob, "location", keys_l, interp="LINEAR")
        vj.animate(ob, "rotation_euler", keys_r, interp="LINEAR")

    az, el, dist = V["cam"]
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens, cam_data.sensor_width, cam_data.sensor_fit = 40, 36.0, "HORIZONTAL"
    cam_data.clip_start, cam_data.clip_end = 0.1, 200.0
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    keys_l, keys_r = [], []
    for f in ext:
        a = math.radians(az + V["orbit"] * math.sin(2 * math.pi * f / vj.FRAMES))
        e = math.radians(el + 2.0 * math.sin(4 * math.pi * f / vj.FRAMES))
        p = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
        keys_l.append((f, tuple(p)))                            # aimed at the logo's middle: it sits centered,
        keys_r.append((f, tuple((Vector((0, 0, AIM_Z)) - p).to_track_quat("-Z", "Y").to_euler())))   # inside the arch
    vj.animate(cam, "location", keys_l, interp="LINEAR")
    vj.animate(cam, "rotation_euler", keys_r, interp="LINEAR")
    return scene, [s["Split"] for s in sig]


scene, split = build()
vj.setup_render(scene, samples=int(vj.arg("--samples", 16)), pct=int(vj.arg("--pct", 100)),
                bloom=tuple(float(x) for x in vj.arg("--bloom", "1.0,0.6,0.4").split(",")), mblur=vj.flag("--mblur"))
nt = scene.node_tree                                                  # a brief RGB split rides the snap (smooth)
comp = [n for n in nt.nodes if n.bl_idname == "CompositorNodeComposite"][0]
src = comp.inputs["Image"].links[0].from_socket
lens = nt.nodes.new("CompositorNodeLensdist")
nt.links.new(src, lens.inputs["Image"])
nt.links.new(lens.outputs["Image"], comp.inputs["Image"])
vj.animate(lens.inputs["Dispersion"], "default_value", [(f, 0.06 * v) for f, v in enumerate(split)])
vj.finish(scene, f"sting_{VNAME}")
