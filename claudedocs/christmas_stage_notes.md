# MIDTOWN (Christmas stage) — running log

The plan is `christmas_stage_plan.md`. NOTES.md belongs to the Dino session; this file is the Christmas session's.

## 2026-10-16

- The user asked for a Christmas stage and character idea.
  - Round 1: SILENT NIGHT + Krampus. The user answered "hmm more ideas".
  - Round 2 offered five pairings. The user picked **2: MIDTOWN + the Animatronic Santa** ("ohhhhh i really like 2").
- Concept blockout: `TribeUE\TribeXR\Scripts\Blender\christmas\concept_blockout.py`.
  - Run: `run_concept.sh` (shared GPU lock) and `sheet.py`.
  - 9 views in 16 s, 197k faces, 3,120 people.
  - Renders + sheet are in `claudedocs/christmas_concept/`.
  - The user: **"looks good to me"**.
- Layout choice: the tree stands BEHIND the billboard (y 27) so it never covers the visuals. The round-2 pitch had it
  the other way round.
- Blockout lessons:
  - **Snow cubes:** a cube near a camera renders as a big white tile, so keep flakes 8 m from every camera. In the
    real stage, snow is sheets, not particles.
  - **Haze beams:** near a camera they read as wide slabs. Lower alpha (0.022) helps.
  - **Window cells:** a world-space shader with ~8% lit at strength 1.5 reads as "3 a.m.". The shipped stage needs a
    baked atlas instead.
  - **Edit tool:** a file rewritten by a script must be Read again before Edit.
- The user's correction: Christmas is **not held until Oct 31**. It runs in parallel with the Halloween session (shared
  GPU lock; pushes still need the user's OK).
- Read in the hook (for the plan, sections 4 and 10):
  - **Found by the stage's folder name:**
    - walking map: club.cpp:12-13, 120;
    - drone reel: dumper.cpp:1945-1948;
    - intro file: intro.cpp:97.
  - **Hard-coded, so Midtown needs another session's change:**
    - the show bus collection is a 3-row table (dumper.cpp:2538-2546), so Midtown needs a `"christmas"` row;
    - EM_MAX is 4 (dumper.cpp:2166);
    - the side-screen mirroring runs on the club's map only (club.cpp:291).
- A peer message from the Reactor session (tribe-hack-20): combo4 = combo3 + club.cpp 748faaac (its side screens mirror
  the main screen). It is not installed. Any APK we build must start from club.cpp 748faaac, and we tell them before
  installing.

## 2026-10-16 evening: phase 0 started (the user: "go for it")

**New files** (nothing shared edited):
- **`Scripts\Blender\christmas\xm_stage.py`**: the generator, v0. It is hw_stage.v0's pipeline (Cycles bake, glow
  palette, the screen's UV layout, FBX export, previews), copied and adapted.
  - Frame: FINAL Tribe coordinates (riser top 0, deck -1, street FIELD_Z = -2.5, as Dino and Graveyard). The concept had
    the street at -1.5.
  - **City + tower on a tiling window texture** (T_XmCityTile, 4x4 cells of 3.2 m x 3.6 m): crisp and cheap.
    - Lit windows are glow quads on exactly the same cell grid (`lit_windows`).
    - Roofs and trims sample a wall pixel (WALL_UV).
    - 426 buildings, ~16k lit windows (8% near, 6% far, more on street floors), all within CITY_R = 400 m of the
      480 m sky.
  - **Baked:** tree (2048), store (2048), deck (2048), street (4096), ground (4096, position-based asphalt / paving /
    snow).
  - **Flat:** the el.
  - **Static art:** the side billboards (T_XmBillboard).
  - **Screen:** SM_DinoVisualScreen with the Dino v7.1 UVs.
- **`run_xm_stage.sh`**: the generator under the GPU lock; XM_OUT overrides out_xm.
- **`Scripts\build_christmas.py`**: build_halloween.py's stock path.
  - Unlit MICs of Tribe's glTFRuntime parents.
  - NoCollision on every actor.
  - PAL_Christmas -> chunk 58.
  - XmDeckLamp_L/R.
  - Level /Game/Mods/Christmas/Maps/Environment_Christmas.
- **`D:\TribeUE\MetaXmas\TribeXR`**: the project copy, 9.6 MB (uproject, Config, Build, Plugins, Binaries,
  Scripts/pack_chunk.sh + make_obb.py from MetaHw). Config and uproject are identical to MetaHw's.
  - `Scripts\cook_christmas.sh [build|cook|pack|all]` writes logs to D:\TribeUE\MetaXmas\logs.

**Fast pipeline test (scratchpad xm_fast):**
- Generator: 36 s, 95k tris.
- UE build: ok; screen centre y = -1030 cm -> yaw 180, tree 59.5 m tall at y -2724 cm before the turn.
- Cook: "Success - 0 error(s), 3 warning(s)" (the same engine cvar notes as Graveyard and the club) in 21 s with the
  warm shared shader cache. The plan's "37 min first cook" estimate was wrong: the DDC is shared.
- Chunk 58 manifest: 36 entries, all under Content\Mods\Christmas (map, 13 MIs, 13 meshes, 9 textures; no stubs, no
  engine content, no shader archive). Pak 15.0 MB (fast textures).

**Look fixes from the fast previews:**
- **City walls:** at 0.030 linear they read medium grey, not 3 a.m. Now wall 0.012, glass ~0.004, sill 0.018 (Graveyard's
  stone reads at ~0.027).
- **Store displays:** dimmed to (0.60, 0.36, 0.18).
- **Street and ground:** exposure 5.0 and 4.5 (were 6.0); snow albedo 0.22.

**Headset:** not on adb at 21:10. Last known live OBB (paks_current/paks.txt, 2026-10-12 09:50): 50, 53, 54 (Graveyard
v7), 55 (Reactor v8).
- Pushing chunk 58 needs: the headset on adb, Tribe closed, a menu slot (EM_MAX 4 is full), and the user's OK.
- envs.txt is restored by reseed.sh's ENVBK copy (the Dino session's), so the Midtown line must go there too.

**Finding the dumper.cpp owner (the user: "your gonna have to find that chat"):**
- Memory names the Dino/environment session tribe-hack-f1. It was not running at 21:10.
- The running peers were tribe-hack-20 (Reactor), tribe-hack-57 and tribe-hack-0c.
- Both 57 and 0c got the full request: EM_MAX 4 -> 8 at dumper.cpp:2166, and a "christmas" SHOWS row for
  /Game/Mods/Christmas/MaterialInstances/MPC_XmShow.MPC_XmShow at dumper.cpp:2538.
- **tribe-hack-0c: not the owner.** It is the new RED EYE session (a hangar stage with a GREMLIN character,
  /Game/Mods/RedEye, **chunk 59**). EM_MAX 8 covers it too.
- **Chunk claims:** 56 Big Dub, 57 Thanksgiving (pitch), 58 MIDTOWN, 59 RED EYE.
- **tribe-hack-57: not the owner either.** It is the Thanksgiving session (HARVEST MOON + MAJOR TOM): /Game/Mods/Harvest,
  MPC_HmShow, chunk 57. It also needs a menu box and a SHOWS row later.
- So **no running chat owns dumper.cpp** (21:13): the Dino session is closed. Four stages now wait on EM_MAX > 4:
  MIDTOWN, RED EYE, Thanksgiving, Big Dub.
- push_obb.sh's `--env` refuses a 5th menu line by design (it mirrors EM_MAX 4). It needs the same raise when EM_MAX
  moves.

**The Dino chat, reopened** (the user: "you can reopen it thats fine"):
- It is session 2c3e1a91 (named tribe-hack-b4 in its last run, last active 19:41).
- Resumed in the background: `claude --bg --resume 2c3e1a91... --permission-mode auto` with a request scoped to code
  edits only (no build, sign, install, push or re-seed).
- The user can open it with `claude attach 2c3e1a91`, or end it with `claude stop 2c3e1a91`.

What it did (its report; the lines checked here with Grep, the md5s not):
- **dumper.cpp 2616d9fc -> 7752cd1d5:** `#define EM_MAX 8` (:2166); the "christmas" SHOWS row (:2542); the loop bound
  sizeof-based (:2544).
- **push_obb.sh 8380cf1f -> 6c70d1ab:** 8 boxes (:108-109, comment :16).
- **Its safety read:** every EM_MAX array is guarded; g_emW has 32 slots; boxes past 4 have never run on the device; and
  Tribe's list layout with 8 extra boxes is unknown (expect scrolling).

**Tribe's auto-mode classifier then denied my next Bash call: [Create Unsafe Agents].** Starting a background session in
auto mode counts as creating an unsafe agent here.
- Lesson: don't launch Claude sessions (claude --bg / -p) from this session. Ask the user to reopen a chat themselves.

The Reactor session (tribe-hack-20) was told that combo4 was built from the old dumper.cpp and must be rebuilt before any
install.

**combo5** (Reactor session, its report):
- Contents: combo4 + the 8-box menu + MIDTOWN's SHOWS row.
- Sources: dumper.cpp 7752cd1d (EM_MAX 8, the christmas row and the sizeof bound checked by Reactor); club.cpp 748faaac;
  head.cpp 6bfa9ead; intro.cpp 3f8f77dc; club_collide.h 83ab550e; gait.h ea05eff4; intro_ride.h 6c711050.
- Compile: 0 errors, the same 7 warnings. libhook_combo5.so is 390,552 B, md5 3c25a799, and carries "MPC_XmShow".
- APK: `out/hookA/combo5.aligned.apk`, 112,123,119 B, md5 2bee4163e689775088a52b6312600a57. libUnreal.so is unchanged
  (915c3130).
- **Not installed:** the headset was off USB, and the install waits for the user's OK in the Reactor chat. It replaces
  combo4 (045188e2), which was never installed as far as Reactor knows.
- After the install, Reactor checks the "[ENV] added box" and "[CLUB] side screens" lines, then sets reseed.sh MOD=combo5.

## 2026-10-17: v0 built (the user: "go")

**Full bake** (out_xm, finished 2026-10-16 21:18): 500 s, 94,886 tris, 13 meshes, 9 textures, 7 previews.

**`cook_christmas.sh all`** (09:41-09:43):
- **Build:** 0 errors. Textures at full size: ground and street 4096², sky 4096x2048, tree/store/deck 2048². 13 meshes;
  PAL_Christmas -> chunk 58; screen y -1030 cm -> yaw 180; tree 59.5 m; saved 13 actors + 2 deck lamps.
- **Cook:** "Success - 0 error(s), 3 warning(s)" (the same engine cvar notes); 48 s commandlet, 62 s step.
- **Chunk 58 manifest:** 36 entries, 0 outside Mods/Christmas.
- **Cooked sizes:** a 4096² texture is 9.96 MB of .ubulk, which matches ASTC 6x6 with full mips (4096²/36 x 16 B x 4/3 =
  9.94 MB), so mip 0 ships. The largest mesh is SM_XmGlow, 8.8 MB cooked (the lit windows and bulbs); SM_XmCity 2.3 MB.
- **Pak:** 79 files, 47,237,662 B, md5 09ae2ab36b7cfa8b9ea77be31f1aca7c; V11, uncompressed, mount ../../../, no shader
  library, nothing outside Mods/Christmas (repak list).
- **Staged:** `C:\Users\Chris\TribeUE\paks_current\staging\xm_v0_20261017\pakchunk58-Android_ASTC_P.pak` (md5 checked).
  The `v3..v7_*` folders next to it are Graveyard's.
- **Previews + sheet:** `claudedocs/christmas_v0/` (xm_v0_sheet.jpg + one JPG per view).

**v0 look notes for v1 (from the previews):**
- Bake grain on the store facade and the near crowd barriers (store, crowd and dj_front views). It needs more bake
  samples or a denoise on the close surfaces.
- The snowy sidewalk on the store side reads bright in the store view. Check it in the headset before changing it.
- No light show on v0: MPC_XmShow does not exist yet. The hook logs "[GIANT] no show collection for stage folder
  'christmas' (MPC_XmShow): no light show" and skips (dumper.cpp giant_lookup, read 2026-10-17).

**Headset (read-only, 09:45):** on adb (2G0YC1ZF96072F); Tribe not running.
- Installed: **combo3** (base.apk md5 a156adfc). firstInstallTime = lastUpdateTime = 2026-10-16 19:10:56: a fresh install,
  most likely the Dino session's re-seed.
- **combo5 is NOT installed.**
- Live OBB md5 cae836af (= paks.txt, unchanged since 2026-10-12).
- envs.txt has the 4 boxes; the reseed backup envs.txt is the same 4.
- reseed.sh MOD=combo3, PATCH=paks_current/patch_live.obb.

**Push dry run** (`OBB_WORK=<scratchpad>`, no push):
- The merged OBB is 50, 53, 54, 55 unchanged + 58 added; 515,768,226 B, md5 6ae3e0c1d69dc5810568148636c45215. Work dir
  deleted afterwards.
- **On combo3 a 5th envs.txt line is ignored:** the loader reads `while(n<EM_MAX&&fgets(...))` (dumper.cpp:3543;
  current source; the Dino session's diff only changed the define, the SHOWS row and the SHOWS bound). So pushing before
  combo5 is harmless; the Midtown box shows once combo5 is in.
- push_obb.sh's --env writes only the headset's envs.txt. After a push, copy it to
  backup/tribemod_20261006/envs.txt (no re-seed running) so a re-seed keeps the box. PATCH= already follows the mirror.

## 2026-10-17: the user: "why dont we finish everything first?"

**Decision:** no v0 push. Build every phase of the plan first, then push once. The device-only checks (fps with the crowd
and lasers, the 5th menu box, the show bus, the head flight with the Santa skin) wait for that push, so every piece is
held to the budgets Graveyard measured on the device.

**Mapped (read-only explorers, 4 of 5 reports in):**
- Video loops: the Reactor kit is the template. Its assemble_set.py needs about 11 or more distinct loops (10-minute
  no-repeat rule), so 3 variants x 8 concepts. C: is 98% full, so the pack goes to `D:\TribeUE\Visuals\christmas\`.
- Crowd, walking map, intro, drone:
  - The intro runs only when MPC_XmShow exists with at least 6 of the hook's 19 names, so the animated build comes
    first.
  - The intro moves one actor (the rider), toggles 4 and writes IntroStep/DoorOpen.
  - The walking map is all-or-nothing: one bad line, or over 4,608 persons, rejects the whole file.
- Unreal show build:
  - hw_materials copies the Dino functions and reads a 32-row cue table; dm.cue_level (movers, lasers) reads 16 rows.
  - MPC_HwShow has 23 scalars and none of the club's dimmer names.
  - Hook sections: SL_BAR0 {0,16,0,8,16,24,28,0}; the blackout bar is 15.
- Character: horseman_build.py is the template. Its input breeches.glb lives in %TEMP%\claude\sb, so copy it somewhere
  lasting. The head file name must equal the skin file name.

**Bake grain fixed in xm_stage.py:** a new `denoise()` (OIDN through the compositor of an empty scene; a linear EXR
round trip) is on by default in `bake()`. The ground drops from 128 spp + blur 4 to 64 spp + OIDN.
- Tested on v0's T_XmStore.png: 11 s at 2048 px; edges kept, grain gone.
- `--fast` run passed (51 s): mean linear changed -1% to -6% at 4 spp.

**Side screens: combo6** (Reactor session, on my request):
- club.cpp 748faaac -> fc5a5dfe; :292 now also allows `christmas_collide.txt`.
- out/hookA/combo6.aligned.apk md5 0ca580ec9e39c58f2841e8e2b2477796 = combo5 + that line (verified here).
- **Not installed:** it waits for the user's OK in the Reactor chat.
- MIDTOWN side: the billboards must be one actor with mesh `SM_ClubSideScreens` (material 0 swapped to the main screen's
  material while the visuals are on).

**Re-seed list (pending):** reseed.sh (Dino session; that chat is closed) needs christmas_collide.txt, intro.christmas.txt,
drone_path.christmas.txt on lines 87-88 and `santa` in KEEP_SKINS. Raise it when the user reopens the Dino chat, before
any MIDTOWN push.

**Video loops delegated:** a builder subagent `midtown-visuals` builds the kit copy, 9 scene scripts and look-dev for all
27 pieces in D:\TribeUE\Visuals\christmas, then stops for review before the finals.

## 2026-10-17 (continued): v1 build in progress (the animated stage)

**Step 1, glow by show row + the animated Unreal path (verified):**
- `xm_stage.py`: glow split into 14 meshes, one per show row (`glow_row()`). The side billboards are now ONE mesh
  `SM_ClubSideScreens` in the main screen's UV layout, 16:9, idle art `T_XmSideIdle`.
- New tables:
  - `xm_show.py` T_XmCues: 32 bars x 20 rows (stage, wash, search, lenses, windows, tree, star, lamps, marquee,
    signals, candy, crown, always, snow, steam, displays, neon, festoon, sky, train). Sections follow the hook's
    SL_BAR0: bar 15 = the power cut.
  - `xm_lasers.py` T_XmLaser*: the Dino's motion patterns with 12 Christmas colour schemes (red / gold / green /
    white; a check refuses any hue outside red..green).
- `Scripts\xm_materials.py`: hw_materials copied + MIDTOWN's factories (lit_glide, chase_tex, windows_wake, tree_lights,
  star_glow, signal_blink, sign_sparkle, sky_glow, search_sweep, movers, train_cross, snow_sprites, steam_card).
- `build_christmas.py` XM_ANIM=1: MPC_XmShow with Graveyard's exact 23 names (none of the club's dimmers).
- **Fast animated cook:** "Success - 0 error(s)", no material compile failures, chunk 58 carries its
  ShaderArchive-TribeXR_Chunk58-SF_VULKAN_ES31_ANDROID. One fix: the Power node's pin is "Exp".

**Step 2, the rig (fast run):**
- 22 moving heads on the Dino mover engine (8 header, 6 front truss, 8 gantries); beams 7.6..42 m, solved over the
  sweep.
- 4 sweeping searchlights (data pre-flipped).
- Lasers: 18 units, 161 beams in the engine's 9 groups:
  - fan = the billboard's top bar;
  - horns = 4 rooftop units across the canyon (30-140 m);
  - towers = sky lasers from the tower;
  - lip = 6 deck units;
  - mouth = the star's gold fan (82-187 m);
  - delay = 4 gantry units.
- **Laser verification: 0 problems, closest pass 6.4 m from the DJ's head** (limit 4.9).
- Fix: the billboard unit's beams were 8 m (blocked by the front truss), so it now sits on the header truss and aims
  flatter.

**Step 3, the set pieces:**
- el train as its own mesh: crosses every 4 min in 60 s, parked under the street between;
- ~9,000 snow flakes as camera-facing sprites (instead of the plan's sheets: far less overdraw, faded near any camera);
- steam cards on the 4 stacks;
- silhouette dioramas in the 5 lit store windows (elves, nutcrackers, teddies, a toy train, a rocking horse, gifts).

**Step 5, intro + walking map + drone reel (written):**
- `intro/xm_intro_path.py`:
  - press 1: the city's power goes down and Santa does a 70-s lap of the dark tree, the camera ahead on his right with
    the tree behind him;
  - press 2: he peels off, climbs NEW plaza stairs onto the deck, walks past the billboard, climbs the riser and stops
    at the decks;
  - press 3: wide shot; DoorOpen 0 -> 1 over 8 s lights the tree tier by tier, then the star.
  - Checks pass: seam 0.7 degrees, turns <= 7 degrees, truss clearance 0.72 m, 14.5 m from the tree's axis.
- **The tree moved from y 27 to y 33:** its lowest tier (r 14.2) overhung the deck's back edge, so no walk could circle
  it. It is still centred behind the billboard.
- New geometry:
  - the plaza stairs (8 steps) and deck-front stairs (6) with a gap in the barricades: free roam into the crowd;
  - the tree-lighting plunger backstage (`SM_XmButton`, intro_button colours);
  - xm_stage records every walk floor and wall where it builds them (`walk_field.json`), so
    `intro/xm_collide.py` can't drift from the set. It checks the hook's caps and a BFS walk check.
- `intro/drone_path.christmas.txt`: 10 shots, about 114 s. Checker: `xm_dronecheck.py` (orbit height = the mod's
  30 cm).

**Gates:**
- `xm_cuecheck.py`: PASS on the fast output. It found and fixed two issues:
  - The show clock (Time + ShowOffset) JUMPS when a song loops a section, so every continuous phase (chases, the tree's
    climb, breathing, sweeps) now runs on plain Time; only cue levels and the beat pulse follow the song.
  - A single window waking at the drop rose in 2 frames: now 3.8.
- `xm_overdraw.py`, `run_blender_locked.sh`, `ship_xm.sh`: the full gate chain. It stages, never pushes.

**Delegated:** `midtown-visuals` (loops), `santa-skin` (skin + head), `midtown-crowd` (the Christmas crowd module).

**11:40, the gate chain passes end to end (`ship_xm.sh --fast`, scratchpad xm_v1fast):**
- bake 121,672 tris, 35 meshes;
- lasers 161 beams, 0 problems, the closest 6.4 m from the DJ;
- comfort PASS;
- overdraw: the DJ 0.33 layers/px (budget 2.5), the stream camera 0.57;
- drone reel PASS: 10 shots, 114 s, closest 1.6 m. The first run caught 3 bad shots: through a gantry's delay speaker,
  a look point inside the tree, and a shot through a festoon and a block;
- walking map OK: 31 floors, 44 walls, 11,412 m2, backstage -> decks / crowd / plaza;
- intro OK;
- Unreal animated build + cook "Success - 0 error(s)", shader archive in chunk 58, pak 18.0 MB (fast textures).
- Fix found by the cook gate: M_XmSnow and M_XmSteam failed to translate for Android. They sampled the linear DATA
  textures (T_XmFlake, T_XmSteamNoise) through Color samplers; now Linear Color.

**The intro's walking Santa (`intro/xm_rider.py`)**, tested with skullbuck.glb standing in for skins/santa.glb:
- the procedural animatronic march: swing axes found by test turns, 8 eased segments per stride, 1 stride/s at 1.6 m/s;
- the ue_decode check passes (0.12 mm);
- the night bake is written;
- KEEP 0.4 -> 0.22 (a 2048x512 VAT = 8 MB for one actor was too much).
- Fix: Decimate moved BEFORE the Armature modifier; after it, the collapse followed the pose and the vertex count changed
  per frame (the topology check refused it).
- `ship_xm.sh` step 1b runs the export after the bake (the bake clears the folder) and skips it while skins/santa.glb is
  missing.

**Crowd integration** in xm_stage.py (build_the_crowd, mat_crowd, the 4096 bake without OIDN, pose_preview,
`walk_people.json` with ABSOLUTE feet z). It waits for `crowd/xm_crowd.py` (the midtown-crowd builder).

**`push_midtown.sh`** (written, NOT run): a dry run by default. With `--push`, after the user's OK:
- preflight: Tribe closed, warns unless combo6 is installed;
- push_obb.sh --push --env Midtown;
- the three tribemod texts + the Santa skin and head through /data/local/tmp, md5-checked;
- copies into backup/tribemod_20261006;
- optional `--media` push of the loops;
- prints the reseed.sh request for the Dino chat.

**The Christmas crowd (`crowd/xm_crowd.py`, by the midtown-crowd builder; crowd3 copied, Graveyard untouched):**
- 4,202 people (4,188 field + 14 on shoulders), 366,566 tris (Graveyard 334,120: the avenue packs the same people into
  less area, so the near tier has 140); VAT 2048x1024, the layout and six UV channels of Graveyard v7.
- Dark coats, ugly sweaters, scarves, mittens; Santa suits, elves, reindeer, 3 inflatable Santas; Santa hats 20.8%
  (some with light-up pompoms), elf hats, antlers, beanies, holly; glowsticks in red, green, white and gold.
- Its decisions: crowd3's zombie "lurch" and Thriller "claw" swapped for "shuffle" and "heart" (edit `CLIPS` to revert);
  people in Santa or elf hats never clap (the clap put their hands 3 cm into the hat); a FOH keep-out.
- It fixed three crowd3 bugs in its copy (buns and ponytails through hats, the hairline through beanies, feet on the
  curb). The Dino and Graveyard crowds still have them.

**12:22, the integrated fast run passes with the crowd and the walking Santa (`ship_xm.sh --fast`):**
- the walking map: 4,202 dancers + 31 floors + 44 boxes (201,936 bytes), under the 4,608 cap; the walk check OK;
- drone reel PASS; the crowd is now the closest object on 3 shots (1.42 m at the least, over the sidewalk crowd; the check
  uses the rest pose, so raised arms take about 0.3 m off that);
- overdraw unchanged (the crowd is opaque); comfort PASS;
- Unreal: the crowd's VatPivot reads back right (100% of the roots in the avenue); M_XmCrowdVAT, M_XmCrowdGlowVAT and
  M_XmRiderVAT compile for the Quest; cook "Success - 0 error(s)" (the 3 warnings are engine console notices);
- pak 66.9 MB with the fast textures (Graveyard's live pak is 181 MB).

**12:37, v1 built at full quality and STAGED (`ship_xm.sh`, 14 min; NOT pushed):**
- `C:\Users\Chris\TribeUE\paks_current\staging\xm_20261017_1237\`:
  - pakchunk58-Android_ASTC_P.pak 109,054,877 B, md5 5789312c8b665cbc77943e6c52accce1 (chunk 58 manifest 110 entries,
    the shader archive in it);
  - christmas_collide.txt b3f32d2f (201,936 B), intro.christmas.txt d10ca742, drone_path.christmas.txt 1afd7c06.
- Every gate passed: lasers 161 beams, 0 problems, 6.4 m from the DJ; comfort PASS; overdraw DJ 0.32 layers/px; drone
  reel PASS; walking map OK with 4,202 dancers; intro OK; cook "Success - 0 error(s)".
- The bake took 10 min. The crowd atlas (4096 px, 128 spp) has output mean 0.002, the same as Graveyard v7's working
  bake (v6's black bake read 0.000).
- Previews: `claudedocs/christmas_v1/` (7 views + `xm_v1_sheet.jpg`).
- `push_midtown.sh` dry run: the six files check out locally (pak, 3 texts, skins/santa.glb f0b35316, heads/santa.glb
  1fcd5d46); it stopped at "headset not connected over adb", so the OBB-merge half runs at push time.

**14:33, the loop pack's look-dev passed (midtown-visuals builder, `D:\TribeUE\Visuals\christmas`):**
- 27 pieces = 8 loops + the MIDTOWN sting, in 3 colour variants each: candy (red/white), frost (cold white/blue),
  gilded (gold).
  - Tree Lighting, Skyline Wake, Subway Rush, Candy Cane Tunnel, Gift Wrap, Workshop Glitch (the Santa on a CCTV feed,
    "CAM 03 / WORKSHOP / DEC 24 03 00"), Neon Reindeer (wire reindeer on a rooftop, no red nose), Snowstorm.
- Every look-dev passes the kit's gates: 0 flashes/s, 0 one-frame hits, seamless loops, mean frame .036-.147 (Gift Wrap
  is the brightest).
- Six pieces have motion hooks rather than light pulses (kick ratio ~1.00). I accepted that.
- Approval sheets: `claudedocs/christmas_v1/loops_approval_*.jpg` (copies of renders\approval\).
- Kit bugs fixed in its copies only:
  - lookdev.sh / make_loop.sh wiped their work folder before taking the GPU lock;
  - assemble_set.py had a hard-coded opener and a ValueError crash.
- 14:35: I approved the look-dev; finals + the hour set are running: queue_finals.sh ASSEMBLE=1, about 2-3 h of GPU.

**The staged texts, checked with the hook's own parsers** (MSVC builds of the repo's tests, in my scratchpad; no repo
file changed):
- `tests/intro_ride_test.cpp` (hook/intro_ride.h) on intro.christmas.txt: "parse ok, 387 keys (seam key 279), loop
  0.00..69.79 s, exit to 96.55 s, camhold 78.79 s, 0 lines not understood"; rider XmRider, step IntroStep, door DoorOpen
  8.0 s; speed 1.53..1.65 m/s.
- `tests/club_collide_test.cpp` (hook/club_collide.h) on christmas_collide.txt: "parse ok: 31 floors, 44 boxes, 4202
  people, 2 spots, 0 bad lines". Its host-side flood fill then stops with "state table full": the TEST's table is sized
  for the Dino field (1M states at 10 cm) and MIDTOWN walks 11,412 m2. The hook has no such table; xm_collide.py's 20 cm
  BFS is the walk check.
- The hook's SHOWS row (dumper.cpp:2542) names `/Game/Mods/Christmas/MaterialInstances/MPC_XmShow.MPC_XmShow`, the path
  the build saves and the cook ships.
- Snow sprites, by derivation (no device yet): each flake is built facing -Y with u right / v up, the material re-flips
  V for the import and expands the corners in view space (UE view = X right, Y up), so the sprites face the camera and
  are not culled. First thing to look at on the device.
- Avatar menu: SM_MAX 8 skin boxes (dumper.cpp:2075); a re-seed keeps lampwing, skullbuck, horseman, so santa is the 4th.

**17:39, the 27 loop finals are delivered** (`D:\TribeUE\Visuals\christmas\deliver\Loops\`, midtown-visuals):
- Builder's report: all 27 pass both gates at full res (frames + seam, then the MP4); 0 flashes, 0 one-frame hits; Neon
  Reindeer passed under --mblur with no change (largest step 5.83 / 5.97 / 5.45 vs max 6.07 / 6.21 / 5.62). GPU: 27
  finals 113.8 min; look-dev + stills 58.8 min; 172.6 min in all. Mid-frame sheet `renders\finals_loops_sheet.jpg`.
- Read back here: 24 loops (411 frames = 13.70 s, 8 bars at 140) + 3 stings (206 frames, 4 bars); all H.264 High,
  1920x1080, 30 fps, yuv420p tv-range BT.709, no audio, about 15.9 Mbit/s, 13.5-27.6 MB each (~680 MB in all).
- **My own comfort check** (scratchpad `flashcheck.py`, written from the rules, not from check_loop.py). It counts WCAG
  general flashes (swings >= 0.1 relative luminance, darker end < 0.8) and red flashes (320*max(0,R-G-B) swings >= 20
  with a saturated-red end), on 60-px blocks in sliding 480-px windows at 25% area. It also finds one-frame spikes or
  dips, applies the project caps (120-px block <= 0.65 luma, frame mean <= 0.5) and measures the loop wrap step.
  - Proved first on synthetic clips. A 5 Hz strobe fails (5/s), 2 Hz passes, a 1-frame pop fails (77% of a window), a
    5 Hz red strobe fails (red 5/s), a 0.5 Hz fade passes, and a ramp's wrap pop reads x28.8.
  - Two bugs in my first draft, caught by those clips. The zigzag's extremes slid along flat stretches, so the 1-frame
    pop was missed; and red was zeroed below the 0.8 ratio, which made toggling at the cutoff look like swings.
- **26/27 pass everything**:
  - every file is under the caps (block max 0.571, Workshop Glitch; frame mean max 0.245, Gift Wrap frost);
  - general flashes at most 2/s, red at most 1/s;
  - every wrap step is at most x0.75 of the largest inner step. The stings read x1.14-1.30, but on steps of 0.0005-0.0007
    (keyframe noise on a near-still frame).
- **Gift Wrap (candy) is borderline, on a stricter red rule I added.**
  - It is within WCAG (red 1/s, general 2/s) and the kit's luma one-frame rule (largest 22% of a window, under 25%).
  - It has 3 single-frame red pops per pass (frames 152, 358, 391/393; largest 28% of a window, about 3% of the
    screen). The tartan boxes slam in, or jolt at an accent, so the saturated red sweeps a region for one frame (5.9 ->
    40.9 -> 0.0).
  - Frost and gilded have the same motion with no red: clean. The set plays candy 3 times (16:27, 26:31, 46:38, 27 s
    each).
  - My call: keep it and tell the user; skipping that file, or re-rendering it with the slam softened, is theirs to ask.
- The set's timeline (`00 FULL 1-HOUR SET - Midtown Visuals - timeline.txt`), read back:
  - 76 segments, contiguous, ending at 3600.00 s (2100 bars);
  - all 27 files used; six ~10-min sections (Midnight, Rush Hour, Blackout, Snowfall, Toy Riot, Last Train);
  - no two variants of one loop back to back;
  - no file starts again within 10 min: the closest is 603 s start-to-start (521 s end-to-start).

**The hook build to install for MIDTOWN is now combo8, not combo6** (club_venue_notes.md:755):
- combo8 (12:49) = dumper.cpp 3476d016 + club.cpp fc5a5dfe. out/hookA/combo8.aligned.apk md5 7d6a9051, lib 6c5271a2;
  it supersedes combo6 and combo7 for installing.
- Each lib was checked for MIDTOWN's strings:
  - combo6, combo7 and combo8 have MPC_XmShow, the "christmas" row and christmas_collide.txt (club.cpp:292's side
    screens);
  - combo5 has the row but not the side screens.
- `push_midtown.sh` preflight now finds the out/hookA build whose APK md5 matches the installed one, checks that build's
  libhook for those strings, and names the newest qualifying build in its warning. Before, it accepted only combo6's md5.
  - A local test caught my first version splitting the repo path at its space.
  - Then tested on combo3 (warns, names combo8), combo8 (passes) and an unknown md5 (warns).

**17:51, `push_midtown.sh` dry run with the headset connected**: the OBB-merge half now tested.
- Preflight: the six local files' md5s are as staged. Tribe was not running. Installed build combo3 (a156adfc): warned.
  The headset's envs.txt has 4 boxes (Dino Stage, Dino Classic, Reactor, Graveyard Shift), so Midtown would be the 5th.
- The live OBB pulled as cae836af (468,530,388 B), the 2026-10-12 push: no one has pushed since. Its 4 paks match
  paks_current/paks.txt.
- Chunk 58 was added; the merged OBB is 577,585,441 B, md5 a7c2c023, stored, comment "      2304". Nothing was written.
- Headset storage: 23 GB free of 103 GB. Movies has Dino Visuals 2.9 GB, Reactor Visuals 3.4 GB (its hour set 2.7 GB)
  and Halloween Visuals 220 MB. MIDTOWN adds about 4 GB (the loops, the set and the OBB swap).

**18:51, RED EYE pushed chunk 59** (tribe-hack-0c, on the user's go); read back here at 18:53:
- The live OBB is 395dbe6e (paks_current/paks.txt: chunks 50, 53, 54, 55 + 59 at 44,987,798 B; previous cae836af).
- The 17:51 dry-run merge is history. A real `push_midtown.sh --push` re-pulls, so it merges 6 paks and keeps chunk 59.
  The merged OBB will be about 622.6 MB, not 577.6.
- Headset envs.txt: Dino Stage, RED EYE, Reactor, Graveyard Shift. RED EYE replaced Dino Classic as box 2, the user's
  pick while combo3 shows only 4 boxes. backup/tribemod_20261006/envs.txt matches it (md5 18578768).
- After the combo8 install, RED EYE puts Dino Classic back as a 5th line. Midtown is then the 5th or 6th box, depending
  on order; push_obb.sh refuses only a 9th.

**18:28, the hour set is done** (`D:\TribeUE\Visuals\christmas\deliver\00 FULL 1-HOUR SET - Midtown Visuals.mp4`):
- The queue log says "set DONE ... 108000 frames in 49.2 min (36.6 fps)", then "queue end". The builder's waiter
  didn't wake it, so I nudged it at ~19:10 for set_check, the set-level comfort pass, the contact sheet and the report.
- ffprobe here: 2,698,523,719 B, md5 5efc23ab; H.264 High 1080p30 tv/bt709; 108,000 frames = 3600.000 s; video only;
  6.0 Mbit/s (Reactor's set on the headset is 2.7 GB too).
- **My set check** (scratchpad `vcheck/setcheck.py` + flashcheck.py):
  - content: 5 samples per segment matched against all 27 loops' frames (16x9 RGB). 374/380 land on the timeline's
    file within 2 frames of phase (median distance 0.0004). The 6 misses are the 90% samples of the 6 sting segments,
    which sit inside the dissolve into the next loop.
  - joins: all 75 are ~2 s crossfades, with no hard cuts and no stray or black frames (each frame within +-3 s of a join
    reads as the previous file, a blend, or the next file, in that order). CORRECTED later on 10-17: the blends end ON the bar
    line. assemble_set.py blends over the 102 frames before each bar line with a smoothstep weight, and the builder
    measured it; my threshold read the faint last 5-20 % as finished. The timeline is on time.
  - comfort over the hour:
    - caps OK: frame mean max 0.245, block max 0.571;
    - flashes at most 2/s general and red, the peak in the dissolve into Gift Wrap (candy) at 16.45 min;
    - no luminance one-frame hits;
    - 12 red one-frame pops, all in the three Gift Wrap (candy) segments (+5.07 / +11.93 / +13.07 / +18.77 s into
      each; area 0.25-0.28). The dissolve out dims the second pass's last two.
  - Lesson: a helper named `inspect.py` in the scratchpad shadowed the stdlib module when np.median imported it (the
    script's own folder comes first on sys.path). Video checkers now live in a clean `vcheck/` folder.

**19:03-19:07, combo8 is installed; Midtown is ready to push** (read back here, adb read-only):
- The Reactor chat (tribe-hack-20) installed combo8 at 19:03 on the user's go; the headset's base.apk md5 is 7d6a9051.
- At 19:04:42 it pushed Reactor v9 (chunk 55, 2f7df8cf) + Harvest v1 (chunk 57, 981356dd). Live OBB 1a384762 =
  chunks 50, 53, 54, 55, 57, 59; 563,882,016 B.
- envs.txt (d28abb42) has 6 boxes: Dino Stage, RED EYE, Reactor, Graveyard Shift, Harvest Moon, Dino Classic. Midtown
  will be box 7 of 8.
- Dry run 19:06:58 with `--media D:/TribeUE/Visuals/christmas/deliver`:
  - preflight "installed build: combo8 (7d6a9051...), with the christmas show row and the side screens", the new check
    on a real install;
  - media: 28 videos, 3.2 GB;
  - merged OBB 7 paks, 672,937,069 B, md5 0e355825; nothing written.
- reseed.sh (192c50bd) still has KEEP_SKINS="lampwing skullbuck horseman" and none of Midtown's, Harvest's or RED
  EYE's files on its restore list. That is the Dino chat's file; a re-seed would drop them until it's updated.
- The Reactor chat says the user wanted everything pushed. That is a peer's report, so the push waits for the user's
  OK here.

**19:10-19:12, MIDTOWN v1 is LIVE** (pushed by the Reactor chat, tribe-hack-20, after the user told it "well lets get
midtown in there too"; its report, not re-read here):
- `push_midtown.sh --push --media D:/TribeUE/Visuals/christmas/deliver <xm_20261017_1237>` finished 19:12:14, exit 0.
- Live OBB 0971dd30 (7 paks: 50, 53, 54, 55, 57, 58, 59). envs.txt has 7 boxes, Midtown last (md5 c16d5102, on the
  headset and in backup/tribemod_20261006). The three tribemod texts are md5-checked and copied to the backup folder.
- /sdcard/Movies/Midtown Visuals holds 28 videos (the set's md5 5efc23ab); 20 GB free. Tribe was not launched after.
- Log: the Reactor chat's scratchpad push_midtown.log (session 9aaea2df).
- Fix Tribe Login.exe (scripts/fix_login.sh) snapshots and restores every tribemod file. Only a manual reseed.sh drops
  Midtown's files, until the Dino chat adds them to its list.
- First visit not checked yet: fps with the crowd and lasers, load time, snow, the show bus, intro presses 1-3, the
  Santa head, free roam, the side screens, comfort.

**2026-10-18 09:40-10:34, the crowd's clap-through-hats fix, rebuilt and STAGED as v1.1** (the user: "ok fix it all"):
- RED EYE (tribe-hack-0c) found it while copying xm_crowd.py. crowd3's "clap" brings the hands down to ~15 cm above
  the head's centre, inside every crown. make_person swapped the clap only for Santa and elf hats, and the preview's
  hand check only had spheres for the Santa hat, the elf hat and the antlers. So it said "none".
- New measurement: every frame of all 17 clips, near and mid supersets. The arms AND the headwear are skinned to the
  frame (no rigid-hat assumption). It counts arm/hand/glove/warmer edges that cut a headwear face (BVH ray cast along the
  edge, two-sided; checked on a test triangle) and hand vertices inside a crown (odd hits along two rays). Near tier:
  - cowboy: clap 38 edges, 4.2 cm deep; wave 14; heart 4; hold 3; ride 3.
  - bucket: clap 32, 2.9 cm deep; wave 2.
  - Santa clap 22; elf clap 35; beanie/pom dome clap 2; cap clap 2+2; antlers clap 2; ski goggles clap 4.
  - Clean: the pompom and the holly crown.
  - Mid tier: cowboy (clap, wave, heart, hold, ride), bucket (clap, wave), cap brim, Santa, elf.
  - It reproduces RED EYE's counts exactly (bucket 32, beanie 2, cap 2).
- The fix in crowd/xm_crowd.py:
  - HAT_CLIP_SWAP (hat -> clips) and `_hat_clip_swaps(people)`, run as the last step of build_people: near and mid
    tiers only (the far tier wears these hats as a colour). A dancer goes handsup on the same beat; hold/ride take the
    hat off. Ski goggles take the clap rule.
  - It draws nothing from the rng. A first try inside make_person re-drew the whole crowd (4,202 -> 4,173 people). The
    together-group timing draw (`if pr["clip"] == clip: ... rng.gauss`) is skipped for a swapped member, which shifts
    the stream for everyone after it.
- xm_crowd_preview.py: hat_spheres/hands_vs_hats replaced by arms_vs_hats (the same edge + inside test, every hat), and
  the people check uses HAT_CLIP_SWAP.
- Verified:
  - scratch builds old vs new: 4,202 people, every field identical except 15 people's clip / hat. The 15: 9 clap,
    3 wave and 1 heart now handsup; 2 mid cowboy filmers hat off.
  - Re-counted by the parts each person wears against the measurement: 10 clashing people before (4 near: beanie
    and pom clap, antlers clap, cowboy heart; 6 mid: bucket clap and wave, cowboy hold), 0 after.
  - preview --no-render: "wearing clashes: none"; arms through hats "worn none"; VAT decode unchanged.
- `ship_xm.sh` 10:02-10:34, every gate PASS:
  - bake 1341 s (the first lightmap, the tree, took 669 s, probably an OptiX kernel rebuild; the rest normal);
  - crowd 4,202 people, hat_swaps 15, clap 62 (was 71), handsup 224 (was 211);
  - comfort, overdraw, drone reel, walking map, intro all PASS;
  - cook "Success - 0 error(s), 3 warning(s)" (console-variable notices); manifest 110 entries, 1 shader archive.
- Staged `paks_current/staging/xm_20261018_1034/`: pak b911f8c4 (109,048,301 B). christmas_collide.txt b3f32d2f,
  intro d10ca742 and drone path 1afd7c06 are byte-identical to v1, so only the pak changes on the headset.
- NOT pushed. The dry run at 10:35 stopped at preflight: the headset wasn't on adb. Push = `push_midtown.sh --push
  [--media ...] xm_20261018_1034`, with OBB_WORK set to a folder of my own, on the user's OK. Rollback: xm_20261017_1237.
- Other crowds (their owners fix their own files; my tables went to each chat):
  - Graveyard (tribe-hack-eb): fixing by parts, including the far witches' cones.
  - Reactor (tribe-hack-20): fixed and checked, 10 of 352 changed; its bake waits for the user.
  - Harvest (tribe-hack-57): its 3 gaps fixed (beanie/pom clap, goggles clap, farmer hat jumppump), 2 changed.
  - RED EYE: its goggles gap fixed, 2 changed.
  - The Dino crowd (crowd3.py) has the same table as Reactor's, but the Dino chat is closed: it needs the user.
- Tools: scratchpad hatcheck/ (hat_clash.py, people_dump.py, compare_people.py).
- Later on 10-18, the Halloween chat found two gaps in my tools:
  - hat_clash.py checks only HEADWEAR, or the parts named. A scan of every part that rides the head (head_parts.py)
    finds nothing missed in Midtown, Harvest or RED EYE. In club_crowd and crowd3 it adds the onesie hood (clap 8
    edges near) and the antennae (clap 1-2). Sent to Reactor; for the Dino chat when it reopens.
  - people_dump.py builds with default arguments. That equals the bake for Midtown (verified: the same people stats,
    and walk_people.json/christmas_collide.txt identical) and RED EYE, but not for Graveyard or Harvest (exclude /
    extra) or the club (points). Harvest was told; its fix logic stands, only its count was off.
- 10-18 10:57 (relayed by the Reactor chat): the user told it "tell them all yes or whatever" and wants one batch push, which the
  Reactor chat runs when the user says "push all" there. I sent it the Midtown v1.1 line (OBB_WORK=/d/TribeUE/obb_work_xm
  push_midtown.sh --push xm_20261018_1034, stage only; push_obb's --env sees Midtown and leaves envs.txt unchanged).
  The videos follow separately with push_media once they pass.
- Dino crowd: not edited (its chat's file; the relayed "yes" answered an either/or). A tested patch is in the
  scratchpad: hatcheck/dino_patch/crowd3_hat_arms.diff, against crowd3.py acc08bc4. It adds HAT_ARMS (part-keyed;
  crowd3 keeps no hat name) and `_hat_arm_swaps` at the end of build_people. On a default-arguments build (4,198
  people, not the bake's exact crowd, which passes the grounds' exclude/extra): 17 changed, nothing else differs,
  clashes 17 -> 0. Applying it needs a Dino stage rebuild by the Dino chat.

**10-18 11:16-11:17, MIDTOWN v1.1 is LIVE** (the Reactor chat ran my line on the user's "push all" in its chat):
- Its report: exit 0. OBB 4929c79f -> 2fd1e39c (728,036,329 B), and the device md5 matches the merge. Chunk 58 =
  b911f8c4; the other 6 paks are unchanged. envs.txt is unchanged (7 boxes). The tribemod texts and Santa skins are
  md5-checked and backed up.
- Read back here: paks_current/paks.txt says "pushed 2026-10-18 11:17:09 obb md5 2fd1e39c", with
  pakchunk58 b911f8c4. The local mirror patch_live.obb hashes to 2fd1e39c.
- Its 11:03 dry run had found combo9 installed (the Halloween chat put it on at 10:52), with Midtown's strings, so the
  preflight passed.
- reseed.sh is now 3c9384d6: KEEP_SKINS has santa, and its restore list has christmas_collide.txt,
  intro.christmas.txt and drone_path.christmas.txt. The open item from 10-17 is done (not by me).
- The videos come next, with push_media, once the visuals agent's fixes pass my checks.

**10-18 12:48-13:05, the loop-pack fixes are delivered and pass my own checks. NOT pushed** (midtown-visuals' round,
for the user's "ok fix it all"):
- Delivered to `D:\TribeUE\Visuals\christmas\deliver`. The 6 replaced files were moved to `_old_20261017\`, not deleted.
  The md5s, read back here, are as reported:
  - Gift Wrap (candy) b74a97fc (was f30c7a84): only the candy tartan's red lines are dimmed, to 0.55.
  - Workshop Glitch candy 3eff43d5, frost d7824c8c, gilded df8286ee (were 341ab992, 1cd95f12, e3519ddc): the hat-lag
    keys before frame 0 now come from the periodic head pose.
  - The hour set 2ee4c796 (was 5efc23ab), 2,698,714,072 B, and its timeline c258b43e (was 029a6cf2). It is re-planned
    so no file plays again within 10 min, from the end of a play to the first frame of the next, 2-bar pre-roll included.
- My checks (scratchpad vcheck/):
  - ffprobe: the set is 108,000 frames, 3600.000 s, H.264 High 1080p30 at 5.99 Mbit/s; the loops are 411 frames.
  - flashcheck.py --loop: the 4 new loops PASS. Gift Wrap (candy): red one-frame hits 6 -> 0 (largest area 0.28 ->
    0.11); flashes general 2/s, red 1/s.
  - Workshop Glitch, old vs new decoded at full res (seamdiff.py): every frame differs at the encoding floor (PSNR
    50-53 dB). Frame 0 also has one local change, at the same spot (x 768-800, y 224) in all three palettes: 32-px
    block max 5.1-5.7, against <= 3.7 everywhere else. So the re-key is in and nothing else moved. My 32x18 wrap metric
    cannot see a change this small (0.0053 old and new).
  - tlcheck.py (new; from the timeline text alone):
    - 76 segments, 2100 bars = 3600 s, contiguous. Tree Lighting (candy) opens and Snowstorm (candy) closes.
    - A sting opens every act after the first (Midnight's follows the opener). No scene plays twice in a row, and
      all 27 loops play.
    - Tightest repeat: 10.46 min end to first frame (Subway Rush frost/candy/gilded, Workshop Glitch frost). The old
      timeline fails the same rule 9 times, down to 8.63 min.
    - Plays: Skyline Wake (candy) x4; Candy Cane Tunnel (frost), Gift Wrap (frost), Workshop Glitch (candy) and the
      3 stings x2; the rest x3. Gift Wrap (candy) now has 96 bars in the set (16 + 48 + 32), up from 48.
  - setcheck.py on the new set, decoded fresh:
    - Content: 374/380 samples match. The 6 misses are the 8-bar stings sampled at 90%, inside the crossfade into
      the next file, which is what they match (the same 6 as on 10-17).
    - Joins: 75 blends, 0 hard cuts, 0 not clean.
    - Comfort: mean luma max 0.245, 120-px block max 0.571; flashes general 2/s, red 1/s. One-frame hits: 0 general
      (largest area 0.22) and 0 red (largest 0.12). The 10-17 set had 12 red hit frames, all in Gift Wrap (candy).
- setcheck.py's decode cache is now keyed to the set file's size and mtime. The old set32.npy held the 10-17 set and
  would have re-checked it (the visuals agent's catch); deleted.
- Headset, read only, ~13:02: the 5 old files are on it (their sizes match the 10-17 files). Midtown Visuals has 28
  files; Tribe is not running; 18 GB free.
- Push, on the user's go only: `bash scripts/push_media.sh "Midtown Visuals"` with the set and the 4 loops
  (deliver/ and deliver/Loops/). It replaces same-name files, skips identical ones, md5-checks each copy and never
  deletes. The timeline .txt stays on the PC, as on 10-17.

**10-18 16:29-16:31, the fixed videos are on the headset** (the user's "push" in this chat; I ran it):
- `scripts/push_media.sh "Midtown Visuals"` with the set and the 4 loops: exit 0, "5 pushed, 0 already there, 0 failed".
  Each copy was md5-checked on the headset: set 2ee4c796, Gift Wrap (candy) b74a97fc, Workshop Glitch candy 3eff43d5,
  frost d7824c8c, gilded df8286ee. 36-37 MB/s; the set took 71 s.
- Tribe was not running. Read back after: Midtown Visuals still has 28 files, the 5 at their new sizes; 18 GB free.
- Log: scratchpad push_media_20261018.log. The old versions are only on the PC now (deliver/_old_20261017/).
- Not seen in the headset yet: the Gift Wrap tartan's look and the Workshop Glitch loop point.
