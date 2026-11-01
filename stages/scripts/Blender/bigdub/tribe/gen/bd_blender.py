"""bd_blender.py: BIG DUB's meshes (build/bigdub/meshes/*.npz, bd_site.py) to FBX files (build/bigdub/fbx/) for
Unreal, with the gear's FBX conventions (art/gear/scripts/gear_blender.py): the scene in centimetres (unit scale 0.01),
exported with Blender's own axes (forward Y, up Z), so Unreal's importer applies only its Y flip; every mesh is written
in Blender's frame with y -> -y and each triangle's corners reversed (gear_blender.to_blender), so Unreal shows exactly
the coordinates bd_site.py authored. UVs are written with v flipped (Unreal's importer flips it back). Vertex colours go
as FLOAT_COLOR attributes exported "LINEAR": the FBX holds the values bd_site.py wrote, Unreal stores 255 x value.
The extra UV sets (bd_mesh.AUX_UVS, the materials' per-vertex data) follow the first as UVChannel_2.., so they arrive
as UV channels 1.. in Unreal; their v is flipped like the first's and comes back as written.

One FBX per mesh and LOD: <name>.fbx (LOD 0), <name>_LOD1.fbx, <name>_LOD2.fbx.

    "D:/Tools/blender-4.5.14-windows-x64/blender.exe" -b --factory-startup --python D:/VRDJ/tools/bigdub/bd_blender.py
"""
import glob
import os
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
# TRIBE copy (2026-11-01): the Tribe stage's own folders (tribe/out/gen/meshes -> tribe/out/gen/fbx)
ROOT = os.path.normpath(os.path.join(HERE, "..", "out", "gen"))
MESHES = os.environ.get("BIGDUB_MESHES", os.path.join(ROOT, "meshes"))
FBX = os.environ.get("BIGDUB_FBX", os.path.join(ROOT, "fbx"))

FBX_EXPORT = dict(use_selection=True, object_types={"MESH"}, use_mesh_modifiers=False, mesh_smooth_type="FACE",
                  use_triangles=True, use_tspace=False, colors_type="LINEAR", prioritize_active_color=False,
                  apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0,
                  axis_forward="Y", axis_up="Z", bake_space_transform=False, add_leaf_bones=False,
                  bake_anim=False, path_mode="STRIP", embed_textures=False, use_custom_props=False,
                  use_metadata=True)


def reset_scene_cm():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 0.01
    sc.unit_settings.length_unit = "CENTIMETERS"
    return sc


def material(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    return m


def make_object(name, V, F, C, UV, Mi, materials, X=None):
    V = np.asarray(V, np.float64).copy()
    V[:, 1] = -V[:, 1]
    F = np.asarray(F, np.int64)[:, ::-1].copy()
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V))
    me.vertices.foreach_set("co", V.astype(np.float32).ravel())
    nf = len(F)
    me.loops.add(nf * 3)
    me.loops.foreach_set("vertex_index", F.astype(np.int32).ravel())
    me.polygons.add(nf)
    me.polygons.foreach_set("loop_start", (np.arange(nf) * 3).astype(np.int32))
    me.polygons.foreach_set("loop_total", np.full(nf, 3, np.int32))
    me.polygons.foreach_set("material_index", np.asarray(Mi, np.int32))
    # Unreal's FBX importer orders UV sets named UVChannel_<n> by n (others keep their order): named so, explicitly
    sets = [("UVChannel_1", UV)] + ([(f"UVChannel_{k + 2}", X[k]) for k in range(len(X))] if X is not None else [])
    for layer_name, data in sets:
        uvl = me.uv_layers.new(name=layer_name)
        uv = np.asarray(data, np.float32)[F.ravel()]
        uv[:, 1] = 1.0 - uv[:, 1]
        uvl.data.foreach_set("uv", uv.ravel())
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    ca.data.foreach_set("color", np.asarray(C, np.float32).ravel())
    me.color_attributes.active_color = ca
    for mname in materials:
        me.materials.append(material(mname))
    # No validate(): it deletes a face that repeats another's corners in the other winding, which is how the
    # generator makes double-sided bulbs, skirts and gables. The generator's indices are checked in numpy instead.
    if len(F) and (F.min() < 0 or F.max() >= len(V)):
        raise ValueError(f"{name}: a face index is out of range")
    me.update(calc_edges=True)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def export(ob, path):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=path, **FBX_EXPORT)


def main():
    t0 = time.time()
    os.makedirs(FBX, exist_ok=True)
    only = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    files = sorted(glob.glob(os.path.join(MESHES, "*.npz")))
    n = 0
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        if only and name not in only:
            continue
        d = np.load(f, allow_pickle=False)
        mats = [str(m) for m in d["materials"]]
        lods = [("", "")] + [(str(k), f"_LOD{k}") for k in range(1, 4) if f"V{k}" in d]
        for key, suffix in lods:
            reset_scene_cm()
            X = d["X" + key] if ("X" + key) in d else None
            ob = make_object(name, d["V" + key], d["F" + key], d["C" + key], d["UV" + key], d["M" + key], mats, X)
            out = os.path.join(FBX, name + suffix + ".fbx")
            export(ob, out)
            n += 1
            print(f"[bigdub] {name}{suffix}: {len(d['F' + key])} triangles, {len(mats)} slots -> {out}", flush=True)
    print(f"[bigdub] done: {n} FBX in {time.time() - t0:.1f} s", flush=True)


try:
    main()
except Exception as e:  # noqa: BLE001 - the log must say so and Blender must exit non-zero
    import traceback
    traceback.print_exc()
    print(f"[bigdub] FAILED: {e!r}", flush=True)
    sys.exit(1)
