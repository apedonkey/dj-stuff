"""Dump the UV layers of an exported FBX as Blender reads it back: names in order, min/max per channel, and the
LaserFix kind split (beam 0 / aperture 1). Usage: blender -b --factory-startup --python fbx_uvs.py -- <file.fbx>"""
import sys

import bpy
import numpy as np

path = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=path)
for ob in bpy.context.scene.objects:
    if ob.type != "MESH":
        continue
    me = ob.data
    print(f"[UV] {ob.name}: {len(me.vertices)} verts, {len(me.loops)} loops, {len(me.uv_layers)} UV layers")
    for i, uv in enumerate(me.uv_layers):
        a = np.empty(len(me.loops) * 2)
        uv.data.foreach_get("uv", a)
        a = a.reshape(-1, 2)
        print(f"[UV]   {i} {uv.name:18s} u {a[:, 0].min():9.3f} .. {a[:, 0].max():9.3f}   "
              f"v {a[:, 1].min():9.3f} .. {a[:, 1].max():9.3f}")
        if uv.name == "LaserFix":
            k = a[:, 1]
            print(f"[UV]   LaserFix kind: {(k < 0.5).sum()} beam loops, {(k > 0.5).sum()} aperture loops; "
                  f"distinct kinds {np.unique(np.round(k, 3))[:8]}")
