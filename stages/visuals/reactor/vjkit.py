"""Shared kit for the REACTOR club VJ loops (Tribe XR, the club's 16 x 9 m core window): Blender 4.5 headless, EEVEE
Next.

Copied from the GRAVEYARD SHIFT pack (TribeUE/Visuals/halloween/scripts/vjkit.py, itself adapted from the Dino pack;
neither is edited from here) on 2026-10-09 and given the club's palette (claudedocs/club_venue_plan.md, tribe hack
repo). The Reactor screen shows the WHOLE 16:9 frame, so the middle-90% safe area applies as on Halloween. Kept from
the Halloween kit: a configurable loop length (the sting is 4 bars), fast keying, per-object materials,
swell/section envelopes, rim-lit silhouettes.

Music grid: 140 BPM half-time dubstep (--bpm N or env VJ_BPM; --straight or env VJ_HALFTIME=0 for 4-on-the-floor),
30 fps -> a beat is 12.857 frames, a bar 51.43. A loop is BARS bars (--bars N or env VJ_BARS, default 8): 8 bars =
32 beats = 411.43 frames, rounded to FRAMES = 411 (13.70 s); 4 bars = 205.71 -> 206 frames (6.87 s). Beat k lands on
frame BEAT_F[k] = floor(k * FPB + 0.5); a loop renders frames 0..FRAMES-1 and frame FRAMES equals frame 0.
Accents: half-time puts them on the kick (beat 1) and the snare (beat 3), ACC = 2 beats apart; straight, every beat.
Scene scripts take all timing from FPB / BEAT_F / FRAMES / ACC (never a hard-coded frame count) and key beat pulses
from the accent clock (clock()["kick"], ["aph"], ["acc"]).

Every loop script imports this module, builds its scene and calls finish(). Shared pieces:
  clock(f)            per-frame musical signals (kick envelope, beat phase, bar, accent index/phase, loop phase)
  build_clock(keys)   a shader node group "VJClock" whose Value nodes are keyed per frame: every material reads the
                      same musical clock (one source of truth for beat sync)
  Shader              tiny node-graph builder (math chains, mixes, emission, additive light, rims, ramps, 4D noise)
  tube / horn         swept tubes and curved horns (from TribeXR/Scripts/Blender/dino_stage.py, our stage generator)
  animate / keyed     key any RNA property for a list of (frame, value); keyed() writes all keys in one pass
  swell / section     the fill into each 4-bar hit and the A/B section switch (a palette morph lands on the hit)
  setup_render()      EEVEE Next + one tight compositor Bloom, Standard view, 1920x1080 @ 30 fps, PNG frames
  variant()           picks the --variant entry of a loop's VARIANTS table
  finish()            --all / --frames / --out / --seam (frame FRAMES in the same session) / --safe PREFIX report
"""
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

# ------------------------------------------------------------------ CLI (after "--")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


def flag(name):
    return name in ARGS


# ------------------------------------------------------------------ music grid
FPS = 30
BARS = int(arg("--bars", os.environ.get("VJ_BARS", 8)))
BPM = float(arg("--bpm", os.environ.get("VJ_BPM", 140)))
HALFTIME = not flag("--straight") and (flag("--halftime") or os.environ.get("VJ_HALFTIME", "1") == "1")
ACC = 2 if HALFTIME else 1                                        # beats between accents (kick, snare)
BEATS = BARS * 4
FPB = FPS * 60.0 / BPM                                            # frames per beat: 12.857 at 140 BPM
FRAMES = int(round(BEATS * FPB))                                  # 411 at 140 BPM, 8 bars (206 for 4 bars)
BEAT_F = [int(math.floor(k * FPB + 0.5)) for k in range(BEATS)] + [FRAMES]   # nearest frame of each beat
assert all(a < b for a, b in zip(BEAT_F, BEAT_F[1:]))
HALF = BEATS // 2                                                 # first beat of the second half (section B)

# ------------------------------------------------------------------ palette (linear emission colors)
# The club's palette (club_venue_plan.md section 2: Cherenkov blue and hazard amber carry the look; alarm red and laser
# green are accents) tuned for emission under the Standard view transform, which clips each channel on its own: keep
# green/blue low in the reds and ambers so a bright core keeps its hue, and use the high-luma colours (coolant cyan,
# laser green, steel) as lines, never as big shapes.
CHERENKOV = (0.08, 0.40, 1.0)     # Cherenkov blue: the core's glow, carries the look
COOLANT = (0.05, 0.85, 1.0)       # coolant cyan: high luma, lines only
AMBER = (1.0, 0.45, 0.03)         # hazard amber: carries the look (stripes, heat, warnings)
EMBER = (1.0, 0.12, 0.006)        # deep orange-red (molten fuel, embers)
ALARM = (1.0, 0.03, 0.015)        # alarm red: beacons, SCRAM, warnings (accent)
LASER = (0.10, 1.0, 0.18)         # laser green: lines only (accent)
UVP = (0.28, 0.0, 1.0)            # UV purple
PLASMA = (1.0, 0.08, 0.55)        # plasma magenta (fusion, particle streams)
STEEL = (0.40, 0.46, 0.55)        # steel white (dim): structure, rims
HOT = (1.0, 0.70, 0.35)           # white-hot fuel: small shapes only
WHITE = (1.0, 1.0, 1.0)


def log(msg):
    print("[VJ] " + msg, flush=True)


def variant(variants):
    """(name, settings) of the --variant entry in a loop's VARIANTS table (default: its first entry)."""
    name = arg("--variant", next(iter(variants)))
    if name not in variants:
        raise SystemExit(f"unknown --variant {name!r}; choose one of: {', '.join(variants)}")
    return name, variants[name]


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def clock(f):
    """Musical state at frame f (any integer; periodic with FRAMES)."""
    f %= FRAMES
    k = max(i for i in range(BEATS) if BEAT_F[i] <= f)            # current beat
    f0, f1 = BEAT_F[k], BEAT_F[k + 1]
    ph = (f - f0) / (f1 - f0)                                    # 0 on the beat frame -> 1
    bar, beat = divmod(k, 4)
    hat_f = int(math.floor((k + 0.5) * FPB + 0.5))               # the offbeat ("and")
    eighth_f = f0 if f < hat_f else hat_f
    a = k - k % ACC                                               # beat of the current accent
    aph = (f - BEAT_F[a]) / (BEAT_F[a + ACC] - BEAT_F[a])         # 0 on the accent frame -> 1 at the next accent
    if HALFTIME:                                                  # kick on beat 1, snare on beat 3, each decaying
        kick = (1.0 if a % 4 == 0 else 0.85) * math.exp(-5.0 * aph)   # over its half bar
    else:
        kick = math.exp(-6.0 * ph)
    return {
        "f": f, "k": k, "ph": ph, "bar": bar, "beat": beat,
        "kick": kick, "acc": a // ACC, "aph": aph, "snare": HALFTIME and a % 4 == 2,
        "hat": math.exp(-(f - hat_f) / 1.6) if f >= hat_f else 0.0,
        "pulse8": math.exp(-(f - eighth_f) / 1.8),                # 8th-note envelope (beat + offbeat)
        "beatpos": k + ph,                                        # continuous beat count 0..BEATS
        "loop": f / FRAMES,                                       # 0..1 over the loop
    }


def beatpos(f):
    """Continuous beat position for any integer frame (not wrapped): BEATS per loop."""
    n, ff = divmod(f, FRAMES)
    return n * BEATS + clock(ff)["beatpos"]


def beat_frame(k):
    """Frame of absolute beat k (any integer; BEATS beats per loop)."""
    n, kk = divmod(k, BEATS)
    return n * FRAMES + BEAT_F[kk]


def accent_frames():
    """Frames of the accents in one loop (half-time: kick and snare), with their strength (kick 1.0, snare 0.85)."""
    return [(BEAT_F[k], 1.0 if k % 4 == 0 or not HALFTIME else 0.85) for k in range(0, BEATS, ACC)]


def jolt(f, decay=3.0, period=5.0, delay=1):
    """Half-time weight as motion, not light: a damped jolt after each accent (the kick 1.0, the snare 0.85) that
    starts `delay` frames after the accent frame (a jolt on the very impact frame throws freshly lit geometry across a
    region edge and back: a one-frame hit). Sums the tails of the previous accents. Scale it into a camera's pitch or
    height. Periodic over the loop."""
    v = 0.0
    for af, amp in accent_frames():
        t = (f - af - delay) % FRAMES
        if t < 6 * decay:
            v += amp * math.exp(-t / decay) * math.sin(2 * math.pi * t / period)
    return v


# ------------------------------------------------------------------ shared envelopes (4-bar sections)
def since_hit(f):
    """Frames since the last section hit: the downbeats of beat 0 and beat HALF (cyclic)."""
    f %= FRAMES
    return f - BEAT_F[HALF] if f >= BEAT_F[HALF] else f


def swell(f, beats_in=2, decay_beats=1.0):
    """The fill: eases in over the last `beats_in` beats before each section hit (beat 0 and beat HALF), peaks at 1 on
    the hit, then decays over about `decay_beats` beats. A crescendo into the hit, no frame-to-frame flashing."""
    f %= FRAMES
    for hit in (HALF, BEATS):
        f0, f1 = BEAT_F[hit - beats_in], BEAT_F[hit]
        if f0 <= f < f1:
            return ((f - f0) / (f1 - f0)) ** 2
    return math.exp(-since_hit(f) / (decay_beats * FPB))


def section(f, morph=8):
    """0 = section A (first half), 1 = section B (second half). Over the last `morph` frames before each hit the value
    morphs into the next section's, so a new palette lands complete on the hit (a morph after the hit pushes the
    brightness peak past the downbeat)."""
    f %= FRAMES
    nxt = BEAT_F[HALF] if f < BEAT_F[HALF] else FRAMES
    cur = 0.0 if f < BEAT_F[HALF] else 1.0
    x = ease((f - (nxt - morph)) / morph) if f >= nxt - morph else 0.0
    return cur + (1.0 - 2.0 * cur) * x


def loop_signals(f):
    """LoopCos / LoopSin: a circle walked once per loop (seamless 4D noise), plus Loop2Cos / Loop2Sin twice."""
    a = 2 * math.pi * (f % FRAMES) / FRAMES
    return {"LoopCos": math.cos(a), "LoopSin": math.sin(a), "Loop2Cos": math.cos(2 * a), "Loop2Sin": math.sin(2 * a)}


# ------------------------------------------------------------------ scene basics
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    world = bpy.data.worlds.new("Black")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0, 0, 0, 1)
    bg.inputs["Strength"].default_value = 0.0
    scene.world = world
    return scene


def new_obj(name, bm, mat=None, parent=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat is not None:
        me.materials.append(mat)
    if parent is not None:
        ob.parent = parent
    return ob


def new_empty(name, parent=None):
    ob = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    return ob


def finish_bm(bm, smooth=True, name="m"):
    """bmesh -> mesh data (to share between objects)."""
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    return me


def mesh_obj(name, me, mat=None, parent=None):
    """Object on (possibly shared) mesh data; its material is linked to the object, so objects sharing a mesh can
    differ (a mesh-level material would silently stay the first object's)."""
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat is not None:
        if not me.materials:
            me.materials.append(mat)
        ob.material_slots[0].link = "OBJECT"
        ob.material_slots[0].material = mat
    ob.parent = parent
    return ob


def camera(scene, lens=35.0, clip=(0.1, 1000.0), name="Cam"):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens, cam_data.sensor_width, cam_data.sensor_fit = lens, 36.0, "HORIZONTAL"
    cam_data.clip_start, cam_data.clip_end = clip
    cam = bpy.data.objects.new(name, cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def look_at(src, dst, roll=0.0):
    """Euler rotation for a camera at src looking at dst (Z up), rolled `roll` degrees about its view axis."""
    q = (Vector(dst) - Vector(src)).to_track_quat("-Z", "Y")
    if roll:
        q = q @ Matrix.Rotation(math.radians(roll), 4, "Z").to_quaternion()
    return q.to_euler()


# ------------------------------------------------------------------ geometry (tube/horn: dino_stage.py)
def tube(bm, pts, radius_fn, segs=12, cap0=True, tip=False, closed=False, cap1=True):
    """Swept tube along polyline pts; radius_fn(u), u in [0,1]; parallel-transported frame. closed: ring."""
    n = len(pts)
    tans = []
    for i in range(n):
        if closed:
            a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        else:
            a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
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
        r = radius_fn(i / (n - 1))
        rings.append([bm.verts.new(pts[i] + (nrm * math.cos(2 * math.pi * j / segs)
                                             + bin_ * math.sin(2 * math.pi * j / segs)) * r) for j in range(segs)])
    for i in range(n if closed else n - 1):
        a, c = rings[i], rings[(i + 1) % n]
        for j in range(segs):
            bm.faces.new((a[j], a[(j + 1) % segs], c[(j + 1) % segs], c[j]))
    if closed:
        return
    if cap0:
        bm.faces.new(list(reversed(rings[0])))
    if tip:
        apex = bm.verts.new(pts[-1] + tans[-1] * (radius_fn(1.0) * 2 + 0.05))
        last = rings[-1]
        for j in range(segs):
            bm.faces.new((last[j], last[(j + 1) % segs], apex))
    elif cap1:
        bm.faces.new(rings[-1])


def curved_path(base, direction, length, bend_axis, bend_deg, steps):
    pts, d, pos = [], direction.normalized(), base.copy()
    rot = Matrix.Rotation(math.radians(bend_deg) / steps, 3, bend_axis.normalized())
    for _ in range(steps + 1):
        pts.append(pos.copy())
        pos = pos + d * (length / steps)
        d = (rot @ d).normalized()
    return pts


def horn(bm, base, direction, length, r0, bend_axis, bend_deg, segs=10, steps=18):
    pts = curved_path(base, direction, length, bend_axis, bend_deg, steps)
    tube(bm, pts, lambda u: r0 * max(1 - u, 0.0) ** 0.85 + 0.02, segs=segs, tip=True)


def catmull(ctrl, per=8, closed=False):
    """Catmull-Rom through ctrl (Vectors), per samples per span; ends clamped (or a closed loop)."""
    if closed:
        P = [ctrl[-1]] + list(ctrl) + [ctrl[0], ctrl[1]]
    else:
        P = [ctrl[0]] + list(ctrl) + [ctrl[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for s in range(per):
            t = s / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    if not closed:
        out.append(ctrl[-1].copy())
    return out


def circle_pts(center, radius, n, axis="Y"):
    """n points on a circle around `center`; axis "Y": in the XZ plane (facing a camera on -Y), "Z": in XY."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s = math.cos(a) * radius, math.sin(a) * radius
        pts.append(center + (Vector((c, 0, s)) if axis == "Y" else Vector((c, s, 0))))
    return pts


def disc_bm(radius, n=96, axis="Y"):
    """A flat disc; axis "Y": in the XZ plane with its normal toward -Y (a camera on -Y sees its front); "Z": XY."""
    import bmesh
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in circle_pts(Vector((0, 0, 0)), radius, n, axis)]
    bm.faces.new(list(reversed(vs)) if axis == "Y" else vs)
    return bm


def quad_bm(w, h, axis="Y"):
    """A w x h rectangle centered on the origin; axis "Y": in XZ facing -Y; "Z": in XY facing +Z."""
    import bmesh
    bm = bmesh.new()
    if axis == "Y":
        pts = [(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)]
    else:
        pts = [(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)]
    bm.faces.new([bm.verts.new(p) for p in pts])
    return bm


# ------------------------------------------------------------------ animation
def fcurves_of(id_data):
    act = id_data.animation_data.action
    try:
        return list(act.fcurves)
    except AttributeError:                                       # slotted-action API only
        slot = id_data.animation_data.action_slot
        return list(act.layers[0].strips[0].channelbag(slot).fcurves)


def animate(owner, prop, frame_values, interp="CONSTANT"):
    """Key owner.prop at every (frame, value); value is a float or a sequence for vector props."""
    f0, v0 = frame_values[0]
    setattr(owner, prop, v0)
    owner.keyframe_insert(prop, frame=f0)
    path = owner.path_from_id(prop)
    for fc in fcurves_of(owner.id_data):
        if fc.data_path != path:
            continue
        i = fc.array_index
        for f, v in frame_values[1:]:
            fc.keyframe_points.insert(f, v[i] if isinstance(v, (tuple, list, Vector)) else v, options={"FAST"})
        for kp in fc.keyframe_points:
            kp.interpolation = interp
        fc.update()


def keyed(owner, prop, frame_values, interp="LINEAR"):
    """Key owner.prop at every (frame, value) in one pass per F-curve (fast for hundreds of objects)."""
    f0, v0 = frame_values[0]
    setattr(owner, prop, v0)
    owner.keyframe_insert(prop, frame=f0)
    path = owner.path_from_id(prop)
    for fc in fcurves_of(owner.id_data):
        if fc.data_path != path:
            continue
        i = fc.array_index
        kp = fc.keyframe_points
        kp.add(len(frame_values) - 1)
        co = []
        for f, v in frame_values:
            co += [f, v[i] if isinstance(v, (tuple, list, Vector)) else v]
        kp.foreach_set("co", co)
        for p in kp:
            p.interpolation = interp
        fc.update()


EXT = list(range(-2, FRAMES + 3))                                 # transform keys: motion blur samples past the ends


# ------------------------------------------------------------------ shader building
CLOCK = None


def build_clock(series):
    """series: {name: [value per frame 0..FRAMES]}; makes the VJClock node group, keyed per frame."""
    global CLOCK
    ng = bpy.data.node_groups.new("VJClock", "ShaderNodeTree")
    out = ng.nodes.new("NodeGroupOutput")
    for i, (name, vals) in enumerate(series.items()):
        ng.interface.new_socket(name, in_out="OUTPUT", socket_type="NodeSocketFloat")
        v = ng.nodes.new("ShaderNodeValue")
        v.name = v.label = name
        v.location = (0, -80 * i)
        ng.links.new(v.outputs[0], out.inputs[name])
        animate(v.outputs[0], "default_value", list(enumerate(vals)))
    CLOCK = ng
    return ng


def clock_from(signals):
    """Build the VJClock group from a per-frame signals(f) -> {name: value} function (frames 0..FRAMES)."""
    sig = [signals(f) for f in range(FRAMES + 1)]
    return build_clock({key: [s[key] for s in sig] for key in sig[0]})


class Shader:
    """Emission-only material graph builder. Inputs may be floats, tuples or sockets."""

    def __init__(self, name, method="DITHERED"):
        self.mat = bpy.data.materials.new(name)
        self.mat.use_nodes = True
        self.nt = self.mat.node_tree
        self.nt.nodes.clear()
        self.out = self.nt.nodes.new("ShaderNodeOutputMaterial")
        self.clk = self.nt.nodes.new("ShaderNodeGroup")
        self.clk.node_tree = CLOCK
        self._cam = None
        self.mat.surface_render_method = method

    # inputs ---------------------------------------------------------
    def c(self, key):
        return self.clk.outputs[key]

    def node(self, kind, **props):
        n = self.nt.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def put(self, sock, val):
        if isinstance(val, bpy.types.NodeSocket):
            self.nt.links.new(val, sock)
        elif isinstance(val, (tuple, list)) and len(val) == 3 and sock.type == "RGBA":
            sock.default_value = (*val, 1.0)
        else:
            sock.default_value = val

    @property
    def dist(self):
        if self._cam is None:
            self._cam = self.nt.nodes.new("ShaderNodeCameraData")
        return self._cam.outputs["View Distance"]

    # math -----------------------------------------------------------
    def math(self, op, a, b=0.0, c=0.0, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.put(n.inputs[0], a)
        self.put(n.inputs[1], b)
        self.put(n.inputs[2], c)
        return n.outputs[0]

    def add(self, *xs):
        acc = xs[0]
        for x in xs[1:]:
            acc = self.math("ADD", acc, x)
        return acc

    def mul(self, *xs):
        acc = xs[0]
        for x in xs[1:]:
            acc = self.math("MULTIPLY", acc, x)
        return acc

    def sub(self, a, b):
        return self.math("SUBTRACT", a, b)

    def inv(self, a):                                             # 1 - a
        return self.math("SUBTRACT", 1.0, a)

    def madd(self, a, b, c):                                      # a * b + c
        return self.math("MULTIPLY_ADD", a, b, c)

    def exp(self, x):
        return self.math("EXPONENT", x)

    def falloff(self, d, length):                                 # exp(-d / length)
        return self.exp(self.math("MULTIPLY", d, -1.0 / length))

    def gauss(self, x, center, width):                            # exp(-((x - center) / width)^2)
        t = self.math("DIVIDE", self.math("SUBTRACT", x, center), width)
        return self.exp(self.math("MULTIPLY", self.math("MULTIPLY", t, t), -1.0))

    def smooth(self, x, lo, hi):                                  # smoothstep(lo, hi, x); bounds may be sockets
        n = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        self.put(n.inputs["Value"], x)
        self.put(n.inputs["From Min"], lo)
        self.put(n.inputs["From Max"], hi)
        return n.outputs["Result"]

    def length2(self, x, y):                                      # sqrt(x^2 + y^2)
        return self.math("SQRT", self.add(self.mul(x, x), self.mul(y, y)))

    def mix(self, fac, a, b):                                     # color mix
        n = self.node("ShaderNodeMix", data_type="RGBA", clamp_factor=True)
        self.put([s for s in n.inputs if s.name == "Factor" and s.type == "VALUE"][0], fac)
        self.put([s for s in n.inputs if s.name == "A" and s.type == "RGBA"][0], a)
        self.put([s for s in n.inputs if s.name == "B" and s.type == "RGBA"][0], b)
        return [s for s in n.outputs if s.name == "Result" and s.type == "RGBA"][0]

    def xyz(self, vec):
        n = self.node("ShaderNodeSeparateXYZ")
        self.put(n.inputs[0], vec)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def vec(self, x, y, z):
        n = self.node("ShaderNodeCombineXYZ")
        self.put(n.inputs[0], x)
        self.put(n.inputs[1], y)
        self.put(n.inputs[2], z)
        return n.outputs[0]

    def obj_coords(self):
        return self.xyz(self.node("ShaderNodeTexCoord").outputs["Object"])

    def world_pos(self):
        return self.xyz(self.node("ShaderNodeNewGeometry").outputs["Position"])

    def uv(self):
        return self.xyz(self.node("ShaderNodeUVMap").outputs["UV"])

    def obj_info(self):
        """(color socket, alpha socket, random socket) of the object (per-object values keyed in Object.color)."""
        oi = self.node("ShaderNodeObjectInfo")
        return oi.outputs["Color"], oi.outputs["Alpha"], oi.outputs["Random"]

    def facing(self, blend=0.5):
        lw = self.node("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = blend
        return lw.outputs["Facing"]

    def core(self, lo=0.45, hi=1.5):
        """Neon-tube profile: brighter where the surface faces the camera (hot core, softer edges)."""
        f = self.math("SUBTRACT", 1.0, self.facing())
        return self.madd(self.mul(f, f), hi - lo, lo)

    def rim(self, edge=(0.38, 0.92)):
        """0 where the surface faces the camera, 1 along the silhouette edges: a neon outline on a black body."""
        return self.smooth(self.facing(), *edge)

    def ramp(self, fac, stops):
        """Color ramp [(position, (r, g, b))] driven by fac."""
        r = self.node("ShaderNodeValToRGB")
        els = r.color_ramp.elements
        els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1)
        els[1].position, els[1].color = stops[-1][0], (*stops[-1][1], 1)
        for p, c in stops[1:-1]:
            els.new(p).color = (*c, 1)
        self.put(r.inputs["Fac"], fac)
        return r.outputs["Color"]

    def noise4(self, vec, w, scale=1.0, detail=2.0, rough=0.5, distortion=0.0):
        """4D noise Fac (seamless loops walk w and one vector axis round a circle via LoopCos/LoopSin)."""
        n = self.node("ShaderNodeTexNoise", noise_dimensions="4D")
        self.put(n.inputs["Vector"], vec)
        self.put(n.inputs["W"], w)
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        n.inputs["Distortion"].default_value = distortion
        return n.outputs["Fac"]

    def emit(self, color, strength):
        e = self.node("ShaderNodeEmission")
        self.put(e.inputs["Color"], color)
        self.put(e.inputs["Strength"], strength)
        self.nt.links.new(e.outputs[0], self.out.inputs["Surface"])
        return self.mat

    def emit_sum(self, terms, additive=False):
        """Sum of emissions [(color, strength)]; additive = also transparent (adds onto what is behind)."""
        acc = None
        for col, st in terms:
            e = self.node("ShaderNodeEmission")
            self.put(e.inputs["Color"], col)
            self.put(e.inputs["Strength"], st)
            if acc is None:
                acc = e.outputs[0]
            else:
                add = self.node("ShaderNodeAddShader")
                self.nt.links.new(acc, add.inputs[0])
                self.nt.links.new(e.outputs[0], add.inputs[1])
                acc = add.outputs[0]
        if additive:
            add = self.node("ShaderNodeAddShader")
            self.nt.links.new(self.node("ShaderNodeBsdfTransparent").outputs[0], add.inputs[0])
            self.nt.links.new(acc, add.inputs[1])
            acc = add.outputs[0]
            self.mat.surface_render_method = "BLENDED"
            self.mat.use_transparency_overlap = True
        self.nt.links.new(acc, self.out.inputs["Surface"])
        return self.mat

    def additive(self, color, strength):
        """Light that adds onto what is behind it and never occludes (beams, glows): transparent + emission."""
        return self.emit_sum([(color, strength)], additive=True)

    def emit_masked(self, on, color, strength):
        """Emission where on = 1, fully transparent where on = 0 (dithered): things that do not exist yet must not cut
        dark holes, and an opaque black emitter before its event breaks the seam."""
        e = self.node("ShaderNodeEmission")
        self.put(e.inputs["Color"], color)
        self.put(e.inputs["Strength"], strength)
        mx = self.node("ShaderNodeMixShader")
        self.put(mx.inputs["Fac"], on)
        self.nt.links.new(self.node("ShaderNodeBsdfTransparent").outputs[0], mx.inputs[1])
        self.nt.links.new(e.outputs[0], mx.inputs[2])
        self.nt.links.new(mx.outputs[0], self.out.inputs["Surface"])
        return self.mat


def black_mat(name="Black"):
    """Pure black occluder (a silhouette): emission 0."""
    s = Shader(name)
    return s.emit((0.0, 0.0, 0.0), 0.0)


# ------------------------------------------------------------------ render setup
def setup_render(scene, samples=16, pct=100, view="Standard", look=None, bloom=(1.0, 0.6, 0.4), exposure=0.0,
                 mblur=False):
    """bloom: (threshold, strength, size) of the compositor's Bloom glare, or None. mblur: half-frame shutter."""
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    ee = scene.eevee
    ee.taa_render_samples = samples
    ee.use_shadows = False
    ee.use_raytracing = False
    ee.use_gtao = False
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    scene.render.resolution_percentage = pct
    scene.render.fps, scene.render.fps_base = FPS, 1.0
    scene.frame_start, scene.frame_end = 0, FRAMES - 1
    scene.render.film_transparent = False
    scene.render.use_motion_blur = mblur
    scene.render.motion_blur_shutter = 0.5
    scene.render.motion_blur_position = "CENTER"
    im = scene.render.image_settings
    im.file_format, im.color_mode, im.color_depth, im.compression = "PNG", "RGB", "8", 15
    scene.view_settings.view_transform = view
    if look:
        try:
            scene.view_settings.look = look
        except TypeError as e:
            log(f"look {look!r} unavailable: {e}")
    scene.view_settings.exposure = exposure
    scene.view_settings.gamma = 1.0
    scene.render.use_compositing = bloom is not None
    if bloom is not None:
        scene.use_nodes = True
        nt = scene.node_tree
        nt.nodes.clear()
        rl = nt.nodes.new("CompositorNodeRLayers")
        g = nt.nodes.new("CompositorNodeGlare")                   # tight bloom: the neon halo, black stays black
        g.glare_type = "BLOOM"
        g.quality = "HIGH"
        g.inputs["Threshold"].default_value = bloom[0]
        g.inputs["Smoothness"].default_value = 0.3
        g.inputs["Strength"].default_value = bloom[1]
        g.inputs["Size"].default_value = bloom[2]
        comp = nt.nodes.new("CompositorNodeComposite")
        nt.links.new(rl.outputs["Image"], g.inputs["Image"])
        nt.links.new(g.outputs["Image"], comp.inputs["Image"])


def standard_render(scene):
    """setup_render with the common CLI (--samples --pct --view --exposure --bloom --mblur)."""
    setup_render(scene, samples=int(arg("--samples", 16)), pct=int(arg("--pct", 100)),
                 view=arg("--view", "Standard"), look=arg("--look"), exposure=float(arg("--exposure", 0.0)),
                 bloom=tuple(float(x) for x in arg("--bloom", "1.0,0.6,0.4").split(",")), mblur=flag("--mblur"))


def compositor_tail(scene):
    """(node tree, the socket feeding the Composite node): to splice an extra compositor node after the Bloom."""
    nt = scene.node_tree
    comp = [n for n in nt.nodes if n.bl_idname == "CompositorNodeComposite"][0]
    return nt, comp, comp.inputs["Image"].links[0].from_socket


WARM = False                                                    # has this Blender session rendered a frame yet?


def render_frames(scene, out_dir, frames, prefix):
    global WARM
    os.makedirs(out_dir, exist_ok=True)
    t_all = time.time()
    if scene.render.use_motion_blur and not WARM and frames:
        # Blender 4.5 EEVEE: the first frame rendered in a session has no motion blur on moving objects
        # (2026-10-10, Chain Reaction's seam: frame 0 was always the first render). A throwaway render first.
        scene.frame_set(frames[0])
        bpy.ops.render.render(write_still=False)
        log(f"warm-up render (frame {frames[0]}, not saved) {time.time() - t_all:.2f}s")
    WARM = True
    for f in frames:
        t0 = time.time()
        scene.frame_set(f)
        scene.render.filepath = os.path.join(out_dir, f"{prefix}{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        log(f"frame {f} {time.time() - t0:.2f}s")
    log(f"rendered {len(frames)} frames in {time.time() - t_all:.1f}s")


SAFE = (0.05 * 1920, 0.05 * 1080, 0.95 * 1920, 0.95 * 1080)     # the middle 90%: key art stays inside


def safe_report(scene, prefixes, step=6, samples=600, frames=None):
    """Where the key art lands against the middle-90% safe area: the vertices of the mesh objects whose names start
    with any of `prefixes`, projected through the scene camera on every `step`-th frame of the loop (or `frames`).
    Logs their pixel extent and the share outside the safe area (no render)."""
    from bpy_extras.object_utils import world_to_camera_view
    obs = [o for o in scene.objects if o.type == "MESH" and o.name.startswith(tuple(prefixes))]
    lo, hi, n_all, n_frame, n_out = [1e9, 1e9], [-1e9, -1e9], 0, 0, 0
    for f in frames or range(0, FRAMES, step):
        scene.frame_set(f)
        for ob in obs:
            vs, mw = ob.data.vertices, ob.matrix_world
            for i in range(0, len(vs), max(1, len(vs) // samples)):
                p = world_to_camera_view(scene, scene.camera, mw @ vs[i].co)
                n_all += 1
                x, y = p.x * 1920, (1.0 - p.y) * 1080
                if p.z <= 0 or not (0 <= x <= 1920 and 0 <= y <= 1080):
                    continue
                lo, hi = [min(lo[0], x), min(lo[1], y)], [max(hi[0], x), max(hi[1], y)]
                n_frame += 1
                n_out += not (SAFE[0] <= x <= SAFE[2] and SAFE[1] <= y <= SAFE[3])
    names = ", ".join(o.name for o in obs[:6]) + (" ..." if len(obs) > 6 else "")
    log(f"safe area: {names} in frame x {lo[0]:.0f}..{hi[0]:.0f} y {lo[1]:.0f}..{hi[1]:.0f}; "
        f"{n_out / max(n_frame, 1):.1%} of the in-frame points outside the middle 90% "
        f"({1 - n_frame / max(n_all, 1):.0%} of all points off the frame)")


def finish(scene, name):
    """Common CLI: --frames a,b,c | --all ; --out DIR ; --seam DIR (also render frame FRAMES there, in the same
    session, for the seam check) ; --blend FILE ; --safe PREFIX,PREFIX (where those objects land against the middle-90%
    safe area over the loop, or over --safe-frames A:B every 3rd frame; no render needed)."""
    if arg("--safe"):
        span = arg("--safe-frames")
        safe_report(scene, arg("--safe").split(","),
                    frames=range(*map(int, span.split(":")), 3) if span else None)
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    out = os.path.abspath(arg("--out", os.path.join(root, "renders", name, "frames")))   # Blender would resolve a
    blend = arg("--blend")                                                                # relative path from C:/
    if blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(blend))
        log(f"saved {blend}")
    if flag("--all"):
        frames = list(range(FRAMES))
    elif arg("--frames"):
        frames = [int(x) for x in arg("--frames").split(",")]
    else:
        frames = []
    if frames:
        render_frames(scene, out, frames, name + "_")
    if arg("--seam"):
        render_frames(scene, os.path.abspath(arg("--seam")), [FRAMES], name + "_")
