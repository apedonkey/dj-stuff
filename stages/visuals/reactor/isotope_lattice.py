"""ISOTOPE LATTICE - REACTOR VJ loop. 8 bars, seamless, 1920x1080 @ 30 fps; tempo from vjkit (140 BPM half-time = 411
frames).

A crystal lattice of glowing atoms joined by neon bonds, turning slowly in the dark. The camera orbits it by exactly
the lattice block's own rotational symmetry per loop (90 degrees round a cubic block, 60 round a hexagonal one), so
frame 411 is frame 0 by construction; every other motion is periodic and symmetric about the orbit's axis.
  Waves    the bonds light up in neon waves on the accents: the kick sends a spherical wave out from the centre, the
           snare a flat wave sweeping up through the layers; the bonds run hot (toward white) as the front passes.
  Orbits   some atoms (symmetric sets of 4 or 6) carry crossed electron orbits: an electron runs round each ring with a
           comet trail behind it; they speed up in section B.
  Drop     section B (bar 5's downbeat): the palette lands on the hit, the waves run stronger, the lattice breathes with
           the kick (a slight swell of its spacing) and the camera eases in.
Variants (palette / camera / density): uv (rock salt, two species, a three-quarter view), gold (body-centred cubic,
seen from higher up), cyan (graphite-like hexagonal layers, a low view across them).
No strobing: the waves are fronts that travel through the bonds, never the whole lattice at once.

  blender.exe -b --factory-startup --python isotope_lattice.py -- --variant uv --frames 0,103,240 [--pct 50]
  blender.exe -b --factory-startup --python isotope_lattice.py -- --variant uv --all --seam DIR [--out DIR]
"""
import math
import os
import sys
from itertools import product

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vjkit as vj  # noqa: E402
import rx_science as rx  # noqa: E402
from vjkit import AMBER, CHERENKOV, COOLANT, EMBER, HOT, PLASMA, UVP, WHITE  # noqa: E402

GOLD = (1.0, 0.6, 0.12)
# lattice, spacing, bond radius and gain; atom colours / radii / gains per species; bond colours (A, B); the wave's
# hot colour; orbit colour; camera (elevation deg, distance m, lens mm, start azimuth deg, aim height m)
VARIANTS = {
    "uv": dict(lattice="rocksalt", a=1.5, bond_r=0.03, bond_gain=1.0,
               atom=(UVP, PLASMA), atom_r=(0.2, 0.14), atom_gain=(1.25, 1.0),
               bond=(CHERENKOV, PLASMA), hot=(0.8, 0.72, 1.0), orbit=(0.75, 0.55, 1.0),
               cam=(24.0, 17.5, 30.0, 18.0, -0.7)),
    "gold": dict(lattice="bcc", a=1.5, bond_r=0.022, bond_gain=0.8,
                 atom=(AMBER, HOT), atom_r=(0.15, 0.21), atom_gain=(1.1, 0.75),
                 bond=(GOLD, EMBER), hot=(1.0, 0.85, 0.6), orbit=(1.0, 0.8, 0.45),
                 cam=(32.0, 18.0, 30.0, 12.0, -0.67), trim=0.92),
    "cyan": dict(lattice="honeycomb", a=0.95, bond_r=0.026, bond_gain=0.85,
                 atom=(CHERENKOV, UVP), atom_r=(0.15, 0.15), atom_gain=(1.3, 1.3),
                 bond=(COOLANT, CHERENKOV), hot=(0.75, 1.0, 1.0), orbit=(0.6, 0.9, 1.0),
                 cam=(13.0, 15.0, 30.0, 8.0, 0.0)),
}
VNAME, V = vj.variant(VARIANTS)
# trim: the whole variant's emission. Gold's dense centre peaked at 0.653 luma per 1 m2 just after the downbeat
# (kick wave + swell; cap 0.65) at full gain
GAIN = float(vj.arg("--gain", 1.0)) * V.get("trim", 1.0)
BOND_R = V["bond_r"]
ORBIT_R, ORBIT_TUBE = 0.42, 0.011
REVS = 12                                      # electron laps per loop (whole: periodic)
FADE = 12.0                                    # depth cue: brightness x exp(-(distance - camera distance) / FADE)
WAVE_V, WAVE_W = 0.42, 0.75                    # the wave fronts: m per frame, half width (m)
SPEED_SWING = 0.4                              # electrons: (1 - swing) in bars 1-4, (1 + swing) in bars 5-8


# ------------------------------------------------------------------ lattices: (atoms [(pos, species)], bonds
# [(i, j, kind)], symmetry order about Z, orbit seeds [(pos, normals)]); every block is symmetric about Z
def rocksalt(a, n=2):
    atoms, index = [], {}
    for ijk in product(range(-n, n + 1), repeat=3):
        index[ijk] = len(atoms)
        atoms.append((Vector(ijk) * a, sum(ijk) % 2))
    bonds = []
    for (i, j, k), ia in index.items():
        for d in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            jb = index.get((i + d[0], j + d[1], k + d[2]))
            if jb is not None:
                bonds.append((ia, jb, 0))
    seeds = [Vector((n, 0, n)) * a, Vector((n, n, 0)) * a]
    return atoms, bonds, 4, seeds


def bcc(a, n=2):
    atoms, corners, bonds = [], {}, []
    for ijk in product(range(-n, n + 1), repeat=3):
        corners[ijk] = len(atoms)
        atoms.append((Vector(ijk) * a, 0))
    for i, j, k in product(range(-n, n), repeat=3):
        c = len(atoms)
        atoms.append((Vector((i + 0.5, j + 0.5, k + 0.5)) * a, 1))
        for di, dj, dk in product((0, 1), repeat=3):
            bonds.append((c, corners[(i + di, j + dj, k + dk)], 0))
    seeds = [Vector((n - 0.5, n - 0.5, n - 0.5)) * a, Vector((n, 0, 0)) * a]
    return atoms, bonds, 4, seeds


def honeycomb(bond_l, layers=2, rmax=3.3, gap=1.5):
    """Graphite-like hexagonal layers stacked straight above each other (a hexagon's centre on the Z axis: 6-fold)."""
    s3 = math.sqrt(3.0)
    flat = {}
    for n1, n2 in product(range(-6, 7), repeat=2):
        cx, cy = n1 * s3 * bond_l + n2 * s3 * bond_l / 2, n2 * 1.5 * bond_l
        for m in range(6):
            t = math.radians(30 + 60 * m)
            x, y = cx + bond_l * math.cos(t), cy + bond_l * math.sin(t)
            if math.hypot(x, y) <= rmax:
                flat[(round(x, 3) + 0.0, round(y, 3) + 0.0)] = (x, y)
    flat = list(flat.values())
    atoms, bonds = [], []
    for k in range(-layers, layers + 1):
        base = len(atoms)
        atoms += [(Vector((x, y, k * gap)), (k + layers) % 2) for x, y in flat]
        for i, j in product(range(len(flat)), repeat=2):
            if i < j and abs(math.dist(flat[i], flat[j]) - bond_l) < 0.02 * bond_l:
                bonds.append((base + i, base + j, 0))
        if k > -layers:
            bonds += [(base - len(flat) + i, base + i, 1) for i in range(len(flat))]
    # an outer vertex (of the hexagon next to the centre one) and a vertex of the centre hexagon, both on top
    seeds = [Vector((1.5 * s3 * bond_l, -0.5 * bond_l, layers * gap)),
             Vector((0.5 * s3 * bond_l, 0.5 * bond_l, layers * gap))]
    return atoms, bonds, 6, seeds


def lattice():
    kind = V["lattice"]
    if kind == "rocksalt":
        return rocksalt(V["a"])
    if kind == "bcc":
        return bcc(V["a"])
    return honeycomb(V["a"])


# ------------------------------------------------------------------ timing
def ramp(b, b0, b1):
    return vj.ease((b - b0) / (b1 - b0))


def b_amount(f):
    b = vj.beatpos(f % vj.FRAMES)
    return ramp(b, vj.HALF - 2, vj.HALF) * (1.0 - ramp(b, vj.BEATS - 2, vj.BEATS))


def speed_factor(b):
    b %= vj.BEATS
    if b < 2.0:
        s = 1.0 - 2.0 * vj.ease(b / 2.0)
    elif b < vj.HALF - 0.5:
        s = -1.0
    elif b < vj.HALF + 1.0:
        s = -1.0 + 2.0 * vj.ease((b - (vj.HALF - 0.5)) / 1.5)
    else:
        s = 1.0
    return 1.0 + SPEED_SWING * s


def lap_table():
    g = [0.0]
    for f in range(vj.FRAMES):
        acc = sum(speed_factor(vj.beatpos(f) + (vj.beatpos(f + 1) - vj.beatpos(f)) * (k + 0.5) / 8) for k in range(8))
        g.append(g[-1] + acc / 8)
    return [x / g[-1] for x in g]


G_TAB = lap_table()


def laps(f):
    n, ff = divmod(f, vj.FRAMES)
    return n + G_TAB[ff]


def since_accent(f, parity):
    """Frames since the last accent of this parity (0 = kicks, 1 = snares; half-time alternates them)."""
    best = None
    for i, (af, _) in enumerate(vj.accent_frames()):
        if i % 2 != parity:
            continue
        t = (f - af) % vj.FRAMES
        best = t if best is None else min(best, t)
    return best


def signals(f):
    c = vj.clock(f)
    tk, ts = since_accent(f, 0), since_accent(f, 1)
    strong = 0.75 + 0.35 * b_amount(f)
    s = {"Kick": c["kick"], "Swell": vj.swell(f), "Section": vj.section(f),
         "KR": WAVE_V * tk, "KA": strong * math.exp(-tk / 16.0) * min(1.0, (tk + 1) / 2.0),
         "SZ": -4.2 + WAVE_V * 1.05 * ts, "SA": 0.85 * strong * math.exp(-ts / 16.0) * min(1.0, (ts + 1) / 2.0),
         "Orb": 2 * math.pi * REVS * laps(f)}
    s.update(vj.loop_signals(f))
    return s


# ------------------------------------------------------------------ materials
def wave(s):
    """0..~1: the kick's spherical front and the snare's rising flat front at this point (lattice coordinates)."""
    x, y, z = s.obj_coords()
    r = s.math("SQRT", s.add(s.mul(x, x), s.mul(y, y), s.mul(z, z)))
    wk = s.mul(s.c("KA"), s.gauss(r, s.c("KR"), WAVE_W))
    ws = s.mul(s.c("SA"), s.gauss(z, s.c("SZ"), WAVE_W))
    return s.add(wk, ws)


def depth(s):
    """1 at the lattice's centre distance, brighter on the near side, dimmer on the far side."""
    return s.falloff(s.sub(s.dist, V["cam"][1]), FADE)


def bond_mat(name, base):
    s = vj.Shader(name)
    w = wave(s)
    lift = s.add(0.3, s.mul(w, 1.1), s.mul(s.c("Swell"), 0.3))
    col = s.mix(s.c("Section"), *V["bond"])
    col = s.mix(s.math("MINIMUM", s.mul(w, 0.75), 0.85), col, V["hot"])
    return s.emit(col, s.mul(s.core(0.5, 1.4), lift, depth(s), base * GAIN))


def atom_mat(name, col, base):
    s = vj.Shader(name)
    w = wave(s)
    lift = s.add(0.62, s.mul(w, 0.55), s.mul(s.c("Kick"), 0.12), s.mul(s.c("Swell"), 0.25))
    c = s.mix(s.mul(s.smooth(s.core(0.0, 1.0), 0.75, 1.0), 0.3), col, WHITE)
    return s.emit(c, s.mul(s.core(0.35, 1.25), lift, depth(s), base * GAIN))


def orbit_mat():
    """Per-object Object.color R = the electron's phase (turns). A comet trail behind the electron, a faint ring."""
    s = vj.Shader("Orbit")
    col, _, _ = s.obj_info()
    ph = s.xyz(col)[0]
    x, y, _ = s.obj_coords()
    ang = s.math("ARCTAN2", y, x)
    d = s.math("FRACT", s.add(s.mul(s.sub(s.c("Orb"), ang), 1.0 / (2 * math.pi)), ph))
    trail = s.add(s.exp(s.mul(d, -1.0 / 0.11)), 0.1)
    return s.additive(V["orbit"], s.mul(trail, depth(s), s.add(1.0, s.mul(s.c("Swell"), 0.3)), 2.4 * GAIN))


def electron_mat():
    s = vj.Shader("Electron")
    return s.emit(s.mix(0.5, V["orbit"], WHITE), s.mul(depth(s), s.core(0.5, 1.3), 4.0 * GAIN))


# ------------------------------------------------------------------ scene
def build():
    scene = vj.reset_scene()
    vj.clock_from(signals)
    ext = vj.EXT
    atoms, bonds, nsym, seeds = lattice()
    root = vj.new_empty("Lattice")
    vj.keyed(root, "scale", [(f, (1.0 + 0.03 * vj.clock(f)["kick"] * b_amount(f),) * 3) for f in ext])

    for kind in sorted({b[2] for b in bonds}):
        bm = bmesh.new()
        for i, j, k in bonds:
            if k == kind:
                vj.tube(bm, [atoms[i][0], atoms[j][0]], lambda u: BOND_R * (0.7 if kind else 1.0), segs=8)
        vj.new_obj(f"Bonds{kind}", bm, bond_mat(f"Bonds{kind}", V["bond_gain"] * (1.0 if kind == 0 else 0.55)), root)
    for sp in (0, 1):
        bm = bmesh.new()
        for p, s_ in atoms:
            if s_ == sp:
                bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=V["atom_r"][sp],
                                          matrix=Matrix.Translation(p))
        if bm.verts:
            ob = vj.new_obj(f"Atoms{sp}", bm, atom_mat(f"Atoms{sp}", V["atom"][sp], V["atom_gain"][sp]), root)
            ob.data.shade_smooth()
        else:
            bm.free()

    # electron orbits: two crossed rings per seed atom, copied round the block's symmetry (same phases, so the block
    # stays symmetric at every frame)
    om, em = orbit_mat(), electron_mat()
    ring_bm = bmesh.new()
    vj.tube(ring_bm, vj.circle_pts(Vector((0, 0, 0)), ORBIT_R, 64, axis="Z"), lambda u: ORBIT_TUBE, segs=6, closed=True)
    ring_me = vj.finish_bm(ring_bm, name="Ring")
    ebm = bmesh.new()
    bmesh.ops.create_uvsphere(ebm, u_segments=12, v_segments=6, radius=0.055)
    e_me = vj.finish_bm(ebm, name="Electron")
    normals = [Vector((0.75, 0.2, 0.65)).normalized(), Vector((-0.45, 0.8, 0.4)).normalized()]
    n = 0
    for si, seed in enumerate(seeds):
        for m in range(nsym):
            rz = Matrix.Rotation(2 * math.pi * m / nsym, 3, "Z")
            for ri, nrm in enumerate(normals):
                q = (rz @ nrm).to_track_quat("Z", "Y")
                ph = (0.37 * si + 0.5 * ri) % 1.0
                ring = vj.mesh_obj(f"Orbit{n:02d}", ring_me, om, root)
                ring.location, ring.rotation_mode, ring.rotation_quaternion = rz @ seed, "QUATERNION", q
                ring.color = (ph, 0.0, 0.0, 1.0)
                el = vj.mesh_obj(f"Electron{n:02d}", e_me, em, ring)
                keys = []
                for f in ext:
                    t = 2 * math.pi * (REVS * laps(f) + ph)
                    keys.append((f, (ORBIT_R * math.cos(t), ORBIT_R * math.sin(t), 0.0)))
                vj.keyed(el, "location", keys)
                n += 1

    el0, dist0, lens, az0, aim_z = V["cam"]
    cam = vj.camera(scene, lens=lens, clip=(0.5, 200.0))
    loc, rot, lk, prev = [], [], [], None
    for f in ext:
        u = f / vj.FRAMES
        az = math.radians(az0 + 360.0 / nsym * u)
        el = math.radians(el0 + 4.0 * math.sin(2 * math.pi * u + 0.3))
        d = dist0 * (1.0 - 0.07 * b_amount(f))
        p = Vector((d * math.cos(el) * math.sin(az), -d * math.cos(el) * math.cos(az), aim_z + d * math.sin(el)))
        aim = Vector((0.0, 0.0, aim_z + 0.04 * vj.jolt(f)))
        q = (aim - p).to_track_quat("-Z", "Y")
        q = q @ Matrix.Rotation(math.radians(1.2 * math.sin(2 * math.pi * u + 1.0)), 4, "Z").to_quaternion()
        prev = rx.compat_euler(q, prev)
        loc.append((f, tuple(p)))
        rot.append((f, tuple(prev)))
        lk.append((f, lens * (1.0 + 0.022 * vj.clock(f)["kick"])))
    vj.keyed(cam, "location", loc)
    vj.keyed(cam, "rotation_euler", rot)
    vj.keyed(cam.data, "lens", lk)
    return scene


scene = build()
vj.standard_render(scene)
vj.finish(scene, f"isotope_lattice_{VNAME}")
