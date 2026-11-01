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
