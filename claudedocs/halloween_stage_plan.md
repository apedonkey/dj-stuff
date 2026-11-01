# Halloween stage plan: GRAVEYARD SHIFT (working title)

Written 2026-10-06, planning only. Nothing here is built. The plan is grounded in the Dino Stage pipeline as it stood
on 2026-10-06 (NOTES.md Sessions 3o to 3v, the scripts in `C:\Users\Chris\TribeUE`, and `hook/dumper.cpp`). Labels:
**measured** = read from a log or a file in this project; **Dino** = what the Dino Stage does today; **estimate** =
my number, to be checked; **assumed** = not verified, with the check named.

A second Claude session is building the Dino Stage right now. Section 10 is about not getting in its way; read it
before touching anything.

**Concept renders (2026-10-06):** `claudedocs/halloween_concept/` holds six EEVEE blockout views (facade, venue aerial,
stream, dj_back, crowd, dj_left) and a contact sheet, from
`C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\halloween\concept_blockout.py` (boxes and tubes at the plan's layout,
13 s to build and render; `--views` picks cameras). They show layout, scale, palette and density, not the final look.
The user approved this direction on 2026-10-06 ("that looks pretty good!").
Lesson from building it: one bmesh.ops call per limb on a single growing mesh is O(mesh) per call and stalled for 11
minutes at 2,500 people; each person or tree is built in its own bmesh and merged (bm_merge), as the Dino scripts do.

---

## 0. Assumptions this plan stands on

| assumption | basis | if wrong |
|---|---|---|
| The stream is on or near Halloween, Sat 2026-10-31 | the request says "upcoming"; 25 days from today | the phase plan in section 11 compresses or stretches; the order stays |
| Tempo defaults are 140 BPM, half-time feel | the user plays heavy dubstep, 128-150 BPM (memory 2026-10-06) | hw_show / loops take BPM as a parameter; 128 is one constant |
| The stage ships as a second custom environment next to the Dino Stage, in the same patch OBB, same mod APK | Dino pipeline (measured: 5 custom env boxes have coexisted) | none; this is the only sane route |
| The user tests on one Quest 3 and streams via Tribe's Go Live on a fresh Meta token | Sessions 3h, 3v | re-seed procedure before the stream (section 13) |
| "Just as big" = Dino's content classes at Dino's scale: set + rig + lasers, 5 to 8 grounds modules, a 4.4k VAT crowd, the 23 m visuals screen, a cue-table light show, a VJ loop pack, a drone reel | the Dino inventory in section 1 | scope per class is in each section's "cut if late" line |

---

## 1. What "as big as Dino" means

Dino Stage inventory (measured from NOTES 3s to 3v and the scripts) against the Halloween target.

| class | Dino Stage today | Halloween target |
|---|---|---|
| Centerpiece | spine arches, horns, T. rex skull v2 (11 m head), lava moon behind the screen | ruined gothic cathedral facade: two towers (36 m, one spire broken), a splayed portal framing the screen, a clock face at the gable, blood moon (20 m) behind the towers |
| Rig | 19 moving heads, 4 sky-tracker units (24 heads), 45 laser beams from the horn tips, 82 beam quads, 81 halos | 22 heads (tower balconies + portal truss + facade uplights), 4 searchlight units, 4 gargoyle laser fans + 1 portal fan, same quad budget |
| Grounds modules | vendors (14 units), infrastructure (FOH, 4 towers, masts), landmarks (ferris wheel, 2nd stage + 110 crowd, 3 dinosaurs, 440 trees, 165 tents), atmosphere | graveyard, dead forest, haunted carnival (+ "THE CRYPT" 2nd stage), pumpkin patch + swamp, vendors, infrastructure, atmosphere + weather (7 modules) |
| Crowd | crowd v3: 4,439 VAT people, 17 clips, rave outfits, glow accessories, totems | crowd v3 code with a Halloween costume layer (skeletons, witches, zombies, pumpkin heads, ghosts, devils, mummies, cats), orange/purple/green glow, 2 new clips if time allows |
| Visuals wall | 23 x 12.94 m 16:9 screen registered as Tribe's backdrop, fill mode | same screen size and registration (portal-framed), or an arch-shaped variant (decision 3) |
| Motion | VAT crowd, laser sweeps (WPO), bulb chase, lens strobe, beams on cue rows, show-lit set | all of those, plus ground fog, lightning (sky + bolts), flame jets, bat flocks, ghosts, will-o-wisps, 4 rigid cue-driven hero motions |
| Light show | 32 bars at 128 BPM (60 s), 12 cue rows, comfort rules | 32 bars at 140 BPM (54.9 s), 14 cue rows, same comfort rules, plus a 16-minute macro cycle (storm builds, clock strikes) |
| VJ loops | 8 concepts + a sting, Spine Tunnel rendered | 8 concepts + a sting at 140 BPM half-time, all rendered |
| Camera | 8-shot drone reel, 81 s | 12-shot reel, about 140 s |
| Payload | chunk 50, 120 MB, 32 actors, loads in 1 s, 71-72 fps | chunk 54, target <= 130 MB, <= 40 actors, loads in <= 2 s, >= 71 fps average |

---

## 2. Concept and art direction

**One line.** A headliner set at the witching hour in a necropolis: a ruined cathedral is the stage, the crowd fills a
foggy graveyard field, a blood moon hangs behind broken spires, and the only light is the show.

**Why a cathedral.** It is the Halloween silhouette that is tall, symmetric and cheap: towers and walls are boxes with
windows cut as glow cells, buttresses are wedges, tracery is tubes. Its tops carry the rig the way the Dino horns do,
and gargoyles at the tower corners give the lasers a mouth to come from (the direct analogue of "lasers from the horn
tips"). The ruin reads instantly from the stream camera and from the back of the field.

**Palette.** Pumpkin orange (1.0, 0.40, 0.05), UV purple (0.40, 0.10, 1.0), toxic green (0.15, 1.0, 0.25), blood red
(1.0, 0.08, 0.05), bone white dim (0.40, 0.40, 0.42), moon blue (0.35, 0.65, 1.0). Rule: orange and purple carry the
look; green and red are accents (lasers, eyes, windows); cyan and magenta are not used, so the stage never looks like
Dino's.

**Darkness.** Same rule as the Dino night pass (the user, 2026-10-05): everything dark except the DJ, the visuals, the
lasers and the lights. The set and the crowd are show-lit (wash row), near black between hits.

**Comfort.** Same rules the user set on 2026-10-06 and that check_loop.py and show.py enforce: no strobes, at most 3
flashes per second anywhere, no one-frame hits, no full-frame white, on-beat at most ~1.6x mid-beat, fills swell into
the downbeat. Lightning and fire are the new hazards; section 7 bounds them.

**Name.** The LED banners, the sting and the env box need a name. Recommendation: **GRAVEYARD SHIFT** (a night-set pun
that DJs get; 14 characters fit the 5x7 LED font on the FOH banners the way "DINO STAGE" does). Alternatives:
NECROPOLIS, WITCHING HOUR, HALLOWS STAGE. Decision 2 in section 12.

**Mood by set section** (so the show and the loops agree):

| set section | stage | sky and weather | crowd |
|---|---|---|---|
| intro | windows glow dim purple, candles, clock ticking | moon out, no lightning, low fog | sway, nod |
| build | heads come up orange, searchlights wake, first gargoyle fan | clouds brighten, first distant strike | pump, handsup |
| blackout bar | only the clock face and the moon | one close strike | hold |
| drop | everything, flame jets, hands rise, coffins open | strikes every 2 bars (soft) | jump, headbang |
| breakdown | windows only, fog thickens, ghosts cross | moon alone | sway, talk |
| outro | fans alternate, searchlights sweep out | strikes fade | shuffle |

---

## 3. Layout and fixed constraints

Everything is modeled in the Dino frame (grounds/kit.py docstring): meters, Z up, the DJ at the origin facing -Y, the
crowd toward -Y, the stage behind the DJ (+Y). The set is modeled with the stage floor at z=0 and lowered by
STAGE_DROP = 1.0 m at export, so the DJ riser stays at Tribe's floor and the crowd stands 1.5 m below the deck
(GROUND_Z = -1.5). FBX export mirrors Y, which the UE import undoes with a 180 degree turn (measured, Session 3s).

**Fixed by Tribe (measured, Sessions 3t and 3v; world cm):**

| thing | value | consequence |
|---|---|---|
| DJ rig BP_Rig_C | (-5, 31, 78), PlayerStartDJ (-6, 87, 1) facing -Y | the booth table top sits at 74 cm, x -95..85, y -5..50 (Dino TABLE) |
| Table height handle | user-adjustable, box z 0..69 | a static booth top only fits the current height (known caveat, same as Dino) |
| SpectatorBoundingBox | x -250..250, y -221..279, z -6..494 | Tribe's own 4 spectator cameras stay inside it: keep it clear of geometry |
| SpectatorCamera1 | (-2, -86, 176) looking +Y | the "front" stream shot: the DJ with the screen, portal and towers behind; compose for it |
| BP_MiniMenu | (-5, -6, 93), box x -73..65, z 89..191 | nothing within that box |
| Pointer / menu rays | line traces | every StaticMeshActor NoCollision via set_collision_profile_name, or the menu dies (Session 3q) |
| Visuals back wall UVs | U = 0.5 - x/w, V 0.5 (top) .. 1.0 (bottom) | copy dino_stage.visual_screen_uv exactly (Session 3v) |

**Stage frame (meters, pre-drop):** stage deck x -25..25, y -4.5..13.5, top z=0; barrier y=-7.5; crowd rows y -8.6
to about -66 with half-width crowd_half(y) = 20 + 0.55(-y) (19 m at y=-10 m, 56 m at y=-66 m); visuals screen
23 x 12.94 m at y=10.3, center z=7.2 (bottom 0.73, top 13.67).

**Top-down sketch (meters, not to scale):**

```
 y=+90   . . . . . . . . . . . . . . [BLOOD MOON disc, z=34] . . . . . . . . . . . .
 y=+30         ruined nave footprint (roofless dark walls, seen only from the aerial)
 y=+14   ====[TOWER L]=====[ portal / clock / gable ]=====[TOWER R]====   facade, x -30..30
 y=+10.3                        [ VISUALS SCREEN 23 x 12.94 ]
 y=0..13.5  (dead oak L)   stage deck, rig truss, flame jets at the lip (y=-4)   (dead oak R)
 y=0                               [DJ riser + altar booth]  <- Tribe floor
 y=-7.5    ~~~~~~~~~~~~~~~~ iron fence barrier with lanterns ~~~~~~~~~~~~~~~~
 y=-8..-66         CROWD (graveyard field, fog sheets)        half-width 20+0.55(-y)
 side strips      |tombstone rows, mausoleums (delay stacks)|  both sides, 3..14 m past the crowd edge
 lanes            |vendors: hearse trucks, coffin bars       |  backs at crowd_half(y)+17.6 (Dino rule)
 beyond           |dead forest ring, lanterns, crows          |  |x| > crowd_half+24 and y < -75
 y=-31                      FOH mausoleum "GRAVEYARD SHIFT" banners
 y=-42, -65                 crypt speaker towers at x=+-17 / +-15
 back-left (-60,-110)       HAUNTED CARNIVAL: carousel, House of Horrors, wagons
 back-right (+45..75, -80..-100)  PUMPKIN PATCH, Pumpkin King, scarecrows
 back-right (+60,-125)      THE CRYPT second stage, LED wall, 100 people
 y=-95..-130                SWAMP: dark water plane, will-o-wisps
 r=480                      storm sky sphere; far ground black
```

---

## 4. The set, piece by piece

All of it is built procedurally in `hw_stage.py` (the Dino generator's structure, adapted), baked with Cycles like
Dino, exported as one FBX per surface, and imported as MICs of Tribe's unlit glTFRuntime parents (stock build) or
fork-cooked materials (animated build). Tris are estimates.

### 4.1 Cathedral facade (SM_HwFacade, bake 4096, ~45k tris)
- Facade plane at y=14, x -30..30. Two towers centered x=+-24, footprint 8 x 8 m, z 0..36. Left spire intact to 46 m;
  right spire snapped at 40 m with a jagged top (the ruin cue). Towers get 3 tiers of pointed windows per face
  (glow cells: red, purple, green, amber; the windows are the "windows" cue row), string courses, corner pinnacles.
- Nave gable between the towers: wall top z=22 at the towers, peak z=27 at x=0. Broken crenellations along the top.
- Portal: a splayed gothic archway from the facade (y=14) forward to y=10.0, jambs stepping in 4 orders, apex ~15.5 m.
  The visuals screen is its back wall, so the video sits at the end of a 4 m deep stone reveal (strong depth cue in
  VR). Nothing of the portal crosses the 23 x 12.94 m picture.
- Clock face at (0, 14, 21), r=3.2 m: disc, 12 marks, two hands (the hands are a rigid cue motion, section 7).
- 6 flying-buttress fins (wedges) on the facade, 8 gargoyles (one per tower corner, ~600 tris each) with open mouths
  at the laser origins, 2 rose windows blind (stone) to keep the glow budget on the tower windows.
- Behind the facade, a roofless "nave" footprint 30 m deep in dark stone, so the aerial and the drone reel see a ruin,
  not a flat card.
- Materials (bake keys in hw_kit.LIT): stone_dark, stone_moss (green-grey), iron_rust, wood_rot. Window glass is glow.
- Cut if late: the nave footprint and the buttresses.

### 4.2 Blood moon (SM_HwMoon, ~200 tris)
Disc r=14 m at about (-30, 100, 80): high and off-axis, so it clears the gable from the crowd field and from the
stream and drone cameras. The concept blockout (2026-10-06) showed that a moon low behind the gable is hidden from
everywhere on the field; the DJ never sees the moon over the facade either way (the 26 m gable 14 m behind them covers
the sky to ~62 degrees), which is fine: the DJ gets it in the VJ loops. Texture T_HwMoon: a procedural red-orange moon
with maria and a dark limb. Animated build: slow cloud drift across it (scrolling noise mask) and a faint pulse on the
wash row. It stays below 45% luma (it is the largest bright area, same lesson as the lava moon). Dino's moon sits behind
the screen; this one sits in the sky, so it also shows when Tribe's visuals are on.

### 4.3 Visuals screen (SM_HwVisualScreen)
Same geometry as Dino v7.1: 23 x 12.94 m quad at y=10.3, Tribe's UV0 layout from `visual_screen_uv`, plain black MIC;
the mod registers it as the BackdropMesh and forces fill mode. See section 9.3 for the one hook detail (the mod finds
the screen by mesh name). Option (decision 3): a gothic-arch-shaped screen with 16:9 box UVs, cropping the video's top
corners; our loops keep key art inside the middle 90% so nothing important is lost.

### 4.4 DJ area (SM_HwRiser, SM_HwBooth, SM_HwDjProps; ~12k tris)
- Riser as in Dino (Tribe's floor), skinned as a stone altar platform with a carved skull frieze (baked, not glow).
- Booth front: a coffin-lid shape under the gear at the Dino TABLE dimensions (x -0.95..0.85, y -0.05..0.5, top 0.74),
  with a slow "ember" scroll texture in the animated build (Dino's scroll_tex factory). Static top: same caveat as Dino.
- Two gargoyles (3 m) flanking the riser at x=+-2.6, y=0.3, eyes red glow (eyes = cue row "eyes", pulse on the drop).
- Candle clusters on the riser corners at x=+-1.6, y=+-0.9 (glow key candle; flicker material in the animated build).
  Nothing within 60 cm of the table edge, so the controllers never clip a prop.
- A cauldron at (-3.2, 1.2, 0) with a green glow puff (one translucent billboard quad, animated scroll), a raven on the
  booth's left corner, cobweb quads (two-sided masked) on the riser rails, skull piles at the riser foot.
- Hanging lanterns on chains from the portal truss, lowest point z >= 3.6 m (the DJ's head is ~2.6 m pre-drop + the
  riser's 1 m: keep 1 m of air above it).
- Deck lamps: two level spot lights HwDeckLamp_L/R exactly like Dino's DECK_LAMPS (3 cd, radius 140, cones 38/20
  degrees, no shadows), warm orange. The user wanted "a small light on the decks, not the entire stage" (v6.2).
  tribemod/lights.txt can scale them by name.
- Cut if late: cauldron, raven, cobwebs.

### 4.5 Rig and lasers (SM_HwRig, SM_HwLenses, SM_HwLasers; ~25k tris)
- 22 moving heads: 4 clusters of 4 on tower balconies (z=18 and z=28, both towers), 6 on a truss across the portal top
  (z=16.5) aimed at the crowd, 4 on the deck as facade uplights (orange, purple).
- Lens palette texture T_HwLens: white, orange, purple, green, red, amber, warm, blue (the LENS_U scheme).
- Stage look exported by hw_atmosphere as STAGE_AIMS / STAGE_ANGLES / STAGE_COLORS (the Dino contract), so the heads
  in the bake and the beams in the show agree.
- Lasers: 4 fans from the gargoyle mouths at (+-26, 14, 36) and (+-22, 14, 36): red and green, 9 to 13 lines each,
  sweeping over the crowd (laser_sweep WPO with pan then tilt, Dino's material), plus 1 red fan from the portal apex.
  UV1-3 pivot data and UV4 LaserCue per the atmosphere.py "lasers" contract.
- Clearance gates (same tool family as atmosphere_lasercheck.py): no beam within 0.46 m of the set, DJ head gap
  >= 4.9 m, nothing crosses the screen.
- Cut if late: the portal fan.

### 4.6 Sky and ground (SM_HwSky, SM_HwGround, SM_HwFarGround)
- Sky sphere r=480 m (Dino's), texture T_HwSky 4096 x 2048: near-black zenith, a deep purple-grey cloud deck
  (procedural noise), a thin orange-red horizon band (distant fires), a few stars through gaps. The moon is NOT in the
  sky texture (bats cross it, the lightning brightens clouds around it).
- Animated build: the sky is a custom material (hw_materials.lightning_sky) whose emissive rises with the "storm" cue
  row; stock build: a MIC, static.
- Ground: the crowd field as a graveyard lawn with dirt paths (bake 4096, grows to 320 x 320 m like Dino). Far ground
  black (0.004, 0.004, 0.006).

---

## 5. Grounds modules

Same contract as grounds/kit.py (`build(rng)` returns lit / glow / beams / halos / lights / exclude / people, plus the
"lasers" list the atmosphere module uses), deterministic with seed 1234, one baked mesh per module. They import
`hw_kit` (section 9.1), which extends the shared palette in-process without editing kit.py. Each module gets a
preview harness run before integration, exactly as the Dino modules did. Tris and counts are estimates; keep each
module under its number or trade within the section.

| module | contents | tris | lights | people |
|---|---|---|---|---|
| hw_graveyard | tombstone rows (400: slabs, obelisks, celtic, a few crosses) in the side strips 3..14 m past the crowd edge, 4 mausoleums (6 m) at y=-25/-50 both sides that house the delay stacks, 20 coffins (lids are a cue motion), 6 open graves with static arms, iron fence barrier at y=-7.5 with lanterns, dead hedges; green/purple uplights in the stones | 30k | 24 | 20 ghouls standing between stones |
| hw_forest | dead-tree ring: 120 L-system trees 12..25 m (near: 500 tris; far: 60-tri black glow silhouettes, the Dino trick), 2 giant dead oaks (30 m) at (+-36, 6) flanking the towers with hanging lanterns, crows on branches (static), 40 lanterns | 60k | 30 | 0 |
| hw_carnival | back-left (-60, -110): haunted carousel 12 m with skeletal horses (glow outlines), HOUSE OF HORRORS facade with marquee bulbs (Dino's chase material), fortune-teller wagon, ticket booth, strongman tower, 2 candy wagons | 35k | 26 | 60 |
| hw_pumpkins | back-right (+45..75, -80..-100): pumpkin patch (300 pumpkins at 24-60 tris, 80 with lit faces, flicker in the animated build), Pumpkin King 8 m (jaw is a cue motion), 6 scarecrows, hay bales, corn rows as opaque low-poly stalks (no masked cards: overdraw) | 30k | 12 | 25 |
| hw_crypt | THE CRYPT second stage at (+60, -125): a stone crypt with an LED wall (chase material), truss, 2 stacks, its own 100-person crowd (via the "people" list), purple beams; and the swamp at y -95..-130: dark water plane with baked moon glints, 60 will-o-wisps (orbit WPO glow dots) | 25k | 10 | 100 |
| hw_vendors | 14 units with their backs at |x| = crowd_half(y)+17.6 (Dino rule): WITCH'S BREW (bar), GRAVE DIGGER DOGS, BAT BITES (tacos), POISON APPLES, SCREAM CREAM, BLOOD BANK (red drinks), BRAINS (noodles), CURSED MERCH, MORGUE LOCKERS / CHARGE, HEX BURGERS, BONE BROTH, COFFIN COFFEE, plus 8 outhouses with a skull WC light tower; hearse food trucks and coffin bars; festoon masts in orange/purple | 25k | 40 | 110 |
| hw_infrastructure | FOH mausoleum at (0, -31) with GRAVEYARD SHIFT LED banners (dripping variant of the 5x7 font: extra pixels below letters), 2 follow spots on the DJ, 4 crypt speaker towers at (+-17, -42) and (+-15, -65) with purple sky beams, 4 light masts, roof at the DJ's eye height like Dino's FOH; TOTEMS off (the crowd carries them) | 15k | 14 | 18 |
| hw_atmosphere | 4 searchlight units (purple/green, 340 m beams), STAGE_AIMS for the 22 heads, the 5 laser fans, beam and halo quads (<= 90 and <= 90), fog sheets, flame jets, lightning bolts, bat flock and ghost spawn data (UV-encoded), overdraw and clearance checks | 4k + quads | 0 | 0 |

Module order of value (build first if time is short): graveyard, forest, atmosphere, infrastructure, vendors,
pumpkins, carnival, crypt.

---

## 6. Crowd

Base: crowd v3 (`crowd2/crowd3.py`, same API as v2), used as-is for bodies, friend groups, riders, flow artists, field
density, tiers and the VAT. The Halloween layer is a copy, `hw_crowd.py`, with the same `build_crowd2()` API and these
changes (the knobs table in crowd2/README.md names where):

- **Costumes** (`make_person()`): skeleton (black outfit with bone stripes as vertex color), witch (cone hat, cape),
  zombie (torn tops, greenish skin tint, "lurch" clip bias), pumpkin head (sphere head, orange, glow face quad),
  ghost (sheet over the body, two-sided), devil (glow horns red, cape), vampire (cape, collar), mummy (wrap stripes),
  cat (ears, tail), a few inflatable dinosaurs as a Dino callback. Target: 55% costumed, 45% ravers in Halloween glow.
- **Glow accessories** (the SM_HwPhones mesh): orange and purple glowsticks, LED horns, light-up masks, jack-o-lantern
  buckets, phones; totems with skull and pumpkin heads; LED frames in orange/purple/green.
- **Clips**: the 17 existing clips. Tempo via `vat_crowd(bpm=140)` (the parameter exists). For half-time dubstep,
  raise HALF_TIME_OK toward 70% and weight headbang / pump / jump up in the front zone, sway / nod / hold behind.
  If the VAT author has time: 2 new clips, "lurch" (zombie two-step) and "claw" (the Thriller arms). Not on the
  critical path.
- **Darkness**: bake exposure 0.55 x NIGHT 0.5 as Dino v6 (0.275), show-lit by the wash row with floor 0.06.
- **Budget**: same tiers (near < 12 m ~874 tris, mid < 18.5 m ~256, far ~21), target 4,250 field + riders + module
  extras, about 330k tris, VAT 2048 x 1024 (16 MiB). Measured on Dino: 71-72 fps with this crowd.
- Cut if late: ship crowd v3 unchanged with the glow colors swapped (a 20-line change) and add costumes afterwards.

---

## 7. Motion, weather and the show

### 7.1 The cue table (hw_show.py)
Same mechanism as show.py: a 32 bar x 16 row linear data texture T_HwCues (R level, G strobe, B pulse), one loop at
140 BPM = 128 beats = 54.86 s, read by `dino_materials.cue_level` (the texture is a parameter; the module's
BEAT_HZ / SHOW_LOOP_S constants are set for 140 at build time, and every factory gets its rate passed explicitly).
Rows: stage 0, wash 1, search 2, fan 3, garg1-4 4-7, infra 8, crypt 9, lenses 10, windows 11, storm 12, always 13,
fire 14, eyes 15. The program follows the section-2 mood table; strobe is forced to 0 everywhere (Dino's comfort rule),
the wash never pulses per beat.

A **smooth variant**, `cue_level_smooth` (lerp between bar b and b+1 by the fractional bar), is added in hw_materials
for motions; the nearest-sample version stays for lights.

**Macro cycle.** An hour-long set repeats a 55 s loop about 65 times, so a second, slow layer runs on Time with a
16-minute period: the storm's strike probability rises over 12 minutes and resets, the clock's minute hand sweeps a
full hour and the face flares red at "midnight" (a 2-bar swell, not a flash), the moon's cloud cover thins and
thickens. Shader Time stays precise enough for this for hours (float32 at 3600 s resolves ~0.2 ms).

### 7.2 Ground fog (new; translucent sheets)
- 2 flat sheets over the crowd field (x +-50, y -8..-72) at z = GROUND_Z + 0.25 and + 0.6, and 1 sheet over the deck
  around the riser (y -4.5..2) at deck + 0.2, which puts the DJ a meter above a fog-covered deck.
- Material: unlit translucent, two scrolling noise tiles multiplied, soft vertex-alpha edges, tinted dark grey and
  multiplied by the wash row, so it only shows when the set is lit. No depth fade (assumed unavailable on this mobile
  forward path; if it works, use it; the design does not need it).
- The sheets cut through the front rows' shins, hidden by the noise and the distance (>= 8 m from the DJ). If it
  shows in the headset test, lower the top sheet.
- Gate: overdraw. The Dino beams measure 0.57 layers/px from the DJ (hw_atmosphere keeps the atmosphere_overdraw.py
  method). Fog adds up to 3 layers over the lower half of the view. Ship 2 sheets by default; the third only if the
  on-device fps gate holds.

### 7.3 Lightning (sky row "storm")
- The sky's emissive rises with the row, attack >= 3 frames (~45 ms at 72 Hz, so never a one-frame hit), decay ~400 ms,
  peak sky luma capped at 35%. 2 to 3 bolt meshes (glow polyline quads) at (+-60, 100) and (30, 140) m behind the
  cathedral, alpha from the same row, never over the crowd or the DJ.
- Rate: none in intro/breakdown, one strike per 4 bars in the build, one per 2 bars at the drop, fading in the outro.
  Far under 3 per second. The wash row gets a small bump with each strike so the set catches the flash.
- Stream viewers see the wall and the sky; the caps above keep it within the no-strobe rules the user set.
- Decision 5: lightning on by default with these caps, or off.

### 7.4 Flame jets (row "fire")
6 jets at the stage lip, x = +-6, +-12, +-18, y=-4: two crossed 2 m cards with a scrolling fire texture T_HwFire
(procedural), alpha-masked soft, orange (luma ~0.5). Fire only at the drop, 1-bar bursts with 2-bar gaps (0.5 per
second). Nearest jet 6 m from the DJ.

### 7.5 Flocks and ghosts (WPO)
- Bats: 3 flocks x 50, each bat 6 tris (body + two wing quads) with UV-stored flock center, radius, phase; WPO orbits
  the flock center (RotateAboutAxis, the laser_sweep technique) and flaps the wings (sin on the wing quads). Flocks
  circle the moon, the left tower and the graveyard back; never low over the crowd.
- Ghosts: 8 two-sided translucent sheets (~1.1k tris each) with a sin waver along UV and a slow orbit path; alpha 0.2 to
  0.3, greenish-white dim. Over the graveyard sides and between the towers at z ~30, >= 15 m from the DJ.
- Will-o-wisps: 60 glow dots over the swamp, the same orbit material with small radii.

### 7.6 Rigid cue-driven hero motions (WPO translate/rotate by cue_level_smooth)
1. Two 12 m skeletal hands rise out of the deck at x=+-22, y=4 (flanking the screen, in front of the towers) over the
   build, hold at the drop, sink in the breakdown.
2. Graveyard coffin lids swing open at the drop (RotateAboutAxis about the hinge stored in UV).
3. The Pumpkin King's jaw opens on the drop.
4. The clock hands (macro cycle, section 7.1).
Each is one small material built with the ModMaterialTools plugin (the laser_sweep precedent is 47 nodes). No VAT is
needed for props; VAT stays for the crowd.

### 7.7 Comfort check (new tool, hw_cuecheck.py)
Reads T_HwCues and the material rates and reports: flashes per second per row (attack < 3 frames counts as a flash),
the brightest bar against the mid-bar average, and strobe flags. Must pass before any animated build is pushed. The VJ
loops keep using check_loop.py.

---

## 8. Visuals wall: the VJ loop pack

Spec as Visuals/CONCEPTS.md with two changes: 140 BPM half-time, and a frame count that follows from it. At 30 fps,
140 BPM is 12.857 frames per beat; 8 bars = 32 beats = 411.43 frames, so a loop is **411 frames (13.70 s), beat k on
frame floor(12.857k + 0.5), frame 411 equals frame 0**. The rounding makes the loop run at 140.15 BPM, a 0.1% error
that is irrelevant because a fixed-tempo video cannot follow a live 128-150 BPM set anyway; beat pulses stay subtle
(the user's tempo memory). vjkit.py already computes FRAMES = round(BEATS x FPB) and BEAT_F from a non-integer FPB
(measured in the kit); whether BPM is already an argument is to be checked (assumed one line if not).

Half-time hooks: accents on the kick (beat 1) and the snare (beat 3) of each bar; drops are carried by motion and
wobble (slow LFO scale/rotation at 1 cycle per bar), not by flashes. Same look rules: Standard view transform, one
tight Bloom, black backgrounds, key art inside the middle 90%, every 1 m^2 block under 70% luma, no strobes.
Files go to `/sdcard/Movies/Halloween Visuals/` on the Quest.

| # | loop | slot | picture | beat hook |
|---|------|------|---------|-----------|
| 1 | Witching Hour | intro | the gable clock in neon purple ticks toward midnight; the second hand jumps per beat; at bar 8 it strikes and the face flares red (a swell) | second hand per beat |
| 2 | Candlelight Seance | breakdown | a ring of candles on black; flames breathe on the half-time pulse; a planchette glides, spelling letters on bars 1 and 5 | flames on 1 and 3 |
| 3 | Bat Swarm | build | bats pour out of a cave mouth toward the camera, wings flap on 8ths, the swarm thickens into the next phrase | flap on 8ths, swell into bar 8 |
| 4 | Thriller Yard | build | tombstone silhouettes on a UV-purple horizon; zombie hands and heads rise one row per bar, arms claw on the snare | claw on 3 |
| 5 | Hellgate | drop | iron gates swing open on frame 0 and hellfire rolls out (orange, not white); embers and a wobble-driven heat shimmer through bars 1-5, the gates close over bars 6-8 to re-open on the loop | gates on the downbeat, wobble per bar |
| 6 | Pumpkin Stomp | heavy drop | giant jack-o-lantern faces slam toward the camera on each kick, cracks glow green; every 4th is a king-sized one | stomp on 1 and 3 |
| 7 | Dead Forest Ride | build into drop | fly-through of neon dead trees over a laser-grid path (the Spine Tunnel method: geometry runs on past the backdrop), lanterns pass per beat, the moon with bats at the end; the palette morphs green on bar 5 | lantern per beat |
| 8 | Blood Moon | outro | the moon fills the screen behind the broken spires; clouds drift, bats cross, searchlights sway once per 2 bars | bulb-ring style pulse on 1 |
| + | GRAVEYARD SHIFT sting | ID, 4 bars | letters drawn from bone segments drip into place on the downbeat, pulse per beat, crumble on the last beat | identity |

Render budget (measured on Spine Tunnel): about 4 minutes per loop at 1080p30 with 16 EEVEE samples on the 1660S,
plus 30 s to encode. Nine loops is about an hour of GPU time, scheduled around bakes (section 10).

---

## 9. Technical architecture

### 9.1 File layout (nothing shared is edited)

```
C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\halloween\
  hw_stage.py          the generator (dino_stage.py's orchestration adapted: build, drop, bake, export, manifest)
  hw_kit.py            `from kit import *`, then extends kit.GLOW / LIT IN-PROCESS (new keys appended, PAL_ROWS
                       recomputed) and adds Halloween helpers: gothic_arch, tracery, tombstone, coffin, pumpkin,
                       dead_tree (L-system), gargoyle, lantern, led_text_drip. Writes T_HwGroundsPal.
  hw_show.py           the cue table at 140 BPM (tex_cues / write_png_linear reused from show.py)
  hw_crowd.py          crowd3.py copied, Halloween make_person(); same API
  modules\             hw_graveyard.py hw_forest.py hw_carnival.py hw_pumpkins.py hw_crypt.py hw_vendors.py
                       hw_infrastructure.py hw_atmosphere.py, plus hw_preview.py (grounds/preview.py adapted)
  checks\              hw_lasercheck.py hw_overdraw.py hw_cuecheck.py hw_clearance.py
  out_hw\              bakes and FBX (HW_OUT=<dir> for test builds; --fast for the 2.5 min pipeline test)
C:\Users\Chris\TribeUE\TribeXR\Scripts\build_halloween.py   UE import: /Game/Mods/Halloween, chunk 54, its own
                       SURFACES and ANIM tables; helper functions copied from build_dino.py (that file runs its
                       build at import, so it cannot be imported); env HW_SRC, HW_CHUNK, HW_ANIM
C:\Users\Chris\TribeUE\TribeXR\Scripts\hw_materials.py      imports dino_materials for the shared factories (cue_level,
                       show_lit, beams_material, laser_sweep, chase, scroll_tex, strobe_tex, vat_crowd); adds
                       cue_level_smooth, flicker, fog_sheet, lightning_sky, fire_card, flock_orbit, ghost_waver,
                       rigid_cue (translate / rotate), moon_clouds
C:\Users\Chris\TribeUE\MetaHw\TribeXR     a fork-project copy like MetaVat: Config/Plugins/Scripts from Meta\TribeXR,
                       Content\Mods\Halloween only, its own Saved\Cooked and ModPak (no cook collisions with the Dino
                       session). ~4-5 GB; C: has 59 GB free, D: 334 GB (measured 2026-10-06)
C:\Users\Chris\TribeUE\Visuals\halloween\  CONCEPTS.md + one scene script per loop on vjkit.py; renders\<loop>\
C:\Users\Chris\TribeUE\paks_current\       EVERY current pak from both stages; the only input to the OBB (9.4)
tribe hack\scripts\push_obb.sh             zips paks_current\*.pak with make_obb.py, pushes via /data/local/tmp, mv's
                       over the patch OBB (the open-inode trick), prints md5
tribe hack\claudedocs\halloween_stage_notes.md   this work's running log (NOTES.md belongs to the Dino session)
```

Shared modules are imported, never edited: grounds/kit.py, show.py, crowd2/crowd3.py, dino_materials.py. If the Dino
session changes a contract (kit's `build()` dict, crowd3's API, dino_materials signatures), hw_stage.py's start-up
assertions name it and the Halloween copy adapts. Duplicated helpers (build_dino's import functions) are a deliberate
trade: no edits to a file the other session is editing. Unify after both stages ship.

### 9.2 Build and ship (per iteration)
1. `blender -b --factory-startup --python halloween/hw_stage.py` (full bake ~20 min on the 1660S by Dino's measure;
   `-- --fast` for a 2.5 min pipeline check). Writes out_hw\ with manifest.txt and show_groups.json.
2. `UnrealEditor.exe <MetaHw>\TribeXR.uproject -ExecutePythonScript=build_halloween.py -unattended -nosplash -nullrhi`
   with HW_ANIM=1 for the animated build.
3. Cook with the fork: `MSYS_NO_PATHCONV=1 UnrealEditor-Cmd.exe <uproject> -run=cook -targetplatform=Android_ASTC
   -unversioned -map=/Game/Mods/Halloween/Maps/Environment_Halloween`. The first cook of the new project compiles the
   global shaders (37 min, measured on Meta); later cooks are minutes.
4. `pack_chunk.sh 54` -> pakchunk54-Android_ASTC_P.pak (with ShaderArchive-TribeXR_Chunk54) -> copy into paks_current\.
5. `push_obb.sh` (section 9.4). Tribe must be relaunched: paks mount only at launch (measured, Session 3s).
6. `tribemod/envs.txt` gets the line `Graveyard Shift=/Game/Mods/Halloween/Maps/Environment_Halloween`, and
   scripts/reseed.sh's ENVBK copy gets it too, or the next re-seed drops the box.
7. Device gate from logcat `[ENV]`: load <= 2 s, the screen registers ("is Tribe's backdrop now"), fps windows at
   71-72, no frame over 20 ms outside the load. The user confirms the pointer and a media-folder video on the screen.

### 9.3 Mod (hook) changes: one line now, two small features later
- **Screen lookup.** `em_register_backdrop` finds our screen with `em_find_mesh_actor("SM_DinoVisualScreen")`, which
  compares the StaticMesh asset's NAME (measured, dumper.cpp ~2238). Stopgap with zero hook changes: the Halloween
  level's screen mesh asset is also named SM_DinoVisualScreen, in its own package (/Game/Mods/Halloween/Meshes/),
  so only one exists in the loaded level. Proper fix: match any mesh name ending in "VisualScreen" (a strcmp becomes a
  suffix test). Because the Dino session also builds APKs, the proper fix is handed to whoever next rebuilds the hook,
  not done in parallel.
- **Per-environment drone reel** (later): drone_path.txt is global and re-read live. Either the user swaps the file for
  the Halloween stream, or the hook tries `drone_path.<label>.txt` first. Small change, same rule about who edits.
- **Lights** need nothing: lights.txt matches by name part, and the Halloween lamps have their own names.
- **Live tempo** (optional, both stages benefit): the mod knows Tribe's BPM address (TribePlayerController +0x97c,
  found in Ghidra, never read live) and already sets MPC parameters through KismetMaterialLibrary. Writing the live BPM
  into a collection our materials read would let the show and the crowd follow the set from 128 to 150. Blocked on a
  collection we can reference: shipping our own UMaterialParameterCollection needs a ue_schemadiff SAME check first.
  Research item, not on the critical path.

### 9.4 The patch OBB is shared: one rule
`make_obb.py` writes a fresh zip from the paks it is given. A push that lists only one stage's pak **removes the other
stage from the headset** (silently: the box stays, the level fails to load). Rule for both sessions: every pak that
should be on the device lives in `TribeUE\paks_current\`, and the only way to push is `push_obb.sh`, which zips that
folder. Dino's chunk 50 (and 53 if kept) go in there on day 1.

---

## 10. Working next to the Dino session

Collision list, and the rule for each:

| shared thing | hazard | rule |
|---|---|---|
| patch OBB on the device | one push drops the other stage | paks_current + push_obb.sh only (9.4) |
| tribemod/envs.txt, reseed.sh ENVBK | a re-seed restores a stale list | both lines in both places; append, never rewrite |
| the hook APK (dumper.cpp, sign_apk.sh, reseed.sh MOD=) | two edits to one C file; `install -r` may end the Meta token | one editor at a time; Halloween hook changes are handed over as patches; APK freeze by day 20 |
| NOTES.md | concurrent edits | Halloween logs to claudedocs\halloween_stage_notes.md; a summary goes into NOTES.md only at a quiet point |
| Scripts\Blender\out, Meta\TribeXR\Saved | bake and cook outputs | Halloween never writes there (out_hw, MetaHw) |
| kit.py, show.py, crowd3.py, dino_materials.py, build_dino.py | contract drift | import only; start-up assertions; adapt on our side |
| the GTX 1660S and the 6-core CPU | a 20 min bake, a 4 min loop render and a cook fight for the GPU/CPU | check for a running blender/UnrealEditor-Cmd before starting a heavy job; bakes in the user's away hours; loops queued after bakes |
| the one headset and the one tester | every device gate needs the user | batch device tests: at most 3 a day, each with a written pass/fail list; never two unpushed OBBs waiting |
| Blender agents' scratchpad | the Dino team hit a "final" folder collision | unique folder names with an hw_ prefix |

---

## 11. Phases, gates and schedule (assumes the stream on 2026-10-31)

Each phase ends shippable; nothing waits on a later phase to look finished. Dates are targets.

| phase | days | work | gate |
|---|---|---|---|
| 0 Scaffold | Oct 6-8 | folders, MetaHw project copy, paks_current + push_obb.sh, envs.txt line, hw_stage.py blockout (facade boxes, towers, portal, screen, riser, ground, sky, barrier) MIC-only, chunk 54 | loads in <= 2 s, pointer works, a media-folder video fills the screen, 71+ fps, Dino still loads from the same OBB |
| 1 The set | Oct 8-13 | cathedral detail, windows, gargoyles, clock, moon, DJ area, rig + 5 fans, sky texture; first full bake; stock build | previews (dj_front, stream, crowd, aerial) approved in chat; laser clearance passes; headset pass |
| 2 Grounds | Oct 9-16 (parallel agents) | hw_kit helpers, then graveyard + forest + atmosphere first, infrastructure + vendors next, pumpkins + carnival + crypt last; previews per module | overdraw <= budget, no keep-out overlaps with the crowd, each module under its tris number |
| 3 Crowd | Oct 12-17 | hw_crowd costumes and glow, tempo knobs, VAT; optional 2 clips | crowd preview line-ups approved; fps >= 71 on device with the full stage |
| 4 Animated build | Oct 14-20 | hw_show cues, hw_materials (flicker, fog, lightning, fire, flocks, ghosts, rigid motions), fork cook with the chunk-54 shader archive, hw_cuecheck | "Shader Test"-style device gate: motions visible, cue check passes, fps holds; the user's comfort verdict in the headset |
| 5 Media | Oct 15-24 (GPU queue) | 8 loops + sting rendered and checked, Halloween drone reel, avatar skin if wanted | check_loop.py passes on every loop; the reel plays through once with no clipping into geometry |
| 6 Polish and freeze | Oct 24-29 | the user's headset notes, two polish iterations max, APK frozen by Oct 26, content (OBB) frozen Oct 29 | a full dress rehearsal stream segment on Oct 29 |
| Stream day | Oct 31 | section 13 checklist | |

Parallelism: phase 2's modules run as 3 to 4 agents at once (the Dino grounds were built that way, 4 agents, one
afternoon); phase 5's loops are independent renders. Phases 1-3 are serialized on the generator and the bake.

---

## 12. Decisions for the user (with recommendations; the plan proceeds on the recommendation if unanswered)

1. **Stream date.** Assumed 2026-10-31.
2. **Name.** GRAVEYARD SHIFT (recommended), NECROPOLIS, WITCHING HOUR or HALLOWS STAGE.
3. **Screen shape.** 23 m 16:9 rectangle in the portal (recommended: the video fills it exactly), or a gothic-arch
   screen with 16:9 box UVs (crops the top corners).
4. **Tempo.** 140 BPM half-time for the show, the crowd and the loops (recommended, per your sets), or 128 like Dino.
5. **Lightning.** On with the caps in 7.3 (recommended), or off.
6. **THE CRYPT second stage.** Include (recommended) or drop it to save budget.
7. **Avatar skin.** A Halloween skullbuck skin through the existing skins pipeline (tribemod/skins, check_skin.py):
   yes or no. Not part of the stage build.
8. **Ambient audio** (thunder, crows). Default OFF: Tribe mixes level audio into the headset and probably the stream
   (assumed; untested), and sound asset classes have not been schema-checked against the fork. Only if you want it.

---

## 13. Stream-day checklist (from Sessions 3e, 3h, 3v)

- Two days before: content frozen; `push_obb.sh` of the final paks_current; relaunch Tribe; load both stages once.
- The day before: re-seed the Meta token if Go Live has not been exercised in the last 2 days (the token lasted 3-4
  days on 2026-10-06; scripts/reseed.sh restores the patch OBB, envs.txt, drone files, flags and storage permissions).
  Do NOT `adb install -r` a new APK after the final re-seed.
- Media: `/sdcard/Movies/Halloween Visuals/` holds the 9 loops; test one on the wall from the Media tab.
- Camera: the Halloween `drone_path.txt` in place (or the per-env reel), `drone.txt` mode=path; run the reel once.
- Lights: `lights.txt` has the HwDeckLamp lines if the user wants them scaled.
- In the headset: pick Graveyard Shift, confirm the pointer, the screen video, the fps feel, and the comfort of the
  lightning and fire during one drop before going live.
- Fallback: the Dino Stage is in the same OBB. Switching takes one click.

---

## 14. Risks, ranked (probability x cost x silence)

1. **OBB clobbering between sessions.** Silent, likely without a rule. Mitigation: 9.4, from day 1.
2. **Translucent overdraw (fog, fire, ghosts, beams) costs frames.** Loud on device (fps), silent in previews.
   Mitigation: overdraw measurement per module, 2 fog sheets by default, the fps gate before anything ships.
3. **Comfort: lightning and fire read as strobes to the user or the viewers.** Mitigation: attack >= 3 frames, luma
   caps, rates in 7.3/7.4, hw_cuecheck, and the user's own verdict in phase 4 (decision 5 can turn it off).
4. **Time: one PC, one headset, one tester, two stages.** Mitigation: phases end shippable; module value order in
   section 5; "cut if late" lines; the APK freeze on Oct 26.
5. **Contract drift in shared modules while the Dino session evolves them.** Mitigation: start-up assertions, adapt
   on our side only.
6. **The screen-name coupling in the hook.** Mitigation: the SM_DinoVisualScreen naming stopgap, then the suffix fix.
7. **Fork cook of a second project.** First cook 37 min, disk ~5 GB. Mitigation: start it in phase 0.
8. **Meta token expiry on stream day.** Mitigation: section 13; no reinstall after the final re-seed.
9. **Static booth top vs the adjustable table height.** Known Dino caveat; the user keeps the table where it is, or the
   booth front is built 5 cm lower than the table.
10. **Unverified assumptions:** depth fade on this mobile forward path (not needed), vjkit BPM parameterization (one
    line if not), sound class compatibility (audio off), the hour-long Time precision (derived, fine).

---

## 15. Companion items (not the stage, but the same stream)

- Avatar Halloween skin (decision 7).
- Env box preview image: the mod copies The Void's identity for custom boxes, so the box shows the Void's picture. A
  Halloween preview texture would need a small hook change (set SkinInfo.PreviewImage). Cosmetic; after the stage.
- Live tempo (9.3): a research item that would make both stages follow the set's BPM.
- A per-environment drone reel in the hook (9.3).

---

## Appendix A. Drone reel draft (tribemod/drone_path.txt syntax; world cm, DJ rig at the origin, crowd -Y, stage +Y)

Cathedral towers at x=+-2400, y=1400, tops z=3600-4600; moon at (-3000, 10000, 8000); graveyard strips past x=+-2600;
pumpkin patch around (+6000, -9000); carousel around (-6000, -11000).

```
# moonrise reveal: from behind the crowd, the facade and the moon
fly 12 0,-7000,600 0,-3600,1500 look=0,1400,2400
# graveyard crawl at tombstone height, the stage beyond
fly 16 -5200,-3000,180 -2600,-1200,220 look=0,600,900
# pumpkin patch pass
fly 14 4800,-5200,250 3000,-2800,300 look=0,800,1200
# tower climb to the gargoyle lasers
fly 12 -2600,-900,300 -2600,-200,4200 look=0,1400,2600
# over the crowd toward you
fly 14 0,-2400,700 0,-700,330 look=dj
# close orbit around you
orbit 15 r=260 h=30 deg=360 start=-90
# over your shoulder: the crowd ahead
fly 8 -250,380,260 250,380,260 look=0,-3000,200
# low hero past the flame jets
fly 8 -400,-380,40 400,-380,40 look=0,300,900
# portal push toward the screen
fly 10 0,-1500,500 0,200,900 look=0,1400,900
# crane from the pit up the facade
fly 10 0,-900,150 0,-900,2600 look=0,1400,1600
# carousel to stage
fly 14 -6000,-9000,600 -3500,-5000,900 look=0,0,800
# tighter arc the other way
orbit 10 r=170 h=10 deg=-140 start=-20
```
About 143 s. Cuts on change; eased with smoothstep (the mod's path mode).

## Appendix B. Budgets at a glance

| budget | Dino (measured) | Halloween target | how it is checked |
|---|---|---|---|
| fps | 71-72 at 72 Hz, 0-22 frames > 20 ms per 10 s | >= 71 average, same tail | logcat fps windows (Session 3v method) |
| tris | crowd 327k + set and grounds | <= 600k total: crowd 330k, set 85k, grounds 185k | hw_stage.py per-mesh log |
| actors (draw calls) | 32-33 | <= 40 | build_halloween.py log |
| translucent overdraw from the DJ | 0.57 layers/px (beams) | <= 2.5 incl. fog | hw_overdraw.py (atmosphere_overdraw method) |
| chunk size | 120 MB | <= 130 MB | pack_chunk.sh output |
| load time | 1 s | <= 2 s | `[ENV]` log |
| laser clearance | >= 0.46 m set, >= 4.9 m DJ head, none across the screen | same | hw_lasercheck.py |
| flashes | <= 3/s, no 1-frame hits, no full-frame white, on-beat <= 1.6x | same, plus sky <= 35% luma, fire <= 0.5 bursts/s | hw_cuecheck.py, check_loop.py |
| bake time | 18-19 min full | ~20 min | bake log |
