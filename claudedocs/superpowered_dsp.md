# Superpowered's DSP inside Tribe XR

What the Superpowered SDK code linked into Tribe's `libUnreal.so` (build 2304) does, read from the decompiled binary
on 2026-10-27. It complements `claudedocs/mixer_effects.md`, which covers what Tribe feeds these objects and Tribe's own
effects. This is a behaviour reference for building our own engine, not code to port.

- **Where it is:** the SDK's code occupies Ghidra 0x6cec000–0x6d70000, next to its licence check
  ("Invalid Superpowered license key.", 0x6cf6e50).
- **Outputs:** every function in that range decompiled is in `D:/TribeUE/tribe_native/fx/sdk_all.c` (828 functions,
  1 failed); vtable dumps are in `probe2.txt` and `probe3.txt` there.
- **Tools:** `scripts/FxProbe.java`, run with `scripts/ghidra_probe.sh` (read-only, about 50 s per run).

Labels as in `native_summary.md`: **(read)** means the decompiled code shows it; **(inferred)** rests on names, layouts
or the SDK's public API.

## How the classes were named

The binary has no symbols or type names for the SDK, so each name rests on three independent routes:

1. **Vtable order.** The effects' vtables sit in one run at 0x7b9c990–0x7b9cb20, 0x28 bytes apart: `process`, then
   two destructors. They come in the alphabetical order of Superpowered's source files: 3BandEQ, Bitcrusher,
   Compressor, Echo, Filter, Flanger, Gate, Limiter, Reverb, Roll, Whoosh. Delay has no vtable, matching an SDK class
   that isn't an effect subclass **(read: the order; inferred: the file names)**.
2. **Constructor signatures and sizes.** These match the SDK's public API **(read: the calls)**:
   - `Echo(samplerate, 96000)`, `Reverb(samplerate, 96000)`, `Roll(samplerate, 96000)`;
   - `Delay(maxDelayMs, maxSamplerate, maxFrames, samplerate)`;
   - `TimeStretching(samplerate, minimumRate)`;
   - `Filter(type, samplerate)`.
3. **Parameter clamps inside each `process`.** For example Echo beats 1/32–2, bpm 40–250, decay 0–0.99; Gate and Roll
   beats 1/64–4; Reverb pre-delay 0–500 ms; Whoosh frequency 20–20,000 Hz **(read)**. They match the ranges the SDK
   documents for those classes **(inferred: from memory of the SDK headers; not re-checked against a copy)**.

On top of that, the Reverb's delay lengths equal Freeverb's published tunings and the Filter's coefficients are the
RBJ cookbook formulas (below), so those two are pinned by their algorithms alone.

## Common machinery

- **Effect base layout (read):**

  | Offset | Field |
  |---|---|
  | +0x0 | vtable |
  | +0x8 | `enabled` byte |
  | +0xc | sample rate |
  | +0x10 on | the class's public parameters |

  `process(in, out, frames)` works on interleaved stereo floats.
- **Fades on enable/disable (read):** each effect keeps a small state machine (off, starting, on, stopping). Echo
  and Reverb keep running after `enabled` goes false until their tail falls below 1e-5, then reset.
- **Parameter ramps (read):** dry/wet/decay and similar move linearly across one block instead of jumping (shared
  helpers: `Volume` 0x6d36610, two-input mix with two gain ramps 0x6d36a6c, `Peak` 0x6d36c74).
- **Licence gate (read):** most entry points `abort()` if the SDK wasn't initialised (flag at 0x80b4578).
- **NEON:** the inner loops are vectorised, typically 4 frames at a time with a scalar tail.

## The effects

### Echo (0x7b9ca08; `process` 0x6cee8b0)

- **Parameters (read):**

  | Offset | Parameter | Range / default |
  |---|---|---|
  | +0x10 | dry | 0–1 |
  | +0x14 | wet | 0–1 |
  | +0x18 | bpm | 40–250, default 128 |
  | +0x1c | beats | 1/32–2, default 0.5 |
  | +0x20 | decay | 0–0.99, default 0.5 |
- **Algorithm (read):** a ring buffer whose length is the delay itself, `beats × 60/bpm × samplerate` frames
  (integer; a change takes effect without interpolation). Per chunk: `ring = input + decay × delayed`, then
  `output = dry × input + wet × delayed`. Dry, wet and decay ramp across the block.
- **Capacity (read):** 3 × the maximum sample rate in floats, i.e. 3 s at 48 kHz.
- **Optional feedback effect (read):** `process` takes a fifth argument, an effect run on the ring after each write.
  The public `process` passes none (`mov x4, xzr`). Tribe's Phantom Echo passes a 3-band EQ that kills the lows.

### Delay (constructor 0x6ceefb0; `process` 0x6cef128 → 0x6cef3c0)

- A plain ring buffer: integer delay of `delayMs × samplerate / 1000`, no feedback **(read)**.
- `process(input, frames, fx)` returns a pointer to the delayed samples; the optional `fx` (for example the Reverb's
  low shelf) runs on them **(read)**.

### Reverb (0x7b9cad0; constructor 0x6cf33fc; `process` 0x6cf3cd0)

**Freeverb**, with changes **(read)**:
- **Structure:**
  - 8 parallel combs of 1116, 1188, 1277, 1356, 1422, 1491, 1557 and 1617 samples (right channel +23);
  - then 4 serial allpasses of 556, 441, 341 and 225 (+23), feedback 0.5;
  - input gain 0.015.
  
  Lengths are in samples and not rescaled for the sample rate.
- **Parameters:** dry +0x10, wet +0x14, mix +0x18, width +0x1c, damp +0x20, roomSize +0x24, predelayMs +0x28
  (0–500), lowCutHz +0x2c. Constructor defaults: dry 0.987, wet 0.588, mix 0.4, width 1, damp 0.5, room 0.8.
- **Mapping:**
  - damping `0.4 × damp`;
  - comb feedback `2r − r²` for room r ≤ 0.98 (0.98 above), not Freeverb's `0.7 + 0.28r`: 0.75 at r 0.5, 0.96 at
    0.8;
  - width: `wet × (width/2 + 0.5)` and `wet × (1 − width)/2`;
  - **mix** sets dry/wet with an equal-power curve: wet `sin(mix·π/2)`, dry 1 below mix 1/3, then
    `cos((mix − 1/3)·3π/4)`.
- **Pre-delay and low cut:** pre-delay is a Superpowered Delay (500 ms max). Low cut is a −12 dB **low shelf**
  (slope 0.1), not a high-pass, active above 20 Hz.
- **Processing:** blocks of 1024 frames, one comb/allpass bank per channel (0x6cf4950).

### Filter (0x7b9ca30; constructor 0x6cef57c; `process` 0x6cef750; coefficients 0x6cefd88)

- **Parameters (read):**

  | Offset | Parameter | Default |
  |---|---|---|
  | +0x10 | frequency | 1000 Hz |
  | +0x14 | decibel | 0 |
  | +0x18 | resonance | 1.0 |
  | +0x1c | octave | 1.0 |
  | +0x20 | slope | 0.001 |
  | +0x24 | type | – |
- **Types (read):**
  - 0 resonant low-pass and 1 resonant high-pass use frequency + resonance;
  - 2 and 3 (band-pass, notch) use octave;
  - 4 and 5 (low and high shelf) use slope + decibel;
  - 6 (parametric) uses octave + decibel.
  
  The names of types 2–6 are inferred from the parameters they read.
- **Coefficients (read):** RBJ cookbook biquads with `w = 2π·f/sr` and `α = sin(w)/(20·resonance)`, so
  **Q = 10 × resonance**. Resonance is clamped 0.01–1 (Q 0.1–10) and frequency to 1 Hz–Nyquist.
  - Low-pass: `b0 = (1 − cos w)/2 ÷ (1 + α)`.
  - High-pass: `b0 = (1 + cos w)/2 ÷ (1 + α)`, `b1 = −(1 + cos w)`.
  - Checked numerically: resonance 0.0707 gives −3.01 dB at the corner (Butterworth); 1.0 gives a +20 dB peak.
- **Processing (read):** direct form, 4 frames at a time from precomputed block coefficients. A second coefficient
  bank crossfades changes.

### 3-band EQ (0x7b9c990; constructor 0x6cec75c; `process` 0x6ceca80)

- Gains low +0x10, mid +0x14, high +0x18, linear 0–8 **(read)**.
- **Built from SDK Filters (read):** a low shelf at 200 Hz, a 1.2 kHz band four octaves wide, and a 5 kHz band; each
  is set to `20·log10(gain)` dB.
- **Kill (read):** a band below 0.01 switches to a kill path (notch and parametric filters in the constructor). Tribe
  uses gains of exactly 0 and 1 for Beat FX band selection.

### Flanger (0x7b9ca58; constructor 0x6cf1610; `process` 0x6cf19dc)

- **Parameters (read):**

  | Offset | Parameter | Range / default |
  |---|---|---|
  | +0x10 | wet | default 0.7 |
  | +0x14 | depth | 0–1, default 0.16 |
  | +0x18 | lfoBeats | 0.25–128, default 16 |
  | +0x1c | bpm | 40–250, default 128 |
  | +0x20 | clipper threshold | −3 dB |
  | +0x24 | clipper maximum | +6 dB |
  | +0x28 | stereo | – |
- **Algorithm (read):** the delay sweeps from 0.3 ms to `0.3 + 7.7·depth` ms under an LFO locked to bpm × lfoBeats.
  A 180 Hz high-pass biquad (Q 1) sits in the flanged path, and a clipper sits on the output.
- Not traced: the LFO's exact shape and the stereo option's phase.

### Gate (0x7b9ca80; `process` 0x6cf26a4) and Roll (0x7b9caf8; `process` 0x6cf5918)

- **Parameters (read):** wet +0x10, bpm +0x14 (40–250), beats +0x18 (1/64–4).
- **Gate (read):** opens and closes every `beats` beats (a 50 % square). The gain moves linearly to the new level
  across one block. The level when closed comes from wet: dry 1 up to wet 0.05, then `1 − (wet − 0.05)/0.95`.
- **Roll (read):** captures a `beats`-long slice and repeats it, with the same dry rule; wet gain is `wet/0.95`
  capped at 1.
- **Changes (read):** a new beats value is taken only on the grid (position within a 4-beat bar within 0.05 of a step).

### Whoosh (0x7b9cb20; constructor 0x6cf6048; `process` 0x6cf6308)

- Parameters: wet +0x10 (default 0.4), frequency +0x14 (20–20,000 Hz, default 500) **(read)**.
- **Algorithm (read):** integer white noise (scaled by 1/2³¹) through a resonant low-pass biquad at the frequency
  (Q 2), at a level of 0.3 up to 1 kHz falling to 0.15 at 20 kHz, mixed into the signal by wet.
- Tribe uses it as the NXS2 "Noise" effect and Noise Chopper's source.

### Bitcrusher (0x7b9c9b8; constructor 0x6ced2ac; `process` 0x6ced3b4)

- Parameters: frequency +0x10 (int, default 8,000), bits +0x14 (byte) **(read)**.
- **Algorithm (read):** a sample-and-hold whose phase advances by `frequency/samplerate` per sample, then
  quantisation to `bits` (`round(x·2^bits)/2^bits`). It crossfades in and out over one block when switched.
- **Clamps (read):** bits 1–16; frequency from 20 Hz up to Nyquist. Bits 16 at the Nyquist rate counts as bypass.

### Compressor (0x7b9c9e0; constructor 0x6ced8f4; `process` 0x6ceda40) and Limiter (0x7b9caa8; 0x6cf2bc4 / 0x6cf2d04)

- **Compressor parameters (read):** constructor defaults wet 1, attack 0.003 s, release 0.3 s, ratio 3, threshold
  0 dB, side-chain high-pass 1 Hz. Clamps: attack 0.0001–1 s, high-pass 1–10,000 Hz. Time constants are
  `exp(−0.2231/(t·sr))`, i.e. 80 % of the change in `t`. The side chain has a high-pass biquad active above 20 Hz.
- **Limiter parameters (read):** threshold clamped −40…0 dB, release 0.001–1 s; gain `10^((dB − 0.5)/20)`.
- **Not read:** the gain-computer loops of both (knee, look-ahead). Tribe uses the Compressor on each channel and a
  Limiter inside Spiral.

## Mixing, output and spatialisation

- **Stereo mixer (`process` 0x6d35e90 → 0x6d374a0, read):** four stereo inputs, each with left/right gains that ramp
  across the block, summed with an output gain, with peak meters. Tribe uses it for Color FX returns, the mic and the
  output stage.
- **Spatializer (0x6d610cc, 7,152 bytes):**
  - Tribe's output stage calls it once per virtual monitor **(read)**.
  - Its constants are angle steps (15°, 30°, 45°, 60°, 75°, 90°, 180°, 270°, 345°, 360°; 1/15 and 1/90), 7 and
    9 kHz, and 64. That points to interpolation between measured directions, an HRTF-style table **(inferred)**.
  - **Not read** line by line.

## Time-stretching (constructor 0x6d632dc; addInput 0x6d64240 → 0x6d642b8; getOutput 0x6d65ca8 → 0x6d5c110)

- **Frame size (read):** 2,048 samples when a minimum rate is given, 512 otherwise. Tribe always passes 0.01, so
  2,048-sample frames (43 ms at 48 kHz) for both the Pitch Beat FX and the mic Pitch FX. The minimum rate floors at
  0.01.
- **Quality setting (read):** byte +0xc (the SDK's `sound`) changes how many bins are processed: half the frame
  minus 64 for setting 2, otherwise 64.
- **The core (6.6 KB) is not readable:** NEON-vectorised butterflies with no trig calls, plus helpers
  (0x6d66a30, 0x6d67e70). That they form an FFT, i.e. a frequency-domain stretcher, is **(inferred)** from the
  power-of-two frames and the code's shape.
- **Constants seen in the core (read; their roles not traced):** 6879.6, 0.8, 0.03, 1.1, 0.75, 0.35, 0.25, 0.15.
- **API (read: Tribe's calls):** addInput, getOutputLengthFrames (0x6d640f8), getOutput, reset (0x6d6413c); pitch
  in cents at +4.

## The deck player

- **Tribe's deck calls only part of the player's public API.** Pairing each Tribe deck function with the SDK
  function it calls names them **(inferred from usage)**:

  | SDK function | Tribe uses it as |
  |---|---|
  | 0x6d5339c | process |
  | 0x6d5310c | open |
  | 0x6d52630 | setPosition |
  | 0x6d52b8c | loop |
  | 0x6d52da4 | exitLoop |
  | 0x6d5233c | isLooping |
  | 0x6d52710 | setReverse |
  | 0x6d5236c | reverse state |
  | 0x6d5277c → 0x6d59c54 | pitchBend |
  | 0x6d527e4 | endPitchBend |
  | 0x6d5237c | position |
  | 0x6d52388 | display position |
  | 0x6d52394 | position as a fraction |
  | 0x6d523a0 | duration |
  | 0x6d52410 | closest beat |
  | 0x6d5232c | bpm |
  | 0x6d523ac | latest event |
  | 0x6d523ec | end-of-file flag |
  | 0x6d5234c | scratching state |

- **Public fields Tribe writes directly (read):** `timeStretching` +0x10 (Master Tempo on, unless the jog is in
  mode 3); `pitchShiftCents` +0x60 (Tribe clamps ±1200); the playback rate is the double at +8.
- **The core (0x6d53cf4, 15.8 KB) is only partly read:**
  - Commands from the game thread arrive lock-free (exclusive-monitor loops); pitch bend, for example, is queued as
    a 0x28-byte record **(read)**.
  - Each block pulls decoded audio from a buffer pool (0x6d5b8a0..) **(read)**.
  - The audio then runs through the varispeed resampler (0x6d600b8, which keeps 5 frames of history: 6-point
    interpolation, plain copy at rate 1) or through time-stretching (calls 0x6d642b8 / 0x6d5c110 / 0x6d6413c)
    **(read: the calls; the interpolation kernel not read)**.
  - Jumps, loops, start and stop are de-clicked with a 64-step raised-cosine table, `0.5·(1 + cos(πk/64))`,
    inlined six times **(read)**.
- **Pitch bend (0x6d59c54, read):** the rate moves 4 % of the remaining gap per call toward `(1 ± max) × rate`.
  `max` is clamped 0.01–0.3 (0.5 with the default 100 ms hold), and the hold time is in ms.
- **Jog, slip and loops are Tribe's own code** around the SDK (in `SuperPowered.SuperPoweredAudioPlayer.c`, render
  0x479dce0):
  - **Nudge** (jog mode 1, read): 2,300 ticks per platter turn become pitch-bend commands, capped at 30 % and scaled
    by jog speed (full at 360°/s).
  - **Scratch** (mode 2, read): playback rate = platter turns per second × 1.8, so 33⅓ RPM plays at normal speed
    (0.556 rev/s × 1.8 = 1.0; derived).
  - **Not decompiled:** the mode switch (0x479c988) jumps through a table Ghidra didn't recover, so modes 3–5 and
    the slip state machine (0x4797a68) aren't read.

## Not read, and why

- Time-stretching's core and the Spatializer: NEON-heavy, no recoverable math beyond the constants listed.
- The Compressor's and Limiter's gain computers, and the player core beyond the parts above: large functions, only
  their parameters and structure traced.
- The other vtables at 0x7b9cb80–0x7b9cd68 and 0x7b9d2c0–0x7b9d388 (large open/seek/read-style functions): decoders
  and I/O by their shape **(inferred)**, not DSP.
