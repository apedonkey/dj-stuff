"""Shared kit for the Dino Stage VJ loops (Blender 4.5 headless, EEVEE Next).

Music grid: 140 BPM half-time dubstep (--bpm N or env VJ_BPM; --straight or env VJ_HALFTIME=0 for a 4-on-the-floor
grid), 30 fps -> a beat is 12.857 frames, a bar 51.43, 8 bars 411 frames (13.7 s; at 128 BPM 450 frames, 15.0 s).
Beats are quantized to the nearest frame (BEAT_F); a loop renders frames 0..FRAMES-1 and frame FRAMES equals frame 0.
Accents: half-time puts them on the kick (beat 1) and the snare (beat 3), ACC = 2 beats apart; straight, on every
beat. Scene scripts derive all timing from FPB / BEAT_F / FRAMES / ACC (never hard-code a frame count) and key beat
pulses from the accent clock (clock()["kick"], ["aph"], ["acc"]), so the same script plays straight or half-time.

Every loop script imports this module, builds its scene and calls finish(). Shared pieces:
  clock(f)            per-frame musical signals (kick envelope, beat phase, bar, section...) used to key the scene
  build_clock(keys)   a shader node group "VJClock" whose Value nodes are keyed per frame: every material reads the
                      same musical clock (one source of truth for beat sync)
  Shader              tiny node-graph builder (math chains, mixes, emission)
  tube / horn         swept tubes and curved horns (from TribeXR/Scripts/Blender/dino_stage.py, our stage generator)
  animate()           keys any RNA property for a list of (frame, value)
  setup_render()      EEVEE Next + compositor bloom, 1920x1080 @ 30 fps, PNG frames
  variant()           picks the --variant entry of a loop's VARIANTS table
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
FPS, BARS = 30, 8
BPM = float(arg("--bpm", os.environ.get("VJ_BPM", 140)))
HALFTIME = not flag("--straight") and (flag("--halftime") or os.environ.get("VJ_HALFTIME", "1") == "1")
ACC = 2 if HALFTIME else 1                                        # beats between accents (kick, snare)
BEATS = BARS * 4
FPB = FPS * 60.0 / BPM                                            # frames per beat: 12.857 at 140 BPM
FRAMES = int(round(BEATS * FPB))                                  # 411 at 140 BPM (450 at 128)
BEAT_F = [int(math.floor(k * FPB + 0.5)) for k in range(BEATS)] + [FRAMES]   # nearest frame of each beat
assert all(a < b for a, b in zip(BEAT_F, BEAT_F[1:]))

# palette (linear emission colors)
AMBER = (1.0, 0.36, 0.025)
ORANGE = (1.0, 0.16, 0.01)
CYAN = (0.0, 0.62, 1.0)
MAGENTA = (1.0, 0.0, 0.42)
GREEN = (0.08, 1.0, 0.03)
RED = (1.0, 0.0, 0.015)
UV = (0.30, 0.0, 1.0)
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
    ph = (f - f0) / (f1 - f0)                                    # 0 on the kick frame -> 1
    bar, beat = divmod(k, 4)
    hat_f = int(math.floor((k + 0.5) * FPB + 0.5))               # the offbeat ("and")
    eighth_f = f0 if f < hat_f else hat_f
    a = k - k % ACC                                               # beat of the current accent
    aph = (f - BEAT_F[a]) / (BEAT_F[a + ACC] - BEAT_F[a])         # 0 on the accent frame -> 1 at the next accent
    if HALFTIME:                                                  # kick on beat 1, snare on beat 3, each decaying
        kick = (1.0 if a % 4 == 0 else 0.85) * math.exp(-5.0 * aph)   # over its half bar
    else:
        kick = math.exp(-6.0 * ph)                                # 1 on the kick frame, ~0 by the next beat
    return {
        "f": f, "k": k, "ph": ph, "bar": bar, "beat": beat,
        "kick": kick, "acc": a // ACC, "aph": aph, "snare": HALFTIME and a % 4 == 2,
        "hat": math.exp(-(f - hat_f) / 1.6) if f >= hat_f else 0.0,
        "pulse8": math.exp(-(f - eighth_f) / 1.8),                # 8th-note envelope (kick + offbeat)
        "beatpos": k + ph,                                        # continuous beat count 0..32
        "loop": f / FRAMES,                                       # 0..1 over the loop
    }


def jolt(f, decay=3.0, period=5.0):
    """Half-time weight as motion, not light: a damped jolt after each accent (the kick 1.0, the snare 0.85; straight:
    every beat), 0 on the accent frame, a quick throw and a short wobble. Scale it into a camera's pitch or height."""
    c = clock(f)
    t = c["f"] - BEAT_F[c["acc"] * ACC]
    return (0.85 if c["snare"] else 1.0) * math.exp(-t / decay) * math.sin(2 * math.pi * t / period)


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


# ------------------------------------------------------------------ geometry (tube/horn: dino_stage.py)
def tube(bm, pts, radius_fn, segs=12, cap0=True, tip=False, closed=False):
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
    else:
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


def catmull(ctrl, per=8):
    """Catmull-Rom through ctrl (Vectors), per samples per span; ends clamped."""
    P = [ctrl[0]] + list(ctrl) + [ctrl[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for s in range(per):
            t = s / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(ctrl[-1].copy())
    return out


def circle_pts(center, radius, n, axis="Y"):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s = math.cos(a) * radius, math.sin(a) * radius
        pts.append(center + (Vector((c, 0, s)) if axis == "Y" else Vector((c, s, 0))))
    return pts


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

    def madd(self, a, b, c):                                      # a * b + c
        return self.math("MULTIPLY_ADD", a, b, c)

    def exp(self, x):
        return self.math("EXPONENT", x)

    def falloff(self, d, length):                                 # exp(-d / length)
        return self.exp(self.math("MULTIPLY", d, -1.0 / length))

    def gauss(self, x, center, width):                            # exp(-((x - center) / width)^2)
        t = self.math("DIVIDE", self.math("SUBTRACT", x, center), width)
        return self.exp(self.math("MULTIPLY", self.math("MULTIPLY", t, t), -1.0))

    def smooth(self, x, lo, hi):                                  # smoothstep(lo, hi, x)
        n = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        self.put(n.inputs["Value"], x)
        n.inputs["From Min"].default_value = lo
        n.inputs["From Max"].default_value = hi
        return n.outputs["Result"]

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

    def core(self, lo=0.45, hi=1.5):
        """Neon-tube profile: brighter where the surface faces the camera (hot core, softer edges)."""
        lw = self.node("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.5
        f = self.math("SUBTRACT", 1.0, lw.outputs["Facing"])
        return self.madd(self.mul(f, f), hi - lo, lo)

    def emit(self, color, strength):
        e = self.node("ShaderNodeEmission")
        self.put(e.inputs["Color"], color)
        self.put(e.inputs["Strength"], strength)
        self.nt.links.new(e.outputs[0], self.out.inputs["Surface"])
        return self.mat

    def additive(self, color, strength):
        """Light that adds onto what is behind it and never occludes (lasers, flashes): transparent + emission."""
        e = self.node("ShaderNodeEmission")
        self.put(e.inputs["Color"], color)
        self.put(e.inputs["Strength"], strength)
        add = self.node("ShaderNodeAddShader")
        self.nt.links.new(self.node("ShaderNodeBsdfTransparent").outputs[0], add.inputs[0])
        self.nt.links.new(e.outputs[0], add.inputs[1])
        self.nt.links.new(add.outputs[0], self.out.inputs["Surface"])
        self.mat.surface_render_method = "BLENDED"
        self.mat.use_transparency_overlap = True
        return self.mat


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


WARM = False                                                    # has this Blender session rendered a frame yet?


def render_frames(scene, out_dir, frames, prefix):
    global WARM
    os.makedirs(out_dir, exist_ok=True)
    t_all = time.time()
    if scene.render.use_motion_blur and not WARM and frames:
        # Blender 4.5 EEVEE: the first frame rendered in a session has no motion blur on moving objects (found by the
        # REACTOR session 2026-10-10: frame 0 was always the first render, so every loop's wrap frame was unblurred).
        # A throwaway render first.
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


def in_polygon(x, y, poly):
    """Even-odd test of a point against a polygon [(x, y)]."""
    inside = False
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            inside = not inside
    return inside


def arch_report(scene, prefixes, step=6, samples=600, frames=None):
    """Where the key art lands against the Dino Stage's arch window (scripts/arch_window.json, from arch_window.py):
    the vertices of the mesh objects whose names start with any of `prefixes`, projected through the scene camera on
    every `step`-th frame of the loop (or of `frames`, a range). Logs their pixel extent and the share outside the
    window (no render)."""
    import json
    from bpy_extras.object_utils import world_to_camera_view
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "arch_window.json")) as fh:
        poly = [tuple(p) for p in json.load(fh)["outline_px"]]
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
                    continue                                       # off the 16:9 frame altogether
                lo, hi = [min(lo[0], x), min(lo[1], y)], [max(hi[0], x), max(hi[1], y)]
                n_frame += 1
                n_out += not in_polygon(x, y, poly)
    names = ", ".join(o.name for o in obs[:6]) + (" ..." if len(obs) > 6 else "")
    log(f"arch window: {names} in frame x {lo[0]:.0f}..{hi[0]:.0f} y {lo[1]:.0f}..{hi[1]:.0f}; "
        f"{n_out / max(n_frame, 1):.1%} of the in-frame points outside the window "
        f"({1 - n_frame / max(n_all, 1):.0%} of all points off the frame)")


def finish(scene, name):
    """Common CLI: --frames a,b,c | --all ; --out DIR ; --seam DIR (also render frame FRAMES there, in the same session,
    for the seam check) ; --blend FILE ; --arch PREFIX,PREFIX (where those objects land against the Dino Stage's arch
    window over the loop, or over --arch-frames A:B every 3rd frame; no render needed)."""
    if arg("--arch"):
        span = arg("--arch-frames")
        arch_report(scene, arg("--arch").split(","),
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
