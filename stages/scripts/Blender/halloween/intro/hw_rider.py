"""GRAVEYARD SHIFT intro: the Headless Horseman's ride (Blender 4.5, headless).

The user, 2026-10-10: a pre-stream cutscene, "the headless horseman is riding a horse through the woods to the stage,
head in hand in the left and a lantern on the right", filmed low from the front left looking up. Chosen: a model rides
(not the user), presses on a backstage button run it (hook/intro.cpp).

v6 (2026-10-10 evening). The user saw v5 on the headset: "the quality of the horse needs upped A LOT. it looks like shit
in there". Two causes, both fixed here:
- export() never pre-compensated Unreal's FBX V flip on the VAT data UVs (crowd/hw_crowd.py does). In game the gallop
  read other vertices' offsets, turned 45 degrees and scaled, and the rider and his props never moved. export() now
  flips like hw_crowd and decodes its own output the way Unreal will read it before writing anything (ue_decode).
- the metaball horse and its sine gallop. Replaced by the Quaternius horse (CC0, assets/README.txt) and its keyframed
  Gallop, welded and smoothed (Subdivision 1), restyled black: a burning mane, tail and fetlocks, glowing eyes, a saddle
  on a ragged blanket, stirrups, a bridle and reins. The bake is lit for the stream camera (a cool moon key from its
  side, a rim from behind, the lantern, the pumpkin) and keeps the coat's sheen as that camera sees it.

This builds the rider: the horse, the user's own Horseman avatar (skins/horseman.glb in the tribe hack repo, read only)
posed in the saddle by IK with its head removed, the pumpkin head (heads/horseman.glb) in the left hand and a lantern in
the right. Frame: the horse faces -Y (like the avatar), hooves on z = 0 at their lowest, metres; the seat at SADDLE.

    blender -b --factory-startup --python hw_rider.py -- [--out DIR] [--previews] [--phase-sheet] [--measure] [--export]
(importable: build() makes the rig and its parts in the current scene; hw_animatic.py uses it)
(take the GPU lock for renders: ../run_blender_locked.sh <log> <this file> [args])
"""
import math
import os
import random
import sys

import json
import struct
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "C:/Users/Chris/OneDrive/Desktop/tribe hack"
SKIN, HEAD = REPO + "/skins/horseman.glb", REPO + "/heads/horseman.glb"
HORSE_GLB = os.path.join(HERE, "assets", "quaternius_horse.glb")    # CC0, Quaternius: assets/README.txt
OUT = ARGS[ARGS.index("--out") + 1] if "--out" in ARGS else os.path.join(HERE, "out_rider")
FRAMES = 28                    # one gallop stride in the VAT (+1 wrap row): two per keyed frame of the action
GALLOP_SAMPLES = 56            # the action sampled once into poses that gallop() interpolates (scene time stays free)
GALLOP_HZ = 2.4                # strides/s at hw_intro_path.SPEED: --measure, 2026-10-10: the planted hooves sweep
                               # 1.9-3.0 m a stride (mean 2.4), so 2.4/s keeps them on the ground at 6 m/s
RIDER_KEEP = 0.7               # the avatar decimated to this share of its faces for the headset
SADDLE = Vector((0.0, -0.12, 1.70))       # the seat on the horse's back (the rider's hips sit just above it)
BACK_TOP = SADDLE.z - 0.08                # the horse's back under the saddle: the import is scaled to it
SEAT_BONE = "Torso2"                      # the bone under the saddle: the rider and his props ride on it
UE_FLIPS_V = True              # Unreal's FBX importer stores 1 - V on every UV channel (crowd/hw_crowd.py, verified)
STREAM_CAM = (Vector((1.2, -5.0, 0.5)), Vector((0.0, 0.0, 2.0)))   # intro.halloween.txt "cam loop" in the rider's frame
GLOSS_W = 0.4                  # the coat's baked sheen, view-independent (the stream sees him from ahead and behind)


def log(msg):
    print(f"[RIDER] {msg}", flush=True)


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def activate(ob):
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        if o is not None:
            o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def _world_verts(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    ev.to_mesh_clear()
    co = co.reshape(-1, 3)
    m = np.array(ob.matrix_world)
    return co @ m[:3, :3].T + m[:3, 3]


# ---------------------------------------------------------------- the horse: Quaternius's, scaled, welded, its gallop
_POSES = {}                    # armature name -> GALLOP_SAMPLES poses {bone: (loc, rot, scale)}, the loop closed


def _arm_of(rig):
    return rig if rig.type == "ARMATURE" else next(c for c in rig.children if c.type == "ARMATURE")


def _set_pose(arm, pose):
    for pb in arm.pose.bones:
        loc, rot, scl = pose[pb.name]
        pb.matrix_basis = Matrix.LocRotScale(loc, rot, scl)


def gallop(rig, t):
    """Pose the horse at phase t (0..1) of one stride: the sampled Gallop, interpolated (rig = the root or the armature)."""
    arm = _arm_of(rig)
    poses = _POSES[arm.name]
    x = (t % 1.0) * len(poses)
    i = int(math.floor(x)) % len(poses)
    a = x - math.floor(x)
    A, B = poses[i], poses[(i + 1) % len(poses)]
    for pb in arm.pose.bones:
        la, ra, sa = A[pb.name]
        lb, rb, sb = B[pb.name]
        if ra.dot(rb) < 0.0:
            rb = Quaternion((-rb.w, -rb.x, -rb.y, -rb.z))
        pb.matrix_basis = Matrix.LocRotScale(la.lerp(lb, a), ra.slerp(rb, a), sa.lerp(sb, a))


def _sample_gallop(arm, act):
    """The action at GALLOP_SAMPLES + 1 even steps; the last step's mismatch with the first is spread over the stride
    (the export's last frame is not quite its first), so the loop has no pop. The action is removed afterwards."""
    ad = arm.animation_data or arm.animation_data_create()
    for tr in list(ad.nla_tracks):
        ad.nla_tracks.remove(tr)
    ad.action = act
    slots = list(getattr(act, "slots", []) or [])
    if hasattr(ad, "action_slot") and slots:
        ad.action_slot = next((s for s in slots if s.identifier == "OB" + arm.name), slots[0])
    f0, f1 = act.frame_range
    sc = bpy.context.scene
    raw = []
    for k in range(GALLOP_SAMPLES + 1):
        fr = f0 + (f1 - f0) * k / GALLOP_SAMPLES
        sc.frame_set(int(math.floor(fr)), subframe=fr - math.floor(fr))
        raw.append({pb.name: pb.matrix_basis.decompose() for pb in arm.pose.bones})
    ad.action = None
    moved = sum(1 for nm in raw[0] if (raw[0][nm][1].rotation_difference(raw[GALLOP_SAMPLES // 2][nm][1]).angle > 0.05))
    if moved < 8:
        raise RuntimeError(f"the Gallop action barely moves the rig ({moved} bones): the action or slot did not apply")
    poses = []
    for k in range(GALLOP_SAMPLES):
        a = k / GALLOP_SAMPLES
        pose = {}
        for name, (loc, rot, scl) in raw[k].items():
            l0, r0, s0 = raw[0][name]
            l1, r1, s1 = raw[-1][name]
            d = r0 @ r1.inverted()
            if d.w < 0.0:
                d = Quaternion((-d.w, -d.x, -d.y, -d.z))
            fix = Quaternion().slerp(d, a)
            sfix = [1.0 + (s0[i] / s1[i] - 1.0) * a if abs(s1[i]) > 1e-9 else 1.0 for i in range(3)]
            pose[name] = (loc + (l0 - l1) * a, fix @ rot, Vector([scl[i] * sfix[i] for i in range(3)]))
        poses.append(pose)
    _POSES[arm.name] = poses
    log(f"gallop: '{act.name}' frames {f0:.0f}..{f1:.0f} sampled {GALLOP_SAMPLES}x ({moved} bones turn), the loop closed")


def horse_import():
    """The Quaternius horse under an empty (the rig the animatic moves): the armature scaled so the back under the saddle
    is BACK_TOP above the lowest hoof of the stride and moved so the saddle point lands on SADDLE; the mesh welded into one
    smooth skin under a Subdivision 1; its Gallop sampled (gallop()). Left in the rest pose. -> (root, arm, body)"""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=HORSE_GLB)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == "ARMATURE")
    body = next(o for o in new if o.type == "MESH" and o.name.startswith("Horse"))
    for o in new:
        if o not in (arm, body):
            bpy.data.objects.remove(o)
    acts = [a for a in bpy.data.actions if a.name.split("|")[-1] == "Gallop"]
    act = next((a for a in acts if "|" in a.name), acts[0])
    bm = bmesh.new()                                                  # the flat-shaded copy -> one smooth skin
    bm.from_mesh(body.data)
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.to_mesh(body.data)
    bm.free()
    for p in body.data.polygons:
        p.use_smooth = True
    _sample_gallop(arm, act)
    # the lowest hoof over the stride and the back's top at the saddle point (rest), both in the import's units
    zmin = 1e9
    for k in range(0, GALLOP_SAMPLES, 4):
        _set_pose(arm, _POSES[arm.name][k])
        bpy.context.view_layer.update()
        zmin = min(zmin, float(_world_verts(body)[:, 2].min()))
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    B = arm.data.bones
    fy = (arm.matrix_world @ B["FrontShoulder.L"].head_local).y
    by = (arm.matrix_world @ B["BackShoulder.L"].head_local).y
    ys = fy + 0.30 * (by - fy)                                        # just behind the withers
    co = _world_verts(body)
    near = co[(np.abs(co[:, 0]) < 0.35) & (np.abs(co[:, 1] - ys) < 0.35)]          # the low-poly back: a wide window
    s = BACK_TOP / (float(near[:, 2].max()) - zmin)
    root = link(bpy.data.objects.new("HorseRig", None))
    arm.matrix_world = Matrix.Translation((0.0, SADDLE.y - s * ys, -s * zmin)) @ Matrix.Scale(s, 4) @ arm.matrix_world
    arm.parent = root
    sub = body.modifiers.new("Subdiv", "SUBSURF")                     # after the Armature modifier: smooth deformation
    sub.levels = sub.render_levels = 1
    bpy.context.view_layer.update()
    log(f"horse: Quaternius, {n0} -> {len(body.data.vertices)} verts welded (Subdivision 1 on top), scale {s:.4f}, "
        f"the saddle point at import y {ys:.2f}")
    return root, arm, body


def horse_width(body):
    """Half the barrel's width under the saddle (rest), m."""
    co = _world_verts(body)
    band = co[(np.abs(co[:, 1] - SADDLE.y) < 0.12) & (co[:, 2] > BACK_TOP - 0.75) & (co[:, 2] < BACK_TOP - 0.15)]
    return float(np.abs(band[:, 0]).max())


def measure_stride(rig, body):
    """How far each planted hoof sweeps back over one stride (m): the gallop keeps pace at SPEED / that (strides/s)."""
    hooves = [i for i, m in enumerate(body.data.materials) if m and "Hooves" in m.name]
    tracks = {}
    n = GALLOP_SAMPLES
    for k in range(n):
        gallop(rig, k / n)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        ev = body.evaluated_get(dg)
        me = ev.to_mesh()
        mw = body.matrix_world
        pts = [mw @ me.vertices[v].co for p in me.polygons if p.material_index in hooves for v in p.vertices]
        ev.to_mesh_clear()
        for p in pts:
            key = ("L" if p.x > 0 else "R") + ("F" if p.y < SADDLE.y else "B")
            tracks.setdefault(key, {}).setdefault(k, []).append(p)
    out = {}
    for key, per in tracks.items():
        lows = {k: min(v, key=lambda q: q.z) for k, v in per.items()}
        z0 = min(q.z for q in lows.values())
        stance = sorted(k for k, q in lows.items() if q.z < z0 + 0.03)
        steps = [lows[b].y - lows[a].y for a, b in zip(stance, stance[1:]) if b == a + 1]
        if steps:
            out[key] = (sum(steps) / len(steps)) * n
    gallop(rig, 0.0)
    return out


# ---------------------------------------------------------------- the horse's skin, queried in world space (rest pose)
class Skin:
    def __init__(self, body):
        dg = bpy.context.evaluated_depsgraph_get()
        self.mw = body.matrix_world.copy()
        self.mi = self.mw.inverted()
        self.n3 = self.mw.to_3x3().inverted().transposed()
        self.tree = BVHTree.FromObject(body, dg)

    def near(self, p, off=0.0):
        """(the closest skin point pushed out by off, its normal)"""
        loc, nrm, _, _ = self.tree.find_nearest(self.mi @ Vector(p))
        n = (self.n3 @ nrm).normalized()
        return (self.mw @ loc) + n * off, n

    def cast(self, origin, direction, off=0.0):
        """(where a ray from inside leaves the skin, pushed out by off, its normal facing out), or near() if it misses"""
        o = self.mi @ Vector(origin)
        d = (self.mi.to_3x3() @ Vector(direction)).normalized()
        loc, nrm, _, _ = self.tree.ray_cast(o, d)
        if loc is None:
            return self.near(Vector(origin) + Vector(direction) * 0.2, off)
        n = (self.n3 @ nrm).normalized()
        if n.dot(Vector(direction)) < 0.0:
            n = -n
        return (self.mw @ loc) + n * off, n


def _skinned(name, bm, body, arm, mats):
    """A mesh (world-space bmesh, rest pose) that deforms with the horse: the body's frame, each vertex weighted like the
    body vertex nearest to it, an Armature modifier."""
    me = bpy.data.meshes.new(name)
    mi = body.matrix_world.inverted()
    for v in bm.verts:
        v.co = mi @ v.co
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me))
    ob.parent = body.parent
    ob.matrix_parent_inverse = body.matrix_parent_inverse.copy()
    ob.matrix_basis = body.matrix_basis.copy()
    for m in mats:
        me.materials.append(m)
    src = body.data
    kd = KDTree(len(src.vertices))
    for v in src.vertices:
        kd.insert(v.co, v.index)
    kd.balance()
    names = {g.index: g.name for g in body.vertex_groups}
    groups = {}
    for v in me.vertices:
        _, idx, _ = kd.find(v.co)
        for g in src.vertices[idx].groups:
            if g.weight <= 0.0:
                continue
            nm = names[g.group]
            if nm not in groups:
                groups[nm] = ob.vertex_groups.new(name=nm)
            groups[nm].add([v.index], g.weight, "REPLACE")
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    for p in me.polygons:
        p.use_smooth = True
    return ob


def _tongue(bm, base, up, back, width, length, mats=(0, 1, 2)):
    """A thin flame tongue: a curved 3-segment strip tapering to a point, leaning back; core, body and tip materials."""
    side = back.cross(up)
    if side.length < 1e-6:
        side = Vector((1.0, 0.0, 0.0))
    side.normalize()
    prev = None
    for k in range(4):
        a = k / 3.0
        c = base + up * (length * a) + back * (length * 0.55 * a * a)
        w = width * (1.0 - a) + 0.002
        vs = [bm.verts.new(c + side * w), bm.verts.new(c - side * w)]
        if prev:
            f = bm.faces.new((prev[0], prev[1], vs[1], vs[0]))
            f.material_index = mats[k - 1]
        prev = vs


def horse_flames(body, arm, mats):
    """The burning mane (along the crest), the tail's flames and a ring of small flames over each hoof, skinned."""
    rr = random.Random(7)
    co = _world_verts(body)                                           # rest pose, subdivided skin
    me_mats = body.data.materials
    hair = {i for i, m in enumerate(me_mats) if m and "Hair" in m.name}
    hoof = {i for i, m in enumerate(me_mats) if m and "Hooves" in m.name}
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    me = ev.to_mesh()
    hv = np.array(sorted({v for p in me.polygons if p.material_index in hair for v in p.vertices}), dtype=int)
    fv = np.array(sorted({v for p in me.polygons if p.material_index in hoof for v in p.vertices}), dtype=int)
    ev.to_mesh_clear()
    bm = bmesh.new()
    mane = co[hv][co[hv][:, 1] < SADDLE.y - 0.25]                     # the mane: hair in front of the saddle
    if len(mane):
        y0, y1 = mane[:, 1].min(), mane[:, 1].max()
        nb = 30
        for k in range(nb):
            a = k / (nb - 1)
            yy = y1 + (y0 - y1) * a                                   # from the withers to the poll
            sel = mane[np.abs(mane[:, 1] - yy) < (y1 - y0) / nb * 1.5]
            if not len(sel):
                continue
            top = sel[sel[:, 2].argmax()]
            base = Vector(top) + Vector((rr.uniform(-0.02, 0.02), 0.0, -0.02))
            for _ in range(2):                                        # two thinner, shorter tongues per step
                _tongue(bm, base + Vector((rr.uniform(-0.025, 0.025), rr.uniform(-0.02, 0.02), 0.0)),
                        Vector((rr.uniform(-0.3, 0.3), rr.uniform(0.3, 0.7), 1.0)).normalized(), Vector((0.0, 1.0, 0.0)),
                        rr.uniform(0.009, 0.016), rr.uniform(0.09, 0.22) * (1.0 - 0.3 * a))
    tail = co[hv][co[hv][:, 1] > SADDLE.y + 0.6]
    for k in range(min(22, len(tail))):                               # the tail: tongues streaming back and down
        p = Vector(tail[rr.randrange(len(tail))])
        _tongue(bm, p, Vector((rr.uniform(-0.25, 0.25), 1.0, -0.15)).normalized(), Vector((0.0, 0.3, -1.0)).normalized(),
                rr.uniform(0.016, 0.03), rr.uniform(0.22, 0.42))
    feet = co[fv]
    for sx in (-1, 1):                                                # the fetlocks: a ring of short flames per hoof
        for front in (True, False):
            sel = feet[(np.sign(feet[:, 0]) == sx) & ((feet[:, 1] < SADDLE.y) == front)]
            if not len(sel):
                continue
            c = Vector(sel.mean(axis=0))
            ztop = float(sel[:, 2].max())
            r = float(np.hypot(sel[:, 0] - c.x, sel[:, 1] - c.y).max()) * 0.9
            for j in range(8):
                ang = 2 * math.pi * j / 8 + rr.uniform(-0.2, 0.2)
                base = Vector((c.x + r * math.cos(ang), c.y + r * math.sin(ang), ztop + 0.01))
                _tongue(bm, base, Vector((0.25 * math.cos(ang), 0.25 * math.sin(ang) + 0.3, 1.0)).normalized(),
                        Vector((0.0, 1.0, 0.0)), rr.uniform(0.01, 0.016), rr.uniform(0.07, 0.13))
    ob = _skinned("HorseFlames", bm, body, arm, mats)
    log(f"flames: {len(ob.data.polygons)} faces (mane {len(mane)} hair verts, tail {len(tail)}, hooves {len(feet)})")
    return ob


# ---------------------------------------------------------------- the tack: blanket, saddle, stirrups, bridle, reins
def _grid_faces(bm, rows, mat):
    out = []
    for r in range(len(rows) - 1):
        for c in range(len(rows[r]) - 1):
            f = bm.faces.new((rows[r][c], rows[r][c + 1], rows[r + 1][c + 1], rows[r + 1][c]))
            f.material_index = mat
            out.append(f)
    return out


def _band(bm, pts, nrms, width, mat, closed=False):
    """A flat strap along pts lying on the skin (normals nrms), width wide. -> its faces"""
    n = len(pts)
    prs = []
    for i in range(n):
        t = (pts[(i + 1) % n] if closed or i < n - 1 else pts[i]) - (pts[i - 1] if closed or i > 0 else pts[i])
        b = t.cross(nrms[i])
        b = b.normalized() if b.length > 1e-9 else Vector((0, 0, 1))
        prs.append((bm.verts.new(pts[i] + b * width / 2), bm.verts.new(pts[i] - b * width / 2)))
    out = []
    for i in range(n if closed else n - 1):
        a, b = prs[i], prs[(i + 1) % n]
        f = bm.faces.new((a[0], b[0], b[1], a[1]))
        f.material_index = mat
        out.append(f)
    return out


def _tube(bm, pts, radius, mat, segs=6):
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = t.orthogonal().normalized()
        b = t.cross(a)
        rings.append([bm.verts.new(p + (a * math.cos(2 * math.pi * k / segs) + b * math.sin(2 * math.pi * k / segs)) * radius)
                      for k in range(segs)])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(segs):
            f = bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
            f.material_index = mat


def _ring(bm, centre, normal, radius, tube_r, mat, segs=12):
    """An iron ring (a closed tube) around centre in the plane facing normal."""
    a = normal.orthogonal().normalized()
    b = normal.normalized().cross(a)
    pts = [centre + (a * math.cos(2 * math.pi * k / segs) + b * math.sin(2 * math.pi * k / segs)) * radius for k in range(segs)]
    _tube(bm, pts + [pts[0]], tube_r, mat, segs=5)


def horse_tack(body, arm, hw, mats):
    """Leather (0), cloth (1), iron (2): a ragged blanket over the back, the saddle (seat, pommel, cantle, flaps), the
    stirrup leathers and irons at the rider's feet, a bridle (noseband, cheek pieces, crown, browband, bit rings) and
    loose reins. Skinned like the flames; every sheet faces out of the skin. -> (object, stirrup centres)"""
    sk = Skin(body)
    rr = random.Random(11)
    bm = bmesh.new()
    orient = []
    # the blanket: a sheet draped over the barrel between the legs, conformed to the skin, its hem torn
    ny, na = 12, 15
    rows = []
    for j in range(ny + 1):
        y = SADDLE.y - 0.32 + 0.74 * j / ny
        row = []
        for i in range(na + 1):
            phi = math.radians(-100 + 200 * i / na)                    # 0 = the spine
            guess = Vector((math.sin(phi) * (hw + 0.2), y, BACK_TOP - hw + math.cos(phi) * (hw + 0.2)))
            p, n = sk.near(guess, 0.018)
            if i in (0, na):                                           # the hem: torn, uneven
                p = p + Vector((0, 0, -rr.uniform(0.0, 0.08) - (0.05 if j % 2 else 0.0)))
            row.append(bm.verts.new(p))
        rows.append(row)
    orient += _grid_faces(bm, rows, 1)
    # the saddle: a seat over the blanket, high at the cantle (back) and the pommel (front), leather flaps down the sides
    ny, na = 10, 8
    rows = []
    for j in range(ny + 1):
        u = j / ny
        y = SADDLE.y - 0.27 + 0.55 * u
        lift = 0.03 + 0.10 * max(0.0, (u - 0.75) / 0.25) ** 1.5 + 0.08 * max(0.0, (0.2 - u) / 0.2) ** 1.5
        row = []
        for i in range(na + 1):
            phi = math.radians(-50 + 100 * i / na)
            guess = Vector((math.sin(phi) * (hw + 0.2), y, BACK_TOP - hw + math.cos(phi) * (hw + 0.2)))
            p, n = sk.near(guess, 0.032)
            edge = 1.0 - abs(i / na - 0.5) * 2.0                       # the seat rounds off to its sides
            row.append(bm.verts.new(p + n * lift * (0.35 + 0.65 * edge)))
        rows.append(row)
    orient += _grid_faces(bm, rows, 0)
    for side in (0, na):                                               # close the seat's sides down to the blanket
        col = [rows[j][side] for j in range(ny + 1)]
        low = [bm.verts.new(sk.near(v.co, 0.02)[0]) for v in col]
        for a in range(ny):
            f = bm.faces.new((col[a], col[a + 1], low[a + 1], low[a]))
            f.material_index = 0
            orient.append(f)
    for fy_, lift in ((SADDLE.y - 0.30, 0.16), (SADDLE.y + 0.30, 0.20)):   # pommel and cantle
        p, n = sk.near(Vector((0.0, fy_, BACK_TOP + 0.1)), 0.03)
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=1.0,
                                  matrix=Matrix.Translation(p + n * lift * 0.5) @ Matrix.Diagonal(Vector((0.11, 0.05, lift * 0.5, 1.0))))
    stirrups = {}
    for sx in (-1, 1):                                                 # flaps, leathers, irons
        flap = []
        for j in range(4):
            y = SADDLE.y - 0.16 + 0.32 * j / 3
            col = []
            for k in range(5):
                z = BACK_TOP - 0.12 - 0.42 * k / 4
                p, n = sk.near(Vector((sx * (hw + 0.1), y, z)), 0.036)
                col.append(bm.verts.new(p))
            flap.append(col)
        for j in range(3):
            for k in range(4):
                f = bm.faces.new((flap[j][k], flap[j + 1][k], flap[j + 1][k + 1], flap[j][k + 1]))
                f.material_index = 0
                orient.append(f)
        foot = FEET["Left" if sx > 0 else "Right"]
        top, _ = sk.near(Vector((sx * hw, SADDLE.y + 0.02, BACK_TOP - 0.1)), 0.05)
        iron = foot + Vector((0.0, 0.02, -0.06))
        _tube(bm, [top.lerp(iron + Vector((0, 0, 0.07)), a / 5) for a in range(6)], 0.012, 0)
        _ring(bm, iron, Vector((0.0, 1.0, 0.0)), 0.075, 0.012, 2)
        stirrups["Left" if sx > 0 else "Right"] = iron
    # the bridle: loops around the head where rays from its axis leave the skin, straps on the skin
    hb = arm.data.bones["Head"]
    poll = arm.matrix_world @ hb.head_local
    co = _world_verts(body)
    muzzle = Vector(co[co[:, 1].argmin()])
    axis = (muzzle - poll).normalized()
    up = axis.orthogonal()
    if up.z < 0:
        up = -up
    side = axis.cross(up).normalized()
    up = side.cross(axis).normalized()

    def loop(a, off=0.012, n=16):
        c = poll.lerp(muzzle, a)
        got = [sk.cast(c, up * math.cos(2 * math.pi * k / n) + side * math.sin(2 * math.pi * k / n), off) for k in range(n)]
        return [p for p, _ in got], [nn for _, nn in got]
    nose, nose_n = loop(0.78)
    crown, crown_n = loop(0.10)
    orient += _band(bm, nose, nose_n, 0.035, 0, closed=True)            # noseband, crown piece
    orient += _band(bm, crown, crown_n, 0.03, 0, closed=True)
    for k in (4, 12):                                                  # cheek pieces: noseband side -> crown side
        got = [sk.near(nose[k].lerp(crown[k], i / 8), 0.012) for i in range(9)]
        orient += _band(bm, [p for p, _ in got], [nn for _, nn in got], 0.028, 0)
    c_brow = poll.lerp(muzzle, 0.2)
    brow = [sk.cast(c_brow, up + side * (1.2 * (i / 6 - 0.5)), 0.012) for i in range(7)]
    orient += _band(bm, [p for p, _ in brow], [nn for _, nn in brow], 0.024, 0)
    bits = []
    c_bit = poll.lerp(muzzle, 0.86)
    for sgn in (-1, 1):                                                # the bit rings at the mouth's corners
        p, nn = sk.cast(c_bit, side * sgn - up * 0.6, 0.02)
        _ring(bm, p, nn, 0.035, 0.007, 2, segs=10)
        bits.append(p)
    pom, _ = sk.near(Vector((0.0, SADDLE.y - 0.30, BACK_TOP + 0.1)), 0.12)
    for b in bits:                                                     # the reins: along the neck to the pommel, sagging
        pts = []
        for i in range(12):
            a = i / 11
            p, nn = sk.near(b.lerp(pom, a), 0.03 + 0.05 * math.sin(math.pi * a))
            pts.append(p + Vector((0, 0, -0.05 * math.sin(math.pi * a))))
        _tube(bm, pts, 0.009, 0, segs=5)
    bm.normal_update()
    flipped = 0
    for f in orient:                                                   # sheets face out of the skin (the bake lights them)
        _, nn = sk.near(f.calc_center_median(), 0.0)
        if f.normal.dot(nn) < 0.0:
            f.normal_flip()
            flipped += 1
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    ob = _skinned("HorseTack", bm, body, arm, mats)
    log(f"tack: {len(ob.data.vertices)} verts, {len(ob.data.polygons)} faces ({flipped} sheets turned out); stirrups at "
        + ", ".join(f"{k} ({v.x:.2f},{v.y:.2f},{v.z:.2f})" for k, v in stirrups.items()))
    return ob, stirrups


# ---------------------------------------------------------------- the rider: the user's Horseman, posed by IK
SEAT_HIPS = SADDLE + Vector((0.0, 0.02, 0.10))   # the avatar's Hips bone (its origin) on the saddle
L_HAND = Vector((0.34, -0.55, 2.24))               # left hand: the head held up in front
R_HAND = Vector((-0.50, -0.40, 2.25))              # the lantern held up at head height to light the way: the user could
                                                   # not see it low at his side from the front-left camera
FEET = {"Left": Vector((0.42, -0.08, 0.95)), "Right": Vector((-0.42, -0.08, 0.95))}   # x set from the barrel in build()


def empty(name, loc):
    e = link(bpy.data.objects.new(name, None))
    e.location = loc
    return e


def _rx(pb, deg):
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = (math.radians(deg), 0.0, 0.0)


def rider():
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=SKIN)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == "ARMATURE")
    body = next(o for o in new if o.type == "MESH" and o.vertex_groups)
    for o in new:
        if o not in (arm, body):
            bpy.data.objects.remove(o)
    arm.location = SEAT_HIPS
    bpy.context.view_layer.update()
    P = arm.pose.bones
    _rx(P["Spine"], -6.0)                                            # sit tall, a slight lean back
    for side, sx in (("Left", 1.0), ("Right", -1.0)):
        foot = empty(f"IK_{side}Foot", FEET[side])
        pole = empty(f"IK_{side}Knee", FEET[side] + Vector((0.5 * sx, -1.0, 0.6)))
        c = P[f"{side}Leg"].constraints.new("IK")
        c.target, c.pole_target, c.chain_count, c.pole_angle = foot, pole, 2, math.radians(-90)
        hand = empty(f"IK_{side}Hand", L_HAND if side == "Left" else R_HAND)
        epole = empty(f"IK_{side}Elbow", (L_HAND if side == "Left" else R_HAND) + Vector((0.45 * sx, 0.5, -0.45)))
        c = P[f"{side}ForeArm"].constraints.new("IK")
        c.target, c.pole_target, c.chain_count, c.pole_angle = hand, epole, 2, math.radians(-90)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    posed = bpy.data.meshes.new_from_object(body.evaluated_get(dg))
    rid = link(bpy.data.objects.new("Rider", posed))
    rid.matrix_world = body.matrix_world.copy()
    hand_l = arm.matrix_world @ P["LeftHand"].head
    hand_r = arm.matrix_world @ P["RightHand"].head
    # headless: drop every vertex the Head bone owns (the collar and neck stump belong to Neck: the memory's lesson)
    gi = body.vertex_groups["Head"].index
    drop = {v.index for v in body.data.vertices for g in v.groups if g.group == gi and g.weight > 0.5}
    bm = bmesh.new()
    bm.from_mesh(posed)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in drop], context="VERTS")
    bm.to_mesh(posed)
    bm.free()
    for o in [arm, body] + [o for o in bpy.data.objects if o.name.startswith("IK_")]:
        bpy.data.objects.remove(o)
    rid.data.transform(rid.matrix_world)
    rid.matrix_world = Matrix.Identity(4)
    log(f"rider: {len(posed.vertices)} verts after removing {len(drop)} head verts; hands at "
        f"L ({hand_l.x:.2f},{hand_l.y:.2f},{hand_l.z:.2f}) R ({hand_r.x:.2f},{hand_r.y:.2f},{hand_r.z:.2f})")
    return rid, hand_l, hand_r


def pumpkin_in_hand(hand_l):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=HEAD)
    pk = next(o for o in bpy.data.objects if o not in before and o.type == "MESH")
    pk.location = hand_l + Vector((0.02, -0.06, 0.09))               # in the hand, the face forward (v6: it floated
                                                                     # 5 cm over the wrist; its bottom is 0.117 m
                                                                     # under its origin, so now 3 cm into the grip)
    return pk


def lantern_in_hand(hand_r):
    """An iron lantern hanging from the right hand: a ring handle, a pyramid cap, corner posts and bands framing four
    amber panes, a base. -> (iron, panes, centre)"""
    top = hand_r + Vector((0.0, 0.0, -0.05))
    c = top + Vector((0.0, 0.0, -0.30))
    bm_iron, bm_glass = bmesh.new(), bmesh.new()

    def box(bm, centre, size):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(centre) @ Matrix.Diagonal(Vector((*size, 1.0))))
    bmesh.ops.create_cone(bm_iron, cap_ends=True, segments=4, radius1=0.16, radius2=0.035, depth=0.11,
                          matrix=Matrix.Translation(c + Vector((0, 0, 0.2))) @ Matrix.Rotation(math.pi / 4, 4, "Z"))
    box(bm_iron, c + Vector((0, 0, -0.165)), (0.23, 0.23, 0.035))      # base
    for dz in (-0.135, 0.135):                                         # bands
        for sx, sy, w, d in ((1, 0, 0.018, 0.22), (-1, 0, 0.018, 0.22), (0, 1, 0.22, 0.018), (0, -1, 0.22, 0.018)):
            box(bm_iron, c + Vector((sx * 0.105, sy * 0.105, dz)), (w, d, 0.022))
    for sx in (-1, 1):                                                 # corner posts
        for sy in (-1, 1):
            box(bm_iron, c + Vector((sx * 0.105, sy * 0.105, 0.0)), (0.022, 0.022, 0.29))
    for k in range(8):                                                 # the handle: a half ring of 8 segments
        a0, a1 = math.pi * k / 8, math.pi * (k + 1) / 8
        p0 = top + Vector((0.06 * math.cos(a0), 0, 0.06 * math.sin(a0) - 0.06))
        p1 = top + Vector((0.06 * math.cos(a1), 0, 0.06 * math.sin(a1) - 0.06))
        d = p1 - p0
        bmesh.ops.create_cube(bm_iron, size=1.0, matrix=Matrix.Translation((p0 + p1) / 2)
                              @ d.to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Diagonal(Vector((0.012, 0.012, d.length, 1.0))))
    for k in range(4):                                                 # four panes just inside the posts, a cross of
        ang = math.pi / 2 * k                                          # mullions over each
        o_ = Vector((math.cos(ang), math.sin(ang), 0.0))
        t_ = Vector((-math.sin(ang), math.cos(ang), 0.0))
        pc = c + o_ * 0.098
        vs = [bm_glass.verts.new(pc + t_ * sx_ * 0.096 + Vector((0, 0, sz_ * 0.124)))
              for sx_, sz_ in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        bm_glass.faces.new(vs)
        box(bm_iron, c + o_ * 0.104, (0.014 + 0.2 * abs(t_.x), 0.014 + 0.2 * abs(t_.y), 0.014))
        box(bm_iron, c + o_ * 0.104, (0.014, 0.014, 0.26))
    iron = link(bpy.data.objects.new("LanternIron", bpy.data.meshes.new("LanternIron")))
    bm_iron.to_mesh(iron.data)
    glass = link(bpy.data.objects.new("LanternGlass", bpy.data.meshes.new("LanternGlass")))
    bm_glass.to_mesh(glass.data)
    return iron, glass, c


# ---------------------------------------------------------------- materials, preview lights, cameras
def mat(name, rgb, emit=0.0, rough=0.6, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = spec
    if emit:
        b.inputs["Emission Color"].default_value = (*rgb, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


def shadowless(m):
    """Cycles: shadow rays pass through (the lantern's panes and the pumpkin let their own light out in the bake)."""
    nt = m.node_tree
    out = next(nd for nd in nt.nodes if nd.type == "OUTPUT_MATERIAL")
    surf = out.inputs["Surface"].links[0].from_socket
    lp, tr, mix = nt.nodes.new("ShaderNodeLightPath"), nt.nodes.new("ShaderNodeBsdfTransparent"), nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Shadow Ray"], mix.inputs["Fac"])
    nt.links.new(surf, mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m


def assign(ob, m):
    ob.data.materials.clear()
    ob.data.materials.append(m)


COAT = {"Main": (0.030, 0.027, 0.031), "Main_Light": (0.048, 0.044, 0.050), "Main_Dark": (0.018, 0.016, 0.019),
        "Hair": (0.010, 0.009, 0.010), "Muzzle": (0.014, 0.011, 0.011), "Hooves": (0.035, 0.031, 0.029)}


def restyle_horse(body):
    """The Quaternius colours -> a black horse with a sheen and burning eyes (slot by slot, by the source names)."""
    eyes = mat("HorseEyes", (1.0, 0.32, 0.04), emit=1.0)
    pupils = mat("HorsePupils", (0.9, 0.12, 0.02), emit=1.0)
    cache = {}
    for i, m in enumerate(body.data.materials):
        src = (m.name if m else "").split(".")[0]
        if src == "Eye_White":
            new = eyes
        elif src == "Eye_Black":
            new = pupils
        else:
            rgb = COAT.get(src, COAT["Main"])
            new = cache.get(src) or mat("Coat_" + src, rgb, rough=0.32 if src.startswith("Main") else 0.6, spec=0.6)
            cache[src] = new
        body.data.materials[i] = new


def preview_setup(lantern_c, pumpkin):
    """Night, the lantern and the pumpkin's glow, a cool moon key from the stream camera's side and a rim from behind
    (lights that ride with the horse: the bake keeps them), EEVEE, a camera."""
    scene = bpy.context.scene
    w = bpy.data.worlds.new("Night")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.006, 0.007, 0.016, 1)
    scene.world = w
    for name, kind, loc, power, col in (("Lantern", "POINT", lantern_c, 95.0, (1.0, 0.62, 0.25)),
                                        ("PumpkinGlow", "POINT", pumpkin.matrix_world.translation + Vector((0.0, -0.32, -0.05)),
                                         7.0, (1.0, 0.45, 0.1))):            # in front of the face, not inside the shell
        ld = bpy.data.lights.new(name, kind)
        ld.energy, ld.color, ld.shadow_soft_size = power, col, 0.05
        lo = link(bpy.data.objects.new(name, ld))
        lo.location = loc
    for name, dirn, power, col in (("Moon", (-0.45, 0.55, -0.70), 1.2, (0.6, 0.7, 1.0)),
                                   ("Rim", (0.50, -0.60, -0.62), 1.3, (0.7, 0.8, 1.0))):
        sun = bpy.data.lights.new(name, "SUN")
        sun.energy, sun.color, sun.angle = power, col, math.radians(3)
        so = link(bpy.data.objects.new(name, sun))
        so.rotation_euler = Vector(dirn).to_track_quat("-Z", "Y").to_euler()
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 32
    scene.render.resolution_x, scene.render.resolution_y = 960, 960
    scene.view_settings.view_transform = "Standard"
    cd = bpy.data.cameras.new("cam")
    cam = link(bpy.data.objects.new("cam", cd))
    scene.camera = cam
    return cam


def shoot(cam, name, pos, tgt, lens=28):
    scene = bpy.context.scene
    cam.data.lens = lens
    cam.location = pos
    cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    log("render " + scene.render.filepath)


# ---------------------------------------------------------------- build (importable)
def build(materials=True):
    """The horse, its rig and everything that rides on it, in the current scene, posed at gallop phase 0.
    -> dict(rig (the empty to move), arm, horse, parts (every mesh that rides on it, horse first), lantern_c, pumpkin,
    rider)."""
    root, arm, horse = horse_import()                                 # rest pose from here until the end
    hw = horse_width(horse)
    for side, sx in (("Left", 1.0), ("Right", -1.0)):
        FEET[side] = Vector((sx * (hw + 0.17), FEET[side].y, FEET[side].z))
    flame_m = [mat("FlameCore", (1.0, 0.62, 0.12), emit=1.0), mat("Flame", (1.0, 0.33, 0.03), emit=1.0),
               mat("FlameTip", (0.75, 0.07, 0.01), emit=1.0)]
    tack_m = [mat("Leather", (0.055, 0.032, 0.02), rough=0.45), mat("Blanket", (0.028, 0.014, 0.034), rough=0.9, spec=0.2),
              mat("IronTack", (0.06, 0.06, 0.065), rough=0.35)]
    flames = horse_flames(horse, arm, flame_m)
    tack, _ = horse_tack(horse, arm, hw, tack_m)
    rid, hand_l, hand_r = rider()
    pumpkin = pumpkin_in_hand(hand_l)
    iron, glass, lantern_c = lantern_in_hand(hand_r)
    bone = arm.data.bones[SEAT_BONE]
    rest = arm.matrix_world @ bone.matrix_local @ Matrix.Translation((0.0, bone.length, 0.0))
    for ob in (rid, pumpkin, iron, glass):                            # rigid on the bone under the saddle (from rest)
        ob.parent = arm
        ob.parent_type = "BONE"
        ob.parent_bone = SEAT_BONE
        ob.matrix_parent_inverse = rest.inverted()
    if materials:
        restyle_horse(horse)
        assign(iron, mat("Iron", (0.035, 0.035, 0.04), rough=0.4))
        assign(glass, shadowless(mat("LanternLight", (1.0, 0.42, 0.07), emit=1.0)))
    arm.data.pose_position = "POSE"
    gallop(root, 0.0)
    bpy.context.view_layer.update()
    log(f"barrel half-width {hw:.2f} m; stirrups at x +-{hw + 0.17:.2f}")
    return {"rig": root, "arm": arm, "horse": horse, "parts": [horse, flames, tack, rid, pumpkin, iron, glass],
            "lantern_c": lantern_c, "pumpkin": pumpkin, "rider": rid}


# ---------------------------------------------------------------- export for the headset (the crowd's VAT format)
def _write_exr(path, rgba):
    """Uncompressed half-float scanline OpenEXR, row 0 = the TOP (Unreal's V 0): hw_crowd.write_exr's layout."""
    h, w, _ = rgba.shape
    dt = np.dtype("<f2")

    def attr(name, typ, data):
        return name.encode() + b"\0" + typ.encode() + b"\0" + struct.pack("<i", len(data)) + data
    chl = b"".join(c.encode() + b"\0" + struct.pack("<iBBBBii", 1, 0, 0, 0, 0, 1, 1) for c in "ABGR") + b"\0"
    hdr = struct.pack("<ii", 20000630, 2)
    hdr += attr("channels", "chlist", chl) + attr("compression", "compression", b"\0")
    hdr += attr("dataWindow", "box2i", struct.pack("<iiii", 0, 0, w - 1, h - 1))
    hdr += attr("displayWindow", "box2i", struct.pack("<iiii", 0, 0, w - 1, h - 1))
    hdr += attr("lineOrder", "lineOrder", b"\0") + attr("pixelAspectRatio", "float", struct.pack("<f", 1.0))
    hdr += attr("screenWindowCenter", "v2f", struct.pack("<ff", 0.0, 0.0)) + attr("screenWindowWidth", "float", struct.pack("<f", 1.0))
    hdr += b"\0"
    line = w * 4 * dt.itemsize
    first = len(hdr) + 8 * h
    out = bytearray(hdr) + struct.pack(f"<{h}Q", *[first + y * (8 + line) for y in range(h)])
    for y in range(h):
        px = rgba[y].astype(dt)
        out += struct.pack("<ii", y, line) + b"".join(px[:, c].tobytes() for c in (3, 2, 1, 0))
    open(path, "wb").write(out)


def _write_png(path, rgb_lin):
    """8-bit sRGB PNG from linear RGB, row 0 = the top."""
    v = np.clip(rgb_lin, 0.0, 1.0)
    enc = np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055)
    a = (np.clip(enc, 0, 1) * 255 + 0.5).astype(np.uint8)
    h, w, _ = a.shape
    raw = b"".join(b"\0" + a[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    open(path, "wb").write(png + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def ue_flip(v):
    """What to write so Unreal's FBX import (which stores 1 - V) ends up holding v."""
    return 1.0 - v if UE_FLIPS_V else v


def ue_decode(written, tex, W, rows, H, p, frames=FRAMES):
    """The VAT offsets hw_materials.vat_crowd computes for every vertex at loop position p (0..1), from the per-vertex
    UV values AS WRITTEN to the FBX: Unreal's import flips each V first. written: dict UV name -> (n, 2) array."""
    rd = {k: np.stack([v[:, 0], 1.0 - v[:, 1] if UE_FLIPS_V else v[:, 1]], axis=1) for k, v in written.items()}
    vid, clip = rd["VatIndex"][:, 0], rd["VatIndex"][:, 1]
    c, s = rd["VatRotScale"][:, 0], rd["VatRotScale"][:, 1]
    msz, phase = rd["VatScalePhase"][:, 0], rd["VatScalePhase"][:, 1]
    rate = rd["VatRate"][:, 0]
    f = np.mod(p * rate + phase, 1.0) * frames
    f0 = np.floor(f)
    a = (f - f0)[:, None]
    row = clip * rows + f0

    def tap(r):                                                       # TF_NEAREST, TA_CLAMP, mip 0
        x = np.clip(np.floor(vid + 0.5).astype(int), 0, W - 1)
        y = np.clip(np.floor(r + 0.5).astype(int), 0, H - 1)
        return tex[y, x, :3]
    o = tap(row) * (1 - a) + tap(row + 1) * a
    ox = o[:, 0] * np.sign(msz)
    return np.stack([c * ox - s * o[:, 1], s * ox + c * o[:, 1], np.abs(msz) * o[:, 2]], axis=1)


def export(out_dir, bake_size=2048, samples=1024, exposure=4.0):
    """SM_HwRider.fbx (one mesh: UVMap = the bake, VatIndex / VatRotScale / VatScalePhase / VatRate as the crowd's, the V
    flip pre-compensated), T_HwRider.png (Cycles: the stream camera's light; diffuse + its view of the sheen + every
    emitter), T_HwRiderVAT.exr + .json (offsets from frame 0 over one stride; hw_materials.vat_crowd plays it at
    GALLOP_HZ). Nothing is written unless ue_decode reproduces every frame from the written data (+-3 mm)."""
    os.makedirs(out_dir, exist_ok=True)
    o = build()
    rig, parts = o["rig"], o["parts"]
    rid = o["rider"]                                                  # the avatar, lighter for the headset
    dec = rid.modifiers.new("Dec", "DECIMATE")
    dec.ratio = RIDER_KEEP
    activate(rid)
    bpy.ops.object.modifier_apply(modifier="Dec")
    # one mesh at frame 0: the parts' world geometry, materials and UVs, in a fixed order (the VAT's columns)
    gallop(rig, 0.0)
    bpy.context.view_layer.update()
    bm = bmesh.new()
    uv_src = bm.loops.layers.uv.new("UVMap")
    mats, counts = [], []
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in parts:
        me = ob.evaluated_get(dg).to_mesh()
        me.transform(ob.matrix_world)
        vs = [bm.verts.new(v.co) for v in me.vertices]
        bm.verts.ensure_lookup_table()
        uvl = me.uv_layers.active
        slot0 = len(mats)
        mats += [m for m in me.materials] or [None]
        for poly in me.polygons:
            try:
                f = bm.faces.new([vs[i] for i in poly.vertices])
            except ValueError:
                continue
            f.material_index = slot0 + min(poly.material_index, max(0, len(me.materials) - 1))
            f.smooth = poly.use_smooth
            if uvl:
                for lp, li in zip(f.loops, poly.loop_indices):
                    lp[uv_src].uv = uvl.data[li].uv
        counts.append(len(me.vertices))
        ob.evaluated_get(dg).to_mesh_clear()
    me = bpy.data.meshes.new("SM_HwRider")
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    comb = link(bpy.data.objects.new("SM_HwRider", me))
    n = len(me.vertices)
    log(f"combined: {n} verts, {len(me.polygons)} faces from {len(parts)} parts ({counts})")
    # the VAT: every part's world vertices over one stride, offsets from frame 0
    W = 2048
    bands = (n + W - 1) // W
    rows = FRAMES + 1
    H = 1 << (bands * rows - 1).bit_length()
    tex = np.zeros((H, W, 4), dtype=np.float32)
    tex[..., 3] = 1.0
    base, truth = None, []
    for f in range(rows):
        gallop(rig, (f % FRAMES) / FRAMES)
        bpy.context.view_layer.update()
        pos = np.concatenate([_world_verts(ob) for ob in parts])
        if len(pos) != n:
            raise RuntimeError(f"frame {f}: {len(pos)} verts, expected {n} (a part changed topology)")
        if base is None:
            base = pos.copy()
        off = pos - base
        truth.append(off)
        for b in range(bands):
            seg = off[b * W:(b + 1) * W]
            tex[b * rows + f, :len(seg), :3] = seg
    gallop(rig, 0.0)
    bpy.context.view_layer.update()
    # the per-vertex VAT channels (UV1..UV4), written pre-flipped as hw_crowd does, then decoded as Unreal will
    idx = np.arange(n)
    one = np.tile([1.0, ue_flip(0.0)], (n, 1))
    written = {"VatIndex": np.stack([idx % W, 1.0 - idx // W if UE_FLIPS_V else idx // W], axis=1).astype(np.float64),
               "VatRotScale": one, "VatScalePhase": one.copy(), "VatRate": one.copy()}
    tex16 = tex.astype(np.float16).astype(np.float32)                 # what the RGBA16F texture holds
    worst = 0.0
    for f in range(FRAMES):
        for half in (0.0, 0.5):
            got = ue_decode(written, tex16, W, rows, H, (f + half) / FRAMES)
            want = truth[f] if half == 0.0 else (truth[f] + truth[f + 1]) / 2
            worst = max(worst, float(np.abs(got - want).max()))
    if worst > 0.003:
        raise RuntimeError(f"ue_decode check: the VAT decodes {worst * 1000:.1f} mm off (Unreal would draw it wrong)")
    log(f"ue_decode check: every frame and half frame decodes within {worst * 1000:.2f} mm, as Unreal reads the FBX")
    _write_exr(os.path.join(out_dir, "T_HwRiderVAT.exr"), tex)
    meta = {"what": "GRAVEYARD SHIFT intro rider VAT (intro/hw_rider.py v6): offsets (m, Blender space) from frame 0 of "
                    "one gallop stride; columns = vertex % 2048, UV1.y = vertex // 2048 (the band, read as the clip); "
                    "rows = band * rows_per_clip + frame (row 0 = top); data UVs written as 1 - v (Unreal flips V)",
            "texture": "T_HwRiderVAT.exr", "width": W, "height": H, "frames_per_clip": FRAMES, "rows_per_clip": rows,
            "beats_per_clip": 140.0 / (60.0 * GALLOP_HZ), "loop_rate": GALLOP_HZ, "axis_scale": [100.0, -100.0, 100.0],
            "ue_flips_v": UE_FLIPS_V, "vertices": n, "bands": bands, "decode_check_mm": round(worst * 1000, 3),
            "horse": "Quaternius Horse (CC0), assets/quaternius_horse.glb",
            "max_offset_m": float(np.abs(tex[..., :3]).max())}
    json.dump(meta, open(os.path.join(out_dir, "T_HwRiderVAT.json"), "w"), indent=1)
    log(f"VAT {W}x{H}: {bands} bands x {rows} rows, max offset {meta['max_offset_m']:.2f} m")
    for name in ("VatIndex", "VatRotScale", "VatScalePhase", "VatRate"):
        lay = me.uv_layers.new(name=name).data
        vals = written[name]
        for poly in me.polygons:
            for li, v in zip(poly.loop_indices, poly.vertices):
                lay[li].uv = (float(vals[v, 0]), float(vals[v, 1]))
    # the bake: a fresh atlas as the active UV, the parts' own UVs still feed their textures (render UV)
    bake_uv = me.uv_layers.new(name="BakeUV")
    me.uv_layers.active = bake_uv
    me.uv_layers["UVMap"].active_render = True
    activate(comb)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    for ob in parts:
        ob.hide_render = True
    glass = parts[-1]
    lantern_now = glass.matrix_world @ (sum((v.co for v in glass.data.vertices), Vector()) / len(glass.data.vertices))
    preview_setup(lantern_now, o["pumpkin"])
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dev
            prefs.refresh_devices()
            if any(d.type == dev for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == dev
                scene.cycles.device = "GPU"
                log(f"Cycles on {dev}")
                break
        except Exception as e:  # noqa: BLE001
            log(f"{dev} unavailable: {e}")
    scene.cycles.samples = samples
    cam = scene.camera
    cam.location = STREAM_CAM[0]
    cam.rotation_euler = (STREAM_CAM[1] - STREAM_CAM[0]).to_track_quat("-Z", "Y").to_euler()
    # the sheen is baked from above each surface (view-independent) at GLOSS_W: baked as the front camera sees it,
    # the rump flared near white when the exit camera follows from behind
    img = bpy.data.images.new("T_HwRider", bake_size, bake_size, alpha=False, float_buffer=True)
    for m in me.materials:
        if m is None:
            continue
        tx = m.node_tree.nodes.new("ShaderNodeTexImage")
        tx.image = img
        for nd in m.node_tree.nodes:
            nd.select = False
        tx.select = True
        m.node_tree.nodes.active = tx
    activate(comb)
    passes = {}
    for kind, pf in (("DIFFUSE", {"DIRECT", "INDIRECT", "COLOR"}), ("GLOSSY", {"DIRECT", "INDIRECT", "COLOR"}),
                     ("EMIT", set())):
        bpy.ops.object.bake(type=kind, pass_filter=pf, margin=6, use_clear=True)
        px = np.empty(bake_size * bake_size * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        passes[kind] = px.reshape(bake_size, bake_size, 4)[::-1, :, :3].copy()
        log(f"bake {kind}: mean {passes[kind].mean():.4f}, p99 {np.percentile(passes[kind], 99):.4f}")
    lin = (1.0 - np.exp(-(passes["DIFFUSE"] + GLOSS_W * passes["GLOSSY"]) * exposure)) + np.clip(passes["EMIT"], 0.0, 1.0)
    _write_png(os.path.join(out_dir, "T_HwRider.png"), lin)
    log(f"baked T_HwRider {bake_size}px at {samples} samples, exposure {exposure}")
    # ship UV0 = the bake: move BakeUV to the front by rebuilding the layer order
    order = ["BakeUV", "VatIndex", "VatRotScale", "VatScalePhase", "VatRate"]
    data = {k: [tuple(d.uv) for d in me.uv_layers[k].data] for k in order}
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    for k in order:
        lay = me.uv_layers.new(name="UVMap" if k == "BakeUV" else k)
        for d, uv in zip(lay.data, data[k]):
            d.uv = uv
    me.materials.clear()
    bpy.ops.object.select_all(action="DESELECT")
    comb.select_set(True)
    bpy.context.view_layer.objects.active = comb
    bpy.ops.export_scene.fbx(filepath=os.path.join(out_dir, "SM_HwRider.fbx"), use_selection=True, object_types={"MESH"},
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z",
                             axis_up="Y", mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False)
    log(f"exported SM_HwRider.fbx ({n} verts) to {out_dir}")


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if "--export" in ARGS:
        export(OUT)
    else:
        os.makedirs(OUT, exist_ok=True)
        o = build()
        rig = o["rig"]
        if "--measure" in ARGS:
            sys.path.insert(0, HERE)
            import hw_intro_path as ip
            st = measure_stride(rig, o["horse"])
            for k, v in sorted(st.items()):
                log(f"stride {k}: the planted hoof sweeps {v:.2f} m per stride -> {ip.SPEED / abs(v):.2f} strides/s at "
                    f"{ip.SPEED} m/s")
        if "--previews" in ARGS or "--phase-sheet" in ARGS:
            cam = preview_setup(o["lantern_c"], o["pumpkin"])
            if "--previews" in ARGS:
                shoot(cam, "preview_cutscene", (2.6, -4.6, 0.55), (0.0, -0.4, 2.1), 24)
                shoot(cam, "preview_stream", tuple(STREAM_CAM[0]), tuple(STREAM_CAM[1]), 22)
                shoot(cam, "preview_side", (6.5, -0.2, 1.7), (0.0, -0.2, 1.5), 30)
                shoot(cam, "preview_front", (0.0, -6.5, 2.0), (0.0, -0.5, 1.7), 30)
                shoot(cam, "preview_back34", (-3.5, 4.5, 2.6), (0.0, -0.2, 1.7), 28)
                shoot(cam, "preview_head", (1.4, -2.6, 2.3), (0.0, -1.0, 2.0), 35)
            if "--phase-sheet" in ARGS:
                for i in range(8):
                    gallop(rig, i / 8.0)
                    bpy.context.view_layer.update()
                    shoot(cam, f"phase_{i}", (6.5, -0.2, 1.4), (0.0, -0.2, 1.3), 30)
    log("done")
