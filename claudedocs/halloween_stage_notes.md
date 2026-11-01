# Halloween stage (GRAVEYARD SHIFT): running notes

The running log for the Halloween stage. The plan is `claudedocs/halloween_stage_plan.md`; the concept renders are in
`claudedocs/halloween_concept/`. NOTES.md belongs to the Dino session, so Halloween work is logged here.

## 2026-10-08: phase 0 started (the user: "go ahead and start")

**State of the other sessions when this started** (read, not changed):
- Dino session: patch_v82.obb (chunks 50 + 53), mod song9.aligned.apk, a v9 lasers bake under the GPU lock from
  18:05:49. It owns hook/dumper.cpp, NOTES.md, scripts/reseed.sh and the Dino scripts.
- Club session (REACTOR, `claudedocs/club_venue_plan.md`): chunk 55, its project copy D:\TribeUE\MetaClub, v1 pushed
  17:52 as a merged OBB (50 + 53 + 55) and tested 17:55-17:58 (71-72 fps); its envs.txt line is box 4.
- GPU lock convention (from NOTES.md, 2026-10-06): `mkdir C:\Users\Chris\TribeUE\gpu.lock.d` with owner.txt inside;
  release by removing it. Every session follows it. It worked twice today: this session's first test bake waited for the
  club's REACTOR v2 bake, and the full bake below waited for the Dino session's v9 bake.

**New files (nothing shared was edited):**
- `D:\TribeUE\MetaHw\TribeXR`: the Halloween fork-project copy, made like MetaClub (uproject, Config, Build, Plugins
  with the glTFRuntime stubs + ModMaterialTools, Binaries/Win64/UnrealEditor.target, Scripts/pack_chunk.sh +
  make_obb.py), copied from Meta\TribeXR. Config and uproject are identical to MetaClub's. 10 MB before the first cook.
  On D: because C: is at 96% (43 GB free).
- `D:\TribeUE\MetaHw\TribeXR\Scripts\cook_halloween.sh [build|cook|pack|all]`: the club's cook_club.sh with Halloween
  names; logs in D:\TribeUE\MetaHw\logs.
- `TribeUE\TribeXR\Scripts\Blender\halloween\hw_stage.py`: the generator, v0. The approved concept's set (cathedral,
  portal, clock, gargoyles, two giant dead oaks, deck, Dino's riser + stairs + booth table dimensions, iron fence
  barrier, portal truss, 22 moving-head bodies with lens glows, hanging and post lanterns, candles), lighting baked in
  Cycles as dino_stage.py does, the Dino v7.1 screen geometry and Tribe UV layout, a procedural storm sky and blood moon.
  Helpers copied from dino_stage.py (it runs at import).
  - It models in the FINAL frame: the deck top at -1 m, the riser top = Tribe's floor (0), the crowd field at -2.5 m
    (Dino's post-drop numbers); no drop step. The concept had the field at -1.5; it moved down 1 m to match Dino.
  - Fixed from the concept: the riser gargoyles floated 1 m above the deck (now on the riser top, on pedestals); the
    nave "floor" slab sat at mid-wall height (removed; the ruined nave walls now have broken tops); balcony heads hovered
    0.3 m above their balconies.
- `.../halloween/run_hw_stage.sh [--fast]`: hw_stage.py under the GPU lock; log in out_hw/bake.log.
- `TribeUE\TribeXR\Scripts\build_halloween.py`: the UE import (modeled on build_club.py / build_dino.py): unlit MICs of
  Tribe's glTFRuntime parents, NoCollision on every actor, PAL_Halloween -> chunk 54, two deck lamps HwDeckLamp_L/R,
  level /Game/Mods/Halloween/Maps/Environment_Halloween. HW_SRC picks the Blender output.
- `tribe hack\scripts\push_obb.sh [--push] [--env "Label=/Game/..."] <pak>...`: the shared merge push (below).

**Fast pipeline test (scratchpad hw_fast, 1/8-size bakes):** generator 11 s; UE build ok; cook "Success - 0 error(s),
3 warning(s)" (the same engine cvar notes the club saw) in 21 s with the warm shader cache; chunk 54 manifest 23 entries,
all under /Game/Mods/Halloween (map, 9 MIs, 8 meshes, 6 textures; no stubs, no engine content, no shader archive);
pak 3.1 MB, 51 files. Import check: screen centre y = -1030 cm -> level yaw 180 (screen ends at +10.3 m, as Dino);
the moon lands at x +30 m, i.e. over the left tower from the crowd's view, as designed. 8 actors + 2 lamps.

**Exposure calibration:** the fast bake of the stone came out at mean linear 0.006; Dino v7.1's bone structure bakes at
0.089 with exposure 1.6 x NIGHT. The stone is dark by design, and Tribe shows no bloom (MobileHDR off), so the full
bake uses exposure 7.0 (facade), 6.0 (deck, ground), x NIGHT 0.5.

**push_obb.sh** (the club session drafted the same idea as push_obb_merge.sh in its scratchpad):
- pulls the live patch OBB from the headset, keeps every pak in it, adds or replaces only the ones given, and builds
  the merged OBB the way make_obb.py does (stored zip, TribeXR/Content/Paks/<pak>, comment "      2304");
- `--push` refuses while Tribe runs, and refuses if the live OBB changed since the pull (compare-and-swap), then pushes
  to patch.new.tmp, mv's it over the live file, and compares md5s;
- after a verified push it mirrors the live state to `C:\Users\Chris\TribeUE\paks_current\` (patch_live.obb, paks/,
  paks.txt), which is what scripts/reseed.sh's PATCH= could point at so a re-seed restores every stage;
- `--env` adds a menu line to tribemod/envs.txt on the headset, and refuses a 5th line (the mod's limit, below).
- Dry run at ~18:12: the live OBB (249,229,340 B, md5 ce69696d...) held 50 + 53 + 55 (the club's v1, pushed 17:52);
  merged with the fast pak 54 it kept all three and added 54 (md5 8fece041..., not pushed). A plain make_obb push of
  only 50 + 53 + 54 would have deleted the club's stage.

**Blockers found (need the user or the Dino session):**
1. **The menu is full.** envs.txt on the headset: Festival, Dino Stage, Dino Classic, Reactor. The mod shows at most
   4 boxes: `#define EM_MAX 4` in hook/dumper.cpp (used only to size the label/path/item arrays and loop bounds), so a
   5th line is silently ignored. Options: the Dino session raises EM_MAX to 8 in its next mod build (one line), or the
   user picks a box to drop for now (Festival is the oldest test stage).
2. **Tribe was running** on the headset (pid 17851), so no push is possible until the user closes it. The club's v2
   push is waiting for the same thing.
3. **The Dino session's next push** will drop chunk 55 (and 54) if it builds its OBB from its own paks only. The club
   session asked the user to pass that on; push_obb.sh is the fix.
4. **Dino-only mod features are gated on "a custom stage is active", not on which one** (read in dumper.cpp):
   giant_lookup runs when g_emState == EM_ACTIVE and finds /Game/Mods/Dino/.../MPC_DinoGiant by path; giant_tick then
   watches the button point (0, 152, 106) cm and drives the lift for song scripts with lift= (PRELUDE I). [assumed] Once
   the Dino Stage has been visited, the MPC stays loaded (a world keeps a parameter-collection instance per used
   collection), so on Graveyard Shift or Reactor a hand near that point, or PRELUDE I, would raise the DJ 5.45 m with no
   platform. Check on the headset: visit Dino, switch to another custom stage, play PRELUDE I, watch for [GIANT] lines.
   Fix (Dino session): gate giant_lookup on the active box's path containing "/Mods/Dino/".

### v0 full bake + build (2026-10-08 18:23-18:30)
- **Bake** (out_hw): queued behind the Dino session's v9 bake; took the GPU lock at 18:23:02 when that one finished;
  269 s; lock released by the runner.
  - SM_HwFacade 4096 px, 64 spp, 74 s: mean linear 0.0049 (output mean 0.013 over the whole texture; the facade UVs
    cover 47.7%, so about 0.027 over the stone).
  - SM_HwDeck 2048 px, 96 spp, 26 s: mean linear 0.0076 (output 0.018).
  - SM_HwGround 4096 px, 128 spp, smooth 4, 154 s: mean linear 0.0011 (output 0.003).
  - 8 meshes, 20,278 tris in all (facade 4,634; deck 2,792; glow 8,832; sky 3,968).
- **Previews** (out_hw/preview_*.png, EEVEE, Standard, no bloom = what the Quest shows): facade, crowd eye height,
  stream, dj_back, dj_front, aerial. Contact sheet + JPEGs in `claudedocs/halloween_v0/`.
  - Lesson: a factory-startup Blender saves JPEGs through the AgX view transform, which dulls them; the sheet script sets
    Standard. (The 2026-10-06 concept sheet went through AgX too, so it reads slightly duller than its PNGs.)
  - Phase-1 note: stars only show where the cloud band is thin, so from the decks they cluster in one patch.
- **UE**: build ok in 25 s (textures 4096/4096/2048/4096x2048/1024 + the palette); cook "Success - 0 error(s),
  3 warning(s)" in 48 s; chunk 54 manifest 23 entries; `pakchunk54-Android_ASTC_P.pak` 30,703,020 B, 51 files.
- **Merge dry run** (18:31): live OBB unchanged (md5 ce69696d..., 50 + 53 + 55); merged with the v0 pak 54:
  279,932,536 B, md5 3527ae4d4d7a45bde6cf61a78115c50d. Not pushed: Tribe still running (pid 17851) and the menu still
  full (4 boxes).
- **To ship** once Tribe is closed and a menu slot exists:
  `bash scripts/push_obb.sh --push --env "Graveyard Shift=/Game/Mods/Halloween/Maps/Environment_Halloween" /d/TribeUE/MetaHw/TribeXR/Saved/ModPak/pakchunk54-Android_ASTC_P.pak`

### First push + device test (2026-10-08 18:33-18:53; log: scratchpad logcat_hw_v0.txt, the club prompt's filter)
- The user chose "Festival" as the box to give up, and closed Tribe. Backup of the headset's envs.txt before the change:
  `C:\Users\Chris\TribeUE\paks_current\envs_before_halloween_20261008.txt`. The Festival line was removed (its level
  stays in chunk 50; one line brings the box back).
- `push_obb.sh --push --env "Graveyard Shift=..."` at 18:33:36: the live OBB had changed since the 18:31 dry run (the
  club pushed its v2 pak 55 in between, md5 5de618df...); the script pulled that one, kept 50 + 53 + 55 v2, added 54:
  279,916,664 B, md5 20893f1efc2a67accaf377218f4d5d4e, verified on the headset. envs.txt now: Dino Stage, Dino Classic,
  Reactor, Graveyard Shift. paks_current/ mirrors it.
- Launch 18:51 (pid 21899): all 4 boxes read; every box was added before Tribe's Void item existed ("WITHOUT the Void's
  identity: not found"), then got the identity at 18:52:18.6 when the Void item appeared. Transient, as designed.
- **Mod race (Dino session's code):** the user clicked Graveyard Shift at 18:52:19.80; the once-per-launch restore of
  the saved stage ("auto: re-applying 'Reactor'", the club's last test) fired at 18:52:20.11 and loaded Reactor over
  the click. Fix idea: skip the auto re-apply when a click is pending (g_emReq >= 0) or arrived after launch.
- The merged OBB serves the other stages: Reactor IN at 18:52:23 and 18:52:31, Dino Stage IN at 18:52:38 and 18:52:59,
  Dino Classic IN at 18:52:51, each "visible after 1 s". Dino Stage steady 70-71 fps after its load window.
- **Graveyard Shift on the headset (18:55:58 click):** LoadLevelInstanceBySoftObjectPtr success=1 at 18:56:00.6;
  "'Graveyard Shift' is IN (visible after 1 s)" at 18:56:01.5; "our screen ... is Tribe's backdrop now ...
  material=MI_HwVisualScreen" at 18:56:02.4 (the SM_DinoVisualScreen mesh-name stopgap works with no mod change);
  HwDeckLamp_L/R found (3 cd).
  - [PERF] in Graveyard Shift: 66.5 fps (load window, one 400 ms frame, as every stage's load window), 69.7, then
    71.8 / 71.8 fps with 1 frame over 20 ms per 10 s (worst 22.7 ms). Dino Stage in the same session: 70-71 fps,
    9-11 frames over 20 ms.
- **Phase 0 gate:** load <= 2 s PASS (1 s); 71+ fps PASS (71.8); Dino/Dino Classic/Reactor still load from the merged
  OBB PASS; screen registered PASS (video on it: the user's check); pointer: the user's check.
- **Lift risk REFUTED on device:** "[GIANT] ready" on the Dino Stage at 18:52:42; after switching to Dino Classic,
  "[GIANT] MPC_DinoGiant not loaded" at 18:52:53, so Tribe frees the Dino MPC when the Dino level streams out; no
  "[GIANT] ready" on Reactor (18:55:52) or Graveyard Shift (18:56:01). The lift and song-lift do not arm on other
  stages. (The earlier "assumed" note above was wrong.)
- **Tribe exit at 18:56:51** (50 s into Graveyard Shift): `dumpsys activity exit-info` reason=1 EXIT_SELF, status 0
  (same record as the user's own quit at 18:31:53 for the push); the log shows "environment list went away" and "body
  gone" just before, i.e. an orderly shutdown. Not a crash, ANR or low-memory kill. The last [PERF] window before it:
  71.2 fps, 15 frames over 20 ms (worst 24.9 ms).
- Not verified yet: no video was played on Graveyard Shift (the screen stayed MI_HwVisualScreen, Tribe's visuals off)
  and no menu click was made while on it (pointer). Both are the user's next check.

## 2026-10-08 evening: phase 1 (the set), v1

The user, after the v0 device test: "go ahead its fine" (taken as: v0 is fine, start phase 1; the video-on-wall and
pointer checks were not seen in a log).

**hw_stage.py v1** (v0 kept as hw_stage.v0.bak.py, its output as out_hw_v0/):
- Towers: front buttresses with 3 setbacks and sloped caps; framed twin-light windows (two pointed lights + a roundel,
  stone jambs, sill, mullion, pointed hood) on the front, inner and outer faces, 3 tiers; a glowing blood-red rose
  window with stone tracery under each parapet; crockets on the whole spire; rubble on the snapped one; moss on the
  lower stones (mat_lit moss=(z0, z1)).
- Gable: parapet blocks on both rakes, a broken cross at the peak; stepped pilasters between portal and towers;
  capitals and bases on the portal shafts.
- Gargoyles: crouching, open jaws, horns, wings, red eyes; the 4 front ones are the laser apertures.
- Rig (SM_HwRig, 1024 bake): 26 moving heads (Dino's fixture shape): 16 on the tower balconies, 6 on the portal truss,
  4 deck uplights on the facade; 4 searchlights (2 drums each); the portal laser housing. The truss moved to y 9.8, in
  front of the screen, and its 7 lanterns now hang above the picture (bottom 13.2 m > screen top 12.67 m); in v0 they
  hung 0.2 m BEHIND the screen.
- Frozen translucent show (alpha-blended, own T_HwBeam / T_HwHalo in the Halloween colors): SM_HwBeams (26 head beams),
  SM_HwHalos (lens, searchlight and cauldron glows), SM_HwLasers (4 gargoyle fans x 9 + a 13-line portal fan = 49 lines,
  landing at crowd head height), SM_HwSearch (8 sky beams, 320 m). Hidden from the bakes.
- DJ area: a frieze of 12 skulls with dim red eyes on the riser front; a coffin-shaped panel with a glowing cross on the
  booth front; 2 candelabras; a cauldron with a green brew glow and halo (back left); a raven on the left gargoyle;
  skull piles on the deck.
- Sky: stars everywhere, dimmed (not cut) under clouds (v0's stars clustered in one cloud gap).
- Facade split (v1a): SM_HwFacade (big surfaces, 4096) + SM_HwFacadeDetail (frames, tracery, crenellations,
  gargoyles, oaks, ...: 2048). The single 4096 atlas had dropped to 25.4% UV coverage with all the small parts; split:
  62.5% for the walls (2.5x the texel density) and 17.1% for the details (about 3 cm per pixel).
- Laser clearance check (BVH ray casts + closest pass to the DJ's head at (0, 0.9, 1.7)): first run 2 lines of the
  left outer gargoyle fan hit the left oak's crown (x -30.8 / -27.9 at z 27-29); v1a aimed the outer fans inward
  (1 hit left); v1b moved both oaks from x +-36 to +-39 and landed the outer fans at (+-15, -34) over 32 degrees:
  0 hits of 49 lines, closest pass to the DJ's head 17.0 m (rule >= 4.9 m).
- Rose windows' bake light 900 -> 250 W: it washed the tower tops red in the first preview.
- Fast run: 32,790 tris in all (facade 2,890 + detail 7,324, deck 5,464, rig 2,892, glow 9,688, sky 3,968, beams 104,
  halos 180, lasers 196, sky beams 32).
- build_halloween.py: SURFACES for SM_HwFacadeDetail, SM_HwRig and the 4 translucent meshes (parent
  /glTFRuntime/M_Unlit_glTFRuntimeTwoSidedTranslucent_Inst, whose stub is in MetaHw's Plugins/glTFRuntime).
- Shell lesson: an apostrophe inside a python heredoc broke the Bash tool's quoting ("unexpected EOF while looking for
  matching"); patch scripts now go to a file first.
- **v1 full bake** (329 s, GPU lock taken and released): facade 4096 in 100 s (mean linear 0.0055), detail 2048 in 13 s,
  deck 2048 in 27 s, rig 1024 in 5 s, ground 4096 in 167 s. 0 laser hits, closest pass to the DJ's head 17.0 m.
  Previews + contact sheet: `claudedocs/halloween_v1/` (facade, crowd, riser close-up, stream, dj_back, dj_front, aerial).
- **v1 UE**: build ok in 33 s (14 actors + 2 lamps; facade extent 5750 x 3540 x 4850 cm now that the oaks moved to the
  detail mesh); cook "Success - 0 error(s), 3 warning(s)" in 67 s; chunk 54 manifest 39 entries, all under
  /Content/Mods/Halloween/ (1 map, 14 MIs, 14 meshes, 10 textures; checked with scratchpad check_manifest.py);
  pakchunk54 35,699,635 B.
- **v1 push 20:16:20**: the live OBB (md5 12935c16...) held a NEW Dino pak 50 (126,471,709 B, md5 eb8d8c3a...) with
  Halloween v0 and Reactor v2 still in it, so the Dino session's latest push kept the other stages. Merged 50 + 53 +
  54 v1 + 55: 285,192,750 B, md5 b7b55ed30bec49cc9a94761759d1af73, verified on the headset. envs.txt unchanged (Graveyard
  Shift is box 4). Log capture: scratchpad logcat_hw_v1.txt.

## 2026-10-08 late: v2 (phases 2-5) in progress, paused at the usage limit

Done:
- hw_stage.py v2: giant hands, cue-lit windows, eyes and lenses, the clock face and hands, bats, ghosts, fog, flame
  jets, lightning bolts, 49 sweeping laser lines, the grounds-module loader and the costumed-crowd hook. The fast test
  passes: 27 meshes, 347k tris, 0 laser hits on the set at rest and at the sweep extremes, closest pass to the DJ head
  12.4 m.
- build_halloween.py v2: the stock build (default) plus HW_ANIM=1, the animated build on Scripts/hw_materials.py. The
  manifest check raises on unknown meshes. Bolts, fire, fog and ghosts ship only in the animated build.
- Animated test build on the FAST output (session scratchpad hw_fast_v2): 53 s, 20 materials, 24 of 27 meshes on our
  materials, World Position Offset on bats, clock hands, crowd, ghosts, hands, lasers and phones. Crowd VAT 2048x1024,
  28 frames per clip.
- Fork cook of that test build: Success, 0 errors, 5 warnings, chunk 54 manifest 75 entries, 70 s.
- hw_preview.py: the v2 meshes join the module previews once out_hw holds v2 output (v1 copy in the session scratchpad).
- Animated build: the grounds glow gets a soft flicker (M_HwGroundsFlicker, 15 percent, 2-4 Hz sines, no flashes).
- claudedocs/halloween_drone_path.txt: the Appendix A reel. It is NOT on the headset.

Not done:
- The five background agents (grounds a, b, c, crowd, visuals) were stopped at the usage limit. On disk:
  modules/hw_graveyard.py and modules/hw_vendors.py, crowd/hw_crowd.py (unfinished), and whatever is in
  Visuals/halloween/deliver. Check that every mp4 there plays to the end before pushing any.
- Not started: the full v2 bake into out_hw, the final animated build, cook and merge-push, the VJ loops push, the
  comfort check of the cue table on device, the clock rotation direction check.
- The headset still runs v1 (chunk 54, pushed 20:16:20, OBB md5 b7b55ed30bec49cc9a94761759d1af73).
- The MetaHw project now holds the animated FAST test build, not v1. The v1 pak is kept in paks_current/paks.
- Test pak: -rw-r--r-- 1 Chris 197121 44320033 Oct  8 20:59 /d/TribeUE/MetaHw/TribeXR/Saved/ModPak/pakchunk54-Android_ASTC_P.pak; shader-archive entries in the chunk 54 manifest: 1

## 2026-10-08 night: resumed after the usage limit (v2, phases 2-5)

- The five helpers resumed with their context (graveyard + infrastructure, vendors + forest, carnival + pumpkins +
  crypt, costumed crowd, VJ loops). No stale GPU lock and no orphaned Blender/ffmpeg processes were left by the stop.
- Fire material bug: `M_HwFire` failed to compile for SF_VULKAN_ES31_ANDROID ("Arithmetic between types float2 and
  float3"): UV0 x a float3 constant. Fixed by masking the constants to float2; recooked: no material failures. In game
  it would have shown Unreal's default material on the flame jets.
- Translucent overdraw (new tool hw_overdraw.py, the Dino method plus an occluded measure). From the DJ: 0.95 layers/px
  behind the opaque set (animated build), 1.69 counting every layer; budget 2.5. Stream camera 0.33.
- Two-module integration test (graveyard + vendors, fast): passes. Found and fixed: an empty module beam list exported
  a 0-face FBX (the Unreal import would have failed); the portal fan's outer lines at the sweep extremes hit the
  graveyard mausoleums (70 deg + 12 deg sweep ended 3.6 m past the crowd edge) -> 60 deg + 10 deg, 3.4 m inside it.
- Hinged module parts (CONTRACT.md "hinged"): the plan's coffin lids and the Pumpkin King's jaw. Modules return the
  part closed with a hinge (point, axis, opening, delay); hw_stage joins them into SM_HwHinged (5 UV channels: UVMap
  + hinge data), baked closed; hw_materials.hinge_swing turns each part with the hands row; the stock build shows them
  closed. Tested end to end with a coffin in hw_example.py: bake, FBX, Unreal import, compile, Android cook.
  hw-grounds-a (coffin lids) and hw-grounds-c (the jaw, delay 0.8) were told.
- Comfort check (new tool hw_cuecheck.py, plan 7.7): models every animated material frame by frame at 72 Hz from the
  shipped T_HwCues.png and T_HwSky.png, constants read from hw_materials.py. It found three rule breaks, all fixed in
  hw_materials.py (each rule: the user, 2026-10-06, "no one-frame hits"):
  1. every bar-line cue step was instant (the cathedral jumped 11% -> 91% in one frame at the drop): cue steps now ramp
     over 60 ms (4.3 frames);
  2. the beat pulse rose 0.6 -> 1.0 in one frame on every beat: it ramps over 60 ms too;
  3. a pulse switching off at a bar line spiked the lenses up for one frame: the pulse flag ramps with the level;
  plus the bolts reached full opacity in about 2 frames (the 1.6 gain moved from opacity to colour).
  Now PASS: busiest output 2 flashes/s (limit 3), quickest attack 3.9 frames (limit 3), pulse 1.43x (limit 1.6), sky
  at a full strike 14.5% display luma (limit 35%). Negative tests (instant steps, pulses, strikes) all FAIL as they
  should. Added from the plan (7.3): the set catches each lightning strike (+25% x the strike envelope).
- Clock hands: the turning direction is derived (a Blender clockwise turn maps to the Unreal rotation with SIGN -1, the
  laser_sweep mirror rule): clockwise for the audience. Still worth a glance in the headset.
- Drone reel check (new tool hw_dronecheck.py): samples each fly/orbit line against every opaque mesh. With the two
  modules, the graveyard pass starts inside a vendor unit: the draft reel predates the module layout (the carnival
  also sits on the other side from the draft's carousel shot). The reel gets re-aimed against the final modules.
- New: Scripts/Blender/halloween/ship_hw.sh [--fast] [--stock] [--skip-bake] [--push]: bake -> comfort check ->
  overdraw (DJ <= 2.5) -> drone report -> Unreal build/cook/pack (no material may fail) -> chunk-54 shader archive ->
  push_obb.sh dry run (or --push). Tested end to end on the fast path (two modules, no crowd): every gate ran, the
  dry run merged with the live OBB, which another session had changed since my v1 push (md5 f1394669..., its paks
  50/53/55 kept as they are).
- New: modules/hw_modlint.py (no GPU): budgets, tall geometry inside the crowd without an exclude rect, geometry
  over the set, and cells where two modules stand at the same height. First run (bounding boxes) over-counted;
  with true triangle coverage and height ranges: no collisions between modules; hw_infrastructure has 6 tall cells
  inside the crowd near (+-29, -57) without an exclude rect; hw_forest has trees inside the stage oaks' zone
  (|x| 29..49, y -4..16). Both owners told.
- New: scripts/push_media.sh "<Movies subfolder>" <files>: md5-verified copy to /sdcard/Movies/<subfolder>/.
- Drone reel re-aimed at the real modules (+ a pass behind THE CRYPT's crowd, 153 s); verify with hw_dronecheck.py.
- Lasers vs the crowd infrastructure (all seven modules, fast bake): 21 hits on the FOH mausoleum at (0, -31) and the
  speaker towers at (+-17, -42), every fan landing right where they stand. The clearance check also only sampled rest
  and the sweep extremes; it now samples 9 pan x 3 lift steps (27 poses: a line passing an obstacle between its
  extremes clips it mid-sweep), which raised the count to 36. Fixed on the laser side (the FOH roof is meant to sit at
  the DJ's eye height): every fan now lands IN FRONT of the FOH (inner (+-6, -25), outer (+-15, -22), portal
  (0, -26)), and the sweep's tilt only lifts (0..+amp; laser_sweep and the clearance poses both): a 5-degree dip had
  dropped a 58 m line's end ~5 m into the FOH and the field. Result: 0 hits in 49 lines x 27 poses; DJ head gap 11.2 m.
- Ground bake vs the modules' light pools (hw-grounds-b's integration note): the modules previewed their light on the
  ground as a 0.035 diffuse at exposure 1, the stage bakes GRASS 0.03 at 6.0 x NIGHT, so the pools would have come out
  ~2.6x brighter. hw_stage now bakes the 149 module lights onto the ground x0.39 and restores them afterwards.
- All seven modules done (graveyard + infrastructure, vendors + forest, carnival + pumpkins + crypt/swamp); the lint
  passes with no flags and no collisions; grounds ~140.5k tris of 185k. Costumed crowd done: 4,549 people, 334k tris,
  56% in costume (skeleton, devil, witch, zombie, pumpkin, cat, ghost, vampire, mummy), two new clips (lurch, claw).
  Graveyard ships 8 hinged coffin lids + 2 hinged arms; the Pumpkin King's jaw was requested from hw-grounds-c.

## 2026-10-09: v2 full build (the helpers hit their weekly usage limit; the lead finished their work)

- hw-grounds-c and hw-visuals stopped on the weekly limit at 22:2x on 2026-10-08. No stale GPU lock or process.
- The Pumpkin King's jaw, done by the lead in hw_pumpkins.py: a closed shell plate over the lower face (6 cm proud),
  a glowing mouth on the head behind it (2.5 cm: z-fighting margin at ~110 m), hinged left-right at the grin's
  corners, 28 degrees, delay 0.8 (shut through the build, open for the drop); 216 hinged tris. Preview camera "king"
  added to hw_preview.py.
- Full v2 ship_hw.sh (2026-10-09 16:55-17:15): bake 937 s, 41 meshes, 7 modules, 11 hinged parts (484 tris: 8 coffin
  lids, 2 arms, the jaw); lasers 0 hits in 49 lines x 27 poses with the crowd, DJ head gap 11.2 m; comfort PASS (sky
  at a full strike 11.6% display luma); DJ overdraw 1.01 layers/px occluded; Unreal: 41 actors + 2 lamps, cook 0
  errors / 3 warnings, chunk-54 shader archive present; pak 141.5 MB (the plan's target was 130: the crowd mesh
  21.5 MB, the VAT 16 MB and seven 4096 bakes at 9.5 MB each; the graveyard/vendors bakes at 2048 would save ~14 MB
  if load time suffers). Previews: claudedocs/halloween_v2/ (hw_v2_sheet.jpg).
- Drone reel: the graveyard crawl passed 0.36 m from a raised hand in the walkway queues: raised to 3.3 m over the
  field; the whole reel now passes hw_dronecheck (minimum 0.6 m, the orbit past the deck props).
- Push: refused at 17:15 because Tribe was running on the headset (someone was in it). A watcher
  (scratchpad push_when_closed.sh) pushes through push_obb.sh once Tribe has been closed for a minute; v1 pak kept at
  C:\Users\Chris\TribeUE\paks_current\rollback\pakchunk54-Android_ASTC_P.v1_20261008.pak (md5 1d828b4f...).
  The live OBB had changed again (the Dino session's chunk 50, md5 b11c0398...): the merge keeps it.
- Loops: 5 of 8 passed by hw-visuals (Witching Hour, Bat Swarm, Blood Moon, Dead Forest Ride, Hellgate). The lead
  wrote the sting (GRAVEYARD / SHIFT in bones, 4 bars), Candlelight Seance and Thriller Yard, and renders Pumpkin
  Stomp (hw-visuals' script) and those three.
- PUSHED v2 at 2026-10-09 17:19:37 (Tribe had been closed for a minute; push_obb.sh verified the device md5): live OBB
  md5 632ff97d812fdbc1a54940fa4134a497 = chunk 50 b11c0398 (Dino), 53 7420a9fc, 54 734f3f96 (Halloween v2, 141,534,534
  B, the animated build), 55 23911ea0 (club). envs.txt unchanged (Graveyard Shift already there). Relaunch Tribe to
  mount it. Rollback: push the v1 pak in paks_current\rollback\ with push_obb.sh.
- The user opened Graveyard Shift at 17:09 and found it "didn't look done at all": that session ran v1 (Tribe started
  17:09:39, died 17:17:55 in the event log); v2 was pushed at 17:19 and needs a relaunch. Not yet seen in the headset.
- Loops, all gated (check_loop.py on frames and on the MP4): the lead finished Pumpkin Stomp (hw-visuals' script: it
  failed with accents x2.4 and 1 m2 blocks 0.78: the slammed pumpkin now holds for 72% of the accent, the impact lands
  a frame after the beat, softer faces; the 0.78 block was the King's crown clipping to white at the top edge, dimmed
  1.3 -> 0.55; now blocks 0.52, seam 78.5 dB) and wrote + rendered the sting (GRAVEYARD / SHIFT in bones, 4 bars),
  Candlelight Seance and Thriller Yard (after a look-dev: horizon lowered, the front stone row removed, rows closer, a
  moon). Delivered: C:\Users\Chris\TribeUE\Visuals\halloween\deliver\ (9 files + README.txt) and pushed md5-verified to
  /sdcard/Movies/Halloween Visuals/ (scripts/push_media.sh) at ~17:58.
- Not pushed: the Halloween drone reel (claudedocs/halloween_drone_path.txt): the mod reads one drone_path.txt for
  every stage, so copying it over would replace the Dino reel too. A per-stage reel needs a hook change (Dino session).
- Open: the headset check of v2 (load time, fps >= 71, the screen video, the animated materials not grey, the comfort of
  the lightning and fire, the clock turning clockwise, the King's jaw); a passive logcat capture is running
  (scratchpad logcat_hw_v2.txt, 3 h from 17:20).

## 2026-10-09 evening: v2 seen in the headset; v3 = darker + many more lasers, music-driven (Dino engine)

- The user saw v2 at ~22:24 (two Tribe runs; capture scratchpad logcat_hw_v2b.txt): "looks pretty good! just needs to be
  a lot darker out. also we DEFINETLY need more lazers". No shader errors (the animated materials loaded). Graveyard
  Shift 70.2-72.0 fps over ~2.5 min (the 10-s windows after the switch-in included), 11-28 frames over 20 ms per 10 s
  late in the second visit; Dino Stage and Reactor ~71.6-72.0 once settled. So: thin lasers only, no heavy additions.
- Same evening the user asked the Dino session for "the lazers being music driven like how we have at the dino stage"
  on Reactor and Graveyard. Agreed with the Dino session (tribe-hack-f1):
  - Graveyard uses the Dino's laser engine, dino_materials.laser_show (imported, never edited, as build_club.py does),
    with the Dino's show.py tables written by hw_stage.py (T_HwLaserProg / T_HwLaserLib, and tex_cues() as the lasers'
    16-row cue table T_HwLaserCues).
  - MPC_HwShow at /Game/Mods/Halloween/MaterialInstances/MPC_HwShow: the 17 show-bus names plus ShowPrevBar /
    ShowNextBar (-1 default). The hook (dumper.cpp, Dino session) now finds the active stage's collection; it also
    writes ShowPrevBar / ShowNextBar in song mode (source md5 710855a7; it ships in the next APK, at the user's say).
  - Bus semantics (Dino session): ShowOffset puts the show on the song's bars (32 bars at 140 BPM, the same loop as
    ours; song mode loops sections intro 0-7, build 8-14, drop 16-23, breakdown 24-27, outro 28-31; bar 15 only in the
    free show). ShowLevel 1 except a song's "dark" look (0) or "top" (0 + TopLasers 1: groups 1-5 and 7), 0.15 s up /
    0.3 s down fades. Hits 0.15-s decays, DropBoom 1.2 s, Bass 0..1.
- v3 changes:
  - Darker (hw_stage):
    - the grounds bake x0.45, the field x0.6 (its module pools too), the crowd x0.7, the set x0.7 (SET_DIM);
    - the sky's clouds and horizon glow x0.35 and its stars x0.8 (display luma at rest 3.8%, a full strike 9.9%);
    - the far ground x0.4.
  - Darker (materials and build): the fog x~0.2 and lit 0.15..1 instead of 0.35..1 (v2's fog showed as a grey veil
    over the field, display ~0.2-0.33, the brightest non-emitter); the set's floors 0.08/0.10 -> 0.05/0.06; the crowd's
    floor 0.06 -> 0.04; the strike gain 2.2 -> 3.0 on the darker sky.
  - The whole show is on MPC_HwShow: hw_materials.show_time = Time + ShowOffset, every cue level x ShowLevel, the bar
    ramps and glides use ShowPrevBar / ShowNextBar when sent (else the clock's neighbours: in song mode a section loop
    would have blinked the set for 60 ms every 8 bars).
  - Lasers, rebuilt in the Dino's format (club_lasers.py's copy of atmosphere's laser_mesh: raw values, no pre-flip):
    17 units, 146 beams (v2: 49), plus aperture glows. The engine's families:
    - 0 fan: the portal;
    - 1-4 horns: the gargoyles;
    - 5 towers: new sky lasers from the front pinnacles;
    - 6 lip: six new units on 1.2 m posts at the deck front, between the flame jets;
    - 7 mouth / 8 delay: the back / front crypt towers' skull eyes, aimed back over the DJ at the stage.
  - Each beam's length is solved for the engine's whole +-1 pan/tilt sweep (13x13 poses plus swept surfaces between
    them: the first fast test showed lip beams slipping through the crypt towers' lattice and skull beams through the
    portal truss between sampled poses). Rules: raised hands (field +2.3 m), the deck +3 m, at least 4.9 m from the DJ's
    head, 0.4 m short of the set and the grounds. Stubs under 40% of their unit's longest dropped (3). Verified at 11x11
    other poses plus sweeps: 0 problems, closest 6.4 m. ship_hw.sh now stops unless that line reads 0 problems.
  - hw_cuecheck: floors and fog read from their sources. The lasers are modelled as the Dino engine (group levels x its
    strongest beat pulse): <= 3 flashes/s, steps and beat pulses exempt from the attack rules. That's the Dino's engine
    unchanged, thin lines; drum-hit flashes from the hit maps are at most one per beat.
- Backups: out_hw_v2/ (the v2 bake), paks_current\rollback\pakchunk54-Android_ASTC_P.v2_20261009.pak (md5 734f3f96...).
- Built 2026-10-09 23:18-23:38 (ship_hw.sh, no push), after the Dino session's FBX check suggested 0.2 m more
  headroom over the field (HEAD_Z = field + 2.5; the first full bake was stopped 3 minutes in and restarted):
  - bake 16 min: 146 beams, verification 0 problems, closest to the DJ 6.4 m;
  - comfort PASS (sky at rest 3.8% display luma, 9.9% at a full strike);
  - DJ overdraw 1.02 layers/px (v2 1.01);
  - drone reel PASS: its low pass over the deck lifted 0.4 -> 1.0 m, 0.53 m over the new laser housings;
  - Unreal: MPC_HwShow created with 19 scalars; M_HwLaserShow (the Dino engine) built; the cook ran 0 errors with no
    material failing to compile; the chunk-54 shader archive is present.
  - pak 141,652,126 B, md5 225bb7f02755acf17191e4a1e63f116f.
  - The Dino session's laser_fbx_check.py on the final FBX: PASS (lowest point 2.51 m over the field, DJ 6.39 m,
    UE pose emulation 0.095 cm).
  - Brightness vs v2 (display luma means of the textures): sky forward view 0.086 -> 0.038, field 0.035 -> 0.022,
    carnival 0.137 -> 0.097, pumpkins 0.122 -> 0.081, vendors 0.089 -> 0.059; the set's bakes x0.7 (deck output mean
    0.021 -> 0.016). Before/after sheet: claudedocs/halloween_v3/hw_v2_vs_v3.jpg.
  - The push dry run read the headset's live chunk 54 (v2, 734f3f96) and would replace it. NOT pushed: waiting for the
    user. The music sync also needs the Dino session's next APK.
- 2026-10-10 04:26: the user approved "push once Tribe is closed" (they are away until later). A watcher (scratchpad
  push_v3_when_closed.sh, 36 h) pushes the STAGED copy C:/Users/Chris/TribeUE/paks_current/staging/v3_20261009/
  pakchunk54-Android_ASTC_P.pak (md5 225bb7f0...) once Tribe has been closed for a minute, so later builds can not
  change what gets pushed. A read-only log capture (scratchpad logcat_hw_v3.txt) runs to 14:27.
- ROLLBACK FIX: push_obb.sh names the OBB entry after the file's basename, so pushing a renamed file
  (pakchunk54-...v2_20261009.pak) would have ADDED a second chunk-54 pak instead of replacing it. The rollback commands
  given on 2026-10-09 were wrong. Rollback paks now sit in per-version folders under the right name:
  paks_current/rollback/v1_20261008/ and /v2_20261009/pakchunk54-Android_ASTC_P.pak (md5 1d828b4f / 734f3f96).
  Rollback = close Tribe, then:
  bash scripts/push_obb.sh --push C:/Users/Chris/TribeUE/paks_current/rollback/v2_20261009/pakchunk54-Android_ASTC_P.pak

## 2026-10-10: v4 = the stream intro (the Headless Horseman's ride), building; not pushed

- The user (away from the headset): a cutscene for when the Twitch stream starts.
  - The Headless Horseman rides through the woods behind the stage, head in his left hand, a lantern in his right.
  - The stream camera is low at his front left, looking up. "Eventually the trees clear up and we get to the back of
    the stage."
  - A backstage button raises a roll-up door ("like a garage door") under the screen. A song plays and the user walks
    out to the decks.
  - At the door, the camera is at the front of the stage, showing the whole thing and part of the crowd.
  - Chosen via AskUserQuestion: a Horseman MODEL rides (the user isn't moved), two presses end it, the door is under
    the screen.
  - Then: "Gonna have to make WAY more trees ... riding through the middle of a spooky forest".
- Feasibility from the Dino session (it owns the mod's side; it builds when the user says "build"):
  - It's unknown whether UE level sounds reach the stream. Tribe's decks play through Superpowered/OpenSL, so the intro
    song plays from a cued deck (the mod presses Play: BP_PlayButton_C / BP_Deck_C). SFX get mixed into the track.
  - Walking already works per stage via tribemod/<folder>_collide.txt (halloween_collide.txt).
  - The drone reel is now per stage: tribemod/drone_path.halloween.txt (the Halloween reel can finally go on).
  - Buttons: the giant button's hand-distance code (14 cm). Moving our actors each frame is fine.
- Built (Scripts/Blender/halloween/intro/ unless noted):
  - hw_intro_path.py (plain Python: the single source for the ride).
    - Loop: 174 m / 29 s, anticlockwise, so the camera on the rider's left rides the loop's clear inside.
    - Exit: leaves along the loop's tangent on a 9 m arc (the Dino session's review: the first exit snapped 76
      degrees), out of the trees to the nave's back corner, 63.5 m / 11.6 s. The camera holds 7 s in; he vanishes
      round the corner.
    - Centripetal Catmull-Rom (the uniform form backtracked).
    - Writes hw_intro.txt for the mod: 82 keys at 0.5 s, cams, the wide shot, the button, the spots, actor and
      scalar names, 3 presses.
  - hw_rider.py: the user's own avatar (repo skins/horseman.glb, read only), headless, IK-posed in the saddle,
    holding the pumpkin (heads/horseman.glb) in the left hand and a lantern in the right.
    - The horse: a black metaball "nightmare" horse with a flame mane and tail and glowing eyes.
    - The gallop: a procedural transverse gallop, 1.7 strides/s = 6 m/s.
    - export(): SM_HwRider (15,364 verts) with the gallop in the crowd's VAT format (T_HwRiderVAT 2048x256, played by
      hw_materials.vat_crowd), lit by T_HwRider (Cycles: the lantern, the pumpkin, the moon).
  - modules/hw_woods.py: about 375 dead trees from hw_forest.Tree (imported read only; its branch rule is wrapped
    during the build to keep the trail and the camera lane clear below 7 m), the trail, lanterns, wisps, a moon
    shaft.
    - About 91K tris: 23K lit, 69K black silhouettes.
    - OWN_GLOW: hw_stage.py now lets a module ship its own glow mesh (SM_HwGroundsGlowWoods), so the mod can hide the
      whole wood outside the intro.
  - hw_stage.py v4: the crypt gate in front of the screen's lower middle, behind the booth. The screen is unchanged;
    raising it would have put the truss lanterns over the picture.
    - Stone frame, pinnacles, a skull tympanum hiding the roll drum, and a backstage crypt with a red work lamp, all
      baked with the deck.
    - SM_HwGate: 10 slats, baked to T_HwGate. UV1 holds each slat's centre z for hw_materials.gate_lift (rise, then
      fold into the drum, on MPC_HwShow DoorOpen).
    - SM_HwButton: the cap; hw_materials.intro_button colours it by IntroStep.
  - build_halloween.py: the gate, button, rider (VAT), the woods' glow, and MPC_HwShow's IntroStep (0) / DoorOpen
    (1 = open when no intro runs).
    - HwRider, HwWoods and HwWoodsGlow: renamed, parked (the rider at z -50 m) and saved hidden in game; the mod
      shows them for the intro.
  - hw_collide.py: halloween_collide.txt.
    - Contents: Dino's riser and stairs, the deck in front of the gate, the crypt, walls, spots decks and backstage.
    - Checks: my 10 cm walk check finds crypt -> gate -> deck -> side stairs -> decks; the Dino session's
      independent check reached the decks with no dead ends.
  - hw_animatic.py: the preview video, using the shipped bake and the same math the mod will use.
- The flow as proposed: press 1 = the pre-show (the door shuts, the ride loop, the stream camera on the rider),
  press 2 = ride in (the exit at the loop's end; mean 26 s to his arrival), press 3 = showtime (the cued deck plays,
  the wide shot, the door rises).
- Open questions for the user (the Dino session's):
  - a: press 3 during the exit: queue it or cut at once?
  - b: which deck plays, and what happens to another playing deck?
  - c: one intro per stage load?
  - d: should the mod set the capture's FOV to match the preview (79 / 66 degrees)?
  The deck press also needs one log_pe capture on the headset (the user's OK).
- 2026-10-10 morning: the user said "Ok go ahead" (the Dino session builds the mod side, which it has: compiled, not
  packaged).
  - Their showtime idea: "a button backstage that when I press it, the venue gets dark, starts the visuals. I could
    load up the song on the deck before I go back there ... the button is mapped to the play button on that deck."
  - So press 3 = the paused cued deck's Play: dark for 'hold' s, then the deck plays, the visuals start (the mod
    rewinds and pauses Tribe's BackdropMediaPlayer at press 1 and plays it with the music), the door rises.
  - No song name is needed.
- The mod's file is now tribemod/intro.halloween.txt (one per stage folder): 0.25 s keys, 3-decimal times, plus
  fov ride 79 / fov wide 66, hold 2.0, back 20.
  - The deck press waits for one log_deck capture on the headset (the user presses Play then Pause once); the Dino
    session writes tribemod/intro_deck.txt from it.
- Preview 1 (sent to the user): its held arrival shot was black. Fixes:
  - cold moonlight spots on the back of the cathedral (BackMoon±1, BackMoonC);
  - the exit camera framing the towers;
  - camhold at exit + 4.5 s;
  - a ruined doorway in the nave's back wall at x -7.5: he gallops through it into the dark nave instead of round
    the corner in view;
  - the woods bake 2048 -> 1024 (its bark baked to ~0).
- v4 test cook (07:45, before the doorway): 0 errors, shader archive present, pak 167.5 MB (v3 141.7). The build log
  shows HwRider / HwWoods / HwWoodsGlow as StaticMeshActors, hidden in game; MPC_HwShow has 21 scalars.
- Preview 2 (08:27, sent): the user said "I cant really see the lantern". Fixes:
  - the lantern is raised and 1.4 times bigger, and its glass glows brighter;
  - the ride camera now sits in front of him.
  The user's other request was legs: "my arms are already tracked so we don't need to add that. Im more concerned
  about the legs moving". The Dino session built a legs-only walk cycle in its hook, driven by the player's speed. It
  is in its combo1 APK, which is not installed.
- v4 final (08:31): pakchunk54-Android_ASTC_P.pak, 165,814,739 B, md5 b3ce58e0. It is staged with
  intro.halloween.txt (a076dc93) and halloween_collide.txt (2058287d) in
  C:/Users/Chris/TribeUE/paks_current/staging/v4_20261010/.
- 2026-10-10 08:33: the user chose "Push v4 instead". The v3 watcher is stopped, so v3 will never be pushed.
  - A watcher in this session pushes only the staged v4 (it checks the md5), via push_obb.sh, after Tribe has been
    closed for a minute. It gives up after 36 h.
  - Tribe has been open since 10-09 22:24 (PID 11305, idle on the Dino stage), so the push waits until the user quits
    Tribe.
- The tribemod files go in after v4 is live, in the Dino session's push window, together with the combo1 APK and
  only when the user says push. The Dino session froze copies in backup/dino_pending/tribemod_after_v4/, and their
  md5s match mine:
  - intro.halloween.txt a076dc93
  - halloween_collide.txt 2058287d
  - drone_path.halloween.txt 6c1e0daf (claudedocs/halloween_drone_path.txt)
  If any of them changes, the new md5 goes to the Dino session before anything moves.
- Still to do in the headset, each with the user's OK:
  - install combo1;
  - one log_deck capture (Play, then Pause, on a cued deck) for the press-3 deck;
  - tune the walk cycle by eye;
  - run the intro end to end;
  - check fps and load time with the 166 MB pak (v2's was 142 MB).
- v4 is live:
  - 08:41:43: the Dino session closed Tribe (adb am force-stop) because the user asked it to ("Why cant you just
    close out tribe?").
  - 08:44:02: the watcher's push_obb.sh said PUSHED OK. The live OBB md5 is now 784d492b (it was 969123a1).
  - The OBB holds chunks 50 (1193318f), 53 (7420a9fc), 54 (b3ce58e0, v4) and 55 (7ccef713). envs.txt is unchanged
    because it already had Graveyard Shift.
  - To roll back to v2: paks_current/rollback/v2_20261009/.
  - Tribe has not been relaunched since. A read-only logcat capture (scratchpad logcat_hw_v4.txt, 24 h from 08:44)
    will record the first v4 visit.
- The Dino session's window ran right after the push:
  - 08:43:39: combo1 installed.
  - 08:44:57: v14b pushed on top of v4. The live OBB is now 7151057a, with chunk 50 87ec24ba and chunk 54 still
    b3ce58e0.
  - The three tribemod files went in at the agreed md5s.
  - Checked on the device, read-only, at 08:47: the OBB md5sums to 7151057a; the three files match; intro_deck.txt is
    absent (until the deck capture, press 3 does everything except start the song); envs.txt has Graveyard Shift.
- 08:47:22: the club's v7 was pushed with the user's OK. The live OBB is now db9445bc. Only chunk 55 changed
  (793294ce); chunk 54 is still b3ce58e0, per paks.txt.
- 11:00 VJ loops: the REACTOR session found that Blender 4.5 EEVEE renders a session's first frame without motion
  blur. They suspected every Graveyard loop's frame 0, because make_loop.sh renders 0 first. Checked here by
  rendering frame 0 first and then second in the same session:
  - Blood Moon: 59.1 dB.
  - Dead Forest Ride: 59.5 dB.
  - Witching Hour: 65.0 dB.
  These match the shipped seam gates, so the bug is real here. With a warmed session the seams are 96.5, 65.9 and
  70.3 dB.
  - The changed pixels are 0.01-0.03% of the frame. In Blood Moon they are the wing trails of three small bats in
    front of the moon, one frame every 13.7 s. That can't be seen, so the shipped loops stay on the headset.
  - Visuals/halloween/scripts/vjkit.py render_frames now does one throwaway render per session when --mblur is on.
    The patched kit's frame 0 is bit-identical to a warmed render (checked).

## 2026-10-10 midday: v5 = two crypt doors instead of the roll-up (staged, not pushed)
- The user: "Ok so for the crypt door, make them 2 doors not a garage door. Like crypt doors".
- intro/hw_intro_path.py is the single rule:
  - DOOR_T 0.10, DOOR_OPEN_DEG 110 (outward, to the deck), DOOR_STAGGER 0.15 (the right leaf trails);
  - door_turn_deg / door_xy.
  - The mod's file still regenerates byte-identical (a076dc93); its comment text "the door rises" was kept on
    purpose.
- hw_stage.py:
  - build_gate makes two oak leaves, 1512 tris. Each has a backing board and 5 planks, 3 iron strap hinges (studs,
    a diamond tip, a knuckle on the hinge axis) and a ring knocker on the front, and 3 ledges and a Z-brace behind.
    UV1 GateData u = the leaf's side.
  - The roll-up's guides and drum are gone; iron hinge plates sit on the pillars.
  - The lasers are solved and verified against the doors shut and open (gate_open_pose, a check-only copy that is
    never baked or exported).
- hw_materials.door_swing replaces gate_lift. It turns each leaf in Blender's frame from WorldPosition (v4's level
  mapping), not RotateAboutAxis. Simulated node for node against door_xy: 0.0000 mm worst over 20k points.
- halloween_collide.txt (md5 6c8cff8f) adds the boxes door_open_-1 and door_open_+1, the open doors' footprints.
  - My walk check is OK.
  - The Dino session re-checked it with the C++ and Python rules: 58,037 states, 0 dead ends; the 442 states lost
    are all inside the new boxes.
  - The Dino session pushes the map right after the v5 pak, in the user's push window.
- hw_dronecheck.py checks the doors open as well as shut: PASS, the same numbers as v4.
- The chain ran 11:49-12:36:
  - a fast check;
  - the bake: laser verification 146 beams, 0 problems, OK; T_HwGate output mean 0.007 (v4's iron door 0.004);
  - the preview video;
  - comfort PASS; overdraw within budget; drone PASS;
  - Unreal build OK, cook 0 errors, shader archive present; push_obb.sh dry run OK.
- Staged in paks_current/staging/v5_20261010/:
  - the pak: 165,933,914 B, md5 a67563bd;
  - intro.halloween.txt a076dc93;
  - halloween_collide.txt 6c8cff8f.
- Kept for rollback: v4's bake in out_hw_v4/ and v4's preview as out_animatic/hw_intro_preview_v4.mp4.
- The new preview went to the user at 12:4x. Pushing waits for the user's OK, and Tribe must be closed.
- hw_animatic.py gained --cam X,Y,Z:TX,TY,TZ:LENS and --door a,b,c (DoorOpen per --times moment) for close-up
  look checks.
- The user also got 720p preview copies of the nine VJ loops (scratchpad visuals_preview/).
- v5 is LIVE. The user said "Push once closed" and Tribe was already closed:
  - 12:48:17: push_obb.sh said PUSHED OK. The live OBB is now 2e5915c7, with chunk 54 a67563bd; the other chunks
    are unchanged.
  - 12:48:19: the walking map went in (via /data/local/tmp, cp, chmod 666). The device reads 6c8cff8f.
  - All three md5s were re-checked on the device. The Dino session was told.
  - To roll back: paks_current/rollback/v4_20261010/ (pak b3ce58e0 + the v4 map 2058287d).
  - The read-only logcat capture (logcat_hw_v4.txt, until 08:44 tomorrow) will record the first v5 visit.

## 2026-10-10 16:21: v5's first visit (my capture, logcat_hw_v4.txt; the Dino session's report agrees)
- Clicked 16:21:22. The level loaded in 2.6 s; MPC_HwShow 19/19; the walking map read 11 floors and 32 boxes
  (2649 B = v5's 6c8cff8f); [INTRO] ready at 16:21:37; the reel loaded 13 shots, 153 s.
- fps: 70-72 in every 10 s window after the load. The load window was 58.1 fps, about like Reactor's load.
  - Single long frames: 182 ms at 16:22:34 (the user's first time behind the doors), 146 ms at 16:24:14,
    94 ms at 16:24:34.
  - No DefaultMaterial, shader or fatal lines.
- The user walked down through the doorway to the button and back with no refusals. Press 1 at 16:22:43.9 shut the
  door over 4.0 s, and the pre-show looped until the user left for Reactor at 16:25:10. No press 2 or 3.
- The 16:24:46-16:25:05 stall was two Lampwing skin loads (about 9 s each), not the stage.
- The head BOO (the character session's auto mode) flies to the stream camera wherever it is:
  - in the reel: 16:21:36 in shot 1 (the head went about 38 m out) and 16:22:20 in shot 5 (about 28 m);
  - in the intro pre-show: 16:23:11 and 16:24:13, about 80 m into the woods. It hung 4-6 m from the intro camera
    next to the rider: a second head beside the Horseman who carries his own.
  - The reel can't follow random takeoffs (22-35 s after landing). For 61% of the loop (93 of 153 s) the lens is
    more than 15 m out (shots 1-5 and 12, 28-127 m); only shots 7, 8, 9 and 13 stay under 6.3 m
    (scratchpad reel_dist.py).
  - Suggested to the Dino session for the head code (not ours; the user's call): no auto takeoff from press 1
    until the intro hands the camera back; BOO only within about 15 m of the lens. The reel and intro file are
    unchanged.
- Not confirmed: how the doors look and move. That needs the user's eyes.
- Update 16:3x from the Dino session: the character session had already added head.txt boomax=<m> (hook/head.cpp
  f8854277, which I checked). Default 12 m; 0 = any distance. While the lens is farther than that from the hips,
  the BOO is skipped, not delayed, and the head keeps orbiting. It ships with the next APK build.
  - With 12 m, every intro BOO is skipped (that camera is 80-130 m out). So are about 2 in 3 Graveyard reel BOOs:
    the lens is more than 12 m out for 98 of 153 s (64%).
  - Still open, and the user's call: stopping automatic takeoffs during the intro. Passed to the character session.

## 2026-10-10 evening: v6 = the horse rebuilt and the rider's VAT fixed (staged, not pushed)
- The user, typed in the Dino chat: "Also the quality of the horse needs upped A LOT. it looks like shit in there".
- Root cause, my bug since v4: hw_rider.export() wrote the VAT data UVs without the V-flip pre-compensation that
  crowd/hw_crowd.py does (Unreal's FBX import stores 1 - V on every UV channel). In game:
  - the horse's two vertex bands swapped offsets, so its front tore into spikes as it galloped;
  - bands 2-7 clamped to zero offsets, so the rider, pumpkin and lantern froze;
  - VatRotScale read (1, 1), which turned every offset 45 deg and scaled it by 1.41.
  - The v4/v5 previews rendered the Blender rig, never the exported asset, so nothing showed it.
- Fixes and new checks:
  - export() writes the data UVs pre-flipped. Before writing anything it decodes its own output the way Unreal reads
    it (hw_rider.ue_decode). v6: every frame and half frame within 0.49 mm. Negative test: v5's writing decodes
    2.57 m off.
  - build_halloween.check_rider_uvs reads the imported UVs back in Unreal and stops the build if they're wrong. v6:
    "bands [0..11], VatRotScale (1, 0)".
  - hw_animatic.py now draws the rider as Unreal does by default: the exported FBX, its bake, and the VAT decoded
    with the flip. --live-rider gives the old Blender rig.
- The horse: Quaternius "Horse" (CC0; intro/assets/quaternius_horse.glb + README.txt with the source and md5).
  - Welded and smoothed, Subdivision 1 after the armature.
  - Its keyframed Gallop is sampled into 56 poses with the loop closed, played at GALLOP_HZ 2.4: the planted hooves
    sweep about 2.4 m a stride, which keeps them on the ground at the ride's 6 m/s.
  - Restyled: a black coat with a sheen, glowing eyes, burning mane, tail and fetlocks; tack (a ragged blanket,
    saddle, flaps, stirrups, a bridle with bit rings, and reins), skinned by the nearest body vertex's weights.
  - The lantern has four amber panes behind mullions, and its light now escapes in the bake (shadow rays pass the
    panes). The pumpkin's glow moved in front of its face.
  - The avatar keeps 70% of its faces (was 42%).
  - The VAT is 2048x512, 12 bands x 29 rows (28 frames); the mesh has 23,978 verts. M_HwRiderVAT is two-sided.
  - The bake is lit for the stream camera: a moon key from its side, a rim from behind, the lantern and the
    pumpkin; diffuse plus the gloss as that camera sees it; 1024 samples on OptiX.
- Old files: intro/hw_rider.v5.bak.py, intro/hw_animatic.v5.bak.py; v5's rider export in out_hw_rider_v5/.
- Pipeline (ship_hw.sh --skip-bake):
  - comfort PASS, overdraw OK, drone PASS;
  - ANIMATED build, cook 0 errors, shader archive in chunk 54;
  - push_obb.sh dry run OK (merged OBB would be 13f615e8).
  - A first try that ran cook_halloween.sh alone made a STOCK build: it builds stock unless HW_ANIM=1, which only
    ship_hw.sh sets. Caught from the build log before staging.
- Staged in paks_current/staging/v6_20261010/: the pak (170,761,809 B, md5 ebc50e43), plus the unchanged intro
  a076dc93 and map 6c8cff8f.
- Rollback: paks_current/rollback/v5_20261010/ (pak a67563bd, map 6c8cff8f, intro a076dc93).
- Push: scratchpad push_v6_when_closed.sh (chunk 54 only), after the user's OK. The tribemod files are unchanged, so
  the re-seed backup needs nothing.
- Preview: intro/out_animatic_v6/hw_intro_preview.mp4 (the in-game rider).
- Before/after renders as the game decodes them: scratchpad horse_tools/before_after.png.
- v6, part 2 (the user, answering the push question: "can we make where the headless horseman rides into the crypt
  glow?"; also "what does that button do?", answered: the push option and the three crypt-button presses):
  - hw_stage.crypt_glow: a veil of light just inside the back wall fills the ruined doorway the rider enters
    (x -9.5..-5.5, y 45). Nested pointed arches in 7 greens, from a deep edge to a pale core (GLOW crypt_0..6; the
    palette grew to 4 rows, and every glow UV is rebuilt by the bake).
    - It is part of SM_HwGlow, so it flickers softly in game (M_HwFlicker).
    - In the bake it lights the jambs and throws a green pool on the path.
    - It is opaque and faces out, so he rides into it and is gone.
  - hw_intro_path.CAM_EXIT look 9 -> 6.5 m: the held shot shows the whole glowing doorway and the ground. The intro
    file changes by that one line (cam exit look=1000,0,650): md5 a076dc93 -> e5262e86.
    - It is a tribemod file: push it with the pak, then copy it into backup/tribemod_20261006/ and tell the Dino
      session.
  - The rider's bake: rim 2.6 -> 1.3, and the sheen is baked view-independent at 0.4. Baked from the front camera,
    the rump flared near white when the exit camera follows from behind.
  - hw_animatic.py: HW_STAGE previews another bake folder. The fast test bake is out_hw_cryptfast (scratch).
  - The full bake and ship ran as one pass: ship_hw.sh, no push.
- v6, part 3: the drone reel. The user: "lets just focus the camera trail around the crowd and the stage. i noticed
  its showing the other stage and i dont really want that. instead, do a high up shot of the crowd and stage".
  - claudedocs/halloween_drone_path.txt (the tribemod file drone_path.halloween.txt): 13 shots / 153 s -> 11 shots /
    131 s, md5 6c1e0daf -> c3c9f93d. The old reel is in scratchpad halloween_drone_path.v5.txt.
  - Out: the pumpkin patch, THE CRYPT (the second stage), the haunted carousel.
  - In, second: "high up", a 16 s sideways pass 42 m above the field behind the crowd ((+-30, -62) m Blender),
    looking down to (0, -14, 3): the whole crowd and the stage beyond.
  - Kept: the walkway crawl beside the crowd (it heads at the stage), the tower climb, and the rest near the DJ.
  - hw_dronecheck.py on the fast bake (same geometry): PASS. The high pass's nearest object is the bat flock, 12.9 m
    away.
  - It goes in with the pak and the intro on the user's OK, then into backup/tribemod_20261006/. The Dino session
    gets the md5.
- v6, part 4: "the pumpkin head on the avatar is a little too high" meant the user's OWN avatar (the Dino session asked
  them: the head on the coat's collar, lower). That goes to the character session.
  - On my side, the intro rider's held pumpkin sits in his grip now: it floated 5 cm over the wrist (offset 0.17 ->
    0.09). The 6 cm hand drop I first made for it was reverted.
- v6 final, all in one pass:
  - ship_hw.sh (the full bake with the crypt glow): lasers 146 beams 0 problems; comfort PASS; overdraw DJ 1.02;
    drone (the new reel) PASS.
  - Then the rider re-export and ship_hw.sh --skip-bake: ANIMATED build, cook 0 errors, shader archive in chunk 54,
    the rider's UVs read back OK. The dry run merges to OBB 5b396b9d.
- Staged in paks_current/staging/v6_20261010/:
  - pak ba4ebd92 (170,813,662 B);
  - intro.halloween.txt e5262e86; drone_path.halloween.txt c3c9f93d;
  - walking map 6c8cff8f, unchanged.
- Rollback: rollback/v5_20261010/ (pak a67563bd, intro a076dc93, drone 6c1e0daf, map 6c8cff8f).
- Push: scratchpad push_v6_when_closed.sh. It checks every md5, pushes the pak via push_obb.sh, then both tribemod
  files via /data/local/tmp (md5 on the device), then copies them into backup/tribemod_20261006/.
  - Waiting on the user's OK. Tribe must be quit (it was open on Reactor, pid 26930, per the Dino session).
- v6 is LIVE. The user asked "did we already push? ask the main chat": the Dino session and my read-only check at
  19:58 both showed v5 still on. Then the user chose "Push now" (Tribe was closed since 19:50:28).
  - 20:03:57 push_obb.sh PUSHED OK: OBB f206696d (was 2e5915c7), chunk 54 ba4ebd92, the others unchanged.
  - 20:04:00 intro.halloween.txt e5262e86 and drone_path.halloween.txt c3c9f93d are on the device (md5 checked) and
    in backup/tribemod_20261006/.
  - Rollback: paks_current/rollback/v5_20261010/. The Dino session was told.
  - The read-only logcat capture (logcat_hw_v4.txt) will record the first v6 visit.

## v7 (2026-10-11, LIVE 2026-10-12 09:50)
- The user's v6 feedback, relayed by the Dino session: longer lasers, a way into the crowd (then free roam), the deck too
  bright and empty, a longer reel without the shot behind a building.
- Built: lasers land 1.5 m past the ground with a near-eye fade; the deck near-black with pools, coffin stacks, tombs,
  trees, candelabras, pumpkins and low fog; stairs and a barrier gateway plus 4,549 soft `person` lines (free roam,
  the crowd parts via UV5 VatPivot and PlayerX/PlayerY); a 32-shot reel checked for sight (hw_dronecheck --hidden).
- Found: v6's bake had a black crowd and ground (Cycles "Error writing tile"); bake() now refuses an all-black texture.
- Pushed on the user's OK in this chat: OBB cae836af (chunk 54 ba54c9db), halloween_collide.txt 2ed4e6b7,
  drone_path.halloween.txt 292a7dc5; all md5-checked on the device and copied into backup/tribemod_20261006.

## v8: the Crowd camera (2026-10-18)
- The user: "add another camera view to the selfie camera AND another camera view entirely. well both will have it.
  its a camera in the crowd about where the middle platform is looking at the dj"; "this is for the halloween stage";
  then a brand-new camera-menu button over taking over Camera 1-4 ("we've already done that with the stages in the ui").
- The view: on the FOH mausoleum's roof deck (FOH at (0, -31), platform top 2.05 m final) between the two follow spots,
  Blender (0, -31.3, 4.3) = Tribe (0, -3130, 430) cm, aimed at Tribe (0, 87, 90) (just under the DJ's head) at 40 deg.
  Picked from animatic stills (hw_animatic.py --cam, scratchpad foh_cam): A roof 90 deg (wide, the reel's look before
  combo9), B roof 35 deg (aimed too high), B2 45 deg, B3 40 deg from 4.3 m (chosen), C crowd level 65 deg (strong POV,
  but the front dancers block a held shot). Copies in halloween_v8/.
- Selfie camera: reel v8 (claudedocs/halloween_drone_path.txt 45406c4f; v7 kept as halloween_v7/drone_path_v7_live.txt)
  adds `fly 14 40,-3130,430 -40,-3130,430 look=0,87,90 fov=40` after the low crowd pass: 33 shots, 398 s.
  hw_dronecheck PASS (the new shot: 0.87 m from the follow-spot rig, view hidden 0 %). A hook before combo9 ignores
  fov=, so until then the shot plays at Tribe's 90 deg (still a good wide FOH shot).
- The button: hook/camview.cpp (new, 1a2f6f67) + hook-ins in dumper.cpp (3476d016 -> 040839da; the Reactor chat,
  which builds the APKs, cleared the edit and builds it as combo9). It reads tribemod/camview.<folder>.txt
  (camview.halloween.txt cdb4f106: label=Crowd, pos, look, fov=40, sway=0), finds W_VisualsMenu's camera buttons,
  clones one button cell with SpawnObject plus the widgets' own style setters, and adds it to the shortest row. A press
  (polled IsPressed) runs Tribe's Selfie handler, then holds the selfie capture at the view (drone_update's g_viewP /
  g_viewA; a stage intro still wins; the reel waits) at the file's FOV. Tribe's own camera buttons (their BndEvt
  handlers) give the camera back. It also applies the reel's per-shot fov=. Compile-checked: the same 7 warnings as combo8.
- First-run risk: the camera menu's layout was never seen; the code works it out at runtime and logs it ([CAMVIEW] tree /
  looks). Look for: "[CAMVIEW] added 'Crowd'", "'Crowd' picked", "[DRONE] selfie view", and the looks lines.
  Kill switch: tribemod/camview_off.
- Staged in paks_current/staging/v8_20261018/: camview.halloween.txt cdb4f106, drone_path.halloween.txt 45406c4f.
- Pushed 2026-10-18 10:52 on the user's go in this chat ("just do it now"), Tribe closed: combo9 by adb install -r
  (base.apk 2c747dd9, firstInstallTime unchanged 2026-10-16 19:10:56), both files md5-checked on the device and copied
  into backup/tribemod_20261006 (camview.halloween.txt is a new tribemod file name; the Reactor chat was told for
  reseed.sh). Live OBB unchanged then (0971dd30).

## v8: the crowd's hats (2026-10-18)
- The RED EYE session found arms through hats in the crowds; the Midtown session measured ours (hw_crowd.py 1b32e5c3
  keeps crowd3's clap, whose hands come down to ~15 cm over the head's centre) and handed it over: hw_crowd.py is ours.
- Measured again by another route (scratchpad hatfix/hw_armcheck.py: BVHTree.overlap of the posed arm / prop faces
  against each head part, every frame and half frame, every tier's superset AND every person as drawn: their morphs
  posed at frame 0 of their clip plus the canonical VAT offset). Its crowd build is the bake's (grounds modules with
  seed 1234 for exclude + extra, then build_crowd2(Random(11))): walk_people.json byte-identical to v7's (f1616c83).
  Midtown's hat table confirmed (and handsup is clean on the witch hat: their one "inside" vertex was a parity artifact).
  New: pumpkin heads (part "pumpkin", not in HEADWEAR) clash in clap / wave / hold / ride, far_pumpkin in clap / wave.
- Fix (hw_crowd.py c71cd777; v7 kept as hw_crowd.v7.bak.py): HAT_CLIP_SWAP + _hat_clip_swaps() as the last step of
  build_people, no rng draws: a dancer whose clip goes through what they wear on the head puts their hands up on the same
  beat; a filmer / totem holder / rider (hold, ride) takes the hat off (the witch band with it), or the pumpkin head
  (b_head comes back). 36 people changed; every other field of every person identical; walking map and VAT unchanged,
  so halloween_collide.txt stays 2ed4e6b7.
- As drawn, before -> after: near/mid hat or pumpkin overlaps 19 people -> 0. Left (all minor, not hands in a hat):
  far tier 4 pumpkin brushes (morph-made: 3 hold, 1 handsup) and 4 flat arm cards across the pyramid head (clap), one
  near clapper's hands touching the top of the hair for one frame, braids across the shoulders (17 people, crowd3's).
- Built with ship_hw.sh (bake 1430 s, "36 hat swaps"): lasers 0 problems, comfort PASS, overdraw dj 1.07, reel PASS,
  cook 0 errors (3 console-variable warnings), shader archive in; chunk 54 dd1ae112 (181,272,603 B), the same 287 paths
  as v7 (pak_list diff); walk_people.json f1616c83 and T_HwCrowdVAT.exr 4e346754 byte-identical to v7. v7's bake outputs
  kept in out_hw_v7/, its pak in paks_current/rollback/v7_20261011/ (ba54c9db).
- Pushed 2026-10-18 11:12:06 on the same go, Tribe closed, after telling the Reactor chat (it batches the other chats'
  pushes; the user wants one Tribe restart): OBB 4929c79f (was 19b1ad51, RED EYE's 11:06 push), every other chunk as it
  was; halloween_collide.txt unchanged (2ed4e6b7).
