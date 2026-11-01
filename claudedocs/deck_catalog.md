# Tribe XR gear catalog: decks, mixers and controllers

Read from the Blueprints of Tribe XR 0.12.5.1 (build 2304) itself, not from screenshots or guesses. Made by `scripts/deck_catalog.py` from `scripts/uasset_tool` dumps of `/Game/Equipment`, using the type mappings the hook dumped from the running game (`pulled/TribeXR_full.usmap`). Every Blueprint named here is also available as readable pseudo-code (see the last section).

## How Tribe builds a piece of gear

- **A model** is a small Blueprint on top of one of two engines: `BP_Deck` (decks: playback, cues, loops, sync, beat grid, track loading) or `BP_Console` (mixers: channels, EQ, filters, FX, cueing). A matching `...Info` class holds what the gear menu shows: name, store SKU, width, preview image.
- **Controls are separate actors.** The model's `SpawnControls` (and `SpawnChannel` once per mixer channel) spawns each control class and gives it the deck or mixer it drives (`Deck` / `Console`), the model's equipment mesh, and its tables of control meshes and materials. Every control derives from `BP_BaseDeckControl`: knobs, faders, toggle, radio and plain buttons, jog wheels, touch strips.
- **Where a control sits:** `Setup Child Control` looks the control's unique name (for example `ChannelEQKnobLow_0`) up in the model's control table, `DT_<ModelId>_ControlInfo`. If the row names a bone, the control sits on that bone of the model's skeletal mesh; otherwise it sits at the marker component the model passed (`Marker_Play`, `Marker_CueChannel1` ...). The same row's `ElementIndex` picks the control's graphic from a texture atlas.
- **What a control does:** its press, turn or slide handler calls a function on its deck or mixer (the Slip button calls `Deck.SetSlip(on)`), and it follows the deck's events to light up (`Deck.OnSlipModeChanged`). The deck's `Multi_...` and `Server_...` functions carry those changes to everyone in the room.

**Positions** are in cm in the gear's own space: x runs left (-) to right (+), y back (-) to front (+, the side you stand at: every deck's Play/Cue and every mixer's channel faders sit at +y, its screen or trim knobs at -y), z up, from the model's origin. Marker positions are exact. Bone positions come from the skeleton's reference pose; where a control has both, the two agree on the CDJ-3000, Tribe CDJ and DJM-NXS2 (median offset under 0.2 cm), and on the Tribe Mixer every bone position is moved by the constant offset its markers show (below).

## What the engines can do

Summarised from the engines' function names (every function, with parameters, is in `deck_reference.md`; the pseudo-code shows what each does).

**Decks (`BP_Deck`, 329 functions; sync lives in its base `BP_MixerChannelDevice`).**
- Playback: `Start Play` / `Stop Play`, reverse (`SetReversePlayback`), pitch and tempo (`Multi_SetCurrentPitch`, tempo range `CycleTempoRange`, `ResetTempo`), key lock (`SetMasterTempo`), touch/brake (`Multi_SetTouchBrake`), the jog wheel (`JogStart` / `JogTick` / `JogStop`, `SetJogMode`, vinyl mode), needle and track search (`Needle Set Position`, `SetPositionFromFraction`), time display mode.
- Cues: the cue point (`SetCue`, `SeekToCue`, cue preview, auto-cue to the first beat), hot cues (`SetHotCue`, `SeekToHotCue`, `ClearHotCue`, colours, call/record mode `SetHotCueMode`) and memory cues (`SetMemoryCue`, `SeekToMemoryCue`, `ClearMemoryCue`).
- Loops and jumps: loop in/out, reloop/exit, `CutLoop`, `ExtendLoop`, beat loops (`SetBeatLoop`), `JumpLoop`, beat jump (`Multi_BeatJump` with selectable intervals), slip (`SetSlip`, slip reverse).
- Key: `SetKey`, key shift up/down, key sync. Sync: `StartSync` / `End Sync` / `ToggleSync`, sync master, `RealignBeatSync`.
- Beat grid: set BPM, set first bar, halve/double, reset, the in-VR beat-grid editor, quantize.
- Tracks: local files, Beatport, SoundCloud, Tidal and Dropbox (each has its login handler), shared Dropbox links, track transfer between players, instant doubles, saved player memory (cues and loops per track), performance pads with pad modes, the player screen and its button banks.
- Multiplayer: one player's deck is the replication master (`HasRepAuthority`); its state goes out as net-sync packets (`MakeNetSyncPacket`, `Multi_UpdateNetSyncMs_...`, `PlayNetSynced`), and `Multi_...` functions mirror each action for everyone.

**Mixers (`BP_Console`, 148 functions).**
- Channels: fader and fader curve, EQ per band (`Set Channel EQ`, EQ curves), trim, filter level and resonance, send level, headphone cue (`SetChannelCue`), crossfader assign, crossfader and its curve, master filter.
- Color FX (`SetActiveFXButton`, `SetColorFxParameter`, centre lock, "smart" color FX) and Beat FX (type, channel, level, time with next/previous intervals, on/off, quantize, BPM with auto and tap tempo, X-Pad, FX EQ). Send FX master mix, size, time and tone.
- Mic: level, EQ, mode, mic FX, talkover, and ducking the music while someone speaks.
- Sync master handling (`AutoSwitchSyncMaster`, `ResyncDecks`), Tribe's Smart Fader (tempo matching driven by the fader: `SetSmartFaderEnabled`, `SetPitchFromSmartFader`), VU meters, headphones, room audio spatialisation, saved mixer state and control locks.

**The rig (`BP_Rig`, 70 functions)** spawns the chosen mixer and one channel device per channel, sets deck scale and the equipment skin, locks gear for lessons, checks DLC and subscriptions for paid gear and stream tracks, switches MIDI mode, saves and restores the whole setup, and knows where the DJ, teacher and spectators stand.

## The gear

| Name in the menu | Model | Type | Group | Store SKU | Width (cm) | Channels | Controls | Built on |
|---|---|---|---|---|---|---|---|---|
| CDJ3000 | CDJ3000 | Deck | Pioneer | Equipment_CDJ3000 | 33.5 | - | 51 | Deck |
| CDJ3000X | CDJ3000X | Deck | Pioneer | Equipment_CDJ3000X | 33.5 | - | 58 | CDJ3000 |
| DDJ-FLX4 | FLX4 | Deck | Controller | Equipment_FLX4 | 33 | 2 | 81 | Deck |
| Starter CDJ | StarterCDJ | Deck | Tribe | Equipment_StarterCDJ | 33 | - | 16 | Deck |
| Tribe CDJ | TribeCDJ | Deck | Tribe | Equipment_TribeCDJ | 32.5 | - | 30 | Deck |
| VinylDeck | TribeVinylDeck | VinylDeck | - | Equipment_VinylDeck | 39 | - | 5 | VinylDeck |
| DJM-A9 | DJM_A9 | Mixer | Pioneer | Equipment_A9 | 38 | 4 | 87 | Console |
| DJM-900NXS2 | DJM_Nexus_2 | Mixer | Pioneer | Equipment_DJM_Nexus_2 | 33 | 4 | 80 | Console |
| DJM-V10 | DJM_V10 | Mixer | Pioneer | Equipment_V10 | 38 | 6 | 145 | Console |
| DDJ-FLX4 | FLX4-Mixer | Mixer | Controller | Equipment_FLX4 | - | 2 | 34 | Console |
| Starter Mixer | StarterMixer | Mixer | Tribe | Equipment_StarterMixer | 25.3 | 2 | 20 | Console |
| Tribe Mixer | TribeMixer | Mixer | Tribe | Equipment_TribeMixer | 33 | 4 | 63 | Console |

## CDJ3000

Model `BP_CDJ3000_C` on `BP_Deck_C`. model id `CDJ3000`. SKU `Equipment_CDJ3000`. 33.5 cm wide. control table `DT_CDJ3000_ControlInfo`. skeleton `SK_CDJ3000_Skeleton`.

| # | Control | Label | Kind | x, y, z (cm) | Placed by | Settings | What it does |
|---|---|---|---|---|---|---|---|
| 1 | PitchSlider | {BPM} BPM / {Tempo} / {Key} / ({Master BPM} {Mast… | fader | 13.8, 14.5, 3.4 | bone pitch_fader_bone | - | calls Console.Multi_SetSmartFaderPitchMod_Reliable, Label.HighlightOnHover, Tribe_Game_Instance_BP.ThirdPersonSpectatorActive, SpectatorLabel.HighlightOnHover, Console.Multi_SetSmartFaderPitchMod, Deck.FlushNetDormancy ...; follows Deck.OnConsoleRespawned, Deck.OnSyncStateChanged, Deck.OnTempoUnlocked |
| 2 | PlayDirectionSwitch | PlayDirection | stepped slider | -14.6, 5.1, 2.7 | bone directon_switch_bone | - | calls OwningPawn.Server_EndSlipReverse, Deck.EndSlipReverse, Deck.SetReversePlayback, Deck.BeginSlipReverse, OwningPawn.Server_BeginSlipReverse, PlayDirectionPanel.CreateDynamicMaterialInstance; follows Deck.OnDeckDirectionChanged |
| 3 | DeckQuantizeButton | Quantize | toggle button | -13.1, -9.0, 3.0 | marker Marker_DeckQuantize | - | calls Deck.SetQuantized |
| 4 | TempoSliderRangeButton | Tempo Range Adjust | button | 13.8, 4.5, 3.0 | marker Marker_TempoRange | - | calls Deck.CycleTempoRange, PitchSlider.FlushNetDormancy, PitchSlider.OnRep_MaxPitchModulation |
| 5 | TimeModeButton | Time Mode | toggle button | -14.0, -11.0, 3.0 | marker Marker_AutoCue | - | calls Deck.SetTimeMode |
| 6 | JogWheel3000 | JogWheel | jog wheel | 0.0, 8.3, 3.8 | bone outer_jog_wheel_bone | - | calls JogWheelFlashingRing.CreateDynamicMaterialInstance; follows Deck.OnAlbumArtRequested, Deck.OnConsoleRespawned, Deck.OnJogModeChanged, Deck.OnSlipModeChanged ... |
| 7 | JogAdjust | Jog Adjust | knob | 9.1, -0.4, 3.4 | bone jog_adjust_knob_bone | JogWheelToAffect=self.Jogwheel | generic behaviour of its kind |
| 8 | VinylModeToggle | Jog Mode | button | 14.8, -3.4, 2.8 | marker Marker_JogMode | JogModePanelTransform=CallFunc_MakeTransform_ReturnValue | calls Deck.SetJogMode; follows Deck.OnJogModeChanged |
| 9 | TrackSearchNextButton | Track Search Forward | button | -12.8, 8.8, 3.0 | marker Marker_TrackSearchNext | - | calls Deck.Multi_SetPositionFromFraction |
| 10 | TrackSearchPrevButton | Track Search Backward | button | -14.8, 8.7, 3.0 | marker Marker_TrackSearchPrev | - | calls Deck.Multi_SetPositionFromFraction |
| 11 | SearchButtonLeft | Search Backward | button | -14.7, 11.4, 3.0 | marker Marker_SearchRev | - | calls Deck.SetPlaybackMs, Deck.RealignBeatSync, Console.AutoSwitchSyncMaster (in SearchButtonRight) |
| 12 | SearchButtonRight | Search Forward | button | -12.8, 11.5, 3.0 | marker Marker_SearchFwd | - | calls Deck.SetPlaybackMs, Deck.RealignBeatSync, Console.AutoSwitchSyncMaster |
| 13 | NeedleSearch | NeedleSearch | fader | -0.1, -8.7, 2.9 | marker Marker_NeedleSearch | - | calls Console.AutoSwitchSyncMaster, Deck.SetPositionFromFraction, Deck.RealignBeatSync |
| 14 | LoopInButton | Loop In/Cue | button | -14.8, -3.4, 3.0 | marker Marker_LoopIn | - | calls Deck.SetLoopAdjustmentMode, Deck.SetLoopInPosition, OwningPawn.Server_SetLoopIn; follows Deck.OnIsLoopingChanged, Deck.OnLoopInSet |
| 15 | LoopOutButton | LoopOut | button | -12.3, -3.4, 3.0 | marker Marker_LoopOut | - | calls Deck.SetLoopOutPosition, OwningPawn.Server_SetLoopOut, Deck.SetLoopAdjustmentMode, OwningPawn.Server_SetLoopAdjustmentMode; follows Deck.OnIsLoopingChanged |
| 16 | ReloopExitButton | Reloop/Exit | button | -9.2, -3.3, 2.9 | marker Marker_LoopExit | - | calls Deck.ReturnToLoop, Deck.ExitLoop; follows Deck.OnIsLoopingChanged |
| 17 | LoopCutButton | Loop Cutter | button | 4.7, -3.4, 2.9 | marker Marker_CueCallLeft | - | calls Deck.ClearMemoryCue, Deck.Multi_ClearMemoryCue, OwningPawn.Server_ClearMemoryCue, Deck.CutLoop, Deck.Multi_SeekToMemoryCue, OwningPawn.Server_SeekToMemoryCue |
| 18 | LoopExtendButton | Loop Extend | button | 6.5, -3.4, 2.9 | marker Marker_CueCallRight | - | calls Deck.ExtendLoop, Deck.Multi_SeekToMemoryCue, OwningPawn.Server_SeekToMemoryCue, Deck.SetMemoryCue, Deck.Multi_SetMemoryCue, OwningPawn.Server_SetMemoryCue |
| 19 | BeatLoopFourButton | 4 Beat Loop/Loop Cutter | button | -14.8, -0.7, 3.0 | marker Marker_BeatLoopLeft | - | calls Deck.CutLoop, OwningPawn.Server_CutLoop, OwningPawn.Server_SetLoopIn, OwningPawn.Server_SetLoopOut, Deck.SetBeatLoop |
| 20 | BeatLoopEightButton | 8 Beat Loop/Loop Extend | button | -12.2, -0.7, 3.0 | marker Marker_BeatLoopRight | - | calls Deck.ExtendLoop, OwningPawn.Server_ExtendLoop, OwningPawn.Server_SetLoopIn, OwningPawn.Server_SetLoopOut, Deck.SetBeatLoop |
| 21 | BeatJumpLeft | Beat Jump Backwards | button | -14.8, 1.7, 3.0 | marker Marker_BeatJumpLeft | - | calls Deck.PrevBeatJumpInterval, Deck.HandleLoopJump, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump |
| 22 | BeatJumpRight | Beat Jump Forwards | button | -12.3, 1.7, 3.0 | marker Marker_BeatJumpRight | - | calls Deck.NextBeatJumpInterval, Deck.HandleLoopJump, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump, Deck.Multi_JumpLoop ... |
| 23 | MemoryButton | Memory | button | 10.5, -3.4, 2.9 | marker Marker_Memory | - | calls Deck.SetMemoryCue, Deck.Multi_SetMemoryCue, OwningPawn.Server_SetMemoryCue |
| 24 | DeleteButton | Delete | button | 8.7, -3.4, 2.9 | marker Marker_Delete | - | calls Deck.ClearMemoryCue, Deck.Multi_ClearMemoryCue, OwningPawn.Server_ClearMemoryCue |
| 25 | HotCueCallDelToggle | HotCueMode | button | -14.6, -5.8, 2.9 | marker Marker_HotCueRecCall | - | calls Deck.SetHotCueMode, OwningPawn.Server_SetHotCueMode; follows Deck.OnHotCueModeChanged |
| 26 | HotCueButton | Hot Cue {X} | button | -10.5, -5.8, 2.9 | marker Marker_HotCueA | HotCueIndex=0 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 27 | HotCueButton | Hot Cue {X} | button | -7.5, -5.8, 2.9 | marker Marker_HotCueB | HotCueIndex=1 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 28 | HotCueButton | Hot Cue {X} | button | -4.5, -5.8, 2.9 | marker Marker_HotCueC | HotCueIndex=2 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 29 | HotCueButton | Hot Cue {X} | button | -1.5, -5.8, 2.9 | marker Marker_HotCueD | HotCueIndex=3 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 30 | HotCueButton | Hot Cue {X} | button | 1.5, -5.8, 2.9 | marker Marker_HotCueE | HotCueIndex=4 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 31 | HotCueButton | Hot Cue {X} | button | 4.5, -5.8, 2.9 | marker Marker_HotCueF | HotCueIndex=5 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 32 | HotCueButton | Hot Cue {X} | button | 7.5, -5.8, 2.9 | marker Marker_HotCueG | HotCueIndex=6 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 33 | HotCueButton | Hot Cue {X} | button | 10.5, -5.8, 2.9 | marker Marker_HotCueH | HotCueIndex=7 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 34 | TouchBrakeKnob | Vinyl Speed Adjust Touch/Brake | knob | 13.7, -5.9, 3.5 | bone touch_brake_knob_bone | DefaultRotationFraction=0 | calls Deck.SetTouchBrake |
| 35 | SyncButton | Sync | button | 12.8, -0.5, 2.9 | marker Marker_BeatSyncSlave | - | calls ChannelDevice.End Sync, ChannelDevice.SetSyncMode, ChannelDevice.ToggleSync, SyncButtonInstanced.SetHiddenInGame, OwningPawn.Server_ToggleSync, ChannelDevice.StartSync ...; follows ChannelDevice.OnConsoleRespawned, ChannelDevice.OnSyncStateChanged |
| 36 | SyncMasterButton | Sync Master | button | 14.8, -0.5, 2.9 | marker Marker_SyncMaster | - | calls ChannelDevice.ToggleSyncMaster, SyncButtonInstanced.SetHiddenInGame, ChannelDevice.SetSyncMaster, SyncButtonInstanced.SetStaticMesh; follows ChannelDevice.OnConsoleRespawned |
| 37 | CueButton | Cue | button | -13.8, 15.3, 2.9 | marker Marker_Cue | - | calls Deck.StopCuePreview, OwningPawn.Server_SeekToCue, PlayButton.Grab, PlayButton.Release, Deck.StartCuePreview, Deck.SetPlaybackMs ...; follows Deck.OnConsoleRespawned, Deck.OnCuePreviewCleared, Deck.OnDeckPause, Deck.OnDeckPlay ... |
| 38 | PlayButton | Play | button | -13.8, 19.9, 2.9 | marker Marker_Play | - | calls Deck.ClearCuePreview, OwningPawn.Server_StartPlay, Deck.Stop Play, OwningPawn.Server_StopPlay, Deck.Start Play; follows Deck.OnCuePreviewCleared, Deck.OnDeckPause, Deck.OnDeckPlay, Deck.OnTrackChanged ... |
| 39 | MasterTempoButton | Master Tempo | toggle button | 13.8, 6.9, 3.0 | marker Marker_MasterTempo | - | calls Deck.SetMasterTempo, KeySyncButton.SetButtonOn; follows Deck.OnKeySyncChanged |
| 40 | SlipButton | Slip | toggle button | -15.0, -9.0, 2.9 | marker Marker_Slip | - | calls Deck.SetSlip; follows AudioPlayer.OnSlipConditionChanged, Deck.OnSlipModeChanged |
| 41 | TempoResetButton | Tempo Reset | toggle button | 10.6, 14.6, 2.9 | marker Marker_TempoReset | - | calls Deck.SetTempoLocked, TempoResetPanel.CreateDynamicMaterialInstance, TempoResetPanel.SetVisibility |
| 42 | KeySyncButton | KeySync | toggle button | 13.8, 1.2, 2.9 | marker Marker_KeySync | - | calls Deck.ToggleKeySync; follows Deck.OnConsoleRespawned, Deck.OnTrackChanged, Mixer.OnMasterKeyChanged |
| 43 | BeatJumpScreenSelector | - | button | -7.1, -13.2, 3.8 | marker Marker_BeatJumpButton_1 | BeatJumpValue=19 | calls Deck.SetBeatJumpValue |
| 44 | BeatJumpScreenSelector | - | button | -5.0, -13.2, 3.8 | marker Marker_BeatJumpButton_2 | BeatJumpValue=22 | calls Deck.SetBeatJumpValue |
| 45 | BeatJumpScreenSelector | - | button | -3.0, -13.2, 3.8 | marker Marker_BeatJumpButton_3 | BeatJumpValue=24 | calls Deck.SetBeatJumpValue |
| 46 | BeatJumpScreenSelector | - | button | -0.9, -13.2, 3.8 | marker Marker_BeatJumpButton_4 | BeatJumpValue=26 | calls Deck.SetBeatJumpValue |
| 47 | BeatJumpScreenSelector | - | button | 1.2, -13.2, 3.8 | marker Marker_BeatJumpButton_5 | BeatJumpValue=28 | calls Deck.SetBeatJumpValue |
| 48 | BeatJumpScreenSelector | - | button | 3.3, -13.2, 3.8 | marker Marker_BeatJumpButton_6 | BeatJumpValue=29 | calls Deck.SetBeatJumpValue |
| 49 | BeatJumpScreenSelector | - | button | 5.3, -13.2, 3.8 | marker Marker_BeatJumpButton_7 | BeatJumpValue=30 | calls Deck.SetBeatJumpValue |
| 50 | BeatJumpScreenSelector | - | button | 7.4, -13.2, 3.8 | marker Marker_BeatJumpButton_8 | BeatJumpValue=31 | calls Deck.SetBeatJumpValue |
| 51 | BeatgridEditButton | Edit Beatgrid | button | 8.8, -11.8, 3.5 | marker Marker_BeatgridEditButton | - | calls Deck.ToggleBeatgridEditor |

## CDJ3000X

Model `BP_CDJ3000X_C` on `BP_CDJ3000_C`. model id `CDJ3000X`. SKU `Equipment_CDJ3000X`. 33.5 cm wide. control table `DT_CDJ3000X_ControlInfo`. skeleton `SK_CDJ3000X_Skeleton`.

This model's markers disagree with its bones (0 of 5 agree); the game uses the bone when the control table names one, so the positions below are the bones'.

| # | Control | Label | Kind | x, y, z (cm) | Placed by | Settings | What it does |
|---|---|---|---|---|---|---|---|
| 1 | PitchSlider | {BPM} BPM / {Tempo} / {Key} / ({Master BPM} {Mast… | fader | 4.4, -13.8, 9.2 | bone jnt_tempo_slider | - | calls Console.Multi_SetSmartFaderPitchMod_Reliable, Label.HighlightOnHover, Tribe_Game_Instance_BP.ThirdPersonSpectatorActive, SpectatorLabel.HighlightOnHover, Console.Multi_SetSmartFaderPitchMod, Deck.FlushNetDormancy ...; follows Deck.OnConsoleRespawned, Deck.OnSyncStateChanged, Deck.OnTempoUnlocked |
| 2 | PlayDirectionSwitch | PlayDirection | stepped slider | -4.6, 14.6, 9.4 | bone jnt_rev | - | calls OwningPawn.Server_EndSlipReverse, Deck.EndSlipReverse, Deck.SetReversePlayback, Deck.BeginSlipReverse, OwningPawn.Server_BeginSlipReverse, PlayDirectionPanel.CreateDynamicMaterialInstance; follows Deck.OnDeckDirectionChanged |
| 3 | DeckQuantizeButton | Quantize | toggle button | -14.8, -7.3, 8.7 | marker Marker_DeckQuantize | - | calls Deck.SetQuantized |
| 4 | TempoSliderRangeButton | Tempo Range Adjust | button | 13.8, 5.7, 8.7 | marker Marker_TempoRange | - | calls Deck.CycleTempoRange, PitchSlider.FlushNetDormancy, PitchSlider.OnRep_MaxPitchModulation |
| 5 | JogWheel3000X | JogWheel | jog wheel | -1.5, 0.0, 9.4 | bone jnt_jog_wheel | - | calls JogWheelFlashingRing.CreateDynamicMaterialInstance (in JogWheel3000); follows Deck.OnAlbumArtRequested, Deck.OnConsoleRespawned, Deck.OnJogModeChanged, Deck.OnSlipModeChanged ... |
| 6 | JogAdjust | Jog Adjust | knob | -9.8, -8.7, 9.2 | bone jnt_jog_feel | JogWheelToAffect=self.Jogwheel, JogwheelMinFriction=0.25, JogwheelMaxFriction=3.5 | generic behaviour of its kind |
| 7 | VinylModeToggle | Jog Mode | button | 14.8, -1.6, 8.6 | marker Marker_JogMode | JogModePanelTransform=CallFunc_MakeTransform_ReturnValue | calls Deck.SetJogMode; follows Deck.OnJogModeChanged |
| 8 | TrackSearchNextButton | Track Search Forward | button | -12.7, 9.8, 8.7 | marker Marker_TrackSearchNext | - | calls Deck.Multi_SetPositionFromFraction |
| 9 | TrackSearchPrevButton | Track Search Backward | button | -14.7, 9.7, 8.6 | marker Marker_TrackSearchPrev | - | calls Deck.Multi_SetPositionFromFraction |
| 10 | SearchButtonLeft | Search Backward | button | -14.7, 12.3, 8.6 | marker Marker_SearchRev | - | calls Deck.SetPlaybackMs, Deck.RealignBeatSync, Console.AutoSwitchSyncMaster (in SearchButtonRight) |
| 11 | SearchButtonRight | Search Forward | button | -12.7, 12.3, 8.6 | marker Marker_SearchFwd | - | calls Deck.SetPlaybackMs, Deck.RealignBeatSync, Console.AutoSwitchSyncMaster |
| 12 | NeedleSearch | NeedleSearch | fader | -0.2, -6.7, 9.0 | marker Marker_NeedleSearch | - | calls Console.AutoSwitchSyncMaster, Deck.SetPositionFromFraction, Deck.RealignBeatSync |
| 13 | LoopInButton | Loop In/Cue | button | -14.8, -1.7, 8.7 | marker Marker_LoopIn | - | calls Deck.SetLoopAdjustmentMode, Deck.SetLoopInPosition, OwningPawn.Server_SetLoopIn; follows Deck.OnIsLoopingChanged, Deck.OnLoopInSet |
| 14 | LoopOutButton | LoopOut | button | -12.2, -1.7, 8.7 | marker Marker_LoopOut | - | calls Deck.SetLoopOutPosition, OwningPawn.Server_SetLoopOut, Deck.SetLoopAdjustmentMode, OwningPawn.Server_SetLoopAdjustmentMode; follows Deck.OnIsLoopingChanged |
| 15 | ReloopExitButton | Reloop/Exit | button | -9.3, -1.7, 8.6 | marker Marker_LoopExit | - | calls Deck.ReturnToLoop, Deck.ExitLoop; follows Deck.OnIsLoopingChanged |
| 16 | LoopCutButton | Loop Cutter | button | 4.4, -1.7, 8.6 | marker Marker_CueCallLeft | - | calls Deck.ClearMemoryCue, Deck.Multi_ClearMemoryCue, OwningPawn.Server_ClearMemoryCue, Deck.CutLoop, Deck.Multi_SeekToMemoryCue, OwningPawn.Server_SeekToMemoryCue |
| 17 | LoopExtendButton | Loop Extend | button | 6.1, -1.7, 8.6 | marker Marker_CueCallRight | - | calls Deck.ExtendLoop, Deck.Multi_SeekToMemoryCue, OwningPawn.Server_SeekToMemoryCue, Deck.SetMemoryCue, Deck.Multi_SetMemoryCue, OwningPawn.Server_SetMemoryCue |
| 18 | BeatLoopFourButton | 4 Beat Loop/Loop Cutter | button | -14.8, 0.8, 8.7 | marker Marker_BeatLoopLeft | - | calls Deck.CutLoop, OwningPawn.Server_CutLoop, OwningPawn.Server_SetLoopIn, OwningPawn.Server_SetLoopOut, Deck.SetBeatLoop |
| 19 | BeatLoopEightButton | 8 Beat Loop/Loop Extend | button | -12.2, 0.8, 8.7 | marker Marker_BeatLoopRight | - | calls Deck.ExtendLoop, OwningPawn.Server_ExtendLoop, OwningPawn.Server_SetLoopIn, OwningPawn.Server_SetLoopOut, Deck.SetBeatLoop |
| 20 | BeatJumpLeft | Beat Jump Backwards | button | -14.8, 3.2, 8.7 | marker Marker_BeatJumpLeft | - | calls Deck.PrevBeatJumpInterval, Deck.HandleLoopJump, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump |
| 21 | BeatJumpRight | Beat Jump Forwards | button | -12.3, 3.2, 8.7 | marker Marker_BeatJumpRight | - | calls Deck.NextBeatJumpInterval, Deck.HandleLoopJump, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump, Deck.Multi_JumpLoop ... |
| 22 | MemoryButton | Memory | button | 9.9, -1.7, 8.6 | marker Marker_Memory | - | calls Deck.SetMemoryCue, Deck.Multi_SetMemoryCue, OwningPawn.Server_SetMemoryCue |
| 23 | DeleteButton | Delete | button | 8.2, -1.7, 8.6 | marker Marker_Delete | - | calls Deck.ClearMemoryCue, Deck.Multi_ClearMemoryCue, OwningPawn.Server_ClearMemoryCue |
| 24 | HotCueCallDelToggle | HotCueMode | button | -14.3, -4.1, 8.5 | marker Marker_HotCueRecCall | - | calls Deck.SetHotCueMode, OwningPawn.Server_SetHotCueMode; follows Deck.OnHotCueModeChanged |
| 25 | HotCueButton | Hot Cue {X} | button | -10.2, -4.1, 8.5 | marker Marker_HotCueA | HotCueIndex=0 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 26 | HotCueButton | Hot Cue {X} | button | -7.2, -4.1, 8.5 | marker Marker_HotCueB | HotCueIndex=1 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 27 | HotCueButton | Hot Cue {X} | button | -4.2, -4.1, 8.5 | marker Marker_HotCueC | HotCueIndex=2 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 28 | HotCueButton | Hot Cue {X} | button | -1.3, -4.1, 8.5 | marker Marker_HotCueD | HotCueIndex=3 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 29 | HotCueButton | Hot Cue {X} | button | 1.6, -4.1, 8.5 | marker Marker_HotCueE | HotCueIndex=4 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 30 | HotCueButton | Hot Cue {X} | button | 4.3, -4.1, 8.5 | marker Marker_HotCueF | HotCueIndex=5 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 31 | HotCueButton | Hot Cue {X} | button | 7.2, -4.1, 8.5 | marker Marker_HotCueG | HotCueIndex=6 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 32 | HotCueButton | Hot Cue {X} | button | 10.0, -4.1, 8.5 | marker Marker_HotCueH | HotCueIndex=7 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 33 | TouchBrakeKnob | Vinyl Speed Adjust Touch/Brake | knob | -14.9, -13.9, 9.3 | bone jnt_vinyl_speed_adj | DefaultRotationFraction=0 | calls Deck.SetTouchBrake |
| 34 | SyncButton | Sync | button | 12.8, 1.1, 8.6 | marker Marker_BeatSyncSlave | - | calls ChannelDevice.End Sync, ChannelDevice.SetSyncMode, ChannelDevice.ToggleSync, SyncButtonInstanced.SetHiddenInGame, OwningPawn.Server_ToggleSync, ChannelDevice.StartSync ...; follows ChannelDevice.OnConsoleRespawned, ChannelDevice.OnSyncStateChanged |
| 35 | SyncMasterButton | Sync Master | button | 14.8, 1.1, 8.6 | marker Marker_SyncMaster | - | calls ChannelDevice.ToggleSyncMaster, SyncButtonInstanced.SetHiddenInGame, ChannelDevice.SetSyncMaster, SyncButtonInstanced.SetStaticMesh; follows ChannelDevice.OnConsoleRespawned |
| 36 | CueButton | Cue | button | -13.7, 16.0, 8.6 | marker Marker_Cue | - | calls Deck.StopCuePreview, OwningPawn.Server_SeekToCue, PlayButton.Grab, PlayButton.Release, Deck.StartCuePreview, Deck.SetPlaybackMs ...; follows Deck.OnConsoleRespawned, Deck.OnCuePreviewCleared, Deck.OnDeckPause, Deck.OnDeckPlay ... |
| 37 | PlayButton | Play | button | -13.7, 20.3, 8.6 | marker Marker_Play | - | calls Deck.ClearCuePreview, OwningPawn.Server_StartPlay, Deck.Stop Play, OwningPawn.Server_StopPlay, Deck.Start Play; follows Deck.OnCuePreviewCleared, Deck.OnDeckPause, Deck.OnDeckPlay, Deck.OnTrackChanged ... |
| 38 | MasterTempoButton | Master Tempo | toggle button | 13.8, 8.1, 8.7 | marker Marker_MasterTempo | - | calls Deck.SetMasterTempo, KeySyncButton.SetButtonOn; follows Deck.OnKeySyncChanged |
| 39 | SlipButton | Slip | toggle button | -14.6, -6.0, 8.7 | marker Marker_Slip | - | calls Deck.SetSlip; follows AudioPlayer.OnSlipConditionChanged, Deck.OnSlipModeChanged |
| 40 | TempoResetButton | Tempo Reset | toggle button | 10.9, 15.2, 8.6 | marker Marker_TempoReset | - | calls Deck.SetTempoLocked, TempoResetPanel.CreateDynamicMaterialInstance, TempoResetPanel.SetVisibility |
| 41 | KeySyncButton | KeySync | toggle button | 13.8, 2.7, 8.6 | marker Marker_KeySync | - | calls Deck.ToggleKeySync; follows Deck.OnConsoleRespawned, Deck.OnTrackChanged, Mixer.OnMasterKeyChanged |
| 42 | ScreenLoopJumpButton | - | button | -7.8, -11.9, 10.0 | marker Marker_BeatJumpButton_1 | - | calls Deck.ExitLoop, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump, OwningPawn.Server_ExitLoop, Deck.HandleLoopJump ...; follows Deck.OnBeatLoopSet, Deck.OnIsLoopingChanged, Deck.OnScreenButtonBankChanged, Deck.OnScreenModeChanged ... |
| 43 | ScreenLoopJumpButton | - | button | -5.6, -11.9, 10.0 | marker Marker_BeatJumpButton_2 | ButtonIndex=1 | calls Deck.ExitLoop, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump, OwningPawn.Server_ExitLoop, Deck.HandleLoopJump ...; follows Deck.OnBeatLoopSet, Deck.OnIsLoopingChanged, Deck.OnScreenButtonBankChanged, Deck.OnScreenModeChanged ... |
| 44 | ScreenLoopJumpButton | - | button | -3.4, -11.9, 10.0 | marker Marker_BeatJumpButton_3 | ButtonIndex=2 | calls Deck.ExitLoop, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump, OwningPawn.Server_ExitLoop, Deck.HandleLoopJump ...; follows Deck.OnBeatLoopSet, Deck.OnIsLoopingChanged, Deck.OnScreenButtonBankChanged, Deck.OnScreenModeChanged ... |
| 45 | ScreenLoopJumpButton | - | button | -1.3, -11.9, 10.0 | marker Marker_BeatJumpButton_4 | ButtonIndex=3 | calls Deck.ExitLoop, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump, OwningPawn.Server_ExitLoop, Deck.HandleLoopJump ...; follows Deck.OnBeatLoopSet, Deck.OnIsLoopingChanged, Deck.OnScreenButtonBankChanged, Deck.OnScreenModeChanged ... |
| 46 | ScreenLoopJumpButton | - | button | 1.0, -11.9, 10.0 | marker Marker_BeatJumpButton_5 | ButtonIndex=4 | calls Deck.ExitLoop, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump, OwningPawn.Server_ExitLoop, Deck.HandleLoopJump ...; follows Deck.OnBeatLoopSet, Deck.OnIsLoopingChanged, Deck.OnScreenButtonBankChanged, Deck.OnScreenModeChanged ... |
| 47 | ScreenLoopJumpButton | - | button | 3.2, -11.9, 10.0 | marker Marker_BeatJumpButton_6 | ButtonIndex=5 | calls Deck.ExitLoop, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump, OwningPawn.Server_ExitLoop, Deck.HandleLoopJump ...; follows Deck.OnBeatLoopSet, Deck.OnIsLoopingChanged, Deck.OnScreenButtonBankChanged, Deck.OnScreenModeChanged ... |
| 48 | ScreenLoopJumpButton | - | button | 5.4, -11.9, 10.0 | marker Marker_BeatJumpButton_7 | ButtonIndex=6 | calls Deck.ExitLoop, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump, OwningPawn.Server_ExitLoop, Deck.HandleLoopJump ...; follows Deck.OnBeatLoopSet, Deck.OnIsLoopingChanged, Deck.OnScreenButtonBankChanged, Deck.OnScreenModeChanged ... |
| 49 | ScreenLoopJumpButton | - | button | 7.6, -11.9, 10.0 | marker Marker_BeatJumpButton_8 | ButtonIndex=7 | calls Deck.ExitLoop, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump, OwningPawn.Server_ExitLoop, Deck.HandleLoopJump ...; follows Deck.OnBeatLoopSet, Deck.OnIsLoopingChanged, Deck.OnScreenButtonBankChanged, Deck.OnScreenModeChanged ... |
| 50 | BeatgridEditButton | Edit Beatgrid | button | -10.3, -11.1, 9.8 | marker Marker_BeatgridEditButton | - | calls Deck.ToggleBeatgridEditor |
| 51 | ScreenModeSelectButton | Screen Mode {Mode} | toggle button | 5.9, -19.7, 11.6 | marker Marker_ScreenModeButtonBeatLoop | ScreenButtonMode=1 | calls Deck.SetActiveScreenMode; follows Deck.OnScreenModeChanged |
| 52 | ScreenModeSelectButton | Screen Mode {Mode} | toggle button | 8.0, -19.7, 11.6 | marker Marker_ScreenModeButtonKeyShift | ScreenButtonMode=2 | calls Deck.SetActiveScreenMode; follows Deck.OnScreenModeChanged |
| 53 | ScreenModeSelectButton | Screen Mode {Mode} | toggle button | 10.1, -19.7, 11.6 | marker Marker_ScreenModeButtonBeatJump | ScreenButtonMode=3 | calls Deck.SetActiveScreenMode; follows Deck.OnScreenModeChanged |
| 54 | ScreenButtonBankSelector | Screen Button Bank {Num} | button | 9.4, -11.9, 10.0 | marker Marker_ScreenBankButton1 | - | calls Deck.SetScreenButtonBank; follows Deck.OnScreenModeChanged |
| 55 | ScreenButtonBankSelector | Screen Button Bank {Num} | button | 10.2, -11.9, 10.0 | marker Marker_ScreenBankButton2 | BankNumber=1 | calls Deck.SetScreenButtonBank; follows Deck.OnScreenModeChanged |
| 56 | KeyShiftScreenButton | Key Shift {Dir} | button | -5.4, -11.9, 10.0 | marker Marker_KeyShiftDecrement | bIsLeft=true | calls Deck.DecrementKeyShift, Deck.IncrementKeyShift; follows Deck.OnKeyShiftChanged, Deck.OnScreenModeChanged |
| 57 | KeyShiftScreenButton | Key Shift {Dir} | button | 5.2, -11.9, 10.0 | marker Marker_KeyShiftIncrement | - | calls Deck.DecrementKeyShift, Deck.IncrementKeyShift; follows Deck.OnKeyShiftChanged, Deck.OnScreenModeChanged |
| 58 | KeyShiftResetButton | Key Shift Reset | button | -0.1, -11.3, 9.8 | marker Marker_KeyShiftReset | - | calls Deck.SetKeyShift; follows Deck.OnScreenModeChanged |

## DDJ-FLX4 (deck)

Model `BP_FLX4_C` on `BP_Deck_C`. model id `DDJ-FLX4`. SKU `Equipment_FLX4`. 33 cm wide. control table `DT_DDJ-FLX4_ControlInfo_1`. skeleton `SK_DDJ-FLX4_Skeleton`.

| # | Control | Label | Kind | x, y, z (cm) | Placed by | Settings | What it does |
|---|---|---|---|---|---|---|---|
| 1 | FXPad (pad 1) | PerformancePad | button | -28.9, 12.9, 1.6 | bone JPerfPad1 | BeatFXType=switch(Temp_int_Variable_16) {0: Temp_byte_Variable_47; 1: Temp_byte_Variable_46; 2: Temp_byte_Variable_45; 3: Temp_byte_Variable_44; 4: Temp_byte_Variable_43; 5: Temp_byte_Variable_42; 6: Temp_byte_Variable_41; 7: Temp_byte_Variable_40; default: K2Node_Select_Default_3}, BeatFxInterval=switch(Temp_int_Variable_14) {0: Temp_byte_Variable_31; 1: Temp_byte_Variable_30; 2: Temp_byte_Variable_29; 3: Temp_byte_Variable_28; 4: Temp_byte_Variable_27; 5: Temp_byte_Variable_26; 6: Temp_byte_Variable_25; 7: Temp_byte_Variable_24; default: K2Node_Select_Default_1}, ColorFXType=switch(Temp_int_Variable_15) {0: Temp_byte_Variable_39; 1: Temp_byte_Variable_38; 2: Temp_byte_Variable_37; 3: Temp_byte_Variable_36; 4: Temp_byte_Variable_35; 5: Temp_byte_Variable_34; 6: Temp_byte_Variable_33; 7: Temp_byte_Variable_32; default: K2Node_Select_Default_2}, DefaultLevel=switch(Temp_int_Variable_13) {0: Temp_real_Variable_15; 1: Temp_real_Variable_14; 2: Temp_real_Variable_13; 3: Temp_real_Variable_12; 4: Temp_real_Variable_11; 5: Temp_real_Variable_10; 6: Temp_real_Variable_9; 7: Temp_real_Variable_8; default: K2Node_Select_Default}, PadIndex=Temp_int_Variable_19 | calls Deck.SetSlip, Mixer.SetBeatFXPadEnabled, Mixer.SetColorFXPadEnabled, Mixer.DisableColorFXPad, Deck.ExitLoop, Mixer.DisableBeatFXPad ... |
| 2 | FXPad (pad 2) | PerformancePad | button | -25.5, 12.9, 1.6 | bone JPerfPad2 | BeatFXType=switch(Temp_int_Variable_16) {0: Temp_byte_Variable_47; 1: Temp_byte_Variable_46; 2: Temp_byte_Variable_45; 3: Temp_byte_Variable_44; 4: Temp_byte_Variable_43; 5: Temp_byte_Variable_42; 6: Temp_byte_Variable_41; 7: Temp_byte_Variable_40; default: K2Node_Select_Default_3}, BeatFxInterval=switch(Temp_int_Variable_14) {0: Temp_byte_Variable_31; 1: Temp_byte_Variable_30; 2: Temp_byte_Variable_29; 3: Temp_byte_Variable_28; 4: Temp_byte_Variable_27; 5: Temp_byte_Variable_26; 6: Temp_byte_Variable_25; 7: Temp_byte_Variable_24; default: K2Node_Select_Default_1}, ColorFXType=switch(Temp_int_Variable_15) {0: Temp_byte_Variable_39; 1: Temp_byte_Variable_38; 2: Temp_byte_Variable_37; 3: Temp_byte_Variable_36; 4: Temp_byte_Variable_35; 5: Temp_byte_Variable_34; 6: Temp_byte_Variable_33; 7: Temp_byte_Variable_32; default: K2Node_Select_Default_2}, DefaultLevel=switch(Temp_int_Variable_13) {0: Temp_real_Variable_15; 1: Temp_real_Variable_14; 2: Temp_real_Variable_13; 3: Temp_real_Variable_12; 4: Temp_real_Variable_11; 5: Temp_real_Variable_10; 6: Temp_real_Variable_9; 7: Temp_real_Variable_8; default: K2Node_Select_Default}, PadIndex=Temp_int_Variable_19 | as above |
| 3 | FXPad (pad 3) | PerformancePad | button | -22.2, 12.9, 1.6 | bone JPerfPad3 | BeatFXType=switch(Temp_int_Variable_16) {0: Temp_byte_Variable_47; 1: Temp_byte_Variable_46; 2: Temp_byte_Variable_45; 3: Temp_byte_Variable_44; 4: Temp_byte_Variable_43; 5: Temp_byte_Variable_42; 6: Temp_byte_Variable_41; 7: Temp_byte_Variable_40; default: K2Node_Select_Default_3}, BeatFxInterval=switch(Temp_int_Variable_14) {0: Temp_byte_Variable_31; 1: Temp_byte_Variable_30; 2: Temp_byte_Variable_29; 3: Temp_byte_Variable_28; 4: Temp_byte_Variable_27; 5: Temp_byte_Variable_26; 6: Temp_byte_Variable_25; 7: Temp_byte_Variable_24; default: K2Node_Select_Default_1}, ColorFXType=switch(Temp_int_Variable_15) {0: Temp_byte_Variable_39; 1: Temp_byte_Variable_38; 2: Temp_byte_Variable_37; 3: Temp_byte_Variable_36; 4: Temp_byte_Variable_35; 5: Temp_byte_Variable_34; 6: Temp_byte_Variable_33; 7: Temp_byte_Variable_32; default: K2Node_Select_Default_2}, DefaultLevel=switch(Temp_int_Variable_13) {0: Temp_real_Variable_15; 1: Temp_real_Variable_14; 2: Temp_real_Variable_13; 3: Temp_real_Variable_12; 4: Temp_real_Variable_11; 5: Temp_real_Variable_10; 6: Temp_real_Variable_9; 7: Temp_real_Variable_8; default: K2Node_Select_Default}, PadIndex=Temp_int_Variable_19 | as above |
| 4 | FXPad (pad 4) | PerformancePad | button | -18.8, 12.9, 1.6 | bone JPerfPad4 | BeatFXType=switch(Temp_int_Variable_16) {0: Temp_byte_Variable_47; 1: Temp_byte_Variable_46; 2: Temp_byte_Variable_45; 3: Temp_byte_Variable_44; 4: Temp_byte_Variable_43; 5: Temp_byte_Variable_42; 6: Temp_byte_Variable_41; 7: Temp_byte_Variable_40; default: K2Node_Select_Default_3}, BeatFxInterval=switch(Temp_int_Variable_14) {0: Temp_byte_Variable_31; 1: Temp_byte_Variable_30; 2: Temp_byte_Variable_29; 3: Temp_byte_Variable_28; 4: Temp_byte_Variable_27; 5: Temp_byte_Variable_26; 6: Temp_byte_Variable_25; 7: Temp_byte_Variable_24; default: K2Node_Select_Default_1}, ColorFXType=switch(Temp_int_Variable_15) {0: Temp_byte_Variable_39; 1: Temp_byte_Variable_38; 2: Temp_byte_Variable_37; 3: Temp_byte_Variable_36; 4: Temp_byte_Variable_35; 5: Temp_byte_Variable_34; 6: Temp_byte_Variable_33; 7: Temp_byte_Variable_32; default: K2Node_Select_Default_2}, DefaultLevel=switch(Temp_int_Variable_13) {0: Temp_real_Variable_15; 1: Temp_real_Variable_14; 2: Temp_real_Variable_13; 3: Temp_real_Variable_12; 4: Temp_real_Variable_11; 5: Temp_real_Variable_10; 6: Temp_real_Variable_9; 7: Temp_real_Variable_8; default: K2Node_Select_Default}, PadIndex=Temp_int_Variable_19 | as above |
| 5 | FXPad (pad 5) | PerformancePad | button | -28.9, 16.3, 1.6 | bone JPerfPad5 | BeatFXType=switch(Temp_int_Variable_16) {0: Temp_byte_Variable_47; 1: Temp_byte_Variable_46; 2: Temp_byte_Variable_45; 3: Temp_byte_Variable_44; 4: Temp_byte_Variable_43; 5: Temp_byte_Variable_42; 6: Temp_byte_Variable_41; 7: Temp_byte_Variable_40; default: K2Node_Select_Default_3}, BeatFxInterval=switch(Temp_int_Variable_14) {0: Temp_byte_Variable_31; 1: Temp_byte_Variable_30; 2: Temp_byte_Variable_29; 3: Temp_byte_Variable_28; 4: Temp_byte_Variable_27; 5: Temp_byte_Variable_26; 6: Temp_byte_Variable_25; 7: Temp_byte_Variable_24; default: K2Node_Select_Default_1}, ColorFXType=switch(Temp_int_Variable_15) {0: Temp_byte_Variable_39; 1: Temp_byte_Variable_38; 2: Temp_byte_Variable_37; 3: Temp_byte_Variable_36; 4: Temp_byte_Variable_35; 5: Temp_byte_Variable_34; 6: Temp_byte_Variable_33; 7: Temp_byte_Variable_32; default: K2Node_Select_Default_2}, DefaultLevel=switch(Temp_int_Variable_13) {0: Temp_real_Variable_15; 1: Temp_real_Variable_14; 2: Temp_real_Variable_13; 3: Temp_real_Variable_12; 4: Temp_real_Variable_11; 5: Temp_real_Variable_10; 6: Temp_real_Variable_9; 7: Temp_real_Variable_8; default: K2Node_Select_Default}, PadIndex=Temp_int_Variable_19 | as above |
| 6 | FXPad (pad 6) | PerformancePad | button | -25.5, 16.3, 1.6 | bone JPerfPad6 | BeatFXType=switch(Temp_int_Variable_16) {0: Temp_byte_Variable_47; 1: Temp_byte_Variable_46; 2: Temp_byte_Variable_45; 3: Temp_byte_Variable_44; 4: Temp_byte_Variable_43; 5: Temp_byte_Variable_42; 6: Temp_byte_Variable_41; 7: Temp_byte_Variable_40; default: K2Node_Select_Default_3}, BeatFxInterval=switch(Temp_int_Variable_14) {0: Temp_byte_Variable_31; 1: Temp_byte_Variable_30; 2: Temp_byte_Variable_29; 3: Temp_byte_Variable_28; 4: Temp_byte_Variable_27; 5: Temp_byte_Variable_26; 6: Temp_byte_Variable_25; 7: Temp_byte_Variable_24; default: K2Node_Select_Default_1}, ColorFXType=switch(Temp_int_Variable_15) {0: Temp_byte_Variable_39; 1: Temp_byte_Variable_38; 2: Temp_byte_Variable_37; 3: Temp_byte_Variable_36; 4: Temp_byte_Variable_35; 5: Temp_byte_Variable_34; 6: Temp_byte_Variable_33; 7: Temp_byte_Variable_32; default: K2Node_Select_Default_2}, DefaultLevel=switch(Temp_int_Variable_13) {0: Temp_real_Variable_15; 1: Temp_real_Variable_14; 2: Temp_real_Variable_13; 3: Temp_real_Variable_12; 4: Temp_real_Variable_11; 5: Temp_real_Variable_10; 6: Temp_real_Variable_9; 7: Temp_real_Variable_8; default: K2Node_Select_Default}, PadIndex=Temp_int_Variable_19 | as above |
| 7 | FXPad (pad 7) | PerformancePad | button | -22.2, 16.3, 1.6 | bone JPerfPad7 | BeatFXType=switch(Temp_int_Variable_16) {0: Temp_byte_Variable_47; 1: Temp_byte_Variable_46; 2: Temp_byte_Variable_45; 3: Temp_byte_Variable_44; 4: Temp_byte_Variable_43; 5: Temp_byte_Variable_42; 6: Temp_byte_Variable_41; 7: Temp_byte_Variable_40; default: K2Node_Select_Default_3}, BeatFxInterval=switch(Temp_int_Variable_14) {0: Temp_byte_Variable_31; 1: Temp_byte_Variable_30; 2: Temp_byte_Variable_29; 3: Temp_byte_Variable_28; 4: Temp_byte_Variable_27; 5: Temp_byte_Variable_26; 6: Temp_byte_Variable_25; 7: Temp_byte_Variable_24; default: K2Node_Select_Default_1}, ColorFXType=switch(Temp_int_Variable_15) {0: Temp_byte_Variable_39; 1: Temp_byte_Variable_38; 2: Temp_byte_Variable_37; 3: Temp_byte_Variable_36; 4: Temp_byte_Variable_35; 5: Temp_byte_Variable_34; 6: Temp_byte_Variable_33; 7: Temp_byte_Variable_32; default: K2Node_Select_Default_2}, DefaultLevel=switch(Temp_int_Variable_13) {0: Temp_real_Variable_15; 1: Temp_real_Variable_14; 2: Temp_real_Variable_13; 3: Temp_real_Variable_12; 4: Temp_real_Variable_11; 5: Temp_real_Variable_10; 6: Temp_real_Variable_9; 7: Temp_real_Variable_8; default: K2Node_Select_Default}, PadIndex=Temp_int_Variable_19 | as above |
| 8 | FXPad (pad 8) | PerformancePad | button | -18.8, 16.3, 1.6 | bone JPerfPad8 | BeatFXType=switch(Temp_int_Variable_16) {0: Temp_byte_Variable_47; 1: Temp_byte_Variable_46; 2: Temp_byte_Variable_45; 3: Temp_byte_Variable_44; 4: Temp_byte_Variable_43; 5: Temp_byte_Variable_42; 6: Temp_byte_Variable_41; 7: Temp_byte_Variable_40; default: K2Node_Select_Default_3}, BeatFxInterval=switch(Temp_int_Variable_14) {0: Temp_byte_Variable_31; 1: Temp_byte_Variable_30; 2: Temp_byte_Variable_29; 3: Temp_byte_Variable_28; 4: Temp_byte_Variable_27; 5: Temp_byte_Variable_26; 6: Temp_byte_Variable_25; 7: Temp_byte_Variable_24; default: K2Node_Select_Default_1}, ColorFXType=switch(Temp_int_Variable_15) {0: Temp_byte_Variable_39; 1: Temp_byte_Variable_38; 2: Temp_byte_Variable_37; 3: Temp_byte_Variable_36; 4: Temp_byte_Variable_35; 5: Temp_byte_Variable_34; 6: Temp_byte_Variable_33; 7: Temp_byte_Variable_32; default: K2Node_Select_Default_2}, DefaultLevel=switch(Temp_int_Variable_13) {0: Temp_real_Variable_15; 1: Temp_real_Variable_14; 2: Temp_real_Variable_13; 3: Temp_real_Variable_12; 4: Temp_real_Variable_11; 5: Temp_real_Variable_10; 6: Temp_real_Variable_9; 7: Temp_real_Variable_8; default: K2Node_Select_Default}, PadIndex=Temp_int_Variable_19 | as above |
| 9 | HotCuePad (pad 1) | PerformancePad | control | -28.9, 12.9, 1.6 | bone JPerfPad1 | HotCueIndex=Temp_int_Variable_22 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ... (in HotCueButton); follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 10 | HotCuePad (pad 2) | PerformancePad | control | -25.5, 12.9, 1.6 | bone JPerfPad2 | HotCueIndex=Temp_int_Variable_22 | as above |
| 11 | HotCuePad (pad 3) | PerformancePad | control | -22.2, 12.9, 1.6 | bone JPerfPad3 | HotCueIndex=Temp_int_Variable_22 | as above |
| 12 | HotCuePad (pad 4) | PerformancePad | control | -18.8, 12.9, 1.6 | bone JPerfPad4 | HotCueIndex=Temp_int_Variable_22 | as above |
| 13 | HotCuePad (pad 5) | PerformancePad | control | -28.9, 16.3, 1.6 | bone JPerfPad5 | HotCueIndex=Temp_int_Variable_22 | as above |
| 14 | HotCuePad (pad 6) | PerformancePad | control | -25.5, 16.3, 1.6 | bone JPerfPad6 | HotCueIndex=Temp_int_Variable_22 | as above |
| 15 | HotCuePad (pad 7) | PerformancePad | control | -22.2, 16.3, 1.6 | bone JPerfPad7 | HotCueIndex=Temp_int_Variable_22 | as above |
| 16 | HotCuePad (pad 8) | PerformancePad | control | -18.8, 16.3, 1.6 | bone JPerfPad8 | HotCueIndex=Temp_int_Variable_22 | as above |
| 17 | BeatJumpPad (pad 1) | PerformancePad | button | -28.9, 12.9, 1.6 | bone JPerfPad1 | BeatJumpValue=switch(Temp_int_Variable_26) {0: Temp_real_Variable_28; 1: Temp_real_Variable_30; 2: Temp_real_Variable_24; 3: Temp_real_Variable_25; 4: Temp_real_Variable_26; 5: Temp_real_Variable_27; 6: Temp_real_Variable_29; 7: Temp_real_Variable_31; default: K2Node_Select_Default_11}, PadIndex=Temp_int_Variable_18 | calls Deck.HandleLoopJump, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump |
| 18 | BeatJumpPad (pad 2) | PerformancePad | button | -25.5, 12.9, 1.6 | bone JPerfPad2 | BeatJumpValue=switch(Temp_int_Variable_26) {0: Temp_real_Variable_28; 1: Temp_real_Variable_30; 2: Temp_real_Variable_24; 3: Temp_real_Variable_25; 4: Temp_real_Variable_26; 5: Temp_real_Variable_27; 6: Temp_real_Variable_29; 7: Temp_real_Variable_31; default: K2Node_Select_Default_11}, PadIndex=Temp_int_Variable_18 | as above |
| 19 | BeatJumpPad (pad 3) | PerformancePad | button | -22.2, 12.9, 1.6 | bone JPerfPad3 | BeatJumpValue=switch(Temp_int_Variable_26) {0: Temp_real_Variable_28; 1: Temp_real_Variable_30; 2: Temp_real_Variable_24; 3: Temp_real_Variable_25; 4: Temp_real_Variable_26; 5: Temp_real_Variable_27; 6: Temp_real_Variable_29; 7: Temp_real_Variable_31; default: K2Node_Select_Default_11}, PadIndex=Temp_int_Variable_18 | as above |
| 20 | BeatJumpPad (pad 4) | PerformancePad | button | -18.8, 12.9, 1.6 | bone JPerfPad4 | BeatJumpValue=switch(Temp_int_Variable_26) {0: Temp_real_Variable_28; 1: Temp_real_Variable_30; 2: Temp_real_Variable_24; 3: Temp_real_Variable_25; 4: Temp_real_Variable_26; 5: Temp_real_Variable_27; 6: Temp_real_Variable_29; 7: Temp_real_Variable_31; default: K2Node_Select_Default_11}, PadIndex=Temp_int_Variable_18 | as above |
| 21 | BeatJumpPad (pad 5) | PerformancePad | button | -28.9, 16.3, 1.6 | bone JPerfPad5 | BeatJumpValue=switch(Temp_int_Variable_26) {0: Temp_real_Variable_28; 1: Temp_real_Variable_30; 2: Temp_real_Variable_24; 3: Temp_real_Variable_25; 4: Temp_real_Variable_26; 5: Temp_real_Variable_27; 6: Temp_real_Variable_29; 7: Temp_real_Variable_31; default: K2Node_Select_Default_11}, PadIndex=Temp_int_Variable_18 | as above |
| 22 | BeatJumpPad (pad 6) | PerformancePad | button | -25.5, 16.3, 1.6 | bone JPerfPad6 | BeatJumpValue=switch(Temp_int_Variable_26) {0: Temp_real_Variable_28; 1: Temp_real_Variable_30; 2: Temp_real_Variable_24; 3: Temp_real_Variable_25; 4: Temp_real_Variable_26; 5: Temp_real_Variable_27; 6: Temp_real_Variable_29; 7: Temp_real_Variable_31; default: K2Node_Select_Default_11}, PadIndex=Temp_int_Variable_18 | as above |
| 23 | BeatJumpPad (pad 7) | PerformancePad | button | -22.2, 16.3, 1.6 | bone JPerfPad7 | BeatJumpValue=switch(Temp_int_Variable_26) {0: Temp_real_Variable_28; 1: Temp_real_Variable_30; 2: Temp_real_Variable_24; 3: Temp_real_Variable_25; 4: Temp_real_Variable_26; 5: Temp_real_Variable_27; 6: Temp_real_Variable_29; 7: Temp_real_Variable_31; default: K2Node_Select_Default_11}, PadIndex=Temp_int_Variable_18 | as above |
| 24 | BeatJumpPad (pad 8) | PerformancePad | button | -18.8, 16.3, 1.6 | bone JPerfPad8 | BeatJumpValue=switch(Temp_int_Variable_26) {0: Temp_real_Variable_28; 1: Temp_real_Variable_30; 2: Temp_real_Variable_24; 3: Temp_real_Variable_25; 4: Temp_real_Variable_26; 5: Temp_real_Variable_27; 6: Temp_real_Variable_29; 7: Temp_real_Variable_31; default: K2Node_Select_Default_11}, PadIndex=Temp_int_Variable_18 | as above |
| 25 | SamplerPad (pad 1) | PerformancePad | button | -28.9, 12.9, 1.6 | bone JPerfPad1 | SamplePath=CallFunc_Concat_StrStr_ReturnValue_1, PadIndex=Temp_int_Variable_20 | calls SamplePlayer.Open, SamplePlayer.Play |
| 26 | SamplerPad (pad 2) | PerformancePad | button | -25.5, 12.9, 1.6 | bone JPerfPad2 | SamplePath=CallFunc_Concat_StrStr_ReturnValue_1, PadIndex=Temp_int_Variable_20 | as above |
| 27 | SamplerPad (pad 3) | PerformancePad | button | -22.2, 12.9, 1.6 | bone JPerfPad3 | SamplePath=CallFunc_Concat_StrStr_ReturnValue_1, PadIndex=Temp_int_Variable_20 | as above |
| 28 | SamplerPad (pad 4) | PerformancePad | button | -18.8, 12.9, 1.6 | bone JPerfPad4 | SamplePath=CallFunc_Concat_StrStr_ReturnValue_1, PadIndex=Temp_int_Variable_20 | as above |
| 29 | SamplerPad (pad 5) | PerformancePad | button | -28.9, 16.3, 1.6 | bone JPerfPad5 | SamplePath=CallFunc_Concat_StrStr_ReturnValue_1, PadIndex=Temp_int_Variable_20 | as above |
| 30 | SamplerPad (pad 6) | PerformancePad | button | -25.5, 16.3, 1.6 | bone JPerfPad6 | SamplePath=CallFunc_Concat_StrStr_ReturnValue_1, PadIndex=Temp_int_Variable_20 | as above |
| 31 | SamplerPad (pad 7) | PerformancePad | button | -22.2, 16.3, 1.6 | bone JPerfPad7 | SamplePath=CallFunc_Concat_StrStr_ReturnValue_1, PadIndex=Temp_int_Variable_20 | as above |
| 32 | SamplerPad (pad 8) | PerformancePad | button | -18.8, 16.3, 1.6 | bone JPerfPad8 | SamplePath=CallFunc_Concat_StrStr_ReturnValue_1, PadIndex=Temp_int_Variable_20 | as above |
| 33 | FXPad (pad 1) | PerformancePad | button | -28.9, 12.9, 1.6 | bone JPerfPad1 | BeatFXType=switch(Temp_int_Variable_12) {0: Temp_byte_Variable_23; 1: Temp_byte_Variable_22; 2: Temp_byte_Variable_21; 3: Temp_byte_Variable_20; 4: Temp_byte_Variable_19; 5: Temp_byte_Variable_18; 6: Temp_byte_Variable_17; 7: Temp_byte_Variable_16; default: K2Node_Select_Default_8}, BeatFxInterval=switch(Temp_int_Variable_10) {0: Temp_byte_Variable_7; 1: Temp_byte_Variable_6; 2: Temp_byte_Variable_5; 3: Temp_byte_Variable_4; 4: Temp_byte_Variable_3; 5: Temp_byte_Variable_2; 6: Temp_byte_Variable_1; 7: Temp_byte_Variable; default: K2Node_Select_Default_6}, ColorFXType=switch(Temp_int_Variable_11) {0: Temp_byte_Variable_15; 1: Temp_byte_Variable_14; 2: Temp_byte_Variable_13; 3: Temp_byte_Variable_12; 4: Temp_byte_Variable_11; 5: Temp_byte_Variable_10; 6: Temp_byte_Variable_9; 7: Temp_byte_Variable_8; default: K2Node_Select_Default_7}, DefaultLevel=switch(Temp_int_Variable_9) {0: Temp_real_Variable_7; 1: Temp_real_Variable_6; 2: Temp_real_Variable_5; 3: Temp_real_Variable_4; 4: Temp_real_Variable_3; 5: Temp_real_Variable_2; 6: Temp_real_Variable_1; 7: Temp_real_Variable; default: K2Node_Select_Default_5}, PadIndex=Temp_int_Variable_23 | calls Deck.SetSlip, Mixer.SetBeatFXPadEnabled, Mixer.SetColorFXPadEnabled, Mixer.DisableColorFXPad, Deck.ExitLoop, Mixer.DisableBeatFXPad ... |
| 34 | FXPad (pad 2) | PerformancePad | button | -25.5, 12.9, 1.6 | bone JPerfPad2 | BeatFXType=switch(Temp_int_Variable_12) {0: Temp_byte_Variable_23; 1: Temp_byte_Variable_22; 2: Temp_byte_Variable_21; 3: Temp_byte_Variable_20; 4: Temp_byte_Variable_19; 5: Temp_byte_Variable_18; 6: Temp_byte_Variable_17; 7: Temp_byte_Variable_16; default: K2Node_Select_Default_8}, BeatFxInterval=switch(Temp_int_Variable_10) {0: Temp_byte_Variable_7; 1: Temp_byte_Variable_6; 2: Temp_byte_Variable_5; 3: Temp_byte_Variable_4; 4: Temp_byte_Variable_3; 5: Temp_byte_Variable_2; 6: Temp_byte_Variable_1; 7: Temp_byte_Variable; default: K2Node_Select_Default_6}, ColorFXType=switch(Temp_int_Variable_11) {0: Temp_byte_Variable_15; 1: Temp_byte_Variable_14; 2: Temp_byte_Variable_13; 3: Temp_byte_Variable_12; 4: Temp_byte_Variable_11; 5: Temp_byte_Variable_10; 6: Temp_byte_Variable_9; 7: Temp_byte_Variable_8; default: K2Node_Select_Default_7}, DefaultLevel=switch(Temp_int_Variable_9) {0: Temp_real_Variable_7; 1: Temp_real_Variable_6; 2: Temp_real_Variable_5; 3: Temp_real_Variable_4; 4: Temp_real_Variable_3; 5: Temp_real_Variable_2; 6: Temp_real_Variable_1; 7: Temp_real_Variable; default: K2Node_Select_Default_5}, PadIndex=Temp_int_Variable_23 | as above |
| 35 | FXPad (pad 3) | PerformancePad | button | -22.2, 12.9, 1.6 | bone JPerfPad3 | BeatFXType=switch(Temp_int_Variable_12) {0: Temp_byte_Variable_23; 1: Temp_byte_Variable_22; 2: Temp_byte_Variable_21; 3: Temp_byte_Variable_20; 4: Temp_byte_Variable_19; 5: Temp_byte_Variable_18; 6: Temp_byte_Variable_17; 7: Temp_byte_Variable_16; default: K2Node_Select_Default_8}, BeatFxInterval=switch(Temp_int_Variable_10) {0: Temp_byte_Variable_7; 1: Temp_byte_Variable_6; 2: Temp_byte_Variable_5; 3: Temp_byte_Variable_4; 4: Temp_byte_Variable_3; 5: Temp_byte_Variable_2; 6: Temp_byte_Variable_1; 7: Temp_byte_Variable; default: K2Node_Select_Default_6}, ColorFXType=switch(Temp_int_Variable_11) {0: Temp_byte_Variable_15; 1: Temp_byte_Variable_14; 2: Temp_byte_Variable_13; 3: Temp_byte_Variable_12; 4: Temp_byte_Variable_11; 5: Temp_byte_Variable_10; 6: Temp_byte_Variable_9; 7: Temp_byte_Variable_8; default: K2Node_Select_Default_7}, DefaultLevel=switch(Temp_int_Variable_9) {0: Temp_real_Variable_7; 1: Temp_real_Variable_6; 2: Temp_real_Variable_5; 3: Temp_real_Variable_4; 4: Temp_real_Variable_3; 5: Temp_real_Variable_2; 6: Temp_real_Variable_1; 7: Temp_real_Variable; default: K2Node_Select_Default_5}, PadIndex=Temp_int_Variable_23 | as above |
| 36 | FXPad (pad 4) | PerformancePad | button | -18.8, 12.9, 1.6 | bone JPerfPad4 | BeatFXType=switch(Temp_int_Variable_12) {0: Temp_byte_Variable_23; 1: Temp_byte_Variable_22; 2: Temp_byte_Variable_21; 3: Temp_byte_Variable_20; 4: Temp_byte_Variable_19; 5: Temp_byte_Variable_18; 6: Temp_byte_Variable_17; 7: Temp_byte_Variable_16; default: K2Node_Select_Default_8}, BeatFxInterval=switch(Temp_int_Variable_10) {0: Temp_byte_Variable_7; 1: Temp_byte_Variable_6; 2: Temp_byte_Variable_5; 3: Temp_byte_Variable_4; 4: Temp_byte_Variable_3; 5: Temp_byte_Variable_2; 6: Temp_byte_Variable_1; 7: Temp_byte_Variable; default: K2Node_Select_Default_6}, ColorFXType=switch(Temp_int_Variable_11) {0: Temp_byte_Variable_15; 1: Temp_byte_Variable_14; 2: Temp_byte_Variable_13; 3: Temp_byte_Variable_12; 4: Temp_byte_Variable_11; 5: Temp_byte_Variable_10; 6: Temp_byte_Variable_9; 7: Temp_byte_Variable_8; default: K2Node_Select_Default_7}, DefaultLevel=switch(Temp_int_Variable_9) {0: Temp_real_Variable_7; 1: Temp_real_Variable_6; 2: Temp_real_Variable_5; 3: Temp_real_Variable_4; 4: Temp_real_Variable_3; 5: Temp_real_Variable_2; 6: Temp_real_Variable_1; 7: Temp_real_Variable; default: K2Node_Select_Default_5}, PadIndex=Temp_int_Variable_23 | as above |
| 37 | FXPad (pad 5) | PerformancePad | button | -28.9, 16.3, 1.6 | bone JPerfPad5 | BeatFXType=switch(Temp_int_Variable_12) {0: Temp_byte_Variable_23; 1: Temp_byte_Variable_22; 2: Temp_byte_Variable_21; 3: Temp_byte_Variable_20; 4: Temp_byte_Variable_19; 5: Temp_byte_Variable_18; 6: Temp_byte_Variable_17; 7: Temp_byte_Variable_16; default: K2Node_Select_Default_8}, BeatFxInterval=switch(Temp_int_Variable_10) {0: Temp_byte_Variable_7; 1: Temp_byte_Variable_6; 2: Temp_byte_Variable_5; 3: Temp_byte_Variable_4; 4: Temp_byte_Variable_3; 5: Temp_byte_Variable_2; 6: Temp_byte_Variable_1; 7: Temp_byte_Variable; default: K2Node_Select_Default_6}, ColorFXType=switch(Temp_int_Variable_11) {0: Temp_byte_Variable_15; 1: Temp_byte_Variable_14; 2: Temp_byte_Variable_13; 3: Temp_byte_Variable_12; 4: Temp_byte_Variable_11; 5: Temp_byte_Variable_10; 6: Temp_byte_Variable_9; 7: Temp_byte_Variable_8; default: K2Node_Select_Default_7}, DefaultLevel=switch(Temp_int_Variable_9) {0: Temp_real_Variable_7; 1: Temp_real_Variable_6; 2: Temp_real_Variable_5; 3: Temp_real_Variable_4; 4: Temp_real_Variable_3; 5: Temp_real_Variable_2; 6: Temp_real_Variable_1; 7: Temp_real_Variable; default: K2Node_Select_Default_5}, PadIndex=Temp_int_Variable_23 | as above |
| 38 | FXPad (pad 6) | PerformancePad | button | -25.5, 16.3, 1.6 | bone JPerfPad6 | BeatFXType=switch(Temp_int_Variable_12) {0: Temp_byte_Variable_23; 1: Temp_byte_Variable_22; 2: Temp_byte_Variable_21; 3: Temp_byte_Variable_20; 4: Temp_byte_Variable_19; 5: Temp_byte_Variable_18; 6: Temp_byte_Variable_17; 7: Temp_byte_Variable_16; default: K2Node_Select_Default_8}, BeatFxInterval=switch(Temp_int_Variable_10) {0: Temp_byte_Variable_7; 1: Temp_byte_Variable_6; 2: Temp_byte_Variable_5; 3: Temp_byte_Variable_4; 4: Temp_byte_Variable_3; 5: Temp_byte_Variable_2; 6: Temp_byte_Variable_1; 7: Temp_byte_Variable; default: K2Node_Select_Default_6}, ColorFXType=switch(Temp_int_Variable_11) {0: Temp_byte_Variable_15; 1: Temp_byte_Variable_14; 2: Temp_byte_Variable_13; 3: Temp_byte_Variable_12; 4: Temp_byte_Variable_11; 5: Temp_byte_Variable_10; 6: Temp_byte_Variable_9; 7: Temp_byte_Variable_8; default: K2Node_Select_Default_7}, DefaultLevel=switch(Temp_int_Variable_9) {0: Temp_real_Variable_7; 1: Temp_real_Variable_6; 2: Temp_real_Variable_5; 3: Temp_real_Variable_4; 4: Temp_real_Variable_3; 5: Temp_real_Variable_2; 6: Temp_real_Variable_1; 7: Temp_real_Variable; default: K2Node_Select_Default_5}, PadIndex=Temp_int_Variable_23 | as above |
| 39 | FXPad (pad 7) | PerformancePad | button | -22.2, 16.3, 1.6 | bone JPerfPad7 | BeatFXType=switch(Temp_int_Variable_12) {0: Temp_byte_Variable_23; 1: Temp_byte_Variable_22; 2: Temp_byte_Variable_21; 3: Temp_byte_Variable_20; 4: Temp_byte_Variable_19; 5: Temp_byte_Variable_18; 6: Temp_byte_Variable_17; 7: Temp_byte_Variable_16; default: K2Node_Select_Default_8}, BeatFxInterval=switch(Temp_int_Variable_10) {0: Temp_byte_Variable_7; 1: Temp_byte_Variable_6; 2: Temp_byte_Variable_5; 3: Temp_byte_Variable_4; 4: Temp_byte_Variable_3; 5: Temp_byte_Variable_2; 6: Temp_byte_Variable_1; 7: Temp_byte_Variable; default: K2Node_Select_Default_6}, ColorFXType=switch(Temp_int_Variable_11) {0: Temp_byte_Variable_15; 1: Temp_byte_Variable_14; 2: Temp_byte_Variable_13; 3: Temp_byte_Variable_12; 4: Temp_byte_Variable_11; 5: Temp_byte_Variable_10; 6: Temp_byte_Variable_9; 7: Temp_byte_Variable_8; default: K2Node_Select_Default_7}, DefaultLevel=switch(Temp_int_Variable_9) {0: Temp_real_Variable_7; 1: Temp_real_Variable_6; 2: Temp_real_Variable_5; 3: Temp_real_Variable_4; 4: Temp_real_Variable_3; 5: Temp_real_Variable_2; 6: Temp_real_Variable_1; 7: Temp_real_Variable; default: K2Node_Select_Default_5}, PadIndex=Temp_int_Variable_23 | as above |
| 40 | FXPad (pad 8) | PerformancePad | button | -18.8, 16.3, 1.6 | bone JPerfPad8 | BeatFXType=switch(Temp_int_Variable_12) {0: Temp_byte_Variable_23; 1: Temp_byte_Variable_22; 2: Temp_byte_Variable_21; 3: Temp_byte_Variable_20; 4: Temp_byte_Variable_19; 5: Temp_byte_Variable_18; 6: Temp_byte_Variable_17; 7: Temp_byte_Variable_16; default: K2Node_Select_Default_8}, BeatFxInterval=switch(Temp_int_Variable_10) {0: Temp_byte_Variable_7; 1: Temp_byte_Variable_6; 2: Temp_byte_Variable_5; 3: Temp_byte_Variable_4; 4: Temp_byte_Variable_3; 5: Temp_byte_Variable_2; 6: Temp_byte_Variable_1; 7: Temp_byte_Variable; default: K2Node_Select_Default_6}, ColorFXType=switch(Temp_int_Variable_11) {0: Temp_byte_Variable_15; 1: Temp_byte_Variable_14; 2: Temp_byte_Variable_13; 3: Temp_byte_Variable_12; 4: Temp_byte_Variable_11; 5: Temp_byte_Variable_10; 6: Temp_byte_Variable_9; 7: Temp_byte_Variable_8; default: K2Node_Select_Default_7}, DefaultLevel=switch(Temp_int_Variable_9) {0: Temp_real_Variable_7; 1: Temp_real_Variable_6; 2: Temp_real_Variable_5; 3: Temp_real_Variable_4; 4: Temp_real_Variable_3; 5: Temp_real_Variable_2; 6: Temp_real_Variable_1; 7: Temp_real_Variable; default: K2Node_Select_Default_5}, PadIndex=Temp_int_Variable_23 | as above |
| 41 | BeatLoopPad (pad 1) | PerformancePad | button | -28.9, 12.9, 1.6 | bone JPerfPad1 | BeatLoopLength=switch(Temp_int_Variable_17) {0: Temp_real_Variable_23; 1: Temp_real_Variable_22; 2: Temp_real_Variable_21; 3: Temp_real_Variable_20; 4: Temp_real_Variable_19; 5: Temp_real_Variable_18; 6: Temp_real_Variable_17; 7: Temp_real_Variable_16; default: K2Node_Select_Default_4}, PadIndex=Temp_int_Variable_21 | calls OwningPawn.Server_ExitLoopPrecise, Deck.ExitLoop, Deck.SetBeatLoop, OwningPawn.Server_SetLoopIn, OwningPawn.Server_SetLoopOut; follows Deck.OnActivePadModeChanged, Deck.OnBeatLoopSet, Deck.OnIsLoopingChanged |
| 42 | BeatLoopPad (pad 2) | PerformancePad | button | -25.5, 12.9, 1.6 | bone JPerfPad2 | BeatLoopLength=switch(Temp_int_Variable_17) {0: Temp_real_Variable_23; 1: Temp_real_Variable_22; 2: Temp_real_Variable_21; 3: Temp_real_Variable_20; 4: Temp_real_Variable_19; 5: Temp_real_Variable_18; 6: Temp_real_Variable_17; 7: Temp_real_Variable_16; default: K2Node_Select_Default_4}, PadIndex=Temp_int_Variable_21 | as above |
| 43 | BeatLoopPad (pad 3) | PerformancePad | button | -22.2, 12.9, 1.6 | bone JPerfPad3 | BeatLoopLength=switch(Temp_int_Variable_17) {0: Temp_real_Variable_23; 1: Temp_real_Variable_22; 2: Temp_real_Variable_21; 3: Temp_real_Variable_20; 4: Temp_real_Variable_19; 5: Temp_real_Variable_18; 6: Temp_real_Variable_17; 7: Temp_real_Variable_16; default: K2Node_Select_Default_4}, PadIndex=Temp_int_Variable_21 | as above |
| 44 | BeatLoopPad (pad 4) | PerformancePad | button | -18.8, 12.9, 1.6 | bone JPerfPad4 | BeatLoopLength=switch(Temp_int_Variable_17) {0: Temp_real_Variable_23; 1: Temp_real_Variable_22; 2: Temp_real_Variable_21; 3: Temp_real_Variable_20; 4: Temp_real_Variable_19; 5: Temp_real_Variable_18; 6: Temp_real_Variable_17; 7: Temp_real_Variable_16; default: K2Node_Select_Default_4}, PadIndex=Temp_int_Variable_21 | as above |
| 45 | BeatLoopPad (pad 5) | PerformancePad | button | -28.9, 16.3, 1.6 | bone JPerfPad5 | BeatLoopLength=switch(Temp_int_Variable_17) {0: Temp_real_Variable_23; 1: Temp_real_Variable_22; 2: Temp_real_Variable_21; 3: Temp_real_Variable_20; 4: Temp_real_Variable_19; 5: Temp_real_Variable_18; 6: Temp_real_Variable_17; 7: Temp_real_Variable_16; default: K2Node_Select_Default_4}, PadIndex=Temp_int_Variable_21 | as above |
| 46 | BeatLoopPad (pad 6) | PerformancePad | button | -25.5, 16.3, 1.6 | bone JPerfPad6 | BeatLoopLength=switch(Temp_int_Variable_17) {0: Temp_real_Variable_23; 1: Temp_real_Variable_22; 2: Temp_real_Variable_21; 3: Temp_real_Variable_20; 4: Temp_real_Variable_19; 5: Temp_real_Variable_18; 6: Temp_real_Variable_17; 7: Temp_real_Variable_16; default: K2Node_Select_Default_4}, PadIndex=Temp_int_Variable_21 | as above |
| 47 | BeatLoopPad (pad 7) | PerformancePad | button | -22.2, 16.3, 1.6 | bone JPerfPad7 | BeatLoopLength=switch(Temp_int_Variable_17) {0: Temp_real_Variable_23; 1: Temp_real_Variable_22; 2: Temp_real_Variable_21; 3: Temp_real_Variable_20; 4: Temp_real_Variable_19; 5: Temp_real_Variable_18; 6: Temp_real_Variable_17; 7: Temp_real_Variable_16; default: K2Node_Select_Default_4}, PadIndex=Temp_int_Variable_21 | as above |
| 48 | BeatLoopPad (pad 8) | PerformancePad | button | -18.8, 16.3, 1.6 | bone JPerfPad8 | BeatLoopLength=switch(Temp_int_Variable_17) {0: Temp_real_Variable_23; 1: Temp_real_Variable_22; 2: Temp_real_Variable_21; 3: Temp_real_Variable_20; 4: Temp_real_Variable_19; 5: Temp_real_Variable_18; 6: Temp_real_Variable_17; 7: Temp_real_Variable_16; default: K2Node_Select_Default_4}, PadIndex=Temp_int_Variable_21 | as above |
| 49 | KeyShiftPad (pad 1) | PerformancePad | button | -28.9, 12.9, 1.6 | bone JPerfPad1 | KeyShiftInterval=switch(Temp_int_Variable) {0: Temp_int_Variable_8; 1: Temp_int_Variable_7; 2: Temp_int_Variable_6; 3: Temp_int_Variable_5; 4: Temp_int_Variable_4; 5: Temp_int_Variable_3; 6: Temp_int_Variable_2; 7: Temp_int_Variable_1; default: K2Node_Select_Default_10}, PadIndex=Temp_int_Variable_25 | calls Deck.SetKeyShift; follows Deck.OnActivePadModeChanged, Deck.OnKeyShiftChanged |
| 50 | KeyShiftPad (pad 2) | PerformancePad | button | -25.5, 12.9, 1.6 | bone JPerfPad2 | KeyShiftInterval=switch(Temp_int_Variable) {0: Temp_int_Variable_8; 1: Temp_int_Variable_7; 2: Temp_int_Variable_6; 3: Temp_int_Variable_5; 4: Temp_int_Variable_4; 5: Temp_int_Variable_3; 6: Temp_int_Variable_2; 7: Temp_int_Variable_1; default: K2Node_Select_Default_10}, PadIndex=Temp_int_Variable_25 | as above |
| 51 | KeyShiftPad (pad 3) | PerformancePad | button | -22.2, 12.9, 1.6 | bone JPerfPad3 | KeyShiftInterval=switch(Temp_int_Variable) {0: Temp_int_Variable_8; 1: Temp_int_Variable_7; 2: Temp_int_Variable_6; 3: Temp_int_Variable_5; 4: Temp_int_Variable_4; 5: Temp_int_Variable_3; 6: Temp_int_Variable_2; 7: Temp_int_Variable_1; default: K2Node_Select_Default_10}, PadIndex=Temp_int_Variable_25 | as above |
| 52 | KeyShiftPad (pad 4) | PerformancePad | button | -18.8, 12.9, 1.6 | bone JPerfPad4 | KeyShiftInterval=switch(Temp_int_Variable) {0: Temp_int_Variable_8; 1: Temp_int_Variable_7; 2: Temp_int_Variable_6; 3: Temp_int_Variable_5; 4: Temp_int_Variable_4; 5: Temp_int_Variable_3; 6: Temp_int_Variable_2; 7: Temp_int_Variable_1; default: K2Node_Select_Default_10}, PadIndex=Temp_int_Variable_25 | as above |
| 53 | KeyShiftPad (pad 5) | PerformancePad | button | -28.9, 16.3, 1.6 | bone JPerfPad5 | KeyShiftInterval=switch(Temp_int_Variable) {0: Temp_int_Variable_8; 1: Temp_int_Variable_7; 2: Temp_int_Variable_6; 3: Temp_int_Variable_5; 4: Temp_int_Variable_4; 5: Temp_int_Variable_3; 6: Temp_int_Variable_2; 7: Temp_int_Variable_1; default: K2Node_Select_Default_10}, PadIndex=Temp_int_Variable_25 | as above |
| 54 | KeyShiftPad (pad 6) | PerformancePad | button | -25.5, 16.3, 1.6 | bone JPerfPad6 | KeyShiftInterval=switch(Temp_int_Variable) {0: Temp_int_Variable_8; 1: Temp_int_Variable_7; 2: Temp_int_Variable_6; 3: Temp_int_Variable_5; 4: Temp_int_Variable_4; 5: Temp_int_Variable_3; 6: Temp_int_Variable_2; 7: Temp_int_Variable_1; default: K2Node_Select_Default_10}, PadIndex=Temp_int_Variable_25 | as above |
| 55 | KeyShiftPad (pad 7) | PerformancePad | button | -22.2, 16.3, 1.6 | bone JPerfPad7 | KeyShiftInterval=switch(Temp_int_Variable) {0: Temp_int_Variable_8; 1: Temp_int_Variable_7; 2: Temp_int_Variable_6; 3: Temp_int_Variable_5; 4: Temp_int_Variable_4; 5: Temp_int_Variable_3; 6: Temp_int_Variable_2; 7: Temp_int_Variable_1; default: K2Node_Select_Default_10}, PadIndex=Temp_int_Variable_25 | as above |
| 56 | KeyShiftPad (pad 8) | PerformancePad | button | -18.8, 16.3, 1.6 | bone JPerfPad8 | KeyShiftInterval=switch(Temp_int_Variable) {0: Temp_int_Variable_8; 1: Temp_int_Variable_7; 2: Temp_int_Variable_6; 3: Temp_int_Variable_5; 4: Temp_int_Variable_4; 5: Temp_int_Variable_3; 6: Temp_int_Variable_2; 7: Temp_int_Variable_1; default: K2Node_Select_Default_10}, PadIndex=Temp_int_Variable_25 | as above |
| 57 | PitchSlider | {BPM} BPM / {Tempo} / {Key} / ({Master BPM} {Mast… | fader | -14.7, 11.7, 2.4 | bone JTempoSliderLeft | MaxOffset=4.5 | calls Console.Multi_SetSmartFaderPitchMod_Reliable, Label.HighlightOnHover, Tribe_Game_Instance_BP.ThirdPersonSpectatorActive, SpectatorLabel.HighlightOnHover, Console.Multi_SetSmartFaderPitchMod, Deck.FlushNetDormancy ...; follows Deck.OnConsoleRespawned, Deck.OnSyncStateChanged, Deck.OnTempoUnlocked |
| 58 | DeckQuantizeButton (ch 1) | Quantize | toggle button | -5.5, -36.6, 7.6 | marker Marker_DeckQuantizeButton1 | - | calls Deck.SetQuantized |
| 59 | DeckQuantizeButton (ch 2) | Quantize | toggle button | 5.9, -36.6, 7.6 | marker Marker_DeckQuantizeButton2 | - | as above |
| 60 | BeatgridEditButton (ch 1) | Edit Beatgrid | button | -2.5, -36.6, 7.7 | marker Marker_BeatgridEditButton1 | - | calls Deck.ToggleBeatgridEditor |
| 61 | BeatgridEditButton (ch 2) | Edit Beatgrid | button | 2.9, -36.6, 7.7 | marker Marker_BeatgridEditButton2 | - | as above |
| 62 | MasterTempoButton (ch 1) | Master Tempo | toggle button | -4.4, -36.6, 7.6 | marker Marker_MasterTempoButton1 | - | calls Deck.SetMasterTempo, KeySyncButton.SetButtonOn; follows Deck.OnKeySyncChanged |
| 63 | MasterTempoButton (ch 2) | Master Tempo | toggle button | 4.7, -36.6, 7.6 | marker Marker_MasterTempoButton2 | - | as above |
| 64 | JogWheel_FLX4 | JogWheel | jog wheel | -23.8, -3.2, 2.4 | bone JJogWheelOuterLeft | - | calls JogWheelFlashingRing.CreateDynamicMaterialInstance (in JogWheel_TribeCDJ) |
| 65 | WaveformSearch (ch 1) | NeedleSearch | fader | -0.1, -32.8, 6.3 | marker Marker_WaveformSearch1 | - | calls Console.AutoSwitchSyncMaster, Jogwheel.SetWaveformJogTouch, OwningPawn.Server_SetWaveformJogTouch, Jogwheel.SetWaveformTouchJogDelta |
| 66 | WaveformSearch (ch 2) | NeedleSearch | fader | -0.1, -28.0, 4.4 | marker Marker_WaveformSearch2 | - | as above |
| 67 | NeedleSearch (ch 1) | NeedleSearch | fader | -8.0, -37.8, 8.2 | marker Marker_NeedleSearch1 | - | calls Console.AutoSwitchSyncMaster, Deck.SetPositionFromFraction, Deck.RealignBeatSync |
| 68 | NeedleSearch (ch 2) | NeedleSearch | fader | 7.6, -37.8, 8.2 | marker Marker_NeedleSearch2 | - | as above |
| 69 | LoopInButton | Loop In/Cue | button | -33.1, -16.0, 1.8 | bone JLoopInLeft | - | calls Deck.SetLoopAdjustmentMode, Deck.SetLoopInPosition, OwningPawn.Server_SetLoopIn; follows Deck.OnIsLoopingChanged, Deck.OnLoopInSet |
| 70 | LoopOutButton | LoopOut | button | -29.2, -16.0, 1.8 | bone JLoopOutLeft | - | calls Deck.SetLoopOutPosition, OwningPawn.Server_SetLoopOut, Deck.SetLoopAdjustmentMode, OwningPawn.Server_SetLoopAdjustmentMode; follows Deck.OnIsLoopingChanged |
| 71 | FourBeatExitButton | 4 Beat Loop/Exit | button | -25.3, -16.0, 1.7 | bone JLoopExitLeft | - | calls Deck.ExitLoop, OwningPawn.Server_ExitLoopPrecise, OwningPawn.Server_SetLoopIn, OwningPawn.Server_SetLoopOut, Deck.SetBeatLoop; follows Deck.OnIsLoopingChanged |
| 72 | LoopCutButton | Loop Cutter | button | -21.5, -16.0, 1.7 | bone JCueLoop1Left | - | calls Deck.ClearMemoryCue, Deck.Multi_ClearMemoryCue, OwningPawn.Server_ClearMemoryCue, Deck.CutLoop, Deck.Multi_SeekToMemoryCue, OwningPawn.Server_SeekToMemoryCue |
| 73 | LoopExtendButton | Loop Extend | button | -18.3, -16.0, 1.7 | bone JCueLoop2Left | - | calls Deck.ExtendLoop, Deck.Multi_SeekToMemoryCue, OwningPawn.Server_SeekToMemoryCue, Deck.SetMemoryCue, Deck.Multi_SetMemoryCue, OwningPawn.Server_SetMemoryCue |
| 74 | SyncMasterComboButton | Sync | button | -14.6, -16.0, 1.9 | bone JBeatSync1 | - | calls OwningPawn.Server_SetSyncMaster, BP_Deck.CycleTempoRange, OwningPawn.Server_ToggleSync, Console.AutoSwitchSyncMaster, ChannelDevice.SetSyncMaster |
| 75 | CueButton | Cue | button | -33.1, 11.3, 1.8 | bone JCue1 | - | calls Deck.StopCuePreview, OwningPawn.Server_SeekToCue, PlayButton.Grab, PlayButton.Release, Deck.StartCuePreview, Deck.SetPlaybackMs ...; follows Deck.OnConsoleRespawned, Deck.OnCuePreviewCleared, Deck.OnDeckPause, Deck.OnDeckPlay ... |
| 76 | PlayButton | Play | button | -33.1, 15.5, 1.8 | bone JPlay1 | - | calls Deck.ClearCuePreview, OwningPawn.Server_StartPlay, Deck.Stop Play, OwningPawn.Server_StopPlay, Deck.Start Play; follows Deck.OnCuePreviewCleared, Deck.OnDeckPause, Deck.OnDeckPlay, Deck.OnTrackChanged ... |
| 77 | ShiftButton | Shift | button | 14.7, 7.2, 1.7 | bone JShift1 | - | calls Deck.SetShifted, OwningPawn.ToggleShiftEnabled, OwningPawn.Server_SetShiftEnabled |
| 78 | PerformancePadSelectButton | {Type} Mode | radio button | -28.9, 9.5, 1.6 | bone JPerfMode1 | PadMode=1, SecondaryPadMode=1 | calls Deck.SetActivePadButton; follows Deck.OnActivePadModeChanged |
| 79 | PerformancePadSelectButton | {Type} Mode | radio button | -25.6, 9.5, 1.6 | bone JPerfMode2 | PadMode=2, SecondaryPadMode=6 | calls Deck.SetActivePadButton; follows Deck.OnActivePadModeChanged |
| 80 | PerformancePadSelectButton | {Type} Mode | radio button | -22.2, 9.5, 1.6 | bone JPerfMode3 | PadMode=3, SecondaryPadMode=7 | calls Deck.SetActivePadButton; follows Deck.OnActivePadModeChanged |
| 81 | PerformancePadSelectButton | {Type} Mode | radio button | -18.8, 9.5, 1.6 | bone JPerfMode4 | PadMode=4, SecondaryPadMode=8 | calls Deck.SetActivePadButton; follows Deck.OnActivePadModeChanged |

## Starter CDJ

Model `BP_StarterCDJ_C` on `BP_Deck_C`. model id `StarterCDJ`. SKU `Equipment_StarterCDJ`. 33 cm wide. control table `DT_StarterCDJ_ControlInfo`. skeleton `SK_StarterCDJ_Skeleton`.

| # | Control | Label | Kind | x, y, z (cm) | Placed by | Settings | What it does |
|---|---|---|---|---|---|---|---|
| 1 | PitchSlider | {BPM} BPM / {Tempo} / {Key} / ({Master BPM} {Mast… | fader | 13.6, 20.7, 2.2 | bone Joint_Tempo_Slider | MaxOffset=3.7, BoneOriginCenterOffset=-3.7 | calls Console.Multi_SetSmartFaderPitchMod_Reliable, Label.HighlightOnHover, Tribe_Game_Instance_BP.ThirdPersonSpectatorActive, SpectatorLabel.HighlightOnHover, Console.Multi_SetSmartFaderPitchMod, Deck.FlushNetDormancy ...; follows Deck.OnConsoleRespawned, Deck.OnSyncStateChanged, Deck.OnTempoUnlocked |
| 2 | DeckQuantizeButton | Quantize | toggle button | -13.4, 13.1, 2.1 | marker Marker_DeckQuantize | - | calls Deck.SetQuantized |
| 3 | BeatgridEditButton | Edit Beatgrid | button | 12.6, -15.9, 4.0 | marker Marker_BeatgridEditButton | - | calls Deck.ToggleBeatgridEditor |
| 4 | JogWheel_StarterCDJ | JogWheel | jog wheel | 0.0, 6.2, 2.8 | bone Joint_Jogwheel_Outer | - | calls JogWheelFlashingRing.CreateDynamicMaterialInstance (in JogWheel_TribeCDJ) |
| 5 | NeedleSearch | NeedleSearch | fader | -0.2, -12.0, 2.6 | marker Marker_NeedleSearch | - | calls Console.AutoSwitchSyncMaster, Deck.SetPositionFromFraction, Deck.RealignBeatSync |
| 6 | BeatLoopFourButton | 4 Beat Loop/Loop Cutter | button | -13.9, -5.4, 2.0 | marker Marker_LoopIn | - | calls Deck.CutLoop, OwningPawn.Server_CutLoop, OwningPawn.Server_SetLoopIn, OwningPawn.Server_SetLoopOut, Deck.SetBeatLoop |
| 7 | BeatLoopEightButton | 8 Beat Loop/Loop Extend | button | -10.6, -5.4, 2.0 | marker Marker_LoopOut | - | calls Deck.ExtendLoop, OwningPawn.Server_ExtendLoop, OwningPawn.Server_SetLoopIn, OwningPawn.Server_SetLoopOut, Deck.SetBeatLoop |
| 8 | ReloopExitButton | Reloop/Exit | button | -7.4, -5.4, 2.0 | marker Marker_LoopExit | - | calls Deck.ReturnToLoop, Deck.ExitLoop; follows Deck.OnIsLoopingChanged |
| 9 | SyncMasterComboButton | Sync | button | 12.8, -5.4, 2.0 | marker Marker_BeatSync | - | calls OwningPawn.Server_SetSyncMaster, BP_Deck.CycleTempoRange, OwningPawn.Server_ToggleSync, Console.AutoSwitchSyncMaster, ChannelDevice.SetSyncMaster |
| 10 | CueButton | Cue | button | -13.4, 16.3, 2.0 | marker Marker_Cue | - | calls Deck.StopCuePreview, OwningPawn.Server_SeekToCue, PlayButton.Grab, PlayButton.Release, Deck.StartCuePreview, Deck.SetPlaybackMs ...; follows Deck.OnConsoleRespawned, Deck.OnCuePreviewCleared, Deck.OnDeckPause, Deck.OnDeckPlay ... |
| 11 | PlayButton | Play | button | -13.4, 20.8, 2.0 | marker Marker_Play | - | calls Deck.ClearCuePreview, OwningPawn.Server_StartPlay, Deck.Stop Play, OwningPawn.Server_StopPlay, Deck.Start Play; follows Deck.OnCuePreviewCleared, Deck.OnDeckPause, Deck.OnDeckPlay, Deck.OnTrackChanged ... |
| 12 | HotCuePad | PerformancePad | control | -6.0, 21.0, 2.1 | marker Marker_PerformancePad0 | - | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ... (in HotCueButton); follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 13 | HotCuePad | PerformancePad | control | -2.0, 21.0, 2.1 | marker Marker_PerformancePad1 | HotCueIndex=1 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ... (in HotCueButton); follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 14 | HotCuePad | PerformancePad | control | 2.0, 21.0, 2.1 | marker Marker_PerformancePad2 | HotCueIndex=2 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ... (in HotCueButton); follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 15 | HotCuePad | PerformancePad | control | 5.9, 21.0, 2.1 | marker Marker_PerformancePad3 | HotCueIndex=3 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ... (in HotCueButton); follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 16 | ShiftButton | Shift | button | -9.3, 21.0, 2.0 | marker Marker_ShiftButton | - | calls Deck.SetShifted, OwningPawn.ToggleShiftEnabled, OwningPawn.Server_SetShiftEnabled |

## Tribe CDJ

Model `BP_TribeCDJ_C` on `BP_Deck_C`. model id `TribeCDJ`. SKU `Equipment_TribeCDJ`. 32.5 cm wide. control table `DT_TribeCDJ_ControlInfo`. skeleton `TribeCDJ_Skeleton`.

| # | Control | Label | Kind | x, y, z (cm) | Placed by | Settings | What it does |
|---|---|---|---|---|---|---|---|
| 1 | PitchSlider | {BPM} BPM / {Tempo} / {Key} / ({Master BPM} {Mast… | fader | 13.7, 11.9, 4.0 | bone pitch_fader_bone | - | calls Console.Multi_SetSmartFaderPitchMod_Reliable, Label.HighlightOnHover, Tribe_Game_Instance_BP.ThirdPersonSpectatorActive, SpectatorLabel.HighlightOnHover, Console.Multi_SetSmartFaderPitchMod, Deck.FlushNetDormancy ...; follows Deck.OnConsoleRespawned, Deck.OnSyncStateChanged, Deck.OnTempoUnlocked |
| 2 | PlayDirectionButton | PlayDirection | toggle button | -14.3, 1.7, 2.1 | bone directon_switch_bone | - | calls Deck.SetReversePlayback; follows Deck.OnDeckDirectionChanged |
| 3 | DeckQuantizeButton | Quantize | toggle button | -9.2, -12.6, 3.4 | marker Marker_DeckQuantize | - | calls Deck.SetQuantized |
| 4 | TempoSliderRangeButton | Tempo Range Adjust | button | 13.8, 2.3, 3.5 | marker Marker_TempoRangeAdjust | - | calls Deck.CycleTempoRange, PitchSlider.FlushNetDormancy, PitchSlider.OnRep_MaxPitchModulation |
| 5 | TimeModeButton | Time Mode | toggle button | -9.1, -15.6, 4.2 | marker Marker_TimeMode | - | calls Deck.SetTimeMode |
| 6 | BeatgridEditButton | Edit Beatgrid | button | 6.3, -11.8, 3.2 | marker Marker_BeatgridEditButton | - | calls Deck.ToggleBeatgridEditor |
| 7 | JogWheel_TribeCDJ | JogWheel | jog wheel | 0.1, 5.8, 4.0 | bone outer_jog_wheel_bone | - | calls JogWheelFlashingRing.CreateDynamicMaterialInstance |
| 8 | JogAdjust | Jog Adjust | knob | 9.2, -2.8, 4.0 | bone jog_adjust_knob_bone | JogWheelToAffect=self.Jogwheel | generic behaviour of its kind |
| 9 | VinylModeToggle | Jog Mode | button | 14.6, -3.7, 3.5 | marker Marker_JogMode | JogModePanelTransform=CallFunc_MakeTransform_ReturnValue | calls Deck.SetJogMode; follows Deck.OnJogModeChanged |
| 10 | TrackSearchNextButton | Track Search Forward | button | -12.7, 5.6, 3.5 | marker Marker_TrackSearchNext | - | calls Deck.Multi_SetPositionFromFraction |
| 11 | TrackSearchPrevButton | Track Search Backward | button | -14.7, 5.6, 3.5 | marker Marker_TrackSearchPrev | - | calls Deck.Multi_SetPositionFromFraction |
| 12 | SearchButtonLeft | Search Backward | button | -14.8, 8.6, 3.5 | marker Marker_SearchRev | - | calls Deck.SetPlaybackMs, Deck.RealignBeatSync, Console.AutoSwitchSyncMaster (in SearchButtonRight) |
| 13 | SearchButtonRight | Search Forward | button | -12.8, 8.6, 3.5 | marker Marker_SearchFwd | - | calls Deck.SetPlaybackMs, Deck.RealignBeatSync, Console.AutoSwitchSyncMaster |
| 14 | NeedleSearch | NeedleSearch | fader | -0.0, -8.0, 3.1 | marker Marker_NeedleSearch | - | calls Console.AutoSwitchSyncMaster, Deck.SetPositionFromFraction, Deck.RealignBeatSync |
| 15 | LoopInButton | Loop In/Cue | button | -10.1, -5.7, 3.5 | marker Marker_LoopIn | - | calls Deck.SetLoopAdjustmentMode, Deck.SetLoopInPosition, OwningPawn.Server_SetLoopIn; follows Deck.OnIsLoopingChanged, Deck.OnLoopInSet |
| 16 | LoopOutButton | LoopOut | button | -7.5, -5.7, 3.5 | marker Marker_LoopOut | - | calls Deck.SetLoopOutPosition, OwningPawn.Server_SetLoopOut, Deck.SetLoopAdjustmentMode, OwningPawn.Server_SetLoopAdjustmentMode; follows Deck.OnIsLoopingChanged |
| 17 | ReloopExitButton | Reloop/Exit | button | -4.5, -5.6, 3.5 | marker Marker_LoopExit | - | calls Deck.ReturnToLoop, Deck.ExitLoop; follows Deck.OnIsLoopingChanged |
| 18 | LoopCutButton | Loop Cutter | button | 4.9, -5.6, 3.5 | marker Marker_LoopCut | - | calls Deck.ClearMemoryCue, Deck.Multi_ClearMemoryCue, OwningPawn.Server_ClearMemoryCue, Deck.CutLoop, Deck.Multi_SeekToMemoryCue, OwningPawn.Server_SeekToMemoryCue |
| 19 | LoopExtendButton | Loop Extend | button | 6.7, -5.6, 3.5 | marker Marker_LoopExtend | - | calls Deck.ExtendLoop, Deck.Multi_SeekToMemoryCue, OwningPawn.Server_SeekToMemoryCue, Deck.SetMemoryCue, Deck.Multi_SetMemoryCue, OwningPawn.Server_SetMemoryCue |
| 20 | HotCueRecCallToggle | HotCueMode | button | -13.7, -1.6, 3.5 | marker Marker_HotCueRecCall | - | calls Deck.SetHotCueMode |
| 21 | HotCueButton | Hot Cue {X} | button | -13.7, -9.3, 3.5 | marker Marker_HotCueA | HotCueIndex=0 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 22 | HotCueButton | Hot Cue {X} | button | -13.7, -6.8, 3.5 | marker Marker_HotCueB | HotCueIndex=1 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 23 | HotCueButton | Hot Cue {X} | button | -13.7, -4.3, 3.5 | marker Marker_HotCueC | HotCueIndex=2 | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged |
| 24 | TouchBrakeKnob | Vinyl Speed Adjust Touch/Brake | knob | 13.7, -7.7, 4.0 | bone touch_brake_knob_bone | DefaultRotationFraction=0 | calls Deck.SetTouchBrake |
| 25 | SyncButton | Sync | button | 12.7, -0.4, 3.5 | marker Marker_SyncSlave | - | calls ChannelDevice.End Sync, ChannelDevice.SetSyncMode, ChannelDevice.ToggleSync, SyncButtonInstanced.SetHiddenInGame, OwningPawn.Server_ToggleSync, ChannelDevice.StartSync ...; follows ChannelDevice.OnConsoleRespawned, ChannelDevice.OnSyncStateChanged |
| 26 | SyncMasterButton | Sync Master | button | 14.8, -0.4, 3.5 | marker Marker_SyncMaster | - | calls ChannelDevice.ToggleSyncMaster, SyncButtonInstanced.SetHiddenInGame, ChannelDevice.SetSyncMaster, SyncButtonInstanced.SetStaticMesh; follows ChannelDevice.OnConsoleRespawned |
| 27 | CueButton | Cue | button | -13.8, 12.7, 3.5 | marker Marker_Cue | - | calls Deck.StopCuePreview, OwningPawn.Server_SeekToCue, PlayButton.Grab, PlayButton.Release, Deck.StartCuePreview, Deck.SetPlaybackMs ...; follows Deck.OnConsoleRespawned, Deck.OnCuePreviewCleared, Deck.OnDeckPause, Deck.OnDeckPlay ... |
| 28 | PlayButton | Play | button | -13.8, 17.3, 3.5 | marker Marker_Play | - | calls Deck.ClearCuePreview, OwningPawn.Server_StartPlay, Deck.Stop Play, OwningPawn.Server_StopPlay, Deck.Start Play; follows Deck.OnCuePreviewCleared, Deck.OnDeckPause, Deck.OnDeckPlay, Deck.OnTrackChanged ... |
| 29 | MasterTempoButton | Master Tempo | toggle button | 13.8, 4.4, 3.5 | marker Marker_MasterTempo | - | calls Deck.SetMasterTempo, KeySyncButton.SetButtonOn; follows Deck.OnKeySyncChanged |
| 30 | SlipButton | Slip | toggle button | -10.2, -1.2, 3.5 | marker Marker_Slip | - | calls Deck.SetSlip; follows AudioPlayer.OnSlipConditionChanged, Deck.OnSlipModeChanged |

## VinylDeck

Model `BP_TribeVinylDeck_C` on `BP_VinylDeck_C`. model id `TribeVinylDeck`. SKU `Equipment_VinylDeck`. 39 cm wide. control table `DT_TribeVinylDeck_ControlInfo`. skeleton `SK_VinylDeck_Skeleton`.

| # | Control | Label | Kind | x, y, z (cm) | Placed by | Settings | What it does |
|---|---|---|---|---|---|---|---|
| 1 | VinylPitchSlider | {BPM} BPM / {Tempo} / {Key} / ({Master BPM} {Mast… | fader | 19.7, 6.9, 8.2 | bone TempoSlider | - | calls VinylDeck.SetAutoSpinRate |
| 2 | VinylStartStopButton | Start/Stop | button | -19.8, 14.9, 8.5 | marker Marker_StartStopButton | VinylDeck=self | calls BP_Vinyl_Wheel.SetVinylInterpTime, VinylDeck.ToggleVinylDeckSpinning |
| 3 | TempoResetButton | Tempo Reset | toggle button | 15.9, 10.8, 8.6 | marker Marker_PitchReset | - | calls Deck.SetTempoLocked, TempoResetPanel.CreateDynamicMaterialInstance, TempoResetPanel.SetVisibility |
| 4 | VinylPowerButton | Power Knob | stepped knob | -20.0, 10.4, 10.2 | bone PowerKnob | VinylDeck=self | calls VinylDeck.SetDeckOn, VinylDeck.ToggleVinylDeckSpinning |
| 5 | VinylWheel | JogWheel | jog wheel | -4.7, -0.1, 9.5 | bone Platter | - | calls AudioPlayer.SetScratchEndMode, AudioPlayer.AutoJogBegin, Deck.JogTick, AudioPlayer.JogEnd; follows Deck.OnDeckPlay, Deck.OnStreamTrackBeginDownload, Deck.OnTrackChanged, Deck.OnTrackUnloaded |

## DJM-A9

Model `BP_DJM_A9_C` on `BP_Console_C`. model id `DJM-A9`. SKU `Equipment_A9`. 38 cm wide. control table `DT_DJM-A9_ControlInfo`. skeleton `SK_DJM-A9_Mixer_Skeleton`.

| # | Control | Label | Kind | x, y, z (cm) | Placed by | Settings | What it does |
|---|---|---|---|---|---|---|---|
| 1 | ChannelTrimKnob (ch 1) | Trim {Ch} | knob | -8.6, -15.4, 4.9 | bone jnt_ch1_trim | - | calls Mixer.SetChannelTrim; follows Video Call Manager.OnAudioOutputTypeChanged, Video Call Manager.OnCallEndedDelegate, Video Call Manager.OnVideoCallStartSuccessDelegate |
| 2 | ChannelTrimKnob (ch 2) | Trim {Ch} | knob | -4.0, -15.4, 4.9 | bone jnt_ch2_trim | - | as above |
| 3 | ChannelTrimKnob (ch 3) | Trim {Ch} | knob | 0.6, -15.4, 4.9 | bone jnt_ch3_trim | - | as above |
| 4 | ChannelTrimKnob (ch 4) | Trim {Ch} | knob | 5.2, -15.4, 4.9 | bone jnt_ch4_trim | - | as above |
| 5 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -8.6, -12.2, 4.9 | bone jnt_ch1_eq_hi | EQBand=4 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 6 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -4.0, -12.2, 4.9 | bone jnt_ch2_eq_hi | EQBand=4 | as above |
| 7 | ChannelEQKnob (ch 3) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 0.6, -12.2, 4.9 | bone jnt_ch3_eq_hi | EQBand=4 | as above |
| 8 | ChannelEQKnob (ch 4) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 5.2, -12.2, 4.9 | bone jnt_ch4_eq_hi | EQBand=4 | as above |
| 9 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -8.6, -8.8, 4.9 | bone jnt_ch1_eq_mid | EQBand=2 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 10 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -4.0, -8.8, 4.9 | bone jnt_ch2_eq_mid | EQBand=2 | as above |
| 11 | ChannelEQKnob (ch 3) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 0.6, -8.8, 4.9 | bone jnt_ch3_eq_mid | EQBand=2 | as above |
| 12 | ChannelEQKnob (ch 4) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 5.2, -8.8, 4.9 | bone jnt_ch4_eq_mid | EQBand=2 | as above |
| 13 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -8.6, -5.3, 4.9 | bone jnt_ch1_eq_low | EQBand=0 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 14 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -4.0, -5.3, 4.9 | bone jnt_ch2_eq_low | EQBand=0 | as above |
| 15 | ChannelEQKnob (ch 3) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 0.6, -5.3, 4.9 | bone jnt_ch3_eq_low | EQBand=0 | as above |
| 16 | ChannelEQKnob (ch 4) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 5.2, -5.3, 4.9 | bone jnt_ch4_eq_low | EQBand=0 | as above |
| 17 | ChannelColorKnob (ch 1) | Color FX Level {Ch} | knob | -8.6, -0.6, 4.8 | bone jnt_ch1_color_fx | - | calls Mixer.SetChannelColor; follows Console.OnColorFXCenterLockToggled |
| 18 | ChannelColorKnob (ch 2) | Color FX Level {Ch} | knob | -4.0, -0.6, 4.8 | bone jnt_ch2_color_fx | - | as above |
| 19 | ChannelColorKnob (ch 3) | Color FX Level {Ch} | knob | 0.6, -0.6, 4.8 | bone jnt_ch3_color_fx | - | as above |
| 20 | ChannelColorKnob (ch 4) | Color FX Level {Ch} | knob | 5.2, -0.6, 4.8 | bone jnt_ch4_color_fx | - | as above |
| 21 | ChannelCueButton (ch 1) | Channel {Ch} Cue | toggle button | -9.4, 3.2, 4.3 | marker Marker_CueChannel_1 | - | calls Console.SetChannelCue |
| 22 | ChannelCueButton (ch 2) | Channel {Ch} Cue | toggle button | -4.9, 3.2, 4.3 | marker Marker_CueChannel_2 | - | as above |
| 23 | ChannelCueButton (ch 3) | Channel {Ch} Cue | toggle button | -0.3, 3.2, 4.3 | marker Marker_CueChannel_3 | - | as above |
| 24 | ChannelCueButton (ch 4) | Channel {Ch} Cue | toggle button | 4.3, 3.2, 4.3 | marker Marker_CueChannel_4 | - | as above |
| 25 | ChannelVolumeSlider (ch 1) | Volume Fader {Ch} | fader | -8.6, 10.3, 4.9 | bone jnt_ch1_fader | MaxOffset=2.35 | calls Rig.broadcast OnControlReset, Console.SetChannelFader |
| 26 | ChannelVolumeSlider (ch 2) | Volume Fader {Ch} | fader | -4.0, 10.3, 4.9 | bone jnt_ch2_fader | MaxOffset=2.35 | as above |
| 27 | ChannelVolumeSlider (ch 3) | Volume Fader {Ch} | fader | 0.6, 10.3, 4.9 | bone jnt_ch3_fader | MaxOffset=2.35 | as above |
| 28 | ChannelVolumeSlider (ch 4) | Volume Fader {Ch} | fader | 5.2, 10.3, 4.9 | bone jnt_ch4_fader | MaxOffset=2.35 | as above |
| 29 | VUMeter (ch 1) | - | control | -10.7, -11.1, 4.1 | marker Marker_VUMeterChannel_1 | VUStaticMesh=SM_VUMeter | - |
| 30 | VUMeter (ch 2) | - | control | -6.1, -11.1, 4.1 | marker Marker_VUMeterChannel_2 | VUStaticMesh=SM_VUMeter | as above |
| 31 | VUMeter (ch 3) | - | control | -1.4, -11.1, 4.1 | marker Marker_VUMeterChannel_3 | VUStaticMesh=SM_VUMeter | as above |
| 32 | VUMeter (ch 4) | - | control | 3.2, -11.1, 4.1 | marker Marker_VUMeterChannel_4 | VUStaticMesh=SM_VUMeter | as above |
| 33 | CrossfaderAssign (ch 1) | Crossfader Assign {Ch} | stepped slider | -8.6, 15.7, 4.1 | bone jnt_ch1_xf_assign | DefaultFractionIndex=switch(Temp_int_Variable_2) {0: Temp_int_Variable; 1: Temp_int_Variable_1; 2: Temp_int_Variable_4; 3: Temp_int_Variable_5; default: K2Node_Select_Default_1} | calls Console.SetCrossfaderAssign |
| 34 | CrossfaderAssign (ch 2) | Crossfader Assign {Ch} | stepped slider | -4.0, 15.7, 4.1 | bone jnt_ch2_xf_assign | DefaultFractionIndex=switch(Temp_int_Variable_2) {0: Temp_int_Variable; 1: Temp_int_Variable_1; 2: Temp_int_Variable_4; 3: Temp_int_Variable_5; default: K2Node_Select_Default_1} | as above |
| 35 | CrossfaderAssign (ch 3) | Crossfader Assign {Ch} | stepped slider | 0.6, 15.7, 4.1 | bone jnt_ch3_xf_assign | DefaultFractionIndex=switch(Temp_int_Variable_2) {0: Temp_int_Variable; 1: Temp_int_Variable_1; 2: Temp_int_Variable_4; 3: Temp_int_Variable_5; default: K2Node_Select_Default_1} | as above |
| 36 | CrossfaderAssign (ch 4) | Crossfader Assign {Ch} | stepped slider | 5.2, 15.7, 4.1 | bone jnt_ch4_xf_assign | DefaultFractionIndex=switch(Temp_int_Variable_2) {0: Temp_int_Variable; 1: Temp_int_Variable_1; 2: Temp_int_Variable_4; 3: Temp_int_Variable_5; default: K2Node_Select_Default_1} | as above |
| 37 | MasterLevelKnob | Master Level | knob | 10.3, -19.2, 4.7 | bone jnt_master_level | - | calls Mixer.SetMasterLevel; follows Video Call Manager.OnAudioOutputTypeChanged, Video Call Manager.OnCallEndedDelegate, Video Call Manager.OnVideoCallStartSuccessDelegate |
| 38 | MasterCueButton | Master Cue | toggle button | 9.3, 3.2, 4.2 | marker Marker_MasterCue | - | calls Mixer.SetMasterCue |
| 39 | VUMeter | - | control | 9.1, -11.1, 4.0 | marker Marker_MasterVUMeter_L | VUStaticMesh=SM_VUMeter | - |
| 40 | VUMeter | - | control | 11.5, -11.1, 4.0 | marker Marker_MasterVUMeter_R | VUStaticMesh=SM_VUMeter | - |
| 41 | BeatFXBeatPreviousButton | Beat FX Previous | button | 15.2, -3.6, 4.3 | marker Marker_BeatFX_ArrowLeft | - | calls Console.SetBeatFxAutoBpm, Console.SetPreviousBeatFXTimeInterval |
| 42 | BeatFXBeatNextButton | Beat FX Next | button | 18.9, -3.6, 4.3 | marker Marker_BeatFX_ArrowRight | - | calls Console.ResetTapBpmQueue, OwningPawn.Server_SetBeatFXBpm, Console.OnTapButtonPressed, Console.SetNextBeatFXTimeInterval |
| 43 | BeatFXTypeKnob_A9 | Mobius/Triplet Roll/Roll/Trans/Triplet Filter/Fil… | stepped knob | 17.0, 3.5, 5.1 | bone jnt_fx_select | - | calls Label.UpdateLabelText, Console.SetBeatFxType (in BeatFXTypeKnob) |
| 44 | BeatFXChannelButton | Beat FX Channel {Channel}  | radio button | 14.4, 6.6, 4.2 | marker Marker_BeatFXChannelSelect1 | - | calls Console.SetBeatFXChannel; follows Console.OnBeatFxChannelChanged |
| 45 | BeatFXChannelButton | Beat FX Channel {Channel}  | radio button | 16.1, 6.6, 4.2 | marker Marker_BeatFXChannelSelect2 | BeatFXChannel=1 | calls Console.SetBeatFXChannel; follows Console.OnBeatFxChannelChanged |
| 46 | BeatFXChannelButton | Beat FX Channel {Channel}  | radio button | 17.8, 6.6, 4.2 | marker Marker_BeatFXChannelSelect3 | BeatFXChannel=2 | calls Console.SetBeatFXChannel; follows Console.OnBeatFxChannelChanged |
| 47 | BeatFXChannelButton | Beat FX Channel {Channel}  | radio button | 19.6, 6.6, 4.2 | marker Marker_BeatFXChannelSelect4 | BeatFXChannel=3 | calls Console.SetBeatFXChannel; follows Console.OnBeatFxChannelChanged |
| 48 | BeatFXChannelButton | Beat FX Channel {Channel}  | radio button | 16.2, 8.6, 4.2 | marker Marker_BeatFXChannelSelectCFA | BeatFXChannel=9 | calls Console.SetBeatFXChannel; follows Console.OnBeatFxChannelChanged |
| 49 | BeatFXChannelButton | Beat FX Channel {Channel}  | radio button | 17.8, 8.6, 4.2 | marker Marker_BeatFXChannelSelectCFB | BeatFXChannel=10 | calls Console.SetBeatFXChannel; follows Console.OnBeatFxChannelChanged |
| 50 | BeatFXChannelButton | Beat FX Channel {Channel}  | radio button | 14.4, 8.6, 4.2 | marker Marker_BeatFXChannelSelectMic | BeatFXChannel=16 | calls Console.SetBeatFXChannel; follows Console.OnBeatFxChannelChanged |
| 51 | BeatFXChannelButton | Beat FX Channel {Channel}  | radio button | 19.5, 8.6, 4.2 | marker Marker_BeatFXChannelSelectMaster | BeatFXChannel=17 | calls Console.SetBeatFXChannel; follows Console.OnBeatFxChannelChanged |
| 52 | BeatFXTimeKnob | Beat FX Time | knob | 17.0, 11.6, 4.9 | bone jnt_fx_time | - | calls Console.AddBeatFXTime, Console.SetBeatFXTimeInterval, Console.Multi_SetBeatFxBpm, Console.SetBeatFxTime |
| 53 | BeatFXLevelDepthKnob | Beat FX Level/Depth | knob | 17.0, 15.2, 5.0 | bone jnt_fx_level | - | calls Console.SetBeatFXLevel |
| 54 | BeatFXToggleButton | Beat FX On/Off | toggle button | 17.0, 19.1, 4.3 | marker Marker_BeatFX_ToggleButton | - | calls Console.SetBeatFXToggleIntent, MidiManager.SendMidiEvent |
| 55 | BeatFXQuantizeButton | Beat FX Quantize | toggle button | 19.0, -1.5, 4.2 | marker Marker_BeatFX_QuantizeButton | - | calls Console.SetBeatFXQuantize |
| 56 | BeatFXTapButton | Beat FX Tap Tempo | button | 17.0, -1.8, 4.3 | marker Marker_BeatFxTapButton | - | calls Console.ResetTapBpmQueue, OwningPawn.Server_SetBeatFXBpm, Console.OnTapButtonPressed, Console.SetTapButtonHeld |
| 57 | BeatFXAutoTapButton | Beat FX Auto/Tap Tempo | toggle button | 14.9, -1.5, 4.3 | marker Marker_BeatFXAutoTap | - | calls Console.SetBeatFxAutoBpm; follows Console.OnBeatFxBpmModeChanged |
| 58 | BeatFXEqButton | Beat FX EQ {X} (High/Mid/Low) | toggle button | 14.9, 0.8, 4.2 | marker Marker_BeatFxEqLow | EQBand=0 | calls Console.SetBeatFxEq |
| 59 | BeatFXEqButton | Beat FX EQ {X} (High/Mid/Low) | toggle button | 17.0, 0.8, 4.2 | marker Marker_BeatFxEqMid | EQBand=1 | calls Console.SetBeatFxEq |
| 60 | BeatFXEqButton | Beat FX EQ {X} (High/Mid/Low) | toggle button | 19.0, 0.8, 4.2 | marker Marker_BeatFxEqHigh | EQBand=2 | calls Console.SetBeatFxEq |
| 61 | BeatFxXpadSliderA9 | Xpad | fader | 16.9, -6.0, 4.0 | marker Marker_XpadSlider | - | calls Console.SetBeatFxTouchIntent, Console.SetBeatFxXpadEnabled, Console.SetBeatFxParameter; follows Console.OnActiveBeatFxChanged |
| 62 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -12.7, -1.7, 4.2 | marker Marker_ColorFX_DubEcho | FXType=2 | calls Console.SetActiveFXButton, Console.DisableFX |
| 63 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -14.9, 2.6, 4.2 | marker Marker_ColorFX_Noise | FXType=4 | calls Console.SetActiveFXButton, Console.DisableFX |
| 64 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -12.6, 2.6, 4.2 | marker Marker_ColorFX_Filter | FXType=6 | calls Console.SetActiveFXButton, Console.DisableFX |
| 65 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -14.9, 0.5, 4.2 | marker Marker_ColorFX_Crush | FXType=5 | calls Console.SetActiveFXButton, Console.DisableFX |
| 66 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -15.0, -1.7, 4.2 | marker Marker_ColorFX_Space | FXType=1 | calls Console.SetActiveFXButton, Console.DisableFX |
| 67 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -12.8, 0.5, 4.2 | marker Marker_ColorFX_Sweep | FXType=3 | calls Console.SetActiveFXButton, Console.DisableFX |
| 68 | ColorFXParameterKnob | Color FX Parameter | knob | -13.8, 5.6, 4.9 | bone jnt_color_fx_param | - | calls Console.SetColorFxParameter |
| 69 | ColorFXCenterLockSwitch | Color FX Center Lock | stepped slider | -13.6, -3.8, 4.1 | bone jnt_center_lock | MaxOffset=0.17, BoneOriginCenterOffset=-0.12 | calls Console.SetColorFXCenterLockEnabled |
| 70 | HeadphoneMixKnob | Headphone Mix | knob | -13.8, 11.8, 4.9 | bone jnt_hp_a_mix | - | calls Mixer.SetHeadphonesMix |
| 71 | HeadphoneLevelKnob | Headphone Level | knob | -13.8, 14.8, 4.9 | bone jnt_hp_a_level | - | calls Mixer.SetHeadphonesLevel |
| 72 | HeadphoneIndicator | - | control | -13.9, 19.2, 4.1 | marker Marker_Headphones_Indicator | - | - |
| 73 | Crossfader | Crossfader | fader | -1.7, 19.7, 4.9 | bone jnt_crossfader | MaxOffset=2.35 | calls Console.Set Crossfader |
| 74 | CrossfaderCurveSwitch | Crossfader Curve | stepped slider | 10.3, 18.6, 4.1 | bone jnt_xf_curve | - | calls Console.SetCrossfaderCurve |
| 75 | ChannelFaderCurveSwitch | Channel Fader Curve | stepped slider | 10.3, 16.5, 4.1 | bone jnt_ch_fader_curve | - | calls Console.SetChannelFaderCurve |
| 76 | EqCurveSwitch | EQ Curve | stepped slider | 10.5, 14.3, 4.1 | bone jnt_eq_curve | - | calls Console.SetEqCurve |
| 77 | MicLevelKnob | Microphone Level | knob | -18.9, -15.0, 4.9 | bone jnt_mic1_level | - | calls Console.SetMicLevel |
| 78 | MicTalkoverButton | Microphone Talkover | toggle button | -18.9, -4.2, 4.2 | marker Marker_MicTalkoverButton | - | calls Console.SetMicTalkoverEnabled |
| 79 | MicEQKnob | Microphone EQ {X} | knob | -18.9, -7.0, 4.9 | bone jnt_mic_eq_low | Band=0 | calls Console.SetMicEQ |
| 80 | MicEQKnob | Microphone EQ {X} | knob | -18.9, -9.6, 4.9 | bone jnt_mic_eq_high | Band=2 | calls Console.SetMicEQ |
| 81 | MicFXButton | Mic FX {FX} | toggle button | -18.9, -1.7, 4.2 | marker Marker_MicFXEcho | BeatFXType=2 | calls Console.SetActiveMicFX; follows Console.OnMicFxChanged |
| 82 | MicFXButton | Mic FX {FX} | toggle button | -18.9, 0.5, 4.2 | marker Marker_MicFXPitch | BeatFXType=10 | calls Console.SetActiveMicFX; follows Console.OnMicFxChanged |
| 83 | MicFXButton | Mic FX {FX} | toggle button | -18.9, 2.6, 4.2 | marker Marker_MicFXMegaPhone | BeatFXType=19 | calls Console.SetActiveMicFX; follows Console.OnMicFxChanged |
| 84 | MicFXParameterKnob | Mic FX Parameter | knob | -18.9, 5.6, 4.9 | bone jnt_mic_fx_param | - | calls Mixer.SetMicFxParameter |
| 85 | MicReverbButton | Mic Reverb | toggle button | -18.9, 9.2, 4.2 | marker Marker_MicReverb | - | calls Mixer.SetMicReverbEnabled |
| 86 | MicReverbParameterKnob | Mic Reverb Parameter | knob | -18.9, 11.8, 4.9 | bone jnt_mic_reverb_param | - | calls Mixer.SetMicReverbParameter |
| 87 | MicOnButton | Microphone On/Off | toggle button | -18.9, 17.9, 4.1 | marker Marker_MicOnButton | - | calls Console.SetMicMode |

## DJM-900NXS2

Model `BP_DJM_Nexus_2_C` on `BP_Console_C`. model id `DJM-NXS-2`. SKU `Equipment_DJM_Nexus_2`. 33 cm wide. control table `DT_DJM-NXS-2_ControlInfo`. skeleton `SK_DJM-NXS-2_Mixer_Skeleton`.

| # | Control | Label | Kind | x, y, z (cm) | Placed by | Settings | What it does |
|---|---|---|---|---|---|---|---|
| 1 | ChannelTrimKnob (ch 1) | Trim {Ch} | knob | -8.5, -13.5, 5.1 | bone Chan_1_Trim_Jnt | BoneKnobCenterYawOffset=150 | calls Mixer.SetChannelTrim; follows Video Call Manager.OnAudioOutputTypeChanged, Video Call Manager.OnCallEndedDelegate, Video Call Manager.OnVideoCallStartSuccessDelegate |
| 2 | ChannelTrimKnob (ch 2) | Trim {Ch} | knob | -4.1, -13.5, 5.1 | bone Chan_2_Trim_Jnt | BoneKnobCenterYawOffset=150 | as above |
| 3 | ChannelTrimKnob (ch 3) | Trim {Ch} | knob | 0.1, -13.5, 5.1 | bone Chan_3_Trim_Jnt | BoneKnobCenterYawOffset=150 | as above |
| 4 | ChannelTrimKnob (ch 4) | Trim {Ch} | knob | 4.4, -13.5, 5.1 | bone Chan_4_Trim_Jnt | BoneKnobCenterYawOffset=150 | as above |
| 5 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -8.5, -10.6, 5.2 | bone Chan_1_EQ_Hi_Jnt | EQBand=4 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 6 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -4.1, -10.6, 5.2 | bone Chan_2_EQ_Hi_Jnt | EQBand=4 | as above |
| 7 | ChannelEQKnob (ch 3) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 0.1, -10.6, 5.2 | bone Chan_3_EQ_Hi_Jnt | EQBand=4 | as above |
| 8 | ChannelEQKnob (ch 4) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 4.4, -10.6, 5.2 | bone Chan_4_EQ_Hi_Jnt | EQBand=4 | as above |
| 9 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -8.5, -7.5, 5.2 | bone Chan_1_EQ_Mid_Jnt | EQBand=2 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 10 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -4.1, -7.5, 5.2 | bone Chan_2_EQ_Mid_Jnt | EQBand=2 | as above |
| 11 | ChannelEQKnob (ch 3) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 0.1, -7.5, 5.2 | bone Chan_3_EQ_Mid_Jnt | EQBand=2 | as above |
| 12 | ChannelEQKnob (ch 4) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 4.4, -7.5, 5.2 | bone Chan_4_EQ_Mid_Jnt | EQBand=2 | as above |
| 13 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -8.5, -4.5, 5.2 | bone Chan_1_EQ_Low_Jnt | EQBand=0 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 14 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -4.1, -4.5, 5.2 | bone Chan_2_EQ_Low_Jnt | EQBand=0 | as above |
| 15 | ChannelEQKnob (ch 3) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 0.1, -4.5, 5.2 | bone Chan_3_EQ_Low_Jnt | EQBand=0 | as above |
| 16 | ChannelEQKnob (ch 4) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 4.4, -4.5, 5.2 | bone Chan_4_EQ_Low_Jnt | EQBand=0 | as above |
| 17 | ChannelColorKnob (ch 1) | Color FX Level {Ch} | knob | -8.5, -0.7, 5.1 | bone Chan_1_Color_FX_Jnt | - | calls Mixer.SetChannelColor; follows Console.OnColorFXCenterLockToggled |
| 18 | ChannelColorKnob (ch 2) | Color FX Level {Ch} | knob | -4.2, -0.7, 5.1 | bone Chan_2_Color_FX_Jnt | - | as above |
| 19 | ChannelColorKnob (ch 3) | Color FX Level {Ch} | knob | 0.1, -0.7, 5.1 | bone Chan_3_Color_FX_Jnt | - | as above |
| 20 | ChannelColorKnob (ch 4) | Color FX Level {Ch} | knob | 4.4, -0.7, 5.1 | bone Chan_4_Color_FX_Jnt | - | as above |
| 21 | ChannelCueButton (ch 1) | Channel {Ch} Cue | toggle button | -8.5, 1.9, 4.3 | marker Marker_CueChannel_1 | - | calls Console.SetChannelCue |
| 22 | ChannelCueButton (ch 2) | Channel {Ch} Cue | toggle button | -4.1, 1.9, 4.3 | marker Marker_CueChannel_2 | - | as above |
| 23 | ChannelCueButton (ch 3) | Channel {Ch} Cue | toggle button | 0.1, 1.9, 4.3 | marker Marker_CueChannel_3 | - | as above |
| 24 | ChannelCueButton (ch 4) | Channel {Ch} Cue | toggle button | 4.4, 1.9, 4.3 | marker Marker_CueChannel_4 | - | as above |
| 25 | ChannelVolumeSlider (ch 1) | Volume Fader {Ch} | fader | -8.5, 10.9, 5.0 | bone Volume_1_Jnt | BoneOriginCenterOffset=2.35 | calls Rig.broadcast OnControlReset, Console.SetChannelFader |
| 26 | ChannelVolumeSlider (ch 2) | Volume Fader {Ch} | fader | -4.2, 10.9, 5.0 | bone Volume_2_Jnt | BoneOriginCenterOffset=2.35 | as above |
| 27 | ChannelVolumeSlider (ch 3) | Volume Fader {Ch} | fader | 0.1, 10.9, 5.0 | bone Volume_3_Jnt | BoneOriginCenterOffset=2.35 | as above |
| 28 | ChannelVolumeSlider (ch 4) | Volume Fader {Ch} | fader | 4.4, 10.9, 5.0 | bone Volume_4_Jnt | BoneOriginCenterOffset=2.35 | as above |
| 29 | VUMeter (ch 1) | - | control | -10.3, -8.8, 4.1 | marker Marker_VUMeterChannel_1 | VUStaticMesh=SM_VUMeter | - |
| 30 | VUMeter (ch 2) | - | control | -6.0, -8.8, 4.1 | marker Marker_VUMeterChannel_2 | VUStaticMesh=SM_VUMeter | as above |
| 31 | VUMeter (ch 3) | - | control | -1.7, -8.8, 4.1 | marker Marker_VUMeterChannel_3 | VUStaticMesh=SM_VUMeter | as above |
| 32 | VUMeter (ch 4) | - | control | 2.5, -8.8, 4.1 | marker Marker_VUMeterChannel_4 | VUStaticMesh=SM_VUMeter | as above |
| 33 | CrossfaderAssign (ch 1) | Crossfader Assign {Ch} | stepped slider | -8.5, 13.8, 4.1 | bone Chan_1_Assign_Jnt | DefaultFractionIndex=switch(Temp_int_Variable_2) {0: Temp_int_Variable; 1: Temp_int_Variable_1; 2: Temp_int_Variable_4; 3: Temp_int_Variable_5; default: K2Node_Select_Default_1} | calls Console.SetCrossfaderAssign |
| 34 | CrossfaderAssign (ch 2) | Crossfader Assign {Ch} | stepped slider | -4.2, 13.8, 4.1 | bone Chan_2_Assign_Jnt | DefaultFractionIndex=switch(Temp_int_Variable_2) {0: Temp_int_Variable; 1: Temp_int_Variable_1; 2: Temp_int_Variable_4; 3: Temp_int_Variable_5; default: K2Node_Select_Default_1} | as above |
| 35 | CrossfaderAssign (ch 3) | Crossfader Assign {Ch} | stepped slider | 0.1, 13.8, 4.1 | bone Chan_3_Assign_Jnt | DefaultFractionIndex=switch(Temp_int_Variable_2) {0: Temp_int_Variable; 1: Temp_int_Variable_1; 2: Temp_int_Variable_4; 3: Temp_int_Variable_5; default: K2Node_Select_Default_1} | as above |
| 36 | CrossfaderAssign (ch 4) | Crossfader Assign {Ch} | stepped slider | 4.4, 13.8, 4.1 | bone Chan_4_Assign_Jnt | DefaultFractionIndex=switch(Temp_int_Variable_2) {0: Temp_int_Variable; 1: Temp_int_Variable_1; 2: Temp_int_Variable_4; 3: Temp_int_Variable_5; default: K2Node_Select_Default_1} | as above |
| 37 | MasterLevelKnob | Master Level | knob | 8.4, -16.4, 5.1 | bone Master_Volume_Jnt | BoneKnobCenterYawOffset=147 | calls Mixer.SetMasterLevel; follows Video Call Manager.OnAudioOutputTypeChanged, Video Call Manager.OnCallEndedDelegate, Video Call Manager.OnVideoCallStartSuccessDelegate |
| 38 | MasterBalanceKnob | Master Balance | knob | 8.4, -0.6, 4.8 | bone Master_Balance_Jnt | - | calls Mixer.SetMasterBalance |
| 39 | MasterCueButton | Master Cue | toggle button | 8.4, 1.9, 4.2 | marker Marker_MasterCue | - | calls Mixer.SetMasterCue |
| 40 | VUMeter | - | control | 7.6, -8.7, 4.1 | marker Marker_MasterVUMeter_L | VUStaticMesh=SM_VUMeter | - |
| 41 | VUMeter | - | control | 9.2, -8.7, 4.2 | marker Marker_MasterVUMeter_R | VUStaticMesh=SM_VUMeter | - |
| 42 | BeatFXBeatPreviousButton | Beat FX Previous | button | 11.3, -2.3, 4.3 | marker Marker_BeatFX_ArrowLeft | - | calls Console.SetBeatFxAutoBpm, Console.SetPreviousBeatFXTimeInterval |
| 43 | BeatFXBeatNextButton | Beat FX Next | button | 14.7, -2.3, 4.3 | marker Marker_BeatFX_ArrowRight | - | calls Console.ResetTapBpmQueue, OwningPawn.Server_SetBeatFXBpm, Console.OnTapButtonPressed, Console.SetNextBeatFXTimeInterval |
| 44 | BeatFXTypeKnob_NXS2 | Helix/Roll/SlipRoll/Pitch/Phaser/Flanger/Filter/T… | stepped knob | 13.1, 4.6, 5.2 | bone Beat_FX_Type_Jnt | BoneKnobCenterYawOffset=-164 | calls Label.UpdateLabelText, Console.SetBeatFxType (in BeatFXTypeKnob) |
| 45 | BeatFXChannelKnob_NXS2 | BeatFXChannel | stepped knob | 13.1, 7.4, 5.2 | bone Beat_FX_Chan_Jnt | - | calls Console.SetBeatFXChannel |
| 46 | BeatFXTimeKnob | Beat FX Time | knob | 13.1, 10.4, 5.2 | bone Beat_FX_Time_Jnt | - | calls Console.AddBeatFXTime, Console.SetBeatFXTimeInterval, Console.Multi_SetBeatFxBpm, Console.SetBeatFxTime |
| 47 | BeatFXLevelDepthKnob | Beat FX Level/Depth | knob | 13.1, 13.8, 5.2 | bone Beat_FX_Level_Jnt | - | calls Console.SetBeatFXLevel |
| 48 | BeatFXToggleButton | Beat FX On/Off | toggle button | 13.1, 17.0, 4.3 | marker Marker_BeatFX_ToggleButton | - | calls Console.SetBeatFXToggleIntent, MidiManager.SendMidiEvent |
| 49 | BeatFXQuantizeButton | Beat FX Quantize | toggle button | 15.0, -0.3, 4.2 | marker Marker_BeatFX_QuantizeButton | - | calls Console.SetBeatFXQuantize |
| 50 | BeatFXTapButton | Beat FX Tap Tempo | button | 13.1, -0.6, 4.3 | marker Marker_BeatFxTapButton | - | calls Console.ResetTapBpmQueue, OwningPawn.Server_SetBeatFXBpm, Console.OnTapButtonPressed, Console.SetTapButtonHeld |
| 51 | BeatFXAutoTapButton | Beat FX Auto/Tap Tempo | toggle button | 11.1, -0.3, 4.3 | marker Marker_BeatFXAutoTap | - | calls Console.SetBeatFxAutoBpm; follows Console.OnBeatFxBpmModeChanged |
| 52 | BeatFXEqButton | Beat FX EQ {X} (High/Mid/Low) | toggle button | 11.1, 1.9, 4.2 | marker Marker_BeatFxEqLow | EQBand=0 | calls Console.SetBeatFxEq |
| 53 | BeatFXEqButton | Beat FX EQ {X} (High/Mid/Low) | toggle button | 13.0, 1.9, 4.2 | marker Marker_BeatFxEqMid | EQBand=1 | calls Console.SetBeatFxEq |
| 54 | BeatFXEqButton | Beat FX EQ {X} (High/Mid/Low) | toggle button | 15.0, 1.9, 4.2 | marker Marker_BeatFxEqHigh | EQBand=2 | calls Console.SetBeatFxEq |
| 55 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -13.6, -1.7, 4.3 | marker Marker_ColorFX_DubEcho | FXType=2 | calls Console.SetActiveFXButton, Console.DisableFX |
| 56 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -15.2, 0.4, 4.3 | marker Marker_ColorFX_Noise | FXType=4 | calls Console.SetActiveFXButton, Console.DisableFX |
| 57 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -11.9, 0.4, 4.3 | marker Marker_ColorFX_Filter | FXType=6 | calls Console.SetActiveFXButton, Console.DisableFX |
| 58 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -13.6, 0.4, 4.3 | marker Marker_ColorFX_Crush | FXType=5 | calls Console.SetActiveFXButton, Console.DisableFX |
| 59 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -15.2, -1.7, 4.3 | marker Marker_ColorFX_Space | FXType=1 | calls Console.SetActiveFXButton, Console.DisableFX |
| 60 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -11.8, -1.7, 4.3 | marker Marker_ColorFX_Sweep | FXType=3 | calls Console.SetActiveFXButton, Console.DisableFX |
| 61 | ColorFXParameterKnob | Color FX Parameter | knob | -13.6, 2.9, 5.1 | bone Color_FX_Param_Jnt | - | calls Console.SetColorFxParameter |
| 62 | HeadphoneMixKnob | Headphone Mix | knob | -13.5, 10.1, 5.2 | bone Headphone_Mix_Jnt | - | calls Mixer.SetHeadphonesMix |
| 63 | HeadphoneLevelKnob | Headphone Level | knob | -13.6, 12.9, 5.2 | bone Headphone_Level_Jnt | BoneKnobCenterYawOffset=150 | calls Mixer.SetHeadphonesLevel |
| 64 | HeadphoneIndicator | - | control | -13.6, 17.6, 4.2 | marker Marker_Headphones_Indicator | - | - |
| 65 | Crossfader | Crossfader | fader | -2.0, 17.6, 5.0 | bone Crossfader_Jnt | - | calls Console.Set Crossfader |
| 66 | CrossfaderCurveSwitch | Crossfader Curve | stepped slider | 8.4, 13.8, 4.1 | bone Crossfader_Curve_Jnt | - | calls Console.SetCrossfaderCurve |
| 67 | ChannelFaderCurveSwitch | Channel Fader Curve | stepped slider | 8.4, 11.5, 4.1 | bone Chan_Fader_Curve_Jnt | - | calls Console.SetChannelFaderCurve |
| 68 | EqCurveSwitch | EQ Curve | stepped slider | 8.2, 9.2, 4.1 | bone EQ_Curve_Jnt | - | calls Console.SetEqCurve |
| 69 | MicLevelKnob | Microphone Level | knob | -14.8, -10.7, 5.1 | bone Mic_Level_Jnt | BoneKnobCenterYawOffset=148 | calls Console.SetMicLevel |
| 70 | MicSwitch | Microphone On/Off/Talkover | stepped slider | -13.8, -4.8, 4.3 | bone Mic_Switch_Jnt | MaxSliderOffset=0.3, BoneOriginCenterOffset=0.2 | calls Console.SetMicMode |
| 71 | MicEQKnob | Microphone EQ {X} | knob | -13.6, -7.0, 5.1 | bone Mic_Low_Jnt | Band=0 | calls Console.SetMicEQ |
| 72 | MicEQKnob | Microphone EQ {X} | knob | -13.6, -8.7, 5.1 | bone Mic_Hi_Jnt | Band=2 | calls Console.SetMicEQ |
| 73 | BeatFxXpadButton | - | button | 11.0, -5.8, 4.3 | marker Marker_XpadButton_1_16 | BeatFxInterval=13 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |
| 74 | BeatFxXpadButton | - | button | 12.4, -5.8, 4.3 | marker Marker_XpadButton_1_8 | BeatFxInterval=15 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |
| 75 | BeatFxXpadButton | - | button | 13.7, -5.8, 4.3 | marker Marker_XpadButton_1_4 | BeatFxInterval=17 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |
| 76 | BeatFxXpadButton | - | button | 15.0, -5.8, 4.3 | marker Marker_XpadButton_1_2 | BeatFxInterval=19 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |
| 77 | BeatFxXpadButton | - | button | 11.0, -4.1, 4.3 | marker Marker_XpadButton_3_4 | BeatFxInterval=21 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |
| 78 | BeatFxXpadButton | - | button | 12.4, -4.1, 4.3 | marker Marker_XpadButton_1 | BeatFxInterval=22 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |
| 79 | BeatFxXpadButton | - | button | 13.7, -4.1, 4.3 | marker Marker_XpadButton_2 | BeatFxInterval=24 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |
| 80 | BeatFxXpadButton | - | button | 15.0, -4.1, 4.3 | marker Marker_XpadButton_4 | BeatFxInterval=26 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |

## DJM-V10

Model `BP_DJM_V10_C` on `BP_Console_C`. model id `DJM-V10`. SKU `Equipment_V10`. 38 cm wide. control table `DT_DJM-V10_ControlInfo`. skeleton `SK_DJM-V10_Mixer_Skeleton`.

| # | Control | Label | Kind | x, y, z (cm) | Placed by | Settings | What it does |
|---|---|---|---|---|---|---|---|
| 1 | ChannelInputKnob (ch 1) | Channel {X} Input | stepped knob | -12.9, -19.7, 4.8 | bone JOINT_DIGITAL_LINE_PHONO_01 | - | calls Mixer.SetChannelInput |
| 2 | ChannelInputKnob (ch 2) | Channel {X} Input | stepped knob | -9.0, -19.7, 4.8 | bone JOINT_DIGITAL_LINE_PHONO_02 | - | as above |
| 3 | ChannelInputKnob (ch 3) | Channel {X} Input | stepped knob | -5.0, -19.7, 4.8 | bone JOINT_DIGITAL_LINE_PHONO_03 | - | as above |
| 4 | ChannelInputKnob (ch 4) | Channel {X} Input | stepped knob | -0.9, -19.7, 4.8 | bone JOINT_DIGITAL_LINE_PHONO_04 | - | as above |
| 5 | ChannelInputKnob (ch 5) | Channel {X} Input | stepped knob | 3.1, -19.7, 4.8 | bone JOINT_DIGITAL_LINE_PHONO_05 | - | as above |
| 6 | ChannelInputKnob (ch 6) | Channel {X} Input | stepped knob | 7.1, -19.7, 4.8 | bone JOINT_DIGITAL_LINE_PHONO_06 | - | as above |
| 7 | ChannelTrimKnob (ch 1) | Trim {Ch} | knob | -13.7, -17.2, 5.0 | bone JOINT_TRIM_01 | - | calls Mixer.SetChannelTrim; follows Video Call Manager.OnAudioOutputTypeChanged, Video Call Manager.OnCallEndedDelegate, Video Call Manager.OnVideoCallStartSuccessDelegate |
| 8 | ChannelTrimKnob (ch 2) | Trim {Ch} | knob | -9.8, -17.2, 5.0 | bone JOINT_TRIM_02 | - | as above |
| 9 | ChannelTrimKnob (ch 3) | Trim {Ch} | knob | -5.8, -17.2, 5.0 | bone JOINT_TRIM_03 | - | as above |
| 10 | ChannelTrimKnob (ch 4) | Trim {Ch} | knob | -1.7, -17.2, 5.0 | bone JOINT_TRIM_04 | - | as above |
| 11 | ChannelTrimKnob (ch 5) | Trim {Ch} | knob | 2.2, -17.2, 5.0 | bone JOINT_TRIM_05 | - | as above |
| 12 | ChannelTrimKnob (ch 6) | Trim {Ch} | knob | 6.3, -17.2, 5.0 | bone JOINT_TRIM_06 | - | as above |
| 13 | ChannelCompKnob (ch 1) | Comp Level {Ch} | knob | -11.8, -16.1, 4.5 | bone JOINT_comp_01 | BoneKnobCenterYawOffset=150 | calls Mixer.SetChannelComp |
| 14 | ChannelCompKnob (ch 2) | Comp Level {Ch} | knob | -7.9, -16.1, 4.5 | bone JOINT_comp_02 | BoneKnobCenterYawOffset=150 | as above |
| 15 | ChannelCompKnob (ch 3) | Comp Level {Ch} | knob | -3.9, -16.1, 4.5 | bone JOINT_comp_03 | BoneKnobCenterYawOffset=150 | as above |
| 16 | ChannelCompKnob (ch 4) | Comp Level {Ch} | knob | 0.2, -16.1, 4.5 | bone JOINT_comp_04 | BoneKnobCenterYawOffset=150 | as above |
| 17 | ChannelCompKnob (ch 5) | Comp Level {Ch} | knob | 4.2, -16.1, 4.5 | bone JOINT_comp_05 | BoneKnobCenterYawOffset=150 | as above |
| 18 | ChannelCompKnob (ch 6) | Comp Level {Ch} | knob | 8.2, -16.1, 4.5 | bone JOINT_comp_06 | BoneKnobCenterYawOffset=150 | as above |
| 19 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -12.9, -4.7, 5.1 | bone JOINT_EQ_LOW_01 | EQBand=0 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 20 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -8.9, -4.7, 5.1 | bone JOINT_EQ_LOW_02 | EQBand=0 | as above |
| 21 | ChannelEQKnob (ch 3) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -4.9, -4.7, 5.1 | bone JOINT_EQ_LOW_03 | EQBand=0 | as above |
| 22 | ChannelEQKnob (ch 4) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -0.9, -4.7, 5.1 | bone JOINT_EQ_LOW_04 | EQBand=0 | as above |
| 23 | ChannelEQKnob (ch 5) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 3.1, -4.7, 5.1 | bone JOINT_EQ_LOW_05 | EQBand=0 | as above |
| 24 | ChannelEQKnob (ch 6) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 7.1, -4.7, 5.1 | bone JOINT_EQ_LOW_06 | EQBand=0 | as above |
| 25 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -12.9, -7.8, 5.1 | bone JOINT_EQ_LOW_MID_01 | EQBand=1 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 26 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -8.9, -7.8, 5.1 | bone JOINT_EQ_LOW_MID_02 | EQBand=1 | as above |
| 27 | ChannelEQKnob (ch 3) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -4.9, -7.8, 5.1 | bone JOINT_EQ_LOW_MID_03 | EQBand=1 | as above |
| 28 | ChannelEQKnob (ch 4) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -0.9, -7.8, 5.1 | bone JOINT_EQ_LOW_MID_04 | EQBand=1 | as above |
| 29 | ChannelEQKnob (ch 5) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 3.1, -7.8, 5.1 | bone JOINT_EQ_LOW_MID_05 | EQBand=1 | as above |
| 30 | ChannelEQKnob (ch 6) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 7.1, -7.8, 5.1 | bone JOINT_EQ_LOW_MID_06 | EQBand=1 | as above |
| 31 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -12.9, -10.8, 5.1 | bone JOINT_EQ_MID_01 | EQBand=3 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 32 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -8.9, -10.8, 5.1 | bone JOINT_EQ_MID_02 | EQBand=3 | as above |
| 33 | ChannelEQKnob (ch 3) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -4.9, -10.8, 5.1 | bone JOINT_EQ_MID_03 | EQBand=3 | as above |
| 34 | ChannelEQKnob (ch 4) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -0.9, -10.8, 5.1 | bone JOINT_EQ_MID_04 | EQBand=3 | as above |
| 35 | ChannelEQKnob (ch 5) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 3.1, -10.8, 5.1 | bone JOINT_EQ_MID_05 | EQBand=3 | as above |
| 36 | ChannelEQKnob (ch 6) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 7.1, -10.8, 5.1 | bone JOINT_EQ_MID_06 | EQBand=3 | as above |
| 37 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -12.9, -13.9, 5.1 | bone JOINT_EQ_HI_01 | EQBand=4 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 38 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -8.9, -13.9, 5.1 | bone JOINT_EQ_HI_02 | EQBand=4 | as above |
| 39 | ChannelEQKnob (ch 3) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -4.9, -13.9, 5.1 | bone JOINT_EQ_HI_03 | EQBand=4 | as above |
| 40 | ChannelEQKnob (ch 4) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -0.9, -13.9, 5.1 | bone JOINT_EQ_HI_04 | EQBand=4 | as above |
| 41 | ChannelEQKnob (ch 5) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 3.1, -13.9, 5.1 | bone JOINT_EQ_HI_05 | EQBand=4 | as above |
| 42 | ChannelEQKnob (ch 6) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 7.1, -13.9, 5.1 | bone JOINT_EQ_HI_06 | EQBand=4 | as above |
| 43 | ChannelSendKnob (ch 1) | Send Level {Ch} | knob | -12.9, 4.0, 4.9 | bone JOINT_SEND_01 | BoneKnobCenterYawOffset=150 | calls Console.SetChannelSendLevel |
| 44 | ChannelSendKnob (ch 2) | Send Level {Ch} | knob | -8.9, 4.0, 4.9 | bone JOINT_SEND_02 | BoneKnobCenterYawOffset=150 | as above |
| 45 | ChannelSendKnob (ch 3) | Send Level {Ch} | knob | -4.9, 4.0, 4.9 | bone JOINT_SEND_03 | BoneKnobCenterYawOffset=150 | as above |
| 46 | ChannelSendKnob (ch 4) | Send Level {Ch} | knob | -0.9, 4.0, 4.9 | bone JOINT_SEND_04 | BoneKnobCenterYawOffset=150 | as above |
| 47 | ChannelSendKnob (ch 5) | Send Level {Ch} | knob | 3.0, 4.0, 4.9 | bone JOINT_SEND_05 | BoneKnobCenterYawOffset=150 | as above |
| 48 | ChannelSendKnob (ch 6) | Send Level {Ch} | knob | 7.0, 4.0, 4.9 | bone JOINT_SEND_06 | BoneKnobCenterYawOffset=150 | as above |
| 49 | ChannelFilterKnob (ch 1) | Filter Level {Ch} | knob | -12.9, -1.2, 5.0 | bone JOINT_FILTER_01 | BoneKnobCenterYawOffset=150 | calls Console.SetChannelFilterLevel |
| 50 | ChannelFilterKnob (ch 2) | Filter Level {Ch} | knob | -8.9, -1.2, 5.0 | bone JOINT_FILTER_02 | BoneKnobCenterYawOffset=150 | as above |
| 51 | ChannelFilterKnob (ch 3) | Filter Level {Ch} | knob | -4.9, -1.2, 5.0 | bone JOINT_FILTER_03 | BoneKnobCenterYawOffset=150 | as above |
| 52 | ChannelFilterKnob (ch 4) | Filter Level {Ch} | knob | -0.9, -1.2, 5.0 | bone JOINT_FILTER_04 | BoneKnobCenterYawOffset=150 | as above |
| 53 | ChannelFilterKnob (ch 5) | Filter Level {Ch} | knob | 3.1, -1.2, 5.0 | bone JOINT_FILTER_05 | BoneKnobCenterYawOffset=150 | as above |
| 54 | ChannelFilterKnob (ch 6) | Filter Level {Ch} | knob | 7.1, -1.2, 5.0 | bone JOINT_FILTER_06 | BoneKnobCenterYawOffset=150 | as above |
| 55 | ChannelCueButton (ch 1) | Channel {Ch} Cue | toggle button | -13.9, 6.6, 4.2 | marker Marker_CueChannel1 | - | calls Console.SetChannelCue |
| 56 | ChannelCueButton (ch 2) | Channel {Ch} Cue | toggle button | -9.9, 6.6, 4.2 | marker Marker_CueChannel2 | - | as above |
| 57 | ChannelCueButton (ch 3) | Channel {Ch} Cue | toggle button | -5.9, 6.6, 4.2 | marker Marker_CueChannel3 | - | as above |
| 58 | ChannelCueButton (ch 4) | Channel {Ch} Cue | toggle button | -1.9, 6.6, 4.2 | marker Marker_CueChannel4 | - | as above |
| 59 | ChannelCueButton (ch 5) | Channel {Ch} Cue | toggle button | 2.2, 6.6, 4.2 | marker Marker_CueChannel5 | - | as above |
| 60 | ChannelCueButton (ch 6) | Channel {Ch} Cue | toggle button | 6.1, 6.6, 4.2 | marker Marker_CueChannel6 | - | as above |
| 61 | BeatFXAssignButton (ch 1) | Beat FX Assign {Channel} (Master/Mic/Crossfader B… | button | -12.9, 1.4, 4.2 | marker Marker_BeatFXAssign_Channel1 | BeatFXChannel=switch(Temp_int_Variable) {0: Temp_byte_Variable_5; 1: Temp_byte_Variable_4; 2: Temp_byte_Variable_3; 3: Temp_byte_Variable_2; 4: Temp_byte_Variable_1; 5: Temp_byte_Variable; default: K2Node_Select_Default} | calls Console.SetBeatFXAssignButton |
| 62 | BeatFXAssignButton (ch 2) | Beat FX Assign {Channel} (Master/Mic/Crossfader B… | button | -9.0, 1.4, 4.2 | marker Marker_BeatFXAssign_Channel2 | BeatFXChannel=switch(Temp_int_Variable) {0: Temp_byte_Variable_5; 1: Temp_byte_Variable_4; 2: Temp_byte_Variable_3; 3: Temp_byte_Variable_2; 4: Temp_byte_Variable_1; 5: Temp_byte_Variable; default: K2Node_Select_Default} | as above |
| 63 | BeatFXAssignButton (ch 3) | Beat FX Assign {Channel} (Master/Mic/Crossfader B… | button | -4.9, 1.4, 4.2 | marker Marker_BeatFXAssign_Channel3 | BeatFXChannel=switch(Temp_int_Variable) {0: Temp_byte_Variable_5; 1: Temp_byte_Variable_4; 2: Temp_byte_Variable_3; 3: Temp_byte_Variable_2; 4: Temp_byte_Variable_1; 5: Temp_byte_Variable; default: K2Node_Select_Default} | as above |
| 64 | BeatFXAssignButton (ch 4) | Beat FX Assign {Channel} (Master/Mic/Crossfader B… | button | -1.0, 1.4, 4.2 | marker Marker_BeatFXAssign_Channel4 | BeatFXChannel=switch(Temp_int_Variable) {0: Temp_byte_Variable_5; 1: Temp_byte_Variable_4; 2: Temp_byte_Variable_3; 3: Temp_byte_Variable_2; 4: Temp_byte_Variable_1; 5: Temp_byte_Variable; default: K2Node_Select_Default} | as above |
| 65 | BeatFXAssignButton (ch 5) | Beat FX Assign {Channel} (Master/Mic/Crossfader B… | button | 3.1, 1.4, 4.2 | marker Marker_BeatFXAssign_Channel5 | BeatFXChannel=switch(Temp_int_Variable) {0: Temp_byte_Variable_5; 1: Temp_byte_Variable_4; 2: Temp_byte_Variable_3; 3: Temp_byte_Variable_2; 4: Temp_byte_Variable_1; 5: Temp_byte_Variable; default: K2Node_Select_Default} | as above |
| 66 | BeatFXAssignButton (ch 6) | Beat FX Assign {Channel} (Master/Mic/Crossfader B… | button | 7.1, 1.4, 4.2 | marker Marker_BeatFXAssign_Channel6 | BeatFXChannel=switch(Temp_int_Variable) {0: Temp_byte_Variable_5; 1: Temp_byte_Variable_4; 2: Temp_byte_Variable_3; 3: Temp_byte_Variable_2; 4: Temp_byte_Variable_1; 5: Temp_byte_Variable; default: K2Node_Select_Default} | as above |
| 67 | ChannelVolumeSlider (ch 1) | Volume Fader {Ch} | fader | -12.9, 11.7, 4.9 | bone JOINT_VOLUME_01 | - | calls Rig.broadcast OnControlReset, Console.SetChannelFader |
| 68 | ChannelVolumeSlider (ch 2) | Volume Fader {Ch} | fader | -8.9, 11.7, 4.9 | bone JOINT_VOLUME_02 | - | as above |
| 69 | ChannelVolumeSlider (ch 3) | Volume Fader {Ch} | fader | -4.9, 11.7, 4.9 | bone JOINT_VOLUME_03 | - | as above |
| 70 | ChannelVolumeSlider (ch 4) | Volume Fader {Ch} | fader | -0.9, 11.7, 4.9 | bone JOINT_VOLUME_04 | - | as above |
| 71 | ChannelVolumeSlider (ch 5) | Volume Fader {Ch} | fader | 3.1, 11.7, 4.9 | bone JOINT_VOLUME_05 | - | as above |
| 72 | ChannelVolumeSlider (ch 6) | Volume Fader {Ch} | fader | 7.1, 11.7, 4.9 | bone JOINT_VOLUME_06 | - | as above |
| 73 | VUMeter (ch 1) | - | control | -14.6, -9.4, 4.1 | marker Marker_VUMeter_Channel_1 | VUStaticMesh=SM_VUMeter_V10 | - |
| 74 | VUMeter (ch 2) | - | control | -10.6, -9.4, 4.1 | marker Marker_VUMeter_Channel_2 | VUStaticMesh=SM_VUMeter_V10 | as above |
| 75 | VUMeter (ch 3) | - | control | -6.6, -9.4, 4.1 | marker Marker_VUMeter_Channel_3 | VUStaticMesh=SM_VUMeter_V10 | as above |
| 76 | VUMeter (ch 4) | - | control | -2.6, -9.4, 4.1 | marker Marker_VUMeter_Channel_4 | VUStaticMesh=SM_VUMeter_V10 | as above |
| 77 | VUMeter (ch 5) | - | control | 1.4, -9.4, 4.1 | marker Marker_VUMeter_Channel_5 | VUStaticMesh=SM_VUMeter_V10 | as above |
| 78 | VUMeter (ch 6) | - | control | 5.4, -9.4, 4.1 | marker Marker_VUMeter_Channel_6 | VUStaticMesh=SM_VUMeter_V10 | as above |
| 79 | CrossfaderAssign (ch 1) | Crossfader Assign {Ch} | stepped slider | -12.9, 16.9, 4.0 | bone JOINT_AthruB_01 | DefaultFractionIndex=switch(Temp_bool_Variable) {false: Temp_int_Variable_4; true: Temp_int_Variable_5; default: K2Node_Select_Default_4} | calls Console.SetCrossfaderAssign |
| 80 | CrossfaderAssign (ch 2) | Crossfader Assign {Ch} | stepped slider | -8.9, 16.9, 4.0 | bone JOINT_AthruB_02 | DefaultFractionIndex=switch(Temp_bool_Variable) {false: Temp_int_Variable_4; true: Temp_int_Variable_5; default: K2Node_Select_Default_4} | as above |
| 81 | CrossfaderAssign (ch 3) | Crossfader Assign {Ch} | stepped slider | -4.9, 16.9, 4.0 | bone JOINT_AthruB_03 | DefaultFractionIndex=switch(Temp_bool_Variable) {false: Temp_int_Variable_4; true: Temp_int_Variable_5; default: K2Node_Select_Default_4} | as above |
| 82 | CrossfaderAssign (ch 4) | Crossfader Assign {Ch} | stepped slider | -0.9, 16.9, 4.0 | bone JOINT_AthruB_04 | DefaultFractionIndex=switch(Temp_bool_Variable) {false: Temp_int_Variable_4; true: Temp_int_Variable_5; default: K2Node_Select_Default_4} | as above |
| 83 | CrossfaderAssign (ch 5) | Crossfader Assign {Ch} | stepped slider | 3.1, 16.9, 4.0 | bone JOINT_AthruB_05 | DefaultFractionIndex=switch(Temp_bool_Variable) {false: Temp_int_Variable_4; true: Temp_int_Variable_5; default: K2Node_Select_Default_4} | as above |
| 84 | CrossfaderAssign (ch 6) | Crossfader Assign {Ch} | stepped slider | 7.1, 16.9, 4.0 | bone JOINT_AthruB_06 | DefaultFractionIndex=switch(Temp_bool_Variable) {false: Temp_int_Variable_4; true: Temp_int_Variable_5; default: K2Node_Select_Default_4} | as above |
| 85 | MasterLevelKnob | Master Level | knob | 11.1, -17.2, 5.1 | bone JOINT_MASTER_LEVEL | BoneKnobCenterYawOffset=-60 | calls Mixer.SetMasterLevel; follows Video Call Manager.OnAudioOutputTypeChanged, Video Call Manager.OnCallEndedDelegate, Video Call Manager.OnVideoCallStartSuccessDelegate |
| 86 | MasterFilterKnob | Master Filter Knob | knob | 11.1, -1.2, 5.0 | bone JOINT_FILTER_07 | BoneKnobCenterYawOffset=150 | calls Console.SetMasterFilterLevel |
| 87 | MasterCueButton | Master Cue | toggle button | 10.2, 3.3, 4.2 | marker Marker_CueMaster | - | calls Mixer.SetMasterCue |
| 88 | BeatFXAssignButton | Beat FX Assign {Channel} (Master/Mic/Crossfader B… | button | 11.0, 1.4, 4.2 | marker Marker_BeatFXAssign_Master | BeatFXChannel=17 | calls Console.SetBeatFXAssignButton |
| 89 | VUMeter | - | control | 10.4, -9.4, 4.1 | marker Marker_VUMeter_MasterLeft | VUStaticMesh=SM_VUMeter_V10 | - |
| 90 | VUMeter | - | control | 11.9, -9.4, 4.1 | marker Marker_VUMeter_MasterRight | VUStaticMesh=SM_VUMeter_V10 | - |
| 91 | BeatFXBeatPreviousButton | Beat FX Previous | button | 14.9, 4.9, 4.2 | marker Marker_BeatFXPrev | - | calls Console.SetBeatFxAutoBpm, Console.SetPreviousBeatFXTimeInterval |
| 92 | BeatFXBeatNextButton | Beat FX Next | button | 18.9, 4.9, 4.2 | marker Marker_BeatFXNext | - | calls Console.ResetTapBpmQueue, OwningPawn.Server_SetBeatFXBpm, Console.OnTapButtonPressed, Console.SetNextBeatFXTimeInterval |
| 93 | BeatFXTypeKnob_V10 | Pitch/Roll/Trans/Filter/Phaser/Flanger/Reverb/Hel… | stepped knob | 16.9, 10.1, 5.1 | bone JOINT_BEAT_FX_TYPE | - | calls Label.UpdateLabelText, Console.SetBeatFxType (in BeatFXTypeKnob) |
| 94 | BeatFXTimeKnob | Beat FX Time | knob | 16.9, 13.2, 5.1 | bone JOINT_TIME | - | calls Console.AddBeatFXTime, Console.SetBeatFXTimeInterval, Console.Multi_SetBeatFxBpm, Console.SetBeatFxTime |
| 95 | BeatFXLevelDepthKnob | Beat FX Level/Depth | knob | 16.9, 16.5, 5.1 | bone JOINT_LEVEL_DEPTH | - | calls Console.SetBeatFXLevel |
| 96 | BeatFXToggleButton | Beat FX On/Off | toggle button | 16.9, 19.8, 4.3 | marker Marker_BeatFXToggleButton | - | calls Console.SetBeatFXToggleIntent, MidiManager.SendMidiEvent |
| 97 | BeatFXQuantizeButton | Beat FX Quantize | toggle button | 15.5, -1.9, 4.0 | marker Marker_BeatFXQuantizeButton | - | calls Console.SetBeatFXQuantize |
| 98 | BeatFXTapButton | Beat FX Tap Tempo | button | 16.9, 4.9, 4.2 | marker Marker_BeatFXTap | - | calls Console.ResetTapBpmQueue, OwningPawn.Server_SetBeatFXBpm, Console.OnTapButtonPressed, Console.SetTapButtonHeld |
| 99 | BeatFXAutoTapButton | Beat FX Auto/Tap Tempo | toggle button | 14.2, -1.9, 4.0 | marker Marker_BeatFXAutoTap | - | calls Console.SetBeatFxAutoBpm; follows Console.OnBeatFxBpmModeChanged |
| 100 | BeatFXEqButton | Beat FX EQ {X} (High/Mid/Low) | toggle button | 14.8, 7.4, 4.2 | marker Marker_BeatFXEQLow | EQBand=0 | calls Console.SetBeatFxEq |
| 101 | BeatFXEqButton | Beat FX EQ {X} (High/Mid/Low) | toggle button | 16.9, 7.4, 4.2 | marker Marker_BeatFXEQMid | EQBand=1 | calls Console.SetBeatFxEq |
| 102 | BeatFXEqButton | Beat FX EQ {X} (High/Mid/Low) | toggle button | 18.9, 7.4, 4.2 | marker Marker_BeatFXEQHigh | EQBand=2 | calls Console.SetBeatFxEq |
| 103 | SendFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -20.3, 1.4, 4.3 | marker Marker_ShortDelayButton | FXType=7 | calls Console.SetActiveFXButton, Console.DisableFX (in ColorFXButton) |
| 104 | SendFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -18.3, 1.4, 4.3 | marker Marker_LongDelayButton | FXType=8 | calls Console.SetActiveFXButton, Console.DisableFX (in ColorFXButton) |
| 105 | SendFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -20.3, 3.8, 4.3 | marker Marker_DubEchoButton | FXType=2 | calls Console.SetActiveFXButton, Console.DisableFX (in ColorFXButton) |
| 106 | SendFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -18.3, 3.8, 4.3 | marker Marker_ReverbButton | FXType=9 | calls Console.SetActiveFXButton, Console.DisableFX (in ColorFXButton) |
| 107 | SendSizeFeedbackKnob | Send Size Feedback Knob | knob | -19.8, 8.2, 4.9 | bone JOINT_SIZE_FEEDBACK | - | calls Console.SetSendFXSize |
| 108 | SendTimeKnob | Send Time Knob | knob | -16.8, 8.2, 4.9 | bone JOINT_TIME1 | - | calls Console.SetSendFXTime |
| 109 | SendToneKnob | Send Tone Knob | knob | -19.8, 11.3, 4.9 | bone JOINT_TONE | - | calls Console.SetSendFXTone |
| 110 | SendMasterMixKnob | Send Master Mix Knob | knob | -16.8, 11.3, 4.9 | bone JOINT_MASTER_MIX_LEVEL | - | calls Console.SetSendFXMasterMixLevel |
| 111 | SendMasterMixButton | Send Master Mix Toggle | toggle button | -18.3, 5.8, 4.3 | marker Marker_MasterMixButton | - | calls Console.SetSendFXMasterMixEnabled |
| 112 | HeadphoneMixKnob | Headphone Mix | knob | -20.1, 16.8, 4.9 | bone JOINT_mix01 | - | calls Mixer.SetHeadphonesMix |
| 113 | HeadphoneLevelKnob | Headphone Level | knob | -16.6, 16.8, 4.9 | bone JOINT_level01 | - | calls Mixer.SetHeadphonesLevel |
| 114 | HeadphonePreEQButton | Headphone Pre EQ | toggle button | -18.3, 14.3, 4.3 | marker Marker_PreEQButton | - | calls Mixer.SetHeadphonesPreEq |
| 115 | HeadphoneIndicator | - | control | -18.4, 20.4, 4.2 | marker Marker_Headphones_Indicator | - | - |
| 116 | FilterResonanceKnob | Filter Resonance Knob | knob | -18.3, -1.3, 5.0 | bone JOINT_RESONANCE | - | calls Console.SetChannelFilterResonance |
| 117 | FilterButton | High Pass Filter/Low Pass Filter | button | -19.8, -4.2, 4.3 | marker Marker_LPFButton | FilterType=1 | calls Console.SetActiveFilterButton |
| 118 | FilterButton | High Pass Filter/Low Pass Filter | button | -16.9, -4.2, 4.3 | marker Marker_HPFButton | FilterType=2 | calls Console.SetActiveFilterButton |
| 119 | Crossfader | Crossfader | fader | -2.9, 20.3, 4.9 | bone JOINT_CrossFader | - | calls Console.Set Crossfader |
| 120 | IsolatorEQKnob | Isolator EQ {EQ Band} (High/HighMid/Mid/LowMid/Lo… | knob | 15.1, -6.0, 5.2 | bone JOINT_ISOLATOR_LOW | - | calls Mixer.SetMasterIsolatorEq |
| 121 | IsolatorEQKnob | Isolator EQ {EQ Band} (High/HighMid/Mid/LowMid/Lo… | knob | 15.1, -10.5, 5.2 | bone JOINT_ISOLATOR_MID | EQBand=2 | calls Mixer.SetMasterIsolatorEq |
| 122 | IsolatorEQKnob | Isolator EQ {EQ Band} (High/HighMid/Mid/LowMid/Lo… | knob | 15.1, -15.0, 5.2 | bone JOINT_ISOLATOR_HI | EQBand=4 | calls Mixer.SetMasterIsolatorEq |
| 123 | IsolatorOnButton | Isolator Toggle | toggle button | 15.1, -17.9, 4.3 | marker Marker_IsolatorOnButton | - | calls Mixer.SetMasterIsolatorEqEnabled |
| 124 | MicLevelKnob | Microphone Level | knob | -19.5, -12.8, 4.9 | bone JOINT_LEVEL_MIC1 | - | calls Console.SetMicLevel |
| 125 | MicSwitch | Microphone On/Off/Talkover | stepped slider | -19.6, -6.8, 4.2 | bone JOINT_MIC_SWITCH | MaxSliderOffset=0.3 | calls Console.SetMicMode |
| 126 | MicEQKnob | Microphone EQ {X} | knob | -17.1, -10.1, 4.9 | bone JOINT_EQ_HI | Band=0 | calls Console.SetMicEQ |
| 127 | MicEQKnob | Microphone EQ {X} | knob | -19.5, -10.1, 4.9 | bone JOINT_EQ_LOW | Band=2 | calls Console.SetMicEQ |
| 128 | BeatFXAssignButton | Beat FX Assign {Channel} (Master/Mic/Crossfader B… | button | -16.9, -6.8, 4.3 | marker Marker_BeatFXAssign_Mic | BeatFXChannel=16 | calls Console.SetBeatFXAssignButton |
| 129 | CurveSettingsButton | Curve Settings | button | 17.6, -1.9, 4.0 | marker Marker_CurveSettingsButton | - | calls Console.ToggleBeatFxView |
| 130 | CurveSettingsExitButton | Exit Curve Settings | button | 19.8, -2.0, 4.0 | marker Marker_CurveSettingsExitButton | - | calls Console.ToggleBeatFxView |
| 131 | CrossfaderSelectButton | Crossfader Curve {Setting} (Long/Medium/Short) | button | 14.6, 1.8, 4.0 | marker Marker_CrossFaderCurveButton_Short | CurveSetting=2 | calls Console.SetCrossfaderCurve |
| 132 | CrossfaderSelectButton | Crossfader Curve {Setting} (Long/Medium/Short) | button | 16.8, 1.8, 4.0 | marker Marker_CrossFaderCurveButton_Medium | CurveSetting=1 | calls Console.SetCrossfaderCurve |
| 133 | CrossfaderSelectButton | Crossfader Curve {Setting} (Long/Medium/Short) | button | 19.1, 1.8, 4.0 | marker Marker_CrossFaderCurveButton_Long | - | calls Console.SetCrossfaderCurve |
| 134 | ChFaderSelectButton | Channel Fader Select {Setting} (Long/Medium/Short) | button | 14.6, -0.3, 4.0 | marker Marker_ChFaderCurveButton_Short | - | calls Console.SetChannelFaderCurve |
| 135 | ChFaderSelectButton | Channel Fader Select {Setting} (Long/Medium/Short) | button | 16.8, -0.3, 4.0 | marker Marker_ChFaderCurveButton_Medium | CurveSetting=1 | calls Console.SetChannelFaderCurve |
| 136 | ChFaderSelectButton | Channel Fader Select {Setting} (Long/Medium/Short) | button | 19.1, -0.3, 4.0 | marker Marker_ChFaderCurveButton_Long | CurveSetting=2 | calls Console.SetChannelFaderCurve |
| 137 | BeatFxXpadSlider | - | fader | 16.9, 1.4, 4.1 | marker Marker_XpadSlider | - | calls Console.SetBeatFxXpadEnabled, Console.SetBeatFxTouchIntent, Console.SetBeatFxParameter; follows Console.OnActiveBeatFxChanged |
| 138 | BeatFxXpadButton | - | button | 14.4, 0.8, 4.0 | marker Marker_XPad_1-16 | BeatFxInterval=13 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |
| 139 | BeatFxXpadButton | - | button | 16.1, 0.8, 4.0 | marker Marker_XPad_1-8 | BeatFxInterval=15 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |
| 140 | BeatFxXpadButton | - | button | 17.7, 0.8, 4.0 | marker Marker_XPad_1-4 | BeatFxInterval=17 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |
| 141 | BeatFxXpadButton | - | button | 19.4, 0.8, 4.0 | marker Marker_XPad_1-2 | BeatFxInterval=19 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |
| 142 | BeatFxXpadButton | - | button | 14.4, 2.0, 4.0 | marker Marker_XPad_3-4 | BeatFxInterval=21 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |
| 143 | BeatFxXpadButton | - | button | 16.1, 2.0, 4.0 | marker Marker_XPad_1 | BeatFxInterval=22 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |
| 144 | BeatFxXpadButton | - | button | 17.7, 2.0, 4.0 | marker Marker_XPad_2 | BeatFxInterval=24 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |
| 145 | BeatFxXpadButton | - | button | 19.4, 2.0, 4.0 | marker Marker_XPad_4 | BeatFxInterval=26 | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval |

## DDJ-FLX4 (mixer)

Model `BP_FLX4-Mixer_C` on `BP_Console_C`. model id `DDJ-FLX4`. SKU `Equipment_FLX4`. control table `DT_DDJ-FLX4_ControlInfo_0`. skeleton `SK_DDJ-FLX4_Skeleton`.

| # | Control | Label | Kind | x, y, z (cm) | Placed by | Settings | What it does |
|---|---|---|---|---|---|---|---|
| 1 | ChannelTrimKnob (ch 1) | Trim {Ch} | knob | -3.0, -14.4, 2.8 | bone JTrimLeft | - | calls Mixer.SetChannelTrim; follows Video Call Manager.OnAudioOutputTypeChanged, Video Call Manager.OnCallEndedDelegate, Video Call Manager.OnVideoCallStartSuccessDelegate |
| 2 | ChannelTrimKnob (ch 2) | Trim {Ch} | knob | 3.2, -14.4, 2.8 | bone JTrimRight | - | as above |
| 3 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -3.0, -10.7, 2.8 | bone JEQHighLeft | EQBand=4 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 4 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 3.0, -10.7, 2.8 | bone JEQHighRight | EQBand=4 | as above |
| 5 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -3.0, -7.0, 2.8 | bone JEQMidLeft | EQBand=2 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 6 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 3.0, -7.0, 2.8 | bone JEQMidRight | EQBand=2 | as above |
| 7 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -3.0, -3.3, 2.8 | bone JEQLowLeft | EQBand=0 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 8 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 3.0, -3.3, 2.8 | bone JEQLowRight | EQBand=0 | as above |
| 9 | ChannelColorKnob (ch 1) | Color FX Level {Ch} | knob | -3.0, 0.4, 2.8 | bone JCFXLeft | - | calls Mixer.SetChannelColor; follows Console.OnColorFXCenterLockToggled |
| 10 | ChannelColorKnob (ch 2) | Color FX Level {Ch} | knob | 3.0, 0.4, 2.8 | bone JCFXRight | - | as above |
| 11 | ChannelCueButton (ch 1) | Channel {Ch} Cue | toggle button | -3.0, 4.1, 1.6 | bone JCueChannel1 | - | calls Console.SetChannelCue |
| 12 | ChannelCueButton (ch 2) | Channel {Ch} Cue | toggle button | 3.0, 4.1, 1.6 | bone JCueChannel2 | - | as above |
| 13 | ChannelVolumeSlider (ch 1) | Volume Fader {Ch} | fader | -3.0, 10.1, 2.6 | bone JChannelFaderLeft | MaxOffset=2.95 | calls Rig.broadcast OnControlReset, Console.SetChannelFader |
| 14 | ChannelVolumeSlider (ch 2) | Volume Fader {Ch} | fader | 2.9, 10.1, 2.6 | bone JChannelFaderRight | MaxOffset=2.95 | as above |
| 15 | VUMeter (ch 1) | - | control | -0.7, -7.0, 1.7 | marker Marker_VUMeter_Channel1 | VUStaticMesh=SM_VUMeter_FLX4 | - |
| 16 | VUMeter (ch 2) | - | control | 0.7, -7.0, 1.7 | marker Marker_VUMeter_Channel2 | VUStaticMesh=SM_VUMeter_FLX4 | as above |
| 17 | LoadButton (ch 1) | Load | button | -4.9, -17.5, 1.8 | bone JLoad1 | - | calls W_TrackOptions.LoadTrackToDeck, ActiveTrackList.OnLoadButtonClick |
| 18 | LoadButton (ch 2) | Load | button | 4.9, -17.5, 1.8 | bone JLoad2 | - | as above |
| 19 | MasterLevelKnob | Master Level | knob | 8.6, -14.4, 2.8 | bone JMasterLevel | - | calls Mixer.SetMasterLevel; follows Video Call Manager.OnAudioOutputTypeChanged, Video Call Manager.OnCallEndedDelegate, Video Call Manager.OnVideoCallStartSuccessDelegate |
| 20 | MasterCueButton | Master Cue | toggle button | 8.7, -10.7, 1.6 | bone JCueMaster | - | calls Mixer.SetMasterCue |
| 21 | RotaryKnob | Rotary Knob | knob | 0.0, -18.0, 2.7 | bone JRotaryKnob | BoneKnobCenterYawOffset=147 | calls OwningPawn.SetInputMode, OwningPawn.ShowDesktopMiniMenu, MiniMenu.ShowMusicPanel, TrackBrowser.RotaryClick, TrackBrowser.RotaryNext, TrackBrowser.RotaryPrev |
| 22 | HeadphoneLevelKnob | Headphone Level | knob | -8.6, 8.8, 2.8 | bone JHeadphoneLevel | - | calls Mixer.SetHeadphonesLevel |
| 23 | HeadphoneMixKnob | Headphone Mix | knob | -8.6, 4.9, 2.8 | bone JHeadphoneMix | - | calls Mixer.SetHeadphonesMix |
| 24 | HeadphoneIndicator | - | control | -8.6, 17.3, 1.6 | marker Marker_Headphones_Indicator | - | - |
| 25 | MicLevelKnob | Microphone Level | knob | -8.6, -7.0, 2.8 | bone JMicLevel | - | calls Console.SetMicLevel |
| 26 | Crossfader | Crossfader | fader | -0.0, 17.3, 2.6 | bone JCrossfader | MaxOffset=3 | calls Console.Set Crossfader |
| 27 | BeatFXBeatPreviousButton | Beat FX Previous | button | 7.5, 4.1, 1.7 | bone JBeatFXNumber1 | - | calls Console.SetBeatFxAutoBpm, Console.SetPreviousBeatFXTimeInterval |
| 28 | BeatFXBeatNextButton | Beat FX Next | button | 9.7, 4.1, 1.7 | bone JBeatFXNumber2 | - | calls Console.ResetTapBpmQueue, OwningPawn.Server_SetBeatFXBpm, Console.OnTapButtonPressed, Console.SetNextBeatFXTimeInterval |
| 29 | BeatFXLevelDepthKnob | Beat FX Level/Depth | knob | 8.6, 8.8, 2.8 | bone JBeatFXLevel | - | calls Console.SetBeatFXLevel |
| 30 | BeatFXToggleButton | Beat FX On/Off | toggle button | 8.7, 13.1, 1.8 | bone JBeatFXOnOff | - | calls Console.SetBeatFXToggleIntent, MidiManager.SendMidiEvent |
| 31 | BeatFXSelectButton | Beat FX Select | button | 8.7, 0.4, 1.7 | bone JBeatFXSelect | - | calls Console.AdvanceBeatFXType |
| 32 | BeatFXChannelSwitch | Beat FX Channel | stepped slider | 8.6, -3.3, 2.1 | bone JBeatFXChannel | - | calls Console.SetBeatFXChannel |
| 33 | SmartFaderButton | Smart Fader | toggle button | -8.6, 13.1, 1.9 | bone JSmartFader | - | calls Console.SetSmartFaderEnabled |
| 34 | SmartCFXButton | ColorFX | toggle button | -8.6, 0.4, 1.9 | bone JSmartCFX | - | calls Mixer.SetActiveChannelFx, Console.SetSmartColorFx; follows Console.OnShiftChanged |

## Starter Mixer

Model `BP_StarterMixer_C` on `BP_Console_C`. model id `StarterMixer`. SKU `Equipment_StarterMixer`. 25.3 cm wide. control table `DT_StarterMixer_ControlInfo`. skeleton `SK_StarterMixer_Skeleton`.

| # | Control | Label | Kind | x, y, z (cm) | Placed by | Settings | What it does |
|---|---|---|---|---|---|---|---|
| 1 | ChannelTrimKnob (ch 1) | Trim {Ch} | knob | -3.0, -12.1, 3.2 | bone Joint_Channel1_Trim | BoneKnobCenterYawOffset=150 | calls Mixer.SetChannelTrim; follows Video Call Manager.OnAudioOutputTypeChanged, Video Call Manager.OnCallEndedDelegate, Video Call Manager.OnVideoCallStartSuccessDelegate |
| 2 | ChannelTrimKnob (ch 2) | Trim {Ch} | knob | 3.0, -12.1, 3.2 | bone Joint_Channel2_Trim | BoneKnobCenterYawOffset=150 | as above |
| 3 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -3.0, -9.2, 3.3 | bone Joint_Channel1_Hi | EQBand=4 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 4 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 3.0, -9.2, 3.3 | bone Joint_Channel2_Hi | EQBand=4 | as above |
| 5 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -3.0, -6.2, 3.3 | bone Joint_Channel1_Mid | EQBand=2 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 6 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 3.0, -6.2, 3.3 | bone Joint_Channel2_Mid | EQBand=2 | as above |
| 7 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -3.0, -3.3, 3.3 | bone Joint_Channel1_Low | EQBand=0 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 8 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 3.0, -3.3, 3.3 | bone Joint_Channel2_Low | EQBand=0 | as above |
| 9 | ChannelColorKnob (ch 1) | Color FX Level {Ch} | knob | -3.0, -0.4, 3.2 | bone Joint_Channel1_Filter | - | calls Mixer.SetChannelColor; follows Console.OnColorFXCenterLockToggled |
| 10 | ChannelColorKnob (ch 2) | Color FX Level {Ch} | knob | 3.0, -0.4, 3.2 | bone Joint_Channel2_Filter | - | as above |
| 11 | ChannelCueButton (ch 1) | Channel {Ch} Cue | toggle button | -3.0, 2.6, 3.3 | marker Marker_CueChannel1 | - | calls Console.SetChannelCue |
| 12 | ChannelCueButton (ch 2) | Channel {Ch} Cue | toggle button | 3.0, 2.7, 3.4 | marker Marker_CueChannel2 | - | as above |
| 13 | ChannelVolumeSlider (ch 1) | Volume Fader {Ch} | fader | -3.0, 10.1, 3.1 | bone Joint_Channel1_Volume | MaxOffset=2.3, BoneOriginCenterOffset=2.3 | calls Rig.broadcast OnControlReset, Console.SetChannelFader |
| 14 | ChannelVolumeSlider (ch 2) | Volume Fader {Ch} | fader | 3.0, 10.1, 3.1 | bone Joint_Channel2_Volume | MaxOffset=2.3, BoneOriginCenterOffset=2.3 | as above |
| 15 | VUMeter (ch 1) | - | control | -0.4, -6.1, 3.2 | marker Marker_VUMeter_Channel1 | VUStaticMesh=SM_VUMeter | - |
| 16 | VUMeter (ch 2) | - | control | 0.4, -6.1, 3.1 | marker Marker_VUMeter_Channel2 | VUStaticMesh=SM_VUMeter | as above |
| 17 | MasterLevelKnob | Master Level | knob | -0.0, -14.6, 3.1 | bone Joint_Master_Volume | BoneKnobCenterYawOffset=147 | calls Mixer.SetMasterLevel; follows Video Call Manager.OnAudioOutputTypeChanged, Video Call Manager.OnCallEndedDelegate, Video Call Manager.OnVideoCallStartSuccessDelegate |
| 18 | MasterCueButton | Master Cue | toggle button | 0.0, -12.0, 3.3 | marker Marker_MasterCue | - | calls Mixer.SetMasterCue |
| 19 | HeadphoneIndicator | - | control | -7.4, 14.7, 3.2 | marker Marker_Headphones_Indicator | - | - |
| 20 | Crossfader | Crossfader | fader | -0.0, 13.7, 3.1 | bone Joint_Crossfader | MaxOffset=2.7 | calls Console.Set Crossfader |

## Tribe Mixer

Model `BP_TribeMixer_C` on `BP_Console_C`. model id `TribeMixer`. SKU `Equipment_TribeMixer`. 33 cm wide. control table `DT_TribeMixer_ControlInfo`. skeleton `SK_TribeMixer_Skeleton`.

Bone positions moved by (-0.01, -1.18, -4.38) cm to match this model's markers (15 of 15 controls with both agree on that offset).

| # | Control | Label | Kind | x, y, z (cm) | Placed by | Settings | What it does |
|---|---|---|---|---|---|---|---|
| 1 | ChannelTrimKnob (ch 1) | Trim {Ch} | knob | -8.1, -13.0, 4.6 | bone Chan_1_Trim_Jnt | - | calls Mixer.SetChannelTrim; follows Video Call Manager.OnAudioOutputTypeChanged, Video Call Manager.OnCallEndedDelegate, Video Call Manager.OnVideoCallStartSuccessDelegate |
| 2 | ChannelTrimKnob (ch 2) | Trim {Ch} | knob | -3.8, -13.0, 4.6 | bone Chan_2_Trim_Jnt | - | as above |
| 3 | ChannelTrimKnob (ch 3) | Trim {Ch} | knob | 0.5, -13.0, 4.6 | bone Chan_3_Trim_Jnt | - | as above |
| 4 | ChannelTrimKnob (ch 4) | Trim {Ch} | knob | 4.8, -13.0, 4.6 | bone Chan_4_Trim_Jnt | - | as above |
| 5 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -8.1, -10.2, 4.7 | bone Chan_1_EQ_Hi_Jnt | EQBand=4 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 6 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -3.8, -10.2, 4.7 | bone Chan_2_EQ_Hi_Jnt | EQBand=4 | as above |
| 7 | ChannelEQKnob (ch 3) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 0.5, -10.2, 4.7 | bone Chan_3_EQ_Hi_Jnt | EQBand=4 | as above |
| 8 | ChannelEQKnob (ch 4) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 4.8, -10.2, 4.7 | bone Chan_4_EQ_Hi_Jnt | EQBand=4 | as above |
| 9 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -8.1, -7.3, 4.7 | bone Chan_1_EQ_Mid_Jnt | EQBand=2 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 10 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -3.8, -7.3, 4.7 | bone Chan_2_EQ_Mid_Jnt | EQBand=2 | as above |
| 11 | ChannelEQKnob (ch 3) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 0.5, -7.3, 4.7 | bone Chan_3_EQ_Mid_Jnt | EQBand=2 | as above |
| 12 | ChannelEQKnob (ch 4) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 4.8, -7.3, 4.7 | bone Chan_4_EQ_Mid_Jnt | EQBand=2 | as above |
| 13 | ChannelEQKnob (ch 1) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -8.1, -4.4, 4.7 | bone Chan_1_EQ_Low_Jnt | EQBand=0 | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged |
| 14 | ChannelEQKnob (ch 2) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | -3.8, -4.4, 4.7 | bone Chan_2_EQ_Low_Jnt | EQBand=0 | as above |
| 15 | ChannelEQKnob (ch 3) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 0.5, -4.4, 4.7 | bone Chan_3_EQ_Low_Jnt | EQBand=0 | as above |
| 16 | ChannelEQKnob (ch 4) | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | 4.8, -4.4, 4.7 | bone Chan_4_EQ_Low_Jnt | EQBand=0 | as above |
| 17 | ChannelColorKnob (ch 1) | Color FX Level {Ch} | knob | -8.1, -0.9, 4.6 | bone Chan_1_Color_FX_Jnt | - | calls Mixer.SetChannelColor; follows Console.OnColorFXCenterLockToggled |
| 18 | ChannelColorKnob (ch 2) | Color FX Level {Ch} | knob | -3.8, -0.9, 4.6 | bone Chan_2_Color_FX_Jnt | - | as above |
| 19 | ChannelColorKnob (ch 3) | Color FX Level {Ch} | knob | 0.5, -0.9, 4.6 | bone Chan_3_Color_FX_Jnt | - | as above |
| 20 | ChannelColorKnob (ch 4) | Color FX Level {Ch} | knob | 4.8, -0.9, 4.6 | bone Chan_4_Color_FX_Jnt | - | as above |
| 21 | ChannelCueButton (ch 1) | Channel {Ch} Cue | toggle button | -8.1, 1.8, 4.2 | marker Marker_CueChannel1 | - | calls Console.SetChannelCue |
| 22 | ChannelCueButton (ch 2) | Channel {Ch} Cue | toggle button | -3.8, 1.8, 4.2 | marker Marker_CueChannel2 | - | as above |
| 23 | ChannelCueButton (ch 3) | Channel {Ch} Cue | toggle button | 0.5, 1.7, 4.2 | marker Marker_CueChannel3 | - | as above |
| 24 | ChannelCueButton (ch 4) | Channel {Ch} Cue | toggle button | 4.8, 1.8, 4.2 | marker Marker_CueChannel4 | - | as above |
| 25 | ChannelVolumeSlider (ch 1) | Volume Fader {Ch} | fader | -8.1, 9.4, 4.6 | bone Volume_1_Jnt | BoneOriginCenterOffset=2.15 | calls Rig.broadcast OnControlReset, Console.SetChannelFader |
| 26 | ChannelVolumeSlider (ch 2) | Volume Fader {Ch} | fader | -3.8, 9.4, 4.6 | bone Volume_2_Jnt | BoneOriginCenterOffset=2.15 | as above |
| 27 | ChannelVolumeSlider (ch 3) | Volume Fader {Ch} | fader | 0.5, 9.4, 4.6 | bone Volume_3_Jnt | BoneOriginCenterOffset=2.15 | as above |
| 28 | ChannelVolumeSlider (ch 4) | Volume Fader {Ch} | fader | 4.8, 9.4, 4.6 | bone Volume_4_Jnt | BoneOriginCenterOffset=2.15 | as above |
| 29 | VUMeter (ch 1) | - | control | -10.0, -8.8, 3.9 | marker Marker_VUMeter_Channel1 | VUStaticMesh=SM_VUMeter | - |
| 30 | VUMeter (ch 2) | - | control | -5.7, -8.8, 3.9 | marker Marker_VUMeter_Channel2 | VUStaticMesh=SM_VUMeter | as above |
| 31 | VUMeter (ch 3) | - | control | -1.4, -8.8, 3.9 | marker Marker_VUMeter_Channel3 | VUStaticMesh=SM_VUMeter | as above |
| 32 | VUMeter (ch 4) | - | control | 2.9, -8.8, 3.9 | marker Marker_VUMeter_Channel4 | VUStaticMesh=SM_VUMeter | as above |
| 33 | CrossfaderAssign (ch 1) | Crossfader Assign {Ch} | stepped slider | -8.1, 12.5, 4.1 | bone Chan_1_Assign_Jnt | DefaultFractionIndex=switch(Temp_int_Variable_2) {0: Temp_int_Variable; 1: Temp_int_Variable_1; 2: Temp_int_Variable_4; 3: Temp_int_Variable_5; default: K2Node_Select_Default_1} | calls Console.SetCrossfaderAssign |
| 34 | CrossfaderAssign (ch 2) | Crossfader Assign {Ch} | stepped slider | -3.8, 12.5, 4.1 | bone Chan_2_Assign_Jnt | DefaultFractionIndex=switch(Temp_int_Variable_2) {0: Temp_int_Variable; 1: Temp_int_Variable_1; 2: Temp_int_Variable_4; 3: Temp_int_Variable_5; default: K2Node_Select_Default_1} | as above |
| 35 | CrossfaderAssign (ch 3) | Crossfader Assign {Ch} | stepped slider | 0.5, 12.5, 4.1 | bone Chan_3_Assign_Jnt | DefaultFractionIndex=switch(Temp_int_Variable_2) {0: Temp_int_Variable; 1: Temp_int_Variable_1; 2: Temp_int_Variable_4; 3: Temp_int_Variable_5; default: K2Node_Select_Default_1} | as above |
| 36 | CrossfaderAssign (ch 4) | Crossfader Assign {Ch} | stepped slider | 4.8, 12.5, 4.1 | bone Chan_4_Assign_Jnt | DefaultFractionIndex=switch(Temp_int_Variable_2) {0: Temp_int_Variable; 1: Temp_int_Variable_1; 2: Temp_int_Variable_4; 3: Temp_int_Variable_5; default: K2Node_Select_Default_1} | as above |
| 37 | MasterLevelKnob | Master Level | knob | 8.8, -15.5, 4.7 | bone Master_Volume_Jnt | - | calls Mixer.SetMasterLevel; follows Video Call Manager.OnAudioOutputTypeChanged, Video Call Manager.OnCallEndedDelegate, Video Call Manager.OnVideoCallStartSuccessDelegate |
| 38 | MasterBalanceKnob | Master Balance | knob | 8.8, -0.7, 4.7 | bone Master_Balance_Jnt | - | calls Mixer.SetMasterBalance |
| 39 | MasterCueButton | Master Cue | toggle button | 8.7, 1.8, 4.1 | marker Marker_MasterCue | - | calls Mixer.SetMasterCue |
| 40 | VUMeter | - | control | 8.0, -8.6, 4.1 | marker Marker_MasterVUMeter_L | VUStaticMesh=SM_VUMeter | - |
| 41 | VUMeter | - | control | 9.5, -8.6, 4.1 | marker Marker_MasterVUMeter_R | VUStaticMesh=SM_VUMeter | - |
| 42 | BeatFXBeatPreviousButton | Beat FX Previous | button | 11.5, -4.8, 4.2 | marker Marker_BeatFX_ArrowLeft | - | calls Console.SetBeatFxAutoBpm, Console.SetPreviousBeatFXTimeInterval |
| 43 | BeatFXBeatNextButton | Beat FX Next | button | 14.6, -4.8, 4.1 | marker Marker_BeatFX_ArrowRight | - | calls Console.ResetTapBpmQueue, OwningPawn.Server_SetBeatFXBpm, Console.OnTapButtonPressed, Console.SetNextBeatFXTimeInterval |
| 44 | BeatFXTypeKnob | Roll/Flanger/Trans/Echo | stepped knob | 13.1, 2.4, 4.5 | bone Beat_FX_Type_Jnt | - | calls Label.UpdateLabelText, Console.SetBeatFxType |
| 45 | BeatFXChannelKnob | BeatFXChannel | stepped knob | 13.1, 5.4, 4.5 | bone Beat_FX_Chan_Jnt | - | calls Console.SetBeatFXChannel |
| 46 | BeatFXTimeKnob | Beat FX Time | knob | 13.1, 8.4, 4.5 | bone Beat_FX_Time_Jnt | - | calls Console.AddBeatFXTime, Console.SetBeatFXTimeInterval, Console.Multi_SetBeatFxBpm, Console.SetBeatFxTime |
| 47 | BeatFXLevelDepthKnob | Beat FX Level/Depth | knob | 13.1, 11.9, 4.7 | bone Beat_FX_Level_Jnt | - | calls Console.SetBeatFXLevel |
| 48 | BeatFXToggleButton | Beat FX On/Off | toggle button | 13.1, 15.1, 4.1 | marker Marker_BeatFX_ToggleButton | - | calls Console.SetBeatFXToggleIntent, MidiManager.SendMidiEvent |
| 49 | BeatFXQuantizeButton | Beat FX Quantize | toggle button | 14.8, -2.5, 4.3 | marker Marker_BeatFX_QuantizeButton | - | calls Console.SetBeatFXQuantize |
| 50 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -14.2, -1.8, 4.1 | marker Marker_ColorFX_DubEcho | FXType=2 | calls Console.SetActiveFXButton, Console.DisableFX |
| 51 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -12.2, -1.8, 4.1 | marker Marker_ColorFX_Noise | FXType=4 | calls Console.SetActiveFXButton, Console.DisableFX |
| 52 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -12.2, 0.2, 4.1 | marker Marker_ColorFX_Filter | FXType=6 | calls Console.SetActiveFXButton, Console.DisableFX |
| 53 | ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | -14.2, 0.2, 4.1 | marker Marker_ColorFX_Crush | FXType=5 | calls Console.SetActiveFXButton, Console.DisableFX |
| 54 | HeadphoneMixKnob | Headphone Mix | knob | -13.4, 9.1, 4.7 | bone Headphone_Mix_Jnt | - | calls Mixer.SetHeadphonesMix |
| 55 | HeadphoneLevelKnob | Headphone Level | knob | -13.3, 11.9, 4.7 | bone Headphone_Level_Jnt | - | calls Mixer.SetHeadphonesLevel |
| 56 | HeadphoneIndicator | - | control | -13.4, 15.4, 4.0 | marker Marker_Headphones_Indicator | - | - |
| 57 | Crossfader | Crossfader | fader | -1.7, 16.0, 4.6 | bone Crossfader_Jnt | - | calls Console.Set Crossfader |
| 58 | CrossfaderCurveSwitch | Crossfader Curve | stepped slider | 8.8, 14.9, 4.1 | bone Crossfader_Curve_Jnt | - | calls Console.SetCrossfaderCurve |
| 59 | ChannelFaderCurveSwitch | Channel Fader Curve | stepped slider | 8.8, 12.5, 4.1 | bone Chan_Fader_Curve_Jnt | - | calls Console.SetChannelFaderCurve |
| 60 | MicLevelKnob | Microphone Level | knob | -13.3, -10.7, 4.6 | bone Mic_Level_Jnt | - | calls Console.SetMicLevel |
| 61 | MicSwitch | Microphone On/Off/Talkover | stepped slider | -13.3, -4.7, 4.5 | bone Mic_Switch_Jnt | - | calls Console.SetMicMode |
| 62 | MicEQKnob | Microphone EQ {X} | knob | -13.3, -7.0, 4.6 | bone Mic_Low_Jnt | Band=0 | calls Console.SetMicEQ |
| 63 | MicEQKnob | Microphone EQ {X} | knob | -13.3, -8.7, 4.6 | bone Mic_Hi_Jnt | Band=2 | calls Console.SetMicEQ |

## Every control class

The calls and events each class has in its own code (inherited behaviour comes from its parent). "On" lists the gear that spawns it.

| Control | Label | Kind | Parent | What it does | On | Asset (under /Game/Equipment) |
|---|---|---|---|---|---|---|
| ResoNextClipButton | Next Clip Layer {Channel} | button | InputButton | calls Apc.CheckLeavingClipGrid, OscManager.SetControlOscAddresses, OscManager.SendOscMessageInt | - | APC40/AdvanceClipButtons/BP_ResoNextClipButton |
| ResoPreviouisClipButton | Previous Clip Layer {Channel} | button | InputButton | calls Apc.CheckLeavingClipGrid, OscManager.SetControlOscAddresses, OscManager.SendOscMessageInt | - | APC40/AdvanceClipButtons/BP_ResoPreviouisClipButton |
| ResoBpmAdjustKnob | BPM Adjust | knob | KnobBase | calls OscManager.SetControlOscAddresses, OscManager.SendOscMessageFloat | - | APC40/BpmAdjustKnob/BP_ResoBpmAdjustKnob |
| ResoBpmDivideButton | BPM Divide | button | InputButton | calls BpmAdjustKnob.SetResolumeTempo, OscManager.SetControlOscAddresses, OscManager.SendOscMessageFloat | - | APC40/BpmDivideMultiplyButtons/BP_ResoBpmDivideButton |
| ResoBpmMultiplyButton | BPM Multiply | button | InputButton | calls BpmAdjustKnob.SetResolumeTempo, OscManager.SetControlOscAddresses, OscManager.SendOscMessageFloat | - | APC40/BpmDivideMultiplyButtons/BP_ResoBpmMultiplyButton |
| BpmNudgeDownButton | Nudge BPM Down | button | InputButton | calls OscManager.SetControlOscAddresses, OscManager.SendOscMessageInt | - | APC40/BpmNudgeButtons/BP_BpmNudgeDownButton |
| BpmNudgeUpButton | Nudge BPM Up | button | InputButton | calls OscManager.SetControlOscAddresses, OscManager.SendOscMessageInt | - | APC40/BpmNudgeButtons/BP_BpmNudgeUpButton |
| ResoBpmTapButton | Tap Tempo | button | InputButton | calls OscManager.SetControlOscAddresses, OscManager.SendOscMessageInt | - | APC40/BpmTapButton/BP_ResoBpmTapButton |
| ResoLaunchClipButton | Layer {Channel} Column {Row} | button | BaseDeckControl | calls LocalPawn.Server_OnClipButtonPressed, Apc.Set Button Mesh Material, Apc.OnOutputButtonChanged, Apc.SetActiveOutputButton, Apc.SetActivePreviewButton, OscManager.SetControlOscAddresses ... | - | APC40/ClipLaunchButton/BP_ResoLaunchClipButton |
| ResoClipSpeedKnob | Selected Clip Speed | knob | KnobBase | calls LocalPawn.Server_OnKnobTurnedReliable, LocalPawn.Server_OnKnobTurnedUnreliable, OscManager.SetControlOscAddresses, OscManager.RemoveAddressFromWhitelist, OscManager.SendOscMessageFloat | - | APC40/ClipSpeedKnob/BP_ResoClipSpeedKnob |
| ResoColumnTriggerButton | Trigger Column {Row} | radio button | BaseRadioButton | calls Apc.SetActiveColumnButton, OscManager.SetControlOscAddresses, LocalPawn.Server_OnRadioButtonPressed, OscManager.SendOscMessageInt | - | APC40/ColumnTriggerButton/BP_ResoColumnTriggerButton |
| ResoAssignCrossfadeAButton | Selected Layer to A | toggle button | BaseToggleButton | calls OscManager.SetControlOscAddresses, Apc.Update Crossfade Button Status, Apc.ClearCrossfadeButton, OscManager.RemoveAddressFromWhitelist, CrossfaderBButton.ReceiveOscMessage, LocalPawn.Server_OnToggleButtonPressed ... | - | APC40/CrossfadeAssignButtons/BP_ResoAssignCrossfadeAButton |
| ResoAssignCrossfadeBButton | Selected Layer to B | toggle button | BaseToggleButton | calls OscManager.SetControlOscAddresses, Apc.Update Crossfade Button Status, Apc.ClearCrossfadeButton, LocalPawn.Server_OnToggleButtonPressed, OscManager.SendOscMessageInt | - | APC40/CrossfadeAssignButtons/BP_ResoAssignCrossfadeBButton |
| ResoCrossfader | Crossfader | fader | SliderBase | calls LocalPawn.Server_OnSliderMovedReliable, LocalPawn.Server_OnSliderMovedUnreliable, OscManager.SetControlOscAddresses, OscManager.SendOscMessageFloat | - | APC40/Crossfader/BP_ResoCrossfader |
| ResoCompositionDashboardKnob | Composition Dashboard {Channel} | knob | KnobBase | calls LocalPawn.Server_OnKnobTurnedReliable, OscManager.SetControlOscAddresses, LocalPawn.Server_OnKnobTurnedUnreliable, OscManager.SendOscMessageFloat | - | APC40/DashboardKnob/BP_ResoCompositionDashboardKnob |
| ResoLayerDashboardKnob | Selected Layer Dashboard {Channel} | knob | KnobBase | calls LocalPawn.Server_OnKnobTurnedReliable, Apc.SetKnobPositionInLayer, OscManager.SetControlOscAddresses, LocalPawn.Server_OnKnobTurnedUnreliable, OscManager.RemoveAddressFromWhitelist, OscManager.SendOscMessageFloat | - | APC40/DashboardKnob/BP_ResoLayerDashboardKnob |
| ResoDeckSelectButton | Select Deck {Channel} | radio button | BaseRadioButton | calls LocalPawn.Server_OnRadioButtonPressed, OscManager.SetControlOscAddresses, Apc.SetActiveDeckButton, Apc.Init Reso Layer, Apc.Set Button Mesh Material, OscManager.SendOscMessageInt | - | APC40/DeckSelectButton/BP_ResoDeckSelectButton |
| ResoClearAllButton | Clear All Layers | button | InputButton | calls Apc.SetActiveOutputButton, OscManager.SetControlOscAddresses, LocalPawn.Server_OnInputButtonPressed, OscManager.SendOscMessageInt | - | APC40/LayerClearButtons/BP_ResoClearAllButton |
| ResoClearLayerButton | Clear Layer {Channel} | button | InputButton | calls OscManager.SendOscMessageInt, OscManager.SetControlOscAddresses, Apc.SetActiveOutputButton, LocalPawn.Server_OnInputButtonPressed | - | APC40/LayerClearButtons/BP_ResoClearLayerButton |
| ResoLayerSelectButton | Select Layer {Channel} | radio button | BaseRadioButton | calls LocalPawn.Server_OnRadioButtonPressed, OscManager.SetControlOscAddresses, Apc.SetActiveLayerButton, Apc.Init Reso Clips, Apc.EnableInteractiveLayer, OscManager.SendOscMessageInt | - | APC40/LayerSelectButton/BP_ResoLayerSelectButton |
| ResoLayerSlider | Layer {Channel} Opacity | fader | SliderBase | calls LocalPawn.Server_OnSliderMovedReliable, OscManager.SetControlOscAddresses, LocalPawn.Server_OnSliderMovedUnreliable, OscManager.SendOscMessageFloat | - | APC40/LayerSlider/BP_ResoLayerSlider |
| ResoMasterSlider | Master Opacity | fader | SliderBase | calls LocalPawn.Server_OnSliderMovedReliable, LocalPawn.Server_OnSliderMovedUnreliable, OscManager.SetControlOscAddresses, OscManager.SendOscMessageFloat | - | APC40/MasterSlider/Bp_ResoMasterSlider |
| ResoMatchTribeBpmButton | Sync Tribe Tempo | button | InputButton | calls OscManager.SetControlOscAddresses, BpmAdjustKnob.SetResolumeTempo, OscManager.SendOscMessageFloat, OscManager.SendOscMessageInt; follows CurrentBeatmatchTrack.OnTrackPlayed, TribeGameState.OnDeckTrackChanged | - | APC40/MatchTribeBpmButton/BP_ResoMatchTribeBpmButton |
| ResoMetronomeButton | Toggle Metronome | toggle button | BaseToggleButton | calls OscManager.SetControlOscAddresses, OscManager.SendOscMessageInt | - | APC40/MetronomeButton/BP_ResoMetronomeButton |
| ResoPlayPauseButton | PlayPause | toggle button | BaseToggleButton | calls OscManager.SetControlOscAddresses, LocalPawn.Server_OnToggleButtonPressed, OscManager.SendOscMessageInt | - | APC40/PlayPauseButton/BP_ResoPlayPauseButton |
| ResoPreviewCompositionButton | Preview Composition | button | InputButton | calls OscManager.SetControlOscAddresses, OscManager.SendOscMessageInt | - | APC40/PreviewCompositionButton/BP_ResoPreviewCompositionButton |
| ResoRecordButton | Record | toggle button | BaseToggleButton | calls OscManager.SetControlOscAddresses, OscManager.SendOscMessageInt | - | APC40/RecordButton/BP_ResoRecordButton |
| ResoBypassButton | Bypass Layer {Channel} | toggle button | BaseToggleButton | calls OscManager.SetControlOscAddresses, LocalPawn.Server_OnToggleButtonPressed, OscManager.SendOscMessageInt | - | APC40/SoloBypassButtons/BP_ResoBypassButton |
| ResoSoloButton | Solo Layer {Channel} | toggle button | BaseToggleButton | calls OscManager.SetControlOscAddresses, LocalPawn.Server_OnToggleButtonPressed, Apc.SetActiveSoloButton, OscManager.SendOscMessageInt | - | APC40/SoloBypassButtons/BP_ResoSoloButton |
| AcidSynthFilterKnob | Accent/Decay/EnvelopeMod/Resonance/CutoffFrequenc… | knob | KnobBase | generic behaviour of its kind | - | AcidSynth/Filters/BP_AcidSynthFilterKnob |
| AcidSynthLoadButton | Load Sequence | button | InputButton | calls AcidSynth.Open Acid Presets Menu | - | AcidSynth/Sequencing/BP_AcidSynthLoadButton |
| AcidSynthPlayButton | Start/Stop Sequence | button | InputButton | calls AcidSynth.StopPlay, AcidSynth.StartPlay | - | AcidSynth/Sequencing/BP_AcidSynthPlayButton |
| AcidSynthRandomButton | Randomize Sequence | button | InputButton | calls OwningPawn.Server_SetSequence, AcidSynth.SetSequence | - | AcidSynth/Sequencing/BP_AcidSynthRandomButton |
| AcidSynthSequenceButton | Sequence Button | button | InputButton | generic behaviour of its kind | - | AcidSynth/Sequencing/BP_AcidSynthSequenceButton |
| AcidSynthKeySyncButton | KeySync | toggle button | BaseToggleButton | calls AcidSynth.SetKeySyncEnabled | - | AcidSynth/Sync/BP_AcidSynthKeySyncButton |
| AcidSynthTempoSlider | Tempo Slider | fader | SliderBase | calls AcidSynth.Set BPM; follows AcidSynth.OnConsoleRespawned, AcidSynth.OnSyncStateChanged | - | AcidSynth/Tempo/BP_AcidSynthTempoSlider |
| DragSequenceEditorHandle | - | fader | SliderBase | generic behaviour of its kind | - | AcidSynth/UI/BP_DragSequenceEditorHandle |
| AcidSynthWaveformSwitch | - | stepped slider | QuantizedSlider | generic behaviour of its kind | - | AcidSynth/Waveform/BP_AcidSynthWaveformSwitch |
| BaseRadioButton | - | radio button | BaseDeckControl | generic behaviour of its kind | - | BP_BaseRadioButton |
| BaseToggleButton | - | toggle button | BaseDeckControl | generic behaviour of its kind | - | BP_BaseToggleButton |
| InputButton | - | button | BaseDeckControl | generic behaviour of its kind | - | BP_InputButton |
| KnobBase | - | knob | BaseDeckControl | generic behaviour of its kind | - | BP_KnobBase |
| QuantizedKnob | - | stepped knob | KnobBase | generic behaviour of its kind | - | BP_QuantizedKnob |
| QuantizedSlider | - | stepped slider | SliderBase | generic behaviour of its kind | - | BP_QuantizedSlider |
| SliderBase | - | fader | BaseDeckControl | generic behaviour of its kind | - | BP_SliderBase |
| BeatJumpLeft | Beat Jump Backwards | button | InputButton | calls Deck.PrevBeatJumpInterval, Deck.HandleLoopJump, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump | CDJ3000, CDJ3000X | Deck/BeatJump/BP_BeatJumpLeft |
| BeatJumpRight | Beat Jump Forwards | button | InputButton | calls Deck.NextBeatJumpInterval, Deck.HandleLoopJump, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump, Deck.Multi_JumpLoop ... | CDJ3000, CDJ3000X | Deck/BeatJump/BP_BeatJumpRight |
| BeatJumpScreenSelector | - | button | InputButton | calls Deck.SetBeatJumpValue | CDJ3000 | Deck/BeatJump/BP_BeatJumpScreenSelector |
| JogAdjust | Jog Adjust | knob | KnobBase | generic behaviour of its kind | CDJ3000, CDJ3000X, Tribe CDJ | Deck/JogAdjust/BP_JogAdjust |
| JogWheel3000X | JogWheel | jog wheel | JogWheel3000 | calls JogWheelFlashingRing.CreateDynamicMaterialInstance (in JogWheel3000); follows Deck.OnAlbumArtRequested, Deck.OnConsoleRespawned, Deck.OnJogModeChanged, Deck.OnSlipModeChanged ... | CDJ3000X | Deck/JogWheel/BP_JogWheel3000X |
| JogWheel3000 | JogWheel | jog wheel | JogWheel | calls JogWheelFlashingRing.CreateDynamicMaterialInstance; follows Deck.OnAlbumArtRequested, Deck.OnConsoleRespawned, Deck.OnJogModeChanged, Deck.OnSlipModeChanged ... | CDJ3000 | Deck/JogWheel/BP_JogWheel3000 |
| JogWheel | JogWheel | jog wheel | BaseDeckControl | calls Deck.JogStart, Deck.JogTick, GrabSphere.SetCollisionEnabled, AudioPlayer.JogBegin, OwningPawn.Server_SetJogGrabState, HoveringHand.RumbleControllerOnTap ... | - | Deck/JogWheel/BP_JogWheel |
| JogWheel_FLX4 | JogWheel | jog wheel | JogWheel_TribeCDJ | calls JogWheelFlashingRing.CreateDynamicMaterialInstance (in JogWheel_TribeCDJ) | DDJ-FLX4 | Deck/JogWheel/BP_JogWheel_FLX4 |
| JogWheel_StarterCDJ | JogWheel | jog wheel | JogWheel_TribeCDJ | calls JogWheelFlashingRing.CreateDynamicMaterialInstance (in JogWheel_TribeCDJ) | Starter CDJ | Deck/JogWheel/BP_JogWheel_StarterCDJ |
| JogWheel_TribeCDJ | JogWheel | jog wheel | JogWheel | calls JogWheelFlashingRing.CreateDynamicMaterialInstance | Tribe CDJ | Deck/JogWheel/BP_JogWheel_TribeCDJ |
| VinylModeToggle | Jog Mode | button | InputButton | calls Deck.SetJogMode; follows Deck.OnJogModeChanged | CDJ3000, CDJ3000X, Tribe CDJ | Deck/JogWheel/BP_VinylModeToggle |
| VinylWheel | JogWheel | jog wheel | JogWheel | calls AudioPlayer.SetScratchEndMode, AudioPlayer.AutoJogBegin, Deck.JogTick, AudioPlayer.JogEnd; follows Deck.OnDeckPlay, Deck.OnStreamTrackBeginDownload, Deck.OnTrackChanged, Deck.OnTrackUnloaded | VinylDeck | Deck/JogWheel/BP_VinylWheel |
| BeatLoopEightButton | 8 Beat Loop/Loop Extend | button | InputButton | calls Deck.ExtendLoop, OwningPawn.Server_ExtendLoop, OwningPawn.Server_SetLoopIn, OwningPawn.Server_SetLoopOut, Deck.SetBeatLoop | CDJ3000, CDJ3000X, Starter CDJ | Deck/Looping/BP_BeatLoopEightButton |
| BeatLoopFourButton | 4 Beat Loop/Loop Cutter | button | InputButton | calls Deck.CutLoop, OwningPawn.Server_CutLoop, OwningPawn.Server_SetLoopIn, OwningPawn.Server_SetLoopOut, Deck.SetBeatLoop | CDJ3000, CDJ3000X, Starter CDJ | Deck/Looping/BP_BeatLoopFourButton |
| BeatLoopPad | PerformancePad | button | PerformancePadButton | calls OwningPawn.Server_ExitLoopPrecise, Deck.ExitLoop, Deck.SetBeatLoop, OwningPawn.Server_SetLoopIn, OwningPawn.Server_SetLoopOut; follows Deck.OnActivePadModeChanged, Deck.OnBeatLoopSet, Deck.OnIsLoopingChanged | DDJ-FLX4 | Deck/Looping/BP_BeatLoopPad |
| FourBeatExitButton | 4 Beat Loop/Exit | button | InputButton | calls Deck.ExitLoop, OwningPawn.Server_ExitLoopPrecise, OwningPawn.Server_SetLoopIn, OwningPawn.Server_SetLoopOut, Deck.SetBeatLoop; follows Deck.OnIsLoopingChanged | DDJ-FLX4 | Deck/Looping/BP_FourBeatExitButton |
| LoopCutButton | Loop Cutter | button | InputButton | calls Deck.ClearMemoryCue, Deck.Multi_ClearMemoryCue, OwningPawn.Server_ClearMemoryCue, Deck.CutLoop, Deck.Multi_SeekToMemoryCue, OwningPawn.Server_SeekToMemoryCue | CDJ3000, CDJ3000X, DDJ-FLX4, Tribe CDJ | Deck/Looping/BP_LoopCutButton |
| LoopExtendButton | Loop Extend | button | InputButton | calls Deck.ExtendLoop, Deck.Multi_SeekToMemoryCue, OwningPawn.Server_SeekToMemoryCue, Deck.SetMemoryCue, Deck.Multi_SetMemoryCue, OwningPawn.Server_SetMemoryCue | CDJ3000, CDJ3000X, DDJ-FLX4, Tribe CDJ | Deck/Looping/BP_LoopExtendButton |
| LoopInButton | Loop In/Cue | button | InputButton | calls Deck.SetLoopAdjustmentMode, Deck.SetLoopInPosition, OwningPawn.Server_SetLoopIn; follows Deck.OnIsLoopingChanged, Deck.OnLoopInSet | CDJ3000, CDJ3000X, DDJ-FLX4, Tribe CDJ | Deck/Looping/BP_LoopInButton |
| LoopOutButton | LoopOut | button | InputButton | calls Deck.SetLoopOutPosition, OwningPawn.Server_SetLoopOut, Deck.SetLoopAdjustmentMode, OwningPawn.Server_SetLoopAdjustmentMode; follows Deck.OnIsLoopingChanged | CDJ3000, CDJ3000X, DDJ-FLX4, Tribe CDJ | Deck/Looping/BP_LoopOutButton |
| ReloopExitButton | Reloop/Exit | button | InputButton | calls Deck.ReturnToLoop, Deck.ExitLoop; follows Deck.OnIsLoopingChanged | CDJ3000, CDJ3000X, Starter CDJ, Tribe CDJ | Deck/Looping/BP_ReloopExitButton |
| MasterTempoButton | Master Tempo | toggle button | BaseToggleButton | calls Deck.SetMasterTempo, KeySyncButton.SetButtonOn; follows Deck.OnKeySyncChanged | CDJ3000, CDJ3000X, DDJ-FLX4, Tribe CDJ | Deck/MasterTempoButton/BP_MasterTempoButton |
| DeleteButton | Delete | button | InputButton | calls Deck.ClearMemoryCue, Deck.Multi_ClearMemoryCue, OwningPawn.Server_ClearMemoryCue | CDJ3000, CDJ3000X | Deck/Memory/BP_DeleteButton |
| MemoryButton | Memory | button | InputButton | calls Deck.SetMemoryCue, Deck.Multi_SetMemoryCue, OwningPawn.Server_SetMemoryCue | CDJ3000, CDJ3000X | Deck/Memory/BP_MemoryButton |
| BeatJumpPad | PerformancePad | button | PerformancePadButton | calls Deck.HandleLoopJump, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump | DDJ-FLX4 | Deck/Performance/BP_BeatJumpPad |
| FXPad | PerformancePad | button | PerformancePadButton | calls Deck.SetSlip, Mixer.SetBeatFXPadEnabled, Mixer.SetColorFXPadEnabled, Mixer.DisableColorFXPad, Deck.ExitLoop, Mixer.DisableBeatFXPad ... | DDJ-FLX4 | Deck/Performance/BP_FXPad |
| KeyShiftPad | PerformancePad | button | PerformancePadButton | calls Deck.SetKeyShift; follows Deck.OnActivePadModeChanged, Deck.OnKeyShiftChanged | DDJ-FLX4 | Deck/Performance/BP_KeyShiftPad |
| PerformancePadButton | PerformancePad | button | InputButton | calls Deck.broadcast OnPerformancePadInteraction | - | Deck/Performance/BP_PerformancePadButton |
| PerformancePadSelectButton | {Type} Mode | radio button | BaseRadioButton | calls Deck.SetActivePadButton; follows Deck.OnActivePadModeChanged | DDJ-FLX4 | Deck/Performance/BP_PerformancePadSelectButton |
| SamplerPad | PerformancePad | button | PerformancePadButton | calls SamplePlayer.Open, SamplePlayer.Play | DDJ-FLX4 | Deck/Performance/BP_SamplerPad |
| PitchSlider | {BPM} BPM / {Tempo} / {Key} / ({Master BPM} {Mast… | fader | SliderBase | calls Console.Multi_SetSmartFaderPitchMod_Reliable, Label.HighlightOnHover, Tribe_Game_Instance_BP.ThirdPersonSpectatorActive, SpectatorLabel.HighlightOnHover, Console.Multi_SetSmartFaderPitchMod, Deck.FlushNetDormancy ...; follows Deck.OnConsoleRespawned, Deck.OnSyncStateChanged, Deck.OnTempoUnlocked | CDJ3000, CDJ3000X, DDJ-FLX4, Starter CDJ, Tribe CDJ | Deck/PitchFader/BP_PitchSlider |
| VinylPitchSlider | {BPM} BPM / {Tempo} / {Key} / ({Master BPM} {Mast… | fader | PitchSlider | calls VinylDeck.SetAutoSpinRate | VinylDeck | Deck/PitchFader/BP_VinylPitchSlider |
| CueButton | Cue | button | BaseDeckControl | calls Deck.StopCuePreview, OwningPawn.Server_SeekToCue, PlayButton.Grab, PlayButton.Release, Deck.StartCuePreview, Deck.SetPlaybackMs ...; follows Deck.OnConsoleRespawned, Deck.OnCuePreviewCleared, Deck.OnDeckPause, Deck.OnDeckPlay ... | CDJ3000, CDJ3000X, DDJ-FLX4, Starter CDJ, Tribe CDJ | Deck/PlayPause/BP_CueButton |
| HotCueButton | Hot Cue {X} | button | BaseDeckControl | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ...; follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged | CDJ3000, CDJ3000X, Tribe CDJ | Deck/PlayPause/BP_HotCueButton |
| HotCueCallDelToggle | HotCueMode | button | InputButton | calls Deck.SetHotCueMode, OwningPawn.Server_SetHotCueMode; follows Deck.OnHotCueModeChanged | CDJ3000, CDJ3000X | Deck/PlayPause/BP_HotCueCallDelToggle |
| HotCuePad | PerformancePad | control | HotCueButton | calls Deck.ClearHotCue, Deck.Multi_ClearHotCue, Tribe_Pawn_BP.Server_ClearHotCue, Deck.ReleaseHotCue, Deck.Multi_SeekToHotCue, Tribe_Pawn_BP.Server_SeekToHotCue ... (in HotCueButton); follows Deck.OnHotCueModeChanged, Deck.OnHotOrMemoryCueChanged | DDJ-FLX4, Starter CDJ | Deck/PlayPause/BP_HotCuePad |
| HotCueRecCallToggle | HotCueMode | button | InputButton | calls Deck.SetHotCueMode | Tribe CDJ | Deck/PlayPause/BP_HotCueRecCallToggle |
| PlayButton | Play | button | BaseDeckControl | calls Deck.ClearCuePreview, OwningPawn.Server_StartPlay, Deck.Stop Play, OwningPawn.Server_StopPlay, Deck.Start Play; follows Deck.OnCuePreviewCleared, Deck.OnDeckPause, Deck.OnDeckPlay, Deck.OnTrackChanged ... | CDJ3000, CDJ3000X, DDJ-FLX4, Starter CDJ, Tribe CDJ | Deck/PlayPause/BP_PlayButton |
| PlayDirectionButton | PlayDirection | toggle button | BaseToggleButton | calls Deck.SetReversePlayback; follows Deck.OnDeckDirectionChanged | Tribe CDJ | Deck/PlayPause/BP_PlayDirectionButton |
| PlayDirectionSwitch | PlayDirection | stepped slider | QuantizedSlider | calls OwningPawn.Server_EndSlipReverse, Deck.EndSlipReverse, Deck.SetReversePlayback, Deck.BeginSlipReverse, OwningPawn.Server_BeginSlipReverse, PlayDirectionPanel.CreateDynamicMaterialInstance; follows Deck.OnDeckDirectionChanged | CDJ3000, CDJ3000X | Deck/PlayPause/BP_PlayDirectionSwitch |
| ShiftButton | Shift | button | InputButton | calls Deck.SetShifted, OwningPawn.ToggleShiftEnabled, OwningPawn.Server_SetShiftEnabled | DDJ-FLX4, Starter CDJ | Deck/PlayPause/BP_ShiftButton |
| TimeModeButton | Time Mode | toggle button | BaseToggleButton | calls Deck.SetTimeMode | CDJ3000, Tribe CDJ | Deck/PlayPause/BP_TimeModeButton |
| VinylStartStopButton | Start/Stop | button | InputButton | calls BP_Vinyl_Wheel.SetVinylInterpTime, VinylDeck.ToggleVinylDeckSpinning | VinylDeck | Deck/PlayPause/BP_VinylStartStopButton |
| VinylPowerButton | Power Knob | stepped knob | QuantizedKnob | calls VinylDeck.SetDeckOn, VinylDeck.ToggleVinylDeckSpinning | VinylDeck | Deck/Power/BP_VinylPowerButton |
| BeatgridEditButton | Edit Beatgrid | button | InputButton | calls Deck.ToggleBeatgridEditor | CDJ3000, CDJ3000X, DDJ-FLX4, Starter CDJ, Tribe CDJ | Deck/Quantize/BP_BeatgridEditButton |
| DeckQuantizeButton | Quantize | toggle button | BaseToggleButton | calls Deck.SetQuantized | CDJ3000, CDJ3000X, DDJ-FLX4, Starter CDJ, Tribe CDJ | Deck/Quantize/BP_DeckQuantizeButton |
| KeyShiftResetButton | Key Shift Reset | button | InputButton | calls Deck.SetKeyShift; follows Deck.OnScreenModeChanged | CDJ3000X | Deck/Screen/BP_KeyShiftResetButton |
| KeyShiftScreenButton | Key Shift {Dir} | button | InputButton | calls Deck.DecrementKeyShift, Deck.IncrementKeyShift; follows Deck.OnKeyShiftChanged, Deck.OnScreenModeChanged | CDJ3000X | Deck/Screen/BP_KeyShiftScreenButton |
| ScreenButtonBankSelector | Screen Button Bank {Num} | button | InputButton | calls Deck.SetScreenButtonBank; follows Deck.OnScreenModeChanged | CDJ3000X | Deck/Screen/BP_ScreenButtonBankSelector |
| ScreenLoopJumpButton | - | button | InputButton | calls Deck.ExitLoop, Deck.SetPositionFromBeatJump, Deck.Multi_BeatJump, OwningPawn.Server_BeatJump, OwningPawn.Server_ExitLoop, Deck.HandleLoopJump ...; follows Deck.OnBeatLoopSet, Deck.OnIsLoopingChanged, Deck.OnScreenButtonBankChanged, Deck.OnScreenModeChanged ... | CDJ3000X | Deck/Screen/BP_ScreenLoopJumpButton |
| ScreenModeSelectButton | Screen Mode {Mode} | toggle button | BaseToggleButton | calls Deck.SetActiveScreenMode; follows Deck.OnScreenModeChanged | CDJ3000X | Deck/Screen/BP_ScreenModeSelectButton |
| NeedleSearch | NeedleSearch | fader | SliderBase | calls Console.AutoSwitchSyncMaster, Deck.SetPositionFromFraction, Deck.RealignBeatSync | CDJ3000, CDJ3000X, DDJ-FLX4, Starter CDJ, Tribe CDJ | Deck/Search/BP_NeedleSearch |
| SearchButtonLeft | Search Backward | button | SearchButtonRight | calls Deck.SetPlaybackMs, Deck.RealignBeatSync, Console.AutoSwitchSyncMaster (in SearchButtonRight) | CDJ3000, CDJ3000X, Tribe CDJ | Deck/Search/BP_SearchButtonLeft |
| SearchButtonRight | Search Forward | button | InputButton | calls Deck.SetPlaybackMs, Deck.RealignBeatSync, Console.AutoSwitchSyncMaster | CDJ3000, CDJ3000X, Tribe CDJ | Deck/Search/BP_SearchButtonRight |
| Tonearm | Tonearm | tonearm | BaseDeckControl | calls RecentGrabController.RumbleControllerOnTap, VinylDeck.Multi_SetTouchBrake, VinylDeck.Stop Play, VinylDeck.SetTouchBrake, OwningPawn.Server_SetTouchBrake, self.broadcast TonearmReleased ...; follows VinylDeck.OnTrackOpened, VinylDeck.OnTrackUnloaded | - | Deck/Search/BP_Tonearm |
| TrackSearchNextButton | Track Search Forward | button | InputButton | calls Deck.Multi_SetPositionFromFraction | CDJ3000, CDJ3000X, Tribe CDJ | Deck/Search/BP_TrackSearchNextButton |
| TrackSearchPrevButton | Track Search Backward | button | InputButton | calls Deck.Multi_SetPositionFromFraction | CDJ3000, CDJ3000X, Tribe CDJ | Deck/Search/BP_TrackSearchPrevButton |
| WaveformSearch | NeedleSearch | fader | SliderBase | calls Console.AutoSwitchSyncMaster, Jogwheel.SetWaveformJogTouch, OwningPawn.Server_SetWaveformJogTouch, Jogwheel.SetWaveformTouchJogDelta | DDJ-FLX4 | Deck/Search/BP_WaveformSearch |
| SlipButton | Slip | toggle button | BaseToggleButton | calls Deck.SetSlip; follows AudioPlayer.OnSlipConditionChanged, Deck.OnSlipModeChanged | CDJ3000, CDJ3000X, Tribe CDJ | Deck/SlipButton/BP_SlipButton |
| TouchBrakeKnob | Vinyl Speed Adjust Touch/Brake | knob | KnobBase | calls Deck.SetTouchBrake | CDJ3000, CDJ3000X, Tribe CDJ | Deck/SpeedAdjust/BP_TouchBrakeKnob |
| KeySyncButton | KeySync | toggle button | BaseToggleButton | calls Deck.ToggleKeySync; follows Deck.OnConsoleRespawned, Deck.OnTrackChanged, Mixer.OnMasterKeyChanged | CDJ3000, CDJ3000X | Deck/SyncButton/BP_KeySyncButton |
| SyncButton | Sync | button | BaseDeckControl | calls ChannelDevice.End Sync, ChannelDevice.SetSyncMode, ChannelDevice.ToggleSync, SyncButtonInstanced.SetHiddenInGame, OwningPawn.Server_ToggleSync, ChannelDevice.StartSync ...; follows ChannelDevice.OnConsoleRespawned, ChannelDevice.OnSyncStateChanged | CDJ3000, CDJ3000X, Tribe CDJ | Deck/SyncButton/BP_SyncButton |
| SyncMasterButton | Sync Master | button | BaseDeckControl | calls ChannelDevice.ToggleSyncMaster, SyncButtonInstanced.SetHiddenInGame, ChannelDevice.SetSyncMaster, SyncButtonInstanced.SetStaticMesh; follows ChannelDevice.OnConsoleRespawned | CDJ3000, CDJ3000X, Tribe CDJ | Deck/SyncButton/BP_SyncMasterButton |
| SyncMasterComboButton | Sync | button | SyncButton | calls OwningPawn.Server_SetSyncMaster, BP_Deck.CycleTempoRange, OwningPawn.Server_ToggleSync, Console.AutoSwitchSyncMaster, ChannelDevice.SetSyncMaster | DDJ-FLX4, Starter CDJ | Deck/SyncButton/BP_SyncMasterComboButton |
| TempoSliderRangeButton | Tempo Range Adjust | button | InputButton | calls Deck.CycleTempoRange, PitchSlider.FlushNetDormancy, PitchSlider.OnRep_MaxPitchModulation | CDJ3000, CDJ3000X, Tribe CDJ | Deck/TempoRangeButton/BP_TempoSliderRangeButton |
| TempoResetButton | Tempo Reset | toggle button | BaseToggleButton | calls Deck.SetTempoLocked, TempoResetPanel.CreateDynamicMaterialInstance, TempoResetPanel.SetVisibility | CDJ3000, CDJ3000X, VinylDeck | Deck/TempoResetButton/BP_TempoResetButton |
| DrumMachineFilterKnob | Swing/SD Snappiness/SD Tone/BD Pitch/BD Distortio… | knob | KnobBase | generic behaviour of its kind | - | DrumMachine/Filters/BP_DrumMachineFilterKnob |
| DrumMachinePad | Cymbal/Tom High/Tom Mid/Tom Low/Bell/Shaker/Hi-Ha… | button | InputButton | calls DrumMachine.Toggle Drum in Selected Range, OwningPawn.Server_ToggleDrumMachineHit, DrumMachine.Multi_TriggerDrum, DrumMachine.TriggerDrum, OwningPawn.Server_TriggerDrumMachineHit, DrumMachine.Seconds Since Last Triggered | - | DrumMachine/Sequencing/BP_DrumMachinePad |
| DrumMachinePlayButton | Start/Stop Sequence | button | InputButton | calls DrumMachine.StartPlay, DrumMachine.StopPlay | - | DrumMachine/Sequencing/BP_DrumMachinePlayButton |
| DrumMachineQuantizeButton | Randomize Sequence | button | InputButton | calls DrumMachine.Toggle Quantize | - | DrumMachine/Sequencing/BP_DrumMachineQuantizeButton |
| DrumMachineRecordButton | Start/Stop Recording | button | InputButton | calls DrumMachine.Toggle Record | - | DrumMachine/Sequencing/BP_DrumMachineRecordButton |
| DrumMachineSequenceButton | - | button | InputButton | calls DrumMachine.Select Sequence Index | - | DrumMachine/Sequencing/BP_DrumMachineSequenceButton |
| DrumMachineTempoSlider | Tempo Slider | fader | SliderBase | calls DrumMachine.Set BPM; follows DrumMachine.OnConsoleRespawned, DrumMachine.OnSyncStateChanged | - | DrumMachine/Tempo/BP_DrumMachineTempoSlider |
| MixerKnobBase | - | knob | KnobBase | generic behaviour of its kind | - | Mixer/BP_MixerKnobBase |
| MixerSliderBase | - | fader | SliderBase | generic behaviour of its kind | - | Mixer/BP_MixerSliderBase |
| BeatFXAutoTapButton | Beat FX Auto/Tap Tempo | toggle button | BaseToggleButton | calls Console.SetBeatFxAutoBpm; follows Console.OnBeatFxBpmModeChanged | DJM-900NXS2, DJM-A9, DJM-V10 | Mixer/BeatFX/BP_BeatFxAutoTapButton |
| BeatFXBeatNextButton | Beat FX Next | button | InputButton | calls Console.ResetTapBpmQueue, OwningPawn.Server_SetBeatFXBpm, Console.OnTapButtonPressed, Console.SetNextBeatFXTimeInterval | DDJ-FLX4, DJM-900NXS2, DJM-A9, DJM-V10, Tribe Mixer | Mixer/BeatFX/BP_BeatFXBeatNextButton |
| BeatFXBeatPreviousButton | Beat FX Previous | button | InputButton | calls Console.SetBeatFxAutoBpm, Console.SetPreviousBeatFXTimeInterval | DDJ-FLX4, DJM-900NXS2, DJM-A9, DJM-V10, Tribe Mixer | Mixer/BeatFX/BP_BeatFXBeatPreviousButton |
| BeatFXChannelButton | Beat FX Channel {Channel}  | radio button | BaseRadioButton | calls Console.SetBeatFXChannel; follows Console.OnBeatFxChannelChanged | DJM-A9 | Mixer/BeatFX/BP_BeatFXChannelButton |
| BeatFXChannelKnob | BeatFXChannel | stepped knob | QuantizedKnob | calls Console.SetBeatFXChannel | Tribe Mixer | Mixer/BeatFX/BP_BeatFXChannelKnob |
| BeatFXChannelKnob_NXS2 | BeatFXChannel | stepped knob | QuantizedKnob | calls Console.SetBeatFXChannel | DJM-900NXS2 | Mixer/BeatFX/BP_BeatFXChannelKnob_NXS2 |
| BeatFXChannelSwitch | Beat FX Channel | stepped slider | QuantizedSlider | calls Console.SetBeatFXChannel | DDJ-FLX4 | Mixer/BeatFX/BP_BeatFXChannelSwitch |
| BeatFXEqButton | Beat FX EQ {X} (High/Mid/Low) | toggle button | BaseToggleButton | calls Console.SetBeatFxEq | DJM-900NXS2, DJM-A9, DJM-V10 | Mixer/BeatFX/BP_BeatFxEqButton |
| BeatFXLevelDepthKnob | Beat FX Level/Depth | knob | MixerKnobBase | calls Console.SetBeatFXLevel | DDJ-FLX4, DJM-900NXS2, DJM-A9, DJM-V10, Tribe Mixer | Mixer/BeatFX/BP_BeatFXLevelDepthKnob |
| BeatFXQuantizeButton | Beat FX Quantize | toggle button | BaseToggleButton | calls Console.SetBeatFXQuantize | DJM-900NXS2, DJM-A9, DJM-V10, Tribe Mixer | Mixer/BeatFX/BP_BeatFXQuantizeButton |
| BeatFXSelectButton | Beat FX Select | button | InputButton | calls Console.AdvanceBeatFXType | DDJ-FLX4 | Mixer/BeatFX/BP_BeatFXSelectButton |
| BeatFXTapButton | Beat FX Tap Tempo | button | InputButton | calls Console.ResetTapBpmQueue, OwningPawn.Server_SetBeatFXBpm, Console.OnTapButtonPressed, Console.SetTapButtonHeld | DJM-900NXS2, DJM-A9, DJM-V10 | Mixer/BeatFX/BP_BeatFxTapButton |
| BeatFXTimeKnob | Beat FX Time | knob | KnobBase | calls Console.AddBeatFXTime, Console.SetBeatFXTimeInterval, Console.Multi_SetBeatFxBpm, Console.SetBeatFxTime | DJM-900NXS2, DJM-A9, DJM-V10, Tribe Mixer | Mixer/BeatFX/BP_BeatFXTimeKnob |
| BeatFXToggleButton | Beat FX On/Off | toggle button | BaseToggleButton | calls Console.SetBeatFXToggleIntent, MidiManager.SendMidiEvent | DDJ-FLX4, DJM-900NXS2, DJM-A9, DJM-V10, Tribe Mixer | Mixer/BeatFX/BP_BeatFXToggleButton |
| BeatFXTypeKnob_A9 | Mobius/Triplet Roll/Roll/Trans/Triplet Filter/Fil… | stepped knob | BeatFXTypeKnob | calls Label.UpdateLabelText, Console.SetBeatFxType (in BeatFXTypeKnob) | DJM-A9 | Mixer/BeatFX/BP_BeatFXTypeKnob_A9 |
| BeatFXTypeKnob | Roll/Flanger/Trans/Echo | stepped knob | QuantizedKnob | calls Label.UpdateLabelText, Console.SetBeatFxType | Tribe Mixer | Mixer/BeatFX/BP_BeatFXTypeKnob |
| BeatFXTypeKnob_NXS2 | Helix/Roll/SlipRoll/Pitch/Phaser/Flanger/Filter/T… | stepped knob | BeatFXTypeKnob | calls Label.UpdateLabelText, Console.SetBeatFxType (in BeatFXTypeKnob) | DJM-900NXS2 | Mixer/BeatFX/BP_BeatFXTypeKnob_NXS2 |
| BeatFXTypeKnob_V10 | Pitch/Roll/Trans/Filter/Phaser/Flanger/Reverb/Hel… | stepped knob | BeatFXTypeKnob | calls Label.UpdateLabelText, Console.SetBeatFxType (in BeatFXTypeKnob) | DJM-V10 | Mixer/BeatFX/BP_BeatFXTypeKnob_V10 |
| BeatFxXpadButton | - | button | InputButton | calls Console.SetBeatFXEnabled, Console.HandleXPadButtonToggled, Console.SetBeatFXTimeInterval | DJM-900NXS2, DJM-V10 | Mixer/BeatFX/BP_BeatFxXpadButton |
| BeatFxXpadSliderA9 | Xpad | fader | SliderBase | calls Console.SetBeatFxTouchIntent, Console.SetBeatFxXpadEnabled, Console.SetBeatFxParameter; follows Console.OnActiveBeatFxChanged | DJM-A9 | Mixer/BeatFX/BP_BeatFxXpadSliderA9 |
| BeatFxXpadSlider | - | fader | SliderBase | calls Console.SetBeatFxXpadEnabled, Console.SetBeatFxTouchIntent, Console.SetBeatFxParameter; follows Console.OnActiveBeatFxChanged | DJM-V10 | Mixer/BeatFX/BP_BeatFxXpadSlider |
| BeatFXAssignButton | Beat FX Assign {Channel} (Master/Mic/Crossfader B… | button | BaseDeckControl | calls Console.SetBeatFXAssignButton | DJM-V10 | Mixer/Channel/BeatFXAssign/BP_BeatFXAssignButton |
| ChannelColorKnob | Color FX Level {Ch} | knob | ChannelKnobBase | calls Mixer.SetChannelColor; follows Console.OnColorFXCenterLockToggled | DDJ-FLX4, DJM-900NXS2, DJM-A9, Starter Mixer, Tribe Mixer | Mixer/Channel/Color/BP_ChannelColorKnob |
| ChannelCompKnob | Comp Level {Ch} | knob | ChannelKnobBase | calls Mixer.SetChannelComp | DJM-V10 | Mixer/Channel/Comp/BP_ChannelCompKnob |
| ChannelEQKnob | EQ {X} {Ch} (High/HighMid/Mid/LowMid/Low) | knob | ChannelKnobBase | calls Console.Set Channel EQ; follows Console.OnCalculateSmartTempos, Console.OnCrossfaderChanged | DDJ-FLX4, DJM-900NXS2, DJM-A9, DJM-V10, Starter Mixer, Tribe Mixer | Mixer/Channel/EQ/BP_ChannelEQKnob |
| ChannelFilterKnob | Filter Level {Ch} | knob | ChannelKnobBase | calls Console.SetChannelFilterLevel | DJM-V10 | Mixer/Channel/Filter/BP_ChannelFilterKnob |
| ChannelInputKnob | Channel {X} Input | stepped knob | QuantizedKnob | calls Mixer.SetChannelInput | DJM-V10 | Mixer/Channel/Input/BP_ChannelInputKnob |
| ChannelKnobBase | - | knob | MixerKnobBase | generic behaviour of its kind | - | Mixer/Channel/BP_ChannelKnobBase |
| ChannelSendKnob | Send Level {Ch} | knob | ChannelKnobBase | calls Console.SetChannelSendLevel | DJM-V10 | Mixer/Channel/Send/BP_ChannelSendKnob |
| ChannelTrimKnob | Trim {Ch} | knob | ChannelKnobBase | calls Mixer.SetChannelTrim; follows Video Call Manager.OnAudioOutputTypeChanged, Video Call Manager.OnCallEndedDelegate, Video Call Manager.OnVideoCallStartSuccessDelegate | DDJ-FLX4, DJM-900NXS2, DJM-A9, DJM-V10, Starter Mixer, Tribe Mixer | Mixer/Channel/Trim/BP_ChannelTrimKnob |
| ChannelVolumeSlider | Volume Fader {Ch} | fader | MixerSliderBase | calls Rig.broadcast OnControlReset, Console.SetChannelFader | DDJ-FLX4, DJM-900NXS2, DJM-A9, DJM-V10, Starter Mixer, Tribe Mixer | Mixer/Channel/Volume/BP_ChannelVolumeSlider |
| CrossfaderAssign | Crossfader Assign {Ch} | stepped slider | QuantizedSlider | calls Console.SetCrossfaderAssign | DJM-900NXS2, DJM-A9, DJM-V10, Tribe Mixer | Mixer/Channel/CrossfaderAssign/BP_CrossfaderAssign |
| EqCurveSwitch | EQ Curve | stepped slider | QuantizedSlider | calls Console.SetEqCurve | DJM-900NXS2, DJM-A9 | Mixer/Channel/EQ/BP_EqCurveSwitch |
| LoadButton | Load | button | InputButton | calls W_TrackOptions.LoadTrackToDeck, ActiveTrackList.OnLoadButtonClick | DDJ-FLX4 | Mixer/Channel/Load/BP_LoadButton |
| ColorFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | BaseDeckControl | calls Console.SetActiveFXButton, Console.DisableFX | DJM-900NXS2, DJM-A9, Tribe Mixer | Mixer/ColorFX/BP_ColorFXButton |
| ColorFXCenterLockSwitch | Color FX Center Lock | stepped slider | QuantizedSlider | calls Console.SetColorFXCenterLockEnabled | DJM-A9 | Mixer/ColorFX/BP_ColorFXCenterLockSwitch |
| ColorFXParameterKnob | Color FX Parameter | knob | MixerKnobBase | calls Console.SetColorFxParameter | DJM-900NXS2, DJM-A9 | Mixer/ColorFX/BP_ColorFxParameterKnob |
| SmartCFXButton | ColorFX | toggle button | BaseToggleButton | calls Mixer.SetActiveChannelFx, Console.SetSmartColorFx; follows Console.OnShiftChanged | DDJ-FLX4 | Mixer/ColorFX/BP_SmartCFXButton |
| ChFaderSelectButton | Channel Fader Select {Setting} (Long/Medium/Short) | button | InputButton | calls Console.SetChannelFaderCurve | DJM-V10 | Mixer/Crossfader/BP_ChFaderSelectButton |
| ChannelFaderCurveSwitch | Channel Fader Curve | stepped slider | QuantizedSlider | calls Console.SetChannelFaderCurve | DJM-900NXS2, DJM-A9, Tribe Mixer | Mixer/Crossfader/BP_ChannelFaderCurveSwitch |
| CrossfaderCurveSwitch | Crossfader Curve | stepped slider | QuantizedSlider | calls Console.SetCrossfaderCurve | DJM-900NXS2, DJM-A9, Tribe Mixer | Mixer/Crossfader/BP_CrossfaderCurveSwitch |
| CrossfaderSelectButton | Crossfader Curve {Setting} (Long/Medium/Short) | button | InputButton | calls Console.SetCrossfaderCurve | DJM-V10 | Mixer/Crossfader/BP_CrossfaderSelectButton |
| Crossfader | Crossfader | fader | MixerSliderBase | calls Console.Set Crossfader | DDJ-FLX4, DJM-900NXS2, DJM-A9, DJM-V10, Starter Mixer, Tribe Mixer | Mixer/Crossfader/BP_Crossfader |
| CurveSettingsButton | Curve Settings | button | InputButton | calls Console.ToggleBeatFxView | DJM-V10 | Mixer/Crossfader/BP_CurveSettingsButton |
| CurveSettingsExitButton | Exit Curve Settings | button | InputButton | calls Console.ToggleBeatFxView | DJM-V10 | Mixer/Crossfader/BP_CurveSettingsExitButton |
| SmartFaderButton | Smart Fader | toggle button | BaseToggleButton | calls Console.SetSmartFaderEnabled | DDJ-FLX4 | Mixer/Crossfader/BP_SmartFaderButton |
| ChannelCueButton | Channel {Ch} Cue | toggle button | BaseToggleButton | calls Console.SetChannelCue | DDJ-FLX4, DJM-900NXS2, DJM-A9, DJM-V10, Starter Mixer, Tribe Mixer | Mixer/Cueing/BP_ChannelCueButton |
| HeadphoneLevelKnob | Headphone Level | knob | MixerKnobBase | calls Mixer.SetHeadphonesLevel | DDJ-FLX4, DJM-900NXS2, DJM-A9, DJM-V10, Tribe Mixer | Mixer/Cueing/BP_HeadphoneLevelKnob |
| HeadphoneMixKnob | Headphone Mix | knob | MixerKnobBase | calls Mixer.SetHeadphonesMix | DDJ-FLX4, DJM-900NXS2, DJM-A9, DJM-V10, Tribe Mixer | Mixer/Cueing/BP_HeadphoneMixKnob |
| HeadphonePreEQButton | Headphone Pre EQ | toggle button | BaseToggleButton | calls Mixer.SetHeadphonesPreEq | DJM-V10 | Mixer/Cueing/BP_HeadphonePreEQButton |
| MasterCueButton | Master Cue | toggle button | BaseToggleButton | calls Mixer.SetMasterCue | DDJ-FLX4, DJM-900NXS2, DJM-A9, DJM-V10, Starter Mixer, Tribe Mixer | Mixer/Cueing/BP_MasterCueButton |
| FilterButton | High Pass Filter/Low Pass Filter | button | BaseDeckControl | calls Console.SetActiveFilterButton | DJM-V10 | Mixer/Filter/BP_FilterButton |
| FilterResonanceKnob | Filter Resonance Knob | knob | MixerKnobBase | calls Console.SetChannelFilterResonance | DJM-V10 | Mixer/Filter/BP_FilterResonanceKnob |
| MasterFilterKnob | Master Filter Knob | knob | MixerKnobBase | calls Console.SetMasterFilterLevel | DJM-V10 | Mixer/Filter/BP_MasterFilterKnob |
| IsolatorEQKnob | Isolator EQ {EQ Band} (High/HighMid/Mid/LowMid/Lo… | knob | MixerKnobBase | calls Mixer.SetMasterIsolatorEq | DJM-V10 | Mixer/Isolator/BP_IsolatorEQKnob |
| IsolatorOnButton | Isolator Toggle | toggle button | BaseToggleButton | calls Mixer.SetMasterIsolatorEqEnabled | DJM-V10 | Mixer/Isolator/BP_IsolatorOnButton |
| MasterBalanceKnob | Master Balance | knob | MixerKnobBase | calls Mixer.SetMasterBalance | DJM-900NXS2, Tribe Mixer | Mixer/Master/BP_MasterBalanceKnob |
| MasterLevelKnob | Master Level | knob | MixerKnobBase | calls Mixer.SetMasterLevel; follows Video Call Manager.OnAudioOutputTypeChanged, Video Call Manager.OnCallEndedDelegate, Video Call Manager.OnVideoCallStartSuccessDelegate | DDJ-FLX4, DJM-900NXS2, DJM-A9, DJM-V10, Starter Mixer, Tribe Mixer | Mixer/Master/BP_MasterLevelKnob |
| MicEQKnob | Microphone EQ {X} | knob | MixerKnobBase | calls Console.SetMicEQ | DJM-900NXS2, DJM-A9, DJM-V10, Tribe Mixer | Mixer/Microphone/BP_MicEQKnob |
| MicFXButton | Mic FX {FX} | toggle button | BaseToggleButton | calls Console.SetActiveMicFX; follows Console.OnMicFxChanged | DJM-A9 | Mixer/Microphone/BP_MicFXButton |
| MicFXParameterKnob | Mic FX Parameter | knob | MixerKnobBase | calls Mixer.SetMicFxParameter | DJM-A9 | Mixer/Microphone/BP_MicFXParameterKnob |
| MicLevelKnob | Microphone Level | knob | MixerKnobBase | calls Console.SetMicLevel | DDJ-FLX4, DJM-900NXS2, DJM-A9, DJM-V10, Tribe Mixer | Mixer/Microphone/BP_MicLevelKnob |
| MicOnButton | Microphone On/Off | toggle button | BaseToggleButton | calls Console.SetMicMode | DJM-A9 | Mixer/Microphone/BP_MicOnButton |
| MicReverbButton | Mic Reverb | toggle button | BaseToggleButton | calls Mixer.SetMicReverbEnabled | DJM-A9 | Mixer/Microphone/BP_MicReverbButton |
| MicReverbParameterKnob | Mic Reverb Parameter | knob | MixerKnobBase | calls Mixer.SetMicReverbParameter | DJM-A9 | Mixer/Microphone/BP_MicReverbParameterKnob |
| MicSwitch | Microphone On/Off/Talkover | stepped slider | QuantizedSlider | calls Console.SetMicMode | DJM-900NXS2, DJM-V10, Tribe Mixer | Mixer/Microphone/BP_MicSwitch |
| MicTalkoverButton | Microphone Talkover | toggle button | BaseToggleButton | calls Console.SetMicTalkoverEnabled | DJM-A9 | Mixer/Microphone/BP_MicTalkoverButton |
| RotaryKnob | Rotary Knob | knob | KnobBase | calls OwningPawn.SetInputMode, OwningPawn.ShowDesktopMiniMenu, MiniMenu.ShowMusicPanel, TrackBrowser.RotaryClick, TrackBrowser.RotaryNext, TrackBrowser.RotaryPrev | DDJ-FLX4 | Mixer/Screen/BP_RotaryKnob |
| SendFXButton | Reverb/Long Delay/Short Delay/Filter/Crush/Noise/… | button | ColorFXButton | calls Console.SetActiveFXButton, Console.DisableFX (in ColorFXButton) | DJM-V10 | Mixer/SendFX/BP_SendFXButton |
| SendMasterMixButton | Send Master Mix Toggle | toggle button | BaseToggleButton | calls Console.SetSendFXMasterMixEnabled | DJM-V10 | Mixer/SendFX/BP_SendMasterMixButton |
| SendMasterMixKnob | Send Master Mix Knob | knob | MixerKnobBase | calls Console.SetSendFXMasterMixLevel | DJM-V10 | Mixer/SendFX/BP_SendMasterMixKnob |
| SendSizeFeedbackKnob | Send Size Feedback Knob | knob | MixerKnobBase | calls Console.SetSendFXSize | DJM-V10 | Mixer/SendFX/BP_SendSizeFeedbackKnob |
| SendTimeKnob | Send Time Knob | knob | MixerKnobBase | calls Console.SetSendFXTime | DJM-V10 | Mixer/SendFX/BP_SendTimeKnob |
| SendToneKnob | Send Tone Knob | knob | MixerKnobBase | calls Console.SetSendFXTone | DJM-V10 | Mixer/SendFX/BP_SendToneKnob |
| HeightHandle | - | fader | SliderBase | calls DefaultSceneRoot.K2_GetComponentLocation, self.broadcast OnHeightChanged, DefaultSceneRoot.K2_SetWorldLocation; follows TribeGameState.OnLocalPawnReady, TribeGameState.OnNewEnvironmentLoaded | - | Table/BP_HeightHandle |
| SpatialAnchorHandle | - | handle | BaseDeckControl | calls LocalPawn.SetAttachMode, self.broadcast OnAnchorTransformChanged, AnchorManager.SetAnchorTransform, AnchorManager.DeleteAnchor, LocalPawn.RefreshDJAttachMode, LocalPawn.SetHeightOffset ...; follows AnchorManager.OnSavedAnchorsLoaded, Tribe_Game_Instance.OnVROriginRecentered | - | Table/BP_SpatialAnchorHandle |

## Reading further

- `claudedocs/deck_reference.md`: every function of the deck engine (`BP_Deck`), the mixer engine (`BP_Console`), their shared base (`BP_MixerChannelDevice`), the control base (`BP_BaseDeckControl`) and the rig (`BP_Rig`), with parameters and what each calls.
- `D:/TribeUE/tribe_assets/catalog/code/`: all 280 equipment Blueprints as pseudo-code (one `.txt` per asset, `scripts/kismet_print.py` format). `deck_catalog.json` next to it has this catalog's data.
- Rebuild: dump the hook's `TribeXR.usmap` (tribemod/usmap_now), augment it with `uasset_tool augment`, `uasset_tool dump` the Equipment folder, then run `scripts/deck_catalog.py`. NOTES.md has the commands.

## Not covered here

- How the gear looks: the meshes and textures are exported and previewed in `claudedocs/gear_models.md`. This catalog names each model's skeletal mesh and skeleton.
- What the native code does under the Blueprints (the audio engine, the equipment mesh's table lookup, the networking): `claudedocs/native_reference.md`, with the decompiled C++ in `D:/TribeUE/tribe_native/classes/`. This catalog shows the calls into it.
- The FLX4 deck lists deck 1 (`DT_DDJ-FLX4_ControlInfo_1`); deck 2 reads `_2`.
