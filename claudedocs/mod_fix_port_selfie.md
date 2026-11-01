# Selfie camera view (the "Crowd" button): port of camview.cpp to Tribe 0.12.6 (2311)

2026-10-31. I edited only `backup/mod_fix_work/selfie/camview.cpp` (copied from `hook/camview.cpp`, md5 1a2f6f67) and
wrote this file. Nothing was built, signed, installed or pushed, and no adb was run. Everything about 2311 below was
read offline from the store `backup/mod_halloween_work/lib2311/libUnreal.so` (capstone disassembly plus the UHT
reflection tables). 2304 facts come from `lib2304/libUnreal.so` and the 2304 asset catalog
(`D:/TribeUE/tribe_assets/catalog/code/Visuals/W_VisualsMenu.txt`).

## Answer first

- **camview.cpp is ported, and one hook serves both builds.** It finds the menu as `TribeVisualsMenuWidget` (2311) or
  `W_VisualsMenu_C` (2304) in a single pass over the object array. It accepts the 2311 handlers
  (`HandleSelfieCamera`, `HandleCamera<d>`) as well as the 2304 `BndEvt__` events, and on 2311 it waits for the
  C++-built widget tree before trying to add the button. That is 50 added lines and 16 removed; the rest of the file is
  unchanged.
- **The 2311 menu layout is no longer unknown** (mapping item "still unverified 3"). I read the menu's C++ tree builder.
  All eight camera buttons are plain `UButton`s, each holding a `UTextBlock`, and they sit directly inside one
  `UVerticalBox` (`VerticalBox_117`). That is camview's existing "one row" case. The clone template will be
  `CameraButton8`, and the Crowd button goes into the list below it. Only engine widgets get cloned, so the mapping's
  "add 1-2 h if the cells don't clone" case shouldn't come up. Whether the clone actually shows and works is still a
  headset check.
- **dumper.cpp: no extra edits are needed** beyond the ones the main agent already plans. I checked those names
  against 2311: the pawn's subobjects are `Camera`/`CameraComponent`, `VROrigin`/`SceneComponent` and
  `MotionControllerL/R`/`MotionControllerComponent`, and `"SelfieStick"` matches only the stick class in both builds.
- **Top risk:** the selfie view runs only if the game-thread tick exists. That tick, along with `g_camComp`/`g_fnLoc`,
  comes from the avatar load path (`do_load` → our iso actor, dumper.cpp:1180-1188, 1241, 3239-3240). It also needs
  the stage to be up through the env menu (`g_emState==EM_ACTIVE`). Both belong to other pieces. If either is missing,
  the Crowd button silently never appears.

## What I read from 2311 (evidence for the changes)

All addresses are store ELF vaddrs in the 2311 `libUnreal.so`.

1. **The menu's widget tree is built in C++** by one large function at `0x5b5de3c`. It returns at once if
   `WidgetTree->RootWidget` (WidgetTree at `this+0x278`) is already set. Two places call it:
   - `0x5b6bc64` takes an sret pointer, calls the builder, then tail-calls `0x3882960`. Its vtable slot (`0x81c3138`)
     is the one 85 other widget classes fill with `0x3882960`, and the neighbouring slots match, so this is the
     menu's `RebuildWidget` override.
   - `0x5b6bc90` (vtable `0x81c3158`) creates the WidgetTree if it is missing, calls the builder, then binds the
     buttons.

   So the menu object can be live before its buttons exist. That is why change C6 below exists.
2. **The camera page** (parents taken from each `UPanelWidget::AddChild(parent, child)` call, `0x37b8e9c`; widget
   classes from the `StaticClass` called before each construction):

   ```
   VisualsPanelSwitcher (WidgetSwitcher, +0x438)
     CameraControlsBox (VerticalBox, +0x440)
       VerticalBox_117 (VerticalBox, not a property)      <- parent of every camera button
         CameraOnBorder (Border, +0x448) > HorizontalBox_151 > CameraText0 (TextBlock), CameraOnSlider (TribeOnOffSliderWidget)
         CameraButton1 (+0x458) > CameraText1      CameraButton2 (+0x460) > CameraText2      CameraButton3 (+0x468) > CameraText3
         CameraButton6 (+0x470) > CameraText5      CameraButton4 (+0x478) > CameraText4
         SelfieCameraButton (+0x480) > HorizontalBox_11 > CameraSelfieText (TextBlock), ResetSelfieButton (+0x488) > ResetSelfieText
         CameraButton7 (+0x490) > CameraText7      CameraButton8 (+0x498) > CameraText8
   ```
   That is the child order inside VerticalBox_117. Every button is a `UButton` and every slot a `VerticalBoxSlot`.
   I checked the parents by register dataflow as well as by the `mov x0, x24` pattern. The builder spills
   VerticalBox_117 from x24 to `[sp+0x10]` at `0x5b60928`, uses x24 for temporaries twice, and reloads it from that
   slot (`0x5b60a78`, `0x5b61030`, `0x5b61564`). No store touches the slot in between, on the main path or in the
   construct stubs, and x24 has no other writes up to CameraButton8's AddChild (`0x5b62a50`). ResetSelfieButton's
   parent (x21) is HorizontalBox_11 by the same check. The
   designer default names (`VerticalBox_117`, `HorizontalBox_151`, `HorizontalBox_11`) suggest the C++ was ported
   one-for-one from the 2304 Widget Blueprint. I could not read the 2304 tree itself, so treat that as derived.
3. **Bindings** (`0x5b6bd60`...): each `FScriptDelegate` is built from a static `FName` and added to the button's
   `OnClicked` (`+0x568`, a dynamic multicast delegate, so its broadcast goes through ProcessEvent):

   | button (menu offset) | handler |
   |---|---|
   | CameraButton1/2/3/4 (0x458/0x460/0x468/0x478) | HandleCamera1/2/3/4 |
   | CameraButton6 (0x470) | HandleCamera6 |
   | CameraButton7/8 (0x490/0x498) | HandleCamera7/8 |
   | SelfieCameraButton (0x480) | HandleSelfieCamera |
   | ResetSelfieButton (0x488, nested inside the Selfie button) | HandleResetSelfie |
   | CameraOnSlider (0x450, delegate +0x2e8) | HandleCameraToggle(bool) |
4. **The handlers' FFunctionParams.** In 2311 the layout is OuterFunc, SuperFunc, Name, OwningClassName,
   DelegateName, PropertyArray, NumProperties, StructureSize, ObjectFlags, FunctionFlags.
   - `HandleSelfieCamera` and `HandleCamera1`: 0 properties, StructureSize (ParmsSize) 0, flags 0x40401
     (Final, Native, Private).
   - `SetActiveCameraButton`: 1 property, 8 bytes. `HandleCameraToggle`: 1 property, 1 byte.

   So `call_uf` with a zeroed buffer is correct for HandleSelfieCamera, and camview's `psz` guard (0 ≤ 256) passes.
5. **`HandleSelfieCamera` body `0x5b6d344` is null-safe.** It returns if `TribePlayerController` (+0x2e8) is null or
   `ActiveSelfieStick` (+0x988) fails IsValid. Otherwise it calls `SetActiveSpectatorCamera(stick->CaptureComponent2D
   @0x2a0)`, sets the old `ActiveCameraButton` (+0x3b0) to the unselected color, stores the Selfie button there and
   gives it `SelectedColor` (+0x3c0). In both builds the pick is marked only by `SetColorAndOpacity`; 2304's
   `SetActiveCameraButton` does the same (W_VisualsMenu.txt:271-280). Pressing Crowd with no stick out can't crash
   Tribe.
6. **No subclass.** `Z_Construct_UClass_UTribeVisualsMenuWidget` (`0x541c04c`) is referenced only by its 34
   FFunctionParams and its own registration entry. No other class lists it as a dependency, so no native subclass is
   registered. The mapping found no VisualsMenu asset in the 2311 pak.
7. **The pawn** (ATribePawn constructor, around `0x5a2c46c`) creates its default subobjects with these names and
   classes: `VROrigin` SceneComponent +0x3c0, `Camera` CameraComponent +0x3c8, `HeadCollisionSphere`
   SphereComponent, `AvatarPropMesh` StaticMeshComponent, `MotionControllerL/R` MotionControllerComponent
   +0x3e0/+0x3e8.
8. **Class names.**
   - Containing `SelfieStick`: 2304 has only the `BP_SelfieStick` asset (inventory_full.tsv) and no native one; 2311
     has only `ATribeSelfieStick`.
   - Containing `TribePawn`: classes are `ATribePawn` (both builds) and the 2304 BP `TribePawnBP_C`.
     `TribePawnCameraInput` is a struct (its registration name has no A/U prefix), and `ETribePawn*` are enums. The
     ASCII `TribePawnBP` in 2311 is a reflected member name among `TribeGameStateBP`, `GetDanceManagerBP`..., not a
     class.
9. **Auto-load's filter still matches on 2311.** `AvatarBodyMesh` is a subobject of the native
   `UReadyPlayerMeComponent` in both builds. In 2311 an avatar actor's constructor (around `0x5430594`) creates that
   component under the name `ReadyPlayerMeComponent`, next to `MetaAvatar2Component` and `LocalLipSync`. So the
   filter at dumper.cpp:3810 should still match.

## Changes (all in backup/mod_fix_work/selfie/camview.cpp; line numbers are the new file's)

| # | lines | before → after | why | confidence; falsifier |
|---|---|---|---|---|
| C1 | 315-326 (new), 367 | `m=em_find_live("W_VisualsMenu_C")` → `m=cv_find_menu(cls,sizeof cls,&nLive)`. A single pass accepts the class name `"TribeVisualsMenuWidget"` or `"W_VisualsMenu_C"` (`CV_MENU_CLS`). It uses em_find_live's filters (CDO / archetype / 0x40000000 flags skipped; exact `class_name` strcmp, which I checked at dumper.cpp:2251-2256), keeps the newest (highest index) match, and returns the class name and the number of live matches. | Dual build without a second full object-array walk while the menu is absent. Exact class match is enough: no subclass exists (evidence 6). | High. Falsifier: with the camera menu open on 2311, no `Tribe's visuals menu: 0x… (TribeVisualsMenuWidget, …)` line, only `no live camera menu` lines. |
| C2 | 368 (new) | Silent → `[CAMVIEW] no live camera menu (TribeVisualsMenuWidget / W_VisualsMenu_C) yet: …` on the first miss, then every 20th (about once a minute, only while a stage with a camview file is up). | Fail-safe diagnostic; a missing menu used to leave no trace. | High. |
| C3 | 327-337 (new `cv_cam_handler`), 370-376 | The handler scan accepted only `BndEvt__*CameraButton*` on the menu's own class. Now: `HandleSelfieCamera` → 0; `HandleCamera<d>` → d, exact match (d = 1..8 and nothing after the digit); the BndEvt rule is kept; everything else is skipped (HandleCameraToggle, HandleResetSelfie, the other 26 UFUNCTIONs). The scan walks the class and its supers up to UserWidget (at most 8 levels). On 2304, the BndEvt event named `CameraButton5` now maps to 6. | The 2311 handlers are native UFUNCTIONs bound to OnClicked (evidence 3). The super walk costs nothing and would cover a future subclass; on 2304 `W_VisualsMenu_C : UserWidget`, so it scans exactly what it scanned before. 5→6: that 2304 event's body calls `SetActiveCameraButton(self.CameraButton6)` (W_VisualsMenu.txt:465-467). This fixes the log label and the cell `cv_unpicked` skips. It is cosmetic. | High (names and bindings traced; the 2304 body read). Falsifier: on 2311 fewer than 8 `camera handler` lines, or one naming HandleCameraToggle/HandleResetSelfie; or pressing Tribe's Camera 1 while Crowd holds does not log `the camera goes back (Tribe's CameraButton1)`. |
| C4 | 378 (new) | → `[CAMVIEW] <cls>: N camera handler(s), none for the Selfie button: our button can't switch the stream` when no Selfie handler is found. | Says up front why a Crowd press would do nothing (it used to show only at press time). | High. |
| C5 | 382-383 | `W_VisualsMenu_C.SetActiveCameraButton …` → `<class found>.SetActiveCameraButton …`; `Tribe's visuals menu: 0x…` → `Tribe's visuals menu: 0x… (<class>, N live)`. | The mapping asked for this. `N live` > 1 means our button could land in a menu copy that isn't shown. | High. |
| C6 | 392-399 | Before: whenever menu + stage + functions were ready, `cv_build` ran in 3 consecutive frames (`g_cvTries<3`), and a failed menu was never retried. After: no try is spent while the menu's `SelfieCameraButton` property is still null (offset looked up once per menu class), and `g_cvTries` resets when the menu object changes. | On 2311 the tree is built by `RebuildWidget` and a second virtual (evidence 1), so the poll thread can find the menu before its buttons exist. The old code would then log `the camera menu has 0 of its buttons (Selfie MISSING)` three times in three frames and never add the button. On 2304 the Blueprint tree exists from Initialize, so behaviour there is unchanged in practice. If the property is missing entirely, `cv_build` still runs and logs why. | High that it is harmless; medium that the early-find case actually happens. Falsifier for the whole build step: `Tribe's visuals menu` is logged but `camera menu 0x…: … buttons under …` never follows while a camview stage is up. |
| C7 | 11-17, 21-22, 41, 418-419 | Comments: both builds named, 2311's layout and handler binding described. | Accuracy. | n/a |

Kept as is on purpose: `cv_select`'s call of the Selfie handler (`call_uf` with a zeroed 256-byte buffer; ParmsSize
0 passes the guard, evidence 4), the IsPressed polling, `cv_build`'s layout logic, the look copying and the FOV code.
All of these use engine classes and functions only (`UButton`, `UTextBlock`, `UVerticalBox[Slot]`, the
`GameplayStatics`/`KismetTextLibrary`/`TextBlock`/`Widget`/`PanelWidget` UFUNCTIONs), and the engine is unchanged.

## dumper.cpp edits the main agent must apply

No changes beyond the main agent's known list are needed for the selfie view. Exact text for those, all checked
against 2311:

- **dumper.cpp:3463:** `if(tgt==0){ uintptr_t st=find_live_class_sub("BP_SelfieStick_C");` →
  `if(tgt==0){ uintptr_t st=find_live_class_sub("SelfieStick");`
  This matches `BP_SelfieStick_C` (2304) and `TribeSelfieStick` (2311), and nothing else in either build
  (evidence 8). The property `CaptureComponent2D` stays.
- **dumper.cpp:3393** (cam_probe diagnostic): `find_live_class_sub("BP_SelfieStick_C")` → `find_live_class_sub("SelfieStick")`.
  The comment at 3380 still says BP_SelfieStick_C (cosmetic only).
- **dumper.cpp:1183-1187:** replace the `"TribePawnBP_C"` needle with `"TribePawn"` five times:
  ```
  g_camComp =find_live("Camera","CameraComponent","TribePawn");
  g_vrOrigin=find_live("VROrigin","SceneComponent","TribePawn");
  g_mcL     =find_live("MotionControllerL","MotionControllerComponent","TribePawn");
  g_mcR     =find_live("MotionControllerR","MotionControllerComponent","TribePawn");
  g_pawn    =find_live_class_sub("TribePawn");
  ```
  The object names and exact classes are confirmed from ATribePawn's constructor (evidence 7). The path filter
  matches `TribePawnBP_C_0` (2304) and `TribePawn_0` (2311). The class-substring match is safe (evidence 8).
- **dumper.cpp:3471** (only with `target=auto`, which camview refuses): `"TribePlayerControllerBP_C"` →
  `"TribePlayerController"`. Leave `PC_AUTOCAM_NEXTCUT` (0x974) unused until it has been re-derived.

Optional, not needed for parity with 2304: drone_poll takes the first live selfie stick. In a room with several
sticks it could fly one other than `TribePlayerController.ActiveSelfieStick` (+0x988 on 2311), which is the one
HandleSelfieCamera puts on the stream. 2304 had the same behaviour. Change it only if the headset shows the stream on
one stick while another one moves.

Also checked and fine: `drone_dump_enum_once` looks up `/Script/TribeXR.EAutoCamMode`, which exists in both builds,
so it stays a one-shot. Every other name drone_poll/drone_update/drone_load_path use is an engine path
(`SceneComponent.K2_*`, `RelativeLocation/Rotation`) or mod data. `SpectatorCameraAutoCam` and `drone_dump_pc_once`
are auto-only.

## Untested / needs the headset

Preconditions (other pieces): new PE / np / ga addresses; the avatar load reaching
`[LOAD] follow: … cam=0x… … pawn=0x…` with both non-zero (this is also the game-thread tick); Graveyard up through
the env menu or `active_env.txt`; the tribemod files from mapping target 12 (`camview.halloween.txt` v2,
`drone_path.halloween.txt`, `drone.txt mode=path`).

Expected first-launch log, in order:
1. `[CAMVIEW] camview.halloween.txt: button 'Crowd', camera (170, -2730, -90) looking at you, fov 60, sway 3 cm`
2. `[CAMVIEW] UMG: IsPressed 0x… SetVisibility 0x… AddChild 0x… TextToString 0x…; SpawnObject 0x… SetText 0x…`, all
   non-zero.
3. Eight `[CAMVIEW] camera handler N: HandleCamera1 -> CameraButton1` … `HandleCamera6 -> CameraButton6` …
   `HandleSelfieCamera -> SelfieCameraButton` lines, in any order. There must be no HandleCameraToggle or
   HandleResetSelfie line.
4. `[CAMVIEW] TribeVisualsMenuWidget.SetActiveCameraButton 0x… params: Button:ObjectProperty`
5. `[CAMVIEW] Tribe's visuals menu: 0x… (TribeVisualsMenuWidget, 1 live)`. If it says 2 or more, note it (see the
   risks).
6. `[CAMVIEW] offsets: … UserWidget.WidgetTree@632` (0x278, as the builder uses).
7. `[CAMVIEW] camera menu 0x…: 8 buttons under VerticalBox VerticalBox_117; one row; target row VerticalBox
   VerticalBox_117 (9 children), template cell Button CameraButton8 (CameraButton8)`
8. About 24 `[CAMVIEW] tree …` lines matching the tree in evidence 2.
9. `[CAMVIEW] clone Button CameraButton8 -> 0x…, N setters: …` and `clone   TextBlock CameraText8 -> 0x…`
10. `[CAMVIEW] looks when ours was added: …`. The unpicked camera buttons should share one hash.
11. `[CAMVIEW] added 'Crowd': cell 0x… (VerticalBoxSlot in VerticalBox_117), button 0x…, label 0x…; build 1`
12. Stick out: `[DRONE] resolve (selfie stick): capture=0x…` (not 0).

In the headset, on Graveyard with the stick out:
- A "Crowd" button appears at the bottom of the camera list, unhighlighted.
- Pressing it logs `[CAMVIEW] 'Crowd' picked: the selfie camera holds at (170, -2730, -90), fov 60` without
  "(no selfie camera resolved yet)", then `[CAMVIEW] stream camera FOV <Tribe's> -> 60.0 deg`. The stream shows the
  crowd view, and the Selfie button loses its highlight to ours.
- `[DRONE] … selfie view … drift≈0cm` appears every 5 s. A large drift means the C++ stick moves its capture and
  fights us.
- Pressing Tribe's Camera 1 logs `[CAMVIEW] the camera goes back (Tribe's CameraButton1)`, then
  `the stream camera's FOV is Tribe's again (…)`, and the reel resumes.

## Risks

- **Silent, outside this file:** no avatar load means no tick and no `g_camComp`, so nothing in the selfie view runs.
  No env-menu stage means camview never arms. Watch for the `[LOAD] follow:` line and a `[CAMVIEW] camview.halloween.txt`
  line.
- **First run of the clone path on any build.** The 2304 `added` line was never seen either. If cloning fails it
  logs why and adds nothing (fail-safe). The crash surface is limited to engine setters called on engine widgets.
  Copying `WidgetStyle` bytewise can over-retain Slate brush handles (a small leak, not a crash), the same as on 2304.
- **More than one live menu:** our button goes into the newest one. The `N live` count will show if that is the wrong
  one.
- **Highlight (cosmetic):** `cv_unpicked` votes by a hash of every style property. If the eight buttons don't share
  one unpicked hash, our cell's highlight can be wrong. The `[CAMVIEW] looks` lines show this.
- **Crowd pressed with no stick out:** HandleSelfieCamera does nothing, so the stream stays where it was, while camview
  still marks the view as held. 2304 behaved the same, and it is not a crash.
- **Not verified offline:** whether UButton's `+0x568` is `OnClicked` or another of its dynamic delegates. Any of them
  dispatches through ProcessEvent, so camview_pe sees it either way.
