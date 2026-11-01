# VAT crowd prototype (Dino Stage)

This folder prototypes an animated (dancing) crowd for the Dino Stage using a vertex animation texture (VAT) that
an Unreal material plays back through World Position Offset. The plan and the reasons for it are in
[DESIGN.md](DESIGN.md). This README covers how to run the prototype, what it writes, and what it measured.

## Run

```
D:\Tools\blender-4.5.14-windows-x64\blender.exe -b --factory-startup --python vat_crowd_proto.py [-- --frame 17 --no-preview]
```

A run takes about 2 s, or about 10 s on the first Workbench render. It ends with `[VAT] PASS` (exit code 0), or with
`[VAT] FAIL` and exit code 1. `--frame N` picks which frame gets re-evaluated in the "frame N" check (default 17).
`--no-preview` skips the contact-sheet render. The script does not read or modify `dino_stage.py`, and it writes
only to `out/`.

## What it builds

- **One person**, matching the style of `dino_stage.person()` at detail 2. It uses the same `limb()` cones, the same
  proportions (h 1.75, w 0.44), the same 8-segment squashed torso and 5-segment two-part arms, and the same palette
  and bottle-label UV cell. The only change is the legs, which are 3-ring tubes with a knee so they can bend.
  - Size: **104 verts, 168 tris.** Today's detail-2 person is 92 verts and 152 tris (counted on the real
    `person()` output).
  - Unreal render verts, estimated from unique (vertex, UV0) pairs: **117** with the smooth-normal export used here,
    336 if exported flat-shaded.
  - Note: in Blender 4.5, `create_icosphere(subdivisions=0)` and `subdivisions=1` produce the same 20-face
    icosahedron. So `person()`'s "rounder head for the front rows" never happens: every crowd head today is 20 tris.
- **Rig and dances.** An 11-bone armature (pelvis, spine, head, upper and lower arms, thighs, shins). Two actions
  are keyed procedurally on every frame, each lasting 30 frames at 30 fps. That is 1 s, or 2 beats at the authored
  120 BPM.
  - `jump`: hands up, a hop on each beat, and a crouch on landing. The legs use 2-bone IK.
  - `pump`: right fist pump on each beat, with a knee bounce, a head nod and a slight torso twist.
- **The VAT.**
  - Each texel holds a position offset in meters from the rest pose, in Blender object space.
  - Columns are vertices: x = the value of UV1.x.
  - Rows are frames: y = clip × 31 + frame. Row 0 is the top row of the file.
  - Each clip stores 31 rows, so frame 30 repeats frame 0 and the material's interpolation never has to wrap.
  - The texture is 128 × 64, RGBA16F, 64 KB in memory.

## Files

| file | what |
|---|---|
| `vat_crowd_proto.py` | the prototype (build → rig → key → bake → export → verify → preview) |
| `DESIGN.md` | the Quest plan: options, recommendation, per-person data layout, texture settings, material graph, lighting, risks, sources |
| `out/T_VAT_Person.exr` | the VAT, RGBA **half** float, uncompressed, A = 1 (67 KB). This is the file to ship. |
| `out/T_VAT_Person_16.png` | the same offsets normalized to 16-bit (14 KB). Decode: `offset = min + png/65535 * (max - min)`, with min and max from the JSON |
| `out/SM_VatPerson.fbx` | static rest mesh. UV0 = lighting cell, UV1 = (vertex index, clip), UV2 and UV3 = identity person data |
| `out/SM_VatCrowdTest.fbx` | 25 people (5 × 5) with mixed yaw, scale, mirror, clip and phase, using the per-person UV layout of DESIGN.md |
| `out/VAT_Person.json` | material metadata: texture size, frames, rows per clip, clip table, PNG decode range, bounds, UV layout, the test crowd's parameters |
| `out/vat_person.blend` | the rig and both actions, for editing the dances by hand (re-run the script to bake again) |
| `out/preview_vat_frames.png` | contact sheet decoded from the written EXR. Top row: jump; bottom row: pump; left to right: frames 0, 3, … 27 |
| `out/verify_report.json` | the numbers below |

The FBX export uses the same settings as `dino_stage.py` (`-Z` forward, `Y` up, `FBX_SCALE_UNITS`). It therefore
imports into Unreal like the other Dino meshes, with `import_uniform_scale` 100.

## Measured results (last run, 2026-10-05)

| check | result |
|---|---|
| Rig: evaluated bone matrices vs the procedural pose | max deviation 1.6e-6 |
| Rig: Blender-deformed mesh vs numpy skinning | max 0.00006 cm |
| **EXR** decoded with Blender's own EXR reader vs the evaluated mesh, all 62 frames | **max 0.048 cm**. The half-float rounding bound for offsets up to 1.37 m is 0.049 cm. |
| **Frame 17**, rig re-evaluated fresh, vs the EXR | jump **0.040 cm**, pump **0.044 cm** |
| 16-bit PNG decoded by Blender vs the evaluated mesh | max 0.0012 cm |
| 16-bit PNG after Unreal's RGBA16F conversion (emulated) | max 0.037 cm |
| Loop seam (frame 30 vs frame 0) | 0 cm |
| **Test crowd**, re-imported from its FBX and run through a numpy copy of the material graph, at 5 times incl. sub-frame | **0.051 cm** with full-precision UVs, **0.092 cm** with Unreal's default 16-bit UVs |
| Largest offset (a raised hand) | 1.37 m. Animated bounds: z up to 2.12 m (rest 1.74 m), x ±0.47 m, y −0.17 to +0.34 m |

### What these checks cover, and what they don't

- **Independent decoders.** The EXR and PNG writers are this script's own code. They are decoded with Blender's
  OpenImageIO-based readers, not by inverting the writer, so a layout, row-order or flip mistake would show up as a
  large error. The ground truth is Blender's depsgraph evaluation of the armature-deformed mesh.
- **The material is emulated, not run.** The test-crowd check runs a numpy translation of the material graph.
  It proves the data layout and the math. It does not prove that the Unreal graph you build matches it: build the
  graph node for node as in DESIGN.md.
- **Unreal's import behaviour is emulated from known or observed facts, not run:**
  - V is flipped on FBX import.
  - Blender (x, y, z) m becomes Unreal (x, −y, z) cm. This was observed in `build_dino.log`: the screen at y = +10.9 m
    landed at −1090 cm.
  - UVs are 16-bit floats unless "Use Full Precision UVs" is on.

  If either convention is wrong, the failure is loud, not subtle: people visibly twist or explode, because the
  rotation data lives in a V channel.
- **The V-flip evidence is weak.** It rests on one UE4-era community report. The script therefore has one switch,
  `UE_FLIPS_V`, near the top: set it to False and re-run if Unreal turns out not to flip. Both settings pass the
  self-test, so only the Unreal import can tell which one is right.

## What remains on the Unreal side

Full detail is in DESIGN.md §8.

1. **Prerequisite:** the Meta-fork build must pass `scripts/ue_schemadiff.py` with UMaterial SAME. Until then, no
   custom material can ship (NOTES.md: our own materials OOM-killed Tribe).
2. Import `T_VAT_Person.exr` with these settings:
   - Compression **HDR** (`TC_HDR`, RGBA16F). Set it explicitly: a project setting can otherwise default float
     imports to BC6.
   - sRGB off
   - Mip Gen **NoMipmaps**
   - Filter **Nearest**
   - Never Stream on
   - **Downscale 1.0** (when left at 0, a no-mip texture takes its texture group's downscale)
   - Group `TEXTUREGROUP_16BitData`
3. Import both FBXs with build_dino's FBX settings (legacy importer, Force Front XAxis off):
   - `generate_lightmap_u_vs` False, so UV1 is not overwritten
   - NoCollision
   - Optional: Use Full Precision UVs
   - Positive/Negative Bounds Extension of about 50 cm

   Then check that the static mesh editor shows 4 UV channels.
4. Author `M_VatCrowd` (Unlit, Opaque) from the node list in DESIGN.md §5.
   - Watch out: UE 5.4 Python's `MaterialProperty` enum hides `MP_WORLD_POSITION_OFFSET`. So either try
     `MaterialProperty.cast(12)`, or use a template material with WPO pre-wired to a material function, or wire
     that one pin by hand.
   - Apply a material instance to `SM_VatCrowdTest` and compare it with `preview_vat_frames.png`. Mirrored people
     must pump with their left arm. About half should jump and half pump, each out of phase.
5. Cook for Android_ASTC and confirm the VAT cooked as RGBA16F: 64 KB for 128 × 64. Then test it in the level on
   the headset.
6. Production work: tiers (mid and far canonical meshes on the same rig), 4 to 6 clips, a VAT across all tiers,
   `dino_stage.build_crowd()` building copies of the canonical meshes with the per-person UVs, the lighting bake in
   the rest pose, and `build_dino.py` assigning the new material instead of the unlit glTF MIC.
