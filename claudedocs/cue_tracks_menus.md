# Cue headphones, song selection and menus

How Tribe XR (build 2304) does three things:
- the hand-to-ear headphone cue;
- picking a song and getting it playing on a deck (including in multiplayer);
- its menus.

The sources:
- **Blueprints:** decoded to pseudo-code in `D:/TribeUE/tribe_assets/catalog/code/` (the `Pawn`, `Menus`, `TrackManager`,
  `MusicServices`, `Equipment` and `GameModes` folders).
- **C++:** decompiled in `D:/TribeUE/tribe_native/`. See `claudedocs/native_reference.md`.

Everything below was read from that code unless it says **(inferred)**.

## The hand-to-ear cue

### The gesture

The gesture lives in `Pawn/TribeControllers` (each hand) and `Pawn/TribePawnBP` (you).

1. **Hover.** Every frame each hand measures its distance to your head.
   - The "head" is a point 5 cm behind the headset camera.
   - "Near" means within 25 cm (`MaxHeadphoneWornToggleDistSquared` = 625).
   - Crossing that line lights the console's headphone indicator (`OnHeadphonesHovered` → `BP_HeadphoneIndicator`).
2. **Toggle.** Press grab (grip, or trigger where it grabs) with that hand while it's near your head and not on a
   control. That toggles the headphone on one ear.
   - The ear is chosen by **which side of your head the hand is on** (the camera's right vector), not by which hand
     it is.
   - The controller rumbles.
3. **When it works:** only in VR input mode (`ETribePawnInputMode` 0 = VR, not spectator or desktop), and only with
   virtual headphones enabled. They're on by default; only the Demo Mix game mode turns them off. On desktop, the
   "Headphone Toggle Left/Right" inputs do the same.
4. **What it sets.** `TribePawnBP.ToggleVirtualHeadphones` flips that ear, then calls
   `BP_Console.SetHeadphonesWorn(left, right)`. That calls `SuperPoweredLibrary.SetHeadphonesWorn`, which stores one
   flag per ear in the audio engine, and broadcasts `OnHeadphonesToggled` so the indicator shows L, R or off.

### What you hear

This is the SuperPowered module's output function (Ghidra `0x47b5c30`), run for every block of audio.

1. **Two buses.** The mixer renders a **main** bus and a **headphone** bus. How it builds the headphone bus is in
   "Inside the mixer" below.
2. **The room.** The main bus is split into its left and right channels.
   - In VR, each is played from a virtual booth monitor positioned in 3D around your head (the spatializer is on
     only in VR).
   - The monitors sit at (-500, 0, 170) and (500, 0, 170) cm with gain 24 (`BP_Console` "Setup Room
     Spatialization").
   - The listener is your headset camera (`TribePawnBP` "Update Room Spatialization").
3. **An ear with the headphone on** gets two changes:
   - That monitor's spatializer is given the **Headphone Isolation** setting (the engine calls it `Occlusion`), so the
     room is muffled in that ear **(inferred: Superpowered's occlusion parameter)**.
   - The cue bus is added to that ear.
   
   At 100 % isolation the room is removed from that ear completely. Below 100 %, you hear the muffled room plus the
   cue.
4. **Last:** global volume, then the output limiter.
   - The console sets global volume to 2 at setup.
   - It lowers the volume while someone talks on voice chat (`OnVoiceStateChangedDucking` → `StartDuckingAudio`; the
     ducked level wasn't checked).
5. **Split Mono** (Settings) replaces all of this. The left channel carries the mono main mix and the right carries
   mono of everything else. That suits a splitter cable to speakers plus real headphones **(inferred)**.

The settings menu (`W_SettingsMenu`) holds the related options:
- Headphone Isolation, 0–100 %;
- Split Mono;
- Output Limiter;
- audio input and output devices.

### Inside the mixer

This is read line by line from the mixer's render (`USuperPoweredMixer`, Ghidra `0x47aeca8`) and the stage functions
it calls. For every block of audio, in order:

1. **Input:** input routing, the mic channel, then each channel's trim (and compressor).
2. **Cue, if PRE EQ is on:** every channel whose cue button is lit is summed into the cue bus.
3. **Tone:** channel FX, then the three EQ bands and the filter (type, resonance).
4. **Cue, if PRE EQ is off:** the same sum, taken here instead, after EQ and filter.
5. **Faders and crossfader:** each channel's sound is scaled by its fader and crossfader gain. The cue was summed
   before this, so **cue is pre-fader and pre-crossfader**, as on a club mixer.
   - Fader curves (v = 0–10):
     - dB: 0 is −96 dB and 10 is 0 dB, `10^((10 − v)/10 × −96 / 20)`;
     - squared: `(v/10)²`;
     - linear: `v/10`.
   - Crossfader curves (x = −1 to +1):
     - cut: full level until fully across, then 0;
     - constant power: `√((x + 1)/2)`;
     - linear: `(x + 1)/2`.
     
     A channel assigned to A uses −x, one assigned to B uses x, and THRU ignores the crossfader.
6. **Master:** Beat FX, send FX, the master sum (crossfader assign, master FX mix), the master filter and isolator,
   and the mic into the master.
7. **The headphone bus** is:
   ```
   cue × clamp(1 − MIX, 0, 1)
   + master × clamp(MIX + 1, 0, 1)    (only while MASTER CUE is on)
   ```
   - MIX runs from −1 (cue only) through 0 (both at full) to +1 (master only).
   - The master here comes after the master FX and isolator, but before the master level and balance.
8. **Outputs:**
   - main = master bus × balance (left `1 − b`, right `1 + b`, each capped at 1) × MASTER LEVEL;
   - headphones = headphone bus × **HEADPHONE LEVEL**.
   
   These are the two buses the output stage above receives.

Where each control's value lives on the mixer object, for patching:

| Kind | Offset | Control |
|---|---|---|
| per channel | +0x4E0 | input |
| per channel | +0x4E8 | trim |
| per channel | +0x568 / +0x5A8 / +0x5E8 | EQ bands |
| per channel | +0x6B0 | filter |
| per channel | +0x6D0 | send |
| per channel | +0x6F0 | cue |
| per channel | +0x6F8 | fader |
| per channel | +0x718 | crossfader assign |
| global | +0x720 | fader curve |
| global | +0x721 | EQ curve |
| global | +0x730 | MASTER CUE |
| global | +0x734 | master level |
| global | +0x738 | balance |
| global | +0x768 | headphone PRE EQ |
| global | +0x76C | MIX |
| global | +0x770 | headphone LEVEL |
| global | +0x774 | crossfader |
| global | +0x778 | crossfader curve |

## Song selection

1. **The browser.** `TrackManager/W_TrackBrowser` is built from:
   - lists and folders (`W_TrackList`, `W_Folder`);
   - search (`W_SearchSelector`) and sort (`W_TrackSortBox`);
   - track info (`W_TrackInformation`) and an Open Key wheel (`W_OpenkeyWheel`).
   
   Service logins are in `MusicServices` (Beatport, SoundCloud, Tidal, Dropbox). Song requests from other players are
   `W_RequestList` / `W_TrackRequest`. The data behind it is the C++ `TrackLibrary`.
2. **Load button.** `W_TrackList.OnLoadButtonClick(channel)` calls `W_TrackOptions.AttemptTrackLoad`, which checks
   two things first:
   - a copyrighted track is refused while the mixer is recording;
   - if that deck is playing, it asks you to confirm (unless a MIDI controller is active).
   
   Then it calls `LoadTrackToDeck`.
3. **Your pawn** (`TribePawnBP.LoadTrackToChannel`).
   - The host loads directly through the rig.
   - A guest asks the host by filename: `Server_LoadTrackByFilename` or `Server_LoadStreamTrackByFilename`.
   - A Dropbox track from someone else's shared link is refused: "You don't own this Dropbox track".
4. **The rig** (`BP_Rig.LoadTrackToChannel`) passes it to the device on that channel through `TrackLoadingInterface`.
   Only decks implement it.
5. **The deck** (`BP_Deck` `LoadTrack`) sends the load to every headset, by filename:
   - `Multi_OpenTrackByName` for local files;
   - `Multi_OpenStreamTrackByName` for Beatport, SoundCloud, Tidal or your own Dropbox;
   - `Multi_OpenDropboxSharedTrack` for Dropbox when net sync is on. The host first creates a Dropbox shared link.
6. **Each headset** (`BP_Deck.OpenCurrentTrack`) looks for the file in this order:
   1. its own library;
   2. track packs;
   3. for a stream, it opens the stream with **its own** account, and shows "{StreamingService} service required…" if
      it has none;
   4. otherwise `RequestTrackTransfer` copies the file from the player who loaded it (the C++
      `FileTransferComponent`).

## Menus

Every menu, button by button (label, event, what it does, the config key it saves), is in
`claudedocs/menu_catalog.md`. This section is the overview.

- **Two 3D panels**, both owned by the game state:
  - the main menu (`BP_MainMenu` → `W_MainMenu`);
  - the mini menu (`BP_MiniMenu` → `W_MiniMenu` / `W_MiniMenuPanel`).
- **Opening them.** **B** (`Input_Button2_Pressed` from the right controller) toggles the mini menu, through
  `TribePawnBP.InputToggleMenuVisibility` → `MiniMenu.OnMenuVisibilityButtonClicked`. **Y** (the same event from the
  left controller) doesn't: it calls `TribeBlueprintLibrary.ResetOrientationAndPositionKeepHeight` and stops there, the
  recentre (corrected 2026-10-29: `Pawn/TribePawnBP.txt` L18670; `DefaultInput.ini` maps `OculusTouch_Left_Y_Click` to
  "MotionController L Button 2" and `OculusTouch_Right_B_Click` to "R Button 2").
- **Mini menu buttons:** Music (the track browser), Equipment, Visuals, Social, Lessons, Demo Mix, Exit, Close.
- **Main menu buttons:** Home, Settings, Account, Achievements, Leaderboard, Record, Dance Game, Help / How-Tos,
  Announcements, Tribe+, featured content.
- **Other panels:**
  - settings (`W_SettingsMenu`);
  - gear selection (`W_EquipmentMenu`, `W_MixerSelection`, `W_ChannelDeviceSelection`);
  - visuals (`W_VisualsProfileMenu`);
  - rooms (`W_RoomManager`, `W_RoomsList`), friends (`W_FriendsList`), profile (`W_ProfileMenu`);
  - recordings (`W_RecordingsMenu`), lessons and the DJ challenge;
  - the Ready Player Me creator (`W_RPMAvatarCreator`) and the VR keyboard (`W_TribeKeyboard`);
  - onboarding;
  - the deck screens, which are menus too (`W_PlayerDisplay_3000`, `_3000X`, `_FLX4`, `_TribeCDJ`, `_StarterCDJ`,
    `_Vinyl`, `_AcidSynth`, `_DrumMachine`).

## Not covered yet

- **The mixer's effects** (Color FX, send FX, Beat FX, mic FX) are in `claudedocs/mixer_effects.md`. That file
  lists what is still unread inside them.
- **The `Audio` folder:** it holds sound files only, no logic.

## Rebuilding the pseudo-code

1. `repak unpack -i TribeXR/Content/<Folder>` from `D:/TribeUE/tribe_paks/pakchunk0-Android_ASTC.pak` into
   `D:/TribeUE/tribe_assets/all`.
2. `uasset_tool augment pulled/TribeXR.usmap D:/TribeUE/tribe_assets/all pulled/TribeXR_full2.usmap`.
3. `uasset_tool dump pulled/TribeXR_full2.usmap <Content/Folder> D:/TribeUE/tribe_assets/dump/<Folder>`.
4. `scripts/kismet_print.py` on each JSON.
