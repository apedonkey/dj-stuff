# Christmas stage plan: MIDTOWN, with the Animatronic Santa

Written 2026-10-16, after the user approved the concept renders ("looks good to me").

Ground rules:
- Nothing here is built for the game yet.
- **The work runs now, in parallel** with the Halloween, Reactor, Dino and other sessions. The user, 2026-10-16: "its not
  being held until the 31st".
- Labels used below:
  - **read** = checked in a file or the code today;
  - **memory** = from the project memory, true when it was written;
  - **estimate** = my number, to be measured;
  - **assumed** = not verified, with the check named.

Concept renders: `claudedocs/christmas_concept/` (9 views + `xm_concept_sheet.jpg`) from
`C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\christmas\concept_blockout.py`. Run it with `run_concept.sh`, which takes
the shared GPU lock, takes 16 s and writes `concept/`; `sheet.py` makes the contact sheet. They show layout, scale, palette
and density, not the final look.

---

## 0. Assumptions

| assumption | basis | if wrong |
|---|---|---|
| The Christmas stream is Sat 2026-12-19 or Thu 2026-12-24 (Christmas Eve) | not stated; both dates read from the calendar | phases keep their order; the freeze dates move |
| "As big as Graveyard": set + rig + lasers, street modules, a ~4k VAT crowd, the 23 m screen, a cue-table show, a VJ loop pack, a drone reel, an intro | the Graveyard plan's inventory (memory + halloween_stage_plan.md) | each section has a "cut if late" line |
| 140 BPM half-time for the show, the crowd and the loops | the user plays heavy dubstep, 128-150 BPM (memory) | one constant |
| It ships like the others: one pak in the shared patch OBB, a box in tribemod/envs.txt, the mod's loader | Dino, Graveyard, Reactor (memory) | none |
| Content folder `/Game/Mods/Christmas`, display name **Midtown**, pak **chunk 58** | 50/53/54/55 are live, 56 is Big Dub's, the Thanksgiving pitch assumed 57 (memory) | renaming the folder renames every per-stage file in section 10 |

---

## 1. Concept and art direction

**One line.** The city at 3 a.m. on Christmas Eve:
- the crowd fills a closed-off avenue between skyscrapers;
- the stage sits in a plaza at the head of the avenue, with the visuals on a giant LED billboard;
- a 60 m Christmas tree rises behind the billboard, in front of an Art Deco tower;
- rooftop lasers cross the canyon and an elevated train rattles across the far end;
- the department store's window Santa has walked out of his display to play the set.

**Palette.**
- Christmas red (1.0, 0.06, 0.04), cold white (0.80, 0.86, 1.0) and gold (1.0, 0.60, 0.16) carry the look.
- Green (0.12, 1.0, 0.32) is an accent (lasers, signals).
- Sodium orange (1.0, 0.52, 0.18) is the street-lamp color.
- Not used: Graveyard's orange/purple and Dino's cyan/magenta, so Midtown never looks like either.

**Darkness** (the user's standing rule: dark except the DJ, the visuals, the lasers and the lights):
- About 8% of windows are lit, at strength 1.5 in the blockout.
- The canyon walls are near black between hits.
- The tree, the billboards, the show and the street lamps carry the light.

**Comfort.** The same rules hw_cuecheck.py and check_loop.py enforce: no strobes, at most 3 flashes/s, no one-frame
hits (every cue ramps over >= 60 ms), no full-frame white, fills swell into the downbeat.
- The power-cut drop (below) is the new hazard. It is a dip and a ramp back, never a cut to black and a slam to full.

**Mood by set section**

| section | stage | city | crowd |
|---|---|---|---|
| intro | tree dark, billboard on, star dim | most windows dark, snow, steam | sway |
| build | tree chases upward tier by tier, gantry signals blink, searchlights wake | windows flicker on along the canyon | pump, hands up |
| blackout bar ("power cut") | only the star and the billboard | street lamps dip to 20% over 2 beats | hold |
| drop | everything: the star fan, rooftop fans, heads, candy-stripe bars | lamps back over 2 beats, searchlights sweep | jump, headbang |
| breakdown | tree warm-white only, billboard | the el train crosses, snow thickens | sway |
| outro | fans alternate, searchlights out | windows go dark one by one | shuffle |

**Slow layer.** A ~16-minute macro cycle runs on Time, like Graveyard's:
- the el train crosses every ~4 minutes;
- the tower's crown bands climb;
- once per cycle the city's windows all switch on for 2 bars ("the whole city wakes up"), as a swell, not a flash.

---

## 2. Layout and fixed constraints

**Frame.** The same frame as Graveyard (memory: grounds/kit.py docstring):
- meters, Z up;
- the DJ at the origin on Tribe's floor, facing -Y;
- the deck top at -1, the street (crowd floor) at -1.5;
- the stage behind the DJ (+Y).

FBX export mirrors Y; the UE import undoes it.

**Fixed by Tribe** (memory, Graveyard plan section 3; world cm):
- DJ rig at (-5, 31, 78): booth top at 74 cm, x -95..85, y -5..50.
- SpectatorBoundingBox: x -250..250, y -221..279, z -6..494. Keep it clear.
- BP_MiniMenu box: x -73..65, z 89..191.
- Every StaticMeshActor gets NoCollision via set_collision_profile_name, or the menu ray dies.
- Screen UVs: copy `visual_screen_uv` exactly.

**Top-down (meters; blockout values, read from concept_blockout.py):**

```
 y=+66..112   ART DECO TOWER 54x46 base, setbacks to 195 m, crown light bands to 214, spire 255, red beacon
 y=+27        THE TREE: 60 m, base r 14, star at z 59.5 (behind the billboard, never in front of it)
 y=+10.3      BILLBOARD = VISUALS SCREEN 23 x 12.94 (SM_DinoVisualScreen), truss frame, marquee bulbs
 y=-4.5..13.5 stage deck x +-25; DJ riser + booth at the origin; gift stacks on the deck corners
 y=-7.5       blue police barricades across the avenue (and across the cross streets at x +-31)
 PLAZA        |x| < 45, y -8 .. 60 (snowy stone); flanking buildings x +-45..70
 AVENUE       building fronts at x = +-30, sidewalks 26..30; CROWD |x| < 26, y -8.6 .. -90 (~3.1k in the blockout)
 y=-8..-36    block A: left = hotel 58 m with the vertical NOEL neon sign; right = DEPARTMENT STORE 34 m, display
              windows y -11..-31, the BROKEN one at y -19 (glass + boot prints to the stage)
 y=-36..-52   cross street 1: FOH riser, gantry 1 at y -44 (signals, delay speakers, MIDTOWN signs both faces)
 y=-52..-84   block B: billboards on both fronts; gantry 2 at y -72
 y=-84..-100  cross street 2; THE EL at y -92 (deck z 6.7..7.9), train cars z 8.1..11.7
 beyond       the avenue runs on to y -500 between blocks 25-140 m tall; a city grid to x +-430
 rooftops     laser units on the avenue-front roofs (4 in the blockout), searchlights on the tower and the flanks
```

**The tree goes behind the billboard.** In front of it, the tree would cover the visuals. Its base front edge sits at
y 12.8, behind the screen at 10.3.

---

## 3. The set, piece by piece

All of it comes from `xm_stage.py`, the Graveyard generator (hw_stage.py) copied and adapted, never edited in place. It
is baked with Cycles, exported one FBX per surface, and imported as MICs (stock build) or fork-cooked materials (animated
build). Tris are estimates.

| piece | content | tris | cut if late |
|---|---|---|---|
| Billboard (SM_DinoVisualScreen + SM_XmBillboard) | the 23 x 12.94 quad with Tribe's UV0; a black LED cabinet; a truss frame; 70 marquee bulbs (chase row) | 6k | marquee chase |
| The tree (SM_XmTree, SM_XmTreeLights, SM_XmStar) | 9 tiers (needle bake, dark); ~2.3k bulbs as glow cells in 5 colors on a palette texture; ~150 glass ornaments; the star + halo card; laser fan origin | 40k | ornaments |
| Tower (SM_XmTower) | setback boxes with a baked window atlas; crown bands (glow, crown row); spire; beacon | 4k | none |
| Canyon (SM_XmCity, SM_XmCityGlow) | avenue-front blocks with cornices, setbacks, water towers; a window ATLAS bake (lit cells as glow, not a per-pixel shader: the blockout's shader is world-space math we don't ship); cornice bulb lines; far city as 60-tri boxes with an emissive window texture | 60k | far city as one textured shell |
| Department store (SM_XmStore) | stone facade, columns, mansard; 6 display windows (5 lit dioramas with silhouette cutouts: elves, a train, a rocking horse); the broken window (dark, jagged glass cards, shards); boot prints decal; the wreath | 12k | dioramas as flat cards |
| Hotel + NOEL sign | vertical red neon blade sign, 4 letters + edge chase bulbs | 3k | none |
| Billboards (SM_XmSideScreens) | 6 side billboards (2 face the crowd over cross street 1); static Christmas art in the stock build; mirror Tribe's visuals if decision 3 is yes | 2k | 2 of 6 |
| DJ area | riser, booth front as a black LED counter with a candy-stripe edge (chase); deck lamps HwDeckLamp-style (XmDeckLamp_L/R); gift stacks; nothing within 60 cm of the table edge | 8k | gifts |
| Street (module xm_street) | lamps with wreaths (point lights baked + a glow head), steam stacks + steam cards, parked cabs, subway entrance with green globes, barricades, festoon strings across the avenue (7), plowed snow | 30k | cabs, subway |
| Gantries (module xm_gantry) | 2 trusses over the avenue: hanging signals (blink row), delay speakers, candy-stripe LED bar (chase), MIDTOWN LED signs (both faces), 4 heads each | 15k | the second gantry |
| The el (module xm_el) | steel deck and columns outside the avenue; a 9-car train with lit windows; the crossing is a rigid cue motion (translate X) on the macro layer | 12k | a parked train |
| Sky (SM_XmSky) | sphere r 480 (Dino's); near-black navy with a low cloud deck lit faintly warm from the city; no moon (the tower beacon and the searchlights own the sky) | 1k | none |
| Snow | 2-3 large camera-facing snow sheets (scrolling dots) in the canyon, overdraw-gated; NOT thousands of flakes | quads | snow off |

---

## 4. Rig, lasers and the show

- **Moving heads (22):** 8 on the billboard header truss, 6 on the front truss over the DJ (z 12.5, above Tribe's cameras),
  8 on the gantries. They use the Dino mover engine, as Reactor v7 did (memory).
- **Lasers** (the user: "we DEFINETLY need more lazers"), on the Dino laser engine (dino_materials.laser_show, imported,
  never edited):
  - 4 rooftop units: red, white, green, red. Each fans across the canyon and lands on the far side of the street.
  - The star: a gold fan down the avenue.
  - The billboard top bar: a green fan to the back of the crowd.
  - Every beam lands on a surface, with the near-eye fade (20-80 cm), per Reactor v8 / Graveyard v7 (memory).
- **Searchlights (4):** 2 on the tower's first setback, 2 on the plaza flanks, sweeping the cloud deck.
- **Show bus:** `MPC_XmShow` at `/Game/Mods/Christmas/MaterialInstances/MPC_XmShow`, holding the 17 show-bus names plus
  ShowPrevBar / ShowNextBar. This is the same contract as MPC_HwShow and MPC_ClubShow (memory).
  - **Read in dumper.cpp:2538-2546:** the hook finds a stage's show collection in a hard-coded 3-row table by stage folder
    (club, halloween, and a third row). So Midtown needs **one new row** (`"christmas"`) in the Dino session's file. Until
    that APK is installed, the show runs free on its own 140 BPM loop, as Graveyard did before its row.
- **Cue rows (new names):**
  - tree (tier chase)
  - star
  - windows (the city's lit cells)
  - lamps (the power-cut dip)
  - marquee
  - signals
  - candy (the gantry bars)
  - crown
  - train (macro)
- **Gates:** `xm_cuecheck.py` (hw_cuecheck copied: ATTACK_S = 60 ms, no instant steps) and `xm_overdraw.py` (snow and
  steam sheets).

---

## 5. Crowd

- Crowd v3 through a copy (`christmas/crowd/`), the way Graveyard copied it. The Christmas layer:
  - winter coats in dark colors;
  - about 20% Santa hats, plus beanies, elf hats, antler headbands and ugly-sweater torsos;
  - a few inflatable-costume Santas.
- Glow: red, green, white and gold glowsticks and phones.
- The same 17 clips at 140 half-time.
- **Walking:** free roam through the soft crowd, using club.cpp's `person` lines (limit 4608, memory) in
  `christmas_collide.txt`.
- Budget: ~4.2k people, the tiers and fps measured on Dino and Graveyard (71-72 fps).
- Cut if late: crowd v3 with Christmas glow colors only.

---

## 6. Stream intro: the tree lighting

Built on the same system as the Horseman's intro:
- the file is `tribemod/intro.<folder>.txt`, here `intro.christmas.txt` (read: intro.cpp:97);
- the actors are found by name under `/Mods/<folder>/`;
- MPC IntroStep 0..3.

The presses:
- **Before press 1:** the city is quiet. The tree is dark, and the camera sits on the department store's broken window.
- **Press 1:** the camera follows the boot prints along the sidewalk to the stage. The el train crosses overhead (the
  "rider" in the intro's ride format).
- **Press 2:** a countdown on the gantry signs and the windows, 10 to 1 across 4 bars.
- **Press 3:** the tree lights from the bottom up, the star fan fires, and the cued deck plays (Graveyard's press-3
  contract).

The exact actor and step mapping waits for phase 4, against intro.cpp's format. That is the Dino session's code: we
write the file, they own the reader.

---

## 7. The character: the Animatronic Santa

- **Built on skullbuck's rig the way the Horseman was:** `scripts/horseman_build.py`'s tools (avatar_common.py,
  render_skin.py, pose_test.py), with `skins/skullbuck.glb` untouched.
- **New files:** `scripts/santa_build.py`, `skins/santa.glb` + `heads/santa.glb`.
- **Look:**
  - red velvet coat, torn at the side to show metal ribs;
  - white fur trim, black belt with a gold buckle, black boots;
  - bare metal forearms with pistons and elbow servos, black gloves;
  - head: a slightly-too-pink face, white beard, frozen slot grin, one black button eye, one red camera-lens eye, hat.
- **The trick runs on the existing flying-head code, unchanged (memory):**
  - DH_C / DH_F / DH_U bones under Head;
  - `heads/santa.glb` (origin at the centre, facing front);
  - `head.txt` keeps its knobs (`every=600`, `boomax=12`, `intro=hold`).
- **Neck stump:** the coil spring, cut wires and neck post are Neck-weighted (a Head-weighted collar collapses when Head
  is hidden: the Horseman lesson). They show only while the head is off, and the spring does not stretch with the flight.
- **Unverified:** emissive glow on a skin (the lens eye) is still unchecked on device (the Horseman's glow was never
  confirmed by eye). Fallback: a bright red unlit-looking material.
- **Device tests** need the user's OK for every push, and the skin goes into the re-seed backup list (section 10).

---

## 8. Visuals: the MIDTOWN loop pack and the hour set

140 BPM half-time, 411 frames per 8-bar loop, the vjkit gates (check_loop.py; memory: Dino VJ loops).

| # | loop | slot | picture | beat hook |
|---|---|---|---|---|
| 1 | Tree Lighting | intro | a dark tree lights tier by tier into a star burst (swell, not flash) | tier per beat |
| 2 | Skyline Wake | build | a night skyline whose windows switch on in runs | runs on 1 and 3 |
| 3 | Subway Rush | build into drop | a fly-through of a tiled tunnel, signal lights pass per beat (the Spine Tunnel method) | light per beat |
| 4 | Candy Cane Tunnel | drop | a red/white spiral tunnel whose twist jolts on the kick | jolt on 1 |
| 5 | Gift Wrap | drop | ribbons tear open on the snare, revealing a darker pattern | tear on 3 |
| 6 | Workshop Glitch | heavy drop | the animatronic Santa's head in a store window, twitching, his lens eye pulsing | twitch on 1 and 3 |
| 7 | Neon Reindeer | build | wireframe reindeer galloping across a rooftop line at half-time | stride per bar |
| 8 | Snowstorm | breakdown | snow whirls through a street lamp's cone | swirl per bar |
| + | MIDTOWN sting | ID | the gantry sign's dot letters light on the downbeat | identity |

Delivery: `/sdcard/Movies/Midtown Visuals/` plus a 60-minute set video (Reactor's assemble_set.py method), pushed only on
the user's yes.

---

## 9. Pipeline and files (nothing shared is edited)

```
C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\christmas\
  concept_blockout.py, run_concept.sh, sheet.py     the concept (done)
  xm_stage.py           the generator: hw_stage.py copied and adapted (orchestration, drop, bake, export, manifest)
  xm_kit.py             extends kit's palette in-process (red / cold white / gold keys) + helpers (window atlas,
                        led_text, string lights, setback building)
  xm_show.py            the cue table at 140 BPM
  modules\              xm_street.py xm_gantry.py xm_el.py xm_store.py xm_city.py xm_atmosphere.py + preview harness
  crowd\                the crowd v3 copy with the Christmas layer
  intro\                xm_intro_path.py (single source of the intro), xm_collide.py (christmas_collide.txt)
  checks                xm_cuecheck.py xm_overdraw.py xm_dronecheck.py (copies of the hw_ gates)
  ship_xm.sh            bake -> cuecheck -> overdraw -> dronecheck -> UE build/cook/pack -> shader-archive check ->
                        push_obb.sh (stops at the first failed gate; XM_ANIM=1 for the animated build)
C:\Users\Chris\TribeUE\TribeXR\Scripts\build_christmas.py    UE import: /Game/Mods/Christmas, chunk 58
D:\TribeUE\MetaXmas\TribeXR                                  fork-project copy (C: is 98% full: 26 GB free, read today)
C:\Users\Chris\TribeUE\Visuals\christmas\                    the loop pack
tribe hack\claudedocs\christmas_stage_notes.md               the running log
```

Lessons carried over (memory):
- **UV V flip:** Unreal flips V on every UV channel, so VAT and laser data UVs need the pre-compensation. Preview the
  SHIPPED asset path, not the Blender rig.
- **Cooks from bash** need MSYS_NO_PATHCONV=1.
- **Materials compile only in the cook,** so grep the cook log for "Failed to compile".
- **`bake()` refuses an all-black bake** (Graveyard v6's black crowd).
- **GPU lock:** mkdir gpu.lock.d with owner.txt, released on exit.
- **push_obb.sh names each OBB entry after the file's basename.** Rollback paks keep their real names in per-version
  folders.

---

## 10. Per-stage files on the headset (read in the hook today: all are found by the stage's folder name)

| file | read where | Midtown name |
|---|---|---|
| walking map | club.cpp:12-13, 120 | `tribemod/christmas_collide.txt` |
| drone reel | dumper.cpp:1945-1948 | `tribemod/drone_path.christmas.txt` |
| stream intro | intro.cpp:97 | `tribemod/intro.christmas.txt` |
| env menu box | envs.txt | `Midtown=/Game/Mods/Christmas/Maps/Environment_Christmas` |
| screen | dumper.cpp:2322 (`em_find_mesh_actor("SM_DinoVisualScreen")`) | the screen mesh asset is named SM_DinoVisualScreen in our package |

**Re-seed rule (memory):** every new tribemod file also goes into `backup/tribemod_20261006/`, and its name goes to the
Dino session for reseed.sh's list. Otherwise a re-seed silently drops it.

---

## 11. Other sessions: what we need from each, what we never touch

| session | what Midtown needs | rule |
|---|---|---|
| Dino (owns dumper.cpp, reseed.sh, re-seeds, most APKs) | (a) a `"christmas"` row in the SHOWS table (dumper.cpp:2538); (b) EM_MAX raised from 4 (dumper.cpp:2166; Big Dub needs it too); (c) new tribemod names on the re-seed list | ask through the user/messages; never edit its files |
| Reactor (owns club.cpp) | optional: side billboards mirror Tribe's visuals: `club_side_screens()` runs on the club's map only (club.cpp:291) | ask; combo4 (its build) is pending, build from club.cpp 748faaac |
| Character (owns head.cpp) | nothing: the head works unchanged | tell it about skins/santa.glb before any push |
| Halloween | its scripts are the templates: copy, never edit; shares the GPU lock | copies only |
| Thanksgiving pitch / Big Dub | chunk 57 / 56 stay theirs | Midtown is chunk 58 |

Every headset push and APK install waits for the user's OK, given in this chat.

---

## 12. Phases (parallel with the other sessions; dates are targets)

| phase | dates | work | gate |
|---|---|---|---|
| 0 Scaffold | Oct 17-21 | MetaXmas copy + first cook (37 min shader compile on the first cook, memory); xm_stage.py blockout from the concept geometry (canyon boxes, tree tiers, tower, billboard, deck, street, sky); MIC-only; chunk 58; push on the user's OK | loads <= 2 s, the screen plays a media video, 71+ fps, the other stages still load from the same OBB |
| 1 The set | Oct 21-31 | window atlas, tree + star, tower, store, DJ area, rig + lasers; first full bake; stock build | previews approved in chat; laser clearance; headset pass |
| 2 Street, crowd, walking | Oct 27-Nov 7 | modules (street, gantries, el, city), crowd layer, christmas_collide.txt | overdraw budget; crowd fps >= 71 on device; walk test |
| 3 Animated build | Nov 3-14 | MPC_XmShow + cue table, chases, power-cut dip, el train motion, tree lighting, snow sheets; fork cook | cuecheck passes; the user's comfort verdict in the headset |
| 4 Character + intro | Oct 20-Nov 21 (parallel) | santa_build.py, heads/santa.glb; intro.christmas.txt | the head flies with the new skin on device; intro presses 1-3 |
| 5 Media | Nov 10-Dec 5 (GPU queue) | 8 loops + sting, hour set, drone reel | check_loop.py on every loop; the reel plays through clean |
| 6 Polish + freeze | Dec 5-17 | the user's notes; APK freeze Dec 12; content freeze Dec 17 | dress rehearsal |
| Stream | Dec 19 (or 24) | Graveyard's stream-day checklist (re-seed, media, reel, lights, comfort check) | |

---

## 13. Decisions for the user (the plan proceeds on the recommendation if unanswered)

1. **Stream date.** Assumed Sat Dec 19; Christmas Eve (Thu Dec 24) moves the freeze by 5 days.
2. **Menu box.** Recommended: raise EM_MAX to 8 in the Dino session's next APK. Big Dub needs it too, and the menu is
   full today with 4 boxes. For early headset tests, swap a box (e.g. Dino Classic) out of envs.txt.
3. **Side billboards show your visuals.** Recommended yes: a small extension of the Reactor session's side-screen code.
   Otherwise they show static Christmas art.
4. **Second stage.** Recommended: none for v1 (a subway-platform B-stage could come later).
5. **Power-cut drop.** On, as a 2-beat dip and ramp (recommended), or off.
6. **Snow.** Recommended: 2-3 snow sheets, overdraw-gated; or no snow.
7. **Booth front.** Recommended: a black LED counter with a candy-stripe edge; or a street vendor's chestnut cart.

---

## 14. Risks, ranked (probability x cost x silence)

1. **Cross-session hook dependencies** (the SHOWS row, EM_MAX) sit in another session's file. This is silent: the show
   runs free and nobody notices. Mitigation: ask early (phase 0), and check the `[GIANT] show bus` log line on the first
   device visit.
2. **The window glow budget.** Thousands of lit cells could cost overdraw or texture memory. Mitigation: bake them into
   a window atlas per facade, measured in phase 1.
3. **Translucent overdraw** from snow, steam and beams. It shows on device (fps), not in previews. Mitigation:
   xm_overdraw gate, sheets not particles.
4. **Comfort:** the power-cut dip, chases and the blinking signals. Mitigation: 60 ms ramps, cuecheck, the user's
   verdict.
5. **Time:** two holiday stages and Big Dub in parallel on one PC, one headset and one tester. Mitigation: phases end
   shippable, cut-if-late lines, device tests batched.
6. **Avatar emissive unverified.** Mitigation: the fallback material.
7. **Meta token on stream day.** Mitigation: the re-seed procedure; no APK install after the final re-seed.

---

## Appendix A. Drone reel draft (drone_path.christmas.txt; world cm, DJ at the origin, crowd -Y)

```
# canyon fly-in from over the el train, the tree ahead
fly 14 0,-11000,1800 0,-4000,1200 look=0,2700,3000
# under the gantry signs at head height
fly 10 -1500,-6000,400 -800,-3000,350 look=0,0,600
# the store window and the boot prints
fly 10 2500,-2600,200 2500,-1200,220 look=2900,-1900,150
# crane up the tree to the star
fly 12 1800,1200,300 900,2000,5600 look=0,2700,5900
# over the crowd toward you
fly 12 0,-2400,700 0,-700,330 look=dj
# close orbit
orbit 14 r=260 h=30 deg=360 start=-90
# over your shoulder: the canyon full of lasers
fly 8 -250,380,260 250,380,260 look=0,-6000,800
# rooftop pass along a laser unit
fly 12 -2800,-1000,6000 -2800,-5000,5200 look=2400,-3000,0
```
About 92 s. The real reel is checked by xm_dronecheck (sight lines, no clipping) before it ships.

## Appendix B. Budgets (Graveyard's, memory)

| budget | target | check |
|---|---|---|
| fps | >= 71 average at 72 Hz | logcat fps windows |
| tris | <= 600k total (crowd ~330k) | generator per-mesh log |
| actors | <= 40 | build_christmas.py log |
| translucent overdraw from the DJ | <= 2.5 layers/px | xm_overdraw.py |
| chunk size | <= 130 MB | pack output |
| load | <= 2 s | `[ENV]` log |
| flashes | <= 3/s, no 1-frame hits | xm_cuecheck.py, check_loop.py |
