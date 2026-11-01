# REACTOR club generator for the Tribe XR mod kit (Blender 4.5, headless):
#   D:\Tools\blender-4.5.14-windows-x64\blender.exe -b --factory-startup --python club_stage.py [-- --fast]
# Builds the REACTOR indoor club (claudedocs/club_venue_plan.md, tribe hack repo; layout in club_layout.py): the hall, the
# core bay with the reactor vessel behind the screen, the stage with its control-console booth, the containment airlock
# (the stage gate), the mezzanines and lounge, the COOLANT BAR and entrance, the rig (trusses, moving heads, laser bar,
# pixel strips) and the screens. Lighting is BAKED into textures on the GPU (Cycles) the way dino_stage.py does it, and
# v1 ships on Tribe's own unlit glTFRuntime instances: a static night ("between hits") room with frozen beams and lasers.
# The animated show (cue table, sweeping lasers, the crowd) is phase 3.
#
# Frame: meters, Z up, the DJ at the origin facing -Y, the stage deck = Tribe's floor (z 0), the dance floor at
# club_layout.FLOOR. No stage drop: everything is modeled where it ships. The Unreal import (build_club.py) checks where
# the screen landed and turns the level around if the FBX axis conversion mirrored Y (as build_dino.py does).
# Output (CLUB_OUT=<dir>, default ./out_club): SM_Club*.fbx + SM_DinoVisualScreen.fbx (the hook finds the screen by that
# mesh name), T_Club*.png, manifest.txt, preview_*.png. --fast: 1/8-size bakes with 4 samples (pipeline test; never ship).
# Helper functions are copied from dino_stage.py (that file runs its build at import, so it cannot be imported).
import json
import math
import os
import random
import struct
import sys
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "grounds"))
import kit as gkit  # noqa: E402  (primitives, the glow palette, beams and halos; read-only use)
sys.path.insert(0, HERE)
import club_crowd  # noqa: E402  (the club's copy of crowd v3: our points and zones, the pivot channel)
import club_layout as L  # noqa: E402
import club_show  # noqa: E402  (the cue table T_ClubCues and its rows)
import club_lasers  # noqa: E402  (v5: the sweeping lasers, in the Dino laser engine's format)
import club_laser_scenes  # noqa: E402  (v6: the Dino's laser scenes mapped onto the club's rigs)
import club_movers  # noqa: E402  (v7: the moving heads move, the Dino's v13 mover engine)
sys.path.insert(1, os.path.join(HERE, ".."))
import show as dino_show  # noqa: E402  (the Dino's show.py, read only: its laser program and pattern library)
from club_spots import club_points  # noqa: E402  (the crowd's spots, shared with club_collide.py)

gkit.DJ_EYE = Vector(L.DJ_EYE)      # in-process only: halos face the DJ's eye (kit's default is Dino's pre-drop head)
OUT = os.environ.get("CLUB_OUT") or os.path.join(HERE, "out_club")
os.makedirs(OUT, exist_ok=True)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FAST = "--fast" in ARGS
NIGHT = 0.35                         # every bake x0.35 (Dino's night pass is 0.5; the user on v1, 2026-10-08: "we can make
                                     # it a little darker")
random.seed(55)
rng = random.Random(55)


def log(msg):
    print("[CLUB] " + msg, flush=True)


# ---------------------------------------------------------------- PNG I/O (sRGB 8-bit), copied from dino_stage.py
def srgb(lin):
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


def write_png(path, rgb_lin_top_down):
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
    return 1.0 - np.exp(-lin * exposure)          # soft shoulder: baked highlights never clip to flat white


# ---------------------------------------------------------------- scene (Cycles on the GPU), copied from dino_stage.py
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
for dev_type in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = dev_type
        prefs.refresh_devices()
        gpus = [d for d in prefs.devices if d.type == dev_type]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == dev_type
            scene.cycles.device = "GPU"
            log(f"Cycles on {dev_type}: {[d.name for d in gpus]}")
            break
    except Exception as e:  # noqa: BLE001
        log(f"{dev_type} unavailable: {e}")
scene.view_settings.view_transform = "Standard"
coll = scene.collection


def new_obj(name, bm, mats=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    for m in mats or []:
        me.materials.append(m)
    return ob


def setmat(faces, idx):
    for f in faces:
        f.material_index = idx
    return faces


def merge(dst, src):
    """Append src into dst keeping material indices and the UVMap layer (palette / beam / halo UVs). Repeated items are
    built in their own small bmesh and merged: a bmesh op on one growing mesh costs O(mesh) (Halloween blockout)."""
    lay_d = dst.loops.layers.uv.get("UVMap") or dst.loops.layers.uv.new("UVMap")
    lay_s = src.loops.layers.uv.get("UVMap")
    vmap = {v: dst.verts.new(v.co) for v in src.verts}
    for f in src.faces:
        try:
            nf = dst.faces.new([vmap[v] for v in f.verts])
        except ValueError:
            continue
        nf.material_index = f.material_index
        if lay_s is not None:
            for ld, ls in zip(nf.loops, f.loops):
                ld[lay_d].uv = ls[lay_s].uv
    src.free()


def glow(bm, faces, key):
    gkit.glow_faces(bm, faces, key)
    return faces


def text(bm, s, center, right, pixel, gap, key):
    """kit.led_text centred on `center` (the bottom edge's middle). right (1,0,0) faces -Y (the crowd), (-1,0,0) faces
    +Y (the stage), (0,-1,0) faces -X (the stage, from the right-hand wall)."""
    w = gkit.text_width(s, pixel)
    r = Vector(right)
    return gkit.led_text(bm, s, Vector(center) - r * (w / 2), r, (0, 0, 1), pixel=pixel, gap=gap, key=key)


# ---------------------------------------------------------------- the room's solids (beams and lasers end on them)
def solid(p):
    x, y, z = p
    if abs(x) >= L.HX or y <= L.Y_BACK or y >= L.Y_BAY or z <= L.FLOOR:
        return True
    if z >= (L.CEIL if y < L.LIP_Y else L.STAGE_CEIL):
        return True
    if y >= L.LIP_Y and z <= 0.0:
        return True
    if y >= L.SCREEN_Y - 0.05 and abs(x) <= L.SCREEN_HW + L.FRAME_W and z <= L.SCREEN_Z1 + L.FRAME_W:
        return True
    if L.MZ_X0 <= abs(x) and L.MZ_Y0 <= y <= L.MZ_Y1 and L.MZ_Z - 0.3 <= z <= L.MZ_Z:
        return True
    return False


def beam_len(o, d, maxlen=70.0, step=0.05):
    t = 0.3
    while t < maxlen and not solid(o + d * t):
        t += step
    return t


# ---------------------------------------------------------------- builders (each returns lit bmeshes; glow goes to G)
G = bmesh.new()                                    # every static unlit emitter: faces UV'd into the palette (T_ClubGlowPal)
LENS, COREG, PIXB, PIXA = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()   # animated emitters (phase 3a): lenses,
for _b in (G, LENS, COREG, PIXB, PIXA):           # the core's rings, blue / amber pixel strips (chase)
    gkit.uv_layer(_b)


def build_floor():
    """SM_ClubFloor: the dance floor and back floor (mats: floor 0, hazard 1). Under the stage nothing: the deck covers."""
    bm = bmesh.new()
    setmat(gkit.box(bm, (0, (L.Y_BACK + L.LIP_Y) / 2, L.FLOOR - 0.1), (2 * L.HX, L.LIP_Y - L.Y_BACK, 0.2)), 0)
    setmat(gkit.box(bm, (0, L.BARRIER_Y - 0.4, L.FLOOR + 0.004), (2 * L.STAGE_HW, 0.5, 0.008)), 1)     # hazard band
    setmat(gkit.box(bm, ((L.AIR_X0 + L.AIR_X1) / 2, L.AIR_Y0 - 0.95, L.FLOOR + 0.004), (4.0, 1.6, 0.008)), 1)
    return bm


def build_hall():
    """SM_ClubHall: walls, ceilings, the proscenium step, the bay's back wall, columns, ribs, wall pipes
    (mats: concrete 0, concrete_dark 1, steel 2). Glow: the blue LED lines on the columns and ribs, pipe bands."""
    bm = bmesh.new()
    zmid, zh = (L.FLOOR + L.STAGE_CEIL) / 2, L.STAGE_CEIL - L.FLOOR
    for sx in (-1, 1):                                                        # side walls, floor to the stage ceiling
        setmat(gkit.box(bm, (sx * (L.HX + 0.2), (L.Y_BACK + L.Y_BAY) / 2, zmid), (0.4, L.Y_BAY - L.Y_BACK, zh)), 0)
    setmat(gkit.box(bm, ((-L.HX + L.EX0) / 2, L.Y_BACK - 0.2, (L.FLOOR + L.CEIL) / 2), (L.EX0 + L.HX, 0.4, L.CEIL - L.FLOOR)), 0)
    setmat(gkit.box(bm, ((L.EX1 + L.HX) / 2, L.Y_BACK - 0.2, (L.FLOOR + L.CEIL) / 2), (L.HX - L.EX1, 0.4, L.CEIL - L.FLOOR)), 0)
    setmat(gkit.box(bm, ((L.EX0 + L.EX1) / 2, L.Y_BACK - 0.2, (L.FLOOR + L.EX_H + L.CEIL) / 2),
                    (L.EX1 - L.EX0, 0.4, L.CEIL - L.FLOOR - L.EX_H)), 0)
    setmat(gkit.box(bm, (0, L.Y_BAY + 0.2, L.STAGE_CEIL / 2), (2 * L.HX, 0.4, L.STAGE_CEIL)), 1)
    setmat(gkit.box(bm, (0, (L.Y_BACK + L.LIP_Y) / 2, L.CEIL + 0.1), (2 * L.HX, L.LIP_Y - L.Y_BACK, 0.2)), 1)
    setmat(gkit.box(bm, (0, (L.LIP_Y + L.Y_BAY) / 2, L.STAGE_CEIL + 0.1), (2 * L.HX, L.Y_BAY - L.LIP_Y, 0.2)), 1)
    setmat(gkit.box(bm, (0, L.LIP_Y - 0.2, (L.CEIL + L.STAGE_CEIL) / 2), (2 * L.HX, 0.4, L.STAGE_CEIL - L.CEIL)), 1)
    for sx in (-1, 1):
        for cy in L.COL_Y:
            if sx < 0 and cy > L.AIR_Y0 - 1.0:                                 # the airlock frame carries that bay
                continue
            top = L.CEIL if cy < L.LIP_Y else L.STAGE_CEIL
            setmat(gkit.box(bm, (sx * (L.HX - 0.3), cy, (L.FLOOR + top) / 2), (0.6, 0.6, top - L.FLOOR)), 2)
            glow(G, gkit.box(G, (sx * (L.HX - 0.62), cy, (L.FLOOR + 0.6 + top - 0.4) / 2), (0.04, 0.08, top - 1.0 - L.FLOOR)),
                 "blue_dim")
        for pz in (6.4, 7.1):                                                 # coolant pipes along the walls
            setmat(gkit.cyl(bm, (sx * (L.HX - 0.35), L.Y_BACK + 0.5, pz), (sx * (L.HX - 0.35), L.SCREEN_Y - 0.5, pz), 0.22, segs=10), 2)
            for by in range(int(L.Y_BACK + 2), int(L.SCREEN_Y - 1), 3):
                glow(G, gkit.cyl(G, (sx * (L.HX - 0.35), by, pz), (sx * (L.HX - 0.35), by + 0.15, pz), 0.235, segs=10), "blue")
    for cy in L.COL_Y[1:-1]:                                                   # ceiling ribs over the floor, LED under each
        setmat(gkit.box(bm, (0, cy, L.CEIL - 0.25), (2 * L.HX, 0.4, 0.5)), 2)
        glow(G, gkit.box(G, (0, cy, L.CEIL - 0.52), (2 * L.HX - 1.2, 0.06, 0.04)), "blue")
    return bm


def build_stage():
    """SM_ClubStage: deck + wings + bay floor (one slab, top z 0), the console booth, rod columns, the wing rail and the
    backstage door, the crowd barrier, the airlock (frame, stairs, closed doors, vestibule), the screen frame, the side
    screens' frames, the name plate (mats: deck 0, steel 1, hazard 2, glass 3, panel 4). Glow: lip strip, console lights,
    rod light, door frame + sign, barrier strip, airlock frame/beacon/signs, the pixel fascia, the REACTOR plate."""
    bm = bmesh.new()
    setmat(gkit.box(bm, (0, (L.LIP_Y + L.Y_BAY) / 2, -0.6), (2 * L.HX, L.Y_BAY - L.LIP_Y, 1.2)), 0)
    setmat(gkit.box(bm, (0, L.LIP_Y + 0.12, 0.004), (2 * L.STAGE_HW, 0.2, 0.008)), 2)            # hazard edge on the lip
    T = L.TABLE                                                                                   # the console (Dino TABLE)
    setmat(gkit.box(bm, ((T["x0"] + T["x1"]) / 2, (T["y0"] + T["y1"]) / 2, T["top"] / 2),
                    (T["x1"] - T["x0"], T["y1"] - T["y0"], T["top"])), 4)
    setmat(gkit.box(bm, ((T["x0"] + T["x1"]) / 2, (T["y0"] + T["y1"]) / 2, T["top"] - 0.02),
                    (T["x1"] - T["x0"] + 0.12, T["y1"] - T["y0"] + 0.12, 0.04)), 1)
    for r in range(3):                                                                            # switch lights
        for c in range(12):
            glow(G, gkit.box(G, (T["x0"] + 0.1 + c * 0.145, T["y0"] - 0.015, 0.22 + r * 0.16), (0.05, 0.02, 0.05)),
                 ("amber", "red", "green")[(r * 7 + c * 5) % 3])
    glow(G, gkit.box(G, ((T["x0"] + T["x1"]) / 2, T["y0"] - 0.015, T["top"] - 0.05), (T["x1"] - T["x0"] - 0.04, 0.02, 0.025)), "blue")
    for sx in (-1, 1):                                                                            # control-rod light columns
        setmat(gkit.cyl(bm, (sx * L.ROD_X, L.ROD_Y, 0), (sx * L.ROD_X, L.ROD_Y, 0.15), 0.28, segs=12), 1)
        setmat(gkit.cyl(bm, (sx * L.ROD_X, L.ROD_Y, 3.6), (sx * L.ROD_X, L.ROD_Y, 3.75), 0.28, segs=12), 1)
        setmat(gkit.cyl(bm, (sx * L.ROD_X, L.ROD_Y, 0.15), (sx * L.ROD_X, L.ROD_Y, 3.6), 0.2, segs=12, cap=False), 3)
        glow(G, gkit.cyl(G, (sx * L.ROD_X, L.ROD_Y, 0.2), (sx * L.ROD_X, L.ROD_Y, 2.5), 0.1, segs=8), "sky")
    for x in (8.2, 9.4, 10.6, 11.8):                                                              # right wing rail
        setmat(gkit.cyl(bm, (x, L.LIP_Y + 0.05, 0), (x, L.LIP_Y + 0.05, 1.1), 0.04, segs=5), 1)
    setmat(gkit.cyl(bm, (L.STAGE_HW, L.LIP_Y + 0.05, 1.1), (L.HX, L.LIP_Y + 0.05, 1.1), 0.04, segs=5), 1)
    setmat(gkit.box(bm, (L.HX - 0.05, 4.0, 1.2), (0.1, 1.4, 2.4)), 4)                             # backstage door
    glow(G, gkit.box(G, (L.HX - 0.12, 4.0, 2.47), (0.04, 1.6, 0.06)), "amber")
    for y in (3.24, 4.76):
        glow(G, gkit.box(G, (L.HX - 0.12, y, 1.2), (0.04, 0.06, 2.4)), "amber")
    text(G, "CONTROL ROOM", (L.HX - 0.14, 4.0, 2.62), (0, -1, 0), 0.05, 0.012, "amber")
    # crowd barrier
    for i in range(9):
        setmat(gkit.box(bm, (-L.STAGE_HW + i * 2, L.BARRIER_Y, L.FLOOR + 0.55), (0.08, 0.5, 1.1)), 1)
    setmat(gkit.box(bm, (0, L.BARRIER_Y, L.FLOOR + 1.08), (2 * L.STAGE_HW, 0.08, 0.06)), 1)
    setmat(gkit.box(bm, (0, L.BARRIER_Y, L.FLOOR + 0.6), (2 * L.STAGE_HW, 0.03, 0.9)), 1)
    glow(G, gkit.box(G, (0, L.BARRIER_Y - 0.05, L.FLOOR + 1.12), (2 * L.STAGE_HW, 0.02, 0.02)), "warm_dim")
    glow(G, gkit.box(G, (0, L.LIP_Y - 0.02, -0.015), (2 * L.STAGE_HW, 0.04, 0.03)), "blue")       # lip LED strip
    # the airlock: stairs, frame with the doorway, lintel, vestibule roof, glass side, closed doors
    rise = (0.0 - L.FLOOR) / L.STAIR_N
    for i in range(L.STAIR_N):
        y0, top = L.STAIR_Y0 + 0.3 * i, L.FLOOR + rise * (i + 1)
        setmat(gkit.box(bm, ((L.AIR_X0 + L.AIR_X1) / 2, (y0 + L.LIP_Y) / 2, (L.FLOOR + top) / 2), (3.2, L.LIP_Y - y0, top - L.FLOOR)), 1)
    zc, zh = (L.FLOOR + L.LINTEL_TOP) / 2, L.LINTEL_TOP - L.FLOOR
    setmat(gkit.box(bm, ((L.AIR_X0 + L.DOOR_X0) / 2, L.AIR_Y0, zc), (L.DOOR_X0 - L.AIR_X0, 0.3, zh)), 2)
    setmat(gkit.box(bm, ((L.DOOR_X1 + L.AIR_X1) / 2, L.AIR_Y0, zc), (L.AIR_X1 - L.DOOR_X1, 0.3, zh)), 2)
    setmat(gkit.box(bm, ((L.AIR_X0 + L.AIR_X1) / 2, L.AIR_Y0, (L.DOOR_TOP + L.LINTEL_TOP) / 2),
                    (L.AIR_X1 - L.AIR_X0, 0.3, L.LINTEL_TOP - L.DOOR_TOP)), 1)
    setmat(gkit.box(bm, ((L.AIR_X0 + L.AIR_X1) / 2, (L.AIR_Y0 + L.AIR_Y1) / 2, L.LINTEL_TOP + 0.05),
                    (L.AIR_X1 - L.AIR_X0, L.AIR_Y1 - L.AIR_Y0, 0.1)), 1)
    setmat(gkit.box(bm, (L.AIR_X1, (L.AIR_Y0 + L.AIR_Y1) / 2, zc), (0.05, L.AIR_Y1 - L.AIR_Y0, zh)), 3)
    half = (L.DOOR_X1 - L.DOOR_X0) / 2
    for a in (L.DOOR_X0, L.DOOR_MID):                                                             # closed (v1)
        setmat(gkit.box(bm, (a + half / 2, L.AIR_Y0 - 0.21, (L.FLOOR + L.DOOR_TOP) / 2), (half - 0.02, 0.1, L.DOOR_TOP - L.FLOOR)), 1)
        setmat(gkit.box(bm, (a + half / 2, L.AIR_Y0 - 0.265, 0.1), (half - 0.02, 0.01, 0.35)), 2)
    for x in (L.DOOR_X0 - 0.02, L.DOOR_X1 + 0.02):
        glow(G, gkit.box(G, (x, L.AIR_Y0 - 0.16, (L.FLOOR + L.DOOR_TOP) / 2), (0.04, 0.02, L.DOOR_TOP - L.FLOOR)), "warm_dim")
    glow(G, gkit.box(G, (L.DOOR_MID, L.AIR_Y0 - 0.16, L.DOOR_TOP + 0.02), (L.DOOR_X1 - L.DOOR_X0 + 0.08, 0.02, 0.04)), "warm_dim")
    glow(G, gkit.cyl(G, (L.DOOR_MID, L.AIR_Y0, L.LINTEL_TOP + 0.1), (L.DOOR_MID, L.AIR_Y0, L.LINTEL_TOP + 0.45), 0.14, segs=12), "red")
    xc = (L.AIR_X0 + L.AIR_X1) / 2
    text(G, "CONTAINMENT", (xc, L.AIR_Y0 - 0.17, 1.98), (1, 0, 0), 0.045, 0.01, "amber")
    text(G, "DJS ONLY", (xc, L.AIR_Y0 - 0.17, 1.5), (1, 0, 0), 0.06, 0.012, "red")
    # the screen's hazard frame + the REACTOR name plate on its top bar
    fw = L.FRAME_W
    setmat(gkit.box(bm, (0, L.SCREEN_Y + 0.1, L.SCREEN_Z1 + fw / 2), (2 * L.SCREEN_HW + 2 * fw, 0.3, fw)), 2)
    setmat(gkit.box(bm, (0, L.SCREEN_Y + 0.1, L.SCREEN_Z0 / 2), (2 * L.SCREEN_HW + 2 * fw, 0.3, L.SCREEN_Z0)), 2)
    for sx in (-1, 1):
        setmat(gkit.box(bm, (sx * (L.SCREEN_HW + fw / 2), L.SCREEN_Y + 0.1, (L.SCREEN_Z1 + fw) / 2), (fw, 0.3, L.SCREEN_Z1 + fw)), 2)
    setmat(gkit.box(bm, (0, L.SCREEN_Y - 0.04, L.SCREEN_Z1 + 0.3), (3.8, 0.04, 0.6)), 4)
    text(G, "REACTOR", (0.0, L.SCREEN_Y - 0.07, L.SCREEN_Z1 + 0.02), (1, 0, 0), 0.08, 0.016, "amber")
    for c, n, t in side_frames():                                                                 # side-screen backings
        setmat(gkit.box(bm, c - n * 0.12, (2 * L.SIDE_HW + 0.3, 0.15, 2 * L.SIDE_HH + 0.25), yaw=math.atan2(t.y, t.x)), 1)
    # the pixel fascia across the stage front: 40 x 3 tiles, frozen on one frame of a chase
    cols, rows = 40, 3
    for c in range(cols):
        for r in range(rows):
            z = L.FLOOR + 0.06 + (r + 0.5) * 0.95 / rows                # a chase runs across it in the game
            glow(PIXB, gkit.box(PIXB, (-L.STAGE_HW + (c + 0.5) * 2 * L.STAGE_HW / cols, L.LIP_Y - 0.03, z),
                                (2 * L.STAGE_HW / cols - 0.05, 0.02, 0.95 / rows - 0.05)), "blue")
    return bm


def side_frames():
    """(centre, facing normal n, the viewer's right t) of each side screen (turned to face (0, SIDE_AIM_Y))."""
    out = []
    for c in L.SIDE_C:
        c = Vector(c)
        n = Vector((0.0, L.SIDE_AIM_Y, 0.0)) - Vector((c.x, c.y, 0.0))
        n.normalize()
        t = (-n).cross(Vector((0, 0, 1)))          # the viewer looks along -n; their right
        out.append((c, n, t.normalized()))
    return out


def screen_quad(bm, uv, c, n, t, hw, hh):
    """One screen quad facing n with Tribe's back-wall UV0 layout (Session 3v): U = 0.5 - s/w from the viewer's left to
    right, Blender V = 0.5 * (z - bottom) / h (UE flips V: 0.5 at the top, 1.0 at the bottom). M_VideoBackdrop samples
    (1-U, 2V-1), so the frame lands the right way round."""
    up = Vector((0, 0, hh))
    pts = [c - t * hw - up, c + t * hw - up, c + t * hw + up, c - t * hw + up]
    f = bm.faces.new([bm.verts.new(p) for p in pts])
    f.normal_update()
    if f.normal.dot(n) < 0:
        f.normal_flip()
    for lp in f.loops:
        p = lp.vert.co
        s = (p - c).dot(t)
        lp[uv].uv = (0.5 - s / (2 * hw), 0.5 * (p.z - (c.z - hh)) / (2 * hh))


def build_screens():
    """SM_DinoVisualScreen (the hook registers it as Tribe's backdrop by this mesh name) and SM_ClubSideScreens (the
    mod mirrors the video onto them in phase 2)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    hh = (L.SCREEN_Z1 - L.SCREEN_Z0) / 2
    screen_quad(bm, uv, Vector((0.0, L.SCREEN_Y, L.SCREEN_Z0 + hh)), Vector((0, -1, 0)), Vector((1, 0, 0)), L.SCREEN_HW, hh)
    main = new_obj("SM_DinoVisualScreen", bm)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    for c, n, t in side_frames():
        screen_quad(bm, uv, c, n, t, L.SIDE_HW, L.SIDE_HH)
    return main, new_obj("SM_ClubSideScreens", bm)


def build_core():
    """SM_ClubCore: the vessel and dome, rod drives, drive towers, the bay's pipes (mats: steel 0, concrete_dark 1,
    hazard 2). Glow: the fuel-rod rings (sky), the towers' red beacons, pipe bands."""
    bm = bmesh.new()
    vx, vy, vr, vt = L.VESSEL_X, L.VESSEL_Y, L.VESSEL_R, L.VESSEL_TOP
    setmat(gkit.cyl(bm, (vx, vy, 0), (vx, vy, vt), vr, segs=32), 0)
    setmat(gkit.sphere(bm, (vx, vy, vt), vr, segs=32, rings=12, scale=(1, 1, 0.8)), 0)
    for z in (1.6, 4.0, 6.4, 8.8):
        glow(COREG, gkit.cyl(COREG, (vx, vy, z), (vx, vy, z + 0.14), vr + 0.05, segs=32), "sky")
    for dz in (0.8, 1.7, 2.3):
        r = vr * math.sqrt(max(0.0, 1 - (dz / (vr * 0.8)) ** 2))
        glow(COREG, gkit.cyl(COREG, (vx, vy, vt + dz), (vx, vy, vt + dz + 0.1), r + 0.05, segs=32), "sky")
    for i in range(9):
        a = i * 2 * math.pi / 9
        p = (vx + 0.7 * math.cos(a), vy + 0.7 * math.sin(a))
        setmat(gkit.cyl(bm, (*p, vt + 2.3), (*p, L.STAGE_CEIL - 0.25), 0.1, segs=6), 0)
    for sx in (-1, 1):
        setmat(gkit.box(bm, (sx * L.TOWER_X, L.TOWER_Y, 5.5), (1.3, 1.3, 11.0)), 0)
        for z in (2.0, 6.0, 10.0):
            setmat(gkit.box(bm, (sx * L.TOWER_X, L.TOWER_Y, z), (1.34, 1.34, 0.5)), 2)
        glow(G, gkit.cyl(G, (sx * L.TOWER_X, L.TOWER_Y, 11.0), (sx * L.TOWER_X, L.TOWER_Y, 11.35), 0.16, segs=10), "red")
    for z in (2.0, 4.2, 6.4, 8.6, 10.8):
        setmat(gkit.cyl(bm, (-L.HX + 0.4, L.Y_BAY - 0.5, z), (L.HX - 0.4, L.Y_BAY - 0.5, z), 0.28, segs=10), 0)
        for x in range(-10, 11, 4):
            glow(G, gkit.cyl(G, (x, L.Y_BAY - 0.5, z), (x + 0.15, L.Y_BAY - 0.5, z), 0.3, segs=10), "blue")
    return bm


def build_mezz():
    """SM_ClubMezz: both mezzanines (decks, railings, supports, stairs, the side-laser poles) and the lounge under them
    (mats: steel 0, grate 1, sofa 2, wood 3). Glow: fascia strips, lounge lamps."""
    bm = bmesh.new()
    for sx in (-1, 1):
        setmat(gkit.box(bm, (sx * (L.MZ_X0 + L.MZ_X1) / 2, (L.MZ_Y0 + L.MZ_Y1) / 2, L.MZ_Z - 0.15),
                        (L.MZ_X1 - L.MZ_X0, L.MZ_Y1 - L.MZ_Y0, 0.3)), 1)
        xi = sx * (L.MZ_X0 + 0.08)
        for k in range(11):
            y = L.MZ_Y0 + k * (L.MZ_Y1 - L.MZ_Y0) / 10
            setmat(gkit.cyl(bm, (xi, y, L.MZ_Z), (xi, y, L.MZ_Z + 1.1), 0.04, segs=5), 0)
        setmat(gkit.cyl(bm, (xi, L.MZ_Y0, L.MZ_Z + 1.1), (xi, L.MZ_Y1, L.MZ_Z + 1.1), 0.05, segs=6), 0)
        setmat(gkit.cyl(bm, (xi, L.MZ_Y0, L.MZ_Z + 0.55), (xi, L.MZ_Y1, L.MZ_Z + 0.55), 0.03, segs=5), 0)
        setmat(gkit.cyl(bm, (sx * L.MZ_X0, L.MZ_Y1 - 0.08, L.MZ_Z + 1.1), (sx * L.MZ_X1, L.MZ_Y1 - 0.08, L.MZ_Z + 1.1), 0.05, segs=6), 0)
        for x in (L.MZ_X0 + 1.3, L.MZ_X0 + 2.6):
            setmat(gkit.cyl(bm, (sx * x, L.MZ_Y1 - 0.08, L.MZ_Z), (sx * x, L.MZ_Y1 - 0.08, L.MZ_Z + 1.1), 0.04, segs=5), 0)
        for y in (-23.5, -19.5, -15.5, -11.5, -8.5):
            setmat(gkit.box(bm, (sx * (L.MZ_X0 + 0.3), y, (L.FLOOR + L.MZ_Z - 0.3) / 2), (0.3, 0.3, L.MZ_Z - 0.3 - L.FLOOR)), 0)
        glow(PIXB, gkit.box(PIXB, (sx * (L.MZ_X0 - 0.01), (L.MZ_Y0 + L.MZ_Y1) / 2, L.MZ_Z - 0.08), (0.03, L.MZ_Y1 - L.MZ_Y0, 0.06)), "blue")
        glow(PIXA, gkit.box(PIXA, (sx * (L.MZ_X0 - 0.01), (L.MZ_Y0 + L.MZ_Y1) / 2, L.MZ_Z - 0.24), (0.03, L.MZ_Y1 - L.MZ_Y0, 0.04)), "amber")
        n = 20
        for i in range(n):                                                   # stairs along the wall: floor -> deck
            y0, top = L.MZ_STAIR_Y0 + 0.3 * i, L.FLOOR + (L.MZ_Z - L.FLOOR) * (i + 1) / n
            setmat(gkit.box(bm, (sx * 11.25, (y0 + L.MZ_Y0) / 2, (L.FLOOR + top) / 2), (1.3, L.MZ_Y0 - y0, top - L.FLOOR)), 0)
        setmat(gkit.cyl(bm, (sx * 10.55, L.MZ_STAIR_Y0, L.FLOOR + 1.0), (sx * 10.55, L.MZ_Y0, L.MZ_Z + 1.0), 0.04, segs=5), 0)
        setmat(gkit.cyl(bm, (sx * 8.4, L.MZ_Y1 - 0.2, L.MZ_Z), (sx * 8.4, L.MZ_Y1 - 0.2, 4.6), 0.06, segs=6), 0)
        for y in (-21.0, -15.0, -9.8):                                       # lounge booths under the deck
            setmat(gkit.box(bm, (sx * 11.35, y, L.FLOOR + 0.22), (0.9, 2.6, 0.45)), 2)
            setmat(gkit.box(bm, (sx * 11.75, y, L.FLOOR + 0.6), (0.25, 2.6, 0.9)), 2)
            setmat(gkit.box(bm, (sx * 10.3, y, L.FLOOR + 0.22), (0.7, 1.0, 0.45)), 3)
            glow(G, gkit.sphere(G, (sx * 10.3, y, L.FLOOR + 0.55), 0.1, segs=6, rings=4), "amber")
    return bm


def build_bar():
    """SM_ClubBar: the counter, back-bar shelves, stools and the entrance's decontamination corridor (mats: steel 0,
    wood 1, concrete_dark 2). Glow: coolant tubes, bottles, the signs, the corridor's UV strips."""
    bm = bmesh.new()
    xc = (L.BAR_X0 + L.BAR_X1) / 2
    setmat(gkit.box(bm, (xc, L.BAR_Y, L.FLOOR + 0.55), (L.BAR_X1 - L.BAR_X0, 0.8, 1.1)), 0)
    setmat(gkit.box(bm, (xc, L.BAR_Y, L.FLOOR + 1.12), (L.BAR_X1 - L.BAR_X0 + 0.2, 1.0, 0.05)), 1)
    for k in range(34):
        x = L.BAR_X0 + 0.15 + k * (L.BAR_X1 - L.BAR_X0 - 0.3) / 33
        glow(G, gkit.cyl(G, (x, L.BAR_Y - 0.43, L.FLOOR + 0.1), (x, L.BAR_Y - 0.43, L.FLOOR + 1.0), 0.055, segs=6),
             "blue" if k % 2 else "blue_dim")
    for z in (L.FLOOR + 1.3, L.FLOOR + 1.9, L.FLOOR + 2.5):
        setmat(gkit.box(bm, (xc, L.Y_BACK + 0.25, z), (L.BAR_X1 - L.BAR_X0, 0.4, 0.05)), 0)
        x = L.BAR_X0 + 0.2
        while x < L.BAR_X1 - 0.2:
            glow(G, gkit.box(G, (x, L.Y_BACK + 0.25, z + 0.17), (0.08, 0.08, 0.3)), rng.choice(("amber", "blue", "green", "white_dim")))
            x += 0.24 + rng.uniform(0, 0.08)
    for k in range(12):
        x = L.BAR_X0 + 0.5 + k * (L.BAR_X1 - L.BAR_X0 - 1.0) / 11
        setmat(gkit.cyl(bm, (x, L.BAR_Y - 0.95, L.FLOOR), (x, L.BAR_Y - 0.95, L.FLOOR + 0.75), 0.18, segs=8), 0)
    text(G, "COOLANT", (xc, L.Y_BACK + 0.06, L.FLOOR + 3.2), (-1, 0, 0), 0.07, 0.015, "blue")   # the user: no "BAR" word
    text(G, "REACTOR", (xc, L.Y_BACK + 0.06, L.FLOOR + 4.0), (-1, 0, 0), 0.15, 0.03, "amber")
    ez, d = L.FLOOR + L.EX_H, L.EX_DEPTH
    ec = (L.EX0 + L.EX1) / 2
    setmat(gkit.box(bm, (ec, L.Y_BACK - d / 2, L.FLOOR - 0.1), (L.EX1 - L.EX0 + 0.8, d, 0.2)), 2)
    for x in (L.EX0 - 0.2, L.EX1 + 0.2):
        setmat(gkit.box(bm, (x, L.Y_BACK - d / 2, (L.FLOOR + ez) / 2), (0.4, d, ez - L.FLOOR)), 2)
        xs = x + (0.25 if x < L.EX0 else -0.25)
        glow(G, gkit.box(G, (xs, L.Y_BACK - d / 2, ez - 0.3), (0.04, d - 0.4, 0.05)), "uv")
        glow(G, gkit.box(G, (xs, L.Y_BACK - d / 2, L.FLOOR + 0.15), (0.04, d - 0.4, 0.04)), "uv")
    setmat(gkit.box(bm, (ec, L.Y_BACK - d / 2, ez + 0.1), (L.EX1 - L.EX0 + 0.8, d, 0.2)), 2)
    glow(G, gkit.box(G, (ec, L.Y_BACK - d - 0.1, (L.FLOOR + ez) / 2), (L.EX1 - L.EX0, 0.2, ez - L.FLOOR)), "black")
    glow(G, gkit.box(G, (ec, L.Y_BACK + 0.02, ez + 0.05), (L.EX1 - L.EX0, 0.04, 0.06)), "amber")
    return bm


HEAD_COLORS = ("amber", "blue", "white")
MOVE_GROUPS = ("Hall", "Bay", "Floor")


def tilt_axis(d):
    """The head's tilt axis at rest: k = normalize(h x Z), h = d's horizontal part (club_movers / the UE material)."""
    h = Vector((d.x, d.y, 0.0))
    h = h.normalized() if h.length > 1e-6 else Vector((0, -1, 0))
    return h.cross(Vector((0, 0, 1))).normalized()


def hanging_head(rig, top, d, lens_key, mv=None):
    """A moving head hung under a truss: clamp, yoke, a head aimed along d, its lens on the palette. Returns the lens
    centre. mv (v7) = {"bm": the mover mesh, "lays": its data layers, "lens_lays": LENS's, "vals": the fixture's five
    values}: the yoke (pan only) and head go to the mover mesh, the lens carries the data too; the clamp stays baked.
    The yoke's arms sit on the head's tilt axis."""
    hc = top - Vector((0, 0, 0.45))
    gkit.box(rig, top - Vector((0, 0, 0.1)), (0.36, 0.36, 0.18))
    k = tilt_axis(d)
    tgt = mv["bm"] if mv else rig
    before = set(tgt.faces) if mv else None
    for s in (-1, 1):
        gkit.box(tgt, top - Vector((0, 0, 0.32)) + k * (s * 0.21), (0.05, 0.12, 0.34), yaw=math.atan2(k.y, k.x))
    if mv:
        club_movers.stamp_new(tgt, before, mv["lays"], club_movers.yoke_values(mv["vals"]))
        before = set(tgt.faces)
    gkit.cyl(tgt, hc - d * 0.2, hc + d * 0.18, 0.16, segs=10, r2=0.18)
    if mv:
        club_movers.stamp_new(tgt, before, mv["lays"], mv["vals"])
    before = set(LENS.faces)
    glow(LENS, gkit.cyl(LENS, hc + d * 0.18, hc + d * 0.2, 0.15, segs=10), lens_key)
    if mv:
        club_movers.stamp_new(LENS, before, mv["lens_lays"], mv["vals"])
    return hc + d * 0.2


def sweep_len(lens, d, vals):
    """A moving beam's length: the shortest distance to a solid over the engine's whole sweep (+0.3 m), so no pose
    pushes it through a wall, the floor or the mezzanine; at least 2 m."""
    (px, py), (pz, _ph), (pa, ta), (yaw, _u), _fix = vals
    best = 1e9
    for P, Q in club_movers.SWEEP:
        o, dd = club_movers.posed_ray(lens, d, Vector((px, py, pz)), yaw, P, Q, pa, ta)
        best = min(best, beam_len(o, dd, maxlen=40.0, step=0.1))
    return max(2.0, best + 0.3)


def build_rig():
    """SM_ClubRig (steel): trusses, hangers, moving heads, laser units. Plus the frozen translucent meshes: beams
    (SM_ClubBeams), lens and laser-spot halos (SM_ClubHalos), laser lines (SM_ClubLasers) on T_ClubBeam / T_ClubHalo."""
    rig = bmesh.new()
    beams = {k: bmesh.new() for k in ("Hall", "Bay", "Floor")}
    halos = {k: bmesh.new() for k in ("Hall", "Bay", "Floor")}
    lasers = {}                                                               # v5: club_lasers (the laser engine)
    for b in (*beams.values(), *halos.values(), *lasers.values()):
        gkit.uv_layer(b)
    movers = bmesh.new()                                                      # v7: yokes + heads (SM_ClubMoverHeads)
    mover_lays = club_movers.add_layers(movers)
    lens_lays = club_movers.add_layers(LENS)
    beam_lays = {k: club_movers.add_layers(b) for k, b in beams.items()}
    halo_lays = {k: club_movers.add_layers(b) for k, b in halos.items()}
    moves = []                                                                # (group, five values) per fixture
    for i, ty in enumerate(L.TRUSS_Y):
        gkit.truss(rig, (-L.HX + 0.6, ty, L.TRUSS_Z), (L.HX - 0.6, ty, L.TRUSS_Z), size=0.5, step=1.0)
        pix = (PIXB, PIXA)[i % 2]
        glow(pix, gkit.box(pix, (0, ty, L.TRUSS_Z - 0.28), (2 * L.HX - 1.4, 0.06, 0.05)), ("blue", "amber")[i % 2])
        for x in (-L.HX + 1.5, L.HX - 1.5):
            gkit.cyl(rig, (x, ty, L.TRUSS_Z + 0.25), (x, ty, L.CEIL), 0.02, segs=4)
    for (a, b), key in ((L.FRONT_TRUSS, "blue"), (L.BAY_TRUSS, "amber")):
        gkit.truss(rig, a, b, size=0.5, step=1.0)
        pix = PIXB if key == "blue" else PIXA
        glow(pix, gkit.box(pix, ((a[0] + b[0]) / 2, a[1], a[2] - 0.28), (b[0] - a[0] - 0.2, 0.06, 0.05)), key)
    heads = []                                                                # (top, target, color, group)
    for i, ty in enumerate(L.TRUSS_Y):
        for k, hx in enumerate((-10.0, -6.0, -2.0, 2.0, 6.0, 10.0)):
            heads.append(((hx, ty, L.TRUSS_Z - 0.25), (hx * 1.35 + rng.uniform(-1, 1), ty + (3 if k % 2 else -3), L.FLOOR),
                          HEAD_COLORS[(i + k) % 3], "Hall"))
    for k in range(8):
        hx = L.BAY_TRUSS[0][0] + 0.6 + k * 2.4
        heads.append(((hx, L.BAY_TRUSS[0][1], L.BAY_TRUSS[0][2] - 0.25), (hx * 1.5, -20 - 4 * (k % 3), L.FLOOR + 1.5),
                      ("blue", "amber")[k % 2], "Bay"))
    n_beams = 0
    for i, (top, tgt, col, grp) in enumerate(heads):
        top, tgt = Vector(top), Vector(tgt)
        hb = bmesh.new()
        hc = top - Vector((0, 0, 0.45))
        d = (tgt - hc).normalized()
        if grp == "Hall":                                                     # u across the truss row, x across the hall
            u = top.x / 10.0
        else:
            k_ = sum(1 for h in heads[:i] if h[3] == grp)
            u = (k_ - 3.5) / 3.5
        vals = club_movers.move_values(len(moves), hc, d, grp, max(-1.0, min(1.0, u)), (top.x + L.HX) / (2 * L.HX))
        moves.append((grp, vals))
        lens = hanging_head(hb, top, d, col, mv={"bm": movers, "lays": mover_lays, "lens_lays": lens_lays, "vals": vals})
        merge(rig, hb)
        Lb = sweep_len(lens, d, vals)
        before = set(beams[grp].faces)
        gkit.beam_planes(beams[grp], lens, d, Lb, 0.22, 0.22 + 0.07 * Lb, color=col, planes=2)
        club_movers.stamp_new(beams[grp], before, beam_lays[grp], vals)
        before = set(halos[grp].faces)
        gkit.halo(halos[grp], lens, 0.9, color=col, planes=3)
        club_movers.stamp_new(halos[grp], before, halo_lays[grp], vals)
        n_beams += 1
    for hx in (-7.5, -5.5, -3.5, 3.5, 5.5, 7.5):                              # floor heads on the deck, up and out
        base = Vector((hx, 4.4, 0.0))
        tgt = Vector((hx * 1.2, -14, L.CEIL))
        hb = bmesh.new()
        gkit.box(hb, base + Vector((0, 0, 0.08)), (0.42, 0.42, 0.16))         # the base: static, baked
        hc = base + Vector((0, 0, 0.42))
        d = (tgt - hc).normalized()
        merge(rig, hb)
        vals = club_movers.move_values(len(moves), hc, d, "Floor", hx / 7.5, (hx + L.HX) / (2 * L.HX))
        moves.append(("Floor", vals))
        k = tilt_axis(d)                                                      # the yoke (v7, as the Dino's moving_head):
        before = set(movers.faces)                                            # two arms on the tilt axis, pan only
        for s_ in (-1, 1):
            gkit.box(movers, base + Vector((0, 0, 0.36)) + k * (s_ * 0.22), (0.06, 0.12, 0.42), yaw=math.atan2(k.y, k.x))
        club_movers.stamp_new(movers, before, mover_lays, club_movers.yoke_values(vals))
        before = set(movers.faces)
        gkit.cyl(movers, hc - d * 0.2, hc + d * 0.18, 0.16, segs=10, r2=0.18)   # the head (v7: it moves)
        club_movers.stamp_new(movers, before, mover_lays, vals)
        col = "white" if abs(hx) > 6 else "blue"
        before = set(LENS.faces)
        glow(LENS, gkit.cyl(LENS, hc + d * 0.18, hc + d * 0.2, 0.15, segs=10), col)
        club_movers.stamp_new(LENS, before, lens_lays, vals)
        Lb = sweep_len(hc + d * 0.2, d, vals)
        before = set(beams["Floor"].faces)
        gkit.beam_planes(beams["Floor"], hc + d * 0.2, d, Lb, 0.22, 0.22 + 0.07 * Lb, color=col, planes=2)
        club_movers.stamp_new(beams["Floor"], before, beam_lays["Floor"], vals)
        before = set(halos["Floor"].faces)
        gkit.halo(halos["Floor"], hc + d * 0.2, 0.9, color=col, planes=3)
        club_movers.stamp_new(halos["Floor"], before, halo_lays["Floor"], vals)
        n_beams += 1
    club_lasers.housings(gkit, rig)                                           # v5: the laser engine's units
    bs, _dropped = club_lasers.beams()
    n_lasers = len(bs)
    log(f"rig: {len(heads) + 6} heads ({n_beams} beams); {len(club_lasers.units())} laser units, {n_lasers} sweeping beams")
    with open(os.path.join(OUT, "club_moves.json"), "w") as jf:                 # v7: the checks read the fixtures' data
        json.dump([[g_, list(map(list, v_))] for g_, v_ in moves], jf)
    log(f"movers: {len(moves)} fixtures ({', '.join(f'{g_} {sum(1 for m_ in moves if m_[0] == g_)}' for g_ in MOVE_GROUPS)})")
    return rig, beams, halos, lasers, movers


# ---------------------------------------------------------------- the decorative crowd (plan 4.9)
CROWD_LIGHT_EXPOSURE, CROWD_LIGHT_GAIN = 10.0, 1.0     # the light-only bake (x NIGHT) and the material's gain on it
CROWD_PREVIEW_LEVEL = 0.65                              # the preview shows a typical show level (game: 0.3 .. 1, wash)
CROWD_RIM = (0.10, 0.35, 1.0)                           # the preview's rim (in the game the show colours it)


def build_crowd():
    """SM_ClubCrowd + SM_ClubPhones: the club's copy of crowd v3 (club_crowd.py) at club_spots.club_points, everyone at the
    near tier (people walk among them now); its VAT goes to T_ClubCrowdVAT.exr / .json (6 UV channels: + the pivot)."""
    pts = club_points(random.Random(11))
    crowd, phones, _ = club_crowd.build_crowd2(random.Random(11), points=pts, out_dir=OUT, vat_name="T_ClubCrowdVAT",
                                               tiers=(("near", 1e9),), half_fn=lambda y: 7.6)
    for ob, name in ((crowd, "SM_ClubCrowd"), (phones, "SM_ClubPhones")):
        ob.name = name
        ob.data.name = name
    log(f"crowd: {len(pts)} spots")
    return crowd, phones


def mat_crowd_preview(light_png):
    """What the Quest will show of a dancer: the vertex colour (Col, crisp clothes) x the baked light (UV0) x the gain,
    plus a rim (LayerWeight facing^3) standing in for the show's coloured rim light."""
    m = bpy.data.materials.new("PCrowd")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = "Col"
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = load_png(light_png)
    mul = nt.nodes.new("ShaderNodeMixRGB")
    mul.blend_type = "MULTIPLY"
    mul.inputs["Fac"].default_value = 1.0
    nt.links.new(at.outputs["Color"], mul.inputs["Color1"])
    nt.links.new(tx.outputs["Color"], mul.inputs["Color2"])
    gain = nt.nodes.new("ShaderNodeMixRGB")
    gain.blend_type = "MULTIPLY"
    gain.inputs["Fac"].default_value = 1.0
    gain.inputs["Color2"].default_value = (CROWD_LIGHT_GAIN * CROWD_PREVIEW_LEVEL,) * 3 + (1,)
    nt.links.new(mul.outputs["Color"], gain.inputs["Color1"])
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.4
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 3.0
    nt.links.new(lw.outputs["Facing"], pw.inputs[0])
    rim = nt.nodes.new("ShaderNodeMixRGB")
    rim.blend_type = "MULTIPLY"
    rim.inputs["Fac"].default_value = 1.0
    rim.inputs["Color2"].default_value = (*(0.6 * c for c in CROWD_RIM), 1)
    nt.links.new(pw.outputs["Value"], rim.inputs["Color1"])
    add = nt.nodes.new("ShaderNodeMixRGB")
    add.blend_type = "ADD"
    add.inputs["Fac"].default_value = 1.0
    nt.links.new(gain.outputs["Color"], add.inputs["Color1"])
    nt.links.new(rim.outputs["Color"], add.inputs["Color2"])
    nt.links.new(add.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], outn.inputs["Surface"])
    return m


def mat_crowd():
    """Copied from dino_stage.py: per-part colours from the "Col" attribute, darker at night (x0.5)."""
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
    """Copied from dino_stage.py: emission coloured by the mesh's colour attribute (the crowd's glowing bits)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = layer
    nt.links.new(at.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], outn.inputs["Surface"])
    return m


# ---------------------------------------------------------------- bake materials (Principled; baked as DIFFUSE)
def mat_flat(name, rgb, rough=0.8):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def mat_noise(name, c0, c1, scale, rough=0.85):
    """Concrete and steel with a little variation (object-space noise between two albedos)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = 6.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c0, 1)
    ramp.color_ramp.elements[1].color = (*c1, 1)
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    return m


def mat_hazard(name):
    """Hazard stripes: diagonal amber/black bands (object space), baked like any albedo."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    w = nt.nodes.new("ShaderNodeTexWave")
    w.wave_type, w.bands_direction, w.wave_profile = "BANDS", "DIAGONAL", "SAW"
    w.inputs["Scale"].default_value = 1.6
    w.inputs["Distortion"].default_value = 0.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.55, 0.30, 0.03, 1)
    cr.elements[1].position, cr.elements[1].color = 0.5, (0.012, 0.012, 0.012, 1)
    nt.links.new(tc.outputs["Object"], w.inputs["Vector"])
    nt.links.new(w.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.6
    return m


def mat_emit(name, rgb=None, strength=1.0, image=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    if image is not None:
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = image
        tx.interpolation = "Closest"
        nt.links.new(tx.outputs["Color"], em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = (*rgb, 1)
    nt.links.new(em.outputs["Emission"], outn.inputs["Surface"])
    return m


def mat_visuals(name, strength):
    """Stand-in for a VJ loop on the screens (bakes their light onto the stage; shows in the previews)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    w = nt.nodes.new("ShaderNodeTexWave")
    w.inputs["Scale"].default_value = 0.11
    w.inputs["Distortion"].default_value = 5.0
    w.inputs["Detail"].default_value = 3.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    dark = (0.0, 0.006, 0.02, 1)
    cr.elements[0].position, cr.elements[0].color = 0.0, dark
    cr.elements[1].position, cr.elements[1].color = 0.44, (0.10, 0.45, 1.0, 1)
    for pos, col in ((0.50, dark), (0.70, (1.0, 0.55, 0.05, 1)), (0.735, dark), (0.90, (0.75, 0.85, 1.0, 1)), (0.93, dark)):
        e = cr.elements.new(pos)
        e.color = col
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    nt.links.new(tc.outputs["Object"], w.inputs["Vector"])
    nt.links.new(w.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], outn.inputs["Surface"])
    return m


def mat_alpha(name, image):
    """Preview of Tribe's alpha-blended unlit instance: texture rgb over the background by texture alpha."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
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
    nt.links.new(mix.outputs["Shader"], outn.inputs["Surface"])
    return m


def load_png(path):
    img = bpy.data.images.load(path, check_existing=False)
    img.colorspace_settings.name = "sRGB"
    return img


# ---------------------------------------------------------------- bake lights: the room between hits + its practicals
BLUE, AMBER, RED = (0.10, 0.45, 1.0), (1.0, 0.55, 0.05), (1.0, 0.06, 0.03)


def add_light(name, kind, pos, target, color, power, size=0.5, spot_deg=45):
    ld = bpy.data.lights.new(name, kind)
    ld.color, ld.energy = color, power
    if kind == "SPOT":
        ld.spot_size, ld.spot_blend, ld.shadow_soft_size = math.radians(spot_deg), 0.6, size
    else:
        ld.shadow_soft_size = size
    ob = bpy.data.objects.new(name, ld)
    ob.location = pos
    if target is not None:
        ob.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(ob)


def club_lights():
    w = bpy.data.worlds.new("Club")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.004, 0.005, 0.009, 1)
    scene.world = w
    add_light("Core", "POINT", (0, 7.0, 7.5), None, (0.25, 0.55, 1.0), 9000, size=2.0)           # Cherenkov spill
    add_light("CoreLow", "POINT", (0, 6.3, 2.0), None, (0.25, 0.55, 1.0), 2500, size=1.0)
    for sx in (-1, 1):
        add_light(f"StageKey{sx}", "SPOT", (sx * 5, -1.5, 8.3), (sx * 2, 2, 0), (0.75, 0.85, 1.0), 1400, 0.5, 45)
        add_light(f"Mezz{sx}a", "SPOT", (sx * 10, -20, 8.2), (sx * 10, -20, L.MZ_Z), BLUE, 900, 0.5, 55)
        add_light(f"Mezz{sx}b", "SPOT", (sx * 10, -12, 8.2), (sx * 10, -12, L.MZ_Z), BLUE, 900, 0.5, 55)
        for y in (-21.0, -15.0, -9.8):
            add_light(f"Lounge{sx}{int(-y)}", "POINT", (sx * 10.3, y, L.FLOOR + 0.9), None, AMBER, 40, size=0.2)
    for i, ty in enumerate(L.TRUSS_Y):                                         # colored pools on the dance floor
        for sx in (-1, 1):
            add_light(f"Pool{i}{sx}", "SPOT", (sx * 4, ty, L.TRUSS_Z - 0.6), (sx * 3.5, ty - 1.5, L.FLOOR),
                      BLUE if (i + (sx > 0)) % 2 else AMBER, 1600, 0.4, 40)
    add_light("Bar", "POINT", (-2, L.Y_BACK + 1.6, 1.6), None, AMBER, 500, size=0.6)
    add_light("BarFront", "POINT", (-2, L.BAR_Y - 1.4, 1.2), None, (0.4, 0.6, 1.0), 220, size=0.6)
    add_light("Beacon", "POINT", (L.DOOR_MID, L.AIR_Y0 - 0.7, L.LINTEL_TOP + 0.3), None, RED, 260, size=0.3)
    add_light("Corridor", "POINT", ((L.EX0 + L.EX1) / 2, L.Y_BACK - 2.5, L.FLOOR + 2.2), None, (0.3, 0.3, 1.0), 120, size=0.4)


# ---------------------------------------------------------------- unwrap + bake + export, copied from dino_stage.py
def unwrap(ob, margin=0.003):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=margin, area_weight=0.0, correct_aspect=True)
    bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")


def blur(img, passes=3, r=3):
    for _ in range(passes):
        for ax in (0, 1):
            c = np.cumsum(np.pad(img, [(r + 1, r) if a == ax else (0, 0) for a in range(3)], mode="edge"), axis=ax)
            img = (np.take(c, range(2 * r + 1, c.shape[ax]), axis=ax) - np.take(c, range(0, c.shape[ax] - 2 * r - 1), axis=ax)) / (2 * r + 1)
    return img


def bake(ob, name, size, exposure, samples=96, margin=8, smooth=0, passes=("DIRECT", "INDIRECT", "COLOR")):
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
    bpy.ops.object.bake(type="DIFFUSE", pass_filter=set(passes), margin=margin, use_clear=True)
    px = np.empty(size * size * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    lin = px.reshape(size, size, 4)[::-1, :, :3]
    if smooth:
        lin = blur(lin, r=smooth)
    path = os.path.join(OUT, name + ".png")
    write_png(path, tonemap(lin, exposure))
    log(f"baked {ob.name} -> {name}.png (mean linear {lin.mean():.4f})")
    return path


def export_fbx(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, ob.name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"}, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",
                             mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False)
    log(f"fbx {os.path.basename(path)}: {len(ob.data.polygons)} faces, "
        f"{sum(len(p.vertices) - 2 for p in ob.data.polygons)} tris")


def render_preview(name, cam_pos, target, lens=18):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_end = 500
    cam = bpy.data.objects.new(name, cd)
    cam.location = cam_pos
    cam.rotation_euler = (Vector(target) - Vector(cam_pos)).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(cam)
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.cycles.samples = 16 if FAST else 32
    scene.render.filepath = os.path.join(OUT, f"preview_{name}.png")
    bpy.ops.render.render(write_still=True)
    log("preview " + scene.render.filepath)


# ---------------------------------------------------------------- main
MAT = {
    "floor": mat_noise("Floor", (0.025, 0.025, 0.028), (0.045, 0.045, 0.05), 0.6, 0.6),
    "concrete": mat_noise("Concrete", (0.05, 0.05, 0.055), (0.09, 0.09, 0.095), 0.8),
    "concrete_dark": mat_noise("ConcreteDark", (0.025, 0.025, 0.028), (0.045, 0.045, 0.05), 0.8),
    "steel": mat_noise("Steel", (0.035, 0.038, 0.042), (0.07, 0.072, 0.078), 3.0, 0.5),
    "deck": mat_flat("Deck", (0.03, 0.03, 0.034), 0.5),
    "hazard": mat_hazard("Hazard"),
    "glass": mat_flat("Glass", (0.015, 0.025, 0.04), 0.1),
    "panel": mat_flat("Panel", (0.02, 0.022, 0.026), 0.4),
    "grate": mat_noise("Grate", (0.03, 0.032, 0.035), (0.06, 0.062, 0.066), 9.0, 0.6),
    "sofa": mat_flat("Sofa", (0.09, 0.02, 0.015), 0.7),
    "wood": mat_flat("Wood", (0.07, 0.04, 0.025), 0.6),
}
LIT = {   # object -> (builder result, material keys in index order, bake size, exposure, samples, smooth)
    "SM_ClubFloor": (build_floor(), ("floor", "hazard"), 2048, 2.8, 128, 3),
    "SM_ClubHall": (build_hall(), ("concrete", "concrete_dark", "steel"), 4096, 2.6, 96, 1),
    "SM_ClubStage": (build_stage(), ("deck", "steel", "hazard", "glass", "panel"), 2048, 2.2, 96, 0),
    "SM_ClubCore": (build_core(), ("steel", "concrete_dark", "hazard"), 2048, 1.8, 96, 0),
    "SM_ClubMezz": (build_mezz(), ("steel", "grate", "sofa", "wood"), 2048, 2.4, 96, 0),
    "SM_ClubBar": (build_bar(), ("steel", "wood", "concrete_dark"), 1024, 2.2, 96, 0),
}
rig_bm, beams_bms, halos_bms, lasers_bms, movers_bm = build_rig()
LIT["SM_ClubRig"] = (rig_bm, ("steel",), 2048, 1.8, 64, 0)
vscreen, sscreens = build_screens()
objs = {}
for name, (bm_, keys, *_rest) in LIT.items():
    objs[name] = new_obj(name, bm_, [MAT[k] for k in keys])
glow_ob = new_obj("SM_ClubGlow", G)                                      # static practicals (always on)
lens_ob, core_ob = new_obj("SM_ClubLenses", LENS), new_obj("SM_ClubCoreGlow", COREG)
pixb_ob, pixa_ob = new_obj("SM_ClubPixelBlue", PIXB), new_obj("SM_ClubPixelAmber", PIXA)
anim_glow = (lens_ob, core_ob, pixb_ob, pixa_ob)
R = club_show.CUE_ROWS
ROWS = {}                                                                # translucent mesh -> its cue row (build_club)
trans = []
for kind, groups, bms in (("Beams", (("Hall", "heads"), ("Bay", "bayheads"), ("Floor", "floorheads")), beams_bms),
                          ("Halos", (("Hall", "heads"), ("Bay", "bayheads"), ("Floor", "floorheads")), halos_bms)):
    for grp, row in groups:
        trans.append(new_obj(f"SM_Club{kind}{grp}", bms[grp]))
        ROWS[trans[-1].name] = R[row]
crowd_ob, phones_ob = build_crowd()
laser_ob = new_obj("SM_ClubLaserShow", club_lasers.build_mesh(gkit))     # v5: moved by the laser engine in the game
mover_ob = new_obj("SM_ClubMoverHeads", movers_bm)                         # v7: the moving heads' yokes and heads
log(club_lasers.report()[1])
for ob in (*objs.values(), glow_ob, *anim_glow, vscreen, sscreens, *trans, crowd_ob, phones_ob, laser_ob, mover_ob):
    log(f"{ob.name}: {len(ob.data.polygons)} faces, {sum(len(p.vertices) - 2 for p in ob.data.polygons)} tris")

gkit.write_png(os.path.join(OUT, "T_ClubGlowPal.png"), gkit.tex_palette())
gkit.write_png(os.path.join(OUT, "T_ClubBeam.png"), gkit.tex_beam())
gkit.write_png(os.path.join(OUT, "T_ClubHalo.png"), gkit.tex_halo())
club_show.write_cues(OUT)                                                             # T_ClubCues (comfort-checked)
_lprog, _llib = club_laser_scenes.club_textures(dino_show)       # the Dino's laser program + library, its scene masks
dino_show.write_png_linear(os.path.join(OUT, "T_ClubLaserProg.png"), _lprog)   # on the club's rigs (v6: no dark
dino_show.write_png_linear(os.path.join(OUT, "T_ClubLaserLib.png"), _llib)     # bars for the club)
with open(os.path.join(OUT, "club_rows.json"), "w") as jf:                             # build_club: translucent mesh -> row
    json.dump({"rows": ROWS, "cue_rows": R, "crowd_light_gain": CROWD_LIGHT_GAIN}, jf, indent=1)
pal = load_png(os.path.join(OUT, "T_ClubGlowPal.png"))
glow_ob.data.materials.append(mat_emit("GlowEmit", image=pal, strength=4.0))       # the practicals light the room
for ob in (lens_ob, core_ob):
    ob.data.materials.append(mat_emit("E" + ob.name, image=pal, strength=4.0))
pixb_ob.data.materials.append(mat_emit("EPixBlue", (0.15, 0.30, 1.0), 4.0))
pixa_ob.data.materials.append(mat_emit("EPixAmber", (1.0, 0.60, 0.12), 4.0))
vscreen.data.materials.append(mat_visuals("ScreenEmit", 1.6))                         # the visuals' glow on the stage
sscreens.data.materials.append(mat_visuals("SideEmit", 1.2))
crowd_ob.data.materials.clear()
crowd_ob.data.materials.append(mat_crowd())
phones_ob.data.materials.clear()
phones_ob.data.materials.append(mat_emit_col("PhoneEmit", 4.0))
laser_ob.hide_render = True                                                           # out of the bakes
mover_ob.hide_render = True                                                           # (v7: they move in the game)
mover_ob.data.materials.append(mat_emit("EMoverHeads", (0.035, 0.036, 0.04), 1.0))   # dark metal, as in the game
laser_ob.data.materials.append(mat_alpha("ASM_ClubLaserShow", load_png(os.path.join(OUT, "T_ClubBeam.png"))))
for ob in trans:
    ob.hide_render = True                                                             # out of the bakes
    tex = "T_ClubHalo" if ob.name.startswith("SM_ClubHalos") else "T_ClubBeam"
    ob.data.materials.append(mat_alpha("A" + ob.name, load_png(os.path.join(OUT, tex + ".png"))))
club_lights()

baked = {}
for name, (_bm, keys, size, exposure, samples, smooth) in LIT.items():
    unwrap(objs[name], 0.002 if size >= 2048 else 0.004)
    baked[name] = bake(objs[name], "T" + name[2:], size, exposure, samples=samples, smooth=smooth)
baked_crowd = bake(crowd_ob, "T_ClubCrowdLight", 1024, exposure=CROWD_LIGHT_EXPOSURE, samples=128, margin=2, smooth=2,
                   passes=("DIRECT", "INDIRECT"))   # light only: the clothes come from Col (crisp), not the atlas

# what the Quest will show: every surface unlit (its texture or palette as-is), the screens black until Tribe's video
for lt in [o for o in coll.objects if o.type == "LIGHT"]:
    bpy.data.objects.remove(lt)
for name, path in baked.items():
    objs[name].data.materials.clear()
    objs[name].data.materials.append(mat_emit("P" + name, image=load_png(path)))
crowd_ob.data.materials.clear()
crowd_ob.data.materials.append(mat_crowd_preview(baked_crowd))
for ob in (glow_ob, *anim_glow, phones_ob):
    ob.data.materials[0].node_tree.nodes["Emission"].inputs["Strength"].default_value = 1.0
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
for ob in (*trans, laser_ob, mover_ob):
    ob.hide_render = False
exported = (*objs.values(), glow_ob, *anim_glow, vscreen, sscreens, *trans, crowd_ob, phones_ob, laser_ob, mover_ob)
for ob in exported:
    export_fbx(ob)
with open(os.path.join(OUT, "manifest.txt"), "w") as mf:                               # build_club.py imports exactly these
    mf.write("\n".join(ob.name for ob in exported) + "\n")

# previews: the screens show a stand-in loop (in the game they show your media-folder visuals)
render_preview("stream", (0, -9.5, 2.2), (0, 4, 5.2), lens=16)
render_preview("dj_view", L.DJ_EYE, (0, -24, 0.0), lens=16)
render_preview("crowd", (1.5, -20.5, 0.45), (0, 3, 4.0), lens=18)
render_preview("gate", (-8.8, -11.0, 0.55), (L.DOOR_MID, L.AIR_Y0, 0.9), lens=18)
render_preview("bar", (3.5, -26.2, 0.6), (0, 3, 3.6), lens=16)
render_preview("mezz", (-9.3, -9.5, L.MZ_Z + 1.65), (2, 2, 3.0), lens=16)
log("done")
