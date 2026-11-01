import bpy, bmesh
from mathutils import Vector
SRC=r"C:\Users\Chris\OneDrive\Desktop\tribe hack\skins\skullbuck.glb"
def load():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)
    me=max([o for o in bpy.data.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices))
    arm=[o for o in bpy.data.objects if o.type=='ARMATURE'][0]
    return me,arm
def parts_of(bm):
    bm.verts.ensure_lookup_table(); seen=set(); parts=[]
    for v in bm.verts:
        if v.index in seen: continue
        st=[v]; comp=[]; seen.add(v.index)
        while st:
            a=st.pop(); comp.append(a.index)
            for e in a.link_edges:
                b=e.other_vert(a)
                if b.index not in seen: seen.add(b.index); st.append(b)
        parts.append(comp)
    return parts
def sampler(img):
    W,H=img.size; px=img.pixels[:]
    def col(uv):
        x=min(W-1,int(uv.x%1*W)); y=min(H-1,int(uv.y%1*H)); i=(y*W+x)*4; return px[i:i+3]
    return col
