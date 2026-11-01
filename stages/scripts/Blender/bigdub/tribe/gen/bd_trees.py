"""bd_trees.py: BIG DUB's tall trees (instanced, three LODs) and the lights on the lit ones (plain Python + numpy).

Four meshes, each drawn by one hierarchical instanced component (bd_site.py places the instances):
  SM_BdTreeHardwood         a tall straight-trunked hardwood (the tongue's tulip poplars and oaks): 30 m at scale 1,
                            its trunk flared at the foot over five roots, limbs, a crown of lumpy lobes
  SM_BdTreeHemlock          a tall conifer (hemlock / white pine): 27 m at scale 1, tiers of drooping, ragged boughs
  SM_BdTreeLightsHardwood   the lights a lit hardwood carries, placed with it: a bulb string wound up the trunk, strings
                            draped in the crown, paper lanterns (warm, or the lantern "planets" in pink, orange and cyan)
  SM_BdTreeLightsHemlock    the same for a lit conifer
The bodies have one material slot, "Surface" (M_BdSurface: albedo x the light map and the moon; UV1 = (height over the
foot in metres, KIND_BARK or KIND_LEAF); vertex alpha = how shaded a crown's inside is). The lights have one, "Glow"
(M_BdGlow: each light a soft halo turned to the eye in the vertex shader; vertex colour R = palette offset, G = warmth,
B = how far the show's colour steps move it, A = twinkle phase; UV2.x = its size, UV3 = (GLOW_HALO, brightness)).
A body costs one draw per LOD, its lights another: the lit and the dark trees share the body.

LODs (the screen sizes are set on import, build_bigdub.py): LOD0 near (about 40 m), LOD1 to about 130 m, LOD2 beyond (a
few big glows keep a lit tree visible from the stages; a far hardwood's crown is two big lobes, 48 triangles, since
thousands are in view from any heading). No per-tree dynamic lights anywhere.
"""
import math

import numpy as np

import bd_mesh as M

SURF, GLOW = "Surface", "Glow"

# albedos (linear): the light map, the moon and the stages light them in the material
BARK = np.array([0.150, 0.128, 0.104])
LEAF = np.array([0.046, 0.080, 0.034])
LEAF_TOP = np.array([0.070, 0.110, 0.050])
NEEDLE = np.array([0.030, 0.060, 0.036])
NEEDLE_TIP = np.array([0.052, 0.090, 0.056])


def _surf(m, V, F, UV, rgb, kind, occlusion=0.0):
    """Adds a body part: albedo rgb ((3,) or (n, 3)), UV1 = (its height in metres, kind), alpha = occlusion."""
    n = len(V)
    rgb = np.broadcast_to(np.asarray(rgb, np.float64), (n, 3))
    occ = np.broadcast_to(np.asarray(occlusion, np.float64), (n,))
    col = np.concatenate([M.encode(rgb)[:, :3], occ[:, None]], 1).astype(np.float32)
    h = np.stack([np.maximum(V[:, 2], 0.0) / 100.0, np.full(n, float(kind))], 1)
    m.add(V, F, col, UV, SURF, (h,))


def _trunk(m, rb, rt, top, sides, lod, flare=1.35, kind=M.KIND_BARK):
    """A tapered trunk, flared at its foot (LOD 0 and 1), UV in metres (u round, v up)."""
    zs = ([-40.0, 60.0, 400.0, 1200.0, top], [-40.0, 120.0, top], [-40.0, top])[lod]
    for z0, z1 in zip(zs[:-1], zs[1:]):
        def r_at(z):
            r = rb + (rt - rb) * max(z, 0.0) / top
            return r * (flare if z <= 0.0 and lod < 2 else 1.0)
        V, F, UV = M.cylinder(r_at(z0), r_at(z1), z0, z1, sides, cap_top=False)
        UV[:, 1] += z0 / 100.0
        _surf(m, V, F, UV, BARK, kind)


def _roots(m, rng, rb, n, kind=M.KIND_BARK):
    """Root flares: low wedges running out from the trunk's foot into the ground."""
    for k in range(n):
        a = 2 * math.pi * k / n + rng.uniform(-0.35, 0.35)
        L = rng.uniform(85.0, 150.0)
        w = rng.uniform(14.0, 22.0)
        h = rng.uniform(18.0, 28.0)
        d = np.array([math.cos(a), math.sin(a)])
        s = np.array([-d[1], d[0]])
        b0 = d * rb * 0.85
        tip = d * (rb + L)
        V = np.array([[*(b0 + s * w), -12.0], [*(b0 - s * w), -12.0], [*b0, h], [*tip, -14.0]], np.float64)
        # its two sides, wound outward (its back is inside the trunk, its bottom under the ground)
        F = np.array([(0, 2, 3), (1, 3, 2)])
        UV = np.array([[0, 0], [w / 50, 0], [w / 100, h / 100], [0, L / 100]], np.float32)
        _surf(m, V, F, UV, BARK * 0.9, kind, 0.3)


def _lobe(m, rng, rx, rz, c, sub, lumpy, top_rgb, low_rgb, occ_low):
    V, F, UV = M.blob(rx, rx * rng.uniform(0.8, 1.15), rz, c, sub, rng, lumpy)
    t = np.clip((V[:, 2] - (c[2] - rz)) / (2 * rz), 0, 1)
    rgb = low_rgb[None, :] * (1 - t[:, None]) + top_rgb[None, :] * t[:, None]
    _surf(m, V, F, UV, rgb, M.KIND_LEAF, occ_low * (1.0 - t))


def hardwood(rng, lod):
    """A tall hardwood: trunk 30 m, crown from ~15 m."""
    m = M.Mesh("tree", (SURF,))
    H = 3000.0
    rb, rt = 33.0, 12.0
    sides = (8, 6, 4)[lod]
    _trunk(m, rb, rt, H * 0.80, sides, lod, 1.2)
    if lod == 0:
        _roots(m, rng, rb, 5)
    if lod < 2:
        for k in range(6 if lod == 0 else 3):
            ang = 2 * math.pi * k / (6 if lod == 0 else 3) + rng.uniform(-0.4, 0.4)
            z = H * rng.uniform(0.48, 0.72)
            L = rng.uniform(450, 780)
            a = (math.cos(ang) * 8, math.sin(ang) * 8, z)
            b = (math.cos(ang) * L, math.sin(ang) * L, z + L * rng.uniform(0.45, 0.8))
            V, F, UV = M.box_between(a, b, 15.0 if lod == 0 else 19.0)
            _surf(m, V, F, UV, BARK, M.KIND_BARK)
    if lod == 2:
        # far: two big lobes either side of the trunk, the crown's mass and outline in 40 triangles
        for k in range(2):
            ang = math.pi * k + rng.uniform(-0.4, 0.4)
            rad = rng.uniform(220, 320)
            c = (math.cos(ang) * rad, math.sin(ang) * rad, H * rng.uniform(0.78, 0.86))
            _lobe(m, rng, rng.uniform(620, 720), rng.uniform(480, 580), c, 0, 0.1, LEAF_TOP, LEAF, 0.4)
        return m
    # near: a big lobe on top, a ring of lobes round the upper trunk, smaller ones breaking the outline
    big = (7, 6)[lod]
    for k in range(big):
        ang = 2 * math.pi * k / big + rng.uniform(-0.3, 0.3)
        rad = rng.uniform(260, 520) if k else 0.0
        cz = H * rng.uniform(0.64, 0.86) if k else H * 0.88
        c = (math.cos(ang) * rad, math.sin(ang) * rad, cz)
        _lobe(m, rng, rng.uniform(360, 540), rng.uniform(260, 400), c, (1, 0)[lod], 0.24, LEAF_TOP, LEAF, 0.55)
    if lod == 0:
        for k in range(7):
            ang = rng.uniform(0, 2 * math.pi)
            rad = rng.uniform(520, 760)
            c = (math.cos(ang) * rad, math.sin(ang) * rad, H * rng.uniform(0.66, 0.92))
            _lobe(m, rng, rng.uniform(170, 260), rng.uniform(140, 210), c, 0, 0.3, LEAF_TOP, LEAF, 0.35)
    return m


def _bough_tier(m, rng, z0, r, h, sides, droop, ragged):
    """A conifer's tier of boughs: a cone whose rim droops below its attachment and alternates long and short tips
    (a ragged edge), with a dark underside."""
    tip = (0.0, 0.0, z0 + h)
    rim = []
    for k in range(sides):
        a = 2 * math.pi * k / sides + rng.uniform(-0.12, 0.12)
        rr = r * (1.0 if k % 2 == 0 else 1.0 - ragged) * rng.uniform(0.88, 1.08)
        rim.append((math.cos(a) * rr, math.sin(a) * rr, z0 - droop * (rr / r)))
    V = np.array([tip] + rim, np.float64)
    # (tip, rim k, rim k + 1) faces outward and up, as M.cone winds its sides
    F = np.array([(0, 1 + k, 1 + (k + 1) % sides) for k in range(sides)])
    rgb = np.where((np.arange(len(V)) == 0)[:, None], NEEDLE_TIP[None, :], NEEDLE[None, :])
    _surf(m, V, F, np.zeros((len(V), 2), np.float32), rgb, M.KIND_LEAF, np.where(np.arange(len(V)) == 0, 0.0, 0.25))
    # the underside, close under the rim, dark, facing down
    under = np.array([(0.0, 0.0, z0 + h * 0.15)] + rim, np.float64)
    Fu = np.array([(0, 1 + (k + 1) % sides, 1 + k) for k in range(sides)])
    _surf(m, under, Fu, np.zeros((len(under), 2), np.float32), NEEDLE * 0.6, M.KIND_LEAF, 0.7)


def hemlock(rng, lod):
    """A tall conifer: trunk 27 m, tiers of drooping boughs from ~5 m."""
    m = M.Mesh("tree", (SURF,))
    H = 2700.0
    rb, rt = 31.0, 6.0
    _trunk(m, rb, rt, H * 0.93, (7, 6, 4)[lod], lod, 1.15, M.KIND_BARK2)
    if lod == 0:
        _roots(m, rng, rb, 4, M.KIND_BARK2)
    tiers = (10, 5, 2)[lod]
    sides = (14, 10, 6)[lod]
    z_bottom, z_top = H * 0.20, H
    for k in range(tiers):
        t = k / max(tiers - 1, 1)
        z0 = z_bottom + (z_top - z_bottom) * t * 0.84
        r = (1 - t * 0.80) * rng.uniform(430, 520) * (1.15 if lod == 2 else 1.0)
        h = (z_top - z_bottom) / tiers * (1.7 if lod < 2 else 1.5) + (H - z0) * (0.0 if k < tiers - 1 else 0.3)
        _bough_tier(m, rng, z0, r, min(h, H - z0 + 60.0), sides, (0.32 if lod < 2 else 0.2) * r, (0.30, 0.22, 0.0)[lod])
    return m


# ---- the lights ----------------------------------------------------------------------------------------------------

LANTERN_COLOURS = [(1.0, 0.30, 0.55), (1.0, 0.50, 0.12), (0.15, 0.85, 1.0), (1.0, 0.85, 0.40)]


def halos(m, P, size, cols, bright=1.0):
    """Soft halos at points P (n, 3): each a quad whose four corners sit 0.5 cm apart round its centre (the vertex shader
    turns it to the eye, UV2.x = its half size); cols (n, 4) or (4,) for M_BdGlow."""
    P = np.asarray(P, np.float64).reshape(-1, 3)
    n = len(P)
    if n == 0:
        return
    corners = np.array([(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)])
    V = (P[:, None, :] + np.concatenate([corners * 0.5, np.zeros((4, 1))], 1)[None, :, :]).reshape(-1, 3)
    F = (np.array([(0, 1, 2), (0, 2, 3)])[None, :, :] + (np.arange(n) * 4)[:, None, None]).reshape(-1, 3)
    UV = np.tile(corners, (n, 1)).astype(np.float32)
    C = np.asarray(cols, np.float32)
    C = np.repeat(C.reshape(n, 4), 4, 0) if C.ndim == 2 else np.broadcast_to(C, (4 * n, 4))
    sz = np.repeat(np.broadcast_to(np.asarray(size, np.float64), (n,)), 4)
    br = np.repeat(np.broadcast_to(np.asarray(bright, np.float64), (n,)), 4)
    x = M.aux(4 * n, None, np.stack([sz, np.zeros(4 * n)], 1), np.stack([np.full(4 * n, M.GLOW_HALO), br], 1))
    m.add(V, F, C, UV, GLOW, x)


def _light_col(offset, warmth, step, phase):
    return np.array([offset % 1.0, warmth, step, phase % 1.0], np.float32)


def _trunk_spiral(rng, height_cm, r_base, r_top, n_turns, n_bulbs, z0, z1):
    t = np.linspace(0, 1, n_bulbs)
    z = z0 + (z1 - z0) * t
    r = r_base + (r_top - r_base) * (z / height_cm) + 5.0
    a = 2 * math.pi * n_turns * t + rng.uniform(0, 2 * math.pi)
    return np.stack([r * np.cos(a), r * np.sin(a), z], axis=1)


def tree_lights(rng, lod, H, rb, rt, crown_z, crown_r):
    """The lights a lit tree carries, LOD by LOD (fewer, bigger lights further away)."""
    m = M.Mesh("lights", (GLOW,))
    off = rng.uniform(0, 1)
    if lod == 0:
        P = _trunk_spiral(rng, H, rb, rt, 6.0, 44, 110.0, 950.0)
        halos(m, P, 9.0, np.array([_light_col(off + 0.25 * (i % 4), 0.0, 1.0, i * 0.137) for i in range(len(P))]), 0.9)
        for s in range(3):
            a0 = rng.uniform(0, 2 * math.pi)
            a1 = a0 + rng.uniform(1.0, 2.2)
            z = crown_z + rng.uniform(-150, 250)
            pa = (math.cos(a0) * crown_r * 0.75, math.sin(a0) * crown_r * 0.75, z)
            pb = (math.cos(a1) * crown_r * 0.75, math.sin(a1) * crown_r * 0.75, z + rng.uniform(-100, 100))
            P = M.catenary(pa, pb, rng.uniform(80, 180), 18)
            halos(m, P, 11.0, np.array([_light_col(off + 0.5 + 0.125 * s, 0.0, 1.0, i * 0.21 + s * 0.3) for i in range(len(P))]), 0.9)
        for k in range(4):
            a = rng.uniform(0, 2 * math.pi)
            r = rng.uniform(180, 380)
            z = crown_z - rng.uniform(250, 600)
            warm = k % 2 == 0
            halos(m, [(math.cos(a) * r, math.sin(a) * r, z)], 34.0,
                  _light_col(rng.uniform(0, 1), 1.0 if warm else 0.0, 0.0, rng.uniform(0, 1)), 1.0)
    elif lod == 1:
        P = _trunk_spiral(rng, H, rb, rt, 3.0, 14, 110.0, 950.0)
        halos(m, P, 20.0, np.array([_light_col(off + 0.25 * (i % 4), 0.0, 1.0, i * 0.137) for i in range(len(P))]), 0.85)
        for s in range(2):
            a0 = rng.uniform(0, 2 * math.pi)
            a1 = a0 + 1.6
            z = crown_z + 50
            P = M.catenary((math.cos(a0) * crown_r * 0.75, math.sin(a0) * crown_r * 0.75, z),
                           (math.cos(a1) * crown_r * 0.75, math.sin(a1) * crown_r * 0.75, z), 140, 6)
            halos(m, P, 24.0, np.array([_light_col(off + 0.5, 0.0, 1.0, i * 0.21) for i in range(len(P))]), 0.85)
        for k in range(2):
            a = rng.uniform(0, 2 * math.pi)
            halos(m, [(math.cos(a) * 260, math.sin(a) * 260, crown_z - 400)], 60.0,
                  _light_col(rng.uniform(0, 1), 1.0 if k == 0 else 0.0, 0.0, rng.uniform(0, 1)), 1.0)
    else:
        P = np.array([(rb + 10, 0, 220), (-rb - 10, 0, 600), (crown_r * 0.6, 0, crown_z),
                      (-crown_r * 0.4, crown_r * 0.5, crown_z + 200), (0, -crown_r * 0.6, crown_z - 100)], np.float64)
        halos(m, P, 75.0, np.array([_light_col(off + 0.25 * i, 0.0 if i < 4 else 1.0, 1.0, i * 0.3) for i in range(len(P))]), 0.8)
    return m


def build_tree_meshes(seed=7):
    """{asset name: [LOD0, LOD1, LOD2]} for the four tree assets."""
    out = {}
    for name, fn in (("SM_BdTreeHardwood", hardwood), ("SM_BdTreeHemlock", hemlock)):
        lods = []
        for lod in range(3):
            rng = np.random.default_rng(seed + lod * 101 + (5 if fn is hemlock else 0))
            mesh = fn(rng, lod)
            mesh.name = name
            lods.append(mesh)
        out[name] = lods
    for name, H, rb, rt, cz, cr in (("SM_BdTreeLightsHardwood", 3000.0, 33.0, 12.0, 3000.0 * 0.62, 520.0),
                                    ("SM_BdTreeLightsHemlock", 2700.0, 31.0, 6.0, 2700.0 * 0.30, 430.0)):
        lods = []
        for lod in range(3):
            rng = np.random.default_rng(seed + 17 + lod * 101 + (5 if "Hemlock" in name else 0))
            mesh = tree_lights(rng, lod, H, rb, rt, cz, cr)
            mesh.name = name
            lods.append(mesh)
        out[name] = lods
    return out


# Heights at scale 1 (cm): bd_site.py scales instances to 22-34 m.
BASE_HEIGHT = {"SM_BdTreeHardwood": 3000.0, "SM_BdTreeHemlock": 2700.0}
# LOD screen sizes (UE's bounds screen size): LOD1 from 0.32, LOD2 from 0.11
LOD_SCREEN_SIZES = (1.0, 0.32, 0.11)
LIGHTS_OF = {"SM_BdTreeHardwood": "SM_BdTreeLightsHardwood", "SM_BdTreeHemlock": "SM_BdTreeLightsHemlock"}
