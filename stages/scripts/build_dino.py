# Builds the "Dino Stage" environment for Tribe XR from the Blender output (Scripts/Blender/out, made by dino_stage.py).
# Run (full editor, like build_festival.py):
#   UnrealEditor.exe TribeXR.uproject -ExecutePythonScript="<this file>" -unattended -nosplash -abslog=<log>
# Same rules as the Festival (v2.1): every surface is an instance of a material Tribe ships (no shader maps in the pak),
# here Tribe's unlit glTFRuntime material showing lighting baked in Blender; every actor has collision OFF
# (set_collision_profile_name clears bUseDefaultCollision, which otherwise re-enables the mesh's BlockAll at load and
# swallows Tribe's menu pointer ray). Content lives under /Game/Mods/Dino and is labeled into the same chunk 50 pak.
import glob
import json
import math
import os
import sys

import unreal

ROOT = os.environ.get("DINO_ROOT", "/Game/Mods/Dino")    # DinoAnim: the animated twin rides next to the stock one
MAPS, MI, TEX, MESH = ROOT + "/Maps", ROOT + "/MaterialInstances", ROOT + "/Textures", ROOT + "/Meshes"
LEVEL = MAPS + "/Environment_Dino"
CHUNK_ID = int(os.environ.get("DINO_CHUNK", "50"))
UNLIT_PARENT = "/glTFRuntime/M_Unlit_glTFRuntimeBase"
UNLIT_2SIDED_PARENT = "/glTFRuntime/M_Unlit_glTFRuntimeTwoSided_Inst"
# Tribe also ships alpha-blended unlit instances (paklist: M_Unlit_glTFRuntime[TwoSided]Translucent_Inst; opacity =
# baseColorTexture alpha): beams and glow sprites. The stub here only stands in for the path, like the others.
UNLIT_2SIDED_TRANSLUCENT_PARENT = "/glTFRuntime/M_Unlit_glTFRuntimeTwoSidedTranslucent_Inst"
NO_MIPS = {"T_DinoGroundsPal", "T_DinoCues", "T_DinoLaserProg", "T_DinoLaserLib"}   # lookups: mips would blend cells
DATA_TEX = {"T_DinoCues", "T_DinoLaserProg", "T_DinoLaserLib"}   # linear data (the show's tables): sRGB off, uncompressed
# light-show rows (dino_stage.py CUE_ROWS) per beam/halo mesh group (out/show_groups.json: mesh -> "module:index")
BEAM_ROWS = {"atmosphere:0": 2, "atmosphere:1": 0, "infrastructure:0": 8, "landmarks:0": 9}   # sky, stage, FOH, stage 2
HALO_ROWS = {"atmosphere": 0}                      # the stage lenses follow the stage; other halos stay on (row 13)
# DINO_ANIM=1 (run by the Meta FORK editor only): these surfaces get our own animated materials (dino_materials.py)
# instead of instances of Tribe's. Their shaders ship in ShaderArchive-TribeXR_Chunk50, so the cook MUST be the fork's
# (device gate passed 2026-10-05). Unset: the MIC-only stage, cookable by either engine.
ANIMATED = os.environ.get("DINO_ANIM") == "1"
# mesh -> (factory name in dino_materials, material name, texture or None)
ANIM = {
    "SM_DinoLED": ("led_wall", "M_DinoLEDAnim", "T_DinoLED"),
    "SM_DinoScreen": ("moon", "M_DinoMoonAnim", "T_DinoMoon"),
    "SM_DinoBulbs": ("chase", "M_DinoBulbChase", None),
    "SM_DinoLenses": ("mover_lens", "M_DinoLensMover", "T_DinoLens"),         # v13: the lenses move with their heads
    "SM_DinoPillars": ("pillars", "M_DinoPillarsAnim", None),
    "SM_DinoBooth": ("scroll_tex", "M_DinoBoothAnim", "T_DinoBooth"),
    "SM_DinoBeams": ("beams_material", "M_DinoBeamsAnim", "T_DinoBeam"),     # every SM_DinoBeams<k>
    "SM_DinoHalos": ("beams_material", "M_DinoHalosAnim", "T_DinoHalo"),
    "SM_DinoLasers": ("laser_show", "M_DinoLasersShow", "T_DinoBeam"),     # v9 pattern engine, WPO (ModMaterialTools)
    # v13: the stage's moving heads move (atmosphere.STAGE_MOVES; the same pattern engine, WPO)
    "SM_DinoMoverBeams": ("mover_beams", "M_DinoMoverBeams", "T_DinoBeam"),
    "SM_DinoMoverHalos": ("mover_beams", "M_DinoMoverHalos", "T_DinoHalo"),
    "SM_DinoMoverHeads": ("mover_heads", "M_DinoMoverHeads", None),
    # night (the user: "the stage would also be dark except for the dj and the visuals, lazrs, lights"): the baked set is
    # lit only by the show's wash row (near black between hits)
    "SM_DinoStructure": ("show_lit", "M_DinoStructureShow", "T_DinoStructure"),
    "SM_DinoRig": ("show_lit", "M_DinoRigShow", "T_DinoRig"),
    "SM_DinoDeck": ("show_lit", "M_DinoDeckShow", "T_DinoDeck"),
    "SM_DinoRiser": ("show_lit", "M_DinoRiserShow", "T_DinoRiser"),
    "SM_DinoPlants": ("show_lit_2s", "M_DinoPlantsShow", "T_DinoPlants"),
    "SM_DinoGroundsStagedeck": ("show_lit", "M_DinoGroundsStagedeckShow", "T_DinoGroundsStagedeck"),   # v8: the DJ deck's gear dims with the stage
}
SRC = os.environ.get("DINO_SRC") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "Blender", "out")   # DINO_SRC: a bake elsewhere (DINO_OUT)

eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
level_ss = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actor_ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

# mesh -> (material instance name, parent, texture png or None, flat color or None)
SURFACES = {
    "SM_DinoStructure": ("MI_DinoStructure", UNLIT_PARENT, "T_DinoStructure", None),
    "SM_DinoDeck": ("MI_DinoDeck", UNLIT_PARENT, "T_DinoDeck", None),
    "SM_DinoGround": ("MI_DinoGround", UNLIT_PARENT, "T_DinoGround", None),
    "SM_DinoCrowd": ("MI_DinoCrowd", UNLIT_PARENT, "T_DinoCrowd", None),
    "SM_DinoLED": ("MI_DinoLED", UNLIT_PARENT, "T_DinoLED", None),
    "SM_DinoScreen": ("MI_DinoScreen", UNLIT_PARENT, "T_DinoMoon", None),
    # the big screen for Tribe's own visuals (videos from the media folder, GIFs, NDI): the mod registers it as the
    # backdrop (SetupEnvironmentBackdrop) after load and Tribe puts its own material on it; black until then
    "SM_DinoVisualScreen": ("MI_DinoVisualScreen", UNLIT_PARENT, None, (0.0, 0.0, 0.0)),
    "SM_DinoSky": ("MI_DinoSky", UNLIT_2SIDED_PARENT, "T_DinoSky", None),
    "SM_DinoBulbs": ("MI_DinoBulbs", UNLIT_PARENT, None, (1.0, 0.78, 0.45)),
    "SM_DinoPhones": ("MI_DinoPhones", UNLIT_PARENT, None, (0.85, 0.9, 1.0)),
    "SM_DinoEyes": ("MI_DinoEyes", UNLIT_PARENT, None, (1.0, 0.06, 0.02)),
    "SM_DinoFarGround": ("MI_DinoFar", UNLIT_PARENT, None, (0.004, 0.004, 0.006)),   # night pass
    "SM_DinoRig": ("MI_DinoRig", UNLIT_PARENT, "T_DinoRig", None),
    "SM_DinoLenses": ("MI_DinoLenses", UNLIT_PARENT, "T_DinoLens", None),
    "SM_DinoBooth": ("MI_DinoBooth", UNLIT_PARENT, "T_DinoBooth", None),
    "SM_DinoRiser": ("MI_DinoRiser", UNLIT_PARENT, "T_DinoRiser", None),
    "SM_DinoGlow": ("MI_DinoGlow", UNLIT_PARENT, None, (0.2, 0.9, 1.0)),
    "SM_DinoPillars": ("MI_DinoPillars", UNLIT_PARENT, None, (0.2, 0.9, 1.0)),
    "SM_DinoPlants": ("MI_DinoPlants", UNLIT_2SIDED_PARENT, "T_DinoPlants", None),
    "SM_DinoFlags": ("MI_DinoFlags", UNLIT_2SIDED_PARENT, "T_DinoFlags", None),
    "SM_DinoGroundsGlow": ("MI_DinoGroundsGlow", UNLIT_PARENT, "T_DinoGroundsPal", None),
    "SM_DinoHalos": ("MI_DinoHalos", UNLIT_2SIDED_TRANSLUCENT_PARENT, "T_DinoHalo", None),
    "SM_DinoLasers": ("MI_DinoLasers", UNLIT_2SIDED_TRANSLUCENT_PARENT, "T_DinoBeam", None),   # frozen unless ANIMATED
    "SM_DinoMoverBeams": ("MI_DinoMoverBeams", UNLIT_2SIDED_TRANSLUCENT_PARENT, "T_DinoBeam", None),   # v13 (frozen
    "SM_DinoMoverHalos": ("MI_DinoMoverHalos", UNLIT_2SIDED_TRANSLUCENT_PARENT, "T_DinoHalo", None),   # unless ANIMATED)
    "SM_DinoMoverHeads": ("MI_DinoMoverHeads", UNLIT_PARENT, None, (0.035, 0.036, 0.04)),
}
# festival grounds (grounds/*.py via dino_stage.py): one baked mesh per module, SM_DinoGrounds<Name> + T_DinoGrounds<Name>
for _fbx in sorted(glob.glob(os.path.join(SRC, "SM_DinoGrounds*.fbx"))):
    _n = os.path.splitext(os.path.basename(_fbx))[0]
    if _n not in SURFACES:
        SURFACES[_n] = ("MI" + _n[2:], UNLIT_PARENT, "T" + _n[2:], None)
for _fbx in sorted(glob.glob(os.path.join(SRC, "SM_DinoHalos*.fbx"))):   # one halo mesh per module (show rows)
    _n = os.path.splitext(os.path.basename(_fbx))[0]
    SURFACES[_n] = ("MI" + _n[2:], UNLIT_2SIDED_TRANSLUCENT_PARENT, "T_DinoHalo", None)
for _fbx in sorted(glob.glob(os.path.join(SRC, "SM_DinoBeams*.fbx"))):   # one translucent mesh per beam group (sorting)
    _n = os.path.splitext(os.path.basename(_fbx))[0]
    SURFACES[_n] = ("MI" + _n[2:], UNLIT_2SIDED_TRANSLUCENT_PARENT, "T_DinoBeam", None)
# dino_stage.py lists what it exported this run: anything else in out/ is stale and stays out of the level
_MANIFEST = os.path.join(SRC, "manifest.txt")
if os.path.exists(_MANIFEST):
    _listed = {l.strip() for l in open(_MANIFEST) if l.strip()}
    _missing = sorted(_listed - set(SURFACES))
    if _missing:
        raise RuntimeError(f"manifest meshes without a SURFACES entry: {_missing}")
    SURFACES = {k: v for k, v in SURFACES.items() if k in _listed}
else:                                                    # older output without a manifest: what's there
    SURFACES = {k: v for k, v in SURFACES.items() if os.path.exists(os.path.join(SRC, k + ".fbx"))}


def log(msg):
    unreal.log("[DINO] " + msg)


def fresh(path):
    if eal.does_asset_exist(path):
        eal.delete_asset(path)


def import_texture(png, name):
    path = f"{TEX}/{name}"
    fresh(path)
    task = unreal.AssetImportTask()
    for k, v in (("filename", png), ("destination_path", TEX), ("destination_name", name), ("automated", True),
                 ("replace_existing", True), ("save", False)):
        task.set_editor_property(k, v)
    tools.import_asset_tasks([task])
    tex = unreal.load_asset(path)
    tex.set_editor_property("srgb", True)
    if name in DATA_TEX:
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
    if name in NO_MIPS:
        tex.set_editor_property("filter", unreal.TextureFilter.TF_NEAREST)
        tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    eal.save_asset(path)
    log(f"texture {path} ({tex.blueprint_get_size_x()}x{tex.blueprint_get_size_y()})")
    return tex


VAT_MESHES = ("SM_DinoCrowd", "SM_DinoPhones")
# The giant intro (Blender/giant.py -> out_giant): the lift + button + floor-length robe, moved by MPC_DinoGiant (WPO),
# which the mod drives. Separate from the stage bake; skipped when out_giant has no giant_manifest.txt.
GIANT_SRC = os.environ.get("DINO_GIANT_SRC") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "Blender", "out_giant")
GIANT_MESHES = {"SM_DinoGiantLift": "giant_lift", "SM_DinoGiantGlow": "giant_glow", "SM_DinoGiantRobe": "giant_robe"}
# v7.5: no visible follow-spot beam (the user: "i dont need the light beam but how i look illuminated looks good"); the
# real light below stays. To bring the beam back: "SM_DinoGiantSpot": "giant_spot" here + build_spot() in giant.py.
# The giant intro's follow spot as a real light (lights the DJ's avatar; our set is unlit): on the FOH tower's right-hand
# follow spot (giant.py SPOT_APEX, Tribe world cm), aimed at the DJ's mid-height across the lift's range. The mod sets
# its intensity (candelas) with the fade; 0 at rest.
GIANT_SPOT_LIGHT = ("DinoGiantSpotLight", (-95.0, -3100.0, 535.0), (0.0, 90.0, 430.0))
# Two small lamps over the decks (the user: "the dj decks are too dark ... i only wanted a small light on the decks, not
# for the entire stage"). Tribe world cm: the mixer measured x -25..15, y 15..63, z 75..87; CDJs either side.
DECK_LAMPS = (("DinoDeckLamp_L", (-45.0, 40.0, 150.0)), ("DinoDeckLamp_R", (35.0, 40.0, 150.0)))   # crowd v2 (Scripts/Blender/crowd2): VAT channels + vertex colors


# v14 (the user: "it still needs to be darker on stage and in the crowd i think"): the baked field and festival-grounds
# MICs get baseColorFactor = dino_materials.NIGHT_GAIN (glTF: factor x texture); the set and crowd get it in show_light
NIGHT_MICS = {"SM_DinoGround", "SM_DinoGroundsVendors", "SM_DinoGroundsInfrastructure", "SM_DinoGroundsLandmarks",
              "SM_DinoGroundsAtmosphere"}
FULL_UV_MESHES = {"SM_DinoLasers", "SM_DinoMoverBeams", "SM_DinoMoverHalos", "SM_DinoMoverHeads",
                  "SM_DinoLenses"}   # per-vertex pivots (Blender m, up to 65) ride in UV1/UV2


def import_mesh(fbx, name):
    path = f"{MESH}/{name}"
    fresh(path)
    ui = unreal.FbxImportUI()
    for k, v in (("import_mesh", True), ("import_as_skeletal", False), ("import_materials", False),
                 ("import_textures", False), ("import_animations", False),
                 ("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)):
        ui.set_editor_property(k, v)
    sm = ui.get_editor_property("static_mesh_import_data")
    for k, v in (("combine_meshes", True), ("auto_generate_collision", False), ("generate_lightmap_u_vs", False),
                 ("build_nanite", False), ("import_uniform_scale", 100.0)):   # Blender writes meters; Unreal reads cm
        sm.set_editor_property(k, v)
    if name in VAT_MESHES or name == "SM_DinoGiantGlow":                # the glow parts carry their colors per vertex
        sm.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
    task = unreal.AssetImportTask()
    for k, v in (("filename", fbx), ("destination_path", MESH), ("destination_name", name), ("automated", True),
                 ("replace_existing", True), ("save", False), ("options", ui)):
        task.set_editor_property(k, v)
    tools.import_asset_tasks([task])
    mesh = unreal.load_asset(path)
    if mesh is None:
        raise RuntimeError("import failed: " + fbx)
    if name in FULL_UV_MESHES:                       # data in the UVs: keep 32-bit floats (FP16 rounds 65 m to 6 cm)
        sms = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        bs = sms.get_lod_build_settings(mesh, 0)
        bs.set_editor_property("use_full_precision_u_vs", True)
        sms.set_lod_build_settings(mesh, 0, bs)
        log(f"mesh {path}: full-precision UVs ({sms.get_num_uv_channels(mesh, 0)} channels)")
    eal.save_asset(path)
    b = mesh.get_bounds()
    log(f"mesh {path}: origin=({b.origin.x:.0f},{b.origin.y:.0f},{b.origin.z:.0f}) "
        f"extent=({b.box_extent.x:.0f},{b.box_extent.y:.0f},{b.box_extent.z:.0f})")
    return mesh


def instance(name, parent, vectors=None, textures=None):
    path = f"{MI}/{name}"
    fresh(path)
    mi = tools.create_asset(name, MI, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, parent)
    for pname, rgb in (vectors or {}).items():
        mel.set_material_instance_vector_parameter_value(mi, pname, unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
    for pname, tex in (textures or {}).items():
        mel.set_material_instance_texture_parameter_value(mi, pname, tex)
    mel.update_material_instance(mi)
    eal.save_asset(path)
    return mi


_SG = os.path.join(SRC, "show_groups.json")
SHOW_GROUPS = json.load(open(_SG)) if os.path.exists(_SG) else {}


def cue_instance(name, parent, row):
    """An instance of one of our show materials with its CueRow (no static changes: it shares the parent's shaders)."""
    path = f"{MI}/{name}"
    fresh(path)
    mi = tools.create_asset(name, MI, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, parent)
    mel.set_material_instance_scalar_parameter_value(mi, "CueRow", float(row))
    mel.update_material_instance(mi)
    eal.save_asset(path)
    return mi


def chunk_label():
    name = "PAL_" + ROOT.rstrip("/").rsplit("/", 1)[-1]   # unique per root: two "PAL_Dino" labels (Dino + DinoAnim) made
    # the asset manager keep one and drop the other's chunk, so a whole stage cooked into no chunk (2026-10-05)
    path = f"{ROOT}/{name}"
    fresh(path)
    factory = unreal.DataAssetFactory()
    factory.set_editor_property("data_asset_class", unreal.PrimaryAssetLabel)
    label = tools.create_asset(name, ROOT, unreal.PrimaryAssetLabel, factory)
    rules = unreal.PrimaryAssetRules()
    rules.set_editor_property("chunk_id", CHUNK_ID)
    rules.set_editor_property("priority", 1)
    rules.set_editor_property("apply_recursively", False)
    rules.set_editor_property("cook_rule", unreal.PrimaryAssetCookRule.ALWAYS_COOK)
    label.set_editor_property("rules", rules)
    label.set_editor_property("label_assets_in_my_directory", True)
    eal.save_asset(path)
    log(f"chunk label {path} -> chunk {CHUNK_ID}")


def translucent_stub(unlit):
    """Stand-in for Tribe's /glTFRuntime/M_Unlit_glTFRuntimeTwoSidedTranslucent_Inst (created once, never shipped):
    an instance of the unlit stub with the blend mode overridden to Translucent and two-sided on."""
    path = UNLIT_2SIDED_TRANSLUCENT_PARENT
    if eal.does_asset_exist(path):
        return unreal.load_asset(path)
    pkg, name = path.rsplit("/", 1)
    mi = tools.create_asset(name, pkg, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, unlit)
    ov = mi.get_editor_property("base_property_overrides")
    ov.set_editor_property("override_blend_mode", True)
    ov.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    ov.set_editor_property("override_two_sided", True)
    ov.set_editor_property("two_sided", True)
    mi.set_editor_property("base_property_overrides", ov)
    mel.update_material_instance(mi)
    eal.save_asset(path)
    log(f"stub {path} created")
    return mi


def build():
    for parent in (UNLIT_PARENT, UNLIT_2SIDED_PARENT):
        if not eal.does_asset_exist(parent):
            raise RuntimeError(parent + " stub missing: run build_festival.py once first")
    unlit, unlit2 = unreal.load_asset(UNLIT_PARENT), unreal.load_asset(UNLIT_2SIDED_PARENT)
    parents = {UNLIT_PARENT: unlit, UNLIT_2SIDED_PARENT: unlit2}
    if any(v[1] == UNLIT_2SIDED_TRANSLUCENT_PARENT for v in SURFACES.values()):
        parents[UNLIT_2SIDED_TRANSLUCENT_PARENT] = translucent_stub(unlit)
    if "SM_DinoLED" not in SURFACES:                    # v7.1: the curved LED wall is gone; its old assets would still cook
        for path in (f"{MESH}/SM_DinoLED", f"{MI}/MI_DinoLED", f"{MI}/M_DinoLEDAnim", f"{TEX}/T_DinoLED"):
            if eal.does_asset_exist(path):
                eal.delete_asset(path)
                log(f"removed stale {path}")
    for path in (f"{MI}/M_DinoLasersSweep",):           # v9: the laser show replaced v8's sweep material
        if eal.does_asset_exist(path):
            eal.delete_asset(path)
            log(f"removed stale {path}")
    if "SM_DinoGiantSpot" not in GIANT_MESHES:          # v7.5: the beam is gone; its old assets would still cook
        for path in (f"{MESH}/SM_DinoGiantSpot", f"{MI}/M_DinoGiantSpot"):
            if eal.does_asset_exist(path):
                eal.delete_asset(path)
                log(f"removed stale {path}")
    textures = {}
    for png in sorted(glob.glob(os.path.join(SRC, "T_Dino*.png"))):
        name = os.path.splitext(os.path.basename(png))[0]
        textures[name] = import_texture(png, name)
    meshes, mats, anim = {}, {}, {}
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import dino_materials as dm                                          # also the crowd v2 import helpers
    # the giant intro's collection first: every show material reads its ShowLevel / ShowOffset (blackout + restart)
    giant_on = ANIMATED and os.path.exists(os.path.join(GIANT_SRC, "giant_manifest.txt"))
    mpc = dm.make_mpc(MI, "MPC_DinoGiant", dm.GIANT_MPC_PARAMS) if giant_on else None
    dm.SHOW_MPC = mpc
    if ANIMATED:
        log("ANIMATED build: our own materials for " + ", ".join(ANIM))
    vat_exr, vat, meta = os.path.join(SRC, "T_DinoCrowdVAT.exr"), None, None
    if ANIMATED and os.path.exists(vat_exr):                             # crowd v2: the dance (RGBA16F, exact)
        fresh(f"{TEX}/T_DinoCrowdVAT")
        task = unreal.AssetImportTask()
        for k, v in (("filename", vat_exr), ("destination_path", TEX), ("destination_name", "T_DinoCrowdVAT"),
                     ("automated", True), ("replace_existing", True), ("save", False)):
            task.set_editor_property(k, v)
        tools.import_asset_tasks([task])
        vat = dm.prepare_vat_texture(unreal.load_asset(f"{TEX}/T_DinoCrowdVAT"))
        eal.save_asset(f"{TEX}/T_DinoCrowdVAT")
        meta = json.load(open(os.path.join(SRC, "T_DinoCrowdVAT.json")))
        log(f"crowd v2 VAT {vat.blueprint_get_size_x()}x{vat.blueprint_get_size_y()}")
    for sm_name, (mi_name, parent_path, tex, color) in SURFACES.items():
        meshes[sm_name] = import_mesh(os.path.join(SRC, sm_name + ".fbx"), sm_name)
        if sm_name in VAT_MESHES and vat is not None:                     # 5 UV channels, 16-bit UVs, no collision data
            dm.prepare_vat_mesh(meshes[sm_name])
            eal.save_asset(f"{MESH}/{sm_name}")
            mats[sm_name] = (dm.vat_crowd("M_DinoCrowdVAT", MI, vat, meta, baked_texture=textures["T_DinoCrowd"],
                                          cues=textures.get("T_DinoCues"))
                             if sm_name == "SM_DinoCrowd" else dm.vat_crowd("M_DinoCrowdGlowVAT", MI, vat, meta, glow=True))
            continue
        key = next((k for k in ("SM_DinoBeams", "SM_DinoHalos") if sm_name.startswith(k)), sm_name)
        if ANIMATED and key in ANIM:
            fac, mname, atex = ANIM[key]
            if mname not in anim:                                    # one material per kind (all beam meshes share)
                kw = {"texture": textures[atex]} if atex else {}
                if fac == "chase":
                    kw["rgb"] = (1.0, 0.78, 0.45)
                if "T_DinoCues" in textures and fac in ("beams_material", "laser_show", "strobe_tex", "show_lit", "show_lit_2s",
                                                        "mover_beams", "mover_heads", "mover_lens"):
                    kw["cues"] = textures["T_DinoCues"]               # the light show
                if fac in ("laser_show", "mover_beams", "mover_heads", "mover_lens"):   # the laser program + library
                    kw["prog"], kw["lib"] = textures["T_DinoLaserProg"], textures["T_DinoLaserLib"]
                anim[mname] = getattr(dm, fac)(mname, MI, **kw)
            mats[sm_name] = anim[mname]
            if key in ("SM_DinoMoverBeams", "SM_DinoMoverHalos") and "T_DinoCues" in textures:   # v13: the stage's rows
                row = BEAM_ROWS["atmosphere:1"] if key == "SM_DinoMoverBeams" else HALO_ROWS["atmosphere"]
                mats[sm_name] = cue_instance("MI" + sm_name[2:] + "Show", anim[mname], row)
                log(f"show: {sm_name} (moving heads) -> cue row {row}")
                continue
            if key in ("SM_DinoBeams", "SM_DinoHalos") and "T_DinoCues" in textures:   # its own cue row
                grp = SHOW_GROUPS.get(sm_name, "")
                row = BEAM_ROWS.get(grp, 13) if key == "SM_DinoBeams" else HALO_ROWS.get(grp, 13)
                mats[sm_name] = cue_instance("MI" + sm_name[2:] + "Show", anim[mname], row)
                log(f"show: {sm_name} ({grp or '?'}) -> cue row {row}")
            continue
        parent = parents[parent_path]
        if color is None and tex and sm_name in NIGHT_MICS:            # baked field / festival grounds: darker (v14)
            color = (dm.NIGHT_GAIN,) * 3
        mats[sm_name] = instance(mi_name, parent, {"baseColorFactor": color} if color else None,
                                 {"baseColorTexture": textures[tex]} if tex else None)
    if giant_on:
        for sm_name, fac in GIANT_MESHES.items():
            meshes[sm_name] = import_mesh(os.path.join(GIANT_SRC, sm_name + ".fbx"), sm_name)
            dm.prepare_giant_mesh(meshes[sm_name], up_cm=1200.0 if sm_name != "SM_DinoGiantSpot" else 900.0)
            eal.save_asset(f"{MESH}/{sm_name}")
            if fac == "giant_spot":
                mats[sm_name] = dm.giant_spot("M" + sm_name[2:], MI, mpc, textures["T_DinoBeam"])
            else:
                mats[sm_name] = getattr(dm, fac)("M" + sm_name[2:], MI, mpc)
        log(f"giant intro: {', '.join(GIANT_MESHES)} + MPC_DinoGiant (show materials read ShowLevel/ShowOffset)")
    chunk_label()

    # Blender modeled the stage BEHIND the DJ (+Y) with the crowd toward -Y. If the FBX axis conversion mirrored Y,
    # the screen comes out in front: turn the whole level around (the set is symmetric in X).
    sy = meshes["SM_DinoScreen"].get_bounds().origin.y
    yaw = 180.0 if sy < 0 else 0.0
    deck_w = meshes["SM_DinoDeck"].get_bounds().box_extent.x * 2
    log(f"orientation: screen center y={sy:.0f} cm -> level yaw {yaw:.0f}; deck+barrier width {deck_w:.0f} cm (expect ~6000)")

    if eal.does_asset_exist(LEVEL):
        eal.delete_asset(LEVEL)
    if not level_ss.new_level(LEVEL):
        raise RuntimeError("new_level failed for " + LEVEL)
    for sm_name, mesh in meshes.items():
        actor = actor_ss.spawn_actor_from_object(mesh, unreal.Vector(0, 0, 0), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        actor.set_actor_label(sm_name.replace("SM_", ""))
        comp = actor.static_mesh_component
        comp.set_mobility(unreal.ComponentMobility.MOVABLE)
        for slot in range(max(1, comp.get_num_materials())):         # every section (e.g. multi-material FBX)
            comp.set_material(slot, mats[sm_name])
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        comp.set_editor_property("cast_shadow", False)
        if (sm_name in VAT_MESHES and vat is not None) or sm_name in GIANT_MESHES:   # evaluate WPO, never disable it
            dm.prepare_vat_actor(comp)
        if comp.get_editor_property("use_default_collision"):
            raise RuntimeError(sm_name + ": collision still on")
    for lname, pos in DECK_LAMPS:                                     # deck lamps (Tribe's own gear is lit; our set is not)
        la = actor_ss.spawn_actor_from_class(unreal.SpotLight, unreal.Vector(*pos), unreal.Rotator(roll=0.0, pitch=-90.0, yaw=0.0))
        lc = la.get_component_by_class(unreal.SpotLightComponent)
        lc.set_mobility(unreal.ComponentMobility.MOVABLE)
        for k, v in (("intensity_units", unreal.LightUnits.CANDELAS), ("intensity", 3.0), ("attenuation_radius", 140.0),
                     ("outer_cone_angle", 38.0), ("inner_cone_angle", 20.0), ("cast_shadows", False),
                     ("light_color", unreal.Color(r=255, g=235, b=205, a=255))):
            lc.set_editor_property(k, v)
        try:
            la.rename(lname)                                           # lights.txt matches by name ("DinoDeckLamp=1.5")
        except Exception as e:  # noqa: BLE001
            log(f"deck lamp rename failed ({e}); it keeps {la.get_name()}")
        la.set_actor_label(lname)
        log(f"deck lamp {la.get_name()} at {pos}")
    if mpc is not None:                                                # the giant intro's follow spot (a real light)
        lname, pos, aim = GIANT_SPOT_LIGHT
        dx, dy, dz = (aim[i] - pos[i] for i in range(3))
        rot = unreal.Rotator(roll=0.0, pitch=math.degrees(math.atan2(dz, math.hypot(dx, dy))), yaw=math.degrees(math.atan2(dy, dx)))
        la = actor_ss.spawn_actor_from_class(unreal.SpotLight, unreal.Vector(*pos), rot)
        lc = la.get_component_by_class(unreal.SpotLightComponent)
        lc.set_mobility(unreal.ComponentMobility.MOVABLE)
        for k, v in (("intensity_units", unreal.LightUnits.CANDELAS), ("intensity", 0.0), ("attenuation_radius", 4500.0),
                     ("outer_cone_angle", 9.0), ("inner_cone_angle", 5.0), ("cast_shadows", False),
                     ("light_color", unreal.Color(r=255, g=240, b=220, a=255))):
            lc.set_editor_property(k, v)
        try:
            la.rename(lname)
        except Exception as e:  # noqa: BLE001
            log(f"giant spot rename failed ({e}); it keeps {la.get_name()}")
        la.set_actor_label(lname)
        log(f"giant spot light {la.get_name()} at {pos} -> {aim} (pitch {rot.pitch:.1f}, yaw {rot.yaw:.1f})")
    if not level_ss.save_current_level():
        raise RuntimeError("save_current_level failed")
    log(f"saved {LEVEL} ({len(meshes)} actors)")
    log("done")


try:
    build()
except Exception as e:
    unreal.log_error("[DINO] FAILED: " + repr(e))
finally:
    unreal.SystemLibrary.quit_editor()
