# Characters on Tribe 0.12.6 (2311): the avatar menu, Tribe's own avatar, every character

2026-10-31, afternoon. Read-only work. Nothing was built, signed, installed or pushed. On the headset I ran only `ls`,
`md5sum`, `logcat -d` and one `pull` of `tribemod/load_result.txt` (md5 checked). Scratch files are in
`backup/mod2311_work/chars/`: `refl2311.py` (reads the 2311 reflection tables), `dis2311.py` (disassembly helpers),
their outputs `refl_avatar.txt` and `refl_meta.txt`, and the pulled `load_result_1500.txt` (33.6 MB).

Store addresses below are vaddrs in `backup/mod_fix_work/lib/libUnreal.2311.store.so`. The hook's runtime address is the
store vaddr + 0x1000. Line numbers are in `backup/mod_fix_stream_fix/src/dumper.cpp` (md5 aae4996a).

Every claim carries a tag:
- **[obs]**: observed. I read it in a file, the library or a log, or I ran it.
- **[der]**: derived from observed facts. The steps are given.
- **[asm]**: assumed. What would prove it wrong is given.

## Answer first

**What is broken, and why**

1. **The avatar menu still looks for 2304 Blueprints.** It asks for `BP_ReadyPlayerMeAvatarSkin_C`, `W_SkinItem_C`
   events and a `W_ProfileMenu_C` event (dumper.cpp:3706-3709) **[obs]**. 2311 has the C++ classes
   `UTribeProfileMenuWidget`, `UTribeSkinItemWidget` and `UTribeReadyPlayerMeAvatarSkin` instead **[obs]**. New names
   alone won't fix it. On 2304 the mod swallowed the click. On 2311 a press runs in Tribe's C++
   (`UTribeSkinItemWidget::NativeOnMouseButtonDown`, store 0x5B4C890). That code applies the box's skin itself after it
   raises the one event the hook can see (decoded, section 1.3) **[obs]**. The menu must be ported the way the stage
   menu was.
2. **"Lookups 0 in some sessions" is timing, not names.** `skin_menu_poll` never calls `ensure_resolved()`. It relies
   on the auto-load branch, which runs only once the ProcessEvent hook is in (dumper.cpp:4031). In the 13:40 launch the
   hook never installed, so the object list stayed empty: `[STREAM] diag objects: 0 matched, 0 in the array`
   **[obs]**. All seven engine paths are unchanged in 2311 **[obs]** (map T8; `ListView` re-checked here).
3. **Both avatars show because the mod never hides Tribe's avatar, and it draws an extra copy of its own.**
   - The mod puts its mesh on Tribe's RPM slot (`AvatarBodyMesh`) and forces it visible (dumper.cpp:1296, 1005-1009)
     **[obs]**. On 2311 that slot sits at world (0,0,0), and it was drawn in 7 of 17 launches today (`RENDER ... slot:
     WasRecentlyRendered(0.5)=1 | loc=(0,0,0)`) **[obs]**.
   - Tribe's own avatar is the local pawn's `TribeAvatar` component (`ATribePawn` +0x3F0) **[obs]**. Its body is
     "visible in scene capture only" when you don't see it yourself (decoded, 2.1) **[obs]**, so the stream and selfie
     camera show it **[der]**. Nothing in the mod hides it **[obs]**.
   - Which of the two the user saw is one diagnostic line away (2.3). The fix covers both.
4. **Where the RPM box comes from.** 2311 fills the avatar list from `VisualsManager.RPMAvatarSkins` (cached RPM
   avatars), then `DT_OculusAvatarSkins`, then `OculusAvatar_Custom` (decoded, 1.4) **[obs]**. So the RPM box is missing
   when that map is empty **[der]**. Why it is empty on this headset is not settled offline **[asm]**: one diagnostic
   line lists the boxes.
5. **Characters.** Skullbuck, Gremlin and Horseman loaded on 2311 today: 20 loads, all `mesh(materials)` non-null, body
   tracking re-rigged **[obs]**. Lampwing, Major Tom and Santa were never tried on 2311 **[obs]**. No `[HEAD]` line from
   2311 survived the logcat rotation, so the heads are unverified **[obs]**. Their code needs no 2311 change beyond the
   `SelfieStick` name, which is already ported **[der]**.

**The fixes** (section 4)
- **C1-C5, the avatar menu on 2311.**
  - Resolve before looking up anything.
  - Find `TribeProfileMenuWidget.AvatarList` and spawn our boxes as `TribeReadyPlayerMeAvatarSkin` named
    `ReadyPlayerMe_Custom`. Tribe's own apply on a press can't be stopped, and with that name it only re-applies its RPM
    avatar.
  - Label the boxes from the list's `EntryWidgetPool`, and catch a press through `UserWidget.OnMouseButtonDown` or
    `TribeSkinItemWidget.OnSkinApplied`, as the stage menu does.
- **C6-C8, Tribe's own avatar.**
  - While a mod skin is on, hide Tribe's avatar with one engine call, `SetHiddenInGame(true)` on the pawn's
    `TribeAvatar`. Tribe's own code forwards that flag to whichever avatar is active (decoded, 2.4).
  - Show it again when a Tribe avatar box (RPM) is picked.
  - Stop putting our mesh on Tribe's slot on 2311.
- **C9-C12, small fixes.**
  - Retire the dead 2304 skin-cycle hook.
  - Add a one-shot diagnostic.
  - Fix the per-frame follow log, which has grown `load_result.txt` to 33.6 MB.

**What only the headset can settle:** the box class `AvatarList` uses, H1 vs H2 (2.3), and why `RPMAvatarSkins` is empty.
C11 logs all three on the first menu open.

## 1. The avatar menu on 2311

### 1.1 Tribe's classes

How they were found **[obs]**: `refl2311.py` parses UHT's compiled-in tables in the store library. The steps are
`FClassRegisterCompiledInInfo` (UTF-16 name) → `FClassParams` (matched by its `StaticClass` pointer) → `PropertyArray` /
`FunctionLinkArray`, and `FFunctionParams` through the pointer slot that each `Z_Construct_UFunction` loads. It found
8,596 compiled-in types and 4,634 class parameter blocks.

Checks:
- The method reproduces known values: `ATribePawn.VROrigin` @0x3C0 and `Camera` @0x3C8 (map T20),
  `UTribeSkinItemWidget.Skin` @0x2F0 and `NameText` @0x390 (port H5), `UListView.ListItems` @0xB38 (also read as a raw
  `+0xB38` inside Tribe's `BuildAvatarSkinWidgets`).
- Bool offsets from the tables are not usable (bitfields). Bools below come from native code.

| Role | 2304 name (what the mod asks for) | 2311 class (FName = without U/A) | Members used (2311) |
|---|---|---|---|
| Menu | `W_ProfileMenu_C` | `UTribeProfileMenuWidget` : UUserWidget | `AvatarList` @0x398, `RPMAvatarPanel` @0x3A0 (UTribeRPMAvatarCreatorWidget), `VisualsManager` @0x3E8 |
| List | `AvatarList` (ListView) | `UListView` | `ListItems` @0xB38, `EntryWidgetClass` @0x198, `EntryWidgetPool` @0x1C8 |
| Box | `W_SkinItem_C` | `UTribeSkinItemWidget` : UUserWidget | `Addon` @0x2E8, `Skin` @0x2F0 (UTribeSkinBase), `NameText` @0x390, `bSelected` @0x350, `OnSkinPurchaseRequested` @0x368; UFUNCTIONs `OnSkinApplied(AppliedSkin, Pawn)`, `SetSelected(bInSelected)`, `InitSkinItem(InSkin)` |
| RPM item | `BP_ReadyPlayerMeAvatarSkin_C` | `UTribeReadyPlayerMeAvatarSkin` : `UTribeOculusAvatarSkin` : `UTribeSkinBase` | base: `Name` (FName) @0x28, `SkinInfo` @0x30, `bOwned` @0x58, `DynamicThumbnail` @0x60, `Addon` @0x68, `OnApplied` @0x70; `UTribeOculusAvatarSkin.AvatarID` (FString) @0xA0 |
| Other avatar items | `BP_OculusAvatarSkin_C` | `UTribeOculusAvatarSkin`, `UTribeAvatarPropSkin` | |
| Visuals manager | `BP_TribeVisualsManager_C` | `ATribeVisualsManager` | `OculusAvatarSkins` (map) @0x478, `RPMAvatarSkins` (map) @0x4C8, `ActiveSkins` (map) @0x518; `ApplySkinToPlayer(Skin)`, `GetSkin(SkinName)`, `InitMyRPMAvatarSkin`, `InitRPMAvatarSkins`, `AddCachedRPMAvatarSkin(AvatarFilename)` |
| Pawn | `TribePawnBP_C` | `ATribePawn` | `TribeAvatar` @0x3F0 (UTribeAvatarComponent), `AvatarPropMesh` @0x3D8, `ActiveSkinClasses` @0x468, `ActiveSkins` @0x4B8 (replicated) |

Where the individual values come from:
- **`AvatarList`'s class** **[obs]**: its class function (store 0x37D9380) registers `"/Script/UMG"`, `"ListView"`.
  That matches the map's line 137.
- **The `StaticClass` names** **[obs]**: `GetPrivateStaticClassBody` registers `TribeReadyPlayerMeAvatarSkin` (UTF-16 at
  0x1F2960) for that class. The class behind every `?53ba34c` in the dumps is `UTribeSkinBase`, whose
  `GetPrivateStaticClass` is store 0x53BA34C.
- **`bSelected` @0x350** **[der]**: the six bools follow `ProgressBarMat` @0x348 and come before
  `OnJumpToAddonSelected` @0x358, in this order: bSelected 0x350, bRequiresSubscription, bIsLessonPack,
  bIsReadyPlayerMe 0x353, bRequiresReview 0x354, bIsRealController. The press handler reads +0x350 in its "already
  selected" test (1.3), and the stage port read it the same way.
- **`bOwned` @0x58** **[der]**: the press handler reads `Skin+0x58` as "owned", and 0x58 sits between `SkinInfo`
  (0x30) and `DynamicThumbnail` (0x60).

`UTribeProfileMenuWidget` UFUNCTIONs **[obs]**: `BuildAvatarSkinWidgets`, `AddSkinWidgets(Listview, Skins[])`,
`AddSkinWidgetsForList(Listview, SkinDataTable)`, `OnAvatarClicked(Item)`, `OnActiveSkinChanged(PrevSkin, NewSkin)`,
`OnAvatarSkinLoaded(AvatarSkin)`, `OnSkinsLoaded`, `ShowAvatars`, `ShowReadyPlayerMe`.
- `OnSkinsLoaded`, `OnActiveSkinChanged` and `OnAvatarSkinLoaded` each have the bare UTF-16 name literal that
  `AddDynamic` stores in this build **[obs]**. `OnAvatarClicked` has none **[obs]**.
- So `OnAvatarClicked` is not bound with `AddDynamic` **[der]**. It is most likely bound natively to the list's
  `OnItemClicked()`, which never passes ProcessEvent **[asm]**. This would be proved wrong by a `[SKIN]` trace line for
  `TribeProfileMenuWidget.OnAvatarClicked` with `tribemod/skin_trace` on.

### 1.2 Tribe's 2311 names for every lookup in the mod

| dumper.cpp | What the mod asks for (2304) | 2311 | Notes |
|---|---|---|---|
| 3706 `g_smRpmCls` | `/Game/Visuals/Skins/OculusAvatar/BP_ReadyPlayerMeAvatarSkin.BP_ReadyPlayerMeAvatarSkin_C` | `/Script/TribeXR.TribeReadyPlayerMeAvatarSkin` | name change |
| 3707 `g_smFnObjSet` | `W_SkinItem_C.OnListItemObjectSet` | **none**: the box is filled natively (port R5) | labels come from the list's `EntryWidgetPool` instead (as `em_pool_scan`) |
| 3708 `g_smFnMouseDown` | `W_SkinItem_C.OnMouseButtonDown` | `/Script/UMG.UserWidget.OnMouseButtonDown`, with `self` is-a `TribeSkinItemWidget` | the same function the stage menu uses (`g_emFnUWDown`); it can't be swallowed (1.3) |
| 3709 `g_smFnListEvt` | `W_ProfileMenu_C.BndEvt__W_AchievementMenu_AvatarList_..._SimpleListItemEventDynamic__DelegateSignature` | **none** (`OnAvatarClicked` is native-bound, 1.1) | second route: `TribeSkinItemWidget.OnSkinApplied(AppliedSkin, Pawn)`, which is AddDynamic-bound to the item's `OnApplied` (port R4) |
| 3653 `sm_find_avatar_list` | an object named `AvatarList` of class `ListView`, not under `/Game/` | the live `TribeProfileMenuWidget`'s `AvatarList` property | the name route may still work: the UTF-16 literal `AvatarList` exists (0xB19A2) **[obs]**, and the line `Tribe's RPM skin object = 0x0` quoted in avatar_plan.md is printed only when `g_smList` != 0 (dumper.cpp:3715) **[der]** |
| 3680 `sm_find_live_rpm_skin` | class `BP_ReadyPlayerMeAvatarSkin_C` | class `TribeReadyPlayerMeAvatarSkin` | also used as the identity source (C3) |
| 949 `is_rpm_skin` | `BP_ReadyPlayerMeAvatarSkin_C` | `TribeReadyPlayerMeAvatarSkin` | only used by the `g_apply_fn` branch, which can't fire on 2311 (next row) |
| 930 `g_apply_fn` | `/Game/Visuals/BP_TribeVisualsManager.BP_TribeVisualsManager_C.ApplySkinToPlayer` | `/Script/TribeXR.TribeVisualsManager.ApplySkinToPlayer` exists, but the press handler calls it with a direct `bl 0x5B46D8C` (store 0x5B4C9E4) **[obs]** | it never reaches ProcessEvent from a press **[der]**: retire it on 2311 (C9) |
| 3398 (repl_pe) | `"BP_ReadyPlayerMeAvatarSkin_C"` | `"TribeReadyPlayerMeAvatarSkin"` | sits inside the `OnListItemObjectSet` branch, which is dead on 2311 |
| 521 `keys[]` | BP_ReadyPlayerMeAvatarSkin_C, BP_OculusAvatarSkin_C, W_RPMAvatarCreator_C, BP_TribeSkinBase_C | TribeReadyPlayerMeAvatarSkin, TribeOculusAvatarSkin, TribeRPMAvatarCreatorWidget, TribeSkinBase | `dump_now` diagnostic only |
| 536 `skc[]` | BP_ReadyPlayerMeAvatarSkin_C, BP_OculusAvatarSkin_C, BP_EnvironmentSkin_C | TribeReadyPlayerMeAvatarSkin, TribeOculusAvatarSkin, TribeEnvironmentSkin | `dump_now` only |
| 524 / 544 | `TribePawnBP_C.ActiveSkinClasses`, `TribeGameInstanceBP_C.AvatarId` | `TribePawn.ActiveSkinClasses` @0x468; the avatar id is `UTribeAvatarComponent.AvatarId` @0x268 | `dump_now` only |
| 1250, 4033 | `find_live("AvatarBodyMesh","SkeletalMeshComponent","ReadyPlayerMeComponent")` | unchanged: the subobject is still named `AvatarBodyMesh` (UTF-16 literal present) **[obs]**; the reflected property is `AvatarMeshComponent` @0x260, as on 2304 (native_reference.md:1047) | works today (20 `body=0x...` lines) **[obs]**; see 2.2 for why it should not be used on 2311 |

### 1.3 What a press does on 2311

`UTribeSkinItemWidget::NativeOnMouseButtonDown`, store 0x5B4C890, decoded **[obs]**:

1. `bl 0x3885CFC` (`UUserWidget::NativeOnMouseButtonDown`) raises `UserWidget.OnMouseButtonDown` through ProcessEvent
   with the box as `self`. This is the one point the hook sees **before** Tribe acts.
2. `Skin = box+0x2F0`. If the skin is **not owned** (`Skin+0x58 == 0`), there are two outcomes:
   - A previewable skin (`0x59E04C0(Skin.Name)` true and `box+0x354 == 0`) logs an analytics event
     `"SkinPreviewed_" + name` (UTF-16 at 0x328F92) and goes on to step 3.
   - Otherwise the box broadcasts `OnSkinPurchaseRequested` (+0x368) and stops.
3. **Owned:** an addon (`box+0x2E8`) in state 0 starts a download; state 2 applies if `0x59DA2B4()` returns true. With no
   addon (or state 3), the box applies if it is **not selected** (`box+0x350 == 0`). If it is selected, it applies only
   if `Skin->vfunc[0x300]()` (CanReapply) is true. For `UTribeReadyPlayerMeAvatarSkin` that slot is store 0x15D7068,
   `mov w0,#0; ret`, which is always false.
4. **Apply:** `ApplySkinToPlayer(VisualsManager, Skin)` at 0x5B46D8C, which runs
   `Skin->ApplySkin(LocalPawn)` (port R2).

What the RPM item's apply does: the vtable of `UTribeReadyPlayerMeAvatarSkin` is 0x8105270, the address its
`InternalConstructor` stores at 0x538FB68 **[obs]**.
- The ApplySkin slot (+0x2D0) is 0x5B47570, which is `UTribeSkinBase::ApplySkin`, not overridden. It calls slot +0x308,
  then `0x5A330D0(pawn, skin)`, then broadcasts `OnApplied`.
- Slot +0x308 is 0x5B417B8, decoded **[obs]**:
  - `name = GetSkinName()` (slot +0x2C0 = 0x1A63894, `ldr x0,[x0,#0x28]`).
  - If `name == FName("ReadyPlayerMe_Custom")` (UTF-16 at 0x1FEBC0) and the pawn's virtual +0x800 is true (**[asm]**
    IsLocallyControlled): it calls `ReadConfigString("TribeAvatar", "ReadyPlayerMeAvatarUrl")` (0x59F55EC; UTF-16 at
    0x1B47F6 / 0x206FAE). If found → `pawn+0x3F0 (TribeAvatar) → 0x5430CB8(url)` (**[asm]** `SetupAvatar`). If not →
    `0x5432398()` (**[asm]** the default avatar id) → the same call.
  - Any other name → `0x5B4140C(this, pawn)` (not decoded; **[asm]** it applies the item's `AvatarID`).
  - Both RPM-custom outcomes then **save** `WriteConfigString("TribeSkins", "OculusAvatar", name)` (0x59F5590; UTF-16
    at 0x13F484 / 0x1B46FA).

**Consequences for our boxes [der]**
- **A press on any of our boxes makes Tribe apply our item**, unless our box is selected. The hook can't block it
  (step 1 happens before the apply, inside native code).
- **An item spawned with no identity** has `Name = None` and `bOwned = false`. A press then either asks to buy it or
  (via the non-RPM branch) applies an empty `AvatarID`, which may save `OculusAvatar=None`. That would silently change
  the user's saved Tribe avatar. **Never add a box without the name.**
- **An item named `ReadyPlayerMe_Custom` and owned** only makes Tribe re-apply its RPM avatar from the config URL, and
  save `OculusAvatar=ReadyPlayerMe_Custom`. That is a harmless re-apply. The `AvatarID` string isn't needed on that
  branch.
- **An item that is also selected** (`box.SetSelected(true)`, with CanReapply false) is not applied at all.

### 1.4 Where the boxes come from (and the RPM box)

`UTribeProfileMenuWidget::BuildAvatarSkinWidgets`, store 0x594B0F0, decoded **[obs]**:
1. Clears `AvatarList` (`0x37D7F1C`).
2. Adds the values of `VisualsManager+0x4C8` (`RPMAvatarSkins`) through `AddSkinWidgets` (0x58F9478).
3. `0x15D7060` returns a constant 1, so it then adds the rows of
   `/Game/Visuals/Skins/OculusAvatar/DT_OculusAvatarSkins.DT_OculusAvatarSkins` (UTF-16 at 0x13F334) through 0x58F92C8.
4. Unless a flag from `0x5A0B9D0` is set, it copies `AvatarList.ListItems` (+0xB38/+0xB40) and calls
   `GetSkin("OculusAvatar_Custom")` (UTF-16 at 0x1FEAD8). The loop that follows was not decoded.

So the RPM box(es) come from `RPMAvatarSkins`, and an empty map means no RPM box **[der]**. What fills that map
(`InitRPMAvatarSkins`, `AddCachedRPMAvatarSkin`, `InitMyRPMAvatarSkin`) was not decoded. My guess **[asm]**: the cache
file the mod stages (`Documents/rpmavatar-<basename of the loopback URL>`, 2.5) isn't accepted as a cached RPM avatar.
C11's list of `ListItems` shows exactly which boxes Tribe built. Other avatar UI strings in 2311 **[obs]**: "Default
Avatar", "My Ready Player Me Avatar", "Create your Ready Player Me Avatar", and skin names `ReadyPlayerMe_Create`,
`ReadyPlayerMe_Default`, `OculusAvatar_Default`, `OculusAvatar_Custom`.

### 1.5 Why the lookups come back 0 in some sessions: timing

- In the 13:40 launch (pid 22629), every `[MENU]` lookup is 0, the engine functions included, and
  `[STREAM] diag objects: 0 matched, 0 in the array` **[obs]** (logcat_1340_first_launch_after_fix_no_hook.txt). With no
  object count, every `find_by_path` returns 0 **[der]** (dumper.cpp:289 loops to `g_numElements`).
- `skin_menu_poll` (3699) starts with `menu_resolve_engine_fns()` and never calls `ensure_resolved()` **[obs]**. The only
  automatic `ensure_resolved()` is the auto-load branch at 4031-4032, gated on `orig_pe` (the ProcessEvent hook)
  **[obs]**. That launch's hook never installed ("ProcessEvent calls 0", README) **[obs]**, so nothing resolved **[der]**.
- `menu_resolve_engine_fns` retries only while `AddItem` is 0 (3688) **[obs]**. If `AddItem` resolves and another one
  doesn't, that one stays 0 for the session **[der]**.
- The names are fine. `ListView.AddItem`/`GetIndexForItem`, `GameplayStatics.SpawnObject`, `TextBlock.SetText` and
  `KismetTextLibrary.Conv_StringToText` are unchanged in 2311 (map T8; UListView 20 props / 27 functions here too)
  **[obs]**.
- The Blueprint lookups are a names problem: those classes don't exist in 2311 (1.2).
- A launch without the hook can't load a character at all: every game-thread call goes through it **[der]**. The hook
  install is the startup work, not this part.

## 2. Tribe's own avatar on 2311

### 2.1 How it draws

These member lists match 2304's native_reference.md (ReadyPlayerMeComponent 11 props / 8 functions in both)
**[obs]**.
- **The pawn's avatar** **[obs]**: `ATribePawn.TribeAvatar` @0x3F0 is a `UTribeAvatarComponent`. It holds
  `CurrentETribeAvatarType` @0x278 (enum None / ReadyPlayerMe / MetaAvatar2), `ActiveAvatarComponent` @0x2C8,
  `ReadyPlayerMeComponent` @0x2D0, `MetaAvatar2Component` @0x2D8 and `AvatarId` @0x268.
- **The two avatar kinds** **[obs]**:
  - `UReadyPlayerMeComponent`: `AvatarMeshComponent` @0x260 (subobject name `AvatarBodyMesh`),
    `RightHandMeshComponent` @0x268, `LeftHandMeshComponent` @0x270.
  - `UMetaAvatar2Component`: `ThirdPersonMeshComponent` @0x290, `FirstPersonMeshComponent` @0x2A0.
  - 2311 ships `libovravatar2.so`.
- **`SetAvatarVisibility(bThirdPersonVisible)`** (store 0x54317A8, reached from its exec thunk 0x5243E7C) **[obs]**:
  - It stores the flag at +0x289.
  - Type 1 → `0x542BA34(active, v)`; type 2 → `0x4C408FC(active, v)`. So ReadyPlayerMe = 1 and MetaAvatar2 = 2
    **[der]**.
- **What the RPM side (0x542BA34) does** **[obs]**: if its virtual +0x540 is true (**[asm]** "avatar loaded"), it calls
  on the body:
  - `0x3D5BD84(!v)`, which is `SetVisibleInSceneCaptureOnly` (the call inside that UFUNCTION's exec thunk 0x3A66240);
  - `0x3D5BDBC(flag +0x2FA)`, which is `SetHiddenInSceneCapture` (exec 0x3A63764);
  - `0x3D84630(true, true)`.

  If the avatar isn't loaded, `0x3D84630(false, true)` on the body and both hands.
- **What that means** **[der]**: when you don't see your own body (`v` false), it is drawn only in scene captures, that
  is the selfie stick and the stream. `SetAvatarVisibility` is "see yourself", not "hide".

### 2.2 What the mod does to it today

- **Today's code** **[obs]**: `do_load` finds `AvatarBodyMesh` with `find_live` and calls `attach_mesh`, which runs
  `SetLeaderPoseComponent(null)`, `SetSkeletalMeshAsset(ours)`, `SetOwnerNoSee(false)`, `SetVisibility(true,true)` and
  `SetHiddenInGame(false,true)` (1005-1009, 1296). The keeper re-attaches whenever the mesh changes (4084-4090, 3404).
- **The render reports, per launch** **[obs]** (`RENDER #n slot`, every launch in load_result_1500.txt): the slot is
  always at loc=(0,0,0), scale 1. `WasRecentlyRendered(0.5)=1` at least once in 7 of the 17 launches that loaded a
  skin (the launches starting at lines 1, 214, 329, 433, 534, 5898 and 35393).
  - GUIDE.md:463 says that on 2304 the slot stayed at the origin and was never drawn.
  - So on 2311 a copy of the character is sometimes drawn at the world origin **[der]**. The skins' origin is the
    hips, so it would stand sunk to the hips, with the hips at floor level, where the DJ rig sits in the Void.
- **Tribe nulled the slot 4 times** (`NATIVE reset of body (cur=0x0)`), and never put another mesh there **[obs]**.
- **Our own actor reports `ISO ... =0` in the later launches** **[obs]**. That is expected: body tracking retires the
  static follow mesh (1682), and the visible body is the A2 meshes.

### 2.3 "Both show": two readings and the discriminator

- **H1.** `find_live` picked the local pawn's RPM component. Then the second figure is our mesh drawn from Tribe's slot.
  `SetVisibleInSceneCaptureOnly` would put it in the stream, at the origin.
- **H2.** `find_live` picked another actor's RPM component. 2311 has extra avatar users: strings
  `Replays/DanceAvatar.glb`, `/MentorAvatar.glb`, `Replays/DefaultAvatar.glb` **[obs]**. In that case the local pawn's
  own avatar loads untouched and shows in captures.
- **The discriminator** (C11): log the slot's owner actor next to `g_pawn.TribeAvatar.ReadyPlayerMeComponent`, and each
  avatar mesh's mesh name, world location, hidden/visible flags and `WasRecentlyRendered`.
- C6 + C8 fix both readings, so the fix doesn't wait on this.

### 2.4 How to hide it while a mod skin is on, and show it for the RPM box

- **Hide.** Call `/Script/Engine.SceneComponent.SetHiddenInGame(NewHidden=true, bPropagateToChildren=true)` on
  `g_pawn.TribeAvatar` (+0x3F0). Tribe forwards that flag itself **[obs]**:
  - Two functions in `UTribeAvatarComponent` (store 0x5432470 and 0x54311D4) call `SetHiddenInGame` (impl 0x3D849CC,
    from its exec thunk 0x3A72A38) on `ActiveAvatarComponent` with **its own** `bHiddenInGame` (bit 11 of the halfword
    at +0x188), propagate true.
  - Then they broadcast `OnAvatarVisibilityChanged` (+0x250).
  - **[asm]** 0x543244C is the `OnHiddenInGameChanged` override, and 0x54311D4 runs when an avatar finishes loading. If
    so, the hide survives avatar reloads and type switches.
- **Tribe's own visibility toggles don't touch this flag** **[obs]**: the decoded functions in 2.1 call
  SetVisibility-family functions, not 0x3D849CC.
- **Re-assert anyway.** The library has 672 direct calls to `SetHiddenInGame` (0x3D849CC) **[obs]**, so some other path
  could flip it. Re-check once a second while a mod skin is on (C6).
- **Show.** The same call with false, when a Tribe avatar box is picked (C7).
- **Props.** The pawn's avatar props follow `OnAvatarVisibilityChanged` **[asm]**: `ATribePawn.RefreshAvatarPropVisibility`
  exists. Proved wrong if a hat floats alone: then also hide `AvatarPropMesh` (+0x3D8).
- **Other players.** Component hidden flags don't replicate **[asm]**. Others keep seeing stock Tribe, as GUIDE.md:461
  says they already do.

### 2.5 The saved-avatar keys

- **What the snapshot holds** **[obs]**: `avatar_url.txt` in the 13:35 snapshot and on the headset (md5 b19a3edb on
  both) is 32 bytes. It is a loopback `http://` URL to a `.glb` on port **8000**: not a secret, and not a readyplayer.me
  URL.
- **What the mod does with it** (`ini_upsert`, dumper.cpp:740-749, in the constructor) **[obs]**:
  - The file exists, so it **sets** `[TribeAvatar] ReadyPlayerMeAvatarUrl="<that URL>"`.
  - It copies `tribemod/custom.glb` (md5 bb01368f, the httpd's ETag) to
    `Android/data/.../files/Documents/rpmavatar-<basename>`.
  - It **deletes** the key only when the file is absent.
- **So the GUIDE.md:507 deletion does not happen with today's files** **[der]**. Instead, every launch overwrites
  whatever URL the user saved with the loopback one **[der]**.
- **The loopback URL is dead** **[obs]**: the mod's httpd listens on **8787**, not 8000. `httpd.log` shows no request
  today.
- **The key and the cache name still exist in 2311** **[obs]**: UTF-16 `ReadyPlayerMeAvatarUrl`, `ReadyPlayerMeETag`,
  `%srpmavatar-%s`. 1.3 shows that applying the RPM-custom skin reads exactly this key.
- **So Tribe's "RPM avatar" here is custom.glb from the cache**, if the cache-hit route still works on 2311 **[asm]**.
  The user's real RPM avatar can't load: readyplayer.me went down Sep 29 (GUIDE.md:453).
- **No change proposed to `ini_upsert`.** Removing the key would change what the RPM box shows. If the user wants
  Tribe's real default avatar instead, deleting `tribemod/avatar_url.txt` makes the next launch delete the key. That is
  a headset file change, so it needs the user.

## 3. Per character

Every file on the headset matches the 13:35 snapshot (md5) **[obs]**. `active_skin.txt` = `horseman.glb`,
`head.txt` = `auto` (every 600 s of play, ±20 %) **[obs]**. Loads come from load_result_1500.txt: 20 `do_load` sections
in 23 launches, all with the 2311 pool address `np=0x884d640` **[obs]**.

| Character | skins/ md5 | Loaded on 2311? | heads/ | Head on 2311 | 2311-specific |
|---|---|---|---|---|---|
| Skullbuck | 2c1f9c44 | **yes**, 8 launches (lines 2-5900), materials on | none | feature off for it: "no heads/skullbuck.glb" is expected | none |
| Gremlin | 57731386 | **yes**, once (line 16288, a `next_skin` cycle): materials on, `A2: rest skeleton 57 bones ... mapped 22/22`, re-rigged | 8f288613 | not logged | none seen |
| Horseman | a04620a1 (v3) | **yes**, 11 loads | ed59d303 | not logged (the set's logcat rotated) | none seen |
| Lampwing | 1ac0465c (9.2 MB, the largest) | **not tried on 2311** | none | feature off for it | a load stalled Tribe ~9 s on 2304 (GUIDE.md:508): test it off-stream |
| Major Tom | a4f19156 | **not tried on 2311** | 37e1ab21 | not logged | glass material (BLEND) unchecked by eye, as on 2304 |
| Santa | f0b35316 | **not tried on 2311** | 1fcd5d46 | not logged | none known |
| Tribe RPM | custom.glb bb01368f via the cache (2.5) | Tribe loads it, not the mod | n/a | n/a | the box is missing (1.4); hide/show is C6/C7 |

**Heads [der]**
- `head.cpp` has no Blueprint names except `SelfieStick`, already changed for 2311 (port D1).
- Its engine functions are unchanged: `glTFRuntimeAsset.LoadStaticMesh`, `StaticMeshComponent.SetStaticMesh`,
  `SceneComponent.GetSocketTransform`, `K2_SetWorldLocationAndRotation`.
- It needs body tracking live (`g_a2Live`), which it is on 2311: "A2: 120 frames driven OK" **[obs]**.
- `head_tick` runs from the 2311 ProcessEvent driver with dt clamped to 0.25 s, so the play clock advances
  (3381, head.cpp:181-182).

**The only skin switch that works on 2311 is `next_skin`** (4055) **[obs]**. The menu-select cycle depends on
`g_apply_fn`, which is 0 on 2311 (1.2).

## 4. The changes

All in `backup/mod_fix_stream_fix/src/dumper.cpp`. Each one keeps the 2304 route as the fallback. Mode detection is
`find_by_path("/Script/TribeXR.TribeReadyPlayerMeAvatarSkin",1)` != 0 → 2311 mode, else the old route after 3 tries,
the same pattern as the stage port's H14.

That src is combo_peretry (the retry install, the atomic flag and the diagnostics), not exactly the live combo_pedriver.
The 12:18 tree wasn't kept separately **[obs]**. Build with the recipe in the brief, and check that only `libhook.so` and
`META-INF/` differ from combo_pedriver_2311.apk.

| # | Where | Change | 2311 name / offset and how found | Risk |
|---|---|---|---|---|
| C1 | `skin_menu_poll` (3699) | First line: `ensure_resolved(); if(!g_resolved) return;` (log once "waiting for the engine objects"). `menu_resolve_engine_fns` retries until all seven are non-zero. 2311 mode: `g_smRpmCls` = `/Script/TribeXR.TribeReadyPlayerMeAvatarSkin`, `g_smWCls` = `/Script/TribeXR.TribeSkinItemWidget`, `g_smOffWSkin` = `prop_offset(g_smWCls,"Skin")` (expect 752), `g_smFnUWDown` = `/Script/UMG.UserWidget.OnMouseButtonDown`, `g_smFnSkinApplied` = `em_find_child_func(g_smWCls,"OnSkinApplied")`. Skip the three Blueprint scans in 2311 mode (now repeated forever every ~6 s, mod_fix_port_halloween.md section 4). `want` needs AddItem, GetIndexForItem, SpawnObject, GS, RpmCls, WCls, OffWSkin ≥ 0, and UWDown or SkinApplied | 1.1, 1.2 (reflection) | low. `ensure_resolved` is what auto-load already runs on this thread. It adds no work on the game thread |
| C2 | `sm_find_avatar_list` (3653) | 2311: `em_find_live("TribeProfileMenuWidget")` → `prop_offset(...,"AvatarList")` → must be `obj_alive` and `em_is_a(l,"ListView")`; else the old name route | `AvatarList` @0x398, class UListView (1.1) | low (reads only) |
| C3 | `sm_find_live_rpm_skin` (3680) | Accept class `TribeReadyPlayerMeAvatarSkin`. Prefer the live item whose `Name` reads `ReadyPlayerMe_Custom`; else any non-CDO one that isn't ours. Also scan `AvatarList.ListItems` (`prop_offset(ListView,"ListItems")`, expect 0xB38) for Tribe's own items | 1.1, 1.3 | low |
| C4 | `menu_tick` (2199) spawn path | After `sm_spawn(g_smRpmCls, outer)`: if C3 found Tribe's RPM item, `em_copy_identity(ours, it)` (Name, bOwned, ints and enums; no strings). Else set `Name` = `KismetStringLibrary.Conv_StringToName("ReadyPlayerMe_Custom")` (engine UFUNCTION; 8 bytes at `prop_offset(cls,"Name")`) and `bOwned` = 1 through its FBoolProperty mask (as `em_copy_identity` does). **If neither works, don't add the box** (log it). Optional C4b: on each pool scan, `box.SetSelected(true)` on our boxes, so a press doesn't apply at all (1.3 step 3) | `Name` @0x28, `bOwned` @0x58; the RPM-custom branch decoded at 0x5B417B8 | **medium.** A press still makes Tribe re-apply its RPM avatar (reloads custom.glb from the cache, **[asm]** a short hitch) and save `[TribeSkins] OculusAvatar=ReadyPlayerMe_Custom`, which changes Tribe's saved avatar to the RPM one. C4b avoids both, but our boxes may look selected **[asm]**. Our items' empty `AvatarID` may start a failed thumbnail fetch (`ReloadAvatarThumbnail`) **[asm]**: watch for a crash right after `added box` |
| C5 | new `sm_pe_2311(self, func, parms)`, called from `repl_pe` beside `em_pe_2311` (3393) when `g_skinMenuOn && (func==g_smFnUWDown \|\| func==g_smFnSkinApplied)` | Copy `em_pe_2311`'s logic: a press on a box (class chain to `g_smWCls`) whose `Skin` is ours → `sm_map_widget` + `sm_load(idx)`; `OnSkinApplied` with our item → `sm_load` only within 1 s of a press, or if no press was ever seen; a press on a box whose `Skin` is Tribe's (`TribeOculusAvatarSkin` family, RPM included) → `sm_tribe_avatar_pick()` (C7). Labels: `sm_pool_scan(list)` once a second in `menu_tick`, a copy of `em_pool_scan` (2531) against `g_smWCls`/`g_smOffWSkin`, then `sm_label_box`. Raise `sm_load`'s debounce from 700 ms to "same item within 3 s" (GUIDE.md:508). Leave the 2304 swallow block (3395-3402) as is: all three pointers are 0 on 2311 | 1.3; port R1/R4/R5/R10 | **medium.** The press route is the stage menu's, untested on device for both menus. If `AvatarList`'s entry class isn't `TribeSkinItemWidget`, nothing matches and nothing breaks; `next_skin` still works |
| C6 | new `sm_tribe_avatar_hide(bool)`, called by `do_load` after a successful skin load (2311 mode) and once a second from `menu_tick` while a mod skin is on | `uintptr_t ta = rdptr(g_pawn + prop_offset(cls(g_pawn),"TribeAvatar"))`; check it is-a `TribeAvatarComponent`; `call_bool2(ta, g_fnHid, hide, 1)`. Re-assert: read `bHiddenInGame` (FBoolProperty on SceneComponent) and call only when it differs; log each flip | `TribeAvatar` @0x3F0; forwarding decoded at 0x543244C / 0x54311D4 (2.4) | **low-medium.** Tribe may un-hide it on some path (re-assert covers it, with up to 1 s of flash) **[asm]**. Needs `g_pawn` (follow_wire) |
| C7 | new `sm_tribe_avatar_pick()` (from C5) | Hide our actor: `Actor.SetActorHiddenInGame(true)` on `g_isoActor`, which covers the A2 meshes and the head component on it **[der]**: both are added to that actor with AddComponentByClass (head.cpp:139, dumper.cpp:1645). Call `head_force_on`. `sm_tribe_avatar_hide(false)`. Write `active_skin.txt` = `rpm`. In `do_load`, `rpm` = load the last real skin (new `last_skin.txt`) **hidden**, so the per-frame driver, which needs `g_isoActor` (3379), keeps running. Picking a mod box: `SetActorHiddenInGame(false)`, load, C6 | `ATribePawn.TribeAvatar` (1.1) | **medium.** It's a workaround: the driver should not need the avatar actor (section 5). Without C7, picking Tribe's RPM box shows both until a mod box is picked |
| C8 | `do_load` (1296) | In 2311 mode, don't `attach_mesh` to Tribe's slot and don't start the keeper. Log `(2311: Tribe's AvatarBodyMesh left to Tribe; its avatar is hidden by C6)`. Keep `find_live("AvatarBodyMesh",...)` at 4033 as the "pawn ready" signal | 2.2, 2.3 | low. Removes the copy at the origin and the keeper fight. The `(no live Tribe AvatarBodyMesh slot ...)` path already exists (1297), and the follow actor and A2 never use `g_body` |
| C9 | `ensure_resolved` (930) and `repl_pe` (3426-3429) | 2311 mode: don't look up `g_apply_fn`; the cycle branch stays inert. `is_rpm_skin` (949) accepts `TribeReadyPlayerMeAvatarSkin` too | 1.2 | none |
| C10 | `do_dump` (521, 536, 524, 544) | Add the 2311 names from 1.2 | 1.2 | none (dump_now only) |
| C11 | new `sm_diag_once()` from `skin_menu_poll`, when the list is first found, and again on `tribemod/skin_diag` (one-shot) | Log: `AvatarList.EntryWidgetClass`; every `ListItems` entry (class, `Name`, `bOwned`, `AvatarID` **length only**); `g_pawn.TribeAvatar` fields (`CurrentETribeAvatarType`, `ActiveAvatarComponent` class, `IsThirdPersonVisible()`); for the RPM `AvatarMeshComponent`/hands and the Meta meshes: mesh name, world loc, attach parent, bVisible/bHiddenInGame, `WasRecentlyRendered(0.5)`; the full path of the `AvatarBodyMesh` that `find_live` returns, and whether it is the pawn's | 1.1, 2.1 | none (reads; calls only getters). **Never print `AvatarId` or URLs** |
| C12 | `follow_update` (1129-1131) | `long t=g_isoTicks+g_camTicks+g_pe_drv;` | 2311 drives frames from `repl_pe` (`g_pe_drv`) and `g_isoTicks`/`g_camTicks` stay 0, so `t%180==0` is true every frame **[der]**. Observed: consecutive `follow:` lines at dt 0.016-0.06 s, and load_result.txt at 33.6 MB | low. Removes a `fopen`/`fprintf`/`chmod` and a logcat line per frame on the game thread |

Order: C12, C8, C1-C3 and C11 first. They are safe and settle the open questions. Then C6. Then C4/C5 (the menu). Then
C7.

## 5. Tests, per character

Prerequisites:
- The build passes the brief's checks: 7 warnings, and only `libhook.so` and `META-INF/` differ.
- Install only on the user's go. The install restarts Tribe and raises the Restore dialog (Close, never Restore).
- Launch, pick Graveyard Shift, open Profile > Avatars.
- `logcat -d -s TRIBEMOD` and `tribemod/load_result.txt` must show:
  - `[MENU] 2311 menu (C++): TribeReadyPlayerMeAvatarSkin=0x... TribeSkinItemWidget=0x... Skin@752 press=0x... apply=0x...`
  - `[MENU] engine fns: AddItem=0x...` with all seven non-zero.
  - The C11 block: `EntryWidgetClass=TribeSkinItemWidget` and Tribe's items (expected among them `OculusAvatar_Default`,
    `ReadyPlayerMe_*`).
  - For each character: `[MENU] spawned skin object for 'X' ... identity Name=ReadyPlayerMe_Custom bOwned=1` and
    `[MENU] added box 'X'`. The boxes read Gremlin, Horseman, Lampwing, Majortom, Santa, Skullbuck within ~1 s of
    opening.
  - `load_result.txt` stops growing by ~1 KB a second (C12).

For each character, the user presses its box once:

| Pick | logcat / load_result must show | In the headset |
|---|---|---|
| Gremlin | `[MENU] press on our box 'Gremlin'` → `[MENU] clicked 'Gremlin' -> loading gremlin.glb` → `=== do_load` → `asset=0x... skins/gremlin.glb` → `mesh(materials)=0x...` → `A2: re-rigged for the new skin` → `[MENU] Tribe's avatar hidden` → `[HEAD] loaded heads/gremlin.glb -> UStaticMesh` → `[HEAD] rig ok: DH_C/DH_F/DH_U` | only Gremlin, also in the selfie camera; nothing at the decks |
| Horseman | the same with horseman.glb; `[HEAD] rig ok` | pumpkin head on; no RPM body in the selfie view |
| Lampwing | the same with lampwing.glb; `[HEAD] lampwing.glb: no heads/lampwing.glb -> feature off`; note the gap between `asset=` and `mesh(materials)` | wings shown; any freeze longer than ~9 s is a finding. Test it off-stream |
| Majortom | the same with majortom.glb; `[HEAD] loaded heads/majortom.glb` | helmet glass looks clear (first eye check) |
| Santa | the same with santa.glb; `[HEAD] loaded heads/santa.glb` | — |
| Skullbuck | the same with skullbuck.glb; `[HEAD] skullbuck.glb: no heads/... -> feature off` | — |
| Tribe's RPM box | `[MENU] Tribe avatar picked (ReadyPlayerMe_Custom)` → `[MENU] Tribe's avatar shown` → our actor hidden; after a relaunch `active_skin.txt` = `rpm` and the avatar stays Tribe's | Tribe's avatar only. Then pick Horseman again: back to Horseman only |

- **The head flight.** The flight itself needs about 10 minutes of play with `head.txt` = `auto`. A one-off `boo` or
  `off` in head.txt makes it immediate, but that's a headset file change, so it needs the user.
  - Must show: `[HEAD] TAKEOFF (auto)` → `ORBIT` → `RETURN` → `ON`.
- **Failure lines to look for:**
  - `[MENU] ... can't see a press` (C1 lookups);
  - no `press on our box` after a press: create `tribemod/skin_trace` and press again, then read the `[SKIN]` lines;
  - a crash right after `added box` (C4's thumbnail risk).

## 6. Found on the way (outside the menu, but they decide whether characters load)

- **Every per-frame feature still needs the avatar actor.** The 2311 driver runs only `if(g_isoActor ...)` (3379)
  **[obs]**. On 2311 the pawn fallback is dead too: it waits for a `ReceiveTick` through ProcessEvent, which never
  comes (3414) **[der]**. If no skin loads, the stage show, stream settings and menus never tick **[der]**.
  - Seen today **[obs]**: six launches in a row resolved and never loaded a skin (the `resolved:` lines 56745-56752;
    each `resolved:` line is one process, since it prints once per launch). One of them armed the load
    (`auto-load: pawn ready ... -> armed`, line 56750) and never ran `do_load`.
  - The fix belongs with the startup work: let the driver run when `g_resolved && g_pawn` even without our actor. Each
    tick function checks its own needs (mod_fix_port.md section 2, the fallback-driver row).
- **The 13:57:37 crash is in the stage code** (`club_tick → club_show_player → mpc_call_on`), not in the character code
  **[obs]** (README).
- **The 2311 menu reads `TribeSkinItemWidget.bIsReadyPlayerMe`** (+0x353) on boxes **[obs]** (reflection). Tribe may
  draw RPM boxes differently; it doesn't matter for ours.

## 7. Phase 1, already written and compiled (in the scratch folder only)

`backup/mod2311_work/chars/apply_phase1.py <src> <out>` copies the hook sources and applies **C12, C8, C1-C3, C9, C11
and C6** to `dumper.cpp` with exact-string edits. Each anchor must match, or nothing is written. Nothing else changes:
the other sources are byte-identical **[obs]**.

**Outputs [obs]**
- `src_phase1/` (dumper.cpp md5 e89fe154; the script regenerates it).
- `phase1.diff` (219 lines against the current src, md5 aae4996a, unchanged).
- `build_phase1/libhook.so` (md5 9d055ce9, 507 KB). Built with the brief's command line: exit 0, the same 7 warnings as
  `build/warnings_retry.txt` (one line number shifted by the insertions).
- No APK was made.

**What phase 1 does**
- It doesn't put our mesh on Tribe's slot.
- It hides Tribe's avatar once a mod skin is on. The file `tribemod/tribe_avatar_shown` turns that off without a
  rebuild, and the "show" path only undoes the mod's own hide.
- It logs the diagnostic once the avatar list is first open. The `tribemod/skin_diag` file asks for it again.
- It stops the per-frame follow log.
- It resolves before the menu lookups.
- It does **not** add boxes. In 2311 mode `g_skinMenuOn` stays 0, so `menu_tick` and the 2304 swallow block stay inert.
  That waits for C4/C5, after the diagnostic has shown the entry class and Tribe's items.
- 2304 behaviour is unchanged: every new path is gated on `g_smMode==1`, which needs the native
  `TribeReadyPlayerMeAvatarSkin` class. 2304 has no such class (no UTF-16 registration name in its library) **[obs]**.

**To ship it** (only on the user's go): the APK steps in the brief with this `libhook.so`, then `sign_apk.sh`. Then
compare with combo_pedriver_2311.apk: only `lib/arm64-v8a/libhook.so` and `META-INF/` may differ.

**What the first launch must show**
- `[MENU] avatar menu kind: 2311 (C++ ...)`
- `[LOAD] 2311: Tribe's AvatarBodyMesh left to Tribe ...`
- About a second after the avatar appears: `[MENU] Tribe's avatar hidden (TribeAvatar 0x... SetHiddenInGame(1, propagate) -> bHiddenInGame=1; flip #1)`
- After opening Profile > Avatars: `[MENU] live avatar list = 0x... (TribeProfileMenuWidget.AvatarList)`, then the
  `[MENU] diag:` block and `[MENU] diag render:` lines.
- `load_result.txt` no longer gains a `follow:` line per frame.
- In the headset and the selfie view: only the mod character, and nothing at the decks.
- **If the flip count keeps rising** (`flip #50`, `#100`), Tribe is un-hiding it on some path. That's harmless but worth
  reporting.

## 8. Not verified, and what to watch

- **Nothing here ran in Tribe.** The class, member and offset names are from the 2311 reflection tables, re-checked
  against known offsets and Tribe's own code. The behaviour comes from disassembly. Which branch runs on the device is
  not tested.
- **Silent failure to watch: Tribe's saved avatar.** After the first press on one of our boxes, Tribe saves
  `[TribeSkins] OculusAvatar=ReadyPlayerMe_Custom` (decoded). With C4b on, it doesn't.
  - If an identity-less item ever gets applied, `None` would be saved. C4 refuses to add such a box. Check that `[MENU]
    added box` lines always show `Name=ReadyPlayerMe_Custom`.
- **Not decoded:** `0x5A330D0` (the pawn side of every apply; **[asm]** it records and multicasts the skin name through
  `Multi_AddActiveSkin`), `0x5B4140C` (the non-RPM apply), and what fills `RPMAvatarSkins`.
- **Multiplayer.** A press makes the pawn multicast `ReadyPlayerMe_Custom`. Others then try to load the loopback URL on
  their side **[asm]**, the same as stock Tribe with this ini. Test solo first.
- **H1/H2 (2.3) and the box class** are settled by C11's first run.
