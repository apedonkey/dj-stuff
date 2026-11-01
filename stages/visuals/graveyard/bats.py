"""Bats for the GRAVEYARD SHIFT loops (Blender's Python): a silhouette bat (black body and wing membranes) with neon
rims (the wing's edges and finger bones as thin tubes, the body rim-lit), two wings hinged at the shoulders, flapping
on the music clock. Scenes give each bat a flight function; spawning and despawning by age modulo the loop keeps
everything seamless.

Local frame of a bat: +Y forward (the head), +Z up, +X its right; wingspan about 1.25 (scale the object for size).
  meshes = bat_meshes(rim_mat, black_mat)      shared mesh data (body, left wing, right wing)
  body, wl, wr = make_bat(name, meshes)        objects (wings parented to the body at the shoulders)
  key_bat(body, wl, wr, states)                states: [(frame, location, rotation quaternion, scale, flap deg)]
  flap_angle(f, phase, amp, bias)              wings fully down on every 8th note (2 flaps per beat)
  rim_mat(name, gain, near, far)               rim color = object color (constant per bat), distance fades
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

import hwgeo as g
import vjkit as vj

SHOULDER = 0.045                          # wing hinge offset from the body axis (x)


def _scallop(a, b, depth, n=5):
    """Points from a to b along a curve bowed toward the wing's root (+y side / toward the shoulder)."""
    ax, ay = a
    bx, by = b
    mx, my = (ax + bx) / 2, (ay + by) / 2
    dx, dy = bx - ax, by - ay
    ln = math.hypot(dx, dy)
    nx, ny = -dy / ln, dx / ln                    # left normal of a->b
    if nx * (0.0 - mx) + ny * (0.1 - my) < 0:      # bow toward the shoulder region
        nx, ny = -nx, -ny
    out = []
    for i in range(1, n + 1):
        t = i / (n + 1)
        bow = 4 * t * (1 - t) * depth
        out.append((ax + dx * t + nx * bow, ay + dy * t + ny * bow))
    return out


def wing_outline():
    """Right wing outline (x out along the span from the shoulder, y forward), counter-clockwise."""
    root_front, wrist, tip = (0.0, 0.05), (0.27, 0.14), (0.62, 0.0)
    f4, f5, root_back = (0.53, -0.22), (0.35, -0.29), (0.0, -0.17)
    lead = [root_front, (0.12, 0.11), wrist, (0.44, 0.09), tip]
    trail = [tip] + _scallop(tip, f4, 0.055) + [f4] + _scallop(f4, f5, 0.06) + [f5] + \
        _scallop(f5, root_back, 0.07) + [root_back]
    return lead + trail[1:], wrist, (tip, f4, f5)


def bat_meshes(rim, black):
    """(body, left wing, right wing) mesh data; material slot 0 = black, 1 = rim."""
    out, wrist, fingers = wing_outline()

    def wing(side):
        bm = bmesh.new()
        pts = [Vector((side * x, y, 0.0)) for x, y in out]
        if side < 0:
            pts.reverse()
        g.fill(bm, pts)
        for f in bm.faces:
            f.material_index = 0
        n0 = len(bm.faces)
        g.stroke(bm, pts, 0.012, segs=5, closed=True, joints=False)
        for tipp in fingers:
            g.stroke(bm, [Vector((side * wrist[0], wrist[1], 0.0)), Vector((side * tipp[0], tipp[1], 0.0))],
                     0.008, segs=4, joints=False)
        for f in list(bm.faces)[n0:]:
            f.material_index = 1
        me = vj.finish_bm(bm, smooth=False, name="BatWing")
        me.materials.append(black)
        me.materials.append(rim)
        return me

    bm = bmesh.new()
    sphere = bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=1.0)
    bmesh.ops.scale(bm, vec=(0.06, 0.16, 0.055), verts=sphere["verts"])
    bmesh.ops.translate(bm, vec=(0.0, -0.02, 0.0), verts=sphere["verts"])
    head = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.052)
    bmesh.ops.translate(bm, vec=(0.0, 0.15, 0.012), verts=head["verts"])
    for side in (-1, 1):                                              # pointed ears
        base = Vector((side * 0.028, 0.16, 0.045))
        vj.tube(bm, [base, base + Vector((side * 0.02, -0.005, 0.07))], lambda u: 0.02 * (1 - u) + 0.002,
                segs=6, tip=True)
    body = vj.finish_bm(bm, smooth=True, name="BatBody")
    body.materials.append(rim_body_mat(rim))
    return body, wing(-1), wing(1)


_BODY_MATS = {}


def rim_body_mat(rim):
    """The body uses a facing-based rim of the same color logic as the wing rims (built once per rim material)."""
    if rim.name in _BODY_MATS:
        return _BODY_MATS[rim.name]
    s = vj.Shader(rim.name + "Body")
    col, _, _ = s.obj_info()
    gain = rim.get("gain", 1.0)
    near, far = rim.get("near", (1.5, 5.0)), rim.get("far", (60.0, 120.0))
    fade = s.mul(s.smooth(s.dist, *near), s.inv(s.smooth(s.dist, *far)))
    m = s.emit(col, s.mul(s.rim((0.45, 0.95)), fade, gain * 0.8))
    _BODY_MATS[rim.name] = m
    return m


def rim_mat(name, gain=1.6, near=(1.5, 5.0), far=(60.0, 120.0), kick=0.0):
    """Wing rim light: object color (per bat, constant), faded out close to the lens (big near bats must not become
    bright areas) and far away; optionally lifted by the clock's Kick."""
    s = vj.Shader(name)
    col, _, _ = s.obj_info()
    fade = s.mul(s.smooth(s.dist, *near), s.inv(s.smooth(s.dist, *far)))
    lift = s.add(1.0, s.mul(s.c("Kick"), kick)) if kick else 1.0
    m = s.emit(col, s.mul(fade, lift, s.core(0.6, 1.3), gain))
    m["gain"], m["near"], m["far"] = gain, near, far
    return m


def make_bat(name, meshes, color=(0.28, 0.0, 1.0)):
    body_me, wl_me, wr_me = meshes
    body = bpy.data.objects.new(name, body_me)
    bpy.context.scene.collection.objects.link(body)
    wl = bpy.data.objects.new(name + "WL", wl_me)
    wr = bpy.data.objects.new(name + "WR", wr_me)
    for w, side in ((wl, -1), (wr, 1)):
        bpy.context.scene.collection.objects.link(w)
        w.parent = body
        w.location = (side * SHOULDER, 0.0, 0.01)
    for ob in (body, wl, wr):
        ob.color = (*color, 1.0)
        ob.rotation_mode = "QUATERNION" if ob is body else "XYZ"
    return body, wl, wr


def flap_angle(f, phase=0.0, amp=52.0, bias=8.0, rate=2.0):
    """Wing angle (deg, + = up) at frame f: `rate` flaps per beat, fully down on each 8th note (rate 2) + phase
    (in flaps). Periodic over the loop (whole flaps per loop)."""
    p = rate * vj.beatpos(f) + phase
    return bias - amp * math.cos(2 * math.pi * p)


def key_bat(body, wl, wr, states):
    """states: [(frame, location, rotation quaternion, uniform scale, flap angle deg)]."""
    vj.keyed(body, "location", [(f, tuple(loc)) for f, loc, _, _, _ in states])
    vj.keyed(body, "rotation_quaternion", [(f, tuple(q)) for f, _, q, _, _ in states])
    vj.keyed(body, "scale", [(f, (sc, sc, sc)) for f, _, _, sc, _ in states])
    vj.keyed(wl, "rotation_euler", [(f, (0.0, math.radians(fl), 0.0)) for f, _, _, _, fl in states])
    vj.keyed(wr, "rotation_euler", [(f, (0.0, math.radians(-fl), 0.0)) for f, _, _, _, fl in states])


def heading(vel, up=Vector((0, 0, 1)), bank=0.0):
    """Rotation turning the bat's +Y onto vel (Z up), banked `bank` degrees about its forward axis."""
    q = vel.normalized().to_track_quat("Y", "Z")
    if bank:
        q = q @ Quaternion((0.0, 1.0, 0.0), math.radians(bank))
    return q
