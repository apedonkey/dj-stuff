# Tribe XR equipment engines: function reference

Every function of the classes that run Tribe's gear, from its Blueprints (build 2304). `[Net...]` marks replicated calls, `[Event]` engine events. "Calls" lists the other functions each one calls (first 8). Pseudo-code for all of them: `D:/TribeUE/tribe_assets/catalog/code/`. Made by `scripts/deck_catalog.py`.

## BP_Deck_C: the deck engine: every player model derives from it

Parent `BP_MixerChannelDevice_C`. 329 functions; variables: `UberGraphFrame`, `Marker_RadialFX`, `BeatgridEditor`, `Screen`, `bReadyToPlay`, `CurrentPlayerState`, `bPlaybackActivated`, `bKeySyncSlave`, `bTempoLocked`, `CurrentPitch`, `AudioPlayer`, `ClientPlaybackSyncToleranceMs`, `Server_NetSyncPacket`, `Server_CueTimestamp`, `bCuePreviewActive`, `OnDeckPlay`, `OnDeckPause`, `Server_LoopOutTimestamp`, `bLoopActivated`, `bLastTickPlaying`, `bLastTIckLooping`, `bReverse`, `OnHotCueModeChanged`, `OnTrackChanged`, `bVinylMode`, `IsJogging`, `OnTrackOpened`, `OnJogModeChanged`, `Controls`, `PlayButton`, `CueButton`, `CurrentTrack`, `CurrentTrackFileName`, `bMasterTempo`, `bQuantized`, `bSlip`, `TouchBrake`, `OnPlayerMemoryLoaded`, `PitchSlider`, `FaderToggleThreshold`, `SyncButton`, `KeySyncButton`, `SyncMasterButton`, `bAutoCueFirstBeat`, `HotCues`, `PendingTrackFilename`, `TrackRequestClient`, `StateRequestPawn`, `ActiveTransferManager`, `BeatgridBpm`, `BeatgridStartMs`, `LastTickPlayMs`, `OpenCheckTimer`, `bUpdateRepLock`, `RepPitchDelta`, `TribeGameInstance`, `TribeGameState`, `OnCuePreviewCleared`, `LastServerUpdateTimeSeconds`, `NetLockTimestamp`, `PlayTimestamp`, `OnDeckDirectionChanged`, `ActiveTransfer`, `OnReplicatedTimeUpdated`, `ActiveProgressBar`, `StreamingTrackReportHandle`, `ActiveStreamingClient`, `bQueuedOpen`, `MaxPitchRangePercentages`, `ScreenClass`, `HotCueMode`, `OnSlipModeChanged`, `OnIsLoopingChanged`, `OnLoopInSet`, `OnMasterTrackAnalyzed`, `OnKeySyncChanged`, `Jogwheel`, `DefaultBeatJumpInterval`, `OnTempoUnlocked`, `OnTrackUnloaded`, `OnAlbumArtRequested`, `OnStreamTrackBeginDownload`, `DefaultSavedControls`, `K_ConfigSectionSavedControls`, `K_DeckSaveGame`, `CurrentBeatJumpInterval`, `DeviceSaveGame`, `SavedTrackInfo`, `PendingFreeSoundCloudPlaylists`, `OnBeatGridUpdated`, `bLockBeatgrid`, `LoopAdjustmentMode`, `OnEquipmentSaveLoaded`, `bLoadedAnalysis`, `TrackLoadPawn`, `OnHotOrMemoryCueChanged`, `MemoryCueTimestamps`, `MemoryCueLengthTimestamps`, `MemoryCueIsSet`, `ActivePadSelectButton`, `CachedPadSelectButton`, `PerformancePadButtons`, `AudioPlayerParams`, `OnPadFloatParameterChanged`, `OnPadByteParameterChanged`, `ActivePadMode`, `bFaderStartReady`, `OnBeatLoopSet`, `OnPerformancePadInteraction`, `CurrentKeyShift`, `OnKeyShiftChanged`, `SamplePlayer`, `OnActivePadModeChanged`, `HotCueTimestamps`, `HotCueLengthTimestamps`, `HotCueIsSet`, `HotCueImportedColors`, `ShiftButton`, `bSearchButtonPressed`, `AllowedBeatJumpIntervals`, `ActiveScreenMode`, `OnScreenModeChanged`, `ScreenButtonBank`, `OnScreenButtonBankChanged`, `InstantDoubleDeck`, `OnCurrentTrackEnded`, `bSlipReverseActive`, `bSlipEnabledBySlipReverse`.

| Function | Kind | Calls |
|---|---|---|
| AbsoluteToNetSyncMs(AbsoluteMs: Double, RepMaster: Object(BP_Deck_C), out NetSyncMs: Double) | - | EqualEqual_ObjectObject, GetPositionToReplicate, Subtract_DoubleDouble |
| AddProgressBar(AutoDisplayTransfer: Object(FileTransfer), AutoDisplayStreamTrack: Object(TribeStreamTrack), out BarWidget: Object(BP_TransferProgressBar_C)) | - | IsValid, K2_DestroyActor, GetDownloadBarTransform, BeginDeferredActorSpawnFromClass, SetObjectPropertyByName, FinishSpawningActor, K2_AttachToActor |
| AudioPlayerOpenTrack(Track: Object(TribeTrack)) | - | K2_IsValidTimerHandle, IsAudioInMemoryReady, GetAudioInMemoryBP, IsCopyright, GetFilePath, GetAudioPlayer, OpenAudioInMemory, K2_SetTimerDelegate |
| AudioPlayerReleaseTrack() | - | K2_IsValidTimerHandle, GetTrackLibrary, GetBlankTrackFilePath, GetAudioPlayer, Open, K2_SetTimerDelegate |
| AutoCueFirstBeat() | - | HasRepAuthority, GetAudioPlayer, GetCueAsTime, EqualEqual_DoubleDouble, BooleanAND, SetCueToFirstBeat |
| AwaitStreamTrackLogin(StreamTrack: Object(TribeStreamTrack)) | - | GetStreamingClientName, NotEqual_NameName, Conv_NameToString, Concat_StrStr, PrintString, GetTrackManager, GetTrackLibrary, FindStreamingClient |
| BeginSlipReverse() | - | GetSlip, SetReversePlayback, SetSlip |
| CanBeRepMaster(out bCanBeRepMaster: Bool) | - | GetAudioPlayer, IsLooping, GetLoopLengthMs, GetRemainingTimeMs, LessEqual_DoubleDouble, GreaterEqual_DoubleDouble, BooleanNAND, GetIsPlaying |
| CancelPendingTransfer() | - | - |
| CheckTrackOpened() | - | GetAudioPlayer, CheckForPlayerEvent |
| CleanupBufferTrack(BufferTrack: Object(TribeBufferTrack)) | - | - |
| CleanupStreamTrack(StreamTrack: Object(TribeStreamTrack)) | - | - |
| ClearAllHotCues() | - | GetAudioPlayer, ClearAllHotCues |
| ClearAllMemoryCues() | - | GetAudioPlayer, ClearAllMemoryCues |
| ClearControlEventBindings() | - | IsValid, ClearEventBindings |
| ClearCuePreview() | - | - |
| ClearEventBindings() | - | - |
| ClearHotCue(Index: Int, bSaveMemory: Bool) | - | GetAudioPlayer, ClearHotCue, IsValid, Map_Remove, SavePlayerMemory |
| ClearMemoryCue(out IndexCleared: Int) | - | GetAudioPlayer, ClearMemoryCue, GreaterEqual_IntInt, IsValid, Map_Remove, SavePlayerMemory |
| ClearMemoryCueByIndex(IndexToClear: Int) | - | GetAudioPlayer, ClearMemoryCueByIndex |
| Client_DestroyMarkers() | - | - |
| ClientInitDisplay() | - | Get Screen, SetScreenButtonMode, Set Beat Jump Indicator, SetScreenButtonBank, SetKeyShiftInterval |
| CutLoop() | - | GetAudioPlayer, CutLoop, UpdateReplicatedLoopOutPosition |
| CycleTempoRange() | - | AdvancePitchFaderIndex |
| DecrementKeyShift() | - | Greater_IntInt, FlushNetDormancy, Subtract_IntInt, MarkPropertyDirtyFromRepIndex, OnRep_CurrentKeyShift |
| DestroyControls() | - | Array_Length, Less_IntInt, Array_Get, K2_DestroyActor, Add_IntInt |
| DoubleBeatgridBpm() | - | IsValid, GetSuperpoweredMaxBpm, GetBpm, Multiply_DoubleDouble, LessEqual_DoubleDouble, SetBpm |
| EndSlipReverse(bContinueReverse: Bool) | - | SetReversePlayback, GetAudioPlayer, GetSlipCondition, EqualEqual_ByteByte, GetIsPlaying, Not_PreBool, BooleanOR, BooleanAND |
| ExitLoop() | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bLooping, HasAuthority, RestartRepInterval, SetTimeRepLock |
| ExtendLoop() | - | GetAudioPlayer, ExtendLoop, UpdateReplicatedLoopOutPosition |
| Get Adjusted Server Net Sync Packet(out AdjustedServerTimestamp: Struct(F_DeckNetPacket)) | - | GetSecondsSinceLastServerUpdate, FMax, GetServerWorldTimeSeconds, Subtract_DoubleDouble |
| Get Screen(out Screen: Object(BP_DeckScreenBase_C)) | - | - |
| GetAudioDevice(out AudioDevice: Object(SuperPoweredChannelDevice)) | - | - |
| GetAudioPlayer(out AudioPlayer: Object(SuperPoweredAudioPlayer)) | - | - |
| GetBeatgridEditor(out BeatgridEditor: Object(BP_BeatgridEditor_C)) | - | - |
| GetBeatJumpValue(out BeatJumpInterval: Enum(EBeatFxTimeInterval)) | - | - |
| GetControls(out Controls: Array<Object(BP_BaseDeckControl_C)>) | - | - |
| GetCurrentBeatJumpLength(out NumBeats: Double) | - | BeatFxIntervalToFloat |
| GetCurrentTrack(out CurrentTrack: Object(TribeTrack)) | - | - |
| GetCurrentTrackDisplayName() -> Str | - | IsValid, GetTrackName, GetTrackNameFromFile |
| GetDeckLive(out bDeckLive: Bool) | - | NotEqual_ObjectObject, GetChannelFader, Greater_DoubleDouble, GetIsPlaying, BooleanAND |
| GetDefaultSaveControlNames(out ControlNames: Set<Name>) | - | - |
| GetDisplaySyncInfo(out bIsSynced: Bool) | - | HasAuthority, IsSyncSlave, NotEqual_ByteByte |
| GetDisplayTempo(out Tempo: Double, out Bpm: Double) | - | HasAuthority, GetBpm, GetTempo, Subtract_DoubleDouble, Multiply_DoubleDouble |
| GetDownloadBarTransform(out Transform: Struct(Transform)) | - | - |
| GetHotCueColor(Index: Int, out LinearColor: Struct(LinearColor), out Hue: Double) | - | Array_Get, EqualEqual_LinearColorLinearColor, GetAudioPlayer, GetHotCueAsTime, Greater_DoubleDouble, IsPioneerEquipment, BooleanAND, RGBToHSV |
| GetHotCueMode(GrabbingHand: Object(TribeControllers_C), out HotCueMode: Enum(E_HotCueMode)) | - | IsShiftActive, IsValid, IsShiftEnabled |
| GetHotCueTimestamp(Index: Int, out bHotCueSet: Bool, out CueMs: Double, out LengthMs: Double, out IsLoop: Bool) | - | GetAudioPlayer, GetHotCueAsTime, Greater_DoubleDouble |
| GetIsPlaying(out isPlaying: Bool) | - | IsPlaying |
| GetKeySync(out bKeySync: Bool) | - | - |
| GetLoadedTrack(out LoadedTrack: Object(TribeTrack)) | - | - |
| GetLoopAdjustmentMode(out LoopAdjustmentMode: Enum(ELoopAdjustMode)) | - | - |
| GetMemoryCueTimestamp(Index: Int, out bMemoryCueSet: Bool, out CueMs: Double, out LengthMs: Double, out IsLoop: Bool) | - | GetAudioPlayer, GetMemoryCueAsTime, Greater_DoubleDouble |
| GetPitchLerpFromDelta(DeltaMs: Double, out PitchLerp: Double) | - | NearlyEqual_FloatFloat, SignOfFloat, GetAudioPlayer, GetReverse, Divide_DoubleDouble, Square, Multiply_DoubleDouble, Add_DoubleDouble |
| GetPlaybackMs(out TrackMs: Double) | - | GetAudioPlayer, GetPosition |
| GetPlaybackRate(out PlaybackRate: Double) | - | GetAudioPlayer, GetReverse, Multiply_DoubleDouble |
| GetPlaybackSeconds(out Current Track Time: Double) | - | GetAudioPlayer, GetDisplayTimeSeconds |
| GetPositionFraction(out Position: Double) | - | GetPositionAsFraction |
| GetPositionInLoop(PositionMs: Double, out LoopedMs: Double) | - | GetAudioPlayer, GetLoopLengthMs, GreaterEqual_DoubleDouble, GetLoopInMs, Less_DoubleDouble, GetLoopOutMs, Subtract_DoubleDouble, Percent_FloatFloat |
| GetPositionReplicateRate(out RateSeconds: Double) | - | GetAudioPlayer, IsScratching, BooleanOR, GetConsole, GetReplicationSyncMaster, EqualEqual_ObjectObject |
| GetPositionToReplicate(out ReplicateMs: Double) | - | GetAudioPlayer, GetDisplayPosition |
| GetRadialFXTransform(out FXTransform: Struct(Transform)) | - | GetRelativeTransform |
| GetRemainingTimeMs(out RemainingMs: Double) | - | GetDuration, GetDisplayPosition, Subtract_DoubleDouble |
| GetReplicatedPosition(out ReplicatedMs: Double) | - | NetSyncToAbsoluteMs |
| GetSecondsSinceLastServerUpdate(out SecondsSinceUpdate: Double) | - | GetTimeSeconds, Subtract_DoubleDouble |
| GetServerNetSyncPacket(out NetSyncPacket: Struct(F_DeckNetPacket)) | - | - |
| GetSlip(out bSlip: Bool) | - | - |
| GetTrackDurationMs(out DurationMs: Double) | - | GetDuration |
| GetVarReplicateConditionOverrides(out OutClass: Class(Object), out OutOverrides: Array<Struct(RepConditionOverride)>) | Event | GetVarReplicateConditionOverrides, Array_Append, GetObjectClass |
| HalveBeatgridBpm() | - | IsValid, GetSuperpoweredMinBpm, GetBpm, Multiply_DoubleDouble, GreaterEqual_DoubleDouble, SetBpm |
| HandleBeatportLoginResult(LoginState: Enum(EStreamingLoginState), EventMessage: Str) | - | NotEqual_ByteByte, GetTrackManager, OpenCurrentTrack |
| HandleDropboxLoginResult(bSuccess: Bool) | - | GetTrackLibrary, GetDropboxClientName, FindStreamingClient, OpenCurrentTrack |
| HandleDropboxPawnReady(LocalPlayer: Object(TribePawnBP_C)) | - | RequestDropboxSharedUrlFromServer |
| HandleDropboxSharedUrl(DropboxTrack: Object(TribeStreamTrack), bSuccess: Bool, SharedUrl: Str, ClientData: Object(Object)) | - | GetFileName, EqualEqual_StrStr, Multi_OpenDropboxSharedTrack |
| HandleHotCuesLoaded() | - | Subtract_IntInt, LessEqual_IntInt, GetHotCueTimestamp, HasAuthority, Multi_SetHotCue, Add_IntInt, WasTrackLoadedLocally, GetPlayerPawn |
| HandleLoopJump(NumBeats: Double, bBackwards: Bool) | - | Multiply_DoubleDouble, GetAudioPlayer, GetLoopInMs, GetBeatDistanceAsTime, Add_DoubleDouble, GetLoopLengthMs, GreaterEqual_DoubleDouble, GetIsPlaying |
| HandleMemoryCuesLoaded() | - | Subtract_IntInt, LessEqual_IntInt, GetMemoryCueTimestamp, HasAuthority, Multi_SetMemoryCue, Add_IntInt, WasTrackLoadedLocally, GetPlayerPawn |
| HandleMixerDevicesUpdated() | - | - |
| HandleRepMasterChanged(RepMaster: Object(BP_Deck_C)) | - | - |
| HandleSoundCloudFreePlaylistsQuery(QueryState: Enum(ETribeStreamingQueryState), StreamFolder: Object(TribeStreamFolder)) | - | NotEqual_ByteByte, Subtract_IntInt, LessEqual_IntInt, OpenCurrentTrack |
| HandleSoundCloudLoginResult(bSuccess: Bool, ref LoginUser: Struct(SoundCloudLogin)) | - | GetTrackLibrary, GetSoundCloudClientName, FindStreamingClient, OpenCurrentTrack |
| HandleTidalLoginResult(bSuccess: Bool, bSubscriptionActive: Bool, bHasDJExtension: Bool) | - | GetTrackLibrary, GetTidalClientName, FindStreamingClient, BooleanAND, OpenCurrentTrack, UnloadTrack |
| HandleTrackBeatgridChanged() | - | HasAuthority, UpdateBeatGridToCurrentTrack, GetBpm, GetBeatgridStartMs, EqualEqual_DoubleDouble, BooleanAND, Multi_SetBeatGrid, Server_SetDeckBeatGrid |
| HandleTrackLoadPawnDestroyed(DestroyedActor: Object(Actor)) | - | - |
| HandleTrackOpened() | - | HasAuthority, IsValid, RequestPlayerDeckState, AutoCueFirstBeat, UpdateReplicatedState, RefreshReplicationMaster, GetReportPositionRate, Greater_DoubleDouble |
| HandleVideoCallStarted(ChannelName: Str) | - | - |
| HasPositionJumpedRecently(LastPositionMs: Double, DeltaTime: Double, out bJumped: Bool) | - | GetAudioPlayer, IsScratching, IsPlaying, BooleanOR, GetPosition, Multiply_DoubleDouble, NearlyEqual_FloatFloat, Not_PreBool |
| HasRepAuthority(out bRepAuthority: Bool) | - | HasAuthority |
| IncrementKeyShift() | - | Less_IntInt, FlushNetDormancy, Add_IntInt, MarkPropertyDirtyFromRepIndex, OnRep_CurrentKeyShift |
| InitEventBindings() | - | - |
| Initialize Audio Player() | - | EqualEqual_ObjectObject, CreateAudioPlayer, GetSamplePlayer, Get Screen, InitializeScreen, GetBeatgridEditor, InitializeBeatgridEditor, RefreshMixerConnect |
| IsAtCue(out IsAtCue: Bool) | - | GetAudioPlayer, IsAtCue |
| IsAwaitingClientState(out bAwaitingClientState: Bool) | - | NotEqual_ObjectObject, BooleanOR |
| IsCuePreviewActive(out CuePreviewActive: Bool) | - | - |
| IsLooping(out Looping: Bool) | - | - |
| IsMixedToCueOnly(out MixedToCueOnly: Bool) | - | GetMixer, GetChannelFader, GetChannelCue, LessEqual_DoubleDouble, BooleanAND |
| IsNetSyncActive(out bRepNetSync: Bool) | - | GetOnlineSessionState, EqualEqual_ByteByte, Array_Length, Greater_IntInt, BooleanOR |
| IsNetSyncPacketValid(ref NetSyncPacket: Struct(F_DeckNetPacket), out bValid: Bool) | - | EqualEqual_ObjectObject, ShouldUseServerPosition |
| IsPlaying(out bPlayingAudio: Bool) | - | - |
| IsSynced(out bSynced: Bool) | - | HasAuthority, GetAudioPlayer, IsSyncSlave |
| IsTrackOpened(out bTrackOpen: Bool) | - | EqualEqual_ByteByte, NotEqual_ObjectObject, BooleanAND |
| IsTrackTransferActive(out bTransferActive: Bool) | - | NotEqual_ObjectObject |
| IsVinylMode(out bVinylMode: Bool) | - | - |
| JogStart(JogGrabStatus: Enum(E_JogWheelGrabStatus), WaveformJogStatus: Enum(E_WaveformJogStatus)) | - | EqualEqual_ByteByte, BooleanOR, GetAudioPlayer, JogBegin, IsSyncMaster, GetConsole, AutoSwitchSyncMaster, IsSynced |
| JogStop(Decelerate: Double) | - | GetAudioPlayer, JogEnd |
| JogTick(DeltaTime: Double, RotationDelta: Double, MaxBendPercent: Double, bSearch: Bool) | - | NotEqual_DoubleDouble, JogStop, Divide_DoubleDouble, Multiply_DoubleDouble, GetPlaybackMs, Add_DoubleDouble, SetPlaybackMs, GetAudioPlayer |
| JumpLoop(bWaitForBeat: Bool, LoopInPosition: Double) | - | GetAudioPlayer, LoopJump, HasAuthority, RestartRepInterval, SetTimeRepLock |
| LoadDeviceState(SaveDirectory: Str, SaveSetting: Enum(E_DeviceSaveCofiguration)) | - | - |
| LoadPlayerMemory() | - | Map_Keys, Array_Length, Less_IntInt, Array_Get, Map_Find, SetHotCueFromTimestamp, RGBToHSV, MultiplyMultiply_FloatFloat |
| LoadTrack(Track: Object(TribeTrack), LoadingPawn: Object(TribePawnBP_C)) | - | - |
| MakeDeckStatePacket(out DeckStatePacket: Struct(F_DeckStatePacket)) | - | GetIsPlaying, GetAudioPlayer, IsLooping, GetCueAsTime, GetLoopOutMs, GetReverse |
| MakeNetSyncPacket(Timestamp: Double, out NetSyncPacket: Struct(F_DeckNetPacket)) | - | GetPositionToReplicate, GetConsole, GetReplicationSyncMaster, EqualEqual_ObjectObject, AbsoluteToNetSyncMs |
| MakeTrackSaveState(out TribeTrackSaveInfo: Struct(TribeTrackSaveInfo)) | - | GetAudioPlayer, GetLoopOutMs, GetCueAsTime, IsValid, GetPlaybackMs |
| Multi_BeatJump(Pawn: Object(TribePawnBP_C), bBackwards: Bool, NumBeats: Double, bWaitForBeat: Bool) | NetMulticast | - |
| Multi_ClearHotCue(Index: Int) | NetMulticast | - |
| Multi_ClearMemoryCue(Index: Int) | NetMulticast | - |
| Multi_JumpLoop(Pawn: Object(TribePawnBP_C), bWaitForBeat: Bool, LoopInPosition: Double) | NetMulticast | - |
| Multi_OpenDropboxSharedTrack(FileName: Str, SharedUrl: Str, LoadingPawn: Object(TribePawnBP_C)) | NetMulticast | - |
| Multi_OpenStreamTrackByName(FileName: Str, StreamingClient: Name, LoadingPawn: Object(TribePawnBP_C)) | NetMulticast | - |
| Multi_OpenTrackByName(FileName: Str, LoadingPawn: Object(TribePawnBP_C)) | NetMulticast | - |
| Multi_PrepareInstantDouble(InstantDoubleDeck: Object(BP_Deck_C)) | NetMulticast | - |
| Multi_ReturnToLoop(Pawn: Object(TribePawnBP_C), TargetPositionMs: Double, ServerTimeSeconds: Double, PlaybackRate: Double) | NetMulticast | - |
| Multi_SeekToHotCue(Index: Int, AndStop: Bool, bQuantizeJumpImmediately: Bool) | NetMulticast | - |
| Multi_SeekToMemoryCue(bForwards: Bool, AndStop: Bool) | NetMulticast | - |
| Multi_SetBeatGrid(BeatgridBpm: Double, BeatgridStartMs: Double) | NetMulticast | - |
| Multi_SetCuePosition(CueMs: Double) | NetMulticast | - |
| Multi_SetCurrentPitch(NewPitch: Double) | NetMulticast | - |
| Multi_SetHotCue(Index: Int, CueTimestamp: Double, LengthTimestamp: Double) | NetMulticast | - |
| Multi_SetLoopInPosition(LoopInMs: Double) | NetMulticast | - |
| Multi_SetLoopOutPosition(LoopOutMs: Double) | NetMulticast | - |
| Multi_SetMemoryCue(Index: Int, CueTimestamp: Double, LengthTimestamp: Double) | NetMulticast | - |
| Multi_SetPlaybackMs(PositionMs: Double) | NetMulticast | - |
| Multi_SetPositionFromFraction(PlaybackFraction: Double) | NetMulticast | - |
| Multi_SetTouchBrake(TouchBrake: Double) | NetMulticast | - |
| Multi_StartPlay(ref NetSyncPacket: Struct(F_DeckNetPacket)) | NetMulticast | - |
| Multi_StopAtCue(WorldTime: Double) | NetMulticast | - |
| Multi_StopPlay(ref NetSyncPacket: Struct(F_DeckNetPacket)) | NetMulticast | - |
| Multi_UnloadTrackForTransfer(RequestingPlayer: Object(TribePlayerControllerBP_C)) | NetMulticast | - |
| Multi_UpdateNetSyncMs_Reliable(ref NetSyncPacket: Struct(F_DeckNetPacket)) | NetMulticast | - |
| Multi_UpdateNetSyncMs_Unreliable(ref NetSyncPacket: Struct(F_DeckNetPacket)) | NetMulticast | - |
| Needle Set Position(PlaybackFraction: Double) | - | FMin, SetPositionFromFraction |
| NetSyncToAbsoluteMs(bAddPlayDelta: Bool, NetSyncPacket: Struct(F_DeckNetPacket), out ReplicatedMs: Double) | - | GetServerWorldTimeSeconds, NotEqual_ObjectObject, GetAudioPlayer, Subtract_DoubleDouble, TimeToPositionDelta, FMax, GetPositionToReplicate, GetLoopWrappedPositionMs |
| NextBeatJumpInterval() | - | Array_Find, Array_Length, Subtract_IntInt, Less_IntInt, FlushNetDormancy, Add_IntInt, Array_Get, MarkPropertyDirtyFromRepIndex |
| OnActivePadModeChanged__DelegateSignature(NewPadMode: Enum(E_PerformancePadMode), Deck: Object(BP_Deck_C)) | - | - |
| OnAlbumArtRequested__DelegateSignature(Deck: Object(BP_Deck_C)) | - | - |
| OnAndroidBackgrounded() | - | - |
| OnAndroidForegrounded() | - | - |
| OnBeatGridChanged() | - | - |
| OnBeatGridUpdated__DelegateSignature(Bpm: Double, StartMs: Double) | - | - |
| OnBeatLoopSet__DelegateSignature(NumBeats: Double) | - | - |
| OnBufferTrackAudioChanged(BufferTrack: Object(TribeBufferTrack)) | - | EqualEqual_ObjectObject, IsAudioInMemoryReady, OpenTrack, GetFileName, Concat_StrStr, PrintString, UnloadTrack |
| OnChannelFadeChanged(Channel: Int, Level: Double, bShifted: Bool) | - | - |
| OnChannelMixerCueToggled(Channel: Int, bEnabled: Bool) | - | - |
| OnColoredHotCuesToggles() | - | - |
| OnConsoleChanged(OldConsole: Object(BP_Console_C), Console: Object(BP_Console_C)) | - | - |
| OnCrossfaderLevelChanged(Level: Double) | - | - |
| OnCuePreviewCleared__DelegateSignature(Deck: Object(BP_Deck_C)) | - | - |
| OnCurrentTrackEnded__DelegateSignature() | - | - |
| OnDeckDirectionChanged__DelegateSignature(Deck: Object(BP_Deck_C), bReverse: Bool) | - | - |
| OnDeckPause__DelegateSignature(PausedDeck: Object(BP_Deck_C)) | - | - |
| OnDeckPlay__DelegateSignature(PlayingDeck: Object(BP_Deck_C)) | - | - |
| OnEquipmentSaveLoaded__DelegateSignature(Deck: Object(BP_Deck_C)) | - | - |
| OnHotCueModeChanged__DelegateSignature(Deck: Object(BP_Deck_C), HotCueMode: Enum(E_HotCueMode)) | - | - |
| OnHotOrMemoryCueChanged__DelegateSignature() | - | - |
| OnInstantDoubleOpened() | - | - |
| OnIsLoopingChanged__DelegateSignature(Deck: Object(BP_Deck_C), bLooping: Bool) | - | - |
| OnJogModeChanged__DelegateSignature(Deck: Object(BP_Deck_C)) | - | - |
| OnKeyShiftChanged__DelegateSignature(KeyShiftInterval: Int) | - | - |
| OnKeySyncChanged__DelegateSignature(Deck: Object(BP_Deck_C), bEnabled: Bool) | - | - |
| OnLoopInSet__DelegateSignature(Deck: Object(BP_Deck_C)) | - | - |
| OnMasterTrackAnalyzed__DelegateSignature(Track: Object(TribeTrack)) | - | - |
| OnPadByteParameterChanged__DelegateSignature(PadIndex: Int, Parameter: Byte) | - | - |
| OnPadFloatParameterChanged__DelegateSignature(PadIndex: Int, Parameter: Double) | - | - |
| OnPerformancePadInteraction__DelegateSignature(bStartInteraction: Bool, PadIndex: Int) | - | - |
| OnPlayerMemoryChanged(ref PlayerMemory: Struct(TribePlayerMemory)) | - | - |
| OnPlayerMemoryLoaded__DelegateSignature() | - | - |
| OnRep_ActivePadMode() | - | RespawnPadButtons |
| OnRep_ActivePadSelectButton() | - | NotEqual_ObjectObject, IsValid, SetFlashing, SetButtonOn |
| OnRep_ActiveScreenMode() | - | Get Screen, SetScreenButtonMode |
| OnRep_bKeySyncSlave() | - | GetAudioPlayer, SetKeySyncEnabled, SetKeyShift, Refresh Screen Master Tempo, Get Screen, Set Key Text Color |
| OnRep_bLooping() | - | HasAuthority, IsTrackOpened, GetAudioPlayer, IsLooping, NotEqual_BoolBool, Reloop, ResetPitchLerp, ExitLoop |
| OnRep_bMasterTempo() | - | GetAudioPlayer, SetMasterTempo, Refresh Screen Master Tempo |
| OnRep_bPlaybackActivated() | - | IsTrackOpened, GetAudioPlayer, Play, Multiply_DoubleDouble, GetRemainingTimeMs, Divide_DoubleDouble, LessEqual_DoubleDouble, Pause |
| OnRep_bQuantized() | - | GetAudioPlayer, SetQuantize |
| OnRep_bReverse() | - | GetAudioPlayer, SetReverse, HasAuthority, TriggerRepTick, SetUpdateRepLock |
| OnRep_bSlip() | - | GetAudioPlayer, SetSlip, Get Screen, SetSlipEnabled, EqualEqual_ByteByte, BooleanAND, SetActiveScreenMode |
| OnRep_bTempoLocked() | - | ResetTempo |
| OnRep_bVinylMode() | - | GetAudioPlayer, SetVinylMode |
| OnRep_CurrentBeatJumpInterval() | - | Get Screen, Set Beat Jump Indicator |
| OnRep_CurrentKeyShift() | - | Multiply_IntInt, GetKeySync, GetKeySyncCentsOffset, Add_IntInt, SetPitchShift, IsValid, EqualEqual_IntInt, FlushNetDormancy |
| OnRep_CurrentPitch() | - | RefreshTempo, IsTempoSyncLocked, IsValid, UpdatePositionToMatchTempo |
| OnRep_CurrentTrackFileName() | - | OpenCurrentTrack |
| OnRep_HotCueMode() | - | - |
| OnRep_LoopAdjustmentMode() | - | SetLoopAdjustMode |
| OnRep_ScreenButtonBank() | - | Get Screen, SetScreenButtonBank |
| OnReplicatedTimeUpdated__DelegateSignature() | - | - |
| OnSavedTrackOpened(Deck: Object(BP_Deck_C)) | - | - |
| OnScreenButtonBankChanged__DelegateSignature() | - | - |
| OnScreenModeChanged__DelegateSignature(ScreenMode: Enum(E_ScreenButtonMode)) | - | - |
| OnSessionStateChanged(NewSessionState: Enum(ETribeSessionState)) | - | - |
| OnSlipConditionChanged(SlipCondition: Enum(ESlipCondition)) | - | - |
| OnSlipModeChanged__DelegateSignature(Deck: Object(BP_Deck_C), bSlip: Bool) | - | - |
| OnStreamTrackAvailabilityChanged(StreamTrack: Object(TribeStreamTrack), bAvailable: Bool) | - | EqualEqual_ObjectObject, HasBeenDownloaded, OpenTrack, UnloadTrack |
| OnStreamTrackBeginDownload__DelegateSignature(Deck: Object(BP_Deck_C)) | - | - |
| OnSyncChanged() | - | - |
| OnSyncMasterChanged(NewMaster: Object(Actor)) | - | - |
| OnTempoUnlocked__DelegateSignature(Deck: Object(BP_Deck_C)) | - | - |
| OnTrackAnalysisReady(Track: Object(TribeTrack)) | - | - |
| OnTrackChanged__DelegateSignature(Deck: Object(BP_Deck_C)) | - | - |
| OnTrackEnded() | - | - |
| OnTrackLoadEvent(AudioPlayer: Object(SuperPoweredAudioPlayer), Event: Enum(ESuperPoweredPlayerEvent)) | - | - |
| OnTrackMetadataReady(Track: Object(TribeTrack)) | - | - |
| OnTrackOpened__DelegateSignature(Deck: Object(BP_Deck_C)) | - | - |
| OnTrackReceived(ReplicationManager: Object(BP_TrackReplicationManager_C), Track: Object(TribeTrack)) | - | - |
| OnTrackTransferStarted(ReplicationManager: Object(BP_TrackReplicationManager_C), FileTransfer: Object(FileTransfer)) | - | - |
| OnTrackUnloaded__DelegateSignature(Deck: Object(BP_Deck_C), UnloadedTrack: Object(TribeTrack)) | - | - |
| OnTransferComplete(bSuccess: Bool, FileTransfer: Object(FileTransfer)) | - | - |
| OpenCurrentTrack() | - | Len, Conv_IntToBool, GetTrackLibrary, FindTrack, IsValid, OpenTrack, UnloadTrack, GetPakTrackPrefix |
| OpenTrack(Track: Object(TribeTrack)) | - | NotEqual_ObjectObject, UnloadTrack, IsValid, HasValidSharedUrl, IsFromSharedUrl, Not_PreBool, BooleanAND, RequestDropboxSharedUrlFromServer |
| PlayNetSynced(ref NetSyncPacket: Struct(F_DeckNetPacket)) | - | IsTrackOpened, GreaterEqual_DoubleDouble, BooleanAND, NetSyncToAbsoluteMs, GetAudioPlayer, SetPosition, FlushNetDormancy, MarkPropertyDirtyFromRepIndex |
| PrevBeatJumpInterval() | - | Array_Find, Greater_IntInt, FlushNetDormancy, Subtract_IntInt, Array_Get, MarkPropertyDirtyFromRepIndex, OnRep_CurrentBeatJumpInterval |
| PrintNetDebugInfo() | - | ShouldUseServerPosition, Conv_BoolToString, IsNetSyncPacketValid, FloatToStringWithPrecision, GetObjectName, Concat_StrStr, PrintString |
| RealignBeatSync() | - | GetAudioPlayer, RealignBeatSync, HasAuthority, RestartRepInterval, GetSyncMaster, SendClientResyncToServer |
| ReceiveBeginPlay() | Event | - |
| ReceiveDestroyed() | Event | - |
| ReceiveEndPlay(EndPlayReason: Enum(EEndPlayReason)) | Event | - |
| ReceiveTick(DeltaSeconds: Float) | Event | - |
| Refresh Screen Master Tempo() | - | Get Screen, Set Master Tempo Color, BooleanOR, SetMasterTempoEnabled |
| RefreshReplicationMaster() | - | HasAuthority, GetConsole, RefreshReplicationSyncMaster |
| RefreshScreenRenderPhase() | - | Get Screen, GetRig, Array_Length, SetRenderingPhase |
| RefreshTempo() | - | HasAuthority, GetAudioPlayer, SetTempo, GetTempo, NearlyEqual_FloatFloat, EqualEqual_DoubleDouble, Add_DoubleDouble, FlushNetDormancy |
| Release Audio Player() | - | - |
| ReleaseHotCue(HotCueIndex: Int) | - | GetAudioPlayer, ReleaseSlippedHotCue |
| ReportStreamTrackTime() | - | IsPlaying, GetAudioPlayer, GetPosition, FTrunc, ReportStreamTrackPosition |
| RequestDropboxSharedUrlFromServer() | - | IsValid, Server_RequestDropboxSharedUrl |
| RequestPawnDeckState(TribePawn: Object(TribePawnBP_C)) | - | - |
| RequestPlayerDeckState(TribePlayerController: Object(TribePlayerControllerBP_C), out bRequestSent: Bool, out RequestPawn: Object(TribePawnBP_C)) | - | K2_GetPawn, RequestPawnDeckState |
| RequestTrackTransfer(FileName: Str, RequestingPlayer: Object(TribePlayerControllerBP_C)) | - | - |
| ResetBeatgrid() | - | IsValid, ResetBeatGrid |
| ResetControls() | - | Array_Length, Less_IntInt, Array_Get, Reset, Add_IntInt |
| ResetPitchLerp() | - | RefreshTempo |
| ResetTempo() | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_CurrentPitch |
| Resolve Double Deck(out bSuccess: Bool, out DoubledDeck: Object(BP_Deck_C)) | - | GetSyncMaster, EqualEqual_ObjectObject, BooleanOR, NotEqual_ObjectObject, GetCurrentTrack |
| RespawnPadButtons(PadMode: Enum(E_PerformancePadMode)) | - | - |
| RestartRepInterval() | - | - |
| ReturnToLoop() | - | IsTrackOpened, GetAudioPlayer, ReturnToLoop, FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bLooping |
| SaveDeviceState(SaveDirectory: Str) | - | - |
| SeekToCue(AndStop: Bool) | - | GetServerWorldTimeSeconds, SeekToCueNetSynced |
| SeekToCueNetSynced(AndStop: Bool, Timestamp: Double) | - | GreaterEqual_DoubleDouble, GetAudioPlayer, SeekToCue, FlushNetDormancy, IsPlaying, MarkPropertyDirtyFromRepIndex, OnRep_bPlaybackActivated, HasAuthority |
| SeekToHotCue(Index: Int, AndStop: Bool, bQuantizeJumpImmediately: Bool) | - | IsTrackOpened, SetLoopAdjustmentMode, IsPlaying, GetAudioPlayer, SeekToHotCue, UpdatePlaybackStates, HasAuthority, TriggerRepTick |
| SeekToMemoryCue(bForwards: Bool, bAndStop: Bool) | - | SetLoopAdjustmentMode, GetAudioPlayer, SeekToMemoryCue, HasAuthority, TriggerRepTick, SetTimeRepLock |
| SendClientResyncToServer(SyncMaster: Object(BP_Deck_C)) | - | - |
| SetActivePadButton(ActivePadSelectButton: Object(BP_PerformancePadSelectButton_C), GrabbingHand: Object(TribeControllers_C), bForceShift: Bool) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_ActivePadSelectButton, IsShiftActive, BooleanOR, NotEqual_ByteByte, OnRep_ActivePadMode |
| SetActiveScreenMode(ActiveScreenMode: Enum(E_ScreenButtonMode)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_ActiveScreenMode |
| SetBeatgridBpm(Bpm: Double) | - | IsValid, GetSuperpoweredMaxBpm, GetSuperpoweredMinBpm, FClamp, SetBpm |
| SetBeatgridEditorVisible(bNewVisibility: Bool) | - | SetVisibility, SetActorEnableCollision |
| SetBeatgridFirstBar() | - | IsValid, GetPlaybackMs, Divide_DoubleDouble, FFloor, Divide_IntInt, Multiply_IntInt, Multiply_IntFloat, Subtract_DoubleDouble |
| SetBeatJumpValue(BeatJumpValue: Enum(EBeatFxTimeInterval)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_CurrentBeatJumpInterval |
| SetBeatLoop(NumBeats: Double, bForceUnquantized: Bool) | - | GetAudioPlayer, SetBeatLoop, HasAuthority, UpdateReplicatedLoopInPosition, UpdateReplicatedLoopOutPosition, FlushNetDormancy, GetCueAsTime, MarkPropertyDirtyFromRepIndex |
| SetCue() | - | GetAudioPlayer, SetCue, GetCueAsTime, Multi_SetCuePosition |
| SetCueFromTimestamp(CueMs: Double) | - | Multi_SetCuePosition |
| SetCueToFirstBeat() | - | GetAudioPlayer, SetCueToFirstBeat, GetCueAsTime, Multi_SetCuePosition |
| SetCurrentTrackInfo(FileName: Str, StreamingClient: Name, LoadingPawn: Object(TribePawnBP_C)) | - | - |
| SetDeckPositionNetSynced(bPlaying: Bool, ref NetSyncPacket: Struct(F_DeckNetPacket)) | - | Greater_DoubleDouble, NetSyncToAbsoluteMs, GetAudioPlayer, SetPosition, FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bPlaybackActivated, HasAuthority |
| SetDeckRotated() | - | - |
| SetDeckStateNetSynced(SendingPawn: Object(TribePawnBP_C), ref DeckStatePacket: Struct(F_DeckStatePacket), ref NetSyncPacket: Struct(F_DeckNetPacket)) | - | HasAuthority, NotEqual_ObjectObject, EqualEqual_ObjectObject, GetController, Multi_SetLoopInPosition, Multi_SetLoopOutPosition, FlushNetDormancy, MarkPropertyDirtyFromRepIndex |
| SetEquipmentVisible(bVisible: Bool) | Event | - |
| SetHotCue(Index: Int) | - | GetAudioPlayer, SetHotCue, IsValid, GetHotCueAsTime, Map_Add, SavePlayerMemory |
| SetHotCueFromTimestamp(Index: Int, CueMs: Double, LengthMs: Double) | - | GetAudioPlayer, SetHotCueFromTimestamp |
| SetHotCueMode(HotCueMode: Enum(E_HotCueMode)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_HotCueMode |
| SetHotCueScreenColor(Index: Int) | - | Array_Get, GetHotCueColor, Get Screen, SetCueIndicatorColor |
| SetInstancedDeckMesh() | - | - |
| SetJogMode(VinylMode: Bool) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bVinylMode |
| SetKey(Track: Object(TribeTrack)) | - | GetAudioPlayer, GetKeyIndex, SetOriginalKey |
| SetKeyShift(KeyShiftInterval: Int) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_CurrentKeyShift |
| SetLoopAdjustmentMode(LoopAdjustmentMode: Enum(ELoopAdjustMode)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_LoopAdjustmentMode |
| SetLoopInFromTimestamp(LoopInMs: Double) | - | Multi_SetLoopInPosition |
| SetLoopInPosition() | - | GetAudioPlayer, SetLoopIn, UpdateReplicatedLoopInPosition, IsTrackOpened |
| SetLoopOutFromTimestamp(LoopOutMs: Double) | - | Multi_SetLoopOutPosition |
| SetLoopOutPosition() | - | GetAudioPlayer, SetLoopOut, UpdateReplicatedLoopOutPosition, HasAuthority, SetTimeRepLock |
| SetMasterTempo(MasterTempo: Bool) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bMasterTempo |
| SetMemoryCue(out MemoryCueIndex: Int) | - | GetAudioPlayer, SetMemoryCue, IsValid, GetMemoryCueAsTime, Map_Add, SavePlayerMemory |
| SetMemoryCueFromTimestamp(Index: Int, CueMs: Double, LengthMs: Double) | - | GetAudioPlayer, SetMemoryCueFromTimestamp |
| SetPadByteParameter(PadIndex: Int, Parameter: Byte) | - | Array_Get, SetByteParameter |
| SetPadFloatParameter(PadIndex: Int, Parameter: Double) | - | Array_Get, SetFloatParameter |
| SetPlaybackMs(PositionMs: Double) | - | GetAudioPlayer, SetPosition, HasAuthority, RestartRepInterval, SetTimeRepLock |
| SetPositionFromBeatJump(NumBeats: Double, bBackwards: Bool, bWaitForBeat: Bool) | - | Multiply_DoubleDouble, GetAudioPlayer, BeatJump, HasAuthority, RestartRepInterval, SetTimeRepLock |
| SetPositionFromFraction(PlaybackFraction: Double) | - | GetAudioPlayer, SetPositionFromFraction, HasAuthority, RestartRepInterval, SetTimeRepLock |
| SetQuantized(Quantize: Bool) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bQuantized |
| SetReversePlayback(Reverse: Bool) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bReverse |
| SetScreenButtonBank(ScreenButtonBank: Int) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_ScreenButtonBank |
| SetSlip(Slip: Bool) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bSlip |
| SetTempoLocked(bLocked: Bool) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bTempoLocked |
| SetTimeMode(bTimeRemaining: Bool) | - | Get Screen, Set Time Mode |
| SetTimeRepLock() | - | GetServerWorldTimeSeconds, FMax, SetUpdateRepLock |
| SetTouchBrake(TouchBrake: Double) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex |
| Setup Child Control(NewChild: Object(BP_BaseDeckControl_C), Marker: Object(SceneComponent)) | - | Array_Add, EqualEqual_NameName, GetRelativeTransform, K2_SetActorRelativeTransform, K2_AttachToActor, IsValid, K2_DestroyComponent, GetBoneTransform |
| SetUpdateRepLock() | - | ResetPitchLerp, HasAuthority, PrintString |
| SetupTonearmChildControl(NewChild: Object(BP_BaseDeckControl_C)) | - | Array_Add, GetTransform, GetBoneTransform, MakeRelativeTransform, BreakTransform, BreakRotIntoAxes, MakeRotationFromAxes, MakeTransform |
| ShiftBeatgridStartMs(ShiftInterval: Double) | - | IsValid, GetAudioPlayer, GetDuration, GetBeatgridStartMs, Add_DoubleDouble, FClamp, SetBeatStartMs |
| ShouldUseServerPosition(out bUseRepPosition: Bool) | - | IsTrackOpened, EqualEqual_ObjectObject, GetAudioPlayer, IsScratching, HasPendingJumpOnNextBeat, BooleanOR, Not_PreBool, BooleanAND |
| SpawnControls() | - | - |
| Start Play() | - | - |
| StartCuePreview() | - | Not_PreBool, GetAudioPlayer, IsAtCue, GetServerWorldTimeSeconds, FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bPlaybackActivated, SeekToCue |
| Stop Play() | - | - |
| StopCuePreview() | - | SeekToCue |
| StopNetSynced(PositionMs: Double, Timestamp: Double) | - | GreaterEqual_DoubleDouble, GetAudioPlayer, SetPosition, FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bPlaybackActivated, HasAuthority, RestartRepInterval |
| StopPlayForceNoBrake() | - | SetTouchBrake, Stop Play |
| TickNetBeatSync_Client(DeltaSeconds: Double) | - | - |
| TickNetBeatSync_Server(DeltaSeconds: Double) | - | - |
| TimeToPositionDelta(TimeDeltaSeconds: Double, out PlayDeltaMs: Double) | - | GetAudioPlayer, IsLooping, Multiply_DoubleDouble, GetLoopLengthMs, GetPlaybackRate, Percent_FloatFloat |
| ToggleBeatgridEditor() | - | Not_PreBool, SetBeatgridEditorVisible |
| ToggleKeySync(bSyncOn: Bool) | - | - |
| ToggleSyncMaster(bManuallySet: Bool) | - | - |
| TriggerRepTick(bReliableRPC: Bool) | - | - |
| UnloadTrack() | - | - |
| UnloadTrack_Implementation() | - | IsValid, Get Screen, HideDisplay, FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bPlaybackActivated, OnRep_CurrentKeyShift, ClearAllHotCues |
| UpdateBeatGridToCurrentTrack() | - | HasAuthority, GetBpm, GetBeatgridStartMs, Multi_SetBeatGrid, Greater_DoubleDouble |
| UpdateNetSyncMs(ref NetSyncPacket: Struct(F_DeckNetPacket)) | - | - |
| UpdatePitch() | - | HasAuthority, GetAudioPlayer, GetTempo, NearlyEqual_FloatFloat, RealignBeatSync, IsSyncSlave, EqualEqual_DoubleDouble, Subtract_DoubleDouble |
| UpdatePlaybackStates() | - | GetAudioPlayer, GetRecentEof, OnTrackEnded, IsPlaying, NotEqual_BoolBool, FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bPlaybackActivated |
| UpdateReplicatedLoopInPosition() | - | GetAudioPlayer, GetLoopInMs, Multi_SetLoopInPosition, FlushNetDormancy, IsLooping, MarkPropertyDirtyFromRepIndex, OnRep_bLooping |
| UpdateReplicatedLoopOutPosition() | - | GetAudioPlayer, GetLoopOutMs, Multi_SetLoopOutPosition, FlushNetDormancy, IsLooping, MarkPropertyDirtyFromRepIndex, OnRep_bLooping |
| UpdateReplicatedState() | - | HasRepAuthority, GetAudioPlayer, GetCueAsTime, Multi_SetLoopInPosition, GetLoopOutMs, Multi_SetLoopOutPosition, FlushNetDormancy, IsLooping |
| UpdateReplicatedTime(bReliable: Bool) | - | RefreshReplicationSyncMaster, FlushNetDormancy, GetServerWorldTimeSeconds, MakeNetSyncPacket, MarkPropertyDirtyFromRepIndex, Multi_UpdateNetSyncMs_Reliable, Multi_UpdateNetSyncMs_Unreliable |
| UpdateToServerPosition() | - | GetReplicatedPosition, GetAudioPlayer, GetPosition, GetLoopWrappedDeltaMs, NotEqual_ObjectObject, Divide_DoubleDouble, NearlyEqual_FloatFloat, IsSyncMaster |
| UserConstructionScript() | Event | UserConstructionScript, SetChildActorClass, Initialize Audio Player |
| WasTrackLoadedLocally(out bLoadedLocally: Bool) | - | EqualEqual_ObjectObject, HasAuthority, IsLocallyControlled |

## BP_Console_C: the mixer engine: every mixer model derives from it

Parent `TribeEquipmentBase`. 167 functions; variables: `UberGraphFrame`, `Marker_MixerScreenMenuAttachPoint`, `Marker_ConsoleMenuAttachPoint`, `ConsoleContainer`, `SP_Mixer`, `ActiveDuckTags`, `DuckingGlobalVolume`, `ActiveFXButton`, `DefaultGlobalVolume`, `CurrentBeatFXTime`, `Controls`, `Displays`, `Crossfader`, `HeadphoneIndicator`, `OnHeadphonesToggled`, `CurrentBeatFXBpm`, `MicEQ`, `MicMode`, `bMicTalkoverEnabled`, `CrossfaderCurve`, `ChannelFaderCurve`, `OnHeadphonesHovered`, `MicControls`, `OnChannelCueToggled`, `OnChannelFadeChanged`, `OwningRig`, `EqCurve`, `ChannelEQs`, `SyncMaster`, `OnSyncMasterChanged`, `CachedSyncMaster`, `ChannelsControls`, `RepMaster`, `OnRepMasterChanged`, `CachedActiveFx`, `OnMasterTrackAnalyzed`, `bAutoBpm`, `OnActiveBeatFxChanged`, `BeatFxToggleButton`, `bBeatFxEnabled`, `CachedBeatFXAssignButton`, `CachedFilterButton`, `DefaultSavedControls`, `K_ConfigSectionSavedControls`, `K_MixerSaveGame`, `OnBeatFxBpmModeChanged`, `bTapButtonHeld`, `ActiveFilterButton`, `ActiveBeatFXAssignButton`, `Mixer Params`, `EquipmentSaveFxButtonKey`, `MasterVUMeterL`, `MasterVUMeterR`, `ChannelVUMeters`, `ColorFXButtons`, `EquipmentSaveSyncMasterKey`, `EquipmentSaveFilterButtonKey`, `BeatFXTypeIndex`, `AvailableBeatFX`, `AvailableColorFx`, `OnActiveColorFxChanged`, `OnCrossfaderChanged`, `GapQueueBack`, `RecentTapGapsSeconds`, `TapSecondsElapsed`, `TapQueueCapacity`, `bTapQueueActive`, `CurrentSmartColorFx`, `bSmartFaderEnabled`, `OnSmartFaderEnabled`, `LeftDeckSmartTempo`, `RightDeckSmartTempo`, `SmartTempoLeftPitchMod`, `SmartTempoRightPitchMod`, `LeftTargetBpm`, `RightTargetBpm`, `LeftOriginalBpm`, `RightOriginalBpm`, `OnCalculateSmartTempos`, `MasterLightDbs`, `ChannelLightDbs`, `bColorFXCenterLockEnabled`, `OnBeatFxChannelChanged`, `ActiveMicFX`, `OnMicFxChanged`, `EquipmentSaveBeatIntervalKey`, `bBeatFxToggleIntent`, `bBeatFxTouchIntent`, `OnShiftChanged`, `OnColorFXCenterLockToggled`.

| Function | Kind | Calls |
|---|---|---|
| AddBeatFXTime(timeMs: Double) | - | GetMixer, AddBeatFxTime, UpdateReplicatedBeatFXTime |
| AdvanceBeatFXType(GrabbingHand: Object(TribeControllers_C)) | - | IsShiftActive, FlushNetDormancy, Subtract_IntInt, MarkPropertyDirtyFromRepIndex, OnRep_BeatFXTypeIndex, Add_IntInt |
| AutoSwitchSyncMaster(bOnlySwitchIfSynced: Bool, out bSwitchSuccess: Bool, out NewMaster: Object(BP_MixerChannelDevice_C)) | - | Array_Length, Less_IntInt, Array_Get, NotEqual_ObjectObject, ShouldImplementSync, BooleanAND, IsPlaying, ChannelIsAudible |
| CalculateSmartFaderTempos() | - | EqualEqual_ObjectObject, ForceSwitchSyncMaster, LessEqual_IntInt, EqualEqual_IntInt, GetDeckByChannel, NotEqual_ObjectObject, IsTempoSyncLocked, EqualEqual_DoubleDouble |
| ChannelControlName(Name: Text, MixerChannel: Int) -> Text | - | Add_IntInt, Conv_IntToInt64, Format |
| Client Init Display() | - | GetBeatFXDisplayWidget, UpdateBeatMs, SetAutoBpm, SetCrossfaderCurve, SetChannelFaderCurve |
| ClientDestroyMarkers() | - | - |
| ConnectDevice(Device: Object(SuperPoweredChannelDevice), Channel: Int) | - | Get Or Create Mixer, Connect |
| DestroyControls() | - | Array_Length, Less_IntInt, Array_Get, K2_DestroyActor, Add_IntInt |
| DisableFX() | - | SetActiveFXButton |
| DisableMicControls() | - | Array_Length, Less_IntInt, Array_Get, DisableInteraction, Add_IntInt |
| ForceSwitchSyncMaster() | - | AutoSwitchSyncMaster, Array_Length, Less_IntInt, Array_Get, NotEqual_ObjectObject, ShouldImplementSync, BooleanAND, IsPlaying |
| Get General EQ Position(out General EQ Position: Struct(Vector)) | - | - |
| Get Or Create Mixer(out Mixer: Object(SuperPoweredMixer)) | - | EqualEqual_ObjectObject, Initialize Mixer |
| GetActiveBeatFXAssignButton(out ActiveButton: Object(BP_BeatFXAssignButton_C)) | - | - |
| GetActiveFilterButton(out FilterButton: Object(BP_FilterButton_C)) | - | - |
| GetActiveFXButton(out ActiveFXButton: Object(BP_ColorFXButton_C)) | - | - |
| GetActiveFXType(out FXType: Byte) | - | IsValid |
| GetAverageTapBpm(out BPM: Double) | - | Array_Length, Less_IntInt, Array_Get, Greater_DoubleDouble, Add_IntInt, Add_DoubleDouble, Conv_IntToDouble, Divide_DoubleDouble |
| GetBeatFxDisplayBpm(out Bpm: Double) | - | GetMixer, GetBeatFxBpm |
| GetBeatFXDisplayWidget(out BeatFXDisplayWidget: Interface(BeatFXDisplayInterface_C)) | - | - |
| GetBeatFXTime() -> Double | - | GetMixer, GetBeatFxTime |
| GetChannelFader(Channel: Int, out FaderGain: Double) | - | GetChannelFader |
| GetColorFXCenterLockEnabled(out bEnabled: Bool) | - | - |
| GetConsoleAttachPoint(out AttachTransform: Struct(Transform)) | - | K2_GetComponentToWorld |
| GetDefaultSaveControlNames(out ControlNames: Set<Name>) | - | - |
| GetMixer(out Mixer: Object(SuperPoweredMixer)) | - | - |
| GetMixerMesh(out Static Mesh: Object(StaticMeshComponent)) | - | - |
| GetMixerScreenAttachPoint(out AttachTransform: Struct(Transform)) | - | K2_GetComponentToWorld |
| GetReplicationSyncMaster(out ReplicationSyncMaster: Object(BP_Deck_C)) | - | - |
| GetVarReplicateConditionOverrides(out OutClass: Class(Object), out OutOverrides: Array<Struct(RepConditionOverride)>) | Event | GetObjectClass |
| HandleSyncMasterDestroyed(DestroyedActor: Object(Actor)) | - | EqualEqual_ObjectObject, SetSyncMaster |
| HandleXPadButtonToggled(bXPadOn: Bool, BeatFxInterval: Enum(EBeatFxTimeInterval)) | - | GetBeatFXDisplayWidget, OnXPadButtonToggled |
| Initialize Mixer(out Mixer: Object(SuperPoweredMixer)) | - | Array_Resize, Subtract_IntInt, LessEqual_IntInt, Array_Set, CreateMixer, Add_IntInt |
| IsShiftActive(GrabbingHand: Object(TribeControllers_C), out bShiftActive: Bool) | - | Array_Length, Less_IntInt, Array_Get, NotEqual_ObjectObject, IsShiftAllowed, IsValid, IsShiftEnabled, GetPlayerPawn |
| IsSmartFaderPitchEnabled(out bPitchEnabled: Bool) | - | GetGameState, GetBeatHighwayState, EqualEqual_ByteByte, BooleanOR, Not_PreBool, BooleanAND |
| LoadConsoleState(EquipmentSaveGame: Object(TribeEquipmentSaveGame)) | - | GetInt, GreaterEqual_IntInt, Conv_IntToByte, GetValidValue, Not_PreBool, Array_Length, Less_IntInt, BooleanAND |
| LoadDeviceState(SaveDirectory: Str, SaveSetting: Enum(E_DeviceSaveCofiguration)) | - | - |
| Lock Controls() | - | Array_Length, Less_IntInt, Array_Get, DisableInteraction, Add_IntInt |
| Multi_SetBeatFxBpm(BeatFxBpm: Double) | NetMulticast | - |
| Multi_SetRepMaster(NewRepMaster: Object(BP_Deck_C)) | NetMulticast | - |
| Multi_SetSmartFaderPitchMod(Channel: Int, PitchMod: Double) | NetMulticast | - |
| Multi_SetSmartFaderPitchMod_Reliable(Channel: Int, PitchMod: Double) | NetMulticast | - |
| OnActiveBeatFxChanged__DelegateSignature(NewBeatFx: Enum(EBeatFxType)) | - | - |
| OnActiveColorFxChanged__DelegateSignature(NewColorFx: Enum(EColorFxType)) | - | - |
| OnAllClientActorsReplicated() | - | - |
| OnBeatFxBpmModeChanged__DelegateSignature(bAuto: Bool) | - | - |
| OnBeatFxChannelChanged__DelegateSignature(BeatFxChannel: Enum(EBeatFxChannel)) | - | - |
| OnCalculateSmartTempos__DelegateSignature() | - | - |
| OnChannelCueToggled__DelegateSignature(Channel: Int, bEnabled: Bool) | - | - |
| OnChannelFadeChanged__DelegateSignature(Channel: Int, Level: Double, bShifted: Bool) | - | - |
| OnColorFXCenterLockToggled__DelegateSignature(bCenterLockEnabled: Bool) | - | - |
| OnCrossfaderChanged__DelegateSignature(Level: Double) | - | - |
| OnHeadphonesHovered__DelegateSignature(bHovered: Bool, Hand: Enum(E_Hand)) | - | - |
| OnHeadphonesToggled__DelegateSignature(bLeftWorn: Bool, bRightWorn: Bool) | - | - |
| OnMasterTrackAnalyzed__DelegateSignature(Track: Object(TribeTrack)) | - | - |
| OnMicFxChanged__DelegateSignature(ActiveMicFx: Enum(EBeatFxType)) | - | - |
| OnRep_ActiveBeatFX() | - | - |
| OnRep_ActiveBeatFXAssignButton() | - | NotEqual_ObjectObject, IsValid, OnBeatFxAssignDisabled, Get Or Create Mixer, SetBeatFxChannel, OnBeatFxAssignEnabled |
| OnRep_ActiveFilterButton() | - | NotEqual_ObjectObject, IsValid, OnFilterDisabled, Get Or Create Mixer, SetChannelFilterType, OnFilterEnabled |
| OnRep_ActiveFXButton() | - | NotEqual_ObjectObject, IsValid, OnFXDisabled, Get Or Create Mixer, SetActiveChannelFx, OnFXEnabled |
| OnRep_ActiveMicFX() | - | GetMixer, SetActiveMicFx |
| OnRep_AutoBpm() | - | GetMixer, SetAutoBpm, GetBeatFXDisplayWidget, ResetTapBpmQueue |
| OnRep_bBeatFxEnabled() | - | SetBeatFxEnabled, GetBeatFXDisplayWidget, SetBeatFXEnabled, IsValid, OnBeatFxEnabled |
| OnRep_bColorFXCenterLockEnabled() | - | - |
| OnRep_BeatFXTypeIndex() | - | Get Or Create Mixer, Array_Length, ModuloNegative, Array_Get, SetActiveBeatFx |
| OnRep_bMicTalkoverEnabled() | - | EqualEqual_ByteByte, SetMicMode |
| OnRep_bSmartFaderEnabled() | - | CalculateSmartFaderTempos, Array_Length, Less_IntInt, Array_Get, Add_IntInt |
| OnRep_ChannelFaderCurve() | - | Get Or Create Mixer, SetChannelFaderCurve, GetBeatFXDisplayWidget |
| OnRep_CrossfaderCurve() | - | Get Or Create Mixer, SetCrossfaderCurve, GetBeatFXDisplayWidget |
| OnRep_CurrentBeatFXTime() | - | HasAuthority, GetBeatFXDisplayWidget, UpdateBeatMs, Get Or Create Mixer, SetBeatFxTimeMs |
| OnRep_EqCurve() | - | Get Or Create Mixer, SetEqCurve |
| OnRep_MicMode() | - | HasAuthority, Get Or Create Mixer, SetMicMode |
| OnRep_RepMaster() | - | - |
| OnRep_SyncMaster() | - | NotEqual_ObjectObject, Get Or Create Mixer, GetSyncMaster, ReleaseSyncMaster, HasAuthority, FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bStartAsMaster |
| OnRepMasterChanged__DelegateSignature(RepMaster: Object(BP_Deck_C)) | - | - |
| OnShiftChanged__DelegateSignature(bIsShifted: Bool) | - | - |
| OnSmartFaderDeckBeatgridChanged(Bpm: Double, StartMs: Double) | - | - |
| OnSmartFaderEnabled__DelegateSignature(bEnabled: Bool) | - | - |
| OnSyncMasterChanged__DelegateSignature(NewMaster: Object(Actor)) | - | - |
| OnTapButtonPressed() | - | SetTapButtonHeld, SetBeatFxAutoBpm, HasAuthority, EqualEqual_IntInt, Subtract_IntInt, LessEqual_IntInt, Add_IntInt, Array_Get |
| OnVoiceStateChangedDucking(PlayerId: Str, bNewTalkingState: Bool) | - | - |
| ReceiveBeginPlay() | Event | - |
| ReceiveDestroyed() | Event | - |
| ReceiveTick(DeltaSeconds: Float) | Event | - |
| RefreshChannelEqs() | - | Array_Length, Less_IntInt, Array_Get, OnKnobTurned, Add_IntInt |
| RefreshCrossfaderBeatFxIndicators() | - | - |
| RefreshReplicationSyncMaster(out ReplicationSyncMaster: Object(BP_Deck_C)) | - | CanBeRepMaster, NotEqual_ObjectObject, HasAuthority, Multi_SetRepMaster, IsValid, Array_Length, Less_IntInt, Array_Get |
| RefreshSmartFaderMaster(NewMaster: Object(Actor)) | - | NotEqual_ObjectObject, EqualEqual_IntInt, Divide_DoubleDouble, GetMixer, GetCrossfader, SetPitchFromSmartFader |
| ResetControls() | - | Array_Length, Less_IntInt, Array_Get, Reset, SetActiveFXButton, Add_IntInt |
| ResetTapBpmQueue() | - | Array_Clear, Array_Resize |
| ResyncDecks() | - | Array_Length, Less_IntInt, Array_Get, IsSyncMaster, Not_PreBool, IsSynced, BooleanAND, RealignBeatSync |
| SaveConsoleState(EquipmentSaveGame: Object(TribeEquipmentSaveGame)) | - | GetActiveFXButton, NotEqual_ObjectObject, Conv_ByteToInt, SaveInt, GetActiveFilterButton, GetBeatFxTimeInterval |
| SaveDeviceState(SaveDirectory: Str) | - | - |
| Set Channel EQ(Channel: Int, Band: Enum(EEQBand), Level: Double) | - | Get Or Create Mixer, SetChannelEq |
| Set Crossfader(Volume: Double) | - | - |
| Set EQ Band(Band: Enum(E_EQBand), Last: Struct(Vector), Next: Double, out Final: Struct(Vector)) | - | NotEqual_ByteByte, BreakVector, MakeVector |
| Set Smart Fader Pitch Mod(Channel: Int, PitchMod: Double) | - | EqualEqual_IntInt, Add_DoubleDouble, Multiply_DoubleDouble, Get Or Create Mixer, GetCrossfader, SetPitchFromSmartFader |
| SetActiveFilterButton(NewFilterButton: Object(BP_FilterButton_C)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_ActiveFilterButton |
| SetActiveFXButton(NewActiveButton: Object(BP_ColorFXButton_C)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_ActiveFXButton |
| SetActiveMicFX(ActiveMicFX: Enum(EBeatFxType)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_ActiveMicFX |
| SetBeatFXAssignButton(ActiveBeatFXAssignButton: Object(BP_BeatFXAssignButton_C)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_ActiveBeatFXAssignButton |
| SetBeatFxAutoBpm(bAutoBpm: Bool) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_AutoBpm |
| SetBeatFxBpm(Bpm: Double) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, Get Or Create Mixer, SetBeatFxBpm, GetBeatFXDisplayWidget, FloatToStringWithPrecision, Conv_StringToText, SetBPM |
| SetBeatFXChannel(Channel: Enum(EBeatFxChannel)) | - | Get Or Create Mixer, SetBeatFxChannel, SetBeatFxIndicators |
| SetBeatFXEnabled(Enabled: Bool) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bBeatFxEnabled |
| SetBeatFxEq(EqBand: Enum(E_EQBand), bEnabled: Bool) | - | Get Or Create Mixer, NotEqual_ByteByte, SetBeatFxEqLow, SetBeatFxEqMid, SetBeatFxEqHigh |
| SetBeatFxIndicators(BeatFxChannel: Enum(EBeatFxChannel)) | - | - |
| SetBeatFXLevel(Level: Double) | - | Get Or Create Mixer, SetBeatFxLevel |
| SetBeatFxParameter(Value: Double) | - | Get Or Create Mixer, SetBeatFxParameter, GetBeatFXDisplayWidget, OnXPadSliderValueChanged |
| SetBeatFXQuantize(Enabled: Bool) | - | SetBeatFxQuantize, GetBeatFXDisplayWidget, SetQuantize |
| SetBeatFxTime(timeMs: Double) | - | GetMixer, SetBeatFxTimeMs, UpdateReplicatedBeatFXTime |
| SetBeatFXTimeInterval(NewTimeInterval: Enum(EBeatFxTimeInterval)) | - | SetBeatFxTimeInterval, UpdateReplicatedBeatFXTime, GetBeatFXDisplayWidget, ShowBeatInterval |
| SetBeatFXToggleIntent(bBeatFxToggleIntent: Bool) | - | UpdateBeatFXEnabled |
| SetBeatFxTouchIntent(bBeatFxSliderIntent: Bool) | - | UpdateBeatFXEnabled |
| SetBeatFxType(NewBeatFX: Enum(EBeatFxType)) | - | Get Or Create Mixer, SetActiveBeatFx |
| SetBeatFxXpadEnabled(bEnabled: Bool) | - | Get Or Create Mixer, SetBeatFxXPadEnabled, GetBeatFXDisplayWidget, SetBeatFXXpadEnabled |
| SetChannelCue(Channel: Int, Cue: Bool) | - | Get Or Create Mixer, SetChannelCue |
| SetChannelFader(Channel: Int, Level: Double, bShifted: Bool) | - | Get Or Create Mixer, SetChannelFader |
| SetChannelFaderCurve(Curve: Enum(EFaderCurve)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_ChannelFaderCurve |
| SetChannelFilterLevel(Channel: Int, Level: Double) | - | Get Or Create Mixer, SetChannelFilterLevel |
| SetChannelFilterResonance(Resonance: Double) | - | Get Or Create Mixer, SetChannelFilterResonance |
| SetChannelSendLevel(Channel: Int, Resonance: Double) | - | Get Or Create Mixer, SetChannelSendLevel |
| SetClipIndicatorHidden(Channel: Int, bHidden: Bool) | - | - |
| SetColorFXCenterLockEnabled(bEnabled: Bool) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bColorFXCenterLockEnabled |
| SetColorFxParameter(Parameter: Double) | - | Get Or Create Mixer, SetColorFxParameter |
| SetCrossfaderAssign(Channel: Int, Assign: Enum(ECrossfaderAssign)) | - | Get Or Create Mixer, SetChannelCrossfaderAssign, RefreshCrossfaderBeatFxIndicators |
| SetCrossfaderCurve(Curve: Enum(EFaderCurve)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_CrossfaderCurve |
| SetEqCurve(EqCurve: Enum(EEqCurve)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_EqCurve, RefreshChannelEqs |
| SetEquipmentVisible(bVisible: Bool) | Event | - |
| SetHeadphonesWorn(Left: Bool, Right: Bool) | - | SetHeadphonesWorn |
| SetMasterFilterLevel(Level: Double) | - | Get Or Create Mixer, SetMasterFilterLevel |
| SetMicEQ(Band: Enum(E_EQBand), Level: Double) | - | Set EQ Band |
| SetMicLevel(Level: Double) | - | Get Or Create Mixer, SetMicLevel |
| SetMicMode(MicMode: Enum(EMicMode)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_MicMode |
| SetMicTalkoverEnabled(bTalkoverEnabled: Bool) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bMicTalkoverEnabled |
| SetNextBeatFXTimeInterval(out NewInterval: Enum(EBeatFxTimeInterval), out IntervalChanged: Bool) | - | SetNextBeatFxTimeInterval, UpdateReplicatedBeatFXTime, GetBeatFXDisplayWidget, ShowBeatInterval |
| SetPitchFromSmartFader(CrossfaderLevel: Double) | - | GetGameState, GetBeatHighwayState, EqualEqual_ByteByte, BooleanOR, IsTrackOpened, Add_DoubleDouble, Divide_DoubleDouble, Lerp |
| SetPreviousBeatFXTimeInterval(out NewInterval: Enum(EBeatFxTimeInterval), out IntervalChanged: Bool) | - | SetPreviousBeatFxTimeInterval, UpdateReplicatedBeatFXTime, GetBeatFXDisplayWidget, ShowBeatInterval |
| SetSendFXMasterMixEnabled(bEnabled: Bool) | - | Get Or Create Mixer, SetMasterFxMix |
| SetSendFXMasterMixLevel(MixLevel: Double) | - | Get Or Create Mixer, SetSendFxMasterMixLevel |
| SetSendFXSize(Size: Double) | - | Get Or Create Mixer, SetSendFxSize |
| SetSendFXTime(Time: Double) | - | Get Or Create Mixer, SetSendFxTime |
| SetSendFXTone(Tone: Double) | - | Get Or Create Mixer, SetSendFxTone |
| SetSmartColorFx(SmartColorFx: Enum(EColorFxType)) | - | - |
| SetSmartFaderEnabled(bSmartFaderEnabled: Bool) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bSmartFaderEnabled |
| SetSyncMaster(SyncMaster: Object(BP_MixerChannelDevice_C)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_SyncMaster |
| SetTapButtonHeld(bTapButtonHeld: Bool) | - | - |
| Setup Room Spatialization() | - | - |
| SetupChildControl(ref Child: Object(BP_BaseDeckControl_C), SpawnMarker: Object(SceneComponent)) | - | Array_Add, EqualEqual_NameName, GetRelativeTransform, K2_SetActorRelativeTransform, K2_AttachToActor, IsValid, K2_DestroyComponent, GetBoneTransform |
| SetupChildControl_Transform(ref Child: Object(BP_BaseDeckControl_C), ref NewRelativeTransform: Struct(Transform)) | - | Array_Add, EqualEqual_NameName, K2_SetActorRelativeTransform, K2_AttachToActor, GetBoneTransform, BreakTransform, K2_SetActorRelativeLocation |
| SetupChildDisplay(DisplayActor: Object(Actor), Marker: Object(SceneComponent)) | - | GetRelativeTransform, SetupChildDisplay_Transform, K2_DestroyComponent |
| SetupChildDisplay_Transform(DisplayActor: Object(Actor), ref NewRelativeTransform: Struct(Transform)) | - | Array_Add, K2_SetActorRelativeTransform, K2_AttachToActor |
| SpawnChannel(ChannelIndex: Int) | - | - |
| SpawnControls() | - | - |
| StartDuckingAudio(DuckTag: Name) | - | Set_Contains, Set_Add, SetGlobalVolume |
| StopDuckingAudio(DuckTag: Name) | - | Set_Remove, Set_Length, EqualEqual_IntInt, SetGlobalVolume |
| ToggleBeatFxView(bShowMainDisplay: Bool) | - | GetBeatFXDisplayWidget, ToggleMainDisplay |
| Unlock Controls() | - | Array_Length, Less_IntInt, Array_Get, EnableInteraction, Add_IntInt |
| Update EQ() | - | BreakVector, SetMicEq |
| UpdateBeatFXEnabled() | - | BooleanOR, SetBeatFXEnabled |
| UpdateMaster() | - | HasAuthority, IsValid, IsPlaying, ChannelIsAudible, AutoSwitchSyncMaster, IsSynced |
| UpdateReplicatedBeatFXTime() | - | Get Or Create Mixer, FlushNetDormancy, GetBeatFxTime, MarkPropertyDirtyFromRepIndex, OnRep_CurrentBeatFXTime |
| UpdateTapQueue(DeltaSeconds: Double) | - | Add_DoubleDouble |
| UpdateVUMeters() | - | NotEqual_ObjectObject, GetMixer, GetMasterMeter, ConvertArrayType, GetMeterLightIndex, SetDisplayLevels, Array_Length, Less_IntInt |
| UserConstructionScript() | Event | UserConstructionScript, Get Or Create Mixer |

## BP_MixerChannelDevice_C: the base of anything that plugs into a mixer channel (decks, synths)

Parent `TribeEquipmentBase`. 38 functions; variables: `UberGraphFrame`, `DefaultSceneRoot`, `Rig`, `Console`, `MixerChannel`, `bSynced`, `OnSyncStateChanged`, `SyncMode`, `bStartAsMaster`, `OnConsoleRespawned`, `bBeatSyncDirty`, `CachedConsole`, `bManualMasterOverride`, `bShifted`.

| Function | Kind | Calls |
|---|---|---|
| AllowsSimaltaneousSyncMaster(out bAllowed: Bool) | - | - |
| End Sync() | - | - |
| GetAudioDevice(out AudioDevice: Object(SuperPoweredChannelDevice)) | - | GetObjectClass, GetClassDisplayName, Concat_StrStr, PrintString |
| GetConsole(out Console: Object(BP_Console_C)) | - | - |
| GetControls(out Controls: Array<Object(BP_BaseDeckControl_C)>) | - | - |
| GetRig(out Rig: Object(BP_Rig_C)) | - | - |
| GetSyncMaster(out SyncMaster: Object(BP_MixerChannelDevice_C)) | - | - |
| GetVarReplicateConditionOverrides(out OutClass: Class(Object), out OutOverrides: Array<Struct(RepConditionOverride)>) | Event | GetObjectClass |
| IsPlaying(out bPlayingAudio: Bool) | - | GetAudioDevice, NotEqual_ObjectObject, IsPlaying |
| IsShiftActive(GrabbingHand: Object(TribeControllers_C), out bShiftActive: Bool) | - | IsShiftActive |
| IsShiftAllowed(out bShiftAllowed: Bool) | - | - |
| IsSynced(out bSynced: Bool) | - | GetAudioDevice, IsSyncSlave |
| IsSyncMaster(out bSyncMaster: Bool) | - | GetAudioDevice, IsSyncMaster |
| IsTempoSyncLocked(out SyncLocked: Bool) | - | IsSynced, IsSyncMaster, Not_PreBool, BooleanAND, NotEqual_ObjectObject |
| Lock Controls() | - | GetControls, Array_Length, Less_IntInt, Array_Get, DisableInteraction, Add_IntInt |
| OnConsoleChanged(OldConsole: Object(BP_Console_C), Console: Object(BP_Console_C)) | - | - |
| OnConsoleRespawned__DelegateSignature(OldConsole: Object(BP_Console_C), Console: Object(BP_Console_C)) | - | - |
| OnRep_bStartAsMaster() | - | HasAuthority, NotEqual_ObjectObject, SetSyncMaster |
| OnRep_bSynced() | - | OnSyncChanged |
| OnRep_Console() | - | NotEqual_ObjectObject, RefreshMixerConnect, IsValid, OnConsoleChanged, OnSyncMasterChanged |
| OnSyncChanged() | - | - |
| OnSyncMasterChanged(NewMaster: Object(Actor)) | - | - |
| OnSyncStateChanged__DelegateSignature(ChannelDevice: Object(BP_MixerChannelDevice_C)) | - | - |
| RealignBeatSync() | - | GetAudioDevice, RealignBeatSync |
| ReceiveBeginPlay() | Event | - |
| ReceiveEndPlay(EndPlayReason: Enum(EEndPlayReason)) | Event | - |
| RefreshMixerConnect() | - | IsValid, GetAudioDevice, NotEqual_ObjectObject, ConnectDevice, AddTickPrerequisiteActor |
| SetConsole(Console: Object(BP_Console_C)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_Console |
| SetShifted(bShifted: Bool, GrabbingHand: Object(TribeControllers_C)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, GetConsole, IsShiftActive |
| SetSynced(bSynced: Bool) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_bSynced |
| SetSyncMaster(bMaster: Bool) | - | - |
| SetSyncMode(SyncMode: Enum(ESlaveSyncMode)) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex |
| ShouldImplementSync(out bUseSync: Bool) | - | - |
| StartSync() | - | - |
| ToggleSync() | - | - |
| ToggleSyncMaster(bManuallySet: Bool) | - | - |
| Unlock Controls() | - | GetControls, Array_Length, Less_IntInt, Array_Get, EnableInteraction, Add_IntInt |

## BP_BaseDeckControl_C: the base of every button, knob and fader

Parent `TribeNetActor`. 80 functions; variables: `UberGraphFrame`, `SM_ControlFX`, `DefaultSceneRoot`, `GrabbingHand`, `bGrabbed`, `HighlightMaterial`, `PreHighlightMaterial`, `HighlightBrightness`, `HighlightColor`, `bHighlightMaterialApplied`, `bHandHovering`, `bOnlyTickWhileGrabbed`, `OnInteractionStart`, `Label`, `SpectatorLabel`, `PreHighlightMaterialOld`, `bOnlyReplicateWhileGrabbed`, `ControlMeshDataTable`, `ControlName`, `EquipmentMesh`, `BoneName`, `BoneHighlightHue`, `SegmentTextureIndex`, `bUseHighwayHighlightHue`, `ControlInteractionType`, `bInvisibleMesh`, `HighwayHighlightHue`, `ControlInterpDelta`, `TargetControlValue`, `InterpSpeed`, `InterpTimer`, `BeatHighwayClampMin`, `BeatHighwayClampMax`, `bClampToHighwayValues`, `ControlFXRelativeTransform`, `TribeGameState`, `ControlId`, `ControlFXBaseMat`, `ControlFXDynamicMat`, `ControlFXScaleMin`, `ControlFXScaleConst`, `bInteractable`.

| Function | Kind | Calls |
|---|---|---|
| ActivateControlFX(StartPos: Double, EndPos: Double, bOneShot: Bool) | - | GetGameTimeInSeconds, SetScalarParameterValue, SetHiddenInGame, K2_SetTimerDelegate |
| ApplyHighlightMaterial(Primitive: Object(PrimitiveComponent)) | - | - |
| CanHighlight(out Interactable: Bool) | - | IsLessonLocked, BooleanOR, IsPreviewMode |
| ConstructControlId() | - | GetUniqueControlName, GetTribeEquipmentBase, Conv_NameToString, Split, Conv_StringToInt, Conv_StringToName |
| DeactivateControlFX() | - | SetHiddenInGame |
| DisableInteraction() | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex |
| EnableInteraction() | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex |
| EndInteraction() | - | - |
| GetControlId(out ControlId: Struct(TribeControlId)) | - | - |
| GetControlLabelText(out LabelText: Text) | - | - |
| GetControlValue(out Value: Double) | - | - |
| GetDefaultBeatHighwayRange(out Min: Double, out Max: Double) | - | - |
| GetHighlightPrimitive(out Primitive: Object(PrimitiveComponent), out MaintainCurrentMaterial: Bool, out HideOnUnhighlight: Bool) | - | K2_GetComponentsByClass, Array_Get |
| GetInteractOverlapPrimitive(out Overlap Primitive: Object(PrimitiveComponent)) | - | - |
| GetLabelDisplayTime(out DisplayTime: Double) | - | - |
| GetLabelWidgetClass(out LabelWidget: Class(UserWidget)) | - | - |
| GetMidiOutIndex(out Index: Int) | - | - |
| GetMidiPawn(out MidiPawn: Object(TribePawnBP_C)) | - | GetPlayerPawn |
| GetOverlapPrimitive(out Primitive: Object(PrimitiveComponent)) | - | GetHighlightPrimitive |
| GetRig(out Rig: Object(BP_Rig_C)) | - | GetTribeEquipmentBase |
| GetTribeEquipmentBase(out EquipmentBase: Object(TribeEquipmentBase)) | - | - |
| GetUniqueControlName(out ControlName: Name) | - | - |
| GetVarReplicateConditionOverrides(out OutClass: Class(Object), out OutOverrides: Array<Struct(RepConditionOverride)>) | Event | GetObjectClass |
| Grab(TribeController: Object(TribeControllers_C)) | - | - |
| HandleMidiChange(MidiValue: Double) | - | - |
| HandleMidiEvent(MidiMessageType: Enum(ETribeMidiMessageType), MidiSubAction: Enum(ETribeMidiSubAction), Value: Double, CustomData: Int) | - | HasAuthority, NotEqual_ByteByte, GetMidiPawn, GetMidiHand, Grab, Release, HandleMidiChange |
| HasHandHovering(out HandHovering: Bool) | - | - |
| HasScrollBehavior(HoveredComponent: Object(SceneComponent), out bScrollBehavior: Bool) | - | - |
| Hide Highlight() | - | - |
| HighlightOnHover(TribeController: Object(TribeControllers_C)) | - | - |
| InitControlFX() | - | CreateDynamicMaterialInstance, SetMaterial, K2_SetRelativeTransform |
| InterpToValue(Value: Double, Speed: Double) | - | K2_SetTimerDelegate |
| Is Control VFX Enabled(out Enabled: Bool) | - | IsMidiDeviceActive, BooleanOR, GetBeatHighwayState, EqualEqual_ByteByte, NotEqual_ByteByte |
| IsGrabbable(out Interactable: Bool) | - | IsLessonLocked, Not_PreBool, BooleanAND |
| IsLessonLocked(out bLessonLocked: Bool) | - | GetRig |
| IsMixerControl(out bIsMixerControl: Bool) | - | GetTribeEquipmentBase |
| IsNetInteractable(TribeControllers: Object(TribeControllers_C), out Interactable: Bool) | - | IsLocallyControlled, ReplicatesInteraction |
| IsPreviewMode(out bPreviewMode: Bool) | - | GetTribeEquipmentBase, NotEqual_ObjectObject |
| LabelGrab() | - | IsValid, Grab |
| LabelHover() | - | GetControlLabelText, TextIsEmpty, Not_PreBool, GetBeatHighwayState, EqualEqual_ByteByte, BooleanAND, IsValid, HighlightOnHover |
| LabelLeaveHover() | - | IsValid, UnhighlightOnLeaveHover |
| LabelRelease() | - | IsValid, Release |
| LoadControlState(EquipmentSaveGame: Object(TribeEquipmentSaveGame)) | - | - |
| NeedsMinimumDistance(out NeedsMinimumDistance: Bool, out MinimumDistance: Double) | - | - |
| OnClientActorsReplicated() | - | - |
| OnInteractionStart__DelegateSignature(Control: Object(BP_BaseDeckControl_C)) | - | - |
| OnRep_ControlMeshDataTable() | - | SetControlMeshes, SetControlFXTransform |
| OnRep_EquipmentMesh() | - | SetBoneNameAndTextureIndex |
| ReceiveBeginPlay() | Event | - |
| ReceiveEndPlay(EndPlayReason: Enum(EEndPlayReason)) | Event | - |
| Release(TribeController: Object(TribeControllers_C)) | - | - |
| ReplicatesInteraction(out bReplicatesInteraction: Bool) | - | LessEqual_ByteByte, BooleanOR |
| Reset() | - | HasAuthority, SetOwner |
| RestartInteraction() | - | EndInteraction, StartInteraction |
| ReturnHighlightMaterial(Primitive: Object(PrimitiveComponent)) | - | - |
| SaveControlState(EquipmentSaveGame: Object(TribeEquipmentSaveGame)) | - | - |
| SendMidiEvent(bNoteOn: Bool) | - | IsMidiDeviceActive, GetMidiOutIndex, GetControlId, SendMidiEvent |
| SetBeatHighwayClampedValues(CurrentValue: Double, NextValue: Double) | - | Less_DoubleDouble |
| SetBoneNameAndTextureIndex() | - | GetTribeEquipmentBase, GetEquipmentMeshTableIndex, GetUniqueControlName, GetControlModelInfo |
| SetBoneVisible(bVisible: Bool) | - | SetBoneVisible |
| SetControlFXTransform() | - | GetActorBounds, BreakVector, Add_DoubleDouble, BreakTransform, Divide_DoubleDouble, Multiply_DoubleDouble, FMin, Conv_DoubleToVector |
| SetControlLitState(ElementIndex: Byte, bIsLit: Bool, LitHue: Double) | - | SetElementLitState, SendMidiEvent |
| SetControlMaterials() | - | - |
| SetControlMeshes() | - | - |
| SetControlValue(Value: Double) | - | - |
| SetElementStateWithMidi(Element: Byte, TextureBlend: Float, LitState: Enum(EElementLitState), LitHue: Float, LitDesaturation: Float, bMidiLightOn: Bool) | - | SetElementState, SendMidiEvent |
| SetupControlForBeatHighway(bHighwayOn: Bool) | - | - |
| ShouldGrabOnTriggerAxis(TribeController: Object(TribeControllers_C), out bGrab: Bool) | - | - |
| ShouldReleaseBeforeReset(out bReleaseBeforeReset: Bool) | - | - |
| Show Highlight() | - | - |
| StartInteraction() | - | - |
| TickInterpControlValue() | - | GetControlValue, FInterpTo_Constant, SetControlValue, EqualEqual_DoubleDouble, K2_ClearAndInvalidateTimerHandle |
| ToggleLight(bOn: Bool) | - | IsActorBeingDestroyed, UseStaticMeshes, SetElementStateWithMidi |
| UnhighlightOnLeaveHover(TribeController: Object(TribeControllers_C)) | - | - |
| UpdateControlFX(CurrentValue: Double, DeltaSeconds: Double) | - | - |
| UpdateHighlightMaterialParams() | - | - |
| UsePersistentLabel(out bPersistent: Bool) | - | - |
| UserConstructionScript() | Event | NotEqual_ObjectObject, SetControlMeshes, SetBoneNameAndTextureIndex, GetHighlightPrimitive, IsValid, CreateDynamicMaterialInstance, SetHiddenInGame, SetScalarParameterValue |
| UseStaticMeshes(out bUseStaticMeshes: Bool) | - | IsValid, Not_PreBool |

## BP_Rig_C: the rig that holds the decks and mixer in front of you

Parent `TribeNetActor`. 74 functions; variables: `UberGraphFrame`, `EditorPreviewSkeletalMesh`, `EquipmentRoot`, `DefaultSceneRoot`, `Console`, `DeckScale`, `ChannelDevices`, `Decks`, `TribeGameInstance`, `K_EquipmentSection`, `bMixerDevicesLoaded`, `OnMixerDevicesLoaded`, `ActiveSkin`, `Apc`, `MixerDevice`, `K_MixerName`, `K_SavedControls`, `MixerChannelDevices`, `DefaultProChannelDevices`, `DefaultProMixerDevice`, `DefaultFreeChannelDevices`, `DefaultFreeMixerDevice`, `AvailableChannelDevices`, `GenericGear`, `OnControlStartInteraction`, `OnControlEndInteraction`, `AvailableMixerDevices`, `K_SpawnLayout`, `EquipmentSpawnLayout`, `bMixerScreenVisible`, `SaveSetting`, `DefaultSaveDirectory`, `OnControlReset`, `OnEquipmentSpawned`, `OnDeckScaleChanged`, `LessonManager`, `MixerScreen`, `MixerScreenSelector`, `RetainedTracks`, `bMidiModeActive`, `bLockedForLessons`.

| Function | Kind | Calls |
|---|---|---|
| CheckDevicesAllowed(Mixer: Class(TribeMixerInfo), ref Devices: Array<Class(TribeChannelDeviceInfo)>, out bAllowed: Bool, out FailureReason: Text) | - | Array_Length, Greater_IntInt, Conv_IntToInt64, Format, MakeLiteralInt, Subtract_IntInt, Array_Set, Less_IntInt |
| ClearEventBindings() | - | - |
| ClientCheckEquipmentReplicated() | - | - |
| DestroyChannelDevices(ref ChannelsToDestroy: Array<Int>) | - | Array_Length, Less_IntInt, Array_Get, NotEqual_ObjectObject, Array_RemoveItem, Add_IntInt, K2_DestroyActor, Array_Set |
| DestroyEquipment() | - | DestroyChannelDevices, DestroyMixer |
| DestroyMixer() | - | K2_DestroyActor, FlushNetDormancy, MarkPropertyDirtyFromRepIndex |
| EnforceDLCChecks(bDLCLoaded: Bool) | - | HasAuthority, GetGameMode, GetRigDeviceOverrides, CheckDevicesAllowed, MarkPropertyDirtyFromRepIndex, RefreshPreviewMode, WriteConfigString, HostGame |
| FilterControlsForSaveType(SavingDevice: Interface(DeviceSaveStateInterface_C), ref Controls: Array<Object(BP_BaseDeckControl_C)>, SaveType: Enum(E_DeviceSaveCofiguration), out ControlsToSave: Array<Object(BP_BaseDeckControl_C)>) | - | NotEqual_ByteByte, GetDefaultSaveControlNames, Array_Length, Less_IntInt, Array_Get, GetUniqueControlName, Set_Contains, Array_Add |
| GetAllControls(out Controls: Array<Object(BP_BaseDeckControl_C)>) | - | Array_Append, Array_Length, Less_IntInt, Array_Get, Add_IntInt |
| GetAvailableChannelDevices(out AllowedEquipment: Array<Class(TribeChannelDeviceInfo)>) | - | Array_Length, Less_IntInt, Array_Get, IsAndroidBuild, Not_PreBool, BooleanOR, IsDLCOwned, Array_Add |
| GetAvailableMixerDevices(out AllowedEquipment: Array<Class(TribeEquipmentInfo)>) | - | Array_Length, Less_IntInt, Array_Get, IsAndroidBuild, Not_PreBool, BooleanOR, IsDLCOwned, Array_Add |
| GetChannelConfigKey(Channel: Int, out Key: Str) | - | Add_IntInt, Conv_IntToString, Concat_StrStr |
| GetDeck(DeckIndex: Int, out Deck: Object(BP_Deck_C)) | - | Array_Get |
| GetDeckByChannel(DeckChannel: Int, out Deck: Object(BP_Deck_C)) | - | Array_Length, Less_IntInt, Array_Get, IsValid, EqualEqual_IntInt, BooleanAND, Add_IntInt |
| GetDeviceByChannel(DeckChannel: Int, out Device: Object(BP_MixerChannelDevice_C)) | - | Array_Length, Less_IntInt, Array_Get, NotEqual_ObjectObject, EqualEqual_IntInt, Add_IntInt |
| GetDJTransform() -> Struct(Transform) | - | MakeTransform |
| GetMixer(out Mixer: Object(BP_Console_C)) | - | - |
| GetNumDevices(out NumDevices: Int) | - | Array_Length, Less_IntInt, Array_Get, IsValidClass, IsValidSoftClassReference, Add_IntInt |
| GetSpectatorTransform() -> Struct(Transform) | - | MakeTransform |
| GetTeacherTransform() -> Struct(Transform) | - | MakeTransform |
| HandleEnvironmentChangedMidi(EnvironmentType: Enum(ETribeEnvironmentType), EnvironmentLevel: Object(LevelStreaming)) | - | RefreshMidiEquipmentVisible |
| HandleEquipmentSpawned() | - | HasAuthority, IsSubscriptionStatusConfirmed, RefreshPreviewMode, RefreshMidiEquipmentVisible, IsValid, SetSkin, GetMixer, SetMidiMode |
| HasCopyrightTracks(out bCopyrightAudio: Bool, out CopyrightClientName: Name) | - | Array_Length, Less_IntInt, Array_Get, NotEqual_ObjectObject, GetLoadedTrack, IsCopyright, GetStreamingClientName, Add_IntInt |
| HasUnusableStreamTracks(out bUnusableStreamingAudio: Bool, out StreamClientName: Name) | - | Array_Length, Less_IntInt, Array_Get, NotEqual_ObjectObject, GetLoadedTrack, CanLoadStreamTrack, Add_IntInt, GetStreamingClientName |
| InitEventBindings() | - | - |
| IsEquipmentLocked(out bIsLocked: Bool) | - | IsValid |
| IsEquipmentSpawned(out bSpawned: Bool) | - | IsValid, HasAuthority, GetDeck, Array_Length, Less_IntInt, Array_Get, NotEqual_ObjectObject, IsActorBeingDestroyed |
| IsValidDevice(Device: Class(TribeChannelDeviceInfo), out bValid: Bool) | - | IsValidClass, NotEqual_ClassClass |
| LoadControlStates(ref Controls: Array<Object(BP_BaseDeckControl_C)>, EquipmentSaveGame: Object(TribeEquipmentSaveGame)) | - | Array_Length, Less_IntInt, Array_Get, IsValid, LoadControlState, Add_IntInt |
| LoadDeviceStates(SaveDirectory: Str, SaveSettings: Enum(E_DeviceSaveCofiguration)) | - | LoadDeviceState, Array_Length, Less_IntInt, Array_Get, Add_IntInt |
| LoadRigAndDeviceStates(SaveDirectory: Str, bForceFullLoad: Bool) | - | LoadRigState, LoadDeviceStates, NotEqual_ByteByte |
| LoadRigConfig() | - | GetGameMode, GetRigDeviceOverrides, FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_MixerDevice, OnRep_MixerChannelDevices, LoadSpawnLayout, Array_Length |
| LoadRigState(SaveDirectory: Str) | - | LoadRigSaveGame, NotEqual_ObjectObject, GetRigState, RespawnEquipment, GreaterEqual_DoubleDouble, SetDeckScale |
| LoadSaveSetting(out LoadedSetting: Enum(E_DeviceSaveCofiguration)) | - | GetGameMode, ReadConfigString, Map_Find |
| LoadSelectedDevice(MixerChannel: Int, out SelectedDevice: Class(TribeChannelDeviceInfo)) | - | Add_IntInt, Conv_IntToString, Concat_StrStr, ReadConfigString, Array_Length, Less_IntInt, Array_Get, Conv_StringToName |
| LoadSelectedMixer(out MixerDevice: Class(TribeMixerInfo)) | - | ReadConfigString, Array_Length, Less_IntInt, Array_Get, Conv_StringToName, EqualEqual_NameName, IsTribeProSubscriptionActive, Add_IntInt |
| LoadSpawnLayout(out bLoaded: Bool, out SpawnLayout: Struct(EquipmentSpawnLayout)) | - | ReadConfigString, EquipmentLayoutFromString |
| LoadTrackToChannel(Track: Object(TribeTrack), ChannelIndex: Int, LoadingPawn: Object(TribePawnBP_C)) | - | - |
| OnControlEndInteraction__DelegateSignature(Control: Object(BP_BaseDeckControl_C)) | - | - |
| OnControlReset__DelegateSignature(Control: Object(BP_BaseDeckControl_C)) | - | - |
| OnControlStartInteraction__DelegateSignature(Control: Object(BP_BaseDeckControl_C)) | - | - |
| OnDeckScaleChanged__DelegateSignature(DeckScale: Double) | - | - |
| OnEquipmentSpawned__DelegateSignature() | - | - |
| OnMixerDevicesLoaded__DelegateSignature() | - | - |
| OnRep_DeckScale() | - | BreakVector, Subtract_DoubleDouble, Multiply_DoubleDouble, MakeVector, K2_AddRelativeLocation, Conv_DoubleToVector, SetRelativeScale3D |
| OnRep_MixerChannelDevices() | - | IsValidClass, Array_Length, GreaterEqual_IntInt, HasAuthority, RefreshMidiChannelMappings, ClientCheckEquipmentReplicated |
| OnRep_MixerDevice() | - | IsValid, IsValidSoftObjectReference, SetupForMixer, GetGameState, SetMixerScreenVisible |
| OnSubscriptionUpdated(bSuccess: Bool) | - | - |
| ReceiveBeginPlay() | Event | - |
| ReceiveDestroyed() | Event | - |
| ReceiveEndPlay(EndPlayReason: Enum(EEndPlayReason)) | Event | - |
| RefreshMidiChannelMappings() | - | GetGameState, ResetMidiChannelMap, Array_Length, Less_IntInt, Array_Get, NotEqual_ByteByte, Add_IntInt, Max |
| RefreshMidiEquipmentVisible() | - | GetGameState, GetOpenDeviceName, ShouldDeviceUseMidiMode, EqualEqual_ClassClass, EqualEqual_ByteByte, BooleanAND, Not_PreBool, SetEquipmentVisible |
| RefreshPreviewMode() | - | HasAuthority, GetGameMode, GetRigDeviceOverrides, Array_Length, Less_IntInt, Array_Get, IsValidDevice, FlushNetDormancy |
| ReleaseRetainedTracks() | - | - |
| ReleaseRetainedTracks_Delay(Delay: Double) | - | - |
| ResetControls() | - | ResetControls, Array_Length, Less_IntInt, Array_Get, Add_IntInt |
| RespawnEquipment(bOverrideConfig: Bool, ref OverrideMixerChannelDevices: Array<Class(TribeChannelDeviceInfo)>, OverrideMixerDevice: Class(TribeMixerInfo), OverrideEquipmentSpawnLayout: Str, out bSuccess: Bool) | - | HasAuthority, NotEqual_ByteByte, FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_MixerChannelDevices, OnRep_MixerDevice, IsEmpty, Array_Length |
| Save Rig State(SaveDirectory: Str) | - | EquipmentLayoutToString, MakeRigSaveGame, SaveRigState |
| SaveControlStates(ref Controls: Array<Object(BP_BaseDeckControl_C)>, EquipmentSaveGame: Object(TribeEquipmentSaveGame)) | - | Array_Length, Less_IntInt, Array_Get, SaveControlState, Add_IntInt |
| SaveDeviceStates(SaveDirectory: Str) | - | Array_Length, Less_IntInt, Array_Get, SaveDeviceState, Add_IntInt |
| SetDeckScale(Scale: Double) | - | HasAuthority, FlushNetDormancy, MarkPropertyDirtyFromRepIndex, OnRep_DeckScale |
| SetEquipmentVisible(bVisible: Bool) | - | GetMixer, NotEqual_ObjectObject, SetEquipmentVisible, Array_Length, Less_IntInt, Array_Get, Add_IntInt |
| SetLockedForLessons(bLockedForLessons: Bool) | - | FlushNetDormancy, MarkPropertyDirtyFromRepIndex |
| SetMidiModeActive(bMidiMode: Bool) | - | NotEqual_BoolBool, IsEquipmentSpawned, GetMixer, SetMidiMode, Array_Length, Less_IntInt, Array_Get, NotEqual_ObjectObject |
| SetMixerScreenVisible(bVisible: Bool) | - | IsValidSoftObjectReference, BooleanAND, IsValid, K2_DestroyActor, MakeTransform, BeginDeferredActorSpawnFromClass, SetObjectPropertyByName, FinishSpawningActor |
| SetSkin(RigSkin: Object(BP_RigSkin_C)) | - | IsEquipmentSpawned, Array_Length, Less_IntInt, Array_Get, ApplyToDeck, IsValid, ApplySkin, ApplyToMixer |
| SetupChannelDeviceSpawns() | - | Array_Length, Array_Resize, GetEquipmentLayoutSpawnTransforms, Less_IntInt, Array_Get, IsValidSoftClassReference, EqualEqual_ObjectObject, Spawn Channel Device |
| SetupMixerSpawn() | - | IsValidClass, IsValidSoftClassReference, LoadClassAsset_Blocking, SpawnMixer, PrintString |
| ShouldDeviceUseMidiMode(DeviceName: Str, out bUseMidiMode: Bool) | - | Contains |
| Spawn Channel Device(Device: Class(TribeChannelDeviceInfo), SpawnTransform: Struct(Transform), MixerChannel: Int) | - | IsValidClass, SpawnObject, IsValidSoftClassReference, LoadClassAsset_Blocking, BeginDeferredActorSpawnFromClass, SetObjectPropertyByName, SetIntPropertyByName, FinishSpawningActor |
| SpawnEquipment() | - | LoadRigConfig, SetupMixerSpawn, SetupChannelDeviceSpawns, HandleEquipmentSpawned |
| SpawnMixer(Class: Class(BP_Console_C), SpawnTransform: Struct(Transform)) | - | BeginDeferredActorSpawnFromClass, SetObjectPropertyByName, FinishSpawningActor, FlushNetDormancy, MarkPropertyDirtyFromRepIndex, K2_AttachToComponent, SetMidiMode |
