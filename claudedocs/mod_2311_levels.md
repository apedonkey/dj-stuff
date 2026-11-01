# The seven stages on Tribe 0.12.6 (2311): status, the crash, the fixes, the bring-up plan

2026-10-31, written headless. The headset was only read: `adb devices`, one `stat` + `ls` of the OBB and tribemod
folders, one `logcat -d`. Labels on every claim:
**O** = observed (I read it or ran it today), **D** = derived (the steps are shown), **A** = assumed (not checked).
Addresses: "runtime" = vaddr in the patched libUnreal.so (what the tombstone prints and what the hook adds to `g_base`);
store vaddr = runtime − 0x1000. Line numbers are in `backup/mod_fix_stream_fix/src/` unless a file says otherwise.
Scratch work (scripts, outputs, the proposed patch): `backup/mod2311_work/levels/` (listed at the end).

## Answer first

1. **No stage needs re-cooking.** All seven are in the live stages file (patch_live.obb = the headset's
   patch.2311 OBB). Each pak was cooked with the same engine build as Graveyard Shift's, and in the same package format
   as Graveyard and as 2311's own packages. They depend only on engine and glTFRuntime content that 2311 ships
   byte-identical to 2304 (section 1).
2. **Status per stage:**

   | Stage | Pak | Status on 2311 | What it needs |
   |---|---|---|---|
   | Graveyard Shift | 54 | **Works.** It loaded today and the user streamed a full set on it (from the brief). The walking and crowd make-way code ran on it until the crash (D, 4.1) | S1 (the crash) |
   | Dino Classic | 53 | **Should load:** the same content checks and load path as Graveyard (D). It has no show, no screen and no walking map; that is how the stage was built (O) | S1 (it can still crash right after a switch from a show stage, 4.3) |
   | Reactor | 55 | **Fix known** | S1; S4 (airlock gate reads bitfield bools as whole bytes) |
   | Midtown | 58 | **Fix known**; side screens and intro not yet seen on 2311 | S1 |
   | RED EYE | 59 | **Fix known**; 18/19 show scalars (no `Height`, so no crane), as built in v3 (O) | S1 |
   | Harvest Moon | 57 | **Fix known**; its intro (moving cap button, two presses, descent camera) not yet seen on 2311 | S1 |
   | Dino Stage | 50 | **Fix known**; the giant lift not yet seen on 2311 | S1 |

   "Fix known" means I found no stage-specific 2311 break. The remaining items are device checks that apply to every
   stage (3.1): the menu press, the sticks, and the DJ rig at the origin.
3. **The 13:57:37 crash is shared by every stage that has a light show.** The hook kept writing to a stage's show
   collection (`g_gColl`, an MPC) after that collection had been freed. `show_set` checks only that the pointer is
   non-zero, and `obj_alive` cannot tell when an object slot has been reused. Unreal then built a world instance for
   the dead pointer and read 3 as its parameter array (section 4, from the disassembly against the UE 5.4 source).
   The trigger is a stage unload: a switch, a reload or leaving. That trigger is not in the evidence, because no mod
   log lines from that session survived.
4. **Shared fixes**, written as a patch to a copy of src. It compiles with the same 7 warnings as the live build, and
   nothing was packaged or installed (section 6):
   S1 show collection as a weak handle (the crash) · S2 `obj_alive` uses the engine's own dead-object test ·
   S3 the per-frame driver also runs without our avatar actor · S4 Reactor gate bitfields ·
   S5 keep the stage pick (`active_env.txt`) when a load fails or Tribe switches by itself, and retry twice.
   S3 and S5 address "load every time": without S3 no stage can load in a launch where the custom avatar fails.
5. **Order to bring them up:** Graveyard → Dino Classic → Reactor → Midtown → RED EYE → Harvest Moon → Dino Stage, each
   followed by the switch test (section 5).

## 1. The content: the live stages file

### 1.1 The file
- `C:/Users/Chris/TribeUE/paks_current/patch_live.obb`: 817,060,647 B, md5 9236ca337c41d98aa547c13091ddf4cb, zip
  comment `"      2311"`, seven stored paks (O). It is the 2304 live OBB with the comment changed
  (mod_fix_port.md section 3).
- Headset: `patch.2311.com.TribeXR.TribeXR.obb` is 817,060,647 B, mtime 2026-10-31 10:57:05 (O, `adb stat` at 15:23).
  The 13:35 re-seed measured md5 9236ca33 before it started, then pushed this file and logged "stages file: OK"
  (O, backup/reseed_runs/fix_login.log).
- Each pak's md5 inside the OBB equals the md5 recorded at the 2026-10-22 push in `paks_current/paks.txt` (O). These
  are the same paks that ran on 2304.

### 1.2 Per stage (all O: scripts/pak listing via `pakcook.py`, `namecheck.py`; kit outputs md5-matched)

| Stage (envs.txt label → path) | Pak, size, md5 | Files | What the hook looks up, found in the pak | Built by |
|---|---|---|---|---|
| Dino Stage → /Game/Mods/Dino/Maps/Environment_Dino | pakchunk50, 126,777,183 B, 87ec24ba | 255: 116 .uasset, 118 .uexp, 2 .umap, 18 .ubulk, 1 shader archive. Also holds /Game/Mods/Festival (Environment_Festival, not in envs.txt) | MPC_DinoGiant 19/19 scalars (no PlayerX/Y); level names SM_DinoVisualScreen, DinoGiantSpotLight | C:/Users/Chris/TribeUE/Meta/TribeXR, cook_v14b.log 2026-10-09 23:12 (build 58 s + cook 51 s) |
| Dino Classic → /Game/Mods/DinoAnim/Maps/Environment_Dino | pakchunk53, 96,780,416 B, 7420a9fc | 172: 76/77/1/17/1 | no MPC; no SM_DinoVisualScreen | same kit, cook_dinoanim.log 2026-10-05 16:46 (35 s + 106 s) |
| Graveyard Shift → /Game/Mods/Halloween/Maps/Environment_Halloween | pakchunk54, 181,279,034 B, 5e57a8dc | 291: 131/132/1/26/1 | MPC_HwShow 19/19 + PlayerX, PlayerY, IntroStep, DoorOpen; SM_DinoVisualScreen, HwRider, HwWoods, HwWoodsGlow, HwCryptScreen | D:/TribeUE/MetaHw, cook_halloween.log 2026-10-19 11:16 (187 s + 80 s) |
| Reactor → /Game/Mods/Club/Maps/Environment_Club | pakchunk55, 64,186,471 B, 2f7df8cf | 177: 82/83/1/10/1 | MPC_ClubShow 19/19 + PlayerX/Y + RoomGain, StageGain, CrowdGain, CrowdRim; SM_DinoVisualScreen, SM_ClubSideScreens | D:/TribeUE/MetaClub, cook_club.log 2026-10-16 21:28 (57 s + 60 s) |
| Harvest Moon → /Game/Mods/Harvest/Maps/Environment_Harvest | pakchunk57, 140,088,847 B, 45d8a908 | 327: 153/154/1/18/1 | MPC_HmShow 19/19 + PlayerX/Y + IntroStep/DoorOpen; SM_DinoVisualScreen, HmButton, HmScout, HmScoutBeam | D:/TribeUE/MetaHarvest, cook_harvest.log 2026-10-20 18:56 (65 s + 93 s) |
| Midtown → /Game/Mods/Christmas/Maps/Environment_Christmas | pakchunk58, 109,048,301 B, b911f8c4 | 231: 108/109/1/12/1 | MPC_XmShow 19/19 + PlayerX/Y + IntroStep/DoorOpen; SM_DinoVisualScreen, SM_ClubSideScreens, XmRider | D:/TribeUE/MetaXmas, cook_christmas.log 2026-10-18 10:33 (210 s + 175 s) |
| RED EYE → /Game/Mods/RedEye/Maps/Environment_RedEye | pakchunk59, 98,899,131 B, 4fd69e22 | 179: 83/84/1/10/1 | MPC_ReShow **18/19 (no Height)** + PlayerX/Y + IntroStep/DoorOpen; SM_DinoVisualScreen, ReJet | D:/TribeUE/MetaRedEye, cook_redeye.log 2026-10-22 17:35 (153 s + 73 s) |

- The older notes' chunk numbers are right: 54 Halloween, 55 Reactor, 57 Harvest, 58 Midtown, 59 RED EYE. Also 50 =
  Dino Stage (+ Festival) and 53 = Dino Classic (O).
- "Built by": each kit's `Saved/ModPak/pakchunkNN-Android_ASTC_P.pak` has the live md5, written about a minute after the
  cook log named (O). The times are first-to-last timestamps in the editor build log and the cook log (O).
- The "found in the pak" column checks name maps. An MPC scalar's name in the MPC's name map shows that the
  parameter exists, and the hook resolves it by that name at runtime (D). The intro actor names match
  `tribemod/intro.<folder>.txt` (rider/woods/screen/buttonactor lines, O).

### 1.3 How they were cooked, compared with Graveyard and with 2311's own paks

| Check | 7 stage paks (757 packages, all parsed) | Graveyard (chunk 54) | 2311's own (386 headers sampled through Oodle: engine materials, glTFRuntime, Void, Visuals, Deck, all 13 maps) |
|---|---|---|---|
| Pak container | v11, zero key GUID, index not encrypted, every entry stored | same | v11, zero GUID, not encrypted; Oodle (pakchunk0: 5,776 Oodle + 4,091 stored) |
| FPackageFileSummary | LegacyFileVersion −8, UE4/UE5/licensee versions 0 (= unversioned: the runtime's own versions apply), **0 custom versions**, SavedBy/CompatibleWith engine version empty (the cooker writes them empty) | same | same |
| Package flags | 0x80002200 (FilterEditorOnly, UnversionedProperties, Cooked); maps 0x80022200 (+ContainsMap) | same | pakchunk0: 0x80002200 ×358, 0x80022200 ×8 (maps), 0xA0002200 ×15, 0x80042200 ×5; pakchunk1: 0x80022200 ×5 (maps) |
| Shader archive | `ShaderArchive-TribeXR_ChunkNN-SF_VULKAN_ES31_ANDROID…`, version 2, tables parse to the file end | same | Global / Chunk0 / Chunk1: version 2, parse to the end. The engine's `GShaderCodeArchiveVersion = 2` (D:/MetaUE54 ShaderCodeLibrary.cpp:66) |
| Engine that cooked it | 5.4.4-0+Partner-Oculus-UE5 (Meta's fork, D:/MetaUE54), `-run=cook -targetplatform=Android_ASTC -unversioned`, from each cook log's header and command line | same | libUnreal 2311 and 2304 both carry the UTF-16 build string "Partner-Oculus-UE5-CL-0" |
| Imports outside the stage's own folder | /Script/Engine, /Script/NavigationSystem (+/Script/CoreUObject as class package), /Engine/EngineMaterials/WorldGridMaterial, /glTFRuntime/M_Unlit_glTFRuntimeBase; chunks 50/53/57/59 also /glTFRuntime/M_Unlit_glTFRuntimeTwoSided_Inst; chunk 50 also /Engine/BasicShapes/{BasicShapeMaterial,Cube,Sphere}. **No /Script/TribeXR, no /Game path outside /Game/Mods/<own>, no soft package references, no cross-stage imports** | same set (minus TwoSided/BasicShapes) | (n/a) |
| Those dependencies in 2311 | every file present in 2311's pakchunk0 with the **same entry SHA1 as in 2304's** (WorldGridMaterial .uasset/.uexp, BasicShapes ×6, both glTFRuntime materials ×4); GlobalShaderCache-VULKAN_ES3_1_ANDROID.bin a1ecb35e… and ShaderArchive-Global 805b4be6… identical in both builds | | |

The rows are O. The conclusion is D: Graveyard loads on 2311 (brief), and every other stage matches Graveyard on each
of these checks. That includes cooked unversioned property data, which binds to the runtime's class layouts: the only classes involved are
engine classes, and the halloween map found their reflected layouts identical between 2304 and 2311
(mod_fix_halloween.md P2). So the other six load the same way. The custom materials in every pak were cooked by that
fork, and their shaders ship in each pak's own shader archive (version 2, above), as Graveyard's do.

### 1.4 Re-cook: not needed. If one is ever wanted
- Per stage: `cook_<stage>.sh all` in its kit (D:/TribeUE/MetaHw/TribeXR/Scripts/cook_halloween.sh is the model).
  `build` runs `UnrealEditor.exe <kit>.uproject -ExecutePythonScript=C:/Users/Chris/TribeUE/TribeXR/Scripts/build_<stage>.py`,
  `cook` runs `UnrealEditor-Cmd.exe … -run=cook -targetplatform=Android_ASTC -unversioned -map=<map>`, both from
  D:/MetaUE54, and `pack` runs `pack_chunk.sh <chunk>` (repak V11). The OBB is then merged and pushed with
  scripts/push_obb.sh. The Dino kit has no cook script; its v14b log shows the same two commands.
- Times from the logs (O): editor build 35-210 s plus cook 51-175 s per stage (table above). Pushing the 817 MB OBB
  took 9 s at the re-seed (O). Nothing was cooked in this job.

## 2. What the mod does for each stage on 2311

### 2.0 Which code
The live APK's libhook.so (md5 3b070807) is `build/libhook_pedrv.so` (O). The stage log strings in `src/` match
it except two `[ENV]` diagnostic lines (`auto-apply state`, `lookups`), the `[SKIN] diag` lines and the PE retry
message (O, string diff). So the stage code cited from src is the live stage code (D).

### 2.1 The shared path (all seven stages)
| Part | Code | 2311 status |
|---|---|---|
| Boxes from envs.txt (7 lines; up to 8) | `em_read_envs` dumper.cpp:3741-3753 (`[ENV] box N: 'Label' -> path`), `EM_MAX 8` :2224 | unchanged; file data |
| Menu on 2311 | mode detect :3880-3890 (`[ENV] 2311 menu (C++)…`), list = live `TribeVisualsMenuWidget.EnvironmentList` :3720-3726, boxes spawned as `TribeEnvironmentSkin` with the Void's identity :3289-3301, labels from the list's `EntryWidgetPool` :2531-2543, press/apply caught in `em_pe_2311` :2513-2527 via repl_pe :3393-3394 | ported today (H1-H17). The press route has not been seen on device; the no-click route works (Graveyard today) |
| No-click load | `tribemod/active_env.txt` = label, re-applied once per launch after Tribe's environment holds still ~8 s :3939-3942; `env_autotest` loads box 0 :3944-3946 | unchanged |
| Load steps 1-4 | env_menu_tick :3324-3354: SetEnvironment(Void=3), hide the Void's screens, `LoadLevelInstanceBySoftObjectPtr` (:2597-2618), wait until visible (40 s limit) | engine functions unchanged (T15); worked for Graveyard |
| Void screens | by name in Environment_Void :3911-3915, fallback to the manager's `BackdropStaticMeshActor` :3919-3924 | **2311's Environment_Void.umap still names SM_BackdropScreen and SM_BackdropScreen_ChromaKey** (O: name map read through Oodle, `void_names.txt`). The fallback should not be needed |
| Tribe's visuals on our screen | `em_register_backdrop` :2437-2466 with the 2311 signature `em_backdrop_2311` :2416-2436, re-register :3358-3363; needs a level actor whose mesh is `SM_DinoVisualScreen` | ported (H4). Six stages have the mesh, Dino Classic does not (O) |
| Video fill | Tribe's `/Game/Environment/Materials/MPC_VideoBackdrop` :2361-2409 | present in 2311 (O) |
| Show bus | `SHOWS` folder → MPC :2703-2708; `giant_lookup` (poll thread) :2697-2737; `giant_mpc`/`show_key`/`show_set` :2745-2749; `giant_tick` :3169-3282 (song cues, grid, hits, bass, laser variant, show bars) | stage content unchanged; **the lifetime bug, section 4** |
| Songs / mixer | `song_lookup` :3009 (`/Script/TribeXR.TribeDeck` first), `mix_lookup` :2873-2890 (C++ slider/knob classes first) | ported (H8, H9) |
| Walking | club.cpp: map `tribemod/<folder>_collide.txt` :118-130, pawn by `GetPlayerPawn` + its `VROrigin`/`Camera` properties :172-198, sticks by `GetInputAnalogKeyState` :236-246 (2304's Blueprint stick events, :51-86, don't exist on 2311) | ported (C1). Ran on Graveyard today (D, 4.1) |
| Crowd make-way | `club_show_player` club.cpp:251-255 (PlayerX/Y), on walking stages only | same bus as the show (section 4) |
| Lights | `em_lights` :2472-2497; `tribemod/lights.txt` is empty (O), so it only logs the lights | unchanged |
| Drone reel | `drone_load_path` :1994-2029: `drone_path.<folder>.txt`, else `drone_path.txt` | ported (SelfieStick, core :3393/:3463) |
| Unload / switch | `em_unload` :2639-2645, `em_fail` :2646-2650; stock pick :3323 / :2519-2520; "Tribe switched environment" :3368-3370 | unchanged |
| Per-frame driver | repl_pe :3377-3381: any ProcessEvent once 16 ms have passed, **only while our avatar actor exists** (`g_isoActor`) | new today (pedriver). See S3 |
| Pawn, camera, hands | `follow_wire` :1138-1153, once when our actor spawns (:1230) | ported (core 1183-1187 in the original) |

### 2.2 Per-stage parts (O: tribemod copy of 13:35 + pak names)
| Stage | Show MPC | Walking map | Gate | Side screens | Intro | Camera button | Drone path | Other |
|---|---|---|---|---|---|---|---|---|
| Dino Stage | MPC_DinoGiant (giant) | dino_collide.txt (25 floors, 4,446 people, spot decks) | – | – | – | – | drone_path.txt (no dino file) | giant lift (giant.txt: height 545, rise 44, descend 60, press 14; button at world (0,152,106), :2675); follow spot DinoGiantSpotLight |
| Dino Classic | none (no SHOWS row "dinoanim") | none | – | – | – | – | drone_path.txt | no SM_DinoVisualScreen: Tribe's visuals have no screen here |
| Reactor | MPC_ClubShow | club_collide.txt (52 floors, 349 people) | **1** (`airlock_door`; spots guest_stage, guest_floor) | SM_ClubSideScreens | – | – | drone_path.club.txt | club.txt `crowd=0.1 rim=0.15` dimmers |
| Graveyard Shift | MPC_HwShow | halloween_collide.txt (34 floors, 4,549 people) | – | – | intro.halloween.txt (button −150,940,5; HwRider, HwWoods(+Glow), HwCryptScreen; door 4 s shut=2) | camview.halloween.txt "Crowd" | drone_path.halloween.txt | – |
| Harvest Moon | MPC_HmShow | harvest_collide.txt (48 floors, 4,047 people) | – | – | intro.harvest.txt (button −240,380,13; buttonactor HmButton travel 3; HmScout, HmScoutBeam; autoshow; descent camera) | – | drone_path.harvest.txt | – |
| Midtown | MPC_XmShow | christmas_collide.txt (31 floors, 4,202 people) | – | SM_ClubSideScreens (billboards) | intro.christmas.txt (button 500,1205,5; XmRider; door 8 s) | – | drone_path.christmas.txt | – |
| RED EYE | MPC_ReShow (no Height → `g_gHasGiant` false, :2731) | redeye_collide.txt (25 floors, 3,935 people) | – | – | intro.redeye.txt (button 600,1300,0; ReJet; door 6 s) | – | drone_path.redeye.txt | – |

The intros, the camera button and the walking maps are tied to their stage only by the folder name
(`em_active_folder` :2228-2232). They use the pawn, the hands, the selfie stick and the show bus.

### 2.3 Ported today vs still 2304
- Ported (mod_fix_port.md, mod_fix_port_halloween.md, mod_fix_port_selfie.md): every lookup on the stage path tries
  the 2311 C++ name first and keeps the 2304 Blueprint name as a fallback. The fallbacks are inert on 2311:
  dumper.cpp :2293 TribeMainGS_C, :2438 BP_TribeVisualsManager_C, :2877-2890 mixer BPs, :3013 BP_Deck_C, :3737/:3759
  BP_EnvironmentSkin_C, :3893-3896 W_SkinItem_C / W_VisualsMenu_C, :3910 BP_Rig_C; intro.cpp:82 BP_PlayButton_C;
  camview.cpp:318 W_VisualsMenu_C.
- 2304-only and inert by design: club.cpp:59-69 stick events on `TribePawnBP_C`. The 2311 pawn has none, so walking
  polls the keys.
- Not portable as data: `intro_deck.txt`, which presses Play on the cued deck at showtime. On 2311 `PlayNetSynced`
  takes a 152-byte struct (mod_fix_port_halloween.md section 4). The file is not on the headset (O), so showtime
  leaves the decks alone and logs "NO deck started"; the user presses Play.
- Still using the 2304 approach on 2311: `club_allowed` reads `bHost`/`bDJing` as whole bytes (S4). `em_soft_get`
  tests `1<<28` as "unreachable", but in UE 5.4 the GC's unreachable flag rotates among bits 0-2 (S2; O: D:/MetaUE54
  ObjectMacros.h:610-624 and the 2311 `FWeakObjectPtr::Get`, section 4.4).

## 3. What breaks or is unknown, per stage, and the change for each

### 3.1 Shared (all stages)
| Item | Evidence | Change |
|---|---|---|
| **Stale show collection → crash** | section 4 | **S1**: dumper.cpp `giant_lookup`, `giant_mpc`, `show_key`, `show_set`, `giant_reset`, `giant_tick`, `em_unload`, `env_menu_tick` (load request); intro.cpp `intro_tick`. Section 4.4 |
| Cached objects checked only by "same address + same index" | `obj_alive` :2148-2149 | **S2**: also reject items the engine treats as dead: item flags & (`*GUnreachableObjectFlag` \| Garbage 1<<21), as `FWeakObjectPtr::Get` runtime 0x1A376AC does; flag pointer in the GOT slot at runtime **0x8679A30** (O, disassembly). Same test in `em_soft_get` :2333 |
| No stage at all if the custom avatar fails | the per-frame driver needs `g_isoActor` (:3379); on 2311 the pawn's ReceiveTick fallback (:3414) doesn't fire (brief); `env_menu_tick` (all loading) runs only from the driver | **S3**: :3379 `if((g_isoActor\|\|g_fallbackTicker)&&…)`. `fallback_wire` (:1158) arms the pawn ~90 s after resolve (:4043-4046) |
| The pick is forgotten when a load fails or Tribe switches environment by itself | `em_fail` :2647 and :3369 call `em_write_active("")`: the next launch won't auto-load | **S5**: keep `active_env.txt` on both (only picking a stock environment, :3323, deletes it); after a failed load the auto-load retries twice per launch (env_menu_poll). A, but a plausible part of "restart multiple times": the sign is `[ENV] unloaded our environment (Tribe switched environment)` soon after `is IN` |
| Menu press on our box | H5: native `ApplySkinToPlayer` on our spawned skin object, not seen on device | test once (5.1). If it crashes, it crashes right after `[ENV] press on our box`; the no-click route stays |
| Sticks | `GetInputAnalogKeyState` on the 2311 controller (C1, medium in the port notes) | device: `[CLUB] probe P2: the OculusTouch_* keys carry the sticks` |
| DJ rig at the world origin (T14) | every walking map, intro button, camera position and the giant button are in "rig at the origin" cm. `DJRoomMap.uexp` has the same SHA1 in 2304 and 2311 (O), and the rig is not a placed actor there (no "Rig" in its name map, O), so Tribe's code spawns it | device: `[ENV] DJ rig: loc=(…)` must read about (0,0,…). A: unchanged, because the user played a full Graveyard set with no offset reported |
| Our screen as Tribe's backdrop with the Void's lights | H4 | device: `[ENV] visuals: our screen … is Tribe's backdrop now`, visuals visible on the stage screen |

### 3.2 Per stage
- **Graveyard Shift.** Works (brief). Needs S1. Unseen on 2311: the intro (3 presses), the Crowd camera button,
  `[INTRO] screen HwCryptScreen` showing the selfie preview. No other change known.
- **Dino Classic.** No change known. By design it logs `[GIANT] no show collection for stage folder 'dinoanim'`, up
  to 20 × `[ENV] visuals: not ready (… our screen=0x0)`, and `[CLUB] no tribemod/dinoanim_collide.txt` (D from the
  code + pak). S1 matters here: before S1, a switch from a show stage leaves the old `g_gColl` in use, and
  `giant_tick` keeps writing to it (4.3).
- **Reactor.** S1 + **S4**: club.cpp `club_resolve` :183-184 and `club_allowed` :202-203. Read the byte at
  `Offset + ByteOffset` and mask it with the BoolProperty's `ByteMask` (FBoolProperty `{FieldSize, ByteOffset,
  ByteMask, FieldMask}` after FProperty, the layout em_actor_hidden :2346-2349 already uses on device). How found:
  the 2311 reflection tables list `bHost`/`bDJing` as bitfields on `ATribePawn` (mod_fix_port_halloween.md T20). For
  the host, `Role == Authority` already opens the gate, so the user (host) is not affected; guests in a room are.
- **Midtown.** S1. Unseen on 2311: the billboard side screens (`[CLUB] side screens: found`) and the XmRider intro.
- **RED EYE.** S1. 18/19 scalars is how v3 was built (no crane, O). Unseen: the ReJet intro.
- **Harvest Moon.** S1. Unseen: `buttonactor` (the cap moves through `K2_SetActorLocationAndRotation`, an engine
  function), autoshow, and the descent camera (`descent` line). Largest crowd (4,047) and pak: watch `[PERF]`.
- **Dino Stage.** S1. Unseen on 2311: the giant lift, which moves `g_vrOrigin` (the pawn's `VROrigin` property, ported)
  with `K2_SetRelativeLocation`, presses with `g_mcL`/`g_mcR` (the pawn's `MotionControllerL/R`), and pauses
  walking (`g_walkPause`). The button sits at the fixed world position (0,152,106) (:2675), which depends on T14.

## 4. The 13:57:37 crash: the stage show's objects and when they go away

### 4.1 What crashed (O: backup/mod2311_evidence/logcat_crash_buffer.txt; disassembly of the patched lib with
capstone, `backup/mod2311_work/levels/dis.py`; UE source D:/MetaUE54)
| Frame | Runtime pc | What it is | How identified |
|---|---|---|---|
| #10-#07 | libhook | repl_pe+248 → club_tick+3912 → club_show_player+392 → mpc_call_on+368 | tombstone symbols |
| #06 | 0x19EA230 | inside ProcessEvent (0x19E9EB4) | call_uf → PE |
| #04/#03 | 0x3FD2FA4 / 0x3FD3028 | exec thunk / `UKismetMaterialLibrary::SetScalarParameterValue` (fn 0x3FD2FCC: `cbz` Collection, `GetWorldFromContextObject`, then `bl 0x4618F84`) | matches KismetMaterialLibrary.cpp:19-41 |
| (tail call) | 0x4618F84 | `UWorld::GetParameterCollectionInstance`: loops `World+0x1E0/+0x1E8`, compares `FWeakObjectPtr::Get(instance+0x2C)` with the collection; **none matched → `b 0x4618D84`** | World.cpp:1612-1624 ("Lazy create one if not found") |
| #02 | 0x4618EBC | `CreateParameterCollectionInstance` (0x4618D84): stores the new instance, calls `UpdateRenderState(true)` | World.cpp:1652+ |
| #01 | 0x4123F30 | `UpdateRenderState` → `GetParameterData` | |
| #00 | 0x4124108 | `UMaterialParameterCollectionInstance::GetParameterData` (0x4123FBC): `Collection` weak ptr at +0x2C is valid, `Collection->ScalarParameters` Num (+0x40) ≥ 1, Data (+0x38) **= 3** (x28 = 3, index x23 = 0) → `ldr x25,[x8]` at 0x3 | registers in the tombstone |

Caller of ProcessEvent: frame #13 is a tick function's `ExecuteTick` (vtable +0x10). #12 is that object's tick, and #11
fires a parameterless Blueprint event through `FindFunctionChecked` + ProcessEvent (O). That is an ordinary tick, not
GC or level streaming.

### 4.2 Why (D, from 4.1 and the code)
- A real, loaded MPC always has a world instance: `UMaterialParameterCollection::PostLoad` adds one to every world
  (ParameterCollection.cpp:42-65), and every new world gets one for each MPC in memory (World.cpp:1575-1591). So when the lookup creates a new
  instance, the pointer passed in was not a live collection that world knows. A live MPC with Num ≥ 1 also never
  has 3 as its array pointer. So `g_gColl` no longer pointed at a live MPC: it pointed at freed memory, or at another
  object in the MPC's old place.
- How the hook keeps it. `giant_lookup` (poll thread, about every 8 s: env_menu_poll every ~2 s, :4079 and :4091, and
  the giant lookup every 4th call, :3847) returns early while `obj_alive(g_gColl)` passes (:2699). `obj_alive` checks
  only that the object array's slot `idx = *(o+0xC)` still holds `o` (:2148-2149). `em_unload` never clears
  `g_gColl` (:2639-2645). The only reset (:2700) runs if a lookup happens to see `obj_alive` fail while no stage is up.
- How the writes reach it. `giant_tick` checks `obj_alive(g_gColl)` once per frame at its entry (:3170). But
  `show_set` (:2749) and `giant_mpc` (:2745) check only that `g_gColl` is non-zero, and `club_tick`, which runs right
  after `giant_tick`, calls `club_show_player` → `show_set` with no check of the collection (club.cpp:254-255, :332).
  On a walking stage the stale pointer goes to the engine in two ways: (1) the MPC was freed and nothing has replaced
  the pointer yet (until the next `giant_lookup`, ≤ ~8 s); (2) its slot was reused, so `obj_alive` passes, the lookup
  keeps it indefinitely and `giant_tick` writes too. (Found by reading the code; claudedocs/mod_2311_load.md 2b,
  a parallel job's doc, reaches the same reading.)
- When the MPC goes away. The world instance holds its collection weakly (MaterialParameterCollectionInstance.h:87,
  and the weak pointer at +0x2C in the disassembly). Materials hold it strongly (MaterialCachedData.h:58-63). So the
  MPC lives exactly as long as its stage's level and materials: after a switch, a reload of the same stage, or leaving
  (Tribe picks another environment, or our "Tribe switched environment" unload), plus the GC that follows a streamed-out
  level, it is freed.
- Why it crashes inside the engine. `KismetMaterialLibrary.SetScalarParameterValue` finds no world instance for the
  pointer, creates one and reads the pointer's "parameter array". The crash follows when the bytes now at
  +0x38/+0x40 (freed and reused memory, or a new object in the old slot) look like a non-empty array, as here (D;
  which of the two ways applied at 13:57 is not known).
- What triggered it at 13:57 is not in the evidence. The main log buffer had rotated, so there are no TRIBEMOD lines
  from that session (README). The freeze recorder shows the game thread stopped for 48 s (13:55:23-13:56:11, the
  headset out of focus: vrshell placeholder, "NO_LONGER_IMMERSIVE"). The crash came 86 s after it resumed (O). The
  unload that left the pointer stale could be any of the triggers above; S1 removes the stale use whatever the
  trigger was. The earlier crash at 13:22:56 (GameThread, fault 0xffff0003, no backtrace) fits the same signature
  with a different value at +0x38 (A).

### 4.3 When the show objects are null or gone, per stage and per transition (D, from the code)
- **While a show stage is up and unchanged** (Dino Stage, Reactor, Graveyard, Harvest, Midtown, RED EYE): the MPC is
  alive. The writes are `giant_tick` (all six), `club_show_player`/`club_show_dims` (walking stages; dims Reactor
  only) and the intro's IntroStep/DoorOpen (Graveyard, Harvest, Midtown, RED EYE). The world context `g_pawn` is set
  once when our actor spawns (:1230) and checked with the same weak `obj_alive`. If Tribe replaced its pawn, the show
  would stop silently (`giant_tick` returns, :3170).
- **Switching A → B** (`em_unload("switching")` :3327, then the load): `g_gColl` still points at A's MPC. Until GC frees
  it, every stage writes A's MPC: B's lights run free, and B's crowd make-way and intro keys are A's. After the free,
  the next write can crash (the 13:57 path). **Dino Classic is no exception**: it has no collection of its own, so
  `giant_tick` keeps writing A's.
- **Reloading the same stage** (the most direct path): the old level instance unloads before the new one loads (3 s
  Void wait). The forced GC in between can free the MPC and load it again as a new object. Walking stays on across the
  reload: same map file (club_lookup club.cpp:123) and same box index (`g_emActive==g_clubOnIdx`). So from the first
  frame the stage is back, `club_show_player` writes the old, freed MPC until `giant_lookup` replaces it.
- **Leaving to a stock environment** (press :2519-2520 / :3323, or Tribe :3368-3370): `em_unload` → `EM_IDLE`, and
  `giant_tick`, `club_tick` and `intro_tick` all stop writing (they need `EM_ACTIVE`). The stale pointer bites at the
  next load of any stage.
- **Same weak check, lower risk**: the Void screens (`em_hide_screens` every second while a stage is up, :3356), the
  intro actors (`ir_hide`, `set_actor_lr`), the side screens (`SetMaterial`), the giant spot light, and club's pawn,
  VROrigin and camera. All are checked with `obj_alive` before engine calls. S2 makes that check reject objects the
  GC has marked dead. A recycled slot holding a live object of another class remains possible for these (A: rare);
  the full handle in S1 covers the per-frame show bus, where it happened.

### 4.4 Fix S1 (+S2): what the patch does
Patch: `backup/mod2311_work/levels/stage_fixes.diff` (from `apply_fix.py`; patched tree `src_fix/`; scratch build
`build_fix/libhook.so` md5 f5b5515a, **same 7 warnings as the live build**, not packaged or installed).
- The engine's own weak-pointer test, read from 2311 (O): `FWeakObjectPtr::Get` runtime 0x1A376AC and `IsValid`
  0x1A37570. GUObjectArray is at runtime 0x88A6150 (NumElements +0x24, chunk table +0x10), the item stride is 0x14,
  serial at item+0x10, flags at item+8 tested against `*[GOT 0x8679A30] | 0x200000`. The value behind that GOT slot is
  `UE::GC::GUnreachableObjectFlag`, which UE 5.4 rotates among 1, 2 and 4 (ObjectMacros.h:610-612). The patch takes
  only those values and falls back to Garbage alone otherwise.
- `show_coll_ok()`: same slot, same serial (non-zero), not dead, same class pointer, same FName; checked once per frame.
  A loaded MPC has a serial because its world instance holds a weak pointer to it (D, 4.2). If none exists yet, it is
  not adopted (`[GIANT] … no world instance yet … looking again`).
- `giant_lookup` (poll thread) only finds the collection for the current load generation `g_emLoadGen`. It publishes
  the generation and then the pointer; it no longer writes `g_gColl` or `g_gN`. `giant_tick` (game thread) adopts
  (`[GIANT] show bus adopted: 0x… (slot …, serial …, gen …)`) and drops (`[GIANT] show bus released (…)`).
  `em_unload` drops and bumps the generation, and so does every load request. `g_showGen` moves on each drop and
  adopt, so club.cpp and intro.cpp look their keys up again. `intro_tick` also requires the ride file to be this
  stage's (`intro.<folder>.txt`).
- `giant_mpc` and `show_set` (before: only a non-zero test) and `show_key`, `giant_reset`, `giant_tick` and
  `intro_tick` (before: `obj_alive(g_gColl)`) now require `show_coll_ok()`.
- Side effect: after adoption the poll thread stops re-scanning for the collection for the rest of that load. It used
  to rescan every ~8 s while `obj_alive` passed, which cost little. During the 13:55 pause the poll thread was at
  62-97 % CPU inside `refresh_numelements` (O, freeze_log + symbolized libhook frames), so fewer full scans help.

## 5. Bring-up order and per-stage tests

### 5.0 Before the tests
- Build: package `src_fix/` (or src + `stage_fixes.diff`) with the BUILD RECIPE. Only `lib/arm64-v8a/libhook.so` and
  `META-INF/*` may differ from combo_pedriver_2311.apk. The patch is against `src/`, which is combo_peretry plus
  diagnostics: the PE install retry and the atomic busy flag. The build job decides the base. The hunks don't touch
  the retry or atomic lines.
- Capture: the main buffer rotated within minutes today, so run a streaming capture during each test:
  `adb -s 2G0YC1ZF96072F logcat -v threadtime -s TRIBEMOD:I > stage_<name>.txt` (read-only).
- Load a stage without the menu: `tribemod/active_env.txt` = the exact label, one line, then launch. Or use
  Visuals > Environments > the box: the 2311 press route, test it once in 5.1.
- **Every stage must show, in order:** `[ENV] 2311 menu (C++): …` · `[ENV] box 0..6: '…'` · `[ENV] auto: re-applying
  '<Label>'` (or `press on our box` + `clicked`) · `[ENV] step 1/4: SetEnvironment(Void=3) …` · `[ENV] Void
  SM_BackdropScreen = 0x…` · `[ENV] step 2/4: environment now 3 (Void); hid 2 Void screen(s)` · `[ENV] DJ rig:
  loc=(…)` (about the origin) · `[ENV] step 3/4: … success=1` · `[ENV] *** '<Label>' is IN (visible after N s) ***`
  (2304: 1 s) · except Dino Classic: `[ENV] visuals: 2311 signature, handing back …` then `[ENV] visuals: our screen
  0x… is Tribe's backdrop now` · show stages (with S1): `[GIANT] show bus: MPC_… (load N), 19/19 …` then `[GIANT]
  show bus adopted: …` · `[SONG] TribeDeck 0x…`, `[MIX] N channel faders …` · `[PERF] … (env: <Label>)` every 10 s.
  **Fail:** `gave up after 40 s`, repeating `visuals: … NOT called`, any `[GIANT] … is gone or not a collection`, a crash.

### 5.1 Graveyard Shift (known good: proves the new build doesn't break the working stage)
Headset: at the decks play a track 1 min · walk into the crowd (left stick) · go backstage to the button (−150, 940, 5)
and press 3 times · open the camera menu and pick "Crowd" · press our Graveyard box in Visuals > Environments once.
Logcat: `[CLUB] walking map halloween_collide.txt: 34 floors, 122 boxes …` · `[CLUB] on: 'Graveyard Shift' is up` ·
`[CLUB] local pawn 0x… (TribePawn): VROrigin@… Camera@…` · `[CLUB] crowd make-way: PlayerX found, PlayerY found` ·
`[CLUB] probe P2: the OculusTouch_* keys carry the sticks` · `[CLUB] walking on.` · `[INTRO] intro.halloween.txt: 160 keys …`
· `[INTRO] found HwRider / HwWoods / HwWoodsGlow / HwCryptScreen` · `[INTRO] ready on this stage: IntroStep found,
DoorOpen found` · `[INTRO] press 1 / press 2 / press 3` · `[INTRO] the music: NO deck started` (expected) ·
`[CAMVIEW] camera menu 0x…` · `[DRONE] path: … from drone_path.halloween.txt` · `[ENV] press on our box 'Graveyard
Shift'` (the press route; if Tribe crashes right after it, use only the no-click route).

### 5.2 Dino Classic (the plain load path for a second pak, and the switch away from a show stage)
Load it, then switch to Graveyard with the menu and back. Logcat: the common lines up to `is IN` · `[GIANT] no show
collection for stage folder 'dinoanim'` · `[ENV] visuals: not ready (… our screen=0x0)` (expected) · `[CLUB] no
tribemod/dinoanim_collide.txt: no walking on this stage` · with S1: `[GIANT] show bus released (stage unloaded)`
when leaving Graveyard, and no `adopted` line on Dino Classic.

### 5.3 Reactor (walking with a gate, dimmers, side screens)
Walk from the floor through the airlock door (gate box x 900..1120, y −586..−545); play a video in Tribe's visuals.
Logcat: `[CLUB] settings: walk=1 … | dimmers: crowd=0.10 rim=0.15` · `[CLUB] dimmers: 4 of 4 in the show collection` ·
`[CLUB] gate: OPEN for you (role=auto; pawn Role 3 Authority, bHost …, bDJing …)` · `[CLUB] side screens: found
(actor 0x…)` then `side screens: mirroring the main screen (…)` · `[DRONE] path: … drone_path.club.txt`.

### 5.4 Midtown (billboards + intro)
Walk; visuals on; backstage button (500, 1205, 5), 3 presses. Logcat: `[CLUB] walking map christmas_collide.txt: 31
floors …` · `[CLUB] side screens: found` · `[INTRO] found XmRider` · `[INTRO] ready on this stage: …` · `press 1..3`.

### 5.5 RED EYE
Walk; button (600, 1300, 0), 3 presses. Logcat: `[GIANT] MPC_ReShow: 18/19 parameters (missing: Height)` then the
show bus 18/19 (no crane: expected) · `[INTRO] found ReJet` · `[CLUB] walking map redeye_collide.txt: 25 floors …`.

### 5.6 Harvest Moon
Walk; button (−240, 380, 13): the cap should move down as the hand comes in; 2 presses (autoshow). Logcat: `[INTRO]
found HmButton / HmScout / HmScoutBeam` · `press 2: … showtime follows once the camera holds (autoshow)` · `[INTRO]
the music: …` · `[CLUB] walking map harvest_collide.txt: 48 floors …` · `[PERF]` near 72 fps (2304: 71-72).

### 5.7 Dino Stage (the lift)
Press the pedestal button behind the DJ, (0, 152, 106); ride up; press again to come down; walk after landing.
Logcat: `[GIANT] ready: MPC_DinoGiant 0x…, button at (0,152,106), lift 545 cm, rise 44 s, … spot light 0x…` (non-zero)
· `[GIANT] hand N cm from the button` · `[GIANT] button: going up to 545 cm over 44 s` · `[CLUB] walking paused
(another feature moves VROrigin)` · `[GIANT] up (545 cm)` · `[GIANT] button: coming down over 60 s` · `[GIANT] down
(landed)` · `[CLUB] walking resumes` · `[DRONE] path: … from drone_path.txt`.

### 5.8 The switch test (the crash scenario; only on the S1 build, never during a live set)
Graveyard → Reactor → Graveyard → a stock environment → Graveyard → Dino Classic → Graveyard, using the menu (or
edit `active_env.txt` + relaunch where the press route fails). Then take the headset off for 60 s, put it back on,
and walk for 10 min. Each unload must log `[GIANT] show bus released (stage unloaded)`, each load `[GIANT] show bus
adopted … gen N` with a new gen, and `[CLUB] crowd make-way: PlayerX found` again. No crash. Run the same cycle once
for each new stage as it comes up.

**Why this order:** start from the stage known to work; then the simplest stage (no show, screen, walking or intro)
and the transition that crashed; then add one subsystem at a time: gate and side screens, billboards and intro, an
18/19 show, the most complex intro, and the lift, which moves VROrigin.

## 6. Shared fixes (patch in the scratch folder; nothing applied to src)
| Fix | File: function (lines in src) | What | 2311 name / offset, how found |
|---|---|---|---|
| S1 | dumper.cpp `giant_lookup` :2697-2737, `giant_mpc`/`show_key`/`show_set` :2745-2749, `giant_reset` :2771-2782, `giant_tick` :3169-3170, `em_unload` :2639-2645, `env_menu_tick` :3327-3328; intro.cpp `intro_tick` :278; new `show_coll_ok`/`show_drop`/`show_adopt` after :2694 | show collection as a weak handle, found per load, adopted/dropped on the game thread | `FWeakObjectPtr::Get` 0x1A376AC (index+serial at item+0x10, flags at item+8, stride 0x14, GUObjectArray 0x88A6150); `GetParameterCollectionInstance` 0x4618F84 → `CreateParameterCollectionInstance` 0x4618D84; `GetParameterData` 0x4123FBC (instance weak `Collection` +0x2C; MPC `ScalarParameters` +0x38/+0x40): disassembly of the crash frames vs UE 5.4 source |
| S2 | dumper.cpp `obj_alive` :2148-2149, `em_soft_get` :2333; new `gc_dead_mask` | the engine's dead test for every cached object | GOT slot runtime 0x8679A30 → `GUnreachableObjectFlag` (values 1/2/4), Garbage 0x200000: disassembly of 0x1A376AC + ObjectMacros.h:610-624 |
| S3 | dumper.cpp `repl_pe` :3379 | the per-frame driver also from `g_fallbackTicker` | none (logic). The pawn fallback exists (:1158-1168, :4043-4046) but its driver only fires through ReceiveTick, which 2311 doesn't route through PE (brief) |
| S4 | club.cpp `club_resolve` :183-184, `club_allowed` :202-203 | `bHost`/`bDJing` through the BoolProperty ByteOffset/ByteMask | reflection at runtime, as `em_actor_hidden` :2346-2349; bitfields per the 2311 tables (port T20) |
| S5 | dumper.cpp `em_fail` :2646-2647, `env_menu_tick` :3369, `env_menu_poll` :3939 | keep `active_env.txt`; up to 2 auto-load retries per launch after a failed load | none (behaviour). Picking a stock environment still clears it (:3323) |

Overlap with the parallel load job: claudedocs/mod_2311_load.md (section 3.3) proposes a general weak-reference helper
(`wref_get`) for `g_gColl`, `g_mpcColl` and other cached objects. It also proposes the same driver change (S3, its 3.4)
and never deleting `active_env.txt` (S5). For `g_gColl`, take S1 or its helper, not both. S1's per-load adoption and
drop at unload (4.4) still apply if the helper is used.

## 7. Risks and what was not verified
- **The trigger of the 13:57 crash is not observed** (no mod log lines survived). S1 is derived from the crash
  mechanics, not tested on device. If it is wrong, the failure is loud: the same tombstone. Watch the 5.8 lines.
- S2 changes `obj_alive` for every feature. It mirrors `FWeakObjectPtr::Get`, so a live object can't fail it (D).
  If the GOT slot read gives a value other than 1, 2 or 4, it falls back to Garbage only. Not run on device.
- S3 lets all per-frame work run from the pawn fallback when there is no avatar actor; each tick function checks its
  own needs (mod_fix_port.md section 2). Not run on device.
- S5 can re-try a stage that keeps failing at every launch (bounded: 2 retries). Picking a stock environment ends it.
- Graveyard "works" rests on the brief and on the crash frames (walking + show ran). No 2311 `[ENV]` log exists on
  disk (O: searched backup/ and claudedocs/; the headset buffer held no TRIBEMOD lines at 15:35).
- T14 (the rig at the origin), H4 (backdrop with the Void's lights), H5 (menu press) and P2 (sticks) are device checks.
- Outside the stages, seen while tracing (not fixed here): `sr()`'s `g_jmp`/`g_guard` are process-wide (dumper.cpp:74-75)
  but used by the poll and game threads at once. One thread's `sigsetjmp` can overwrite the other's jump buffer, and its
  `g_guard=0` can turn the other's guarded read into a real SIGSEGV. Making them `__thread` is a small change for the
  reliability job. Also, every `sr()` does `sigsetjmp(…,1)`, a signal-mask syscall, which is why full object scans
  are expensive.

## Scratch folder (backup/mod2311_work/levels/)
- `pakcook.py` (pak footer, index, package summaries, imports; Oodle via `C:/Users/Chris/.cargo/bin/oo2core_9_win64.dll`),
  `summarize.py`, `depcheck.py` (entry SHA1s), `shaderarch.py`, `softrefs.py`, `namecheck.py`, `voidnames.py`, `dis.py`.
- Outputs: `patch_live_cook.json` + `patch_live_summary.txt`, `main2311_cook.json` + `main2311_summary.txt`,
  `depcheck_main.txt`, `shaderarch.txt`, `softrefs.txt`, `namecheck.txt`, `void_names.txt`, `logcat_d_1530.txt`
  (the 15:35 read-only dump; no TRIBEMOD lines).
- The proposed fix: `apply_fix.py`, `src_fix/`, `stage_fixes.diff`, `build_fix/libhook.so` + `warnings.txt`.
