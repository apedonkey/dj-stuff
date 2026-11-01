# REACTOR: export only the sweeping lasers (SM_ClubLaserShow.fbx from club_lasers.py) into CLUB_OUT, with club_stage.py's
# scene and FBX settings. The lasers are never in the bakes (club_stage.py hides them from the render), so a laser-only
# change can reuse a full bake's output as it is: copy it, replace this one file, build from the copy (v8, 2026-10-11).
#   CLUB_OUT=<copy of a club_stage.py output> D:\Tools\blender-4.5.14-windows-x64\blender.exe -b --factory-startup \
#       --python export_lasers.py
# No render, no bake: no GPU lock needed.
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "grounds"))
import kit as gkit  # noqa: E402  (the beam texture's columns and the quad helper; read-only use)
sys.path.insert(0, HERE)
import club_lasers  # noqa: E402

OUT = os.environ.get("CLUB_OUT")
if not OUT or not os.path.exists(os.path.join(OUT, "manifest.txt")):
    raise SystemExit("CLUB_OUT must be a copy of a club_stage.py output (it has manifest.txt)")
if "SM_ClubLaserShow" not in open(os.path.join(OUT, "manifest.txt")).read().split():
    raise SystemExit("that output has no SM_ClubLaserShow in its manifest")

bpy.ops.wm.read_factory_settings(use_empty=True)                 # as club_stage.py
coll = bpy.context.scene.collection
me = bpy.data.meshes.new("SM_ClubLaserShow")
bm = club_lasers.build_mesh(gkit)
bm.to_mesh(me)
bm.free()
ob = bpy.data.objects.new("SM_ClubLaserShow", me)
coll.objects.link(ob)
me.materials.append(bpy.data.materials.new("ASM_ClubLaserShow"))   # club_stage.py's slot name (the import ignores it)
bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
path = os.path.join(OUT, "SM_ClubLaserShow.fbx")
bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"}, apply_unit_scale=True,   # club_stage.py's
                         apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",          # export_fbx()
                         mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False)
print("[CLUB] " + club_lasers.report()[1], flush=True)
print(f"[CLUB] fbx {path}: {len(me.polygons)} faces, {sum(len(p.vertices) - 2 for p in me.polygons)} tris, "
      f"uv layers {[u.name for u in me.uv_layers]}", flush=True)
print("[CLUB] done", flush=True)
