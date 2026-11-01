"""bd_mesh.py: the mesh toolkit BIG DUB's generator builds with (plain Python + numpy; no Blender, no Unreal).

Every mesh is authored straight in Unreal's world frame (centimetres, X north, Y east, Z up; bd_frame.py), with each
triangle wound counter-clockwise when seen from the side it faces (the right-hand rule), as the gear's meshes are:
bd_blender.py turns them into Blender's frame the way art/gear/scripts/gear_blender.py does (y -> -y, corners
reversed), so after the FBX round trip Unreal shows exactly these coordinates and faces.

Per vertex: a colour (four floats 0..1, written to the FBX as they are and read by Unreal as bytes; what each channel
means depends on the material, bd_site.py), UV set 0, and AUX_UVS more UV sets of data for the materials (UV channels
1..AUX_UVS in Unreal; zero where a part doesn't set them):
  M_BdSurface  UV1 = (height over the ground in metres, the surface's kind: KIND_*)
  M_BdLights   UV1 = (brightness, the light's mode: LIGHT_*)
  M_BdGlow     UV1 = (yaw, pitch) degrees, UV2 = (length or size, width) cm, UV3 = (kind GLOW_*, brightness)
Per triangle: a material slot.
"""
import io
import math
import zipfile

import numpy as np

AUX_UVS = 3

# M_BdSurface's kinds (UV1.y): which detail it takes and how the light map lights it (build_bigdub.py SURFACE_HLSL)
KIND_GROUND, KIND_BARK, KIND_LEAF, KIND_STONE, KIND_CLOTH, KIND_WOOD, KIND_GEAR, KIND_CANOPY, KIND_BARK2 = 0, 1, 2, 3, 4, 5, 6, 7, 8
# M_BdLights' modes (UV1.y)
LIGHT_BULB, LIGHT_WARM, LIGHT_NEON, LIGHT_FIRE, LIGHT_FIXED, LIGHT_LANTERN = 0, 1, 2, 3, 4, 5
# M_BdGlow's kinds (UV3.x)
GLOW_HALO, GLOW_BEAM, GLOW_LASER, GLOW_SKY, GLOW_DOME, GLOW_FLAME = 0, 1, 2, 3, 4, 5


def aux(n, *pairs):
    """AUX_UVS sets for n vertices: pairs[k] (2,) or (n, 2) goes in set k, the rest zero."""
    out = np.zeros((AUX_UVS, n, 2), np.float32)
    for k, p in enumerate(pairs):
        if p is not None:
            out[k] = np.broadcast_to(np.asarray(p, np.float32), (n, 2)) if np.ndim(p) == 1 else np.asarray(p, np.float32).reshape(n, 2)
    return out


class Mesh:
    """Triangles, built up part by part, with a material slot per triangle."""

    def __init__(self, name, materials):
        self.name = name
        self.materials = list(materials)
        self._v, self._f, self._c, self._uv, self._x, self._m = [], [], [], [], [], []
        self._n = 0
        self.default_aux = None        # (pairs...) for add() calls that pass no aux (see aux())
        self.aux_rule = None           # or a function (material name, colour) -> pairs, which wins over default_aux

    def slot(self, material):
        return self.materials.index(material)

    def add(self, verts, faces, color, uv=None, material=0, aux_uv=None):
        """verts (n, 3) cm; faces (m, 3) indices into verts; color: (4,) for all or (n, 4); uv (n, 2) or None;
        aux_uv: (AUX_UVS, n, 2) from aux(), a tuple of pairs for aux(), or None (the mesh's default_aux, else zeros)."""
        verts = np.asarray(verts, np.float64).reshape(-1, 3)
        faces = np.asarray(faces, np.int64).reshape(-1, 3)
        n = len(verts)
        if n == 0 or len(faces) == 0:
            return
        col = np.asarray(color, np.float32)
        col = np.broadcast_to(col, (n, 4)) if col.ndim == 1 else col.reshape(n, 4)
        uvs = np.zeros((n, 2), np.float32) if uv is None else np.asarray(uv, np.float32).reshape(n, 2)
        mat = self.slot(material) if isinstance(material, str) else int(material)
        if aux_uv is None:
            pairs = self.aux_rule(self.materials[mat], color) if self.aux_rule else self.default_aux
            x = aux(n, *pairs) if pairs else aux(n)
        elif isinstance(aux_uv, tuple):
            x = aux(n, *aux_uv)
        else:
            x = np.asarray(aux_uv, np.float32).reshape(AUX_UVS, n, 2)
        self._v.append(verts)
        self._f.append(faces + self._n)
        self._c.append(np.ascontiguousarray(col, np.float32))
        self._uv.append(uvs)
        self._x.append(x)
        self._m.append(np.full(len(faces), mat, np.int32))
        self._n += n

    def extend(self, other, material_map=None):
        """Appends another mesh's triangles (its slots mapped by name)."""
        V, F, C, UV, M = other.arrays()
        if len(F) == 0:
            return
        names = [other.materials[i] for i in range(len(other.materials))]
        remap = np.array([self.slot(material_map.get(n, n) if material_map else n) for n in names], np.int32)
        self._v.append(V)
        self._f.append(F + self._n)
        self._c.append(C)
        self._uv.append(UV)
        self._x.append(other.aux_arrays())
        self._m.append(remap[M])
        self._n += len(V)

    def arrays(self):
        if not self._v:
            return (np.zeros((0, 3)), np.zeros((0, 3), np.int64), np.zeros((0, 4), np.float32), np.zeros((0, 2), np.float32),
                    np.zeros(0, np.int32))
        return (np.concatenate(self._v), np.concatenate(self._f), np.concatenate(self._c), np.concatenate(self._uv),
                np.concatenate(self._m))

    def aux_arrays(self):
        """(AUX_UVS, n, 2): the extra UV sets of every vertex."""
        if not self._x:
            return np.zeros((AUX_UVS, 0, 2), np.float32)
        return np.concatenate(self._x, axis=1)

    @property
    def triangles(self):
        return sum(len(f) for f in self._f)

    def save(self, path, lods=None):
        """One .npz per mesh: V F C UV X M, the slot names, and its LODs' arrays (V1 F1 ..., V2 F2 ...). X holds the
        extra UV sets (AUX_UVS, n, 2). Written with fixed zip times, so the same mesh gives the same bytes every run."""
        V, F, C, UV, M = self.arrays()
        data = dict(V=V.astype(np.float32), F=F.astype(np.int32), C=C, UV=UV, X=self.aux_arrays(), M=M,
                    materials=np.array(self.materials))
        for i, lod in enumerate(lods or [], start=1):
            v, f, c, uv, m = lod.arrays()
            if [lod.materials[k] for k in range(len(lod.materials))] != self.materials:
                raise ValueError(f"{self.name}: LOD {i} has other material slots ({lod.materials} vs {self.materials})")
            data.update({f"V{i}": v.astype(np.float32), f"F{i}": f.astype(np.int32), f"C{i}": c, f"UV{i}": uv,
                         f"X{i}": lod.aux_arrays(), f"M{i}": m})
        save_npz(path, data)


def save_npz(path, data):
    """np.savez_compressed's format, with every member stamped 1980-01-01 (numpy stamps the clock's time, so two runs'
    files would differ in their headers)."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for key, val in data.items():
            buf = io.BytesIO()
            np.lib.format.write_array(buf, np.asanyarray(val), allow_pickle=False)
            info = zipfile.ZipInfo(key + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            zf.writestr(info, buf.getvalue())


# ---- transforms -----------------------------------------------------------------------------------------------------

def rot_z(points, yaw_deg):
    """Rotates (n, 3) points about +Z by Unreal yaw (degrees: +X toward +Y)."""
    a = math.radians(yaw_deg)
    c, s = math.cos(a), math.sin(a)
    p = np.asarray(points, np.float64).reshape(-1, 3)
    return np.stack([p[:, 0] * c - p[:, 1] * s, p[:, 0] * s + p[:, 1] * c, p[:, 2]], axis=1)


def place(points, origin, yaw_deg=0.0, scale=1.0):
    p = np.asarray(points, np.float64).reshape(-1, 3) * scale
    return rot_z(p, yaw_deg) + np.asarray(origin, np.float64)


def basis_from_yaw(yaw_deg):
    """forward and right unit vectors (x, y) of an Unreal yaw."""
    a = math.radians(yaw_deg)
    return np.array([math.cos(a), math.sin(a)]), np.array([-math.sin(a), math.cos(a)])


# ---- primitives (local space; CCW outward) ------------------------------------------------------------------------

def box(sx, sy, sz, center=(0, 0, 0)):
    """An axis box sx x sy x sz centred on center: 24 vertices (flat faces), 12 triangles, UV per face in metres."""
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    cx, cy, cz = center
    faces_def = [  # (normal axis corners) each quad CCW seen from outside
        [(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)],      # +Z
        [(-hx, hy, -hz), (hx, hy, -hz), (hx, -hy, -hz), (-hx, -hy, -hz)],  # -Z
        [(hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz)],      # +X
        [(-hx, hy, -hz), (-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz)],  # -X
        [(hx, hy, -hz), (-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz)],      # +Y
        [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz)],  # -Y
    ]
    V, F, UV = [], [], []
    for quad in faces_def:
        b = len(V)
        V.extend([(x + cx, y + cy, z + cz) for x, y, z in quad])
        d1 = np.subtract(quad[1], quad[0])
        d2 = np.subtract(quad[3], quad[0])
        l1, l2 = float(np.linalg.norm(d1)) / 100.0, float(np.linalg.norm(d2)) / 100.0
        UV.extend([(0, 0), (l1, 0), (l1, l2), (0, l2)])
        F.extend([(b, b + 1, b + 2), (b, b + 2, b + 3)])
    return np.array(V), np.array(F), np.array(UV, np.float32)


def box_between(a, b, thickness, depth=None):
    """A box from point a to point b (3D), square section `thickness` (or thickness x depth), oriented along a-b."""
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    d = b - a
    L = float(np.linalg.norm(d))
    if L < 1e-6:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64), np.zeros((0, 2), np.float32)
    x = d / L
    up = np.array([0.0, 0.0, 1.0]) if abs(x[2]) < 0.95 else np.array([1.0, 0.0, 0.0])
    y = np.cross(up, x)
    y /= np.linalg.norm(y)
    z = np.cross(x, y)
    V, F, UV = box(L, thickness, depth if depth is not None else thickness, (L / 2, 0, 0))
    R = np.stack([x, y, z], axis=1)
    return V @ R.T + a, F, UV


def cylinder(r0, r1, z0, z1, sides=8, cap_top=True, cap_bottom=False, center=(0.0, 0.0)):
    """A tapered cylinder along Z, smooth-shared sides (UV: u around in metres, v up in metres)."""
    cx, cy = center
    V, F, UV = [], [], []
    circ = 2 * math.pi * max(r0, r1) / 100.0
    for k in range(sides + 1):
        a = 2 * math.pi * k / sides
        ca, sa = math.cos(a), math.sin(a)
        V.append((cx + r0 * ca, cy + r0 * sa, z0))
        V.append((cx + r1 * ca, cy + r1 * sa, z1))
        u = circ * k / sides
        UV.extend([(u, 0.0), (u, (z1 - z0) / 100.0)])
    for k in range(sides):
        i0, i1, i2, i3 = 2 * k, 2 * k + 1, 2 * k + 2, 2 * k + 3
        F.extend([(i0, i2, i3), (i0, i3, i1)])
    if cap_top and r1 > 0:
        c = len(V)
        V.append((cx, cy, z1))
        UV.append((0, 0))
        for k in range(sides):
            F.append((2 * k + 1, 2 * k + 3, c))
    if cap_bottom and r0 > 0:
        c = len(V)
        V.append((cx, cy, z0))
        UV.append((0, 0))
        for k in range(sides):
            F.append((2 * k + 2, 2 * k, c))
    return np.array(V), np.array(F), np.array(UV, np.float32)


def cone(r, z0, z1, sides=8, center=(0.0, 0.0), skirt=True):
    """A cone (tip up) with an optional underside."""
    cx, cy = center
    V = [(cx + r * math.cos(2 * math.pi * k / sides), cy + r * math.sin(2 * math.pi * k / sides), z0) for k in range(sides)]
    tip = len(V)
    V.append((cx, cy, z1))
    F = [(k, (k + 1) % sides, tip) for k in range(sides)]
    if skirt:
        c = len(V)
        V.append((cx, cy, z0 + (z1 - z0) * 0.08))
        F.extend([((k + 1) % sides, k, c) for k in range(sides)])
    UV = [(0, 0)] * len(V)
    return np.array(V), np.array(F), np.array(UV, np.float32)


_ICO = None


def icosphere(subdiv=1):
    """Unit icosphere (vertices, faces), CCW outward."""
    global _ICO
    if _ICO is not None and subdiv in _ICO:
        return _ICO[subdiv]
    t = (1 + 5 ** 0.5) / 2
    V = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t), (t, 0, -1),
         (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
         (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    V = [np.array(v, np.float64) / np.linalg.norm(v) for v in V]
    for _ in range(subdiv):
        cache = {}

        def mid(i, j):
            key = (min(i, j), max(i, j))
            if key not in cache:
                m = V[i] + V[j]
                V.append(m / np.linalg.norm(m))
                cache[key] = len(V) - 1
            return cache[key]
        nf = []
        for a, b, c in F:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf.extend([(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)])
        F = nf
    # The table above is wound counter-clockwise outward (its signed volume is positive).
    Va, Fa = np.array(V), np.array(F).copy()
    out = Va, Fa
    _ICO = _ICO or {}
    _ICO[subdiv] = out
    return out


def blob(rx, ry, rz, center, subdiv=1, rng=None, lumpy=0.18):
    """An irregular ellipsoid (a tree crown lobe): an icosphere scaled and pushed in and out a little."""
    V, F = icosphere(subdiv)
    V = V.copy()
    if rng is not None and lumpy > 0:
        V *= (1.0 + rng.uniform(-lumpy, lumpy, (len(V), 1)))
    V = V * np.array([rx, ry, rz]) + np.asarray(center, np.float64)
    return V, F.copy(), np.zeros((len(V), 2), np.float32)


def octahedron(r, center):
    c = np.asarray(center, np.float64)
    V = np.array([(r, 0, 0), (-r, 0, 0), (0, r, 0), (0, -r, 0), (0, 0, r), (0, 0, -r)], np.float64) + c
    F = np.array([(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)])
    return V, F, np.zeros((6, 2), np.float32)


def bulbs(points, r, kind="diamond"):
    """Many small light points at once: octahedra (8 triangles) or flat diamonds crossed (4 triangles, cheaper)."""
    P = np.asarray(points, np.float64).reshape(-1, 3)
    n = len(P)
    if n == 0:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64), np.zeros((0, 2), np.float32)
    if kind == "octa":
        base = np.array([(r, 0, 0), (-r, 0, 0), (0, r, 0), (0, -r, 0), (0, 0, r), (0, 0, -r)], np.float64)
        bf = np.array([(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)])
    else:
        # two vertical diamonds at right angles, each double-sided by its own winding: 8 verts, 4 + 4 triangles
        base = np.array([(r, 0, 0), (-r, 0, 0), (0, 0, r * 1.2), (0, 0, -r * 1.2),
                         (0, r, 0), (0, -r, 0), (0, 0, r * 1.2), (0, 0, -r * 1.2)], np.float64)
        bf = np.array([(0, 2, 1), (0, 1, 3), (1, 2, 0), (3, 1, 0), (4, 6, 5), (4, 5, 7), (5, 6, 4), (7, 5, 4)])
    k = len(base)
    V = (P[:, None, :] + base[None, :, :]).reshape(-1, 3)
    F = (bf[None, :, :] + (np.arange(n) * k)[:, None, None]).reshape(-1, 3)
    return V, F, np.zeros((len(V), 2), np.float32)


def quad(p0, p1, p2, p3, uv=((0, 0), (1, 0), (1, 1), (0, 1))):
    """A quad p0..p3 CCW seen from its front."""
    return np.array([p0, p1, p2, p3], np.float64), np.array([(0, 1, 2), (0, 2, 3)]), np.array(uv, np.float32)


def prism(poly, z0, z1, cap_top=True, cap_bottom=True):
    """A vertical prism over a convex polygon (x, y) (any winding)."""
    poly = [(float(x), float(y)) for x, y in poly]
    area = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    if area < 0:
        poly = poly[::-1]
    n = len(poly)
    V, F = [], []
    for x, y in poly:
        V.append((x, y, z0))
        V.append((x, y, z1))
    for i in range(n):
        j = (i + 1) % n
        F.extend([(2 * i, 2 * j, 2 * j + 1), (2 * i, 2 * j + 1, 2 * i + 1)])
    if cap_top:
        for i in range(1, n - 1):
            F.append((1, 2 * i + 1, 2 * (i + 1) + 1))
    if cap_bottom:
        for i in range(1, n - 1):
            F.append((0, 2 * (i + 1), 2 * i))
    return np.array(V), np.array(F), np.zeros((len(V), 2), np.float32)


def ribbon(points, widths, up_offsets=None):
    """A flat strip along a 3D polyline (its left and right edges at width/2), facing up; UV: u across, v along (m)."""
    P = np.asarray(points, np.float64).reshape(-1, 3)
    n = len(P)
    W = np.broadcast_to(np.asarray(widths, np.float64), (n,))
    d = np.zeros((n, 2))
    d[1:-1] = P[2:, :2] - P[:-2, :2]
    d[0] = P[1, :2] - P[0, :2]
    d[-1] = P[-1, :2] - P[-2, :2]
    d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
    left = np.stack([-d[:, 1], d[:, 0]], axis=1)    # +90 degrees in Unreal's yaw sense
    L = P.copy()
    R = P.copy()
    L[:, :2] += left * (W[:, None] / 2)
    R[:, :2] -= left * (W[:, None] / 2)
    V = np.empty((2 * n, 3))
    V[0::2] = R
    V[1::2] = L
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]) / 100.0
    UV = np.empty((2 * n, 2), np.float32)
    UV[0::2, 0] = 0
    UV[1::2, 0] = 1
    UV[0::2, 1] = s
    UV[1::2, 1] = s
    F = []
    for i in range(n - 1):
        a, b, c, e = 2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3
        F.extend([(a, c, e), (a, e, b)])
    return V, np.array(F), UV


def catenary(a, b, sag, n):
    """n points on a hanging string from a to b (3D), sagging `sag` cm at the middle."""
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    t = np.linspace(0, 1, n)
    P = a[None, :] + (b - a)[None, :] * t[:, None]
    P[:, 2] -= sag * 4 * t * (1 - t)
    return P


def grid_tris(nx, ny):
    """Triangles of a (ny, nx) vertex grid (row-major), CCW seen from +Z when rows run +Y... see terrain()."""
    i = np.arange(ny - 1)[:, None] * nx + np.arange(nx - 1)[None, :]
    a, b, c, d = i, i + 1, i + nx + 1, i + nx
    return np.stack([np.stack([a, c, b], -1), np.stack([a, d, c], -1)], axis=2).reshape(-1, 3)


def fix_winding_up(V, F):
    """Turns any triangle whose normal points down so it faces up (terrain-like surfaces)."""
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    nz = np.cross(p1 - p0, p2 - p0)[:, 2]
    F = F.copy()
    flip = nz < 0
    F[flip] = F[flip][:, ::-1]
    return F


def encode(rgb, alpha=0.0):
    """Linear colour -> the vertex colour the surface material decodes (value ** 2.2): better steps in the darks.
    alpha: M_BdSurface's and M_BdCrowd's shade (the colour x 1 - 0.8 alpha: a crown's inside, a stone's foot); the
    lights' and the glow's phase. 0 by default."""
    c = np.clip(np.asarray(rgb, np.float64), 0, 1) ** (1 / 2.2)
    a = np.asarray(alpha, np.float64)
    if c.ndim == 1:
        return np.concatenate([c, a.reshape(-1)[:1]]).astype(np.float32)
    if a.ndim == c.ndim - 1:
        a = a.reshape(a.shape + (1,))
    a = np.broadcast_to(a, c.shape[:-1] + (1,))
    return np.concatenate([c, a], axis=-1).astype(np.float32)
