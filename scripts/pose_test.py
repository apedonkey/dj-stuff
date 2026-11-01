import bpy, math, sys, os
a=sys.argv[sys.argv.index("--")+1:]; out=a[0]; src=a[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
arm=[o for o in bpy.data.objects if o.type=='ARMATURE'][0]
pb=arm.pose.bones
def rot(b,x=0,y=0,z=0):
    pb[b].rotation_mode='XYZ'; pb[b].rotation_euler=(math.radians(x),math.radians(y),math.radians(z))
# figure out which local axis swings the thigh forward by trying and measuring knee position
import mathutils
bpy.context.view_layer.update()
def knee(): return (arm.matrix_world@pb['LeftLeg'].head)
k0=knee(); best=None
for ax in range(3):
    for s in (1,-1):
        v=[0,0,0]; v[ax]=50*s; rot('LeftUpLeg',*v); bpy.context.view_layer.update(); k=knee()
        if best is None or k.y<best[0]: best=(k.y,ax,s)
rot('LeftUpLeg')
_,ax,s=best; print("FWD axis",ax,s)
v=[0,0,0]; v[ax]=60*s; rot('LeftUpLeg',*v)
v=[0,0,0]; v[ax]=-70*s; rot('LeftLeg',*v)
v=[0,0,0]; v[ax]=-25*s; rot('RightUpLeg',*v)
bpy.context.view_layer.update()
sc=bpy.context.scene; sc.render.engine='BLENDER_EEVEE_NEXT'; sc.render.resolution_x=800; sc.render.resolution_y=900
w=bpy.data.worlds.new('w'); sc.world=w; w.use_nodes=True; w.node_tree.nodes['Background'].inputs[0].default_value=(0.55,0.55,0.6,1)
L=bpy.data.objects.new('sun',bpy.data.lights.new('sun','SUN')); L.data.energy=3; L.rotation_euler=(0.8,0,0.5); sc.collection.objects.link(L)
cam=bpy.data.objects.new('cam',bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera=cam
from mathutils import Vector
def shot(name,az,el):
    cam.data.type='ORTHO'; cam.data.ortho_scale=1.25; t=Vector((0,0,-0.3))
    d=Vector((math.sin(az)*math.cos(el),-math.cos(az)*math.cos(el),math.sin(el)))
    cam.location=t+d*8; cam.rotation_euler=(t-cam.location).to_track_quat('-Z','Y').to_euler()
    sc.render.filepath=os.path.join(out,name); bpy.ops.render.render(write_still=True)
shot('pose_side.png',math.pi/2,0.1); shot('pose_back34.png',math.pi*0.8,0.15); shot('pose_front34.png',-0.5,0.1)
