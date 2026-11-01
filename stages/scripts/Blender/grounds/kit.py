"""Shared kit for the festival-grounds modules of the Dino Stage (Blender 4.5, headless).

A grounds module is one file in this folder (vendors.py, infrastructure.py, landmarks.py, atmosphere.py) with:

    from kit import *            # this folder is on sys.path
    NAME = "vendors"             # short id; the lit mesh ships as SM_Grounds<Name>
    BAKE_SIZE = 2048             # baked-lighting texture size for this module's lit mesh (2048 or 4096)

    def build(rng) -> dict:      # rng: random.Random seeded by the caller (stay deterministic)
        return {
            "lit":    [(bm, "metal_dark"), ...],   # opaque surfaces, lighting BAKED (Cycles); key from LIT below
            "glow":   [bm, ...],                   # opaque unlit emitters: every face UV'd at pal_uv(key) (GLOW below)
            "beams":  [bm, ...],                   # translucent light beams: UVs from beam_planes() (T_DinoBeam)
            "halos":  [bm, ...],                   # translucent glow sprites: UVs from halo() (T_DinoHalo)
            "lights": [light(...), ...],           # Blender lights that bake onto everything (crowd, ground, props)
            "exclude": [(x0, y0, x1, y1), ...],    # crowd keep-out rectangles (FOH, tower bases, ...)
            "people": [(x, y, yaw, pose), ...],    # extra people for the crowd mesh: pose in down/up/one/hips
        }

Space (all modules): meters, Z up, the DJ at the origin facing -Y (the crowd); the stage stands behind the DJ (+Y).
Model on the crowd field floor z = GROUND_Z. The main script lowers everything by STAGE_DROP afterwards (do not).
Existing set (do not build over it):
  - stage deck x -25..25, y -4.5..13.5 (top z=0, i.e. 1.5 m above the field); crowd barrier at y=-7.5 (x -30..30);
    the spine arches/horns/skull rise to ~24 m between x=-20..20, y=0..12; truss towers + line arrays at x=+-17, y~2;
  - the crowd: rows from y=-8.6 back to about y=-63 (about -66 once keep-out rects push rows back), half-width
    crowd_half(y) = 14 + 0.5*(-y) (19 m each side at y=-10, 31 m at y=-34, 45 m at y=-62); 2,100 people, ~1.75 m tall;
  - baked ground plane x -80..80, y -130..30 (the main script may enlarge it); dark far ground to 600 m; star sky
    sphere radius 480 m.
Look: a night festival in the woods (Lost-Lands-like, dinosaur theme, our own designs). Light carries the look:
string lights, LED/neon signs, uplights, beams. Surfaces are dark and lit by your lights in the bake.
Runtime: Quest 3 (mobile). Every face costs; no per-object animation; everything static.
"""
import math
import random
import struct
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

GROUND_Z = -1.5


def crowd_half(y):
    """Half-width of the crowd at depth y (y<0). Crowd v2 (2026-10-05, "pack that venue out"): 20 + 0.55*(-y), was
    14 + 0.5*(-y)."""
    return 20 + 0.55 * (-y)


# ------------------------------------------------------------------ lit materials (baked): key -> (albedo linear, rough)
LIT = {
    "metal_dark": ((0.05, 0.05, 0.055), 0.5),      # truss, poles, scaffolding, speaker boxes
    "metal_grey": ((0.25, 0.25, 0.26), 0.45),
    "metal_alu": ((0.45, 0.45, 0.47), 0.35),
    "canvas_white": ((0.70, 0.68, 0.62), 0.9),     # tents, umbrellas (catch warm light well)
    "canvas_red": ((0.50, 0.05, 0.04), 0.9),
    "canvas_blue": ((0.04, 0.10, 0.45), 0.9),
    "canvas_green": ((0.05, 0.30, 0.08), 0.9),
    "canvas_yellow": ((0.65, 0.48, 0.05), 0.9),
    "canvas_black": ((0.02, 0.02, 0.022), 0.9),    # scrims, skirts
    "wood": ((0.25, 0.15, 0.08), 0.8),
    "wood_dark": ((0.10, 0.06, 0.035), 0.8),
    "truck_white": ((0.60, 0.60, 0.58), 0.4),
    "truck_red": ((0.45, 0.04, 0.03), 0.4),
    "truck_yellow": ((0.60, 0.45, 0.05), 0.4),
    "truck_teal": ((0.05, 0.35, 0.35), 0.4),
    "truck_black": ((0.03, 0.03, 0.035), 0.4),
    "plastic_blue": ((0.05, 0.15, 0.50), 0.5),     # portable toilets
    "plastic_white": ((0.65, 0.65, 0.62), 0.5),
    "plastic_orange": ((0.70, 0.22, 0.03), 0.5),
    "rubber": ((0.02, 0.02, 0.02), 0.8),
    "glass_dark": ((0.02, 0.025, 0.03), 0.1),
    "foliage": ((0.03, 0.08, 0.03), 0.9),          # trees (dark: uplight them for color)
    "foliage_pine": ((0.02, 0.05, 0.03), 0.9),
    "bark": ((0.06, 0.04, 0.025), 0.9),
    "grass": ((0.04, 0.07, 0.03), 0.95),
    "dirt": ((0.09, 0.07, 0.05), 0.95),
    "stone": ((0.18, 0.16, 0.14), 0.8),
    "dino_green": ((0.10, 0.18, 0.07), 0.7),       # statues
    "dino_grey": ((0.22, 0.21, 0.20), 0.7),
    "dino_brown": ((0.20, 0.12, 0.06), 0.7),
    "bone": ((0.55, 0.42, 0.22), 0.65),
}

# ------------------------------------------------------------------ glow palette (unlit, shown as-is): key -> color
GLOW = {
    "bulb_warm": (1.0, 0.72, 0.38), "bulb_white": (1.0, 1.0, 0.95), "white": (1.0, 1.0, 1.0),
    "red": (1.0, 0.08, 0.05), "orange": (1.0, 0.40, 0.05), "amber": (1.0, 0.60, 0.12), "yellow": (1.0, 0.85, 0.10),
    "lime": (0.60, 1.0, 0.10), "green": (0.15, 1.0, 0.25), "cyan": (0.10, 0.90, 1.0), "sky": (0.35, 0.65, 1.0),
    "blue": (0.15, 0.30, 1.0), "purple": (0.55, 0.15, 1.0), "uv": (0.40, 0.10, 1.0), "magenta": (1.0, 0.10, 0.75),
    "pink": (1.0, 0.40, 0.70),
    # dimmer emitters: lit windows, screens, signs' backing, lanterns at distance
    "warm_dim": (0.45, 0.30, 0.15), "white_dim": (0.40, 0.40, 0.42), "red_dim": (0.40, 0.03, 0.02),
    "blue_dim": (0.05, 0.10, 0.40), "green_dim": (0.04, 0.35, 0.08), "purple_dim": (0.20, 0.05, 0.40),
    "screen_blue": (0.10, 0.20, 0.50), "screen_teal": (0.05, 0.40, 0.40), "fire": (1.0, 0.45, 0.08),
    "ember": (0.60, 0.15, 0.02), "black": (0.0, 0.0, 0.0),
}
_GLOW_KEYS = list(GLOW)
PAL_COLS = 8
PAL_ROWS = (len(_GLOW_KEYS) + PAL_COLS - 1) // PAL_COLS


def pal_uv(key):
    """UV of the palette cell for a GLOW key (T_DinoGroundsPal)."""
    i = _GLOW_KEYS.index(key)
    return ((i % PAL_COLS + 0.5) / PAL_COLS, 1.0 - (i // PAL_COLS + 0.5) / PAL_ROWS)


def tex_palette(cell=8):
    """Linear RGB, top-down rows: one flat cell per GLOW key."""
    img = np.zeros((PAL_ROWS * cell, PAL_COLS * cell, 3))
    for i, k in enumerate(_GLOW_KEYS):
        r, c = divmod(i, PAL_COLS)
        img[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] = GLOW[k]
    return img


def uv_layer(bm):
    return bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")


def set_uv(bm, faces, uv):
    """Every loop of these faces -> one UV (palette color)."""
    lay = uv_layer(bm)
    for f in faces:
        for lp in f.loops:
            lp[lay].uv = uv


def glow_faces(bm, faces, key):
    set_uv(bm, faces, pal_uv(key))


# ------------------------------------------------------------------ geometry helpers (all return the new faces)
def _op_faces(res):
    """The faces a bmesh.ops.create_* call made, from its new verts. (Not an index range: create_cone with caps frees
    faces internally and later faces reuse those slots, so 'indices past the old count' mixes old and new faces.)"""
    return list({f for v in res["verts"] for f in v.link_faces})


def box(bm, center, size, yaw=0.0, pitch=0.0, roll=0.0):
    """Axis box of size (sx, sy, sz) centered at center, rotated by yaw (about Z), then pitch (X), roll (Y), radians."""
    m = (Matrix.Translation(center) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(pitch, 4, "X")
         @ Matrix.Rotation(roll, 4, "Y") @ Matrix.Diagonal(Vector(size).to_4d()))
    return _op_faces(bmesh.ops.create_cube(bm, size=1.0, matrix=m))


def _frame(a, b):
    a, b = Vector(a), Vector(b)
    d = b - a
    L = d.length
    z = d.normalized() if L > 1e-9 else Vector((0, 0, 1))
    return a, b, L, z.to_track_quat("Z", "Y").to_matrix().to_4x4()


def cyl(bm, a, b, r, segs=8, cap=True, r2=None):
    """Cylinder (or truncated cone if r2) from point a to point b."""
    a, b, L, rot = _frame(a, b)
    m = Matrix.Translation((a + b) / 2) @ rot
    return _op_faces(bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segs, radius1=r,
                                           radius2=r if r2 is None else r2, depth=L, matrix=m))


def cone(bm, base, tip, r, segs=8, cap=True):
    return cyl(bm, base, tip, r, segs=segs, cap=cap, r2=0.0)


def sphere(bm, c, r, segs=8, rings=5, scale=(1, 1, 1)):
    return _op_faces(bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r,
                                               matrix=Matrix.Translation(c) @ Matrix.Diagonal(Vector(scale).to_4d())))


def quad(bm, p0, p1, p2, p3, uvs=None):
    """One quad (counter-clockwise seen from its front). uvs: 4 (u, v) or None."""
    f = bm.faces.new([bm.verts.new(Vector(p)) for p in (p0, p1, p2, p3)])
    if uvs:
        lay = uv_layer(bm)
        for lp, uv in zip(f.loops, uvs):
            lp[lay].uv = uv
    return [f]


def truss(bm, a, b, size=0.4, step=1.0, r=0.025):
    """Box truss from a to b: four chords plus zig-zag lacing on every face."""
    a, b = Vector(a), Vector(b)
    d = b - a
    L, t = d.length, d.normalized()
    up = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
    s1 = t.cross(up).normalized() * size / 2
    s2 = t.cross(s1).normalized() * size / 2
    corners = [s1 + s2, s1 - s2, -s1 - s2, -s1 + s2]
    out = []
    for c in corners:
        out += cyl(bm, a + c, b + c, r * 1.4, segs=4, cap=False)
    n = max(1, int(L / step))
    for i in range(n):
        p0, p1 = a + d * (i / n), a + d * ((i + 1) / n)
        for k in range(4):
            c0, c1 = corners[k], corners[(k + 1) % 4]
            out += cyl(bm, p0 + c0, p1 + c1, r, segs=3, cap=False)
    return out


def catenary(a, b, sag, n=12):
    """Points of a hanging cable from a to b sagging `sag` meters at mid-span."""
    a, b = Vector(a), Vector(b)
    return [a.lerp(b, i / n) - Vector((0, 0, sag * 4 * (i / n) * (1 - i / n))) for i in range(n + 1)]


def string_lights(bm_wire, bm_bulbs, a, b, sag, spacing=0.6, bulb_r=0.06, key="bulb_warm", wire_r=0.008):
    """Festoon: a dark wire (lit mesh) and bulbs (glow mesh, palette key) hanging between a and b."""
    pts = catenary(a, b, sag, n=max(4, int((Vector(b) - Vector(a)).length / 1.5)))
    wire = []
    for p, q in zip(pts, pts[1:]):
        wire += cyl(bm_wire, p, q, wire_r, segs=3, cap=False)
    L = sum((q - p).length for p, q in zip(pts, pts[1:]))
    nb = max(1, int(L / spacing))
    bulbs = []
    for i in range(1, nb):
        t = i / nb
        f = t * (len(pts) - 1)
        k = min(int(f), len(pts) - 2)
        p = pts[k].lerp(pts[k + 1], f - k) - Vector((0, 0, bulb_r * 1.2))
        bulbs += sphere(bm_bulbs, p, bulb_r, segs=4, rings=3)
    glow_faces(bm_bulbs, bulbs, key)
    return wire, bulbs


# 5x7 LED font (rows top->bottom, '#' = lit)
_FONT = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["####.", "....#", "....#", ".###.", "....#", "....#", "####."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": [".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."],
    " ": ["....."] * 7,
    "-": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
    "!": ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
    "&": [".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"],
    "$": ["..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#.."],
    "'": ["..#..", "..#..", ".....", ".....", ".....", ".....", "....."],
    ".": [".....", ".....", ".....", ".....", ".....", ".....", "..#.."],
    "*": [".....", "#.#.#", ".###.", "#####", ".###.", "#.#.#", "....."],
}


def led_text(bm, text, origin, right, up, pixel=0.12, gap=0.025, key="red"):
    """Dot-matrix sign: one small quad per lit pixel of a 5x7 font, glowing in palette `key`.
    origin = bottom-left corner of the first letter; right/up = unit vectors of the sign plane (front = right x up)."""
    origin, right, up = Vector(origin), Vector(right).normalized(), Vector(up).normalized()
    s = pixel - gap
    faces = []
    for ci, ch in enumerate(text.upper()):
        rows = _FONT.get(ch, _FONT[" "])
        for r, row in enumerate(rows):
            for c, px in enumerate(row):
                if px != "#":
                    continue
                o = origin + right * ((ci * 6 + c) * pixel) + up * ((6 - r) * pixel)
                faces += quad(bm, o, o + right * s, o + right * s + up * s, o + up * s)
    glow_faces(bm, faces, key)
    return faces


def text_width(text, pixel=0.12):
    return (len(text) * 6 - 1) * pixel


# ------------------------------------------------------------------ translucent parts (atmosphere)
BEAM_COLS = ["white", "cyan", "blue", "purple", "magenta", "amber", "green", "red"]   # T_DinoBeam / T_DinoHalo columns


def beam_planes(bm, apex, direction, length, w0, w1, color="white", planes=2, roll=0.0):
    """A light beam as `planes` crossed quads (a classic billboard-free beam): narrow (w0) at the apex, wide (w1) at the
    far end. UVs: u across the beam inside the color's column of T_DinoBeam, v from 0 (apex) to 1 (end)."""
    apex = Vector(apex)
    d = Vector(direction).normalized()
    up = Vector((0, 0, 1)) if abs(d.z) < 0.95 else Vector((1, 0, 0))
    s0 = d.cross(up).normalized()
    col = BEAM_COLS.index(color)
    u0, u1 = (col + 0.02) / len(BEAM_COLS), (col + 0.98) / len(BEAM_COLS)
    faces = []
    end = apex + d * length
    for k in range(planes):
        ang = roll + math.pi * k / planes
        s = (Matrix.Rotation(ang, 3, d) @ s0).normalized()
        faces += quad(bm, apex - s * w0 / 2, apex + s * w0 / 2, end + s * w1 / 2, end - s * w1 / 2,
                      uvs=[(u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)])
    return faces


DJ_EYE = Vector((0.0, 0.0, 2.6))   # the DJ's head, pre-drop


def halo(bm, center, size, color="white", planes=3):
    """A soft glow sprite: `planes` crossed squares mapped to the color's cell of T_DinoHalo. The first faces the DJ's
    head (a flat horizontal square read as a thin bright line from eye height), then the XZ and YZ planes."""
    c = Vector(center)
    col = BEAM_COLS.index(color)
    u0, u1 = col / len(BEAM_COLS), (col + 1) / len(BEAM_COLS)
    uvs = [(u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)]
    h = size / 2
    to_dj = DJ_EYE - c
    to_dj = to_dj.normalized() if to_dj.length > 1e-6 else Vector((0, -1, 0))
    r = Vector((0, 0, 1)).cross(to_dj)
    r = r.normalized() if r.length > 1e-6 else Vector((1, 0, 0))
    axes = [(r, to_dj.cross(r).normalized()), (Vector((1, 0, 0)), Vector((0, 0, 1))),
            (Vector((0, 1, 0)), Vector((0, 0, 1)))][:planes]
    faces = []
    for a, b in axes:
        faces += quad(bm, c - a * h - b * h, c + a * h - b * h, c + a * h + b * h, c - a * h + b * h, uvs=uvs)
    return faces


def tex_beam(w=1024, h=256):
    """RGBA linear, top-down: per color column, alpha = soft across-profile x fade along the beam (v=0 bright apex)."""
    img = np.zeros((h, w, 4))
    n = len(BEAM_COLS)
    cw = w // n
    x = (np.arange(cw) + 0.5) / cw
    across = np.exp(-((x - 0.5) / 0.22) ** 2) * 0.85 + np.exp(-((x - 0.5) / 0.06) ** 2) * 0.15
    v = 1.0 - (np.arange(h) + 0.5) / h                                 # top row = v 1 (far end)
    along = np.clip(1.0 - v, 0, 1) ** 1.6 * 0.9 + 0.1 * np.exp(-v * 12)
    a = np.outer(along, across) * 0.55
    for i, k in enumerate(BEAM_COLS):
        img[:, i * cw:(i + 1) * cw, :3] = GLOW[k]
        img[:, i * cw:(i + 1) * cw, 3] = a
    return img


def tex_halo(cell=128):
    n = len(BEAM_COLS)
    img = np.zeros((cell, cell * n, 4))
    y, x = np.mgrid[0:cell, 0:cell]
    r = np.hypot((x + 0.5) / cell - 0.5, (y + 0.5) / cell - 0.5) * 2
    a = np.clip(1 - r, 0, 1) ** 2.2 * 0.8
    for i, k in enumerate(BEAM_COLS):
        img[:, i * cell:(i + 1) * cell, :3] = GLOW[k]
        img[:, i * cell:(i + 1) * cell, 3] = a
    return img


# ------------------------------------------------------------------ lights + PNG
def light(name, kind, pos, color, power, target=None, size=0.5, spot_deg=45.0):
    """A light spec: kind SPOT/POINT/AREA; power in W (Blender units: a 1000 W point light ~ a bright stage lamp at 5 m).
    target: where a SPOT/AREA points."""
    return {"name": name, "kind": kind, "pos": tuple(pos), "target": tuple(target) if target else None,
            "color": tuple(color), "power": float(power), "size": float(size), "spot_deg": float(spot_deg)}


def add_light(spec, coll):
    ld = bpy.data.lights.new(spec["name"], spec["kind"])
    ld.color, ld.energy = spec["color"], spec["power"]
    if spec["kind"] == "SPOT":
        ld.spot_size = math.radians(spec["spot_deg"])
        ld.shadow_soft_size = spec["size"]
        ld.spot_blend = 0.5
    elif spec["kind"] == "AREA":
        ld.size = spec["size"]
    else:
        ld.shadow_soft_size = spec["size"]
    ob = bpy.data.objects.new(spec["name"], ld)
    ob.location = spec["pos"]
    if spec["target"] is not None:
        d = Vector(spec["target"]) - Vector(spec["pos"])
        ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(ob)
    return ob


def srgb(lin):
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


def write_png(path, img_lin_top_down):
    """HxWx3 (RGB) or HxWx4 (RGBA; alpha stays linear) floats, row 0 = top."""
    h, w, ch = img_lin_top_down.shape
    rgb = (srgb(img_lin_top_down[..., :3]) * 255.0 + 0.5).astype(np.uint8)
    if ch == 4:
        a = (np.clip(img_lin_top_down[..., 3:4], 0, 1) * 255.0 + 0.5).astype(np.uint8)
        px, ctype = np.concatenate([rgb, a], axis=2), 6
    else:
        px, ctype = rgb, 2
    raw = b"".join(b"\x00" + px[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    open(path, "wb").write(png)


def tris(bm):
    return sum(len(f.verts) - 2 for f in bm.faces)
