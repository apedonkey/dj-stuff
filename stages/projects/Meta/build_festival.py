# Builds the Festival environment for Tribe XR -- v2: NO custom shaders in the mod pak.
# Run (full editor; spawning actors crashes in -run=pythonscript commandlet mode on 5.4, EXCEPTION_ACCESS_VIOLATION @0x40):
#   UnrealEditor.exe TribeXR.uproject -ExecutePythonScript="<this file>" -unattended -nosplash -abslog=<log>
# The script closes the editor itself when it finishes (or fails).
#
# Why v2: loading our own cooked *materials* made Tribe allocate ~2 GB and get killed (2026-10-04). Meshes cook
# byte-identical to Tribe's, materials don't (their compiled shader-map data depends on the engine build's plugins and
# features). So every surface here is a MaterialInstanceConstant of a material Tribe already ships:
#   lit colors      -> /Engine/BasicShapes/BasicShapeMaterial            ("Color")
#   unlit colors    -> /glTFRuntime/M_Unlit_glTFRuntimeBase              ("baseColorFactor", "baseColorTexture")
#   unlit 2-sided   -> /glTFRuntime/M_Unlit_glTFRuntimeTwoSided_Inst      (sky dome, seen from inside)
# /glTFRuntime/* only exist here as stub parents (Plugins/glTFRuntime); they are never shipped, so on the headset the
# instances resolve to Tribe's real materials by path. Instances without static-switch overrides carry no shader maps.
#
# Layout facts from the headset (NOTES.md Session 3n): Tribe's DJ rig sits at the world origin, the floor is z=0, and
# the DJ stands at about y=+90 facing -Y. So: the crowd is toward -Y, the stage deck top is flush with the floor, and the
# LED wall stands behind the DJ (+Y) the way a festival main stage faces its crowd.
import os
import unreal

ROOT = "/Game/Mods/Festival"
MAPS = ROOT + "/Maps"
MI = ROOT + "/MaterialInstances"
TEX = ROOT + "/Textures"
LEVEL = MAPS + "/Environment_Festival"
CHUNK_ID = 50  # our own pak chunk -> pakchunk50

LIT_PARENT = "/Engine/BasicShapes/BasicShapeMaterial"
UNLIT_PARENT = "/glTFRuntime/M_Unlit_glTFRuntimeBase"
UNLIT_2SIDED_PARENT = "/glTFRuntime/M_Unlit_glTFRuntimeTwoSided_Inst"
WHITE = "/Engine/EngineResources/WhiteSquareTexture"
SCRIPTS = os.path.dirname(os.path.abspath(__file__))

eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
level_ss = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actor_ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def log(msg):
    unreal.log("[FESTIVAL] " + msg)


def fresh(path):
    if eal.does_asset_exist(path):
        eal.delete_asset(path)


# ---- stub parents (mirror the names/parameters of Tribe's shipped glTFRuntime materials; never shipped) ----
def stub_unlit_base():
    if eal.does_asset_exist(UNLIT_PARENT):
        return unreal.load_asset(UNLIT_PARENT)
    mat = tools.create_asset("M_Unlit_glTFRuntimeBase", "/glTFRuntime", unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    col = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -500, 0)
    col.set_editor_property("parameter_name", "baseColorFactor")
    col.set_editor_property("default_value", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
    tex = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -500, 220)
    tex.set_editor_property("parameter_name", "baseColorTexture")
    tex.set_editor_property("texture", unreal.load_asset(WHITE))
    mul = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -250, 100)
    mel.connect_material_expressions(col, "", mul, "A")
    mel.connect_material_expressions(tex, "RGB", mul, "B")
    mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(mat)
    eal.save_asset(UNLIT_PARENT)
    log("stub " + UNLIT_PARENT)
    return mat


def stub_unlit_two_sided(base):
    if eal.does_asset_exist(UNLIT_2SIDED_PARENT):
        return unreal.load_asset(UNLIT_2SIDED_PARENT)
    mi = tools.create_asset("M_Unlit_glTFRuntimeTwoSided_Inst", "/glTFRuntime", unreal.MaterialInstanceConstant,
                            unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, base)
    ov = mi.get_editor_property("base_property_overrides")
    ov.set_editor_property("override_two_sided", True)
    ov.set_editor_property("two_sided", True)
    mi.set_editor_property("base_property_overrides", ov)
    mel.update_material_instance(mi)
    eal.save_asset(UNLIT_2SIDED_PARENT)
    log("stub " + UNLIT_2SIDED_PARENT)
    return mi


# ---- our assets (all under /Game/Mods/Festival -> chunk 50) ----
def import_texture(png, name):
    path = f"{TEX}/{name}"
    fresh(path)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", png)
    task.set_editor_property("destination_path", TEX)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    tools.import_asset_tasks([task])
    tex = unreal.load_asset(path)
    tex.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    eal.save_asset(path)
    log("texture " + path)
    return tex


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
    log("instance " + path)
    return mi


def chunk_label():
    name = "PAL_Festival"
    path = f"{ROOT}/{name}"
    fresh(path)
    factory = unreal.DataAssetFactory()
    factory.set_editor_property("data_asset_class", unreal.PrimaryAssetLabel)
    label = tools.create_asset(name, ROOT, unreal.PrimaryAssetLabel, factory)
    rules = unreal.PrimaryAssetRules()
    rules.set_editor_property("chunk_id", CHUNK_ID)
    rules.set_editor_property("priority", 1)
    rules.set_editor_property("apply_recursively", False)   # never pull parents/engine content (or the stubs) into our chunk
    rules.set_editor_property("cook_rule", unreal.PrimaryAssetCookRule.ALWAYS_COOK)
    label.set_editor_property("rules", rules)
    label.set_editor_property("label_assets_in_my_directory", True)
    eal.save_asset(path)
    log(f"chunk label {path} -> chunk {CHUNK_ID} (not recursive)")


SHAPES = {"cube": "/Engine/BasicShapes/Cube", "sphere": "/Engine/BasicShapes/Sphere"}


def place(label, shape, loc, scale, mat, yaw=0.0):
    mesh = unreal.load_asset(SHAPES[shape])
    actor = actor_ss.spawn_actor_from_object(mesh, unreal.Vector(*loc), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    actor.set_actor_label(label)
    actor.set_actor_scale3d(unreal.Vector(*scale))
    comp = actor.static_mesh_component
    comp.set_mobility(unreal.ComponentMobility.MOVABLE)     # lit by the Void's lights without a lighting build
    comp.set_material(0, mat)
    # SetCollisionProfileName also clears bUseDefaultCollision. AStaticMeshActor sets that flag, and at load it re-applies
    # the MESH's collision (BlockAll) over ours. In v2 the 300 m sky sphere then enclosed the player, and Tribe's menu
    # pointer ray hit it at distance 0: no laser, no menu clicks. SetCollisionEnabled alone does not clear the flag.
    comp.set_collision_profile_name("NoCollision")
    comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    comp.set_editor_property("cast_shadow", False)
    if comp.get_editor_property("use_default_collision") or comp.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION:
        raise RuntimeError(f"{label}: collision still on (use_default_collision="
                           f"{comp.get_editor_property('use_default_collision')}, {comp.get_collision_enabled()})")
    return actor


def build():
    log("start (v2: material instances of Tribe's shipped materials only)")
    if eal.does_directory_exist(ROOT + "/Materials"):
        eal.delete_directory(ROOT + "/Materials")          # v1's custom materials (their shader maps OOM'd Tribe)
        log("removed v1 custom materials")
    lit = unreal.load_asset(LIT_PARENT)
    unlit = stub_unlit_base()
    unlit2 = stub_unlit_two_sided(unlit)
    sky_tex = import_texture(os.path.join(SCRIPTS, "Textures", "T_SkyGradient.png"), "T_SkyGradient")
    m = {
        "deck": instance("MI_StageDeck", lit, {"Color": (0.05, 0.05, 0.06)}),
        "ground": instance("MI_Ground", lit, {"Color": (0.04, 0.07, 0.04)}),
        "truss": instance("MI_Truss", lit, {"Color": (0.30, 0.30, 0.32)}),
        "speaker": instance("MI_Speaker", lit, {"Color": (0.02, 0.02, 0.02)}),
        "barrier": instance("MI_Barrier", lit, {"Color": (0.55, 0.55, 0.58)}),
        "led": instance("MI_LEDWall", unlit, {"baseColorFactor": (1.0, 0.15, 0.85)}),
        "side": instance("MI_SideScreen", unlit, {"baseColorFactor": (0.1, 0.8, 1.0)}),
        "light": instance("MI_LightFixture", unlit, {"baseColorFactor": (1.0, 0.9, 0.7)}),
        "sky": instance("MI_Sky", unlit2, {"baseColorFactor": (1.0, 1.0, 1.0)}, {"baseColorTexture": sky_tex}),
    }
    chunk_label()

    fresh(LEVEL)
    if not level_ss.new_level(LEVEL):
        raise RuntimeError("new_level failed for " + LEVEL)
    log(f"new level {LEVEL}")
    place("Ground", "cube", (0, -6000, -160), (600, 600, 0.2), m["ground"])
    place("StageDeck", "cube", (0, 300, -75), (26, 13, 1.5), m["deck"])
    place("LEDWall", "cube", (0, 850, 560), (20, 0.3, 11), m["led"])
    for x in (-1300, 1300):
        for y in (-350, 950):
            place(f"TrussColumn_{x}_{y}", "cube", (x, y, 650), (0.6, 0.6, 13), m["truss"])
        place(f"TrussSide_{x}", "cube", (x, 300, 1300), (0.6, 13.6, 0.6), m["truss"])
    for y in (-350, 950):
        place(f"TrussBeam_{y}", "cube", (0, y, 1300), (26.6, 0.6, 0.6), m["truss"])
    place("Canopy", "cube", (0, 300, 1360), (27, 14, 0.2), m["truss"])
    for i, x in enumerate(range(-1100, 1101, 200)):
        place(f"Light_{i:02d}", "cube", (x, -350, 1240), (0.45, 0.45, 0.45), m["light"])
    for x in (-1650, 1650):
        place(f"Speakers_{x}", "cube", (x, -250, 160), (2.4, 2.4, 6.4), m["speaker"])
        place(f"SideScreen_{x}", "cube", (x * 1.45, -150, 700), (8, 0.3, 5), m["side"], yaw=(-18.0 if x < 0 else 18.0))
    place("CrowdBarrier", "cube", (0, -750, -100), (34, 0.3, 1.2), m["barrier"])
    place("SkyDome", "sphere", (0, 0, 0), (600, 600, 600), m["sky"])

    if not level_ss.save_current_level():
        raise RuntimeError("save_current_level failed")
    log(f"saved {LEVEL}")
    log("done")


try:
    build()
except Exception as e:
    unreal.log_error("[FESTIVAL] FAILED: " + repr(e))
finally:
    unreal.SystemLibrary.quit_editor()
