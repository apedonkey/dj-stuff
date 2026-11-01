# Tribe mod on 0.12.6 (2311): why some launches don't load everything, and a startup that does

2026-10-31, written about 16:00. This is a read-only analysis of today's source (backup/mod_fix_stream_fix/src), the 2311
library (backup/mod_fix_work/lib), today's logs (backup/mod2311_evidence) and read-only adb at ~15:35. Nothing was built
or installed, and no file on the headset was changed.
- Redacted evidence extract: backup/mod2311_work/load/evidence_extract.txt.
- Scripts that reproduce the binary checks (same folder): bt_check.py, funcs.py, u16find.py.
- Line numbers below are in backup/mod_fix_stream_fix/src unless a path is given.

Labels: **(O)** observed (read it or ran it), **(D)** derived from observed facts (the steps are given), **(A)** assumed
(plausible, not checked).

## 0. The short answer

1. **Two of the five launches since the 13:38 reinstall got no ProcessEvent hook, and without the hook nothing else
   starts.** (O) These were 13:40:38 (pid 22629) and 14:26:25 (pid 16230). Neither wrote a "resolved:" line or a
   do_load to load_result.txt. The 13:40 launch logged "ProcessEvent calls 0" and "0 in the array". The object-array
   resolve only runs once `orig_pe` is set (dumper.cpp:4031), and every later step depends on it: the lookups, the
   avatar, the stage, the menus and the stream settings. So the user restarts until a launch gets the hook.
   - **13:40: cause found (high confidence).** The library constructor could not reach `tribemod/` (it was the first
     launch after the reinstall), so `executor_on` read as absent. combo_pedriver installs the hook only once, in the
     constructor, so it skipped it. Three independent traces show this; see section 2a.
   - **14:26: cause not proven.** That launch's constructor did reach `tribemod/`: its ini_upsert.log and httpd.log
     entries exist. So the one-shot install failed some other way. Leading candidate (medium-low confidence): the
     prologue read (`sr()`) races the poll thread. In its first `stream_poll`, the poll thread rewrites the shared range
     table (`st_hook_send` → `load_maps()`, stream.cpp:109). A failed read makes the hook log "NOT a prologue … hook
     SKIPPED". The constructor's log line didn't survive.
2. **The 13:57:37 crash that ended the set was a stale show-collection pointer.** The mechanism is high confidence; the
   trigger is unknown.
   - `show_set` (dumper.cpp:2749) hands `g_gColl` to KismetMaterialLibrary.SetScalarParameterValue after checking only
     that it is non-null.
   - The engine found no parameter-collection instance for that pointer, so it created one. It then crashed reading the
     "collection's" parameter array, whose data pointer was 3 (registers and disassembly, section 2b).
   - So `g_gColl` no longer pointed at MPC_HwShow. What freed it isn't in any log: logcat had rotated.
3. **The 13:22:56 crash did not take that path.** (D, high) None of the six 13:20–13:23 launches (combo_peretry) reached
   do_load, and the per-frame driver that calls club_tick needs our avatar actor. What crashed them can't be determined
   from what survives.
4. **The stage isn't re-applied because the mod deletes the saved choice itself.** (O) This happened at least once
   today; which code path did it is unknown.
   - `active_env.txt` was restored at 13:39 owned by shell. It is now owned by the app (u0_a202, mode 0660, 14:28:13),
     so it was deleted and later created again by a pick.
   - Three code paths delete it: `em_fail` (any failed or timed-out load), "Tribe switched environment", and "stock
     environment picked".
   - The auto-apply also fires only once per launch, and only after the avatar exists.
5. **load_result.txt grows because `follow_update` logs on every frame on 2311.** (O)
   - 250,256 "follow: isoTicks=0 fallbackTicks=0" lines make up 32.6 MB of the 33.6 MB file. The 2311 driver never
     increments the counters the log condition tests.
   - The same line floods logcat, whose main ring buffer is 256 KiB. That is why no mod log survived from the crash
     session or from the 14:26 launch.

**The design in brief:**
- Hook ProcessEvent in the constructor, before any thread starts, whether or not tribemod is readable yet. Check the
  patched bytes, retry inside the constructor, and never patch later.
- Run every other step as a retrying state machine with its dependency, a time limit and one log line.
- Run the per-frame driver as soon as the world exists, not only once the avatar has loaded.
- Pass the engine only objects that pass a GUObjectArray index and identity check. Drop world objects when the world
  changes.
- Never delete active_env.txt automatically.
- Print one `[READY]` line until everything is up, then once a minute.

## 1. Startup timeline

The live build combo_pedriver equals today's src minus the retry thread, the atomic busy flag and two late
diagnostics (section 2a lists exactly what differs). In today's good launches, our avatar actor (and with it the
per-frame driver) came up about 35 s after the process started (D): each freeze self-test fires 20 s after the first
driver tick (freeze.cpp:136).

| Launch (process start) | Freeze self-test | Driver's first run | Gap |
|---|---|---|---|
| 13:42:02 | 13:42:58 | 13:42:38 | 36 s |
| 13:57:42 | 13:58:37 | 13:58:17 | 35 s |
| 14:27:29.7 | 14:28:25 | 14:28:05 | 35 s |

| # | Step | Code | Thread | Waits for | If it runs too early | Retries | Logs |
|---|---|---|---|---|---|---|---|
| 1 | Constructor | on_load 4110-4127 | the loader, inside `System.loadLibrary` (libhook is a DT_NEEDED of libUnreal, so it runs before libUnreal's own initializers: D, ELF load order) | nothing | — | — | `dumper libhook constructor` |
| 1a | ini edits | ini_upsert 740-759, stage_cache 685-696 | constructor | tribemod/avatar_url.txt, avatar_etag.txt, body_tracking, http_log | if tribemod can't be read, the reads fail as "absent": the RPM URL key is **deleted** from GameUserSettings.ini (747) and Engine.ini's body-tracking key is removed (751) (D, code). The 13:40 launch therefore ran without both keys: the next launch's block shows them SET from 290 and 0 bytes (O). The constructor runs before the engine reads its ini (the comment at 4113), so a later fix can't help that launch | none | `[INI]` + tribemod/ini_upsert.log |
| 1b | libUnreal base | 4116 | constructor | /proc/self/maps | — | 100 × 50 ms | `FAILED to find libUnreal.so base`, then returns: no threads, no hook |
| 1c | Poll thread | 4118-4120 → dump_thread 4007-4093 | new thread, 0.5 s loop | — | — | — | `dumper thread up` |
| 1d | Local HTTP server | 4122-4124 → httpd_thread 850-862 | new thread | tribemod/custom.glb | `server NOT started (no asset)`, permanent | none | tribemod/httpd.log |
| 1e | ProcessEvent hook | pedriver: inline at the end of on_load, after 1c and 1d (O, disassembly of build/libhook_pedrv.so: 0x2f3b8 `open(executor_on)` → 0x2f3e4 `sr(base+0x19E9EB4)` → 0x2f460 `A64HookFunction`). Today's src: pe_install_thread 4108 → pe_install_try 4096-4106 | pedriver: constructor. peretry: a third thread | tribemod/executor_on readable; the word at base+0x19E9EB4 readable through `sr()` (84-87, shared range table 58-70) | executor_on unreadable reads as "absent" and the hook is skipped for the whole session (pedriver) | pedriver: none. peretry: every 0.5 s for 120 s | `ProcessEvent hook installed @… (orig=…)`, `NOT a prologue`, `executor_on absent` |
| 2 | Resolve | auto-load block 4031-4034 → ensure_resolved 919-931 | poll | **orig_pe != 0** and tribemod/auto_load | without the hook it never runs: everything below stays 0 (O, 13:40) | every ~2 s until resolved | `resolved: np=… ga=… NumElem=N` (load_result.txt) |
| 3 | Avatar arm | 4033-4034: find_live("AvatarBodyMesh","SkeletalMeshComponent","ReadyPlayerMeComponent") 935-947 | poll | the resolve; Tribe's pawn with its RPM component | not found: retried | until armed, **then never**: auto_done is set when armed, so a failed do_load isn't retried | `auto-load: pawn ready (body=…) -> armed` |
| 4 | do_load | repl_pe 3430 → run_guarded 1306-1311 → do_load 1241-1305 | game, inside the hook | g_load_req | — | none | `=== do_load (game tid=N) ===` … `done` |
| 4a | Skin | 1255-1257: active_skin.txt → skins/<file>, else glb_path.txt, else custom.glb; materials, then gray (1270-1274); head_skin_loaded (head.cpp:97-130) | game | do_load | — | none | `asset=… (path=…)`, `[HEAD] …` |
| 5 | Avatar actor | auto_actor 4039-4040 (2 s after do_load) → repl_pe 3418 → spawn_iso_actor 1172-1239 → follow_wire 1138-1153 | poll → game | g_loaded_once, g_mymesh, the camera manager | returns 0; no retry (`aa` counts down once) | none | `iso: …`, `follow: …` |
| 6 | Per-frame driver | repl_pe 3378-3381 | game, ≥ 16 ms apart, behind ue_enter | **g_isoActor** | nothing per-frame runs without our actor: stage, menus, show, game-thread stream parts, head, drone | runs every ProcessEvent once our actor exists | `[PERF]` every 10 s; `[STREAM] diag ticks` counts its runs |
| 6a | Fallback ticker | 4043-4046 → fallback_wire 1158-1168 | poll → game | 90 s after the resolve with no avatar actor | on 2311 it does nothing: the 16 ms driver (3379) tests only g_isoActor, and the pawn's ReceiveTick never reaches ProcessEvent | every 30 s | `fallback: …` |
| 7 | Stage lookups | env_menu_poll 3840-3950 (engine functions 3852-3879, 2311 menu classes 3880-3890, envs.txt 3901, list, Void item, rig) | poll, every 2 s | **g_resolved** (3843) | returns | each pass | `[ENV] fns: …`, `[ENV] 2311 menu (C++) …`, `[ENV] ON` (logcat only) |
| 8 | Game state | env_menu_tick 3311-3322 (GetGameState; contexts: our actor, the env list, the rig) | game, every 60th driver run (~1 s) | the driver | — | each tick until found | `[ENV] game state = …` |
| 9 | Stage auto-apply | 3928 (settle) + 3939-3942 → env_menu_tick 3324-3354 | poll → game | g_envMenuOn, the game state, CurrentEnvironment unchanged for 4 polls (8 s), EM_IDLE | if the game thread isn't ready the request is refused (`click ignored, not ready`) and dropped | **once per launch**: autoDone is set before the request is honored | `[ENV] auto: re-applying '…'`, `[ENV] step 1/4…4/4`, `*** '…' is IN ***` |
| 10 | Env menu boxes | env_menu_tick 3289-3306 + em_pool_scan 2531-2543 | game | g_envMenuOn and the live list | — | each tick | `[ENV] spawned/added box …` |
| 11 | Avatar menu boxes | skin_menu_poll 3699-3718 → menu_tick 2199-2214 | poll → game | g_skinMenuOn, which needs the 2304 Blueprint lookups (3705-3711) | never on 2311 (2d) | each poll | `[MENU] blueprint lookups: … 0x0` |
| 12 | Stream settings | stream_poll stream.cpp:172-211 (stream.txt 173-183; manager and controller 190-203, which need the object array); stream_tick 247-303 (off-call size 214-227; encoder 270-303) | poll (stream_tick with g_stOnPoll=1) and game (driver) | the resolve for g_stMgr; the driver for GetIsChannelStreaming (255) | returns at 249 without the manager | each poll | `[STREAM] stream.txt: …`, `[STREAM] stream size …`, `[STREAM] encoder …` |
| 13 | Freeze recorder | freeze_poll freeze.cpp:143-155 | poll | the first driver beat (freeze_beat, freeze.cpp:33) | — | — | `[FREEZE] recorder on`; self-test 20 s later |

## 2. The failures

### 2a. Launches where ProcessEvent never gets hooked

**The launches since the 13:38 reinstall** (O, sources: the extract, the system log, load_result.txt pulled at 15:35,
freeze_log.txt, httpd.log and ini_upsert.log diffed against the 13:35 snapshot):

| Start | pid | Constructor reached tribemod/ | Resolve | do_load | Driver | End |
|---|---|---|---|---|---|---|
| 13:40:38 | 22629 | **no** | **none** ("ProcessEvent calls 0", "0 in the array") | none | never | relaunched at 13:42 |
| 13:42:02 | 24193 | yes (first ini block after the reinstall; avatar cache staged 13:42:02.85) | NumElem 30218 | tid 24243 | ~13:42:38 | SIGSEGV 13:57:37 |
| 13:57:42 | 11459 | yes | 17932 | tid 11516 | ~13:58:17 | quit 14:26:15; killed 14:26:25 (`destroyTimeout`) |
| 14:26:25 | 16230 | yes | **none** | none | never (no freeze self-test) | died 14:27:26 after 61 s with no crash record (most likely the user quit, A) |
| 14:27:29 | 17390 | yes | 17932 | tid 17440 | ~14:28:05 | ended 15:00:21 |

One more detail on 14:26:19: the user's relaunch first landed in the still-dying process 11459. Android killed that
process for `destroyTimeout` and started 16230 for the same launch (O, system log).

**Why 13:40 had no hook (high confidence).** Three independent traces show that the constructor of 22629 could neither
read nor write tribemod/ (O):
1. **ini_upsert.log** gained 4 blocks for 5 launches. The first block written after the reinstall is the one that found
   fresh ini files ("ReadyPlayerMeAvatarUrl: SET (290->362 bytes)", "bBodyTrackingEnabled: SET (0->76 bytes)") and
   staged the avatar cache.
2. **The staged avatar cache** files/Documents/rpmavatar-… has mtime 13:42:02.85, i.e. the 13:42 launch staged it. The
   uninstall had wiped Android/data, so the file was missing at 13:40:38. A constructor that could read avatar_url.txt
   would have staged it then, or logged "cache: … fail" into the log.
3. **httpd.log** gained 4 "asset loaded"/"listening" pairs for 5 launches.

So `open(executor_on)` failed too, and pedriver logged "executor_on absent; PE hook not installed (safe mode)" and
never retried (D).

The access appeared during the launch itself:
- The poll thread's `[MENU]` lines from 13:40:48 on need tribemod/skin_menu (3700).
- Tribe created files/Documents/{TribeRecordings,rekordbox} at 13:40:48.0.
- The package dir got its cache/ at 13:40. Both it and files/ are owned by u0_a202 now (O).

That Android fixes the ownership of the app's external dir when the app first uses it is (A). NOTES.md:4226-4228 records
the same "executor_on absent" / errno 13 after a reinstall on 2304.

**Why 14:26 had no hook (not proven).** The constructor of 16230 did reach tribemod/: the 4 blocks are 13:42, 13:57:42,
14:26:25 and 14:27:29, and 13:40 is the missing one (D). So the one-shot install failed despite a readable executor_on.
Candidates:
1. **Range-table race (D from code, not observed).** `sr()` checks every read against the global `g_ranges` table.
   - On a miss, `sr()` calls `load_maps()` (58-64), which sets `g_nranges=0` and refills the table.
   - The poll thread starts before the hook install (pedriver order, above). Its first `stream_poll` calls
     `st_hook_send` (stream.cpp:116-119, 187), which runs `load_maps()` (stream.cpp:109) and parses /proc/self/maps.
   - If both threads refill or search the table at once, `in_range` can fail for the valid ProcessEvent address. `sr()`
     then returns false and the hook logs "NOT a prologue (w=0x00000000); hook SKIPPED". pedriver does not retry.
   - For: it fits a constructor that read tribemod but got no hook. Against: nothing; it simply wasn't logged.
2. **The poll thread hung before its first resolve** (A). With no resolve nothing would be logged even with the hook
   in. Nothing for or against it.
3. **A64HookFunction failed (mprotect)**, leaving orig_pe NULL (A). Against: the same call works in every other launch.

**combo_pedriver (12:18) compared with today's src.** The src after 12:18 wasn't saved, so the difference comes from the
builds' function sizes (O, `llvm-nm -S` on build/libhook_*.so):

| Step | Build | Function changed | What it is |
|---|---|---|---|
| pedrv → envdiag | | env_menu_poll +84 B | the "auto-apply state" line at the 200th poll (~400 s) |
| envdiag → atomic | | repl_pe +124 B | the atomic busy flag (ue_enter/ue_leave) |
| atomic → skindiag | | env_menu_poll +656 B | the `[SKIN] diag` list at the 400th poll (~800 s) |
| skindiag → retry | combo_peretry | on_load −172 B, new pe_install_thread (468 B) | the retry thread |

The set session ran pedriver (O): the tombstone's libhook offsets (repl_pe+248 = 0x18dc8, club_tick+3912 = 0x2104c,
club_show_player+392 = 0x3b7fc, mpc_call_on+368 = 0x3b5f0) match only libhook_pedrv.so (md5 3b070807).

**What the retry thread does.** It recovers from a failed first attempt by patching ProcessEvent again every 0.5 s for
2 minutes, i.e. while the engine runs.
- And64InlineHook publishes `*result` (orig_pe) before it fills the trampoline (vendor/And64InlineHook.cpp:581-582).
- It then writes the jump with plain stores (533-541). At ProcessEvent the 5-word form is used, because base+0x19E9EB4+8
  is not 8-byte aligned: NOP, `LDR X17,#8`, `BR X17`, then the 8-byte target.
- A GameThread that has executed the old first instruction (`stp x29,x30,[sp,#-0x60]!`) and then fetches the new second
  one enters repl_pe with its stack already moved by 0x60. That crashes later at a random place (D).
- The chance per late install is small (A). The thread is only safe when it doesn't need to retry.

**Could it have caused the 13:22 crash? Not shown, and unlikely** (D):
- All six crash-loop launches had the hook. Each logged "resolved:", which requires orig_pe (load_result.txt lines
  56744-56752; the six sessions match the six dropbox tombstones at 13:20:41, 13:20:59, 13:21:18, 13:21:54, 13:22:57
  and 13:23:25).
- The two diagnostics run only after 400 and 800 s.
- The atomic flag behaves the same as the old check-then-set on one thread.
- A late patch could crash a launch at random, but six crashes in a row with no install in between point to something
  deterministic that the surviving evidence doesn't show.
- Which build ran them (D): the 13:00 reseed reinstalled combo_peretry (9ff0a53e) at ~13:04, and combo_pedriver
  (e36afd77) was installed again by 13:25:56 (fix_login.log). The rollback time isn't recorded, so the last of the six
  may already have been pedriver.
- The tombstones are in /data/system/dropbox, which isn't readable without root (O: `ls` denied).

### 2b. GameThread SIGSEGVs

**Address rule (O, checked two ways).** The tombstone pcs are ELF virtual addresses in the patched library, not file
offsets:
- Frame #00's instruction at that vaddr is `ldr x25, [x8]` with x8 = 3, which is the reported fault address 0x3.
- All 20 caller frames land on a `bl`/`blr` at the printed pc. libunwindstack prints the call instruction itself for
  frames ≥ 1.
- Read as file offsets instead, only 2 of 20 frames are calls (bt_check.py).
- The patched text segment has vaddr = file offset + 0x10000 (llvm-readelf).
- Patched vaddr = store vaddr + 0x1000; runtime = libUnreal base + patched vaddr. The build id c3b274dd… is the patched
  library's.

**The 13:57:37 backtrace mapped to functions.** Function starts come from .eh_frame_hdr (funcs.py). Names are derived
by matching the disassembly to UE 5.4's source; there are no symbols.

| # | pc (patched) | Function start (+offset) | Identified as | How |
|---|---|---|---|---|
| 11 | 0x27a8fd4 | 0x27a8d58 (+0x27c) | an engine caller of ProcessEvent | `ldr x8,[x8,#0x270]; blr x8`: vtable slot 78, ProcessEvent's slot (mod_fix_port.md §0) |
| 10-7 | libhook | — | repl_pe+248 → club_tick+3912 → club_show_player+392 → mpc_call_on+368 | symbols in libhook_pedrv.so (O) |
| 6 | 0x19ea230 | **0x19e9eb4** (+0x37c) | UObject::ProcessEvent (reached through orig_pe's trampoline) | the FDE starts exactly at ProcessEvent (store 0x19E8EB4) (O) |
| 5 | 0x189c5b8 | 0x189c53c (+0x7c) | UFunction::Invoke | `blr x8` to the native thunk |
| 4 | 0x3fd2fa4 | 0x3fd2e54 (+0x150) | the exec thunk of KismetMaterialLibrary.SetScalarParameterValue | reads the parameters from the frame and calls #3 |
| 3 | 0x3fd3028 | 0x3fd2fcc (+0x5c) | UKismetMaterialLibrary::SetScalarParameterValue | `cbz x1` (null Collection) → GEngine (GOT 0x8693788) → GetWorldFromContextObject(ctx, 1) → `bl 0x4618f84` → then the instance's SetScalarParameterValue (`bl 0x4123554`) |
| – | (tail call) | 0x4618f84 | UWorld::GetParameterCollectionInstance | loops World+0x1e0/+0x1e8 (ParameterCollectionInstances), compares each instance's weak Collection (+0x2c) via FWeakObjectPtr::Get (0x1a376ac, store 0x1A366AC per the notes); **no match: `b 0x4618d84`** (O) |
| 2 | 0x4618ebc | 0x4618d84 (+0x138) | UWorld::AddParameterCollectionInstance | appends the new instance (with the incremental-GC barrier), then calls 0x4123800(instance, true) |
| 1 | 0x4123f30 | 0x4123ee4 (+0x4c) | the new instance's render-state update | tests the flag at +0x118 and the weak World (+0x34), then calls #0 with a local array |
| 0 | 0x4124108 | 0x4123fbc (+0x14c) | UMaterialParameterCollectionInstance::GetParameterData | per index: `Collection.Get()` (0x1a376ac), `ldr x28,[x0,#0x38]` = ScalarParameters.Data, stride x25 = 0x1c (FName 8 + FGuid 16 + float 4, the stride giant_lookup also uses), packs 4 per vector |

**What crashed.** The registers at the fault (O): x23 = 0 (parameter index 0), x25 = 0x1c, x28 = 3, so x8 = 0·0x1c + 3
= 3. The object behind the new instance's Collection weak pointer was a live UObject whose +0x38 is 3, i.e. not a
material parameter collection (D).
- A still-live MPC_HwShow already has an instance in the world after the show bus's first write, so the engine would not
  have created a new one.
- Creating an instance for a valid collection can't yield data pointer 3.
- So the pointer the mod passed was stale (D, high).

**What mpc_call_on calls (O).** It calls KismetMaterialLibrary.SetScalarParameterValue through ProcessEvent on the
library's default object `g_mpcLib`, with parameters {WorldContextObject = `g_pawn`, Collection = `g_gColl`,
ParameterName = the key's FName, ParameterValue} (2388-2396). The callers are show_set (2749), giant_mpc (2745) and
club_show_player (club.cpp:251-255, every driver frame while a walking stage is up, club.cpp:332).

**How `g_gColl` goes stale (O in code):**
- show_set and giant_mpc check only `g_gColl != 0`. club_tick runs right after giant_tick, which may have just returned
  because `!obj_alive(g_gColl)` (3170). club_tick writes anyway.
- giant_lookup re-checks only every 8 s (env_menu_poll's tick%4==3 at 2 s; 3847). When the collection is dead but our
  stage counts as up, the re-find fails and returns **without clearing** `g_gColl` (2699-2713).
- em_unload doesn't clear it either (2639-2645).
- `obj_alive` (2148-2149) reads the object's own index field and checks that the array slot holds the same address. If
  another object now sits at that address it passes; there is no serial or identity check.

**What could have freed MPC_HwShow at 13:57 (candidates, none logged):**
1. Any unload and reload of the stage: a re-pick runs `em_unload("switching")` and then loads a new level instance. The
   old package can be collected in between, and the new collection sits elsewhere. For up to 8 s, or for good if the
   address got reused, the driver writes through the old pointer.
2. A world change.
3. Anything else that unloads the level.

What is known about 13:42-13:57: a headset-off pause from 13:55:23 to 13:56:11 (freeze log and system log), then the
crash 86 s after resuming (O).

**13:22:56 (fault 0xffff0003): not the same path (D, high).** The process that crashed then never logged a do_load (none
of the six crash-loop sessions did). So no avatar actor existed, the 16 ms driver (3379) never ran, and club_tick never
ran. The only other route, the ReceiveTick path (3411-3414), needs g_isoActor or a fallback ticker. The fallback is armed
90 s after the resolve, and its ReceiveTick never reaches ProcessEvent on 2311. The +3 in both fault addresses looks
alike, but nothing else connects them.

### 2c. The stage doesn't load by itself at launch

**Facts (O):**
- active_env.txt held "Graveyard Shift" in the 13:35 snapshot and was restored at 13:39 owned by shell, like every
  restored file.
- Now it is owned by u0_a202 with mode 0660 and mtime 14:28:13.69. That is an app-created file: the mod's `open(O_CREAT
  |O_TRUNC)` keeps the owner of an existing file.
- So between 13:39 and 14:28 the mod deleted it, and a request created it again at 14:28:13.
- The 14:27:29 launch's driver started at about 14:28:05. Since the file didn't exist right before 14:28:13, nothing
  could auto-apply in that launch. The write came from a pick about 8 s after the menus came up (D). A pick goes
  through `em_click`: either a press on our box, or Tribe applying one of our box objects by itself (2513-2518).

**Why the saved stage gets lost or not applied (D unless marked):**
1. **The mod deletes active_env.txt itself.** `em_write_active("")` (2498-2500) runs from:
   - `em_fail` (2646-2650): "level not loadable" (3347), "streaming object went away" (3349), or the 40 s "timeout"
     (3354);
   - "Tribe switched environment" (3369): CurrentEnvironment ≠ Void on 2 consecutive ticks while our stage is up;
   - "you picked a stock environment" (3323): a press on a skin box, then OnSkinApplied of a stock environment within
     1 s (2519-2520).

   Which one ran today is unknown (logcat rotated). An early auto-apply that hits a not-ready moment ends in em_fail,
   which forgets the choice, and the user re-picks. That cycle matches "every launch". (A: the cycle is unverified.)
2. **The auto-apply runs only once.** `autoDone=true` is set before the request is honored (3940). env_menu_tick drops a
   refused request (3333-3334), and nothing re-applies after a later unload.
3. **It needs the avatar.** The game state is found only by env_menu_tick, i.e. by the driver, i.e. after our actor
   spawns. A launch with no hook or no avatar can't apply the stage, and can't show the boxes either.
4. **No world-change detection.** The EM_ACTIVE state never checks that our streamed level still exists (3355-3370). If
   the level goes away, the mod stays "active" and doesn't re-apply.

**Cheap checks that would settle item 1:**
- `ls -l …/tribemod/active_env.txt` after each quit and after each stage load.
- The `[ENV] auto:` / `unloaded our environment (…)` lines. These survive once the per-frame logging is fixed.

### 2d. Lookups that come back 0

1. **No resolve: everything is 0** (O, 13:40). AddItem, GetIndexForItem, SpawnObject, Str2Text and SetText were all 0
   ("[MENU] engine fns: … 0x0"), next to "[STREAM] diag objects: 0 matched, 0 in the array". find_by_path walks
   0 objects (287-296) because the resolve never ran (2a). These are not renamed: 2311 has the same UListView,
   UGameplayStatics and UTextBlock functions (mod_fix_halloween.md T8), and the stage boxes work in good launches.
   Those boxes need all three: g_envMenuOn (3949).
2. **Renamed in 2311: the avatar menu's Blueprint lookups are 0 in every launch.** skin_menu_poll looks up
   `/Game/Visuals/Skins/OculusAvatar/BP_ReadyPlayerMeAvatarSkin…_C`, `W_SkinItem_C.OnListItemObjectSet/OnMouseButtonDown`
   and `W_ProfileMenu_C`'s `BndEvt__…AvatarList…` (3705-3709). On 2311 these are C++:
   - `UTribeReadyPlayerMeAvatarSkin`;
   - `UTribeProfileMenuWidget.AvatarList` @0x398;
   - `UTribeSkinItemWidget`, which has no OnListItemObjectSet or OnMouseButtonDown UFUNCTION.

   (mod_fix_halloween.md:98, 137-138; O: the class-name literals TribeReadyPlayerMeAvatarSkin, TribeProfileMenuWidget and
   TribeSkinItemWidget are in the 2311 library as UTF-16, u16find.py.) So g_skinMenuOn never turns on (3717-3718) and
   the avatar boxes never appear. This is a port gap (avatar_plan.md step 1), not timing.
3. **Transient zeros in good launches** (O in code):
   - skin_menu_poll calls menu_resolve_engine_fns before any resolve (3703), so the 0x0 line repeats every 2 s until the
     resolve. env_menu_poll does wait (3843).
   - find_by_path doesn't refresh the object count. After an early resolve (NumElem 5009-5575 seen today), objects
     created later stay invisible until something calls refresh_numelements; the auto-load's refresh (4033) does so
     within ~2 s.

### 2e. stream.txt "sometimes not parsed after a restart"

1. **It was parsed, but nothing applied** (O, 13:40). st_diag_objects ran at 13:41:08, and it runs only once g_stIdx ≥ 0
   (stream.cpp:185-186). But TribeVideoCallManager is found through the object array (190-199), so with no resolve
   stream_tick returns at 249 and neither the size nor the encoder settings apply. From the user's side that looks like
   "not parsed". The root cause is 2a.
2. **The encoder settings during a Twitch stream need the driver.** `streaming` comes from GetIsChannelStreaming, which
   is called only on the game thread (255). On the poll thread `live` is just the in-call flag. Without the avatar actor,
   the 1280x720 size (off-call, poll thread) can still apply, but the fps and kbps settings depend on the call flags (D).
3. **Latent defect (D, not seen today).** stream_poll stores the file's mtime/size key before it knows the read worked
   (stream.cpp:175-178). A failed fopen or a short read parses an empty config, marks it current, and the file isn't read
   again until it changes.

### 2f. load_result.txt at 33.6 MB

- **Who writes it:** only `load_status` (915-916). Each line costs fopen + fprintf + fclose + chmod on /sdcard, plus a
  logcat line. Nothing ever trims it (O).
- **Who reads it:** nothing in the mod. scripts/fix_login.sh skips it when it compares files (lines 41, 245), added after
  the 13:00 run stopped on "tribemod: differences: load_result.txt" (O, fix_login.log).
- **Why it grows (O in code).** `follow_update` logs when `t==1 || t%180==0`, with t = g_isoTicks + g_camTicks
  (1129-1131). On 2311 neither counter moves: only the ReceiveTick path (3413-3414) increments them, and it never fires.
  So t stays 0 and every driver run writes a line.
- **Measured (O):** 7.8 MB at 13:35, 33.6 MB at 15:00. 250,256 such lines total 32.6 MB. After 13:35, 193,144 lines came
  in ~74 min of driver time, about 43 lines/s or ~6 KB/s (D).
- **Cost (D):**
  - The driver does two FUSE file operations and a log write about 43 times a second on the game thread.
  - The 256 KiB main logcat buffer (O, `logcat -g`) holds about 2-3 minutes of mod output. That's why neither the crash
    session's nor the 14:26 launch's mod lines survived.
  - Every reseed copies the file off the headset and back.

## 3. Design: everything loaded on every launch

Rules the design follows:
- The ProcessEvent patch happens only where no thread can be executing ProcessEvent, and is verified.
- Every later step runs in one supervisor. Each step waits for exactly what it needs, retries with a time limit, and
  logs one line on every state change.
- No engine call gets an object without a liveness and identity check.
- The world can change under the mod; when it does, the mod notices and re-runs the steps.
- Status goes to one line.

### 3.1 The hook: constructor only, verified

- Install ProcessEvent **first in on_load**, after the base is found and **before** the poll, httpd or any other thread
  starts. At that point libUnreal's own initializers haven't run, so no thread can be inside ProcessEvent (D: ELF load
  order).
- Check the prologue without `sr()` and `g_ranges`: parse /proc/self/maps into local variables, require that
  [pe, pe+20) lies in an `r-x` mapping of libUnreal.so, then read the word directly.
- **Verify after A64HookFunction:**
  - word 0 = 0xd503201f (NOP);
  - word 1 = 0x58000051 (`LDR X17,#8`);
  - word 2 = 0xd61f0220 (`BR X17`);
  - the 8 bytes at +12 = repl_pe;
  - orig_pe ≠ 0.

  Log `[HOOK] ProcessEvent hooked @… verified (attempt n)`. On a failure, retry up to 5 times, 20 ms apart, still inside
  the constructor. After that log `[HOOK] FAILED: <reason>`; the status line shows hook=0, so a bad launch is visible
  at once.
- **Don't let tribemod's readability decide whether to patch.**
  - If opening executor_on fails with ENOENT while the tribemod directory itself opens: safe mode, no patch (today's
    meaning of removing executor_on).
  - Any other failure (EACCES, the directory missing or unreadable, which is the first launch after a reinstall): patch
    anyway with `g_mod_on=0`.
  - repl_pe's first statement becomes `if(!g_mod_on){ orig_pe(self,func,parms); return; }`.
  - The poll thread sets g_mod_on=1 once it can read executor_on, and logs it.
- **Remove pe_install_thread**, so nothing patches after the constructor. **Move st_hook_send's two re-send hooks**
  (stream.cpp:116-119) into the same constructor block, with the same local maps check. That removes today's
  poll-thread `load_maps()` at stream.cpp:109 and the poll-thread code patching.
- **Don't let ini_upsert delete keys when tribemod can't be read** (740-759). Leave both ini files as they are and log
  `[INI] tribemod not readable yet: ini left as is`. Today an unreadable tribemod removes the RPM URL key.

### 3.2 Safe reads from several threads

- `sr()`, `in_range()` and `load_maps()` share one table and one sigjmp_buf across the constructor, the poll thread, the
  game thread, the httpd thread and the freeze thread.
- Build each new range table in a fresh buffer and publish it with one atomic pointer store; readers load the pointer
  once.
- Give the fault guard thread-local state: a `__thread` jmp_buf and flag, which the handler tests instead of
  `g_dump_tid`.
- Use `sigsetjmp(…,0)` with SA_NODEFER on the guard handler, so a read doesn't cost a signal-mask syscall.
- (A: bionic's `sigsetjmp(…,1)` saves the mask with a syscall. That's per read today, and a find_by_path walks ~56k
  objects with ~100 reads each.)

### 3.3 Object safety

- **New `WRef`:** `{ptr, index, serial, class, name}`, filled when a pointer is stored. `wref_get` returns ptr only if
  all of these hold:
  - index < NumElements;
  - the FUObjectItem at index (stride 0x14, 112) still holds ptr;
  - its flags carry neither Garbage (1<<21) nor Unreachable (1<<28), the bits em_soft_get already uses (2333);
  - either the captured serial (item+0x10) is non-zero and still matches, or, when it was 0, the object's class (+0x10)
    and FName (+0x18) are unchanged.

  Reuse of the address by a different object fails the check; today's `obj_alive` passes it.
- **Convert every cached object that is handed to an engine call:**
  - g_gColl, g_mpcColl;
  - g_pawn, g_camComp, g_vrOrigin, g_mcL/R;
  - g_emGameState, g_emList, g_emRig, g_emStream, g_emScreens[], g_emVM, g_emOurScreen, g_emItems[], g_emVoidItem;
  - g_smList, g_smItems[];
  - club.cpp's g_cPawn, g_cVRO, g_cCam, g_cPC, g_cPar, g_csSide, g_csComp, g_csMainComp;
  - g_stMgr, g_stPC, g_gSpotComp, g_lComp[], g_hdCap, g_droneCap, g_cvMenu, g_cvBtn.
- **The crash fix itself:**
  - show_set and giant_mpc call `wref_get(&g_gColl)` on every write and skip the write when it fails;
  - giant_lookup clears a dead collection whatever the stage state;
  - em_unload clears it and bumps g_showGen, so club re-reads its keys.
- **World changes.** The supervisor keeps WRefs to the game state and the local pawn. When either fails, or
  GetGameState returns a different object, it increments `g_worldGen` and resets everything world-scoped:
  - the stage goes back to "re-apply";
  - the show collection, the club, the camera view and the menu lists are looked up again;
  - our avatar actor is respawned in the new world (the old one unrooted).

### 3.4 The startup supervisor

Each step below has a state: waiting(reason), working, done, or gave up(reason). Each runs where it does today, and
logs one line when its state changes.

| Step | Needs | Done when | Retry / limit | Change from today |
|---|---|---|---|---|
| hook | — | patched bytes verified | 5 × in the constructor | 3.1 |
| resolve | — (read-only) | object array found and > 1000 objects; `refresh_numelements` before every lookup pass | every 1 s; FAIL at 60 s | no longer waits for orig_pe or auto_load (4031) |
| lookups | resolve | all engine natives found in one pass: glTFRuntime, menus, env, MPC library, GameplayStatics | each poll; the missing names logged once, then every 30 s | one place, one log line |
| world | lookups | local pawn and game state alive (WRefs) | every 1 s | new; on loss: worldGen++ |
| driver | world | runs from repl_pe every ≥ 16 ms | — | **runs when the world is up, not only with g_isoActor** (3379); add g_pawn to env_menu_tick's world contexts (3314) |
| avatar | world, camera manager | do_load succeeded and our actor is spawned | do_load re-armed after a failure, 3 tries 10 s apart; if Tribe's RPM body hasn't appeared 30 s after the world is up, load without it (do_load already copes, 1297) | today: one arm (auto_done), no retry |
| skin | avatar | do_load loaded active_skin.txt's file | with the avatar | reports the file name |
| stage | world, lookups, game state, CurrentEnvironment stable 4 s, idle | our level visible (EM_ACTIVE) | a refused or failed load retries 3 times, 15 s apart, logging the reason; on a world change while active, back to waiting | **active_env.txt changes only on a user pick: ours sets it, a press-confirmed stock pick clears it (3323). Remove the deletes in em_fail (2647) and "Tribe switched environment" (3369)**; autoDone becomes a state |
| menus | lookups, the live lists | env boxes added == envs.txt lines; avatar boxes == skins/*.glb, once ported | each tick | avatar menu: port to the 2311 classes (avatar plan); until then it reports `avatar:n/a` and isn't required |
| stream | resolve, manager found | stream.txt parsed non-empty, and Tribe's size pair == stream.txt's size | each poll | don't store the file key when the read fails or is empty (stream.cpp:175-178) |

A part is required only if its file or flag asks for it:
- avatar: auto_load;
- skin: active_skin.txt;
- stage: active_env.txt names a box;
- stream: stream.txt has size=;
- env menu: the env_menu flag;
- avatar menu: the skin_menu flag, and only once the menu supports this build.

That's "everything the files ask for", and no more.

### 3.5 The status line

The poll thread prints one line every 2 s until all required parts are done, then every 60 s. It also writes the same
line to `tribemod/ready.txt` (tmp file + rename, overwritten, never appended), so a test can read it with `cat` if logcat
has rotated:

```
[READY] all=1 hook=1 world=1 avatar=1 skin=horseman.glb stage="Graveyard Shift" stream=1280x720 menus=env7/7,avatar:n/a drv=43/s gen=1 t=41.2s
[READY] all=0 hook=1 world=1 avatar=1 skin=horseman.glb stage=waiting(settle 2/4) stream=pending(no manager) menus=env0/7 drv=40/s gen=1 t=24.8s
[READY] FAIL t=180.0s missing=stage(level not loadable x3),menus(env 0/7)
```

- `hook` is 1 when the patched bytes verified and ProcessEvent calls are counting.
- `t` is seconds since the constructor.
- After 180 s with parts still missing, one FAIL line, then the 60 s cadence goes on.

**Logging changes that keep it readable:**
- follow_update counts its own runs (1129-1131) and logs once per 180.
- load_status keeps writing load_result.txt but rotates it at 1 MB, as freeze_log.txt rotates at 512 KB (freeze.cpp:83-86).
- No per-frame line goes to logcat, so the `[READY]` lines and a crash's last lines stay in the 256 KiB buffer.

### 3.6 Every change

| # | File / function (line) | Change | Why | Risk |
|---|---|---|---|---|
| 1 | dumper.cpp on_load 4110-4127, pe_install_try 4096-4106 | hook first, before threads; local maps check; verify the bytes; retries inside the constructor; `g_mod_on` pass-through when tribemod is unreadable | 2a: both no-hook launches; no live patching | low: same patch, earlier; pass-through adds one load + branch per call |
| 2 | dumper.cpp pe_install_thread 4108 | delete | 2a: late patching races the GameThread | none |
| 3 | stream.cpp st_hook_send 116-119 / st_hook_one 101-115 | run from the constructor block; drop its `load_maps()` (109) and its mprotect | removes the poll-thread table rewrite and the poll-thread code patch | low: Tribe's re-send functions aren't running at startup (A) |
| 4 | dumper.cpp ini_upsert 740-759 | skip all edits if tribemod/ can't be opened | the first launch after a reinstall deletes the RPM URL key today | none |
| 5 | dumper.cpp sr/in_range/load_maps 58-90, segv_handler 76-81, run_guarded 1306-1311 | published range table; thread-local guard; no mask syscall | multi-thread races (2a, candidate 1); per-read syscall | medium: touches every read; keep semantics, test with the dumps |
| 6 | dumper.cpp new WRef + wref_get, obj_alive 2148 | identity-checked weak references; convert the list in 3.3 | 2b: stale and reused pointers | medium: many call sites; mechanical |
| 7 | dumper.cpp show_set 2749, giant_mpc 2745, giant_lookup 2697-2713, em_unload 2639-2645 | wref check on every write; clear dead collections; bump g_showGen on unload | 2b: the crash | low |
| 8 | dumper.cpp new world tracker (poll + env_menu_tick) | g_worldGen; reset world-scoped caches; respawn our actor | 2b/2c: pointers from a previous world; stage not re-applied | medium: respawn path is new; log every reset |
| 9 | dumper.cpp repl_pe 3379, env_menu_tick 3314 | driver runs when the world is up; g_pawn as a world context | §1 step 6: stage, menus and stream stop depending on the avatar | low: each tick function checks its own needs (most already do) |
| 10 | dumper.cpp dump_thread 4031-4034 | resolve without orig_pe/auto_load; avatar arm/retry state machine; load without Tribe's body after 30 s | 2a/2c: resolve gated on the hook; one-shot avatar | low |
| 11 | dumper.cpp env_menu_poll 3939-3942, env_menu_tick 3323-3370, em_fail 2646-2650 | stage state machine with retries; never delete active_env.txt except on a press-confirmed stock pick | 2c | low: a stock environment picked without a recognized press would be overridden at the next launch (the user picks it again, which clears the choice) |
| 12 | stream.cpp stream_poll 173-183 | keep the old key when the read fails or is empty | 2e latent defect | none |
| 13 | dumper.cpp follow_update 1129-1131, load_status 915-916 | own run counter; rotate load_result.txt at 1 MB | 2f | none |
| 14 | dumper.cpp new status supervisor (poll thread) + tribemod/ready.txt | `[READY]` line | pass/fail from logcat | none |
| 15 | dumper.cpp skin_menu_poll 3699-3718, menu_tick 2199-2214, repl_pe 3395-3402 | avatar menu on the 2311 classes (separate job: avatar_plan.md) | 2d | as in that plan |
| 16 | scripts that install or reseed (fix_login.sh and friends) | after an install, one warm-up launch before the user's first real launch (or fix the parent dirs' mode) | the first launch after a reinstall can't read tribemod in the constructor (2a). Change 1 makes this harmless for the hook; the ini edits still need it | low (A: that a warm-up launch fixes the ownership) |

Base for the build: today's src. Change 2 removes the retry thread; keep the atomic flag (harmless). The two env
diagnostics can stay or go.

## 4. Launch test (the build job writes the script)

This test is for the user to run while not live. It never installs anything, never sends input, and never taps a
dialog.

1. **Before the first launch:**
   - Check the device is awake (`dumpsys power`: mWakefulness=Awake). Tribe only ticks while the headset is worn or
     awake; the freeze log shows the "headset-off pause".
   - Check that `pm path com.TribeXR.TribeXR` shows the mod's install.
   - Record the md5 of the installed base.apk, and print it at the end so the result names the build.
2. **For each of N launches (default 10):**
   1. `am force-stop com.TribeXR.TribeXR`. Wait until `pidof com.TribeXR.TribeXR` is empty (≤ 10 s); otherwise mark the
      launch "did not stop" and continue.
   2. Note the device time, then `am start -n com.TribeXR.TribeXR/com.epicgames.unreal.GameActivity`.
   3. Stream `logcat -v threadtime -T '<that time>' -s TRIBEMOD:I` into launches/<n>.log. Also save `logcat -b crash -d`
      at the end of the launch.
   4. **Meta's unofficial-app dialog** (com.oculus.vrshell/.systemdialog.launchcheck.UnOfficialAppDialogActivity) was
      up at each launch seen in today's logs (13:40:38, 13:42:02, 13:57:42, 14:26:25) and went away within ~2 s each
      time (O; the user was in the headset, A). Its buttons are Restore / Close, and Restore wipes the mod
      (NOTES.md:3767-3770, 5848-5856).
      While it shows in `dumpsys activity activities`:
      - the script prints "In the headset: tap OPEN APP, never Restore";
      - it waits up to 120 s, never taps, and doesn't count that time;
      - if the dialog stays up, it stops the whole test;
      - Close on that dialog can drop the launch (NOTES.md:5856). If the process is gone right after the dialog, the
        script counts the launch as "dropped", not failed, and launches again.
   5. Wait up to 150 s for a `[READY] all=1` line (pass), a `[READY] FAIL` line (fail), or the process dying (fail,
      "crashed"; attach the crash buffer). If 150 s pass with none of these, fail with the last `[READY]` line's missing
      parts.
   6. Record per launch: number, pid, hook time (`[HOOK]` line), all=1 time, the parts missing, and the crash summary
      (fault address and the first libhook frame).
3. **At the end:**
   - Print a table with PASS/FAIL per launch and the totals, plus the most common missing part.
   - Then `am force-stop` once more, so the headset is left with Tribe closed. The user relaunches it.
4. **Why N = 10:** today 2 of 5 launches failed before anything loaded. If the true failure rate were still 40 %, ten
   passes in a row would happen with probability 0.6^10 ≈ 0.6 %. Use N = 20 for a 10 % rate (0.9^20 ≈ 12 % chance of
   passing anyway).
5. **The first launch after an install or a reseed is a separate case:** it is today's 13:40 failure. After the fix it
   should pass too, but with that launch's ini edits missing (§1 step 1a). If the test starts right after an install,
   it reports launch 1 on its own line and judges the other N-1 as usual.

## 5. Risks and what wasn't checked

**Not determined:**
- What freed MPC_HwShow at 13:57 (2b).
- What crashed the six 13:20-13:23 launches (2a).
- What failed in the 14:26 launch (2a candidates).
- Which code path deleted active_env.txt (2c).

All four need logs that rotated away or root-only tombstones. The logging changes (3.5) are what make the next
occurrence readable.

**Derived without a device check:**
- The engine function names in the backtrace (structure matched to UE 5.4; no symbols).
- That patching in the constructor is race-free (ELF load order).
- That the warm-up launch fixes the directory ownership (A).
- The 35 s startup figure comes from freeze self-test times minus 20 s.

**New risk in the design:**
- The world-change reset and the avatar respawn (change 8) are new code paths.
- The WRef conversion (change 6) touches many call sites.
- The read-guard change (change 5) touches every memory read.

Each needs a pass with the dumps (`dump_now`, `usmap_now`) and a full set rehearsal before a live set.

**What to watch after shipping:**
- `[READY]` times across the launch test.
- Any `[HOOK] FAILED` line.
- `stage=` retries.
- load_result.txt staying under 1 MB.
- Frame time (`[PERF]`). Removing the per-frame file writes should help; that is (A) until measured.
