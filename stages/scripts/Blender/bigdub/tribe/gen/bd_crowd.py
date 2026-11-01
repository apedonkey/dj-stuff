"""bd_crowd.py: BIG DUB's crowds (plain Python + numpy): low dancers, instanced, three LODs, two poses.

  SM_BdCrowdUp    a dancer with both hands up (fists over the head, elbows out)
  SM_BdCrowdDown  a dancer with the arms down and a little bent
1.75 m at scale 1, facing +X (bd_site.py turns each to its stage). One material slot, "Crowd" (M_BdCrowd: M_BdSurface's
light, so the stages' colours and sweeps play over them, with a World Position Offset that bobs every dancer on the
beat and pumps the raised fists; vertical only, so it needs no instance rotation). Per vertex:
  colour   albedo (clothes, skin, hair); alpha the shade under the arms and between the legs
  UV1      (height over the feet in metres, KIND_CLOTH)
  UV2.x    how much of the fists' pump a vertex takes (the forearms and fists of SM_BdCrowdUp)
  UV2.y    1 on clothes (M_BdCrowd colours each dancer's clothes by its PerInstanceRandom), 0 on skin and hair
  UV3.x    how much of the bob (0 at the feet, 1 from the hips up; the head 1.15)
No walls: the walk passes through them, as through the other venues' crowds (docs/venues.md, "Dancers don't block").
"""
import math

import numpy as np

import bd_mesh as M

SLOT = "Crowd"
SKIN = [(0.40, 0.27, 0.20), (0.30, 0.19, 0.13), (0.18, 0.11, 0.07), (0.46, 0.33, 0.26)]
CLOTHES = [(0.05, 0.05, 0.06), (0.30, 0.30, 0.32), (0.08, 0.12, 0.25), (0.35, 0.10, 0.12), (0.08, 0.20, 0.10),
           (0.40, 0.32, 0.12), (0.22, 0.10, 0.28), (0.55, 0.55, 0.52)]


def _add(m, V, F, rgb, occ, pump, bob, cloth=0.0):
    n = len(V)
    rgb = np.broadcast_to(np.asarray(rgb, np.float64), (n, 3))
    col = np.concatenate([M.encode(rgb)[:, :3], np.broadcast_to(np.asarray(occ, np.float64), (n,))[:, None]], 1).astype(np.float32)
    h = np.stack([np.maximum(V[:, 2], 0.0) / 100.0, np.full(n, float(M.KIND_CLOTH))], 1)
    pump_ = np.broadcast_to(np.asarray(pump, np.float64), (n,))
    bob_ = np.broadcast_to(np.asarray(bob, np.float64), (n,))
    x = M.aux(n, h, np.stack([pump_, np.full(n, float(cloth))], 1), np.stack([bob_, np.zeros(n)], 1))
    m.add(V, F, col, np.zeros((n, 2), np.float32), SLOT, x)


def _limb(m, a, b, r0, r1, sides, rgb, occ, pump_a, pump_b, bob_a, bob_b, cloth=0.0):
    """A tapered limb from a to b (cm), its pump and bob weights blended along it."""
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    d = b - a
    L = float(np.linalg.norm(d))
    z = d / L
    up = np.array([0.0, 0.0, 1.0]) if abs(z[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    x = np.cross(up, z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    V, F, _ = M.cylinder(r0, r1, 0.0, L, sides, cap_top=False, cap_bottom=False)
    t = np.clip(V[:, 2] / L, 0, 1)
    W = a + V[:, 0:1] * x + V[:, 1:2] * y + V[:, 2:3] * z
    _add(m, W, F, rgb, occ, pump_a + (pump_b - pump_a) * t, bob_a + (bob_b - bob_a) * t, cloth)


def dancer(rng, lod, arms_up):
    """One dancer at LOD lod (0 about 140 triangles, 1 about 46, 2 a dozen)."""
    m = M.Mesh("crowd", (SLOT,))
    skin = np.array(SKIN[rng.integers(len(SKIN))])
    top = np.array(CLOTHES[rng.integers(len(CLOTHES))])
    legs = np.array(CLOTHES[rng.integers(3)])
    hair = np.array((0.04, 0.03, 0.025))
    if lod == 2:
        # far: a body and a head
        _limb(m, (0, 0, 0), (0, 0, 150), 20, 15, 3, top * 0.8, 0.2, 0, 0, 0, 1, 1.0)
        V, F, _ = M.octahedron(13.0, (0, 0, 162))
        _add(m, V, F, skin, 0.0, 0, 1.15)
        if arms_up:
            for s in (-1, 1):
                _limb(m, (0, s * 18, 138), (6, s * 30, 200), 5, 4, 3, skin, 0.0, 0.0, 1.0, 1, 1)
        return m
    sides = (5, 3)[lod]
    # legs (a stance a little apart), hips, torso, shoulders, neck, head
    for s in (-1, 1):
        _limb(m, (0, s * 11, 0), (0, s * 10, 88), 7.5, 9.0, sides, legs, 0.3, 0, 0, 0.0, 1.0, 0.5)
    _limb(m, (0, 0, 86), (0, 0, 104), 16, 15, sides, legs, 0.15, 0, 0, 1, 1, 0.5)
    _limb(m, (0, 0, 102), (0, 0, 146), 15, 19, sides + (2 if lod == 0 else 0), top, 0.0, 0, 0, 1, 1, 1.0)
    if lod == 0:
        V, F, _ = M.box(22, 40, 8, (0, 0, 146))
        _add(m, V, F, top, 0.0, 0, 1.0, 1.0)
        _limb(m, (0, 0, 148), (0, 0, 156), 5, 5, 4, skin, 0.0, 0, 0, 1, 1.1)
        V, F, _ = M.blob(10.5, 9.5, 12.0, (1.0, 0.0, 167.0), 0, rng, 0.06)
        rgb = np.where((V[:, 2] > 169.0)[:, None] | (V[:, 0] < -4.0)[:, None], hair[None, :], skin[None, :])
        _add(m, V, F, rgb, 0.0, 0, 1.15)
    else:
        V, F, _ = M.octahedron(11.5, (0, 0, 166))
        _add(m, V, F, skin, 0.0, 0, 1.15)
    # arms: up, fists over the head and elbows out; or down, a little bent and out from the body
    for s in (-1, 1):
        sh = (0.0, s * 19.0, 142.0)
        if arms_up:
            el = (8.0, s * 30.0, 168.0)
            fist = (12.0, s * 17.0, 198.0 + rng.uniform(-6, 6))
            _limb(m, sh, el, 4.2, 3.6, sides, top if lod == 0 else skin, 0.0, 0.0, 0.5, 1, 1, 1.0 if lod == 0 else 0.0)
            _limb(m, el, fist, 3.3, 2.8, sides, skin, 0.0, 0.5, 1.0, 1, 1)
        else:
            el = (2.0, s * 25.0, 113.0)
            hand = (14.0, s * 22.0, 88.0)
            _limb(m, sh, el, 4.2, 3.6, sides, top, 0.15, 0, 0, 1, 1, 1.0)
            _limb(m, el, hand, 3.3, 2.8, sides, skin, 0.15, 0, 0, 1, 1)
    return m


def build_crowd_meshes(seed=11):
    out = {}
    for name, up in (("SM_BdCrowdUp", True), ("SM_BdCrowdDown", False)):
        lods = []
        for lod in range(3):
            mesh = dancer(np.random.default_rng(seed + (3 if up else 0)), lod, up)
            mesh.name = name
            lods.append(mesh)
        out[name] = lods
    return out


# LOD screen sizes (a dancer's bounds are about 1 m round): LOD1 from about 16 m, LOD2 from about 40 m
LOD_SCREEN_SIZES = (1.0, 0.05, 0.02)
CULL_CM = 25000.0
