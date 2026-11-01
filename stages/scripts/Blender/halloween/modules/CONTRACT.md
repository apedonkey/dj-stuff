# GRAVEYARD SHIFT grounds modules: the contract

The Halloween stage's festival grounds, built as modules exactly like the Dino Stage's `../../grounds/*.py`, so
`../hw_stage.py` can load, bake and ship them. Plan: `claudedocs/halloween_stage_plan.md` in the tribe hack repo
(sections 2, 3, 5). Look: the approved concept `claudedocs/halloween_concept/` and the current stage
`claudedocs/halloween_v1/` (renders).

## Ground rules (other sessions share this machine)

- **Edit only your own files** in this folder (`hw_<name>.py`, your notes). Never edit `../../grounds/kit.py` or any other
  file of the Dino or club sessions, `../hw_stage.py`, or anything in the tribe hack repo. Import the kit read-only.
- **No headset**: never run adb or push anything to the Quest. The Halloween session lead integrates and ships.
- **GPU lock**: every Blender run that renders or bakes (Cycles or EEVEE) goes through `run_preview.sh`, which takes
  `C:\Users\Chris\TribeUE\gpu.lock.d` (mkdir + owner.txt) and releases it. If you script Blender yourself, take the lock
  the same way. Keep renders short (32 samples, 1280x720 is plenty).
- Deterministic: use only the `rng` passed to `build()` (the lead builds with seed 1234, as the preview does).

## The module file

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "grounds"))
from kit import *            # box, cyl, cone, sphere, quad, truss, string_lights, led_text, beam_planes, halo, light, ...
NAME = "graveyard"           # the lit mesh ships as SM_HwGrounds<Name>, baked to T_HwGrounds<Name>
BAKE_SIZE = 2048             # 2048 or 4096

def build(rng) -> dict:
    return {
        "lit":    [(bm, "stone"), ...],     # opaque, lighting BAKED (Cycles); key from kit.LIT
        "glow":   [bm, ...],                # opaque unlit emitters: faces UV'd with glow_faces(bm, faces, key), kit.GLOW keys
        "beams":  [bm, ...],                # translucent beams: beam_planes() (kit.BEAM_COLS columns)
        "halos":  [bm, ...],                # translucent glow sprites: halo()
        "lights": [light(...), ...],        # lights that bake onto everything (your surfaces, the ground, the crowd)
        "exclude": [(x0, y0, x1, y1), ...], # crowd keep-out rectangles
        "people": [(x, y, yaw, pose), ...], # extra people for the crowd mesh (pose: down/up/one/hips); no own crowds
    }
```
This is `kit.py`'s contract unchanged (read its docstring). Everything is static, except the optional hinged parts
below: no other animation, no per-object motion.

### Hinged parts (optional, added 2026-10-08: coffin lids, the Pumpkin King's jaw)

A module may also return `"hinged": [(bm, key, pivot, axis, open_deg, delay), ...]`:
- `bm`: ONE moving part only, modelled CLOSED, in the kit frame like everything else; opaque, baked with the kit.LIT
  `key`. A part with two materials is two entries with the same hinge.
- `pivot`: a point on the hinge line (x, y, z), kit frame, meters. `axis`: the hinge direction (any length).
- `open_deg`: how far it opens at the cue's full level, in degrees; + is a right-hand turn about `axis` (thumb along
  the axis, fingers show the turn). Keep it within +-120.
- `delay`: 0..0.9, the share of the cue ramp the part waits before it starts. Stagger the coffins over 0..0.6;
  0.8 holds a part shut until just before the drop (the Pumpkin King's jaw).
- It opens with the show's "hands" row: creaks open over the build, stays open through the drop, closes in the
  breakdown, always smoothly. The stock build shows it closed, and the bake lights it closed.
- Whatever it reveals (the coffin's inside, a glowing mouth) is an ordinary static "lit" or "glow" part.
- Budget: <= 3,000 tris of hinged parts per module. Check the open pose with `run_preview.sh <module> --open`.
- hw_stage.py joins every module's hinged parts into one mesh, SM_HwHinged (baked to T_HwHinged, 1024).

## Space (the kit's frame, before the stage drop)

Meters, Z up. The DJ at the origin facing -Y (the crowd); the stage and cathedral behind the DJ (+Y). Model on the crowd
field floor `z = GROUND_Z = -1.5`; the stage deck top is z = 0. `hw_stage.py` lowers everything by 1.0 m afterwards
(so on the Quest the field is at -2.5 m and the DJ's floor at 0). Do not lower anything yourself.

## The existing set (do not build over it; keep it visible from the crowd)

- Stage deck x -25..25, y -4.5..14 (top z 0). Iron fence barrier at y -7.5, x -31..31.
- Cathedral: facade wall x -20..20 at y 14..15 up to z 27; towers x +-20..28, y 14..22, up to z 47 (spires); gargoyles
  at the tower tops; portal arches x +-16.4 at y 10.7..14; the 23 m screen at y 10.3, x +-11.5, z 0.7..13.7; ruined nave
  x +-15, y 15..45. Truss y 9.8 at z 17.5. Two giant dead oaks at (+-39, 6), crowns ~10 m around.
- Searchlights at (+-32, -92) and (+-31, 24). Laser fans land over the crowd at head height.
- The crowd: rows from y -8.6 back to about -66, half-width `crowd_half(y) = 20 + 0.55*(-y)` (25.5 m at y -10, 38.7 m at
  y -34, 56.3 m at y -66). The lead builds it (the costumed crowd); you only add "people" where yours belong.
- Baked ground plane x -110..110, y -160..60; dark far ground beyond; storm sky (radius 480 m), blood moon at (-30, 100, 81).

## Zones (the plan's layout; kit frame)

| module | where | what |
|---|---|---|
| hw_graveyard | side strips, \|x\| from crowd_half(y)+3 to crowd_half(y)+10, y -10..-70, both sides | ~400 tombstones (slabs, crosses, obelisks, celtic), 4 mausoleums at y -25 and -50 (both sides, doors facing the crowd), ~20 coffins (some open), 6 open graves with reaching arms, a low iron fence on the strip's outer edge with lanterns, green/purple uplights in the stones, ~20 ghoul "people" between the stones |
| hw_infrastructure | in and around the crowd | FOH mausoleum at (0, -31), ~8 x 4 m, with GRAVEYARD SHIFT LED banners facing the stage and the crowd, 2 follow spots on the DJ; 4 crypt speaker towers at (+-17, -42) and (+-15, -65) (~13 m, line arrays, purple LED strips, purple sky beams); 4 light masts at (+-30, -58) and (+-24, -78); exclude rects for all of them |
| hw_vendors | lanes with unit BACKS at \|x\| = crowd_half(y)+17.6, y -14..-66, fronts facing the crowd; a walkway at crowd_half+10..14 | 14 units: WITCH'S BREW (bar), GRAVE DIGGER DOGS, BAT BITES (tacos), POISON APPLES, SCREAM CREAM, BLOOD BANK (red drinks), BRAINS (noodles), CURSED MERCH, MORGUE LOCKERS, HEX BURGERS, BONE BROTH, COFFIN COFFEE, plus hearse food trucks and coffin bars; 8 outhouses with a skull WC light tower; festoon masts with orange/purple bulbs; ~110 people queuing |
| hw_forest | beyond the vendor lanes (\|x\| > crowd_half(y)+24, y > -75) and around the back attractions (y -75..-155) | a dead-tree ring: ~120 bare L-system trees 10..25 m (near ones lit, far ones as black silhouettes on the glow palette, the Dino trick); hanging lanterns and a few cages in the near trees; crows on branches; keep clear of the carnival, pumpkin patch, crypt and swamp areas below |
| hw_carnival | back left, centre (-60, -110), radius ~25 | haunted carousel (~12 m, skeletal horses, bulb chase ring), HOUSE OF HORRORS facade with marquee bulbs and a dark mouth, fortune-teller wagon, ticket booth, strongman tower, 2 candy wagons; ~60 people |
| hw_pumpkins | back right, x 40..78, y -78..-102 | pumpkin patch (~300 pumpkins, 24-60 tris each, ~80 with lit faces), the Pumpkin King (~8 m, lit face toward the main stage), 6 scarecrows, hay bales, low corn rows (opaque stalks, no masked cards); ~25 people |
| hw_crypt | back right, the crypt at (60, -128) facing +Y, its crowd at y -112..-122 | THE CRYPT second stage: stone crypt front, its own LED wall (glow), truss, 2 stacks, purple beams, "THE CRYPT" sign; its own crowd of ~100 as "people"; and the swamp: x -35..35, y -95..-135, a dark water plane (lit, very dark blue), dead reeds, ~60 will-o-wisp glow dots just above the water |

## Look

- Night. Surfaces are dark; light comes from your practicals: lanterns, candles, uplights, signs, marquee bulbs.
- Palette: orange, amber, fire, ember, purple, uv, green, lime, red (kit.GLOW keys; also the *_dim ones, bulb_warm,
  black). Avoid cyan, sky, blue, magenta and pink: they are the Dino Stage's and the club's look. Beams: purple, amber,
  green, red, white from kit.BEAM_COLS.
- Lit materials: kit.LIT keys (stone, metal_dark, wood, wood_dark, canvas_black, truck_black, foliage_pine, bark, dirt...).
- The bake: Cycles diffuse, tonemapped `1 - exp(-0.9 x)` (Dino's grounds exposure 1.8 x the night factor 0.5), shown unlit
  on the Quest. `hw_preview.py` simulates exactly that; tune your light powers by its renders.
- No strobes or flashes (everything is static anyway). Big bright areas glare in VR: keep large emitters dim.

## Budgets (Quest 3: the whole stage must hold 72 fps with the 4,400-person crowd)

| module | tris | lights |
|---|---|---|
| hw_graveyard | 30k | 30 |
| hw_infrastructure | 15k | 15 |
| hw_vendors | 25k | 40 |
| hw_forest | 45k | 25 |
| hw_carnival | 30k | 25 |
| hw_pumpkins | 25k | 12 |
| hw_crypt (+ swamp) | 25k | 15 |

Beams/halos: keep quads few (tens per module), they are alpha-blended overdraw.

## Preview

```bash
bash run_preview.sh hw_graveyard --views dj_left,dj_right,side_left,overview
```
Renders the module in context (the current Halloween stage from `../out_hw`, unlit as shipped, plus the stage's main bake
lights) into `out/preview_<module>_<view>.png` and prints `[HWGROUNDS]` stats: tris per part, lights, exclude rects,
people, bounds. Views: dj, dj_left, dj_right, dj_front, overview, back, side_left, side_right, crowd, drone_crowd,
carnival, pumpkins, crypt (see `CAMS` in hw_preview.py). Write a short report (what you built, stats, and anything the lead
must know) at the end.
