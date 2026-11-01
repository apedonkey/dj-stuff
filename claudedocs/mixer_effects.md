# Tribe XR's mixer effects

How Tribe XR (build 2304) processes its Color FX, send FX and Beat FX, read from the decompiled C++ in
`libUnreal.so`: the mixer render, its stage functions, the effect units and their data tables.

How the code was identified:
- **Effect names** come from Unreal's type data (`EColorFxType`, `EBeatFxType`, `EBeatFxTimeInterval`,
  `EBeatFxChannel`, `EChannelFxType`).
- **Superpowered SDK classes** were identified by their constructors and field layouts. For example,
  `Reverb(samplerate, 96000)` and Echo/Flanger/Gate fields such as wet, bpm and beats sit where the SDK puts them.
  These identifications are **(inferred)**, but every value Tribe feeds them is **(read)**.
- **Knob values:** the per-channel Color knob runs −1…+1 with 0 at the centre. Parameter, Level and Time are 0…1.
  The Beat FX time is in beats × (60000 / BPM) ms.

The mixer's signal chain, cue bus and output are in `claudedocs/cue_tracks_menus.md` ("Inside the mixer").

## Where each effect sits

The channel FX run at one of three points in a channel's chain. The point comes from a table (`0x89dbf0`) indexed by
the effect type.

| Point | Effects | Consequence |
|---|---|---|
| 0: after trim, before EQ | Noise, Noise Chopper | in the cue only when PRE EQ is off: the render takes the PRE EQ cue before any channel FX (cue_tracks_menus.md "Inside the mixer", steps 2-3; corrected 2026-10-28 after the VRDJ color_fx review) |
| 1: after EQ and filter | Sweep, Crush, Filter | in the cue only when PRE EQ is off |
| 2: after the fader | Space, Dub Echo, Short Delay, Long Delay, Reverb, Phantom Echo, Vaporize | tails ring on when you pull the fader down; never in the cue (cue is pre-fader) |

Beat FX can target:
- channels 1–6;
- crossfader side A or B (that side's bus, before the master sum);
- the mic;
- the master (after the master sum).

## Color FX

There are two units, chosen by the mixer type.

### The DJM-900NXS2-style unit (`FUN_047a3448`)

It handles the six classic Color FX. Each effect is on only while the knob is off-centre and on the same side as in
the previous audio block. When you switch effects, the old effect objects are switched off and new ones are created.

- **Space**
  - The channel × |knob| feeds a Superpowered Reverb: dry 0, wet 1, predelay 0–60 ms over the knob.
  - Turning right sets the reverb's low cut to 3 kHz (an airy tail). Turning left sets the low cut to 150 Hz with
    damping 0.9 (dark).
  - Room size is 0.7 + 0.3 × Parameter (0.8 when Parameter is unset).
- **Dub Echo**
  - The channel × |knob|^0.2 × 0.6 goes through two filters (right: 600 Hz and 20 kHz; left: 300 Hz and 4 kHz,
    resonance 0.04), into a Superpowered Echo at 60 BPM.
  - Echo length 0.031 + 0.099 × |knob| beats (31–130 ms). Feedback 0.4–0.99, from Parameter × knob.
- **Sweep**
  - Right: a band-pass that closes in. The low-pass falls from 20 kHz toward 1 kHz (`20000 − 19000·x^0.2`) while
    the high-pass rises from 20 Hz toward 1.8 kHz (`20 + 1780·x^1.3`). Both are scaled by 2 × Parameter + 0.2,
    resonance 0.16.
  - Left: a Superpowered Gate synced to the BPM, chopping every 1/2 beat, wet 0.2–1.0 from Parameter.
- **Noise:** a noise generator mixed into the channel. The generator is a Superpowered Whoosh (filtered white
  noise; see `claudedocs/superpowered_dsp.md`) **(read: same constructor, 0x6cf6048, as Noise Chopper's)**.
  - Its level ramps from 0 to 1 between knob 0.1 and 0.3 (or uses Parameter when set).
  - Its filter sweeps 80 Hz → 10 kHz when turning right, and 10 kHz → 80 Hz when turning left.
- **Crush:** a Superpowered Bitcrusher, then a filter.
  - Bits run from 16 down to 1 (`16.5 − 15·|knob|^0.33`).
  - Sample rate is 12000 − 10000 × Parameter (6000 when Parameter is unset).
  - Turning right adds a 1.6 kHz filter at resonance 0.25.
- **Filter:** a low-pass and a high-pass in series.
  - Left lowers the low-pass from 20 kHz to 80 Hz (`80 + 19920·(1 − |k|)^2.87`).
  - Right raises the high-pass from 20 Hz to 8 kHz (`20 + 7980·k^2.59`).
  - Resonance is 0.04–1.0 from Parameter^2.19 (0.25 when Parameter is unset). On the right it ramps in over the
    first 35 % of the knob.

### The V10/A9-style ("smart") unit (`FUN_047a4a1c`)

- **Filter:** the same curves as above, with resonance fixed at 0.25.
- **Phantom Echo:** a Superpowered Echo synced to the BPM, with a 3-band EQ in its feedback that strips the lows from
  every repeat (see "Inside the effects").
  - The knob filters the channel: right is a high-pass, left a low-pass, with the curves above.
  - The echo send ramps with the knob to 0.5–0.7.
- **Vaporize:** a Superpowered Reverb behind the same filter pair. Its "vapor" amount (the reverb's damping) is
  |knob| × 0.6, and its send is |knob| × 0.6 up to the knob's halfway point, then rises to 1.0.
- **Noise Chopper:** a noise source (Superpowered Whoosh) through its filter, cut by a gate synced to the BPM.
  - The filter is 400 Hz–17 kHz on the left and 80 Hz–17 kHz on the right, following k².
  - The gate chops every 1/8 beat (1/16 near the left end) on the left side, and every 1/2 beat on the right.

For this mixer type, Space, Dub Echo, Sweep, Noise and Crush reuse the NXS2 unit through the per-channel effect
slots.

## Send FX

These are the V10's built-in sends (`FUN_047a42fc`).

1. **Feed:** each channel's SEND level feeds its send unit.
2. **Effect:** the unit runs the selected effect.
3. **Return:** the returns are summed with a ×5 output gain, then run through a TONE filter at
   `440 + 5560·tone^1.4` Hz, so Tone sweeps 440 Hz–6 kHz. (The filter's type is set where the filter is created.)
4. **Into the master:** with master FX mix on, the return enters the master at `level^0.7 × 1.3`.

| Send | Time knob | Size knob |
|---|---|---|
| Dub Echo | delay `0.06 + 0.14·t^1.02` s, through a +12 dB filter at 4 kHz and a −10 dB filter at 415 Hz | feedback `size^0.45` (max 0.98) |
| Short Delay | delay `0.06 + 0.15·t^1.91` s | feedback `size^0.45` |
| Long Delay | delay `0.15 + 0.78·t^1.71` s | feedback `size^0.45` |
| Reverb (Superpowered) | room size `0.6 + 0.4·t^0.55` | damping `1 − 0.6·s^2.5`, predelay `30·s^2.5` ms, low cut `150 − 140·s` Hz |

## Beat FX

### The engine (`FUN_047a7dd8`)

- **Timing**
  - The BPM is clamped to 20–300.
  - An effect's time is the interval's beat multiplier × 60000 / BPM. The interval runs from 1/64 to 128 beats,
    with negative values (reverse) for Mobius.
  - Each effect clamps the time to its own range (table below).
  - With the X-PAD on, the pad position picks the interval from a per-effect list.
- **BPM source:** the manual Beat FX BPM, or with AUTO BPM the sync master deck's playback position.
- **Quantized switching:** when you change effect with Quantize on, the engine works out how far the next beat is
  from the deck's position. It passes the dry signal through until that sample, then starts the new effect exactly
  on the beat.
- **Levels:** each effect sets a target dry and wet level. The engine smooths them over a few milliseconds, then:
  1. A band filter keeps only the bands selected with LOW / MID / HI in the wet signal.
  2. On the dry path, a 3-band EQ scales those same bands by the dry level.
  
  So the selected bands crossfade from dry to wet, and the other bands stay dry.
- **Tails:** switching off Echo, Ping Pong, Spiral, Reverb, Helix or Mobius keeps it running with its input cut, so
  the tail rings out; picking another effect then rebuilds that effect's object so the next use starts clean
  **(read: bitmask 0x10403c in the engine)**. The per-type table's flag (value 2 for Echo, Ping Pong, Spiral, Reverb
  and Shimmer) is not what drives this; where that flag is read wasn't traced.

### The 20 Beat FX

| Beat FX | Range | What it is (Level = the depth knob) |
|---|---|---|
| Delay | 1/16–16 beats, 1 ms–16 s | Superpowered Delay at the beat time; dry `1 − L^3.5`, wet `L^0.85` |
| Echo | 1/16–16 beats | Superpowered Echo (dry 0, wet 1) at the deck BPM; feedback `0.3 + 0.52·L`; the beat length glides when changed |
| Ping Pong | 1/16–16 beats | two Superpowered Echoes on left and right, plus a delay of half the time on one side, re-interleaved |
| Spiral | 1/16–16 beats, ≥10 ms | Tribe-built feedback delay (see "Inside the effects"); length from the time (or X-pad `30 + 970·x` ms); feedback climbing toward 1.0 with Level |
| Reverb | 1/16–2 "beats" = 1–100 % | Superpowered Reverb (wet 1, damping 0.1), room size from the Time %, then a filter at `100 + 11900·p^3` Hz (Parameter / X-pad) |
| Trans | 1/16–16 beats | gate synced to the BPM, chopping at half the interval; wet 0.8–1.0 |
| Filter | 1/16–64 beats | filter swept by an LFO synced to the BPM, 200 Hz–18 kHz; resonance `0.1 + 0.1·L` |
| Flanger | 1/4–64 beats, ≥80 ms | Superpowered Flanger (depth 0.05, stereo), LFO period = the time; wet `L^0.25` |
| Phaser | 1/16–64 beats | Tribe 6-stage phaser; its LFO period is (interval in beats)/2 seconds whatever the BPM, so it matches the time only at 120 BPM; depth `0.8 + 0.2·L`, feedback 0.9; wet `L^0.3` |
| Pitch | −50 % … +100 % | Superpowered time-stretching used as a pitch shifter, up to ±2400 cents (2 octaves), scaled by `L^0.4` |
| Slip Roll | 1/16–4 beats | Superpowered Roll with Tribe's level logic: dry `0.5 + 0.15·L` during the first repeat, then `1 − L^0.4`; wet `L^0.3` (see "Inside the effects") |
| Roll | 1/16–4 beats | Superpowered Roll (wet, bpm, beats); same levels as Slip Roll |
| Vinyl Brake | 1/16–16 beats | passes the music dry (dry 1, wet 0); no mixer model offers it |
| Helix | 1/16–16 beats | Tribe-built 32 s loop that re-pitches the held slice when the interval changes, and fades it after release (`0.001^(1/length)` per sample) |
| Shimmer | 1–100 % | no processing (time handled like Reverb's); no mixer model offers it |
| Slip Loop | 1/16–16 beats | no processing; no mixer model offers it (the deck's slip loop is a CDJ-3000X screen feature) |
| Triplet Filter | 1/12–4 beats | Filter on triplet intervals |
| Triplet Roll | 1/12–4 beats | Roll on triplet intervals |
| Megaphone | 1/16–64 beats | no Beat FX processing; it is the DJM-A9's mic FX (see "Mic FX" in "Inside the effects") |
| Mobius | −64…+64 beats | Tribe-built: adds a synthesized Shepard–Risset glissando over the music; period 2 × time (10 ms–60 s), direction from the sign; fully wet; level a piecewise curve of Level |

## Mic FX

The mic stage (`FUN_047afa28`) runs in this order:
1. With mic mode on, the mic EQ.
2. With the mic FX on, the mic FX unit (`FUN_047ab760`). It holds the type, Parameter and reverb on/off
   (`SetActiveMicFx`, `SetMicFxParameter`, `SetMicReverbEnabled`).
3. If Beat FX targets the mic, the Beat FX engine with the same band and level handling.

## Inside the effects

Read 2026-10-27 from the effect objects themselves. Each is a small C++ object whose first virtual is
`process(in, out, frames)` on interleaved stereo; Tribe's vtables sit at Ghidra 0x74d6d78–0x74d6eb8. The
Superpowered pieces they use (Echo, Reverb, Filter, Gate, Roll, Whoosh, Limiter, ...) are in
`claudedocs/superpowered_dsp.md`. Bulk decompiled C: `D:/TribeUE/tribe_native/fx/` (`tribefx_vtables.c`,
`module_all.c`, `beatfx_dispatch.c`, `colorfx_*.c`, `micfx.c`); script `scripts/FxProbe.java` via
`scripts/ghidra_probe.sh`.

Filter Q below comes from the SDK's resonance setting: Q = 10 × resonance **(read: the coefficient code)**.

### What the Beat FX engine holds

Its constructor (0x47a520c) builds one object per effect **(read)**:

| Slot | Object | Used by |
|---|---|---|
| +0x98 | Superpowered 3-band EQ | the LOW / MID / HI band selection on the wet signal |
| +0xa0 | Superpowered Delay (32 s) | Delay |
| +0xa8 | Superpowered Echo | Echo |
| +0xb0, +0xb8, +0xc0 | two Echoes and a Delay | Ping Pong |
| +0xc8 | Tribe Spiral | Spiral |
| +0xd0, +0xd8 | Superpowered Reverb, then a Filter | Reverb |
| +0xe0 | Superpowered Gate | Trans |
| +0xe8 | Superpowered Filter (low-pass) | Filter, Triplet Filter |
| +0xf0 | Superpowered Flanger | Flanger |
| +0xf8 | Tribe Phaser | Phaser |
| +0x100 | Superpowered time-stretching (minimum rate 0.01) | Pitch |
| +0x108 | Superpowered Roll | Slip Roll |
| +0x110 | Superpowered Roll | Roll, Triplet Roll |
| +0x118 | Tribe Helix | Helix |
| +0x120 | Tribe Mobius | Mobius |

X-PAD intervals **(read: tables 0x89dc10, 0x89dc40, 0x89dc88)**: most effects 1/16, 1/8, 1/4, 1/2, 3/4, 1 beat;
Helix 1/16, 1/12, 1/8, 1/6, 1/4, 1/3, 1/2, 2/3, 1; Triplet Roll 1/6, 1/4, 1/3, 1/2, 2/3, 1.

### Spiral

Vtable 0x74d6e90, `process` 0x47ba59c, setup 0x47a98f4. A stereo feedback delay with a 3.99 s buffer **(read)**.
- **Path per block (read):** input → low-pass 12 kHz (Q 0.71) → + the previous block's feedback → Superpowered
  Limiter (keeps the loop from running away) → high-pass 150 Hz (Q 0.3) → low-pass 12.1 kHz (Q 0.7) → delay line →
  wet → low-pass 10 kHz (Q 0.3) → × level. While the tail rings out the input is silence.
- **Delay time (read):** glides to the target with a 0.4 s one-pole (`1 − e^(−1/(0.4·sr))` per sample) and is
  swept ±5 ms by a 1 Hz triangle; reads interpolate linearly. The glide is what bends the repeats' pitch when the
  interval changes **(inferred)**.
- **Mapping (read):** feedback `8·L` below L = 0.1, 0.8 up to L = 0.5, then `0.386·L + 0.607` (0.993 at L = 1); in
  the tail `(L − 0.5)·0.4 + 0.8` (1.0 at L = 1). Delay = the beat time clamped to 10 ms–3.99 s, or X-PAD
  `30 + 970·x` ms. Engine dry 1, wet `L/0.75` (1 from L = 0.75).
- It also keeps a dB peak meter of the wet tail (+0x114); what reads it wasn't traced.

### Phaser

Vtable 0x74d6e68, `process` 0x47b9c88, per-sample 0x47b9d8c; built inline in the engine constructor **(read)**.
- **Six first-order allpass stages** per channel. Coefficient `a = (1 − w·c)/(1 + w·c)` with c = 0.95, 0.85, 0.75,
  0.65, 0.55, 0.45, where one triangle LFO sweeps w from `800/(sr/2)` to `10000/(sr/2)`. The right channel's LFO is
  90° ahead **(read)**.
- **Feedback:** `tanh(last output) × feedback` is added to the input, and a one-pole low-pass (pole
  `1/(1 + 1/(2π·8000/(sr/2)))`, about 0.68 at 48 kHz) smooths that sum **(read)**.
- **Output:** `input + depth × allpass output`, then mixed with the dry input by mix. Depth, feedback and mix glide
  with a 20 Hz one-pole **(read)**.
- **Mapping (read):** depth `0.8 + 0.2·L`, feedback 0.9, mix 1; engine wet `L^0.3`, dry `1 − L^0.3`.
- **The LFO ignores the BPM.** The setup writes a phase step of `2π·(beat ms / interval ms)/sr`, which is `1/beats`
  Hz at any tempo, and the per-sample function advances it once per channel, so twice per frame. The LFO period is
  therefore `(interval in beats)/2` seconds: right at 120 BPM only **(read; computed: a 4-beat interval is 2.0 s at
  every tempo, against 1.71 s at 140 BPM and 1.38 s at 174 BPM)**.

### Helix

Vtable 0x74d6dc8, `process` 0x47b7f1c, setup 0x47aad8c, start and release in the dispatcher (0x47a8580, case 14).
A 32-second stereo loop with a fractional read/write head **(read)**.
- **Capture (read):** the loop length is the beat time (50 ms–32 s) or an X-PAD step.
- **Each sample (read):**
  1. Read at (head − loop length) with monotone cubic interpolation: tangents are half the neighbour differences,
     zeroed when their sign disagrees with the segment, limited to 3× its slope; the result is clamped between the
     two neighbours.
  2. Low-pass at `clamp(18000/max(speed,1) × (0.5 + 0.5·min(1, loop/0.2 s)), 4 kHz, 18 kHz)`, or 8 kHz once the
     speed has settled.
  3. Write back `feedback × that + input gain × input`; that is also the output.
- **Changing the interval while it holds** doesn't re-cut the loop: speed = old length / new length (0.01–8×),
  gliding with a 0.4 s one-pole, with an extra low-pass at `12 kHz × speed` (≥ 1 kHz) while it glides below 1×
  **(read)**. So the held slice is re-pitched **(inferred: the "helix" sound)**.
- **Release (read):** input stops; the loop keeps repeating, its gain falling by `0.001^(1/max(loop, 4 s))` per
  sample (−60 dB over the loop length, at least 4 s) and scaled by `0.95 − 0.55·t`, t = loop length mapped
  30 ms–4 s to 0–1. It ends below 0.0001.
- **Mapping (read):** L < 0.5: feedback `1.115·L^0.263`, input gain `4L² − 3.4L + 1`; L ≥ 0.5: feedback
  `0.8 + 0.2·L`, input gain `0.6 − 0.6·L`. Engine wet 1, dry 0 (1 while the tail rings out).

### Mobius

Vtable 0x74d6df0, `process` 0x47b91bc, oscillator 0x47b965c, setup in the dispatcher (case 20).
Not an effect on the music: it **adds a synthesized Shepard–Risset glissando** **(read)**.
- **Voices (read):** four, two octaves apart, at `55·2^(8·phase + 2k)` Hz (k = 0–3, wrapping over 8 octaves, so
  55 Hz–14 kHz), each weighted by `exp(−0.5·log2(f/440)² / 6.25)`: a Gaussian 2.5 octaves wide around 440 Hz.
- **Timing (read; derived):** the phase moves every other frame, so a full cycle takes 4 × the interval and the
  2-octave pattern repeats once per interval. The interval's sign sets up or down.
- **Waveform (read):** each voice is a band-limited oscillator (PolyBLEP-style corrections; the name is mine).
  Parameter morphs square → saw over 0–0.5 and saw → triangle over 0.5–1.
- **Output (read):** the tone (× level × 0.08) goes into a cross-coupled stereo delay (74 ms left, 11.3 ms right,
  feedback 0.8); each output channel gets music + tone + delay return × 0.3.
- **Level (read):** `0.32·L² + 0.08·L` up to L = 0.5, then `4.56·L² − 4.58·L + 1.27` (1.25 at L = 1). The engine runs
  it fully wet; the music passes through inside the object.

### Phantom Echo, Vaporize and Noise Chopper (V10/A9 unit 0x47a4a1c)

- **Phantom Echo** (constructor 0x47b9a30): the knob's low-pass and high-pass on the channel (resonance 0.1, Q 1),
  then a send into a Superpowered Echo (dry 0, wet 1, ½ beat, decay 0.75, at the mixer BPM), summed back by a 4-input
  stereo mixer **(read)**. Its `process` stub (0x47b9c7c, `ldp x8, x4, [x0, #0x18]`) hands the object's 3-band EQ
  (low 0, mid 1, high 1) to the Echo as its feedback effect, so **every repeat loses its lows** **(read: the
  disassembly and the Echo's fifth parameter)**.
- **Vaporize** (constructor 0x47ba93c): the same filter pair (resonance 0.15), then a send into a Superpowered
  Reverb: dry 0, wet 1, room size 0.81, pre-delay 80 ms, low cut 130 Hz, damping `0.6·|knob|` (the "vapor"). Its
  `process` is the Reverb's own **(read)**.
- **Noise Chopper** (0x47b99d0): in place on the channel, a Superpowered Whoosh (filtered white noise, wet 0.5,
  frequency = the knob curve), then a Superpowered Gate at the mixer BPM **(read)**.

### Slip Roll

Setup 0x47aaa08. A Superpowered Roll, not a Tribe object **(read)**. Tribe adds:
- when the beat length changes, the Roll is switched off for one block so it captures a fresh slice;
- during the first repeat the dry level is `0.5 + 0.15·L` (the music stays audible), then `1 − L^0.4`; wet
  `L^0.3`.

### The V10 send delays

Vtable 0x74d6d78, `process` 0x47b7ae4, built by the send unit's constructor (0x47a4014) together with two
parametric filters (type 6) and a Reverb **(read)**:
- Tribe-built stereo delays with 1 s buffers (48,001 samples per channel), linear interpolation, feedback and wet.
- The delay time moves linearly each block toward a target smoothed by a 50 Hz one-pole. Start values 0.0999 s,
  0.388 s and 0.129 s.

### Mic FX

Unit 0x47ab760, setup 0x47abba0, constructor 0x47ab4bc. It holds an Echo, a low-pass and a high-pass, a
time-stretcher, a Bitcrusher, Tribe's clipper (vtable 0x74d6da0, 0x47b7cf4), a Reverb and a 4-input mixer **(read)**.
P is the mic FX knob, −1…+1.
- **Echo:** low-pass at 20 kHz (P > 0) or 2 kHz (P ≤ 0), resonance 0.04, then an Echo at the BPM, 1 beat, decay
  `0.4 + 0.35·|P|`; mix dry `1 − |P|^0.8`, echo `|P|^0.8` **(read)**.
- **Pitch:** time-stretching on the mic at `round(1200·P)` cents (±1 octave). The shifted signal replaces the mic once
  the stretcher has a full block **(read)**.
- **Megaphone** (only the DJM-A9 has the button):
  - a high-pass at 1,240 Hz left at the SDK's default resonance 1.0, i.e. Q 10, a **+20 dB peak at 1.24 kHz**
    **(read; computed)**;
  - then, for P ≥ 0.33, the Bitcrusher: sample rate sr/8 → sr/16 over P 0.33–0.66, then 15 → 8 bits over
    0.66–1;
  - for P < 0, Tribe's hard clipper instead: clip at `±10^(−d/20)`, output `× 10^(d/40)`, with d = 0.2 down to
    P = −0.33, rising to 1.0 at P = −1 (a mild clip);
  - the effect fades in over |P| 0–0.33 (dry `(0.33 − |P|)/0.33`); above 0.33 the output gain rises to 2× at
    |P| = 1 **(read)**.
- **Reverb:** a send at the reverb level into a Superpowered Reverb, which keeps ringing (input cut) when switched off
  **(read)**.

### Shimmer, Slip Loop, Megaphone and Vinyl Brake as Beat FX

- The dispatcher has no case for Shimmer (15), Slip Loop (16) or Megaphone (19). Vinyl Brake (13) only sets dry 1,
  wet 0 **(read)**.
- No mixer offers any of the four as a Beat FX **(read: every model's `AvailableBeatFX` default in the Blueprint
  dumps: BP_Console, DJM-A9, DJM-900NXS2, DJM-V10, DDJ-FLX4)**. Shimmer's time is still computed like Reverb's.
- Where they exist instead: Megaphone is the A9's mic FX (above). The deck's own stop brake is
  `BP_Deck.TouchBrake` → the player's `Pause(seconds)` deceleration, and Slip Loop is the CDJ-3000X screen's slip
  loop (`BP_ScreenLoopJumpButton`), both outside the mixer **(read: Blueprints)**.

### Still not read

- Inside Superpowered's player, time-stretcher, Spatializer, Compressor and Limiter loops: see
  `claudedocs/superpowered_dsp.md` for what was recovered.
- What reads Spiral's peak meter, and the per-type table flag at 0x89d748 + 0x18.
