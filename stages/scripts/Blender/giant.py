"""The giant intro (the user, 2026-10-06): "a moving platform where i start very high up in the air with a cape that
drapes to the floor ... the platform im standing on, has a button ... ill que the track while im at the decks, turn
around and press the button and the platform raises up ... press the button again and the platform will slowly come
down and im right at the decks", "when im on the ground no cape". Height chosen in the headset: platform 5.45 m, eyes 7 m.

Builds three meshes for build_dino.py (Blender 4.5 headless; writes FBX + giant_manifest.txt to DINO_GIANT_OUT or
out_giant/). Coordinates are Tribe's floor frame, NOT dropped: the riser top (Tribe's floor) is z=0, the DJ faces -Y,
Tribe's mixer ends at y ~0.63. Everything moves in the material (World Position Offset) from MPC_DinoGiant, which the
mod (hook/dumper.cpp, giant_*) drives every frame, so the meshes are authored at rest:
- SM_DinoGiantLift: the lift plate under the DJ, a telescoping column, the button pedestal. UV1.x = lift weight
  (0 stays on the floor, 1 rides at the full height, 0.5 the middle telescope stage).
- SM_DinoGiantGlow: the button cap (red) and the plate's edge strips (cyan); vertex colour = emissive colour,
  UV1 = (lift weight, button mask), UV0.x = 1 on the cap only (it sinks on a press).
- SM_DinoGiantRobe: the floor-length robe. Rest pose = a 1 m tall wall standing on the hem ellipse (every ring sits on
  the hem's x/y), UV1 = (h: 0 hem .. 1 shoulders, theta 0..1). The material pulls each ring from the hem up to the
  shoulders (MPC RobeTop) with a flare that covers the plate. Faces point outward: from inside (the DJ) it is culled.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.environ.get("DINO_GIANT_OUT") or os.path.join(HERE, "out_giant")

PLATE = {"x0": -0.60, "x1": 0.60, "y0": 0.70, "y1": 1.70, "t": 0.06}    # top flush with the floor when down; the robe covers it
COLUMN = (0.0, 0.95)                                                       # under the DJ: inside the slim robe                                                       # telescope centre (x, y)
BUTTON = Vector((0.0, 1.52, 1.06))                                        # cap centre at rest (the hook has it too)
# v2 after the user: "the cape ... is way too large. try to get close to the picture reference. more skinnier at the
# top with widening at the bottom": 2.8 m wide at the floor (was 5.6), front edge still y 0.68 behind the gear
HEM = {"cx": 0.0, "cy": 1.68, "ax": 1.4, "by": 1.0}
N_THETA, N_H = 64, 28


def log(msg):
    print("[GIANT] " + msg, flush=True)


def new_obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def set_uv1(bm, faces_w):
    """faces_w: [(face, (u, v) per loop or a constant (u, v))] -> UV1 ("LiftData")."""
    layer = bm.loops.layers.uv.get("LiftData") or bm.loops.layers.uv.new("LiftData")
    for f, w in faces_w:
        for loop in f.loops:
            loop[layer].uv = w(loop.vert.co) if callable(w) else w


def box(bm, lo, hi):
    """Axis-aligned box from lo to hi; returns its faces."""
    ret = bmesh.ops.create_cube(bm, size=1.0)
    vs = ret["verts"]
    c = (Vector(lo) + Vector(hi)) / 2
    s = Vector(hi) - Vector(lo)
    bmesh.ops.transform(bm, verts=vs, matrix=Matrix.Translation(c) @ Matrix.Diagonal(Vector((s.x, s.y, s.z, 1.0))))
    return list({f for v in vs for f in v.link_faces})


def cylinder(bm, cx, cy, r, z0, z1, segs=24, cap=True):
    ret = bmesh.ops.create_cone(bm, cap_ends=cap, segments=segs, radius1=r, radius2=r, depth=1.0,
                                matrix=Matrix.Translation((cx, cy, 0.5)))
    vs = ret["verts"]
    for v in vs:                                                       # z 0..1 -> z0..z1 (keeps top/bottom identity)
        v.co.z = z0 + (z1 - z0) * v.co.z
    return list({f for v in vs for f in v.link_faces})


def top_only(bm, faces):
    """Keep only the up-facing faces of a box (the rest is deleted): visible from above, invisible from below."""
    for f in faces:
        f.normal_update()
    drop = [f for f in faces if f.normal.z < 0.5]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    return [f for f in faces if f.is_valid]


def uv_init(bm):
    bm.loops.layers.uv.new("UVMap")
    bm.loops.layers.uv.new("LiftData")


def build_lift():
    bm = bmesh.new()
    uv_init(bm)
    P = PLATE
    faces = box(bm, (P["x0"], P["y0"], -P["t"]), (P["x1"], P["y1"], 0.0))      # the plate (moves fully)
    faces = top_only(bm, faces)                                            # seen from above only (the slim robe can't hide it)
    set_uv1(bm, [(f, (1.0, 0.0)) for f in faces])
    # telescope: an outer stage (bottom on the floor, top at half height) and an inner stage (half -> under the plate);
    # at rest both collapse into the plate's thickness (z -0.06..-0.01), so nothing shows when the lift is down
    cx, cy = COLUMN
    outer = cylinder(bm, cx, cy, 0.30, -0.055, -0.035)
    set_uv1(bm, [(f, lambda co: (0.0 if co.z < -0.045 else 0.5, 0.0)) for f in outer])
    inner = cylinder(bm, cx, cy, 0.22, -0.050, -0.010)
    set_uv1(bm, [(f, lambda co: (0.5 if co.z < -0.03 else 1.0, 0.0)) for f in inner])
    collar = cylinder(bm, cx, cy, 0.42, -0.06, -0.058)                     # floor collar (stays)
    set_uv1(bm, [(f, (0.0, 0.0)) for f in collar])
    # button pedestal behind the DJ: post + housing tilted toward the DJ (who turns around to face +Y)
    post = box(bm, (-0.06, BUTTON.y + 0.02 - 0.06, 0.0), (0.06, BUTTON.y + 0.02 + 0.06, BUTTON.z - 0.09))
    set_uv1(bm, [(f, (1.0, 0.0)) for f in post])
    housing = box(bm, (-0.16, BUTTON.y - 0.11, BUTTON.z - 0.10), (0.16, BUTTON.y + 0.11, BUTTON.z - 0.02))
    set_uv1(bm, [(f, (1.0, 0.0)) for f in housing])
    ob = new_obj("SM_DinoGiantLift", bm)
    log(f"lift: {len(ob.data.polygons)} faces")
    return ob


def build_glow():
    bm = bmesh.new()
    uv_init(bm)
    col = bm.loops.layers.color.new("Col")
    def paint(faces, rgb):
        for f in faces:
            for loop in f.loops:
                loop[col] = (*rgb, 1.0)
    cap = cylinder(bm, BUTTON.x, BUTTON.y, 0.075, BUTTON.z - 0.02, BUTTON.z + 0.02, segs=28)
    paint(cap, (1.0, 0.08, 0.04))
    set_uv1(bm, [(f, (1.0, 1.0)) for f in cap])                          # button mask = 1
    press = bm.loops.layers.uv["UVMap"]                                  # UV0.x = 1: the cap sinks on a press (giant_glow)
    for f in cap:
        for loop in f.loops:
            loop[press].uv = (1.0, 0.0)
    ring = cylinder(bm, BUTTON.x, BUTTON.y, 0.10, BUTTON.z - 0.025, BUTTON.z - 0.015, segs=28)
    paint(ring, (1.0, 0.25, 0.05))
    set_uv1(bm, [(f, (1.0, 1.0)) for f in ring])
    P, w, h = PLATE, 0.03, 0.012                                         # edge strips on the plate top
    strips = []
    for lo, hi in (((P["x0"], P["y0"], 0.0), (P["x1"], P["y0"] + w, h)), ((P["x0"], P["y1"] - w, 0.0), (P["x1"], P["y1"], h)),
                   ((P["x0"], P["y0"], 0.0), (P["x0"] + w, P["y1"], h)), ((P["x1"] - w, P["y0"], 0.0), (P["x1"], P["y1"], h))):
        strips += box(bm, lo, hi)
    strips = top_only(bm, strips)                                          # likewise: the DJ sees them, the crowd doesn't
    paint(strips, (0.2, 0.9, 1.0))
    set_uv1(bm, [(f, (1.0, 0.0)) for f in strips])
    ob = new_obj("SM_DinoGiantGlow", bm)
    log(f"glow: {len(ob.data.polygons)} faces")
    return ob


def hem_point(t):
    a = 2 * math.pi * t
    return Vector((HEM["cx"] + HEM["ax"] * math.cos(a), HEM["cy"] + HEM["by"] * math.sin(a), 0.0))


def build_robe():
    bm = bmesh.new()
    uv0 = bm.loops.layers.uv.new("UVMap")
    data = bm.loops.layers.uv.new("LiftData")
    rings = []
    for j in range(N_H + 1):
        h = j / N_H
        ring = []
        for i in range(N_THETA):
            p = hem_point(i / N_THETA)
            p.z = h * 1.0                                                  # rest: a 1 m wall on the hem
            ring.append(bm.verts.new(p))
        rings.append(ring)
    for j in range(N_H):
        for i in range(N_THETA):
            i2 = (i + 1) % N_THETA
            f = bm.faces.new((rings[j][i], rings[j][i2], rings[j + 1][i2], rings[j + 1][i]))
            for loop, (ii, jj) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                loop[uv0].uv = (ii / N_THETA, jj / N_H)
                loop[data].uv = (jj / N_H, ii / N_THETA)                   # (h, theta)
    bm.normal_update()
    out = 0                                                                # outward = away from the hem centre
    for f in bm.faces:
        c = f.calc_center_median()
        if f.normal.dot(Vector((c.x - HEM["cx"], c.y - HEM["cy"], 0))) < 0:
            out += 1
    if out > len(bm.faces) / 2:
        for f in bm.faces:
            f.normal_flip()
    ob = new_obj("SM_DinoGiantRobe", bm)
    log(f"robe: {len(ob.data.polygons)} faces ({N_THETA} x {N_H}), hem ellipse {HEM}")
    return ob


# The giant's follow spot: the right-hand follow spot on the FOH tower (grounds/infrastructure.py: lens ~(0.95, -31.0,
# 6.35) pre-drop) onto the DJ's head. Tribe floor frame (post-drop) here; the far end rides up with the lift (UV1.x = 1).
SPOT_APEX = Vector((0.95, -31.0, 5.35))
SPOT_HEAD = Vector((0.0, 0.9, 1.6))                                       # the DJ's head on the floor; + Height when up


def build_spot():
    """The giant intro's only light (the user: "no lasers or lights and only a spotlight on me when im tall and when im
    on the ground"): a follow-spot cone from the FOH tower over the crowd onto the DJ, 3 crossed planes on T_DinoBeam's
    white column (u across, v 0 at the lens). UV1.x = 0 at the lens, 1 at the DJ: the lift WPO tilts it up with Height.
    MPC SpotOn fades it in and out. Not built since v7.5: the user wanted the light on them without the visible beam
    ("i dont need the light beam but how i look illuminated looks good"); build_dino's real SpotLight stays."""
    d = SPOT_HEAD - SPOT_APEX
    dn = d.normalized()
    s0 = dn.cross(Vector((0, 0, 1))).normalized()
    bm = bmesh.new()
    uv0 = bm.loops.layers.uv.new("UVMap")
    data = bm.loops.layers.uv.new("LiftData")
    u0, u1 = 0.02 / 8, 0.98 / 8                                         # kit.BEAM_COLS[0] = "white" of 8 columns
    w0, w1 = 0.30, 2.2                                                 # the lens .. a circle around head and shoulders
    end = SPOT_HEAD + dn * 1.2                                          # a little past the head, onto the robe/riser behind
    for k in range(3):
        sk = (Matrix.Rotation(math.pi * k / 3, 3, dn) @ s0).normalized()
        vs = [bm.verts.new(c) for c in (SPOT_APEX - sk * w0 / 2, SPOT_APEX + sk * w0 / 2, end + sk * w1 / 2, end - sk * w1 / 2)]
        f = bm.faces.new(vs)
        for loop, uv, w in zip(f.loops, ((u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)), (0.0, 0.0, 1.0, 1.0)):
            loop[uv0].uv = uv
            loop[data].uv = (w, 0.0)
    ob = new_obj("SM_DinoGiantSpot", bm)
    log(f"spot: lens {tuple(round(c, 2) for c in SPOT_APEX)} -> head {tuple(round(c, 2) for c in SPOT_HEAD)}, {d.length:.1f} m")
    return ob


def export_fbx(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, ob.name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"}, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",
                             mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False)
    log(f"fbx {os.path.basename(path)}")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    obs = [build_lift(), build_glow(), build_robe()]                  # build_spot(): the beam, off since v7.5
    for ob in obs:
        export_fbx(ob)
    with open(os.path.join(OUT, "giant_manifest.txt"), "w") as f:
        f.write("\n".join(ob.name for ob in obs) + "\n")
    log("done")
