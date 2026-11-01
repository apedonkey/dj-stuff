# Tribe mod on 0.12.6 (2311): the plan for "everything loads, every launch"

2026-10-31, written by the build job before it built anything and brought up to date after the builds (17:40). The
user asked: "we need to get all the levels and characters in. also i need a solid plan to have all of it load
everytime. sometimes i have to restart the game multiple times."

This plan stands on three investigations from today (claudedocs/mod_2311_load.md, mod_2311_levels.md,
mod_2311_characters.md), the interactive session's review notes, and this job's own reading of the source and the 2311
library. Labels: **(O)** observed (read or ran it), **(D)** derived (steps given), **(A)** assumed (not checked).
What was built, change by change, with file, function, reason and confidence: claudedocs/mod_2311_build.md.

## 1. Why launches fail today, in one paragraph

Every feature of the mod (the character, the stage, the menus, the stream settings, the head, the drone) runs through
one hook on Tribe's `ProcessEvent`. On two of today's five launches after the reinstall the hook never went in, so
nothing loaded and the only fix was another restart (O, load doc 2a). One cause is proven: on the first launch after an
install the mod can't read its own folder yet, takes that as "switched off", and never tries again (O). The other
launch failed while another thread was rewriting the shared memory-map table the hook's safety check reads (D, a race
in the code; not logged). On top of that, launches that did get the hook could still end with no character (a skin
load is tried once and never again), no stage (the mod deletes the saved stage after any failed load, and the auto-load
needs the character first), and the 13:57 crash came from the light-show code writing to a stage object that had been
freed (O, both docs agree on the mechanism).

## 2. What loads at launch, in what order

### Step 1: before Tribe's engine starts (the library constructor)

Runs once, on the thread that loads Tribe's library, before any of Tribe's own code runs.

1. Edit Tribe's ini files (body tracking, logging; from step B the Ready Player Me keys are left alone, section 5).
   Skipped if `tribemod/` isn't readable yet, so a first launch can't delete keys by mistake.
2. Find Tribe's library in memory (up to 5 s).
3. **Hook `ProcessEvent` right here, before any thread exists.** Nothing can be running `ProcessEvent` yet, so the
   patch can't race the game. The mod checks the first instruction (`stp x29, x30, [sp, #-0x60]!`, O in the 2311
   library), patches, reads the patched words back (NOP, `LDR X17`, `BR X17`, the hook's address) and checks the
   trampoline. Up to 5 tries, 20 ms apart, and never a second patch once anything was written. The check uses its own
   fresh read of the memory map, not the shared table.
   - `tribemod/` not readable yet (the first launch after an install): hooked anyway, in **pass-through** (every call
     goes straight to Tribe); the mod switches itself on as soon as it can read `executor_on`.
   - `tribemod/` readable and `executor_on` missing: safe mode, no patch (today's meaning of that file).
   - Tribe's two encoder re-send functions are hooked at the same moment (their first 16 bytes checked, O).
4. Start the poll thread (the supervisor) and the small HTTP server.

Log: `[HOOK] ProcessEvent hooked @... verified (try 1; ...)`, or `[HOOK] FAILED: <reason>`, or `... pass-through`.

### Step 2: the supervisor (poll thread, every 0.5 s)

Each part waits for exactly what it needs, retries with a limit, and logs one line when its state changes.

| Part | Waits for | Done when | Retries |
|---|---|---|---|
| mod on | `executor_on` readable | read | every 1 s (pass-through until then) |
| resolve | the mod on (no longer waits for the hook's calls or `auto_load`) | Tribe's object list found | every 2 s |
| game thread | `ProcessEvent` calls on the thread named `GameThread` | known | one name check per 64 calls until found |
| world | resolve; Tribe's local pawn (camera manager -> player controller -> pawn) | the game thread has wired the pawn, camera and hands | checked every 0.5 s; if the pawn goes away (a room change), everything world-bound is dropped and wired again |
| character | world | `active_skin.txt` says what to show: a mod file (loaded once Tribe's avatar body is there, or 30 s after the world is up without it), or `tribe` (Tribe's own avatar, nothing loaded) | a failed load: 3 more tries, 10 s apart; our avatar actor: 5 tries, 5 s apart |
| stage | world, the stage menu's lookups, Tribe's environment unchanged for 4 polls (~8 s); the character is **not** needed | `active_env.txt` names a mod stage and it is in; a stock one (`stock:<name>`) is Tribe's to restore | a failed load: 3 more tries, 15 s apart; a level that goes away is loaded again; tries count afresh only after the stage held 60 s; 12 loads per launch at most |
| menus | world, Tribe's lists | the stage menu has all `envs.txt` boxes (step B: one box per `skins/*.glb` plus "Tribe Avatar") | each second; required only once Tribe's list exists (it may need the menu opened once) |
| stream | resolve, Tribe's video-call manager | `stream.txt` read and Tribe's stream size equal to it | each poll |

`active_env.txt` and `active_skin.txt` change only when **you** pick something (note 18): a mod stage writes its
label, a stock environment writes `stock:<name>`, a mod character writes its file, Tribe's own avatar writes `tribe`.
The mod never deletes them by itself.

### Step 3: the game thread (inside the hook)

Every 16 ms or more, on the game thread only (the mod now checks the thread; before, any thread calling
`ProcessEvent` could run the per-frame code and the loads), once the **world** is up, not only once our avatar exists:
light show, walking, intro, camera button, stream encoder, body following, body tracking, drone, head, menus, stage
loading, frame-rate log. Each part checks its own needs: the body, body tracking and the head need our avatar; the
light show needs its stage in and its collection re-checked; walking needs its map.

Every call the mod makes into Tribe goes through one check first: the object it calls, and every object it passes,
must still be alive in Tribe's object list (the engine's own "is it being collected" test) and of the right class.
If not, the call is skipped and logged once (`[CALL] skipped ...`). This is the general fix for the 13:57 crash and
anything like it after a stage switch or a room change. The light-show collection also gets an exact identity check
(slot, serial number, class and name) and is looked up afresh for every stage load (levels doc S1).

## 3. What you see

- Launch as always. Meta's "unofficial app" dialog appears for about 2 s: tap **Open App**, never Restore (Restore
  reinstalls the store version and wipes the mod).
- The DJ room appears. About 35-60 s after launch (A: today's good launches took ~35 s to the character), your last
  character appears and your last stage loads (Tribe switches to the Void for a moment, then the stage fades in). The
  boxes are in Visuals > Environments (and, from step B, in Profile > Avatars).
- If a part fails, only that part is missing, and the `[READY]` line says which.

## 4. How a launch is judged: the `[READY]` line

The supervisor logs one line every 2 s until everything required is up, then once a minute, and writes the same line
to `tribemod/ready.txt` (replaced whole each time, readable over adb even after logcat rotates):

```
[READY] all=1 step=C pid=17390 t=41.2s hook=1 world=1 avatar=1 skin=horseman.glb stage="Graveyard Shift" stream=1280x720 menus=env7/7,avatar7/7 paks=7/7 gen=0 skips=0
[READY] all=0 step=C pid=17390 t=24.8s hook=1 world=1 avatar=1 skin=horseman.glb stage=waiting(settle 2/4, try 1) stream=1280x720 menus=env:list-not-open,avatar:list-not-open paks=? gen=0 skips=0 missing=stage(waiting(settle 2/4, try 1))
[READY] FAIL step=C pid=17390 t=180.0s ... missing=stage(gave-up("Graveyard Shift" failed 4 times))
```

- `pid` is Tribe's process (a test tells this launch's file from the last one's), `gen` counts world changes, `skips`
  counts calls the call check refused, `paks` (step C) is how many `envs.txt` levels are in the mounted paks.
- A part is required only if your files ask for it: the character if `auto_load` exists and `active_skin.txt` isn't
  `tribe`; the stage if `active_env.txt` names a mod stage; the stream if `stream.txt` has `size=`; the menus if
  `env_menu` (from B also `skin_menu`) exists and Tribe's list for them exists.
- After 180 s with parts still missing: one `FAIL` line naming them, then the once-a-minute line goes on.
- `tribemod/ready_history.txt`: one `start` line per launch, then one line with the result (READY or FAIL, the time,
  what was missing), capped at 200 lines. A `start` line with no result line means that launch ended early.
- `load_result.txt` no longer gets a line per frame (that flood is why no mod log survived the 13:57 crash), and it
  rotates at 1 MB.

## 5. Your avatar and Ready Player Me (note 19)

> **Correction (interactive session, 2026-10-31 ~18:00): Ready Player Me is gone.** Today readyplayer.me,
> tribexr.readyplayer.me, models.readyplayer.me and api.readyplayer.me all fail from the PC (curl, no answer), while
> google.com answers 200 (O). NOTES.md ~3506 found the same on 2026-09-29 (models.readyplayer.me NXDOMAIN). So Tribe's
> Ready Player Me panel can't load an avatar, and the "load your avatar there once" route below won't work.
> The user's "regular avatar" in Tribe is the **Meta avatar** (a separate path, MetaAvatar2), which Tribe showed on 2304
> once the dead Ready Player Me key was gone (NOTES.md ~3514: remove avatar_url.txt, relaunch -> Meta avatar; O on
> 2304, A on 2311). On build B the way back is the one-shot **`tribemod/rpm_url_clear`** (one launch), not the Ready
> Player Me panel. Test it in 7.3.

- **What the mod has been doing (O).** At every launch it wrote `avatar_url.txt`'s `http://127.0.0.1:8000/...` into
  Tribe's `[TribeAvatar] ReadyPlayerMeAvatarUrl` (GameUserSettings.ini, in Tribe's private data) and copied
  `custom.glb` into Tribe's avatar cache. Nothing listens on port 8000 (the mod's server is on 8787) and there is no
  ETag, so Tribe's load of that URL can't succeed (D, from the cache rules in NOTES.md ~3500).
- **Your original URL is not in any backup (O).** Every saved ini and every `ini_upsert.log` since 2026-10-01 holds
  the loopback URL; today's reinstall gave Tribe a fresh ini (SET 283->355 bytes at 13:42) and wiped Tribe's avatar
  cache (`Documents/`). There is no old value to restore.
- **How your Ready Player Me avatar comes back (D, with one A).** Tribe 0.12.6 has its own Ready Player Me panel again
  (2311 library strings: "My Ready Player Me Avatar", "Use your latest custom avatar from tribexr.readyplayer.me",
  `UTribeRPMAvatarCreatorWidget`; O). From step B the mod stops writing or deleting the two keys, so whatever Tribe's
  panel saves stays saved: open Profile > Avatars > the Ready Player Me entry and load your avatar there once.
  (A: that readyplayer.me answers today; NOTES.md recorded it unreachable on 2026-09-29.)
- **The mod's dead URL stays until you choose.** Step B stops re-writing it but doesn't remove it on its own: what Tribe
  shows with the key gone (its default avatar) or with it there (a failed load) isn't known offline.
- **One-shot helpers (step B, never automatic).** `tribemod/rpm_url_set.txt` (one line, your avatar URL): written into
  Tribe's setting at the next launch, then renamed `rpm_url_set.done`. `tribemod/rpm_url_clear` (empty file): removes
  the dead URL at the next launch, then is deleted. `tribemod/rpm_route_on`: the old behaviour exactly. Logs never print
  a URL past its host.
- **Picking a mod character never changes your saved Tribe avatar (B).** A press on a mod box marks that box
  "selected" inside the press, before Tribe decides whether to apply it; Tribe never applies a selected Ready Player Me
  box (O: the press handler at store 0x5B4C890 reads `bSelected` @0x350 after the mod sees the press; that class's
  CanReapply is `mov w0, wzr; ret`; `SetSelected` only stores the flag and redraws). So Tribe applies and saves nothing.
  The list's own click handler applies nothing either (decoded at 0x594A574). If Tribe ever applies a mod box by
  another route, the log says `[MENU] WARNING Tribe applied our box` (Tribe then saves `OculusAvatar=ReadyPlayerMe_Custom`).
- **The Tribe avatar box (B).** The mod adds a **"Tribe Avatar"** box after its characters. Pressing it, or any of
  Tribe's own avatar boxes, hides the mod character, shows Tribe's avatar and writes `tribe` to `active_skin.txt`, so
  the next launch also starts with Tribe's avatar. A mod box goes back. Tribe's own Ready Player Me box is missing today
  (A: its Ready Player Me list is empty after the cache wipe); the step B diagnostic lists exactly what Tribe built.
- **Kill switches (no rebuild):** `tribemod/tribe_avatar_shown` (never hide Tribe's avatar), `tribemod/skin_boxes_off`
  (no mod boxes in the avatar menu; the rest of B stays).

## 6. The three builds

Each is its own APK, so a headset test can tell which step broke something. Each differs from
combo_pedriver_2311.apk only in `lib/arm64-v8a/libhook.so` and the signature files (checked, O).

| Build | File (backup/mod2311_build/) | md5 |
|---|---|---|
| A: startup + crash fixes | mod2311_A.apk | fb2293b64af51630069f2e26bd482f44 |
| B: A + characters | mod2311_B.apk | 7b263977a3374a38736eaf14032167f9 |
| C: B + stages | mod2311_C.apk | 8feaaad05f67ec3ebf3e62b3ecb3fdd0 |

No stage pak or OBB changes: all seven stages are the paks that ran on 2304 (levels doc).

## 7. The tests (the user and the interactive session run them; this job touched nothing on the headset)

### 7.1 Every build: cold starts, and the preflight

`bash scripts/launch_check.sh [N]` (default 10 launches; `--dry-run` prints the commands): force-stop, start, wait up
to 120 s for `[READY] all=1` (from `tribemod/ready.txt`, matched by Tribe's pid, then logcat), record PASS/FAIL with
the line and the missing parts, stop on a crash and save its lines. It never taps anything; if Meta's dialog with
**Restore** stays up, it stops and tells you. Ten passes in a row would be a 0.6 % chance if today's 40 % failure rate
were still there (load doc 4). Launch 1 right after an install starts in pass-through: judge it apart.

`bash scripts/launch_check.sh --preflight`: the check about an hour before a set. Headset on USB and awake, Tribe
running (started if not) and READY, then the Meta login: auth errors since the launch, then again while you press Go
Live once. One verdict: **GO**, or **NOT READY: <part>** with the fix (login errors: run "Fix Tribe Login.exe"; a part
not loaded: close Tribe, launch it again, run the check again).

### 7.2 Build A (in the headset, not live)

1. Install A. First launch: `[HOOK] ProcessEvent hooked ... verified`, `[HOOK] the game thread: tid ...`,
   `[WORLD] up`, `[AVATAR] horseman.glb loaded`, `[ENV] auto: applying 'Graveyard Shift'`, then `[READY] all=1`.
2. `launch_check.sh` 10 launches: 10 PASS. Any `[CALL] skipped` line in a launch log is a finding (the call check
   refused a call): note its function.
3. Play 10 minutes on Graveyard (walk, intro button, a track). Then switch Graveyard -> Graveyard (re-pick), a stock
   environment, Graveyard. Each unload logs `[GIANT] show bus released`, each load `[GIANT] show bus adopted ... gen N`
   with a new N. No crash. `active_env.txt` reads `stock:...` after the stock pick and the label after the re-pick.
4. Take the headset off 60 s, put it back on, play 5 minutes.
5. `ready_history.txt` has a start and a result line per launch.

### 7.3 Build B (characters; note 5: all six skins, the four heads, the Tribe/RPM box)

Open Profile > Avatars: Gremlin, Horseman, Lampwing, Majortom, Santa, Skullbuck and Tribe Avatar, next to Tribe's own.
For each character: press it once; the log shows `[MENU] press on our box 'X': selected before Tribe's check`, then the
load; only that character shows (also in the selfie view), nothing at the decks, Tribe's avatar hidden. Lampwing: watch
for a stall (9 s on 2304). Heads (gremlin, horseman, majortom, santa): `[HEAD] loaded heads/<x>.glb`; the flight after
~10 min of play (`head.txt` = auto). Tribe Avatar (and Tribe's own boxes): Tribe's avatar shows, the mod character is
gone, `active_skin.txt` = `tribe`; relaunch: still Tribe's avatar, `[READY] ... skin=tribe`; press Horseman: back.
Never a `WARNING Tribe applied our box` line. The Ready Player Me check: the diagnostic block (`[MENU] diag: ...`)
lists Tribe's items; then, if wanted, `rpm_url_clear` (one launch) and Tribe's own Ready Player Me panel. Then the
cold-start test again.

### 7.4 Build C (stages; note 15: bring-up order, each followed by a switch test, never during a live set)

First launch: `[ENV] stages in the paks: 7/7 levels found`. Then Graveyard Shift -> Dino Classic -> Reactor -> Midtown
-> RED EYE -> Harvest Moon -> Dino Stage. For each, load it (menu or `active_env.txt`), check its lines (levels doc
5.1-5.7: `is IN`, `show bus adopted`, the walking map, intro actors, side screens, the lift), then switch to Graveyard
and back. Reactor as a guest in a room is the only way to see the gate change. Then the cold-start test with each stage
as the saved pick.

## 8. The change list

Each change, with its file, function, reason and confidence: claudedocs/mod_2311_build.md.

**A: startup and crash fixes**
1. ProcessEvent hooked in the library constructor, before any thread, checked before and after the patch; pass-through
   until `tribemod/` is readable; safe mode only when `executor_on` is really absent; the retry thread is gone.
2. Tribe's two encoder re-send hooks moved to the same moment (no code patching from the poll thread).
3. The ini edits skipped while `tribemod/` can't be read (a first launch can't delete keys).
4. The safe-read guard has a slot per thread; the memory-map table is rebuilt into a fresh table and published, never
   emptied in place; the signal handler is installed with a count and never chained to itself.
5. The mod works on the game thread only (per-frame work, menu handlers, loads).
6. Every engine call checked first (object and object parameters alive by the engine's test, and of the right class);
   raw writes into Tribe's objects check the class too.
7. The light-show collection as a weak handle, found per stage load, adopted and dropped on the game thread.
8. The per-frame work runs once the world is up, without waiting for our avatar; the follow log no longer writes a
   line per frame; `load_result.txt` rotates at 1 MB; the freeze recorder beats on any game-thread call.
9. World changes: the pawn is watched; everything world-bound is dropped and wired again; our avatar actor, its head
   and the stage come back by themselves.
10. The character: loaded with retries, our actor spawned with retries, `tribe` in `active_skin.txt` respected; engine
    lookups for the load and the spawn done once.
11. The stage: `active_env.txt` never deleted, stock picks recorded, failed loads retried (capped), a level that went
    away loaded again.
12. `[READY]`, `ready.txt`, `ready_history.txt`; quieter logs.

**B: characters** (on top of A)
13. The avatar menu on 2311's C++ classes: one box per character plus "Tribe Avatar", labelled from the list's boxes;
    a press marks the box selected before Tribe's check, so Tribe applies and saves nothing.
14. Tribe's avatar hidden while a mod character is up, shown for Tribe's boxes, with our character hidden then.
15. No mesh on Tribe's own avatar slot (the copy at the world origin is gone).
16. Tribe's Ready Player Me keys left alone, with the one-shot helpers of section 5.
17. The one-time avatar diagnostic; the menu kind decided only once the world is up.

**C: stages** (on top of B)
18. REACTOR's gate reads its two bitfield flags correctly.
19. A stage's intro runs only with its own ride file.
20. The soft-pointer test uses the engine's dead test.
21. A startup check that every `envs.txt` level is in the mounted paks (`paks=` in `[READY]`).

## 9. Risks

- **Nothing here has run on the headset.** The builds compile (the same 7 warnings as today's), their APKs match the
  live one except the library, and every 2311 address used was checked in the store library
  (backup/mod2311_build/tools/verify_2311.py). Behaviour is checked by reading, the disassembly and one review.
- **The call check can skip a call that should happen** (a false "wrong class"). It logs `[CALL] skipped <function>`
  once per function and counts `skips=` in `[READY]`: look for it in the first launch of each build.
- **Pass-through on a first launch** means that launch's ini edits are skipped (as today), and the mod wakes up once
  it can read its folder (A: seconds later). It also means ProcessEvent is patched on that launch even if
  `executor_on` turns out to be absent (calls only pass through).
- **A room change** drops and re-wires everything world-bound; that path is new and only testable in a room.
- **Tribe's saved avatar:** the selected-box block is verified in the disassembly, not on the device. A press by a
  route other than the box's mouse-down would apply the box: the log then says `WARNING Tribe applied our box`.
- **Our near-empty avatar items in Tribe's list (B):** Tribe builds a box for each natively; what it does with their
  empty thumbnail and avatar id wasn't decoded (the review's top item). A crash right after `[MENU] adding box` is the
  sign; then create `tribemod/skin_boxes_off`.
