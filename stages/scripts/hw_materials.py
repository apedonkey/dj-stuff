# Animated materials for GRAVEYARD SHIFT (the Halloween stage). Build with the Meta fork editor only: they compile to OUR
# shaders, which ship in pak chunk 54's ShaderArchive (the custom-material device gate passed 2026-10-05 for the Dino
# Stage). World Position Offset goes through the ModMaterialTools editor plugin (MetaHw/TribeXR/Plugins).
#
# A SNAPSHOT of the proven parts of the Dino Stage's dino_materials.py (2026-10-08; the graph builder G, cue_level,
# show_light, beams_material, the v5 laser_sweep, vat_crowd and the VAT import helpers), copied rather than imported:
# the Dino session edits that file all the time, and its show reads the Dino-only MPC_DinoGiant. Nothing here references
# a Dino asset. New for Halloween: cue_level_smooth, cue_tex, flicker_tex, lightning_sky, bolts, fog_sheet, fire_card,
# flock_orbit, ghost_waver, rigid_rise, hinge_swing, clock_hands, clock_face, moon_clouds.
#
# v3 (2026-10-09): the show follows the music. build_halloween.py makes MPC_HwShow (the hook's show bus, dumper.cpp, the
# Dino session's) and sets SHOW_MPC: the show clock is Time + ShowOffset (the song's bars) and every cue level x ShowLevel
# (a song's "dark" / "top" looks), as in dino_materials.cue_level. The lasers moved to dino_materials.laser_show (the
# Dino's pattern engine, imported by build_halloween.py), so v2's laser_sweep is gone. The fog is darker (the user: "a
# lot darker out"), the sky's strike gain rises with its darker texture.
#
# Masters take their texture as a parameter "Tex" (and their light-show row as "CueRow"), so one material serves many
# meshes through instances that set parameters only (no extra shaders). Tempo: 140 BPM, half-time (the user's dubstep).
import math

import unreal

mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
M = unreal
BEAT_HZ = 140.0 / 60.0
HALF_HZ = BEAT_HZ / 2
SHOW_LOOP_S = 32 * 4 / BEAT_HZ          # hw_show.py: 32 bars at 140 BPM = 54.9 s
BAR_S = 4 / BEAT_HZ
CUE_ROWS_N = 32                         # hw_show.py: T_HwCues is 32 bars x 32 rows
MACRO_S = 960.0                         # the slow layer: the storm builds and the clock strikes midnight every 16 min
WASH_ROW, STORM_ROW, FIRE_ROW, HANDS_ROW, FOG_ROW = 1, 12, 14, 16, 17
ATTACK_S = 0.06                         # every cue step ramps over 60 ms (4.3 frames at 72 Hz): never a one-frame hit
STRIKE_BUMP = 0.25                      # how much a full lightning strike adds to the set's light (show_lit)
SHOW_MPC = None                         # v3: MPC_HwShow when build_halloween made it (else the show runs on Time alone)


class G:
    """A tiny graph builder (dino_materials.G): nodes laid out left to right, links checked."""

    def __init__(self, name, folder, translucent=False, two_sided=False):
        path = f"{folder}/{name}"
        if eal.does_asset_exist(path):
            eal.delete_asset(path)
        self.path = path
        self.m = tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
        self.m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
        self.m.set_editor_property("two_sided", two_sided)
        if translucent:
            self.m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
        self.x = -2400

    def n(self, cls, **props):
        e = mel.create_material_expression(self.m, cls, self.x, 0)
        self.x += 160
        for k, v in props.items():
            e.set_editor_property(k, v)
        return e

    def link(self, a, b, inp="", out=""):
        if not mel.connect_material_expressions(a, out, b, inp):
            raise RuntimeError(f"{self.path}: connect {a.get_name()}.{out} -> {b.get_name()}.{inp} failed")
        return b

    def const(self, v):
        return self.n(M.MaterialExpressionConstant, r=float(v))

    def color(self, rgb):
        return self.n(M.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(*rgb, 1.0))

    def time(self, scale=1.0):
        t = self.n(M.MaterialExpressionTime)
        return t if scale == 1.0 else self.link(t, self.n(M.MaterialExpressionMultiply, const_b=float(scale)), "A")

    def mul(self, a, b=None, k=None):
        e = self.n(M.MaterialExpressionMultiply, **({"const_b": float(k)} if k is not None else {}))
        self.link(a, e, "A")
        if b is not None:
            self.link(b, e, "B")
        return e

    def add(self, a, b=None, k=None):
        e = self.n(M.MaterialExpressionAdd, **({"const_b": float(k)} if k is not None else {}))
        self.link(a, e, "A")
        if b is not None:
            self.link(b, e, "B")
        return e

    def sub(self, a, b):
        e = self.n(M.MaterialExpressionSubtract)
        self.link(a, e, "A")
        self.link(b, e, "B")
        return e

    def sine(self, a):                                   # sin(2*pi*a)
        return self.link(a, self.n(M.MaterialExpressionSine, period=1.0))

    def frac(self, a):
        return self.link(a, self.n(M.MaterialExpressionFrac))

    def floor(self, a):
        return self.link(a, self.n(M.MaterialExpressionFloor))

    def sat(self, a):
        return self.link(a, self.n(M.MaterialExpressionClamp, min_default=0.0, max_default=1.0))

    def lerp(self, a, b, alpha):
        e = self.n(M.MaterialExpressionLinearInterpolate)
        self.link(a, e, "A")
        self.link(b, e, "B")
        self.link(alpha, e, "Alpha")
        return e

    def wave01(self, a, lo, hi):                         # lo..hi following sin(2*pi*a)
        return self.add(self.mul(self.sine(a), k=(hi - lo) / 2), k=(hi + lo) / 2)

    def mask(self, src, ch, out=""):
        e = self.n(M.MaterialExpressionComponentMask, r="r" in ch, g="g" in ch, b="b" in ch, a="a" in ch)
        return self.link(src, e, out=out)

    def append(self, a, b):
        e = self.n(M.MaterialExpressionAppendVector)
        self.link(a, e, "A")
        self.link(b, e, "B")
        return e

    def uv(self, i):
        return self.n(M.MaterialExpressionTextureCoordinate, coordinate_index=i)

    def world(self, mask):                               # absolute world position (cm), masked "x"/"y"/"z"/"xz"...
        wp = self.n(M.MaterialExpressionWorldPosition)
        cm = self.n(M.MaterialExpressionComponentMask, r="x" in mask, g="y" in mask, b="z" in mask, a=False)
        return self.link(wp, cm)

    def tex(self, texture, uv=None, sampler=M.MaterialSamplerType.SAMPLERTYPE_COLOR):
        s = self.n(M.MaterialExpressionTextureSample, texture=texture, sampler_type=sampler)
        if uv is not None:
            self.link(uv, s, "UVs")
        return s

    def tex_param(self, name, texture, uv=None, sampler=M.MaterialSamplerType.SAMPLERTYPE_COLOR):
        s = self.n(M.MaterialExpressionTextureSampleParameter2D, parameter_name=name, texture=texture, sampler_type=sampler)
        if uv is not None:
            self.link(uv, s, "UVs")
        return s

    def param(self, name, value):
        return self.n(M.MaterialExpressionScalarParameter, parameter_name=name, default_value=float(value))

    def emissive(self, e, out=""):
        if not mel.connect_material_property(e, out, M.MaterialProperty.MP_EMISSIVE_COLOR):
            raise RuntimeError(self.path + ": emissive connect failed")

    def opacity(self, e, out=""):
        if not mel.connect_material_property(e, out, M.MaterialProperty.MP_OPACITY):
            raise RuntimeError(self.path + ": opacity connect failed")

    def save(self):
        mel.recompile_material(self.m)
        eal.save_asset(self.path)
        unreal.log(f"[HW] material {self.path}: {mel.get_num_material_expressions(self.m)} expressions")
        return self.m


class _Extend(G):
    """G bound to a material a factory already built and saved (no delete, no create), to add to its graph
    (club_materials._Extend)."""

    def __init__(self, mat, path):  # noqa: the base __init__ would delete and recreate the asset
        self.m, self.path, self.x = mat, path, 400


LASER_NEAR = (20.0, 80.0)      # cm: club_materials.LASER_NEAR (Reactor v8)


def laser_near_fade(mat, path, start_cm=LASER_NEAR[0], full_cm=LASER_NEAR[1]):
    """v7 (the beams now run down through the crowd, where the user roams): dino_materials.laser_show's emissive x 0 at
    the eye .. 1 from full_cm away, so a beam swept through your head never fills the view (club_materials.laser_show's
    near_fade, Reactor v8). The Dino's factory is untouched: its saved material is extended here."""
    g = _Extend(mat, path)
    prop = M.MaterialProperty.MP_EMISSIVE_COLOR
    src = mel.get_material_property_input_node(mat, prop)
    if src is None:
        raise RuntimeError(path + ": dm.laser_show left no emissive input to extend")
    dist = g.n(M.MaterialExpressionDistance)
    mel.connect_material_expressions(g.n(M.MaterialExpressionCameraPositionWS), "", dist, "A")
    mel.connect_material_expressions(g.n(M.MaterialExpressionWorldPosition), "", dist, "B")
    k = g.sat(g.mul(g.add(dist, k=-start_cm), k=1.0 / (full_cm - start_cm)))
    e = g.n(M.MaterialExpressionMultiply)
    if not mel.connect_material_expressions(src, mel.get_material_property_input_node_output_name(mat, prop), e, "A"):
        raise RuntimeError(path + ": near fade: emissive link failed")
    if not mel.connect_material_expressions(k, "", e, "B"):
        raise RuntimeError(path + ": near fade: fade link failed")
    if not mel.connect_material_property(e, "", prop):
        raise RuntimeError(path + ": near fade: emissive connect failed")
    return g.save()


def connect_wpo(g, expr):
    """World Position Offset: Python's MaterialProperty enum hides it in 5.4, so the ModMaterialTools editor plugin
    wires it (dino_materials.connect_wpo)."""
    lib = getattr(unreal, "ModMaterialToolsLibrary", None)
    if lib is None or not lib.connect_world_position_offset(g.m, expr, ""):
        raise RuntimeError(g.path + ": WPO connect failed (ModMaterialTools plugin loaded?)")


# ---------------------------------------------------------------- the light show clock (hw_show.py's cue table)
def _cue_sample(g, cues, row, bar_expr):
    u = g.mul(g.add(bar_expr, k=0.5), k=1.0 / 32.0)
    v = g.mul(g.add(row, k=0.5), k=1.0 / CUE_ROWS_N)
    smp = g.n(M.MaterialExpressionTextureSample, texture=cues, sampler_type=M.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    g.link(g.append(u, v), smp, "UVs")
    return smp


def _mpc(g, pname):
    return g.n(M.MaterialExpressionCollectionParameter, collection=SHOW_MPC, parameter_name=pname)


def show_time(g, scale=1.0):
    """The show clock in seconds (x scale): Time + the hook's ShowOffset when MPC_HwShow is set (v3: the song's bars,
    32 bars at 140 BPM, as dino_materials.cue_level), else Time."""
    t = g.time()
    if SHOW_MPC is not None:
        t = g.add(t, _mpc(g, "ShowOffset"))
    return t if scale == 1.0 else g.mul(t, k=scale)


def _bar(g):
    """(bar index, fraction of the bar) in the 32-bar loop right now."""
    barf = g.mul(g.frac(g.mul(show_time(g), k=1.0 / SHOW_LOOP_S)), k=32.0)
    bar = g.floor(barf)
    return bar, g.sub(barf, bar)


def _bus_bar(g, clock_bar, pname):
    """A neighbouring bar: the hook's ShowPrevBar / ShowNextBar when it sends one (>= 0: song mode loops sections, so the
    clock's neighbour can be the wrong bar there), else the clock's (the free show plays the bars in order)."""
    if SHOW_MPC is None:
        return clock_bar
    hb = _mpc(g, pname)
    return g.lerp(clock_bar, hb, g.sat(g.mul(g.add(hb, k=0.5), k=1000.0)))


def _ch(g, smp, name):
    m = g.n(M.MaterialExpressionMultiply, const_b=1.0)
    g.link(smp, m, "A", out=name)
    return m


def cue_level(g, cues, row):
    """Level of light-show row `row` (an expression) now (dino_materials.cue_level without the Dino MPC): R = level,
    G = strobe flag (a soft 2 Hz blink at most; hw_show sets none), B = beat pulse (gentle, beats 1 and 3, half-time).
    A bar-line step ramps from the previous bar's level over ATTACK_S (comfort: no one-frame hits)."""
    bar, fb = _bar(g)
    smp = _cue_sample(g, cues, row, bar)
    prv = g.frac(g.mul(g.add(bar, k=31.0), k=1.0 / 32.0))                  # the previous bar (0 -> 31)
    psmp = _cue_sample(g, cues, row, _bus_bar(g, g.mul(prv, k=32.0), "ShowPrevBar"))
    ramp = g.sat(g.mul(fb, k=BAR_S / ATTACK_S))
    lc, stf = _ch(g, smp, "R"), _ch(g, smp, "G")
    lvl = g.lerp(_ch(g, psmp, "R"), lc, ramp)
    puf = g.lerp(_ch(g, psmp, "B"), _ch(g, smp, "B"), ramp)               # the pulse flag ramps too (no spike)
    t = show_time(g)
    sq = g.wave01(g.mul(t, k=2.0), 0.4, 1.0)
    strobe = g.add(g.mul(stf, g.add(sq, k=-1.0)), k=1.0)
    ph = g.frac(g.mul(t, k=HALF_HZ))
    inv = g.add(g.mul(ph, k=-1.0), k=1.0)
    patt = g.sat(g.mul(ph, k=1.0 / (HALF_HZ * ATTACK_S)))               # the pulse ramps up over ATTACK_S too
    env = g.add(g.mul(g.mul(g.mul(inv, inv), patt), k=0.4), k=0.6)      # 0.6 + 0.4 (1 - ph)^2 after the ramp
    pulse = g.add(g.mul(puf, g.add(env, k=-1.0)), k=1.0)
    out = g.mul(g.mul(lvl, strobe), pulse)
    if SHOW_MPC is not None:                                            # a song's "dark" / "top" look (0.15 s / 0.3 s fades)
        out = g.mul(out, _mpc(g, "ShowLevel"))
    return out


def cue_level_smooth(g, cues, row):
    """The row's level (R only) gliding into the next bar's over the last 15% of each bar (the Dino laser engine's
    blend): motions and big emitters never jump on a bar line."""
    bar, fb = _bar(g)
    nxt = g.frac(g.mul(g.add(bar, k=1.0), k=1.0 / 32.0))
    a = _ch(g, _cue_sample(g, cues, row, bar), "R")
    b = _ch(g, _cue_sample(g, cues, row, _bus_bar(g, g.mul(nxt, k=32.0), "ShowNextBar")), "R")
    bx = g.sat(g.mul(g.add(fb, k=-0.85), k=1.0 / 0.15))
    bl = g.mul(g.mul(bx, bx), g.add(g.mul(bx, k=-2.0), k=3.0))           # smoothstep
    return g.lerp(a, b, bl)


def strike_env(g):
    """Lightning envelope inside the current bar: one strike on beat 3 (the half-time snare), a 50 ms attack (>= 3
    frames at 72 Hz: never a one-frame hit), then a 450 ms fade. 0 before the strike."""
    _, fb = _bar(g)
    d = g.mul(g.add(fb, k=-0.5), k=BAR_S)                                # seconds since the strike
    att = g.sat(g.mul(d, k=1.0 / 0.05))
    dec = g.sat(g.add(g.mul(d, k=-1.0 / 0.45), k=1.0 + 0.05 / 0.45))
    return g.mul(att, dec)


def macro(g):
    """The 16-minute layer, 0 -> 1 -> 0: the storm builds and eases off over it."""
    return g.wave01(g.add(g.time(1.0 / MACRO_S), k=-0.25), 0.0, 1.0)


def show_light(g, cues, floor=0.08, sweep=0.0):
    """Night: how much of the baked light shows right now (dino_materials.show_light): floor (near black) between
    hits, up to 1 when the wash row fires. sweep > 0: bands of light travel across (the crowd)."""
    lvl = cue_level(g, cues, g.const(WASH_ROW))
    if sweep > 0:
        ph = g.add(g.time(0.35), g.add(g.mul(g.world("x"), k=0.0025 * sweep), g.mul(g.world("y"), k=0.0012 * sweep)))
        lvl = g.mul(lvl, g.wave01(ph, 0.35, 1.0))
    return g.add(g.mul(lvl, k=1.0 - floor), k=floor)


def flicker(g, amount):
    """Candle-like flicker 1-amount..1, phase from world position (no two lanterns in step); ~2-4 Hz, soft (sines)."""
    a = g.wave01(g.add(g.time(2.3), g.mul(g.add(g.world("x"), g.world("y")), k=0.013)), 1.0 - amount, 1.0)
    b = g.wave01(g.add(g.time(3.7), g.mul(g.world("z"), k=0.021)), 1.0 - amount * 0.5, 1.0)
    return g.mul(a, b)


# ---------------------------------------------------------------- masters (instances set Tex / CueRow / Floor ...)
def show_lit(name, folder, default_tex, cues, floor=0.08):
    """The baked set (facade, rig, deck): Tex x (show light + the lightning bump). Floor is a parameter."""
    g = G(name, folder)
    s = g.tex_param("Tex", default_tex)
    lvl = cue_level(g, cues, g.const(WASH_ROW))
    fl = g.param("Floor", floor)
    light = g.add(g.mul(lvl, g.add(g.mul(fl, k=-1.0), k=1.0)), fl)        # floor + (1 - floor) * level
    storm = g.mul(cue_level(g, cues, g.const(STORM_ROW)), g.add(g.mul(macro(g), k=0.6), k=0.4))
    light = g.add(light, g.mul(g.mul(storm, strike_env(g)), k=STRIKE_BUMP))   # the set catches the lightning
    g.emissive(g.mul(s, light))
    return g.save()


def cue_tex(name, folder, default_tex, cues):
    """Glowing parts that follow one show row: Tex x (Floor + (1 - Floor) x level(CueRow)) x flicker(Flicker).
    Lens discs (lenses row), stained glass (windows row), eyes (eyes row)."""
    g = G(name, folder)
    s = g.tex_param("Tex", default_tex, sampler=M.MaterialSamplerType.SAMPLERTYPE_COLOR)
    lvl = cue_level(g, cues, g.param("CueRow", 13))
    fl = g.param("Floor", 0.08)
    light = g.add(g.mul(lvl, g.add(g.mul(fl, k=-1.0), k=1.0)), fl)
    amt = g.param("Flicker", 0.0)
    a = g.wave01(g.add(g.time(2.3), g.mul(g.add(g.world("x"), g.world("y")), k=0.013)), 0.0, 1.0)
    fk = g.add(g.mul(g.mul(g.add(a, k=-1.0), amt), k=1.0), k=1.0)       # 1 - amt (1 - a)
    g.emissive(g.mul(g.mul(s, light), fk))
    return g.save()


def flicker_tex(name, folder, default_tex, amount=0.2):
    """Lanterns, candles, the cauldron: Tex x a soft flicker."""
    g = G(name, folder)
    s = g.tex_param("Tex", default_tex)
    g.emissive(g.mul(s, flicker(g, amount)))
    return g.save()


def beams_material(name, folder, default_tex, cues, rate=BEAT_HZ / 4, spread=0.0008):
    """Translucent beams/halos (dino_materials.beams_material): colour from Tex, alpha = Tex alpha x a breathing level
    rippling across the fans x the show level of row CueRow (one instance per beam group)."""
    g = G(name, folder, translucent=True, two_sided=True)
    s_ = g.tex_param("Tex", default_tex)
    ph = g.add(show_time(g, rate), g.mul(g.world("x"), k=spread))
    lvl = g.mul(g.wave01(ph, 0.65, 1.0), cue_level(g, cues, g.param("CueRow", 13)))
    op = g.n(M.MaterialExpressionMultiply)
    g.link(s_, op, "A", out="A")
    g.link(lvl, op, "B")
    g.emissive(s_, "RGB")
    g.opacity(op)
    return g.save()


def _pivot(g, uv_xy, uv_z):
    """A per-vertex pivot stored in Blender meters (UV channels) -> world cm: mesh local = (x, -y, z) * 100 (our FBX
    import), then TransformPosition local -> world (the level actor is turned 180 degrees)."""
    px = g.mul(g.mask(uv_xy, "r"), k=100.0)
    py = g.mul(g.mask(uv_xy, "g"), k=-100.0)
    pz = g.mul(g.mask(uv_z, "r"), k=100.0)
    pl = g.append(g.append(px, py), pz)
    piv = g.n(M.MaterialExpressionTransformPosition,
              transform_source_type=M.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL,
              transform_type=M.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD)
    return g.link(pl, piv, "")


def _rotate(g, axis, angle_turns, pivot, pos):
    r = g.n(M.MaterialExpressionRotateAboutAxis)
    g.link(axis, r, "NormalizedRotationAxis")
    g.link(angle_turns, r, "RotationAngle")
    g.link(pivot, r, "PivotPoint")
    g.link(pos, r, "Position")
    return r                                                            # the OFFSET (rotated - position)


def lightning_sky(name, folder, default_tex, cues, gain=3.0):
    """The storm sky: Tex x (1 + gain x storm level x the strike envelope x the 16-min build (0.4..1)). v3: the sky
    texture is x0.35 darker, so a full strike (x4) lights it to about v2's resting brightness."""
    g = G(name, folder, two_sided=True)
    s = g.tex_param("Tex", default_tex)
    lvl = g.mul(cue_level(g, cues, g.const(STORM_ROW)), g.add(g.mul(macro(g), k=0.6), k=0.4))
    g.emissive(g.mul(s, g.add(g.mul(g.mul(lvl, strike_env(g)), k=gain), k=1.0)))
    return g.save()


def bolts(name, folder, default_tex, cues):
    """Lightning bolts behind the cathedral (translucent quads on T_HwBeam's moon column): visible only in a strike."""
    g = G(name, folder, translucent=True, two_sided=True)
    s_ = g.tex_param("Tex", default_tex)
    lvl = g.mul(cue_level(g, cues, g.const(STORM_ROW)), g.add(g.mul(macro(g), k=0.6), k=0.4))
    op = g.n(M.MaterialExpressionMultiply)
    g.link(s_, op, "A", out="A")
    g.link(g.mul(lvl, strike_env(g)), op, "B")                          # opacity follows the 50 ms attack
    g.emissive(g.mul(s_, k=1.6), "")                                     # the brightness gain sits in the colour
    g.opacity(g.sat(op))
    return g.save()


def fog_sheet(name, folder, noise_tex, cues, rgb=(0.022, 0.018, 0.030), lit_floor=0.15):
    """Ground fog: two noise layers drifting in world XY (cm), soft edges from UV0 (0..1 across the sheet), alpha x
    the fog row (smooth); it brightens with the wash (lit by the show). v3: ~x0.2 darker and lit 0.15..1 (was 0.35..1):
    a dark haze between the hits that only catches the light in the drop (v2's showed as a grey veil over the field).
    v7 (the user, 2026-10-11: a low ground fog, "keep it low"): build_halloween passes a moonlit rgb and lit_floor."""
    g = G(name, folder, translucent=True, two_sided=True)
    wxy = g.world("xy")
    p1 = g.add(g.mul(wxy, k=1.0 / 3200.0), g.mul(g.time(), k=0.004))
    p2 = g.add(g.mul(wxy, k=1.0 / 1300.0), g.mul(g.time(), k=-0.007))
    n1 = g.mask(g.tex_param("Noise", noise_tex, p1), "r", out="RGB")
    n2 = g.mask(g.tex(noise_tex, p2), "r", out="RGB")
    uv0 = g.uv(0)
    u, v = g.mask(uv0, "r"), g.mask(uv0, "g")
    def edge(x):
        mn = g.n(M.MaterialExpressionMin)
        g.link(x, mn, "A")
        g.link(g.add(g.mul(x, k=-1.0), k=1.0), mn, "B")
        return g.sat(g.mul(mn, k=6.0))
    shape = g.mul(g.mul(n1, n2), g.mul(edge(u), edge(v)))
    dens = g.mul(cue_level_smooth(g, cues, g.const(FOG_ROW)), g.param("Density", 0.9))
    g.opacity(g.sat(g.mul(g.mul(shape, dens), k=1.6)))
    lit = g.add(g.mul(cue_level(g, cues, g.const(WASH_ROW)), k=1.0 - lit_floor), k=lit_floor)
    g.emissive(g.mul(g.color(rgb), lit))
    return g.save()


def fire_card(name, folder, fire_tex, noise_tex, cues):
    """Flame jets: a static flame shape and colour ramp (Tex on UV0: alpha = the tongue, wide at the base) x noise
    scrolling up through it (tongues licking); alpha x the fire row (smooth: never a jump) x a fast lick."""
    g = G(name, folder, translucent=True, two_sided=True)
    s_ = g.tex_param("Tex", fire_tex, g.uv(0))
    rg = lambda v: g.mask(g.color(v), "rg")                         # float2: UV x a float3 does not compile
    nuv = g.add(g.mul(g.uv(0), rg((0.8, 0.45, 0.0))), g.mul(g.time(), rg((0.0, -0.9, 0.0))))
    nz = g.mask(g.tex(noise_tex, g.mask(nuv, "rg")), "r", out="RGB")
    lick = g.wave01(g.add(g.time(6.0), g.mul(g.world("x"), k=0.01)), 0.8, 1.0)
    lvl = g.mul(cue_level_smooth(g, cues, g.const(FIRE_ROW)), lick)
    if SHOW_MPC is not None:                                        # a song's "dark" look stops the jets too
        lvl = g.mul(lvl, _mpc(g, "ShowLevel"))
    op = g.n(M.MaterialExpressionMultiply)
    g.link(s_, op, "A", out="A")
    g.link(g.mul(g.add(g.mul(nz, k=1.1), k=0.35), lvl), op, "B")
    g.emissive(g.mul(s_, k=1.2), "")
    g.opacity(g.sat(op))
    return g.save()


def door_swing(name, folder, default_tex, hinge_x_m, hinge_y_m, open_deg, stagger):
    """The crypt gate's two doors (hw_stage.build_gate, v5; the user: "make them 2 doors not a garage door. Like crypt
    doors"): Tex (their bake, shut) and, on MPC_HwShow's DoorOpen (0 shut .. 1 open, the mod eases it), each leaf turns
    about its jamb's vertical hinge at Blender (side x hinge_x_m, hinge_y_m) out to the deck, open_deg at 1; the
    right leaf (side +1) trails by `stagger` of the travel. UV1.x = the leaf's side (-1 / +1, Blender x). The turn is
    done in Blender's frame from the world position (world cm = (-100x, 100y, 100z), the level frame gate_lift used in
    v4 and _pivot uses), so no RotateAboutAxis handedness is involved; hw_intro_path.door_xy is the same rule in Python.
    No MPC (the stock build): the doors stay shut."""
    g = G(name, folder)
    s = g.tex_param("Tex", default_tex)
    g.emissive(s, "RGB")
    if SHOW_MPC is not None:
        side = g.mask(g.uv(1), "r")
        delay = g.add(g.mul(side, k=0.5 * stagger), k=0.5 * stagger)              # 0 left, stagger right
        prog = g.sat(g.mul(g.sub(_mpc(g, "DoorOpen"), delay), k=1.0 / (1.0 - stagger)))
        turns = g.mul(g.mul(prog, side), k=open_deg / 360.0)                       # + = anticlockwise from above
        sn, cs1 = g.sine(turns), g.add(g.sine(g.add(turns, k=0.25)), k=-1.0)      # sin a, cos a - 1
        wp = g.n(M.MaterialExpressionWorldPosition)
        dx = g.sub(g.mul(g.mask(wp, "r"), k=-0.01), g.mul(side, k=hinge_x_m))     # Blender m from the hinge
        dy = g.add(g.mul(g.mask(wp, "g"), k=0.01), k=-hinge_y_m)
        ddx = g.sub(g.mul(dx, cs1), g.mul(dy, sn))                                 # the turn's displacement
        ddy = g.add(g.mul(dx, sn), g.mul(dy, cs1))
        connect_wpo(g, g.append(g.append(g.mul(ddx, k=-100.0), g.mul(ddy, k=100.0)), g.const(0.0)))
    return g.save()


def intro_button(name, folder):
    """The backstage button's cap by IntroStep: 0 idle and 1 the pre-show ride: green (press: start / ride in), 2 riding
    in: amber, 3 showtime: a dim red; a slow breath (0.8 Hz, 0.75..1). No MPC: green."""
    g = G(name, folder)
    step = _mpc(g, "IntroStep") if SHOW_MPC is not None else g.const(0.0)
    c = g.lerp(g.color((0.15, 1.0, 0.25)), g.color((1.0, 0.55, 0.05)), g.sat(g.add(step, k=-1.0)))
    c = g.lerp(c, g.color((0.35, 0.02, 0.02)), g.sat(g.add(step, k=-2.0)))
    g.emissive(g.mul(c, g.wave01(g.time(0.8), 0.75, 1.0)))
    return g.save()


def flock_orbit(name, folder, default_tex):
    """Bats: every vertex turns about the vertical through its flock's centre (UV1 = centre x, y; UV2 = (centre z,
    phase); UV3 = (turns per second, wing flag -1/0/1)); wings flap 3 Hz. Black silhouettes on the palette texture,
    two-sided (seen from below and from the drone)."""
    g = G(name, folder, two_sided=True)
    s = g.tex_param("Tex", default_tex)
    uv1, uv2, uv3 = g.uv(1), g.uv(2), g.uv(3)
    pivot = _pivot(g, uv1, uv2)
    phase = g.mask(uv2, "g")
    ang = g.mul(g.add(g.mul(g.time(), g.mask(uv3, "r")), phase), k=-1.0)
    wp = g.n(M.MaterialExpressionWorldPosition)
    r1 = _rotate(g, g.color((0.0, 0.0, 1.0)), ang, pivot, wp)
    wing = g.link(g.mask(uv3, "g"), g.n(M.MaterialExpressionAbs))
    flap = g.mul(g.mul(g.sine(g.add(g.time(3.0), phase)), wing), k=14.0)  # cm, wing tips only
    up = g.append(g.append(g.const(0.0), g.const(0.0)), flap)
    connect_wpo(g, g.add(r1, up))
    g.emissive(s, "RGB")
    return g.save()


def ghost_waver(name, folder, rgb=(0.55, 1.0, 0.65)):
    """Ghosts: translucent sheets drifting round a centre (UV1/UV2 as the bats, UV3.x = turns per second) and wavering
    (a sine travelling up the sheet, UV0.y = height on the sheet). Faint: alpha 0.18-0.3."""
    g = G(name, folder, translucent=True, two_sided=True)
    uv1, uv2, uv3, uv0 = g.uv(1), g.uv(2), g.uv(3), g.uv(0)
    pivot = _pivot(g, uv1, uv2)
    phase = g.mask(uv2, "g")
    wp = g.n(M.MaterialExpressionWorldPosition)
    r1 = _rotate(g, g.color((0.0, 0.0, 1.0)), g.mul(g.add(g.mul(g.time(), g.mask(uv3, "r")), phase), k=-1.0), pivot, wp)
    h = g.mask(uv0, "g")
    wv = g.mul(g.mul(g.sine(g.add(g.add(g.time(0.4), phase), g.mul(h, k=0.8))), h), k=35.0)
    off = g.append(g.append(wv, g.mul(wv, k=0.6)), g.const(0.0))
    connect_wpo(g, g.add(r1, off))
    edge = g.sat(g.mul(g.add(g.mul(g.link(g.add(g.mask(uv0, "r"), k=-0.5), g.n(M.MaterialExpressionAbs)), k=-2.0),
                             k=1.0), k=2.5))
    g.opacity(g.mul(g.mul(edge, g.wave01(g.add(g.time(0.3), phase), 0.18, 0.3)), g.sat(g.mul(h, k=3.0))))
    g.emissive(g.color(rgb))
    return g.save()


def rigid_rise(name, folder, default_tex, cues, travel_cm=1300.0):
    """The giant skeletal hands: they rise out of the deck with the hands row (smooth) and sink back; WPO = (0, 0,
    (level - 1) x travel). Baked texture, shown with the show light."""
    g = G(name, folder)
    s = g.tex_param("Tex", default_tex)
    lvl = cue_level_smooth(g, cues, g.const(HANDS_ROW))
    dz = g.mul(g.add(lvl, k=-1.0), k=travel_cm)
    connect_wpo(g, g.append(g.append(g.const(0.0), g.const(0.0)), dz))
    g.emissive(g.mul(s, show_light(g, cues, floor=0.25)))
    return g.save()


def hinge_swing(name, folder, default_tex, cues):
    """Hinged grounds parts (coffin lids, the Pumpkin King's jaw; modules/CONTRACT.md "hinged"): each turns about its
    own hinge as the hands row rises (smooth: never a jump), after its own delay, eased. Baked texture (the closed
    pose), no show light (the grounds look). Per vertex, Blender meters, final frame: UV1 = hinge point (x, y), UV2 =
    (z, delay), UV3 = axis (x, y), UV4 = (axis z, opening in turns). A Blender turn by a about axis k is UE
    RotateAboutAxis(image of k, -a) after our mirrored FBX import (v2's laser_sweep rule; derived for the clock hands)."""
    g = G(name, folder)
    s = g.tex_param("Tex", default_tex)
    uv2, uv3, uv4 = g.uv(2), g.uv(3), g.uv(4)
    pivot = _pivot(g, g.uv(1), uv2)
    axl = g.append(g.append(g.mask(uv3, "r"), g.mul(g.mask(uv3, "g"), k=-1.0)), g.mask(uv4, "r"))   # mesh local
    ax = g.link(axl, g.n(M.MaterialExpressionTransform,
                         transform_source_type=M.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL,
                         transform_type=M.MaterialVectorCoordTransform.TRANSFORM_WORLD))
    ax = g.link(ax, g.n(M.MaterialExpressionNormalize))
    lvl = cue_level_smooth(g, cues, g.const(HANDS_ROW))
    d = g.mask(uv2, "g")
    dv = g.n(M.MaterialExpressionDivide)
    g.link(g.sub(lvl, d), dv, "A")
    g.link(g.add(g.mul(d, k=-1.0), k=1.0), dv, "B")
    x = g.sat(dv)
    e = g.mul(g.mul(x, x), g.add(g.mul(x, k=-2.0), k=3.0))                 # smoothstep
    ang = g.mul(g.mul(g.mask(uv4, "g"), e), k=-1.0)
    wp = g.n(M.MaterialExpressionWorldPosition)
    connect_wpo(g, _rotate(g, ax, ang, pivot, wp))
    g.emissive(s)
    return g.save()


def clock_hands(name, folder, center_m, rgb=(1.0, 0.08, 0.05)):
    """The gable clock's hands turn about the clock axis (Blender +Y through center_m): the minute hand once per 16-min
    cycle, the hour hand from 11 to 12 and on. UV1.x = hand (0 hour, 1 minute). A Blender rotation by a about axis k is
    UE RotateAboutAxis(image of k, -a) after our mirrored FBX import (v2's laser_sweep rule). Unverified on device: if
    the hands turn the wrong way, flip SIGN."""
    SIGN = -1.0
    g = G(name, folder)
    cx, cy, cz = center_m
    pl = g.color((cx * 100.0, -cy * 100.0, cz * 100.0))
    piv = g.link(pl, g.n(M.MaterialExpressionTransformPosition,
                         transform_source_type=M.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL,
                         transform_type=M.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD), "")
    ax_l = g.color((0.0, -1.0, 0.0))                                   # Blender +Y in mesh-local terms
    ax = g.link(ax_l, g.n(M.MaterialExpressionTransform,
                          transform_source_type=M.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL,
                          transform_type=M.MaterialVectorCoordTransform.TRANSFORM_WORLD))
    ax = g.link(ax, g.n(M.MaterialExpressionNormalize))
    f = g.time(1.0 / MACRO_S)
    hand = g.mask(g.uv(1), "r")
    minute = g.frac(f)
    hour = g.mul(g.add(f, k=11.0), k=1.0 / 12.0)
    ang = g.mul(g.lerp(hour, minute, hand), k=SIGN)
    wp = g.n(M.MaterialExpressionWorldPosition)
    connect_wpo(g, _rotate(g, ax, ang, piv, wp))
    g.emissive(g.color(rgb))
    return g.save()


def clock_face(name, folder, rgb=(0.12, 0.012, 0.006)):
    """The clock face glows up at midnight (the minute hand at 12, once per 16-min cycle): a ~4 s swell, no flash."""
    g = G(name, folder)
    f = g.frac(g.time(1.0 / MACRO_S))
    d = g.link(g.add(f, k=-0.5), g.n(M.MaterialExpressionAbs))                      # 0.5 at midnight
    sw = g.sat(g.mul(g.add(d, k=-0.4955), k=1.0 / 0.0045))                          # last/first ~4.3 s of the cycle
    g.emissive(g.mul(g.color(rgb), g.add(g.mul(g.mul(sw, sw), k=5.0), k=1.0)))
    return g.save()


def moon_clouds(name, folder, default_tex, noise_tex):
    """The blood moon with thin clouds drifting across it."""
    g = G(name, folder)
    s = g.tex_param("Tex", default_tex)
    p = g.add(g.mul(g.uv(0), k=1.3), g.mul(g.time(), k=0.004))
    n = g.mask(g.tex(noise_tex, p), "r", out="RGB")
    cloud = g.sat(g.mul(g.add(n, k=-0.45), k=4.0))
    g.emissive(g.mul(s, g.add(g.mul(cloud, k=-0.55), k=1.0)))
    return g.save()


# ---------------------------------------------------------------- the crowd (dino_materials.vat_crowd, no Dino MPC)
MAKE_WAY = (110.0, 55.0)        # v7 (Reactor's club_crowd numbers): a dancer starts moving 110 cm from the player and is
                                # pushed up to 55 cm away, all of it within 30 cm


def vat_crowd(name, folder, vat_texture, meta, baked_texture=None, glow=False, bpm=140.0, cues=None, two_sided=False,
              make_way=False):
    """Crowd V3 material. meta = the T_HwCrowdVAT.json dict. Bodies: emissive = baked_texture on UV0 (x the show's
    sweeping light with cues). glow=True (SM_HwPhones): emissive = vertex colour x GlowBoost, breathing on the beat.
    two_sided: v6's rider (flame tongues, the blanket and straps are single sheets).
    make_way (v7; the user, 2026-10-11: free roam in the crowd, the dancers parting as on Reactor): each dancer is pushed
    away from the player as a whole: UV5 VatPivot = the root (Blender m), PlayerX / PlayerY (world cm) in MPC_HwShow,
    written every frame by hook/club.cpp for any stage with a <folder>_collide.txt (club_materials.club_crowd's rule)."""
    g = G(name, folder, two_sided=two_sided)

    def par(pname, value):
        return g.n(M.MaterialExpressionScalarParameter, parameter_name=pname, default_value=float(value))

    def op(cls, a, b, **kw):
        e = g.n(cls, **kw)
        if a is not None:
            g.link(a, e, "A")
        if b is not None:
            g.link(b, e, "B")
        return e
    tc = [g.uv(i) for i in (1, 2, 3, 4)]
    vid, clip = g.mask(tc[0], "r"), g.mask(tc[0], "g")
    c, s = g.mask(tc[1], "r"), g.mask(tc[1], "g")
    msz, phase = g.mask(tc[2], "r"), g.mask(tc[2], "g")
    rate = g.mask(tc[3], "r")
    loops = par("LoopRate", bpm / (60.0 * meta["beats_per_clip"]))
    p = g.frac(g.add(g.mul(g.mul(g.time(), loops), rate), phase))
    f = g.mul(p, par("FramesPerClip", meta["frames_per_clip"]))
    f0 = g.floor(f)
    a = op(M.MaterialExpressionSubtract, f, f0)
    row = g.add(g.mul(g.add(clip, par("ClipOffset", 0.0)), par("RowsPerClip", meta["rows_per_clip"])), f0)
    tw, th = par("TexW", meta["width"]), par("TexH", meta["height"])
    u = op(M.MaterialExpressionDivide, g.add(vid, k=0.5), tw)
    v0 = op(M.MaterialExpressionDivide, g.add(row, k=0.5), th)
    v1 = g.add(v0, op(M.MaterialExpressionDivide, None, th, const_a=1.0))
    smp = []
    for vv in (v0, v1):
        s_ = g.n(M.MaterialExpressionTextureSampleParameter2D, parameter_name="VAT", texture=vat_texture,
                 sampler_type=M.MaterialSamplerType.SAMPLERTYPE_DATA,
                 mip_value_mode=M.TextureMipValueMode.TMVM_MIP_LEVEL, const_mip_value=0)
        g.link(op(M.MaterialExpressionAppendVector, u, vv), s_, "UVs")
        smp.append(s_)
    o = g.n(M.MaterialExpressionLinearInterpolate)
    g.link(smp[0], o, "A", out="RGB")
    g.link(smp[1], o, "B", out="RGB")
    g.link(a, o, "Alpha")
    ox = g.mul(g.mask(o, "r"), g.link(msz, g.n(M.MaterialExpressionSign)))
    oy, oz = g.mask(o, "g"), g.mask(o, "b")
    rx = op(M.MaterialExpressionSubtract, g.mul(c, ox), g.mul(s, oy))
    ry = g.add(g.mul(s, ox), g.mul(c, oy))
    rz = g.mul(g.link(msz, g.n(M.MaterialExpressionAbs)), oz)
    r3 = op(M.MaterialExpressionAppendVector, op(M.MaterialExpressionAppendVector, rx, ry), rz)
    axis = g.n(M.MaterialExpressionVectorParameter, parameter_name="AxisScale",
               default_value=unreal.LinearColor(*meta["axis_scale"], 0.0))
    axis3 = g.mask(axis, "rgb")
    def to_world(v):
        e = g.n(M.MaterialExpressionTransform,
                transform_source_type=M.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL,
                transform_type=M.MaterialVectorCoordTransform.TRANSFORM_WORLD)
        return g.link(v, e)
    wpo = to_world(g.mul(r3, axis3))
    if make_way:
        if "UV5 VatPivot" not in meta.get("uv_channels", {}):
            raise RuntimeError(name + ": the VAT json has no UV5 VatPivot (bake the crowd with v7's hw_crowd.py)")
        reach, push_cm = MAKE_WAY
        piv = g.uv(5)
        root_l = g.mul(op(M.MaterialExpressionAppendVector, op(M.MaterialExpressionAppendVector, g.mask(piv, "r"),
                                                                g.mask(piv, "g")), g.const(0.0)), axis3)
        root_ws = g.add(g.n(M.MaterialExpressionObjectPositionWS), to_world(root_l))
        root_xy = g.mask(root_ws, "rg")
        player = op(M.MaterialExpressionAppendVector, _mpc(g, "PlayerX"), _mpc(g, "PlayerY"))
        away = op(M.MaterialExpressionSubtract, root_xy, player)
        dist = g.add(op(M.MaterialExpressionDistance, root_xy, player), k=1.0)            # cm (+1: never 0)
        near = g.sat(g.mul(g.add(g.mul(dist, k=-1.0), k=reach), k=1.0 / (reach - 30.0)))   # 0 at reach .. 1 at 30
        w = g.mul(g.mul(near, near), par("PushCm", push_cm))
        push = g.mul(op(M.MaterialExpressionDivide, away, dist), w)
        wpo = g.add(wpo, op(M.MaterialExpressionAppendVector, push, g.const(0.0)))
    connect_wpo(g, wpo)
    if glow:
        lvl = g.wave01(show_time(g, HALF_HZ), 0.75, 1.0)
        g.emissive(g.mul(g.mul(g.n(M.MaterialExpressionVertexColor), lvl), par("GlowBoost", 1.0)))
    else:
        if baked_texture is None:
            raise RuntimeError(name + ": bodies need the baked crowd texture")
        b_ = g.n(M.MaterialExpressionTextureSampleParameter2D, parameter_name="Baked", texture=baked_texture,
                 sampler_type=M.MaterialSamplerType.SAMPLERTYPE_COLOR)
        if cues is not None:
            lit = g.n(M.MaterialExpressionMultiply)
            g.link(b_, lit, "A", out="RGB")
            g.link(show_light(g, cues, floor=0.04, sweep=1.0), lit, "B")
            g.emissive(lit)
        else:
            g.emissive(b_, "RGB")
    return g.save()


def prepare_vat_texture(tex):
    """The VAT import settings (dino_materials.prepare_vat_texture: cooked bit-exact as RGBA16F for Android_ASTC)."""
    for k, v in (("lod_group", unreal.TextureGroup.TEXTUREGROUP_16_BIT_DATA),
                 ("compression_settings", unreal.TextureCompressionSettings.TC_HDR), ("srgb", False),
                 ("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS),
                 ("filter", unreal.TextureFilter.TF_NEAREST), ("never_stream", True),
                 ("address_x", unreal.TextureAddress.TA_CLAMP), ("address_y", unreal.TextureAddress.TA_CLAMP)):
        tex.set_editor_property(k, v)
    ds = unreal.PerPlatformFloat()
    ds.set_editor_property("default", 1.0)
    tex.set_editor_property("downscale", ds)
    return tex


def prepare_vat_mesh(mesh, uv_channels=5, full_precision_uvs=False):
    """Crowd meshes after the FBX import (dino_materials.prepare_vat_mesh): no lightmap UVs, no reversed index buffer,
    no cooked collision / navigation data, bounds padded for jumps and totems. Raises if the UV channels are missing."""
    sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    n = sub.get_num_uv_channels(mesh, 0)
    if n != uv_channels:
        raise RuntimeError(f"{mesh.get_name()}: {n} UV channels, expected {uv_channels}")
    bs = sub.get_lod_build_settings(mesh, 0)
    bs.set_editor_property("use_full_precision_u_vs", full_precision_uvs)
    bs.set_editor_property("build_reversed_index_buffer", False)
    bs.set_editor_property("generate_lightmap_u_vs", False)
    sub.set_lod_build_settings(mesh, 0, bs)
    if sub.get_num_uv_channels(mesh, 0) != uv_channels:
        raise RuntimeError(f"{mesh.get_name()}: the rebuild changed the UV channels")
    mesh.set_editor_property("has_navigation_data", False)
    body = mesh.get_editor_property("body_setup")
    if body is not None:
        body.set_editor_property("never_needs_cooked_collision_data", True)
    mesh.set_editor_property("positive_bounds_extension", unreal.Vector(100.0, 100.0, 250.0))
    mesh.set_editor_property("negative_bounds_extension", unreal.Vector(100.0, 100.0, 50.0))
    return mesh


def prepare_wpo_mesh(mesh, uv_channels, pad_cm):
    """Any WPO mesh (lasers, bats, ghosts, hands, clock hands): keep its UV channels exact (full precision), pad the
    bounds by how far its vertices travel, no collision / navigation data."""
    sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    n = sub.get_num_uv_channels(mesh, 0)
    if n < uv_channels:
        raise RuntimeError(f"{mesh.get_name()}: {n} UV channels, expected >= {uv_channels}")
    bs = sub.get_lod_build_settings(mesh, 0)
    bs.set_editor_property("use_full_precision_u_vs", True)
    bs.set_editor_property("generate_lightmap_u_vs", False)
    sub.set_lod_build_settings(mesh, 0, bs)
    mesh.set_editor_property("has_navigation_data", False)
    body = mesh.get_editor_property("body_setup")
    if body is not None:
        body.set_editor_property("never_needs_cooked_collision_data", True)
    mesh.set_editor_property("positive_bounds_extension", unreal.Vector(pad_cm, pad_cm, pad_cm))
    mesh.set_editor_property("negative_bounds_extension", unreal.Vector(pad_cm, pad_cm, pad_cm))
    return mesh


def prepare_wpo_actor(component):
    """WPO always evaluated, never distance-disabled (dino_materials.prepare_vat_actor)."""
    component.set_editor_property("evaluate_world_position_offset", True)
    component.set_editor_property("world_position_offset_disable_distance", 0)


def instance(name, folder, parent, scalars=None, textures=None):
    """A parameter-only instance of one of our masters (no static switches: it shares the parent's shaders)."""
    path = f"{folder}/{name}"
    if eal.does_asset_exist(path):
        eal.delete_asset(path)
    mi = tools.create_asset(name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, parent)
    for k, v in (scalars or {}).items():
        mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
    for k, v in (textures or {}).items():
        mel.set_material_instance_texture_parameter_value(mi, k, v)
    mel.update_material_instance(mi)
    eal.save_asset(path)
    return mi
