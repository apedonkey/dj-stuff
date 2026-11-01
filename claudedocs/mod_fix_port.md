# Mod port to Tribe 0.12.6 (versionCode 2311): what changed, why, and how sure

2026-10-31. Built on the three maps (claudedocs/mod_fix_stream.md, mod_fix_selfie.md, mod_fix_halloween.md). Pieces:
the 720p stream and Twitch (priority 1), the selfie camera view (2), the Halloween stage (3). The selfie view and the
Halloween stage were ported by two subagents in their own copies (claudedocs/mod_fix_port_selfie.md,
claudedocs/mod_fix_port_halloween.md); the stream, the shared core, the merge, the build and the checks were done here.
Originals: backup/mod_fix_work/original/ (hook/*, the scripts as they were at 10:41, the tribemod config files).

Confidence: **H** = checked by a second route (disassembly, bytes, or structure) independent of the map's method;
**M** = derived from code or the map but not re-checked; **L** = a guess that only the headset can settle.

## 0. Shared facts every piece depends on

| Fact | Result | How checked | Conf. |
|---|---|---|---|
| The toolchain still makes the shipped 2304 hook | Rebuilding the untouched sources gives libhook.so md5 b67ec69b, 473,904 B, 7 warnings: byte-identical to the 2304 mod's (combo22) | NDK r26d, the GUIDE's command line | H |
| add_needed.py moves 2311's libUnreal.so by exactly +0x1000 | .text and .rodata byte-identical after the shift; all 1,575,432 RELR pointers moved and their contents +0x1000; 14,850 symbol relocations and 122 defined symbols +0x1000; .data.rel.ro/.got/.data identical apart from relocated slots; GUObjectArray's GOT slot 0x8679738 holds 0x88A6150 | backup/mod_fix_work/tools/verify_skew.py + llvm-readelf -r / --dyn-syms diff. (LIEF's .bss *section header* says 0x87F5348; that is bookkeeping: the RW PT_LOAD that holds .bss moved +0x1000 with the same memsz, and the loader uses only program headers) | H |
| ProcessEvent (2311) = store vaddr 0x19E8EB4, runtime 0x19E9EB4 | Its head bytes in the patched lib are `fd7bbaa9 fc0b00f9 fd030091 fa6702a9`, the 2304 PE's first four words; the address is UObject vtable slot 78 in all 4,068 vtables that hold it (2304: 0x1857DD4 in all 3,828, slot 78) | vtable structure scan (UE builds without RTTI: header = two zero words) | H |
| The per-frame driver | All ticks (stream_tick, camview_tick, drone_update, giant_tick, env_menu_tick, ...) run from our own SkeletalMeshActor's ReceiveTick, which spawns only after `auto_load` finds `AvatarBodyMesh` under `ReadyPlayerMeComponent` and the avatar loads. Both names are created by identical constructor code in both builds (`CreateDefaultSubobject(TEXT("AvatarBodyMesh"))` into this+0x260, same field layout; another constructor creates `ReadyPlayerMeComponent`) | xrefs of the UTF-16 literals + disassembly in both libs | M (code identical; the live path is not observed) |

## 1. The stream (hook/stream.cpp): priority 1

Every value the map gave was re-derived from the 2311 library by disassembly, and each 2304 counterpart reproduces the
shipped constant under the +0x1000 rule.

| # | Change | Evidence (2311 store vaddr) | Conf. |
|---|---|---|---|
| S1 | `ST_ENGINE_OFF` 0x550 -> **0x570** | call start: `bl …; str x0,[x19,#0x570]` at 0x5A6F250 (2304: `str x0,[x19,#0x550]` at 0x50C0A80, same neighbours); the re-send reads `ldr x20,[x0,#0x570]` | H |
| S4 | `ST_DIMS_VADDR` 0x7F02DC4 -> **0x8B092C4** | getter 0x5A7ECB0 = `adrp 0x8b08000; add #0x2c4; ldr x0,[x8]; ret` (2304 getter -> 0x7F01DC4); both re-sends build their config from it | H |
| S5 | `ST_DIMS_OFFCALL_VADDR` 0x7F02740 -> **0x8B08CF0** | capture tick 0x5A3CF1C: `adrp 0x8b07000; add #0xcf0; ldp w0,w10; ldr x8,[x19,#0x888]; ldr x9,[x8,#0x300]` (2304: `#0x740`, same sequence) | H |
| S6 | `ST_TRIBE_W/H` 848x480: **unchanged, now verified** | The map found no writer (L/M). The writer is a static initializer: `add x19,…#0x2c0`, then the pre-index `str xzr,[x19,#0x70]!` makes x19 = 0x8B08330, then `mov x10,#0x350; movk x10,#0x1e0,lsl#32; stur x10,[x19,#-0x6c]` writes 848 \| 480<<32 to 0x8B082C4. 2304: `[x19,#0x48]!` then `-0x44` writes 0x7F01DC4, matching the device log's 848x480 | H |
| S7 | +0x888 / +0x914 / rate 15: unchanged | the 2311 capture tick uses 0x888, 0x914, 0x880, 0x300, 0x138, 0x13c, 0x918; 0x23C9B78 is `mov w0,#15; ret` | H |
| S2/S3 | Agora slots and heads: unchanged | libagora-rtc-sdk.so md5 81b006ac in both; heads at 0x180F150 / 0x180F31C match | H |
| S8 | `ST_TRIBE_SEND_VADDR` 0x50D4CE4 -> **0x5A81E7C**, new `ST_TRIBE_SEND_HEAD` `ff4302d1 fd7b06a9 fd830191 f65707a9` | disassembly of 0x5A80E7C: engine +0x570, channel std::string +0x780, uid +0x798, +0xa10 / +0x960 / +0x958, then +0x928 with the pair and the .rodata constants 0x4C4EC0 / 0x4C9350. Takes only x0, returns nothing. The bytes at runtime address 0x5A81E7C in the patched lib = the head | H |
| S9 | **new hook** on Tribe's role-change re-send, `ST_TRIBE_ROLE_VADDR` **0x5A82F18**, head `ffc301d1 fd7b05a9 fd430191 f44f06a9` | disassembly of 0x5A81F18: role byte +0xa40 -> flags +0x548 (0 or 3), enableLocalAudio(false) (+0x190), then (flags bit 1 only) Tribe's own +0x928 with 15 fps / standard. x0 only, void. Runtime bytes = the head | H (what it does), M (when it fires) |
| - | Hook mechanics | And64InlineHook overwrites at most 5 instructions: S8 sub/stp/add/stp/stp, S9 sub/stp/add/stp/mrs; none PC-relative, none a branch target | H |

Code changes (backup/mod_fix_work/stream/stream.cpp, merged into hook/stream.cpp):
- the constants above, with the 2304 value in each comment, and a 2311 paragraph in the header comment;
- `st_hook_one()` hooks one re-send after its 16-byte head check; `st_hook_send()` now hooks both (log lines name them
  "join" and "role change");
- a second counter `g_stTribeRoles`; `stream_tick` treats either counter like the old one (ours again about 1 s later,
  only while live) and logs "Tribe sent its own encoder settings (it joined; #n)" or "(a role change; #n)".

Not changed on purpose: the protocol-version global and `/agora/token2` (2311's own lib sends "4"), the native Go
Live menu, the Twitch login flow, the struct layout (same Agora library).

## 2. The shared core (hook/dumper.cpp, edited here)

| Line(s) (original) | Before -> after | Why | Conf. |
|---|---|---|---|
| 35-37 | RVA_NamePool 0x07C632C0 -> 0x0884D640; RVA_GUObjectArray 0x07CBADD0 -> 0x088A6150; RVA_GUObj_GOTslot 0x07AA59E8 -> 0x08679738 (runtime values) | map E3-E5; the GOT slot's content was read from the file (0x88A5150 -> 0x88A6150 after the shift); GUObjectArray - FNamePool = 0x58B10 in both builds. Only the dump diagnostics use these three; the live resolve uses params.txt or the scans | H (slot), M (pool, from the maps' code matching + the distance invariant) |
| 175, 267 | the two scans' window `g_base+0x08000000` -> `g_base+0x0C000000` | **missing from all three maps:** 2311's FNamePool and GUObjectArray sit at runtime +0x884D640 / +0x88A6150, past the old 128 MB window, so without a correct params.txt the hook could never find them (the selfie map's "delete np= and let the scan find it" would have failed) | H |
| 912 | params.txt `np=` is now checked: FName 0 must read "None", else it logs and scans | a wrong np= had no fallback. The re-seed restores backup/reseed_20261001/params.txt, which still has the 2304 values; with this check and the wider scans the hook heals itself (ga= was already validated, with a scan fallback) | H (logic) |
| 867 | RVA_PE_GHIDRA 0x1857dd4 -> 0x19e8eb4 (PE_SKEW 0x1000 kept) | section 0; the hook's prologue check (a9ba7bfd) still guards it | H |
| 1183-1187 | the pawn and its tracked components: `find_live(…,"TribePawnBP_C")` -> the local pawn (camera manager -> PCOwner -> Pawn, engine properties), else the first live object of class exactly `TribePawn` or `TribePawnBP_C`; then the pawn's own properties `Camera`, `VROrigin`, `MotionControllerL/R` (class checked), else `find_live(name, class, "TribePawn")` | 2311 has no TribePawnBP_C; ATribePawn declares these four as C++ properties (map T20 / selfie 10). Exact class match: "TribePawn" is also a substring of other 2311 names (ETribePawnAttachMode, TribePawnCameraInput). g_camComp is what drone_update needs, and g_pawn is the show bus's world context | H (names), M (that the live objects match at runtime) |
| new, before spawn_iso_actor; 3237; 3244; 3817 | **a fallback per-frame driver.** `follow_wire()` holds the pawn/component lookup (spawn_iso_actor calls it as before). New `fallback_wire()` (game thread, on request): if no avatar actor exists ~90 s after the engine resolved, the pawn becomes the ticker (`g_fallbackTicker`), and the PE dispatch now runs when either driver exists (`g_isoActor‖g_fallbackTicker`). Re-tried every 30 s until a pawn is found, and again if that pawn dies; our actor still takes over when it spawns | Every per-frame function (stream_tick included) ran only from our avatar actor, which spawns only after the custom avatar loads. If that chain breaks on 2311 the stream's 720p would silently never apply. Each tick function checks its own needs (follow_update returns without our actor, giant_tick without the pawn, ...), so ticking them from the pawn is safe; UE 5.4's AActor::Tick sends ReceiveTick through PE for any ticking actor. Strictly additive: the normal path is unchanged | M (the pawn's tick reaching PE is engine behaviour, not observed on 2311) |
| 3393, 3463 | `find_live_class_sub("BP_SelfieStick_C")` -> `("SelfieStick")` | matches BP_SelfieStick_C and TribeSelfieStick; the only 2311 class with that substring is ATribeSelfieStick | H |
| 3471 | **left on purpose** at `TribePlayerControllerBP_C` (comment added) | it only feeds `drone.txt target=auto`, which writes the controller's raw +0x974 (unverified on 2311). Leaving the 2304 name keeps that write impossible on 2311; the user runs mode=path (selfie target). The selfie map suggested the rename | H (that it's safe) |

## 3. The paks and the patch OBB

- **No re-cook.** The kit at D:/TribeUE/MetaHw was not used (0 minutes). Re-derived here, independent of the map:
  pakchunk54's raw bytes (entries stored uncompressed) name only /Script/CoreUObject, /Script/Engine,
  /Script/NavigationSystem, /Engine/EngineMaterials/WorldGridMaterial, /Engine/Maps/Templates/OpenWorld and
  /glTFRuntime/M_Unlit_glTFRuntimeBase: nothing from /Script/TribeXR, no /Game path outside Mods/Halloween. Pak v11.
  (The map's list lacked /Engine/Maps/Templates/OpenWorld; the map found every engine-side OBB file SHA1-identical
  between the builds, so it resolves as it did on 2304.) The same engine build runs both (map P2).
- None of the seven mod paks overrides a stock path: every file is under TribeXR/Content/Mods/ or is the chunk's own
  shader archive (scripts/pak_list.py over the live 2304 patch OBB, 1,632 files). Mounting them can't touch Tribe's
  2311 content. Only chunk 54's dependencies were checked; the other six stages load only when picked.
- **backup/mod_fix_candidate/patch.2311.com.TribeXR.TribeXR.obb**: the live 2304 patch OBB (pulled 09:41 today, md5
  ce16dd5c) with the zip comment `"      2304"` -> `"      2311"`, nothing else (cmp: 2 bytes differ). 817,060,647 B,
  md5 9236ca337c41d98aa547c13091ddf4cb; testzip clean; seven stored paks (chunks 50, 53, 54, 55, 57, 58, 59). The
  store main.2311 OBB carries the same `"      2311"` comment.

## 4. The selfie camera view (hook/camview.cpp): subagent, reviewed and merged here

Full record: claudedocs/mod_fix_port_selfie.md. In short:
- The menu is found as `TribeVisualsMenuWidget` (2311) or `W_VisualsMenu_C` (2304), with em_find_live's filters (H).
- The handler scan maps `HandleSelfieCamera` -> 0 and `HandleCamera<d>` -> d (exact names), keeps 2304's `BndEvt__`
  rule, skips HandleCameraToggle / HandleResetSelfie, and walks parent classes up to UserWidget (H for the names; the
  subagent traced each HandleCamera<d> to its button's OnClicked dynamic delegate, which goes through ProcessEvent).
- **Build timing fix** (missed by the map): 2311 builds the menu's widgets in C++ (RebuildWidget), so camview now waits
  until the menu's SelfieCameraButton is set and gives each new menu object its own 3 tries; the old code could spend its
  3 tries before the buttons existed (M).
- The 2311 menu's tree, read from its C++ builder: all eight camera buttons sit straight in one VerticalBox
  (VerticalBox_117), camview's existing one-row case, so Crowd is cloned from CameraButton8 (M: the clone path has never
  been seen to run on either build).
- dumper.cpp needs (applied in section 2): the SelfieStick needle and the pawn lookup.

## 5. The Halloween stage: subagent, reviewed and merged here

Full record: claudedocs/mod_fix_port_halloween.md (per-change confidence, library addresses, expected log lines). In
short, every lookup tries the 2311 C++ name first and the 2304 Blueprint name second:
- game state `TribeMainGameState`; visuals manager `TribeVisualsManager`; rig exactly `TribeRig`; decks
  `/Script/TribeXR.TribeDeck` (functions from the class's own list); mixer `TribeMixerSliderBase`/`TribeMixerKnobBase`
  with `TribeChannelVolumeSlider`/`TribeChannelColorKnob` by class chain; play buttons `TribePlayButton` matched to a
  deck through its `Deck` property; `SelfieStick` in intro.cpp and head.cpp (H for names).
- SetupEnvironmentBackdrop's 2311 signature: our screen (checked to be a StaticMeshActor) plus the manager's own three
  lights (soft pointers resolved as FWeakObjectPtr::Get does, class-checked) and its LightDimFactor; if anything
  doesn't resolve it does not call and retries; re-registers (at most 6 times) if the Void registers its backdrop after
  ours (M).
- The menu (T6/T7): the live widget's `EnvironmentList` property; a press is seen as `UserWidget.OnMouseButtonDown` on
  a box whose `Skin` is ours, or `TribeSkinItemWidget.OnSkinApplied` right after a press; labels come from the list's
  `EntryWidgetPool.ActiveWidgets` once a second (M; the click itself is the riskiest new path, see section 9).
- If the Void's backdrop isn't found by name, the manager's `BackdropStaticMeshActor` is hidden, only if it sits in the
  Void's level (M).
- club.cpp: comments and one log line; walking falls back to key polling as before (H).
- Not ported (out of scope): the avatar/skin menu, the dump diagnostics, TribeControllers_C, `intro_deck.txt`'s 2311
  call (PlayNetSynced now takes a 152-byte struct; needs a headset capture).

## 6. The merge

- Base backup/mod_fix_work/original/hook, pieces in backup/mod_fix_work/{stream,core,selfie,halloween}/.
  `git merge-file --diff3` of dumper.cpp (original, core, halloween): 0 conflicts. The other files came from one piece
  each. Result: backup/mod_fix_work/merge/ (copied into hook/ after the checks).
- The stream path checked after the merge: stream.cpp identical to the ported copy; stream_tick in both tick paths;
  stream_poll in the poll loop; the new dispatch condition; the new constants.
- The merged tree compiles with the same 7 warnings as the shipped 2304 build, no errors.

## 8. Tests that don't need the headset (all run 2026-10-31)

| Test | Result |
|---|---|
| tests/gait_test.cpp (MSVC 2019) | ALL CHECKS PASS (10 checks) |
| tests/club_collide_test.cpp on the Graveyard walking map (halloween_collide.txt) | parse ok (34 floors, 122 boxes, 4,549 people); 470,830 states reachable from the decks, 0 with no way back |
| tests/intro_ride_test.cpp on intro.halloween.txt | parse ok, 160 keys, 0 lines not understood; worst key yaw vs spline 2.97 deg; speed 5.95-6.07 m/s |
| tests/usmap_test.cpp + its UAssetAPI read-back (dotnet) | diff empty: PASS |
| tests/test_scan_strings.py | OK |
| tests/install_tribemod_test.sh (mock adb) | PASS, 12/12 |
| tests/fix_login_test.sh (mock adb) | **no valid result**: 9 passed, 26 failed, but another session rewrote scripts/fix_login.sh (10:57) and this test (11:09) while it ran (started 11:05). This port changes neither file |

These tests cover the walking rules, the gait, the intro ride, the .usmap writer and the install scripts; none covers
the code this port changed (the hook's reflection and hooks only run inside Tribe).
