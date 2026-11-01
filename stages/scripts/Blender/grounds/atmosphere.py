"""Festival-grounds module: atmosphere. Xenon sky trackers behind the crowd and behind the stage, the stage's moving
heads frozen in one programmed look (STAGE_AIMS / STAGE_ANGLES / STAGE_COLORS, for re-aiming and re-coloring the
fixtures in dino_stage.py), sweeping lasers ("lasers": a fan from the stage front over the crowd, and laser heads on the
tips of the high horns firing into the crowd; animated in UE by the material, see LASER_UV and laser_pose()), and glow
sprites on the brightest lenses. Beams, lasers and halos use the kit's texture layout (T_DinoBeam / T_DinoHalo) and
ship alpha-blended.

The look, as a lighting designer would call it: deck lip = a cyan fan (up and out) interleaved with amber crossers
(three pairs crossing over the crowd at different depths); tower tops = white wings (three beams per tower spreading
outward from near vertical); sky trackers = an X and a V behind the crowd, an X high behind the skull; lasers = a
green fan breathing over the crowd from the stage front, and eight horn-tip heads (horns 3-6 each side, green / cyan /
green / red from the top; the tips come from ../arch.py) scanning into the crowd in mirrored pairs, rippling down the
arch.
Checked by atmosphere_lasercheck.py (UV contract, DJ head, floor, stage clearance over the whole sweep)."""
import math
import os
import sys

from kit import *

_BLENDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # Scripts/Blender: the stage's own modules
if _BLENDER not in sys.path:
    sys.path.append(_BLENDER)
import arch  # noqa: E402  (the stage arch, v2: the horn tips the laser heads sit on)

NAME = "atmosphere"
BAKE_SIZE = 1024

# ------------------------------------------------------------------ stage fixtures (dino_stage.build_rig, pre-drop)
HEAD_UP, LENS_OUT = 0.42, 0.205          # moving_head(): head center above the base; lens disc in front of the center
TOWER_BASES = [(x, -3.0, 16.75) for x in (-13.9, -12.8, -11.7, 13.9, 12.8, 11.7)]
DECK_BASES = [(float(x), -4.3, 0.0) for x in range(-19, 20, 3)]
PILLAR_TOPS = [(x, 0.5, 6.0) for x in (-21.0, -9.5, 9.5, 21.0)]


def aim(pan, tilt):
    """Unit direction: pan in degrees from -Y (toward the crowd) toward +X, tilt in degrees above the horizon.
    Same as dino_stage.moving_head() with yaw_deg = pan, pitch_deg = -tilt."""
    p, t = math.radians(pan), math.radians(tilt)
    return Vector((math.sin(p) * math.cos(t), -math.cos(p) * math.cos(t), math.sin(t)))


def lens_center(base, d):
    """Where the integration puts the re-aimed fixture's lens: base + (0, 0, 0.42) + d * 0.205, d normalized."""
    return Vector(base) + Vector((0, 0, HEAD_UP)) + Vector(d).normalized() * LENS_OUT


def _stage_look():
    """(base, pan, tilt, color, beam length, beam end width) per fixture: tower tops, then the deck lip left to right."""
    look = []
    for i, base in enumerate(TOWER_BASES):
        side, k = (-1 if base[0] < 0 else 1), i % 3                   # k = 0 outermost
        look.append((base, side * 70.0, 54.0 + 13 * k, "white", 65.0, 2.8))              # wings
    for i, base in enumerate(DECK_BASES):
        s = i - 6                                                      # -6..6 (center fixture at x=-1)
        if i % 2 == 0:
            look.append((base, 6.5 * s, 58.0 - 2 * abs(s), "cyan", 75.0, 3.0))           # fan, up and out
        else:
            t = abs(s) // 2                                            # 0 inner .. 2 outer pair
            look.append((base, -math.copysign(11 + 11 * t, s), 44.0 - 6 * t, "amber", 65.0, 2.6))   # crossers
    return look


STAGE_LOOK = _stage_look()
STAGE_AIMS = [(tuple(lens_center(b, aim(p, t))), tuple(aim(p, t)))
              for b, p, t, *_ in STAGE_LOOK]                       # (lens center, unit direction) per fixture, unrounded:
                                                                   # each stage beam starts exactly at its lens center
STAGE_ANGLES = [(-t, p) for _, p, t, *_ in STAGE_LOOK]             # moving_head(..., pitch_deg, yaw_deg, ...)
STAGE_COLORS = [c for _, _, _, c, _, _ in STAGE_LOOK]              # BEAM_COLS key per fixture (lens disc color)

# ------------------------------------------------------------------ v13: the moving heads move
# Each fixture turns as one about its head's center (mover_pose_pq), driven per bar by the laser engine's patterns
# (dino_materials MOVER_MOTION_HLSL; at most MOVER_FMAX cycles a bar, like real heads). STAGE_MOVES: per fixture the
# five LASER_UV values its head, lens, glow and beam all carry (the yoke the same with tilt 0).
MOVER_FMAX = 2.0
MOVER_AMP = {"white": (30.0, 10.0), "cyan": (22.0, 14.0), "amber": (16.0, 10.0)}   # wings, deck fan, crossers (deg)


def _stage_moves():
    moves, deck = [], [i for i, look in enumerate(STAGE_LOOK) if look[0][2] < 1]
    for i, (base, pan, tilt, color, _len, _w1) in enumerate(STAGE_LOOK):
        pv = Vector(base) + Vector((0, 0, HEAD_UP))
        if base[2] > 1:                                                # wings: outermost +-1, inner +-0.2
            side, k = (-1 if base[0] < 0 else 1), i % 3
            u = side * (1.0 - 0.4 * k)
        else:                                                          # deck lip: -1..1 left to right
            j = deck.index(i)
            u = (j - (len(deck) - 1) / 2) / ((len(deck) - 1) / 2)
        pa, ta = MOVER_AMP[color]
        moves.append(((pv.x, pv.y), (pv.z, (0.37 * i) % 1.0), (pa, ta), (pan, u), ((base[0] + 25.0) / 50.0, 0.0)))
    return moves


STAGE_MOVES = _stage_moves()


def stamp_uv(faces, layers, values):
    """Every loop of these faces gets values[i] in layers[i]."""
    for f in faces:
        for lp in f.loops:
            for lay, val in zip(layers, values):
                lp[lay].uv = val


# ------------------------------------------------------------------ sky trackers: unit center, heads' (pan, tilt)
TRACKERS = [
    ((-32.0, -92.0), [(80, 55), (-60, 70)]),      # behind the crowd: inner heads cross over the field, outer lean out
    ((32.0, -92.0), [(-80, 55), (60, 70)]),
    ((-30.0, 22.0), [(120, 55)]),                  # behind the stage: lean in and back, crossing high behind the skull
    ((30.0, 22.0), [(-120, 55)]),
]
TRACKER_LEN = 340.0

# ------------------------------------------------------------------ sweeping lasers v2 ("lasers"; WPO-animated in UE)
# The user (2026-10-08): "the lazers need to be coming from the actual lazer things on the stage, currently there off
# from it or coming out of nowhere so we just need to upgrade the quality", and "All of them" for which: real laser
# units with lit apertures on the horn tips, the tower tops and the stage front, every beam leaving its unit's
# aperture. Motion and color come from the material's pattern engine (show.py T_DinoLaserLib / T_DinoLaserProg,
# dino_materials.laser_show); this module gives each beam its unit, its place in the unit's fan and its range.
# Every laser vertex carries five UV layers after "UVMap", in this order (pre-drop Blender meters, degrees):
#   LaserPivot (pivot.x, pivot.y), LaserPivotZPhase (pivot.z, phase 0..1), LaserAmp (pan_amp, tilt_amp: what the
#   engine's pan / tilt of +-1 mean for this beam; 0 for an aperture glow), LaserCue (group, u = the beam's place in
#   its unit's fan, -1 = toward -X .. 1), LaserFix (x = the unit's place across the rig, 0 = the -X end .. 1; kind:
#   0 = beam, 1 = aperture glow).
#   Groups and their show.py cue rows: 0 = the center fan (row 3), 1..4 = horn pairs k6, k5, k4, k3 (rows 4-7),
#   5 = tower units (row 11), 6 = stage-front units (row 12).
LASER_UV = ("LaserPivot", "LaserPivotZPhase", "LaserAmp", "LaserCue", "LaserFix")
LASER_GAP = 0.1               # beams start 10 cm out from their pivot (the aperture), so every vertex sits close to the
                              # beam axis as seen from the pivot: a tilt axis taken per vertex stays well defined
FLOOR_MARGIN = 0.3            # at its lowest sweep extreme a laser ends this far above the crowd floor
LAND_Z = 0.25                 # rest aim points: the crowd's head height
BEAM_W = (0.02, 0.10)         # beam width at the aperture / at the far end (v8: 0.03-0.04 / 0.15-0.2): crisp lines
BEAM_CORE, BEAM_V1 = 0.35, 0.85   # beam(): the middle 35% of the white column's profile; fade just before the end
UNIT_BOX = (0.5, 0.46, 0.3)   # every laser housing: depth (along its aim heading), width, height

# center fan: one unit on a 0.5 m road case on the deck lip, center stage (between the x=-1 and x=2 fixtures)
LASER_UNIT = (0.5, -4.22, 0.65)                    # housing center; the aperture is on its crowd-side face
LASER_ANGS = [-40 + 5 * k for k in range(17)]      # degrees within the fan plane (v10: 17 lines, v9: 13)
LASER_TILT, LASER_LEN = 17.0, 58.0                 # the fan plane rises 17 deg toward the crowd
FAN_PAN, FAN_TILT = 12.0, 4.0                      # what the engine's +-1 means for the fan (checked over the barrier
                                                   # row and the first flags by atmosphere_lasercheck.py)

# horn heads: {(side, k): (last point of horn k's center line, its unit tangent there)} for horns 3..6 of each wing,
# pre-drop, from the arch itself (arch.horn_tips(): the wings are mirror images); the tip cone point is 0.11 m past
# the last point along the tangent, and the head sits on it
HORN_TIPS = arch.horn_tips((3, 4, 5, 6))
HORN_FANS = {   # (-1, horn k) = the -X head: (beams, rest aim point (x, y) at LAND_Z, degrees between beams, pan amp,
                #   tilt amp). The +X head is its mirror image (aim (-x, y)). Rest aims are 10, 20, 28, 16 deg off -Y
                #   toward the center, 24, 28, 32, 34 deg down (v8 kept every sweep >= 1 m from the stage, the skull
                #   and the towers; the v9 ranges are re-checked by atmosphere_lasercheck.py)
    (-1, 6): (7, (3.7, -56.6), 5.0, 18.0, 8.0),       # v10: 7 beams each (v9: 5)
    (-1, 5): (7, (7.1, -46.7), 5.5, 16.0, 7.0),
    (-1, 4): (7, (4.3, -36.2), 6.0, 16.0, 7.0),
    (-1, 3): (7, (-12.9, -32.5), 5.0, 13.0, 7.0),
}
HORN_FANS.update({(1, k): (n, (-x, y), *rest) for (_, k), (n, (x, y), *rest) in list(HORN_FANS.items())})
HEAD_BOX = UNIT_BOX
HORN_LEN_MAX = 70.0
# tower units on the -X tower (the +X tower mirrors them: x and pan negated): one on top of the truss column (x -15.2,
# top at z 17.0), one on its crowd face at z 9 (the truss is 0.6 m square). (housing center, rest pan, rest tilt, beams,
# degrees between beams, pan amp, tilt amp, length cap)
TOWER_UNITS = [
    ((-15.2, -3.0, 17.17), 20.0, -18.0, 8, 6.0, 22.0, 10.0, 60.0),     # v10: 8 beams each (v9: 6)
    ((-15.2, -3.57, 9.0), 12.0, -6.0, 8, 6.5, 22.0, 10.0, 60.0),
]
# the tunnel (v10): a ring unit hung under the T. rex's chin (its lowest point is (0, -2.1, 12.73) in out_v9), firing a
# cone of beams MOUTH_CONE deg around its axis at the crowd's center; patterns with per-beam phases spin it into a
# tunnel (its u runs once around the ring)
MOUTH_UNIT = (0.0, -2.2, 12.5)
MOUTH_AIM = (0.0, -40.0, LAND_Z)
MOUTH_BEAMS, MOUTH_CONE, MOUTH_PAN, MOUTH_TILT, MOUTH_LEN = 16, 9.0, 12.0, 6.0, 55.0
# delay towers in the crowd (grounds/infrastructure.py TOWERS; header bar at G + 13.76 with moving heads up to ~13.1):
# a unit on a short pole above each bar, beams crossing over the middle (front ring: aimed in and back) and the back
# (back ring: aimed in and toward the stage, kept short of the front towers). -X towers; the +X ones mirror them.
DELAY_UNITS = [  # (housing center, rest pan, rest tilt, beams, degrees between beams, pan amp, tilt amp, length cap)
    ((-17.0, -42.0, 13.35), 50.0, -8.0, 8, 5.0, 16.0, 8.0, 34.0),
    ((-15.0, -65.0, 13.35), 125.0, -6.0, 8, 5.0, 14.0, 8.0, 28.0),
]
DELAY_BAR_TOP = -1.5 + 13.5 + 0.26 + 0.175            # infrastructure: G + TOWER_H + header axis + half its truss
# stage-front units: on 0.8 m road cases 0.7 m behind the deck-lip fixtures (y -3.6), clear of the wedge monitors
# (x +-2.4), the CO2 cannons (+-11.5, +-17.5), the flame units (+-14.5) and the riser (|x| < 4.5 from y -2.5); they fan
# up and out over the crowd and stay well above the fixtures and CO2 barrels in front of them
LIP_X = (-13.0, -8.0, -4.0, 4.0, 8.0, 13.0)
LIP_Y, LIP_CASE_H = -3.6, 0.8
LIP_TILT, LIP_BEAMS, LIP_SPREAD, LIP_PAN, LIP_TILT_AMP, LIP_LEN = 20.0, 6, 6.0, 22.0, 8.0, 58.0   # v10: 6 beams


def laser_pose_pq(co, pivot, P, Q, pan_amp, tilt_amp):
    """Where the UE material moves a laser vertex for the engine's pan P and tilt Q (-1..1), the same math in Blender
    space: rotate about the vertical through the pivot by pan_amp * P (+ = counter-clockwise from above, -Y toward +X),
    then about the horizontal axis perpendicular to the panned beam, k = normalize(h x Z) with h = the horizontal part of
    (vertex - pivot), by tilt_amp * Q (+ = raises the beam). Degrees in, Vector out."""
    pivot = Vector(pivot)
    v = Vector(co) - pivot
    v = Matrix.Rotation(math.radians(pan_amp * P), 3, "Z") @ v
    h = Vector((v.x, v.y, 0.0))
    if h.length > 1e-6:
        v = Matrix.Rotation(math.radians(tilt_amp * Q), 3, h.normalized().cross(Vector((0, 0, 1)))) @ v
    return pivot + v


def mover_pose_pq(co, pivot, yaw_deg, P, Q, pan_amp, tilt_amp):
    """Where the UE mover material puts a moving head's vertex (v13) for pan P and tilt Q (-1..1), in Blender space: the
    whole fixture turns rigidly about its head's center. Pan as laser_pose_pq (about the vertical, + = counter-clockwise
    from above); tilt (+ raises) about the fixture's own horizontal axis k = normalize(h x Z), h = its rest direction's
    horizontal part (yaw_deg, as aim()) after the pan, the same axis for its head, lens, glow and beam."""
    pivot = Vector(pivot)
    rp = Matrix.Rotation(math.radians(pan_amp * P), 3, "Z")
    v = rp @ (Vector(co) - pivot)
    y = math.radians(yaw_deg)
    h = rp @ Vector((math.sin(y), -math.cos(y), 0.0))
    k = h.normalized().cross(Vector((0, 0, 1)))
    return pivot + Matrix.Rotation(math.radians(tilt_amp * Q), 3, k) @ v


def laser_pose(co, pivot, phase, pan_amp, tilt_amp, s):
    """v8's classic sweep, now one sample of the engine's range (skull_check.py, atmosphere_preview.py --sweep):
    P = sin(2 pi (s + phase)), Q = sin(2 pi (0.7 s + phase + 0.25))."""
    return laser_pose_pq(co, pivot, math.sin(2 * math.pi * (s + phase)),
                         math.sin(2 * math.pi * (0.7 * s + phase + 0.25)), pan_amp, tilt_amp)


VIEWERS = (Vector((0, 0, 2.6)), Vector((0, -95, 13)))    # the DJ's head and the stream drone (pre-drop)


# ------------------------------------------------------------------ helpers
def beam(bm, apex, direction, length, w0, w1, color="white", planes=2, roll=0.0, core=1.0, v1=1.0):
    """kit.beam_planes plus two knobs: core < 1 maps the quads onto only the middle of the color column's soft
    profile (flatter, crisper: lasers); v1 < 1 stops short of the texture's fade-out (less fall-off along)."""
    apex, d = Vector(apex), Vector(direction).normalized()
    up = Vector((0, 0, 1)) if abs(d.z) < 0.95 else Vector((1, 0, 0))
    s0 = d.cross(up).normalized()
    n, col = len(BEAM_COLS), BEAM_COLS.index(color)
    u0, u1 = (col + 0.5 - 0.48 * core) / n, (col + 0.5 + 0.48 * core) / n
    end = apex + d * length
    faces = []
    for k in range(planes):
        s = (Matrix.Rotation(roll + math.pi * k / planes, 3, d) @ s0).normalized()
        faces += quad(bm, apex - s * w0 / 2, apex + s * w0 / 2, end + s * w1 / 2, end - s * w1 / 2,
                      uvs=[(u0, 0.0), (u1, 0.0), (u1, v1), (u0, v1)])
    return faces


def sprite(bm, center, size, color, axis=None):
    """A soft glow like kit.halo, but its crossed squares face the main viewers (the DJ, the stream drone) and the lens
    axis instead of the world axes: from those spots it reads round, and no square shows edge-on as a bright line."""
    c = Vector(center)
    normals = [(v - c).normalized() for v in VIEWERS] + ([Vector(axis).normalized()] if axis is not None else [])
    picked = []
    for n in normals:
        if all(abs(n.dot(m)) < 0.94 for m in picked):
            picked.append(n)
    col = BEAM_COLS.index(color)
    u0, u1 = col / len(BEAM_COLS), (col + 1) / len(BEAM_COLS)
    faces = []
    for n in picked:
        a = n.cross(Vector((0, 0, 1)))
        a = a.normalized() if a.length > 1e-3 else Vector((1, 0, 0))
        b = a.cross(n).normalized()
        a, b = a * size / 2, b * size / 2
        faces += quad(bm, c - a - b, c + a - b, c + a + b, c - a + b, uvs=[(u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)])
    return faces


def fan_dir(tilt, ang):
    """Direction in a flat fan whose center line points at the crowd tilted up `tilt` deg; `ang` deg sideways in it."""
    a = math.radians(ang)
    return (aim(0, tilt) * math.cos(a) + Vector((math.sin(a), 0, 0))).normalized()


def disc(bm, center, normal, r, segs=12):
    """A flat round face facing `normal`."""
    n0 = len(bm.faces)
    rot = Vector((0, 0, 1)).rotation_difference(Vector(normal)).to_matrix().to_4x4()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=segs, radius=r, matrix=Matrix.Translation(center) @ rot)
    bm.faces.ensure_lookup_table()
    faces = [bm.faces[i] for i in range(n0, len(bm.faces))]
    for f in faces:
        f.normal_update()
        if f.normal.dot(Vector(normal)) < 0:
            f.normal_flip()
    return faces


def tracker_unit(dark, alu, rubber, glow, cx, cy, dirs):
    """A trailer-mounted xenon sky tracker: wheeled base, then per head a turntable, a yoke turned to the beam and a
    drum along it with a glowing lens. Returns (lens center, direction) per head."""
    z0 = GROUND_Z
    w = 1.7 * len(dirs) + 0.3
    box(dark, (cx, cy, z0 + 0.62), (w, 1.5, 0.45))                     # trailer bed
    for sx in (-1, 1):                                                 # wheels
        x = cx + sx * (w / 2 - 0.45)
        cyl(rubber, (x, cy - 0.85, z0 + 0.32), (x, cy - 0.6, z0 + 0.32), 0.32, segs=8)
        cyl(rubber, (x, cy + 0.6, z0 + 0.32), (x, cy + 0.85, z0 + 0.32), 0.32, segs=8)
    lenses = []
    for j, (pan, tilt) in enumerate(dirs):
        d = aim(pan, tilt)
        hx = cx + (j - (len(dirs) - 1) / 2) * 1.7
        side = Vector((d.x, d.y, 0)).normalized().cross(Vector((0, 0, 1))).normalized()
        zt = z0 + 0.85
        cyl(alu, (hx, cy, zt), (hx, cy, zt + 0.14), 0.45, segs=10)    # turntable
        pivot = Vector((hx, cy, zt + 0.95))
        foot = Vector((hx, cy, zt + 0.16))
        for s in (-1, 1):                                              # yoke
            cyl(dark, foot + side * s * 0.6, pivot + side * s * 0.6 + Vector((0, 0, 0.08)), 0.06, segs=4)
        cyl(dark, foot - side * 0.62, foot + side * 0.62, 0.07, segs=4)
        cyl(alu, pivot - d * 0.75, pivot + d * 0.6, 0.48, segs=12)    # drum
        cyl(dark, pivot + d * 0.6, pivot + d * 0.72, 0.53, segs=12, cap=False)   # bezel
        glow_faces(glow, disc(glow, pivot + d * 0.66, d, 0.43), "white")
        lenses.append((pivot + d * 0.66, d))
    return lenses


def _horn_heads():
    heads = []
    for (side, k), (_, (lx, ly), *_) in sorted(HORN_FANS.items(), key=lambda kv: (-kv[0][1], kv[0][0])):
        last, tan = (Vector(v) for v in HORN_TIPS[(side, k)])
        apex = last + tan * 0.11                                       # tube(tip=True) cone point
        land = Vector((lx, ly, LAND_Z))
        f = Vector((land.x - apex.x, land.y - apex.y, 0)).normalized()
        center = apex + Vector((0, 0, HEAD_BOX[2] / 2 - 0.04))         # sits on the cone point, 4 cm over it
        heads.append({"side": side, "k": k, "last": last, "tan": tan, "center": center, "f": f,
                      "pivot": center + f * (HEAD_BOX[0] / 2 + 0.01), "land": land})
    return heads


HORN_HEADS = _horn_heads()


def _unit(name, group, center, rest, n, spread, pan_amp, tilt_amp, len_max, f=None, **extra):
    """A laser unit: its housing (center, UNIT_BOX turned to the heading f) and its fan of n beams spread `spread` deg
    apart around the rest direction (in the plane of the rest direction and the horizontal across it). The aperture,
    the pivot every beam of the unit turns about, is on the housing's face toward f, 1 cm out."""
    center, rest = Vector(center), Vector(rest).normalized()
    f = Vector(f) if f is not None else Vector((rest.x, rest.y, 0)).normalized()
    return dict(name=name, group=group, center=center, f=f, pivot=center + f * (UNIT_BOX[0] / 2 + 0.01), rest=rest,
                n=n, spread=spread, pan=pan_amp, tilt=tilt_amp, len_max=len_max, **extra)


def _laser_units():
    """Every laser unit, then x = its place across the rig (0 = the -X end .. 1) from the pivots' spread."""
    units = [_unit("fan", 0, LASER_UNIT, aim(0, LASER_TILT), len(LASER_ANGS), LASER_ANGS[1] - LASER_ANGS[0],
                   FAN_PAN, FAN_TILT, LASER_LEN, case=((LASER_UNIT[0], LASER_UNIT[1] + 0.02, 0.25), (0.5, 0.45, 0.5)))]
    for hi, h in enumerate(HORN_HEADS):
        n, _, spread, pan_amp, tilt_amp = HORN_FANS[(h["side"], h["k"])]
        units.append(_unit(f"horn {'L' if h['side'] < 0 else 'R'}{h['k']}", 7 - h["k"], h["center"],
                           h["land"] - h["pivot"], n, spread, pan_amp, tilt_amp, HORN_LEN_MAX, f=h["f"], head=hi))
    for s in (-1, 1):
        for (cx, cy, cz), pan, tilt, n, spread, pan_amp, tilt_amp, len_max in TOWER_UNITS:
            name = f"tower {'L' if s < 0 else 'R'}{'top' if cz > 12 else 'mid'}"
            units.append(_unit(name, 5, (-s * cx, cy, cz), aim(-s * pan, tilt), n, spread, pan_amp, tilt_amp, len_max))
    for x in LIP_X:
        units.append(_unit(f"lip {x:+.0f}", 6, (x, LIP_Y, LIP_CASE_H + UNIT_BOX[2] / 2), aim(1.5 * x, LIP_TILT),
                           LIP_BEAMS, LIP_SPREAD, LIP_PAN, LIP_TILT_AMP, LIP_LEN,
                           case=((x, LIP_Y, LIP_CASE_H / 2), (0.6, 0.6, LIP_CASE_H))))
    mc = Vector(MOUTH_UNIT)
    units.append(_unit("mouth", 7, mc, Vector(MOUTH_AIM) - (mc + Vector((0, -1, 0)) * (UNIT_BOX[0] / 2 + 0.01)),
                       MOUTH_BEAMS, MOUTH_CONE, MOUTH_PAN, MOUTH_TILT, MOUTH_LEN, f=(0.0, -1.0, 0.0), ring=True))
    for s in (-1, 1):
        for (cx, cy, cz), pan, tilt, n, spread, pan_amp, tilt_amp, len_max in DELAY_UNITS:
            name = f"delay {'L' if s < 0 else 'R'}{'front' if cy > -50 else 'back'}"
            units.append(_unit(name, 8, (-s * cx, cy, cz), aim(-s * pan, tilt), n, spread, pan_amp, tilt_amp, len_max,
                               pole=True))
    xs = [u["pivot"].x for u in units]
    for u in units:
        u["x"] = (u["pivot"].x - min(xs)) / (max(xs) - min(xs))
    return units


def _beam_length(pivot, d, tilt_amp, len_max):
    """The longest beam (<= len_max) that still ends FLOOR_MARGIN over the crowd floor at its steepest tilt."""
    down = math.radians(tilt_amp) - math.asin(max(-1.0, min(1.0, d.z)))   # steepest drop below the horizon
    if down <= math.radians(1.0):
        return len_max
    return min(len_max, (pivot.z - (GROUND_Z + FLOOR_MARGIN)) / math.sin(down))


def _laser_table():
    """One dict per laser beam: its unit (index), group, pivot, rest direction d, length (pivot to end), u (its place
    in the unit's fan, -1..1), x (the unit's place across the rig; the center fan's beams split at its middle, so the
    engine's mirrored patterns open it like a pair), sweep amplitudes and a phase (v8 previews only)."""
    lasers = []
    for ui, un in enumerate(LASER_UNITS):
        rest = un["rest"]
        perp = Vector((0, 0, 1)).cross(rest).normalized()               # +X for a unit facing the crowd (-Y)
        up = rest.cross(perp).normalized()
        n = un["n"]
        for j in range(n):
            if un.get("ring"):                                         # a cone: u once around it, from its -X side
                phi = 2 * math.pi * j / n
                c = math.radians(un["spread"])
                d = (rest * math.cos(c) + (perp * -math.cos(phi) + up * math.sin(phi)) * math.sin(c)).normalized()
                u = 2.0 * j / n - 1.0
                x = 0.5 - 0.02 * math.cos(phi)                         # its halves mirror like the center fan's
            else:
                u = (j - (n - 1) / 2) / ((n - 1) / 2) if n > 1 else 0.0
                a = math.radians((j - (n - 1) / 2) * un["spread"])
                d = (rest * math.cos(a) + perp * math.sin(a)).normalized()
                x = 0.5 + 0.02 * u if un["group"] == 0 else un["x"]
            lasers.append({"unit": ui, "group": un["group"], "head": un.get("head"), "pivot": un["pivot"], "d": d,
                           "length": _beam_length(un["pivot"], d, un["tilt"], un["len_max"]), "u": u, "x": x,
                           "pan": un["pan"], "tilt": un["tilt"], "cue": un["group"],
                           "phase": (0.37 * ui + 0.05 * j) % 1.0})
    return lasers


LASER_UNITS = _laser_units()
LASERS = _laser_table()


def panel(bm, center, normal, w, h, uvs=None):
    """An upright quad of w x h facing `normal` (counter-clockwise seen from there)."""
    c, n = Vector(center), Vector(normal).normalized()
    r = Vector((0, 0, 1)).cross(n).normalized() * w / 2
    u = n.cross(r).normalized() * h / 2
    return quad(bm, c - r - u, c + r - u, c + r + u, c - r + u, uvs=uvs)


def laser_mesh():
    """Every laser beam and every unit's aperture glow as one mesh: "UVMap" (T_DinoBeam's white column; the material
    colors it), then the LASER_UV layers, in that order. An aperture glow is a quad on the housing's face, mapped to the
    bright start of the beam texture, that never moves (LaserAmp 0) and lights with its unit (kind 1)."""
    bm = bmesh.new()
    uv_layer(bm)
    layers = [bm.loops.layers.uv.new(name) for name in LASER_UV]

    def stamp(faces, values):
        for f in faces:
            for lp in f.loops:
                for lay, val in zip(layers, values):
                    lp[lay].uv = val
    for b in LASERS:
        p, d = b["pivot"], b["d"]
        faces = beam(bm, p + d * LASER_GAP, d, b["length"] - LASER_GAP, BEAM_W[0], BEAM_W[1], "white",
                     core=BEAM_CORE, v1=BEAM_V1)
        stamp(faces, ((p.x, p.y), (p.z, b["phase"]), (b["pan"], b["tilt"]), (float(b["cue"]), b["u"]), (b["x"], 0.0)))
    n, col = len(BEAM_COLS), BEAM_COLS.index("white")
    u0, u1 = (col + 0.02) / n, (col + 0.98) / n
    for un in LASER_UNITS:
        p, f = un["pivot"], un["f"]
        faces = panel(bm, p + f * 0.004, f, UNIT_BOX[1] * 0.62, UNIT_BOX[2] * 0.36,
                      uvs=[(u0, 0.0), (u1, 0.0), (u1, 0.05), (u0, 0.05)])
        stamp(faces, ((p.x, p.y), (p.z, 0.0), (0.0, 0.0), (float(un["group"]), 0.0), (un["x"], 1.0)))
    return bm


# ------------------------------------------------------------------ build
def build(rng):
    dark, alu, rubber, glow = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    sky, stage, halos = bmesh.new(), bmesh.new(), bmesh.new()
    lights, exclude = [], []

    for i, ((cx, cy), dirs) in enumerate(TRACKERS):
        for c, d in tracker_unit(dark, alu, rubber, glow, cx, cy, dirs):
            beam(sky, c, d, TRACKER_LEN, 1.8, 26.0, "white", planes=3)
            sprite(halos, c + d * 0.2, 3.0, "white", d)
        toward = 1 if cy < 0 else -1                                   # light the side the audience sees
        lights.append(light(f"Tracker{i}", "POINT", (cx, cy + toward * 2.5, GROUND_Z + 3.2), (0.8, 0.86, 1.0), 400,
                            size=0.3))
        exclude.append((cx - 3, cy - 2.5, cx + 3, cy + 2.5))

    movers, mhalos = bmesh.new(), bmesh.new()                          # v13: the stage's moving heads, moving
    uv_layer(movers)
    uv_layer(mhalos)
    mlay = [movers.loops.layers.uv.new(n) for n in LASER_UV]
    hlay = [mhalos.loops.layers.uv.new(n) for n in LASER_UV]
    for i, (base, pan, tilt, color, length, w1) in enumerate(STAGE_LOOK):
        d = aim(pan, tilt)
        c = lens_center(base, d)
        stamp_uv(beam(movers, c, d, length, 0.36, w1, color), mlay, STAGE_MOVES[i])
        stamp_uv(sprite(mhalos, c + d * 0.08, 1.1 if base[2] > 1 else 0.9, color, d), hlay, STAGE_MOVES[i])
    stage.free()

    for un in LASER_UNITS:                                             # the laser units (their apertures glow in the
        f = un["f"]                                                    # lasers mesh, colored by the show)
        yaw = math.atan2(f.y, f.x)
        box(dark, un["center"], UNIT_BOX, yaw=yaw)                                       # housing
        box(alu, un["center"] + f * (UNIT_BOX[0] / 2 - 0.02), (0.05, UNIT_BOX[1] + 0.04, UNIT_BOX[2] + 0.04),
            yaw=yaw)                                                                     # front bezel
        for s in (-1, 1):                                                                # cooling fins on the sides
            side = Vector((-f.y, f.x, 0)) * s * (UNIT_BOX[1] / 2 + 0.015)
            box(alu, un["center"] - f * 0.06 + side, (UNIT_BOX[0] * 0.6, 0.03, UNIT_BOX[2] * 0.7), yaw=yaw)
        if "case" in un:                                                                 # road case under it
            box(dark, *un["case"])
        if un.get("head") is not None:                                                   # horn tip: a collar
            h = HORN_HEADS[un["head"]]
            cyl(dark, h["last"] - h["tan"] * 0.22, h["last"] - h["tan"] * 0.08, 0.17, segs=8, cap=False)
        if un["group"] == 5 and un["center"].z < 12:                                     # tower face: a bracket
            box(alu, un["center"] - f * (UNIT_BOX[0] / 2 + 0.03) - Vector((0, 0, 0.08)), (0.08, 0.3, 0.12), yaw=yaw)
        if un.get("ring"):                                                               # hung from the chin
            top = un["center"] + Vector((0, 0, UNIT_BOX[2] / 2))
            cyl(alu, top, top + Vector((0, 0, 0.3)), 0.04, segs=6)
        if un.get("pole"):                                                               # on the tower's header bar
            bot = un["center"] - Vector((0, 0, UNIT_BOX[2] / 2))
            cyl(alu, Vector((bot.x, bot.y, DELAY_BAR_TOP)), bot, 0.05, segs=6)
            box(alu, Vector((bot.x, bot.y, DELAY_BAR_TOP + 0.02)), (0.3, 0.3, 0.04))

    for p in PILLAR_TOPS:
        sprite(halos, (p[0], p[1], p[2] + 0.05), 1.4, "cyan")

    return {"lit": [(dark, "metal_dark"), (alu, "metal_alu"), (rubber, "rubber")], "glow": [glow],
            "beams": [sky], "lasers": [laser_mesh()], "halos": [halos], "movers": [movers], "mover_halos": [mhalos],
            "lights": lights, "exclude": exclude, "people": []}
