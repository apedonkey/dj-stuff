# Selfie camera view: 2304 (Tribe 0.12.5.1) -> 2311 (Tribe 0.12.6) target map

Mapping only (2026-10-31). Nothing was built, edited or pushed. Pieces covered: hook/camview.cpp (the Crowd button,
Tribe's camera buttons, the FOV), the drone_update path that feeds the selfie view, the drone_path / camview files,
and the 2311 counterparts of W_VisualsMenu and the Selfie handler.

## TL;DR

- **The port is mostly a rename, not an address remap.** Tribe 0.12.6 moved the camera menu, the selfie stick, the
  player controller and the pawn out of Blueprints into C++. `W_VisualsMenu_C`, `BP_SelfieStick_C`,
  `TribePlayerControllerBP_C` and `TribePawnBP_C` no longer exist (their assets are gone from the 2311 OBB). Their
  C++ replacements keep the **same property names** (`SelfieCameraButton`, `CameraButton1..8`, `CaptureComponent2D`,
  `ActiveSelfieStick`, `Camera`), so camview's reflection code mostly carries over. What breaks is the class-name
  strings and the handler-name matcher.
- **As the hook stands, nothing in the selfie view would work on 2311, and it would fail without crashing.** No menu
  found means no Crowd button. No `BP_SelfieStick_C` means `g_droneCap` stays 0, so neither the reel nor the Crowd
  view flies. No `TribePawnBP_C` means `g_camComp` stays 0, which turns drone_update off completely.
- **Native addresses: 3 needed, 3 mapped, all high confidence.** ProcessEvent, FNamePool and GUObjectArray, each found
  by matching code between the two builds. Engine struct offsets are unchanged.
- **Port estimate for the selfie view alone:** about 2.5 to 3.5 h, including a headset session. Add 1 to 2 h if the
  2311 menu layout defeats the cell cloning. Details at the end.

## Address rules (verified)

| | 2304 (mod) | 2311 (store) |
|---|---|---|
| libUnreal.so md5 | store d7c722db, modded 915c3130 (+8,200 B) | 385f58a9 (142,361,784 B) |
| .text vaddr / file off | 0x1446000 / 0x1436000 | 0x15d7000 / 0x15c7000 |
| .data.rel.ro vaddr / off | 0x6d1c080 / 0x6cfc080 | 0x7676040 / 0x7656040 |
| .bss vaddr | 0x7c09300 | 0x87f3680 |

- **Where the "+0x1000 skew" comes from:** hook/add_needed.py (LIEF `add_library`) inserts one page into libUnreal.so.
  In the modded 2304 lib every PT_LOAD vaddr is the store vaddr + 0x1000 (store .text vaddr 0x1446000, modded
  0x1447000; the store .text bytes appear at modded file offset 0x1437000). So **runtime RVA = store ELF vaddr +
  0x1000**, which is the notes' "Ghidra = ELF vaddr + 0x100000 = RVA + 0xFF000". This holds for .bss as well:
  params.txt `np=0x07C632C0` and `ga=0x07CBBDD0` are the store addresses 0x7c622c0 / 0x7cbadd0 + 0x1000, and the store
  2304 code references exactly those two store addresses (53 and 223 references).
- **For 2311 the skew is an assumption until the patched 2311 lib exists.** LIEF chooses the layout per binary. Check:
  after add_needed.py, the patched lib's executable PT_LOAD vaddr must be 0x15d8000 (store 0x15d7000 + 0x1000). If it
  differs, use (patched .text vaddr − 0x15d7000) as the skew everywhere below.
- The relocations are RELR (implicit addends), so pointers in .data.rel.ro / .got hold plain store vaddrs. That is how
  the reflection tables below were read.

## Native targets

### 1. UObject::ProcessEvent (hook point for camview_pe and the game-thread tick; call_uf goes through it)
- **2304:** store vaddr 0x1857dd4 (hook: `RVA_PE_GHIDRA=0x1857dd4`, `PE_SKEW=0x1000`, runtime 0x1858dd4;
  Default__Object vtable[78], checked at runtime in the earlier sessions).
- **2311:** store vaddr **0x19e8eb4**, runtime **0x19e9eb4** with a 0x1000 skew.
- **How matched:** the first 24, 32 and 48 instructions of 2304's PE, with PC-relative fields masked, match exactly one
  place in 2311 .text (and only one place in 2304). Over 400 instructions the two are 96% identical; every difference
  is the low-12-bit immediate of a global address (ADD/LDR after ADRP). The first `ret` is at the same index (193).
  Both load `UFunction` +0xB6 (ParmsSize) and +0xB8 (ReturnValueOffset) with ldrh. The first word is the same
  `stp x29,x30,[sp,#-0x60]!` (0xa9ba7bfd), so on_load's prologue guard passes.
- **Confidence:** high.
- **Unverified:** the patched 2311 lib's skew (see above).
- **Port:** `RVA_PE_GHIDRA = 0x19e8eb4` (the name is misleading: it holds the store ELF vaddr); keep `PE_SKEW = 0x1000`
  once the patched lib is checked.

### 2. FNamePool (fname_resolve; every name lookup camview does)
- **2304:** store vaddr 0x7c622c0; params.txt `np=0x07C632C0`, `bo=0x40`.
- **2311:** store vaddr **0x884c640**, so `np=0x0884D640` (with the 0x1000 skew); `bo=0x40` unchanged.
- **How matched:** 53 2304 code sites reference the pool. Each site's 30-instruction window (relative fields and load
  immediates masked) was searched in 2311. 14 windows matched uniquely, and all 14 decode to the same 2311 address.
- **Confidence:** high.
- **Port:** update params.txt, or delete the `np=` line so `scan_namepool()` finds it at runtime. A wrong `np=` is
  fatal: there is no fallback once `P_np` is set.

### 3. GUObjectArray (obj_at, em_find_live, find_live_class_sub)
- **2304:** store vaddr 0x7cbadd0; params.txt `ga=0x07CBBDD0`; hook `RVA_GUObjectArray=0x07CBADD0`,
  `RVA_GUObj_GOTslot=0x07AA59E8` (the GOT slot that holds &GUObjectArray, store vaddr).
- **2311:** store vaddr **0x88a5150**, so `ga=0x088A6150`. GOT slot store vaddr **0x8678738** (runtime 0x8679738).
- **How matched:** 223 2304 code references. 89 windows matched uniquely in 2311, and all 89 decode to 0x88a5150. The
  GOT slot is the only 8-byte value 0x88a5150 in the 2311 file, just as 0x7aa59e8 is the only one in 2304.
- **Confidence:** high.
- **Note:** the hook adds no skew to `RVA_GUObjectArray` / `RVA_GUObj_GOTslot`, so on the patched 2304 lib those two
  fallbacks were already one page off. `ga=` in params.txt (or the scan) did the work. For 2311, either use runtime
  values (0x088A6150 / 0x08679738) or leave them as fallbacks behind a correct `ga=`.

### 4. Engine struct offsets
- OFF_Class 0x10, Name 0x18, Outer 0x20, Flags 0x08, Index 0x0C; OFF_Super 0x40, Children 0x48, ChildProps 0x50,
  PropSize 0x58; UField::Next 0x28; UFunction ParmsSize 0xB6 / ReturnValueOffset 0xB8.
- **2311:** unchanged. 0xB6 / 0xB8 are seen directly in 2311's ProcessEvent. The rest is inferred from the engine
  code being identical apart from global addresses.
- **Confidence:** high for 0xB6 / 0xB8. Medium-high for the rest: not every offset was checked one by one. The hook's
  R3 self-check and `calib_fprop_size()` re-derive them at runtime anyway.
- **Port:** none.

### Not used by the selfie view
- `PC_AUTOCAM_NEXTCUT = 0x974` is a raw C++ member offset in the controller. drone_update writes 1e9 to it **only with
  drone.txt `target=auto`**, and camview refuses to run in that mode. The 2311 controller gained members
  (ActiveSelfieStick 0x988, OnSpectatorCameraToggled 0x9c8, OnboardingCaptureComponent 0x9d8, SelfieStickClass
  0x9e8), so 0x974 is **unverified on 2311**. Writing there could corrupt the object. Keep `target=selfie` (the
  headset's drone.txt is `mode=path`, so it is already selfie) until someone re-derives 0x974.
- calib() anchors (dispatcher 0x4ffc2d4, CallFunction 0x1856bac, ...) only feed calib.txt and are stale on 2311.
  They are read-only, so this is harmless.

## Blueprint -> C++ targets (the real port work)

Method: each 2311 class was found from its UHT registration entry (the UTF-16 name -> Z_Construct_UClass -> GOT ->
FClassParams). The UFUNCTION names come from FunctionLinkArray, and property names/offsets from the
FPropertyParams `Offset` field. Asset presence was checked against both OBBs' pak indexes, reading in place.
2311's pakchunk0 has no path containing `VisualsMenu`, `SelfieStick`, `TribePlayerControllerBP` or `TribePawnBP`.
`TribeXR/Content/GameModes` holds 22 files in 2304 and 0 in 2311.

### 5. The camera menu: W_VisualsMenu_C -> TribeVisualsMenuWidget
- **2304:** Blueprint `/Game/Visuals/W_VisualsMenu.W_VisualsMenu_C` (pakchunk0). camview finds it with
  `em_find_live("W_VisualsMenu_C")` (exact class-name match), camview.cpp:339.
- **2311:** C++ `UTribeVisualsMenuWidget`, reflected name **`TribeVisualsMenuWidget`**
  (`/Script/TribeXR.TribeVisualsMenuWidget`): ClassParams 0x81c2da8, StaticClass 0x541d930, Z_Construct 0x541c04c;
  34 UFUNCTIONs, 61 UPROPERTYs. Its widget tree is built in C++: the UTF-16 widget names `SelfieCameraButton`,
  `CameraSelfieText`, `ResetSelfieButton`, `ResetSelfieText` exist, and there is no WidgetBlueprint asset.
- **How matched:** same role and the same property set as the 2304 Blueprint's variables (below).
- **Confidence:** high that this is the camera menu. Medium that the live object's class is exactly
  `TribeVisualsMenuWidget`: no Blueprint asset exists that could subclass it, but this was not seen on a device.
- **Port:** camview.cpp:339 `em_find_live("W_VisualsMenu_C")` -> `"TribeVisualsMenuWidget"`. Also fix the log text at
  camview.cpp:37 and :352.

### 6. The camera buttons (properties on the menu)
| property | 2304 (BP var) | 2311 offset | class |
|---|---|---|---|
| SelfieCameraButton | yes | 0x480 | UButton |
| CameraButton1 / 2 / 3 / 4 | yes | 0x458 / 0x460 / 0x468 / 0x478 | UButton |
| CameraButton6 / 7 / 8 | yes | 0x470 / 0x490 / 0x498 | UButton |
| CameraButton5 | absent | absent | (unchanged quirk) |
| ResetSelfieButton | yes | 0x488 | UButton |
| ActiveCameraButton | yes | 0x3b0 | UButton |
| TribePlayerController | yes | 0x2e8 | ATribePlayerController |
- **How matched:** UHT property tables. The property class was resolved via ClassFunc -> StaticClass -> registration
  name.
- **Confidence:** high.
- **Port:** none. camview reads these by name through `prop_offset`.

### 7. Tribe's camera handlers, including the Selfie handler
- **2304 (Blueprint events, ProcessEvent-visible):**
  `BndEvt__CameraButtonSelife_K2Node_ComponentBoundEvent_11_OnButtonClickedEvent__DelegateSignature` (Selfie: if
  ActiveSelfieStick is valid, `SetActiveSpectatorCamera(ActiveSelfieStick.CaptureComponent2D)`, then
  `SetActiveCameraButton(SelfieCameraButton)`), `BndEvt__CameraButton1..4_*` (SetSpectatorCamByIndex 0..3),
  `BndEvt__W_VisualsMenu_CameraButton5_*` (first-person capture, marks CameraButton6),
  `BndEvt__W_CameraMenu_CameraButton7/8_*` (ShowAutoCam 1/0). Source: D:/TribeUE/tribe_assets/catalog/code/Visuals/W_VisualsMenu.txt.
- **2311 (native UFUNCTIONs on TribeVisualsMenuWidget):**

  | UFUNCTION | exec thunk | C++ body | camview index |
  |---|---|---|---|
  | `HandleSelfieCamera` | 0x541d15c | 0x5b6d344 | 0 (Selfie) |
  | `HandleCamera1` | 0x541c4b8 | 0x5b6cee4 | 1 |
  | `HandleCamera2`, `3`, `4` | (not traced) | (not traced) | 2, 3, 4 |
  | `HandleCamera6` | 0x541c638 | 0x5b6d164 | 6 |
  | `HandleCamera7` | 0x541c698 | (not traced) | 7 |
  | `HandleCamera8` | (not traced) | (not traced) | 8 |

  `HandleResetSelfie` and `HandleCameraToggle` are **not** camera picks; the new matcher must skip them.
  `SetActiveCameraButton` (exec 0x541d53c, body 0x5b6e6a0) still exists.
- **What HandleSelfieCamera does (checked in its code):** the body loads `this+0x2e8` (TribePlayerController), then
  `+0x988` (ActiveSelfieStick), then `+0x2a0` (CaptureComponent2D). It calls 0x5a439dc, which is
  ATribePlayerController::SetActiveSpectatorCamera (execSetActiveSpectatorCamera 0x53734c4 calls it, and it calls
  ATribeSelfieStick::StaticClass). Then it restyles `+0x3b0` (ActiveCameraButton) and `+0x480` (SelfieCameraButton)
  through the same two calls SetActiveCameraButton makes. That is the 2304 Blueprint handler, step for step.
  HandleCamera6 also calls SetActiveSpectatorCamera, like 2304's CameraButton5 event.
- **Will ProcessEvent see Tribe's presses?** Each handler name exists as a standalone UTF-16 literal
  (`HandleCamera1`, `HandleSelfieCamera`, ...). That is what binding a dynamic delegate by name produces, and dynamic
  delegates dispatch through ProcessEvent, so camview_pe should still see them.
- **Confidence:** high for the names and for the Selfie handler's behaviour. Medium-high for ProcessEvent visibility:
  the binding call sites were not traced. Falsifier: on the headset, pressing Tribe's Camera 1 while the Crowd view
  holds does not log `[CAMVIEW] the camera goes back (Tribe's CameraButton1)`.
- **Effect if not ported:** camview_poll (camview.cpp:341-347) only accepts `BndEvt__*CameraButton*` names, so on 2311
  `g_cvNCamFn = 0` and `g_cvFnSelfie = 0`. A Crowd press then logs "Tribe's Selfie handler wasn't found" and does
  nothing, and Tribe's own camera buttons never hand the camera back.
- **Port:** in the handler scan, map `HandleSelfieCamera` -> 0 and `HandleCamera<d>` (d = 1..8) -> d, and skip
  `HandleCameraToggle` and `HandleResetSelfie`. Keeping the `BndEvt__` rule as well makes one hook work on both builds.
  Calling HandleSelfieCamera with `call_uf` and a zeroed buffer works for a native UFUNCTION (it takes no parameters;
  the existing psz guard covers it).

### 8. The selfie stick: BP_SelfieStick_C -> TribeSelfieStick
- **2304:** `/Game/Equipment/Table/BP_SelfieStick.BP_SelfieStick_C`. drone_poll does
  `find_live_class_sub("BP_SelfieStick_C")` and then reads property `CaptureComponent2D` (dumper.cpp:3463-3464). That
  gives `g_droneCap`, the capture the reel and the Crowd view fly, and whose FOVAngle cv_fov sets.
- **2311:** C++ `ATribeSelfieStick`, reflected name **`TribeSelfieStick`**: ClassParams 0x8137478, StaticClass
  0x53b012c. Properties: `CaptureComponent2D` 0x2a0 (USceneCaptureComponent2D, confirmed), `CameraMesh` 0x2a8,
  `ArmMesh` 0x2b0, `DisplayPlane` 0x2b8, `InitialTransform` 0x2c0. UFUNCTIONs include ResetSelfieCamera,
  SaveCameraPosition, LoadCameraPosition, ResetCameraPosition. The controller spawns it from `SelfieStickClass` (0x9e8).
- **Confidence:** high.
- **Effect if not ported:** `g_droneCap` never resolves ("take the selfie stick out" every minute). Nothing flies, and
  cv_fov has no capture to set.
- **Port:** dumper.cpp:3463 (and the [CAM] log at :3393): needle `"BP_SelfieStick_C"` -> `"SelfieStick"`.
  find_live_class_sub is a substring match, so this matches both builds. The property name stays. The same rename is
  needed at head.cpp:282 and intro.cpp:129 (other pieces, same fix).

### 9. The player controller: TribePlayerControllerBP_C -> TribePlayerController
- **2311:** C++ `ATribePlayerController` (ClassParams 0x80dd228). ActiveCaptureComponent 0x888,
  FirstPersonCaptureComponent 0x890 and AutoCamCaptureComponent 0x898 have the same offsets as in 2304.
  `ActiveSelfieStick` (0x988, ATribeSelfieStick) was a Blueprint variable in 2304 and is now C++. New native
  UFUNCTIONs: SetActiveSpectatorCamera, SetSpectatorCamByIndex, ShowAutoCam, ToggleSpectatorCamera,
  IsSpectatorCameraEnabled.
- **Selfie view:** uses the controller only through HandleSelfieCamera. No port needed.
- **Port (target=auto only):** dumper.cpp:3471 `"TribePlayerControllerBP_C"` -> `"TribePlayerController"`, and
  re-derive 0x974 before anyone uses `target=auto`.
- **Confidence:** high for the names and offsets listed.

### 10. Your head (the pawn camera): TribePawnBP_C -> TribePawn (load-bearing)
- **2304:** dumper.cpp:1183-1187: `g_camComp = find_live("Camera","CameraComponent","TribePawnBP_C")`, plus VROrigin,
  MotionControllerL/R and `g_pawn`. drone_update requires `g_camComp && g_fnLoc` to do anything, and camview's
  `look=dj` reads your head from g_camComp.
- **2311:** the Blueprint `/Game/Pawn/TribePawnBP` is gone. C++ `ATribePawn` (ClassParams 0x80cf0e0) now declares
  `VROrigin` 0x3c0, `Camera` 0x3c8, `HeadCollisionSphere` 0x3d0, `MotionControllerL` 0x3e0 and `MotionControllerR`
  0x3e8 (MotionController class confirmed UMotionControllerComponent). These were Blueprint components in 2304; the
  2304 C++ ATribePawn had none of them.
- **Effect if not ported:** the path filter `"TribePawnBP_C"` matches nothing, so `g_camComp = 0` and the selfie view
  and the reel are dead even with the selfie stick found.
- **Port:** use the inpath filter `"TribePawn"` (substring: matches both `TribePawnBP_C_0` and `TribePawn_0`), or more
  robustly read the live pawn's `Camera` property through `prop_offset`. The same applies to `g_pawn` (also the
  fallback game-thread ticker). This is shared FOLLOW wiring in dumper.cpp, so tell the avatar / Halloween pieces.
- **Confidence:** high that the Blueprint is gone and the C++ property is named `Camera`. Medium that the component
  object is named `Camera` with class exactly `CameraComponent`: its CreateDefaultSubobject name and ClassFunc did not
  resolve statically. If find_live by name misses, reading the property sidesteps both questions.

### 11. Engine functions and properties camview looks up by path
`/Script/UMG.Button.IsPressed`, `UMG.Widget.SetVisibility`, `UMG.PanelWidget.AddChild`,
`Engine.KismetTextLibrary.Conv_TextToString` / `Conv_StringToText`, `GameplayStatics.SpawnObject`, `TextBlock.SetText`,
`SceneComponent.K2_SetWorldLocationAndRotation` / `K2_SetRelativeLocationAndRotation` / `K2_GetComponentLocation`,
`SceneCaptureComponent2D.FOVAngle`, the setters cv_props uses (SetStyle, SetBrush, SetColorAndOpacity, SetIsEnabled,
SetRow, SetColumn), and the UMG layout properties Slot / Parent / Content / Slots / WidgetTree.
- **2311:** every name is present as a C-string or a merged string tail, as in 2304. The engine is unchanged (see 1
  and 4).
- **Confidence:** high.
- **Port:** none. The first launch logs them (`[CAMVIEW] UMG: IsPressed 0x...`).

### 12. The data files (drone_path, camview, flags)
- No binary dependency. The 2311 store install has **no tribemod folder** (backup/tribe_2311/pull_2311.log), so
  restore from backup/tribemod_20261031_preupdate/tribemod_full/tribemod/:
  - `camview.halloween.txt`: the live v2 (pos=170,-2730,-90, look=dj, fov=60, sway=3). claudedocs/halloween_camview.txt
    is the older v1 (0,-3130,430), so use the backup copy.
  - `drone_path.halloween.txt` (identical to claudedocs/halloween_drone_path.txt).
  - `drone.txt` (`mode=path`), plus the `drone_cam` and `executor_on` flags.
  - `params.txt` with the new `np=` / `ga=` (above).
- camview and drone_load_path pick the `.halloween` files through `em_active_folder()`, which belongs to the Halloween
  stage piece. Heads-up for that piece: dumper.cpp:3697 finds the stage list's click handler as
  `BndEvt__W_VisualsMenu_EnvironmentList_*` in `W_VisualsMenu_C`. Both are gone in 2311, and TribeVisualsMenuWidget's
  UFUNCTION list has no environment-list item handler.

## What is still unverified (everything below needs the headset or the patched lib)

1. The patched 2311 libUnreal.so's skew. Expected 0x1000; read its PT_LOAD vaddrs after add_needed.py.
2. That Tribe's camera presses reach ProcessEvent on 2311 (handler binding not traced). Falsifier above.
3. The 2311 menu's layout. The tree is now built in C++, so rows and cells may differ from 2304, and **the 2304 layout
   was never logged either**: the notes record no `[CAMVIEW] added` / `tree` lines (halloween_stage_notes.md "v8":
   "First-launch [CAMVIEW] log check still pending"). camview works the layout out at runtime and logs it. If a cell
   is a UserWidget it refuses to clone and logs why.
4. The pawn camera component's object name and class (target 10).
5. 0x974 on 2311 (auto-cam only).
6. The game-thread tick: camview_tick and drone_update run from our iso actor's ReceiveTick, or from the pawn when the
   iso actor isn't up. Those are other pieces' paths, but the selfie view stops if neither ticks.

## What the port changes (selfie piece only)

| file:line | 2304 | 2311 |
|---|---|---|
| camview.cpp:339 | `em_find_live("W_VisualsMenu_C")` | `"TribeVisualsMenuWidget"` (try both for a dual build) |
| camview.cpp:341-347 | handlers = `BndEvt__*CameraButton*` | also `HandleSelfieCamera` -> 0, `HandleCamera<d>` -> d; skip HandleCameraToggle / HandleResetSelfie |
| dumper.cpp:3463 (+:3393) | `find_live_class_sub("BP_SelfieStick_C")` | `"SelfieStick"` |
| dumper.cpp:1183-1187 | inpath / class `"TribePawnBP_C"` | `"TribePawn"`, or read `Camera` / `VROrigin` / `MotionController*` off the live pawn |
| dumper.cpp:3471 (auto only) | `"TribePlayerControllerBP_C"` | `"TribePlayerController"` |
| dumper.cpp:867 | `RVA_PE_GHIDRA=0x1857dd4` | `0x19e8eb4` (PE_SKEW 0x1000 after checking 1) |
| dumper.cpp:35-37 | NamePool / GUObjectArray / GOT slot | runtime 0x0884D640 / 0x088A6150 / 0x08679738 (store vaddr + 0x1000) |
| tribemod/params.txt | `np=0x07C632C0 bo=0x40 ga=0x07CBBDD0` | `np=0x0884D640 bo=0x40 ga=0x088A6150` |

## Port steps

1. Patch the 2311 libUnreal.so with add_needed.py and read the PT_LOAD vaddrs to confirm the skew (shared step).
2. Apply the edits in the table above.
3. Build libhook, sign, install. Restore the tribemod files listed in target 12 with the new params.txt.
4. First launch, in the logs:
   - `[CAMVIEW] camera handler N: HandleSelfieCamera -> SelfieCameraButton` and 6 more,
     then `Tribe's visuals menu: 0x...`.
   - `[DRONE] resolve (selfie stick): capture=0x...` (not 0).
   - `follow: ... cam=0x...` (not 0).
   - `[CAMVIEW] tree ...` and `added 'Crowd'`.
5. In the headset on Graveyard: take the stick out and press Crowd. Expect `'Crowd' picked` and
   `stream camera FOV 90.0 -> 60.0`, with the stream at the Crowd view. Press Tribe's Camera 1: expect
   `camera goes back (Tribe's CameraButton1)` and the FOV restored. Let the reel's fov=40/60 shots play.

## Time estimate (honest)

- Code edits, including a dual-build version: 30-45 min.
- Patch, skew check, build, sign, install (if no other piece has done it): 30-45 min.
- Restoring the tribemod files: about 10 min.
- First launch plus the in-headset test: 30-60 min (needs the user).
- **Total: about 2.5-3.5 h.** Add 1-2 h if the C++-built menu's cells don't clone (UserWidget cells or a different row
  structure). Add 15 min if the pawn camera lookup needs the property-read version.
