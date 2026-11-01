# mod2311 builds A, B, C: what changed, why, and how sure

2026-10-31, the build job (headless). The plan in plain words is claudedocs/mod_2311_plan.md; this is the record of
every change. Labels: **(O)** observed (read or ran it), **(D)** derived (steps given), **(A)** assumed. Nothing was
installed, pushed or run on the headset; adb was not used by this job at all.

## 1. The builds

All in `backup/mod2311_build/`. Each APK = Tribe's 2311 store APK minus META-INF, with the mod's manifest
(backup/mod_fix_stream_fallback/manifest), the LIEF-patched libUnreal (backup/mod_fix_work/lib) and this libhook.so,
signed by scripts/sign_apk.sh (tools/make_apk.py, tools/build_all.sh).

| Step | APK | APK md5 | APK bytes | libhook.so | libhook md5 | libhook bytes | Source |
|---|---|---|---|---|---|---|---|
| A | mod2311_A.apk | fb2293b64af51630069f2e26bd482f44 | 115,407,687 | mod2311_A_libhook.so | 82212c073c80877ea011c75b9200b9ba | 516,496 | src_A/ |
| B | mod2311_B.apk | 7b263977a3374a38736eaf14032167f9 | 115,419,975 | mod2311_B_libhook.so | 5672a8a9809878258b92aaf9edc40098 | 538,944 | src_B/ |
| C | mod2311_C.apk | 8feaaad05f67ec3ebf3e62b3ecb3fdd0 | 115,419,975 | mod2311_C_libhook.so | acee994407adfcbddcc8ab0c63042d77 | 541,632 | src_C/ (= src/) |

(B and C have the same APK size because apksigner pads the signing block to 4 KB; their libraries differ, O.)
`builds.txt` lists these md5s for scripts/launch_check.sh. Diffs: `diff_A_vs_live.diff`, `diff_B_vs_A.diff`,
`diff_C_vs_B.diff`, `diff_C_vs_live.diff` (live = backup/mod_fix_stream_fix/src, which was not edited).

**Checks run (O):**
- Compile, the brief's command line: exit 0, **7 warnings, the same set as today's builds** (4 × -Wformat-nonliteral,
  unused `nm`, `OBJOBJECTS`, `RVA_NamePool`), for A, B and C. No new warning.
- APK compare (tools/compare_apk.py) with combo_pedriver_2311.apk: 707 vs 707 entries; only
  `lib/arm64-v8a/libhook.so`, `META-INF/MANIFEST.MF`, `META-INF/TRIBE.SF`, `META-INF/TRIBE.RSA` differ, for A, B and C.
  `apksigner verify` passed for each.
- Each APK's libhook.so md5 equals its `mod2311_<X>_libhook.so`.
- 2311 addresses (tools/verify_2311.py on libUnreal.2311.store.so + .patched.so): 12 checks, all PASS (section 3).
- tests/launch_check_test.sh (mock adb): 43 passed, 0 failed.
- One review of the final diff (a subagent, read-only): section 5.

## 2. Every change

Line numbers are in `src_C/` (the final tree); the same functions exist in src_A/src_B where the step says so.
Confidence: **high** = the mechanism is checked by reading plus the binary or the evidence; **medium** = sound by
reading, depends on runtime behaviour not seen; **low** = a guess that only the headset can settle.

### Step A: startup reliability and the crash fixes

| # | File: function (line) | What changed | Why | Confidence |
|---|---|---|---|---|
| A1 | dumper.cpp: `pe_hook_ctor` (4783), `pe_patch_ok` (4777), `tribemod_state` (4771), `on_load` (4807); `pe_install_try`/`pe_install_thread` removed | ProcessEvent is hooked in the constructor before any thread is created: `maps_rx` (a fresh local read of /proc/self/maps) must show the code r-x; the first word must be `0xA9BA7BFD`; after `A64HookFunction` the words are checked in all three forms And64InlineHook writes (NOP/LDR/BR + target, LDR/BR + target, B) and `orig_pe` must be set; up to 5 tries 20 ms apart, never a second patch once anything was written (then every call passes straight through). `tribemod/` unreadable -> hooked in pass-through (`g_mod_on=0`); readable without `executor_on` -> safe mode (no patch). | Load doc 2a: 13:40 had no hook because the constructor couldn't read `tribemod/` and never tried again; 14:26 had no hook, likely the prologue read racing the poll thread's rebuild of the shared range table (D: in combo_pedriver the hook ran after the threads started and read through `sr()`; the poll thread's first `stream_poll` -> `st_hook_send` -> `load_maps()` zeroes `g_nranges` first). peretry's retry thread re-patched under a running game thread (load doc). Notes 6, 13. | high (mechanism); the 14:26 cause stays D |
| A2 | dumper.cpp: `modon_poll` (4546) | Pass-through -> on as soon as `executor_on` can be read (checked every 1 s); readable-without-it -> safe mode for the session. | The other half of A1. | high |
| A3 | stream.cpp: `st_hook_one` (105), `st_hook_send`, `stream_poll` | Tribe's two encoder re-send hooks are installed from the constructor right after ProcessEvent (same `maps_rx` check, direct read of the 16-byte heads); the mprotect and `load_maps()` on the poll thread are gone. | Load doc 3.1 change 3: no code patching under a running game, no poll-thread table rewrite. | high |
| A4 | dumper.cpp: `ini_upsert` (825) | Returns at once (one log line) when `tribemod_state()<0`. | Load doc 1a: an unreadable `tribemod/` read every file as absent and deleted the RPM URL and body-tracking keys. | high |
| A5 | dumper.cpp: `load_maps_since`/`load_maps` (80), `in_range` (98) | Four range tables with sequence numbers; a rebuild fills one that isn't published, then publishes it; a reader retries if the sequence moved during its search; a miss rebuilds unless another thread published a newer table since the miss. | Levels doc 7 / load doc 3.2: the one shared table was emptied and refilled while other threads searched it. | high |
| A6 | dumper.cpp: `GuardSlot`/`guard_slot`, `segv_handler` (129), `segv_chain`, `install_guard`/`remove_guard` (133), `sr` (144), `run_guarded` (1494) | One guard slot per thread (keyed by `pthread_self`, claimed with a CAS); `sigsetjmp(...,0)` and an explicit unblock after a recovered fault; handler with SA_ONSTACK; install/remove counted under a mutex and never saving our own handler as the "old" one; `run_guarded` = guard up while the load runs (the old outer jump target was overwritten by the first read anyway). | Note 13 / levels doc 7: one `sigjmp_buf` and one flag for all threads: one thread's read could overwrite another's jump target (a jump onto another thread's stack) or turn its guard off. Also found here (D): a dump overlapping a load stored our own handler as the old one, so a real crash afterwards recursed in the handler. | high |
| A7 | dumper.cpp: `is_game_thread` + `repl_pe` (3850) | `repl_pe` passes every call straight through unless the mod is on and the caller is the thread named `GameThread` (the 13:57 tombstone: tid 24243, name GameThread, O); learned with one `prctl` per 64 calls until found. `call_uf` refuses other threads once known. | Found here (O in code): the per-frame driver and every request drain (loads, spawns, body tracking) ran on whichever thread called ProcessEvent next. Whether other threads call it on 2311 is (A); the gate costs one compare. | high (safe either way) |
| A8 | dumper.cpp: `obj_live` (1052), `gc_dead_mask` (193), `cls_is` (1063), `fn_sig` (1071), `call_skip` (1085), `call_uf` (1090); `obj_alive` = `obj_live` | Before every engine call: the object is in its object-array slot and passes the engine's own dead test (`flags & (*GUnreachableObjectFlag | Garbage)`, GOT slot runtime 0x8679A30, verified); it is a subclass of the function's class (cached is-a; interface functions skip this); every non-null ObjectProperty parameter passes the same two tests against its PropertyClass. Failures skip the call (logged once per function, counted in `skips=`). | Note 8 / note 12: the 13:57 crash handed a stale object to the engine; the trigger is unknown, so the check is applied to every call rather than to a list of cached pointers. A freed slot reused by another class fails the class test. See section 6 for how this differs from the load doc's WRef. | high (mechanism), medium (no false positives: checked by reading every call site, review agreed) |
| A9 | dumper.cpp: `show_coll_ok` (3084), `show_drop` (3092), `show_adopt` (3095), `giant_lookup` (3110), `giant_mpc` (3160), `show_key`, `show_set` (3164), `giant_reset`, `giant_tick` (3584), `em_unload` (3017), `env_menu_tick`; intro.cpp: `intro_tick` (276) | The levels doc's S1, as written there: the show collection is found once per stage load (`g_emLoadGen`) on the poll thread, adopted on the game thread only with a non-zero weak serial, and checked before every write (slot, serial, dead flags, class, name); dropped at every unload and when the check fails. | The 13:57:37 crash (both docs, high on mechanism). | high |
| A10 | dumper.cpp: `follow_update` (1280), `load_status` (1024) | The follow log counts its own runs (one line per 3600); `load_result.txt` rotates to `load_result.1.txt` at 1 MB. | Note 7 / load doc 2f: a line per frame, 33.6 MB, and the flood that rotated the crash session's logs out of logcat. | high |
| A11 | dumper.cpp: `pawn_of_cam_mgr` (1308), `follow_wire` (1312), `world_wire` (1333), `world_poll` (4555); `fallback_wire` and the ReceiveTick driver removed | The poll thread finds the camera manager and Tribe's local pawn and asks the game thread to wire it; the per-frame driver runs whenever that pawn is alive, with or without our avatar actor (each part checks its own needs, note 10). | Notes 9-10, levels S3, load doc 3.4: no stage, menus or stream without the avatar; the 90 s fallback never ticked on 2311. | high (logic), medium (the camera-manager route on 2311 is from today's follow_wire, which worked) |
| A12 | dumper.cpp: `world_poll`, `world_reset_game` (3839), `head_forget` (3836) | The pawn is checked every 0.5 s (alive, still a TribePawn); on loss `g_worldGen` moves on and the game thread drops pawn, camera, hands, camera manager, menus, walking state, the lift's base and the light list; our actor and its tracked meshes and head component are forgotten if they died (the head mesh stays); a stage that was up is loaded again. | Note 8 "clear the caches on every world change"; load doc 3.3. | medium (new path; only a room change exercises it) |
| A13 | dumper.cpp: `do_load` (1415), `do_load_inner` (1420), `avatar_poll` (4583), `repl_pe` iso drain | The load reports its result (`g_loadOk`, `g_loadWhy`, `g_skinLoaded`); the supervisor loads once Tribe's avatar body is there or 30 s after the world is up, retries a failed load 3 times 10 s apart, spawns our actor 2 s later and again (5 × 5 s) if missing, and a dead previous actor is cleaned up before a respawn; `active_skin.txt` = `tribe` loads nothing. The engine lookups in `do_load` and `spawn_iso_actor` are done once (they were full object walks on the game thread every time). | Note 1, load doc 2a/3.4: one arm, no retry ("6 launches resolved but never loaded a skin"); note 18 (`tribe`); the review's item 2. | high |
| A14 | dumper.cpp: `em_write_active` (2690), `em_fail` (3024), `em_pe_2311` (2705), `env_menu_tick` (3715), `env_menu_poll` (4359) | `active_env.txt` is never deleted: a mod pick writes its label, a stock pick writes `stock:<name>` (press + OnSkinApplied, or Tribe leaving our stage within 4 s of a skin-box press; "The Void" is never taken for a stock pick); Tribe switching by itself unloads ours and keeps the pick for the next launch. The auto-apply is a state machine: waits for the world (not the avatar) and an environment unchanged for 4 polls, retries a failed or vanished load 15 s later (4 tries; fresh tries only after the stage held 60 s; 12 per launch at most). EM_ACTIVE now notices our level going away. | Notes 9, 18; levels S5; load doc 2c (three paths deleted the file; the auto-apply fired once and needed the avatar). | high (logic), medium (stock-pick detection: OnSkinApplied for env items wasn't seen on device) |
| A15 | dumper.cpp: `ready_poll`, `ready_history`, `ready_write_file` (~4620); `MOD2311_STEP` | `[READY]` every 2 s until all required parts are up, then every 60 s; `ready.txt` (tmp + rename); `ready_history.txt` start + result per launch, kept to the last 150 lines once over 200; `pid=` in the line. | Notes 1, 11, 20; load doc 3.5. | high |
| A16 | dumper.cpp: `menu_resolve_engine_fns`, `skin_menu_poll`, `drone_poll`, `ensure_resolved`; stream.cpp `stream_poll` | No lookups before the object array; each missing engine function retried; a line only when the found count changes; the drone's miss once a minute; resolve failures 1 in 15; the stream.txt key kept only once the file was read (load doc 2e). | The 13:40 log was 0x0 lookups every 2 s; quieter logcat. | high |
| A17 | dumper.cpp: `calib_fprop_size` (1208) | At most 3 full object walks when its anchor can't be found; calibrated on the poll thread before the first game-thread call. | Each new function's parameter check needs it; a failure must not cost a walk per call. | high |
| A18 | dumper.cpp: `em_copy_identity` (2450) | Copies only between objects of the same class. | Review item 10 (it writes the source class's offsets). | high |
| A19 | stream.cpp `st_capture_clamp` (230), intro.cpp `intro_fov` (173), camview.cpp `cv_fov` (301) | Raw writes into Tribe's objects (the stream camera's capture timer, the stream camera's FOV) also require the object's class to be the one measured. | Review item 11: a reused slot holding another class passes obj_alive. | high |
| A20 | dumper.cpp: `repl_pe` | The freeze recorder beats on every game-thread ProcessEvent (16 ms apart), not only in the per-frame driver; a dead pawn is checked once per 16 ms. | Review item 5: no false freezes while a world loads. | high |

### Step B: the characters (on top of A)

| # | File: function (line) | What changed | Why | Confidence |
|---|---|---|---|---|
| B1 | dumper.cpp: `sm_poll_2311` (4188), `skin_menu_poll` (4212), `sm_find_avatar_list`, `sm_find_live_rpm_skin`, `sm_read_skins` (4143), `avatar_poll` | The avatar menu on 2311's classes: `TribeReadyPlayerMeAvatarSkin`, `TribeSkinItemWidget` (+ `Skin` offset, `SetSelected`, `OnSkinApplied`), `UserWidget.OnMouseButtonDown`, `KismetStringLibrary.Conv_StringToName`, `Actor.SetActorHiddenInGame`; the live `TribeProfileMenuWidget.AvatarList`; one box per `skins/*.glb` plus "Tribe Avatar". The menu kind is decided once the class is found, "2304" only once the world is up and it is still missing after 3 looks. | Characters doc C1-C3; the review's item 3. | high (names from the 2311 reflection tables, characters doc) |
| B2 | dumper.cpp: `menu_tick_2311` (2842), `sm_identity` (2768), `sm_name`, `sm_pool_scan` (2829) | Our items are spawned as `TribeReadyPlayerMeAvatarSkin`; identity = Tribe's RPM item's plain fields if one exists, then always `Name=ReadyPlayerMe_Custom` and `bOwned=1`, read back; a box without it is never added (retried 4 × 5 s); labels from the list's EntryWidgetPool. Kill switch `tribemod/skin_boxes_off`; a line before every AddItem. | Characters doc C4; an unowned box makes a press ask to buy it (decoded, 0x5B4C8C4). | medium (Tribe's native box build on our item is not decoded: section 5 item 1) |
| B3 | dumper.cpp: `sm_pe_2311` (2808), `sm_select_box`, `sm_pick` (2800), `sm_pick_tribe` (2796); `repl_pe` | A press on our box: `SetSelected(true)` on the box inside the press, then our skin loads; Tribe then sees the box selected and RPM's CanReapply false and applies nothing. A press on Tribe's own avatar box or our "Tribe Avatar": Tribe mode. OnSkinApplied of our item: a WARNING line (and our load if no press was seen). All engine calls inside the busy flag. | Note 19 (never change the saved Tribe avatar), note 3 (C4b). Verified in the 2311 library (O): `NativeOnMouseButtonDown` (0x5B4C890) calls `UUserWidget::NativeOnMouseButtonDown` at 0x5B4C8B0 before it reads `bSelected` at 0x5B4C9A0 and applies at 0x5B4C9E4; CanReapply (vtable 0x8105270 +0x300) = `mov w0, wzr; ret`; `SetSelected` (0x5B4BA58) = `strb w1, [x0,#0x350]` + a visual refresh with no apply or config call; `OnAvatarClicked` (0x594A574) ignores the item ("CustomizeAvatar" step only). | high (static), not device-tested |
| B4 | dumper.cpp: `sm_tribe_avatar_hide` (2780), `sm_actor_hide` (2790), `sm_tick_2311` (2914) | Once a second: while our actor is up and no Tribe avatar is picked, Tribe's `TribeAvatar` is `SetHiddenInGame(true, propagate)` (kill switch `tribe_avatar_shown`); in Tribe mode our actor is `SetActorHiddenInGame(true)` and Tribe's avatar shown (only undoing our own hide). | Characters doc C6/C7, note 19 (the RPM box must bring Tribe's avatar back). | medium (the hide's forwarding is decoded in the characters doc; not seen on device) |
| B5 | dumper.cpp: `do_load` | On 2311 our mesh is not put on Tribe's `AvatarBodyMesh` slot; no keeper. | Characters doc C8: that slot sits at the world origin and was drawn in 7 of 17 launches. | high |
| B6 | dumper.cpp: `ini_upsert` (825), `ini_url_cut`, `ini_flag` | The Ready Player Me keys are left as Tribe has them; `rpm_route_on` = old route; `rpm_url_set.txt` = set once then renamed `.done`; `rpm_url_clear` = delete both once; URLs logged cut to the host. | Note 19 (stop writing the dead URL; never print ids). The original URL is in no backup (section 7). | high |
| B7 | dumper.cpp: `sm_diag_poll`, `sm_diag_game`, `sm_diag_mesh` | The characters doc's C11 diagnostic, once when the list is first found and on `tribemod/skin_diag`. | Settles the box class, which avatar slot, and what Tribe built (the missing RPM box). | high |
| B8 | dumper.cpp: `sm_load` (2377) | The same box within 3 s counts as one click. | GUIDE: two Lampwing loads stalled Tribe. | high |

### Step C: the stages (on top of B)

| # | File: function (line) | What changed | Why | Confidence |
|---|---|---|---|---|
| C1 | club.cpp: `club_resolve` (173), `club_allowed` (204) | `bHost`/`bDJing` read at Offset + ByteOffset and masked with ByteMask (levels doc S4). | 2311 makes them bitfield bools; only guests were affected. | high |
| C2 | intro.cpp: `intro_tick` (276) | Runs only when the loaded ride file is this stage's `intro.<folder>.txt`. | Levels doc S1's intro part: after a switch the old ride stays loaded up to ~8 s. | high |
| C3 | dumper.cpp: `em_soft_get` (2519) | The engine's dead test instead of UE4's `1<<28`. | Levels doc S2. | high |
| C4 | dumper.cpp: `em_check_paks` (3705), `ready_poll` | Once, on the game thread: `BlueprintPathsLibrary.FileExists` for every `envs.txt` level's `.umap`; one line; `paks=N/M` in `[READY]`. | "Get all the levels in": a missing pak shows at launch. | medium (FileExists through the pak layer is what em_diagnose relies on; not seen on 2311) |

## 3. 2311 addresses this build relies on (tools/verify_2311.py, all PASS, O)

| What | Store vaddr | Runtime | Check |
|---|---|---|---|
| Segment shift | text 0x15D7000, data 0x7676040 / 0x87C4040 | +0x1000 | program headers |
| ProcessEvent | 0x19E8EB4 | 0x19E9EB4 | first word `a9ba7bfd` (`stp x29,x30,[sp,#-0x60]!`); no PC-relative instruction in the 5 overwritten; same word in the patched lib; (0x19E9EB4+8)&7 = 4 -> the 5-word form |
| Encoder re-send (join) | 0x5A80E7C | 0x5A81E7C | 16-byte head as in stream.cpp |
| Encoder re-send (role) | 0x5A81F18 | 0x5A82F18 | 16-byte head as in stream.cpp |
| FWeakObjectPtr::Get | 0x1A366AC | 0x1A376AC | GUObjectArray 0x88A5150 (+0x24 count, +0x10 chunks), stride 0x14, serial +0x10, flags +8, `orr ... #0x200000` |
| GOT -> GUnreachableObjectFlag | 0x8678A30 | 0x8679A30 | target store 0x87C9C00 in .data, initial value 2 |
| Box press | 0x5B4C890 | - | UserWidget call 0x5B4C8B0 < bSelected read 0x5B4C9A0 < apply 0x5B4C9E4 |
| RPM skin CanReapply | vtable 0x8105270 +0x300 | - | `adrp 0x8105000; add 0x260; add 0x10` in the constructor; slot -> 0x15D7068 `mov w0, wzr; ret` |
| SetSelected | 0x5B4BA58 (via exec 0x53BBAE8) | - | `strb w1,[x0,#0x350]`; the refresh (0x5B4BB38, 287 instructions) calls no ApplySkinToPlayer / config read or write |
| OnAvatarClicked | 0x594A574 (via exec 0x5387964) | - | ignores the item; `this+0x3D0 -> 0x54243F0(FName("CustomizeAvatar"), true)` |

## 4. Kill switches and one-shot files (tribemod/, no rebuild)

`executor_on` absent = safe mode (no hook) · `tribe_avatar_shown` = never hide Tribe's avatar (B) · `skin_boxes_off` = no
mod boxes in the avatar menu (B) · `skin_diag` = the avatar diagnostic again (B, one-shot) · `rpm_route_on` = the old
Ready Player Me route (B) · `rpm_url_set.txt` / `rpm_url_clear` = set or clear Tribe's Ready Player Me URL once (B) ·
`skin_menu`, `env_menu`, `auto_load`, `auto_actor` as before.

## 5. The review (one subagent, read-only, on diff_C_vs_live; ~31 minutes)

It found no definite game-thread crash. It checked and agreed with: the constructor hook (no path leaves ProcessEvent
patched with `orig_pe` NULL, never patched twice, the three verification forms match the library), the fault guard,
the range tables, the busy flag (every `ue_enter` paired), the show-collection handle, the call check (no class
mismatch among the call sites; zeroed parameter buffers) and step C. Its items and what was done:

| # | Item (severity) | Done |
|---|---|---|
| 1 | Our near-empty RPM items go through Tribe's native box build; a thumbnail fetch for the empty avatar id may crash (possible crash, not verified, B) | Not decoded (time). Added the `skin_boxes_off` kill switch and a log line before each AddItem; the plan's risk section and the B test name the sign. **Open.** |
| 2 | Avatar respawn after every room change did 7 full object walks on the game thread (stall) | Fixed: the lookups in `spawn_iso_actor` and `do_load` are done once (A13). |
| 3 | The avatar-menu kind decided on the first lookup, possibly before Tribe's classes exist | Fixed for both menus: "2304" only once the world is up and still missing (B1, and the env menu in A). |
| 4 | Head lost after a respawn (`head_drop` cleared the head mesh) | Fixed: `head_forget` drops only the component (A12). |
| 5 | False freeze reports during a world load; dead pawn re-checked on every call | Fixed (A20). |
| 6 | Engine calls outside the busy flag in the OnSkinApplied branch | Fixed (B3). |
| 7 | Stage auto-apply could repeat forever on a level that keeps vanishing | Fixed: fresh tries only after 60 s up, 12 loads per launch (A14). |
| 8 | World reset left the lift's base and the light list | Fixed (A12). |
| 9 | One failed identity read hid a box for the session | Fixed: retried 4 × 5 s (B2). While checking it, this job found that its own 20 ms rebuild throttle could make a just-allocated object read as unmapped, so the call check would skip a real call (for example the new mesh onto our actor): the throttle was replaced by "rebuild unless a newer table was published since the miss" (A5). |
| 10 | `em_copy_identity` didn't check the classes match | Fixed (A18). |
| 11 | Older raw writes checked only by obj_alive | Fixed (A19). |
| note | First launch after an install: ProcessEvent is patched even if `executor_on` turns out absent | By design (load doc 3.1); calls only pass through. In the plan's risks. |
| note | The poll thread and the game thread both run `stream_tick` and share its statics | Older than this diff; no pointer involved; left as is. |

## 6. Where this build differs from the investigation docs and the notes

- **Note 8 / load doc 3.3 (WRef for every cached object).** Not done as per-variable WRefs (about 60 pointers in six
  files, each a new chance to get a store site wrong). Instead every engine call is checked at the one place all calls
  pass (`call_uf`): slot + the engine's dead test + class, for the object and every object parameter (A8), plus the
  exact WRef-style identity (slot, serial, class, name) for the show collection, where the crash happened (A9), plus a
  class check before raw writes (A19), plus the world-change reset (A12). What this does not catch: a freed object's
  slot reused by a live object **of the same class** (a type-safe call on the wrong instance: no memory corruption).
  The layout it relies on is the 2311 binary's (O, section 3), as note 8 asked.
- **Note 19 vs the name `ReadyPlayerMe_Custom`.** Our items keep that name (characters doc C4), but no press can make
  Tribe apply or save it: the box is selected inside the press (C4b, verified in the binary). The name only matters if
  Tribe applies a box by a route the decode didn't find; then it is the least harmful identity known (a re-apply of
  Tribe's own RPM avatar, saving `OculusAvatar=ReadyPlayerMe_Custom`), and the log says WARNING. An unnamed item would
  save `None` or open a purchase.
- **Characters doc C7 (load the last skin hidden so the driver keeps running).** Not needed: the driver no longer needs
  our actor (A11); in Tribe mode nothing is loaded.
- **Characters doc 1.1 ("OnAvatarClicked is most likely bound natively to OnItemClicked", [asm]).** Its body is now
  decoded (section 3): it doesn't apply anything, so the box press is the only apply route.
- **Characters doc 2.5 ("Tribe's RPM avatar here is custom.glb from the cache, if the cache-hit route still works",
  [asm]).** The ini has no ETag (`summary: ... etag=(none)` in every ini_upsert.log, O) and the load gate needs URL +
  ETag + cache file for a hit (NOTES.md ~3500), so with today's files Tribe downloads from port 8000, where nothing
  listens (D). The RPM route can't show custom.glb on this headset.
- **Load doc 3.2 (`__thread` jump buffers).** Done with per-thread slots keyed by `pthread_self` instead, so the signal
  handler never touches TLS (a first TLS access inside a crash handler could allocate).
- **Load doc design: "resolve every 1 s".** Kept at 2 s, as today (each failed try is a full scan).
- **Plan wording corrected after the build:** the stage settle is 4 polls (~8 s), not 4 s.

## 7. The Ready Player Me URL (note 19)

- Tribe keeps it in `[TribeAvatar] ReadyPlayerMeAvatarUrl` (+ `ReadyPlayerMeETag`) of
  `/data/data/com.TribeXR.TribeXR/files/UnrealGame/TribeXR/TribeXR/Saved/Config/Android/GameUserSettings.ini` (the
  path in `ini_upsert`, O); `[TribeSkins] OculusAvatar` holds the chosen avatar (`ReadyPlayerMe_Custom` in the
  2026-10-01 snapshots, O). The file is app-private: adb can't read or write it.
- Searched (values cut to the host): backup/tribemod_20261001/tribemod/ini/03_ and 07_GameUserSettings.ini: the
  loopback URL; every ini_upsert.log in backup/tribemod_20261001, backup/tribemod_20261031_preupdate and
  backup/reseed_runs/*: only the loopback URL, set at each launch (O). backup/tribemod_20261006 has no ini copy.
  No Documents/ backup exists apart from `rpmavatar-custom.glb` (O). The user's original URL is not recoverable from
  the PC.
- How it comes back: Tribe's own Ready Player Me panel (B leaves the keys alone so its save sticks), or
  `rpm_url_set.txt` if the user has the URL. Whether readyplayer.me serves avatars today is (A).

## 8. Not tested

- Nothing ran on the headset: not the hook install, not the game-thread gate, not the call check, not the menus.
- The call check's false positives (`[CALL] skipped` lines) and its cost per call (estimated below today's per-read
  `sigprocmask`, which A6 removes; not measured: watch `[PERF]`).
- Room changes (A12), the stock-pick detection (A14), the Tribe-mode switch and the hide/show (B3/B4), Tribe's native
  box build on our items (section 5 item 1), the pak check (C4), the Reactor gate as a guest (C1).
- Lampwing, Major Tom and Santa have never loaded on 2311; no 2311 head line exists.
- The cold-start script ran only against the mock adb (43/43) and once in `--dry-run` (it contacts nothing then).

## 9. Files

`backup/mod2311_build/`: mod2311_{A,B,C}.apk (+ .idsig, from apksigner), mod2311_{A,B,C}_libhook.so, builds.txt,
src_{A,B,C}/ (src/ = src_C), out_{A,B,C}/ (libhook.so + build.log), diff_*.diff (the complete record of the source
changes), tools/ (verify_2311.py, make_apk.py, compare_apk.py, build_all.sh; edit_a_*.py, edit_b.py, edit_c.py and
edit_review.py hold most of the edits as scripts, a few small fixes were applied inline and are only in the diffs).
scripts/launch_check.sh, tests/launch_check_test.sh. claudedocs/mod_2311_plan.md.

Rebuild: `bash backup/mod2311_build/tools/build_all.sh A B C` (from the repo root; one step at a time).
