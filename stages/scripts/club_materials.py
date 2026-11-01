"""REACTOR's own material factories (the club session's; Unreal editor Python in the Meta fork). Built on dino_materials.py
(the Dino session's: imported read only for its graph builder G, cue_level, show_mpc, connect_wpo and the VAT helpers;
never edited from here). build_club.py sets dm.SHOW_MPC = MPC_ClubShow before any factory runs, so everything here
reads the show bus that the hook drives (dumper.cpp show bus: the song's bars, hits, drops and bass).

  club_crowd()   the dancing crowd, v2 (2026-10-09, the user: "improve the quality of the crowd ... be able to walk in the
                 crowd"): crisp clothes (the vertex colour, decoded from sRGB) x the light-only bake (T_ClubCrowdLight,
                 smooth) x the show's wash, plus a rim lit in the show's colours (blue wash, amber heads, brighter on the
                 song's hits); dancing on the show clock (Time + ShowOffset: the song's beat once the hook drives it);
                 making way: each dancer is pushed away from the player as a whole (UV5 = the dancer's root, PlayerX /
                 PlayerY in MPC_ClubShow from hook/club.cpp)
  club_lit()     the baked room and stage, lit by the show's wash, x the dark-club dimmers RoomGain / StageGain (v6)
  mover_beams(), mover_lens(), mover_heads()   v7: the moving heads move (beams, halos, lenses, yokes + heads carry
                 their fixture's data; dm._mover_wpo, the Dino's v13 engine, on the club's laser program); every beam
                 fades out within 1.5 m of the eye (near_fade)
  lenses(), core_glow(), beams(), laser_lines()   the Dino show factories with the song's hits: lenses flash on
                 HitMajor, beams swell on hits and boom on drops, the core breathes with Bass, the laser lines pulse with
                 Bass and boom on drops (the sweeping laser engine comes later)
  laser_show()   v8: the sweeping lasers (the Dino's engine, dm.laser_show) with two club additions: the part of a beam
                 past a mezzanine deck's top is clipped (lids_keep; the beams now run on to the floor), and the beams fade
                 out within 80 cm of the eye (near_fade)
Comfort (the user finds flashing too much): the hook's hits come at most once a beat and decay in 0.15 s, so at 140 BPM a
light can't flash more than ~2.3 times a second (the rule is 3); DropBoom falls over 1.2 s; nothing here strobes.

Vertex colours: Blender's FBX export writes Col sRGB-encoded (io_scene_fbx default), Unreal's FBX import decodes it to
linear, and the static mesh build stores it sRGB-encoded again (MeshBuilder/StaticMeshBuilder.cpp: ToFColor(true));
the material reads that byte as-is, so the albedo is VertexColor ^ ColGamma (2.2, a parameter)."""
import unreal

import dino_materials as dm

M = unreal
mel = unreal.MaterialEditingLibrary
BLUE, AMBER = (0.10, 0.45, 1.0), (1.0, 0.55, 0.05)      # club_venue_plan.md: Cherenkov blue, hazard amber
HEADS_ROW = 0                                            # club_show.CUE_ROWS["heads"]


def mpc(g, pname):
    if dm.SHOW_MPC is None:
        raise RuntimeError("club_materials: dm.SHOW_MPC (MPC_ClubShow) must be set first")
    return dm.show_mpc(g, pname)


def show_time(g):
    """Time + ShowOffset: the club's show clock (the hook rewrites ShowOffset every frame to sit on the song's bars)."""
    return g.add(g.time(), mpc(g, "ShowOffset"))


def boost(g, major=0.0, minor=0.0, drop=0.0):
    """1 + major * HitMajor + minor * HitMinor + drop * DropBoom (each 0..1 from the hook; 0 without a song)."""
    e = g.const(1.0)
    for k, pname in ((major, "HitMajor"), (minor, "HitMinor"), (drop, "DropBoom")):
        if k:
            e = g.add(e, g.mul(mpc(g, pname), k=k))
    return e


def bass_factor(g, depth):
    """1 + HitsOn * depth * (2 Bass - 1): the track's bass swings a level by +-depth while a song map is in force."""
    return g.add(g.mul(mpc(g, "HitsOn"), g.mul(g.add(g.mul(mpc(g, "Bass"), k=2.0), k=-1.0), k=depth)), k=1.0)


# The dark club (the user, 2026-10-09: "it needs to be WAY darker in there in the crowd and on stage. not as much on stage
# though. its supposed to be a dark club"): four dimmers in MPC_ClubShow, defaults in build_club.CLUB_EXTRAS (the pak's
# look); the hook can override each live from tribemod/club.txt (room= stage= crowd= rim=). The light sources themselves
# (beams, halos, lasers, lenses, LED strips, phones, the screens) are not dimmed: in a dark club they are the light.
ROOM_FLOOR, STAGE_FLOOR, CROWD_FLOOR = 0.05, 0.06, 0.04     # the share of the baked light left between the wash's hits


def club_lit(name, folder, texture, cues, gain="RoomGain", floor=ROOM_FLOOR):
    """A baked surface of the club lit only by the show: texture x (floor .. 1 by the wash row) x the MPC dimmer (RoomGain
    for the room, StageGain for the stage). The club's own copy of dm.show_lit, so the Dino's night tuning
    (dm.NIGHT_GAIN) never changes the club."""
    g = dm.G(name, folder)
    lvl = g.add(g.mul(dm.cue_level(g, cues, g.const(dm.WASH_ROW)), k=1.0 - floor), k=floor)
    g.emissive(g.mul(g.mul(g.tex(texture), lvl), mpc(g, gain)))
    return g.save()


def lenses(name, folder, texture, cues, row=10):
    """Fixture lenses: the show's lens row (dm.strobe_tex with cues), flashing brighter on the song's hits."""
    g = dm.G(name, folder)
    lvl = g.add(g.mul(dm.cue_level(g, cues, g.const(row)), k=0.94), k=0.06)
    g.emissive(g.mul(g.mul(g.tex(texture), lvl), boost(g, major=0.8, minor=0.3)))
    return g.save()


def core_glow(name, folder, texture, cues, row=2):
    """The core's rings: the show's core row, breathing with the track's bass (+-30 %)."""
    g = dm.G(name, folder)
    lvl = g.add(g.mul(dm.cue_level(g, cues, g.const(row)), k=0.94), k=0.06)
    g.emissive(g.mul(g.mul(g.tex(texture), lvl), bass_factor(g, 0.3)))
    return g.save()


def near_fade(g, start_cm=30.0, full_cm=150.0):
    """0 at the eye .. 1 from full_cm away (v7): a beam swept through your head never fills the view (VR comfort)."""
    dist = g.n(M.MaterialExpressionDistance)
    g.link(g.n(M.MaterialExpressionCameraPositionWS), dist, "A")
    g.link(g.n(M.MaterialExpressionWorldPosition), dist, "B")
    return dm._sat(g, g.mul(g.add(dist, k=-start_cm), k=1.0 / (full_cm - start_cm)))


def _beams(name, folder, texture, cues, hit, drop, bass, prog=None, lib=None):
    """Beams and halos: the texture, breathing on the show clock, the cue row CueRow, hits and drops, faded near the eye.
    prog + lib (v7): the moving heads' move (dm._mover_wpo, the Dino's v13 mover engine on the club's laser program)."""
    g = dm.G(name, folder, translucent=True, two_sided=True)
    s_ = g.tex(texture)
    ph = g.add(g.mul(show_time(g), k=dm.BEAT_HZ / 4), g.mul(g.world("x"), k=0.0008))     # breathing on the show clock
    lvl = g.mul(g.wave01(ph, 0.65, 1.0), dm.cue_level(g, cues, g.param("CueRow", 13)))
    lvl = g.mul(g.mul(lvl, boost(g, major=hit, drop=drop)), near_fade(g))
    if bass:
        lvl = g.mul(lvl, bass_factor(g, bass))
    op = g.n(M.MaterialExpressionMultiply)
    g.link(s_, op, "A", out="A")
    g.link(lvl, op, "B")
    g.emissive(s_, "RGB")
    g.opacity(op)
    if prog is not None:
        dm._mover_wpo(g, prog, lib)
    return g.save()


def mover_beams(name, folder, texture, cues, prog, lib):
    """v7: the moving heads' beams and halos (SM_ClubBeams* / SM_ClubHalos*): beams() that move with their fixture."""
    return _beams(name, folder, texture, cues, hit=0.5, drop=0.6, bass=0.0, prog=prog, lib=lib)


def mover_lens(name, folder, texture, cues, prog, lib, row=10):
    """v7: the moving heads' lenses (SM_ClubLenses): lenses() that move with their fixture."""
    g = dm.G(name, folder)
    lvl = g.add(g.mul(dm.cue_level(g, cues, g.const(row)), k=0.94), k=0.06)
    g.emissive(g.mul(g.mul(g.tex(texture), lvl), boost(g, major=0.8, minor=0.3)))
    dm._mover_wpo(g, prog, lib)
    return g.save()


def mover_heads(name, folder, prog, lib, rgb=(0.035, 0.036, 0.04)):
    """v7: the moving heads' yokes and heads (SM_ClubMoverHeads): dark unlit metal (dims with the show) that moves."""
    g = dm.G(name, folder)
    g.emissive(dm.show_dim(g, g.color(rgb)))
    dm._mover_wpo(g, prog, lib)
    return g.save()


def beams(name, folder, texture, cues):
    """Moving-head beams and halos (one material, CueRow per instance): swell on hits, boom on drops."""
    return _beams(name, folder, texture, cues, hit=0.5, drop=0.6, bass=0.0)


def laser_lines(name, folder, texture, cues):
    """The laser lines (static until the sweeping engine is ported): pulse with the bass, boom on drops."""
    return _beams(name, folder, texture, cues, hit=0.3, drop=0.8, bass=0.4)


# v8 (2026-10-11, the user: "yeah let them hit the floor"): the sweeping lasers run on to the floor (club_lasers.py v8)
LASER_NEAR = (20.0, 80.0)    # near_fade for the lasers: thin lines, so a tighter fade than the moving heads' wide beams
                             # (30..150 cm) and a beam passing over your head stays lit


class _Extend(dm.G):
    """dm.G bound to a material that a dm factory already built and saved (no delete, no create), to add to its graph."""

    def __init__(self, mat, path):  # noqa: the base __init__ would delete and recreate the asset
        self.m, self.path, self.x = mat, path, 400


def lids_keep(g, lids):
    """0 where the line from the laser's aperture down to this pixel went through the top of one of lids, else 1.
    lids: (x0, x1, y0, y1, z top) in the club frame, Blender m (club_lasers.LIDS: the mezzanine decks). A beam is one fixed
    length and runs on past where it lands; the floor and the walls hide the rest, but a deck would let it out of its
    underside into the lounge. The aperture comes from the beam's data as dm.laser_show reads it (UV1 = x and y, V read back
    as 1 - v; UV2 = z), in mesh local cm = (x, -y, z) * 100, so the pixel goes to local cm too (the level actor's turn)."""
    tc1, tc2 = (g.n(M.MaterialExpressionTextureCoordinate, coordinate_index=i) for i in (1, 2))
    frag = g.n(M.MaterialExpressionTransformPosition,
               transform_source_type=M.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD,
               transform_type=M.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
    g.link(g.n(M.MaterialExpressionWorldPosition), frag)
    code = ["float3 P = float3(UV1.x * 100.0, (1.0 - UV1.y) * -100.0, UV2.x * 100.0);", "float keep = 1.0;"]
    for x0, x1, y0, y1, z in lids:                   # local cm: x * 100, -y * 100 (the y range flips), z * 100
        zc = f"{z * 100.0:.3f}"
        code += [f"if (P.z > {zc} && Frag.z < {zc})",
                 "{",
                 f"    float2 c = P.xy + ({zc} - P.z) / (Frag.z - P.z) * (Frag.xy - P.xy);",
                 f"    if (c.x >= {x0 * 100.0:.3f} && c.x <= {x1 * 100.0:.3f} && c.y >= {-y1 * 100.0:.3f} && "
                 f"c.y <= {-y0 * 100.0:.3f}) keep = 0.0;",
                 "}"]
    code.append("return keep;")
    c = g.n(M.MaterialExpressionCustom)
    c.set_editor_property("code", "\n".join(code))
    c.set_editor_property("output_type", M.CustomMaterialOutputType.CMOT_FLOAT1)
    c.set_editor_property("description", "LaserLids")
    ins = []
    for nm in ("UV1", "UV2", "Frag"):
        ci = M.CustomInput()
        ci.set_editor_property("input_name", nm)
        ins.append(ci)
    c.set_editor_property("inputs", ins)
    for nm, src in (("UV1", tc1), ("UV2", tc2), ("Frag", frag)):
        g.link(src, c, nm)
    return c


def laser_show(name, folder, texture, cues, prog, lib, lids=()):
    """v8: the Dino's laser engine (dm.laser_show, untouched) with its emissive x near_fade(LASER_NEAR) x lids_keep(lids):
    a beam swept through your head never fills the view, and none comes out of a mezzanine deck's underside."""
    mat = dm.laser_show(name, folder, texture, cues=cues, prog=prog, lib=lib)
    g = _Extend(mat, f"{folder}/{name}")
    prop = M.MaterialProperty.MP_EMISSIVE_COLOR
    src = mel.get_material_property_input_node(mat, prop)
    if src is None:
        raise RuntimeError(g.path + ": dm.laser_show left no emissive input to extend")
    e = g.n(M.MaterialExpressionMultiply)
    g.link(src, e, "A", out=mel.get_material_property_input_node_output_name(mat, prop))
    k = near_fade(g, *LASER_NEAR)
    if lids:
        k = g.mul(k, lids_keep(g, lids))
    g.link(k, e, "B")
    g.emissive(e)
    return g.save()


def club_crowd(name, folder, vat_texture, meta, light_texture=None, cues=None, glow=False, light_gain=1.0,
               push_cm=55.0, reach_cm=110.0):
    """The crowd (SM_ClubCrowd) or its glowing bits (glow=True, SM_ClubPhones). meta = T_ClubCrowdVAT.json. The VAT graph
    is dm.vat_crowd's (same UV channels, AxisScale, Transform), clocked by the show and offset by the make-way push."""
    g = dm.G(name, folder)

    def par(pname, value):
        return g.n(M.MaterialExpressionScalarParameter, parameter_name=pname, default_value=float(value))

    def mask(src, ch):
        return g.link(src, g.n(M.MaterialExpressionComponentMask, r=ch == "r", g=ch == "g", b=ch == "b", a=False))

    def op(cls, a, b, **kw):
        e = g.n(cls, **kw)
        if a is not None:
            g.link(a, e, "A")
        if b is not None:
            g.link(b, e, "B")
        return e
    if meta.get("uv_channels", {}).get("UV5 VatPivot") is None:
        raise RuntimeError(name + ": the VAT json has no UV5 VatPivot (bake with club_crowd.py)")
    tc = [g.n(M.MaterialExpressionTextureCoordinate, coordinate_index=i) for i in (1, 2, 3, 4, 5)]
    vid, clip = mask(tc[0], "r"), mask(tc[0], "g")
    c, s = mask(tc[1], "r"), mask(tc[1], "g")
    msz, phase = mask(tc[2], "r"), mask(tc[2], "g")
    rate = mask(tc[3], "r")
    pvx, pvy = mask(tc[4], "r"), mask(tc[4], "g")
    t = show_time(g)
    loops = par("LoopRate", 140.0 / (60.0 * meta["beats_per_clip"]))  # 1 loop = 2 beats of the show clock (140 BPM)
    p = g.frac(g.add(g.mul(g.mul(t, loops), rate), phase))
    f = g.mul(p, par("FramesPerClip", meta["frames_per_clip"]))
    f0 = g.link(f, g.n(M.MaterialExpressionFloor))
    a = op(M.MaterialExpressionSubtract, f, f0)
    row = g.add(g.mul(g.add(clip, par("ClipOffset", 0.0)), par("RowsPerClip", meta["rows_per_clip"])), f0)
    tw, th = par("TexW", meta["width"]), par("TexH", meta["height"])
    u = op(M.MaterialExpressionDivide, g.add(vid, k=0.5), tw)
    v0 = op(M.MaterialExpressionDivide, g.add(row, k=0.5), th)
    v1 = g.add(v0, op(M.MaterialExpressionDivide, None, th, const_a=1.0))
    smp = []
    for vv in (v0, v1):                                                # this frame and the next (lerp, no wrap)
        s_ = g.n(M.MaterialExpressionTextureSampleParameter2D, parameter_name="VAT", texture=vat_texture,
                 sampler_type=M.MaterialSamplerType.SAMPLERTYPE_DATA,
                 mip_value_mode=M.TextureMipValueMode.TMVM_MIP_LEVEL, const_mip_value=0)
        g.link(op(M.MaterialExpressionAppendVector, u, vv), s_, "UVs")
        smp.append(s_)
    o = g.n(M.MaterialExpressionLinearInterpolate)
    g.link(smp[0], o, "A", out="RGB")
    g.link(smp[1], o, "B", out="RGB")
    g.link(a, o, "Alpha")
    ox = g.mul(mask(o, "r"), g.link(msz, g.n(M.MaterialExpressionSign)))   # mirror
    oy, oz = mask(o, "g"), mask(o, "b")
    rx = op(M.MaterialExpressionSubtract, g.mul(c, ox), g.mul(s, oy))     # yaw + scale (Blender space)
    ry = g.add(g.mul(s, ox), g.mul(c, oy))
    rz = g.mul(g.link(msz, g.n(M.MaterialExpressionAbs)), oz)
    r3 = op(M.MaterialExpressionAppendVector, op(M.MaterialExpressionAppendVector, rx, ry), rz)
    axis = g.n(M.MaterialExpressionVectorParameter, parameter_name="AxisScale",
               default_value=unreal.LinearColor(*meta["axis_scale"], 0.0))
    axis3 = g.link(axis, g.n(M.MaterialExpressionComponentMask, r=True, g=True, b=True, a=False))

    def to_world(v):                                                   # a local (mesh) vector -> world, like the VAT
        e = g.n(M.MaterialExpressionTransform,
                transform_source_type=M.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL,
                transform_type=M.MaterialVectorCoordTransform.TRANSFORM_WORLD)
        return g.link(v, e)
    vat_ws = to_world(g.mul(r3, axis3))
    # making way: the dancer's root (UV5, Blender m) in world cm = the actor's origin + its local offset, turned with it
    root_l = g.mul(op(M.MaterialExpressionAppendVector, op(M.MaterialExpressionAppendVector, pvx, pvy), g.const(0.0)), axis3)
    root_ws = g.add(g.n(M.MaterialExpressionObjectPositionWS), to_world(root_l))
    root_xy = g.link(root_ws, g.n(M.MaterialExpressionComponentMask, r=True, g=True, b=False, a=False))
    player = op(M.MaterialExpressionAppendVector, mpc(g, "PlayerX"), mpc(g, "PlayerY"))
    away = op(M.MaterialExpressionSubtract, root_xy, player)
    dist = g.add(op(M.MaterialExpressionDistance, root_xy, player), k=1.0)                   # cm (+1: never 0)
    near = dm._sat(g, g.mul(g.add(g.mul(dist, k=-1.0), k=reach_cm), k=1.0 / (reach_cm - 30.0)))   # 0 at reach .. 1 at 30
    w = g.mul(g.mul(near, near), par("PushCm", push_cm))                                       # eased: (..)^2 x push
    push = g.mul(op(M.MaterialExpressionDivide, away, dist), w)
    push3 = op(M.MaterialExpressionAppendVector, push, g.const(0.0))
    dm.connect_wpo(g, g.add(vat_ws, push3))
    vc = g.link(g.n(M.MaterialExpressionVertexColor), g.n(M.MaterialExpressionComponentMask, r=True, g=True, b=True, a=False))
    col = g.n(M.MaterialExpressionPower, const_exponent=2.2)          # albedo = VertexColor ^ ColGamma (sRGB bytes)
    g.link(vc, col, "Base")
    g.link(par("ColGamma", 2.2), col, "Exp")                              # the editor shortens Exponent to Exp
    if glow:                                                           # phones, glowsticks, LEDs: breathing on the beat
        breath = g.wave01(g.mul(t, k=dm.HALF_HZ), 0.75, 1.0)
        g.emissive(g.mul(g.mul(g.mul(col, breath), par("GlowBoost", 1.6)), boost(g, major=0.4)))
        return g.save()
    if light_texture is None or cues is None:
        raise RuntimeError(name + ": the bodies need T_ClubCrowdLight and the cue table")
    lt = g.n(M.MaterialExpressionTextureSampleParameter2D, parameter_name="Light", texture=light_texture,
             sampler_type=M.MaterialSamplerType.SAMPLERTYPE_COLOR)
    lt_rgb = g.n(M.MaterialExpressionMultiply, const_b=1.0)
    g.link(lt, lt_rgb, "A", out="RGB")
    wash = dm.cue_level(g, cues, g.const(dm.WASH_ROW))
    heads = dm.cue_level(g, cues, g.const(HEADS_ROW))
    level = g.mul(g.add(g.mul(wash, k=1.0 - CROWD_FLOOR), k=CROWD_FLOOR), par("LightGain", light_gain))  # dark between hits
    base = g.mul(g.mul(g.mul(col, lt_rgb), level), mpc(g, "CrowdGain"))
    # the rim: (1 - |N.V|)^3 (silhouettes against the stage), blue with the wash, amber with the heads, brighter on hits
    nv = g.link(op(M.MaterialExpressionDotProduct, g.n(M.MaterialExpressionVertexNormalWS),
                   g.n(M.MaterialExpressionCameraVectorWS)), g.n(M.MaterialExpressionAbs))
    rim = g.n(M.MaterialExpressionPower, const_exponent=3.0)
    g.link(g.link(nv, g.n(M.MaterialExpressionOneMinus)), rim, "Base")
    rimcol = g.add(g.mul(g.color(BLUE), g.add(g.mul(wash, k=0.9), k=0.1)), g.mul(g.color(AMBER), heads))
    rim_e = g.mul(g.mul(g.mul(g.mul(rim, rimcol), par("RimGain", 0.7)), boost(g, major=0.8, drop=0.5)),
                  mpc(g, "CrowdRim"))
    g.emissive(g.add(base, rim_e))
    return g.save()
