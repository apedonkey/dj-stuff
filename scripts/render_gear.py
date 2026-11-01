"""Render previews of Tribe's DJ gear from scripts/mesh_export's glTF + PNG output.

    blender -b --factory-startup --python scripts/render_gear.py -- <export root> <out dir> [mesh name ...] [--sheet-only]

<export root> holds TribeXR/Content/...; every SK_*.glb in Equipment/Models/SkeletalMeshes is a piece of gear (or only
the named ones). Each mesh's material is rebuilt from the material JSON mesh_export wrote next to its textures: the
base colour is the "off" texture (TextureA, else the first colour-like texture), roughness from the material's
scalars. Writes <name>_top.png (orthographic, from above) and <name>_34.png (three-quarter, from the front-left) per
mesh, and gear_contact_sheet.png with every 3/4 view. Eevee; run it under the GPU lock (gpu_lock.sh).
"""
import glob
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ROOT, OUT = argv[0], argv[1]
SHEET_ONLY = "--sheet-only" in argv      # re-compose the contact sheet from existing renders (no GPU, no lock)
ONLY = set(a for a in argv[2:] if not a.startswith("--"))
os.makedirs(OUT, exist_ok=True)
EQ = os.path.join(ROOT, "TribeXR", "Content", "Equipment")
MESHES = sorted(glob.glob(os.path.join(EQ, "Models", "SkeletalMeshes", "SK_*.glb")))
JSONS = {os.path.splitext(os.path.basename(p))[0]: p for p in glob.glob(os.path.join(ROOT, "**", "MI_*.json"), recursive=True)}
JSONS.update({os.path.splitext(os.path.basename(p))[0]: p for p in glob.glob(os.path.join(ROOT, "**", "M_*.json"), recursive=True)})
PREFER = ("TextureA", "Diffuse", "BaseColor", "Base Color", "Albedo", "Color", "Texture")


def png_for(ref):
    """'TribeXR/Content/.../T_X.T_X' -> the exported PNG"""
    p = os.path.join(ROOT, ref.split(".")[0] + ".png")
    return p if os.path.exists(p) else None


def build_material(mat):
    js = JSONS.get(mat.name.split(".")[0])
    if not js:
        return False
    d = json.load(open(js, encoding="utf-8"))
    tex = d.get("Textures", {})
    pick = next((tex[k] for k in PREFER if k in tex), None)
    if not pick:
        pick = next((v for k, v in tex.items() if not any(w in k for w in ("Segment", "Weight", "Normal", "Mask", "Palette", "Rough"))), None)
    img = png_for(pick) if pick else None
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None) or nt.nodes.new("ShaderNodeBsdfPrincipled")
    rough = d.get("Parameters", {}).get("Scalars", {}).get("BaseRoughness")
    if rough is not None:
        bsdf.inputs["Roughness"].default_value = float(rough)
    if img:
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = bpy.data.images.load(img, check_existing=True)
        nt.links.new(tn.outputs["Color"], bsdf.inputs["Base Color"])
    return bool(img)


def setup_world():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys() else "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = 1200, 900
    sc.render.film_transparent = False
    w = bpy.data.worlds.new("w")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.32, 0.33, 0.36, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.6
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 4.5
    sun.rotation_euler = (math.radians(40), math.radians(15), math.radians(30))
    sc.collection.objects.link(sun)


def bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def shoot(name, center, size, ortho, loc, out):
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    d = center - loc
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = size * 1.15
    else:
        cam.data.lens = 50
    cam.data.clip_start, cam.data.clip_end = 0.001, 100
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)


done = [os.path.splitext(os.path.basename(p))[0] for p in MESHES] if SHEET_ONLY else []
for path in ([] if SHEET_ONLY else MESHES):
    name = os.path.splitext(os.path.basename(path))[0]
    if ONLY and name not in ONLY:
        continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_world()
    bpy.ops.import_scene.gltf(filepath=path)
    # the gear only: the glTF importer also adds a hidden 2 m icosphere for bone display, which must not drive framing
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.data.materials and not o.hide_render and o.visible_get()]
    textured = sum(build_material(m) for o in meshes for m in o.data.materials if m)
    lo, hi = bbox(meshes)
    c, ext = (lo + hi) / 2, hi - lo
    size = max(ext.x, ext.y)
    shoot(name, c, size, True, c + Vector((0, 0, max(ext) * 4)), os.path.join(OUT, f"{name}_top.png"))
    dist = max(ext) * 2.6
    shoot(name, c, size, False, c + Vector((-dist * 0.55, -dist * 0.8, dist * 0.65)), os.path.join(OUT, f"{name}_34.png"))
    print(f"RENDERED {name}: {len(meshes)} meshes, {textured} textured materials, size {ext.x * 100:.1f} x {ext.y * 100:.1f} x {ext.z * 100:.1f} cm")
    done.append(name)

# contact sheet: every 3/4 view, 4 per row, at half size
tiles = [os.path.join(OUT, f"{n}_34.png") for n in done]
if tiles:
    tw, th, cols = 600, 450, 4
    rows = (len(tiles) + cols - 1) // cols
    sheet = np.ones((rows * th, cols * tw, 4), dtype=np.float32)
    sheet[..., :3] = 0.62                          # the renders' grey, for the empty cells
    for i, t in enumerate(tiles):
        im = bpy.data.images.load(t)
        w, h = im.size
        px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::2, ::2][:th, :tw]
        r, c_ = rows - 1 - i // cols, i % cols
        sheet[r * th:r * th + px.shape[0], c_ * tw:c_ * tw + px.shape[1]] = px
    out = bpy.data.images.new("sheet", cols * tw, rows * th, alpha=True)
    out.pixels = sheet.ravel()
    out.filepath_raw = os.path.join(OUT, "gear_contact_sheet.png")
    out.file_format = "PNG"
    out.save()
    print(f"CONTACT SHEET {len(tiles)} views -> {out.filepath_raw}")
