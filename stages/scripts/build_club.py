# Builds the REACTOR club environment for Tribe XR from the Blender output (Scripts/Blender/club/out_club, made by
# club_stage.py; plan: claudedocs/club_venue_plan.md in the tribe hack repo). Run with the Meta fork editor on the club's
# own project copy (so its cooks never touch the Dino session's Saved/Cooked):
#   D:\MetaUE54\Engine\Binaries\Win64\UnrealEditor.exe D:\TribeUE\MetaClub\TribeXR\TribeXR.uproject
#       -ExecutePythonScript="<this file>" -unattended -nosplash -nullrhi -abslog=<log>
# CLUB_ANIM=1 (phase 3a): the show. The baked room is lit only by the light show's wash row (near black between hits),
# beams / halos / lasers fade with their cue rows, lenses and the core pulse, the pixel strips chase, the crowd dances
# (VAT). These are our own materials from Scripts/dino_materials.py (imported, never edited), so the cook MUST be the
# fork's and the pak carries ShaderArchive-TribeXR_Chunk55. The show runs free on its 32-bar loop until the mod's MPC
# lookup is generalised to the club (plan 5.6). Unset: v1/v2's static room on Tribe's own unlit instances.
# v4 (2026-10-09): MPC_ClubShow, the show bus. The hook (dumper.cpp, the Dino session's) drives it like MPC_DinoGiant:
# the song's bars (ShowOffset), blackouts (ShowLevel), hits (HitMajor/Minor), drops (DropBoom) and bass (Bass); hook/club.cpp
# writes the player's head (PlayerX/Y) for the crowd's make-way. Our own factories in Scripts/club_materials.py read it:
# crowd v2 (crisp vertex-colour clothes x the light-only bake x the show, a show-coloured rim, dancing on the show clock,
# making way), lenses flashing on hits, the core breathing with the bass, beams and lasers on hits and drops.
# v6 (2026-10-09, the user: "WAY darker in there in the crowd and on stage. not as much on stage though. its supposed to
# be a dark club"): the room and stage are club_materials.club_lit (our own; the Dino's NIGHT_GAIN no longer reaches the
# club) x the dimmers RoomGain / StageGain, the crowd x CrowdGain / CrowdRim, all in MPC_ClubShow (CLUB_EXTRAS).
# v7 (2026-10-09): the moving heads move (club_movers.py; the Dino's v13 mover engine, dm._mover_wpo): yokes + heads
# (SM_ClubMoverHeads), lenses, beams and halos carry their fixture's data; built only when the export has the movers.
# v8 (2026-10-11, the user: "yeah let them hit the floor"): the sweeping lasers run on to the floor (club_lasers.py v8), on
# club_materials.laser_show: the Dino's engine + a clip past the mezzanine decks (club_lasers.LIDS) + a near-eye fade.
# Every actor has collision OFF (set_collision_profile_name clears bUseDefaultCollision, which otherwise re-enables the
# mesh's BlockAll at load and swallows Tribe's menu pointer ray). Content lives under /Game/Mods/Club, pak chunk 55.
# Helpers are copied from build_dino.py (it runs its build at import).
import glob
import inspect
import json
import os
import sys

import unreal

ROOT = os.environ.get("CLUB_ROOT", "/Game/Mods/Club")
MAPS, MI, TEX, MESH = ROOT + "/Maps", ROOT + "/MaterialInstances", ROOT + "/Textures", ROOT + "/Meshes"
LEVEL = MAPS + "/Environment_Club"
CHUNK_ID = int(os.environ.get("CLUB_CHUNK", "55"))
ANIMATED = os.environ.get("CLUB_ANIM") == "1"
UNLIT_PARENT = "/glTFRuntime/M_Unlit_glTFRuntimeBase"
UNLIT_2SIDED_TRANSLUCENT_PARENT = "/glTFRuntime/M_Unlit_glTFRuntimeTwoSidedTranslucent_Inst"
NO_MIPS = {"T_ClubGlowPal", "T_ClubCues", "T_ClubLaserProg", "T_ClubLaserLib"}   # lookups: mips would blend cells
DATA_TEX = {"T_ClubCues", "T_ClubLaserProg", "T_ClubLaserLib"}   # linear data (the show's tables): sRGB off, uncompressed
SRC = os.environ.get("CLUB_SRC") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "Blender", "club", "out_club")
PIX_BLUE, PIX_AMBER = (0.15, 0.30, 1.0), (1.0, 0.60, 0.12)

# mesh -> (material instance name, parent, texture png or None, flat color or None): the static path, and the fallback
SURFACES = {
    "SM_ClubFloor": ("MI_ClubFloor", UNLIT_PARENT, "T_ClubFloor", None),
    "SM_ClubHall": ("MI_ClubHall", UNLIT_PARENT, "T_ClubHall", None),
    "SM_ClubStage": ("MI_ClubStage", UNLIT_PARENT, "T_ClubStage", None),
    "SM_ClubCore": ("MI_ClubCore", UNLIT_PARENT, "T_ClubCore", None),
    "SM_ClubMezz": ("MI_ClubMezz", UNLIT_PARENT, "T_ClubMezz", None),
    "SM_ClubBar": ("MI_ClubBar", UNLIT_PARENT, "T_ClubBar", None),
    "SM_ClubRig": ("MI_ClubRig", UNLIT_PARENT, "T_ClubRig", None),
    "SM_ClubGlow": ("MI_ClubGlow", UNLIT_PARENT, "T_ClubGlowPal", None),
    "SM_ClubLenses": ("MI_ClubLenses", UNLIT_PARENT, "T_ClubGlowPal", None),
    "SM_ClubCoreGlow": ("MI_ClubCoreGlow", UNLIT_PARENT, "T_ClubGlowPal", None),
    "SM_ClubPixelBlue": ("MI_ClubPixelBlue", UNLIT_PARENT, None, PIX_BLUE),
    "SM_ClubPixelAmber": ("MI_ClubPixelAmber", UNLIT_PARENT, None, PIX_AMBER),
    "SM_ClubCrowd": ("MI_ClubCrowd", UNLIT_PARENT, "T_ClubCrowdLight", None),
    "SM_ClubPhones": ("MI_ClubPhones", UNLIT_PARENT, None, (0.85, 0.9, 1.0)),
    # v5: the sweeping lasers (club_lasers.py), moved by the Dino's laser engine (dino_materials.laser_show)
    "SM_ClubLaserShow": ("MI_ClubLaserShow", UNLIT_2SIDED_TRANSLUCENT_PARENT, "T_ClubBeam", None),
    # v7: the moving heads' yokes and heads (club_movers.py), moved by the Dino's v13 mover engine
    "SM_ClubMoverHeads": ("MI_ClubMoverHeads", UNLIT_PARENT, None, (0.035, 0.036, 0.04)),
    # the core window: the mod finds it by this MESH name, registers it as Tribe's backdrop and Tribe puts its own video
    # material on it; black until then (and hidden by Tribe while the visuals are off: the core shows behind it)
    "SM_DinoVisualScreen": ("MI_ClubVisualScreen", UNLIT_PARENT, None, (0.0, 0.0, 0.0)),
    "SM_ClubSideScreens": ("MI_ClubSideScreens", UNLIT_PARENT, None, (0.02, 0.04, 0.10)),   # idle panels; phase 2: the mod mirrors the video
}
for _fbx in sorted(glob.glob(os.path.join(SRC, "SM_Club*.fbx"))):      # per-group translucent meshes (each its cue row)
    _n = os.path.splitext(os.path.basename(_fbx))[0]
    if _n.startswith(("SM_ClubBeams", "SM_ClubHalos", "SM_ClubLasers")):
        SURFACES[_n] = ("MI" + _n[2:], UNLIT_2SIDED_TRANSLUCENT_PARENT, "T_ClubHalo" if _n.startswith("SM_ClubHalos") else "T_ClubBeam", None)
_MANIFEST = os.path.join(SRC, "manifest.txt")         # club_stage.py lists what it exported: build exactly that
_listed = [l.strip() for l in open(_MANIFEST) if l.strip()]
_missing = sorted(set(_listed) - set(SURFACES))
if _missing:
    raise RuntimeError(f"manifest meshes without a SURFACES entry: {_missing}")
SURFACES = {k: v for k, v in SURFACES.items() if k in _listed}
_ROWS = os.path.join(SRC, "club_rows.json")            # translucent mesh -> its cue row (club_show.CUE_ROWS)
_ROWS_J = json.load(open(_ROWS)) if os.path.exists(_ROWS) else {}
ROWS = _ROWS_J.get("rows", {})
CROWD_LIGHT_GAIN = float(_ROWS_J.get("crowd_light_gain", 1.0))     # club_stage.py: the light-only bake's gain
SHOW_LIT = ("SM_ClubFloor", "SM_ClubHall", "SM_ClubStage", "SM_ClubCore", "SM_ClubMezz", "SM_ClubBar", "SM_ClubRig")
VAT_MESHES = ("SM_ClubCrowd", "SM_ClubPhones")
FULL_UV_MESHES = {"SM_ClubLaserShow"}                # per-vertex pivots ride in the UVs: 32-bit (as build_dino.py)
# v7: with SM_ClubMoverHeads in the export, the lenses, beams and halos carry their fixture's move data too (club_movers)
MOVERS = "SM_ClubMoverHeads" in SURFACES
MOVER_MESHES = ({"SM_ClubMoverHeads", "SM_ClubLenses"} |
                {k for k in SURFACES if k.startswith(("SM_ClubBeams", "SM_ClubHalos"))}) if MOVERS else set()
FULL_UV_MESHES |= MOVER_MESHES
BOUNDS_CM = {"SM_ClubLaserShow": 400.0}              # padded bounds for the sweeps (the movers' beams reach farther: 800)
# Two small lamps over the decks, as on the Dino Stage (Tribe world cm: the mixer measured x -25..15, y 15..63, z 75..87)
DECK_LAMPS = (("ClubDeckLamp_L", (-45.0, 40.0, 150.0)), ("ClubDeckLamp_R", (35.0, 40.0, 150.0)))

eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
level_ss = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actor_ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def log(msg):
    unreal.log("[CLUB] " + msg)


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
    if name in VAT_MESHES:                                              # the crowd carries its colours per vertex
        sm.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
    task = unreal.AssetImportTask()
    for k, v in (("filename", fbx), ("destination_path", MESH), ("destination_name", name), ("automated", True),
                 ("replace_existing", True), ("save", False), ("options", ui)):
        task.set_editor_property(k, v)
    tools.import_asset_tasks([task])
    mesh = unreal.load_asset(path)
    if mesh is None:
        raise RuntimeError("import failed: " + fbx)
    if name in FULL_UV_MESHES:                     # data in the UVs: keep 32-bit floats; padded bounds for the sweeps
        sms = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        bs = sms.get_lod_build_settings(mesh, 0)
        bs.set_editor_property("use_full_precision_u_vs", True)
        sms.set_lod_build_settings(mesh, 0, bs)
        ext = BOUNDS_CM.get(name, 800.0)
        mesh.set_editor_property("positive_bounds_extension", unreal.Vector(ext, ext, ext))
        mesh.set_editor_property("negative_bounds_extension", unreal.Vector(ext, ext, ext))
        log(f"mesh {path}: full-precision UVs ({sms.get_num_uv_channels(mesh, 0)} channels), bounds +-{ext:.0f} cm")
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
    name = "PAL_" + ROOT.rstrip("/").rsplit("/", 1)[-1]   # unique per root (two same-named labels drop a chunk: Dino)
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


# the factories this build takes from dino_materials (owned by the Dino session): checked first, so a change there
# stops this build with a clear message instead of a half-built level
NEEDS = {"chase": ("name", "folder", "rgb"),                       # (v6: the room is club_lit now, not dm.show_lit)
         "prepare_vat_texture": ("tex",), "prepare_vat_mesh": ("mesh", "uv_channels"), "prepare_vat_actor": ("component",),
         "make_mpc": ("folder", "name", "scalars"), "cue_level": ("g", "cues", "row"), "show_mpc": ("g", "pname"),
         "connect_wpo": ("g", "expr"), "_sat": ("g", "x"), "_mover_wpo": ("g", "prog", "lib"), "show_dim": ("g", "e"),
         "laser_show": ("name", "folder", "texture", "cues", "prog", "lib")}
# the hook's show bus writes these by name (dumper.cpp G_PARAMS, the Dino session's order); club extras come after them
SHOW_NAMES = ("Height", "RobeTopX", "RobeTopY", "RobeTopZ", "RobeOn", "ButtonGlow", "ShowLevel", "ShowOffset", "SpotOn",
              "TopLasers", "LaserVariant", "HitMajor", "HitMinor", "HitCount", "DropBoom", "HitsOn", "Bass",
              "ShowPrevBar", "ShowNextBar")   # v14b (the Dino session): the bars around this one as the song plays them
CLUB_EXTRAS = {"PlayerX": 1.0e6, "PlayerY": 1.0e6, "GateOpen": 0.0, "GateState": 0.0, "GateDeny": 0.0,
               # v6, the dark club (club_materials.club_lit / club_crowd): the pak's look; hook/club.cpp can override
               # each live from tribemod/club.txt (room= stage= crowd= rim=). v5 was 1 / 1 / 1 / 1 (and brighter floors)
               "RoomGain": 0.3, "StageGain": 0.6, "CrowdGain": 0.3, "CrowdRim": 0.5}
STAGE_LIT = ("SM_ClubStage", "SM_ClubCore")                    # the DJ's stage and the core wall behind it: StageGain


def load_materials_module():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import dino_materials as dm
    for fn, params in NEEDS.items():
        f = getattr(dm, fn, None)
        if f is None:
            raise RuntimeError(f"dino_materials.{fn} is gone: adapt build_club.py")
        have = inspect.signature(f).parameters
        missing = [p for p in params if p not in have]
        if missing:
            raise RuntimeError(f"dino_materials.{fn} lost parameters {missing}: adapt build_club.py")
    if getattr(dm, "WASH_ROW", None) != 1:
        raise RuntimeError(f"dino_materials.WASH_ROW is {getattr(dm, 'WASH_ROW', None)}, club_show.py puts the wash on row 1")
    for k in ("G", "BEAT_HZ", "HALF_HZ", "GIANT_MPC_PARAMS"):
        if not hasattr(dm, k):
            raise RuntimeError(f"dino_materials.{k} is gone: adapt club_materials.py / build_club.py")
    if tuple(dm.GIANT_MPC_PARAMS)[:len(SHOW_NAMES)] != SHOW_NAMES:
        raise RuntimeError(f"MPC_DinoGiant's names changed ({list(dm.GIANT_MPC_PARAMS)}): the show bus writes by name, check")
    import club_materials as cm
    for fn in ("get_material_property_input_node", "get_material_property_input_node_output_name"):
        if not hasattr(mel, fn):                                         # v8: cm.laser_show extends dm.laser_show's graph
            raise RuntimeError(f"MaterialEditingLibrary.{fn} missing: cm.laser_show can't extend the laser material")
    return dm, cm


def laser_lids():
    """v8: the mezzanine decks' tops in the club frame (club_lasers.LIDS, plain Python), for the laser material's clip."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "Blender", "club"))
    import club_lasers
    return club_lasers.LIDS


def build():
    for parent in (UNLIT_PARENT, UNLIT_2SIDED_TRANSLUCENT_PARENT):
        if not eal.does_asset_exist(parent):
            raise RuntimeError(parent + " stub missing (the project's Plugins/glTFRuntime holds the stand-ins)")
    parents = {p: unreal.load_asset(p) for p in (UNLIT_PARENT, UNLIT_2SIDED_TRANSLUCENT_PARENT)}
    dm, cm = load_materials_module() if ANIMATED else (None, None)
    if ANIMATED:                                                        # the show bus: the hook drives it like MPC_DinoGiant
        params = {k: dm.GIANT_MPC_PARAMS[k] for k in SHOW_NAMES}
        params.update(CLUB_EXTRAS)
        dm.SHOW_MPC = dm.make_mpc(MI, "MPC_ClubShow", params)
        log(f"MPC_ClubShow at {MI}/MPC_ClubShow: {len(params)} scalars (ShowLevel default {params['ShowLevel']})")
    log(("ANIMATED build (phase 3a show + crowd)" if ANIMATED else "static build (Tribe's unlit instances)") +
        f": {len(SURFACES)} meshes from {SRC}")
    textures = {}
    for png in sorted(glob.glob(os.path.join(SRC, "T_Club*.png"))):
        name = os.path.splitext(os.path.basename(png))[0]
        textures[name] = import_texture(png, name)
    vat, meta = None, None
    if ANIMATED and "SM_ClubCrowd" in SURFACES:                         # the crowd's dance (RGBA16F, exact)
        fresh(f"{TEX}/T_ClubCrowdVAT")
        task = unreal.AssetImportTask()
        for k, v in (("filename", os.path.join(SRC, "T_ClubCrowdVAT.exr")), ("destination_path", TEX),
                     ("destination_name", "T_ClubCrowdVAT"), ("automated", True), ("replace_existing", True), ("save", False)):
            task.set_editor_property(k, v)
        tools.import_asset_tasks([task])
        vat = dm.prepare_vat_texture(unreal.load_asset(f"{TEX}/T_ClubCrowdVAT"))
        eal.save_asset(f"{TEX}/T_ClubCrowdVAT")
        meta = json.load(open(os.path.join(SRC, "T_ClubCrowdVAT.json")))
        log(f"crowd VAT {vat.blueprint_get_size_x()}x{vat.blueprint_get_size_y()}")
    cues = textures.get("T_ClubCues")
    if ANIMATED and cues is None:
        raise RuntimeError("T_ClubCues.png missing: club_stage.py writes it")
    meshes, mats, shared = {}, {}, {}
    for sm_name, (mi_name, parent_path, tex, color) in SURFACES.items():
        meshes[sm_name] = import_mesh(os.path.join(SRC, sm_name + ".fbx"), sm_name)
        if not ANIMATED:
            mats[sm_name] = instance(mi_name, parents[parent_path], {"baseColorFactor": color} if color else None,
                                     {"baseColorTexture": textures[tex]} if tex else None)
            continue
        if sm_name in SHOW_LIT:                                           # the baked room, lit by the show's wash
            stage = sm_name in STAGE_LIT                                  # x the dark-club dimmer (v6)
            mats[sm_name] = cm.club_lit("M" + sm_name[2:] + "Show", MI, textures[tex], cues,
                                        gain="StageGain" if stage else "RoomGain",
                                        floor=cm.STAGE_FLOOR if stage else cm.ROOM_FLOOR)
        elif sm_name == "SM_ClubLenses" and MOVERS:                       # v7: the lenses move with their heads
            mats[sm_name] = cm.mover_lens("M_ClubLenses", MI, textures["T_ClubGlowPal"], cues,
                                          textures["T_ClubLaserProg"], textures["T_ClubLaserLib"], row=10)
        elif sm_name == "SM_ClubLenses":
            mats[sm_name] = cm.lenses("M_ClubLenses", MI, textures["T_ClubGlowPal"], cues, row=10)
        elif sm_name == "SM_ClubMoverHeads":                               # v7: yokes + heads, dark metal that moves
            mats[sm_name] = cm.mover_heads("M_ClubMoverHeads", MI, textures["T_ClubLaserProg"], textures["T_ClubLaserLib"])
        elif sm_name == "SM_ClubCoreGlow":
            mats[sm_name] = cm.core_glow("M_ClubCoreGlow", MI, textures["T_ClubGlowPal"], cues, row=2)
        elif sm_name in ("SM_ClubPixelBlue", "SM_ClubPixelAmber"):
            mats[sm_name] = dm.chase("M" + sm_name[2:], MI, rgb=PIX_BLUE if sm_name.endswith("Blue") else PIX_AMBER)
        elif sm_name == "SM_ClubLaserShow":                               # v5: the Dino's laser engine, our units
            lids = laser_lids()                                           # v8: + the deck clip and the near fade
            mats[sm_name] = cm.laser_show("M_ClubLaserShow", MI, textures["T_ClubBeam"], cues,
                                          textures["T_ClubLaserProg"], textures["T_ClubLaserLib"], lids=lids)
            log(f"lasers: M_ClubLaserShow clips past {len(lids)} deck tops {lids}, fades within {cm.LASER_NEAR[1]:.0f} cm")
        elif sm_name in VAT_MESHES and vat is not None:
            dm.prepare_vat_mesh(meshes[sm_name], uv_channels=6)          # UV0 + VAT UV1..UV4 + the pivot (UV5)
            eal.save_asset(f"{MESH}/{sm_name}")
            mats[sm_name] = (cm.club_crowd("M_ClubCrowdVAT", MI, vat, meta, light_texture=textures["T_ClubCrowdLight"],
                                           cues=cues, light_gain=CROWD_LIGHT_GAIN)
                             if sm_name == "SM_ClubCrowd" else cm.club_crowd("M_ClubCrowdGlowVAT", MI, vat, meta, glow=True))
        elif sm_name.startswith(("SM_ClubBeams", "SM_ClubHalos", "SM_ClubLasers")):
            kind = ("Halos" if sm_name.startswith("SM_ClubHalos") else "Lasers" if sm_name.startswith("SM_ClubLasers")
                    else "Beams")
            if kind not in shared:                                        # one material per kind, an instance per row
                if MOVERS and kind != "Lasers":                           # v7: beams and halos move with their heads
                    shared[kind] = cm.mover_beams(f"M_Club{kind}Anim", MI, textures[tex], cues,
                                                  textures["T_ClubLaserProg"], textures["T_ClubLaserLib"])
                else:
                    make = cm.laser_lines if kind == "Lasers" else cm.beams
                    shared[kind] = make(f"M_Club{kind}Anim", MI, textures[tex], cues)
            if sm_name not in ROWS:
                raise RuntimeError(f"{sm_name}: no cue row in club_rows.json")
            mats[sm_name] = cue_instance("MI" + sm_name[2:] + "Show", shared[kind], ROWS[sm_name])
            log(f"show: {sm_name} -> cue row {ROWS[sm_name]}")
        else:                                                             # static: practicals, screens
            mats[sm_name] = instance(mi_name, parents[parent_path], {"baseColorFactor": color} if color else None,
                                     {"baseColorTexture": textures[tex]} if tex else None)
    chunk_label()

    # Blender modeled the core bay BEHIND the DJ (+Y). The FBX import converts handedness by flipping Y, so the screen
    # comes in at -Y: turn the level around. Conversion + turn keep the DJ's right on the DJ's right (Dino's screen and
    # LED text read correctly on device), so the airlock stays on the DJ's right as designed.
    sy = meshes["SM_DinoVisualScreen"].get_bounds().origin.y
    yaw = 180.0 if sy < 0 else 0.0
    hall = meshes["SM_ClubHall"].get_bounds()
    log(f"orientation: screen centre y={sy:.0f} cm -> level yaw {yaw:.0f}; hall extent "
        f"({hall.box_extent.x * 2:.0f} x {hall.box_extent.y * 2:.0f} x {hall.box_extent.z * 2:.0f} cm, expect ~2480 x 4430 x 1420)")

    if eal.does_asset_exist(LEVEL):
        eal.delete_asset(LEVEL)
    if not level_ss.new_level(LEVEL):
        raise RuntimeError("new_level failed for " + LEVEL)
    for sm_name, mesh in meshes.items():
        actor = actor_ss.spawn_actor_from_object(mesh, unreal.Vector(0, 0, 0), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        actor.set_actor_label(sm_name.replace("SM_", ""))
        comp = actor.static_mesh_component
        comp.set_mobility(unreal.ComponentMobility.MOVABLE)
        for slot in range(max(1, comp.get_num_materials())):
            comp.set_material(slot, mats[sm_name])
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        comp.set_editor_property("cast_shadow", False)
        if ANIMATED and sm_name in VAT_MESHES and vat is not None:      # evaluate WPO, never disable it
            dm.prepare_vat_actor(comp)
        if comp.get_editor_property("use_default_collision"):
            raise RuntimeError(sm_name + ": collision still on")
    for lname, pos in DECK_LAMPS:                                   # deck lamps (Tribe's gear is lit; our set is not)
        la = actor_ss.spawn_actor_from_class(unreal.SpotLight, unreal.Vector(*pos), unreal.Rotator(roll=0.0, pitch=-90.0, yaw=0.0))
        lc = la.get_component_by_class(unreal.SpotLightComponent)
        lc.set_mobility(unreal.ComponentMobility.MOVABLE)
        for k, v in (("intensity_units", unreal.LightUnits.CANDELAS), ("intensity", 3.0), ("attenuation_radius", 140.0),
                     ("outer_cone_angle", 38.0), ("inner_cone_angle", 20.0), ("cast_shadows", False),
                     ("light_color", unreal.Color(r=255, g=235, b=205, a=255))):
            lc.set_editor_property(k, v)
        try:
            la.rename(lname)                                        # lights.txt matches by name
        except Exception as e:  # noqa: BLE001
            log(f"deck lamp rename failed ({e}); it keeps {la.get_name()}")
        la.set_actor_label(lname)
        log(f"deck lamp {la.get_name()} at {pos}")
    if not level_ss.save_current_level():
        raise RuntimeError("save_current_level failed")
    log(f"saved {LEVEL} ({len(meshes)} actors)")
    log("done")


try:
    build()
except Exception as e:
    unreal.log_error("[CLUB] FAILED: " + repr(e))
finally:
    unreal.SystemLibrary.quit_editor()
