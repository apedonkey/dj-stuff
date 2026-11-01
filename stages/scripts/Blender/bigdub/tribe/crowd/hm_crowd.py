# HARVEST MOON crowd ("hm_crowd"): the Thanksgiving crowd (Blender 4.5), a copy of MIDTOWN's crowd
# (../../christmas/crowd/xm_crowd.py, the newest copy of the Dino Stage's Crowd V3 ../../crowd2/crowd3.py by way of
# Graveyard's hw_crowd.py; none of them is edited from here) with its Christmas layer replaced by a Thanksgiving +
# visitor one and the field laid out for the crop circle. Same contract as crowd3 / hw_crowd / xm_crowd:
#
#   import hm_crowd
#   crowd, glow, extras = hm_crowd.build_crowd2(rng, exclude, extra)       # drop-in for crowd3.build_crowd2()
#
# * Procedural people (no third-party assets): crowd3's lofted bodies, body types, faces and hair, dressed for a farm
#   field on a late-November night: flannel shirts (a check by vertex colour), denim jackets and jeans, dark jackets,
#   hoodies, puffer vests, work boots, in a dark autumn palette (rust, mustard, olive, brown, navy, charcoal, black).
#   Hats: pilgrim hats (a black capotain: a tall flat-topped crown, a band and a buckle), plush turkey hats (a brown
#   body, a fan of feathers behind, a little red-wattled head over the brow), tinfoil hats (a crumpled cone or dome),
#   straw farmer and cowboy hats and green alien masks (big black almond eyes); the rest bare heads, beanies and caps.
#   Pilgrims, turkeys, aliens, farmers in bib overalls and tinfoil crews; a few green inflatable aliens (mid tier).
#   Friend groups often dress alike.
# * Glowing bits (their own mesh, emissive vertex colour) in green, gold and warm white: glowsticks, glow necklaces, LED
#   gloves and shoes, flow toys; phones with cold-white screens. No red, magenta or cyan. Totems: inflatable aliens on
#   poles (glowing green, black eyes), giant turkey legs, corn cobs (glowing yellow kernels) and flags.
# * Three detail tiers by distance from the DJ (near < 12 m, mid < 18.5 m, far beyond), one rig, crowd3's 17 dance
#   clips (shuffle and heart in the slots Graveyard gave its zombie "lurch" and Thriller "claw"; pose() still knows
#   those two), so the VAT keeps its 2048 x 1024 layout; every tier has one "superset" canonical mesh holding every
#   optional part, so the VAT stays one texture (columns = superset vertices; rows = (page * 17 + clip) * 29 + frame:
#   the near tier fills page 0, mid + far page 1, so every column index stays below 2048, exact in 16-bit UVs). The VAT
#   stores offsets from each clip's frame 0, and every person's base mesh is posed at frame 0 of their clip (and
#   morphed to their body type). Tempo: the DJ plays 140 BPM half-time dubstep, so ~65 % of the beat-locked dancers run
#   at half time.
# * The field: the apron in front of the bale barrier (x -34..34, y -16..-7.5) joined to the crop circle C0 (centre
#   (0, -38), radius 31), every root 0.5 m inside it and behind y -8.35 (no hand reaches into the bales); standing corn
#   all round; roots at least 0.4 m apart. Dense at the barrier,
#   thinning toward the back of the circle and toward the corn; round the hay-wagon FOH at (0, -52); people under the
#   tractor beam (r 12 m round the circle's centre) reach up for it. Friend groups, couples, people on friends'
#   shoulders, filmers, totems. Headbang / pump / jump up front, sway / nod / filming further back.
# * Per person (UV channels): VAT column, clip, yaw/scale, mirror, phase, playback rate, root. UV0 = per-person lighting
#   cell (bigger for nearer tiers); "Col" = albedo per part (patterns per vertex: flannel checks, quilting, stripes,
#   feather fans).
# Space: meters, Z up, the DJ at the origin facing -Y; the crowd stands on z = GROUND_Z (the main script drops it later).
import json
import math
import os
import random
import struct
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
HM_DIR = os.path.dirname(HERE)                                  # Scripts/Blender/harvest
GROUND_Z = -1.5
FPS, FRAMES = 30, 28                       # one clip = 28 samples = 2 beats (any tempo: LoopRate = BPM / 120)
ROWS = FRAMES + 1                          # + a copy of frame 0: the material's frame lerp never wraps
CLIPS = ("jump", "jumppump", "pump", "handsup", "wave", "clap", "sway", "twostep", "shuffle", "headbang", "nod",
         "heart", "hold", "talk", "carry", "ride", "flow")   # crowd3's clips (Graveyard's lurch and claw: swap them
#                                                             into the slots of shuffle and heart; pose() knows all 19)
AUTHORED_BPM, BEATS_PER_CLIP = 128.0, 2
HM_BPM = 140.0                             # the Thanksgiving set tempo: material LoopRate = HM_BPM / 120
UE_AXIS = (100.0, -100.0, 100.0)           # Blender m -> Unreal local cm (our FBX path mirrors Y; verified in the editor)
UE_FLIPS_V = True                          # Unreal's FBX importer stores 1 - V (verified in the fork editor 2026-10-05)
H = 1.75                                   # canonical body height (per person sz scales it)
VAT_LAYOUT = {"UV0 UVMap": "baked-lighting cell", "UV1 VatIndex": "x = VAT column, y = page * 17 + clip",
              "UV2 VatRotScale": "x = sx cos(yaw), y = sx sin(yaw)", "UV3 VatScalePhase": "x = mirror * sz, y = phase",
              "UV4 VatRate": "x = playback rate (1 = authored tempo)",
              "UV5 VatPivot": "x, y = the dancer's root (Blender m; v7: the crowd makes way round the player)"}
DATA_UVS = ("VatIndex", "VatRotScale", "VatScalePhase", "VatRate", "VatPivot")


def log(msg):
    print("[HMCROWD] " + msg, flush=True)


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
ITEM_REGIONS = ("hair", "hat", "hat2", "hat3", "feather", "wattle", "mask", "mask_eye", "goggles", "scarf", "ialien",
                "ialien2", "ialien3", "pack", "strap", "tutu", "warmer", "phone", "pole", "flag1", "flag2", "tleg",
                "tbone", "husk", "staff")
GLOW_LIST = ("glow_screen", "glow_flash", "glow_stick", "glow_necklace", "glow_glove", "glow_shoe", "glow_fan",
             "glow_hoop", "glow_poi", "glow_staff", "glow_alien", "glow_corn", "glow_antenna", "glow_hand",
             "glow_chest")
REGIONS = BODY_REGIONS + ITEM_REGIONS + GLOW_LIST
REG = {r: i for i, r in enumerate(REGIONS)}
GLOW_REGIONS = {REG[r] for r in GLOW_LIST}


SKINS = [(0.85, 0.66, 0.53), (0.80, 0.58, 0.45), (0.72, 0.52, 0.38), (0.62, 0.42, 0.29), (0.50, 0.32, 0.21),
         (0.38, 0.23, 0.14), (0.27, 0.16, 0.10), (0.18, 0.11, 0.07), (0.88, 0.72, 0.62), (0.68, 0.50, 0.40)]
HAIR_NATURAL = [(0.012, 0.009, 0.007)] * 6 + [(0.04, 0.025, 0.014)] * 4 + [(0.12, 0.07, 0.03)] * 2 + [
    (0.45, 0.33, 0.15), (0.60, 0.48, 0.26), (0.35, 0.10, 0.03), (0.55, 0.53, 0.50)]
# Thanksgiving palette (plan section 6): the clothes stay dark autumn (rust, mustard, olive, brown, navy, charcoal,
# black); the hats and costumes carry the theme; the glow is the visitor's green, the farm's gold and warm white (no
# red, magenta or cyan). Linear RGB.
HAIR_DYED = [(0.45, 0.10, 0.02), (0.85, 0.80, 0.70), (0.10, 0.40, 0.08), (0.70, 0.45, 0.12), (0.08, 0.04, 0.16),
             (0.35, 0.06, 0.03)]                                # copper, platinum, alien green, honey, dark violet, auburn
BLACK = (0.012, 0.012, 0.014)
RUST, MUSTARD, OLIVE, BROWN = (0.20, 0.050, 0.018), (0.30, 0.19, 0.025), (0.070, 0.080, 0.022), (0.080, 0.040, 0.016)
NAVY, CHARCOAL, FOREST = (0.012, 0.022, 0.075), (0.045, 0.045, 0.050), (0.012, 0.050, 0.020)
CREAM = (0.70, 0.64, 0.52)                                      # pilgrim collars, sherpa linings, the turkey leg's bone
GOLD, SILVER = (0.80, 0.56, 0.12), (0.62, 0.62, 0.66)
ALIEN_GREENS = [(0.10, 0.30, 0.05), (0.14, 0.38, 0.07), (0.07, 0.22, 0.05)]
INFLATABLE_GREEN = (0.12, 0.42, 0.07)
BRIGHTS = [RUST, MUSTARD, (0.42, 0.13, 0.03), CREAM, GOLD, ALIEN_GREENS[1]]    # + burnt orange, alien green
COATS = [BLACK] * 4 + [NAVY, CHARCOAL, (0.065, 0.065, 0.070), OLIVE, BROWN, (0.11, 0.030, 0.014), FOREST]
#                                                                black, navy, charcoal, olive, brown, oxblood, forest
DARKS = COATS
MUTED = [(0.30, 0.20, 0.10), (0.24, 0.24, 0.26), CREAM, (0.17, 0.19, 0.10), (0.25, 0.08, 0.04), (0.30, 0.33, 0.40)]
#                                                                camel, grey, cream, sage, brick, slate
DENIMS = [(0.05, 0.08, 0.18), (0.10, 0.15, 0.30), (0.25, 0.35, 0.50)]
EARTH = [(0.28, 0.25, 0.16), (0.15, 0.17, 0.08), (0.25, 0.18, 0.10), (0.18, 0.18, 0.19)]
WORKBOOTS = [(0.30, 0.18, 0.07), (0.22, 0.12, 0.05), (0.12, 0.07, 0.03)]      # wheat, tan, dark brown
FLANNELS = [(RUST, (0.07, 0.018, 0.008), BLACK), (OLIVE, (0.025, 0.030, 0.010), BLACK), (NAVY, FOREST, BLACK),
            (MUSTARD, BROWN, (0.030, 0.015, 0.006)), ((0.18, 0.18, 0.19), CHARCOAL, BLACK),
            ((0.25, 0.04, 0.03), NAVY, BLACK), ((0.45, 0.40, 0.32), RUST, BROWN)]
#                                     (base, stripe, crossing): buffalo check, green, navy-green, mustard, grey, red-navy,
#                                     cream
STRAWS = [(0.52, 0.40, 0.17), (0.45, 0.34, 0.14), (0.60, 0.48, 0.24)]
FLAGS = [RUST, MUSTARD, OLIVE, ALIEN_GREENS[1], CREAM, (0.42, 0.13, 0.03), BLACK]
GLOW_COLS = {"green": (0.15, 1.0, 0.25), "gold": (1.0, 0.60, 0.16), "white": (1.0, 0.86, 0.64)}
GLOW_W = (0.45, 0.30, 0.25)                                     # the visitor's green carries it, gold and warm white
GLOWS = list(GLOW_COLS.values())
TURKEY_BROWNS = [(0.13, 0.060, 0.025), (0.18, 0.090, 0.035), (0.10, 0.050, 0.020)]
FEATHERS = [(0.16, 0.070, 0.025), (0.28, 0.090, 0.025), (0.09, 0.045, 0.018)]   # the fan's lobes in turn
FEATHER_TIPS = [CREAM, (0.55, 0.38, 0.12), (0.62, 0.30, 0.06)]                  # cream, honey or orange tips
WATTLE, BEAK = (0.50, 0.030, 0.020), (0.70, 0.40, 0.060)


def hm_glow(rng):
    return rng.choices(GLOWS, weights=GLOW_W)[0]


def top_color(rng):
    """A jacket, hoodie or shirt colour: mostly dark, some muted (no cream), a few autumn brights."""
    k = rng.random()
    return rng.choice(COATS if k < 0.82 else MUTED[:2] + MUTED[3:] if k < 0.94 else BRIGHTS[:3] + BRIGHTS[4:])


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
    lifted toward the viewer (the inflatable Santa's eyes, buckle and front trim)."""
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
FOIL_JIT = (0.10, -0.07, 0.04, -0.10, 0.08, -0.03, 0.06, -0.08, 0.02, -0.05, 0.09)   # the tinfoil's crumples


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


def almond(cx, cz, hw, hh, tilt, n=6):
    """An almond (an alien's eye) for glyph(): n points (x, z) round (cx, cz), hw / hh the half-width / half-height,
    pointed at both ends, turned `tilt` degrees (positive lifts the +x end)."""
    ca, sa = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        x, z = hw * math.cos(a), hh * math.sin(a)
        pts.append((cx + x * ca - z * sa, cz + x * sa + z * ca))
    return pts


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
    g.named["torso"] = tisl
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
    g.named["head"] = g.island(2 * math.pi * 0.093, 0.112 * math.pi)
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
        if d["one_box_shoes"]:
            g.box(V3(an.x, 0.03, 0.045), (0.095, 0.26, 0.09), Matrix.Identity(3), "b_legs", "shoe", {ft: 1.0}, taper=(0.85, 0.6))
        else:
            g.box(V3(an.x, 0.035, 0.022), (0.098, 0.275, 0.044), Matrix.Identity(3), "b_legs", "sole", {ft: 1.0},
                  taper=(0.85, 1.0))
            g.box(V3(an.x, 0.02, 0.068), (0.09, 0.2, 0.06), Matrix.Identity(3), "b_legs", "shoe", {ft: 1.0}, taper=(0.9, 0.6))


# ---------------------------------------------------------------------------- head wear
def add_head_wear(g, d):
    hc, hw, segs = HC, {"head": 1.0}, d["hair_segs"]

    def dome(part, reg, scale, zmin, front_cut=0.0, extra_back=0.0, strands=False, face_open=False, front=0.0):
        def deform(u, p):
            q = p.copy()
            if front and u.y > 0:                                     # the upper front pushed out over the raised
                q.y += front * u.y * min(1.0, max(0.0, (u.z - 0.15) / 0.25))   # hairline (not the rim)
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
    # hats: a shared crown shell (beanie, cap, foil dome) + brim / pompom; the brimmed hats (pilgrim, straw farmer,
    # straw cowboy), the plush turkey, the foil cone and the alien mask. One hat per person, so the big hats share the
    # three "cow_" islands.
    dome("hat_dome", "hat", 1.23, 0.03, front=0.012)                  # crowd3: 1.19 (its raised hairline poked through)
    brim = [hc + V3(x, y, 0.035 - 0.02 * max(0.0, y - 0.1) / 0.08) for x, y in ((-0.08, 0.08), (0.08, 0.08), (0.075, 0.195),
                                                                              (-0.075, 0.195))]   # crowd3: to 0.18
    g.face_toward([g.vert(q, hw) for q in brim], V3(0, 0, 1), "hat_brim", "hat2")
    g.face_toward([g.vert(q - V3(0, 0, 0.004), hw) for q in brim], V3(0, 0, -1), "hat_brim", "hat2")
    g.octa(hc + V3(0, -0.01, 0.15), 0.03, "hat_pom", "hat2", hw)
    cseg = max(6, segs - 4)
    g.named["cow_crown"] = g.island(math.pi * 2 * 0.11, 0.2)
    g.named["cow_top"] = g.island(2 * math.pi * 0.21, 0.08)
    g.named["cow_under"] = g.island(2 * math.pi * 0.21, 0.08)

    def brimmed(part, crown, crown_r, outer_c, outer_r, rim=None, band=None):
        """A crown (a limb up through `crown`, radii crown_r, a flat top) on a brim from its foot out to a ring round
        outer_c (outer_r = side, front, back radii; `rim` shapes it), two-sided (the underside 5 mm lower). band =
        (region, height, proud): a band round the crown's foot, `proud` out at the bottom, its top tucked into the
        crown."""
        cr = limb(g, crown, crown_r, [hw] * len(crown), cseg, part, ["hat"] * (len(crown) - 1), cap_end=True,
                  isl=g.named["cow_crown"])
        cout = g.ring(outer_c, V3(1, 0, 0), V3(0, 1, 0), *outer_r, cseg, hw, shape=rim)
        g.bridge(cout, cr[0], part, "hat2", g.named["cow_top"], 0.0, 1.0)                           # top: faces up
        ci = [g.vert(g.v[i] - V3(0, 0, 0.005), hw) for i in cr[0]]
        co_ = [g.vert(g.v[i] - V3(0, 0, 0.005), hw) for i in cout]
        g.bridge(ci, co_, part, "hat2", g.named["cow_under"], 0.0, 1.0)                             # under: down
        if band:
            reg, bh, proud = band
            r0, r1 = crown_r[0] + proud, crown_r[0] + (crown_r[1] - crown_r[0]) * bh / (crown[1] - crown[0]).length - 0.002
            lo = g.ring(crown[0], V3(1, 0, 0), V3(0, 1, 0), r0, r0, r0, cseg, hw)
            hi = g.ring(crown[0] + V3(0, 0, bh), V3(1, 0, 0), V3(0, 1, 0), r1, r1, r1, cseg, hw)
            g.bridge(lo, hi, part, reg, g.island(2 * math.pi * r0, bh), 0.0, 1.0)
    # pilgrim hat (a capotain): a tall crown with a flat top, a flat brim, a band and a square buckle on the front (its
    # own part: a box's flat top and bottom are not brim faces), leaning back with the band
    pc0 = hc + V3(0, -0.004, 0.030)
    brimmed("pilgrim_hat", [pc0, hc + V3(0, -0.004, 0.245)], [0.116, 0.094], hc + V3(0, -0.004, 0.027),
            (0.19, 0.195, 0.19), band=("hat2", 0.040, 0.005))
    g.box(pc0 + V3(0, 0.1185, 0.020), (0.048, 0.008, 0.036), Matrix.Rotation(math.radians(15), 3, "X"), "pilgrim_buckle",
          "hat3", hw)
    # straw farmer hat: a low round crown, a wide brim drooping a little at the front and back, a band
    brimmed("hat_farmer", [hc + V3(0, -0.004, 0.045), hc + V3(0, -0.004, 0.150)], [0.114, 0.100],
            hc + V3(0, -0.004, 0.028), (0.235, 0.245, 0.235), rim=lambda p, a: p + V3(0, 0, -0.012 * math.sin(a) ** 2),
            band=("hat3", 0.030, 0.004))

    def curl(p, a):                                                   # sides of the brim turned up
        return p + V3(0, 0, 0.045 * abs(math.cos(a)) ** 3)
    brimmed("hat_cowboy", [hc + V3(0, -0.004, 0.05), hc + V3(0, -0.004, 0.19)], [0.112, 0.090],
            hc + V3(0, -0.004, 0.035), (0.22, 0.20, 0.19), rim=curl, band=("hat3", 0.028, 0.007))
    if d["detail"] == "near":                                           # (ski) goggles pushed up on the forehead
        g.box(hc + V3(0, 0.072, 0.07), (0.15, 0.03, 0.045), Matrix.Rotation(math.radians(20), 3, "X"), "goggles", "goggles", hw)
    # plush turkey hat: a round brown body over the head (open at the brow), a fan of feathers standing up behind it,
    # the neck and a little head over the brow with a beak and a red wattle (and eyes, near)
    near = d["detail"] == "near"
    g.ellipsoid(hc + V3(0, -0.012, 0.030), (0.108, 0.135, 0.155), d["turkey_segs"], d["turkey_rings"], "turkey_hat",
                "hat", hw, zmin=0.0, close_bottom=False, isl=g.named["cow_crown"])
    lean = math.radians(18)                                           # the fan's plane leans back
    up, side = V3(0, -math.sin(lean), math.cos(lean)), V3(1, 0, 0)
    back = side.cross(up)                                             # the fan's back side (-Y, down a little)
    fb, prof, nl = hc + V3(0, -0.105, 0.080), d["turkey_lobe"], d["turkey_lobes"]
    fisl = g.island(0.09 * nl, 0.36)
    for k in range(nl):                                               # lobes: colours in turn (pj = lobe), pale tips
        a = math.radians(14 + 152 * k / (nl - 1))                     # (pat = 1); every other one 4 mm further back
        dv, pv = side * math.cos(a) + up * math.sin(a), side * -math.sin(a) + up * math.cos(a)
        base = fb + back * (0.004 if k % 2 else 0.0)
        for b_, toward in ((0, -back), (1, back)):                    # the front face, then its twin 3 mm behind
            vs = [g.vert(base + dv * r + pv * t + back * (0.003 * b_), hw, tip, k) for r, t, tip in prof]
            uv = [((k + 0.5 + t / 0.09) / nl, (b_ + (r - 0.04) / 0.19) / 2) for r, t, _ in prof]
            g.face_toward(vs, toward, "turkey_hat", "feather", uv, fisl)
    th = hc + V3(0, 0.160, 0.140)                                     # the turkey's head
    if near:
        limb(g, [hc + V3(0, 0.098, 0.100), hc + V3(0, 0.140, 0.125)], [0.026, 0.022], [hw, hw], 6, "turkey_hat",
             ["hat2"], isl=g.named["cow_under"])                      # (its foot 1 cm inside the body, clear of hair)
        g.ellipsoid(th, (0.030, 0.036, 0.032), 6, 3, "turkey_hat", "hat2", hw)
        for s in (1, -1):
            g.octa(th + V3(s * 0.026, 0.018, 0.010), 0.0065, "turkey_hat", "mask_eye", hw)
    else:
        g.octa(th, 0.034, "turkey_hat", "hat2", hw)
    g.box(th + V3(0, 0.040, -0.004), (0.020, 0.030, 0.014), Matrix.Identity(3), "turkey_hat", "hat3", hw, taper=(0.3, 0.3))
    limb(g, [th + V3(0, 0.030, -0.014), th + V3(0, 0.034, -0.052)], [0.011, 0.005], [hw, hw], 4, "turkey_hat",
         ["wattle"], cap_end=True)
    # tinfoil hat: a crumpled silver cone; every ring jittered and turned a little (no two facets alike), the base ring
    # pushed outward only (it clears the hair)
    fs, frs = d["foil_segs"], []
    for k, (o, r) in enumerate(d["foil_path"]):
        jit = [FOIL_JIT[(3 * j + 5 * k) % len(FOIL_JIT)] for j in range(fs)]
        frs.append(g.ring(hc + o, V3(1, 0, 0), V3(0, 1, 0), r, r, r, fs, hw, phase=0.35 * k,
                          jitter=[abs(v) for v in jit] if k == 0 else jit))
    for k in range(len(frs) - 1):
        g.bridge(frs[k], frs[k + 1], "foil_cone", "hat", g.named["cow_crown"], k / (len(frs) - 1), (k + 1) / (len(frs) - 1))
    g.cap(frs[-1], "foil_cone", "hat", isl=g.named["cow_crown"], v=1.0)
    # alien mask: a green head over the whole head (a big cranium narrowing to the chin, open at the neck), big black
    # almond eyes slanting up and out (glyphs on its front)
    ms, mr = d["mask_segs"], d["mask_rings"]
    mrings = [g.ring(hc + V3(0, 0.004, z), V3(1, 0, 0), V3(0, 1, 0), rx, ryf, ryb, ms, hw, phase=math.pi / ms)
              for z, rx, ryf, ryb in mr]
    vz = [(z - mr[0][0]) / (mr[-1][0] - mr[0][0]) for z, *_ in mr]
    for k in range(len(mrings) - 1):
        g.bridge(mrings[k], mrings[k + 1], "alien_mask", "mask", g.named["cow_crown"], vz[k], vz[k + 1])
    g.cap(mrings[-1], "alien_mask", "mask", isl=g.named["cow_crown"], v=1.0)
    ex, ez, ew, eh, en = d["mask_eye"]
    for s in (1, -1):
        glyph(g, ["alien_mask"], almond(s * ex, hc.z + ez, ew, eh, s * 22, en), hw, "alien_mask", "mask_eye")


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
    # tutu: a ruffled skirt flaring from the hips (two-sided; the pilgrim skirt)
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
    # totem pole upright through the right fist + a flag, an inflatable alien, a giant turkey leg or a corn cob on top;
    # all of them inside Midtown's flag / sign / star envelope (0.56 m over the pole's top, 0.95 m to the side), so the
    # VAT offsets stay where they were
    top_ = gR + V3(0, 0, 1.95)
    limb(g, [gR + V3(0, 0, -0.25), top_], [0.016, 0.014], [hwR, hwR], d["pole_segs"], "pole", ["pole"], cap_end=True)
    for z0, z1, reg in ((0.0, -0.32, "flag1"), (-0.32, -0.62, "flag2")):
        q = [top_ + V3(dx, 0, dz) for dx, dz in ((0.02, z0), (0.95, z0 - 0.04), (0.95, z1 - 0.04), (0.02, z1))]
        quad2(g, q, "flag", reg, hwR, V3(0, 1, 0))
    ts_, tr_ = d["totem_segs"], d["totem_rings"]
    # the inflatable alien (glow mesh, green): an egg head (a wide cranium, the chin narrowing), a little body, arms up;
    # its black almond eyes sit 8 mm in front of the head, placed on the egg directly (glyph() reads non-glow faces only)
    ac, ar = top_ + V3(0, 0, 0.34), (0.15, 0.13, 0.18)

    def egg(u, p, c_=ac, kx=0.45, ky=0.2):                            # below the middle: narrower toward the chin
        k = max(0.0, -u.z)
        return V3(c_.x + (p.x - c_.x) * (1 - kx * k), c_.y + (p.y - c_.y) * (1 - ky * k), p.z)
    g.ellipsoid(ac, ar, ts_, tr_, "talien", "glow_alien", hwR, deform=egg)
    g.ellipsoid(top_ + V3(0, 0, 0.06), (0.075, 0.065, 0.11), max(4, ts_ - 2), 3, "talien", "glow_alien", hwR)

    def on_egg(x, z):                                                 # the egg's front at (x, z), 8 mm out
        t = (z - ac.z) / ar[2]
        k = max(0.0, -t)
        ux = (x - ac.x) / (ar[0] * (1 - 0.45 * k))
        return V3(x, ac.y + ar[1] * (1 - 0.2 * k) * math.sqrt(max(0.0, 1 - t * t - ux * ux)) + 0.008, z)
    for s in (1, -1):
        limb(g, [top_ + V3(s * 0.05, 0, 0.10), top_ + V3(s * 0.15, 0.02, 0.15), top_ + V3(s * 0.20, 0.03, 0.26)],
             [0.022, 0.018, 0.014], [hwR] * 3, 4, "talien", ["glow_alien"] * 2, cap_end=True)
        g.face_toward([g.vert(on_egg(x, z), hwR) for x, z in almond(ac.x + s * 0.055, ac.z - 0.01, 0.048, 0.022,
                                                                     s * 22, 6 if near else 4)],
                      V3(0, 1, 0), "talien", "mask_eye")
    # the giant turkey leg: a roast drumstick (a teardrop, thin end down) on the pole, the bone out of its foot, two
    # knuckles at its end
    lc = top_ + V3(0, 0, 0.28)
    g.ellipsoid(lc, (0.13, 0.12, 0.19), ts_, tr_, "tleg", "tleg", hwR,
                deform=lambda u, p: egg(u, p, lc, 0.55, 0.55))
    limb(g, [top_ + V3(0, 0, 0.12), top_ + V3(0, 0, -0.06)], [0.030, 0.026], [hwR, hwR], max(4, ts_ - 2), "tleg",
         ["tbone"])
    for s in (1, -1):
        g.octa(top_ + V3(s * 0.028, 0, -0.08), 0.036, "tleg", "tbone", hwR)
    # the corn cob: an ear of glowing kernels (a check of two yellows) in three green husk leaves peeling off its foot
    g.ellipsoid(top_ + V3(0, 0, 0.27), (0.07, 0.07, 0.22), ts_, d["corn_rings"], "corn", "glow_corn", hwR)
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.5
        o, tg = V3(math.cos(a), math.sin(a), 0), V3(-math.sin(a), math.cos(a), 0)
        leaf = [top_ + o * r + tg * w + V3(0, 0, z) for r, w, z in ((0.035, -0.035, 0.05), (0.035, 0.035, 0.05),
                                                                     (0.09, 0.03, 0.17), (0.13, 0.0, 0.26),
                                                                     (0.09, -0.03, 0.17))]
        quad2(g, leaf, "corn", "husk", hwR, o * 0.91 - V3(0, 0, 0.41))
    # inflatable alien suit (mid tier only, as Midtown's inflatable Santa: it reads from 12-20 m): a round green body, a
    # huge egg head with big black almond eyes, antennae with glowing tips, long thin arms with darker hands, puffy legs
    # to mid-shin over the person's legs (their boots show below)
    if not near:
        sw_ = {"spine1": 0.5, "spine2": 0.5}
        g.ellipsoid(V3(0, 0.03, 1.12), (0.34, 0.31, 0.50), 8, 5, "ialien", "ialien", sw_)
        hcs = V3(0, 0.06, 1.86)
        g.ellipsoid(hcs, (0.26, 0.23, 0.27), 8, 5, "ialien", "ialien", {"head": 1.0},
                    deform=lambda u, p: egg(u, p, hcs, 0.40, 0.15))
        for s in (1, -1):
            glyph(g, ["ialien"], almond(s * 0.10, hcs.z - 0.01, 0.085, 0.040, s * 24), {"head": 1.0}, "ialien",
                  "ialien2")
            tip = hcs + V3(s * 0.16, -0.02, 0.42)                       # antennae: a stalk and a glowing ball
            limb(g, [hcs + V3(s * 0.08, -0.02, 0.22), tip], [0.014, 0.010], [{"head": 1.0}] * 2, 4, "ialien",
                 ["ialien"], cap_end=True)
            g.octa(tip + V3(0, 0, 0.02), 0.035, "ialien", "glow_antenna", {"head": 1.0})
        for s in (1, -1):                                               # long thin arms, darker hands
            ap = [V3(s * 0.30, 0.05, 1.40), V3(s * 0.42, 0.10, 1.16), V3(s * 0.44, 0.16, 0.92)]
            limb(g, ap, [0.070, 0.058, 0.048], [{"spine2": 1.0}] * 3, 6, "ialien", ["ialien", "ialien"], cap_end=True)
            g.octa(ap[-1] + V3(0, 0.02, -0.06), 0.060, "ialien", "ialien3", {"spine2": 1.0})
        for s in (1, -1):                                               # puffy legs to mid-shin over the person's legs
            n = "R" if s > 0 else "L"
            limb(g, [J[f"hip.{n}"] + V3(0, 0, -0.05), J[f"knee.{n}"], J[f"knee.{n}"].lerp(J[f"ankle.{n}"], 0.35)],
                 [0.15, 0.12, 0.10], [{f"thigh.{n}": 1.0}, {f"thigh.{n}": 0.5, f"shin.{n}": 0.5}, {f"shin.{n}": 1.0}], 6,
                 "ialien", ["ialien", "ialien"], cap_end=True)


def add_scarf(g, d):
    """A knitted scarf, a roll round the neck on the shoulder slope (as many sides as the torso, so it stays a constant
    gap outside it; the middle ring bulges; the side vertices shrug with the shoulders as the torso's do) and, near, one
    end hanging down the chest (a strip drawn on the torso, 1 cm proud)."""
    ss = d["torso"]

    def low_w(p):                                                     # the torso's shoulder weights (add_body)
        w = {"spine2": 1.0}
        if abs(p.x) > 0.09:
            w = lerpw(w, {f"clav.{'R' if p.x > 0 else 'L'}": 1.0}, 0.35)
        return w
    wts = (low_w, {"spine2": 0.75, "neck": 0.25}, {"spine2": 0.35, "neck": 0.5, "head": 0.15})   # the top gives way
    #                                                                   to the chin (headbang)
    spec = d["scarf_rings"]
    wts = wts if len(spec) == 3 else (wts[0], wts[2])
    rings = [g.ring(V3(0, -0.004, z), V3(1, 0, 0), V3(0, 1, 0), rx, ryf, ryb, ss, w, phase=math.pi / ss)
             for (z, rx, ryf, ryb), w in zip(spec, wts)]
    isl = g.island(2 * math.pi * 0.12, 0.09)
    nr = len(rings)
    for k in range(nr - 1):
        g.bridge(rings[k], rings[k + 1], "scarf", "scarf", isl, k / (nr - 1), (k + 1) / (nr - 1))
    if d["detail"] == "near":
        rows = []
        for k, z in enumerate((1.45, 1.34, 1.23)):
            rows.append([g.vert(g.surface(["b_torso"], V3(x, 1.0, z), V3(0, -1, 0), 0.010), torso_w(z), pat=k % 2)
                         for x in (0.032, 0.102)])
        f0 = len(g.f)
        hisl = g.island(0.07, 0.22)
        for k in range(len(rows) - 1):
            uv = ((0.0, 1 - k / 2), (1.0, 1 - k / 2), (1.0, 1 - (k + 1) / 2), (0.0, 1 - (k + 1) / 2))
            g.face_toward((rows[k][0], rows[k][1], rows[k + 1][1], rows[k + 1][0]), V3(0, 1, 0), "scarf", "scarf", uv,
                          hisl)
        g.clear_out(range(f0, len(g.f)), ["b_torso"], gap=0.008)


def add_far_body(g):
    """~21 tris: a 3-sided column (feet -> hips -> shoulders, a flat face to the stage), a pyramid head, two arm ribbons;
    plus a pole with a flag or a totem cut-out (holders), glow quads at the hand and the chest, and the hats as flat
    cut-outs in front of the head."""
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
    hw_ = {"head": 1.0}

    def bill(c, y, pts, part, reg, w, tags=None):                     # a one-sided polygon facing the stage
        g.face_toward([g.vert(c + V3(dx, y, dz), w, *(tags[k] if tags else (0, 0))) for k, (dx, dz) in enumerate(pts)],
                      V3(0, 1, 0), part, reg)
    # the hats, in front of the head: the pilgrim's tall crown, brim and buckle; the turkey's feather fan (behind; lobe
    # colours and a pale top through pj / pat, as near), its body, head and wattle; the foil cone; the straw brim and crown
    bill(hc, 0.070, ((-0.088, 0.06), (0.088, 0.06), (0.072, 0.30), (-0.072, 0.30)), "far_pilgrim", "hat", hw_)
    bill(hc, 0.074, ((-0.16, 0.045), (0.16, 0.045), (0.16, 0.072), (-0.16, 0.072)), "far_pilgrim", "hat2", hw_)
    bill(hc, 0.078, ((-0.028, 0.074), (0.028, 0.074), (0.028, 0.104), (-0.028, 0.104)), "far_pilgrim", "hat3", hw_)
    bill(hc, 0.055, ((-0.10, 0.06), (0.10, 0.06), (0.236, 0.142), (0.17, 0.27), (0.0, 0.34), (-0.17, 0.27),
                     (-0.236, 0.142)), "far_turkey", "feather", hw_,
         tags=((0, 0), (0, 1), (0, 2), (0, 0), (1, 1), (0, 2), (0, 0)))
    bill(hc, 0.072, ((-0.11, 0.05), (0.11, 0.05), (0.12, 0.12), (0.06, 0.18), (-0.06, 0.18), (-0.12, 0.12)),
         "far_turkey", "hat", hw_)
    bill(hc, 0.080, ((-0.025, 0.14), (0.025, 0.14), (0.025, 0.19), (-0.025, 0.19)), "far_turkey", "hat2", hw_)
    bill(hc, 0.082, ((-0.012, 0.105), (0.012, 0.105), (0.012, 0.142), (-0.012, 0.142)), "far_turkey", "wattle", hw_)
    bill(hc, 0.072, ((-0.10, 0.06), (0.10, 0.06), (0.025, 0.32)), "far_foil", "hat", hw_)
    bill(hc, 0.070, ((-0.10, 0.07), (0.10, 0.07), (0.09, 0.17), (-0.09, 0.17)), "far_straw", "hat", hw_)
    bill(hc, 0.076, ((-0.24, 0.03), (0.24, 0.03), (0.24, 0.09), (-0.24, 0.09)), "far_straw", "hat2", hw_)
    # the totems on the pole: the alien's glowing egg, the corn cob's glowing ear, the turkey leg (its bone, then meat)
    bill(top_, 0.03, ((0.0, 0.16), (0.08, 0.22), (0.13, 0.36), (0.07, 0.47), (-0.07, 0.47), (-0.13, 0.36), (-0.08, 0.22)),
         "far_talien", "glow_alien", hw)
    bill(top_, 0.03, ((0.0, 0.05), (0.06, 0.14), (0.065, 0.36), (0.0, 0.48), (-0.065, 0.36), (-0.06, 0.14)),
         "far_corn", "glow_corn", hw)
    bill(top_, 0.025, ((-0.025, -0.10), (0.025, -0.10), (0.025, 0.12), (-0.025, 0.12)), "far_tleg", "tbone", hw)
    bill(top_, 0.03, ((0.0, 0.09), (0.09, 0.20), (0.12, 0.32), (0.07, 0.45), (-0.07, 0.45), (-0.12, 0.32), (-0.09, 0.20)),
         "far_tleg", "tleg", hw)


DETAIL = {
    "near": {"detail": "near", "torso": 12, "torso_keep": {0, 1, 2, 3, 4, 5, 6, 7}, "neck": 8, "head_segs": 12,
             "head_rings": 8, "arm": 8, "arm_rings": 5, "leg": 8, "leg_rings": 6, "thumb": True, "hair_segs": 12,
             "hair_rings": 4, "pole_segs": 5, "face_detail": True, "hair_strands": True,
             "one_box_shoes": False, "tutu_segs": 14, "neck_segs": 10, "hoop_segs": 16,
             # Harvest parts, loose enough that the head and hair stay inside (checked). Turkey hat: the body's
             # segments and rings, the fan's lobes and their outline (along the lobe, across it, tip?); tinfoil cone:
             # (offset from the head centre, radius) from inside the band to the tip; alien mask: rings (z over the
             # head centre, side, front, back radius) from the neck opening up, the eyes (x, z, half-width,
             # half-height, points); totems: segments and rings
             "turkey_segs": 10, "turkey_rings": 4, "turkey_lobes": 6,
             "turkey_lobe": [(0.04, 0.0, 0), (0.13, -0.034, 0), (0.185, -0.027, 0), (0.215, 0.0, 1), (0.185, 0.027, 0),
                             (0.13, 0.034, 0)],
             "foil_segs": 8, "foil_path": [(V3(0.000, -0.006, 0.035), 0.124), (V3(0.004, -0.010, 0.120), 0.088),
                                           (V3(0.010, -0.016, 0.200), 0.048), (V3(0.022, -0.020, 0.262), 0.012)],
             "mask_segs": 10, "mask_rings": [(-0.115, 0.072, 0.090, 0.080), (-0.060, 0.088, 0.118, 0.108),
                                             (0.000, 0.104, 0.135, 0.130), (0.070, 0.114, 0.130, 0.130),
                                             (0.130, 0.094, 0.104, 0.106), (0.172, 0.048, 0.054, 0.056)],
             "mask_eye": (0.050, 0.006, 0.044, 0.021, 6),
             "totem_segs": 8, "totem_rings": 5, "corn_rings": 6,
             # scarf rings (z, rx, ry front, ry back): on the shoulder slope, bulging, round the neck
             "scarf_rings": [(1.462, 0.132, 0.077, 0.080), (1.492, 0.118, 0.096, 0.090), (1.518, 0.084, 0.080, 0.074)]},
    "mid": {"detail": "mid", "torso": 6, "torso_keep": {0, 1, 3, 4, 6, 7}, "neck": 0, "head_segs": 6, "head_rings": 4,
            "arm": 4, "arm_rings": 3, "leg": 4, "leg_rings": 3, "thumb": False, "hair_segs": 6, "hair_rings": 2,
            "pole_segs": 3, "face_detail": False, "hair_strands": False, "one_box_shoes": True,
            "tutu_segs": 8, "neck_segs": 6, "hoop_segs": 10,
            "turkey_segs": 6, "turkey_rings": 2, "turkey_lobes": 5,
            "turkey_lobe": [(0.04, 0.0, 0), (0.14, -0.042, 0), (0.215, 0.0, 1), (0.14, 0.042, 0)],
            "foil_segs": 6, "foil_path": [(V3(0.000, -0.006, 0.035), 0.128), (V3(0.006, -0.012, 0.150), 0.070),
                                          (V3(0.022, -0.020, 0.262), 0.012)],
            "mask_segs": 6, "mask_rings": [(-0.115, 0.078, 0.096, 0.086), (-0.030, 0.108, 0.140, 0.132),
                                           (0.070, 0.122, 0.138, 0.138), (0.150, 0.080, 0.088, 0.090)],
            "mask_eye": (0.048, 0.006, 0.042, 0.021, 4),
            "totem_segs": 6, "totem_rings": 4, "corn_rings": 4,
            "scarf_rings": [(1.462, 0.135, 0.080, 0.082), (1.515, 0.090, 0.088, 0.080)]},
}
BODY_PARTS = ("b_torso", "b_head", "b_arms", "b_legs")
OPTIONAL_PARTS = ("hair", "hair_long", "hair_pony", "hair_bun", "hair_braids", "hat_dome", "hat_brim", "hat_pom",
                  "hat_farmer", "hat_cowboy", "pilgrim_hat", "pilgrim_buckle", "turkey_hat", "foil_cone", "alien_mask",
                  "goggles", "scarf", "pack", "tutu", "warmers", "necklace", "gloves", "lightshoes", "phone",
                  "glowstick", "fan", "staff", "poi", "hoop", "pole", "flag", "talien", "tleg", "corn", "ialien",
                  "far_hand", "far_chest", "far_pilgrim", "far_turkey", "far_foil", "far_straw", "far_talien",
                  "far_tleg", "far_corn")
PARTS = BODY_PARTS + OPTIONAL_PARTS
PART = {p: i for i, p in enumerate(PARTS)}
TOTEM_PARTS = ("pole", "flag", "talien", "tleg", "corn")
HAIR_PARTS = ("hair", "hair_long", "hair_pony", "hair_bun", "hair_braids")
FAR_BILLBOARDS = ("b_arms", "pole", "flag", "far_hand", "far_chest", "far_pilgrim", "far_turkey", "far_foil",
                  "far_straw", "far_talien", "far_tleg", "far_corn")       # one-sided quads (far tier)


def build_canonical(tier):
    g = Geo()
    if tier == "far":
        add_far_body(g)
    else:
        add_body(g, DETAIL[tier])
        add_head_wear(g, DETAIL[tier])
        add_items(g, DETAIL[tier])
        add_scarf(g, DETAIL[tier])
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
        the torso by bone weight (tops, tutus, packs, straps, necklaces, scarves, braids), the limb fields the arm and
        leg tubes (+ leg warmers); the inflatable alien keeps its shape."""
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
        inflatable = self.V_part == PART["ialien"]
        for m_ in (sh, hp, bu, be):
            m_[inflatable] = 0.0
        lt = np.zeros((n, 3))                                         # limb thickness: radial from the bone axis
        lt_flare = np.zeros((n, 3))
        limbs = np.isin(self.V_part, [PART[q] for q in ("b_arms", "b_legs", "warmers")])
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
APRON = (-34.0, -16.0, 34.0, -7.5)                        # x0, y0, x1, y1 (hm_stage.APRON): the crowd's front, up to
#                                                           the bale barrier (y -7.5)
C0 = (0.0, -38.0, 31.0)                                   # the crop circle (hm_stage.C0): centre x, y, radius
EDGE = 0.5                                                # every root keeps this far inside the apron or the circle ...
Y_MAX = -8.35                                             # ... and behind this line: the bales' face is at y -7.775 and a
#                                                           low hand in "pump" reaches 0.48 m forward under their top
Y_FRONT, Y_BACK = -8.55, C0[1] - C0[2] + EDGE             # the first row (its jitter stays behind Y_MAX); the circle's back
FEATHER = 6.0                                             # people thin out over the last 6 m before the corn
MIN_GAP = 0.40                                            # roots at least this far apart: two torsos side by side need
#                                                           0.37 m (crowd3's rows put some 0.19 m apart)
FLOW_Y = -9.0                                             # flow toys stay behind this: a hoop sweeps 0.75 m round its
#                                                           dancer, and the bales' top (1 m) is lower than a swung staff
FOH_EXCLUDE = (-4.0, -56.0, 4.0, -48.0)                   # the hay-wagon FOH planned at (0, -52) and room round it:
#                                                           always kept out (set it to None to drop it)
BEAM_C, BEAM_R = (0.0, -38.0), 12.0                       # the tractor beam's foot (hm_stage BEAM_FOOT_R): people under
BEAM_CLIPS = {"handsup": 0.10, "wave": 0.05}              # it reach up for the ship (added to their zone's weights)
PERSON_CAP = 4608                                         # the walking map's people (hook/club_collide.h CC_MAXP)


def field_half(y):
    """Half-width of the crowd at depth y: the apron's or the circle's, whichever is wider, less EDGE (< 0: none)."""
    h = -1.0
    if APRON[1] + EDGE <= y <= Y_MAX:
        h = APRON[2] - EDGE
    dy, r = y - C0[1], C0[2] - EDGE
    if abs(dy) < r:
        h = max(h, math.sqrt(r * r - dy * dy))
    return h


def in_field(x, y):
    """A root the field allows: behind Y_MAX and EDGE inside the apron or the circle."""
    return y <= Y_MAX and ((APRON[0] + EDGE <= x <= APRON[2] - EDGE and y >= APRON[1] + EDGE) or
                           math.hypot(x - C0[0], y - C0[1]) <= C0[2] - EDGE)


def corn_dist(x, y):
    """How far (x, y) is from the standing corn: from the apron's sides and back edge or from the circle's rim,
    whichever is further (the barrier side is not corn)."""
    a = min(x - APRON[0], APRON[2] - x, y - APRON[1]) if y <= APRON[3] else -1.0
    return max(a, C0[2] - math.hypot(x - C0[0], y - C0[1]))


def under_beam(x, y):
    return math.hypot(x - BEAM_C[0], y - BEAM_C[1]) < BEAM_R


TIERS = (("near", 12.0), ("mid", 18.5), ("far", 1e9))     # by distance from the DJ (origin)
CLIP_ZONE = {                                             # who dances what, by zone (140 BPM half-time dubstep:
    "front": {"headbang": 0.22, "jump": 0.18, "pump": 0.16, "jumppump": 0.11, "handsup": 0.10, "wave": 0.05,
              "clap": 0.04, "heart": 0.04, "twostep": 0.03, "sway": 0.03, "shuffle": 0.02, "nod": 0.02},   # bang up
    "middle": {"headbang": 0.13, "jump": 0.11, "pump": 0.12, "jumppump": 0.07, "handsup": 0.07, "wave": 0.06,  # front,
               "clap": 0.04, "heart": 0.04, "sway": 0.12, "twostep": 0.07, "shuffle": 0.03, "nod": 0.12, "hold": 0.02},
    "back": {"headbang": 0.06, "jump": 0.06, "pump": 0.07, "jumppump": 0.04, "handsup": 0.05, "wave": 0.07,
             "clap": 0.04, "heart": 0.03, "sway": 0.19, "twostep": 0.10, "shuffle": 0.03, "nod": 0.22, "hold": 0.04},
}                                                         # sway, nod and film further back; "hold" = a phone up
BEAT_CLIPS = {"jump", "jumppump", "pump", "handsup", "wave", "clap", "twostep", "lurch", "claw", "shuffle", "heart",
              "headbang", "hold", "carry", "ride"}       # on the beat: phase 0 or 1 beat (+-30 ms), exact tempo
HALF_TIME_OK = set(BEAT_CLIPS)                            # any beat clip may run at half time ...
HALF_TIME_P = 0.65                                        # ... and ~65 % do (crowd3: 15 % of 7 clips)
GROOVE_HALF_P = 0.45                                      # free-floating groove clips at half time (crowd3: 20 %)
CARRIER_DROP = {"phone", "glowstick", "pole", "flag", "talien", "tleg", "corn", "fan", "poi", "staff", "hoop",
                "hat_dome", "hat_brim", "hat_pom", "hat_farmer", "hat_cowboy", "pilgrim_hat", "pilgrim_buckle",
                "turkey_hat", "foil_cone", "alien_mask", "hair_bun", "hair_pony", "goggles", "scarf"}
#                                                           a friend sits right behind the carrier's head (and on the
#                                                           scarf)


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
    """Rows from the barrier back: packed at the barrier, gaps growing with depth and toward the corn; people drop out
    over the last FEATHER m before the corn (the apron's sides, the circle's rim) instead of a straight cut. Nobody
    stands within MIN_GAP of someone already placed (a grid of MIN_GAP cells holds them)."""
    pts, cells = [], {}

    def clear(px, py):                                                # (registers the point when it is clear)
        i, j = math.floor(px / MIN_GAP), math.floor(py / MIN_GAP)
        for a in (i - 1, i, i + 1):
            for b in (j - 1, j, j + 1):
                if any((qx - px) ** 2 + (qy - py) ** 2 < MIN_GAP * MIN_GAP for qx, qy in cells.get((a, b), ())):
                    return False
        cells.setdefault((i, j), []).append((px, py))
        return True
    y = Y_FRONT
    while y > Y_BACK:
        depth = Y_FRONT - y
        gap = scale * (0.52 + 0.0142 * depth)
        half = min(half_fn(y), field_half(y))
        x = -half + rng.uniform(0, gap)
        while x < half:
            side = min(1.0, max(0.0, 1.0 - (corn_dist(x, y) - EDGE) / FEATHER))
            gx = gap * (1.0 + 0.55 * side)
            px, py = x + rng.uniform(-0.3, 0.3) * gx, y + rng.uniform(-0.3, 0.3) * gap
            keep = 1.0 - 0.5 * side * side
            if (rng.random() < keep and abs(px) <= half and in_field(px, py) and not _excluded(px, py, exclude)
                    and clear(px, py)):
                pts.append((px, py))                                  # (the jitter never crosses into the corn)
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


COSTUMES = {"pilgrim": 0.27, "turkey": 0.25, "alien": 0.18, "farmer": 0.16, "foil": 0.14}
COSTUME_RATE = 0.09          # people who pick a costume on their own; friend groups with a theme add more (~18 % in all)
SQUAD_THEME = 0.25           # friend groups who dress alike (85 % of the group wear the theme: a pilgrim crew, ...)
IALIEN_P, IALIEN_MIN, IALIEN_MAX = 0.004, 3, 4   # inflatable aliens: mid tier only (they read from 12-20 m), 3 or 4
HAT_W = {None: 0.36, "beanie": 0.20, "pom": 0.06, "cap": 0.22, "pilgrim": 0.046, "turkey": 0.038, "foil": 0.031,
         "straw": 0.030, "alien": 0.022}   # people without a costume (with the costumes' hats, and after HAT_CLASH takes
#                                            some off: pilgrim and turkey hats ~8 % each, foil, straw and masks ~5 %)
HAT_CLASH = {                # a hat and the clips whose arms go into it (hm_crowd_preview.py's arm-capsule check, 1.5 cm
    "pilgrim": {"clap", "wave", "heart", "hold", "ride"},        # or more): a free dancer puts both hands up instead, a
    "straw": {"clap", "wave", "heart", "hold", "ride"},          # filmer, holder or rider takes the hat off (Midtown's
    "turkey": {"clap"}, "foil": {"clap"}, "alien": {"clap"}, "cap": {"clap"}}   # rule for clapping in Santa hats)
HAT_ARMS = {                 # every headwear part and the clips whose arm, hand or glove edges cut its faces in some frame,
    "pilgrim_hat": {"clap", "wave", "heart", "hold", "ride"},     # near or mid tier, at any depth (Midtown's
    "hat_cowboy": {"clap", "wave", "heart", "hold", "ride"},      # hat_clash.py, 2026-10-18: all 17 clips, the arms
    "hat_farmer": {"clap", "wave", "heart", "hold", "ride", "jumppump"},   # and the hats skinned to every frame).
    "turkey_hat": {"clap"}, "foil_cone": {"clap"}, "alien_mask": {"clap"}, "hat_dome": {"clap"}, "hat_brim": {"clap"},
    "goggles": {"clap"}}     # HAT_CLASH swaps most of these inside make_person; _hat_arm_swaps the rest: beanies and
#                              poms clapping, ski goggles clapping, the farmer's wide brim in jumppump
CROWNED =("pilgrim", "turkey", "foil", "straw", "beanie", "pom", "cap")   # no bun or ponytail through these
COSTUME_CLIPS = {            # added to the zone weights for that costume
    "ialien": {"jump": 0.20, "wave": 0.12, "sway": 0.10}, "pilgrim": {"headbang": 0.05, "nod": 0.05, "twostep": 0.04},
    "turkey": {"jump": 0.06, "shuffle": 0.06, "wave": 0.04}, "alien": {"handsup": 0.06, "wave": 0.05, "sway": 0.04},
    "farmer": {"twostep": 0.10, "clap": 0.04}, "foil": {"nod": 0.05, "headbang": 0.05}}
TORSO_R = ("hips", "belly", "midriff", "chest", "shoulders")
ARM_R = ("sleeve_top", "sleeve_mid", "forearm", "wrist")
LEG_R = ("thigh_top", "thigh", "knee", "shin", "ankle")
HEADWEAR = ("hat_dome", "hat_brim", "hat_pom", "hat_farmer", "hat_cowboy", "pilgrim_hat", "pilgrim_buckle",
            "turkey_hat", "foil_cone", "alien_mask", "goggles")
WHITE_LINEN = (0.80, 0.78, 0.72)                                  # the pilgrims' collars and cuffs


def _pick_clip(rng, zone, costume, beam=False):
    table = dict(CLIP_ZONE[zone])
    for c, add in list(COSTUME_CLIPS.get(costume, {}).items()) + (list(BEAM_CLIPS.items()) if beam else []):
        table[c] = table.get(c, 0.0) + add
    return _choice_w(rng, table)


def _wear_hat(rng, hat, parts, col, pat):
    """Put on one hat (parts and colours): None, beanie, pom, cap, pilgrim, turkey, foil, straw or alien (the mask)."""
    parts.difference_update(HEADWEAR)
    pat.pop("hat", None)
    pat.pop("feather", None)
    if hat in CROWNED:                                                # no bun or ponytail through a crown (crowd3 kept
        parts.difference_update({"hair_bun", "hair_pony"})           # them under caps and cowboy hats)
    if hat == "pilgrim":                                              # black, the brim and band a shade off, a gold or
        parts |= {"pilgrim_hat", "pilgrim_buckle"}                    # silver buckle
        col.update(hat=rng.choice([BLACK, BLACK, (0.03, 0.03, 0.032), (0.05, 0.035, 0.025)]), hat2=(0.035, 0.035, 0.038),
                   hat3=GOLD if rng.random() < 0.7 else SILVER)
    elif hat == "turkey":                                             # a brown plush body, the fan's lobes in turn with
        parts.add("turkey_hat")                                       # pale tips, a tan or red head, a yellow beak, a red
        col.update(hat=rng.choice(TURKEY_BROWNS), hat2=rng.choice([(0.30, 0.20, 0.12), (0.45, 0.10, 0.06)]), hat3=BEAK,
                   wattle=WATTLE)                                     # wattle
        pat["feather"] = ("fan", (rng.sample(FEATHERS, 3), rng.choice(FEATHER_TIPS)))
    elif hat == "foil":                                               # a crumpled cone or a dome of foil: silver facets,
        parts.add("foil_cone" if rng.random() < 0.6 else "hat_dome")  # every other one darker
        col["hat"] = SILVER
        pat["hat"] = ("check", (0.30, 0.31, 0.34))
    elif hat == "straw":                                              # a farmer's or a cowboy's straw hat (a weave of two
        parts.add("hat_farmer" if rng.random() < 0.5 else "hat_cowboy")   # straws) with a dark band
        straw = rng.choice(STRAWS)
        col.update(hat=straw, hat2=mul(straw, 0.9), hat3=rng.choice([BROWN, BLACK, RUST, NAVY]))
        pat["hat"] = ("stripe", mul(straw, 0.72))
    elif hat == "alien":                                              # the mask covers the head: no hair or scarf in it
        parts.difference_update(HAIR_PARTS + ("scarf",))
        parts.add("alien_mask")
        col["mask"] = rng.choice(ALIEN_GREENS)
    elif hat in ("beanie", "pom"):
        parts |= {"hat_dome", "hat_pom"} if hat == "pom" else {"hat_dome"}
        col["hat"] = rng.choice(COATS + BRIGHTS + MUTED)
        col["hat2"] = CREAM if rng.random() < 0.5 else rng.choice(BRIGHTS)
        if rng.random() < 0.35:                                       # a striped beanie
            pat["hat"] = ("stripe", rng.choice([CREAM, RUST, MUSTARD, OLIVE, BLACK]))
    elif hat == "cap":
        parts |= {"hat_dome", "hat_brim"}
        col["hat"] = rng.choice(COATS + MUTED + BRIGHTS[:3])
        col["hat2"] = mul(col["hat"], 0.75)


def _dress(rng, costume, p, parts, col, pat, skin):
    """The Thanksgiving costume over the autumn outfit: parts in and out, colours and patterns (vertex colour only).
    Returns the hat the costume wears (None for the inflatable alien; the hat lottery without a costume)."""
    def paint(regs, c):
        for r in regs:
            col[r] = c
            pat.pop(r, None)
    if costume == "pilgrim":                                          # black or charcoal, a white collar and cuffs,
        dark = rng.choice([BLACK, BLACK, CHARCOAL, (0.05, 0.035, 0.025)])   # breeches and stockings or a long skirt
        paint(TORSO_R + ARM_R, dark)
        paint(("shoulders", "wrist"), WHITE_LINEN)
        if rng.random() < 0.35:                                       # a long dark skirt over dark stockings
            parts.add("tutu")
            col["tutu"] = rng.choice([BLACK, CHARCOAL, BROWN, (0.05, 0.035, 0.025)])
            paint(LEG_R, rng.choice([BLACK, (0.03, 0.03, 0.035)]))
        else:
            paint(("hips",) + LEG_R[:3], rng.choice([BLACK, CHARCOAL, BROWN]))
            paint(LEG_R[3:], CREAM if rng.random() < 0.5 else BLACK)
        paint(("shoe", "sole"), BLACK)
        col["hand"] = skin
        parts.difference_update({"warmers", "lightshoes", "pack"})
        p["morph"].pop("flare", None)
        return "pilgrim"
    if costume == "turkey":                                           # a brown onesie with a pale front, or a brown top
        brown = rng.choice(TURKEY_BROWNS)                             # over jeans; a well-fed belly
        if rng.random() < 0.5:
            paint(TORSO_R + ARM_R + LEG_R, brown)
            for r in ("belly", "midriff", "chest"):
                pat[r] = ("front", (0.45, 0.33, 0.20))
            parts.difference_update({"warmers", "lightshoes"})
            p["morph"].pop("flare", None)
        else:
            paint(TORSO_R[1:] + ARM_R, brown)
        p["morph"]["belly"] = p["morph"].get("belly", 0.0) + 0.015
        return "turkey"
    if costume == "alien":                                            # a green, black or silver suit, green hands
        paint(TORSO_R + ARM_R + LEG_R, rng.choice([(0.04, 0.16, 0.04), BLACK, (0.40, 0.42, 0.45), (0.06, 0.22, 0.05)]))
        col["hand"] = rng.choice(ALIEN_GREENS + [skin])
        parts.difference_update({"warmers", "pack"})
        p["morph"].pop("flare", None)
        return "alien"
    if costume == "farmer":                                           # denim bib overalls over a flannel, work boots
        fl, den = rng.choice(FLANNELS), rng.choice(DENIMS)
        for r in TORSO_R[1:] + ARM_R:
            col[r] = fl[0]
            pat[r] = ("bib", (den, fl)) if r in TORSO_R else ("plaid", fl)
        paint(("hips",) + LEG_R, den)
        paint(("ankle", "shoe"), rng.choice(WORKBOOTS))
        col["sole"] = (0.05, 0.035, 0.02)
        parts.difference_update({"warmers", "lightshoes", "tutu"})
        p["morph"].pop("flare", None)
        return "straw"
    if costume == "foil":                                             # the tinfoil crew: their own clothes, foil hats
        return "foil"
    if costume == "ialien":                                           # the inflatable alien suit (mid tier)
        parts.clear()
        parts |= {"b_legs", "ialien"}
        col.update(ialien=INFLATABLE_GREEN, ialien2=BLACK, ialien3=mul(INFLATABLE_GREEN, 0.55))
        col.update(thigh_top=INFLATABLE_GREEN, thigh=INFLATABLE_GREEN, knee=INFLATABLE_GREEN, shin=BLACK, ankle=BLACK,
                   shoe=BLACK, sole=BLACK)
        col["glow_antenna"] = rng.choice([GLOW_COLS["green"], GLOW_COLS["gold"]])
        pat.clear()
        return None
    return _choice_w(rng, HAT_W)


def make_person(rng, x, y, tier, zone="middle", yaw=None, clip=None, role=None, holder_bias=0.0, squad=None,
                force_costume=None):
    """Everything about one person: placement, body type, autumn outfit, Thanksgiving costume and hat, parts, clip,
    phase, rate. force_costume: a costume name, "plain" (none), or None: field people and the grounds' extras pick for
    themselves (~18 % in costume); riders and carriers never wear one (they still get a hat)."""
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
    # ---- costume (~18 %): pilgrims, turkeys, aliens, farmers, tinfoil crews; a few inflatable aliens (mid tier)
    costume = None if force_costume in ("plain", "raver") else force_costume      # "raver": Graveyard's word
    if force_costume is None and role in (None, "extra"):
        if tier == "mid" and role is None and rng.random() < IALIEN_P:
            costume = "ialien"
        elif squad and squad.get("costume") and rng.random() < 0.85:
            costume = squad["costume"]
        elif rng.random() < COSTUME_RATE:
            costume = _choice_w(rng, COSTUMES)
    p["costume"] = costume
    p["skin"] = skin
    parts = set(BODY_PARTS)
    col, pat = {}, {}
    # ---- hair: short, long, ponytail, bun, braids, buzz cut, bald; natural or (fewer than Graveyard) dyed
    hair = rng.choices(("short", "long", "pony", "bun", "braids", "buzz", "bald"),
                       weights=(0.24, 0.22, 0.10, 0.09, 0.08, 0.17, 0.10))[0]
    hcol = rng.choice(HAIR_DYED) if rng.random() < 0.15 else rng.choice(HAIR_NATURAL)
    if hair not in ("buzz", "bald"):
        parts.add("hair")
        parts.add({"long": "hair_long", "pony": "hair_pony", "bun": "hair_bun", "braids": "hair_braids"}.get(hair, "hair"))
    col["hair"] = hcol
    col["scalp"] = skin if hair == "bald" else hcol
    # ---- outfit (a farm field, late November): a flannel shirt, a denim jacket, a dark jacket, a hoodie, a puffer vest
    #      or a long coat over jeans, work trousers or joggers; work boots, boots or sneakers
    tk = rng.choices(("flannel", "denim", "jacket", "hoodie", "vest", "long"), weights=(0.26, 0.13, 0.20, 0.21, 0.12, 0.08))[0]
    top = (squad["top"] if squad and squad.get("top") and rng.random() < 0.8 else
           rng.choice(DENIMS) if tk == "denim" else top_color(rng))
    fl = rng.choice(FLANNELS)
    bk = rng.choices(("jeans", "black", "work", "joggers", "leggings"), weights=(0.46, 0.22, 0.16, 0.08, 0.08))[0]
    bottom = (rng.choice(DENIMS) if bk == "jeans" else rng.choice(EARTH) if bk == "work" else
              rng.choice([(0.05, 0.05, 0.055), (0.12, 0.12, 0.13), BLACK]) if bk == "joggers" else rng.choice(COATS))
    foot = rng.choices(("work", "boots", "sneaker", "light", "platform", "fuzzy"),
                       weights=(0.38, 0.18, 0.30, 0.06, 0.03, 0.05))[0]
    shoe = (rng.choice(WORKBOOTS) if foot == "work" else rng.choice([BLACK, BLACK, (0.10, 0.05, 0.02)]) if foot == "boots"
            else rng.choice([(0.8, 0.8, 0.78), BLACK, (0.25, 0.25, 0.27), RUST]))
    long_top = tk == "long" or (tk == "jacket" and rng.random() < 0.3)            # it covers the hips
    torso_top = {"hips": top if long_top else bottom, "belly": top, "midriff": top, "chest": top, "shoulders": top}
    sleeves = {"sleeve_top": top, "sleeve_mid": top, "forearm": top, "wrist": top}
    legs = {"thigh_top": bottom, "thigh": bottom, "knee": bottom, "shin": bottom, "ankle": bottom}
    if tk == "long" and rng.random() < 0.6:                           # a long coat: to the thighs
        legs["thigh_top"] = top
    if tk == "flannel":                                               # a flannel shirt: the check on body and sleeves
        torso_top.update({r: fl[0] for r in TORSO_R[1:]})
        sleeves = {r: fl[0] for r in ARM_R}
        for r in TORSO_R[1:] + ARM_R:
            pat[r] = ("plaid", fl)
    elif tk == "denim" and rng.random() < 0.45:                       # a sherpa collar
        torso_top["shoulders"] = CREAM
    elif tk == "vest":                                                # a puffer vest (quilted bands, a bulkier body) over
        for r in TORSO_R[1:]:                                         # a flannel (half of them) or a dark hoodie
            pat[r] = ("stripe", mul(top, 0.55))
        flannel_under = rng.random() < 0.5
        under = fl[0] if flannel_under else rng.choice(COATS)
        sleeves = {r: under for r in ARM_R}
        if flannel_under:
            for r in ARM_R:
                pat[r] = ("plaid", fl)
        for k, v in (("belly", 0.012), ("shoulders", 0.008), ("bust", 0.006)):
            p["morph"][k] += v
    if foot in ("work", "boots"):
        legs["ankle"] = shoe
        if foot == "boots" and rng.random() < 0.35:                   # tall boots
            legs["shin"] = shoe
    elif foot == "fuzzy":                                             # sheepskin boots (near: the fuzzy warmers)
        warm = rng.choice([CREAM, (0.30, 0.20, 0.10), (0.25, 0.16, 0.09), BROWN])
        if tier == "near":
            parts.add("warmers")
        legs.update(shin=warm, ankle=warm)
        col["warmer"] = warm
        shoe = mul(warm, 0.8)
    elif foot == "light":
        parts.add("lightshoes")
    elif foot == "platform":                                          # thick soles: the person stands 4.5 cm taller
        p["morph"]["platform"] = 0.045
        p["z"] += 0.045 * p["sz"]
    col.update(torso_top)
    col.update(sleeves)
    col.update(legs)
    col["shoe"] = shoe
    col["sole"] = {"sneaker": (0.75, 0.75, 0.72), "platform": (0.9, 0.9, 0.92), "boots": (0.03, 0.03, 0.03),
                   "work": (0.05, 0.035, 0.02)}.get(foot, (0.6, 0.6, 0.58))
    # ---- hands (work gloves: 15 %), face (a neck gaiter, shades), a scarf (12 %)
    col["hand"] = rng.choice([BLACK, (0.06, 0.06, 0.065), (0.30, 0.20, 0.10), (0.22, 0.12, 0.05), OLIVE]) if (
        rng.random() < 0.15) else skin
    col.update(face=skin, skin=skin, jaw=skin, eyes=mul(skin, 0.3), brow=mul(skin, 0.6), mouth=mul(skin, 0.62))
    if rng.random() < 0.06:
        m = rng.choice(COATS + [RUST, CREAM])
        col.update(jaw=m, mouth=m)
    if rng.random() < 0.08:
        col["eyes"] = (0.01, 0.01, 0.01)
    if "hair_braids" not in parts and rng.random() < 0.12:          # (braids run over the shoulders, through it)
        parts.add("scarf")
        col["scarf"] = rng.choice(BRIGHTS + MUTED + COATS[4:])
        if rng.random() < 0.4:                                        # a striped scarf
            pat["scarf"] = ("stripe", rng.choice([CREAM, RUST, MUSTARD, OLIVE, BLACK]))
    # ---- the costume layer, then the hat (the costume's, or the hat lottery)
    hat = _dress(rng, costume, p, parts, col, pat, skin)
    if costume != "ialien":
        _wear_hat(rng, hat, parts, col, pat)
        if hat in (None, "cap") and tier == "near" and rng.random() < 0.04:
            parts.add("goggles")                                      # ski goggles on the forehead
    p["hat"] = hat
    col.update(goggles=rng.choice([BLACK, GOLD, (0.6, 0.6, 0.65)]), mask_eye=BLACK)
    # ---- packs and glow wear
    if costume in (None, "foil") and "scarf" not in parts and rng.random() < 0.08:
        parts.add("pack")
    col["pack"] = rng.choice(COATS + BRIGHTS[:3])
    col["strap"] = (0.02, 0.02, 0.02)
    if costume != "ialien" and rng.random() < 0.15:
        parts.add("necklace")
    if costume != "ialien" and rng.random() < 0.04:
        parts.add("gloves")                                           # LED gloves
        if costume is None:
            col["hand"] = BLACK
    # ---- held things: totems, flow toys, phones, glowsticks (a held thing decides the dance)
    free = role is None and costume != "ialien"
    holder = free and d > 10.5 and rng.random() < 0.012 + holder_bias
    if holder:
        item = rng.choices(("flag", "talien", "tleg", "corn"), weights=(0.62, 0.38, 0.0, 0.0))[0]   # BIG DUB: flags and inflatable aliens
        parts |= {"pole", item}
        clip, p["held"], p["totem"] = "hold", "totem", item
    elif free and y < FLOW_Y and rng.random() < (0.03 if tier != "far" else 0.02):
        toy = rng.choices(("hoop", "poi", "staff", "fan"), weights=(0.35, 0.25, 0.2, 0.2))[0]
        parts.add(toy)
        clip, p["held"], p["flow"] = "flow", toy, toy
    elif free and rng.random() < 0.06:
        parts.add("phone")
        clip, p["held"] = "hold", "phone"
    elif costume != "ialien" and role != "rider" and rng.random() < 0.14:
        parts.add("glowstick")
        p["held"] = "glowstick"
    p["holder"] = holder
    for r in ("glow_stick", "glow_necklace", "glow_glove", "glow_shoe", "glow_fan", "glow_hoop", "glow_poi", "glow_staff",
              "glow_antenna"):
        if r not in col:
            col[r] = hm_glow(rng)
    col.update(glow_alien=rng.choice([GLOW_COLS["green"], (0.45, 1.0, 0.50)]),
               glow_corn=rng.choice([(1.0, 0.78, 0.12), (1.0, 0.66, 0.10)]), glow_screen=(0.55, 0.7, 1.0),
               glow_flash=(1.0, 1.0, 0.95))
    pat["glow_corn"] = ("check", mul(col["glow_corn"], 0.55))         # the kernels
    col.update(phone=(0.02, 0.02, 0.025), pole=(0.35, 0.35, 0.36), staff=(0.1, 0.1, 0.1), tbone=CREAM,
               tleg=rng.choice([(0.20, 0.09, 0.03), (0.16, 0.07, 0.025)]),
               husk=rng.choice([(0.06, 0.14, 0.03), (0.10, 0.16, 0.05)]))
    fg = rng.sample(FLAGS, 2)
    col.update(flag1=fg[0], flag2=fg[1])
    # ---- the dance (zone mix + costume bias + the beam); "hold" without a held thing means filming: a phone goes up
    if clip is None:
        clip = _pick_clip(rng, zone, costume, under_beam(x, y))
    if clip in HAT_CLASH.get(hat, ()):                                # the arms would go into the hat: a filmer, holder
        if clip in ("hold", "ride"):                                  # or rider takes it off, anyone else dances with
            hat = rng.choice((None, None, "beanie"))                  # both hands up
            _wear_hat(rng, hat, parts, col, pat)
            p["hat"] = hat
        else:
            clip = "handsup"
    if clip == "hold" and p["held"] is None and costume != "ialien":
        parts.discard("glowstick")
        parts.add("phone")
        p["held"] = "phone"
    # ---- the far shape: body + pole with a flag or a totem + one-sided stand-ins for the glowing things and the hats
    if tier == "far":
        far = {"b_torso", "b_head", "b_arms"}
        if holder:
            far |= {"pole", {"flag": "flag", "talien": "far_talien", "tleg": "far_tleg", "corn": "far_corn"}[p["totem"]]}
        hand = parts & {"phone", "glowstick", "gloves", "fan", "poi", "staff"}
        if hand:
            far.add("far_hand")
            gl = sorted(hand)[0]
            col["glow_hand"] = ((1.0, 1.0, 0.95) if gl == "phone" else
                                col["glow_" + {"glowstick": "stick", "gloves": "glove"}.get(gl, gl)])
        if parts & {"necklace", "hoop"}:
            far.add("far_chest")
            col["glow_chest"] = col["glow_hoop"] if "hoop" in parts else col["glow_necklace"]
        for q, fb in (("pilgrim_hat", "far_pilgrim"), ("turkey_hat", "far_turkey"), ("foil_cone", "far_foil"),
                      ("hat_farmer", "far_straw"), ("hat_cowboy", "far_straw")):
            if q in parts:
                far.add(fb)
        if parts & {"hat_dome", "hat_farmer", "hat_cowboy"}:          # the far head takes the hat's colour
            col["scalp"] = col["hat"]
        if "alien_mask" in parts:                                     # a green head
            col.update(face=col["mask"], scalp=col["mask"])
        parts = far
    p["parts"], p["col"], p["pat"] = parts, col, pat
    p["clip"] = clip
    _timing(rng, p)
    return p


def _hat_arm_swaps(people):
    """The near and mid people whose arms still go through their headwear (HAT_ARMS, by the parts worn): a dancer puts
    both hands up instead, on the same beat (every clip in HAT_ARMS is a beat clip, so the timing stays right); a
    filmer, totem holder or rider takes the headwear off. It runs on the finished people and draws nothing from the rng,
    so every placement and look stays as it was (HAT_CLASH's swaps sit inside make_person and draw from it: moving
    them here would re-draw the whole crowd). The far tier's stand-ins have nothing to go through. Midtown's
    _hat_clip_swaps, by part. Returns how many people changed."""
    n = 0
    for p in people:
        if p["tier"] == "far" or not any(p["clip"] in HAT_ARMS.get(q, ()) for q in p["parts"]):
            continue
        if p["clip"] in ("hold", "ride"):
            p["parts"] = p["parts"] - set(HEADWEAR)
            p["hat"] = None
        else:
            p["clip"] = "handsup"
        n += 1
    return n


def build_people(rng, pts, extra, half_fn, tiers):
    """Field positions -> people: friend groups (dancing together, or facing each other talking / dancing), couples,
    people turned to a neighbour, room around flow artists, three or four inflatable aliens, people on friends'
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
        clip = _pick_clip(rng, zone_of(cy), squad.get("costume") if squad else None, under_beam(cx, cy))
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
            else:                                                     # facing each other: talk / sway / heart
                yaw = math.atan2(-(cx - x), cy - y) + rng.gauss(0, 0.25)
                c2 = (rng.choice(("talk", "talk", "sway", "twostep", "heart", "nod")) if kind == "circle" else
                      rng.choice(("sway", "twostep", "heart", "talk")))
                pr = make_person(rng, x, y, tier_of(x, y), zone_of(y), yaw=yaw, clip=c2, squad=squad)
            people[j] = pr
    for j in range(n):
        if people[j] is None:
            x, y = P[j]
            side = max(0.0, abs(x) / half_fn(y) - 0.45) * 0.12
            pr = make_person(rng, x, y, tier_of(x, y), zone_of(y), holder_bias=side + (0.012 if y < -30 else 0.0))
            if pr["clip"] not in ("hold", "flow") and pr["costume"] != "ialien" and y < -10.5 and rng.random() < 0.05:
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
    infl = [j for j, pr in enumerate(people) if pr["costume"] == "ialien"]
    for j in infl[IALIEN_MAX:]:                                       # three or four inflatable aliens, always
        pr = people[j]
        people[j] = make_person(rng, pr["x"], pr["y"], "mid", zone_of(pr["y"]), yaw=pr["yaw"], force_costume="plain")
    if len(infl) < IALIEN_MIN:
        mids = [j for j, pr in enumerate(people) if pr["tier"] == "mid" and pr["costume"] is None
                and pr["clip"] not in ("hold", "flow") and not pr["holder"]]
        for j in rng.sample(mids, min(len(mids), IALIEN_MIN - len(infl))):
            pr = people[j]
            people[j] = make_person(rng, pr["x"], pr["y"], "mid", zone_of(pr["y"]), yaw=pr["yaw"], force_costume="ialien")
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
        if r["tier"] != "far" and rng.random() < 0.4:                  # some riders hold up a flag, an alien, corn, a leg
            r["totem"] = rng.choice(("flag", "talien", "flag", "corn", "tleg"))
            r["parts"] = (r["parts"] - {"glowstick"}) | {"pole", r["totem"]}
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
    n_hat = _hat_arm_swaps(people)
    return people, {"groups": len(groups), "riders": len(riders), "cleared_for_flow": n_cleared, "hat_swaps": n_hat}


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
    """Per-loop colours: the region colour, with per-VERTEX patterns (stripes, flannel checks, feather fans) so corners
    that share a vertex share a colour (no extra vertex splits in Unreal). Patterns that go by height or side read the
    canonical (rest) positions, so they are the same in every pose."""
    regs = c.F_reg[c.L_face[loops]]
    out = reg_col[regs].copy()
    for rname, (kind, arg) in p["pat"].items():
        sel = regs == REG[rname]
        if not sel.any():
            continue
        vv = lv[sel]
        x, y, z = (c.V[vv, k][:, None] for k in range(3))
        if kind == "stripe":                                          # tights, scarves, beanies, quilting, straw: every
            other = np.array(arg, dtype=np.float32)                   # other ring
            k = ((c.pat[vv] + c.pj[vv]) % 2)[:, None]
            out[sel] = out[sel] * (1 - k) + other * k
        elif kind == "check":                                         # foil facets, corn kernels: a checker (pat =
            k = c.pat[vv][:, None]                                    # (j + ring) % 2)
            out[sel] = out[sel] * (1 - k) + np.array(arg, dtype=np.float32) * k
        elif kind in ("plaid", "bib"):                                # a flannel check: stripes round the body (every
            base, band, dark = (np.array(a_, dtype=np.float32) for a_ in (arg if kind == "plaid" else arg[1]))
            v = (c.pj[vv] % 2 == 0)[:, None]                          # other vertex) across bands (every other ring),
            h = ((c.pat[vv] + c.pj[vv]) % 2 > 0.5)[:, None]           # darkest where they cross; bib overalls: denim
            o = np.where(v & h, dark, np.where(v | h, band, base))    # down the front over it
            if kind == "bib":
                o = np.where((np.abs(x) < 0.09) & (y > 0.0), np.array(arg[0], dtype=np.float32), o)
            out[sel] = o
        elif kind == "fan":                                           # turkey feathers: the lobes' colours in turn (pj),
            pal, tip = np.array(arg[0], dtype=np.float32), np.array(arg[1], dtype=np.float32)   # pale tips (pat)
            out[sel] = np.where((c.pat[vv] > 0.5)[:, None], tip, pal[c.pj[vv] % len(pal)])
        elif kind == "front":                                         # a pale panel down the front
            out[sel] = np.where((np.abs(x) < 0.08) & (y > 0.0), np.array(arg, dtype=np.float32), out[sel])
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


def build_crowd2(rng, exclude=(), extra=(), out_dir=None, target=3960, half_fn=None, tiers=TIERS, vat_name="T_HmCrowdVAT"):
    """The Thanksgiving crowd. Returns (SM_HmCrowd, SM_HmPhones, extras): bodies (UV0 lighting cells, Col albedo, VAT
    UV channels; every person posed at frame 0 of their clip), the glowing bits (Col = emissive colour, same VAT), no
    extras. Writes <out_dir>/<vat_name>.exr (+ .json): the VAT both objects play, 2048 x 1024 (a RuntimeError if it
    ever is not). out_dir: else env HM_OUT, else harvest/out_hm. exclude: keep-out rects (x0, y0, x1, y1; None = none);
    FOH_EXCLUDE (the hay-wagon FOH) is always added. half_fn: field_half (the apron joined to the crop circle) unless
    given; the field never leaves the apron and the circle either way. Everyone (field + riders + extra) fits the
    walking map's PERSON_CAP: the field target comes down first if extra would pass it, and the back row gives way if
    the layout still does. Same signature and layout as crowd3 / xm_crowd.build_crowd2 (only the default names differ;
    the field target is Harvest's)."""
    t0 = time.time()
    half_fn = half_fn or field_half
    out_dir = out_dir or os.environ.get("HM_OUT") or os.path.join(HM_DIR, "out_hm")
    os.makedirs(out_dir, exist_ok=True)
    excl = [tuple(map(float, r)) for r in (exclude or ())] + ([FOH_EXCLUDE] if FOH_EXCLUDE else [])
    extra = list(extra)
    room = PERSON_CAP - len(extra) - (target // 300 + 1) - 60      # the riders, and a margin for the layout's spread
    if target > room:
        log(f"target {target} -> {room}: {len(extra)} extra people and the riders must fit the walking map's "
            f"{PERSON_CAP} people")
        target = room
    canons = [Canon(t) for t in ("near", "mid", "far")]
    tex, vlay, n_pages, ncols = bake_vat(canons)
    if tex.shape[:2] != (1024, 2048) or n_pages != 2 or ncols > 2048:
        raise RuntimeError(f"the VAT came out {tex.shape[1]} x {tex.shape[0]}, {n_pages} pages, widest {ncols} columns "
                           f"(tier columns { {c.tier: len(c.V) for c in canons} }): the material expects 2048 x 1024, "
                           f"2 pages under 2048 columns")
    pts, density = layout(rng, excl, half_fn, target)
    people, roles = build_people(rng, pts, extra, half_fn, tiers)
    over = len(people) - PERSON_CAP
    if over > 0:                                                      # the back row gives way (never riders or extras)
        back = sorted((i for i, p in enumerate(people) if p["role"] == "dancer"), key=lambda i: people[i]["y"])[:over]
        drop = set(back)
        people = [p for i, p in enumerate(people) if i not in drop]
        log(f"{over} dancers off the back row: the walking map holds {PERSON_CAP} people")
    arrays, n_units = assemble(people, canons, vlay)
    finite = bool(np.isfinite(tex).all()) and all(a[k] is None or np.isfinite(a[k]).all() for a in arrays.values()
                                                  for k in ("co", "uv0", "uv1", "uv2", "uv3", "uv4", "uv5", "col"))
    if not finite:
        raise RuntimeError("the crowd has non-finite vertices, UVs, colours or VAT texels")
    _LAST.update(people=people, canons=canons, vlay=vlay, arrays=arrays)
    crowd = mesh_from_arrays("SM_HmCrowd", arrays["body"])
    phones = mesh_from_arrays("SM_HmPhones", arrays["glow"])
    _POSE[crowd.name] = [None, arrays["body"]["vdata"]]
    _POSE[phones.name] = [None, arrays["glow"]["vdata"]]
    _VAT["tex"] = tex
    write_exr(os.path.join(out_dir, vat_name + ".exr"), tex, half=True)
    _VAT["tex_half"] = tex.astype(np.float16).astype(np.float32)
    stats = {}
    glowing = {"necklace", "gloves", "lightshoes", "phone", "glowstick", "fan", "poi", "staff", "hoop", "talien", "corn",
               "ialien", "far_hand", "far_chest", "far_talien", "far_corn"}
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
    clips, costumes, hats = {}, {}, {}
    for p in people:
        clips[p["clip"]] = clips.get(p["clip"], 0) + 1
        if p["costume"]:
            costumes[p["costume"]] = costumes.get(p["costume"], 0) + 1
        hat = p.get("hat") if p["role"] != "carrier" else None        # carriers take their hats off
        if hat:
            hats[hat] = hats.get(hat, 0) + 1
    tris = {k: int((np.diff(np.append(a["lstart"], len(a["lvert"]))) - 2).sum()) for k, a in arrays.items()}
    field = [p for p in people if p["role"] in ("dancer", "carrier")]
    beat = [p for p in people if p["clip"] in BEAT_CLIPS]
    groove = [p for p in people if p["clip"] not in BEAT_CLIPS]
    n_all = max(1, len(people))
    shares = {"costumed_all": round(sum(p["costume"] is not None for p in people) / n_all, 3),
              "costumed_field": round(sum(p["costume"] is not None for p in field) / max(1, len(field)), 3),
              "pilgrim_hat_all": round(hats.get("pilgrim", 0) / n_all, 3),
              "turkey_hat_all": round(hats.get("turkey", 0) / n_all, 3),
              "foil_hat_all": round(hats.get("foil", 0) / n_all, 3),
              "straw_hat_all": round(hats.get("straw", 0) / n_all, 3),
              "alien_mask_all": round(hats.get("alien", 0) / n_all, 3),
              "half_time_beat_clips": round(sum(p["rate"] < 0.75 for p in beat) / max(1, len(beat)), 3),
              "half_time_groove_clips": round(sum(p["rate"] < 0.75 for p in groove) / max(1, len(groove)), 3)}
    meta = {"what": "Thanksgiving crowd VAT (hm_crowd, from xm_crowd / crowd3): per-vertex offsets (m, Blender space) "
                    "from FRAME 0 of each clip (every person is posed at frame 0 of their clip); columns = tier superset "
                    "vertices; rows = (page * len(clips) + clip) * rows_per_clip + frame (row 0 = top); UV1.y = page * "
                    "len(clips) + clip",
            "texture": vat_name + ".exr", "width": tex.shape[1], "height": tex.shape[0], "columns_used": ncols,
            "pages": n_pages, "tier_pages": {t: v[0] for t, v in vlay.items()},
            "tier_columns": {t: v[1] for t, v in vlay.items()},
            "fps": FPS, "frames_per_clip": FRAMES, "rows_per_clip": ROWS, "clips": list(CLIPS),
            "authored_bpm": AUTHORED_BPM, "beats_per_clip": BEATS_PER_CLIP, "loop_rate_for_bpm": "LoopRate = BPM / 120",
            "set_bpm": HM_BPM, "loop_rate": round(HM_BPM / 120.0, 4), "shares": shares,
            "tier_vertices": {c.tier: len(c.V) for c in canons}, "tier_superset_tris": {c.tier: c.tris for c in canons},
            "axis_scale": list(UE_AXIS), "ue_flips_v": UE_FLIPS_V, "uv_channels": VAT_LAYOUT,
            "field": {"apron": list(APRON), "c0": list(C0), "edge": EDGE, "y_max": Y_MAX, "y_front": Y_FRONT,
                      "y_back": Y_BACK, "ground_z": GROUND_Z, "exclude": [list(r) for r in excl],
                      "beam": [list(BEAM_C), BEAM_R]},
            "person_cap": PERSON_CAP, "people": len(people), "field_people": len(people) - roles["riders"] - len(extra),
            "riders": roles["riders"], "extra_people": len(extra), "groups": roles["groups"],
            "cleared_for_flow": roles["cleared_for_flow"], "hat_swaps": roles["hat_swaps"], "target": target,
            "density_scale": density, "tiers": stats,
            "clip_counts": clips, "costumes": costumes, "hats": hats, "tris": tris,
            "blender_vertices": {k: len(a["co"]) for k, a in arrays.items()}, "atlas_units": n_units,
            "max_offset_m": float(np.abs(tex[..., :3]).max()), "finite": finite}
    json.dump(meta, open(os.path.join(out_dir, vat_name + ".json"), "w"), indent=1)
    _VAT["meta"] = meta
    log(f"thanksgiving crowd: {len(people)} people ({meta['field_people']} field + {roles['riders']} riders + "
        f"{len(extra)} extra), {roles['groups']} groups, {roles['hat_swaps']} hat swaps (HAT_ARMS), costumes "
        f"{costumes}, hats {hats}, shares {shares}, tiers {stats}, tris {tris}, VAT {tex.shape[1]}x{tex.shape[0]} "
        f"({n_pages} pages, widest {ncols} columns; tier columns { {c.tier: len(c.V) for c in canons} }), atlas "
        f"{n_units} units, {time.time() - t0:.1f} s")
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


def pose_preview(objects, t, loop_rate=HM_BPM / 120.0):
    """Move the crowd objects' vertices to their animated positions at time t (s), e.g. for preview renders AFTER the
    bake and the FBX export. The first call remembers the current (frame-0) positions - so transforms applied after
    build_crowd2() (the stage drop) are kept; pose_preview(objects, None) restores them. loop_rate = BPM / 120 (default:
    the Thanksgiving set, 140 BPM)."""
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
