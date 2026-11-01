# Hangar stage plan: RED EYE, with GREMLIN

Written 2026-10-17, after the user approved the concept renders ("go").

Ground rules:
- Nothing here is built for the game yet.
- RED EYE has no date. It runs in parallel with the other sessions but yields to the dated stages when they clash for
  the GPU or the headset:
  - Graveyard Shift keeps first claim on both until its stream on 2026-10-31;
  - after it, Thanksgiving (Nov 26) and Christmas (Dec 19 or 24) go first.
- Every headset push and APK install waits for the user's OK, given in this chat.
- Labels used below:
  - **read** = checked in a file or the code today;
  - **memory** = from the project memory, true when it was written;
  - **derived** = follows from read facts by the steps shown;
  - **estimate** = my number, to be measured;
  - **assumed** = not verified, with the check named.

Concept renders are in `claudedocs/redeye_concept/`:
- `redeye_concept_sheet.jpg` (8 views) and `gremlin_concept_sheet.jpg` (4 views);
- made by `C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\redeye\`:
  - `concept_blockout.py` and `gremlin_concept.py`;
  - `run_concept.sh`, which takes the shared GPU lock;
  - `sheet.py`;
- they show layout, scale, palette and the two hero moments, not the final look.

The reference is VOYD's closing set on the Dome stage at Rampage Open Air 2024. The running log is
`claudedocs/redeye_notes.md`.

---

## 0. Assumptions

| assumption | basis | if wrong |
|---|---|---|
| No stream date: a first playable early, the full show later | not stated | give a date and the phases get freezes like the other plans |
| "As big as Graveyard": hall + rig + lasers, airfield modules, a ~3.9k VAT crowd, the screen, a cue-table show, a VJ loop pack, a drone reel, an intro | the Graveyard, Midtown and Harvest plans' inventory | each section has a "cut if late" line |
| 140 BPM half-time for the show, the crowd and the loops | the user plays heavy dubstep, 128-150 BPM (memory) | one constant |
| It ships like the others: one pak in the shared patch OBB, a box in tribemod/envs.txt, the mod's loader | Dino, Graveyard, Reactor (memory) | none |
| Content folder `/Game/Mods/RedEye`, display name **RED EYE**, pak **chunk 59**, asset prefix `Re` | 56 Big Dub, 57 Harvest, 58 Midtown; 59 agreed with the Midtown session on 2026-10-16 (notes) | renaming the folder renames every per-stage file in section 10 |
| The hook finds every per-stage file by the folder name in lower case: `redeye` | em_active_folder (read: dumper.cpp:2170) | none |

---

## 1. Concept and art direction

**One line.** An aircraft hangar on a dead airfield at 3 a.m.:
- the crowd dances in a huge arched hall, built on the Rampage Dome's frame;
- VOYD's rig stands at the stage end: the laser line on the stage lip, the LED frame round the screen, the hard white
  top spot and the flame heads;
- the back doors stand open on a lit runway;
- in the opener, the overhead crane lifts the DJ into the air in a long ragged robe. A second crane lowers a 10 m copy
  of skullbuck's skull behind them.

**Palette.**
- Black, blood red (lasers, the frame) and cold white (the top spot, the crown lasers). The steel is hazard yellow,
  unlit: the cranes, the doors, the floor bands.
- Laser sections follow the reference video: red is the main look, green belongs to the wing, violet-white to the
  crown.
- Not used: Graveyard's orange/purple, Dino's cyan/magenta, Harvest's gold, Midtown's red-and-white. The flames are the
  only warm light.

**Darkness** (the user's standing rule: dark except the DJ, the visuals, the lasers and the lights):
- The hall is near black between hits. The ribs and the roof show only in laser light and haze.
- The light comes from the frame, the screen, the lasers, the heads, the top spot and the runway through the doors.
- The crowd stays dark: glowsticks and phones only.

**Comfort.** The rules that hw_cuecheck.py and check_loop.py enforce (memory):
- no strobes, and at most 3 flashes per second;
- every cue ramps over at least 60 ms;
- no full-frame white;
- fills swell into the downbeat.

On this stage that means:
- The runway's "rabbit" (its sequenced flashers) and the nav lights are soft ramped chases. They are small and far away.
- The flames fire on the hits as ramped cards, at most 3 per second, from the outer 8 heads only (nothing in front of
  the DJ).

**Mood by set section**

| section | stage | hall and airfield | crowd |
|---|---|---|---|
| intro | the frame's outline dim, the eye on the screen idle, the top spot faint | runway edge lights, the beacon, stars | sway |
| build | lip fans rise slowly, the frame stripes chase upward, the heads wake | the rabbit chases toward the hangar, the wing's edge wakes | pump |
| blackout bar | only the screen and the top spot | the runway only | hold |
| drop | lip fans to the floor (red), crown fans (white), flames on the hits, all heads | the wing's green lasers to the floor in the green sections | jump |
| breakdown | the crown in violet-white, slow; the frame dim | the beacon; sometimes a landing outside (the slow layer) | sway |
| outro | lip and crown alternate | the rabbit runs outward | shuffle |

**The opener** runs in song mode on PRELUDE I. Read today in `backup/tribemod_20261006/song.txt`:
`lift=69.0 126.0 166.0` and `cues=0:dark 113.1:top 166:drop ...`.

| time | what happens |
|---|---|
| 0:00 | dark |
| 1:09 | the crane lifts you over 8 s (giant.txt `rise=`, 8 s by default) and the top spot comes on; the mask comes down behind you over the same 8 s |
| 1:53 | the 'top' look: only the mask's eye beams and the top spot |
| 2:06 | you come down over 40 s; the mask goes back up into the roof |
| 2:46 | you land at the decks on the drop, and the show takes over |

**Slow layer.** A ~16-minute macro cycle runs on Time, like Graveyard's:
- the airport beacon turns (white and green);
- the windsock swings;
- once per cycle a jet lands on the runway outside. It is a rigid motion along a path on the macro clock, seen through
  the doors.

---

## 2. Layout and fixed constraints

**Frame.** The concept's frame (read: concept_blockout.py):
- meters, Z up;
- Tribe's floor is the DJ riser's top, z 0. The DJ faces -Y, toward the crowd and the doors;
- the deck top is at -1 and the hall floor (the crowd) at -2.5;
- the stage is behind the DJ (+Y).

FBX export mirrors Y; the UE import undoes it (memory).

**Fixed by Tribe** (memory, Graveyard plan section 3; world cm):
- DJ rig at (-5, 31, 78): booth top at 74 cm, x -95..85, y -5..50.
- SpectatorBoundingBox: x -250..250, y -221..279, z -6..494. Keep it clear.
  - The concept's dressing booth (y -0.6) sits inside it, so it goes. Tribe's own rig is the booth.
  - The lift parts inside it follow the Dino lift, which works there (memory: device-verified).
- BP_MiniMenu box: x -73..65, z 89..191.
- Every StaticMeshActor gets NoCollision via set_collision_profile_name, or the menu ray dies.
- Screen UVs: copy `visual_screen_uv` exactly.
- The lift's button position is fixed in the hook at (0, 152, 106) cm (read: dumper.cpp:2511, `G_BTN`). RED EYE's crane
  pendant puts its button cap exactly there.

**Top-down (meters; values read from concept_blockout.py):**

```
 y=+18          the back wall
 y=+9.2         VISUALS SCREEN 16 x 9 (SM_DinoVisualScreen in our package), centre z 6.5
 y=+8.6         LED FRAME: columns x +-10.2..12.6, header z 13.2..15.6, stripe bands; the crown lasers on the header
 y=~+5          CRANE 2 and THE MASK: parked dark in the roof; hangs behind the DJ during a flight
 y=+1.2         CRANE 1 over the lift plate (giant.py's plate: x +-0.6, y 0.7..1.7); the top spot under its trolley
 y=-3..16       stage deck x +-24, top z -1; DJ riser 8 x 3.4 (y -1.2..2.2), top z 0
 y=-3.25        flame heads on the lip: |x| > 12 only (8 of 16)
 y=-2.6         line arrays at x +-17, flown from z 15 up
 y=-4.2         subs under the lip; the lip laser line (14 emitters, x -19.5..19.5)
 y=-6.2         barrier
 y=-7.6..-93    the crowd on the hall floor; FOH at (0, -60)
 y=-46, z 13    THE WING: a 40 m black flying wing, nose to the stage, hung from the ribs
 y=-8..-82      6 light trusses across the hall at z 15.5 (moving heads)
 x=+-25, z 18   crane rails along the side walls
 y=-100         the door wall: opening x +-24 up to z 19, leaves stacked in pockets; the RED EYE sign over it
 y=-100..-185   the apron: the parked jet, the yellow taxi line out of the door
 y=-185..-2095  the runway, x +-22.5: edge, centre-line, threshold and end lights; the rabbit bars at y -260..-1160
 around         2 neighbour hangars, the tower with its beacon, the windsock, field fog, stars
 THE HALL       a 17-point polygon arch: 68 m span, apex 26.9 m above z 0; y -100..+18; truss ribs every 6 m
```

**The far runway and the sky.** The runway runs 1.9 km out, past the sky sphere (Dino's sphere, r 480; Harvest plan).
Beyond ~400 m its light rows are compressed onto the ground inside the sphere and sized for distance (the Dino far-tree
trick, memory). From the hall they still read as 2 km long.

---

## 3. The set, piece by piece

All of it comes from `re_stage.py`, which is Graveyard's generator (hw_stage.py) copied and adapted, never edited in
place.
- Baked with Cycles and exported one FBX per surface.
- Imported as MICs (stock build) or as fork-cooked materials (animated build).
- The tris are estimates.

| piece | content | tris | cut if late |
|---|---|---|---|
| Hall (SM_ReHall, SM_ReRibs) | the arch skin as fabric panels; 20 truss ribs as two-chord boxes with a lattice texture (not modelled lattice); purlins; the back wall; baked near black | 30k | purlins |
| Door wall and doors (SM_ReDoorWall, SM_ReDoors) | the opening x +-24 up to z 19; 8 leaves that roll into the pockets on `DoorOpen` (WPO along X); hazard stripes; the RED EYE LED sign | 5k | sign |
| Floor (SM_ReFloor) | concrete, hazard bands along the walls, the yellow taxi line out of the door | 1k | bands |
| Stage (SM_ReStage) | deck, riser, subs, barrier, line arrays, flame heads. Nothing in the SpectatorBoundingBox but the floor | 8k | line arrays |
| Screen (SM_DinoVisualScreen) | the 16 x 9 quad at y 9.2 with Tribe's UV0, in our own package (the name stopgap, section 10) | 2 | none |
| LED frame (SM_ReFrame) | columns and a header round the screen; stripe bands on the 'frame' row; the crown laser bar on the header | 3k | none (it is the look) |
| Cranes (SM_ReCranes) | two bridges and trolleys on the wall rails, SWL 40T signs, the top spot's housing under crane 1 | 6k | crane 2's sign |
| The lift (SM_ReLift, SM_ReLiftGlow, SM_ReRobe, SM_ReHook) | section 4.1 | 6k | the pendant's cable |
| The mask (SM_ReMask, SM_ReMaskBeams) | skullbuck's head mesh x16, decimated to ~6k (it has 14.2k faces; read: the concept's render log); 2 chains; the eye beams (section 4.2) | 7k | the chains |
| Rig (SM_ReRig) | 6 light trusses with 24 moving heads, the lip laser line, the crown bar | 10k | 2 trusses |
| Wing (SM_ReWing, SM_ReWingGlow) | the 40 m flying wing on 4 cables, a red LED leading edge, nav lights, 10 laser emitters underneath | 3k | nav lights |
| Airfield (SM_ReAirfield, SM_ReRunwayLights) | apron, runway, the light rows as one emissive mesh of camera-facing quads, the rabbit bars, the tower and beacon, 2 neighbour hangars, the parked jet, the windsock | 25k | neighbour hangars |
| FOH (module re_foh) | riser, desks, 2 follow spots | 3k | none |
| DJ area | deck lamps ReDeckLamp_L/R (Graveyard's DECK_LAMPS pattern, memory); nothing within 60 cm of the table edge | 1k | none |
| Sky (SM_ReSky) | the r 480 sphere: near black, a cold haze at the horizon, a star field in the texture | 1k | none |
| Haze | 2 sheets in the hall under the trusses; field fog outside the doors (Graveyard's fog_sheet, memory) | quads | the second sheet |

The set totals about 110k tris (estimate). That fits Graveyard's budget for the set plus the field (Appendix B).

---

## 4. The two hero moments: the crane flight and the mask

### 4.1 The crane flight reuses the Dino giant lift

How the lift works today (read in dumper.cpp):

| part | how it works | where |
|---|---|---|
| Height | the lift moves VROrigin's relative Z. The height is giant.txt `height=` (545 cm by default), shared by every stage that has the lift | :2594 |
| Button | a press within `press=` cm of the button at (0, 152, 106) cm starts the rise or the descent. The button rides up with the lift | :3007 |
| Song mode | the song script's `lift=` drives the lift, and presses are ignored | :3022 |
| Show bus | while you are up, every frame writes Height, RobeTopX/Y/Z (27 cm below the eyes, 8 cm behind) and RobeOn (above 25 cm) | :3099-3108 |
| Follow spot | the SpotLightComponent on an actor whose name contains "DinoGiantSpotLight", set to 6000 cd x SpotOn | :2558-2564, :2585 |
| Walking | pauses while the lift is up (`g_walkPause`) | :2517 |
| Drone | the "giant shot" cuts to (0, -1200, 240) cm, 12 m out and low. In RED EYE that is over the front rows and clear of the wing (derived from section 2) | :1891 |

**The gate:** `g_gHasGiant = dino && n[GP_H]` with `dino = si==0` (:2546, :2565). The lift runs on the Dino Stage's row
only.

**So RED EYE needs two changes from the Dino session.** The file is the Dino session's; we never edit it.
```cpp
// SHOWS (dumper.cpp:2539): one row
{"redeye","/Game/Mods/RedEye/MaterialInstances/MPC_ReShow.MPC_ReShow","MPC_ReShow"},
// :2546 and :2565: the lift on RED EYE's row too
bool lift=si==0||(si>=0&&!strcmp(SHOWS[si][0],"redeye"));
g_gHasGiant=lift&&n[GP_H];
```
The rest of the lift code works on any stage: our level matches the button position and the spot actor's name, and our
materials read the same parameters.

**What RED EYE builds.** `re_crane.py` copies and adapts giant.py's recipe (read: giant.py's header).
- **The plate** (SM_ReLift):
  - giant.py's plate (x +-0.6, y 0.7..1.7), a steel hatch with hazard edges;
  - flush with the riser at rest, riding at the full height (UV1.x = lift weight).
- **The pendant** (SM_ReLift + SM_ReLiftGlow):
  - a yellow crane pendant control box on a cable, with a big button cap centred at (0, 1.52, 1.06) m;
  - it rides up with the lift, like Dino's pedestal;
  - the cap glows on ButtonGlow and sinks on a press.
- **The robe** (SM_ReRobe): giant.py's robe material, copied and changed.
  - The hem doesn't stay on the floor: it hangs about 1.8 m below the plate (hem z = Height - 1.8 m, never below 0).
    You read as hanging in the air, not as a 7 m giant standing on the floor (decision 5).
  - The ragged hem is jagged geometry, not a masked material.
  - Its faces point outward only, so it is culled from inside, like Dino's.
- **The hook and lines** (SM_ReHook):
  - the hook block comes down from its parked spot under crane 1's trolley (z 15.6) to 2.8 m above your head as you
    rise;
  - two lines run from the hook to your shoulders (RobeTop), and the hoist cable up to the trolley shortens;
  - all of it is WPO on Height and RobeTop. It appears with the robe (RobeOn), following the Dino rule ("when im on the
    ground no cape").
- **The top spot.**
  - The spot light under crane 1's trolley is an actor named `DinoGiantSpotLight`, a name stopgap like the screen's.
  - It sits about 10 m above your head when you are up (z ~16.7 against ~7.2), while Dino's spot is 32 m away (read:
    the G_SPOT_CD comment, dumper.cpp:2531). The hook sets the same 6000, so the spot's units or attenuation are set in
    the level until it looks like Dino's (phase 2).
  - When you are down, a cone mesh on the 'spot' row gives the show its top spot.

### 4.2 The mask: keyed to the lift, no extra hook work

- **Recommended:** the mask moves with Height. As you rise, crane 2 lowers the skull behind you. As you come down, it
  goes back up into the roof.
  - This is material only: WPO = smoothstep(Height / 545 cm) x the drop distance.
  - The 545 is a material constant. If giant.txt's height changes, change it too.
- **Parked**, the skull sits in the roof's darkness, its colour multiplied down so it doesn't catch the lights. It
  brightens as it comes down.
- **It hangs behind you**, facing the crowd, at least 2 m behind the plate. When you turn round up there you see the
  whole skull, not its teeth.
- It covers the screen only while it hangs: in the opener, from 1:09 to 2:46 (decision 4).
- **The eye beams** are part of the mask, not of the laser engine:
  - two red beam fans in their own material, moved by the same WPO;
  - shown on the 'top' look (TopLasers), and only while the skull is down;
  - they pulse on Bass.
  - Why: the Dino laser engine's emitters can't follow WPO (the Harvest plan hits the same limit with its rim lasers).
- **If the hook change never comes**, Height stays 0, so there is no flight and the mask never comes down.
  - Fallback: the mask follows the show clock instead and comes down through each drop section.
  - It would then cover the screen in every drop, so it stays a fallback.

### 4.3 The doors ride the intro's door ramp

The doors ride `DoorOpen`, the intro's door ramp (the contract is in Harvest plan section 4):
- intro.cpp sets `DoorOpen` to 1 when a stage with an intro loads;
- it eases to 0 at press 1;
- it eases back to 1 when the music starts.

Our doors at each value:
- **0, shut:** the 8 leaves close across the opening;
- **1, open:** the leaves stack in the pockets.

Without an intro the doors are open (MPC_ReShow's default for `DoorOpen` is 1). At press 1 they roll shut. At showtime
they roll open on the runway.

### 4.4 Culling

A WPO-moved mesh is culled by its rest bounds (the same open question as Harvest's moon).
- build_redeye.py sets bounds extensions on the plate, the robe, the hook, the mask and the doors to cover both
  positions. **Assumed** to work through the StaticMesh bounds-extension properties.
- Dino's lift moves 5.45 m by WPO and works on device (memory), so the lift parts are low risk.
- The mask's ~8 m drop and the doors are new. Phase 2 checks them on device.

---

## 5. Rig, lasers and the show

- **Moving heads (24):** 4 on each of the 6 light trusses. They use the Dino mover engine, as Reactor v7 did (memory).
- **Lasers** run on the Dino laser engine.
  - Every beam lands on a surface and has the near-eye fade (20-80 cm), per Reactor v8 and Graveyard v7 (memory).
  - The beams stop at the hall's walls and roof (the concept's clip_len rule). A beam that leaves by the door runs on
    over the apron.
  - The units:
    - the lip line: 14 emitters, red fans into the crowd and down to the floor (the reference's main look);
    - the crown: 6 units on the frame header, white and violet-white, fanning over the crowd up to the roof ribs;
    - the wing: 10 units under the wing, green, straight down to the floor in the green sections. The lip line is off
      then, so the wing owns them (as in the concept);
    - the mask's eye beams (section 4.2) are separate from the engine.
- **Flames** come from the outer 8 heads (|x| > 12).
  - They are emissive flame cards that fire on HitMajor: ramped, at most 3 per second.
  - There are no dynamic lights. A baked glow on the deck front brightens with the row.
- **Show bus:** `MPC_ReShow` at `/Game/Mods/RedEye/MaterialInstances/MPC_ReShow`. It holds:
  - the 19 parameters the hook writes (read: dumper.cpp:2521, G_PARAMS: Height ... ShowNextBar). RED EYE uses the
    lift's set too (Height, RobeTop, RobeOn, ButtonGlow, SpotOn);
  - IntroStep and DoorOpen, for the intro;
  - PlayerX and PlayerY, for the crowd make-way. club.cpp writes them into whatever show collection is active (Harvest
    plan, read there 2026-10-16).
- **Bass** (read: G_PARAMS carries it) drives the eye beams, the frame's stripe speed and the wing's edge.
- **Cue rows (new names):**
  - lip
  - crown
  - frame
  - wing
  - flames
  - spot
  - trusses
  - rabbit (the runway's sequenced flashers)
  - airfield (the beacon, the nav lights, the tower)
  - macro (the landing jet, the windsock)
- **Gates:**
  - `re_cuecheck.py`: hw_cuecheck copied (ATTACK_S = 60 ms, no instant steps);
  - `re_overdraw.py`: the haze sheets, the top spot's cone and the beams.

---

## 6. Crowd and walking

- **Crowd v3 through a copy** (`redeye/crowd/`), the way Graveyard copied it. The RED EYE layer:
  - black, charcoal and dark olive, with red accents;
  - about 6% gremlin ears (fans of the mascot, as in the concept), 4% pilot caps and a few skull masks.
- **Glow:** red and white glowsticks and cold phone screens.
- **Totems:** a paper plane, a gremlin on a pole, a RED EYE sign.
- **Clips:** the same 17 at 140 half-time.
- **Density:** ~3.9k people, densest at the front and thinning toward the doors. The concept packed 6,058 onto the hall
  floor (read: the concept's render log).
- **Walking:** free roam with `redeye_collide.txt` on club.cpp. It keys on the folder name (read: club.cpp:12-13, 120),
  so no hook change. The map:
  - floors: the hall floor, the stage stairs and gate (Graveyard v7's pattern), and the apron outside the doors, so you
    can walk out of the hangar and look down the runway (decision 7);
  - boxes: the FOH and the barrier;
  - people: the soft crowd's `person` lines (club.cpp limit 4608, memory).
  - Walking pauses while the lift is up (read: `g_walkPause`).
- **Cut if late:** crowd v3 with only the glow colours swapped.

---

## 7. Stream intro: the night landing

It is built on the system the Horseman's and the scout's intros use, with no new hook code.
- intro.cpp:97 looks for `intro.<folder>.txt` (read). The file's contents follow Harvest plan section 7.
- The file is `tribemod/intro.redeye.txt`. It holds:
  - the ride as `key` lines, a `loop`, an `exit` and `cam` offsets;
  - the rider and light actor names;
  - the step and door show names;
  - `hold`, `back`, `fov`, and the button's position and radius.
- `redeye/intro/re_intro_path.py` is the single source of the ride.

The presses:
- **The button:** a red guarded switch on the side of the booth. It is never at the lift's button spot (0, 1.52, 1.06).
- **Press 1, the pre-show:**
  - the hall goes dark and the doors roll shut;
  - Tribe's video rewinds and pauses;
  - the stream camera rides with **the red-eye flight**: a small jet (`ReJet`, the rider) flying a holding pattern over
    the dark airfield, landing lights on, nav lights blinking softly;
  - the cones of its landing lights (`ReJetBeams`, a "woods" actor) sweep the ground, and the rabbit runs.
- **Press 2:**
  - the jet leaves the hold, lands, rolls out and turns off onto the apron;
  - it is hidden at the exit's end, where the parked jet has stood all along;
  - the camera holds on the wide shot of the hangar.
- **Press 3, showtime** (Graveyard's press-3 contract, memory):
  - the cut to the wide shot;
  - `hold` seconds later the cued deck and the video play;
  - the doors roll open over the door time;
  - the lights take the song. If the cued track is PRELUDE I, the opener (section 1) runs.

The head's `intro=hold` keeps GREMLIN's head on through all of it (memory: head.txt).

---

## 8. The character: GREMLIN

**The build.** GREMLIN is built on skullbuck's rig the way the Horseman was.
- It uses `scripts/horseman_build.py`'s tools: avatar_common.py, the profile + loft functions, render_skin.py,
  pose_test.py and check_skin.py (all present, read today).
- `skins/skullbuck.glb` stays untouched.
- New files:
  - `scripts/gremlin_build.py`;
  - `skins/gremlin.glb` and `heads/gremlin.glb`;
  - the box label comes from the file name, "Gremlin" (read: dumper.cpp:3465).

**The body** (the concept maquette, made real):
- torn olive coveralls lofted from skullbuck's body profiles: sleeves torn above the elbow, legs rolled to mid-shin, a
  zip, a chest pocket and a GREMLIN name tape;
- a tool belt with pouches and a wrench, rigid on Hips;
- bare grey-green forearms and shins, skinny;
- the hands:
  - three long clawed fingers and a thumb, weighted to skullbuck's finger bones so posed fingers still work with the
    controllers (memory: avatar spec);
  - the third finger takes the ring and pinky bones' weights, half each;
- bare clawed feet;
- a red pilot's scarf with its tails over the left shoulder, rigid on Spine2;
- RED EYE nose art on the back panel.

**The head** is 100% Head, with DH_C, DH_F and DH_U under Head (memory). It has:
- a leather flying helmet with a seam, goggles pushed up and a chin strap;
- bat ears through the helmet's slits, about 62 cm tip to tip and 37 cm above the head's centre (read: the notes);
- angry brows, a hooked nose and a needle grin that follows the jaw;
- big red eyes with slit pupils. They are emissive, which is untested (see below).

**The neck socket** is a brass threaded socket on the neck stump, weighted to Neck.
- The Horseman lesson: a Head-weighted collar collapses when Head is hidden.
- It sits inside the head while the head is on, and shows when the head flies.

**The flying head** runs on the existing flying-head code, unchanged (memory).
- `heads/gremlin.glb` is the flying copy. It adds:
  - a threaded bolt and a hex nut under the neck;
  - a propeller on the helmet's crown: two blades and a blur disc (r 0.17 m).
- The attached head inside skins/gremlin.glb has neither.
  - **Derived:** heads/<skin>.glb is a separate static mesh, so the two copies can differ with no code change.
  - The first device test confirms it.
- It flies the ORBIT ring like a toy plane: r 90 cm round the hips, about 10 cm above head height.
- head.txt keeps its knobs (`every=600`, `boomax=12`, `intro=hold`).
- The propeller can't spin: the flying head is one static mesh with glTF's standard materials. The blur disc fakes the
  spin.

**Unverified on device, tested first:**
- **The blur disc** would be a see-through material on an avatar, just like Major Tom's glass helmet.
  - One test answers both. The Harvest plan runs it first, with a throwaway skin carrying one glass sphere, and RED EYE
    uses its result.
  - Fallback: the two blades only, opaque.
- **The red eyes' glow.** The Horseman's glow was never confirmed by eye (memory).
  - Fallback: a bright red that looks unlit.
- **The ears.** Check them:
  - in pose_test;
  - in the selfie camera (cut off at the top of the frame?);
  - in first person (do they intrude when you look up?).
  - Fallback: shorter ears, a 45 cm span.

**Skin boxes.**
- The avatar menu holds 8 boxes (read: dumper.cpp:2075, `SM_MAX 8`).
- skins/ on this PC holds 5 today: default, horseman, lampwing, mentor, skullbuck (read).
- With Major Tom and Santa, Gremlin would fill the 8th box.

**Device tests** need the user's OK for every push.
- The skin and the head go on the re-seed backup list (section 10).
- Tell the character session (head.cpp's owner) before the first push.

---

## 9. Visuals: the RED EYE loop pack and the hour set

The pack follows the vjkit gates (check_loop.py; memory: Dino VJ loops):
- 140 BPM half-time, 411 frames per 8-bar loop;
- the key art inside the screen's window, on black backgrounds;
- no strobes.

| # | loop | slot | picture | beat hook |
|---|---|---|---|---|
| 1 | Red Eye | intro | one huge slit-pupil eye in the dark; the pupil narrows and widens | blink per bar |
| 2 | Final Approach | build | runway lights rush at the camera while the rabbit chases ahead | a light bar per beat |
| 3 | Hangar Doors | drop | the doors roll apart on the downbeat onto the runway | doors on 1 |
| 4 | Gremlins | heavy drop | clawed hands unscrew bolts on a wing panel; the bolts pop on the snare | pop on 3 |
| 5 | Flameout | drop | a jet engine's turbine face spins up; flame rings burst on the kick | ring on 1 |
| 6 | Black Box | breakdown | a flight recorder's trace and a voice waveform, red on black | trace per bar |
| 7 | Radar | breakdown | a green radar sweep whose blips form a skull | sweep per bar |
| 8 | Eyes | heavy drop | rows of red slit eyes open across a black wall | open on 1 and 3 |
| + | RED EYE sting | ID | the letters in LED font light up behind the opening eye | identity |

Delivery:
- the loops go to `/sdcard/Movies/RED EYE Visuals/`;
- a 60-minute set video is made with assemble_set.py (read: Visuals/scripts/assemble_set.py);
- pushed only on the user's yes.

---

## 10. Pipeline and files (nothing shared is edited)

```
C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\redeye\
  concept_blockout.py, gremlin_concept.py, run_concept.sh, sheet.py     the concept (done)
  re_stage.py           the generator: hw_stage.py copied and adapted (orchestration, drop, bake, export, manifest)
  re_kit.py             extends kit's palette in-process (blood red / cold white / hazard yellow / laser green and
                        violet) + helpers (polygon arch, rib, truss rows, runway light rows, LED frame)
  re_crane.py           the two cranes, the lift (giant.py copied and adapted: plate, pendant, robe, hook), the mask
  re_show.py            the cue table at 140 BPM
  modules\              re_hall.py re_rig.py re_wing.py re_airfield.py re_foh.py re_atmosphere.py + preview harness
  crowd\                the crowd v3 copy with the RED EYE layer
  intro\                re_intro_path.py (single source of the intro), re_collide.py (redeye_collide.txt)
  checks                re_cuecheck.py re_overdraw.py re_dronecheck.py (copies of the hw_ gates)
  ship_re.sh            bake -> cuecheck -> overdraw -> dronecheck -> UE build/cook/pack -> shader-archive check ->
                        push_obb.sh (stops at the first failed gate; RE_ANIM=1 for the animated build)
C:\Users\Chris\TribeUE\TribeXR\Scripts\build_redeye.py    UE import: /Game/Mods/RedEye, chunk 59, bounds extensions
D:\TribeUE\MetaRedEye\TribeXR                              fork-project copy (D: has 321 GB free, C: 19 GB; read today)
C:\Users\Chris\TribeUE\Visuals\redeye\                     the loop pack
tribe hack\scripts\gremlin_build.py                        the skin (+ skins/gremlin.glb, heads/gremlin.glb)
tribe hack\claudedocs\redeye_notes.md                      the running log
```

The templates exist (read today): hw_stage.py, hw_show.py, hw_cuecheck.py, hw_overdraw.py, hw_dronecheck.py and
ship_hw.sh in `Blender\halloween\`; giant.py in `Blender\`; build_halloween.py and dino_materials.py in `Scripts\`.

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
- **Thin trim inside a thicker panel never renders** (Harvest's door X-trim).

**Per-stage files on the headset** (read today: all are found by the folder name, `redeye`):

| file | read where | RED EYE name |
|---|---|---|
| walking map | club.cpp:12-13, 120 | `tribemod/redeye_collide.txt` |
| drone reel | dumper.cpp:1948 | `tribemod/drone_path.redeye.txt` |
| stream intro | intro.cpp:97 | `tribemod/intro.redeye.txt` |
| env menu box | envs.txt | `RED EYE=/Game/Mods/RedEye/Maps/Environment_RedEye` |
| screen | `em_find_mesh_actor("SM_DinoVisualScreen")` (Midtown plan: dumper.cpp:2322) | our screen mesh asset is named SM_DinoVisualScreen in our package |
| the skin | the avatar menu (one box per skins/*.glb, at most 8) | `skins/gremlin.glb`, `heads/gremlin.glb` |
| lift settings | giant.txt, shared with the Dino Stage | nothing new: RED EYE uses the same height and timing |

**Re-seed rule (memory):** every new tribemod file also goes into `backup/tribemod_20261006/`, and its name goes to the
Dino session for reseed.sh's list. Otherwise a re-seed silently drops it.

---

## 11. Other sessions: what we need from each, what we never touch

| session | what RED EYE needs | rule |
|---|---|---|
| Dino (owns dumper.cpp, reseed.sh, re-seeds, most APKs) | (a) the `"redeye"` SHOWS row; (b) the lift on that row (section 4.1, two lines); (c) our tribemod names on the re-seed list. EM_MAX is already 8 (read: dumper.cpp:2166) | ask through the user or messages; never edit its files |
| Reactor (owns club.cpp) | nothing: walking and the make-way work by folder name | |
| Character (owns head.cpp) | nothing: the head works unchanged | tell it about skins/gremlin.glb before any push |
| Halloween | its scripts are the templates: copy, never edit; it shares the GPU lock; first claim on the headset until Oct 31 | copies only |
| Harvest (57) | its see-through avatar test (Major Tom's glass) also answers the propeller disc | share the result |
| Midtown (58), Big Dub (56) | the 8 menu boxes are shared (decision 2) | chunk 59 is ours |

EM_MAX 8 in detail:
- dumper.cpp last changed 2026-10-16 21:16 (read).
- The combo5 build (out/hookA/combo5.apk) was made at 21:18. Its hook carries the Christmas row's `MPC_XmShow` string
  (read), so it was built from that source (derived).
- Whether combo5 is installed on the headset was not checked.

---

## 12. Phases (parallel; RED EYE yields to the dated stages; dates are targets)

| phase | dates | work | gate |
|---|---|---|---|
| 0 Scaffold | Oct 18-25 | the MetaRedEye copy on D: and its first cook (a 37 min shader compile, memory); a re_stage.py blockout from the concept geometry (hall, ribs, door wall, deck, frame + screen, floor, apron, runway lights, sky); MIC-only; chunk 59; a box (decision 2); push on the user's OK | loads <= 2 s, the screen plays a media video, 71+ fps, the other stages still load from the same OBB |
| 1 The set | Oct 26-Nov 9 | hall detail, the doors on DoorOpen, the frame stripes, the rig and heads, lip and crown lasers, flames, the wing and its lasers, the airfield; the first full bake; stock, then animated | previews approved in chat; laser clearance; a headset pass |
| 2 Crane + mask | Nov 2-16 (needs the Dino session's two changes) | re_crane.py: plate, pendant, robe, hook and lines, the spot; crane 2, the mask and its eye beams; bounds | PRELUDE I and the button both fly you up and down on device; nothing culled; the mask hangs behind you and parks dark |
| 3 Crowd + walking | Nov 9-23 | the crowd layer, totems, redeye_collide.txt (hall and apron) | crowd fps >= 71 on device; a walk test out to the apron |
| 4 GREMLIN | Oct 19-Nov 16 (parallel) | gremlin_build.py, skins/ and heads/gremlin.glb, check_skin.py, pose_test (fingers, ears, the orbit) | LOADS + MOVES; the head flies a full cycle on device; the user's look verdict |
| 5 Animated show | Nov 16-30 | MPC_ReShow and the re_show cue table, the rabbit, the landing jet, haze; fork cook; re_cuecheck | cuecheck passes; the user's comfort verdict in the headset |
| 6 Intro | Nov 23-Dec 7 | re_intro_path.py, intro.redeye.txt, ReJet and its beams, the switch | presses 1-3 on device; the doors shut and open on cue |
| 7 Media | after Thanksgiving's media (the GPU queue) | 8 loops + the sting, the hour set, the drone reel | check_loop.py on every loop; the reel plays through clean (re_dronecheck) |
| 8 Polish | December, around Midtown's freeze | the user's notes | the user's sign-off |

---

## 13. Decisions for the user (the plan proceeds on the recommendation if unanswered)

1. **Date.** None is assumed. If you want RED EYE for a particular stream, give the date and the plan gets freezes.
2. **Menu box.** EM_MAX is 8 in the mod's source and in the combo5 build (section 11).
   - With Midtown and Harvest Moon, RED EYE is the 7th box, and Big Dub needs 1 to 3 more.
   - Recommended: RED EYE takes the 7th box. If the 8 run out, drop Dino Classic (or Graveyard after Halloween).
3. **The crane flight.** Recommended: the Dino lift on RED EYE (a SHOWS row and two changed lines in the Dino session's
   file, section 4.1). Otherwise there is no flight on this stage.
4. **The mask.** Recommended: it comes down while you fly and hangs behind you, in front of the screen. Or hang it
   higher, clear of the screen.
5. **The robe.** Recommended: it hangs ~1.8 m below your feet, so you read as flying. Or Dino's floor-length robe, so
   you read as a 7 m giant.
6. **Gremlin's propeller.** Recommended: try the blur disc, using the shared see-through test. Two opaque blades if it
   fails.
7. **Walking out onto the apron.** Recommended: yes. Or the hall only.

---

## 14. Risks, ranked (probability x cost x silence)

1. **The hook changes sit in the Dino session's file** (the SHOWS row, the lift on our row).
   - This failure is silent. Without them the stage loads and the show runs free, but the opener's `lift=` is ignored
     ("a lift= needs the giant", dumper.cpp:3002) and the mask never moves.
   - Mitigation: ask in phase 0. On the first device visit, look for `[GIANT] ready` in the log, not `show bus: ... no
     giant intro`.
2. **WPO bounds and culling** on the mask's drop and the doors.
   - Silent in previews, loud on device.
   - Mitigation: bounds extensions, the phase 2 device check, the show-clock fallback for the mask.
3. **The hall's translucency and texture budget.**
   - Haze sheets under a 68 m roof, the spot's cone and the beams stack overdraw. The big baked surfaces cost texture
     memory.
   - Mitigation: re_overdraw, a bake atlas sized per surface in phase 1, the fps gate.
4. **The menu has 8 boxes for up to 10 stages.** Mitigation: decision 2, and envs.txt swaps for early tests.
5. **Avatar see-through and glow are unverified** (the propeller disc, the eyes). Mitigation: the shared test, the
   fallbacks.
6. **Gremlin's three-finger hands** with controller poses. A merged ring-and-pinky finger may bend oddly. Mitigation:
   pose_test on every finger pose before the first push.
7. **Time.** RED EYE yields to Halloween, Thanksgiving, Christmas and Big Dub, all on one PC, one headset and one tester.
   Mitigation: phases that end shippable, cut-if-late lines, device tests batched with the other sessions'.
8. **The Meta token on a stream day.** Mitigation: the re-seed procedure, and no APK install after the final re-seed.

---

## Appendix A. Drone reel draft (drone_path.redeye.txt; world cm, DJ at the origin, crowd -Y)

```
# in through the doors from the apron, the hall full of lasers ahead
fly 14 0,-16000,1200 0,-9000,900 look=0,800,800
# under the wing, across
fly 12 -1600,-5200,800 1600,-4000,800 look=0,-4600,1300
# along the crane rail toward the stage (1 m inside the rail, above the truss ends)
fly 14 2300,-7000,1700 2300,-800,1700 look=0,800,700
# low over the crowd toward you
fly 12 0,-2400,500 0,-700,330 look=dj
# close orbit (GREMLIN's head orbits inside this)
orbit 14 r=260 h=30 deg=360 start=-90
# over your shoulder: the hall and the open doors
fly 8 -250,380,260 250,380,260 look=0,-10000,600
# the lip laser line at floor level
fly 12 -2200,-900,-120 2200,-900,-120 look=0,-3000,0
# up the LED frame toward the roof
fly 12 1400,-300,200 1400,-300,2000 look=0,860,1000
# out of the doors: the runway
fly 12 1500,-9400,400 -1500,-10400,400 look=0,-60000,200
```

The reel runs about 110 s.
- re_dronecheck checks the real reel before it ships: sight lines, no clipping, and the wing, the cranes and the mask's
  volume as keep-outs.
- During a flight the drone holds the giant shot at (0, -1200, 240) (read: dumper.cpp:1891).

## Appendix B. Budgets (Graveyard's, memory)

| budget | target | check |
|---|---|---|
| fps | >= 71 average at 72 Hz | the `[PERF]` log lines (read: dumper.cpp:2495) |
| tris | <= 600k total: crowd ~330k, set ~110k, airfield ~25k | the generator's per-mesh log |
| actors | <= 40 | build_redeye.py's log |
| translucent overdraw from the DJ | <= 2.5 layers/px (haze, the spot's cone, the beams) | re_overdraw.py |
| chunk size | <= 130 MB | the pack output |
| load | <= 2 s | the `[ENV]` log |
| flashes | <= 3/s, no 1-frame hits | re_cuecheck.py, check_loop.py |
