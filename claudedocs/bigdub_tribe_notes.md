# BIG DUB for Tribe XR: the Main Stage (2026-11-01)

The user (2026-11-01): "i just want the main stage. also can we put people in it like the crowd?" and, after trying the
game's BIG DUB on the headset, "the darkness is perfect in here though dont change that or the jellyfish its cool".

Built in one headless run. **Nothing went on the headset:** no push, no install, no adb at all. Nothing is committed.
Labels: **measured** = run or read today; **assumed** = not verified, with the check named.

## What it is

An 8th Tribe stage, menu label **Big Dub**, folder `/Game/Mods/BigDub`, map `/Game/Mods/BigDub/Maps/Environment_BigDub`,
pak **chunk 56**.

It is the Stone Circle Main Stage of the user's own game (D:/VRDJ, the "hq" night of 2026-10-31), made by a copy of the
game's own generator (D:/VRDJ is only read) and the game's six night materials, ported to Tribe.

**Kept from the game (the same place, the same darkness):**
- the real terrain: 15 core tiles with 3 LODs each, plus the outer terrain, horizon and far canopy;
- the forest: 3,594 instanced trees;
- the sky: the Milky Way, procedural stars and the waxing moon;
- the Stone Circle: 59 stones and the Flame Stone, uplit;
- the whole stage:
  - deck, truss roof with moving heads and LED strips;
  - LED pillars and PA;
  - the barrier with its LED rail and the FOH;
  - the sun emblem and the **MAIN STAGE** neon sign;
- the **jellyfish and spiky flowers** over the crowd, and the flags round the ring;
- the Main Stage's 14 beams, 23 lasers in 3 fans, 3 sky beams and its crowd glow;
- the lit trees round the ring (40), the tents within 75 m, and the haze and the ground mist.

The night is the game's: its constants and formulas are copied verbatim. Its levels (`StageLight`, `Haze`, `Mist` and the
others) are at the game's values (all 1.0, `ScreenLevel` 0.85) in `MPC_BdShow`.

**Not built** (the ask): the Pavilion, New Camp, both bridges and the paths' furniture (the 148 path lights and the
festoons). Their light is out of the light map too: it holds the Main Stage's light and the 41 lamps that stay. The paths'
ground stays as the land is shaped. The creek is kept only within 250 m of the ring; the nearest water is 80 m away,
under the trees.

**Changed for Tribe:**
- **The frame:** Tribe's rig faces -Y; the game's Main Stage DJ faces yaw -102. Every BIG DUB actor carries one
  transform, +12 degrees about the DJ's point (0, 90, 0), so the DJ stands where the game's does.
  - Each material turns the world position, the camera and the normal back into the game's frame
    (`build_bigdub.py` `tribe_code`), so the light map, the moon and the stage centre read as authored.
  - The glow's World Position Offset is turned forward again.
- **The visuals screen:** the 12 x 6.75 m LED wall is Tribe's `SM_DinoVisualScreen` (Tribe's backdrop UVs), so the
  user's VJ loops play on it. The pillars keep the game's screen programmes.
- **The game's booth table is gone:** it stood inside Tribe's spectator box, where Tribe's own rig stands.
- **Deck lamps:** two `BdDeckLamp_L/R` spotlights, the same as HARVEST MOON's (Tribe's gear is lit; the set is not).
  `lights.txt` can scale them with `BdDeckLamp`.
- **The crowd** is Tribe's crowd v3, not the game's dancers (below).

## The light show (needs build C3)

- **The show collection:** `/Game/Mods/BigDub/MaterialInstances/MPC_BdShow`, 30 scalars:
  - the hook's 19 (`G_PARAMS`);
  - `PlayerX` / `PlayerY`;
  - the game's 9 night levels.
- **Same parameters:** the game's show driver writes the same 19 names as the hook, so the materials needed no
  re-wiring.
- **The light-show clock:** the materials read `Time + ShowOffset` as the game's do.
  **Assumed** to be the hook's convention too (the game's driver was ported from it); the first visit shows it.
- **Without C3**, the hook logs `no show collection for stage folder 'bigdub'`. The stage then runs on the collection's
  defaults: the beams and lasers still move on their own clock, but with no beat, no drops and no crowd making way.

## The crowd

| | |
|---|---|
| Dancers | **1,502**, filling the Stone Circle in front of the barrier, each on the knoll's real ground (z -2.72 to +0.07 m under the DJ's floor) |
| Tiers | 66 near (under 10 m from the DJ), 292 mid (under 16 m), 1,144 far |
| Triangles | 157,004 bodies + 3,267 glow (measured) |

**How it was built:**
- **The library:** HARVEST MOON's crowd library, copied to `tribe/crowd/hm_crowd.py`. In the copy, the totems are flags
  and inflatable aliens (no turkey legs or corn).
- **The driver** `bd_crowd_tribe.py` makes three changes:
  - **the field:** the ring's ellipse (inside 0.93 of the stones), with the FOH, the 4 LED pillars and the flags as
    keep-outs;
  - **festival costumes and hats:** aliens and foil, caps and straw hats;
  - **festival glow colours:** cyan, pink, green and violet.
- **The hat fix:** `HAT_CLASH` and `_hat_arm_swaps` ran (0 swaps were left to make).
- **The rng-stream rule:** the ground heights are an rng-free pass after the last draw.

**Its look:** colour baked on UV0 (albedo x a soft light from the stage's side), times the game's stage light at each
dancer: the purple wash, the sweeps, the moon, the lamps, the haze.

**Its motion:** the VAT dance (`hm_materials.vat_crowd`'s decode) and the make-way round the walking player.

## Budget (measured: the game's `estimate_budget`, a 104-degree view, 8 headings, Quest LODs; `tribe/tribe_budget.py`)

| eye | facing | heaviest heading | all around |
|---|---|---|---|
| the DJ (170 cm over the deck) | the crowd: 431,769 tris, 26 draws | 509,757 tris (+315 deg), 32 draws | 628,443 tris, 33 draws |
| in the crowd (20 m out, 165 cm) | the stage: 389,179 tris, 21 draws | 513,859 tris (+135 deg), 31 draws | 630,059 tris, 32 draws |

**Against GRAVEYARD SHIFT's 527,118 triangles, 44 draws and 2 lights:**
- inside from every heading, from both eyes;
- 2 lights (the deck lamps);
- the margin is 13-17k triangles. The far-creek trim bought 12k of it.

**Two corrections to the method:**
- The game's estimator skips a mesh whose bounds hold the eye when its centre is behind it. The renderer draws such a
  mesh, so the crowd is counted whenever the eye is inside it.
- 0 translucent or masked sections. The additive glow is one section.

**Not measured:** the per-pixel cost. Every surface runs the game's full-precision night shader (the light map, the
detail textures, the moon, haze and mist), which the other Tribe stages' baked textures don't. See Risks.

## Walking and the drone

**Walking: `bigdub_collide.txt`** (`tribe/bd_collide.py`, measured):

| Lines | Count | What |
|---|---|---|
| floors | 124 | the deck (z 0), its 15 back-stair steps, and 108 ground terraces over the ring and a band 1.10 x its ellipse (2.5-3 m past the stones) |
| boxes | 45 | the stage's walls, the barrier, the pillars, the FOH, Tribe's table, the LED wall |
| circles | 222 | each stone as a chain of circles, the flags' poles, the tree trunks near the band |
| people | 1,502 | the dancers, soft |
| spots | 1 | `decks` |

The file is 88,880 bytes, every count under the hook's caps (club_collide.h: 128 floors, 512 boxes, 512 circles,
4,608 people, 8 spots; 512 KiB).

**The walk check passes:** from the DJ a walker reaches 2,810 m². That covers the crowd's front, the middle, the Flame
Stone's end, behind the stage, and the band all round the ring, out between the stones.

**The limit:** the hook's floors are flat and there can be 128. On the knoll's slopes a foot stands at most **28 cm**
off the drawn ground (22 cm mean worst-point error); the hook eases the height between floors.

**The drone: `drone_path.bigdub.txt`.** 9 shots, 106 s. `tribe/bd_dronecheck.py` passes it (measured):
- the hook's limits;
- 1.5 m over the ground, and 3 m over the dancers;
- 0.8 m from every set vertex;
- out of the LED wall and the tree crowns.

It plays when `drone.txt` has `mode=path` (a global setting).

## Files and md5s (measured)

| what | where | md5 |
|---|---|---|
| the pak (chunk 56, 93 files, 67,056,111 B) | `C:/Users/Chris/TribeUE/paks_current/staging/bigdub_20261101_1355/pakchunk56-Android_ASTC_P.pak` | `494c9365bcc0542cb426b784567e858b` |
| the stages OBB, all 8 (884,116,934 B, comment `"      2311"`) | `.../staging/bigdub_20261101_1355/patch.2311.com.TribeXR.TribeXR.obb` | `1e3d2a3b3e81e8c78b5539384597cdfd` |
| walking map | `.../staging/bigdub_20261101_1355/tribemod/bigdub_collide.txt` | `cbed089b677f80559b2ca1250c61d478` |
| drone reel | `.../tribemod/drone_path.bigdub.txt` | `1a51f47e5ebb884e17eb681c66e8a1e0` |
| envs.txt (the 7 live lines + `Big Dub=/Game/Mods/BigDub/Maps/Environment_BigDub`) | `.../tribemod/envs.txt` | `8f7d54a55d4bf69455f6631da750fb4b` |
| build C3 APK (115,419,975 B) | `backup/mod2311_build/mod2311_C3.apk` | `5c2a9a99324a677665fd81a807c01fd9` |
| C3 libhook.so (541,480 B) | `backup/mod2311_build/mod2311_C3_libhook.so` | `dbdea5cf45fb3b87483efc9153db181f` |

**The OBB:**
- It is `patch_live.obb`'s 7 paks, copied byte for byte (each md5 re-checked against the live file), plus chunk 56.
- It was written the way `push_obb.sh` writes its merge (stored, sorted, comment "      2311"), by
  `tribe/stage_obb.py`.
- `patch_live.obb` is untouched (still `9236ca33`). The kits' own `make_obb.py` still writes the old "      2304"
  comment: don't use it.

**C3 = C2 + one line** (`backup/mod2311_build/diff_C3_vs_C2.diff`), in `dumper.cpp` `giant_lookup`'s SHOWS table:
- the row
  `{"bigdub","/Game/Mods/BigDub/MaterialInstances/MPC_BdShow.MPC_BdShow","MPC_BdShow"}`;
- nothing else: the C2 guard (`run_guarded(ensure_resolved,...)`) and everything else are unchanged;
- the same 7 compiler warnings as C2;
- `compare_apk.py`: only libhook.so and META-INF differ from the reference;
- its md5 line was added to `backup/mod2311_build/builds.txt`, so `launch_check.sh` can name it.

**Renders** (`claudedocs/bigdub_tribe/`, 1920 x 1080, from the kit's own level on the PC's renderer):
- what they show: the linear scene colour, sRGB-encoded, as the Quest shows unlit emissive (`r.MobileHDR=False`);
- the show state: `ShowLevel` 1, some bass;
- `bigdub_tribe_dj.png`: the DJ's view;
- `bigdub_tribe_crowd_from_stage.png`;
- `bigdub_tribe_ring_from_crowd.png`: from the FOH;
- `bigdub_tribe_drone.png`: the reel's high pass.

The screen is black in them: Tribe puts the video on it in game. They were taken before the far-creek trim; the trimmed
water isn't in any view.

## How it is built (each step stops on failure)

```bash
T=C:/Users/Chris/TribeUE/TribeXR/Scripts/Blender/bigdub/tribe
bash $T/make_site.sh                         # the site (the game generator's copy, Main Stage only) + Tribe changes + FBX, ~2 min
bash $T/crowd/run_crowd.sh --target 1500     # the crowd (Blender, GPU lock, waits for 8 GB free RAM), ~1.5 min
python -P -B $T/bd_collide.py $T/out/bigdub_collide.txt   # walking map: caps + walk check
python -P -B $T/bd_dronecheck.py             # drone reel check
PYTHONPATH=$T/gen python -P -B $T/tribe_budget.py
bash D:/TribeUE/MetaBigDub/TribeXR/Scripts/cook_bigdub.sh all     # Unreal build, cook (stops on a failed material), pack 56
bash D:/TribeUE/MetaBigDub/TribeXR/Scripts/render_bigdub.sh && python -P -B $T/hdr_to_png.py "<repo>/claudedocs/bigdub_tribe"
python -P -B $T/stage_obb.py C:/Users/Chris/TribeUE/paks_current/patch_live.obb <pak56> <out.obb>
bash backup/mod2311_build/tools/build_all.sh C3
```

**The pieces:**
- **The kit:** `D:/TribeUE/MetaBigDub/TribeXR`. Its uproject, Config, Build, Plugins and Binaries were copied from
  MetaHarvest; it has its own Content and Cooked.
- **The Unreal build:** `C:/Users/Chris/TribeUE/TribeXR/Scripts/build_bigdub.py`. The materials are the game's
  `build_bigdub.py`, copied verbatim, plus `tribe_code`.
- **The pictures:** `Scripts/bigdub_views.py`.
- **The generator copy:** `tribe/gen/`. The `TRIBE` changes are in `bd_site.py` `main()`. The output path is set in
  `bd_frame.py` and `bd_blender.py`. The CC0 textures are copied with their LICENSE and SOURCE files.

**Lessons:**
- **Collection path:** create the collection *in* `MaterialInstances`. The first build created it in the root and never
  saved it, and every material failed with "CollectionParameter has invalid Collection" in the cook only.
- **Renders:**
  - run the editor with `-ExecCmds="py ..."`. With `-ExecutePythonScript` it quits as soon as the script returns.
  - take scene captures as HDR scene colour. `SCS_FINAL_COLOR_LDR` with the tonemapper off came out black.
  - give a fresh editor about 60-90 s for its meshes and shaders to build before the captures are lit.
- **HISM trees:** they work through `SubobjectDataSubsystem` (`add_hism`) on a placed StaticMeshActor.

## Headset test (the interactive session, on the user's go)

1. **The OBB.** Run `bash scripts/push_obb.sh --env "Big Dub=/Game/Mods/BigDub/Maps/Environment_BigDub"
   C:/Users/Chris/TribeUE/paks_current/staging/bigdub_20261101_1355/pakchunk56-Android_ASTC_P.pak`.
   - First run it without `--push`: if the headset's OBB is still `9236ca33`, the dry run's merged md5 is `1e3d2a3b`.
   - Then run it with `--push`. Its `--env` adds the 8th menu box (EM_MAX is 8, so this is the last free box).
2. **The tribemod files.** Push `bigdub_collide.txt` and `drone_path.bigdub.txt` to `tribemod/` (the usual
   `/data/local/tmp` route).
   - **Re-seed lists:** copy both, and envs.txt with its Big Dub line, into `backup/tribemod_20261006/`, and add their
     names to `reseed.sh`'s list. Otherwise a re-seed drops them.
3. **Build C3.** Install it with `adb install -r backup/mod2311_build/mod2311_C3.apk`: replace only, never uninstall.
   - If Tribe's Restore App dialog comes up, press Close, never Restore.
   - Then run the usual launch check.
4. **Load the stage.** Pick Big Dub: `tribemod/active_env.txt` = `Big Dub`, then launch (the menu-press route is
   unconfirmed on 2311).
5. **The logs** (`adb logcat -d`) must show:
   - `[ENV] stages in the paks: 8/8 levels found`;
   - `[ENV] visuals: our screen 0x... is Tribe's backdrop now`;
   - `[GIANT] show bus: MPC_BdShow 0x... (load N), 19/19 parameters: the light show runs here`, and **not**
     `no show collection for stage folder 'bigdub'` (that means C3 isn't installed);
   - `[CLUB] walking map bigdub_collide.txt: 124 floors, 45 boxes, 222 circles, 1502 people, 1 spots (88880 bytes)`;
   - `[CLUB] on: 'Big Dub' is up`;
   - with `drone.txt` `mode=path`: `[DRONE] path: 9 shot(s), 106 s loop, from drone_path.bigdub.txt`.
6. **By eye:**
   - the frame rate (the other stages' 71-72 fps);
   - the darkness against the game's;
   - the jellyfish;
   - the VJ loops on the LED wall;
   - the lasers and beams on the beat;
   - the crowd dancing and making way;
   - walking down the back stairs, round the barrier's ends, into the crowd and out between the stones;
   - the drone reel.

## Not verified, and the risks (ranked)

1. **Frame rate.**
   - **The risk:** the triangles and draws are inside the budget, but the night shader costs more per pixel than the
     other stages' materials, and the 3 additive layers (beams, lasers, halos) cover much of the view at a drop.
   - **The knobs:** `BeamLevel`, `Haze`, `Mist` and `StarLevel` in `MPC_BdShow`. The hook doesn't write them, so set the
     defaults in `build_bigdub.py` `OWN_PARAMS` and rebuild.
   - **The next cut:** the crowd's near tier (899 tris a dancer).
2. **The show clock** (`Time + ShowOffset`) and the beat sync: **assumed** to match the hook's, as above.
3. **The crowd up close:** the tiers go by distance from the DJ (as on every stage), so walking into the back of the crowd
   shows the 23-triangle far dancers up close (`bigdub_tribe_ring_from_crowd.png`).
4. **Walking heights:** up to 28 cm off the drawn ground on the slopes, a limit of the hook's flat floors. A heightfield
   or ramp floor type in club.cpp would fix it.
5. **The renders:** they are the PC's GPU running the same shader math. The Quest's half-float paths and its sRGB
   framebuffer can still shift the darkness a little.
6. **Names and data, as flagged for the game (D:/VRDJ/docs/venues.md "BIG DUB"):** the festival's name, the real farm,
   the land cover classified from Esri imagery, and the OpenStreetMap credit. This is a stage for the user's own stream.
