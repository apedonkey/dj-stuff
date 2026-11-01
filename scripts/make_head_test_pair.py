# Make the detachable-head TEST PAIR from the current skullbuck:
#   out/headtest/skullbuck.glb       = the skin + 3 leaf bones DH_C / DH_F / DH_U (children of Head) at the skull centre
#   out/headtest/skullbuck_head.glb  = the skull+antlers as a STATIC mesh, origin at that same centre
import sys; sys.path.insert(0, r"C:\Users\Chris\AppData\Local\Temp\claude\sb")
from common import *
from mathutils import Vector
OUT = r"C:\Users\Chris\OneDrive\Desktop\tribe hack\out\headtest"
me, arm = load()
HEADB = {'Head', 'LeftEye', 'RightEye'}
gi = {g.index: g.name for g in me.vertex_groups}
def dom(v):
    if not v.groups: return None
    g = max(v.groups, key=lambda g: g.weight); return gi[g.group]
head_idx = {v.index for v in me.data.vertices if dom(v) in HEADB}
mw = me.matrix_world
pts = [mw @ me.data.vertices[i].co for i in head_idx]
skull = [p for p in pts if p.z < 0.80]                      # antlers excluded from the pivot
lo = Vector((min(p.x for p in skull), min(p.y for p in skull), min(p.z for p in skull)))
hi = Vector((max(p.x for p in skull), max(p.y for p in skull), max(p.z for p in skull)))
C = (lo + hi) / 2
print("HEADVERTS", len(head_idx), "of", len(me.data.vertices), "CENTRE", [round(x, 4) for x in C], "skull z", round(lo.z, 3), round(hi.z, 3))

# --- static copy ---
st = me.copy(); st.data = me.data.copy(); st.name = "Head_Static"; bpy.context.scene.collection.objects.link(st)
st.modifiers.clear(); st.parent = None; st.matrix_world = mw.copy()
for vg in list(st.vertex_groups): st.vertex_groups.remove(vg)
bm = bmesh.new(); bm.from_mesh(st.data); bm.verts.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index not in head_idx], context='VERTS')
for v in bm.verts: v.co = (mw @ v.co) - C                   # world space, pivot at the centre
bm.to_mesh(st.data); bm.free(); st.matrix_world = st.matrix_world.Identity(4)
print("STATIC tris", sum(len(p.vertices) - 2 for p in st.data.polygons))

# --- DH bones on the skin ---
bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones; headb = eb['Head']; inv = arm.matrix_world.inverted()
for name, off in (('DH_C', Vector((0, 0, 0))), ('DH_F', Vector((0, -0.10, 0))), ('DH_U', Vector((0, 0, 0.10)))):
    b = eb.new(name); b.head = inv @ (C + off); b.tail = b.head + Vector((0, 0, 0.02)); b.parent = headb; b.use_connect = False; b.use_deform = False
bpy.ops.object.mode_set(mode='OBJECT')
print("BONES", [b.name for b in arm.data.bones if b.name.startswith('DH_')], "Head@", [round(x, 4) for x in (arm.matrix_world @ arm.data.bones['Head'].head_local)])

bpy.ops.object.select_all(action='DESELECT'); me.select_set(True); arm.select_set(True)
bpy.ops.export_scene.gltf(filepath=OUT + r"\skullbuck.glb", export_format='GLB', use_selection=True, export_animations=False)
bpy.ops.object.select_all(action='DESELECT'); st.select_set(True)
bpy.ops.export_scene.gltf(filepath=OUT + r"\skullbuck_head.glb", export_format='GLB', use_selection=True, export_animations=False)
print("DONE")
