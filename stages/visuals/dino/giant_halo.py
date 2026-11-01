"""GIANT HALO - Dino Stage VJ loop for the giant intro. 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit
(140 BPM half-time = 411 frames by default).

The stage goes dark, one spotlight finds the DJ and a lift raises them about 7 m in a floor-length robe. Behind them
the wall shows a huge red halo, like a backlit eclipse: a thin glowing ring around a black disc, a soft corona whose
streamers churn slowly, and smoke drifting up through its light (the smoke catches the glow in faint rays near the
ring and stays dark over the disc). A barely perceptible half-time breath: the halo swells a few percent into the
kick (beat 1) and a little less into the snare (beat 3). Calm and majestic: no hits, no flashes, mostly black.
Composition: the ring is centered where the raised DJ's head lands on the Dino Stage screen for the crowd (x 960,
y ~405 of 1080; the arch screen shows rows ~190-890 of the frame), so the spotlit DJ stands in front of the disc.
Variants: red.

  blender.exe -b --factory-startup --python giant_halo.py -- --variant red --frames 0,26,205 [--pct 50]
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402

# ring: hot core line, inner limb, corona near / far; smoke color and gain (linear emission colors). The Standard view
# transform clips each channel on its own and sRGB lifts small values a lot (linear 0.16 shows as 0.44), so a red that
# must stay red keeps green and blue at a few percent even in its clipped core
VARIANTS = {
    "red": dict(core=(1.0, 0.025, 0.01), limb=(1.0, 0.012, 0.008), corona=(1.0, 0.004, 0.012), far=(0.7, 0.0, 0.02),
                smoke=(1.0, 0.02, 0.025), smoke_gain=1.0),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

LENS = 50.0                                   # static camera at the origin looking down +Y
CX_PX, CY_PX, R_PX = 960, 405, 200            # ring center and radius in frame pixels
D_HALO = 100.0                                # the halo plane's distance (m)
BREATH_RING, BREATH_LIGHT, BREATH_SMOKE = 0.006, 0.06, 0.08   # swell on the accent: ring radius, halo, smoke light


def mpp(depth):
    """Meters per frame pixel at a depth."""
    return depth * 36.0 / LENS / 1920.0


RING_Z = (540 - CY_PX) * mpp(D_HALO)          # the ring center on the halo plane (x = 0)
RING_R = R_PX * mpp(D_HALO)
# smoke layers in front of the halo: depth (m), noise scale (1/m), drift per loop (m, x / up), seed, density window,
# gain
SMOKE = [(34.0, 0.16, (1.2, 2.6), 3.1, (0.50, 0.74), 0.25),
         (52.0, 0.10, (-1.8, 3.4), 7.7, (0.49, 0.72), 0.35),
         (74.0, 0.07, (1.0, 4.4), 12.3, (0.48, 0.70), 0.45)]


# ------------------------------------------------------------------ music
def breath(f):
    """0..1: peaks on each accent (the kick 1.0, the snare 0.8), a smooth 6-frame rise into it, a slow fall after."""
    c = vj.clock(f)
    amp = 0.8 if c["snare"] else 1.0
    nxt = 0.8 if vj.HALFTIME and ((c["acc"] + 1) * vj.ACC) % 4 == 2 else 1.0
    return max(amp * math.exp(-2.5 * c["aph"]), nxt * vj.ease((c["aph"] - 0.75) / 0.25))


def signals(f):
    c = vj.clock(f)
    t = c["loop"]
    return {"Breath": breath(f), "LoopT": t, "W1": math.cos(0.5 * math.pi * t), "W2": math.sin(0.5 * math.pi * t),
            "LoopCos": math.cos(2 * math.pi * t), "LoopSin": math.sin(2 * math.pi * t)}


# ------------------------------------------------------------------ shader helpers
def noise(s, vec, w, scale=1.0, detail=3.0, rough=0.55):
    n = s.node("ShaderNodeTexNoise", noise_dimensions="4D")
    s.put(n.inputs["Vector"], vec)
    s.put(n.inputs["W"], w)
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    return n.outputs["Fac"]


def ring_space(s, x, z):
    """(r, ux, uz) of a point on the halo plane relative to the ring: radius in ring radii (swelling a little with
    the breath) and the unit direction."""
    qx = s.mul(x, 1.0 / RING_R)
    qz = s.mul(s.math("SUBTRACT", z, RING_Z), 1.0 / RING_R)
    r0 = s.math("SQRT", s.add(s.mul(qx, qx), s.mul(qz, qz)))
    inv = s.math("DIVIDE", 1.0, s.math("MAXIMUM", r0, 1e-4))
    r = s.math("DIVIDE", r0, s.madd(s.c("Breath"), BREATH_RING, 1.0))
    return r, s.mul(qx, inv), s.mul(qz, inv)


def streamers(s, ux, uz, r, freq=2.4, slow=0.22):
    """Radial streaks: noise of the direction (plus a little radius), churning on a small circle in noise space."""
    vec = s.vec(s.mul(ux, freq), s.mul(uz, freq), s.madd(s.c("LoopCos"), slow, s.mul(r, 0.35)))
    return noise(s, vec, s.mul(s.c("LoopSin"), slow), scale=1.0, detail=2.0, rough=0.5)


def emit_sum(s, terms, additive=False):
    acc = None
    for col, st in terms:
        e = s.node("ShaderNodeEmission")
        s.put(e.inputs["Color"], col)
        s.put(e.inputs["Strength"], st)
        if acc is None:
            acc = e.outputs[0]
        else:
            add = s.node("ShaderNodeAddShader")
            s.nt.links.new(acc, add.inputs[0])
            s.nt.links.new(e.outputs[0], add.inputs[1])
            acc = add.outputs[0]
    if additive:
        add = s.node("ShaderNodeAddShader")
        s.nt.links.new(s.node("ShaderNodeBsdfTransparent").outputs[0], add.inputs[0])
        s.nt.links.new(acc, add.inputs[1])
        acc = add.outputs[0]
        s.mat.surface_render_method = "BLENDED"
        s.mat.use_transparency_overlap = True
    s.nt.links.new(acc, s.out.inputs["Surface"])
    return s.mat


# ------------------------------------------------------------------ materials
def smoke_density(s, x, z, scale, drift, seed, window):
    """0..1 smoke on a layer (layer-plane meters x, up): noise drifting `drift` m per loop, made seamless as a
    variance-preserving crossfade (cos/sin weights) of two copies one drift apart, then cut into wisps."""
    dx, dz = drift

    def at(t):
        return s.vec(s.mul(s.math("SUBTRACT", x, s.mul(t, dx)), scale),
                     s.mul(s.math("SUBTRACT", z, s.mul(t, dz)), scale), seed)
    n1 = noise(s, at(s.c("LoopT")), seed * 0.37, detail=4.0, rough=0.6)
    n2 = noise(s, at(s.math("SUBTRACT", s.c("LoopT"), 1.0)), seed * 0.37, detail=4.0, rough=0.6)
    n = s.add(s.mul(s.math("SUBTRACT", n1, 0.5), s.c("W1")), s.mul(s.math("SUBTRACT", n2, 0.5), s.c("W2")), 0.5)
    return s.smooth(n, *window)


def halo_mat():
    """Everything on one opaque plane: black disc, hot ring, corona with streamers, and the SMOKE layers in front of
    it lit by the halo (rays near the ring, dark over the disc, a faint spill elsewhere). The camera is static, so a
    smoke card at depth d would only show this plane's point scaled by d / D_HALO: one plane and one streamer lookup
    give the same picture as separate transparent cards, several times faster."""
    s = vj.Shader("Halo")
    x, _, z = s.xyz(s.node("ShaderNodeNewGeometry").outputs["Position"])
    r, ux, uz = ring_space(s, x, z)
    out = s.math("GREATER_THAN", r, 1.0)
    above = s.math("MAXIMUM", s.math("SUBTRACT", r, 1.0), 0.0)
    inside = s.math("MAXIMUM", s.math("SUBTRACT", 1.0, r), 0.0)
    st = streamers(s, ux, uz, r)
    ray = s.math("POWER", s.smooth(st, 0.32, 0.78), 1.4)            # 0 between streamers .. 1 on one
    lift = s.madd(s.c("Breath"), BREATH_LIGHT, 1.0)
    core = s.gauss(r, 1.0, 0.0105)
    limb = s.mul(s.math("SUBTRACT", 1.0, out), s.exp(s.mul(inside, -1.0 / 0.022)))
    near = s.mul(out, s.exp(s.mul(above, -1.0 / 0.085)), s.madd(ray, 0.45, 0.75))
    far = s.mul(out, s.exp(s.mul(above, -1.0 / 0.42)), s.madd(ray, 1.3, 0.12))
    sray = s.smooth(st, 0.3, 0.8)
    rim = s.add(s.mul(out, s.exp(s.mul(above, -1.0 / 0.22))),                 # backlit near the ring; in front of the
                s.mul(s.math("SUBTRACT", 1.0, out), s.exp(s.mul(inside, -1.0 / 0.06))))   # disc only at its rim
    back = s.add(s.mul(rim, s.madd(sray, 0.8, 0.35)),
                 s.mul(out, s.exp(s.mul(above, -1.0 / 1.1)), s.madd(sray, 0.25, 0.05)),   # the corona's spill
                 0.012)                                                                   # the spotlight's spill
    dens = None
    for depth, scale, drift, seed, window, gain in SMOKE:
        k = depth / D_HALO
        d = s.mul(smoke_density(s, s.mul(x, k), s.mul(z, k), scale, drift, seed, window), gain)
        dens = d if dens is None else s.add(dens, d)
    smoke = s.mul(dens, back, s.madd(s.c("Breath"), BREATH_SMOKE, 1.0), V["smoke_gain"] * GAIN)
    return emit_sum(s, [(V["core"], s.mul(core, lift, 2.4 * GAIN)),
                        (V["limb"], s.mul(limb, lift, 0.9 * GAIN)),
                        (V["corona"], s.mul(near, lift, 0.85 * GAIN)),
                        (V["far"], s.mul(far, lift, 0.16 * GAIN)),
                        (V["smoke"], smoke)])


# ------------------------------------------------------------------ scene
def card(name, depth, mat, margin=1.25, z0=0.0):
    """A plane facing the camera at `depth`, covering the frame with a margin (local x right, local z up)."""
    w = 1920 * mpp(depth) * margin
    h = 1080 * mpp(depth) * margin
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(v) for v in ((-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2),
                                            (-w / 2, 0, h / 2))])
    ob = vj.new_obj(name, bm, mat)
    ob.location = (0.0, depth, z0)
    return ob


def build():
    scene = vj.reset_scene()
    frames = list(range(vj.FRAMES + 1))
    sig = [signals(f) for f in frames]
    vj.build_clock({k: [s[k] for s in sig] for k in sig[0]})

    card("HaloPlane", D_HALO, halo_mat(), margin=1.1)

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens, cam_data.sensor_width, cam_data.sensor_fit = LENS, 36.0, "HORIZONTAL"
    cam_data.clip_start, cam_data.clip_end = 1.0, 500.0
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0.0, 0.0, 0.0)
    cam.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    scene.camera = cam
    return scene


scene = build()
vj.setup_render(scene, samples=int(vj.arg("--samples", 16)), pct=int(vj.arg("--pct", 100)),
                bloom=tuple(float(x) for x in vj.arg("--bloom", "1.0,0.6,0.4").split(",")), mblur=vj.flag("--mblur"))
vj.finish(scene, f"giant_halo_{VNAME}")
