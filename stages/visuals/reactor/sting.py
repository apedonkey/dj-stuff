"""REACTOR STING - the REACTOR club's ID; it opens each act of the set. 4 bars, seamless, 1920x1080 @ 30 fps; tempo
from vjkit (140 BPM half-time; render with VJ_BARS=4: 206 frames, 6.87 s).

The word REACTOR in our own monoline strokes (letters.py) as neon tubes, inside a tilted core ring. Two energy packets
circle the ring in opposite directions, one lap per bar each, so they meet at the ring's front (bottom) on every kick
and at its back (top) on every snare; their light ripples along the nameplate from its middle and back.
  Downbeat     everything lands at once: the ring closes under the meeting packets, the strokes finish drawing, the
               swell peaks (no flash) and the camera thumps a frame later.
  Bars 1-3     the nameplate holds, breathing into the kick and the snare; the camera eases back.
  Bar 4        power cycle. Beats 1-2: the packets wipe the ring from the bottom up, and each letter's strokes drain
               out of their ends as a packet passes beneath it (from the middle outward). Beats 3-4: the core ring
               sweeps back in, redrawn from the top down behind the packets while the camera pushes in; each letter
               re-ignites as a packet passes over it and draws itself out with a hot head, all of them finishing
               exactly on the next downbeat (the loop's seam).
No strobing: the landing is a swell, the wipes follow the packets, the drains take most of a beat.
Variants: amber (amber nameplate, Cherenkov ring), blue (Cherenkov nameplate, coolant ring, from a little above),
red (alarm-red nameplate, amber ring, from a little below).

  VJ_BARS=4 blender.exe -b --factory-startup --python sting.py -- --variant amber --frames 0,30,170,190 [--pct 50]
  VJ_BARS=4 blender.exe -b --factory-startup --python sting.py -- --variant blue --all --seam DIR [--out DIR]
"""
import math
import os
import sys

import bmesh
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
import rx_sting as rx  # noqa: E402
from vjkit import ALARM, AMBER, CHERENKOV, COOLANT  # noqa: E402

# word: tube color, white-hot core line color, gain; ring: color, core, gain; packet: hot color; glow: back glow color
# and gain; tilt: the ring's tilt (deg, front edge down); bank: its roll about the view axis; elev: camera elevation
# (deg, + = above); sway: camera drift (x, z m); roll: camera roll drift (deg)
VARIANTS = {
    "amber": dict(word=AMBER, word_core=(1.0, 0.78, 0.45), word_gain=0.85, ring=CHERENKOV, ring_core=(0.45, 0.75, 1.0),
                  ring_gain=1.0, packet=(0.7, 0.88, 1.0), glow=CHERENKOV, glow_gain=1.0,
                  tilt=24.0, bank=0.0, elev=0.0, sway=(0.35, 0.2), roll=0.4),
    "blue": dict(word=CHERENKOV, word_core=(0.55, 0.82, 1.0), word_gain=0.95, ring=COOLANT, ring_core=(0.6, 0.95, 1.0),
                 ring_gain=0.7, packet=(0.85, 0.95, 1.0), glow=(0.03, 0.2, 1.0), glow_gain=1.0,
                 tilt=21.0, bank=-6.0, elev=3.0, sway=(0.5, 0.25), roll=0.6),
    "red": dict(word=ALARM, word_core=(1.0, 0.32, 0.18), word_gain=1.3, ring=AMBER, ring_core=(1.0, 0.75, 0.4),
                ring_gain=0.9, packet=(1.0, 0.8, 0.5), glow=(1.0, 0.06, 0.01), glow_gain=0.9,
                tilt=26.0, bank=5.0, elev=-2.0, sway=(0.35, 0.2), roll=1.2),
}
VNAME, V = vj.variant(VARIANTS)
GAIN = float(vj.arg("--gain", 1.0))

HL, TRACK, R_STROKE = 1.75, 0.22, 0.074        # letter height, tracking (in letter heights), tube radius (m)
R_RING, RING_TUBE, RING_Z = 5.9, 0.06, 0.54    # core ring radius, tube radius, center height (centers its ellipse
                                               # on the word: the near half projects bigger than the far half)
LENS, CAM_D, DOLLY = 60.0, 24.0, 1.2           # camera lens (mm), distance (m), ease-back over the hold (m)
ERASE_P = 0.19                                 # a letter drains over this share of the last bar (0.75 beats)
EDGE = 0.02                                    # soft edge of the ring wipe (share of a half turn)
HEAD_W, TAIL_L = 0.11, 0.55                    # packet head width and tail length (rad)
RIPPLE_FADE = 2.6                              # m: a packet's ripple on the nameplate fades as it leaves the middle
HOLD_BARS = vj.BARS - 1                        # the last bar is the power cycle


# ------------------------------------------------------------------ timing (all periodic over the loop)
def bars_t(f):
    """Continuous time in bars (0..BARS): the packets' clock, one lap per bar at constant speed."""
    return vj.BARS * (f % vj.FRAMES) / vj.FRAMES


def cycle_p(f):
    """None during the hold, else 0..1 through the last bar (the power cycle)."""
    t = bars_t(f)
    return None if t < HOLD_BARS else t - HOLD_BARS


def theta(f):
    """Packet A's angle (rad, 0..2pi) from the ring's front point; packet B sits at -theta."""
    return 2 * math.pi * (bars_t(f) % 1.0)


def cut(f):
    """The ring wipe: during the power cycle the ring shows where |angle| / pi >= cut (the packets' own |angle|), so it
    is wiped bottom-up behind them (cut 0 -> 1) and redrawn top-down (1 -> 0); 0 = the whole ring."""
    p = cycle_p(f)
    return 0.0 if p is None else 2.0 * min(p, 1.0 - p)


def held(f):
    """1 while the nameplate holds; eases out at the start of the power cycle and back in for the landing."""
    p = cycle_p(f)
    if p is None:
        return 1.0
    return max(1.0 - vj.ease(p / 0.15), vj.ease((p - 0.85) / 0.15))


def swell(f):
    """The landing: rises over the last two beats, peaks on the downbeat, decays over ~1.5 beats."""
    p = cycle_p(f)
    if p is not None and p >= 0.5:
        return ((p - 0.5) / 0.5) ** 2
    return math.exp(-4.0 * bars_t(f) / 1.5)


def breath(f):
    """A smooth half-time breath: rises over the last quarter of each accent interval into the accent (the kick 1.0,
    the snare 0.85), falls slowly after (Giant Halo's, no hard edge on the beat)."""
    c = vj.clock(f)
    amp = 0.85 if c["snare"] else 1.0
    nxt = 0.85 if vj.HALFTIME and ((c["acc"] + 1) * vj.ACC) % 4 == 2 else 1.0
    return max(amp * math.exp(-2.5 * c["aph"]), nxt * vj.ease((c["aph"] - 0.75) / 0.25))


def ring_scale(f):
    """The ring breathes out a little while it is wiped and sweeps back in as it is redrawn."""
    p = cycle_p(f)
    return 1.0 if p is None else 1.0 + 0.02 * math.sin(math.pi * p) ** 2


def dolly(f):
    """0..1 camera ease-back: out slowly over the hold, in over the power cycle, at rest on the downbeat."""
    p = cycle_p(f)
    return vj.ease(bars_t(f) / HOLD_BARS) if p is None else 1.0 - vj.ease(p)


# ------------------------------------------------------------------ camera and ring poses
AIM = Vector((0.0, 0.0, 0.0))


def cam_pose(f, base=False):
    a = 2 * math.pi * (f % vj.FRAMES) / vj.FRAMES
    e = math.radians(V["elev"])
    d = CAM_D + (0.0 if base else DOLLY * dolly(f))
    p = AIM + Vector((0.0, -math.cos(e), math.sin(e))) * d
    roll = 0.0
    if not base:
        sx, sz = V["sway"]
        p += Vector((sx * math.sin(a), 0.0, sz * math.sin(2 * a + 0.4) + 0.07 * vj.jolt(f) * held(f)))
        roll = V["roll"] * math.sin(a + 0.9)
    return p, vj.look_at(p, AIM, roll=roll)


def ring_matrix(f):
    rot = Euler((math.radians(V["tilt"]), math.radians(V["bank"]), 0.0), "XYZ")
    return Matrix.Translation((0.0, 0.0, RING_Z)) @ rot.to_matrix().to_4x4() @ Matrix.Scale(ring_scale(f), 4)


def ring_point(alpha, m=None):
    """World point of the ring at angle alpha (0 = front, +pi/2 = right in the ring's own frame)."""
    m = m or ring_matrix(0)
    return m @ Vector((R_RING * math.sin(alpha), -R_RING * math.cos(alpha), 0.0))


def letter_times(xc):
    """(p_off, p_on) of a letter centred at frame x = xc: the first moment in the power cycle a packet passes beneath
    it (wipe phase, p < 0.5) and over it (redraw phase, p >= 0.5), from where the base camera sees them."""
    cam, rot = cam_pose(0, base=True)
    m = ring_matrix(0)

    def px(alpha):
        return rx.project(cam, rot, LENS, ring_point(alpha, m))[0]

    def first(p0, p1, n=400):
        """The first p in [p0, p1] where either packet's frame x crosses xc."""
        prev = None
        for i in range(n + 1):
            p = p0 + (p1 - p0) * i / n
            ds = (px(2 * math.pi * p) - xc, px(-2 * math.pi * p) - xc)
            if prev is None:
                if min(abs(d) for d in ds) < 1.0:
                    return p
            elif any((a <= 0 < b) or (b <= 0 < a) for a, b in zip(prev, ds)):
                return p
            prev = ds
        return None
    off = first(0.0, 0.5)
    on = first(0.5, 1.0)
    return (off if off is not None else 0.25), (on if on is not None else 0.75)


def letter_state(f, p_off, p_on):
    """(reveal, erase, head glow, drain glow) of a letter: Object.color, read by the word shader."""
    p = cycle_p(f)
    if p is None or p < p_off:
        return 1.0, 0.0, 0.0, 0.0
    if p < p_on:
        e = vj.ease(min(1.0, (p - p_off) / ERASE_P))
        return 1.0, e, 0.0, math.sin(math.pi * e)
    r = rx.fly_in((p - p_on) / (1.0 - p_on), pa=0.12, pb=0.55)
    return r, 0.0, math.sin(math.pi * r) ** 0.7, 0.0


def packet_x(f, sign):
    """Where packet A (sign +1) or B (-1) sits across the word, in word-plane meters (its ray through the y = 0
    plane), for the packets' ripple along the nameplate."""
    cam, _ = cam_pose(f, base=True)
    p = ring_point(sign * theta(f), ring_matrix(f))
    k = (0.0 - cam.y) / (p.y - cam.y)
    return cam.x + (p.x - cam.x) * k


def signals(f):
    xa, xb = packet_x(f, 1), packet_x(f, -1)
    s = {"Swell": swell(f), "Breath": breath(f) * held(f), "Theta": theta(f), "Cut": cut(f) * (1 + EDGE) - EDGE,
         "PkA": xa, "PkB": xb, "RipA": math.exp(-abs(xa) / RIPPLE_FADE), "RipB": math.exp(-abs(xb) / RIPPLE_FADE)}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def word_mat():
    """Opaque neon tubes drawn on and erased by the per-letter Object.color (reveal, erase, head glow) and alpha (drain
    glow); transparent where not drawn. Each packet's light ripples along it in x, strongest where they meet (the
    middle, on the accents) and fading as they part, so the nameplate's light crests on the kick and the snare (with
    an even ripple, two bands on the outer letters outshone one on the C and the light peaked between accents)."""
    s = vj.Shader("Word")
    col, drain, _ = s.obj_info()
    rv, er, hd = s.xyz(col)
    u = s.node("ShaderNodeAttribute", attribute_name="u").outputs["Fac"]
    slen = s.node("ShaderNodeAttribute", attribute_name="slen").outputs["Fac"]
    w = 0.03
    m_r = s.inv(s.smooth(u, s.madd(rv, 1 + w, -w), s.mul(rv, 1 + w)))
    m_e = s.smooth(u, s.madd(er, 1 + w, -w), s.mul(er, 1 + w))
    vis = s.mul(m_r, m_e)
    head = s.mul(s.gauss(s.mul(s.sub(u, s.madd(rv, 1 + w, -w / 2)), slen), 0.0, 0.16), hd)
    dglow = s.mul(s.gauss(s.mul(s.sub(u, s.madd(er, 1 + w, -w / 2)), slen), 0.0, 0.3), drain)
    x, _, _ = s.world_pos()
    ripple = s.add(s.mul(s.gauss(x, s.c("PkA"), 1.1), s.c("RipA")), s.mul(s.gauss(x, s.c("PkB"), 1.1), s.c("RipB")))
    lift = s.add(0.62, s.mul(s.c("Breath"), 0.18), s.mul(s.c("Swell"), 0.45), s.mul(ripple, 0.45))
    hot = s.add(head, s.mul(dglow, 0.6))
    c = s.mix(s.mul(s.smooth(s.core(0.0, 1.0), 0.8, 1.0), 0.35), V["word"], V["word_core"])
    c = s.mix(s.math("MINIMUM", s.add(s.mul(ripple, 0.18), s.mul(hot, 0.8)), 0.85), c, V["word_core"])
    strength = s.mul(s.add(s.mul(vis, lift), s.mul(hot, 1.6)), s.core(), V["word_gain"] * GAIN)
    return s.emit_masked(s.math("MAXIMUM", vis, s.math("MINIMUM", s.mul(hot, 2.0), 1.0)), c, strength)


def ring_mat(name, gain, head_gain, tail_gain, base):
    """Additive core ring (and its ticks): wiped by Cut around the ring's own angle; two packets at +-Theta with tails
    behind them. The heads always show, the tails only on the drawn ring (unmasked tails left a ghost ring in the
    wipe), so the packets eat the ring on the way up and draw it on the way down."""
    s = vj.Shader(name)
    lx, ly, _ = s.obj_coords()
    ang = s.math("ARCTAN2", lx, s.mul(ly, -1.0))                       # 0 at the front point, +pi/2 on the right
    xn = s.math("DIVIDE", s.math("ABSOLUTE", ang), math.pi)
    vis = s.smooth(xn, s.c("Cut"), s.add(s.c("Cut"), EDGE))
    th = s.c("Theta")
    behind_a = s.math("WRAP", s.sub(th, ang), 2 * math.pi, 0.0)        # rad behind packet A (moving to +angle)
    behind_b = s.math("WRAP", s.add(ang, th), 2 * math.pi, 0.0)        # rad behind packet B (at -theta, to -angle)

    def head(d):
        return s.gauss(s.math("MINIMUM", d, s.sub(2 * math.pi, d)), 0.0, HEAD_W)
    hd = s.add(head(behind_a), head(behind_b))
    tl = s.add(s.falloff(behind_a, TAIL_L), s.falloff(behind_b, TAIL_L))
    hot = s.add(s.mul(hd, head_gain), s.mul(tl, tail_gain, vis))
    lift = s.add(0.62, s.mul(s.c("Breath"), 0.15), s.mul(s.c("Swell"), 0.45))
    c = s.mix(s.mul(s.smooth(s.core(0.0, 1.0), 0.8, 1.0), 0.3), V["ring"], V["ring_core"])
    c = s.mix(s.math("MINIMUM", s.mul(hot, 0.5), 0.9), c, V["packet"])
    strength = s.mul(s.add(s.mul(vis, lift, base), hot), s.core(), gain * GAIN)
    mat = s.additive(c, strength)
    mat.use_backface_culling = True
    return mat


def glow_mat():
    """A soft glow behind the nameplate (additive): the core's light, shimmering slowly (4D noise round the loop)."""
    s = vj.Shader("Backglow")
    x, _, z = s.obj_coords()
    core = s.mul(s.gauss(x, 0.0, 4.6), s.gauss(z, 0.0, 1.9))
    haze = s.mul(s.gauss(x, 0.0, 9.0), s.gauss(z, 0.0, 4.2))
    n = s.noise4(s.vec(s.mul(x, 0.18), s.add(s.mul(z, 0.3), s.mul(s.c("LoopCos"), 0.35)), s.mul(s.c("LoopSin"), 0.35)),
                 s.mul(s.c("LoopCos"), 0.2), scale=1.3, detail=3.0, rough=0.55)
    shimmer = s.madd(s.smooth(n, 0.3, 0.75), 0.4, 0.75)
    lift = s.add(0.8, s.mul(s.c("Swell"), 0.4), s.mul(s.c("Breath"), 0.08))
    return s.additive(V["glow"], s.mul(s.add(s.mul(core, 0.065), s.mul(haze, 0.016)), shimmer, lift,
                                       V["glow_gain"] * GAIN))


# ------------------------------------------------------------------ geometry
def ring_bm():
    bm = bmesh.new()
    pts = [Vector((R_RING * math.sin(a), -R_RING * math.cos(a), 0.0))
           for a in (2 * math.pi * i / 256 for i in range(256))]
    vj.tube(bm, pts, lambda u: RING_TUBE, segs=10, closed=True)
    return bm


def ticks_bm(n=72):
    """Short radial ticks just outside the ring (a gauge), every 6th one longer."""
    bm = bmesh.new()
    for i in range(n):
        a = 2 * math.pi * i / n
        d = Vector((math.sin(a), -math.cos(a), 0.0))
        r0, r1 = R_RING + 0.14, R_RING + (0.40 if i % 6 == 0 else 0.28)
        vj.tube(bm, [d * r0, d * ((r0 + r1) / 2), d * r1], lambda u: 0.024, segs=6)
    return bm


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT

    word_m = word_mat()
    for i, (ch, strokes) in enumerate(rx.word_strokes("REACTOR", HL, 0.0, TRACK)):
        bm = bmesh.new()
        for st in strokes:
            rx.stroke_tube(bm, st, R_STROKE, segs=10)
        ob = vj.new_obj(f"Word{i}{ch}", bm, word_m)
        ob.data.shade_smooth()
        xs = [p.x for st in strokes for p in st]
        cam, rot = cam_pose(0, base=True)
        xc = rx.project(cam, rot, LENS, Vector(((min(xs) + max(xs)) / 2, 0.0, 0.0)))[0]
        p_off, p_on = letter_times(xc)
        vj.log(f"letter {ch}: drains at p {p_off:.3f}, re-ignites at p {p_on:.3f} of the last bar")
        vj.keyed(ob, "color", [(f, letter_state(f, p_off, p_on)) for f in ext])

    ring_keys = []
    for f in ext:
        m = ring_matrix(f)
        ring_keys.append((f, m))
    rot = (math.radians(V["tilt"]), math.radians(V["bank"]), 0.0)
    for name, bm, mat in (("Ring", ring_bm(), ring_mat("Ring", V["ring_gain"], 2.6, 0.8, 1.0)),
                          ("Ticks", ticks_bm(), ring_mat("Ticks", V["ring_gain"], 1.6, 0.5, 0.28))):
        ob = vj.new_obj(name, bm, mat)
        ob.data.shade_smooth()
        ob.location = (0.0, 0.0, RING_Z)
        ob.rotation_euler = rot
        vj.keyed(ob, "scale", [(f, (ring_scale(f),) * 3) for f in ext])

    halo_m = rx.soft_glow_mat("PacketHalo", V["packet"], 0.35 * GAIN, power=3.0, lift_key="Swell", lift_amt=0.3)
    for name, sign in (("PacketA", 1), ("PacketB", -1)):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=0.42)
        ob = vj.new_obj(name, bm, halo_m)
        ob.data.shade_smooth()
        vj.keyed(ob, "location", [(f, tuple(ring_point(sign * theta(f), m))) for f, m in ring_keys])

    glow = vj.new_obj("Backglow", vj.quad_bm(30.0, 14.0), glow_mat())
    glow.location = (0.0, 2.0, 0.0)

    cam = vj.camera(scene, lens=LENS, clip=(0.5, 200.0))
    poses = [(f, cam_pose(f)) for f in ext]
    vj.keyed(cam, "location", [(f, tuple(p)) for f, (p, _) in poses])
    vj.keyed(cam, "rotation_euler", [(f, tuple(r)) for f, (_, r) in poses])
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"sting_{VNAME}")
