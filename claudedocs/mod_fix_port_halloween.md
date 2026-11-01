# Graveyard Shift (Halloween stage) on Tribe 0.12.6 (2311): the port

2026-10-31. Edited only `backup/mod_fix_work/halloween/{dumper.cpp, club.cpp, intro.cpp, head.cpp}` (copies of `hook/`,
byte-identical to `backup/mod_fix_work/original/hook/`). Nothing was built, signed, pushed or run. "copy L" = line in my
copy, "orig L" = line in the original. Work list: claudedocs/mod_fix_halloween.md sections 4-7.

## Answer first

1. **Every Blueprint lookup on the stage's path now tries the 0.12.6 C++ name first and keeps the 2304 name as a
   fallback.** That can't change 2304: its library has no native TribeEnvironmentSkin, TribeSkinItemWidget,
   TribeVisualsMenuWidget, TribeMainGameState, TribeRig, TribeDeck, TribePlayButton, TribeSelfieStick or mixer classes
   (their UTF-16 registration names are absent). Of the classes involved, 2304 has only TribeGameState,
   TribeVisualsManager, TribePawn and TribeEquipmentBase as native.
2. **The menu click path on 2311 is known now (read from the library), and the hook listens to it.** A press on a box
   runs `UTribeSkinItemWidget::NativeOnMouseButtonDown`. Its first act is the engine's `UUserWidget::NativeOnMouseButtonDown`,
   which raises `/Script/UMG.UserWidget.OnMouseButtonDown` through ProcessEvent with the box as `self`. Then it calls
   `VisualsManager.ApplySkinToPlayer(Skin)` -> `Skin->ApplySkin(LocalPawn)`; for an environment skin that sets the
   environment, then broadcasts `Skin.OnApplied`. InitSkinItem had bound that broadcast to the box's `OnSkinApplied`
   with AddDynamic, so it arrives through ProcessEvent too. The hook takes the press (and, guarded, the apply). Nothing
   can be swallowed: Tribe's apply is native, so it puts on The Void itself, because our object carries the Void's identity.
3. **Labels:** Tribe fills a box natively (no ProcessEvent), so the hook reads the list's own
   `EntryWidgetPool.ActiveWidgets` once a second and relabels the boxes whose `Skin` is ours.
4. **SetupEnvironmentBackdrop (2311 signature):** the native body null-checks all four object parameters, but it reads
   `BackdropMesh+0x290` without a class check. The hook passes our screen (checked to be a StaticMeshActor), the manager's
   own three lights (the weak half of each TSoftObjectPtr is resolved against GUObjectArray and class-checked) and its
   LightDimFactor. If anything doesn't resolve, it does **not** call (logged, retried every 3 s).
5. **Without a click:** `tribemod/active_env.txt` = `Graveyard Shift`. (`env_autotest` loads the *first* envs.txt line,
   which is Dino Stage today.)
6. **Main agent:** nothing to apply inside its regions. The stage depends on its `g_pawn`, `g_camComp`, `g_mcL/R`.

## 1. What was read from the 2311 library (store vaddrs)

Method: the UHT tables, parsed as the map did (FClassRegisterCompiledInInfo -> FClassParams -> PropPointers /
FuncInfo; 5.4 FFunctionParams has OwningClassName and DelegateName, so PropertyArray sits at +40). Code was disassembled
with capstone, starting from FNameNativePtrPair exec thunks, vtables found through constructors, BL/ADRP xrefs and UTF-16
literal xrefs. The throwaway scripts lived in %TEMP% and were deleted.

| # | Claim | Evidence | Conf. |
|---|---|---|---|
| R1 | A press on a skin box raises `UserWidget.OnMouseButtonDown` through ProcessEvent before Tribe applies the skin | 0x5B4C890 sits in a vtable (slot data 0x8148710). It first does `bl 0x3885CFC` (= `UUserWidget::NativeOnMouseButtonDown`: it copies the FGeometry, calls the BP-event thunk 0x3875EFC and returns its NativeReply). The thunk does `FindFunctionChecked(FName @0x8A46198)` and then `ProcessEvent` (vtable +0x270). That FName is built from UTF-16 "OnMouseButtonDown" (static init at 0x389B5A4: base 0x8A460A0 + 0xF8). Then 0x5B4C890 checks the Skin. If it's owned (+0x58), has no addon, and the box isn't selected (+0x350) or the skin can re-apply (vslot 0x300), it calls `ApplySkinToPlayer` (0x5B4C9E4). If it isn't owned, it broadcasts OnSkinPurchaseRequested instead | high |
| R2 | ApplySkinToPlayer applies the skin to the local pawn | 0x5B46D8C: `Skin->vslot 0x2D0 (ApplySkin)(GameState(+0x7C0)->LocalPawn(+0x420))` | high |
| R3 | ApplySkin sets the environment, then broadcasts OnApplied | `UTribeSkinBase::ApplySkin` 0x5B47570 (UTribeEnvironmentSkin doesn't override it; its vtable is 0x7FE8E20, from its ctor 0x5B3C1E4). It calls vslot 0x308 (the environment skin's 0x5B3C394 sets the environment from `EnvironmentType` @0xA0), then 0x5A330D0 (pawn), then tail-calls 0x37D6E38(this+0x70, this, Pawn) -> ProcessMulticastDelegate 0x19F15BC | high |
| R4 | The box listens to its skin's OnApplied | `InitSkinItem` 0x5B4B030 removes the old Skin's bindings, sets `Skin` (+0x2F0), then `AddDynamic(this, "OnSkinApplied")` on `InSkin+0x70` (the only uses of the UTF-16 literal: 0x5B4B830 / 0x5B4B8E0). The box's `OnSkinApplied` and `UnlockAndApplySkin` are empty (`ret`, 0x15D7CA4) | high |
| R5 | A box fill never reaches ProcessEvent | 0x5B4AB50 (the only native caller of InitSkinItem besides its thunk) casts the item to TribeSkinBase and tail-calls InitSkinItem. It does not raise `UserObjectListEntry.OnListItemObjectSet` | high (that 0x5B4AB50 is NativeOnListItemObjectSet: medium) |
| R6 | No other environment-click entry point exists | `UTribeSkinItemWidget::ApplySkin` (0x5B4C644) has no native caller apart from its exec thunk. None of TribeVisualsMenuWidget's UFUNCTIONs handles environments (the Handle* ones are cameras and visual toggles) | high |
| R7 | SetupEnvironmentBackdrop's body | 0x5B58958 (exec 0x5419C98; x1 BackdropMesh, x2/x3/x4 lights, d0 dim). `str x1,[x0,#0x2d0]`; if x1 and mode byte +0x8F4: `ldr x0,[x1,#0x290]` (AStaticMeshActor.StaticMeshComponent, **no class check**) -> SetMaterial(0, video/GIF/NDI material). Each light: `cbz` -> soft pointer reset and intensity 0; else FSoftObjectPath(obj), weak assign (0x1A3646C), intensity read from +0x2A0 (ASpotLight.SpotLightComponent) or +0x290 (ASkyLight.LightComponent), then +0x244. Then (conditionally) a 2.0 s timer, and `str d8,[x19,#0x7a8]` (LightDimFactor) | high |
| R8 | How the weak half of a soft pointer resolves | `FWeakObjectPtr::Get` 0x1A366AC: serial @+4 (0 = null), index @+0 (<0 = null), NumElements at GUObjectArray+0x24, item stride 0x14, item serial @+0x10, item flags @+8 tested against a GC mask \| 0x200000 (Garbage). Soft pointer = weak (8) + FTopLevelAssetPath (16) + SubPathString (16) = 0x28, which matches the 0x720/0x748/0x770 spacing | high |
| R9 | Reflection | TribeDeck -> TribeMixerChannelDevice -> TribeEquipmentBase. TribeChannelVolumeSlider -> TribeMixerSliderBase -> TribeSliderBase. TribeChannelColorKnob -> TribeChannelKnobBase -> TribeMixerKnobBase -> TribeKnobBase. TribeMainGameState -> TribeGameState. TribePlayButton -> TribeBaseDeckControl, `Deck` ObjectProperty @0x4C8 -> ATribeDeck (`GetTribeEquipmentBase` exists nowhere). The ReturnValues of GetIsPlaying (Bool), GetPlaybackSeconds (Double), GetCurrentTrackDisplayName (Str) and IsAtCue (Bool) carry flags 0x580 (Parm\|OutParm\|ReturnParm), so `fn_out` takes them. `call_ret` reads ReturnValueOffset (+0xB8), which the engine sets for native functions too. ATribePawn has `bHost`/`bDJing` (bitfields), `Role` is AActor's @0x150. All other offsets are as in the map | high |
| R10 | The list's entry pool is reflected | `UListViewBase.EntryWidgetPool` StructProperty @0x1C8; `FUserWidgetPool.ActiveWidgets` Array @0, `InactiveWidgets` @0x10 | high |
| R11 | Name collisions in 2311 | "SelfieStick": only ATribeSelfieStick. "TribeRig": also UTribeRigSkin and **UTribeRigSaveGame**. "PlayButton": also ATribeAcidSynth- and ATribeDrumMachinePlayButton (the intro walks the class chain from TribePlayButton, then matches by Deck) | high |
| R12 | The stick events are gone | ATribePawn's `Input_ThumbStickX_Axis`/`Y_Axis(TribeController, AxisValue double)` have no UTF-16 FName literal, so nothing binds them by name, and native calls never pass ProcessEvent | high |

## 2. Changes

| # | File:line (copy) | Before -> after | Why | Conf. | Falsified by |
|---|---|---|---|---|---|
| H1 | dumper.cpp L2199-2206 (after orig L2197) | new: `g_emMode` (0 unknown, 1 = C++ menu, 2 = Blueprint menu), `g_emWCls`, `g_emFnUWDown`, `g_emFnSkinApplied`, `g_emOffWSkin` | state for the 2311 routes | high | - |
| H2 | dumper.cpp L2250 (orig 2240) | `"TribeMainGS_C"` -> `"TribeMainGameState"` or `"TribeMainGS_C"` | T4 | high | gs stays 0 although `[ENV] GetGameState gave nothing ...` ran (only used when GetGameState fails) |
| H3 | dumper.cpp L2269-2292 | new helpers: `em_find_live_pl` (exact class, live, in a level), `em_is_a` (class chain by name), `em_soft_get` (R8, reads only) | T9, T11, T19 | high | - |
| H4 | dumper.cpp L2368-2420 (orig 2331-2354) | manager: exact `"TribeVisualsManager"`, then `"BP_TribeVisualsManager_C"`. If the function has the 2311 parameters (by name; types checked: 3x ObjectProperty + DoubleProperty, each within ParmsSize), `em_backdrop_2311` fills them. Our screen must be a StaticMeshActor. Booth/Backdrop spots must resolve to SpotLight, the room sky light to SkyLight, LightDimFactor must be a finite DoubleProperty. Any failure: no call, one log line, retried (every 3 s, 20 tries, as before). The 2304 path is unchanged | T10, T11, R7 | high (signature, null handling), medium (that the Void's own lights are the right ones to hand back) | `[ENV] visuals: ... NOT called` lines that never stop; a crash right after `[ENV] visuals: 2311 signature, handing back ...` |
| H5 | dumper.cpp L2462-2484 | new `em_pe_2311` (game thread, from repl_pe). (a) `UserWidget.OnMouseButtonDown` on a TribeSkinItemWidget (class chain) whose `Skin` is ours: map the box, log, `em_click`. Every skin-box press stamps a time. (b) `TribeSkinItemWidget.OnSkinApplied(AppliedSkin, Pawn)`: our object -> `em_click`, but only if it isn't already up/loading and (a press came within 1 s, or no press was ever seen). A stock TribeEnvironmentSkin applied within 1 s of a press while ours is up -> unload request. Nothing swallowed | T6, R1-R4. OnSkinApplied also fires for Tribe's own re-applies, hence the press window | medium-high (from the code), low until seen on device | no `[ENV] press on our box` and no `[ENV] Tribe applied our skin object` after pressing our box |
| H6 | dumper.cpp L2488-2500, L3259-3263 (orig 3144-3145) | new `em_pool_scan`: list -> `EntryWidgetPool` (struct via FStructProperty::Struct at sizeof(FProperty)) -> `ActiveWidgets` -> boxes whose `Skin` is ours get mapped. The label loop (2311) drops a mapped box whose Skin is no longer ours before it relabels | T6 labels, R5, R10 | medium | our boxes show Tribe's name for The Void while `[ENV] the list's boxes: EntryWidgetPool@456 ActiveWidgets@0` was logged |
| H7 | dumper.cpp L2593, L3310, L3314-3320 (orig 2485, 3192, 3196) | while our stage is up (2311 only), about every 5 s: if `TribeVisualsManager.BackdropStaticMeshActor` is no longer our screen, register again. At most 6 times per load | a slow Void (2311's new loading screen, T1) can register its own backdrop *after* ours and silently take Tribe's visuals back | medium | `[ENV] visuals: Tribe's backdrop is now ...` 6 times on every load (something legitimately swaps it, e.g. the Key Backwall): then remove this |
| H8 | dumper.cpp L2816-2818, L2833-2835, L2846-2847 (orig 2707, 2722-2723, 2734) | mixer base classes: the C++ paths when the deck class is native (its meta-class is `Class`), else the BP paths. Fader/filter: is-a `TribeChannelVolumeSlider` / `TribeChannelColorKnob`, or the BP names | T19, R9 | high (names, chains); medium (that the slider/knob travel is still about +-2.2 / +-150) | `[MIX] 0 channel faders` or `NOT usable`; levels stuck at 0 or 1 |
| H9 | dumper.cpp L2966-2981 (orig 2853-2864) | deck class `/Script/TribeXR.TribeDeck` (3 tries), then the BP path. The three functions come from the class's function list (`em_find_child_func`) instead of three full-path scans (same functions on 2304). The log prints the class name | T18, R9 | high | `[SONG] TribeDeck ...: ... out @-1` |
| H10 | dumper.cpp L3346-3347 (after orig 3221) | repl_pe: `if(g_envMenuOn&&func&&parms&&(func==g_emFnUWDown\|\|func==g_emFnSkinApplied)) em_pe_2311(...)` | two pointer compares per call; both 0 on 2304 | high | - |
| H11 | dumper.cpp L3671-3676 (orig 3544) | 2311: the live `TribeVisualsMenuWidget.EnvironmentList` (it must be a live ListView); the old name route stays as the fallback | T7 | high (names), medium (that this list hosts the boxes on device) | `[ENV] TribeVisualsMenuWidget ...: EnvironmentList@1072 = ... not a live ListView yet` forever |
| H12 | dumper.cpp L3687, L3705-3715 (orig 3555, 3573-3579) | Tribe's environment items: class `TribeEnvironmentSkin` or `BP_EnvironmentSkin_C`. The Void item by Name `Environment_Void`, and on 2311 also by `EnvironmentType == Void` (logged) | T5 | high (class), medium (row name) | `[ENV] added box ... (WITHOUT the Void's identity: not found)` |
| H13 | dumper.cpp L3725-3731, L3761-3762 (orig 3590-3593, 3624) | probe (probe_on only): C++ paths first, the BP paths as the fallback | PR_PATH | high | - |
| H14 | dumper.cpp L3830-3843 (orig 3692) | menu-mode detection: `TribeEnvironmentSkin` found -> mode 1. Then: `g_emCls` = it, TribeSkinItemWidget and its `Skin` offset, `/Script/UMG.UserWidget.OnMouseButtonDown`, `TribeSkinItemWidget.OnSkinApplied`. Otherwise (after 3 tries) mode 2: the old Blueprint lookups, unchanged. On 2311 those four scans no longer repeat forever | T5-T7 | high | `[ENV] Blueprint menu (2304)` on a 2311 install |
| H15 | dumper.cpp L3859-3860 (orig 3710) | rig: exact `TribeRig` (mode 1), the `BP_Rig_C` substring (mode 2) | T9, R11 | high | `[ENV] DJ rig actor` missing, or a TribeRigSaveGame address |
| H16 | dumper.cpp L3866-3876 (orig 3711-3715) | 2311: if `SM_BackdropScreen` isn't found by name, hide `TribeVisualsManager.BackdropStaticMeshActor`, but only if its path is in `Environment_Void` (never ours, never the environment we came from). One log line if the chroma screen isn't found by name | T13 | medium | `[ENV] step 2/4 ... hid 0 Void screen(s)` with no fallback line, and the Void's wall visible inside the stage |
| H17 | dumper.cpp L2071-2074 (orig 2071-2072) | skin_trace (diagnostic): also logs TribeSkinItemWidget, Tribe\*Skin\*, VisualsMenu, UserObjectListEntry and UserWidget mouse functions | the map's T6 suggestion | high | - |
| I1 | intro.cpp L31-33, L36-38 | comments; new `g_irBtnDeckOff` | T24 | - | - |
| I2 | intro.cpp L81-88 (orig 80-81) | play-button class: `/Script/TribeXR.TribePlayButton` when the deck class is native, else the BP path. Use `GetTribeEquipmentBase` if the class has it (2304), else the `Deck` ObjectProperty (2311); one log line says which | T24, R9 | high | `[INTRO] play buttons: ... its deck by NOTHING` |
| I3 | intro.cpp L197-200 (orig 190) | `intro_deck_button`: 2311 matches `button.Deck == deck` | T24 | high | `[INTRO] deck N: its play button isn't found` with a `button:` line in intro_deck.txt |
| I4 | intro.cpp L136 (orig 129) | `"BP_SelfieStick_C"` -> `"SelfieStick"` (the same as the main agent's 3393/3463) | T23, R11 | high | `[INTRO] screen ...: the selfie stick's preview plane 0x0` with the stick out |
| I5 | intro.cpp L147 | log text only | - | - | - |
| D1 | head.cpp L282 | `"BP_SelfieStick_C"` -> `"SelfieStick"` | T23 | high | no `[HEAD] selfie-stick camera` with the stick out |
| C1 | club.cpp L38-39, L84-86, L170-171 | comments; the stick-event log adds "-> not all there (0.12.6 has none): the sticks come from GetInputAnalogKeyState" | T20/T21, R12. **No functional change:** `club_sticks` sets `ev=false` when any `g_cAxFn` is 0 and then uses the polled keys (copy L236-246); `club_resolve` reads `VROrigin`/`Camera`/`Role`/`bHost`/`bDJing` by name from GetPlayerPawn's pawn | high (code path), medium (that GetInputAnalogKeyState sees the Quest sticks on 2311) | no `[CLUB] probe P2: the OculusTouch_* (or MotionController_*) keys carry the sticks` after moving a stick on the stage |

All four files keep their brace/paren balance against the originals (a string-and-comment-stripped count; nothing was compiled).

## 3. Changes the main agent must apply in its regions

None. For the merge:
- My repl_pe insertion follows orig L3221 (the end of the environment block). The unchanged avatar block (orig
  3222-3229) separates it from the region starting at 3230. My other hunks start at orig 2068 and end at 3718.
- New names (check for clashes): `em_find_live_pl`, `em_is_a`, `em_soft_get`, `em_backdrop_2311`, `em_pe_2311`,
  `em_pool_scan`, `g_emMode`, `g_emWCls`, `g_emFnUWDown`, `g_emFnSkinApplied`, `g_emOffWSkin`, `g_emPressMs`,
  `g_emPressSeen`, `g_emReReg`, `PR_PATH_BP` (dumper.cpp); `g_irBtnDeckOff` (intro.cpp).
- The stage needs from your region: `g_pawn` (show_set, giant_world_time, giant_tick, intro_tick and the club's world
  context all require it), `g_camComp` (giant_tick returns early without it, and the intro's "at the decks"), and
  `g_mcL`/`g_mcR` (the intro's backstage button). With no pawn, the stage loads but its lights run free and the intro
  stays off.

## 4. What I did not port, and why

- **Avatar/skin menu** (W_SkinItem_C, W_ProfileMenu_C, BP_ReadyPlayerMeAvatarSkin_C, `g_apply_fn` at 918, `is_rpm_skin`
  at 937, `sm_*`) and the dump/diagnostic code at 518-607: out of scope. Note: the re-seed touches `tribemod/skin_menu`,
  so on 2311 `skin_menu_poll` keeps retrying its Blueprint lookups (three full-path object scans every ~6 s on the poll
  thread, forever). Harmless but wasteful; whoever ports the avatar menu can gate it as H14 does. The shared helpers
  (`box_set_label`, `sm_spawn`, `sm_list_*`, `make_text`, `menu_resolve_engine_fns`) are unchanged.
- **TribeControllers_C** (hands, 1667/1674) and camview.cpp's `W_VisualsMenu_C`: other pieces.
- **The club gate** reads `bHost`/`bDJing` as whole bytes, not bit-masked. This is pre-existing, and Halloween's walking
  map has no `gate` lines (its "gate_*" names are ordinary boxes), so I left it.
- **intro_deck.txt's calls:** on 2311 `PlayNetSynced(NetSyncPacket)` takes a 152-byte struct by const reference, which
  intro_deck.txt can't fill (struct parameters are skipped, so it's zeroed). `StopNetSynced(PositionMs, Timestamp)` takes
  two doubles; `TribePlayButton`'s calls are `OnPlay(PlayingDeck)` and `OnPause(PausedDeck)`. What a real press calls on
  2311 needs the deck capture (`tribemod/log_deck`) on the headset; the hook only executes what the file says.
- **Giving the Void its backdrop back** when ours unloads but the Void stays (picking stock "The Void" while ours is
  up): 2304 didn't do this either. The next environment's level registers its own.

## 5. Untested / needs the headset

**Loading Graveyard Shift without a menu click.** Needed in `tribemod/`: `executor_on`, `auto_load`, `auto_actor`,
`env_menu` (the re-seed touches all four), and `envs.txt` with `Graveyard Shift=/Game/Mods/Halloween/Maps/Environment_Halloween`
(line 4 of today's file). Then write `active_env.txt` containing exactly:

```
Graveyard Shift
```

It applies once per launch, after Tribe's own environment has held the same value for ~8 s. The hook deletes
active_env.txt when a load fails and rewrites it on each successful pick. `env_autotest` (one-shot) loads the
**first** envs.txt line, so to test with it, move the Graveyard line to the top.

**First-launch log lines to expect (2311), roughly in order:**
- `[ENV] ETribeEnvironmentType ... Void = 3`, `[ENV] fns: ... SetEnvironment=0x... Void=3`
- `[ENV] 2311 menu (C++): TribeEnvironmentSkin=0x... TribeSkinItemWidget=0x... Skin@752 | press UserWidget.OnMouseButtonDown=0x... | apply TribeSkinItemWidget.OnSkinApplied=0x...`
  (any 0 there, or the trailing "-> our boxes can't see a press", means only the no-click route works)
- `[ENV] box 3: 'Graveyard Shift' -> /Game/Mods/Halloween/Maps/Environment_Halloween`, `[ENV] ON`
- `[ENV] live environment list = 0x...`, `[ENV] Tribe's 'The Void' list item = 0x...`, `[ENV] DJ rig actor = 0x...`
- `[ENV] game state's environment property: CurrentEnvironment (EnumProperty) @0x308`, `[ENV] game state = 0x... class=TribeMainGameState ...`
- `[ENV] auto: re-applying 'Graveyard Shift' ...`, `[ENV] clicked 'Graveyard Shift' -> ...`, `[ENV] step 1/4: SetEnvironment(Void=3) ...`
- `[ENV] Void SM_BackdropScreen = 0x...` **or** `[ENV] Void backdrop (not found by name): the visuals manager's BackdropStaticMeshActor ...` (T13)
- `[ENV] step 2/4: environment now 3 (Void); hid N Void screen(s)`, `[ENV] Void SM_BackdropScreen: loc=(...)`, `[ENV] DJ rig: loc=(...)`
  (T14: compare with a 2304 log; the stage, walking map, Crowd camera and intro path assume the rig at the origin)
- `[ENV] step 3/4: ... success=1 stream=0x...`, `[ENV] *** 'Graveyard Shift' is IN (visible after N s) ***`
- `[ENV] visuals: 2311 signature, handing back the manager's booth spot 0x..., backdrop spot 0x..., room sky light 0x..., dim factor X`,
  then `[ENV] visuals: our screen 0x... is Tribe's backdrop now ...` (or `... NOT called yet` lines, which retry)
- `[GIANT] show bus: MPC_HwShow 0x... (gen 1), 19/19 parameters: the light show runs here, no giant intro`
- `[SONG] TribeDeck 0x...: GetIsPlaying out @0 BoolProperty, GetPlaybackSeconds out @0 DoubleProperty, GetCurrentTrackDisplayName out @0 StrProperty, CurrentTrackFileName @856 StrProperty`,
  `[GRID] BeatgridBpm @1848 8B, BeatgridStartMs @1856 8B`, `[SONG] N deck(s)`
- `[MIX] N channel faders (CurrentSliderOffset @1232, 8B), M filters (CurrentKnobRotationYaw @1248, 8B), deck MixerChannel @720 4B -> following the faders`
  (N, M = the mixer's channels)
- `[CLUB] stick events on TribePawnBP_C: LX 0x0 ... -> not all there (0.12.6 has none) ...`, `[CLUB] walking map halloween_collide.txt: ...`,
  `[CLUB] on: 'Graveyard Shift' is up`, `[CLUB] local pawn 0x... (TribePawn...): VROrigin@960 Camera@968 Role@336 ...`,
  `[CLUB] key names: OculusTouch_Left_Thumbstick_X ...`, then on the first stick push: `[CLUB] probe P2: the OculusTouch_* keys carry the sticks ...`
- `[INTRO] intro.halloween.txt: ...`, `[INTRO] the deck's IsAtCue 0x..., out @0 BoolProperty`, `[INTRO] ready on this stage: ...`,
  and once intro_deck.txt is read: `[INTRO] play buttons: TribePlayButton 0x..., its deck by the Deck property`
- `[HEAD] resolved: ...`; with the selfie stick out: `[HEAD] selfie-stick camera 0x... (the boo target)`

**Then the menu (one press):** open Visuals > Environments, look for the Graveyard Shift box (label set within ~1 s),
press it once. Expect `[ENV] press on our box 'Graveyard Shift' (UserWidget.OnMouseButtonDown)` then `[ENV] clicked ...`.
Tribe also switches to The Void by itself at that moment (it applies our object). If neither line appears, create
`tribemod/skin_trace`, press again and read the `[SKIN]` lines.

**Watch list:**
- The press runs Tribe's native `ApplySkinToPlayer` on a skin object we spawned. 2304 swallowed this; 2311 can't. It
  carries the Void's Name, EnvironmentType and bOwned, so Tribe treats it as The Void. Native code that reads its
  un-copied fields (SkinInfo, thumbnail, Addon) is unverified. A crash there is loud and comes right after the press
  line. **Test the no-click route first.**
- No `g_pawn` means no lights (free 140 BPM loop) and no intro: the `[LOAD] follow: ... pawn=0x0` line (main agent).
- T1: 2311 may show a loading screen during step 1. If the Void finishes after our level, H7 re-registers the backdrop.
  Watch for `[ENV] visuals: Tribe's backdrop is now ...`.

## 6. Mapping items found missing or wrong

- **T6** "unknown (new click path)": now read statically (R1-R5). The engine's `UserWidget.OnMouseButtonDown` *is* raised
  through ProcessEvent (the native override calls the engine's first), and `OnSkinApplied` is a dynamic-delegate
  handler. `OnListItemObjectSet` really is gone from the ProcessEvent path, so labels need the pool scan.
- **T11:** the map called null-checking "unknown". The native body null-checks all four object parameters but reads
  `BackdropMesh+0x290` unchecked (R7), so passing nulls would not have crashed in this function. Passing back the
  manager's values keeps the Void's lighting.
- **T19:** the super chains the map left unextracted are confirmed (R9).
- **T9:** `"TribeRig"` is also a substring of `UTribeRigSaveGame`, not only TribeRigSkin.
- **Section 8, step 6** ("load Graveyard Shift via active_env.txt/env_autotest"): env_autotest loads box 0 (Dino Stage
  with the current envs.txt). Only active_env.txt targets Graveyard.
- **T24:** besides `Deck`, note that `PlayNetSynced` (the "play=PlayNetSynced" probe result) takes a 152-byte struct,
  which intro_deck.txt can't fill.
- **T20:** `bHost`/`bDJing` exist on ATribePawn as bitfield bools; club.cpp reads whole bytes (pre-existing; no gates
  on this stage).
