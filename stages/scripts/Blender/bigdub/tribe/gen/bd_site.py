"""bd_site.py: generates BIG DUB, the user's festival-forest venue, from the real farm's geodata (plain Python + numpy +
scipy; run with `python -P`, docs/venues.md "BIG DUB"):

    PYTHONPATH=D:/VRDJ/tools/bigdub python -P D:/VRDJ/tools/bigdub/bd_site.py

What it writes to build/bigdub/ (bd_blender.py turns the meshes into FBX; Scripts/venues/bigdub/build_bigdub.py builds
the Unreal map from all of it):
  meshes/*.npz      every mesh in the world frame (bd_frame.py), LODs inside, material slots by name
  textures/*.png    the palette, the ground's detail and the night sky
  site.json         the spots (DJ starts, booth anchors), the instanced trees, the meshes' LODs and draw distances, the
                    walk's probes, the stats and the budget estimate
  walk.png          the walk from above: green walkable, red boundary walls, blue water, white floors, cyan the stones
  site_top.png      the Stone Circle and the Main Stage inside it from above, with the ring's walk check (ring_report)

The terrain is tier A of the plan (to the metre): the USGS 1 m DEM, its paths cut in as benches where the ground is too
steep for them (MAX_GRADE), nothing else moved. Fields and woods come from the masks (2 m).
"""
import json
import math
import os
import sys
import time

import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

import bd_frame as Fr
import bd_layout as L
import bd_mesh as M
import bd_structures as S
import bd_trees as T
import bd_crowd as C
import bd_decor as D

T0 = time.time()
OUT = Fr.OUT
MESH_DIR = os.path.join(OUT, "meshes")
TEX_DIR = os.path.join(OUT, "textures")
CELL = 2.0                 # the core terrain's grid (m)


def log(msg):
    print(f"[bigdub {time.time() - T0:6.1f}s] {msg}", flush=True)


# ====================================================================================================================
# the ground
# ====================================================================================================================

class Ground:
    """The carved 1 m DEM over EXT, the 10 m far window beyond it, the land cover, the water."""

    def __init__(self):
        self.dem0, self.x0, self.y0 = Fr.load_dem_ext()
        self.dem = self.dem0.copy()
        self.H, self.W = self.dem.shape
        self.far, self.fx0, self.fy0 = Fr.load_far_window(10, 3000)
        cls, step, roads = Fr.load_masks()
        self.cls, self.cstep, self.roads = cls, step, roads
        self.creek = Fr.load_creek()
        self.frame = None
        self.core_mask = None        # paths' cut cores (locked)
        self.path_weight = np.zeros(self.dem.shape, np.float32)
        self.path_kind = np.zeros(self.dem.shape, np.uint8)       # 1 gravel, 2 dirt

    # -- sampling (crop metres) --
    def elev(self, cx, cy):
        cx = np.asarray(cx, np.float64)
        cy = np.asarray(cy, np.float64)
        inside = (cx >= self.x0) & (cx <= self.x0 + self.W - 1.001) & (cy >= self.y0) & (cy <= self.y0 + self.H - 1.001)
        out = Fr.bilinear(self.far, cx, cy, self.fx0, self.fy0, 10.0)
        if np.any(inside):
            out = np.where(inside, Fr.bilinear(self.dem, cx, cy, self.x0, self.y0, 1.0), out)
        return out

    def zworld(self, Xw, Yw):
        cx, cy = self.frame.crop(Xw, Yw)
        return (self.elev(cx, cy) - self.frame.e0) * 100.0

    def cls_at(self, cx, cy):
        cx = np.asarray(cx, np.float64)
        cy = np.asarray(cy, np.float64)
        i = np.floor(cy / self.cstep).astype(np.int64)
        j = np.floor(cx / self.cstep).astype(np.int64)
        inside = (i >= 0) & (j >= 0) & (i < self.cls.shape[0]) & (j < self.cls.shape[1])
        out = np.ones(np.shape(cx), np.int64)                      # outside the crop: woods (the ridges are wooded)
        if np.any(inside):
            out = np.where(inside, self.cls[np.clip(i, 0, self.cls.shape[0] - 1), np.clip(j, 0, self.cls.shape[1] - 1)], out)
        return out

    def ij(self, cx, cy):
        return (np.asarray(cy) - self.y0).astype(np.int64), (np.asarray(cx) - self.x0).astype(np.int64)


def build_water(g):
    """Water on the 1 m grid: OSM's creek (the ravine's stream and the runs) and the creek traced from the LiDAR with
    its pools (ground within 0.35 m of the water's level near the channel). Also the water's level per cell."""
    H, W = g.H, g.W
    osm = np.zeros((H, W), bool)
    ci, cj = np.nonzero(g.cls == 3)
    for di in range(g.cstep):
        for dj in range(g.cstep):
            ii = ci * g.cstep + di - int(g.y0)
            jj = cj * g.cstep + dj - int(g.x0)
            ok = (ii >= 0) & (jj >= 0) & (ii < H) & (jj < W)
            osm[ii[ok], jj[ok]] = True
    seed = np.ones((H, W), bool)
    level = np.zeros((H, W), np.float64)
    for x, y, e in g.creek:
        i, j = int(y - g.y0), int(x - g.x0)
        if 0 <= i < H and 0 <= j < W:
            seed[i, j] = False
            level[i, j] = e
    dist, (ii, jj) = ndi.distance_transform_edt(seed, return_indices=True)
    wl = level[ii, jj]
    lidar = (dist <= 5.0) | ((dist <= 22.0) & (g.dem0 <= wl + 0.35))
    # the OSM-only stream: its level is its bed's (the ground's local minimum)
    bed = ndi.minimum_filter(g.dem0, size=9)
    level_all = np.where(dist <= 22.0, wl, bed + 0.05)
    water = lidar | osm
    log(f"water: {water.sum() / 1e4:.2f} ha on the 1 m grid ({lidar.sum() / 1e4:.2f} ha along the LiDAR creek and its pools, "
        f"{(osm & ~lidar).sum() / 1e4:.2f} ha more on OSM's line)")
    return water, level_all


def grade_limit(z, s, g, flat_start=0.0, flat_end=0.0):
    """The profile nearest z (the smoothed ground) whose grade stays within g, its two ends on the ground: z is first
    held inside both ends' cones (so the ends can be reached), then clamped forward and back with the ends pinned.
    flat_start / flat_end: metres at that end held level (where the path meets a bridge's deck)."""
    seg = np.diff(s)
    mid = (s[1:] + s[:-1]) / 2
    gs = np.where((mid < flat_start) | (mid > s[-1] - flat_end), 0.0, g)
    reach = np.concatenate([[0], np.cumsum(gs * seg)])          # the most a profile can climb from the start
    z0, z1 = z[0], z[-1]
    lower = np.maximum(z0 - reach, z1 - (reach[-1] - reach))
    upper = np.minimum(z0 + reach, z1 + (reach[-1] - reach))
    p = np.clip(z, lower, np.maximum(upper, lower))
    for _ in range(400):
        before = p.copy()
        for i in range(1, len(p)):
            lim = gs[i - 1] * seg[i - 1]
            p[i] = min(max(p[i], p[i - 1] - lim), p[i - 1] + lim)
        for i in range(len(p) - 2, -1, -1):
            lim = gs[i] * seg[i]
            p[i] = min(max(p[i], p[i + 1] - lim), p[i + 1] + lim)
        p[0], p[-1] = z0, z1
        if np.max(np.abs(p - before)) < 1e-4:
            break
    return p


def carve(g):
    """Cuts each path into the ground as a bench at its grade-limited profile (both cut and fill), with shoulders that
    blend back to the ground; then the bridges' end pads, level."""
    locked = np.zeros(g.dem.shape, bool)
    core_d = np.full(g.dem.shape, np.inf)
    profiles = {}
    for p in L.PATHS:
        pts, s = Fr.resample(p["pts"], 1.0)
        z = g.elev(pts[:, 0], pts[:, 1])
        zs = ndi.gaussian_filter1d(z, 4.0, mode="nearest")
        ends = [b[k] for b in L.BRIDGES for k in ("a", "b")]
        meets = lambda q: any(math.hypot(q[0] - e[0], q[1] - e[1]) < 1.0 for e in ends)
        fs = 3.0 if meets(pts[0]) else 0.0
        fe = 3.0 if meets(pts[-1]) else 0.0
        zs[0], zs[-1] = z[0], z[-1]
        prof = grade_limit(zs, s, L.MAX_GRADE, fs, fe)
        hw = p["width"] / 2
        dense, ds = Fr.resample(pts, 0.5)
        dz = np.interp(ds, s, prof)
        tree = cKDTree(dense)
        pad = hw + 12.0
        x0, y0 = dense.min(0) - pad
        x1, y1 = dense.max(0) + pad
        i0, j0 = g.ij(x0, y0)
        i1, j1 = g.ij(x1, y1)
        i0, j0 = max(int(i0), 0), max(int(j0), 0)
        i1, j1 = min(int(i1) + 1, g.H), min(int(j1) + 1, g.W)
        yy, xx = np.mgrid[i0:i1, j0:j1]
        cx = xx + g.x0 + 0.5
        cy = yy + g.y0 + 0.5
        d, k = tree.query(np.stack([cx.ravel(), cy.ravel()], 1), distance_upper_bound=pad)
        d = d.reshape(cx.shape)
        k = np.minimum(k.reshape(cx.shape), len(dense) - 1)
        target = dz[k]
        cur = g.dem[i0:i1, j0:j1]
        core = hw + (2.2 if p["kind"] == "dirt" else 0.6)   # a trail's bench: 3 walk cells wide
        shoulder = np.clip(2.5 + 0.9 * np.abs(cur - target), 2.5, 11.0)
        t = np.clip((d - core) / shoulder, 0, 1)
        w = np.where(d <= core, 1.0, 1.0 - t * t * (3 - 2 * t))
        w[~np.isfinite(d)] = 0.0
        # where two paths' cores overlap (a junction), the cell follows the nearer centreline; a shoulder never
        # moves another path's core
        cd = core_d[i0:i1, j0:j1]
        own_core = (d <= core) & (d < cd)
        w = np.where(locked[i0:i1, j0:j1] & ~own_core, 0.0, w)
        g.dem[i0:i1, j0:j1] = cur + w * (target - cur)
        locked[i0:i1, j0:j1] |= own_core
        cd[own_core] = d[own_core]
        pw = g.path_weight[i0:i1, j0:j1]
        vis = np.clip(1.0 - (d - hw) / 1.2, 0, 1).astype(np.float32)
        newer = vis > pw
        pw[newer] = vis[newer]
        g.path_kind[i0:i1, j0:j1][newer] = 1 if p["kind"] == "gravel" else 2
        grade = np.abs(np.diff(prof)) / np.maximum(np.diff(s), 1e-6)
        cut = float(np.max(np.abs(prof - z)))
        profiles[p["name"]] = dict(pts=pts, s=s, z=prof, width=p["width"], grade_max=float(grade.max()), cut_max=cut,
                                   festoon=p.get("festoon", False), kind=p["kind"])
        log(f"path {p['name']}: {s[-1]:.0f} m, {prof[0]:.1f} -> {prof[-1]:.1f} m, grade max {grade.max():.2f}, "
            f"cut/fill max {cut:.1f} m")
    for b in L.BRIDGES:
        for end in (b["a"], b["b"]):
            ze = float(g.elev(end[0], end[1]))
            i, j = g.ij(end[0], end[1])
            r, f = 2, 3                       # level within 2 m (the deck's 1.5 m run onto the bank), blended by 3 m
            yy, xx = np.mgrid[i - r - f:i + r + f + 1, j - r - f:j + r + f + 1]
            d = np.hypot(yy - i, xx - j)
            w = np.clip(1.0 - (d - r) / f, 0, 1)
            sub = g.dem[i - r - f:i + r + f + 1, j - r - f:j + r + f + 1]
            g.dem[i - r - f:i + r + f + 1, j - r - f:j + r + f + 1] = sub + w * (ze - sub)
    g.core_mask = locked
    return profiles


# ====================================================================================================================
# the spots and the structures
# ====================================================================================================================

def spot_frames(g):
    """Each spot's DJ floor (world), its yaw, and the stage builders' frames."""
    out = {}
    for name in L.SPOT_ORDER:
        sp = L.SPOTS[name]
        x, y = sp["dj"]
        dx, dy = math.cos(math.radians(sp["facing"])), -math.sin(math.radians(sp["facing"]))
        yaw = Fr.Frame.yaw_of_crop_dir(dx, dy)
        ground = float(g.elev(x, y))
        out[name] = dict(crop=(x, y), yaw=yaw, ground=ground, deck=sp["deck"], label=sp["label"])
    return out


def build_structures(g, spots, rng, glow):
    parts = {}
    ground = g.zworld
    # Main
    sp = spots["Main"]
    o = g.frame.world(sp["crop"][0], sp["crop"][1], sp["ground"] + sp["deck"])
    sf = S.StageFrame(o, sp["yaw"], ground)
    parts["Main"] = S.main_stage(sf, rng, glow)
    parts["Main"].points["frame"] = (o.tolist(), sp["yaw"])
    # Pavilion: the hall's floor 45 cm over the highest ground under it, the DJ's riser 20 cm over that
    sp = spots["Pavilion"]
    o0 = g.frame.world(sp["crop"][0], sp["crop"][1], sp["ground"])
    sf0 = S.StageFrame(o0, sp["yaw"], ground)
    gx = np.linspace(-250, 1880, 12)
    gy = np.linspace(-455, 455, 5)
    GX, GY = np.meshgrid(gx, gy)
    gmax = float(np.max(sf0.gz(GX.ravel(), GY.ravel())))
    hall = gmax + 45.0                      # local to o0
    o = o0 + np.array([0.0, 0.0, hall + 20.0])
    sf = S.StageFrame(o, sp["yaw"], ground)
    parts["Pavilion"] = S.pavilion(sf, rng, -20.0, glow)
    parts["Pavilion"].points["hall_floor_z"] = float(o[2] - 20.0)
    parts["Pavilion"].points["frame"] = (o.tolist(), sp["yaw"])
    spots["Pavilion"]["deck"] = (hall + 20.0) / 100.0
    # New Camp
    sp = spots["NewCamp"]
    o = g.frame.world(sp["crop"][0], sp["crop"][1], sp["ground"] + sp["deck"])
    sf = S.StageFrame(o, sp["yaw"], ground)
    parts["NewCamp"] = S.newcamp_stage(sf, rng, glow)
    parts["NewCamp"].points["frame"] = (o.tolist(), sp["yaw"])
    # bridges
    for b in L.BRIDGES:
        za = float(g.elev(*b["a"]))
        zb = float(g.elev(*b["b"]))
        A = g.frame.world(b["a"][0], b["a"][1], za)
        B = g.frame.world(b["b"][0], b["b"][1], zb)
        parts["bridge_" + b["name"]] = S.bridge(A, B, b["width"] * 100.0, b["kind"], rng, b["name"], glow)
        dz = (zb - za) / max(math.hypot(b["b"][0] - b["a"][0], b["b"][1] - b["a"][1]), 1e-6)
        log(f"bridge {b['name']}: {za:.1f} -> {zb:.1f} m, grade {abs(dz):.2f}")
    return parts


# ====================================================================================================================
# trees, tents, festoons
# ====================================================================================================================

def in_regions(cx, cy):
    m = np.zeros(np.shape(cx), bool)
    for poly in L.WALK_REGIONS:
        m |= Fr.inside_polygon(cx, cy, poly)
    return m


def near_regions(cx, cy, margin):
    """Within margin metres of the walk regions (a dilated raster test)."""
    return in_regions(cx, cy) | (_region_dist(cx, cy) <= margin)


_RD = None


def _region_dist(cx, cy):
    global _RD
    if _RD is None:
        x0, y0, x1, y1 = 800, -200, 1500, 950
        yy, xx = np.mgrid[y0:y1:2, x0:x1:2]
        inside = in_regions(xx + 1.0, yy + 1.0)
        d = ndi.distance_transform_edt(~inside) * 2.0
        _RD = (d, x0, y0)
    d, x0, y0 = _RD
    # points off the raster read its border's distance (over 150 m from every region: "not near")
    i = np.clip(((np.asarray(cy) - y0) / 2).astype(np.int64), 0, d.shape[0] - 1)
    j = np.clip(((np.asarray(cx) - x0) / 2).astype(np.int64), 0, d.shape[1] - 1)
    return d[i, j]


def keep_out_mask(g, parts, profiles, cx, cy, extra_m=0.0):
    """True where nothing may stand: paths, water, structures' walls and floors (crop points)."""
    bad = np.zeros(np.shape(cx), bool)
    i, j = g.ij(cx, cy)
    ok = (i >= 0) & (j >= 0) & (i < g.H) & (j < g.W)
    bad |= ~ok
    ii, jj = np.clip(i, 0, g.H - 1), np.clip(j, 0, g.W - 1)
    bad |= g.water[ii, jj]
    bad |= g.path_weight[ii, jj] > 0.05
    return bad


def poly_contains_any(polys, X, Y, margin):
    """For world points, inside any polygon's bounding box grown by margin (fast, conservative)."""
    out = np.zeros(np.shape(X), bool)
    for poly in polys:
        P = np.asarray(poly)
        x0, y0 = P.min(0) - margin
        x1, y1 = P.max(0) + margin
        out |= (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)
    return out


def poly_distance(polys, X, Y):
    """A world point's distance (cm) to the nearest of the polygons, 0 inside one."""
    best = float("inf")
    for poly in polys:
        P = np.asarray(poly, np.float64)[:, :2]
        if Fr.inside_polygon(np.array([X]), np.array([Y]), [tuple(q) for q in P])[0]:
            return 0.0
        A, B = P, np.roll(P, -1, axis=0)
        AB = B - A
        t = np.clip(((X - A[:, 0]) * AB[:, 0] + (Y - A[:, 1]) * AB[:, 1]) / np.maximum((AB ** 2).sum(1), 1e-9), 0.0, 1.0)
        d = np.hypot(A[:, 0] + t * AB[:, 0] - X, A[:, 1] + t * AB[:, 1] - Y)
        best = min(best, float(d.min()))
    return best


RING_CLEAR_M = 3.5           # no tree or tent inside the Stone Circle, nor this far outside its stones (a clear walk round)


def ring_clear(cx, cy, margin_m=RING_CLEAR_M):
    """Crop points inside the Stone Circle or within about margin_m outside its stones."""
    sc = L.STONE_CIRCLE
    return L.ring_radius(cx, cy) < 1.0 + margin_m / min(sc["ra"], sc["rb"])


def place_trees(g, parts, profiles, spots, rng):
    """Instanced trees: a jittered lattice over the woods inside the walk regions and NEAR_TREE_MARGIN_M around them.
    Kept clear: paths (+2 m), water (+3 m), the stages and their structures (+2.5 m), the bridges, the Stone Circle
    (the Main Stage and its crowd) and RING_CLEAR_M round its stones, and the other crowds' fronts; some trees stay in
    those crowds further back (the plan: tall trunks through the whole field)."""
    sp_ = L.TREE_SPACING_M
    x0, y0, x1, y1 = 880.0, -120.0, 1400.0, 860.0
    gx = np.arange(x0, x1, sp_)
    gy = np.arange(y0, y1, sp_)
    GX, GY = np.meshgrid(gx, gy)
    cx = (GX + rng.uniform(-0.42, 0.42, GX.shape) * sp_).ravel()
    cy = (GY + rng.uniform(-0.42, 0.42, GY.shape) * sp_).ravel()
    cls = g.cls_at(cx, cy)
    near = near_regions(cx, cy, L.NEAR_TREE_MARGIN_M)
    woods = (cls == 1) | (cls == 2)
    # a few trees stand on the field patches' edges too (the masks' fields include the clearings' rims)
    fieldside = (cls == 0) & (rng.uniform(0, 1, cx.shape) < 0.12)
    keep = near & (woods | fieldside)
    # water and paths
    i, j = g.ij(cx, cy)
    i = np.clip(i, 0, g.H - 1)
    j = np.clip(j, 0, g.W - 1)
    wd = ndi.distance_transform_edt(~g.water) if not hasattr(g, "_wd") else g._wd
    g._wd = wd
    keep &= wd[i, j] > 3.0
    pd = g._pathdist[i, j]
    keep &= pd > 2.0
    # structures: floors and walls (world) + 2.5 m
    W = g.frame.world(cx, cy, 0.0)
    X, Y = W[:, 0], W[:, 1]
    struct_polys = []
    for p in parts.values():
        struct_polys += [f[0] for f in p.floors]
        struct_polys += [w[0] for w in p.walls if (np.ptp(np.asarray(w[0])[:, 0]) > 60 or np.ptp(np.asarray(w[0])[:, 1]) > 60)]
    keep &= ~poly_contains_any(struct_polys, X, Y, 250.0)
    for b in L.BRIDGES:
        d, t = Fr.point_segment_distance(cx, cy, b["a"][0], b["a"][1], b["b"][0], b["b"][1])
        keep &= d > (b["width"] / 2 + 3.5)
    # the Stone Circle: the Main Stage and its crowd are inside it, the stones stand in a clearing
    keep &= ~ring_clear(cx, cy)
    # the other crowds: no trees in each stage's front, thinned further back
    for name, sp in spots.items():
        if name == "Main":
            continue
        fwd, right = M.basis_from_yaw(sp["yaw"])
        o = np.asarray(parts[name].points["frame"][0])[:2]
        rel = np.stack([X - o[0], Y - o[1]], 1)
        u = rel @ fwd / 100.0
        v = rel @ right / 100.0
        depth, half, thin_depth = {"Pavilion": (26.0, 12.0, 30.0), "NewCamp": (24.0, 16.0, 40.0)}[name]
        front = (u > -9.0) & (u < depth) & (np.abs(v) < half)
        thin = (u >= depth) & (u < thin_depth) & (np.abs(v) < half + 10) & (rng.uniform(0, 1, u.shape) < 0.55)
        keep &= ~(front | thin)
    cx, cy, cls = cx[keep], cy[keep], cls[keep]
    W = W[keep]
    n = len(cx)
    zg = g.elev(cx, cy)
    # species: evergreen cells -> hemlock (85 %), woods -> hardwood (85 %)
    hem = (cls == 2) ^ (rng.uniform(0, 1, n) < 0.15)
    # lit: most trees round the three stages; now and then one along a festooned path (a lantern tree to walk by) or in
    # a camp; the rest dark: the woods between the stages are a night forest. (The same two draws as the first build's
    # rule, so the trees stand where they stood.)
    lit_d = np.full(n, 1e9)
    for name, pr in profiles.items():
        if not pr["festoon"]:
            continue
        dense, _ = Fr.resample(pr["pts"], 1.0)
        d, _ = cKDTree(dense).query(np.stack([cx, cy], 1))
        lit_d = np.minimum(lit_d, d)
    near_path = lit_d < L.LIT_PATH_M
    near_stage = L.ring_radius(cx, cy) < L.LIT_RING
    for name, c in stage_centres(spots).items():
        if name != "Main":
            near_stage |= np.hypot(cx - c[0], cy - c[1]) < L.LIT_STAGE_M
    in_camp = np.zeros(n, bool)
    for camp in L.CAMPS:
        x0_, y0_, x1_, y1_ = camp["rect"]
        in_camp |= (cx >= x0_) & (cx <= x1_) & (cy >= y0_) & (cy <= y1_)
    u_path = rng.uniform(0, 1, n)
    u_stage = rng.uniform(0, 1, n)
    lit = (near_stage & (u_stage < 0.85)) | (near_path & (u_path < 0.22)) | (in_camp & (u_path < 0.10))
    yaw = rng.uniform(0, 360, n)
    sxy = rng.uniform(0.85, 1.15, n)
    sz = rng.uniform(0.82, 1.14, n)
    inst = {}
    trunks = []
    for name in ("SM_BdTreeHardwood", "SM_BdTreeHemlock", "SM_BdTreeLightsHardwood", "SM_BdTreeLightsHemlock"):
        inst[name] = []
    for k in range(n):
        name = "SM_BdTreeHemlock" if hem[k] else "SM_BdTreeHardwood"
        base = W[k]
        z = (zg[k] - g.frame.e0) * 100.0 - 15.0
        row = [float(base[0]), float(base[1]), float(z), float(yaw[k]), float(sxy[k]), float(sxy[k]), float(sz[k])]
        inst[name].append(row)
        if lit[k]:
            inst[T.LIGHTS_OF[name]].append(row)
        rt = (30.0 if hem[k] else 32.0) * sxy[k] + 3.0
        trunks.append((float(base[0]), float(base[1]), float(z) + 15.0, rt))
    hgt = {"SM_BdTreeHardwood": 3000.0, "SM_BdTreeHemlock": 2700.0}
    hs = np.array([(2700.0 if hem[k] else 3000.0) * sz[k] for k in range(n)]) / 100.0
    log(f"trees: {n} instanced ({int(lit.sum())} with lights, {int(hem.sum())} conifers), heights {hs.min():.1f}-{hs.max():.1f} m "
        f"(mean {hs.mean():.1f} m); " + ", ".join(f"{k} {len(v)}" for k, v in sorted(inst.items())))
    lit_xy = [(float(cx[k]), float(cy[k])) for k in range(n) if lit[k]]
    return inst, trunks, dict(count=n, lit=int(lit.sum()), conifers=int(hem.sum()), height_m=[round(float(hs.min()), 1),
                                                                                          round(float(hs.mean()), 1), round(float(hs.max()), 1)],
                              lit_near_stages=int((lit & near_stage).sum()), lit_by_paths=int((lit & ~near_stage).sum())), lit_xy


def place_tents(g, parts, trunks, spots, rng):
    part = S.Part()
    mesh = part.mesh("SM_BdTents")
    tx = np.array([t[0] for t in trunks])
    ty = np.array([t[1] for t in trunks])
    ttree = cKDTree(np.stack([tx, ty], 1)) if len(tx) else None
    placed = []
    struct_polys = []
    for p in parts.values():
        struct_polys += [f[0] for f in p.floors] + [w[0] for w in p.walls]
    count = 0
    lit_n = 0
    for camp in L.CAMPS:
        x0, y0, x1, y1 = camp["rect"]
        n = int((x1 - x0) * (y1 - y0) / 1e4 * camp["per_ha"])
        tries = 0
        made = 0
        while made < n and tries < n * 30:
            tries += 1
            cx = rng.uniform(x0, x1)
            cy = rng.uniform(y0, y1)
            if not in_regions(np.array([cx]), np.array([cy]))[0]:
                continue
            i, j = g.ij(cx, cy)
            if g.water[i, j] or g._pathdist[i, j] < 2.5 or g._wd[i, j] < 6.0:
                continue
            sl = g.slope_deg[i, j]
            if sl > 12.0:
                continue
            W = g.frame.world(cx, cy, 0.0)
            X, Y = float(W[0]), float(W[1])
            if ttree is not None and ttree.query([X, Y])[0] < 260.0:
                continue
            if poly_contains_any(struct_polys, np.array([X]), np.array([Y]), 350.0)[0]:
                continue
            if any(math.hypot(X - px, Y - py) < 520.0 for px, py in placed):
                continue
            # crowds stay clear: the Stone Circle and a walk round it, the other stages' fronts
            if ring_clear(np.array([cx]), np.array([cy]), RING_CLEAR_M + 2.5)[0]:
                continue
            clear = True
            for name, sp in spots.items():
                if name == "Main":
                    continue
                fwd, right = M.basis_from_yaw(sp["yaw"])
                o = np.asarray(parts[name].points["frame"][0])[:2]
                rel = np.array([X - o[0], Y - o[1]])
                u, v = rel @ fwd / 100.0, rel @ right / 100.0
                if -10.0 < u < 40.0 and abs(v) < 24.0:
                    clear = False
            if not clear:
                continue
            z = (float(g.elev(cx, cy)) - g.frame.e0) * 100.0
            kind = rng.choice(["dome", "dome", "dome", "canopy", "bell"]) if camp["name"] != "newcamp" else rng.choice(
                ["dome", "dome", "bell", "bell", "canopy"])
            lit = rng.uniform(0, 1) < 0.4
            # lit only near the paths or by the stages (New Camp, Camp Central): the rest of the camps sleep dark
            shown = lit and (camp["name"] in ("newcamp", "camp_central") or g._pathdist[i, j] < 14.0)
            S.tent(part, mesh, X, Y, z, rng.uniform(0, 360), kind, lit, rng, shown)
            placed.append((X, Y))
            made += 1
            lit_n += int(shown)
        count += made
    log(f"tents: {count} ({lit_n} lit from inside)")
    part.points["tents"] = count
    return part


def build_festoons(g, profiles, rng, glow):
    part = S.Part()
    poles = 0
    for name, pr in profiles.items():
        if not pr["festoon"]:
            continue
        pts = pr["pts"]
        W = g.frame.world(pts[:, 0], pts[:, 1], pr["z"])
        p = S.festoons(W, pr["width"] * 50.0, rng, offset=rng.uniform(0, 1), glow=glow)
        paths = part.points.get("pole_paths", [])
        part.merge(p)
        part.points["pole_paths"] = paths + [p.points.get("pole_list", [])]
        poles += p.points.get("poles", 0)
    log(f"festoons: {poles} poles")
    part.points["poles"] = poles
    return part


# ====================================================================================================================
# the terrain's meshes
# ====================================================================================================================

# the moon: a waxing gibbous in the south-south-west (plan section 3), as the sky shows it (M_BdSky) and the material
# lights with it: bearing 205 degrees, 40 degrees up (the plan's is lower; at 22 degrees the 28 m trees round every
# clearing hid it). World X north, Y east, Z up.
MOON_BEARING, MOON_ELEV = 205.0, 40.0
MOON = np.array([math.cos(math.radians(MOON_ELEV)) * math.cos(math.radians(MOON_BEARING)),
                 math.cos(math.radians(MOON_ELEV)) * math.sin(math.radians(MOON_BEARING)), math.sin(math.radians(MOON_ELEV))])
# the sun's direction in the moon's own frame (x the eye's right, y up, z toward the eye): 80 % lit, waxing, so its bright
# limb is to the right (west) and a little down toward the set sun
MOON_SUN = np.array([0.778, -0.195, 0.586]) / np.linalg.norm([0.778, -0.195, 0.586])

# the ground's albedos (linear) by land cover: 0 field (grass), 1 deciduous woods (leaf litter), 2 evergreen (needles),
# 3 water (OSM's line), 4 road (OSM). The paths' dirt and the steep's rock come in the material (the light map's B and the
# surface's normal), the light from the light map and the moon.
GROUND_ALB = {0: (0.080, 0.100, 0.042), 1: (0.120, 0.088, 0.056), 2: (0.088, 0.072, 0.050), 3: (0.040, 0.045, 0.042),
              4: (0.170, 0.142, 0.108)}
RING_FLOOR = np.array([0.150, 0.118, 0.080])          # the Stone Circle's floor: packed dirt (the research: bare dirt)
MOSS = np.array([0.050, 0.085, 0.034])
_MACRO = None


def macro_noise(cx, cy):
    """A smooth 0..1 noise over crop metres (patches of 10-40 m) for the ground's variation, from its own fixed stream."""
    global _MACRO
    if _MACRO is None:
        rng = np.random.default_rng(4401)
        x0, y0, x1, y1 = Fr.EXT
        grid = rng.uniform(0, 1, (int((y1 - y0) / 4) + 2, int((x1 - x0) / 4) + 2))
        n = ndi.gaussian_filter(grid, 4.0) * 0.65 + ndi.gaussian_filter(grid, 1.5) * 0.35
        _MACRO = ((n - n.min()) / (n.max() - n.min()), x0, y0)
    n, x0, y0 = _MACRO
    return Fr.bilinear(n, cx, cy, x0, y0, 4.0)


def ground_colours(g, cx, cy):
    """Albedos (linear) for terrain points: the land cover, patches of lighter and darker ground and moss in the woods,
    darker wet ground by the water; inside the Stone Circle its packed dirt."""
    cls = g.cls_at(cx, cy)
    base = np.zeros(cx.shape + (3,))
    for k, c in GROUND_ALB.items():
        base[cls == k] = c
    nz = macro_noise(cx, cy)
    base *= (0.76 + 0.48 * nz)[..., None]
    moss = np.clip((nz - 0.60) * 3.0, 0, 1) * ((cls == 1) | (cls == 2))
    base = base * (1 - 0.6 * moss[..., None]) + MOSS * (0.6 * moss)[..., None]
    t = np.clip((1.03 - L.ring_radius(cx, cy)) / 0.22, 0, 1)
    base = base * (1 - t[..., None]) + RING_FLOOR * (0.85 + 0.3 * nz)[..., None] * t[..., None]
    i, j = g.ij(cx, cy)
    inside = (i >= 0) & (j >= 0) & (i < g.H) & (j < g.W)
    ii, jj = np.clip(i, 0, g.H - 1), np.clip(j, 0, g.W - 1)
    wd = np.where(inside, g._wd[ii, jj], 99.0)
    base *= (1.0 - 0.45 * np.clip(1.0 - wd / 4.0, 0, 1))[..., None]
    return base


def normals_of_grid(Z, step_cm):
    gy, gx = np.gradient(Z, step_cm)
    # Z indexed [row = crop y (south) -> world -X, col = crop x (east) -> world +Y]: d/dX = -d/drow, d/dY = d/dcol
    n = np.stack([gy, -gx, np.ones_like(Z)], -1)       # (-dZ/dX, -dZ/dY, 1) with dZ/dX = -gy, dZ/dY = gx
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def terrain_tile(g, x0, y0, x1, y1, step, name, skirt_m=3.0, hole=None, kind=M.KIND_GROUND):
    """A terrain grid over crop [x0, x1] x [y0, y1] about every `step` m (a whole number of cells, so the grid ends on the
    tile's edge), world frame, its albedo per vertex, UV1 = (0, kind), with skirts on its edges and round its hole."""
    xs = np.linspace(x0, x1, max(1, int(round((x1 - x0) / step))) + 1)
    ys = np.linspace(y0, y1, max(1, int(round((y1 - y0) / step))) + 1)
    CX, CY = np.meshgrid(xs, ys)
    E = g.elev(CX, CY)
    W = g.frame.world(CX, CY, E)
    rgb = ground_colours(g, CX, CY)
    ny, nx = CX.shape
    V = W.reshape(-1, 3)
    F = M.grid_tris(nx, ny)
    inside = None
    if hole is not None:
        hx0, hy0, hx1, hy1 = hole
        cxm = (CX[:-1, :-1] + CX[1:, 1:]) / 2
        cym = (CY[:-1, :-1] + CY[1:, 1:]) / 2
        inside = (cxm > hx0) & (cxm < hx1) & (cym > hy0) & (cym < hy1)
        F = F[~np.repeat(inside.ravel(), 2)]
    F = M.fix_winding_up(V, F)
    col = M.encode(rgb.reshape(-1, 3), 0.0)
    UV = np.stack([CX.ravel(), CY.ravel()], 1).astype(np.float32) / 4.0
    m = M.Mesh(name, ("Surface",))
    m.default_aux = (np.array([0.0, float(kind)]),)
    m.add(V, F, col, UV, 0)
    if skirt_m > 0:
        G = V.reshape(ny, nx, 3)
        edges = [G[0], G[-1], G[:, 0], G[:, -1]]
        if inside is not None:
            # round the hole: every edge between a kept cell and a cut one, so a coarse ring never shows a gap where it
            # stands over the finer tiles' edge
            for r in range(ny - 1):
                for c in range(nx - 1):
                    if inside[r, c]:
                        continue
                    for dr, dc, p, q in ((-1, 0, (r, c), (r, c + 1)), (1, 0, (r + 1, c), (r + 1, c + 1)),
                                         (0, -1, (r, c), (r + 1, c)), (0, 1, (r, c + 1), (r + 1, c + 1))):
                        rr, cc = r + dr, c + dc
                        if 0 <= rr < ny - 1 and 0 <= cc < nx - 1 and inside[rr, cc]:
                            edges.append(np.array([G[p], G[q]]))
        for edge in edges:
            n = len(edge)
            low = edge - np.array([0, 0, skirt_m * 100.0])
            Vs = np.concatenate([edge, low])
            Fs = []
            for k in range(n - 1):
                Fs.append((k, k + 1, n + k + 1))
                Fs.append((k, n + k + 1, n + k))
            Fs = np.array(Fs)
            Fs = np.concatenate([Fs, Fs[:, ::-1]])          # both sides: a skirt is seen from either
            m.add(Vs, Fs, M.encode((0.040, 0.034, 0.026)), None, 0)
    return m


def build_terrain(g):
    """The core's tiles (three LODs each) and SM_BdFar: the rest of the extended DEM, the horizon and the far woods'
    canopy in one mesh. They ring every spot, so their LODs chosen by their bounds would never leave LOD 0, and apart
    they cost a draw each from every heading; together, one."""
    lods = {}
    x0, y0, x1, y1 = L.CORE
    cols, rows = L.CORE_TILES
    tw, th = (x1 - x0) / cols, (y1 - y0) / rows
    for b in range(rows):
        for a in range(cols):
            name = f"SM_BdTerrain_{a}_{b}"
            tx, ty = x0 + a * tw, y0 + b * th
            lods[name] = [terrain_tile(g, tx, ty, tx + tw, ty + th, s, name) for s in (CELL, 4.0, 8.0)]
    far = M.Mesh("SM_BdFar", ("Surface",))
    ex0, ey0, ex1, ey1 = Fr.EXT
    far.extend(terrain_tile(g, ex0, ey0, ex1, ey1, L.OUTER_STEP_M, "outer", 4.0, hole=L.CORE))
    # the horizon: the 10 m window beyond EXT, every 50 m, raised by the forest's height: the real ridge lines, wooded
    fx0, fy0 = g.fx0, g.fy0
    fx1, fy1 = fx0 + g.far.shape[1] * 10.0 - 10.0, fy0 + g.far.shape[0] * 10.0 - 10.0
    xs = np.arange(fx0, fx1, L.FAR_STEP_M)
    ys = np.arange(fy0, fy1, L.FAR_STEP_M)
    CX, CY = np.meshgrid(xs, ys)
    E = Fr.bilinear(g.far, CX, CY, fx0, fy0, 10.0) + 17.0
    Wf = g.frame.world(CX, CY, E)
    ny, nx = CX.shape
    F = M.grid_tris(nx, ny)
    cxm = (CX[:-1, :-1] + L.FAR_STEP_M / 2).ravel()
    cym = (CY[:-1, :-1] + L.FAR_STEP_M / 2).ravel()
    inner = (cxm > ex0 + 60) & (cxm < ex1 - 60) & (cym > ey0 + 60) & (cym < ey1 - 60)
    F = F[~np.repeat(inner, 2)]
    V = Wf.reshape(-1, 3)
    F = M.fix_winding_up(V, F)
    lum = 0.7 + 0.6 * macro_noise(CX, CY).reshape(-1)
    rgb = np.array([0.040, 0.066, 0.032])[None, :] * lum[:, None]
    far.add(V, F, M.encode(rgb, 0.0), np.zeros((len(V), 2), np.float32), 0, (np.array([17.0, float(M.KIND_CANOPY)]),))
    lods["SM_BdFar"] = [far]
    return lods


def build_canopy(g, rng):
    """The forest beyond the instanced trees: a canopy surface 18-26 m over the woods (L.CANOPY_STEP_M cells, one mesh:
    it rings every spot, so splitting it saves no triangles in view, only adds draws), with skirts down to the ground
    where the woods end: what the far woods are, seen from the stages at night."""
    ex0, ey0, ex1, ey1 = Fr.EXT
    step = L.CANOPY_STEP_M
    xs = np.arange(ex0, ex1 + 1, step)
    ys = np.arange(ey0, ey1 + 1, step)
    CX, CY = np.meshgrid(xs, ys)
    cxm, cym = CX[:-1, :-1] + step / 2, CY[:-1, :-1] + step / 2
    cls = g.cls_at(cxm, cym)
    woods = (cls == 1) | (cls == 2)
    outside = ~((cxm >= 0) & (cxm < 2000) & (cym >= 0) & (cym < 1800))
    noise = ndi.gaussian_filter(rng.uniform(0, 1, cxm.shape), 2.0)
    woods |= outside & (noise > np.percentile(noise, 22))
    i, j = g.ij(cxm, cym)
    ok = (i >= 0) & (j >= 0) & (i < g.H) & (j < g.W)
    wet = np.zeros(cxm.shape, bool)
    wet[ok] = g.water[i[ok], j[ok]]
    woods &= ~wet
    near = near_regions(cxm, cym, L.NEAR_TREE_MARGIN_M - 4.0)
    woods &= ~near
    E = g.elev(CX, CY)
    hgt = 22.0 + 4.0 * ndi.gaussian_filter(rng.uniform(-1, 1, CX.shape), 1.0) + rng.uniform(-2.0, 2.0, CX.shape)
    top = g.frame.world(CX, CY, E + hgt)
    bottom = g.frame.world(CX, CY, E - 0.5)
    m = M.Mesh("SM_BdCanopy", ("Surface",))
    Vt, Ft, Ct, Ht = [], [], [], []
    vid = {}

    def vtx(r, c, low=False):
        key = (r, c, low)
        if key not in vid:
            p = (bottom if low else top)[r, c]
            vid[key] = len(Vt)
            Vt.append(p)
            lum = 0.65 + 0.35 * ((r * 7 + c * 13) % 5) / 4.0
            Ct.append(np.array([0.046, 0.078, 0.036]) * (lum if not low else 0.55))
            Ht.append(0.0 if low else float(hgt[r, c]))
        return vid[key]
    for r in range(woods.shape[0]):
        for c in range(woods.shape[1]):
            if not woods[r, c]:
                continue
            a, b, cc, d = vtx(r, c), vtx(r, c + 1), vtx(r + 1, c + 1), vtx(r + 1, c)
            Ft += [(a, b, cc), (a, cc, d)]
            for (dr, dc), (p, q) in (((-1, 0), ((r, c), (r, c + 1))), ((1, 0), ((r + 1, c + 1), (r + 1, c))),
                                     ((0, -1), ((r + 1, c), (r, c))), ((0, 1), ((r, c + 1), (r + 1, c + 1)))):
                rr, cc2 = r + dr, c + dc
                if 0 <= rr < woods.shape[0] and 0 <= cc2 < woods.shape[1] and woods[rr, cc2]:
                    continue
                t0, t1 = vtx(*p), vtx(*q)
                b0, b1 = vtx(*p, low=True), vtx(*q, low=True)
                Ft += [(t0, b1, t1), (t0, b0, b1), (t0, t1, b1), (t0, b1, b0)]
    V = np.array(Vt)
    F = np.array(Ft)
    H = np.array(Ht)
    m.add(V, F, M.encode(np.array(Ct), 0.0), np.zeros((len(V), 2), np.float32), 0,
          (np.stack([H, np.full(len(V), float(M.KIND_CANOPY))], 1),))
    log(f"canopy beyond the trees: {len(F)} triangles ({step:.0f} m cells), in SM_BdFar")
    return m


def build_water_mesh(g):
    """The creek's surface over every water cell of the core (2 m) and the extended DEM (8 m), at the water's level."""
    m = M.Mesh("SM_BdWater", ("Water",))
    for (x0, y0, x1, y1), step, hole in ((L.CORE, CELL, None), (Fr.EXT, 8.0, L.CORE)):
        xs = np.arange(x0, x1 + 0.01, step)
        ys = np.arange(y0, y1 + 0.01, step)
        CX, CY = np.meshgrid(xs, ys)
        i, j = g.ij(CX, CY)
        ok = (i >= 0) & (j >= 0) & (i < g.H) & (j < g.W)
        ii, jj = np.clip(i, 0, g.H - 1), np.clip(j, 0, g.W - 1)
        lvl = np.where(ok, g.water_level[ii, jj], 0.0)
        wet = np.where(ok, ndi.binary_dilation(g.water, iterations=2)[ii, jj] if step > 4 else g.water[ii, jj], False)
        cell = wet[:-1, :-1] | wet[1:, :-1] | wet[:-1, 1:] | wet[1:, 1:]
        if hole is not None:
            cxm, cym = CX[:-1, :-1] + step / 2, CY[:-1, :-1] + step / 2
            hx0, hy0, hx1, hy1 = hole
            cell &= ~((cxm > hx0) & (cxm < hx1) & (cym > hy0) & (cym < hy1))
        # the level on dry corners: the nearest wet corner's (so the sheet stays flat at the banks)
        lv = np.where(wet, lvl, np.nan)
        mask = ~np.isnan(lv)
        if mask.any():
            dd, (ia, ja) = ndi.distance_transform_edt(~mask, return_indices=True)
            lv = lv[ia, ja]
        W = g.frame.world(CX, CY, lv + 0.04)
        ny, nx = CX.shape
        F = M.grid_tris(nx, ny)
        F = F[np.repeat(cell.ravel(), 2)]
        if len(F) == 0:
            continue
        used = np.unique(F)
        remap = np.full(nx * ny, -1)
        remap[used] = np.arange(len(used))
        V = W.reshape(-1, 3)[used]
        F = remap[F]
        F = M.fix_winding_up(V, F)
        UV = (np.stack([CX.ravel()[used], CY.ravel()[used]], 1) / 6.0).astype(np.float32)
        m.add(V, F, np.array([1.0, 1.0, 1.0, 1.0], np.float32), UV, 0)
    log(f"water surface: {m.triangles} triangles")
    return m


def build_sky(g):
    """A dome 4 km round the site (inward), UV equirectangular: u around from north, v from the zenith down."""
    R = 400000.0
    nu, nv = 48, 14
    V, UV, F = [], [], []
    for iv in range(nv + 1):
        el = math.radians(90.0 - 100.0 * iv / nv)            # down to 10 degrees under the horizon
        for iu in range(nu + 1):
            az = 2 * math.pi * iu / nu
            V.append((R * math.cos(el) * math.cos(az), R * math.cos(el) * math.sin(az), R * math.sin(el)))
            UV.append((iu / nu, iv / nv))
    for iv in range(nv):
        for iu in range(nu):
            a = iv * (nu + 1) + iu
            b = a + 1
            c = a + nu + 2
            d = a + nu + 1
            F += [(a, c, b), (a, d, c)]
    V = np.array(V) + np.array([g.sky_centre[0], g.sky_centre[1], -2000.0])
    F = np.array(F)
    # inward: each triangle's normal points at the centre
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    n = np.cross(p1 - p0, p2 - p0)
    outward = np.einsum("ij,ij->i", n, (p0 + p1 + p2) / 3 - V.mean(0)) > 0
    F[outward] = F[outward][:, ::-1]
    m = M.Mesh("SM_BdSky", ("Sky",))
    m.add(V, F, np.array([1.0, 1.0, 1.0, 1.0], np.float32), np.array(UV, np.float32), 0)
    return m


# ====================================================================================================================
# textures
# ====================================================================================================================

PALETTE = [(1.00, 0.12, 0.08), (1.00, 0.45, 0.06), (1.00, 0.78, 0.18), (0.15, 1.00, 0.25), (0.10, 0.85, 0.80),
           (0.30, 0.45, 1.00), (0.65, 0.25, 1.00), (1.00, 0.20, 0.65)]


def write_png(path, rgba):
    from PIL import Image
    Image.fromarray(np.ascontiguousarray(rgba)).save(path)


def srgb(x):
    """Linear 0..1 to the sRGB curve the GPU decodes sRGB textures with (exactly: its linear toe matters in the dark)."""
    x = np.clip(np.asarray(x, np.float64), 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def to_u8(x, dither=None):
    """0..1 to bytes; with dither (an array of -0.5..0.5) added in steps first, so dark gradients don't band."""
    x = np.asarray(x, np.float64) * 255.0
    if dither is not None:
        x = x + dither
    return np.clip(np.round(x), 0, 255).astype(np.uint8)


# CC0 photographs (tools/bigdub/cc0/<asset>/, each with its LICENSE.txt and SOURCE.txt; docs/venues.md "Licences"), used
# as luminance detail: the material multiplies an albedo by them, so only their light and dark is taken
CC0 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cc0")
CC0_FILES = {"grass": ("Grass004", "Grass004_1K-JPG_Color.jpg"), "litter": ("dry_decay_leaves", "dry_decay_leaves_diff_1k.jpg"),
             "dirt": ("gravel_ground_01", "gravel_ground_01_diff_1k.jpg"), "rock": ("mossy_rock", "mossy_rock_diff_1k.jpg"),
             "bark": ("Bark012", "Bark012_1K-JPG_Color.jpg"), "pine": ("pine_bark", "pine_bark_diff_1k.jpg"),
             "planks": ("wood_planks_grey", "wood_planks_grey_diff_1k.jpg")}


def cc0_detail(key, contrast):
    """A CC0 colour map as detail: its linear luminance over its mean (so the albedo keeps its brightness), the contrast
    scaled, stored halved (0..1 for 0..2; the material doubles it)."""
    from PIL import Image
    folder, name = CC0_FILES[key]
    im = Image.open(os.path.join(CC0, folder, name)).convert("RGB")
    if im.size != (1024, 1024):
        im = im.resize((1024, 1024), Image.LANCZOS)
    lin = (np.asarray(im, np.float64) / 255.0) ** 2.2
    lum = lin @ np.array([0.2126, 0.7152, 0.0722])
    d = 1.0 + (lum / lum.mean() - 1.0) * contrast
    return np.clip(d, 0.0, 2.0) / 2.0


def tile_noise(rng, size, octaves):
    """Tiling fBm (size x size, 0..1)."""
    n = np.zeros((size, size))
    for octave, amp in octaves:
        g = rng.uniform(-1, 1, (octave, octave))
        g = np.kron(g, np.ones((size // octave, size // octave)))
        n += amp * ndi.gaussian_filter(g, size / octave / 2.5, mode="wrap")
    return (n - n.min()) / (n.max() - n.min())


def milky_way_sky(rng):
    """The night sky for M_BdSky, 2048 x 512 (u round from north toward east, v from the zenith to 10 degrees under the
    horizon, as SM_BdSky's UV): rgb the sky's own light (linear before the sRGB curve): the gradient to the horizon, a
    faint airglow, a town's glow low in the south-east and the Milky Way: the summer band from the south (its core 21
    degrees up, due south at 22:30, plan section 3) arching nearly overhead in the east to the north, with star clouds
    and the dark rift; alpha the stars' density (the material draws the stars)."""
    W, H = 2048, 512
    v = (np.arange(H) + 0.5) / H
    el = 90.0 - 100.0 * v
    az = (np.arange(W) + 0.5) / W * 360.0
    AZ, EL = np.meshgrid(az, el)
    d = np.stack([np.cos(np.radians(EL)) * np.cos(np.radians(AZ)), np.cos(np.radians(EL)) * np.sin(np.radians(AZ)),
                  np.sin(np.radians(EL))], -1)
    zen = np.array([0.0010, 0.0016, 0.0042])
    hor = np.array([0.0042, 0.0058, 0.0105])
    t = np.clip(1 - np.maximum(EL, 0) / 90.0, 0, 1) ** 3
    sky = zen * (1 - t[..., None]) + hor * t[..., None]
    sky += np.array([0.00025, 0.00060, 0.00035]) * np.exp(-((EL - 14.0) / 8.0) ** 2)[..., None]
    sky += np.array([0.0030, 0.0022, 0.0013]) * (np.exp(-np.maximum(EL, 0) / 5.0) * np.exp(-((AZ - 140.0) / 30.0) ** 2))[..., None]

    def unit(azd, eld):
        return np.array([math.cos(math.radians(eld)) * math.cos(math.radians(azd)),
                         math.cos(math.radians(eld)) * math.sin(math.radians(azd)), math.sin(math.radians(eld))])
    # the galactic plane: through the core (az 180, el 21) and high in the east (az 90, el 80)
    core = unit(180.0, 21.0)
    pole = np.cross(core, unit(90.0, 80.0))
    pole /= np.linalg.norm(pole)
    e2 = np.cross(pole, core)
    b = np.degrees(np.arcsin(np.clip(d @ pole, -1, 1)))                   # galactic latitude
    lon = np.degrees(np.arctan2(d @ e2, d @ core))                        # longitude from the core
    # star clouds: noise in (longitude, latitude), wrapping in longitude
    nz = tile_noise(rng, 512, ((8, 0.4), (16, 0.3), (32, 0.2), (64, 0.1)))
    li = ((lon + 180.0) / 360.0 * 512).astype(np.int64) % 512
    bi = np.clip(((b + 45.0) / 90.0 * 512).astype(np.int64), 0, 511)
    clouds = nz[bi, li]
    fine = tile_noise(rng, 512, ((32, 0.5), (64, 0.3), (128, 0.2)))[bi, (li * 3) % 512]
    width = 10.0 + 7.0 * np.exp(-(lon / 32.0) ** 2)
    band = np.exp(-(b / width) ** 2)
    along = 0.72 + 0.28 * np.exp(-(lon / 55.0) ** 2)
    bright = band * along * (0.45 + 0.75 * clouds) * (0.8 + 0.4 * fine)
    bright += 0.9 * np.exp(-(lon ** 2 + (b * 1.5) ** 2) / 11.0 ** 2) * (0.7 + 0.5 * clouds)
    rift_b = 1.2 + 1.1 * np.sin(np.radians(lon * 4.0))
    rift = (np.exp(-((b - rift_b) / 2.2) ** 2) * (1.0 / (1.0 + np.exp(-(lon + 5.0) / 4.0)))
            * (1.0 / (1.0 + np.exp((lon - 115.0) / 8.0))))
    dark = np.clip((0.42 - fine) * 3.0, 0, 1) * band
    bright *= (1.0 - 0.62 * rift) * (1.0 - 0.35 * dark)
    warmth = np.exp(-(lon / 38.0) ** 2)
    mw_col = np.array([0.78, 0.84, 1.0]) * (1 - warmth[..., None]) + np.array([1.0, 0.86, 0.66]) * warmth[..., None]
    sky += mw_col * (bright * 0.060)[..., None]
    density = np.clip(0.18 + 0.82 * bright / max(float(np.percentile(bright, 99.5)), 1e-6), 0, 1)
    below = EL < 0
    sky[below] = hor * 0.6
    density[below] = 0.0
    dith = rng.uniform(-0.5, 0.5, (H, W, 1))
    out = np.zeros((H, W, 4), np.uint8)
    out[..., :3] = to_u8(srgb(sky), dith)
    out[..., 3] = to_u8(density)
    return out


def moon_texture(rng):
    """The moon's face, 256 x 256 (x right, y up as the eye sees it): highland grey with the near side's maria where
    they lie (Imbrium, Serenitatis, Tranquillitatis, Crisium, Fecunditatis, Nubium, Procellarum), craters and Tycho's
    rays, darker at the limb. Alpha: the disc."""
    N = 256
    y, x = np.mgrid[0:N, 0:N]
    px = (x + 0.5) / N * 2 - 1
    py = 1 - (y + 0.5) / N * 2
    r = np.hypot(px, py)
    alb = np.full((N, N), 0.80)
    maria = [(-0.30, 0.38, 0.30), (0.12, 0.36, 0.17), (0.28, 0.12, 0.20), (0.62, 0.22, 0.13), (0.50, -0.20, 0.14),
             (-0.20, -0.30, 0.16), (-0.58, 0.05, 0.36), (-0.05, -0.05, 0.12)]
    for mx, my, mr in maria:
        alb -= 0.30 * np.exp(-((px - mx) ** 2 + (py - my) ** 2) / (mr * mr))
    alb = np.clip(alb, 0.42, 0.85)
    alb *= 0.9 + 0.2 * tile_noise(rng, N, ((8, 0.5), (16, 0.3), (32, 0.2)))
    for _ in range(90):
        cx, cy = rng.uniform(-1, 1, 2)
        cr = rng.uniform(0.012, 0.06)
        dd = np.hypot(px - cx, py - cy) / cr
        alb *= 1.0 - 0.18 * np.exp(-(dd ** 2)) + 0.12 * np.exp(-((dd - 1.0) / 0.25) ** 2)
    tx, ty = -0.12, -0.62                     # Tycho and its rays
    ang = np.arctan2(py - ty, px - tx)
    dist = np.hypot(px - tx, py - ty)
    rays = (0.5 + 0.5 * np.cos(ang * 9.0)) ** 8 * np.exp(-dist / 0.5)
    alb += 0.18 * rays + 0.3 * np.exp(-(dist / 0.03) ** 2)
    z = np.sqrt(np.clip(1 - r * r, 0, 1))
    lin = np.clip(alb * (0.72 + 0.28 * z), 0, 1)
    out = np.zeros((N, N, 4), np.uint8)
    out[..., :3] = to_u8(srgb(lin))[..., None] * np.ones(3, np.uint8)
    out[..., 3] = to_u8(np.clip((1.0 - r) * 60.0, 0, 1))
    return out


def build_textures():
    """T_BdPalette (8 x 1), T_BdDetail (the ground's four kinds: R grass, G leaf litter, B the paths' dirt, A rock),
    T_BdDetail2 (R hardwood bark, G foliage and ripples (our noise), B conifer bark, A planks), T_BdSky, T_BdMoon. Each
    procedural part from its own random stream."""
    os.makedirs(TEX_DIR, exist_ok=True)
    pal = np.zeros((1, 8, 4), np.uint8)
    for k, c in enumerate(PALETTE):
        pal[0, k, :3] = to_u8(srgb(np.array(c)))
        pal[0, k, 3] = 255
    write_png(os.path.join(TEX_DIR, "T_BdPalette.png"), pal)
    det = np.stack([cc0_detail("grass", 0.9), cc0_detail("litter", 0.85), cc0_detail("dirt", 0.9), cc0_detail("rock", 0.9)], -1)
    write_png(os.path.join(TEX_DIR, "T_BdDetail.png"), to_u8(det))
    leaf = tile_noise(np.random.default_rng(5101), 1024, ((8, 0.30), (16, 0.30), (32, 0.25), (64, 0.15))) ** 1.4
    leaf = np.clip(leaf / leaf.mean() * 0.5, 0, 1)
    det2 = np.stack([cc0_detail("bark", 1.0), leaf, cc0_detail("pine", 1.0), cc0_detail("planks", 0.9)], -1)
    write_png(os.path.join(TEX_DIR, "T_BdDetail2.png"), to_u8(det2))
    write_png(os.path.join(TEX_DIR, "T_BdSky.png"), milky_way_sky(np.random.default_rng(5102)))
    write_png(os.path.join(TEX_DIR, "T_BdMoon.png"), moon_texture(np.random.default_rng(5103)))
    log("textures: T_BdPalette (8 x 1), T_BdDetail and T_BdDetail2 (1024, CC0 luminance), T_BdSky (2048 x 512), "
        "T_BdMoon (256)")


# ====================================================================================================================
# walking: the floor, the walls, the walk's check
# ====================================================================================================================

def walk_cells(g, parts, spots):
    """The core's 2 m cells a walker may stand on: inside the walk regions, no water within 1 m, the cell's triangles
    under MAX_WALK_SLOPE_DEG, joined (through the bridges) to the Main Stage."""
    x0, y0, x1, y1 = L.CORE
    xs = np.arange(x0, x1 + 0.5 * CELL, CELL)
    ys = np.arange(y0, y1 + 0.5 * CELL, CELL)
    CX, CY = np.meshgrid(xs, ys)
    Z = g.elev(CX, CY)
    cxm, cym = CX[:-1, :-1] + CELL / 2, CY[:-1, :-1] + CELL / 2
    ok = in_regions(cxm, cym)
    wet1 = ndi.binary_dilation(g.water, iterations=1)
    i, j = g.ij(cxm, cym)
    inside = (i >= 0) & (j >= 0) & (i < g.H) & (j < g.W)
    ii, jj = np.clip(i, 0, g.H - 1), np.clip(j, 0, g.W - 1)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            ok &= ~wet1[np.clip(ii + di, 0, g.H - 1), np.clip(jj + dj, 0, g.W - 1)]
    ok &= inside
    # slope of the cell's two triangles (the floor mesh's own)
    a, b, c, d = Z[:-1, :-1], Z[:-1, 1:], Z[1:, 1:], Z[1:, :-1]
    s1 = np.hypot(b - a, c - b) / CELL
    s2 = np.hypot(c - d, d - a) / CELL
    slope = np.degrees(np.arctan(np.maximum(s1, s2)))
    ok &= slope <= L.MAX_WALK_SLOPE_DEG
    lab, n = ndi.label(ok)
    # join components through the bridges, keep the Main Stage's
    def lab_at(cx, cy):
        r = int((cy - y0) // CELL)
        q = int((cx - x0) // CELL)
        best = 0
        for rad in range(0, 4):
            for rr in range(r - rad, r + rad + 1):
                for qq in range(q - rad, q + rad + 1):
                    if 0 <= rr < lab.shape[0] and 0 <= qq < lab.shape[1] and lab[rr, qq]:
                        return lab[rr, qq]
        return best
    parent = list(range(n + 1))

    def find(a_):
        while parent[a_] != a_:
            parent[a_] = parent[parent[a_]]
            a_ = parent[a_]
        return a_
    for bdef in L.BRIDGES:
        la, lb = lab_at(*bdef["a"]), lab_at(*bdef["b"])
        if la and lb:
            parent[find(la)] = find(lb)
        log(f"bridge {bdef['name']}: joins walk components {la} and {lb}")
    # each stage's crowd field (a point in front of its lip) joins its stage's deck
    roots = {}
    for name, sp in spots.items():
        fx, fy = math.cos(math.radians(L.SPOTS[name]["facing"])), -math.sin(math.radians(L.SPOTS[name]["facing"]))
        px, py = sp["crop"][0] + fx * 12.0, sp["crop"][1] + fy * 12.0
        roots[name] = lab_at(px, py)
    main_root = find(roots["Main"]) if roots["Main"] else 0
    keep = np.zeros(n + 1, bool)
    for k in range(1, n + 1):
        keep[k] = find(k) == main_root
    walk = keep[lab]
    reach = {name: bool(r and find(r) == main_root) for name, r in roots.items()}
    log(f"walk cells: {int(ok.sum())} under {L.MAX_WALK_SLOPE_DEG:.0f} degrees in the regions, {int(walk.sum())} joined to the "
        f"Main Stage ({walk.sum() * CELL * CELL / 1e4:.2f} ha); spots joined: {reach}")
    return dict(walk=walk, ok=ok, lab=lab, CX=CX, CY=CY, Z=Z, slope=slope, reach=reach, cxm=cxm, cym=cym)


def collision(g, wc, parts, trunks):
    """The walking collision: SM_BdWalkFloors (the walkable terrain's triangles, the decks', stairs' and floors'
    prisms, the bridge decks) and SM_BdWalkWalls (the walk's edge, every trunk, the structures' walls)."""
    walk, CX, CY, Z = wc["walk"], wc["CX"], wc["CY"], wc["Z"]
    W = g.frame.world(CX, CY, Z)
    ny, nx = CX.shape
    F = M.grid_tris(nx, ny)
    F = F[np.repeat(walk.ravel(), 2)]
    used = np.unique(F)
    remap = np.full(nx * ny, -1)
    remap[used] = np.arange(len(used))
    Vt = W.reshape(-1, 3)[used]
    Ft = M.fix_winding_up(Vt, remap[F])
    floors = M.Mesh("SM_BdWalkFloors", ("Surface",))
    floors.add(Vt, Ft, np.array([1, 1, 1, 1], np.float32), None, 0)
    nfloor_prisms = 0
    floor_polys = []
    for p in parts.values():
        for poly, z0, z1 in p.floors:
            V, Fp, _ = M.prism(poly, z0, z1)
            floors.add(V, Fp, np.array([1, 1, 1, 1], np.float32), None, 0)
            floor_polys.append((poly, z0, z1))
            nfloor_prisms += 1
        for V, Fr_ in p.ramps:
            floors.add(V, Fr_, np.array([1, 1, 1, 1], np.float32), None, 0)
            # the ramp's underside too (a closed sheet is safer for sweeps from either side)
            floors.add(V - np.array([0, 0, 20.0]), Fr_[:, ::-1], np.array([1, 1, 1, 1], np.float32), None, 0)
    walls = M.Mesh("SM_BdWalkWalls", ("Surface",))
    # the walk's edge: every cell side between a walkable cell and one that isn't (or the grid's end), one wall each.
    # pad[r + 1, c + 1] is cell (r, c).
    edges = []
    Wg = W
    pad = np.pad(walk, 1, constant_values=False)
    MAXRUN = 1                     # one cell side a wall: a bridge's opening is then exact
    # sides along a vertex row r (from vertex (r, c) to (r, c + 1)): between cells (r - 1, c) and (r, c)
    for r in range(ny):
        e = pad[r, 1:nx] != pad[r + 1, 1:nx]
        c = 0
        while c < nx - 1:
            if not e[c]:
                c += 1
                continue
            s0 = c
            while c < nx - 1 and e[c] and c - s0 < MAXRUN:
                c += 1
            edges.append(((r, s0), (r, c)))
    # sides along a vertex column c (from vertex (r, c) to (r + 1, c)): between cells (r, c - 1) and (r, c)
    for c in range(nx):
        e = pad[1:ny, c] != pad[1:ny, c + 1]
        r = 0
        while r < ny - 1:
            if not e[r]:
                r += 1
                continue
            s0 = r
            while r < ny - 1 and e[r] and r - s0 < MAXRUN:
                r += 1
            edges.append(((s0, c), (r, c)))
    # openings: where a bridge meets a bank, the edge stays open across its deck's width
    openings = []
    for b in L.BRIDGES:
        A = g.frame.world(b["a"][0], b["a"][1], 0.0)[:2]
        B = g.frame.world(b["b"][0], b["b"][1], 0.0)[:2]
        openings.append((A, B, b["width"] * 50.0 + 15.0))     # 12 cm past the rails: too narrow for a body
    nwall = 0
    dropped_open = dropped_floor = 0
    for (r0, c0), (r1, c1) in edges:
        if (r0, c0) == (r1, c1):
            continue
        p0 = Wg[r0, c0]
        p1 = Wg[r1, c1]
        mid = (p0 + p1) / 2
        skip = False
        for A, B, hw in openings:
            ab = B - A
            Lab = float(np.linalg.norm(ab))
            u = ab / Lab
            rel = mid[:2] - A
            along = float(rel @ u)
            perp = abs(float(rel[0] * u[1] - rel[1] * u[0]))
            # only where the deck is: over the gap and its 1.5 m run onto each bank (+0.5 m); past that the edge's walls
            # stay, or a walker could leave the landing where the ground beyond it is too steep to walk
            if perp < hw and -200.0 < along < Lab + 200.0:
                skip = True
        if skip:
            dropped_open += 1
            continue
        for poly, z0, z1 in floor_polys:
            if Fr.inside_polygon(np.array([mid[0]]), np.array([mid[1]]), poly)[0]:
                skip = True
                break
        if skip:
            dropped_floor += 1
            continue
        zlo = min(p0[2], p1[2]) - 10.0
        zhi = max(p0[2], p1[2]) + 250.0
        dx, dy = (p1 - p0)[:2]
        Ln = math.hypot(dx, dy)
        nxv, nyv = -dy / Ln * 1.0, dx / Ln * 1.0
        poly = [(p0[0] - nxv, p0[1] - nyv), (p1[0] - nxv, p1[1] - nyv), (p1[0] + nxv, p1[1] + nyv), (p0[0] + nxv, p0[1] + nyv)]
        V, Fw, _ = M.prism(poly, zlo, zhi)
        walls.add(V, Fw, np.array([1, 1, 1, 1], np.float32), None, 0)
        nwall += 1
    # trunks inside or near the walk (octagons; a trunk outside the walk's reach needs none)
    tw = 0
    walk_area = cKDTree(np.stack([W[:-1, :-1][walk][:, 0], W[:-1, :-1][walk][:, 1]], 1)) if walk.any() else None
    for X, Y, z, r in trunks:
        if walk_area is None or walk_area.query([X, Y])[0] > 400.0:
            continue
        V, Fw, _ = M.prism(S.octa_poly(X, Y, r), z - 10.0, z + 250.0)
        walls.add(V, Fw, np.array([1, 1, 1, 1], np.float32), None, 0)
        tw += 1
    sw = 0
    for p in parts.values():
        for poly, z0, z1 in p.walls:
            V, Fw, _ = M.prism(poly, z0, z1)
            walls.add(V, Fw, np.array([1, 1, 1, 1], np.float32), None, 0)
            sw += 1
    stats = dict(edge_walls=nwall, edge_walls_open_at_bridges=dropped_open, edge_walls_under_floors=dropped_floor,
                 trunk_walls=tw, structure_walls=sw, floor_prisms=nfloor_prisms, floor_tris=floors.triangles,
                 wall_tris=walls.triangles)
    log(f"collision: floors {floors.triangles} tris ({nfloor_prisms} prisms), walls {walls.triangles} tris ({nwall} edge, "
        f"{dropped_open} opened at the bridges, {dropped_floor} under floors, {tw} trunks, {sw} structure walls)")
    return floors, walls, stats


def structure_cells(W, parts, margin_cm=200.0):
    """The cells (by their centres' world XY in W) a structure stands on or within margin_cm of: its walls, and its
    floors (a deck's walker stands on its top, not on the ground under it; this cell model knows only the ground)."""
    WX, WY = W[..., 0], W[..., 1]
    blocked = np.zeros(WX.shape, bool)
    edge_pts = []
    for p in parts.values():
        for poly, z0, z1 in list(p.walls) + list(p.floors):
            P = np.asarray(poly, np.float64)[:, :2]
            for a, b in zip(P, np.roll(P, -1, axis=0)):
                n = max(2, int(np.linalg.norm(b - a) // 50.0) + 2)
                edge_pts.append(a[None, :] + (b - a)[None, :] * np.linspace(0, 1, n)[:, None])
            lo, hi = P.min(0), P.max(0)
            sel = (WX >= lo[0]) & (WX <= hi[0]) & (WY >= lo[1]) & (WY <= hi[1])
            if sel.any():
                r, c = np.nonzero(sel)
                ins = Fr.inside_polygon(WX[r, c], WY[r, c], [tuple(q) for q in P])
                blocked[r[ins], c[ins]] = True
    if edge_pts:
        d, _ = cKDTree(np.concatenate(edge_pts)).query(np.stack([WX.ravel(), WY.ravel()], 1))
        blocked |= (d <= margin_cm).reshape(WX.shape)
    return blocked


def walk_report(g, wc, parts, rng):
    """The forest the walk covers, and probe points for the editor's reach map: walkable woods away from trunks and
    structures (must be reached), water and the bluff outside the trail (must not)."""
    walk, cxm, cym, slope = wc["walk"], wc["cxm"], wc["cym"], wc["slope"]
    cls = g.cls_at(cxm, cym)
    woods = (cls == 1) | (cls == 2)
    region = in_regions(cxm, cym)
    i, j = g.ij(cxm, cym)
    ii, jj = np.clip(i, 0, g.H - 1), np.clip(j, 0, g.W - 1)
    wet = g.water[ii, jj]
    standable = region & ~wet & (slope <= L.MAX_WALK_SLOPE_DEG)
    a = CELL * CELL / 1e4
    rep = dict(region_ha=round(float(region.sum() * a), 2), region_woods_ha=round(float((region & woods).sum() * a), 2),
               standable_woods_ha=round(float((standable & woods).sum() * a), 2), walk_ha=round(float(walk.sum() * a), 2),
               walk_woods_ha=round(float((walk & woods).sum() * a), 2))
    rep["woods_covered_of_standable"] = round(rep["walk_woods_ha"] / max(rep["standable_woods_ha"], 1e-9), 3)
    # probes (world, on the walk floor): 40 walkable woods cells away from trunks and structures, 12 water, 8 steep
    W = g.frame.world(cxm, cym, wc["Z"][:-1, :-1])
    trunks = np.array([[t[0], t[1]] for t in g.trunks]) if g.trunks else np.zeros((0, 2))
    tt = cKDTree(trunks) if len(trunks) else None
    pick = np.argwhere(walk & woods & (ndi.binary_erosion(walk, iterations=2)) & ~structure_cells(W, parts))
    rng.shuffle(pick)
    reached = []
    for r, c in pick:
        Xw, Yw, Zw = W[r, c]
        if tt is not None and tt.query([Xw, Yw])[0] < 150.0:
            continue
        reached.append([float(Xw), float(Yw), float(Zw)])
        if len(reached) >= 40:
            break
    notr = []
    wet_cells = np.argwhere(region & wet)
    rng.shuffle(wet_cells)
    for r, c in wet_cells[:12]:
        notr.append([float(W[r, c, 0]), float(W[r, c, 1]), float(W[r, c, 2]), "water"])
    steep = np.argwhere(region & ~wet & ~walk & (slope > 32.0))
    rng.shuffle(steep)
    for r, c in steep[:8]:
        notr.append([float(W[r, c, 0]), float(W[r, c, 1]), float(W[r, c, 2]), "steep bank"])
    rep["probes_reached"] = reached
    rep["probes_not_reached"] = notr
    log(f"walk: {rep['walk_ha']} ha walkable, {rep['walk_woods_ha']} ha of it woods; of the regions' standable woods "
        f"{rep['woods_covered_of_standable'] * 100:.1f} % is walked; probes {len(reached)} in / {len(notr)} out")
    return rep


def walk_image(g, wc, floors_polys, stone_polys, profiles, path):
    from PIL import Image, ImageDraw
    walk, cxm, cym = wc["walk"], wc["cxm"], wc["cym"]
    S_ = 2
    img = np.zeros(walk.shape + (3,), np.uint8)
    cls = g.cls_at(cxm, cym)
    img[:] = (30, 30, 30)
    img[(cls == 1) | (cls == 2)] = (20, 50, 20)
    i, j = g.ij(cxm, cym)
    ii, jj = np.clip(i, 0, g.H - 1), np.clip(j, 0, g.W - 1)
    img[g.water[ii, jj]] = (30, 60, 200)
    img[wc["ok"] & ~walk] = (40, 95, 40)
    img[walk] = (60, 170, 60)
    edge = walk & ~ndi.binary_erosion(walk)
    img[edge] = (220, 40, 40)
    im = Image.fromarray(img).resize((walk.shape[1] * S_, walk.shape[0] * S_), Image.NEAREST)
    d = ImageDraw.Draw(im)
    x0, y0 = L.CORE[0], L.CORE[1]
    P = lambda x, y: ((x - x0) / CELL * S_, (y - y0) / CELL * S_)
    for name, pr in profiles.items():
        d.line([P(x, y) for x, y in pr["pts"]], fill=(255, 255, 255), width=1)
    for poly in floors_polys:
        cx, cy = g.frame.crop(np.array([p[0] for p in poly]), np.array([p[1] for p in poly]))
        d.polygon([P(a, b) for a, b in zip(cx, cy)], outline=(255, 255, 255))
    for b in L.BRIDGES:
        d.line([P(*b["a"]), P(*b["b"])], fill=(255, 0, 255), width=3)
    for poly in stone_polys:
        cx, cy = g.frame.crop(np.array([p[0] for p in poly]), np.array([p[1] for p in poly]))
        d.polygon([P(a, b) for a, b in zip(cx, cy)], fill=(0, 230, 255))
    for n, sp in L.SPOTS.items():
        px, py = P(*sp["dj"])
        d.ellipse([px - 5, py - 5, px + 5, py + 5], outline=(255, 255, 0), width=2)
        d.text((px + 7, py - 7), n, fill=(255, 255, 0))
    im.save(path)


# ====================================================================================================================
# the Stone Circle on the walk
# ====================================================================================================================

RING_RASTER_M = 0.25        # the ring check's raster (the walker's body is 40 cm across)
RING_BAND_M = (1.0, 4.0)    # the walk round the ring's outside: this far past the stones' line


def walk_floor_z(wc, cx, cy):
    """The walking floor's elevation (m) at crop points: the 2 m grid's own triangles, as collision() lays them."""
    Z = wc["Z"]
    fx = (np.asarray(cx, np.float64) - L.CORE[0]) / CELL
    fy = (np.asarray(cy, np.float64) - L.CORE[1]) / CELL
    c = np.clip(np.floor(fx).astype(np.int64), 0, Z.shape[1] - 2)
    r = np.clip(np.floor(fy).astype(np.int64), 0, Z.shape[0] - 2)
    u, v = fx - c, fy - r
    a, b, cc, d = Z[r, c], Z[r, c + 1], Z[r + 1, c + 1], Z[r + 1, c]
    return np.where(u >= v, a + u * (b - a) + v * (cc - b), a + v * (d - a) + u * (cc - d))


def ring_report(g, wc, parts, trunks, profiles, path):
    """The Stone Circle on the walk (the user: walkable round its outside, its inside reachable), on a 25 cm raster over
    the ring and 8 m round it. A raster point is free where its 2 m cell is walked and no wall (the stones, the stage's
    and every structure's walls, trunks, poles, tents) nor floor prism (a deck stands on the ground like a wall) comes
    within the walker's 20 cm. From the crowd 14 m in front of the Main Stage's DJ it floods the free points: how much
    of the ring's inside it reaches and whether it gets out through the gaps; then, within the band RING_BAND_M past the
    stones' line alone, whether the free way goes all the way round (every 5 degrees of the ring). Also the reach map's
    probes for the ring (5 inside, 8 round the outside) and site_top.png (the ring from above) at path."""
    sc = L.STONE_CIRCLE
    R = RING_RASTER_M
    ring = np.array([L.ring_point(t) for t in range(0, 360, 2)])
    x0, y0 = ring.min(0) - 8.0
    x1, y1 = ring.max(0) + 8.0
    xs = np.arange(x0, x1, R) + R / 2
    ys = np.arange(y0, y1, R) + R / 2
    CX, CY = np.meshgrid(xs, ys)
    walk = wc["walk"]
    ci = np.clip(((CY - L.CORE[1]) // CELL).astype(np.int64), 0, walk.shape[0] - 1)
    cj = np.clip(((CX - L.CORE[0]) // CELL).astype(np.int64), 0, walk.shape[1] - 1)
    walked = walk[ci, cj]
    polys = []
    for p in parts.values():
        polys += [w[0] for w in p.walls] + [f[0] for f in p.floors]
    polys += [S.octa_poly(X, Y, rad) for X, Y, _, rad in trunks]
    blocked = np.zeros(CX.shape, bool)
    for poly in polys:
        P = np.asarray(poly, np.float64)[:, :2]
        pcx, pcy = g.frame.crop(P[:, 0], P[:, 1])
        j0, j1 = max(int((pcx.min() - x0) / R) - 1, 0), min(int((pcx.max() - x0) / R) + 2, CX.shape[1])
        i0, i1 = max(int((pcy.min() - y0) / R) - 1, 0), min(int((pcy.max() - y0) / R) + 2, CX.shape[0])
        if j0 >= j1 or i0 >= i1:
            continue
        blocked[i0:i1, j0:j1] |= Fr.inside_polygon(CX[i0:i1, j0:j1], CY[i0:i1, j0:j1], list(zip(pcx, pcy)))
    free = walked & ~ndi.binary_dilation(blocked, iterations=1)
    a, b = L.ring_uv(CX, CY)
    r = L.ring_radius(CX, CY)
    tpar = np.degrees(np.arctan2(b / sc["rb"], a / sc["ra"])) % 360.0
    past = (r - 1.0) * np.hypot(sc["ra"] * np.cos(np.radians(tpar)), sc["rb"] * np.sin(np.radians(tpar)))
    inside = past < -0.8
    band = (past > RING_BAND_M[0]) & (past < RING_BAND_M[1])
    sp = L.SPOTS["Main"]
    f = (math.cos(math.radians(sp["facing"])), -math.sin(math.radians(sp["facing"])))
    crowd = (sp["dj"][0] + f[0] * 14.0, sp["dj"][1] + f[1] * 14.0)

    def nearest_free(px, py, mask, need=2):
        ok = ndi.binary_erosion(mask, iterations=need) if need else mask
        cand = np.argwhere(ok)
        if not len(cand):
            return None
        d2 = (CX[cand[:, 0], cand[:, 1]] - px) ** 2 + (CY[cand[:, 0], cand[:, 1]] - py) ** 2
        k = int(np.argmin(d2))
        return (int(cand[k, 0]), int(cand[k, 1])) if d2[k] <= 9.0 else None

    lab, _ = ndi.label(free)
    s0 = nearest_free(*crowd, free)
    comp = (lab == lab[s0]) if s0 else np.zeros(CX.shape, bool)
    inside_free = inside & free
    inside_frac = float((comp & inside).sum() / max(inside_free.sum(), 1))
    out_reached = bool((comp & band).any())
    bl, nb = ndi.label(free & band)
    sizes = ndi.sum(np.ones(CX.shape), bl, index=np.arange(1, nb + 1)) if nb else np.zeros(0)
    loop = (bl == (int(np.argmax(sizes)) + 1)) if nb else np.zeros(CX.shape, bool)
    sectors = int(len(np.unique((tpar[loop] // 5).astype(np.int64)))) if loop.any() else 0
    band_frac = float((free & band).sum() / max(band.sum(), 1))
    line = np.abs(past) < 0.3
    _, ways = ndi.label(free & line)
    # probes (world, on the walking floor): free points 50 cm clear of any wall, in the flooded walk
    probes = []
    targets = [("the Stone Circle's middle", sc["center"], comp & inside),
               ("the crowd 15 m in front of the Main Stage", (sp["dj"][0] + f[0] * 15.0, sp["dj"][1] + f[1] * 15.0), comp & inside),
               ("the ring's inside by the Flame Stone", L.ring_point(180.0, 0.85), comp & inside),
               ("the ring's inside, north", L.ring_point(270.0, 0.8), comp & inside),
               ("the ring's inside, south", L.ring_point(90.0, 0.8), comp & inside)]
    for t in range(0, 360, 45):
        rad = math.hypot(sc["ra"] * math.cos(math.radians(t)), sc["rb"] * math.sin(math.radians(t)))
        targets.append((f"outside the ring at {t} degrees", L.ring_point(float(t), 1.0 + 2.5 / rad), comp & band))
    missing = []
    for what, (px, py), mask in targets:
        k = nearest_free(px, py, mask)
        if k is None:
            missing.append(what)
            continue
        qx, qy = float(CX[k]), float(CY[k])
        W = g.frame.world(qx, qy, float(walk_floor_z(wc, qx, qy)))
        probes.append([round(float(W[0]), 1), round(float(W[1]), 1), round(float(W[2]), 1), what])
    rep = dict(inside_reached=round(inside_frac, 3), out_through_gaps=out_reached, band_free=round(band_frac, 3),
               band_loop_sectors=sectors, ways_through_line=int(ways), probes=probes, probes_missing=missing)
    log(f"Stone Circle walk: the crowd reaches {inside_frac * 100:.1f} % of the ring's free inside, "
        f"{'gets out through its gaps' if out_reached else 'NOT out of the ring'}; {int(ways)} ways through the stones' "
        f"line; the band {RING_BAND_M[0]:.0f}-{RING_BAND_M[1]:.0f} m outside the stones is {band_frac * 100:.1f} % free, "
        f"its free way round covers {sectors} of 72 sectors of 5 degrees; probes {len(probes)}"
        + (f", MISSING {missing}" if missing else ""))
    if inside_frac < 0.95 or not out_reached or sectors < 72 or missing:
        log("WARNING the Stone Circle's walk check failed (above)")
    # site_top.png: the ring from above, 8 px a metre
    from PIL import Image, ImageDraw
    img = np.zeros(CX.shape + (3,), np.uint8)
    img[:] = (35, 35, 35)
    img[walked] = (45, 80, 45)
    img[free] = (70, 130, 70)
    img[free & comp & inside] = (90, 150, 175)
    img[loop] = (60, 170, 200)
    img[blocked] = (230, 200, 60)
    im = Image.fromarray(img).resize((CX.shape[1] * 2, CX.shape[0] * 2), Image.NEAREST)
    d = ImageDraw.Draw(im)
    Pp = lambda x, y: ((x - x0) / R * 2, (y - y0) / R * 2)
    for pr in profiles.values():
        d.line([Pp(x, y) for x, y in pr["pts"]], fill=(200, 170, 120), width=2)
    d.line([Pp(*q) for q in ring] + [Pp(*ring[0])], fill=(255, 255, 255), width=1)
    for X, Y, Z, what in probes:
        qx, qy = g.frame.crop(X, Y)
        px, py = Pp(float(qx), float(qy))
        d.ellipse([px - 4, py - 4, px + 4, py + 4], outline=(255, 0, 255), width=2)
    px, py = Pp(*sp["dj"])
    d.ellipse([px - 6, py - 6, px + 6, py + 6], outline=(255, 60, 60), width=3)
    d.line([(px, py), (px + f[0] * 80, py + f[1] * 80)], fill=(255, 60, 60), width=3)
    d.text((6, 6), "BIG DUB: the Stone Circle (white line) round the Main Stage (red: the DJ, facing) and its crowd; "
           "yellow: walls and decks; blue: the flooded inside; cyan: the free way round outside; magenta: probes",
           fill=(255, 255, 255))
    im.save(path)
    return rep


# ====================================================================================================================
# the crowds
# ====================================================================================================================

# where each stage's dancers stand, in its frame (u metres toward the crowd from the DJ, |v| metres across), and how
# full it is: dense at the front, thinning toward the back
CROWD_ZONES = {
    "Main": [(8.6, 46.0, 30.0, lambda u: np.clip(1.02 - (u - 8.6) / 34.0, 0.12, 0.92))],
    "Pavilion": [(4.6, 18.0, 3.7, lambda u: np.clip((u - 4.6) / 4.0, 0.25, 0.6)), (20.5, 33.0, 9.0, lambda u: np.full(np.shape(u), 0.22))],
    "NewCamp": [(5.4, 27.0, 12.0, lambda u: np.clip(0.95 - (u - 5.4) / 26.0, 0.15, 0.85))],
}


def place_crowds(g, parts, spots, trunks):
    """The dancers (bd_crowd.py), 1 m apart at their densest, facing their stage: inside the Stone Circle in front of
    the Main Stage's barrier, on the Pavilion's floor and in front of its open end, in New Camp's field. Clear of every
    structure's walls and floors (pillars, barriers, the FOH, the stones), of trunks and of the water; on the hall's floor
    in the Pavilion. Their own random stream. No walls: the walk passes through them."""
    rng = np.random.default_rng(6101)
    polys = [w[0] for p in parts.values() for w in p.walls] + [f[0] for k, p in parts.items() if k not in ("Pavilion",)
                                                                for f in p.floors]
    boxes = [(np.asarray(q, np.float64).min(0) - 60.0, np.asarray(q, np.float64).max(0) + 60.0) for q in polys]
    ttree = cKDTree(np.array([[t[0], t[1]] for t in trunks])) if trunks else None
    rows = {"SM_BdCrowdUp": [], "SM_BdCrowdDown": []}
    counts = {}
    for name, zones in CROWD_ZONES.items():
        o, yaw = parts[name].points["frame"]
        o = np.asarray(o, np.float64)
        fwd, right = M.basis_from_yaw(yaw)
        n0 = sum(len(v) for v in rows.values())
        for u0, u1, vh, dens in zones:
            us = np.arange(u0, u1, 0.95)
            vs = np.arange(-vh, vh + 0.01, 0.95)
            U, Vv = np.meshgrid(us, vs)
            U = (U + rng.uniform(-0.3, 0.3, U.shape)).ravel()
            Vv = (Vv + rng.uniform(-0.3, 0.3, Vv.shape)).ravel()
            keep = rng.uniform(0, 1, U.shape) < dens(U)
            X = o[0] + (U * fwd[0] + Vv * right[0]) * 100.0
            Y = o[1] + (U * fwd[1] + Vv * right[1]) * 100.0
            cx, cy = g.frame.crop(X, Y)
            if name == "Main":
                keep &= L.ring_radius(cx, cy) < 0.9
            i, j = g.ij(cx, cy)
            ii, jj = np.clip(i, 0, g.H - 1), np.clip(j, 0, g.W - 1)
            keep &= ~g.water[ii, jj]
            if ttree is not None:
                keep &= ttree.query(np.stack([X, Y], 1))[0] > 75.0
            vx, vy = crowd_view_point(parts)
            keep &= np.hypot(X - vx, Y - vy) > 110.0
            for k in np.nonzero(keep)[0]:
                if any(lo[0] <= X[k] <= hi[0] and lo[1] <= Y[k] <= hi[1] and
                       Fr.inside_polygon(np.array([X[k]]), np.array([Y[k]]), [tuple(q) for q in np.asarray(poly)[:, :2]])[0]
                       for (lo, hi), poly in zip(boxes, polys)) or \
                   poly_contains_any([q for q in polys if np.ptp(np.asarray(q)[:, 0]) < 300 and np.ptp(np.asarray(q)[:, 1]) < 300],
                                     np.array([X[k]]), np.array([Y[k]]), 45.0)[0]:
                    continue
                inside_hall = name == "Pavilion" and U[k] < 18.6
                z = parts["Pavilion"].points["hall_floor_z"] if inside_hall else float(g.zworld(X[k], Y[k]))
                face = math.degrees(math.atan2(o[1] - Y[k], o[0] - X[k])) + rng.uniform(-22.0, 22.0)
                sc = rng.uniform(0.9, 1.08)
                mesh = "SM_BdCrowdUp" if rng.uniform(0, 1) < 0.38 else "SM_BdCrowdDown"
                rows[mesh].append([float(X[k]), float(Y[k]), float(z) - 2.0, float(face), float(sc), float(sc), float(sc)])
        counts[name] = sum(len(v) for v in rows.values()) - n0
    log(f"crowds: {counts} ({len(rows['SM_BdCrowdUp'])} with hands up)")
    return rows, counts


# ====================================================================================================================
# the pictures' cameras (Scripts/render/bigdub_views.py reads them from site.json "views")
# ====================================================================================================================

EYE_CM = 165.0
CROWD_VIEW_M = 21.0          # the Stone Circle from the crowd: this far in front of the Main Stage's DJ, among the dancers


def crowd_view_point(parts):
    o, yaw = parts["Main"].points["frame"]
    fwd, _ = M.basis_from_yaw(yaw)
    return float(o[0] + fwd[0] * CROWD_VIEW_M * 100.0), float(o[1] + fwd[1] * CROWD_VIEW_M * 100.0)


def view_points(g, wc, parts, spots, trunks):
    """Eye points for the extra pictures, on the walk and clear of trunks and walls by 1.5 m: each stage from about 50 m
    in front of it (the nearest such point to its axis, within 50 degrees), the Stone Circle from the crowd, and a walk
    between the stages on the Big Bottom's path, the woods dark and the path lights leading on."""
    walls = [w[0] for p in parts.values() for w in p.walls]
    centres = [np.asarray(q, np.float64)[:, :2].mean(0) for q in walls]
    radii = [float(np.max(np.linalg.norm(np.asarray(q, np.float64)[:, :2] - c, axis=1))) for q, c in zip(walls, centres)]
    wtree = cKDTree(np.array(centres))
    ttree = cKDTree(np.array([[t[0], t[1]] for t in trunks]))
    maxr = max(radii)

    def clear(X, Y):
        cx, cy = g.frame.crop(X, Y)
        r = int((cy - L.CORE[1]) // CELL)
        c = int((cx - L.CORE[0]) // CELL)
        if not (0 <= r < wc["walk"].shape[0] and 0 <= c < wc["walk"].shape[1]) or not wc["walk"][r, c]:
            return False
        if ttree.query([X, Y])[0] < 150.0:
            return False
        return all(np.linalg.norm(centres[k] - (X, Y)) > radii[k] + 400.0 for k in wtree.query_ball_point([X, Y], maxr + 400.0))

    def sight(X, Y, tx, ty):
        """Nothing right in front of the eye: no wall (a stone, a tent, a post) within 70 cm of the line to the target
        over its first 8 m, no trunk within 1.1 m of it over its first 15 m (further on, the scene is what it shows)."""
        dist = math.hypot(tx - X, ty - Y)
        for t in np.linspace(0.0, min(1.0, 1500.0 / dist), 50):
            px, py = X + (tx - X) * t, Y + (ty - Y) * t
            if ttree.query([px, py])[0] < 110.0:
                return False
            if t * dist <= 800.0 and any(np.linalg.norm(centres[k] - (px, py)) < radii[k] + 70.0
                                         for k in wtree.query_ball_point([px, py], maxr + 70.0)):
                return False
        return True

    def eye_at(X, Y):
        cx, cy = g.frame.crop(X, Y)
        return [round(X, 1), round(Y, 1), round(float(g.frame.world(cx, cy, walk_floor_z(wc, cx, cy))[2]) + EYE_CM, 1)]

    views = {}
    for name in L.SPOT_ORDER:
        o, yaw = parts[name].points["frame"]
        target = [float(o[0]), float(o[1]), float(o[2]) + 450.0]
        best = None
        for dist in (50.0, 47.0, 53.0, 44.0, 56.0):
            for off in sorted(range(-50, 51, 5), key=abs):
                a = math.radians(yaw + off)
                X, Y = o[0] + math.cos(a) * dist * 100.0, o[1] + math.sin(a) * dist * 100.0
                if clear(X, Y) and sight(X, Y, o[0], o[1]):
                    best = (X, Y, off, dist)
                    break
            if best:
                break
        if best:
            views[f"{name.lower()}_50m"] = dict(eye=eye_at(best[0], best[1]), look=target, off_axis_deg=best[2], dist_m=best[3])
    X, Y = crowd_view_point(parts)
    o, yaw = parts["Main"].points["frame"]
    views["circle_crowd"] = dict(eye=eye_at(X, Y), look=[float(o[0]), float(o[1]), float(o[2]) + 420.0])
    # the walk: the Big Bottom's path between the Pavilion and New Camp, heading south toward the Rainbow Bridge
    pr = [p for p in L.PATHS if p["name"] == "bottom_path"][0]
    pts, s_ = Fr.resample(pr["pts"], 1.0)
    k0, k1 = int(np.searchsorted(s_, 205.0)), int(np.searchsorted(s_, 235.0))
    W0 = g.frame.world(pts[k0][0], pts[k0][1], 0.0)
    W1 = g.frame.world(pts[k1][0], pts[k1][1], 0.0)
    e = eye_at(float(W0[0]), float(W0[1]))
    views["walk"] = dict(eye=e, look=[round(float(W1[0]), 1), round(float(W1[1]), 1), e[2] + 150.0])
    # the Rainbow Bridge over the misty creek, from the Big Bottom's path 9 m short of it
    br = [b_ for b_ in L.BRIDGES if b_["name"] == "rainbow"][0]
    Wb0 = g.frame.world(br["a"][0] + 3.0, br["a"][1] - 9.0, 0.0)
    Wb1 = g.frame.world((br["a"][0] + br["b"][0]) / 2, (br["a"][1] + br["b"][1]) / 2, 0.0)
    e = eye_at(float(Wb0[0]), float(Wb0[1]))
    views["bridge"] = dict(eye=e, look=[round(float(Wb1[0]), 1), round(float(Wb1[1]), 1), e[2] + 250.0])
    # the Main Stage DJ's eye looking level over the crowd (the standard picture looks 20 degrees down at the decks)
    o, yaw = parts["Main"].points["frame"]
    fwd, _ = M.basis_from_yaw(yaw)
    views["main_level"] = dict(eye=[float(o[0]), float(o[1]), float(o[2]) + EYE_CM],
                               look=[float(o[0] + fwd[0] * 3000.0), float(o[1] + fwd[1] * 3000.0), float(o[2]) + 520.0])
    desc = ", ".join(k + " " + str(v.get("off_axis_deg", 0)) + " deg" for k, v in views.items())
    log(f"views: {desc}")
    return views


# ====================================================================================================================
# the festival's dressing (bd_decor.py)
# ====================================================================================================================

def _free_spot(g, X, Y, trunk_tree, avoid, clear_trunk=300.0, clear_avoid=450.0, clear_path=3.0, max_slope=10.0):
    """True where a prop may stand: on flat dry ground off the paths, clear of trunks and of the points in avoid."""
    cx, cy = g.frame.crop(X, Y)
    i, j = g.ij(cx, cy)
    if not (0 <= i < g.H and 0 <= j < g.W) or g.water[i, j] or g._wd[i, j] < 4.0 or g._pathdist[i, j] < clear_path:
        return False
    if g.slope_deg[i, j] > max_slope or not in_regions(np.array([cx]), np.array([cy]))[0]:
        return False
    if trunk_tree is not None and trunk_tree.query([X, Y])[0] < clear_trunk:
        return False
    return all(math.hypot(X - ax, Y - ay) >= clear_avoid for ax, ay in avoid)


def build_decor(g, parts, spots, profiles, trunks, glow):
    """The dressing, from its own random stream: the stages' neon signs, jellyfish and spiky flowers over the crowds,
    flags, campfires in the camps, mushrooms in the Big Bottom, lantern planets along the paths, wisteria in the
    Pavilion. Returns the part and the warm lamps it adds to the light map."""
    rng = np.random.default_rng(7101)
    part = S.Part()
    lamps = []
    ttree = cKDTree(np.array([[t[0], t[1]] for t in trunks])) if trunks else None
    tents = [(float(np.mean(np.asarray(w[0])[:, 0])), float(np.mean(np.asarray(w[0])[:, 1]))) for w in parts["tents"].walls]
    # the signs: over the Main Stage's front truss, in the Pavilion's ESE gable, on New Camp's truss
    for name, local, hcm in (("Main", (365.0, 0.0, 1085.0), 72.0), ("Pavilion", (1905.0, 0.0, 470.0), 50.0),
                             ("NewCamp", (-415.0, 0.0, 800.0), 66.0)):
        o, yaw = parts[name].points["frame"]
        P = M.place(np.array([local]), o, yaw)[0]
        D.neon_sign(part, glow, {"Main": "MAIN STAGE", "Pavilion": "PAVILION", "NewCamp": "NEW CAMP"}[name], P, yaw, hcm, name)
    # jellyfish and spiky flowers over the Main Stage's crowd, jellyfish over New Camp's
    blues = [((0.20, 0.50, 1.00), 5), ((0.20, 0.50, 1.00), 5), ((1.00, 0.35, 0.75), 7), ((0.20, 0.90, 0.90), 4)]
    o, yaw = parts["Main"].points["frame"]
    fwd, right = M.basis_from_yaw(yaw)
    o = np.asarray(o, np.float64)
    for k, (u, v) in enumerate([(14, -9), (17, 6), (21, -2), (24, 11), (26, -13), (29, 3), (32, -7), (35, 9), (19, 15),
                                (23, -17)]):
        X, Y = o[0] + (u * fwd[0] + v * right[0]) * 100.0, o[1] + (u * fwd[1] + v * right[1]) * 100.0
        z = float(g.zworld(X, Y)) + rng.uniform(800.0, 1150.0)
        rgb, pal = blues[k % len(blues)]
        D.jellyfish(part, glow, (X, Y, z), rng.uniform(85.0, 125.0), rgb, pal, rng)
    for u, v in [(16, -2), (20, 10), (27, -10), (31, 13), (36, -1), (25, 1)]:
        X, Y = o[0] + (u * fwd[0] + v * right[0]) * 100.0, o[1] + (u * fwd[1] + v * right[1]) * 100.0
        D.spiky_flower(part, glow, (X, Y, float(g.zworld(X, Y)) + rng.uniform(950.0, 1300.0)), rng.uniform(70.0, 100.0), rng)
    o, yaw = parts["NewCamp"].points["frame"]
    fwd, right = M.basis_from_yaw(yaw)
    o = np.asarray(o, np.float64)
    for k, (u, v) in enumerate([(9, -6), (13, 5), (17, -9), (21, 2), (25, 9)]):
        X, Y = o[0] + (u * fwd[0] + v * right[0]) * 100.0, o[1] + (u * fwd[1] + v * right[1]) * 100.0
        rgb, pal = blues[(k + 1) % len(blues)]
        D.jellyfish(part, glow, (X, Y, float(g.zworld(X, Y)) + rng.uniform(700.0, 950.0)), rng.uniform(75.0, 105.0), rgb, pal, rng)
    # flags: round the inside of the Stone Circle by the crowd, beside New Camp's field and the Pavilion's open end
    nflags = 0
    for t in np.arange(25.0, 336.0, 22.0):
        if abs(((t + 180.0) % 360.0) - 180.0) < 40.0 or abs(t - 180.0) < 28.0:   # not behind the stage, not by the Flame Stone
            continue
        cx, cy = L.ring_point(float(t), 0.86)
        W = g.frame.world(cx, cy, 0.0)
        if g._pathdist[g.ij(cx, cy)] < 2.0:
            continue
        D.flag(part, float(W[0]), float(W[1]), float(g.zworld(W[0], W[1])), rng.uniform(0, 360), D.FLAG_COLOURS[nflags % 6], rng)
        nflags += 1
    for name, pts in (("NewCamp", [(8, -15), (16, -15), (24, -15), (8, 15), (16, 15), (24, 15)]),
                      ("Pavilion", [(21, -8), (21, 8), (27, -10), (27, 10)])):
        o, yaw = parts[name].points["frame"]
        fwd, right = M.basis_from_yaw(yaw)
        for u, v in pts:
            X, Y = o[0] + (u * fwd[0] + v * right[0]) * 100.0, o[1] + (u * fwd[1] + v * right[1]) * 100.0
            if _free_spot(g, X, Y, ttree, [], 120.0, 0.0, 1.5, 20.0):
                D.flag(part, X, Y, float(g.zworld(X, Y)), yaw + 90.0, D.FLAG_COLOURS[nflags % 6], rng)
                nflags += 1
    # campfires in the camps, on open flat ground clear of the tents and trees
    fires = []
    for camp, want in (("bigbottom_west", 2), ("bigbottom_east", 2), ("white_pines", 2), ("newcamp", 2), ("camp_central", 1)):
        x0, y0, x1, y1 = next(c["rect"] for c in L.CAMPS if c["name"] == camp)
        for _ in range(400):
            if sum(1 for f in fires if f[2] == camp) >= want:
                break
            cx, cy = rng.uniform(x0, x1), rng.uniform(y0, y1)
            W = g.frame.world(cx, cy, 0.0)
            if _free_spot(g, float(W[0]), float(W[1]), ttree, tents + [(f[0], f[1]) for f in fires], 420.0, 650.0, 4.0):
                fires.append((float(W[0]), float(W[1]), camp))
    for X, Y, _ in fires:
        D.campfire(part, glow, X, Y, float(g.zworld(X, Y)), rng)
        cx, cy = g.frame.crop(X, Y)
        lamps.append((float(cx), float(cy), 9.0, 1.7))
    # the mushrooms: a cluster off the Big Bottom's paths where the loop leaves the main path
    shrooms = []
    for _ in range(600):
        if len(shrooms) >= 7:
            break
        cx, cy = 1090.0 + rng.uniform(-30, 30), 300.0 + rng.uniform(-28, 28)
        W = g.frame.world(cx, cy, 0.0)
        if _free_spot(g, float(W[0]), float(W[1]), ttree, tents + [(m_[0], m_[1]) for m_ in shrooms] + [(f[0], f[1]) for f in fires],
                      260.0, 420.0, 3.5, 16.0):
            shrooms.append((float(W[0]), float(W[1])))
    for k, (X, Y) in enumerate(shrooms):
        big = k < 4
        D.mushroom(part, glow, X, Y, float(g.zworld(X, Y)), rng.uniform(200.0, 300.0) if big else rng.uniform(110.0, 160.0),
                   rng.uniform(120.0, 165.0) if big else rng.uniform(70.0, 95.0), rng)
        cx, cy = g.frame.crop(X, Y)
        lamps.append((float(cx), float(cy), 6.5, 0.45 if big else 0.25))
    # lantern planets along the festooned paths, hanging over their edges
    nl = 0
    colours = [((1.0, 0.35, 0.65), 7), ((1.0, 0.55, 0.15), 1), ((0.20, 0.85, 1.0), 4), ((1.0, 0.85, 0.30), 2)]
    for name, pr in profiles.items():
        if not pr["festoon"]:
            continue
        pts, s_ = Fr.resample(pr["pts"], 1.0)
        for t in np.arange(13.0, s_[-1] - 5.0, 26.0):
            i = min(int(np.searchsorted(s_, t)), len(pts) - 2)
            d = pts[i + 1] - pts[i]
            d /= max(np.linalg.norm(d), 1e-6)
            side = np.array([-d[1], d[0]]) * (1 if nl % 2 else -1)
            q = pts[i] + side * (pr["width"] / 2 + rng.uniform(0.8, 2.2))
            if L.ring_radius(q[0], q[1]) < 1.15:
                continue
            W = g.frame.world(q[0], q[1], 0.0)
            z = float(g.zworld(W[0], W[1])) + rng.uniform(380.0, 620.0)
            rgb, pal = colours[nl % 4]
            D.lantern_sphere(part, glow, (float(W[0]), float(W[1]), z), rng.uniform(24.0, 38.0), rgb, pal, rng)
            lamps.append((float(q[0]), float(q[1]), 4.5, 0.22))
            nl += 1
    # the Flame Stone: its floodlights' warm pool
    fs = parts["stones"].points.get("flame_stone")
    if fs:
        cx, cy = g.frame.crop(fs[0], fs[1])
        lamps.append((float(cx), float(cy), 5.5, 1.6))
    log(f"decor: 3 signs, 15 jellyfish, 6 flowers, {nflags} flags, {len(fires)} campfires, {len(shrooms)} mushrooms, "
        f"{nl} lantern planets; {len(part.walls)} walls")
    return part, lamps


# ====================================================================================================================
# the night's light: path lights, the light map, the structures' heights, the glow
# ====================================================================================================================

PATH_LIGHT_STEP_M = 9.0        # a path light every 9 m along every path, on alternate sides
PATH_LIGHT_POST_CM = 75.0


def place_path_lights(g, profiles, parts):
    """Low lanterns on posts along every path, on alternate sides, just off its edge (crop points and their ground z):
    the walker's way between the stages at night. None inside the Stone Circle (the stage lights it), on the bridges'
    landings, in the water or on the stages' structures."""
    struct_polys = []
    for p in parts.values():
        struct_polys += [f[0] for f in p.floors] + [w[0] for w in p.walls if np.ptp(np.asarray(w[0])[:, 0]) > 60 or np.ptp(np.asarray(w[0])[:, 1]) > 60]
    ends = [b[k] for b in L.BRIDGES for k in ("a", "b")]
    out = []
    for name, pr in profiles.items():
        pts, s = Fr.resample(pr["pts"], 0.5)
        n = int(s[-1] // PATH_LIGHT_STEP_M)
        for k in range(1, n + 1):
            t = k * PATH_LIGHT_STEP_M
            i = min(int(np.searchsorted(s, t)), len(pts) - 2)
            p = pts[i]
            d = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
            d = d / max(np.linalg.norm(d), 1e-6)
            side = np.array([-d[1], d[0]]) * (1 if k % 2 == 0 else -1)
            q = p + side * (pr["width"] / 2 + 0.45)
            if L.ring_radius(q[0], q[1]) < 1.08 or any(math.hypot(q[0] - e[0], q[1] - e[1]) < 5.0 for e in ends):
                continue
            ii, jj = g.ij(q[0], q[1])
            if g.water[ii, jj] or g._wd[ii, jj] < 2.0:
                continue
            W = g.frame.world(q[0], q[1], 0.0)
            if poly_contains_any(struct_polys, np.array([W[0]]), np.array([W[1]]), 120.0)[0]:
                continue
            out.append((float(q[0]), float(q[1]), float(g.zworld(W[0], W[1])), name))
    log(f"path lights: {len(out)}, every {PATH_LIGHT_STEP_M:.0f} m along {len(profiles)} paths")
    return out


def build_path_lights(g, lights, glow):
    """Each path light: a dark wooden post, a lantern head with warm glass (M_BdLights, steady) and its halo; a wall
    round the post (the walk's posts are walls, as the festoon poles are)."""
    part = S.Part()
    m = part.mesh("SM_BdPathLights")
    for cx, cy, z, _ in lights:
        W = g.frame.world(cx, cy, 0.0)
        X, Y = float(W[0]), float(W[1])
        V, F, UV = M.box(8, 8, PATH_LIGHT_POST_CM + 20, (X, Y, z + (PATH_LIGHT_POST_CM + 20) / 2 - 20))
        m.add(V, F, S.TIMBER_DARK, UV, S.SURF)
        top = z + PATH_LIGHT_POST_CM
        V, F, UV = M.box(16, 16, 3, (X, Y, top + 19.5))
        m.add(V, F, S.BLACK, UV, S.SURF)
        V, F, UV = M.box(13, 13, 17, (X, Y, top + 9.5))
        m.add(V, F, S.L(0.0, 1.0, 0.0, (X * 0.00011) % 1.0), UV, S.LIGHT, S.light_aux(1.0, M.LIGHT_WARM))
        S.glow_halo(glow, [(X, Y, top + 9.5)], 34.0, S.glow_col(0.0, 1.0, 0.0, 0.0), 0.9)
        part.walls.append((S.octa_poly(X, Y, 9.0), z - 10.0, z + 250.0))
    return part


def fill_heights(mesh, ground, scale=1.0, floor_z=None):
    """M_BdSurface's UV1.x for every Surface vertex of a mesh: its height over the ground (m) at its XY, times scale;
    or over floor_z (world cm) where given (the Pavilion's hall: what is under its roof is lit by its strings)."""
    if "Surface" not in mesh.materials or mesh.triangles == 0:
        return
    V, F, C, UV, Mi = mesh.arrays()
    X = mesh.aux_arrays().copy()
    sel = np.zeros(len(V), bool)
    sel[F[Mi == mesh.slot("Surface")].ravel()] = True
    base = ground(V[sel, 0], V[sel, 1]) if floor_z is None else np.full(int(sel.sum()), float(floor_z))
    X[0, sel, 0] = np.maximum(V[sel, 2] - base, 0.0) / 100.0 * scale
    mesh._x = [X]


LMAP_RES = 0.5                     # the light map: m a pixel
LMAP_W, LMAP_H = 1024, 2048        # 512 x 1024 m over the core (crop x 900..1380, y -20..800)
LMAP_X0, LMAP_Y0 = 884.0, -122.0   # crop of its north-west corner
WARM_MAX = 2.5                     # the warm channel's top (R = sqrt(warm / WARM_MAX))


def _splat(field, x, y, r, inten):
    """A lamp's pool of light on the light map: crop (x, y), radius r m, its peak inten: bright in the middle, soft to
    its edge."""
    j0 = max(int((x - r - LMAP_X0) / LMAP_RES), 0)
    j1 = min(int((x + r - LMAP_X0) / LMAP_RES) + 2, LMAP_W)
    i0 = max(int((y - r - LMAP_Y0) / LMAP_RES), 0)
    i1 = min(int((y + r - LMAP_Y0) / LMAP_RES) + 2, LMAP_H)
    if j0 >= j1 or i0 >= i1:
        return
    xs = LMAP_X0 + (np.arange(j0, j1) + 0.5) * LMAP_RES
    ys = LMAP_Y0 + (np.arange(i0, i1) + 0.5) * LMAP_RES
    d = np.hypot(xs[None, :] - x, ys[:, None] - y) / r
    f = np.clip(1.0 - d * d, 0, 1) ** 2 * (0.35 + 0.65 / (1.0 + (d * r / 1.2) ** 2))
    field[i0:i1, j0:j1] += inten * f


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


STAGE_BOXES = {"Pavilion": (-3.0, 46.0, 13.0), "NewCamp": (-6.0, 32.0, 17.0)}   # u from, u to, |v| (m, the stage's frame)


def stage_centres(spots):
    """Where each stage's light is centred (crop): the Main Stage's in the middle of the Stone Circle, the others in
    their crowds."""
    out = {"Main": tuple(L.STONE_CIRCLE["center"])}
    for name, ahead in (("Pavilion", 12.0), ("NewCamp", 12.0)):
        sp = spots[name]
        fx, fy = math.cos(math.radians(L.SPOTS[name]["facing"])), -math.sin(math.radians(L.SPOTS[name]["facing"]))
        out[name] = (sp["crop"][0] + fx * ahead, sp["crop"][1] + fy * ahead)
    return out


def build_light_map(g, profiles, spots, lamps):
    """T_BdLight: the festival's light, baked, by world XY (1024 x 2048, 0.5 m a pixel over the core), read by every
    material (build_bigdub.py):
      R  the warm lamps' light: path lights, festoons, lantern trees, lit tents, the Pavilion's strings, the footbridge
         (sqrt of its share of WARM_MAX)
      G  the stages' show-coloured light: the whole Stone Circle, the Pavilion's hall and Camp Central, New Camp's
         field, and a spill into the woods round each (sqrt); the material falls each off with height
      B  the paths (the ground takes their dirt)
      A  the woods (the moon doesn't reach under the canopy; the ground takes leaf litter instead of grass)
    Beyond its edge the material reads no light and woods. lamps: (crop x, y, radius m, intensity)."""
    os.makedirs(TEX_DIR, exist_ok=True)
    xs = LMAP_X0 + (np.arange(LMAP_W) + 0.5) * LMAP_RES
    ys = LMAP_Y0 + (np.arange(LMAP_H) + 0.5) * LMAP_RES
    CX, CY = np.meshgrid(xs, ys)
    warm = np.zeros(CX.shape, np.float64)
    for x, y, r, inten in lamps:
        _splat(warm, x, y, r, inten)
    # the stages: the Main Stage lights its whole ring; the others their hall and crowd field; and a spill round each
    stage = _smoothstep(1.50, 0.82, L.ring_radius(CX, CY))
    for name, (u0, u1, vh) in STAGE_BOXES.items():
        sp = spots[name]
        fx, fy = math.cos(math.radians(L.SPOTS[name]["facing"])), -math.sin(math.radians(L.SPOTS[name]["facing"]))
        dx, dy = CX - sp["crop"][0], CY - sp["crop"][1]
        u = dx * fx + dy * fy
        v = np.abs(-dx * fy + dy * fx)
        out = np.hypot(np.maximum(np.maximum(u0 - u, u - u1), 0.0), np.maximum(v - vh, 0.0))
        stage = np.maximum(stage, _smoothstep(14.0, 0.0, out))
    for cx, cy in stage_centres(spots).values():
        stage = np.maximum(stage, 0.16 * _smoothstep(75.0, 30.0, np.hypot(CX - cx, CY - cy)))
    # the paths: their dirt, the edge a little ragged
    rag = Fr.bilinear(tile_noise(np.random.default_rng(5104), 256, ((16, 0.5), (32, 0.3), (64, 0.2))), (CX % 128.0) * 2.0,
                      (CY % 128.0) * 2.0) - 0.5
    path = np.zeros(CX.shape, np.float64)
    flat = np.stack([CX.ravel(), CY.ravel()], 1)
    for pr in profiles.values():
        dense, _ = Fr.resample(pr["pts"], 0.25)
        d, _ = cKDTree(dense).query(flat, distance_upper_bound=pr["width"] / 2 + 2.0)
        d = d.reshape(CX.shape)
        w = np.clip(1.0 - (d - pr["width"] / 2 - 0.2 + 0.7 * rag) / 0.7, 0, 1)
        w[~np.isfinite(d)] = 0.0
        path = np.maximum(path, w)
    # the woods: the land cover's woods, softened; open over the water and in the Stone Circle's clearing
    cls = g.cls_at(CX, CY)
    woods = ndi.gaussian_filter(((cls == 1) | (cls == 2)).astype(np.float64), 4.0)
    i, j = g.ij(CX, CY)
    ii, jj = np.clip(i, 0, g.H - 1), np.clip(j, 0, g.W - 1)
    woods *= np.where(g.water[ii, jj], 0.35, 1.0)
    woods *= _smoothstep(0.92, 1.18, L.ring_radius(CX, CY))
    rgba = np.zeros(CX.shape + (4,), np.uint8)
    rgba[..., 0] = to_u8(np.sqrt(np.clip(warm / WARM_MAX, 0, 1)))
    rgba[..., 1] = to_u8(np.sqrt(np.clip(stage, 0, 1)))
    rgba[..., 2] = to_u8(path)
    rgba[..., 3] = to_u8(np.clip(woods, 0, 1))
    write_png(os.path.join(TEX_DIR, "T_BdLight.png"), rgba)
    mx, my = g.frame.mx, g.frame.my
    centres = {k: [round(float(v), 1) for v in g.frame.world(c[0], c[1], 0.0)[:2]] for k, c in stage_centres(spots).items()}
    lit = dict(lu=[1.0 / (100.0 * LMAP_RES * LMAP_W), (mx - Fr.DJ_Y_OFFSET_CM / 100.0 - LMAP_X0) / (LMAP_RES * LMAP_W)],
               lv=[-1.0 / (100.0 * LMAP_RES * LMAP_H), (my - LMAP_Y0) / (LMAP_RES * LMAP_H)],
               warm_max=WARM_MAX, stages=centres, moon_dir=[round(float(v), 6) for v in MOON],
               moon_sun=[round(float(v), 6) for v in MOON_SUN], crop_origin=[LMAP_X0, LMAP_Y0], metres_per_px=LMAP_RES,
               size=[LMAP_W, LMAP_H], lamps=len(lamps))
    log(f"light map: {LMAP_W} x {LMAP_H} at {LMAP_RES} m; {len(lamps)} lamps (warm peak {warm.max():.2f}); stage light over "
        f"{(stage > 0.5).sum() * LMAP_RES ** 2 / 1e4:.2f} ha; paths {(path > 0.5).sum() * LMAP_RES ** 2 / 1e4:.2f} ha")
    return lit


def lamps_of(g, path_lights, parts, lit_trees, spots):
    """The warm lamps for the light map (crop x, y, radius m, peak)."""
    lamps = [(cx, cy, 5.0, 0.95) for cx, cy, _, _ in path_lights]
    for poles in parts["festoons"].points.get("pole_paths", []):
        for a, b in zip(poles[:-1], poles[1:]):
            A, B = np.asarray(a), np.asarray(b)
            for t in np.linspace(0.0, 1.0, max(2, int(np.hypot(*(B - A)[:2]) / 250.0))):
                cx, cy = g.frame.crop(A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t)
                lamps.append((float(cx), float(cy), 6.5, 0.16))
    for X, Y, _ in parts["tents"].points.get("lit_tents", []):
        cx, cy = g.frame.crop(X, Y)
        lamps.append((float(cx), float(cy), 4.5, 0.55))
    for cx, cy in lit_trees:
        lamps.append((float(cx), float(cy), 6.0, 0.22))
    # the Pavilion's hall, lit by its strings: a row of pools down its length
    sp = spots["Pavilion"]
    fx, fy = math.cos(math.radians(L.SPOTS["Pavilion"]["facing"])), -math.sin(math.radians(L.SPOTS["Pavilion"]["facing"]))
    for u in np.arange(-1.0, 19.5, 2.5):
        lamps.append((sp["crop"][0] + fx * u, sp["crop"][1] + fy * u, 7.0, 0.26))
    # the bridges' lights: warm pools along the footbridge, the Rainbow Bridge's along its deck
    for b in L.BRIDGES:
        if b["kind"] == "suspension":
            for t in np.linspace(0, 1, 9):
                lamps.append((b["a"][0] + (b["b"][0] - b["a"][0]) * t, b["a"][1] + (b["b"][1] - b["a"][1]) * t, 6.0, 0.3))
        if b["kind"] == "beam":
            for t in np.linspace(0, 1, 9):
                lamps.append((b["a"][0] + (b["b"][0] - b["a"][0]) * t, b["a"][1] + (b["b"][1] - b["a"][1]) * t, 4.0, 0.35))
    return lamps


def build_glow(g, parts, spots, glow):
    """The stages' beams, lasers, sky beams and glows on top of the halos already in glow (the festoons, path lights):
    beams from every moving head toward its stage's crowd, laser fans crossing the Main Stage's crowd from both sides
    (the research: cyan and white, red and purple, green) and over New Camp's, sky beams above each stage (seen over the
    canopy from anywhere), a soft glow over each stage's crowd and each lens's glare."""
    nb = 0
    for name, (length, pitch0, spread) in (("Main", (4200.0, -6.0, 7.0)), ("Pavilion", (650.0, -48.0, 9.0)),
                                           ("NewCamp", (3000.0, -4.0, 8.0))):
        movers = parts[name].points.get("movers", [])
        for k, (P, yaw, off) in enumerate(movers):
            yw = yaw + (k - (len(movers) - 1) / 2.0) * spread / max(len(movers) / 8.0, 1.0)
            pt = pitch0 + (k % 3) * (10.0 if name != "Pavilion" else 8.0)
            col = S.glow_col(off, 0.0, 1.0, k * 0.137)
            S.glow_ribbon(glow, P, yw, pt, length, 9.0, M.GLOW_BEAM, col, 0.55 if name != "Pavilion" else 0.45)
            S.glow_halo(glow, [P], 30.0, col, 0.8)
            nb += 1
    nl = 0
    o, yaw = parts["Main"].points["frame"]
    for s_, off in ((-1, 0.5), (1, 0.75)):                 # cyan and violet from either side tower, crossing
        P = M.place(np.array([[350.0, s_ * 830.0, 900.0]]), o, yaw)[0]
        for k in range(7):
            yw = yaw - s_ * (14.0 + k * 6.0)
            S.glow_ribbon(glow, P, yw, -4.5 + (k % 2) * 2.0, 4600.0, 1.4, M.GLOW_LASER, S.glow_col(off, 0.0, 0.5, (0.0 if s_ < 0 else 0.33) + k * 0.02), 1.0, 2)
            nl += 1
    P = M.place(np.array([[350.0, 0.0, 975.0]]), o, yaw)[0]
    for k in range(9):                                     # green from the front truss's middle
        S.glow_ribbon(glow, P, yaw + (k - 4) * 7.0, -5.0, 4800.0, 1.4, M.GLOW_LASER, S.glow_col(0.375, 0.0, 0.0, 0.66 + k * 0.02), 1.0, 2)
        nl += 1
    o, yaw = parts["NewCamp"].points["frame"]
    P = M.place(np.array([[-430.0, 0.0, 700.0]]), o, yaw)[0]
    for k in range(9):
        S.glow_ribbon(glow, P, yaw + (k - 4) * 8.0, -3.0, 3600.0, 1.4, M.GLOW_LASER, S.glow_col(0.625, 0.0, 0.5, 0.2 + k * 0.02), 1.0, 2)
        nl += 1
    ns = 0
    for name, pts, off in (("Main", [(-650.0, -830.0, 1000.0), (-650.0, 830.0, 1000.0), (-650.0, 0.0, 1050.0)], 0.75),
                           ("Pavilion", [(-300.0, -320.0, 780.0), (-300.0, 320.0, 780.0)], 0.0),
                           ("NewCamp", [(-430.0, -680.0, 740.0), (-430.0, 680.0, 740.0)], 0.5)):
        o, yaw = parts[name].points["frame"]
        for k, q in enumerate(pts):
            P = M.place(np.array([q]), o, yaw)[0]
            S.glow_ribbon(glow, P, yaw + 180.0 + k * 120.0, 74.0 + 4.0 * (k % 2), 32000.0, 22.0, M.GLOW_SKY,
                          S.glow_col(off, 0.0, 0.25, k * 0.29), 0.32, 6)
            ns += 1
    for name, height, size, off in (("Main", 1500.0, 2600.0, 0.75), ("Pavilion", 900.0, 1400.0, 0.0), ("NewCamp", 1100.0, 1900.0, 0.5)):
        c = stage_centres(spots)[name]
        z = float(g.zworld(*g.frame.world(c[0], c[1], 0.0)[:2])) + height
        W = g.frame.world(c[0], c[1], 0.0)
        S.glow_halo(glow, [(W[0], W[1], z)], size, S.glow_col(off, 0.0, 1.0, 0.0), 0.10, M.GLOW_DOME)
    log(f"glow: {nb} beams, {nl} lasers, {ns} sky beams, 3 stage glows; {glow.triangles} triangles in all")


# The hard-coded points of the C++ tests (VRDJBigDubTests.cpp: the ReachMap probes, the Walk legs): no new wall may stand
# on them. Checked here so a path light or a prop can't move them under a wall unnoticed (world cm).
TEST_PROBES_REACHED = [(0.0, 90.0), (5400.0, -12310.0), (-56000.0, -13710.0), (-30100.0, -21810.0), (-40100.0, -18210.0),
                       (-13100.0, -13410.0), (-13500.0, -5610.0), (-19300.0, -10610.0), (-5300.0, -210.0), (-40700.0, -6410.0),
                       (-48750.0, -10910.0), (-3100.0, -13210.0), (-351.9, -1512.9), (-876.9, -4062.9), (348.1, 1712.1),
                       (-2976.9, -962.9), (-1026.9, -4762.9), (2298.1, -2087.9)]
TEST_LEGS = [((834.4, 408.5), (1470.2, 273.3), (1470.2, 273.3)), ((1660.0, -4930.0), (400.0, -3370.0), (-311.9, -1377.2)),
             ((1584.3, 1045.0), (353.4, 1752.9), (-1059.0, 1606.9)), ((-46400.0, -10910.0), (-50920.0, -10910.0), (-50810.0, -11400.0)),
             ((-1800.0, -12160.0), (-4400.0, -14260.0), (-4400.0, -14260.0)), ((-23000.0, -10610.0), (-31000.0, -10110.0), (-31000.0, -10110.0))]


def check_test_points(new_walls):
    """True if no new wall (polygon, z0, z1) comes within 45 cm of a reached probe or within the walker's 20 cm (+15)
    of a Walk leg's line (both in world XY)."""
    bad = []
    for poly, _, _ in new_walls:
        P = np.asarray(poly, np.float64)[:, :2]
        c = P.mean(0)
        rad = float(np.max(np.linalg.norm(P - c, axis=1)))
        for x, y in TEST_PROBES_REACHED:
            if math.hypot(x - c[0], y - c[1]) < rad + 45.0:
                bad.append(("probe", (x, y), c.tolist()))
        for a, v, b in TEST_LEGS:
            for p0, p1 in ((a, v), (v, b)):
                d, _ = Fr.point_segment_distance(c[0], c[1], p0[0], p0[1], p1[0], p1[1])
                if float(d) < rad + 35.0:
                    bad.append(("leg", p0, c.tolist()))
    if bad:
        log(f"WARNING new walls on the tests' fixed points: {bad[:6]}")
    return not bad


# ====================================================================================================================
# the budget
# ====================================================================================================================

QUEST_PROJ = 0.80          # the Quest 3's per-eye projection scale (about 104 degrees across): screen size = 0.8 r / d
FOV_DEG = 104.0
BUDGET_HEADINGS = 8        # the in-view count every 45 degrees round each spot (the DJ turns round)
BUDGET_TRIS = 500_000      # in view, from any heading: under GRAVEYARD SHIFT's 527,118 (docs/venues.md, "Performance")
BUDGET_DRAWS = 44          # in view, from any heading: GRAVEYARD SHIFT's 44


def bounds(V):
    lo, hi = V.min(0), V.max(0)
    c = (lo + hi) / 2
    return c, float(np.linalg.norm(hi - lo) / 2)


def estimate_budget(lods, screens, inst, inst_meshes, cull, eyes):
    """Per eye point (DJ's eye at each spot, facing its crowd): triangles and draws in view (a 104-degree cone) and all
    around, with each mesh's LOD from its bounds' screen size (UE's 2 x 0.5 x P x r / d) and draw distances."""
    out = {}
    mesh_info = {}
    for name, ls in lods.items():
        V, F, C, UV, Mi = ls[0].arrays()
        if len(V) == 0:
            continue
        c, r = bounds(V)
        mesh_info[name] = (c, r, [(len(l.arrays()[1]), len(np.unique(l.arrays()[4]))) for l in ls], screens.get(name, (1.0,)))
    tree_info = {}
    for name, ls in inst_meshes.items():
        V = ls[0].arrays()[0]
        c, r = bounds(V)
        tree_info[name] = (c, r, [(len(l.arrays()[1]), len(np.unique(l.arrays()[4]))) for l in ls], screens.get(name))
    for spot, (eye, yaw) in eyes.items():
        fwd = np.array([math.cos(math.radians(yaw)), math.sin(math.radians(yaw))])
        res = {"view": [0, 0], "around": [0, 0]}
        detail = {}
        for name, (c, r, lv, ss) in mesh_info.items():
            d = max(float(np.linalg.norm(c - eye)), 1.0)
            if cull.get(name) and d - r > cull[name]:
                continue
            size = QUEST_PROJ * r / d
            lod = 0
            for k, s in enumerate(ss):
                if size < s:
                    lod = k
            lod = min(lod, len(lv) - 1)
            tris, secs = lv[lod]
            dirv = (c - eye)[:2]
            ang = math.degrees(math.acos(max(-1.0, min(1.0, float(dirv @ fwd) / max(np.linalg.norm(dirv), 1e-6)))))
            half = math.degrees(math.asin(min(1.0, r / d)))
            res["around"][0] += tris
            res["around"][1] += secs
            if ang - half <= FOV_DEG / 2:
                res["view"][0] += tris
                res["view"][1] += secs
                detail[name] = (tris, secs, lod)
        for name, rows in inst.items():
            if not rows:
                continue
            c0, r, lv, ss = tree_info[name]
            P = np.array([[x, y, z] for x, y, z, *_ in rows]) + c0
            scale = np.array([max(sx, sz) for *_, sx, sy, sz in rows])
            d = np.maximum(np.linalg.norm(P - eye, axis=1), 1.0)
            if cull.get(name):
                near = d - r * scale <= cull[name]
                P, scale, d = P[near], scale[near], d[near]
                rows = [rw for rw, k in zip(rows, near) if k]
                if not rows:
                    continue
            size = QUEST_PROJ * r * scale / d
            lod = np.zeros(len(rows), np.int64)
            for k, s in enumerate(ss):
                lod[size < s] = k
            dirv = (P - eye)[:, :2]
            cosang = (dirv @ fwd) / np.maximum(np.linalg.norm(dirv, axis=1), 1e-6)
            ang = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
            half = np.degrees(np.arcsin(np.clip(r * scale / d, 0, 1)))
            vis = ang - half <= FOV_DEG / 2
            for k in range(len(lv)):
                tris, secs = lv[k]
                na = int((lod == k).sum())
                nv = int(((lod == k) & vis).sum())
                res["around"][0] += na * tris
                res["view"][0] += nv * tris
                if na:
                    res["around"][1] += secs
                if nv:
                    res["view"][1] += secs
                    detail[f"{name} LOD{k}"] = (nv * tris, secs, k)
        res["top"] = sorted(((n, t[0], t[1]) for n, t in detail.items()), key=lambda x: -x[1])[:14]
        out[spot] = res
    return out


# ====================================================================================================================
# main
# ====================================================================================================================

# ---- TRIBE (2026-11-01): the Main Stage alone, for Tribe XR's stage menu ------------------------------------------------
TRIBE_KEEP_M = 75.0         # tents (and their lamps) kept within this of the ring's centre (the Pavilion is 122 m away)
TRIBE_LIT_TREE_M = 60.0     # lit trees kept within this of the ring's centre: the ring's own (1.75 x its ellipse)
TRIBE_DECOR_RR = 1.08       # decor kept inside this ring radius (1 = the stones): jellyfish, flowers, flags, the sign
TRIBE_GLOW_RR = 1.15        # glow quads (by their centre) kept inside this ring radius: the Main Stage's beams and halos


def tribe_near(cx, cy, r_m):
    c = L.STONE_CIRCLE["center"]
    return np.hypot(np.asarray(cx) - c[0], np.asarray(cy) - c[1]) < r_m


def tribe_filter_mesh(m, keep):
    """A copy of mesh m with only the triangles whose centroid (world X, Y in cm) passes keep(X, Y) (arrays)."""
    V, F, C, UV, Mi = m.arrays()
    out = M.Mesh(m.name, m.materials)
    out.default_aux, out.aux_rule = m.default_aux, m.aux_rule
    if len(F) == 0:
        return out
    X = m.aux_arrays()
    cen = V[F].mean(axis=1)
    sel = np.asarray(keep(cen[:, 0], cen[:, 1]), bool)
    F = F[sel]
    if len(F) == 0:
        return out
    used = np.unique(F)
    remap = np.full(len(V), -1, np.int64)
    remap[used] = np.arange(len(used))
    out._v.append(V[used])
    out._f.append(remap[F])
    out._c.append(C[used])
    out._uv.append(UV[used])
    out._x.append(X[:, used])
    out._m.append(Mi[sel])
    out._n = len(used)
    return out


TRIBE_YAW = 12.0            # the Tribe frame: the game's frame turned +12 degrees about the DJ's point (0, 90): the
TRIBE_DJ = (0.0, 90.0)      # Main Stage's DJ (yaw -102) then faces -Y, as Tribe's rig does


def tribe_xy(X, Y):
    """Game-frame world cm -> Tribe-frame world cm (z is the same)."""
    a = math.radians(TRIBE_YAW)
    c, s = math.cos(a), math.sin(a)
    x, y = np.asarray(X, np.float64) - TRIBE_DJ[0], np.asarray(Y, np.float64) - TRIBE_DJ[1]
    return x * c - y * s + TRIBE_DJ[0], x * s + y * c + TRIBE_DJ[1]


def game_xy(x, y):
    """Tribe-frame world cm -> game-frame world cm."""
    a = math.radians(-TRIBE_YAW)
    c, s = math.cos(a), math.sin(a)
    x, y = np.asarray(x, np.float64) - TRIBE_DJ[0], np.asarray(y, np.float64) - TRIBE_DJ[1]
    return x * c - y * s + TRIBE_DJ[0], x * s + y * c + TRIBE_DJ[1]


def tribe_export(g, parts):
    """For the Tribe stage's crowd and walking map: the ground round the Stone Circle as a height grid in the Tribe frame
    (tribe_ground.npy: z cm at x = X0 + i * STEP, y = Y0 + j * STEP, [j, i]), and the Main Stage's, the stones' and the
    decor's floors, ramps and walls in the Tribe frame (tribe_site.json)."""
    X0, X1, Y0, Y1, STEP = -4000.0, 4000.0, -6000.0, 2600.0, 25.0
    xs = np.arange(X0, X1 + 1e-6, STEP)
    ys = np.arange(Y0, Y1 + 1e-6, STEP)
    XX, YY = np.meshgrid(xs, ys)
    GX, GY = game_xy(XX, YY)
    Z = np.asarray(g.zworld(GX.ravel(), GY.ravel()), np.float64).reshape(XX.shape)
    np.save(os.path.join(OUT, "tribe_ground.npy"), Z.astype(np.float32))

    def poly_t(poly):
        P = np.asarray(poly, np.float64)
        tx, ty = tribe_xy(P[:, 0], P[:, 1])
        return [[round(float(a), 1), round(float(b), 1)] for a, b in zip(tx, ty)]

    def near_ring(poly):
        P = np.asarray(poly, np.float64)
        cx, cy = g.frame.crop(P[:, 0].mean(), P[:, 1].mean())
        return float(L.ring_radius(cx, cy)) < 1.35
    out = dict(note="Tribe frame (the game's turned +12 deg about (0, 90)), world cm; ground grid in tribe_ground.npy",
               grid=dict(x0=X0, y0=Y0, step=STEP, nx=len(xs), ny=len(ys)))
    for key in ("Main", "stones", "decor"):
        p = parts[key]
        out[key] = dict(floors=[[poly_t(f[0]), round(float(f[1]), 1), round(float(f[2]), 1)] for f in p.floors if near_ring(f[0])],
                        walls=[[poly_t(w[0]), round(float(w[1]), 1), round(float(w[2]), 1)] for w in p.walls if near_ring(w[0])],
                        ramps=[repr(r)[:400] for r in p.ramps])
    cx, cy = tribe_xy(*g.frame.world(*L.STONE_CIRCLE["center"], g.frame.e0)[:2])
    out["ring"] = dict(cx=round(float(cx), 1), cy=round(float(cy), 1), ra=L.STONE_CIRCLE["ra"] * 100.0,
                       rb=L.STONE_CIRCLE["rb"] * 100.0, note="ra along Tribe Y, rb along X (cm)")
    fs = parts["stones"].points.get("flame_stone")
    if fs:
        fx, fy = tribe_xy(fs[0], fs[1])
        out["flame_stone"] = [round(float(fx), 1), round(float(fy), 1)]
    with open(os.path.join(OUT, "tribe_site.json"), "w") as f:
        json.dump(out, f, indent=0)
    log(f"TRIBE export: ground {Z.shape[1]} x {Z.shape[0]} at {STEP:.0f} cm (z {Z.min():.0f}..{Z.max():.0f}); "
        + ", ".join(f"{k}: {len(out[k]['floors'])} floors {len(out[k]['walls'])} walls {len(out[k]['ramps'])} ramps"
                    for k in ("Main", "stones", "decor")) + f"; ring centre ({cx:.0f}, {cy:.0f})")


def main():
    rng = np.random.default_rng(2026)
    os.makedirs(MESH_DIR, exist_ok=True)
    g = Ground()
    log(f"DEM: 1 m over crop x {Fr.EXT[0]}..{Fr.EXT[2]}, y {Fr.EXT[1]}..{Fr.EXT[3]} ({g.W} x {g.H}); far window 10 m "
        f"{g.far.shape[1] * 10 / 1000:.0f} x {g.far.shape[0] * 10 / 1000:.0f} km")
    g.water, g.water_level = build_water(g)
    # the frame: its origin is the first build's Main Stage DJ spot (bd_layout.FRAME_ORIGIN), its floor z = 0
    ox, oy = L.FRAME_ORIGIN
    origin_ground = float(Fr.bilinear(g.dem0, ox, oy, g.x0, g.y0))
    g.frame = Fr.Frame(ox, oy, origin_ground + L.FRAME_FLOOR_OVER_GROUND_M)
    log(f"frame: origin at crop ({ox:.0f}, {oy:.0f}), floor {g.frame.e0:.2f} m = world z 0; the Main Stage's DJ at crop "
        f"({L.SPOTS['Main']['dj'][0]:.1f}, {L.SPOTS['Main']['dj'][1]:.1f}) facing {L.SPOTS['Main']['facing']:.1f}, inside "
        f"the Stone Circle")
    profiles = carve(g)
    # distances used by placement
    g._pathdist = ndi.distance_transform_edt(g.path_weight < 0.05)
    g._wd = ndi.distance_transform_edt(~g.water)
    gy_, gx_ = np.gradient(g.dem)
    g.slope_deg = np.degrees(np.arctan(np.hypot(gx_, gy_)))
    spots = spot_frames(g)
    glow = M.Mesh("SM_BdGlow", ("Glow",))
    parts = build_structures(g, spots, rng, glow)
    # the Stone Circle round the Main Stage and its crowd: a stone is left out where it would stand within 1 m of a path
    # (the gaps are the ways in) or 1.5 m of the stage's structures (none should: the stage stands clear of the ring).
    # Its own random stream, so the ring's stones never move the forest's draws.
    main_part = parts["Main"]
    keep_polys = [f[0] for f in main_part.floors] + [w[0] for w in main_part.walls]
    stage_blocked = []

    def keep_out(X, Y, r_cm):
        cx, cy = g.frame.crop(X, Y)
        i, j = g.ij(cx, cy)
        if g._pathdist[i, j] < 1.0 + r_cm / 100.0:
            return True
        if poly_distance(keep_polys, X, Y) < 150.0 + r_cm:
            stage_blocked.append((X, Y))
            return True
        return False
    parts["stones"] = S.stone_circle(g.frame, g.zworld, np.random.default_rng(2031), L.STONE_CIRCLE, keep_out)
    sp_ = parts["stones"].points
    log(f"Stone Circle: {sp_['stones']} of {L.STONE_CIRCLE['stones']} stones all round the Main Stage and its crowd; "
        f"{len(sp_['gaps']) - len(stage_blocked)} left out for the ways in, {len(stage_blocked)} for the stage")
    if stage_blocked:
        log(f"WARNING the Main Stage's structures reach the ring's stones at {stage_blocked}")
    inst, trunks, tree_stats, lit_xy = place_trees(g, parts, profiles, spots, rng)
    g.trunks = trunks
    parts["tents"] = place_tents(g, parts, trunks, spots, rng)
    # TRIBE: every builder still runs, in the game's order, so every random draw (trees, tents, stones, decor) lands
    # where the game's has it; the paths' festoons and lights put their halos in a mesh that is thrown away
    drop_glow = M.Mesh("SM_BdGlowDropped", ("Glow",))
    parts["festoons"] = build_festoons(g, profiles, rng, drop_glow)
    # the night's light: path lights (their walls checked against the tests' fixed points), the light map, the glow
    path_lights = place_path_lights(g, profiles, parts)
    parts["pathlights"] = build_path_lights(g, path_lights, drop_glow)
    parts["decor"], decor_lamps = build_decor(g, parts, spots, profiles, trunks, glow)
    o_, y_ = parts["Pavilion"].points["frame"]
    D.wisteria(parts["Pavilion"], S.StageFrame(o_, y_, g.zworld), -250.0, 1880.0, 455.0,
               parts["Pavilion"].points["hall_floor_z"] - o_[2] + 360.0, np.random.default_rng(7102))
    test_points_clear = check_test_points(parts["pathlights"].walls + parts["decor"].walls)
    # TRIBE: the Main Stage alone. Its light map has only its own stage light and the lamps that stay (the lit tents
    # within TRIBE_KEEP_M of the ring's centre, the lit trees round the ring, the ring's decor and the Flame Stone's
    # floods): no path lights, festoons, Pavilion strings or bridges
    lit_xy = [(cx, cy) for cx, cy in lit_xy if tribe_near(cx, cy, TRIBE_LIT_TREE_M)]
    tent_part = parts["tents"]
    tent_part.points["lit_tents"] = [t for t in tent_part.points.get("lit_tents", [])
                                     if tribe_near(*g.frame.crop(t[0], t[1]), TRIBE_KEEP_M)]
    decor_lamps = [lp for lp in decor_lamps if L.ring_radius(lp[0], lp[1]) < TRIBE_DECOR_RR]
    tribe_lamps = [(float(cx), float(cy), 4.5, 0.55) for cx, cy in (g.frame.crop(t[0], t[1]) for t in tent_part.points["lit_tents"])]
    tribe_lamps += [(float(cx), float(cy), 6.0, 0.22) for cx, cy in lit_xy] + decor_lamps
    boxes_, centres_ = dict(STAGE_BOXES), stage_centres
    STAGE_BOXES.clear()
    globals()["stage_centres"] = lambda spots_: {"Main": tuple(L.STONE_CIRCLE["center"])}
    lighting = build_light_map(g, profiles, spots, tribe_lamps)
    STAGE_BOXES.update(boxes_)
    globals()["stage_centres"] = centres_
    build_glow(g, parts, spots, glow)
    glow = tribe_filter_mesh(glow, lambda X, Y: L.ring_radius(*g.frame.crop(X, Y)) < TRIBE_GLOW_RR)
    crowd_rows, crowd_counts = place_crowds(g, parts, spots, trunks)
    # TRIBE: the game's dancers are not shipped (the Tribe crowd replaces them); the Main Stage's are kept as a reference
    with open(os.path.join(OUT, "tribe_game_crowd.json"), "w") as f_:
        json.dump({k: [r for r in v if L.ring_radius(*g.frame.crop(r[0], r[1])) < 1.0] for k, v in crowd_rows.items()}, f_)
    for name_ in ("SM_BdTreeLightsHardwood", "SM_BdTreeLightsHemlock"):
        inst[name_] = [r for r in inst[name_] if tribe_near(*g.frame.crop(r[0], r[1]), TRIBE_LIT_TREE_M)]
    log(f"TRIBE: the Main Stage only: {len(tribe_lamps)} lamps in the light map, {glow.triangles} glow triangles, "
        f"{sum(len(inst[n]) for n in ('SM_BdTreeLightsHardwood', 'SM_BdTreeLightsHemlock'))} lit trees; parts {sorted(parts)}")
    terrain = build_terrain(g)
    log(f"terrain: {len(terrain)} meshes; core tiles LOD0 {sum(m[0].triangles for k, m in terrain.items() if k.startswith('SM_BdTerrain_'))} "
        f"tris")
    canopy = build_canopy(g, np.random.default_rng(2027))     # its own stream: its grid's size moves nothing after it
    terrain["SM_BdFar"][0].extend(canopy)
    log(f"SM_BdFar (the outer terrain, the horizon, the far canopy): {terrain['SM_BdFar'][0].triangles} triangles")
    water = build_water_mesh(g)
    g.sky_centre = g.frame.world(1150.0, 380.0, g.frame.e0)[:2]
    sky = build_sky(g)
    build_textures()
    tree_meshes = T.build_tree_meshes()
    tree_meshes.update(C.build_crowd_meshes())
    # walking
    wc = walk_cells(g, parts, spots)
    floors, walls, cstats = collision(g, wc, parts, trunks)
    walkrep = walk_report(g, wc, parts, rng)
    floor_polys = [poly for p in parts.values() for poly, _, _ in p.floors]
    walk_image(g, wc, floor_polys, [w[0] for w in parts["stones"].walls], profiles, os.path.join(OUT, "walk.png"))
    ringrep = ring_report(g, wc, parts, trunks, profiles, os.path.join(OUT, "site_top.png"))
    views = view_points(g, wc, parts, spots, trunks)
    # gather the meshes
    lods = dict(terrain)
    lods["SM_BdWater"] = [water]
    lods["SM_BdSky"] = [sky]
    # every structure (the three stages, the bridges, the Stone Circle, the tents, the festoons, the path lights) in one
    # mesh: three draws (Surface, Lights, Screen) from anywhere; each part's surfaces get their height over the ground
    # first (the Pavilion's: over its floor, scaled, as its strings light everything under its roof)
    structures = M.Mesh("SM_BdStructures", S.MATS)
    for key, p in parts.items():
        # TRIBE: the Main Stage, its ring, its decor and the tents round it; not the Pavilion, New Camp, the bridges,
        # the paths' festoons or their lights
        if key not in ("Main", "stones", "tents", "decor"):
            continue
        for name, m in p.meshes.items():
            if key == "tents":
                m = tribe_filter_mesh(m, lambda X, Y: tribe_near(*g.frame.crop(X, Y), TRIBE_KEEP_M))
            elif key == "decor":
                m = tribe_filter_mesh(m, lambda X, Y: L.ring_radius(*g.frame.crop(X, Y)) < TRIBE_DECOR_RR)
            if key == "Pavilion":
                fill_heights(m, g.zworld, 0.35, p.points["hall_floor_z"])
            else:
                fill_heights(m, g.zworld)
            structures.extend(m)
    lods["SM_BdStructures"] = [structures]
    lods["SM_BdGlow"] = [glow]
    screens = {k: (1.0, 0.6, 0.3) for k in terrain if k.startswith("SM_BdTerrain_")}
    screens.update({k: (C.LOD_SCREEN_SIZES if k.startswith("SM_BdCrowd") else T.LOD_SCREEN_SIZES) for k in tree_meshes})
    inst_cull = {k: C.CULL_CM for k in tree_meshes if k.startswith("SM_BdCrowd")}
    cull = {}
    bounds_scale = {"SM_BdGlow": 1.5}
    # spots for the game
    spot_out = {}
    eyes = {}
    for name in L.SPOT_ORDER:
        p = parts[name] if name in parts else None
        o, yaw = p.points["frame"]
        anchor = p.points["anchor"]
        dj = np.asarray(p.points["dj"])
        spot_out[name] = dict(label=spots[name]["label"], yaw=round(yaw, 3), dj=[round(float(v), 2) for v in dj],
                              start=[round(float(dj[0]), 2), round(float(dj[1]), 2), round(float(dj[2]) + 100.0, 2)],
                              anchor=[round(float(v), 2) for v in anchor], deck_m=round(spots[name]["deck"], 3),
                              crop=list(spots[name]["crop"]), ground_m=round(spots[name]["ground"], 2),
                              joined=bool(wc["reach"].get(name, False)))
        eyes[name] = (dj + np.array([0, 0, 170.0]), yaw)
    # the DJ turns round: every 45 degrees from the crowd's heading, and the heaviest of the eight
    sweep = estimate_budget(lods, screens, inst, tree_meshes, dict(cull, **inst_cull),
                            {(name, k): (eye, yaw + 45.0 * k) for name, (eye, yaw) in eyes.items() for k in range(BUDGET_HEADINGS)})
    budget = {}
    for name in eyes:
        b = sweep[(name, 0)]
        heads = [sweep[(name, k)]["view"] for k in range(BUDGET_HEADINGS)]
        kt = max(range(BUDGET_HEADINGS), key=lambda k: heads[k][0])
        kd = max(range(BUDGET_HEADINGS), key=lambda k: heads[k][1])
        b["worst"] = dict(tris=heads[kt][0], tris_heading=45 * kt, draws=heads[kd][1], draws_heading=45 * kd)
        budget[name] = b
        log(f"budget at {name}: facing the crowd {b['view'][0]:,} tris, {b['view'][1]} draws; heaviest heading "
            f"{heads[kt][0]:,} tris (+{45 * kt}), most draws {heads[kd][1]} (+{45 * kd}); all around {b['around'][0]:,} "
            f"tris, {b['around'][1]} draws; heaviest meshes facing the crowd {[(n, t) for n, t, s in b['top'][:6]]}")
        if heads[kt][0] > BUDGET_TRIS or heads[kd][1] > BUDGET_DRAWS:
            log(f"WARNING {name}: over the venue budget ({BUDGET_TRIS:,} tris, {BUDGET_DRAWS} draws in view)")
    # write meshes (the old files first: bd_blender.py converts every .npz here, and a merged or renamed mesh's old file
    # would come back as a stray FBX)
    for old in os.listdir(MESH_DIR):
        if old.endswith(".npz"):
            os.remove(os.path.join(MESH_DIR, old))
    written = []
    for name, ls in lods.items():
        ls[0].name = name
        ls[0].save(os.path.join(MESH_DIR, name + ".npz"), ls[1:])
        written.append(dict(name=name, lods=len(ls), tris=[l.triangles for l in ls], materials=ls[0].materials,
                            screen_sizes=list(screens.get(name, ())), cull_cm=cull.get(name, 0.0), kind="visual",
                            bounds_scale=bounds_scale.get(name, 1.0)))
    for name, ls in tree_meshes.items():
        ls[0].save(os.path.join(MESH_DIR, name + ".npz"), ls[1:])
        written.append(dict(name=name, lods=len(ls), tris=[l.triangles for l in ls], materials=ls[0].materials,
                            screen_sizes=list(screens[name]), cull_cm=inst_cull.get(name, 0.0), kind="instanced"))
    for m in (floors, walls):
        m.save(os.path.join(MESH_DIR, m.name + ".npz"))
        written.append(dict(name=m.name, lods=1, tris=[m.triangles], materials=m.materials, screen_sizes=[], cull_cm=0.0,
                            kind="collision"))
    tribe_export(g, parts)
    sc = L.STONE_CIRCLE
    site = dict(
        version=3,
        frame=dict(origin_crop=[g.frame.mx, g.frame.my], floor_elev_m=g.frame.e0,
                   note="world X north, Y east, Z up; cm. The origin is the first build's Main Stage DJ spot"),
        spots=spot_out, spot_order=list(L.SPOT_ORDER),
        meshes=written, instances=inst,
        trees=tree_stats, tents=parts["tents"].points["tents"], festoon_poles=parts["festoons"].points["poles"],
        stones=parts["stones"].points["stones"],
        ring=dict(center_crop=list(sc["center"]), center_world=[round(float(v), 1) for v in g.frame.world(*sc["center"], g.frame.e0)[:2]],
                  ra_m=sc["ra"], rb_m=sc["rb"], rot_deg=sc["rot"], slots=sc["stones"], stones=parts["stones"].points["stones"],
                  gaps_world=[[round(v, 1) for v in q] for q in parts["stones"].points["gaps"]],
                  stage_inset_m=sc["stage_inset"], walk=ringrep),
        paths={k: dict(length_m=round(float(v["s"][-1]), 1), grade_max=round(v["grade_max"], 3), cut_max_m=round(v["cut_max"], 2))
               for k, v in profiles.items()},
        bridges={b["name"]: parts["bridge_" + b["name"]].points[b["name"]] for b in L.BRIDGES},
        collision=cstats, walk=walkrep, budget={k: dict(view_tris=v["view"][0], view_draws=v["view"][1],
                                                         around_tris=v["around"][0], around_draws=v["around"][1],
                                                         worst=v["worst"], top=v["top"])
                                                for k, v in budget.items()},
        pillars=parts["Main"].points.get("pillars", []),
        lighting=lighting, path_lights=len(path_lights), test_points_clear=test_points_clear, crowds=crowd_counts, views=views,
        instance_cull_cm=inst_cull,
        glow_triangles=glow.triangles,
    )
    with open(os.path.join(OUT, "site.json"), "w", newline="\n") as f:
        json.dump(site, f, indent=1)
    log(f"wrote {len(written)} meshes to {MESH_DIR} and site.json")


if __name__ == "__main__":
    main()
