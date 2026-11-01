"""bd_structures.py: BIG DUB's built things (plain Python + numpy): the three stages, the Rainbow Bridge and the
ravine footbridge, the Stone Circle, the tents, the festoon lights along the paths and the crowd barriers.

Each builder works in its own frame and hands back world-frame meshes plus the walking collision it needs:
  floors  [(polygon [(x, y)...], z0, z1)]   prisms whose tops are walked on (decks, stairs, the pavilion's floor)
  ramps   [(V, F)]                          sloped walking surfaces as triangles (the bridge decks)
  walls   [(polygon, z0, z1)]               what blocks the body (posts, rails, the booth tables, stones, tents ...)
A stage's frame: the DJ's floor point at the origin, +x toward the crowd, +y the DJ's right, +z up, centimetres.

Material slots: "Surface" (M_BdSurface: albedo x the light map, the moon and the show; UV1 = (height over the ground,
the surface's kind); bd_site.py fills in the heights), "Lights" (M_BdLights: R palette offset, G warmth, B how much the
show's colour steps move it, A twinkle phase; UV1 = (brightness, mode)), "Screen" (M_BdScreen: the LED walls and the
projection screen, a show-driven picture on UV 0..1) and, in the glow mesh, "Glow" (M_BdGlow: halos, beams, lasers).
"""
import math

import numpy as np

import bd_frame as Fr
import bd_mesh as M

SURF, LIGHT, SCREEN, GLOW = "Surface", "Lights", "Screen", "Glow"
MATS = (SURF, LIGHT, SCREEN)

# albedos (linear); the light map, the moon and the show light them in the material
BLACK = M.encode((0.035, 0.035, 0.040))
STAGE_DECK = M.encode((0.050, 0.050, 0.055))
TRUSS = M.encode((0.420, 0.425, 0.440))
TIMBER = M.encode((0.340, 0.240, 0.150))
TIMBER_DARK = M.encode((0.180, 0.120, 0.075))
TIMBER_IN = M.encode((0.400, 0.280, 0.170))          # the pavilion's timbers, lit warm by its own strings
ROOF_GREEN = M.encode((0.100, 0.220, 0.130))
STEEL = M.encode((0.300, 0.310, 0.330))
BARRIER = M.encode((0.055, 0.055, 0.060))           # black steel: its lit rail shows it
STONE = M.encode((0.340, 0.290, 0.230))
WHITE_CLOTH = M.encode((0.750, 0.750, 0.740))
# each albedo's kind (M_BdSurface UV1.y): which detail it takes
KIND_OF = {BLACK.tobytes(): M.KIND_GEAR, STAGE_DECK.tobytes(): M.KIND_GEAR, TRUSS.tobytes(): M.KIND_GEAR,
           TIMBER.tobytes(): M.KIND_WOOD, TIMBER_DARK.tobytes(): M.KIND_WOOD, TIMBER_IN.tobytes(): M.KIND_WOOD,
           ROOF_GREEN.tobytes(): M.KIND_GEAR, STEEL.tobytes(): M.KIND_GEAR, BARRIER.tobytes(): M.KIND_GEAR,
           STONE.tobytes(): M.KIND_STONE, WHITE_CLOTH.tobytes(): M.KIND_CLOTH}


def surf_aux(col):
    """UV1 for a Surface part of colour col: (0: bd_site.py fills the height in, the colour's kind)."""
    c = np.asarray(col, np.float32)
    kind = KIND_OF.get(c.tobytes(), M.KIND_GEAR) if c.ndim == 1 else M.KIND_GEAR
    return (np.array([0.0, float(kind)]),)


def light_aux(bright=1.0, mode=M.LIGHT_BULB):
    return (np.array([float(bright), float(mode)]),)


def aux_for(mat, col):
    return surf_aux(col) if mat == SURF else (light_aux() if mat == LIGHT else None)


def L(offset, warmth=0.0, step=1.0, phase=0.0):
    """A colour for the Lights material."""
    return np.array([offset % 1.0, warmth, step, phase % 1.0], np.float32)


class Part:
    """A builder's output: meshes (by asset name) and collision."""

    def __init__(self):
        self.meshes = {}
        self.floors, self.ramps, self.walls = [], [], []
        self.points = {}

    def mesh(self, name, materials=MATS):
        if name not in self.meshes:
            self.meshes[name] = M.Mesh(name, materials)
            self.meshes[name].aux_rule = aux_for
        return self.meshes[name]

    def merge(self, other):
        for k, m in other.meshes.items():
            if k in self.meshes:
                self.meshes[k].extend(m)
            else:
                self.meshes[k] = m
        self.floors += other.floors
        self.ramps += other.ramps
        self.walls += other.walls
        self.points.update(other.points)


class StageFrame:
    """Local stage frame (cm) <-> world (cm), with the ground under it."""

    def __init__(self, origin, yaw, ground):
        self.o = np.asarray(origin, np.float64)
        self.yaw = float(yaw)
        self.ground = ground            # ground(Xw, Yw) -> Zw (arrays)

    def w(self, P):
        return M.place(P, self.o, self.yaw)

    def wxy(self, poly):
        P = np.array([(x, y, 0.0) for x, y in poly])
        W = self.w(P)
        return [(float(a), float(b)) for a, b in W[:, :2]]

    def gz(self, x, y):
        """Ground height (local z) under local (x, y)."""
        W = self.w(np.stack([np.atleast_1d(x), np.atleast_1d(y), np.zeros(np.size(x))], axis=1))
        return self.ground(W[:, 0], W[:, 1]) - self.o[2]

    def add(self, mesh, V, F, col, UV, mat):
        mesh.add(self.w(V), F, col, UV, mat)

    def floor(self, part, x0, y0, x1, y1, z0, z1):
        part.floors.append((self.wxy([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]), self.o[2] + z0, self.o[2] + z1))

    def wall(self, part, x0, y0, x1, y1, z0, z1):
        part.walls.append((self.wxy([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]), self.o[2] + z0, self.o[2] + z1))

    def wall_post(self, part, x, y, r, z0, z1):
        P = [(x + r * math.cos(math.pi / 8 + k * math.pi / 4) / math.cos(math.pi / 8),
              y + r * math.sin(math.pi / 8 + k * math.pi / 4) / math.cos(math.pi / 8)) for k in range(8)]
        part.walls.append((self.wxy(P), self.o[2] + z0, self.o[2] + z1))


# ---- shared pieces --------------------------------------------------------------------------------------------------

def truss(mesh, sf, a, b, size=40.0, chord=5.0, lace=3.0, pitch=60.0):
    """A square box truss from a to b (local cm): four chords and zig-zag lacing on each face."""
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    d = b - a
    Ltot = float(np.linalg.norm(d))
    x = d / Ltot
    up = np.array([0.0, 0.0, 1.0]) if abs(x[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    y = np.cross(up, x)
    y /= np.linalg.norm(y)
    z = np.cross(x, y)
    h = size / 2
    corners = [(-h, -h), (h, -h), (h, h), (-h, h)]
    for cy, cz in corners:
        o = y * cy + z * cz
        V, F, UV = M.box_between(a + o, b + o, chord)
        sf.add(mesh, V, F, TRUSS, UV, SURF)
    n = max(1, int(Ltot // pitch))
    for f in range(4):
        (c0y, c0z), (c1y, c1z) = corners[f], corners[(f + 1) % 4]
        o0 = y * c0y + z * c0z
        o1 = y * c1y + z * c1z
        for k in range(n):
            t0, t1 = k / n, (k + 1) / n
            p0 = a + d * t0 + (o0 if k % 2 == 0 else o1)
            p1 = a + d * t1 + (o1 if k % 2 == 0 else o0)
            V, F, UV = M.box_between(p0, p1, lace)
            sf.add(mesh, V, F, TRUSS, UV, SURF)


def booth_table(part, mesh, sf):
    """The booth table every venue has (docs/venues.md): its drawn top 190 x 65 cm about the anchor, 74 cm over the
    DJ's floor; a black box with a glowing strip along its crowd face. Its anchor goes to part.points."""
    ax, ay = Fr.ANCHOR_AHEAD_CM, Fr.ANCHOR_RIGHT_CM
    hx, hy = Fr.TABLE_HALF[1], Fr.TABLE_HALF[0]          # depth along x, width along y
    V, F, UV = M.box(2 * hx, 2 * hy, Fr.TABLE_TOP_CM, (ax, ay, Fr.TABLE_TOP_CM / 2))
    sf.add(mesh, V, F, BLACK, UV, SURF)
    # the LED strip on the crowd face and a thin lip line on the top's front edge
    V, F, UV = M.box(2.0, 2 * hy - 10, 14.0, (ax + hx + 1.0, ay, 48.0))
    sf.add(mesh, V, F, L(0.0, 0.0, 1.0), UV, LIGHT)
    sf.wall(part, ax - hx, ay - hy, ax + hx, ay + hy, -10.0, 100.0)
    part.points["anchor"] = sf.w(np.array([[ax, ay, Fr.TABLE_TOP_CM]]))[0]
    part.points["dj"] = sf.w(np.array([[0.0, 0.0, 0.0]]))[0]


def stairs_sideways(part, mesh, sf, x0, x1, y_edge, outward, deck_z=0.0, riser_max=20.0, going=50.0, col=STAGE_DECK):
    """Stairs off a deck's side edge at y = y_edge, going outward (+1 / -1) in y, treads x0..x1. The foot is where the
    ground is within a riser of the last tread."""
    gz = float(np.min(sf.gz(np.array([x0, x1, x0, x1]), np.array([y_edge + outward * going * 6] * 2 + [y_edge] * 2))))
    drop = deck_z - gz
    n = max(1, int(math.ceil(drop / riser_max)))
    h = drop / n
    for k in range(1, n):
        ya = y_edge + outward * going * (k - 1)
        yb = y_edge + outward * going * k
        top = deck_z - h * k
        lo, hi = min(ya, yb), max(ya, yb)
        g = float(np.min(sf.gz(np.array([x0, x1, x0, x1]), np.array([lo, lo, hi, hi]))))
        V, F, UV = M.box(x1 - x0, hi - lo, top - (g - 30.0), ((x0 + x1) / 2, (lo + hi) / 2, (top + g - 30.0) / 2))
        sf.add(mesh, V, F, col, UV, SURF)
        sf.floor(part, x0, lo, x1, hi, g - 30.0, top)
    # handrails as walls on the open sides of the flight
    end = y_edge + outward * going * n
    lo, hi = min(y_edge, end), max(y_edge, end)
    sf.wall(part, x0 - 6.0, lo, x0 - 2.0, hi, gz - 10.0, deck_z + 110.0)
    sf.wall(part, x1 + 2.0, lo, x1 + 6.0, hi, gz - 10.0, deck_z + 110.0)
    return n


def stairs_forward(part, mesh, sf, y0, y1, x_edge, outward, deck_z, riser_max=20.0, going=50.0, col=TIMBER):
    """Stairs off an edge at x = x_edge going outward in x (treads y0..y1)."""
    gz = float(np.min(sf.gz(np.array([x_edge + outward * going * 5] * 2), np.array([y0, y1]))))
    drop = deck_z - gz
    if drop <= riser_max + 1.0:
        return 0
    n = max(1, int(math.ceil(drop / riser_max)))
    h = drop / n
    for k in range(1, n):
        xa = x_edge + outward * going * (k - 1)
        xb = x_edge + outward * going * k
        lo, hi = min(xa, xb), max(xa, xb)
        top = deck_z - h * k
        g = float(np.min(sf.gz(np.array([lo, hi, lo, hi]), np.array([y0, y0, y1, y1]))))
        V, F, UV = M.box(hi - lo, y1 - y0, top - (g - 30.0), ((lo + hi) / 2, (y0 + y1) / 2, (top + g - 30.0) / 2))
        sf.add(mesh, V, F, col, UV, SURF)
        sf.floor(part, lo, y0, hi, y1, g - 30.0, top)
    end = x_edge + outward * going * n
    lo, hi = min(x_edge, end), max(x_edge, end)
    sf.wall(part, lo, y0 - 6.0, hi, y0 - 2.0, gz - 10.0, deck_z + 110.0)
    sf.wall(part, lo, y1 + 2.0, hi, y1 + 6.0, gz - 10.0, deck_z + 110.0)
    return n


def led_line(mesh, sf, a, b, glow, rgb=None, pal=0.0, step=0.0, r=2.5, halo=13.0, spacing=38.0):
    """A LED line from a to b (local to sf): a tube (M_BdLights: neon in its own colour rgb, or a bulb strip in the
    show's palette from offset pal) and, with glow, a halo every spacing cm along it (world)."""
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    V, F, UV = M.box_between(a, b, r * 2.0)
    if rgb is not None:
        col = np.array([*(np.asarray(rgb) ** (1 / 2.2)), 0.0], np.float32)
        mesh.add(sf.w(V), F, col, UV, LIGHT, light_aux(1.0, M.LIGHT_NEON))
    else:
        mesh.add(sf.w(V), F, L(pal, 0.0, step, 0.0), UV, LIGHT, light_aux(1.0, M.LIGHT_BULB))
    if glow is not None:
        n = max(1, int(np.linalg.norm(b - a) / spacing))
        P = sf.w(np.array([a + (b - a) * (k + 0.5) / n for k in range(n)]))
        glow_halo(glow, P, halo, glow_col(pal, 0.0, step, 0.0), 0.5)


def mover(mesh, sf, x, y, z, offset, part=None):
    """A moving head hanging under a truss: body, yoke and a lens (the show's colour). With part, its lens (world) and
    palette offset go to part.points["movers"] for the glow's beams."""
    if part is not None:
        part.points.setdefault("movers", []).append((sf.w(np.array([[x, y, z - 78.0]]))[0].tolist(), sf.yaw, offset))
    V, F, UV = M.box(34, 34, 30, (x, y, z - 18))
    sf.add(mesh, V, F, BLACK, UV, SURF)
    V, F, UV = M.cylinder(15, 15, z - 72, z - 36, 8, cap_top=True, cap_bottom=True, center=(x, y))
    sf.add(mesh, V, F, BLACK, UV, SURF)
    V, F, UV = M.cylinder(11, 11, z - 76, z - 73, 8, cap_top=False, cap_bottom=True, center=(x, y))
    sf.add(mesh, V, F, L(offset, 0.0, 1.0, 0.1), UV, LIGHT)
    V, F, UV = M.box(26, 6, 6, (x + 13, y, z - 54))   # a front lens facing the crowd too
    sf.add(mesh, V, F, L(offset, 0.0, 1.0, 0.1), UV, LIGHT)


def screen(mesh, sf, x, y0, y1, z0, z1, frame=12.0, facing=1, back=True):
    """A screen at x facing +x (facing=1) or -x (-1): the picture (UV 0..1, u to the viewer's right, v down) and a
    black frame and back behind it. Vertex colour R: the picture's aspect (width / height / 4)."""
    aspect = (y1 - y0) / max(z1 - z0, 1.0) / 4.0
    if facing > 0:
        # seen from +x the viewer's right is -y: u runs from y1 to y0
        V, F, UV = M.quad((x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1), ((1, 1), (0, 1), (0, 0), (1, 0)))
    else:
        V, F, UV = M.quad((x, y1, z0), (x, y0, z0), (x, y0, z1), (x, y1, z1), ((1, 1), (0, 1), (0, 0), (1, 0)))
    n = np.cross(V[F[0, 1]] - V[F[0, 0]], V[F[0, 2]] - V[F[0, 0]])
    if n[0] * facing < 0:
        F = F[:, ::-1]
    sf.add(mesh, V, F, np.array([aspect, 1.0, 1.0, 1.0], np.float32), UV, SCREEN)
    if back:
        V, F, UV = M.box(20.0, (y1 - y0) + 2 * frame, (z1 - z0) + 2 * frame, (x - 11.0 * facing, (y0 + y1) / 2, (z0 + z1) / 2))
        sf.add(mesh, V, F, BLACK, UV, SURF)


def festoon_string(mesh, sf, a, b, sag, spacing, offset, warmth=0.75, step=0.5, r=7.0, world=False, glow=None,
                   halo=None):
    """Bulbs on a hanging string from a to b (local to sf, or world). With glow (a Part's glow mesh) each bulb also gets
    a halo halo cm across (default 2.4 x r) there, in world coordinates."""
    P = M.catenary(a, b, sag, max(3, int(np.linalg.norm(np.subtract(b, a)) / spacing)))
    cols = np.array([L(offset + 0.37 * i, warmth, step, i * 0.173) for i in range(len(P))])
    if glow is None:
        V, F, UV = M.bulbs(P, r)
        k = len(V) // len(P)
        if world:
            mesh.add(V, F, np.repeat(cols, k, 0), UV, LIGHT)
        else:
            sf.add(mesh, V, F, np.repeat(cols, k, 0), UV, LIGHT)
    else:
        Pw = P if world else sf.w(P)
        glow_halo(glow, Pw, halo if halo is not None else r * 2.4, cols, 0.85)
    # no wire: at night only the bulbs show, and a wire per span would cost more triangles than its bulbs


# ---- the Main Stage ------------------------------------------------------------------------------------------------

def main_stage(sf, rng, glow=None):
    """The Stone Circle Stage (plan 6.1), all of it inside the Stone Circle (stone_circle(), bd_layout.STONE_CIRCLE):
    the deck at the ring's east end, a box-truss roof with moving heads, a 12 x 6.75 m LED wall, the lit sun emblem
    over it, LED pillars beside the stage and out in the crowd, PA stacks, the crowd barrier 4 m off the lip and a FOH
    tent 35 m out, short of the far stones."""
    part = Part()
    m = part.mesh("SM_BdMainStage")
    # deck: x -650..350 (the DJ 3.5 m from its front edge), y -800..800, top at the DJ's floor
    gmin = float(np.min(sf.gz(np.array([-650, 350, -650, 350, -150]), np.array([-800, -800, 800, 800, 0]))))
    V, F, UV = M.box(1000, 1600, -gmin + 40, (-150, 0, (gmin - 40) / 2))
    sf.add(m, V, F, STAGE_DECK, UV, SURF)
    sf.floor(part, -650, -800, 350, 800, gmin - 40, 0.0)
    # a glowing edge strip along the deck's front lip
    V, F, UV = M.box(3, 1600, 5, (351.5, 0, -6))
    sf.add(m, V, F, L(0.125, 0.0, 1.0), UV, LIGHT)
    booth_table(part, m, sf)
    # stairs off both sides at the back
    for s in (-1, 1):
        stairs_sideways(part, m, sf, -560.0, -410.0, s * 800.0, s, 0.0)
    # the LED wall, its frame and the sun emblem over it
    screen(m, sf, -600.0, -600.0, 600.0, 80.0, 755.0)
    for k in range(14):
        a = 2 * math.pi * k / 14
        p0 = (-612.0, 0.0 + math.cos(a) * 95, 900.0 + math.sin(a) * 95)
        p1 = (-612.0, 0.0 + math.cos(a) * 165, 900.0 + math.sin(a) * 165)
        V, F, UV = M.box_between(p0, p1, 9.0)
        sf.add(m, V, F, L(0.25, 1.0, 0.0, k * 0.07), UV, LIGHT)
    V, F, UV = M.cylinder(80, 80, -625, -615, 16, cap_top=True, cap_bottom=True)
    V = V[:, [2, 0, 1]] + np.array([0.0, 0.0, 900.0])   # turned to face +x: its axis along x
    V[:, 0] = V[:, 0] * 1.0
    sf.add(m, V, F, L(0.25, 1.0, 0.0, 0.5), UV, LIGHT)
    # truss: four towers to 10 m, the roof grid and a lighting bar
    H = 1000.0
    for x in (-650.0, 350.0):
        for y in (-830.0, 830.0):
            g = float(sf.gz(np.array([x]), np.array([y]))[0])
            truss(m, sf, (x, y, g - 20), (x, y, H), 40.0)
            sf.wall(part, x - 35, y - 35, x + 35, y + 35, g - 10.0, g + 250.0)
            V, F, UV = M.box(70, 70, 20, (x, y, g - 5))
            sf.add(m, V, F, BLACK, UV, SURF)
    truss(m, sf, (350, -850, H), (350, 850, H), 40.0)
    for dz in (-24.0, 24.0):
        led_line(m, sf, (372.0, -850.0, H + dz), (372.0, 850.0, H + dz), glow, None, 0.75, 1.0)
    truss(m, sf, (-650, -850, H), (-650, 850, H), 40.0)
    truss(m, sf, (-670, -830, H), (370, -830, H), 40.0)
    truss(m, sf, (-670, 830, H), (370, 830, H), 40.0)
    truss(m, sf, (-150, -830, H - 40), (-150, 830, H - 40), 30.0)
    # moving heads under the front truss and the mid bar, blinders on the front
    for i, y in enumerate(np.linspace(-700, 700, 8)):
        mover(m, sf, 350.0, float(y), H - 22, i * 0.125, part)
    for i, y in enumerate(np.linspace(-650, 650, 6)):
        mover(m, sf, -150.0, float(y), H - 55, 0.5 + i * 0.125, part)
    for y in (-120.0, 120.0):
        V, F, UV = M.box(16, 90, 45, (372.0, y, H - 60))
        sf.add(m, V, F, BLACK, UV, SURF)
        for dy in (-22.0, 22.0):
            for dz in (-11.0, 11.0):
                V, F, UV = M.cylinder(9, 9, 0, 4, 8, cap_top=True)
                V = V[:, [2, 0, 1]] + np.array([381.0, y + dy, H - 60 + dz])
                sf.add(m, V, F, L(0.0, 1.0, 0.0, 0.3), UV, LIGHT)
    # PA: a stack each side, on the ground in front of the deck's corners
    for s in (-1, 1):
        y = s * 1000.0
        g = float(sf.gz(np.array([250.0]), np.array([y]))[0])
        V, F, UV = M.box(120, 140, 380, (250.0, y, g + 190))
        sf.add(m, V, F, BLACK, UV, SURF)
        sf.wall(part, 190.0, y - 70, 310.0, y + 70, g - 10, g + 250)
        for k in range(4):
            V, F, UV = M.box(2, 110, 8, (311.0, y, g + 60 + k * 90))
            sf.add(m, V, F, L(0.6, 0.0, 1.0, k * 0.2), UV, LIGHT)
    # LED pillars: beside the stage and out among the crowd (plan: "at least three more per side"), the far pair 3.5 m
    # in from the ring's stones and 5.5 m off the circle walk's way in
    pillars = [(0.0, -1180.0), (0.0, 1180.0), (1500.0, -1700.0), (1500.0, 1700.0), (2900.0, -1800.0), (2900.0, 1800.0)]
    for i, (x, y) in enumerate(pillars):
        g = float(sf.gz(np.array([x]), np.array([y]))[0])
        V, F, UV = M.box(90, 170, 120, (x - 15, y, g + 60))
        sf.add(m, V, F, BLACK, UV, SURF)
        V, F, UV = M.box(40, 150, 720, (x - 5, y, g + 470))
        sf.add(m, V, F, BLACK, UV, SURF)
        # both faces play: the crowd behind them and the stage see them
        screen(m, sf, x + 16, y - 65, y + 65, g + 120, g + 820, back=False)
        screen(m, sf, x - 26, y - 65, y + 65, g + 120, g + 820, facing=-1, back=False)
        sf.wall(part, x - 60, y - 85, x + 40, y + 85, g - 10, g + 250)
        part.points.setdefault("pillars", []).append(sf.w(np.array([[x, y, g]]))[0].tolist())
    # the crowd barrier, 4 m off the lip, -1100..1100
    bx = 750.0
    ys = np.linspace(-1100, 1100, 23)
    for i in range(len(ys) - 1):
        y0, y1 = ys[i], ys[i + 1]
        g0 = float(sf.gz(np.array([bx]), np.array([(y0 + y1) / 2]))[0])
        V, F, UV = M.box(8, y1 - y0 - 4, 120, (bx, (y0 + y1) / 2, g0 + 60))
        sf.add(m, V, F, BARRIER, UV, SURF)
        V, F, UV = M.box(90, y1 - y0 - 4, 4, (bx + 45, (y0 + y1) / 2, g0 + 2))
        sf.add(m, V, F, BARRIER, UV, SURF)
        V, F, UV = M.box_between((bx, y0 + 2, g0 + 118), (bx + 60, y0 + 2, g0 + 4), 5)
        sf.add(m, V, F, BARRIER, UV, SURF)
        V, F, UV = M.box(4, y1 - y0 - 4, 3, (bx, (y0 + y1) / 2, g0 + 121.5))
        sf.add(m, V, F, L(0.125 * i, 0.0, 1.0, i * 0.09), UV, LIGHT)
        sf.wall(part, bx - 8, y0, bx + 8, y1, g0 - 10, g0 + 125)
    # FOH: a canopy 35 m out with its desk
    fx, fy = 3500.0, 0.0
    g = float(sf.gz(np.array([fx]), np.array([fy]))[0])
    for dx in (-200.0, 200.0):
        for dy in (-200.0, 200.0):
            V, F, UV = M.box(8, 8, 260, (fx + dx, fy + dy, g + 130))
            sf.add(m, V, F, STEEL, UV, SURF)
            sf.wall_post(part, fx + dx, fy + dy, 8.0, g - 10, g + 250)
    V, F, UV = M.box(420, 420, 10, (fx, fy, g + 265))
    sf.add(m, V, F, BLACK, UV, SURF)
    V, F, UV = M.box(120, 260, 95, (fx + 40, fy, g + 47))
    sf.add(m, V, F, BLACK, UV, SURF)
    V, F, UV = M.box(40, 200, 3, (fx + 20, fy, g + 97))
    sf.add(m, V, F, L(0.75, 0.3, 0.3, 0.4), UV, LIGHT)
    sf.wall(part, fx - 25, fy - 135, fx + 105, fy + 135, g - 10, g + 120)
    return part


# ---- the Pavilion --------------------------------------------------------------------------------------------------

def pavilion(sf, rng, hall_floor_z, glow=None):
    """The Dance and Dining Pavilion (plan 6.2): a 21.3 x 9.1 m timber post-and-beam hall, its green metal gable roof,
    open sides with a rail, the wooden floor on piers, the stage at the WNW gable end (an LED wall, a 20 cm DJ riser),
    moving heads on the beams and string lights. hall_floor_z: the hall's floor, local (the DJ stands 20 cm over it)."""
    part = Part()
    m = part.mesh("SM_BdPavilion")
    x0, x1, hw = -250.0, 1880.0, 455.0
    fz = hall_floor_z
    # the floor on piers
    gmin = float(np.min(sf.gz(np.array([x0, x1, x0, x1, (x0 + x1) / 2]), np.array([-hw, -hw, hw, hw, 0.0]))))
    V, F, UV = M.box(x1 - x0, 2 * hw, 12, ((x0 + x1) / 2, 0, fz - 6))
    sf.add(m, V, F, TIMBER_IN, UV, SURF)
    sf.floor(part, x0, -hw, x1, hw, gmin - 30.0, fz)
    for xp in np.linspace(x0 + 40, x1 - 40, 8):
        for yp in (-hw + 40, 0.0, hw - 40):
            g = float(sf.gz(np.array([xp]), np.array([yp]))[0])
            if fz - 12 - g > 5:
                V, F, UV = M.box(30, 30, fz - 12 - (g - 20), (xp, yp, (fz - 12 + g - 20) / 2))
                sf.add(m, V, F, TIMBER_DARK, UV, SURF)
    # the DJ riser and the booth
    V, F, UV = M.box(400, 400, 20, (-50, 0, -10))
    sf.add(m, V, F, STAGE_DECK, UV, SURF)
    sf.floor(part, -250, -200, 150, 200, fz - 5, 0.0)
    V, F, UV = M.box(3, 400, 4, (151.5, 0, -6))
    sf.add(m, V, F, L(0.5, 0.0, 1.0), UV, LIGHT)
    booth_table(part, m, sf)
    # posts, ties, rafters, knee braces
    eave, ridge = fz + 360.0, fz + 650.0
    xs = np.linspace(x0, x1, 7)
    for x in xs:
        for s in (-1, 1):
            y = s * 440.0
            g = float(sf.gz(np.array([x]), np.array([y]))[0])
            V, F, UV = M.box(25, 25, eave - (g - 20), (x, y, (eave + g - 20) / 2))
            sf.add(m, V, F, TIMBER_IN, UV, SURF)
            sf.wall_post(part, x, y, 14.0, fz - 10, fz + 250)
            V, F, UV = M.box_between((x, y, fz + 250), (x, s * 290.0, eave - 10), 12)
            sf.add(m, V, F, TIMBER_IN, UV, SURF)
        V, F, UV = M.box_between((x, -455, eave - 8), (x, 455, eave - 8), 18)
        sf.add(m, V, F, TIMBER_IN, UV, SURF)
        for s in (-1, 1):
            V, F, UV = M.box_between((x, s * 515.0, eave - 25), (x, 0.0, ridge), 16)
            sf.add(m, V, F, TIMBER_IN, UV, SURF)
        V, F, UV = M.box_between((x, 0, eave - 8), (x, 0, ridge), 12)
        sf.add(m, V, F, TIMBER_IN, UV, SURF)
    # the plates along the eaves and the ridge beam
    for s in (-1, 1):
        V, F, UV = M.box_between((x0 - 60, s * 440.0, eave), (x1 + 60, s * 440.0, eave), 20)
        sf.add(m, V, F, TIMBER_IN, UV, SURF)
    V, F, UV = M.box_between((x0 - 60, 0.0, ridge), (x1 + 60, 0.0, ridge), 20)
    sf.add(m, V, F, TIMBER_IN, UV, SURF)
    # the roof: two planes of green metal over boards
    for s in (-1, 1):
        a = (x0 - 70, 0.0, ridge + 14)
        b = (x1 + 70, 0.0, ridge + 14)
        c = (x1 + 70, s * 525.0, eave - 20)
        d = (x0 - 70, s * 525.0, eave - 20)
        V = np.array([a, b, c, d], np.float64)
        Fq = np.array([(0, 1, 2), (0, 2, 3)]) if s > 0 else np.array([(0, 2, 1), (0, 3, 2)])
        n = np.cross(V[Fq[0, 1]] - V[Fq[0, 0]], V[Fq[0, 2]] - V[Fq[0, 0]])
        if n[2] < 0:
            Fq = Fq[:, ::-1]
        sf.add(m, V, Fq, ROOF_GREEN, np.zeros((4, 2), np.float32), SURF)
        Vb = V - np.array([0, 0, 10.0])
        sf.add(m, Vb, Fq[:, ::-1], TIMBER_DARK, np.zeros((4, 2), np.float32), SURF)
        led_line(m, sf, (x0 - 70, s * 527.0, eave - 18), (x1 + 70, s * 527.0, eave - 18), glow, (1.0, 0.20, 0.65), 0.875)
        for xe in (x0 - 70, x1 + 70):
            led_line(m, sf, (xe, s * 527.0, eave - 18), (xe, 0.0, ridge + 16), glow, (1.0, 0.20, 0.65), 0.875)
        # the gable ends' boards (triangles), both ends
    for x in (x0 - 20, x1 + 20):
        V = np.array([(x, -440.0, eave), (x, 440.0, eave), (x, 0.0, ridge)], np.float64)
        sf.add(m, V, np.array([(0, 1, 2), (0, 2, 1)]), TIMBER_DARK, np.zeros((3, 2), np.float32), SURF)
    # the LED wall at the WNW gable (behind the DJ), 6.4 x 3.6 m, and its back wall
    screen(m, sf, x0 + 25, -320.0, 320.0, fz + 40.0, fz + 400.0)
    sf.wall(part, x0 - 30, -455.0, x0 + 15, 455.0, fz - 10, fz + 250)
    # the rail: 1 m along both sides, open in the middle bay and at the ESE end
    gap0, gap1 = xs[3] - 10, xs[4] + 10
    for s in (-1, 1):
        for xa, xb in ((x0, gap0), (gap1, x1)):
            V, F, UV = M.box_between((xa, s * 450.0, fz + 100), (xb, s * 450.0, fz + 100), 10)
            sf.add(m, V, F, TIMBER_IN, UV, SURF)
            V, F, UV = M.box_between((xa, s * 450.0, fz + 45), (xb, s * 450.0, fz + 45), 6)
            sf.add(m, V, F, TIMBER_IN, UV, SURF)
            sf.wall(part, xa, s * 450.0 - 6, xb, s * 450.0 + 6, fz - 10, fz + 110)
        stairs_sideways(part, m, sf, gap0 + 10, gap1 - 10, s * hw, s, fz, col=TIMBER)
    stairs_forward(part, m, sf, -300.0, 300.0, x1, 1, fz, col=TIMBER)
    # the ESE end's rail beside its stairs
    for s in (-1, 1):
        V, F, UV = M.box_between((x1, s * 300.0, fz + 100), (x1, s * 455.0, fz + 100), 10)
        sf.add(m, V, F, TIMBER_IN, UV, SURF)
        sf.wall(part, x1 - 6, min(s * 300.0, s * 455.0), x1 + 6, max(s * 300.0, s * 455.0), fz - 10, fz + 110)
    # moving heads on the ties, string lights along the eaves and across the hall
    for i, x in enumerate(xs[1:-1]):
        for s in (-1, 1):
            mover(m, sf, x, s * 200.0, eave - 18, 0.25 * i + (0.5 if s > 0 else 0.0), part)
    for k in range(len(xs) - 1):
        for s in (-1, 1):
            festoon_string(m, sf, (xs[k], s * 430.0, eave - 30), (xs[k + 1], s * 430.0, eave - 30), 45, 40.0, 0.1 * k, 0.8, 0.4,
                           4.5, glow=glow)
        festoon_string(m, sf, (xs[k], -400.0, eave - 25), (xs[k + 1], 400.0, eave - 25), 70, 50.0, 0.5 + 0.1 * k, 0.2, 1.0, 5.0,
                       glow=glow)
    return part


# ---- New Camp -------------------------------------------------------------------------------------------------------

def newcamp_stage(sf, rng, glow=None):
    """The New Camp Stage (plan 6.3): a 12 x 7 m deck 1 m high, a goal-post truss carrying a white projection screen
    and a lighting bar, PA stacks, a low barrier."""
    part = Part()
    m = part.mesh("SM_BdNewCampStage")
    gmin = float(np.min(sf.gz(np.array([-450, 250, -450, 250]), np.array([-600, -600, 600, 600]))))
    V, F, UV = M.box(700, 1200, -gmin + 40, (-100, 0, (gmin - 40) / 2))
    sf.add(m, V, F, TIMBER_DARK, UV, SURF)
    sf.floor(part, -450, -600, 250, 600, gmin - 40, 0.0)
    V, F, UV = M.box(3, 1200, 5, (251.5, 0, -6))
    sf.add(m, V, F, L(0.375, 0.0, 1.0), UV, LIGHT)
    booth_table(part, m, sf)
    for s in (-1, 1):
        stairs_sideways(part, m, sf, -400.0, -260.0, s * 600.0, s, 0.0, col=TIMBER_DARK)
    H = 720.0
    for s in (-1, 1):
        y = s * 680.0
        g = float(sf.gz(np.array([-430.0]), np.array([y]))[0])
        truss(m, sf, (-430.0, y, g - 20), (-430.0, y, H), 30.0)
        sf.wall(part, -460, y - 30, -400, y + 30, g - 10, g + 250)
    truss(m, sf, (-430.0, -700.0, H), (-430.0, 700.0, H), 30.0)
    led_line(m, sf, (-410.0, -700.0, H + 20), (-410.0, 700.0, H + 20), glow, (0.10, 0.85, 0.80), 0.5)
    for s in (-1, 1):
        led_line(m, sf, (-410.0, s * 680.0, 0.0), (-410.0, s * 680.0, H), glow, (0.10, 0.85, 0.80), 0.5)
    # the white screen (the show's picture on cloth) in a black frame
    screen(m, sf, -410.0, -350.0, 350.0, 150.0, 550.0, 8.0)
    for i, y in enumerate(np.linspace(-550, 550, 6)):
        mover(m, sf, -430.0, float(y), H - 18, 0.2 * i, part)
    for s in (-1, 1):
        y = s * 820.0
        g = float(sf.gz(np.array([150.0]), np.array([y]))[0])
        V, F, UV = M.box(100, 110, 260, (150.0, y, g + 130))
        sf.add(m, V, F, BLACK, UV, SURF)
        sf.wall(part, 100.0, y - 55, 200.0, y + 55, g - 10, g + 250)
    bx = 500.0
    ys = np.linspace(-700, 700, 15)
    for i in range(len(ys) - 1):
        y0, y1 = ys[i], ys[i + 1]
        g0 = float(sf.gz(np.array([bx]), np.array([(y0 + y1) / 2]))[0])
        V, F, UV = M.box(6, y1 - y0 - 4, 100, (bx, (y0 + y1) / 2, g0 + 50))
        sf.add(m, V, F, BARRIER, UV, SURF)
        V, F, UV = M.box(4, y1 - y0 - 4, 3, (bx, (y0 + y1) / 2, g0 + 101.5))
        sf.add(m, V, F, L(0.375 + 0.125 * i, 0.0, 1.0, i * 0.09), UV, LIGHT)
        sf.wall(part, bx - 7, y0, bx + 7, y1, g0 - 10, g0 + 105)
    # bunting strings from the truss towers out to the first trees' height (lights for the crowd field)
    for s in (-1, 1):
        festoon_string(m, sf, (-430.0, s * 680.0, H - 40), (900.0, s * 1300.0, 420.0), 120, 50.0, 0.25 * (s + 1), 0.3, 1.0, 8.0,
                       glow=glow)
    return part


# ---- bridges ---------------------------------------------------------------------------------------------------------

def along(poly, t):
    """The point at fraction t (0..1, scalar or array) of a polyline's length."""
    P = np.asarray(poly, np.float64)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    d = np.asarray(t, np.float64) * cum[-1]
    return np.stack([np.interp(d, cum, P[:, k]) for k in range(3)], axis=-1)


def bridge(world_a, world_b, width, kind, rng, name, glow=None):
    """A footbridge between two world points (the deck's ends, on the ground): the deck as a walking ramp, rails as
    walls. kind "suspension": the Rainbow Bridge's pylons, cables, hangers, mesh sides and six rainbow strips; "beam":
    a timber deck on beams with a post-and-rail."""
    part = Part()
    m = part.mesh("SM_BdBridges")
    a = np.asarray(world_a, np.float64)
    b = np.asarray(world_b, np.float64)
    d = b - a
    Lxy = float(np.hypot(d[0], d[1]))
    ux = np.array([d[0], d[1], 0.0]) / Lxy
    side = np.array([-ux[1], ux[0], 0.0])
    # the deck runs 1.5 m onto each bank level with its end (bd_site.py cuts a level pad there and the paths arriving
    # there run level for their last 3 m), and is level for its first and last 4 m too, so the landings' benches (cut
    # level round the ends) meet it at its own height; it climbs between them
    ext = 150.0
    land = min(400.0, Lxy * 0.2)
    n = max(4, int(Lxy / 100) + 1)
    s_ = np.concatenate([[-ext], np.linspace(0.0, Lxy, n), [Lxy + ext]])
    zs = np.interp(s_, [0.0, land, Lxy - land, Lxy], [a[2], a[2], b[2], b[2]])
    pts = np.stack([a[0] + ux[0] * s_, a[1] + ux[1] * s_, zs], axis=1)
    hw = width / 2
    deck_col = TIMBER if kind == "beam" else STEEL
    # the deck: top ribbon + thickness (a closed beam) and its walking surface
    top = pts + np.array([0, 0, 3.0])
    V, F, UV = M.ribbon(top, width)
    m.add(V, F, TIMBER, UV, SURF)
    Vb, Fb, UVb = M.ribbon(top - np.array([0, 0, 25.0]), width)
    m.add(Vb, Fb[:, ::-1], deck_col, UVb, SURF)
    for s in (-1, 1):
        edge = top + side * s * hw
        for i in range(len(edge) - 1):
            V, F, UV = M.box_between(edge[i] - np.array([0, 0, 12.0]), edge[i + 1] - np.array([0, 0, 12.0]), 25.0, 25.0)
            m.add(V, F, deck_col, UV, SURF)
    Vr, Fr_, _ = M.ribbon(top, width + 4.0)
    part.ramps.append((Vr, Fr_))
    # rails (walls) both sides
    for s in (-1, 1):
        rail = top + side * s * (hw + 3.0)
        for i in range(len(rail) - 1):
            p0, p1 = rail[i], rail[i + 1]
            poly = [(p0[0] - side[0] * 4, p0[1] - side[1] * 4), (p1[0] - side[0] * 4, p1[1] - side[1] * 4),
                    (p1[0] + side[0] * 4, p1[1] + side[1] * 4), (p0[0] + side[0] * 4, p0[1] + side[1] * 4)]
            part.walls.append((poly, min(p0[2], p1[2]) - 10.0, max(p0[2], p1[2]) + 250.0))
    # rails and posts (visual)
    post_n = max(2, int(Lxy / 200) + 1)
    for s in (-1, 1):
        rail = top + side * s * hw
        for i in range(len(rail) - 1):
            V, F, UV = M.box_between(rail[i] + np.array([0, 0, 110.0]), rail[i + 1] + np.array([0, 0, 110.0]), 6.0)
            m.add(V, F, deck_col, UV, SURF)
            V, F, UV = M.box_between(rail[i] + np.array([0, 0, 50.0]), rail[i + 1] + np.array([0, 0, 50.0]), 4.0)
            m.add(V, F, deck_col, UV, SURF)
        for t in np.linspace(0, 1, post_n):
            p = along(rail, t)
            V, F, UV = M.box_between(p, p + np.array([0, 0, 112.0]), 8.0)
            m.add(V, F, deck_col, UV, SURF)
    if kind == "suspension":
        # the rainbow: six bands along both top rails (fixed colours, pulsing with the show) and along the cables
        for s in (-1, 1):
            rail = top + side * s * hw + np.array([0, 0, 116.0])
            for band in range(6):
                t0, t1 = band / 6, (band + 1) / 6
                for q in range(4):
                    p0 = along(rail, t0 + (t1 - t0) * q / 4)
                    p1 = along(rail, t0 + (t1 - t0) * (q + 1) / 4)
                    V, F, UV = M.box_between(p0, p1, 5.0)
                    m.add(V, F, L(band / 8.0, 0.0, 0.0, band * 0.11), UV, LIGHT)
        # pylons (A-frames) at both ends, cables, hangers
        tops = []
        for end, sgn in ((a, -1.0), (b, 1.0)):
            base = end + ux * sgn * 60.0
            g = base[2]
            for s in (-1, 1):
                foot = base + side * s * (hw + 70.0) - np.array([0, 0, 40.0])
                head = base + side * s * (hw + 10.0) + np.array([0, 0, 620.0 + 3.0])
                V, F, UV = M.box_between(foot, head, 22.0)
                m.add(V, F, STEEL, UV, SURF)
                V, F, UV = M.box_between(foot + np.array([0, 0, 40.0]), head - np.array([0, 0, 40.0]), 4.0)
                m.add(V, F, L(band_off(s), 0.0, 0.0, 0.2), UV, LIGHT)
                part.walls.append(([(foot[0] - 20, foot[1] - 20), (foot[0] + 20, foot[1] - 20), (foot[0] + 20, foot[1] + 20),
                                    (foot[0] - 20, foot[1] + 20)], g - 50.0, g + 250.0))
                tops.append(head)
            V, F, UV = M.box_between(base + side * -(hw + 10.0) + np.array([0, 0, 600.0]),
                                     base + side * (hw + 10.0) + np.array([0, 0, 600.0]), 20.0)
            m.add(V, F, STEEL, UV, SURF)
        for s_i, s in enumerate((-1, 1)):
            ta = tops[0 + s_i]
            tb = tops[2 + s_i]
            cable = M.catenary(ta, tb, 360.0, 24)
            for i in range(len(cable) - 1):
                V, F, UV = M.box_between(cable[i], cable[i + 1], 4.0)
                m.add(V, F, STEEL, UV, SURF)
                # a strip of LEDs along the cable, the rainbow's bands from end to end
                band = int(6 * i / (len(cable) - 1))
                V, F, UV = M.box_between(cable[i] + np.array([0, 0, 3.0]), cable[i + 1] + np.array([0, 0, 3.0]), 2.4)
                m.add(V, F, L(band / 8.0, 0.0, 0.0, i * 0.05), UV, LIGHT, light_aux(1.3, M.LIGHT_BULB))
                if glow is not None:
                    glow_halo(glow, [(cable[i] + cable[i + 1]) / 2 + np.array([0, 0, 3.0])], 26.0, glow_col(band / 8.0, 0.0, 0.0, i * 0.05), 0.6)
            # hangers down to the rail
            rail = top + side * s * hw + np.array([0, 0, 110.0])
            for k in range(1, len(cable) - 1, 2):
                t = k / (len(cable) - 1)
                pr = along(rail, t)
                pc = cable[k]
                if pc[2] > pr[2] + 20:
                    V, F, UV = M.box_between(pc, pr, 1.6)
                    m.add(V, F, STEEL, UV, SURF)
                    V, F, UV = M.bulbs([pc], 7.0)
                    m.add(V, F, L(k / 24.0, 0.0, 0.0, k * 0.05), UV, LIGHT)
                    if glow is not None:
                        glow_halo(glow, [pc], 30.0, glow_col(k / 24.0, 0.0, 0.0, k * 0.05), 0.7)
    else:
        # warm bulbs along the beam bridge's rails
        for s in (-1, 1):
            rail = top + side * s * hw + np.array([0, 0, 115.0])
            P = along(rail, np.linspace(0, 1, max(3, int(Lxy / 70))))
            V, F, UV = M.bulbs(P, 6.0)
            m.add(V, F, np.repeat(np.array([L(0.1 * i, 1.0, 0.0, 0.17 * i) for i in range(len(P))]), len(V) // len(P), 0), UV, LIGHT)
            if glow is not None:
                glow_halo(glow, P, 16.0, glow_col(0.0, 1.0, 0.0, 0.0), 0.8)
    part.points[name] = [a.tolist(), b.tolist()]
    return part


def band_off(s):
    return 0.0 if s < 0 else 5.0 / 8.0


# ---- the glow (M_BdGlow, additive): halos, beams, lasers -------------------------------------------------------------

def glow_halo(mesh, P, size, col, bright=1.0, kind=M.GLOW_HALO):
    """Halos (or domes, flames: kind) at world points P (n, 3): a quad each, its corners 0.5 cm round its centre (the
    vertex shader turns it to the eye; UV2.x its half size in cm). col: (4,) or (n, 4) for M_BdGlow."""
    P = np.asarray(P, np.float64).reshape(-1, 3)
    n = len(P)
    if n == 0:
        return
    corners = np.array([(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)])
    V = (P[:, None, :] + np.concatenate([corners * 0.5, np.zeros((4, 1))], 1)[None, :, :]).reshape(-1, 3)
    F = (np.array([(0, 1, 2), (0, 2, 3)])[None, :, :] + (np.arange(n) * 4)[:, None, None]).reshape(-1, 3)
    C = np.asarray(col, np.float32)
    C = np.repeat(C.reshape(n, 4), 4, 0) if C.ndim == 2 else np.broadcast_to(C, (4 * n, 4))
    sz = np.repeat(np.broadcast_to(np.asarray(size, np.float64), (n,)), 4)
    br = np.repeat(np.broadcast_to(np.asarray(bright, np.float64), (n,)), 4)
    x = M.aux(4 * n, None, np.stack([sz, np.zeros(4 * n)], 1), np.stack([np.full(4 * n, float(kind)), br], 1))
    mesh.add(V, F, C, np.tile(corners, (n, 1)), GLOW, x)


def glow_ribbon(mesh, P, yaw, pitch, length, width, kind, col, bright=1.0, segs=6):
    """A beam, laser or sky beam (kind) from world point P toward (yaw, pitch) degrees, length cm, half width at its
    source cm: segs quads along it (t = UV0.y 0..1, s = UV0.x -1..1), built and swept in the vertex shader."""
    P = np.asarray(P, np.float64).reshape(3)
    t = np.linspace(0.0, 1.0, segs + 1)
    st = np.array([(sx, tt) for tt in t for sx in (-1.0, 1.0)])
    V = P[None, :] + np.concatenate([st * 0.5, np.zeros((len(st), 1))], 1)
    F = []
    for k in range(segs):
        a, b, c, d = 2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2
        F += [(a, b, c), (a, c, d)]
    n = len(V)
    x = M.aux(n, np.array([yaw, pitch]), np.array([length, width]), np.array([float(kind), bright]))
    mesh.add(V, np.array(F), np.asarray(col, np.float32), st, GLOW, x)


def glow_col(offset, warmth=0.0, step=1.0, phase=0.0):
    return np.array([offset % 1.0, warmth, step, phase % 1.0], np.float32)


def flame_slab(w, th, h, levels=9):
    """The Flame Stone's body (its own frame: x across its broad face, y through it, z up from 25 cm under the ground):
    a slab that narrows to a tip, bows toward its face and sways in an S, in levels rings of four corners."""
    V, UV = [], []
    for k in range(levels + 1):
        t = k / levels
        hw = w / 2 * (1.0 - 0.80 * t ** 1.6)
        ht = th / 2 * (1.0 - 0.45 * t)
        bow = 0.10 * h * math.sin(math.pi * 0.85 * t)
        sway = 0.07 * h * math.sin(2.0 * math.pi * t + 0.4) * t
        z = -25.0 + (h + 25.0) * t
        for cx_, cy_ in ((-hw, -ht), (hw, -ht), (hw, ht), (-hw, ht)):
            V.append((cx_ + sway, cy_ + bow, z))
            UV.append(((cx_ + hw) / 100.0, z / 100.0))
    F = []
    for k in range(levels):
        for e in range(4):
            a, b = 4 * k + e, 4 * k + (e + 1) % 4
            c, d = 4 * (k + 1) + (e + 1) % 4, 4 * (k + 1) + e
            F += [(a, b, c), (a, c, d)]
    top = 4 * levels
    F += [(top, top + 1, top + 2), (top, top + 2, top + 3)]
    return np.array(V, np.float64), np.array(F), np.array(UV, np.float32)


# ---- the Stone Circle ----------------------------------------------------------------------------------------------

def stone_circle(frame, ground, rng, cfg, keep_out):
    """The Stone Circle (plan 5.7), which is the Main Stage: cfg["stones"] standing stones all the way round the
    61 x 49 m ellipse, evenly along its length from the east end (behind the stage), the stage and its crowd inside.
    The Flame Stone (22 ft) stands at the far, west end, facing the stage down the long axis.

    A stone that would come within keep_out(Xw, Yw, half_width_cm) (a path, so the gap is the way in; the stage's
    structures) is left out. The stage's light (the light map) covers the ring, so each stone takes the show's colours
    on its face toward the stage; its foot is a little shaded (vertex alpha, M_BdSurface's shade: 0.25 at the ground),
    and a small lamp (M_BdLights) stands at its inner foot. Returns the part; points: "stones" (placed), "ring" (the
    stones' line, world), "gaps" (the left-out slots, world)."""
    part = Part()
    m = part.mesh("SM_BdStones", (SURF, LIGHT))
    cx, cy = cfg["center"]
    ra, rb, rot = cfg["ra"], cfg["rb"], math.radians(cfg["rot"])
    ux, uy, vx, vy = math.cos(rot), math.sin(rot), -math.sin(rot), math.cos(rot)
    n = cfg["stones"]
    # the ellipse as a fine polyline from its east end (t = 0) round through the south (t = 90: crop +v), and its length
    ts = np.radians(np.linspace(0.0, 360.0, 3601))
    ex, ey = ra * np.cos(ts), rb * np.sin(ts)
    px, py = cx + ex * ux + ey * vx, cy + ex * uy + ey * vy
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(px), np.diff(py)))])
    step = s[-1] / n
    placed = 0
    gaps = []
    for i in range(n):
        # even steps along the ring, each stone nudged up to 12 % of a step either way (a circle raised by hand)
        si = (i * step + rng.uniform(-0.12, 0.12) * step) % s[-1] if i != n // 2 else s[-1] / 2
        t = float(np.interp(si, s, ts))
        x = cx + ra * math.cos(t) * ux + rb * math.sin(t) * vx
        y = cy + ra * math.cos(t) * uy + rb * math.sin(t) * vy
        h = rng.uniform(220, 430) if i != n // 2 else 670.0       # the Flame Stone (22 ft) at the far side
        w = rng.uniform(80, 240)
        th = rng.uniform(40, 62)
        narrow = rng.uniform(0.75, 0.95)
        lean = rng.uniform(-0.04, 0.04)
        jitter = rng.uniform(-8, 8)
        shade = rng.uniform(0.8, 1.15)
        W = frame.world(x, y, 0.0)
        Xw, Yw = float(W[0]), float(W[1])
        if keep_out(Xw, Yw, w / 2 + 3.0):
            gaps.append([Xw, Yw])
            continue
        g = float(ground(np.array([Xw]), np.array([Yw]))[0])
        # tangent of the ellipse at t, in crop metres -> world yaw: the stone's broad face looks at the ring's middle
        tx = -ra * math.sin(t) * ux + rb * math.cos(t) * vx
        ty = -ra * math.sin(t) * uy + rb * math.cos(t) * vy
        yaw = Fr.Frame.yaw_of_crop_dir(tx, ty) + jitter
        if i == n // 2:
            # the Flame Stone: a tall slab of rusty sandstone that bows a little under its own weight and narrows to a
            # leaping tip (the research: "becomes a leaping flame"); two warm floodlights at its foot make it glow
            V, F, UV = flame_slab(w, th, h)
        else:
            V, F, UV = M.box(w, th, h, (0, 0, h / 2 - 25))
            V[V[:, 2] > h / 2, 0] *= narrow                          # narrower at the top
        V[:, 1] += V[:, 2] * lean
        occ = 0.25 * (1.0 - np.clip((V[:, 2] + 25.0) / 80.0, 0.0, 1.0))   # a little shade at the foot
        hgt = np.maximum(V[:, 2], 0.0) / 100.0
        V = M.place(V, (Xw, Yw, g), yaw)
        rgb = (np.array([0.42, 0.25, 0.16]) if i == n // 2 else np.array([0.34, 0.29, 0.23])) * shade
        m.add(V, F, M.encode(np.repeat(rgb[None, :], len(V), 0), occ), UV, SURF,
              (np.stack([hgt, np.full(len(V), float(M.KIND_STONE))], 1),))
        fw, fy = M.basis_from_yaw(yaw)
        # the lamp: a low can on the ground 70 cm in from the stone toward the ring's middle, its lens toward the stone;
        # every other lamp takes the palette's opposite colour
        o = np.array([Xw, Yw]) - np.asarray(frame.world(cx, cy, 0.0), np.float64)[:2]
        o /= max(float(np.linalg.norm(o)), 1e-6)
        lamp = np.array([Xw, Yw]) - o * (th / 2 + 70.0)
        gl = float(ground(np.array([lamp[0]]), np.array([lamp[1]]))[0])
        lyaw = math.degrees(math.atan2(o[1], o[0]))
        Vl, Fl, UVl = M.box(24, 24, 22, (0.0, 0.0, 6.0))
        m.add(M.place(Vl, (lamp[0], lamp[1], gl), lyaw), Fl, BLACK, UVl, SURF)
        Vl, Fl, UVl = M.box(3, 18, 16, (13.5, 0.0, 8.0))
        m.add(M.place(Vl, (lamp[0], lamp[1], gl), lyaw), Fl, L(0.5 * (i % 2), 0.0, 1.0, i * 0.11), UVl, LIGHT)
        if i == n // 2:
            for side in (-1.0, 1.0):
                q = np.array([Xw, Yw]) - o * (th / 2 + 160.0) + np.array([-o[1], o[0]]) * side * 80.0
                gq = float(ground(np.array([q[0]]), np.array([q[1]]))[0])
                Vq, Fq, UVq = M.box(30, 30, 26, (0.0, 0.0, 10.0))
                m.add(M.place(Vq, (q[0], q[1], gq), lyaw + 180.0), Fq, BLACK, UVq, SURF)
                Vq, Fq, UVq = M.box(3, 24, 20, (-16.5, 0.0, 12.0))
                m.add(M.place(Vq, (q[0], q[1], gq), lyaw + 180.0), Fq, L(0.0, 1.0, 0.0, 0.3), UVq, LIGHT, light_aux(1.2, M.LIGHT_WARM))
            part.points["flame_stone"] = [Xw, Yw, g, float(h)]
        corners = [np.array([Xw, Yw]) + fw * sx * (w / 2 + 3) + fy * sy * (th / 2 + 3) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        part.walls.append(([tuple(c) for c in corners], g - 10.0, g + 250.0))
        placed += 1
    part.points["stones"] = placed
    part.points["gaps"] = gaps
    ring = frame.world(px[::50], py[::50], 0.0)[:, :2]
    part.points["ring"] = ring.tolist()
    return part


# ---- tents and festoons ------------------------------------------------------------------------------------------

TENT_COLOURS = [(0.240, 0.250, 0.280), (0.120, 0.200, 0.120), (0.260, 0.160, 0.096), (0.104, 0.136, 0.240),
                (0.280, 0.240, 0.120), (0.200, 0.120, 0.200)]
TENT_LIT = (1.00, 0.52, 0.20)          # a lit tent's fabric: the lamp inside shows through it (M_BdLights, lantern)


def tent(part, mesh, X, Y, g, yaw, kind, lit, rng, shown=None):
    """A tent. lit decides the random draws (as the first build made them, so every tent after it stands where it
    stood); shown (default lit) whether it is lit: its fabric glowing from the lamp inside."""
    shown = lit if shown is None else shown
    col = np.array(TENT_LIT if lit else TENT_COLOURS[rng.integers(len(TENT_COLOURS))])
    if lit and not shown:
        col = np.array(TENT_COLOURS[int(abs(X * 0.37 + Y * 0.11)) % len(TENT_COLOURS)])
    lit, glowing = shown, lit
    cloth = (LIGHT, light_aux(0.42, M.LIGHT_LANTERN)) if lit else (SURF, (np.array([0.0, float(M.KIND_CLOTH)]),))
    if kind == "dome":
        V, F, UV = M.cone(130.0, -10.0, 135.0, 8, skirt=False)
        V[:, 0] *= 1.15
        V = M.place(V, (X, Y, g), yaw)
        mesh.add(V, F, M.encode(col, (X * 0.000137 + Y * 0.000071) % 1.0 if lit else 0.0), UV, cloth[0], cloth[1])
        part.walls.append((octa_poly(X, Y, 125.0), g - 10.0, g + 140.0))
    elif kind == "bell":
        V, F, UV = M.cylinder(200, 200, -10, 85, 10, cap_top=False)
        V = M.place(V, (X, Y, g), yaw)
        mesh.add(V, F, M.encode(col, 0.3 if lit else 0.0), UV, cloth[0], cloth[1])
        V, F, UV = M.cone(215.0, 85.0, 300.0, 10, skirt=False)
        V = M.place(V, (X, Y, g), yaw)
        mesh.add(V, F, M.encode(col * 0.85, 0.6 if lit else 0.0), UV, cloth[0], cloth[1])
        part.walls.append((octa_poly(X, Y, 200.0), g - 10.0, g + 250.0))
    else:  # canopy (3 x 3 m)
        for dx in (-140.0, 140.0):
            for dy in (-140.0, 140.0):
                V, F, UV = M.box(6, 6, 245, (dx, dy, 122))
                V = M.place(V, (X, Y, g), yaw)
                mesh.add(V, F, STEEL, UV, SURF)
                p = M.place(np.array([[dx, dy, 0.0]]), (X, Y, g), yaw)[0]
                part.walls.append((octa_poly(p[0], p[1], 6.0), g - 10.0, g + 250.0))
        V = np.array([(-150, -150, 240), (150, -150, 240), (150, 150, 240), (-150, 150, 240), (0, 0, 300)], np.float64)
        F = np.array([(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (0, 2, 1), (0, 3, 2)])
        V = M.place(V, (X, Y, g), yaw)
        mesh.add(V, F, M.encode(np.minimum(col * 1.2, 1.0), 0.8 if lit else 0.0), np.zeros((5, 2), np.float32), cloth[0], cloth[1])
    if glowing:
        phase = rng.uniform(0, 1)
        if lit:
            V, F, UV = M.box(16, 16, 22, (0.0, 0.0, 0.0))
            p = M.place(np.array([[150.0 if kind != "canopy" else 0.0, 0.0, 30.0 if kind != "canopy" else 200.0]]), (X, Y, g), yaw)[0]
            mesh.add(V + p, F, L(0.0, 1.0, 0.0, phase), UV, LIGHT, light_aux(1.0, M.LIGHT_WARM))
            part.points.setdefault("lit_tents", []).append((float(X), float(Y), float(g)))


def octa_poly(x, y, r):
    R = r / math.cos(math.pi / 8)
    return [(x + R * math.cos(math.pi / 8 + k * math.pi / 4), y + R * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]


def festoons(path_world, half_width, rng, spacing=2200.0, height=450.0, offset=0.0, glow=None):
    """Poles beside a path (world points along it, with the ground's z) and strings of bulbs between them."""
    part = Part()
    m = part.mesh("SM_BdFestoons")
    P = np.asarray(path_world, np.float64)
    seg = np.linalg.norm(np.diff(P[:, :2], axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] < spacing * 0.6:
        return part
    k = max(2, int(round(s[-1] / spacing)) + 1)
    poles = []
    for i, t in enumerate(np.linspace(0, s[-1], k)):
        j = min(int(np.searchsorted(s, t, side="right")) - 1, len(P) - 2)
        f = (t - s[j]) / max(seg[j], 1e-6)
        p = P[j] + (P[j + 1] - P[j]) * f
        d = (P[j + 1] - P[j])[:2]
        d = d / max(np.linalg.norm(d), 1e-6)
        side = np.array([-d[1], d[0]]) * (1 if i % 2 == 0 else -1)
        q = np.array([p[0] + side[0] * (half_width + 60.0), p[1] + side[1] * (half_width + 60.0), p[2]])
        poles.append(q)
        V, F, UV = M.cylinder(7, 5, -30, height, 6, center=(0.0, 0.0))
        m.add(V + q, F, TIMBER_DARK, UV, SURF)
        part.walls.append((octa_poly(q[0], q[1], 10.0), q[2] - 10.0, q[2] + 250.0))
    for i in range(len(poles) - 1):
        a = poles[i] + np.array([0, 0, height - 15])
        b = poles[i + 1] + np.array([0, 0, height - 15])
        festoon_string(m, None, a, b, 70.0, 60.0, offset + 0.13 * i, 0.75, 0.5, 7.0, world=True, glow=glow)
    part.points["poles"] = len(poles)
    part.points["pole_list"] = [q.tolist() for q in poles]
    part.points["height"] = height
    return part
