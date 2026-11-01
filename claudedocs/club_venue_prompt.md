# New project brief: an indoor club venue for Tribe XR, built to be pitched to the Tribe devs

Paste this whole file as the first message of a new Claude Code chat opened in
`C:\Users\Chris\OneDrive\Desktop\tribe hack`. It is self-contained. It was written on 2026-10-07 by the chat that built
the Dino Stage, so that this new project gets its own context.

---

## 0. What I want from you (the new chat)

I'm a DJ who plays streamed VR sets in **Tribe XR** on a **Meta Quest 3**. Over the last week a Claude session and I built a
custom outdoor festival stage, the **Dino Stage**, and loaded it into Tribe through a native mod. It works and looks great.
Now I want a **second, different venue**:

- **An indoor club, medium size.** Not a festival field: a real room with walls and a ceiling, a stage, a dance floor and a
  bar/lounge feel. Dark, night-club atmosphere, lasers, haze and a big visuals screen.
- **People can join it and move around in it**, VRChat-style: thumbstick locomotion, not just walking in your play space.
- **Roles and a stage gate.**
  - The **host of the room** is the only one who can let a **DJ** onto the stage.
  - Only the host and the DJ(s) are allowed on the stage. Everyone else stays on the floor.
  - A non-DJ who walks up to the stage reaches a **gate** (or barrier) and **is not let in**.
- **Lasers, lights and visuals**: everything the Dino Stage has, adapted to an indoor room (see §4).
- **End goal: pitch the venue to the Tribe XR developers** so they ship it as an official environment, and everyone in
  Tribe can join it with no mods. Build it so they can adopt it with as little work as possible.

Work with me step by step. First a plan and a concept I approve (blockout renders like the Halloween concept, see §7).
Then build. Verify everything on the headset, and tell me plainly what's verified and what's assumed.

---

## 1. Who I am and how I play (respect these)

- I play **heavy dubstep, 128-150 BPM, mostly 140** (half-time feel: kick on 1, snare on 3), in **hour-long streamed sets**
  (Twitch, through Tribe's Go Live).
- I mix with the **channel faders and the filters** (the DJM's COLOR knob). I **never use the crossfader**. I cue the next
  song **in my headphones with its channel fader down**, so the crowd can't hear it until I bring it in.
- **Comfort:**
  - I found stage flashing "a bit too much for me": no strobes, at most 3 flashes per second, no one-frame flashes.
  - I liked how dark the Dino Stage was ("i liked how dark it was before"). It's a night-time vibe: the room is dark except
    for the DJ, the visuals, the lasers and the light hits.
- My "**keywall**" means **Tribe's visuals back wall**: the screen that plays videos from Tribe's media folder
  (`/sdcard/Movies` on the Quest). It does **not** mean Tribe's green chroma-key wall.
- I play Tribe's visuals from the media folder. We made an original **VJ loop pack** for the Dino Stage (§5.6).
- I'm on Windows 11; the Quest is connected over USB (adb). I often control things from my phone through Remote Control.

---

## 2. Hard rules (security and safety; never break these)

1. **APK signing.** Build the mod APK only with `bash scripts/sign_apk.sh <in.apk> <out.apk>`, run from the repo root with
   **no `cd` prefix** (an allow rule matches that exact form).
   - The keystore password lives in a private file outside the repo (`C:\Users\Chris\.tribe-signing\ks.pass`). **Never read,
     print or extract it**, from that file, from logs or transcripts, or by any other route.
2. **Never `adb uninstall` the mod.** That wipes the Meta login token, the 1.9 GB OBB and all the mod data.
   - Update with `adb install -r out/hookA/<build>.aligned.apk`.
   - The **only** exception is the re-seed (§3.4), and it needs my explicit OK.
3. **Never tap "Restore"** on Meta's unofficial-app dialog: always **OPEN APP**. Restore reverts to the store version.
4. My **Twitch stream key is a password.** Never log it or print it.
5. **Commit to git only when I ask.**
6. **Another Claude session may be building a Halloween stage** ("GRAVEYARD SHIFT", plan in
   `claudedocs/halloween_stage_plan.md`).
   - Don't edit its files: `Scripts\Blender\halloween\`, `build_halloween.py`, `hw_materials.py`, the fork copy
     `C:\Users\Chris\TribeUE\MetaHw`, `claudedocs\halloween_stage_notes.md`.
   - It reserved **pak chunk 54**.
7. **Don't edit the Dino Stage's files** for this project. Copy or import them instead:
   - `dino_stage.py`, `kit.py`, `show.py`, `crowd3.py`, `dino_materials.py`, `build_dino.py`, `NOTES.md`;
   - `hook/dumper.cpp`, unless a change is deliberately shared and I've agreed to it.
   - Give the club its own folders, scripts and notes (§7).
8. **The patch OBB is shared.** `make_obb.py` writes a fresh zip from the paks you list, so a push that lists only one
   stage's pak **silently removes the others**. Every push must include every current pak (§3.3).
9. **GPU lock.** Before any GPU-heavy job (Blender Cycles bakes, renders): `mkdir C:\Users\Chris\TribeUE\gpu.lock.d` and
   write `owner.txt` inside. Remove it when you're done. Other agents use the same lock. Unreal builds use `-nullrhi` and
   don't need it.
10. **Before pushing to the headset**, check whether Tribe is running (`pidof com.TribeXR.TribeXR`). Swapping the patch OBB
    or installing an APK closes Tribe, so ask me first if I might be in it.

---

## 3. The platform: what we know about Tribe XR (verified unless marked)

### 3.1 Engine and delivery
- Tribe is built on **Meta's Oculus fork of Unreal 5.4** (OVRPlugin 1.103 ≈ SDK v71). Tribe's own UMaterial has extra
  XR soft-occlusion fields, which shifts unversioned property indices.
  - **Custom materials must be cooked with the fork.** Never ship materials cooked with stock UE 5.4: loading them
    OOM-killed Tribe.
  - The fork editor is built at **`D:\MetaUE54`**: `Engine\Binaries\Win64\UnrealEditor.exe` and `UnrealEditor-Cmd.exe`.
  - The fork project is **`C:\Users\Chris\TribeUE\Meta\TribeXR\TribeXR.uproject`**.
  - `scripts/ue_schemadiff.py` compares class schemas between engines.
- Custom content ships in a **patch OBB**: `/sdcard/Android/obb/com.TribeXR.TribeXR/patch.2304.com.TribeXR.TribeXR.obb`.
  - It's a stored zip with comment "      2304" that holds `TribeXR/Content/Paks/pakchunkNN-Android_ASTC_P.pak`.
  - Tribe mounts it at startup and accepts unsigned paks. 2304 is Tribe's OBB version.
  - The main OBB is `main.2304...obb` (1.9 GB, backed up at `pulled/main.2304.com.TribeXR.TribeXR.obb`).
- Pak chunks in use:
  - **50**: Dino Stage + Festival (`/Game/Mods/Dino`, `/Game/Mods/Festival`)
  - **51**: ShaderTest
  - **53**: Dino Classic (`/Game/Mods/DinoAnim`)
  - **54**: reserved for Halloween
  - **Use 55 for the club** (check that it's free).
  - Find out how the project assigns a folder to a chunk (most likely a PrimaryAssetLabel) by looking at how chunk 50 is
    set up, and do the same for the club.
- **Every placed StaticMeshActor needs `set_collision_profile_name("NoCollision")`**. `SetCollisionEnabled` alone gets
  undone by `bUseDefaultCollision`, and a solid sky sphere once swallowed Tribe's menu pointer ray.
  - For the club's **gate and walls**, collision is something you'll need to design deliberately (§6). Know this pitfall.
- Unreal logs don't reach logcat (Tribe is a Shipping build). Verify from inside the game through the mod's own
  `TRIBEMOD` log lines.

### 3.2 The build pipeline (Dino Stage; copy its shape)
1. **Blender 4.5, headless**, at `D:\Tools\blender-4.5.14-windows-x64\blender.exe`. Generator scripts build the whole set,
   bake lighting into textures and export FBX plus PNG plus a `manifest.txt`. For the Dino Stage:
   - `C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\dino_stage.py`
   - modules `arch.py`, `giant.py`, `show.py`, `grounds\*.py` (`kit.py` contract, `preview.py` harness, `stagedeck.py`,
     `atmosphere.py` lasers + `atmosphere_lasercheck.py`), crowd v3
   - output folders such as `out_v81\`; the live stage was built from `out_v81`
2. **Unreal import + level build**, from `C:\Users\Chris\TribeUE\TribeXR\Scripts`:
   - `build_dino.py` with materials from `dino_materials.py`, run by `UnrealEditor.exe ... -ExecutePythonScript=...`;
   - env vars `DINO_ANIM=1`, `DINO_SRC=<bake folder>`, `DINO_GIANT_SRC`.
3. **Cook, pack, OBB.** Exact commands that work:
   ```
   export MSYS_NO_PATHCONV=1; UE=/d/MetaUE54/Engine/Binaries/Win64; P=/c/Users/Chris/TribeUE/Meta/TribeXR
   "$UE/UnrealEditor-Cmd.exe" "C:\Users\Chris\TribeUE\Meta\TribeXR\TribeXR.uproject" -run=cook -targetplatform=Android_ASTC -unversioned \
       -map=/Game/Mods/Festival/Maps/Environment_Festival+/Game/Mods/Dino/Maps/Environment_Dino -unattended -nosplash -nullrhi -abslog=<log>
   cd "$P" && bash Scripts/pack_chunk.sh 50          # -> Saved/ModPak/pakchunk50-Android_ASTC_P.pak
   python $P/Scripts/make_obb.py <out.obb> <every current pak ...>
   ```
   - Delete `Saved/Cooked/Android_ASTC/TribeXR/Content/Mods` and `.../Metadata/ChunkManifest` before cooking.
   - The `-map=` list must include **every** custom map, or the cook drops the others.
   - Check the cook says `Success - 0 error(s)`.
   - Read `Metadata/ChunkManifest/pakchunkNN.txt` to see what went into each chunk.
4. **Push.** Push the OBB to `.../patch.new.tmp`, `mv` it over the patch OBB, then compare md5s.
   - Files for the mod's folder `/sdcard/Android/data/com.TribeXR.TribeXR/files/tribemod/` **must be staged**: push to
     `/data/local/tmp/x.tmp`, then `cp` and `chmod 666`. A plain `adb push` into `Android/data` silently vanishes on this
     headset.
   - `scripts/reseed.sh` has a `put()` helper that does this.
   - adb is `tools\platform-tools\adb.exe`; the Quest's serial is `2G0YC1ZF96072F`.
5. A typical stage build (build + cook + pack) takes about 5 minutes. A full Blender bake of the Dino Stage takes about
   20 minutes, under the GPU lock.

### 3.3 The mod (`hook/dumper.cpp`, built into `out/hookA/songN.aligned.apk`)
A native library injected into Tribe. It hooks `ProcessEvent` and resolves UE objects through reflection: `find_by_path`,
`prop_offset`, `call_uf`, `read_fstring`, a poll thread plus the game-thread tick. The current build is **song8**. Build it:
```
out/android-ndk-r26d/toolchains/llvm/prebuilt/windows-x86_64/bin/aarch64-linux-android32-clang++.cmd -shared -fPIC -O2 \
  -fvisibility=hidden -nostdlib++ -Wl,--no-undefined -Wall -Wformat=2 -o out/hookA/libhook_X.so hook/dumper.cpp \
  hook/vendor/And64InlineHook.cpp -llog -lm
cp out/hookA/menu.apk out/hookA/X.apk && cp out/hookA/libhook_X.so out/hookA/stage/lib/arm64-v8a/libhook.so && \
  (cd out/hookA/stage && "/c/Program Files/7-Zip/7z.exe" a -tzip ../X.apk lib/arm64-v8a/libhook.so)
bash scripts/sign_apk.sh out/hookA/X.apk out/hookA/X.aligned.apk
```
Write patches as Python scripts in the scratchpad (exact-match `str.replace` with `assert count == 1`). Shell heredocs
break on quotes and backslashes.

What the mod does:
- **Custom avatar** (glTFRuntime, `custom.glb`, skins menu).
- **Custom environments menu.** `tribemod/envs.txt` holds lines `Name=/Game/Mods/X/Maps/Environment_X`. The boxes copy the
  identity of Tribe's "The Void" list item. Levels load through `LoadLevelInstanceBySoftObjectPtr`; the by-name loader
  checks the asset registry and fails.
- **Visuals on our screen.** The mod registers our screen as `BackdropMesh` through
  `BP_TribeVisualsManager_C.SetupEnvironmentBackdrop`.
  - It finds the screen by the **static mesh name `SM_DinoVisualScreen`**. A new venue must use that mesh name, or extend
    the hook to accept more names.
  - The screen's UV0 copies Tribe's back-wall layout: the material samples (1−U, 2V−1).
  - The mod forces `MPC_VideoBackdrop` to fill mode: StretchMode z > 0.5.
- **Giant intro.** A lift with a button, a robe, a crowd camera, a blackout and a follow spot. It's driven by the MPC at
  `/Game/Mods/Dino/MaterialInstances/MPC_DinoGiant.MPC_DinoGiant`, whose path is hard-coded in the hook. Its parameters:
  Height, RobeTop*, RobeOn, ButtonGlow, ShowLevel, ShowOffset, SpotOn, TopLasers.
  - **To reuse the show logic in the club, generalise the hook's MPC lookup to the active environment's path.**
- **Drone camera.** A scripted camera reel for the stream (`drone.txt`, `drone_path.txt`).
- **Song mode.**
  - Every track in my library has a light script, `tribemod/songs/<key>.txt`.
    - key = FNV-1a 64 of the track's file name as the hook reads it: non-ASCII → `?`, ASCII lower-cased.
    - Format: `match=`, `bpm=`, `lift=`, `cues=t:look ...`. Looks: dark, top, intro, build, drop, breakdown, outro, show.
  - The deck's playhead drives the show: `BP_Deck_C.GetPlaybackSeconds`, `GetIsPlaying`, the `CurrentTrackFileName`
    property.
- **Lights follow the deck the crowd hears.**
  - Heard level = channel fader × filter openness.
  - Faders: `BP_ChannelVolumeSlider_C`, `BP_SliderBase_C.CurrentSliderOffset`, −2.2 bottom .. +2.2 top, with a
    `Mixer Channel` variable.
  - Filters: `BP_ChannelColorKnob_C`, `BP_KnobBase_C.CurrentKnobRotationYaw`, 0 = centre.
  - Deck channel: `BP_MixerChannelDevice_C.MixerChannel`.
  - Optional `tribemod/mix.txt` with `fader_sign=-1`.
- **Beat-grid lock (song8, just installed; verify it).** The lights' bar and beat clock follows the playing deck's
  **Tribe beat grid**, `BP_Deck_C.BeatgridBpm` / `BeatgridStartMs` (doubles). Beat 1 of a bar comes from the song's first
  drop.
- The mixer is a **DJM Nexus 2 (`BP_DJM_Nexus_2_C`)** with 4× CDJ-3000 (`BP_CDJ3000_C`, subclasses of `BP_Deck_C`).
- **Mixer probe**, read-only: touch `tribemod/probe_on` and it logs every numeric BP variable of the decks, mixer, sliders
  and knobs. Remove the flag afterwards.

### 3.4 The Meta login token (important for multiplayer testing)
- The modded app **cannot refresh Meta's login**: `graph.oculus.com/authenticate_application` returns 400, "Application
  does not have permission for this action" or "Unofficial Application".
- It **rides a token** minted by a genuine Tribe login. When the token expires, Go Live, lounges and multiplayer stop.
- **The fix is the re-seed:** `scripts/reseed.sh`, about 10 minutes, and it needs my explicit OK for its uninstalls.
  1. Uninstall the mod and install genuine `pulled/base.apk` plus the main OBB. I launch Tribe, tap OPEN APP, and log in
     fully.
  2. Uninstall the genuine app and install the mod again. The script then restores the OBBs, avatar, skins, env files,
     `song.txt`, `giant.txt` and all the song scripts.
- Backups: `backup/reseed_20261001`, `backup/tribemod_20261006`, `backup/tribemod_20261007_full`.
- Data points:
  - A token lasted 3-4 days once.
  - On 2026-10-07 one survived five `install -r` builds, then died right after the headset rebooted (battery died) plus
    another install.
  - The last re-seed was 2026-10-07 18:13.
- Each new install shows Meta's unofficial-app dialog on first launch, and **OPEN APP restarts Tribe once**
  (logged as EXIT_SELF). That is normal.

### 3.5 Multiplayer reality
- Tribe's multiplayer syncs **positions, voice, which environment is picked and your avatar's ID**. **Each headset renders
  from its own installed files.**
- So **other players can't see our custom venue or custom character**. I tested it: they saw stock Tribe.
- The avatar comes from **Ready Player Me** by ID for everyone. We can't change what other headsets load.
- **Untested idea for sharing a venue without a mod:**
  - Package it to **replace one of Tribe's stock environment slots**. Level paths are hard-wired per built-in environment
    enum, `/Game/Maps/Environments/<Name>`.
  - Friends copy one patch OBB file and run genuine Tribe.
  - Mod-driven extras (song sync, fader-following, the giant lift) would stay local to me.
  - Needs a test: does a stock-slot override load in genuine Tribe, and does Tribe keep everyone in the same environment?
- **For the real goal (everyone can join, with host-controlled stage access), Tribe's devs must ship it.** That's the
  pitch. Tribe's 2026 updates added **Rooms and Video Calls, a Privacy Bubble and moderation tools**, so they already have
  room hosts and moderation; a stage-access role fits that.
- Alternative: VRChat. It has worlds, custom avatars, built-in movement and AudioLink for audio-reactive lights.
  - Instance owners/masters and Udon scripting make a host-controlled gate easy.
  - I'd keep DJing in Tribe and stream into a video player in the world (Twitch or RTMP bridge).
  - Keep this as a fallback, or a parallel prototype if the pitch stalls.

---

## 4. What to reuse from the Dino Stage (look, systems, lessons)

- **The light show is a cue table.**
  - `show.py` writes `T_DinoCues.png`, a 32-bar × 16-row linear texture. R = level, G = strobe flag (comfort: disabled),
    B = beat-pulse flag.
  - Rows: stage 0, wash 1, sky 2, fan 3, horn6..3 4-7, infra 8, stage2 9, lenses 10, always 13.
  - Rows 11, 12 and 14 hold the **laser pattern weights**: sweep, circle, fan, crossfire, figure-8, hold, bounce, plus a
    chase amount. They crossfade over the last 15% of a bar.
  - The 32-bar show at 140 BPM: intro 0-7, build 8-14, blackout 15, drop 16-23, breakdown 24-27, outro 28-31.
  - Materials read it through `cue_level` in `dino_materials.py`, on the clock Time + ShowOffset.
- **Lasers** are geometry planes moved in the material through World Position Offset. Per-vertex data:
  - UV1/UV2: pivot and phase;
  - UV3: pan/tilt amplitude;
  - UV4.x: cue group (0 = stage fan, 1-4 = horn pairs).
  - Lasers must never end in the air awkwardly or clip props; `atmosphere_lasercheck.py` ray-checks this.
- **Visuals screen** carries the `SM_DinoVisualScreen` name for the backdrop hook, with UVs in Tribe's back-wall layout.
  The VJ loops are composed for the arch window (§5.6).
- **Night look:** everything is unlit with baked textures. The set is lit only by the show's wash row between hits.
  Additive glows, haze sprites and beams.
- **Performance:**
  - The Dino Stage runs at **~72 fps** on Quest 3 with a 4,400-dancer VAT crowd.
  - It drops to **~58 fps while streaming**, because Go Live renders the stage a second time.
  - A medium indoor club should be lighter. Real people are the crowd, so the VAT crowd is optional decoration.
  - Budget for Quest 2 too if Tribe's devs ask.
- **Lessons that cost time:**
  - The UE object count was once stuck at 16384 because of an early resolve: fixed, read `[R2]`.
  - A deck's playhead can repeat a value for a frame: smooth it.
  - Blender's UV packer is not deterministic for every mesh.
  - Cue times must sit on real hits (measured), not on a guessed grid.
  - Every mod or stage install closes Tribe.

---

## 5. Existing tools and data (paths)

1. **Repo:** `C:\Users\Chris\OneDrive\Desktop\tribe hack`
   - `NOTES.md` (long engineering log; "Session 3v" covers the Dino Stage)
   - `hook\dumper.cpp`, `scripts\reseed.sh`, `scripts\sign_apk.sh`
   - `claudedocs\` (Halloween plan, concept renders)
   - `tools\platform-tools\adb.exe`, `out\hookA\`, `pulled\`, `backup\`, `skins\` (lampwing.glb, skullbuck.glb)
2. **Stage generators and builders:** `C:\Users\Chris\TribeUE\TribeXR\Scripts` (§3.2).
3. **Fork project:** `C:\Users\Chris\TribeUE\Meta\TribeXR`
   - `Scripts\pack_chunk.sh`, `Scripts\make_obb.py`
   - `Saved\ModPak\` holds the paks and OBBs; the current live OBB is `patch_v82.obb`, built from chunk 50 + 53
4. **Song analysis:** `C:\Users\Chris\TribeUE\TribeXR\Scripts\songs\scan_library.py` and `make_cues.py`, with data in
   `C:\Users\Chris\TribeUE\Songs` (`features\`, `cues\`, `overrides\`, `index.jsonl`).
   - The scan pulls each song from the headset's `/sdcard/Music`, measures it and deletes the copy.
   - Re-running it scans only new songs.
5. **Light scripts on the headset:** `tribemod/songs/`. `reseed.sh` restores them.
6. **VJ pipeline:** `C:\Users\Chris\TribeUE\Visuals`
   - `CONCEPTS.md`
   - `scripts\vjkit.py` (140 BPM half-time accent clock), `make_loop.sh`, `check_loop.py` (gates), `assemble_set.py`,
     `arch_window.py`
   - `deliver\`: 28 loops at 140 plus a 60-minute Full Set, already on the headset in `/sdcard/Movies/Dino Visuals/`
   - Gate rules:
     - every ~1 m² block ≤ 0.65 luma, no frame over 0.5 mean;
     - ≤ 3 flashes/s, no one-frame hits;
     - on-beat frames ≤ ~1.6× mid-beat;
     - the loop seam ≥ 45 dB.
   - Rendering: Standard view transform, not AgX; key art inside the screen window.
7. **Memory:** `C:\Users\Chris\.claude\projects\C--Users-Chris-OneDrive-Desktop-tribe-hack\memory\`. `MEMORY.md` loads
   automatically. Relevant files:
   - `custom-environment-unreal.md`, `modded-build-login-recovery.md`, `dino-vj-loops.md`
   - `user-plays-heavy-dubstep.md`, `keywall-means-visuals-back-wall.md`, `stream-bridge-vrchat-myx.md`
   - `halloween-stage-plan.md`, `props-via-gltfruntime.md`
8. **A planning template:** `claudedocs/halloween_stage_plan.md` and `claudedocs/halloween_concept/`, whose blockout is
   `Scripts\Blender\halloween\concept_blockout.py`. That's how a second venue was planned. Copy its approach, not its
   files.

---

## 6. Design problems to solve (think these through with me)

1. **The room.**
   - Size: a medium indoor club. Suggest a capacity, for example 60-150 people in VR terms, and dimensions.
   - Layout: stage, dance floor, bar/lounge, entrance, raised side areas.
   - Ceiling height for lasers. A theme and name that fit heavy dubstep.
   - A dark palette, with the visuals screen as the focal point.
   - Haze that reads indoors; lasers that hit walls and ceiling properly. Indoors, beams end on surfaces, so the laser
     length and stop rules from `atmosphere_lasercheck.py` need an indoor version.
2. **Stage, gate and roles.**
   - Places to define: a physical gate or barrier at the stage access (stairs or ramp), with a visible state: open (green)
     for host and DJ, closed or red for everyone else.
   - The behaviour spec for the pitch:
     - The host grants or revokes the DJ role.
     - Only the host and the DJs can pass the gate.
     - Audience members who walk into the gate are stopped (collision) or gently pushed back, plus a message such as
       "Stage access: DJ only".
     - Also plan for what happens if someone teleports in.
   - What we can prototype ourselves: locally, the mod can make the gate stop *me* and show the UI, but it can't enforce
     anything on other players' headsets. The real enforcement belongs to Tribe's server and room logic. **Write a clear
     spec for Tribe's devs** and mock it in the prototype.
   - Investigate what Tribe exposes about rooms, hosts and roles with the mod's reflection tools. Look at
     TribeGameInstanceBP_C, the game state and player states. The 2026 Rooms features suggest host and moderator data.
3. **Moving around.**
   - Thumbstick locomotion: left stick walks where you look, right stick snap-turns, with comfort options (speed,
     optional vignette).
   - How it can work in Tribe: the giant lift already moves the play space every frame (`K2_SetRelativeLocation` on
     `TribePawnBP_C.VROrigin`, `giant_set_rel`), and the avatar's feet follow.
   - Floor height must follow the room (stage, stairs, floor), from a heightfield we export from Blender. Walls and the
     gate need simple collision volumes we check ourselves, since the set is NoCollision.
   - Find out whether Tribe already binds the thumbsticks. A toggle such as clicking a stick may be needed.
   - Add a one-press "back to the decks" for the DJ.
   - Test whether other players see you move (positions are synced, so they probably do).
4. **Lights and lasers.**
   - Reuse the cue-table show with laser patterns, song mode, fader-following and beat-grid lock.
   - Generalise the hook's hard-coded Dino MPC path so the club's materials can share the same mod logic.
   - Indoor fixtures: moving heads on trusses, ceiling laser bars, LED strips, a DJ booth with a lit front.
5. **Visuals.**
   - One big screen behind the DJ (the keywall) carrying the `SM_DinoVisualScreen` name, or extend the hook.
   - Possibly side screens or LED tiles that mirror the main video (Tribe only feeds one backdrop; check whether a material
     can reuse its render target).
   - The VJ team's pipeline can make club-themed loops later.
6. **The pitch package (at the end).**
   - A 1-2 minute highlight video from the stream.
   - A one-pager: what it is, what Tribe would need to add (roles, gate, locomotion), performance numbers on Quest 3 and
     ideally Quest 2.
   - A clean asset bundle: Blender sources, FBX, textures and the UE import script. Everything we use must be **original**
     (procedurally generated by our scripts) so ownership is clear.
   - An honest note that I built a preview mod.
   - Contact routes: Tribe XR's Discord and their **Resident DJ program** (needs full 1-hour sets, community activity,
     promoting Tribe).

---

## 7. How to work

- **Plan first.** Ask me the open questions (theme/name, size, look, roles, platform priority). Then make **concept
  blockout renders** (a Blender script, a few views plus a contact sheet), the way the Halloween plan did. Build only after
  I approve.
- **Separate everything:**
  - generator `C:\Users\Chris\TribeUE\TribeXR\Scripts\Blender\club\`
  - build script `build_club.py`, materials `club_materials.py`
  - content `/Game/Mods/Club/` (map `Environment_Club`), its own chunk (55)
  - notes in `claudedocs/club_venue_notes.md`
  - Import shared helpers instead of editing the Dino files.
- **Coexistence:**
  - Add the club to `tribemod/envs.txt` as `Club=/Game/Mods/Club/Maps/Environment_Club` (pick the real name).
  - Add it to `backup/tribemod_20261006/envs.txt` too, so the re-seed restores it.
  - Every patch OBB push includes chunks 50, 53 and 55, plus 54 if Halloween has shipped. Consider creating the
    `C:\Users\Chris\TribeUE\paks_current\` convention from the Halloween plan: every current pak in one folder, and one
    script that zips that folder.
  - Add the club's map to the cook's `-map=` list along with the others.
- **Verify on the device.** Use logcat with the `TRIBEMOD` tag; my session captured it to a file with `adb logcat -v time
  -T 1 TRIBEMOD:V ActivityManager:I DEBUG:V libc:F AndroidRuntime:E AuthLogger:V LoggingErrorHandler:V MakeEvoRequest:V
  '*:S'`.
  - Check frame rate (the mod logs `[PERF]`), crashes (`dumpsys activity exit-info com.TribeXR.TribeXR`) and login errors
    (grep `authenticate_application`).
  - Watch the battery: the Quest drains faster than it charges while Tribe runs.
- **Communicate:** the answer first, then the reasoning, then the risk. Mark what's verified and what's assumed. No
  marketing language. If something will close Tribe or needs the re-seed, ask first.

---

## 8. First steps for you

1. Read `MEMORY.md` (auto-loaded), then skim `NOTES.md` "Session 3v" and `claudedocs/halloween_stage_plan.md` (sections 1-3
   and 10) to see how a venue gets planned and built here.
2. Ask me 5-8 sharp questions:
   - name and theme;
   - size and capacity;
   - stage layout and where the gate goes;
   - look references;
   - platform priority: Tribe pitch first, a VRChat prototype in parallel, or both;
   - how the host should grant the DJ role in the experience;
   - must-have vs nice-to-have.
3. Then propose the plan: phases, what we can prototype in Tribe today versus what's spec-for-Tribe-devs, the risks
   (multiplayer visibility, collision, locomotion conflicts) and a first concept-render task.
