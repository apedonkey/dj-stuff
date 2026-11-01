"""REACTOR's sweeping lasers (stage v5; the user, 2026-10-09: "we need to have the lazers and lights go with the music like
how it does on the dino stage"). Laser units at the club's own spots, written in the Dino Stage's laser format, so the
Dino's engine moves them: dino_materials.laser_show + show.py's pattern program (T_ClubLaserProg / T_ClubLaserLib are
show.py's own tables, read only), driven by the hook's show bus (the song's bars, per-song variant, hits, bass, drops).

Format (grounds/atmosphere.py laser_mesh, the Dino session's; copied, never imported): "UVMap" maps the beam texture's
white column, then five layers per vertex, raw values (laser_show reads every V back as 1 - v: Unreal's FBX import flips
V on all channels): LaserPivot (x, y), LaserPivotZPhase (z, phase), LaserAmp (pan, tilt degrees for the engine's +-1),
LaserCue (group, u = the beam's place in its fan -1..1), LaserFix (x = the unit's place across the rig 0..1, kind: 0 beam,
1 aperture glow). Club frame, Blender m (the level maps it to world cm as (-100x, 100y, 100z)).

Groups -> the club's cue rows (laser_show reads row grp + 3 for groups 0..4; club_show.CUE_ROWS):
  0 = the front-truss fans      -> row 3 laserbar    (the engine's "fan" family)
  1 = the mezzanine pole units  -> row 4 sidelasers  (its "horns" family)
  2 = the back-truss units      -> row 5 backlasers  (its "horns" family)

v8 (2026-10-11; the user: "ok so i noticed that the lazers are stopping before they hit the floor. why are they doing
that?", then "yeah let them hit the floor"): every beam lands on a surface. A beam is one fixed-length mesh that the
engine turns about its aperture, so it can't stop where it lands. v5-v7 cut each beam where its lowest pose reached raised
hands (2.3 m over the floor), so in most poses it ended in mid-air. Now each beam is just long enough to reach a surface
in every pose of its sweep (the floor, a wall, the ceiling, a mezzanine deck); in the game the floor and walls hide the
rest (depth test). A mezzanine deck can't hide it from the lounge under it, so the club's laser material
(club_materials.laser_show) clips the part past a deck's top (LIDS). The beams go through the people now, but still never
over the stage below 3 m or near the DJ's head. The back units aim at the floor in front of the stage (v7 aimed 3.4 m above
the same spot, and only missed the stage because the beams stopped short).
The beams keep their brightness and width per metre instead of per beam. v7 stretched the texture's fade (v 0..0.85)
over each beam, so a tip had about 4 % of the aperture's light and long beams looked even shorter.
Plain Python (math only) for the geometry and the check; build_mesh() / housings() need Blender (bmesh)."""
import functools
import math

import club_layout as L

STAGE_TOP = 3.0                        # no beam over the stage below this (the DJ and the guests) ...
DJ_HEAD, DJ_CLEAR = (-0.1, 0.9, 1.68), 1.6      # ... nor this close to the DJ's head
UNIT_BOX = (0.5, 0.46, 0.3)            # laser housing: depth (along its heading), width, height (atmosphere's)
LASER_GAP = 0.1                        # beams start 10 cm out from the aperture (atmosphere's)
BEAM_W = (0.02, 0.10)                  # crisp lines: width at the aperture / from WIDE_AT on (atmosphere's ends)
WIDE_AT = 15.0                         # v8: the width grows over the first 15 m (about v7's beams), then stays
V_PER_M = 0.0125                       # v8: the texture's along-fade per metre: 75 % of the aperture's light at 10 m,
                                       # 58 % at 20 m, 43 % at 30 m (v7: 0.85 per beam, ~4 % at the tip)
SEG = 2.5                              # v8: segment length while the beam widens: keeps its profile centred
BEAM_CORE = 0.35                       # atmosphere's: the middle of the white column's profile
MIN_LEN = 3.0                          # a beam this short after the check is dropped
REACH = 45.0                           # v8: no beam longer than this (the hall's diagonal)
LAND_MARGIN = 1.5                      # v8: beams run on this far past their farthest landing (under the floor, ...): the
                                       # 9 x 9 poses can miss the farthest one (a far corner; 0.5 m was 1 mm short there)
LASER_UV = ("LaserPivot", "LaserPivotZPhase", "LaserAmp", "LaserCue", "LaserFix")
# v8: the tops (x0, x1, y0, y1, z) that hide a beam going down through them: the mezzanine decks. The laser material
# clips the beam past them (club_materials.laser_show gets these from build_club.py); the floor and walls need no clip.
LIDS = ((L.MZ_X0, L.MZ_X1, L.MZ_Y0, L.MZ_Y1, L.MZ_Z), (-L.MZ_X1, -L.MZ_X0, L.MZ_Y0, L.MZ_Y1, L.MZ_Z))
AIRLOCK_ROOF = (L.AIR_X0, L.AIR_X1, L.AIR_Y0, L.AIR_Y1, L.LINTEL_TOP + 0.1)   # not clipped: no beam may go through it

# (name, group, housing centre, rest aim point, beams, degrees between beams, pan amp, tilt amp)
_TRUSS_Z = L.FRONT_TRUSS[0][2] - 0.42          # hung under the front truss
_BACK_Z = L.TRUSS_Z - 0.42                     # under the hall's back truss
UNITS = (
    [(f"front {x:+.1f}", 0, (x, L.FRONT_TRUSS[0][1], _TRUSS_Z), (0.45 * x, -15.0, 2.4), 9, 4.5, 10.0, 5.0)
     for x in (-4.5, -1.5, 1.5, 4.5)]
    + [(f"pole {'L' if sx < 0 else 'R'}", 1, (sx * 8.4, L.MZ_Y1 - 0.2, 4.85), (-sx * 1.5, -17.0, 2.4), 7, 5.0, 12.0, 4.0)
       for sx in (-1, 1)]
    + [(f"back {x:+.1f}", 2, (x, L.TRUSS_Y[-1], _BACK_Z), (0.3 * x, -8.0, L.FLOOR), 9, 5.0, 10.0, 4.0)   # v8: on the floor
       for x in (-3.5, 3.5)]
)


# ------------------------------------------------------------------ small vector math (tuples; no Blender needed)
def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def norm(a):
    n = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
    return (a[0] / n, a[1] / n, a[2] / n)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def rotate(v, axis, deg):
    """Rodrigues: v turned deg about the unit axis (right-handed, like Blender's Matrix.Rotation)."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    kx = cross(axis, v)
    kd = axis[0] * v[0] + axis[1] * v[1] + axis[2] * v[2]
    return tuple(v[i] * c + kx[i] * s + axis[i] * kd * (1 - c) for i in range(3))


def pose_dir(d, P, Q, pan_amp, tilt_amp):
    """atmosphere.laser_pose_pq for a direction: about Z by pan_amp * P, then about normalize(h x Z) by tilt_amp * Q
    (h = the panned direction's horizontal part); + tilt raises the beam."""
    v = rotate(d, (0.0, 0.0, 1.0), pan_amp * P)
    h = (v[0], v[1], 0.0)
    if math.hypot(h[0], h[1]) > 1e-6:
        v = rotate(v, norm(cross(h, (0.0, 0.0, 1.0))), tilt_amp * Q)
    return v


# ------------------------------------------------------------------ the units and their beams
def units():
    """Each unit: housing centre, heading f (horizontal), pivot (the aperture: the housing's face toward f, 1 cm out),
    rest direction, and its x across the rig (0 = the -X end .. 1)."""
    out = []
    for name, grp, c, aimpt, n, spread, pan, tilt in UNITS:
        rest = norm(sub(aimpt, c))
        f = norm((rest[0], rest[1], 0.0))
        pivot = add(c, mul(f, UNIT_BOX[0] / 2 + 0.01))
        out.append(dict(name=name, group=grp, center=c, f=f, pivot=pivot, rest=rest, n=n, spread=spread, pan=pan,
                        tilt=tilt))
    xs = [u["pivot"][0] for u in out]
    for u in out:
        u["x"] = (u["pivot"][0] - min(xs)) / (max(xs) - min(xs))
    return out


def crossed(pivot, p, lid):
    """Did the line from the aperture down to p go through lid's top (x0, x1, y0, y1, z) inside its footprint?"""
    x0, x1, y0, y1, zt = lid
    if not pivot[2] > zt > p[2]:
        return False
    s = (zt - pivot[2]) / (p[2] - pivot[2])
    cx, cy = pivot[0] + s * (p[0] - pivot[0]), pivot[1] + s * (p[1] - pivot[1])
    return x0 <= cx <= x1 and y0 <= cy <= y1


def where(pivot, p):
    """What a beam point is in: "hidden" (in or past a wall, the ceiling or the floor, under the stage deck, or past a
    mezzanine deck's top, which the material clips), "roof" (past the airlock roof: in sight again in the vestibule),
    "stage" (over the stage) or "open" (the hall, the lounge under the mezzanines, the vestibule)."""
    x, y, z = p
    if abs(x) > L.HX or y < L.Y_BACK or y > L.SCREEN_Y or z < L.FLOOR:
        return "hidden"
    if z > (L.CEIL if y < L.LIP_Y else L.STAGE_CEIL):
        return "hidden"
    if y >= L.LIP_Y:
        return "hidden" if z < 0.0 else "stage"
    if any(crossed(pivot, p, lid) for lid in LIDS):
        return "hidden"
    return "roof" if crossed(pivot, p, AIRLOCK_ROOF) else "open"


def walk(pivot, v, step=0.05):
    """One pose of a beam, out to REACH: (land, bad, why). land: where it first goes out of sight (it lands there), None
    if it never does; bad: the first point it must not reach (a visible point over the stage below 3 m or by the DJ's
    head, or one in sight again after it landed), None if there is none."""
    t, land = LASER_GAP, None
    while t <= REACH:
        p = add(pivot, mul(v, t))
        w = where(pivot, p)
        if w == "hidden":
            if land is None:
                land = t
        elif land is not None:
            return land, t, "in sight again past where it lands"
        elif w == "roof":
            return land, t, "through the airlock roof"
        elif w == "stage" and p[2] < STAGE_TOP:
            return land, t, "over the stage, below 3 m"
        elif w == "stage" and math.dist(p, DJ_HEAD) < DJ_CLEAR:
            return land, t, "the DJ's head"
        t += step
    return land, None, None


SWEEP = tuple(k / 4.0 - 1.0 for k in range(9))     # the engine's pan and tilt, -1..1 (9 x 9 poses)


def solve(pivot, d, pan, tilt):
    """A beam's length: LAND_MARGIN past where it lands in its farthest-landing pose, but short of any point it must not
    reach in any pose. Returns (length, poses that end short of a surface, why it was cut or None)."""
    lands, bad = [], (REACH + LAND_MARGIN, None)
    for P in SWEEP:
        for Q in SWEEP:
            land, t_bad, why = walk(pivot, pose_dir(d, P, Q, pan, tilt))
            lands.append(land)
            if t_bad is not None and t_bad < bad[0]:
                bad = (t_bad, why)
    reached = [t for t in lands if t is not None]
    length = min(max(reached, default=REACH) + LAND_MARGIN, bad[0] - 0.1)
    short = sum(1 for t in lands if t is None or t > length)
    return length, short, bad[1] if bad[0] - 0.1 < length + 1e-9 else None


@functools.lru_cache(maxsize=None)
def beams():
    """One dict per beam that survives the check: unit index, group, pivot, rest direction d, length, u, x, amps, phase,
    and how many of its poses end short of a surface (short, why). Solved once (club_stage.py asks three times)."""
    out, dropped = [], []
    for ui, un in enumerate(units()):
        rest = un["rest"]
        perp = norm(cross((0.0, 0.0, 1.0), rest))
        n = un["n"]
        for j in range(n):
            u = (j - (n - 1) / 2) / ((n - 1) / 2) if n > 1 else 0.0
            a = math.radians((j - (n - 1) / 2) * un["spread"])
            d = norm(add(mul(rest, math.cos(a)), mul(perp, math.sin(a))))
            length, short, why = solve(un["pivot"], d, un["pan"], un["tilt"])
            x = 0.5 + 0.02 * u if un["group"] == 0 else un["x"]
            b = dict(unit=ui, group=un["group"], pivot=un["pivot"], d=d, length=length, u=u, x=x, pan=un["pan"],
                     tilt=un["tilt"], phase=(0.37 * ui + 0.05 * j) % 1.0, short=short, why=why)
            (out if length >= MIN_LEN else dropped).append(b)
    return out, dropped


def report():
    bs, dropped = beams()
    poses = len(SWEEP) ** 2
    lines = [f"{len(units())} units, {len(bs)} beams ({len(dropped)} dropped under {MIN_LEN} m); "
             f"{sum(b['short'] for b in bs)} of {len(bs) * poses} poses end short of a surface"]
    for ui, un in enumerate(units()):
        mine = [b for b in bs if b["unit"] == ui]
        ls = [b["length"] for b in mine]
        whys = sorted({b["why"] for b in mine if b["why"]})
        lines.append(f"  {un['name']:10s} group {un['group']}: {len(ls)} beams, length {min(ls) if ls else 0:.1f}.."
                     f"{max(ls) if ls else 0:.1f} m, {sum(b['short'] for b in mine)} poses short"
                     + (f" (cut: {', '.join(whys)})" if whys else ""))
    return bs, "\n".join(lines)


# ------------------------------------------------------------------ Blender: the beam mesh and the housings
def build_mesh(gkit):
    """Every beam + every unit's aperture glow as one bmesh (UVMap = T_ClubBeam's white column, then LASER_UV), as
    atmosphere.laser_mesh builds the Dino's: export it as SM_ClubLaserShow."""
    import bmesh
    from mathutils import Matrix, Vector
    bm = bmesh.new()
    gkit.uv_layer(bm)
    layers = [bm.loops.layers.uv.new(nm) for nm in LASER_UV]
    ncol, col = len(gkit.BEAM_COLS), gkit.BEAM_COLS.index("white")

    def stamp(faces, values):
        for fa in faces:
            for lp in fa.loops:
                for lay, val in zip(layers, values):
                    lp[lay].uv = val

    def width(t):
        return BEAM_W[0] + (BEAM_W[1] - BEAM_W[0]) * min(t / WIDE_AT, 1.0)

    def beam(apex, direction, length, planes=2):
        """v8: crossed quads in segments (SEG apart while the beam widens, then one to the end): the width and the
        texture's fade go by the metre (width(t), v = V_PER_M t), and short segments keep the across-profile centred
        (one long trapezoid split in two triangles skews it)."""
        apex, d = Vector(apex), Vector(direction).normalized()
        up = Vector((0, 0, 1)) if abs(d.z) < 0.95 else Vector((1, 0, 0))
        s0 = d.cross(up).normalized()
        u0, u1 = (col + 0.5 - 0.48 * BEAM_CORE) / ncol, (col + 0.5 + 0.48 * BEAM_CORE) / ncol
        wide = min(length, WIDE_AT)
        ts = [0.0]
        while ts[-1] + SEG < wide - 1e-6:
            ts.append(ts[-1] + SEG)
        ts += [wide] + ([length] if length > wide + 1e-6 else [])
        faces = []
        for k in range(planes):
            s = (Matrix.Rotation(math.pi * k / planes, 3, d) @ s0).normalized()
            for t0, t1 in zip(ts, ts[1:]):
                a, b = apex + d * t0, apex + d * t1
                w0, w1, v0, v1 = width(t0), width(t1), V_PER_M * t0, V_PER_M * t1
                faces += gkit.quad(bm, a - s * w0 / 2, a + s * w0 / 2, b + s * w1 / 2, b - s * w1 / 2,
                                   uvs=[(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
        return faces
    bs, _ = beams()
    for b in bs:
        p, d = Vector(b["pivot"]), Vector(b["d"])
        faces = beam(p + d * LASER_GAP, d, b["length"] - LASER_GAP)
        stamp(faces, ((p.x, p.y), (p.z, b["phase"]), (b["pan"], b["tilt"]), (float(b["group"]), b["u"]), (b["x"], 0.0)))
    u0, u1 = (col + 0.02) / ncol, (col + 0.98) / ncol
    for un in units():                                       # the aperture glow: lights with its unit, never moves
        p, f = Vector(un["pivot"]), Vector(un["f"])
        c = p + f * 0.004
        r = Vector((0, 0, 1)).cross(f).normalized() * UNIT_BOX[1] * 0.62 / 2
        up = f.cross(r).normalized() * UNIT_BOX[2] * 0.36 / 2
        faces = gkit.quad(bm, c - r - up, c + r - up, c + r + up, c - r + up,
                          uvs=[(u0, 0.0), (u1, 0.0), (u1, 0.05), (u0, 0.05)])
        stamp(faces, ((p.x, p.y), (p.z, 0.0), (0.0, 0.0), (float(un["group"]), 0.0), (un["x"], 1.0)))
    return bm


def housings(gkit, rig):
    """The laser housings (dark boxes turned to their heading) and their clamps, into the rig's (baked) bmesh."""
    for un in units():
        c, f = un["center"], un["f"]
        yaw = math.atan2(f[1], f[0]) - math.pi / 2               # the box's depth axis (its local y) along f
        gkit.box(rig, c, (UNIT_BOX[1], UNIT_BOX[0], UNIT_BOX[2]), yaw=yaw)
        gkit.box(rig, (c[0], c[1], c[2] + UNIT_BOX[2] / 2 + 0.06), (0.08, 0.08, 0.12))   # clamp to the truss / pole


if __name__ == "__main__":
    print(report()[1])
