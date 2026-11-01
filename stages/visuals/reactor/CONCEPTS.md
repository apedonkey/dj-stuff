# REACTOR VJ loops: concept list and pack plan

Original loops for the REACTOR club in Tribe XR. They play on the club's main screen: the core's viewing window behind
the DJ, **16 x 9 m, the whole 16:9 frame visible** (no arch crop like the Dino Stage). The club is a dark industrial
bass club inside a reactor hall. The user plays one hour-long visuals video per set (heavy dubstep, 128-150 BPM), so
the pack must stay entertaining for an hour. Everything is procedural in Blender from our own geometry: no downloaded
footage, images, models or fonts, and no real brands or logos. Letters come from `scripts/letters.py` (our monoline
strokes); the radiation trefoil and hazard stripes are generic symbols built from geometry.

The user picked all twelve concepts (2026-10-09), plus a sting and an opener:

| # | concept | script | variants (palette / camera / density) |
|---|---|---|---|
| 1 | Cherenkov Pool | `cherenkov_pool.py` | blue, uv, deep |
| 2 | Control Rods | `control_rods.py` | amber, cyan, red |
| 3 | Chain Reaction | `chain_reaction.py` | cyan, amber, magenta |
| 4 | Meltdown | `meltdown.py` | ember, alarm, scram |
| 5 | Cooling Towers | `cooling_towers.py` | teal, orange, purple |
| 6 | Turbine Hall | `turbine_hall.py` | amber, blue, green |
| 7 | Coolant Pipes | `coolant_pipes.py` | cyan, amber, uv |
| 8 | Containment | `containment.py` | red, amber, breach |
| 9 | Particle Ring | `particle_ring.py` | magenta, cyan, green |
| 10 | Geiger Scope | `geiger_scope.py` | green, amber, cyan |
| 11 | Isotope Lattice | `isotope_lattice.py` | uv, gold, cyan |
| 12 | Hazard Type | `hazard_type.py` | amber, red, blue |
| S | Reactor Sting (4 bars) | `sting.py` | amber, blue, red |
| O | Cold Start (the opener) | `cold_start.py` | blue |

## The concepts

1. **Cherenkov Pool.** Looking down into a pool-type reactor core: a square grid of fuel assemblies (rods end-on)
   under deep water, Cherenkov blue rising from the core, slow caustics rippling over it. Accents: the glow swells from
   the centre outward (kick bigger than snare). Section B: rod banks withdraw and the grid brightens in a pattern. Slow
   descent and turn. *deep* = darker water, more caustics, less core.
2. **Control Rods.** A side cut-away of the core: dozens of vertical rods with hazard-chevron caps. A bank slams down on
   the kick, another withdraws on the snare; the gaps glow hotter as rods lift. Slow sideways track.
3. **Chain Reaction.** Nuclei (glowing spheres) drift in the dark. A neutron (a bright dot with a trail) hits one on the
   accent; it splits into two fragments and 2-3 neutrons that hit more nuclei: a branching cascade that blooms. Section
   B (the drop) fills the frame; every cascade fades before the seam.
4. **Meltdown.** The core goes critical: a molten fuel mass, orange to white-hot, slumping; embers rising; analog gauge
   needles at the frame sides pushing into the red; heat shimmer. *scram*: on a section downbeat the rods slam in and
   everything sinks to deep blue over at least 3 frames (a fade, not a flash), then reignites through the swell.
5. **Cooling Towers.** Hyperbolic towers in silhouette against a dark sky; steam plumes (layered cards) lit from inside,
   swelling into each downbeat; slow-blinking aircraft lights (fades, never strobes); a low dolly past the towers.
6. **Turbine Hall.** Giant turbine rotors spinning (motion blur), thin power arcs leaping between terminals on the
   accents (lines, not big flashes), a power meter line rising; a camera tracking along the hall.
7. **Coolant Pipes.** A fly-through of a pipe tunnel: big pipes, flanges and valves; pressure waves of light race
   along the pipes on the accents; steam vents. Geometry runs on behind the far end for the whole loop (the seam).
8. **Containment.** A wall of hexagonal shield plates and hazard stripes, slow sweeping beacon cones (soft); a slow
   push in. *breach*: section B cracks glow through the plates and steam jets out.
9. **Particle Ring.** A fly-through of a toroidal ring (tokamak / accelerator): magnet coils pass the camera, a plasma
   ribbon spirals along the torus; accents brighten the plasma and kick the coils' glow. The torus is periodic, so the
   loop is seamless by construction.
10. **Geiger Scope.** A retro CRT oscilloscope: phosphor glow, graticule, waveforms tracing, decay clicks as spikes on
    the accents; in section B the radiation trefoil assembles from particles. Scanlines, slight barrel curve.
11. **Isotope Lattice.** A rotating crystal lattice of atoms; bonds light up in neon waves on the accents; electron
    orbits trace rings round some atoms; a slow orbiting camera.
12. **Hazard Type.** Kinetic type: monoline stencil words (REACTOR, CAUTION, CRITICAL, CONTAINMENT, SCRAM, CORE) and
    hazard chevrons sliding and scrolling in layers on the accents. No full-frame fills.

- **Reactor Sting** (4 bars, `VJ_BARS=4`): the REACTOR nameplate in monoline strokes and a core ring sweeping in; it
  opens each act of the set.
- **Cold Start** (8 bars, played for the opening 64 bars of the set): the hall wakes. Warning beacons spin up, steam,
  the core window brightens as the rods withdraw. One variant (blue).

## Pack plan
- **Loops**: 12 concepts x 3 variants = 36 loops, plus 3 stings and the opener, in `deliver/Loops/` named
  `Reactor - Cherenkov Pool (blue) 140bpm.mp4`.
- **The set**: `deliver/Reactor Visuals - Full Set.mp4`, 60:00 at 140 BPM, in six acts that follow the reactor's
  story: Startup (intro), Criticality (build), Full Power (peak), Coolant (breakdown), Meltdown (peak), SCRAM (outro).
  Cold Start opens it; a sting opens each act; crossfades of 2 bars end on 16-bar phrase boundaries; no loop twice in a
  row or twice within 10 minutes. Assembled by an adapted copy of the Dino pack's `assemble_set.py`.
- **Order**: authoring and quarter-res look-dev first (all 14 pieces), one full-res still per variant for the user's
  approval, then the full renders as an unattended queue under the GPU lock, then the set.

## Shared spec (every loop; the Dino and Halloween packs' rules)
- File: MP4, H.264 High, yuv420p 8-bit, 1920x1080, 30 fps, no audio, ~16 Mbps (`scripts/encode.py`).
- Timing: **140 BPM half-time** from `vjkit` (`vj.FPB`, `vj.BEAT_F`, `vj.FRAMES`, `vj.ACC`, `vj.clock(f)`): accents
  on the kick (beat 1) and snare (beat 3), no pulse on every beat; 8 bars = 411 frames, seamless (frame 411 = frame 0).
  Drops get their weight from motion (`vj.jolt`, shakes, punches), not brightness.
- Picture: pure black backgrounds, neon line work, glows and silhouettes. Standard view transform (never AgX), one
  tight compositor Bloom (`vj.setup_render`). Palette: the `vjkit` constants (CHERENKOV, COOLANT, AMBER, EMBER, ALARM,
  LASER, UVP, PLASMA, STEEL, HOT); the high-luma colours (COOLANT, LASER, STEEL) are lines, never big shapes.
- Composition: the whole frame shows on the 16 x 9 m window; key art inside the middle 90% (`contact_sheet.py` marks it).
- The gate (`scripts/check_loop.py`, applied by `lookdev.sh` and `make_loop.sh`): every 120 x 120 px block (1 m2 of the
  screen) at most 0.65 luma, no frame above 0.5 mean, at most 3 flashes per second anywhere, no one-frame hits, accent
  frames at most ~1.6x the frames between, seam >= 45 dB. **No strobes**: the user finds flashing too much, and stream
  viewers see the screen too. Fills swell into the downbeat and peak on it.
- Lessons from the Dino and Halloween packs are in the memory note (dino-vj-loops) and in their scripts; the most
  useful: additive light on bright geometry clips to white; a near-lens bright shape dominates its region; morph
  palettes during the swell, not after the hit; objects that exist before their event must be fully transparent.

## GPU etiquette (one shared GTX 1660)
- Every Blender render (look-dev included) goes through `scripts/gpu_lock.sh` (`lookdev.sh` / `make_loop.sh` /
  `gpu_run.sh` do it). Reactor's lock waits until the lock has been free for 45 s, so Halloween's renders (priority until
  2026-10-31) go first. One render per lock hold; never hold it while editing.
- Long renders: run them in the background and wait for them to finish; don't poll in a loop.
- Work only under `TribeUE/Visuals/reactor/`; `_work/` names are per piece (`lookdev_<concept>_<variant>`).

## Lessons from authoring (2026-10-09)
- A sky card that rides with the camera must take its stars in the card's own coordinates. In world x they slide with
  the travel and the seam fails (40 dB). (Cooling Towers)
- In a fly-through, an exponential distance fade never reaches zero, so frame 411 saw less far tunnel than frame 0. Clip
  the camera (160 m) and keep geometry at least 175 m ahead for the whole loop. (Coolant Pipes)
- A pale accent colour on dark, low-luma line work makes each kick and snare wave double the frame mean (kick x2.01).
  Use a deep accent colour and a per-variant wave_gain. (Coolant Pipes uv)
- Near-lens geometry under an accent lift dominates its 1/16 region: fade it out to 6.5 m. (Particle Ring coils)
- Approval stills: f206 (section B's first downbeat) is the queue's default. Pick the frame that shows the idea:
  Control Rods f240 (banks half out), Geiger Scope f330 (the trefoil formed); the plant agent used f257 (bar 6).

## Lessons from the final renders (2026-10-10)
- With motion blur on (make_loop passes `--mblur`), Blender 4.5 EEVEE's first render in a session has no blur on
  moving objects. make_loop renders frame 0 first, so frame 0 was the odd one out.
  - Chain Reaction amber's seam fell to 44.7 dB. The cause is the render order, not the animation: rendered 411 first,
    frame 411 became the odd one.
  - `vjkit.render_frames` now does one throwaway render first when motion blur is on (WARM). Frame 0 vs 411: 90 dB.
  - Loops rendered before the fix keep an unblurred frame 0 that only shows on fast motion. Their seams: Cold Start,
    stings, Cherenkov Pool, Control Rods 72-106 dB (kept); Chain Reaction cyan 48.7 and magenta 53.2 dB (re-rendered).
- Full-res render time varies a lot by concept: about 0.5 s/frame (sting, Control Rods) up to 2.5 s/frame (Cold Start).
  The queue log has each piece's time.
- Seam review of the finals rendered after the fix: the lowest are Coolant Pipes 53.0-53.9 dB, Isotope Lattice cyan
  56.9 and Hazard Type 57.9-66.5 (everything else 70-113).
  - Re-rendering frames 0, 1, 410 and 411 in one session reproduced each score exactly: these come from the scenes,
    not from the render order.
  - Where frame 411 differs from frame 0: the steam haze at the vanishing point (Coolant Pipes, whose look-dev seams
    were already 51.7-54.8), the motion-blurred edges of the chevrons (Hazard Type), a few pixels (Isotope Lattice).
    The mechanism is not pinned down. The clock signals, the 137-frame flow cycle and the transform keys are periodic.
  - Size: at most ~630 pixels change by more than 16 levels (none by more than 80), against ~600,000 in one ordinary
    frame step (frame 0 vs 1 is 14-17 dB). Invisible in motion, so they were kept.
