# Crowd V2 for the Dino Stage (Blender 4.5): a packed, dancing festival crowd driven by a vertex animation texture (VAT).
#
#   import crowd2
#   crowd, glow, extras = crowd2.build_crowd2(rng, exclude, extra)        # in place of dino_stage.build_crowd()
#
# * People are modeled procedurally here (no third-party assets): lofted bodies (torso, neck, head with a face shape,
#   arms with hands, legs with shoes) plus optional parts: hair styles, caps / bucket hats / beanies, hoodie hoods,
#   backpacks, phones, glowsticks, and totems on poles (flags, LED signs, inflatables, dino cut-outs).
# * Three detail tiers by distance from the DJ (near ~1,000 tris, mid ~300, far ~40), all bound to ONE rig and playing the
#   same 8 dance clips, so the whole field moves alike. Each tier has one "superset" canonical mesh holding every optional
#   part; a person copies only the parts they wear, so the VAT stays one texture (columns = superset vertices of all
#   tiers, rows = clips x 31 frames).
# * Per person (UV channels, see VAT_LAYOUT): VAT column, clip, yaw/scale, mirror, phase, playback rate. UV0 is a per-
#   person lighting cell (bigger cells for nearer tiers) so the stage bake lands on every body; "Col" = albedo per part.
# * Glowing bits (phone screens and flashes, glowsticks, totem LED frames) go to a second object that uses the same VAT
#   with an emissive vertex-colour material (dino_materials.vat_crowd(..., glow=True)).
# Space: meters, Z up, the DJ at the origin facing -Y; the crowd stands on z = GROUND_Z (the main script drops it later).
import json
import math
import os
import random
import struct
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
GROUND_Z = -1.5
FPS, FRAMES = 30, 30                       # one clip = 30 frames = 1 s = 2 beats at the authored 120 BPM
ROWS = FRAMES + 1                          # + a copy of frame 0: the material's frame lerp never wraps
CLIPS = ("jump", "pump", "sway", "headbang", "clap", "wave", "hold", "bounce")
AUTHORED_BPM, BEATS_PER_CLIP = 120.0, 2
UE_AXIS = (100.0, -100.0, 100.0)           # Blender m -> Unreal local cm (our FBX path mirrors Y; verified in the editor)
UE_FLIPS_V = True                          # Unreal's FBX importer stores 1 - V (verified in the fork editor 2026-10-05)
H = 1.75                                   # canonical body height (per person sz scales it)
VAT_LAYOUT = {"UV0 UVMap": "baked-lighting cell", "UV1 VatIndex": "x = VAT column, y = clip",
              "UV2 VatRotScale": "x = sx cos(yaw), y = sx sin(yaw)", "UV3 VatScalePhase": "x = mirror * sz, y = phase",
              "UV4 VatRate": "x = playback rate (1 = authored tempo)"}
DATA_UVS = ("VatIndex", "VatRotScale", "VatScalePhase", "VatRate")


def log(msg):
    print("[CROWD2] " + msg, flush=True)


def V3(x, y, z):
    return Vector((x, y, z))


# ============================================================================ rig (canonical rest pose)
# facing +Y, the person's right on +X. Joint positions in meters.
J = {"pelvis": V3(0, 0, 0.95), "spine1": V3(0, -0.01, 1.05), "spine2": V3(0, -0.01, 1.24), "neck": V3(0, 0.0, 1.45),
     "head": V3(0, 0.01, 1.54)}
for _s, _n in ((1, "R"), (-1, "L")):
    J[f"clav.{_n}"] = V3(_s * 0.035, 0.0, 1.42)
    J[f"shoulder.{_n}"] = V3(_s * 0.185, -0.005, 1.415)
    J[f"elbow.{_n}"] = V3(_s * 0.245, -0.015, 1.145)
    J[f"wrist.{_n}"] = V3(_s * 0.285, 0.02, 0.885)
    J[f"fingers.{_n}"] = V3(_s * 0.30, 0.035, 0.715)
    J[f"hip.{_n}"] = V3(_s * 0.09, 0.0, 0.90)
    J[f"knee.{_n}"] = V3(_s * 0.10, 0.012, 0.485)
    J[f"ankle.{_n}"] = V3(_s * 0.10, -0.012, 0.085)
    J[f"toe.{_n}"] = V3(_s * 0.105, 0.16, 0.025)
BONES = [("pelvis", None), ("spine1", "pelvis"), ("spine2", "spine1"), ("neck", "spine2"), ("head", "neck")]
for _n in "RL":
    BONES += [(f"clav.{_n}", "spine2"), (f"upperarm.{_n}", f"clav.{_n}"), (f"forearm.{_n}", f"upperarm.{_n}"),
              (f"hand.{_n}", f"forearm.{_n}"), (f"thigh.{_n}", "pelvis"), (f"shin.{_n}", f"thigh.{_n}"),
              (f"foot.{_n}", f"shin.{_n}")]
BONE_NAMES = [b for b, _ in BONES]
BONE_IDX = {b: i for i, b in enumerate(BONE_NAMES)}

# ============================================================================ looks
REGIONS = ("skin", "face", "eyes", "brow", "mouth", "scalp", "torso", "sleeve_top", "sleeve_mid", "sleeve_low", "hand", "pants_top", "pants_mid",
           "pants_low", "shoe", "sole", "hair", "hat", "hat2", "hood", "pack", "strap", "phone", "pole", "flag1", "flag2",
           "sign", "inflatable", "cutout", "glow_screen", "glow_flash", "glow_stick", "glow_led")
REG = {r: i for i, r in enumerate(REGIONS)}
GLOW_REGIONS = {REG[r] for r in REGIONS if r.startswith("glow_")}
SKINS = [(0.80, 0.58, 0.45), (0.70, 0.50, 0.37), (0.58, 0.39, 0.27), (0.42, 0.27, 0.18), (0.27, 0.16, 0.10),
         (0.88, 0.70, 0.58), (0.75, 0.55, 0.40)]
TOPS = ([(0.015, 0.015, 0.017)] * 7 + [(0.62, 0.62, 0.60)] * 2 + [(0.30, 0.30, 0.32), (0.05, 0.07, 0.20), (0.08, 0.20, 0.08),
        (0.35, 0.04, 0.05), (0.60, 0.42, 0.05), (0.85, 0.18, 0.50), (0.05, 0.55, 0.65), (0.90, 0.35, 0.05),
        (0.45, 0.80, 0.08), (0.30, 0.08, 0.45), (0.18, 0.20, 0.10), (0.80, 0.80, 0.15)])
BOTTOMS = [(0.05, 0.08, 0.18)] * 4 + [(0.10, 0.15, 0.30)] * 2 + [(0.015, 0.015, 0.018)] * 4 + [
    (0.30, 0.26, 0.18), (0.20, 0.20, 0.21), (0.10, 0.12, 0.06), (0.45, 0.42, 0.38)]
SHOES = [(0.75, 0.75, 0.72)] * 3 + [(0.02, 0.02, 0.02)] * 3 + [(0.35, 0.33, 0.30), (0.60, 0.15, 0.10), (0.10, 0.25, 0.55)]
HAIRS = [(0.015, 0.01, 0.008)] * 5 + [(0.05, 0.03, 0.017)] * 4 + [(0.14, 0.08, 0.035)] * 2 + [
    (0.50, 0.38, 0.18), (0.62, 0.50, 0.28), (0.40, 0.12, 0.04), (0.75, 0.15, 0.45), (0.10, 0.35, 0.65), (0.15, 0.55, 0.30)]
HATS = [(0.015, 0.015, 0.017)] * 3 + [(0.75, 0.75, 0.72), (0.70, 0.08, 0.06), (0.06, 0.12, 0.45), (0.85, 0.65, 0.05),
        (0.08, 0.45, 0.15), (0.80, 0.20, 0.60), (0.25, 0.25, 0.27)]
PACKS = [(0.02, 0.02, 0.022)] * 3 + [(0.25, 0.25, 0.27), (0.70, 0.10, 0.08), (0.05, 0.30, 0.60), (0.85, 0.55, 0.05)]
FLAGS = [(0.90, 0.08, 0.06), (0.06, 0.25, 0.90), (0.95, 0.80, 0.08), (0.08, 0.75, 0.25), (0.90, 0.25, 0.75),
         (0.95, 0.45, 0.05), (0.92, 0.92, 0.90), (0.05, 0.05, 0.06)]
GLOWSTICKS = [(0.2, 1.0, 0.25), (1.0, 0.2, 0.75), (0.15, 0.85, 1.0), (1.0, 0.85, 0.1), (1.0, 0.4, 0.05), (0.7, 0.3, 1.0)]
LEDS = [(1.0, 0.15, 0.1), (0.1, 0.8, 1.0), (1.0, 0.2, 0.9), (0.3, 1.0, 0.3), (1.0, 0.75, 0.1), (0.95, 0.95, 1.0)]


# ============================================================================ canonical geometry
class Geo:
    """Accumulates one canonical (superset) mesh: vertices with bone weights, faces tagged with a part and a region, and
    per-corner UVs inside per-primitive islands (packed per tier later). Seams only where a tube / box / ellipsoid wraps
    around (one vertex column) and caps / box ends reuse their ring's texels, so Unreal splits few vertices."""

    def __init__(self):
        self.v, self.w, self.f, self.fpart, self.freg = [], [], [], [], []
        self.fuv, self.fisl, self.isl = [], [], []

    def vert(self, co, w):
        self.v.append(Vector(co))
        self.w.append(dict(w))
        return len(self.v) - 1

    def island(self, w, h):
        """A UV island of physical size w x h meters (uniform texel density after packing)."""
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
            uv, isl = self._planar(idx)                                # loose faces: their own planar island
        self.f.append(list(idx))
        self.fpart.append(part)
        self.freg.append(REG[reg])
        self.fuv.append([tuple(x) for x in uv])
        self.fisl.append(isl)

    def ring(self, c, e1, e2, rx, ryf, ryb, segs, w, phase=0.0, shape=None):
        """Ellipse ring around c in the plane (e1, e2): rx along e1, ryf toward +e2 (front), ryb toward -e2 (back)."""
        out = []
        for j in range(segs):
            a = 2 * math.pi * j / segs + phase
            ca, sa = math.cos(a), math.sin(a)
            ry = ryf if sa > 0 else ryb
            p = c + e1 * (rx * ca) + e2 * (ry * sa)
            if shape:
                p = shape(p, a)
            wv = w(p) if callable(w) else w
            out.append(self.vert(p, wv))
        return out

    def bridge(self, ra, rb, part, reg, isl=-1, va=0.0, vb=1.0):
        n = len(ra)
        for j in range(n):
            uv = ((j / n, va), ((j + 1) / n, va), ((j + 1) / n, vb), (j / n, vb))
            self.face((ra[j], ra[(j + 1) % n], rb[(j + 1) % n], rb[j]), part, reg, uv if isl >= 0 else None, isl)

    def face_toward(self, idx, direction, part, reg, uv=None, isl=-1):
        """Add a face whose normal points along direction (vertex order, and UVs, flipped if needed)."""
        a, b, c = (self.v[i] for i in idx[:3])
        n = (b - a).cross(c - b)
        if n.dot(direction) < 0:
            idx = list(reversed(idx))
            uv = list(reversed(uv)) if uv is not None else None
        self.face(idx, part, reg, uv, isl)

    def cap(self, ring, part, reg, flip=False, isl=-1, v=0.0):
        """n-gon over a ring; with an island it reuses the ring's texels (zero-area UVs: no extra vertices)."""
        n = len(ring)
        order = list(range(n))[::-1] if flip else list(range(n))
        self.face([ring[k] for k in order], part, reg, [(k / n, v) for k in order] if isl >= 0 else None, isl)

    def box(self, center, size, rot, part, reg, w, taper=None):
        """Oriented box: rot = 3x3 Matrix (columns = local axes), taper = (sx, sz) scale of the +y end. UVs: the four
        sides as one strip around the local y axis (one seam), the ends on the strip's edges."""
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
                if q == (0, 4, 6, 2) and u == 0.0:                     # the -x side closes the strip at u = 1
                    u = 1.0
                uv.append((u, 1.0 if k & 2 else 0.0))
            self.face([idx[i] for i in q], part, reg, uv, isl)
        return idx

    def ellipsoid(self, c, r, segs, rings, part, reg, w, deform=None, zmin=-1.0, zmax=1.0, close_bottom=True):
        """UV ellipsoid (optionally a z-slice) with a deform(p_unit, p) hook; reg may be a function of the face centre."""
        rows = []
        for i in range(rings + 1):
            t = zmax - (zmax - zmin) * i / rings                    # unit-sphere height of this ring
            if abs(t) >= 0.999:
                p_unit = V3(0, 0, 1 if t > 0 else -1)
                p = c + V3(0, 0, r[2] * p_unit.z)
                if deform:
                    p = deform(p_unit, p)
                rows.append([self.vert(p, w)])
                continue
            rr = math.sqrt(max(0.0, 1 - t * t))
            row = []
            for j in range(segs):
                a = 2 * math.pi * j / segs
                p_unit = V3(rr * math.cos(a), rr * math.sin(a), t)
                p = c + V3(r[0] * p_unit.x, r[1] * p_unit.y, r[2] * p_unit.z)
                if deform:
                    p = deform(p_unit, p)
                row.append(self.vert(p, w))
            rows.append(row)
        arc = math.acos(max(-1.0, min(1.0, zmin))) - math.acos(max(-1.0, min(1.0, zmax)))
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


def frame_for(t, ref=V3(1, 0, 0)):
    """Orthonormal (e1, e2) across the direction t; e1 follows ref as closely as possible."""
    t = t.normalized()
    e1 = ref - t * ref.dot(t)
    if e1.length < 1e-6:
        e1 = V3(0, 1, 0) - t * t.y
    e1.normalize()
    return e1, t.cross(e1)


def lerpw(a, b, s):
    """Blend two weight dicts."""
    out = {}
    for k, v in a.items():
        out[k] = out.get(k, 0.0) + v * (1 - s)
    for k, v in b.items():
        out[k] = out.get(k, 0.0) + v * s
    return {k: v for k, v in out.items() if v > 1e-6}


def limb(g, pts, radii, wts, segs, part, regs, ref=V3(1, 0, 0), cap_end=False, cap_start=False, flat=1.0):
    """Loft a tube through pts (one ring each), radii per ring, weights per ring, region per band. One UV island:
    u around (seam at ring vertex 0), v along the length."""
    rings = []
    for i, (p, r, w) in enumerate(zip(pts, radii, wts)):
        t = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
        e1, e2 = frame_for(t, ref)
        rings.append(g.ring(p, e1, e2, r, r * flat, r * flat, segs, w))
    lens = [0.0]
    for a, b in zip(pts, pts[1:]):
        lens.append(lens[-1] + (b - a).length)
    total = max(lens[-1], 1e-3)
    isl = g.island(math.pi * (1 + flat) * sum(radii) / len(radii), total)
    for i in range(len(rings) - 1):
        g.bridge(rings[i], rings[i + 1], part, regs[i], isl, lens[i] / total, lens[i + 1] / total)
    if cap_start:
        g.cap(rings[0], part, regs[0], flip=True, isl=isl, v=0.0)
    if cap_end:
        g.cap(rings[-1], part, regs[-1], isl=isl, v=1.0)
    return rings


def add_body(g, d):
    """The body at detail d: dict of segment counts. Torso, neck, head, arms, hands, legs, shoes."""
    # ---- torso: (z, rx, ry front, ry back, weights)
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
    if d["torso_rings"] < len(torso):
        keep = {0, 1, 2, 4, 6, 7} if d["torso_rings"] == 6 else {0, 1, 4, 6, 7}
        torso = [r for i, r in enumerate(torso) if i in keep]
    rings = []
    for z, rx, ryf, ryb in torso:
        def shoulder_w(p, z=z):                                      # the shoulder line follows the clavicles a bit
            w = tw(z)
            if z > 1.40 and abs(p.x) > 0.09:
                side = "R" if p.x > 0 else "L"
                w = lerpw(w, {f"clav.{side}": 1.0}, 0.35)
            return w
        rings.append(g.ring(V3(0, -0.005, z), V3(1, 0, 0), V3(0, 1, 0), rx, ryf, ryb, d["torso"], shoulder_w,
                            phase=math.pi / d["torso"]))
    zs = [r[0] for r in torso]
    tisl = g.island(2 * math.pi * max(r[1] for r in torso), zs[-1] - zs[0])
    vz = [(z - zs[0]) / (zs[-1] - zs[0]) for z in zs]
    for i in range(len(rings) - 1):
        g.bridge(rings[i], rings[i + 1], "body", "pants_top" if zs[i + 1] <= 0.90 else "torso", tisl, vz[i], vz[i + 1])
    g.cap(rings[0], "body", "pants_top", flip=True, isl=tisl, v=0.0)
    g.cap(rings[-1], "body", "torso", isl=tisl, v=1.0)
    # ---- neck
    if d["neck"]:
        limb(g, [V3(0, 0.0, 1.43), V3(0, 0.012, 1.555)], [0.062, 0.056],
             [{"spine2": 0.5, "neck": 0.5}, {"neck": 0.4, "head": 0.6}], d["neck"], "body", ["skin"])
    # ---- head: an ellipsoid with a jaw, a chin, a nose, cheeks; the scalp region gets hair colour for buzz cuts
    hc = V3(0, 0.012, 1.630)

    def head_deform(u, p):
        q = p.copy()
        if u.z < -0.15:                                              # jaw narrows toward the chin
            k = min(1.0, (-0.15 - u.z) / 0.85)
            q.x = hc.x + (q.x - hc.x) * (1 - 0.35 * k)
            if u.y < 0:
                q.y = hc.y + (q.y - hc.y) * (1 - 0.25 * k)
        if u.y > 0.55 and abs(u.x) < 0.35 and -0.35 < u.z < 0.15:   # nose
            q.y += 0.018 * (1 - abs(u.x) / 0.35)
        if u.y > 0.3 and u.z < -0.55:                                # chin forward
            q.y += 0.01
        if u.y < -0.2 and u.z > -0.2:                                # back of the skull
            q.y -= 0.008
        return q

    def head_reg(c):
        u = c - hc
        if u.z > 0.045 or (u.y < -0.02 and u.z > -0.04):
            return "scalp"
        if d.get("face_detail") and u.y > 0.03:                    # front faces: sockets, brow, mouth (albedo only)
            ang = math.degrees(math.atan2(u.y, u.x))
            if 0.0 < u.z < 0.028 and 55 < ang < 125:
                return "eyes"
            if 0.028 < u.z < 0.056 and 35 < ang < 145:
                return "brow"
            if -0.056 < u.z < -0.028 and 62 < ang < 118:
                return "mouth"
        return "face"
    g.ellipsoid(hc, (0.074, 0.093, 0.112), d["head_segs"], d["head_rings"], "body", head_reg, {"head": 1.0},
                deform=head_deform)
    # ---- arms + hands (both sides)
    for s, n in ((1, "R"), (-1, "L")):
        sh, el, wr, fi = J[f"shoulder.{n}"], J[f"elbow.{n}"], J[f"wrist.{n}"], J[f"fingers.{n}"]
        ua, fa, ha = f"upperarm.{n}", f"forearm.{n}", f"hand.{n}"
        pts = [sh + V3(-s * 0.02, 0, -0.012), sh.lerp(el, 0.45), el, el.lerp(wr, 0.5), wr]
        rad = [0.056, 0.049, 0.041, 0.040, 0.031]
        wts = [{ua: 0.75, f"clav.{n}": 0.25}, {ua: 1.0}, {ua: 0.5, fa: 0.5}, {fa: 1.0}, {fa: 0.4, ha: 0.6}]
        regs = ["sleeve_top", "sleeve_mid", "sleeve_low", "sleeve_low"]
        if d["arm_rings"] == 3:
            pts, rad, wts = [pts[0], pts[2], pts[4]], [rad[0], rad[2], rad[4]], [wts[0], wts[2], wts[4]]
            regs = ["sleeve_mid", "sleeve_low"]
        limb(g, pts, rad, wts, d["arm"], "body", regs, ref=V3(0, 1, 0))
        # hand: a mitten (palm box tapering to the fingers) + a thumb; palm faces the thigh
        hd = (fi - wr).normalized()
        rot = Matrix((V3(0, 1, 0).cross(hd).normalized() * s, hd, V3(0, 1, 0).cross(hd).normalized().cross(hd) * s)).transposed()
        g.box(wr.lerp(fi, 0.5), (0.038, (fi - wr).length, 0.088), rot, "body", "hand", {ha: 1.0}, taper=(0.75, 0.85))
        if d["thumb"]:
            g.box(wr.lerp(fi, 0.33) + V3(-s * 0.004, 0.04, 0.0), (0.022, 0.06, 0.022), rot, "body", "hand", {ha: 1.0})
    # ---- legs + shoes
    for s, n in ((1, "R"), (-1, "L")):
        hp, kn, an = J[f"hip.{n}"], J[f"knee.{n}"], J[f"ankle.{n}"]
        th, sn, ft = f"thigh.{n}", f"shin.{n}", f"foot.{n}"
        pts = [hp + V3(0, 0, 0.03), hp.lerp(kn, 0.3), hp.lerp(kn, 0.62), kn, kn.lerp(an, 0.4), an + V3(0, 0, 0.02)]
        rad = [0.086, 0.081, 0.071, 0.054, 0.057, 0.040]
        wts = [{th: 1.0}, {th: 1.0}, {th: 1.0}, {th: 0.5, sn: 0.5}, {sn: 1.0}, {sn: 0.6, ft: 0.4}]
        regs = ["pants_top", "pants_mid", "pants_mid", "pants_low", "pants_low"]
        if d["leg_rings"] == 4:
            pts, rad, wts = [pts[0], pts[2], pts[3], pts[5]], [rad[0], rad[2], rad[3], rad[5]], [wts[0], wts[2], wts[3], wts[5]]
            regs = ["pants_top", "pants_mid", "pants_low"]
        elif d["leg_rings"] == 3:
            pts, rad, wts = [pts[0], pts[3], pts[5]], [rad[0], rad[3], rad[5]], [wts[0], wts[3], wts[5]]
            regs = ["pants_mid", "pants_low"]
        limb(g, pts, rad, wts, d["leg"], "body", regs, ref=V3(1, 0, 0))
        # shoe: a sole box plus a tapered upper toward the toe
        if d.get("one_box_shoes"):
            g.box(V3(an.x, 0.03, 0.045), (0.095, 0.26, 0.09), Matrix.Identity(3), "body", "shoe", {ft: 1.0}, taper=(0.85, 0.6))
        else:
            g.box(V3(an.x, 0.035, 0.022), (0.098, 0.275, 0.044), Matrix.Identity(3), "body", "sole", {ft: 1.0},
                  taper=(0.85, 1.0))
            g.box(V3(an.x, 0.02, 0.068), (0.09, 0.2, 0.06), Matrix.Identity(3), "body", "shoe", {ft: 1.0}, taper=(0.9, 0.6))


def add_hair_and_hats(g, d):
    """Optional head parts (each its own part id): hair styles, caps, bucket hats, beanies, hoodie hood."""
    hc = V3(0, 0.012, 1.630)
    hw = {"head": 1.0}
    segs = d["hair_segs"]

    def dome(part, reg, scale, zmin, front_cut=0.0, extra_back=0.0):
        """A shell over the head: unit-sphere slice from the top down to zmin (lower at the back by extra_back). Near
        tier: strands - a jittered shell with crown volume and a jagged fringe / nape edge (no helmet)."""
        strands = d.get("hair_strands", False) and reg == "hair"      # hats keep a clean shell

        def deform(u, p):
            q = p.copy()
            if u.y < 0 and u.z < 0.2:                                  # longer at the back
                q.z -= extra_back * (-u.y)
            if u.y > 0.35 and u.z < 0.35:                              # cut away above the forehead
                q.z += front_cut * (u.y - 0.35)
            if strands:
                if u.z > 0.3:                                          # crown volume, a bit higher at the back
                    q.z += 0.012 * (u.z - 0.3) + 0.006 * max(0.0, -u.y)
                k = math.sin(37.0 * u.x + 23.0 * u.y + 11.0 * u.z)     # deterministic tufts
                q = hc + (q - hc) * (1.0 + 0.045 * k)
            return q
        rows = g.ellipsoid(hc + V3(0, -0.004, 0.006), (0.074 * scale, 0.093 * scale, 0.112 * scale), segs,
                           d["hair_rings"], part, reg, hw, deform=deform, zmin=zmin, zmax=1.0, close_bottom=False)
        if strands:                                                    # jagged lower edge: every other vertex lower
            for j, vi in enumerate(rows[-1]):
                if j % 2:
                    front = (g.v[vi] - hc).y > 0.04
                    g.v[vi] = g.v[vi] + V3(0, 0, -(0.012 if front else 0.028))
    dome("hair_short", "hair", 1.09, -0.15, front_cut=0.10, extra_back=0.02)
    dome("hair_long", "hair", 1.10, -0.25, front_cut=0.10, extra_back=0.03)
    # long hair: a curtain down the back to the shoulder blades (curved, ragged bottom; two-sided)
    cols_x = (-0.095, -0.05, 0.0, 0.05, 0.095) if d.get("hair_strands") else (-0.085, 0.085)
    for side, back in ((1, -0.097), (-1, -0.083)):
        grid = []
        for zi, z in enumerate((1.63, 1.52, 1.40)):
            row = []
            for xi, x in enumerate(cols_x):
                drop = (0.035 if (xi % 2) else 0.0) if zi == 2 else 0.0
                yy = back + 3.0 * x * x - 0.012 * (1.63 - z) / 0.23
                row.append(g.vert(V3(x * (1 + 0.15 * (1.63 - z) / 0.23), yy, z - drop),
                                  lerpw({"head": 1.0}, {"neck": 1.0}, min(1.0, (1.63 - z) / 0.25))))
            grid.append(row)
        hisl = g.island(2 * max(cols_x), 0.26)
        nx = len(cols_x) - 1
        for zi in range(len(grid) - 1):
            for xi in range(nx):
                q = (grid[zi][xi], grid[zi][xi + 1], grid[zi + 1][xi + 1], grid[zi + 1][xi])
                uv = ((xi / nx, 1 - zi / 2), ((xi + 1) / nx, 1 - zi / 2), ((xi + 1) / nx, 1 - (zi + 1) / 2),
                      (xi / nx, 1 - (zi + 1) / 2))
                g.face_toward(q, V3(0, -side, 0), "hair_long", "hair", uv, hisl)
    dome("hair_pony", "hair", 1.08, -0.18, front_cut=0.10)
    limb(g, [hc + V3(0, -0.11, 0.06), hc + V3(0, -0.15, -0.05), hc + V3(0, -0.155, -0.2)], [0.03, 0.026, 0.012],
         [hw, hw, hw], max(4, segs // 2), "hair_pony", ["hair", "hair"], ref=V3(1, 0, 0), cap_end=True)
    dome("hair_bun", "hair", 1.07, -0.15, front_cut=0.10)
    g.ellipsoid(hc + V3(0, -0.07, 0.10), (0.045, 0.045, 0.04), max(6, segs // 2), 4, "hair_bun", "hair", hw)
    # cap: crown + a brim to the front
    dome("hat_cap", "hat", 1.19, 0.05, front_cut=0.0)                   # outside the jittered hair (<= 1.15)
    brim_pts = [hc + V3(x, y, 0.035 - 0.02 * max(0.0, y - 0.1) / 0.08)
                for x, y in ((-0.08, 0.08), (0.08, 0.08), (0.075, 0.18), (-0.075, 0.18))]
    g.face_toward([g.vert(q, hw) for q in brim_pts], V3(0, 0, 1), "hat_cap", "hat2")
    g.face_toward([g.vert(q - V3(0, 0, 0.004), hw) for q in brim_pts], V3(0, 0, -1), "hat_cap", "hat2")
    # bucket hat: crown + sloping brim ring
    crown = limb(g, [hc + V3(0, -0.004, 0.04), hc + V3(0, -0.004, 0.158)], [0.114, 0.09], [hw, hw], segs, "hat_bucket",
                 ["hat"], cap_end=True)
    outer = g.ring(hc + V3(0, -0.004, 0.012), V3(1, 0, 0), V3(0, 1, 0), 0.16, 0.165, 0.16, segs, hw)
    g.bridge(crown[0], outer, "hat_bucket", "hat2", g.island(2 * math.pi * 0.16, 0.05), 0.0, 1.0)
    under_in = [g.vert(g.v[i] - V3(0, 0, 0.005), hw) for i in crown[0]]
    under_out = [g.vert(g.v[i] - V3(0, 0, 0.005), hw) for i in outer]
    g.bridge(list(reversed(under_out)), list(reversed(under_in)), "hat_bucket", "hat2", g.island(2 * math.pi * 0.16, 0.05),
             0.0, 1.0)
    # beanie: a taller dome
    dome("hat_beanie", "hat", 1.19, 0.0)
    g.ellipsoid(hc + V3(0, -0.01, 0.125), (0.03, 0.03, 0.025), max(5, segs // 2), 3, "hat_beanie", "hat2", hw)
    # hoodie hood lying on the upper back (a squashed half tube around the neck)
    if d["hood"]:
        pts = [V3(-0.13, -0.03, 1.47), V3(-0.09, -0.12, 1.45), V3(0, -0.15, 1.44), V3(0.09, -0.12, 1.45), V3(0.13, -0.03, 1.47)]
        limb(g, pts, [0.03, 0.05, 0.055, 0.05, 0.03], [{"spine2": 1.0}] * 5, max(4, segs // 2), "hood", ["hood"] * 4,
             ref=V3(0, 0, 1), flat=0.7)


def add_items(g, d):
    """Optional carried items (right hand / back): backpack, phone, glowstick, totems on poles. The phone and the pole
    stand upright in the fist (the "hold" clip keeps the hand upright overhead); the glowstick extends the hand."""
    hw = {"hand.R": 1.0}
    wr, fi = J["wrist.R"], J["fingers.R"]
    grip = wr.lerp(fi, 0.45)
    hd = (fi - wr).normalized()
    # backpack / hydration pack on the upper back, straps over the shoulders and down the chest
    g.box(V3(0, -0.175, 1.20), (0.26, 0.11, 0.34), Matrix.Identity(3), "pack", "pack", {"spine2": 1.0})
    if d["straps"]:
        for s in (1, -1):
            g.box(V3(s * 0.10, 0.09, 1.30), (0.04, 0.03, 0.24), Matrix.Rotation(math.radians(-12), 3, "X"), "pack", "strap",
                  {"spine2": 1.0})
            g.box(V3(s * 0.10, -0.03, 1.448), (0.04, 0.2, 0.03), Matrix.Identity(3), "pack", "strap", {"spine2": 1.0})
    # phone upright above the fist: screen toward the person (-Y), flash on the back toward the stage (+Y)
    pc = grip + V3(0, 0.0, 0.11)
    g.box(pc, (0.072, 0.012, 0.15), Matrix.Identity(3), "phone", "phone", hw)
    scr = [g.vert(pc + V3(x, -0.0065, z), hw) for x, z in ((-0.031, -0.065), (0.031, -0.065), (0.031, 0.068), (-0.031, 0.068))]
    g.face_toward(scr, V3(0, -1, 0), "phone", "glow_screen")
    fl = [g.vert(pc + V3(x, 0.0065, z), hw) for x, z in ((0.008, 0.035), (0.028, 0.035), (0.028, 0.06), (0.008, 0.06))]
    g.face_toward(fl, V3(0, 1, 0), "phone", "glow_flash")
    # glowstick: continues the hand (points down at rest, up when the arm is raised)
    limb(g, [grip + hd * 0.02, grip + hd * 0.24], [0.011, 0.011], [hw, hw], 4, "glowstick", ["glow_stick"],
         cap_end=True, cap_start=True)
    # totem pole: upright through the fist, ~1.95 m above it (overhead in the "hold" clip: top at ~4 m)
    top = grip + V3(0, 0, 1.95)
    limb(g, [grip + V3(0, 0, -0.25), top], [0.016, 0.014], [hw, hw], d["pole_segs"], "pole", ["pole"], cap_end=True)
    # flag: two-tone cloth, two-sided
    for z0, z1, reg in ((0.0, -0.32, "flag1"), (-0.32, -0.62, "flag2")):
        q = [top + V3(dx, 0, dz) for dx, dz in ((0.02, z0), (0.95, z0 - 0.04), (0.95, z1 - 0.04), (0.02, z1))]
        g.face_toward([g.vert(p + V3(0, 0.004, 0), hw) for p in q], V3(0, 1, 0), "flag", reg)
        g.face_toward([g.vert(p - V3(0, 0.004, 0), hw) for p in q], V3(0, -1, 0), "flag", reg)
    # LED sign: a board with a glowing frame on both faces
    g.box(top + V3(0, 0, -0.30), (0.62, 0.025, 0.46), Matrix.Identity(3), "sign", "sign", hw)
    for side in (1, -1):
        y = side * 0.0135
        for (x0, z0, x1, z1) in ((-0.31, 0.21, 0.31, 0.25), (-0.31, -0.25, 0.31, -0.21), (-0.31, -0.21, -0.27, 0.21),
                                 (0.27, -0.21, 0.31, 0.21)):
            q = [g.vert(top + V3(x, y, -0.30 + z), hw) for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1))]
            g.face_toward(q, V3(0, side, 0), "sign", "glow_led")
    # inflatable: a squashed blob on top
    g.ellipsoid(top + V3(0, 0, 0.22), (0.30, 0.22, 0.26), d["blob_segs"], max(3, d["blob_segs"] // 2), "inflatable",
                "inflatable", hw)
    # dino cut-out: a flat silhouette board (two-sided)
    sil = [(-0.40, 0.00), (-0.15, 0.05), (0.05, 0.02), (0.18, 0.12), (0.30, 0.13), (0.34, 0.06), (0.22, 0.04),
           (0.20, -0.12), (0.10, -0.12), (0.06, -0.04), (-0.12, -0.05), (-0.16, -0.14), (-0.24, -0.14), (-0.24, -0.04)]
    for side in (1, -1):
        q = [g.vert(top + V3(x * 1.2, side * 0.006, z * 1.2 - 0.10), hw) for x, z in sil]
        g.face_toward(q, V3(0, side, 0), "cutout", "cutout")


def add_far_body(g):
    """~36 tris: a 4-sided column (feet -> hips -> chest -> shoulders), a bipyramid head, two straight arm ribbons facing
    the stage; holders get a pole + flag quad, phone people a flash quad."""
    col = [(0.02, 0.15, 0.09, {"foot.R": 0.5, "foot.L": 0.5}), (0.90, 0.17, 0.10, {"pelvis": 1.0}),
           (1.27, 0.17, 0.10, {"spine2": 1.0}), (1.44, 0.15, 0.07, {"spine2": 1.0})]
    rings = [g.ring(V3(0, 0, z), V3(1, 0, 0), V3(0, 1, 0), rx, ry, ry, 4, w, phase=math.pi / 4) for z, rx, ry, w in col]
    zs = [c_[0] for c_ in col]
    cisl = g.island(2 * (0.30 + 0.18), zs[-1] - zs[0])
    vz = [(z - zs[0]) / (zs[-1] - zs[0]) for z in zs]
    for i, reg in enumerate(("pants_low", "torso", "torso")):
        g.bridge(rings[i], rings[i + 1], "body", reg, cisl, vz[i], vz[i + 1])
    g.cap(rings[-1], "body", "torso", isl=cisl, v=1.0)
    hc = V3(0, 0.01, 1.62)                                            # head: a triangular bipyramid
    top = g.vert(hc + V3(0, 0, 0.13), {"head": 1.0})
    bot = g.vert(hc + V3(0, 0, -0.10), {"head": 1.0})
    eq = [g.vert(hc + V3(0.09 * math.cos(a_), 0.1 * math.sin(a_), 0), {"head": 1.0})
          for a_ in (math.pi / 2, math.pi / 2 + 2.094, math.pi / 2 + 4.189)]
    hisl = g.island(2 * math.pi * 0.095, 0.23)
    for k in range(3):
        out = (g.v[eq[k]] + g.v[eq[(k + 1) % 3]]) / 2 - hc
        g.face_toward((top, eq[k], eq[(k + 1) % 3]), out, "body", "scalp", ((0.5, 1.0), (k / 3, 0.5), ((k + 1) / 3, 0.5)), hisl)
        g.face_toward((bot, eq[(k + 1) % 3], eq[k]), out, "body", "face", ((0.5, 0.0), ((k + 1) / 3, 0.5), (k / 3, 0.5)), hisl)
    for s_, n in ((1, "R"), (-1, "L")):                               # arms: one quad each, shoulder -> fingertips
        sh, fi = J[f"shoulder.{n}"], J[f"fingers.{n}"]
        q = [g.vert(sh + V3(-0.035, 0.02, 0), {f"upperarm.{n}": 1.0}), g.vert(sh + V3(0.035, 0.02, 0), {f"upperarm.{n}": 1.0}),
             g.vert(fi + V3(0.03, 0.02, 0), {f"hand.{n}": 1.0}), g.vert(fi + V3(-0.03, 0.02, 0), {f"hand.{n}": 1.0})]
        g.face_toward(q, V3(0, 1, 0), "body", "sleeve_mid")
    hw = {"hand.R": 1.0}                                              # far holders: pole + flag only
    grip = J["fingers.R"]
    top_ = grip + V3(0, 0, 1.95)
    p = [g.vert(grip + V3(dx, 0.02, dz), hw) for dx, dz in ((-0.02, -0.2), (0.02, -0.2), (0.02, 1.95), (-0.02, 1.95))]
    g.face_toward(p, V3(0, 1, 0), "pole", "pole")
    fq = [g.vert(top_ + V3(dx, 0.02, dz), hw) for dx, dz in ((0.02, 0.0), (0.9, -0.05), (0.9, -0.6), (0.02, -0.55))]
    g.face_toward(fq, V3(0, 1, 0), "flag", "flag1")
    g.face_toward([g.vert(grip + V3(dx, 0.025, dz), hw) for dx, dz in ((-0.03, 0.0), (0.03, 0.0), (0.03, 0.12), (-0.03, 0.12))],
                  V3(0, 1, 0), "phone", "glow_flash")


DETAIL = {
    "near": {"torso": 12, "torso_rings": 8, "neck": 8, "head_segs": 12, "head_rings": 8, "arm": 8, "arm_rings": 5,
             "leg": 8, "leg_rings": 6, "thumb": True, "hair_segs": 12, "hair_rings": 4, "hood": True, "straps": True,
             "pole_segs": 5, "blob_segs": 8, "face_detail": True, "hair_strands": True},
    "mid": {"torso": 6, "torso_rings": 5, "neck": 0, "head_segs": 6, "head_rings": 4, "arm": 4, "arm_rings": 3,
            "leg": 4, "leg_rings": 3, "thumb": False, "hair_segs": 6, "hair_rings": 2, "hood": False, "straps": False,
            "pole_segs": 3, "blob_segs": 6, "one_box_shoes": True},
}
OPTIONAL_PARTS = ("hair_short", "hair_long", "hair_pony", "hair_bun", "hat_cap", "hat_bucket", "hat_beanie", "hood",
                  "pack", "phone", "glowstick", "pole", "flag", "sign", "inflatable", "cutout")
PARTS = ("body",) + OPTIONAL_PARTS
PART = {p: i for i, p in enumerate(PARTS)}


def build_canonical(tier):
    g = Geo()
    if tier == "far":
        add_far_body(g)
    else:
        add_body(g, DETAIL[tier])
        add_hair_and_hats(g, DETAIL[tier])
        add_items(g, DETAIL[tier])
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


def _leg(g, n, lift=0.0, dx=0.0, toe=0.0):
    """Two-bone IK: the hip follows the pelvis, the ankle goes to its rest spot (+dx, +lift), the knee bends forward."""
    hip0, knee0, ank0 = J[f"hip.{n}"], J[f"knee.{n}"], J[f"ankle.{n}"]
    hip1, ank1 = g["pelvis"] @ hip0, ank0 + V3(dx, 0, lift)
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
    g[f"foot.{n}"] = Tm(ank1) @ Rx(toe).to_4x4() @ Tm(-ank0)        # foot stays level unless toe pitch


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


def pose(clip, p):
    """G (4x4 mathutils) per bone at loop position p in [0, 1): one loop = 2 beats; q = position inside the beat."""
    q = (2.0 * p) % 1.0
    sw = math.sin(2 * math.pi * p)                                    # one sway cycle per loop
    beat = (0.5 + 0.5 * math.cos(2 * math.pi * q)) ** 2               # 1 on the beat, 0 between
    g = {}
    lift, toe = 0.0, 0.0
    if clip == "jump":                                                # hands up, a hop on every beat
        a = 0.45
        if q < a:
            air, crouch, tuck = 0.20 * math.sin(math.pi * q / a), 0.0, 0.07 * math.sin(math.pi * q / a)
        else:
            air, crouch, tuck = 0.0, 0.11 * math.sin(math.pi * (q - a) / (1 - a)), 0.0
        k = crouch / 0.11
        _trunk(g, V3(0, -0.25 * crouch, air - crouch), s1=Rx(-5 * k), s2=Rx(-(6 * k - 2 * air / 0.2)), neck=Rx(-3 * k),
               head=Rx(-4 * k))
        for n in "RL":
            _arm(g, n, 150 + 12 * math.sin(2 * math.pi * q), 18, 25 + 25 * k, shrug=10)
        lift, toe = air + tuck, -18 * air / 0.2
    elif clip == "pump":                                              # right fist pump on the beat, knee bounce
        pump = (0.5 + 0.5 * math.cos(2 * math.pi * (q - 0.12))) ** 3
        b = 0.045 * beat
        _trunk(g, V3(0, -0.2 * b, -b), s2=Rz(6 * pump) @ Rx(4 * pump), neck=Rx(-3), head=Rx(-(2 + 8 * pump)))
        _arm(g, "R", 95 + 70 * pump, 12 + 6 * pump, 100 - 85 * pump, shrug=8 * pump)
        _arm(g, "L", 14 + 6 * pump, 6, 30 + 10 * pump)
    elif clip == "sway":                                              # weight shift side to side, dance arms
        b = 0.03 * beat
        _trunk(g, V3(0.05 * sw, 0, -b), pelvis=Ry(4 * sw) @ Rz(6 * sw), s1=Ry(-3 * sw), s2=Ry(-3 * sw) @ Rz(-4 * sw),
               neck=Ry(3 * sw), head=Ry(4 * sw) @ Rx(-4 * beat))
        _arm(g, "R", 48 + 14 * sw, 12 + 6 * sw, 85, wrist=-10)
        _arm(g, "L", 48 - 14 * sw, 12 - 6 * sw, 85, wrist=-10)
    elif clip == "headbang":                                          # bang on the beat, horns up
        k = (0.5 + 0.5 * math.cos(2 * math.pi * (q - 0.05))) ** 2
        _trunk(g, V3(0, -0.02 * k, -0.045 * k), s1=Rx(-6 * k), s2=Rx(-(8 + 12 * k)), neck=Rx(-(8 + 24 * k)),
               head=Rx(-(4 + 16 * k)))
        for n in "RL":
            _arm(g, n, 140 - 28 * k, 20, 55 + 15 * k, shrug=6)
    elif clip == "clap":                                              # clap overhead on the beat
        c = (0.5 + 0.5 * math.cos(2 * math.pi * q)) ** 3
        _trunk(g, V3(0, 0, -0.03 * c), s2=Rx(2 * c), head=Rx(-5 * c))
        for n in "RL":
            _arm(g, n, 152, 16 - 40 * c, 30 + 15 * c, shrug=8)
    elif clip == "wave":                                              # both arms up, swaying together
        w = 22 * sw
        _trunk(g, V3(0.04 * sw, 0, -0.025 * beat), pelvis=Ry(3 * sw), s2=Ry(4 * sw), head=Ry(5 * sw))
        _arm(g, "R", 165, 12 + w, 15, shrug=10)
        _arm(g, "L", 165, 12 - w, 15, shrug=10)
    elif clip == "hold":                                              # totem / phone overhead, bobbing
        b = 0.035 * beat
        _trunk(g, V3(0, 0, -b), s2=Ry(-2 * sw), head=Rx(-4 * beat) @ Ry(3 * sw))
        _arm(g, "R", 168, 8 + 3 * sw, 18, shrug=12, upright=4 * sw)
        _arm(g, "L", 28 + 10 * beat, 8, 45)
    else:                                                             # "bounce": chill knee bounce, head nod
        b = 0.035 * beat
        _trunk(g, V3(0, -0.01 * beat, -b), pelvis=Rz(3 * sw), s2=Rz(-2 * sw), head=Rx(-6 * beat))
        _arm(g, "R", 12 + 6 * math.sin(2 * math.pi * q), 6, 25, shrug=3 * beat)
        _arm(g, "L", 12 - 6 * math.sin(2 * math.pi * q), 6, 25, shrug=3 * beat)
    for n in "RL":
        _leg(g, n, lift=lift, toe=toe)
    return g


# ============================================================================ canonical meshes as arrays
def pack_islands(sizes, margin=0.015):
    """Shelf-pack rectangles (w, h in meters) into the unit square at one uniform scale (equal texel density).
    Returns [(ox, oy, sw, sh)] in unit space."""
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


class Canon:
    """One tier's superset mesh as numpy arrays + its two UV layouts (body cell, totem cell)."""
    TOTEM_PARTS = ("pole", "flag", "sign", "inflatable", "cutout")

    def __init__(self, tier):
        g = build_canonical(tier)
        self.tier = tier
        self.V = np.array([tuple(v) for v in g.v], dtype=np.float64)
        self.W = np.zeros((len(g.v), len(BONE_NAMES)))
        for i, wd in enumerate(g.w):
            for b, w in wd.items():
                self.W[i, BONE_IDX[b]] += w
        self.W /= self.W.sum(1, keepdims=True)
        self.F_len = np.array([len(f) for f in g.f], dtype=np.int64)
        self.F_start = np.concatenate([[0], np.cumsum(self.F_len)[:-1]])
        self.L_vert = np.array([v for f in g.f for v in f], dtype=np.int64)
        self.L_face = np.repeat(np.arange(len(g.f)), self.F_len)
        k = np.arange(len(self.L_vert)) - self.F_start[self.L_face]
        self.L_rev = self.F_start[self.L_face] + (self.F_len[self.L_face] - 1 - k)   # mirrored winding
        self.F_part = np.array([PART[p] for p in g.fpart], dtype=np.int64)
        self.F_reg = np.array(g.freg, dtype=np.int64)
        self.F_glow = np.isin(self.F_reg, list(GLOW_REGIONS))
        totem = np.isin(self.F_part, [PART[p] for p in self.TOTEM_PARTS])
        f_isl = np.array(g.fisl, dtype=np.int64)
        local = np.array([uv for f_uv in g.fuv for uv in f_uv], dtype=np.float64)       # per loop, island-local 0..1
        place = np.zeros((len(g.isl), 4))
        for mask in (~self.F_glow & ~totem, ~self.F_glow & totem):       # body cell layout, totem cell layout
            used = sorted(set(f_isl[mask].tolist()))
            for i, rect in zip(used, pack_islands([g.isl[i] for i in used])):
                place[i] = rect
        pl = place[f_isl[self.L_face]]
        self.L_uv = np.stack([pl[:, 0] + local[:, 0] * pl[:, 2], pl[:, 1] + local[:, 1] * pl[:, 3]], 1)
        self.L_uv[self.F_glow[self.L_face]] = 0.0
        self.L_cell = totem[self.L_face].astype(np.int64)             # 0 = body cell, 1 = totem cell
        self.tris = int((self.F_len - 2).sum())

    def posed(self, clip, p):
        g = pose(clip, p)
        out = np.zeros_like(self.V)
        for b, name in enumerate(BONE_NAMES):
            w = self.W[:, b]
            if not w.any():
                continue
            m = np.array(g[name])
            out += w[:, None] * (self.V @ m[:3, :3].T + m[:3, 3])
        return out


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


def bake_vat(canons):
    """Offsets of every tier's superset vertices for every clip frame -> (texture HxWx4 float32, column offsets)."""
    cols, off = {}, 0
    for c in canons:
        cols[c.tier] = off
        off += len(c.V)
    tex_w = 1 << (off - 1).bit_length()
    tex_h = 1 << (len(CLIPS) * ROWS - 1).bit_length()
    tex = np.zeros((tex_h, tex_w, 4), dtype=np.float32)
    tex[..., 3] = 1.0
    for ci, clip in enumerate(CLIPS):
        for f in range(ROWS):
            for c in canons:
                o = c.posed(clip, (f % FRAMES) / FRAMES) - c.V
                tex[ci * ROWS + f, cols[c.tier]:cols[c.tier] + len(c.V), :3] = o
    return tex, cols


# ============================================================================ the field
def crowd_half_v2(y):
    """Proposed half-width of the packed crowd at depth y (y < 0): wider at the front sides than before."""
    return 20.0 + 0.55 * (-y)


Y_FRONT, Y_BACK = -8.6, -66.0
TIERS = (("near", 12.0), ("mid", 20.5), ("far", 1e9))     # by distance from the DJ (origin)
CLIP_WEIGHTS = {"jump": 0.20, "pump": 0.17, "sway": 0.15, "headbang": 0.07, "clap": 0.10, "wave": 0.12, "bounce": 0.19}
POSE_CLIPS = {"down": ("bounce", "sway"), "up": ("jump", "wave"), "one": ("pump",), "hips": ("bounce",)}


def _excluded(x, y, exclude):
    return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in exclude)


def _field(rng, scale, half_fn, exclude):
    pts = []
    y = Y_FRONT
    while y > Y_BACK:
        gap = scale * (0.62 + 0.0105 * (Y_FRONT - y))
        half = half_fn(y) - 0.3
        x = -half + rng.uniform(0, gap)
        while x < half:
            px, py = x + rng.uniform(-0.28, 0.28) * gap, y + rng.uniform(-0.28, 0.28) * gap
            if not _excluded(px, py, exclude):
                pts.append((px, py))
            x += gap * rng.uniform(0.88, 1.12)
        y -= gap * 0.92
    return pts


def layout(rng, exclude, half_fn, target):
    """Field positions with a density scale chosen so the count lands near target (deterministic search)."""
    lo, hi = 0.5, 3.0
    for _ in range(18):
        mid = (lo + hi) / 2
        if len(_field(random.Random(4242), mid, half_fn, exclude)) > target:
            lo = mid
        else:
            hi = mid
    return _field(rng, hi, half_fn, exclude), hi


def make_person(rng, x, y, tier, clip=None, yaw=None, holder_bias=0.0):
    """Everything about one person: placement, body scale, look, parts, clip, phase, rate."""
    d = math.hypot(x, y)
    if yaw is None:                                                   # face the stage (+ a little randomness)
        yaw = math.atan2(-(0.0 - x), 5.0 - y) + rng.gauss(0, 0.22)
    height = min(1.97, max(1.50, rng.gauss(1.72, 0.085)))
    p = {"x": x, "y": y, "tier": tier, "yaw": yaw, "sz": height / H, "sx": rng.uniform(0.9, 1.12),
         "mirror": rng.choice((1.0, -1.0)), "skin": rng.choice(SKINS), "top": rng.choice(TOPS),
         "bottom": rng.choice(BOTTOMS), "shoe": rng.choice(SHOES), "hair_col": rng.choice(HAIRS),
         "hat_col": rng.choice(HATS), "pack_col": rng.choice(PACKS), "flag": rng.sample(FLAGS, 2),
         "glow": rng.choice(GLOWSTICKS), "led": rng.choice(LEDS)}
    p["top_kind"] = rng.choices(("tank", "tee", "long", "hoodie"), weights=(0.18, 0.55, 0.12, 0.15))[0]
    p["bottom_kind"] = rng.choices(("shorts", "long"), weights=(0.33, 0.67))[0]
    parts = {"body"}
    hair = rng.choices(("hair_short", "hair_long", "hair_pony", "hair_bun", None), weights=(0.36, 0.24, 0.1, 0.07, 0.23))[0]
    hat = rng.choices((None, "hat_cap", "hat_bucket", "hat_beanie"), weights=(0.74, 0.12, 0.09, 0.05))[0]
    if hat == "hat_beanie" and hair in ("hair_pony", "hair_bun"):
        hair = "hair_short"
    if hat == "hat_bucket" and hair == "hair_bun":
        hair = "hair_long"
    parts |= {h for h in (hair, hat) if h}
    p["bald"] = hair is None
    if p["top_kind"] == "hoodie" and tier == "near":
        parts.add("hood")
    if rng.random() < 0.16:
        parts.add("pack")
    holder = d > 10.5 and rng.random() < 0.012 + holder_bias
    item = None
    if holder:
        item = rng.choices(("flag", "sign", "inflatable", "cutout"), weights=(0.4, 0.25, 0.15, 0.2))[0]
        parts |= {"pole", item}
        clip = "hold"
    elif rng.random() < 0.05:
        parts.add("phone")
        clip = "hold"
    elif rng.random() < 0.075:
        parts.add("glowstick")
    if tier == "far":                                                 # the far shape: body, pole + flag, a light quad
        if "glowstick" in parts:
            p["flash_col"] = p["glow"]                                # far glowsticks: the hand light quad, stick colour
        parts = {"body"} | ({"pole", "flag"} if holder else set()) | ({"phone"} if parts & {"phone", "glowstick"} else set())
    p["parts"], p["holder"] = parts, holder
    if clip is None:
        clip = rng.choices(list(CLIP_WEIGHTS), weights=list(CLIP_WEIGHTS.values()))[0]
    p["clip"] = clip
    p["phase"] = (0.5 * rng.randrange(2) + rng.gauss(0, 0.035)) % 1.0        # on the beat, a little loose
    rate = 1.0 + rng.gauss(0, 0.012)
    if clip in ("sway", "bounce") and rng.random() < 0.18:
        rate *= 0.5                                                   # half-time movers
    p["rate"] = rate
    return p


def look_colors(p):
    """Region -> linear RGB for this person."""
    skin, top, bottom = p["skin"], p["top"], p["bottom"]
    tk, bk = p["top_kind"], p["bottom_kind"]
    c = {r: skin for r in REGIONS}
    hairc = p["hair_col"]
    c.update({"eyes": tuple(0.28 * v for v in skin), "brow": tuple(0.55 * a + 0.45 * b * 0.6 for a, b in zip(skin, hairc)),
              "mouth": tuple(0.62 * v for v in skin)})
    c.update({"torso": top, "sleeve_top": skin if tk == "tank" else top,
              "sleeve_mid": top if tk in ("long", "hoodie") else skin,
              "sleeve_low": top if tk in ("long", "hoodie") else skin, "pants_top": bottom, "pants_mid": bottom,
              "pants_low": bottom if bk == "long" else skin, "shoe": p["shoe"], "sole": (0.6, 0.6, 0.58),
              "hair": p["hair_col"], "scalp": skin if p["bald"] else p["hair_col"], "hat": p["hat_col"],
              "hat2": tuple(0.7 * v for v in p["hat_col"]), "hood": top, "pack": p["pack_col"], "strap": (0.03, 0.03, 0.03),
              "phone": (0.02, 0.02, 0.025), "pole": (0.35, 0.35, 0.36), "flag1": p["flag"][0], "flag2": p["flag"][1],
              "sign": (0.03, 0.03, 0.035), "inflatable": p["flag"][0], "cutout": (0.15, 0.55, 0.12),
              "glow_screen": (0.55, 0.7, 1.0), "glow_flash": p.get("flash_col", (1.0, 1.0, 0.95)), "glow_stick": p["glow"], "glow_led": p["led"]})
    return c


def _pack_cells(sizes):
    """Shelf-pack square cells (sizes in units, any order) into an N x N unit grid; returns (N, [(ox, oy)])."""
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


def assemble(people, canons, cols):
    """Build (body arrays, glow arrays) for all people. Arrays: verts, loop_start, loop_vert, uv layers, colours,
    and per-vertex VAT data for previews."""
    by_tier = {c.tier: c for c in canons}
    sizes, owner = [], []
    for i, p in enumerate(people):
        u = CELL_UNITS[p["tier"]]
        sizes.append(u)
        owner.append((i, 0))
        if p["holder"]:
            sizes.append(u)
            owner.append((i, 1))
    n_units, pos = _pack_cells(sizes)
    cell_of = {}
    for (i, k), (ox, oy), s in zip(owner, pos, sizes):
        cell_of[(i, k)] = (ox, oy, s)
    pad = 0.04
    out = {"body": {k: [] for k in ("co", "lstart", "lvert", "uv0", "uv1", "uv2", "uv3", "uv4", "col", "vdata")},
           "glow": {k: [] for k in ("co", "lstart", "lvert", "uv0", "uv1", "uv2", "uv3", "uv4", "col", "vdata")}}
    counts = {"body": [0, 0], "glow": [0, 0]}                         # running vertex / loop totals
    ranges = {"body": [], "glow": []}                                 # (person, first vertex, canonical vertex ids)
    flip = (lambda v: 1.0 - v) if UE_FLIPS_V else (lambda v: v)
    for i, p in enumerate(people):
        c = by_tier[p["tier"]]
        part_ok = np.zeros(len(PARTS), dtype=bool)
        part_ok[[PART[q] for q in p["parts"] if q in PART]] = True
        fmask = part_ok[c.F_part]
        cols_rgb = look_colors(p)
        reg_col = np.array([cols_rgb[r] for r in REGIONS], dtype=np.float32)
        cos_, sin_ = math.cos(p["yaw"]), math.sin(p["yaw"])
        m = p["mirror"]
        rot = np.array([[cos_, -sin_, 0], [sin_, cos_, 0], [0, 0, 1]]) @ np.diag([p["sx"] * m, p["sx"], p["sz"]])
        clip_i = CLIPS.index(p["clip"])
        for kind, gmask in (("body", ~c.F_glow), ("glow", c.F_glow)):
            fm = fmask & gmask
            if not fm.any():
                continue
            loops = np.nonzero(fm[c.L_face])[0]
            if m < 0:
                loops = c.L_rev[loops]
            lv = c.L_vert[loops]
            uniq, inv = np.unique(lv, return_inverse=True)
            nv0, nl0 = counts[kind]
            o = out[kind]
            o["co"].append(c.V[uniq] @ rot.T + np.array([p["x"], p["y"], GROUND_Z]))
            faces = np.nonzero(fm)[0]
            o["lstart"].append(nl0 + np.concatenate([[0], np.cumsum(c.F_len[faces])[:-1]]))
            o["lvert"].append(nv0 + inv)
            uvc = c.L_uv[loops]
            if kind == "body":
                cells = c.L_cell[loops]
                ox = np.empty(len(loops))
                oy = np.empty(len(loops))
                sz = np.empty(len(loops))
                for k in (0, 1):
                    sel = cells == k
                    if sel.any():
                        cx, cy, s = cell_of[(i, k)]
                        ox[sel], oy[sel], sz[sel] = cx, cy, s
                o["uv0"].append(np.stack([(ox + sz * pad + uvc[:, 0] * sz * (1 - 2 * pad)) / n_units,
                                          (oy + sz * pad + uvc[:, 1] * sz * (1 - 2 * pad)) / n_units], 1))
            else:
                o["uv0"].append(np.zeros((len(loops), 2)))
            nl = len(loops)
            o["uv1"].append(np.stack([lv + cols[p["tier"]], np.full(nl, flip(clip_i))], 1))
            o["uv2"].append(np.tile([p["sx"] * cos_, flip(p["sx"] * sin_)], (nl, 1)))
            o["uv3"].append(np.tile([m * p["sz"], flip(p["phase"])], (nl, 1)))
            o["uv4"].append(np.tile([p["rate"], flip(0.0)], (nl, 1)))
            col = reg_col[c.F_reg[c.L_face[loops]]]
            o["col"].append(np.concatenate([col, np.ones((nl, 1), dtype=np.float32)], 1))
            o["vdata"].append(np.column_stack([uniq + cols[p["tier"]], np.full(len(uniq), clip_i),
                                               np.full(len(uniq), p["sx"] * cos_), np.full(len(uniq), p["sx"] * sin_),
                                               np.full(len(uniq), m * p["sz"]), np.full(len(uniq), p["phase"]),
                                               np.full(len(uniq), p["rate"])]))
            counts[kind] = [nv0 + len(uniq), nl0 + nl]
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
    for lname, key in (("UVMap", "uv0"),) + tuple(zip(DATA_UVS, ("uv1", "uv2", "uv3", "uv4"))):
        lay = me.uv_layers.new(name=lname)
        lay.data.foreach_set("uv", a[key].astype(np.float32).ravel())
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    ca.data.foreach_set("color", a["col"].astype(np.float32).ravel())
    me.color_attributes.active_color = ca
    me.uv_layers.active = me.uv_layers["UVMap"]                      # bakes target the active UV map: the lighting cells
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
_POSE = {}                                                            # object name -> (rest co, per-vertex VAT data)
_VAT = {}
_LAST = {}                                                            # the last build (people, canons, ...) for checks


def build_crowd2(rng, exclude=(), extra=(), out_dir=None, target=4300, half_fn=None, tiers=TIERS, vat_name="T_DinoCrowdVAT"):
    """The packed, dancing crowd. Returns (SM_DinoCrowd, SM_DinoPhones, extras): bodies (UV0 lighting cells, Col albedo,
    VAT UV channels), the glowing bits (phones, glowsticks, LED frames: Col = emissive colour, same VAT), no extras.
    Writes <out_dir>/<vat_name>.exr (+ .json) - the VAT both objects play."""
    t0 = time.time()
    if half_fn is None:
        try:
            import kit
            half_fn = kit.crowd_half
        except ImportError:
            half_fn = crowd_half_v2
    out_dir = out_dir or os.environ.get("DINO_OUT") or os.path.join(os.path.dirname(HERE), "out")
    os.makedirs(out_dir, exist_ok=True)
    canons = [Canon(t) for t in ("near", "mid", "far")]
    tex, cols = bake_vat(canons)
    pts, density = layout(rng, list(exclude), half_fn, target)

    def tier_of(x, y):
        d = math.hypot(x, y)
        return next(name for name, r in tiers if d < r)
    people = []
    for x, y in pts:
        half = half_fn(y)
        side = max(0.0, abs(x) / half - 0.45) * 0.10                  # more totems toward the sides
        people.append(make_person(rng, x, y, tier_of(x, y), holder_bias=side + (0.01 if y < -30 else 0.0)))
    for ex, ey, eyaw, epose in extra:
        clip = rng.choice(POSE_CLIPS.get(epose, ("bounce",)))
        people.append(make_person(rng, ex, ey, tier_of(ex, ey), clip=clip, yaw=eyaw))
    arrays, n_units = assemble(people, canons, cols)
    _LAST.update(people=people, canons=canons, cols=cols, arrays=arrays)
    crowd = mesh_from_arrays("SM_DinoCrowd", arrays["body"])
    phones = mesh_from_arrays("SM_DinoPhones", arrays["glow"])
    _POSE[crowd.name] = [None, arrays["body"]["vdata"]]                 # rest is captured on the first pose_preview()
    _POSE[phones.name] = [None, arrays["glow"]["vdata"]]
    _VAT["tex"] = tex
    exr = os.path.join(out_dir, vat_name + ".exr")
    write_exr(exr, tex, half=True)
    _VAT["tex_half"] = tex.astype(np.float16).astype(np.float32)
    stats = {}
    for p in people:
        s = stats.setdefault(p["tier"], {"people": 0, "holders": 0, "phones": 0, "glowsticks": 0})
        s["people"] += 1
        s["holders"] += p["holder"]
        s["phones"] += "phone" in p["parts"]
        s["glowsticks"] += "glowstick" in p["parts"]
    tris = {k: int((np.diff(np.append(a["lstart"], len(a["lvert"]))) - 2).sum()) for k, a in arrays.items()}
    meta = {"what": "Crowd V2 VAT: per-vertex offsets (m, Blender space) from the canonical rest pose; columns = tier "
                    "superset vertices, rows = clip * rows_per_clip + frame (row 0 = top)",
            "texture": vat_name + ".exr", "width": tex.shape[1], "height": tex.shape[0], "fps": FPS,
            "frames_per_clip": FRAMES, "rows_per_clip": ROWS, "clips": list(CLIPS), "authored_bpm": AUTHORED_BPM,
            "beats_per_clip": BEATS_PER_CLIP, "loop_rate_for_bpm": "LoopRate = BPM / 120", "tier_columns": cols,
            "tier_vertices": {c.tier: len(c.V) for c in canons}, "tier_superset_tris": {c.tier: c.tris for c in canons},
            "axis_scale": list(UE_AXIS), "ue_flips_v": UE_FLIPS_V, "uv_channels": VAT_LAYOUT,
            "people": len(people), "field_people": len(pts), "extra_people": len(extra), "density_scale": density,
            "tiers": stats, "tris": tris, "atlas_units": n_units,
            "max_offset_m": float(np.abs(tex[..., :3]).max())}
    json.dump(meta, open(os.path.join(out_dir, vat_name + ".json"), "w"), indent=1)
    _VAT["meta"] = meta
    log(f"crowd v2: {len(people)} people ({len(pts)} field + {len(extra)} extra), tiers {stats}, tris {tris}, "
        f"VAT {tex.shape[1]}x{tex.shape[0]}, atlas {n_units} units, {time.time() - t0:.1f} s")
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


def pose_preview(objects, t, loop_rate=128.0 / 120.0):
    """Move the crowd objects' vertices to their animated positions at time t (s), e.g. for preview renders AFTER the
    bake and the FBX export. The first call remembers the current (rest) positions - so transforms applied after
    build_crowd2() (the stage drop) are kept; pose_preview(objects, None) restores them. loop_rate = BPM / 120."""
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
