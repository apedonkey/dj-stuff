"""bd_frame.py: BIG DUB's geodata and its frame in the game (plain Python + numpy).

The geodata (D:/TribeUE/bigdub_geo, read only; licences in docs/venues.md "BIG DUB"):
  dem_crop.npy        USGS 3DEP 1 m bare-earth DEM, a 2,000 x 1,800 m crop (rows = y south, cols = x east), metres
  data/dem_x72y441.tif  the whole 10 x 10 km DEM tile (the horizon ring)
  masks.npz           2 m land-cover classes (0 field, 1 deciduous woods, 2 evergreen, 3 water (OSM line), 4 road (OSM))
                      and the OSM roads in crop metres
  creek_path.json     the creek's main stem traced from the DEM (crop metres and water elevation)

The crop frame (the plan's, claudedocs/bigdub_stage_plan.md section 1.1): x east, y south, metres.

The game's frame (world cm, Unreal's X forward / Y right / Z up), the one every venue uses: the Main Stage's DJ stands
at (0, 90, 0) facing -Y, as on GRAVEYARD SHIFT and REACTOR (docs/venues.md). The Main Stage faces west, so:
  world X = -(crop y - main y) x 100      (north)
  world Y =  (crop x - main x) x 100 + 90 (east)
  world Z =  (elevation - the Main Stage's deck floor) x 100
A rotation (no mirror): the site keeps its real shape and slopes, turned so west is the crowd's -Y.
"""
import json
import math
import os

import numpy as np

GEO = os.environ.get("BIGDUB_GEO", "D:/TribeUE/bigdub_geo")
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
# TRIBE copy (2026-11-01): the Tribe stage's generator writes into its own folder, never into the game's build/bigdub
OUT = os.environ.get("BIGDUB_OUT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "gen"))

DJ_Y_OFFSET_CM = 90.0          # the venues' DJ spot is (0, 90) (docs/venues.md), the booth anchor (5, 22.5, 74)
ANCHOR_AHEAD_CM = 67.5         # the anchor stands this far ahead of the DJ ...
ANCHOR_RIGHT_CM = 5.0          # ... and this far to the DJ's right
TABLE_TOP_CM = 74.0            # the booth table's top over the DJ's floor (the Dino TABLE every venue has)
TABLE_HALF = (95.0, 32.5)      # the drawn top: 190 x 65 cm about the anchor (AVRDJBooth TableSizeCm + VenueTableLipCm)


def load_dem():
    dem = np.load(os.path.join(GEO, "dem_crop.npy"), allow_pickle=False).astype(np.float64)
    if not np.isfinite(dem).all():
        dem = np.nan_to_num(dem, nan=float(np.nanmin(dem)))
    return dem


EXT = (-200, -400, 2200, 2000)      # the extended 1 m DEM's crop window (x0, y0, x1, y1): the crop's north edge is only
                                    # 76 m from the Pavilion, so the terrain runs on past it from the whole tile


def load_dem_ext():
    """The 1 m DEM over EXT (crop metres), from the whole tile (cached): (array [row = y - y0, col = x - x0], x0, y0)."""
    x0, y0, x1, y1 = EXT
    cache = os.path.join(OUT, f"dem_ext_{x0}_{y0}_{x1}_{y1}.npy")
    if os.path.isfile(cache):
        a = np.load(cache, allow_pickle=False)
    else:
        import tifffile
        r0, c0 = 5937, 4350
        with tifffile.TiffFile(os.path.join(GEO, "data", "dem_x72y441.tif")) as tf:
            full = tf.pages[0].asarray()
        a = full[r0 + y0:r0 + y1, c0 + x0:c0 + x1].astype(np.float32)
        crop = np.load(os.path.join(GEO, "dem_crop.npy"), allow_pickle=False)
        if not np.allclose(a[-y0:-y0 + crop.shape[0], -x0:-x0 + crop.shape[1]], crop, equal_nan=True):
            raise RuntimeError("the tile's window doesn't match dem_crop.npy")
        if (a < 0).any():
            raise RuntimeError("no-data cells in the extended DEM window")
        os.makedirs(OUT, exist_ok=True)
        np.save(cache, a)
    return a.astype(np.float64), float(x0), float(y0)


def load_masks():
    mk = np.load(os.path.join(GEO, "masks.npz"), allow_pickle=False)
    return mk["cls"].astype(np.uint8), int(mk["step"]), json.loads(str(mk["roads"]))


def load_creek():
    return json.load(open(os.path.join(GEO, "creek_path.json")))["path"]


def load_far_window(step=10, half=3000):
    """The whole DEM tile around the site, every `step` m, `half` m each way of the site centre: (array, x0, y0) with the
    array's [0, 0] at crop (x0, y0). Reads the 10 km GeoTIFF once and caches the window in build/bigdub."""
    cache = os.path.join(OUT, f"dem_far_{step}m_{half}.npy")
    r0, c0 = 5937, 4350                              # the crop's origin in the tile (dem_crop.json R0, C0)
    cy, cx = r0 + 400, c0 + 1150                     # the site's middle, in tile pixels
    if os.path.isfile(cache):
        a = np.load(cache, allow_pickle=False)
    else:
        import tifffile
        with tifffile.TiffFile(os.path.join(GEO, "data", "dem_x72y441.tif")) as tf:
            full = tf.pages[0].asarray()
        a = full[cy - half:cy + half:step, cx - half:cx + half:step].astype(np.float32)
        os.makedirs(OUT, exist_ok=True)
        np.save(cache, a)
    return a.astype(np.float64), (cx - half) - c0, (cy - half) - r0


class Frame:
    """crop metres <-> world cm, about the Main Stage's DJ spot."""

    def __init__(self, main_x, main_y, floor_elev):
        self.mx, self.my, self.e0 = float(main_x), float(main_y), float(floor_elev)

    def world(self, cx, cy, elev):
        cx, cy, elev = np.broadcast_arrays(np.asarray(cx, np.float64), np.asarray(cy, np.float64), np.asarray(elev, np.float64))
        return np.stack([-(cy - self.my) * 100.0, (cx - self.mx) * 100.0 + DJ_Y_OFFSET_CM, (elev - self.e0) * 100.0], axis=-1)

    def crop(self, X, Y):
        X, Y = np.asarray(X, np.float64), np.asarray(Y, np.float64)
        return self.mx + (Y - DJ_Y_OFFSET_CM) / 100.0, self.my - X / 100.0

    def elev_of_z(self, Z):
        return self.e0 + np.asarray(Z, np.float64) / 100.0

    @staticmethod
    def yaw_of_crop_dir(dx, dy):
        """The Unreal yaw (degrees) of a crop-frame direction (dx east, dy south)."""
        # world = (-dy, dx)
        return math.degrees(math.atan2(dx, -dy))

    @staticmethod
    def crop_dir_of_yaw(yaw):
        a = math.radians(yaw)
        fx, fy = math.cos(a), math.sin(a)        # world (X, Y)
        return fy, -fx                            # crop (dx east, dy south)


def bilinear(grid, x, y, x0=0.0, y0=0.0, step=1.0):
    """Samples a [row = y, col = x] grid at crop (x, y) (arrays), clamped to its edges."""
    x = (np.asarray(x, np.float64) - x0) / step
    y = (np.asarray(y, np.float64) - y0) / step
    H, W = grid.shape
    x = np.clip(x, 0, W - 1.000001)
    y = np.clip(y, 0, H - 1.000001)
    j = np.floor(x).astype(np.int64)
    i = np.floor(y).astype(np.int64)
    fx = x - j
    fy = y - i
    a = grid[i, j]
    b = grid[i, j + 1]
    c = grid[i + 1, j]
    d = grid[i + 1, j + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def point_segment_distance(px, py, ax, ay, bx, by):
    """Distance from points (arrays) to the segment a-b, and the position t (0..1) along it."""
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / max(L2, 1e-12), 0.0, 1.0)
    qx, qy = ax + t * dx, ay + t * dy
    return np.hypot(px - qx, py - qy), t


def polyline_length(pts):
    p = np.asarray(pts, np.float64)
    return float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1)))


def resample(pts, spacing):
    """A polyline resampled every `spacing` (its own units), ends kept."""
    p = np.asarray(pts, np.float64)
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    n = max(2, int(math.ceil(s[-1] / spacing)) + 1)
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, p[:, k]) for k in range(p.shape[1])], axis=1), t


def inside_polygon(px, py, poly):
    """Even-odd test of points (arrays) against a polygon [(x, y)...]."""
    px = np.asarray(px, np.float64)
    py = np.asarray(py, np.float64)
    inside = np.zeros(px.shape, bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cond = (y1 > py) != (y2 > py)
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
        inside ^= cond & (px < xint)
    return inside
