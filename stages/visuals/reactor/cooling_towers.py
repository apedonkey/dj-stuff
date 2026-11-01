"""COOLING TOWERS - REACTOR VJ loop. 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM half-time =
411 frames).

A low dolly past the plant's hyperbolic cooling towers at night. The towers stand in black silhouette, rim-lit by
their own steam; each plume (layered cards) streams up out of the tower's mouth, lit from inside, and bends downwind.
Through the open lattice of columns at each tower's foot the lit interior glows. Red aircraft lights on the rims fade
up and down once a bar (fades, never blinks). Three rows at different depths (the far one with a reactor dome and a
stack) parallax past each other; the camera travels exactly one row period per loop, so frame 411 equals frame 0.
  Bars 1-4 (A): the steam is lit in the variant's first colour.  Bars 5-8 (B): its second (the morph lands on bar 5's
  downbeat and back on the loop's).
Beat hooks: the steam swells into every downbeat: over the bar's last beat a puff inflates in each mouth, and from the
downbeat it lifts away up the plume (a band of brighter, denser steam rising with the flow); the last two beats of bars
4 and 8 swell into the next phrase; the camera thumps softly (pitch) after the kick and the snare.
No strobing: the steam moves slowly and is alpha-blended (overlapping plumes never add up), the lights fade over half a
bar, nothing near the lens is lit.

  blender.exe -b --factory-startup --python cooling_towers.py -- --variant teal --frames 0,100,300 [--pct 50]
  blender.exe -b --factory-startup --python cooling_towers.py -- --variant teal --all --seam DIR [--out DIR] [--mblur]
"""
import math
import os
import random
import sys

import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
import rx_plant as rx  # noqa: E402
from vjkit import ALARM, AMBER, CHERENKOV, COOLANT, EMBER, PLASMA, UVP  # noqa: E402

TEAL = (0.02, 0.80, 0.62)          # coolant cyan leaning toward laser green (high luma: low strengths only)

# steam: (section A, section B) colours; mouth: the hotter colour low in each plume and inside the towers' feet; rim:
# the silhouettes' edge light (A, B); sky: the faint horizon glow. steam_gain per palette (teal is high luma, UV low).
# near_y: depth of the nearest row (m); lens: focal length (mm); far: towers in the far row per period.
VARIANTS = {
    "teal": dict(steam=(TEAL, CHERENKOV), mouth=COOLANT, rim=(TEAL, CHERENKOV), sky=CHERENKOV, steam_gain=0.42,
                 cam_z=3.0, near_y=400.0, lens=26.0, far=2),
    "orange": dict(steam=(AMBER, EMBER), mouth=(1.0, 0.55, 0.06), rim=(AMBER, EMBER), sky=EMBER, steam_gain=0.4,
                   cam_z=2.0, near_y=370.0, lens=26.0, far=2),
    "purple": dict(steam=(UVP, PLASMA), mouth=PLASMA, rim=(UVP, PLASMA), sky=UVP, steam_gain=0.9,
                   cam_z=4.0, near_y=420.0, lens=26.0, far=3),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

P = 460.0                                   # m the camera travels per loop = every row's period
H = 140.0                                   # tower height (m)
R_THROAT, Z_THROAT, C_HYP = 30.0, 112.0, 89.7   # hyperboloid: r(z) = R_THROAT * sqrt(1 + ((z - Z_THROAT) / C_HYP)^2)
Z_IN = 9.0                                  # top of the air inlet (the column lattice below it)
R_MOUTH = 31.0
FLOW_T = vj.FRAMES // 3                     # 137 frames: the steam's flow cycle (divides the loop)
RISE = 90.0                                 # m the steam rises per flow cycle
PUFF_RISE = RISE * 4 * vj.FPB / FLOW_T      # m a puff rises per bar: it rides the flow (33.8 m)
BEND, SPREAD = 0.0012, 0.36                 # the plume's downwind bend (x = -BEND z^2) and widening per m of rise
SKY_Y = 4000.0                              # rig space: the sky card's distance
TAN_H = 18.0 / 26.0                         # half-width / depth at a 26 mm lens


def hyper_r(z):
    return R_THROAT * math.sqrt(1.0 + ((z - Z_THROAT) / C_HYP) ** 2)


# ------------------------------------------------------------------ music
def blink(b):
    """Aircraft light level over a bar (b = beats into the bar): a slow fade up into the downbeat and back down by the
    snare; never a step."""
    v = 0.5 + 0.5 * math.cos(2 * math.pi * b / 4.0)
    return vj.ease((v - 0.3) / 0.65)


def signals(f):
    c = vj.clock(f)
    b = c["beatpos"] - 4 * c["bar"]                                   # beats into the bar
    s = {"Kick": c["kick"], "Swell": vj.swell(f), "Section": vj.section(f), "BarPhase": b / 4.0,
         "MouthPuff": rx.bar_pulse(b / 4.0), "Blink": blink(b), "Blink2": blink((b + 2.0) % 4.0)}
    s.update(rx.flow_signals(f, FLOW_T))
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def depth_fade(s, length=1000.0):
    return s.falloff(s.dist, length)                                 # far rows sink into the night


def shell_mat():
    """Black concrete, rim-lit by the steam: neon silhouette edges, brighter toward the top."""
    s = vj.Shader("Shell")
    _, _, z = s.obj_coords()
    up = s.smooth(z, 15.0, H)
    edge = s.rim((0.45, 0.95))
    lift = s.add(0.7, s.mul(s.c("MouthPuff"), 0.25), s.mul(s.c("Swell"), 0.3), s.mul(s.c("Kick"), 0.05))
    col = s.mix(s.c("Section"), V["rim"][0], V["rim"][1])
    lit = s.add(s.mul(edge, s.madd(up, 0.75, 0.25)), s.mul(s.smooth(z, H - 30.0, H), 0.03))
    return s.emit(col, s.mul(lit, lift, depth_fade(s), 1.6 * GAIN))


def trim_mat():
    """The lip, the ring beam and the column lattice: neon tubes, bright at the top lip, dim at the foot."""
    s = vj.Shader("Trim")
    _, _, z = s.obj_coords()
    top = s.smooth(z, 60.0, H)
    lift = s.add(0.7, s.mul(s.c("MouthPuff"), 0.35), s.mul(s.c("Swell"), 0.3))
    col = s.mix(s.c("Section"), V["rim"][0], V["rim"][1])
    return s.emit(col, s.mul(s.core(0.4, 1.2), s.madd(top, 0.85, 0.12), lift, depth_fade(s), 1.5 * GAIN))


def feet_mat():
    """The lit interior seen through the column lattice: warm steam churning inside (seamless 4D noise)."""
    s = vj.Shader("Feet")
    x, y, z = s.obj_coords()
    n = s.noise4(s.vec(s.mul(x, 0.06), s.mul(y, 0.06), s.mul(s.c("LoopCos"), 0.8)), s.mul(s.c("LoopSin"), 0.8),
                 scale=1.0, detail=2.0)
    low = s.inv(s.smooth(z, 2.0, Z_IN + 1.0))
    lift = s.add(0.8, s.mul(s.c("MouthPuff"), 0.25), s.mul(s.c("Swell"), 0.25))
    return s.emit(V["mouth"], s.mul(s.madd(n, 0.5, 0.45), s.madd(low, 0.4, 0.6), lift, depth_fade(s),
                                    0.3 * GAIN))


def steam_mat():
    """One card of a plume (object space: x across, z up from the mouth; object colour R = the card's noise seed):
    a widening, downwind-bending column of rising flow noise, lit from inside (brightest at the mouth and the core),
    alpha-blended. The puff: a traveling bar pulse rising with the flow."""
    s = vj.Shader("Steam", method="BLENDED")
    x, _, z = s.obj_coords()
    seed = s.xyz(s.obj_info()[0])[0]
    zc = s.math("MAXIMUM", z, 0.0)
    dx = s.sub(x, s.mul(s.mul(zc, zc), -BEND))
    q = s.math("DIVIDE", s.math("ABSOLUTE", dx), s.madd(zc, SPREAD, R_MOUTH))
    body = s.inv(s.smooth(q, 0.4, 1.0))
    core = s.inv(s.smooth(q, 0.0, 0.85))
    span = s.mul(s.smooth(z, -2.0, 8.0), s.inv(s.smooth(z, 140.0, 330.0)))
    n = rx.flow_noise(s, dx, z, 1.0 / 70.0, 1.0 / 62.0, RISE, seed=s.mul(seed, 17.0), contrast=1.4)
    u = s.math("FRACT", s.sub(s.c("BarPhase"), s.mul(z, 1.0 / PUFF_RISE)))
    puff = s.mul(rx.pulse_shader(s, u), s.exp(s.mul(zc, -1.0 / 85.0)), s.madd(s.c("Section"), 0.35, 0.65))
    dens = s.mul(body, span, s.smooth(n, s.sub(0.22, s.mul(puff, 0.15)), 0.62))
    alpha = s.math("MINIMUM", s.mul(dens, s.madd(puff, 0.35, 0.6)), 0.9)
    glow = s.mul(s.add(s.exp(s.mul(zc, -1.0 / 55.0)), s.mul(s.exp(s.mul(zc, -1.0 / 200.0)), 0.35)),
                 s.madd(core, 0.6, 0.4), s.add(1.0, s.mul(puff, 1.4)))
    lift = s.add(1.0, s.mul(s.c("Swell"), 0.3), s.mul(s.c("Kick"), 0.04))
    col = s.mix(s.exp(s.mul(zc, -1.0 / 35.0)), s.mix(s.c("Section"), V["steam"][0], V["steam"][1]), V["mouth"])
    return s.emit_masked(alpha, col, s.mul(glow, lift, s.madd(n, 0.5, 0.6), depth_fade(s, 1400.0),
                                           V["steam_gain"] * GAIN))


def light_mat(name, signal):
    """Aircraft lights: red, fading up and down once a bar (never a step)."""
    s = vj.Shader(name)
    return s.emit(ALARM, s.mul(s.c(signal), s.core(0.6, 1.3), 7.0 * GAIN))


def plant_mat():
    """Far plant buildings (dome, stack): faint rim lines."""
    s = vj.Shader("Plant")
    _, _, z = s.obj_coords()
    col = s.mix(s.c("Section"), V["rim"][0], V["rim"][1])
    return s.emit(col, s.mul(s.rim((0.5, 0.95)), s.madd(s.smooth(z, 0.0, 60.0), 0.6, 0.4),
                             s.add(0.8, s.mul(s.c("Swell"), 0.2)), depth_fade(s), 1.1 * GAIN))


def sky_mat():
    """Rides with the camera: a faint glow along the horizon (world height), stars fixed to the card (they stay put on
    screen, as stars do; in world x they would slide with the camera's travel and break the seam)."""
    s = vj.Shader("Sky")
    x, _, zl = s.obj_coords()
    z = s.world_pos()[2]
    glow = s.exp(s.mul(s.math("MAXIMUM", z, 0.0), -1.0 / 200.0))
    vor = s.node("ShaderNodeTexVoronoi", voronoi_dimensions="2D")
    s.put(vor.inputs["Vector"], s.vec(x, zl, 0.0))
    vor.inputs["Scale"].default_value = 0.012
    rnd = s.xyz(vor.outputs["Color"])[0]
    star = s.mul(s.inv(s.smooth(vor.outputs["Distance"], 0.0, 0.06)), s.math("GREATER_THAN", rnd, 0.82),
                 s.smooth(z, 300.0, 800.0))
    return s.emit_sum([(V["sky"], s.mul(glow, 0.04 * GAIN)), ((0.75, 0.8, 1.0), s.mul(star, 0.5 * GAIN))])


# ------------------------------------------------------------------ geometry
def shell_bm():
    """The hyperboloid shell from the inlet's top to the lip (open ends, normals out)."""
    bm = bmesh.new()
    n, m = 72, 30
    rings = []
    for i in range(m + 1):
        z = Z_IN + (H - Z_IN) * i / m
        r = hyper_r(z)
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * j / n), r * math.sin(2 * math.pi * j / n), z))
                      for j in range(n)])
    for a, b in zip(rings, rings[1:]):
        for j in range(n):
            bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
    return bm


def trim_bm():
    """The lip and the inlet's ring beam (tori) and the X-braced column lattice of the air inlet."""
    bm = bmesh.new()
    rx.ring(bm, (0, 0, H), (0, 0, 1), hyper_r(H) + 0.3, 0.9, n=96, segs=8)
    rx.ring(bm, (0, 0, Z_IN), (0, 0, 1), hyper_r(Z_IN) + 0.2, 0.7, n=96, segs=6)
    n = 40
    r0, r1 = hyper_r(Z_IN) + 1.6, hyper_r(Z_IN)
    for i in range(n):
        a, d = 2 * math.pi * i / n, math.pi / n
        for s0, s1 in ((-d, d), (d, -d)):
            p0 = Vector((r0 * math.cos(a + s0), r0 * math.sin(a + s0), 0.0))
            p1 = Vector((r1 * math.cos(a + s1), r1 * math.sin(a + s1), Z_IN))
            rx.cylinder(bm, p0, p1, 0.55, segs=6, caps=False)
    return bm


def feet_bm():
    bm = bmesh.new()
    r = hyper_r(Z_IN) - 5.0
    pts = [Vector((0, 0, z)) for z in (0.0, Z_IN + 2.0)]
    vj.tube(bm, pts, lambda u: r, segs=48, cap0=False, cap1=False)
    return bm


def card_bm():
    """A plume card: x -310..150 (downwind is -x), z -12..360 above the mouth, facing -Y."""
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in ((-310, 0, -12), (150, 0, -12), (150, 0, 360), (-310, 0, 360))]
    bm.faces.new(vs)
    return bm


def dome_bm():
    bm = bmesh.new()
    vj.tube(bm, [Vector((0, 0, 0)), Vector((0, 0, 26.0))], lambda u: 34.0, segs=64, cap0=False, cap1=False)
    prof = [Vector((0, 0, 26.0 + 22.0 * math.sin(math.radians(a)))) for a in range(0, 91, 10)]
    vj.tube(bm, prof, lambda u: 34.0 * math.cos(math.radians(90.0 * u)) + 0.01, segs=64, cap0=False, cap1=False)
    rx.ring(bm, (0, 0, 26.0), (0, 0, 1), 34.3, 0.6, n=96, segs=6)
    return bm


def stack_bm():
    bm = bmesh.new()
    vj.tube(bm, [Vector((0, 0, 0)), Vector((0, 0, 175.0))], lambda u: 6.0 - 2.5 * u, segs=32, cap0=False)
    return bm


def lights_bm(pts, r):
    bm = bmesh.new()
    for p in pts:
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r, matrix=Matrix.Translation(p))
    return bm


def layout():
    """[(kind, x as a share of P, depth y, scale, cards)] for one period of the three rows."""
    ny = V["near_y"]
    out = [("tower", 0.20, ny, 1.0, 3),
           ("tower", 0.03, ny + 190.0, 0.93, 3), ("tower", 0.55, ny + 210.0, 1.0, 3),
           ("dome", 0.12, ny + 470.0, 1.0, 0), ("stack", 0.66, ny + 470.0, 1.0, 0)]
    far = [0.36, 0.87] if V["far"] == 2 else [0.30, 0.50, 0.87]
    out += [("tower", x, ny + 460.0 + 25.0 * i, 0.86, 2) for i, x in enumerate(far)]
    return out


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)

    shell_me = vj.finish_bm(shell_bm(), smooth=True, name="ShellMesh")
    trim_me = vj.finish_bm(trim_bm(), smooth=True, name="TrimMesh")
    feet_me = vj.finish_bm(feet_bm(), smooth=True, name="FeetMesh")
    card_me = vj.finish_bm(card_bm(), smooth=False, name="CardMesh")
    dome_me = vj.finish_bm(dome_bm(), smooth=True, name="DomeMesh")
    stack_me = vj.finish_bm(stack_bm(), smooth=True, name="StackMesh")
    r_top = hyper_r(H) + 0.3
    lip_pts = [Vector((r_top * math.cos(a), r_top * math.sin(a), H + 1.2)) for a in
               (math.radians(d) for d in (200, 245, 290, 335))]                         # the -y (camera) side
    tl_me = vj.finish_bm(lights_bm(lip_pts, 1.3), smooth=True, name="TowerLights")
    sl_me = vj.finish_bm(lights_bm([Vector((0, -6.0 + 2.5 * z / 175.0, z)) for z in (60.0, 118.0, 176.0)], 1.5),
                         smooth=True, name="StackLights")

    m_shell, m_trim, m_feet, m_steam = shell_mat(), trim_mat(), feet_mat(), steam_mat()
    m_plant, m_l1, m_l2 = plant_mat(), light_mat("Lights", "Blink"), light_mat("Lights2", "Blink2")
    for i, (kind, xs, y, sc, cards) in enumerate(layout()):
        x0 = xs * P
        half = TAN_H * y + 330.0 * sc                                  # the view's half-width there + plume reach
        for k in range(int(math.floor((-half - x0) / P)), int(math.ceil((P + half - x0) / P)) + 1):
            x = x0 + k * P
            tag = f"{kind}{i}_{k}"
            if kind == "tower":
                root = vj.new_empty(f"Tower{tag}")
                root.location, root.scale = (x, y, 0.0), (sc, sc, sc)
                vj.mesh_obj(f"TowerShell{tag}", shell_me, m_shell, root)
                vj.mesh_obj(f"TowerTrim{tag}", trim_me, m_trim, root)
                vj.mesh_obj(f"TowerFeet{tag}", feet_me, m_feet, root)
                vj.mesh_obj(f"TowerLights{tag}", tl_me, m_l1 if i % 2 == 0 else m_l2, root)
                for j, dy in enumerate((-22.0, 0.0, 22.0)[:cards] if cards == 3 else (-12.0, 12.0)):
                    card = vj.mesh_obj(f"Plume{tag}_{j}", card_me, m_steam)
                    card.location, card.scale = (x, y + dy * sc, H * sc), (sc, sc, sc)
                    card.color = (random.Random(100 * i + j).uniform(0.0, 1.0), 0.0, 0.0, 1.0)   # per slot
            elif kind == "dome":
                vj.mesh_obj(f"Dome{tag}", dome_me, m_plant).location = (x, y, 0.0)
            else:
                vj.mesh_obj(f"Stack{tag}", stack_me, m_plant).location = (x, y, 0.0)
                vj.mesh_obj(f"StackLights{tag}", sl_me, m_l2).location = (x, y, 0.0)

    rig = vj.new_empty("Rig")                                          # rides with the camera: ground and sky
    vj.keyed(rig, "location", [(f, (P * f / vj.FRAMES, 0.0, 0.0)) for f in (-30, vj.FRAMES + 30)])
    ground = vj.new_obj("Ground", vj.quad_bm(9000.0, 4300.0, axis="Z"), vj.black_mat("GroundBlack"), rig)
    ground.location = (0.0, 2100.0, 0.0)
    sky = vj.new_obj("Sky", vj.quad_bm(6800.0, 4000.0), sky_mat(), rig)
    sky.location = (0.0, SKY_Y, 1300.0)

    cam = vj.camera(scene, lens=V["lens"], clip=(1.0, 9000.0))
    cam.data.shift_y = 0.2
    loc, rot = [], []
    for f in vj.EXT:
        a = 2 * math.pi * f / vj.FRAMES
        loc.append((f, (P * f / vj.FRAMES, 0.0, V["cam_z"] + 0.6 * math.sin(a))))
        pitch = 0.5 * math.sin(a + 0.8) + 0.35 * vj.jolt(f)
        rot.append((f, (math.radians(90.0 + pitch), math.radians(0.5 * math.sin(2 * a + 0.3)), 0.0)))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"cooling_towers_{VNAME}")
