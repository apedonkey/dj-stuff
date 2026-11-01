"""REACTOR v7 (2026-10-09): the moving heads move, on the Dino session's v13 mover engine (dino_materials' mover WPO;
the contract is in claudedocs/club_venue_notes.md, "v7 plan"). The helpers club_stage.build_rig and the checks share:

  LASER_UV         the five data layers after UVMap (grounds/atmosphere.LASER_UV's names and order)
  MOVER_AMP        per head group: (pan, tilt) amplitude in degrees
  move_values()    the five values a fixture's head, lens, halo and beam all carry; yoke_values(): the yoke's (tilt 0)
  add_layers()     the layers on a bmesh (after its UVMap); stamp_new(): the data onto the faces a builder just made
                   (from a snapshot of bm.faces: bmesh ops reuse face slots, so an index range misses faces)
  mover_pose_pq()  where the UE material puts a vertex for the engine's pan P and tilt Q (-1..1): atmosphere's math
  SWEEP            (P, Q) samples over the engine's whole range (beam lengths, the clearance check)

Per vertex, in Blender m (the materials read V as 1 - v; Unreal's FBX import flips it): UV1 = the pivot (x, y), UV2 =
(pivot z, phase), UV3 = (pan amp, tilt amp) deg, UV4 = (rest yaw deg, u), UV5 = (x 0..1 across the rig, 0). The pivot is
the head's centre (the tilt axis); the rest yaw is measured like atmosphere.aim(): degrees from -Y toward +X; u runs -1..1
across a row (fans, phases); x < 0.5 is the left side (mirrored patterns). The yoke only pans; the clamp or base is static
and stays in the baked rig."""
import math

from mathutils import Matrix, Vector

LASER_UV = ("LaserPivot", "LaserPivotZPhase", "LaserAmp", "LaserCue", "LaserFix")
# hall heads light the dance floor from 8.4 m: the widest swing; the bay heads throw 25 m over the room: smaller angles
# move the far end as much; the floor heads stand on the deck beside the DJ: the least (the clearance check holds them)
MOVER_AMP = {"Hall": (24.0, 14.0), "Bay": (16.0, 9.0), "Floor": (14.0, 10.0)}
SWEEP = [(p, q) for p in (-1.0, -0.5, 0.0, 0.5, 1.0) for q in (-1.0, -0.5, 0.0, 0.5, 1.0)]


def yaw_of(d):
    """A direction's rest yaw as atmosphere.aim() measures it: degrees from -Y toward +X."""
    return math.degrees(math.atan2(d.x, -d.y))


def move_values(i, pivot, d, group, u, x01):
    """The five layer values of fixture i: pivot (head centre), phase, amplitudes, rest yaw + u, x across the rig."""
    pa, ta = MOVER_AMP[group]
    return ((pivot.x, pivot.y), (pivot.z, (0.37 * i) % 1.0), (pa, ta), (yaw_of(d), u), (x01, 0.0))


def yoke_values(vals):
    """The yoke pans with its head but never tilts."""
    return vals[0], vals[1], (vals[2][0], 0.0), vals[3], vals[4]


def add_layers(bm):
    """UVMap first (channel 0), then the five data layers (channels 1-5); returns the five."""
    if bm.loops.layers.uv.get("UVMap") is None:
        bm.loops.layers.uv.new("UVMap")
    return [bm.loops.layers.uv.get(n) or bm.loops.layers.uv.new(n) for n in LASER_UV]


def stamp_new(bm, before, lays, vals):
    """Every face of bm that is not in `before` (a set(bm.faces) taken before the builder ran) gets the values."""
    n = 0
    for f in bm.faces:
        if f in before:
            continue
        n += 1
        for lp in f.loops:
            for lay, val in zip(lays, vals):
                lp[lay].uv = val
    return n


def mover_pose_pq(co, pivot, yaw_deg, P, Q, pan_amp, tilt_amp):
    """atmosphere.mover_pose_pq (the Dino session's, v13), the same math: pan about the vertical through the pivot by
    pan_amp * P (+ = counter-clockwise from above), then tilt (+ raises) by tilt_amp * Q about the fixture's own
    horizontal axis k = normalize(h x Z), h = its rest direction's horizontal part (yaw_deg) after the pan."""
    pivot = Vector(pivot)
    rp = Matrix.Rotation(math.radians(pan_amp * P), 3, "Z")
    v = rp @ (Vector(co) - pivot)
    y = math.radians(yaw_deg)
    h = rp @ Vector((math.sin(y), -math.cos(y), 0.0))
    k = h.normalized().cross(Vector((0, 0, 1)))
    return pivot + Matrix.Rotation(math.radians(tilt_amp * Q), 3, k) @ v


def posed_ray(lens, d, pivot, yaw_deg, P, Q, pan_amp, tilt_amp):
    """The lens centre and beam direction in pose (P, Q)."""
    a = mover_pose_pq(lens, pivot, yaw_deg, P, Q, pan_amp, tilt_amp)
    b = mover_pose_pq(Vector(lens) + Vector(d), pivot, yaw_deg, P, Q, pan_amp, tilt_amp)
    return a, (b - a).normalized()
