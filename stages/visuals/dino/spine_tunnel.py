"""SPINE TUNNEL - Dino Stage VJ loop (build -> drop). 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit
(140 BPM half-time = 411 frames by default; --bpm 128 --straight made the 128 cuts).

Fly through an endless neon ribcage. One rib arch passes the camera per beat; every 4th arch (the bar's downbeat) is
cyan and carries flared horns like the stage's spine. A lava moon with a chasing bulb ring sits at the end of the
tunnel over a laser-grid floor.
  Bars 1-4 (A): amber ribs, red spine, UV grid; the tunnel alone.
  Bars 5-8 (B): magenta ribs, UV spine, green grid; an 8-beam laser fan (green/cyan/red) re-cues on every accent.
Every accent (half-time: the kick on beat 1 and the snare on beat 3; straight: every beat) lifts the near arches, sends
a light pulse down the tunnel and punches the lens in a little (accent frames at most ~1.6x as bright as the frames
between them). The last two beats of bars 4 and 8 swell into the next downbeat while a cyan ghost arch glides in and
settles framing the screen; the palette morphs into the other section's so it lands on the hit, and the arch
dissolves after it.
No strobing (the user finds stage flashing too much): at most 3 flashes per second, no one-frame hits, no full-frame
white, and no ~1 m2 patch of the 16 x 9 m wall averages over 70% luma.
Geometry and look are our own; the tube/horn generators come from TribeXR/Scripts/Blender/dino_stage.py.

  blender.exe -b --factory-startup --python spine_tunnel.py -- --frames 0,14,225 [--pct 50] [--samples 16]
  blender.exe -b --factory-startup --python spine_tunnel.py -- --all [--out DIR] [--blend FILE]
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

# Variants: palettes as (bars 1-4, bars 5-8), the camera path, the arch density (beats between arches) and the kick
# pulse's run down the tunnel (m per beat, width m): over brighter or sparser ribs a fast pulse reads as a one-frame hit.
VARIANTS = {
    "amber": dict(ribs=(AMBER, MAGENTA), downbeat=(CYAN, CYAN), spine=(RED, UV), grid=(UV, GREEN), rim=AMBER,
                  lasers=[GREEN, CYAN, GREEN, RED, RED, GREEN, CYAN, GREEN], cam="center", step=1, wave=(130, 7)),
    "ice": dict(ribs=(CYAN, UV), downbeat=(MAGENTA, MAGENTA), spine=(UV, MAGENTA), grid=(UV, CYAN), rim=MAGENTA,
                lasers=[MAGENTA, RED, MAGENTA, UV, UV, MAGENTA, RED, MAGENTA], cam="corkscrew", step=1,
                wave=(70, 11)),   # the corkscrew sweeps the ribs through the top-left corner: 3 flashes/s there,
                                  # the cap (also at 128); a near-lens fade did nothing (nothing in view is < 6 m)
    "ember": dict(ribs=(RED, ORANGE), downbeat=(AMBER, AMBER), spine=(ORANGE, RED), grid=(RED, UV), rim=AMBER,
                  lasers=[AMBER, RED, AMBER, ORANGE, ORANGE, AMBER, RED, AMBER], cam="low", step=2, wave=(70, 11),
                  pulse=0.3),   # half-time: each arch now arrives on an accent and carries it, so the accent light is
                                # cut (pulse 1.0: x1.80, 0.5: x1.60, the cap)
}
VNAME, V = vj.variant(VARIANTS)

D = 4.0                                   # camera travel per beat (m)
STEP = V["step"]                          # beats between arches: 1 = one per beat, 2 = half time
SP = D * STEP                             # arch spacing (m)
TRAVEL = vj.BEATS * D                     # 128 m per loop, a whole number of arch spacings: frame 450 == frame 0
CAM_Z = 2.8
H = 7.4                                   # vertebra height
MOON_DIST, MOON_R, MOON_Z = 300.0, 95.0, 6.0
N_ARCH = int((TRAVEL + MOON_DIST) / SP) + 4   # the tunnel always runs on behind the moon, so its far end never shows
LASER_SRC = Vector((0.0, 250.0, 4.0))     # rig space (the rig follows the camera's travel)
GHOST_FROM = 260.0                        # ghost arch start distance (m)
GHOST_HIT = 10.0                          # its distance on the downbeat: it frames the screen, midway between two
                                          # arches (on top of one its light stacked and clipped to white)
FADE = 24.0                               # arch brightness falls off as exp(-distance / FADE)
GAIN = float(vj.arg("--gain", 0.45))      # global emission multiplier (look development)
PULSE = V.get("pulse", 1.0)               # strength of the accent light (kick lift and wave)

# rib centerline, right side, (x, y offset, z): from the vertebra out, down and raked back toward the tail (-Y)
RIB = [(0.45, 0.0, H - 0.05), (2.2, -0.1, H - 0.2), (4.0, -0.3, H - 0.9), (5.35, -0.55, H - 2.3),
       (5.95, -0.8, H - 4.2), (5.75, -0.95, H - 5.9), (5.2, -1.05, H - 7.1), (4.9, -1.1, H - 7.8)]


def rib_pts(side, y):
    return vj.catmull([Vector((side * x, y + dy, z)) for x, dy, z in RIB], per=6)


# ------------------------------------------------------------------ geometry
def build_arches():
    ribs, accent, spine = bmesh.new(), bmesh.new(), bmesh.new()
    for i in range(-3, N_ARCH):
        y = i * SP
        acc = (i * STEP) % 4 == 0                                # passes the camera on a bar's downbeat
        for side in (-1, 1):
            vj.tube(accent if acc else ribs, rib_pts(side, y), lambda u: 0.11 - 0.05 * u, segs=10)
            vj.horn(spine, Vector((side * 0.5, y, H)), Vector((side, 0.0, 0.25)), 1.1, 0.11,
                    Vector((0, -side, 0)), 20, segs=8, steps=8)                         # transverse process
        vj.tube(spine, vj.circle_pts(Vector((0, y, H)), 0.5, 24), lambda u: 0.075, segs=8, closed=True)  # centrum
        vj.horn(spine, Vector((0, y, H + 0.5)), Vector((0, -0.12, 1)), 3.0 if acc else 1.9,
                0.2 if acc else 0.15, Vector((1, 0, 0)), 38, segs=8, steps=14)        # neural spine, raked back
        if acc:
            for side in (-1, 1):                     # flared horns (the stage's), in the low-luma spine colors: in
                vj.horn(spine, Vector((side * 0.55, y, H + 0.2)), Vector((side * 0.8, -0.1, 1.0)), 4.6, 0.3,
                        Vector((0, side, 0)), -50, segs=10, steps=20)       # cyan they crowded the top on kicks
    return ribs, accent, spine


def ghost_arch_bm():
    bm = bmesh.new()
    pts = list(reversed(rib_pts(1, 0.0))) + rib_pts(-1, 0.0)[1:]
    vj.tube(bm, pts, lambda u: 0.15, segs=10)
    return bm


def disc_bm(radius, n=160):
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in vj.circle_pts(Vector((0, 0, 0)), radius, n)]
    bm.faces.new(list(reversed(vs)))                              # normal toward -Y (the camera)
    return bm


def beam_bm(length=330.0, r0=0.16, r1=0.05, segs=8):
    bm = bmesh.new()
    pts = [Vector((0, -length * t, 0)) for t in (0.0, 0.5, 1.0)]
    vj.tube(bm, pts, lambda u: r0 + (r1 - r0) * u, segs=segs)
    return bm


# ------------------------------------------------------------------ materials
def arch_mat(name, col_a, col_b, base):
    s = vj.Shader(name)
    d = s.dist
    near = s.mul(s.c("Kick"), s.falloff(d, 22.0))
    wave = s.mul(s.c("WaveAmp"), s.gauss(d, s.madd(s.c("WavePos"), V["wave"][0], 10.0), V["wave"][1]))
    lift = s.add(0.5, s.mul(near, 0.32 * PULSE), s.mul(wave, 0.38 * PULSE), s.mul(s.c("Swell"), 0.7))
    col = s.mix(s.c("Section"), col_a, col_b)
    col = s.mix(s.mul(s.smooth(s.core(0.0, 1.0), 0.8, 1.0), 0.4), col, (1.0, 1.0, 1.0))    # white-hot core line
    return s.emit(col, s.mul(base * GAIN, s.falloff(d, FADE), s.core(), lift))


def grid_mat(col_a, col_b):
    s = vj.Shader("Grid")
    geo = s.node("ShaderNodeNewGeometry")
    x, y, _ = s.xyz(geo.outputs["Position"])

    def lines(v, spacing, half_w):
        t = s.math("FRACT", s.madd(v, 1.0 / spacing, 0.5))
        dist = s.mul(s.math("ABSOLUTE", s.math("SUBTRACT", t, 0.5)), spacing)
        return s.math("SUBTRACT", 1.0, s.smooth(dist, half_w, half_w * 2.5))

    g = s.math("MAXIMUM", lines(x, 2.0, 0.045), lines(y, 2.0, 0.045))
    d = s.dist
    fade = s.mul(s.falloff(d, 38.0), s.falloff(s.math("ABSOLUTE", x), 45.0))
    near = s.mul(s.c("Kick"), s.falloff(d, 18.0))
    wave = s.mul(s.c("WaveAmp"), s.gauss(d, s.madd(s.c("WavePos"), V["wave"][0], 10.0), V["wave"][1]))
    lift = s.add(0.55, s.mul(near, 0.3 * PULSE), s.mul(wave, 0.32 * PULSE), s.mul(s.c("Swell"), 0.45))
    return s.emit(s.mix(s.c("Section"), col_a, col_b), s.mul(g, fade, lift, 2.2 * GAIN))


def moon_coords(s):
    tc = s.node("ShaderNodeTexCoord")
    x, _, z = s.xyz(tc.outputs["Object"])
    qx, qz = s.mul(x, 1.0 / MOON_R), s.mul(z, 1.0 / MOON_R)
    r = s.math("SQRT", s.add(s.mul(qx, qx), s.mul(qz, qz)))
    return qx, qz, r


def moon_mat():
    s = vj.Shader("LavaMoon")
    qx, qz, r = moon_coords(s)
    cz, cw = s.mul(s.c("LoopCos"), 0.55), s.mul(s.c("LoopSin"), 0.55)     # a circle in noise space: seamless churn
    noise = s.node("ShaderNodeTexNoise", noise_dimensions="4D")
    s.put(noise.inputs["Vector"], s.vec(s.mul(qx, 2.0), s.mul(qz, 2.0), cz))
    s.put(noise.inputs["W"], cw)
    noise.inputs["Scale"].default_value = 1.6
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.55
    noise.inputs["Distortion"].default_value = 0.6
    n = noise.outputs["Fac"]
    warp = s.mul(s.math("SUBTRACT", n, 0.5), 0.9)
    vor = s.node("ShaderNodeTexVoronoi", voronoi_dimensions="4D", feature="DISTANCE_TO_EDGE")
    s.put(vor.inputs["Vector"], s.vec(s.madd(qx, 3.2, warp), s.madd(qz, 3.2, warp), s.mul(cz, 1.4)))
    s.put(vor.inputs["W"], s.mul(cw, 1.4))
    crack = s.math("SUBTRACT", 1.0, s.smooth(vor.outputs["Distance"], 0.0, 0.07))
    heat = s.add(s.mul(crack, 0.85), s.mul(s.math("POWER", n, 3.0), 1.1))
    ramp = s.node("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    stops = [(0.0, (0.03, 0.0, 0.0)), (0.3, (0.32, 0.012, 0.0)), (0.6, (1.0, 0.16, 0.0)),
             (0.85, (1.0, 0.42, 0.03)), (1.0, (1.0, 0.78, 0.32))]
    els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1)
    els[1].position, els[1].color = stops[-1][0], (*stops[-1][1], 1)
    for p, c in stops[1:-1]:
        els.new(p).color = (*c, 1)
    s.put(ramp.inputs["Fac"], heat)
    limb = s.smooth(r, 0.7, 1.0)
    pulse = s.add(1.0, s.mul(s.c("Kick"), 0.07), s.mul(s.c("Swell"), 0.4))
    return s.emit(ramp.outputs["Color"], s.mul(s.madd(limb, 0.8, 0.55), pulse, 1.7 * GAIN))


def rim_mat():
    s = vj.Shader("MoonRim")
    return s.emit(V["rim"], s.mul(s.add(1.0, s.mul(s.c("Kick"), 0.35), s.mul(s.c("Swell"), 0.6)), 4.0 * GAIN,
                                  s.core()))


def bulb_mat():
    s = vj.Shader("MoonBulbs")
    tc = s.node("ShaderNodeTexCoord")
    x, _, z = s.xyz(tc.outputs["Object"])
    idx = s.mul(s.math("ARCTAN2", z, x), 48 / (2 * math.pi))                 # bulb index around the ring
    chase = s.math("COSINE", s.mul(s.math("SUBTRACT", s.mul(idx, 0.25), s.c("BeatPos")), 2 * math.pi))
    lit = s.smooth(chase, 0.35, 0.95)                                         # every 4th bulb, 4 bulbs per beat
    level = s.add(0.12, lit, s.mul(s.c("Kick"), 0.2), s.mul(s.c("Swell"), 0.4))
    return s.emit((1.0, 0.55, 0.2), s.mul(level, 6.0 * GAIN))


def beam_mat(name, gain, near_fade):
    """Per-object light (lasers, ghost arch): color = object color RGB, intensity = object color alpha."""
    s = vj.Shader(name)
    oi = s.node("ShaderNodeObjectInfo")
    fade = s.smooth(s.dist, near_fade[0], near_fade[1])
    return s.additive(oi.outputs["Color"], s.mul(oi.outputs["Alpha"], gain * GAIN, fade))


# ------------------------------------------------------------------ choreography
SECTION_B = 16                                         # first beat of bars 5-8
GHOST_LAUNCH = (14, 30)                                # beat 3 of bars 4 and 8: arrives on the next downbeat
MORPH = 8                                              # frames for the A/B palette morph that lands on a hit
DISSOLVE = 6                                           # frames for the ghost arch to fade out after a hit
LASER_COLORS = V["lasers"]
# Per beat of bars 5-8: (angle deg, spread m, offset m). The 8 beams land on a line in the camera's plane that runs
# `offset` from the camera, turned by `angle` about it (0 = a horizontal fan above); the line never passes through the
# camera, which would collapse the fan onto a single line on screen.
CUES = [(0, 2.6, 6.5), (0, 3.4, 2.5), (0, 2.6, 6.5), (0, 3.4, 2.5),         # bar 5: the fan bounces
        (22, 3.0, 4.5), (-22, 3.0, 4.5), (22, 3.0, 4.5), (-22, 3.0, 4.5),     # bar 6: it rocks
        (0, 1.0, 5.0), (0, 2.0, 5.0), (0, 3.0, 5.0), (0, 4.2, 5.0),           # bar 7: it opens up
        (90, 2.4, 5.0), (45, 2.4, 5.0), (0, 2.4, 5.0), (-45, 2.4, 5.0)]       # bar 8: it swings over the top
if vj.HALFTIME:                                        # one cue per accent (kick, snare): the same moves at half speed
    CUES = [(0, 2.6, 6.5), (0, 3.4, 2.5), (22, 3.0, 4.5), (-22, 3.0, 4.5),
            (0, 1.4, 5.0), (0, 3.6, 5.0), (90, 2.4, 5.0), (-45, 2.4, 5.0)]
PUNCH = 0.035                                          # lens punch-in on an accent (share of the focal length)


def since_hit(f):
    """Frames since the last hit: the downbeats of bars 1 and 5, where the sections switch (cyclic)."""
    f %= vj.FRAMES
    return f - vj.BEAT_F[SECTION_B] if f >= vj.BEAT_F[SECTION_B] else f


def swell(f):
    """The fill: eases in over the last 2 beats of bars 4 and 8, peaks at 1 on the next downbeat, then decays over
    about a beat. A crescendo into the hit, with no frame-to-frame flashing."""
    c = vj.clock(f)
    if c["bar"] in (3, 7) and c["beat"] >= 2:
        f0, f1 = vj.BEAT_F[4 * c["bar"] + 2], vj.BEAT_F[4 * c["bar"] + 4]
        return ((c["f"] - f0) / (f1 - f0)) ** 2
    return math.exp(-since_hit(f) / vj.FPB)


def section(f):
    """0 = A (bars 1-4), 1 = B (bars 5-8). Over the last MORPH frames of the fill the palette morphs into the next
    section's, so it lands complete on the hit (no cut; B is the brighter palette, so a morph after the hit would push
    the brightness peak past the downbeat)."""
    f %= vj.FRAMES
    nxt = vj.BEAT_F[SECTION_B] if f < vj.BEAT_F[SECTION_B] else vj.FRAMES     # the next hit
    cur = 0.0 if f < vj.BEAT_F[SECTION_B] else 1.0
    x = vj.ease((f - (nxt - MORPH)) / MORPH) if f >= nxt - MORPH else 0.0
    return cur + (1.0 - 2.0 * cur) * x


def signals(f):
    c = vj.clock(f)
    return {
        "Kick": c["kick"], "WavePos": c["aph"], "WaveAmp": (1 - c["aph"]) ** 1.5,
        "Section": section(f), "Swell": swell(f), "BeatPos": c["beatpos"],
        "LoopCos": math.cos(2 * math.pi * c["loop"]), "LoopSin": math.sin(2 * math.pi * c["loop"]),
    }


def laser_state(f):
    """[(direction rig-space, intensity)] for the 8 beams at frame f. They fade in and out with the section morph."""
    c = vj.clock(f)
    j = max(c["acc"] - SECTION_B // vj.ACC, 0)                     # bars 1-4: dark (or fading in), on the first cue
    a0, a1 = CUES[max(j - 1, 0)], CUES[j]
    x = vj.ease((c["f"] - vj.BEAT_F[c["acc"] * vj.ACC]) / 4.0)   # snap to the new cue in 4 frames
    ang, spread, off = (p + (q - p) * x for p, q in zip(a0, a1))
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    level = min(0.75 + 0.1 * c["kick"] + 0.2 * swell(f), 1.0) * section(f)
    out = []
    for i in range(8):
        u = (i - 3.5) * spread
        tgt = Vector((u * ca - off * sa, 0.0, CAM_Z + u * sa + off * ca))
        out.append(((tgt - LASER_SRC).normalized(), level))
    return out


def ghost_state(f):
    """(distance ahead of the camera, intensity) of the ghost arch. Launched at the tunnel's end on beat 3 of bars 4
    and 8, it rushes in and eases out, settling to frame the screen on the next downbeat; then it drifts on and
    dissolves over DISSOLVE frames. Cyclic: the bar-8 launch lands on frame 450 == 0."""
    for b in GHOST_LAUNCH:
        span = vj.BEAT_F[b + 2] - vj.BEAT_F[b]
        t = (f - vj.BEAT_F[b]) % vj.FRAMES                         # frames since launch
        if t <= span:
            u = t / span
            return GHOST_HIT + (GHOST_FROM - GHOST_HIT) * (1 - u) ** 2.2, vj.ease(u / 0.3)
        if t <= span + DISSOLVE:
            return GHOST_HIT - 0.6 * (t - span), 1.0 - vj.ease((t - span) / DISSOLVE)
    return -60.0, 0.0


def cam_path(f):
    """(x m, z m, pitch deg, roll deg) of the camera at frame f: periodic over the loop, so the seam holds."""
    a = 2 * math.pi * f / vj.FRAMES
    if V["cam"] == "corkscrew":                  # a slow spiral around the tunnel's axis, banking into the turn
        return 1.4 * math.sin(a), CAM_Z + 0.9 * math.cos(a), 0.0, 6.0 * math.sin(a)
    if V["cam"] == "low":                        # skimming the floor, looking up at the ribs, a slight weave
        return 0.6 * math.sin(a), 1.5, 5.0, 2.0 * math.sin(2 * a)
    return 0.0, CAM_Z, 0.0, 3.0 * math.sin(2 * a)


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    frames = list(range(vj.FRAMES + 1))                            # keys through 450 (== 0) for the seam check
    ext = list(range(-2, vj.FRAMES + 3))                           # transforms: motion blur samples past the ends
    sig = [signals(f) for f in frames]
    vj.build_clock({key: [s[key] for s in sig] for key in sig[0]})

    ribs, accent, spine = build_arches()
    vj.new_obj("Ribs", ribs, arch_mat("Ribs", *V["ribs"], 4.0))
    vj.new_obj("RibsDownbeat", accent, arch_mat("RibsDownbeat", *V["downbeat"], 4.0))
    vj.new_obj("Spine", spine, arch_mat("Spine", *V["spine"], 4.0))

    floor = bmesh.new()
    bmesh.ops.create_grid(floor, x_segments=1, y_segments=1, size=1.0)
    bmesh.ops.scale(floor, vec=(700, 1500, 1), verts=floor.verts)
    bmesh.ops.translate(floor, vec=(0, 1400, 0), verts=floor.verts)
    vj.new_obj("GridFloor", floor, grid_mat(*V["grid"]))

    rig = vj.new_empty("FarRig")                                    # follows the camera's travel, never rolls
    vj.animate(rig, "location", [(f, (0, TRAVEL * f / vj.FRAMES, 0)) for f in (-30, 480)], interp="LINEAR")
    moon = vj.new_obj("LavaMoon", disc_bm(MOON_R), moon_mat(), rig)
    moon.location = (0, MOON_DIST, MOON_Z)
    rim = bmesh.new()
    vj.tube(rim, vj.circle_pts(Vector((0, 0, 0)), MOON_R * 1.03, 160), lambda u: 0.9, segs=8, closed=True)
    vj.new_obj("MoonRim", rim, rim_mat(), rig).location = (0, MOON_DIST - 1, MOON_Z)
    bulbs = bmesh.new()
    for p in vj.circle_pts(Vector((0, 0, 0)), MOON_R * 1.09, 48):
        bmesh.ops.create_icosphere(bulbs, subdivisions=2, radius=1.9, matrix=Matrix.Translation(p))
    vj.new_obj("MoonBulbs", bulbs, bulb_mat(), rig).location = (0, MOON_DIST - 1, MOON_Z)

    beam = beam_mat("Laser", 10.0, (6.0, 35.0))
    states = {f: laser_state(f) for f in ext}
    for i in range(8):
        ob = vj.new_obj(f"Laser{i}", beam_bm(), beam, rig)
        ob.location = LASER_SRC
        ob.rotation_mode = "QUATERNION"
        vj.animate(ob, "rotation_quaternion",
                   [(f, tuple(states[f][i][0].to_track_quat("-Y", "Z"))) for f in ext], interp="LINEAR")
        vj.animate(ob, "color", [(f, (*LASER_COLORS[i], states[f][i][1])) for f in frames])

    ghost = vj.new_obj("GhostArch", ghost_arch_bm(), beam_mat("Ghost", 1.45, (0.5, 3.0)), rig)   # 1.6 at 128:
    # at 140 it rushes in with the green lasers fading in and their stack came within 0.03 of the block cap
    gs = {f: ghost_state(f) for f in ext}
    vj.animate(ghost, "location", [(f, (0, gs[f][0], 0)) for f in ext], interp="LINEAR")
    vj.animate(ghost, "color", [(f, (0.0, 0.55, 1.0, gs[f][1])) for f in frames])

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens, cam_data.sensor_width, cam_data.sensor_fit = 20.0, 36.0, "HORIZONTAL"
    cam_data.shift_y = 0.09
    cam_data.clip_start, cam_data.clip_end = 0.3, 4000.0
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    keys_loc, keys_rot = [], []
    for f in ext:
        (x, z, pitch, roll), dip = cam_path(f), 0.07 * vj.clock(f)["kick"]
        keys_loc.append((f, (x, TRAVEL * f / vj.FRAMES, z - dip)))
        keys_rot.append((f, (math.radians(90.0 + pitch), math.radians(roll), 0.0)))
    vj.animate(cam, "location", keys_loc, interp="LINEAR")
    vj.animate(cam, "rotation_euler", keys_rot, interp="LINEAR")
    if vj.HALFTIME:                                                 # the hits land as a punch-in, not as light
        vj.animate(cam_data, "lens", [(f, 20.0 * (1.0 + PUNCH * vj.clock(f)["kick"])) for f in ext], interp="LINEAR")
    return scene


scene = build()
vj.setup_render(scene, samples=int(vj.arg("--samples", 16)), pct=int(vj.arg("--pct", 100)),
                view=vj.arg("--view", "Standard"), look=vj.arg("--look"), exposure=float(vj.arg("--exposure", 0.0)),
                bloom=tuple(float(x) for x in vj.arg("--bloom", "1.0,0.6,0.4").split(",")), mblur=vj.flag("--mblur"))
vj.finish(scene, f"spine_tunnel_{VNAME}")
