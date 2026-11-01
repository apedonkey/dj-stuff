# GRAVEYARD SHIFT crowd (hw_crowd)

`hw_crowd.py` builds the costumed audience for the Halloween stage. It is a copy of the Dino Stage's crowd v3
(`../../crowd2/crowd3.py`, never edited from here) with a Halloween layer. The API, the mesh structure, the VAT
layout, the tiers and the budget stay crowd3's, so it drops in with one import.

## Use (hw_stage.py)

```python
sys.path.insert(0, os.path.join(HERE, "crowd"))
import hw_crowd
crowd, phones, _ = hw_crowd.build_crowd2(random.Random(11), exclude=excl, extra=extra, out_dir=OUT)
hw_crowd.pose_preview([crowd, phones], 0.31)   # after the export; (..., None) restores; default tempo 140 BPM
```

- **Returns** `SM_HwCrowd` and `SM_HwPhones` (crowd3's layout: UV layers `UVMap`, `VatIndex`, `VatRotScale`,
  `VatScalePhase`, `VatRate`; `Col` is the albedo on the crowd and the emissive colour on the phones), and `[]`.
- **Writes** `<out_dir>/T_HwCrowdVAT.exr` (RGBA half float, 2048 x 1024, 16 MiB on the GPU) and `T_HwCrowdVAT.json`.
  `out_dir` defaults to env `HW_OUT`, else `halloween/out_hw`.
- **JSON:** every crowd3 key with crowd3's values (`width` 2048, `height` 1024, `frames_per_clip` 28, `rows_per_clip`
  29, `beats_per_clip` 2, `axis_scale`, `ue_flips_v`, ...), plus `set_bpm` 140, `loop_rate` 1.1667 and `shares`.
- **Material:** LoopRate = BPM / 120, so **1.1667 for the 140 BPM set** (the Dino Stage uses 128 / 120). Per-person
  rates are still 1.0 or 0.5 (half time) in `VatRate`.
- **Field width:** `kit.crowd_half` from `../../grounds/kit.py` (read only), as in crowd3. The module adds the grounds
  folder to `sys.path` itself if it is missing.

## What changed from crowd3

- **Costumes (about 55 %):** skeleton, witch, zombie, pumpkin head, ghost, devil, vampire, mummy and cat; plus 3 to 5
  inflatable T-rexes in the mid tier, as the nod to the Dino Stage. Friend groups share a costume 35 % of the time.
  The grounds' extra people are costumed too (crowd3 kept them plain); riders and carriers are not.
  - Skeleton: black suit, white bone strips (ribs, sternum, pelvis, arm and leg bones), skull face, dark sockets.
  - Witch: cone hat with a wavy brim and a coloured band (35 % with an LED band), dark dress, cape or tutu skirt,
    striped tights, sometimes a green face.
  - Zombie: grey-green skin, torn and bloody clothes. Pumpkin: a ribbed pumpkin head with a glowing jack-o-lantern face.
  - Ghost: a sheet from a dome over the head to a ragged hem, black eye holes, the arms under it.
  - Devil: glowing red horns, cape, spade tail, red face paint. Vampire: cape with a red lining, high collar, pale.
  - Mummy: bandage bands everywhere, glowing eyes on 25 %. Cat: LED ears (70 %), tail, black catsuit.
- **Ravers:** Halloween palette (black, orange, UV purple, toxic green, blood red, bone; no cyan, magenta or pink).
  LED (purge) masks on 10 %, LED horns and cat ears, rose crowns.
- **Glow:** orange and purple carry it, green and red are accents (weights 30 / 30 / 20 / 12, plus amber and violet).
  Jack-o-lantern faces and buckets glow candle orange. Some devils, vampires and mummies have glowing eyes.
- **Held things:** glowsticks, phones and flow toys as before, plus jack-o-lantern buckets (3 %). Totems are skulls
  with glowing eyes, jack-o-lanterns, bat cut-outs, flags and LED signs. The inflatable blob and the dino cut-out are
  gone.
- **Clips:** still 17. "lurch" (a zombie two-step) and "claw" (Thriller arms, the upper body twisting to each side)
  take the slots of "shuffle" and "heart", so the VAT keeps 2 pages x 17 clips x 29 rows. `pose()` still has shuffle
  and heart; swap them back in `CLIPS`.
- **Tempo:** about 65 % of the beat-locked dancers run at half time (`HALF_TIME_P`; crowd3: 15 % of 7 clips), and every
  beat clip may. Groove clips run at half time 45 % of the time (crowd3: 20 %). Half-time phases stay on the
  half-time grid (0 or 2 beats), and the phase jitter stays about 30 ms at either rate.
- **Zones (`CLIP_ZONE`):** headbang, jump and pump lead the front. Sway, nod and filming lead the middle and back:
  "hold" without a held thing gives the person a phone. Costumes add a bias (`COSTUME_CLIPS`): zombies and mummies
  lurch, witches, vampires and ghosts claw, pumpkins, skeletons and devils headbang and pump.
- **Geometry:** costume parts live in the tier supersets like every other part. A part that replaces a body part
  reuses its lighting island (the pumpkin uses the head's, the ghost sheet the torso's, the witch hat the cowboy
  hat's), so the body's baked-light resolution is unchanged. Glyphs (faces, masks, eyes, eye holes) and bone strips are
  projected onto the faceted surface and pushed out until their centre and edge midpoints clear it by 2 mm.
- **Far tier:** one-sided, stage-facing stand-ins, like crowd3's: a 16-tri pumpkin head with a glowing face quad, a
  witch-hat triangle, a white ribcage quad with white arms and skull, a glowing face for masks and eyes, a bucket glow
  and a totem-top glow.
- **T-rex:** a bigger raised head, an open jaw with teeth, eyes and longer arms (crowd3 noted it read as a blob).

## Measured (hw_crowd_preview.py, crowd seed 11, grounds seed 1234, no stage)

With the Halloween grounds modules as of 2026-10-08 22:06 (carnival, crypt, forest, graveyard, infrastructure,
pumpkins, vendors: 51 keep-outs, 326 extra people). The second column uses the Dino grounds crowd3 was measured with.
The build is deterministic: the same inputs give the same crowd. When the grounds modules change, the counts move.

| | Halloween grounds | Dino grounds | crowd3 (Dino grounds) |
|---|---|---|---|
| people | 4,549 | 4,455 | 4,439 |
| field + riders + extra | 4,209 + 14 + 326 | 4,191 + 14 + 250 | 4,175 + 14 + 250 |
| costumed | 55.7 % (field 56.6 %) | 56.0 % | 3 % |
| body tris | 321,087 | 316,115 | 317,488 |
| glow tris | 13,033 | 12,145 | 9,396 |
| total tris | 334,120 | 328,260 | 326,884 |
| Unreal vertices (estimate) | 349,576 | 343,874 | about 338k |

**Costumes (Halloween grounds):** skeleton 389, devil 329, witch 317, zombie 315, pumpkin 290, cat 258, ghost 249,
vampire 229, mummy 151, T-rex 5; ravers 2,017.

**Tiers (Halloween grounds):**

| tier | people | body tris | per person | glow tris |
|---|---|---|---|---|
| near (< 12 m) | 123 | 107,034 | 870 | 2,017 |
| mid (< 18.5 m) | 509 | 126,972 | 249 | 4,968 |
| far | 3,917 | 87,081 | 22 | 6,048 |

Per person (body + glow) in the near tier, a ghost costs 559 tris, a pumpkin 771, a raver 913 and a devil 976. In the
far tier, everyone costs 22 to 26 tris, and a pumpkin head 36.

**VAT:** 2048 x 1024. The near superset fills page 0 with 1,912 columns, and mid (1,171) and far (74) share page 1.
Both stay under 2048, so 16-bit UVs index them exactly.

**Timing:** 66 % of beat-clip dancers and 45 % of groove-clip dancers run at half time. Front: jump 15 %, headbang
14 %, pump 11 %, jumppump 10 %. Back: nod 18 %, sway 17 %, hold 11 %.

**Build time:** about 11 s in Blender.

## Checks (all pass; hw_crowd_preview.py prints them)

- **VAT decode:** pages and frame-0 offsets, decoded through the material math, match direct skinning to 0.026 cm
  (body) and 0.024 cm (glow) with 16-bit UVs.
- **Body types against frame-0 offsets:** 0.15 cm median, 1.00 cm at the 95th percentile, 2.76 cm at most (crowd3:
  0.13 / 0.94 / 2.75).
- **Face winding, per tier and per part:** 0 problems. No face looks into its own shell, two-sided parts are matched
  pairs wound opposite, and decals face away from the surface they sit on. Brims, capes, tutus, hoops, flags,
  collars, cut-outs and the devil spade are 100 % paired. A self-test reverses one face of each kind and every rule
  catches it. Mirrored people keep outward faces (positive signed volume).
- **Pumpkin heads** stay out of the torso in all 17 clips, near and mid tier (0.0 cm). The control, the neck that is
  buried by design, registers 5.0 cm.
- **Lighting atlas:** the torso island spans 0.477 x 0.292 of a near cell (crowd3: 0.474 x 0.290).
- **Largest VAT offset:** 1.45 m, from spinning flow props (crowd3: 1.44 m).

## Files

| file | what |
|---|---|
| `hw_crowd.py` | the module: `build_crowd2()`, `pose_preview()`, `crowd_half_v2()`; knobs `COSTUMES`, `COSTUME_RATE`, `SQUAD_THEME`, `TREX_P` / `TREX_MIN`, `CLIP_ZONE`, `COSTUME_CLIPS`, `HALF_TIME_P`, `GROOVE_HALF_P`, `HW_BPM`, `DETAIL` |
| `hw_crowd_preview.py` | checks and Workbench renders: `-- [--grounds hw\|dino\|none] [--no-render] [--only name,...]`. Writes only into `previews/` |
| `run_hw_crowd_preview.sh` | runs the preview under the shared GPU lock (`--no-render` skips the lock); log in `previews/preview.log` |
| `previews/` | DJ views (studio, flat, night x0.05, show wash x0.3), front-row close-ups, mid field, aerial, side, behind; costume line-ups (near / mid / far, back, night), accessories and totems, ravers, every dance, the new clips through their loop; costumes at 10 to 60 m by day and night; this build's VAT `.exr` / `.json` |

## Known limits

- **Far tier:** crowd3's 22-tri body. The costume stand-ins are one-sided and face the stage, so drone shots from
  behind the crowd see plain columns. From a low side camera the far tier looks blocky.
- **Skeletons:** bone strips are on the front only.
- **Mummies:** the bandage bands are per-vertex colour on crowd3's rings, so they are subtle up close.
- **T-rex:** better than crowd3's, but still a mascot-like blob from the front.
- **Tails:** cat and devil tails hang behind the body. They show from the sides and from behind, not to the DJ.
- **Claw:** the inner hand passes close to a witch-hat brim. No cross-part collision check runs over all poses.
- **Budget:** the counts follow the grounds modules' keep-outs and extra people. Today's Halloween modules add about
  6k tris over the Dino grounds. `build_crowd2(target=...)` (4,250 field people) is the knob if the frame budget needs
  it.
- **Column headroom:** the near page uses 1,912 of 2,048 columns, so about 130 are left for more near-tier geometry.
- **As in crowd3:** lighting is baked at frame 0 of each dance, and the tempo is fixed per build (LoopRate in the
  material).
