"""bd_layout.py: where BIG DUB's things stand (crop metres: x east, y south; bd_frame.py), from the user's plan
(claudedocs/bigdub_stage_plan.md sections 1.3, 4.2, 5 and 6; the Blender blockout's STAGES table) checked against the
1 m DEM. The plan marks every stage position "assumed, +-40-50 m"; where the DEM disagreed with a point it was moved
the least distance onto real ground, and the reason is written next to it.

Facings use the blockout's convention: degrees, 0 = east (+x), 90 = north (-y); the stage faces its crowd.
"""
import math

# ---- the Stone Circle, which is the Main Stage -----------------------------------------------------------------------
# The ring (plan 5.7): an ellipse 61 x 49 m (200 x 160 ft) on the knoll, its long axis turned 12 degrees north of east
# (its short one 12 degrees west of north). The user, 2026-10-30: the Stone Circle is the Main Stage. Its 62 stones go
# all the way round, and the stage (deck, truss roof, LED wall, pillars, PA, barrier, FOH) stands inside the ring at its
# east end, on the long axis, facing down it over the crowd, who fill the rest of the ring. The first build had the
# stage outside the ring's east end and the stones over only 240 degrees, open toward it.
# The Main Stage's DJ keeps the plan's booth point (1210, 130) and the ring is placed round it: its centre is
# ra - stage_inset back along the long axis, (1193.9, 133.4), 14 m east of the plan's (1180, 130). At the plan's centre
# the ring's west end stood on the cutting of the ravine trail's switchback (cut 4-5 m into the bank there: 25-53
# degrees, not walkable), inside and outside the stones; from 10 m east on, both are walkable all round.
# stage_inset: how far in from the ring's east end (on the long axis) the DJ stands: the deck then stands 4.9 m clear of
# the nearest stone and the feet of its back stairs 2.6 m.
MAIN_DJ = (1210.0, 130.0)
STONE_CIRCLE = dict(ra=30.5, rb=24.5, rot=-12.0, stones=62, stage_inset=14.0)
_k = STONE_CIRCLE["ra"] - STONE_CIRCLE["stage_inset"]
STONE_CIRCLE["center"] = (round(MAIN_DJ[0] - _k * math.cos(math.radians(STONE_CIRCLE["rot"])), 3),
                          round(MAIN_DJ[1] - _k * math.sin(math.radians(STONE_CIRCLE["rot"])), 3))


def ring_axes(sc=None):
    """The ring's centre and unit axes in crop metres: u along the long axis toward its east end, v along the short."""
    sc = sc or STONE_CIRCLE
    r = math.radians(sc["rot"])
    return sc["center"], (math.cos(r), math.sin(r)), (-math.sin(r), math.cos(r))


def ring_uv(cx, cy, sc=None):
    """Crop points (floats or arrays) in the ring's own axes (metres along u and v from its centre)."""
    (x0, y0), (ux, uy), (vx, vy) = ring_axes(sc)
    dx, dy = cx - x0, cy - y0
    return dx * ux + dy * uy, dx * vx + dy * vy


def ring_radius(cx, cy, sc=None):
    """The ellipse's own radius of crop points: 1 on the stones' line, under 1 inside the ring."""
    sc = sc or STONE_CIRCLE
    a, b = ring_uv(cx, cy, sc)
    return ((a / sc["ra"]) ** 2 + (b / sc["rb"]) ** 2) ** 0.5


def ring_point(t_deg, scale=1.0, sc=None):
    """The point of the ring at its parameter t (degrees; 0 = the east end, 90 = the south side), scaled about the
    centre (1 = the stones' line)."""
    sc = sc or STONE_CIRCLE
    (x0, y0), (ux, uy), (vx, vy) = ring_axes(sc)
    t = math.radians(t_deg)
    a, b = sc["ra"] * math.cos(t) * scale, sc["rb"] * math.sin(t) * scale
    return x0 + a * ux + b * vx, y0 + a * uy + b * vy


# The Main Stage faces down the ring's long axis, west-south-west (blockout 192 degrees; the first build faced due west).
_MAIN_FACING = round(math.degrees(math.atan2(math.sin(math.radians(STONE_CIRCLE["rot"])),
                                             -math.cos(math.radians(STONE_CIRCLE["rot"])))) % 360.0, 3)

# The world frame's origin (bd_frame.py; world X = -(y - its y) x 100, Y = (x - its x) x 100 + 90, Z = 0 on its floor):
# the Main Stage's DJ spot, the floor 1.2 m over the ground there, as in the first build, so every spot and probe
# keeps its world coordinates (the Main Stage's DJ still stands at (0, 90, 0); only its facing turned 12 degrees).
FRAME_ORIGIN = MAIN_DJ
FRAME_FLOOR_OVER_GROUND_M = 1.2

# ---- the three DJ spots ----------------------------------------------------------------------------------------------
# dj: where the DJ stands (crop m); facing (blockout degrees); deck: the DJ's floor over the ground there (m).
SPOTS = {
    # The Main Stage, inside the Stone Circle (above): the plan's booth point, 14 m in from the ring's east end on the
    # knoll (252 m, 4-6 degrees), facing west-south-west down the ring's long axis over the crowd inside it.
    "Main": dict(label="MAIN STAGE", dj=MAIN_DJ, facing=_MAIN_FACING, deck=1.2),
    # The Pavilion: the plan's (1072, 76) is the top of the ravine's 25-33 degree bank; the hall goes 14 m east onto
    # the shelf's flat (249 m, 2 degrees: the flattest ground within 30 m), its stage at the WNW gable end, facing
    # ESE along the hall and out of its open end into Camp Central (the plan's "south-east", yaw -30).
    "Pavilion": dict(label="PAVILION", dj=(1086.0, 76.0), facing=-30.0, deck=0.85),
    # New Camp: the plan's (1060, 650) is on the 40-55 degree bluff south of the west run (the DEM has no 240 m
    # terrace there: the bank climbs from the water at 226.6 m to the plateau at 269 m within 55 m). The stage goes
    # 40 m south onto the plateau's edge (269-271 m, 3 degrees), facing the plan's south-west over the Old Forest's
    # side; the Rainbow Bridge lands on the bluff below it and a trail climbs to the stage.
    "NewCamp": dict(label="NEW CAMP", dj=(1072.0, 690.0), facing=-150.0, deck=1.0),
}
SPOT_ORDER = ("Main", "Pavilion", "NewCamp")

# ---- paths (crop m): [(x, y)...], width m, kind ("gravel" 4 m roads, "dirt" 2-3 m trails). The profile is the
# ground's, smoothed, with its grade held to MAX_GRADE: where the ground is steeper across or along, the path is cut into
# the slope as a bench (bd_site.py carve()). ------------------------------------------------------------------------
MAX_GRADE = 0.27                          # 15 degrees: a trail's bench stays well under the walk's 25
PATHS = [
    # The shelf road (OSM's private farm road, Bridgeport Road's spur, as the aerial shows it): the Pavilion along the
    # shelf, then round the outside of the Stone Circle's north side and behind the Main Stage (the ring's east end),
    # 9-14 m off the stones' line, so the ring has no gap for it. The farm road's own line ran through where the ring and
    # the stage stand now; it is moved out round them by up to 18 m.
    dict(name="shelf_road", kind="gravel", width=4.0, festoon=True,
         pts=[(1093.0, 60.0), (1125.0, 77.0), (1160.0, 93.0), (1185.0, 99.0), (1205.0, 100.0), (1222.0, 105.0),
              (1234.0, 116.0), (1238.0, 130.0), (1242.0, 142.0)]),
    # The crowd's way from the Pavilion's open end along the shelf into the Stone Circle: it crosses the ring square on
    # at its north-west side (the stones leave the way in there) and ends 8 m inside, in the crowd. Kept 17 m and more
    # off the ravine trail's switchback, which is cut 5 m lower.
    dict(name="circle_walk", kind="dirt", width=3.0, festoon=True,
         pts=[(1103.0, 86.0), (1135.0, 100.0), (1157.5, 111.5), (1175.4, 126.0)]),
    # The Pavilion down the ravine's bank to the floodplain: two legs cut into the bank (it is 25-33 degrees here).
    dict(name="ravine_trail", kind="dirt", width=2.6, festoon=True,
         pts=[(1103.0, 92.0), (1128.0, 112.0), (1146.0, 132.0), (1122.0, 142.0), (1098.0, 145.0), (1085.5, 150.5)]),
    # The Big Bottom: the footbridge's south end, south through the woods to White Pines and the Rainbow Bridge.
    dict(name="bottom_path", kind="dirt", width=3.0, festoon=True,
         pts=[(1068.5, 171.5), (1076.0, 225.0), (1090.0, 290.0), (1103.0, 360.0), (1108.0, 440.0), (1104.0, 520.0),
              (1100.0, 570.0), (1100.0, 598.0)]),
    # A loop through the Big Bottom's east woods (the camps), back to the main path.
    dict(name="bottom_loop", kind="dirt", width=2.4, festoon=True,
         pts=[(1090.0, 290.0), (1135.0, 320.0), (1160.0, 380.0), (1150.0, 450.0), (1108.0, 470.0)]),
    # White Pines to the Hemlock Hole's beach (the elbow pool).
    dict(name="beach_path", kind="dirt", width=2.4, festoon=False,
         pts=[(1104.0, 520.0), (1140.0, 545.0), (1170.0, 560.0)]),
    # The bluff trail: the Rainbow Bridge's south landing up the 40-55 degree bluff to the plateau, in two legs.
    dict(name="bluff_trail", kind="dirt", width=2.6, festoon=True,
         pts=[(1100.0, 637.0), (1068.0, 644.0), (1036.0, 652.0), (1030.0, 658.0), (1062.0, 666.0), (1092.0, 674.0),
              (1094.0, 682.0)]),
    # New Camp: the plateau path past the stage's back to its crowd field and the tents.
    dict(name="camp_path", kind="dirt", width=3.0, festoon=True,
         pts=[(1094.0, 682.0), (1082.0, 700.0), (1060.0, 712.0), (1030.0, 718.0), (1005.0, 712.0)]),
]

# ---- bridges (crop m): end points (the deck's ends on the banks), deck width m, kind -------------------------------
BRIDGES = [
    # The Rainbow Bridge (plan 5.6): a suspension footbridge over the west run just downstream (west) of the elbow
    # pool, from the beach at White Pines to the bluff. Its strips in six rainbow bands.
    dict(name="rainbow", a=(1100.0, 598.0), b=(1100.0, 637.0), width=1.8, kind="suspension"),
    # A timber footbridge over the ravine's creek between the floodplain and the Big Bottom (ours: the DEM has the
    # creek there and the plan's walk from the stages to the bridge crosses it).
    dict(name="ravine_footbridge", a=(1085.5, 150.5), b=(1068.5, 171.5), width=2.2, kind="beam"),
]

# ---- where walking is allowed (crop m polygons; the walkable ground is inside them, not water, under 25 degrees after
# the paths are cut, and joined to the stages) ------------------------------------------------------------------------
MAX_WALK_SLOPE_DEG = 25.0
WALK_REGIONS = [
    # the shelf (the Main Stage's knoll, the Stone Circle, Camp Central, the Pavilion), the ravine's bank and its
    # floodplain, the Big Bottom and White Pines down to the west run: one outline; the creek and the banks over 25
    # degrees fall out of it by themselves
    [(1050.0, 40.0), (1150.0, 55.0), (1262.0, 100.0), (1268.0, 175.0), (1215.0, 205.0), (1205.0, 260.0),
     (1215.0, 330.0), (1222.0, 430.0), (1215.0, 520.0), (1180.0, 580.0), (1120.0, 612.0), (1040.0, 600.0),
     (975.0, 520.0), (965.0, 380.0), (985.0, 240.0), (1010.0, 150.0), (1040.0, 95.0)],
    # the bluff trail's corridor and New Camp's plateau
    [(1020.0, 632.0), (1112.0, 630.0), (1125.0, 660.0), (1135.0, 700.0), (1120.0, 760.0), (1040.0, 772.0),
     (985.0, 752.0), (985.0, 700.0), (1010.0, 668.0)],
]

# ---- the terrain's extent (crop m) ------------------------------------------------------------------------------------
CORE = (900.0, -20.0, 1380.0, 800.0)     # 2 m terrain tiles with LODs (the walk and its surroundings)
CORE_TILES = (3, 5)                      # columns x rows: 160 x 164 m tiles (no sliver row: a tile is a draw)
OUTER_STEP_M = 20.0                      # the rest of the extended DEM, one mesh: 20 m divides the core's offsets from
                                         # EXT's corner (1100, 1580, 380, 1200 m), so the hole is cut on the core's edges
FAR_STEP_M = 50.0                        # the DEM tile's ring around the crop (the horizon)
CANOPY_STEP_M = 24.0                     # the far woods' canopy surface, one mesh

# ---- trees ------------------------------------------------------------------------------------------------------------
NEAR_TREE_MARGIN_M = 70.0                # instanced trees inside the walk regions and this far around them
TREE_SPACING_M = 7.5                     # mean spacing in the woods (Poisson-ish)
# which trees carry lights (bd_site.py place_trees): most round the stages, the woods between them dark
LIT_RING = 1.75                          # round the Main Stage: inside 1.75 x the Stone Circle's ellipse (~23 m past it)
LIT_STAGE_M = 40.0                       # round the Pavilion's and New Camp's crowds
LIT_PATH_M = 9.0                         # now and then (22 %) a tree this close to a festooned path: a lantern to walk by

# ---- camps (crop m rects) and tents per hectare -----------------------------------------------------------------------
CAMPS = [
    dict(name="newcamp", rect=(995.0, 690.0, 1125.0, 760.0), per_ha=75),
    dict(name="bigbottom_west", rect=(1000.0, 230.0, 1080.0, 420.0), per_ha=22),
    dict(name="bigbottom_east", rect=(1115.0, 300.0, 1200.0, 470.0), per_ha=26),
    dict(name="white_pines", rect=(1060.0, 520.0, 1160.0, 575.0), per_ha=30),
    dict(name="camp_central", rect=(1060.0, 50.0, 1100.0, 75.0), per_ha=40),
]
