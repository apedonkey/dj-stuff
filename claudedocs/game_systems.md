# Tribe XR, decompiled: coverage and the game systems

Tribe XR build 2304 (OBB `main.2304`, Unreal 5.4.4). Since 2026-10-27 evening every package in Tribe's four paks is
decoded, apart from Epic's engine content. This file covers:
- what is decoded and where it is;
- how the non-gear systems work: lessons, beat highway and dance game, the visuals wall, the crowd, the stock
  stages, the video stage, Twitch and the small integrations;
- the data files that ship beside the assets.

Statements about behaviour are marked **(read)** where code shows them, with the file and function, and
**(inferred)** where they rest on names or context.

How to read the citations:
- **Blueprint paths** are relative to `D:/TribeUE/tribe_assets/catalog/code/`; **C files** to
  `D:/TribeUE/tribe_native/classes/` (Ghidra pseudo-C: fields are raw offsets, engine helpers are `FUN_` addresses).
- **"str 0x…"** is a constant in `libUnreal.so` at that Ghidra address (file offset = address − 0x100000).
- **Enums** come from `pulled/TribeXR_full3.usmap`; class defaults from the dumps in `D:/TribeUE/tribe_assets/dump/`.
- **Positions** are in cm.

## Where everything is

| Part | Write-up | Bulk output (on D:, not in the repo) |
|---|---|---|
| Decks, mixers, controllers: every control, its position and what it calls | `deck_catalog.md`, `deck_reference.md` | `D:/TribeUE/tribe_assets/catalog/code/Equipment/` |
| Gear models and textures | `gear_models.md` | `D:/TribeUE/tribe_models/` |
| Menus: every button and what it does | `menu_catalog.md`, `cue_tracks_menus.md` | `.../catalog/code/Menus/`, `TrackManager/`, `MusicServices/` |
| Cue headphones, track loading, the mixer's signal path | `cue_tracks_menus.md` | |
| Mixer effects, including Tribe's own effect DSP | `mixer_effects.md` | `D:/TribeUE/tribe_native/fx/` |
| Superpowered's DSP (player, key lock, SDK effects) | `superpowered_dsp.md` | `D:/TribeUE/tribe_native/fx/` |
| Tribe's C++ (179 classes) | `native_reference.md` (summary: `native_summary.md`) | `D:/TribeUE/tribe_native/classes/` |
| Lessons, beat highway, DJ challenge, dance game | this file | `.../catalog/code/Lessons/`, `Dance/`, `.../catalog/data/Replays/` |
| Visuals wall, crowd, stock stages, video stage, Twitch, achievements, OSC/MIDI/Discord/NDI | this file | `.../catalog/code/Visuals/`, `Maps/`, `Environment/`, `VideoCall/`, `Twitch/`, ... |

`.../catalog` is `D:/TribeUE/tribe_assets/catalog`. The unpacked game itself is `D:/TribeUE/tribe_assets/all/TribeXR`.

## What is decoded

**The paks:** the OBB holds four.
- `pakchunk0` (688 MB) is the game.
- `pakchunk1` (404 MB) holds the five stock stages that aren't in chunk 0: Desert, Hip Hop, Hotel Selina, Lodato
  Lounge and Polygon City.
- `pakchunk0optional` and `pakchunk1optional` hold optional texture and mesh data for the stages.

All four are unpacked to `D:/TribeUE/tribe_assets/all`: 7,975 files, including 2,787 `.uasset` and 13 `.umap`.

Per Content folder:

| Folder | Packages | Blueprints | Functions | Tables, structs, enums | Notes |
|---|---:|---:|---:|---:|---|
| Equipment | 837 | 278 | 3,605 | 51 | decks, mixers, controllers |
| Menus | 386 | 140 | 2,295 | 11 | includes the deck screens |
| Environment | 296 | 13 | 0 | 0 | stage art; the 13 classes only hold components |
| Replays | 286 | 0 | 0 | 0 | lesson voice-over: 162 sounds, 123 lip-sync tracks; data files below |
| Visuals | 220 | 13 | 182 | 15 | visuals wall, crowd, skins |
| Audio | 169 | 0 | 0 | 0 | sounds only |
| Lessons | 163 | 87 | 755 | 13 | |
| Achievements | 88 | 5 | 65 | 2 | |
| VideoCall | 54 | 7 | 328 | 2 | |
| Pawn | 53 | 7 | 478 | 10 | |
| Dance | 32 | 9 | 96 | 0 | |
| MusicServices | 28 | 6 | 131 | 0 | |
| TrackManager | 26 | 24 | 519 | 0 | |
| Maps | 23 | 13 | 41 | 0 | 13 levels with their level Blueprints, 10 lighting-data packages |
| Twitch | 13 | 8 | 82 | 0 | |
| GameModes | 11 | 10 | 199 | 0 | |
| NDI | 10 | 1 | 0 | 0 | |
| Waveform | 9 | 3 | 40 | 0 | |
| OSC, Discord, MIDI, Metaverse | 5 | 5 | 60 | 0 | |
| Movies, VideoSphere, Accounts | 10 | 0 | 0 | 0 | media and textures only |
| Plugins (MetaXR, glTFRuntime, NDI IO) | 81 | 0 | 0 | 0 | no Blueprints |
| **Total** | **2,800** | **629** | **8,876** | **104** | |

**Results:**
- Every Blueprint is printed as pseudo-code: 629 class files plus 104 table, struct and enum files.
- Level files also list their placed actors with positions (cm), rotations and scales.
- Of 2,800 packages, 0 failed to read. 7 exports stayed unparsed, in 5 NDI assets: NDI plugin objects whose classes
  weren't loaded on the Quest when the type dump ran. They hold no functions.

**Not decoded:**
- **Epic's engine content** in chunk 0 (`Engine/Content` 234 packages, `Engine/Plugins` 142). It is stock UE 5.4.4.
  Its source and content are in `D:\MetaUE54`.
- **Material graphs.** A cooked game keeps compiled shaders, not the node graphs.
- **Art**, apart from the gear: stage meshes and textures are unpacked but not exported to glTF/PNG.

## Data files beside the assets

These are read by Tribe's code at run time. They are not Unreal packages.

| Files | What | Readable as |
|---|---|---|
| 501 `.sav` in `Replays/` | Unreal save files. **Equipment saves (327):** every control's value for one device at one lesson step, plus its track, cue, loop and hot cues. **Rig saves (109):** mixer, channel devices, layout. **Replay saves (64):** avatar, scale, auto-grab. **Dance moves (1).** | text in `.../catalog/data/Replays/` (`scripts/gvas_print.py`) |
| 109 `.seq` in `Replays/` | beat highway charts | plain text, format in the lessons section |
| 126 `.inrp` in `Replays/` | recorded input that the mentor demos replay: head, hands, buttons, triggers | binary, layout below (`scripts/inrp_print.py`) |
| 1 `.json` | lesson pack manifest (`LessonPack_EQLoopsHotCues`: EQ, Loops, Hot Cues, 4 sequences each) | plain text |
| 624 `.txt` | subtitles: 70 lesson replays in each of en, de, es, fr, it, ja-JP and ko-KR (69 in zh-Hans), 16 deck-breakdown videos in en, ja-JP, ko-KR and zh-Hans, plus one stray `_Demo.txt` | plain text |
| 3 `.glb` | Mentor, Default (4.7 MB each) and Dance (148 KB) avatars | glTF |
| `Config/*.ini` | the project's engine and game settings | plain text, highlights below |

The saves were written by four engine builds:
- UE 4.26.2 (74) and 4.27.2 (383): stock and Oculus branches;
- UE 5.4.4 (44).

`gvas_print.py` reads both tag layouts. The 5.4 one has complete type names and a serialization-control byte at the
start of the object.

### Replay files (`.inrp`)

The mentor's recorded performance: 126 files, 158.8 minutes in all, 5.2 s to 366.9 s each. They were read from
libUnreal.so (Ghidra addresses). The decompiled code is in `D:/TribeUE/tribe_native/inrp/`.

**Loading and saving (read):**
- `InputReplayComponent::LoadReplay` (0x51ae3a0) loads the whole file. It runs one serializer (0x51e7588) over the
  replay struct and fails on a version other than 2. `StopRecording` saves with the same serializer, so the reader
  and writer share one layout.
- **Recording** (`TickComponent` 0x51ab000): a frame is added when the `TimeBetweenPositionCaptures` timer runs out,
  or when a key event or a non-zero axis value happens. So frames are irregular: 10.7 to 29 ms apart in the Flanger
  lesson.
- **Playback:**
  - transforms are interpolated between frames, then applied with `SetWorldLocationAndRotation` (world ones) or
    `SetRelativeLocationAndRotation` (relative ones);
  - key codes become FKey presses (1.0) and releases (0.0) on the player input;
  - axis codes become axis values;
  - passing a timestamp fires `OnTimestampTriggered`.

**Layout (read; little-endian):**
- `int32 version` = 2, `int32 frameCount`.
- Each frame:
  - `float time` (s since recording started);
  - `int32 n` + n world transforms;
  - `int32 n` + n relative transforms;
  - `int32 n` + n key-press bytes;
  - `int32 n` + n key-release bytes;
  - `int32 n` + n axis entries of `uint8 code, float value`.
- Then `int32 n` + n `float` timestamps.

**Transforms (read):**
- Each is a quantized vector, then a compressed rotator.
- **The vector** is UE 5.4's `WriteQuantizedVector`, scale 10:
  - a `uint32` holds the bit count (low 6 bits) and a divide-by-10 flag (bit 6);
  - then three components of ceil(bits/8) bytes each, sign-extended;
  - the shipped files use 10 to 12 bits, so positions are in 0.1 mm steps.
- **The rotator** is `FRotator::SerializeCompressed`: per axis, a byte whose low bit says whether a non-zero angle
  byte follows. Degrees = byte × 360/256.

**Codes and components:**
- **Codes (read, from the table built at 0x51bbb80):**
  - keys 0-17 are the Touch controllers' trigger click/touch, grip click, A/B/X/Y click/touch, and thumbstick up/touch;
  - axes 0-5 are both triggers, both grips, and both thumbsticks' Y.
- **What's recorded:** every shipped file holds 0 world and 4 relative transforms per frame.
  - Going by the data, they are head, left hand, right hand, and the actor root (constant per file) **(inferred)**:
    the head is highest at 151-169 cm, the left hand's y is mostly negative, the right hand's positive.
  - The native code passes three components from a pawn helper plus pawn +0x1a0 **(read)**. Which property each one
    is wasn't traced.

**Check:** `python -I scripts/inrp_print.py <Replays dir>` parses all 126 files with 0 failures and 0 bytes left
over, rerun independently while reviewing.
- In `BeatFXFlanger.inrp`: 9,108 frames over 146.99 s, 211 presses and 211 releases, trigger axes 0.00 to 1.00.
- In 45 files the press and release counts differ by more than one. A key held when recording starts shows up as a
  release first.

## Lessons and games: who does what

- **C++** **(read: the class files)**: `ATribeBeatHighwayManager` (chart loading, the line timer, hit judging, score,
  save game, leaderboard points, DJ-challenge progress, chart recording); `ATribeBeatHighwayLane`/`…LaneImpl` (per-control
  event queue, icons, miss timer, self-destroy); `UTribeLessonPackAddon` (DLC lesson tables); `UTribeReplaySaveGame` and
  `UInputReplayComponent` (mentor replays); `UTribeSubtitles`; `ATribeDanceManager`, `ATribeDanceHighwayObject`,
  `UTribeDanceMap`, `UTribeDanceMoveSaveGame`. `ATribeLessonBase` is an empty Actor base.
- **Blueprint**: lesson flow (`BP_LessonManager`, `BP_LessonBase`, `BP_ReplayLessonBase`, `BP_BeatHighwayLessonBase` and
  subclasses), lane spawning and input handling (`BP_HighwayManager`, `BP_BeatHighwayLaneImpl`), all menus, onboarding
  (`BP_OnboardingController`, `BP_FreeToPlayController`), crowd reactions (`Visuals/BP_CrowdManager`), dance scoring
  (`Dance/BP/BP_DanceManager`, `BP_HighwayObject`) and the mentor avatar (`Pawn/InputReplayPawn`).

**Not in the decompile:** the highway's per-line playback tick (`FUN_0510566c`, started by `PlaySequence`), its line
parser (`FUN_05103a10`) and the recorder's line writer (`FUN_051013fc`). Of the constructors, only the highway manager's
was read afterwards, for two defaults. Claims that depend on the unread parts are **(inferred)**.

## Lessons

**Three kinds.**
- **Classic mentor lessons**: Hapa "March 21" (13 rows), Vinyl (8), Pioneer Top Five Features (10), in `F_LessonEntry`
  tables {Title, Description, LessonClass} **(read: Lessons/DT_*.txt)**. Each class is a `BP_ReplayLessonBase` subclass
  that returns a replay name (e.g. "Hapa/MarchLessons/2_LoopIn/LoopIn"), tracks per mixer channel (0: "come_together.mp3",
  3: "kick_back.mp3"), its gear and `GetNextLesson` **(read: Lessons/Hapa/March21/BP_Lesson_HapaMarch_02_LoopIn.txt)**.
  Step 0 plays the replay; when it finishes (0.2 s delay) step 1 calls FinishLesson **(read: BP_ReplayLessonBase.txt)**.
- **Beat-highway lessons**: `GameModeLessonEntry` {LessonId "LessonPack_<Pack>/<Lesson>", Title, LessonClass,
  SequenceEntries[{SequenceTitle, SequenceID, SequenceType, InteractionMode}]} **(read: usmap; DT_Lessons_DJChallenge_Day1.txt)**.
  Classes derive from `BP_BeatHighwayLessonBase`; most DJ-challenge classes are empty subclasses.
- **DLC lesson packs** (`TribeXR-LessonPack_<Name>`): no class; `BP_BeatHighwayAddonLesson` plays them. On install the
  add-on builds its table from `<content>/Replays/LessonPacks/LessonPack_<Name>` and adds the pack's tracks
  **(read: TribeLessonPackAddon.c: NewVirtual91; TribePaths.c: GetLessonPacksPath)**. `MakeLessonDataTable` lists the
  folders and reads a `.json` with "lessons", "name", "sequences", "sequenceType", "folderOrder" **(read: literals; how
  they combine is inferred)**. A `MentorAvatar.glb` in the pack folder becomes the mentor **(read: BP_BeatHighwayAddonLesson.txt)**.

**Starting.** `BP_LessonManager` stops any running lesson, spawns the class (setting `LessonManager`, and `LessonInfo` for
highway lessons), binds OnLessonEnded and calls InitLesson **(read: StartLesson, StartGameModeLesson(Async),
StartGameModeAddonLesson, SetActiveLesson)**. Analytics progress 1/2/3 on Init/Finish/Skip **(read: BP_LessonBase.txt)**.
On Android backgrounding the lesson is stopped; on return it is started again by class (DLC lessons by their stored
entry) **(read: BP_LessonManager.txt: HandleAndroidBackgrounded/Foregrounded; GameModes/TribeGameStateBP.txt)**. A classic
lesson always locks gear swaps; a highway lesson only while a sequence runs **(read: Equipment/BP_Rig.txt: IsEquipmentLocked)**.

**Stepping a highway lesson** **(read: BP_BeatHighwayLessonBase.txt: ContinueLesson_Implementation, PlayLessonHighwaySequence)**:
1. Unless the type is Exercise, mentor replays `Replays/LessonPacks/<LessonId>/<SeqId>/<SeqId>_Demo.inrp`, then `_Demo_1`,
   `_Demo_2`… until a file is missing. Each loads the `_Demo_EquipmentSave`, stops all decks without brake, sets master
   level 0.4 and headphone level 0.3.
2. A replay timestamp starts the `<SeqId>_Demo.seq` chart in replay mode under the mentor's hands; a negative timestamp t
   starts it |t| seconds in **(read: OnTimestampTriggered)**.
3. Then by type: Hybrid, Exercise, Demonstration, Unspecified play `<SeqId>.seq`; Explanation has no chart and completes at
   once; Video plays `<SeqId>.mp4` and completes when it ends.
4. `ContinueAfterSequence` records the result (see scores); after the last one, SetSequenceCompleted(LessonId, 100, LessonCompleted).
- The menu's Play runs PlaySequenceAtIndex(i, true); Replay (Hybrid only) passes false and skips the mentor
  **(read: Menus/W_BeatHighwaySequenceMenu.txt)**. Subclasses hook the steps: Day 2 Pre-Cue routes channel cue buttons to
  the virtual headphones (left ear for channels below numChannels/2), Day 4 Gear Overview flashes control groups, Day 5
  6-song mix sets Beat FX time interval 17 **(read: Lessons/Hapa/DJChallenge/Day2/…PreCue.txt, BP_BeatHighwayLessonBase.txt:
  OnCueButtonPressed, Day4/…GearOverview.txt, Day5/…6SongMix.txt)**.

**Listing and unlocking.**
- Highway packs list rows in table order: status 0 if completed, 1 for the first uncompleted, 2 for later ones (3 if
  config `TribeLessons/bUnlockAll` or the pack's `bAllUnlocked`). Status 2 rows don't start when clicked **(read:
  Menus/W_BeatHighwayLessonMenu.txt: DisplayLessonPack)**. Names are **(inferred)**: E_LessonStatus is NewEnumerator0..4.
- Sequences follow the same rule; finishing one unlocks the next. Labels: Hybrid/Exercise "Challenge" with "{Score} / 100",
  Explanation "Learn", Demonstration/Video "Watch" **(read: W_BeatHighwaySequenceMenu.txt, W_BeatHighwaySequenceItem.txt)**.
- After a pack's last lesson: SetSequenceCompleted(PackName, 100, LessonPackCompleted) **(read: HandleLessonsCompleted)**.
- The sequence menu also raises a subscribe prompt, "Nice work — you finished {LessonName}! Go Pro to unlock the full
  lesson library." **(read; it sits in a latent continuation, so when it fires is not visible)**.
- Classic packs have no lock state; "Next Lesson" loads GetNextLesson **(read: Lessons/W_LessonMenu.txt)**.

**Gear per step.**
- Classic: ResetEverything respawns the gear if it differs from GetLessonEquipment (default 2 Tribe CDJs on channels 0
  and 3, Tribe mixer), otherwise unloads all tracks and resets controls; then the track map loads. Master level 0.25 in a
  video call with audio output type 2, 3, 5 or 6, else 0.5 **(read: BP_LessonBase.txt)**.
- Highway: `<SeqId>_EquipmentSave/` (or `_Demo_EquipmentSave`) holds `Rig.sav` (mixer class, channel device classes,
  layout string, deck scale) and `Deck_1/Deck_2/Mixer.sav` (every control value by name, mixer names suffixed _0.._3, plus
  SavedTrack {TrackName, PlaybackPosition, CuePosition, LoopOutPosition}) **(read: data)**. Of the 501 saves: 327 equipment,
  109 rig, 64 replay, 1 dance. Rigs: starter mixer + 2 starter CDJs ("0,/1,//") ×63; DJM-900NXS2 with CDJ-3000s on
  channels 1 and 4 ("1,0,/2,3,//") ×38; FLX4 ×8. Day 1 "Play Cue 1 Bar" loads "Metronome_Counting 1 Bar_125.mp3".
- PlayHighwaySequence sets PreparingToPlay (3), calls Rig.LoadRigState then LoadDeviceStates(path, 4), waits for every
  deck's OnEquipmentSaveLoaded and the sync master's track analysis, then starts the chart **(read: BP_HighwayManager.txt)**.

## The mentor replay avatar

- `PlayLessonReplay(dir, name, bEnqueue, AvatarIdOverride)` reuses or spawns an `InputReplayPawn` at the origin with
  PlayerInfo {HMD 1, OnlineID "0", AvatarID}, `bDJing` true, camera auto-switch only outside VR **(read: BP_LessonManager.txt)**.
- Avatar: the override if it is a valid Ready Player Me id or Meta avatars are supported, else `GetTribeMentorAvatarId()`.
  Highway lessons pass the replay's `.sav` sidecar AvatarId ("zip://99.glb" in 61 of 64, "2755444181226226" in 3); DLC
  packs pass MentorAvatar.glb **(read: BP_BeatHighwayLessonBase.txt, data)**. The sidecar also sets deck scale (if ≥ 1)
  and auto-grab.
- Replays live under `GetInputReplayPath()` = `<content>/Replays/` (126 `.inrp` shipped) **(read: InputReplayComponent.c)**.
  The voice is SoundWave `/Game/Replays/<name>_Audio` with a `_Audio_LipSyncSequence` **(read: Pawn/InputReplayPawn.txt:
  FindReplayAudioAssets)**. `SetMentorHasMenuControl` hands menu input to the mentor **(read: BP_LessonBase.txt)**.
- Timestamps: StoreTimestamp appends floats while recording; AddTimestamp loads, inserts, sorts and re-saves; playback
  raises OnTimestampTriggered(Index, Timestamp) **(read: InputReplayComponent.c; the trigger moment is inferred)**.

## Subtitles

- File `<replay path>_Sub_<culture>.txt`: blocks "(MM:SS):" then a text line; time = MM × 60 + SS **(read:
  TribeSubtitles.c: LoadSubtitles)**. Shipped: 70 files each for de, en, es, fr, it, ja-JP, ko-KR and 69 for zh-Hans.
- `GetSubtitleIndexFromTime` scans forward from the current index for the last entry whose time ≤ now **(read)**.
- The toggle is config `TribeLessons/bSubtitlesEnabled`; with no saved value it is on for non-English cultures
  **(read: W_BeatHighwaySequenceMenu.txt: LoadSubtitlesEnabled and its defaults)**.

## The beat highway

**Chart format (.seq)**, 109 files, 19,328 event lines **(read: data)**:
- Line 1 `Version=1`; optional line 2 `SoftObjectPaths=` (15 files, all onboarding mixes) lists SoundWaves loaded into
  `SequenceAudioClips` **(read: TribeBeatHighwayManager.c: PlaySequence)**.
- Each further line holds one or two events (`TribeBeatHighwayEventPair`): 6 columns (11,272 lines), 7 = +ReactionType (66),
  8 = +SoundClipIndex (7,937), 12 = two 6-column events (32), 16 = two 8-column events (4), 9 = an 8-column line with a
  trailing comma (1), plus 16 empty lines.
- Reactions occur only in the onboarding mixes (Crowd 104, CrowdAndDialogue 12, Dialogue 6, typos "visual" and "False").
  134 clip references (indices 0-21), including on empty lines.
- On load each event's value is rounded to the control's `RoundingInterval` from `DT_BeatHighwayLaneInfo` (153 rows; volume
  fader 1, crossfader 0.05, EQ 0.25; 0 = none). An event whose value differs from that control's previous value becomes
  On; only On events count toward the maximum score **(read: PlaySequence)**. Faders are charted as Hold lines with values.
- Holds are shown (held icon) but never judged or scored; a button held for a bar is On + 3 Hold lines **(read: judge below)**.

**How long one line lasts.** One line is one tick of a looping timer whose period is
`BeatFrequency × 60 / MasterTempo` seconds **(read: PlaySequence and StartRecording build the timer with
`BeatFrequency * (60.0 / MasterTempo)`; GetPlaybackTimeRateSeconds returns its rate)**. MasterTempo is the override tempo
if above 0 (onboarding tutorials: 62), else the BPM of the sync-master deck or the first deck with one, else 125
**(read: BP_HighwayManager.txt: GetTempoAndStartingBeat)**.
- **One line is one beat.** `BeatFrequency` defaults to 1.0: the constructor (`FUN_051010d4`) writes `0x3f800000` at
  +0x290. No asset or Blueprint changes it **(read)**. So at 125 BPM a line lasts 0.48 s.
- **The charts agree:** "Hold Cue 1 Bar" is On + 3 Holds; "Volume Fader Four/Two Beats" and "Crossfader Four/Two
  Beats" change every 4/2 lines; and the replay sync subtracts (NumDisplayedBeatEvents + 1) × 60/BPM seconds.
- The C++ `MasterTempo` default is 120 (`0x42f00000` at +0x29c), but `PlaySequence` is always given a tempo.
- The first tick comes one period after start; a start offset skips whole lines and shortens the first wait **(read)**.
  StartingBeat (1-4) = round((closest beat ms − beatgrid start ms) / beat ms) mod 4 + 1 aligns the lane's bar lines.

**Lanes.** One lane per control (`ActiveLanes`, keyed by ControlName + MixerChannel).
- The C++ tick calls `SpawnHighwayLane`; the Blueprint spawns `BP_BeatHighwayLaneImpl` on the deck (or the mixer for mixer
  events) at the control's relative location + RelativeLaneLocation, scaled by LaneScale, with a Center/Left/Right mesh
  (MeshType column) **(read: BP_HighwayManager.txt: SpawnHighwayLane; BP_BeatHighwayLaneImpl.txt: HandleSetupLane)**.
  Left/Right lanes give their icons a −0.19/+0.19 term that grows as they travel **(read: TribeBeatHighwayLaneImpl.c:
  NewVirtual229, NewVirtual232; that the material uses it as a sideways skew is inferred)**. The
  EBeatHighwayLaneAttachment functions (`AttachLane`, default Top) have no caller.
- Overlapping controls are hidden by bone (ref-counted, `JogWheel` exempt); overlapping lanes with no pending event are
  destroyed **(read: SpawnHighwayLane; TribeBeatHighwayLane.c: EndPlay)**.
- Icons: a 12-slot ring; On → OneClickOnIcon, or OnPlusHoldIcon if a Hold follows, or up/down OnIcons in continuous modes;
  Hold → HeldIcon. Spacing 1/12 lane per lane step, scrolling (BPM/60)/6 lane per second **(read:
  TribeBeatHighwayLaneImpl.c: NewVirtual229, NewVirtual232)**. A lane step is half a line, so notes show about 6 beats
  ahead **(inferred: `OnControlStartInteraction` divides a lane index by trunc(BeatFrequency / 0.5) = 2)**.
- A lane with no event in the next BeatGapThreshold lines destroys itself after ((IdleBeatsUntilDestroyed + 6) / BPM) × 60
  − 0.05 s **(read)**.

**Judging** **(read: TribeBeatHighwayManager.c: FUN_0510627c, behind GetBeatEventResult)**:
- A press calls GetBeatEventResult(ControlId). The judge looks only at On events for that control on line
  `PlaybackSequenceIndex − NumDisplayedBeatEvents` (early by rate − elapsed) and the line before it (late by elapsed),
  skips a line already judged for that control, and keeps the nearer one.
- **The control's value is not checked.** `GetBeatEventResult` takes a `ControlValue`, but the judge never reads `s0`,
  the register it arrives in **(read: the disassembly of `FUN_0510627c`)**.
- **The bucket.** r = offset / period, clamped to −1..1. Then bucket = floor(r × 4 + 0.5) / 4 (`frintm`, a floor), so r is
  rounded to the nearest quarter and the windows are symmetric **(read: the disassembly, 0x05106708-0x051067f8)**:

  | r | Result |
  |---|---|
  | [−1, −0.875) | FailureEarly |
  | [−0.875, −0.625) | VeryEarly |
  | [−0.625, −0.375) | Early |
  | [−0.375, −0.125) | SlightlyEarly |
  | [−0.125, 0.125) | PerfectEarly if r ≤ 0, PerfectLate if r > 0 |
  | [0.125, 0.375) | SlightlyLate |
  | [0.375, 0.625) | Late |
  | [0.625, 0.875) | VeryLate |
  | [0.875, 1] | FailureLate |

  No On event in range = Failure, DesiredValue −1.
- Points: 1 for a perfect bucket, else 1 − |r|. Score (`GetScore`) = points / On events, −1 if none.
- Lessons store and show round(score × 100); the demo mix stores score × 100 **(read: ContinueAfterSequence; OnMixEnded)**.

**Input modes.** `UserInteractionMode` is OneClick when the menu's one-click slider is on, ContinuousUnguided when off;
replay mode uses ContinuousUnguided for the BeatHighwayIntro pack, else OneClick; onboarding forces OneClick
**(read: BP_HighwayManager.txt: PlayHighwaySequence; W_BeatHighwaySequenceMenu.txt)**. No Blueprint sets
ContinuousGuided or reads the per-sequence InteractionMode in the tables **(read: grep)**.
- OneClick: grabbing a fader or knob releases it, it glides to the charted value at 10 per second (0 to 1 in 0.1 s), and
  the press is judged **(read: OnControlAreaGrabbed, CheckControlInput; ControlSnapSpeed 10)**.
- Continuous: the lane judges automatically when the value comes within 0.05 of the next target **(read:
  BP_BeatHighwayLaneImpl.txt: CheckContinuousControlInput)**. The control gets clamp limits between the current and next
  target **(read: SetBeatHighwayClampedValues; their use is inferred)**.

**Misses and help.** When an event reaches the hit line, the lane starts a timer of 0.5 beat (if the lane's next event is
within 2 steps) or 1 beat; with no input by then it reports FailureNoInput **(read: TribeBeatHighwayLaneImpl.c:
NewVirtual229; TribeBeatHighwayLane.c: FUN_050fe740)**. On FailureNoInput the Blueprint sets a fader/knob to its target, or presses a button with
your left hand **(read: BP_BeatHighwayLaneImpl.txt: HandleSuccessResult)**. When you start a stopped deck with Play or a
hot cue (first time per channel), the track position is shifted so the music lines up with the chart **(read:
OnControlStartInteraction)**. If a Play lane expires with its deck stopped, the deck starts IdleBeatsUntilDestroyed beats
further in **(read: CheckPlay)**.

**Feedback.**
- Popup per lane: "Perfect", "SlightlyEarly/Late", "Early/Late", "VeryEarly/Late" (the Failure Early/Late results show the
  "Very" text, Failure and NoInput none); the goal flashes the failure colour for 0.2 s below SlightlyEarly
  **(read: HandleSuccessResult)**. Replay mode shows no popup and sends no reaction; onboarding turns popups back on.
- `BP_CrowdManager`: sparkle rate 40/75/130/250/400 and speed 1/1/1.2/1.75/2.7 from failures up to perfect. Crowd → crowd
  cheer; Dialogue → Hapa voice: perfect "Nice/NiceJob/JustLikeThat", slightly "Allright/YouGotIt", early "TryThatOneMoreTime/
  GettingCloser/Almost", late "LittleSlow"; CrowdAndDialogue both **(read: Visuals/BP_CrowdManager.txt)**.
- No Blueprint calls GetAudioClip; how SoundClipIndex clips play is **(inferred)** to be the C++ tick.
- End message bands (0-100): <30 "YouCanDoBetter/GoodEffort/TryAgain", <60 "AllRight/NotBad/OK", <80
  "NiceJob/Sweet/GoodJob", ≥80 "Amazing/GreatJob/Incredible"; a new high score "NiceYouBeatYourHighScore/
  GreatImprovement/NewHighScore" **(read: GetRandomScoreMessage)**.

**Recording a chart** (Recordings menu) **(read: Menus/W_RecordingsMenu.txt: RecordReplay, RecordSequence; BP_HighwayManager.txt)**:
- ArmForRecording("<Name>/<Name>[demo suffix]") sets ArmedForRecording; RecordReplay also records the player's input
  replay, the mixer to "<…>_Audio" with mic mode 1, and the avatar/deck scale/auto-grab sidecar.
- The first control touched saves `<GameMode path><Name>_EquipmentSave`, starts the line timer and stores a replay
  timestamp of (playback time − (NumDisplayedBeatEvents + 1) × 60 / BPM), which later starts the chart in sync.
- Presses become On, quantized to the nearer line; ClickAndHold buttons write Hold every line while held; empty lines are
  written when nothing is held **(read: RecordBeatEvent, RecordEmptyEvent; RecordingTick)**.
- With `bRecordContinuousAsOneClick` (true), touching a fader snaps it to the opposite end of 0..1 and records one On.
- Values round to 0.01. StopRecording prepends a header (the "Version=1" text is **(inferred)**) and writes `.seq`.
  `GetGameModePath` builds on "Documents/" and "GameMode/" **(read: TribePaths.c)**.

## Scores, XP and leaderboard points

- Save slot "BeatHighway": `SequenceScores` (name → score), `ExperienceLevel`, `bAddedPointsToLeaderboard`
  **(read: usmap; BeginPlay, SetSequenceCompleted)**. Keys: "<LessonId><step>" (e.g.
  "LessonPack_DJChallengeDay1/01_PlayAndCue2"), "<LessonId>", the pack name, "Onboarding/Mix<N>".
- A step counts as done as soon as its key exists; any score completes an exercise **(read: IsSequenceCompleted)**.
- Exercises (Hybrid/Exercise) store round(score × 100); other types store −1 **(read: ContinueAfterSequence)**.
- First completion gives points: exercise = its score, ExplanationCompleted 10 ("Done"), LessonCompleted 100
  ("CompletedAllExercises"), LessonPackCompleted 100 ("CompletedAllLessons"); type None = the score. Only types 1 and 2
  show a notification. A higher retry gives the difference with a high-score message; otherwise
  OnSequenceCompletedNoHighScore **(read: SetSequenceCompleted)**.
- AddLeaderboardPoints sends {round(points), category, message, notify} to the game instance; the category is the text
  before "/", and all five DJ-challenge days merge into "LessonPack_DJChallenge" **(read: FUN_05100554)**. On first run
  every stored score above 0 is back-filled once, except keys starting "TribeXR-LessonPack_" **(read: BeginPlay)**.
- XP: AddExperience adds to ExperienceLevel and saves, but no Blueprint calls AddExperience or GetExperience **(read: grep)**.

## The 5-day DJ challenge

- Days 1-5 are `DT_Lessons_DJChallenge_Day1..5` (`DJChallengeDayDataTables` on BP_HighwayManager): 6/7/4/4/4 lessons,
  21/24/13/11/8 sequences = 25 lessons and 77 sequences (35 exercises, 31 explanations, 11 demonstrations). Days 1-2 and
  6 of Day 3's 13 sequences are tagged OneClick, the rest ContinuousUnguided (the tag is unused, see above) **(read: tables)**.
- RefreshDJChallengeProgress (on BeginPlay and every completion): per day Completed/Total sequences, bDayCompleted
  (Total > 0 and all done), Progress, the first uncompleted lesson; CurrentDay = first incomplete day (5 when all done);
  TotalProgress = all completed / all sequences **(read: TribeBeatHighwayManager.c)**.
- Days are not locked: an earlier unfinished day only changes the button from "Continue" to "Start"
  **(read: Menus/W_DJChallengePathEntry.txt: UpdateProgress)**. Banner: "Day {Current} of 5 - {Percent}% Complete".
- First open plays the intro replay "LessonPacks/DJChallengeIntro/DJChallengeIntro_Demo" and sets config
  `TribeStatus/DJChallengeOnboarded` **(read: Menus/W_LessonPacksMenu.txt)**. With all five day packs completed, achievement
  '5DayDJChallenge' **(read: W_BeatHighwayLessonMenu.txt: CheckForDJChallengeBadge)**.

## Onboarding and the free-to-play demo mixes

- `BP_OnboardingController` **(read)**: first time is config `TribeStatus/Onboarded` not true. It handles the
  grandfather notice and sign-up, then StartOnboarding (third-person spectator, crowd ambient, track preview
  "095 - F.O.O.L - Revenger.mp3"). The slideshow is off (`ShouldShowSlideshow` returns false).
- Deck tutorial, first time: four charts `Replays/Onboarding/BeatHighwayTutorial1..4` in replay mode, OneClick, tempo 62,
  for deck channel 1's Play button, performance pad 2 (pad mode 2 switched on), channel 1 volume fader and low EQ.
  - A result of SlightlyEarly or better gives 2 points and advances after 1/3/0.5 s.
  - Lower results play "Try_again-General" (Failure), "Try_again-Early" or "Try_again-Late".
  - Then "Practice_Great_remember_to_click", a 9 s wait, and the chosen genre's mix **(inferred: latent continuation)**.
- `BP_FreeToPlayController` "Demo Mix" **(read)**: 6 genre mixes (voice intros Electro, House, Trap, Tech house, Dubstep,
  Hip hop) play `Replays/Onboarding/Mix<N>/Mix<N>.seq` with `Mix<N>_EquipmentSave`. Score × 100 is saved as
  "Onboarding/Mix<N>" and shown as high scores. 12 demo tracks go into the lesson tracks folder.
- The older `GameModes/DemoGM` uses `HighwaySequences/Onboarding` and saves score × 0.1 **(read: DemoGM.txt: OnMixEnded)**.

## The dance game

- What it is: targets fly at you each beat; hit them with the matching hand (left blue, right red).
  - **Maps**: named lists of moves {BeatLength, RightHandPositions[], LeftHandPositions[]} with OriginalBPM.
  - **Storage**: saved in slot "DanceCache" **(read: usmap; TribeDanceManager.c: SaveDanceMoveCache)**.
  - **Shipped**: `DefaultDanceCache` has 8 maps, 32 moves of 8 beats, all at 125 BPM. Positions sit on an 18 cm grid:
    X −43/−25/−7/11/29, Z 126/144/162, Y 0; −1,−1,−1 = no target **(derived: data)**.
- Playing: a downbeat (beat % 4 == 0) of the DJ's broadcast beat signal starts the game. Each beat then spawns one object
  holding that beat's left and right positions, moving maps in order, optionally looping or shuffled **(read:
  HandleMetaverseBeatSignal, DancePlayTick; BP_DanceManager.txt: StartDanceGame)**. The editor runs it from the sync
  master's BPM instead. Only a user with video-call priority 32 broadcasts the beat (that 32 means "on stage" is inferred).
- Travel: spawn 300 cm before the rig, 330 cm to the player, covered in NumBeatsToPlayer beats; an unhit hand is a miss
  80 cm past the rig **(read: SetupSpawnpoints; TribeDanceHighwayObject.c: Tick)**.
- Score: hit +1 and streak +1, an air horn every 64 streak; a miss resets the streak **(read: AddPointFromBeatHit)**.
  Hit effects grow up to a 150 streak (UpdateNiagaraParameters). `TotalAllowedMisses` (15) is never read.
- Recording: 4 metronome count-in beats, then one beat per tick; trigger presses store each hand's position, grid-snapped
  and assigned to the nearer beat **(read: StartCountIn, RecordHandPosition, DanceRecordTick)**.
  - After BeatLength beats the move is appended and saved. An input replay `DanceReplays/Replay_<Map><index>` is kept.
  - The length resets to 4.
- The demo dancer (`Replays/DanceAvatar.glb`) stands at (0, −300, −140), turned 90°, scale (−1.5, −1.5, 1.5). It replays at
  CurrentBPM / OriginalBPM speed **(read: SpawnReplayPawn, RestartDanceReplay)**.

## Where this calls into the gear

- `BP_Rig`: LoadRigState, LoadDeviceStates(path, 4), LoadRigAndDeviceStates, SaveDeviceStates, Save Rig State,
  RespawnEquipment, SetDeckScale, SetLockedForLessons, ResetControls, GetDeckByChannel, and the control
  start/end/reset delegates the highway listens to.
- `BP_Deck`: LoadTrack, Start/Stop Play, StopPlayForceNoBrake, Get/SetPlaybackMs, StartSync, SeekToCue, and the audio
  player's GetBpm, GetClosestBeatMs, GetHotCueAsTime and GetSecondsToNextBar.
- `BP_Console`: SyncMaster, SetHeadphonesWorn, the mixer's SetHeadphonesLevel, SetBeatFXTimeInterval, ChannelsControls.
- `BP_BaseDeckControl`: GetControlId/Value, InterpToValue, Grab/Release, highlight, SetBoneVisible,
  SetBeatHighwayClampedValues, and GetDefaultBeatHighwayRange (0..1). The FLX4 updates pad lanes when its pad mode changes.
- `BP_LessonManager` also has a text command language ("Deck1 -> play", "Mixer -> lock", controls named like
  "Deck1 HotCueButtonA") with no caller in this build **(read: HandleLessonAction; grep)**.

## Lessons and games: not covered or unclear

- The C++ playback tick is not in the decompile, so these are unread: when OnSequenceEnded fires, how lane steps map to
  lines, how clips play, what the "load" lines written by RecordTrackLoadEvent do.
- C++ defaults read so far: `BeatFrequency` 1.0 and `MasterTempo` 120, from the constructor. Still unread:
  NumDisplayedBeatEvents, MaxEventsPerBeat, IdleBeatsUntilDestroyed, BeatGapThreshold, the dance grid size,
  NumBeatsToPlayer. They are derived above only where the data allows.
- ChangeMasterTempo (a mid-chart tempo change) has no Blueprint caller; its use is unknown.
- The DLC JSON schema details, and the E_LessonStatus and E_NotificationCloseReason names. (The `.inrp` layout is in
  "Replay files" above.)
- The dance replay is recorded per move (`Replay_<Map><index>`) but played as `Replay_<Map>`; whether that file exists is unchecked.

## The visuals wall

### Parts and play modes

- **The actor.** `BP_TribeVisualsManager` (native parent `ATribeVisualsManager`) sits in CommonLevel at (-90.0072,
  144.473, -136) **(read: `Maps/Levels/CommonLevel.txt`)**.
- **Canvases and video.** It draws on `RT_BackdropCanvas` (images, GIFs) and `RT_BackdropCanvasText` (text), both
  1024 × 256. Video plays in `BackdropMediaPlayer` (Loop = True) into the media texture `BackdropMediaPlayer_Video`
  **(read: asset dumps)**.
- **One wall mesh at a time.** `SetBackdropStaticMesh` stores one actor (+0x2d0). While something plays, it sets slot 0
  to that mode's material: GIF `L_flaresDJbooth` (+0x2e8), video `M_VideoBackdrop` (+0x2e0), NDI `MI_InputSourceBackwall`
  (+0x2f0); idle is `M_VideoBackdropEmpty` **(read: `TribeXR.TribeVisualsManager.c: SetBackdropStaticMesh`;
  `Visuals/BP_TribeVisualsManager.txt: UserConstructionScript`)**. Correction to NOTES.md: +0x3d4 is the play mode, not
  the draw mode, and NOTES has the video and NDI slots swapped.
- **Play modes** (`ETribeVMPlayMode`: 0 NotPlaying, 1 GifPlaying, 2 VideoPlaying, 3 NdiStreamPlaying). The first GIF
  sets 1, `OnMediaPlayerOpened` sets 2, `StreamNdiToBackdrop` sets 3 and `StopDrawingAll` sets 0 **(read: calls to
  `FUN_0520f2fc`)**.
- **Visibility.** `UpdateBackdropVisibility` shows the wall while anything plays. When idle it hides the wall only in
  environment 7, Passthrough **(read; that the compared field is GameState.CurrentEnvironment is inferred from the 7)**.
- **Lights.** On a play-mode change the Blueprint calls `SetLightsDimmed(next != 0)`. While dimmed, the room skylight
  and booth spotlight run at level intensity × `LightDimFactor`, and the backdrop spotlight switches on **(read:
  `PlayModeChanged`, `SetLightsDimmed_Impl`)**. The menu's lighting toggle (`SetLightsDisabled`) cancels the dimming.

### Sources

- **The media list.** `RefreshMediaFolders` scans `TribePaths.GetVisualsMediaPath` for `.gif` and `.mp4` only (str
  0x00411bb0 = ".mp4") **(read)**. Folders: **My Gifs** (with a `Downloads` subfolder for paths containing
  `Downloads/`), **My Videos**, **360 Videos** (paths containing `360`), **Visual Packs** (one folder per installed
  `TribeXR-VisualsPack_` pak, played straight from the pak; **read: `CreateVisualsPackFolder`**), and one folder per
  `TribeXR-360VideoPack_` pak.
- **Picking a file** (`Visuals/W_VisualSourcesList.txt`) **(read)**. The NDI entry → `StreamNdiToBackdrop`; a GIF →
  `DrawGifToBackdrop`; a path containing `360` → the VideoSphere environment, then the sphere; anything else →
  `StreamVideoToBackdrop("file://"+path)`. A loop with "360" in its path never reaches the wall.
- **Video.** `StreamVideoToBackdrop` stores the URL and opens it on the player (the asset loops; the extra engine call
  with 1 is probably SetLooping, **inferred**). On open: play mode 2, the aspect ratio into `MPC_VideoBackdrop.Aspect`,
  and `OnMediaPlayerOpenSuccess`. A failed open does nothing: its body is the empty stub at 0x01546ca4 **(read)**.
- **GIF downloads.** `DownloadGifFileToBackdrop(url)` takes `.gif`/`.mp4` only and runs at most `MaxGifsDownloading`
  at once (the rest queue) **(read)**. Files go to `Downloads/Gifs/TEMP`, or with `bSaveGifDownloads` to
  `<media>/Downloads<GiphyId>.gif`, in which case an earlier download is redrawn from disk.
- **Text.** `SetBackdropHeader1/2` redraw both lines in `Roboto_Large`: header 1 at 0.65, 0.80 of the canvas and
  header 2 at 0.35, 0.70 (str 0x0055b560, 0x005541a8). Their only caller, `DrawDeckTrackToBackdrop`, is never called,
  so stock Tribe shows no track titles **(read)**.
- **Images.** `DrawTextureToBackdropRandom` places a texture at random, rotated 80·r − 40° (Twitch emotes use it)
  **(read)**.

### Per-frame work and the average colour

- **Native `Tick`.** Play mode 3 runs `NdiPlaybackTick` and mode 2 runs `VideoPlaybackTick`. In every mode a beat timer
  at +0x3bc counts down and adds 60.0 / BPM when it runs out **(read: `TribeXR.TribeVisualsManager.c: Tick`)**.
- **`GifPlaybackTick`** fires after each GIF frame is drawn (from `DrawGifFrameToBackdrop`), not every engine frame
  **(read)**.
- **How the three event stubs were identified (read, in Ghidra).** Each looks up a global FName and calls
  `ProcessEvent`. `_INIT_1105` builds those globals from the strings:

  | Stub | Global | Name |
  |---|---|---|
  | `FUN_050ef9e0` | `0x7ffeb10` | `NdiPlaybackTick` |
  | `FUN_050f08cc` | `0x7ffeb28` | `VideoPlaybackTick` |
  | `FUN_050eef38` | `0x7ffeb08` | `GifPlaybackTick` |
- **The average colour drives only the backdrop spotlight** **(read: `BP_TribeVisualsManager.txt`)**:
  - GIF: `GetGifAverageColor()`, the first GIF's current frame from a per-frame colour table;
  - NDI: `ComputeAverageColorFromTexture(VT_NdiInputLeft)`;
  - video: the same on desktop, but on Android the video tick returns at once.

  So on Quest the light follows GIFs and NDI, not videos.

### GIF draw modes

| Menu label | Enum | MPC Tile / Mirror / StretchMode | Frame of w × h px on the 1024 × 256 canvas |
|---|---|---|---|
| Split | 0 | 1 / 0 / (1,0,0,0) | two GIFs at 2w × 2h centred at x 256 and 768, y 128; a lone GIF fills both halves |
| Mirrored | 1 | 1 / 1 / (1,0,0,0) | 2w × 2h at x 256, plus a U-flipped copy at 768 |
| Fullscreen | 2 | 0 / 0 / (1,0,0,0) | 4w × 4h from x 0, y 128 − 2h |
| FitToScreen | 3 | 0 / 0 / (0,1,0,0) | height 256, width 2·256·w/h, centred at x 512; canvas cleared first |
| Stretch | 4 | 0 / 0 / (0,0,1,0) | (0,0) to (1024,256) |

**(read: `DrawGifFrameToBackdrop`, `SetGifDrawMode`, `DrawModeChanged`; labels from the `W_VisualsMenu` defaults)**.
The menu selects Fullscreen at start. Split keeps two GIFs and replaces them alternately; leaving it drops the second.

### GIF timing and beat-matching

- **Frame timer.** A looping timer of 1 / PlaybackRate s (0.1 s while loading) advances each GIF **(read:
  `TribeXR.TribeGif.c: StartPlaying`)**.
- **Which BPM.** `RefreshGifBeatmatch` takes `GetBpm()` and `GetSecondsToNextBar()` of the deck whose track changed
  last. It runs only when that track starts playing or finishes analysis, so GIFs ignore tempo changes within a track
  **(read; "ignore" inferred: no other callers)**.
- **The math.** Each GIF gets `SetBeatmatchBPM(BPM / BeatsPerLoop)` **(read: `DrawGifToBackdrop`)**. That function
  **(read: `TribeGif.c: SetBeatmatchBPM`)**:
  1. L = (NumFrames / NativeFps) / (60 / bpm);
  2. if L > 1.6, divide L by 2^ceil(log2(L/1.6)); if L < 0.625, multiply L by 2^ceil(log2(0.625/L));
  3. PlaybackRate = clamp(L × NativeFps, 10.0, 90.0).

  So each loop spans a power-of-two multiple of BeatsPerLoop beats, at 0.625-1.6× its own speed. BeatsPerLoop's C++
  default isn't decompiled, and no Blueprint sets it.
- **Phase.** With beat-match on, a new GIF starts at `SetProgressSeconds(-timer)`, so its first frame lands on the next
  beat of the +0x3bc timer. With it off, the GIF starts at frame 0 at its own speed **(read)**.

### Deck rings, and no sync

- **Deck rings** ("control VFX"). Each deck gets a plane with `MI_RadialShockwave`, shown while that deck plays and its
  channel is audible **(read: `SpawnRadialFX`, `UpdateRadialFX`)**. `Phase` = 1 − frac(SecondsToNextBar / (60 / BPM)),
  a 0 → 1 ramp every beat. The colour depends on whether the channel is below NumDecks / 2.
- **No sync between players.** Neither the C++ (overrides: Destructor, EndPlay, Tick) nor the Blueprint replicates
  anything, so each player sees only what they picked **(read)**. Twitch commands may be the exception (see Twitch;
  unchecked).

## The crowd

- **Not a visible crowd.** No decoded class or level has audience figures **(read)**. `BP_CrowdManager` is audio plus
  `NS_CrowdSparkle` and `NS_Fireworks_MiniTranslucent` **(read: its dump)**.
- **Where it exists.** Only the Demo Mix game mode and the free-play lessons spawn it, attached to the rig at
  (0, -30, -5) **(read: `GameModes/DemoGM/DemoGM.txt`, `Lessons/BP_FreeToPlayController.txt`)**.
- **What drives it.** Only `BeatHighwayManager.OnBeatEventResult`, the DJ challenge's timing grade. Player count,
  energy and LOD play no part **(read: `Visuals/BP_CrowdManager.txt`)**. By grade pair (`EBeatEventResult` 0-11):

  | | failures | failures | Very | plain | Slightly | Perfect |
  |---|---|---|---|---|---|---|
  | Sparkle spawn rate | 40 | 40 | 75 | 130 | 250 | 400 |
  | Upward velocity | 1 | 1 | 1 | 1.2 | 1.75 | 2.7 |
  | Cheer volume | 0 | 0 | 0.15 | 0.3 | 0.5 | 0.8 |

- **Afterwards.** Spawn rate and velocity decay × 0.9975 per tick, down to 60 and 1. The reaction type picks a cheer,
  a Hapa voice line, or both. Cheers play at world (0, -200, 0) and never repeat back to back.

## Stock environments

### Boot and level roles

- **StartMap** runs `HostGame("TribeMainGM")` **(read: `Maps/StartMap.txt`)**. It runs `OnboardingGM` with config
  `DemoMode`, `ArcadeGM` with `arcade`, and desktop modes with `spectator` or `nohmd`. On Android it first requests
  media and audio permissions.
- **DJRoomMap** is the game map (`GetGameLevelName`), with an empty level Blueprint **(read)**. Its BeginPlay loads
  each `AdditionalSublevels` entry, blocking and visible **(read: `TribeXR.TribeGameState.c: HandleBeginPlay`)**. That
  the list holds CommonLevel is **(inferred: NOTES.md; the rig is there)**.
- **CommonLevel** holds what persists across environments **(read)**:
  - `BP_Rig` (-4.6847, 31.132, 100) and `PlayerStartDJ` (-6.0, 87.31, 0.77, yaw -90);
  - `SpectatorCamera1` (-1.92, -85.8, 175.7, yaw 90), `2_3` (0, 39.47, 194, top-down), `3` (119.7, 85.44, 150,
    yaw -141), `4` (98.99, -75.53, 158, yaw -233), plus first-person and auto-cam;
  - the spectrum analyzer, the video-call manager and the schedule.

  The DJ faces -Y, toward the cameras; every wall stands behind the DJ at +Y **(inferred: positions)**.

### Switching and streaming

- **The level list is native**, which confirms NOTES.md. `GetEnvironmentLevelName` maps each enum value (table below)
  into `World'/Game/Maps/Environments/%s.%s'` **(read: `TribeXR.TribeEnvironmentTypes.c`)**.
- **`SetEnvironment(new)`** **(read: `TribeXR.TribeGameState.c`)**. It is ignored if `new` is current, or while the
  previous level is still unloading (+0x309 ≠ 0). Otherwise it unloads the old level, streams the new one, turns
  passthrough on only for 7, and fires `OnEnvironmentChanged`; `OnNewEnvironmentLoaded` fires once the level is shown.
  On Android a loading screen goes up 0.1 s before and down 1.5 s after (`TribeGameStateBP.txt:
  SetEnvironment_ShowLoadingScreen`).
- **The menu side** **(read)**. The menu applies an `Environment_*` skin (10 rows in `DT_EnvironmentSkins`).
  `BP_EnvironmentSkin` switches only when the skin's pawn is the host, and saves `[TribeSkins] Environment=`. The
  default is Passthrough where supported, else TribeLounge in VR and LodatoLounge on desktop.
- **Multiplayer.** Skins go `Server_AddActiveSkin` → `Multi_AddActiveSkin`, and every machine applies them by name to
  that pawn; `ActiveSkins` also replicates for late joiners **(read: `Pawn/TribePawnBP.txt`)**.
  - `IsHost` returns the pawn's `bHost`, which is replicated (`CPF_Net`) **(read: `TribePawnBP.IsHost`, the class's
    property flags)**.
  - So the host's pawn passes the check on every machine. Each guest's machine applies the host's environment skin
    and switches itself **(read link by link; not watched end to end)**.
  - A mod that replaces a stock level path is therefore seen only by players who have the mod **(inferred)**.
- **Per-environment pawn settings** **(read)**. Android near clip is 0.1, except HipHop 1 and Pioneer 8; VideoSphere
  leaves it unchanged. Avatar lighting comes from tuning tables keyed by level name.

### What each level does

- **The shared call.** Every level Blueprint calls `SetupEnvironmentBackdrop(BackdropMesh, BoothSpotlight,
  BackdropSpotlight, RoomSkylight, LightDimFactor)` on BeginPlay **(read)**. NOTES.md lists other arguments; these are the
  real five. The call reads the two lights' current intensities, and on Android refreshes the rig's lighting cache 1 s
  and 2 s later.
- **No beat reactions.** No level Blueprint reads BPM, beats or audio. Motion comes from media players and level
  sequences **(read)**.

| Enum | Level | Wall | Dim | Level Blueprint does | Placed (selection) |
|---|---|---|---|---|---|
| 1 Lounge | Environment_TribeLounge | SM_DefaultDJRoom_Screen_9 (-82.08,113.04,0.21) | 0.8 | passes AvatarSpotLight as the booth light | DJRoom_Table (-5.42,39.62,0.21), room sections |
| 2 Desert | Environment_Desert_Optimized | SM_BackdropScreen | 0.8 | wall only | desk, speakers, skybox, plants |
| 3 Void | Environment_Void | SM_BackdropScreen (0,0,-30) | 0.8 | wall only | 3 spotlights, directional, skylight, chroma screen |
| 4 Lodato | Environment_LodatoLounge | SM_BackdropScreen_32 (0,206.1,66.8) ×0.55 | 0.7 | wall only | 10 spotlights, booth (0,157,-22) |
| 5 PolygonCity | Environment_PolygonCity | Screen2_2 (-5.8,474.85,184) | 0.8 | wall only | 62 point lights, Table_2 (-3.38,-7.48,-9.94) |
| 6 HipHop | Environment_HipHop | backdrop_screen (-10,311,73) | 0.8 | plays `MS_HipHopRideVideo`; Android hides 2 spots | wagon (-9.1,-65,0), `ActorGroundMotion` sequence, stage01-08 along -Y to about -300,000 |
| 7 Passthrough | Environment_Passthrough | SM_BackdropScreen (0,0,-30) | 0.8 | `SetRootAnchorHandleActive` on/off | as Void |
| 8 HotelSelina | Environment_HotelSelina | SM_ArchScreen (0,0,-82) | 0.8 | plays balloon sequence + `MS_HotelSelinaVideo`; mobile atlas on Android | 29 point / 18 spot, SM_SelinaTable (0,30,0) |
| 9 Pioneer | Environment_Pioneer | backdrop_screen (-10,250.6,7.06) | 0 | plays two `MS_Powerstation_*` videos | `ActorGroundMotion`, 77 spot / 10 point, PDJ_Table_2 (0,37.6,-8.9) |
| 10 VideoSphere | Environment_VideoSphere | None | 0.8 | lights only | TribeVideoSphere (-10,-50,1290) |

All rows **(read: `Maps/Environments/*.txt`)**. Pioneer's dim factor of 0 blacks out its booth light and skylight
whenever visuals play. The ride sequences aren't started in their level Blueprints, so they must autoplay
**(inferred)**.

## The video-call stage

- **What it is.** `ATribeVideoCallManager` runs an Agora call with RTM messages. Channels come from `GET
  …/videocall/channels` on the mixreality backend **(read: strings in `TribeXR.TribeVideoCallManager.c`)**. The
  encoder (848 × 480 at 15 fps) is in `claudedocs/stream_quality_notes.md`.
- **Roles.** Priority is OnStage 32, InCrowd 128, Spectator 192 **(read: `W_VideoCallMenu.txt: JoinCall`,
  `JoinWorkshop`, "Start Video Call")**. Your own channel gives 32, spectating 192, otherwise 128. The workshop is
  channel `workshop` in mode 3 (Mentor 32, Student 128). A host starts at 32 on a Public channel named after them, or
  picks `workshop`, `lounge` or `support`.
- **Modes** **(read)**. Channel: None, Public, Private, Workshop, Support, Lobby. `E_RoomType`: None, VideoCall,
  Workshop, Support, Room, RoomAndChannel. Privacy: Public, Private, Disabled.
- **Stage queue** **(read: `W_VideoCallStageQueue.txt`, `W_VideoCallMenu.txt`)**. Staging modes are Open, Closed,
  Queue and QueueClosed; the button toggles Open ↔ Closed and Queue ↔ QueueClosed. Per-set timers are 30, 60, 120, 180,
  240, 300, 480, 600, 900, 1800 or 3600 s, with a "Starting In {Seconds}" countdown. The panel adds, removes, advances,
  plays/pauses and resets; `SetStageQueueTimerSeconds` applies only after an access check (moderator, inferred).
- **Moderation** **(read)**. `BanUser` needs `bIsModerator`. `MuteUser` toggles a muted set and sends "mute" or
  "unmute" with the user id. Room kicks go through `TribeGameModeBP.KickPlayer`.
- **Outputs** **(read)**. Audio: Disabled, Silence, Master, MasterWithVirtualHeadphones, Mic, MicAndMaster,
  MicAndMasterWithVirtualHeadphones. Video: None or SpectatorCam.
- **RTMP** **(read: `GetRtmpUrls`)**. `RtmpUrl` is the Twitch ingest, when Twitch streaming is on, you're logged in
  and a key exists. `AltRtmpUrl` is the custom URL, when that setting is on and the URL isn't empty. Both go to
  `StartCallWithParameters`, so both can stream at once.

## Twitch

- **Login.** OAuth at `id.twitch.tv` redirects to `https://mixreality.tribexr.com/twitch/` with scopes `openid
  chat:read chat:edit channel:read:stream_key`. The alternatives are `/twitch/alt-login` or a pasted `AccessToken=`
  **(read: `TribeXR.TribeTwitchManager.c`)**.
- **Ingest:** `rtmp://sfo.contribute.live-video.net/app/` + the key **(read: `GetIngestUrl`)**.
- **Chat.** It uses IRC (`PRIVMSG #%s`, `PART #%s`), and `ChatChannel` is replicated **(read:
  `GetLifetimeReplicatedProps`)**. Room guests probably join the host's chat and run commands locally, so a `!gif`
  would appear on every wall **(inferred; what a client does on receiving `ChatChannel`, `FUN_050e457c`, wasn't
  read)**. The panel keeps 64 messages, and the viewer count arrives with `OnStreamInfoUpdated`
  **(read: `W_TwitchChat.txt`)**.
- **Commands** (`Twitch/BP_TribeTwitchManager.txt: HandleCommandString`) **(read)**. They start with `!`, split on
  spaces and ignore case; only the host replies. A command with the wrong number of words is ignored, so a multi-word
  `!request` does nothing. The gif/vid and cam checkboxes are saved as `[ChatCommands] gif/cam` and are on until first
  saved.

| Command | Effect |
|---|---|
| `!nowplaying` | posts `[channel] title` for each playing deck, joined by ` \|\| ` |
| `!gif <url>`, `!vid <url>` | needs `https://media.giphy.com/…`; `.gif` → `DownloadGifFileToBackdrop`, else → `StreamVideoToBackdrop` |
| `!cam <n>` | `SetSpectatorCamByIndex(n − 1)`: any viewer can switch the stream camera |
| `!request <word>` | adds to the request panel while requests are open |

- **Emotes.** Each emote is fetched from `static-cdn.jtvnw.net` at × 2.0, spawned at rig + (±80, -34, 40) at scale
  0.25, and drawn on the wall **(read: `DisplayEmote`)**.

## Achievements

- **Rules** (`Achievements/BP_AchievementsManager.txt`) **(read)**. A tier unlocks when progress equals a step
  exactly. Single-step rows pay `Points`; tiered rows pay round(Points × step), or Points × step / 60 for minute
  counters. Daily rows reset 1 day after they were earned. A track is "mixed in" when its deck starts while another
  deck plays, and a 60 s timer counts mixing minutes.
- **Daily:** JoinVideoCall 500 (or HostVideoCall 800 for a moderator) at call start, JoinMultiplayer 100 and
  HostMultiplayerRoom 800 from session state, JoinWorkshop 1000, and FirstLivestream 200 when the stream goes live.
- **One-time** (ImportGifs counts only the GIF `Downloads` folder; ImportVideos counts My Videos):

  | Points | Rows |
  |---|---|
  | 10 | UpdateDeckScale, LoadTracks |
  | 100 | StarterTutorial, TribeOG (hidden until earned), CreateWebProfile, DownloadTrackPack, ConnectDropbox / Tidal / Soundcloud / Beatport / Twitch, DownloadVisualsPack, ChangeEquipment, ChangeEnvironment |
  | 200 | CustomizeAvatar, JoinDiscord (5 s after the Help link), ImportGifs, PlayDanceGame, RecordMix |
  | 500 | ImportVideos, CompleteLessons (16) |
  | 1000 | 5DayDJChallenge |

- **Tiered** (points; steps): UniqueTracksMixed (10; 10 to 2500), TracksMixed (2; 10 to 10000), TracksMixedLive (50;
  10 to 10000), TotalMixingHours (100; 60 to 600000 min), TotalStreamingHours (1000; 60 to 600000 min), LiveDJMix
  (800; 15 to 1440 min of mixing while live) **(read: `DT_TribeAchievements`; triggers from the `SetAchievementValue`
  call sites)**.

## OSC, MIDI, Metaverse, Discord, NDI

- **OSC** is the virtual APC40 driving Resolume. It sends to 127.0.0.1:7000 and listens on 127.0.0.1:7001 (config
  `[OSC]`), with addresses like `/composition/layers/{n}/dashboard/link{Channel}`. An incoming message reaches a control
  only while it's grabbed **(read: `OSC/BP_OscManager.txt`, `Equipment/APC40/*`)**.
- **MIDI.** Devices open only while Tribe Pro is active. Control ids map to deck controls via `HandleMidiEvent(0 on /
  1 off / 2 CC, …)`. Android drops the MIDI-controller skin **(read: `TribeMidiManager.c: HandleSubscriptionUpdated`,
  `MIDI/BP_TribeMidiManager.txt`)**.
- **Metaverse.** The dance game spawns `BP_Metaverse` **(read: `Metaverse/BP_Metaverse.txt`, `MetaverseActor.c`)**.
  While broadcasting, it polls the sync master's `GetCurrentBeatInt` every tick and sends `RespondToBeatSignal(BPM,
  beat, time)` on each change, plus a BPM update when a track plays. The messages (beatSignal, BPMChange, TrackChange,
  PoseChange, beatSpectrumAnalysis) go out on "metaverseStream" through a video-call helper (inferred from its address).
- **Spectrum analyzer** (CommonLevel) **(read: `TribeSpectrumAnalyzer.c`)**. It analyses 12 bands at 50, 100, 200,
  400, 800, 1600, 2400, 3200, 5000, 8000, 15000 and 18500 Hz. Running maxima decay × 0.1, within [1e-05, 9999.0]. It
  follows the sync master's beat and exposes `OnBeatEvent` and `GetFrequencyResults`.
- **Discord.** The Blueprint sets "In Room - {Genre}", the party id, size and max. Every native setter calls the empty
  stub, so nothing happens on Quest **(read: `TribeDiscordManager.c`)**.
- **NDI** is an input, received into `VT_NdiInputLeft` and shown with `MI_InputSourceBackwall` **(read)**.
  `FindNdiComponents` returns 0 on this build, and the media list's NDI entry (+0x340) is never written in the
  decompiled file. So it's likely unusable on Quest **(inferred)**.

## Hooks for a custom stage

- **Register your wall.** Call `SetupEnvironmentBackdrop` from your level's BeginPlay with your wall, booth light,
  backdrop light, skylight and dim factor. Tribe then drives slot 0 of the wall and colours the backdrop light. It
  forgets the wall only when the environment unloads to None **(read: `ClearEnvironmentBackdrop`)**.
- **Use Tribe's sources in your own materials:** `MPC_VideoBackdrop` (Tile, Mirror, StretchMode, Aspect),
  `RT_BackdropCanvas`, `RT_BackdropCanvasText`, `BackdropMediaPlayer_Video` **(inferred: plain global assets)**.
- **Beat** (all read). Read deck `GetBpm`, `GetSecondsToNextBar` and `GetCurrentBeatInt`, with phase = 1 −
  frac(SecondsToNextBar · BPM / 60). Catch new-beat edges as `BP_Metaverse` does, or use
  `TribeSpectrumAnalyzer.GetFrequencyResults` and `OnBeatEvent`.
- **Events** (read): `TribeGameState.OnNewEnvironmentLoaded`, `OnDeckTrackChanged`, `PlayModeChanged`,
  `TribeTrack.OnTrackPlayed`.
- **Cameras.** Spectator cameras 1-4 are in CommonLevel, and `!cam n` picks index n − 1. That the index order matches
  the names is **(inferred)**.

## Visuals, stages and social: not covered or unclear

- **Not decompiled:** `SetPlayMode` (`FUN_0520f2fc`), the GIF re-apply (`FUN_05211070`), the media-open helper
  (`FUN_0520f610`), and the C++ defaults of `BeatsPerLoop`, `MaxGifsDownloading` and `bSaveGifDownloads`.
- **Not decoded:** the ring and chroma colours (struct literals), and how the canvas maps onto each wall's UVs.
- **Unchecked:** whether visuals packs accept more than `.mp4` (a runtime type list), the viewer-count poll rate, the
  RTM message formats and what bans send, how `OnBeatEvent` fires, and whether the 0.25 s analyzer timer is the decay
  timer.
- **Skipped:** the room-browser widgets (`W_VideoRoomList`, `W_SocialRoomItem`, `W_VideoLoungePreview`) and
  `TribeVideoCallSchedule`.

## Engine and network settings (`Config/DefaultEngine.ini`, `DefaultGame.ini`)

- **Maps and classes:**
  - the game starts in `StartMap`;
  - a host loads `DJRoomMap` (`ServerDefaultMap`);
  - the game instance is `TribeGameInstanceBP`;
  - the game mode is `TribeMainGM`.
  - `MapsToCook` lists StartMap, DJRoomMap and eight environments: Desert_Optimized, LodatoLounge, PolygonCity,
    HipHop, Passthrough, VideoSphere, HotelSelina and Pioneer.
  - TribeLounge, Void and `Levels/CommonLevel` aren't in that list but ship in chunk 0 too. Probably something
    references them **(inferred)**.
- **Rendering:**
  - forward shading, instanced stereo, mobile multiview (direct);
  - 2x MSAA (`r.MSAACount=2`, AA method 3), `vr.PixelDensity=1`;
  - no mobile HDR, no texture streaming, no occlusion queries, no movable spotlights on mobile;
  - static lighting allowed; motion blur, auto exposure and lens flares off.
- **Online:**
  - `DefaultPlatformService=EOSPlus`: Epic Online Services paired with the Oculus platform;
  - the game net driver is `NetDriverEOS` (EOS peer-to-peer), with `IpNetDriver` as the fallback;
  - `MaxClientRate` and `MaxInternetClientRate` are 2,400,000 bytes/s;
  - voice is on (`bHasVoiceEnabled=true`, `bAndroidVoiceEnabled=True`);
  - the Oculus subsystem has its own net driver class (`OculusNetDriver` with `OculusNetConnection`);
  - the Steam subsystem is configured but off in this build (`bEnabled=false`, `P2PConnectionTimeout=90`).
  - The EOS and Oculus credentials in these files are not copied here.

## How it was decoded, and the checks

**Pipeline:**
1. **Unpack.** `repak 0.2.3 unpack` each pak into an empty folder, then merge into
   `D:/TribeUE/tribe_assets/all` without overwriting. All 3,727 files already there were in the new unpack; 400 of
   them compared byte for byte were identical. The paks share no paths.
2. **Mappings.** `uasset_tool augment pulled/TribeXR.usmap D:/TribeUE/tribe_assets/all pulled/TribeXR_full3.usmap`.
   It adds 246 Blueprint classes/structs and 2 enums from the assets' own class exports. 0 parents are missing.
3. **Read.** `uasset_tool inventory` and `dump` with `TribeXR_full3.usmap`. `scripts/uasset_tool` now also reads
   `.umap` levels, which it used to skip.
4. **Print.** `scripts/code_print.py <dump dir> <code dir>` writes the pseudo-code (via `scripts/kismet_print.py`),
   tables, structs, enums and placed actors.
5. **Saves.** `scripts/gvas_print.py <Replays dir> <out dir>`.

**Checks**, each by a second route:
- **The tool change.** The rebuilt `uasset_tool` re-inventoried Equipment identically to the earlier
  `inventory_after.tsv` (837 rows, once line endings are normalised).
- **The printer.** `code_print.py` reproduces all 491 non-empty earlier pseudo-code files. The equipment files match
  byte for byte. The others differ only in CRLF line endings and the `var` lines they lacked. The 27 empty files the
  old printer wrote for tables, structs and enums now have content.
- **Function counts.** The functions printed equal the inventory's function count in every folder (8,876).
- **Blueprint-only events.** The hook's runtime dump lists 32 events that Tribe's C++ declares for Blueprints to
  implement.
  - 31 are implemented in the decoded Blueprints.
  - The 32nd, `TribeGameInstance::PreMapTravel`, is implemented nowhere: `TribeGameInstanceBP` (19 functions) has no
    such function.
- **Saves.**
  - All 501 parse with no undecoded values, each ending exactly at the 4-byte object trailer.
  - Every top-level field appears in the class's schema from the runtime type dump.
  - 79 of the 109 control names used as keys match deck catalog names directly. The others are composed per-band
    names (`ChannelEQKnobHighHigh_0`) and deck screen states (`NeedleSearch`).
- **The system sections.** Agents drafted them; I checked them against the code before merging.
  - **Checked against the code:**
    - the GIF beat-match math (`TribeGif.c`);
    - the crowd's numbers and the ten levels' dim factors;
    - 34 achievement rows, the Twitch commands, the OSC defaults and the video-call priorities;
    - 25 lessons and 77 sequences in the DJ challenge;
    - the dance cache (8 maps, 125 BPM) and the onboarding tempo (62).
  - **Read in Ghidra, because the drafts had inferred or assumed them:**
    - the three visuals-wall event stubs, from the FName globals they look up;
    - `bHost`'s replication, which is how guests follow the host's environment;
    - `BeatFrequency`'s default (1.0, from the constructor);
    - the judge ignoring the control's value, and its floor rounding. The draft had assumed truncation and listed
      lopsided windows.
- **The C++ effects** (`mixer_effects.md`, `superpowered_dsp.md`). Checked by a second route:
  - the Phaser's tempo bug (the dispatcher's step formula, plus the per-sample code advancing the LFO twice per frame);
  - that no mixer offers Shimmer, Slip Loop, Megaphone or Vinyl Brake (every `AvailableBeatFX` list in the
    Blueprints);
  - the reverb's Freeverb lengths (written in sequence in the SDK's constructor);
  - a rerun of `inrp_print.py` over all 126 replays.
- **Mislabelled C++ helpers.** Nine engine helpers carried Tribe names in the decompiled C (for example FName's
  constructor appeared as `TribeBeatHighwayLane__SetupLane` at 253 call sites). They are renamed; the table is in
  `native_summary.md`.
