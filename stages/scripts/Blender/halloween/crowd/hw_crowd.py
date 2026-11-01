# GRAVEYARD SHIFT crowd ("hw_crowd"): the costumed Halloween crowd (Blender 4.5), a copy of the Dino Stage's Crowd V3
# (../../crowd2/crowd3.py, never edited from here) with a Halloween layer. Same contract as crowd3 / crowd2:
#
#   import hw_crowd
#   crowd, glow, extras = hw_crowd.build_crowd2(rng, exclude, extra)       # drop-in for crowd3.build_crowd2()
#
# * Procedural people (no third-party assets): crowd3's lofted bodies, body types, faces and hair. About 55 % wear a
#   costume, the rest are ravers in Halloween colours (black, orange, purple, toxic green, blood red, bone):
#   skeletons (black suit, white bone strips, skull face), witches (cone hat with brim, cape, tutu skirt, striped
#   tights), zombies (grey-green skin, torn and bloody clothes), pumpkin heads (a ribbed pumpkin with a glowing
#   jack-o-lantern face), ghosts (a sheet over the body with eye holes), devils (glowing red horns, cape, spade tail),
#   vampires (cape with a red lining, high collar, pale), mummies (bandage stripes), cats (light-up ears, tail) and a
#   few inflatable T-rexes (mid tier) as a nod to the Dino Stage. Friend groups often share a costume.
# * Glowing bits (their own mesh, emissive vertex colour) in orange, purple, green and red: glowsticks, glow
#   necklaces, LED gloves and shoes, LED horns and cat ears, light-up masks and eyes, jack-o-lantern faces and
#   buckets, witch-hat LED bands, phones, flow toys; totems: skulls and pumpkins with glowing faces, bat cut-outs,
#   flags, LED signs.
# * Three detail tiers by distance from the DJ (near < 12 m, mid < 18.5 m, far beyond), one rig, 17 dance clips
#   (crowd3's, with "lurch" (a zombie two-step) and "claw" (Thriller arms) in place of "shuffle" and "heart", so the
#   VAT keeps its 2048 x 1024 layout); every tier has one "superset" canonical mesh holding every optional part, so the
#   VAT stays one texture (columns = superset vertices; rows = (page * 17 + clip) * 29 + frame: the near tier fills
#   page 0, mid + far page 1, so every column index stays below 2048, exact in 16-bit UVs). The VAT stores offsets
#   from each clip's frame 0, and every person's base mesh is posed at frame 0 of their clip (and morphed to their body
#   type). Tempo: the DJ plays 140 BPM half-time dubstep, so ~65 % of the beat-locked dancers run at half time.
# * The field (crowd3's): dense at the barrier, thinner toward the back and the sides; friend groups, couples, people
#   on friends' shoulders, filmers, totems. Headbang / pump / jump up front, sway / nod / filming further back.
# * Per person (UV channels): VAT column, clip, yaw/scale, mirror, phase, playback rate. UV0 = per-person lighting cell
#   (bigger for nearer tiers); "Col" = albedo per part (patterns per vertex: mesh, fishnet, kandi, tie-dye, bandage
#   wraps, torn cloth, stripes).
# Space: meters, Z up, the DJ at the origin facing -Y; the crowd stands on z = GROUND_Z (the main script drops it later).
import json
import math
import os
import random
import struct
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
HW_DIR = os.path.dirname(HERE)                                  # Scripts/Blender/halloween
_GROUNDS = os.path.normpath(os.path.join(HW_DIR, "..", "grounds"))
if _GROUNDS not in [os.path.normpath(p) for p in sys.path]:     # kit.crowd_half (read only), as crowd3 uses it
    sys.path.append(_GROUNDS)
GROUND_Z = -1.5
FPS, FRAMES = 30, 28                       # one clip = 28 samples = 2 beats (any tempo: LoopRate = BPM / 120)
ROWS = FRAMES + 1                          # + a copy of frame 0: the material's frame lerp never wraps
CLIPS = ("jump", "jumppump", "pump", "handsup", "wave", "clap", "sway", "twostep", "lurch", "headbang", "nod",
         "claw", "hold", "talk", "carry", "ride", "flow")    # crowd3 clips with lurch and claw in the slots of shuffle
#                                                             and heart (pose() still knows those two: swap back here)
AUTHORED_BPM, BEATS_PER_CLIP = 128.0, 2
HW_BPM = 140.0                             # the Halloween set tempo: material LoopRate = HW_BPM / 120
UE_AXIS = (100.0, -100.0, 100.0)           # Blender m -> Unreal local cm (our FBX path mirrors Y; verified in the editor)
UE_FLIPS_V = True                          # Unreal's FBX importer stores 1 - V (verified in the fork editor 2026-10-05)
H = 1.75                                   # canonical body height (per person sz scales it)
VAT_LAYOUT = {"UV0 UVMap": "baked-lighting cell", "UV1 VatIndex": "x = VAT column, y = page * 17 + clip",
              "UV2 VatRotScale": "x = sx cos(yaw), y = sx sin(yaw)", "UV3 VatScalePhase": "x = mirror * sz, y = phase",
              "UV4 VatRate": "x = playback rate (1 = authored tempo)",
              "UV5 VatPivot": "x, y = the dancer's root (Blender m; v7: the crowd makes way round the player)"}
DATA_UVS = ("VatIndex", "VatRotScale", "VatScalePhase", "VatRate", "VatPivot")


def log(msg):
    print("[HWCROWD] " + msg, flush=True)


def V3(x, y, z):
    return Vector((x, y, z))


# ============================================================================ rig (canonical rest pose)
# facing +Y, the person's right on +X. Joint positions in meters.
J = {"pelvis": V3(0, 0, 0.95), "spine1": V3(0, -0.01, 1.05), "spine2": V3(0, -0.01, 1.24), "neck": V3(0, 0.0, 1.45),
     "head": V3(0, 0.01, 1.54), "waist": V3(0, 0, 1.0)}
for _s, _n in ((1, "R"), (-1, "L")):
    J[f"clav.{_n}"] = V3(_s * 0.035, 0.0, 1.42)
    J[f"shoulder.{_n}"] = V3(_s * 0.185, -0.005, 1.415)
    J[f"elbow.{_n}"] = V3(_s * 0.245, -0.015, 1.145)
    J[f"wrist.{_n}"] = V3(_s * 0.285, 0.02, 0.885)
    J[f"fingers.{_n}"] = V3(_s * 0.30, 0.035, 0.715)
    J[f"grip.{_n}"] = J[f"wrist.{_n}"].lerp(J[f"fingers.{_n}"], 0.45)
    J[f"hip.{_n}"] = V3(_s * 0.09, 0.0, 0.90)
    J[f"knee.{_n}"] = V3(_s * 0.10, 0.012, 0.485)
    J[f"ankle.{_n}"] = V3(_s * 0.10, -0.012, 0.085)
    J[f"toe.{_n}"] = V3(_s * 0.105, 0.16, 0.025)
BONES = [("pelvis", None), ("spine1", "pelvis"), ("spine2", "spine1"), ("neck", "spine2"), ("head", "neck")]
for _n in "RL":
    BONES += [(f"clav.{_n}", "spine2"), (f"upperarm.{_n}", f"clav.{_n}"), (f"forearm.{_n}", f"upperarm.{_n}"),
              (f"hand.{_n}", f"forearm.{_n}"), (f"thigh.{_n}", "pelvis"), (f"shin.{_n}", f"thigh.{_n}"),
              (f"foot.{_n}", f"shin.{_n}")]
BONES += [("prop.R", "hand.R"), ("prop.L", "hand.L"), ("hoop", "pelvis")]   # spinning flow toys
BONE_NAMES = [b for b, _ in BONES]
BONE_IDX = {b: i for i, b in enumerate(BONE_NAMES)}

# ============================================================================ regions + palettes
BODY_REGIONS = ("skin", "face", "eyes", "brow", "mouth", "jaw", "scalp", "hips", "belly", "midriff", "chest",
                "shoulders", "sleeve_top", "sleeve_mid", "forearm", "wrist", "hand", "thigh_top", "thigh", "knee",
                "shin", "ankle", "shoe", "sole")
ITEM_REGIONS = ("hair", "hat", "hat2", "crown", "goggles", "pumpkin", "pumpkin2", "sheet", "sheet_dark", "bone",
                "bone_dark", "collar", "collar2", "tail", "tail2", "trex", "trex2", "trex3", "pack", "strap", "cape", "cape2",
                "tutu", "warmer", "phone", "pole", "flag1", "flag2", "sign", "skull", "skull_dark", "ptotem", "ptotem2",
                "bucket", "bucket2", "cutout", "staff")
GLOW_LIST = ("glow_screen", "glow_flash", "glow_stick", "glow_led", "glow_necklace", "glow_glove", "glow_shoe",
             "glow_horn", "glow_fan", "glow_hoop", "glow_poi", "glow_staff", "glow_band", "glow_pface", "glow_mask",
             "glow_eye", "glow_bucket", "glow_skull", "glow_ptotem", "glow_hand", "glow_chest", "glow_head",
             "glow_face", "glow_lhand", "glow_ttop")
REGIONS = BODY_REGIONS + ITEM_REGIONS + GLOW_LIST
REG = {r: i for i, r in enumerate(REGIONS)}
GLOW_REGIONS = {REG[r] for r in GLOW_LIST}


def _c(r, g, b):
    return (r, g, b)


SKINS = [(0.85, 0.66, 0.53), (0.80, 0.58, 0.45), (0.72, 0.52, 0.38), (0.62, 0.42, 0.29), (0.50, 0.32, 0.21),
         (0.38, 0.23, 0.14), (0.27, 0.16, 0.10), (0.18, 0.11, 0.07), (0.88, 0.72, 0.62), (0.68, 0.50, 0.40)]
HAIR_NATURAL = [(0.012, 0.009, 0.007)] * 6 + [(0.04, 0.025, 0.014)] * 4 + [(0.12, 0.07, 0.03)] * 2 + [
    (0.45, 0.33, 0.15), (0.60, 0.48, 0.26), (0.35, 0.10, 0.03), (0.55, 0.53, 0.50)]
# Halloween palette (plan section 2): orange and purple carry the look, green and red are accents; no cyan, magenta or
# pink (the colours of the Dino Stage and the club).
HAIR_DYED = [(0.95, 0.35, 0.03), (0.45, 0.08, 0.80), (0.20, 0.75, 0.15), (0.80, 0.05, 0.06), (0.90, 0.90, 0.92),
             (0.08, 0.04, 0.16), (0.55, 0.85, 0.10), (0.60, 0.20, 0.85)]
NEON = [(1.0, 0.40, 0.03), (0.50, 0.08, 1.0), (0.20, 1.0, 0.20), (1.0, 0.08, 0.05), (0.60, 1.0, 0.05),
        (1.0, 0.62, 0.05), (0.70, 0.20, 1.0)]                    # orange, UV purple, toxic green, blood, lime, amber, violet
DARKS = [(0.012, 0.012, 0.014)] * 5 + [(0.035, 0.035, 0.04), (0.05, 0.012, 0.08), (0.012, 0.02, 0.06), (0.06, 0.012, 0.02)]
PASTELS = [(0.42, 0.30, 0.55), (0.70, 0.45, 0.22), (0.35, 0.45, 0.25), (0.45, 0.08, 0.10), (0.75, 0.72, 0.62),
           (0.55, 0.50, 0.65)]                                  # the crowd3 pastels, muted: dusk, rust, moss, burgundy, bone
LIGHTS = [(0.80, 0.78, 0.70), (0.70, 0.70, 0.72), (0.62, 0.58, 0.48)]
METALS = [(0.60, 0.60, 0.66), (0.80, 0.62, 0.20), (0.55, 0.35, 0.70)]
DENIMS = [(0.05, 0.08, 0.18), (0.10, 0.15, 0.30), (0.25, 0.35, 0.50)]
EARTH = [(0.28, 0.25, 0.16), (0.15, 0.17, 0.08), (0.25, 0.18, 0.10), (0.18, 0.18, 0.19)]
FLAGS = [(1.0, 0.40, 0.03), (0.45, 0.08, 0.85), (0.15, 0.80, 0.15), (0.05, 0.05, 0.06), (0.90, 0.88, 0.82),
         (0.80, 0.05, 0.05), (0.95, 0.65, 0.05), (0.30, 0.05, 0.45)]
GLOW_COLS = {"orange": (1.0, 0.40, 0.05), "purple": (0.45, 0.10, 1.0), "green": (0.15, 1.0, 0.25),
             "red": (1.0, 0.08, 0.05), "amber": (1.0, 0.62, 0.08), "violet": (0.70, 0.25, 1.0)}
GLOW_W = (0.30, 0.30, 0.20, 0.12, 0.04, 0.04)                  # orange and purple carry it
GLOWS = list(GLOW_COLS.values())
CANDLE = (1.0, 0.55, 0.08)                                     # jack-o-lantern faces
BONE = (0.80, 0.78, 0.70)
BLACK = (0.012, 0.012, 0.014)
BLOOD = (0.30, 0.02, 0.02)
BANDAGES = [(0.78, 0.74, 0.62), (0.70, 0.66, 0.54), (0.82, 0.80, 0.72)]
ZOMBIE_SKIN = [(0.42, 0.50, 0.36), (0.36, 0.45, 0.33), (0.50, 0.53, 0.42), (0.40, 0.44, 0.38)]
PUMPKINS = [(0.85, 0.32, 0.03), (0.95, 0.42, 0.05), (0.75, 0.27, 0.02), (0.90, 0.50, 0.10)]
SHEETS = [(0.86, 0.86, 0.84)] * 4 + [(0.80, 0.78, 0.72), (0.72, 0.72, 0.75), (0.76, 0.72, 0.86)]
WITCH_HATS = [BLACK] * 3 + [(0.12, 0.02, 0.20), (0.03, 0.12, 0.05)]
TREX_COLS = [(0.15, 0.6, 0.1), (0.6, 0.15, 0.6), (0.9, 0.5, 0.05)]


def hw_glow(rng):
    return rng.choices(GLOWS, weights=GLOW_W)[0]


def top_color(rng):
    k = rng.random()
    return rng.choice(DARKS if k < 0.40 else NEON if k < 0.72 else PASTELS if k < 0.88 else LIGHTS if k < 0.96 else METALS)


def mul(c, k):
    return tuple(max(0.0, min(1.0, v * k)) for v in c)


# ============================================================================ canonical geometry
class Geo:
    """Accumulates one canonical (superset) mesh: vertices with bone weights and a pattern tag (ring parity / position),
    faces tagged with a part and a region, per-corner UVs inside per-primitive islands (packed per tier later). Seams
    only where a tube / box / ellipsoid wraps around; caps and box ends reuse their ring's texels."""

    def __init__(self):
        self.v, self.w, self.pat, self.pj = [], [], [], []
        self.f, self.fpart, self.freg, self.fuv, self.fisl, self.isl = [], [], [], [], [], []
        self._rn = 0
        self.named = {}                    # name -> island: a costume part that REPLACES a part reuses its island
        self._bvh, self._bvh_key = None, None
        self.decals = set()                # glyphs and strips drawn on a surface (never projected onto themselves)

    def surface(self, parts, origin, direction, lift=0.004):
        """Where a ray from `origin` along `direction` first meets the faces of `parts` (glow faces and decals left
        out), moved `lift` back toward the origin: glyphs and strips sit just in front of the faceted surface they are
        drawn on. None on a miss."""
        from mathutils.bvhtree import BVHTree
        key = (tuple(parts), len(self.f), len(self.decals))
        if self._bvh_key != key:
            polys = [f for k, (f, pt, rg) in enumerate(zip(self.f, self.fpart, self.freg))
                     if pt in parts and rg not in GLOW_REGIONS and k not in self.decals]
            self._bvh = BVHTree.FromPolygons([tuple(v) for v in self.v], polys)
            self._bvh_key = key
        dn = Vector(direction).normalized()
        hit = self._bvh.ray_cast(Vector(origin), dn)[0]
        return None if hit is None else hit - dn * lift

    def clear_out(self, faces, parts, gap=0.002):
        """Mark `faces` as decals and push each out along its normal until its centre and edge midpoints clear the
        faces of `parts` by `gap`: a flat polygon spanning a convex surface sinks into it between its corners."""
        self.decals.update(faces)
        for fi in faces:
            idx = self.f[fi]
            P = [self.v[i] for i in idx]
            n = Vector()
            for k in range(len(P)):                                  # Newell normal (the winding the face shows)
                a, b = P[k], P[(k + 1) % len(P)]
                n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
            if n.length < 1e-12:
                continue
            n.normalize()
            need = 0.0
            for q in [sum(P, Vector()) / len(P)] + [(P[k] + P[(k + 1) % len(P)]) / 2 for k in range(len(P))]:
                h = self.surface(parts, q + n * 0.05, -n, 0.0)
                if h is not None:
                    need = max(need, gap - (q - h).dot(n))
            if need > 0:
                for i in idx:
                    self.v[i] = self.v[i] + n * need

    def vert(self, co, w, pat=0, pj=0):
        self.v.append(Vector(co))
        self.w.append(dict(w))
        self.pat.append(pat)
        self.pj.append(pj)
        return len(self.v) - 1

    def island(self, w, h):
        self.isl.append((max(float(w), 0.01), max(float(h), 0.01)))
        return len(self.isl) - 1

    def _planar(self, idx):
        pts = [self.v[i] for i in idx]
        e1 = (pts[1] - pts[0]).normalized()
        n = (pts[1] - pts[0]).cross(pts[2] - pts[1])
        e2 = n.normalized().cross(e1) if n.length > 1e-12 else V3(0, 0, 1)
        co = [((q - pts[0]).dot(e1), (q - pts[0]).dot(e2)) for q in pts]
        x0, y0 = min(c[0] for c in co), min(c[1] for c in co)
        w, h = max(max(c[0] for c in co) - x0, 1e-3), max(max(c[1] for c in co) - y0, 1e-3)
        return [((c[0] - x0) / w, (c[1] - y0) / h) for c in co], self.island(w, h)

    def face(self, idx, part, reg, uv=None, isl=-1):
        if uv is None or isl < 0:
            uv, isl = self._planar(idx)
        self.f.append(list(idx))
        self.fpart.append(part)
        self.freg.append(REG[reg])
        self.fuv.append([tuple(x) for x in uv])
        self.fisl.append(isl)

    def ring(self, c, e1, e2, rx, ryf, ryb, segs, w, phase=0.0, shape=None, jitter=None):
        rn = self._rn
        self._rn += 1
        out = []
        for j in range(segs):
            a = 2 * math.pi * j / segs + phase
            ca, sa = math.cos(a), math.sin(a)
            ry = ryf if sa > 0 else ryb
            k = 1.0 + (jitter[j % len(jitter)] if jitter else 0.0)
            p = c + e1 * (rx * ca * k) + e2 * (ry * sa * k)
            if shape:
                p = shape(p, a)
            wv = w(p) if callable(w) else w
            out.append(self.vert(p, wv, (j + rn) % 2, j))
        return out

    def bridge(self, ra, rb, part, reg, isl=-1, va=0.0, vb=1.0):
        n = len(ra)
        for j in range(n):
            uv = ((j / n, va), ((j + 1) / n, va), ((j + 1) / n, vb), (j / n, vb))
            self.face((ra[j], ra[(j + 1) % n], rb[(j + 1) % n], rb[j]), part, reg, uv if isl >= 0 else None, isl)

    def face_toward(self, idx, direction, part, reg, uv=None, isl=-1):
        a, b, c = (self.v[i] for i in idx[:3])
        n = (b - a).cross(c - b)
        if n.dot(direction) < 0:
            idx = list(reversed(idx))
            uv = list(reversed(uv)) if uv is not None else None
        self.face(idx, part, reg, uv, isl)

    def cap(self, ring, part, reg, flip=False, isl=-1, v=0.0):
        n = len(ring)
        order = list(range(n))[::-1] if flip else list(range(n))
        self.face([ring[k] for k in order], part, reg, [(k / n, v) for k in order] if isl >= 0 else None, isl)

    def box(self, center, size, rot, part, reg, w, taper=None):
        hx, hy, hz = (s_ / 2 for s_ in size)
        idx = []
        for k in range(8):
            x, y, z = (hx if k & 1 else -hx), (hy if k & 2 else -hy), (hz if k & 4 else -hz)
            if taper and y > 0:
                x, z = x * taper[0], z * taper[1]
            idx.append(self.vert(center + rot @ V3(x, y, z), w))
        isl = self.island(2 * (size[0] + size[2]), size[1])
        ucorner = {(0, 0): 0.0, (1, 0): 0.25, (1, 1): 0.5, (0, 1): 0.75}
        for q in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)):
            uv = []
            for k in q:
                u = ucorner[(k & 1, (k >> 2) & 1)]
                if q == (0, 4, 6, 2) and u == 0.0:
                    u = 1.0
                uv.append((u, 1.0 if k & 2 else 0.0))
            self.face([idx[i] for i in q], part, reg, uv, isl)
        return idx

    def ellipsoid(self, c, r, segs, rings, part, reg, w, deform=None, zmin=-1.0, zmax=1.0, close_bottom=True, isl=None):
        rows = []
        for i in range(rings + 1):
            t = zmax - (zmax - zmin) * i / rings
            if abs(t) >= 0.999:
                p_unit = V3(0, 0, 1 if t > 0 else -1)
                p = c + V3(0, 0, r[2] * p_unit.z)
                if deform:
                    p = deform(p_unit, p)
                rows.append([self.vert(p, w)])
                continue
            rr = math.sqrt(max(0.0, 1 - t * t))
            row = []
            rn = self._rn
            self._rn += 1
            for j in range(segs):
                a = 2 * math.pi * j / segs
                p_unit = V3(rr * math.cos(a), rr * math.sin(a), t)
                p = c + V3(r[0] * p_unit.x, r[1] * p_unit.y, r[2] * p_unit.z)
                if deform:
                    p = deform(p_unit, p)
                row.append(self.vert(p, w, (j + rn) % 2, j))
            rows.append(row)
        arc = math.acos(max(-1.0, min(1.0, zmin))) - math.acos(max(-1.0, min(1.0, zmax)))
        if isl is None:
            isl = self.island(2 * math.pi * max(r[0], r[1]), r[2] * max(arc, 0.05))
        vr = [1.0 - i / (len(rows) - 1) for i in range(len(rows))]
        n = segs
        for i in range(len(rows) - 1):
            a, b, va, vb = rows[i], rows[i + 1], vr[i], vr[i + 1]
            if len(a) == 1:
                for j in range(n):
                    self._face_r(reg, part, (a[0], b[j], b[(j + 1) % n]), ((0.5, va), (j / n, vb), ((j + 1) / n, vb)), isl)
            elif len(b) == 1:
                for j in range(n):
                    self._face_r(reg, part, (a[j], b[0], a[(j + 1) % n]), ((j / n, va), (0.5, vb), ((j + 1) / n, va)), isl)
            else:
                for j in range(n):
                    self._face_r(reg, part, (a[j], b[j], b[(j + 1) % n], a[(j + 1) % n]),
                                 ((j / n, va), (j / n, vb), ((j + 1) / n, vb), ((j + 1) / n, va)), isl)
        if close_bottom and len(rows[-1]) > 1:
            self._face_r(reg, part, list(rows[-1]), [(k / n, vr[-1]) for k in range(n)], isl)
        return rows

    def _face_r(self, reg, part, idx, uv=None, isl=-1):
        if callable(reg):
            c = sum((self.v[i] for i in idx), Vector()) / len(idx)
            reg = reg(c)
        self.face(idx, part, reg, uv, isl)

    def octa(self, c, r, part, reg, w):
        """A small octahedron (8 tris): glow balls, flower heads."""
        p = [self.vert(c + d, w) for d in (V3(r, 0, 0), V3(0, r, 0), V3(-r, 0, 0), V3(0, -r, 0), V3(0, 0, r), V3(0, 0, -r))]
        isl = self.island(4 * r, 2 * r)
        for k in range(4):
            a, b = p[k], p[(k + 1) % 4]
            self.face_toward((p[4], a, b), (self.v[a] + self.v[b]) / 2 + V3(0, 0, r / 2) - c, part, reg,
                             ((0.5, 1.0), (k / 4, 0.5), ((k + 1) / 4, 0.5)), isl)
            self.face_toward((p[5], b, a), (self.v[a] + self.v[b]) / 2 - V3(0, 0, r / 2) - c, part, reg,
                             ((0.5, 0.0), ((k + 1) / 4, 0.5), (k / 4, 0.5)), isl)


def frame_for(t, ref=V3(1, 0, 0)):
    t = t.normalized()
    e1 = ref - t * ref.dot(t)
    if e1.length < 1e-6:
        e1 = V3(0, 1, 0) - t * t.y
    e1.normalize()
    return e1, t.cross(e1)


def lerpw(a, b, s):
    out = {}
    for k, v in a.items():
        out[k] = out.get(k, 0.0) + v * (1 - s)
    for k, v in b.items():
        out[k] = out.get(k, 0.0) + v * s
    return {k: v for k, v in out.items() if v > 1e-6}


def limb(g, pts, radii, wts, segs, part, regs, ref=V3(1, 0, 0), cap_end=False, cap_start=False, flat=1.0, jitter=None,
         isl=None):
    """Loft a tube through pts (one ring each). One UV island: u around (seam at ring vertex 0), v along the length."""
    rings = []
    for i, (p, r, w) in enumerate(zip(pts, radii, wts)):
        t = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
        e1, e2 = frame_for(t, ref)
        rings.append(g.ring(p, e1, e2, r, r * flat, r * flat, segs, w, jitter=jitter))
    lens = [0.0]
    for a, b in zip(pts, pts[1:]):
        lens.append(lens[-1] + (b - a).length)
    total = max(lens[-1], 1e-3)
    if isl is None:
        isl = g.island(math.pi * (1 + flat) * sum(radii) / len(radii), total)
    for i in range(len(rings) - 1):
        g.bridge(rings[i], rings[i + 1], part, regs[i], isl, lens[i] / total, lens[i + 1] / total)
    if cap_start:
        g.cap(rings[0], part, regs[0], flip=True, isl=isl, v=0.0)
    if cap_end:
        g.cap(rings[-1], part, regs[-1], isl=isl, v=1.0)
    return rings


def glyph(g, parts, pts_xz, w, part, reg, y_from=1.0, lift=0.004, toward=None):
    """A flat polygon drawn on the front (+Y) of `parts`: each (x, z) is projected along -Y onto those faces and
    lifted toward the viewer (eye holes, jack-o-lantern faces, LED masks, glowing eyes)."""
    idx = []
    for x, z in pts_xz:
        q = g.surface(parts, V3(x, y_from, z), V3(0, -1, 0), lift)
        if q is None:
            raise RuntimeError(f"glyph point ({x:.3f}, {z:.3f}) misses {parts}")
        idx.append(g.vert(q, w))
    g.face_toward(idx, toward or V3(0, 1, 0), part, reg)
    g.clear_out([len(g.f) - 1], parts)
    return idx


def quad2(g, pts, part, reg, w, normal):
    """A two-sided quad (front face toward normal + a back face 3 mm behind)."""
    g.face_toward([g.vert(p, w) for p in pts], normal, part, reg)
    g.face_toward([g.vert(p - normal.normalized() * 0.003, w) for p in pts], -normal, part, reg)


HC = V3(0, 0.012, 1.630)                   # head centre


def hand_rot(n):
    """The hand box frame: x = thickness (palm normal), y = wrist -> fingertips, z = palm width."""
    s = 1 if n == "R" else -1
    hd = (J[f"fingers.{n}"] - J[f"wrist.{n}"]).normalized()
    side = V3(0, 1, 0).cross(hd).normalized()
    return Matrix((side * s, hd, side.cross(hd) * s)).transposed()


def torso_w(z):
    """Torso bone weights by height (the same blend add_body gives the torso rings)."""
    if z < 1.0:
        return {"pelvis": 1.0}
    if z < 1.12:
        return lerpw({"pelvis": 1.0}, {"spine1": 1.0}, (z - 1.0) / 0.12)
    if z < 1.28:
        return lerpw({"spine1": 1.0}, {"spine2": 1.0}, (z - 1.12) / 0.16)
    return {"spine2": 1.0}


def jack_face(detail, s=1.0):
    """Jack-o-lantern glyphs: (x, z) polygons about a pumpkin centre, for a pumpkin of radius ~0.165 m scaled by s."""
    polys = [[(-0.100, 0.008), (-0.030, 0.008), (-0.062, 0.062)], [(0.030, 0.008), (0.100, 0.008), (0.062, 0.062)]]
    if detail == "near":                                             # + a nose and a jagged grin (one polygon)
        xs, tp = (-0.105, -0.052, 0.0, 0.052, 0.105), (-0.044, -0.058, -0.047, -0.058, -0.044)
        bt = (-0.064, -0.088, -0.096, -0.088, -0.064)
        polys += [[(-0.018, -0.026), (0.018, -0.026), (0.0, 0.004)]]
        polys += [list(zip(xs, tp)) + list(zip(xs[::-1], bt[::-1]))]
    else:                                                            # + one mouth quad
        polys += [[(-0.085, -0.035), (0.085, -0.035), (0.065, -0.07), (-0.065, -0.07)]]
    return [[(x * s, z * s) for x, z in poly] for poly in polys]


def pumpkin(g, c, r, segs, rings, rib, part, w, detail, isl=None, stem_segs=4, reg="pumpkin", reg2="pumpkin2",
            face_reg="glow_pface"):
    """A ribbed pumpkin (segs / 2 lobes when rib > 0, a dimple under the stem, a flat bottom), its stem, and a glowing
    jack-o-lantern face: glyphs of the same part in a glow region (they ship in the glow mesh)."""
    def deform(u, p):
        q = p.copy()
        if rib:
            k = 1.0 + rib * math.cos(segs / 2 * math.atan2(u.y, u.x)) * (1.0 - u.z * u.z)
            q.x, q.y = c.x + (q.x - c.x) * k, c.y + (q.y - c.y) * k
        if u.z > 0.7:
            q.z -= 0.23 * r[2] * (u.z - 0.7) / 0.3
        if u.z < -0.55:
            q.z = max(q.z, c.z - r[2] * 0.8)
        return q
    g.ellipsoid(c, r, segs, rings, part, reg, w, deform=deform, isl=isl)
    s = r[0] / 0.165
    st = c + V3(0, 0, r[2] * 0.73)
    limb(g, [st, st + V3(0.008, -0.01, 0.055) * s, st + V3(0.03, -0.02, 0.08) * s], [0.02 * s, 0.015 * s, 0.011 * s],
         [w, w, w], stem_segs, part, [reg2, reg2], cap_end=True)
    for poly in jack_face(detail, s):
        glyph(g, [part], [(c.x + x, c.z + z) for x, z in poly], w, part, face_reg, lift=0.005)


# ---------------------------------------------------------------------------- body
def add_body(g, d):
    """The base body (parts b_torso, b_head, b_arms, b_legs): torso bands hips / belly / midriff / chest / shoulders,
    arms sleeve_top / sleeve_mid / forearm / wrist / hand, legs thigh_top / thigh / knee / shin / ankle / shoe."""
    def tw(z):
        if z < 1.0:
            return {"pelvis": 1.0}
        if z < 1.12:
            return lerpw({"pelvis": 1.0}, {"spine1": 1.0}, (z - 1.0) / 0.12)
        if z < 1.28:
            return lerpw({"spine1": 1.0}, {"spine2": 1.0}, (z - 1.12) / 0.16)
        return {"spine2": 1.0}
    torso = [(0.78, 0.125, 0.075, 0.085), (0.90, 0.168, 0.095, 0.115), (1.02, 0.146, 0.088, 0.085),
             (1.14, 0.150, 0.098, 0.088), (1.27, 0.166, 0.112, 0.094), (1.37, 0.182, 0.098, 0.090),
             (1.435, 0.168, 0.068, 0.072), (1.48, 0.085, 0.058, 0.062)]
    torso = [r for i, r in enumerate(torso) if i in d["torso_keep"]]
    rings = []
    for z, rx, ryf, ryb in torso:
        def shoulder_w(p, z=z):
            w = tw(z)
            if z > 1.40 and abs(p.x) > 0.09:
                w = lerpw(w, {f"clav.{'R' if p.x > 0 else 'L'}": 1.0}, 0.35)
            return w
        rings.append(g.ring(V3(0, -0.005, z), V3(1, 0, 0), V3(0, 1, 0), rx, ryf, ryb, d["torso"], shoulder_w,
                            phase=math.pi / d["torso"]))
    zs = [r[0] for r in torso]

    def band(z0, z1):
        zc = (z0 + z1) / 2
        return "hips" if zc < 0.90 else "belly" if zc < 1.0 else "midriff" if zc < 1.14 else "chest" if zc < 1.37 else "shoulders"
    tisl = g.island(2 * math.pi * max(r[1] for r in torso), zs[-1] - zs[0])
    g.named["torso"] = tisl                                           # the ghost sheet reuses it
    vz = [(z - zs[0]) / (zs[-1] - zs[0]) for z in zs]
    for i in range(len(rings) - 1):
        g.bridge(rings[i], rings[i + 1], "b_torso", band(zs[i], zs[i + 1]), tisl, vz[i], vz[i + 1])
    g.cap(rings[0], "b_torso", "hips", flip=True, isl=tisl, v=0.0)
    g.cap(rings[-1], "b_torso", "shoulders", isl=tisl, v=1.0)
    if d["neck"]:
        limb(g, [V3(0, 0.0, 1.43), V3(0, 0.012, 1.555)], [0.062, 0.056],
             [{"spine2": 0.5, "neck": 0.5}, {"neck": 0.4, "head": 0.6}], d["neck"], "b_head", ["skin"])
    hc = HC

    def head_deform(u, p):
        q = p.copy()
        if u.z < -0.15:
            k = min(1.0, (-0.15 - u.z) / 0.85)
            q.x = hc.x + (q.x - hc.x) * (1 - 0.35 * k)
            if u.y < 0:
                q.y = hc.y + (q.y - hc.y) * (1 - 0.25 * k)
        if u.y > 0.55 and abs(u.x) < 0.35 and -0.35 < u.z < 0.15:
            q.y += 0.018 * (1 - abs(u.x) / 0.35)
        if u.y > 0.3 and u.z < -0.55:
            q.y += 0.01
        if u.y < -0.2 and u.z > -0.2:
            q.y -= 0.008
        return q

    def head_reg(c):
        u = c - hc
        if u.z > 0.045 or (u.y < -0.02 and u.z > -0.04):
            return "scalp"
        ang = math.degrees(math.atan2(u.y, u.x))
        if d["face_detail"] and u.y > 0.03:
            if 0.0 < u.z < 0.028 and 55 < ang < 125:
                return "eyes"
            if 0.028 < u.z < 0.056 and 35 < ang < 145:
                return "brow"
            if -0.056 < u.z < -0.028 and 62 < ang < 118:
                return "mouth"
        if u.z < -0.02 and u.y > -0.01:
            return "jaw"
        return "face"
    g.named["head"] = g.island(2 * math.pi * 0.093, 0.112 * math.pi)  # the pumpkin head reuses it
    g.ellipsoid(hc, (0.074, 0.093, 0.112), d["head_segs"], d["head_rings"], "b_head", head_reg, {"head": 1.0},
                deform=head_deform, isl=g.named["head"])
    for s, n in ((1, "R"), (-1, "L")):
        sh, el, wr, fi = J[f"shoulder.{n}"], J[f"elbow.{n}"], J[f"wrist.{n}"], J[f"fingers.{n}"]
        ua, fa, ha = f"upperarm.{n}", f"forearm.{n}", f"hand.{n}"
        pts = [sh + V3(-s * 0.02, 0, -0.012), sh.lerp(el, 0.45), el, el.lerp(wr, 0.5), wr]
        rad = [0.056, 0.049, 0.041, 0.040, 0.031]
        wts = [{ua: 0.75, f"clav.{n}": 0.25}, {ua: 1.0}, {ua: 0.5, fa: 0.5}, {fa: 1.0}, {fa: 0.4, ha: 0.6}]
        regs = ["sleeve_top", "sleeve_mid", "forearm", "wrist"]
        if d["arm_rings"] == 3:
            pts, rad, wts = [pts[0], pts[2], pts[4]], [rad[0], rad[2], rad[4]], [wts[0], wts[2], wts[4]]
            regs = ["sleeve_top", "forearm"]
        limb(g, pts, rad, wts, d["arm"], "b_arms", regs, ref=V3(0, 1, 0))
        g.named[f"arm.{n}"] = (pts, wts)                              # bone strips follow the same weights
        rot = hand_rot(n)
        g.box(wr.lerp(fi, 0.5), (0.038, (fi - wr).length, 0.088), rot, "b_arms", "hand", {ha: 1.0}, taper=(0.75, 0.85))
        if d["thumb"]:
            g.box(wr.lerp(fi, 0.33) + V3(-s * 0.004, 0.04, 0.0), (0.022, 0.06, 0.022), rot, "b_arms", "hand", {ha: 1.0})
    for s, n in ((1, "R"), (-1, "L")):
        hp, kn, an = J[f"hip.{n}"], J[f"knee.{n}"], J[f"ankle.{n}"]
        th, sn, ft = f"thigh.{n}", f"shin.{n}", f"foot.{n}"
        pts = [hp + V3(0, 0, 0.03), hp.lerp(kn, 0.3), hp.lerp(kn, 0.62), kn, kn.lerp(an, 0.4), an + V3(0, 0, 0.02)]
        rad = [0.086, 0.081, 0.071, 0.054, 0.057, 0.040]
        wts = [{th: 1.0}, {th: 1.0}, {th: 1.0}, {th: 0.5, sn: 0.5}, {sn: 1.0}, {sn: 0.6, ft: 0.4}]
        regs = ["thigh_top", "thigh", "knee", "shin", "ankle"]
        if d["leg_rings"] == 3:
            pts, rad, wts = [pts[0], pts[3], pts[5]], [rad[0], rad[3], rad[5]], [wts[0], wts[3], wts[5]]
            regs = ["thigh", "shin"]
        limb(g, pts, rad, wts, d["leg"], "b_legs", regs, ref=V3(1, 0, 0))
        g.named[f"leg.{n}"] = (pts, wts)
        if d["one_box_shoes"]:
            g.box(V3(an.x, 0.03, 0.045), (0.095, 0.26, 0.09), Matrix.Identity(3), "b_legs", "shoe", {ft: 1.0}, taper=(0.85, 0.6))
        else:
            g.box(V3(an.x, 0.035, 0.022), (0.098, 0.275, 0.044), Matrix.Identity(3), "b_legs", "sole", {ft: 1.0},
                  taper=(0.85, 1.0))
            g.box(V3(an.x, 0.02, 0.068), (0.09, 0.2, 0.06), Matrix.Identity(3), "b_legs", "shoe", {ft: 1.0}, taper=(0.9, 0.6))


# ---------------------------------------------------------------------------- head wear
def add_head_wear(g, d):
    hc, hw, segs = HC, {"head": 1.0}, d["hair_segs"]

    def dome(part, reg, scale, zmin, front_cut=0.0, extra_back=0.0, strands=False, face_open=False):
        def deform(u, p):
            q = p.copy()
            if u.y < 0 and u.z < 0.2:
                q.z -= extra_back * (-u.y)
            if u.y > 0.35 and u.z < 0.35:
                q.z += front_cut * (u.y - 0.35)
            if face_open and u.y > 0.2 and u.z < 0.42:                 # a hood: the front opens up to the forehead
                k = min(1.0, (u.y - 0.2) / 0.3)
                zt = hc.z + 0.006 + 0.112 * scale * 0.42
                q.z += (max(q.z, zt) - q.z) * k
            if strands:
                if u.z > 0.3:
                    q.z += 0.012 * (u.z - 0.3) + 0.006 * max(0.0, -u.y)
                k = math.sin(37.0 * u.x + 23.0 * u.y + 11.0 * u.z)
                q = hc + (q - hc) * (1.0 + 0.045 * k)
            return q
        rows = g.ellipsoid(hc + V3(0, -0.004, 0.006), (0.074 * scale, 0.093 * scale, 0.112 * scale), segs,
                           d["hair_rings"], part, reg, hw, deform=deform, zmin=zmin, zmax=1.0, close_bottom=False)
        if strands:
            for j, vi in enumerate(rows[-1]):
                if j % 2:
                    front = (g.v[vi] - hc).y > 0.04
                    g.v[vi] = g.v[vi] + V3(0, 0, -(0.012 if front else 0.028))
        return rows
    # hair: one shared shell + appendages (long curtain, ponytail, bun, braids)
    dome("hair", "hair", 1.09, -0.2, front_cut=0.10, extra_back=0.025, strands=d["hair_strands"])
    cols_x = (-0.095, -0.05, 0.0, 0.05, 0.095) if d["hair_strands"] else (-0.085, 0.085)
    for side, back in ((1, -0.097), (-1, -0.083)):
        grid = []
        for zi, z in enumerate((1.63, 1.50, 1.36)):
            row = []
            for xi, x in enumerate(cols_x):
                drop = (0.035 if (xi % 2) else 0.0) if zi == 2 else 0.0
                yy = back + 3.0 * x * x - 0.014 * (1.63 - z) / 0.23
                row.append(g.vert(V3(x * (1 + 0.18 * (1.63 - z) / 0.27), yy, z - drop),
                                  lerpw({"head": 1.0}, {"spine2": 1.0}, min(1.0, (1.63 - z) / 0.3))))
            grid.append(row)
        hisl = g.island(2 * max(cols_x), 0.3)
        nx = len(cols_x) - 1
        for zi in range(2):
            for xi in range(nx):
                q = (grid[zi][xi], grid[zi][xi + 1], grid[zi + 1][xi + 1], grid[zi + 1][xi])
                uv = ((xi / nx, 1 - zi / 2), ((xi + 1) / nx, 1 - zi / 2), ((xi + 1) / nx, 1 - (zi + 1) / 2), (xi / nx, 1 - (zi + 1) / 2))
                g.face_toward(q, V3(0, -side, 0), "hair_long", "hair", uv, hisl)
    limb(g, [hc + V3(0, -0.11, 0.06), hc + V3(0, -0.15, -0.05), hc + V3(0, -0.155, -0.22)], [0.03, 0.026, 0.012],
         [hw, hw, lerpw(hw, {"neck": 1.0}, 0.5)], max(4, segs // 2), "hair_pony", ["hair", "hair"], cap_end=True)
    g.ellipsoid(hc + V3(0, -0.07, 0.10), (0.047, 0.047, 0.042), max(6, segs // 2), 3, "hair_bun", "hair", hw)
    for s in (1, -1):                                                   # braids: over the shoulders to the chest
        limb(g, [hc + V3(s * 0.07, -0.03, -0.04), V3(s * 0.115, 0.03, 1.475), V3(s * 0.12, 0.108, 1.33)],
             [0.016, 0.014, 0.008], [hw, {"neck": 0.5, "spine2": 0.5}, {"spine2": 1.0}], 4, "hair_braids",
             ["hair", "hair"], cap_end=True)
    # hats: a shared crown shell (cap / beanie) + brim / pompom; bucket; cowboy
    dome("hat_dome", "hat", 1.19, 0.03)
    brim = [hc + V3(x, y, 0.035 - 0.02 * max(0.0, y - 0.1) / 0.08) for x, y in ((-0.08, 0.08), (0.08, 0.08), (0.075, 0.18), (-0.075, 0.18))]
    g.face_toward([g.vert(q, hw) for q in brim], V3(0, 0, 1), "hat_brim", "hat2")
    g.face_toward([g.vert(q - V3(0, 0, 0.004), hw) for q in brim], V3(0, 0, -1), "hat_brim", "hat2")
    g.octa(hc + V3(0, -0.01, 0.15), 0.03, "hat_pom", "hat2", hw)
    crown = limb(g, [hc + V3(0, -0.004, 0.04), hc + V3(0, -0.004, 0.158)], [0.114, 0.09], [hw, hw], segs, "hat_bucket",
                 ["hat"], cap_end=True)
    outer = g.ring(hc + V3(0, -0.004, 0.012), V3(1, 0, 0), V3(0, 1, 0), 0.16, 0.165, 0.16, segs, hw)
    g.bridge(outer, crown[0], "hat_bucket", "hat2", g.island(2 * math.pi * 0.16, 0.05), 0.0, 1.0)     # top: faces up
    ui = [g.vert(g.v[i] - V3(0, 0, 0.005), hw) for i in crown[0]]
    uo = [g.vert(g.v[i] - V3(0, 0, 0.005), hw) for i in outer]
    g.bridge(ui, uo, "hat_bucket", "hat2", g.island(2 * math.pi * 0.16, 0.05), 0.0, 1.0)               # under: down
    cseg = max(6, segs - 4)
    g.named["cow_crown"] = g.island(math.pi * 2 * 0.095, 0.14)        # the witch hat reuses these three (one hat each)
    g.named["cow_top"] = g.island(2 * math.pi * 0.2, 0.08)
    g.named["cow_under"] = g.island(2 * math.pi * 0.2, 0.08)
    ccrown = limb(g, [hc + V3(0, -0.004, 0.05), hc + V3(0, -0.004, 0.19)], [0.105, 0.085], [hw, hw], cseg, "hat_cowboy",
                  ["hat"], cap_end=True, isl=g.named["cow_crown"])

    def curl(p, a):                                                   # sides of the brim turned up
        return p + V3(0, 0, 0.045 * abs(math.cos(a)) ** 3)
    cout = g.ring(hc + V3(0, -0.004, 0.035), V3(1, 0, 0), V3(0, 1, 0), 0.22, 0.20, 0.19, cseg, hw, shape=curl)
    g.bridge(cout, ccrown[0], "hat_cowboy", "hat2", g.named["cow_top"], 0.0, 1.0)                       # top: faces up
    ci = [g.vert(g.v[i] - V3(0, 0, 0.005), hw) for i in ccrown[0]]
    co_ = [g.vert(g.v[i] - V3(0, 0, 0.005), hw) for i in cout]
    g.bridge(ci, co_, "hat_cowboy", "hat2", g.named["cow_under"], 0.0, 1.0)                             # under: down
    # flower crown: little flowers around the head (colours cycle by flower: pj)
    nfl = 8 if d["detail"] == "near" else 5
    for k in range(nfl):
        a = 2 * math.pi * (k + 0.5) / nfl
        c = hc + V3(0.082 * math.cos(a), 0.1 * math.sin(a), 0.045 + 0.012 * math.sin(a))
        i0 = len(g.v)
        if d["detail"] == "near":
            g.octa(c, 0.022, "crown", "crown", hw)
        else:
            quad2(g, [c + V3(-0.025, 0, -0.02), c + V3(0.025, 0, -0.02), c + V3(0.025, 0, 0.02), c + V3(-0.025, 0, 0.02)],
                  "crown", "crown", hw, V3(math.cos(a), math.sin(a), 0))
        for vi in range(i0, len(g.v)):
            g.pj[vi] = k
    if d["detail"] == "near":                                           # goggles pushed up on the forehead
        g.box(hc + V3(0, 0.072, 0.07), (0.15, 0.03, 0.045), Matrix.Rotation(math.radians(20), 3, "X"), "goggles", "goggles", hw)
    for s in (1, -1):                                                   # light-up horns / ears (glow)
        hb = hc + V3(s * 0.055, 0.02, 0.085)
        limb(g, [hb, hb + V3(s * 0.035, 0.0, 0.07), hb + V3(s * 0.06, 0.0, 0.10)], [0.022, 0.012, 0.004], [hw, hw, hw],
             d["horn_segs"], "horns", ["glow_horn", "glow_horn"], cap_start=True)
        eb = hc + V3(s * 0.06, 0.0, 0.09)
        quad2(g, [eb + V3(-s * 0.03, 0, 0), eb + V3(s * 0.03, 0, 0), eb + V3(s * 0.01, 0, 0.065), eb + V3(-s * 0.005, 0, 0.06)],
              "ears", "glow_horn", hw, V3(0, 1, 0))
    # witch hat: a wide wavy brim (top + under) and a bent cone with a coloured band; one hat per person, so it reuses
    # the cowboy hat islands. witch_band: an LED band around it (glow mesh)
    ws, zb = d["witch_segs"], 0.040
    wout = g.ring(hc + V3(0, -0.004, zb), V3(1, 0, 0), V3(0, 1, 0), 0.215, 0.225, 0.215, ws, hw,
                  shape=lambda p, a: p + V3(0, 0, 0.014 * math.cos(2 * a) - 0.008))
    base_r = (0.097, 0.110, 0.106)
    wbase = g.ring(hc + V3(0, -0.004, zb + 0.004), V3(1, 0, 0), V3(0, 1, 0), *base_r, ws, hw)
    g.bridge(wout, wbase, "witch_hat", "hat", g.named["cow_top"], 0.0, 1.0)                            # top: faces up
    wui = [g.vert(g.v[i] - V3(0, 0, 0.005), hw) for i in wbase]
    wuo = [g.vert(g.v[i] - V3(0, 0, 0.005), hw) for i in wout]
    g.bridge(wui, wuo, "witch_hat", "hat", g.named["cow_under"], 0.0, 1.0)                             # under: down
    cone = [wbase]
    for dz, rx, ry, off in d["witch_cone"]:
        cone.append(g.ring(hc + off + V3(0, 0, dz), V3(1, 0, 0), V3(0, 1, 0), rx, ry, ry, ws, hw))
    tip = g.vert(hc + V3(0.05, -0.13, 0.40), hw)
    nv = len(cone)
    for k in range(nv - 1):
        g.bridge(cone[k], cone[k + 1], "witch_hat", "hat2" if k == 0 else "hat", g.named["cow_crown"], k / nv,
                 (k + 1) / nv)
    for j in range(ws):
        g.face((cone[-1][j], cone[-1][(j + 1) % ws], tip), "witch_hat", "hat",
               ((j / ws, (nv - 1) / nv), ((j + 1) / ws, (nv - 1) / nv), ((j + 0.5) / ws, 1.0)), g.named["cow_crown"])
    dz1, rx1, ry1, off1 = d["witch_cone"][0]
    band = []
    for t in (0.2, 0.8):                                               # 4.5 mm outside the band, within its height
        zt = zb + 0.004 + t * (dz1 - zb - 0.004)
        rxt = base_r[0] + t * (rx1 - base_r[0]) + 0.0045
        ryt = base_r[1] + t * (ry1 - base_r[1]) + 0.0045
        band.append(g.ring(hc + V3(0, -0.004 + t * (off1.y + 0.004), zt), V3(1, 0, 0), V3(0, 1, 0), rxt, ryt, ryt, ws, hw))
    g.bridge(band[0], band[1], "witch_band", "glow_band")
    # pumpkin head: a ribbed pumpkin sitting on the shoulders (it replaces the head and the hair, so it reuses the head
    # island) with a stem and a glowing jack-o-lantern face
    pumpkin(g, hc + V3(0, 0.0, -0.012), (0.165, 0.152, 0.130), d["pumpkin_segs"], d["pumpkin_rings"], d["pumpkin_rib"],
            "pumpkin", hw, d["detail"], isl=g.named["head"], stem_segs=d["stem_segs"])
    # light-up mask (purge style: slanted eyes, a stitched grin) and glowing eyes: glyphs on the face (glow mesh)
    ez, mz = hc.z + 0.015, hc.z - 0.043
    ex0, ex1 = d["mask_eye_x"]
    for s in (1, -1):
        glyph(g, ["b_head"], [(s * ex0, ez - 0.004), (s * ex1, ez + 0.006), (s * ex1, ez + 0.019), (s * ex0, ez + 0.009)],
              hw, "mask_led", "glow_mask", lift=0.005)
        glyph(g, ["b_head"], [(s * (ex0 + 0.004), ez - 0.001), (s * (ex1 - 0.006), ez + 0.003),
                              (s * (ex1 - 0.006), ez + 0.014), (s * (ex0 + 0.004), ez + 0.011)],
              hw, "glow_eyes", "glow_eye", lift=0.005)
    mx = d["mask_mouth_x"]
    xs = [mx * (2 * k / d["mask_mouth_n"] - 1) for k in range(d["mask_mouth_n"] + 1)]
    zs_ = [mz + 0.009 * (abs(x) / mx) ** 2 for x in xs]                  # a grin: the ends turn up
    for k in range(len(xs) - 1):
        glyph(g, ["b_head"], [(xs[k], zs_[k] + 0.0055), (xs[k + 1], zs_[k + 1] + 0.0055), (xs[k + 1], zs_[k + 1] - 0.0055),
                              (xs[k], zs_[k] - 0.0055)], hw, "mask_led", "glow_mask", lift=0.005)


# ---------------------------------------------------------------------------- outfits, costumes and carried things
def add_items(g, d):
    near = d["detail"] == "near"
    hwR, hwL = {"hand.R": 1.0}, {"hand.L": 1.0}
    gR, gL = J["grip.R"], J["grip.L"]
    hdR = (J["fingers.R"] - J["wrist.R"]).normalized()
    # hydration pack (+ straps)
    g.box(V3(0, -0.14, 1.22), (0.22, 0.09, 0.30), Matrix.Identity(3), "pack", "pack", {"spine2": 1.0})
    if near:
        for s in (1, -1):
            g.box(V3(s * 0.10, 0.09, 1.30), (0.035, 0.03, 0.24), Matrix.Rotation(math.radians(-12), 3, "X"), "pack", "strap",
                  {"spine2": 1.0})
            g.box(V3(s * 0.10, -0.03, 1.448), (0.035, 0.2, 0.03), Matrix.Identity(3), "pack", "strap", {"spine2": 1.0})
    # cape / pashmina: from the shoulders down the back, two-sided
    cw = [{"spine2": 1.0}, {"spine1": 0.6, "spine2": 0.4}, {"pelvis": 0.6, "spine1": 0.4}]
    rows = [(1.43, -0.105, 0.17), (1.15, -0.15, 0.22), (0.86, -0.19, 0.26)]
    ncol = 3 if near else 2
    for side in (1, -1):
        grid = [[g.vert(V3(-hx + 2 * hx * k / (ncol - 1), y - side * 0.0015 + 0.03 * abs(-1 + 2 * k / (ncol - 1)), z), w)
                 for k in range(ncol)] for (z, y, hx), w in zip(rows, cw)]
        isl = g.island(0.5, 0.6)
        for r in range(2):
            for k in range(ncol - 1):
                uv = ((k / (ncol - 1), 1 - r / 2), ((k + 1) / (ncol - 1), 1 - r / 2), ((k + 1) / (ncol - 1), 1 - (r + 1) / 2),
                      (k / (ncol - 1), 1 - (r + 1) / 2))
                g.face_toward((grid[r][k], grid[r][k + 1], grid[r + 1][k + 1], grid[r + 1][k]), V3(0, -side, 0),
                              "cape", "cape" if side > 0 else "cape2", uv, isl)
    # tutu: a ruffled skirt flaring from the hips (two-sided)
    ts = d["tutu_segs"]
    rj = [0.12 if (j % 2) else -0.06 for j in range(ts)]
    top = g.ring(V3(0, -0.005, 0.95), V3(1, 0, 0), V3(0, 1, 0), 0.175, 0.105, 0.125, ts, {"pelvis": 1.0})
    bot = g.ring(V3(0, -0.005, 0.80), V3(1, 0, 0), V3(0, 1, 0), 0.31, 0.26, 0.27, ts, {"pelvis": 0.7, "thigh.R": 0.15,
                 "thigh.L": 0.15}, jitter=rj)
    g.bridge(bot, top, "tutu", "tutu", g.island(2 * math.pi * 0.25, 0.2), 0.0, 1.0)            # outside: out + up

    def inset(i):
        c = V3(0, -0.005, g.v[i].z)
        return c + (g.v[i] - c) * 0.97
    top2 = [g.vert(inset(i), g.w[i]) for i in top]
    bot2 = [g.vert(inset(i), g.w[i]) for i in bot]
    g.bridge(top2, bot2, "tutu", "tutu", g.island(2 * math.pi * 0.25, 0.2), 0.0, 1.0)          # inside: in + down
    # fuzzy leg warmers (near): jittered tubes over the shins
    if near:
        fz = [0.18, -0.12, 0.22, -0.05, 0.15, -0.15, 0.2, -0.08]
        for s, n in ((1, "R"), (-1, "L")):
            kn, an = J[f"knee.{n}"], J[f"ankle.{n}"]
            limb(g, [kn.lerp(an, 0.12), kn.lerp(an, 0.55), an + V3(0, 0, 0.0)], [0.072, 0.078, 0.075],
                 [{f"shin.{n}": 0.85, f"thigh.{n}": 0.15}, {f"shin.{n}": 1.0}, {f"shin.{n}": 0.6, f"foot.{n}": 0.4}], 8,
                 "warmers", ["warmer", "warmer"], jitter=fz)
    # glow necklace
    ns = d["neck_segs"]
    r1 = g.ring(V3(0, -0.002, 1.483), V3(1, 0, 0), V3(0, 1, 0), 0.088, 0.084, 0.076, ns, {"spine2": 0.7, "neck": 0.3},
                shape=lambda p, a: p + V3(0, 0, -0.058 * max(0.0, math.sin(a)) ** 1.5))
    r2 = [g.vert(g.v[i] + V3(0, 0, 0.012), g.w[i]) for i in r1]
    g.bridge(r1, r2, "necklace", "glow_necklace", g.island(0.5, 0.02), 0.0, 1.0)
    # LED gloves: glowing fingertips on both hands
    for n in "RL":
        fi, wr = J[f"fingers.{n}"], J[f"wrist.{n}"]
        hd = (fi - wr).normalized()
        if near:                                                        # glowing fingertips: the last 6.5 cm
            g.box(fi - hd * 0.032, (0.041, 0.066, 0.088), hand_rot(n), "gloves", "glow_glove", {f"hand.{n}": 1.0},
                  taper=(0.82, 0.9))
        else:
            quad2(g, [fi + V3(-0.03, 0.02, 0.02), fi + V3(0.03, 0.02, 0.02), fi + V3(0.03, 0.02, -0.03), fi + V3(-0.03, 0.02, -0.03)],
                  "gloves", "glow_glove", {f"hand.{n}": 1.0}, V3(0, 1, 0))
    # light-up shoes: a glowing strip around each sole
    for n in "RL":                                                      # a strip just outside each sole box
        an = J[f"ankle.{n}"]
        cy, hx, hy, z0, z1 = (0.035, 0.053, 0.1415, 0.004, 0.03) if near else (0.03, 0.051, 0.134, 0.004, 0.034)
        loop = [V3(an.x + hx, cy - hy, 0), V3(an.x + hx * 0.87, cy + hy, 0), V3(an.x - hx * 0.87, cy + hy, 0),
                V3(an.x - hx, cy - hy, 0)]
        a0 = [g.vert(q + V3(0, 0, z0), {f"foot.{n}": 1.0}) for q in loop]
        a1 = [g.vert(q + V3(0, 0, z1), {f"foot.{n}": 1.0}) for q in loop]
        g.bridge(a0, a1, "lightshoes", "glow_shoe", g.island(0.8, 0.03), 0.0, 1.0)
    # phone upright above the right fist: screen toward the person, flash toward the stage
    pc = gR + V3(0, 0.0, 0.11)
    g.box(pc, (0.072, 0.012, 0.15), Matrix.Identity(3), "phone", "phone", hwR)
    g.face_toward([g.vert(pc + V3(x, -0.0065, z), hwR) for x, z in ((-0.031, -0.065), (0.031, -0.065), (0.031, 0.068), (-0.031, 0.068))],
                  V3(0, -1, 0), "phone", "glow_screen")
    g.face_toward([g.vert(pc + V3(x, 0.0065, z), hwR) for x, z in ((0.006, 0.03), (0.03, 0.03), (0.03, 0.062), (0.006, 0.062))],
                  V3(0, 1, 0), "phone", "glow_flash")
    # glowstick (continues the hand)
    limb(g, [gR + hdR * 0.02, gR + hdR * 0.24], [0.011, 0.011], [hwR, hwR], 4, "glowstick", ["glow_stick"],
         cap_end=True, cap_start=True)
    # LED fan: a half-disc above the right fist (spins in "flow")
    fan = [gR + V3(0, 0.01, 0.04)] + [gR + V3(0.26 * math.cos(math.radians(a)), 0.01, 0.04 + 0.26 * math.sin(math.radians(a)))
                                      for a in range(15, 166, 30 if near else 50)]
    for side in (1, -1):
        for k in range(1, len(fan) - 1):
            pts = [fan[0], fan[k], fan[k + 1]]
            g.face_toward([g.vert(p + V3(0, side * 0.002, 0), {"prop.R": 1.0}) for p in pts], V3(0, side, 0), "fan", "glow_fan")
    # staff: a stick through the right fist with glowing ends (spins in "flow")
    pw = {"prop.R": 1.0}
    limb(g, [gR + V3(-0.55, 0.0, 0.0), gR + V3(0.55, 0.0, 0.0)], [0.012, 0.012], [pw, pw], 4, "staff", ["staff"])
    for s in (1, -1):
        g.octa(gR + V3(s * 0.58, 0, 0), 0.05, "staff", "glow_staff", pw)
    # poi: glowing balls swinging from both fists (orbit in "flow")
    for n in "RL":
        g.octa(J[f"grip.{n}"] + V3(0, 0.02, -0.48), 0.06, "poi", "glow_poi", {f"prop.{n}": 1.0})
    # LED hoop around the waist (orbits in "flow"): a flat band, two-sided
    hs = d["hoop_segs"]
    h0 = g.ring(V3(0, 0, 1.0), V3(1, 0, 0), V3(0, 1, 0), 0.46, 0.46, 0.46, hs, {"hoop": 1.0})
    h1 = [g.vert(g.v[i] + V3(0, 0, 0.028), g.w[i]) for i in h0]
    g.bridge(h0, h1, "hoop", "glow_hoop", g.island(2.9, 0.03), 0.0, 1.0)                     # outside band
    h2 = [g.vert(V3(g.v[i].x * 0.985, g.v[i].y * 0.985, g.v[i].z), g.w[i]) for i in h0]
    h3 = [g.vert(g.v[i] + V3(0, 0, 0.028), g.w[i]) for i in h2]
    g.bridge(h3, h2, "hoop", "glow_hoop", g.island(2.9, 0.03), 0.0, 1.0)                     # inside band
    # totem pole upright through the right fist + flag / LED sign / skull / pumpkin / bat cut-out on top
    top_ = gR + V3(0, 0, 1.95)
    limb(g, [gR + V3(0, 0, -0.25), top_], [0.016, 0.014], [hwR, hwR], d["pole_segs"], "pole", ["pole"], cap_end=True)
    for z0, z1, reg in ((0.0, -0.32, "flag1"), (-0.32, -0.62, "flag2")):
        q = [top_ + V3(dx, 0, dz) for dx, dz in ((0.02, z0), (0.95, z0 - 0.04), (0.95, z1 - 0.04), (0.02, z1))]
        quad2(g, q, "flag", reg, hwR, V3(0, 1, 0))
    g.box(top_ + V3(0, 0, -0.30), (0.62, 0.025, 0.46), Matrix.Identity(3), "sign", "sign", hwR)
    for side in (1, -1):
        y = side * 0.0135
        for (x0, z0, x1, z1) in ((-0.31, 0.21, 0.31, 0.25), (-0.31, -0.25, 0.31, -0.21), (-0.31, -0.21, -0.27, 0.21),
                                 (0.27, -0.21, 0.31, 0.21)):
            g.face_toward([g.vert(top_ + V3(x, y, -0.30 + z), hwR) for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1))],
                          V3(0, side, 0), "sign", "glow_led")
    # skull totem: a cranium, a jaw, glowing eye sockets (glow), a dark nose and a teeth line
    sk = top_ + V3(0, 0, 0.30)

    def skdeform(u, p):
        q = p.copy()
        if u.z < -0.2 and u.y > 0.0:                                  # the face narrows toward the cheekbones
            q.x = sk.x + (q.x - sk.x) * (1 - 0.18 * min(1.0, (-0.2 - u.z) / 0.6))
        return q
    g.ellipsoid(sk, (0.19, 0.21, 0.20), d["skull_segs"], d["skull_rings"], "skull", "skull", hwR, deform=skdeform)
    g.box(top_ + V3(0, 0.075, 0.12), (0.19, 0.16, 0.10), Matrix.Identity(3), "skull", "skull", hwR, taper=(0.9, 0.85))
    for s_ in (1, -1):
        glyph(g, ["skull"], [(sk.x + s_ * 0.025, sk.z - 0.005), (sk.x + s_ * 0.112, sk.z - 0.005),
                             (sk.x + s_ * 0.105, sk.z + 0.06), (sk.x + s_ * 0.032, sk.z + 0.06)], hwR, "skull",
              "glow_skull", lift=0.006)
    glyph(g, ["skull"], [(sk.x - 0.022, sk.z - 0.075), (sk.x + 0.022, sk.z - 0.075), (sk.x, sk.z - 0.03)], hwR, "skull",
          "skull_dark")
    glyph(g, ["skull"], [(sk.x - 0.07, top_.z + 0.125), (sk.x + 0.07, top_.z + 0.125), (sk.x + 0.07, top_.z + 0.14),
                         (sk.x - 0.07, top_.z + 0.14)], hwR, "skull", "skull_dark")
    # pumpkin totem: a big jack-o-lantern on the pole
    pumpkin(g, top_ + V3(0, 0, 0.27), (0.30, 0.27, 0.24), d["ptotem_segs"], d["ptotem_rings"], d["pumpkin_rib"], "ptotem",
            hwR, d["detail"], stem_segs=d["stem_segs"], reg="ptotem", reg2="ptotem2", face_reg="glow_ptotem")
    # bat cut-out (two-sided)
    bat = [(-0.05, 0.12), (0.0, 0.07), (0.05, 0.12), (0.07, 0.03), (0.26, 0.10), (0.46, 0.05), (0.33, -0.03),
           (0.22, -0.01), (0.12, -0.09), (0.0, -0.06), (-0.12, -0.09), (-0.22, -0.01), (-0.33, -0.03), (-0.46, 0.05),
           (-0.26, 0.10), (-0.07, 0.03)]
    for side in (1, -1):
        g.face_toward([g.vert(top_ + V3(x * 1.3, side * 0.006, z * 1.3 + 0.05), hwR) for x, z in bat], V3(0, side, 0),
                      "cutout", "cutout")
    # jack-o-lantern bucket hanging from the left fist (+ a handle near): an orange pail with a glowing face
    hwL_ = {"hand.L": 1.0}
    gL_ = J["grip.L"]
    bc = gL_ + (J["fingers.L"] - J["wrist.L"]).normalized() * 0.165 + V3(-0.01, 0, 0)
    g.ellipsoid(bc, (0.10, 0.10, 0.085), d["bucket_segs"], d["bucket_rings"], "bucket",
                lambda c: "bucket2" if c.z > bc.z + 0.04 else "bucket", hwL_)
    if near:
        limb(g, [bc + V3(0.085, 0, 0.05), gL_ + V3(0, 0, 0.01), bc + V3(-0.085, 0, 0.05)], [0.006] * 3, [hwL_] * 3, 3,
             "bucket", ["bucket2", "bucket2"])
        polys = [[(-0.055, 0.005), (-0.015, 0.005), (-0.035, 0.035)], [(0.015, 0.005), (0.055, 0.005), (0.035, 0.035)],
                 [(-0.05, -0.02), (0.05, -0.02), (0.035, -0.045), (-0.035, -0.045)]]
    else:
        polys = [[(-0.045, -0.035), (0.045, -0.035), (0.045, 0.03), (-0.045, 0.03)]]
    for poly in polys:
        glyph(g, ["bucket"], [(bc.x + x, bc.z + z) for x, z in poly], hwL_, "bucket", "glow_bucket", lift=0.005)
    # inflatable T-rex suit (mid tier only: it reads from 12-20 m): body, head + jaw, tail, tiny arms
    if not near:
        sw_ = {"spine1": 0.5, "spine2": 0.5}
        g.ellipsoid(V3(0, 0.04, 1.18), (0.36, 0.40, 0.52), 8, 5, "trex", "trex", sw_)
        th, thr = V3(0, 0.36, 1.99), (0.19, 0.34, 0.17)
        g.ellipsoid(th, thr, 8, 4, "trex", lambda c_: "trex3" if c_.z < th.z - 0.07 and c_.y > th.y else "trex",
                    {"head": 1.0})                                      # the mouth (dark) under the snout
        g.box(V3(0, 0.40, 1.79), (0.26, 0.42, 0.07), Matrix.Rotation(math.radians(-22), 3, "X"), "trex", "trex2",
              {"head": 1.0})                                            # the lower jaw, open
        limb(g, [V3(0, 0.15, 1.62), V3(0, 0.28, 1.86)], [0.16, 0.14], [{"spine2": 1.0}, {"head": 1.0}], 6, "trex", ["trex"])
        for x in (-0.10, -0.05, 0.0, 0.05, 0.10):                      # teeth along the upper jaw
            glyph(g, ["trex"], [(x - 0.018, 1.905), (x + 0.018, 1.905), (x, 1.872)], {"head": 1.0}, "trex", "trex2")
        for s in (1, -1):                                               # eyes: white, a dark pupil on top
            glyph(g, ["trex"], [(s * 0.10 + 0.035 * math.cos(a), 2.05 + 0.03 * math.sin(a))
                                for a in (0.0, 1.05, 2.1, 3.14, 4.19, 5.24)], {"head": 1.0}, "trex", "trex2")
            glyph(g, ["trex"], [(s * 0.10 - 0.012, 2.038), (s * 0.10 + 0.012, 2.038), (s * 0.10 + 0.012, 2.062),
                                (s * 0.10 - 0.012, 2.062)], {"head": 1.0}, "trex", "trex3", lift=0.009)
        limb(g, [V3(0, -0.30, 0.95), V3(0, -0.80, 0.70), V3(0, -1.15, 0.45)], [0.22, 0.12, 0.03],
             [{"pelvis": 1.0}] * 3, 6, "trex", ["trex", "trex"], cap_start=True, cap_end=True)
        for s in (1, -1):                                               # the tiny arms, reaching forward
            limb(g, [V3(s * 0.26, 0.30, 1.34), V3(s * 0.30, 0.50, 1.25), V3(s * 0.28, 0.57, 1.14)], [0.05, 0.035, 0.02],
                 [{"spine2": 1.0}] * 3, 4, "trex", ["trex", "trex"], cap_end=True)
        for s in (1, -1):                                               # its legs: big puffy tubes over the person's legs
            n = "R" if s > 0 else "L"
            limb(g, [J[f"hip.{n}"] + V3(0, 0, -0.05), J[f"knee.{n}"], J[f"ankle.{n}"] + V3(0, 0, 0.05)], [0.15, 0.12, 0.10],
                 [{f"thigh.{n}": 1.0}, {f"thigh.{n}": 0.5, f"shin.{n}": 0.5}, {f"shin.{n}": 1.0}], 6, "trex",
                 ["trex", "trex"], cap_end=True)


def add_costume_body(g, d):
    """Costume pieces worn on the body: the ghost sheet, skeleton bone strips, the vampire collar, cat / devil tails."""
    near = d["detail"] == "near"
    # ---- ghost: a sheet from a dome over the head to a ragged hem below the knees, with eye holes (+ a mouth near).
    # Ghosts drop the torso, the head and the hair (the sheet reuses the torso island); the arms stay, sheet-coloured.
    segs = d["sheet_segs"]
    ph = math.pi / segs

    def shoulder_w(p):
        w = {"spine2": 1.0}
        if abs(p.x) > 0.09:
            w = lerpw(w, {"clav.R" if p.x > 0 else "clav.L": 1.0}, 0.5)
        return w

    def leg_w(k_pelvis):
        def w(p):
            s_ = min(1.0, max(0.0, 0.5 + p.x / 0.2))
            return {"pelvis": k_pelvis, "thigh.R": (1 - k_pelvis) * s_, "thigh.L": (1 - k_pelvis) * (1 - s_)}
        return w
    spec = [(0.420, 0.340, 0.255, 0.245, leg_w(0.55), True), (0.620, 0.310, 0.225, 0.215, leg_w(0.75), False),
            (0.900, 0.280, 0.200, 0.190, {"pelvis": 1.0}, False),
            (1.150, 0.255, 0.180, 0.165, {"spine1": 0.5, "spine2": 0.5}, False),
            (1.420, 0.270, 0.170, 0.160, shoulder_w, False), (1.640, 0.122, 0.135, 0.130, {"head": 1.0}, False),
            (1.750, 0.085, 0.100, 0.095, {"head": 1.0}, False)]
    rings = []
    for i, (z, rx, ryf, ryb, w, ragged) in enumerate(spec):
        if i not in d["sheet_keep"]:
            continue
        shape = (lambda p, a: p + V3(0, 0, 0.028 * math.cos(segs * (a - ph) / 2))) if ragged else None
        rings.append(g.ring(V3(0, 0.004 if z > 1.5 else -0.005, z), V3(1, 0, 0), V3(0, 1, 0), rx, ryf, ryb, segs, w,
                            phase=ph, shape=shape))
    pole = g.vert(V3(0, 0.004, 1.795), {"head": 1.0})
    isl, nr = g.named["torso"], len(rings)
    for k in range(nr - 1):
        g.bridge(rings[k], rings[k + 1], "ghost", "sheet", isl, k / nr, (k + 1) / nr)
    for j in range(segs):
        g.face((rings[-1][j], rings[-1][(j + 1) % segs], pole), "ghost", "sheet",
               ((j / segs, (nr - 1) / nr), ((j + 1) / segs, (nr - 1) / nr), ((j + 0.5) / segs, 1.0)), isl)
    eye = ([(-0.017, 0.0), (-0.009, -0.026), (0.009, -0.026), (0.017, 0.0), (0.009, 0.026), (-0.009, 0.026)] if near
           else [(-0.016, -0.024), (0.016, -0.024), (0.016, 0.024), (-0.016, 0.024)])
    for s in (1, -1):
        glyph(g, ["ghost"], [(s * 0.046 + x, 1.668 + z) for x, z in eye], {"head": 1.0}, "ghost", "sheet_dark")
    if near:
        glyph(g, ["ghost"], [(x, 1.588 + z) for x, z in ((-0.02, -0.018), (0.02, -0.018), (0.024, 0.0), (0.02, 0.018),
                                                          (-0.02, 0.018), (-0.024, 0.0))],
              {"spine2": 0.25, "head": 0.75}, "ghost", "sheet_dark")
    # ---- skeleton: white bone strips over the black suit (ribs, arm and leg bones; near: sternum, pelvis, a nose),
    # dark eye sockets. Strips are projected onto the body 4 mm out and carry its weights.

    def torso_strip(center, half, vertical):
        rows = []
        for sg in (1, -1):
            row = []
            for x, z in center:
                px, pz = (x, z + sg * half) if vertical else (x + sg * half, z)
                q = g.surface(["b_torso"], V3(px, 1.0, pz), V3(0, -1, 0))
                row.append(g.vert(q, torso_w(q.z)))
            rows.append(row)
        f0 = len(g.f)
        for k in range(len(center) - 1):
            g.face_toward((rows[0][k], rows[0][k + 1], rows[1][k + 1], rows[1][k]), V3(0, 1, 0), "bones", "bone")
        g.clear_out(range(f0, len(g.f)), ["b_torso"])

    def limb_strip(rig, t0, t1, half, part):
        pts, wts = rig
        lens = [0.0]
        for a_, b_ in zip(pts, pts[1:]):
            lens.append(lens[-1] + (b_ - a_).length)

        def at(t):
            x = t * lens[-1]
            i = max(k for k in range(len(pts) - 1) if lens[k] <= x)
            u = (x - lens[i]) / max(lens[i + 1] - lens[i], 1e-6)
            return pts[i].lerp(pts[i + 1], u), lerpw(wts[i], wts[i + 1], u), (pts[i + 1] - pts[i]).normalized()
        quad = []
        front = V3(0, 1, 0)
        for t, order in ((t0, (-1, 1)), (t1, (1, -1))):
            c, w, ax = at(t)
            front = (V3(0, 1, 0) - ax * ax.y).normalized()
            side = ax.cross(front).normalized()
            for sg in order:
                o = c + side * (sg * half)
                quad.append(g.vert(g.surface([part], o + front * 0.3, -front), w))
        g.face_toward(quad, front, "bones", "bone")
        g.clear_out([len(g.f) - 1], [part])
    for z_, dz, xo in d["ribs"]:
        for s in (1, -1):
            torso_strip([(s * x, z_ - dz * k) for k, x in enumerate(xo)], d["rib_half"], True)
    for n in "RL":
        limb_strip(g.named["arm." + n], 0.10, 0.44, 0.011, "b_arms")
        limb_strip(g.named["arm." + n], 0.58, 0.92, 0.010, "b_arms")
        limb_strip(g.named["leg." + n], 0.08, 0.45, 0.014, "b_legs")
        limb_strip(g.named["leg." + n], 0.58, 0.90, 0.012, "b_legs")
    hw = {"head": 1.0}
    if near:
        torso_strip([(0.0, 1.12), (0.0, 1.24), (0.0, 1.36)], 0.011, False)                      # sternum
        for s in (1, -1):                                                                       # pelvis, sockets
            glyph(g, ["b_torso"], [(s * 0.04, 0.945), (s * 0.13, 0.955), (s * 0.115, 0.895), (s * 0.05, 0.875)],
                  {"pelvis": 1.0}, "bones", "bone")
            glyph(g, ["b_head"], [(s * 0.033 + 0.016 * math.cos(a), 1.646 + 0.015 * math.sin(a))
                                  for a in (0.0, 1.05, 2.1, 3.14, 4.19, 5.24)], hw, "bones", "bone_dark")
        glyph(g, ["b_head"], [(-0.011, 1.606), (0.011, 1.606), (0.0, 1.626)], hw, "bones", "bone_dark")
    else:
        for s in (1, -1):
            glyph(g, ["b_head"], [(s * 0.008, 1.636), (s * 0.032, 1.636), (s * 0.032, 1.662), (s * 0.008, 1.662)], hw,
                  "bones", "bone_dark")
    # ---- vampire collar: tall and stiff behind the neck, flaring out (two-sided: black outside, red inside)
    nc = 4 if near else 3
    base = [V3(0.115 * math.cos(a), -0.01 + 0.10 * math.sin(a), 1.445)
            for a in (math.radians(205 + 130 * k / (nc - 1)) for k in range(nc))]
    top = [V3(0.20 * math.cos(a), -0.01 + 0.16 * math.sin(a), 1.665)
           for a in (math.radians(195 + 150 * k / (nc - 1)) for k in range(nc))]
    for side, reg in ((1, "collar"), (-1, "collar2")):
        inward = 0.0 if side > 0 else 0.003
        bv = [g.vert(p - V3(p.x, p.y + 0.01, 0).normalized() * inward, {"spine2": 1.0}) for p in base]
        tv = [g.vert(p - V3(p.x, p.y + 0.01, 0).normalized() * inward, {"spine2": 0.7, "neck": 0.3}) for p in top]
        isl = g.island(0.5, 0.22)
        for k in range(nc - 1):
            q = (bv[k], bv[k + 1], tv[k + 1], tv[k])
            c = sum((g.v[i] for i in q), Vector()) / 4
            uv = ((k / (nc - 1), 0.0), ((k + 1) / (nc - 1), 0.0), ((k + 1) / (nc - 1), 1.0), (k / (nc - 1), 1.0))
            g.face_toward(q, V3(c.x, c.y + 0.01, 0) * side, "collar", reg, uv, isl)
    # ---- cat / devil tail from the tailbone: down, out and curling up; a two-sided devil spade at the tip
    tp = [V3(0, -0.10, 0.93), V3(0, -0.20, 0.80), V3(0.02, -0.28, 0.62), V3(0.06, -0.33, 0.48), V3(0.10, -0.36, 0.52)]
    trd = [0.022, 0.020, 0.017, 0.014, 0.010]
    tp, trd = [tp[i] for i in d["tail_keep"]], [trd[i] for i in d["tail_keep"]]
    limb(g, tp, trd, [{"pelvis": 1.0}] * len(tp), d["tail_segs"], "tail", ["tail"] * (len(tp) - 1), cap_end=True)
    tip = tp[-1]
    quad2(g, [tip + V3(0.0, 0, -0.03), tip + V3(0.04, 0, 0.02), tip + V3(0.0, 0, 0.075), tip + V3(-0.04, 0, 0.02)],
          "tail_spade", "tail2", {"pelvis": 1.0}, V3(0, -1, 0))


def add_far_body(g):
    """~21 tris: a 3-sided column (feet -> hips -> shoulders, a flat face to the stage), a pyramid head, two arm ribbons;
    plus a pole + flag (holders) and glow quads at the hand, the chest and above the head."""
    col = [(0.02, 0.15, 0.09, {"foot.R": 0.5, "foot.L": 0.5}), (0.90, 0.17, 0.10, {"pelvis": 1.0}),
           (1.44, 0.16, 0.08, {"spine2": 1.0})]
    rings = [g.ring(V3(0, 0, z), V3(1, 0, 0), V3(0, 1, 0), rx, ry, ry, 3, w, phase=math.pi / 6) for z, rx, ry, w in col]
    zs = [c_[0] for c_ in col]
    cisl = g.island(2 * (0.32 + 0.18), zs[-1] - zs[0])
    vz = [(z - zs[0]) / (zs[-1] - zs[0]) for z in zs]
    for i, reg in enumerate(("thigh", "chest")):
        g.bridge(rings[i], rings[i + 1], "b_torso", reg, cisl, vz[i], vz[i + 1])
    g.cap(rings[-1], "b_torso", "shoulders", isl=cisl, v=1.0)
    hc = V3(0, 0.01, 1.62)
    top = g.vert(hc + V3(0, 0, 0.13), {"head": 1.0})
    eq = [g.vert(hc + V3(0.09 * math.cos(a_), 0.1 * math.sin(a_), -0.08), {"head": 1.0})
          for a_ in (math.pi / 2, math.pi / 2 + 2.094, math.pi / 2 + 4.189)]
    hisl = g.island(2 * math.pi * 0.095, 0.23)
    for k in range(3):
        out = (g.v[eq[k]] + g.v[eq[(k + 1) % 3]]) / 2 - hc
        g.face_toward((top, eq[k], eq[(k + 1) % 3]), out, "b_head", "scalp" if k else "face",
                      ((0.5, 1.0), (k / 3, 0.0), ((k + 1) / 3, 0.0)), hisl)
    g.face_toward(eq, V3(0, 0, -1), "b_head", "face", ((0.0, 0.0), (0.5, 0.0), (1.0, 0.0)), hisl)
    for s_, n in ((1, "R"), (-1, "L")):
        sh, fi = J[f"shoulder.{n}"], J[f"fingers.{n}"]
        q = [g.vert(sh + V3(-0.035, 0.02, 0), {f"upperarm.{n}": 1.0}), g.vert(sh + V3(0.035, 0.02, 0), {f"upperarm.{n}": 1.0}),
             g.vert(fi + V3(0.03, 0.02, 0), {f"hand.{n}": 1.0}), g.vert(fi + V3(-0.03, 0.02, 0), {f"hand.{n}": 1.0})]
        g.face_toward(q, V3(0, 1, 0), "b_arms", "sleeve_mid")
    hw = {"hand.R": 1.0}
    grip = J["fingers.R"]
    top_ = grip + V3(0, 0, 1.95)
    g.face_toward([g.vert(grip + V3(dx, 0.02, dz), hw) for dx, dz in ((-0.02, -0.2), (0.02, -0.2), (0.02, 1.95), (-0.02, 1.95))],
                  V3(0, 1, 0), "pole", "pole")
    g.face_toward([g.vert(top_ + V3(dx, 0.02, dz), hw) for dx, dz in ((0.02, 0.0), (0.9, -0.05), (0.9, -0.6), (0.02, -0.55))],
                  V3(0, 1, 0), "flag", "flag1")
    g.face_toward([g.vert(grip + V3(dx, 0.025, dz), hw) for dx, dz in ((-0.035, -0.02), (0.035, -0.02), (0.035, 0.12), (-0.035, 0.12))],
                  V3(0, 1, 0), "far_hand", "glow_hand")
    g.face_toward([g.vert(V3(dx, 0.115, dz), {"spine2": 1.0}) for dx, dz in ((-0.09, 1.38), (0.09, 1.38), (0.09, 1.43), (-0.09, 1.43))],
                  V3(0, 1, 0), "far_chest", "glow_chest")
    g.face_toward([g.vert(hc + V3(dx, 0.06, dz), {"head": 1.0}) for dx, dz in ((-0.09, 0.10), (0.09, 0.10), (0.11, 0.17), (-0.11, 0.17))],
                  V3(0, 1, 0), "far_head", "glow_head")
    hw_ = {"head": 1.0}
    g.face_toward([g.vert(hc + V3(dx, 0.17, dz), hw_) for dx, dz in ((-0.065, -0.045), (0.065, -0.045), (0.065, 0.035),
                                                                     (-0.065, 0.035))],
                  V3(0, 1, 0), "far_face", "glow_face")                 # jack-o-lantern face, LED mask, glowing eyes
    ptop, pbot = g.vert(hc + V3(0, 0, 0.125), hw_), g.vert(hc + V3(0, 0, -0.105), hw_)
    angs = (0.0, math.pi / 2, math.pi, 1.5 * math.pi)
    ra = [g.vert(hc + V3(0.17 * math.cos(a), 0.155 * math.sin(a), 0.045), hw_) for a in angs]
    rb = [g.vert(hc + V3(0.17 * math.cos(a), 0.155 * math.sin(a), -0.045), hw_) for a in angs]
    for k in range(4):                                                  # the pumpkin head: 16 tris, round-ish
        a_, b_, c_, d_ = ra[k], ra[(k + 1) % 4], rb[k], rb[(k + 1) % 4]
        mid_ = (g.v[a_] + g.v[b_]) / 2 - hc
        mid_.z = 0.0
        g.face_toward((ptop, a_, b_), mid_ + V3(0, 0, 0.12), "far_pumpkin", "pumpkin")
        g.face_toward((a_, c_, d_, b_), mid_, "far_pumpkin", "pumpkin")
        g.face_toward((pbot, d_, c_), mid_ - V3(0, 0, 0.12), "far_pumpkin", "pumpkin")
    g.face_toward([g.vert(hc + V3(dx, 0.05, dz), hw_) for dx, dz in ((-0.11, 0.07), (0.11, 0.07), (0.03, 0.47))],
                  V3(0, 1, 0), "far_hat", "hat")                        # witch hat: cone + brim
    g.face_toward([g.vert(hc + V3(dx, 0.055, dz), hw_) for dx, dz in ((-0.21, 0.045), (0.21, 0.045), (0.21, 0.075),
                                                                      (-0.21, 0.075))],
                  V3(0, 1, 0), "far_hat", "hat")
    g.face_toward([g.vert(V3(dx, 0.06, dz), {"spine2": 1.0}) for dx, dz in ((-0.09, 1.12), (0.09, 1.12), (0.09, 1.34),
                                                                         (-0.09, 1.34))],
                  V3(0, 1, 0), "far_ribs", "bone")                      # skeleton ribcage
    lgrip = J["fingers.L"]
    g.face_toward([g.vert(lgrip + V3(dx, 0.03, dz), {"hand.L": 1.0}) for dx, dz in ((-0.05, -0.13), (0.05, -0.13),
                                                                                   (0.05, -0.02), (-0.05, -0.02))],
                  V3(0, 1, 0), "far_lhand", "glow_lhand")               # jack-o-lantern bucket
    g.face_toward([g.vert(top_ + V3(dx, 0.03, dz), hw) for dx, dz in ((-0.12, 0.06), (0.12, 0.06), (0.12, 0.28),
                                                                      (-0.12, 0.28))],
                  V3(0, 1, 0), "far_ttop", "glow_ttop")                 # skull eyes / pumpkin face / LED frame


DETAIL = {
    "near": {"detail": "near", "torso": 12, "torso_keep": {0, 1, 2, 3, 4, 5, 6, 7}, "neck": 8, "head_segs": 12,
             "head_rings": 8, "arm": 8, "arm_rings": 5, "leg": 8, "leg_rings": 6, "thumb": True, "hair_segs": 12,
             "hair_rings": 4, "pole_segs": 5, "face_detail": True, "hair_strands": True,
             "one_box_shoes": False, "horn_segs": 5, "tutu_segs": 14, "neck_segs": 10, "hoop_segs": 16,
             # Halloween parts
             "witch_segs": 10, "witch_cone": [(0.075, 0.088, 0.099, V3(0, -0.006, 0)), (0.24, 0.045, 0.048, V3(0.008, -0.045, 0))],
             "pumpkin_segs": 12, "pumpkin_rings": 7, "pumpkin_rib": 0.035, "stem_segs": 5, "mask_eye_x": (0.016, 0.050),
             "mask_mouth_x": 0.036, "mask_mouth_n": 3, "skull_segs": 8, "skull_rings": 4, "ptotem_segs": 8,
             "ptotem_rings": 4, "bucket_segs": 8, "bucket_rings": 3, "sheet_segs": 12, "sheet_keep": {0, 1, 2, 3, 4, 5, 6},
             "tail_segs": 5, "tail_keep": (0, 1, 2, 3, 4), "rib_half": 0.009,
             "ribs": [(1.315, 0.015, (0.028, 0.08, 0.128)), (1.245, 0.015, (0.028, 0.08, 0.128)),
                      (1.175, 0.015, (0.028, 0.08, 0.128))]},
    "mid": {"detail": "mid", "torso": 6, "torso_keep": {0, 1, 3, 4, 6, 7}, "neck": 0, "head_segs": 6, "head_rings": 4,
            "arm": 4, "arm_rings": 3, "leg": 4, "leg_rings": 3, "thumb": False, "hair_segs": 6, "hair_rings": 2,
            "pole_segs": 3, "face_detail": False, "hair_strands": False, "one_box_shoes": True,
            "horn_segs": 3, "tutu_segs": 8, "neck_segs": 6, "hoop_segs": 10,
            "witch_segs": 6, "witch_cone": [(0.075, 0.088, 0.099, V3(0, -0.006, 0))],
            "pumpkin_segs": 6, "pumpkin_rings": 4, "pumpkin_rib": 0.0, "stem_segs": 3, "mask_eye_x": (0.006, 0.031),
            "mask_mouth_x": 0.028, "mask_mouth_n": 1, "skull_segs": 6, "skull_rings": 3, "ptotem_segs": 6,
            "ptotem_rings": 3, "bucket_segs": 6, "bucket_rings": 2, "sheet_segs": 6, "sheet_keep": {0, 2, 4, 5},
            "tail_segs": 3, "tail_keep": (0, 2, 4), "rib_half": 0.012,
            "ribs": [(1.30, 0.025, (0.03, 0.125)), (1.20, 0.025, (0.03, 0.125))]},
}
BODY_PARTS = ("b_torso", "b_head", "b_arms", "b_legs")
OPTIONAL_PARTS = ("hair", "hair_long", "hair_pony", "hair_bun", "hair_braids", "hat_dome", "hat_brim", "hat_pom",
                  "hat_bucket", "hat_cowboy", "witch_hat", "witch_band", "crown", "goggles", "horns", "ears", "mask_led",
                  "glow_eyes", "pumpkin", "ghost", "bones", "collar", "tail", "tail_spade", "pack", "cape", "tutu",
                  "warmers", "necklace", "gloves", "lightshoes", "phone", "glowstick", "bucket", "fan", "staff", "poi",
                  "hoop", "pole", "flag", "sign", "skull", "ptotem", "cutout", "trex", "far_hand", "far_chest",
                  "far_head", "far_face", "far_hat", "far_pumpkin", "far_ribs", "far_lhand", "far_ttop")
PARTS = BODY_PARTS + OPTIONAL_PARTS
PART = {p: i for i, p in enumerate(PARTS)}
TOTEM_PARTS = ("pole", "flag", "sign", "skull", "ptotem", "cutout")
HAIR_PARTS = ("hair", "hair_long", "hair_pony", "hair_bun", "hair_braids")
FAR_BILLBOARDS = ("b_arms", "pole", "flag", "far_hand", "far_chest", "far_head", "far_face", "far_hat", "far_ribs",
                  "far_lhand", "far_ttop")                       # one-sided quads (far tier)


def build_canonical(tier):
    g = Geo()
    if tier == "far":
        add_far_body(g)
    else:
        add_body(g, DETAIL[tier])
        add_head_wear(g, DETAIL[tier])
        add_items(g, DETAIL[tier])
        add_costume_body(g, DETAIL[tier])
    return g


# ============================================================================ dances
# Each bone gets G = its rest->pose deformation in canonical space (posed point = G @ rest point); a child is its
# parent's G times a rotation about its own rest joint, so every rotation below is written in rest-pose world axes.
# Lean forward = Rx(-deg); tilt toward +X = Ry(+deg); twist toward -X = Rz(+deg).
def Tm(v):
    return Matrix.Translation(v)


def about(pivot, r3):
    return Tm(pivot) @ r3.to_4x4() @ Tm(-pivot)


def Rx(deg):
    return Matrix.Rotation(math.radians(deg), 3, "X")


def Ry(deg):
    return Matrix.Rotation(math.radians(deg), 3, "Y")


def Rz(deg):
    return Matrix.Rotation(math.radians(deg), 3, "Z")


def _leg(g, n, lift=0.0, dx=0.0, dy=0.0, toe=0.0):
    """Two-bone IK: the hip follows the pelvis, the ankle goes to its rest spot (+dx, +dy, +lift), knees bend forward."""
    hip0, knee0, ank0 = J[f"hip.{n}"], J[f"knee.{n}"], J[f"ankle.{n}"]
    hip1, ank1 = g["pelvis"] @ hip0, ank0 + V3(dx, dy, lift)
    l1, l2 = (knee0 - hip0).length, (ank0 - knee0).length
    dv = ank1 - hip1
    d = min(dv.length, l1 + l2 - 1e-4)
    u = dv.normalized()
    a = math.acos(max(-1.0, min(1.0, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d))))
    knee1 = hip1 + (Matrix.Rotation(a, 3, u.cross(V3(0, 1, 0)).normalized()) @ u) * l1
    rt = (knee0 - hip0).normalized().rotation_difference((knee1 - hip1).normalized()).to_matrix()
    rs = (ank0 - knee0).normalized().rotation_difference((ank1 - knee1).normalized()).to_matrix()
    g[f"thigh.{n}"] = Tm(hip1) @ rt.to_4x4() @ Tm(-hip0)
    g[f"shin.{n}"] = Tm(knee1) @ rs.to_4x4() @ Tm(-knee0)
    g[f"foot.{n}"] = Tm(ank1) @ Rx(toe).to_4x4() @ Tm(-ank0)


def _leg_sit(g, n, spread=28.0, lift=84.0, knee=86.0):
    """Sitting on someone's shoulders: thigh forward and out, shin hanging down."""
    s = 1 if n == "R" else -1
    g[f"thigh.{n}"] = g["pelvis"] @ about(J[f"hip.{n}"], Rz(-s * spread) @ Rx(lift))
    g[f"shin.{n}"] = g[f"thigh.{n}"] @ about(J[f"knee.{n}"], Rx(-knee))
    g[f"foot.{n}"] = g[f"shin.{n}"] @ about(J[f"ankle.{n}"], Rx(25))


def _arm(g, n, elev, splay, flex, shrug=0.0, twist=0.0, wrist=0.0, upright=None):
    """elev: raise forward/up about X (0 hanging, 180 straight up); splay: outward about Y; flex: elbow bend.
    upright=(rock deg) keeps the hand's world orientation upright (pole / phone holders) instead of following the arm."""
    s = 1 if n == "R" else -1
    g[f"clav.{n}"] = g["spine2"] @ about(J[f"clav.{n}"], Ry(-s * shrug))
    g[f"upperarm.{n}"] = g[f"clav.{n}"] @ about(J[f"shoulder.{n}"], Ry(s * splay) @ Rx(elev) @ Rz(s * twist))
    g[f"forearm.{n}"] = g[f"upperarm.{n}"] @ about(J[f"elbow.{n}"], Rx(flex))
    if upright is None:
        g[f"hand.{n}"] = g[f"forearm.{n}"] @ about(J[f"wrist.{n}"], Rx(wrist))
    else:
        w1 = g[f"forearm.{n}"] @ J[f"wrist.{n}"]
        g[f"hand.{n}"] = Tm(w1) @ Ry(s * upright).to_4x4() @ Tm(-J[f"wrist.{n}"])


def _trunk(g, off=V3(0, 0, 0), pelvis=None, s1=None, s2=None, neck=None, head=None):
    I3 = Matrix.Identity(3)
    g["pelvis"] = Tm(off) @ about(J["pelvis"], pelvis or I3)
    g["spine1"] = g["pelvis"] @ about(J["spine1"], s1 or I3)
    g["spine2"] = g["spine1"] @ about(J["spine2"], s2 or I3)
    g["neck"] = g["spine2"] @ about(J["neck"], neck or I3)
    g["head"] = g["neck"] @ about(J["head"], head or I3)


def _pulse(q, at, sharp=3):
    return (0.5 + 0.5 * math.cos(2 * math.pi * (q - at))) ** sharp


def pose(clip, p):
    """G (4x4 mathutils) per bone at loop position p in [0, 1): one loop = 2 beats; q = position inside the beat."""
    q = (2.0 * p) % 1.0
    tw = 2 * math.pi
    sw = math.sin(tw * p)                                             # one sway cycle per loop
    beat = (0.5 + 0.5 * math.cos(tw * q)) ** 2                        # 1 on the beat, 0 between
    g = {}
    legs = {"R": {}, "L": {}}
    sit = False
    if clip in ("jump", "jumppump"):
        a = 0.45 if clip == "jump" else 0.4
        hop = 0.20 if clip == "jump" else 0.13
        dip = 0.11 if clip == "jump" else 0.08
        if q < a:
            air, crouch, tuck = hop * math.sin(math.pi * q / a), 0.0, 0.35 * hop * math.sin(math.pi * q / a)
        else:
            air, crouch, tuck = 0.0, dip * math.sin(math.pi * (q - a) / (1 - a)), 0.0
        k = crouch / dip
        if clip == "jump":
            _trunk(g, V3(0, -0.25 * crouch, air - crouch), s1=Rx(-5 * k), s2=Rx(-(6 * k - 2 * air / hop)), neck=Rx(-3 * k),
                   head=Rx(-4 * k))
            for n in "RL":
                _arm(g, n, 150 + 12 * math.sin(tw * q), 18, 25 + 25 * k, shrug=10)
        else:
            pump = _pulse(q, 0.1)
            _trunk(g, V3(0, -0.2 * crouch, air - crouch), s2=Rz(5 * pump) @ Rx(-5 * k), head=Rx(-(3 + 7 * pump)))
            _arm(g, "R", 100 + 68 * pump, 14, 95 - 80 * pump, shrug=8 * pump)
            _arm(g, "L", 55 + 25 * pump, 22, 75)
        for n in "RL":
            legs[n] = {"lift": air + tuck, "toe": -18 * air / hop}
    elif clip == "pump":
        pump = _pulse(q, 0.12)
        b = 0.045 * beat
        _trunk(g, V3(0, -0.2 * b, -b), s2=Rz(6 * pump) @ Rx(4 * pump), neck=Rx(-3), head=Rx(-(2 + 8 * pump)))
        _arm(g, "R", 95 + 70 * pump, 12 + 6 * pump, 100 - 85 * pump, shrug=8 * pump)
        _arm(g, "L", 14 + 6 * pump, 6, 30 + 10 * pump)
    elif clip == "handsup":                                           # the drop: hands high, head back, slow sway
        _trunk(g, V3(0.025 * sw, 0, -0.025 * beat), pelvis=Ry(2 * sw), s2=Rx(5) @ Ry(3 * sw), neck=Rx(8),
               head=Rx(9) @ Ry(4 * sw))
        _arm(g, "R", 170, 28 + 5 * sw, 10, shrug=14, wrist=-20)
        _arm(g, "L", 170, 28 - 5 * sw, 10, shrug=14, wrist=-20)
    elif clip == "wave":
        w = 22 * sw
        _trunk(g, V3(0.04 * sw, 0, -0.025 * beat), pelvis=Ry(3 * sw), s2=Ry(4 * sw), head=Ry(5 * sw))
        _arm(g, "R", 165, 12 + w, 15, shrug=10)
        _arm(g, "L", 165, 12 - w, 15, shrug=10)
    elif clip == "clap":
        c = (0.5 + 0.5 * math.cos(tw * q)) ** 3
        _trunk(g, V3(0, 0, -0.03 * c), s2=Rx(2 * c), head=Rx(-5 * c))
        for n in "RL":
            _arm(g, n, 152, 16 - 40 * c, 30 + 15 * c, shrug=8)
    elif clip == "sway":
        b = 0.03 * beat
        _trunk(g, V3(0.05 * sw, 0, -b), pelvis=Ry(4 * sw) @ Rz(6 * sw), s1=Ry(-3 * sw), s2=Ry(-3 * sw) @ Rz(-4 * sw),
               neck=Ry(3 * sw), head=Ry(4 * sw) @ Rx(-4 * beat))
        _arm(g, "R", 48 + 14 * sw, 12 + 6 * sw, 85, wrist=-10)
        _arm(g, "L", 48 - 14 * sw, 12 - 6 * sw, 85, wrist=-10)
    elif clip == "twostep":                                           # step out right, back, out left, back
        dxr = 0.11 * (0.5 - 0.5 * math.cos(tw * p))
        dxl = -0.11 * (0.5 - 0.5 * math.cos(tw * (p - 0.5)))
        lr = 0.05 * max(0.0, math.sin(tw * p))
        ll = 0.05 * max(0.0, math.sin(tw * (p - 0.5)))
        cx = (dxr + dxl) / 2
        _trunk(g, V3(cx, 0, -0.03 * beat), pelvis=Rz(-5 * sw), s2=Rz(8 * sw) @ Ry(-3 * sw) @ Rx(-3), head=Ry(5 * sw))
        _arm(g, "R", 42 + 18 * sw, 12, 95, wrist=-15)
        _arm(g, "L", 42 - 18 * sw, 12, 95, wrist=-15)
        legs["R"], legs["L"] = {"dx": dxr, "lift": lr}, {"dx": dxl, "lift": ll}
    elif clip == "shuffle":                                           # running man: one foot slides back, the other lifts
        dyr, dyl = 0.12 * math.cos(tw * p), -0.12 * math.cos(tw * p)
        lr, ll = 0.11 * max(0.0, -math.sin(tw * p)), 0.11 * max(0.0, math.sin(tw * p))
        _trunk(g, V3(0, 0.02, -0.035 * beat), s1=Rx(-4), s2=Rx(-5) @ Rz(5 * sw), head=Rx(-5 * beat))
        _arm(g, "R", 40 + 30 * max(0.0, -math.sin(tw * p)), 10, 95, wrist=-10)
        _arm(g, "L", 40 + 30 * max(0.0, math.sin(tw * p)), 10, 95, wrist=-10)
        legs["R"], legs["L"] = {"dy": dyr, "lift": lr}, {"dy": dyl, "lift": ll}
    elif clip == "headbang":
        k = _pulse(q, 0.05, 2)
        _trunk(g, V3(0, -0.02 * k, -0.045 * k), s1=Rx(-6 * k), s2=Rx(-(8 + 12 * k)), neck=Rx(-(8 + 24 * k)),
               head=Rx(-(4 + 16 * k)))
        for n in "RL":
            _arm(g, n, 140 - 28 * k, 20, 55 + 15 * k, shrug=6)
    elif clip == "nod":                                               # chill: nod, small bounce, a drink at the chest
        _trunk(g, V3(0, 0, -0.02 * beat), s2=Rz(3 * sw), head=Rx(-(3 + 9 * beat)))
        _arm(g, "R", 32, 8, 112, wrist=-20)
        _arm(g, "L", 10 + 4 * sw, 6, 20)
    elif clip == "heart":                                             # hands forming a heart above the head
        _trunk(g, V3(0.03 * sw, 0, -0.02 * beat), pelvis=Ry(2 * sw), s2=Ry(3 * sw), head=Rx(5) @ Ry(3 * sw))
        for n in "RL":
            _arm(g, n, 148, -12, 68, shrug=10, twist=-25, wrist=30)
    elif clip == "hold":                                              # totem / phone overhead, bobbing
        b = 0.035 * beat
        _trunk(g, V3(0, 0, -b), s2=Ry(-2 * sw), head=Rx(-4 * beat) @ Ry(3 * sw))
        _arm(g, "R", 168, 8 + 3 * sw, 18, shrug=12, upright=4 * sw)
        _arm(g, "L", 28 + 10 * beat, 8, 45)
    elif clip == "talk":                                              # facing a friend: gestures, nods, a laugh
        gs = math.sin(tw * 2 * p)
        _trunk(g, V3(0.015 * sw, 0, -0.012 * beat), s2=Rz(4 * sw) @ Rx(-3 + 4 * max(0.0, math.sin(tw * p + 1.0))),
               neck=Ry(8 * math.sin(tw * p + 1.0)), head=Rx(-(2 + 5 * max(0.0, gs))))
        _arm(g, "R", 38 + 18 * gs, 15, 95 + 20 * gs, twist=10, wrist=-15)
        _arm(g, "L", 20, 32, 100)
    elif clip == "carry":                                             # a friend on the shoulders: hold the shins, bob
        b = 0.03 * beat
        _trunk(g, V3(0, 0, -b), s2=Rx(-2), head=Rx(-3 * beat))
        for n in "RL":
            _arm(g, n, 78, -4, 96, shrug=6)
    elif clip == "ride":                                              # on a friend's shoulders: the same bob, wave
        b = 0.03 * beat
        _trunk(g, V3(0, 0, -b), s2=Ry(3 * sw), head=Rx(-4 * beat) @ Ry(4 * sw))
        _arm(g, "R", 168, 10, 15, shrug=12, upright=3 * sw)
        _arm(g, "L", 150 + 15 * math.sin(tw * 2 * p), 28, 20, shrug=10)
        sit = True
    elif clip == "flow":                                              # flow arts: circling arms, spinning props
        om = tw * 2 * p
        _trunk(g, V3(0.03 * sw, 0, -0.02 * beat), pelvis=Rz(5 * sw), s2=Ry(3 * sw) @ Rz(-4 * sw), head=Ry(3 * sw))
        _arm(g, "R", 95 + 45 * math.sin(om), 25 + 30 * math.cos(om), 30)
        _arm(g, "L", 95 + 45 * math.sin(om + math.pi), 25 + 30 * math.cos(om + math.pi), 30)
    elif clip == "lurch":                                             # zombie two-step: arms out front, hands hanging,
        dxr = 0.09 * (0.5 - 0.5 * math.cos(tw * p))                    # head lolling; step out right, drag back, out left
        dxl = -0.09 * (0.5 - 0.5 * math.cos(tw * (p - 0.5)))
        lr = 0.035 * max(0.0, math.sin(tw * p))
        ll = 0.035 * max(0.0, math.sin(tw * (p - 0.5)))
        _trunk(g, V3((dxr + dxl) / 2, 0.0, -0.035 * beat), pelvis=Rz(-4 * sw), s1=Rx(-6),
               s2=Rz(6 * sw) @ Ry(-5 * sw) @ Rx(-8), neck=Rx(-6), head=Ry(14 + 6 * sw) @ Rx(-8 + 6 * beat))
        for n, ph in (("R", 0.0), ("L", math.pi)):
            _arm(g, n, 84 + 9 * math.sin(tw * 2 * p + ph), 6, 12, shrug=6, wrist=-35)
        legs["R"], legs["L"] = {"dx": dxr, "lift": lr}, {"dx": dxl, "lift": ll}
    elif clip == "claw":                                              # Thriller arms: claws up to one side, then the
        c = math.sin(tw * p)                                           # other; hunched, a stomp landing on each beat
        k = 0.5 + 0.5 * math.copysign(abs(c) ** 0.6, c)              # 1: claws to the right, 0: to the left
        sd = 2 * k - 1
        _trunk(g, V3(0.03 * sd, 0.0, -0.04 * beat), pelvis=Rz(-6 * sd), s1=Rz(-8 * sd) @ Rx(-5),
               s2=Rz(-16 * sd) @ Rx(-8), neck=Rx(-5), head=Rz(-8 * sd) @ Ry(6 * sd) @ Rx(-6 + 5 * beat))
        _arm(g, "R", 105 + 18 * k, 5 + 40 * k, 95 - 20 * k, shrug=8 + 6 * k, wrist=-50)
        _arm(g, "L", 105 + 18 * (1 - k), 5 + 40 * (1 - k), 95 - 20 * (1 - k), shrug=8 + 6 * (1 - k), wrist=-50)
        legs["R"] = {"dx": 0.06 * k, "lift": 0.04 * (1 - beat) * k}
        legs["L"] = {"dx": -0.06 * (1 - k), "lift": 0.04 * (1 - beat) * (1 - k)}
    else:
        raise ValueError(clip)
    for n in "RL":
        if sit:
            _leg_sit(g, n)
        else:
            _leg(g, n, **legs[n])
    if clip == "flow":                                                # props spin in the plane facing the stage
        for n, sgn in (("R", 1.0), ("L", -1.0)):
            gp = g[f"hand.{n}"] @ J[f"grip.{n}"]
            g[f"prop.{n}"] = Tm(gp) @ Ry(sgn * 360.0 * p).to_4x4() @ Tm(-J[f"grip.{n}"])
        om = tw * 2 * p
        g["hoop"] = g["pelvis"] @ Tm(V3(0.25 * math.cos(om), 0.25 * math.sin(om), 0)) @ about(
            J["waist"], Rx(7 * math.sin(om)) @ Ry(-7 * math.cos(om)))
    else:
        g["prop.R"], g["prop.L"], g["hoop"] = g["hand.R"], g["hand.L"], g["pelvis"]
    return g


_PA = {}


def pose_arrays(clip, p):
    """The pose as stacked arrays: R (B, 3, 3), t (B, 3) (memoized: poses don't depend on the tier)."""
    key = (clip, round(float(p), 9))
    if key not in _PA:
        g = pose(clip, p)
        m = np.array([np.array(g[b]) for b in BONE_NAMES])
        _PA[key] = (m[:, :3, :3], m[:, :3, 3])
    return _PA[key]


# ============================================================================ canonical meshes as arrays
def pack_islands(sizes, margin=0.015):
    if not sizes:
        return []
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i][1])
    area = sum((w + margin) * (h + margin) for w, h in sizes)
    best = None
    for f in (1.0, 1.08, 1.16, 1.25, 1.35, 1.5, 1.7, 2.0):
        width = max(math.sqrt(area) * f, max(w for w, _ in sizes) + margin)
        pos, x, y, row, maxw = [None] * len(sizes), 0.0, 0.0, 0.0, 0.0
        for i in order:
            w, h = sizes[i]
            if x > 0 and x + w + margin > width:
                x, y, row = 0.0, y + row, 0.0
            pos[i] = (x + margin / 2, y + margin / 2)
            x += w + margin
            row = max(row, h + margin)
            maxw = max(maxw, x)
        side = max(maxw, y + row)
        if best is None or side < best[0]:
            best = (side, pos)
    side, pos = best
    return [(px / side, py / side, w / side, h / side) for (px, py), (w, h) in zip(pos, sizes)]


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


class Canon:
    """One tier's superset mesh as numpy arrays: geometry, weights, parts, regions, UV layouts (body / totem cell),
    morph bases (body types) and the frame-0 pose of every clip."""

    def __init__(self, tier):
        g = build_canonical(tier)
        self.tier = tier
        self.V = np.array([tuple(v) for v in g.v], dtype=np.float64)
        self.W = np.zeros((len(g.v), len(BONE_NAMES)))
        for i, wd in enumerate(g.w):
            for b, w in wd.items():
                self.W[i, BONE_IDX[b]] += w
        self.W /= self.W.sum(1, keepdims=True)
        self.pat = np.array(g.pat, dtype=np.float32)
        self.pj = np.array(g.pj, dtype=np.int64)
        self.F_len = np.array([len(f) for f in g.f], dtype=np.int64)
        self.F_start = np.concatenate([[0], np.cumsum(self.F_len)[:-1]])
        self.L_vert = np.array([v for f in g.f for v in f], dtype=np.int64)
        self.L_face = np.repeat(np.arange(len(g.f)), self.F_len)
        k = np.arange(len(self.L_vert)) - self.F_start[self.L_face]
        self.L_rev = self.F_start[self.L_face] + (self.F_len[self.L_face] - 1 - k)
        self.F_part = np.array([PART[p] for p in g.fpart], dtype=np.int64)
        self.F_reg = np.array(g.freg, dtype=np.int64)
        self.F_glow = np.isin(self.F_reg, list(GLOW_REGIONS))
        totem = np.isin(self.F_part, [PART[p] for p in TOTEM_PARTS])
        f_isl = np.array(g.fisl, dtype=np.int64)
        local = np.array([uv for f_uv in g.fuv for uv in f_uv], dtype=np.float64)
        place = np.zeros((len(g.isl), 4))
        isl_main = np.zeros(len(g.isl), dtype=bool)                   # an island a body part uses keeps full size,
        isl_main[f_isl[np.isin(self.F_part, [PART[q] for q in BODY_PARTS + HAIR_PARTS])]] = True   # shared or not
        for mask in (~self.F_glow & ~totem, ~self.F_glow & totem):     # rarely worn parts get smaller islands
            used = sorted(set(f_isl[mask].tolist()))
            sizes = [tuple(v * (1.0 if isl_main[i] else 0.6) for v in g.isl[i]) for i in used]
            for i, rect in zip(used, pack_islands(sizes)):
                place[i] = rect
        pl = place[f_isl[self.L_face]]
        self.L_uv = np.stack([pl[:, 0] + local[:, 0] * pl[:, 2], pl[:, 1] + local[:, 1] * pl[:, 3]], 1)
        self.L_uv[self.F_glow[self.L_face]] = 0.0
        self.L_cell = totem[self.L_face].astype(np.int64)
        self.tris = int((self.F_len - 2).sum())
        # vertex -> parts (a vertex belongs to the parts of its faces)
        self.V_part = np.zeros(len(g.v), dtype=np.int64)
        self.V_part[self.L_vert] = self.F_part[self.L_face]
        self._morph_bases()
        self.frame0 = {c: pose_arrays(c, 0.0) for c in CLIPS}
        # far-tier billboards are one-sided quads: a raised arm turns its ribbon around, so per clip, flip the faces
        # whose frame-0 normal points away from the stage (+Y in the person's frame) -> assemble() reverses them
        self.flip0 = {c: np.zeros(len(self.F_part), dtype=bool) for c in CLIPS}
        if tier == "far":
            bill = np.nonzero(np.isin(self.F_part, [PART[q] for q in FAR_BILLBOARDS]))[0]
            for clip in CLIPS:
                P0 = self.posed(clip, 0.0)
                for f in bill:
                    q = P0[self.L_vert[self.F_start[f]:self.F_start[f] + self.F_len[f]]]
                    n = np.cross(q[1] - q[0], q[2] - q[1]) + (np.cross(q[2] - q[0], q[3] - q[2]) if len(q) > 3 else 0.0)
                    self.flip0[clip][f] = n[1] < 0

    def _bone_sum(self, names):
        return self.W[:, [BONE_IDX[b] for b in names]].sum(1)

    def _morph_bases(self):
        """Per-vertex displacement fields for body types (meters at weight 1). The torso fields move everything worn on
        the torso by bone weight (tops, tutus, packs, straps, necklaces, braids), the limb fields the arm and leg tubes
        (+ leg warmers); the inflatable T-rex keeps its shape."""
        V, n = self.V, len(self.V)
        x, y, z = V[:, 0], V[:, 1], V[:, 2]
        wt = self._bone_sum(["pelvis", "spine1", "spine2"])
        wc = self._bone_sum(["clav.R", "clav.L"])
        sgn = np.where(x >= 0, 1.0, -1.0)
        armR = self._bone_sum(["upperarm.R", "forearm.R", "hand.R", "prop.R"]) + 0.6 * self._bone_sum(["clav.R"])
        armL = self._bone_sum(["upperarm.L", "forearm.L", "hand.L", "prop.L"]) + 0.6 * self._bone_sum(["clav.L"])
        legR = self._bone_sum(["thigh.R", "shin.R", "foot.R"])
        legL = self._bone_sum(["thigh.L", "shin.L", "foot.L"])
        mb = {}
        sh = np.zeros((n, 3))                                         # shoulders: arms out, shoulder line wider
        sh[:, 0] = armR - armL + (wt + wc) * sgn * _smooth(1.28, 1.42, z) * np.clip((np.abs(x) - 0.08) / 0.09, 0, 1)
        mb["shoulders"] = sh
        hp = np.zeros((n, 3))                                         # hips: pelvis wider, seat back, thighs apart
        hp[:, 0] = wt * (x / 0.17) * np.exp(-((z - 0.88) / 0.10) ** 2) + (legR - legL) * _smooth(0.35, 0.9, z) * 0.9
        hp[:, 1] = wt * np.minimum(y, 0) / 0.11 * 0.6 * np.exp(-((z - 0.86) / 0.09) ** 2)
        mb["hips"] = hp
        bu = np.zeros((n, 3))                                         # bust: chest front forward
        bu[:, 1] = wt * (y > 0) * np.exp(-((z - 1.27) / 0.065) ** 2) * np.clip(1 - (np.abs(x) - 0.07) / 0.1, 0, 1) * 0.9
        mb["bust"] = bu
        be = np.zeros((n, 3))                                         # belly: waist front forward + a little wider
        be[:, 1] = wt * np.maximum(y, 0) / 0.09 * np.exp(-((z - 1.06) / 0.11) ** 2)
        be[:, 0] = wt * x / 0.15 * 0.35 * np.exp(-((z - 1.06) / 0.12) ** 2)
        mb["belly"] = be
        trex = self.V_part == PART["trex"]
        for m_ in (sh, hp, bu, be):
            m_[trex] = 0.0
        lt = np.zeros((n, 3))                                         # limb thickness: radial from the bone axis
        lt_flare = np.zeros((n, 3))
        limbs = np.isin(self.V_part, [PART[q] for q in ("b_arms", "b_legs", "warmers", "bones")])   # bone strips too
        for n_ in "RL":
            for a, b, bone in ((J[f"shoulder.{n_}"], J[f"elbow.{n_}"], "upperarm." + n_),
                               (J[f"elbow.{n_}"], J[f"wrist.{n_}"], "forearm." + n_),
                               (J[f"hip.{n_}"], J[f"knee.{n_}"], "thigh." + n_),
                               (J[f"knee.{n_}"], J[f"ankle.{n_}"], "shin." + n_)):
                a_, b_ = np.array(a), np.array(b)
                sel = limbs & (self._bone_sum([bone]) >= 0.5)
                ab = b_ - a_
                t = np.clip(((V[sel] - a_) @ ab) / (ab @ ab), 0, 1)
                radial = V[sel] - (a_ + t[:, None] * ab)
                lt[sel] = radial
                if bone.startswith("shin"):
                    lt_flare[sel] = radial * (0.3 + 0.7 * t[:, None])
        mb["limbs"] = lt
        mb["flare"] = lt_flare
        pf = np.zeros((n, 3))                                         # platform soles: the sole bottom goes down
        pf[(self._bone_sum(["foot.R", "foot.L"]) > 0.5) & (z < 0.03), 2] = -1.0
        mb["platform"] = pf
        self.morph = mb

    def posed(self, clip, p):
        R, t = pose_arrays(clip, p)
        return np.einsum("nb,bij,nj->ni", self.W, R, self.V) + self.W @ t

    def lbs(self, X, idx, Rt):
        R, t = Rt
        W = self.W[idx]
        return np.einsum("nb,bij,nj->ni", W, R, X) + W @ t


# ============================================================================ VAT
def write_exr(path, rgba, half=True):
    """Uncompressed scanline OpenEXR. rgba: HxWx4 floats, row 0 = TOP of the image (Unreal's V = 0)."""
    h, w, _ = rgba.shape
    dt = np.dtype("<f2") if half else np.dtype("<f4")

    def attr(name, typ, data):
        return name.encode() + b"\0" + typ.encode() + b"\0" + struct.pack("<i", len(data)) + data
    chl = b"".join(c.encode() + b"\0" + struct.pack("<iBBBBii", 1 if half else 2, 0, 0, 0, 0, 1, 1) for c in "ABGR") + b"\0"
    hdr = struct.pack("<ii", 20000630, 2)
    hdr += attr("channels", "chlist", chl) + attr("compression", "compression", b"\0")
    hdr += attr("dataWindow", "box2i", struct.pack("<iiii", 0, 0, w - 1, h - 1))
    hdr += attr("displayWindow", "box2i", struct.pack("<iiii", 0, 0, w - 1, h - 1))
    hdr += attr("lineOrder", "lineOrder", b"\0") + attr("pixelAspectRatio", "float", struct.pack("<f", 1.0))
    hdr += attr("screenWindowCenter", "v2f", struct.pack("<ff", 0.0, 0.0)) + attr("screenWindowWidth", "float", struct.pack("<f", 1.0))
    hdr += b"\0"
    line = w * 4 * dt.itemsize
    first = len(hdr) + 8 * h
    out = bytearray(hdr) + struct.pack(f"<{h}Q", *[first + y * (8 + line) for y in range(h)])
    for y in range(h):
        px = rgba[y].astype(dt)
        out += struct.pack("<ii", y, line) + b"".join(px[:, c].tobytes() for c in (3, 2, 1, 0))
    open(path, "wb").write(out)


def vat_pages(canons, limit=2048):
    """Tier -> (page, first column). A page is a band of len(CLIPS) * ROWS rows; tiers fill a page left to right until
    the next one would pass `limit` columns (16-bit UVs hold integers exactly only up to 2048)."""
    out, page, col = {}, 0, 0
    for c in canons:
        if col and col + len(c.V) > limit:
            page, col = page + 1, 0
        out[c.tier] = (page, col)
        col += len(c.V)
    return out, page + 1


def bake_vat(canons):
    """Offsets from each clip's FRAME 0 for every tier's superset vertices -> (texture HxWx4 float32, tier -> (page,
    first column), pages, widest page). Row of (page, clip, frame) = (page * len(CLIPS) + clip) * ROWS + frame."""
    vlay, n_pages = vat_pages(canons)
    width = max(vlay[c.tier][1] + len(c.V) for c in canons)
    if width > 2048:
        log(f"WARNING: a VAT page is {width} columns wide: 16-bit UVs are not exact past 2048 (use full-precision UVs)")
    tex_w = 1 << (width - 1).bit_length()
    tex_h = 1 << (n_pages * len(CLIPS) * ROWS - 1).bit_length()
    tex = np.zeros((tex_h, tex_w, 4), dtype=np.float32)
    tex[..., 3] = 1.0
    for ci, clip in enumerate(CLIPS):
        for c in canons:
            page, col = vlay[c.tier]
            base = c.posed(clip, 0.0)
            r0 = (page * len(CLIPS) + ci) * ROWS
            for f in range(ROWS):
                tex[r0 + f, col:col + len(c.V), :3] = c.posed(clip, (f % FRAMES) / FRAMES) - base
    return tex, vlay, n_pages, width


# ============================================================================ the field
def crowd_half_v2(y):
    """Half-width of the packed crowd at depth y (y < 0) (agreed for kit.crowd_half, 2026-10-05)."""
    return 20.0 + 0.55 * (-y)


Y_FRONT, Y_BACK = -8.6, -66.0
TIERS = (("near", 12.0), ("mid", 18.5), ("far", 1e9))     # by distance from the DJ (origin)
CLIP_ZONE = {                                             # who dances what, by zone (140 BPM half-time dubstep:
    "front": {"headbang": 0.22, "jump": 0.18, "pump": 0.16, "jumppump": 0.11, "handsup": 0.10, "wave": 0.05,
              "clap": 0.04, "claw": 0.04, "twostep": 0.03, "sway": 0.03, "lurch": 0.02, "nod": 0.02},   # bang up front,
    "middle": {"headbang": 0.13, "jump": 0.11, "pump": 0.12, "jumppump": 0.07, "handsup": 0.07, "wave": 0.06,
               "clap": 0.04, "claw": 0.04, "sway": 0.12, "twostep": 0.07, "lurch": 0.03, "nod": 0.12, "hold": 0.02},
    "back": {"headbang": 0.06, "jump": 0.06, "pump": 0.07, "jumppump": 0.04, "handsup": 0.05, "wave": 0.07,
             "clap": 0.04, "claw": 0.03, "sway": 0.19, "twostep": 0.10, "lurch": 0.03, "nod": 0.22, "hold": 0.04},
}                                                         # sway, nod and film further back; "hold" = a phone up
BEAT_CLIPS = {"jump", "jumppump", "pump", "handsup", "wave", "clap", "twostep", "lurch", "claw", "shuffle", "heart",
              "headbang", "hold", "carry", "ride"}       # on the beat: phase 0 or 1 beat (+-30 ms), exact tempo
HALF_TIME_OK = set(BEAT_CLIPS)                            # any beat clip may run at half time ...
HALF_TIME_P = 0.65                                        # ... and ~65 % do (crowd3: 15 % of 7 clips)
GROOVE_HALF_P = 0.45                                      # free-floating groove clips at half time (crowd3: 20 %)
CARRIER_DROP = {"phone", "glowstick", "pole", "flag", "sign", "skull", "ptotem", "cutout", "fan", "poi", "staff", "hoop",
                "hat_dome", "hat_brim", "hat_pom", "hat_bucket", "hat_cowboy", "witch_hat", "witch_band", "crown",
                "horns", "ears", "hair_bun", "hair_pony", "goggles", "bucket", "collar", "tail", "tail_spade"}
#                                                           a friend sits right behind the carrier's head


def _timing(rng, p):
    """Phase + playback rate. Beat clips stay on the beat (the authored tempo; ~65 % at half time, phase offsets of 0 or
    2 beats then, so they stay on the half-time grid); groove clips float (random phase, +-3 % tempo, 45 % at half
    time): neighbours never move in lockstep for long. The phase jitter is ~30 ms at either rate."""
    if p["clip"] in BEAT_CLIPS:
        p["rate"] = 0.5 if (p["clip"] in HALF_TIME_OK and rng.random() < HALF_TIME_P) else 1.0
        p["phase"] = (0.5 * rng.randrange(2) + rng.gauss(0, 0.035 * p["rate"])) % 1.0
    else:
        p["phase"] = rng.random()
        p["rate"] = (0.5 if rng.random() < GROOVE_HALF_P else 1.0) * (1.0 + rng.gauss(0, 0.03))


POSE_CLIPS = {"down": ("nod", "sway", "twostep"), "up": ("jump", "wave", "handsup"), "one": ("pump", "jumppump"),
              "hips": ("nod", "talk")}


def _excluded(x, y, exclude):
    return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in exclude)


def _field(rng, scale, half_fn, exclude):
    """Rows from the barrier back: packed at the barrier, gaps growing with depth and toward the sides; the sides and
    the last 10 m feather out (people drop out toward the edge instead of a straight cut)."""
    pts = []
    y = Y_FRONT
    while y > Y_BACK:
        depth = Y_FRONT - y
        gap = scale * (0.52 + 0.0142 * depth)
        half = half_fn(y) - 0.3
        back = min(1.0, max(0.0, ((Y_BACK + 10.0) - y) / 10.0))
        x = -half + rng.uniform(0, gap)
        while x < half:
            side = max(0.0, abs(x) / half - 0.72) / 0.28
            gx = gap * (1.0 + 0.55 * side)
            px, py = x + rng.uniform(-0.3, 0.3) * gx, y + rng.uniform(-0.3, 0.3) * gap
            keep = (1.0 - 0.5 * side * side) * (1.0 - 0.8 * back)
            if rng.random() < keep and not _excluded(px, py, exclude):
                pts.append((px, py))
            x += gx * rng.uniform(0.85, 1.15)
        y -= gap * 0.9
    return pts


def layout(rng, exclude, half_fn, target):
    lo, hi = 0.5, 3.0
    for _ in range(18):
        mid = (lo + hi) / 2
        if len(_field(random.Random(4242), mid, half_fn, exclude)) > target:
            lo = mid
        else:
            hi = mid
    return _field(rng, hi, half_fn, exclude), hi


def _face_stage(x, y):
    return math.atan2(-(0.0 - x), 5.0 - y)


def _choice_w(rng, table):
    return rng.choices(list(table), weights=list(table.values()))[0]


BUILDS = {"slim": (0.24, dict(shoulders=-0.012, hips=-0.006, bust=0.0, belly=0.0, limbs=-0.08), 0.93),
          "average": (0.34, dict(shoulders=0.0, hips=0.004, bust=0.006, belly=0.006, limbs=0.0), 1.0),
          "athletic": (0.15, dict(shoulders=0.03, hips=0.0, bust=0.0, belly=-0.004, limbs=0.13), 1.04),
          "curvy": (0.17, dict(shoulders=-0.006, hips=0.036, bust=0.03, belly=0.006, limbs=0.06), 1.0),
          "heavy": (0.10, dict(shoulders=0.016, hips=0.03, bust=0.016, belly=0.05, limbs=0.16), 1.08)}


COSTUMES = {"skeleton": 0.15, "witch": 0.13, "zombie": 0.13, "pumpkin": 0.12, "ghost": 0.09, "devil": 0.12,
            "vampire": 0.09, "mummy": 0.06, "cat": 0.11}
COSTUME_RATE = 0.47          # people who pick a costume on their own; friend groups with a theme add more (~55 % in all)
SQUAD_THEME = 0.35           # friend groups who dress alike (85 % of the group wear the theme)
TREX_P, TREX_MIN = 0.006, 3  # inflatable T-rexes (the Dino Stage nod): mid tier only (they read from 12-20 m)
COSTUME_CLIPS = {            # added to the zone weights for that costume
    "zombie": {"lurch": 0.50, "claw": 0.06}, "mummy": {"lurch": 0.40, "claw": 0.05},
    "ghost": {"wave": 0.10, "sway": 0.10, "claw": 0.08, "handsup": 0.06},
    "witch": {"claw": 0.16, "sway": 0.08, "wave": 0.04}, "vampire": {"claw": 0.10, "nod": 0.06},
    "skeleton": {"headbang": 0.10, "jump": 0.06, "lurch": 0.04}, "pumpkin": {"headbang": 0.14, "nod": 0.04},
    "devil": {"pump": 0.10, "headbang": 0.08}, "cat": {"claw": 0.04, "twostep": 0.06, "sway": 0.06}}
TORSO_R = ("hips", "belly", "midriff", "chest", "shoulders")
ARM_R = ("sleeve_top", "sleeve_mid", "forearm", "wrist")
LEG_R = ("thigh_top", "thigh", "knee", "shin", "ankle")
HEADWEAR = ("hat_dome", "hat_brim", "hat_pom", "hat_bucket", "hat_cowboy", "witch_hat", "witch_band", "crown", "goggles",
            "horns", "ears", "mask_led", "glow_eyes")
RED_DEVIL = (0.60, 0.04, 0.03)
LINING_RED = (0.55, 0.02, 0.03)


def _pick_clip(rng, zone, costume):
    table = dict(CLIP_ZONE[zone])
    for c, add in COSTUME_CLIPS.get(costume, {}).items():
        table[c] = table.get(c, 0.0) + add
    return _choice_w(rng, table)


def _dress(rng, costume, p, parts, col, pat, skin):
    """The costume layer over the rave outfit: parts in and out, colours and patterns (vertex colour only)."""
    def paint(regs, c):
        for r in regs:
            col[r] = c
            pat.pop(r, None)
    hairless, headwear = set(HAIR_PARTS), set(HEADWEAR)
    if costume == "skeleton":                                         # black suit, bone strips, a skull face
        paint(TORSO_R + ARM_R + LEG_R + ("shoe",), BLACK)
        col.update(hand=BONE, face=BONE, jaw=BONE, brow=BONE, eyes=BONE, mouth=mul(BONE, 0.35), skin=BONE, bone=BONE,
                   bone_dark=(0.01, 0.01, 0.01))
        col["scalp"] = BLACK if rng.random() < 0.6 else BONE         # a hood, or a bare skull
        parts.difference_update(hairless | headwear | {"cape", "tutu", "warmers"})
        parts.add("bones")
        p["morph"].pop("flare", None)
    elif costume == "witch":                                          # cone hat, dark dress, cape / tutu, striped tights
        dress = rng.choice([BLACK, BLACK, (0.10, 0.02, 0.16), (0.02, 0.08, 0.03)])
        paint(TORSO_R + ("sleeve_top", "thigh_top"), dress)
        if rng.random() < 0.6:
            paint(("sleeve_mid", "forearm", "wrist"), dress)
        legs = ("thigh", "knee", "shin", "ankle")
        if rng.random() < 0.5:
            other = rng.choice([(0.75, 0.73, 0.68), (0.40, 0.08, 0.60), (0.85, 0.35, 0.03), (0.12, 0.55, 0.10)])
            for r in legs:
                col[r] = BLACK
                pat[r] = ("stripe", other)
        else:
            paint(legs, BLACK)
        col["shoe"] = BLACK
        parts.difference_update(headwear | {"hair_bun", "hair_pony", "warmers"})
        parts.add("witch_hat")
        col["hat"] = rng.choice(WITCH_HATS)
        col["hat2"] = rng.choice([NEON[0], NEON[1], NEON[2], (0.45, 0.08, 0.10)])
        if rng.random() < 0.35:
            parts.add("witch_band")
            col["glow_band"] = hw_glow(rng)
        if rng.random() < 0.5:
            parts.add("cape")
            col["cape"], col["cape2"] = dress, rng.choice([(0.30, 0.05, 0.45), (0.10, 0.35, 0.08), dress])
        if rng.random() < 0.4:
            parts.add("tutu")
            col["tutu"] = rng.choice([BLACK, (0.30, 0.05, 0.45), (0.10, 0.35, 0.08), (0.80, 0.30, 0.03)])
        if parts & hairless and rng.random() < 0.5:
            col["hair"] = col["scalp"] = rng.choice([(0.012, 0.009, 0.007), (0.35, 0.10, 0.03), (0.40, 0.08, 0.60),
                                                     (0.20, 0.75, 0.15), (0.90, 0.90, 0.92)])
        if rng.random() < 0.15:                                       # green face paint
            green = (0.22, 0.50, 0.18)
            for r, v in list(col.items()):
                if v == skin and r in BODY_REGIONS:
                    col[r] = green
            col.update(face=green, jaw=green, skin=green, hand=green, brow=mul(green, 0.6), mouth=mul(green, 0.5),
                       eyes=mul(green, 0.3))
            p["skin"] = green
    elif costume == "zombie":                                         # grey-green skin, torn and bloody clothes
        top = rng.choice([(0.55, 0.52, 0.45), (0.35, 0.08, 0.06), (0.28, 0.25, 0.16), (0.10, 0.15, 0.30),
                          (0.25, 0.27, 0.30), (0.45, 0.40, 0.30)])
        paint(TORSO_R[1:] + ("sleeve_top",), top)
        for r in TORSO_R[1:] + ("sleeve_top",):
            pat[r] = ("torn", (skin, BLOOD))
        paint(("hips", "thigh_top", "thigh", "knee"), rng.choice(DENIMS + EARTH[:2]))
        if rng.random() < 0.5:
            for r in ("thigh", "knee"):
                pat[r] = ("torn", (skin, BLOOD))
        col.update(mouth=BLOOD, eyes=mul(skin, 0.42), brow=mul(skin, 0.55), jaw=mul(skin, 0.85))
        parts.difference_update(headwear | {"tutu", "warmers", "cape"})
        if parts & hairless:
            col["hair"] = col["scalp"] = rng.choice(HAIR_NATURAL)
    elif costume == "pumpkin":                                        # a pumpkin for a head, with a glowing face
        parts.difference_update({"b_head"} | hairless | headwear)
        parts.add("pumpkin")
        col["pumpkin"] = rng.choice(PUMPKINS)
        col["pumpkin2"] = rng.choice([(0.15, 0.22, 0.05), (0.20, 0.12, 0.04)])
        col["glow_pface"] = CANDLE if rng.random() < 0.85 else rng.choice([GLOW_COLS["green"], GLOW_COLS["purple"]])
        paint(TORSO_R[1:] + ("sleeve_top",), rng.choice([BLACK, BLACK, (0.05, 0.20, 0.04), (0.85, 0.35, 0.03),
                                                         (0.30, 0.05, 0.45)]))
    elif costume == "ghost":                                          # a sheet over the body, the arms under it
        sheet = rng.choice(SHEETS)
        parts.difference_update({"b_torso", "b_head", "pack", "cape", "tutu", "necklace", "warmers"} | hairless |
                                headwear)
        parts.add("ghost")
        paint(TORSO_R + ARM_R + ("hand", "thigh_top", "thigh", "knee", "face", "scalp", "jaw", "skin"), sheet)
        col.update(sheet=sheet, sheet_dark=(0.01, 0.01, 0.01))
        paint(("shin", "ankle"), rng.choice([BLACK, (0.05, 0.08, 0.18)]))
        col["shoe"] = rng.choice([BLACK, (0.8, 0.8, 0.78)])
        p["morph"].pop("flare", None)
    elif costume == "devil":                                          # glowing red horns, cape, spade tail
        top = rng.choice([RED_DEVIL, RED_DEVIL, BLACK])
        paint(TORSO_R[1:] + ("sleeve_top",), top)
        if rng.random() < 0.6:
            paint(("hips",) + LEG_R, rng.choice([BLACK, BLACK, RED_DEVIL]))
        parts.difference_update(headwear)
        parts.add("horns")
        col["glow_horn"] = GLOW_COLS["red"] if rng.random() < 0.85 else GLOW_COLS["orange"]
        if rng.random() < 0.7:
            parts.add("cape")
            col["cape"], col["cape2"] = (RED_DEVIL, BLACK) if rng.random() < 0.5 else (BLACK, RED_DEVIL)
        if rng.random() < 0.8:
            parts |= {"tail", "tail_spade"}
            col["tail"] = col["tail2"] = rng.choice([RED_DEVIL, BLACK])
        if rng.random() < 0.35:                                       # red face paint
            col.update(face=(0.55, 0.05, 0.03), jaw=(0.55, 0.05, 0.03), brow=(0.30, 0.03, 0.02), mouth=BLACK)
        if rng.random() < 0.2:
            parts.add("glow_eyes")
            col["glow_eye"] = GLOW_COLS["red"]
    elif costume == "vampire":                                        # cape with a red lining, high collar, pale
        paint(TORSO_R[1:] + ARM_R, rng.choice([BLACK, BLACK, (0.30, 0.02, 0.03), (0.72, 0.70, 0.66)]))
        paint(("hips",) + LEG_R + ("shoe",), BLACK)
        parts.difference_update(headwear | {"tutu", "warmers", "pack"})
        if rng.random() < 0.9:
            parts.add("cape")
            col["cape"], col["cape2"] = BLACK, LINING_RED
        if rng.random() < 0.85:
            parts.add("collar")
            col["collar"], col["collar2"] = BLACK, LINING_RED
        if parts & hairless:
            col["hair"] = col["scalp"] = rng.choice(HAIR_NATURAL[:10])
        col["mouth"] = (0.40, 0.02, 0.03)
        if rng.random() < 0.15:
            parts.add("glow_eyes")
            col["glow_eye"] = GLOW_COLS["red"]
        p["morph"].pop("flare", None)
    elif costume == "mummy":                                          # bandage wraps everywhere
        band = rng.choice(BANDAGES)
        parts.difference_update(hairless | headwear | {"tutu", "warmers", "cape"})
        for r in TORSO_R + ARM_R + LEG_R + ("hand", "face", "jaw", "brow", "scalp", "mouth", "skin"):
            col[r] = band
            pat[r] = ("wrap", mul(band, 0.45))
        col["eyes"] = (0.03, 0.03, 0.03)
        col["shoe"] = mul(band, 0.5)
        if rng.random() < 0.25:
            parts.add("glow_eyes")
            col["glow_eye"] = rng.choice([GLOW_COLS["green"], GLOW_COLS["red"], GLOW_COLS["orange"]])
        p["morph"].pop("flare", None)
    elif costume == "cat":                                            # light-up ears, a tail, black (or tabby / white)
        coat = rng.choices([BLACK, (0.85, 0.40, 0.08), (0.75, 0.74, 0.72)], weights=(0.7, 0.15, 0.15))[0]
        paint(TORSO_R[1:] + ("sleeve_top", "sleeve_mid"), coat)
        if coat == BLACK or rng.random() < 0.5:                       # a catsuit: hips and legs too
            paint(("hips",) + LEG_R, coat)
            if coat == BLACK and rng.random() < 0.3:
                for r in ("thigh", "knee", "shin", "ankle"):
                    col[r] = skin
                    pat[r] = ("mesh", (0.01, 0.01, 0.012))          # fishnets
        if coat[0] > 0.8 and coat[2] < 0.1:                           # an orange tabby: dark stripes
            for r in TORSO_R[1:]:
                pat[r] = ("tiedye", (0.25, 0.10, 0.02))
        parts.difference_update(headwear)
        parts.add("ears")
        col["glow_horn"] = hw_glow(rng) if rng.random() < 0.7 else (0.02, 0.02, 0.02)
        if rng.random() < 0.8:
            parts.add("tail")
            col["tail"] = coat
        col.update(eyes=(0.01, 0.01, 0.01), mouth=(0.03, 0.02, 0.02))
    elif costume == "trex":                                           # the inflatable T-rex suit (mid tier)
        parts.clear()
        parts |= {"b_legs", "trex"}
        tc = rng.choice(TREX_COLS)
        col.update(trex=tc, trex2=(0.9, 0.9, 0.85), trex3=(0.10, 0.01, 0.01), thigh=tc, knee=tc, shin=tc, ankle=tc,
                   thigh_top=tc)


def make_person(rng, x, y, tier, zone="middle", yaw=None, clip=None, role=None, holder_bias=0.0, squad=None,
                force_costume=None):
    """Everything about one person: placement, body type, Halloween costume or rave outfit, parts, clip, phase, rate.
    force_costume: a costume name, "raver" (none), or None: field people and the grounds' extras pick for themselves
    (~55 % in costume); riders and carriers never wear one."""
    d = math.hypot(x, y)
    p = {"x": x, "y": y, "z": 0.0, "tier": tier, "role": role or "dancer", "held": None,
         "yaw": (_face_stage(x, y) + rng.gauss(0, 0.2)) if yaw is None else yaw, "mirror": rng.choice((1.0, -1.0))}
    build = rng.choices(list(BUILDS), weights=[v[0] for v in BUILDS.values()])[0]
    mw, sxb = BUILDS[build][1], BUILDS[build][2]
    p["morph"] = {k: v + rng.gauss(0, 0.006 if k != "limbs" else 0.03) for k, v in mw.items()}
    height = min(1.98, max(1.50, rng.gauss(1.71 + (0.04 if build == "athletic" else 0.0), 0.085)))
    p["sz"], p["sx"] = height / H, sxb * rng.uniform(0.96, 1.04)
    p["build"] = build
    skin = rng.choice(SKINS)
    # ---- costume (~55 %) or a raver in Halloween colours
    costume = None if force_costume == "raver" else force_costume
    if force_costume is None and role in (None, "extra"):
        if tier == "mid" and role is None and rng.random() < TREX_P:
            costume = "trex"
        elif squad and squad.get("costume") and rng.random() < 0.85:
            costume = squad["costume"]
        elif rng.random() < COSTUME_RATE:
            costume = _choice_w(rng, COSTUMES)
    p["costume"] = costume
    if costume == "zombie":
        skin = rng.choice(ZOMBIE_SKIN)
    elif costume == "vampire":                                        # pale make-up
        skin = tuple(0.45 * a_ + 0.55 * b_ for a_, b_ in zip(skin, (0.90, 0.87, 0.85)))
    p["skin"] = skin
    parts = set(BODY_PARTS)
    col, pat = {}, {}
    # ---- hair: short, long, ponytail, bun, braids, buzz cut, bald; natural or dyed
    hair = rng.choices(("short", "long", "pony", "bun", "braids", "buzz", "bald"),
                       weights=(0.24, 0.22, 0.10, 0.09, 0.08, 0.17, 0.10))[0]
    hcol = rng.choice(HAIR_DYED) if rng.random() < 0.28 else rng.choice(HAIR_NATURAL)
    if hair not in ("buzz", "bald"):
        parts.add("hair")
        parts.add({"long": "hair_long", "pony": "hair_pony", "bun": "hair_bun", "braids": "hair_braids"}.get(hair, "hair"))
    col["hair"] = hcol
    col["scalp"] = skin if hair == "bald" else hcol
    # ---- outfit: top, bottom, feet
    tk = rng.choices(("tee", "tank", "crop", "bralette", "bandeau", "bodysuit", "mesh", "long", "hoodie", "shirtless"),
                     weights=(0.17, 0.12, 0.15, 0.10, 0.05, 0.07, 0.09, 0.05, 0.05,
                              0.10 if build in ("athletic", "slim", "average") else 0.0))[0]
    top = squad["top"] if squad and squad.get("top") and rng.random() < 0.8 else top_color(rng)
    bk = rng.choices(("booty", "shorts", "tutu", "flowy", "cargo", "jeans", "black", "fishnet"),
                     weights=(0.15, 0.17, 0.06, 0.10, 0.14, 0.12, 0.14, 0.12))[0]
    if tk in ("crop", "bralette", "bandeau", "bodysuit") or bk in ("tutu", "booty"):   # the silhouette follows the outfit
        p["morph"]["bust"] += 0.018
        p["morph"]["hips"] += 0.014
        p["morph"]["shoulders"] -= 0.010
    elif tk == "shirtless":
        p["morph"]["shoulders"] += 0.012
        p["morph"]["bust"] = min(p["morph"]["bust"], 0.004)
    bottom = (rng.choice(DENIMS) if bk == "jeans" else rng.choice(EARTH) if bk == "cargo" else
              rng.choice(DARKS) if bk in ("black", "fishnet") else top_color(rng) if bk in ("flowy", "tutu") else
              rng.choice(DARKS + NEON + DENIMS))
    foot = rng.choices(("sneaker", "boots", "warmers", "platform", "light"), weights=(0.46, 0.18, 0.16, 0.08, 0.12))[0]
    shoe = rng.choice([(0.8, 0.8, 0.78), (0.02, 0.02, 0.02), (0.02, 0.02, 0.02)] + NEON[:4] + PASTELS[:2])
    warm = rng.choice(NEON + PASTELS + [(0.9, 0.9, 0.9)])
    torso_top = {"hips": bottom, "belly": top, "midriff": top, "chest": top, "shoulders": top}
    sleeves = {"sleeve_top": top, "sleeve_mid": skin, "forearm": skin, "wrist": skin}
    if tk == "tank":
        sleeves["sleeve_top"] = skin
    elif tk == "crop":
        torso_top.update(belly=skin if rng.random() < 0.6 else bottom, midriff=skin)
    elif tk in ("bralette", "bandeau"):
        torso_top.update(belly=skin if rng.random() < 0.7 else bottom, midriff=skin,
                         shoulders=skin if tk == "bandeau" else mul(top, 0.8))
        sleeves["sleeve_top"] = skin
    elif tk == "bodysuit":
        torso_top["hips"] = top
        sleeves["sleeve_top"] = skin if rng.random() < 0.5 else top
    elif tk == "mesh":                                                # dark mesh over skin / a lighter layer
        base_c, see = rng.choice(DARKS), rng.choice([skin, (0.5, 0.5, 0.52), top])
        torso_top.update({r: base_c for r in ("belly", "midriff", "chest", "shoulders")})
        sleeves.update(sleeve_top=base_c, sleeve_mid=base_c)
        for r in ("belly", "midriff", "chest", "shoulders", "sleeve_top", "sleeve_mid"):
            pat[r] = ("mesh", see)
    elif tk in ("long", "hoodie"):
        sleeves.update(sleeve_mid=top, forearm=top, wrist=top)
    elif tk == "shirtless":
        torso_top.update(belly=skin, midriff=skin, chest=skin, shoulders=skin)
        sleeves["sleeve_top"] = skin
    if tk in ("tee", "tank", "crop") and rng.random() < 0.15:          # tie-dye
        for r in ("belly", "midriff", "chest", "shoulders", "sleeve_top"):
            pat[r] = ("tiedye", rng.choice(NEON + PASTELS))
    legs = {"thigh_top": bottom, "thigh": bottom, "knee": bottom, "shin": bottom, "ankle": bottom}
    bare = bk in ("booty", "tutu") or (tk == "bodysuit" and rng.random() < 0.6)
    if bare:                                                          # bare legs, fishnets sometimes
        legs.update(thigh=skin, knee=skin, shin=skin, ankle=skin)
        if tk == "bodysuit" and bk not in ("booty", "tutu"):
            legs["thigh_top"] = top
        if rng.random() < 0.35:
            for r in ("thigh", "knee", "shin", "ankle"):
                pat[r] = ("mesh", (0.01, 0.01, 0.012))
    elif bk == "shorts":
        legs.update(knee=skin, shin=skin, ankle=skin)
    elif bk == "fishnet":                                             # hot pants over fishnet tights
        legs.update(thigh=skin, knee=skin, shin=skin, ankle=skin)
        for r in ("thigh", "knee", "shin", "ankle"):
            pat[r] = ("mesh", (0.01, 0.01, 0.012))
    if bk == "tutu":
        parts.add("tutu")
        col["tutu"] = rng.choice(NEON + PASTELS)
    if bk == "flowy" and not bare:
        p["morph"]["flare"] = rng.uniform(0.35, 0.6)
        pat["shin"] = pat["ankle"] = ("tiedye", rng.choice(NEON + PASTELS + DARKS))
    if foot == "boots":
        legs.update(ankle=shoe)
    elif foot == "warmers":
        if tier == "near":
            parts.add("warmers")
        legs.update(shin=warm, ankle=warm)
        pat.pop("shin", None)
        pat.pop("ankle", None)
        col["warmer"] = warm
    elif foot == "light":
        parts.add("lightshoes")
    elif foot == "platform":                                          # thick soles: the person stands 4.5 cm taller
        p["morph"]["platform"] = 0.045
        p["z"] += 0.045 * p["sz"]
    col.update(torso_top)
    col.update(sleeves)
    col.update(legs)
    col["shoe"] = shoe
    col["sole"] = (0.75, 0.75, 0.72) if foot != "platform" else (0.9, 0.9, 0.92)
    col["hand"] = skin
    # ---- face: masks / bandanas, shades, kandi
    col.update(face=skin, skin=skin, jaw=skin, eyes=mul(skin, 0.3), brow=mul(skin, 0.6), mouth=mul(skin, 0.62))
    if rng.random() < 0.14:
        m = rng.choice(DARKS + NEON + [(0.85, 0.85, 0.85)])
        col.update(jaw=m, mouth=m)
        if rng.random() < 0.3:
            pat["jaw"] = ("tiedye", rng.choice(NEON))
    if rng.random() < 0.2:
        col["eyes"] = rng.choice([(0.01, 0.01, 0.01), (0.01, 0.01, 0.01), (0.55, 0.05, 0.05), (0.40, 0.10, 0.60)])
    if rng.random() < 0.3:                                           # kandi stacks on the forearms
        pat["wrist"] = ("kandi", rng.sample(NEON + PASTELS, 3))
        col["wrist"] = (0.8, 0.8, 0.8)
    # ---- head wear (ravers; costumes replace it below)
    hat = rng.choices((None, "cap", "bucket", "beanie", "cowboy"), weights=(0.70, 0.06, 0.10, 0.03, 0.07))[0]
    if hat == "cap":
        parts |= {"hat_dome", "hat_brim"}
    elif hat == "beanie":
        parts |= {"hat_dome", "hat_pom"}
        parts -= {"hair_pony", "hair_bun"}
    elif hat == "bucket":
        parts.add("hat_bucket")
    elif hat == "cowboy":
        parts.add("hat_cowboy")
    col["hat"] = (rng.choice(DARKS + NEON + PASTELS + LIGHTS + [(0.45, 0.30, 0.15), (0.75, 0.6, 0.35)]) if hat != "cowboy"
                  else rng.choice([(0.45, 0.30, 0.15), (0.75, 0.6, 0.35), (0.9, 0.9, 0.9), (0.40, 0.08, 0.60),
                                   (0.02, 0.02, 0.02)]))
    col["hat2"] = mul(col["hat"], 0.75)
    if hat is None and rng.random() < 0.10:
        parts.add("crown")                                            # a rose crown
    if hat in (None, "cap") and tier == "near" and rng.random() < 0.09:
        parts.add("goggles")
    col["goggles"] = rng.choice(NEON + [(0.02, 0.02, 0.02)])
    glow_c = hw_glow(rng)
    if hat is None and "crown" not in parts:
        r_ = rng.random()
        if r_ < 0.06:
            parts.add("horns")                                        # LED horns
        elif r_ < 0.11:
            parts.add("ears")                                         # LED cat ears
    if rng.random() < 0.10:
        parts.add("mask_led")                                         # a light-up (purge) mask
        col["glow_mask"] = rng.choice([GLOW_COLS["red"], GLOW_COLS["green"], GLOW_COLS["purple"], GLOW_COLS["orange"]])
    # ---- the costume layer
    _dress(rng, costume, p, parts, col, pat, skin)
    # ---- capes, hydration packs, glow wear
    if costume is None and rng.random() < 0.05:
        parts.add("cape")
        col["cape"] = rng.choice(NEON + PASTELS + METALS)
        col["cape2"] = mul(col["cape"], 0.6)
        pat["cape"] = ("tiedye", rng.choice(NEON + PASTELS))
    if costume in (None, "zombie", "skeleton", "cat") and "cape" not in parts and rng.random() < 0.18:
        parts.add("pack")
    col["pack"] = rng.choice(DARKS + NEON[:4] + PASTELS[:2])
    col["strap"] = (0.02, 0.02, 0.02)
    if costume not in ("trex", "ghost") and rng.random() < 0.20:
        parts.add("necklace")
    if costume != "trex" and rng.random() < 0.06:
        parts.add("gloves")
        if costume is None:
            col["hand"] = (0.012, 0.012, 0.014)
    # ---- held things: totems, flow toys, phones, glowsticks, jack-o-lantern buckets (a held thing decides the dance)
    free = role is None and costume != "trex"
    holder = free and d > 10.5 and rng.random() < 0.012 + holder_bias
    if holder:
        item = rng.choices(("flag", "sign", "skull", "ptotem", "cutout"), weights=(0.30, 0.22, 0.20, 0.16, 0.12))[0]
        parts |= {"pole", item}
        clip, p["held"], p["totem"] = "hold", "totem", item
    elif free and rng.random() < (0.03 if tier != "far" else 0.02):
        toy = rng.choices(("hoop", "poi", "staff", "fan"), weights=(0.35, 0.25, 0.2, 0.2))[0]
        parts.add(toy)
        clip, p["held"], p["flow"] = "flow", toy, toy
    elif free and rng.random() < 0.06:
        parts.add("phone")
        clip, p["held"] = "hold", "phone"
    elif costume != "trex" and role != "rider" and rng.random() < 0.10:
        parts.add("glowstick")
        p["held"] = "glowstick"
    if (costume != "trex" and role not in ("rider", "carrier") and not holder and clip in (None, "nod", "pump", "hold", "talk")
            and rng.random() < 0.03):
        parts.add("bucket")                                           # trick or treat: the bucket hand stays low
        p["bucket"] = True
        if clip is None:
            clip = rng.choice(("nod", "pump", "nod"))
    p["holder"] = holder
    for r in ("glow_stick", "glow_necklace", "glow_glove", "glow_shoe", "glow_fan", "glow_hoop", "glow_poi", "glow_staff",
              "glow_led", "glow_mask", "glow_skull", "glow_eye", "glow_band"):
        if r not in col:
            col[r] = hw_glow(rng)
    col.setdefault("glow_horn", glow_c)
    col.setdefault("glow_pface", CANDLE)
    col.update(glow_bucket=CANDLE, glow_ptotem=CANDLE, glow_screen=(0.55, 0.7, 1.0), glow_flash=(1.0, 1.0, 0.95))
    col.update(phone=(0.02, 0.02, 0.025), pole=(0.35, 0.35, 0.36), sign=(0.03, 0.03, 0.035), staff=(0.1, 0.1, 0.1),
               cutout=rng.choice([(0.30, 0.05, 0.45), (0.85, 0.35, 0.03), BLACK, (0.15, 0.55, 0.12)]),
               skull=BONE, skull_dark=(0.02, 0.02, 0.02), ptotem=rng.choice(PUMPKINS), ptotem2=(0.15, 0.22, 0.05),
               bucket=rng.choice(PUMPKINS), bucket2=(0.05, 0.03, 0.02))
    fl = rng.sample(FLAGS, 2)
    col.update(flag1=fl[0], flag2=fl[1], crown=(0.55, 0.03, 0.06))
    p["crown_cols"] = rng.sample([(0.55, 0.03, 0.06), (0.05, 0.05, 0.06), (0.40, 0.08, 0.60), (0.95, 0.40, 0.05),
                                  (0.80, 0.78, 0.72), (0.20, 0.45, 0.12)], 3)   # roses: blood, black, purple, orange...
    # ---- the dance (zone mix + costume bias); "hold" without a held thing means filming: a phone goes up
    if clip is None:
        clip = _pick_clip(rng, zone, costume)
    if clip == "hold" and p["held"] is None and costume != "trex":
        parts.discard("glowstick")
        parts.add("phone")
        p["held"] = "phone"
    # ---- the far shape: body + pole/flag + one-sided stand-ins for the glowing and costume things
    if tier == "far":
        far = {"b_torso", "b_head", "b_arms"}
        if holder:
            far |= {"pole", "flag"}
            it = p["totem"]
            col["flag1"] = {"skull": BONE, "ptotem": col["ptotem"], "cutout": col["cutout"],
                            "sign": col["sign"]}.get(it, col["flag1"])
            if it != "flag":
                far.add("far_ttop")
                col["glow_ttop"] = {"skull": col["glow_skull"], "ptotem": CANDLE}.get(it, col["glow_led"])
        hand = parts & {"phone", "glowstick", "gloves", "fan", "poi", "staff"}
        if hand:
            far.add("far_hand")
            gl = sorted(hand)[0]
            col["glow_hand"] = ((1.0, 1.0, 0.95) if gl == "phone" else
                                col["glow_" + {"glowstick": "stick", "gloves": "glove"}.get(gl, gl)])
        if parts & {"necklace", "hoop"}:
            far.add("far_chest")
            col["glow_chest"] = col["glow_hoop"] if "hoop" in parts else col["glow_necklace"]
        if parts & {"horns", "ears", "witch_band"}:
            col["glow_head"] = col["glow_band"] if "witch_band" in parts else col["glow_horn"]
            if max(col["glow_head"]) > 0.1:                           # unlit (black) cat ears get no far stand-in
                far.add("far_head")
        if "pumpkin" in parts:
            far = (far - {"b_head"}) | {"far_pumpkin", "far_face"}
            col["glow_face"] = col["glow_pface"]
        elif parts & {"mask_led", "glow_eyes"}:
            far.add("far_face")
            col["glow_face"] = col["glow_mask"] if "mask_led" in parts else mul(col["glow_eye"], 0.7)
        if "witch_hat" in parts:
            far.add("far_hat")
        if "bones" in parts:
            far.add("far_ribs")
            col["sleeve_mid"] = col["scalp"] = BONE
        if "bucket" in parts:
            far.add("far_lhand")
            col["glow_lhand"] = CANDLE
        parts = far
    p["parts"], p["col"], p["pat"] = parts, col, pat
    p["clip"] = clip
    _timing(rng, p)
    return p


def build_people(rng, pts, extra, half_fn, tiers):
    """Field positions -> people: friend groups (dancing together, or facing each other talking / dancing), couples,
    people turned to a neighbour, room around flow artists, a couple of inflatable T-rexes, people on friends'
    shoulders, totems toward the sides and the back; then the grounds' extra people."""
    def tier_of(x, y):
        d = math.hypot(x, y)
        return next(name for name, r in tiers if d < r)

    def zone_of(y):
        return "front" if y > -12.5 else "middle" if y > -32 else "back"
    n = len(pts)
    P = np.array(pts, dtype=np.float64).reshape(-1, 2)
    group = -np.ones(n, dtype=np.int64)
    order = list(range(n))
    rng.shuffle(order)
    groups = []
    for i in order:                                                   # friend groups: 2-5 neighbours within 1.4 m
        if group[i] >= 0 or P[i, 1] > -10.5 or rng.random() > 0.30:
            continue
        dd = np.hypot(P[:, 0] - P[i, 0], P[:, 1] - P[i, 1])
        cand = [int(j) for j in np.argsort(dd)[1:8] if dd[j] < 1.4 and group[j] < 0]
        size = min(len(cand), rng.choices((1, 2, 3, 4), weights=(0.38, 0.30, 0.20, 0.12))[0])
        if size < 1:
            continue
        members = [i] + cand[:size]
        group[members] = len(groups)
        groups.append(members)
    people = [None] * n
    for members in groups:
        cx, cy = P[members].mean(0)
        kind = rng.choices(("together", "circle", "couple"), weights=(0.55, 0.30, 0.15 if len(members) == 2 else 0.0))[0]
        squad = {"top": top_color(rng)} if rng.random() < 0.2 else {}
        if rng.random() < SQUAD_THEME:                                # friends who dress alike
            squad["costume"] = _choice_w(rng, COSTUMES)
        squad = squad or None
        clip = _pick_clip(rng, zone_of(cy), squad.get("costume") if squad else None)
        if clip in BEAT_CLIPS:
            rate = 0.5 if (clip in HALF_TIME_OK and rng.random() < HALF_TIME_P) else 1.0
            ph = 0.5 * rng.randrange(2)
        else:
            rate = (0.5 if rng.random() < GROOVE_HALF_P else 1.0) * (1.0 + rng.gauss(0, 0.02))
            ph = rng.random()
        for j in members:
            x, y = P[j]
            if kind == "together":                                    # the same dance, nearly the same timing
                pr = make_person(rng, x, y, tier_of(x, y), zone_of(y), clip=clip, squad=squad)
                if pr["clip"] == clip:
                    pr["phase"], pr["rate"] = (ph + rng.gauss(0, 0.025 * (0.5 if rate < 0.75 else 1.0))) % 1.0, rate
            else:                                                     # facing each other: talk / sway / claw
                yaw = math.atan2(-(cx - x), cy - y) + rng.gauss(0, 0.25)
                c2 = (rng.choice(("talk", "talk", "sway", "twostep", "claw", "nod")) if kind == "circle" else
                      rng.choice(("sway", "twostep", "claw", "talk")))
                pr = make_person(rng, x, y, tier_of(x, y), zone_of(y), yaw=yaw, clip=c2, squad=squad)
            people[j] = pr
    for j in range(n):
        if people[j] is None:
            x, y = P[j]
            side = max(0.0, abs(x) / half_fn(y) - 0.45) * 0.12
            pr = make_person(rng, x, y, tier_of(x, y), zone_of(y), holder_bias=side + (0.012 if y < -30 else 0.0))
            if pr["clip"] not in ("hold", "flow") and pr["costume"] != "trex" and y < -10.5 and rng.random() < 0.05:
                pr["yaw"] += rng.choice((-1.0, 1.0)) * rng.uniform(0.6, 1.5)        # turned to a neighbour
                pr["clip"] = rng.choice(("talk", "talk", "sway", "nod", "twostep"))
                _timing(rng, pr)
            people[j] = pr
    keep = np.ones(n, dtype=bool)                                     # people make room for hoops, staffs and poi
    for j, pr in enumerate(people):
        r = {"hoop": 0.62, "staff": 0.70, "poi": 0.62}.get(pr.get("flow"), 0.0)
        if r and keep[j]:
            dd = np.hypot(P[:, 0] - P[j, 0], P[:, 1] - P[j, 1])
            for k2 in np.nonzero((dd < r) & keep)[0]:
                if k2 != j and people[k2]["clip"] != "flow":
                    keep[k2] = False
    people = [pr for j, pr in enumerate(people) if keep[j]]
    n_cleared = int(n - keep.sum())
    n_trex = sum(pr["costume"] == "trex" for pr in people)
    if n_trex < TREX_MIN:                                             # a few inflatable T-rexes, always
        mids = [j for j, pr in enumerate(people) if pr["tier"] == "mid" and pr["costume"] is None
                and pr["clip"] not in ("hold", "flow") and not pr["holder"]]
        for j in rng.sample(mids, min(len(mids), TREX_MIN - n_trex)):
            pr = people[j]
            people[j] = make_person(rng, pr["x"], pr["y"], "mid", zone_of(pr["y"]), yaw=pr["yaw"], force_costume="trex")
    riders = []                                                       # people on friends' shoulders
    cands = [j for j, pr in enumerate(people) if -21.0 < pr["y"] < -10.8 and math.hypot(pr["x"], pr["y"]) < 18.5
             and pr["costume"] is None and pr["clip"] != "flow" and abs(pr["x"]) < 0.8 * half_fn(pr["y"])]
    rng.shuffle(cands)
    for j in cands[:max(4, n // 300)]:
        c = people[j]
        c.update(role="carrier", clip="carry", holder=False, held=None, parts=c["parts"] - CARRIER_DROP)
        _timing(rng, c)
        back = 0.13                                                   # the rider sits just behind the carrier's head
        fx, fy = -math.sin(c["yaw"]) * back, math.cos(c["yaw"]) * back
        r = make_person(rng, c["x"] - fx, c["y"] - fy, c["tier"], "middle", yaw=c["yaw"], clip="ride", role="rider")
        r["sz"] = min(r["sz"], c["sz"])
        r["z"] = c["z"] + 1.48 * c["sz"] + 0.02 - 0.78 * r["sz"]     # crotch (canonical z 0.78) on the shoulders
        r["phase"], r["rate"] = c["phase"], c["rate"]
        r["parts"] = r["parts"] - {"tutu", "phone"}
        if r["tier"] != "far" and rng.random() < 0.4:                  # some riders hold up a flag / sign / totem
            r["totem"] = rng.choice(("flag", "sign", "flag", "skull", "ptotem"))
            r["parts"] = (r["parts"] - {"glowstick", "bucket"}) | {"pole", r["totem"]}
            r["holder"], r["held"] = True, "totem"
        riders.append(r)
    people += riders
    for e in extra:                                                   # (x, y, yaw, pose[, floor z]): an optional 5th
        ex, ey, eyaw, epose = e[:4]                                   # value stands the person on a floor at that
        pr = make_person(rng, ex, ey, tier_of(ex, ey), "back", yaw=eyaw,  # (pre-drop) height, e.g. the stage deck z=0
                         clip=rng.choice(POSE_CLIPS.get(epose, ("nod",))), role="extra")
        if len(e) > 4:
            pr["z"] += e[4] - GROUND_Z
        people.append(pr)
    return people, {"groups": len(groups), "riders": len(riders), "cleared_for_flow": n_cleared}


def look_regions(p):
    """Region -> linear RGB for this person (defaults to the skin colour)."""
    c = {r: p["skin"] for r in REGIONS}
    c.update(p["col"])
    return c


def _pack_cells(sizes):
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i])
    n = int(math.ceil(math.sqrt(sum(s * s for s in sizes)) * 1.02))
    while True:
        pos, x, y, row_h, ok = [None] * len(sizes), 0, 0, 0, True
        for i in order:
            s = sizes[i]
            if x + s > n:
                x, y, row_h = 0, y + row_h, 0
            if y + s > n:
                ok = False
                break
            pos[i] = (x, y)
            x += s
            row_h = max(row_h, s)
        if ok:
            return n, pos
        n += 1


CELL_UNITS = {"near": 3, "mid": 2, "far": 1}


def _vertex_colors(c, p, loops, lv, reg_col):
    """Per-loop colours: the region colour, with per-VERTEX patterns (mesh, kandi, tie-dye) so corners that share a
    vertex share a colour (no extra vertex splits in Unreal)."""
    regs = c.F_reg[c.L_face[loops]]
    out = reg_col[regs].copy()
    for rname, (kind, arg) in p["pat"].items():
        sel = regs == REG[rname]
        if not sel.any():
            continue
        vv = lv[sel]
        if kind == "mesh":                                            # dark mesh over a lighter layer: vertex parity
            light = np.array(arg, dtype=np.float32)
            k = c.pat[vv][:, None]
            out[sel] = out[sel] * (1 - k) + light * k * 0.75 + out[sel] * k * 0.25
        elif kind == "kandi":                                         # bead colours around the wrist
            pal = np.array(arg, dtype=np.float32)
            out[sel] = pal[c.pj[vv] % len(pal)]
        elif kind == "wrap":                                          # bandage wraps: dark between rings, grime
            dark = np.array(arg, dtype=np.float32)
            ring = (c.pat[vv] + c.pj[vv]) % 2                          # ring parity (pat = (j + ring) % 2, pj = j)
            h = 0.5 + 0.5 * np.sin(c.V[vv, 0] * 61.0 + c.V[vv, 1] * 47.0 + c.V[vv, 2] * 29.0)
            k = np.clip(0.9 * ring + 0.3 * h - 0.05, 0, 1)[:, None]
            out[sel] = out[sel] * (1 - k) + dark * k
        elif kind == "stripe":                                        # striped tights: every other ring
            other = np.array(arg, dtype=np.float32)
            k = ((c.pat[vv] + c.pj[vv]) % 2)[:, None]
            out[sel] = out[sel] * (1 - k) + other * k
        elif kind == "torn":                                          # torn, bloody clothes: skin through holes
            skin_c, blood = (np.array(a_, dtype=np.float32) for a_ in arg)
            h1 = np.sin(c.V[vv, 0] * 41.0 + c.V[vv, 2] * 29.0 + c.pj[vv] * 2.3)
            h2 = np.sin(c.V[vv, 1] * 53.0 + c.V[vv, 2] * 17.0 + c.pj[vv] * 1.1)
            hole = (h1 > 0.55)[:, None]
            stain = ((h2 > 0.75)[:, None]) & ~hole
            out[sel] = np.where(hole, skin_c, np.where(stain, blood, out[sel] * 0.8))
        elif kind == "tiedye":                                        # blotches of a second colour
            other = np.array(arg, dtype=np.float32)
            h = np.sin(c.V[vv, 0] * 37.0 + c.V[vv, 2] * 23.0 + c.pj[vv] * 1.7)
            k = np.clip(h * 1.5, 0, 1)[:, None]
            out[sel] = out[sel] * (1 - k) + other * k
    if "crown" in p["parts"]:
        sel = regs == REG["crown"]
        if sel.any():
            pal = np.array(p["crown_cols"], dtype=np.float32)
            out[sel] = pal[c.pj[lv[sel]] % len(pal)]
    return out


def assemble(people, canons, vlay):
    """Build (body arrays, glow arrays) for all people: copies of the tier canonicals, morphed to the person's body type
    and posed at frame 0 of their clip. vlay: tier -> (VAT page, first column)."""
    by_tier = {c.tier: c for c in canons}
    sizes, owner = [], []
    for i, p in enumerate(people):
        u = CELL_UNITS[p["tier"]]
        sizes.append(u)
        owner.append((i, 0))
        if p["parts"] & set(TOTEM_PARTS):
            sizes.append(u)
            owner.append((i, 1))
    n_units, pos = _pack_cells(sizes)
    cell_of = {key: (ox, oy, s) for key, (ox, oy), s in zip(owner, pos, sizes)}
    pad = 0.04
    keys = ("co", "lstart", "lvert", "uv0", "uv1", "uv2", "uv3", "uv4", "uv5", "col", "vdata")
    out = {"body": {k: [] for k in keys}, "glow": {k: [] for k in keys}}
    counts = {"body": [0, 0], "glow": [0, 0]}
    ranges = {"body": [], "glow": []}
    flip = (lambda v: 1.0 - v) if UE_FLIPS_V else (lambda v: v)
    for i, p in enumerate(people):
        c = by_tier[p["tier"]]
        page, col0 = vlay[p["tier"]]
        part_ok = np.zeros(len(PARTS), dtype=bool)
        part_ok[[PART[q] for q in p["parts"] if q in PART]] = True
        fmask = part_ok[c.F_part]
        lr = look_regions(p)
        reg_col = np.array([lr[r] for r in REGIONS], dtype=np.float32)
        cos_, sin_ = math.cos(p["yaw"]), math.sin(p["yaw"])
        m = p["mirror"]
        rot = np.array([[cos_, -sin_, 0], [sin_, cos_, 0], [0, 0, 1]]) @ np.diag([p["sx"] * m, p["sx"], p["sz"]])
        clip_i = page * len(CLIPS) + CLIPS.index(p["clip"])
        Rt0 = c.frame0[p["clip"]]
        for kind, gmask in (("body", ~c.F_glow), ("glow", c.F_glow)):
            fm = fmask & gmask
            if not fm.any():
                continue
            loops = np.nonzero(fm[c.L_face])[0]
            rev = c.flip0[p["clip"]][c.L_face[loops]]                  # billboards turned to the stage at frame 0
            if m < 0:                                                 # mirrored people: every face reversed
                rev = ~rev
            loops = np.where(rev, c.L_rev[loops], loops)
            lv = c.L_vert[loops]
            uniq, inv = np.unique(lv, return_inverse=True)
            X = c.V[uniq].copy()
            for mk, mv in p["morph"].items():                         # body type, flared pants, platform soles
                X += mv * c.morph[mk][uniq]
            base = c.lbs(X, uniq, Rt0)
            nv0, nl0 = counts[kind]
            o = out[kind]
            o["co"].append(base @ rot.T + np.array([p["x"], p["y"], GROUND_Z + p["z"]]))
            faces = np.nonzero(fm)[0]
            o["lstart"].append(nl0 + np.concatenate([[0], np.cumsum(c.F_len[faces])[:-1]]))
            o["lvert"].append(nv0 + inv)
            uvc = c.L_uv[loops]
            nl = len(loops)
            if kind == "body":
                cells = c.L_cell[loops]
                ox, oy, sz = np.empty(nl), np.empty(nl), np.empty(nl)
                for k in (0, 1):
                    sel = cells == k
                    if sel.any():
                        ox[sel], oy[sel], sz[sel] = cell_of[(i, k)]
                o["uv0"].append(np.stack([(ox + sz * pad + uvc[:, 0] * sz * (1 - 2 * pad)) / n_units,
                                          (oy + sz * pad + uvc[:, 1] * sz * (1 - 2 * pad)) / n_units], 1))
            else:
                o["uv0"].append(np.zeros((nl, 2)))
            o["uv1"].append(np.stack([lv + col0, np.full(nl, flip(clip_i))], 1))
            o["uv2"].append(np.tile([p["sx"] * cos_, flip(p["sx"] * sin_)], (nl, 1)))
            o["uv3"].append(np.tile([m * p["sz"], flip(p["phase"])], (nl, 1)))
            o["uv4"].append(np.tile([p["rate"], flip(0.0)], (nl, 1)))
            o["uv5"].append(np.tile([p["x"], flip(p["y"])], (nl, 1)))           # v7: the root (make-way)
            colv = _vertex_colors(c, p, loops, lv, reg_col)
            o["col"].append(np.concatenate([colv, np.ones((nl, 1), dtype=np.float32)], 1))
            nu = len(uniq)
            o["vdata"].append(np.column_stack([uniq + col0, np.full(nu, clip_i), np.full(nu, p["sx"] * cos_),
                                               np.full(nu, p["sx"] * sin_), np.full(nu, m * p["sz"]),
                                               np.full(nu, p["phase"]), np.full(nu, p["rate"])]))
            counts[kind] = [nv0 + nu, nl0 + nl]
            ranges[kind].append((i, nv0, uniq))
    res = {}
    for kind, o in out.items():
        res[kind] = {k: (np.concatenate(v) if v else None) for k, v in o.items()}
        res[kind]["ranges"] = ranges[kind]
    return res, n_units


def mesh_from_arrays(name, a):
    me = bpy.data.meshes.new(name)
    nv, nl, nf = len(a["co"]), len(a["lvert"]), len(a["lstart"])
    me.vertices.add(nv)
    me.vertices.foreach_set("co", a["co"].astype(np.float32).ravel())
    me.loops.add(nl)
    me.loops.foreach_set("vertex_index", a["lvert"].astype(np.int32))
    me.polygons.add(nf)
    me.polygons.foreach_set("loop_start", a["lstart"].astype(np.int32))
    for lname, key in (("UVMap", "uv0"),) + tuple(zip(DATA_UVS, ("uv1", "uv2", "uv3", "uv4", "uv5"))):
        lay = me.uv_layers.new(name=lname)
        lay.data.foreach_set("uv", a[key].astype(np.float32).ravel())
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    ca.data.foreach_set("color", a["col"].astype(np.float32).ravel())
    me.color_attributes.active_color = ca
    me.uv_layers.active = me.uv_layers["UVMap"]
    me.uv_layers["UVMap"].active_render = True
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    if len(me.polygons) != nf or len(me.loops) != nl:
        raise RuntimeError(f"{name}: validate() changed the mesh ({nf} -> {len(me.polygons)} faces)")
    me.polygons.foreach_set("use_smooth", np.ones(nf, dtype=bool))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


# ============================================================================ public entry point
_POSE = {}
_VAT = {}
_LAST = {}


def build_crowd2(rng, exclude=(), extra=(), out_dir=None, target=4250, half_fn=None, tiers=TIERS, vat_name="T_HwCrowdVAT"):
    """The costumed Halloween crowd. Returns (SM_HwCrowd, SM_HwPhones, extras): bodies (UV0 lighting cells, Col albedo,
    VAT UV channels; every person posed at frame 0 of their clip), the glowing bits (Col = emissive colour, same VAT),
    no extras. Writes <out_dir>/<vat_name>.exr (+ .json): the VAT both objects play. out_dir: else env HW_OUT, else
    halloween/out_hw. Same signature and layout as crowd3.build_crowd2 (only the default names differ)."""
    t0 = time.time()
    if half_fn is None:
        try:
            import kit
            half_fn = kit.crowd_half
        except ImportError:
            half_fn = crowd_half_v2
    out_dir = out_dir or os.environ.get("HW_OUT") or os.path.join(HW_DIR, "out_hw")
    os.makedirs(out_dir, exist_ok=True)
    canons = [Canon(t) for t in ("near", "mid", "far")]
    tex, vlay, n_pages, ncols = bake_vat(canons)
    pts, density = layout(rng, list(exclude), half_fn, target)
    people, roles = build_people(rng, pts, list(extra), half_fn, tiers)
    arrays, n_units = assemble(people, canons, vlay)
    _LAST.update(people=people, canons=canons, vlay=vlay, arrays=arrays)
    crowd = mesh_from_arrays("SM_HwCrowd", arrays["body"])
    phones = mesh_from_arrays("SM_HwPhones", arrays["glow"])
    _POSE[crowd.name] = [None, arrays["body"]["vdata"]]
    _POSE[phones.name] = [None, arrays["glow"]["vdata"]]
    _VAT["tex"] = tex
    write_exr(os.path.join(out_dir, vat_name + ".exr"), tex, half=True)
    _VAT["tex_half"] = tex.astype(np.float16).astype(np.float32)
    stats = {}
    glowing = {"necklace", "gloves", "lightshoes", "horns", "ears", "phone", "glowstick", "fan", "poi", "staff", "hoop",
               "sign", "witch_band", "mask_led", "glow_eyes", "pumpkin", "bucket", "skull", "ptotem", "far_hand",
               "far_chest", "far_head", "far_face", "far_lhand", "far_ttop"}
    for p in people:
        s = stats.setdefault(p["tier"], {"people": 0, "glowing": 0, "costumes": 0, "totems": 0, "phones": 0, "flow": 0,
                                         "riders": 0})
        s["people"] += 1
        s["glowing"] += bool(p["parts"] & glowing)
        s["costumes"] += p["costume"] is not None
        s["totems"] += p["held"] == "totem"
        s["phones"] += p["held"] == "phone"
        s["flow"] += p["clip"] == "flow"
        s["riders"] += p["role"] == "rider"
    clips, costumes = {}, {}
    for p in people:
        clips[p["clip"]] = clips.get(p["clip"], 0) + 1
        if p["costume"]:
            costumes[p["costume"]] = costumes.get(p["costume"], 0) + 1
    tris = {k: int((np.diff(np.append(a["lstart"], len(a["lvert"]))) - 2).sum()) for k, a in arrays.items()}
    field = [p for p in people if p["role"] in ("dancer", "carrier")]
    beat = [p for p in people if p["clip"] in BEAT_CLIPS]
    groove = [p for p in people if p["clip"] not in BEAT_CLIPS]
    shares = {"costumed_all": round(sum(p["costume"] is not None for p in people) / max(1, len(people)), 3),
              "costumed_field": round(sum(p["costume"] is not None for p in field) / max(1, len(field)), 3),
              "half_time_beat_clips": round(sum(p["rate"] < 0.75 for p in beat) / max(1, len(beat)), 3),
              "half_time_groove_clips": round(sum(p["rate"] < 0.75 for p in groove) / max(1, len(groove)), 3)}
    meta = {"what": "Halloween crowd VAT (hw_crowd, from crowd3): per-vertex offsets (m, Blender space) from FRAME 0 of "
                    "each clip (every person is posed at frame 0 of their clip); columns = tier superset vertices; rows "
                    "= (page * len(clips) + clip) * rows_per_clip + frame (row 0 = top); UV1.y = page * len(clips) + "
                    "clip",
            "texture": vat_name + ".exr", "width": tex.shape[1], "height": tex.shape[0], "columns_used": ncols,
            "pages": n_pages, "tier_pages": {t: v[0] for t, v in vlay.items()},
            "tier_columns": {t: v[1] for t, v in vlay.items()},
            "fps": FPS, "frames_per_clip": FRAMES, "rows_per_clip": ROWS, "clips": list(CLIPS),
            "authored_bpm": AUTHORED_BPM, "beats_per_clip": BEATS_PER_CLIP, "loop_rate_for_bpm": "LoopRate = BPM / 120",
            "set_bpm": HW_BPM, "loop_rate": round(HW_BPM / 120.0, 4), "shares": shares,
            "tier_vertices": {c.tier: len(c.V) for c in canons}, "tier_superset_tris": {c.tier: c.tris for c in canons},
            "axis_scale": list(UE_AXIS), "ue_flips_v": UE_FLIPS_V, "uv_channels": VAT_LAYOUT,
            "people": len(people), "field_people": len(people) - roles["riders"] - len(extra), "riders": roles["riders"],
            "extra_people": len(extra), "groups": roles["groups"], "cleared_for_flow": roles["cleared_for_flow"],
            "density_scale": density, "tiers": stats, "clip_counts": clips, "costumes": costumes, "tris": tris,
            "blender_vertices": {k: len(a["co"]) for k, a in arrays.items()}, "atlas_units": n_units,
            "max_offset_m": float(np.abs(tex[..., :3]).max())}
    json.dump(meta, open(os.path.join(out_dir, vat_name + ".json"), "w"), indent=1)
    _VAT["meta"] = meta
    log(f"halloween crowd: {len(people)} people ({meta['field_people']} field + {roles['riders']} riders + "
        f"{len(extra)} extra), {roles['groups']} groups, costumes {costumes}, shares {shares}, tiers {stats}, tris {tris}, "
        f"VAT {tex.shape[1]}x{tex.shape[0]} ({n_pages} pages, widest {ncols} columns; tier columns "
        f"{ {c.tier: len(c.V) for c in canons} }), atlas {n_units} units, {time.time() - t0:.1f} s")
    return crowd, phones, []


# ============================================================================ previews / checks (Blender side)
def wpo_blender(vdata, t, tex, loop_rate=1.0):
    """The material's offset in Blender space (numpy, float32 like the GPU): vdata columns = (column, clip, c, s, msz,
    phase, rate) per vertex."""
    f32 = np.float32
    v = vdata.astype(f32)
    tex_h, tex_w = tex.shape[:2]
    p = np.mod(f32(t) * f32(loop_rate) * v[:, 6] + v[:, 5], f32(1.0))
    fr = p * f32(FRAMES)
    f0 = np.floor(fr)
    a = (fr - f0)[:, None]
    row = (v[:, 1] * ROWS + f0).astype(np.int64)
    col = v[:, 0].astype(np.int64)
    o = tex[row, col, :3] * (f32(1) - a) + tex[np.minimum(row + 1, tex_h - 1), col, :3] * a
    ox = o[:, 0] * np.sign(v[:, 4])
    return np.stack([v[:, 2] * ox - v[:, 3] * o[:, 1], v[:, 3] * ox + v[:, 2] * o[:, 1], np.abs(v[:, 4]) * o[:, 2]], 1)


def pose_preview(objects, t, loop_rate=HW_BPM / 120.0):
    """Move the crowd objects' vertices to their animated positions at time t (s), e.g. for preview renders AFTER the
    bake and the FBX export. The first call remembers the current (frame-0) positions - so transforms applied after
    build_crowd2() (the stage drop) are kept; pose_preview(objects, None) restores them. loop_rate = BPM / 120 (default:
    the Halloween set, 140 BPM)."""
    for ob in objects:
        entry = _POSE[ob.name]
        if entry[0] is None:
            co = np.empty(len(ob.data.vertices) * 3, dtype=np.float32)
            ob.data.vertices.foreach_get("co", co)
            entry[0] = co.reshape(-1, 3).astype(np.float64)
        rest, vdata = entry
        pos = rest if t is None else rest + wpo_blender(vdata, t, _VAT["tex_half"], loop_rate)
        ob.data.vertices.foreach_set("co", pos.astype(np.float32).ravel())
        ob.data.update()
        if t is None:
            entry[0] = None
