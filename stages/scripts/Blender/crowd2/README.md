# Crowd V3: the rave crowd for the Dino Stage

`crowd3.py` builds the audience for `dino_stage.py`. It has the same API as Crowd V2 (`crowd2.py`, kept unchanged),
so it drops in with one import.

**The people.** About 4,200 people fill the field, plus about 14 people on friends' shoulders and the grounds' extra
people. They are procedural low-poly ravers:
- **Bodies:** per-person build (slim, average, athletic, curvy, heavy), height, shoulders, hips, bust, belly and limb
  thickness. The silhouette follows the outfit.
- **Faces and hair:** eye sockets, brow, mouth and jaw on the face. Hair is short, long, ponytail, bun, braids, buzz
  cut or bald, natural or dyed.
- **Tops:** crop tops, bralettes, bandeaus, bodysuits, mesh tops, tees, tanks, tie-dye, long sleeves, hoodies or
  shirtless. Mesh tops are dark with a lighter pattern per vertex.
- **Bottoms and feet:** booty shorts, shorts, tutus, flared pants, cargos, jeans, fishnets; leg warmers, boots,
  platforms or light-up shoes.
- **Accessories:** kandi stacks, bandanas, shades, goggles pushed up, flower crowns, caps, bucket hats, beanies and
  cowboy hats. Also light-up horns and ears, capes and hydration packs.
- **Costumes:** dino onesies (hood, spikes, tail), aliens (antennae with glowing tips) and inflatable T-rex suits (mid
  tier, at least two).
- **Glowing bits** (their own mesh, with an emissive vertex colour): glow necklaces, LED-glove fingertips, light-up
  soles, glowsticks, phone screens and flashes. Also LED fans, hoops, poi, staff ends, totem LED frames and antenna
  tips.

**Who does what.**
- **Friend groups** of 2–5:
  - half dance together, with the same clip and near-identical timing;
  - the rest face each other, talking or dancing, or pair up as couples.
- **Turned to a neighbour:** about 5% of the rest turn toward someone beside them.
- **Flow artists:** hoop, poi, staff or fan. People step out of a hoop's or staff's way.
- **Phone filmers and totem holders:** totems lean toward the sides and the back.
- **Shoulder riders:** a few people ride on friends' shoulders. Both animate, and some riders wave a flag, a sign or an
  inflatable.

**Dancing.** A vertex animation texture (VAT) is played by the existing World Position Offset material. There are 17
clips:

> jump, jumppump, pump, handsup, wave, clap, sway, twostep, shuffle, headbang, nod, heart, hold, talk, carry, ride, flow

- **Beat clips** stay on the beat: 0 or 1 beat of offset, about 33 ms of jitter (1 σ), and 15% at half time.
- **Groove clips** (sway, nod, heart, talk, flow) float freely: a random phase, ±3% tempo, and 20% at half time.

**Field.** It is packed at the barrier (about 0.6 m spacing) and thins with depth (about 1.5 m at the back). The sides
and the last 10 m feather out, instead of ending in a straight cut.

**Lighting.** It stays baked per person: a UV0 cell per person plus the `Col` albedo. New in V3: every person ships posed
at frame 0 of their own dance. The bake therefore sees raised arms, people on shoulders and spinning props, not a rest
pose.

There are no third-party assets (see LICENSES.md).

## Files

| file | what |
|---|---|
| `crowd3.py` | the V3 module: `build_crowd2()`, `pose_preview()`, `crowd_half_v2()`, and the knobs (below) |
| `crowd3_preview.py` | standalone checks plus Workbench renders: `blender -b --factory-startup --python crowd3_preview.py -- [--no-grounds] [--no-render]`. It writes into `previews_v3/` only, never `Scripts/Blender/out` |
| `previews_v3/` | DJ views (studio and flat albedo), a night approximation (albedo ×0.05, glow at full), front-row close-ups, an aerial and a side view, line-ups of every dance and of the costumes, plus that build's VAT `.exr`/`.json` |
| `crowd2.py`, `crowd2_preview.py`, `previews/` | Crowd V2.1, unchanged (`crowd2_v2.py` is a byte-identical backup) |
| `LICENSES.md` | all procedural |

## dino_stage.py

```python
import crowd3 as crowd2      # crowd2/ is already on sys.path; nothing else changes
crowd, phones, _ = crowd2.build_crowd2(random.Random(11), exclude=_excl, extra=_extra)
...
crowd2.pose_preview([crowd, phones], 0.31)   # after the export, as before; (…, None) restores
```

**Returns:** the same as V2.
- `SM_DinoCrowd`: UV layers `UVMap` (lighting cells), then `VatIndex`, `VatRotScale`, `VatScalePhase`, `VatRate`. The
  `Col` corner colour is the albedo, and shading is smooth.
- `SM_DinoPhones`: the glowing bits. `Col` is the emissive colour, with the same VAT channels.
- `[]`: there is no extra mesh.

**Writes:** `<out>/T_DinoCrowdVAT.exr` (RGBA half float, 2048×1024) and `<out>/T_DinoCrowdVAT.json`. `<out>` respects
`DINO_OUT`; `out_dir=` overrides it.

**Field width:** taken from `kit.crowd_half` (`20 + 0.55*(-y)`), or `crowd_half_v2` if kit isn't importable. Same as V2.

## What changed for Unreal (build_dino.py needs no edits)

**VAT:** 2048×1024, which is 16 MiB on the GPU (V2: 2048×256, 4 MiB).
- 17 clips × 29 rows (28 frames plus a wrap copy of frame 0).
- The three tiers' superset meshes need 2,418 columns together. That is more than 16-bit UVs can index exactly (2048), so
  the rows come in two **pages**:
  - the near tier fills page 0 (1,449 columns);
  - mid and far share page 1 (925 + 41 columns).
- `UV1.y` holds `page * 17 + clip` (at most 33, exact in a half float). The material already computes
  `row = clip * RowsPerClip + frame`, so the pages need no material change.
- The material reads `frames_per_clip` (28), `rows_per_clip` (29), `width`, `height`, `beats_per_clip` and `axis_scale`
  from the JSON, which `build_dino.py` already loads.

**Offsets:** they run from each clip's **frame 0**, not from the rest pose. The shipped mesh is posed at frame 0 of each
person's clip, so `p = 0` gives offset 0 and the base pose matches the VAT. A MIC-only (non-animated) build shows the
crowd frozen mid-dance rather than in the arms-down rest pose.

**UV channels:** still **5**. 16-bit UVs stay exact, because the widest page is 1,449 columns. `prepare_vat_mesh`
defaults are unchanged.

**Texture settings:** `prepare_vat_texture` is unchanged (16-bit data group, TC_HDR, no mips, Nearest, never stream,
clamp).

**Bounds:** the largest offset is 1.44 m, from spinning staffs and poi. That is above the ±1 m horizontal pad that
`prepare_vat_mesh` adds. The pad only matters at the outer edge of the whole crowd mesh, so it is harmless in practice.

## Knobs (crowd3.py)

| knob | default | effect |
|---|---|---|
| `build_crowd2(target=...)` | 4250 | people on the field. Shoulder riders and the grounds' extra people come on top |
| `TIERS` | near < 12 m, mid < 18.5 m, far beyond | distance from the DJ: about 874 / 256 / 21 tris per person |
| `CLIP_ZONE` | front / middle / back mixes | the dance mix by depth. Held things decide the clip: totems and phones "hold", flow toys "flow" |
| `BEAT_CLIPS`, `HALF_TIME_OK`, `_timing()` | see file | which clips lock to the beat, and how phases and tempos spread |
| `make_person()` | see file | outfits, accessories, costumes and held things, with their probabilities |
| `build_people()` | groups 30% of seeds (behind the first 2 m); riders: field // 300, at least 4 | friend groups, couples, turned people, flow clearings, T-rex minimum, shoulder riders |
| `BUILDS` | 5 body types | morph weights per type. The outfit adds a fem/masc lean |
| `DETAIL["near"/"mid"]` | see file | segment counts per tier |
| `CELL_UNITS` | 3 / 2 / 1 | lighting-atlas cell size per tier. Rarely worn parts get 0.6× islands |
| `_field()` | spacing `(0.52 + 0.0142*depth) * scale` | the density gradient and edge feathering. `scale` is solved to hit `target` |

## Measured (crowd3_preview.py: grounds seed 1234, crowd seed 11, no stage)

**Crowd:** 4,439 people (4,175 field, 14 riders, 250 extra) in 874 friend groups.
- Tiers: near 127, mid 492, far 3,820.
- Costumes: 103 onesies, 37 aliens, 3 T-rexes.
- 69 people stepped aside for flow artists.

**Tris:** 317,488 body plus 9,396 glow, 326,884 in all (V2: 342,429). By tier:

| tier | body tris | tris per person |
|---|---|---|
| near | 111,022 | 874 |
| mid | 125,926 | 256 |
| far | 80,540 | 21 |

**Vertices:**
- Blender: 230,189 body plus 13,082 glow.
- Unreal estimate (UV0 seams and colour borders): about 325k body plus 13k glow, 338k in all. V2's SM_DinoCrowd measured
  345,882 in Unreal.

**The trade.** The denser barrier and the richer near tier (127 people at about 874 tris, against V2's 90 near) are paid
for by two cuts:
- the mid radius, 20.5 → 18.5 m;
- the far body, now a 3-sided column of 21 tris.

**Checks:**
- **VAT decode:** pages and frame-0 offsets, decoded through the material math, match direct skinning to 0.024 cm with
  16-bit UVs (0.017 cm with full-precision UVs).
- **Body types against frame-0 offsets:** a morphed vertex rides the canonical offsets. The deviation from exact
  skinning is 0.13 cm median, 0.94 cm at the 95th percentile and 2.75 cm at most.
- **Face winding:** brims, tutus and hoops have matched up and down faces, and outer and inner bands.

**Build time:** about 9 s in Blender.

## Known limits

- **Far tier:** 21 tris per person.
  - Arms and glow quads are one-sided. They are flipped per clip to face the stage at frame 0, but in "flow" (arms
    crossing horizontal) they can turn away for part of the loop.
  - The far tier looks blocky from a low drone or stream camera.
- **Body types:** morphs don't rotate with the bones within a clip (see the deviation above).
- **Riders:** the rider's seat is approximate. Thighs over the shoulders and small overlaps hide in the dark.
- **Inflatable T-rex:** it reads as a blob in the line-up. The head, jaw and arms silhouette needs strengthening, noted
  for a later pass.
- **Lighting:** baked at frame 0 of each dance, so it moves with the limbs during the loop.
- **Tempo:** fixed at 128 BPM (`LoopRate = BPM / 120`) until the mod feeds the real BPM and beat phase.
- **VAT memory:** 16 MiB, 4× V2. The headset frame rate of V2 and V3 is not measured yet.
- **Flow props:** they spin one turn per loop (2 beats), sampled 28 times per turn, so the circle stays round under the
  material's linear frame blend.
