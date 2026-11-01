import bpy, math, sys, os
from mathutils import Vector
a=sys.argv[sys.argv.index("--")+1:]; out=a[0]; src=a[1] if len(a)>1 else r"C:\Users\Chris\OneDrive\Desktop\tribe hack\skins\skullbuck.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
ms=[o for o in bpy.data.objects if o.type=='MESH']
bpy.context.view_layer.update()
pts=[o.matrix_world@Vector(c) for o in ms for c in o.bound_box]
lo=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts))); hi=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
print("BBOX",lo,hi)
sc=bpy.context.scene; sc.render.engine='BLENDER_EEVEE_NEXT'; sc.render.resolution_x=700; sc.render.resolution_y=1000
w=bpy.data.worlds.new('w'); sc.world=w; w.use_nodes=True; w.node_tree.nodes['Background'].inputs[1].default_value=1.0
w.node_tree.nodes['Background'].inputs[0].default_value=(0.55,0.55,0.6,1)
L=bpy.data.objects.new('sun',bpy.data.lights.new('sun','SUN')); L.data.energy=3; L.rotation_euler=(0.8,0,0.5); sc.collection.objects.link(L)
cam=bpy.data.objects.new('cam',bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera=cam
def shot(name,tgt,dist,az,el,ortho):
    cam.data.type='ORTHO'; cam.data.ortho_scale=ortho
    d=Vector((math.sin(az)*math.cos(el),-math.cos(az)*math.cos(el),math.sin(el)))
    cam.location=tgt+d*dist; cam.rotation_euler=(tgt-cam.location).to_track_quat('-Z','Y').to_euler()
    sc.render.filepath=os.path.join(out,name); bpy.ops.render.render(write_still=True)
c=(lo+hi)/2; H=hi.z-lo.z
hip=Vector((c.x,c.y,lo.z+H*0.47))
shot('full_front.png',c,10,0,0.05,H*1.1)
shot('full_back.png',c,10,math.pi,0.05,H*1.1)
shot('hips_back.png',hip,10,math.pi,0.05,H*0.45)
shot('hips_side.png',hip,10,math.pi/2,0.05,H*0.45)
shot('hips_back34.png',hip,10,math.pi*0.78,0.15,H*0.45)
shot('legs_front.png',Vector((c.x,c.y,lo.z+H*0.3)),10,0,0.05,H*0.65)
head=Vector((c.x,c.y,hi.z-H*0.13))                     # head + shoulders: how the head sits in the collar
shot('head_front.png',head,10,0,0.05,H*0.32)
shot('head_side.png',head,10,math.pi/2,0.05,H*0.32)
shot('head_front34.png',head,10,math.pi*0.25,0.12,H*0.32)
