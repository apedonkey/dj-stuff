# Thanksgiving stage plan: HARVEST MOON, with MAJOR TOM

Written 2026-10-16, after the user approved the concept renders ("looks good. go for it").

Ground rules:
- Nothing here is built for the game yet.
- Phase 0 can start in parallel with the other sessions; it needs no headset until its gate.
- Every headset push and APK install waits for the user's OK, given in this chat. Graveyard Shift keeps first claim on
  headset windows until its stream on 2026-10-31.
- Labels used below:
  - **read** = checked in a file or the code today;
  - **memory** = from the project memory, true when it was written;
  - **estimate** = my number, to be measured;
  - **assumed** = not verified, with the check named.

Concept renders are in `claudedocs/harvest_concept/`:
- `harvest_concept_sheet.jpg` (7 views) and `major_tom_concept_sheet.jpg` (4 views);
- made by `C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\harvest\` (`concept_blockout.py`, `major_tom_concept.py`,
  `run_concept.sh` with the shared GPU lock, `sheet.py`);
- they show layout, scale, palette and the reveal, not the final look.

The running log is `claudedocs/harvest_moon_notes.md`.

---

## 0. Assumptions

| assumption | basis | if wrong |
|---|---|---|
| The stream is Thanksgiving night, Thu 2026-11-26 | not stated; read from the calendar (Black Friday is Nov 27) | phases keep their order; the freeze dates move |
| "As big as Graveyard": set + rig + lasers, field modules, a ~3.9k VAT crowd, the 23 m screen, a cue-table show, a VJ loop pack, a drone reel, an intro | the Graveyard and Midtown plans' inventory | each section has a "cut if late" line |
| 140 BPM half-time for the show, the crowd and the loops | the user plays heavy dubstep, 128-150 BPM (memory) | one constant |
| It ships like the others: one pak in the shared patch OBB, a box in tribemod/envs.txt, the mod's loader | Dino, Graveyard, Reactor (memory) | none |
| Content folder `/Game/Mods/Harvest`, display name **Harvest Moon**, pak **chunk 57**, asset prefix `Hm` | live chunks 50/53/54/55 (read: paks_current/paks.txt); 56 Big Dub, 58 Midtown, 59 free (memory) | renaming the folder renames every per-stage file in section 10 |

---

## 1. Concept and art direction

**One line.** Thanksgiving night on a farm:
- the crowd dances inside a crop circle cut into a dry cornfield;
- the DJ plays in front of a giant red barn;
- the full moon over the barn is not the moon. At showtime it grows a saucer rim, comes down and parks over the crowd;
- on the drops its tractor beam lifts the turkeys off the field.

**Palette.**
- The farm is warm and carries the look: gold (1.0, 0.62, 0.18), amber (1.0, 0.42, 0.07), barn red, warm-white bulbs.
- The visitor is cold and is the accent: green-white (0.45, 1.0, 0.50) / (0.75, 1.0, 0.80), laser green
  (0.15, 1.0, 0.25).
- Not used: Graveyard's orange/purple and Dino's cyan/magenta, so Harvest Moon never looks like either.

**Darkness** (the user's standing rule: dark except the DJ, the visuals, the lasers and the lights):
- The barn, the silos and the field are near black between hits; the concept's v2 barn is the reference.
- The light comes from the trim bulbs, the hayloft, the farmhouse windows, the beam, the lasers and the heads.
- The crowd stays dark. The concept's drop renders show the beam at full; in the build it is capped (below).

**Comfort.** The same rules hw_cuecheck.py and check_loop.py enforce: no strobes, at most 3 flashes/s, no one-frame
hits (every cue ramps over >= 60 ms), no full-frame white, fills swell into the downbeat.
- The new hazard is the beam: one big bright area over the crowd. It swells in and out over at least a beat, never snaps.
  Its core is capped like the lava moon (big bright areas under ~45% luma, memory).

**Mood by set section**

| section | stage | sky and field | crowd |
|---|---|---|---|
| intro | trim bulbs, the hayloft, the ship's portholes dim | stars, low mist, the field dark | sway |
| build | silo lamp bands chase upward, heads wake gold, the crop rings light from the centre out | the beam flickers on as a soft swell | pump, hands up |
| blackout bar | only the portholes and the barn trim | the beam off | hold |
| drop | everything: the beam full, rim lasers to the floor, silo fans, turkeys rise | the crop pattern pulses outward on the kick (ramped) | jump, headbang |
| breakdown | windmill bulbs, farmhouse windows, the rim lights circle slowly | a thin beam core, turkeys drift | sway |
| outro | silo fans alternate, rim lights chase round | the pattern fades from the outside in | shuffle |

**Slow layer.** A ~16-minute macro cycle runs on Time, like Graveyard's:
- the windmill spins up and slows down;
- the rim lights rotate;
- once per cycle the cow rises through the beam over 8 bars and disappears into the bay (a rigid motion).

---

## 2. Layout and fixed constraints

**Frame.** The same frame as Graveyard (memory: grounds/kit.py docstring):
- meters, Z up;
- the DJ at the origin on Tribe's floor, facing -Y;
- the deck top at -1, the field (crowd floor) at -1.5;
- the stage behind the DJ (+Y).

FBX export mirrors Y; the UE import undoes it.

**Fixed by Tribe** (memory, Graveyard plan section 3; world cm):
- DJ rig at (-5, 31, 78): booth top at 74 cm, x -95..85, y -5..50.
- SpectatorBoundingBox: x -250..250, y -221..279, z -6..494. Keep it clear. The open doors' free edges stop at x +-17.4 m.
- BP_MiniMenu box: x -73..65, z 89..191.
- Every StaticMeshActor gets NoCollision via set_collision_profile_name, or the menu ray dies.
- Screen UVs: copy `visual_screen_uv` exactly.

**Top-down (meters; values read from concept_blockout.py):**

```
 y=+140, z 95   THE MOON (the ship's hull at its moon spot, scaled up ~1.5x), clear of the ridge from the crowd
 y=+10..40      THE BARN: x +-22, walls to 16 m, gambrel ridge 30.5 m, lit hayloft door, hay hood + mirror ball
 y=+10.8        VISUALS SCREEN 23 x 12.94 (SM_DinoVisualScreen) inside the door opening (x +-13, z -1..13.5)
 y=+9.8         DOORS 13 x 14.5 m each, hinged at x +-13, X-trim bulbs; shut = over the screen, open = 110 deg out
 x=+-29, y=+20  GRAIN SILOS r 5.5, 31 m + domes; catwalks (heads) at 12 and 24 m; lasers at the domes
 y=-4.5..13.5   stage deck x +-25; hay-bale riser + booth at the origin; bale barrier at y -7.5
 y=-8.6..-16    the front apron, |x| < 30 (crowd)
 CROP CIRCLE    C0 centre (0, -38) r 31 = the dance floor (crowd ~3.9k in the blockout); FOH hay wagon at (0, -52)
                ring path r 36..38.5 around it (standing corn between); scarecrow speaker towers on the corn ring at
                r 33.6, angles 205/245/295/335 deg
 THE SHIP       parked over (0, -38): hull r 14 (bottom z 26), rim r 27 at z 40, beam to the floor r 6 -> 10.5
 sides          satellite circles (+-54, -40) r 8 (bars, merch), joined to the ring path; eye dots (+-40, -72) r 3
 tail           circles (0, -80) r 3.2, (0, -88) r 2.2, (0, -94.6) r 1.4 lead to the back circle:
 y=-106         CRASH SITE second stage: back circle r 9 + its own ring 11.2..12.9; a crashed scout saucer, ~90 people
 farm           windmill (-50, 6), farmhouse (56, 6), pickup (42, -14), tractor (-40, -10), bare oaks
 field          dry corn in rows 0.9 m apart inside an ellipse 165 x 128 m round (0, -55); black ground beyond
```

**Why the moon is where it is.** From the crowd, the barn's ridge stands about 22 deg up. The moon spot (-20, 140, 95)
puts the moon at ~25 deg, rising just over the ridge (read: the concept's moonrise view).

---

## 3. The set, piece by piece

All of it comes from `hm_stage.py`, the Graveyard generator (hw_stage.py) copied and adapted, never edited in place. It
is baked with Cycles, exported one FBX per surface, and imported as MICs (stock build) or fork-cooked materials (animated
build). Tris are estimates.

| piece | content | tris | cut if late |
|---|---|---|---|
| Barn (SM_HmBarn, SM_HmBarnTrim) | gambrel shell, weathered red boards (bake), roof, lit hayloft door, HARVEST MOON sign in the lintel band (LED font), warm bulb trim on the outline and the opening, hay hood with a mirror ball | 10k | mirror ball |
| Doors (SM_HmDoors, hinged) | two 13 x 14.5 m panels with the white X trim as bulb strips on both faces; swing 110 deg on `DoorOpen`, like Graveyard v5's crypt doors (memory; Graveyard also has the hinged-part contract SM_HwHinged + hinge_swing) | 2k | none (the intro needs them) |
| Screen (SM_DinoVisualScreen) | the 23 x 12.94 quad at y 10.8 with Tribe's UV0, in its own package (the name stopgap, section 10) | 2 | none |
| Silos (SM_HmSilos) | two corrugated silos with domes and vents, catwalks with railings, cage ladders, warm lamp bands under the domes (chase row) | 8k | ladders |
| The ship (SM_HmShipHull, SM_HmShipRim, SM_HmShipLights) | hull r 14 with the moon's craters; rim r 27 with 72 portholes, 24 under-rim lamps and an edge strip; the bay disc; modeled PARKED, moved by WPO (section 4) | 8k | under-rim lamps |
| Beam (SM_HmBeam, SM_HmBeamRings) | a translucent cone r 6 -> 10.5 from the bay to the floor, a brighter core, 9 light rings riding up, a glow pool on the ground; alpha from the beam row, overdraw-gated | 2k | rings |
| Abductees (SM_HmAbductees, VAT) | 10 flapping turkeys spiralling up the beam (a VAT in the crowd's format, like Graveyard's rider; memory) and one cow on the macro cycle | 6k | rigid spinning turkeys, no VAT |
| Crop floor (SM_HmCropFloor, SM_HmCropGlow) | flattened-straw floors for the whole formation; glow lines: 4 rings and 12 spokes in C0, the ring path's edges, every satellite's rim, the paths' edges; the "floor" row drives a centre-out chase | 4k | spokes |
| Cornfield (SM_HmCornNear, SM_HmCornFar) | near rows as jagged opaque strips (2-4 tris per 1.5 m), never masked cards (overdraw; Graveyard's corn rule, memory); beyond ~40 m from the formation one textured stripe field + black silhouettes (the Dino far-tree trick) | <= 60k | far field only |
| Farm (SM_HmFarm, SM_HmFarmGlow) | windmill (wheel = rigid spin on the macro layer, bulbs on the blade tips), farmhouse with a porch, lit windows and a porch lamp, pickup and tractor with headlights (baked light pools), 4 bare oaks | 20k | tractor, oaks |
| Scarecrow towers (module hm_towers) | 4 delay towers: a pole, a speaker box in a flannel shirt, a sack head with amber eyes, a straw hat, a sky beam each | 6k | sky beams |
| FOH (module hm_foh) | a hay wagon with the desks, a canopy and the HARVEST MOON LED banner facing the DJ, 2 follow spots | 4k | none |
| Crash site (module hm_crash) | the second stage: a crashed scout saucer tilted into the back circle, its hull panel as an LED wall, a booth, a scorched furrow, a green point light, its own ~90 people | 6k | the whole module |
| DJ area | hay-bale riser, a plank-on-bales booth front, deck lamps HmDeckLamp_L/R (Graveyard's DECK_LAMPS pattern, memory), round bales on the corners; nothing within 60 cm of the table edge | 6k | round bales |
| Sky (SM_HmSky) | sphere r 480 (Dino's): near-black navy, a thin cold haze at the horizon, a star field (instanced dots in the texture, not meshes) | 1k | none |
| Mist | 2 low sheets over the field, 1 over the deck (Graveyard's fog_sheet, memory) | quads | the deck sheet |

---

## 4. The moon that comes down (the hero motion)

**Recommended: no hook change.** The descent rides the intro's door ramp, `DoorOpen`:
- **read** in intro.cpp: `DoorOpen` is set to 1 when a stage with an intro loads;
- it eases to 0 over the file's door time at press 1;
- it eases back to 1 over the same time when the music starts.

Every ship part's material lerps between two states by `smoothstep(DoorOpen)`:
- **0 = the moon:** the hull sits at the moon spot, scaled ~1.5x, its craters glowing warm. The rim is retracted inside the
  hull (scaled to ~0.5 about the centre), the portholes are dark and the beam is off.
- **1 = parked:** the hull is over the crowd at scale 1, the craters cold and dim, the rim out with its lights on.

That gives the right story on its own:
- with no intro, the ship is simply parked over the crowd: the show state;
- at press 1 the barn goes dark, the doors shut and the ship flies back up to be the moon. It does that in the dark,
  while the camera is on the intro ride;
- at showtime the doors swing open and the moon comes down as the track starts.

Details to build and check:
- **Culling.** A WPO-moved mesh is culled by its rest bounds. Set the ship meshes' bounds extensions at import
  (build_harvest.py) to cover both positions. **Assumed** to work through the StaticMesh bounds-extension properties;
  the phase 1 device test checks it.
- **Lasers on the rim.** The rim lasers use the Dino laser engine (dino_materials.laser_show, imported, never edited), so
  they cannot follow the WPO. During the descent the show is still coming up from the intro's blackout (memory: the light
  show holds ShowLevel 0 while the intro is dark), and most tracks open quietly. If a fan visibly fires from the empty
  parking spot, keep the rim fans off the "rim" cue row for the first 8 bars after showtime.
- **Timing.** The descent takes the door time, so set it for both: about 8 s (estimate).
- **Fallback.** If WPO bounds or culling fight us, a small intro.cpp addition (the Dino session's file) moves a named
  actor along a second path at showtime. Ask only if needed.

---

## 5. Rig, lasers and the show

- **Moving heads (28):** 8 on a truss over the barn sign, and 5 on each silo catwalk ring (20). They use the Dino mover
  engine, as Reactor v7 did (memory).
- **Lasers** (the user: "we DEFINETLY need more lazers"), on the Dino laser engine. Every beam lands on a surface, with
  the near-eye fade (20-80 cm), per Reactor v8 / Graveyard v7 (memory). The units:
  - the silo domes: 4 fans, green and gold, aimed out over the corn on each side, under the ship;
  - the hayloft door: a white centre fan under the hull;
  - the ship's rim: 18 green lines down to the corn ring around the crowd.
- **Show bus:** `MPC_HmShow` at `/Game/Mods/Harvest/MaterialInstances/MPC_HmShow`. It holds:
  - the 19 parameters the hook writes (read: dumper.cpp G_PARAMS: Height ... Bass, ShowPrevBar, ShowNextBar);
  - IntroStep and DoorOpen (the intro);
  - PlayerX and PlayerY: club.cpp writes them into whatever show collection is active (read: club.cpp:249), for the
    crowd make-way.
- **One hook row needed.** **Read** in dumper.cpp ~2538: the hook finds a stage's show collection in a hard-coded
  3-row table by stage folder. Harvest Moon needs one new row in the Dino session's file:
  `{"harvest","/Game/Mods/Harvest/MaterialInstances/MPC_HmShow.MPC_HmShow","MPC_HmShow"}`. Until that APK is installed,
  the show runs free on its own 140 BPM loop and the crowd won't make way.
- **Bass.** The show bus already carries `Bass` (read: songs/<key>.bass, replayed against the song clock, 30 ms attack,
  150 ms release). The beam's core brightness and the ring speed follow it, and the crop-ring chase follows the hits.
- **Cue rows (new names):**
  - barn (trim and hayloft)
  - doors (the X-trim chase)
  - silos (lamp bands)
  - beam
  - rim (porthole chase and rim lasers)
  - floor (crop glow)
  - farm (windows, headlights)
  - towers
  - crash (the B-stage wall)
  - macro (windmill, cow)
- **Gates:** `hm_cuecheck.py` (hw_cuecheck copied: ATTACK_S = 60 ms, no instant steps) and `hm_overdraw.py` (the beam
  and the mist sheets). Beam limits: core under ~45% luma, swell over at least a beat.

---

## 6. Crowd and walking

- **Crowd v3 through a copy** (`harvest/crowd/`), the way Graveyard copied it. The Thanksgiving + visitor layer:
  - flannel, denim, dark jackets;
  - about 8% pilgrim hats, 8% plush turkey hats, 5% tinfoil hats, 5% straw hats, 5% alien masks;
  - a few inflatable-alien costumes.
- **Glow:** green, gold and warm-white glowsticks and phones.
- **Totems:** inflatable aliens (a real festival favourite), turkey legs, corn cobs.
- **Clips:** the same 17 at 140 half-time.
- **Walking:** free roam with `harvest_collide.txt` on club.cpp. It keys on the folder name (memory), so no hook change.
  - The format (read: club_collide.h) has floors, boxes/gates, circles, people and spots.
  - Floors: the formation as strips (C0, the apron, the ring path, the paths, the satellites, the tail circles, the
    crash site). The corn has no floor, so it stops you without walls.
  - Circles: the scarecrow poles and the FOH wheels.
  - People: the soft crowd's `person` lines (club.cpp limit 4608, memory).
  - The stage stairs and gate follow Graveyard v7's pattern.
- **Budget:** ~3.9k people, with the tiers and fps measured on Dino and Graveyard (71-72 fps, memory).
- **Cut if late:** crowd v3 with the glow colours swapped only.

---

## 7. Stream intro: the scout

Built on the same system as the Horseman's intro, with no new hook code (read: intro_ride.h and intro.cpp):
- the file is `tribemod/intro.harvest.txt`, holding:
  - the ride as `key` lines, a `loop`, an `exit` and `cam` offsets;
  - `rider` and `woods` actor names;
  - the `step` and `door` show names;
  - `hold`, `back`, `fov`, the button position and its radius;
- the script `harvest/intro/hm_intro_path.py` is the single source of the ride, as hw_intro_path.py is for Graveyard.

The presses:
- **The button:** a big green button on a hay-bale plinth behind the booth.
- **Press 1, the pre-show:**
  - the barn goes dark and the doors shut;
  - the moon goes back up (section 4) and Tribe's video rewinds and pauses;
  - the stream camera rides with the **scout**, a small saucer (`HmScout`, the rider) skimming the corn rows in a loop
    round the field;
  - its searchlight cone (`HmScoutBeam`, a "woods" actor) sweeps the stalks.
- **Press 2:** the scout takes the exit and dives into the back circle. That is the crash site, which is a static set
  piece all along; the rider is hidden at the exit's end. The camera holds on the wide field.
- **Press 3, showtime** (Graveyard's press-3 contract, memory):
  - the cut to the wide shot;
  - `hold` s later the cued deck plays and the video plays;
  - the doors swing open and the moon comes down over the door time;
  - the lights take the song.

The head's `intro=hold` keeps Major Tom's helmet on during all of it (memory: head.txt).

---

## 8. The character: MAJOR TOM

- **Built on skullbuck's rig the way the Horseman was.** It uses `scripts/horseman_build.py`'s tools (avatar_common.py,
  the profile + loft functions, render_skin.py, pose_test.py), with `skins/skullbuck.glb` untouched.
- **New files:**
  - `scripts/majortom_build.py`;
  - `skins/majortom.glb` + `heads/majortom.glb`;
  - the box label comes from the file name (memory: "lampwing.glb" -> "Lampwing").
- **Look** (the concept maquette, made real):
  - the suit is lofted from skullbuck's body profiles (torso, arms, legs), puffed out, with ribbed joints at the elbows
    and knees;
  - belt, chest unit with LEDs, "TOM" name tape, mission patch, hose connectors;
  - gloves: a puffed copy of skullbuck's hand mesh, weighted to the hand and finger bones, so posed fingers still work
    with controllers (memory: avatar spec);
  - boots with three talon toes and a spur.
  - The jetpack and the tail fan are rigid on Spine2:
    - 17 banded feathers (dark bronze, a black bar, buff tips) about 0.85 m long;
    - from the front they form a halo behind the helmet in the stream shot.
  - The neck ring is weighted to Neck (the Horseman lesson: a Head-weighted collar collapses when Head is hidden).
  - The helmet ring, the glass bubble and the turkey head are 100% Head, with DH_C / DH_F / DH_U under Head:
    - blue face, short hooked beak, snood, big red wattle, red caruncles, a dark feather ruff at the neck.
- **The trick runs on the existing flying-head code, unchanged (memory).**
  - `heads/majortom.glb` is the helmet + head as one static mesh: origin at the centre, upright, facing front.
  - The head leaves at the suit's metal ring, so there is no stump to hide.
  - It flies the ORBIT ring: r 90 cm round the hips, about 10 cm above head height, 8 s per lap.
  - `head.txt` keeps its knobs (`every=600`, `boomax=12`, `intro=hold`).
- **Check:** the orbit passes just outside the feather tips (read: the concept geometry). Shorten the fan by ~10 cm if the
  helmet grazes it in pose_test.
- **Unverified on device, tested first:**
  - **The glass bubble.** It would be the first see-through material on a skin. It is **assumed** to reach glTFRuntime's
    Translucent instance through alphaMode BLEND (memory: those instances are in the pak). Test it first with a throwaway
    skin carrying one glass sphere, pushed on the user's OK. Fallback: an open visor (no glass).
  - **Emissive LEDs.** The Horseman's glow was never confirmed by eye (memory). Fallback: bright unlit-looking colours.
- **Device tests** need the user's OK for every push. The skin and the head go on the re-seed backup list (section 10).
  Tell the character session (head.cpp's owner) before the first push.

---

## 9. Visuals: the HARVEST MOON loop pack and the hour set

140 BPM half-time, 411 frames per 8-bar loop, the vjkit gates (check_loop.py; memory: Dino VJ loops). Key art inside
the screen's window, black backgrounds, no strobes.

| # | loop | slot | picture | beat hook |
|---|---|---|---|---|
| 1 | Moonrise | intro | a huge gold moon clears a black corn horizon; tassels sway | sway per bar |
| 2 | Crop Circle | build | top-down: a pattern draws itself in glowing lines, ring by ring | a ring per bar, ticks on 1 and 3 |
| 3 | Corn Maze Run | build into drop | a low fly-through of a neon corn maze (the Spine Tunnel method), turns on the snare | turn on 3 |
| 4 | Tractor Beam | drop | looking up into the saucer's underside, light rings rush down at the camera | ring on 1 |
| 5 | Abduction | drop | turkeys (and the cow) spin up a beam into the dark | lift on 1 and 3 |
| 6 | Barn Doors | heavy drop | the X doors bang open on the downbeat and light floods out | doors on 1 |
| 7 | Kernel Panic | heavy drop | popcorn kernels burst on the snare, glowing gold | pop on 3 |
| 8 | Signal | breakdown | scarecrow silhouettes under a pulsing alien waveform | pulse per bar |
| + | HARVEST MOON sting | ID | letters drawn in crop-circle lines on the downbeat | identity |

Delivery: `/sdcard/Movies/Harvest Moon Visuals/` plus a 60-minute set video (Reactor's assemble_set.py method), pushed
only on the user's yes.

---

## 10. Pipeline and files (nothing shared is edited)

```
C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\harvest\
  concept_blockout.py, major_tom_concept.py, run_concept.sh, sheet.py     the concept (done)
  hm_stage.py           the generator: hw_stage.py copied and adapted (orchestration, drop, bake, export, manifest)
  hm_kit.py             extends kit's palette in-process (gold / amber / barn red / visitor green) + helpers (gambrel,
                        crop formation, corn strips, bale, scarecrow)
  hm_show.py            the cue table at 140 BPM
  modules\              hm_field.py hm_farm.py hm_towers.py hm_foh.py hm_crash.py hm_atmosphere.py + preview harness
  crowd\                the crowd v3 copy with the Thanksgiving layer
  intro\                hm_intro_path.py (single source of the intro), hm_collide.py (harvest_collide.txt), hm_abductees.py (VAT)
  checks                hm_cuecheck.py hm_overdraw.py hm_dronecheck.py (copies of the hw_ gates)
  ship_hm.sh            bake -> cuecheck -> overdraw -> dronecheck -> UE build/cook/pack -> shader-archive check ->
                        push_obb.sh (stops at the first failed gate; HM_ANIM=1 for the animated build)
C:\Users\Chris\TribeUE\TribeXR\Scripts\build_harvest.py    UE import: /Game/Mods/Harvest, chunk 57, ship bounds extension
D:\TribeUE\MetaHarvest\TribeXR                              fork-project copy (C: has 26 GB free, read today)
C:\Users\Chris\TribeUE\Visuals\harvest\                     the loop pack
tribe hack\scripts\majortom_build.py                        the skin (+ skins/majortom.glb, heads/majortom.glb)
tribe hack\claudedocs\harvest_moon_notes.md                 the running log
```

Lessons carried over (memory):
- **UV V flip:** Unreal flips V on every UV channel, so VAT and laser data UVs need the pre-compensation. Preview the
  SHIPPED asset path, not the Blender rig.
- **Cooks from bash** need MSYS_NO_PATHCONV=1.
- **cook_halloween.sh alone builds STOCK.** The animated build needs the ANIM flag, so ship through the ship script.
- **Materials compile only in the cook,** so grep the cook log for "Failed to compile".
- **`bake()` refuses an all-black bake** (Graveyard v6's black crowd).
- **GPU lock:** mkdir gpu.lock.d with owner.txt, released on exit.
- **push_obb.sh names each OBB entry after the file's basename.** Rollback paks keep their real names in per-version
  folders.
- **Thin trim inside a thicker panel never renders.** The concept's door X-trim showed only after it moved 0.25 m off
  both faces.

**Per-stage files on the headset** (all found by the stage's folder name):

| file | read where | Harvest Moon name |
|---|---|---|
| walking map | club.cpp (keys on the folder) | `tribemod/harvest_collide.txt` |
| drone reel | dumper.cpp (per-folder reel, memory: song13) | `tribemod/drone_path.harvest.txt` |
| stream intro | intro.cpp (`intro.<folder>.txt`, read) | `tribemod/intro.harvest.txt` |
| env menu box | envs.txt | `Harvest Moon=/Game/Mods/Harvest/Maps/Environment_Harvest` |
| screen | dumper.cpp (`em_find_mesh_actor("SM_DinoVisualScreen")`, memory) | our screen mesh asset is named SM_DinoVisualScreen in our package |
| the skin | the avatar menu (one box per skins/*.glb, max 8, memory) | `skins/majortom.glb`, `heads/majortom.glb` |

**Re-seed rule (memory):** every new tribemod file also goes into `backup/tribemod_20261006/`, and its name goes to the
Dino session for reseed.sh's list. Otherwise a re-seed silently drops it.

---

## 11. Other sessions: what we need from each, what we never touch

| session | what Harvest Moon needs | rule |
|---|---|---|
| Dino (owns dumper.cpp, reseed.sh, re-seeds, most APKs) | (a) the `"harvest"` SHOWS row; (b) EM_MAX raised from 4 (read: dumper.cpp:2166; Midtown asked for 8 today, Big Dub needs it too); (c) our tribemod names on the re-seed list | ask through the user/messages; never edit its files |
| Reactor (owns club.cpp) | nothing: walking and the make-way work by folder name and show_key | combo4 is pending; build from club.cpp 748faaac |
| Character (owns head.cpp) | nothing: the head works unchanged | tell it about skins/majortom.glb before any push |
| Halloween | its scripts are the templates: copy, never edit; it shares the GPU lock; first claim on the headset until Oct 31 | copies only |
| Midtown (58), Big Dub (56), the hangar pitch (59) | nothing | chunk 57 is ours |

---

## 12. Phases (parallel with the other sessions; dates are targets)

| phase | dates | work | gate |
|---|---|---|---|
| 0 Scaffold | Oct 17-23 | MetaHarvest copy on D: + first cook (37 min shader compile on the first cook, memory); hm_stage.py blockout from the concept geometry (barn, doors, silos, screen, deck, crop floor, near corn strips, ship parked, sky); MIC-only; chunk 57; a box (decision 2); push on the user's OK | loads <= 2 s, the screen plays a media video, 71+ fps, the other stages still load from the same OBB |
| 1 The set | Oct 22-Nov 2 | barn detail + trim, doors on DoorOpen, silos + rig + lasers, the ship (hull, rim, lights) + the descent WPO and bounds, beam, crop glow, farm; first full bake; stock then animated | previews approved in chat; laser clearance; the descent seen on device with nothing culled |
| 2 Field, crowd, walking | Oct 27-Nov 9 | corn near/far, scarecrow towers, FOH, crash site, crowd layer, totems, harvest_collide.txt | overdraw budget; crowd fps >= 71 on device; a walk test round the formation |
| 3 Animated show | Nov 2-14 | MPC_HmShow + hm_show cue table, beam swell on Bass, ring chases, abductee VAT, windmill, cow, mist; fork cook; hm_cuecheck | cuecheck passes; the user's comfort verdict on the beam in the headset |
| 4 Major Tom | Oct 18-Nov 12 (parallel) | the glass test skin first; then majortom_build.py, skins/ + heads/majortom.glb, check_skin.py, pose_test (orbit vs fan) | LOADS + MOVES; the helmet flies a full cycle on device; the user's look verdict |
| 5 Intro | Nov 6-16 | hm_intro_path.py, intro.harvest.txt, HmScout + beam actors, the button | presses 1-3 on device; the moon goes up and comes down on cue |
| 6 Media | Nov 1-21 (GPU queue) | 8 loops + sting, hour set, drone reel | check_loop.py on every loop; the reel plays through clean (hm_dronecheck) |
| 7 Polish + freeze | Nov 18-24 | the user's notes; APK freeze Nov 20 (the SHOWS row and EM_MAX must be in by then); content freeze Nov 24 | dress rehearsal |
| Stream | Nov 26 | Graveyard's stream-day checklist (re-seed, media, reel, lights, comfort check) | |

---

## 13. Decisions for the user (the plan proceeds on the recommendation if unanswered)

1. **Stream date.** Assumed Thanksgiving night, Thu Nov 26. Fri 27 or Sat 28 moves the freeze by 1-2 days.
2. **Menu box.** Recommended: EM_MAX to 8 in the Dino session's next APK (Midtown has asked for the same). For early
   headset tests, swap a box out of envs.txt; your pick of which.
3. **The descent.** Recommended: it rides the intro's door ramp (section 4; no hook change, about 8 s). Otherwise a small
   hook addition for a longer, separate descent.
4. **CRASH SITE second stage.** Recommended: include it. It is also where the intro's scout crashes. Or cut it to save
   budget.
5. **Major Tom's helmet.** Recommended: try the glass bubble first, with an open visor as the fallback.
6. **Tail feathers.** Recommended: natural bronze. Or LED-tipped feathers (rides on the unverified avatar glow).
7. **Weather.** Recommended: a clear frosty night (stars, low mist); no snow or lightning.

---

## 14. Risks, ranked (probability x cost x silence)

1. **The descent by WPO.** Rest-bounds culling, or the rim lasers firing from the empty spot. Silent in previews, loud
   on device. Mitigation: bounds extension at import, a device check in phase 1, the rim row held for 8 bars,
   the hook fallback.
2. **Cross-session hook dependencies** (the SHOWS row, EM_MAX) sit in another session's file. This is silent: the show
   runs free and nobody notices. Mitigation: ask in phase 0, and check the `[GIANT]` show-bus line on the first device
   visit.
3. **Corn triangles and draw calls.** The concept's 30k box corn is ~370k tris on its own (estimate), far over budget.
   Mitigation: strips near and a textured field far, a per-mesh tris log, the fps gate.
4. **The beam's brightness and overdraw.** A big translucent cone over the crowd. Mitigation: hm_overdraw, luma cap,
   swell ramps, the user's verdict.
5. **Avatar glass and emissive unverified.** Mitigation: the throwaway glass test first; fallbacks.
6. **Time:** Halloween, Midtown, Big Dub, Reactor and this, on one PC, one headset and one tester. Mitigation: phases end
   shippable, cut-if-late lines, device tests batched.
7. **Meta token on stream day.** Mitigation: the re-seed procedure; no APK install after the final re-seed.

---

## Appendix A. Drone reel draft (drone_path.harvest.txt; world cm, DJ at the origin, crowd -Y)

```
# moonrise reveal from behind the crowd, rising
fly 12 0,-9000,600 0,-6000,1800 look=0,1000,2400
# under the ship, through the beam's edge
fly 12 -2500,-5200,300 2500,-2400,300 look=0,-3800,3000
# crane at the circle's edge: the pattern and the ship
fly 14 3200,-6800,300 4500,-8500,6000 look=0,-3800,0
# a scarecrow tower close by
fly 10 -3500,-5000,900 -2800,-5600,900 look=-3045,-5220,800
# silo climb to the laser fans
fly 12 -2300,1200,300 -2300,1400,3600 look=-2900,2000,3400
# over the crowd toward you
fly 12 0,-2400,700 0,-700,330 look=dj
# close orbit (the helmet's orbit is inside this)
orbit 14 r=260 h=30 deg=360 start=-90
# over your shoulder: the ship ahead
fly 8 -250,380,260 250,380,260 look=0,-3800,2000
# farmhouse porch to the stage
fly 12 5000,-1200,250 2500,-600,400 look=0,500,800
# the crash site
fly 10 1200,-9800,300 300,-10300,250 look=0,-11100,0
```
About 116 s. hm_dronecheck (sight lines, no clipping, the ship's volume as a keep-out) checks the real reel before it ships.

## Appendix B. Budgets (Graveyard's, memory)

| budget | target | check |
|---|---|---|
| fps | >= 71 average at 72 Hz | logcat fps windows |
| tris | <= 600k total: crowd ~330k, set ~90k, field + farm ~180k (corn <= 60k) | generator per-mesh log |
| actors | <= 40 | build_harvest.py log |
| translucent overdraw from the DJ | <= 2.5 layers/px (beam + mist + head beams) | hm_overdraw.py |
| chunk size | <= 130 MB | pack output |
| load | <= 2 s | `[ENV]` log |
| flashes | <= 3/s, no 1-frame hits; beam core <= ~45% luma | hm_cuecheck.py, check_loop.py |
