"""PRIMEVAL JUNGLE - Dino Stage VJ loop (breakdown). 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM
half-time = 411 frames by default).

Layered fern, palm, cycad and horsetail silhouettes slide past in slow parallax against a UV-purple horizon glow, with
a volcano on the skyline. The camera tracks a giant sauropod walking behind the trees: a footfall on every accent
(half-time: the kick and the snare, one stride per 2 bars; straight: every beat, one stride per bar). Once per bar a
laser sheet slices through the canopy: it draws a line across every silhouette it cuts, and the lines on all the layers
snap together into one razor line along the horizon exactly on the downbeat (the sheet crosses the camera's eye height
then). Bars 1-4 the sheet falls from above the canopy (green), bars 5-8 it rises from the ground (cyan). Fireflies
drift and pulse on the offbeats (the "and"); the glow lifts softly on every accent and swells into the downbeats of
bars 1 and 5.
No strobing: at most 3 flashes per second, no one-frame hits, no full-frame white, no ~1 m2 patch of the 16 x 9 m wall
over 0.65 luma. All shapes are generated here; nothing is downloaded.

Variants (--variant):
  uv     UV-purple glow, magenta horizon, green/cyan laser sheet, amber and green fireflies
  ember  the same shot at a volcanic dusk: deep red glow, orange horizon, cyan/magenta sheet, amber fireflies
  crane  uv, with the camera craning up over the canopy through bars 1-4 and settling back into the ferns in bars 5-8

  blender.exe -b --factory-startup --python primeval_jungle.py -- --variant uv --frames 0,14,225 [--pct 25] [--samples 4]
  blender.exe -b --factory-startup --python primeval_jungle.py -- --variant uv --all --out DIR
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
from vjkit import AMBER, CYAN, GREEN, MAGENTA, ORANGE, UV  # noqa: E402

VARIANT = vj.arg("--variant", "uv")
if VARIANT not in ("uv", "ember", "crane"):
    raise SystemExit(f"unknown --variant {VARIANT!r}; choose one of: uv, ember, crane")
CRANE = VARIANT == "crane"
GAIN = float(vj.arg("--gain", 1.0))

PALETTES = {                                             # linear emission colors
    "uv": dict(sky=UV, band=MAGENTA, haze=(0.42, 0.03, 1.0), sheet=(GREEN, CYAN), lava=ORANGE,
               fire=((1.0, 0.5, 0.04), (0.45, 1.0, 0.08)), sky_e=0.55, band_e=0.5),
    "ember": dict(sky=(1.0, 0.035, 0.02), band=(1.0, 0.22, 0.015), haze=(1.0, 0.1, 0.06), sheet=(CYAN, MAGENTA),
                  lava=(1.0, 0.3, 0.02), fire=((1.0, 0.45, 0.03), (1.0, 0.75, 0.2)), sky_e=0.5, band_e=0.42),
}
PAL = PALETTES["uv" if CRANE else VARIANT]

CAM_Z = 3.0                    # eye height (m): the horizon line, where the laser sheet's slices converge
CRANE_RISE = 7.0 if CRANE else 0.0   # how far the crane variant's camera climbs mid-loop (m)
LENS, SHIFT_Y = 35.0, 0.045    # 54 deg wide; the horizon sits 58% down the frame
SKY_Y = 600.0                  # the glow backdrop
HZ, HZ_HALF = 0.09, 150.0      # silhouette haze: HZ * (d / (d + HZ_HALF)) ** 1.6 (aerial perspective: far = lighter)
KICK, SWELL = 0.12, 0.3        # glow lift on the kick and on the fills


def view_w(y):
    """Visible width (m) at depth y."""
    return y * 36.0 / LENS


def cam_z(f):
    """The camera's eye height at frame f (any real; periodic): a slow bob, and the crane variant's climb."""
    return (CAM_Z + 0.25 * math.sin(2 * math.pi * f / vj.FRAMES)
            + CRANE_RISE * math.sin(math.pi * f / vj.FRAMES) ** 2)


# ------------------------------------------------------------------ music
SECTION_B = 16                                           # first beat of bars 5-8


def swell(f):
    """Eases in over the last 2 beats of bars 4 and 8, peaks on the next downbeat, decays over ~1.5 beats."""
    c = vj.clock(f)
    if c["bar"] in (3, 7) and c["beat"] >= 2:
        f0, f1 = vj.BEAT_F[4 * c["bar"] + 2], vj.BEAT_F[4 * c["bar"] + 4]
        return ((c["f"] - f0) / (f1 - f0)) ** 2
    since = c["f"] - (vj.BEAT_F[SECTION_B] if c["f"] >= vj.BEAT_F[SECTION_B] else 0)
    return math.exp(-since / (1.5 * vj.FPB))


FALL = (1.0, 22.0, 9.0)        # bars 1-4: speed (m/frame), frames before the downbeat, frames after
RISE = (0.85, 6.0, 24.0)       # bars 5-8: rises from the ground and on up through the canopy


def sheet(f):
    """(height m, amplitude, section) of the laser sheet. It crosses the camera's eye height exactly on each downbeat,
    at full strength, after a quadratic swell; then it fades out. Bars 1-4 it falls, bars 5-8 it rises."""
    best = (cam_z(f), 0.0, 0.0)
    for bar in range(-1, 10):
        d = 4 * bar
        df = math.floor(d * vj.FPB + 0.5)                           # this downbeat's frame (unwrapped)
        sec = 1.0 if (bar % 8) >= 4 else 0.0
        v, pre, post = RISE if sec else FALL
        t = f - df
        if -pre <= t <= post:
            h = cam_z(df) + (v * t if sec else -v * t)
            a = ((t + pre) / pre) ** 2 if t < 0 else math.exp(-t / (post * 0.35)) * (1 - (t / post) ** 4)
            if a > best[1]:
                best = (h, a, sec)
    return best


def fire_env(f):
    """(envelope, offbeat index): fireflies flare on each offbeat (the "and"): 1 frame of rise, then a ~4-frame
    decay."""
    c = vj.clock(f)
    k = c["k"]
    hat = math.floor((k + 0.5) * vj.FPB + 0.5)
    if c["f"] >= hat - 1:
        dt = c["f"] - hat
        return (0.45 if dt < 0 else math.exp(-dt / 3.5)), k
    prev = math.floor((k - 0.5) * vj.FPB + 0.5)
    return math.exp(-(c["f"] - prev) / 3.5), (k - 1) % vj.BEATS


def signals(f):
    c = vj.clock(f)
    h, a, sec = sheet(f)
    env, fb = fire_env(f)
    return {"Kick": c["kick"], "Swell": swell(f), "Loop": c["loop"], "SheetZ": h, "SheetA": a, "SheetB": sec,
            "Fire": env, "FireBeat": float(fb)}


# ------------------------------------------------------------------ 2D silhouette shapes (in the XZ plane)
def ribbon(bm, pts, width, y=0.0):
    """Flat strip along the 2D polyline pts [(x, z)]; width(u) is the half-width, u in [0, 1]."""
    n = len(pts)
    left, right = [], []
    for i, (x, z) in enumerate(pts):
        ax, az = pts[max(i - 1, 0)]
        bx, bz = pts[min(i + 1, n - 1)]
        dx, dz = bx - ax, bz - az
        ln = math.hypot(dx, dz) or 1.0
        nx, nz = -dz / ln, dx / ln
        w = width(i / (n - 1))
        left.append(bm.verts.new((x + nx * w, y, z + nz * w)))
        right.append(bm.verts.new((x - nx * w, y, z - nz * w)))
    for i in range(n - 1):
        bm.faces.new((left[i], right[i], right[i + 1], left[i + 1]))


def ellipse(bm, cx, cz, rx, rz, tilt=0.0, n=28, y=0.0):
    ct, st = math.cos(tilt), math.sin(tilt)
    vs = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x, z = rx * math.cos(a), rz * math.sin(a)
        vs.append(bm.verts.new((cx + x * ct - z * st, y, cz + x * st + z * ct)))
    bm.faces.new(vs)


def arc(x, z, ang, length, bend, steps=8):
    """Points of a curve from (x, z) heading `ang` (rad, 0 = +x, pi/2 = up) that turns by `bend` rad in total."""
    pts = [(x, z)]
    for i in range(steps):
        a = ang + bend * (i + 0.5) / steps
        x, z = x + math.cos(a) * length / steps, z + math.sin(a) * length / steps
        pts.append((x, z))
    return pts


def leaf(bm, x, z, ang, length, width, droop=0.0, y=0.0):
    ribbon(bm, arc(x, z, ang, length, droop, steps=5), lambda u: width * math.sin(math.pi * min(u * 1.15, 1.0)) ** 0.7
           + 0.004, y)


def frond(bm, x, z, ang, length, bend, leaflet, density=1.0, spread=1.05, droop=-0.25, y=0.0):
    """A fern frond: a tapering rachis with alternating leaflets that shrink toward the tip."""
    n = max(int(18 * density * length / 3.0), 8)
    pts = arc(x, z, ang, length, bend, steps=n)
    ribbon(bm, pts, lambda u: 0.035 * length / 3.0 * (1.0 - 0.8 * u) + 0.006, y)
    for i in range(1, n):
        u = i / n
        px, pz = pts[i]
        dx, dz = pts[i + 1][0] - px, pts[i + 1][1] - pz
        a = math.atan2(dz, dx)
        size = leaflet * (math.sin(math.pi * min(u * 1.25, 1.0)) ** 0.6) * (1.0 - 0.55 * u) + 0.02
        side = 1 if i % 2 else -1
        leaf(bm, px, pz, a + side * spread, size, size * 0.17, droop * side, y)


def palm(bm, x, height, lean, rng, y=0.0, fronds=11):
    """A palm: a curved, tapering trunk and a crown of drooping fronds with long hanging leaflets."""
    trunk = arc(x, -0.5, math.pi / 2 + lean, height + 0.5, -lean * 1.6, steps=12)
    ribbon(bm, trunk, lambda u: 0.32 * (1.0 - 0.45 * u) * height / 14.0 + 0.05, y)
    tx, tz = trunk[-1]
    for i in range(fronds):
        a = math.pi * (0.06 + 0.88 * i / (fronds - 1)) + rng.uniform(-0.12, 0.12)
        side = 1 if math.cos(a) >= 0 else -1
        ln = height * rng.uniform(0.36, 0.48)
        pts = arc(tx, tz, a, ln, -side * rng.uniform(0.9, 1.6), steps=14)
        ribbon(bm, pts, lambda u: 0.05 * height / 14.0 * (1 - 0.7 * u) + 0.01, y)
        for j in range(2, 14):
            px, pz = pts[j]
            dx, dz = pts[j + 1][0] - px, pts[j + 1][1] - pz
            da = math.atan2(dz, dx)
            ll = ln * 0.3 * math.sin(math.pi * j / 14) ** 0.5
            for s in (-1, 1):
                leaf(bm, px, pz, da + s * 0.55 - side * 0.5, ll, ll * 0.09, -side * 0.6, y)
    ellipse(bm, tx, tz - 0.2, 0.45 * height / 14.0, 0.35 * height / 14.0, y=y)


def tree_fern(bm, x, height, rng, y=0.0):
    trunk = arc(x, -0.5, math.pi / 2 + rng.uniform(-0.08, 0.08), height + 0.5, rng.uniform(-0.1, 0.1), steps=10)
    ribbon(bm, trunk, lambda u: 0.22 * height / 8.0 * (1.0 - 0.3 * u) + 0.03, y)
    tx, tz = trunk[-1]
    for i in range(8):
        a = math.pi * (0.05 + 0.9 * i / 7) + rng.uniform(-0.1, 0.1)
        side = 1 if math.cos(a) >= 0 else -1
        frond(bm, tx, tz, a, height * rng.uniform(0.42, 0.55), -side * rng.uniform(1.2, 1.9),
              height * 0.075, density=1.2, y=y)


def fern_clump(bm, x, size, rng, y=0.0, n=7):
    for i in range(n):
        a = math.pi * (0.12 + 0.76 * (i + rng.uniform(-0.3, 0.3)) / (n - 1))
        side = 1 if math.cos(a) >= 0 else -1
        frond(bm, x + rng.uniform(-0.15, 0.15) * size, -0.1, a, size * rng.uniform(0.75, 1.05),
              -side * rng.uniform(0.6, 1.3), size * 0.17, y=y)


def cycad(bm, x, size, rng, y=0.0):
    trunk_h = size * 0.45
    ribbon(bm, [(x, -0.3), (x, trunk_h)], lambda u: size * 0.11 * (1.0 - 0.25 * u), y)
    for i in range(9):
        a = math.pi * (0.1 + 0.8 * i / 8) + rng.uniform(-0.06, 0.06)
        side = 1 if math.cos(a) >= 0 else -1
        frond(bm, x, trunk_h, a, size * rng.uniform(0.6, 0.8), -side * 0.35, size * 0.1, density=1.6,
              spread=1.25, droop=-0.05, y=y)


def horsetails(bm, x, size, rng, y=0.0, n=6):
    for i in range(n):
        sx = x + rng.uniform(-0.6, 0.6) * size * 0.3
        h = size * rng.uniform(0.6, 1.0)
        lean = rng.uniform(-0.12, 0.12)
        pts = arc(sx, -0.2, math.pi / 2 + lean, h, -lean * 0.5, steps=10)
        ribbon(bm, pts, lambda u: 0.025 * size / 3.0 * (1 - 0.5 * u) + 0.004, y)
        for j in range(2, 10, 1):
            px, pz = pts[j]
            for s in (-1, 1):
                leaf(bm, px, pz, math.pi / 2 + lean + s * 0.9, size * 0.06 * (1 - j / 12), size * 0.004, 0.0, y)


def conifer(bm, x, height, rng, y=0.0):
    """A prehistoric conifer (araucaria-like): a bare trunk with layered branch tufts near the top."""
    ribbon(bm, [(x, -0.5), (x, height)], lambda u: 0.25 * height / 18.0 * (1 - 0.6 * u) + 0.05, y)
    for j in range(6):
        z = height * (0.55 + 0.08 * j)
        w = height * 0.18 * (1 - 0.13 * j) * rng.uniform(0.8, 1.15)
        for s in (-1, 1):
            leaf(bm, x, z, math.pi / 2 - s * 1.25, w, height * 0.035, s * 0.25, y)
    ellipse(bm, x, height, height * 0.05, height * 0.06, y=y)


def ground(bm, x0, x1, top, rng, bumps=0.0, y=0.0, step=0.8):
    """Ground band from deep below up to a bumpy edge near `top` (bushes)."""
    x = x0
    while x < x1:
        w = step * rng.uniform(0.6, 1.4)
        h = top + bumps * rng.random() ** 2
        vs = [bm.verts.new((x, y, -60.0)), bm.verts.new((x + w + 0.05, y, -60.0)),
              bm.verts.new((x + w + 0.05, y, h)), bm.verts.new((x + w * 0.5, y, h + bumps * 0.3)),
              bm.verts.new((x, y, h))]
        bm.faces.new(vs)
        x += w


def volcano(bm, cx, base_w, height, crater_w, y=0.0):
    """Concave flanks up to a flat top with a shallow crater dip; vertical strips (no concave n-gons)."""
    def z_at(x):
        r = abs(x - cx)
        if r < crater_w / 2:
            return height * (1.0 - 0.05 * (1.0 - (2 * r / crater_w) ** 2))
        u = min((r - crater_w / 2) / (base_w / 2 - crater_w / 2), 1.0)
        return height * (1.0 - u ** 0.7)
    xs = [cx - base_w / 2 + base_w * i / 80 for i in range(81)]
    for x0, x1 in zip(xs, xs[1:]):
        bm.faces.new([bm.verts.new(v) for v in ((x0, y, -80.0), (x1 + 0.05, y, -80.0),
                                                (x1 + 0.05, y, z_at(x1)), (x0, y, z_at(x0)))])


def hills(bm, x0, x1, base, amp, seed, y=0.0, step=6.0):
    rng = random.Random(seed)
    ph = [rng.uniform(0, 6.3) for _ in range(3)]
    x = x0
    while x < x1:
        z0 = base + amp * (0.5 * math.sin(x * 0.011 + ph[0]) + 0.3 * math.sin(x * 0.027 + ph[1])
                           + 0.2 * math.sin(x * 0.061 + ph[2]))
        z1 = base + amp * (0.5 * math.sin((x + step) * 0.011 + ph[0]) + 0.3 * math.sin((x + step) * 0.027 + ph[1])
                           + 0.2 * math.sin((x + step) * 0.061 + ph[2]))
        bm.faces.new([bm.verts.new(v) for v in ((x, y, -80.0), (x + step + 0.1, y, -80.0),
                                                (x + step + 0.1, y, z1), (x, y, z0))])
        x += step


# ------------------------------------------------------------------ materials
def emit_sum(s, terms, additive=False):
    """Sum of emissions [(color, strength)]."""
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
    s.nt.links.new(acc, s.out.inputs["Surface"])
    return s.mat


def world_z(s):
    return s.xyz(s.node("ShaderNodeNewGeometry").outputs["Position"])[2]


def laser_slice(s):
    """(color, strength) of the laser sheet's cut through this surface: a line of constant screen width."""
    w = s.mul(s.dist, 0.0028)
    dz = s.math("SUBTRACT", world_z(s), s.c("SheetZ"))
    core = s.exp(s.mul(s.math("POWER", s.math("DIVIDE", dz, w), 2.0), -1.0))
    halo = s.exp(s.mul(s.math("POWER", s.math("DIVIDE", dz, s.mul(w, 5.0)), 2.0), -1.0))
    col = s.mix(s.c("SheetB"), PAL["sheet"][0], PAL["sheet"][1])
    above = s.smooth(world_z(s), -0.6, 0.4)                      # it never cuts below the ground
    return col, s.mul(s.c("SheetA"), s.add(s.mul(core, 4.0), s.mul(halo, 0.2)), above, GAIN)


def silhouette_mat(name, dark=1.0):
    s = vj.Shader(name)
    d = s.dist
    q = s.math("DIVIDE", d, s.add(d, HZ_HALF))
    haze = s.mul(s.math("POWER", q, 1.6), HZ * dark * GAIN)
    return emit_sum(s, [(PAL["haze"], haze), laser_slice(s)])


def sky_mat():
    s = vj.Shader("Sky")
    pos = s.node("ShaderNodeNewGeometry").outputs["Position"]
    x, _, z = s.xyz(pos)
    hz = s.math("SUBTRACT", z, CAM_Z)
    up = s.math("MAXIMUM", hz, 0.0)
    glow = s.add(s.mul(s.falloff(up, 18.0), 0.6), s.mul(s.gauss(up, 0.0, 60.0), 0.4))   # black from ~140 m up
    across = s.gauss(x, 0.0, 520.0)
    band = s.gauss(hz, 4.0, 16.0)
    lift = s.add(1.0, s.mul(s.c("Kick"), KICK), s.mul(s.c("Swell"), SWELL))
    base = s.mul(glow, s.madd(across, 0.6, 0.4), lift, PAL["sky_e"] * GAIN)
    vor = s.node("ShaderNodeTexVoronoi", voronoi_dimensions="2D")
    s.put(vor.inputs["Vector"], s.vec(x, z, 0.0))
    vor.inputs["Scale"].default_value = 0.06
    vor.inputs["Randomness"].default_value = 1.0
    rnd = s.xyz(vor.outputs["Color"])[0]
    star = s.mul(s.math("SUBTRACT", 1.0, s.smooth(vor.outputs["Distance"], 0.0, 0.05)),
                 s.math("GREATER_THAN", rnd, 0.72), s.madd(rnd, 1.2, -0.5), s.smooth(hz, 30.0, 120.0), 1.1 * GAIN)
    return emit_sum(s, [(PAL["sky"], base), (PAL["band"], s.mul(band, lift, PAL["band_e"] * GAIN)),
                        ((0.75, 0.7, 1.0), star), laser_slice(s)])


def lava_mat():
    s = vj.Shader("Lava")
    lift = s.add(1.0, s.mul(s.c("Swell"), 0.5))
    return s.emit(PAL["lava"], s.mul(lift, 1.6 * GAIN))


def firefly_mat():
    s = vj.Shader("Fireflies")
    oi = s.node("ShaderNodeObjectInfo")
    rnd = oi.outputs["Random"]
    h = s.math("FRACT", s.mul(s.math("SINE", s.madd(rnd, 127.1, s.mul(s.c("FireBeat"), 311.7))), 43758.5453))
    flare = s.math("GREATER_THAN", h, 0.45)                    # about half of them flare on any one offbeat
    breathe = s.madd(s.math("SINE", s.mul(s.madd(s.c("Loop"), 2.0, rnd), 2 * math.pi)), 0.25, 0.75)
    level = s.add(s.mul(breathe, 0.35), s.mul(flare, s.c("Fire"), 4.0))
    col = s.mix(s.math("GREATER_THAN", rnd, 0.6), PAL["fire"][0], PAL["fire"][1])
    return s.emit(col, s.mul(level, s.core(0.4, 1.2), GAIN))


# ------------------------------------------------------------------ scene
def scrolling_layer(name, y, screens, build_period, seed, mat):
    """A silhouette layer at depth y that slides `screens` frame widths left per loop. Its content repeats every
    period (= its travel), so frame 450 matches frame 0."""
    period = screens * view_w(y)
    half = view_w(y) * 0.5 + 25.0
    bm = bmesh.new()
    k0, k1 = math.floor(-half / period) - 1, math.ceil((half + period) / period) + 1
    for k in range(k0, k1 + 1):
        build_period(bm, k * period, period, random.Random(seed), y)
    ob = vj.new_obj(name, bm, mat)
    vj.animate(ob, "location", [(f, (-period * f / vj.FRAMES, 0.0, 0.0)) for f in (-30, 480)], interp="LINEAR")
    return ob


def treeline_period(bm, x0, p, rng, y):
    x = x0
    while x < x0 + p - 2.0:
        kind = rng.random()
        if kind < 0.4:
            conifer(bm, x, rng.uniform(13.0, 21.0), rng, y)
        elif kind < 0.75:
            palm(bm, x, rng.uniform(10.0, 15.0), rng.uniform(-0.12, 0.12), rng, y, fronds=8)
        else:
            tree_fern(bm, x, rng.uniform(6.0, 9.0), rng, y)
        x += rng.uniform(3.0, 8.5)
    ground(bm, x0, x0 + p, 0.4, rng, bumps=2.6, y=y, step=2.5)


def mid_period(bm, x0, p, rng, y):
    palm(bm, x0 + p * 0.12, rng.uniform(17.0, 20.0), 0.1, rng, y)
    tree_fern(bm, x0 + p * 0.45, rng.uniform(10.0, 12.0), rng, y)
    horsetails(bm, x0 + p * 0.62, 5.0, rng, y)
    palm(bm, x0 + p * 0.8, rng.uniform(12.0, 14.0), -0.18, rng, y, fronds=9)
    ground(bm, x0, x0 + p, 0.6, rng, bumps=2.8, y=y, step=1.6)


def near_period(bm, x0, p, rng, y):
    fern_clump(bm, x0 + p * 0.1, 4.2, rng, y)
    cycad(bm, x0 + p * 0.33, 3.2, rng, y)
    horsetails(bm, x0 + p * 0.5, 3.5, rng, y, n=5)
    fern_clump(bm, x0 + p * 0.72, 3.4, rng, y, n=6)
    ground(bm, x0, x0 + p, 0.15, rng, bumps=0.9, y=y, step=0.9)


def fore_period(bm, x0, p, rng, y):
    fern_clump(bm, x0 + p * 0.05, 3.2, rng, y, n=8)
    fern_clump(bm, x0 + p * 0.3, 2.2, rng, y, n=6)
    palm(bm, x0 + p * 0.62, 8.6, 0.08, rng, y, fronds=12)     # its crown hangs into the top of the frame
    fern_clump(bm, x0 + p * 0.85, 2.6, rng, y, n=7)
    ground(bm, x0, x0 + p, -0.1, rng, bumps=0.5, y=y, step=0.6)


SAURO_Y, SAURO_X, SAURO_S = 110.0, 14.0, 0.9             # depth, x, scale (a giant: ~23 m to the head; at 1.5
                                                         # its neck and head ran above the Dino Stage's arch window)
LEGS = [("LH", -4.2, 8.0, 0.00, -0.35), ("LF", 4.0, 9.2, 0.25, -0.35),    # name, x, length, footfall, y offset
        ("RH", -4.2, 8.0, 0.50, 0.35), ("RF", 4.0, 9.2, 0.75, 0.35)]       # lateral-sequence walk: a foot per accent
STRIDE = 4 * vj.ACC                                       # beats per stride: 8 half-time, 4 straight


def leg_pose(beatpos, footfall):
    """(swing angle rad, length scale) of a leg: planted on its accent, sweeping back for 3 accents, swung forward in
    the 4th with the foot lifted. Positive angle = foot back (Blender's +Y rotation)."""
    phase = (beatpos / STRIDE - footfall) % 1.0
    amp = math.radians(13.0)
    if phase < 0.75:
        return -amp + 2 * amp * phase / 0.75, 1.0
    s = (phase - 0.75) / 0.25
    return amp - 2 * amp * vj.ease(s), 1.0 - 0.1 * math.sin(math.pi * s)


def build_sauropod(mat, ext):
    root = vj.new_empty("Sauropod")
    root.location = (SAURO_X, SAURO_Y, 0.0)
    root.scale = (SAURO_S,) * 3
    body = vj.new_empty("SauroBody", root)
    bm = bmesh.new()
    ellipse(bm, 0.2, 9.9, 7.9, 3.1, tilt=math.radians(7))                           # body
    ribbon(bm, [(-6.5, 10.2), (-10.5, 9.5), (-15.0, 8.1), (-19.5, 6.4), (-23.0, 5.2)],
           lambda u: 1.7 * (1 - u) ** 1.2 + 0.05)                                    # tail root (the rest sways)
    vj.new_obj("SauroTorso", bm, mat, body)
    neck = vj.new_empty("SauroNeck", body)
    neck.location = (5.4, 0.0, 11.0)
    bm = bmesh.new()
    ribbon(bm, [(0.0, 0.0), (1.8, 3.2), (3.2, 7.0), (4.2, 10.8), (4.8, 13.8)], lambda u: 1.9 * (1 - u) + 0.55)
    ellipse(bm, 5.8, 14.3, 1.5, 0.65, tilt=math.radians(-12))                        # head
    ellipse(bm, 5.0, 14.6, 0.8, 0.7)
    vj.new_obj("SauroNeckMesh", bm, mat, neck)
    legs = []
    for name, lx, ln, ff, dy in LEGS:
        pivot = vj.new_empty("Sauro" + name, body)
        pivot.location = (lx, dy, ln)
        bm = bmesh.new()
        ribbon(bm, [(0.0, 0.4), (0.15, -ln * 0.5), (0.0, -ln + 0.4)], lambda u: 0.95 - 0.25 * u)
        ellipse(bm, 0.25, -ln + 0.35, 0.95, 0.45)                                    # foot
        vj.new_obj("SauroLeg" + name, bm, mat, pivot)
        legs.append((pivot, ff))
    keys_body, keys_neck = [], []
    for f in ext:
        c = vj.clock(f)
        bp = 32 * math.floor(f / vj.FRAMES) + c["beatpos"]
        keys_body.append((f, (0.0, 0.0, -0.18 * math.cos(2 * math.pi * bp / vj.ACC))))   # dips on each footfall
        lift = math.radians(4.0) * math.sin(2 * math.pi * f / vj.FRAMES)              # head rises over the loop
        keys_neck.append((f, (0.0, -lift + math.radians(1.5) * math.sin(2 * math.pi * bp / 8.0), 0.0)))
    vj.animate(body, "location", keys_body, interp="LINEAR")
    vj.animate(neck, "rotation_euler", keys_neck, interp="LINEAR")
    for pivot, ff in legs:
        keys_r, keys_s = [], []
        for f in ext:
            c = vj.clock(f)
            ang, sc = leg_pose(32 * math.floor(f / vj.FRAMES) + c["beatpos"], ff)
            keys_r.append((f, (0.0, ang, 0.0)))
            keys_s.append((f, (1.0, 1.0, sc)))
        vj.animate(pivot, "rotation_euler", keys_r, interp="LINEAR")
        vj.animate(pivot, "scale", keys_s, interp="LINEAR")
    return root


def build_fireflies(mat, ext, n=70, seed=11):
    rng = random.Random(seed)
    for i in range(n):
        y = rng.uniform(16.0, 48.0)
        w = view_w(y)
        x0 = rng.uniform(-0.48, 0.48) * w
        z0 = rng.uniform(0.3, CAM_Z + 0.45 * y * 0.5786 * 0.6)
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.06 * y / 25.0)
        ob = vj.new_obj(f"Firefly{i}", bm, mat)
        ax, az, p1, p2, m = rng.uniform(1.0, 3.0), rng.uniform(0.4, 1.2), rng.uniform(0, 6.3), rng.uniform(0, 6.3), \
            rng.choice((1, 2))
        vj.animate(ob, "location", [(f, (x0 + ax * math.sin(2 * math.pi * f / vj.FRAMES + p1), y,
                                         z0 + az * math.sin(2 * math.pi * m * f / vj.FRAMES + p2))) for f in ext],
                   interp="LINEAR")


def build():
    scene = vj.reset_scene()
    frames = list(range(vj.FRAMES + 1))
    ext = list(range(-2, vj.FRAMES + 3))
    sig = [signals(f) for f in frames]
    vj.build_clock({key: [s[key] for s in sig] for key in sig[0]})

    sky = bmesh.new()
    sky.faces.new([sky.verts.new(v) for v in ((-900, SKY_Y, -300), (900, SKY_Y, -300), (900, SKY_Y, 500),
                                              (-900, SKY_Y, 500))])
    vj.new_obj("Sky", sky, sky_mat())

    far = bmesh.new()                                      # static skyline: the volcano and the far hills
    volcano(far, -115.0, 230.0, 74.0, 16.0, y=420.0)
    hills(far, -500.0, 500.0, 8.0, 14.0, 3, y=440.0)
    vj.new_obj("Skyline", far, silhouette_mat("Skyline"))
    lava = bmesh.new()
    ribbon(lava, [(-123.0, 70.2), (-115.0, 69.4), (-107.0, 70.2)], lambda u: 0.55 * math.sin(math.pi * u) + 0.05,
           y=419.0)
    vj.new_obj("Lava", lava, lava_mat())

    scrolling_layer("Treeline", 200.0, 0.25, treeline_period, 21, silhouette_mat("Treeline"))
    build_sauropod(silhouette_mat("Sauropod", dark=0.55), ext)
    scrolling_layer("MidJungle", 75.0, 0.45, mid_period, 22, silhouette_mat("MidJungle"))
    scrolling_layer("NearJungle", 35.0, 0.75, near_period, 23, silhouette_mat("NearJungle"))
    scrolling_layer("Foreground", 14.0, 1.2, fore_period, 24, silhouette_mat("Foreground"))
    build_fireflies(firefly_mat(), ext)

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens, cam_data.sensor_width, cam_data.sensor_fit = LENS, 36.0, "HORIZONTAL"
    cam_data.shift_y = SHIFT_Y
    cam_data.clip_start, cam_data.clip_end = 0.5, 2000.0
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    vj.animate(cam, "location", [(f, (0.0, 0.0, cam_z(f))) for f in ext], interp="LINEAR")
    cam.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    return scene


scene = build()
vj.setup_render(scene, samples=int(vj.arg("--samples", 16)), pct=int(vj.arg("--pct", 100)),
                view=vj.arg("--view", "Standard"), exposure=float(vj.arg("--exposure", 0.0)),
                bloom=tuple(float(x) for x in vj.arg("--bloom", "1.0,0.6,0.4").split(",")), mblur=vj.flag("--mblur"))
vj.finish(scene, "primeval_jungle_" + VARIANT)
