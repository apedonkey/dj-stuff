# Builds GRAVEYARD SHIFT, the Halloween environment for Tribe XR, from the Blender output (Scripts/Blender/halloween/
# out_hw, made by hw_stage.py; plan: claudedocs/halloween_stage_plan.md in the tribe hack repo). Run with the Meta fork
# editor on the Halloween project copy (its cooks never touch the Dino or club sessions' Saved/Cooked):
#   D:\MetaUE54\Engine\Binaries\Win64\UnrealEditor.exe D:\TribeUE\MetaHw\TribeXR\TribeXR.uproject
#       -ExecutePythonScript="<this file>" -unattended -nosplash -nullrhi -abslog=<log>
# (D:\TribeUE\MetaHw\TribeXR\Scripts\cook_halloween.sh build does exactly that; HW_ANIM=1 for the animated build.)
#
# Stock build (default): every surface is an instance of a material Tribe ships (its unlit glTFRuntime material with the
# light baked in Blender; its two-sided alpha-blended one for beams, halos and lasers), so no shader of ours ships; the
# show is frozen and the animated-only meshes (lightning bolts, flame jets, fog, ghosts) stay out.
# Animated build (HW_ANIM=1): our own materials (Scripts/hw_materials.py, compiled by the fork; their shaders ship in
# chunk 54's ShaderArchive): the set lit by the show, beams and lasers on their cue rows, sweeping lasers, lightning,
# fog, flame jets, bats, ghosts, the rising hands, the turning clock, the dancing VAT crowd.
# Every actor has collision OFF: set_collision_profile_name clears bUseDefaultCollision, which otherwise re-enables the
# mesh's BlockAll at load and swallows Tribe's menu pointer ray (NOTES.md Session 3q). Content lives under
# /Game/Mods/Halloween, labeled into pak chunk 54. Helpers follow build_dino.py / build_club.py (copied: build_dino.py runs
# its build at import).
# v3 (2026-10-09): the show follows the music. MPC_HwShow (/Game/Mods/Halloween/MaterialInstances/MPC_HwShow) is the
# hook's show bus (dumper.cpp, the Dino session's: it finds the active stage's MPC and writes the song's bars, variant,
# hits, bass and drops); hw_materials.SHOW_MPC puts the whole show on it, and the lasers run on the Dino's pattern engine
# (dino_materials.laser_show, imported and never edited, as build_club.py does) with the Dino's show.py tables
# (T_HwLaserProg / T_HwLaserLib / T_HwLaserCues, written by hw_stage.py). Darker floors for the set (the user: "a lot
# darker out").
import glob
import inspect
import json
import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "Blender", "halloween", "intro"))
ROOT = os.environ.get("HW_ROOT", "/Game/Mods/Halloween")
MAPS, MI, TEX, MESH = ROOT + "/Maps", ROOT + "/MaterialInstances", ROOT + "/Textures", ROOT + "/Meshes"
MAT = ROOT + "/Materials"
LEVEL = MAPS + "/Environment_Halloween"
CHUNK_ID = int(os.environ.get("HW_CHUNK", "54"))
ANIMATED = os.environ.get("HW_ANIM") == "1"
UNLIT_PARENT = "/glTFRuntime/M_Unlit_glTFRuntimeBase"
UNLIT_2SIDED_PARENT = "/glTFRuntime/M_Unlit_glTFRuntimeTwoSided_Inst"
UNLIT_2SIDED_TRANSLUCENT_PARENT = "/glTFRuntime/M_Unlit_glTFRuntimeTwoSidedTranslucent_Inst"   # alpha = texture alpha
PARENTS = (UNLIT_PARENT, UNLIT_2SIDED_PARENT, UNLIT_2SIDED_TRANSLUCENT_PARENT)
NO_MIPS = {"T_HwGlowPal", "T_HwGroundsPal", "T_HwCues", "T_HwLaserProg", "T_HwLaserLib", "T_HwLaserCues"}   # lookups
DATA_TEX = {"T_HwCues", "T_HwLaserProg", "T_HwLaserLib", "T_HwLaserCues"}   # linear data (the show's tables): sRGB off
# the factories taken from dino_materials (the Dino session's): checked first, so a change there stops this build with a
# clear message instead of a half-built level
NEEDS = {"make_mpc": ("folder", "name", "scalars"), "laser_show": ("name", "folder", "texture", "cues", "prog", "lib")}
# the hook's show bus writes these by name (dumper.cpp, the Dino session's order); ours come after them
SHOW_NAMES = ("Height", "RobeTopX", "RobeTopY", "RobeTopZ", "RobeOn", "ButtonGlow", "ShowLevel", "ShowOffset", "SpotOn",
              "TopLasers", "LaserVariant", "HitMajor", "HitMinor", "HitCount", "DropBoom", "HitsOn", "Bass")
SHOW_EXTRAS = {"PlayerX": 1.0e6, "PlayerY": 1.0e6,     # v7: the player's head (hook/club.cpp), the crowd makes way
               "ShowPrevBar": -1.0, "ShowNextBar": -1.0,  # the bars around the current one when the hook sends them
               "IntroStep": 0.0, "DoorOpen": 1.0}          # the stream intro (v4): its step; the door 0 shut..1 open
                                                           # (open when no intro runs: the mod shuts it for the pre-show)
                                                           # (song mode loops sections); -1 = use the show clock's
SRC = os.environ.get("HW_SRC") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "Blender", "halloween", "out_hw")
ANIM_ONLY = {"SM_HwBolts", "SM_HwFire", "SM_HwFog", "SM_HwGhosts"}   # frozen they would look wrong: animated build only
VAT_MESHES = ("SM_HwCrowd", "SM_HwPhones")
CLOCK_CENTER = (0.0, 13.7, 20.0)                            # hw_stage.build_clock, Blender m (final frame)
CUE = {"stage": 0, "wash": 1, "search": 2, "lenses": 10, "windows": 11, "eyes": 15, "always": 13}   # hw_show.CUE_ROWS

# mesh -> (material instance name, parent, texture png or None, flat color or None): the stock look (and the fallback)
SURFACES = {
    "SM_HwFacade": ("MI_HwFacade", UNLIT_PARENT, "T_HwFacade", None),
    "SM_HwFacadeDetail": ("MI_HwFacadeDetail", UNLIT_PARENT, "T_HwFacadeDetail", None),
    "SM_HwDeck": ("MI_HwDeck", UNLIT_PARENT, "T_HwDeck", None),
    "SM_HwRig": ("MI_HwRig", UNLIT_PARENT, "T_HwRig", None),
    "SM_HwHands": ("MI_HwHands", UNLIT_PARENT, "T_HwHands", None),
    "SM_HwGlow": ("MI_HwGlow", UNLIT_PARENT, "T_HwGlowPal", None),
    "SM_HwWindows": ("MI_HwWindows", UNLIT_PARENT, "T_HwGlowPal", None),
    "SM_HwEyes": ("MI_HwEyes", UNLIT_PARENT, "T_HwGlowPal", None),
    "SM_HwLenses": ("MI_HwLenses", UNLIT_PARENT, "T_HwGlowPal", None),
    "SM_HwClockFace": ("MI_HwClockFace", UNLIT_PARENT, "T_HwGlowPal", None),
    "SM_HwClockHands": ("MI_HwClockHands", UNLIT_PARENT, "T_HwGlowPal", None),
    "SM_HwBats": ("MI_HwBats", UNLIT_2SIDED_PARENT, "T_HwGlowPal", None),
    "SM_HwGroundsGlow": ("MI_HwGroundsGlow", UNLIT_PARENT, "T_HwGroundsPal", None),
    "SM_HwGate": ("MI_HwGate", UNLIT_PARENT, "T_HwGate", None),          # v5: the crypt doors (shut when stock)
    "SM_HwButton": ("MI_HwButton", UNLIT_PARENT, "T_HwGlowPal", None),   # v4: the backstage button
    "SM_HwRider": ("MI_HwRider", UNLIT_PARENT, "T_HwRider", None),       # v4: the intro's Horseman (VAT when animated)
    "SM_HwHinged": ("MI_HwHinged", UNLIT_PARENT, "T_HwHinged", None),     # coffin lids, the jaw: closed when stock
    # the big screen: the mod finds it by this MESH name (dumper.cpp em_register_backdrop) and registers it as Tribe's
    # backdrop; Tribe then puts its own video material on it. Black until then.
    "SM_DinoVisualScreen": ("MI_HwVisualScreen", UNLIT_PARENT, None, (0.0, 0.0, 0.0)),
    "SM_HwGround": ("MI_HwGround", UNLIT_PARENT, "T_HwGround", None),
    "SM_HwFarGround": ("MI_HwFar", UNLIT_PARENT, None, (0.0015, 0.0015, 0.0025)),   # v3: hw_stage.FAR_RGB
    "SM_HwSky": ("MI_HwSky", UNLIT_2SIDED_PARENT, "T_HwSky", None),
    "SM_HwMoon": ("MI_HwMoon", UNLIT_PARENT, "T_HwMoon", None),
    "SM_HwCrowd": ("MI_HwCrowd", UNLIT_PARENT, "T_HwCrowd", None),
    "SM_HwPhones": ("MI_HwPhones", UNLIT_PARENT, None, (0.9, 0.55, 0.25)),
    "SM_HwBeams": ("MI_HwBeams", UNLIT_2SIDED_TRANSLUCENT_PARENT, "T_HwBeam", None),
    "SM_HwHalos": ("MI_HwHalos", UNLIT_2SIDED_TRANSLUCENT_PARENT, "T_HwHalo", None),
    "SM_HwLasers": ("MI_HwLasers", UNLIT_2SIDED_TRANSLUCENT_PARENT, "T_HwBeam", None),
    "SM_HwSearch": ("MI_HwSearch", UNLIT_2SIDED_TRANSLUCENT_PARENT, "T_HwBeam", None),
    "SM_HwBolts": ("MI_HwBolts", UNLIT_2SIDED_TRANSLUCENT_PARENT, "T_HwBeam", None),
    "SM_HwFire": ("MI_HwFire", UNLIT_2SIDED_TRANSLUCENT_PARENT, "T_HwFire", None),
    "SM_HwFog": ("MI_HwFog", UNLIT_2SIDED_TRANSLUCENT_PARENT, "T_HwFogNoise", None),
    "SM_HwGhosts": ("MI_HwGhosts", UNLIT_2SIDED_TRANSLUCENT_PARENT, None, (0.55, 1.0, 0.65)),
}
for _fbx in sorted(glob.glob(os.path.join(SRC, "SM_HwGrounds*.fbx"))):        # one baked mesh per grounds module
    _n = os.path.splitext(os.path.basename(_fbx))[0]
    if _n not in SURFACES:
        SURFACES[_n] = ("MI" + _n[2:], UNLIT_PARENT, "T_HwGroundsPal" if _n.startswith("SM_HwGroundsGlow")
                        else "T" + _n[2:], None)                         # OWN_GLOW modules: SM_HwGroundsGlow<Name>
for _pat, _tex in (("SM_HwGBeams*.fbx", "T_HwGroundsBeam"), ("SM_HwGHalos*.fbx", "T_HwGroundsHalo")):
    for _fbx in sorted(glob.glob(os.path.join(SRC, _pat))):                   # the modules' beam / halo groups
        _n = os.path.splitext(os.path.basename(_fbx))[0]
        SURFACES[_n] = ("MI" + _n[2:], UNLIT_2SIDED_TRANSLUCENT_PARENT, _tex, None)
_MANIFEST = os.path.join(SRC, "manifest.txt")             # hw_stage.py lists what it exported: build exactly that
_listed = [l.strip() for l in open(_MANIFEST) if l.strip()]
if os.path.exists(os.path.join(SRC, "SM_HwRider.fbx")) and os.path.exists(os.path.join(SRC, "T_HwRiderVAT.json")):
    _listed.append("SM_HwRider")                                          # intro/hw_rider.py --export writes it
# actors the mod finds by OBJECT name (labels are editor-only): the intro moves the rider, hides the woods off-intro
MOD_NAMES = {"SM_HwRider": "HwRider", "SM_HwGroundsWoods": "HwWoods", "SM_HwGroundsGlowWoods": "HwWoodsGlow"}
PARKED = {"SM_HwRider": (0.0, 0.0, -5000.0)}                              # out of sight until the intro moves it
_missing = sorted(set(_listed) - set(SURFACES))
if _missing:
    raise RuntimeError(f"manifest meshes without a SURFACES entry: {_missing}")
SURFACES = {k: v for k, v in SURFACES.items() if k in _listed and (ANIMATED or k not in ANIM_ONLY)}
GROUPS = json.load(open(os.path.join(SRC, "hw_groups.json"))) if os.path.exists(os.path.join(SRC, "hw_groups.json")) else {}
# Two small lamps over the decks, as on the Dino Stage (the user, v6.2: "a small light on the decks, not for the entire
# stage"); tribemod/lights.txt scales them by name. Tribe world cm: the mixer measured x -25..15, y 15..63, z 75..87.
DECK_LAMPS = (("HwDeckLamp_L", (-45.0, 40.0, 150.0)), ("HwDeckLamp_R", (35.0, 40.0, 150.0)))

eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
level_ss = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actor_ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def log(msg):
    unreal.log("[HW] " + msg)


def check_rider_uvs(mesh, meta):
    """v6: read back what the FBX import stored on the rider's VAT data channels. UV1.y must be the band (whole numbers
    0 .. bands-1) and UV2 (1, 0); a missing V-flip pre-compensation (v4/v5's bug) reads 1 - band and (1, 1). Stops the
    build when wrong; only logs when this editor can't read the UVs (hw_rider.py's ue_decode check still ran)."""
    try:
        md = mesh.get_static_mesh_description(0)
        n = md.get_vertex_instance_count()
        bands, rot = set(), set()
        for i in range(0, n, max(1, n // 600)):
            vi = unreal.VertexInstanceID()
            vi.set_editor_property("id_value", i)
            u1, u2 = md.get_vertex_instance_uv(vi, 1), md.get_vertex_instance_uv(vi, 2)
            bands.add(round(u1.y, 3))
            rot.add((round(u2.x, 3), round(u2.y, 3)))
    except Exception as e:  # noqa: BLE001
        log(f"rider VAT UVs: read-back unavailable here ({e}); relying on hw_rider.py's ue_decode check")
        return
    if not all(b == int(b) and 0 <= b < meta["bands"] for b in bands) or rot != {(1.0, 0.0)}:
        raise RuntimeError(f"SM_HwRider: VAT UVs read back wrong: bands {sorted(bands)[:8]}, VatRotScale {sorted(rot)[:4]}")
    log(f"rider VAT UVs read back as meant: bands {sorted(int(b) for b in bands)}, VatRotScale (1, 0)")


def check_crowd_pivots(mesh):
    """v7: read back the crowd's UV5 VatPivot (the dancer's root, Blender m, written pre-flipped for Unreal's 1 - V).
    The field crowd stands at y -8.6 .. -66, so most roots must read y < 0; a missing flip pre-compensation reads
    1 - y (all positive), and the make-way would push every dancer from the wrong place. Stops the build when wrong."""
    try:
        md = mesh.get_static_mesh_description(0)
        n = md.get_vertex_instance_count()
        ys = []
        for i in range(0, n, max(1, n // 800)):
            vi = unreal.VertexInstanceID()
            vi.set_editor_property("id_value", i)
            ys.append(md.get_vertex_instance_uv(vi, 5).y)
    except Exception as e:  # noqa: BLE001
        log(f"{mesh.get_name()} pivots: read-back unavailable here ({e})")
        return
    neg = sum(1 for y in ys if y < -5.0) / max(1, len(ys))
    if neg < 0.8:
        raise RuntimeError(f"{mesh.get_name()}: UV5 VatPivot reads back wrong ({neg:.0%} of roots at y < -5 m; "
                           f"y {min(ys):.1f}..{max(ys):.1f})")
    log(f"{mesh.get_name()}: UV5 VatPivot reads back as meant ({neg:.0%} of roots in the field, y {min(ys):.1f}..{max(ys):.1f})")


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
    if name in VAT_MESHES:                                       # the crowd's glow parts carry their colors per vertex
        sm.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
    task = unreal.AssetImportTask()
    for k, v in (("filename", fbx), ("destination_path", MESH), ("destination_name", name), ("automated", True),
                 ("replace_existing", True), ("save", False), ("options", ui)):
        task.set_editor_property(k, v)
    tools.import_asset_tasks([task])
    mesh = unreal.load_asset(path)
    if mesh is None:
        raise RuntimeError("import failed: " + fbx)
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


def load_dino_materials():
    import dino_materials as dm
    for fn, params in NEEDS.items():
        f = getattr(dm, fn, None)
        if f is None:
            raise RuntimeError(f"dino_materials.{fn} is gone: adapt build_halloween.py")
        missing = [q for q in params if q not in inspect.signature(f).parameters]
        if missing:
            raise RuntimeError(f"dino_materials.{fn} lost parameters {missing}: adapt build_halloween.py")
    if tuple(getattr(dm, "GIANT_MPC_PARAMS", {}))[:len(SHOW_NAMES)] != SHOW_NAMES:
        raise RuntimeError("MPC_DinoGiant's names changed: the show bus writes by name, check SHOW_NAMES")
    return dm


def animated_materials(textures, meshes):
    """Our own materials (hw_materials.py) for every animated mesh: {mesh: material or instance}; plus the set of meshes
    whose components must always evaluate World Position Offset."""
    import hw_materials as hm
    if not eal.does_directory_exist(MAT):
        eal.make_directory(MAT)
    T = textures
    cues = T["T_HwCues"]
    out, wpo = {}, set()
    dm = load_dino_materials()
    if abs(dm.SHOW_LOOP_S - hm.SHOW_LOOP_S) > 1e-6:
        raise RuntimeError(f"show loops differ: Dino {dm.SHOW_LOOP_S} s, ours {hm.SHOW_LOOP_S} s (the bus has one clock)")
    params = {k: dm.GIANT_MPC_PARAMS[k] for k in SHOW_NAMES}
    params.update(SHOW_EXTRAS)
    mpc = dm.make_mpc(MI, "MPC_HwShow", params)               # before any material: they all read it
    dm.SHOW_MPC = hm.SHOW_MPC = mpc
    log(f"MPC_HwShow at {MI}/MPC_HwShow: {len(params)} scalars (ShowLevel default {params['ShowLevel']})")

    def inst(name, parent, scalars=None, texs=None):
        return hm.instance(name, MI, parent, scalars, texs)
    show = hm.show_lit("M_HwShowLit", MAT, T["T_HwFacade"], cues)
    for sm, tex, floor in (("SM_HwFacade", "T_HwFacade", 0.05), ("SM_HwFacadeDetail", "T_HwFacadeDetail", 0.05),
                           ("SM_HwDeck", "T_HwDeck", 0.06), ("SM_HwRig", "T_HwRig", 0.05)):   # v3: was 0.08 / 0.10
        if sm in meshes:
            out[sm] = inst("MI" + sm[2:] + "Show", show, {"Floor": floor}, {"Tex": T[tex]})
    cue_tex = hm.cue_tex("M_HwCueTex", MAT, T["T_HwGlowPal"], cues)
    for sm, row, floor, fl in (("SM_HwWindows", CUE["windows"], 0.15, 0.15), ("SM_HwEyes", CUE["eyes"], 0.10, 0.0),
                               ("SM_HwLenses", CUE["lenses"], 0.06, 0.0)):
        if sm in meshes:
            out[sm] = inst("MI" + sm[2:] + "Cue", cue_tex, {"CueRow": row, "Floor": floor, "Flicker": fl})
    if "SM_HwGlow" in meshes:
        out["SM_HwGlow"] = hm.flicker_tex("M_HwFlicker", MAT, T["T_HwGlowPal"], 0.2)
    if "SM_HwGroundsGlow" in meshes or any(m.startswith("SM_HwGroundsGlow") for m in meshes):
        gflick = hm.flicker_tex("M_HwGroundsFlicker", MAT, T["T_HwGroundsPal"], 0.15)   # lanterns, candles: a soft flicker
        for m in meshes:
            if m.startswith("SM_HwGroundsGlow"):
                out[m] = gflick
    if "SM_HwGate" in meshes:                                      # v5: the two crypt doors swing out on DoorOpen
        import hw_intro_path as ip
        out["SM_HwGate"] = hm.door_swing("M_HwGate", MAT, T["T_HwGate"], ip.GATE_X, ip.GATE_Y, ip.DOOR_OPEN_DEG,
                                         ip.DOOR_STAGGER)
        wpo.add("SM_HwGate")
    if "SM_HwButton" in meshes:
        out["SM_HwButton"] = hm.intro_button("M_HwButton", MAT)
    if "SM_HwClockFace" in meshes:
        out["SM_HwClockFace"] = hm.clock_face("M_HwClockFace", MAT)
    if "SM_HwClockHands" in meshes:
        out["SM_HwClockHands"] = hm.clock_hands("M_HwClockHands", MAT, CLOCK_CENTER)
        wpo.add("SM_HwClockHands")
    if "SM_HwHinged" in meshes:                                    # swing open with the hands row
        out["SM_HwHinged"] = hm.hinge_swing("M_HwHinged", MAT, T["T_HwHinged"], cues)
        wpo.add("SM_HwHinged")
    if "SM_HwBats" in meshes:
        out["SM_HwBats"] = hm.flock_orbit("M_HwBats", MAT, T["T_HwGlowPal"])
        wpo.add("SM_HwBats")
    if "SM_HwHands" in meshes:
        out["SM_HwHands"] = hm.rigid_rise("M_HwHands", MAT, T["T_HwHands"], cues)
        wpo.add("SM_HwHands")
    beams = hm.beams_material("M_HwBeams", MAT, T["T_HwBeam"], cues)
    for sm, row, tex in (("SM_HwBeams", CUE["stage"], "T_HwBeam"), ("SM_HwSearch", CUE["search"], "T_HwBeam"),
                         ("SM_HwHalos", CUE["lenses"], "T_HwHalo")):
        if sm in meshes:
            out[sm] = inst("MI" + sm[2:] + "Cue", beams, {"CueRow": row}, {"Tex": T[tex]})
    for sm in meshes:                                              # the modules' beam / halo groups
        if sm.startswith(("SM_HwGBeams", "SM_HwGHalos")):
            tex = "T_HwGroundsHalo" if sm.startswith("SM_HwGHalos") else "T_HwGroundsBeam"
            out[sm] = inst("MI" + sm[2:] + "Cue", beams, {"CueRow": GROUPS.get(sm, CUE["always"])}, {"Tex": T[tex]})
    if "SM_HwLasers" in meshes:                                    # v3: the Dino's laser engine on our units
        for k in ("T_HwLaserProg", "T_HwLaserLib", "T_HwLaserCues"):
            if k not in T:
                raise RuntimeError(k + ".png missing: hw_stage.py v3 writes it")
        out["SM_HwLasers"] = hm.laser_near_fade(                    # v7: + fade within 80 cm of the eye (Reactor v8)
            dm.laser_show("M_HwLaserShow", MAT, T["T_HwBeam"], cues=T["T_HwLaserCues"], prog=T["T_HwLaserProg"],
                          lib=T["T_HwLaserLib"]), f"{MAT}/M_HwLaserShow")
        wpo.add("SM_HwLasers")
    if "SM_HwSky" in meshes:
        out["SM_HwSky"] = hm.lightning_sky("M_HwSky", MAT, T["T_HwSky"], cues)
    if "SM_HwBolts" in meshes:
        out["SM_HwBolts"] = hm.bolts("M_HwBolts", MAT, T["T_HwBeam"], cues)
    if "SM_HwFog" in meshes:
        out["SM_HwFog"] = hm.fog_sheet("M_HwFog", MAT, T["T_HwFogNoise"], cues,       # v7: a visible low fog
                                       rgb=(0.07, 0.075, 0.10), lit_floor=0.4)
    if "SM_HwFire" in meshes:
        out["SM_HwFire"] = hm.fire_card("M_HwFire", MAT, T["T_HwFire"], T["T_HwFogNoise"], cues)
    if "SM_HwGhosts" in meshes:
        out["SM_HwGhosts"] = hm.ghost_waver("M_HwGhosts", MAT)
        wpo.add("SM_HwGhosts")
    if "SM_HwMoon" in meshes:
        out["SM_HwMoon"] = hm.moon_clouds("M_HwMoon", MAT, T["T_HwMoon"], T["T_HwFogNoise"])
    rider_exr = os.path.join(SRC, "T_HwRiderVAT.exr")
    if "SM_HwRider" in meshes and os.path.exists(rider_exr):       # v4: the Horseman's gallop (the crowd's VAT format)
        fresh(f"{TEX}/T_HwRiderVAT")
        task = unreal.AssetImportTask()
        for k, v in (("filename", rider_exr), ("destination_path", TEX), ("destination_name", "T_HwRiderVAT"),
                     ("automated", True), ("replace_existing", True), ("save", False)):
            task.set_editor_property(k, v)
        tools.import_asset_tasks([task])
        rvat = hm.prepare_vat_texture(unreal.load_asset(f"{TEX}/T_HwRiderVAT"))
        eal.save_asset(f"{TEX}/T_HwRiderVAT")
        rmeta = json.load(open(os.path.join(SRC, "T_HwRiderVAT.json")))
        hm.prepare_vat_mesh(meshes["SM_HwRider"])
        eal.save_asset(f"{MESH}/SM_HwRider")
        check_rider_uvs(meshes["SM_HwRider"], rmeta)
        out["SM_HwRider"] = hm.vat_crowd("M_HwRiderVAT", MAT, rvat, rmeta, baked_texture=T["T_HwRider"], cues=None,
                                         two_sided=True)
        wpo.add("SM_HwRider")
        log(f"rider VAT {rvat.blueprint_get_size_x()}x{rvat.blueprint_get_size_y()}, {rmeta['frames_per_clip']} frames, "
            f"{rmeta['vertices']} verts")
    vat_exr = os.path.join(SRC, "T_HwCrowdVAT.exr")
    if "SM_HwCrowd" in meshes and os.path.exists(vat_exr):         # the dance (RGBA16F, exact)
        fresh(f"{TEX}/T_HwCrowdVAT")
        task = unreal.AssetImportTask()
        for k, v in (("filename", vat_exr), ("destination_path", TEX), ("destination_name", "T_HwCrowdVAT"),
                     ("automated", True), ("replace_existing", True), ("save", False)):
            task.set_editor_property(k, v)
        tools.import_asset_tasks([task])
        vat = hm.prepare_vat_texture(unreal.load_asset(f"{TEX}/T_HwCrowdVAT"))
        eal.save_asset(f"{TEX}/T_HwCrowdVAT")
        meta = json.load(open(os.path.join(SRC, "T_HwCrowdVAT.json")))
        log(f"crowd VAT {vat.blueprint_get_size_x()}x{vat.blueprint_get_size_y()}, {meta.get('frames_per_clip')} frames/clip")
        n_uv = len(meta.get("uv_channels", {})) or 5                  # v7: 6 with UV5 VatPivot (the make-way)
        for sm in VAT_MESHES:
            hm.prepare_vat_mesh(meshes[sm], uv_channels=n_uv)
            if n_uv > 5:
                check_crowd_pivots(meshes[sm])
            eal.save_asset(f"{MESH}/{sm}")
            wpo.add(sm)
        out["SM_HwCrowd"] = hm.vat_crowd("M_HwCrowdVAT", MAT, vat, meta, baked_texture=T["T_HwCrowd"], cues=cues,
                                         make_way=True)                       # v7: free roam, the dancers part
        out["SM_HwPhones"] = hm.vat_crowd("M_HwCrowdGlowVAT", MAT, vat, meta, glow=True, make_way=True)
    for sm, n_uv, pad in (("SM_HwLasers", 6, 4000.0), ("SM_HwBats", 4, 2000.0), ("SM_HwGhosts", 4, 900.0),
                          ("SM_HwClockHands", 2, 300.0), ("SM_HwHands", 1, 1300.0), ("SM_HwHinged", 5, 300.0),
                          ("SM_HwGate", 2, 400.0)):
        if sm in meshes:
            hm.prepare_wpo_mesh(meshes[sm], n_uv, pad)
            eal.save_asset(f"{MESH}/{sm}")
    log(f"animated: {len(out)} meshes on our materials; WPO on {sorted(wpo)}")
    return out, wpo


def build():
    for parent in PARENTS:
        if not eal.does_asset_exist(parent):
            raise RuntimeError(parent + " stub missing (the project's Plugins/glTFRuntime holds the stand-ins)")
    parents = {p: unreal.load_asset(p) for p in PARENTS}
    textures = {}
    for png in sorted(glob.glob(os.path.join(SRC, "T_Hw*.png"))):
        name = os.path.splitext(os.path.basename(png))[0]
        textures[name] = import_texture(png, name)
    meshes, mats = {}, {}
    for sm_name, (mi_name, parent_path, tex, color) in SURFACES.items():
        meshes[sm_name] = import_mesh(os.path.join(SRC, sm_name + ".fbx"), sm_name)
        mats[sm_name] = instance(mi_name, parents[parent_path], {"baseColorFactor": color} if color else None,
                                 {"baseColorTexture": textures[tex]} if tex else None)
    wpo = set()
    if ANIMATED:
        anim, wpo = animated_materials(textures, meshes)
        mats.update(anim)
    chunk_label()

    # Blender models the cathedral BEHIND the DJ (+Y). The FBX import converts handedness by flipping Y, so the screen
    # comes in at -Y: turn the level around (as for Dino and the club; the DJ's right stays the DJ's right).
    sy = meshes["SM_DinoVisualScreen"].get_bounds().origin.y
    yaw = 180.0 if sy < 0 else 0.0
    fb = meshes["SM_HwFacade"].get_bounds()
    log(f"orientation: screen centre y={sy:.0f} cm -> level yaw {yaw:.0f}; facade extent "
        f"({fb.box_extent.x * 2:.0f} x {fb.box_extent.y * 2:.0f} x {fb.box_extent.z * 2:.0f} cm); "
        f"{'ANIMATED' if ANIMATED else 'stock'} build")

    if eal.does_asset_exist(LEVEL):
        eal.delete_asset(LEVEL)
    if not level_ss.new_level(LEVEL):
        raise RuntimeError("new_level failed for " + LEVEL)
    for sm_name, mesh in meshes.items():
        actor = actor_ss.spawn_actor_from_object(mesh, unreal.Vector(*PARKED.get(sm_name, (0.0, 0.0, 0.0))),
                                                 unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        actor.set_actor_label(sm_name.replace("SM_", ""))
        if sm_name in MOD_NAMES:                                    # the intro's actors: a unique object name
            try:
                actor.rename(MOD_NAMES[sm_name])
            except Exception as e:  # noqa: BLE001
                log(f"rename {sm_name} -> {MOD_NAMES[sm_name]} failed ({e}); it keeps {actor.get_name()}")
            actor.set_actor_label(MOD_NAMES[sm_name])
            actor.set_actor_hidden_in_game(True)                    # the mod shows them for the intro (the Dino
            log(f"intro actor {actor.get_name()} ({sm_name}), hidden in game")   # session: no mod = no cost)
        comp = actor.static_mesh_component
        comp.set_mobility(unreal.ComponentMobility.MOVABLE)
        for slot in range(max(1, comp.get_num_materials())):
            comp.set_material(slot, mats[sm_name])
        comp.set_collision_profile_name("NoCollision")
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        comp.set_editor_property("cast_shadow", False)
        if sm_name in wpo:                                          # WPO always evaluated, never distance-disabled
            comp.set_editor_property("evaluate_world_position_offset", True)
            comp.set_editor_property("world_position_offset_disable_distance", 0)
        if comp.get_editor_property("use_default_collision"):
            raise RuntimeError(sm_name + ": collision still on")
    for lname, pos in DECK_LAMPS:                                   # deck lamps (Tribe's gear is lit; our set is not)
        la = actor_ss.spawn_actor_from_class(unreal.SpotLight, unreal.Vector(*pos), unreal.Rotator(roll=0.0, pitch=-90.0, yaw=0.0))
        lc = la.get_component_by_class(unreal.SpotLightComponent)
        lc.set_mobility(unreal.ComponentMobility.MOVABLE)
        for k, v in (("intensity_units", unreal.LightUnits.CANDELAS), ("intensity", 3.0), ("attenuation_radius", 140.0),
                     ("outer_cone_angle", 38.0), ("inner_cone_angle", 20.0), ("cast_shadows", False),
                     ("light_color", unreal.Color(r=255, g=225, b=190, a=255))):
            lc.set_editor_property(k, v)
        try:
            la.rename(lname)                                        # lights.txt matches by name
        except Exception as e:  # noqa: BLE001
            log(f"deck lamp rename failed ({e}); it keeps {la.get_name()}")
        la.set_actor_label(lname)
        log(f"deck lamp {la.get_name()} at {pos}")
    if not level_ss.save_current_level():
        raise RuntimeError("save_current_level failed")
    log(f"saved {LEVEL} ({len(meshes)} actors + {len(DECK_LAMPS)} lamps)")
    log("done")


try:
    build()
except Exception as e:
    unreal.log_error("[HW] FAILED: " + repr(e))
finally:
    unreal.SystemLibrary.quit_editor()
