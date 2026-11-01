# A Tribe-style DJ setup in a VRChat world: what's possible

VRChat worlds are built in Unity and scripted with Udon (UdonSharp). Tribe's own code can't run there: it's Unreal
Engine with a native C++ audio engine. A DJ setup has to be rebuilt in Udon. This page lists what that rebuild can
and can't do, and which parts of our Tribe work carry over.

Marked **(test first)** where it isn't confirmed. Sources are at the end.

## Possible

- **Song picker** over tracks built into the world: a list, search by name, sort. Load to deck 1/2 (or 4 decks).
- **Link tracks:** links pre-set in the world, or typed in by visitors (sites on VRChat's allowlist). They play
  through VRChat's video player, so they can't take EQ or effects (see below).
- **Transport:** play, pause, cue and hot cues (jump to stored times). "Jump to drop" cues can come from our
  section markers.
- **Tempo fader and a Sync button,** using each song's stored BPM and first beat. Sync sets the speed ratio and lines
  up the beat. Two decks on one headset then stay locked. **(test first:** that Udon can set a track's playback
  speed**)**
- **Faders:** channel faders, crossfader, master. Tribe's own fader and crossfader curves can be copied
  (`claudedocs/cue_tracks_menus.md`).
- **EQ and filters, echo, reverb on built-in tracks,** using Unity's audio filter components. A community VRChat
  mixer asset already has synced high-/low-pass, echo and reverb.
- **Headphone cue:** each visitor's VRChat makes its own sound, so the DJ's headset can hear a cue mix while the crowd
  hears the main mix. The community mixer has local monitor buttons for this. The hand-to-ear gesture can be rebuilt
  from hand positions **(design idea, not built)**.
- **Crowd hears the mix:** every visitor plays the same tracks, following synced deck state.
- **Lights and visuals:** AudioLink (the community audio-reactive system), plus our per-song section markers and
  light scripts. VJ loops play on world video screens.
- **Track info screens:** BPM, sections, and waveform images pre-rendered offline (each image costs world size).

## Partly, or approximate

- **Song count:** limited by world size.
  - Quest-compatible worlds are reportedly capped around 100 MB, enough for roughly a dozen or two tracks after the
    club itself.
  - PC worlds can be much bigger (one creator reports about 1 GB), roughly 150–200 tracks.
  - These are user reports, not an official page, and the counts assume about 5 MB per track.
- **Speed changes the key:** there's no key lock. Fine for 140 → 140, noticeable for big jumps.
- **Loops:** Udon checks the position once per frame, so loop points can be off slightly.
- **Jog wheel:** nudging works; scratching doesn't.
- **Crowd sync:** close, but not perfectly tight between visitors.
- **New songs** need their BPM and grid worked out before upload. Our tooling already does this.

## Not possible

- **Tribe's audio engine** (Superpowered, native C++) and what it does:
  - key lock and time-stretch;
  - Tribe's Beat FX and Color FX;
  - Tribe's mixer processing.
- **Custom per-sample audio processing in Udon:** `OnAudioFilterRead` is reported not to work.
- **EQ, filters or effects on link/streamed tracks:** VRChat's video player ignores filters, and VRChat closed that
  as can't-fix.
- **Your music library, files on the headset, or Beatport/SoundCloud/Tidal/Dropbox logins** inside the world.
- **Building a link from text while the world runs** (VRChat rule). So there's no "search any song online" browser,
  only pre-set or typed links.
- **Analysing a song's BPM inside VRChat:** do it before upload.
- **Running Tribe's Blueprints or C++ in Unity:** different engine.

## What we already have to work with

| From our work | Use in VRChat | Rights |
|---|---|---|
| Your stages (Reactor club, Dino, Graveyard, Midtown, RED EYE, Harvest Moon: Blender scenes, crowds, lasers) | the world itself | yours |
| Your avatars (`skins/*.glb`: Lampwing, Skullbuck, Horseman, Santa, Major Tom, Gremlin) | VRChat avatars, after conversion | yours |
| Your VJ loops and hour-long sets (`TribeUE/Visuals`) | world screens | yours |
| Song data: about 1,775 songs with BPM, beat grid and sections (`TribeUE/Songs/cues`) | Sync, hot cues, light cues | yours (the audio files' rights are separate) |
| Light scripts and light-show experience | world light shows | yours |
| Deck catalog: every control, its position and what it does (`claudedocs/deck_catalog.md`) | the interaction spec | our notes |
| Mixer and effect internals (cue formula, fader/crossfader curves, EQ, effect settings) | making it feel like Tribe | our notes |
| Menu catalog: song browser layout, sort options, settings (`claudedocs/menu_catalog.md`) | UI reference | our notes |
| Tribe's gear models and textures (`D:/TribeUE/tribe_models`) | the deck and mixer look | Tribe's; the Pioneer replicas also carry Pioneer's designs and logos. Reference, or with Tribe's permission |

## Music rights

Tracks built into a world are downloaded by every visitor. That's fine for your own productions or tracks you have
rights to. Commercial releases risk takedown.

## Tests to run first

Each is cheap and decides a feature:

1. **Speed:** Udon sets a track's playback speed (`AudioSource.pitch`).
2. **Lock:** two decks stay locked after Sync on one headset.
3. **Filters:** high-/low-pass, echo and reverb respond to Udon (or use the community mixer asset).
4. **Size:** the world's size with N tracks. Build & Test shows it.
5. **Network sync:** sync quality with two or more visitors.

## Porting Graveyard Shift (2026-10-27)

**The crowd stays out:** in VRChat the visitors are the crowd. That removes the heaviest piece: about 4,250 dancers,
roughly 330k triangles and a 16 MiB animation texture. Performance stops being the main risk, and a cut-down Quest
version becomes realistic.

Everything was generated by our own Blender scripts (`TribeUE/TribeXR/Scripts/Blender/halloween`, `hw_show.py`), and
the lighting is baked into the textures. So the set re-exports cleanly, and the look carries over.

| Part | Effort |
|---|---|
| Set (facade, moon, booth, rig, grounds, sky): Blender → FBX | easy |
| Walking and collision (Unity colliders) | easy |
| Visuals wall and VJ loops (video player) | easy, but costs world size |
| Crypt doors and the crypt stream monitor (Udon, an animation, a camera to a screen) | easy–medium |
| Materials (Unreal material graphs → Unity shaders) | medium |
| Fog sheets, lightning, flame jets, ghosts and flocks (shader motion) | medium |
| Light show (Udon reading the song cue files, VR Stage Lighting for lasers and moving heads, AudioLink) | medium–hard; the biggest job |
| Horse and rider (baked-animation shader), optional | medium |
| Intro ride (seat the player on a moving platform), optional | medium |

**Tools on this PC (checked):** Unity Hub with 2022.3.22f1 and 6000.0.42f1, the VRChat Creator Companion, and `vpm`
(`~/.dotnet/tools`).

**First step:** export the set from Blender, create a VRChat world project, import it, and check the world size and
frame rate.

## Alternative

DJ in Tribe and stream into VRChat (Twitch / RTMP). This keeps every Tribe feature, and it's what you do today.

## Sources

- [OnAudioFilterRead issue (VRChat feedback)](https://feedback.vrchat.com/udon/p/issue-on-implementing-custom-dsp-algorithms-with-onaudiofilterread)
- [AVPro ignores LowPass/Reverb filters (VRChat feedback)](https://feedback.vrchat.com/open-beta/p/986-avpro-player-ignores-lowpass-reverb-and-other-filters)
- [External URLs / VRCUrl rules (VRChat docs)](https://creators.vrchat.com/worlds/udon/external-urls)
- [VRCUrl can't be built from a string at runtime (VRChat forum)](https://ask.vrchat.com/t/how-can-i-change-url-edit-of-vrcurl-constructor/27476)
- [VRCAudioMixer: crossfader + effects (Booth)](https://booth.pm/ja/items/4494218)
- [Audio Trace: Udon-driven low-pass (Booth)](https://booth.pm/en/items/8566260)
- [Quest world 100 MB limit (VRChat feedback)](https://feedback.vrchat.com/feature-requests/p/review-system-for-quest-worlds-aiming-for-over-100mb-filesize)
- [PC world upload limit (VRChat feedback)](https://feedback.vrchat.com/feature-requests/p/increase-world-upload-limit-for-pc)
