# Animated Dino crowd on Quest 3: design

**Recommendation.** Bake vertex animation textures (VAT) in Blender and play them back with a World Position
Offset (WPO) material on the crowd mesh we already ship: one merged static mesh, 1 draw call, no runtime skinning.
- Each person is a copy of a shared "canonical" person mesh for their detail tier.
- Each vertex carries its own data in UV channels 1 to 3: its VAT column, the person's clip, yaw and scale, a
  mirror flag, and a phase.
- One RGBA16F texture (about 256×128, 256 KB) holds every clip for every tier.
- The per-person baked lighting atlas (UV0) stays exactly as today and moves with the body.

The prototype here (`vat_crowd_proto.py`) builds the near-tier person, two dances, the VAT and a test crowd in
exactly this data layout. It verifies them: 0.048 cm max error from the texture, and 0.05 cm (full-precision UVs) or
0.09 cm (16-bit UVs) through a copy of the material math.

**Prerequisite.** We must be able to ship our OWN material. That is still blocked until the Meta-fork build passes
the UMaterial schema check.

Labels:
- **[observed]**: measured or read in this project.
- **[S#]**: Epic or community source, listed at the end.
- **[derived]**: follows from the cited facts.
- **[unverified]**: plausible, not checked. Each one says how to check it.

---

## 1. Facts this plan stands on

| fact | value | label |
|---|---|---|
| Crowd today (the real `build_crowd()` run in Blender) | 2,100 people, 119,832 tris, 75,292 verts, one mesh, flat-shaded | observed |
| Tiers today: people × tris per person | near (detail 2, y > −14 m): 257 × 152. Mid (detail 1): 843 × 40 to 88. Far (detail 0): 1,000 × 24 to 48 | observed |
| Whole Dino environment (exported FBXs) | 184,402 tris; the crowd is 65% of it | observed |
| Crowd FBX face corners | 252,276. A flat-shaded export becomes up to that many Unreal vertices | observed |
| FBX path Blender → Unreal | (x, y, z) m → (x, −y, z) cm. Observed: the screen at Blender y = +10.9 m landed at −1090 cm (`build_dino.log`). Sources agree: Unreal is left-handed, and only Y differs from Blender [S10][S11] | observed + S |
| `person()` heads | `create_icosphere` subdivisions 0 and 1 give the same 20-face mesh in Blender 4.5. The "rounder near head" never happens | observed |
| Tribe renderer | forward, MobileHDR off, multiview, MSAA 2×, `r.Mobile.SupportGPUScene=True`, Vulkan only | given |
| WPO on mobile XR | the 5.4 mobile feature table lists World Position Offset "Yes", including "Mobile Forward w/ HDR Disabled (Head-mounted Mobile XR)" [S4]. 5.2 fixed WPO being ignored on mobile with GPUScene [S5] | S |
| Custom materials | our own UMaterials OOM-killed Tribe, because the Meta fork adds UMaterial properties. Shipping one needs the fork build plus `ue_schemadiff` UMaterial SAME | observed (NOTES.md) |

## 2. Options (three compared)

| | **A. VAT on the merged crowd mesh** (recommended) | B. VAT on HISM instances | C. Shader-only bob/sway |
|---|---|---|---|
| What moves | baked VAT; each vertex fetches its own offset | same VAT; per-person data from PerInstanceRandom / PerInstanceCustomData | a WPO formula: hop, sway, arm swing around pivots |
| Draw calls | 1 (as today) | 1 per LOD (3 to 6) | 1 |
| Tris | about 134k (fixed tiers by row, as today) | similar; per-instance LOD can lower it | 120k (as today) |
| Lighting | today's per-person baked atlas works unchanged (UV0) | instances share UVs, so per-person cells need custom data to offset UV0 into the atlas | today's atlas works |
| Variation | anything, set per person at build time (clip, phase, mirror, yaw, scale) | 1 random float per instance (mobile support of PerInstanceRandom: [unverified]); more needs custom data | phase/speed only |
| Motion quality | anything you can animate in Blender | same | rigid bob/sway; arms need per-vertex pivot data |
| Engine features we depend on | WPO + vertex texture fetch | + HISM components, mobile instance data under GPUScene, LOD transitions | WPO only |
| Who bakes the VAT | Blender (this prototype; verified) | Blender, or UE's experimental AnimToTexture (§10) | nobody |

**Why A.**
- It changes the least about what already works: the same static-mesh actor, the same lighting bake, one draw call.
- It depends on the fewest engine features: WPO with a texture fetch, which is listed as supported on mobile XR
  [S4].
- Every number in it can be checked in Blender before Unreal is involved.

**Why not B.** B's advantages (culling, per-instance LOD) don't pay off: the crowd fills the DJ's view, and the rows
are already tiered at build time. B also brings mobile instance-data questions:
- Custom data reached the mobile *pixel* shader only in 5.3, and then only with GPUScene [S6].
- There is a backlogged bug about custom data inside material layers [S7].
- Meta's fork notes a GPUScene incompatibility for one of its perf features [S8].

**Where C fits.** C is a fallback or a far-tier option, but at 9 to 14 m the front rows need real arm and leg motion.

## 3. The recommended design in detail

### 3.1 Tiers and triangle budget

All tiers are bound to the same Blender rig and play the same clips, so near and far move consistently. Counts were
measured on meshes built in Blender.

| tier | rows | people | canonical mesh | tris/person | tris | today |
|---|---|---|---|---|---|---|
| near | y > −14 m | 257 | the prototype person: knees, two-part arms, 20-tri head (104 verts) | 168 | 43.2k | 39.1k |
| mid | −34 to −14 m | 843 | detail-1 body cone, head, one straight tube per arm (shoulder ring on the upper arm, hand ring on the forearm) (40 verts) | 60 | 50.6k | 50.3k |
| far | < −34 m | 1,000 | detail-0 body box (bottom on the shins, top on the spine), head box, two open arm tubes (32 verts) | 40 | 40.0k | 31.2k |
| **crowd** | | 2,100 | | | **133.8k** | 120.5k |
| **environment** | | | | | **198k** | 184k (budget ~250k) |

**Budget lever.** Dropping far-tier arms for people who only bounce saves about 10k tris.

**Export smooth normals.** The material is unlit, so normals are unused, and smooth normals stop Unreal from
splitting every face's corners:
- The prototype person comes to 117 Unreal vertices smooth vs 336 flat.
- The crowd should come to about 100k vertices vs about 252k today [derived estimate].
- Keep the faceted look by baking the lighting flat-shaded (§6). The export normals don't affect the bake.

### 3.2 Clips, frames, texture size

- **Frame rate.** 30 fps, 30 frames per clip. One clip = 1 s = 2 beats at an authored 120 BPM.
- **Seam row.** Each clip stores **31 rows**: row 30 is a copy of frame 0, so the material's frame interpolation never
  wraps (no fmod).
- **Interpolation.** The material lerps neighbouring frames, so motion is smooth at 72/90 Hz. That costs 2 fetches
  per vertex.
- **Clips: start with 4.**
  - `jump` (hands up) and `pump` (right arm; mirrored people pump with the left): both in the prototype.
  - `bounce` (knee bounce, arms down or on the hips).
  - `clap/wave` overhead.

  Up to 8 clips fit later.
- **Layout.**
  - Columns: all tiers side by side. Near 0–103, mid 104–143, far 144–175, so **width 256**.
  - Rows: clips × 31. 4 clips = 124 rows, so **height 128**. 8 clips need 256.
  - Memory: 256×128 RGBA16F = **256 KB**; 8 clips = 512 KB.
- **Content.** RGB is the offset from the rest pose in meters, in Blender space. A = 1.
- **Precision.** The largest offset is about 1.4 m (a raised hand), so half-float error is at most 0.049 cm. The
  prototype measured 0.048 cm.

### 3.3 Per-person variation: data in UV channels

| channel | x | y | precision |
|---|---|---|---|
| UV0 | baked-lighting cell u | cell v | as today |
| UV1 | VAT column (integer vertex index of the tier's canonical mesh) | clip index (integer) | integers are exact in half floats up to 2048 |
| UV2 | sx · cos(yaw) | sx · sin(yaw) | half: ≤ 0.0005 relative |
| UV3 | mirror (±1) · sz | phase in [0, 1) | half: ≤ 0.0005 |

- **UV channels.** We use 4. The 5.4 docs say a static mesh takes "up to seven" [S12].
- **UV precision.** Static-mesh UVs default to 16-bit floats unless Use Full Precision UVs is on [S13]. The
  prototype measured both: 0.09 vs 0.05 cm.
- **V pre-flip.** These are the values Unreal reads.
  - Unreal's legacy FBX importer is reported to store `1 − V` [S14]. That source is a UE4 community report, not
    Epic.
  - So the FBX stores every V as `1 − value`. That leaves the material with no OneMinus nodes.
  - The prototype has one switch, `UE_FLIPS_V`. If the step-3 test in §8 shows no flip, set it to False and
    re-export.
  - A wrong assumption is loud: the sin(yaw) channel would visibly twist every person.
- **Per-person transform.** Base mesh = position + R(yaw) · diag(sx, sx, sz) · diag(mirror, 1, 1) · canonical. The
  material applies the same transform to the offset.
  - sx = w / 0.44 and sz = h / 1.75, from `build_crowd`'s random w and h.
  - Mirrored copies get reversed face winding.
- **Assignment at build time** (in `build_crowd`).
  - Clip by weighted choice, for example jump 35%, pump 30%, bounce 20%, clap 15%.
  - Mirror 50%, so half the pumps are left-handed.
  - Phase = small jitter around the beat (±0.04 loop ≈ ±40 ms), so most of the crowd hits the beat together.
  - Optional: add distance/343 m/s as sound delay, which ripples the back rows about 0.17 s late.
- **Tempo.** A scalar `LoopRate` = BPM / 120 loops per second.
  - Now: a material-instance constant (pick about 124 to 128 BPM).
  - Later: a Material Parameter Collection set by the native mod from Tribe's BPM. That value
    (TribePlayerController+0x97c) is [unverified]: it was found in Ghidra, never read live.
  - True beat lock also needs the beat phase, which we don't have yet.
- **Optional:** "song sections". Swap clips every N loops using `floor(Time*LoopRate/8)` hashed with the phase.
  This is about 6 ALU ops.

### 3.4 VAT texture in UE 5.4: settings that survive Android/Vulkan cooking

| setting (Python property) | value | why |
|---|---|---|
| Source file | `T_VAT_*.exr`, half float RGBA | the prototype's file is what ships |
| **Compression** (`compression_settings`) | **`TC_HDR`**: "HDR", uncompressed RGBA16F | Epic contrasts BC6H with "uncompressed HDR (RGBA16F)" [S1]. RGBA16F holds our half values exactly [derived] |
| sRGB (`srgb`) | False | sRGB "can only be used with 8-bit and compressed formats" [S2]; set it explicitly anyway |
| Mip Gen (`mip_gen_settings`) | `TMGS_NO_MIPMAPS` | mips would average neighbouring vertices |
| Filter (`filter`) | `TF_NEAREST` | bilinear would blend neighbouring columns/rows |
| Never Stream (`never_stream`) | True | always resident (256 KB) |
| **Downscale** (`downscale`) | **1.0** | for textures without mips, "0 uses the scale value from the Texture Group" [S3]. A device-profile group could shrink the VAT at cook time; 1.0 pins it |
| LOD group (`lod_group`) | `TEXTUREGROUP_16BitData` ("16 bit data stored in textures") or `ColorLookupTable` ("No compression, no mips") [S3] | also check the Quest device profile's TextureLODGroups entries |
| Address | Clamp | |

**Also set the compression explicitly in the import script.** The project has a "float import format" setting
(HDR_F16 / HDRCompressed_BC6 / HDR_F32_or_F16) whose default we didn't confirm [S2].

**Avoid these.**
- `TC_Default`/`TC_Masks`: ASTC, lossy.
- `TC_VectorDisplacementmap`: 8-bit BGRA. The UE4 table maps it to B8G8R8A8, which is about 1 cm steps over our
  2.7 m range [S1].
- `TC_HDR_Compressed`: BC6H on desktop. On Android it is RGBA16F or ASTC-HDR depending on version (5.6 changed the
  fallback); what 5.4 does is [unverified] [S1].

**Optional.** `TC_HDR_F32` (RGBA32F) keeps the 16-bit PNG route exact, at 2× memory. Mobile "only supports
point-sampled 32-bit float images"; without Nearest it is "converted to a 16-bit float" [S1]. With TC_HDR, the PNG
route lands at half precision too: emulated 0.037 cm.

**Mobile caveats.**
- Vertex texture fetch on UE5 mobile: no caveat found.
- Mip selection: the UE4/ES2 rule was "requires an absolute mip level" [S9]. So the sample node gets an explicit mip
  level 0 (§5) rather than relying on the compiler [unverified whether 5.4 forces it].
- Vertex shaders run at full precision: the docs scope precision modes to pixel shaders, and customized UVs, which
  run in the vertex shader, "are done with full precision" [S15].

### 3.5 Mesh import and actor

Import with build_dino.py's legacy FBX path (`FbxImportUI`). Interchange FBX is still "Experimental" in 5.4 behind
`Interchange.FeatureFlags.Import.FBX`, so the legacy importer is the default [S16]. Settings: static mesh,
combine meshes, `import_uniform_scale` 100, no Nanite, **Force Front XAxis off** (it changes the axis conversion
[S10]). In addition:
- **`generate_lightmap_u_vs` = False** (build_dino already sets it), so no generated lightmap UV lands in our
  channels. AnimToTexture's docs carry the same warning for its index channel [S17].
- **Use Full Precision UVs** (`MeshBuildSettings`): optional (0.09 vs 0.05 cm).
- **Positive and Negative Bounds Extension** on the static mesh, set to the animated bounding box.
  - Values: the prototype JSON gives rest vs animated bounds. Use about (50, 50, 60) cm positive and (50, 50, 20)
    cm negative for the crowd.
  - Bounds Extension is the non-uniform control. Bounds Scale grows the bounds uniformly and costs performance
    [S18].
  - Don't use "Max World Position Offset Displacement": it pads the bounds but also clamps WPO [S19].
- **Component:** `evaluate_world_position_offset` True and `world_position_offset_disable_distance` 0 ("0 = Never
  disable WPO") [S20].
- **Actor:** NoCollision via `set_collision_profile_name` (as every Dino actor), Cast Shadow off.

## 4. Data flow

```
Blender (dino_stage.py + vat module)
  rig + actions ──► per-tier canonical meshes ──► VAT EXR (all tiers × all clips)
  build_crowd(): copies of canonical meshes + UV1..3 person data + UV0 cell ──► SM_DinoCrowd.fbx
  lighting bake (rest pose) ──► T_DinoCrowd.png
Unreal (build_dino.py)
  import EXR (HDR, no mips, nearest, downscale 1) + FBX + PNG ──► MI_DinoCrowdVat (parent M_VatCrowd) ──► one actor
```

## 5. The material graph

`M_VatCrowd` uses Shading Model **Unlit** (`MSM_UNLIT`), Blend Mode **Opaque** (`BLEND_OPAQUE`), and is one-sided.
- Emissive: `TextureSampleParameter2D "Lighting"` (UV0, sRGB) → Emissive Color.
- Everything below feeds **World Position Offset**.
- Class and property names are the verified 5.4 Python ones [S21].

| # | node (`unreal.MaterialExpression…`) | settings | inputs |
|---|---|---|---|
| 1-3 | `TextureCoordinate` ×3 | `coordinate_index` 1, 2, 3 | - |
| 4 | `ComponentMask` ×6 (`r`/`g`) | R and G of 1, 2, 3 | → vid, clip, c, s, msz, phase |
| 5 | `Time` | - | - |
| 6 | `ScalarParameter` `LoopRate` | `default_value` 1.0 | - |
| 7 | `Multiply`, `Add`, `Frac` | p = Frac(Time × LoopRate + phase) | 5, 6, phase |
| 8 | `Multiply` (`FramesPerClip` 30), `Floor`, `Subtract` | f = p × 30; f0 = Floor(f); a = f − f0 | 7 |
| 9 | `Add` (`ClipOffset` 0), `Multiply` (`RowsPerClip` 31), `Add` | row = (clip + ClipOffset) × 31 + f0 | clip, 8 |
| 10 | `Add` 0.5, `Divide` `TexW` | u = (vid + 0.5) / TexW | vid |
| 11 | `Add` 0.5, `Divide` `TexH`, `Add` 1/TexH | v0 = (row + 0.5) / TexH; v1 = v0 + 1/TexH | 9 |
| 12 | `AppendVector` ×2 | (u, v0), (u, v1) | 10, 11 |
| 13 | `TextureSampleParameter2D` `VAT` ×2 | `sampler_type` **SAMPLERTYPE_LINEAR_COLOR**; `mip_value_mode` **TMVM_MIP_LEVEL**, `const_mip_value` 0 | 12 |
| 14 | `LinearInterpolate` | o = Lerp(s0.rgb, s1.rgb, a) | 13, a |
| 15 | `ComponentMask`, `Sign`, `Abs`, `Multiply` | ox = o.r × Sign(msz) | 14, msz |
| 16 | `Multiply`/`Subtract`/`Add` | rx = c·ox − s·o.g; ry = s·ox + c·o.g; rz = Abs(msz)·o.b | 15, c, s |
| 17 | `AppendVector` ×2 | (rx, ry, rz) | 16 |
| 18 | `VectorParameter` `AxisScale` | (100, −100, 100): Blender m → Unreal cm, Y mirrored | - |
| 19 | `Multiply` | offset in Unreal local space | 17, 18 |
| 20 | `Transform` | `transform_source_type` TRANSFORMSOURCE_LOCAL → `transform_type` TRANSFORM_WORLD | 19 → **World Position Offset** |

Material instance values for the prototype: `TexW` 128, `TexH` 64, `FramesPerClip` 30, `RowsPerClip` 31, `LoopRate`
1, `ClipOffset` 0, `AxisScale` (100, −100, 100), `VAT` = T_VAT_Person. This graph is `material_wpo()` in
`vat_crowd_proto.py`, operation for operation. That function is what the test-crowd verification runs.

**Custom-node variant.** This is fewer nodes to author.
- One `MaterialExpressionCustom` (`code`, `inputs`, `output_type` CMOT_FLOAT3 [S21]) feeds node 20.
- Inputs: UV1, UV2, UV3, T (= Time × LoopRate), a Texture Object `Tex`, TexW, TexH, Frames, Rows, AxisScale.

```hlsl
float p = frac(T + UV3.y);
float f = p * Frames;  float f0 = floor(f);  float a = f - f0;
float row = UV1.y * Rows + f0;
float2 uv0 = float2((UV1.x + 0.5) / TexW, (row + 0.5) / TexH);
float3 o = lerp(Texture2DSampleLevel(Tex, TexSampler, uv0, 0).rgb,
                Texture2DSampleLevel(Tex, TexSampler, uv0 + float2(0, 1.0 / TexH), 0).rgb, a);
o.x *= sign(UV3.x);
return float3(UV2.x * o.x - UV2.y * o.y, UV2.y * o.x + UV2.x * o.y, abs(UV3.x) * o.z) * AxisScale;
```

Two details here are [unverified]:
- The macro name `Texture2DSampleLevel`.
- The `<input>Sampler` name for a Texture Object input.

The material compiler errors out if either is wrong.

**Authoring from Python.** The 5.4 `MaterialEditingLibrary` has `create_material_expression(material, class, x, y)`,
`connect_material_expressions(from, from_output_name, to, to_input_name)`, `connect_material_property(from,
from_output_name, property_)` (note the keyword `property_`) and `recompile_material` [S21].

**Gotcha: `unreal.MaterialProperty` does not expose `MP_WORLD_POSITION_OFFSET`.** The Python enum has
`MP_EMISSIVE_COLOR` but skips the hidden values [S21][S22]. Options, in order:
1. Try `unreal.MaterialProperty.cast(12)` [unverified].
2. A template material made once by hand, whose WPO pin takes a `MaterialFunctionCall`. Python then generates the
   function's graph with `create_material_expression_in_function` and `update_material_function`. Both exist in 5.4
   [S21].
3. Wire that one pin by hand.

## 6. Lighting and colour

- **Bake as today, in the rest pose.** Cycles DIFFUSE (albedo from the `Col` attribute × stage lights), one cell
  per person in the 2048 atlas, shown unlit. The baked colour travels with its surface.
  - People stay on their spots, so the coloured light pools stay correct. Only the pose changes.
  - A raised arm keeps the shading it had while hanging (front lit, back darker), which still reads correctly from
    the stage.
- **Turn off crowd shadows in the bake** (`crowd.visible_shadow = False`; the property exists in Blender 4.5
  [observed]). Otherwise the rest pose bakes arm shadows onto torsos, and neighbour shadows freeze in place when
  bodies move. What's left is albedo × soft stage light per surface, which stays plausible in any pose. [unverified
  visually]
- **Keep the faceted look:** bake flat-shaded and export smooth (§3.1).
- **Optional, cheap:** a global beat flash. Emissive × (1 + k · pulse), from the same `LoopRate` clock, or from a
  Material Parameter Collection the mod drives.

## 7. Performance (estimates; measure on the headset)

- **GPU vertex work.** About 100k vertices (smooth) vs about 252k (flat) today. Each does 2 RGBA16F fetches and about
  30 ALU ops. The expectation is equal to or cheaper than the static flat crowd [unverified: GPU time in OVR
  Metrics, static vs VAT].
- **Pixel work.** Unchanged.
- **CPU.** One static mesh draw, no skinning, no ticking, no Blueprint.
- **Memory.** VAT 256–512 KB. Vertex buffers grow by 12 bytes per vertex (3 half2 UV channels), about 1.2 MB.

## 8. Unreal-side steps and verification

1. **Gate:** the fork build passes `ue_schemadiff` with UMaterial SAME. A one-material test pak then loads on the
   headset without the OOM, and its shaders are found (risk 2).
2. Import the prototype files: the EXR with the §3.4 settings; `SM_VatPerson` and `SM_VatCrowdTest` with the §3.5
   settings. In the static mesh editor, check 4 UV channels, and that UV1 x runs 0 to 103.
3. Build `M_VatCrowd` + `MI_VatProto`. In the editor viewport (Realtime), the test crowd must match
   `out/preview_vat_frames.png`:
   - jumpers and pumpers alternate;
   - people are out of phase;
   - mirrored people pump with the LEFT arm.

   Then the canaries:
   - People twisting means the V flip is wrong: flip `UE_FLIPS_V` and re-export.
   - People offset sideways or mirrored means AxisScale is wrong.
   - Clips swapped also means the V flip.
4. Switch the editor preview to Android Vulkan / ES3.1 and check the same view. That also catches a mobile limit on
   UV channels [unverified].
5. Cook for Android_ASTC. Check that the VAT cooked as RGBA16F: 128×64×8 B = 64 KB of mip data.
6. Headset: Dino level with the test crowd beside the static crowd, timed in OVR Metrics.
7. Production: tiers and clips in Blender; `build_crowd()` emits canonical copies + UV1–3; `build_dino.py` imports
   with §3.4/§3.5 and assigns `MI_DinoCrowdVat`.

## 9. Risks and unknowns

1. **Blocking: our own material must load in Tribe.** Today it OOMs. The fork build is the planned fix, but it is
   unproven until the schema check and a headset test pass.
2. **Our material's compiled shaders must ship in our pak** and be found at runtime alongside Tribe's chunked shader
   libraries [unverified]. Check it in gate 1 with a trivial material.
3. **Import conventions.** The V flip rests on one UE4-era community report [S14]. The axis mapping is observed plus
   sourced. Both fail loudly; step 3 checks them, and the V flip has a one-line switch.
4. **Python can't wire WPO directly** (§5). There are workarounds; the worst case is one manual wire.
5. **Texture cooking.** TC_HDR should stay RGBA16F on Android [S1][derived]. Check the cooked size in step 5, and
   pin Downscale 1.0 so no LOD group can shrink the VAT.
6. **Look.** Baked lighting moving with limbs, and synchronized jumping, are judgment calls. Review on the headset at
   the first rows (9 m).
7. **Beat sync** needs the mod to feed BPM and beat phase. Without it, the crowd dances at a fixed tempo.
8. **Budget:** +13k tris over today (measured on proposed tier meshes). GPU time is unmeasured.

**Fallback if custom materials stay blocked:** keep the static crowd. A no-shader idea: split the crowd into about
20 row chunks and bob them with a looping Level Sequence on Tribe's shipped unlit material. This is [unverified]:
it is unknown whether Level Sequences play from a mod pak, and the result would be crude.

## 10. AnimToTexture (the UE-side alternative baker): why not

- **Status.** An **Experimental** plugin (`Engine/Plugins/Experimental/AnimToTexture`, added in 5.1) [S17][S23].
- **What it bakes.** A skeletal mesh's animations, in VERTEX mode ("Position and Normal Per-Vertex") or BONE mode
  (linear blend skinning in the shader, "preferred method if meshes share skeleton") [S17].
- **Precision.** EIGHT_BITS (BGRA8 + TC_VectorDisplacementmap) or SIXTEEN_BITS (RGBA16 source + **TC_HDR**). So
  its "16-bit" also ends up half-float, the same precision as our EXR [S17].
- **Vertex index.** Stored in a UV channel that must not collide with the lightmap UV [S17].
- **Instancing.** Its instanced playback helpers (`AnimToTextureInstancePlaybackLibrary`, which allocates
  per-instance CustomData) live in the plugin's **runtime module**. Tribe's binary doesn't contain that module
  [derived]. Its material is built from material layers, which hit UE-202452 with per-instance custom data [S7][S17].

**Verdict.** It would add a skeletal-mesh + AnimSequence import and an in-editor bake. It gives no control over our
tier/merged layout, and it brings plugin content and runtime pieces. Our Blender bake already produces the same data,
verified, from the script that builds the stage.

## Sources

Epic 5.4 docs live at `https://dev.epicgames.com/documentation/en-us/unreal-engine/<slug>?application_version=5.4`,
and Python API pages at slug `python-api/class/<Name>`. Fetched 2026-10-05 by a research pass. Quotes are verbatim
from it.

- S1: `texture-asset-editor-in-unreal-engine`. "HDR Compressed/BC6H … should be used instead of uncompressed HDR
  (RGBA16F)". Mobile: "only supports point-sampled 32-bit float images. If you don't set the texture to the Nearest
  filter … converted to a 16-bit float". UE4.27 `texture-compression-settings`: HDR → FloatRGBA,
  VectorDisplacementmap → B8G8R8A8. Release notes 5.2 ("Fixed issues with ASTC HDR texture compression") and 5.6
  ("Make ASTC_RGB_HDR on IOS/Android default to ASTC_RGB if ASTC HDR is not supported instead of RGBA16F").
- S2: `API/Runtime/TextureUtilitiesCommon/ETextureImportFloatingPointFormat` (HDR_F16 / HDRCompressed_BC6 /
  HDR_F32_or_F16). Texture docs: sRGB "can only be used with 8-bit and compressed formats"; 32-bit float sources are
  stored as 32-bit.
- S3: `API/Runtime/Engine/Engine/FTextureLODGroup` (MaxLODSize, LODBias, Downscale). Texture Downscale: "for
  textures without mips. 0 uses the scale value from the Texture Group". `python-api/class/TextureGroup`
  (16BitData, ColorLookupTable).
- S4: `rendering-features-for-mobile-games-in-unreal-engine`: WPO "Yes" for "Mobile Forward w/ HDR Disabled
  (Head-mounted Mobile XR)".
- S5: UE 5.2 release notes: WPO "was ignored on Mobile platforms if project uses GPUScene" (fixed).
- S6: UE 5.3 release notes: "Added support for instance custom data in pixel shader while mobile GpuScene is
  enabled". `unreal-engine-console-variables-reference`: `r.Mobile.SupportGPUScene` defaults to 0. 4.25.4 fixed
  UE-100159 (custom data crash on mobile).
- S7: `https://issues.unrealengine.com/issue/UE-202452`: custom data inside a material layer "only gets the data
  correctly when the base material has a PerInstanceCustomData expression" (5.3, backlogged).
- S8: `https://developers.meta.com/horizon/documentation/unreal/po-fork-engine-perf`: "EUB is NOT compatible with
  GPUScene".
- S9: `https://forums.unrealengine.com/t/vertex-texture-sampling/338037`: "Sampling from vertex textures requires an
  absolute mip level on feature level ES2" (UE4).
- S10: `API/Editor/UnrealEd/FFbxImporter/ConvertScene`: "converted to RH -Y or RH X depending if we force a front X
  axis". Unreal is "left-handed and uses a Z-up axis".
- S11: `https://forums.unrealengine.com/t/blender-to-ue4/117879`: "the X and the Z axis in blender and unreal are
  identical. It is only the Y that is in the opposite direction" (community).
- S12: `using-uv-channels-with-static-meshes-in-unreal-engine`: "up to seven different UV Channels".
- S13: `https://forums.unrealengine.com/t/full-precision-uvs/311155` (Epic staff, 2016): "By default static meshes
  use half precision (16 bit) UVs". `python-api/class/MeshBuildSettings` still has the flag in 5.4.
- S14: forums.unrealengine.com thread 444157 (UE4 community): the FBX importer "recalculates the UV … only V is
  affected".
- S15: `r.Mobile.FloatPrecisionMode` and the material `float_precision_mode` docs are pixel-shader scoped.
  Customized UVs doc: "Customized UV inputs however are done with full precision".
- S16: `importing-assets-using-interchange-in-unreal-engine`: "Support for the FBX file format is currently
  Experimental" (`Interchange.FeatureFlags.Import.FBX`).
- S17: `python-api/class/AnimToTextureDataAsset` (modes, UV channel index warning); `API/Plugins/AnimToTextureEditor/
  FHighPrecision` and `FLowPrecision`; AnimToTextureInstancePlaybackLibrary (runtime module).
- S18: `visibility-and-occlusion-culling-in-unreal-engine` (Bounds Scale vs Positive/Negative Bounds Extension).
  `python-api/class/PrimitiveComponent` `bounds_scale`: "useful when using World Position Offset".
- S19: `unreal-engine-material-properties`: Max World Position Offset Displacement (5.2+) pads bounds and clamps WPO.
  Related bugs UE-297159, UE-219233.
- S20: `python-api/class/StaticMeshComponent`: `evaluate_world_position_offset`,
  `world_position_offset_disable_distance` "(0 = Never disable WPO)".
- S21: `python-api/class/MaterialEditingLibrary`, `MaterialProperty`, and the expression classes listed in §5.
  Enum values SAMPLERTYPE_LINEAR_COLOR, TMVM_MIP_LEVEL, TRANSFORMSOURCE_LOCAL, TRANSFORM_WORLD, CMOT_FLOAT3,
  MSM_UNLIT, BLEND_OPAQUE.
- S22: `https://tacolor.xyz/Howto/Manipulate_Material_Expression_Nodes_Of_Material_With_Python_In_UE.html` (UE
  5.0.3): "unreal.MaterialProperty does not contain any enums items such as MP_WorldPositionOffset that are marked
  hidden".
- S23: UE 5.1 release notes: AnimToTexture "now available as an experimental Engine plugin".
  `https://unrealcode.net/AnimationTextures.html` (5.4.3 content: ML_BoneAnimation etc.; bakes one LOD).
