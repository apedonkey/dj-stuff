# Our own VR DJ game: plan

The idea, in your words: Tribe's rooms, but "for an entire venue and be able to walk around". The audio and decks
should be "as close as tribe does", and the Quest should stay smooth "with all the people in the venue at once.
Especially with all the lights and audio going."

Written 2026-10-27 from the Tribe notes in this folder and a round of web research (sources at the end). Nothing is
built yet.

How claims are marked:
- **(checked):** I looked at it myself, on this PC or the headset.
- **(read):** from Tribe's decoded code or a cited page.
- **(derived):** arithmetic on those.
- **(assumed):** not verified; the text says what would check it.

## The short version

1. **Engine:** Unreal, using Meta's Quest branch of it (the "Oculus-VR fork"). Its 5.4.4 version is already built on
   this PC (`D:\MetaUE54`), and our stages are cooked with it.
2. **Audio:** our own deck engine, built from open-source parts. Tribe's audio SDK (Superpowered) can no longer be
   licensed.
3. **How the crowd hears the DJ:**
   - Only the DJ's headset runs decks.
   - It streams its mix to the server at music quality, and the server sends it to everyone.
   - The light cues ride on the same stream, so they land on the beat for each listener.
4. **People:** the people near you are full avatars. The far crowd is drawn as instanced dancers, like our stage
   crowds, and sends much less over the network.
5. **Online:** Unreal's built-in multiplayer runs the game. Epic Online Services (free) handles lobbies and voice
   chat.
6. **Order:** five phases. Each ends with a test on the headset that passes or fails. The audio engine comes first,
   because everything rests on it.

## What changed since I suggested Superpowered

- **Superpowered is closing** **(read: its farewell page)**:
  - it has stopped issuing new licences;
  - it will cease operations on July 31, 2027;
  - existing customers only get prorated renewals.
  
  So "license what Tribe uses" is off the table.
- **Its successor is Yuby,** being built by Gabor Szanto, who made the DJ app DJ Player Pro.
  - There's no public product page, price or release date. The farewell page says to contact him **(read)**.
  - Worth one email, but this plan doesn't depend on it.

## The audio engine

### What Tribe does (from our notes)

- **Its own audio output.** Tribe's decks and mixer run inside Superpowered with their own audio output, not
  Unreal's sound system. In an earlier probe, two OpenSL ES audio streams stayed up after Unreal's sound was switched
  off with `-nosound` **(checked: NOTES.md)**.
- **The signal path,** for each block of audio **(read: `cue_tracks_menus.md`)**:
  1. inputs and trim;
  2. channel FX, EQ and filter;
  3. faders and crossfader (the cue is tapped before them);
  4. Beat FX, send FX and master;
  5. main out and headphone out.
  
  The headphone mix is `cue × clamp(1 − MIX) + master × clamp(MIX + 1)`.
- **The room and the cue.** In VR, the main mix plays from two virtual booth monitors placed around your head. The
  hand-to-ear gesture puts a headphone on one ear. The cue joins that ear, and Headphone Isolation muffles the room
  there **(read)**.
- **The rest:** effect settings are in `mixer_effects.md`. Every deck and mixer control is in `deck_catalog.md`.

That is our spec: what to build, not code to copy (see "Tribe, Pioneer and music rights" below).

### Our parts

| Job | What we'd use | Licence | Notes |
|---|---|---|---|
| Key lock (tempo changes without pitch changes) | **Signalsmith Stretch** | MIT | Best between 0.75× and 1.5× speed. Quality is compared to Rubber Band, which is GPL or paid **(read)**. A DJ tempo fader (±8 to ±16 %) is well inside that range. |
| Key lock, second choice | **Bungee** | MPL-2.0 (also a paid Pro version) | About 20 ms from a speed change to hearing it **(read)**. MPL means we publish only our changes to Bungee's own files. |
| Scratching and vinyl mode | plain resampling, key lock off | ours | |
| Mixer: faders, crossfader, cue bus, headphone MIX and LEVEL | ours, from the Tribe notes | ours | the formulas above |
| EQ, filter, Color FX, Beat FX | ours | ours | standard designs. Tribe's ranges and steps are in `mixer_effects.md`. |
| Sound out of the DJ's headset | **Oboe** (Google) | Apache-2.0 (a mirror lists it; check the LICENSE file) | Picks AAudio or OpenSL ES, whichever performs better on the device **(read)**. |
| Booth monitors and headphone cue | ours, like Tribe | ours | Two monitor sources, muffled on the ear wearing the headphone. |
| Music stream to the crowd | **Opus** | BSD **(assumed: from memory)** | Already inside Unreal: `Engine/Source/ThirdParty/libOpus` in both UE 5.4 installs **(checked)**. |
| Opening MP3, AAC, FLAC and WAV files | Android's built-in decoders, plus a small FLAC/WAV decoder | | to pick in phase 0 **(assumed)** |
| Sound on the crowd's headsets | Unreal's own audio | | The stream plays from the venue's speaker stacks, placed in 3D. |

**Memory.** Tracks are decoded into memory before they play, so seeking and hot cues are instant **(design choice)**.
A 6-minute stereo track at 44.1 kHz, 16-bit, is about 63.5 MB, so four decks need about 254 MB **(derived)**.

**Songs.** Phase 0 uses your songs with the analysis files we already make: BPM, beat grid and sections, about 1,775
songs in `TribeUE/Songs/cues`. Analysing a new song on the headset comes later.

### Measured: key lock on your Quest 3 (2026-10-27)

`scripts/keylock_bench.sh` ran four stereo decks through Signalsmith Stretch on the headset at +8 % tempo **(checked;
log `logs/keylock_bench_20261027_083325.txt`)**.
- It works block by block like a real audio callback: 256 frames at 48 kHz, so a block is due every 5.33 ms.
- "Load" is the time spent on all four decks, as a share of those 5.33 ms, on one core.
- "Delay" is how long a tempo change takes to be heard. A deck reads ahead in its own track, so only the stretcher's
  output delay counts **(derived)**.

| Setting | Delay | Average load (fast / slow core) | Worst block (fast / slow) |
|---|---|---|---|
| Default (120 ms window) | 60 ms | 7.4 % / 8.7 % | 48 % / 60 % |
| Default, computation spread out | 90 ms | 7.8 % / 9.0 % | 16 % / 18 % |
| Cheaper preset (100 ms window, spread) | 90 ms | 5.3 % / 6.1 % | 10 % / 11 % |
| 60 ms window, spread | 45 ms | 7.8 % / 9.1 % | 14 % / 14 % |
| 40 ms window, spread | 30 ms | 7.4 % / 8.6 % | 11 % / 12 % |

- **Every block was on time:** none of the 3,750 blocks in any run went over its 5.33 ms.
- **The cores:** cpu2–5 run at 2.36 GHz and cpu0–1 at 2.05 GHz **(checked)**.
- **Tempo direction:** slowing down by 8 % costs the same as speeding up.
- **The spikes:** without spreading, the worst blocks come every 30 ms. That's when the decks compute their next
  spectral frame, all four in the same block **(inferred)**. Staggering the decks could cut the spike without the
  extra delay **(untested)**.
- **Caveat:** the cores ran at full speed during the test, because the headset was asleep and nothing else was
  running. In a VR app the system can hold the CPU lower **(assumed)**. Even at half speed, the spread-out default
  would average 16–18 % of a core, with the worst block about a third of the budget **(derived)**.
- **What it means:** key lock's CPU cost isn't a problem for four decks. What's left is choosing a window size by ear.
  Shorter windows add less delay but usually hold low bass less steadily **(assumed; a listening test decides)**.
- **Peaks rise:** in the listening test, stretching raised the peaks by 3.1–3.6 dB while the loudness stayed the same
  (average −11.8 dB against −11.9 dB) **(checked)**. So the master needs headroom or a limiter. Tribe has an output
  limiter **(read)**.

### Why only the DJ's headset needs the fast path

The DJ has to hear a fader move or a jog nudge straight away. Listeners don't.
- If the whole show reaches them a fraction of a second late, nobody can tell, as long as the lights are late by the
  same amount.
- So only the DJ's headset runs Oboe and the deck engine.
- Everyone else plays a stream through Unreal's normal audio, which also gives them 3D speakers, distance and room
  echo without extra work.

## How the crowd hears the mix

| | Tribe: every headset plays the tracks | Ours: the DJ streams the mix |
|---|---|---|
| Song files | copied to every listener who doesn't have them **(read: `FileTransferComponent`)** | never leave the DJ's headset |
| Streaming services (Beatport, SoundCloud, Tidal) | each listener needs their own account, or sees "service required" **(read)** | only the DJ needs one |
| Sound quality | lossless, played on each headset | Opus at 128 kb/s, which Opus's own guide calls "pretty much transparent" for stereo music **(read)** |
| Data per listener | the song files | about 58 MB an hour **(derived from 128 kb/s)** |
| Delay behind the DJ | about none: events are scheduled on a ping-corrected server clock **(read)** | a fraction of a second **(assumed: a jitter buffer; phase 2 measures it)** |
| Headsets running a deck engine | all of them | only the DJ's |

**Lights on the beat for everyone.**
- The DJ's deck engine numbers every audio sample it sends.
- Each light cue carries the sample number it belongs to: beat, bar, drop, section (from our cue files), filter
  sweep, FX on or off.
- A listener's headset fires the cue when that sample plays.
- So the lights land on the beat for every listener, whatever their delay.
- The DJ's own lights fire straight from the engine, with no delay.

**The DJ's avatar** should reach listeners with the same delay, so a hand hitting play lines up with the sound
**(design idea)**.

**Why not a voice-chat service for the music:**
- Voice services are tuned for speech **(assumed for EOS voice; its music settings weren't checked)**.
- Agora has a music profile (48 kHz stereo, up to 128 kb/s) **(read)**. But it's paid per minute **(assumed: pricing
  not checked)**, and it doesn't give us the sample numbers the lights need.
- Our own Opus stream costs only server bandwidth.

**Back-to-back sets.** A second DJ in the booth needs low delay too.
- Inside the booth, we'd use Tribe's approach: both DJ headsets run the decks, with track transfer and synced
  controls.
- The crowd still gets the stream.
- That's a later phase.

## Keeping the Quest smooth with a full venue

**What we already know works.**
- Our stage crowds are instanced dancers with baked animation.
- Graveyard Shift's crowd is about 4,250 dancers and 330k triangles (our build numbers).
- Harvest Moon v3, with 4,047 dancers, ran at 71–72 fps on its first launch on your headset, inside Tribe, with
  Tribe's decks running **(checked: 2026-10-18 log)**.
- The drone-camera shots over the whole crowd stuttered.

**Real players cost more than dancers.** Each one moves from live head and hand tracking, so each needs its own
animation and its own network updates. The plan splits them:
- **Near you** (the closest 16 or so; phase 3 tunes the number): full avatars, with head and hands sent 20 times a
  second.
- **Everyone else:** drawn as instanced dancers, like our crowds. Each sends only its position, facing, dance move and
  energy, twice a second.

**Network estimate (derived).** It assumes about 40 bytes per update for a near player and 8 for a far one. Phase 3
measures the real numbers.

| People in the venue | Each headset downloads | The server sends in total |
|---|---|---|
| 50 | about 107 kb/s of people + 128 kb/s of music | about 5.3 Mb/s + 6.4 Mb/s |
| 200 | about 126 kb/s + 128 kb/s | about 25 Mb/s + 26 Mb/s |

Without the split, 200 people would need about 1.3 Mb/s per headset and about 255 Mb/s from the server
**(derived)**.

**Voice chat:** spatial, by distance, so you hear the people near you. The music doesn't duck: Tribe lowers the music
when someone talks **(read)**, which would wreck a venue.

**Lights:**
- Our stages already drive their light shows from a "show bus" of material parameters (the `MPC_*Show` collections in
  our stage builds).
- In our own game, the deck engine writes those parameters directly, so the stage content carries over.

**The frame budget:**
- In our own game, no Tribe systems share the frame.
- Meta's Quest branch adds performance features: Late Latching, Software Occlusion Culling, and Application SpaceWarp
  in stable releases **(read: Meta's compatibility page)**.

## Online

- **The game itself:** Unreal's built-in multiplayer (replication). Tribe uses the same: its deck loads go through
  `Server_…` and `Multi_…` calls **(read)**.
  - **Phase 2** (up to about 10 people): a PC or the DJ's headset hosts the session.
  - **From phase 3:** a dedicated server.
    - Building one needs Unreal compiled from source, not the Launcher version. `D:\MetaUE54` is one.
    - A Linux server also needs Epic's cross-compile toolchain **(read: Redpoint docs, Unreal Community wiki)**.
  - **Many players:** Unreal's Replication Graph or Iris **(assumed: check which is ready in the engine version we
    pick)**.
- **Lobbies, friends and voice chat:** Epic Online Services.
  - Voice and lobbies are free and work across platforms. Voice goes through Epic's servers **(read: Epic's
    announcement)**.
  - Quest support is claimed by a third-party plugin, EOS Integration Kit **(read)**. Epic's own docs weren't checked
    for Quest.
- **Store login and ownership check:** Meta's platform SDK. Tribe has session code for Oculus, Steam and standalone
  **(read)**.
- **Alternative: Photon.**
  - Its Unreal SDK (Fusion 3) is listed as current in July 2026. Its voice product's docs are Unity-first **(read)**.
  - Unreal's own multiplayer plus EOS covers what we need, so Photon is a fallback.

## Engine and this PC

- **Meta's Quest branch of Unreal is already built here** **(checked: its `Build.version`; the tag is from
  `claudedocs/GUIDE.md`)**:
  - `D:\MetaUE54` is a source build of Meta's UE 5.4.4 fork (branch `Partner-Oculus-UE5`).
  - Its tag is `oculus-5.4.4-release-1.103.0-v71.0`, the same engine Tribe runs.
  - Our stages are cooked with it.
  
  What that settles:
  - The Meta, Epic and GitHub account linking the fork requires is already done.
  - A source build is proven on this PC. A dedicated server needs one, so this build can add the server target when
    phase 3 needs it.
  - Our stages are already in this engine's format, so phase 1 needs no upgrade.
- **Start on it.** Phases 0 and 1 use `D:\MetaUE54`. The deck engine is our own C++ in a plugin, so it can move to a
  newer engine later.
- **Newer releases exist** **(read: Meta's page, updated 2026-09-24)**:
  - Meta's page names tags like `oculus-5.7.4-release-1.205.0`; newer tags end in `-release-v205`.
  - It says to pick the highest Meta XR version for your engine version.
  - Moving up is optional. It means a new source build, plus upgrading our stages **(assumed: they upgrade when
    saved)**.
- **Epic's Launcher UE 5.4** (`C:/Program Files/Epic Games/UE_5.4`) can't build a dedicated server and lacks the fork's
  Quest performance features, so it isn't the game's engine.
- **This PC** **(checked)**: 6-core i5-9400F, 32 GB RAM, GTX 1660 SUPER. D: has 254 GB free, C: has 135 GB.
  - A source build of a newer fork would take hours here **(assumed)** and a lot of disk and memory.
  - Limit the parallel compile jobs: on this PC the limit is Windows commit, not RAM (see the commit-limit notes).
- **Building for the Quest** **(checked 2026-10-27)**:
  - Unreal has never packaged a Quest app on this PC: `D:\MetaUE54` has no Android build files.
  - The fork's `Engine/Config/Android/Android_SDK.json` wants NDK r25b (r25b–r26c accepted), Android platform 33,
    build-tools 33.0.1 and CMake 3.22.1. Its Gradle 7.5 and Android plugin 7.4.2 need Java 17.
  - The PC has the 2020 set used to sign mods: Android Studio 4.1 (Java 8), platform 30, build-tools 30.0.3, no
    cmdline-tools. It also has NDK r26d in `out/` and Java 21 as `JAVA_HOME`.
  - One-time setup: install those versions, run `Engine/Extras/Android/SetupAndroid.bat`, and set Unreal's own Java
    location (`JavaPath` in its Android SDK settings) to Java 17, leaving `JAVA_HOME` alone.
  - Builds go on the headset as a sideloaded APK over USB, under their own package name, so Tribe is untouched.

## Phases

Each phase ends with a headset test that passes or fails. The targets are my proposals.

### 0. The deck engine (no venue)

- **Done 2026-10-27:** key lock's CPU cost on your Quest 3. It's small: see "Measured: key lock on your Quest 3"
  above.
- **Listening test ready, 2026-10-27** **(checked)**:
  - `scripts/keylock_listen.sh` rendered ICETROUT – CHIMERA at ±8 % with four window sizes, into
    `out/keylock_listen/ICETROUT-CHIMERA/`.
  - The key holds in all of them. The note-content match with the original is 0.998–0.999, against 0.73–0.76 for a
    plain speed-up.
  - Your pick by ear sets the window size. You heard no difference ("it all sounds right"), so the engine uses the
    40 ms window: the shortest delay (30 ms).
- **Deck engine core built, 2026-10-27, in `D:\VRDJ`** (its own repo; see its README) **(checked: 84 checks pass)**:
  - Deck: cue, hot cues, loops, beat jump, tempo, key lock and beat sync.
  - Mixer: Tribe's mixer path and curves, a 3-band isolator, the one-knob filter and a limiter.
  - Sync held within 0.03 ms over 60 minutes (0.31 ms with key lock).
  - Zero heap allocations while rendering.
  - Demo: a double drop of your tracks (Kane & Undertaker into CHIMERA) rendered by the engine.
- **Then:** two decks, the mixer, key lock, and the cue with the hand-to-ear gesture, on the Quest. A test deck with
  Tribe-like controls (`deck_catalog.md`).
- **Pass when:**
  - an hour of four decks with key lock and FX plays with no dropouts;
  - two synced decks are still on the beat after an hour;
  - key lock at ±8 % sounds clean on your dubstep (judged by your ears);
  - fader-to-sound delay is no worse than Tribe's on the same headset, measured the same way on both.
- **Why first:** it decides everything else about the audio.

### 1. One venue, one player

- Graveyard Shift or Reactor in the new project: walkable, our own decks in the booth, the light show driven by the
  deck engine.
- **Pass when:** 72 fps with the full show, and you play a full hour set.

### 2. The DJ plus up to 10 listeners

- The music stream, light cues on its sample numbers, avatars, voice chat and lobbies (EOS).
- **Pass when:**
  - the lights land on the beat for every listener;
  - the stream has no dropouts over an hour;
  - the DJ's frame rate doesn't drop.
- **Stage access** (the user, 2026-10-28: "a way to limit who is on stage physically ... so the crowd can't just
  come up to the decks without permission"):
  - The stage and booth are a closed zone. Only players the DJ lets up can walk or teleport into it; for everyone else
    the walk map ends at the stage edge, and the gear ignores their hands even if they reach it.
  - Asking and allowing: a crowd player can ask to come up; the DJ (the host) allows, declines or sends someone back
    down at any time, from the player list. Players let up can play the decks (back to back). The DJ-only browser
    window stays per DJ.
  - Tribe does the same through a replicated per-player staging state (`ETribePlayerStagingState`, four values, on the
    player state with `OnStagingStateChanged`), and its online player list has a "promote to stage" control (read:
    W_OnlinePlayerListItem, TribePawnBP, W_VideoCallMenu in the decoded Blueprints). Read its four states and their
    rules before building ours.
- **Gear size and height per player** (the user, 2026-10-28: "i should be able to adjust them. also other users might
  want to do that too"). The BOOTH page's SIZE (100-160 %) and HEIGHT are each player's own saved settings. When two
  DJs share the booth (back to back), settle how both fit: each DJ seeing and touching the gear at their own size
  (local only), or the DJ at the decks setting it for everyone. Check what Tribe does first (its EquipmentScale and
  table height are per-player settings; how they replicate wasn't read).
  - **Decided (the user, 2026-10-28):** "the decks would be set for both. it depends on what the host has set them up
    to". The host's SIZE and HEIGHT apply to the shared booth for every DJ on it; a guest's own settings apply only in
    their own sessions.

### 3. A full venue

- A dedicated server, the near/far split, and the far crowd as dancers.
- **Pass when:** 50 simulated players (run on a PC) keep each real headset at 72 fps, and the server's traffic matches
  the estimate above.

### 4. Store release

- The Meta Horizon Store, as Early Access first.
- Steam (PC VR) later is possible: Tribe ships on both **(read: its Steam session code)**.

## Backlog (the user's notes for the game itself)

- **A microphone you can pick up** (the user, 2026-10-29): "include a microphone for all levels that i can pick up. if i
  pick it up, just enable the mic button so i dont actually have to press it, if i put the mic down on the table or if
  im not holding it, make the mic turn off. make the mic slightly glow if the button is on".
  - A handheld mic in every venue, resting on the booth table. Picking it up turns the mixer's MIC on; letting go or
    putting it down turns it off. The MIC button follows (lit while held). The mic glows softly while it's on.
  - First the mic has to carry sound: today the MIC button only switches the mixer's mic channel (its LED, EQ and
    talkover work in the engine), but the game never opens the headset's microphone. The plugin passes no mic input
    (VRDJAudioCore.cpp renderDevice(..., nullptr)) and the manifest has no RECORD_AUDIO. Needed: the permission, an
    Oboe input stream into the engine's mic channel, and a check that the headset's own speakers don't feed back.
  - Where the mic is heard: the room and the crowd, and the Twitch stream (round 3 asks whether to stream the mic).

## Festival: three DJs (the user, 2026-10-30)

- BIG DUB can have three DJs at once, one per stage. Each DJ's mix is a sound source at its stage. A listener hears every
  nearby DJ, louder the closer they are, fading to silence past a set distance. Walking between stages moves smoothly from
  one mix to the next, so the mixes don't clash.
- **Bandwidth:** a listener near several stages gets several music streams, up to three (about 384 kb/s). The network
  estimate assumed one 128 kb/s stream per listener, so the server numbers go up with this.
- **Lights:** each stage drives its own lights from its own DJ.
- **Voice:** spatial too, by distance (see Online).
- **Decided (the user, 2026-10-30):** a stage with no DJ is silent. A stage carries a decent distance: a DJ is heard
  well across the field, not only up close. The exact distance is tuned in playtesting.

## Shows and menus (the user's idea, 2026-10-30)

- **Everyone starts in TEST ROOM**, alone and private.
- **A SHOWS page on the wrist menu** lists the shows that are live now: the host, the venue and spot, how many listeners,
  and a lock when the show is protected. Pick one to join. START SHOW makes your own.
- **When starting a show,** the host chooses:
  - the venue and spot;
  - the listener limit (up to 10 in phase 2);
  - the lock: open, PIN (4-6 digits typed on the menu, because a full password is hard to type in VR), or private
    (not listed; people join with a code).
- **Host controls:** let a listener in or send them back, kick, mute a listener's mic, and end the show. Stage access
  (see phase 2) applies on top.
- **Listeners** leave with LEAVE SHOW and go back to TEST ROOM.
- **Built on** Epic Online Services lobbies (see Online).
- **Decided (the user, 2026-10-30):** PIN, and all three lock modes. Menus are not on the wrist: one floating menu
  panel, like Tribe's menus (Tribe uses no wrist menus; its panels are opened with B or Y). The left menu button opens it
  (the wrist menu's button today). It reuses the music panel's placement, pokes, pointer, collapse and move. B still opens
  the music panel and Y still recentres, so the menu panel uses the left menu button.
- **Still open:** whether the host approves each join, and whether the wrist menu is removed completely (proposed) or
  kept as an option.

## Wish list for multiplayer (the user's ideas, kept so they aren't lost)

Not planned into a phase yet. Each is an idea the user asked to be written down, with the first things to settle.

- **Players bring their own characters and stages** (the user, 2026-10-28): "for users to import their own characters
  and stages. Obviously there would have to be some restrictions on how big or whatever."
  - Limits per upload: triangles, bones, materials, texture sizes and file size, checked on import with a clear
    pass/fail (like a performance rank), so a crowd of custom avatars keeps every headset at 72 fps.
  - Characters fit our existing path: the Tribe mod already loads glTF characters at run time (skins and detachable
    heads with a triangle budget and a load-and-move check; see the skin build notes in memory). Stages are harder:
    either a glTF scene format with our light-show and screen conventions, or a stage kit for the Unreal editor that
    cooks a pak, as other social VR apps do.
  - Data only, never scripts, so an upload can't run code on other players' headsets.
- **A catalog players can sell in** (the user, 2026-10-28): "have like a catalog if the user wishes to submit at a
  menu or something and if another user wants that stage, they can pay for it and download it. Same with characters."
  - Submitting from a menu, a review step before anything is listed, then browse, buy, download and use.
  - To settle first: payments (the store's in-app purchases and its rules for selling player-made content, and the
    creator's share), moderation (reports, takedowns, age ratings), who owns an upload, and copyright claims.

## Getting it on the store

- **The store:** App Lab has merged into the Meta Horizon Store.
- **Review:** apps pass Meta's technical checks (the VRCs). There's no review of quality or taste **(read)**.
- **Timing:** submit at least two weeks before the planned launch **(read)**.
- **Early Access:** a tag is available **(read)**.
- **Meta's cut:** 30 % was the reported Quest Store fee in 2021–2022 coverage **(read)**. I couldn't find Meta's
  current terms; check the developer agreement.

## Tribe, Pioneer and music rights

This is not legal advice. Get a lawyer's read before a public launch.

- **Tribe's code and files:**
  - Write the new game from our behaviour notes, not from Tribe's decoded C++ or Blueprints.
  - Ship nothing taken from Tribe's app: no models, textures or sounds.
  - Standard mixer behaviour (pre-fader cue, fader and crossfader curves) is how club mixers work, so implementing it
    should be fine **(assumed)**.
- **Decks:** design our own. Tribe's gear includes replicas of Pioneer's decks and mixers, with Pioneer's designs and
  logos.
- **Music:**
  - Streaming a mix to a crowd of strangers is a public performance of every track in it.
  - That's fine for your own productions and for tracks you hold the rights to. Commercial releases need a licensing
    answer before launch.
  - Tribe refuses copyrighted tracks while recording **(read)**. It plays streaming-service tracks through each
    listener's own account, which keeps it from redistributing them **(inferred)**.

## Risks

- **Key lock:**
  - Its CPU cost is measured and small, at full CPU speed.
  - Still open: how it sounds at each window size, the delay it adds to tempo changes, and how fast the CPU runs inside
    a VR app.
- **The stream delay** has to match between the audio and the lights, or the show looks off. Phase 2 measures it.
- **The source build** of Unreal is slow and big on this PC.
- **Music rights** for a public venue are unresolved.
- **The size of the job:** this is a whole game. Each phase ends in something that works and can be tested, so you can
  stop at any of them.

## Sources

- **Superpowered:** [the farewell tour](https://superpowered.com/superpowered-farewell),
  [licensing](https://superpowered.com/licensing),
  [licensing docs](https://docs.superpowered.com/getting-started/licensing/).
- **Key lock:**
  - [Signalsmith Stretch attribution (Qt)](https://doc.qt.io/QT-6/qtmultimedia-attribution-signalsmith-stretch.html);
  - [Signalsmith pitch/time example code](https://github.com/Signalsmith-Audio/pitch-time-example-code);
  - [signalsmith-stretch](https://github.com/Signalsmith-Audio/signalsmith-stretch) (tested: v1.3.2, commit
    `88061fd`) and [signalsmith-linear](https://github.com/Signalsmith-Audio/linear) (tag 0.6.6), both MIT, cloned
    to `out/third_party/`;
  - [Bungee](https://bungee.parabolaresearch.com/).
- **Audio output:** [Oboe README](https://chromium.googlesource.com/external/github.com/google/oboe/+show/refs/heads/1.6-stable/README.md),
  [Meta: platform audio for Unreal](https://developers.meta.com/horizon/documentation/unreal/platform-audio/).
- **The music stream:**
  [Opus recommended settings (Xiph wiki)](https://wiki.xiph.org/Opus_Recommended_Settings),
  [Agora: sound quality best practices](https://docs-beta.agora.io/en/video-calling/best-practices/best-practices-sound-quality).
- **Engine:**
  [Meta: Unreal compatibility matrix](https://developers.meta.com/horizon/documentation/unreal/unreal-compatibility-matrix),
  [Meta XR Interaction SDK for Unreal 205.0](https://developers.meta.com/horizon/downloads/package/meta-xr-interaction-sdk-unreal/205.0/).
- **Servers:**
  [Redpoint: preparing a dedicated server](https://docs.redpoint.games/docs/dedis/preparing_your_game_server),
  [Unreal Community wiki: standalone dedicated server](https://unrealcommunity.wiki/6100e8119c9d1a89e0c31a3c).
- **Lobbies and voice:**
  - [Epic: free voice in EOS](https://www.epicgames.com/site/news/epic-online-services-launches-free-in-game-voice-and-easy-anti-cheat);
  - [EOS Integration Kit](https://github.com/yolohz/EOSIntegrationKit);
  - [Photon: voice with Fusion](https://doc.photonengine.com/fusion/v2/concepts-and-patterns/voice-chat);
  - [Photon product index](https://www.photonengine.com/llms.txt).
- **Store:**
  - [Meta: submit your app](https://developers.meta.com/horizon/resources/publish-submit/);
  - [Meta: app review](https://developers.meta.com/horizon/resources/publish-app-review/);
  - [Meta blog: getting apps ready](https://developers.meta.com/horizon/blog/get-apps-ready-app-lab-meta-horizon-store-meta-quest-developers/);
  - [UploadVR: App Lab merged into the store](https://www.uploadvr.com/quest-app-lab-merged-into-meta-horizon-store/);
  - [TechRadar: Quest store fees](https://www.techradar.com/news/metas-quest-2-game-store-fees-are-turning-it-into-the-metaverses-first-villain);
  - [Meta: the state of VR at GDC 2026](https://developers.meta.com/horizon/blog/gdc-2026-state-of-vr/).
