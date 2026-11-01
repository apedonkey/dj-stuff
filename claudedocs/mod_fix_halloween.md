# Graveyard Shift (Halloween stage) on Tribe 0.12.6 (2311): port map

Mapping only, 2026-10-31. Nothing was built, pushed or installed. Inputs: the mod's 2304 APK and OBBs in
`backup/tribemod_20261031_preupdate/`, the store 2311 APK and OBB in `backup/tribe_2311/`, the store 2304 `libUnreal.so`
in `backup/mod_halloween_work/lib2304/`, and `hook/`. Everything below was read from those files in memory.

## Answer first

1. **The Halloween pak loads on 2311 as it is. No re-cook.** 2311 runs the same engine build as 2304 (Meta's UE 5.4.4 fork,
   OVRPlugin 1.103.0). Every engine-side file in the OBB is byte-identical, and so are the reflected layouts of all the
   classes the pak uses. The pak format is the same (v11, unencrypted, no signatures, no IoStore).
   The patch OBB must be renamed `patch.2311.com.TribeXR.TribeXR.obb`, and its zip comment must become `"      2311"`.
2. **The hook is what breaks.** Tribe 0.12.6 converted its Blueprints to C++. The OBB went from 577 `BP_*`/`W_*`
   packages to 1. `TribePawnBP`, `TribeMainGS`, `TribeControllers` and `TribeGameInstanceBP` are gone too. Every Blueprint
   path or class name the stage code looks up (BP_Deck_C, the mixer BPs, W_VisualsMenu_C, W_SkinItem_C,
   BP_EnvironmentSkin_C, BP_Rig_C, BP_TribeVisualsManager_C, TribePawnBP_C, BP_SelfieStick_C, BP_PlayButton_C) now
   resolves to nothing. Native classes with the same member names replace them; the table below maps each one.
3. **Four things need new code, not just new strings:**
   - the environment-menu click path (the Blueprint events it caught are now C++ virtuals, invisible to ProcessEvent);
   - `SetupEnvironmentBackdrop`, which has a new signature;
   - `GetTribeEquipmentBase` on the play button, which is gone (the button has a `Deck` property instead);
   - the walking code's Blueprint stick events, which are gone (the code's own `GetInputAnalogKeyState` fallback should
     cover this).
4. **The engine addresses moved, and all four are mapped (high confidence):** ProcessEvent, FNamePool, GUObjectArray and
   its GOT slot.

Targets mapped: 39 (E1-E7 engine addresses and rules, P1-P6 pak and OBB, T1-T26 Tribe-side names). Confidence: high for the
addresses, the pak verdict and the name mapping; medium-to-low for the runtime behaviour of the menu and backdrop
changes (not testable offline). Port estimate: about 10-16 hours, mostly on-device iterations (section 8).

## 1. How things were matched

- **Pak entries:** each FPakEntry header carries a SHA1 of the stored bytes. I compared all 10,802 (2304) and 10,230
  (2311) entries of the main OBBs. 9,319 are identical and 110 changed. 1,373 were removed and 801 added.
- **Reflection:** I parsed UHT's compiled-in tables straight from both `libUnreal.so` files (RELR: pointer slots hold
  target addresses). The chain is `FClassRegisterCompiledInInfo` (UTF-16 class name) → `FClassParams` (by StaticClass
  pointer) → `PropertyArray` / `FunctionLinkArray`. Function parameters came from `FFunctionParams`, and enums from
  `FEnumeratorParam`. That gave 4,122 classes in 2304 and 4,727 in 2311.
- **Code addresses:** masked byte signatures. ADRP/ADR/B/BL/B.cond/CBZ/TBZ/LDR-literal immediates and the low-12 page
  offsets were masked. 24- and 64-word windows were taken from the store 2304 `.text` and searched in the store 2311
  `.text`. Each needle was unique in 2304 too.
- **Globals:** every 2304 ADRP+ADD/LDR that reaches the global was located. Its surrounding 24 words were matched in
  2311, and the ADRP+ADD at the matched spot was decoded. A second route was used for each (section 3).

Address frames used below:
- **store vaddr:** the ELF vaddr in Tribe's unmodified `libUnreal.so`. Ghidra = store vaddr + 0x100000.
- **runtime RVA:** what the hook adds to `g_base`. This is the vaddr in the lief-patched .so that `hook/add_needed.py`
  writes. Verified on 2304: the patched `.text` is byte-identical to the store `.text` but sits at +0x1000 (0x1446000 →
  0x1447000). Store PE 0x1857DD4 = patched 0x1858DD4, prologue `a9ba7bfd`. That +0x1000 is the hook's `PE_SKEW`, and
  it's why `params.txt` has `ga=0x07CBBDD0` while dumper.cpp has `0x07CBADD0`.
- **2311 runtime RVAs** below assume add_needed.py shifts 2311 by the same +0x1000. Check this after patching by
  comparing the `.text` section vaddr of the patched .so with 0x15D7000 (the store value).

## 2. The Halloween paks

| # | Target | 2304 | 2311 | How matched | Conf. | Port change |
|---|---|---|---|---|---|---|
| P1 | Halloween pak | `pakchunk54-Android_ASTC_P.pak` in `patch.2304.com.TribeXR.TribeXR.obb` (181,279,034 B, pak v11, mount `../../../`, 291 files, stored uncompressed). 132 packages: `Mods/Halloween/Maps/Environment_Halloween.umap`, 27 MIs + `MPC_HwShow`, 22 materials, 47 meshes, 34 textures | Carry over unchanged | Imports read from every .uasset/.umap header in the pak (name maps): only `/Script/CoreUObject`, `/Script/Engine`, `/Script/NavigationSystem`, `/Engine/EngineMaterials/WorldGridMaterial` and `/glTFRuntime/M_Unlit_glTFRuntimeBase` (12 assets). **No `/Script/TribeXR`, no `/Game/...` outside the mod, no Blueprints.** Classes used: World, Level, Model, WorldSettings, StaticMeshActor/Component, SpotLight/Component, StaticMesh, Material, MaterialInstanceConstant, Texture2D, MaterialParameterCollection, NavigationSystemModuleConfig | high | none |
| P2 | Engine compatibility (unversioned property data and frozen shader maps) | Meta fork `oculus-5.4.4-release-1.103.0-v71.0` (NOTES 3p; `D:/TribeUE/MetaHw/TribeXR/TribeXR.uproject` description) | **Same engine.** (a) All engine-side OBB entries are SHA1-identical: 2,313 `Engine/Content`, 22 `Engine/Config`, every `Engine/Plugins` group, `GlobalShaderCache-VULKAN_ES3_1_ANDROID.bin`, `ShaderArchive-Global-…`, `WorldGridMaterial`, all 80 glTFRuntime files incl. `M_Unlit_glTFRuntimeBase`, all 95 MetaXR files. (b) Of the 4,019 non-Tribe reflected classes present in both builds, 4,018 have identical property/function lists and offsets. The one that differs is `UBeatportTrackHandle`, a Tribe plugin class the pak doesn't use. Every class in P1 is SAME, e.g. UMaterial 121/121 props, UPrimitiveComponent 115/115. (c) `libOVRPlugin.so` identical (CRC 0a01546a, "1.103.0") | Three independent routes | high | none: **no re-cook**. If one is ever wanted, the same kit and engine (`D:/MetaUE54`, `D:/TribeUE/MetaHw`) apply unchanged |
| P3 | Pak container format | v11, index unencrypted, zero key GUID, no `.sig`, no `.utoc/.ucas` | Same for all four 2311 paks (v11, unencrypted, zero GUID, Oodle for Tribe's own entries; no `.sig`/`.utoc`/`.ucas` in the OBB) | `scripts/pak_footer.py` + OBB zip listing | high | none |
| P4 | Chunk shader library | `ShaderArchive-TribeXR_Chunk54-SF_VULKAN_ES31_ANDROID-VULKAN_ES3_1_ANDROID.ushaderbytecode` inside the pak | Same name scheme (`ShaderArchive-TribeXR_Chunk0/1-…` in 2311); the global archive is identical, so the shader format and compiler match | Pak listings | high | none |
| P5 | Patch OBB name | `patch.2304.com.TribeXR.TribeXR.obb` (zip comment `"      2304"`, as on `main.2304`) | `patch.2311.com.TribeXR.TribeXR.obb` with comment `"      2311"` (the store `main.2311` OBB carries `"      2311"`) | Derived from the naming pattern and the observed comments. I did not read UE's Java OBB check | medium-high | Rename and re-comment. `scripts/push_obb.sh:25,71`, `reseed.sh:23,35,40`, `install_tribemod.sh:71`, `fix_login.sh:31-34,132` hard-code 2304 |
| P6 | Chunk IDs | mod chunks 50, 53, 54, 55, 57, 58, 59 | 2311 ships only chunks 0, 0optional, 1, 1optional | Listing | high | none (no collision) |

Not read: 2311's `TribeXR/Config/DefaultEngine.ini` (16,463 → 21,215 B) and `DefaultGame.ini` changed. They are
Oodle-compressed, and no Oodle decoder was available. A pak-mount or pak-signing setting there would show up at the
first launch as `FileExists(pak inside the patch OBB)=0` in the hook's `[ENV] diagnose` log. P3 makes signing
unlikely: Tribe's own paks have no `.sig` files.

## 3. Engine addresses (the hook needs these for everything, the stage included)

| # | Target | 2304 store vaddr → runtime RVA (hook) | 2311 store vaddr → expected runtime RVA | How matched (2 routes each) | Conf. | Port change |
|---|---|---|---|---|---|---|
| E1 | `UObject::ProcessEvent` | 0x01857DD4 → 0x01858DD4 (`RVA_PE_GHIDRA`+`PE_SKEW`, dumper.cpp:867) | **0x019E8EB4 → 0x019E9EB4** (Ghidra 0x01AE8EB4) | (1) Unique masked-signature match, 24 and 64 words. (2) The first 4 words are byte-identical (`a9ba7bfd f9000bfc 910003fd a90267fa`), and `CallFunction` (E2) sits the same 0x1228 bytes before it in both builds | high | `RVA_PE_GHIDRA=0x19E8EB4` (keep `PE_SKEW=0x1000` if the +0x1000 check passes) |
| E2 | `UObject::CallFunction` (calib only, dumper.cpp:401) | 0x01856BAC | 0x019E7C8C | Unique 24-word signature | high | diagnostic constant only |
| E3 | FNamePool | 0x07C622C0 → 0x07C632C0 (`RVA_NamePool`, `params.txt np=`) | **0x0884C640 → 0x0884D640** | (1) 49 code refs in 2304; the 40 tried all matched uniquely and all give this address. (2) GUObjectArray − FNamePool = 0x58B10 in both builds | high | `params.txt np=0x0884D640`, `bo=0x40` unchanged (same engine); `RVA_NamePool=0x0884D640` |
| E4 | GUObjectArray | 0x07CBADD0 → 0x07CBBDD0 (`params.txt ga=`; dumper's `RVA_GUObjectArray` holds the store value) | **0x088A5150 → 0x088A6150** | (1) 223 code refs in 2304; of the 40 tried, 32 matched uniquely, and all 32 give this address. (2) The GOT slot (E5) holds exactly this address | high | `params.txt ga=0x088A6150`. Put runtime values in `RVA_GUObjectArray`/`RVA_GUObj_GOTslot` too: in 2304 both held store values, 0x1000 off, so only `params.txt` made them work |
| E5 | GOT slot holding &GUObjectArray | 0x07AA59E8 (store) | 0x08678738 → 0x08679738 | 627 code refs in 2304; the 40 tried all match and agree. The slot's file content is 0x088A5150 (the 2304 slot likewise holds 0x07CBADD0) | high | `RVA_GUObj_GOTslot` |
| E6 | Engine struct offsets (`OFF_*` dumper.cpp:103/226/914, `FF_*`/`FP_*`, UFunction ParmsSize +0xB6 / RetValOffset +0xB8, UField::Next +0x28, FNamePool blocks +0x40) | as in 2304 | unchanged | Same engine (P2); identical reflection for every engine class | high | none |
| E7 | Per-frame driver: the mod actor's `Actor.ReceiveTick` through ProcessEvent (dumper.cpp:3235-3240) | engine behaviour, observed on 2304 | expected unchanged (engine identical) | Inferred from P2 | medium | none. Confirm with the `[LOAD] iso:` / follow logs. The fallback ticker `TribePawnBP_C` becomes the native pawn (T20) |

The stream addresses in `stream.cpp` (0x7F02DC4, 0x7F02740, 0x50D4CE4) and `hook.cpp`'s avatar dispatcher/choke are
not part of this piece. `libagora-rtc-sdk.so` is byte-identical between the builds (CRC 33bc1e05).

## 4. Loading the stage (env menu: dumper.cpp:2170-2500, 3126-3204, 3652-3727)

Class names below are the UClass FNames the hook compares: the C++ name without its A/U prefix. Object paths are
`/Script/TribeXR.<Name>`. Offsets are 2311 property offsets from the reflection tables; the hook looks them up by
name at runtime, so they are for checking only.

| # | 2304 target (hook line) | 2311 match | Conf. | Port change |
|---|---|---|---|---|
| T1 | `/Script/TribeXR.TribeGameState.SetEnvironment` (3676), 1-byte enum param | Unchanged: `ATribeGameState.SetEnvironment(Environment: enum)`, same flags 0x4020401. 2311 adds `SetEnvironment_ShowLoadingScreen` and `bEnvironmentLoadingScreen`, so a loading screen may now run during step 1 | high | none. Watch the EM_WAIT_BASE timing (3-8 s) |
| T2 | `ETribeEnvironmentType` "Void" (3686-3688) | Unchanged: None=0 Lounge=1 Desert=2 **Void=3** Lodato=4 PolygonCity=5 HipHop=6 Passthrough=7 HotelSelina=8 Pioneer=9 VideoSphere=10 (FEnumeratorParam tables, both builds) | high | none |
| T3 | Game state's environment property, + the native fallback `+0x308` (3159) | `ATribeGameState.CurrentEnvironment` is still an EnumProperty at **0x308** (OldEnvironment 0x309) | high | none |
| T4 | Game-state class fallback `"TribeMainGS_C"` (2240) | `ATribeMainGameState` → `"TribeMainGameState"`. The primary route, `GameplayStatics.GetGameState`, is engine and unchanged | high (name) | string |
| T5 | `/Game/Visuals/Skins/Environment/BP_EnvironmentSkin.BP_EnvironmentSkin_C` (3694): the list item class we spawn | `UTribeEnvironmentSkin` (`EnvironmentType` enum @0xA0) → `/Script/TribeXR.TribeEnvironmentSkin` | high (name), medium (spawn + identity copy still enough for Tribe's native list) | path. `em_copy_identity` copies POD fields generically, so it should carry over |
| T6 | `W_SkinItem_C` box: `OnListItemObjectSet`, `OnMouseButtonDown` caught in ProcessEvent (3695-3696) | `UTribeSkinItemWidget` (`Skin` @0x2F0, `NameText` @0x390, `bSelected`). **Neither event is a UFUNCTION any more.** Its UFUNCTIONs are ApplySkin, UnlockAndApplySkin, InitSkinItem, SetSelected, Refresh, OnSkinApplied and others | high (names), **unknown (new click path)** | new code. Find which UFUNCTION a click sends through ProcessEvent: retarget the `skin_trace` flag (dumper.cpp:2061-2081) to `TribeSkinItemWidget` / `Tribe*Skin` and click on device. Dynamic-delegate handlers are visible to ProcessEvent; native list callbacks are not. Fallback until then: `tribemod/active_env.txt` (auto re-apply, 3716-3721) or `env_autotest` (3722-3725) load the stage with no click |
| T7 | `W_VisualsMenu_C` + its `EnvironmentList` UListView + the `BndEvt__W_VisualsMenu_EnvironmentList_…` event (3697, 3704) | `UTribeVisualsMenuWidget` with **`EnvironmentList` @0x430** (also `EnvironmentSkins` @0x520, `BuildEnvironmentSkinWidgets`, `ShowEnvironments`). The BndEvt function is gone | high (names), medium (widget built in C++: subobject names unknown) | Find the live `TribeVisualsMenuWidget` and read its `EnvironmentList` property, instead of matching an object name/outer. Drop the BndEvt lookup |
| T8 | `ListView.AddItem` / `GetIndexForItem`, `GameplayStatics.SpawnObject`, `TextBlock.SetText`, `KismetTextLibrary.Conv_StringToText` (box creation and labels) | Unchanged (UListView 20/27, UTextBlock 16/16 identical). The label target `NameText` is now a native TextBlock property @0x390 | high | none |
| T9 | `BP_Rig_C` (3710, `find_live_class_sub`) | `ATribeRig` → `"TribeRig"` (props `Decks`, `Console`, `MixerScreen`, funcs `GetDeck`, `GetDJTransform`, …) | high | string. Make it an exact class match: `"TribeRig"` is a substring of `"TribeRigSkin"` |
| T10 | `BP_TribeVisualsManager_C` (2333) | `ATribeVisualsManager` → `"TribeVisualsManager"` | high | string |
| T11 | `…SetupEnvironmentBackdrop(BackdropMesh, ChromaKeyBackdropMesh)` (2334-2349, Blueprint) | **Signature changed:** `SetupEnvironmentBackdrop(BackdropMesh: Object @0, InBoothSpotlight: Object @8, InBackdropSpotlight: Object @16, InRoomSkyLight: Object @24, InLightDimFactor: double @32)`, ParmsSize 40. The manager now stores `BoothSpotlight` (soft ptr @0x720), `BackdropSpotlight` (@0x748), `RoomSkyLight` (@0x770), `LightDimFactor` (@0x7A8) and `BackdropStaticMeshActor` (@0x2D0) | high (signature), **low (behaviour with our values)** | new code. After the Void is in, read the manager's three lights and dim factor (resolve the soft pointers' weak part) and pass them back with our `SM_DinoVisualScreen` actor. As written, the hook would pass nulls (`oC<0` skips the chroma param), and whether Tribe's native code null-checks is unknown: a possible crash |
| T12 | `/Game/Environment/Materials/MPC_VideoBackdrop` (`StretchMode`, `Tile`) (2298) | Present, SHA1-identical | high | none |
| T13 | The Void's screens: StaticMeshActors `SM_BackdropScreen`, `SM_BackdropScreen_ChromaKey` in `Environment_Void` (3711-3715) | **`Environment_Void.umap`/`.uexp` changed in 2311.** Oodle-compressed, actor names not read | **unknown** | Check on device: the hook logs `[ENV] Void SM_BackdropScreen = 0x…`. If the names changed, hide `ATribeVisualsManager.BackdropStaticMeshActor` (@0x2D0) instead |
| T14 | DJ rig position in the Void (the stage, `halloween_collide.txt`, `camview.halloween.txt` and `intro.halloween.txt` all assume the rig at the world origin) | Void map changed, so not confirmed | unknown | Compare the `[ENV] DJ rig: loc=` and `Void SM_BackdropScreen: loc=` lines from the first 2311 load against a 2304 log |
| T15 | Engine UFUNCTIONs: `LevelStreamingDynamic.LoadLevelInstanceBySoftObjectPtr`, `LevelStreaming.IsLevelLoaded/IsLevelVisible/SetShouldBeLoaded/SetShouldBeVisible`, `Actor.SetActorHiddenInGame/K2_GetActorLocation/Rotation/GetActorScale3D/GetActorBounds`, `GameplayStatics.GetGameState/GetCurrentLevelName/GetTimeSeconds`, `BlueprintPathsLibrary.FileExists/ProjectContentDir`, `KismetSystemLibrary.MakeSoftObjectPath/Conv_SoftObjPathToSoftObjRef`, `LightComponent.SetIntensity` (lights.txt), `PrimitiveComponent.GetMaterial` | All identical (ULevelStreamingDynamic 2/2, ULevelStreaming 26/14, AActor 89/140, UGameplayStatics 0/139, UKismetSystemLibrary 0/276, ULightComponent 34/26) | high | none |
| T16 | `envs.txt` row `Graveyard Shift=/Game/Mods/Halloween/Maps/Environment_Halloween`, the `SHOWS` row `halloween → /Game/Mods/Halloween/MaterialInstances/MPC_HwShow` (2554), `em_active_folder` → `"halloween"` | Unchanged: they name the mod's own pak content | high | none |

## 5. Light show (dumper.cpp:2546-2600 show bus, 2702-2768 mixer, 2853-2916 decks)

| # | 2304 target | 2311 match | Conf. | Port change |
|---|---|---|---|---|
| T17 | Show bus: `MPC_HwShow`'s 19 scalars via `KismetMaterialLibrary.SetScalarParameterValue`, `GetTimeSeconds` as the clock | Unchanged (own pak; UKismetMaterialLibrary 5/5 and UMaterialParameterCollection identical). **The world context is `g_pawn`** (show_set 2598, giant_world_time 2604), so no pawn means no lights (T20) | high | none beyond T20 |
| T18 | `/Game/Equipment/Deck/BP_Deck.BP_Deck_C` + `GetIsPlaying`, `GetPlaybackSeconds`, `GetCurrentTrackDisplayName`, props `CurrentTrackFileName`, `BeatgridBpm`, `BeatgridStartMs` (2855-2872) | **`ATribeDeck`** (150 props, 280 funcs) → `/Script/TribeXR.TribeDeck`: `CurrentTrackFileName` Str @0x358, `BeatgridBpm` double @0x738, `BeatgridStartMs` double @0x740; `GetPlaybackSeconds()` → double ReturnValue @0 (parms 8 B), `GetIsPlaying()` → bool @0 (1 B), `GetCurrentTrackDisplayName()` → FString @0 (16 B). The hook's checks (DoubleProperty/BoolProperty/StrProperty) fit these types | high | paths: `/Script/TribeXR.TribeDeck` and `/Script/TribeXR.TribeDeck.<Func>`. Check that `fn_out` takes a native `ReturnValue` (CPF_ReturnParm\|CPF_OutParm); the `[SONG] … out @…` log line shows it |
| T19 | Mixer: `BP_MixerSliderBase_C`, `BP_MixerKnobBase_C`, instances `BP_ChannelVolumeSlider_C` (`CurrentSliderOffset`) and `BP_ChannelColorKnob_C` (`CurrentKnobRotationYaw`), channel var `"Mixer Channel"`/`MixerChannel`, deck `MixerChannel` (2722-2750) | `ATribeMixerSliderBase` (`/Script/TribeXR.TribeMixerSliderBase`), `ATribeMixerKnobBase`, instances `ATribeChannelVolumeSlider` (`"TribeChannelVolumeSlider"`, `MixerChannel` int @0x598) and `ATribeChannelColorKnob` (`"TribeChannelColorKnob"`; `MixerChannel` int @0x578 on its parent `ATribeChannelKnobBase`); `CurrentSliderOffset` double @0x4D0 on `ATribeSliderBase`; `CurrentKnobRotationYaw` double @0x4E0 on `ATribeKnobBase`; `ATribeMixerChannelDevice.MixerChannel` int @0x2D0 | high (names); medium (that ATribeDeck derives from ATribeMixerChannelDevice and the knobs/sliders from the *MixerSliderBase/KnobBase pair; super chains were not extracted) | 2 paths + 2 class-name strings. `"MixerChannel"` is already in the CHN list. The `[MIX] … -> following the faders` log confirms |

## 6. Walking on the stage (`halloween_collide.txt`, club.cpp)

| # | 2304 target | 2311 match | Conf. | Port change |
|---|---|---|---|---|
| T20 | `TribePawnBP_C`: `g_pawn` (dumper.cpp:1187), and the outer of the `VROrigin` / `Camera` / `MotionControllerL/R` components (1183-1186, club.cpp:168) | `ATribePawn` → `"TribePawn"`, with object properties `VROrigin` @0x3C0, `Camera` @0x3C8, `MotionControllerL` @0x3E0, `MotionControllerR` @0x3E8. `TribePawnBP.uasset` is gone, so the live pawn class is native (or a native subclass) | high (class/props), medium (component object names = property names) | strings; better, read the components from the pawn's properties by name rather than matching names under an outer. This also restores the show bus world context (T17) |
| T21 | Stick input: `InpAxisEvt_MotionController L/R Thumbstick_X/Y_K2Node_InputAxisEvent` on `TribePawnBP_C`, caught in ProcessEvent (club.cpp:43-84) | Gone. ATribePawn has native `Input_ThumbStickX_Axis` / `Input_ThumbStickY_…` UFUNCTIONs, but native input bindings don't go through ProcessEvent | high (gone) | none needed: `club_sticks` already falls back to `PlayerController.GetInputAnalogKeyState` (club.cpp:227-235, engine, unchanged). Verify walking on device |
| T22 | `halloween_collide.txt` (228,362 B; folder chosen by `em_active_folder`, club.cpp:103-120) | Data file, unchanged | high | none (T14 applies) |

## 7. Stream intro and Crowd camera (`intro.halloween.txt`, `camview.halloween.txt`): overlap with the camera piece

| # | 2304 target | 2311 match | Conf. | Port change |
|---|---|---|---|---|
| T23 | `BP_SelfieStick_C` (intro.cpp:129, dumper.cpp:3393/3463, head.cpp) | `ATribeSelfieStick` → `"TribeSelfieStick"`: `CaptureComponent2D` @0x2A0, `CameraMesh` @0x2A8, `DisplayPlane` @0x2B8 | high | strings; read the plane and capture from these properties |
| T24 | `/Game/Equipment/Deck/PlayPause/BP_PlayButton.BP_PlayButton_C` + `GetTribeEquipmentBase` (intro.cpp:80-81, 190) | `ATribePlayButton` → `/Script/TribeXR.TribePlayButton`. **`GetTribeEquipmentBase` is gone; the button has a `Deck` object property @0x4C8** | high | new code: match a button to its deck through `Deck` |
| T25 | `M_SelfiePreview`, `BackdropMediaPlayer` (intro.cpp:127,134) | Present, SHA1-identical | high | none |
| T26 | `W_VisualsMenu_C` (camview.cpp:37,339,352: `SetActiveCameraButton`, camera button panel) | `UTribeVisualsMenuWidget`: `SetActiveCameraButton`, `HandleCamera1..8`, `HandleSelfieCamera`, `CamerasSelectionBox` @0x418, `CameraPanel` @0x410, `ActiveCameraButton` @0x3B0 | high (names) | string `"TribeVisualsMenuWidget"`; the button-add path is the camera piece's to check |

Out of scope but on the same pattern, for whoever ports them: `TribePlayerControllerBP_C` → `ATribePlayerController`,
`TribeGameInstanceBP_C` → `UTribeGameInstance`, `TribeControllers_C` → `ATribeControllers`,
`BP_ReadyPlayerMeAvatarSkin_C` → `UTribeReadyPlayerMeAvatarSkin`, `W_ProfileMenu_C.AvatarList` →
`UTribeProfileMenuWidget.AvatarList` @0x398, `BP_TribeVisualsManager_C.ApplySkinToPlayer` →
`ATribeVisualsManager.ApplySkinToPlayer(Skin)` (dumper.cpp:918).

## 8. Port steps and time

1. Patch the 2311 `libUnreal.so` with `add_needed.py`, and confirm `.text` moved by exactly +0x1000. Set E1/E3/E4/E5 in
   dumper.cpp and `params.txt` (`np=0x0884D640`, `bo=0x40`, `ga=0x088A6150`). **0.5 h**
2. Replace the Blueprint paths and class names with native ones (T4, T5, T7, T9, T10, T18, T19, T20, T23, T24, T26). Make
   the class-substring matches exact. About 30 strings across dumper.cpp, club.cpp, intro.cpp, camview.cpp, head.cpp.
   **1-2 h**
3. New `SetupEnvironmentBackdrop` call: pass the manager's own lights and dim factor back (T11). **1-2 h**
4. `intro_deck_button` through `ATribePlayButton.Deck` (T24). **0.5 h**
5. Patch OBB: rename to `patch.2311…`, set the zip comment to `"      2311"`, and update the push/reseed/install scripts
   (P5). The pak is reused as is. **0.5 h**
6. First device runs: install, launch, load Graveyard Shift via `active_env.txt`/`env_autotest` (no menu click needed),
   then read `[LOAD]`, `[ENV]`, `[GIANT]`, `[SONG]`, `[MIX]`, `[CLUB]` and `[INTRO]`. Fix T13/T14 if the Void changed.
   **3-5 h** (several APK cycles; each install raises the Restore App dialog)
7. Menu click path (T6/T7): trace on device, then implement. **2-4 h**; the most uncertain step.

Total: **about 10-16 hours of work, 2 working days**. Steps 1-5 are offline. The stage itself (pak, lights, walking)
should be up after step 6. A menu box that works by clicking needs step 7. No Unreal cook is needed.

## 9. What is still unverified, and what to watch

- **Behaviour, not names, is the open risk.** Every name above was read from 2311's reflection tables. Whether
  Tribe's native code tolerates what the hook does with them is not checkable offline: spawning list items into
  `EnvironmentList`, calling `SetupEnvironmentBackdrop` with our values, and hiding the Void's actors. A null
  dereference in T11 would be a crash at stage load, which is a loud failure.
- **Silent failure to watch for:** no `g_pawn`. If the pawn lookup (T20) fails, the stage loads but the show bus never
  writes, and the lights run their free 140 BPM loop. The `[LOAD] follow: … pawn=0x0` line shows it.
- **T13/T14 (the Void changed):** if the screens were renamed, the Void's own backdrop stays visible inside the stage.
  If the rig moved, the stage, walking map, Crowd camera and intro path are all offset. Both show in the first `[ENV]`
  log.
- **The +0x1000 lief shift** is measured on 2304 only. If add_needed.py lays out 2311 differently, the PE prologue check
  skips the hook (loud: no `[LOAD]` lines past the constructor) instead of crashing.
- **Not read:** 2311's changed `DefaultEngine.ini`/`DefaultGame.ini` (Oodle; P5 note), and UE's Java OBB-comment check
  (P5 is derived from the observed naming).
- `ATribeDeck`'s super chain (T19) was not extracted, so whether its `MixerChannel` comes from
  `ATribeMixerChannelDevice` is inferred. The `[MIX]` log line `deck MixerChannel @…` settles it.
