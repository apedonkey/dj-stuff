# RED EYE + GREMLIN (hangar stage): notes

Running log for the hangar stage and its character. No date is tied to it (not a seasonal stage). Halloween keeps the
GPU, the headset and the hook until 2026-10-31; Christmas (MIDTOWN, chunk 58) and Thanksgiving (HARVEST MOON, chunk 57)
build in parallel, so every render goes through the GPU lock.

## 2026-10-16: the reference, the pitch, the pick

The user: "i want to make a stage and character. the stage should take example from Rampage festival in the hanger
airport stage from 20125. not sure on a character", then "im more thinking voyd set".

**The reference, as found:**
- VOYD (SVDDEN DEATH's dark project) played Rampage Open Air **2024**, not 2025: day 2's closing set on the **Dome**
  stage, Kristalpark Lommel, Belgium (an industrial zone, not an airport).
  Video: https://www.youtube.com/watch?v=oh4r5KiT7zg (SVDDEN DEATH's channel, 58:41).
- The Dome is a huge clear-span hall: a polygon arch of steel truss ribs, fabric panels, rows of light truss across
  the roof. That is why it reads as an aircraft hangar. 2025 photos (Excision, MUZZ) show the same kind of hall.
- What frames of the video show (sampled at 1:30, 7:00, 15:00, 34:41, 41:00, 48:00, 53:00, 56:10):
  - a near-black room;
  - fans of single-colour lasers from a row of emitters at the stage (red sections, green sections, violet-white);
  - an LED frame round the DJ with pink/white stripe patterns;
  - starfield and flesh-with-eyes visuals on the screen;
  - one hard white spot from straight above on the masked DJ (robe, deer skull, antlers);
  - a row of orange point lights along the deck front.
- Dubstep FBI's 2024 recap says "VOYD's mask was lowered from the top of the stage" and lists 20+ lasers, pyro and LED
  screens. The video's thumbnail shows him in the air on wires.
- Already in the project: the user's avatar skullbuck (white deer skull + antlers, dark body) and the Dino stage's giant
  lift with its floor-length robe (VROrigin Z, device-verified) are both VOYD homages. So the character went
  elsewhere, and the lift is reused for the crane flight.

**Pitched** (chat): stage RED EYE, plus character options MOTHMAN (recommended), EJECT, THE ACE and GREMLIN.
**The user picked 4: GREMLIN.** RED EYE was the only stage pitched, so it stands. Other names offered: HANGAR 13,
BLACK BOX, DEAD AIR.

**Stage RED EYE:**
- An aircraft hangar on a dead airfield at 3 a.m., on the Dome's frame.
- The stage end carries VOYD's rig, with no VOYD or Rampage logos: the lip laser line, the LED frame with the screen
  inside, the top spot, flame heads on the deck front.
- Crane flight: the overhead crane hoists the DJ during the intro track (the Dino giant lift, with the robe, blackout
  and follow spot).
- Mask drop: the crane lowers a 10 m skullbuck skull on the first drop.
- A 40 m black flying wing hangs over the crowd, with lasers to the floor.
- The back doors stand open on the runway; its strobes chase toward the hangar on build-ups.
- Intro: a night landing on Graveyard's 3-press system.
- Palette: black, blood red, cold white, with green and violet laser sections. It avoids Graveyard orange/purple,
  Dino cyan/magenta and Harvest gold.

**Character GREMLIN** (the RAF folklore saboteur, not the film's look):
- A wiry grey-green creature in torn olive flight-line coveralls (sleeves torn above the elbow, legs rolled to
  mid-shin).
- Huge bat ears come through the slits of a leather flying helmet. Goggles pushed up, glowing red eyes with slit
  pupils, a hooked nose, a needle grin.
- Three long clawed fingers, bare clawed feet, a red pilot's scarf, a tool belt with a wrench, a GREMLIN name tape.
- RED EYE nose art painted on his back.
- Flying head: the head unscrews. The flying copy (heads/gremlin.glb) carries a threaded bolt under the neck and a
  little propeller on the helmet. It flies the ORBIT ring like a toy plane and buzzes the camera.
- The body keeps a brass threaded socket on the neck stump (Neck-weighted, the horseman lesson).
- Derived, not tried: heads/<skin>.glb is a separate static mesh, so the flying copy can differ from the attached head
  with no code change.

## Concept renders

Generators are in `C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\redeye\`:
- `concept_blockout.py`, the stage. It has 8 views, each rendering one state:
  - approach (pre: the intro's final approach down the runway);
  - interior, stream, dj_view, venue (show: red);
  - crowd (green: the wing's lasers on the floor);
  - mask (the skull on the crane);
  - flight (blackout, the DJ on the hook).
- `gremlin_concept.py`, the character: primitives on skullbuck's bone heads (the Major Tom table). Views: front,
  back, closeup, flight (head off on the orbit ring; the neck socket shows).
- `run_concept.sh` takes the GPU lock. Set `RE_SCRIPT=gremlin_concept.py` for the character.
- `sheet.py` makes the contact sheets.
- Both scripts take `--dry`, which builds the scene with no render (no GPU lock needed). Stage: 301k faces, 6,061
  people, 8 s. Gremlin: 9.9k faces.
- Renders go to `claudedocs/redeye_concept/`.

Frame: meters, Z up, the DJ at the origin on the riser top (z 0) facing -Y. Deck top z -1, the hangar floor (crowd)
z -2.5.
- The hall: a 17-point polygon arch, 68 m span, apex 26.9 m above z 0, from the back wall y 18 to the door wall
  y -100. Ribs every 6 m, inset 0.75 m.
- The door opening: x +-24, floor to z 19, leaves stacked in pockets.
- The screen: 16 x 9 m at y 9.2, centre z 6.5. The LED frame at y 8.6 spans x +-12.6, z -1..15.6.
- The crane: rails at x +-25, z 18. The bridge sits over the DJ (y -0.3), or at y 4 for the mask.
- The giant skull: skullbuck_head.glb x16 at (0, 4, 8), facing -Y. Its eyes were estimated from the mesh's front
  profile, at (+-1.09, 2.0, 9.2).
- The wing: centre (0, -46, 13), nose toward the stage.
- The runway: x +-22.5, y -185..-2095. The strobe bars: y -260..-1160 every 60 m.

**Open (for a plan if the concept is approved):**
- The menu box. `#define EM_MAX 4` (dumper.cpp:2166) and the menu is full. MIDTOWN and Harvest asked the Dino session
  for EM_MAX 8, and that would cover RED EYE too.
- The chunk: 59, agreed with the MIDTOWN session 2026-10-16. Content /Game/Mods/RedEye.
- The crane flight: the Dino giant lift lives in the Dino session's dumper.cpp. It needs a per-stage hookup (it
  checks "a custom stage is active") plus the visible cables and hook as a moving part.
- The mask drop: a rigid hero motion (the Harvest moon's descent faces the same question). The skull covers the
  screen while it hangs.
- The flying wing's lasers to the floor: Reactor v8 / Graveyard v7 recipe.
- The propeller blur disc is translucent on an avatar mesh, which is untested (Major Tom's glass helmet is the same
  question). Fallback: two opaque blades only.
- Gremlin ears: about 62 cm tip to tip and 37 cm above the head centre (pass 2 shape). They need checking in the selfie camera and for clipping in first person.

## 2026-10-16 21:41: concept renders made (awaiting the user's reaction)

- `claudedocs/redeye_concept/redeye_concept_sheet.jpg` (8 views) and `gremlin_concept_sheet.jpg` (4 views), plus each
  view as its own jpg. Rendering takes ~25 s under the GPU lock (stage 16 s, gremlin 7 s).
- Three passes, checked by eye each time:
  - pass 1 was far too bright and orange (flame lights and washes), had flame spikes in front of the DJ, and lasers
    ran through the walls;
  - pass 2 was dark, with lasers clipped to the hall (`clip_len`; a beam that leaves by the door runs on over the
    apron);
  - pass 3 gave the green section to the wing alone (the lip lasers are off) and fixed a grey veil in dj_view (the
    camera sat inside the top-spot cone, now hidden in that view).
- Gremlin pass 2 added angry V brows, upright pointed bat ears with a dark membrane, bigger eyes, a wider grin, a
  helmet seam, no "button" oil stains, and the flying head turned to grin at the camera.
- Still crude: the robe in `flight` reads grey (the spot cone sits in front of it), the bridge sign is cut off at the
  top of `stream`, and the crowd is boxes.

## 2026-10-17: the plan

The user on the renders: "go". The plan is `claudedocs/redeye_plan.md`. Its main choices:
- content `/Game/Mods/RedEye`, chunk 59, display name RED EYE, show bus `MPC_ReShow`, asset prefix `Re`;
- the crane flight is the Dino giant lift. It needs two things in the Dino session's file:
  - a "redeye" SHOWS row;
  - the lift enabled on that row (today `g_gHasGiant = dino && n[GP_H]`, dumper.cpp:2565);
- the mask moves with the lift's Height (material only):
  - it comes down behind you while you fly and parks dark in the roof;
  - its eye beams are its own material (the laser engine can't follow WPO), shown on the 'top' look;
- the robe's hem hangs ~1.8 m below the plate, so you read as flying, not as a 7 m giant;
- the doors ride the intro's DoorOpen. The intro is a night landing: a jet in a holding pattern lands and parks;
- GREMLIN is built on skullbuck's rig with horseman_build.py's tools. The propeller's blur disc waits on Harvest's
  see-through avatar test.

Facts found today (read):
- dumper.cpp (changed 2026-10-16 21:16):
  - EM_MAX is now 8 (it was 4 on 10-16);
  - the SHOWS table has a "christmas" row but no "harvest" row;
  - combo5 (out/hookA, built 21:18) carries the Christmas row. Whether it is installed was not checked.
- The lift:
  - its button is fixed at (0, 152, 106) cm (G_BTN);
  - the follow spot is the SpotLightComponent on any actor named "DinoGiantSpotLight";
  - the drone's giant shot is at (0, -1200, 240).
- PRELUDE I's script (backup/tribemod_20261006/song.txt) has `lift=69.0 126.0 166.0` and
  `cues=0:dark 113.1:top 166:drop ...`. It is the only file with a 'top' cue in Scripts/songs or the backup.
- The avatar menu holds 8 skin boxes (SM_MAX 8, dumper.cpp:2075), and skins/ has 5 on this PC.
- C: has 19 GB free, D: 321 GB.

Phase 0 waits for the user's go.

## 2026-10-17: phase 0 started (the user: "go")

**New files** (nothing shared edited):
- **`Scripts\Blender\redeye\re_stage.py`**: the generator, v0. Midtown's xm_stage.py pipeline (Cycles bake, glow
  palette, the screen's UV layout, FBX export, previews), copied and adapted to the concept's geometry.
  - Frame: FINAL Tribe coordinates (riser top 0, deck -1, hall floor FIELD_Z = -2.5), the same as the concept.
  - **Baked:** SM_ReHall (skin inside + outside, back and door walls, the open door leaves, the header, crane rails;
    4096), SM_ReStage (deck, Dino's riser 9 x 5.5, the booth under Tribe's gear, rig bodies, the LED frame's body, two
    bridge cranes at y 1.2 and 5.0, FOH; 4096), SM_ReFloor (one quad on its own 0-1 UVs; joints, hazard bands and the
    taxi line come from a position-based bake material; 4096), SM_ReAirfield (apron, the runway's near 265 m,
    neighbour hangars, tower, parked jet, windsock, flood masts; 2048).
  - **Flat:** SM_ReRibs (truss ribs, purlins, light trusses, head bodies: 35k tris, the heaviest mesh), SM_ReWing,
    SM_ReFarGround (a 475 m disc).
  - **Glow** (SM_ReGlow on T_ReGlowPal, 17 keys): the LED frame's 91 red / white bands, RED EYE over the door (out
    and in), uplight boxes, exit signs, head lenses, the top spot lens, crane lights and SWL 40T signs, the wing's
    edge and nav lights, the airfield's lights. Runway lights past 400 m from a mid-hall eye are pulled into the sky
    sphere along their sight lines and never drawn under ~1.5 px (`far()`, `light_pt()`).
  - **Screen:** SM_DinoVisualScreen 16 x 9 m at y 9.2, centre z 6.5, Tribe's UV layout.
  - `--dry` builds the meshes only (no GPU): 50,500 tris in 1.8 s.
- **`run_re_stage.sh`**: the generator under the GPU lock; RE_OUT overrides out_re.
- **`Scripts\build_redeye.py`**: build_christmas.py with RED EYE names: unlit MICs of Tribe's glTFRuntime parents,
  NoCollision on every actor, PAL_RedEye -> chunk 59, ReDeckLamp_L/R, level /Game/Mods/RedEye/Maps/Environment_RedEye.
- **`D:\TribeUE\MetaRedEye\TribeXR`**: the project copy, 9.6 MB (uproject, Config, Build, Plugins, Binaries from
  MetaHw; Scripts/pack_chunk.sh + make_obb.py), plus `Scripts\cook_redeye.sh [build|cook|pack|all]` (logs in
  D:\TribeUE\MetaRedEye\logs).

**Fast pipeline test (scratchpad re_fast, 10:33):**
- Generator `--fast`: 29 s under the GPU lock (it waited for the Reactor session's render first).
- `cook_redeye.sh all` on that output:
  - build ok: screen centre y = -920 cm -> level yaw 180 (as Midtown); 10 actors + 2 deck lamps;
  - cook "Success - 0 error(s), 3 warning(s)" (the same engine cvar notes as Graveyard, the club and Midtown), 23 s
    commandlet, 45 s step;
  - chunk 59 manifest: 27 entries, 0 outside Content\Mods\RedEye. Pak 8.2 MB with the 1/8 textures.
- Look fixes from the fast previews: the crane yellow read orange under the frame's light (now a dirty yellow,
  0.15/0.10/0.012); the SWL 40T signs were lit (now a painted grey, glow key "paint"); the stage washes halved
  (20000 W) so the crowd floor stays darker; the flat ribs read as grey wireframe (now 0.004, dark steel against the
  red-lit skin); the neighbour hangars' barrel roofs were open at both ends (now capped).
- Bug found and fixed: `far()` compressed the far runway into 400..460 m from the mid-hall eye, which put the far end
  (y < -480) outside the 480 m sky sphere, hidden. Now 340..420 m: the threshold lights land at ~465 m from the
  origin, inside the 475 m ground disc.

**The first full bake died at 10:34: "Malloc returns null: len=369098752 in Cycles Aligned Alloc, total 1208856552".**
- Cause (read in Windows at 10:36): 31.9 GB RAM with 8.4 GB free, but the commit limit is 38.9 GB with only 3.9 GB
  free. The page file is fixed at 7 GB because C: is 98% full, so Windows refuses allocations long before RAM runs
  out. The biggest holder was `RelicCardinal` (7.8 GB commit; probably a game, not ours). My UE cook test was running
  at the same time (0.9 GB).
- Fixes in re_stage.py: each bake frees its 4096^2 float buffer when its PNG is written, and `wait_commit()` waits up
  to 3 min for 2.5 GB of free commit before a 4096 bake (logged as "free commit ... GB").
- A bigger page file on D: would remove the problem; that is a system setting, so it is the user's call.

**The second full bake (from 10:46) was stopped by Claude Code at ~10:51: the PC was critically low on memory.**
- It had finished T_ReHall (4096, 64 spp + OIDN, 246 s; output mean 0.003) and was on the stage (free commit 4.5 GB at
  its start).
- At the stop: commit 1.7 GB free of 39.0 GB. Holders: this bake 4.2 GB, RelicCardinal 3.1 GB, another session's
  Blender (subway_rush.py --variant candy, started 10:49 while this bake held the GPU lock) 1.65 GB, another session's
  UnrealEditor-Cmd 1.8 GB, several Claude sessions ~0.7 GB each.
- The stop killed only the bash wrapper. Its Blender child (pid 26500) kept running with 4.2 GB and the GPU lock, and
  the wrapper's trap could no longer release the lock. I ended pid 26500 at 10:53 (memory back to 5.0 GB free). The
  lock was already gone by then (not removed by me).
- Not restarted: the stop notice says to restart only when the user asks. Options for the user: the full 4096 bake
  (~15 min, peaks ~4 GB; best with RelicCardinal closed), or a lighter v0 bake at 2048 (about a quarter of the memory).

**combo8 carries RED EYE's hook lines (the user's OK in this chat).**
- tribe-hack-57 (Thanksgiving) reported at ~12:19 that tribe-hack-20 (Reactor) was about to build combo7 from
  hook/dumper.cpp 4476d98c (their Harvest SHOWS row). The user picked "Yes, you edit": this chat edits dumper.cpp
  once, in place of the Dino session.
- 12:47: dumper.cpp 4476d98c -> 3476d016 (the pre-edit copy is in this session's scratchpad). Two changes in
  giant_lookup():
  - :2544, a new last SHOWS row `{"redeye","/Game/Mods/RedEye/MaterialInstances/MPC_ReShow.MPC_ReShow","MPC_ReShow"}`
    (the harvest row now ends in "},");
  - :2567, `g_gHasGiant=(dino||!strcmp(SHOWS[si][0],"redeye"))&&n[GP_H];` (si >= 0 there: the `!c` return comes
    first).
- tribe-hack-20 had already finished combo7 from 4476d98c, so it built **combo8** from 3476d016:
  out/hookA/combo8.aligned.apk, md5 7d6a9051ef5716f74a171900679d0079, libhook_combo8.so 6c5271a2 (compile exit 0,
  the same 7 warnings; it re-checked the diff). combo8 replaces combo7 for installing. Not installed; the install is
  the Reactor chat's, on the user's go there.
- What MPC_ReShow must do (read in giant_lookup; for phase 2):
  - be loaded (a material in the level reads it; an asset nothing references never loads) and carry at least 6 of
    the 19 G_PARAMS. Otherwise the lookup returns before g_gColl is set and repeats every 2 s (tick%4 of the 500 ms
    poll), logging "only n/19 parameters" each time;
  - carry no "Height" scalar until the crane exists. Height alone arms the lift on RED EYE: a hand within press= cm
    of G_BTN (0, 152, 106) cm starts it even with nothing drawn there, and so do the song's lift= cues;
  - the lift's numbers come from the one shared tribemod/giant.txt (hook defaults: height 545 cm, rise 8 s,
    descend 60 s, press 14 cm), so the crane flight uses Dino's;
  - the follow spot is any SpotLightComponent whose owner's name contains "DinoGiantSpotLight" (null-safe without).
- A known cost in the hook, not ours to change: while RED EYE is up without a loaded MPC_ReShow (any stock build,
  like Christmas's stock v0 with its row), giant_lookup calls find_by_path, which walks every object, every 2 s with
  no cap (mpc_lookup stops after 30 tries). Unmeasured on device. A per-stage retry cap would be the Dino session's
  change.
- Stale after the change, left alone (outside the two approved lines): the comment on g_gHasGiant at :2514 ("the Dino
  Stage's"), "the button: Dino only" at :3011, and the "[GIANT] ready: MPC_DinoGiant" log line, which will print that
  name on RED EYE.

**Full bake restarted (the user picked "Full 4096").**
- 12:48:58: run_re_stage.sh with no flags, in the background. It waited for the GPU lock, held by the Thanksgiving
  session's hm_stage.py since 12:44:37 (its Blender held 3.1 GB). Free commit at launch: 6.6 GB of 36.9 GB;
  RelicCardinal was no longer among the top memory users.

**v0 built and staged (13:01), dry-run pushed (13:04), NOT pushed.**
- Full bake 12:52-13:00. It took the GPU lock after the Thanksgiving bake; Blender ran 472 s. T_ReHall 4096 (121 s),
  T_ReStage 4096 at 96 spp (129 s), T_ReFloor 4096 (172 s), T_ReAirfield 2048 (26 s). Free commit stayed 6.4-8.1 GB,
  so wait_commit never waited.
- cook_redeye.sh all: build ok in 30 s (yaw 180, 10 actors + 2 lamps). Cook "Success - 0 error(s), 3 warning(s)"; the
  3 are the console-variable notices of the fast run. Chunk 59: 27 entries, all under Mods/RedEye. Pak 44,987,798 B,
  md5 f68eb4fc0c7344d8bda42384bc9c9445.
- Staged: C:\Users\Chris\TribeUE\paks_current\staging\re_v0_20261017\pakchunk59-Android_ASTC_P.pak (md5 checked).
- Previews: claudedocs/redeye_v0/ (re_v0_sheet.jpg + 7 views, JPG only like christmas_v0).
- The look is as after the fast-bake fixes, with one composition flaw. From the DJ spot (dj_front), the hanging
  wing's trailing edge hides the top third of the inner RED EYE sign over the door (it reads "REU EYE"). Fix it in the
  next bake by moving the wing; its shadow is baked into the floor, so it isn't a pak-only change. The crowd view's
  "grey panel" is the wing seen from below at its flat (18, 18, 20), as designed.
- Push dry run, OBB_WORK=D:\TribeUE\MetaRedEye\obb_work. It needs its own folder: the default paks_current/work is
  shared, and the script rm -rf's it. Live OBB cae836af (pushed 10-12 09:50; chunks 50, 53, 54, 55) + chunk 59 ->
  merged 513,518,362 B, md5 933238b8958561c74c6bf2f2f737180a. Nothing pushed.
- Headset, read only: combo3 installed (base.apk a156adfc, installed 2026-10-16 19:10:56). envs.txt has 4 boxes
  (Dino Stage, Dino Classic, Reactor, Graveyard Shift), combo3's maximum, so a RED EYE line is ignored until combo8
  (EM_MAX 8) is installed. Tribe was not running. The repo adb (37.0.1) and the SDK adb (30.0.5) both speak server
  protocol 41, so mixing them restarts no server.

**v0 PUSHED 18:51 (the user's go: "Push, swap Dino Classic").** The question was asked ~13:06 and answered ~18:50.
- push_obb.sh --push (OBB_WORK on D:, no --env). The live OBB was still cae836af at the pull. Merged 513,518,362 B,
  md5 395dbe6e42ab11db6b831c221678ab9a (the dry run's 933238b8 differs only in zip timestamps); the device md5
  matches; "PUSHED OK". The paks_current mirror (patch_live.obb, paks/, paks.txt) was updated by the script.
- Re-read at 18:51 before the swap: still combo3 (a156adfc), envs.txt unchanged and equal to the backup (a49cd219),
  Tribe closed.
- envs.txt box 2 swapped: "Dino Classic=/Game/Mods/DinoAnim/Maps/Environment_Dino" ->
  "RED EYE=/Game/Mods/RedEye/Maps/Environment_RedEye" (LF, 4 lines; pushed via /data/local/tmp like push_obb.sh).
  Device md5 185787683cfef61bae3068f2cfd33826, and backup/tribemod_20261006/envs.txt got the same file: reseed.sh
  restores envs.txt from there.
- TO DO once combo8 (8 boxes) is installed: put the Dino Classic line back, as a 5th line, on the headset and in
  the backup.
- First look in the headset: pending. Paks mount at Tribe's launch.
- 18:5x, tribe-hack-57 (Harvest): their push (the user's `!` line, not yet run) makes "Harvest Moon" line 5 of
  envs.txt, and they will copy the 5-line file into the backup. They also re-checked this push: OBB 395dbe6e =
  mirror, envs 18578768 = backup. So when Dino Classic comes back: re-read the headset's envs.txt, APPEND the line
  (line 6 if Harvest's has landed), never rewrite the file, then copy the result into backup/tribemod_20261006.
- 19:03-19:04, tribe-hack-20 (Reactor), on the user's "just push all of it" in that chat:
  - combo8 installed (base.apk 7d6a9051, lastUpdateTime 19:03:27, firstInstallTime unchanged, so an update);
  - OBB 395dbe6e -> 1a384762 (Reactor v9, chunk 55 2f7df8cf; Harvest v1, chunk 57 981356dd; 59 still f68eb4fc);
  - envs.txt d28abb42: Dino Stage, RED EYE, Reactor, Graveyard Shift, Harvest Moon, Dino Classic (box 6).
  Read back from this chat at 19:06: the device, the backup and the paks_current mirror all agree. The Dino Classic
  TO DO is done; nothing was appended from here.
- With combo8 live, the hook's "redeye" row is live too. RED EYE v0 has no MPC_ReShow, so while RED EYE is up expect
  "[GIANT] no show collection for stage folder 'redeye' (MPC_ReShow): no light show" in the log about every 30 s
  (every 15th lookup) and a full object walk every 2 s.

## 2026-10-17 evening: v1, the show (the user, after the first look at v0: "looks pretty good, where is all the lasers and the crowd?")

The first look went well; the lasers and the crowd were never in v0 (phase 0 = the building). v1 brings them forward:
the plan's phase-1 rig and lasers, the show, and the phase-3 crowd, on MIDTOWN v1's pipeline (copied, never edited).

**New or changed files (nothing shared edited):**
- `Blender/redeye/re_show.py`: T_ReCues, 32 bars at 140 BPM. Rows: stage, wash, lenses, frame, uplights, signs,
  airfield, rabbit, wing, always. Bar 15 is the blackout: only the RED EYE signs, the wing's red edge and the airfield.
  No strobes, no wash pulses.
- `Blender/redeye/re_lasers.py`: the Dino show's laser motion (show.py, read-only) with RED EYE's 12 colour schemes:
  blood red, cold white, violet, ember, and one green section. A check refuses any hue outside red..violet, the green,
  or white.
- `re_stage.py` v1:
  - one glow mesh per show row (8);
  - 24 moving heads, 4 per light truss, on the Dino mover engine;
  - 30 laser units: 14 lip (group 6), 6 crown (group 0), 10 under the wing (groups 1-4, so the TOP look shows them),
    solved against the set and verified;
  - the wing raised 13 -> 15 m: from the DJ spot its trailing edge hid the top of the inner door sign;
  - the lip's static aperture glows are gone (SM_ReLasers carries animated ones);
  - the crowd hook (crowd/re_crowd.py);
  - --dry now solves and verifies the lasers too (8 s, no GPU).
- **Laser solver lesson:** its swept check cuts a beam at the nearest CORNER of the face it crosses. The v0 hall's
  118 m skin quads, and above all the purlins (one 118 m tube each) and the 110 m crane rails, cut the crown's beams to
  13.5 m and the lip's to ~22 m. Splitting them rib to rib (SEG_YS) fixed it. The two inner crown units now fan outward
  (7 beams, smaller sweep), because the cranes' trolleys hang over the centre. Result: 140 beams, 10 dropped,
  0 problems, closest pass 5.3 m from the DJ's head (limit 4.9).
- `Scripts/re_materials.py`: xm_materials.py copied with checked replacements. RED EYE rows; CROWD_FLOOR 0.2 (MIDTOWN
  0.25).
- `Scripts/build_redeye.py`: the animated path (RE_ANIM=1), with MPC_ReShow at 22 scalars and **no Height**. Since
  combo8, Height alone would arm the lift on RED EYE; the hook still finds 18 of its 19 names, so the show bus runs.
  - The hall, stage and floor follow the wash row (floors 0.35 / 0.3 / 0.3).
  - The glow rows run on cue_tex. The signs flicker 0.03.
  - The frame's bands scroll up (chase KZ -1/160, one per bar). The rabbit runs out along the approach every 2 s
    (KY 1/24000, Sharp 12).
  - The movers and lasers run on the Dino engines; the crowd on the VAT.
- Gates:
  - `re_cuecheck.py`: xm_cuecheck's model of RED EYE's materials.
  - `re_overdraw.py`, `run_blender_locked.sh`.
  - `ship_re.sh`: bake -> lasers -> comfort -> overdraw -> unreal (animated) -> shader archive -> stage. It never
    pushes.

**Fast run (scratchpad re_v1fast, no crowd):**
- Bake 22 s, 22 meshes, 60,256 tris.
- Comfort PASS: no strobes, <= 3 flashes/s (the lasers' 3.0 is the Dino engine's own), every rise >= 4 frames, beat
  pulse 1.43x.
- Overdraw from the DJ 0.27 layers/px (budget 2.5; MIDTOWN 0.33).
- The crowd module is being built by a builder subagent (`redeye-crowd`) in Blender/redeye/crowd/.

**20:01, v1 (show only, no crowd) shipped clean and STAGED; the user then said "just do all of it. we'll push at the
end and ill make my comments on what needs changed at the very end".** So every phase of the plan gets built, with one
push at the end on the user's OK.
- v1: all gates passed at full quality (140 beams 0 problems 5.3 m, comfort PASS, overdraw 0.27, cook 0 errors with the
  chunk-59 shader archive). Staged at `paks_current/staging/re_20261017_2001/`, pak 46,656,730 B, md5 95296b6c. Not
  pushed; the user chose to push once at the end.
- Builders (subagents, their own folders, the GPU lock, a commit check; no adb):
  - `redeye-crowd`: crowd/re_crowd.py.
  - `redeye-gremlin`: scripts/gremlin_build.py, skins/heads gremlin.glb.
  - `redeye-visuals`: D:\TribeUE\Visuals\redeye, 8 loops x 2 variants + the sting + the hour set.
  - `redeye-intro`: intro/re_intro_path.py, intro.redeye.txt, drone_path.redeye.txt, re_dronecheck.py.

**v2 (phase 2 and the rest), built in re_stage.py / re_materials.py / build_redeye.py:**
- **The crane flight** (giant.py's recipe; the Dino lift on RED EYE through combo8's row):
  - SM_ReLift + SM_ReLiftGlow: the plate (3 mm over the riser), a pendant with the cap at G_BTN (0, 1.52, 1.06), red edge
    strips; dino_materials.giant_lift / giant_glow unchanged.
  - SM_ReRobe: re_materials.re_robe, giant_robe copied with the hem at max(0, Height - 1.8 m) on a narrower, ragged
    hem (decision 5).
  - SM_ReHook: crane 1's hook (moved out of SM_ReStage). It comes down to 2.8 m over the head, the hoist cables
    stretch, two lines run to the shoulders by RobeOn (hook_lines).
  - The follow spot: a SpotLight actor `DinoGiantSpotLight` under the light truss at y -32, aimed at the DJ. It is
    34 m out, about Dino's 32 m, so the hook's fixed 6000 cd gives Dino's light.
  - MPC_ReShow now carries Height: 23 scalars.
- **The mask:** skullbuck_head.glb (out/headtest), 14,205 -> 6k tris, a relief 6.8 x 2.2 x 8 m.
  - The plan's 10 m skull under crane 2 would have hidden the frame's top and cut the crown's lasers. Instead it hangs
    on 2 chains from the roof at y 7 (between crane 2 and the frame), parked at z 18-26, dark.
  - It drops 15.5 m by smoothstep(Height / 545) (mask_drop), lit by the wash once down.
  - Eye glows burn while it hangs. The eye beams (10) show on TopLasers x Bass and rise at 70 degrees: the DJ flies
    between the mask and the crowd, so 56 degrees passed 4.1 m from their head. verify_mask_beams = 5.0 m OK; ship_re
    gates on it.
- **The doors:** SM_ReDoors, the 8 leaves moved out of SM_ReHall. door_roll slides them by UV1.x (world cm travel) x
  (1 - DoorOpen); shut they tile x +-24, the centre pair meeting at x 0.
- **Other pieces:**
  - flames: 16 cards on the outer 8 heads, T_ReFlame. flame_card bursts on the half-time beat in the drop (new
    flames row) and on HitMajor.
  - haze: SM_ReHaze, one sheet over the crowd at z 12.5 + field fog on the apron; fog_sheet copied from hw_materials,
    with a new haze row.
  - the beacon: 2 beams turning at 12 rpm on the tower (beacon_spin).
  - the landing jet: SM_ReLander, 22 s every 16 min on the runway (lander_path).
  - the intro's rider: SM_ReJet, actor `ReJet`, hidden and parked at z -50 m, nose -Y in Blender.
  - the intro switch: SM_ReSwitch at (1.0, 0.25, 0.85), intro_button colours, with a guard bracket in SM_ReStage.
- **Walking map:** WALK recorded where built.
  - It covers the deck, the riser with its steps, new side stairs off both deck sides down to the floor beside the
    stage, round the barrier's ends into the crowd, the hall, the door piers, and the apron with its jet, masts and
    windsock.
  - intro/re_collide.py (xm_collide copied) on the dry run: 25 floors, 51 walls, 2 spots; walk OK, backstage reaches
    the decks, the crowd and the apron, 30,582 m2.
- push_redeye.sh written: a dry run by default, push_midtown.sh's flow with our own OBB_WORK on D:.
- Budget so far: 35 meshes, 69.5k tris (+ the crowd ~370k); actors 35 + crowd 2 + 2 lamps + the spot = 40, the
  plan's cap.

**20:16-20:40: the crowd lands, and the fast end-to-end ship passes with everything in.**
- `redeye-crowd` delivered crowd/re_crowd.py, built in 8.7 s, review sheet `Scripts/Blender/redeye/crowd/
  crowd_review_sheet.jpg`. Same contract as xm_crowd.
  - 3,935 people = 3,922 + 13 on shoulders.
  - 343,740 tris: near 174 people / 152,922, mid 460 / 118,350, far 3,301 / 72,468.
  - VAT 2048x1024.
  - Density 3.15/m2 at the barrier, 0.21 by the doors.
  - GREMLIN ears 6.4%, pilot caps + aviator helmets 4.2%, skull masks 1.7%.
  - Totems: gremlin heads with glowing eyes, paper planes, RED EYE signs, flags. Glow is only red/white glowsticks and
    cold phones.
  - It found and fixed crowd3's clap-through-hats bug in our copy: clap -> hands-up under crowned headwear, and filmers
    / totem holders take the ears off. The bug is also in MIDTOWN's and Graveyard's copies; tribe-hack-28 was told
    (FYI, not touched).
- Fast ship (scratchpad re_v2fastc):
  - bake with the crowd;
  - lasers 140/0 problems/5.3 m; mask beams 5.0 m OK;
  - walking map 4,015 lines (3,935 dancers, 189,520 B, under the hook's 512 KiB), walk OK;
  - Unreal: crowd VAT 2048x1024 28 frames/clip; UV5 VatPivot reads back right (100% of the roots on the floor);
    30 meshes on our materials; 37 actors + 2 lamps + the giant spot;
  - cook "Success - 0 error(s)", 0 material compile failures, chunk 59 manifest 99 entries with its shader archive;
    fast pak 53.5 MB.
- **Two gate catches, both fixed:**
  - re_cuecheck failed the flames: a 36% one-frame jump. At a section's first burst, the cue's 60 ms ramp times the
    burst's own 60 ms ramp makes a steep quadratic. FLAME_RISE_S = 0.12 (re_materials; the check reads it): now 2.0
    flashes/s, attack 6.8 frames, max 24%.
  - re_overdraw read 0.00 everywhere: it imports every FBX where it was built, and the intro's jet is built at the
    origin round the DJ (in game it is parked 50 m down, hidden). It now skips SM_ReJet and SM_ReRobe and counts the
    eye beams, flames, haze and beacon as translucent: DJ 0.51 layers/px (budget 2.5).
- 20:40: the full ship (ship_re.sh, crowd in) started.

**21:0x: the intro, the drone reel and GREMLIN delivered.**
- `redeye-intro` delivered:
  - files: intro/re_intro_path.py (the ride's single source; ~30 checks on the hook's own spline, ported from
    intro_ride.h, matching tests/intro_ride_test.cpp to 0.001 cm), intro.redeye.txt (463 keys), drone_path.redeye.txt
    (10 shots, 122 s), re_dronecheck.py (xm_dronecheck + RED EYE keep-outs: the mask's drop, the doors, sky <= 440 m,
    the hook's 8191 B / 40-shot limits);
  - the plan: claudedocs/redeye_v1/intro_plan.png;
  - the ride:
    - press 1: a clockwise hold round the airfield, r 220 m, z 38, 29 m/s;
    - press 2: round the tower, touchdown at (0, -241) at 20 m/s; camhold 85.41 s on the shut doors and the sign; the
      jet taxis out of frame and hides at the cargo jet's stand;
    - press 3: the wide shot (0, -26, 3.2), hold 2 s, DoorOpen over 6 s;
  - the parse: "parse ok, 463 keys, ... 0 lines not understood". The reel passes re_dronecheck, including against
    SM_ReCrowd.
- Its points, and what I did:
  - gear legs added to the jet (mains f -0.5 r +-1.5, nose f +5.5);
  - the outdoor rows (SM_ReGlow, SM_ReSigns, SM_ReAirGlow, SM_ReRabbit) take show=False variants of cue_tex /
    chase_tex (re_materials: cue_level(show=False)), so press 1's blackout (ShowLevel 0) leaves the airfield lit;
  - lander_path hides the 16-minute landing jet while IntroStep is 1-2;
  - the stand stays the cargo jet's (the last 13 s are out of the held frame).
- **The switch moved BACKSTAGE**, to (-6, 13, 0) on a pedestal behind the screen; backstage spot (-6, 12.3, DECK_Z,
  yaw 90). The intro builder found that at the booth the camera returns to its mount the moment the music starts
  (intro.cpp: atDecks), so the stream never saw the doors open. A backstage button is also the user's own idea from
  Graveyard. The walk check reaches the decks, the crowd and the apron from there. To be confirmed by the user at the
  end; it's a one-constant change back.
- ship_re.sh gained step 2c: re_intro_path.py writes <out>/intro.redeye.txt with its checks, and re_dronecheck runs on
  the reel and the ride (--intro). It stages both texts.
- `redeye-gremlin` delivered:
  - skins/gremlin.glb (md5 57731386, 36,801 tris) and heads/gremlin.glb (md5 8f288613, 10,996 tris, the blur-disc
    propeller);
  - check_skin LOADS + MOVES. The head's "no skin" is expected, as for horseman/santa;
  - sheets: claudedocs/redeye_v1/gremlin_review_sheet.jpg, gremlin_pose_sheet.jpg;
  - the fallback head (opaque blades, no disc) at Scripts/Blender/redeye/gremlin_fallback/gremlin_head_noblur.glb
    (md5 20bf1812). It would ship as heads/gremlin.glb if the disc's see-through fails on the device;
  - open on device: the blur disc (BLEND), the emissive eyes, the ears in the selfie at < 0.65 m.

## 2026-10-17 23:00: the final ship's memory wait timed out; re-armed without it

- The wait for 7 GB of free commit gave up after 90 min ("last 3 GB"). Nothing ran; nothing was staged.
- What changed since the 4096 bake crashes:
  - C: has 162 GB free (it was 98% full);
  - the page file is system-managed (AutomaticManagedPagefile True) and has grown from 7 GB to 12.3 GB;
  - the commit limit went from 43 to 44 GB during the wait.
  So Windows now grows the page file on demand. Free commit hovers near 3 GB under load, and a fixed "wait for 7 GB"
  could never be met. The bake keeps its own wait_commit(2.5 GB, max 180 s) before each 4096 texture.
- The real wait is the GPU lock. The visuals builder renders its finals one lock per piece. The team's protocol (the
  kit's gpu_lock.sh) takes the lock only after it has been free for 45 s, so Halloween's waiting renders go first;
  Halloween has the GPU's priority until 10-31. run_re_stage.sh and run_blender_locked.sh now yield the same way. A
  scaled test (45 s -> 2 s) passed both cases: a free lock is taken after the yield; a lock re-taken during the yield
  is waited for.
- 23:05 final ship re-armed (ship_re.sh, all steps). The sources changed after the 20:50 bake (re_stage.py 21:16,
  re_materials.py 21:17, build_redeye.py 21:18, the intro 21:28), so it re-bakes in full.

## 2026-10-17 23:54: the final ship, STAGED (not pushed)

- ship_re.sh, all steps, 23:04-23:54. Every gate passed:
  - bake 742 s; lasers 140 beams, 0 problems, closest 5.3 m to the DJ's head; mask beams 5.0 m;
  - walking map 25 floors, 51 boxes, 3,935 dancers, 2 spots (189,527 B); backstage reaches the decks, crowd and apron;
  - intro PASS (463 keys, 20,275 B, md5 9625c3c5 = the builder's); drone reel AND the intro ride PASS against the
    jet with its new gear (the first run of that check);
  - comfort PASS; overdraw 0.51 layers/px (DJ), 0.52 (DJ in VR);
  - UE: 37 actors + 2 lamps + the spot; cook 0 errors, 3 engine console-variable warnings (not content); chunk 59
    101 entries with the ShaderArchive; 212 files packed.
- Staged: C:\Users\Chris\TribeUE\paks_current\staging\re_20261017_2354:
  pak 100,123,298 B md5 a9ec0b21; redeye_collide.txt d3154b69; intro.redeye.txt 9625c3c5;
  drone_path.redeye.txt c3b8f9c7.
- Sheet: claudedocs/redeye_final/re_final_sheet.jpg (+ the 9 views). Same as v2 where nothing changed (the flight
  pose checked at full size: identical). The previews show the lasers static and white (shader states).
- push_redeye.sh dry run 23:56: the local half OK (the pak, the 3 texts, skins/heads gremlin.glb 57731386 /
  8f288613); stopped at "headset not connected over adb" (adb devices: empty). The OBB merge dry run waits for the
  headset.
- Memory: the page file grew 12.3 -> 15.4 GB during the ship (commit limit 44 -> 47 GB); the bake ran from ~3 GB free.
- The loop pack at 23:56: 3 of 18 delivered (both stings, Red Eye cold); Red Eye blood failed its red-flash gate and
  is being redone; ~15 min of GPU per 8-bar loop, so ~4 h to go, then the hour set.
- 00:13 (10-18): the loop pack stalled on the shared GPU lock. The holder is the Harvest session's look-dev, bash PID 27792
  ("scripts/lookdev.sh moonrise gold --pct 50 --samples 8", started 21:38). It has held gpu.lock.d since 23:50:33 and
  harvest_blender.lock.d since 23:27:21.
  - It is orphaned: its parent 22280 is gone. It has no children, no Blender, and its _work folder was never made, so it
    hangs right after gpu_lock.sh's "acquired" echo.
  - Its owner, tribe-hack-57 (Harvest Moon), was told. Not touched: it's another session's process. The fix, theirs or
    the user's call: a plain kill of 27792, so its trap frees both locks.
- 00:16: cleared by tribe-hack-57. A plain kill ended 27792, but its trap didn't release the locks, so the owner removed
  gpu.lock.d and harvest_blender.lock.d by hand. At 00:16:27 the GPU lock was free and the RED EYE queues were back in
  line for it.

## 2026-10-18 03:50: the loop pack DONE; everything is built (not pushed)

- redeye-visuals delivered 03:06: 16 loops + 2 stings + the hour set in D:\TribeUE\Visuals\redeye\deliver (19 files,
  3,169,647,057 B). Its gates: check_loop 0 flashes/s and 0 one-frame hits, and flashcheck --red-max 1 (red at most
  1/s, 0 red one-frame hits), on all 18 pieces and on the whole hour; set_check PASS.
- Checked here 03:47:
  - ffprobe on all 19: H.264 High 1920x1080 bt709 30/1, no audio. Loops 411 frames (13.70 s), stings 206 (6.87 s), the
    set 108,000 (3600.000 s). The sizes match the builder's list, and the set's md5 00d4772d matches too.
  - The timeline: 76 segments, 2100 bars, 6 acts of 352 bars (Last Call 340). The set opens on Red Eye (blood) for 64
    bars, then the sting; a sting opens acts 2-6. Every loop plays 3 to 5 times (Gremlins blood 3).
- Sheets:
  - claudedocs/redeye_v1/loops_sheet.jpg (the finals) and loops_lookdev_sheet.jpg;
  - D:\TribeUE\Visuals\redeye\renders\finals_set_sheet.jpg (the hour, one frame every 2 min).
  - The set sheet shows Red Eye closed in 5 of its 7 Red Eye frames. Those frames fall on bar lines, and the eye shuts
    fully at loop bars 0 and 4 (it squints on the other downbeats). A strip every 1/4 bar shows it open the rest of
    the time.
- The builder changed four looks to pass the red rule, and Radar's variants are green + blood:
  - Red Eye's per-bar blink is now a squint;
  - Flameout is the intake view, and its ring flares on the kick only;
  - Gremlins does 2 slow twists, and the popped bolt darkens in flight;
  - Hangar Doors blood has near-black leaves.
- The weakest looks, in the builder's words: Gremlins (procedural claws seen from above; the blood version is red on
  red), then Hangar Doors.
- GPU, the builder's count: 163.5 min.
- At 03:46 no bash, Blender or ffmpeg was running, and the GPU lock was free.
- push_redeye.sh: the preflight now checks the headset's room: the live OBB + the new pak + the media + 2 GB spare. It
  stops a --push and warns on a dry run. Mock-tested on 5 cases (room, short on a dry run, short on a push,
  unreadable, no media).
  - Dry run with --media at 03:48: the local half is OK (pak a9ec0b21, the 3 texts, GREMLIN, 19 videos 3.0 GB). The
    headset is not on adb.
- THE PUSH: one push, on the user's OK, with the headset on adb and Tribe closed:
  bash /c/Users/Chris/TribeUE/TribeXR/Scripts/Blender/redeye/push_redeye.sh --push --media /d/TribeUE/Visuals/redeye/deliver /c/Users/Chris/TribeUE/paks_current/staging/re_20261017_2354
  - Then ask the Dino chat, through the user, to add the 3 texts to reseed.sh's restore list and "gremlin" to
    KEEP_SKINS.

## 2026-10-18 10:10: the clap through the flying goggles (MIDTOWN's check): fixed in the source, NOT shipped

- tribe-hack-28 (MIDTOWN) checked every frame of all 17 clips, with the arms and the headwear skinned. Its counts
  matched ours (bucket 32 edges, beanie and cap 2 each) and found one gap: in the near tier the clap cuts 4 arm edges
  through the flying goggles.
  - Cap + clap was already swapped (HAT_CLIP_SWAP), so only hatless goggle wearers are hit.
  - Its dump of seed 11, recounted here: 7 people wear goggles (all near, hat None or cap); 2 of them are hatless +
    clap.
  - Our preview's arm check never saw it, because its WEAR list left the goggles out.
- The fix: re_crowd.py build_people now ends with a pass that swaps clap -> handsup for anyone wearing the goggles,
  after the last random draw.
  - A first try swapped inside make_person, as for the hats, and it reshuffled the whole crowd: 3,935 -> 3,934 people,
    every look different. A "together" group member whose clip no longer matches the group's skips its timing draw
    (the rng.gauss under `if pr["clip"] == clip`), and that shifts the random stream for everyone after it.
    (My first note here said the stream was safe because clap and handsup share _timing's branch. That was wrong.)
- Verified 10:15, with copies of MIDTOWN's people_dump.py + compare_people.py (build_crowd2(Random(11)), as
  re_stage.py calls it):
  - a copy with the fix reverted reproduces MIDTOWN's pre-fix dump exactly (md5 443bb970, 3,935 people), and the
    builds are deterministic;
  - the fixed code: 3,935 people, the costume counts as shipped (129/41/51); no field differs except 2 near-tier,
    hatless dancers going clap -> handsup; MIDTOWN's measured clashes go 2 -> 0;
  - the preview (--no-render): wearing clashes none; goggles vs arms: only the clap (4 edges), never worn together.
- re_crowd_preview.py:
  - the audit counts "clap through the flying goggles";
  - the arm check measures the goggles: WEAR + "goggles"; a tier without them gets no BVH; the clap is ruled out the
    way the hats' swaps are.
- Not re-shipped. The staged final (re_20261017_2354) keeps the 2 dancers; the fix goes out with the next ship, after
  the user's notes.

## 2026-10-18 11:06: PUSHED (the user's "push" in this chat)

- push_redeye.sh --push --media, 11:05:31-11:09:57, exit 0:
  - preflight: 20,074 MB free on the headset; the push needed 5,808 MB. The installed build is combo9 (2c747dd9),
    with RED EYE's show row and lift. envs.txt has 7 boxes (RED EYE is box 2, Midtown the 7th) and was not changed.
  - OBB: the live OBB (672,937,069 B, md5 0971dd30) + chunk 59 -> 728,072,569 B, md5 19b1ad51; the device's md5
    matches the merge. It holds chunks 50, 53, 54, 55, 57, 58 and 59, and is mirrored to paks_current (paks.txt).
  - tribemod, each md5 on the headset = local: redeye_collide.txt d3154b69, intro.redeye.txt 9625c3c5,
    drone_path.redeye.txt c3b8f9c7, skins/gremlin.glb 57731386, heads/gremlin.glb 8f288613.
  - backup/tribemod_20261006: envs.txt (the headset's, 7 boxes) and the 3 texts.
  - media: /sdcard/Movies/RED EYE Visuals, 19 pushed, each md5-checked, 0 failed.
- Skins on the headset: gremlin, horseman, lampwing, santa, skullbuck. That's 5; the avatar menu takes up to 8
  (SM_MAX).
- Coordination: Reactor (tribe-hack-20) was told before and after. The Halloween chat's ship_hw.sh was running at the
  same time, without --push (a dry run).
- Still to do:
  - reseed.sh (not ours): the 3 texts in the restore list and "gremlin" in KEEP_SKINS, through the user;
  - the first-launch check (the show bus, the lift, GREMLIN);
  - the user's notes.
- 11:11: Reactor (tribe-hack-20) added the 3 texts to reseed.sh's restore list and "gremlin" to KEEP_SKINS, on the
  user's "tell them all yes or whatever" in its chat. Checked here:
  - md5 3c9384d6, bash -n OK;
  - the names are inside the restore loop, and the backups are present.
  It also re-checked the push on the headset: OBB 19b1ad51, and the texts and GREMLIN match. Halloween pushed chunk 54
  after us, from 11:11; push_obb.sh merges, so chunk 59 stays.
- 2026-10-18 17:12: first-launch check (logcat; Tribe pid 21270, 16:47:33-17:06:14). The user: "ok i loaded red eye.
  looks pretty decent! we have some things to change though".
  - Route: Harvest Moon (auto-applied) -> Midtown -> GREMLIN (16:50:05) -> RED EYE (16:50:46, IN after 1 s), ~15 min
    there, then the user closed Tribe at 17:06 (player stop, rendering off, RIPC shutdown). No Fatal signal, no
    tombstone; the 1,445 "SIGSEGV" matches are MessageExecutionMonitor's warning text, present in other launches too.
  - Show bus: bound 16:50:59 with all 19 parameters (no "missing" line). The line says "ready: MPC_DinoGiant 0x..."
    only because dumper.cpp:2583's text is fixed; for RED EYE the object is MPC_ReShow (the "redeye" SHOWS row).
    "[GIANT] no show collection for stage folder 'redeye'" at 17:06:14 is the first miss after the level unloaded
    during the quit (the environment list went away at 17:06:11): harmless.
  - Crane: up at 16:53:54 (545 cm, 44 s), down at 16:54:39 (60 s), landed 16:55:39, "show restarts at the drop".
  - GREMLIN: skin + head loaded (clicked twice, 16:50:05 and 16:50:15). Auto takeoff 17:01:42: orbit, boo to the
    selfie-stick lens, RETURN, ON at 17:02:08.
  - Intro: ready (ReJet, IntroStep, DoorOpen found), never started: the backstage switch wasn't pressed.
  - Walking map: 25 floors, 51 boxes, 3,935 people. Drone path: 10 shots, 122 s, flying.
  - Songs: grids locked; laser variants 6, 0, 5, 3, 0; drop booms fired.
  - Frame rate on RED EYE: 92 ten-second windows (15.3 min), avg 71.0 fps (target 72), lowest window 61.4 (the
    load), 5.0% of frames over 20 ms, 7 windows with a frame over 100 ms (400 ms at the load; 279, 238, 224 ms, the
    last in the 10 s before the head's takeoff). Today's other launches: Harvest Moon 4.0%, Midtown 1.6%, stock 0.7%.
  - Next: the user's notes.

## v3: the user's notes (2026-10-18, after the first visit)
- Verbatim: "ok so i dont need the crane at all and no button. the lazers at the top of the visuals are pointing up for
  some reason, they need to be pointing at the crowd. the selfie camera shots needs to be all inside of the hanger or at
  least on the outside looking in. thats it. like the outside one is just at the edge of wehn the roof ends." Then,
  mid-build: "also the screen has to be WAY bigger than it is now. also we dont need that outline around the screen".
- Read as:
  - "no button" = the crane's pendant button (the lift's G_BTN). The intro's backstage switch stays, flagged to the user.
  - The mask goes with the crane: it only came down during a flight (smoothstep(Height / 545)); parked it sat near
    black in the roof. Without Height it would never show.
  - "pointing up" was by design, not a bug: v2 aimed the crown (6 units on the LED frame's header) at z 30, 60 m out,
    "rising onto the roof ribs".
  - The drone shot at the roof's edge = v2's shot 9 (y -94 -> -104, at the door line, looking out at the runway).
    Shots 1 and 10 start outside but look in (allowed).
- Built (scripts backed up first: Scripts/Blender/redeye/backup_v2_20261018, md5s re_stage 91e67480, build_redeye
  e7c4cfc9, re_materials ce36c944, ship_re 07b58095, re_intro_path 85bde37a, drone_path c3b8f9c7):
  - re_stage.py: no cranes, lift (plate + pendant), robe, hook, mask. The top spot (bake light) is the stage roof
    truss's centre head. Screen 32 x 18 m at y 9.2, foot 2.3 m up (z 2.3-20.3; the walk from backstage passes under
    it), no LED frame (glow, body, FrameRim lights).
  - re_stage.py, continued: the crown's 6 units move to the screen's top edge (x +-2.5/7.5/12.5, z 20.75), 9 beams
    each, aimed at (x, -36, floor). The stage roof truss goes up to z 20.9 (x +-20.25, 11 heads): at 15.9 the crowd
    saw it cross the screen. The line arrays go out to x +-19.5. Walk boxes: the screen 2.0-20.6 m up, no pendant, no
    frame columns.
  - First dry run at a 22 deg aim: every crown beam was cut at the first light truss (y -8, z 15.3-15.7) by its
    tilt-up pose. The aim at y -36 (27 deg) clears it: 54/54 crown beams reach the floor (54-63 m).
  - Dry run totals: 154 beams, 0 dropped; verification 0 problems; the DJ's head 5.3 m from the nearest laser (a lip
    unit, as v2).
  - build_redeye.py: NOT_YET = ("Height",), so MPC_ReShow has 18 of the hook's 19 names and the hook runs RED EYE
    show-only (g_gHasGiant needs Height; the button and the song lift= keys need the giant). No hook change.
  - build_redeye.py, continued: purge_stale() deletes the old level and v2's stale assets (6 meshes, 6 MIs,
    6 materials, T_ReMask, and the frame's SM_ReFrame, MI_ReFrame, MI_ReFrameChase). The chunk label cooks the whole
    folder, and the old materials read Height. The giant spot actor and the lift/robe/hook/mask material branches are
    gone.
  - re_materials.py: re_robe, hook_lines, _lift_s, mask_drop, mask_beams and their constants are removed.
  - Checks:
    - re_dronecheck: no mask keep-out;
    - re_overdraw: no SM_ReMaskBeams;
    - ship_re.sh: no mask-beam gate;
    - re_intro_path: the switch check is now its distance from the decks (13.5 m; there's no lift button), and the plot
      has the new screen and no cranes.
  - drone_path.redeye.txt: shot 9 is now over the crowd under the wing (y -44 -> -40, z 2.5 m), looking at the stage
    with the crown's fans coming down ahead. Shot 8 runs up beside the screen. The header comments are updated.
  - Pre-ship checks: walk OK (backstage reaches the decks under the screen, the crowd and the apron; 30,605 m2);
    intro PASS, intro.redeye.txt byte-identical to v2's.
- Gotcha: the patch's Path.write_text wrote CRLF on Windows (the scripts are LF). It was caught by a diff and converted
  back before any run that mattered. Write bytes or use newline="\n".
- The crowd's goggles post-pass (10:10) ships in this build.
- Expected hook lines on the next visit:
  - "[GIANT] MPC_ReShow: 18/19 parameters (missing: Height)";
  - "[GIANT] show bus: MPC_ReShow 0x... (gen N), 18/19 parameters: the light show runs here, no giant intro".
- 17:51-18:11: ship_re.sh (full), exit 0. STAGED in paks_current/staging/re_20261018_1811, NOT pushed:
  - files: pak 98,226,179 B md5 cbd6d7d1; drone_path.redeye.txt 872930fb; intro.redeye.txt 9625c3c5 (unchanged);
    redeye_collide.txt 37fcd461.
  - bake: 729 s.
  - lasers: 154 beams, 0 dropped; verification 0 problems; DJ 5.3 m.
  - crowd: 3,935 people (the goggles post-pass).
  - walking map: OK (backstage -> decks under the screen).
  - intro: PASS.
  - drone: PASS (no segment through or near the set, no hidden views; the intro ride clears).
  - comfort: PASS.
  - overdraw: DJ 0.60 layers/px (v2 0.51; budget 2.5).
  - UE: "stale v2 assets removed: 22"; MPC_ReShow 22 scalars, no Height; 30 actors + 2 lamps; cook 0 errors (3
    engine console warnings); chunk manifest 85 entries, shader archive 1, no lift/mask/robe/hook/frame entries.
  - Renders: claudedocs/redeye_v3/. The crown fans land in the crowd; from the DJ they come over the head into the
    crowd. No cranes. The screen fills the DJ's backward view (preview_dj_back is all screen, black in the bake).
  - Next: the user's OK to push (push_redeye.sh --push on the staged dir; Tribe closed). Then on the next visit:
    "[GIANT] show bus: MPC_ReShow ... 18/19 parameters" and the new drone shot 9.
- 18:15-18:16: PUSHED v3 on the user's "push" in this chat (Reactor, tribe-hack-20, told before and after):
  push_redeye.sh --push re_20261018_1811, exit 0.
  - Preflight: 15,336 MB free on the headset; combo9 installed; envs.txt 7 boxes (RED EYE box 2, unchanged).
  - OBB: 7312c013 (Harvest v3's) + chunk 59 -> 794,141,856 B, md5 c96295be; the device's md5 matches; chunks 50, 53, 54,
    55, 57, 58 unchanged; paks_current mirrored.
  - tribemod, md5-checked: redeye_collide.txt 37fcd461, intro.redeye.txt 9625c3c5, drone_path.redeye.txt 872930fb,
    skins/heads gremlin.glb unchanged (57731386 / 8f288613).
  - backup/tribemod_20261006: envs.txt + the 3 texts (match). reseed.sh (a45750b5) already lists the texts and gremlin.
  - Next: the user relaunches Tribe and opens RED EYE. Check the log for "[GIANT] MPC_ReShow: 18/19 parameters (missing:
    Height)", "show bus: MPC_ReShow ... no giant intro", the drone path (10 shots), and [PERF] against the 17:12
    numbers (71.0 fps, 5.0% frames over 20 ms).
- 18:17: Reactor (tribe-hack-20) checked the push from its side:
  - headset OBB c96295be = paks_current/patch_live.obb;
  - the zip's own list has all 7 paks, 59 = cbd6d7d1;
  - the 3 texts on the headset match backup/tribemod_20261006; envs.txt unchanged (c16d5102);
  - reseed.sh's PATCH= mirror now restores v3;
  - Tribe not running.
- ~19:45: the user, after a look: "in the selfi camera view, there is 2 views i dont like. i dont like when the view is
  looking at the hanging part at the bottom and the very large shot from the outside. dont confused that with the one
  shot from the outside that is right outside of the hanger".
  - Read as v3's shot 2 (under the wing, looking at its underside) and shot 10 (the hangar from the apron, 100-140 m
    out). Shot 1 (from 60 m out, flying in through the doors) stays.
  - v3.1 reel: both cut, the rest renumbered; 8 shots, 98 s, 1,901 B, md5 4c2cdd90. re_dronecheck PASS against the
    v3 set (out_re/check_drone_v31.log). It's only the text file: no pak, no rebuild. The hook reads it when RED EYE
    loads.
  - Not pushed: adb sees no device since ~19:50 (a logcat read hung waiting for it; stopped, no orphan adb client).
    Next: the user's OK + the headset connected, then put() the file through /data/local/tmp, copy it into
    backup/tribemod_20261006, and read the visit's log.
- 2026-10-19 ~10:00: v3 visit log (10-18 19:32-19:47): "[GIANT] MPC_ReShow: 18/19 parameters (missing: Height)", show
  bus up, no giant; drone ran v3's 10 shots; 70.5 fps, 4.9% frames > 20 ms (v2 71.0 / 5.0%). PUSHED v3.1 reel
  (4c2cdd90) on the user's "push": headset md5 matches, copied into backup/tribemod_20261006.
- 2026-10-22 v4 (the user: "add a lot ... to the stage where im standing", the table "too narrow" + "a little longer too.
  to fit the decks", "speakers all through out the stage pointed at the crowd"): TABLE 3.5 x 0.9 m (x -1.8..1.7, y
  -0.4..0.5, top 0.74) with a RED EYE plate; 10 ground stacks (x +-7/11/15/19/22.6, y -1.8, 2 subs + 2 tops), riser
  side-fills (x +-3.7), 2 wedges, delay hangs on the y -32/-58 trusses (x +-10), amp racks + flight cases backstage;
  walk boxes for all (68). Backup backup_v3_20261022. ship_re.sh 17:15-17:36 all gates PASS (lasers 0 problems, walk,
  intro, drone, comfort, overdraw DJ 0.60, cook 0 errors); staged re_20261022_1736; renders claudedocs/redeye_v4.
  Not pushed (waits for the user's OK).
- 17:37-17:38 PUSHED v4 on the user's "ok push it": OBB ce16dd5c (merged, device md5 matches), chunk 59 4fd69e22, texts md5-checked (collide 1be140a8), backups updated; installed build combo12.
