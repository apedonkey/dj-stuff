"""The giant T. rex skull that crowns the Dino Stage arch (Blender 4.5, headless). Our own design: a monumental skull
roaring at the crowd - upper skull raised, jaw dropped wide - with banana teeth, deep brow-shaded eye sockets looking
forward and down past a narrow snout, bull-like brow horns, cheek horns, open temporal windows and a crest of spikes on
its broad back; each spine end
continues as a short spiked vertebral column into its neck. Its eyes and an ember in the throat are a separate glow
mesh (red, unlit, like SM_DinoEyes).

    from skull import build_skull_v2
    skull_bm, eyes_bm = build_skull_v2()     # world meters, pre-drop (modeled on the stage's z=0 like the structure)

Placement: the head sits in front of the k=6 horns (where the arch leaves room for its broad back; they rise just
clear of its back corners), the neck runs back to the spine ends (+-2.2, 9.0, 17.1), the snout reaches out over the DJ.
The chin stays above z 12.5 so the 16 x 9 m visual screen (x -8..8, z 2.7..11.7 at y 10.3) stays clear from the
crowd, the stream drone and the DJ; size and the brow horns are set so no horn laser of grounds/atmosphere.py touches
the skull over its whole sweep (re-check with skull_check.py). Bone = metaballs (smooth blends, real sockets and
openings) decimated to BONE_TRIS; teeth and horns are tubes. Deterministic (no randomness); temporary Blender data is
removed. Skull space: origin at the condyle, world axes, snout toward -Y.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

CONDYLE = Vector((0.0, 5.6, 16.9))      # world (pre-drop): the back-bottom of the skull, where the neck joins
PITCH = 10.0                             # degrees: the upper skull lifts its snout (roaring)
JAW_OPEN = 34.0                          # degrees: the jaw drops about the hinge, relative to the upper skull
HINGE = Vector((0.0, -1.6, 0.0))         # jaw joint, skull space
SCALE = 0.8                              # uniform size of the head about the condyle (the neck stays put); 0.8 is
                                         # the largest that clears every horn-laser sweep and keeps the chin > 12.5
SPINE_END_Z = 17.1                       # the two spine ends the neck reaches back to (dino_stage spine_point(+-1, 1))
BONE_TRIS = 9000                         # decimation target for the metaball bone
MB_RES = 0.2                             # metaball polygonization step (m)

W = Matrix()                                                                           # world (the neck)


def frames():
    """(U, J): upper skull -> world, lower jaw -> world (from the module's current parameters)."""
    u = Matrix.Translation(CONDYLE) @ Matrix.Rotation(math.radians(-PITCH), 4, "X") @ Matrix.Scale(SCALE, 4)
    return u, u @ Matrix.Translation(HINGE) @ Matrix.Rotation(math.radians(JAW_OPEN), 4, "X") @ Matrix.Translation(-HINGE)


ISO = 0.575            # metaball (stiffness 2, threshold 0.6): an isolated element's surface sits at 0.575 x its size
CHAIN = 0.65           # a chain of balls spaced 0.7 rho with radius rho / 0.65 is a tube of radius rho (measured)


# ------------------------------------------------------------------ metaball sculpting
class Blob:
    """Metaball elements in world space; sizes are surface sizes. Negative elements carve sockets and openings."""

    def __init__(self):
        self.els = []

    def ell(self, M, co, half, rot=None, neg=False):
        q = M.to_3x3().normalized().to_quaternion() @ (rot if rot is not None else Quaternion())
        sc = M.to_scale().x
        self.els.append(("ELLIPSOID", M @ Vector(co), 1.0, [h * sc / ISO for h in half], q, neg))

    def ball(self, M, co, r, neg=False):
        self.els.append(("BALL", M @ Vector(co), r * M.to_scale().x / ISO, None, None, neg))

    def chain(self, M, ctrl, r0, r1):
        """A smooth tube of balls through the control points, radius r0 -> r1."""
        pts = spline([Vector(c) for c in ctrl])
        cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            cum.append(cum[-1] + (b - a).length)
        total, s, k = cum[-1], 0.0, 0
        while True:
            u = min(s / total, 1.0)
            while k < len(pts) - 2 and cum[k + 1] < s:
                k += 1
            seg = cum[k + 1] - cum[k]
            p = pts[k].lerp(pts[k + 1], 0.0 if seg < 1e-9 else min(1.0, (s - cum[k]) / seg))
            r = r0 + (r1 - r0) * u
            self.els.append(("BALL", M @ p, r * M.to_scale().x / CHAIN, None, None, False))
            if s >= total:
                break
            s = min(total, s + 0.7 * r)

    def mesh(self, name, res, target):
        """Polygonize, decimate to about `target` tris; a smooth-shaded bmesh (temporary objects and data removed)."""
        sc = bpy.context.scene
        mb = bpy.data.metaballs.new(name)
        mb.resolution = mb.render_resolution = res
        mb.threshold = 0.6
        ob = bpy.data.objects.new(name, mb)
        sc.collection.objects.link(ob)
        for kind, co, rad, size, rot, neg in self.els:
            e = mb.elements.new(type=kind)
            e.co, e.radius, e.use_negative = co, rad, neg
            e.stiffness = 3.0 if neg else 2.0
            if size:
                e.size_x, e.size_y, e.size_z = size
            if rot is not None:
                e.rotation = rot
        bpy.context.view_layer.update()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.metaballs.remove(mb)
        n = sum(len(p.vertices) - 2 for p in me.polygons)
        if n > target:
            tmp = bpy.data.objects.new(name + "Dec", me)
            sc.collection.objects.link(tmp)
            tmp.modifiers.new("Dec", "DECIMATE").ratio = target / n
            bpy.context.view_layer.update()
            me2 = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
            bpy.data.objects.remove(tmp, do_unlink=True)
            bpy.data.meshes.remove(me)
            me = me2
        bm = bmesh.new()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        for f in bm.faces:
            f.smooth = True
        return bm


def spline(P, per=12):
    """Catmull-Rom curve through the points."""
    P = [2 * P[0] - P[1]] + P + [2 * P[-1] - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1:i + 3]
        for k in range(per):
            t = k / per
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2].copy())
    return out


def along(d):
    """Rotation turning +Y onto direction d (for ellipsoids laid along a path)."""
    return Vector((0.0, 1.0, 0.0)).rotation_difference(Vector(d).normalized())


# ------------------------------------------------------------------ tubes: teeth and horns
def bent_path(base, direction, length, bend_axis, bend_deg, steps):
    pts, d, pos = [], Vector(direction).normalized(), Vector(base)
    rot = Matrix.Rotation(math.radians(bend_deg) / steps, 3, Vector(bend_axis).normalized())
    for _ in range(steps + 1):
        pts.append(pos.copy())
        pos = pos + d * (length / steps)
        d = (rot @ d).normalized()
    return pts


def spike(bm, M, base, direction, length, r0, bend_axis, bend_deg, segs=6, steps=5, sink=0.4):
    """A curved, tapering horn or tooth with a sharp tip, transformed by M. It starts `sink` x r0 inside its base so it
    grows out of the bone. Faces are built in a fixed order (deterministic)."""
    d0 = Vector(direction).normalized()
    r0 *= M.to_scale().x
    pts = [M @ p for p in bent_path(Vector(base) - d0 * (sink * r0), d0, length + sink * r0, bend_axis, bend_deg, steps)]
    n = len(pts)
    tans = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]
    ref = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
    nrm = tans[0].cross(ref).normalized()
    rings = []
    for i in range(n - 1):                                         # the last point is the tip
        if i > 0:
            ax = tans[i - 1].cross(tans[i])
            if ax.length > 1e-7:
                nrm = (Matrix.Rotation(tans[i - 1].angle(tans[i]), 3, ax.normalized()) @ nrm).normalized()
        bin_ = tans[i].cross(nrm).normalized()
        r = r0 * (1.0 - i / (n - 1)) ** 0.75
        rings.append([bm.verts.new(pts[i] + (nrm * math.cos(2 * math.pi * j / segs)
                                              + bin_ * math.sin(2 * math.pi * j / segs)) * r) for j in range(segs)])
    tip = bm.verts.new(pts[-1])
    faces = [bm.faces.new(list(reversed(rings[0])))]
    for a, b in zip(rings, rings[1:]):
        for j in range(segs):
            faces.append(bm.faces.new((a[j], a[(j + 1) % segs], b[(j + 1) % segs], b[j])))
    for j in range(segs):
        faces.append(bm.faces.new((rings[-1][j], rings[-1][(j + 1) % segs], tip)))
    for f in faces:
        f.smooth = True
    return faces


def ellipsoid(bm, M, center, half, rot=None, segs=12, rings=8):
    """A UV ellipsoid built in a fixed order (deterministic), transformed by M @ T(center) @ rot @ scale(half)."""
    m = M @ Matrix.Translation(center) @ (rot.to_matrix().to_4x4() if rot is not None else Matrix()) \
        @ Matrix.Diagonal(Vector((*half, 1.0)))
    top = bm.verts.new(m @ Vector((0, 0, 1)))
    ring = [[bm.verts.new(m @ Vector((math.sin(math.pi * i / rings) * math.cos(2 * math.pi * j / segs),
                                      math.sin(math.pi * i / rings) * math.sin(2 * math.pi * j / segs),
                                      math.cos(math.pi * i / rings)))) for j in range(segs)] for i in range(1, rings)]
    bot = bm.verts.new(m @ Vector((0, 0, -1)))
    faces = []
    for j in range(segs):
        k = (j + 1) % segs
        faces.append(bm.faces.new((top, ring[0][j], ring[0][k])))
        for a, b in zip(ring, ring[1:]):
            faces.append(bm.faces.new((a[j], b[j], b[k], a[k])))
        faces.append(bm.faces.new((bot, ring[-1][k], ring[-1][j])))
    return faces


def merge(dst, src):
    vmap = {v: dst.verts.new(v.co) for v in src.verts}
    for f in src.faces:
        try:
            dst.faces.new([vmap[v] for v in f.verts]).smooth = f.smooth
        except ValueError:
            pass
    src.free()


# ------------------------------------------------------------------ the design (skull space, snout toward -Y)
def upper_skull(b):
    M = frames()[0]
    b.ell(M, (0, -0.4, 3.0), (3.1, 0.95, 2.8))                       # nuchal wall: the broad back
    b.ell(M, (0, 0.35, 0.35), (1.35, 0.85, 0.95))                    # condyle, onto the neck
    b.ell(M, (0, -2.7, 3.3), (2.75, 2.2, 2.6))                       # braincase
    b.ell(M, (0, -3.6, 5.5), (2.6, 2.4, 1.15))                       # flat skull roof
    b.chain(M, [(0, -0.6, 6.4), (0, -2.6, 6.7), (0, -4.6, 6.25)], 0.5, 0.42)   # sagittal crest between the windows
    for s in (-1, 1):
        b.ell(M, (s * 3.1, -2.2, 3.4), (0.8, 0.8, 1.8))              # squamosal flare: the back corners (clear of
        b.ell(M, (s * 3.35, -1.9, 1.6), (0.4, 0.5, 0.9))             # the arch's k=6 horns); paroccipital wing
        b.ell(M, (s * 1.7, -2.4, 6.2), (1.1, 1.45, 1.35), neg=True)  # supratemporal window (top)
        b.ell(M, (s * 3.75, -3.1, 2.9), (0.95, 1.25, 1.45), neg=True)    # lateral temporal window
        b.chain(M, [(s * 3.05, -1.8, 0.5), (s * 3.95, -3.5, 0.85), (s * 3.85, -5.4, 1.25), (s * 3.0, -7.3, 1.6)],
                0.8, 0.7)                                            # jugal: the cheek bar under the eye
        b.ell(M, (s * 4.3, -4.7, 0.95), (0.95, 1.05, 0.85))          # jugal boss (cheek horn base)
        b.chain(M, [(s * 3.85, -4.9, 1.35), (s * 3.5, -5.3, 3.3), (s * 3.0, -5.6, 5.2)], 0.6, 0.55)   # postorbital
        b.ell(M, (s * 3.15, -6.85, 3.8), (1.05, 1.05, 1.1), neg=True)  # orbit: carved into the face, looking forward
        b.ell(M, (s * 2.6, -7.0, 5.45), (1.1, 0.95, 0.6))            # heavy brow over the eye
        b.ell(M, (s * 2.1, -8.95, 3.0), (0.55, 1.2, 0.85), neg=True)  # antorbital window
        b.ell(M, (s * 0.75, -11.9, 2.35), (0.48, 0.6, 0.6), neg=True)  # nostril
        b.chain(M, [(s * 2.9, -4.9, 0.5), (s * 2.35, -8.1, 0.5), (s * 1.6, -11.1, 0.65)], 0.48, 0.42)   # tooth row
    for co, half in (((0, -6.9, 3.6), (2.45, 1.5, 2.6)), ((0, -8.5, 3.0), (2.15, 1.35, 2.2)),
                     ((0, -10.0, 2.35), (1.8, 1.2, 1.7)), ((0, -11.2, 1.85), (1.55, 0.9, 1.22)),
                     ((0, -11.95, 1.65), (1.3, 0.55, 0.95))):         # snout: narrow in front (a T. rex's), so the
        b.ell(M, co, half)                                           # forward-set eyes see past it
    for co in ((0, -7.1, 5.5), (0, -8.4, 4.6), (0, -9.7, 3.55), (0, -10.85, 2.7)):    # rugose nasal ridge
        b.ball(M, co, 0.4)
    b.ell(M, (0, -2.7, 0.2), (2.0, 1.8, 1.0), neg=True)             # throat: the back of the mouth
    b.ell(M, (0, -7.6, 0.0), (1.55, 3.6, 0.85), neg=True)            # vaulted palate between the tooth rows (shade)


def lower_jaw(b):
    M = frames()[1]
    for s in (-1, 1):
        pts = spline([Vector((s * 3.5, -1.4, -0.05)), Vector((s * 3.25, -4.6, -0.5)), Vector((s * 2.45, -8.0, -0.85)),
                      Vector((s * 1.6, -10.9, -1.0))], per=8)
        for i, p in enumerate(pts):                                  # tall, thin mandible: dense overlapping ellipsoids
            u = i / (len(pts) - 1)
            d = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
            b.ell(M, p, (0.45, 0.7, 1.05 - 0.4 * u), rot=along(d))
        b.ell(M, (s * 3.4, -3.0, 0.55), (0.55, 1.3, 0.8))             # surangular hump behind the teeth
        b.ell(M, (s * 3.7, -3.6, -0.3), (0.65, 1.1, 0.45), neg=True)  # mandibular opening
    b.ell(M, (0, -11.1, -1.0), (1.55, 0.6, 0.75))                    # chin: the rami meet


def neck_vertebrae():
    """(center, column direction, size) of the neck: each spine end continues as a short vertebral column, and the two
    columns converge on the atlas behind the condyle (world coordinates)."""
    atlas = Vector((0.0, 6.35, CONDYLE.z + 0.3))
    out = []
    for s in (-1, 1):
        a = Vector((s * 2.2, 9.0, SPINE_END_Z))
        for k, t in enumerate((0.02, 0.33, 0.64)):
            out.append((a.lerp(atlas, t), atlas - a, 1.0 - 0.08 * k))
    out.append((atlas, Vector((0.0, -1.0, 0.0)), 1.3))
    return out


def neck(b):
    for c, d, r in neck_vertebrae():
        b.ell(W, c, (r, 0.5, 0.95 * r), rot=along(d))                # disc-like vertebrae: thin along the column


def teeth(bm):
    U, J = frames()
    up_rows = [(-5.1, 2.95, 1.2), (-6.0, 2.85, 1.55), (-6.9, 2.7, 1.85), (-7.8, 2.5, 2.1), (-8.7, 2.3, 2.1),
               (-9.6, 2.08, 1.9), (-10.45, 1.86, 1.6), (-11.15, 1.65, 1.35)]          # (y, |x|, length)
    for s in (-1, 1):
        for i, (y, x, ln) in enumerate(up_rows):
            ln *= (0.82 if (i + (s > 0)) % 4 == 3 else 1.0)            # a few chipped ones
            spike(bm, U, (s * x, y, 0.3), (s * 0.05, 0.1, -1.0), ln, 0.36 + 0.05 * ln,
                  (1, 0, 0), 22, segs=6, steps=5)                    # hang down, curve back (toward the throat)
        for k, x in enumerate((0.5, 1.1)):                           # premaxillary teeth at the snout tip
            spike(bm, U, (s * x, -11.85 + 0.3 * k, 0.55), (s * 0.08, -0.25, -1.0), 1.15, 0.32,
                  (1, 0, 0), 12, segs=6, steps=4)
    lo_rows = [(-5.6, 2.85, 1.05), (-6.5, 2.68, 1.3), (-7.4, 2.45, 1.5), (-8.3, 2.25, 1.55), (-9.2, 2.02, 1.45),
               (-10.0, 1.82, 1.25), (-10.7, 1.62, 1.05)]
    for s in (-1, 1):
        for i, (y, x, ln) in enumerate(lo_rows):
            z = -0.05 - 0.3 * i / (len(lo_rows) - 1)                 # the jaw's top edge drops toward the chin
            spike(bm, J, (s * x, y, z), (s * 0.1, 0.12, 1.0), ln, 0.32 + 0.05 * ln, (1, 0, 0), -20,
                  segs=6, steps=5)                                   # point up, curve back


def horns(bm):
    U = frames()[0]
    for s in (-1, 1):
        spike(bm, U, (s * 4.6, -4.7, 0.95), (s * 0.9, -0.35, -0.25), 3.0, 0.75, (0, 1, 0), s * 30,
              segs=8, steps=7)                                       # cheek horns: out and down
        spike(bm, U, (s * 3.0, -6.3, 5.3), (s * 0.95, 0.25, 0.08), 3.8, 0.72, (0, 1, 0), -s * 60,
              segs=8, steps=8)                                       # brow horns: out over the eyes, curling up
                                                                     # (bull-like; tips under the horn lasers)
    for x in (-2.6, -1.3, 0.0, 1.3, 2.6):                            # spikes along the nuchal crest
        spike(bm, U, (x, -0.2, 5.7 - 0.25 * abs(x)), (x * 0.25, 0.75, 0.65), 1.7 - 0.12 * abs(x), 0.4,
              (1, 0, 0), 12, segs=6, steps=5)
    for c, d, r in neck_vertebrae():                                 # neural spines on the neck vertebrae
        spike(bm, W, c + Vector((0, 0, 0.85 * r)), (0, 0.4, 0.92), 1.2 + 0.5 * r, 0.32 * r, (1, 0, 0), 10,
              segs=6, steps=4)


def glow_parts(eyes):
    U = frames()[0]
    for s in (-1, 1):
        n = Vector((s * 0.45, -0.78, -0.42)).normalized()            # look forward, out and down at the audience
        horiz = n.cross(Vector((0, 0, 1))).normalized()
        vert = horiz.cross(n).normalized()
        slant = math.radians(18) * s                                 # angry: the outer end tilts up
        long_ = (horiz * math.cos(slant) + vert * math.sin(slant)).normalized()
        short = long_.cross(n).normalized()
        rot = Matrix((long_, short, n)).transposed().to_quaternion()
        ellipsoid(eyes, U, Vector((s * 2.95, -6.85, 3.65)), (0.82, 0.52, 0.32), rot=rot, segs=12, rings=6)
    ellipsoid(eyes, U, Vector((0, -1.75, 0.35)), (0.75, 0.25, 0.45), segs=12, rings=6)   # an ember deep in the throat


# Recommended bake lights for the skull, in dino_stage.add_light()'s argument order (name, kind, pos, target, color,
# power, size, spot_deg; pre-drop world, dropped with the other lights): use them in place of SkullKey. SkullKey sits
# low in front and floods the open mouth while the face stays dark; a key from above the front rows lights the brow,
# snout, horns and tooth fronts and leaves the palate (facing down) in shadow, so the maw reads as a dark cavity.
SKULL_LIGHTS = (
    ("SkullTop", "SPOT", (0.0, -14.0, 32.0), (0.0, 1.5, 20.5), (1.0, 0.66, 0.36), 60000, 1.0, 45),
    ("SkullUnder", "SPOT", (0.0, -6.0, 8.0), (0.0, 1.0, 15.5), (1.0, 0.5, 0.25), 8000, 1.0, 40),    # warm under-jaw
    ("SkullRimL", "SPOT", (-12.0, 10.0, 28.0), (0.0, 2.0, 20.0), (0.4, 0.5, 1.0), 25000, 1.0, 35),  # cool rims
    ("SkullRimR", "SPOT", (12.0, 10.0, 28.0), (0.0, 2.0, 20.0), (0.4, 0.5, 1.0), 25000, 1.0, 35),
)


def ports():
    """Laser / smoke port positions (world, pre-drop) for the light designers; nothing is built for them."""
    U = frames()[0]
    return {"mouth": U @ Vector((0, -2.9, 0.3)),
            "eye_L": U @ Vector((-2.95, -6.85, 3.65)), "eye_R": U @ Vector((2.95, -6.85, 3.65)),
            "nostril_L": U @ Vector((-0.85, -12.3, 2.4)), "nostril_R": U @ Vector((0.85, -12.3, 2.4))}


def build_skull_v2():
    """(skull_bm, eyes_bm): the bone (metaballs + teeth + horns, smooth-shaded) and the red glow (eyes + throat)."""
    b = Blob()
    upper_skull(b)
    lower_jaw(b)
    neck(b)
    skull = b.mesh("SkullV2MB", MB_RES, BONE_TRIS)
    extra = bmesh.new()
    teeth(extra)
    horns(extra)
    merge(skull, extra)
    eyes = bmesh.new()
    glow_parts(eyes)
    return skull, eyes
