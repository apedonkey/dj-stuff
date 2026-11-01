# Tribe XR's C++: class reference

Tribe's own native modules in `libUnreal.so` (build 2304). The classes, their native function tables and their vtables are read from the binary (`scripts/NativeTables.java`): each class's registration call gives its package, name, size, constructor and parent, `StaticRegisterNatives` gives each UFunction's exec thunk, and the constructor gives the vtable. Engine virtual names come from the UE 5.4 headers (`scripts/vtable_names.py`, checked against the binary's vtable lengths). Data members come from the runtime type dump (`TribeXR.usmap`). Ghidra decompiled each exec thunk, the implementation behind it and every vtable entry a class overrides into one `.c` file per class under `D:/TribeUE/tribe_native/classes/` (`scripts/NativeDecomp.java`).

Parameters and function flags for `SuperPowered`, `TribeIntonal`, `TribeXR` come from the hook's runtime dump (`hook/native.cpp`), which also lists the functions the C++ declares and Blueprints implement (no "native" in their kind). Classes the dump didn't cover show their functions as `(…)`.

## How Tribe's C++ fits together

<!-- Hand-written; scripts/native_reference.py pastes this file into claudedocs/native_reference.md. Edit it here. -->

Class and function names below come straight from the binary's registration tables. Statements about behaviour come
from reading the decompiled code in `D:/TribeUE/tribe_native/classes/`. They are marked **(read)** where the code
shows them directly and **(inferred)** where they rest on names or on what an unnamed helper probably is.

### Audio engine (module `SuperPowered`)

- **Every sound source is a channel device.** The decks (`USuperPoweredAudioPlayer`), the sampler
  (`USuperPoweredSamplePlayer`), the acid synth (`UAcidSynthChannelDevice`) and the drum machine
  (`UDrumMachineChannelDevice`) all derive from `USuperPoweredChannelDevice`. Each one `Connect`s to a channel of
  the `USuperPoweredMixer`.
  - The base class adds 18 virtuals (slots 88 to 105).
  - Slot 101 takes a float buffer and two integers, so it is the per-block render. The deck's and the acid synth's
    overrides both have this shape **(read)**. That the integers are the frame count and the sample rate is
    **(inferred)**.
- **Sync works between devices**, not only between decks.
  - Any device can `RequestSyncMaster`, `SetSyncSlave` or `RealignBeatSync`. Key sync has its own calls
    (`IsKeySyncSlave`, `SetKeySyncEnabled`).
  - The synth takes its tempo from whichever device is sync master. It asks the mixer through
    `SuperPoweredMixer::GetSyncMaster`, then makes a virtual call on the result **(read:
    `AcidSynthChannelDevice::SuperPoweredChannelDevice_NewVirtual94`)**.
- **A deck** (`USuperPoweredAudioPlayer`, 113 functions) has a CDJ's feature set:
  - hot cues and memory cues;
  - loops: beat loops, loop in/out adjust, reloop, cut, extend;
  - beat jump, quantize, slip, reverse;
  - vinyl mode and jog/scratch (`JogBegin`/`JogTick`/`JogEnd`, `GetVinylRPM`), pitch bend;
  - master tempo (key lock), key shift, beat grids, key detection.
  
  It opens files, audio held in memory, or compressed buffers (the streaming services).
- **The mixer** (`USuperPoweredMixer`, 117 functions) mirrors a club mixer:
  - **Channel strips:** trim, 3-band EQ and curve, fader and curve, filter type/level/resonance, compressor, cue,
    crossfader assign, send level and colour.
  - **Master and crossfader:** crossfader and curve, master level/balance/cue, isolator EQ, master filter.
  - **Headphones and mic:** headphones level/mix/pre-EQ; a mic channel with EQ, effects and reverb.
  - **Effects:** Beat FX (quantized to BPM and beat intervals, X-pad, per-band EQ), Color FX pads, send FX (size,
    time, tone).
  - **Recording:** `StartRecording`/`StopRecording`.
- **Output.**
  - `USuperPoweredLibrary` runs a spatializer: listener position, room properties, left/right monitor positions and
    gain. It also has an output limiter, split output (cue to the headphones) and "headphones worn".
  - `USuperPoweredAudioIOLibrary` picks the render and capture devices (the OS default or the VR default).
- **Analysis.**
  - `USuperPoweredAnalyzer` analyses a track in the background. That this means BPM, key and waveform is
    **(inferred)** from the deck's `GetOriginalBpm`/`GetOriginalKey` and the analyzer library.
  - `USuperPoweredMetadataReader` and `USuperPoweredImageReader` read tags and cover art.
  - `USuperPoweredAnalyzerLibrary` draws waveforms into render targets and handles key names (musical names and Open Key; Tribe has no Camelot names)
    and key compatibility.

### Acid synth and drum machine (module `TribeIntonal`)

- **The acid synth.** `UAcidSynthChannelDevice` plays the TB-303-style synth whose DSP is `libacidsynth.so`.
  - Its render calls the DSP through function pointers kept in globals, passing the synth instance. It writes the
    note as a frequency (`… * 440.0`) **(read)**.
  - `UAcidSynthUniformFuncs` is `Apply` plus 17 setters. They match the 17 fields of `libacidsynth.so`'s uniforms
    struct one for one, from `SetBeatWidth` and `SetKnobCutOffFreq` to `SetEchoMix` and `SetMasterGain` **(read:
    the names in both binaries)**.
- **The drum machine.** `UDrumMachineChannelDevice` is a step sequencer with recording, quantize, a click track and
  `TriggerDrum`.
  - Its voices are a bass drum (pitch, decay, distortion, gain) and a snare (tone, snappiness, gain), plus swing
    (`UDrumMachineUniformFuncs`).
  - The samples are `UDrumMachineSample` subclasses held by `UDrumMachineSamplesSubsystem`.
- **Sequences and presets** are data assets (`UIntonalAcidSequence`, `UIntonalDrumMachineSequence`, `…Preset`).
  - They are saved with `SaveSequence`/`SavePreset` and loaded in the background (`ASyncOpen…`, `ASyncLoad…Library`).
  - The editors are UMG widgets (acid editor, drum machine editor, piano roll) on a `UIntonalWidgetComponent`.

### Tracks, library and streaming

- **Track classes.** `UTribeFile` → `UTribeTrack` → `UTribeBufferTrack` → `UTribeStreamTrack`, then one track class
  per service: Beatport, SoundCloud, Tidal and Dropbox.
  - `UTribePakTrack` is a track shipped in a pak or track pack.
  - `UTribeTempTrack` is a track received from another player.
  - Folders follow the same tree (`UTribeFolder` → `UTribeStreamFolder` → per-service folders).
- **The library.** `UTrackLibrary` (88 functions) covers:
  - playlists, history and the search index;
  - the analysis queue (`AnalyzeTrack`, a cap on how many run at once);
  - Rekordbox import (`GetRekordboxCollectionFiles`, `ImportRekordboxMetadata`) and playlist/history export;
  - adding received tracks (`AddTempTrackFromFileTransfer`).
  
  Caches are `UTrackCacheSaveGame` and `UTrackAnalysisSaveGame`.
- **The track manager.** `ATrackManager` handles the Beatport login and audio quality, and the standard folders
  (Downloads, Playlists, History, Rekordbox, Samples, User).
- **Streaming services:**
  - `UBeatportClient` (its own `Beatport` module): login, curated and user playlists, search, FLAC,
    `ReportTrackPosition`.
  - `UTribeSoundCloudClient`: OAuth, likes, playlists, play reporting.
  - `UTribeTidalClient`: the user's collection.
  - `UTribeDropboxClient`: also reads a Rekordbox library kept in Dropbox (`HandleRekordboxQuery`).
- **Paths.** `UTribePaths` builds paths from `Downloads/Tracks/`, `Downloads/Gifs/`, `TribeRecordings/`,
  `TribeTmp/`, `TribeAddons` and `../../../../Movies/` **(read: string literals)**. The last one is the Movies
  folder, where our VJ packs go **(inferred)**.

### Multiplayer, rooms and equipment

- **The game instance.** `UTribeGameInstance` (114 functions) handles:
  - sessions and rooms (`FindSessions`, `FindRoom`, `GetActiveRooms`, invites);
  - friends, leaderboards, points and levels;
  - DLC ownership, subscriptions and backend URLs. The code holds `https://live.tribexr.com` and
    `https://mixreality.tribexr.com` **(read)**.
- **Tribe's two servers.** These are the paths the app calls on each **(read: which base URL each function
  takes)**. "MixReality" looks like the internal name of Tribe's backend: it also names the DLC bucket
  (`production-mixreality-dist`) and the API types class (`UMixRealityApiTypes`) **(inferred)**.
  - `mixreality.tribexr.com` (`GetBackendURL`):
    - `/api/…`: announcements;
    - `/courier/send` (`TribeBlueprintLibrary::Courier_SendEvent`);
    - `/videocall/channels`: the video stage's channel list;
    - `/calendar/schedule/events`: the events schedule;
    - `/twitch/`: the Twitch login callback.
  - `live.tribexr.com` (`GetBackendLiveURL`):
    - `/profiles/view/` and `/profiles/edit`: DJ profile pages;
    - `/twitch/alt-login`: Twitch login from another device.
  - The server code itself isn't in the app. Only the requests the app makes are visible.
- **Sessions.** `UTribeOnlineSession` has one subclass per platform: Oculus, Steam and standalone.
- **Game framework.**
  - `ATribeGameState` switches environments and toggles passthrough and hand tracking.
  - `ATribePlayerController` drives the spectator cameras: chroma key, an auto-cam tied to beat events
    (`SetAutoCamMode`, `AutoCamResetBeatOrigin`, `OnBeatEvent`), and hiding the rig, room, table or pawns. It also
    implements the engine's kick and mute RPCs (`ClientWasKicked_Implementation`, `ClientMutePlayer_Implementation`).
  - The others are `ATribeGameMode`, `ATribePlayerState` and `ATribePawn`.
- **The network clock.** `ATribeGameState::GetServerWorldTimeSeconds` returns the engine's replicated server time
  plus a ping term on clients: `ping / 2000`, half the round trip in seconds **(read: the arithmetic)**.
  - So events scheduled on the server clock are shifted by the estimated one-way delay.
  - That the helper returns the first player's ping in milliseconds is **(inferred)**: it sits next to
    `APlayerState`'s code.
- **Networked gear.** `ATribeNetActor` is the replication base. It overrides `GetNetPriority` and the per-property
  replication conditions. Built on it:
  - `ATribeEquipmentBase` (`SpawnEquipmentMesh`, `SetMidiMode`);
  - `ATribeEquipmentMesh`: the model itself, with `GetControlModelInfo`, bone transforms and lit states. It is the
    C++ under `claudedocs/deck_catalog.md`'s control placement;
  - `ATribeHand` and `UVRBodyReplicationComponent`.
- **Sending files between players.** `UFileTransferComponent` sends a file in packets over RPC pairs (`Server_…` /
  `Client_…` for init, queue, packet (reliable and unreliable), received, finished and cancelled). This is how one
  player hands another a track, which arrives as a `UTribeTempTrack`.

### Visuals, streaming and social

- **The visuals wall.** `ATribeVisualsManager` (46 functions) drives the backdrop:
  - videos (`StreamVideoToBackdrop`, play mode), NDI input (`StreamNdiToBackdrop`), text and textures;
  - GIFs beat-matched to the BPM (`SetGifBeatmatchBPM`, beats per loop, Giphy links);
  - 360° video spheres, visuals packs, and `RefreshMediaFolders`.
- **The video "stage".** `ATribeVideoCallManager` (a 41 KB object) runs a stage queue, moves users between stage
  and audience, mutes and bans, and holds channels, workshops, and the RTMP and Twitch stream settings.
- **Streaming and social:**
  - `ATribeTwitchManager` with `UTwitchChatClient`: OAuth, chat, ingest URL, viewer count;
  - `ATribeDiscordManager`;
  - `ATribeNdiManager` / `UNDIConnection`: NDI output;
  - `AMetaverseActor`.
- **Games and lessons:**
  - `ATribeBeatHighwayManager`: the "DJ challenge" rhythm game, with recorded beat events, scoring, XP and daily
    lessons;
  - `ATribeDanceManager`, `ATribeLessonBase`;
  - `UInputReplayComponent`, which records and replays input;
  - `ATribeSpectrumAnalyzer`.
- **MIDI.** `ATribeMidiManager` opens devices, remaps channels, and sends and receives events. `UTribeMIDISubsystem`
  supports it.
- **Avatars.** `UTribeAvatarComponent`, plus Ready Player Me (`UReadyPlayerMeComponent` and its hand and head/neck
  anim instances).
- **Add-ons and DLC.** `UTribeAddon` covers lesson, track, visuals and video-sphere packs. The list of available DLC
  is fetched from `https://production-mixreality-dist.s3.us-west-1.amazonaws.com/Addons/TribeXR_AvailableDLC_UE5.json`
  **(read: a string in `UTribeGameInstance`'s code)**.

### Sources and checks

There are two independent reads of the same binary:
- **The static read** of `libUnreal.so` (`scripts/NativeTables.java`) covers all seven modules.
- **The hook's runtime dump** (`hook/native.cpp`, taken in the headset on 2026-10-27 at 04:38) covers TribeXR,
  TribeIntonal and SuperPowered.

How they compare:
- **Classes:** they agree on all 174 classes the dump covers, with the same parents and sizes.
- **Functions:** all 1,496 native function addresses match. Four names differ only in capitalization (`ASyncOpen…`
  vs `AsyncOpen…`), because Unreal's names ignore case.
- **Vtables:** the dump's run 2 to 3 entries past the end in 114 classes, into the class registration record that
  follows. So the static vtables are used.

**What the dump adds:** every function's parameters and flags. It also lists 37 functions with no C++ body. Five are
delegate signatures. The other 32 are events the C++ declares for Blueprints to implement, for example:
- the visuals wall's per-frame playback (`VideoPlaybackTick`, `GifPlaybackTick`, `NdiPlaybackTick`) and its
  play/draw mode changes;
- the beat highway's and dance game's spawning;
- Twitch's chat events;
- `TribePawn::LoadDroppedTrack`.

All of those Blueprints are decoded since 2026-10-27 evening (`claudedocs/game_systems.md`). 31 of the 32 events are
implemented there, for example `VideoPlaybackTick` in `Visuals/BP_TribeVisualsManager.txt` **(read)**.
`TribeGameInstance::PreMapTravel` is implemented nowhere: `TribeGameInstanceBP` has no such function, so the call does
nothing **(read)**.

**Still unnamed:** engine helpers that Tribe's code calls show as `FUN_` addresses, apart from `FFrame::Step` and
`FFrame::StepExplicitProperty`. Those two were named from the thunk pattern, which matches UE's `StepCompiledIn`.

**Mislabels fixed (2026-10-27 evening):** `NativeDecomp.java` names a native's implementation after the first function
its thunk calls, once the usual helpers are dropped.
- **The problem:** where the real implementation is a virtual call, that picks an engine helper instead, and the helper
  then carries the native's name at every call site.
- **The nine found:** engine-range addresses called from many classes. They are renamed in the Ghidra project
  (`scripts/RenameFunctions.java`) and in all `.c` outputs (86 files) **(read: each body)**.

| Was | Address | Is |
|---|---|---|
| `TribeDanceManager__GetReplayRoot` | 0x157c204 | `FString__FromTCHAR`: FString from a TCHAR string (222 calls) |
| `TribeBeatHighwayLane__SetupLane` | 0x173299c | `FName__FromTCHAR`: FName's constructor; static initializers name globals with it (253) |
| `FileTransferComponent__Server_AcceptFileSend` | 0x1816104 | `RPC_ValidFailed`: stores the reason; called with `L"…_Validate"` (44) |
| `FileTransferComponent__Client_NotifyPacketsReceived` | 0x18ebbf4 | `FArrayProperty__StaticClass` (27) |
| `BeatportClient__FindTrackHandle` | 0x191c7cc | `FInt64Property__StaticClass` (25) |
| `InputReplayController__DestroyNetworkActorHandled`, `TribeFile__NewVirtual90` | 0x1546068, 0x155bb10 | `ReturnZero_…`: shared `return 0` |
| `TribeAccountsManager__GetProfileName` | 0x15c4f70 | `FString__CopyFromOffset58_015c4f70`: copies the FString at +0x58, shared by several getters |
| `FileTransfer__GetDownloadBuffer` | 0x1595164 | `FUN_01595164`: an array resize helper |

The other 43 implementation names below 0x4600000 are small getters and stubs. Most are called only by their own
thunk, so their names are right where they appear. A few (at most 5 calls) are shared with identical getters of other
classes, probably through linker folding **(inferred)**.

## Modules

| Module | Classes | Functions | Native | C++ overrides |
|---|---|---|---|---|
| SuperPowered | 12 | 309 | 309 | 73 |
| TribeXR | 130 | 1103 | 1069 | 731 |
| TribeIntonal | 32 | 121 | 118 | 96 |
| TribeMIDI | 1 | 0 | 0 | 4 |
| Beatport | 2 | 22 | 22 | 5 |
| VulkanVideoMeshComponent | 1 | 0 | 0 | 9 |
| AndroidVulkanVideo | 1 | 0 | 0 | 4 |

## SuperPowered

| Class | Parent | Data members | Functions | Overrides | Decompiled |
|---|---|---|---|---|---|
| [SuperPoweredAnalyzer](#superpoweredanalyzer) | BlueprintAsyncActionBase | 5 | 1 | 3 | `SuperPowered.SuperPoweredAnalyzer.c` |
| [SuperPoweredAnalyzerLibrary](#superpoweredanalyzerlibrary) | BlueprintFunctionLibrary | 0 | 8 | 2 | `SuperPowered.SuperPoweredAnalyzerLibrary.c` |
| [SuperPoweredAudioIOLibrary](#superpoweredaudioiolibrary) | BlueprintFunctionLibrary | 0 | 7 | 2 | `SuperPowered.SuperPoweredAudioIOLibrary.c` |
| [SuperPoweredAudioInMemoryStatics](#superpoweredaudioinmemorystatics) | Object | 0 | 0 | 2 | `SuperPowered.SuperPoweredAudioInMemoryStatics.c` |
| [SuperPoweredAudioPlayer](#superpoweredaudioplayer) | SuperPoweredChannelDevice | 2 | 113 | 17 | `SuperPowered.SuperPoweredAudioPlayer.c` |
| [SuperPoweredChannelDevice](#superpoweredchanneldevice) | Object | 1 | 12 | 22 | `SuperPowered.SuperPoweredChannelDevice.c` |
| [SuperPoweredImageReader](#superpoweredimagereader) | BlueprintAsyncActionBase | 4 | 1 | 3 | `SuperPowered.SuperPoweredImageReader.c` |
| [SuperPoweredLibrary](#superpoweredlibrary) | BlueprintFunctionLibrary | 0 | 19 | 2 | `SuperPowered.SuperPoweredLibrary.c` |
| [SuperPoweredMetadataReader](#superpoweredmetadatareader) | BlueprintAsyncActionBase | 4 | 1 | 3 | `SuperPowered.SuperPoweredMetadataReader.c` |
| [SuperPoweredMixer](#superpoweredmixer) | Object | 1 | 117 | 5 | `SuperPowered.SuperPoweredMixer.c` |
| [SuperPoweredSamplePlayer](#superpoweredsampleplayer) | SuperPoweredChannelDevice | 0 | 30 | 10 | `SuperPowered.SuperPoweredSamplePlayer.c` |
| [SuperpoweredTypes](#superpoweredtypes) | Object | 0 | 0 | 2 | `SuperPowered.SuperpoweredTypes.c` |

### SuperPoweredAnalyzer

`/Script/SuperPowered.SuperPoweredAnalyzer` : `BlueprintAsyncActionBase`, 336 bytes; vtable 92 entries, 3 overridden or new.

Data members: `OnAnalysisComplete`: MulticastDelegate, `OnMetadataReady`: MulticastDelegate, `World`: Object, `Filename`: Str, `UserData`: Object.

| Function | Kind |
|---|---|
| `Analyze(WorldContextObject: Object(Object), Filename: Str, ByteOffset: Int, SizeBytes: Int, bGetMetadata: Bool, UserData: Object(Object)) -> Object(SuperPoweredAnalyzer)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `Activate`.

### SuperPoweredAnalyzerLibrary

`/Script/SuperPowered.SuperPoweredAnalyzerLibrary` : `BlueprintFunctionLibrary`, 40 bytes; vtable 88 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `CreateWaveformRenderTarget(WorldContextObject: Object(Object), Type: Enum(EWaveformType), HeightPixels: Int, DurationSeconds: Float, out PixelsPerSecond: Float) -> Object(TextureRenderTarget2D)` | native, static, Blueprint-callable |
| `GetAdjacentKeys(KeyIndex: Int, out PrevKeyIndex: Int, out NextKeyIndex: Int)` | native, static, Blueprint-callable, pure |
| `GetKeyIndexFromKeyString(KeyString: Str) -> Int` | native, static, Blueprint-callable, pure |
| `GetKeyNameFromKeyIndex(KeyIndex: Int) -> Str` | native, static, Blueprint-callable, pure |
| `GetOpenKeyNameFromKeyIndex(KeyIndex: Int) -> Str` | native, static, Blueprint-callable, pure |
| `GetOpenKeySortOrder(KeyIndex: Int) -> Int` | native, static, Blueprint-callable, pure |
| `GetSignedKeyDifference(OriginalKeyIndex: Int, CurrentKeyIndex: Int, out KeyDifference: Int)` | native, static, Blueprint-callable, pure |
| `RenderWaveformToRenderTarget(WorldContextObject: Object(Object), ref AnalysisResults: Struct(SuperPoweredAnalysisResults), ref CueData: Struct(SuperpoweredCueData), RenderTarget: Object(TextureRenderTarget2D), Type: Enum(EWaveformType), StartTime: Float)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### SuperPoweredAudioIOLibrary

`/Script/SuperPowered.SuperPoweredAudioIOLibrary` : `BlueprintFunctionLibrary`, 40 bytes; vtable 88 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `GetCaptureDeviceList() -> Array<Struct(AudioDeviceInfo)>` | native, static, Blueprint-callable, pure |
| `GetDefaultOSCaptureDeviceId() -> Str` | native, static, Blueprint-callable, pure |
| `GetDefaultOSRenderDeviceId() -> Str` | native, static, Blueprint-callable, pure |
| `GetDefaultVRCaptureDeviceId() -> Str` | native, static, Blueprint-callable, pure |
| `GetDefaultVRRenderDeviceId() -> Str` | native, static, Blueprint-callable, pure |
| `GetRenderDeviceList() -> Array<Struct(AudioDeviceInfo)>` | native, static, Blueprint-callable, pure |
| `SetDevices(renderDeviceId: Str, captureDeviceId: Str, auxDeviceId: Str)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### SuperPoweredAudioInMemoryStatics

`/Script/SuperPowered.SuperPoweredAudioInMemoryStatics` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`.

### SuperPoweredAudioPlayer

`/Script/SuperPowered.SuperPoweredAudioPlayer` : `SuperPoweredChannelDevice`, 600 bytes; vtable 106 entries, 17 overridden or new.

Data members: `OnPlayerEvent`: MulticastDelegate, `OnSlipConditionChanged`: MulticastDelegate.

| Function | Kind |
|---|---|
| `AdjustLoopIn(TimeDeltaMs: Double)` | native, Blueprint-callable |
| `AdjustLoopOut(TimeDeltaMs: Double)` | native, Blueprint-callable |
| `AutoJogBegin(bInterpScratch: Bool)` | native, Blueprint-callable |
| `BeatJump(NumBeats: Double, bWaitForBeat: Bool)` | native, Blueprint-callable |
| `CheckForPlayerEvent()` | native, Blueprint-callable |
| `ClearAllHotCues()` | native, Blueprint-callable |
| `ClearAllMemoryCues()` | native, Blueprint-callable |
| `ClearHotCue(Index: Int)` | native, Blueprint-callable |
| `ClearMemoryCue() -> Int` | native, Blueprint-callable |
| `ClearMemoryCueByIndex(Index: Int) -> Bool` | native, Blueprint-callable |
| `CreateAudioPlayer(PlayerParams: Struct(AudioPlayerParams)) -> Object(SuperPoweredAudioPlayer)` | native, static, Blueprint-callable |
| `CutLoop()` | native, Blueprint-callable |
| `EndPitchBend()` | native, Blueprint-callable |
| `ExitLoop(bForce: Bool)` | native, Blueprint-callable |
| `ExtendLoop()` | native, Blueprint-callable |
| `GetAudioPlayerMaxHotCues() -> Int` | native, Blueprint-callable, pure |
| `GetAudioPlayerMaxMemoryCues() -> Int` | native, Blueprint-callable, pure |
| `GetBeatDistanceAsTime(NumBeats: Double) -> Double` | native, Blueprint-callable, pure |
| `GetBpm() -> Double` | native, Blueprint-callable, pure |
| `GetClosestBeatMs() -> Double` | native, Blueprint-callable, pure |
| `GetCueAsTime() -> Double` | native, Blueprint-callable, pure |
| `GetCurrentBeatInt() -> Int` | native, Blueprint-callable, pure |
| `GetCurrentKeyIndex() -> Int` | native, Blueprint-callable, pure |
| `GetCurrentKeyPreKeyShift() -> Int` | native, Blueprint-callable, pure |
| `GetDisplayPosition() -> Double` | native, Blueprint-callable, pure |
| `GetDisplayTimeSeconds() -> Double` | native, Blueprint-callable, pure |
| `GetDuration() -> Double` | native, Blueprint-callable, pure |
| `GetHotCueAsTime(Index: Int, out CueMs: Double, out LengthMs: Double) -> Bool` | native, Blueprint-callable, pure |
| `GetKeySyncCentsOffset() -> Int` | native, Blueprint-callable, pure |
| `GetLoopInMs() -> Double` | native, Blueprint-callable, pure |
| `GetLoopLengthMs() -> Double` | native, Blueprint-callable, pure |
| `GetLoopOutMs() -> Double` | native, Blueprint-callable, pure |
| `GetLoopWrappedDeltaMs(StartMs: Double, EndMs: Double) -> Double` | native, Blueprint-callable, pure |
| `GetLoopWrappedPositionMs(PositionMs: Double) -> Double` | native, Blueprint-callable, pure |
| `GetMasterTempo() -> Bool` | native, Blueprint-callable, pure |
| `GetMemoryCueAsTime(Index: Int, out CueMs: Double, out LengthMs: Double) -> Bool` | native, Blueprint-callable, pure |
| `GetNextBeatPositionMs() -> Double` | native, Blueprint-callable, pure |
| `GetNextMemoryCueIndex() -> Int` | native, Blueprint-callable, pure |
| `GetOpenFileName() -> Str` | native, Blueprint-callable, pure |
| `GetOriginalBpm() -> Double` | native, Blueprint-callable, pure |
| `GetOriginalKey() -> Struct(MusicKeyInfo)` | native, Blueprint-callable, pure |
| `GetPitchShift() -> Int` | native, Blueprint-callable, pure |
| `GetPosition() -> Double` | native, Blueprint-callable, pure |
| `GetPositionAsFraction() -> Double` | native, Blueprint-callable, pure |
| `GetPreviousMemoryCueIndex() -> Int` | native, Blueprint-callable, pure |
| `GetQuantize() -> Bool` | native, Blueprint-callable, pure |
| `GetRecentEof() -> Bool` | native, Blueprint-callable, pure |
| `GetReverse() -> Bool` | native, Blueprint-callable, pure |
| `GetSamplePlayer() -> Object(SuperPoweredSamplePlayer)` | native, Blueprint-callable, pure |
| `GetSecondsToNextBar() -> Double` | native, Blueprint-callable, pure |
| `GetSecondsToNextBeat() -> Double` | native, Blueprint-callable, pure |
| `GetSlip() -> Bool` | native, Blueprint-callable, pure |
| `GetSlipCondition() -> Enum(ESlipCondition)` | native, Blueprint-callable, pure |
| `GetSlipPosition() -> Double` | native, Blueprint-callable, pure |
| `GetTempo() -> Double` | native, Blueprint-callable, pure |
| `GetVinylRPM() -> Double` | native, Blueprint-callable, pure |
| `GetVolume() -> Float` | native, Blueprint-callable, pure |
| `HasPendingJumpOnNextBeat() -> Bool` | native, Blueprint-callable, pure |
| `IsAtCue() -> Bool` | native, Blueprint-callable, pure |
| `IsLooping() -> Bool` | native, Blueprint-callable, pure |
| `IsPendingKeySyncUpdate() -> Bool` | native, Blueprint-callable, pure |
| `IsScratching() -> Bool` | native, Blueprint-callable, pure |
| `IsVinylMode() -> Bool` | native, Blueprint-callable, pure |
| `JogBegin(bAllowVinyl: Bool)` | native, Blueprint-callable |
| `JogEnd(Decelerate: Double)` | native, Blueprint-callable |
| `JogTick(DeltaTime: Float, RotationDelta: Double, MaxBendPercent: Float)` | native, Blueprint-callable |
| `LoopJump(LoopInPosition: Double, bWaitForBeat: Bool)` | native, Blueprint-callable |
| `Open(Filename: Str, ByteOffset: Int, SizeBytes: Int, bIsCopyright: Bool)` | native, Blueprint-callable |
| `OpenAudioInMemory(ref AudioInMemory: Struct(SuperpoweredAudioInMemoryWrapper), Name: Str, bIsCopyright: Bool)` | native, Blueprint-callable |
| `OpenCompressedAudioBuffer(ref CompressedAudioBuffer: Array<Byte>, Name: Str, bIsCopyright: Bool)` | native, Blueprint-callable |
| `Pause(ReleaseTime: Double)` | native, Blueprint-callable |
| `PitchBend(MaxBendPercent: Float, Faster: Bool, BendHoldMs: Int)` | native, Blueprint-callable |
| `Play()` | native, Blueprint-callable |
| `ReleaseSlippedHotCue(HotCueIndex: Int)` | native, Blueprint-callable |
| `Reloop() -> Bool` | native, Blueprint-callable |
| `ReturnToLoop() -> Bool` | native, Blueprint-callable |
| `ReturnToLoopCompensated(CommandTargetPositionMs: Double, CommandServerTimeSeconds: Double, CurrentServerTimeSeconds: Double, CommandPlaybackRate: Double) -> Bool` | native, Blueprint-callable |
| `SeekToClosestBeat(Pause: Bool)` | native, Blueprint-callable |
| `SeekToCue(AndStop: Bool)` | native, Blueprint-callable |
| `SeekToHotCue(Index: Int, AndStop: Bool, bQuantizeJumpImmediately: Bool)` | native, Blueprint-callable |
| `SeekToMemoryCue(Forwards: Bool, AndStop: Bool)` | native, Blueprint-callable |
| `SetBeatGrid(BPM: Double, firstBeatMs: Double)` | native, Blueprint-callable |
| `SetBeatLoop(NumBeats: Double, bForceUnquantized: Bool)` | native, Blueprint-callable |
| `SetBeatPlayPattern(ref BeatPlayPattern: Array<Int>, bReverse: Bool)` | native, Blueprint-callable |
| `SetCue()` | native, Blueprint-callable |
| `SetCueFromTimestamp(CueMs: Double)` | native, Blueprint-callable |
| `SetCueToFirstBeat()` | native, Blueprint-callable |
| `SetHotCue(Index: Int)` | native, Blueprint-callable |
| `SetHotCueFromTimestamp(Index: Int, CueMs: Double, LengthMs: Double)` | native, Blueprint-callable |
| `SetKeyShift(KeyShift: Int)` | native, Blueprint-callable |
| `SetKeySyncEnabled(bEnabled: Bool)` | native, Blueprint-callable |
| `SetLoopAdjustMode(LoopAdjustMode: Enum(ELoopAdjustMode))` | native, Blueprint-callable |
| `SetLoopIn()` | native, Blueprint-callable |
| `SetLoopInFromTimeStamp(LoopInMs: Double)` | native, Blueprint-callable |
| `SetLoopOut()` | native, Blueprint-callable |
| `SetLoopOutFromTimeStamp(LoopOutMs: Double)` | native, Blueprint-callable |
| `SetMasterTempo(MasterTempo: Bool)` | native, Blueprint-callable |
| `SetMemoryCue() -> Int` | native, Blueprint-callable |
| `SetMemoryCueFromTimestamp(Index: Int, CueMs: Double, LengthMs: Double)` | native, Blueprint-callable |
| `SetOriginalKey(KeyIndex: Int)` | native, Blueprint-callable |
| `SetPitchShift(PitchShiftCents: Int)` | native, Blueprint-callable |
| `SetPosition(PositionMs: Double, bForce: Bool)` | native, Blueprint-callable |
| `SetPositionFromFraction(Fraction: Double)` | native, Blueprint-callable |
| `SetPreserveSyncOffset(bPreserveSyncOffset: Bool)` | native, Blueprint-callable |
| `SetQuantize(Quantize: Bool)` | native, Blueprint-callable |
| `SetReverse(Reverse: Bool)` | native, Blueprint-callable |
| `SetScratchEndMode(bAutoEnd: Bool)` | native, Blueprint-callable |
| `SetSlip(Slip: Bool)` | native, Blueprint-callable |
| `SetTempo(Tempo: Double)` | native, Blueprint-callable |
| `SetVinylMode(VinylMode: Bool)` | native, Blueprint-callable |
| `SetVolume(Volume: Float)` | native, Blueprint-callable |
| `ShouldReconcileLoopExit(ExitPositionMs: Double, ExitServerTimeSeconds: Double, ServerTimeSeconds: Double, PlaybackRate: Double, out CompensatedExitPositionMs: Double) -> Bool` | native, Blueprint-callable |
| `UpdateCurrentKey()` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `FinishDestroy`, `SuperPoweredChannelDevice_NewVirtual90`, `SuperPoweredChannelDevice_NewVirtual91`, `SuperPoweredChannelDevice_NewVirtual92`, `SuperPoweredChannelDevice_NewVirtual93`, `SuperPoweredChannelDevice_NewVirtual94`, `SuperPoweredChannelDevice_NewVirtual95`, `SuperPoweredChannelDevice_NewVirtual96`, `SuperPoweredChannelDevice_NewVirtual97`, `SuperPoweredChannelDevice_NewVirtual98`, `SuperPoweredChannelDevice_NewVirtual99`, `SuperPoweredChannelDevice_NewVirtual101`, `SuperPoweredChannelDevice_NewVirtual103`, `SuperPoweredChannelDevice_NewVirtual104`, `SuperPoweredChannelDevice_NewVirtual105`.

### SuperPoweredChannelDevice

`/Script/SuperPowered.SuperPoweredChannelDevice` : `Object`, 64 bytes; vtable 106 entries, 22 overridden or new.

Data members: `m_mixer`: Object.

| Function | Kind |
|---|---|
| `Connect(Channel: Int, Mixer: Object(SuperPoweredMixer))` | native, Blueprint-callable |
| `Disconnect()` | native, Blueprint-callable |
| `GetConnectedMixer() -> Object(SuperPoweredMixer)` | native, Blueprint-callable, pure |
| `IsAudioCopyright() -> Bool` | native, Blueprint-callable, pure |
| `IsKeySyncSlave() -> Bool` | native, Blueprint-callable, pure |
| `IsPlaying() -> Bool` | native, Blueprint-callable, pure |
| `IsSyncMaster() -> Bool` | native, Blueprint-callable, pure |
| `IsSyncSlave() -> Bool` | native, Blueprint-callable, pure |
| `RealignBeatSync() -> Bool` | native, Blueprint-callable |
| `ReleaseSyncMaster()` | native, Blueprint-callable |
| `RequestSyncMaster() -> Bool` | native, Blueprint-callable |
| `SetSyncSlave(Mode: Enum(ESlaveSyncMode))` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginDestroy`, `IsReadyForFinishDestroy`, `NewVirtual88`, `NewVirtual89`, `NewVirtual90`, `NewVirtual91`, `NewVirtual92`, `NewVirtual93`, `NewVirtual94`, `NewVirtual95`, `NewVirtual96`, `NewVirtual97`, `NewVirtual98`, `NewVirtual99`, `NewVirtual100`, `NewVirtual101`, `NewVirtual102`, `NewVirtual103`, `NewVirtual104`, `NewVirtual105`.

### SuperPoweredImageReader

`/Script/SuperPowered.SuperPoweredImageReader` : `BlueprintAsyncActionBase`, 152 bytes; vtable 92 entries, 3 overridden or new.

Data members: `ImagesReady`: MulticastDelegate, `World`: Object, `Filename`: Str, `UserData`: Object.

| Function | Kind |
|---|---|
| `ReadTrackImages(WorldContextObject: Object(Object), Filename: Str, ByteOffset: Int, SizeBytes: Int, UserData: Object(Object)) -> Object(SuperPoweredImageReader)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `Activate`.

### SuperPoweredLibrary

`/Script/SuperPowered.SuperPoweredLibrary` : `BlueprintFunctionLibrary`, 40 bytes; vtable 88 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `GetGlobalVolume() -> Float` | native, static, Blueprint-callable, pure |
| `GetHeadphonesWorn(out Left: Bool, out Right: Bool)` | native, static, Blueprint-callable, pure |
| `GetSplitOutput(out SplitOutput: Bool)` | native, static, Blueprint-callable, pure |
| `GetSuperpoweredMaxBpm() -> Float` | native, static, Blueprint-callable, pure |
| `GetSuperpoweredMinBpm() -> Float` | native, static, Blueprint-callable, pure |
| `IsCompatibleKeys(KeyIndexA: Int, KeyIndexB: Int) -> Bool` | native, static, Blueprint-callable, pure |
| `SetGlobalVolume(Volume: Float)` | native, static, Blueprint-callable |
| `SetHeadphonesProperties(Occlusion: Float)` | native, static, Blueprint-callable |
| `SetHeadphonesWorn(Left: Bool, Right: Bool)` | native, static, Blueprint-callable |
| `SetListenerPositionAndRotation(ref Position: Struct(Vector), ref Rotation: Struct(Rotator))` | native, static, Blueprint-callable |
| `SetMonitorAmplificationLeft(AmplificationDb: Float)` | native, static, Blueprint-callable |
| `SetMonitorAmplificationRight(AmplificationDb: Float)` | native, static, Blueprint-callable |
| `SetMonitorPositionLeft(ref Position: Struct(Vector))` | native, static, Blueprint-callable |
| `SetMonitorPositionRight(ref Position: Struct(Vector))` | native, static, Blueprint-callable |
| `SetOutputLimiterEnabled(bLimiterEnabled: Bool)` | native, static, Blueprint-callable |
| `SetOutputLimiterParams(ThresholdDb: Float, CeilingDb: Float)` | native, static, Blueprint-callable |
| `SetRoomProperties(Reverb: Float)` | native, static, Blueprint-callable |
| `SetSpatializerEnabled(bEnabled: Bool)` | native, static, Blueprint-callable |
| `SetSplitOutput(SplitOutput: Bool)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### SuperPoweredMetadataReader

`/Script/SuperPowered.SuperPoweredMetadataReader` : `BlueprintAsyncActionBase`, 192 bytes; vtable 92 entries, 3 overridden or new.

Data members: `MetadataReady`: MulticastDelegate, `World`: Object, `Filename`: Str, `UserData`: Object.

| Function | Kind |
|---|---|
| `ReadTrackMetadata(WorldContextObject: Object(Object), Filename: Str, ByteOffset: Int, SizeBytes: Int, UserData: Object(Object)) -> Object(SuperPoweredMetadataReader)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `Activate`.

### SuperPoweredMixer

`/Script/SuperPowered.SuperPoweredMixer` : `Object`, 2024 bytes; vtable 88 entries, 5 overridden or new.

Data members: `OnMasterKeyChanged`: MulticastDelegate.

| Function | Kind |
|---|---|
| `Activate()` | native, Blueprint-callable |
| `AddBeatFxTime(timeMs: Double)` | native, Blueprint-callable |
| `BeatFxIntervalToFloat(FxInterval: Enum(EBeatFxTimeInterval)) -> Double` | native, static, Blueprint-callable, pure |
| `BeatFxIntervalToString(FxInterval: Enum(EBeatFxTimeInterval), FxType: Enum(EBeatFxType)) -> Str` | native, static, Blueprint-callable, pure |
| `ChannelIsAudible(Channel: Int) -> Bool` | native, Blueprint-callable, pure |
| `CreateMixer(MixerParams: Struct(MixerParams), ActivateNow: Bool) -> Object(SuperPoweredMixer)` | native, static, Blueprint-callable |
| `DisableBeatFXPad(Channel: Int, PadIndex: Int)` | native, Blueprint-callable |
| `DisableColorFXPad(Channel: Int, PadIndex: Int)` | native, Blueprint-callable |
| `GetActiveBeatFx() -> Enum(EBeatFxType)` | native, Blueprint-callable, pure |
| `GetActiveChannelFx() -> Enum(EColorFxType)` | native, Blueprint-callable, pure |
| `GetAdjacentBeatFxIntervals(out prevInterval: Enum(EBeatFxTimeInterval), out prevPrevInterval: Enum(EBeatFxTimeInterval), out nextInterval: Enum(EBeatFxTimeInterval), out nextNextInterval: Enum(EBeatFxTimeInterval))` | native, Blueprint-callable, pure |
| `GetAudioDeviceChannel(Device: Object(SuperPoweredChannelDevice)) -> Int` | native, Blueprint-callable, pure |
| `GetBeatFxBpm() -> Double` | native, Blueprint-callable, pure |
| `GetBeatFxChannel() -> Enum(EBeatFxChannel)` | native, Blueprint-callable, pure |
| `GetBeatFxEnabled() -> Bool` | native, Blueprint-callable, pure |
| `GetBeatFxLevel() -> Float` | native, Blueprint-callable, pure |
| `GetBeatFxPercentageFromTime() -> Float` | native, Blueprint-callable, pure |
| `GetBeatFxQuantize() -> Bool` | native, Blueprint-callable, pure |
| `GetBeatFxTime() -> Double` | native, Blueprint-callable, pure |
| `GetBeatFxTimeFromInterval(timeInterval: Enum(EBeatFxTimeInterval)) -> Double` | native, Blueprint-callable, pure |
| `GetBeatFxTimeInterval() -> Enum(EBeatFxTimeInterval)` | native, Blueprint-callable, pure |
| `GetBeatFxTimeIntervalRange(out Min: Enum(EBeatFxTimeInterval), out Max: Enum(EBeatFxTimeInterval))` | native, Blueprint-callable, pure |
| `GetBeatFxXPadEnabled() -> Bool` | native, Blueprint-callable, pure |
| `GetChannelColor(Channel: Int) -> Float` | native, Blueprint-callable, pure |
| `GetChannelCrossfaderAssign(Channel: Int) -> Enum(ECrossfaderAssign)` | native, Blueprint-callable, pure |
| `GetChannelCue(Channel: Int) -> Bool` | native, Blueprint-callable, pure |
| `GetChannelEq(Channel: Int, out Low: Float, out Mid: Float, out High: Float)` | native, Blueprint-callable, pure |
| `GetChannelFader(Channel: Int) -> Float` | native, Blueprint-callable, pure |
| `GetChannelFaderCurve() -> Enum(EFaderCurve)` | native, Blueprint-callable, pure |
| `GetChannelFilterType() -> Enum(EChannelFilterType)` | native, Blueprint-callable, pure |
| `GetChannelInput(Channel: Int) -> Enum(EChannelInputMode)` | native, Blueprint-callable, pure |
| `GetChannelMeter(Channel: Int, out Left: Float, out LeftHold: Float, out Right: Float, out RightHold: Float)` | native, Blueprint-callable |
| `GetChannelSendLevel(Channel: Int) -> Float` | native, Blueprint-callable, pure |
| `GetChannelTrim(Channel: Int) -> Float` | native, Blueprint-callable, pure |
| `GetClosestAndAdjacentBeatFxIntervals(out closestInterval: Enum(EBeatFxTimeInterval), out prevInterval: Enum(EBeatFxTimeInterval), out nextInterval: Enum(EBeatFxTimeInterval), out lowerThanClosest: Bool)` | native, Blueprint-callable, pure |
| `GetClosestBeatFxTimeInterval() -> Enum(EBeatFxTimeInterval)` | native, Blueprint-callable, pure |
| `GetCrossfader() -> Float` | native, Blueprint-callable, pure |
| `GetCrossfaderCurve() -> Enum(EFaderCurve)` | native, Blueprint-callable, pure |
| `GetEqCurve() -> Enum(EEqCurve)` | native, Blueprint-callable, pure |
| `GetHeadphonesLevel() -> Float` | native, Blueprint-callable, pure |
| `GetHeadphonesMix() -> Float` | native, Blueprint-callable, pure |
| `GetMasterBalance() -> Float` | native, Blueprint-callable, pure |
| `GetMasterCue() -> Bool` | native, Blueprint-callable, pure |
| `GetMasterFxMix() -> Bool` | native, Blueprint-callable, pure |
| `GetMasterKey() -> Struct(MusicKeyInfo)` | native, Blueprint-callable, pure |
| `GetMasterLevel() -> Float` | native, Blueprint-callable, pure |
| `GetMasterMeter(out Left: Float, out LeftHold: Float, out Right: Float, out RightHold: Float)` | native, Blueprint-callable |
| `GetMeterLightIndex(ref LightDbs: Array<Float>, LevelDb: Float, HoldDb: Float, out LevelIndex: Int, out HoldIndex: Int, out MidiValue: Int)` | native, static, Blueprint-callable |
| `GetMicEq(out Low: Float, out High: Float)` | native, Blueprint-callable, pure |
| `GetMicLevel() -> Float` | native, Blueprint-callable, pure |
| `GetMicMode() -> Enum(EMicMode)` | native, Blueprint-callable, pure |
| `GetNumChannels() -> Int` | native, Blueprint-callable, pure |
| `GetRecordMode() -> Enum(EMixerRecordMode)` | native, Blueprint-callable, pure |
| `GetSyncMaster() -> Object(SuperPoweredChannelDevice)` | native, Blueprint-callable, pure |
| `IsAudioCopyright() -> Bool` | native, Blueprint-callable, pure |
| `IsPercentageBasedFx(FxType: Enum(EBeatFxType)) -> Bool` | native, static, Blueprint-callable, pure |
| `IsRecording() -> Bool` | native, Blueprint-callable, pure |
| `IsRecordingReady() -> Bool` | native, Blueprint-callable, pure |
| `SetActiveBeatFx(Type: Enum(EBeatFxType))` | native, Blueprint-callable |
| `SetActiveChannelFx(Type: Enum(EColorFxType))` | native, Blueprint-callable |
| `SetActiveMicFx(Type: Enum(EBeatFxType))` | native, Blueprint-callable |
| `SetAutoBpm(autoBpm: Bool)` | native, Blueprint-callable |
| `SetBeatFxBpm(BPM: Float)` | native, Blueprint-callable |
| `SetBeatFxChannel(Channel: Enum(EBeatFxChannel))` | native, Blueprint-callable |
| `SetBeatFxEnabled(Enabled: Bool)` | native, Blueprint-callable |
| `SetBeatFxEqHigh(Enabled: Bool)` | native, Blueprint-callable |
| `SetBeatFxEqLow(Enabled: Bool)` | native, Blueprint-callable |
| `SetBeatFxEqMid(Enabled: Bool)` | native, Blueprint-callable |
| `SetBeatFxLevel(Level: Float)` | native, Blueprint-callable |
| `SetBeatFXPadEnabled(Channel: Int, PadIndex: Int, FxType: Enum(EBeatFxType), timeInterval: Enum(EBeatFxTimeInterval), Level: Float, Parameter: Float)` | native, Blueprint-callable |
| `SetBeatFxParameter(Parameter: Float)` | native, Blueprint-callable |
| `SetBeatFxQuantize(Quantize: Bool)` | native, Blueprint-callable |
| `SetBeatFxTimeInterval(timeInterval: Enum(EBeatFxTimeInterval))` | native, Blueprint-callable |
| `SetBeatFxTimeMs(timeMs: Double)` | native, Blueprint-callable |
| `SetBeatFxXPadEnabled(bEnabled: Bool)` | native, Blueprint-callable |
| `SetChannelColor(Channel: Int, Color: Float)` | native, Blueprint-callable |
| `SetChannelComp(Channel: Int, Comp: Float)` | native, Blueprint-callable |
| `SetChannelCrossfaderAssign(Channel: Int, Assign: Enum(ECrossfaderAssign))` | native, Blueprint-callable |
| `SetChannelCue(Channel: Int, Cue: Bool)` | native, Blueprint-callable |
| `SetChannelEq(Channel: Int, EQBand: Enum(EEQBand), Level: Float)` | native, Blueprint-callable |
| `SetChannelFader(Channel: Int, Fader: Float)` | native, Blueprint-callable |
| `SetChannelFaderCurve(Curve: Enum(EFaderCurve))` | native, Blueprint-callable |
| `SetChannelFilterLevel(Channel: Int, Level: Float)` | native, Blueprint-callable |
| `SetChannelFilterResonance(Resonance: Float)` | native, Blueprint-callable |
| `SetChannelFilterType(Type: Enum(EChannelFilterType))` | native, Blueprint-callable |
| `SetChannelInput(Channel: Int, Input: Enum(EChannelInputMode))` | native, Blueprint-callable |
| `SetChannelSendLevel(Channel: Int, SendLevel: Float)` | native, Blueprint-callable |
| `SetChannelTrim(Channel: Int, Trim: Float)` | native, Blueprint-callable |
| `SetColorFXPadEnabled(Channel: Int, PadIndex: Int, FxType: Enum(EColorFxType), Level: Float)` | native, Blueprint-callable |
| `SetColorFxParameter(Parameter: Float)` | native, Blueprint-callable |
| `SetCrossfader(Crossfader: Float)` | native, Blueprint-callable |
| `SetCrossfaderCurve(Curve: Enum(EFaderCurve))` | native, Blueprint-callable |
| `SetEqCurve(Curve: Enum(EEqCurve))` | native, Blueprint-callable |
| `SetHeadphonesLevel(Level: Float)` | native, Blueprint-callable |
| `SetHeadphonesMix(Mix: Float)` | native, Blueprint-callable |
| `SetHeadphonesPreEq(bPreEQ: Bool)` | native, Blueprint-callable |
| `SetMasterBalance(Balance: Float)` | native, Blueprint-callable |
| `SetMasterCue(Cue: Bool)` | native, Blueprint-callable |
| `SetMasterFilterLevel(Level: Float)` | native, Blueprint-callable |
| `SetMasterFxMix(MasterMixOn: Bool)` | native, Blueprint-callable |
| `SetMasterIsolatorEq(EQBand: Enum(EEQBand), Level: Float)` | native, Blueprint-callable |
| `SetMasterIsolatorEqEnabled(bEnabled: Bool)` | native, Blueprint-callable |
| `SetMasterLevel(Level: Float)` | native, Blueprint-callable |
| `SetMicEq(Low: Float, High: Float)` | native, Blueprint-callable |
| `SetMicFxParameter(Parameter: Float)` | native, Blueprint-callable |
| `SetMicLevel(Level: Float)` | native, Blueprint-callable |
| `SetMicMode(MicMode: Enum(EMicMode))` | native, Blueprint-callable |
| `SetMicReverbEnabled(bEnabled: Bool)` | native, Blueprint-callable |
| `SetMicReverbParameter(Parameter: Float)` | native, Blueprint-callable |
| `SetNextBeatFxTimeInterval(out selectedInterval: Enum(EBeatFxTimeInterval)) -> Bool` | native, Blueprint-callable |
| `SetPreviousBeatFxTimeInterval(out selectedInterval: Enum(EBeatFxTimeInterval)) -> Bool` | native, Blueprint-callable |
| `SetSendFxMasterMixLevel(MixLevel: Float)` | native, Blueprint-callable |
| `SetSendFxSize(Size: Float)` | native, Blueprint-callable |
| `SetSendFxTime(Time: Float)` | native, Blueprint-callable |
| `SetSendFxTone(Tone: Float)` | native, Blueprint-callable |
| `StartRecording(Directory: Str, RecordingName: Str, RecordingMode: Enum(EMixerRecordMode)) -> Bool` | native, Blueprint-callable |
| `StopRecording() -> Bool` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginDestroy`, `IsReadyForFinishDestroy`, `FinishDestroy`.

### SuperPoweredSamplePlayer

`/Script/SuperPowered.SuperPoweredSamplePlayer` : `SuperPoweredChannelDevice`, 1624 bytes; vtable 106 entries, 10 overridden or new.

| Function | Kind |
|---|---|
| `ClearSequence()` | native, Blueprint-callable |
| `ClearSequenceIndex(SequenceIndex: Int)` | native, Blueprint-callable |
| `ClearSequenceSample(SampleIndex: Int)` | native, Blueprint-callable |
| `CreateSamplePlayer() -> Object(SuperPoweredSamplePlayer)` | native, static, Blueprint-callable |
| `GetPlayerBpm() -> Float` | native, Blueprint-callable, pure |
| `GetQuantized() -> Bool` | native, Blueprint-callable, pure |
| `GetSampleFileName(SampleIndex: Int) -> Str` | native, Blueprint-callable, pure |
| `GetSamplingActive() -> Bool` | native, Blueprint-callable, pure |
| `GetSamplingIndex() -> Int` | native, Blueprint-callable, pure |
| `GetSequenceBeats() -> Int` | native, Blueprint-callable, pure |
| `GetSequenceIndex() -> Int` | native, Blueprint-callable, pure |
| `GetSequencerBpm() -> Float` | native, Blueprint-callable, pure |
| `GetSequencerEnabled() -> Bool` | native, Blueprint-callable, pure |
| `GetTempo() -> Float` | native, Blueprint-callable, pure |
| `GetVolume() -> Float` | native, Blueprint-callable, pure |
| `IsSamplePlaying(SampleIndex: Int) -> Bool` | native, Blueprint-callable, pure |
| `Open(Filename: Str, SampleIndex: Int) -> Bool` | native, Blueprint-callable |
| `Play(SampleIndex: Int)` | native, Blueprint-callable |
| `SetPlayerBpm(BPM: Float)` | native, Blueprint-callable |
| `SetQuantize(bQuantize: Bool)` | native, Blueprint-callable |
| `SetSequenceBeats(NumBeats: Int)` | native, Blueprint-callable |
| `SetSequencerEnabled(Enabled: Bool)` | native, Blueprint-callable |
| `SetSequenceSample(SequenceIndex: Int, SampleIndex: Int)` | native, Blueprint-callable |
| `SetTempo(Tempo: Float)` | native, Blueprint-callable |
| `SetVolume(Volume: Float)` | native, Blueprint-callable |
| `StartSampling(SampleIndex: Int)` | native, Blueprint-callable |
| `Stop(SampleIndex: Int)` | native, Blueprint-callable |
| `StopAll()` | native, Blueprint-callable |
| `StopSampling()` | native, Blueprint-callable |
| `StopSequencer()` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `FinishDestroy`, `SuperPoweredChannelDevice_NewVirtual90`, `SuperPoweredChannelDevice_NewVirtual91`, `SuperPoweredChannelDevice_NewVirtual92`, `SuperPoweredChannelDevice_NewVirtual101`, `SuperPoweredChannelDevice_NewVirtual102`, `SuperPoweredChannelDevice_NewVirtual103`, `SuperPoweredChannelDevice_NewVirtual104`.

### SuperpoweredTypes

`/Script/SuperPowered.SuperpoweredTypes` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`.

## TribeXR

| Class | Parent | Data members | Functions | Overrides | Decompiled |
|---|---|---|---|---|---|
| [AsyncTaskCreateTribeGif](#asynctaskcreatetribegif) | BlueprintAsyncActionBase | 3 | 2 | 4 | `TribeXR.AsyncTaskCreateTribeGif.c` |
| [AsyncTaskDownloadFile](#asynctaskdownloadfile) | BlueprintAsyncActionBase | 4 | 2 | 3 | `TribeXR.AsyncTaskDownloadFile.c` |
| [AsyncTaskDownloadTribeAnnouncements](#asynctaskdownloadtribeannouncements) | BlueprintAsyncActionBase | 2 | 1 | 5 | `TribeXR.AsyncTaskDownloadTribeAnnouncements.c` |
| [AsyncTaskDownloadTwitchEmote](#asynctaskdownloadtwitchemote) | BlueprintAsyncActionBase | 2 | 1 | 2 | `TribeXR.AsyncTaskDownloadTwitchEmote.c` |
| [AsyncTaskRunProcess](#asynctaskrunprocess) | BlueprintAsyncActionBase | 0 | 0 | 7 | `TribeXR.AsyncTaskRunProcess.c` |
| [AsyncTaskWriteImageBuffer](#asynctaskwriteimagebuffer) | BlueprintAsyncActionBase | 1 | 1 | 3 | `TribeXR.AsyncTaskWriteImageBuffer.c` |
| [BufferedSoundWaveProcedural](#bufferedsoundwaveprocedural) | SoundWaveProcedural | 0 | 1 | 4 | `TribeXR.BufferedSoundWaveProcedural.c` |
| [ConsoleAndLogWidget](#consoleandlogwidget) | UserWidget | 0 | 0 | 4 | `TribeXR.ConsoleAndLogWidget.c` |
| [DanceGridObject](#dancegridobject) | Actor | 2 | 0 | 1 | `TribeXR.DanceGridObject.c` |
| [DropboxApiTypes](#dropboxapitypes) | Object | 0 | 0 | 2 | `TribeXR.DropboxApiTypes.c` |
| [FileSendTransfer](#filesendtransfer) | FileTransfer | 1 | 0 | 2 | `TribeXR.FileSendTransfer.c` |
| [FileTransfer](#filetransfer) | Object | 5 | 2 | 3 | `TribeXR.FileTransfer.c` |
| [FileTransferComponent](#filetransfercomponent) | ActorComponent | 4 | 27 | 35 | `TribeXR.FileTransferComponent.c` |
| [InputReplayComponent](#inputreplaycomponent) | ActorComponent | 11 | 19 | 6 | `TribeXR.InputReplayComponent.c` |
| [InputReplayController](#inputreplaycontroller) | PlayerController | 0 | 0 | 3 | `TribeXR.InputReplayController.c` |
| [MetaverseActor](#metaverseactor) | Actor | 2 | 5 | 5 | `TribeXR.MetaverseActor.c` |
| [MetaverseComponent](#metaversecomponent) | ActorComponent | 5 | 2 | 2 | `TribeXR.MetaverseComponent.c` |
| [MixRealityApiTypes](#mixrealityapitypes) | Object | 0 | 0 | 2 | `TribeXR.MixRealityApiTypes.c` |
| [NDIConnection](#ndiconnection) | Object | 0 | 0 | 2 | `TribeXR.NDIConnection.c` |
| [ReadyPlayerMeComponent](#readyplayermecomponent) | SceneComponent | 11 | 8 | 12 | `TribeXR.ReadyPlayerMeComponent.c` |
| [ReadyPlayerMeHandAnimInstance](#readyplayermehandaniminstance) | AnimInstance | 12 | 1 | 2 | `TribeXR.ReadyPlayerMeHandAnimInstance.c` |
| [ReadyPlayerMeHeadNeckAnimInstance](#readyplayermeheadneckaniminstance) | AnimInstance | 1 | 0 | 5 | `TribeXR.ReadyPlayerMeHeadNeckAnimInstance.c` |
| [SoundCloudApiTypes](#soundcloudapitypes) | Object | 0 | 0 | 2 | `TribeXR.SoundCloudApiTypes.c` |
| [TidalApiTypes](#tidalapitypes) | Object | 0 | 0 | 2 | `TribeXR.TidalApiTypes.c` |
| [TrackAnalysisSaveGame](#trackanalysissavegame) | SaveGame | 1 | 0 | 2 | `TribeXR.TrackAnalysisSaveGame.c` |
| [TrackCacheSaveGame](#trackcachesavegame) | SaveGame | 3 | 0 | 2 | `TribeXR.TrackCacheSaveGame.c` |
| [TrackLibrary](#tracklibrary) | Object | 18 | 88 | 5 | `TribeXR.TrackLibrary.c` |
| [TrackManager](#trackmanager) | Actor | 5 | 18 | 6 | `TribeXR.TrackManager.c` |
| [TribeAccountSaveGame](#tribeaccountsavegame) | TribeEncryptedSaveGame | 3 | 0 | 2 | `TribeXR.TribeAccountSaveGame.c` |
| [TribeAccountsApiTypes](#tribeaccountsapitypes) | Object | 0 | 0 | 2 | `TribeXR.TribeAccountsApiTypes.c` |
| [TribeAccountsManager](#tribeaccountsmanager) | Object | 6 | 15 | 3 | `TribeXR.TribeAccountsManager.c` |
| [TribeAchievementTypes](#tribeachievementtypes) | Object | 0 | 0 | 2 | `TribeXR.TribeAchievementTypes.c` |
| [TribeAddon](#tribeaddon) | Object | 3 | 10 | 6 | `TribeXR.TribeAddon.c` |
| [TribeAddonOrder](#tribeaddonorder) | Object | 0 | 1 | 2 | `TribeXR.TribeAddonOrder.c` |
| [TribeAnalytics](#tribeanalytics) | Object | 0 | 5 | 2 | `TribeXR.TribeAnalytics.c` |
| [TribeAnchorManager](#tribeanchormanager) | Actor | 2 | 6 | 4 | `TribeXR.TribeAnchorManager.c` |
| [TribeAvailableDeviceInfo](#tribeavailabledeviceinfo) | Object | 1 | 0 | 2 | `TribeXR.TribeAvailableDeviceInfo.c` |
| [TribeAvatarComponent](#tribeavatarcomponent) | SceneComponent | 11 | 29 | 11 | `TribeXR.TribeAvatarComponent.c` |
| [TribeBeatHighwayLane](#tribebeathighwaylane) | Actor | 11 | 16 | 8 | `TribeXR.TribeBeatHighwayLane.c` |
| [TribeBeatHighwayLaneImpl](#tribebeathighwaylaneimpl) | TribeBeatHighwayLane | 8 | 6 | 6 | `TribeXR.TribeBeatHighwayLaneImpl.c` |
| [TribeBeatHighwayManager](#tribebeathighwaymanager) | Actor | 27 | 46 | 4 | `TribeXR.TribeBeatHighwayManager.c` |
| [TribeBeatHighwaySaveGame](#tribebeathighwaysavegame) | SaveGame | 3 | 0 | 2 | `TribeXR.TribeBeatHighwaySaveGame.c` |
| [TribeBeatportFolder](#tribebeatportfolder) | TribeStreamFolder | 0 | 0 | 6 | `TribeXR.TribeBeatportFolder.c` |
| [TribeBeatportTrack](#tribebeatporttrack) | TribeStreamTrack | 0 | 0 | 18 | `TribeXR.TribeBeatportTrack.c` |
| [TribeBlueprintLibrary](#tribeblueprintlibrary) | BlueprintFunctionLibrary | 0 | 74 | 2 | `TribeXR.TribeBlueprintLibrary.c` |
| [TribeBufferTrack](#tribebuffertrack) | TribeTrack | 1 | 7 | 11 | `TribeXR.TribeBufferTrack.c` |
| [TribeChannelDeviceInfo](#tribechanneldeviceinfo) | TribeEquipmentInfo | 3 | 0 | 0 | - |
| [TribeComboBoxText](#tribecomboboxtext) | Widget | 14 | 16 | 11 | `TribeXR.TribeComboBoxText.c` |
| [TribeDLCSaveGame](#tribedlcsavegame) | TribeEncryptedSaveGame | 4 | 0 | 2 | `TribeXR.TribeDLCSaveGame.c` |
| [TribeDLCTypes](#tribedlctypes) | Object | 0 | 6 | 2 | `TribeXR.TribeDLCTypes.c` |
| [TribeDanceHighwayObject](#tribedancehighwayobject) | Actor | 3 | 3 | 3 | `TribeXR.TribeDanceHighwayObject.c` |
| [TribeDanceManager](#tribedancemanager) | Actor | 22 | 28 | 3 | `TribeXR.TribeDanceManager.c` |
| [TribeDanceMap](#tribedancemap) | Object | 3 | 1 | 2 | `TribeXR.TribeDanceMap.c` |
| [TribeDanceMoveSaveGame](#tribedancemovesavegame) | SaveGame | 1 | 0 | 2 | `TribeXR.TribeDanceMoveSaveGame.c` |
| [TribeDiscordManager](#tribediscordmanager) | Actor | 0 | 5 | 2 | `TribeXR.TribeDiscordManager.c` |
| [TribeDropboxClient](#tribedropboxclient) | Object | 4 | 9 | 2 | `TribeXR.TribeDropboxClient.c` |
| [TribeDropboxFolder](#tribedropboxfolder) | TribeStreamFolder | 0 | 0 | 6 | `TribeXR.TribeDropboxFolder.c` |
| [TribeDropboxTrack](#tribedropboxtrack) | TribeStreamTrack | 0 | 10 | 16 | `TribeXR.TribeDropboxTrack.c` |
| [TribeEncryptedSaveGame](#tribeencryptedsavegame) | SaveGame | 1 | 0 | 2 | `TribeXR.TribeEncryptedSaveGame.c` |
| [TribeEnvironmentTypes](#tribeenvironmenttypes) | Object | 0 | 2 | 2 | `TribeXR.TribeEnvironmentTypes.c` |
| [TribeEquipmentBase](#tribeequipmentbase) | TribeNetActor | 4 | 3 | 8 | `TribeXR.TribeEquipmentBase.c` |
| [TribeEquipmentInfo](#tribeequipmentinfo) | Object | 10 | 1 | 3 | `TribeXR.TribeEquipmentInfo.c` |
| [TribeEquipmentLayout](#tribeequipmentlayout) | Object | 0 | 4 | 2 | `TribeXR.TribeEquipmentLayout.c` |
| [TribeEquipmentMesh](#tribeequipmentmesh) | TribeNetActor | 5 | 16 | 6 | `TribeXR.TribeEquipmentMesh.c` |
| [TribeEquipmentSaveGame](#tribeequipmentsavegame) | SaveGame | 5 | 12 | 2 | `TribeXR.TribeEquipmentSaveGame.c` |
| [TribeEvent](#tribeevent) | Object | 2 | 2 | 2 | `TribeXR.TribeEvent.c` |
| [TribeFile](#tribefile) | Object | 2 | 9 | 7 | `TribeXR.TribeFile.c` |
| [TribeFolder](#tribefolder) | Object | 10 | 15 | 4 | `TribeXR.TribeFolder.c` |
| [TribeFriend](#tribefriend) | Object | 7 | 6 | 2 | `TribeXR.TribeFriend.c` |
| [TribeGameInstance](#tribegameinstance) | GameInstance | 30 | 115 | 6 | `TribeXR.TribeGameInstance.c` |
| [TribeGameMode](#tribegamemode) | GameModeBase | 1 | 6 | 9 | `TribeXR.TribeGameMode.c` |
| [TribeGameState](#tribegamestate) | GameStateBase | 13 | 13 | 11 | `TribeXR.TribeGameState.c` |
| [TribeGif](#tribegif) | TribeFile | 7 | 17 | 4 | `TribeXR.TribeGif.c` |
| [TribeHand](#tribehand) | TribeNetActor | 3 | 13 | 5 | `TribeXR.TribeHand.c` |
| [TribeInstancedMesh](#tribeinstancedmesh) | Actor | 2 | 0 | 5 | `TribeXR.TribeInstancedMesh.c` |
| [TribeInstancedMeshComponent](#tribeinstancedmeshcomponent) | MeshComponent | 5 | 4 | 16 | `TribeXR.TribeInstancedMeshComponent.c` |
| [TribeLessonBase](#tribelessonbase) | Actor | 0 | 0 | 1 | `TribeXR.TribeLessonBase.c` |
| [TribeLessonPackAddon](#tribelessonpackaddon) | TribeAddon | 1 | 2 | 4 | `TribeXR.TribeLessonPackAddon.c` |
| [TribeMidiManager](#tribemidimanager) | Actor | 5 | 14 | 6 | `TribeXR.TribeMidiManager.c` |
| [TribeMixerInfo](#tribemixerinfo) | TribeEquipmentInfo | 5 | 0 | 2 | `TribeXR.TribeMixerInfo.c` |
| [TribeNdiManager](#tribendimanager) | Actor | 9 | 3 | 2 | `TribeXR.TribeNdiManager.c` |
| [TribeNetActor](#tribenetactor) | Actor | 1 | 1 | 4 | `TribeXR.TribeNetActor.c` |
| [TribeNetworkTypes](#tribenetworktypes) | Object | 0 | 0 | 2 | `TribeXR.TribeNetworkTypes.c` |
| [TribeOculusSession](#tribeoculussession) | TribeOnlineSession | 0 | 0 | 18 | `TribeXR.TribeOculusSession.c` |
| [TribeOnlineSession](#tribeonlinesession) | OnlineSession | 11 | 4 | 46 | `TribeXR.TribeOnlineSession.c` |
| [TribeOnlineTypes](#tribeonlinetypes) | Object | 0 | 0 | 2 | `TribeXR.TribeOnlineTypes.c` |
| [TribePakFile](#tribepakfile) | TribeFile | 0 | 0 | 5 | `TribeXR.TribePakFile.c` |
| [TribePakFolder](#tribepakfolder) | TribeStreamFolder | 1 | 0 | 3 | `TribeXR.TribePakFolder.c` |
| [TribePakTrack](#tribepaktrack) | TribeTrack | 0 | 0 | 8 | `TribeXR.TribePakTrack.c` |
| [TribePaths](#tribepaths) | Object | 0 | 19 | 2 | `TribeXR.TribePaths.c` |
| [TribePawn](#tribepawn) | Pawn | 8 | 23 | 22 | `TribeXR.TribePawn.c` |
| [TribePlayerController](#tribeplayercontroller) | PlayerController | 19 | 21 | 8 | `TribeXR.TribePlayerController.c` |
| [TribePlayerState](#tribeplayerstate) | PlayerState | 10 | 23 | 12 | `TribeXR.TribePlayerState.c` |
| [TribePlayerStats](#tribeplayerstats) | TribeEncryptedSaveGame | 2 | 0 | 2 | `TribeXR.TribePlayerStats.c` |
| [TribeReplaySaveGame](#tribereplaysavegame) | SaveGame | 3 | 8 | 2 | `TribeXR.TribeReplaySaveGame.c` |
| [TribeRigSaveGame](#triberigsavegame) | SaveGame | 4 | 5 | 2 | `TribeXR.TribeRigSaveGame.c` |
| [TribeRoom](#triberoom) | Object | 6 | 20 | 2 | `TribeXR.TribeRoom.c` |
| [TribeSkinTypes](#tribeskintypes) | Object | 0 | 0 | 2 | `TribeXR.TribeSkinTypes.c` |
| [TribeSortingClient](#tribesortingclient) | BlueprintAsyncActionBase | 9 | 4 | 3 | `TribeXR.TribeSortingClient.c` |
| [TribeSoundCloudClient](#tribesoundcloudclient) | Object | 4 | 20 | 2 | `TribeXR.TribeSoundCloudClient.c` |
| [TribeSoundCloudFolder](#tribesoundcloudfolder) | TribeStreamFolder | 0 | 0 | 4 | `TribeXR.TribeSoundCloudFolder.c` |
| [TribeSoundCloudTrack](#tribesoundcloudtrack) | TribeStreamTrack | 0 | 2 | 18 | `TribeXR.TribeSoundCloudTrack.c` |
| [TribeSpectrumAnalyzer](#tribespectrumanalyzer) | Actor | 8 | 9 | 5 | `TribeXR.TribeSpectrumAnalyzer.c` |
| [TribeStandaloneSession](#tribestandalonesession) | TribeOnlineSession | 0 | 0 | 9 | `TribeXR.TribeStandaloneSession.c` |
| [TribeSteamSession](#tribesteamsession) | TribeOnlineSession | 0 | 0 | 13 | `TribeXR.TribeSteamSession.c` |
| [TribeStreamFolder](#tribestreamfolder) | TribeFolder | 1 | 4 | 7 | `TribeXR.TribeStreamFolder.c` |
| [TribeStreamTrack](#tribestreamtrack) | TribeBufferTrack | 2 | 7 | 14 | `TribeXR.TribeStreamTrack.c` |
| [TribeSubtitles](#tribesubtitles) | Object | 0 | 2 | 2 | `TribeXR.TribeSubtitles.c` |
| [TribeTempTrack](#tribetemptrack) | TribeBufferTrack | 1 | 0 | 7 | `TribeXR.TribeTempTrack.c` |
| [TribeTidalClient](#tribetidalclient) | Object | 3 | 7 | 2 | `TribeXR.TribeTidalClient.c` |
| [TribeTidalFolder](#tribetidalfolder) | TribeStreamFolder | 0 | 0 | 6 | `TribeXR.TribeTidalFolder.c` |
| [TribeTidalTrack](#tribetidaltrack) | TribeStreamTrack | 0 | 2 | 17 | `TribeXR.TribeTidalTrack.c` |
| [TribeTrack](#tribetrack) | TribeFile | 14 | 37 | 20 | `TribeXR.TribeTrack.c` |
| [TribeTrackPackAddon](#tribetrackpackaddon) | TribeAddon | 2 | 1 | 6 | `TribeXR.TribeTrackPackAddon.c` |
| [TribeTwitchManager](#tribetwitchmanager) | Actor | 9 | 19 | 7 | `TribeXR.TribeTwitchManager.c` |
| [TribeVideoCallChannel](#tribevideocallchannel) | Object | 6 | 4 | 2 | `TribeXR.TribeVideoCallChannel.c` |
| [TribeVideoCallChannelRoom](#tribevideocallchannelroom) | Object | 2 | 0 | 2 | `TribeXR.TribeVideoCallChannelRoom.c` |
| [TribeVideoCallManager](#tribevideocallmanager) | Actor | 45 | 57 | 11 | `TribeXR.TribeVideoCallManager.c` |
| [TribeVideoCallPresenter](#tribevideocallpresenter) | Object | 5 | 0 | 2 | `TribeXR.TribeVideoCallPresenter.c` |
| [TribeVideoCallSchedule](#tribevideocallschedule) | Actor | 2 | 7 | 3 | `TribeXR.TribeVideoCallSchedule.c` |
| [TribeVideoCallScreen](#tribevideocallscreen) | Actor | 9 | 1 | 3 | `TribeXR.TribeVideoCallScreen.c` |
| [TribeVideoCallUser](#tribevideocalluser) | Object | 29 | 0 | 2 | `TribeXR.TribeVideoCallUser.c` |
| [TribeVideoCallUserInfo](#tribevideocalluserinfo) | Object | 4 | 3 | 2 | `TribeXR.TribeVideoCallUserInfo.c` |
| [TribeVideoSphere](#tribevideosphere) | Actor | 6 | 6 | 3 | `TribeXR.TribeVideoSphere.c` |
| [TribeVideoSphereAddon](#tribevideosphereaddon) | TribeAddon | 0 | 0 | 4 | `TribeXR.TribeVideoSphereAddon.c` |
| [TribeVisualsManager](#tribevisualsmanager) | Actor | 25 | 52 | 4 | `TribeXR.TribeVisualsManager.c` |
| [TribeVisualsPackAddon](#tribevisualspackaddon) | TribeAddon | 0 | 0 | 5 | `TribeXR.TribeVisualsPackAddon.c` |
| [TwitchApiTypes](#twitchapitypes) | Object | 0 | 1 | 2 | `TribeXR.TwitchApiTypes.c` |
| [TwitchChatClient](#twitchchatclient) | Object | 0 | 0 | 2 | `TribeXR.TwitchChatClient.c` |
| [VRBodyReplicationComponent](#vrbodyreplicationcomponent) | ActorComponent | 9 | 6 | 12 | `TribeXR.VRBodyReplicationComponent.c` |

### AsyncTaskCreateTribeGif

`/Script/TribeXR.AsyncTaskCreateTribeGif` : `BlueprintAsyncActionBase`, 184 bytes; vtable 92 entries, 4 overridden or new.

Data members: `OnSuccess`: MulticastDelegate, `OnFailure`: MulticastDelegate, `ProducedGif`: Object.

| Function | Kind |
|---|---|
| `CreateTribeGif(WorldContextObject: Object(Object), GifFile: Str, DeleteGifFile: Bool) -> Object(AsyncTaskCreateTribeGif)` | native, static, Blueprint-callable |
| `LoadTribeGif(WorldContextObject: Object(Object), GifObject: Object(TribeGif)) -> Object(AsyncTaskCreateTribeGif)` | native, static |

C++ overrides: `Destructor`, `DeletingDestructor`, `Activate`, `SetReadyToDestroy`.

### AsyncTaskDownloadFile

`/Script/TribeXR.AsyncTaskDownloadFile` : `BlueprintAsyncActionBase`, 168 bytes; vtable 92 entries, 3 overridden or new.

Data members: `OnProgress`: MulticastDelegate, `OnBufferReady`: MulticastDelegate, `OnSuccess`: MulticastDelegate, `OnFailure`: MulticastDelegate.

| Function | Kind |
|---|---|
| `DownloadFile(URL: Str, SaveDirectory: Str, SaveFileName: Str) -> Object(AsyncTaskDownloadFile)` | native, static, Blueprint-callable |
| `DownloadFileToBuffer(URL: Str) -> Object(AsyncTaskDownloadFile)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `Activate`.

### AsyncTaskDownloadTribeAnnouncements

`/Script/TribeXR.AsyncTaskDownloadTribeAnnouncements` : `BlueprintAsyncActionBase`, 88 bytes; vtable 92 entries, 5 overridden or new.

Data members: `OnSuccess`: MulticastDelegate, `OnFailure`: MulticastDelegate.

| Function | Kind |
|---|---|
| `DownloadTribeAnnouncements(GameInstance: Object(GameInstance)) -> Object(AsyncTaskDownloadTribeAnnouncements)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `Activate`, `SetReadyToDestroy`, `RegisterWithGameInstance`.

### AsyncTaskDownloadTwitchEmote

`/Script/TribeXR.AsyncTaskDownloadTwitchEmote` : `BlueprintAsyncActionBase`, 104 bytes; vtable 92 entries, 2 overridden or new.

Data members: `OnSuccess`: MulticastDelegate, `OnFail`: MulticastDelegate.

| Function | Kind |
|---|---|
| `DownloadTwitchEmote(ref EmoteInstance: Struct(TwitchEmoteInstance), ResolutionMultiplier: Float) -> Object(AsyncTaskDownloadTwitchEmote)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### AsyncTaskRunProcess

`/Script/TribeXR.AsyncTaskRunProcess` : `BlueprintAsyncActionBase`, 136 bytes; vtable 96 entries, 7 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`, `SetReadyToDestroy`, `NewVirtual92`, `NewVirtual93`, `NewVirtual94`, `NewVirtual95`.

### AsyncTaskWriteImageBuffer

`/Script/TribeXR.AsyncTaskWriteImageBuffer` : `BlueprintAsyncActionBase`, 136 bytes; vtable 92 entries, 3 overridden or new.

Data members: `OnImageBufferWriteResult`: MulticastDelegate.

| Function | Kind |
|---|---|
| `WriteImageBuffer(WorldContextObject: Object(Object), ref RawImage: Array<Byte>, bResize: Bool, ResizeWidth: Int, ResizeHeight: Int) -> Object(AsyncTaskWriteImageBuffer)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `Activate`.

### BufferedSoundWaveProcedural

`/Script/TribeXR.BufferedSoundWaveProcedural` : `SoundWaveProcedural`, 1216 bytes; vtable 139 entries, 4 overridden or new.

| Function | Kind |
|---|---|
| `SeekSeconds(TimeSeconds: Float)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `OnBeginGenerate`, `OnGeneratePCMAudio`.

### ConsoleAndLogWidget

`/Script/TribeXR.ConsoleAndLogWidget` : `UserWidget`, 752 bytes; vtable 161 entries, 4 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`, `ReleaseSlateResources`, `RebuildWidget`.

### DanceGridObject

`/Script/TribeXR.DanceGridObject` : `Actor`, 672 bytes; vtable 228 entries, 1 overridden or new.

Data members: `GridMaterial`: Object, `bCenterMarker`: Bool.

C++ overrides: `Destructor`.

### DropboxApiTypes

`/Script/TribeXR.DropboxApiTypes` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`.

### FileSendTransfer

`/Script/TribeXR.FileSendTransfer` : `FileTransfer`, 496 bytes; vtable 88 entries, 2 overridden or new.

Data members: `SentFile`: Object.

C++ overrides: `Destructor`, `DeletingDestructor`.

### FileTransfer

`/Script/TribeXR.FileTransfer` : `Object`, 328 bytes; vtable 88 entries, 3 overridden or new.

Data members: `Filename`: Str, `FilePath`: Str, `FileByteOffset`: Int64, `OnFileTransferUpdate`: MulticastDelegate, `OnFileTransferComplete`: MulticastDelegate.

| Function | Kind |
|---|---|
| `GetDownloadBuffer() -> Array<Byte>` | native, Blueprint-callable, pure |
| `GetFileSize() -> Int` | native, Blueprint-callable, pure |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginDestroy`.

### FileTransferComponent

`/Script/TribeXR.FileTransferComponent` : `ActorComponent`, 296 bytes; vtable 185 entries, 35 overridden or new.

Data members: `OnFileTransferStarted`: MulticastDelegate, `ActiveSendTransfer`: Object, `ActiveReceiveTransfer`: Object, `TransferQueue`: Array<Object>.

| Function | Kind |
|---|---|
| `CancelFileTransfer(Filename: Str)` | native, Blueprint-callable |
| `Client_AcceptFileSend(Filename: Str)` | native, event, client RPC |
| `Client_InitFileTransfer(Filename: Str, FileHash: Str, FileSizeBytes: Int, CompressedSizeBytes: Int)` | native, event, client RPC |
| `Client_NotifyFileReceived(Filename: Str, bSuccess: Bool)` | native, event, client RPC |
| `Client_NotifyPacketReceived(PacketIndex: Int)` | native, event, client RPC |
| `Client_NotifyPacketReceived_Reliable(PacketIndex: Int)` | native, event, client RPC |
| `Client_NotifyPacketsReceived(ref PacketIndices: Array<Int>)` | native, event, client RPC |
| `Client_NotifySendFinished(Filename: Str, bSuccess: Bool)` | native, event, client RPC |
| `Client_NotifyTransferCancelled(Filename: Str)` | native, event, client RPC |
| `Client_QueueFileReceive(Filename: Str)` | native, event, client RPC |
| `Client_SendFilePacket(PacketIndex: Int, ref PacketData: Array<Byte>)` | native, event, client RPC |
| `FindPendingTransfer(Filename: Str) -> Object(FileTransfer)` | native, Blueprint-callable, pure |
| `GetActiveReceiveTransfer() -> Object(FileTransfer)` | native, Blueprint-callable, pure |
| `GetActiveSendTransfer() -> Object(FileTransfer)` | native, Blueprint-callable, pure |
| `IsAllowedFileType(Filename: Str) -> Bool` | native, Blueprint-callable, pure |
| `Server_AcceptFileSend(Filename: Str)` | native, event, server RPC |
| `Server_InitFileTransfer(Filename: Str, FileHash: Str, FileSizeBytes: Int, CompressedSizeBytes: Int)` | native, event, server RPC |
| `Server_NotifyFileReceived(Filename: Str, bSuccess: Bool)` | native, event, server RPC |
| `Server_NotifyPacketReceived(PacketIndex: Int)` | native, event, server RPC |
| `Server_NotifyPacketReceived_Reliable(PacketIndex: Int)` | native, event, server RPC |
| `Server_NotifyPacketsReceived(ref PacketIndices: Array<Int>)` | native, event, server RPC |
| `Server_NotifySendFinished(Filename: Str, bSuccess: Bool)` | native, event, server RPC |
| `Server_NotifyTransferCancelled(Filename: Str)` | native, event, server RPC |
| `Server_QueueFileReceive(Filename: Str)` | native, event, server RPC |
| `Server_SendFilePacket(PacketIndex: Int, ref PacketData: Array<Byte>)` | native, event, server RPC |
| `StartFileSend(FilePath: Str) -> Object(FileSendTransfer)` | native, Blueprint-callable |
| `StartTribeFileSend(SendFile: Object(TribeFile)) -> Object(FileSendTransfer)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginPlay`, `EndPlay`, `TickComponent`, `NewVirtual155`, `NewVirtual156`, `NewVirtual157`, `NewVirtual158`, `NewVirtual159`, `NewVirtual160`, `NewVirtual161`, `NewVirtual162`, `NewVirtual163`, `NewVirtual164`, `NewVirtual165`, `NewVirtual166`, `NewVirtual167`, `NewVirtual168`, `NewVirtual169`, `NewVirtual170`, `NewVirtual171`, `NewVirtual172`, `NewVirtual173`, `NewVirtual174`, `NewVirtual175`, `NewVirtual176`, `NewVirtual177`, `NewVirtual178`, `NewVirtual179`, `NewVirtual180`, `NewVirtual181`, `NewVirtual182`, `NewVirtual183`, `NewVirtual184`.

### InputReplayComponent

`/Script/TribeXR.InputReplayComponent` : `ActorComponent`, 520 bytes; vtable 155 entries, 6 overridden or new.

Data members: `TimeBetweenPositionCaptures`: Float, `bRecording`: Bool, `InputCaptureComponent`: Object, `OnPlaybackFinished`: MulticastDelegate, `OnTimestampTriggered`: MulticastDelegate, `CurrentPlaybackTime`: Float, `CurrentPlaybackIndex`: Int, `CurrentReplaySpeed`: Float, `RelativeComponents`: Array<Object>, `WorldComponents`: Array<Object>, `OwningPlayerInput`: Object.

| Function | Kind |
|---|---|
| `AddTimestamp(ReplayName: Str, Timestamp: Float) -> Bool` | native, Blueprint-callable |
| `CancelRecording()` | native, Blueprint-callable |
| `CropReplay(ReplayName: Str, StartTime: Float, EndTime: Float) -> Bool` | native, Blueprint-callable |
| `GetGameModeReplayFiles(out OutFilenames: Array<Str>)` | native, static, Blueprint-callable |
| `GetInputReplayFiles(out OutFilenames: Array<Str>)` | native, static, Blueprint-callable |
| `GetInputReplayPath() -> Str` | native, static, Blueprint-callable, pure |
| `GetPlaybackPercentage() -> Float` | native, Blueprint-callable, pure |
| `IsPlaying() -> Bool` | native, Blueprint-callable, pure |
| `IsRecording() -> Bool` | native, Blueprint-callable, pure |
| `IsRecordingPaused() -> Bool` | native, Blueprint-callable, pure |
| `IsReplayLoaded() -> Bool` | native, Blueprint-callable, pure |
| `LoadReplay(ReplayName: Str) -> Bool` | native, Blueprint-callable |
| `RemoveTimestamp(ReplayName: Str, TimestampIndex: Int) -> Bool` | native, Blueprint-callable |
| `SetCapturedComponents(RecordedWorldComponents: Array<Object(SceneComponent)>, RecordedRelativeComponents: Array<Object(SceneComponent)>)` | native, Blueprint-callable |
| `StartPlayback(ReplayName: Str, StartTime: Float, bLoop: Bool, bAndLoad: Bool, ReplaySpeed: Float) -> Bool` | native, Blueprint-callable |
| `StartRecording(bRestart: Bool)` | native, Blueprint-callable |
| `StopPlayback()` | native, Blueprint-callable |
| `StopRecording(SaveName: Str)` | native, Blueprint-callable |
| `StoreTimestamp(Timestamp: Float)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `OnRegister`, `OnUnregister`, `BeginPlay`, `TickComponent`.

### InputReplayController

`/Script/TribeXR.InputReplayController` : `PlayerController`, 2136 bytes; vtable 503 entries, 3 overridden or new.

C++ overrides: `Destructor`, `K2_DestroyActor`, `DestroyNetworkActorHandled`.

### MetaverseActor

`/Script/TribeXR.MetaverseActor` : `Actor`, 720 bytes; vtable 228 entries, 5 overridden or new.

Data members: `MetaverseComponent`: Object, `TribeSpectrumAnalyzer`: Object.

| Function | Kind |
|---|---|
| `RespondToBeatSignal(CurrentBPM: Float, BeatNumber: Int, Timestamp: Float)` | native, Blueprint-callable |
| `RespondToBeatSpectrumAnalysis(BeatSpectrumAnalysis: Array<Float>)` | native, Blueprint-callable |
| `RespondToBPMUpdate(BeatMatchBPM: Float, SecondsToNextBar: Float)` | native, Blueprint-callable |
| `RespondToNewTrackLoaded(NewTrackLoaded: Object(TribeTrack))` | native, Blueprint-callable |
| `SpectrumAnalysisRequest()` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginPlay`, `PostActorCreated`, `Tick`.

### MetaverseComponent

`/Script/TribeXR.MetaverseComponent` : `ActorComponent`, 224 bytes; vtable 155 entries, 2 overridden or new.

Data members: `OnBeatSignal`: MulticastDelegate, `OnRequestSpectrumAnalysis`: MulticastDelegate, `OnBeatSpectrumAnalysis`: MulticastDelegate, `VideoCallManager`: Object, `TribeSpectrumAnalyzer`: Object.

| Function | Kind |
|---|---|
| `Connect()` | native, Blueprint-callable |
| `OnNewMetaverseActionHandler(MessageText: Str, UserId: Int)` | native |

C++ overrides: `Destructor`, `DeletingDestructor`.

### MixRealityApiTypes

`/Script/TribeXR.MixRealityApiTypes` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`.

### NDIConnection

`/Script/TribeXR.NDIConnection` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`.

### ReadyPlayerMeComponent

`/Script/TribeXR.ReadyPlayerMeComponent` : `SceneComponent`, 976 bytes; vtable 200 entries, 12 overridden or new.

Data members: `ReadyPlayerMeHandsAnimBlueprintClass`: Object, `AvatarMeshComponent`: Object, `RightHandMeshComponent`: Object, `LeftHandMeshComponent`: Object, `RightHandMesh`: Object, `LeftHandMesh`: Object, `RightHandMaterial`: Object, `LeftHandMaterial`: Object, `PendingAvatarAsset`: Object, `ReplicatedVisemeData`: Struct(ReadyPlayerMeVisemePacket), `ReplicatedInputData`: Struct(ReadyPlayerMeInputPacket).

| Function | Kind |
|---|---|
| `AsyncLoadRPMAvatarThumbnail(AvatarId: Str, ref OnImageResult: Delegate(ReadyPlayerMeImageDelegate__DelegateSignature))` | native, static, Blueprint-callable |
| `HandleAvatarAssetLoaded(AvatarAsset: Object(glTFRuntimeAsset), AssetUrl: Str)` | native |
| `HandleAvatarMetadata(ref QueriedAvatarMetadata: Struct(AvatarMetadata), QueriedAvatarUrl: Str)` | native |
| `HandleAvatarSkeletonLoaded(LoadedSkeletalMesh: Object(SkeletalMesh))` | native |
| `OnRep_InputPacketData()` | native |
| `OnRep_VisemePacketData()` | native |
| `Server_HandleInputPacket(ref PacketData: Struct(ReadyPlayerMeInputPacket))` | native, event, server RPC |
| `Server_HandleVisemePacket(ref PacketData: Struct(ReadyPlayerMeVisemePacket))` | native, event, server RPC |

C++ overrides: `Destructor`, `DeletingDestructor`, `GetLifetimeReplicatedProps`, `ValidateGeneratedRepEnums`, `TickComponent`, `OnComponentDestroyed`, `OnVisibilityChanged`, `OnHiddenInGameChanged`, `NewVirtual196`, `NewVirtual197`, `NewVirtual198`, `NewVirtual199`.

### ReadyPlayerMeHandAnimInstance

`/Script/TribeXR.ReadyPlayerMeHandAnimInstance` : `AnimInstance`, 1040 bytes; vtable 114 entries, 2 overridden or new.

Data members: `HandMotionComponent`: Object, `HandOffsetComponent`: Object, `InputComponent`: Object, `SimulatedInput`: Object, `bRightHand`: Bool, `Grip`: Float, `Trigger`: Float, `bPoint`: Bool, `PointBlend`: Float, `bThumbsUp`: Bool, `ThumbsUpBlend`: Float, `RootXform`: Struct(Transform).

| Function | Kind |
|---|---|
| `UpdateAnimationProperties(DeltaTime: Float)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `NativeInitializeAnimation`.

### ReadyPlayerMeHeadNeckAnimInstance

`/Script/TribeXR.ReadyPlayerMeHeadNeckAnimInstance` : `AnimInstance`, 2960 bytes; vtable 114 entries, 5 overridden or new.

Data members: `HeadComponent`: Object.

C++ overrides: `Destructor`, `DeletingDestructor`, `NativeInitializeAnimation`, `CreateAnimInstanceProxy`, `DestroyAnimInstanceProxy`.

### SoundCloudApiTypes

`/Script/TribeXR.SoundCloudApiTypes` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TidalApiTypes

`/Script/TribeXR.TidalApiTypes` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TrackAnalysisSaveGame

`/Script/TribeXR.TrackAnalysisSaveGame` : `SaveGame`, 168 bytes; vtable 88 entries, 2 overridden or new.

Data members: `Analysis`: Struct(SuperPoweredAnalysisResults).

C++ overrides: `Destructor`, `DeletingDestructor`.

### TrackCacheSaveGame

`/Script/TribeXR.TrackCacheSaveGame` : `SaveGame`, 280 bytes; vtable 88 entries, 2 overridden or new.

Data members: `MetaData`: Map<Name,Struct(TribeTrackMetadata)>, `BeatGrids`: Map<Name,Struct(SuperPoweredBeatGridData)>, `PlayerMemories`: Map<Name,Struct(TribePlayerMemory)>.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TrackLibrary

`/Script/TribeXR.TrackLibrary` : `Object`, 960 bytes; vtable 88 entries, 5 overridden or new.

Data members: `Tracks`: Map<Str,Object>, `RetainedTracks`: Map<Object,Struct(TribeTrackRetainer)>, `ActiveTrackPackAddons`: Map<Object,Object>, `OnAnalysisQueueUpdated`: MulticastDelegate, `OnPlaylistLoaded`: MulticastDelegate, `StreamingServices`: Map<Name,Struct(MusicStreamingService)>, `SamplesFolder`: Object, `UserFolder`: Object, `DownloadsFolder`: Object, `RekordboxFolder`: Object, `PlaylistsFolder`: Object, `RecordingsFolder`: Object, `EditablePlaylistsFolder`: Object, `TempFolder`: Object, `LessonTracksFolder`: Object, `TrackCache`: Object, `HistoryFolder`: Object, `LastSessionPlaylist`: Object.

| Function | Kind |
|---|---|
| `AddDropboxSharedTrack(Filename: Str, SharedUrl: Str, FileOwner: Object(TribePlayerController)) -> Object(TribeStreamTrack)` | native, Blueprint-callable |
| `AddFolderTree(FolderPath: Str, ParentFolder: Object(TribeFolder)) -> Object(TribeFolder)` | native, Blueprint-callable |
| `AddLessonPackTracks(FolderPath: Str)` | native, Blueprint-callable |
| `AddNewPlaylist(PlaylistName: Str) -> Object(TribeFolder)` | native, Blueprint-callable |
| `AddPakTrackFromFile(Filename: Str, ParentFolder: Object(TribeFolder)) -> Object(TribePakTrack)` | native, Blueprint-callable |
| `AddPlaylist(ref PlaylistData: Struct(TribePlaylist), bEditable: Bool) -> Object(TribeFolder)` | native, Blueprint-callable |
| `AddStreamTrack(Filename: Str, ClientName: Name) -> Object(TribeStreamTrack)` | native, Blueprint-callable |
| `AddTempTrackFromFileTransfer(FileTransfer: Object(FileTransfer)) -> Object(TribeTrack)` | native, Blueprint-callable |
| `AddTrackAnalysisToSearch(Track: Object(TribeTrack))` | native, Blueprint-callable |
| `AddTrackFromFile(Filename: Str, ParentFolder: Object(TribeFolder)) -> Object(TribeTrack)` | native, Blueprint-callable |
| `AddTrackMetadataToSearch(Track: Object(TribeTrack))` | native, Blueprint-callable |
| `AddTrackPackAddon(TrackPackAddon: Object(TribeTrackPackAddon))` | native, Blueprint-callable |
| `AddTrackSearchTerm(Track: Object(TribeTrack), SearchTerm: Str)` | native, Blueprint-callable |
| `AddTrackToHistory(Track: Object(TribeTrack))` | native, Blueprint-callable |
| `AddTrackToPlaylistFolder(PlaylistFolder: Object(TribeFolder), Track: Object(TribeTrack))` | native, Blueprint-callable |
| `AnalyzeTrack(Track: Object(TribeTrack))` | native, Blueprint-callable |
| `AnalyzeTrack_Forced(Track: Object(TribeTrack))` | native, Blueprint-callable |
| `AutosaveTrackHistory()` | native, Blueprint-callable |
| `CancelQueuedAnalyses()` | native, Blueprint-callable |
| `CreatePlaylistFolder(DisplayName: Str, bEditable: Bool) -> Object(TribeFolder)` | native, Blueprint-callable |
| `CreateProxyFolder(DisplayName: Str, ParentFolder: Object(TribeFolder)) -> Object(TribeFolder)` | native, Blueprint-callable |
| `CreateStreamFolder(ClientName: Name, ParentFolder: Object(TribeFolder)) -> Object(TribeStreamFolder)` | native, Blueprint-callable |
| `CreateTrackPackFolder(TrackPackAddon: Object(TribeTrackPackAddon)) -> Object(TribePakFolder)` | native, Blueprint-callable |
| `ExportPlaylist(Filename: Str, ref Playlist: Struct(TribePlaylist)) -> Bool` | native, static, Blueprint-callable |
| `ExportPlaylist_Auto(ref Playlist: Struct(TribePlaylist), out OutFilename: Str) -> Bool` | native, static, Blueprint-callable |
| `ExportPlaylist_FullPath(Path: Str, ref Playlist: Struct(TribePlaylist)) -> Bool` | native, static, Blueprint-callable |
| `ExportTrackHistory(out OutFilename: Str) -> Bool` | native, Blueprint-callable |
| `FindStreamingClient(ClientName: Name) -> Object(Object)` | native, Blueprint-callable, pure |
| `FindTrack(Filename: Str) -> Object(TribeTrack)` | native, Blueprint-callable, pure |
| `FindTrackCached(Filename: Str, out bFound: Bool, out Track: Object(TribeTrack))` | native, Blueprint-callable |
| `GetAllowedTrackFileTypes() -> Array<Str>` | native, static, Blueprint-callable, pure |
| `GetAnalysisQueueSize() -> Int` | native, Blueprint-callable, pure |
| `GetBeatportClientName() -> Name` | native, static, Blueprint-callable, pure |
| `GetBlankTrackFilePath() -> Str` | native, Blueprint-callable, pure |
| `GetDisplayKey(KeyIndex: Int) -> Str` | native, Blueprint-callable, pure |
| `GetDisplayOpenkeyKey(KeyIndex: Int) -> Str` | native, Blueprint-callable, pure |
| `GetDropboxClientName() -> Name` | native, static, Blueprint-callable, pure |
| `GetFoldersAndTracksInFolder(Folder: Str, out OutFolders: Array<Str>, out OutTracks: Array<Str>)` | native, static, Blueprint-callable |
| `GetLocalFilesClientName() -> Name` | native, static, Blueprint-callable, pure |
| `GetLoginOnRestartErrorClientName() -> Name` | native, Blueprint-callable, pure |
| `GetMaxConcurrentAnalyses() -> Int` | native, Blueprint-callable, pure |
| `GetOpenkeyEnabled() -> Bool` | native, Blueprint-callable, pure |
| `GetPakTrackPrefix() -> Str` | native, static, Blueprint-callable, pure |
| `GetPlaylistFiles(out OutPlaylists: Array<Str>)` | native, static, Blueprint-callable |
| `GetRekordboxCollectionFiles(out OutFiles: Array<Str>)` | native, static, Blueprint-callable |
| `GetRekordboxPath() -> Str` | native, static, Blueprint-callable, pure |
| `GetSoundCloudClientName() -> Name` | native, static, Blueprint-callable, pure |
| `GetStreamingClientPlayedFolder(ClientName: Name) -> Object(TribeFolder)` | native, Blueprint-callable, pure |
| `GetStreamingClientRootFolder(ClientName: Name) -> Object(TribeFolder)` | native, Blueprint-callable, pure |
| `GetStreamingClientSearchFolder(ClientName: Name) -> Object(TribeFolder)` | native, Blueprint-callable, pure |
| `GetStreamingService(ClientName: Name) -> Struct(MusicStreamingService)` | native, Blueprint-callable, pure |
| `GetTidalClientName() -> Name` | native, static, Blueprint-callable, pure |
| `GetTrackLibrary() -> Object(TrackLibrary)` | native, static, Blueprint-callable, pure |
| `GetTrackNameFromFile(File: Str) -> Str` | native, static, Blueprint-callable, pure |
| `GetUniqueTrackNameForTribeFolder(TribeFolder: Object(TribeFolder), NamePrefix: Str, FileExt: Str) -> Str` | native, Blueprint-callable |
| `HandleStreamTrackMetadataQueried(Track: Object(TribeTrack))` | native |
| `HandleTrackAnalysisComplete(ref Results: Struct(SuperPoweredAnalysisResults), UserData: Object(Object))` | native |
| `HasUserTracks() -> Bool` | native, Blueprint-callable, pure |
| `ImportPlaylist(Filename: Str, out OutPlaylist: Struct(TribePlaylist)) -> Bool` | native, static, Blueprint-callable |
| `ImportPlaylist_FullPath(Path: Str, out OutPlaylist: Struct(TribePlaylist)) -> Bool` | native, static, Blueprint-callable |
| `ImportRekordboxMetadata(XmlFileName: Str)` | native, Blueprint-callable |
| `InitTrackCache()` | native, Blueprint-callable |
| `IsPopulated() -> Bool` | native, Blueprint-callable, pure |
| `IsStreamingClientLoggedIn(ClientName: Name) -> Bool` | native, Blueprint-callable, pure |
| `IsSupportedTrackFileType(Filename: Str) -> Bool` | native, static, Blueprint-callable, pure |
| `LoadPlaylist(PlaylistName: Str) -> Object(TribeFolder)` | native, Blueprint-callable |
| `LoadTrackAnalysis(Track: Object(TribeTrack)) -> Bool` | native, Blueprint-callable |
| `LoadTrackData(Track: Object(TribeTrack))` | native, Blueprint-callable |
| `LoadTrackPak(PakFileName: Str, ParentFolder: Object(TribeFolder)) -> Bool` | native, Blueprint-callable |
| `LogoutStreamingClient(ClientName: Name)` | native, Blueprint-callable |
| `RefreshTrackFolder(Folder: Object(TribeFolder))` | native, Blueprint-callable |
| `RemoveTrack(Track: Object(TribeTrack))` | native, Blueprint-callable |
| `RenameTrack(Track: Object(TribeTrack), NewName: Str)` | native, Blueprint-callable |
| `RepopulateTracks()` | native, Blueprint-callable |
| `ResetSession()` | native, Blueprint-callable |
| `ResetTempFolder()` | native, Blueprint-callable |
| `ResolveTrackPackReference(TrackReference: Str) -> Object(TribeTrack)` | native, Blueprint-callable |
| `SavePlaylist(PlaylistFolder: Object(TribeFolder), out OutFilename: Str) -> Bool` | native, Blueprint-callable |
| `SaveTrackAnalysis(Track: Object(TribeTrack))` | native, Blueprint-callable |
| `SaveTrackCache()` | native, Blueprint-callable |
| `SaveTrackData(Track: Object(TribeTrack))` | native, Blueprint-callable |
| `SaveTrackMetadata(Track: Object(TribeTrack))` | native, Blueprint-callable |
| `SearchForTracks(SearchString: Str, ClientName: Name) -> Array<Object(TribeFile)>` | native, Blueprint-callable |
| `SearchStreamingCatalog(ClientName: Name, SearchString: Str) -> Object(TribeStreamFolder)` | native, Blueprint-callable |
| `SetLoginOnRestartClientName(ClientName: Name)` | native, Blueprint-callable |
| `SetOpenkeyEnabled(bEnabled: Bool)` | native, Blueprint-callable |
| `SetTrackManager(TrackManager: Object(TrackManager))` | native, Blueprint-callable |
| `TrackInAnalysisQueue(Track: Object(TribeTrack)) -> Bool` | native, Blueprint-callable, pure |

C++ overrides: `Destructor`, `DeletingDestructor`, `IsReadyForFinishDestroy`, `FinishDestroy`, `GetWorld`.

### TrackManager

`/Script/TribeXR.TrackManager` : `Actor`, 744 bytes; vtable 228 entries, 6 overridden or new.

Data members: `OnAddTrackToPlaylistRequest`: MulticastDelegate, `TrackLibrary`: Object, `OnBeatportLoginEvent`: MulticastDelegate, `OnBeatportAudioQualitiesResult`: MulticastDelegate, `OnBeatportPlaylistsResult`: MulticastDelegate.

| Function | Kind |
|---|---|
| `BeatportLogin()` | native, Blueprint-callable |
| `BeatportLoginFromClipboard() -> Bool` | native, Blueprint-callable |
| `FindTrackFromFile(Filename: Str, out OutTrack: Object(TribeTrack)) -> Bool` | native, Blueprint-callable |
| `GetBeatportClient() -> Object(Object)` | native, Blueprint-callable, pure |
| `GetDownloadsFolder() -> Object(TribeFolder)` | native, Blueprint-callable, pure |
| `GetEditablePlaylistsFolder() -> Object(TribeFolder)` | native, Blueprint-callable, pure |
| `GetHistoryFolder() -> Object(TribeFolder)` | native, Blueprint-callable, pure |
| `GetPlaylistsFolder() -> Object(TribeFolder)` | native, Blueprint-callable, pure |
| `GetRekordboxFolder() -> Object(TribeFolder)` | native, Blueprint-callable, pure |
| `GetSamplesFolder() -> Object(TribeFolder)` | native, Blueprint-callable, pure |
| `GetUserFolder() -> Object(TribeFolder)` | native, Blueprint-callable, pure |
| `IsBeatportAvailable() -> Bool` | native, Blueprint-callable, pure |
| `IsBeatportLoggedIn() -> Bool` | native, Blueprint-callable, pure |
| `IsBeatportPlaylistsInit() -> Bool` | native, Blueprint-callable, pure |
| `QueryBeatportAudioQualities()` | native, Blueprint-callable |
| `QueryBeatportPlaylists()` | native, Blueprint-callable |
| `SaveTrackCache()` | native, Blueprint-callable |
| `SetBeatportAudioQuality(AudioQuality: Str)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginPlay`, `EndPlay`, `PostActorCreated`, `Destroyed`.

### TribeAccountSaveGame

`/Script/TribeXR.TribeAccountSaveGame` : `TribeEncryptedSaveGame`, 176 bytes; vtable 88 entries, 2 overridden or new.

Data members: `LoginId`: Str, `AccountInfo`: Str, `Timestamp`: Int64.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeAccountsApiTypes

`/Script/TribeXR.TribeAccountsApiTypes` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeAccountsManager

`/Script/TribeXR.TribeAccountsManager` : `Object`, 288 bytes; vtable 88 entries, 3 overridden or new.

Data members: `AccountInfo`: Struct(TribeAccountInfo), `OnEmailChanged`: MulticastDelegate, `OnAccountInfoChanged`: MulticastDelegate, `OnModerationFlagsChanged`: MulticastDelegate, `OnBootcampInterestRegistered`: MulticastDelegate, `GameInstance`: Object.

| Function | Kind |
|---|---|
| `BeginStandaloneManualLogin() -> Str` | native, Blueprint-callable |
| `GetEditProfileUrl() -> Str` | native, Blueprint-callable, pure |
| `GetProfileImageUrl() -> Str` | native, Blueprint-callable, pure |
| `GetProfileName() -> Str` | native, Blueprint-callable, pure |
| `GetProfileUrl() -> Str` | native, Blueprint-callable, pure |
| `IsBannedFromRooms() -> Bool` | native, Blueprint-callable, pure |
| `IsBannedFromVoice() -> Bool` | native, Blueprint-callable, pure |
| `IsEmailVerified() -> Bool` | native, Blueprint-callable, pure |
| `IsFreeTrialActive() -> Bool` | native, Blueprint-callable, pure |
| `IsLoggedIn() -> Bool` | native, Blueprint-callable, pure |
| `IsSubscriptionActive() -> Bool` | native, Blueprint-callable, pure |
| `IsUserGrandfathered() -> Bool` | native, Blueprint-callable, pure |
| `RegisterBootcampInterest(EmailAddress: Str)` | native, Blueprint-callable |
| `RequestAccountInfo()` | native, Blueprint-callable |
| `SendMagicLinkEmail(EmailAddress: Str)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginDestroy`.

### TribeAchievementTypes

`/Script/TribeXR.TribeAchievementTypes` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeAddon

`/Script/TribeXR.TribeAddon` : `Object`, 192 bytes; vtable 92 entries, 6 overridden or new.

Data members: `AddonInfo`: Struct(TribeAddonInfo), `OnAddonDownloadUpdate`: MulticastDelegate, `OnAddonDownloadProgressUpdate`: MulticastDelegate.

| Function | Kind |
|---|---|
| `DownloadAddon()` | native, Blueprint-callable |
| `GetAddonDisplayName() -> Str` | native, Blueprint-callable, pure |
| `GetAddonThumbnail() -> Object(Texture)` | native, Blueprint-callable, pure |
| `GetCleanAddonName(PakFileName: Str) -> Str` | native, static, Blueprint-callable, pure |
| `GetDownloadProgress() -> Struct(TribeAddonDownloadProgress)` | native, Blueprint-callable, pure |
| `GetDownloadProgressFraction(ref InProgress: Struct(TribeAddonDownloadProgress)) -> Float` | native, static, Blueprint-callable, pure |
| `HandleDownloadConfirmed(bSuccess: Bool, DownloadId: UInt64, DownloadPath: Str)` | native |
| `HandleDownloadUpdate(ref NewProgress: Struct(TribeAddonDownloadProgress))` | native |
| `InstallAddon() -> Bool` | native, Blueprint-callable |
| `LazyLoadAddon() -> Bool` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `NewVirtual88`, `NewVirtual89`, `NewVirtual90`, `NewVirtual91`.

### TribeAddonOrder

`/Script/TribeXR.TribeAddonOrder` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `GetAddonListOrder(AddonName: Str, out PinToTop: Bool) -> Int` | native, static, Blueprint-callable, pure |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeAnalytics

`/Script/TribeXR.TribeAnalytics` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `AddAnalyticsEvent(EventName: Str)` | native, static, Blueprint-callable |
| `AddAnalyticsEventWithValue(EventName: Str, Value: Float)` | native, static, Blueprint-callable |
| `AddAnalyticsProgressEvent(EventName: Str, Progress: Enum(ETribeAnalyticsProgress))` | native, static, Blueprint-callable |
| `GetGameAnalyticsABGroupFromId(ID: Str, out bIsControl: Bool) -> Bool` | native, static |
| `SetCustomDimension(Key: Str, Value: Byte)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeAnchorManager

`/Script/TribeXR.TribeAnchorManager` : `Actor`, 920 bytes; vtable 228 entries, 4 overridden or new.

Data members: `OnSavedAnchorsLoaded`: MulticastDelegate, `Anchors`: Map<Name,Struct(TribeSpatialAnchorHandle)>.

| Function | Kind |
|---|---|
| `DeleteAnchor(AnchorName: Name) -> Bool` | native, Blueprint-callable |
| `GetAnchorHandleTransform(ref AnchorHandle: Struct(TribeSpatialAnchorHandle), out OutTransform: Struct(Transform)) -> Bool` | native, Blueprint-callable |
| `GetAnchorTransform(AnchorName: Name, out OutTransform: Struct(Transform)) -> Bool` | native, Blueprint-callable |
| `HasLoadedSavedAnchors() -> Bool` | native, Blueprint-callable, pure |
| `SetAnchoredActor(AnchorName: Name, AnchoredActor: Object(Actor)) -> Bool` | native, Blueprint-callable |
| `SetAnchorTransform(AnchorName: Name, ref AnchorTransform: Struct(Transform)) -> Bool` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginPlay`, `EndPlay`.

### TribeAvailableDeviceInfo

`/Script/TribeXR.TribeAvailableDeviceInfo` : `Object`, 56 bytes; vtable 88 entries, 2 overridden or new.

Data members: `AvailableEquipment`: Array<Object>.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeAvatarComponent

`/Script/TribeXR.TribeAvatarComponent` : `SceneComponent`, 720 bytes; vtable 199 entries, 11 overridden or new.

Data members: `OnAvatarLoaded`: MulticastDelegate, `OnAvatarCached`: MulticastDelegate, `OnAvatarVisibilityChanged`: MulticastDelegate, `bAvatarSetup`: Bool, `AvatarId`: Str, `CurrentETribeAvatarType`: Enum(ETribeAvatarType), `ReadyPlayerMeHandsAnimBlueprintClass`: Object, `LipSyncBufferedWave`: Object, `ActiveAvatarComponent`: Object, `ReadyPlayerMeComponent`: Object, `MetaAvatar2Component`: Object.

| Function | Kind |
|---|---|
| `GetAvatarId() -> Str` | native, Blueprint-callable, pure |
| `GetAvatarIdForServer(InAvatarId: Str, InAvatarType: Enum(ETribeAvatarType)) -> Str` | native, Blueprint-callable, pure |
| `GetAvatarImageCacheFilename(AvatarUrl: Str) -> Str` | native, static, Blueprint-callable, pure |
| `GetAvatarMesh() -> Object(SkeletalMeshComponent)` | native, Blueprint-callable, pure |
| `GetAvatarTypeForId(InAvatarId: Str) -> Enum(ETribeAvatarType)` | native, static, Blueprint-callable, pure |
| `GetAvatarUrlCacheFilename(AvatarUrl: Str) -> Str` | native, static, Blueprint-callable, pure |
| `GetTribeDefaultAvatarId() -> Str` | native, static, Blueprint-callable, pure |
| `GetTribeMentorAvatarId() -> Str` | native, static, Blueprint-callable, pure |
| `HandleActiveAvatarLoaded(AvatarComponent: Object(SceneComponent))` | native |
| `HandleLipSyncVisemesReady()` | native |
| `HandleReadyPlayerMeOnAvatarCached(CachedAvatarFilename: Str, OriginalFilename: Str)` | native |
| `IsAvatarLoaded() -> Bool` | native, Blueprint-callable, pure |
| `IsAvatarLoading() -> Bool` | native, Blueprint-callable, pure |
| `IsMetaAvatarsSupported() -> Bool` | native, static, Blueprint-callable, pure |
| `IsThirdPersonVisible() -> Bool` | native, Blueprint-callable, pure |
| `Multi_SetupAvatar(InAvatarId: Str, AvatarType: Enum(ETribeAvatarType))` | native, event, multicast RPC |
| `Server_SetupAvatar(InAvatarId: Str, AvatarType: Enum(ETribeAvatarType))` | native, event, server RPC |
| `SetAvatarSceneCaptureHidden(bSceneCaptureHidden: Bool)` | native, Blueprint-callable |
| `SetAvatarVisibility(bThirdPersonVisible: Bool)` | native, Blueprint-callable |
| `SetExperimentalTrackingEnabled(bEnabled: Bool)` | native, Blueprint-callable |
| `SetHandTrackingEnabled(bEnabled: Bool)` | native, Blueprint-callable |
| `SetLightTuningValues(ref LightTuningValues: Struct(TribeAvatarLightTuningValues))` | native, Blueprint-callable |
| `SetLipSyncVisemes(ref Visemes: Array<Float>, LaughterScore: Float)` | native, Blueprint-callable |
| `SetOwnerNoSee(bNewOwnerNoSee: Bool)` | native, Blueprint-callable |
| `SetupAvatar(NewAvatarId: Str) -> Bool` | native, Blueprint-callable |
| `StartLipSync(InAudioComponent: Object(AudioComponent), LipSyncSequence: Object(OVRLipSyncFrameSequence), StartTime: Float)` | native, Blueprint-callable |
| `StartSimulating(HeadComponent: Object(SceneComponent), LeftHandComponent: Object(SceneComponent), RightHandComponent: Object(SceneComponent))` | native, Blueprint-callable |
| `StopLipSync()` | native, Blueprint-callable |
| `StopSimulating()` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `GetLifetimeReplicatedProps`, `ValidateGeneratedRepEnums`, `BeginPlay`, `EndPlay`, `OnVisibilityChanged`, `OnHiddenInGameChanged`, `NewVirtual196`, `NewVirtual197`, `NewVirtual198`.

### TribeBeatHighwayLane

`/Script/TribeXR.TribeBeatHighwayLane` : `Actor`, 992 bytes; vtable 232 entries, 8 overridden or new.

Data members: `LaneId`: Struct(TribeControlId), `LaneInfo`: Struct(BeatHighwayLaneInfo), `HighwayManager`: Object, `IdleBeatsUntilDestroyed`: Float, `BeatGapThreshold`: Float, `LastActiveBeatIndex`: Int, `bPlayerInputRecieved`: Bool, `CurrentTargetValue`: Float, `NextTargetValue`: Float, `HiddenDeckControlNames`: Array<Name>, `DeviceEquipmentMesh`: Object.

| Function | Kind |
|---|---|
| `DequeueActiveBeatEvent(out BeatIndex: Int, out Value: Float) -> Bool` | native, Blueprint-callable |
| `EnqueueActiveBeatEvent(BeatIndex: Int, Value: Float) -> Bool` | native, Blueprint-callable |
| `ManualDestroyLane()` | native, Blueprint-callable |
| `OnEffectActivated(Timer: Struct(TimerHandle), EffectDelegate: Delegate(OnEffectActivatedDelegate__DelegateSignature))` | native, Blueprint-callable |
| `OnInputTimerActivated(Timer: Struct(TimerHandle), BeatEvent: Struct(TribeBeatHighwayEvent))` | native |
| `PeekActiveBeatEvent(out BeatIndex: Int, out Value: Float) -> Bool` | native, Blueprint-callable |
| `ResetDestroyTimer(SecondsUntilDestroy: Float)` | native, Blueprint-callable |
| `SetupLane(BeatEvent: Struct(TribeBeatHighwayEvent))` | native, Blueprint-callable |
| `SetupLaneBP(BeatEvent: Struct(TribeBeatHighwayEvent))` | event, Blueprint event |
| `ShowSuccessMessage(EventResult: Enum(EBeatEventResult), ReactionType: Enum(EBeatHighwayReactionType))` | native, Blueprint-callable |
| `ShowSuccessMessageBP(EventResult: Enum(EBeatEventResult), ReactionType: Enum(EBeatHighwayReactionType))` | event, Blueprint event |
| `SpawnBeatEvent(Beat: Int, Event: Struct(TribeBeatHighwayEvent))` | native, Blueprint-callable |
| `SpawnBeatEventBP(Beat: Int, Event: Struct(TribeBeatHighwayEvent))` | event, Blueprint event |
| `StartEffectTimer(Time: Float, TimerDelegate: Delegate(OnEffectActivatedDelegate__DelegateSignature))` | native, Blueprint-callable |
| `TickLane(SequenceTime: Float)` | native, Blueprint-callable |
| `TickLaneBP(SequenceTime: Float)` | event, Blueprint event |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginPlay`, `EndPlay`, `NewVirtual228`, `NewVirtual229`, `NewVirtual230`, `NewVirtual231`.

### TribeBeatHighwayLaneImpl

`/Script/TribeXR.TribeBeatHighwayLaneImpl` : `TribeBeatHighwayLane`, 1088 bytes; vtable 233 entries, 6 overridden or new.

Data members: `NoticeMeFxBasePosition`: Struct(Vector), `Icons`: Array<Struct(TribeBeatHighwayLaneIconInfo)>, `GridXform`: Struct(LinearColor), `InteractionMode`: Enum(EBeatHighwayInteractionMode), `bCheckControlValueOnTick`: Bool, `bNewGoal`: Bool, `bWaitToUpdateGoal`: Bool, `LastPushedValue`: Float.

| Function | Kind |
|---|---|
| `GetGoalMaterialTransform(TargetValue: Float) -> Struct(Vector)` | native, Blueprint-callable, pure |
| `PushIcon(IconTexture: Object(Texture2D), StartCount: Int, XPos: Float)` | native, Blueprint-callable |
| `TickLaneWithBPM(SequenceTime: Float, BeatsPerMinute: Float)` | native, Blueprint-callable |
| `UpdateBeamFx(BeamFx: Object(NiagaraComponent), BasePosition: Struct(Vector), WorldContextObject: Object(Object))` | native, static, Blueprint-callable |
| `UpdateGoal(GoalMesh: Object(StaticMeshComponent), GoalMaterial: Object(MaterialInstanceDynamic), ControlValue: Float)` | native, Blueprint-callable |
| `UpdateLaneBeamFx(BeamFx: Object(NiagaraComponent), BasePosition: Struct(Vector), WorldContextObject: Object(Object))` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginPlay`, `TribeBeatHighwayLane_NewVirtual229`, `TribeBeatHighwayLane_NewVirtual230`, `NewVirtual232`.

### TribeBeatHighwayManager

`/Script/TribeXR.TribeBeatHighwayManager` : `Actor`, 1416 bytes; vtable 228 entries, 4 overridden or new.

Data members: `BeatFrequency`: Float, `MaxEventsPerBeat`: Int, `NumDisplayedBeatEvents`: Int, `MasterTempo`: Float, `TempoChangeOffset`: Float, `StartingBeat`: Int, `bReplayMode`: Bool, `InteractionMode`: Enum(EBeatHighwayInteractionMode), `BeatHighwayLaneInfo`: Object, `BeatHighwaySaveGame`: Object, `DJChallengeDayDataTables`: Array<Object>, `DJChallengeProgress`: Struct(DJChallengeProgress), `OnDJChallengeProgressUpdated`: MulticastDelegate, `ActiveLanes`: Map<Struct(TribeControlId),Object>, `HiddenControlBones`: Map<Name,Int>, `PlaybackSequenceIndex`: Int, `OnSequenceStarted`: MulticastDelegate, `OnSequenceEnded`: MulticastDelegate, `OnExperienceAdded`: MulticastDelegate, `OnSequenceCompletedNoHighScore`: MulticastDelegate, `OnInteractionModeChanged`: MulticastDelegate, `ArmedSequenceName`: Str, `bIgnoreNextEvent`: Bool, `EventsThisBeat`: Int, `EventsNextBeat`: Int, `HighwayState`: Enum(EBeatHighwayState), `SequenceAudioClips`: Array<Object>.

| Function | Kind |
|---|---|
| `AddExperience(ExperiencePoints: Float)` | native, Blueprint-callable |
| `AddLeaderboardPoints(SequenceName: Str, Points: Float, ref Message: Text, bShowNotification: Bool)` | native, Blueprint-callable |
| `AreControlIdsEqual(A: Struct(TribeControlId), B: Struct(TribeControlId)) -> Bool` | native, static, Blueprint-callable, pure |
| `ArePreviousDJChallengeDaysCompleted(DayIndex: Int) -> Bool` | native, Blueprint-callable, pure |
| `ArmForRecording(SequenceName: Str)` | native, Blueprint-callable |
| `BeginSequencePlayback()` | event, Blueprint event |
| `ChangeMasterTempo(NewMasterTempo: Float)` | native, Blueprint-callable |
| `CleanupAndDestroyLane(Lane: Object(TribeBeatHighwayLane))` | native, Blueprint-callable |
| `GetAudioClip(ClipIndex: Int) -> Object(SoundBase)` | native, Blueprint-callable, pure |
| `GetBeatEventInSequence(SequenceIndex: Int) -> Struct(TribeBeatHighwayEventPair)` | native, Blueprint-callable, pure |
| `GetBeatEventResult(ControlId: Struct(TribeControlId), ControlValue: Float, out DesiredValue: Float, out Reaction: Enum(EBeatHighwayReactionType)) -> Enum(EBeatEventResult)` | native, Blueprint-callable |
| `GetBeatHighwayState() -> Enum(EBeatHighwayState)` | native, Blueprint-callable, pure |
| `GetCurrentDJChallengeDay() -> Int` | native, Blueprint-callable, pure |
| `GetDJChallengeCurrentLessonIndex() -> Int` | native, Blueprint-callable, pure |
| `GetDJChallengeCurrentLessonTitle() -> Text` | native, Blueprint-callable, pure |
| `GetDJChallengeDayProgress(DayIndex: Int) -> Struct(DJChallengeDayProgress)` | native, Blueprint-callable, pure |
| `GetDJChallengeTotalProgress() -> Float` | native, Blueprint-callable, pure |
| `GetExperience() -> Float` | native, Blueprint-callable, pure |
| `GetFirstPlayActionIndex() -> Int` | native, Blueprint-callable, pure |
| `GetNumSequencesCompleted(ref GameModeLessonEntry: Struct(GameModeLessonEntry), out OutTotalSequences: Int, out OutNumCompletedSequences: Int)` | native, Blueprint-callable, pure |
| `GetPlaybackSequenceLength() -> Int` | native, Blueprint-callable, pure |
| `GetPlaybackTimeRateSeconds(out RateSeconds: Float) -> Bool` | native, Blueprint-callable, pure |
| `GetPlaybackTimerElapsedSeconds(out ElapsedSeconds: Float) -> Bool` | native, Blueprint-callable, pure |
| `GetRandomScoreMessage(Score: Float, bBeatHighScore: Bool) -> Text` | native, Blueprint-callable, pure |
| `GetSavedSequences() -> Array<Str>` | native, Blueprint-callable, pure |
| `GetScore() -> Float` | native, Blueprint-callable, pure |
| `GetSequenceScore(SequenceName: Str, out Score: Float) -> Bool` | native, Blueprint-callable, pure |
| `IsIncomingEvent(ControlId: Struct(TribeControlId), BeatsThreshold: Int) -> Bool` | native, Blueprint-callable, pure |
| `IsPlayAction(BeatEvent: Struct(TribeBeatHighwayEvent)) -> Bool` | native, Blueprint-callable, pure |
| `IsSequenceCompleted(SequenceName: Str) -> Bool` | native, Blueprint-callable, pure |
| `LoadChannelDeviceState(SaveDirectory: Str, Channel: Int)` | event, Blueprint event |
| `PlaySequence(SequenceID: Str, MasterTempoIn: Float, StartingBeatIn: Int, StartOffsetMs: Float)` | native, Blueprint-callable |
| `RecordBeatEvent(BeatEvent: Struct(TribeBeatHighwayEvent), bQuantize: Bool)` | native, Blueprint-callable |
| `RecordEmptyEvent(bQuantize: Bool)` | native, Blueprint-callable |
| `RecordingTick()` | event, Blueprint event |
| `RecordTrackLoadEvent(TrackName: Str, DeckChannel: Int)` | native, Blueprint-callable |
| `RefreshDJChallengeProgress()` | native, Blueprint-callable |
| `SetInteractionMode(NewInteractionMode: Enum(EBeatHighwayInteractionMode))` | native, Blueprint-callable |
| `SetSequenceCompleted(SequenceName: Str, Score: Float, MessageType: Enum(EBeatHighwaySequenceMessageType))` | native, Blueprint-callable |
| `ShouldUseOnWithHoldIcon(ControlId: Struct(TribeControlId)) -> Bool` | native, Blueprint-callable, pure |
| `SpawnHighwayLane(BeatEvent: Struct(TribeBeatHighwayEvent)) -> Object(TribeBeatHighwayLane)` | event, Blueprint-callable, Blueprint event |
| `StartRecording(MasterTempoIn: Float)` | native, Blueprint-callable |
| `StopRecording(SaveDirectory: Str, SequenceID: Str) -> Bool` | native, Blueprint-callable |
| `StopSequence()` | native, Blueprint-callable |
| `StopSequenceBP()` | event, Blueprint event |
| `UpdateMaterials(SequenceTime: Float)` | native |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginPlay`, `Tick`.

### TribeBeatHighwaySaveGame

`/Script/TribeXR.TribeBeatHighwaySaveGame` : `SaveGame`, 128 bytes; vtable 88 entries, 2 overridden or new.

Data members: `SequenceScores`: Map<Str,Float>, `ExperienceLevel`: Float, `bAddedPointsToLeaderboard`: Bool.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeBeatportFolder

`/Script/TribeXR.TribeBeatportFolder` : `TribeStreamFolder`, 184 bytes; vtable 93 entries, 6 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`, `TribeFolder_NewVirtual89`, `TribeStreamFolder_NewVirtual90`, `TribeStreamFolder_NewVirtual91`, `TribeStreamFolder_NewVirtual92`.

### TribeBeatportTrack

`/Script/TribeXR.TribeBeatportTrack` : `TribeStreamTrack`, 568 bytes; vtable 119 entries, 18 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`, `FinishDestroy`, `TribeFile_NewVirtual88`, `TribeFile_NewVirtual90`, `TribeFile_NewVirtual92`, `TribeTrack_NewVirtual96`, `TribeTrack_NewVirtual98`, `TribeTrack_NewVirtual102`, `TribeTrack_NewVirtual107`, `TribeTrack_NewVirtual108`, `TribeBufferTrack_NewVirtual109`, `TribeBufferTrack_NewVirtual110`, `TribeStreamTrack_NewVirtual114`, `TribeStreamTrack_NewVirtual115`, `TribeStreamTrack_NewVirtual116`, `TribeStreamTrack_NewVirtual117`, `TribeStreamTrack_NewVirtual118`.

### TribeBlueprintLibrary

`/Script/TribeXR.TribeBlueprintLibrary` : `BlueprintFunctionLibrary`, 40 bytes; vtable 88 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `ArraySwap_NativizeFix(ref ObjectArray: Array<Object(Object)>, A: Int, B: Int)` | native, static, Blueprint-callable |
| `ArraySwapName_NativizeFix(ref NameArray: Array<Name>, A: Int, B: Int)` | native, static, Blueprint-callable |
| `BindOnVoiceStateChangedDelegate(ref OnTalkingStateChanged: Delegate(TribeTalkingStateChangedDelegate__DelegateSignature), bUnbind: Bool)` | native, static, Blueprint-callable |
| `CanLoseVRInputFocus() -> Bool` | native, static, Blueprint-callable, pure |
| `ClampVector(ref Vec: Struct(Vector), ref MinValues: Struct(Vector), ref MaxValues: Struct(Vector), out bClampedX: Bool, out bClampedY: Bool, out bClampedZ: Bool) -> Struct(Vector)` | native, static, Blueprint-callable |
| `ClearListViewSelection(ListView: Object(ListView))` | native, static, Blueprint-callable |
| `CommandLineArgUsed(Arg: Str) -> Bool` | native, static, Blueprint-callable, pure |
| `Courier_SendEvent(EventName: Str, WorldContextObject: Object(Object)) -> Bool` | native, static, Blueprint-callable |
| `CrashOnPurpose()` | native, static, Blueprint-callable |
| `CreateSoundwaveFromFile(FilePath: Str) -> Object(SoundWave)` | native, static, Blueprint-callable |
| `DateTimeToClockString12Hrs(ref DateTime: Struct(DateTime)) -> Str` | native, static, Blueprint-callable, pure |
| `DateTimeToClockString24Hrs(ref DateTime: Struct(DateTime)) -> Str` | native, static, Blueprint-callable, pure |
| `DateTimeToString(ref DateTime: Struct(DateTime)) -> Str` | native, static, Blueprint-callable, pure |
| `DeleteFile(Filename: Str) -> Bool` | native, static, Blueprint-callable |
| `DeleteFolder(FolderName: Str) -> Bool` | native, static, Blueprint-callable |
| `FInterpToEaseIn(Current: Float, Target: Float, DeltaTime: Float, InterpSpeed: Float) -> Float` | native, static, Blueprint-callable, pure |
| `FloatToStringWithPrecision(float: Float, out FloatString: Str, Precision: Int, IncludeLeadingZero: Bool)` | native, static, Blueprint-callable, pure |
| `ForceSaveConfig()` | native, static, Blueprint-callable |
| `GetDriveLetters() -> Array<Str>` | native, static, Blueprint-callable |
| `GetListViewSelectedItem(ListView: Object(ListView)) -> Object(Object)` | native, static, Blueprint-callable, pure |
| `GetLookAtTransform(ref T: Struct(Transform), LookDistance: Float, LookOffset: Struct(Vector)) -> Struct(Transform)` | native, static, Blueprint-callable, pure |
| `GetOculusDeviceName() -> Name` | native, static, Blueprint-callable, pure |
| `GetOculusSubsystemName() -> Name` | native, static, Blueprint-callable, pure |
| `GetOnlineSubsystemName() -> Name` | native, static, Blueprint-callable, pure |
| `GetPathLeaf(InPath: Str) -> Str` | native, static, Blueprint-callable, pure |
| `GetStandaloneSubsystemName() -> Name` | native, static, Blueprint-callable, pure |
| `GetSteamSubsystemName() -> Name` | native, static, Blueprint-callable, pure |
| `GetStringFromClipboard() -> Str` | native, static, Blueprint-callable |
| `GetTribeStoreVersion() -> Int` | native, static, Blueprint-callable, pure |
| `GetTribeVersionName() -> Str` | native, static, Blueprint-callable, pure |
| `GetViewportViewDistance(ref TargetSize: Struct(Vector2D), ref ViewportSize: Struct(Vector2D), FOV: Float) -> Float` | native, static, Blueprint-callable, pure |
| `GetVROrientation() -> Struct(Rotator)` | native, static, Blueprint-callable, pure |
| `GetVRPixelDensity() -> Float` | native, static, Blueprint-callable, pure |
| `GetVRPixelDensityMaxAllowed() -> Float` | native, static, Blueprint-callable, pure |
| `GetXRSystemName() -> Name` | native, static, Blueprint-callable, pure |
| `HasVRInputFocus() -> Bool` | native, static, Blueprint-callable, pure |
| `InverseTransformVector(ref T: Struct(Transform), ref Vec: Struct(Vector)) -> Struct(Vector)` | native, static, Blueprint-callable, pure |
| `IsAndroidBuild() -> Bool` | native, static, Blueprint-callable, pure |
| `IsEditorBuild() -> Bool` | native, static, Blueprint-callable, pure |
| `IsHandTrackingEnabled() -> Bool` | native, static, Blueprint-callable, pure |
| `IsHandTrackingSupported() -> Bool` | native, static, Blueprint-callable, pure |
| `IsPicoBuild() -> Bool` | native, static, Blueprint-callable, pure |
| `IsShippingBuild() -> Bool` | native, static, Blueprint-callable, pure |
| `IsValidEmailAddress(EmailAddress: Str) -> Bool` | native, static, Blueprint-callable, pure |
| `IsValidReadyPlayerMeAvatarID(AvatarId: Str) -> Bool` | native, static, Blueprint-callable, pure |
| `IsValidReadyPlayerMeAvatarUrl(AvatarId: Str) -> Bool` | native, static, Blueprint-callable, pure |
| `IsXRDeviceConnected() -> Bool` | native, static, Blueprint-callable, pure |
| `LaunchBrowserURL(URL: Str)` | native, static, Blueprint-callable |
| `LoadTextureFromUrl(ImageUrl: Str, ref OnImageReady: Delegate(TribeImageDelegate__DelegateSignature))` | native, static, Blueprint-callable |
| `ModuloNegative(Dividend: Int, Divisor: Int) -> Int` | native, static, Blueprint-callable, pure |
| `MoveFile(Destination: Str, Source: Str) -> Bool` | native, static, Blueprint-callable |
| `QuitTribe(bForce: Bool)` | native, static, Blueprint-callable |
| `ReadConfigBool(Section: Str, Key: Str, out OutValue: Bool) -> Bool` | native, static, Blueprint-callable |
| `ReadConfigFloat(Section: Str, Key: Str, out OutValue: Float) -> Bool` | native, static, Blueprint-callable |
| `ReadConfigString(Section: Str, Key: Str, out OutValue: Str) -> Bool` | native, static, Blueprint-callable |
| `ReadConfigTransform(Section: Str, Key: Str, out OutValue: Struct(Transform)) -> Bool` | native, static, Blueprint-callable |
| `RefreshLightingCacheOnActors(Actors: Array<Object(Actor)>)` | native, static, Blueprint-callable |
| `ResetOrientationAndPositionKeepHeight()` | native, static, Blueprint-callable |
| `ScrollListViewIndexIntoView(ListView: Object(ListView), ItemIndex: Int)` | native, static, Blueprint-callable |
| `SetDefaultOSRenderDevice(DeviceID: Str) -> Bool` | native, static, Blueprint-callable |
| `SetListViewItems(ListView: Object(ListView), ref ListItems: Array<Object(Object)>)` | native, static, Blueprint-callable |
| `SetListViewSelectedItem(ListView: Object(ListView), Item: Object(Object))` | native, static, Blueprint-callable |
| `SetVRDynamicPixelDensityMin(WorldContextObject: Object(Object), PixelDensityMin: Float)` | native, static, Blueprint-callable |
| `SetVRPixelDensity(WorldContextObject: Object(Object), PixelDensity: Float)` | native, static, Blueprint-callable |
| `TestAnalyticsEvents()` | native, static, Blueprint-callable |
| `TimeSecondsToDurationSeconds(TimeSeconds: Float) -> Str` | native, static, Blueprint-callable, pure |
| `TimeSecondsToTimerString(TimeSeconds: Float) -> Str` | native, static, Blueprint-callable, pure |
| `TimeSecondsToTimerStringMs(TimeSeconds: Float) -> Str` | native, static, Blueprint-callable, pure |
| `TimeSecondsToTimerStringsSeparated(TimeSeconds: Float, out OutMinSec: Str, out OutMilliseconds: Str)` | native, static, Blueprint-callable, pure |
| `UnixTimestampToHoursRemaining(UnixTimestamp: Int64) -> Int` | native, static, Blueprint-callable, pure |
| `WriteConfigBool(Section: Str, Key: Str, Value: Bool)` | native, static, Blueprint-callable |
| `WriteConfigFloat(Section: Str, Key: Str, Value: Float)` | native, static, Blueprint-callable |
| `WriteConfigString(Section: Str, Key: Str, Value: Str)` | native, static, Blueprint-callable |
| `WriteConfigTransform(Section: Str, Key: Str, ref Value: Struct(Transform))` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeBufferTrack

`/Script/TribeXR.TribeBufferTrack` : `TribeTrack`, 512 bytes; vtable 112 entries, 11 overridden or new.

Data members: `OnAudioStateChanged`: MulticastDelegate.

| Function | Kind |
|---|---|
| `DecodeAudioAsync()` | native, Blueprint-callable |
| `GetAudioInMemoryBP() -> Struct(SuperpoweredAudioInMemoryWrapper)` | native, Blueprint-callable, pure |
| `GetCompressedAudioBufferBP() -> Array<Byte>` | native, Blueprint-callable, pure |
| `IsAudioInMemoryCompressed() -> Bool` | native, Blueprint-callable, pure |
| `IsAudioInMemoryReady() -> Bool` | native, Blueprint-callable, pure |
| `IsCompressedAudioReady() -> Bool` | native, Blueprint-callable, pure |
| `IsReadyToDecode() -> Bool` | native, Blueprint-callable, pure |

C++ overrides: `Destructor`, `IsReadyForFinishDestroy`, `FinishDestroy`, `TribeTrack_NewVirtual102`, `TribeTrack_NewVirtual103`, `TribeTrack_NewVirtual104`, `TribeTrack_NewVirtual107`, `TribeTrack_NewVirtual108`, `NewVirtual109`, `NewVirtual110`, `NewVirtual111`.

### TribeChannelDeviceInfo

`/Script/TribeXR.TribeChannelDeviceInfo` : `TribeEquipmentInfo`, 256 bytes; vtable 89 entries, 0 overridden or new.

Data members: `MaxInstances`: Int, `CanLoadTracks`: Bool, `DeviceType`: Enum(EChannelDeviceType).

### TribeComboBoxText

`/Script/TribeXR.TribeComboBoxText` : `Widget`, 5376 bytes; vtable 110 entries, 11 overridden or new.

Data members: `DefaultOptions`: Array<Text>, `SelectedOption`: Text, `WidgetStyle`: Struct(ComboBoxStyle), `ItemStyle`: Struct(TableRowStyle), `ContentPadding`: Struct(Margin), `MaxListHeight`: Float, `HasDownArrow`: Bool, `EnableGamepadNavigationMode`: Bool, `Font`: Struct(SlateFontInfo), `ForegroundColor`: Struct(SlateColor), `bIsFocusable`: Bool, `OnGenerateWidgetEvent`: Delegate, `OnSelectionChanged`: MulticastDelegate, `OnOpening`: MulticastDelegate.

| Function | Kind |
|---|---|
| `AddOption(ref Option: Text)` | native, Blueprint-callable |
| `ClearOptions()` | native, Blueprint-callable |
| `ClearSelection()` | native, Blueprint-callable |
| `FindOptionIndex(ref Option: Text) -> Int` | native, Blueprint-callable, pure |
| `GetOptionAtIndex(Index: Int) -> Text` | native, Blueprint-callable, pure |
| `GetOptionCount() -> Int` | native, Blueprint-callable, pure |
| `GetSelectedIndex() -> Int` | native, Blueprint-callable, pure |
| `GetSelectedOption() -> Text` | native, Blueprint-callable, pure |
| `IsOpen() -> Bool` | native, Blueprint-callable, pure |
| `OnOpeningEvent__DelegateSignature()` | delegate |
| `OnSelectionChangedEvent__DelegateSignature(SelectedItem: Text, SelectionType: Enum(ESelectInfo))` | delegate |
| `RefreshOptions()` | native, Blueprint-callable |
| `RemoveOption(ref Option: Text) -> Bool` | native, Blueprint-callable |
| `SetIsOpen(bOpen: Bool)` | native, Blueprint-callable |
| `SetSelectedIndex(Index: Int)` | native, Blueprint-callable |
| `SetSelectedOption(Option: Text)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `PostInitProperties`, `PostLoad`, `Serialize`, `Serialize`, `ReleaseSlateResources`, `RebuildWidget`, `NewVirtual107`, `NewVirtual108`, `NewVirtual109`.

### TribeDLCSaveGame

`/Script/TribeXR.TribeDLCSaveGame` : `TribeEncryptedSaveGame`, 248 bytes; vtable 88 entries, 2 overridden or new.

Data members: `LoginId`: Str, `OwnedDLC`: Set<Name>, `Timestamp`: Int64, `Now`: Int64.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeDLCTypes

`/Script/TribeXR.TribeDLCTypes` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `DoesDLCRequireReview(TribeSKU: Name, bTestGroup: Bool) -> Bool` | native, static, Blueprint-callable, pure |
| `GetSKUForStore(TribeSKU: Name, StoreName: Name) -> Name` | native, static, Blueprint-callable, pure |
| `GetTribeLifetimeSubscriptionSKU() -> Name` | native, static, Blueprint-callable, pure |
| `GetTribeProSubscriptionSKU() -> Name` | native, static, Blueprint-callable, pure |
| `IsFreeSKU(TribeSKU: Name) -> Bool` | native, static, Blueprint-callable, pure |
| `IsPreviewableSKU(TribeSKU: Name) -> Bool` | native, static, Blueprint-callable, pure |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeDanceHighwayObject

`/Script/TribeXR.TribeDanceHighwayObject` : `Actor`, 704 bytes; vtable 228 entries, 3 overridden or new.

Data members: `DanceManager`: Object, `bLeftObjectHit`: Bool, `bRightObjectHit`: Bool.

| Function | Kind |
|---|---|
| `InitDanceObjects(bRecording: Bool, LeftPosition: Struct(Vector), RightPosition: Struct(Vector))` | native, Blueprint-callable |
| `InitDanceObjectsBP(bRecording: Bool, LeftPosition: Struct(Vector), RightPosition: Struct(Vector))` | event, Blueprint event |
| `UpdateNiagaraParameters(NiagaraComponent: Object(NiagaraComponent), CurrentStreak: Float, ParticleColor: Struct(LinearColor))` | native, Blueprint-callable |

C++ overrides: `Destructor`, `BeginPlay`, `Tick`.

### TribeDanceManager

`/Script/TribeXR.TribeDanceManager` : `Actor`, 928 bytes; vtable 228 entries, 3 overridden or new.

Data members: `OnBeatObjectMissed`: MulticastDelegate, `CurrentDanceMode`: Enum(EDanceMode), `OnDanceMoveRecorded`: MulticastDelegate, `SecondsPerBeat`: Float, `HighwayDistance`: Float, `SpawnLocation`: Struct(Vector), `DestroyLocation`: Struct(Vector), `NumBeatsToPlayer`: Int, `bLoopDanceMaps`: Bool, `CurrentMasterBpm`: Float, `bIsGameReady`: Bool, `DanceCache`: Object, `LocalPawn`: Object, `InputReplay`: Object, `CurrentDanceMove`: Struct(TribeDanceMove), `ActiveDanceMap`: Object, `ActiveDanceMaps`: Array<Object>, `CurrentDanceBeat`: Int, `CurrentHighwayBeat`: Int, `CurrentDanceMoveIndex`: Int, `CurrentDanceMapIndex`: Int, `GridActors`: Array<Object>.

| Function | Kind |
|---|---|
| `BeatTick()` | event, Blueprint event |
| `ClearActiveDanceMap()` | native, Blueprint-callable |
| `ClearBeatTimer()` | native, Blueprint-callable |
| `CreateDanceGrid()` | native, Blueprint-callable |
| `CreateNewDanceMap(MapId: Str) -> Object(TribeDanceMap)` | native, Blueprint-callable |
| `DanceMapExists(MapId: Str) -> Bool` | native, Blueprint-callable, pure |
| `DancePlayTick()` | native, Blueprint-callable |
| `DanceRecordTick()` | native, Blueprint-callable |
| `DeleteDanceGrid()` | native, Blueprint-callable |
| `GetAllDanceMaps() -> Array<Object(TribeDanceMap)>` | native, Blueprint-callable, pure |
| `GetReplayRecordingComponent() -> Object(InputReplayComponent)` | native, Blueprint-callable, pure |
| `GetReplayRoot() -> Str` | native, Blueprint-callable, pure |
| `HandleDanceEnded()` | event, Blueprint event |
| `HandleDanceStarted()` | event, Blueprint event |
| `HandleMetaverseBeatSignal(BeatNumber: Int, CurrentBPM: Float)` | native, Blueprint-callable |
| `HandleRecordingEnded()` | event, Blueprint event |
| `LoadDanceMoveCache()` | native, Blueprint-callable |
| `RecordHandPosition(Position: Struct(Vector), bLeftHand: Bool)` | native, Blueprint-callable |
| `RemoveDanceMap(DanceMap: Object(TribeDanceMap))` | native, Blueprint-callable |
| `SaveDanceMap(Map: Object(TribeDanceMap))` | native, Blueprint-callable |
| `SaveDanceMoveCache()` | native, Blueprint-callable |
| `SetActiveDanceMap(DanceMap: Object(TribeDanceMap))` | native, Blueprint-callable |
| `SetBeatTimer()` | native, Blueprint-callable |
| `SetReplayComponentTickEnabled(bEnabled: Bool)` | native, Blueprint-callable |
| `SetupSpawnpoints(RigTransform: Struct(Transform))` | native, Blueprint-callable |
| `SpawnDanceGridObject(Location: Struct(Vector)) -> Object(DanceGridObject)` | event, Blueprint event |
| `SpawnDanceHighwayObject() -> Object(TribeDanceHighwayObject)` | event, Blueprint event |
| `UndoLastMove() -> Bool` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginPlay`.

### TribeDanceMap

`/Script/TribeXR.TribeDanceMap` : `Object`, 80 bytes; vtable 88 entries, 2 overridden or new.

Data members: `DanceMoves`: Array<Struct(TribeDanceMove)>, `MapName`: Str, `OriginalBPM`: Float.

| Function | Kind |
|---|---|
| `GetNumMoves() -> Int` | native, Blueprint-callable, pure |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeDanceMoveSaveGame

`/Script/TribeXR.TribeDanceMoveSaveGame` : `SaveGame`, 120 bytes; vtable 88 entries, 2 overridden or new.

Data members: `DanceMaps`: Map<Str,Struct(DanceMap)>.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeDiscordManager

`/Script/TribeXR.TribeDiscordManager` : `Actor`, 664 bytes; vtable 228 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `SetDiscordActivityToDefault()` | native, Blueprint-callable |
| `SetDiscordPartyId(InPartyId: Str)` | native, Blueprint-callable |
| `SetDiscordPartyMax(InPartyMax: Int)` | native, Blueprint-callable |
| `SetDiscordPartySize(InPartySize: Int)` | native, Blueprint-callable |
| `SetDiscordState(InState: Str)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `BeginPlay`.

### TribeDropboxClient

`/Script/TribeXR.TribeDropboxClient` : `Object`, 352 bytes; vtable 88 entries, 2 overridden or new.

Data members: `OnLoginResult`: MulticastDelegate, `OnLogoutComplete`: MulticastDelegate, `CurrentPathFolders`: Array<Object>, `CurrentPathTrackFiles`: Array<Object>.

| Function | Kind |
|---|---|
| `HandleRekordboxQuery(QueryState: Enum(ETribeStreamingQueryState), QueriedFolder: Object(TribeStreamFolder))` | native |
| `HandleRekordboxTreeQuery(QueryState: Enum(ETribeStreamingQueryState), QueriedFolder: Object(TribeStreamFolder))` | native |
| `HandleRootQuery(QueryState: Enum(ETribeStreamingQueryState), QueriedFolder: Object(TribeStreamFolder))` | native |
| `IsLoggedIn() -> Bool` | native, Blueprint-callable, pure |
| `Login(InOAuthCode: Str)` | native |
| `LoginFromCache() -> Bool` | native, Blueprint-callable |
| `LoginFromClipboard() -> Bool` | native, Blueprint-callable |
| `Logout()` | native, Blueprint-callable |
| `RequestDropboxOAuthTokens()` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeDropboxFolder

`/Script/TribeXR.TribeDropboxFolder` : `TribeStreamFolder`, 176 bytes; vtable 93 entries, 6 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`, `TribeFolder_NewVirtual89`, `TribeStreamFolder_NewVirtual90`, `TribeStreamFolder_NewVirtual91`, `TribeStreamFolder_NewVirtual92`.

### TribeDropboxTrack

`/Script/TribeXR.TribeDropboxTrack` : `TribeStreamTrack`, 576 bytes; vtable 119 entries, 16 overridden or new.

| Function | Kind |
|---|---|
| `GetDropboxFileOwner() -> Object(TribePlayerController)` | native, Blueprint-callable, pure |
| `GetDropboxPath() -> Str` | native, Blueprint-callable, pure |
| `GetDropboxSharedUrl() -> Str` | native, Blueprint-callable, pure |
| `HandleDownloadFinished(bSuccess: Bool, ref FileBuffer: Array<Byte>)` | native |
| `HandleDownloadProgress(BytesDownloaded: Int, TotalBytes: Int)` | native |
| `HandleDropboxMetadataResult(bSuccess: Bool, ref DropboxFile: Struct(DropboxFile))` | native |
| `HandleFileOwnerDestroyed(DestroyedActor: Object(Actor))` | native |
| `HasValidSharedUrl() -> Bool` | native, Blueprint-callable, pure |
| `IsFromSharedUrl() -> Bool` | native, Blueprint-callable, pure |
| `RequestDropboxSharedUrl(ref OnSharedUrlResult: Delegate(TribeDropboxTrackSharedUrlDelegate__DelegateSignature), ClientData: Object(Object))` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `FinishDestroy`, `TribeFile_NewVirtual88`, `TribeFile_NewVirtual90`, `TribeFile_NewVirtual92`, `TribeTrack_NewVirtual96`, `TribeTrack_NewVirtual98`, `TribeTrack_NewVirtual101`, `TribeTrack_NewVirtual102`, `TribeTrack_NewVirtual107`, `TribeBufferTrack_NewVirtual109`, `TribeStreamTrack_NewVirtual112`, `TribeStreamTrack_NewVirtual113`, `TribeStreamTrack_NewVirtual117`, `TribeStreamTrack_NewVirtual118`.

### TribeEncryptedSaveGame

`/Script/TribeXR.TribeEncryptedSaveGame` : `SaveGame`, 136 bytes; vtable 88 entries, 2 overridden or new.

Data members: `EncryptedData`: Map<Str,Str>.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeEnvironmentTypes

`/Script/TribeXR.TribeEnvironmentTypes` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `GetEnvironmentLevelAssetPath(Environment: Enum(ETribeEnvironmentType)) -> SoftObject(World)` | native, static, Blueprint-callable, pure |
| `GetEnvironmentLevelName(Environment: Enum(ETribeEnvironmentType)) -> Name` | native, static, Blueprint-callable, pure |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeEquipmentBase

`/Script/TribeXR.TribeEquipmentBase` : `TribeNetActor`, 688 bytes; vtable 232 entries, 8 overridden or new.

Data members: `EquipmentMesh`: Object, `ModelId`: Name, `bMidiMode`: Bool, `bPreviewMode`: Bool.

| Function | Kind |
|---|---|
| `SetEquipmentVisible(bVisible: Bool)` | native, event, Blueprint-callable, Blueprint event |
| `SetMidiMode(bEnabled: Bool)` | native, event, Blueprint-callable, Blueprint event |
| `SpawnEquipmentMesh()` | native, event, Blueprint-callable, Blueprint event |

C++ overrides: `Destructor`, `DeletingDestructor`, `GetLifetimeReplicatedProps`, `ValidateGeneratedRepEnums`, `Destroyed`, `NewVirtual229`, `NewVirtual230`, `NewVirtual231`.

### TribeEquipmentInfo

`/Script/TribeXR.TribeEquipmentInfo` : `Object`, 256 bytes; vtable 89 entries, 3 overridden or new.

Data members: `EquipmentId`: Name, `DisplayName`: Text, `Description`: Text, `PreviewImage`: Object, `SpawnEquipmentClass`: SoftObject, `SKU`: Name, `SupportedOnAndroid`: Bool, `DeviceWidth`: Float, `RelativeSpawnTransform`: Struct(Transform), `DeviceGroup`: Enum(ETribeDeviceGroup).

| Function | Kind |
|---|---|
| `PostEquipmentSpawn(Equipment: Object(Object))` | native, event, Blueprint-callable, Blueprint event |

C++ overrides: `Destructor`, `DeletingDestructor`, `NewVirtual88`.

### TribeEquipmentLayout

`/Script/TribeXR.TribeEquipmentLayout` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `EquipmentLayoutFromString(LayoutString: Str, NumChannels: Int, out OutLayout: Struct(EquipmentSpawnLayout)) -> Bool` | native, static, Blueprint-callable |
| `EquipmentLayoutToString(ref Layout: Struct(EquipmentSpawnLayout)) -> Str` | native, static, Blueprint-callable |
| `GetDefaultSpawnLayout(NumChannels: Int) -> Struct(EquipmentSpawnLayout)` | native, static, Blueprint-callable |
| `GetEquipmentLayoutSpawnTransforms(ref EquipmentLayout: Struct(EquipmentSpawnLayout), Mixer: Class(TribeMixerInfo), ref Devices: Array<Class(TribeChannelDeviceInfo)>) -> Array<Struct(Transform)>` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeEquipmentMesh

`/Script/TribeXR.TribeEquipmentMesh` : `TribeNetActor`, 1776 bytes; vtable 229 entries, 6 overridden or new.

Data members: `OnMeshVisibilityChanged`: MulticastDelegate, `ModelId`: Name, `ControlModelDataTables`: Array<Object>, `PoseableMeshComponent`: Object, `WeightsTexture`: Object.

| Function | Kind |
|---|---|
| `GetBoneTransform(BoneName: Name, BoneSpace: Enum(EBoneSpaces)) -> Struct(Transform)` | native, Blueprint-callable, pure |
| `GetControlModelInfo(ControlName: Name, out ControlModelInfo: Struct(TribeControlModelInfo), DataTableIndex: Int) -> Bool` | native, Blueprint-callable, pure |
| `GetPoseableMeshComponent() -> Object(PoseableMeshComponent)` | native, Blueprint-callable, pure |
| `GetRelativeBoneTransform(BoneName: Name) -> Struct(Transform)` | native, Blueprint-callable, pure |
| `IsMeshVisible() -> Bool` | native, Blueprint-callable, pure |
| `OnRep_ModelId()` | native |
| `RefreshMaterials()` | native, Blueprint-callable |
| `SetBoneTransform(BoneName: Name, ref Transform: Struct(Transform), BoneSpace: Enum(EBoneSpaces))` | native, Blueprint-callable |
| `SetBoneVisible(BoneName: Name, bVisible: Bool)` | native, Blueprint-callable |
| `SetDefaultLitMode(LitMode: Enum(EElementLitState))` | native, Blueprint-callable |
| `SetElementLitState(Element: Byte, bIsLit: Bool, LitHue: Float)` | native, Blueprint-callable |
| `SetElementState(Element: Byte, TextureBlend: Float, LitState: Enum(EElementLitState), LitHue: Float, LitDesaturation: Float)` | native, Blueprint-callable |
| `SetMaterialScalarParameter(ParameterName: Name, ParameterValue: Float)` | native, Blueprint-callable |
| `SetMaterialTextureParameter(ParameterName: Name, TextureObject: Object(Texture))` | native, Blueprint-callable |
| `SetMeshVisible(bVisible: Bool)` | native, Blueprint-callable |
| `SetRelativeBoneTransform(BoneName: Name, ref RelTransform: Struct(Transform))` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `GetLifetimeReplicatedProps`, `ValidateGeneratedRepEnums`, `Tick`, `PostInitializeComponents`.

### TribeEquipmentSaveGame

`/Script/TribeXR.TribeEquipmentSaveGame` : `SaveGame`, 536 bytes; vtable 88 entries, 2 overridden or new.

Data members: `BoolMap`: Map<Name,Bool>, `FloatMap`: Map<Name,Float>, `IntMap`: Map<Name,Int>, `SavedTrack`: Struct(TribeTrackSaveInfo), `EquipmentScale`: Float.

| Function | Kind |
|---|---|
| `GetBool(Key: Name, out bSuccess: Bool) -> Bool` | native, Blueprint-callable, pure |
| `GetEquipmentSaveGameDirectory() -> Str` | native, static, Blueprint-callable, pure |
| `GetEquipmentScale() -> Float` | native, Blueprint-callable, pure |
| `GetFloat(Key: Name, out bSuccess: Bool) -> Float` | native, Blueprint-callable, pure |
| `GetInt(Key: Name, out bSuccess: Bool) -> Int` | native, Blueprint-callable, pure |
| `GetSavedTrack(out bSuccess: Bool) -> Struct(TribeTrackSaveInfo)` | native, Blueprint-callable, pure |
| `LoadEquipmentState(SaveDirectory: Str, DeviceName: Str) -> Object(TribeEquipmentSaveGame)` | native, static, Blueprint-callable |
| `SaveBool(Key: Name, Value: Bool)` | native, Blueprint-callable |
| `SaveEquipmentState(SaveDirectory: Str, DeviceName: Str) -> Bool` | native, Blueprint-callable |
| `SaveFloat(Key: Name, Value: Float)` | native, Blueprint-callable |
| `SaveInt(Key: Name, Value: Int)` | native, Blueprint-callable |
| `SaveTrack(Track: Struct(TribeTrackSaveInfo))` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeEvent

`/Script/TribeXR.TribeEvent` : `Object`, 160 bytes; vtable 88 entries, 2 overridden or new.

Data members: `EventInfo`: Struct(TribeEventInfo), `CachedEventImage`: Object.

| Function | Kind |
|---|---|
| `GetThumbnailImage(ref OnImageReady: Delegate(TribeEventImageDelegate__DelegateSignature))` | native, Blueprint-callable |
| `HasEventType(EventType: Enum(ETribeEventType)) -> Bool` | native, Blueprint-callable, pure |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeFile

`/Script/TribeXR.TribeFile` : `Object`, 64 bytes; vtable 93 entries, 7 overridden or new.

Data members: `ParentFolder`: Object, `Filename`: Str.

| Function | Kind |
|---|---|
| `GetFileExtension() -> Str` | native, Blueprint-callable, pure |
| `GetFileName() -> Str` | native, Blueprint-callable, pure |
| `GetFileOffsetBytes() -> Int` | native, Blueprint-callable, pure |
| `GetFilePath() -> Str` | native, Blueprint-callable, pure |
| `GetFileSizeBytes() -> Int` | native, Blueprint-callable, pure |
| `GetRelativePath() -> Str` | native, Blueprint-callable, pure |
| `GetThumbnailTexture() -> Object(Texture)` | native, Blueprint-callable, pure |
| `InitFile(InFilename: Str, InParentFolder: Object(TribeFolder))` | native, Blueprint-callable |
| `LoadFileData(out OutFileData: Array<Byte>) -> Bool` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `NewVirtual88`, `NewVirtual89`, `NewVirtual90`, `NewVirtual91`, `NewVirtual92`.

### TribeFolder

`/Script/TribeXR.TribeFolder` : `Object`, 128 bytes; vtable 90 entries, 4 overridden or new.

Data members: `Parent`: Object, `Name`: Str, `DisplayName`: Str, `Folders`: Array<Object>, `Files`: Array<Object>, `ScrollObject`: Object, `SelectionIndex`: Int, `OnFileAdded`: MulticastDelegate, `OnFolderAdded`: MulticastDelegate, `bAllSortMetadataImported`: Bool.

| Function | Kind |
|---|---|
| `AddFile(File: Object(TribeFile))` | native, Blueprint-callable |
| `AddFileUnique(File: Object(TribeFile))` | native, Blueprint-callable |
| `AddFolder(Folder: Object(TribeFolder))` | native, Blueprint-callable |
| `AnalyzeTracks(bAnalyzeSubfolders: Bool)` | native, Blueprint-callable |
| `ClearFolder()` | native, Blueprint-callable |
| `ContainsFile(File: Object(TribeFile)) -> Bool` | native, Blueprint-callable, pure |
| `GetDisplayName() -> Str` | native, Blueprint-callable, pure |
| `GetDisplayPath() -> Str` | native, Blueprint-callable, pure |
| `GetFilePath() -> Str` | native, Blueprint-callable, pure |
| `GetRelativePath() -> Str` | native, Blueprint-callable, pure |
| `GetRootFolder() -> Object(TribeFolder)` | native, Blueprint-callable, pure |
| `InitFolder(InName: Str, InParent: Object(TribeFolder), DisplayName: Str)` | native, Blueprint-callable |
| `IsEmptyFolder() -> Bool` | native, Blueprint-callable, pure |
| `IsRootFolder() -> Bool` | native, Blueprint-callable, pure |
| `SortFiles(SortMethod: Enum(ETrackSortMode), SecondarySortMethod: Enum(ETrackSortMode), OnSortingComplete: Delegate(TribeSortingCompleteDelegateDynamic__DelegateSignature), OnMetadataImported: Delegate(TribeSortMetadataImportDelegateDynamic__DelegateSignature)) -> Object(TribeSortingClient)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `NewVirtual88`, `NewVirtual89`.

### TribeFriend

`/Script/TribeXR.TribeFriend` : `Object`, 168 bytes; vtable 88 entries, 2 overridden or new.

Data members: `Name`: Str, `Status`: Enum(ETribeFriendStatus), `StatusString`: Str, `Room`: Object, `CachedProfileImage`: Object, `bInvitePending`: Bool, `OnFriendUpdated`: MulticastDelegate.

| Function | Kind |
|---|---|
| `GetOnlinePlatform() -> Name` | native, Blueprint-callable, pure |
| `GetProfileImage(ref OnImageReady: Delegate(TribeImageDelegate__DelegateSignature))` | native, Blueprint-callable |
| `HasEOSNetId() -> Bool` | native, Blueprint-callable, pure |
| `IsHosting() -> Bool` | native, Blueprint-callable, pure |
| `IsJoinable() -> Bool` | native, Blueprint-callable, pure |
| `OnProfileImageDownloaded(DownloadedImage: Object(Texture2DDynamic))` | native |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeGameInstance

`/Script/TribeXR.TribeGameInstance` : `GameInstance`, 1184 bytes; vtable 136 entries, 6 overridden or new.

Data members: `OnVROriginRecentered`: MulticastDelegate, `OnLoadingScreenToggled`: MulticastDelegate, `OnOnlineStatusChanged`: MulticastDelegate, `OnOnlinePlatformLoginChanged`: MulticastDelegate, `OnTribeBackendLoginChanged`: MulticastDelegate, `OnCurrentCultureChanged`: MulticastDelegate, `OnTribeInviteSent`: MulticastDelegate, `OnTribeInviteReceived`: MulticastDelegate, `OnFriendsRefreshedDelegate`: MulticastDelegate, `OnTribeSessionsFound`: MulticastDelegate, `OnSessionStateChanged`: MulticastDelegate, `OnTribeLeaderboardRead`: MulticastDelegate, `OnTribeLocalUserLeaderboardRead`: MulticastDelegate, `OnTribeDLCLoaded`: MulticastDelegate, `OnTribeSubscriptionUpdated`: MulticastDelegate, `OnTribeSubscriptionStatusConfirmed`: MulticastDelegate, `OnTribeAddonDownloaded`: MulticastDelegate, `OnExperimentalTrackingToggled`: MulticastDelegate, `OnTribePointsAdded`: MulticastDelegate, `OnLeaderboardsReady`: MulticastDelegate, `bIsOnline`: Bool, `OnlineId`: Str, `AvatarId`: Str, `PendingErrorMessages`: Array<Text>, `AvailableAddons`: Array<Object>, `ActiveLeaderboardQueries`: Int, `TribeOnlineSessionInterface`: Object, `TribeAccountsManager`: Object, `PlayerStats`: Struct(TribePlayerStatsInfo), `CachedLeaderboardRanks`: Map<Str,Int>.

| Function | Kind |
|---|---|
| `AddFriend(PlayerState: Object(PlayerState), ref OnFriendAdded: Delegate(TribeResultDelegate__DelegateSignature))` | native, Blueprint-callable |
| `AddPointsToPlayer(ref PointsInfo: Struct(TribePlayerPointsInfo))` | native, Blueprint-callable |
| `AreAddonsLoaded() -> Bool` | native, Blueprint-callable, pure |
| `AreFriendsEnabled() -> Bool` | native, static, Blueprint-callable, pure |
| `AreLeaderboardsEnabled() -> Bool` | native, static, Blueprint-callable, pure |
| `CanStartSubscriptionTrial() -> Bool` | native, Blueprint-callable, pure |
| `DestroySession(ref OnDestroyed: Delegate(SessionDestroyedDelegate__DelegateSignature))` | native, Blueprint-callable |
| `FetchLeaderboard(LeaderboardName: Name, ReadType: Enum(ETribeLeaderboardReadType)) -> Bool` | native, Blueprint-callable |
| `FindPlayerFriend(PlayerState: Object(PlayerState)) -> Object(TribeFriend)` | native, Blueprint-callable, pure |
| `FindRoom(HostIdString: Str) -> Object(TribeRoom)` | native, Blueprint-callable, pure |
| `FindSessions(bLAN: Bool)` | native, Blueprint-callable |
| `GetActiveRooms(out OutRooms: Array<Object(TribeRoom)>)` | native, Blueprint-callable, pure |
| `GetBackendLiveURL() -> Str` | native, Blueprint-callable, pure |
| `GetBackendStage() -> Enum(EBackendStage)` | native, Blueprint-callable, pure |
| `GetBackendURL() -> Str` | native, Blueprint-callable, pure |
| `GetCachedLeaderboardRank(LeaderboardName: Str, out Rank: Int) -> Bool` | native, Blueprint-callable, pure |
| `GetCurrentRoom() -> Object(TribeRoom)` | native, Blueprint-callable, pure |
| `GetDefaultGameModeName() -> Str` | native, static, Blueprint-callable, pure |
| `GetExperimentalTrackingEnabled() -> Bool` | native, Blueprint-callable, pure |
| `GetFriendImage(Friend: Object(TribeFriend), ref OnImageReady: Delegate(TribeImageDelegate__DelegateSignature))` | native, Blueprint-callable |
| `GetFriendsList(out OutList: Array<Object(TribeFriend)>, MinAllowedStatus: Enum(ETribeFriendStatus))` | native, Blueprint-callable, pure |
| `GetGameAnalyticsABGroupFromId(ID: Str, out bIsControl: Bool) -> Bool` | native, Blueprint-callable, pure |
| `GetGameLevelName() -> Str` | native, static, Blueprint-callable, pure |
| `GetGlobalLeaderboardName() -> Name` | native, static, Blueprint-callable, pure |
| `GetHostedSessionSettings() -> Struct(TribeSessionSettings)` | native, Blueprint-callable, pure |
| `GetLaunchCount() -> Int` | native, static, Blueprint-callable, pure |
| `GetLeaderboardDefaultRange() -> Int` | native, static, Blueprint-callable, pure |
| `GetLeaderboardNames() -> Array<Name>` | native, static, Blueprint-callable, pure |
| `GetLevelFromPoints(Points: Int, out PercentProgress: Float) -> Int` | native, static, Blueprint-callable, pure |
| `GetLocalUserOnlineId() -> Str` | native, Blueprint-callable, pure |
| `GetOnlinePlatformUserId() -> Str` | native, Blueprint-callable, pure |
| `GetOnlineSessionState() -> Enum(ETribeSessionState)` | native, Blueprint-callable, pure |
| `GetOnlineStoreName() -> Name` | native, static, Blueprint-callable, pure |
| `GetOwnedDLC() -> Set<Name>` | native, Blueprint-callable, pure |
| `GetPendingInviteRooms(out OutInviteRooms: Array<Object(TribeRoom)>)` | native, Blueprint-callable, pure |
| `GetPlatformDesktopMaxFPS() -> Int` | native, static, Blueprint-callable, pure |
| `GetPlayerImage(PlayerState: Object(PlayerState), ref OnImageReady: Delegate(TribeUserImageDelegate__DelegateSignature))` | native, Blueprint-callable |
| `GetPlayerImageById(NetId: Str, ref OnImageReady: Delegate(TribeUserImageDelegate__DelegateSignature))` | native, Blueprint-callable |
| `GetPlayerPoints(LeaderboardName: Str) -> Int` | native, Blueprint-callable, pure |
| `GetProfileImage(ref OnImageReady: Delegate(TribeImageDelegate__DelegateSignature))` | native, Blueprint-callable |
| `GetProfileName() -> Str` | native, Blueprint-callable, pure |
| `GetReviewABTestId() -> Str` | native, static, Blueprint-callable, pure |
| `GetSubscriptionPurchaseOptions() -> Struct(TribeSubscriptionPurchaseOptions)` | native, Blueprint-callable, pure |
| `GetTribeSessionMaxPlayers() -> Int` | native, static, Blueprint-callable, pure |
| `GetTribeSubscriptionColor() -> Struct(LinearColor)` | native, static, Blueprint-callable, pure |
| `GetTribeSubscriptionGroup() -> Enum(ETribeSubscriptionGroup)` | native, Blueprint-callable, pure |
| `GetTribeSubscriptionSignupUrl() -> Str` | native, static, Blueprint-callable, pure |
| `GetTribeUserDebugInfo() -> Str` | native, Blueprint-callable, pure |
| `HandleAccessTokenQueried(Token: Str, bSuccess: Bool)` | native |
| `HandleAccountInfoChanged(ref UpdatedAccountInfo: Struct(TribeAccountInfo))` | native |
| `HandleAddonsQueried(bQuerySuccess: Bool)` | native |
| `HandleDLCQueried(bQuerySuccess: Bool)` | native |
| `HandleLeaderboardReadComplete(LeaderboardName: Str, ref Results: Array<Struct(TribeLeaderboardInfo)>, LocalPlayerResults: Struct(TribeLeaderboardInfo))` | native |
| `HandleLoadingScreenToggled(bNewLoadingScreenActive: Bool)` | native |
| `HandleNativeStoreLogin(bSuccess: Bool, LoginOnlineId: Str)` | native |
| `HandleOnlinePlatformLogin(bSuccess: Bool, LoginOnlineId: Str)` | native |
| `HandleOnlinePlatformLogout(bSuccess: Bool)` | native |
| `HandleSubcriptionPurchaseResult(bPurchaseSuccess: Bool)` | native |
| `HandleSubscriptionQueried(bQuerySuccess: Bool)` | native |
| `HandleVRControllerRecenter()` | native |
| `HasUserLeftReview() -> Bool` | native, Blueprint-callable, pure |
| `HideTribeLoadingScreen()` | native, static, Blueprint-callable |
| `HostSession(ref SessionSettings: Struct(TribeSessionSettings), bLAN: Bool) -> Bool` | native, Blueprint-callable |
| `InitAddons(ref Addons: Array<Struct(TribeAddonInfo)>)` | native |
| `IsChinaBuild() -> Bool` | native, static, Blueprint-callable, pure |
| `IsDesktopModeSupported() -> Bool` | native, static, Blueprint-callable, pure |
| `IsDLCLoaded() -> Bool` | native, Blueprint-callable, pure |
| `IsDLCOwned(TribeSKU: Name) -> Bool` | native, Blueprint-callable, pure |
| `IsExperimentalTrackingSupported() -> Bool` | native, static, Blueprint-callable, pure |
| `IsFreeToPlay() -> Bool` | native, Blueprint-callable, pure |
| `IsFreeTrialActive() -> Bool` | native, Blueprint-callable, pure |
| `IsInitialLeaderboardQueryActive() -> Bool` | native, Blueprint-callable, pure |
| `IsLifetimeSubscriptionActive() -> Bool` | native, Blueprint-callable, pure |
| `IsOnlinePlatformLoggedIn() -> Bool` | native, Blueprint-callable, pure |
| `IsPioneerEquipment(ModelId: Name) -> Bool` | native, static, Blueprint-callable, pure |
| `IsReviewRequiredDLC(TribeSKU: Name) -> Bool` | native, Blueprint-callable, pure |
| `IsSameOnlinePlatform(OnlinePlatformIn: Str) -> Bool` | native, Blueprint-callable, pure |
| `IsSessionsQueryActive() -> Bool` | native, Blueprint-callable, pure |
| `IsStandaloneBuild() -> Bool` | native, static, Blueprint-callable, pure |
| `IsSubscriptionOnlyDLC(TribeSKU: Name) -> Bool` | native, Blueprint-callable, pure |
| `IsSubscriptionStatusConfirmed() -> Bool` | native, Blueprint-callable, pure |
| `IsTribeBackendLoggedIn() -> Bool` | native, Blueprint-callable, pure |
| `IsTribeLoadingScreenActive() -> Bool` | native, static, Blueprint-callable, pure |
| `IsTribeProSubscriptionActive() -> Bool` | native, Blueprint-callable, pure |
| `IsTribeSubscriptionCancelled() -> Bool` | native, Blueprint-callable, pure |
| `IsTribeSubscriptionPeriodSelectable() -> Bool` | native, Blueprint-callable, pure |
| `IsTribeSubscriptionPurchaseExternal() -> Bool` | native, Blueprint-callable, pure |
| `IsTribeSubscriptionSkippable() -> Bool` | native, Blueprint-callable, pure |
| `IsTribeSubscriptionSupported() -> Bool` | native, Blueprint-callable, pure |
| `IsUserGrandfathered() -> Bool` | native, Blueprint-callable, pure |
| `IsVRSupported() -> Bool` | native, static, Blueprint-callable, pure |
| `JoinTribeSession(ref SessionDetails: Struct(TribeSession), ref OnJoinFinished: Delegate(SessionJoinResultDelegate__DelegateSignature))` | native, Blueprint-callable |
| `LoginToTribeBackend(bFailFast: Bool)` | native, Blueprint-callable |
| `PreMapTravel()` | event, Blueprint event |
| `QueryAvailableAddons()` | native, Blueprint-callable |
| `QueryFriendSession(Friend: Object(TribeFriend), ref OnQueryFinished: Delegate(TribeFriendQueryDelegate__DelegateSignature))` | native, Blueprint-callable |
| `QueryFriendsList(ref OnQueryFinished: Delegate(TribeFriendResultDelegate__DelegateSignature))` | native, Blueprint-callable |
| `QueryOwnedDLC()` | native, Blueprint-callable |
| `QuerySubscriptionStatus()` | native, Blueprint-callable |
| `RefreshLoadedDLC()` | native, Blueprint-callable |
| `RequestShutdown()` | native, Blueprint-callable |
| `RequestSubscriptionPurchaseOptions(ref OnOptionsReady: Delegate(TribePurchaseOptionsDelegate__DelegateSignature))` | native, Blueprint-callable |
| `SendSessionInviteToFriend(Friend: Object(TribeFriend)) -> Bool` | native, Blueprint-callable |
| `SetCurrentCulture(Culture: Str, bSaveToConfig: Bool) -> Bool` | native, Blueprint-callable |
| `SetExperimentalTrackingEnabled(bEnabled: Bool)` | native, Blueprint-callable |
| `SetFoveatedRenderingActive(bFoveatedRenderingActive: Bool)` | native, static, Blueprint-callable |
| `SetHostedSessionPrivacy(Joinability: Enum(ETribeSessionJoinability))` | native, Blueprint-callable |
| `SetOnlineStatusUpdateActive(bActive: Bool, SecondsBetweenUpdates: Float)` | native, Blueprint-callable |
| `ShouldUseTapToPlayIntro() -> Bool` | native, Blueprint-callable, pure |
| `ShowTribeLoadingScreen()` | native, static, Blueprint-callable |
| `StartDLCPurchase(TribeSKU: Name, ref OnPurchaseFinished: Delegate(TribeResultDelegate__DelegateSignature)) -> Bool` | native, Blueprint-callable |
| `StartSubscriptionPurchase(ref SelectedPrice: Struct(TribeSubscriptionPrice), ref OnPurchaseConfirmed: Delegate(TribeResultDelegate__DelegateSignature)) -> Bool` | native, Blueprint-callable |
| `StartSubscriptionTrial(ref OnTrialConfirmed: Delegate(TribeResultDelegate__DelegateSignature)) -> Bool` | native, Blueprint-callable |
| `UpdateHostedSessionPrivacy(bPrivate: Bool, ref OnUpdateComplete: Delegate(TribeResultDelegate__DelegateSignature))` | native, Blueprint-callable |
| `UpdateOnlineStatus() -> Bool` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `Init`, `Shutdown`, `JoinSession`, `GetOnlineSessionClass`.

### TribeGameMode

`/Script/TribeXR.TribeGameMode` : `GameModeBase`, 896 bytes; vtable 292 entries, 9 overridden or new.

Data members: `PendingLoginController`: Object.

| Function | Kind |
|---|---|
| `BanPlayer(BannedPlayer: Object(PlayerState), ref BanReason: Text) -> Bool` | native, Blueprint-callable |
| `HandleInviteSent(InvitedFriend: Object(TribeFriend))` | native |
| `HandleOnlinePlatformLoginChanged(bLoggedIn: Bool)` | native |
| `HandleSessionStateChanged(SessionState: Enum(ETribeSessionState))` | native |
| `KickPlayer(KickedPlayer: Object(PlayerState), ref KickReason: Text) -> Bool` | native, Blueprint-callable |
| `SpawnInputReplayPlayerController() -> Object(PlayerController)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginPlay`, `EndPlay`, `PlayerCanRestart_Implementation`, `HandleStartingNewPlayer_Implementation`, `Logout`, `RestartPlayer`, `InitNewPlayer`.

### TribeGameState

`/Script/TribeXR.TribeGameState` : `GameStateBase`, 888 bytes; vtable 250 entries, 11 overridden or new.

Data members: `ActivePlayerList`: Array<Object>, `AdditionalSublevels`: Array<Name>, `CurrentEnvironment`: Enum(ETribeEnvironmentType), `OldEnvironment`: Enum(ETribeEnvironmentType), `CurrentEnvironmentLevel`: Object, `OldEnvironmentLevel`: Object, `PassthroughComponent`: Object, `TribeAnchorManager`: Object, `TribeVisualsManager`: Object, `OnViewportMenuHoverChanged`: MulticastDelegate, `OnActivePlayersChanged`: MulticastDelegate, `OnTrackLoaded`: MulticastDelegate, `bHandTrackingDisabled`: Bool.

| Function | Kind |
|---|---|
| `HandleEnvironmentLoaded()` | native |
| `HandleEnvironmentUnloaded()` | native |
| `IsTribePassthroughSupported() -> Bool` | native, static, Blueprint-callable, pure |
| `OnAndroidFocusToggled(bInBackground: Bool)` | event, Blueprint event |
| `OnApplicationEnteringBackground()` | native |
| `OnApplicationEnteringForeground()` | native |
| `OnEnvironmentChanged(PrevEnvironment: Enum(ETribeEnvironmentType), NewEnvironment: Enum(ETribeEnvironmentType))` | native, event, Blueprint event |
| `OnEnvironmentLoaded(EnvironmentType: Enum(ETribeEnvironmentType), EnvironmentLevel: Object(LevelStreaming))` | native, event, Blueprint event |
| `OnEnvironmentUnloaded(EnvironmentType: Enum(ETribeEnvironmentType), EnvironmentLevel: Object(LevelStreaming))` | native, event, Blueprint event |
| `OnRep_ActivePlayerList()` | native |
| `SetEnvironment(Environment: Enum(ETribeEnvironmentType))` | native, Blueprint-callable |
| `SetHandTrackingDisabled(bNewHandTrackingDisabled: Bool)` | native, Blueprint-callable |
| `SetPassthroughEnabled(bPassthroughEnabled: Bool)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `GetLifetimeReplicatedProps`, `ValidateGeneratedRepEnums`, `GetServerWorldTimeSeconds`, `HandleBeginPlay`, `OnRep_ReplicatedHasBegunPlay`, `OnRep_ReplicatedWorldTimeSecondsDouble`, `NewVirtual247`, `NewVirtual248`, `NewVirtual249`.

### TribeGif

`/Script/TribeXR.TribeGif` : `TribeFile`, 184 bytes; vtable 93 entries, 4 overridden or new.

Data members: `bGifResourcesLoaded`: Bool, `Frames`: Array<Object>, `FrameRate`: Float, `PlaybackRate`: Float, `StartFrame`: Int, `OnResourcesLoadedChanged`: MulticastDelegate, `OnFramePlayed`: MulticastDelegate.

| Function | Kind |
|---|---|
| `CalculateBeatmatchRate(BeatMatchBPM: Float, Duration: Float, MinRate: Float, MaxRate: Float) -> Float` | native, static, Blueprint-callable |
| `GetCurrentFrameAverageColor() -> Struct(LinearColor)` | native, Blueprint-callable, pure |
| `GetCurrentFrameIndex() -> Int` | native, Blueprint-callable, pure |
| `GetCurrentFrameTexture() -> Object(Texture2DDynamic)` | native, Blueprint-callable, pure |
| `GetDimensions() -> Struct(Vector2D)` | native, Blueprint-callable, pure |
| `GetFrameTexture(FrameIndex: Int) -> Object(Texture2DDynamic)` | native, Blueprint-callable, pure |
| `HandleResourcesLoaded(Gif: Object(TribeGif))` | native |
| `IsPlaying() -> Bool` | native, Blueprint-callable, pure |
| `LoadGifResources(WorldContextObject: Object(Object))` | native, Blueprint-callable |
| `PlayNextFrame()` | native, Blueprint-callable |
| `ReleaseGifResources()` | native, Blueprint-callable |
| `ResetToStart()` | native, Blueprint-callable |
| `SetBeatmatchBPM(BeatMatchBPM: Float)` | native, Blueprint-callable |
| `SetPlaybackRate(NewPlaybackRate: Float)` | native, Blueprint-callable |
| `SetProgressSeconds(ProgressSeconds: Float)` | native, Blueprint-callable |
| `StartPlaying(World: Object(World), StartDelay: Float)` | native, Blueprint-callable |
| `StopPlaying()` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginDestroy`, `TribeFile_NewVirtual90`.

### TribeHand

`/Script/TribeXR.TribeHand` : `TribeNetActor`, 1296 bytes; vtable 232 entries, 5 overridden or new.

Data members: `HandMeshComponent`: Object, `MinHandPinchDistance`: Float, `HandPinchFinger`: Enum(EHandTrackingBone).

| Function | Kind |
|---|---|
| `ApplyReplicatedInteractLocation(bHasInteractLocation: Bool, ref InteractLocation: Struct(Vector))` | event, Blueprint event |
| `ApplyReplicatedXRollValue(XRollValue: Float)` | event, Blueprint event |
| `GetHandTrackingBoneLocation(BoneID: Enum(EHandTrackingBone)) -> Struct(Vector)` | native, Blueprint-callable, pure |
| `GetHandTrackingInteractLocation(out OutLocation: Struct(Vector), out OutClosestFinger: Enum(EHandTrackingBone), out OutDistance: Float) -> Bool` | native, Blueprint-callable |
| `GetHandTrackingPointerTransform(out OutTransform: Struct(Transform)) -> Bool` | native, Blueprint-callable |
| `Multi_ApplyHandPose(ref PoseData: Struct(TribeHandPoseReplicationData))` | native, event, multicast RPC |
| `Server_SendHandInteract(ref InteractData: Struct(TribeHandInteractReplicationData))` | native, event, server RPC |
| `Server_SendHandPose(ref PoseData: Struct(TribeHandPoseReplicationData))` | native, event, server RPC |
| `SetHandTrackingActive(bActive: Bool)` | native, Blueprint-callable |
| `SetHandTrackingMeshMaterial(Material: Object(MaterialInterface))` | native, Blueprint-callable |
| `SetHandTrackingMeshVisible(bHandMeshVisible: Bool)` | native, Blueprint-callable |
| `SetHandType(bRightHand: Bool)` | native, Blueprint-callable |
| `UpdateHandTrackingInteraction(DeltaTime: Float, GrabbedActor: Object(Actor)) -> Struct(HandInteractionResult)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `NewVirtual229`, `NewVirtual230`, `NewVirtual231`.

### TribeInstancedMesh

`/Script/TribeXR.TribeInstancedMesh` : `Actor`, 704 bytes; vtable 228 entries, 5 overridden or new.

Data members: `StaticMesh`: Object, `InstancedStaticMeshComponent`: Object.

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginDestroy`, `EndPlay`, `Tick`.

### TribeInstancedMeshComponent

`/Script/TribeXR.TribeInstancedMeshComponent` : `MeshComponent`, 1392 bytes; vtable 350 entries, 16 overridden or new.

Data members: `StaticMesh`: Object, `bUseStaticMeshComponent`: Bool, `InternalMeshComponent`: Object, `InstancedMesh`: Object, `bIsRendering`: Bool.

| Function | Kind |
|---|---|
| `CreateTribeInstancedMeshComponent(OwningActor: Object(Actor), StaticMesh: Object(StaticMesh), ref RelativeTransform: Struct(Transform)) -> Object(TribeInstancedMeshComponent)` | native, static, Blueprint-callable |
| `GetInstancedMeshRenderActor() -> Object(TribeInstancedMesh)` | native, Blueprint-callable |
| `RefreshLightingCache()` | native, Blueprint-callable |
| `SetStaticMesh(InStaticMesh: Object(StaticMesh))` | native, Blueprint-callable |

C++ overrides: `Destructor`, `BeginPlay`, `EndPlay`, `OnVisibilityChanged`, `OnHiddenInGameChanged`, `OnUpdateTransform`, `GetMaterial`, `GetMaterialIndex`, `GetMaterialSlotNames`, `IsMaterialSlotNameValid`, `SetMaterial`, `GetUsedMaterials`, `GetNumMaterials`, `GetMaterials`, `GetNumOverrideMaterials`, `NewVirtual349`.

### TribeLessonBase

`/Script/TribeXR.TribeLessonBase` : `Actor`, 656 bytes; vtable 228 entries, 1 overridden or new.

C++ overrides: `Destructor`.

### TribeLessonPackAddon

`/Script/TribeXR.TribeLessonPackAddon` : `TribeAddon`, 200 bytes; vtable 92 entries, 4 overridden or new.

Data members: `AddonLessonDataTable`: Object.

| Function | Kind |
|---|---|
| `MakeLessonDataTable(LessonPackPath: Str) -> Object(DataTable)` | native, static, Blueprint-callable |
| `StringToBeatHighwaySequenceType(Str: Str) -> Enum(EBeatHighwaySequenceType)` | native, static, Blueprint-callable, pure |

C++ overrides: `Destructor`, `TribeAddon_NewVirtual89`, `TribeAddon_NewVirtual90`, `TribeAddon_NewVirtual91`.

### TribeMidiManager

`/Script/TribeXR.TribeMidiManager` : `Actor`, 1272 bytes; vtable 229 entries, 6 overridden or new.

Data members: `OnNoteOn`: MulticastDelegate, `OnNoteOff`: MulticastDelegate, `OnControlChange`: MulticastDelegate, `OnMidiConnected`: MulticastDelegate, `MIDISubsystem`: Object.

| Function | Kind |
|---|---|
| `CheckAndOpenMidiDevices()` | native, Blueprint-callable |
| `CloseMidiDevice()` | native, Blueprint-callable |
| `GetOpenDeviceName() -> Str` | native, Blueprint-callable, pure |
| `HandleDeviceConnectionChanged(DeviceName: Str, bIsConnected: Bool, bWasOpen: Bool)` | native |
| `HandleMidiMessage(Status: Byte, Data1: Int8, Data2: Int8)` | native |
| `HandleSubscriptionUpdated(bSubscriptionChanged: Bool)` | native |
| `IsMidiDeviceOpen() -> Bool` | native, Blueprint-callable, pure |
| `OnMidiConnectionChanged(DeviceName: Str, bConnected: Bool)` | native, event, Blueprint-callable, Blueprint event |
| `OpenMidiDevice(DeviceName: Str) -> Bool` | native, Blueprint-callable |
| `ResetMidiChannelMap()` | native, Blueprint-callable |
| `SendMidiEvent(ControlId: Struct(TribeControlId), Value: Int, OutDataIndex: Int)` | native, Blueprint-callable |
| `SendMidiEventRaw(Status: Int, Data1: Int, Data2: Int)` | native, Blueprint-callable |
| `SetAutoOpenMidiDevices(bAutoOpen: Bool)` | native, Blueprint-callable |
| `SetMidiChannelRemap(RemappedChannel: Byte, NewChannel: Byte)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginPlay`, `EndPlay`, `Tick`, `NewVirtual228`.

### TribeMixerInfo

`/Script/TribeXR.TribeMixerInfo` : `TribeEquipmentInfo`, 752 bytes; vtable 89 entries, 2 overridden or new.

Data members: `NumChannels`: Int, `MixerScreenOffset`: Struct(Transform), `MixerScreenMesh`: SoftObject, `MixerScreenLayout`: Struct(MixerScreenLayout), `DefaultChannelDevice`: SoftObject.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeNdiManager

`/Script/TribeXR.TribeNdiManager` : `Actor`, 784 bytes; vtable 228 entries, 2 overridden or new.

Data members: `LeftVideoScreenMesh`: Object, `RightVideoScreenMesh`: Object, `LeftScreenMat`: Object, `RightScreenMat`: Object, `ScreenOffMat`: Object, `OnNetworkSourcesChanged`: MulticastDelegate, `ActiveNdiConnectionList`: Array<Str>, `NdiSourceInfoLeft`: Object, `NdiSourceInfoRight`: Object.

| Function | Kind |
|---|---|
| `FindNdiComponents(StreamName: Str, StreamChannel: Int) -> Bool` | native, Blueprint-callable |
| `GetActiveNdiConnections() -> Array<Str>` | native, Blueprint-callable |
| `SetNdiScreenStaticMesh(ScreenMesh: Object(StaticMeshComponent), ScreenChannel: Int)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeNetActor

`/Script/TribeXR.TribeNetActor` : `Actor`, 664 bytes; vtable 229 entries, 4 overridden or new.

Data members: `NetSpawnPriority`: Float.

| Function | Kind |
|---|---|
| `GetVarReplicateConditionOverrides(out OutClass: Class(Object), out OutOverrides: Array<Struct(RepConditionOverride)>)` | native, event, Blueprint-callable, pure, Blueprint event |

C++ overrides: `Destructor`, `GetLifetimeReplicatedProps`, `GetNetPriority`, `NewVirtual228`.

### TribeNetworkTypes

`/Script/TribeXR.TribeNetworkTypes` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeOculusSession

`/Script/TribeXR.TribeOculusSession` : `TribeOnlineSession`, 20680 bytes; vtable 134 entries, 18 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`, `RegisterOnlineDelegates`, `TribeOnlineSession_NewVirtual94`, `TribeOnlineSession_NewVirtual115`, `TribeOnlineSession_NewVirtual116`, `TribeOnlineSession_NewVirtual117`, `TribeOnlineSession_NewVirtual118`, `TribeOnlineSession_NewVirtual119`, `TribeOnlineSession_NewVirtual120`, `TribeOnlineSession_NewVirtual121`, `TribeOnlineSession_NewVirtual126`, `TribeOnlineSession_NewVirtual127`, `TribeOnlineSession_NewVirtual128`, `TribeOnlineSession_NewVirtual129`, `TribeOnlineSession_NewVirtual130`, `TribeOnlineSession_NewVirtual131`, `TribeOnlineSession_NewVirtual132`.

### TribeOnlineSession

`/Script/TribeXR.TribeOnlineSession` : `OnlineSession`, 20600 bytes; vtable 134 entries, 46 overridden or new.

Data members: `QueriedFriends`: Array<Object>, `FriendMap`: Map<Str,Object>, `PendingJoinFriend`: Object, `CurrentRoom`: Object, `QueriedRooms`: Array<Object>, `RoomMap`: Map<Str,Object>, `HostMap`: Map<Str,Object>, `PendingInvites`: Map<Str,Object>, `OutgoingInvites`: Array<Object>, `CachedProfileImage`: Object, `Addons`: Array<Struct(TribeAddonInfo)>.

| Function | Kind |
|---|---|
| `GetTribeAdminFriendName() -> Str` | native, static, Blueprint-callable, pure |
| `HandleModerationFlagsChanged(ref AccountInfo: Struct(TribeAccountInfo))` | native |
| `OnProfileImageDownloaded(Image: Object(Texture2DDynamic))` | native |
| `OnUserProfileImageDownloaded(UserId: Str, Image: Object(Texture2DDynamic))` | native |

C++ overrides: `Destructor`, `DeletingDestructor`, `RegisterOnlineDelegates`, `ClearOnlineDelegates`, `HandleDisconnect`, `OnSessionUserInviteAccepted`, `NewVirtual94`, `NewVirtual95`, `NewVirtual96`, `NewVirtual97`, `NewVirtual98`, `NewVirtual99`, `NewVirtual100`, `NewVirtual101`, `NewVirtual102`, `NewVirtual103`, `NewVirtual104`, `NewVirtual105`, `NewVirtual106`, `NewVirtual107`, `NewVirtual108`, `NewVirtual109`, `NewVirtual110`, `NewVirtual111`, `NewVirtual112`, `NewVirtual113`, `NewVirtual114`, `NewVirtual115`, `NewVirtual116`, `NewVirtual117`, `NewVirtual118`, `NewVirtual119`, `NewVirtual120`, `NewVirtual121`, `NewVirtual122`, `NewVirtual123`, `NewVirtual124`, `NewVirtual125`, `NewVirtual126`, `NewVirtual127`, `NewVirtual128`, `NewVirtual129`, `NewVirtual130`, `NewVirtual131`, `NewVirtual132`, `NewVirtual133`.

### TribeOnlineTypes

`/Script/TribeXR.TribeOnlineTypes` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribePakFile

`/Script/TribeXR.TribePakFile` : `TribeFile`, 96 bytes; vtable 93 entries, 5 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`, `TribeFile_NewVirtual89`, `TribeFile_NewVirtual91`, `TribeFile_NewVirtual92`.

### TribePakFolder

`/Script/TribeXR.TribePakFolder` : `TribeStreamFolder`, 160 bytes; vtable 93 entries, 3 overridden or new.

Data members: `TrackPackAddon`: Object.

C++ overrides: `Destructor`, `DeletingDestructor`, `TribeStreamFolder_NewVirtual92`.

### TribePakTrack

`/Script/TribeXR.TribePakTrack` : `TribeTrack`, 528 bytes; vtable 109 entries, 8 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`, `TribeFile_NewVirtual89`, `TribeFile_NewVirtual90`, `TribeFile_NewVirtual91`, `TribeFile_NewVirtual92`, `TribeTrack_NewVirtual96`, `TribeTrack_NewVirtual99`.

### TribePaths

`/Script/TribeXR.TribePaths` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `GetAddonsPath() -> Str` | native, static, Blueprint-callable, pure |
| `GetAvatarsPath() -> Str` | native, static, Blueprint-callable, pure |
| `GetCustomRigSkinsPath() -> Str` | native, static, Blueprint-callable, pure |
| `GetDefaultTrackPath() -> Str` | native, static, Blueprint-callable, pure |
| `GetDownloadTrackPath() -> Str` | native, static, Blueprint-callable, pure |
| `GetFilesOfTypeInFolder(out OutFiles: Array<Str>, Folder: Str, Extension: Str, bFiles: Bool, bDirectories: Bool)` | native, static, Blueprint-callable |
| `GetFilesOfTypeInFolderRoot(out OutFiles: Array<Str>, Folder: Str, Extension: Str, bFiles: Bool, bDirectories: Bool)` | native, static, Blueprint-callable |
| `GetGameModePath() -> Str` | native, static, Blueprint-callable, pure |
| `GetLessonPacksPath() -> Str` | native, static, Blueprint-callable, pure |
| `GetLessonTracksPath() -> Str` | native, static, Blueprint-callable, pure |
| `GetPlaylistsPath() -> Str` | native, static, Blueprint-callable, pure |
| `GetRecordingsPath() -> Str` | native, static, Blueprint-callable, pure |
| `GetTempTrackPath() -> Str` | native, static, Blueprint-callable, pure |
| `GetTribePathDisplayName(Path: Str) -> Str` | native, static, Blueprint-callable, pure |
| `GetUniqueNameForFolder(ParentFolder: Str, NamePrefix: Str, bFiles: Bool, bFolders: Bool, FileExt: Str) -> Str` | native, static, Blueprint-callable |
| `GetUniqueNameForTribeFolder(TribeFolder: Object(TribeFolder), NamePrefix: Str, bFiles: Bool, bFolders: Bool) -> Str` | native, static, Blueprint-callable |
| `GetUserDocumentsPath() -> Str` | native, static, Blueprint-callable, pure |
| `GetUserTrackPath() -> Str` | native, static, Blueprint-callable, pure |
| `GetVisualsMediaPath() -> Str` | native, static, Blueprint-callable, pure |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribePawn

`/Script/TribeXR.TribePawn` : `Pawn`, 960 bytes; vtable 289 entries, 22 overridden or new.

Data members: `InputReplay`: Object, `InputMode`: Enum(ETribePawnInputMode), `AttachMode`: Enum(ETribePawnAttachMode), `AttachActor`: Object, `HeightOffset`: Float, `CustomAnchorOffset`: Struct(Transform), `OnPlayerStateReplicated`: MulticastDelegate, `CameraInput`: Struct(TribePawnCameraInput).

| Function | Kind |
|---|---|
| `GetAttachMode() -> Enum(ETribePawnAttachMode)` | native, Blueprint-callable, pure |
| `GetCustomAnchorOffset() -> Struct(Transform)` | native, Blueprint-callable, pure |
| `GetMouseViewportPixelPosition(WorldContextObject: Object(Object)) -> Struct(Vector2D)` | native, static, Blueprint-callable, pure |
| `GetReplayRecordingComponent() -> Object(InputReplayComponent)` | native, Blueprint-callable, pure |
| `GetVarReplicateConditionOverrides(out OutClass: Class(Object), out OutOverrides: Array<Struct(RepConditionOverride)>)` | native, event, Blueprint-callable, pure, Blueprint event |
| `HandleAudioFilesDropped(ref AddedTracks: Array<Object(TribeTrack)>, DropPosition: Struct(Vector2D))` | native |
| `LoadDroppedTrack(Track: Object(TribeTrack), DropPosition: Struct(Vector2D))` | event, Blueprint event |
| `Multi_SetAttachMode(NewAttachMode: Enum(ETribePawnAttachMode))` | native, event, multicast RPC |
| `Multi_SetCustomAnchorOffset(ref NewOffset: Struct(Transform))` | native, event, multicast RPC |
| `Multi_SetHeightOffset(NewHeightOffset: Float)` | native, event, multicast RPC |
| `Multi_SetHeightOffset_Unreliable(NewHeightOffset: Float)` | native, event, multicast RPC |
| `RefreshAttachPosition()` | native, Blueprint-callable |
| `RefreshHeightOffset()` | native, Blueprint-callable |
| `Server_SetAttachMode(NewAttachMode: Enum(ETribePawnAttachMode))` | native, event, server RPC |
| `Server_SetCustomAnchorOffset(ref NewOffset: Struct(Transform))` | native, event, server RPC |
| `Server_SetHeightOffset(NewHeightOffset: Float)` | native, event, server RPC |
| `Server_SetHeightOffset_Unreliable(NewHeightOffset: Float)` | native, event, server RPC |
| `SetAttachActor(InAttachActor: Object(Actor))` | native, Blueprint-callable |
| `SetAttachMode(NewAttachMode: Enum(ETribePawnAttachMode))` | native, Blueprint-callable |
| `SetCustomAnchorOffset(ref NewOffset: Struct(Transform))` | native, Blueprint-callable |
| `SetHandTrackingHandsMaterial(Material: Object(MaterialInterface))` | event, Blueprint-callable, Blueprint event |
| `SetHandTrackingHandsVisible(bHandMeshVisible: Bool)` | event, Blueprint-callable, Blueprint event |
| `SetHeightOffset(NewHeightOffset: Float, bReplicateReliably: Bool)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `GetLifetimeReplicatedProps`, `ValidateGeneratedRepEnums`, `OnRep_AttachmentReplication`, `BeginPlay`, `EndPlay`, `GatherCurrentMovement`, `OnRep_PlayerState`, `NewVirtual276`, `NewVirtual277`, `NewVirtual278`, `NewVirtual279`, `NewVirtual280`, `NewVirtual281`, `NewVirtual282`, `NewVirtual283`, `NewVirtual284`, `NewVirtual285`, `NewVirtual286`, `NewVirtual287`, `NewVirtual288`.

### TribePlayerController

`/Script/TribeXR.TribePlayerController` : `PlayerController`, 2440 bytes; vtable 503 entries, 8 overridden or new.

Data members: `KeyboardInputComponent`: Object, `OnKeyboardEvent`: MulticastDelegate, `OnKeyboardInputToggled`: MulticastDelegate, `VideoCallManager`: Object, `ActiveCaptureComponent`: Object, `FirstPersonCaptureComponent`: Object, `AutoCamCaptureComponent`: Object, `WidgetComponents`: Array<Object>, `SpectatorCameras`: Array<Object>, `bRenderSpectatorCamera`: Bool, `SpectatorCameraHiddenActors`: Array<Object>, `SpectatorCameraHiddenComponents`: Array<Object>, `ChromaKeyMaterialParameterCollection`: Object, `bHidePawnsInSpectatorCameras`: Bool, `bHideRigInSpectatorCameras`: Bool, `bHideTableInSpectatorCameras`: Bool, `bHideRoomInSpectatorCameras`: Bool, `bChromaKeyBackdropInSpectatorCameras`: Bool, `ChromaKeyColor`: Struct(LinearColor).

| Function | Kind |
|---|---|
| `AddSpectateHiddenActor(HiddenActor: Object(Actor))` | native, Blueprint-callable |
| `AddSpectateHiddenComponent(HiddenComponent: Object(PrimitiveComponent))` | native, Blueprint-callable |
| `AddWidgetComponent(Widget: Object(WidgetComponent))` | native, Blueprint-callable |
| `AutoCamResetBeatOrigin()` | native, Blueprint-callable |
| `InitSpectatorRenderTick(InVideoCallManager: Object(TribeVideoCallManager), InSpectrumAnalyzer: Object(TribeSpectrumAnalyzer))` | native, Blueprint-callable |
| `IsKeyboardInputActive() -> Bool` | native, Blueprint-callable, pure |
| `OnBeatEvent(BPM: Float, Beat: Int)` | native |
| `RemoveSpectateHiddenActor(HiddenActor: Object(Actor))` | native, Blueprint-callable |
| `RemoveSpectateHiddenComponent(HiddenComponent: Object(PrimitiveComponent))` | native, Blueprint-callable |
| `RemoveWidgetComponent(Widget: Object(WidgetComponent))` | native, Blueprint-callable |
| `SetAutoCamMode(AutoCamModeIn: Enum(EAutoCamMode))` | native, Blueprint-callable |
| `SetAutoKeyboardInputOnTextFocus(bAutoKeyboard: Bool)` | native, Blueprint-callable |
| `SetChromaKeyBackdropInSpectatorCameras(ChromaKeyBackdrop: Bool)` | native, Blueprint-callable |
| `SetChromaKeyColor(NewChromaKeyColor: Struct(LinearColor))` | native, Blueprint-callable |
| `SetHidePawnsInSpectatorCameras(HidePawns: Bool)` | native, Blueprint-callable |
| `SetHideRigInSpectatorCameras(HideRig: Bool)` | native, Blueprint-callable |
| `SetHideRoomInSpectatorCameras(HideRoom: Bool)` | native, Blueprint-callable |
| `SetHideTableInSpectatorCameras(HideTable: Bool)` | native, Blueprint-callable |
| `SetKeyboardInputMode(bKeyboardInput: Bool)` | native, Blueprint-callable |
| `UpdateChromaKeyActorOwnership()` | native, Blueprint-callable |
| `UpdateSceneCaptureComponentHiddenActorsWithChromaKey(SceneCaptureComponent: Object(SceneCaptureComponent2D))` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `EndPlay`, `Tick`, `ClientWasKicked_Implementation`, `ClientUnmutePlayer_Implementation`, `ClientMutePlayer_Implementation`, `ToggleSpeaking`.

### TribePlayerState

`/Script/TribeXR.TribePlayerState` : `PlayerState`, 984 bytes; vtable 259 entries, 12 overridden or new.

Data members: `OnUsernameChanged`: MulticastDelegate, `OnOnlinePlatformChanged`: MulticastDelegate, `OnTribeImageUrlChanged`: MulticastDelegate, `OnStagingStateChanged`: MulticastDelegate, `OnMuteStateChanged`: MulticastDelegate, `TribeUsername`: Str, `OnlinePlatform`: Name, `TribeImageUrl`: Str, `StagingState`: Enum(ETribePlayerStagingState), `CachedProfileImage`: Object.

| Function | Kind |
|---|---|
| `GetOnlinePlatform() -> Name` | native, Blueprint-callable, pure |
| `GetProfileImage(ref OnImageReady: Delegate(TribeImageDelegate__DelegateSignature))` | native, Blueprint-callable |
| `GetStagingState() -> Enum(ETribePlayerStagingState)` | native, Blueprint-callable, pure |
| `GetTribeImageUrl() -> Str` | native, Blueprint-callable, pure |
| `GetTribeUserDisplayName() -> Str` | native, Blueprint-callable, pure |
| `GetTribeUsername() -> Str` | native, Blueprint-callable, pure |
| `HandleAccountInfoChanged(ref UpdatedAccountInfo: Struct(TribeAccountInfo))` | native |
| `HandleModerationFlagsChanged(ref UpdatedAccountInfo: Struct(TribeAccountInfo))` | native |
| `IsLocalPlayer() -> Bool` | native, Blueprint-callable, pure |
| `IsMuted() -> Bool` | native, Blueprint-callable, pure |
| `IsSameOnlinePlatform() -> Bool` | native, Blueprint-callable, pure |
| `Mute() -> Bool` | native, Blueprint-callable |
| `OnProfileImageDownloaded(ProfileImage: Object(Texture2DDynamic))` | native |
| `OnRep_OnlinePlatform()` | native |
| `OnRep_StagingState()` | native |
| `OnRep_TribeImageUrl()` | native |
| `OnRep_TribeUsername()` | native |
| `OnUserProfileImageDownloaded(UserId: Str, ProfileImage: Object(Texture2DDynamic))` | native |
| `Server_SetOnlinePlatform(ref OnlinePlatformIn: Name)` | native, event, server RPC |
| `Server_SetTribeImageUrl(ImageUrl: Str)` | native, event, server RPC |
| `Server_SetTribeUsername(Username: Str)` | native, event, server RPC |
| `SetStagingState(NewStagingState: Enum(ETribePlayerStagingState))` | native, Blueprint-callable |
| `Unmute() -> Bool` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `GetLifetimeReplicatedProps`, `ValidateGeneratedRepEnums`, `BeginPlay`, `ClientInitialize`, `NewVirtual253`, `NewVirtual254`, `NewVirtual255`, `NewVirtual256`, `NewVirtual257`, `NewVirtual258`.

### TribePlayerStats

`/Script/TribeXR.TribePlayerStats` : `TribeEncryptedSaveGame`, 168 bytes; vtable 88 entries, 2 overridden or new.

Data members: `LoginId`: Str, `PointsHash`: Str.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeReplaySaveGame

`/Script/TribeXR.TribeReplaySaveGame` : `SaveGame`, 64 bytes; vtable 88 entries, 2 overridden or new.

Data members: `AvatarId`: Str, `EquipmentScale`: Float, `bAutoGrab`: Bool.

| Function | Kind |
|---|---|
| `GetAutoGrabEnabled() -> Bool` | native, Blueprint-callable, pure |
| `GetAvatarId() -> Str` | native, Blueprint-callable, pure |
| `GetEquipmentScale() -> Float` | native, Blueprint-callable, pure |
| `LoadReplayCache(LoadPath: Str) -> Object(TribeReplaySaveGame)` | native, static, Blueprint-callable |
| `SaveAutoGrabEnabled(bAutoGrabEnabled: Bool)` | native, Blueprint-callable |
| `SaveAvatarId(ID: Str)` | native, Blueprint-callable |
| `SaveEquipmentScale(Scale: Float)` | native, Blueprint-callable |
| `SaveReplayCache(SavePath: Str) -> Bool` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeRigSaveGame

`/Script/TribeXR.TribeRigSaveGame` : `SaveGame`, 88 bytes; vtable 88 entries, 2 overridden or new.

Data members: `MixerDevice`: Object, `ChannelDevices`: Array<Object>, `EquipmentLayoutString`: Str, `EquipmentScale`: Float.

| Function | Kind |
|---|---|
| `GetRigSaveGameName() -> Str` | native, static, Blueprint-callable, pure |
| `GetRigState(out OutMixerDevice: Class(TribeMixerInfo), out OutChannelDevices: Array<Class(TribeChannelDeviceInfo)>, out OutEquipmentLayoutString: Str, out DeckScale: Float)` | native, Blueprint-callable, pure |
| `LoadRigSaveGame(SaveDirectory: Str) -> Object(TribeRigSaveGame)` | native, static, Blueprint-callable |
| `MakeRigSaveGame() -> Object(TribeRigSaveGame)` | native, static, Blueprint-callable |
| `SaveRigState(SaveDirectory: Str, InMixerDevice: Class(TribeMixerInfo), InChannelDevices: Array<Class(TribeChannelDeviceInfo)>, InEquipmentLayoutString: Str, DeckScale: Float)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeRoom

`/Script/TribeXR.TribeRoom` : `Object`, 552 bytes; vtable 88 entries, 2 overridden or new.

Data members: `Session`: Struct(TribeSession), `HostFriend`: Object, `CachedProfileImage`: Object, `FriendsInRoom`: Array<Object>, `OnRoomUpdated`: MulticastDelegate, `OnFriendsUpdated`: MulticastDelegate.

| Function | Kind |
|---|---|
| `GetGenre() -> Str` | native, Blueprint-callable, pure |
| `GetHostIdStr() -> Str` | native, Blueprint-callable, pure |
| `GetHostImageUrl() -> Str` | native, Blueprint-callable, pure |
| `GetHostName() -> Str` | native, Blueprint-callable, pure |
| `GetHostNativeId() -> Str` | native, Blueprint-callable, pure |
| `GetHostUsername() -> Str` | native, Blueprint-callable, pure |
| `GetJoinability() -> Enum(ETribeSessionJoinability)` | native, Blueprint-callable, pure |
| `GetMaxPlayers() -> Int` | native, Blueprint-callable, pure |
| `GetNumOpenSlots() -> Int` | native, Blueprint-callable, pure |
| `GetNumPlayers() -> Int` | native, Blueprint-callable, pure |
| `GetProfileImage(ref OnImageReady: Delegate(TribeImageDelegate__DelegateSignature), WorldContextObject: Object(Object))` | native, Blueprint-callable |
| `GetSessionIdStr() -> Str` | native, Blueprint-callable, pure |
| `IsCurrentRoom() -> Bool` | native, Blueprint-callable, pure |
| `IsJoinable() -> Bool` | native, Blueprint-callable, pure |
| `IsValidSession() -> Bool` | native, Blueprint-callable, pure |
| `IsVersionCompatible() -> Bool` | native, Blueprint-callable, pure |
| `JoinRoom() -> Bool` | native, Blueprint-callable |
| `OnProfileImageDownloaded(ProfileImage: Object(Texture2DDynamic))` | native |
| `OnUserProfileImageDownloaded(UserId: Str, ProfileImage: Object(Texture2DDynamic))` | native |
| `UpdateSessionData(ref SessionData: Struct(TribeSession))` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeSkinTypes

`/Script/TribeXR.TribeSkinTypes` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeSortingClient

`/Script/TribeXR.TribeSortingClient` : `BlueprintAsyncActionBase`, 176 bytes; vtable 92 entries, 3 overridden or new.

Data members: `OnSortingComplete`: Delegate, `OnMetadataImported`: Delegate, `bImportAllMetadata`: Bool, `SortProgress`: Enum(ETrackSortProgress), `MetadataImportedTracks`: Array<Object>, `Files`: Array<Object>, `SortedFiles`: Array<Object>, `World`: Object, `UserData`: Object.

| Function | Kind |
|---|---|
| `HandleSortingFiles(SortMode: Enum(ETrackSortMode), SecondarySortMode: Enum(ETrackSortMode), ref Files: Array<Object(TribeFile)>, out OutSortedFiles: Array<Object(TribeFile)>)` | native, static |
| `SeparateUnsortableTracks(SortMode: Enum(ETrackSortMode), InTracks: Array<Object(TribeTrack)>, out OutSortableTracks: Array<Object(TribeTrack)>, out OutUnsortableTracks: Array<Object(TribeTrack)>)` | native, static |
| `SortFiles(WorldContextObject: Object(Object), SortMethod: Enum(ETrackSortMode), SecondarySortMethod: Enum(ETrackSortMode), bImportAllMetadata: Bool, ref Files: Array<Object(TribeFile)>, SortingCompleted: Delegate(TribeSortingCompleteDelegateDynamic__DelegateSignature), MetadataImported: Delegate(TribeSortMetadataImportDelegateDynamic__DelegateSignature), UserData: Object(Object)) -> Object(TribeSortingClient)` | native, static, Blueprint-callable |
| `SortingHelper(LeftItem: Object(TribeTrack), RightItem: Object(TribeTrack), SortMode: Enum(ETrackSortMode)) -> Enum(ESortComparisonResult)` | native, static |

C++ overrides: `Destructor`, `DeletingDestructor`, `Activate`.

### TribeSoundCloudClient

`/Script/TribeXR.TribeSoundCloudClient` : `Object`, 624 bytes; vtable 88 entries, 2 overridden or new.

Data members: `OnLoginComplete`: MulticastDelegate, `OnLogoutComplete`: MulticastDelegate, `OnUserPlaylistsResult`: MulticastDelegate, `FreePlaylistsFolder`: Object.

| Function | Kind |
|---|---|
| `GetFreePlaylistsFolder() -> Object(TribeFolder)` | native, Blueprint-callable, pure |
| `IsLoggedIn() -> Bool` | native, Blueprint-callable, pure |
| `IsLoggingIn() -> Bool` | native, Blueprint-callable, pure |
| `Login(AccessToken: Str)` | native, Blueprint-callable |
| `LoginFromCache() -> Bool` | native, Blueprint-callable |
| `LoginFromClipboard() -> Bool` | native, Blueprint-callable |
| `LoginWithCode(PKCECode: Str)` | native, Blueprint-callable |
| `LoginWithRefreshToken(RefreshToken: Str)` | native, Blueprint-callable |
| `Logout()` | native, Blueprint-callable |
| `QueryLikedPlaylists()` | native, Blueprint-callable |
| `QueryLikedTracks()` | native, Blueprint-callable |
| `QueryPlaylists()` | native, Blueprint-callable |
| `QueryPlaylistTracks(PlaylistId: Int64)` | native, Blueprint-callable |
| `QueryTrackDownloadUrl(TrackId: Int64)` | native, Blueprint-callable |
| `QueryTrackMetadata(TrackId: Int64)` | native, Blueprint-callable |
| `ReportTrackCheckpoint(TrackId: Int64)` | native, Blueprint-callable |
| `ReportTrackPlayed(TrackId: Int64)` | native, Blueprint-callable |
| `ReportTrackStop(TrackId: Int64)` | native, Blueprint-callable |
| `RequestSoundCloudOAuthTokens()` | native, Blueprint-callable |
| `SearchSoundCloud(SearchString: Str, MaxResults: Int, Offset: Int)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeSoundCloudFolder

`/Script/TribeXR.TribeSoundCloudFolder` : `TribeStreamFolder`, 192 bytes; vtable 93 entries, 4 overridden or new.

C++ overrides: `TribeFolder_NewVirtual89`, `TribeStreamFolder_NewVirtual90`, `TribeStreamFolder_NewVirtual91`, `TribeStreamFolder_NewVirtual92`.

### TribeSoundCloudTrack

`/Script/TribeXR.TribeSoundCloudTrack` : `TribeStreamTrack`, 576 bytes; vtable 119 entries, 18 overridden or new.

| Function | Kind |
|---|---|
| `HandleDownloadFinished(ref FileBuffer: Array<Byte>)` | native |
| `HandleDownloadProgress(BytesDownloaded: Int, TotalBytes: Int)` | native |

C++ overrides: `Destructor`, `DeletingDestructor`, `FinishDestroy`, `TribeFile_NewVirtual88`, `TribeFile_NewVirtual90`, `TribeFile_NewVirtual92`, `TribeTrack_NewVirtual96`, `TribeTrack_NewVirtual98`, `TribeTrack_NewVirtual100`, `TribeTrack_NewVirtual102`, `TribeTrack_NewVirtual107`, `TribeTrack_NewVirtual108`, `TribeBufferTrack_NewVirtual109`, `TribeStreamTrack_NewVirtual112`, `TribeStreamTrack_NewVirtual115`, `TribeStreamTrack_NewVirtual116`, `TribeStreamTrack_NewVirtual117`, `TribeStreamTrack_NewVirtual118`.

### TribeSpectrumAnalyzer

`/Script/TribeXR.TribeSpectrumAnalyzer` : `Actor`, 1072 bytes; vtable 228 entries, 5 overridden or new.

Data members: `OnBeatEvent`: MulticastDelegate, `FrequenciesToAnalyze`: Array<Float>, `MaxMagnitudes`: Array<Float>, `SmoothedMagnitudes`: Array<Float>, `bShouldUseCustomAlpha`: Bool, `CustomAlpha`: Float, `CurrentTrack`: Object, `CurrentMasterDeck`: Object.

| Function | Kind |
|---|---|
| `GetFrequencyResults() -> Array<Float>` | native, Blueprint-callable |
| `OnAnalysisReady(Track: Object(TribeTrack))` | native, Blueprint-callable |
| `OnDeckTrackChanged(Deck: Object(Object))` | native, Blueprint-callable |
| `OnDecreaseMaxValueTimer()` | native |
| `OnEquipmentSpawned()` | native, Blueprint-callable |
| `OnSyncMasterChanged(SyncMaster: Object(Object))` | native, Blueprint-callable |
| `OnTrackPlayed(Track: Object(TribeTrack))` | native, Blueprint-callable |
| `StartProcessing()` | native, Blueprint-callable |
| `StopProcessing()` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginPlay`, `EndPlay`, `Tick`.

### TribeStandaloneSession

`/Script/TribeXR.TribeStandaloneSession` : `TribeOnlineSession`, 20648 bytes; vtable 134 entries, 9 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`, `TribeOnlineSession_NewVirtual95`, `TribeOnlineSession_NewVirtual113`, `TribeOnlineSession_NewVirtual116`, `TribeOnlineSession_NewVirtual117`, `TribeOnlineSession_NewVirtual119`, `TribeOnlineSession_NewVirtual121`, `TribeOnlineSession_NewVirtual132`.

### TribeSteamSession

`/Script/TribeXR.TribeSteamSession` : `TribeOnlineSession`, 20600 bytes; vtable 134 entries, 13 overridden or new.

C++ overrides: `Destructor`, `RegisterOnlineDelegates`, `TribeOnlineSession_NewVirtual94`, `TribeOnlineSession_NewVirtual98`, `TribeOnlineSession_NewVirtual115`, `TribeOnlineSession_NewVirtual116`, `TribeOnlineSession_NewVirtual117`, `TribeOnlineSession_NewVirtual118`, `TribeOnlineSession_NewVirtual119`, `TribeOnlineSession_NewVirtual120`, `TribeOnlineSession_NewVirtual126`, `TribeOnlineSession_NewVirtual127`, `TribeOnlineSession_NewVirtual132`.

### TribeStreamFolder

`/Script/TribeXR.TribeStreamFolder` : `TribeFolder`, 152 bytes; vtable 93 entries, 7 overridden or new.

Data members: `OnPlaylistQueryUpdate`: MulticastDelegate.

| Function | Kind |
|---|---|
| `GetQueryState() -> Enum(ETribeStreamingQueryState)` | native, Blueprint-callable, pure |
| `GetStreamingClientName() -> Name` | native, Blueprint-callable, pure |
| `InitAsSearchQuery(SearchQuery: Str)` | native, Blueprint-callable |
| `Query(QueryClient: Object(Object)) -> Enum(ETribeStreamingQueryState)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `TribeFolder_NewVirtual88`, `TribeFolder_NewVirtual89`, `NewVirtual90`, `NewVirtual91`, `NewVirtual92`.

### TribeStreamTrack

`/Script/TribeXR.TribeStreamTrack` : `TribeBufferTrack`, 512 bytes; vtable 119 entries, 14 overridden or new.

Data members: `OnTrackAvailabilityChanged`: MulticastDelegate, `OnTrackDownloadProgress`: MulticastDelegate.

| Function | Kind |
|---|---|
| `CanLoadStreamTrack() -> Bool` | native, Blueprint-callable, pure |
| `CanLoadWithoutLogin() -> Bool` | native, Blueprint-callable, pure |
| `CanShareWithLogin() -> Bool` | native, Blueprint-callable, pure |
| `GetReportPositionRate() -> Float` | native, Blueprint-callable, pure |
| `HasBeenDownloaded() -> Bool` | native, Blueprint-callable, pure |
| `IsStreamingClientLoggedIn() -> Bool` | native, Blueprint-callable, pure |
| `ReportStreamTrackPosition(bPlaying: Bool, PositionMs: Int, ReportObject: Object(Object))` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `TribeTrack_NewVirtual97`, `TribeTrack_NewVirtual98`, `TribeTrack_NewVirtual103`, `TribeTrack_NewVirtual104`, `TribeBufferTrack_NewVirtual111`, `NewVirtual112`, `NewVirtual113`, `NewVirtual114`, `NewVirtual115`, `NewVirtual116`, `NewVirtual117`, `NewVirtual118`.

### TribeSubtitles

`/Script/TribeXR.TribeSubtitles` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `GetSubtitleIndexFromTime(ref Subtitles: Array<Struct(TribeSubtitle)>, Time: Float, StartIndex: Int) -> Int` | native, static, Blueprint-callable |
| `LoadSubtitles(FilePath: Str, out OutSubtitles: Array<Struct(TribeSubtitle)>) -> Bool` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeTempTrack

`/Script/TribeXR.TribeTempTrack` : `TribeBufferTrack`, 520 bytes; vtable 112 entries, 7 overridden or new.

Data members: `FileTransfer`: Object.

C++ overrides: `Destructor`, `DeletingDestructor`, `TribeFile_NewVirtual92`, `TribeTrack_NewVirtual93`, `TribeTrack_NewVirtual101`, `TribeTrack_NewVirtual104`, `TribeBufferTrack_NewVirtual109`.

### TribeTidalClient

`/Script/TribeXR.TribeTidalClient` : `Object`, 312 bytes; vtable 88 entries, 2 overridden or new.

Data members: `OnLoginResult`: MulticastDelegate, `OnLogoutComplete`: MulticastDelegate, `OnUserCollectionResult`: MulticastDelegate.

| Function | Kind |
|---|---|
| `IsLoggedIn() -> Bool` | native, Blueprint-callable, pure |
| `Login(InOAuthCode: Str)` | native |
| `LoginFromCache() -> Bool` | native, Blueprint-callable |
| `LoginFromClipboard() -> Bool` | native, Blueprint-callable |
| `Logout()` | native, Blueprint-callable |
| `QueryUserCollection()` | native, Blueprint-callable |
| `RequestTidalOAuthTokens()` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeTidalFolder

`/Script/TribeXR.TribeTidalFolder` : `TribeStreamFolder`, 184 bytes; vtable 93 entries, 6 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`, `TribeFolder_NewVirtual89`, `TribeStreamFolder_NewVirtual90`, `TribeStreamFolder_NewVirtual91`, `TribeStreamFolder_NewVirtual92`.

### TribeTidalTrack

`/Script/TribeXR.TribeTidalTrack` : `TribeStreamTrack`, 560 bytes; vtable 119 entries, 17 overridden or new.

| Function | Kind |
|---|---|
| `HandleDownloadFinished(ref FileBuffer: Array<Byte>)` | native |
| `HandleDownloadProgress(BytesDownloaded: Int, TotalBytes: Int)` | native |

C++ overrides: `Destructor`, `DeletingDestructor`, `FinishDestroy`, `TribeFile_NewVirtual88`, `TribeFile_NewVirtual90`, `TribeFile_NewVirtual92`, `TribeTrack_NewVirtual96`, `TribeTrack_NewVirtual98`, `TribeTrack_NewVirtual100`, `TribeTrack_NewVirtual102`, `TribeTrack_NewVirtual106`, `TribeTrack_NewVirtual107`, `TribeTrack_NewVirtual108`, `TribeBufferTrack_NewVirtual109`, `TribeBufferTrack_NewVirtual110`, `TribeStreamTrack_NewVirtual117`, `TribeStreamTrack_NewVirtual118`.

### TribeTrack

`/Script/TribeXR.TribeTrack` : `TribeFile`, 496 bytes; vtable 109 entries, 20 overridden or new.

Data members: `TrackLibrary`: Object, `MetaData`: Struct(TribeTrackMetadata), `bHasMetadata`: Bool, `Memory`: Struct(TribePlayerMemory), `OnPlayerMemoryUpdated`: MulticastDelegate, `OnAnalysisReady`: MulticastDelegate, `OnMetadataReady`: MulticastDelegate, `OnAlbumArtReady`: MulticastDelegate, `OnTrackPlayed`: MulticastDelegate, `Analysis`: Struct(SuperPoweredAnalysisResults), `bHasAnalysis`: Bool, `bHasBeenPlayed`: Bool, `AlbumArt`: Object, `bHasAttemptedAlbumArtLoad`: Bool.

| Function | Kind |
|---|---|
| `Analyze(bForceStart: Bool)` | native, Blueprint-callable |
| `GetAlbum() -> Str` | native, Blueprint-callable, pure |
| `GetArtist() -> Str` | native, Blueprint-callable, pure |
| `GetBeatgridStartMs() -> Float` | native, Blueprint-callable, pure |
| `GetBpm() -> Float` | native, Blueprint-callable, pure |
| `GetGenre() -> Str` | native, Blueprint-callable, pure |
| `GetId() -> Name` | native, Blueprint-callable, pure |
| `GetKeyIndex() -> Int` | native, Blueprint-callable, pure |
| `GetKeyString() -> Str` | native, Blueprint-callable, pure |
| `GetKeyStringOpenkey() -> Str` | native, Blueprint-callable, pure |
| `GetNowPlayingString() -> Str` | native, Blueprint-callable, pure |
| `GetStreamingClientName() -> Name` | native, Blueprint-callable, pure |
| `GetTrackArt() -> Object(Texture)` | native, Blueprint-callable, pure |
| `GetTrackManager() -> Object(TrackManager)` | native, Blueprint-callable, pure |
| `GetTrackName() -> Str` | native, Blueprint-callable, pure |
| `HandleAlbumArtResults(AlbumTexture: Object(Texture2DDynamic))` | native |
| `HandleImageResults(ref ImageResults: Array<Byte>, UserObject: Object(Object))` | native |
| `HandleMetadataResults(ref MetadataResults: Struct(SuperPoweredMetadataResults), UserObject: Object(Object))` | native |
| `HasBeatInfo() -> Bool` | native, Blueprint-callable, pure |
| `InitAlbumArtAsync(WorldContextObject: Object(Object), bForceRefresh: Bool)` | native, Blueprint-callable |
| `InitMetadata(bForceRefresh: Bool)` | native, Blueprint-callable |
| `InitMetadataAsync(WorldContextObject: Object(Object), bForceRefresh: Bool)` | native, Blueprint-callable |
| `IsCopyright() -> Bool` | native, Blueprint-callable, pure |
| `IsTemporaryTrack() -> Bool` | native, Blueprint-callable, pure |
| `IsTrackRetained() -> Bool` | native, Blueprint-callable, pure |
| `MarkAsPlayed()` | native, Blueprint-callable |
| `ReleaseTrack(RetainingObject: Object(Object))` | native, Blueprint-callable |
| `RequestAddTrackToPlaylist()` | native, Blueprint-callable |
| `ResetBeatGrid()` | native, Blueprint-callable |
| `ResetSessionState()` | native, Blueprint-callable |
| `RetainTrack(RetainingObject: Object(Object))` | native, Blueprint-callable |
| `SavePlayerMemory()` | native, Blueprint-callable |
| `SetAnalysis(ref NewAnalysis: Struct(SuperPoweredAnalysisResults))` | native, Blueprint-callable |
| `SetBeatGrid(NewBpm: Float, NewStartMs: Float)` | native, Blueprint-callable |
| `SetBeatStartMs(NewStartMs: Float)` | native, Blueprint-callable |
| `SetBpm(NewBpm: Float)` | native, Blueprint-callable |
| `SetPlayerMemory(ref PlayerMemory: Struct(TribePlayerMemory))` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `TribeFile_NewVirtual88`, `TribeFile_NewVirtual90`, `NewVirtual93`, `NewVirtual94`, `NewVirtual95`, `NewVirtual96`, `NewVirtual97`, `NewVirtual98`, `NewVirtual99`, `NewVirtual100`, `NewVirtual101`, `NewVirtual102`, `NewVirtual103`, `NewVirtual104`, `NewVirtual105`, `NewVirtual106`, `NewVirtual107`, `NewVirtual108`.

### TribeTrackPackAddon

`/Script/TribeXR.TribeTrackPackAddon` : `TribeAddon`, 240 bytes; vtable 92 entries, 6 overridden or new.

Data members: `PreviewArtTexture`: Object, `AlbumArtTexture`: Object.

| Function | Kind |
|---|---|
| `GetTrackPakDisplayName(PakFileName: Str) -> Str` | native, static, Blueprint-callable, pure |

C++ overrides: `Destructor`, `DeletingDestructor`, `TribeAddon_NewVirtual88`, `TribeAddon_NewVirtual89`, `TribeAddon_NewVirtual90`, `TribeAddon_NewVirtual91`.

### TribeTwitchManager

`/Script/TribeXR.TribeTwitchManager` : `Actor`, 952 bytes; vtable 229 entries, 7 overridden or new.

Data members: `OnStreamingStatusChanged`: MulticastDelegate, `OnStreamInfoUpdated`: MulticastDelegate, `OnValidateAccessTokenOrGetAuthCode`: MulticastDelegate, `OnGetAccessTokenFromBackend`: MulticastDelegate, `OnLoggedInChanged`: MulticastDelegate, `ChatChannel`: Str, `Username`: Str, `AccessToken`: Str, `ChatClient`: Object.

| Function | Kind |
|---|---|
| `BP_OnChatChannelChanged()` | event, Blueprint event |
| `BP_OnChatMessageReceived(ref MessageData: Struct(TwitchChatMessage))` | event, Blueprint event |
| `BP_OnLoginComplete(bSuccess: Bool)` | event, Blueprint event |
| `CanAccessTwitchApi() -> Bool` | native, Blueprint-callable, pure |
| `GetAccessTokenFromBackend(AuthCode: Str)` | native, Blueprint-callable |
| `GetAltLoginUrl() -> Str` | native, Blueprint-callable, pure |
| `GetChatChannel() -> Str` | native, Blueprint-callable, pure |
| `GetIngestUrl() -> Str` | native, Blueprint-callable, pure |
| `GetTwitchViewerCount() -> Int` | native, Blueprint-callable, pure |
| `IsLoggedIn() -> Bool` | native, Blueprint-callable, pure |
| `IsStreamLive() -> Bool` | native, Blueprint-callable, pure |
| `Login() -> Bool` | native, Blueprint-callable |
| `Multi_SetChatChannel(NewChatChannel: Str)` | native, event, multicast RPC |
| `RequestTwitchOAuthTokens()` | native, static, Blueprint-callable |
| `SendChatMessage(ChatMessage: Str)` | native, Blueprint-callable |
| `SetAccessToken(NewAccessToken: Str)` | native, Blueprint-callable |
| `SetChatChannel(ChannelName: Str)` | native, Blueprint-callable |
| `StoreAuthInfoFromClipboard() -> Bool` | native, Blueprint-callable |
| `ValidateAccessTokenOrGetAuthCode()` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `GetLifetimeReplicatedProps`, `ValidateGeneratedRepEnums`, `BeginPlay`, `Destroyed`, `NewVirtual228`.

### TribeVideoCallChannel

`/Script/TribeXR.TribeVideoCallChannel` : `Object`, 136 bytes; vtable 88 entries, 2 overridden or new.

Data members: `ChannelName`: Str, `ChannelMode`: Enum(ETribeVideoCallChannelMode), `NativeID`: Str, `EosId`: Str, `ImageUrl`: Str, `CachedProfileImage`: Object.

| Function | Kind |
|---|---|
| `GetProfileImage(ref OnImageReady: Delegate(TribeImageDelegate__DelegateSignature), WorldContextObject: Object(Object))` | native, Blueprint-callable |
| `IsOwnChannel(OnlineId: Str) -> Bool` | native, Blueprint-callable, pure |
| `OnProfileImageDownloaded(ProfileImage: Object(Texture2DDynamic))` | native |
| `OnUserProfileImageDownloaded(UserId: Str, ProfileImage: Object(Texture2DDynamic))` | native |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeVideoCallChannelRoom

`/Script/TribeXR.TribeVideoCallChannelRoom` : `Object`, 56 bytes; vtable 88 entries, 2 overridden or new.

Data members: `TribeRoom`: Object, `TribeVideoCallChannel`: Object.

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeVideoCallManager

`/Script/TribeXR.TribeVideoCallManager` : `Actor`, 41712 bytes; vtable 230 entries, 11 overridden or new.

Data members: `ActiveCaptureComponent`: Object, `OnVideoCallStartSuccessDelegate`: MulticastDelegate, `OnVideoCallStartFailureDelegate`: MulticastDelegate, `OnVideoCallErrorDelegate`: MulticastDelegate, `OnUserListChangedDelegate`: MulticastDelegate, `OnChannelListReadyDelegate`: MulticastDelegate, `OnCallEndedDelegate`: MulticastDelegate, `OnHostInactiveDelegate`: MulticastDelegate, `OnUserInfoReady`: MulticastDelegate, `OnSpectatorAspectRatioChanged`: MulticastDelegate, `VideoCallUsers`: Array<Object>, `OnAudioOutputTypeChanged`: MulticastDelegate, `OnVideoOutputTypeChanged`: MulticastDelegate, `OnPermaMutedChanged`: MulticastDelegate, `OnInVideoCallReplicated`: MulticastDelegate, `OnInVideoCallReplicatedEnded`: MulticastDelegate, `bIsModerator`: Bool, `bInVideoCallReplicated`: Bool, `SpectatorMaterial`: Object, `AudioOutputType`: Enum(ETribeVideoCallAudioOutputType), `VideoOutputType`: Enum(ETribeVideoCallVideoOutputType), `MasterAudioLevel`: Float, `MicAudioLevel`: Float, `bPermaMuted`: Bool, `VideoCallMenu`: Object, `DefaultProfileTextures`: Array<Object>, `DefaultLocalProfileTexture`: Object, `OnStagingModeChanged`: MulticastDelegate, `OnLocalUserPriorityChanged`: MulticastDelegate, `OnStageQueueUsersChanged`: MulticastDelegate, `OnStageQueueTimerChanged`: MulticastDelegate, `OnChannelStreamingChanged`: MulticastDelegate, `OnStageButtonStateChanged`: MulticastDelegate, `OnNewMetaverseAction`: MulticastDelegate, `Presenter`: Object, `OnDisplayBPMChanged`: MulticastDelegate, `OnDisplayTrackChanged`: MulticastDelegate, `VideoCallChannel`: Str, `HostVideoCallChannel`: Str, `VideoCallStage`: Enum(ETribeVideoCallStage), `HostVideoCallStage`: Enum(ETribeVideoCallStage), `VideoCallChannelMode`: Enum(ETribeVideoCallChannelMode), `HostVideoCallChannelMode`: Enum(ETribeVideoCallChannelMode), `VideoCallChannelList`: Array<Object>, `StageQueueUsers`: Array<Object>.

| Function | Kind |
|---|---|
| `AddToStageQueue()` | native, Blueprint-callable |
| `AdvanceToNextInStageQueue() -> Bool` | native, Blueprint-callable |
| `BanUser(UserId: Int)` | native, Blueprint-callable |
| `EndCall()` | native, Blueprint-callable |
| `GenerateUsername() -> Str` | native, Blueprint-callable, pure |
| `GetChannelList() -> Array<Object(TribeVideoCallChannel)>` | native, Blueprint-callable, pure |
| `GetChannelMode() -> Enum(ETribeVideoCallChannelMode)` | native, Blueprint-callable, pure |
| `GetDesiredCaptureAspectRatio() -> Float` | native, Blueprint-callable, pure |
| `GetIsChannelStreaming() -> Bool` | native, Blueprint-callable, pure |
| `GetIsStageQueuePlaying(out TimerValid: Bool) -> Bool` | native, Blueprint-callable, pure |
| `GetLocalUserPriority() -> Enum(ETribeVideoCallUserPriority)` | native, Blueprint-callable, pure |
| `GetNumberOfUsers() -> Int` | native, Blueprint-callable, pure |
| `GetStageButtonState() -> Enum(ETribeVideoCallStageButtonState)` | native, Blueprint-callable, pure |
| `GetStagingMode() -> Enum(ETribeVideoCallStagingMode)` | native, Blueprint-callable, pure |
| `GetVanityURL() -> Str` | native, Blueprint-callable, pure |
| `GetVideoCallAvailableModes() -> Array<Str>` | native, Blueprint-callable, pure |
| `GetVideoCallRtmpStreamEnableSetting() -> Bool` | native, Blueprint-callable, pure |
| `GetVideoCallRtmpStreamUrlSetting(DefaultRtmpStreamUrl: Str) -> Str` | native, Blueprint-callable, pure |
| `GetVideoCallTwitchStreamEnableSetting() -> Bool` | native, Blueprint-callable, pure |
| `GetVideoCallUserMode() -> Enum(ETribeVideoCallUserMode)` | native, Blueprint-callable, pure |
| `GetVideoOutputType() -> Enum(ETribeVideoCallVideoOutputType)` | native, Blueprint-callable, pure |
| `GetWorkshopChannel(out bSuccess: Bool) -> Object(TribeVideoCallChannel)` | native, Blueprint-callable, pure |
| `IsChannelWorkshop() -> Bool` | native, Blueprint-callable, pure |
| `IsCurrentChannel(ChannelName: Str) -> Bool` | native, Blueprint-callable, pure |
| `IsUpdateChannelListActive() -> Bool` | native, Blueprint-callable, pure |
| `JoinHostVideoCall()` | native, Blueprint-callable |
| `MainMenuVisibilityChanged(bVisibility: Bool)` | native, Blueprint-callable |
| `MiniMenuVisibilityChanged(bVisibility: Bool)` | native, Blueprint-callable |
| `MoveToAudience(UserId: Int)` | native, Blueprint-callable |
| `MoveToStage(UserId: Int)` | native, Blueprint-callable |
| `Multi_ReplicateVideoCallEnded(ChannelName: Str)` | native, event, multicast RPC |
| `Multi_ReplicateVideoCallStarted(ChannelName: Str, Stage: Enum(ETribeVideoCallStage), ChannelMode: Enum(ETribeVideoCallChannelMode))` | native, event, multicast RPC |
| `MuteUser(UserId: Int)` | native, Blueprint-callable |
| `NotifySessionStateChanged(NewSessionState: Enum(ETribeSessionState))` | native, Blueprint-callable |
| `OnActivePlayersChanged(ref Players: Array<Object(TribePlayerState)>)` | native |
| `OnNewTrackLoaded(NewTrackLoaded: Object(TribeTrack))` | native |
| `OnRep_InVideoCallReplicated()` | native |
| `PromoteUserToStage(UserId: Int)` | native, Blueprint-callable |
| `RemoveFromStageQueue()` | native, Blueprint-callable |
| `RemoveUserFromStageQueue(UserId: Int)` | native, Blueprint-callable |
| `ResetStageTimer()` | native, Blueprint-callable |
| `SetAudioOutputType(AudioOutputTypeIn: Enum(ETribeVideoCallAudioOutputType))` | native, Blueprint-callable |
| `SetChannelStreaming(bIsStreamingIn: Bool)` | native, Blueprint-callable |
| `SetMasterAudioLevel(Level: Float)` | native, Blueprint-callable |
| `SetMicAudioLevel(Level: Float)` | native, Blueprint-callable |
| `SetStageQueueTimerSeconds(Seconds: Int)` | native, Blueprint-callable |
| `SetStagingMode(StagingModeIn: Enum(ETribeVideoCallStagingMode))` | native, Blueprint-callable |
| `SetVideoCallPresenterLayoutMode(LayoutMode: Enum(ETribeVideoCallLayoutMode))` | native, Blueprint-callable |
| `SetVideoCallRtmpStreamEnableSetting(RtmpStreamEnableSetting: Bool)` | native, Blueprint-callable |
| `SetVideoCallRtmpStreamUrlSetting(RtmpStreamUrl: Str)` | native, Blueprint-callable |
| `SetVideoCallTwitchStreamEnableSetting(TwitchStreamEnableSetting: Bool)` | native, Blueprint-callable |
| `SetVideoOutputType(VideoOutputTypeIn: Enum(ETribeVideoCallVideoOutputType))` | native, Blueprint-callable |
| `StageButtonClick()` | native, Blueprint-callable |
| `StartCallWithParameters(Username: Str, RtmpUrl: Str, AltRtmpUrl: Str, DesiredUserPriority: Enum(ETribeVideoCallUserPriority), DesiredChannel: Str, ChannelMode: Enum(ETribeVideoCallChannelMode))` | native, Blueprint-callable |
| `StreamingMenuVisibilityChanged(bVisibility: Bool)` | native, Blueprint-callable |
| `ToggleStageQueuePlaying()` | native, Blueprint-callable |
| `UpdateChannelList()` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginDestroy`, `GetLifetimeReplicatedProps`, `ValidateGeneratedRepEnums`, `BeginPlay`, `EndPlay`, `Tick`, `PostInitializeComponents`, `NewVirtual228`, `NewVirtual229`.

### TribeVideoCallPresenter

`/Script/TribeXR.TribeVideoCallPresenter` : `Object`, 104 bytes; vtable 88 entries, 2 overridden or new.

Data members: `OnLayoutChangedDelegate`: MulticastDelegate, `Screens`: Array<Object>, `Users`: Array<Object>, `Manager`: Object, `LayoutMode`: Enum(ETribeVideoCallLayoutMode).

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeVideoCallSchedule

`/Script/TribeXR.TribeVideoCallSchedule` : `Actor`, 744 bytes; vtable 228 entries, 3 overridden or new.

Data members: `OnVideoCallEventUpdate`: MulticastDelegate, `EventArray`: Array<Object>.

| Function | Kind |
|---|---|
| `CheckForEventUpdate()` | native |
| `FetchSchedule()` | native, Blueprint-callable |
| `GetCurrentOrNextEventOfType(EventType: Enum(ETribeEventType)) -> Struct(TribeUpcomingEvent)` | native, Blueprint-callable |
| `GetWorkshopEventData() -> Struct(VideoCallEventData)` | native, Blueprint-callable |
| `HandleSubscriptionUpdate(bUpdateSuccess: Bool)` | native |
| `IsFetchScheduleActive() -> Bool` | native, Blueprint-callable, pure |
| `SetEventUpdateCheckActive(bActive: Bool, CheckRate: Float)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginPlay`.

### TribeVideoCallScreen

`/Script/TribeXR.TribeVideoCallScreen` : `Actor`, 752 bytes; vtable 228 entries, 3 overridden or new.

Data members: `OnTextureChangedDelegate`: MulticastDelegate, `OnAspectRatioChangedDelegate`: MulticastDelegate, `StaticMeshComponent`: Object, `TextRenderComponent`: Object, `ScreenTexture`: Object, `bHasCustomMaterial`: Bool, `Texture`: Object, `DefaultTexture`: Object, `Material`: Object.

| Function | Kind |
|---|---|
| `GetAspectRatio() -> Float` | native, Blueprint-callable, pure |

C++ overrides: `Destructor`, `DeletingDestructor`, `PostInitializeComponents`.

### TribeVideoCallUser

`/Script/TribeXR.TribeVideoCallUser` : `Object`, 352 bytes; vtable 88 entries, 2 overridden or new.

Data members: `UserId`: Int, `Name`: Str, `Volume`: Int, `AudioState`: Enum(ETribeVideoCallAudioState), `MuteState`: Enum(ETribeVideoCallMuteState), `VideoState`: Bool, `Priority`: Int, `VrPlatform`: Str, `VrPlatformId`: Str, `EosId`: Str, `TribeImageUrl`: Str, `SessionState`: Int, `bRaiseHand`: Bool, `bInRtm`: Bool, `bInRtc`: Bool, `bIsLocalUser`: Bool, `bSpectator`: Bool, `OnUserNameChangedDelegate`: MulticastDelegate, `OnVrPlatformIdChangedDelegate`: MulticastDelegate, `OnEosIdChangedDelegate`: MulticastDelegate, `OnImageUrlChangedDelegate`: MulticastDelegate, `OnSessionStateChangedDelegate`: MulticastDelegate, `OnUserVolumeChangedDelegate`: MulticastDelegate, `OnUserAudioStateChangedDelegate`: MulticastDelegate, `OnUserMuteStateChangedDelegate`: MulticastDelegate, `OnUserVideoStateChangedDelegate`: MulticastDelegate, `OnUserStageButtonChangedDelegate`: MulticastDelegate, `VideoCallMenu`: Object, `StageButtonState`: Enum(ETribeVideoCallUserStageButtonState).

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeVideoCallUserInfo

`/Script/TribeXR.TribeVideoCallUserInfo` : `Object`, 112 bytes; vtable 88 entries, 2 overridden or new.

Data members: `Username`: Str, `PlatformId`: Str, `UserImageUrl`: Str, `CachedProfileImage`: Object.

| Function | Kind |
|---|---|
| `GetProfileImage(ref OnImageReady: Delegate(TribeImageDelegate__DelegateSignature), WorldContextObject: Object(Object))` | native, Blueprint-callable |
| `OnProfileImageDownloaded(ProfileImage: Object(Texture2DDynamic))` | native |
| `OnUserProfileImageDownloaded(UserId: Str, ProfileImage: Object(Texture2DDynamic))` | native |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TribeVideoSphere

`/Script/TribeXR.TribeVideoSphere` : `Actor`, 704 bytes; vtable 228 entries, 3 overridden or new.

Data members: `DomeMesh`: Object, `MediaPlayer`: Object, `MediaTexture`: Object, `BaseMaterial`: Object, `DynMat`: Object, `bLoop`: Bool.

| Function | Kind |
|---|---|
| `HandleMediaOpened(OpenedUrl: Str)` | native |
| `HandleMediaOpenFailed(FailedUrl: Str)` | native |
| `LoadVideoFromPath(AbsoluteFilePath: Str) -> Bool` | native, Blueprint-callable |
| `Pause()` | native, Blueprint-callable |
| `Play()` | native, Blueprint-callable |
| `Stop()` | native, Blueprint-callable |

C++ overrides: `Destructor`, `BeginPlay`, `EndPlay`.

### TribeVideoSphereAddon

`/Script/TribeXR.TribeVideoSphereAddon` : `TribeAddon`, 192 bytes; vtable 92 entries, 4 overridden or new.

C++ overrides: `Destructor`, `TribeAddon_NewVirtual89`, `TribeAddon_NewVirtual90`, `TribeAddon_NewVirtual91`.

### TribeVisualsManager

`/Script/TribeXR.TribeVisualsManager` : `Actor`, 992 bytes; vtable 228 entries, 4 overridden or new.

Data members: `OnGifPlayed`: MulticastDelegate, `BackdropImagesRenderTarget`: Object, `BackdropTextRenderTarget`: Object, `HeaderFont`: Object, `MaxGifsDownloading`: Int, `bSaveGifDownloads`: Bool, `VideoUrl`: Str, `BackdropStaticMeshActor`: Object, `BackdropMediaPlayer`: Object, `BackdropVideoMaterialInterface`: Object, `BackdropGifMaterialInterface`: Object, `NdiStreamMaterialInterface`: Object, `DefaultMaterialInterface`: Object, `OnMediaPlayerOpenSuccess`: MulticastDelegate, `MediaFolder`: Object, `GifFolder`: Object, `GifDownloadsFolder`: Object, `VideoFolder`: Object, `SphereVideoFolder`: Object, `DLCFolder`: Object, `NdiSourceFile`: Object, `InstalledVisualsPackAddons`: Array<Object>, `InstalledVideoSphereAddons`: Array<Object>, `BackdropGifs`: Array<Object>, `PendingGifs`: Array<Object>.

| Function | Kind |
|---|---|
| `AddPakVideoFromFile(Filename: Str, ParentFolder: Object(TribeFolder)) -> Object(TribePakFile)` | native, Blueprint-callable |
| `ClearBackdropImages()` | native, Blueprint-callable |
| `ComputeAverageColorFromTexture(Texture: Object(Texture))` | native, Blueprint-callable |
| `CreateVideoSphereFolder(SphereAddon: Object(TribeVideoSphereAddon)) -> Object(TribeFolder)` | native, Blueprint-callable |
| `CreateVisualsPackFolder(VisualsPackAddon: Object(TribeVisualsPackAddon)) -> Object(TribeFolder)` | native, Blueprint-callable |
| `DownloadGifFileToBackdrop(GifUrl: Str) -> Bool` | native, Blueprint-callable |
| `DrawGifFileToBackdrop(GifFile: Str, bDeleteFile: Bool)` | native, Blueprint-callable |
| `DrawGifFrameToBackdrop(Gif: Object(TribeGif))` | native |
| `DrawGifToBackdrop(Gif: Object(TribeGif))` | native, Blueprint-callable |
| `DrawModeChanged(DrawMode: Enum(ETribeGifDrawMode))` | event, Blueprint event |
| `DrawTextToBackdrop(Font: Object(Font), Text: Str, ScreenPosition: Struct(Vector2D), Scale: Float, ref Color: Struct(Color))` | native, Blueprint-callable |
| `DrawTextureToBackdrop(Texture: Object(Texture), ScreenPosition: Struct(Vector2D), ScreenSize: Struct(Vector2D), UVs: Struct(Vector2D), Rotation: Float)` | native, Blueprint-callable |
| `DrawTextureToBackdropRandom(Texture: Object(Texture), ScreenSize: Struct(Vector2D))` | native, Blueprint-callable |
| `GetAllowedVideoFileTypes() -> Array<Str>` | native, static, Blueprint-callable, pure |
| `GetGifAverageColor() -> Struct(LinearColor)` | native, Blueprint-callable, pure |
| `GetGifBeatmatchBeatsPerLoop() -> Float` | native, Blueprint-callable, pure |
| `GetGifBeatmatchBPM() -> Float` | native, Blueprint-callable, pure |
| `GetGifDrawMode() -> Enum(ETribeGifDrawMode)` | native, Blueprint-callable, pure |
| `GetGifTempDownloadsFolder() -> Str` | native, static, Blueprint-callable, pure |
| `GetGiphyIdFromUrl(GifUrl: Str) -> Str` | native, Blueprint-callable |
| `GetPlayMode() -> Enum(ETribeVMPlayMode)` | native, Blueprint-callable, pure |
| `GifPlaybackTick()` | event, Blueprint event |
| `HandleCreateGifFinished(Gif: Object(TribeGif))` | native |
| `HandleGifDownloadFinished(DownloadedFile: Str)` | native |
| `HandleGifResourcesLoadedChanged(Gif: Object(TribeGif))` | native |
| `InstallVideoSphereAddon(SphereAddon: Object(TribeVideoSphereAddon))` | native, Blueprint-callable |
| `InstallVisualsPackAddon(VisualsPackAddon: Object(TribeVisualsPackAddon))` | native, Blueprint-callable |
| `IsDrawableGifFile(Filename: Str) -> Bool` | native, Blueprint-callable, pure |
| `IsDrawingGifs() -> Bool` | native, Blueprint-callable, pure |
| `IsGifBeatmatchEnabled() -> Bool` | native, Blueprint-callable, pure |
| `IsSupportedVideoFileType(Filename: Str) -> Bool` | native, static, Blueprint-callable, pure |
| `LoadRigSkinData(SkinName: Str, out OutSkinData: Struct(TribeRigSkinData), out DeckSkinType: Str, out MixerSkinType: Str) -> Bool` | native, static, Blueprint-callable |
| `NdiPlaybackTick()` | event, Blueprint event |
| `OnComputeAverageColorFromTextureResult(Color: Struct(LinearColor))` | event, Blueprint event |
| `OnMediaPlayerOpened(OpenedUrl: Str)` | native |
| `OnMediaPlayerOpenFailed(OpenedUrl: Str)` | native |
| `PlayModeChanged(PrevPlayMode: Enum(ETribeVMPlayMode), NextPlayMode: Enum(ETribeVMPlayMode))` | event, Blueprint event |
| `PlayVideoOnSphereFromPath(FilePath: Str) -> Bool` | native, Blueprint-callable |
| `RefreshMediaFolders()` | native, Blueprint-callable |
| `RestartPlayback()` | native, Blueprint-callable |
| `SetBackdropHeader1(Text: Str)` | native, Blueprint-callable |
| `SetBackdropHeader2(Text: Str)` | native, Blueprint-callable |
| `SetBackdropStaticMesh(BackdropMesh: Object(StaticMeshActor))` | native, Blueprint-callable |
| `SetGifBeatmatchBeatsPerLoop(BeatsPerLoop: Float)` | native, Blueprint-callable |
| `SetGifBeatmatchBPM(BeatMatchBPM: Float, SecondsToNextBar: Float)` | native, Blueprint-callable |
| `SetGifBeatmatchEnabled(bEnabled: Bool)` | native, Blueprint-callable |
| `SetGifDrawMode(NewGifDrawMode: Enum(ETribeGifDrawMode))` | native, Blueprint-callable |
| `StopDrawingAll()` | native, Blueprint-callable |
| `StreamNdiToBackdrop() -> Bool` | native, Blueprint-callable |
| `StreamVideoToBackdrop(URL: Str) -> Bool` | native, Blueprint-callable |
| `UpdateBackdropVisibility()` | native, Blueprint-callable |
| `VideoPlaybackTick()` | event, Blueprint event |

C++ overrides: `Destructor`, `DeletingDestructor`, `EndPlay`, `Tick`.

### TribeVisualsPackAddon

`/Script/TribeXR.TribeVisualsPackAddon` : `TribeAddon`, 224 bytes; vtable 92 entries, 5 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`, `TribeAddon_NewVirtual89`, `TribeAddon_NewVirtual90`, `TribeAddon_NewVirtual91`.

### TwitchApiTypes

`/Script/TribeXR.TwitchApiTypes` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `GetTwitchEmoteUrlFromId(EmoteId: Int, Scale: Float) -> Str` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### TwitchChatClient

`/Script/TribeXR.TwitchChatClient` : `Object`, 160 bytes; vtable 88 entries, 2 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`.

### VRBodyReplicationComponent

`/Script/TribeXR.VRBodyReplicationComponent` : `ActorComponent`, 352 bytes; vtable 159 entries, 12 overridden or new.

Data members: `bAutoRegisterBodyComponents`: Bool, `bLerpToTransform`: Bool, `NetworkLocationConstInterpRate`: Float, `NetworkLocationLerpRate`: Float, `OwningPawn`: Object, `HeadComponent`: Object, `LeftHandComponent`: Object, `RightHandComponent`: Object, `ReplicatedVRBodyTransforms`: Struct(VRBodyReplicationComponentData).

| Function | Kind |
|---|---|
| `IsAuthoritative() -> Bool` | native, Blueprint-callable, pure |
| `OnRep_ReplicatedTransforms()` | native |
| `OverrideReplicatedTransform(Component: Object(SceneComponent), ref RelativeLocation: Struct(Vector), ref RelativeRotation: Struct(Rotator))` | native, Blueprint-callable |
| `RegisterVRBodyForReplication(Head: Object(SceneComponent), LeftHand: Object(SceneComponent), RightHand: Object(SceneComponent)) -> Bool` | native, Blueprint-callable |
| `Server_JumpToAuthorityTransforms()` | native, event, server RPC |
| `Server_UpdateReplicationData(ref UpdatedData: Struct(VRBodyReplicationComponentData))` | native, event, server RPC |

C++ overrides: `Destructor`, `DeletingDestructor`, `GetLifetimeReplicatedProps`, `ValidateGeneratedRepEnums`, `Activate`, `BeginPlay`, `TickComponent`, `SetComponentTickEnabled`, `NewVirtual155`, `NewVirtual156`, `NewVirtual157`, `NewVirtual158`.

## TribeIntonal

| Class | Parent | Data members | Functions | Overrides | Decompiled |
|---|---|---|---|---|---|
| [ASyncLoadAcidSequenceLibrary](#asyncloadacidsequencelibrary) | BlueprintAsyncActionBase | 2 | 1 | 3 | `TribeIntonal.ASyncLoadAcidSequenceLibrary.c` |
| [ASyncLoadDrumMachineSequenceLibrary](#asyncloaddrummachinesequencelibrary) | BlueprintAsyncActionBase | 2 | 1 | 3 | `TribeIntonal.ASyncLoadDrumMachineSequenceLibrary.c` |
| [ASyncOpenAcidSequence](#asyncopenacidsequence) | BlueprintAsyncActionBase | 3 | 1 | 3 | `TribeIntonal.ASyncOpenAcidSequence.c` |
| [ASyncOpenDrumMachineSequence](#asyncopendrummachinesequence) | BlueprintAsyncActionBase | 3 | 1 | 3 | `TribeIntonal.ASyncOpenDrumMachineSequence.c` |
| [AcidSequenceLibrary](#acidsequencelibrary) | Object | 1 | 7 | 2 | `TribeIntonal.AcidSequenceLibrary.c` |
| [AcidSynthChannelDevice](#acidsynthchanneldevice) | SuperPoweredChannelDevice | 6 | 11 | 13 | `TribeIntonal.AcidSynthChannelDevice.c` |
| [AcidSynthUniformFuncs](#acidsynthuniformfuncs) | Object | 0 | 18 | 2 | `TribeIntonal.AcidSynthUniformFuncs.c` |
| [DrumMachineBdSample](#drummachinebdsample) | DrumMachineSample | 0 | 0 | 2 | `TribeIntonal.DrumMachineBdSample.c` |
| [DrumMachineChannelDevice](#drummachinechanneldevice) | SuperPoweredChannelDevice | 12 | 24 | 8 | `TribeIntonal.DrumMachineChannelDevice.c` |
| [DrumMachineClickSample](#drummachineclicksample) | DrumMachineSample | 0 | 0 | 0 | - |
| [DrumMachineLowpassedSnareSample](#drummachinelowpassedsnaresample) | DrumMachineSample | 0 | 0 | 2 | `TribeIntonal.DrumMachineLowpassedSnareSample.c` |
| [DrumMachinePatch](#drummachinepatch) | Object | 3 | 0 | 2 | `TribeIntonal.DrumMachinePatch.c` |
| [DrumMachineSample](#drummachinesample) | Object | 0 | 0 | 5 | `TribeIntonal.DrumMachineSample.c` |
| [DrumMachineSamplesSubsystem](#drummachinesamplessubsystem) | GameInstanceSubsystem | 3 | 0 | 4 | `TribeIntonal.DrumMachineSamplesSubsystem.c` |
| [DrumMachineSequenceLibrary](#drummachinesequencelibrary) | Object | 1 | 7 | 2 | `TribeIntonal.DrumMachineSequenceLibrary.c` |
| [DrumMachineSingleBdSample](#drummachinesinglebdsample) | DrumMachineBdSample | 0 | 0 | 2 | `TribeIntonal.DrumMachineSingleBdSample.c` |
| [DrumMachineSnareSample](#drummachinesnaresample) | DrumMachineSample | 0 | 0 | 2 | `TribeIntonal.DrumMachineSnareSample.c` |
| [DrumMachineUniformFuncs](#drummachineuniformfuncs) | Object | 0 | 9 | 2 | `TribeIntonal.DrumMachineUniformFuncs.c` |
| [IntonalAcidEditorWidget](#intonalacideditorwidget) | UserWidget | 45 | 8 | 4 | `TribeIntonal.IntonalAcidEditorWidget.c` |
| [IntonalAcidPreset](#intonalacidpreset) | DataAsset | 2 | 0 | 2 | `TribeIntonal.IntonalAcidPreset.c` |
| [IntonalAcidSequence](#intonalacidsequence) | DataAsset | 2 | 0 | 2 | `TribeIntonal.IntonalAcidSequence.c` |
| [IntonalDrumMachineEditorWidget](#intonaldrummachineeditorwidget) | UserWidget | 39 | 8 | 4 | `TribeIntonal.IntonalDrumMachineEditorWidget.c` |
| [IntonalDrumMachinePreset](#intonaldrummachinepreset) | DataAsset | 2 | 0 | 2 | `TribeIntonal.IntonalDrumMachinePreset.c` |
| [IntonalDrumMachineSequence](#intonaldrummachinesequence) | DataAsset | 3 | 0 | 2 | `TribeIntonal.IntonalDrumMachineSequence.c` |
| [IntonalPianoRollWidget](#intonalpianorollwidget) | UserWidget | 9 | 2 | 3 | `TribeIntonal.IntonalPianoRollWidget.c` |
| [IntonalSequenceEditorPreview](#intonalsequenceeditorpreview) | Actor | 2 | 0 | 3 | `TribeIntonal.IntonalSequenceEditorPreview.c` |
| [IntonalSequencePainter](#intonalsequencepainter) | Object | 8 | 18 | 2 | `TribeIntonal.IntonalSequencePainter.c` |
| [IntonalSequenceSplineComponent](#intonalsequencesplinecomponent) | SceneComponent | 11 | 1 | 4 | `TribeIntonal.IntonalSequenceSplineComponent.c` |
| [IntonalWidgetComponent](#intonalwidgetcomponent) | WidgetComponent | 0 | 1 | 2 | `TribeIntonal.IntonalWidgetComponent.c` |
| [MomentumCalculatorFuncs](#momentumcalculatorfuncs) | Object | 0 | 3 | 2 | `TribeIntonal.MomentumCalculatorFuncs.c` |
| [SavedAcidSequenceInfo](#savedacidsequenceinfo) | Object | 1 | 0 | 2 | `TribeIntonal.SavedAcidSequenceInfo.c` |
| [SavedDrumMachineSequenceInfo](#saveddrummachinesequenceinfo) | Object | 1 | 0 | 2 | `TribeIntonal.SavedDrumMachineSequenceInfo.c` |

### ASyncLoadAcidSequenceLibrary

`/Script/TribeIntonal.ASyncLoadAcidSequenceLibrary` : `BlueprintAsyncActionBase`, 104 bytes; vtable 92 entries, 3 overridden or new.

Data members: `OnLoadLibrary`: MulticastDelegate, `World`: Object.

| Function | Kind |
|---|---|
| `ASyncLoadAcidSequenceLibrary(ObjectReference: Object(Object)) -> Object(ASyncLoadAcidSequenceLibrary)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `Activate`.

### ASyncLoadDrumMachineSequenceLibrary

`/Script/TribeIntonal.ASyncLoadDrumMachineSequenceLibrary` : `BlueprintAsyncActionBase`, 104 bytes; vtable 92 entries, 3 overridden or new.

Data members: `OnLoadLibrary`: MulticastDelegate, `World`: Object.

| Function | Kind |
|---|---|
| `ASyncLoadDrumMachineSequenceLibrary(ObjectReference: Object(Object)) -> Object(ASyncLoadDrumMachineSequenceLibrary)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `Activate`.

### ASyncOpenAcidSequence

`/Script/TribeIntonal.ASyncOpenAcidSequence` : `BlueprintAsyncActionBase`, 120 bytes; vtable 92 entries, 3 overridden or new.

Data members: `OnOpenedSequence`: MulticastDelegate, `World`: Object, `LoadedSequence`: Struct(SavedAcidSequence).

| Function | Kind |
|---|---|
| `ASyncOpenAcidSequence(ObjectReference: Object(Object), SequenceName: Str) -> Object(ASyncOpenAcidSequence)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `Activate`.

### ASyncOpenDrumMachineSequence

`/Script/TribeIntonal.ASyncOpenDrumMachineSequence` : `BlueprintAsyncActionBase`, 168 bytes; vtable 92 entries, 3 overridden or new.

Data members: `OnOpenedSequence`: MulticastDelegate, `World`: Object, `LoadedSequence`: Struct(SavedDrumMachineSequence).

| Function | Kind |
|---|---|
| `ASyncOpenDrumMachineSequence(ObjectReference: Object(Object), SequenceName: Str) -> Object(ASyncOpenDrumMachineSequence)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `Activate`.

### AcidSequenceLibrary

`/Script/TribeIntonal.AcidSequenceLibrary` : `Object`, 56 bytes; vtable 88 entries, 2 overridden or new.

Data members: `SavedAcidSequences`: Array<Object>.

| Function | Kind |
|---|---|
| `DeleteAcidSequence(SequenceName: Str) -> Bool` | native, static, Blueprint-callable |
| `GetNewSequenceName() -> Str` | native, static, Blueprint-callable |
| `LoadAcidSequenceLibrary() -> Object(AcidSequenceLibrary)` | native, static, Blueprint-callable |
| `LoadSavedAcidSequence(SequenceName: Str, out OutSavedAcidSequence: Struct(SavedAcidSequence)) -> Bool` | native, static, Blueprint-callable |
| `ReloadSavedAcidSequences()` | native, Blueprint-callable |
| `RenameAcidSequence(FromSequenceName: Str, ToSequenceName: Str) -> Bool` | native, static, Blueprint-callable |
| `SaveAcidSequence(SequenceName: Str, AcidSequence: Array<Struct(IntonalAcidEvent)>) -> Bool` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### AcidSynthChannelDevice

`/Script/TribeIntonal.AcidSynthChannelDevice` : `SuperPoweredChannelDevice`, 224 bytes; vtable 106 entries, 13 overridden or new.

Data members: `m_sequence`: Object, `m_isSynced`: Bool, `m_bpm`: Float, `m_uniforms`: Struct(AcidSynthUniforms), `m_curSequenceEventIdx`: Int, `m_isPlaying`: Bool.

| Function | Kind |
|---|---|
| `CreateAcidSynth() -> Object(AcidSynthChannelDevice)` | native, static, Blueprint-callable |
| `GetCurrentKeyIndex() -> Int` | native, Blueprint-callable, pure |
| `IsKeySyncEnabled() -> Bool` | native, Blueprint-callable, pure |
| `ModifyUniforms() -> Struct(AcidSynthUniformUpdater)` | native, Blueprint-callable |
| `SavePreset()` | native, Blueprint-callable |
| `SaveSequence()` | native, Blueprint-callable |
| `SetAcidSequence(NewSequence: Object(IntonalAcidSequence))` | native, Blueprint-callable |
| `SetAcidSequenceEvents(ref Events: Array<Struct(IntonalAcidEvent)>)` | native, Blueprint-callable |
| `SetKeySyncEnabled(bEnabled: Bool)` | native, Blueprint-callable |
| `SetPreset(NewPreset: Object(IntonalAcidPreset))` | native, Blueprint-callable |
| `TogglePlayStop()` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `IsReadyForFinishDestroy`, `FinishDestroy`, `SuperPoweredChannelDevice_NewVirtual91`, `SuperPoweredChannelDevice_NewVirtual92`, `SuperPoweredChannelDevice_NewVirtual94`, `SuperPoweredChannelDevice_NewVirtual95`, `SuperPoweredChannelDevice_NewVirtual96`, `SuperPoweredChannelDevice_NewVirtual99`, `SuperPoweredChannelDevice_NewVirtual101`, `SuperPoweredChannelDevice_NewVirtual103`, `SuperPoweredChannelDevice_NewVirtual104`.

### AcidSynthUniformFuncs

`/Script/TribeIntonal.AcidSynthUniformFuncs` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `Apply(updater: Struct(AcidSynthUniformUpdater)) -> Bool` | native, static, Blueprint-callable |
| `SetBeatWidth(updater: Struct(AcidSynthUniformUpdater), beatWidth: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetChorusMix(updater: Struct(AcidSynthUniformUpdater), chorusMix: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetChorusRate(updater: Struct(AcidSynthUniformUpdater), chorusRate: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetDistortionAmount(updater: Struct(AcidSynthUniformUpdater), distortionAmount: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetDistortionTone(updater: Struct(AcidSynthUniformUpdater), distortionTone: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetEchoFeedback(updater: Struct(AcidSynthUniformUpdater), echoFeedback: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetEchoMix(updater: Struct(AcidSynthUniformUpdater), echoMix: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetEchoTime(updater: Struct(AcidSynthUniformUpdater), echoTime: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetKnobAccent(updater: Struct(AcidSynthUniformUpdater), knobAccent: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetKnobCutOffFreq(updater: Struct(AcidSynthUniformUpdater), knobCutOffFreq: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetKnobDecay(updater: Struct(AcidSynthUniformUpdater), knobDecay: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetKnobEnvMod(updater: Struct(AcidSynthUniformUpdater), knobEnvMod: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetKnobResonance(updater: Struct(AcidSynthUniformUpdater), knobResonance: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetLowpassAttack(updater: Struct(AcidSynthUniformUpdater), lowpassAttack: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetMasterGain(updater: Struct(AcidSynthUniformUpdater), masterGain: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetMidiNoteOffset(updater: Struct(AcidSynthUniformUpdater), midiNoteOffset: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |
| `SetSwitchWaveformSelect(updater: Struct(AcidSynthUniformUpdater), switchWaveformSelect: Float) -> Struct(AcidSynthUniformUpdater)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### DrumMachineBdSample

`/Script/TribeIntonal.DrumMachineBdSample` : `DrumMachineSample`, 72 bytes; vtable 91 entries, 2 overridden or new.

C++ overrides: `DrumMachineSample_NewVirtual89`, `DrumMachineSample_NewVirtual90`.

### DrumMachineChannelDevice

`/Script/TribeIntonal.DrumMachineChannelDevice` : `SuperPoweredChannelDevice`, 432 bytes; vtable 106 entries, 8 overridden or new.

Data members: `m_sequence`: Object, `m_isSynced`: Bool, `m_bpm`: Float, `m_uniforms`: Struct(DrumMachineUniforms), `m_DrumMachinePatchId`: Enum(EIntonalDrumPatch), `SequenceDataChanged`: MulticastDelegate, `IntonalDrumMachineNoteRecorded`: MulticastDelegate, `m_isPlaying`: Bool, `m_isRecording`: Bool, `m_quantizeLevel`: Int, `m_recordQuantizeLevel`: Int, `m_drumMachineSystem`: Object.

| Function | Kind |
|---|---|
| `CreateDrumMachine(InWorldRef: Object(Object)) -> Object(DrumMachineChannelDevice)` | native, static, Blueprint-callable |
| `GetCurBeat() -> Int` | native, Blueprint-callable, pure |
| `GetCurBeatPosition() -> Float` | native, Blueprint-callable, pure |
| `GetCurSequencePosition() -> Float` | native, Blueprint-callable, pure |
| `GetRecordQuantizeLevel() -> Int` | native, Blueprint-callable, pure |
| `IntonalDrumMachineNoteRecorded__DelegateSignature(ref Event: Struct(IntonalDrumMachineEvent))` | delegate |
| `IsClicktrackEnabled() -> Bool` | native, Blueprint-callable, pure |
| `ModifyUniforms() -> Struct(DrumMachineUniformUpdater)` | native, Blueprint-callable |
| `SavePreset()` | native, Blueprint-callable |
| `SaveSequence()` | native, Blueprint-callable |
| `SecondsSinceLastTrigger(DrumType: Enum(EIntonalDrumType)) -> Float` | native, Blueprint-callable, pure |
| `SequenceDataChangedEvent__DelegateSignature(NewSequenceData: Struct(IntonalDrumMachineSequenceData))` | delegate |
| `SetDrumMachineSequence(NewSequence: Object(IntonalDrumMachineSequence))` | native, Blueprint-callable |
| `SetDrumMachineSequenceData(ref Data: Struct(IntonalDrumMachineSequenceData))` | native, Blueprint-callable |
| `SetPreset(NewPreset: Object(IntonalDrumMachinePreset))` | native, Blueprint-callable |
| `SetQuantizeLevel(NewQuantizeLevel: Int)` | native, Blueprint-callable |
| `SetRecordQuantizeLevel(NewQuantizeLevel: Int)` | native, Blueprint-callable |
| `SetUniforms(NewUniforms: Struct(DrumMachineUniforms))` | native, Blueprint-callable |
| `ShouldShowIndex() -> Bool` | native, Blueprint-callable, pure |
| `TogglePlayClicktrack()` | native, Blueprint-callable |
| `TogglePlayStop()` | native, Blueprint-callable |
| `ToggleQuantizeLevel()` | native, Blueprint-callable |
| `ToggleRecord()` | native, Blueprint-callable |
| `TriggerDrum(DrumType: Enum(EIntonalDrumType))` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `FinishDestroy`, `SuperPoweredChannelDevice_NewVirtual91`, `SuperPoweredChannelDevice_NewVirtual92`, `SuperPoweredChannelDevice_NewVirtual101`, `SuperPoweredChannelDevice_NewVirtual103`, `SuperPoweredChannelDevice_NewVirtual104`.

### DrumMachineClickSample

`/Script/TribeIntonal.DrumMachineClickSample` : `DrumMachineSample`, 72 bytes; vtable 91 entries, 0 overridden or new.

### DrumMachineLowpassedSnareSample

`/Script/TribeIntonal.DrumMachineLowpassedSnareSample` : `DrumMachineSample`, 72 bytes; vtable 91 entries, 2 overridden or new.

C++ overrides: `DrumMachineSample_NewVirtual89`, `DrumMachineSample_NewVirtual90`.

### DrumMachinePatch

`/Script/TribeIntonal.DrumMachinePatch` : `Object`, 152 bytes; vtable 88 entries, 2 overridden or new.

Data members: `BdSamples`: Array<Int>, `Samples`: Map<Enum(EIntonalDrumType),Int>, `AllSamples`: Array<Object>.

C++ overrides: `Destructor`, `DeletingDestructor`.

### DrumMachineSample

`/Script/TribeIntonal.DrumMachineSample` : `Object`, 72 bytes; vtable 91 entries, 5 overridden or new.

C++ overrides: `DeletingDestructor`, `BeginDestroy`, `NewVirtual88`, `NewVirtual89`, `NewVirtual90`.

### DrumMachineSamplesSubsystem

`/Script/TribeIntonal.DrumMachineSamplesSubsystem` : `GameInstanceSubsystem`, 96 bytes; vtable 91 entries, 4 overridden or new.

Data members: `DrumMachinePatch808`: Object, `DrumMachinePatch909`: Object, `DrumMachinePatchTechno`: Object.

C++ overrides: `Destructor`, `DeletingDestructor`, `Initialize`, `Deinitialize`.

### DrumMachineSequenceLibrary

`/Script/TribeIntonal.DrumMachineSequenceLibrary` : `Object`, 56 bytes; vtable 88 entries, 2 overridden or new.

Data members: `SavedDrumMachineSequences`: Array<Object>.

| Function | Kind |
|---|---|
| `DeleteDrumMachineSequence(SequenceName: Str) -> Bool` | native, static, Blueprint-callable |
| `GetNewDrumSequenceName() -> Str` | native, static, Blueprint-callable |
| `LoadDrumMachineSequenceLibrary() -> Object(DrumMachineSequenceLibrary)` | native, static, Blueprint-callable |
| `LoadSavedDrumMachineSequence(SequenceName: Str, out OutSavedDrumMachineSequence: Struct(SavedDrumMachineSequence)) -> Bool` | native, static, Blueprint-callable |
| `ReloadSavedDrumMachineSequences()` | native, Blueprint-callable |
| `RenameDrumMachineSequence(FromSequenceName: Str, ToSequenceName: Str) -> Bool` | native, static, Blueprint-callable |
| `SaveDrumMachineSequence(SequenceName: Str, ref SequenceData: Struct(IntonalDrumMachineSequenceData), ref Uniforms: Struct(DrumMachineUniforms)) -> Bool` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### DrumMachineSingleBdSample

`/Script/TribeIntonal.DrumMachineSingleBdSample` : `DrumMachineBdSample`, 72 bytes; vtable 91 entries, 2 overridden or new.

C++ overrides: `DrumMachineSample_NewVirtual89`, `DrumMachineSample_NewVirtual90`.

### DrumMachineSnareSample

`/Script/TribeIntonal.DrumMachineSnareSample` : `DrumMachineSample`, 72 bytes; vtable 91 entries, 2 overridden or new.

C++ overrides: `DrumMachineSample_NewVirtual88`, `DrumMachineSample_NewVirtual89`.

### DrumMachineUniformFuncs

`/Script/TribeIntonal.DrumMachineUniformFuncs` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `SetBdDecay(updater: Struct(DrumMachineUniformUpdater), bdDecay: Float) -> Struct(DrumMachineUniformUpdater)` | native, static, Blueprint-callable |
| `SetBdDistortion(updater: Struct(DrumMachineUniformUpdater), bdDistortion: Float) -> Struct(DrumMachineUniformUpdater)` | native, static, Blueprint-callable |
| `SetBdGain(updater: Struct(DrumMachineUniformUpdater), bdGain: Float) -> Struct(DrumMachineUniformUpdater)` | native, static, Blueprint-callable |
| `SetBdPitch(updater: Struct(DrumMachineUniformUpdater), bdPitch: Float) -> Struct(DrumMachineUniformUpdater)` | native, static, Blueprint-callable |
| `SetMasterGain(updater: Struct(DrumMachineUniformUpdater), masterGain: Float) -> Struct(DrumMachineUniformUpdater)` | native, static, Blueprint-callable |
| `SetSdGain(updater: Struct(DrumMachineUniformUpdater), sdGain: Float) -> Struct(DrumMachineUniformUpdater)` | native, static, Blueprint-callable |
| `SetSdSnappiness(updater: Struct(DrumMachineUniformUpdater), sdSnappiness: Float) -> Struct(DrumMachineUniformUpdater)` | native, static, Blueprint-callable |
| `SetSdTone(updater: Struct(DrumMachineUniformUpdater), sdTone: Float) -> Struct(DrumMachineUniformUpdater)` | native, static, Blueprint-callable |
| `SetSwing(updater: Struct(DrumMachineUniformUpdater), Swing: Float) -> Struct(DrumMachineUniformUpdater)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### IntonalAcidEditorWidget

`/Script/TribeIntonal.IntonalAcidEditorWidget` : `UserWidget`, 2512 bytes; vtable 161 entries, 4 overridden or new.

Data members: `BackgroundColor`: Struct(SlateColor), `OddIdxBackgroundColor`: Struct(SlateColor), `PlayingIdxBackgroundColor`: Struct(SlateColor), `BackgroundDrawBrush`: Struct(SlateBrush), `GridEmptyDrawBrush`: Struct(SlateBrush), `GridNoteDrawBrush`: Struct(SlateBrush), `GridNoteAccentDrawBrush`: Struct(SlateBrush), `GridNoteHighlightedDrawBrush`: Struct(SlateBrush), `PianoNoteDrawBrush`: Struct(SlateBrush), `SequenceLen`: Int, `GridHorizontalPaddingPercent`: Float, `GridVerticalPadding`: Float, `GridSizeRatio`: Struct(Vector2D), `GridEmptyWhiteColor`: Struct(SlateColor), `GridEmptyBlackColor`: Struct(SlateColor), `GridEmptySizePercent`: Struct(Vector2D), `ConnectingSplineThickness`: Float, `SplitCurveAmount`: Float, `GridEmptyItemMinSize`: Struct(Vector2D), `GridNoteWhiteColor`: Struct(SlateColor), `GridNoteBlackColor`: Struct(SlateColor), `GridNoteSizePercent`: Struct(Vector2D), `GridNoteAccentWhiteColor`: Struct(SlateColor), `GridNoteAccentBlackColor`: Struct(SlateColor), `GridNoteAccentSizePercent`: Struct(Vector2D), `GridNoteHighlightedWhiteColor`: Struct(SlateColor), `GridNoteHighlightedBlackColor`: Struct(SlateColor), `GridNoteHighlightedSizePercent`: Struct(Vector2D), `PianoNoteWidth`: Float, `PianoNoteToGridPadding`: Float, `PianoNoteVerticalPadding`: Float, `PianoNoteWhiteBackgroundColor`: Struct(SlateColor), `PianoNoteWhiteFontColor`: Struct(SlateColor), `PianoNoteBlackBackgroundColor`: Struct(SlateColor), `PianoNoteBlackFontColor`: Struct(SlateColor), `PianoNoteFont`: Struct(SlateFontInfo), `PianoNoteRotation`: Float, `OctaveSeperatorHeight`: Float, `OctaveSeperatorColor`: Struct(SlateColor), `Events`: Array<Struct(IntonalAcidEvent)>, `IsHighlighting`: Bool, `HighlightedNote`: Enum(EIntonalNote), `HighlightedIndex`: Int, `PlayingNoteScale`: Float, `PlayingNoteTime`: Float.

| Function | Kind |
|---|---|
| `ClearHighlighted()` | native, Blueprint-callable |
| `DesiredHeight() -> Float` | native, Blueprint-callable, pure |
| `DesiredHeightForWidth(InWidth: Float) -> Float` | native, Blueprint-callable, pure |
| `IndexForXPos(XPos: Float) -> Int` | native, Blueprint-callable, pure |
| `NoteForYPos(YPos: Float) -> Enum(EIntonalNote)` | native, Blueprint-callable, pure |
| `SequenceIndexPlayed(Index: Int)` | native, Blueprint-callable |
| `SetHighlighted(InHighlightedNote: Enum(EIntonalNote), InHighlightedIndex: Int)` | native, Blueprint-callable |
| `UpdateVisibleEvents(ref InEvents: Array<Struct(IntonalAcidEvent)>)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `ReleaseSlateResources`, `RebuildWidget`.

### IntonalAcidPreset

`/Script/TribeIntonal.IntonalAcidPreset` : `DataAsset`, 136 bytes; vtable 88 entries, 2 overridden or new.

Data members: `PresetName`: Str, `Uniforms`: Struct(AcidSynthUniforms).

C++ overrides: `Destructor`, `DeletingDestructor`.

### IntonalAcidSequence

`/Script/TribeIntonal.IntonalAcidSequence` : `DataAsset`, 80 bytes; vtable 88 entries, 2 overridden or new.

Data members: `SequenceName`: Str, `Events`: Array<Struct(IntonalAcidEvent)>.

C++ overrides: `Destructor`, `DeletingDestructor`.

### IntonalDrumMachineEditorWidget

`/Script/TribeIntonal.IntonalDrumMachineEditorWidget` : `UserWidget`, 2432 bytes; vtable 161 entries, 4 overridden or new.

Data members: `BackgroundColor`: Struct(SlateColor), `OddIdxBackgroundColor`: Struct(SlateColor), `PlayingIdxBackgroundColor`: Struct(SlateColor), `BackgroundDrawBrush`: Struct(SlateBrush), `GridEmptyDrawBrush`: Struct(SlateBrush), `GridNoteDrawBrush`: Struct(SlateBrush), `GridNoteAccentDrawBrush`: Struct(SlateBrush), `GridNoteHighlightedDrawBrush`: Struct(SlateBrush), `PianoNoteDrawBrush`: Struct(SlateBrush), `SequenceLen`: Int, `GridHorizontalPaddingPercent`: Float, `GridVerticalPadding`: Float, `GridSizeRatio`: Struct(Vector2D), `GridEmptyColor`: Struct(SlateColor), `GridEmptySizePercent`: Struct(Vector2D), `ConnectingSplineThickness`: Float, `SplitCurveAmount`: Float, `GridEmptyItemMinSize`: Struct(Vector2D), `GridNoteColor`: Struct(SlateColor), `GridNoteSizePercent`: Struct(Vector2D), `GridNoteAccentColor`: Struct(SlateColor), `GridNoteAccentSizePercent`: Struct(Vector2D), `GridNoteHighlightedColor`: Struct(SlateColor), `GridNoteHighlightedSizePercent`: Struct(Vector2D), `PianoNoteWidth`: Float, `PianoNoteToGridPadding`: Float, `PianoNoteVerticalPadding`: Float, `PianoNoteEvenBackgroundColor`: Struct(SlateColor), `PianoNoteEvenFontColor`: Struct(SlateColor), `PianoNoteOddBackgroundColor`: Struct(SlateColor), `PianoNoteOddFontColor`: Struct(SlateColor), `PianoNoteFont`: Struct(SlateFontInfo), `PianoNoteRotation`: Float, `SequenceData`: Struct(IntonalDrumMachineSequenceData), `IsHighlighting`: Bool, `HighlightedNote`: Enum(EIntonalDrumType), `HighlightedIndex`: Int, `PlayingNoteScale`: Float, `PlayingNoteTime`: Float.

| Function | Kind |
|---|---|
| `ClearHighlighted()` | native, Blueprint-callable |
| `DesiredHeight() -> Float` | native, Blueprint-callable, pure |
| `DesiredHeightForWidth(InWidth: Float) -> Float` | native, Blueprint-callable, pure |
| `IndexForXPos(XPos: Float) -> Int` | native, Blueprint-callable, pure |
| `NoteForYPos(YPos: Float) -> Enum(EIntonalDrumType)` | native, Blueprint-callable, pure |
| `SequenceIndexPlayed(Index: Int)` | native, Blueprint-callable |
| `SetHighlighted(InHighlightedNote: Enum(EIntonalDrumType), InHighlightedIndex: Int)` | native, Blueprint-callable |
| `UpdateVisibleEvents(ref InSequenceData: Struct(IntonalDrumMachineSequenceData))` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `ReleaseSlateResources`, `RebuildWidget`.

### IntonalDrumMachinePreset

`/Script/TribeIntonal.IntonalDrumMachinePreset` : `DataAsset`, 104 bytes; vtable 88 entries, 2 overridden or new.

Data members: `PresetName`: Str, `Uniforms`: Struct(DrumMachineUniforms).

C++ overrides: `Destructor`, `DeletingDestructor`.

### IntonalDrumMachineSequence

`/Script/TribeIntonal.IntonalDrumMachineSequence` : `DataAsset`, 128 bytes; vtable 88 entries, 2 overridden or new.

Data members: `SequenceName`: Str, `SequenceData`: Struct(IntonalDrumMachineSequenceData), `Uniforms`: Struct(DrumMachineUniforms).

C++ overrides: `Destructor`, `DeletingDestructor`.

### IntonalPianoRollWidget

`/Script/TribeIntonal.IntonalPianoRollWidget` : `UserWidget`, 824 bytes; vtable 161 entries, 3 overridden or new.

Data members: `WhitePianoNoteClass`: Object, `BlackPianoNoteClass`: Object, `NoteWidth`: Float, `NoteHeight`: Float, `SequenceLength`: Int, `CanvasPanel`: Object, `Size`: Struct(Vector2D), `WhiteNoteViews`: Array<Object>, `BlackNoteViews`: Array<Object>.

| Function | Kind |
|---|---|
| `BuildInterface()` | native, Blueprint-callable |
| `IntToNote(InNote: Int) -> Enum(EIntonalNote)` | native, static, Blueprint-callable, pure |

C++ overrides: `Destructor`, `DeletingDestructor`, `NativePreConstruct`.

### IntonalSequenceEditorPreview

`/Script/TribeIntonal.IntonalSequenceEditorPreview` : `Actor`, 672 bytes; vtable 228 entries, 3 overridden or new.

Data members: `SequenceSplineComponent`: Object, `AcidSequence`: Object.

C++ overrides: `Destructor`, `BeginPlay`, `OnConstruction`.

### IntonalSequencePainter

`/Script/TribeIntonal.IntonalSequencePainter` : `Object`, 200 bytes; vtable 88 entries, 2 overridden or new.

Data members: `IsEditing`: Bool, `IsHovering`: Bool, `IsButtonHovering`: Bool, `IsButtonEditing`: Bool, `CanUndo`: Bool, `CanRedo`: Bool, `PaintMode`: Bool, `DisplayedSequencesChanged`: MulticastDelegate.

| Function | Kind |
|---|---|
| `ClearUndo()` | native, Blueprint-callable |
| `CurSelectedNote(out OutNote: Enum(EIntonalNote), out OutIndex: Int)` | native, Blueprint-callable |
| `DisplayedSequencesChangedEvent__DelegateSignature(ref MainEvents: Array<Struct(IntonalAcidEvent)>, ref GhostEvents: Array<Struct(IntonalAcidEvent)>)` | delegate |
| `EndButtonGrab()` | native, Blueprint-callable |
| `EndButtonHover()` | native, Blueprint-callable |
| `GrabBegin()` | native, Blueprint-callable |
| `GrabEnd()` | native, Blueprint-callable |
| `HoverBegin(Note: Enum(EIntonalNote), Index: Int)` | native, Blueprint-callable |
| `HoverEnd()` | native, Blueprint-callable |
| `HoverMoved(Note: Enum(EIntonalNote), Index: Int)` | native, Blueprint-callable |
| `MoveButtonHover(Index: Int, ButtonIndex: Int)` | native, Blueprint-callable |
| `Redo()` | native, Blueprint-callable |
| `SetSequenceEvents(InEvents: Array<Struct(IntonalAcidEvent)>)` | native, Blueprint-callable |
| `ShiftSequence(Direction: Int)` | native, Blueprint-callable |
| `StartButtonGrab()` | native, Blueprint-callable |
| `StartButtonHover(Index: Int, ButtonIndex: Int)` | native, Blueprint-callable |
| `TransposeSequence(Direction: Int)` | native, Blueprint-callable |
| `Undo()` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### IntonalSequenceSplineComponent

`/Script/TribeIntonal.IntonalSequenceSplineComponent` : `SceneComponent`, 672 bytes; vtable 196 entries, 4 overridden or new.

Data members: `NoteLength`: Float, `TransitionLength`: Float, `NoteHeight`: Float, `RibbonHeight`: Float, `SlideInAmount`: Float, `SplineAmount`: Float, `Oversampling`: Float, `SegmentNiagaraSystem`: Object, `SplineMaterial`: Object, `FlashMaterial`: Object, `Segment`: Struct(NiagaraSplineSegment).

| Function | Kind |
|---|---|
| `SetSequenceEvents(ref Events: Array<Struct(IntonalAcidEvent)>)` | native, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginPlay`, `TickComponent`.

### IntonalWidgetComponent

`/Script/TribeIntonal.IntonalWidgetComponent` : `WidgetComponent`, 1664 bytes; vtable 362 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `GetHitWidgetPathStatic(Component: Object(WidgetComponent), WorldHitLocation: Struct(Vector), bIgnoreEnabledStatus: Bool, CursorRadius: Float) -> Struct(Vector2D)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### MomentumCalculatorFuncs

`/Script/TribeIntonal.MomentumCalculatorFuncs` : `Object`, 40 bytes; vtable 88 entries, 2 overridden or new.

| Function | Kind |
|---|---|
| `CurrentMomentum(ref Calc: Struct(MomentumCalculator)) -> Struct(Vector)` | native, static, Blueprint-callable |
| `MomentumInDirection(ref Calc: Struct(MomentumCalculator), ref Direction: Struct(Vector)) -> Float` | native, static, Blueprint-callable |
| `PushPosition(ref Calc: Struct(MomentumCalculator), ref Position: Struct(Vector), DeltaTime: Float)` | native, static, Blueprint-callable |

C++ overrides: `Destructor`, `DeletingDestructor`.

### SavedAcidSequenceInfo

`/Script/TribeIntonal.SavedAcidSequenceInfo` : `Object`, 56 bytes; vtable 88 entries, 2 overridden or new.

Data members: `SequenceName`: Str.

C++ overrides: `Destructor`, `DeletingDestructor`.

### SavedDrumMachineSequenceInfo

`/Script/TribeIntonal.SavedDrumMachineSequenceInfo` : `Object`, 56 bytes; vtable 88 entries, 2 overridden or new.

Data members: `SequenceName`: Str.

C++ overrides: `Destructor`, `DeletingDestructor`.

## TribeMIDI

| Class | Parent | Data members | Functions | Overrides | Decompiled |
|---|---|---|---|---|---|
| [TribeMIDISubsystem](#tribemidisubsystem) | GameInstanceSubsystem | 0 | 0 | 4 | `TribeMIDI.TribeMIDISubsystem.c` |

### TribeMIDISubsystem

`/Script/TribeMIDI.TribeMIDISubsystem` : `GameInstanceSubsystem`, 128 bytes; vtable 91 entries, 4 overridden or new.

C++ overrides: `Destructor`, `DeletingDestructor`, `Initialize`, `Deinitialize`.

## Beatport

| Class | Parent | Data members | Functions | Overrides | Decompiled |
|---|---|---|---|---|---|
| [BeatportClient](#beatportclient) | Object | 1 | 20 | 3 | `Beatport.BeatportClient.c` |
| [BeatportTrackHandle](#beatporttrackhandle) | Object | 7 | 2 | 2 | `Beatport.BeatportTrackHandle.c` |

### BeatportClient

`/Script/Beatport.BeatportClient` : `Object`, 384 bytes; vtable 88 entries, 3 overridden or new.

Data members: `ActiveTrackHandles`: Array<Object>.

Native functions (20): `CloseTrack`, `CloseTrackFromHandle`, `FindTrackHandle`, `IsLoggedIn`, `IsUsingFLAC`, `Login`, `LoginFromClipboard`, `Logout`, `OpenTrack`, `Query`, `QueryAccountInfo`, `QueryAudioQualities`, `QueryCuratedPlaylists`, `QueryCuratedPlaylistTracks`, `QueryTrackMetadata`, `QueryUserPlaylists`, `QueryUserPlaylistTracks`, `ReportTrackPosition`, `SearchBeatport`, `SetAudioQuality`.

C++ overrides: `Destructor`, `DeletingDestructor`, `FinishDestroy`.

### BeatportTrackHandle

`/Script/Beatport.BeatportTrackHandle` : `Object`, 112 bytes; vtable 88 entries, 2 overridden or new.

Data members: `TrackId`: Int64, `TrackState`: Enum(EBeatportTrackState), `BytesDownloaded`: Int, `BytesRead`: Int, `TotalBytes`: Int, `StatusMessage`: Str, `OwningClient`: Object.

Native functions (2): `GetDownloadProgress`, `IsDownloadComplete`.

C++ overrides: `Destructor`, `DeletingDestructor`.

## VulkanVideoMeshComponent

| Class | Parent | Data members | Functions | Overrides | Decompiled |
|---|---|---|---|---|---|
| [DirectVideoMeshRendererComponent](#directvideomeshrenderercomponent) | ActorComponent | 6 | 0 | 9 | `VulkanVideoMeshComponent.DirectVideoMeshRendererComponent.c` |

### DirectVideoMeshRendererComponent

`/Script/VulkanVideoMeshComponent.DirectVideoMeshRendererComponent` : `ActorComponent`, 328 bytes; vtable 158 entries, 9 overridden or new.

Data members: `StereoMode`: Enum(EStereoMode), `LinkedPlayer`: Object, `HideMeshWhileWeHaveVideo`: Bool, `HasMesh`: Bool, `PositionsAsFloats`: Array<Float>, `Indices`: Array<UInt32>.

C++ overrides: `Destructor`, `DeletingDestructor`, `BeginDestroy`, `Serialize`, `Serialize`, `TickComponent`, `NewVirtual155`, `NewVirtual156`, `NewVirtual157`.

## AndroidVulkanVideo

| Class | Parent | Data members | Functions | Overrides | Decompiled |
|---|---|---|---|---|---|
| [SoundWaveProceduralWithTiming](#soundwaveproceduralwithtiming) | SoundWaveProcedural | 0 | 0 | 4 | `AndroidVulkanVideo.SoundWaveProceduralWithTiming.c` |

### SoundWaveProceduralWithTiming

`/Script/AndroidVulkanVideo.SoundWaveProceduralWithTiming` : `SoundWaveProcedural`, 1152 bytes; vtable 141 entries, 4 overridden or new.

C++ overrides: `Destructor`, `GeneratePCMData`, `NewVirtual139`, `NewVirtual140`.
