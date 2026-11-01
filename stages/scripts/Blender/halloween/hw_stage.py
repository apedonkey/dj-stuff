"""GRAVEYARD SHIFT: the Halloween stage generator (Blender 4.5, headless). v2 = phases 2-4: the set, the grounds modules,
the crowd and the animated show's geometry (v1, the set alone, is hw_stage.v1.bak.py).

v3 (the user on v2, 2026-10-09: "looks pretty good! just needs to be a lot darker out. also we DEFINETLY need more
lazers"; and, through the Dino session, lasers that follow the music like the Dino Stage's): the grounds, the field,
the crowd, the sky and the far ground bake or draw darker (GROUNDS_EXPOSURE, GROUND_EXPOSURE, CROWD_EXPOSURE, SKY_DIM,
FAR_RGB; the fog and the set's floors darken in hw_materials.py / build_halloween.py). The lasers are rebuilt in the
Dino's laser format for dino_materials.laser_show (17 units, ~150 beams: the portal, the four gargoyles, the front
pinnacles' sky lasers, six deck-front units on posts, the crypt towers' skull eyes), every beam's length solved for the
engine's whole +-1 pan/tilt sweep and verified at other poses. T_HwLaserProg / T_HwLaserLib / T_HwLaserCues are the
Dino's show.py tables (read only).

v4 (2026-10-10, the stream intro: the Headless Horseman rides through the woods behind the stage, two presses on a
backstage button end it, "the door come up" and the user walks out to the decks): the woods module hw_woods (its own
glow mesh: OWN_GLOW), the crypt gate in front of the screen's lower middle (stone frame and the backstage crypt baked
with the deck; the roll-up door SM_HwGate rises into its drum on MPC_HwShow DoorOpen; the button SM_HwButton lights by
IntroStep). The ride, the cameras and the button's position: intro/hw_intro_path.py; the rider: intro/hw_rider.py.
v5 (2026-10-10, the user: "make them 2 doors not a garage door. Like crypt doors"): SM_HwGate is two oak crypt doors
with iron strap hinges that swing out to the deck on the same DoorOpen (hw_materials.door_swing, intro.door_xy); the
lasers are solved and verified against the doors shut and open (the open pose is the default when no intro runs).

v2 adds: glow split by show row (SM_HwWindows, SM_HwEyes, SM_HwLenses, SM_HwClockFace + the turning SM_HwClockHands),
laser pivot UVs (hw_materials.laser_sweep), bat flocks (SM_HwBats), ghosts, ground fog, flame jets, lightning bolts,
the giant skeletal hands that rise out of the deck (SM_HwHands), the cue table T_HwCues (hw_show.py), the grounds
modules (modules/*.py, CONTRACT.md: one baked SM_HwGrounds<Name> each, SM_HwGroundsGlow, per-module beam/halo meshes)
and the costumed VAT crowd (crowd/hw_crowd.py, else the Dino crowd3 as a fallback). hw_groups.json tells
build_halloween.py which show row each beam group follows. Env: HW_MODULES (comma list), HW_CROWD=0 (no crowd),
HW_FOG=0 (no fog sheets).

v1's notes:

v0 (hw_stage.v0.bak.py, on the headset 2026-10-08) was the approved concept's set with baked light. v1 details it:
  - towers: front buttresses, framed twin-light windows on the front, inner and outer faces, a blood-red rose window
    under each parapet, moss on the lower stones; a parapet and a broken cross on the gable; open-mouthed gargoyles
  - the rig (SM_HwRig + lens glows): 26 moving heads (tower balconies, portal truss, deck uplights), 4 searchlights,
    the portal laser housing; FROZEN translucent beams, halos, 5 laser fans and sky beams (SM_HwBeams / SM_HwHalos /
    SM_HwLasers / SM_HwSearch, alpha-blended instances of Tribe's material; they move in the animated build, phase 4)
  - the DJ area: a skull frieze with dim red eyes on the riser front, a coffin panel on the booth front, candelabras,
    a cauldron with a green glow, a raven, skull piles; the truss and its lanterns now hang in FRONT of the screen,
    above the picture
  - checks: no laser hits the set, and every laser passes >= 4.9 m from the DJ's head (Dino's rule)
Lighting is baked in Cycles as dino_stage.py does it; one FBX and one texture per surface for ../../build_halloween.py
(Unreal: unlit instances of Tribe's own glTFRuntime materials, pak chunk 54). No crowd or grounds yet (phases 2-3).

Plan: claudedocs/halloween_stage_plan.md in the tribe hack repo; running log: claudedocs/halloween_stage_notes.md.

Frame: FINAL Tribe coordinates (no stage drop afterwards): meters, Z up, the DJ at the origin on Tribe's floor (z=0 =
the riser top) facing -Y, the stage deck top at DECK_Z = -1, the crowd field at FIELD_Z = -2.5 toward -Y, the cathedral
behind the DJ (+Y). The FBX export mirrors Y; build_halloween.py turns the level 180 degrees (as for Dino and the club).

    run_hw_stage.sh [--fast]   (Blender under the shared GPU lock C:\\Users\\Chris\\TribeUE\\gpu.lock.d)
HW_OUT=<dir> writes elsewhere (default: out_hw next to this file). --fast: 1/8-size bakes, 4 samples (pipeline test).
"""
import math
import os
import random
import struct
import sys
import time
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

import importlib
import importlib.util
import inspect
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "grounds"))
sys.path.insert(0, os.path.join(HERE, "modules"))
import hw_deckprops as dp  # noqa: E402  (v7: the deck dressing and the stairs, shared with intro/hw_collide.py)
import kit  # noqa: E402  (read-only use of the shared mesh helpers: box, cyl, cone, sphere, quad, truss, write_png)
from hw_show import tex_cues, write_png_linear, CUE_ROWS  # noqa: E402  (the light show's cue table)
import hw_infrastructure as hwi  # noqa: E402  (read only: where the crypt towers' skulls are, for their lasers)
sys.path.insert(0, os.path.join(HERE, "intro"))
import hw_intro_path as intro  # noqa: E402  (the stream intro: the button and the backstage spot)
_spec = importlib.util.spec_from_file_location("dino_show", os.path.join(HERE, "..", "show.py"))
dino_show = importlib.util.module_from_spec(_spec)   # the Dino's show.py, read only (as club_stage.py imports it):
_spec.loader.exec_module(dino_show)                  # its laser program, pattern library and cue table

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FAST = "--fast" in ARGS
OUT = os.environ.get("HW_OUT") or os.path.join(HERE, "out_hw")
os.makedirs(OUT, exist_ok=True)
BAKE_SAMPLES = 64
NIGHT = 0.5                                   # Dino's night pass: every bake exposure x0.5
FIELD_Z, DECK_Z = -2.5, -1.0                  # final frame (docstring)
LAND_Z = FIELD_Z + 1.75                       # lasers land at the crowd's head height
DJ_HEAD = Vector((0.0, 0.9, 1.7))             # PlayerStartDJ (-6, 87) cm on the riser, eyes ~1.7 m up
TABLE = {"x0": -0.95, "x1": 0.85, "y0": -0.05, "y1": 0.50, "top": 0.74}   # dino_stage.TABLE: the booth under Tribe's gear
SCREEN = {"y": 10.3, "cz": 6.2, "w": 23.0, "h": 23.0 * 9 / 16}           # Dino v7.1's verified 16:9 screen, final frame
TRUSS_Y = 9.8                                 # in front of the screen (y 10.3), so its lanterns never sit behind it
MOON = Vector((-30.0, 100.0, 80.0))           # high and off-axis: seen from the field and the stream cameras
MOON_R = 14.0
OAK_X = 39.0                                  # the giant dead oaks (v1b: 36 -> 39, their crowns met the outer laser fans)
STAGE_DROP = 1.0                              # modules and the crowd are built in the kit's frame (field -1.5): lowered
HW_MODULES = tuple(m for m in os.environ.get("HW_MODULES", "hw_graveyard,hw_infrastructure,hw_vendors,hw_forest,hw_woods,"
                                                           "hw_carnival,hw_pumpkins,hw_crypt").split(",") if m)
MODULE_ROWS = {"hw_infrastructure": "infra", "hw_crypt": "crypt"}   # beam groups that follow a show row (else "always")
CROWD_ON = os.environ.get("HW_CROWD", "1") == "1"
FOG_ON = os.environ.get("HW_FOG", "1") == "1"
# v3 darkness (the user, 2026-10-09: "just needs to be a lot darker out"): in the bakes the grounds modules x0.45, the
# field x0.6 (its module light pools too) and the crowd x0.7; the sky's clouds and horizon glow x0.35, its stars x0.8;
# the far ground x0.4. The set keeps its v1 calibration x SET_DIM (the show lights it; its floors drop in build_halloween.py);
# every emitter (lanterns, windows, eyes, signs, lasers, beams) stays as bright as it was.
GROUNDS_EXPOSURE, GROUND_EXPOSURE, CROWD_EXPOSURE = 1.8 * 0.45, 6.0 * 0.6, 0.55 * 0.7
SKY_DIM, STAR_DIM = 0.35, 0.8
SET_DIM = 0.7                                 # the set's bakes too (its show peak; the user told the Dino session the same
                                              # day "it still needs to be darker on stage and in the crowd i think")
FAR_RGB = (0.0015, 0.0015, 0.0025)            # build_halloween.py's MI_HwFar: the same
FOG_RGB = (0.07 * 0.55, 0.075 * 0.55, 0.10 * 0.55)   # v7: build_halloween's fog at a mid show level (lit 0.4..1)
T0 = time.time()
rng = random.Random(31)


def log(msg):
    print(f"[HW {time.time() - T0:7.1f}s] {msg}", flush=True)


# ---------------------------------------------------------------- PNG I/O (copied from dino_stage.py)
def srgb(lin):
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


def write_png(path, rgb_lin_top_down):
    """rgb_lin_top_down: HxWx3 linear floats, row 0 = top of the image."""
    a = (srgb(rgb_lin_top_down) * 255.0 + 0.5).astype(np.uint8)
    h, w, _ = a.shape
    raw = b"".join(b"\x00" + a[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    open(path, "wb").write(png)
    log(f"texture {os.path.basename(path)} {w}x{h}")


def tonemap(lin, exposure):
    return 1.0 - np.exp(-lin * exposure)      # soft shoulder: baked highlights never clip to flat white


# ---------------------------------------------------------------- scene (Cycles on the GPU, as dino_stage.py)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
_prefs = bpy.context.preferences.addons["cycles"].preferences
for _dev in ("OPTIX", "CUDA"):
    try:
        _prefs.compute_device_type = _dev
        _prefs.refresh_devices()
        _gpus = [d for d in _prefs.devices if d.type == _dev]
        if _gpus:
            for d in _prefs.devices:
                d.use = d.type == _dev
            scene.cycles.device = "GPU"
            log(f"Cycles on {_dev}: {[d.name for d in _gpus]}")
            break
    except Exception as e:  # noqa: BLE001
        log(f"{_dev} unavailable: {e}")
scene.view_settings.view_transform = "Standard"
coll = scene.collection


def new_obj(name, bm, mats=()):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def setmat(faces, idx):
    for f in faces:
        f.material_index = idx
    return faces


def bm_merge(dst, src):
    """Append src's faces (material indices kept) to dst: build repeated items in their own small bmesh, because each
    bmesh.ops call costs O(whole mesh) (the concept's crowd stalled for 11 minutes on one growing mesh)."""
    src.verts.index_update()
    vmap = [dst.verts.new(v.co) for v in src.verts]
    for f in src.faces:
        try:
            dst.faces.new([vmap[v.index] for v in f.verts]).material_index = f.material_index
        except ValueError:
            pass
    src.free()


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


# ---------------------------------------------------------------- glow palette (unlit emitters, one texture)
GLOW = {
    "win_red": (1.0, 0.12, 0.05), "win_purple": (0.50, 0.15, 1.0), "win_green": (0.20, 1.0, 0.30),
    "win_amber": (1.0, 0.60, 0.12), "clock_rim": (1.0, 0.60, 0.12), "clock_hand": (1.0, 0.08, 0.05),
    "clock_face": (0.12, 0.012, 0.006), "lantern": (1.0, 0.50, 0.15), "candle": (1.0, 0.62, 0.25),
    "eyes": (1.0, 0.06, 0.02), "orange": (1.0, 0.40, 0.05), "purple": (0.40, 0.10, 1.0), "green": (0.15, 1.0, 0.25),
    "black": (0.0, 0.0, 0.0), "eyes_dim": (0.38, 0.02, 0.01), "rose_red": (0.85, 0.04, 0.06),
    "rose_gold": (1.0, 0.45, 0.08), "brew": (0.25, 1.0, 0.35), "moon_lens": (0.75, 0.82, 1.0),
}
CRYPT_SHADES = 7                               # v6: the glow in the doorway the Horseman rides into, edge -> core
for _i in range(CRYPT_SHADES):
    _t = (_i / (CRYPT_SHADES - 1)) ** 1.6
    GLOW[f"crypt_{_i}"] = tuple(a + (b - a) * _t for a, b in zip((0.02, 0.16, 0.06), (0.75, 1.0, 0.82)))
GLOW_KEYS = list(GLOW)
PAL_COLS = 8
PAL_ROWS = (len(GLOW_KEYS) + PAL_COLS - 1) // PAL_COLS


def pal_uv(key):
    i = GLOW_KEYS.index(key)
    return ((i % PAL_COLS + 0.5) / PAL_COLS, 1.0 - (i // PAL_COLS + 0.5) / PAL_ROWS)


def tex_palette(cell=8):
    img = np.zeros((PAL_ROWS * cell, PAL_COLS * cell, 3))
    for i, k in enumerate(GLOW_KEYS):
        r, c = divmod(i, PAL_COLS)
        img[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] = GLOW[k]
    return img


def _glow_bm():
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap")
    return bm


G = _glow_bm()      # always-on glow (lanterns, candles, the coffin cross, the brew, the clock rim): SM_HwGlow
GW = _glow_bm()     # stained glass (tower windows, rose windows): SM_HwWindows, show row "windows"
GE = _glow_bm()     # eyes (gargoyles, the skull frieze, the raven): SM_HwEyes, show row "eyes"
GL = _glow_bm()     # moving-head lens discs: SM_HwLenses, show row "lenses"
CF = _glow_bm()     # the clock face (it flares at midnight): SM_HwClockFace


def glow(faces, key, bm=None):
    """UV the faces onto the palette cell of `key` (they belong to bm, default G)."""
    uvl = (bm if bm is not None else G).loops.layers.uv["UVMap"]
    uv = pal_uv(key)
    for f in faces:
        for lp in f.loops:
            lp[uvl].uv = uv
    return faces


# ---------------------------------------------------------------- translucent parts: beams, lasers, halos (frozen)
BEAM_COLS = ["white", "orange", "purple", "green", "red", "amber", "uv", "moon"]   # T_HwBeam / T_HwHalo columns
BEAM_RGB = {"white": (1.0, 1.0, 1.0), "orange": (1.0, 0.40, 0.05), "purple": (0.40, 0.10, 1.0),
            "green": (0.15, 1.0, 0.25), "red": (1.0, 0.08, 0.05), "amber": (1.0, 0.60, 0.12),
            "uv": (0.30, 0.05, 1.0), "moon": (0.55, 0.65, 1.0)}
HEAD_BEAM = {"orange": "orange", "purple": "purple", "green": "green", "win_amber": "amber"}
VIEWERS = (DJ_HEAD, Vector((0.0, -30.0, LAND_Z)))   # halos face the DJ and the middle of the crowd


def tex_beam(w=1024, h=256):
    """kit.tex_beam with the Halloween colors: per column alpha = soft across-profile x fade along (v=0 bright apex)."""
    img = np.zeros((h, w, 4))
    n = len(BEAM_COLS)
    cw = w // n
    x = (np.arange(cw) + 0.5) / cw
    across = np.exp(-((x - 0.5) / 0.22) ** 2) * 0.85 + np.exp(-((x - 0.5) / 0.06) ** 2) * 0.15
    v = 1.0 - (np.arange(h) + 0.5) / h
    along = np.clip(1.0 - v, 0, 1) ** 1.6 * 0.9 + 0.1 * np.exp(-v * 12)
    a = np.outer(along, across) * 0.55
    for i, k in enumerate(BEAM_COLS):
        img[:, i * cw:(i + 1) * cw, :3] = BEAM_RGB[k]
        img[:, i * cw:(i + 1) * cw, 3] = a
    return img


def tex_halo(cell=128):
    n = len(BEAM_COLS)
    img = np.zeros((cell, cell * n, 4))
    y, x = np.mgrid[0:cell, 0:cell]
    r = np.hypot((x + 0.5) / cell - 0.5, (y + 0.5) / cell - 0.5) * 2
    a = np.clip(1 - r, 0, 1) ** 2.2 * 0.8
    for i, k in enumerate(BEAM_COLS):
        img[:, i * cell:(i + 1) * cell, :3] = BEAM_RGB[k]
        img[:, i * cell:(i + 1) * cell, 3] = a
    return img


def beam(bm, apex, direction, length, w0, w1, color, planes=2, roll=0.0, core=1.0):
    """Crossed quads from apex along direction (atmosphere.beam): u across the color's column of T_HwBeam (core < 1:
    only its bright middle, crisp lasers), v 0 at the apex to 1 at the end."""
    apex, d = Vector(apex), Vector(direction).normalized()
    up = Vector((0, 0, 1)) if abs(d.z) < 0.95 else Vector((1, 0, 0))
    s0 = d.cross(up).normalized()
    n, col = len(BEAM_COLS), BEAM_COLS.index(color)
    u0, u1 = (col + 0.5 - 0.48 * core) / n, (col + 0.5 + 0.48 * core) / n
    end = apex + d * length
    faces = []
    for k in range(planes):
        s = (Matrix.Rotation(roll + math.pi * k / planes, 3, d) @ s0).normalized()
        faces += kit.quad(bm, apex - s * w0 / 2, apex + s * w0 / 2, end + s * w1 / 2, end - s * w1 / 2,
                          uvs=[(u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)])
    return end, faces


def halo(bm, center, size, color, axis=None):
    """Soft glow (atmosphere.sprite): crossed squares facing the main viewers and the lens axis, so none shows edge-on."""
    c = Vector(center)
    normals = [(v - c).normalized() for v in VIEWERS] + ([Vector(axis).normalized()] if axis is not None else [])
    picked = []
    for nrm in normals:
        if all(abs(nrm.dot(m)) < 0.94 for m in picked):
            picked.append(nrm)
    col = BEAM_COLS.index(color)
    u0, u1 = col / len(BEAM_COLS), (col + 1) / len(BEAM_COLS)
    for nrm in picked:
        a = nrm.cross(Vector((0, 0, 1)))
        a = a.normalized() if a.length > 1e-3 else Vector((1, 0, 0))
        b = a.cross(nrm).normalized()
        a, b = a * size / 2, b * size / 2
        kit.quad(bm, c - a - b, c + a - b, c + a + b, c - a + b, uvs=[(u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)])


BEAMS, HALOS, SEARCH, BOLTS = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
LASER_UV = ("LaserPivot", "LaserPivotZPhase", "LaserAmp", "LaserCue", "LaserFix")   # UV1..UV5: dino_materials.laser_show
LASERS = bmesh.new()
LASERS.loops.layers.uv.new("UVMap")
for _n in LASER_UV:
    LASERS.loops.layers.uv.new(_n)
LASER_BEAMS = []                               # the solved beams (dicts) for the verification pass


# ---------------------------------------------------------------- materials for the bake
def _nodes(m):
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return nt, nt.nodes.new("ShaderNodeOutputMaterial")


def mat_lit(name, rgb, rough=0.85, brick=0.0, noise=0.3, noise_scale=0.35, moss=None):
    """Diffuse surface for the bake. brick > 0: ashlar blocks (Blender brick texture, scale = 0.5 / block width in m)
    projected on the face's dominant plane; noise: +-variation of the albedo (weathering); moss = (z0, z1): green-grey
    moss creeping up from z0, gone by z1, in noisy patches."""
    m = bpy.data.materials.new(name)
    nt, out = _nodes(m)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = rough
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sp = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sp.inputs[0])

    def math_(op, a, b=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, s in enumerate((a, b)):
            if s is None:
                continue
            if isinstance(s, (int, float)):
                n.inputs[i].default_value = s
            else:
                nt.links.new(s, n.inputs[i])
        return n.outputs[0]
    col = None
    if brick > 0:
        sn = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(geo.outputs["Normal"], sn.inputs[0])
        ax, az = math_("ABSOLUTE", sn.outputs["X"]), math_("ABSOLUTE", sn.outputs["Z"])
        u = math_("ADD", sp.outputs["X"], math_("MULTIPLY", math_("SUBTRACT", sp.outputs["Y"], sp.outputs["X"]), ax))
        v = math_("ADD", sp.outputs["Z"], math_("MULTIPLY", math_("SUBTRACT", sp.outputs["Y"], sp.outputs["Z"]), az))
        cb = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(u, cb.inputs[0])
        nt.links.new(v, cb.inputs[1])
        br = nt.nodes.new("ShaderNodeTexBrick")
        br.inputs["Scale"].default_value = brick
        br.inputs["Color1"].default_value = (*[c * 1.18 for c in rgb], 1)
        br.inputs["Color2"].default_value = (*[c * 0.78 for c in rgb], 1)
        br.inputs["Mortar"].default_value = (*[c * 0.3 for c in rgb], 1)
        br.inputs["Mortar Size"].default_value = 0.035
        nt.links.new(cb.outputs[0], br.inputs["Vector"])
        col = br.outputs["Color"]
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = noise_scale
    nz.inputs["Detail"].default_value = 5.0
    nt.links.new(geo.outputs["Position"], nz.inputs["Vector"])
    if noise > 0:
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = 0.3
        mr.inputs["From Max"].default_value = 0.7
        mr.inputs["To Min"].default_value = 1.0 - noise
        mr.inputs["To Max"].default_value = 1.0 + noise
        nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
        sc = nt.nodes.new("ShaderNodeVectorMath")
        sc.operation = "SCALE"
        if col is None:
            sc.inputs[0].default_value = rgb
        else:
            nt.links.new(col, sc.inputs[0])
        nt.links.new(mr.outputs[0], sc.inputs["Scale"])
        col = sc.outputs["Vector"]
    if moss is not None:
        z0, z1 = moss
        mz = nt.nodes.new("ShaderNodeMapRange")                       # 1 at z0 .. 0 at z1
        mz.inputs["From Min"].default_value = z0
        mz.inputs["From Max"].default_value = z1
        mz.inputs["To Min"].default_value = 1.0
        mz.inputs["To Max"].default_value = 0.0
        nt.links.new(sp.outputs["Z"], mz.inputs["Value"])
        n2 = nt.nodes.new("ShaderNodeTexNoise")
        n2.inputs["Scale"].default_value = 1.6
        n2.inputs["Detail"].default_value = 6.0
        nt.links.new(geo.outputs["Position"], n2.inputs["Vector"])
        fac = math_("MULTIPLY", mz.outputs[0], math_("MULTIPLY", n2.outputs["Fac"], 1.6))
        fac = math_("MINIMUM", fac, 0.85)
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        a_in = [s for s in mix.inputs if s.name == "A" and s.type == "RGBA"][0]
        b_in = [s for s in mix.inputs if s.name == "B" and s.type == "RGBA"][0]
        nt.links.new(fac, mix.inputs["Factor"])
        if col is None:
            a_in.default_value = (*rgb, 1)
        else:
            nt.links.new(col, a_in)
        b_in.default_value = (0.045, 0.075, 0.03, 1)
        col = [s for s in mix.outputs if s.name == "Result" and s.type == "RGBA"][0]
    if col is None:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    else:
        nt.links.new(col, bsdf.inputs["Base Color"])
    return m


def mat_emit(name, rgb=None, strength=1.0, image=None):
    m = bpy.data.materials.new(name)
    nt, out = _nodes(m)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    if image is not None:
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = image
        tx.interpolation = "Closest" if image.size[0] <= 64 else "Linear"
        nt.links.new(tx.outputs["Color"], em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = (*rgb, 1)
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def mat_alpha(name, image):
    """Preview of Tribe's alpha-blended unlit material (dino_stage.mat_alpha): texture rgb over the background by alpha."""
    m = bpy.data.materials.new(name)
    nt, out = _nodes(m)
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = image
    image.alpha_mode = "STRAIGHT"
    em = nt.nodes.new("ShaderNodeEmission")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tx.outputs["Color"], em.inputs["Color"])
    nt.links.new(tx.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    m.surface_render_method = "BLENDED"
    m.use_backface_culling = False
    return m


def assign(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)


def load_png(path):
    img = bpy.data.images.load(path, check_existing=False)
    img.colorspace_settings.name = "sRGB"
    return img


STONE = mat_lit("stone", (0.16, 0.155, 0.17), brick=0.55, noise=0.3, moss=(FIELD_Z, 7.0))
STONE_DARK = mat_lit("stone_dark", (0.075, 0.072, 0.08), brick=0.8, noise=0.3, moss=(FIELD_Z, 5.0))
BARK = mat_lit("bark", (0.055, 0.04, 0.025), rough=0.9, noise=0.35, noise_scale=1.5)
IRON = mat_lit("iron", (0.035, 0.033, 0.037), rough=0.6, noise=0.15)
DECKMAT = mat_lit("deck", (0.03, 0.028, 0.03), rough=0.7, noise=0.25, noise_scale=0.8)
WAX = mat_lit("wax", (0.55, 0.5, 0.42), rough=0.5, noise=0.0)
BONE = mat_lit("bone", (0.42, 0.39, 0.33), rough=0.7, noise=0.25, noise_scale=3.0)
WOOD = mat_lit("coffin_wood", (0.07, 0.035, 0.02), rough=0.6, noise=0.3, noise_scale=4.0)
DOOR_OAK = mat_lit("door_oak", (0.11, 0.07, 0.045), rough=0.65, noise=0.35, noise_scale=4.0)   # v5: the crypt doors
RAVEN = mat_lit("raven", (0.012, 0.012, 0.016), rough=0.4, noise=0.0)
PUMPKIN = mat_lit("pumpkin", (0.40, 0.12, 0.015), rough=0.6, noise=0.25, noise_scale=2.5)   # v7: deck pumpkins
GRASS = mat_lit("grass", (0.03, 0.036, 0.026), rough=0.95, noise=0.4, noise_scale=0.08)
ORANGE, PURPLE, GREENISH = (1.0, 0.40, 0.05), (0.40, 0.10, 1.0), (0.3, 0.9, 0.4)


# ---------------------------------------------------------------- shapes
def solid(bm, faces):
    """Make a hand-built closed solid's normals point outward (Tribe's unlit material culls back faces)."""
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def prism(bm, center, w, d, h):
    """Pitched roof: a triangle in XZ (base w, height h) extruded along Y by d; base at center.z."""
    cx, cy, cz = center
    v = [bm.verts.new(p) for p in ((cx - w / 2, cy - d / 2, cz), (cx + w / 2, cy - d / 2, cz), (cx, cy - d / 2, cz + h),
                                   (cx - w / 2, cy + d / 2, cz), (cx + w / 2, cy + d / 2, cz), (cx, cy + d / 2, cz + h))]
    return solid(bm, [bm.faces.new(f) for f in ((v[0], v[1], v[2]), (v[5], v[4], v[3]), (v[0], v[2], v[5], v[3]),
                                                (v[1], v[4], v[5], v[2]), (v[0], v[3], v[4], v[1]))])


def wedge_y(bm, x0, x1, y_face, depth, z0, z1):
    """A sloped buttress cap: a wedge from depth at z0 to 0 at z1, standing out of a wall at y_face toward -Y."""
    v = [bm.verts.new(p) for p in ((x0, y_face, z0), (x1, y_face, z0), (x1, y_face - depth, z0), (x0, y_face - depth, z0),
                                   (x0, y_face, z1), (x1, y_face, z1))]
    return solid(bm, [bm.faces.new(f) for f in ((v[0], v[3], v[2], v[1]), (v[3], v[0], v[4]), (v[1], v[2], v[5]),
                                                (v[3], v[4], v[5], v[2]), (v[0], v[1], v[5], v[4]))])


def pointed_arch(w, zs, n=14):
    """Outline (x, z) of a pointed arch of half-width w springing at zs, left to right: two arcs of radius 1.25w centred
    at (+-0.25w, zs); apex at zs + 1.2247w."""
    R, c = 1.25 * w, 0.25 * w
    a0, a1 = math.pi, math.atan2(math.sqrt(R * R - c * c), -c)
    pts = [(c + R * math.cos(a0 + (a1 - a0) * i / n), zs + R * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    return pts + [(-x, z) for x, z in reversed(pts[:-1])]


def tree(bm, base, d, L, r, depth, rng_, tips):
    tip = base + d * L
    kit.cyl(bm, base, tip, r, segs=6, cap=False, r2=r * 0.6)
    if depth == 0:
        tips.append(tip)
        return
    for _ in range(rng_.choice((2, 2, 3))):
        axis = d.cross(Vector((rng_.uniform(-1, 1), rng_.uniform(-1, 1), rng_.uniform(-0.2, 0.6)))).normalized()
        nd = (Matrix.Rotation(rng_.uniform(0.35, 0.8), 4, axis) @ d).normalized()
        nd.z = max(nd.z, -0.1)
        tree(bm, tip, nd.normalized(), L * rng_.uniform(0.6, 0.78), r * 0.62, depth - 1, rng_, tips)


def face_frame(n_out):
    """(right, out) unit vectors of a wall face with horizontal outward normal n_out: right = out x Z."""
    out = Vector(n_out).normalized()
    return out.cross(Vector((0, 0, 1))).normalized(), out


def _fbox(bm, p, r, out, along_r, along_out, along_z):
    """An axis box sized along a face's right / out directions (faces are axis aligned here)."""
    return kit.box(bm, p, (abs(r.x) * along_r + abs(out.x) * along_out, abs(r.y) * along_r + abs(out.y) * along_out,
                           along_z))


def lancet(bm, c, n_out, w=1.5, h=4.2, key="win_red"):
    """A framed twin-light gothic window on a wall face: two glowing pointed lights and a glowing roundel above them
    (glow, 3 cm proud of the wall) inside a stone frame: jambs, sill, mullion and a pointed hood (stone, 9-30 cm proud).
    c: the window centre ON the wall surface; n_out: the wall's outward normal."""
    r, out = face_frame(n_out)
    c = Vector(c)
    up = Vector((0, 0, 1))
    gl = c + out * 0.03
    for s in (-1, 1):
        pc = gl + r * (s * w * 0.25)
        glow(_fbox(GW, pc - up * 0.25, r, out, w * 0.38, 0.06, h * 0.62), key, GW)
        glow(kit.cone(GW, pc + up * (h * 0.31 - 0.25), pc + up * (h * 0.31 + 0.45), w * 0.21, segs=4), key, GW)
    glow(_fbox(GW, gl + up * (h * 0.42), r, out, w * 0.3, 0.06, w * 0.3), key, GW)
    fr = c + out * 0.09
    setmat(_fbox(bm, fr + r * (w / 2 + 0.1), r, out, 0.22, 0.2, h + 0.3), 1)              # jambs
    setmat(_fbox(bm, fr - r * (w / 2 + 0.1), r, out, 0.22, 0.2, h + 0.3), 1)
    setmat(_fbox(bm, fr - up * (h / 2 + 0.12), r, out, w + 0.5, 0.3, 0.22), 1)            # sill
    setmat(_fbox(bm, fr - up * 0.2, r, out, 0.12, 0.16, h * 0.7), 1)                      # mullion
    top = fr + up * (h / 2 + 0.15)
    for s in (-1, 1):                                                                      # pointed hood: two bars
        setmat(kit.cyl(bm, top + r * (s * (w / 2 + 0.2)), top + up * (w * 0.55), 0.11, segs=5), 1)


def rose(bm, c, n_out, radius=1.8, key="rose_red"):
    """A rose window: a glowing disc behind stone tracery (a ring of blocks, 8 spokes, a boss)."""
    r, out = face_frame(n_out)
    c = Vector(c)
    up = Vector((0, 0, 1))
    glow(kit.cyl(GW, c + out * 0.02, c + out * 0.05, radius, segs=24), key, GW)
    for i in range(20):                                                                    # the ring
        a = i * 2 * math.pi / 20
        p = c + out * 0.14 + (r * math.cos(a) + up * math.sin(a)) * (radius + 0.12)
        setmat(_fbox(bm, p, r, out, 0.45, 0.26, 0.45), 1)
    for i in range(8):                                                                     # spokes
        a = i * math.pi / 4 + math.pi / 8
        d = r * math.cos(a) + up * math.sin(a)
        setmat(kit.cyl(bm, c + out * 0.12 + d * 0.25, c + out * 0.12 + d * radius, 0.07, segs=4), 1)
    setmat(kit.cyl(bm, c + out * 0.05, c + out * 0.25, 0.35, segs=10), 1)                  # boss


# ---------------------------------------------------------------- the cathedral (SM_HwFacade: stone, dark stone, bark)
MOUTHS = []                                     # laser apertures: the front gargoyles' open mouths


def gargoyle(bm, base, facing):
    """A crouching gargoyle on a parapet corner: body, head with an open jaw (the laser aperture is between the jaws),
    horns, folded wings, red eyes. facing: +-1 along Y. Returns the mouth point."""
    b, f = Vector(base), facing
    fwd = Vector((0, f, 0))
    setmat(kit.box(bm, b + Vector((0, 0, 0.55)), (1.0, 1.3, 1.1), pitch=0.25 * f), 1)          # body
    setmat(kit.box(bm, b + fwd * 0.55 + Vector((0, 0, 0.25)), (0.7, 0.5, 0.5)), 1)             # haunches
    head = b + fwd * 1.15 + Vector((0, 0, 1.15))
    setmat(kit.box(bm, head, (0.62, 0.6, 0.5)), 1)
    setmat(kit.box(bm, head + fwd * 0.5 + Vector((0, 0, 0.14)), (0.5, 0.6, 0.16), pitch=-0.35 * f), 1)   # upper jaw
    setmat(kit.box(bm, head + fwd * 0.45 + Vector((0, 0, -0.2)), (0.46, 0.5, 0.12), pitch=0.45 * f), 1)  # lower jaw
    for hx in (-0.2, 0.2):
        setmat(kit.cone(bm, head + Vector((hx, -0.05 * f, 0.22)), head + Vector((hx * 1.6, -0.35 * f, 0.75)), 0.08,
                        segs=5), 1)
        glow(kit.box(GE, head + Vector((hx * 0.9, 0.31 * f, 0.08)), (0.1, 0.02, 0.07)), "eyes", GE)
    for wx in (-1, 1):                                                                           # wings
        setmat(kit.box(bm, b + Vector((wx * 0.65, -0.25 * f, 1.25)), (0.9, 0.12, 1.4), roll=wx * 0.5, pitch=-0.2 * f), 1)
    return head + fwd * 0.82


def crypt_glow(ax, aw, atop, y=44.45):
    """v6: the doorway the Horseman rides into glows (the user, 2026-10-10: "can we make where the headless horseman
    rides into the crypt glow?"). A veil of light just inside the back wall fills the opening: nested pointed arches,
    deep green at the edges to a pale core low in the middle. It is part of the always-on glow (SM_HwGlow): it flickers
    softly in game, and in the bake it lights the jambs and the ground outside. Opaque, facing out: he rides into it
    and is gone (the mod hides him further in)."""
    def resample(pts, n):
        seg = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
        total, out, i, acc = sum(seg), [], 0, 0.0
        for k in range(n):
            s = total * k / (n - 1)
            while i < len(seg) - 1 and acc + seg[i] < s:
                acc += seg[i]
                i += 1
            t = 0.0 if seg[i] == 0 else min(1.0, (s - acc) / seg[i])
            out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t))
        return out
    w0, top0 = aw / 2 + 0.4, atop + 0.4
    shapes = [[(-w0, FIELD_Z), (-w0, top0), (w0, top0), (w0, FIELD_Z)]]
    for w in (2.0, 1.65, 1.3, 0.95, 0.65, 0.4):                    # nested arches, springing at 1.5 w (apex 2.7 w)
        shapes.append([(-w, FIELD_Z)] + pointed_arch(w, FIELD_Z + 1.5 * w, 10) + [(w, FIELD_Z)])
    n = 40
    rings = [[G.verts.new((ax + x, y, z)) for x, z in resample(s, n)] for s in shapes]
    keys = [f"crypt_{i}" for i in range(CRYPT_SHADES)]
    made = {k: [] for k in keys}
    for k in range(len(rings) - 1):
        a, b = rings[k], rings[k + 1]
        made[keys[k]] += [G.faces.new((a[i], a[i + 1], b[i + 1], b[i])) for i in range(n - 1)]
    core, c = rings[-1], G.verts.new((ax, y, FIELD_Z + 0.3))
    made[keys[-1]] += [G.faces.new((core[i], core[i + 1], c)) for i in range(n - 1)] + [G.faces.new((core[-1], core[0], c))]
    for key, fs in made.items():
        for f in fs:
            f.normal_update()
            if f.normal.y < 0:
                f.normal_flip()
        glow(fs, key)
    log(f"crypt glow: {sum(len(v) for v in made.values())} faces in the rider's doorway (x {ax - aw / 2:.1f}..{ax + aw / 2:.1f})")


def build_facade():
    """Two meshes, so the big walls keep their texel density: SM_HwFacade (towers, walls, gable, buttress and pilaster
    blocks, the portal, the spires: 4096 bake) and SM_HwFacadeDetail (window frames, rose tracery, crenellations,
    pinnacles, crockets, rubble, parapet, capitals, wedges, gargoyles, the oaks: 2048 bake). Thousands of small islands
    in one atlas left v1's first facade at 25% UV coverage."""
    bm, bd = bmesh.new(), bmesh.new()
    S, SD, BK = 0, 1, 2
    win_keys = ("win_red", "win_purple", "win_green", "win_amber")
    for sx in (-1, 1):
        cx = 24 * sx
        setmat(kit.box(bm, (cx, 18, (35 + FIELD_Z) / 2), (8, 8, 35 - FIELD_Z)), S)        # tower, field to z 35
        for k in range(6):                                                                  # crenellations
            for side in (-1, 1):
                setmat(kit.box(bd, (cx + (k - 2.5) * 1.4, 18 + side * 3.6, 35.6), (0.8, 0.8, 1.2)), S)
                setmat(kit.box(bd, (cx + side * 3.6, 18 + (k - 2.5) * 1.4, 35.6), (0.8, 0.8, 1.2)), S)
        for k in range(3):                                                                  # string courses
            setmat(kit.box(bm, (cx, 18, 2 + 11 * k), (8.6, 8.6, 0.5)), SD)
        setmat(kit.box(bm, (cx, 13.3, 16), (9.5, 1.6, 0.5)), SD)                           # balconies (rig)
        setmat(kit.box(bm, (cx, 13.3, 26), (9.5, 1.6, 0.5)), SD)
        for bx in (cx - 3.4, cx + 3.4):                                                     # front buttresses, 3 setbacks
            for z0, z1, dep in ((FIELD_Z, 9.0, 1.4), (9.0, 19.0, 1.0), (19.0, 29.0, 0.6)):
                setmat(kit.box(bm, (bx, 14 - dep / 2, (z0 + z1) / 2), (1.2, dep, z1 - z0)), SD)
                setmat(wedge_y(bd, bx - 0.6, bx + 0.6, 14.0, dep, z1, z1 + dep * 0.9), SD)
        for bx, by in ((cx - 3.6, 14.4), (cx + 3.6, 14.4), (cx - 3.6, 21.6), (cx + 3.6, 21.6)):   # pinnacles
            setmat(kit.cone(bd, (bx, by, 35), (bx, by, 39.5), 0.7, segs=6), S)
        for z in (5.0, 14.0, 23.0):                                                         # framed windows
            for wx in (-1.7, 1.7):
                wb = bmesh.new()
                lancet(wb, (cx + wx, 14.0, z), (0, -1, 0), key=rng.choice(win_keys))
                bm_merge(bd, wb)
            for wy in (16.0, 20.0):
                for face_x, n_out, keys in ((sx * 20.0, (-sx, 0, 0), ("win_purple", "win_green")),
                                            (sx * 28.0, (sx, 0, 0), win_keys)):
                    wb = bmesh.new()
                    lancet(wb, (face_x, wy, z), n_out, key=rng.choice(keys))
                    bm_merge(bd, wb)
        rb = bmesh.new()
        rose(rb, (cx, 14.0, 30.6), (0, -1, 0), key="rose_red")                              # rose window
        bm_merge(bd, rb)
    setmat(kit.cone(bm, (-24, 18, 35), (-24, 18, 46), 3.6, segs=8), S)                     # left spire whole
    for k in range(8):                                                                      # crockets up its edges
        a = k * math.pi / 4 + math.pi / 8
        for t in (0.25, 0.5, 0.75):
            p = Vector((-24, 18, 35)) + Vector((math.cos(a) * 3.6 * (1 - t), math.sin(a) * 3.6 * (1 - t), 11 * t))
            setmat(kit.cone(bd, p, p + Vector((math.cos(a) * 0.5, math.sin(a) * 0.5, 0.45)), 0.18, segs=4), S)
    setmat(kit.cyl(bm, (24, 18, 35), (24, 18, 39.5), 3.6, segs=8, r2=2.2), S)              # right spire snapped
    for k in range(7):
        a = k * 2 * math.pi / 7
        setmat(kit.box(bd, (24 + 1.7 * math.cos(a), 18 + 1.7 * math.sin(a), 39.8 + rng.uniform(0, 1.8)),
                       (rng.uniform(0.6, 1.2), rng.uniform(0.6, 1.1), rng.uniform(1.0, 2.4)), yaw=a,
                       pitch=rng.uniform(-0.35, 0.35)), S)
    for k in range(9):                                                                      # fallen rubble on the parapet
        setmat(kit.box(bd, (24 + rng.uniform(-2.8, 2.8), 18 + rng.uniform(-2.8, 2.8), 35.25),
                       (rng.uniform(0.3, 0.8),) * 2 + (rng.uniform(0.25, 0.5),), yaw=rng.uniform(0, 3)), SD)
    setmat(kit.box(bm, (0, 14.5, (21 + FIELD_Z) / 2), (40, 1.0, 21 - FIELD_Z)), S)          # nave wall, field to z 21
    setmat(prism(bm, (0, 14.5, 21), 40, 1.0, 5), S)                                         # gable to z 26
    for i in range(13):                                                                     # parapet blocks on the rakes
        t = (i + 0.5) / 13
        for s in (-1, 1):
            setmat(kit.box(bd, (s * 20 * (1 - t), 14.5, 21 + 5 * t + 0.35), (0.7, 1.15, 0.7)), S)
    setmat(kit.box(bd, (0, 14.5, 26.9), (0.35, 0.35, 2.0), roll=0.12), SD)                   # broken cross at the peak
    setmat(kit.box(bd, (0.15, 14.5, 27.4), (1.0, 0.3, 0.3), roll=0.12), SD)
    for sx in (-1, 1):                                                                      # roofless nave (aerial, drone)
        for k in range(6):
            h = 11 - rng.uniform(0, 5) * (k % 2)
            setmat(kit.box(bm, (sx * 14.5, 17.5 + 5 * k, (h + FIELD_Z) / 2), (1.0, 5.0, h - FIELD_Z)), SD)
    for k in range(6):
        h = 9 - rng.uniform(0, 4) * (k % 2)
        if k != 1:
            setmat(kit.box(bm, (-12.5 + 5 * k, 45.0, (h + FIELD_Z) / 2), (5.0, 1.0, h - FIELD_Z)), SD)
            continue
        # v4: the stream intro's rider gallops into the cathedral through this ruined doorway (x -9.5..-5.5, 5.5 m
        # high) and vanishes into the dark nave, where the mod hides him (hw_intro_path's exit)
        ax, aw, atop = -7.5, 4.0, FIELD_Z + 5.5
        for px in (-10.0, ax + aw / 2):                                                    # the piers
            pw = (ax - aw / 2) - (-10.0) if px == -10.0 else (-5.0) - (ax + aw / 2)
            setmat(kit.box(bm, (px + pw / 2, 45.0, (h + FIELD_Z) / 2), (pw, 1.0, h - FIELD_Z)), SD)
        setmat(kit.box(bm, (ax, 45.0, (h + atop) / 2), (aw, 1.0, h - atop)), SD)                 # over the opening
        crypt_glow(ax, aw, atop)                                                           # v6: it glows
    for sx in (-1, 1):                                                                      # pilasters, portal to towers
        for z0, z1, dep in ((FIELD_Z, 8.0, 1.2), (8.0, 15.0, 0.9), (15.0, 20.0, 0.6)):
            setmat(kit.box(bm, (sx * 17.6, 14.0 - dep / 2, (z0 + z1) / 2), (1.0, dep, z1 - z0)), SD)
            setmat(wedge_y(bd, sx * 17.6 - 0.5, sx * 17.6 + 0.5, 14.0, dep, z1, z1 + dep * 0.9), SD)
    for k in range(4):                                                                      # portal: 4 orders
        y, w, r = 14.0 - 1.1 * k, 12.5 + 1.0 * k, 0.45 + 0.05 * k
        pts = pointed_arch(w, 7.0)
        for (x0, z0), (x1, z1) in zip(pts[:-1], pts[1:]):
            setmat(kit.cyl(bm, (x0, y, z0), (x1, y, z1), r, segs=8, cap=False), S)
        for sx in (-1, 1):
            setmat(kit.cyl(bm, (sx * w, y, FIELD_Z), (sx * w, y, 7.0), r, segs=8), S)       # shafts
            setmat(kit.box(bd, (sx * w, y, 7.0), (r * 2.6, r * 2.6, 0.45)), SD)             # capitals
            setmat(kit.box(bd, (sx * w, y, DECK_Z + 0.2), (r * 2.6, r * 2.6, 0.4)), SD)     # bases
            setmat(kit.box(bm, (sx * (w + 0.9), y, (7 + FIELD_Z) / 2), (1.8, 1.0, 7 - FIELD_Z)), SD)
    setmat(kit.cyl(bm, (0, 14.1, 20), (0, 13.75, 20), 3.3, segs=36), SD)                    # clock backing
    for sx in (-1, 1):                                                                      # gargoyles at the tower tops
        for gx in (20, 28):
            for gy in (14, 22):
                gb = bmesh.new()
                mouth = gargoyle(gb, (sx * gx, gy, 35.6), -1 if gy == 14 else 1)
                bm_merge(bd, gb)
                if gy == 14:
                    MOUTHS.append((sx, gx, mouth))
    oak_tips = []
    for sx in (-1, 1):                                                                      # two giant dead oaks
        tb, tips = bmesh.new(), []
        tree(tb, Vector((sx * OAK_X, 6, FIELD_Z)), Vector((sx * 0.08, 0.05, 1)).normalized(), 13, 1.3, 4, rng, tips)
        for f in tb.faces:
            f.material_index = BK
        bm_merge(bd, tb)
        oak_tips += rng.sample(tips, 10)
    ob = new_obj("SM_HwFacade", bm, (STONE, STONE_DARK, BARK))
    obd = new_obj("SM_HwFacadeDetail", bd, (STONE, STONE_DARK, BARK))
    return ob, obd, oak_tips


def build_clock():
    for i in range(36):                                                                    # clock: dotted rim
        a = i * 2 * math.pi / 36
        glow(kit.box(G, (3.1 * math.cos(a), 13.7, 20 + 3.1 * math.sin(a)), (0.18, 0.1, 0.18)), "clock_rim")
    for i in range(12):
        a = i * 2 * math.pi / 12
        glow(kit.box(G, (2.6 * math.cos(a), 13.7, 20 + 2.6 * math.sin(a)), (0.3, 0.1, 0.3)), "clock_rim")
    glow(kit.cyl(G, (0, 13.62, 20), (0, 13.55, 20), 0.22, segs=10), "clock_rim")       # centre cap
    glow(kit.cyl(CF, (0, 13.74, 20), (0, 13.72, 20), 3.0, segs=36), "clock_face", CF)
    ch = bmesh.new()                                                                     # the hands, both at 12 at rest
    uv0, hid = ch.loops.layers.uv.new("UVMap"), ch.loops.layers.uv.new("HandId")
    for hand_id, (w, L, y) in enumerate(((0.22, 1.9, 13.65), (0.14, 2.7, 13.6))):
        for f in kit.box(ch, (0, y, 20 + L / 2 - 0.15), (w, 0.08, L)):
            for lp in f.loops:
                lp[uv0].uv = pal_uv("clock_hand")
                lp[hid].uv = (float(hand_id), 0.0)
    return new_obj("SM_HwClockHands", ch)


# ---------------------------------------------------------------- the rig: moving heads, searchlights (SM_HwRig)
def moving_head(rig, base, target, key):
    """dino_stage.moving_head: base, yoke and head pointed at target; its lens is a glowing disc (palette key). Adds the
    frozen beam (to the target) and a lens halo. Returns the lens centre."""
    base, target = Vector(base), Vector(target)
    head_c = base + Vector((0, 0, 0.42))
    aim = (target - head_c).normalized()
    yaw = math.atan2(aim.x, -aim.y)
    R = Matrix.Rotation(yaw, 4, "Z")

    def rbox(c, sz):
        bmesh.ops.create_cube(rig, size=1.0, matrix=Matrix.Translation(base) @ R @ Matrix.Translation(c)
                              @ Matrix.Diagonal(Vector((*sz, 1.0))))
    rbox((0, 0, 0.08), (0.42, 0.42, 0.16))
    for s_ in (-1, 1):
        rbox((s_ * 0.22, 0, 0.36), (0.06, 0.12, 0.42))
    kit.cyl(rig, head_c - aim * 0.22, head_c + aim * 0.2, 0.17, segs=10, r2=0.2)
    lens = head_c + aim * 0.205
    rot = Vector((0, 0, 1)).rotation_difference(aim).to_matrix().to_4x4()
    ret = bmesh.ops.create_circle(GL, cap_ends=True, segments=12, radius=0.16,
                                  matrix=Matrix.Translation(lens + aim * 0.01) @ rot)
    glow(list({f for v in ret["verts"] for f in v.link_faces}), key, GL)
    col = HEAD_BEAM[key]
    L = (target - lens).length
    beam(BEAMS, lens + aim * 0.05, aim, L, 0.22, 0.22 + 0.055 * L, col)
    halo(HALOS, lens + aim * 0.15, 0.9, col, axis=aim)
    return lens


def searchlight(rig, base, dirs, col):
    base = Vector(base)
    kit.box(rig, base + Vector((0, 0, 0.3)), (1.2, 1.2, 0.6))
    for d in dirs:
        d = Vector(d).normalized()
        c = base + Vector((0, 0, 1.0))
        kit.cyl(rig, c - d * 0.6, c + d * 0.6, 0.55, segs=12)
        beam(SEARCH, c + d * 0.65, d, 320.0, 1.0, 14.0, col)
        halo(HALOS, c + d * 0.8, 2.2, col, axis=d)


def build_rig():
    rig = bmesh.new()
    kit.truss(rig, (-14, TRUSS_Y, 16.5), (14, TRUSS_Y, 16.5), size=0.6, step=1.2)          # portal truss
    for sx in (-1, 1):                                                                       # its pick-up chains
        kit.cyl(rig, (sx * 13.5, TRUSS_Y, 16.8), (sx * 13.9, 12.6, 22.5), 0.03, segs=4)
    heads = []
    targets = [(-38, -22), (-26, -40), (-12, -55), (4, -30), (-4, -30), (12, -55), (26, -40), (38, -22)]
    keys = ["orange", "purple", "green", "win_amber"]
    for sx in (-1, 1):                                                                       # tower balconies: 2 x 4 each
        for zb in (16.25, 26.25):
            for k in range(4):
                tx, ty = targets[k + (4 if sx > 0 else 0)]
                f = 1.0 if zb < 20 else 0.7
                heads.append(((24 * sx + (k - 1.5) * 2.2, 13.0, zb), (tx * f, ty, FIELD_Z), keys[(k + int(zb)) % 4]))
    for k in range(6):                                                                       # on the portal truss
        x = -12.5 + k * 5
        heads.append(((x, TRUSS_Y, 16.82), (x * 1.8, -18 - 4 * (k % 3), FIELD_Z), ["orange", "purple"][k % 2]))
    for sx in (-1, 1):                                                                       # deck uplights on the facade
        heads.append(((sx * 13.6, 9.0, DECK_Z), (sx * 10.5, 14.0, 22.0), "orange"))
        heads.append(((sx * 19.4, 9.0, DECK_Z), (sx * 23.0, 14.0, 30.0), "purple"))
    for base, target, key in heads:
        hb_ = bmesh.new()
        moving_head(hb_, base, target, key)
        bm_merge(rig, hb_)
    hb = Vector((0.0, 10.15, 25.2))                                                          # portal laser housing
    kit.box(rig, hb, (0.5, 0.46, 0.3))
    for ux, uy, dirs, col in ((-32, -92, ((-0.35, -0.25, 1), (0.15, 0.3, 1)), "moon"),
                              (32, -92, ((0.35, -0.25, 1), (-0.15, 0.3, 1)), "moon"),
                              (-31, 24, ((-0.3, 0.2, 1), (-0.05, -0.25, 1)), "uv"),
                              (31, 24, ((0.3, 0.2, 1), (0.05, -0.25, 1)), "uv")):
        searchlight(rig, (ux, uy, FIELD_Z), dirs, col)
    log(f"rig: {len(heads)} moving heads, 4 searchlights")
    return new_obj("SM_HwRig", rig, (IRON,)), hb


# The units are written in the Dino's laser format (club_lasers.py's copy of grounds/atmosphere.py laser_mesh: raw
# values; dino_materials.laser_show reads every V back as 1 - v, as Unreal's FBX import flips V on all channels) and
# moved by laser_show from show.py's pattern program (T_HwLaserProg / T_HwLaserLib), each group's level from show.py's
# cue table (T_HwLaserCues rows 3-7, 11, 12, 14, 15), all on the hook's show bus (MPC_HwShow: the song's bars, its
# variant, drum hits, bass and drops). Groups = the engine's families: 0 fan = the portal; 1-4 horns = the gargoyles
# (left outer, left inner, right inner, right outer); 5 towers = the front pinnacles' sky lasers; 6 lip = the deck-front
# units; 7 mouth = the back crypt towers' skull eyes; 8 delay = the front crypt towers'. The engine sweeps pan AND tilt
# over -1..1 (its hit, bass and drop offsets are clamped inside that), so each beam's length is solved for the whole
# sweep: above 3 m over the deck, >= 4.9 m from the DJ's head (Dino's rule), and 0.4 m short of the set and the grounds
# (a BVH of their meshes).
# v7 (2026-10-11; the user, after visiting v6: "make the lasers longer like how we did with reactor"; Reactor v8's recipe,
# club_lasers.py): v3-v6 cut each beam where its lowest pose reached raised hands over the field (2.5 m up), so the
# beams aimed at the crowd ended in mid-air, and the texture's fade was stretched over each beam (v 0..0.85), so a tip
# had about 4 % of the aperture's light. Now a beam runs LAND_MARGIN past the ground (FIELD_Z: the field and the far
# ground hide the rest, depth test) in its farthest-landing pose, or to its cap when a pose never lands; it goes
# through the crowd. The fade and the width go by the metre (V_PER_M, WIDE_AT); a beam longer than LASER_V1 / V_PER_M
# keeps v6's stretch, so none gets dimmer than before.
LASER_GAP, LASER_W, LASER_CORE, LASER_V1 = 0.1, (0.02, 0.10), 0.35, 0.85   # atmosphere's: crisp lines that fade out
WIDE_AT, V_PER_M, LASER_SEG = 15.0, 0.0125, 2.5  # v7 (club_lasers v8): full width from 15 m; 75 % light at 10 m, 43 %
                                                # at 30 m; 2.5 m segments while widening keep the profile centred
LAND_MARGIN = 1.5                               # v7: past the farthest landing (the sampled poses can miss the farthest)
DECK_CLEAR = DECK_Z + 3.0                       # over the deck (y -4.5..14, |x| <= 25): nothing lower
DJ_CLEAR = 4.9
LASER_MIN_LEN = 4.0                             # a beam this short after solving is dropped ...
LASER_MIN_SHARE = 0.4                           # ... and one under 40% of its unit's longest (a stub in its fan)
LASER_SOLVE = tuple(i / 6.0 for i in range(-6, 7))       # 13 x 13 poses over the sweep when solving ...
LASER_VERIFY = tuple(i / 5.0 for i in range(-5, 6))      # ... 11 x 11 (other poses between them) when verifying
LASER_SWEPT = tuple(i / 12.0 for i in range(-12, 13))    # v7: 25 x 25 for the solver's swept surface (the longer beams
                                                         # crossed the FOH fence between 13 x 13's grid lines)
LASER_SWEPT_FROM = 0.5                          # swept surfaces start here: the unit's own housing / jaws / skull are behind
LIP_X = (-15.0, -9.0, -3.0, 3.0, 9.0, 15.0)     # deck-front units, between the flame jets (FIRE_X)
LIP_Y, LIP_Z = -4.25, DECK_Z + 1.35             # housing centre: on 1.2 m posts at the deck's front edge (y -4.5)
LIP_BOX = (0.5, 0.46, 0.3)                      # housing depth (along its heading), width, height (atmosphere's)


def lip_aim(x):
    return Vector((x * 1.8, -40.0, 5.5))


def lip_unit(x):
    """(housing centre, horizontal heading) of the deck-front unit at x."""
    c = Vector((x, LIP_Y, LIP_Z))
    f = lip_aim(x) - c
    f.z = 0.0
    return c, f.normalized()


def laser_units(portal_apex):
    """[(name, group, pivot, rest aim point, beams, degrees between beams, pan amp, tilt amp, length cap)]."""
    U = [("portal", 0, Vector(portal_apex) + Vector((0.0, -0.26, 0.0)), Vector((0.0, -26.0, 4.5)), 17, 3.6, 10.0, 5.0,
          60.0)]
    garg = {(-1, 28): (1, -15.0, -22.0), (-1, 20): (2, -6.0, -25.0), (1, 20): (3, 6.0, -25.0), (1, 28): (4, 15.0, -22.0)}
    for sx, gx, mouth in MOUTHS:
        grp, ax, ay = garg[(sx, gx)]
        U.append((f"garg {sx * gx:+d}", grp, Vector(mouth), Vector((ax, ay, 4.0)), 11, 3.6, 8.0, 5.0, 60.0))
    for sx in (-1, 1):                          # the front-outer pinnacles' tips (build_facade: cones to z 39.5)
        U.append((f"pinnacle {sx:+d}", 5, Vector((sx * 27.6, 14.4, 39.75)), Vector((sx * 70.0, -75.0, 85.0)), 9, 7.0,
                  15.0, 10.0, 120.0))
    for x in LIP_X:
        c, f = lip_unit(x)
        U.append((f"lip {x:+.0f}", 6, c + f * (LIP_BOX[0] / 2 + 0.01), lip_aim(x), 7, 5.0, 12.0, 6.0, 42.0))
    eye_z = hwi.TOWER_TOP + 0.14 + 0.5 * 1.3 - STAGE_DROP          # hw_infrastructure.tower: the skull's eye sockets
    for tx, ty in hwi.TOWERS:                   # the skulls face the stage: beams from between the eyes, over the DJ
        back = ty < -50.0
        U.append((f"skull {tx:+.0f},{ty:.0f}", 7 if back else 8, Vector((tx, ty - 0.05 + 0.826 + 0.25, eye_z)),
                  Vector((tx * 0.1 if back else tx * 0.3, 4.0, 15.0 if back else 13.0)), 7, 3.0 if back else 4.0,
                  8.0 if back else 10.0, 4.0, 85.0 if back else 60.0))
    return U


def _bvh(obstacles):
    """(BVH, vertices, polygons) of the obstacles' meshes (built in place: world coordinates)."""
    verts, polys = [], []
    for ob in obstacles:
        off = len(verts)
        verts += [v.co.copy() for v in ob.data.vertices]
        polys += [[off + i for i in p.vertices] for p in ob.data.polygons]
    return BVHTree.FromPolygons(verts, polys), verts, polys


def _swept_tree(pivot, d, pan, tilt, length, poses):
    """The surface a beam sweeps along the grid lines of poses x poses: planar quads between neighbouring poses (along P
    and along Q), from LASER_SWEPT_FROM out to the beam's end. A thin member crossing the swept region crosses them."""
    n = len(poses)
    verts, polys = [], []
    for P in poses:
        for Q in poses:
            v = _pose_dir(d, P, Q, pan, tilt)
            verts += [pivot + v * LASER_SWEPT_FROM, pivot + v * length]

    def vid(i, j, far):
        return (i * n + j) * 2 + far
    for i in range(n):
        for j in range(n):
            if i + 1 < n:
                polys.append([vid(i, j, 0), vid(i + 1, j, 0), vid(i + 1, j, 1), vid(i, j, 1)])
            if j + 1 < n:
                polys.append([vid(i, j, 0), vid(i, j + 1, 0), vid(i, j + 1, 1), vid(i, j, 1)])
    return BVHTree.FromPolygons(verts, polys)


def _swept_crossing(ob, pivot, d, pan, tilt, length, poses):
    """The obstacle vertex nearest the pivot among the polygons the swept surface crosses, as (distance, point), or None."""
    obvh, ov, op = ob
    best = None
    for a, _ in obvh.overlap(_swept_tree(pivot, d, pan, tilt, length, poses)):
        for vi in op[a]:
            dist = (ov[vi] - pivot).length
            if best is None or dist < best[0]:
                best = (dist, ov[vi])
    return best


def _pose_dir(d, P, Q, pan_amp, tilt_amp):
    """atmosphere.laser_pose_pq for a direction (club_lasers.pose_dir): about Z by pan_amp P, then about normalize(h x Z)
    by tilt_amp Q (h = the panned direction's horizontal part); + Q raises the beam."""
    v = Matrix.Rotation(math.radians(pan_amp * P), 3, "Z") @ d
    h = Vector((v.x, v.y, 0.0))
    if h.length > 1e-6:
        v = Matrix.Rotation(math.radians(tilt_amp * Q), 3, h.normalized().cross(Vector((0.0, 0.0, 1.0)))) @ v
    return v


def _laser_problem(p):
    """Why a beam point is not allowed (None if it is). v7: under the ground (it has landed: hidden) is allowed."""
    if p.z < FIELD_Z:
        return None
    if -4.5 <= p.y <= 14.0 and abs(p.x) <= 25.0 and p.z < DECK_CLEAR:
        return "the deck (< 3 m)"
    if (p - DJ_HEAD).length < DJ_CLEAR:
        return "the DJ's head"
    return None


def _laser_length(ob, pivot, d, pan, tilt, cap, poses, step=0.25, margin=0.4):
    """v7: LAND_MARGIN past the farthest pose's landing on the ground (or cap, when a pose never lands within it), but
    short of everything a pose must not reach (the set, the rules), and with a swept surface between the poses that
    crosses no obstacle: (length, what limits it, where)."""
    bvh = ob[0]
    lands, best, why_best, where = [], cap, "cap", None
    for P in poses:
        for Q in poses:
            v = _pose_dir(d, P, Q, pan, tilt)
            land = (FIELD_Z - pivot.z) / v.z if v.z < -1e-6 else None
            land = land if land is not None and land <= cap else None
            lands.append(land)
            reach = min(best, land if land is not None else cap)
            loc, _, _, dist = bvh.ray_cast(pivot + v * LASER_GAP, v, reach)
            if loc is not None and LASER_GAP + dist - margin < best:
                best, why_best, where = max(0.0, LASER_GAP + dist - margin), "the set", loc
            t = LASER_GAP
            while t <= min(best, reach):
                why = _laser_problem(pivot + v * t)
                if why:
                    best, why_best, where = max(0.0, t - step), why, pivot + v * t
                    break
                t += step
    if all(x is not None for x in lands) and max(lands) + LAND_MARGIN < best:
        best, why_best, where = max(lands) + LAND_MARGIN, "lands", None
    for _ in range(60):                                                  # thin members between the sampled poses
        if best <= LASER_SWEPT_FROM + 0.1:
            return 0.0, why_best, where
        hit = (_swept_crossing(ob, pivot, d, pan, tilt, best, LASER_SWEPT)            # v7: and the verify grid's
               or _swept_crossing(ob, pivot, d, pan, tilt, best, LASER_VERIFY))       # chords (they cut corners)
        if hit is None:
            break
        best, why_best, where = min(best * 0.97, hit[0] - margin), "the set (swept)", hit[1]
    return best, why_best, where


def build_lasers(portal_apex, obstacles):
    """Solve every beam against the obstacles, then write the beams and each unit's aperture glow into LASERS."""
    ob = _bvh(obstacles)
    units = laser_units(portal_apex)
    xs = [u[2].x for u in units]
    x0, x1 = min(xs), max(xs)
    lay = [LASERS.loops.layers.uv[k] for k in LASER_UV]
    ncol, col = len(BEAM_COLS), BEAM_COLS.index("white")
    bu0, bu1 = (col + 0.5 - 0.48 * LASER_CORE) / ncol, (col + 0.5 + 0.48 * LASER_CORE) / ncol
    au0, au1 = (col + 0.02) / ncol, (col + 0.98) / ncol

    def stamp(faces, values):
        for fa in faces:
            for lp in fa.loops:
                for ly, val in zip(lay, values):
                    lp[ly].uv = val
    t0, dropped = time.time(), 0
    for ui, (name, grp, pivot, aim, n, step_deg, pan, tilt, cap) in enumerate(units):
        rest = (aim - pivot).normalized()
        perp = Vector((0.0, 0.0, 1.0)).cross(rest).normalized()
        ux = (pivot.x - x0) / (x1 - x0)
        lens, whys, short, solved = [], {}, None, []
        for j in range(n):
            u = (j - (n - 1) / 2) / ((n - 1) / 2) if n > 1 else 0.0
            a = math.radians((j - (n - 1) / 2) * step_deg)
            d = (rest * math.cos(a) + perp * math.sin(a)).normalized()
            length, why, where = _laser_length(ob, pivot, d, pan, tilt, cap, LASER_SOLVE)
            whys[why] = whys.get(why, 0) + 1
            solved.append((j, u, d, length, why, where))
        longest = max(sl[3] for sl in solved)
        for j, u, d, length, why, where in solved:
            if length < max(LASER_MIN_LEN, LASER_MIN_SHARE * longest):
                dropped += 1
                continue
            if where is not None and (short is None or length < short[0]):
                short = (length, why, where)
            x = 0.5 + 0.02 * u if grp == 0 else ux
            ph = (0.37 * ui + 0.05 * j) % 1.0
            up = Vector((0, 0, 1)) if abs(d.z) < 0.95 else Vector((1, 0, 0))
            s0 = d.cross(up).normalized()
            run = length - LASER_GAP                                     # v7: width and fade by the metre
            vpm = min(V_PER_M, LASER_V1 / run)
            wide = min(run, WIDE_AT)
            ts = [0.0]
            while ts[-1] + LASER_SEG < wide - 1e-6:
                ts.append(ts[-1] + LASER_SEG)
            ts += [wide] + ([run] if run > wide + 1e-6 else [])
            faces = []
            for k in range(2):
                s = (Matrix.Rotation(math.pi * k / 2, 3, d) @ s0).normalized()
                for ta, tb in zip(ts, ts[1:]):
                    a, b = pivot + d * (LASER_GAP + ta), pivot + d * (LASER_GAP + tb)
                    w0, w1 = (LASER_W[0] + (LASER_W[1] - LASER_W[0]) * min(t / WIDE_AT, 1.0) for t in (ta, tb))
                    faces += kit.quad(LASERS, a - s * w0 / 2, a + s * w0 / 2, b + s * w1 / 2, b - s * w1 / 2,
                                      uvs=[(bu0, vpm * ta), (bu1, vpm * ta), (bu1, vpm * tb), (bu0, vpm * tb)])
            stamp(faces, ((pivot.x, pivot.y), (pivot.z, ph), (pan, tilt), (float(grp), u), (x, 0.0)))
            LASER_BEAMS.append(dict(name=f"{name}#{j}", pivot=pivot.copy(), d=d, length=length, pan=pan, tilt=tilt))
            lens.append(length)
        f = Vector((rest.x, rest.y, 0.0)).normalized()                  # the aperture glow: lights with its unit
        c = pivot + f * 0.004
        r = Vector((0.0, 0.0, 1.0)).cross(f).normalized() * LIP_BOX[1] * 0.62 / 2
        upv = f.cross(r).normalized() * LIP_BOX[2] * 0.36 / 2
        stamp(kit.quad(LASERS, c - r - upv, c + r - upv, c + r + upv, c - r + upv,
                       uvs=[(au0, 0.0), (au1, 0.0), (au1, 0.05), (au0, 0.05)]),
              ((pivot.x, pivot.y), (pivot.z, 0.0), (0.0, 0.0), (float(grp), 0.0), (ux, 1.0)))
        log(f"laser unit {name:14s} group {grp}: {len(lens)}/{n} beams, {min(lens, default=0):.1f}..{max(lens, default=0):.1f} m"
            f" (pivot {pivot.x:.1f},{pivot.y:.1f},{pivot.z:.1f}; limited by: "
            + ", ".join(f"{k} {v}" for k, v in sorted(whys.items())) + ")"
            + (f"; shortest {short[0]:.1f} m: {short[1]} at ({short[2].x:.1f},{short[2].y:.1f},{short[2].z:.1f})"
               if short else ""))
    log(f"lasers: {len(units)} units, {len(LASER_BEAMS)} beams ({dropped} dropped under {LASER_MIN_LEN:.0f} m), solved "
        f"over {len(LASER_SOLVE)}x{len(LASER_SOLVE)} poses in {time.time() - t0:.0f}s")
    return units


# ---------------------------------------------------------------- deck, riser, booth, barrier, props (SM_HwDeck)
FIRE_X = (-18.0, -12.0, -6.0, 6.0, 12.0, 18.0)
# v4, the crypt gate (the stream intro; the user, 2026-10-10: "On the back of the stage is a door, kinda like how a
# garage door comes up and leads out to the decks", chosen under the screen). A gothic gateway stands in front of the
# screen's lower middle, behind the DJ booth (the booth already hides that part of the picture from the crowd); behind
# it a small backstage crypt, lit by a red work lamp, where the user waits at the button during the intro. v5: two oak
# crypt doors on the jambs' hinges replace v4's roll-up door and its drum ("Like crypt doors"); they swing out.
GATE_Y, GATE_X, GATE_TOP = intro.GATE_Y, intro.GATE_X, intro.GATE_TOP   # shared with the video and the build
DOOR_Z0, DOOR_Z1 = DECK_Z + 0.01, GATE_TOP - 0.01   # the leaves clear the deck and the tympanum's underside by 1 cm
DOOR_STRAPS = (DOOR_Z0 + 0.42, (DOOR_Z0 + DOOR_Z1) / 2, DOOR_Z1 - 0.42)   # the strap hinges' heights
BOX_X, BOX_Y1, BOX_TOP = 2.4, 10.2, 2.9       # the backstage crypt: x +-2.4, y GATE_Y..10.2, the roof at z 2.9


def add_backstage(bm, ST, SD, IR, BN, WX):
    """The gateway's stone frame (pillars, pinnacles, the tympanum with a skull and a pointed gable, the doors' hinge
    plates on the jambs) and the backstage crypt (side walls, back wall, roof, the button's pedestal, candles) into the
    deck."""
    zb = DECK_Z
    for sx in (-1, 1):
        x = sx * (GATE_X + 0.35)
        setmat(kit.box(bm, (x, GATE_Y + 0.35, (zb + 3.4) / 2), (0.7, 0.7, 3.4 - zb)), ST)            # pillars
        setmat(kit.cone(bm, (x, GATE_Y + 0.35, 3.4), (x, GATE_Y + 0.35, 4.4), 0.32, segs=4), ST)     # pinnacles
        for zs in DOOR_STRAPS:                                                                      # hinge plates
            setmat(kit.box(bm, (sx * (GATE_X + 0.13), GATE_Y - 0.01, zs), (0.14, 0.02, 0.1)), IR)
        setmat(kit.box(bm, (sx * BOX_X, (GATE_Y + BOX_Y1) / 2, (zb + BOX_TOP) / 2),
                       (0.25, BOX_Y1 - GATE_Y, BOX_TOP - zb)), SD)                                   # the crypt's walls
    setmat(kit.box(bm, (0.0, GATE_Y + 0.15, (GATE_TOP + 3.0) / 2), (2 * GATE_X + 0.2, 0.3, 3.0 - GATE_TOP)), ST)
    setmat(prism(bm, (0.0, GATE_Y + 0.15, 3.0), 2 * GATE_X + 1.1, 0.3, 0.8), ST)                     # pointed gable
    sb = bmesh.new()
    skull(sb, (0.0, GATE_Y - 0.08, 2.45), 1.3, BN)                                                   # over the door
    bm_merge(bm, sb)
    setmat(kit.box(bm, (0.0, BOX_Y1, (zb + BOX_TOP) / 2), (2 * BOX_X + 0.25, 0.2, BOX_TOP - zb)), SD)   # back wall
    setmat(kit.box(bm, (0.0, (GATE_Y + BOX_Y1) / 2, BOX_TOP + 0.08), (2 * BOX_X + 0.5, BOX_Y1 - GATE_Y + 0.3, 0.16)), SD)
    bx, by, bz = intro.BUTTON
    setmat(kit.box(bm, (bx, by, (zb + bz - 0.07) / 2), (0.36, 0.36, bz - 0.07 - zb)), ST)            # the pedestal
    setmat(kit.box(bm, (bx, by, bz - 0.06), (0.44, 0.44, 0.04)), IR)
    for k, (cx, cy) in enumerate(((-1.9, 9.9), (-1.6, 9.95), (1.95, 8.2), (-2.0, 8.3), (1.9, 9.9))):  # candles
        hgt = 0.18 + 0.07 * (k % 3)
        setmat(kit.cyl(bm, (cx, cy, zb), (cx, cy, zb + hgt), 0.035, segs=6), WX)
        glow(kit.box(G, (cx, cy, zb + hgt + 0.03), (0.02, 0.02, 0.05)), "candle")
    setmat(kit.box(bm, (0.0, 9.6, BOX_TOP - 0.25), (0.3, 0.3, 0.2)), IR)                          # the work lamp


def build_gate():
    """SM_HwGate (v5): two oak crypt doors, baked shut (UVMap). Each leaf: a backing board and five front planks, three
    black iron strap hinges (studs, a diamond tip, a knuckle on the hinge axis) and a ring knocker on the front, three
    ledges and a Z-brace behind. Each turns about its jamb's vertical hinge at (side x GATE_X, GATE_Y) on MPC_HwShow
    DoorOpen (hw_materials.door_swing; intro.door_xy is the same rule): UV1 'GateData' u = the leaf's side (-1 left,
    +1 right). The leaves stop 6 mm short of x = 0, so no vertex sits on the line between them. SM_HwButton: the
    button's cap on the glow palette (hw_materials.intro_button colours it by IntroStep)."""
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap")
    data = bm.loops.layers.uv.new("GateData")
    z0, z1, y0, T = DOOR_Z0, DOOR_Z1, GATE_Y, intro.DOOR_T
    zc, hgt = (z0 + z1) / 2, z1 - z0
    for s in (-1, 1):
        lb = bmesh.new()                                      # one leaf, then its side into GateData
        xi, xo = s * 0.006, s * (GATE_X - 0.005)               # the meeting edge, the hinge edge
        w, xm = abs(xo - xi), (xi + xo) / 2
        setmat(kit.box(lb, (xm, y0 + 0.04 + (T - 0.04) / 2, zc), (w, T - 0.04, hgt)), 0)        # backing board
        pw = w / 5
        for k in range(5):                                                                      # planks, 1 cm grooves
            setmat(kit.box(lb, (xi + s * pw * (k + 0.5), y0 + 0.02, zc), (pw - 0.01, 0.04, hgt)), 0)
        L = 0.8 * w
        for zs in DOOR_STRAPS:                                                                  # strap hinges
            setmat(kit.box(lb, (xo - s * L / 2, y0 - 0.006, zs), (L, 0.012, 0.11)), 1)
            setmat(kit.box(lb, (xo - s * L, y0 - 0.006, zs), (0.13, 0.012, 0.13), roll=math.pi / 4), 1)
            for k in range(6):
                setmat(kit.box(lb, (xo - s * (0.08 + k * (L - 0.16) / 5), y0 - 0.018, zs), (0.035, 0.012, 0.035)), 1)
            setmat(kit.cyl(lb, (s * GATE_X, y0, zs - 0.08), (s * GATE_X, y0, zs + 0.08), 0.03, segs=8), 1)
        kx, kz, R = xi + s * 0.32, zc - 0.35, 0.11                                              # the ring knocker
        setmat(kit.box(lb, (kx, y0 - 0.008, kz + R), (0.14, 0.016, 0.14)), 1)
        ring = [(kx + R * math.sin(2 * math.pi * i / 12), y0 - 0.03, kz + R * math.cos(2 * math.pi * i / 12))
                for i in range(12)]
        for i in range(12):
            setmat(kit.cyl(lb, ring[i], ring[(i + 1) % 12], 0.014, segs=6), 1)
        for zl in DOOR_STRAPS:                                                                  # ledges behind
            setmat(kit.box(lb, (xm, y0 + T + 0.0175, zl), (w - 0.1, 0.035, 0.16)), 0)
        for za, zz in ((DOOR_STRAPS[0], DOOR_STRAPS[1]), (DOOR_STRAPS[1], DOOR_STRAPS[2])):    # the Z-brace
            ax, bx_ = xo - s * 0.12, xi + s * 0.12
            dx, dz = bx_ - ax, zz - za
            setmat(kit.box(lb, ((ax + bx_) / 2, y0 + T + 0.015, (za + zz) / 2), (math.hypot(dx, dz), 0.03, 0.12),
                           roll=math.atan2(-dz, dx)), 0)
        n0 = len(bm.faces)
        bm_merge(bm, lb)
        for f in list(bm.faces)[n0:]:
            for lp in f.loops:
                lp[data].uv = (float(s), 0.0)
    gate = new_obj("SM_HwGate", bm, (DOOR_OAK, IRON))
    gate.data.uv_layers.active_index = 0
    gate.data.uv_layers["UVMap"].active_render = True
    bb = _glow_bm()
    bx, by, bz = intro.BUTTON
    glow(kit.cyl(bb, (bx, by, bz - 0.04), (bx, by, bz + 0.03), 0.09, segs=12), "lantern", bb)
    log(f"gate: two crypt doors ({tris(gate)} tris), opening x +-{GATE_X} m to z {GATE_TOP}, open "
        f"{intro.DOOR_OPEN_DEG:.0f} deg outward; button at {intro.BUTTON}")
    return gate, new_obj("SM_HwButton", bb)


def gate_open_pose(gate):
    """A check-only copy of the doors at DoorOpen 1 (intro.door_xy, per leaf by its vertices' side of x = 0), never
    linked to the scene: the lasers are solved and verified against it too (open is the pose when no intro runs)."""
    me = gate.data.copy()
    for v in me.vertices:
        s = 1 if v.co.x > 0 else -1
        v.co.x, v.co.y = intro.door_xy(s, v.co.x, v.co.y, 1.0)
    return bpy.data.objects.new("HwGateOpenCheck", me)

def skull(bm, c, s=1.0, mat=0):
    c = Vector(c)
    setmat(kit.sphere(bm, c, 0.2 * s, segs=8, rings=6, scale=(1.0, 0.85, 1.1)), mat)
    setmat(kit.box(bm, c + Vector((0, -0.07 * s, -0.19 * s)), (0.2 * s, 0.14 * s, 0.1 * s)), mat)


COFFIN = ((-0.5, -0.30), (0.22, -0.5), (0.5, -0.36), (0.5, 0.36), (0.22, 0.5), (-0.5, 0.30))   # (along, across)


def coffin(bm, c, length, width, depth, along, across, mat):
    """A six-sided coffin prism centred on c: its outline (COFFIN x length, width) in the (along, across) plane, depth
    along their cross product. Returns the faces (material mat)."""
    along, across = Vector(along).normalized(), Vector(across).normalized()
    out = along.cross(across).normalized()
    ring = [c + along * (a * length) + across * (b * width) for a, b in COFFIN]
    f0 = [bm.verts.new(p - out * depth / 2) for p in ring]
    f1 = [bm.verts.new(p + out * depth / 2) for p in ring]
    faces = [bm.faces.new(f0[::-1]), bm.faces.new(f1)]
    for i in range(len(ring)):
        j = (i + 1) % len(ring)
        faces.append(bm.faces.new((f0[i], f0[j], f1[j], f1[i])))
    return setmat(solid(bm, faces), mat)


def speaker_face(bm, c, r, IR, key="eyes_dim"):
    """A speaker cone on a front face (facing -Y): a dark iron ring and dust cap, with a dim glowing status light."""
    setmat(kit.cyl(bm, c, c + Vector((0, -0.05, 0)), r, segs=12), IR)
    setmat(kit.cone(bm, c + Vector((0, -0.05, 0)), c + Vector((0, 0.02, 0)), r * 0.8, segs=12), IR)
    glow(kit.box(G, c + Vector((r * 0.9, -0.06, -r * 0.9)), (0.03, 0.01, 0.03)), key)


def deck_props(bm, SD, IR, ST, WX, BN, WD, BK, PK):
    """v7 (hw_deckprops.PROPS): coffin speaker stacks, coffin subs, tombstones, dead trees, candelabras and pumpkin
    piles on the deck wings; the stairs down to the crowd. Returns the pool lights [(name, pos, target, rgb, W, deg)]."""
    pools, prng = [], random.Random(77)
    z0 = DECK_Z
    for i, (kind, x, y, size, sx) in enumerate(dp.PROPS):
        c = Vector((x, y, z0))
        if kind in ("coffin_stack", "sub_stack"):
            w, d, h = size
            hl = 0.5 if kind == "coffin_stack" else h / 2
            for k in range(2):                                                # lying coffins: subs, cones forward
                cc = c + Vector((0, 0, hl * (k + 0.5)))
                coffin(bm, cc, w, d * 0.9, hl * 0.96, (sx, 0, 0), (0, 1, 0), WD)
                for ox in (-0.45, 0.45):
                    speaker_face(bm, cc + Vector((ox * w / 2, -d * 0.45 - 0.01, 0)), hl * 0.36, IR)
            if kind == "coffin_stack":                                        # upright coffins: the tops, 2 cones each
                top = z0 + 2 * hl
                ch = h - 2 * hl
                for ox in (-w / 4, w / 4):
                    cc = Vector((x + ox, y, top + ch / 2))
                    coffin(bm, cc, ch, w / 2 * 0.95, d * 0.6, (0, 0, 1), (1, 0, 0), WD)
                    for oz in (-0.28, 0.12):
                        speaker_face(bm, cc + Vector((0, -d * 0.3 - 0.01, oz * ch)), 0.2, IR)
                    glow(kit.box(G, cc + Vector((0, -d * 0.3 - 0.02, 0.36 * ch)), (0.05, 0.01, 0.2)), "orange")  # cross
                    glow(kit.box(G, cc + Vector((0, -d * 0.3 - 0.02, 0.4 * ch)), (0.14, 0.01, 0.05)), "orange")
                pools.append((f"PoolStack{i}", (x - sx * 1.5, y - 3.0, z0 + 5.0), (x, y - 0.4, z0 + 1.2), PURPLE, 2600, 32))
            else:
                pools.append((f"PoolSub{i}", (x, y - 2.0, z0 + 4.0), (x, y, z0), ORANGE, 900, 34))
        elif kind == "tomb":
            w, d, h, tilt = size
            tb = bmesh.new()
            body = h - w / 2
            setmat(kit.box(tb, (0, 0, body / 2), (w, d, body)), ST)
            setmat(kit.cyl(tb, (0, -d / 2, body), (0, d / 2, body), w / 2, segs=10), ST)
            setmat(kit.box(tb, (0, -d / 2 - 0.006, body * 0.62), (w * 0.5, 0.012, 0.05)), SD)   # an engraved line
            bmesh.ops.transform(tb, matrix=Matrix.Translation(c) @ Matrix.Rotation(math.radians(tilt), 4, "Y")
                                @ Matrix.Rotation(math.radians(prng.uniform(-8, 8)), 4, "Z"), verts=tb.verts[:])
            bm_merge(bm, tb)
        elif kind == "tree":
            tb, tips = bmesh.new(), []
            tree(tb, c, Vector((prng.uniform(-0.1, 0.1), 0.05, 1.0)).normalized(), size[0] * 0.36, 0.17, 3,
                 random.Random(500 + i), tips)
            setmat(tb.faces[:], BK)
            top = max(v.co.z for v in tb.verts)
            if top > z0 + size[0]:                                            # keep it under its height
                k = size[0] / (top - z0)
                bmesh.ops.scale(tb, vec=(k, k, k), space=Matrix.Translation(-c), verts=tb.verts[:])
            bm_merge(bm, tb)
            pools.append((f"PoolTree{i}", (x - sx * 2.0, y - 2.5, z0 + 0.3), (x, y, z0 + 2.4), GREENISH, 1400, 40))
        elif kind == "candelabra":
            h = size[0]
            setmat(kit.cone(bm, c, c + Vector((0, 0, 0.3)), 0.24, segs=8), IR)
            setmat(kit.cyl(bm, c, c + Vector((0, 0, h)), 0.04, segs=6), IR)
            setmat(kit.box(bm, c + Vector((0, 0, h - 0.25)), (0.9, 0.05, 0.05)), IR)
            for ax_, hz in ((-0.42, h - 0.25), (-0.2, h - 0.12), (0.0, h), (0.2, h - 0.12), (0.42, h - 0.25)):
                q = c + Vector((ax_, 0, hz))
                setmat(kit.cyl(bm, q, q + Vector((0, 0, 0.06)), 0.05, segs=6), IR)
                setmat(kit.cyl(bm, q + Vector((0, 0, 0.06)), q + Vector((0, 0, 0.26)), 0.026, segs=6), WX)
                glow(kit.box(G, q + Vector((0, 0, 0.30)), (0.026, 0.026, 0.075)), "candle")
            pools.append((f"PoolCandle{i}", (x, y, z0 + h + 2.6), (x, y, z0), (1.0, 0.55, 0.2), 700, 50))
        elif kind == "pumpkins":
            n, rad = size
            for k in range(n):
                a = k * 2.4 + prng.uniform(-0.3, 0.3)
                rr = 0.0 if k == 0 else rad * prng.uniform(0.55, 1.0)
                r = prng.uniform(0.2, 0.3) * (1.25 if k == 0 else 1.0)
                pc = c + Vector((rr * math.cos(a), rr * math.sin(a), r * 0.8))
                setmat(kit.sphere(bm, pc, r, segs=10, rings=6, scale=(1, 1, 0.8)), PK)
                setmat(kit.cyl(bm, pc + Vector((0, 0, r * 0.75)), pc + Vector((0, 0, r * 1.05)), 0.03, segs=5), BK)
                fy = pc + Vector((0, -r * 0.97, 0))                            # the face, toward the crowd
                for ex in (-0.33, 0.33):
                    glow(kit.box(G, fy + Vector((ex * r, -0.005, 0.18 * r)), (0.2 * r, 0.01, 0.16 * r)), "orange")
                glow(kit.box(G, fy + Vector((0, -0.005, -0.25 * r)), (0.6 * r, 0.01, 0.12 * r)), "orange")
            pools.append((f"PoolPumpkin{i}", (x, y - 1.5, z0 + 3.0), (x, y, z0), ORANGE, 500, 45))
    rise = (DECK_Z - FIELD_Z) / dp.STAIR_N                                # the stairs down to the crowd
    for ya, yb, top in dp.stair_steps():
        setmat(kit.box(bm, (0, (yb + dp.STAIR_Y0) / 2, (top + FIELD_Z) / 2),
                       (2 * dp.STAIR_HALF_W, dp.STAIR_Y0 - yb, top - FIELD_Z)), SD)
    yb = dp.STAIR_Y0 - dp.STAIR_N * dp.STAIR_D
    for sx in (-1, 1):                                                    # iron handrails with a candle at the foot
        xr = sx * (dp.STAIR_HALF_W + 0.05)
        setmat(kit.cyl(bm, (xr, dp.STAIR_Y0, DECK_Z + 0.9), (xr, yb, FIELD_Z + 0.9), 0.025, segs=5), IR)
        for yy, zz in ((dp.STAIR_Y0, DECK_Z), (yb, FIELD_Z)):
            setmat(kit.cyl(bm, (xr, yy, zz), (xr, yy, zz + 0.9), 0.03, segs=5), IR)
        pc = Vector((xr, yb - 0.1, FIELD_Z + 0.9))
        setmat(kit.cyl(bm, pc, pc + Vector((0, 0, 0.16)), 0.03, segs=6), WX)
        glow(kit.box(G, pc + Vector((0, 0, 0.2)), (0.03, 0.03, 0.07)), "candle")
    pools.append(("PoolStairs", (0, -5.8, DECK_Z + 4.0), (0, -5.8, FIELD_Z), (1.0, 0.55, 0.2), 700, 45))
    log(f"v7 deck props: {len(dp.PROPS)} ({', '.join(sorted({q[0] for q in dp.PROPS}))}); stairs {dp.STAIR_N} risers of "
        f"{rise:.3f} m; {len(pools)} pool lights")
    return pools


def build_deck(oak_tips):
    bm = bmesh.new()
    DK, SD, IR, ST, WX, BN, WD, RV = 0, 1, 2, 3, 4, 5, 6, 7
    setmat(kit.box(bm, (0, 4.75, (DECK_Z + FIELD_Z) / 2), (50, 18.5, DECK_Z - FIELD_Z)), DK)   # deck y -4.5..14
    for x in LIP_X:                                                   # v3: the deck-front laser units on posts
        c, f = lip_unit(x)
        setmat(kit.cyl(bm, (x, c.y, DECK_Z), (x, c.y, c.z - LIP_BOX[2] / 2), 0.05, segs=6), IR)
        setmat(kit.box(bm, c, (LIP_BOX[1], LIP_BOX[0], LIP_BOX[2]), yaw=math.atan2(f.y, f.x) - math.pi / 2), IR)
    setmat(kit.box(bm, (0, 0.25, DECK_Z / 2), (9.0, 5.5, -DECK_Z)), SD)                   # riser (Dino's): deck to z 0
    for s_ in (-1, 1):                                                                    # stairs at the back corners
        for k in range(4):
            t = (k + 1) * (-DECK_Z) / 5
            setmat(kit.box(bm, (s_ * (4.5 + 0.35 * k + 0.175), 2.0, (DECK_Z - t) / 2), (0.35, 1.8, -DECK_Z - t)), SD)
    for i in range(12):                                                                   # skull frieze, riser front
        x = -4.0 + 8.0 * i / 11
        sb = bmesh.new()
        skull(sb, (x, -2.56, -0.5), 1.0, BN)
        bm_merge(bm, sb)
        for ex in (-0.07, 0.07):
            glow(kit.box(GE, (x + ex, -2.735, -0.47), (0.06, 0.02, 0.05)), "eyes_dim", GE)
    T = TABLE
    w, d, top = T["x1"] - T["x0"], T["y1"] - T["y0"], T["top"]
    cx, cy = (T["x0"] + T["x1"]) / 2, (T["y0"] + T["y1"]) / 2
    setmat(kit.box(bm, (cx, cy, top / 2), (w, d, top)), SD)                               # booth table (stone)
    setmat(kit.box(bm, (cx, cy, top - 0.02), (w + 0.12, d + 0.12, 0.04)), IR)             # lid
    coffin = [(-0.9, 0.24), (-0.9, 0.52), (-0.5, 0.70), (0.8, 0.58), (0.8, 0.18), (-0.5, 0.06)]   # booth front panel
    yf = T["y0"] - 0.02
    vf = [bm.verts.new((x, yf, z)) for x, z in coffin]
    vb = [bm.verts.new((x, yf - 0.04, z)) for x, z in coffin]
    cf = [bm.faces.new(vf), bm.faces.new(list(reversed(vb)))]
    for i in range(len(coffin)):
        j = (i + 1) % len(coffin)
        cf.append(bm.faces.new((vf[i], vf[j], vb[j], vb[i])))
    setmat(solid(bm, cf), WD)
    glow(kit.box(G, (-0.12, yf - 0.05, 0.38), (0.06, 0.012, 0.42)), "orange")              # its glowing cross
    glow(kit.box(G, (-0.12, yf - 0.05, 0.47), (0.26, 0.012, 0.06)), "orange")
    for sx in (-1, 1):                                                                    # gargoyles on the riser
        gx = sx * 3.6
        setmat(kit.box(bm, (gx, 0.6, 0.25), (0.8, 0.8, 0.5)), SD)
        setmat(kit.box(bm, (gx, 0.6, 0.95), (0.6, 0.7, 0.9)), ST)
        setmat(kit.box(bm, (gx, 0.2, 1.35), (0.45, 0.5, 0.4)), ST)
        for hx in (-0.14, 0.14):
            setmat(kit.cone(bm, (gx + hx, 0.25, 1.52), (gx + hx * 1.6, 0.4, 1.85), 0.06, segs=5), ST)
        for wx in (-1, 1):
            setmat(kit.box(bm, (gx + wx * 0.45, 0.85, 1.3), (0.7, 0.08, 0.5), roll=wx * 0.6), ST)
        for ex in (-0.1, 0.1):
            glow(kit.box(GE, (gx + ex, -0.06, 1.4), (0.07, 0.02, 0.05)), "eyes", GE)
    rb = Vector((-3.6, 0.35, 1.63))                                                       # a raven on the left gargoyle
    setmat(kit.sphere(bm, rb, 0.12, segs=8, rings=5, scale=(0.8, 1.3, 0.9)), RV)
    setmat(kit.sphere(bm, rb + Vector((0, -0.15, 0.1)), 0.07, segs=8, rings=5), RV)
    setmat(kit.cone(bm, rb + Vector((0, -0.2, 0.1)), rb + Vector((0, -0.31, 0.08)), 0.025, segs=5), RV)
    setmat(kit.box(bm, rb + Vector((0, 0.18, -0.02)), (0.1, 0.18, 0.02), pitch=0.3), RV)
    glow(kit.box(GE, rb + Vector((0.035, -0.205, 0.12)), (0.012, 0.012, 0.012)), "eyes", GE)
    for ccx, ccy in ((-2.0, -2.1), (2.0, -2.1), (-2.6, 2.6), (2.6, 2.6)):                # candle clusters
        for j in range(5):
            a = j * 1.26
            px, py, h = ccx + 0.18 * math.cos(a), ccy + 0.18 * math.sin(a), 0.15 + 0.05 * j
            setmat(kit.cyl(bm, (px, py, 0), (px, py, h), 0.03, segs=6), WX)
            glow(kit.box(G, (px, py, h + 0.03), (0.025, 0.025, 0.06)), "candle")
    for sx in (-1, 1):                                                                    # candelabras, riser front
        c = Vector((sx * 4.0, -2.05, 0.0))
        setmat(kit.cone(bm, c, c + Vector((0, 0, 0.25)), 0.2, segs=8), IR)
        setmat(kit.cyl(bm, c, c + Vector((0, 0, 1.3)), 0.035, segs=6), IR)
        setmat(kit.box(bm, c + Vector((0, 0, 1.08)), (0.7, 0.04, 0.04)), IR)
        for ax_, hz in ((-0.33, 1.08), (0.0, 1.3), (0.33, 1.08)):
            p = c + Vector((ax_, 0, hz))
            setmat(kit.cyl(bm, p, p + Vector((0, 0, 0.06)), 0.05, segs=6), IR)
            setmat(kit.cyl(bm, p + Vector((0, 0, 0.06)), p + Vector((0, 0, 0.24)), 0.025, segs=6), WX)
            glow(kit.box(G, p + Vector((0, 0, 0.28)), (0.025, 0.025, 0.07)), "candle")
    cc = Vector((-3.6, 2.4, 0.0))                                                         # cauldron, back left
    for k in range(3):
        a = k * 2 * math.pi / 3
        setmat(kit.cyl(bm, cc + Vector((0.32 * math.cos(a), 0.32 * math.sin(a), 0)),
                       cc + Vector((0.22 * math.cos(a), 0.22 * math.sin(a), 0.3)), 0.04, segs=5), IR)
    setmat(kit.sphere(bm, cc + Vector((0, 0, 0.55)), 0.45, segs=12, rings=8, scale=(1, 1, 0.8)), IR)
    setmat(kit.cyl(bm, cc + Vector((0, 0, 0.8)), cc + Vector((0, 0, 0.86)), 0.4, segs=12), IR)
    glow(kit.cyl(G, cc + Vector((0, 0, 0.84)), cc + Vector((0, 0, 0.87)), 0.34, segs=12), "brew")
    halo(HALOS, cc + Vector((0, 0, 1.25)), 1.4, "green")
    for sx in (-1, 1):                                                                    # skull piles on the deck
        for k in range(9):
            p = Vector((sx * 6.0 + rng.uniform(-0.45, 0.45), -3.3 + rng.uniform(-0.4, 0.4),
                        DECK_Z + 0.18 + 0.28 * (k // 4)))
            sb = bmesh.new()
            skull(sb, p, rng.uniform(0.8, 1.1), BN)
            bm_merge(bm, sb)
    for x in FIRE_X:                                                                      # flame-jet bases, deck lip
        setmat(kit.box(bm, (x, -4.0, DECK_Z + 0.12), (0.5, 0.5, 0.25)), IR)
    by = dp.BARRIER_Y                                                                     # iron fence barrier
    for z in (FIELD_Z + 0.6, FIELD_Z + 1.2):                                              # v7: a gateway at |x| < 1.9
        for sx in (-1, 1):
            setmat(kit.box(bm, (sx * (31 + dp.BARRIER_GAP) / 2, by, z), (31 - dp.BARRIER_GAP, 0.08, 0.08)), IR)
    for sx in (-1, 1):                                                                    # the gateway's posts
        setmat(kit.cyl(bm, (sx * dp.BARRIER_GAP, by, FIELD_Z), (sx * dp.BARRIER_GAP, by, FIELD_Z + 1.9), 0.08, segs=6),
               IR)
        setmat(kit.cone(bm, (sx * dp.BARRIER_GAP, by, FIELD_Z + 1.9), (sx * dp.BARRIER_GAP, by, FIELD_Z + 2.25), 0.11,
                        segs=6), IR)
    for i in range(32):
        x = -31 + i * 2
        if abs(x) < dp.BARRIER_GAP + 0.1:
            continue
        setmat(kit.cyl(bm, (x, by, FIELD_Z), (x, by, FIELD_Z + 1.5), 0.05, segs=5), IR)
        setmat(kit.cone(bm, (x, by, FIELD_Z + 1.5), (x, by, FIELD_Z + 1.85), 0.08, segs=5), IR)
        if i % 3 == 1:                                                                    # lanterns on every 3rd post
            setmat(kit.box(bm, (x, by, FIELD_Z + 1.95), (0.3, 0.3, 0.05)), IR)
            glow(kit.box(G, (x, by, FIELD_Z + 2.15), (0.22, 0.22, 0.32)), "lantern")
    for i in range(7):                                                                    # lanterns under the truss,
        x = -12 + i * 4                                                                   # above the picture (12.67)
        setmat(kit.cyl(bm, (x, TRUSS_Y, 16.2), (x, TRUSS_Y, 13.8), 0.03, segs=4), IR)
        glow(kit.box(G, (x, TRUSS_Y, 13.5), (0.4, 0.4, 0.55)), "lantern")
    for t in oak_tips:                                                                    # lanterns in the oaks
        setmat(kit.cyl(bm, t, t - Vector((0, 0, 1.2)), 0.03, segs=4), IR)
        glow(kit.box(G, t - Vector((0, 0, 1.5)), (0.5, 0.5, 0.7)), "lantern")
    add_backstage(bm, ST, SD, IR, BN, WX)                                                 # v4: the crypt gate
    DECK_POOLS[:] = deck_props(bm, SD, IR, ST, WX, BN, WD, 8, 9)                          # v7: the deck dressing
    return new_obj("SM_HwDeck", bm, (DECKMAT, STONE_DARK, IRON, STONE, WAX, BONE, WOOD, RAVEN, BARK, PUMPKIN))


# ---------------------------------------------------------------- screen, ground, sky, moon, bats
def build_screen():
    """Tribe's back-wall UV layout (dino_stage.v7 visual_screen_uv, verified on the headset): U = 0.5 - x/w, Blender V =
    0.5 (z - bottom)/h; the FBX import flips V, Tribe's M_VideoBackdrop samples (1-U, 2V-1). MESH NAME: the mod finds
    our screen by the static mesh name SM_DinoVisualScreen (dumper.cpp em_register_backdrop), so it keeps that name in
    our own package (/Game/Mods/Halloween/Meshes). Registered on the headset 2026-10-08 (v0)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    y, cz, w, h = SCREEN["y"], SCREEN["cz"], SCREEN["w"], SCREEN["h"]
    f = bm.faces.new([bm.verts.new(c) for c in ((-w / 2, y, cz - h / 2), (w / 2, y, cz - h / 2),
                                                 (w / 2, y, cz + h / 2), (-w / 2, y, cz + h / 2))])
    f.normal_update()
    if f.normal.y > 0:                                                                    # face the crowd (-Y)
        f.normal_flip()
    for lp in f.loops:
        co = lp.vert.co
        lp[uv].uv = (0.5 - co.x / w, 0.5 * (co.z - (cz - h / 2)) / h)
    return new_obj("SM_DinoVisualScreen", bm)


def build_ground():
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap")
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=110.0, matrix=Matrix.Translation((0, -50, FIELD_Z)),
                          calc_uvs=True)
    near = new_obj("SM_HwGround", bm, (GRASS,))                                           # 220 x 220 m, baked
    bm2 = bmesh.new()
    bmesh.ops.create_grid(bm2, x_segments=1, y_segments=1, size=700.0, matrix=Matrix.Translation((0, 0, FIELD_Z - 0.1)))
    return near, new_obj("SM_HwFarGround", bm2)


def build_sky():
    """dino_stage.build_sky: a 480 m UV sphere with equirect UVs, faces turned inward."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=480.0)
    ob = new_obj("SM_HwSky", bm)
    me = ob.data
    me.uv_layers.new(name="UVMap")
    uvl = me.uv_layers[0].data
    for poly in me.polygons:
        lon_c = math.atan2(poly.center.y, poly.center.x)
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            lon = math.atan2(co.y, co.x) if math.hypot(co.x, co.y) > 1e-3 else lon_c
            if abs(lon - lon_c) > math.pi:
                lon += 2 * math.pi if lon < lon_c else -2 * math.pi
            lat = math.asin(max(-1.0, min(1.0, co.z / 480.0)))
            uvl[li].uv = ((lon + math.pi) / (2 * math.pi), 0.5 + lat / math.pi)
    for p in me.polygons:
        p.flip()
    return ob


def build_moon():
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    n = 48
    ring = [bm.verts.new(MOON + Vector((MOON_R * math.cos(2 * math.pi * i / n), 0, MOON_R * math.sin(2 * math.pi * i / n))))
            for i in range(n)]
    f = bm.faces.new(ring)
    f.normal_update()
    if f.normal.y > 0:
        f.normal_flip()
    for lp in f.loops:
        d = lp.vert.co - MOON
        lp[uv].uv = (0.5 + 0.5 * d.x / MOON_R, 0.5 + 0.5 * d.z / MOON_R)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    return new_obj("SM_HwMoon", bm)


# ---------------------------------------------------------------- procedural textures (linear RGB, top-down rows)
def value_noise(w, h, base, octaves, seed, wrap_x=True):
    """Fractal value noise in [0, 1], h x w, periodic in x (equirect longitude) when wrap_x."""
    rs = np.random.RandomState(seed)
    out, amp, tot = np.zeros((h, w)), 1.0, 0.0
    for o in range(octaves):
        gx = base * 2 ** o
        gy = max(2, gx // 2)
        g = rs.rand(gy + 1, gx + (0 if wrap_x else 1))
        xs = np.arange(w) * gx / w
        x0 = np.floor(xs).astype(int)
        fx = xs - x0
        x1 = (x0 + 1) % gx if wrap_x else x0 + 1
        ys = np.arange(h) * gy / h
        y0 = np.floor(ys).astype(int)
        fy = ys - y0
        y1 = y0 + 1
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        a = g[y0][:, x0] * (1 - fx) + g[y0][:, x1] * fx
        b = g[y1][:, x0] * (1 - fx) + g[y1][:, x1] * fx
        out += amp * (a * (1 - fy[:, None]) + b * fy[:, None])
        tot += amp
        amp *= 0.5
    return out / tot


def tex_sky(w=4096, h=2048):
    """Storm night: near-black zenith, a purple-grey cloud deck, a red-orange glow on the horizon behind the cathedral
    (distant fires, +Y). v1: stars everywhere above the haze, dimmed (not cut) under the clouds, so they no longer
    cluster in one gap. Linear values stay low: the sky is shown unlit as-is."""
    v = (np.arange(h)[::-1] + 0.5) / h                                 # top row = zenith
    lat = (v - 0.5) * np.pi
    lon = ((np.arange(w) + 0.5) / w) * 2 * np.pi - np.pi
    L, LON = np.meshgrid(lat, lon, indexing="ij")
    img = np.zeros((h, w, 3)) + np.array([0.0022, 0.0018, 0.0060]) * SKY_DIM
    cl = value_noise(w, h, 6, 7, 11)
    cl = np.clip((cl - 0.42) / 0.3, 0, 1) ** 1.3                      # cloud cover 0..1
    band = np.exp(-((L - 0.35) / 0.32) ** 2)                           # clouds sit low-to-mid sky
    stage = np.clip(np.cos(LON - np.pi / 2), 0, 1)                     # +Y: behind the cathedral
    cloud_col = np.array([0.020, 0.015, 0.034]) + stage[..., None] ** 2 * np.array([0.022, 0.006, 0.004])
    cover = cl * band
    img += cover[..., None] * cloud_col * SKY_DIM
    hor = np.exp(-np.maximum(L, 0) / 0.05) * (0.35 + 0.65 * stage ** 3)
    img += hor[..., None] * np.array([0.060, 0.016, 0.006]) * SKY_DIM
    rs = np.random.RandomState(7)
    n = 11000
    s_lon = rs.uniform(-np.pi, np.pi, n)
    s_lat = np.arcsin(rs.uniform(0.12, 1.0, n))
    px = ((s_lon + np.pi) / (2 * np.pi) * w).astype(int) % w
    py = ((0.5 - s_lat / np.pi) * h).astype(int).clip(0, h - 1)
    vis = np.clip(1.0 - 1.6 * cover[py, px], 0.08, 1.0)                # dimmed under cloud, never fully cut
    mag = (rs.exponential(0.09, n) + 0.015) * vis * STAR_DIM
    np.add.at(img, (py, px), mag[:, None] * np.array([0.85, 0.88, 1.0]))
    img[L < 0] = np.array([0.004, 0.004, 0.006]) * SKY_DIM
    return np.clip(img, 0, 1)


def tex_moon(s=1024):
    y, x = np.mgrid[0:s, 0:s]
    u, v = (x + 0.5) / s * 2 - 1, 1 - (y + 0.5) / s * 2
    r = np.sqrt(u * u + v * v)
    n1, n2 = value_noise(s, s, 4, 6, 3, wrap_x=False), value_noise(s, s, 16, 4, 5, wrap_x=False)
    maria = np.clip((n1 - 0.45) / 0.2, 0, 1)
    base = np.array([0.62, 0.15, 0.04])
    shade = (1 - 0.45 * maria) * (0.85 + 0.3 * n2) * (1 - 0.4 * np.clip(r, 0, 1) ** 4)
    img = base * shade[..., None]
    img[r > 1.0] = 0.0
    return np.clip(img, 0, 1)


# ---------------------------------------------------------------- bake lights (the show at a mid-drop, frozen)
def add_light(name, kind, pos, target, color, power, size=1.0, spot_deg=40):
    ld = bpy.data.lights.new(name, kind)
    ld.color = color
    ld.energy = power
    if kind == "SPOT":
        ld.spot_size = math.radians(spot_deg)
        ld.spot_blend = 0.6
        ld.shadow_soft_size = size
    elif kind == "POINT":
        ld.shadow_soft_size = size
    ob = bpy.data.objects.new(name, ld)
    ob.location = pos
    ob.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(ob)


DECK_POOLS = []                                # v7: pool lights for the deck dressing (deck_props)


def stage_lights():
    w = bpy.data.worlds.new("Night")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.012, 0.012, 0.026, 1)
    scene.world = w
    for sx in (-1, 1):
        add_light(f"UpNave{sx}", "SPOT", (sx * 9, 12.5, DECK_Z), (sx * 6, 14.5, 18), ORANGE, 16000, 0.6, 55)
        add_light(f"UpTower{sx}", "SPOT", (sx * 26, 11.5, DECK_Z), (sx * 24, 16, 26), PURPLE, 26000, 0.6, 40)
        add_light(f"UpPortal{sx}", "SPOT", (sx * 15, 9.0, DECK_Z), (sx * 13, 13.5, 14), ORANGE, 6000, 0.4, 40)
        add_light(f"UpOak{sx}", "SPOT", (sx * (OAK_X - 5), 0, FIELD_Z), (sx * OAK_X, 6, 12), (0.25, 0.9, 0.35), 9000,
                  0.6, 45)
        add_light(f"Wash{sx}", "SPOT", (sx * 24, 12.4, 26.5), (sx * 10, -28, FIELD_Z),
                  PURPLE if sx < 0 else GREENISH, 90000 if sx < 0 else 60000, 2.0, 70)
        # v7 (A: near-black deck, light in pools): v1-v6's DeckWash (2 x 9000 W orange over the whole deck) is gone;
        # the riser keeps two narrow pools on the decks and the dressing its own (DECK_POOLS)
        add_light(f"RiserPool{sx}", "SPOT", (sx * 1.2, -1.0, 5.5), (sx * 1.0, 0.6, 0.0), (1.0, 0.6, 0.3), 1300, 0.4, 30)
        add_light(f"Rose{sx}", "POINT", (sx * 24, 12.6, 30.6), (sx * 24, 0, 30.6), (1.0, 0.08, 0.1), 250, 1.5)
    add_light("WashC", "SPOT", (0, TRUSS_Y, 16), (0, -16, FIELD_Z), ORANGE, 40000, 1.0, 80)   # v6's (the crowd's light)
    for name, pos, tgt, rgb, power, deg in DECK_POOLS:
        add_light(name, "SPOT", pos, tgt, rgb, power, 0.4, deg)
    add_light("Follow", "SPOT", (0, -31, 3.5), (0, 0.9, 1.4), (1.0, 0.9, 0.8), 2500, 0.3, 6)
    add_light("Brew", "POINT", (-3.6, 2.4, 1.2), (-3.6, 2.4, 0), (0.25, 1.0, 0.35), 60, 0.3)
    add_light("Backstage", "POINT", (0.0, 9.6, BOX_TOP - 0.45), (0.0, 9.6, DECK_Z), (1.0, 0.22, 0.06), 160, 0.3)
    # the stream intro's arrival: cold moonlight on the back of the cathedral and the clearing where the rider comes
    # out of the trees (the camera holds there until showtime; unlit, it was black)
    for sx in (-1, 1):
        add_light(f"BackMoon{sx}", "SPOT", (sx * 22.0, 60.0, FIELD_Z + 1.0), (sx * 24.0, 22.0, 24.0), (0.45, 0.55, 1.0),
                  22000, 2.0, 45)
    add_light("BackMoonC", "SPOT", (0.0, 63.0, FIELD_Z + 2.5), (0.0, 45.0, 10.0), (0.5, 0.6, 1.0), 14000, 2.0, 55)
    for name, energy, col, rot in (("Moon", 0.25, (0.35, 0.65, 1.0), -MOON), ("MoonFill", 0.35, (0.45, 0.55, 0.9),
                                                                                 Vector((0, 120, -60)))):
        sun = bpy.data.lights.new(name, "SUN")
        sun.energy, sun.color, sun.angle = energy, col, math.radians(8)
        so = bpy.data.objects.new(name, sun)
        so.rotation_euler = rot.to_track_quat("-Z", "Y").to_euler()
        coll.objects.link(so)


# ---------------------------------------------------------------- unwrap + bake + export (copied from dino_stage.py)
def unwrap(ob, margin=0.003):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=margin, area_weight=0.0, correct_aspect=True)
    bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")
    uv = ob.data.uv_layers.active.data
    area = 0.0
    for p in ob.data.polygons:
        pts = [uv[li].uv for li in p.loop_indices]
        area += abs(sum(pts[i].x * pts[(i + 1) % len(pts)].y - pts[(i + 1) % len(pts)].x * pts[i].y
                        for i in range(len(pts)))) / 2
    log(f"unwrap {ob.name}: UV coverage {area * 100:.1f}%")


def blur(img, passes=3, r=3):
    for _ in range(passes):
        for ax in (0, 1):
            c = np.cumsum(np.pad(img, [(r + 1, r) if a == ax else (0, 0) for a in range(3)], mode="edge"), axis=ax)
            img = (np.take(c, range(2 * r + 1, c.shape[ax]), axis=ax)
                   - np.take(c, range(0, c.shape[ax] - 2 * r - 1), axis=ax)) / (2 * r + 1)
    return img


def bake(ob, name, size, exposure, samples=BAKE_SAMPLES, margin=8, smooth=0):
    exposure *= NIGHT
    if FAST:
        size, samples, margin, smooth = max(128, size // 8), 4, max(1, margin // 4), min(smooth, 1)
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=True)
    for m in ob.data.materials:
        nt = m.node_tree
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = img
        for n in nt.nodes:
            n.select = False
        tx.select = True
        nt.nodes.active = tx
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    scene.cycles.samples = samples
    t = time.time()
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT", "COLOR"}, margin=margin, use_clear=True)
    px = np.empty(size * size * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    lin = px.reshape(size, size, 4)[::-1, :, :3]
    if float(lin.max()) <= 0.0:                     # v7: v6 shipped a black ground and crowd (Cycles lost its tile
        raise RuntimeError(f"bake {name}: all black (a Cycles tile-file error?); not shipping it")   # files)
    if smooth:
        lin = blur(lin, r=smooth)
    path = os.path.join(OUT, name + ".png")
    out = tonemap(lin, exposure)
    write_png(path, out)
    log(f"baked {ob.name} -> {name}.png {size}px {samples} spp in {time.time() - t:.0f}s: mean linear {lin.mean():.4f}, "
        f"p99 {np.percentile(lin, 99):.3f}, output mean {out.mean():.3f}")
    return path


def export_fbx(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, ob.name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"}, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",
                             mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False)
    log(f"fbx {os.path.basename(path)}: {len(ob.data.polygons)} faces, {tris(ob)} tris")


def verify_lasers(obstacles):
    """An independent pass over the solved beams at other poses than the solver's (11 x 11): the surface each sweeps
    along those grid lines against the set, a BVH ray along its full length at each pose, the rules point by point
    every 0.2 m, and the closest pass to the DJ's head.
    ship_hw.sh stops unless this logs 0 problems."""
    ob = _bvh(obstacles)
    bvh = ob[0]
    probs, worst = [], (1e9, "")
    for b in LASER_BEAMS:
        pv, L = b["pivot"], b["length"]
        hit = _swept_crossing(ob, pv, b["d"], b["pan"], b["tilt"], L, LASER_VERIFY)
        if hit is not None:
            probs.append(f"{b['name']}: its sweep crosses the set {hit[0]:.1f} m out ({hit[1].x:.1f},{hit[1].y:.1f},"
                         f"{hit[1].z:.1f})")
        for P in LASER_VERIFY:
            for Q in LASER_VERIFY:
                v = _pose_dir(b["d"], P, Q, b["pan"], b["tilt"])
                loc, _, _, dist = bvh.ray_cast(pv + v * LASER_GAP, v, L - LASER_GAP)
                if loc is not None:
                    probs.append(f"{b['name']} pose ({P:+.1f},{Q:+.1f}) hits the set at {LASER_GAP + dist:.1f} m "
                                 f"({loc.x:.1f},{loc.y:.1f},{loc.z:.1f})")
                    continue
                t = LASER_GAP
                while t <= L:
                    why = _laser_problem(pv + v * t)
                    if why:
                        q = pv + v * t
                        probs.append(f"{b['name']} pose ({P:+.1f},{Q:+.1f}): {why} at {t:.1f} m ({q.x:.1f},{q.y:.1f},{q.z:.1f})")
                        break
                    t += 0.2
                tc = max(LASER_GAP, min(L, (DJ_HEAD - pv).dot(v)))
                gap = (pv + v * tc - DJ_HEAD).length
                if gap < worst[0]:
                    worst = (gap, f"{b['name']} pose ({P:+.1f},{Q:+.1f})")
    log(f"laser verification ({len(LASER_VERIFY)}x{len(LASER_VERIFY)} poses): {len(LASER_BEAMS)} beams, {len(probs)} "
        f"problems; closest to the DJ's head {worst[0]:.1f} m ({worst[1]}) {'OK' if worst[0] >= DJ_CLEAR else 'TOO CLOSE'}")
    for pr in probs[:20]:
        log("  laser PROBLEM " + pr)
    return probs, worst


# ---------------------------------------------------------------- v2: the animated show's geometry
BAT_UV = ("BatCenter", "BatCenterZPhase", "BatSpeed")       # UV1..UV3 for hw_materials.flock_orbit
GHOST_UV = ("GhostCenter", "GhostCenterZPhase", "GhostSpeed")   # UV1..UV3 for hw_materials.ghost_waver


def build_bats():
    """3 flocks of black bats circling the moon, the whole left spire and the back of the grounds (never low over the
    crowd). Per vertex: the flock centre, (centre z, phase), (turns per second, wing flag = side x span on the wing
    tips, 0 elsewhere: the material flaps the tips)."""
    bm = bmesh.new()
    uv0 = bm.loops.layers.uv.new("UVMap")
    lays = [bm.loops.layers.uv.new(n) for n in BAT_UV]
    black = pal_uv("black")
    flocks = (((MOON.x + 2, MOON.y - 8, MOON.z - 4), 13.0, 50, 0.045, 2.0),
              ((-24.0, 18.0, 53.0), 9.0, 40, -0.06, 1.2),
              ((4.0, -86.0, 26.0), 22.0, 50, 0.03, 1.2))
    n_bats = 0
    for (cx, cy, cz), r, n, spd, span in flocks:
        for _ in range(n):
            a = rng.uniform(0, 2 * math.pi)
            rr = r * rng.uniform(0.7, 1.3)
            c = Vector((cx + rr * math.cos(a), cy + rr * math.sin(a), cz + rng.uniform(-4, 4)))
            t = Vector((-math.sin(a), math.cos(a), 0)) * (1 if spd > 0 else -1)
            sd = t.cross(Vector((0, 0, 1))).normalized()
            ph, sp, body = rng.random(), spd * rng.uniform(0.85, 1.15), span * 0.35
            parts = [(bm.faces.new([bm.verts.new(q) for q in (c + t * body * 0.5, c + sd * body * 0.12,
                                                              c - t * body * 0.5, c - sd * body * 0.12)]), 0.0)]
            for side in (-1, 1):
                q = [c + t * body * 0.25 + sd * side * body * 0.1, c + sd * side * span * 0.5 + t * body * 0.1,
                     c + sd * side * span * 0.42 - t * body * 0.3, c - t * body * 0.2 + sd * side * body * 0.1]
                parts.append((bm.faces.new([bm.verts.new(v) for v in (q if side > 0 else list(reversed(q)))]),
                              float(side)))
            for f, side in parts:
                for lp in f.loops:
                    tip = (lp.vert.co - c).length > span * 0.3
                    lp[uv0].uv = black
                    lp[lays[0]].uv = (cx, cy)
                    lp[lays[1]].uv = (cz, ph)
                    lp[lays[2]].uv = (sp, side * span if tip else 0.0)
            n_bats += 1
    log(f"bats: {n_bats} in {len(flocks)} flocks")
    return new_obj("SM_HwBats", bm)


def build_ghosts():
    """8 faint ghosts drifting round the graveyard strips, between the towers and over the back: vertical sheets
    narrowing to a head (UV0 = across, up), each orbiting its spot (>= 15 m from the DJ)."""
    bm = bmesh.new()
    uv0 = bm.loops.layers.uv.new("UVMap")
    lays = [bm.loops.layers.uv.new(n) for n in GHOST_UV]
    spots = ((-50, -28, FIELD_Z + 4.0, 5.0, 0.012), (-62, -52, FIELD_Z + 5.0, 6.0, -0.010),
             (52, -30, FIELD_Z + 4.5, 5.5, -0.011), (64, -55, FIELD_Z + 5.5, 6.5, 0.009), (0, 21, 31.0, 3.5, 0.015),
             (-22, -80, FIELD_Z + 6.0, 7.0, 0.008), (26, -84, FIELD_Z + 5.0, 6.0, -0.009), (-36, 4, 22.0, 4.0, -0.012))
    W, H, cols, rows = 1.6, 2.6, 3, 6
    for cx, cy, cz, r, spd in spots:
        a = rng.uniform(0, 2 * math.pi)
        c = Vector((cx + r * math.cos(a), cy + r * math.sin(a), cz))
        right = Vector((math.cos(a), math.sin(a), 0))
        ph = rng.random()
        grid = [[None] * (cols + 1) for _ in range(rows + 1)]
        for j in range(rows + 1):
            taper = 1.0 - 0.45 * (j / rows) ** 2
            for i in range(cols + 1):
                grid[j][i] = bm.verts.new(c + right * (W * (i / cols - 0.5) * taper) + Vector((0, 0, H * j / rows - H * 0.4)))
        for j in range(rows):
            for i in range(cols):
                f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
                for lp, (ii, jj) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                    lp[uv0].uv = (ii / cols, jj / rows)
                    lp[lays[0]].uv = (cx, cy)
                    lp[lays[1]].uv = (cz, ph)
                    lp[lays[2]].uv = (spd, 0.0)
    return new_obj("SM_HwGhosts", bm)


def build_fog():
    """Ground fog: 2 sheets over the crowd field (shin and knee height) and 1 over the deck round the riser (the DJ
    stands a metre above it). UV0 0..1 per sheet (soft edges); the material drifts noise in world XY."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    for x0, x1, y0, y1, z in ((-56, 56, -74, -8, FIELD_Z + 0.25), (-50, 50, -70, -9, FIELD_Z + 0.6),
                              (-24, 24, -4.4, 7.0, DECK_Z + 0.2)):
        f = bm.faces.new([bm.verts.new(q) for q in ((x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z))])
        for lp, c in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            lp[uv].uv = c
    return new_obj("SM_HwFog", bm)


def build_fire():
    """Flame jets at the stage lip: two crossed 1.3 x 2.8 m cards per jet (UV0: across, up), >= 6 m from the DJ."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    for x in FIRE_X:
        base = Vector((x, -4.0, DECK_Z + 0.25))
        for ang in (0.0, math.pi / 2):
            d = Vector((math.cos(ang), math.sin(ang), 0)) * 0.65
            up = Vector((0, 0, 2.8))
            f = bm.faces.new([bm.verts.new(q) for q in (base - d, base + d, base + d + up, base - d + up)])
            for lp, c in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
                lp[uv].uv = c
    return new_obj("SM_HwFire", bm)


def build_bolts():
    """3 jagged lightning bolts with branches, far behind the cathedral (on T_HwBeam's moon column); the animated build
    shows them only during a strike."""
    for x, y in ((-62, 105), (35, 140), (74, 112)):
        q = Vector((x, y, 135.0))
        pts = [q]
        for _ in range(10):
            q = q + Vector((rng.uniform(-5, 5), rng.uniform(-3, 3), -11.0))
            pts.append(q)
        segs = list(zip(pts[:-1], pts[1:]))
        for b in (3, 6):
            q = pts[b]
            for _ in range(4):
                q2 = q + Vector((rng.uniform(-7, 7), rng.uniform(-3, 3), -8.0))
                segs.append((q, q2))
                q = q2
        for a, b in segs:
            beam(BOLTS, a, b - a, (b - a).length, 1.0, 0.9, "moon", core=0.6)


def hand(bm, side):
    """A giant skeletal hand reaching up, palm toward the crowd (-Y), built at the origin (wrist ~5.6 m up, ~10 m in
    all before scaling). side: +1 thumb toward +X."""
    s = side

    def bone(a, c, r):
        kit.cyl(bm, a, c, r, segs=8)
        kit.sphere(bm, a, r * 1.35, segs=8, rings=5)
        kit.sphere(bm, c, r * 1.3, segs=8, rings=5)
    for dx in (-0.45, 0.45):                                                  # radius + ulna
        bone(Vector((dx, 0, -1.0)), Vector((dx * 0.8, -0.2, 5.0)), 0.32)
    wrist = Vector((0, -0.3, 5.6))
    for _ in range(6):                                                        # carpals
        kit.sphere(bm, wrist + Vector((rng.uniform(-0.6, 0.6), rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.3))), 0.3,
                   segs=8, rings=5)
    for fx, ml in ((-0.9, 1.8), (-0.3, 2.1), (0.3, 2.0), (0.85, 1.7)):        # 4 fingers: metacarpal + 3 phalanges
        k0 = wrist + Vector((fx * s, -0.1, 0.4))
        k1 = k0 + Vector((fx * 0.25 * s, -0.25, ml))
        bone(k0, k1, 0.2)
        d, q, L = (k1 - k0).normalized(), k1, 1.3
        for j in range(3):
            d = (Matrix.Rotation(math.radians(-24), 3, "X") @ d).normalized()  # curl toward the crowd
            q2 = q + d * L
            bone(q, q2, 0.16 - 0.02 * j)
            q, L = q2, L * 0.75
    d, q, L = Vector((1.0 * s, -0.4, 0.8)).normalized(), wrist + Vector((1.0 * s, -0.2, 0.2)), 1.4   # thumb
    for j in range(3):
        q2 = q + d * L
        bone(q, q2, 0.2 - 0.03 * j)
        q, L = q2, L * 0.75
        d = (Matrix.Rotation(math.radians(-20 * s), 3, "Z") @ (Matrix.Rotation(math.radians(-15), 3, "X") @ d)).normalized()


def build_hands():
    """The two giant skeletal hands flanking the portal (x +-22, y 4), scaled to ~12.5 m above the deck. In the animated
    build they rise with the hands row (hw_materials.rigid_rise) and sink 13 m under the deck between drops."""
    bm = bmesh.new()
    for sx in (-1, 1):
        hb = bmesh.new()
        hand(hb, -sx)                                                         # thumbs toward the stage centre
        hb.transform(Matrix.Translation((sx * 22.0, 4.0, DECK_Z)) @ Matrix.Scale(1.25, 4))
        bm_merge(bm, hb)
    return new_obj("SM_HwHands", bm, (BONE,))


def value_noise2(s, base, octaves, seed):
    """Fractal value noise in [0, 1], s x s, tileable in both axes."""
    rs = np.random.RandomState(seed)
    out, amp, tot = np.zeros((s, s)), 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o
        g = rs.rand(n, n)
        c = np.arange(s) * n / s
        c0 = np.floor(c).astype(int)
        f = c - c0
        c1 = (c0 + 1) % n
        f = f * f * (3 - 2 * f)
        a = g[c0][:, c0] * (1 - f) + g[c0][:, c1] * f
        b = g[c1][:, c0] * (1 - f) + g[c1][:, c1] * f
        out += amp * (a * (1 - f[:, None]) + b * f[:, None])
        tot += amp
        amp *= 0.5
    return out / tot


def tex_fog_noise(s=512):
    n = np.clip((value_noise2(s, 4, 6, 21) - 0.3) / 0.45, 0, 1)
    return np.repeat(n[..., None], 3, axis=2)


def tex_fire(w=128, h=256):
    """RGBA flame tongue (top row = the tip): alpha wide and solid at the base, narrowing up; colour white-yellow at the
    base to orange to deep red at the tip."""
    y, x = np.mgrid[0:h, 0:w]
    u, v = (x + 0.5) / w, 1.0 - (y + 0.5) / h
    hw = 0.45 * (1 - v) ** 0.8 + 0.02
    a = np.clip(1 - np.abs(u - 0.5) / hw, 0, 1) ** 1.5 * np.clip((1 - v) * 1.3, 0, 1) * np.clip(v * 12, 0, 1) * 0.9
    c0, c1, c2 = np.array([1.0, 0.85, 0.45]), np.array([1.0, 0.45, 0.05]), np.array([0.7, 0.08, 0.02])
    t1 = np.clip(v / 0.4, 0, 1)[..., None]
    t2 = np.clip((v - 0.4) / 0.6, 0, 1)[..., None]
    rgb = np.where(v[..., None] < 0.4, c0 * (1 - t1) + c1 * t1, c1 * (1 - t2) + c2 * t2)
    return np.concatenate([rgb, a[..., None]], axis=2)


# ---------------------------------------------------------------- v2: grounds modules (modules/CONTRACT.md)
def bm_merge_uv(dst, src):
    """Append src into dst keeping the UVMap layer (palette / beam / halo UVs)."""
    su = src.loops.layers.uv.get("UVMap")
    du = dst.loops.layers.uv.get("UVMap") or dst.loops.layers.uv.new("UVMap")
    src.verts.index_update()
    vmap = [dst.verts.new(v.co) for v in src.verts]
    for f in src.faces:
        try:
            nf = dst.faces.new([vmap[v.index] for v in f.verts])
        except ValueError:
            continue
        if su is not None:
            for nl, ol in zip(nf.loops, f.loops):
                nl[du].uv = ol[su].uv
    src.free()


HINGE_UV = ("UVMap", "HingePivot", "HingePivotZDelay", "HingeAxis", "HingeAxisZAngle")   # UV0..UV4 (hinge_swing)


def add_hinged(dst, src, mat_index, pivot, axis, open_turns, delay):
    """Append one hinged part (closed pose, final frame) to dst with its hinge on every loop: UV1 = hinge point (x, y),
    UV2 = (z, delay), UV3 = axis (x, y), UV4 = (axis z, opening in turns; + = right-hand turn about the axis). UVMap
    is left for the bake's unwrap. Returns the faces added."""
    lay = [dst.loops.layers.uv[n] for n in HINGE_UV]
    src.verts.index_update()
    vmap = [dst.verts.new(v.co) for v in src.verts]
    n = 0
    for f in src.faces:
        try:
            nf = dst.faces.new([vmap[v.index] for v in f.verts])
        except ValueError:
            continue
        nf.material_index = mat_index
        for lp in nf.loops:
            lp[lay[1]].uv = (pivot.x, pivot.y)
            lp[lay[2]].uv = (pivot.z, delay)
            lp[lay[3]].uv = (axis.x, axis.y)
            lp[lay[4]].uv = (axis.z, open_turns)
        n += 1
    src.free()
    return n


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = ob.data.name = name
    return ob


_LIT_MATS = {}


def lit_material(key):
    if key not in _LIT_MATS:
        rgb, rough = kit.LIT[key]
        _LIT_MATS[key] = mat_lit("G_" + key, rgb, rough=rough, noise=0.15, noise_scale=0.6)
    return _LIT_MATS[key]


def load_modules():
    """Build each module in HW_MODULES that exists (seed 1234, as hw_preview.py): {name: (module, result)}. A module
    that fails to build is skipped LOUDLY (the bake goes on; the log says which)."""
    out = {}
    for name in HW_MODULES:
        if not os.path.exists(os.path.join(HERE, "modules", name + ".py")):
            log(f"module {name}: not there yet, skipped")
            continue
        try:
            mod = importlib.import_module(name)
            res = mod.build(random.Random(1234))
        except Exception as e:  # noqa: BLE001
            log(f"module {name}: BUILD FAILED, skipped: {e!r}")
            continue
        out[name] = (mod, res)
        log(f"module {name}: lit {sum(kit.tris(b) for b, _ in res.get('lit', []))} tris, glow "
            f"{sum(kit.tris(b) for b in res.get('glow', []))}, beams {sum(len(b.faces) for b in res.get('beams', []))} "
            f"quads, halos {sum(len(b.faces) for b in res.get('halos', []))}, lights {len(res.get('lights', []))}, "
            f"exclude {len(res.get('exclude', []))}, people {len(res.get('people', []))}")
    return out


def mat_crowd():
    """dino_stage.mat_crowd: per-part colours from the "Col" attribute, darkened (night clothes)."""
    m = bpy.data.materials.new("Crowd")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "Col"
    dim = nt.nodes.new("ShaderNodeMixRGB")
    dim.blend_type = "MULTIPLY"
    dim.inputs["Fac"].default_value = 1.0
    dim.inputs["Color2"].default_value = (0.5, 0.5, 0.5, 1)
    nt.links.new(vc.outputs["Color"], dim.inputs["Color1"])
    nt.links.new(dim.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.8
    return m


def mat_emit_col(name, strength=1.0, layer="Col"):
    m = bpy.data.materials.new(name)
    nt, out = _nodes(m)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = layer
    nt.links.new(at.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def mat_fade(name, rgb, alpha=None, image=None, gain=0.45):
    """Preview of a translucent effect: rgb emission over the background by alpha (or by image R x gain: the fog)."""
    m = bpy.data.materials.new(name)
    nt, out = _nodes(m)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*rgb, 1)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    if image is not None:
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = image
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1 / 32.0, 1 / 32.0, 1.0)
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], tx.inputs["Vector"])
        ml = nt.nodes.new("ShaderNodeMath")
        ml.operation = "MULTIPLY"
        ml.inputs[1].default_value = gain
        nt.links.new(tx.outputs["Color"], ml.inputs[0])
        nt.links.new(ml.outputs[0], mix.inputs["Fac"])
    else:
        mix.inputs["Fac"].default_value = alpha
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    m.surface_render_method = "BLENDED"
    m.use_backface_culling = False
    return m


def build_the_crowd(excl, extra):
    """The costumed crowd (crowd/hw_crowd.py), else the Dino crowd v3 as a fallback; both build in the kit's frame and
    write T_HwCrowdVAT.exr/.json into OUT. Returns (crowd, phones, module)."""
    if os.path.exists(os.path.join(HERE, "crowd", "hw_crowd.py")):
        sys.path.insert(0, os.path.join(HERE, "crowd"))
        cm = importlib.import_module("hw_crowd")
    else:
        sys.path.insert(0, os.path.join(HERE, "..", "crowd2"))
        cm = importlib.import_module("crowd3")
        log("crowd: hw_crowd.py not there yet -> the Dino crowd v3 (fallback)")
    kw = {}
    sig = inspect.signature(cm.build_crowd2).parameters
    if "out_dir" in sig:
        kw["out_dir"] = OUT
    if "vat_name" in sig:
        kw["vat_name"] = "T_HwCrowdVAT"
    crowd, phones, _ = cm.build_crowd2(random.Random(11), exclude=excl, extra=extra, **kw)
    last = getattr(cm, "_LAST", {})
    if "people" in last:                                                  # v7: free roam (intro/hw_collide.py `person`)
        with open(os.path.join(OUT, "walk_people.json"), "w") as f:
            json.dump([[round(p["x"], 3), round(p["y"], 3), round(p.get("z", 0.0) - STAGE_DROP, 3)]
                       for p in last["people"]], f)
        log(f"walk_people.json: {len(last['people'])} dancers for the walking map")
    drop = Matrix.Translation((0, 0, -STAGE_DROP))
    pose = getattr(cm, "_POSE", None)                                     # crowd3 keys its pose data by object name
    for ob, nm in ((crowd, "SM_HwCrowd"), (phones, "SM_HwPhones")):
        ob.data.transform(drop)
        old = ob.name
        ob.name = ob.data.name = nm
        if pose is not None and old in pose and old != ob.name:
            pose[ob.name] = pose.pop(old)
    if not os.path.exists(os.path.join(OUT, "T_HwCrowdVAT.exr")):
        raise RuntimeError("the crowd wrote no T_HwCrowdVAT.exr into " + OUT)
    log(f"crowd ({cm.__name__}): {len(crowd.data.polygons)} faces, {tris(crowd)} tris; glow {tris(phones)} tris")
    return crowd, phones, cm


# ---------------------------------------------------------------- main
facade, detail, oak_tips = build_facade()
clockhands = build_clock()
rig, portal_apex = build_rig()
deck = build_deck(oak_tips)
hands = build_hands()
gate, button = build_gate()
screen = build_screen()
ground, far = build_ground()
sky = build_sky()
moon = build_moon()
bats = build_bats()
ghosts = build_ghosts()
fog = build_fog() if FOG_ON else None
fire = build_fire()
build_bolts()
glowob = new_obj("SM_HwGlow", G)
windows = new_obj("SM_HwWindows", GW)
eyes = new_obj("SM_HwEyes", GE)
lenses = new_obj("SM_HwLenses", GL)
clockface = new_obj("SM_HwClockFace", CF)
G = GW = GE = GL = CF = None
beams_ob = new_obj("SM_HwBeams", BEAMS)
halos_ob = new_obj("SM_HwHalos", HALOS)
search_ob = new_obj("SM_HwSearch", SEARCH)
bolts_ob = new_obj("SM_HwBolts", BOLTS)

# the grounds modules (kit frame -> lowered by the stage drop)
modules = load_modules()
mdrop = Matrix.Translation((0, 0, -STAGE_DROP))
excl = [r for _, res in modules.values() for r in res.get("exclude", [])]
extra = [q for _, res in modules.values() for q in res.get("people", [])]
with open(os.path.join(OUT, "walk_field.json"), "w") as _wf:              # v7: free roam (intro/hw_collide.py)
    json.dump({"exclude": [list(map(float, r)) for r in excl], "field_z": FIELD_Z, "barrier_y": dp.BARRIER_Y,
               "y_back": -66.0, "half": [20.0, 0.55]}, _wf)                   # hw_crowd: Y_BACK, crowd_half_v2
grounds_lit, gtrans, module_lights, groups = [], [], [], {}
gglow_bm = _glow_bm()
own_glow_bms = {}                                                         # modules with OWN_GLOW: tag -> glow bmesh
hinged_bm = bmesh.new()
for _n in HINGE_UV:
    hinged_bm.loops.layers.uv.new(_n)
hinged_keys, hinged_n = [], 0
for mname, (mod, res) in modules.items():
    tag = str(getattr(mod, "NAME", mname.replace("hw_", ""))).capitalize()
    parts = []
    for k, (gbm, key) in enumerate(res.get("lit", [])):
        gbm.transform(mdrop)
        parts.append(new_obj(f"G_{mname}_{k}", gbm, (lit_material(key),)))
    if parts:
        grounds_lit.append((join(parts, "SM_HwGrounds" + tag), int(getattr(mod, "BAKE_SIZE", 2048))))
    for k, entry in enumerate(res.get("hinged", [])):                     # CONTRACT.md: hinged parts (optional)
        try:
            gbm, key, pivot, axis, open_deg = entry[:5]
            delay = float(entry[5]) if len(entry) > 5 else 0.0
            if key not in kit.LIT:
                raise ValueError(f"unknown kit.LIT key {key!r}")
            if not (-180.0 <= float(open_deg) <= 180.0 and 0.0 <= delay <= 0.9 and Vector(axis).length > 1e-6):
                raise ValueError(f"open_deg {open_deg}, delay {delay}, axis {tuple(axis)}")
        except Exception as e:  # noqa: BLE001
            log(f"module {mname}: hinged entry {k} REJECTED ({e}); skipped")
            continue
        gbm.transform(mdrop)
        if key not in hinged_keys:
            hinged_keys.append(key)
        add_hinged(hinged_bm, gbm, hinged_keys.index(key), Vector(pivot) + Vector((0.0, 0.0, -STAGE_DROP)),
                   Vector(axis).normalized(), float(open_deg) / 360.0, delay)
        hinged_n += 1
    for gbm in res.get("glow", []):
        gbm.transform(mdrop)
        if getattr(mod, "OWN_GLOW", False):
            if tag not in own_glow_bms:
                own_glow_bms[tag] = _glow_bm()
            bm_merge_uv(own_glow_bms[tag], gbm)
        else:
            bm_merge_uv(gglow_bm, gbm)
    row = CUE_ROWS[MODULE_ROWS.get(mname, "always")]
    for kind, prefix in (("beams", "SM_HwGBeams"), ("halos", "SM_HwGHalos")):
        if res.get(kind):
            mb = bmesh.new()
            mb.loops.layers.uv.new("UVMap")
            for gbm in res[kind]:
                gbm.transform(mdrop)
                bm_merge_uv(mb, gbm)
            if not len(mb.faces):                                            # nothing to ship (empty FBX = failed import)
                log(f"module {mname}: {kind} list has no faces, nothing exported")
                mb.free()
                continue
            ob = new_obj(prefix + tag, mb)
            gtrans.append(ob)
            groups[ob.name] = row
    module_lights += res.get("lights", [])
gglow = new_obj("SM_HwGroundsGlow", gglow_bm) if len(gglow_bm.faces) else None
own_glows = [new_obj("SM_HwGroundsGlow" + t, b) for t, b in own_glow_bms.items() if len(b.faces)]
hinged = None
if len(hinged_bm.faces):                                                  # baked closed with the grounds
    hinged = new_obj("SM_HwHinged", hinged_bm, [lit_material(k) for k in hinged_keys])
    hinged.data.uv_layers.active_index = 0                                # the unwrap and the bake use UVMap
    grounds_lit.append((hinged, 1024))
    log(f"hinged parts: {hinged_n} ({len(hinged.data.polygons)} faces, {tris(hinged)} tris), materials {hinged_keys}")
else:
    hinged_bm.free()
gate_open = gate_open_pose(gate)                                          # v5: the doors open (the default)
LASER_OBSTACLES = ([facade, detail, deck, rig, hands, gate, gate_open, glowob, windows, eyes]
                   + [o for o, _ in grounds_lit])
build_lasers(portal_apex, LASER_OBSTACLES)                                # v3: solved against the set and the grounds
lasers_ob = new_obj("SM_HwLasers", LASERS)
crowd = phones = crowd_mod = None
if CROWD_ON:
    crowd, phones, crowd_mod = build_the_crowd(excl, extra)

TRANS = [beams_ob, halos_ob, lasers_ob, search_ob, bolts_ob, ghosts, fire] + ([fog] if fog else []) + gtrans
GLOWS = [glowob, windows, eyes, lenses, clockface, clockhands, button]
SOLID = ([facade, detail, deck, rig, hands, gate] + GLOWS + [screen, ground, far, sky, moon, bats]
         + ([gglow] if gglow else []) + own_glows + [o for o, _ in grounds_lit] + ([crowd, phones] if crowd else []))
for ob in SOLID + TRANS:
    log(f"{ob.name}: {len(ob.data.polygons)} faces, {tris(ob)} tris")
log(f"total {sum(tris(o) for o in SOLID + TRANS)} tris in {len(SOLID + TRANS)} meshes")
verify_lasers(LASER_OBSTACLES)
_gate_open_me = gate_open.data                                           # the check copy is never baked or exported
bpy.data.objects.remove(gate_open)
bpy.data.meshes.remove(_gate_open_me)

write_png(os.path.join(OUT, "T_HwGlowPal.png"), tex_palette())
write_png(os.path.join(OUT, "T_HwSky.png"), tex_sky(*((512, 256) if FAST else (4096, 2048))))
write_png(os.path.join(OUT, "T_HwMoon.png"), tex_moon(256 if FAST else 1024))
write_png(os.path.join(OUT, "T_HwFogNoise.png"), tex_fog_noise(128 if FAST else 512))
kit.write_png(os.path.join(OUT, "T_HwBeam.png"), tex_beam())
kit.write_png(os.path.join(OUT, "T_HwHalo.png"), tex_halo())
kit.write_png(os.path.join(OUT, "T_HwFire.png"), tex_fire())
write_png_linear(os.path.join(OUT, "T_HwCues.png"), tex_cues())
dino_show.write_png_linear(os.path.join(OUT, "T_HwLaserProg.png"), dino_show.tex_laser_prog())   # the Dino's laser
dino_show.write_png_linear(os.path.join(OUT, "T_HwLaserLib.png"), dino_show.tex_laser_lib())     # program, library
dino_show.write_png_linear(os.path.join(OUT, "T_HwLaserCues.png"), dino_show.tex_cues())         # and group levels
if modules:
    kit.write_png(os.path.join(OUT, "T_HwGroundsPal.png"), kit.tex_palette())
    kit.write_png(os.path.join(OUT, "T_HwGroundsBeam.png"), kit.tex_beam())
    kit.write_png(os.path.join(OUT, "T_HwGroundsHalo.png"), kit.tex_halo())
log("textures written (palette, sky, moon, fog noise, beam, halo, fire, cues, laser program/library/cues" + (", grounds" if modules else "") + ")")

# bake setup: the emitters light the set; translucent and moving parts stay out of the bakes
glow_img = load_png(os.path.join(OUT, "T_HwGlowPal.png"))
for ob in GLOWS + [bats]:
    assign(ob, mat_emit("E" + ob.name, image=glow_img, strength=5.0))
if gglow:
    assign(gglow, mat_emit("EGroundsGlow", image=load_png(os.path.join(OUT, "T_HwGroundsPal.png")), strength=5.0))
for og in own_glows:
    assign(og, mat_emit("E" + og.name, image=load_png(os.path.join(OUT, "T_HwGroundsPal.png")), strength=5.0))
assign(screen, mat_emit("ScreenEmit", (0.35, 0.12, 0.30), 1.0))
assign(sky, mat_emit("SkyEmit", image=load_png(os.path.join(OUT, "T_HwSky.png")), strength=1.0))
assign(moon, mat_emit("MoonEmit", image=load_png(os.path.join(OUT, "T_HwMoon.png")), strength=1.0))
assign(far, mat_emit("FarFlat", FAR_RGB, 1.0))
if crowd:
    assign(crowd, mat_crowd())
    assign(phones, mat_emit_col("PhoneEmit", 4.0))
for ob in TRANS + [bats]:
    ob.hide_render = True
stage_lights()
mlights = []
for spec in module_lights:                                                 # the modules' lights bake onto everything
    lo = kit.add_light(spec, coll)
    lo.location.z -= STAGE_DROP
    mlights.append(lo)
log(f"bake lights: {len([o for o in coll.objects if o.type == 'LIGHT'])} ({len(module_lights)} from the modules)")

for ob in (facade, detail, deck, rig, hands, gate):
    unwrap(ob, 0.002 if ob in (facade, detail) else 0.003)
for gob, _ in grounds_lit:
    unwrap(gob, 0.002)


def only_hands_when(target):
    """The hands are down under the deck most of the time: they cast nothing in the other bakes."""
    hands.hide_render = target is not hands


# exposures (x NIGHT): the set as v1 (calibrated against Dino v7.1); the grounds at Dino's 1.8 (CONTRACT.md); the crowd
# at Dino's 0.55 (the user: "WAY darker")
only_hands_when(facade)
bake_facade = bake(facade, "T_HwFacade", 4096, exposure=7.0 * SET_DIM)
bake_detail = bake(detail, "T_HwFacadeDetail", 2048, exposure=7.0 * SET_DIM, samples=96)
bake_deck = bake(deck, "T_HwDeck", 4096, exposure=6.0 * SET_DIM, samples=96)   # v7: 2048 -> 4096 (the dressing)
bake_rig = bake(rig, "T_HwRig", 1024, exposure=6.0 * SET_DIM, samples=96)
only_hands_when(hands)
bake_hands = bake(hands, "T_HwHands", 1024, exposure=7.0 * SET_DIM, samples=96)
only_hands_when(ground)
bake_gate = bake(gate, "T_HwGate", 1024, exposure=6.0 * SET_DIM, samples=96)
bake_grounds = [(gob, bake(gob, "T" + gob.name[2:], gsize, exposure=GROUNDS_EXPOSURE, samples=64))
                for gob, gsize in grounds_lit]
# The modules tuned their light pools in hw_preview.py, whose ground takes their light as a 0.035 diffuse at exposure 1;
# this bake reads GRASS 0.03 at 6.0 x NIGHT, which made the pools ~2.6x brighter than previewed (hw-grounds-b,
# 2026-10-08). Their lights bake onto the ground at the previewed level x the v3 darkening (GROUND_EXPOSURE / 6.0).
GROUND_MODULE_GAIN = 0.035 / (0.03 * 6.0 * NIGHT)
for lo in mlights:
    lo.data.energy *= GROUND_MODULE_GAIN
bake_ground = bake(ground, "T_HwGround", 4096, exposure=GROUND_EXPOSURE, samples=128, smooth=4)
for lo in mlights:
    lo.data.energy /= GROUND_MODULE_GAIN
log(f"ground: the modules' {len(mlights)} lights baked onto it x{GROUND_MODULE_GAIN:.2f} (their preview level)")
bake_crowd = bake(crowd, "T_HwCrowd", 4096, exposure=CROWD_EXPOSURE, samples=128, margin=2) if crowd else None
hands.hide_render = False

# what the Quest shows: every surface unlit, one material per mesh
for lt in [o for o in coll.objects if o.type == "LIGHT"]:
    bpy.data.objects.remove(lt)
for ob, path in ((facade, bake_facade), (detail, bake_detail), (deck, bake_deck), (rig, bake_rig), (hands, bake_hands),
                 (gate, bake_gate),
                 (ground, bake_ground), *bake_grounds, *(((crowd, bake_crowd),) if crowd else ())):
    assign(ob, mat_emit("P" + ob.name, image=load_png(path)))
for ob in GLOWS + [bats] + ([gglow] if gglow else []) + own_glows + ([phones] if phones else []):
    ob.data.materials[0].node_tree.nodes["Emission"].inputs["Strength"].default_value = 1.0
assign(screen, mat_emit("PScreen", (0.0, 0.0, 0.0)))
beam_img, halo_img = load_png(os.path.join(OUT, "T_HwBeam.png")), load_png(os.path.join(OUT, "T_HwHalo.png"))
for ob in (beams_ob, lasers_ob, search_ob, bolts_ob):
    assign(ob, mat_alpha("A" + ob.name, beam_img))
assign(halos_ob, mat_alpha("A" + halos_ob.name, halo_img))
assign(fire, mat_alpha("AFire", load_png(os.path.join(OUT, "T_HwFire.png"))))
assign(ghosts, mat_fade("AGhosts", (0.55, 1.0, 0.65), alpha=0.25))
if fog:
    assign(fog, mat_fade("AFog", FOG_RGB, image=load_png(os.path.join(OUT, "T_HwFogNoise.png"))))
if gtrans:
    gb, gh = load_png(os.path.join(OUT, "T_HwGroundsBeam.png")), load_png(os.path.join(OUT, "T_HwGroundsHalo.png"))
    for ob in gtrans:
        assign(ob, mat_alpha("A" + ob.name, gh if ob.name.startswith("SM_HwGHalos") else gb))
for ob in TRANS + [bats]:
    ob.hide_render = False
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
names = []
for ob in SOLID + TRANS:
    export_fbx(ob)
    names.append(ob.name)
with open(os.path.join(OUT, "manifest.txt"), "w") as mf:                 # build_halloween.py imports exactly these
    mf.write("\n".join(names) + "\n")
with open(os.path.join(OUT, "hw_groups.json"), "w") as jf:                # module beam groups -> show row
    json.dump(groups, jf, indent=1)
log(f"manifest: {len(names)} meshes; groups {groups}")

# previews (EEVEE, Standard, no bloom: Tribe renders unlit with MobileHDR off); the crowd posed mid-dance
if crowd_mod is not None and hasattr(crowd_mod, "pose_preview"):
    try:
        crowd_mod.pose_preview([crowd, phones], 0.31)
    except Exception as e:  # noqa: BLE001
        log(f"crowd pose_preview failed ({e!r}): previews show the rest pose")
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.eevee.taa_render_samples = 16
scene.eevee.use_shadows = False
scene.render.resolution_x, scene.render.resolution_y = 1280, 720
scene.render.use_compositing = False
cam_data = bpy.data.cameras.new("cam")
cam_data.clip_end = 3000
cam = bpy.data.objects.new("cam", cam_data)
coll.objects.link(cam)
scene.camera = cam
PREVIEWS = {"stream": ((0, -9, 3.5), (0, 6, 9), 16), "dj_back": ((0, -1.0, 1.7), (0, 10, 13), 16),
            "facade": ((0, -55, 6.0), (0, 12, 18), 24), "dj_front": ((0, 0.9, 1.7), (0, -40, -1.0), 18),
            "aerial": ((-70, -95, 55), (0, -20, 0), 24), "crowd": ((3, -40, -0.8), (0, 8, 11), 20),
            "riser": ((2.6, -6.5, 1.0), (0, 0.5, 0.6), 22), "side_left": ((-80, -30, 15), (0, -40, -2), 24)}
for name, (pos, tgt, lens) in PREVIEWS.items():
    cam_data.lens = lens
    cam.location = pos
    cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, f"preview_{name}.png")
    bpy.ops.render.render(write_still=True)
    log("preview " + scene.render.filepath)
log("done")
