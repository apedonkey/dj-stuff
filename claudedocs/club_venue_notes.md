# Club venue (REACTOR): running notes

The running log for the club venue. The plan is `claudedocs/club_venue_plan.md`, and the brief is
`claudedocs/club_venue_prompt.md`. NOTES.md belongs to the Dino session, so club work is logged here.

## 2026-10-07: planning session

**Decisions.** The user answered two rounds of questions:
- Theme: REACTOR.
- Size: a medium hall, 24 x 36 m, 11 m high.
- Layout: an end stage, with the gate (an airlock) at the foot of the side stairs.
- Light rig: the full club rig.
- DJ role: Tribe's own.
- Order: Tribe pitch first.
- The first playable needs walking, the gate, a decorative crowd and side screens.
- Schedule: runs in parallel with Halloween, which has priority until Oct 31.

**Read offline** (object dump `logs/scan_final/objects_v7.txt` + strings in `out/alllibs/libUnreal.so`):
- `ETribePlayerStagingState`: Spectating, RequestedDJ, InvitedDJ, DJ.
  - On TribePlayerState: Get/SetStagingState, OnRep_StagingState, OnStagingStateChanged.
- `ETribeSessionState`: None, PendingHost, Host, PendingJoin, Client, PendingLeave.
- `ETribeSessionJoinability`: Public, Featured, OpenToFriends, InviteOnly, Private.
- Video-call staging: `ETribeVideoCallUserPriority` (OnStage / InCrowd / Spectator) and `ETribeVideoCallStagingMode`
  (Open / Queue / QueueClosed / Closed), plus PromoteUserToStage, MoveToAudience, a stage-queue timer and raise-hand.
- Moderation: `TribeGameMode.KickPlayer/BanPlayer`. Room info: `TribeRoom.GetMaxPlayers/GetNumPlayers/GetHostName`.
  `TribeGameInstance.GetTribeSessionMaxPlayers`.
- `TribePawnBP_C` input events:
  - axes: L and R Thumbstick_X/Y, grip, trigger;
  - actions: L and R Thumbstick (click), Scroll Up/Down, Button 1/2, Grip, Trigger, System;
  - helpers: Input_ThumbStickX_Axis, Input_ThumbStickY_Axis, Input_ThumbStick_Pressed, Input_Thumbstick_Released.

**Not public.** Tribe doesn't publish its room player cap. The 2026 "What's new" post (2026-06-24) mentions rooms,
video calls, moderation and the Privacy Bubble.

**Checked:**
- Pak chunk 55 is free. In use: 50 Dino/Festival, 51 ShaderTest, 52 MetaVat crowd test, 53 DinoAnim; 54 is
  Halloween's reservation.
- Disk: C: has 41 GB free (96% used); D: has 334 GB. So the club's fork-project copy goes on D:.
- The GPU lock was free at 2026-10-07 evening.
- The crowd is all procedural (`crowd2/LICENSES.md`), so it can go in the pitch bundle.

**Files.** The plan and these notes were written in claudedocs. The concept blockout lives at
`TribeUE\TribeXR\Scripts\Blender\club\concept_blockout.py`, with its renders in `claudedocs/club_concept/`.

### Concept blockout (2026-10-07 ~19:56-20:00, GPU lock taken and released)

**Output.**
- Seven EEVEE views in ~5 s (Blender 4.5.14): stream, crowd, dj_view, gate, aerial, bar and gate_open.
- `club_concept_sheet.jpg` (2 x 3) and `club_concept_gate_states.jpg` (closed/red next to open/green), built with
  system Python PIL.
- Scene: 38 moving heads, 56 laser lines that end on surfaces (ray-marched against the room), 155 people.

**Lessons, each found in a render and fixed:**
1. A sign on the proscenium header is never visible from the floor: it sits above the hall ceiling's sight line. A
   sign hung under the front truss hides the core dome from the floor and the stream camera. The name went onto the
   core window's top bar.
2. The hall columns at y -6 and -3 on the airlock side stood in front of the gate. The airlock frame now carries that
   bay.
3. The first gate and crowd cameras landed inside dancers. People now keep clear of the camera spots (CAM_CLEAR).
4. Laser-bar fans aimed at z 3.2-3.7 on the back wall skimmed the heads at the back of the mezzanines. The targets
   moved to z 4.3-4.7 (the 2.4 m over-deck rule).
5. Indoors without shadows, the wash spots light every wall, and 38 beam cones grey the air. The fixes:
   - wash 6000 → 1200 W;
   - beams alpha 0.035 → 0.018 and narrower;
   - haze alpha about halved;
   - darker concrete, rougher floor.
   - The blockout still reads brighter than the baked, show-lit game will.

## 2026-10-08: concept approved, phase 1 started

The user, after seeing all seven views: "wow I really like that!!".

**Still open:**
- the four quick facts (thumbsticks, Max Players, where friends appear, how a friend got on the decks);
- whether club hook features ship in a combined APK before Halloween's freeze or after Oct 31;
- the OK to create `paks_current` + `push_obb.sh`.

None of these blocks the phase-1 bake, build or cook. The push waits for the last one.

### Phase 1: room v1 (static, MIC-only), 2026-10-08

**New files:**
- `TribeUE\TribeXR\Scripts\Blender\club\club_layout.py`: the one source of the dimensions.
- `club_stage.py`: the generator, using dino_stage.py's pipeline. Helpers are copied, because dino_stage runs at
  import.
- `TribeUE\TribeXR\Scripts\build_club.py`: the UE import.
- `D:\TribeUE\MetaClub\TribeXR`: the fork-project copy, 9.6 MB before the first cook.
  - It holds the uproject, Config, Build, Plugins (the glTFRuntime stubs + ModMaterialTools), Binaries/UnrealEditor.target,
    Scripts/pack_chunk.sh, make_obb.py and the new cook_club.sh.
  - No Dino content, and its own Saved.

**Bake** (out_club, 313 s on the 1660S, under the GPU lock):
- 13 meshes, about 22k tris in all, no crowd, no haze.
- Raw linear means, pre-exposure: floor 0.0020, hall 0.0031, stage 0.0066, core 0.022, mezz 0.0034, bar 0.010,
  rig 0.0066.
- Exposures x NIGHT 0.5: floor 2.8, hall 2.6, stage 2.2, mezz 2.4, core and rig 1.8, bar 2.2.
- The previews show a dark room lit by its practicals and light pools.

**Fixes** before the first good run:
- Three add_light calls were missing the positional `target` (None).
- The sign helper now centres along any direction (the CONTROL ROOM sign hangs on the side wall).

**UE import** (build_club.py on MetaClub, -nullrhi, 161 s):
- 10 textures, 13 meshes, chunk label PAL_Club → 55.
- The screen came in at y -540 cm, so the level is turned 180°. Hall bounds 2480 x 4430 x 1420 cm, as expected.
- 13 actors, all NoCollision, plus ClubDeckLamp_L/R. The side screens are a dim idle blue (0.02, 0.04, 0.10) until
  phase 2 mirrors the video.

**Push helper** (drafted in the scratchpad, not run): push_obb_merge.sh.
- It pulls the LIVE patch OBB from the headset, keeps all its paks, adds or replaces only ours, and pushes only with
  `--push` (it refuses while Tribe runs).
- `scripts/reseed.sh` (Dino's file) restores `PATCH=...patch_v82.obb`. After a club push that line has to point at
  the combined OBB, or the next re-seed silently drops the club. That needs the user's OK, since it's a shared file.

**Cook** (MetaClub, fork, first cook, 32 s with the warm shader cache):
- "Success - 0 error(s), 3 warning(s)". The warnings are engine console-variable notes.
- The chunk 55 manifest has 37 entries, all under /Game/Mods/Club: the map, 13 MIs, 13 meshes, 10 textures. No stubs,
  no engine content.

**Pack:** `pakchunk55-Android_ASTC_P.pak`, 26,256,126 B, 83 files, no shader archive (MIC-only).
- Lesson: MSYS_NO_PATHCONV exported for a whole script also reaches pack_chunk.sh. There repak got
  `/d/...` and failed ("Input is not a directory"). cook_club.sh now sets it only on the Unreal commands.
- Lesson: the opposite holds for adb. Device paths need MSYS_NO_PATHCONV=1, or Git Bash rewrites `/sdcard/...` to
  `C:/Program Files/Git/sdcard/...`.

**Dry-run merge** (push_obb_merge.sh, nothing pushed):
- The live headset OBB holds pakchunk50 (126,192,238 B, md5 a03ac603…) + pakchunk53 (96,780,416 B, md5 7420a9fc…),
  with comment "      2304".
- Merged with pakchunk55, the OBB md5 is 4d6bc701… (scratchpad obb_merge/merged.obb).

**Device steps done 2026-10-08 ~17:52-17:55** (the user: "ok push it"; Tribe was not running):
1. **Push:** push_obb_merge.sh --push re-pulled the live OBB (still 50 a03ac603 + 53 7420a9fc), added 55 and pushed via
   patch.new.tmp + mv. Device md5 ce69696dad264ac43a9be7dda7feb8d1 = local.
   - Archived as `D:\TribeUE\MetaClub\TribeXR\Saved\ModPak\patch_reactor_v1.obb` (249,229,340 B).
2. **Menu line:** `Reactor=/Game/Mods/Club/Maps/Environment_Club` appended to the headset's tribemod/envs.txt (staged
   via /data/local/tmp, chmod 666; now 205 B, 4 lines) and to backup/tribemod_20261006/envs.txt.
   - active_env.txt is still "Dino Stage", so the user picks Reactor in the menu.
3. **Re-seed:** `scripts/reseed.sh` PATCH= now points to patch_reactor_v1.obb. That was the only line changed in the
   Dino session's file; `bash -n` passes.
4. **Coordination:** the other running session is the VRChat integration chat (the user). It doesn't push Tribe patch
   OBBs, so there's no conflict. Any session that pushes Tribe OBBs must keep chunk 55.

**Logcat capture** for the first test: scratchpad logcat_reactor_v1.txt (the brief's filter).

### v1 device test, 2026-10-08 17:55-17:58 (verified from the TRIBEMOD log)

**What the log shows:**
- The mod read 4 menu lines ("box 3: 'Reactor' -> /Game/Mods/Club/Maps/Environment_Club").
- Click at 17:56:29.96, then LoadLevelInstanceBySoftObjectPtr success=1 at 17:56:32.86, then "'Reactor' is IN
  (visible after 1 s)".
- "our screen ... is Tribe's backdrop now ... material=MI_ClubVisualScreen". When the user played a video it changed to
  "material=M_VideoBackdrop": Tribe's visuals are on our core window.
- Both ClubDeckLamps were found (3 cd).
- FPS in Reactor: 71.2-72.0 per 10-s window after the load. The load window had one 400 ms frame (67.4 avg). No
  crash, no auth errors.

**The user:** "looks pretty good! we can make it a little darker. also, get rid of the bar word at the bar."

**v2:**
- NIGHT 0.5 → 0.35, i.e. 30% less baked light. Glows and screens are unchanged.
- The bar sign "COOLANT BAR" → "COOLANT" ("the bar word" read as the word BAR; asked the user to say if the whole
  sign should go).
- v1's Blender output is kept in out_club_v1.

**v2 build:**
- Bake 311 s (GPU lock taken and released). Previews are visibly darker; the sign crop confirms "COOLANT".
- UE build, cook (37 entries, 0 errors, 26 s) and pack: pakchunk55 is 26,240,254 B.
- The Dino session took the GPU lock at 18:05:49 for its v9 lasers bake: the lock protocol works.
- **Push refused:** Tribe was running on the headset. The merged OBB (live 50 + 53 + v2 55) is ready but not pushed.
  Waiting for the user.
- **Risk:** the Dino session's v9 push will drop chunk 55 unless it builds from the live OBB or lists pak 55. The user
  was asked to pass the heads-up on, or to let this session message it.

**v2 push:**
- The first two "its closed" from the user: Tribe was still running, parked while the headset slept
  (ResumedActivity = Tribe's GameActivity, mWakefulness=Asleep, PID 17851).
- `am force-stop` from the PC was denied by the auto-mode classifier. Lesson: taking the headset off parks Tribe; the
  user must quit it on the headset, or approve a force-stop.
- After the user quit it, the push went through. Live 50 a03ac603 + 53 7420a9fc unchanged; 55 replaced (v1 f9be2c5a →
  v2). Device md5 5de618df5f90dbd602c48c1f910af91c = local.
- Archived as patch_reactor_v2.obb. reseed.sh PATCH= now points at v2 (same single line; `bash -n` passes).
- Log capture: scratchpad logcat_reactor_v2.txt.

### v2 on device and the shared push convention (2026-10-08 ~18:55-19:50, verified)

**The user's visit:**
- Clicked 'Reactor' at 18:55:49; "'Reactor' is IN (visible after 1 s)"; our screen registered as Tribe's backdrop.
  The user's verdict on v2: "ok".
- The user then switched to Graveyard Shift: the Halloween stage, chunk 54, MI_HwVisualScreen.
- Tribe exited at 18:56:51. exit-info: reason=1 EXIT_SELF, status 0. That is Tribe's own self-exit, not a crash, and
  it happened in Graveyard Shift.

**What the other sessions set up** (the club takes part):
- `C:\Users\Chris\TribeUE\paks_current\` mirrors the live OBB: paks/, paks.txt, patch_live.obb.
- `scripts/push_obb.sh` is built on our push_obb_merge.sh draft. It adds compare-and-swap (it refuses if the live OBB
  changed since its pull), `--env "Label=/Game/..."`, and the mirror. **Club pushes now go through it:**
  `bash scripts/push_obb.sh --push D:/TribeUE/MetaClub/TribeXR/Saved/ModPak/pakchunk55-Android_ASTC_P.pak`.
  The scratchpad draft is retired.
- reseed.sh PATCH= now points at `C:/Users/Chris/TribeUE/paks_current/patch_live.obb`, set by another session. It is
  the better choice: a re-seed restores every stage.
- **Live 19:46:** obb md5 12935c16. Chunk 50 is Dino v9 (eb8d8c3a), 53 is 7420a9fc, 54 is Halloween (00eb8956), and
  55 is **club v2 (8e570bcb, our exact pak)**.
- The headset's envs.txt is: Dino Stage, Dino Classic, Reactor, Graveyard Shift. Festival was dropped:
  **the mod shows at most 4 boxes** (EM_MAX in dumper.cpp), and push_obb.sh refuses a 5th line.
  - The repo backup envs.txt still lists Festival and has no Graveyard Shift. That list is the Halloween/Dino
    sessions' to reconcile; Reactor is present in both.

### The user's facts, and phase 3a started (2026-10-08 evening)

**The user:**
- "the thumbstick in tribe do nothing at all".
- "i believe 16 is the largest" (Max Players).
- "friends are in front of the decks".
- "you can make an open room and people join or by inv".
- "if you have to look, ghidra is available".
- These are recorded in the plan (sections 1.2, 1.3, 12 and 13).

**The object dump also shows a room DJ-role path:**
- TribePawnBP_C.Server_RequestDJMode;
- TribePawnBP_C.HandleStagingStateChanged and GetStagingState;
- W_OnlinePlayerListItem_C.On_StagingImage_MouseButtonDown and HandleStagingStateChanged: a clickable staging icon
  on each row of the room's player list.
- A background agent is decoding the flow offline (Ghidra, plus Blueprint bytecode from the main OBB). Outputs go to
  the scratchpad djrole\.

**Phase 3a: show + crowd. No mod change, no APK.** The Dino laser engine was rewritten today (laser_show, LaserFix),
so the club's lasers fade with their cue rows for now; sweeping comes in 3b.
- `club\club_show.py`: T_ClubCues, 32 x 16, in dino_materials' format.
  - Rows: heads 0, wash 1 (dm.WASH_ROW), core 2, laserbar 3, sidelasers 4, backlasers 5, bayheads 6, floorheads 7,
    lenses 10 (strobe_tex default), always 13, beacons 14.
  - Comfort asserted in check(): no strobe flag, no wash pulse.
- `club_stage.py` (v2 kept as club_stage.v2.bak.py) gains:
  - separate SM_ClubLenses (strobe_tex row 10), SM_ClubCoreGlow (row 2), SM_ClubPixelBlue/Amber (chase);
  - per-group SM_ClubBeams{Hall,Bay,Floor}, SM_ClubHalos{Hall,Bay,Floor,Laser}, SM_ClubLasers{Bar,Side,Back}, with
    rows in club_rows.json;
  - the crowd: crowd3.build_crowd2 with a keep-out over its whole field and our ~180 spots as `extra` (floor,
    mezzanine rails, bar, back floor), VAT T_ClubCrowdVAT, baked T_ClubCrowd.
- `build_club.py` CLUB_ANIM=1:
  - show_lit on the 7 baked meshes, strobe_tex, chase, beams_material + per-row cue instances, vat_crowd + prepare_*;
  - start-up signature checks on the dino_materials factories it uses, and WASH_ROW == 1;
  - the static path is kept as the fallback.
- **The bake waits for the GPU lock:** the Halloween session's hw_stage.py has held it since 20:07:58.
  scratchpad/chain_3a.sh waits for it, then runs a fast test, the full bake (lock released after), and
  `CLUB_ANIM=1 cook_club.sh all`.

**3a built and pushed (2026-10-08 20:13-20:23):**
- The lock was free by the time the chain ran (0 s wait).
- Fast test ok. Crowd v3: 150 people, all extras (0 field). Body 76,555 tris + glow 1,104. VAT 2048x1024, 2 pages.
- Full bake 384 s, lock released 20:21:24. T_ClubCrowd mean 0.0057.
- **UE build:** "ANIMATED build (phase 3a show + crowd): 26 meshes".
  - Materials: 7 show_lit (38 expressions each), lenses and core strobe_tex, 2 chase (16), crowd VAT body (110) and
    glow (67), beams and halos anim (46).
  - Cue instances: Beams Hall/Bay/Floor → 0/6/7; Halos Hall/Bay/Floor/Laser → 0/6/7/3; Lasers Bar/Side/Back → 3/4/5.
  - Level saved with 26 actors.
- **Cook:** 0 errors, 3 warnings, 30 s. The chunk 55 manifest has 69 entries, including the club's ShaderArchive.
- **Pak:** 47,502,742 B, 147 files.
- **Push** (scripts/push_obb.sh --push, Tribe not running): the live OBB was 50 eb8d8c3a + 53 7420a9fc + 54 1d828b4f
  (Halloween's newer one) + 55 v2. 55 was replaced with 3a, md5 23911ea0. Device md5 f1394669 = local; the
  paks_current mirror was updated.
- Log capture: scratchpad logcat_reactor_3a.txt.

## 2026-10-08: walking (W1), part 1: collision map and rules verified; hook code next
- **New files.**
  - `Scripts/Blender/club/club_spots.py`: the crowd spots, shared by the bake and walking. It is identical to club_stage.py's `club_people` (seed 11); club_stage.py still has its own copy.
  - `Scripts/Blender/club/club_collide.py` writes `out_club/club_collide.txt` (world cm) and the top-down check `club_collide.png`. The map has 52 floors, 62 boxes (gate included), 166 circles and 3 spots. It also runs an offline 10 cm flood fill on the values as written: ALL CHECKS PASS.
  - `hook/club_collide.h`: the rules, with no engine code.
  - `tests/club_collide_test.cpp`: the same flood fill, run on the Quest.
- **World mapping verified.** The FBX import flips Y, and the build log says "screen centre y=-540 cm -> level yaw 180". So world = (-100x, 100y, 100z), and the airlock is at world X +800..+1200 (the DJ's right).
- **Rules.** Step 45 cm, head 190, knee 25, radius 20; dancers have r 25 cm.
  - The bay is shut at the screen line (Y 530..570).
  - The gate is one-way: a guest can walk out but not in.
  - A wall refuses a move only if it ends closer than it started (signed distance), so you can always back out of an overlap.
- **On-device check, identical to Python:**
  - host: 78488 states, 0 stuck;
  - guest from the floor: 58694 states, 0 on the stage;
  - guest from the stage spawn: 78488 states, and they reach the dance floor;
  - sliding along the barrier and the gate refusal also behave correctly.
- **Hook facts found.**
  - TribePawnBP_C properties: VROrigin, Camera, bHost, bDJing (logs/scan_final/sdk.txt).
  - Stick events: `InpAxisEvt_MotionController {L,R} Thumbstick_{X,Y}_K2Node_InputAxisEvent` (objects_v7.txt). Find them by scanning name plus outer, not with find_by_path, because their FName number may be non-zero.
  - The poll loop runs every 500 ms; the `(tick%4)==0` slot is free.
  - read_trim_file reads the whole file.
  - In per-frame game-thread code, avoid sr(): the guard flag is shared with the poll thread. Read alive objects directly instead.
- **Next: hook/club.cpp design.**
  - **Hook-up:** `club_pe` (four pointer compares) at the top of repl_pe; `club_tick` after giant_tick on both tick lines; `club_lookup` in env_menu_poll.
  - **Local pawn:** GameplayStatics.GetPlayerPawn(g_isoActor, 0).
  - **Sticks:** from the input events. Fallback: PlayerController.GetInputAnalogKeyState on both key families (OculusTouch_* and MotionController_*), with FNames from KismetStringLibrary.Conv_StringToName.
  - **Moving:** VROrigin via K2_SetRelativeLocationAndRotation with bTeleport.
  - **Start over** when Tribe moves VROrigin (more than 1 cm or 0.5 deg) or its parent (more than 5 cm or 1 deg). Restore the starting pose when the club unloads.
  - **Gate:** allowed = Role==Authority, or bHost, or bDJing; club.txt `role=` overrides it. A guest on the stage (floor 0, Y > -300) is moved to spot `guest_floor`.
  - **Back:** right stick held down for 1 s returns you to the start (guests go to guest_floor).
  - **After club.cpp:** a 4-edit dumper.cpp patch (the Dino session's file: message it first), then compile, build the APK, sign, and ask before installing.

## 2026-10-08: walking (W1), part 2: hook code written and compile-checked
- **New code.**
  - `hook/club.cpp` holds all the walking code (inert off the club's map). Shared-file change: `scratchpad/patch_club_hookup.py` (exact replaces, keeps CRLF) adds 4 lines to dumper.cpp: the include plus `club_pe` at the top of repl_pe, `club_tick` after `giant_tick` on both tick lines, and `club_lookup` in env_menu_poll's free slot.
  - Compiled against a scratch copy of dumper.cpp (19:25, song11): no new warnings. The real dumper.cpp is untouched until the Dino session answers (messages sent to both tribe-hack-f1 sessions).
- **How it works.**
  - Local pawn via GameplayStatics.GetPlayerPawn(0). Its VROrigin and Camera come from TribePawnBP_C properties; the parent comes from SceneComponent.GetAttachParent, with K2_GetComponentScale as a check.
  - Sticks: the larger of Tribe's 4 stick events (caught in ProcessEvent) and PlayerController.GetInputAnalogKeyState on OculusTouch_* and MotionController_* keys (FNames via Conv_StringToName). The first real movement on each source is logged once ("probe P2").
  - Safety: if Tribe moves VROrigin itself, walking starts over from there; if that happens 4 times in 10 s, walking stands down. If Tribe moves the rig, walking resets to the start (after 4 moves it just follows the rig). Leaving the club restores the start pose.
  - club_stage.py now imports `club_people` from club_spots.py (the code was identical; only the docstring differed), so the bake and the collision file share one crowd list.
- **APK plan.**
  - One combined APK, e.g. `club1` = the current dumper.cpp + the 4 lines, built with the brief's section 3.3 commands and `bash scripts/sign_apk.sh`.
  - Push `club_collide.txt` (and optionally `club.txt`) to tribemod via /data/local/tmp.
  - Install with `adb install -r` only after the user's OK and with Tribe closed.
- **Headset test list (pass/fail), logcat `[CLUB]`.**
  1. Load REACTOR: `on`, `engine:` (all non-zero), `stick events` (4 non-zero), `collision map: 52 floors, 62 boxes, 166 circles, 3 spots`, `local pawn`, `walking on. head (...)` (the head near (-6, 87) at the decks), `gate: OPEN for you`.
  2. Left stick walks where you look; one `probe P2` line says which source carries the sticks.
  3. The stage edge stops you (no falling). The airlock on the DJ's right: down the stairs smoothly, through the door, into the hall.
  4. Dancers, the barrier and the bar block you, and you slide along them. Back corners: the mezzanine stairs go up, and the rails hold.
  5. The right stick turns 30 deg; holding it down for 1 s puts you back at the decks.
  6. Body, hands, menus and pointer follow you (probe P5). `[PERF]` fps is unchanged.
  7. `club.txt` with `role=guest`: you're moved outside the airlock within 2 s; walking into the door gives `gate: refused`; walking out from inside still works.
  8. Pick another environment: `walking off (...)`, back at the decks.
- **Applied and built (2026-10-08 22:12).**
  - The Dino session agreed (the user's OK: "figure out walking now"). hook/dumper.cpp is now md5 965a5132 (was 18bc6f22, song11).
  - `out/hookA/club1.aligned.apk` md5 5ace0c5e = song11 + the club; its libhook.so = libhook_club1.so, md5 11c658ad, with 27 `[CLUB]` strings.
  - Not installed yet: the headset is off USB, and the install needs the user's OK.
  - Cadence agreed with the Dino session: whoever builds next builds from the patched file and tells the other; nothing gets installed without the club lines.

## 2026-10-09: round 2. The user, after the first walk: "improve the quality of the crowd, have more people in the crowd, also be able to walk in the crowd ... lazers and lights go with the music like how it does on the dino stage", "specific visuals for an hour set", and a Reactor flight path for the selfie camera
- **Walking test (club1 on song12, 17:10-17:15).**
  - About 300 m walked, stage → airlock → hall → bar end → back up, at 71.7-72 fps.
  - Both stick sources work: Tribe's events and the OculusTouch_* keys. The gate opened (Authority, bHost 1, bDJing 1).
  - Tribe once raised the rig 17 cm while lowering VROrigin 17 cm (height only). The club now keeps your place for height-only changes.
- **Soft crowd (club2/club3).** Dancers are `person` shapes: solid only within 15 cm of the spine. Near people you slow down (to 45 % at most) and drift round them; head-on, you pass on the far side. The offline check and the on-device C++ test agree: 86761 / 66967 / 86761 states.
- **Walking for any stage:** tribemod/<folder>_collide.txt (the Dino session wants dino_collide.txt). The g_walkPause handshake is in the Dino session's lift code. Height-only logs are rate-limited.
- **Show bus (the Dino session's dumper.cpp, song13 = 5e231fca).**
  - The hook drives MPC_DinoGiant on Dino, else MPC_ClubShow, with the same 17 names.
  - The giant lift runs only on Dino.
  - It exposes show_key/show_set + g_showGen + HAVE_SHOW_BUS. club.cpp writes PlayerX/PlayerY every frame (make-way).
  - Bug found and fixed there: mpc_param_name read only 16 names, so Bass (the 17th) never reached the Dino lights.
- **club3** (2d2ad182) = song13 + the club. The Dino session installs it after its re-seed, with backup/club3_pending/: club_collide.txt (3a crowd, new format, a45a0bd8) and drone_path.club.txt.
- **Drone reel:** Scripts/Blender/club/club_drone_reel.py → drone_path.club.txt (9 shots, 91 s, all clear of the room). The hook reads drone_path.<folder>.txt while a stage is up (per-venue reel, no menu box).
- **Crowd v2 (stage v4).**
  - club_crowd.py: a copy of crowd3 (the club's points with zones; dubstep clips; no dino costumes; no flow toys; phones 8 %; UV5 VatPivot).
  - club_spots v2: 349 spots + 3 riders = 352 people, all near tier, 311k tris (Dino's crowd is 323k at 72 fps). 38 groups, 176 glowing, 22 phones, 6 totems.
  - The bake is light-only (T_ClubCrowdLight: clothes come from the vertex colour, so no more atlas mosaics), exposure 10.
- **Vertex colours** (checked in the sources): Blender's FBX export writes sRGB; UE's FBX import decodes to linear; StaticMeshBuilder stores ToFColor(true), i.e. sRGB again. The material therefore decodes VertexColor ^ 2.2 (the ColGamma parameter).
- **Scripts/club_materials.py** (ours, built on dino_materials):
  - club_crowd: show-clocked dance, make-way push (55 cm at <= 30 cm, from 110 cm), Col^2.2 x light x (0.3 + 0.7 wash), a blue/amber rim, brighter on hits.
  - lenses (+HitMajor), core_glow (± Bass), beams (hits, drops), laser_lines (bass, drops).
- **build_club.py v4** (v3a backed up): MPC_ClubShow = the 17 show names in the hook's order, then PlayerX/PlayerY (default 1e6), GateOpen/State/Deny.
- **Next:**
  - the full bake → build → cook → push (push_obb.sh) → install;
  - port the Dino's laser_show (sweeping lasers with per-song variants) to the club's lasers: its fixed cue rows need the club's own laser cue texture.
- **Visuals:** Visuals/reactor/ (the kit copied from Halloween, the Reactor palette, a GPU lock that yields to Halloween). CONCEPTS.md lists 12 concepts + a sting + Cold Start. Four agents are authoring them, with look-dev only until the user approves the stills.
- **Stage v5 (2026-10-09 19:12): v4 + the sweeping lasers.**
  - Scripts/Blender/club/club_lasers.py: 8 units, 68 beams in the Dino laser_show format.
    - front-truss fans: group 0 → cue row 3;
    - mezzanine-pole units: group 1 → row 4;
    - back-truss units: group 2 → row 5.
  - Each beam's length is solved over the engine's full sweep (pan/tilt ±1, 25 poses, every 20 cm): above raised hands (FLOOR + 2.3 m), clear of the mezzanine people (deck + 2.3 m), above 3 m over the stage and 1.6 m from the DJ's head. Lengths 11-19 m; none dropped.
  - T_ClubLaserProg/Lib come from show.py's tex_laser_prog/lib (read-only), so the choreography is the Dino's (per-song variant, hits, bass, drops).
  - build_club: SM_ClubLaserShow with full-precision UVs, bounds ±400 cm, material dm.laser_show. The static laser lines and their halos are gone (23 actors).
  - Cook: 0 errors. pak 7ccef713, 63 MB, staged in backup/club3_pending/ (the v4 pak is kept in v4/). Collision file unchanged (club_collide_v4.txt).
- **First in-headset test of club3 + v5 (2026-10-09 22:27, after the re-seed; the Dino session's capture):**
  - The walking map loaded (349 people). Walking 9-18 m per 10 s. [PERF] in Reactor 71-72 fps. No crash.
  - make-way: PlayerX/PlayerY were MISSING at 22:27:47 and found at 22:27:58, once the show bus found MPC_ClubShow (g_showGen re-lookup). It heals itself.
  - The user: "looks pretty good in there! my only thing right now is that it needs to be WAY darker in there in the crowd and on stage. not as much on stage though. its supposed to be a dark club".
  - Bug (the user, on the Dino Stage: "i was able to actually walk for a sec but then i wasent able too"):
    - club_lookup runs every 2 s (tick%4 at 0.5 s) and did not run between 22:30:27 and 22:30:31.98.
    - So g_clubOn stayed set from Reactor, and club_tick walked on the Dino with club_collide.txt for 0.7 s.
    - Fixed: club_lookup records the stage the map belongs to (g_clubOnIdx). club_tick requires g_emActive == g_clubOnIdx.
- **v6, the dark club (2026-10-09 22:50).**
  - Four dimmers in MPC_ClubShow (build_club.CLUB_EXTRAS); the pak's defaults:

    | Dimmer | Default | Applies to |
    |---|---|---|
    | RoomGain | 0.3 | floor, hall, mezzanine, bar, rig |
    | StageGain | 0.6 | stage, core wall |
    | CrowdGain | 0.3 | crowd bodies |
    | CrowdRim | 0.5 | crowd rim |

    v5 was 1 for all four.
  - The room and stage are club_materials.club_lit, our own copy of dm.show_lit: texture × (floor .. 1 by the wash) × the dimmer.
    - The Dino session's NIGHT_GAIN (0.6, added 22:38 for the Dino's own "darker" feedback) no longer reaches the club.
    - Floors: room 0.05 (was 0.08), stage 0.06.
  - Crowd:
    - level = (0.04 + 0.96 wash) × LightGain × CrowdGain (was 0.3 + 0.7 wash);
    - the rim's blue floor is 0.1 (was 0.25), × CrowdRim.
  - Estimated from the cue table (the wash averages 0.27 over the 32 bars, 0.55 at the drop), as linear light:

    | | Average | Intro (between hits) | Drop |
    |---|---|---|---|
    | Crowd | 5.4× darker | 8× | 4× |
    | Room | 3.6× darker | | |
    | Stage | 1.75× darker | | |

  - Not dimmed: beams, halos, lasers, lenses, LED strips, phones, the screens, the deck lamps. In a dark club they are the light, and the DJ needs to see the gear.
  - Live tuning, hook/club.cpp:
    - tribemod/club.txt `room= stage= crowd= rim=` (0..4) are written to MPC_ClubShow every frame while Reactor is up, walking or not.
    - A key that is not set leaves the pak's value. A removed key keeps its last value until the stage reloads.
    - Logged as "[CLUB] settings: ... | dimmers: ..." and "[CLUB] dimmers: N of 4 in the show collection".
    - With v6 + this APK, darker/brighter is a club.txt push: no rebuild, and Tribe stays open.
- **Lasers in v6 (2026-10-09 22:55).**
  - The Dino's v12 scene masks (prog alpha; the lib's pattern masks at texel 5 z) assume the Dino's families:

    | Family | Bit |
    |---|---|
    | fan | 1 |
    | horns | 2 |
    | towers | 4 |
    | lip | 8 |
    | mouth | 16 |
    | delay | 32 |

  - The club's groups 0/1/2 map to the fan / horns / horns families. So 86 of 256 variant-bars left Reactor with no lasers: bars 4-10 in every variant, plus towers+delay and lip-only drop scenes. The Dino session confirmed it was its bug.
  - Fix: Scripts/Blender/club/club_laser_scenes.py (pure numpy; club_stage.py writes T_ClubLaserProg/Lib through it).
    - A mask keeps its fan/horns bits.
    - A mask with neither maps lip/mouth → front fans, and towers/delay → poles + back truss. 0 stays 0.
    - Result: 0 dark bars. Patterns, colours and levels are unchanged. Refresh without a bake: `python club_laser_scenes.py out_club`.
  - v6 pak 19937909 is staged on D: (backup/club4_pending/README.txt). v6a (dimmers only) is 35f7e6f9.
- **v7 plan: moving heads on the Dino's v13 mover engine** (the contract from the Dino session, 2026-10-09 23:00; verified on its device).
  - DATA: the same 5 UV layers as the lasers, after UVMap. V is raw (the materials read 1 - v).
    - LaserPivot = (pivot x, y) and LaserPivotZPhase = (pivot z, phase), in Blender m. The pivot is the head's centre (the tilt axis); its z follows any stage drop like the geometry.
    - LaserAmp = (pan amp deg, tilt amp deg).
    - LaserCue = (REST YAW deg, u). Rest yaw is measured like atmosphere.aim(): degrees from -Y toward +X.
    - LaserFix = (x 0..1 across the rig, 0).
    - u: -1..1 across a row. x < 0.5 = the left side, for mirrored patterns.
    - Reference: grounds/atmosphere.py _stage_moves() / STAGE_MOVES / stamp_uv.
  - MOTION: one rigid move per fixture.
    - Pan about the vertical through the pivot by pan_amp·P.
    - Then tilt by tilt_amp·Q about k = normalize(h × Z), where h is the horizontal part of the rest direction after the pan.
    - The same k for head, lens, glow and beam (atmosphere.mover_pose_pq).
    - The yoke only pans (tilt amp 0). The base stays static in the baked mesh.
  - MATERIALS (dino_materials.py):
    - mover_beams(name, folder, texture, cues, prog, lib): beams + lens glows; one MIC per mesh with its CueRow.
    - mover_heads(name, folder, cues, prog, lib): yokes + heads; dark unlit metal × show_dim.
    - mover_lens(name, folder, texture, cues, prog, lib, row=10).
    - P/Q come from MOVER_MOTION_HLSL: the bar pattern's pan/tilt, each cycle capped at MOVER_FMAX = 2 per bar, plus hits, bass and the drop boom.
  - EXPORT GOTCHA: stamp the data onto each part's faces from a snapshot (the faces not in set(bm.faces) taken before). Index ranges miss faces, because create_cube/create_cone reuse face slots. Use full-precision UVs (FULL_UV_MESHES).
  - CHECKS: TribeXR/Scripts/Blender/checks/ (they import grounds/atmosphere.py; point them at the club's STAGE_MOVES equivalent).
    - mover_emulate.py: the UE pose vs mover_pose_pq; crowd/DJ clearance sampled ALONG each beam axis.
    - mover_fbx_check.py <out dir>: FBX read-back (layer order; every vertex carries its fixture's values; yokes pan-only; distance limits; UE emulation).
    - Dino results: 0.001 cm; beams ≥ 3.31 m above the field and ≥ 5.59 m from the DJ's eyes.
- **v7, the moving heads move (2026-10-09 23:43).** Pak 793294ce (D:/TribeUE/MetaClub/TribeXR/Saved/ModPak/v7/), staged in backup/club4_pending/README.txt. Not yet on the headset.
  - Scripts/Blender/club/club_movers.py holds the five data layers and move_values().
    - Amplitudes (pan/tilt degrees): Hall 24/14, Bay 16/9, Floor 14/10.
    - Rest yaw = atan2(d.x, -d.y). u: hall hx/10, bay (k-3.5)/3.5, floor hx/7.5. x = (x+12)/24.
    - mover_pose_pq is a copy of atmosphere's.
    - SWEEP = 25 poses.
  - club_stage.build_rig v7:
    - Clamps and floor bases stay in the baked rig. Yokes (pan only) and heads go to SM_ClubMoverHeads.
    - The floor heads got yokes too (the Dino session's catch: 1536 → 1824 pan-only loops).
    - Lenses, beams and halos are stamped from snapshots.
    - Beam length = the shortest clear length over the sweep + 0.3 m. No pose goes through the floor, walls, ceiling or mezzanine slab.
    - club_moves.json goes to the checks.
  - club_materials:
    - mover_beams / mover_lens / mover_heads = the club's look + dm._mover_wpo.
    - near_fade: every beam fades within 1.5 m of the eye (VR comfort, in _beams).
  - build_club v7:
    - MOVERS switch on when the export has SM_ClubMoverHeads.
    - Full-precision UVs and ±800 cm bounds on the movers.
    - SHOW_NAMES + ShowPrevBar/ShowNextBar (the Dino's v14b seam fix): MPC_ClubShow has 28 scalars.
  - Check: club_mover_check.py (a copy of the Dino's mover_fbx_check plus DJ-eye clearance on densely sampled beam quads). PASS:
    - 38/38 fixtures, values exact, UE emulation 0.000 cm;
    - beams: Hall 9.61 m, Bay 23.62 m, Floor 15.91 m;
    - the DJ's eyes are at least 2.36 m from any beam in any pose.
  - Cook 0 errors, 68 entries.
- **Walking for big crowds (2026-10-09 23:00):**
  - club_collide.h 83ab550e: CC_MAXP 4608, CC_MAXB 512, and a 1 m person grid.
    - Visited in ascending index order, so the results are bit-identical to the full scan: 400k random queries per map, 0 mismatches.
    - 17-33× faster.
  - club.cpp 971a4293: the map buffer is 512 KB.
  - tests/club_collide_test.cpp 52ba3c1c: only `spot decks` is required, the state table holds 1M, MSVC builds it on the PC.
  - The Dino's dino_collide.txt (f6500d98, 4446 people) through the hook's C++: 556,744 states from the decks, 0 stuck.
- **Live on the headset (2026-10-10, pushed by the Dino session after the user said go):**
  - 08:43:39 APK combo1.aligned.apk (base.apk 8903d10b).
    - It carries club.cpp 971a4293 and club_collide.h 83ab550e unchanged, plus song14, head.cpp, intro.cpp (Graveyard stream intro) and gait.h (leg walk cycle).
    - The show bus is the same 19 names as v7's MPC_ClubShow (dumper.cpp d4f4f80f G_PARAMS).
  - 08:47:22 OBB db9445bc, recorded in paks_current/paks.txt:
    - chunk 50 87ec24ba (Dino v14b);
    - chunk 53 7420a9fc;
    - chunk 54 b3ce58e0 (Graveyard v4);
    - chunk 55 793294ce (Reactor v7).
  - Rollback: v6 1993790953ed43711008f55b7845f3d7 (D:/TribeUE/MetaClub/TribeXR/Saved/ModPak/v6/). v5 7ccef713 is in backup/club3_pending/.
  - Not yet seen by the user. To test:
    - the darkness (room/crowd 0.3, stage 0.6, rim 0.5);
    - the moving heads;
    - the lasers on every bar;
    - walking in Reactor.
  - Tuning the darkness is tribemod/club.txt `room= stage= crowd= rim=` (0..4), staged via /data/local/tmp, and needs the user's OK. No rebuild.

## First look at v7 and the darker crowd (2026-10-10 afternoon)
- 12:48 the Graveyard v5 push made the live OBB 2e5915c7; chunk 55 is still 793294ce (Reactor v7).
- 16:19:55 combo1's first launch (checked by the Dino session): walking works on the Dino Stage and Graveyard.
  "crowd make-way: PlayerX MISSING" off Reactor is expected: only MPC_ClubShow and the club's crowd material have
  PlayerX/PlayerY. The soft-crowd walking does not need them.
- 16:25 the user's first visit to Reactor v7 (pak defaults, no club.txt). The user, relayed by the Dino session at
  16:32: "So for reactor stage, the crowd is still WAY too bright".
- 16:41 tribemod/club.txt = `crowd=0.1 rim=0.15` (19 B, md5 7451ffed75fc961683afc5d431a6e30a): the crowd's bodies
  10% and its rim 15% of v5, a third of v7's defaults; the room (0.3) and stage (0.6) unchanged.
  - The user ran the adb one-liner themselves (`!` in the club chat): auto mode blocks this session's adb shell writes,
    even after the user's "push it".
  - combo1 logged at 16:41:32 "[CLUB] settings: ... | dimmers: crowd=0.10 rim=0.15" (club.txt is re-read every 2 s).
  - Copied into backup/tribemod_20261006/club.txt (same md5); the Dino session adds club.txt to reseed.sh's list.
  - If the crowd still reads too bright, check the crowd's glow items next: phones, glowsticks and LEDs are emissive
    (GlowBoost 1.6, `club_materials.py`) and not on the dimmers by design, so dimming them takes a pak rebuild.
- 16:40 the Reactor visuals went to /sdcard/Movies/Reactor Visuals/ (41 files, the Dino session's push_media.sh on the
  user's yes); details in TribeUE/Visuals/reactor/deliver/README.txt.

## v8: the lasers land on the floor (2026-10-11)
- The user, 2026-10-10 evening: "ok so i noticed that the lazers are stopping before they hit the floor. why are they
  doing that?"
  - Each beam is one fixed-length mesh that the engine turns about its aperture. v5-v7 cut every beam so that its lowest
    pose stayed above raised hands (2.3 m over the floor) and the mezzanine people, and off the stage and the DJ, so in
    the other poses the tips hung 2-6 m in the air.
  - The fade was also worse than I first told the user ("the last 15%"). BEAM_V1 0.85 stretched the texture's along-fade
    over each whole beam: about half the light at a third of the length, about 4 % at the tip.
- The user, 2026-10-11: "yeah let them hit the floor".
- `club_lasers.py` v8 (v7 kept as `club_lasers.v7.bak.py`):
  - Each beam is long enough to land on a surface in all 81 poses of its sweep: the floor, a wall, the ceiling, the stage
    front, a mezzanine deck top. LAND_MARGIN is 1.5 m: at 0.5 m one pole beam was 1 mm short at the hall's far corner,
    a landing that falls between the grid poses.
  - People are no longer avoided. Still forbidden: over the stage below 3 m, within 1.6 m of the DJ's head, and through
    the airlock roof (it isn't clipped).
  - The back units aim at the floor, (0.3x, -8, FLOOR), instead of 3.4 m above it. The rest descent goes from 16.5 to
    about 30 degrees, and they land between the units and the barrier. v7's aim reached the stage once the beams got
    longer.
  - Width and fade go per metre:
    - width 2 cm, rising to 10 cm at 15 m, then constant;
    - V_PER_M 0.0125: 75 % at 10 m, 58 % at 20 m, 43 % at 30 m;
    - 2.5 m segments while the beam widens, so the across-profile stays centred.
  - Lengths: front 31.2-33.7 m, poles 28.0-32.0 m, back 22.9-24.5 m (v7: 11.1-19.0 m). 1,920 tris (v7: 272).
  - Checks:
    - the solver: 0 of 5,508 poses short of a surface;
    - an independent check (scratchpad verify_lasers.py: analytic ray-plane hits, 3,004 random poses per beam): the tip
      is at least 1.00 m past every landing; the lowest open point over the stage is 8.33 m; the DJ's head is at least
      6.03 m away; 0 poses through the airlock roof; 0 back in sight after landing.
- `club_materials.laser_show` (new; v7 kept as `club_materials.v7.bak.py`): dm.laser_show (untouched), with its emissive
  multiplied by:
  - near_fade(20, 80 cm);
  - lids_keep: the Custom HLSL "LaserLids", 0 past a deck top. It takes the aperture from UV1/UV2 and the pixel in mesh
    local cm (TransformPosition world to local).
  - Reason for the clip: the beams run on past where they land, and the floor and walls hide that part, but a deck would
    let it out of its underside into the lounge.
  - `build_club.py` uses it and takes LIDS from club_lasers (v7 kept as `build_club.v7.bak.py`).
- No re-bake:
  - The housings didn't move: the back units' heading is unchanged horizontally.
  - `export_lasers.py` (new) wrote only SM_ClubLaserShow.fbx into `out_club_v8`, a copy of v7's `out_club`.
  - The FBX read-back has the same 76 per-beam data keys as v7, and lengths, v and widths as designed.
- UE build:
  - `CLUB_ANIM=1 CLUB_SRC=...\out_club_v8 cook_club.sh all`: 24 meshes. M_ClubLaserShow has 75 expressions from the
    Dino engine, 88 after the club's additions.
  - Cook: 0 errors, 3 warnings (the usual console ones). The laser shadermap was compiled for VULKAN_ES3_1_ANDROID.
  - One new, harmless log warning: LogPackageName GetLocalFullPath on T_ClubCore during its delete-and-reimport. The
    texture is identical in size to v7's.
  - Pak v8: 63,669,786 B, md5 616bbe282c7462b7c6189ae95e4a3667, in D:\TribeUE\MetaClub\TribeXR\Saved\ModPak\v8.
  - Compared with v7 (793294ce): the same 145 files, 142 the same size. Changed: SM_ClubLaserShow.uexp (+246,944 B),
    M_ClubLaserShow.uexp (-16 B), the chunk's Vulkan shader archive (+2,733 B).
- **LIVE 2026-10-11 16:57:10.** The user ran the push themselves (a `!` line in the club chat; auto mode blocks this
  session's adb writes): `bash scripts/push_obb.sh --push /d/TribeUE/MetaClub/TribeXR/Saved/ModPak/v8/pakchunk55-Android_ASTC_P.pak`.
  - It merged into the live f206696d (2026-10-10 20:03).
  - New OBB 9543557a665e3b8ead70d8f5fed3294d, 458,041,783 B: 50 87ec24ba, 53 7420a9fc, 54 ba4ebd92 (Graveyard v6),
    55 616bbe28.
  - Re-checked on the device (md5sum) and in the paks_current mirror. reseed.sh PATCH= points at the mirror.
  - The OBB lands shell:ext_obb_rw 644, as every push_obb.sh push does (readable: NOTES.md Session 3m).
  - club.txt is still 7451ffed. The Dino session was told.
  - Rollback: the v7 pak, 793294ce, in ModPak/v7.
  - Next: the user's look in the headset. If they'd rather have the front fans land in the crowd itself, aim them
    lower: their v8 landings are y -19.5..-30.5, the back half and the bar.

## 2026-10-11: free roam in the crowd (scoping only, nothing changed)
- The ask (the user via the Dino session): roam freely through the Reactor crowd, through the figures, like the free
  roam the Dino session is building for Graveyard (not a defined aisle).
- **Answer: Reactor already has it** (soft crowd since club2/club3, 2026-10-09; club.cpp 971a4293 in combo1-combo3).
  - The walking map has the 349 dancers as `person` lines, with only a 15 cm spine core solid (the rules line's 5th
    value).
  - club.cpp slows you to no less than 45 % and steers you round people. The crowd material's make-way pushes dancers
    up to 55 cm aside.
  - out_club_v8/club_collide.png shows the whole field reachable. The solid things out there: the barrier, the bar,
    the mezzanine edges, stairs and rails, the wall columns and the spine cores.
  - The backup copy of club_collide.txt is 75a3d758, the same as out_club(_v8)'s. The device copy was not read: the
    headset was off USB.
- **Looser, data only, if asked:** set the rules line's core to 0 (straight through) and shrink the person `r` (less
  slow-down). club_load_map re-reads club_collide.txt within about 2 s when its mtime changes, so there's no
  APK/pak/restart. The push is a user `!` line plus the backup copy.
  - The slow-down and drift constants (0.45, 0.35, 0.7) are hard-coded in club.cpp. Changing them needs an APK and
    affects every stage.
- **v8 lasers at eye height.** Model: scratchpad roam/eyelevel.py. Every beam over 21x21 poses; the open part (to the
  landing); 1.2-1.9 m above the floor, or above a deck top over the decks.
  - 87 % of the crowd floor's 0.5 m cells (barrier to back wall) is crossed in at least one pose: y -3.6..-10 55 %,
    -10..-19.5 91 %, -19.5..-30.5 100 %.

    | Group | Where, y (2-98 %) | Eye-level stretch before landing, median |
    |---|---|---|
    | front fans | -15.5..-26 | 1.6 m |
    | poles | -15..-30, full width | 3.0 m |
    | back truss | -7..-13 | 1.3 m |

  - This is the same for anyone standing in the crowd today; roaming adds no new case.
  - The guard is near_fade(20, 80 cm). It is untested in the headset. If sweeps across the face bother the user, widen
    it to the movers' 30-150 cm (a pak rebuild).
- Told the Dino session:
  - Graveyard's halloween_collide.txt (backup) has 0 person lines. Person lines give it the same soft crowd with no
    code change.
  - Its figures part only with PlayerX/PlayerY in its crowd material and in the show bus's collection.
  - It should check with this session before changing club.cpp's soft-crowd code (Reactor walks on it).

## 2026-10-16: the user's Reactor list, and combo4 (the side screens mirror the main screen)
- The user's list:
  1. more stuff on stage;
  2. a stack of speakers hanging from the roof on each side of the stage;
  3. a stack on both sides of the DJ booth;
  4. "I dont see anything on the screens left and right of the main screens";
  5. "the lazers are more focused on the back of the crowd";
  6. compare Graveyard's lasers and their music sync with ours;
  7. more visuals;
  8. one file for the full set.
- The user's choices (AskUserQuestion):
  - stage: LED pillars + effects on drops (CO2, sparks, strobe blinders) + reactor props;
  - side screens: the same as the main screen;
  - visuals: a mix of about 24 loops (4 reactor-style + 4 new-style looks, 3 colours each), then rebuild the full set.
- **Full set (item 8):** it already existed on the headset. The user couldn't tell which file it was.
  - Renamed on the headset and the PC (Visuals/reactor/deliver + README) to "00 FULL 1-HOUR SET - Reactor Visuals.mp4", so it sorts first.
  - 2,705,160,667 B, H.264 1080p30, 3600 s.
- **Side screens (item 4):** blank by design until now. build_club.py gives them MI_ClubSideScreens, an idle dim blue, with "phase 2: the mod mirrors the video".
  - club_stage.py screen_quad already gives SM_ClubSideScreens Tribe's backdrop UV0 layout, so no pak change is needed.
  - hook/club.cpp 748faaac (was 971a4293; the old one is in the scratchpad), club_side_screens():
    - runs on the club's map only, every ~0.4 s;
    - once g_emOurScreen is Tribe's backdrop, it finds SM_ClubSideScreens with em_find_mesh_actor (at most 5 object walks, ~2 s apart);
    - copies material 0 of the main screen's StaticMeshComponent onto it (GetMaterial/SetMaterial);
    - puts the idle material back while the backdrop actor is hidden (visuals off).
  - Logs: "[CLUB] side screens: found ...", "... mirroring the main screen (<material>)", "... visuals off: idle panels".
  - combo4 = combo3's tree + this club.cpp.
    - NDK build: 0 errors, the 7 old warnings. libhook_combo4.so is 390,016 B, md5 e7e2f019.
    - out/hookA/combo4.aligned.apk: 112,123,119 B, md5 045188e20cd4ac7261032d7a7b6e2086. libUnreal.so is identical to combo3's.
    - Staged in the scratchpad (out/hookA/stage untouched).
    - NOT INSTALLED: it needs the user's go with Tribe closed. Rollback: combo3 (a156adfc).
    - When installed, set reseed.sh MOD=combo4.
  - The two new tribe-hack sessions (57, 28) were told.

## v8b: the lasers' dark bars fixed and re-aimed into the crowd (2026-10-16)
- **Agent comparison (Graveyard vs Reactor).**
  - Both stages run the same laser engine (dm.laser_show) and the same show-bus sync: the hook pins the bar to the
    heard deck's playhead on the song's grid, plus sections, hits, bass and drops.
  - Graveyard: 9 groups over all 6 families, with the Dino's tables raw.
  - Reactor squeezes 3 groups into 2 families. **Bug (mine, v6):** club_laser_scenes.club_mask sent towers/delay scenes
    to the poles and back truss, whose cue rows are 0 in those bars.
    - 94 of 256 (variant, bar) had no laser that could light, in bars 0-7, 15 and 26-27 in every variant; Graveyard has 44.
    - Its dark_bars() check left the cue rows out, so it said 0. Recounted independently: 94, same bars.
  - The 4 front fans were clones: x = 0.5 + 0.02u, the Dino's one-centre-fan rule, so patterns never travelled across them.
- **Fixes (backups: club_show/club_laser_scenes/club_lasers .v8.bak.py; md5 373feb1a / ac69a736 / 4962f62c):**
  - club_laser_scenes: a mask with neither fan nor horns -> every club group; the club's cue rows decide.
    - dark_bars() now ANDs the scene mask with each group's cue level (GROUPS); main() asserts only DESIGNED_DARK {0-3, 15}.
  - club_show: sidelasers 0.4 in bars 4-7, 0.45-0.6 in 8-11, 0.5 in 24-27; backlasers 0.35 in 4-7, 0.4-0.7 in 8-14, 0.4 in 24-27.
  - Result: dark only in bars 0-3 and 15 (40 of 256). Lit bars per variant: fans 21.2 (was 14.5), poles 19.0 (9.9),
    back 19.0 (7.9).
  - club_lasers:
    - front fans aim (0.45x, -15, FLOOR) and poles (-sx 1.5, -17, FLOOR) (were z 2.4); headings unchanged, so the baked
      housings stay valid;
    - group 0 x = un["x"] + 0.02u (units at 0.229 / 0.41 / 0.59 / 0.771).
  - Solver: 0 of 5508 poses short; front 20.5-22.0 m, poles 18.8-19.5 m, back 22.9-24.5 m.
  - verify_lasers.py: tip past landing >= 1.51 m; over the stage >= 8.32 m; DJ head >= 6.03 m; airlock 0; reappear 0.
  - Floor landings (2-98 %): fans y -18.5..-12.4 (median -15.2; was -30..-18), poles -22.4..-12.2 (-17.2; was the far
    walls), back truss -11.1..-4.2 (-7.9).
- **Build:**
  - out_club_v8b = out_club_v8 + T_ClubCues (rows 4 and 5 only changed) + T_ClubLaserProg/Lib + SM_ClubLaserShow.fbx
    (export_lasers.py; 960 faces, the same 6 UV layers).
  - cook_club.sh all (CLUB_ANIM=1): build 223 s; cook 0 errors / 3 warnings; 68 manifest entries; 145 files.
  - **Pak v8b: D:/TribeUE/MetaClub/TribeXR/Saved/ModPak/v8b/pakchunk55-Android_ASTC_P.pak, 63,668,842 B, md5
    45a18154b27a267a797805a5c94529c1.**
  - Sizes against v8: 143 of 145 identical; SM_ClubLaserShow.uexp -928 B, the shader archive -16 B. (md5 differs on
    almost every file: re-saved packages.)
  - NOT PUSHED: needs the user's go (push_obb.sh --push ...v8b...). Rollback: v8 616bbe28.

## v9: stage additions, in progress (2026-10-16)
- **Pieces, all unbaked** (Scripts/Blender/club/club_extras.py; layout in plain Python, shared by the meshes, the beam checks
  and the walking map):
  - LED pillars on the old rod columns (+-3, 0.6): 0.62 m square, 5.2 m tall, enclosing the 0.28 m posts, so no re-bake.
  - Sidefill stacks at (+-3.35, -0.2): 2 subs + 1 top, 1.52 m, turned to the DJ's eyes.
  - Flown arrays at (+-10.9, -3.5): 6 elements in a J, toed in 20 deg, from the 9.8 m ceiling down to 7.30 m.
  - Along the deck lip: CO2 jets at x +-3.4 and +-7.4, spark fountains at +-1.5 and +-6.4, floor blinders at +-5.0.
  - Rod tubes at the wing corners (+-11.55, -2.3 / -1.45).
  - Coolant pipes along the wings' back (y 4.6) with risers at x +-11.6.
  - Hazard barriers behind the right wing's rail and beside the airlock stairs (y LIP_Y + 0.2).
  - 8 meshes, about 3,300 tris: SM_ClubGear, Grilles, Hazard, PillarLeds, PropGlow, Blinders, CO2, Sparks.
- **Placement vs beams** (scratchpad extras9: mover_dump.py saves 769,500 posed mover-beam samples, 38 fixtures x 25 poses):
  - The moving heads' sweeps cover almost all the air round the stage. No hang spot, truss-blinder spot or stack taller
    than 1.1 m is clear.
  - Picked the fewest (fixture, pose) crossings of 950:
    - arrays at +-10.9 x 6 elements: 16 (bay 14, floor 2); the first plan, +-10 x 8, had 33;
    - stacks 1.52 m: 4;
    - pillars: 30, the floor heads 34/35 (today's posts are already crossed in 22);
    - fx units: 7 and barriers: 3 (hall beams landing at the lip);
    - floor blinders, rod tubes, pipes: 0. Truss blinders would have had 14-23.
  - Lasers (v8b aims, 21x21 poses, 5 cm steps, 15 cm pad): none.
  - None in Tribe's SpectatorBoundingBox; nothing past the walls; the airlock stair landing stays free.
- **Show** (club_show.py new rows, comfort check passes):
  - pillars 8: intro 0.3, build rising, drop 1 with pulse, breakdown 0.25;
  - fx 9: drop 1, outro 0.5;
  - props 11: all the time, 0.3-1;
  - blinders 12: build end 0.6, drop 1;
  - the blackout bar zeroes them, but the pillars glimmer at 0.08.
- **Materials** (club_materials.py, after club_crowd; backup club_materials.v8.bak.py c01c15ce):
  - gear: dark + the crowd's rim x the stage level;
  - grilles: a diamond-dot grid; hazard: triangle-wave chevrons;
  - pillar_leds: 8x72 dot-matrix VU, beats 1/3 + bass + drop boom, blue to amber;
  - prop_glow: a v chase on the half-time beat x bass;
  - blinders: warm lamp discs, HitMajor/DropBoom x row, capped at 2.5;
  - co2: translucent sine billows, DropBoom x fx;
  - sparks: additive streaks, max(DropBoom, 0.7 HitMajor) x fx.
  - Both plumes collapse onto the nozzle by WPO while off and have the near-eye fade.
- **build_club.py:** SURFACES + EXTRAS, the animated branch calls cm.extras (backup build_club.v8.bak.py 5a11c5a6).
  export_extras.py writes the FBXs and adds them to manifest.txt.
- **Walking** (club_collide.py; backup club_collide.v8.bak.py 15e98d42): solids() as boxes / circles.
  ALL CHECKS PASS on out_club_v9: host everywhere, guests held at the gate, stage 170.3 of 199.2 m2 walkable.
- **Previews:** club_extras_preview.py (the club's FBXs and bakes + the additions, EEVEE, "drop" and "calm") ->
  claudedocs/club_concept/v9_preview/, under the shared GPU lock.
- **Build source:** out_club_v9 = out_club_v8b + T_ClubCues (rows 8, 9, 11, 12) + the 8 FBXs + club_collide.txt.
- **v9 build (before the user's approval of the previews):**
  - cook_club.sh all (CLUB_ANIM=1, CLUB_SRC=out_club_v9): build 61 s. The 8 materials compiled (53-105 expressions each).
  - Cook: 0 errors, 3 warnings (the usual); manifest 84 entries (v8b 68); 177 files (145).
  - **Pak v9: ModPak/v9/pakchunk55-Android_ASTC_P.pak, 64,185,754 B, md5 326cad29299c16386119688f92e0a668.**
  - NOT PUSHED: the previews come first. The walking map (out_club_v9/club_collide.txt) goes on with it as a tribemod
    push plus the backup copy.
- **combo5 (2026-10-16 21:18) supersedes combo4 for installing.**
  - The Dino session changed dumper.cpp after combo4: 2616d9fc -> 7752cd1d, EM_MAX 4 -> 8, a christmas SHOWS row
    (MPC_XmShow), a sizeof loop bound. tribe-hack-28 relayed it and asked for a rebuild.
  - combo5 = dumper.cpp 7752cd1d + club.cpp 748faaac (the side screens) + the rest unchanged.
  - Build: 0 errors, the same 7 warnings. libhook_combo5.so md5 3c25a799.
  - out/hookA/combo5.aligned.apk: 112,123,119 B, md5 2bee4163e689775088a52b6312600a57.
  - combo4 (045188e2) kept as built. Not installed (headset off USB).
  - After the install: the "[ENV] added box" lines (8 when envs.txt has 8) and "[CLUB] side screens"; then reseed.sh MOD=combo5.
- **v9 round 2 (after looking at the previews myself):**
  - The speakers read as plain boxes. club_materials.grilles now draws woofer cones (a dark body, a lighter surround, a
    dust cap) and, on the array elements, a horn: cone - horn - cone. The cabinet kind rides in the grille's UV u
    (kind + 0.01 + 0.96 x across; club_extras.cabinet(kind=)). 143 expressions.
  - Gear rim toned down: GEAR_RGB (0.045, 0.047, 0.052), GEAR_RIM (0.17, 0.19, 0.23), exponent 4. The fx units looked
    light grey up close.
  - The preview script mirrors both changes; PREVIEW_VIEWS= renders a subset, with new views speakers_close and
    array_close.
  - **Pak v9 (rebuilt, replaces the first one): 64,186,471 B, md5 2f7df8cfdafda161a93e921c069e01d4.** 0 errors /
    3 warnings, 177 files. Not pushed.
- **combo6 (2026-10-17) supersedes combo5 for installing.** tribe-hack-28 (MIDTOWN, Christmas) asked for the side
  screens on its map too: club.cpp:292 now also accepts "christmas_collide.txt" (748faaac -> fc5a5dfe; old copy in the
  scratchpad).
  - MIDTOWN's billboards: one actor with mesh SM_ClubSideScreens, UV0 in the main screen's layout.
  - combo6 = dumper.cpp 7752cd1d + club.cpp fc5a5dfe + the rest unchanged. The same 7 warnings; libhook_combo6.so
    a08aa604.
  - out/hookA/combo6.aligned.apk: 112,123,119 B, md5 0ca580ec9e39c58f2841e8e2b2477796.
  - Not installed: the headset ran combo3 at 09:45 per tribe-hack-28. After the install: reseed.sh MOD=combo6.
- **combo7 (2026-10-17 12:21) supersedes combo6 for installing.** tribe-hack-57 (HARVEST MOON, Thanksgiving) added one
  SHOWS row to dumper.cpp (7752cd1d -> 4476d98c) and asked for the build; the user had OK'd that plan in its chat.
  - The diff against a 7752cd1d copy (884abbe3's scratchpad) is that one row: {"harvest", .../MPC_HmShow...}. The loop
    bound is sizeof-based and em_active_folder lowercases the folder, so "Harvest" matches. Only dumper.cpp is newer than
    libhook_combo6.so.
  - combo7 = dumper.cpp 4476d98c + club.cpp fc5a5dfe + the rest unchanged. The same 7 warnings; libhook_combo7.so
    20adb374 (MPC_HmShow in the binary).
  - out/hookA/combo7.aligned.apk: 112,123,119 B, md5 70f69fc42e758c0db61afe476902037d. Same signing cert as combo6.
  - Not installed. After the install: reseed.sh MOD=combo7. A Harvest visit logs "[GIANT] no show collection for
    stage folder 'harvest'" until Harvest's v1 pak (with MPC_HmShow) is pushed; that is expected.
- **combo8 (2026-10-17 12:49) supersedes combo7 for installing.** tribe-hack-0c (RED EYE) changed dumper.cpp after
  combo7 was built (4476d98c -> 3476d016, its user's OK in its chat) and asked for the build. Named combo8 rather than
  rebuilding combo7, because combo7's md5 had already gone to the Thanksgiving chat.
  - The diff against 4476d98c (copy in f33276f9's scratchpad, md5 checked) and against 7752cd1d is exactly: a last
    SHOWS row {"redeye", .../MPC_ReShow...}, and :2567 g_gHasGiant=(dino||!strcmp(SHOWS[si][0],"redeye"))&&n[GP_H]
    (si >= 0 there: the !c return comes first). No effect until a RED EYE pak ships MPC_ReShow with a Height scalar.
  - Then RED EYE gets the Dino lift: the button at the fixed G_BTN (0, 152, 106) cm, the song lift=, VROrigin raised by
    giant_set_rel, and the shared giant.txt (height, rise, descend, press). The spot light is null-safe. Sent to 0c.
  - combo8 = dumper.cpp 3476d016 (copy: scratchpad/combo8/dumper.cpp.used) + club.cpp fc5a5dfe + the rest unchanged.
    The same 7 warnings; libhook_combo8.so 6c5271a2 (MPC_ReShow and MPC_HmShow in the binary).
  - out/hookA/combo8.aligned.apk: 112,123,119 B, md5 7d6a9051ef5716f74a171900679d0079. Same signing cert. The packed
    libhook.so matches the built one. (The APK size has been the same since combo6, although the .so grew from 390,552 to
    391,032 B. Most likely apksigner's padding absorbs a few hundred bytes; the content check is the extracted-lib md5.)
  - Not installed. The user is holding installs until the other stage chats finish, then wants me to run them (not
    `!` lines). After the install: reseed.sh MOD=combo8.
- **Batch push 2026-10-17 19:03-19:05 (the user: "just push all of it"; Tribe not running; MIDTOWN not ready, left out):**
  - **combo8 INSTALLED 19:03:27** (`adb install -r`; this session's adb writes were not blocked this time). The
    headset's base.apk md5 is 7d6a9051 = combo8. firstInstallTime unchanged (2026-10-16 19:10:56), so data and login stay.
  - **OBB 395dbe6e -> 1a384762** (563,882,016 B, device md5 checked), one push_obb.sh run:
    - chunk 55 v8 616bbe28 -> **v9 2f7df8cf** (stage additions + the v8b lasers);
    - chunk 57 **Harvest v1 981356dd** added (its notes' md5), with --env "Harvest Moon=..." (box 5);
    - 50 / 53 / 54 / 59 unchanged. Log: scratchpad/push_v9_harvest.log.
  - **tribemod:** club_collide.txt 75a3d758 -> b3234184 (out_club_v9), and envs.txt + "Dino Classic=/Game/Mods/DinoAnim/
    Maps/Environment_Dino" as line 6, so 6 boxes (d28abb42). Both were copied into backup/tribemod_20261006 (reseed.sh
    lists both). Rollback copies: scratchpad/push_1017/.
  - reseed.sh MOD stays combo3 until combo8's first launch is checked in the log.
- **MIDTOWN pushed from this chat, 19:09-19:12** (the user: "well lets get midtown in there too"; tribe-hack-28 told
  first). The command was its own `Scripts/Blender/christmas/push_midtown.sh --push --media D:/TribeUE/Visuals/christmas/
  deliver paks_current/staging/xm_20261017_1237`, read in full first; the inputs matched its notes.
  - OBB 1a384762 -> **0971dd30** (7 paks: + 58 Midtown v1 5789312c; 55 still v9 2f7df8cf). Re-read on the device.
  - envs.txt has 7 boxes, Midtown last (c16d5102, = the backup). Midtown's 3 texts and the Santa skin and head are in
    tribemod; 28 videos are in /sdcard/Movies/Midtown Visuals. The headset has 20 GB free. Log: scratchpad/push_midtown.log.
  - reseed.sh's restore list still lacks the new stages' tribemod files (the Dino chat's file, and it is closed). The
    user's Fix Tribe Login.exe is not affected: fix_login.sh snapshots and restores every tribemod file.
- **combo9 (2026-10-17 20:5x) supersedes combo8 for installing.** tribe-hack-eb (Halloween) added the Graveyard
  camera-menu button ("Crowd", a FOH mausoleum view) at the user's request in its chat:
  - **Sources:** dumper.cpp 3476d016 -> 040839da (only hook-ins) and the new hook/camview.cpp 1a2f6f67. Copies are in
    scratchpad/combo9/*.used.
  - **Review** (diff against combo8's dumper.cpp.used): the DShot fov= field (sh is memset, so the default is 0); the
    view pose in drone_update before the intro's; drone_poll need |= g_viewArmed; the include; the ticks; camview_poll
    every ~1 s.
  - **camview_pe in repl_pe** returns early only for W_VisualsMenu's BndEvt *CameraButton* handlers, after calling
    orig_pe itself. The env list's BndEvt (g_emFnListEvt) is not one of them, and no other code watches camera buttons.
    Off Graveyard, g_cvMenu stays 0, so it costs a compare.
  - **Build:** the same 7 warnings; libhook_combo9.so a6184cf9 ([CAMVIEW] 18 strings).
  - **out/hookA/combo9.aligned.apk:** 112,135,407 B, md5 2c747dd92ebc41efbafda2defeb8fb80. Same cert; the packed lib
    matches.
  - **Not installed.** Halloween pushes camview.halloween.txt and the v8 drone_path.halloween.txt with it, plus the backup
    copies. After the install: reseed.sh MOD=combo9 (once the first launch checks out).

## Hands through hats: the crowd fix (2026-10-18, code done, rebuild waiting)
- **Report:** tribe-hack-28 (MIDTOWN) measured that club_crowd.py (5784faba) kept crowd3's clap (the hands come down to
  ~15 cm over the head's centre) with no hat rule. RED EYE found the bug first; the user told MIDTOWN "fix it all".
  MIDTOWN's arm check (hat_clash.py: every frame of the 17 clips, arms and headwear both skinned) for the club, near tier:
  cowboy clap 38 edges / 3.7 cm deep, wave 14, heart 4, hold 3, ride 3; bucket clap 32 / 2.9 cm, wave 2; cap brim clap 2;
  horns clap 14; ears clap 2; goggles clap 4. Clean: the beanie (dome + pom) and the flower crown; handsup with every part.
- **Fix (club_crowd.py 5784faba -> abf25020; backup club_crowd.v9.bak.py):** HAT_CLIP_SWAP keyed by the headwear PART
  (club_crowd keeps no hat name), applied by `_hat_clip_swaps(people)` as the last step of build_people. A dancer goes to
  handsup at rate 1.0 (handsup is never half time; a heart's free phase snaps to the nearest beat). Hold / ride take the
  part off. It draws nothing from the rng. The VAT json gets "hat_swaps"; the log line prints it.
- **Checked** (scratchpad/hatcheck/: club_people_dump.py = club_stage.build_crowd's exact call; club_compare.py):
  - The old module's dump reproduces the live crowd: T_CheckVAT.exr = out_club_v9's T_ClubCrowdVAT.exr (f331a334), and
    the VAT json is equal except the texture name.
  - The new crowd: 352 people, every field except clip / parts / phase / rate identical; **10 changed**, 0 bad changes:
    clap -> handsup 5 (horns 2, goggles, bucket, cowboy at half time -> full), heart -> handsup 4 (cowboy, phase
    snapped), 1 rider's cowboy hat off. Worn headwear the measured arms go through: 10 -> **0**. All 31 handsup on the
    beat at rate 1.0. The VAT texture is unchanged (f331a334); body tris 310,732 -> 310,678 (the rider's hat).
  - hat_clash.py re-run on the new module gives MIDTOWN's table exactly (the canon and the clips are untouched).
  - MIDTOWN's later scan of every part that rides the head added onesie (its hood) {clap} (near 8 edges) and antennae
    {clap} (near 1). Both are in the table now. Nobody in this crowd is affected: there are no onesies, and the one
    alien sways. The re-run dump is byte-identical to the checked one.
- **Rebuild, not run:** the auto-mode classifier blocked the GPU bake ("Interfere With Workloads"; MIDTOWN's xm_stage.py
  held the GPU lock). It waits for the user's go in this chat:
  1. `bash Scripts/Blender/club/bake_club.sh out_club_v10_bake bake_club_v10` (full club_stage.py, ~6 min under the
     yielding GPU lock).
  2. out_club_v10 = out_club_v9 + the bake's SM_ClubCrowd.fbx, SM_ClubPhones.fbx, T_ClubCrowdLight.png,
     T_ClubCrowdVAT.exr / .json (everything else stays v9's bytes). The crowd files have been the v7 bake's since 10-09.
  3. `CLUB_ANIM=1 CLUB_SRC='C:\...\out_club_v10' cook_club.sh all` (Unreal -nullrhi), pak -> ModPak/v10.
  4. push_obb.sh with every current pak (55 -> v10); it closes Tribe, so ask first. It can go with the combo9 install.

## combo9 installed (by Halloween) and the re-seed list (2026-10-18)
- **combo9 INSTALLED 10:52:24** by tribe-hack-eb, on the user's "just do it now" in its chat, with Tribe closed. It also
  pushed tribemod camview.halloween.txt cdb4f106 (a new file name) and drone_path.halloween.txt 45406c4f (reel v8), with
  backup copies.
- Checked by me on the device at 10:53: base.apk 2c747dd9, firstInstallTime 2026-10-16 19:10:56 (unchanged), both texts
  as stated, and the backups the same. The OBB is unchanged (0971dd30). Tribe has not run since the install.
- **reseed.sh restore list** (lines 85-90, now 55b3f35b, bash -n OK): + camview.halloween.txt and MIDTOWN's three
  backed-up texts (christmas_collide, intro.christmas, drone_path.christmas). I compared the headset's tribemod against
  backup/tribemod_20261006 and the list; no other environment file was missing. RED EYE and Harvest have no tribemod
  files yet.
- **KEEP_SKINS** lacks santa (on the headset since 10-17 19:10; PC copies = headset, f0b35316 / 1fcd5d46) and majortom.
  Harvest owns that edit once the user says yes in its chat, and I asked it to add santa in the same edit.
- **MOD=** is still combo3. It becomes combo9 after combo9's first launch checks out in the log ("[ENV] added box" x7,
  no crash, "[CLUB] side screens" on a Reactor visit).
- **10:57 the user here: "tell them all yes or whatever".** I relayed it verbatim to every chat. RED EYE, MIDTOWN and
  Harvest still wanted the user's own word for headset writes, and got it in their own chats.
  - reseed.sh on that word: KEEP_SKINS + santa majortom gremlin, and the restore list + RED EYE's 3 texts (now 3c9384d6,
    bash -n OK; every kept skin exists in skins/).
- **RED EYE pushed itself 11:06-11:09** (the user's "push" in its chat): OBB 0971dd30 -> **19b1ad51** (59 = a9ec0b21). I
  checked it on the device and in paks_current. Halloween's 54 push started at 11:11.
- **My "push all" batch** (on the user's word here, one push at a time, after the other chats' done messages):
  - MIDTOWN's push_midtown.sh --push xm_20261018_1034 (58 -> b911f8c4); the dry run passed at 11:03.
  - Harvest's push_harvest.sh --push --skin-only (Major Tom, cleared in its chat); the dry run passed at 11:04.
  - Reactor v10, once the user starts the bake: scratchpad/start_reactor_bake.ps1, which runs bake_club.sh detached,
    because auto mode blocks me from starting it.
- **"push all" (the user here, 11:16):** Halloween's 54 push had finished at 11:12 (OBB 4929c79f, 54 = dd1ae112).
  - MIDTOWN's push_midtown.sh --push xm_20261018_1034, 11:16-11:17, exit 0: OBB 4929c79f -> **2fd1e39c** (58 =
    b911f8c4, the other 6 unchanged; device md5 = merge). Texts and Santa re-put (byte-identical), backups copied.
    Log: scratchpad/push_1018_midtown.log.
  - Harvest's push_harvest.sh --push --skin-only, 11:17, exit 0: skins/heads majortom.glb a4f19156 / 37e1ab21,
    md5-checked. Log: scratchpad/push_1018_majortom.log.
  - Reactor v10 was NOT built: MIDTOWN's renders hold the GPU (~1 h), and the user agreed to leave it. The crowd fix
    (club_crowd.py abf25020) ships with the next Reactor build.
  - Headset after: combo9; skins gremlin, horseman, lampwing, majortom, santa, skullbuck; 7 menu boxes; logcat 16 MiB.
  - Next: combo9's first launch in the log, then reseed.sh MOD=combo9.

## combo9's first launch, MOD=combo9 and Harvest's re-seed files (2026-10-18 12:22-12:31)
- **Harvest v3 LIVE 12:22:39** (the user ran push_harvest.sh as a `!` line in the Harvest chat): OBB 2fd1e39c ->
  **7312c013**, 57 = d63be7e3, the other 6 chunks unchanged (paks_current/paks.txt; patch_live.obb = device OBB).
  - Its three tribemod texts are on the headset and in backup/tribemod_20261006, headset = backup (checked):
    harvest_collide.txt 764745f1, intro.harvest.txt 8ed969cd, drone_path.harvest.txt 6a5855a0.
- **combo9's first launch, 12:27:51** (pid 10028). The TRIBEMOD log had nothing after 10:52:08 until then.
  - "dumper libhook constructor", [ENV] box 0-6 (all 7, as in envs.txt), the avatar ("A2: 120 frames driven OK").
  - 12:29:28 the process died while cached (am_proc_died 905,19), with no am_crash and an empty crash buffer. Tribe
    reopened at 12:29:33 (pid 11029). So the user closed and reopened it; it didn't crash.
  - 12:30:22 "'Harvest Moon' is IN (visible after 1 s)", visuals on MI_HmVisualScreen.
  - Not seen yet: [CAMVIEW] (no Graveyard visit) and "[CLUB] side screens" (no Reactor visit).
- **reseed.sh 3c9384d6 -> a45750b5** (bash -n OK; the old one is in scratchpad/reseed.3c9384d6.sh):
  - MOD=out/hookA/combo9.aligned.apk (2c747dd9). combo8 and combo3 are added to the list of earlier builds.
  - The restore list gained harvest_collide.txt, intro.harvest.txt and drone_path.harvest.txt. Harvest asked for this
    and left the edit to me. bash's own parse of the loop gives 23 names, all of them in backup/tribemod_20261006.
  - The preflight files all exist (checked with the script's own assignments): MOD 2c747dd9, PATCH 7312c013, the 6
    kept skins.
- **fix_login.sh needs no list.** It snapshots the headset's whole tribemod folder and the patch OBB (pulling the OBB
  when the PC mirror differs), then reinstalls the APK it pulled from the headset. Only the by-hand reseed.sh keeps lists.
- I told Harvest and Halloween. The user has been in Tribe (Harvest Moon) since 12:29, so no pushes until they're out.
- **RED EYE v3 pushed 18:16** by tribe-hack-0c on the user's "push" in its chat: OBB 7312c013 -> **c96295be**, 59 =
  cbd6d7d1. My own check at 18:17, made by reading the zip itself rather than paks.txt: all 7 paks are there (50
  87ec24ba, 53 7420a9fc, 54 dd1ae112, 55 2f7df8cf, 57 d63be7e3, 58 b911f8c4, 59 cbd6d7d1). Device OBB = mirror. The
  RED EYE texts on the headset = the backups (37fcd461, 9625c3c5, 872930fb). reseed.sh is unchanged (same names), and
  Tribe was closed.

## combo11 (2026-10-20, built for Harvest's intro descent)
- **Asked by tribe-hack-30 (Harvest)** on the user's behalf, because the user couldn't find this chat. Harvest edited
  hook/intro_ride.h (85591052) and hook/intro.cpp (35b04fa7) on 10-20 11:22: an opt-in "descent" line, so the stream
  camera follows the UFO down. Files without that line behave as before.
- **Sources:** dumper.cpp 040839da, camview.cpp 1a2f6f67, club.cpp fc5a5dfe, head.cpp 6bfa9ead, gait.h ea05eff4,
  club_collide.h 83ab550e, intro.cpp 35b04fa7, intro_ride.h 85591052. Copies are in scratchpad/combo11/*.used.
- **Build:** compile exit 0 with the same 7 warnings as combo9; libhook_combo11.so 598cff88.
- **Strings diff against combo10's packed lib** (combo10 = c48a2e38, built 10-19 by another chat; it's what is
  installed): nothing of combo10's is missing. The only new string is "descent"; the rest is code noise.
- **out/hookA/combo11.aligned.apk:** 112,139,503 B, md5 66edc6cb92cf02a4660d73a981a9a108. Same cert as combo10; the
  packed lib matches.
- **NOT installed.** The install waits for the user's OK. After it: the first-launch check, then reseed.sh MOD=combo11.
- **10-20 11:30 combo11 INSTALLED** by Harvest on the user's "install it" in its chat (base.apk 66edc6cb). The 10:14:40
  firstInstallTime is the Desktop login fix (fix_login.log: DONE 10:15). MOD= stays combo10 until combo11's first launch.
- **10-20 12:04 Harvest v4 pushed** (Harvest's chat, the user's "push it"): OBB 1c2c5edc -> 4ee42c1d. My check of the
  zip itself: 50 87ec24ba, 53 7420a9fc, 54 5e57a8dc, 55 2f7df8cf, 57 ef955566, 58 b911f8c4, 59 cbd6d7d1; device =
  mirror. Harvest texts headset = backup (eb1e8fd9, 90c5ee66 with the descent line, b47adcac).

## combo12 (2026-10-20, Harvest's moving button + autoshow)
- Asked by tribe-hack-30 (Harvest; the user asked in its chat): intro_ride.h 828bc46a (autoshow, buttonactor
  <name> [travel=cm]), intro.cpp 9a9aef05 (the button actor moves down on approach and springs back; press 2 queues the
  show when autoshow is on). Opt-in per intro file. Other sources as combo11. Copies in scratchpad/combo12/*.used.
- Compile exit 0, the same 7 warnings; libhook_combo12.so 4744f53f. The strings diff against combo11 shows only the new
  button/autoshow strings (and the press-2 log line gained a %s).
- out/hookA/combo12.aligned.apk: md5 below in the chat to Harvest; same cert, packed lib matches. NOT installed;
  Harvest asks the user and installs. combo11's first launch was never checked; MOD stays combo10 until a combo
  launches cleanly.
- combo12.aligned.apk md5 46babf9f08d78d5927b6242edfd6296d
- **10-20 17:29 combo12 INSTALLED + Harvest v4.1 pushed** (Harvest's chat): base.apk 46babf9f; OBB 5792a06f (zip
  checked: 57 = dada26f3, the other 6 unchanged); intro.harvest.txt b4339805 headset = backup.
- **combo12's first launch 17:37** (closed and reopened 17:38, cached death, empty crash buffer): 7 boxes, Harvest
  Moon IN, HmButton found. Press 1 17:40:16; press 2 17:41:37 "showtime follows once the camera holds (autoshow)";
  the camera held 17:41:57 and showtime ran on its own; the camera went back 17:42:11, after the door finished rising.
  The log has no line for the button's travel or for the descent aim, so those two are by eye only.
- **reseed.sh 3b8a7c5c -> 9a3fb47a:** MOD=combo12 (bash -n OK, 0 CR; the old copy is scratchpad/reseed.3b8a7c5c.sh).
- **10-20 19:27 Harvest v4.2 pushed** (Harvest chat): OBB 5792a06f -> 45a75e3c; zip checked, 57 = 45d8a908, the other 6
  unchanged; device = mirror; Harvest texts headset = backup (c54e22aa, b4339805, b403b149).
