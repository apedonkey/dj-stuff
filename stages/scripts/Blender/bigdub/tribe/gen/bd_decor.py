"""bd_decor.py: BIG DUB's festival dressing (plain Python + numpy), from the research on the real festival at night
(tribe hack/claudedocs: bigdub_research_stages.md, bigdub_research_grounds.md): glowing inflatable jellyfish and spiky
flowers hanging over the Main Stage's crowd and New Camp's, neon signs naming the three stages, campfires in the camps,
festival flags round the stages, giant glowing mushrooms in the Big Bottom (the festival's "Mushroomland"), paper lantern
"planets" in the trees along the paths, and wisteria hanging from the Pavilion's rafters. No logos, no lettering of
theirs: the signs say the menu's stage names in our own neon stroke letters.

Everything is world-frame geometry for the structures' mesh (Surface, Lights) and the glow mesh (bd_structures.py's
glow_halo / glow_ribbon), with walls where a walker would otherwise pass through something solid.
"""
import math

import numpy as np

import bd_mesh as M
import bd_structures as S

# the stages' sign colours: entries of the show's palette (bd_site.PALETTE), so their halos match (offset = index / 8)
SIGN = {"Main": ((1.00, 0.78, 0.18), 2), "Pavilion": ((1.00, 0.20, 0.65), 7), "NewCamp": ((0.10, 0.85, 0.80), 4)}


def tube(mesh, a, b, r, sides, col, mat, aux=None):
    """A round tube from a to b (world cm)."""
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    d = b - a
    L = float(np.linalg.norm(d))
    if L < 1e-3:
        return
    z = d / L
    up = np.array([0.0, 0.0, 1.0]) if abs(z[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    x = np.cross(up, z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    V, F, UV = M.cylinder(r, r, 0.0, L, sides, cap_top=False)
    W = a + V[:, 0:1] * x + V[:, 1:2] * y + V[:, 2:3] * z
    mesh.add(W, F, col, UV, mat, aux)


# ---- neon letters -----------------------------------------------------------------------------------------------------
# our own stroke letters on a 4 x 6 grid (x right, y up): only the letters the stage names need
FONT = {
    "A": [[(0, 0), (2, 6), (4, 0)], [(0.8, 2.4), (3.2, 2.4)]],
    "C": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5)]],
    "E": [[(4, 0), (0, 0), (0, 6), (4, 6)], [(0, 3), (3, 3)]],
    "G": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 3), (2.2, 3)]],
    "I": [[(1, 0), (3, 0)], [(2, 0), (2, 6)], [(1, 6), (3, 6)]],
    "L": [[(0, 6), (0, 0), (4, 0)]],
    "M": [[(0, 0), (0, 6), (2, 3), (4, 6), (4, 0)]],
    "N": [[(0, 0), (0, 6), (4, 0), (4, 6)]],
    "O": [[(1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0)]],
    "P": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)]],
    "S": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (1, 3), (3, 3), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "T": [[(0, 6), (4, 6)], [(2, 6), (2, 0)]],
    "V": [[(0, 6), (2, 0), (4, 6)]],
    "W": [[(0, 6), (1, 0), (2, 4), (3, 0), (4, 6)]],
    " ": [],
}


def neon_sign(part, glow, text, centre, yaw, height_cm, stage):
    """A neon sign: text in our stroke letters, height_cm tall, its middle at centre (world), facing yaw (its letters
    read from in front: the viewer looks along -facing). Tubes (M_BdLights neon, the stage's colour), a halo every 18 cm
    along them, a dark rail behind. Returns its width (cm)."""
    rgb, pal = SIGN[stage]
    unit = height_cm / 6.0
    adv = 5.4 * unit
    width = adv * len(text) - 1.4 * unit
    fwd, right = (np.array([v[0], v[1], 0.0]) for v in M.basis_from_yaw(yaw))
    # a viewer in front looks along -fwd, so the reading direction (their right) is the sign's -right
    left = -right
    o = np.asarray(centre, np.float64)
    m = part.mesh("SM_BdDecor")
    col = np.array([*(np.asarray(rgb) ** (1 / 2.2)), 0.0], np.float32)
    aux = S.light_aux(1.0, M.LIGHT_NEON)
    halo_pts = []
    for k, ch in enumerate(text):
        x0 = -width / 2 + k * adv
        for stroke in FONT[ch]:
            P = np.array([o + left * (x0 + sx * unit) + np.array([0.0, 0.0, (sy - 3.0) * unit]) for sx, sy in stroke])
            for a, b in zip(P[:-1], P[1:]):
                tube(m, a, b, max(2.0, unit * 0.09), 6, col, S.LIGHT, aux)
                n = max(1, int(np.linalg.norm(b - a) / 18.0))
                halo_pts += [a + (b - a) * (t + 0.5) / n for t in range(n)]
            for q in P:
                V, F, UV = M.octahedron(max(2.0, unit * 0.09) * 1.1, q)
                m.add(V, F, col, UV, S.LIGHT, aux)
    S.glow_halo(glow, halo_pts, max(9.0, unit * 0.5), S.glow_col(pal / 8.0, 0.0, 0.0, 0.0), 0.55)
    # the rail it hangs on: a dark bar behind its top and bottom
    for dz in (3.4 * unit, -3.4 * unit):
        a = o + left * (-width / 2 - unit) - fwd * 8.0 + np.array([0.0, 0.0, dz])
        b = o + left * (width / 2 + unit) - fwd * 8.0 + np.array([0.0, 0.0, dz])
        V, F, UV = M.box_between(a, b, 5.0)
        m.add(V, F, S.BLACK, UV, S.SURF)
    return width


# ---- inflatables ------------------------------------------------------------------------------------------------------

def jellyfish(part, glow, P, R, rgb, pal, rng):
    """A glowing inflatable jellyfish hanging at P (its bell's top, world): a lit bell R cm across, trailing tentacles and
    frilly arms (M_BdLights, lantern), a soft halo, a cord up into the dark."""
    m = part.mesh("SM_BdDecor")
    P = np.asarray(P, np.float64)
    sides, rings = 12, 5
    V, F = [], []
    for i in range(rings + 1):
        th = math.radians(8 + 82 * i / rings)
        for k in range(sides):
            ph = 2 * math.pi * k / sides
            rr = R * math.sin(th) * (1.0 + (0.06 * math.cos(ph * 6) if i == rings else 0.0))
            V.append((P[0] + rr * math.cos(ph), P[1] + rr * math.sin(ph), P[2] - R * 0.72 * (1 - math.cos(th))))
    for i in range(rings):
        for k in range(sides):
            a, b = i * sides + k, i * sides + (k + 1) % sides
            c, d = (i + 1) * sides + (k + 1) % sides, (i + 1) * sides + k
            F += [(a, c, b), (a, d, c)]
    V = np.array(V)
    top = len(V)
    V = np.vstack([V, [P + np.array([0, 0, 2.0])]])
    F += [(top, k, (k + 1) % sides) for k in range(sides)]
    F = np.array(F)
    F = np.concatenate([F, F[:, ::-1]])                 # seen from below too
    shade = np.clip(1.0 - (P[2] - V[:, 2]) / (R * 0.9), 0.55, 1.0)
    col = np.concatenate([np.asarray(rgb)[None, :] ** (1 / 2.2) * shade[:, None], np.full((len(V), 1), rng.uniform(0, 1))], 1)
    m.add(V, F, col.astype(np.float32), np.zeros((len(V), 2), np.float32), S.LIGHT, S.light_aux(0.75, M.LIGHT_LANTERN))
    rim_z = P[2] - R * 0.72 * (1 - math.cos(math.radians(90)))
    tcol = np.array([*(np.asarray(rgb) ** (1 / 2.2) * 0.8), rng.uniform(0, 1)], np.float32)
    for k in range(6):
        ph = 2 * math.pi * k / 6 + rng.uniform(-0.2, 0.2)
        a = np.array([P[0] + R * 0.8 * math.cos(ph), P[1] + R * 0.8 * math.sin(ph), rim_z])
        L = R * rng.uniform(1.6, 2.6)
        pts = [a + np.array([math.sin(t * 5 + k) * R * 0.12, math.cos(t * 4 + k) * R * 0.12, -L * t]) for t in np.linspace(0, 1, 6)]
        for q0, q1 in zip(pts[:-1], pts[1:]):
            tube(m, q0, q1, 2.2, 3, tcol, S.LIGHT, S.light_aux(0.6, M.LIGHT_LANTERN))
    for k in range(3):                                    # the frilly oral arms under the middle
        ph = 2 * math.pi * k / 3
        a = np.array([P[0] + R * 0.2 * math.cos(ph), P[1] + R * 0.2 * math.sin(ph), rim_z + R * 0.1])
        pts = [a + np.array([math.cos(ph) * R * 0.25 * t + math.sin(t * 9) * 6, math.sin(ph) * R * 0.25 * t, -R * 1.3 * t])
               for t in np.linspace(0, 1, 5)]
        for q0, q1 in zip(pts[:-1], pts[1:]):
            tube(m, q0, q1, 6.0, 4, tcol, S.LIGHT, S.light_aux(0.7, M.LIGHT_LANTERN))
    S.glow_halo(glow, [P - np.array([0, 0, R * 0.45])], R * 1.25, S.glow_col(pal / 8.0, 0.0, 0.0, rng.uniform(0, 1)), 0.30)
    V, F, UV = M.box_between(P, P + np.array([0, 0, 420.0]), 1.5)
    m.add(V, F, S.BLACK, UV, S.SURF)


def spiky_flower(part, glow, P, R, rng):
    """A white spiky flower inflatable (a ball of cones), glowing from inside, hanging at P."""
    m = part.mesh("SM_BdDecor")
    P = np.asarray(P, np.float64)
    col = np.array([1.0, 0.92, 0.97, rng.uniform(0, 1)], np.float32)
    aux = S.light_aux(0.62, M.LIGHT_LANTERN)
    V, F = M.icosphere(0)
    m.add(V * R * 0.55 + P, F, col, None, S.LIGHT, aux)
    for d in V:
        base = P + d * R * 0.45
        tip = P + d * R * 1.15
        e1 = np.cross(d, [0.0, 0.0, 1.0] if abs(d[2]) < 0.9 else [1.0, 0.0, 0.0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(d, e1)
        ring = [base + (e1 * math.cos(t) + e2 * math.sin(t)) * R * 0.2 for t in np.linspace(0, 2 * math.pi, 5)[:-1]]
        Vc = np.array(ring + [tip])
        Fc = np.array([(k, (k + 1) % 4, 4) for k in range(4)])
        m.add(Vc, Fc, col, None, S.LIGHT, aux)
    S.glow_halo(glow, [P], R * 1.6, S.glow_col(0.875, 0.0, 0.0, 0.0), 0.22)
    V, F, UV = M.box_between(P, P + np.array([0, 0, 420.0]), 1.5)
    m.add(V, F, S.BLACK, UV, S.SURF)


def mushroom(part, glow, X, Y, z, H, R, rng):
    """A giant inflatable mushroom: a pale stem, a red cap with white spots, glowing from inside; a wall round its stem."""
    m = part.mesh("SM_BdDecor")
    V, F, UV = M.cylinder(R * 0.30, R * 0.24, z - 10.0, z + H, 10, cap_top=False, center=(X, Y))
    up = np.clip((V[:, 2] - z) / H, 0, 1)
    stem_col = np.concatenate([np.array([0.95, 0.90, 0.82])[None, :] ** (1 / 2.2) * (0.45 + 0.55 * up)[:, None],
                               np.full((len(V), 1), rng.uniform(0, 1))], 1).astype(np.float32)
    m.add(V, F, stem_col, UV, S.LIGHT, S.light_aux(0.42, M.LIGHT_LANTERN))
    sides, rings = 14, 4
    Vc, Fc = [], []
    cz = z + H - R * 0.15
    for i in range(rings + 1):
        th = math.radians(90 * i / rings)
        for k in range(sides):
            ph = 2 * math.pi * k / sides
            Vc.append((X + R * math.sin(th) * math.cos(ph), Y + R * math.sin(th) * math.sin(ph), cz + R * 0.62 * math.cos(th)))
    for i in range(rings):
        for k in range(sides):
            a, b = i * sides + k, i * sides + (k + 1) % sides
            c, d = (i + 1) * sides + (k + 1) % sides, (i + 1) * sides + k
            Fc += [(a, b, c), (a, c, d)]
    Vc = np.array(Vc)
    crown = np.clip((Vc[:, 2] - cz) / (R * 0.62), 0, 1)
    cap = np.concatenate([np.array([1.0, 0.16, 0.10])[None, :] ** (1 / 2.2) * (0.55 + 0.45 * crown)[:, None],
                          np.full((len(Vc), 1), rng.uniform(0, 1))], 1).astype(np.float32)
    m.add(Vc, np.array(Fc)[:, ::-1], cap, None, S.LIGHT, S.light_aux(0.62, M.LIGHT_LANTERN))
    # the gills underneath: a dim pink disc
    rim = Vc[-sides:]
    Vg = np.vstack([rim, [(X, Y, cz - 4.0)]])
    Fg = np.array([(sides, (k + 1) % sides, k) for k in range(sides)])
    m.add(Vg, Fg, np.array([1.0, 0.55, 0.60, 0.0], np.float32), None, S.LIGHT, S.light_aux(0.22, M.LIGHT_LANTERN))
    for _ in range(9):                                   # white spots on the cap
        th = math.radians(rng.uniform(12, 70))
        ph = rng.uniform(0, 2 * math.pi)
        n = np.array([math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)])
        p = np.array([X, Y, cz]) + np.array([R * n[0], R * n[1], R * 0.62 * n[2]]) * 1.01
        V, F, _ = M.blob(R * 0.14, R * 0.14, R * 0.05, (0, 0, 0), 0, None, 0)
        e1 = np.cross(n, [0.0, 0.0, 1.0]) if abs(n[2]) < 0.95 else np.array([1.0, 0.0, 0.0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(n, e1)
        W = p + V[:, 0:1] * e1 + V[:, 1:2] * e2 + V[:, 2:3] * n
        m.add(W, F, np.array([1.0, 0.95, 0.9, 0.0], np.float32), None, S.LIGHT, S.light_aux(0.6, M.LIGHT_LANTERN))
    S.glow_halo(glow, [(X, Y, cz + R * 0.2)], R * 2.0, S.glow_col(0.0, 0.0, 0.0, 0.0), 0.22)
    part.walls.append((S.octa_poly(X, Y, R * 0.30 + 4.0), z - 10.0, z + 250.0))


def lantern_sphere(part, glow, P, r, rgb, pal, rng):
    """A paper lantern sphere (the research's lantern "planets"), hanging on a cord at P."""
    m = part.mesh("SM_BdDecor")
    V, F = M.icosphere(1)
    V = V * np.array([1.0, 1.0, 0.86])
    ribs = 0.78 + 0.22 * np.abs(np.cos(np.arctan2(V[:, 1], V[:, 0]) * 4.0))
    glow_ = (0.55 + 0.45 * np.clip(0.6 - V[:, 2], 0, 1)) * ribs
    col = np.concatenate([np.asarray(rgb)[None, :] ** (1 / 2.2) * glow_[:, None], np.full((len(V), 1), rng.uniform(0, 1))], 1)
    m.add(V * r + np.asarray(P), F, col.astype(np.float32), None, S.LIGHT, S.light_aux(0.95, M.LIGHT_LANTERN))
    S.glow_halo(glow, [P], r * 2.6, S.glow_col(pal / 8.0, 0.0, 0.0, rng.uniform(0, 1)), 0.45)
    V, F, UV = M.box_between(np.asarray(P) + np.array([0, 0, r]), np.asarray(P) + np.array([0, 0, 300.0]), 1.2)
    m.add(V, F, S.BLACK, UV, S.SURF)


# ---- camp life --------------------------------------------------------------------------------------------------------

def campfire(part, glow, X, Y, z, rng):
    """A campfire: a ring of stones, logs stacked in a cone, embers, flickering flames (M_BdGlow flame quads), its glow;
    three log benches round it; walls round the fire and the benches."""
    m = part.mesh("SM_BdDecor")
    for k in range(9):
        a = 2 * math.pi * k / 9 + rng.uniform(-0.15, 0.15)
        V, F, UV = M.box(rng.uniform(16, 24), rng.uniform(13, 19), rng.uniform(10, 16), (0, 0, 4))
        V = M.place(V, (X + math.cos(a) * 70.0, Y + math.sin(a) * 70.0, z), math.degrees(a) + rng.uniform(-20, 20))
        m.add(V, F, S.STONE, UV, S.SURF)
    for k in range(5):
        a = 2 * math.pi * k / 5 + rng.uniform(-0.2, 0.2)
        V, F, UV = M.box_between((X + math.cos(a) * 45.0, Y + math.sin(a) * 45.0, z), (X, Y, z + 62.0), 10.0)
        m.add(V, F, S.TIMBER_DARK, UV, S.SURF)
    V, F, UV = M.cylinder(42.0, 30.0, z - 2.0, z + 6.0, 8, cap_top=True, center=(X, Y))
    m.add(V, F, np.array([1.0, 0.5, 0.1, rng.uniform(0, 1)], np.float32), np.zeros((len(V), 2), np.float32), S.LIGHT,
          S.light_aux(0.9, M.LIGHT_FIRE))
    ph = rng.uniform(0, 1)
    for k, (sz, dz, dx) in enumerate(((46.0, 52.0, 0.0), (34.0, 44.0, 14.0), (30.0, 40.0, -15.0), (22.0, 70.0, 4.0))):
        S.glow_halo(glow, [(X + dx, Y - dx * 0.4, z + dz)], sz, S.glow_col(0.125, 0.0, 0.0, ph + k * 0.37), 1.0, M.GLOW_FLAME)
    S.glow_halo(glow, [(X, Y, z + 60.0)], 260.0, S.glow_col(0.0, 1.0, 0.0, 0.0), 0.16)
    part.walls.append((S.octa_poly(X, Y, 90.0), z - 10.0, z + 250.0))
    for k in range(3):
        a = 2 * math.pi * k / 3 + rng.uniform(-0.3, 0.3)
        c = np.array([X + math.cos(a) * 240.0, Y + math.sin(a) * 240.0])
        t = np.array([-math.sin(a), math.cos(a)]) * 85.0
        V, F, UV = M.box_between((*(c - t), z + 18.0), (*(c + t), z + 18.0), 30.0)
        m.add(V, F, S.TIMBER_DARK, UV, S.SURF)
        n = np.array([math.cos(a), math.sin(a)]) * 18.0
        part.walls.append(([tuple(c - t - n), tuple(c + t - n), tuple(c + t + n), tuple(c - t + n)], z - 10.0, z + 40.0))


FLAG_COLOURS = [((0.80, 0.10, 0.16), (0.95, 0.80, 0.20)), ((0.10, 0.35, 0.80), (0.85, 0.85, 0.90)),
                ((0.90, 0.50, 0.05), (0.60, 0.10, 0.50)), ((0.15, 0.55, 0.20), (0.95, 0.85, 0.30)),
                ((0.55, 0.15, 0.70), (0.20, 0.75, 0.80)), ((0.90, 0.85, 0.20), (0.80, 0.20, 0.10))]


def flag(part, X, Y, z, yaw, colours, rng):
    """A tall feather flag: a pole and a curved banner, two-tone (its edge band the second colour); a wall round the
    pole."""
    m = part.mesh("SM_BdDecor")
    H = rng.uniform(420.0, 520.0)
    V, F, UV = M.cylinder(3.0, 2.2, z - 20.0, z + H, 6, cap_top=True, center=(X, Y))
    m.add(V, F, S.STEEL, UV, S.SURF)
    fwd, _ = M.basis_from_yaw(yaw)
    n = 9
    inner, outer = [], []
    for i in range(n + 1):
        t = i / n
        hz = z + 120.0 + (H - 140.0) * t
        w = 95.0 * math.sin(math.pi * min(t * 1.15, 1.0)) ** 0.7 * (1.0 if t < 0.85 else (1.0 - (t - 0.85) / 0.15 * 0.6))
        curl = 18.0 * math.sin(t * math.pi * 1.2)
        inner.append((X, Y, hz))
        outer.append((X + fwd[0] * w, Y + fwd[1] * w, hz + curl - 15.0 * t))
    V = np.array(inner + outer)
    F = []
    for i in range(n):
        F += [(i, n + 1 + i, n + 2 + i), (i, n + 2 + i, i + 1)]
    F = np.array(F)
    F = np.concatenate([F, F[:, ::-1]])
    c0, c1 = (np.asarray(c) for c in colours)
    rgb = np.vstack([np.repeat(c0[None, :], n + 1, 0), np.repeat(((c0 + c1) * 0.5)[None, :], n + 1, 0)])
    hgt = np.maximum(V[:, 2] - z, 0.0) / 100.0
    m.add(V, F, M.encode(rgb, 0.0), np.zeros((len(V), 2), np.float32), S.SURF,
          (np.stack([hgt, np.full(len(V), float(M.KIND_CLOTH))], 1),))
    part.walls.append((S.octa_poly(X, Y, 7.0), z - 10.0, z + 250.0))


def wisteria(part, sf, x0, x1, half_w, eave_z, rng):
    """Wisteria hanging from the Pavilion's rafters (the research: on every rafter): lavender clusters, lit by the
    hall's strings and its pink uplights (M_BdSurface, cloth)."""
    m = part.mesh("SM_BdPavilionDecor")
    for x in np.linspace(x0 + 120, x1 - 120, 6):
        for k in range(16):
            y = -half_w + 50 + (2 * half_w - 100) * (k + rng.uniform(-0.45, 0.45)) / 15
            top = eave_z - 12.0
            L = rng.uniform(30.0, 85.0) * (1.0 if k % 3 else 0.6)
            V, F, UV = M.cone(rng.uniform(6.0, 10.0), 0.0, L, 5, (0.0, 0.0), skirt=False)
            V[:, 2] = top - V[:, 2]                         # hanging point down
            F = F[:, ::-1]
            V[:, 0] += x + rng.uniform(-25, 25)
            V[:, 1] += y
            col = np.array([0.50, 0.30, 0.72]) * rng.uniform(0.8, 1.15)
            m.add(sf.w(V), F, M.encode(col, 0.0), UV, S.SURF, (np.array([0.0, float(M.KIND_CLOTH)]),))
