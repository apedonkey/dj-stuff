# Dino Stage VJ loops: concept list and pack plan

Original loops for a dinosaur-themed headliner set on the Dino Stage (Tribe XR). They play on the visuals wall
behind the DJ (the "keywall": the stage's screen, fed by videos in Tribe's media folder on the Quest). Everything is
built procedurally in Blender from our own geometry (the stage generator's horns, spines and skull); no downloaded
footage, images, models or fonts.

**Phase 2 deliverables** (the user plays hour-long sets of heavy dubstep and runs one long visuals video for the whole
set):
- `deliver/Loops/`: every concept in 3 variants (palette, camera path, density), 27 loops at 140 BPM, named like
  `Dino - Fossil Scan (cyan) 140bpm.mp4` (the sting: `Dino - Stage Sting (amber) 140bpm.mp4`); plus
  `Dino - Giant Halo (red) 140bpm.mp4` for the giant intro. The five 128 BPM cuts made before the switch stay as
  extras, named `... 128bpm.mp4`.
- `deliver/Dino Visuals - Full Set.mp4`: 60:00 continuous at 140 BPM (2100 bars), from `scripts/assemble_set.py`.
  96 bars (2:44.6) of Giant Halo open it, the user's choice (2026-10-07): in the opener, SVDDEN DEATH - PRELUDE I, the
  DJ rises at 1:09 and lands at 2:46, so the Halo covers the rise and the 2-bar crossfade into the sting ends just
  before the landing (`--intro-bars` changes it). Six acts of 352 bars (10:03; the last 340) follow the arc Awakening
  (intro), The Hunt (build), Impact (peak), Primeval (breakdown), Stampede (peak), Afterglow (outro), each opening with
  16 bars of the sting; a Lava Moon cut closes it. Every loop is used; crossfades of 2 bars end on 16-bar phrase boundaries; no loop
  plays twice in a row or twice within 10 minutes. H.264 High 1080p30, about 6 Mbps (~2.7 GB), no audio, gated as a
  whole for flashes and brightness. Its timeline: `deliver/Dino Visuals - Full Set - timeline.txt`.
- `deliver/README.txt`: the loop list (written by `scripts/deliver.py`).

## Shared spec (every loop)
- File: MP4, H.264 High, yuv420p 8-bit, 1920x1080, 30 fps, no audio.
- Timing: **140 BPM half-time** (the user plays 128-150 BPM heavy dubstep). Every script takes `--bpm N` (or env
  `VJ_BPM`) and `--straight` (or `VJ_HALFTIME=0`) for a 4-on-the-floor grid; the 128 cuts were made with
  `--bpm 128 --straight`. A loop is 8 bars = 32 beats = 411 frames = 13.7 s at 140, seamless (frame 411 equals
  frame 0). Beat *k* lands on frame `floor(FPB k + 0.5)` (FPB = 12.857 at 140): bar downbeats at frames 0, 51, 103,
  154, 206, 257, 309, 360. Scripts take all timing from `vj.FPB`, `vj.BEAT_F`, `vj.FRAMES` and `vj.ACC`; never
  hard-code a frame count.
- Half-time feel: the accents are the kick on beat 1 and the snare on beat 3 (`vj.clock(f)`: `kick` is their envelope,
  `acc` / `aph` the accent index and phase, `snare` which one it is). No pulse on every beat: per-beat sequencers,
  waves and stomps step on the accents instead. Drops get their weight from motion (shakes, `vj.jolt` camera thumps,
  lens punches, wobble), not from brightness.
- Picture: pure black backgrounds (black reads as an unlit screen at night) with neon line work, glows and silhouettes;
  no green screen, no keying.
- Composition (the lead's rule, 2026-10-06): **compose for the Dino Stage's arch window.** The screen is the arch
  (44 x 16 m); the 16:9 frame maps onto arch.video_box(), a 44.3 x 24.9 m box around it, so only frame rows ~190-890
  ever show and the arch narrows toward the top (row 240: x 361-1559 only). Key art goes inside the visible band
  (rows ~200-880) and away from the top corners the arch cuts off; strong colour, grids, lasers and glow may bleed to
  the frame edges. The reference is TribeXR/Scripts/Blender/arch.py (screen_outline, video_box), which may still
  shift: `scripts/arch_window.py` (Blender's Python, no render) exports it to `scripts/arch_window.json`; contact
  sheets draw that window (outside dimmed, edge in yellow) and warn when arch.py is newer than the export; and any
  scene script takes `--arch PREFIX,...` [`--arch-frames A:B`] to report where those objects land against the window
  over the loop, without rendering.
- Brightness: the show is dark and the wall is huge, so nothing large may glare. Every ~1 m² patch of the wall (a
  120 x 120 px block) stays at or below **0.65** luma on every frame; only thin neon lines go brighter. No frame averages
  over 0.5 (no full-frame white).
- No strobes (the user finds stage flashing "a bit too much"): at most 3 flashes per second anywhere on the wall, no
  one-frame hits. Fills swell into the downbeat and peak on it; the accent pulse stays soft, accent frames at most
  ~1.6x as bright as the frames between accents. Half-time accents come 1.17 times a second, well inside the budget.
- Look: Blender 4.5 EEVEE Next, the **Standard** view transform (AgX washes neon out to pastel), one tight compositor
  Bloom (threshold 1.0, strength 0.6, size 0.4); 16 samples, motion blur on for final renders. Standard clips each
  channel on its own and sRGB lifts small values (linear 0.16 shows as 0.44): a red that must stay red keeps green and
  blue at a few percent, even in a clipped core.
- Palette: amber/orange, cyan, magenta, laser green, deep red, UV purple. Green and cyan are the high-luma colors:
  keep them as lines, never as big shapes.

## The loops
| # | Loop | Slot | Mood | Variants |
|---|------|------|------|----------|
| 0 | Giant Halo | giant intro | majestic, dark | red |
| 1 | Fossil Scan | intro | ominous, awakening | cyan, amber, uv |
| 2 | Amber DNA | intro / breakdown | dreamy, suspense | gold, magenta, vortex |
| 3 | Spine Tunnel | build into drop | momentum, hyperdrive | amber (approved), ice, ember |
| 4 | Raptor Run | build | chase, urgency | green, magenta, stampede |
| 5 | Extinction Event | drop | cataclysm | inferno, cyan, shockwave |
| 6 | Stomp | drop (heavy / half-time) | menacing, heavy | lava, toxic, gold |
| 7 | Primeval Jungle | breakdown | lush, hypnotic | uv, ember, crane |
| 8 | Lava Moon | outro / breakdown | warm afterglow | amber, blood, eclipse |
| + | Dino Stage Sting | act changes, ID | identity, hype | amber, cyan, uv |

### 0. Giant Halo (giant intro)
For the DJ's giant intro: the stage goes dark, one spotlight finds the DJ and a lift raises them about 7 m in a
floor-length robe. Behind them a huge red halo like a backlit eclipse: a thin glowing ring around a black disc, a soft
corona whose streamers churn slowly, smoke drifting up through its light (rays near the ring, dark over the disc).
The ring sits where the raised DJ's head lands on the Dino Stage screen for the crowd (x 960, y ~405, radius 200 px),
so the spotlit DJ stands in front of the disc. **Beat hook:** a barely perceptible half-time breath (a few percent on
the kick and snare). Calm, no hits.

### 1. Fossil Scan (intro)
The stage's own roaring T. rex skull (skull v2) as a laser-scanned hologram: glowing contour slices on black bone,
turning slowly between two views. Once per bar a scan plane sweeps down through it; the slices it crosses flare in
the scan color and cool back. The eyes swell on toward bar 5's downbeat and fade out over bar 8. A dim radar backdrop
rings out once per bar. **Mood:** ominous, something waking up under the ice. **Beat hook:** scan per bar, a faint
slice lift per accent. Variants: *cyan* (three-quarter view from below), *amber* (profile, dense slices), *uv* (head-on,
slices + meridians).

### 2. Amber DNA (intro / breakdown)
A double helix of amber beads with cyan rungs turns and drifts toward the camera. Each accent lights the next rung like
a step sequencer (away in bars 1-4, back in bars 5-8), and on every downbeat a spark runs the length of the strand;
amber dust hangs in the black. **Mood:** dreamy, scientific, the calm before the build. **Beat hook:** one rung per
accent, a spark per bar. Variants: *gold*, *magenta* (magenta beads, green rungs, UV dust), *vortex* (straight down the
helix's axis).

### 3. Spine Tunnel (build into drop)
A fly-through of an endless neon ribcage toward a lava moon with a chasing bulb ring, over a laser-grid floor. One rib
arch passes per beat; every downbeat arch carries the stage's flared horns. Bars 1-4 are bare; bars 5-8 bring an
8-beam laser fan that re-cues on every accent. Each accent sends a light wave down the tunnel and punches the lens in.
The last two beats of bars 4 and 8 swell into the downbeat: a ghost arch glides in and settles framing the screen, and
the palette morphs so the new section lands on the hit. **Mood:** momentum, hyperdrive. Variants: *amber* (the approved
cut: amber then magenta, centered camera), *ice* (cyan then UV, magenta lasers, a slow corkscrew camera), *ember* (red
then orange, half-time arches, a low camera looking up).

### 4. Raptor Run (build)
A pack of raptor silhouettes sprints across a glowing horizon line, legs cycling one stride per beat, over a scrolling
laser-grid floor. Laser fans sweep behind them; on bar 5 the lead raptor leaps and the pack scatters through a burst of
laser fans. **Mood:** chase, urgency, rising tension. **Beat hook:** strides on the beat, rims and lasers lift on the
accents; bar 8 swells into the next phrase. Variants: *green*, *magenta* (palette), *stampede* (nine raptors, a low
front-quarter camera).

### 5. Extinction Event (drop)
A meteor streaks in from the upper left of the arch window during bars 6-8, trailing fire, and slams into the jungle
horizon on the loop's downbeat: the horizon flares orange, a shockwave ring races outward, and the skyline burns red
(a flare, not a white-out). Embers then drift up through bars 1-5; every accent thumps the camera. **Mood:**
cataclysm, the drop itself. **Beat hook:** the impact is frame 0, so starting the loop on the drop puts the hit on the
drop. Variants: *inferno*, *cyan* (a cold comet), *shockwave* (a closer camera the blast knocks back, plus a meteor
shower).

### 6. Stomp (heavy drop / half-time)
Giant three-toed footprints slam down toward the camera on the kick and on the snare. Each lands with a screen shake,
a dust ring and glowing cracks in the ground; the downbeat stomp is bigger and its cracks race to the edges of the
frame. **Mood:** heavy, menacing, made for half-time drops. **Beat hook:** a stomp per accent. Variants: *lava*,
*toxic* (UV/magenta prints on a cyan grid), *gold* (gold prints, longer strides, a low camera).

### 7. Primeval Jungle (breakdown)
Layered fern and palm silhouettes in slow parallax against a UV-purple horizon glow, a sauropod walking behind the
trees (a footfall per accent). A laser sheet slices through the canopy once per bar and its cuts on every layer snap
into one line on the downbeat; fireflies drift and pulse on the offbeats. **Mood:** lush, hypnotic, a chance to
breathe. **Beat hook:** laser sheet per bar, fireflies on the "and". Variants: *uv*, *ember* (volcanic dusk), *crane*
(the camera cranes up over the canopy and back).

### 8. Lava Moon (outro / breakdown)
The Dino Stage in silhouette against a huge churning lava moon, its 48-bulb ring chasing on the beat, amber uplight
beams swaying behind the arch. **Mood:** warm afterglow, closing time. **Beat hook:** bulb chase per beat, the beams
swing once per 2 bars, a soft lift per accent. Variants: *amber*, *blood* (a crimson moon from lower down), *eclipse*
(a dark moon with a corona).

### + Dino Stage Sting
The words DINO STAGE built from neon bone segments (our own letterforms, no font) snap together on bar 1's downbeat,
pulse softly on each accent, then break apart into drifting bone fragments at the end of the loop and fly back in for
the next downbeat. **Mood:** identity, a hype moment between acts. Variants: *amber*, *cyan*, *uv*.

## Making a loop (pipeline)
Scene contract: `scripts/<concept>.py` builds its scene on `scripts/vjkit.py`, picks its variant with
`VNAME, V = vj.variant(VARIANTS)`, keys everything from the music clock, and ends with `vj.setup_render(...)` and
`vj.finish(scene, f"<concept>_{VNAME}")` (see `scripts/spine_tunnel.py`). `vj.finish` handles `--all`, `--frames`,
`--out` and `--seam DIR` (frame 411 in the same Blender run).

GPU: one GTX 1660 shared with the stage bakes. The lock is the directory `C:\Users\Chris\TribeUE\gpu.lock.d`
(made with mkdir, `owner.txt` inside says who and since when); take it before ANY render, hold it for one render.
`scripts/gpu_lock.sh` implements it; `scripts/gpu_run.sh <name> <command>` runs one command under the lock.

```bash
# Git Bash, from C:/Users/Chris/TribeUE/Visuals
B=/d/Tools/blender-4.5.14-windows-x64/blender.exe
# look-dev: a quarter-res pass of the whole loop + its seam frame under the lock (~1 min), then the gate
bash scripts/gpu_run.sh <name> $B -b --factory-startup --python scripts/<concept>.py -- --variant <v> --all --pct 25 \
     --samples 4 --mblur --out _work/<name>_lookdev/<concept>_<v> --seam _work/<name>_lookdev/<concept>_<v>_seam
python scripts/check_loop.py _work/<name>_lookdev/<concept>_<v> <concept>_<v>_ \
     --seam _work/<name>_lookdev/<concept>_<v>_seam/<concept>_<v>_0411.png
# a finished variant, ~6-10 min: render all frames + frame 411 under the lock, gate the frames, encode, gate the MP4,
# still + contact sheet, delete the frames; exit 0 only if everything passes. Extra args go to the scene.
bash scripts/make_loop.sh <name> <concept> <v> [--samples 6]   # -> renders/<concept>/<concept>_<v>_140bpm_*.mp4
python scripts/deliver.py <concept>_<v>_140                       # gate again, copy to deliver/Loops, rewrite README
```
`scripts/check_loop.py` is the gate (all rules above; `--video FILE` checks an MP4, the full set included; 140
half-time by default, `--bpm 128 --straight` for the extras). The seam-pop rule (the last -> first step may not be the
loop's biggest) allows 1.1x on MP4s and ignores steps under 1.0/255: an MP4's frame 0 is a keyframe whose codec noise
alone tipped near-still or seam-fast loops over 1.02x while their frames were bit-exact. Spine Tunnel (ice) is the one
loop at a cap: 3 flashes/s in the top-left region (as its approved 128 cut), where the corkscrew sweeps the ribs.
Gate logs of every make_loop run: `_work/lead_logs/`.

Measured on the GTX 1660 Super: 0.5-0.6 s/frame at 1920x1080 for most loops (4-5 min per loop, more while other jobs
share the GPU), Giant Halo 1.1 s/frame at 6 samples; 30 s to encode.

## Files
- `renders/<concept>/`: each variant's MP4, still and contact sheet (what `make_loop.sh` makes), at 140 (`_140bpm_`)
  and the 128 cuts (`_128bpm_`).
- `renders/spine_tunnel/spine_tunnel_amber_128bpm_*`: the approved 128 cut (decoded frames identical to the earlier
  `spine_tunnel_128bpm_8bars_1080p30_nostrobe.mp4`, which is the file on the Quest);
  `spine_tunnel_128bpm_8bars_1080p30.mp4` is the earlier wall-tuned cut with one-frame hits, kept for comparison only.
- `scripts/`: `vjkit.py`, one script per concept, `encode.py`, `contact_sheet.py`, `check_loop.py`, `gpu_lock.sh`,
  `gpu_run.sh`, `make_loop.sh`, `deliver.py`, `assemble_set.py`.
- `_work/`: scratch frames while a loop is being made (deleted by `make_loop.sh` once it passes).
