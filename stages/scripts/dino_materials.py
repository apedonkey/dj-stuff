# Animated materials for the Dino Stage (Meta fork editor only: they compile to OUR shaders, which ship in the chunk's
# ShaderArchive; the device gate passed 2026-10-05 with M_ModTest). Pixel-shader effects only (no World Position Offset:
# Python can't wire it in 5.4). Tempo is fixed at 140 BPM, half-time (dubstep), until the mod feeds the real beat.
# Every factory: make(name, folder, **inputs) -> a saved UMaterial. Built with MaterialEditingLibrary expressions.
import unreal

mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
# The user: "im usually in between 128 and 150 bpm. mostly heavy dubstep" (2026-10-06): 140 BPM with a half-time feel,
# so the pulses land on the kick (beat 1) and snare (beat 3): HALF_HZ.
BEAT_HZ = 140.0 / 60.0
HALF_HZ = BEAT_HZ / 2
SHOW_LOOP_S = 32 * 4 / BEAT_HZ          # the light show (show.py show_program): 32 bars at 140 BPM = 54.9 s


class G:
    """A tiny graph builder: nodes laid out left to right, links checked."""

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

    # --- small vocabulary
    def const(self, v):
        return self.n(unreal.MaterialExpressionConstant, r=float(v))

    def color(self, rgb):
        return self.n(unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(*rgb, 1.0))

    def time(self, scale=1.0):
        t = self.n(unreal.MaterialExpressionTime)
        return t if scale == 1.0 else self.link(t, self.n(unreal.MaterialExpressionMultiply, const_b=float(scale)), "A")

    def mul(self, a, b=None, k=None):
        e = self.n(unreal.MaterialExpressionMultiply, **({"const_b": float(k)} if k is not None else {}))
        self.link(a, e, "A")
        if b is not None:
            self.link(b, e, "B")
        return e

    def add(self, a, b=None, k=None):
        e = self.n(unreal.MaterialExpressionAdd, **({"const_b": float(k)} if k is not None else {}))
        self.link(a, e, "A")
        if b is not None:
            self.link(b, e, "B")
        return e

    def sine(self, a):                                   # sin(2*pi*a)
        return self.link(a, self.n(unreal.MaterialExpressionSine, period=1.0))

    def frac(self, a):
        return self.link(a, self.n(unreal.MaterialExpressionFrac))

    def wave01(self, a, lo, hi):                         # lo..hi following sin(2*pi*a)
        return self.add(self.mul(self.sine(a), k=(hi - lo) / 2), k=(hi + lo) / 2)

    def world(self, mask):                               # absolute world position (cm), masked "x"/"y"/"z"/"xz"...
        wp = self.n(unreal.MaterialExpressionWorldPosition)
        cm = self.n(unreal.MaterialExpressionComponentMask, r="x" in mask, g="y" in mask, b="z" in mask, a=False)
        return self.link(wp, cm)

    def tex(self, texture, uv=None):
        s = self.n(unreal.MaterialExpressionTextureSample, texture=texture,
                   sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
        if uv is not None:
            self.link(uv, s, "UVs")
        return s

    def emissive(self, e, out=""):
        if not mel.connect_material_property(e, out, unreal.MaterialProperty.MP_EMISSIVE_COLOR):
            raise RuntimeError(self.path + ": emissive connect failed")

    def opacity(self, e, out=""):
        if not mel.connect_material_property(e, out, unreal.MaterialProperty.MP_OPACITY):
            raise RuntimeError(self.path + ": opacity connect failed")

    def param(self, name, value):
        return self.n(unreal.MaterialExpressionScalarParameter, parameter_name=name, default_value=float(value))

    def save(self):
        mel.recompile_material(self.m)
        eal.save_asset(self.path)
        unreal.log(f"[DINO] material {self.path}: {mel.get_num_material_expressions(self.m)} expressions")
        return self.m


def cue_level(g, cues, row):
    """Level of light-show row `row` (an expression) right now. T_DinoCues: 32 bars x 16 rows, linear data, nearest:
    R = level, G = strobe flag (a 10 Hz square), B = beat-pulse flag (a decaying pulse on beats 1 and 3, half-time)."""
    t = g.time()
    if SHOW_MPC is not None:                                          # the mod restarts the show at its drop on landing
        t = g.add(t, show_mpc(g, "ShowOffset"))
    bar = g.link(g.mul(g.frac(g.mul(t, k=1.0 / SHOW_LOOP_S)), k=32.0), g.n(unreal.MaterialExpressionFloor))
    u = g.mul(g.add(bar, k=0.5), k=1.0 / 32.0)
    v = g.mul(g.add(row, k=0.5), k=1.0 / 16.0)
    uv = g.n(unreal.MaterialExpressionAppendVector)
    g.link(u, uv, "A")
    g.link(v, uv, "B")
    smp = g.n(unreal.MaterialExpressionTextureSample, texture=cues,
              sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    g.link(uv, smp, "UVs")

    def ch(name):                                                     # one output channel as a scalar node
        m = g.n(unreal.MaterialExpressionMultiply, const_b=1.0)
        g.link(smp, m, "A", out=name)
        return m
    lvl, stf, puf = ch("R"), ch("G"), ch("B")
    # strobe flag: a soft 2 Hz blink at most (comfort: no flicker above ~3 Hz; show.py sets no strobes now anyway)
    sq = g.wave01(g.mul(t, k=2.0), 0.4, 1.0)
    strobe = g.add(g.mul(stf, g.add(sq, k=-1.0)), k=1.0)                                       # 1 + G (sq - 1)
    ph = g.frac(g.mul(t, k=HALF_HZ))                                                           # beats 1 and 3
    inv = g.add(g.mul(ph, k=-1.0), k=1.0)
    env = g.add(g.mul(g.mul(inv, inv), k=0.4), k=0.6)                                          # gentle: 0.6 + 0.4 (1-ph)^2
    pulse = g.add(g.mul(puf, g.add(env, k=-1.0)), k=1.0)                                       # 1 + B (env - 1)
    out = g.mul(g.mul(lvl, strobe), pulse)
    if SHOW_MPC is not None:                                          # the giant intro's blackout
        out = g.mul(out, show_mpc(g, "ShowLevel"))
    return out


WASH_ROW = 1   # show.py CUE_ROWS["wash"]: the show's light on the set and the crowd
SHOW_MPC = None   # MPC_DinoGiant when build_dino made it: ShowLevel / ShowOffset drive every show light (the giant intro)
SHOW_DIM_FLOOR = 0.15   # bulbs, pillars, booth LEDs during the blackout (dim, not dead)


def show_mpc(g, pname):
    return g.n(unreal.MaterialExpressionCollectionParameter, collection=SHOW_MPC, parameter_name=pname)


def show_mpc_or(g, pname, default):
    """SHOW_MPC's scalar pname, or a constant when there is no collection or it lacks that scalar (v14b: ShowNextBar is
    newer than the club's MPC_ClubShow, which imports these materials too)"""
    if SHOW_MPC is None:
        return g.const(default)
    names = {str(p.get_editor_property("parameter_name")) for p in SHOW_MPC.get_editor_property("scalar_parameters")}
    return show_mpc(g, pname) if pname in names else g.const(default)


def show_dim(g, e):
    """e x (floor + (1 - floor) ShowLevel): decorative lights dim in the giant intro's blackout."""
    if SHOW_MPC is None:
        return e
    return g.mul(e, g.add(g.mul(show_mpc(g, "ShowLevel"), k=1.0 - SHOW_DIM_FLOOR), k=SHOW_DIM_FLOOR))


NIGHT_GAIN = 0.6   # the user, 2026-10-09: "it still needs to be darker on stage and in the crowd i think": every baked
                   # surface (the set via show_light, the crowd, the field and the festival grounds' MICs) x this


def show_light(g, cues, floor=0.08, sweep=0.0):
    """Night: how much of the baked light shows right now. floor (near black) between hits, up to 1 when the show's wash
    row fires (beat flashes, strobes, the drop); all of it x NIGHT_GAIN. sweep > 0: bands of light travel across
    (washes over the crowd)."""
    lvl = cue_level(g, cues, g.const(WASH_ROW))
    if sweep > 0:
        ph = g.add(g.time(0.35), g.add(g.mul(g.world("x"), k=0.0025 * sweep), g.mul(g.world("y"), k=0.0012 * sweep)))
        lvl = g.mul(lvl, g.wave01(ph, 0.35, 1.0))
    return g.mul(g.add(g.mul(lvl, k=1.0 - floor), k=floor), k=NIGHT_GAIN)


def show_lit(name, folder, texture, cues, floor=0.08, sweep=0.0, two_sided=False):
    """A baked surface of the set (bones, rig, deck, riser, plants) lit only by the show: texture x show_light."""
    g = G(name, folder, two_sided=two_sided)
    g.emissive(g.mul(g.tex(texture), show_light(g, cues, floor, sweep)))
    return g.save()


def show_lit_2s(name, folder, texture, cues):
    return show_lit(name, folder, texture, cues, two_sided=True)


def led_wall(name, folder, texture):
    """The red LED wall: the pattern scrolls sideways, and the whole wall pumps on the beat."""
    g = G(name, folder)
    uv = g.n(unreal.MaterialExpressionPanner, speed_x=0.035, speed_y=0.0)
    s = g.tex(texture, uv)
    pump = g.wave01(g.time(BEAT_HZ), 0.7, 1.0)
    g.emissive(g.mul(s, pump))
    return g.save()


def moon(name, folder, texture):
    """The moon screen: the lava disc turns slowly and breathes."""
    g = G(name, folder)
    rot = g.n(unreal.MaterialExpressionRotator, center_x=0.5, center_y=0.5, speed=0.04)
    s = g.tex(texture, rot)
    breathe = g.wave01(g.time(BEAT_HZ / 4), 0.8, 1.0)
    g.emissive(g.mul(s, breathe))
    return g.save()


def chase(name, folder, rgb, speed=0.6, scale=0.004, floor=0.25):
    """Bulb strings: a light runs along them (phase from world position), with a soft tail."""
    g = G(name, folder)
    phase = g.add(g.mul(g.add(g.world("x"), g.world("z")), k=scale), g.time(-speed))
    head = g.frac(phase)
    tail = g.mul(g.mul(head, head), head)                  # head^3: a bright head and a fading tail
    lvl = g.add(g.mul(tail, k=1.0 - floor), k=floor)
    g.emissive(show_dim(g, g.mul(g.color(rgb), lvl)))
    return g.save()


def strobe_tex(name, folder, texture, rate=HALF_HZ, spread=0.003, cues=None, row=10):
    """Fixture lenses: they flash on the beat, each a little offset by its position. With cues: they follow the light
    show's lens row instead (dark when the beams are off)."""
    g = G(name, folder)
    s = g.tex(texture)
    if cues is not None:
        lvl = g.add(g.mul(cue_level(g, cues, g.const(row)), k=0.94), k=0.06)
        g.emissive(g.mul(s, lvl))
        return g.save()
    ph = g.add(g.time(rate), g.mul(g.world("x"), k=spread))
    w = g.sine(ph)
    sharp = g.mul(g.mul(g.add(w, k=1.0), k=0.5), g.mul(g.add(w, k=1.0), k=0.5))   # ((sin+1)/2)^2
    lvl = g.add(g.mul(sharp, k=0.65), k=0.35)
    g.emissive(g.mul(s, lvl))
    return g.save()


def beams_material(name, folder, texture, rate=BEAT_HZ / 4, spread=0.0008, cues=None):
    """Translucent beams/halos: color from the texture, alpha = texture alpha x a breathing level that ripples across
    the fans (phase from world x). With cues: x the light show level of row CueRow (a parameter: one instance per
    beam group)."""
    g = G(name, folder, translucent=True, two_sided=True)
    s_ = g.tex(texture)
    ph = g.add(g.time(rate), g.mul(g.world("x"), k=spread))
    lvl = g.wave01(ph, 0.65 if cues is not None else 0.45, 1.0)
    if cues is not None:
        lvl = g.mul(lvl, cue_level(g, cues, g.param("CueRow", 13)))
    op = g.n(unreal.MaterialExpressionMultiply)
    g.link(s_, op, "A", out="A")
    g.link(lvl, op, "B")
    g.emissive(s_, "RGB")
    g.opacity(op)
    return g.save()


def pillars(name, folder, rgb_a=(0.2, 0.9, 1.0), rgb_b=(1.0, 0.15, 0.75)):
    """LED pillars: a color gradient sweeping up the pillars on the beat."""
    g = G(name, folder)
    ph = g.add(g.mul(g.world("z"), k=0.0025), g.time(-BEAT_HZ / 2))
    t = g.wave01(ph, 0.0, 1.0)
    lerp = g.n(unreal.MaterialExpressionLinearInterpolate)
    g.link(g.color(rgb_a), lerp, "A")
    g.link(g.color(rgb_b), lerp, "B")
    g.link(t, lerp, "Alpha")
    g.emissive(show_dim(g, lerp))
    return g.save()


def scroll_tex(name, folder, texture, speed_x=0.08, pump=(0.75, 1.0)):
    """Booth front: its bars scroll sideways and pump on the kick and snare (half-time)."""
    g = G(name, folder)
    uv = g.n(unreal.MaterialExpressionPanner, speed_x=speed_x, speed_y=0.0)
    s = g.tex(texture, uv)
    g.emissive(show_dim(g, g.mul(s, g.wave01(g.time(HALF_HZ), *pump))))
    return g.save()


def connect_wpo(g, expr):
    """World Position Offset: Python's MaterialProperty enum hides it in 5.4, so the ModMaterialTools editor plugin
    (Meta project Plugins/ModMaterialTools, built 2026-10-05) wires it."""
    lib = getattr(unreal, "ModMaterialToolsLibrary", None)
    if lib is None or not lib.connect_world_position_offset(g.m, expr, ""):
        raise RuntimeError(g.path + ": WPO connect failed (ModMaterialTools plugin loaded?)")


def _sat(g, x):
    return g.link(x, g.n(unreal.MaterialExpressionClamp, min_default=0.0, max_default=1.0))


def _lerp(g, a, b, alpha):
    e = g.n(unreal.MaterialExpressionLinearInterpolate)
    g.link(a, e, "A")
    g.link(b, e, "B")
    g.link(alpha, e, "Alpha")
    return e


def _cue_rgb(g, cues, row, u):
    """The cue table's RGB at column u (0..1) of row `row`, readable in the vertex shader (mip 0)."""
    uv = g.n(unreal.MaterialExpressionAppendVector)
    g.link(u, uv, "A")
    g.link(g.const((row + 0.5) / 16.0), uv, "B")
    smp = g.n(unreal.MaterialExpressionTextureSample, texture=cues,
              sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
              mip_value_mode=unreal.TextureMipValueMode.TMVM_MIP_LEVEL, const_mip_value=0)
    g.link(uv, smp, "UVs")
    return g.link(smp, g.n(unreal.MaterialExpressionComponentMask, r=True, g=True, b=True, a=False), out="RGB")


LASER_GAIN = 2.2     # additive lasers: beam texture alpha x color x level x this (LDR: MobileHDR is off, so >1 saturates)

# The pattern engine (show.py, "the laser show v2"), per laser vertex. Two Custom HLSL nodes: LaserMotion -> (pan P, tilt
# Q, alpha) and LaserColor -> RGB; WPO turns the beam by P, Q about its unit's aperture, and color + alpha reach the pixel
# shader through one VertexInterpolator (so the translucent pixels only multiply). Both read show.py's textures with
# explicit mip 0 (vertex shader): T_DinoLaserProg (bar x variant -> pattern id, color id, level), T_DinoLaserLib
# (pattern / color rows, byte-encoded as show._byte), and T_DinoCues (the group's level row).
_LASER_CLOCK = """
float loopf = Ts * %INV_LOOP%;
float barf = frac(loopf) * 32.0;
float bar = floor(barf);
float fb = barf - bar;
float bx = saturate((fb - 0.85) / 0.15);
float bl = bx * bx * (3.0 - 2.0 * bx);
float vrow = fmod(floor(Var + 0.5) + floor(loopf), 8.0);
float tb = Ts * %INV_BAR%;
float benv = 1.0 - frac(tb * 4.0);
benv = benv * benv;
float rside = X < 0.5 ? 0.0 : 1.0;
"""
LASER_MOTION_HLSL = _LASER_CLOCK + """
float side = rside * 2.0 - 1.0;
float grp = floor(Grp + 0.5);
float4 acc0 = float4(0.0, 0.0, 0.0, 0.0);
float4 acc1 = float4(0.0, 0.0, 0.0, 0.0);
for (int k = 0; k < 2; k++)
{
    float pbar = k == 0 ? bar : (NextBar >= 0.0 ? NextBar : fmod(bar + 1.0, 32.0));   // v14b: a section loops
    float4 pr = Texture2DSampleLevel(Prog, ProgSampler, float2((pbar + 0.5) / 32.0, (vrow + 0.5) / 8.0), 0.0);
    float prow = (floor(pr.r * 255.0 + 0.5) + 0.5) / 64.0;
    float4 t0 = Texture2DSampleLevel(Lib, LibSampler, float2(0.0454545, prow), 0.0);
    float4 t1 = Texture2DSampleLevel(Lib, LibSampler, float2(0.1363636, prow), 0.0);
    float4 t2 = Texture2DSampleLevel(Lib, LibSampler, float2(0.2272727, prow), 0.0);
    float4 t3 = Texture2DSampleLevel(Lib, LibSampler, float2(0.3181818, prow), 0.0);
    float4 t4 = Texture2DSampleLevel(Lib, LibSampler, float2(0.4090909, prow), 0.0);
    float4 t5 = Texture2DSampleLevel(Lib, LibSampler, float2(0.5, prow), 0.0);
    float4 t6 = Texture2DSampleLevel(Lib, LibSampler, float2(0.5909091, prow), 0.0);
    float4 t7 = Texture2DSampleLevel(Lib, LibSampler, float2(0.6818182, prow), 0.0);
    float sp = sin(6.2831853 * (t0.z * 15.9375 * tb + (t1.x * 2.0 - 1.0) * U + (t1.y * 4.0 - 2.0) * X
                                + t1.w * 0.99609375 * rside));
    float pan = (t0.x * 2.0 - 1.0) + t0.y * sign(sp) * pow(abs(sp) + 0.00001, 1.0 - 0.8 * t0.w);
    pan += (t2.x * 2.0 - 1.0) * U * (0.5 + 0.5 * sin(6.2831853 * t2.y * 15.9375 * tb));
    pan *= lerp(1.0, side, t1.z);
    float sq = sin(6.2831853 * (t3.x * 15.9375 * tb + (t3.z * 2.0 - 1.0) * U + (t3.w * 4.0 - 2.0) * X
                                + t4.x * 0.99609375));
    float tilt = (t2.z * 2.0 - 1.0) + t2.w * sign(sq) * pow(abs(sq) + 0.00001, 1.0 - 0.8 * t3.y);
    pan += ((t6.z * 2.0 - 1.0) * U + (t6.w * 2.0 - 1.0) * side) * HitMajor;     // fan burst / mirrored swing on hits
    tilt += (t6.y * 2.0 - 1.0) * HitMajor;                                       // tilt pop on hits
    pan += (t7.x * 2.0 - 1.0) * U * Bass;                                        // fans open with the bass
    tilt += (t7.y * 2.0 - 1.0) * Bass;                                           // beams rise with it
    float ch = frac(t4.y * 15.9375 * tb + (t4.w * 2.0 - 1.0) * U + (t5.x * 4.0 - 2.0) * X);
    float lit = t4.z > 0.996 ? 1.0 : smoothstep(t4.z + 0.03, t4.z - 0.03, ch);
    float gmask = floor(t5.z * 255.0 + 0.5);
    gmask = gmask < 0.5 ? floor(pr.a * 255.0 + 0.5) : gmask;                   // v12: else the bar's scene (show.py)
    float fam = grp < 0.5 ? 0.0 : (grp < 4.5 ? 1.0 : grp - 3.0);                // fan, horns, towers, lip, mouth, delay
    float gbit = gmask < 0.5 ? 1.0 : fmod(floor(gmask / exp2(fam)), 2.0);
    gbit = max(gbit, TopLasers);                                                // the TOP look shows every top laser
    float hitv = lerp(1.0, (1.0 - 0.5 * t6.x) + t6.x * (0.5 + HitMajor + 0.4 * HitMinor), HitsOn);
    float vis = lit * (1.0 - t5.y + t5.y * benv) * gbit * pr.b * hitv * (1.0 + t7.z * Bass);
    float4 res = float4(clamp(pan, -1.0, 1.0), clamp(tilt, -1.0, 1.0), vis, t7.w);
    if (k == 0) { acc0 = res; } else { acc1 = res; }
}
float4 mot = lerp(acc0, acc1, bl);
mot.x = clamp(mot.x + 0.6 * U * DropBoom, -1.0, 1.0);                           // the drop: every fan opens,
mot.y = clamp(mot.y + 0.2 * DropBoom, -1.0, 1.0);                               // lifts, and every beam lights
mot.z = max(mot.z, DropBoom);
float crow = grp + 3.0 + (grp > 4.5 ? 3.0 : 0.0) + (grp > 6.5 ? 1.0 : 0.0);     // rows 3-7, 11, 12, 14, 15
float4 cue = Texture2DSampleLevel(Cues, CuesSampler, float2((bar + 0.5) / 32.0, (crow + 0.5) / 16.0), 0.0);
float hph = frac(Ts * %HALF_HZ%);
float cpulse = 1.0 + cue.b * (0.4 * (1.0 - hph) * (1.0 - hph) - 0.4);
float lvl = max(cue.r * cpulse * ShowLevel, ((grp > 0.5 && grp < 5.5) || (grp > 6.5 && grp < 7.5)) ? TopLasers : 0.0);
lvl = max(lvl, mot.w * Bass * ShowLevel);                                        // the bass keeps the lasers going
float flick = 0.925 + 0.075 * sin(6.2831853 * (T * 9.0 + Phase));
float alpha = Kind > 0.5 ? lvl * (0.35 + 0.65 * mot.z) : lvl * mot.z * flick;
return Kind > 0.5 ? float3(0.0, 0.0, alpha) : float3(mot.x, mot.y, alpha);
"""
LASER_COLOR_HLSL = _LASER_CLOCK + """
float3 col0 = float3(1.0, 1.0, 1.0);
float3 col1 = float3(1.0, 1.0, 1.0);
for (int k = 0; k < 2; k++)
{
    float pbar = k == 0 ? bar : (NextBar >= 0.0 ? NextBar : fmod(bar + 1.0, 32.0));   // v14b: a section loops
    float4 pr = Texture2DSampleLevel(Prog, ProgSampler, float2((pbar + 0.5) / 32.0, (vrow + 0.5) / 8.0), 0.0);
    float crow = (floor(pr.g * 255.0 + 0.5) + 0.5) / 64.0;
    float4 ta = Texture2DSampleLevel(Lib, LibSampler, float2(0.7727273, crow), 0.0);
    float4 tc = Texture2DSampleLevel(Lib, LibSampler, float2(0.8636364, crow), 0.0);
    float4 th = Texture2DSampleLevel(Lib, LibSampler, float2(0.9545455, crow), 0.0);
    float tq = tc.y > 0.5 ? floor(tb * 4.0) * 0.25 : tb;
    float hue = frac(ta.x * 0.99609375 + (ta.y * 4.0 - 2.0) * tq + (ta.z * 2.0 - 1.0) * U + (ta.w * 4.0 - 2.0) * X
                     + tc.x * 0.99609375 * rside + th.x * 0.99609375 * HitCount);
    float3 rgb = saturate(abs(frac(hue + float3(1.0, 0.6666667, 0.3333333)) * 6.0 - 3.0) - 1.0);
    rgb = lerp(float3(1.0, 1.0, 1.0), rgb, tc.z);
    rgb = lerp(rgb, float3(1.0, 1.0, 1.0), tc.w * benv);
    rgb = lerp(rgb, float3(1.0, 1.0, 1.0), th.y * HitMajor);
    if (k == 0) { col0 = rgb; } else { col1 = rgb; }
}
return lerp(lerp(col0, col1, bl), float3(1.0, 1.0, 1.0), 0.6 * DropBoom);
"""


def _hlsl(code):
    return (code.replace("%INV_LOOP%", f"{1.0 / SHOW_LOOP_S:.9f}").replace("%INV_BAR%", f"{32.0 / SHOW_LOOP_S:.9f}")
            .replace("%HALF_HZ%", f"{HALF_HZ:.9f}"))


def _custom(g, desc, code, inputs):
    """A Custom HLSL node returning float3, its inputs wired by name: [(name, expression)]. Texture objects arrive as
    <name> + <name>Sampler."""
    c = g.n(unreal.MaterialExpressionCustom)
    c.set_editor_property("code", _hlsl(code))
    c.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    c.set_editor_property("description", desc)
    ins = []
    for nm, _ in inputs:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", nm)
        ins.append(ci)
    c.set_editor_property("inputs", ins)
    for nm, src in inputs:
        g.link(src, c, nm)
    return c


def laser_show(name, folder, texture, cues=None, prog=None, lib=None):
    """The laser show v2 (2026-10-08): additive lasers moved by WPO from show.py's pattern engine. Per-vertex data from
    grounds/atmosphere.py (every V read back as 1 - v: the FBX import flips V on all channels), UV channels: 1 = pivot (x, y) and 2 = (pivot z, phase) in Blender meters (z already dropped by
    dino_stage.py), 3 = (pan, tilt) amplitude in degrees, 4 = (group, u), 5 = (x, kind). Blender m -> mesh local cm =
    (x, -y, z) * 100 (our FBX import); TransformPosition takes the pivot into the world (the level actor is turned 180).
    Pan turns about world Z through the pivot, then tilt about the horizontal axis across the beam; both are offsets for
    WPO (RotateAboutAxis angles are in turns). Needs cues, prog and lib (T_DinoCues, T_DinoLaserProg, T_DinoLaserLib)."""
    g = G(name, folder, translucent=True, two_sided=True)
    g.m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    uv = {i: g.n(unreal.MaterialExpressionTextureCoordinate, coordinate_index=i) for i in (1, 2, 3, 4, 5)}

    def mask(src, r, gg, b=False):
        return g.link(src, g.n(unreal.MaterialExpressionComponentMask, r=r, g=gg, b=b, a=False))

    def vread(src):
        """A data channel's V as atmosphere.py wrote it. Unreal's FBX import stores 1 - v on every UV channel, so read
        it back as 1 - v (2026-10-09: unread, every beam came in as kind 1, an aperture: frozen and always lit)."""
        return g.add(g.mul(mask(src, False, True), k=-1.0), k=1.0)

    def texobj(t):
        return g.n(unreal.MaterialExpressionTextureObject, texture=t,
                   sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    tt = g.time()
    if SHOW_MPC is not None:
        ts = g.add(tt, show_mpc(g, "ShowOffset"))
        var, show_lvl, top = show_mpc(g, "LaserVariant"), show_mpc(g, "ShowLevel"), show_mpc(g, "TopLasers")
        hmaj, hmin, hcnt, boom, hon, bass = (show_mpc(g, n) for n in ("HitMajor", "HitMinor", "HitCount", "DropBoom",
                                                                       "HitsOn", "Bass"))
    else:
        ts, var, show_lvl, top = tt, g.const(0.0), g.const(1.0), g.const(0.0)
        hmaj = hmin = hcnt = boom = hon = bass = g.const(0.0)
    t_prog, t_lib, t_cues = texobj(prog), texobj(lib), texobj(cues)
    u_, x_ = vread(uv[4]), mask(uv[5], True, False)
    nxt = show_mpc_or(g, "ShowNextBar", -1.0)                      # v14b: the bar that really plays next (-1: bar+1)
    motion = _custom(g, "LaserMotion", LASER_MOTION_HLSL, [
        ("Prog", t_prog), ("Lib", t_lib), ("Cues", t_cues), ("Ts", ts), ("T", tt), ("Var", var), ("U", u_),
        ("X", x_), ("Grp", mask(uv[4], True, False)), ("Kind", vread(uv[5])),
        ("Phase", vread(uv[2])), ("ShowLevel", show_lvl), ("TopLasers", top), ("HitMajor", hmaj),
        ("HitMinor", hmin), ("DropBoom", boom), ("HitsOn", hon), ("Bass", bass), ("NextBar", nxt)])
    color = _custom(g, "LaserColor", LASER_COLOR_HLSL, [
        ("Prog", t_prog), ("Lib", t_lib), ("Ts", ts), ("Var", var), ("U", u_), ("X", x_), ("HitMajor", hmaj),
        ("HitCount", hcnt), ("DropBoom", boom), ("NextBar", nxt)])
    P, Q, A = mask(motion, True, False), mask(motion, False, True), \
        g.link(motion, g.n(unreal.MaterialExpressionComponentMask, r=False, g=False, b=True, a=False))
    # the pivot in the world
    px = g.mul(mask(uv[1], True, False), k=100.0)
    py = g.mul(vread(uv[1]), k=-100.0)
    pz = g.mul(mask(uv[2], True, False), k=100.0)
    xy = g.n(unreal.MaterialExpressionAppendVector)
    g.link(px, xy, "A")
    g.link(py, xy, "B")
    pl = g.n(unreal.MaterialExpressionAppendVector)
    g.link(xy, pl, "A")
    g.link(pz, pl, "B")
    pivot = g.n(unreal.MaterialExpressionTransformPosition,
                transform_source_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL,
                transform_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD)
    g.link(pl, pivot, "")
    wp = g.n(unreal.MaterialExpressionWorldPosition)
    # pan: about world Z, angle (turns) = -pan_deg/360 * P. Negated: the FBX import mirrors Y, which flips the turn sense
    # (M Rz(a) M = Rz(-a)), so -pan here moves the lasers exactly as atmosphere.laser_pose_pq() previews. Tilt keeps its
    # sign: the per-vertex axis (v x Z) mirrors as a pseudo-vector and cancels the flip.
    pan = g.mul(g.mul(P, mask(uv[3], True, False)), k=-1.0 / 360.0)
    zaxis = g.n(unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(0.0, 0.0, 1.0, 1.0))
    r1 = g.n(unreal.MaterialExpressionRotateAboutAxis)
    g.link(zaxis, r1, "NormalizedRotationAxis")
    g.link(pan, r1, "RotationAngle")
    g.link(pivot, r1, "PivotPoint")
    g.link(wp, r1, "Position")
    p1 = g.add(wp, r1)
    # tilt: about the horizontal axis across the beam, from the pivot to this vertex (+ a 1 cm nudge so a vertex sitting
    # on the pivot never normalizes a zero vector)
    v = g.n(unreal.MaterialExpressionSubtract)
    g.link(p1, v, "A")
    g.link(pivot, v, "B")
    nudge = g.n(unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(0.0, -1.0, 0.0, 1.0))
    cr = g.n(unreal.MaterialExpressionCrossProduct)
    g.link(g.add(v, nudge), cr, "A")
    g.link(zaxis, cr, "B")
    ax2 = g.link(cr, g.n(unreal.MaterialExpressionNormalize))
    tilt = g.mul(g.mul(Q, vread(uv[3])), k=1.0 / 360.0)
    r2 = g.n(unreal.MaterialExpressionRotateAboutAxis)
    g.link(ax2, r2, "NormalizedRotationAxis")
    g.link(tilt, r2, "RotationAngle")
    g.link(pivot, r2, "PivotPoint")
    g.link(p1, r2, "Position")
    connect_wpo(g, g.add(r1, r2))
    # color + alpha: computed per vertex, handed to the pixel shader
    c4 = g.n(unreal.MaterialExpressionAppendVector)
    g.link(color, c4, "A")
    g.link(A, c4, "B")
    vi = g.link(c4, g.n(unreal.MaterialExpressionVertexInterpolator))
    rgb = mask(vi, True, True, True)
    alpha = g.link(vi, g.n(unreal.MaterialExpressionComponentMask, r=False, g=False, b=False, a=True))
    s_ = g.tex(texture)                                    # the white column: RGB white, the beam's profile in alpha
    g.emissive(_beam_emissive(g, s_, rgb, alpha))
    return g.save()


def _beam_emissive(g, s_, rgb, alpha):
    """rgb x alpha x the texture's alpha profile x LASER_GAIN (additive)."""
    prof = g.n(unreal.MaterialExpressionMultiply, const_b=LASER_GAIN)
    g.link(s_, prof, "A", out="A")
    return g.mul(g.mul(rgb, alpha), prof)


# ------------------------------------------------------------------------------------- v13: the moving heads move
# (the user, 2026-10-09: "neighther do the lights!"). Per-vertex data as the lasers' (atmosphere.STAGE_MOVES, V read back
# as 1 - v): UV1 pivot (x, y) and UV2 (pivot z, phase) in Blender m, UV3 (pan, tilt) amplitude deg, UV4 (rest yaw deg,
# u), UV5 (x, 0). A fixture's head, yoke, lens, glow and beam all carry the same values, so they move as one.
MOVER_FMAX = 2.0     # cycles a bar at most (atmosphere.MOVER_FMAX): heads sweep, they don't buzz
MOVER_MOTION_HLSL = _LASER_CLOCK + """
float side = rside * 2.0 - 1.0;
float2 acc0 = float2(0.0, 0.0);
float2 acc1 = float2(0.0, 0.0);
for (int k = 0; k < 2; k++)
{
    float pbar = k == 0 ? bar : (NextBar >= 0.0 ? NextBar : fmod(bar + 1.0, 32.0));   // v14b: a section loops
    float4 pr = Texture2DSampleLevel(Prog, ProgSampler, float2((pbar + 0.5) / 32.0, (vrow + 0.5) / 8.0), 0.0);
    float prow = (floor(pr.r * 255.0 + 0.5) + 0.5) / 64.0;
    float4 t0 = Texture2DSampleLevel(Lib, LibSampler, float2(0.0454545, prow), 0.0);
    float4 t1 = Texture2DSampleLevel(Lib, LibSampler, float2(0.1363636, prow), 0.0);
    float4 t2 = Texture2DSampleLevel(Lib, LibSampler, float2(0.2272727, prow), 0.0);
    float4 t3 = Texture2DSampleLevel(Lib, LibSampler, float2(0.3181818, prow), 0.0);
    float4 t4 = Texture2DSampleLevel(Lib, LibSampler, float2(0.4090909, prow), 0.0);
    float4 t6 = Texture2DSampleLevel(Lib, LibSampler, float2(0.5909091, prow), 0.0);
    float4 t7 = Texture2DSampleLevel(Lib, LibSampler, float2(0.6818182, prow), 0.0);
    float f0 = min(t0.z * 15.9375, %FMAX%);
    float f2 = min(t2.y * 15.9375, %FMAX%);
    float f3 = min(t3.x * 15.9375, %FMAX%);
    float sp = sin(6.2831853 * (f0 * tb + (t1.x * 2.0 - 1.0) * U + (t1.y * 4.0 - 2.0) * X + t1.w * 0.99609375 * rside));
    float pan = (t0.x * 2.0 - 1.0) + t0.y * sign(sp) * pow(abs(sp) + 0.00001, 1.0 - 0.8 * t0.w);
    pan += (t2.x * 2.0 - 1.0) * U * (0.5 + 0.5 * sin(6.2831853 * f2 * tb));
    pan *= lerp(1.0, side, t1.z);
    float sq = sin(6.2831853 * (f3 * tb + (t3.z * 2.0 - 1.0) * U + (t3.w * 4.0 - 2.0) * X + t4.x * 0.99609375));
    float tilt = (t2.z * 2.0 - 1.0) + t2.w * sign(sq) * pow(abs(sq) + 0.00001, 1.0 - 0.8 * t3.y);
    pan += ((t6.z * 2.0 - 1.0) * U + (t6.w * 2.0 - 1.0) * side) * HitMajor;
    tilt += (t6.y * 2.0 - 1.0) * HitMajor;
    pan += (t7.x * 2.0 - 1.0) * U * Bass;
    tilt += (t7.y * 2.0 - 1.0) * Bass;
    float2 res = float2(clamp(pan, -1.0, 1.0), clamp(tilt, -1.0, 1.0));
    if (k == 0) { acc0 = res; } else { acc1 = res; }
}
float2 mot = lerp(acc0, acc1, bl);
mot.x = clamp(mot.x + 0.6 * U * DropBoom, -1.0, 1.0);
mot.y = clamp(mot.y + 0.2 * DropBoom, -1.0, 1.0);
return float3(mot.x, mot.y, 0.0);
""".replace("%FMAX%", f"{MOVER_FMAX:.4f}")
# the fixture's tilt axis in the world: its rest direction's horizontal part H0 (world, unit), turned by the pan (turns,
# about world Z as RotateAboutAxis does), crossed with Z
MOVER_AXIS_HLSL = """
float a = 6.2831853 * Pan;
float3 h = H0 * cos(a) + cross(float3(0.0, 0.0, 1.0), H0) * sin(a);
float3 ax = cross(h, float3(0.0, 0.0, 1.0));
return ax / max(length(ax), 0.000001);
"""


def _mover_wpo(g, prog, lib):
    """The moving-head WPO (see MOVER_MOTION_HLSL), wired to the material's World Position Offset."""
    uv = {i: g.n(unreal.MaterialExpressionTextureCoordinate, coordinate_index=i) for i in (1, 2, 3, 4, 5)}

    def mask(src, r, gg, b=False):
        return g.link(src, g.n(unreal.MaterialExpressionComponentMask, r=r, g=gg, b=b, a=False))

    def vread(src):                                    # the FBX import stores 1 - v on every UV channel
        return g.add(g.mul(mask(src, False, True), k=-1.0), k=1.0)

    def texobj(t):
        return g.n(unreal.MaterialExpressionTextureObject, texture=t,
                   sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    tt = g.time()
    if SHOW_MPC is not None:
        ts = g.add(tt, show_mpc(g, "ShowOffset"))
        var, hmaj, boom, bass = (show_mpc(g, n) for n in ("LaserVariant", "HitMajor", "DropBoom", "Bass"))
    else:
        ts, var, hmaj, boom, bass = tt, g.const(0.0), g.const(0.0), g.const(0.0), g.const(0.0)
    motion = _custom(g, "MoverMotion", MOVER_MOTION_HLSL, [
        ("Prog", texobj(prog)), ("Lib", texobj(lib)), ("Ts", ts), ("Var", var), ("U", vread(uv[4])),
        ("X", mask(uv[5], True, False)), ("HitMajor", hmaj), ("DropBoom", boom), ("Bass", bass),
        ("NextBar", show_mpc_or(g, "ShowNextBar", -1.0))])
    P, Q = mask(motion, True, False), mask(motion, False, True)
    # the pivot in the world (Blender m -> mesh local cm (x, -y, z) * 100 -> the level's transform)
    xy = g.n(unreal.MaterialExpressionAppendVector)
    g.link(g.mul(mask(uv[1], True, False), k=100.0), xy, "A")
    g.link(g.mul(vread(uv[1]), k=-100.0), xy, "B")
    pl = g.n(unreal.MaterialExpressionAppendVector)
    g.link(xy, pl, "A")
    g.link(g.mul(mask(uv[2], True, False), k=100.0), pl, "B")
    pivot = g.n(unreal.MaterialExpressionTransformPosition,
                transform_source_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL,
                transform_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD)
    g.link(pl, pivot, "")
    wp = g.n(unreal.MaterialExpressionWorldPosition)
    # pan: about world Z, angle (turns) = -pan_deg/360 * P (the FBX import mirrors Y, as in laser_show)
    pan = g.mul(g.mul(P, mask(uv[3], True, False)), k=-1.0 / 360.0)
    zaxis = g.n(unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(0.0, 0.0, 1.0, 1.0))
    r1 = g.n(unreal.MaterialExpressionRotateAboutAxis)
    g.link(zaxis, r1, "NormalizedRotationAxis")
    g.link(pan, r1, "RotationAngle")
    g.link(pivot, r1, "PivotPoint")
    g.link(wp, r1, "Position")
    p1 = g.add(wp, r1)
    # tilt: about the fixture's own horizontal axis. Its rest yaw (Blender deg, from -Y toward +X) -> the direction in
    # mesh local space (sin, cos, 0) (Blender (sin, -cos, 0), Y mirrored) -> the world through the level's transform
    yaw = g.mul(mask(uv[4], True, False), k=1.0 / 360.0)
    sn = g.link(yaw, g.n(unreal.MaterialExpressionSine, period=1.0))
    cs = g.link(yaw, g.n(unreal.MaterialExpressionCosine, period=1.0))
    hxy = g.n(unreal.MaterialExpressionAppendVector)
    g.link(sn, hxy, "A")
    g.link(cs, hxy, "B")
    hl = g.n(unreal.MaterialExpressionAppendVector)
    g.link(hxy, hl, "A")
    g.link(g.const(0.0), hl, "B")
    h0 = g.n(unreal.MaterialExpressionTransform,
             transform_source_type=unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL,
             transform_type=unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
    g.link(hl, h0, "")
    ax2 = _custom(g, "MoverAxis", MOVER_AXIS_HLSL, [("H0", g.link(h0, g.n(unreal.MaterialExpressionNormalize))),
                                                   ("Pan", pan)])
    tilt = g.mul(g.mul(Q, vread(uv[3])), k=1.0 / 360.0)
    r2 = g.n(unreal.MaterialExpressionRotateAboutAxis)
    g.link(ax2, r2, "NormalizedRotationAxis")
    g.link(tilt, r2, "RotationAngle")
    g.link(pivot, r2, "PivotPoint")
    g.link(p1, r2, "Position")
    connect_wpo(g, g.add(r1, r2))


def mover_beams(name, folder, texture, cues=None, prog=None, lib=None, rate=BEAT_HZ / 4, spread=0.0008):
    """The moving heads' beams and lens glows (SM_DinoMoverBeams / SM_DinoMoverHalos): beams_material's look (texture,
    breathing, the cue row CueRow) and the fixture's move."""
    g = G(name, folder, translucent=True, two_sided=True)
    s_ = g.tex(texture)
    ph = g.add(g.time(rate), g.mul(g.world("x"), k=spread))
    lvl = g.wave01(ph, 0.65 if cues is not None else 0.45, 1.0)
    if cues is not None:
        lvl = g.mul(lvl, cue_level(g, cues, g.param("CueRow", 13)))
    op = g.n(unreal.MaterialExpressionMultiply)
    g.link(s_, op, "A", out="A")
    g.link(lvl, op, "B")
    g.emissive(s_, "RGB")
    g.opacity(op)
    _mover_wpo(g, prog, lib)
    return g.save()


def mover_heads(name, folder, cues=None, prog=None, lib=None, rgb=(0.035, 0.036, 0.04)):
    """The moving heads' yokes and heads (SM_DinoMoverHeads): unlit dark metal (dims with the show like the rig) and the
    fixture's move."""
    g = G(name, folder)
    g.emissive(show_dim(g, g.color(rgb)))
    _mover_wpo(g, prog, lib)
    return g.save()


def mover_lens(name, folder, texture, cues=None, prog=None, lib=None, row=10):
    """The moving heads' lens discs (SM_DinoLenses): strobe_tex's look (the show's lens row) and the fixture's move."""
    g = G(name, folder)
    s = g.tex(texture)
    if cues is not None:
        lvl = g.add(g.mul(cue_level(g, cues, g.const(row)), k=0.94), k=0.06)
    else:
        lvl = g.const(1.0)
    g.emissive(g.mul(s, lvl))
    _mover_wpo(g, prog, lib)
    return g.save()


# ------------------------------------------------------------------------------------------- Crowd V2 (vertex animation)
# Blender: Scripts/Blender/crowd2/crowd2.py build_crowd2() writes SM_DinoCrowd (bodies, baked lighting on UV0),
# SM_DinoPhones (glowing bits: emissive = vertex colour) and T_DinoCrowdVAT.exr + .json (the VAT both meshes play).
# Per-vertex data, as Unreal reads it (crowd2 pre-compensates the FBX importer's V flip, verified in the fork editor):
#   UV1 = (VAT column, clip)   UV2 = (sx cos yaw, sx sin yaw)   UV3 = (mirror * sz, phase)   UV4 = (rate, -)
# The VAT holds offsets in Blender meters; AxisScale (100, -100, 100) maps them to mesh-local cm (our FBX path mirrors
# Y) and Transform (local -> world) turns them with the level actor. Same graph as M_VatCrowd, which ran on the Quest
# (VatTest, chunk 52, 2026-10-05); the data textures need a DATA sampler (16BitData group) and an explicit mip level 0.
def vat_crowd(name, folder, vat_texture, meta, baked_texture=None, glow=False, bpm=140.0, cues=None):
    """Crowd V2 material. meta = the T_DinoCrowdVAT.json dict. Bodies: emissive = baked_texture on UV0. glow=True
    (SM_DinoPhones): emissive = vertex colour x GlowBoost, breathing a little on the beat."""
    M = unreal
    g = G(name, folder)

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
    tc = [g.n(M.MaterialExpressionTextureCoordinate, coordinate_index=i) for i in (1, 2, 3, 4)]
    vid, clip = mask(tc[0], "r"), mask(tc[0], "g")
    c, s = mask(tc[1], "r"), mask(tc[1], "g")
    msz, phase = mask(tc[2], "r"), mask(tc[2], "g")
    rate = mask(tc[3], "r")
    loops = par("LoopRate", bpm / (60.0 * meta["beats_per_clip"]))      # loops per second (1 loop = 2 beats)
    p = g.frac(g.add(g.mul(g.mul(g.time(), loops), rate), phase))     # p = frac(Time * LoopRate * rate + phase)
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
    wpo = g.n(M.MaterialExpressionTransform,
              transform_source_type=M.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL,
              transform_type=M.MaterialVectorCoordTransform.TRANSFORM_WORLD)
    g.link(g.mul(r3, axis3), wpo)
    connect_wpo(g, wpo)
    if glow:
        lvl = g.wave01(g.time(HALF_HZ), 0.75, 1.0)
        g.emissive(g.mul(g.mul(g.n(M.MaterialExpressionVertexColor), lvl), par("GlowBoost", 1.0)))
    else:
        if baked_texture is None:
            raise RuntimeError(name + ": bodies need the baked crowd texture")
        b_ = g.n(M.MaterialExpressionTextureSampleParameter2D, parameter_name="Baked", texture=baked_texture,
                 sampler_type=M.MaterialSamplerType.SAMPLERTYPE_COLOR)
        if cues is not None:                                           # night: dark until the show's light sweeps over them
            lit = g.n(M.MaterialExpressionMultiply)
            g.link(b_, lit, "A", out="RGB")
            g.link(show_light(g, cues, floor=0.06, sweep=1.0), lit, "B")
            g.emissive(lit)
        else:
            g.emissive(b_, "RGB")
    return g.save()


def prepare_vat_texture(tex):
    """T_DinoCrowdVAT import settings (cooked bit-exact as RGBA16F for Android_ASTC in the VatTest). LOD group FIRST:
    changing it resets mip gen + filter. Downscale 1: a no-mip texture otherwise takes its texture group's downscale."""
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
    """Crowd meshes (SM_DinoCrowd / SM_DinoPhones) after the FBX import: no lightmap UVs, no reversed index buffer (the
    actors are never mirrored), no cooked collision / navigation data (static scenery, NoCollision anyway), bounds padded
    for jumps and totems held overhead. 16-bit UVs are enough while the VAT is <= 2048 columns wide (the VAT column
    index stays an exact integer; decode error measured 0.10 cm); full_precision_uvs=True costs ~20 B per vertex.
    Raises if the UV channels did not all arrive."""
    sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    n = sub.get_num_uv_channels(mesh, 0)
    if n != uv_channels:
        raise RuntimeError(f"{mesh.get_name()}: {n} UV channels, expected {uv_channels} (UV0 + VAT UV1..UV4)")
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


def prepare_vat_actor(component):
    """The crowd actors: WPO always evaluated, never distance-disabled (plus NoCollision / no shadows as every actor)."""
    component.set_editor_property("evaluate_world_position_offset", True)
    component.set_editor_property("world_position_offset_disable_distance", 0)


# ---------------------------------------------------------------- the giant intro (the user's lift + floor-length robe)
# MPC_DinoGiant, driven every frame by the mod (hook/dumper.cpp giant_*), all world cm:
#   Height     the lift plate's height above Tribe's floor (0 down .. 545 up)
#   RobeTopX/Y/Z  where the robe hangs from (the DJ's shoulders); RobeOn 0/1 (0 parks the robe under the floor)
#   ButtonGlow 0..1, a short swell after a press (it also sinks the button cap)
#   ShowLevel / ShowOffset / SpotOn: the blackout, the show clock, the follow spot
#   TopLasers  0..1: the horn-tip lasers alone, through the blackout (the mod's song mode, tribemod/song.txt)
GIANT_MPC_PARAMS = {"Height": 0.0, "RobeTopX": 0.0, "RobeTopY": 90.0, "RobeTopZ": 140.0, "RobeOn": 0.0, "ButtonGlow": 0.0,
                    "ShowLevel": 1.0, "ShowOffset": 0.0, "SpotOn": 0.0, "TopLasers": 0.0,
                    "LaserVariant": 0.0,   # LaserVariant (v9): the laser program's variant 0..7, set per song by the mod
                    "HitMajor": 0.0, "HitMinor": 0.0, "HitCount": 0.0, "DropBoom": 0.0, "HitsOn": 0.0,   # v10: the hits
                    "Bass": 0.0,   # v11: the track's bass level (songs/<key>.bass)
                    "ShowPrevBar": -1.0, "ShowNextBar": -1.0}   # v14b: the bars around this one as the song plays them
GIANT_HEM_CENTER = (0.0, 168.0)     # giant.py HEM (cx, cy) in world cm (the level turns 180: world = (-x, y) * 100)
GIANT_ROBE_TOP_R = 28.0             # cm: the ring around the shoulders the robe hangs from
GIANT_BUTTON_TRAVEL = 2.5           # cm the button cap sinks on a press (giant.py marks the cap with UV0.x = 1)


def make_mpc(folder, name, scalars):
    """A MaterialParameterCollection with scalar parameters {name: default} (each new parameter gets its own Id from
    the struct's constructor; Python can't read Id, so the log lists the names)."""
    path = f"{folder}/{name}"
    if eal.does_asset_exist(path):
        eal.delete_asset(path)
    mpc = tools.create_asset(name, folder, unreal.MaterialParameterCollection, unreal.MaterialParameterCollectionFactoryNew())
    params = []
    for k, v in scalars.items():
        p = unreal.CollectionScalarParameter()
        p.set_editor_property("parameter_name", k)
        p.set_editor_property("default_value", float(v))
        params.append(p)
    mpc.set_editor_property("scalar_parameters", params)
    eal.save_asset(path)
    names = [str(p.get_editor_property("parameter_name")) for p in mpc.get_editor_property("scalar_parameters")]
    unreal.log(f"[DINO] {name}: scalars {names}")
    return mpc


def _mpc(g, collection, pname):
    return g.n(unreal.MaterialExpressionCollectionParameter, collection=collection, parameter_name=pname)


def _mask(g, src, ch):
    return g.link(src, g.n(unreal.MaterialExpressionComponentMask, r=ch == "r", g=ch == "g", b=ch == "b", a=False))


def _lift_wpo(g, mpc):
    """z += Height * UV1.x (the lift weight baked by giant.py)."""
    w = _mask(g, g.n(unreal.MaterialExpressionTextureCoordinate, coordinate_index=1), "r")
    up = g.n(unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(0.0, 0.0, 1.0, 1.0))
    return g.mul(up, g.mul(_mpc(g, mpc, "Height"), w))


def giant_lift(name, folder, mpc):
    """The lift plate, telescope and button pedestal: dark gunmetal, unlit."""
    g = G(name, folder)
    g.emissive(g.color((0.028, 0.028, 0.034)))
    connect_wpo(g, _lift_wpo(g, mpc))
    return g.save()


def giant_glow(name, folder, mpc):
    """The button (UV1.y = 1: red, breathing slowly, swells after a press) and the plate's cyan edge strips. The cap
    (UV0.x = 1) sinks GIANT_BUTTON_TRAVEL on a press (the user: "i want the button to actually go down when i press it"):
    the mod sets ButtonGlow to 1 on a press and fades it out over 0.8 s, so min(3 x ButtonGlow, 1) holds the cap down
    ~0.5 s and brings it back up over ~0.3 s."""
    g = G(name, folder)
    vc = g.link(g.n(unreal.MaterialExpressionVertexColor), g.n(unreal.MaterialExpressionComponentMask, r=True, g=True, b=True,
                                                                 a=False))
    button = _mask(g, g.n(unreal.MaterialExpressionTextureCoordinate, coordinate_index=1), "g")
    breathe = g.wave01(g.time(0.4), 0.55, 1.0)                        # 0.4 Hz: calm, nowhere near a flash
    k = g.n(unreal.MaterialExpressionLinearInterpolate, const_a=1.0)
    g.link(breathe, k, "B")
    g.link(button, k, "Alpha")
    glow = _mpc(g, mpc, "ButtonGlow")
    swell = g.add(g.mul(g.mul(button, glow), k=1.5), k=1.0)
    g.emissive(g.mul(g.mul(g.mul(vc, k), swell), k=2.5))
    cap = _mask(g, g.n(unreal.MaterialExpressionTextureCoordinate, coordinate_index=0), "r")
    sink = g.link(g.mul(glow, k=3.0), g.n(unreal.MaterialExpressionClamp, min_default=0.0, max_default=1.0))
    down = g.n(unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(0.0, 0.0, -GIANT_BUTTON_TRAVEL, 1.0))
    connect_wpo(g, g.add(_lift_wpo(g, mpc), g.mul(down, g.mul(cap, sink))))
    return g.save()


def giant_robe(name, folder, mpc):
    """The floor-length robe (giant.py SM_DinoGiantRobe; rest = a 1 m wall on the hem ellipse, UV1 = (h, theta)).
    Each ring is pulled from the hem (world floor, z 0) up toward the shoulders (RobeTop); the horizontal blend
    s^1.4 (s = 1 - h) keeps it slim through the upper body and widens toward the floor (the user's reference photo), then falls to the hem.
    Soft folds sway around it. RobeOn 0 parks it 20 m under the floor. Winding is outward, so from inside (the DJ)
    it is culled."""
    g = G(name, folder)
    uv1 = g.n(unreal.MaterialExpressionTextureCoordinate, coordinate_index=1)
    h, theta = _mask(g, uv1, "r"), _mask(g, uv1, "g")
    wp = g.n(unreal.MaterialExpressionWorldPosition)
    rxy = g.link(wp, g.n(unreal.MaterialExpressionComponentMask, r=True, g=True, b=False, a=False))
    rz = _mask(g, wp, "b")
    hem_c = g.n(unreal.MaterialExpressionConstant2Vector, r=GIANT_HEM_CENTER[0], g=GIANT_HEM_CENTER[1])
    d = g.n(unreal.MaterialExpressionSubtract)
    g.link(rxy, d, "A")
    g.link(hem_c, d, "B")
    dirn = g.link(d, g.n(unreal.MaterialExpressionNormalize))
    top_xy = g.n(unreal.MaterialExpressionAppendVector)
    g.link(_mpc(g, mpc, "RobeTopX"), top_xy, "A")
    g.link(_mpc(g, mpc, "RobeTopY"), top_xy, "B")
    ring = g.add(top_xy, g.mul(dirn, k=GIANT_ROBE_TOP_R))
    s = g.add(g.mul(h, k=-1.0), k=1.0)
    b = g.link(s, g.n(unreal.MaterialExpressionPower, const_exponent=1.4), "Base")
    xy = g.n(unreal.MaterialExpressionLinearInterpolate)
    g.link(ring, xy, "A")
    g.link(rxy, xy, "B")
    g.link(b, xy, "Alpha")
    fold = g.mul(g.mul(g.sine(g.add(g.mul(theta, k=16.0), g.time(0.12))), s), k=7.0)    # cm, more toward the hem
    xy2 = g.add(xy, g.mul(dirn, fold))
    z = g.mul(h, _mpc(g, mpc, "RobeTopZ"))                                               # floor (0) .. shoulders
    target = g.n(unreal.MaterialExpressionAppendVector)
    g.link(xy2, target, "A")
    g.link(z, target, "B")
    on = g.n(unreal.MaterialExpressionSubtract)                                          # target - rest
    g.link(target, on, "A")
    g.link(wp, on, "B")
    park = g.mul(g.n(unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(0.0, 0.0, 1.0, 1.0)),
                 g.add(g.mul(rz, k=-1.0), k=-2000.0))
    wpo = g.n(unreal.MaterialExpressionLinearInterpolate)
    g.link(park, wpo, "A")
    g.link(on, wpo, "B")
    g.link(_mpc(g, mpc, "RobeOn"), wpo, "Alpha")
    connect_wpo(g, wpo)
    shade = g.add(g.mul(g.sine(g.add(g.mul(theta, k=16.0), g.time(0.12))), k=0.25), k=0.75)   # folds: light/dark
    lit = g.mul(g.mul(g.mul(h, h), _mpc(g, mpc, "SpotOn")), k=0.10)    # the follow spot, strongest at the shoulders
    g.emissive(g.mul(g.add(g.color((0.020, 0.016, 0.022)), g.mul(g.color((1.0, 0.92, 0.82)), lit)), shade))
    return g.save()


def giant_spot(name, folder, mpc, texture):
    """The giant intro's follow spot (giant.py SM_DinoGiantSpot): a translucent cone on T_DinoBeam's white column,
    warm white, faded by SpotOn, a slow shimmer for haze; its far end rides up with the lift (UV1.x)."""
    g = G(name, folder, translucent=True, two_sided=True)
    s_ = g.tex(texture)
    shimmer = g.wave01(g.add(g.time(0.15), g.mul(g.world("z"), k=0.002)), 0.8, 1.0)
    op = g.n(unreal.MaterialExpressionMultiply)
    g.link(s_, op, "A", out="A")
    g.link(g.mul(g.mul(_mpc(g, mpc, "SpotOn"), shimmer), k=1.3), op, "B")
    rgb = g.n(unreal.MaterialExpressionMultiply)
    g.link(s_, rgb, "A", out="RGB")
    g.link(g.color((1.0, 0.93, 0.82)), rgb, "B")
    g.emissive(rgb)
    g.opacity(op)
    connect_wpo(g, _lift_wpo(g, mpc))
    return g.save()


def prepare_giant_mesh(mesh, up_cm=1200.0):
    """Lift/glow/robe meshes after the FBX import: the material moves them up to ~12 m and out to the robe's flare,
    so pad the bounds (or the engine culls them at rest size); no collision/nav data."""
    mesh.set_editor_property("has_navigation_data", False)
    body = mesh.get_editor_property("body_setup")
    if body is not None:
        body.set_editor_property("never_needs_cooked_collision_data", True)
    mesh.set_editor_property("positive_bounds_extension", unreal.Vector(300.0, 300.0, up_cm))
    mesh.set_editor_property("negative_bounds_extension", unreal.Vector(300.0, 300.0, 100.0))
    return mesh
