# How Tribe analyses a track (Superpowered's Analyzer)

This note covers how Tribe XR build 2304 works out a track's BPM, beat grid, key, loudness and waveforms. It was read
from the decompiled `libUnreal.so` on 2026-10-28.

- **Who does what.** The analysis is the Superpowered SDK's `Analyzer`, which is statically linked into Tribe.
  Tribe's own code decides when it runs, what audio it gets and which numbers you see.
- **What this note is for.** It is a behaviour reference for our own detectors in `D:/VRDJ/engine/analysis`,
  written in our own words.
- **What stays private.** Decompiled listings, constant tables and test scripts stay in the private research folder
  `D:/TribeUE/tribe_native/analyzer/`. They must never be copied into `D:/VRDJ`.
- **Related notes:** `superpowered_dsp.md` (the SDK's effects and deck player), `mixer_effects.md`,
  `deck_catalog.md` and `native_reference.md`.

**Labels:**
- **(read: …)** means seen in the decompiled code or the raw disassembly at that Ghidra address, or in the named
  file.
- **(derived)** means it follows from read code, or from arithmetic on it.
- **(measured)** means it comes from a private re-creation of the method, run on your 39 SoundCloud MP3s in
  `C:/Users/Chris/Music/BRAND NEW SHIT`. It was not observed in Tribe itself.
- **(simulated)** means synthetic test signals were run through a private re-statement of the key scorer. Those
  numbers are indicative only.
- **(assumed)** means plausible but not checked.

Addresses are Ghidra addresses. Ghidra address = ELF vaddr + 0x100000 = runtime RVA + 0xFF000.

---

## The short answer

**Tribe analyses your SoundCloud tracks itself, from the audio, exactly the way it analyses a file on the headset.**
Nothing is looked up online. The one exception is SoundCloud's own track data. If it includes a BPM or a key, Tribe
shows that instead of its own result (read: details below).

### How it does it, in plain words

- **When it runs.**
  - Loading a track on a deck analyses it straight away (read).
  - Pressing **Analyze** in the track browser queues every track in the folder. Two run at a time and the rest wait
    in the "N In Queue" list (read).
  - A SoundCloud track is analysed from its downloaded audio in memory. In a SoundCloud playlist, Analyze skips any
    track that hasn't been downloaded yet (derived; not seen in Tribe). Such a track gets analysed when you load it
    (read).
- **What it listens with.** There is no FFT. The song runs through 56 filters, most of them very narrow, like a
  graphic EQ with 56 sliders (read):
  - 48 sliders sit on the piano notes from A2 (110 Hz) to G#6 (1.66 kHz);
  - two are a sub band (45 Hz) and a bass band (135 Hz);
  - two are thin "tick" bands at 2 kHz and 9 kHz;
  - the last four are wider: three give the low/mid/high waveform colours, and one (1 kHz) only helps spot hits.

  Every band is read 150 times a second.
- **Tempo, step 1 (rough).** The analyzer watches the sub, bass and tick bands pulse. It asks which beat length makes
  that pulse repeat best 1, 4, 8, 16 and 32 beats later (read).
  - A built-in preference for about 130 BPM settles close calls. At 140 BPM a candidate keeps 99% of its score; at
    70 it keeps 71% (read, re-derived).
  - This step only decides where to look closer.
- **Tempo, step 2 (exact).** It marks every hit from the loudest-sample curve, in 40 ms slices. Then it measures the
  gap between every pair of hits, not just neighbouring ones, up to five minutes apart (read).
  - The longest gap that still agrees sets the decimals.
  - Whole numbers beat .5s, which beat tenths.
  - If the rough tempo sits in 75–100 or 150–200 BPM, it tries both the slow and the fast reading, and a tie goes to
    the slow one.
  - The answer is a whole number or has two decimals. Anything from x.50 upwards is pushed up to the next whole
    number, except when the rough tempo was 75–100, where two decimals are always kept.
- **Beat grid.** It looks for a chain of hits that lands on the beat for at least 16 beats, with no more than two
  misses in a row (read).
  - Hits come from the bass-note bands and from the attacks in the tick bands.
  - A quiet-to-loud drop entry counts extra.
  - The strongest chain pins the grid. The pin is slid back into the first bar, then a few milliseconds earlier onto
    the start of the attack.
  - It does not work out which beat is the "1" of the bar (read, measured).
  - With no chain, the grid starts at 0 ms (read).
- **Key.** It adds up how much of each note (A, A#, B … G#) sounds over the whole song, between 110 Hz and 1.66 kHz,
  ignoring the octave. That 12-note fingerprint is compared with four sets of major and minor "key shapes". Each set
  votes, and the key with the most votes wins (read).
  - It never says "unknown". Silence comes out as A major (derived).
- **Loudness and waveform.** It keeps the following (read):
  - the peak and average level 150 times a second;
  - three band levels for the coloured waveform;
  - a one-point-per-second overview in dB;
  - three numbers: peak dB, average dB, and the average of the loud parts.
- **One answer per file.** Each file gets one tempo, one grid start and one key, with no confidence value. A failure
  shows up as 0 (read).

### What you see on the deck

Tribe keeps two sets of numbers per track (read: `GetBpm` 0x511e7f4, `GetBeatgridStartMs` 0x513c12c, `GetKeyIndex`
0x511e808):
- **"metadata"**, which comes from SoundCloud's or Beatport's own data, from a file's BPM tag, or from your own grid
  edits in Tribe;
- **the analyzer's.**

Whenever the metadata has a value, it wins:
- **SoundCloud's BPM** is used when it lies between 20 and 300. SoundCloud's key is used when its key string parses
  (read).
- **Beatport's BPM and key** are used whenever Beatport supplies them, with no range check (read). That is why
  Beatport tracks show store numbers and SoundCloud tracks usually show the analyzer's.
- **How often SoundCloud has a BPM** for the uploads you play is unknown (assumed: rarely).
- **Your 39 downloaded MP3s carry no BPM or key tags** (read: tag scan of all 39). Played as files, they always show
  the analyzer's numbers.

### What that means for heavy dubstep at 140–150 BPM

- **150 BPM riddim can come out as 75** (measured).
  - Tracks around 149–151 BPM get a rough tempo of exactly 150. That triggers the slow-versus-fast tie-break, and a
    tie goes to the slow answer.
  - In the re-creation, SKINWALKER came out at 75.
  - Nine other tracks in that zone escaped, mostly by luck.
- **145 and 147 BPM can land a fraction off** (measured).
  - At those tempos a beat isn't a whole number of 40 ms slices.
  - 5 of 39 tracks were 0.3–1 BPM off: ANGST 140 read as 140.34, DIAMONDS 145 as 144.32, Hooligans II 145 as 144,
    Miss The Rage 145 as 144 and Tenebrous 147 as 146.
- **The rough step can lock onto the wrong pattern.** British Gas (145) came out at 120.15 (measured).
- **Half-time drops can leave no grid** (measured).
  - 7 of the 30 tracks with a correct tempo found no 16-beat chain and fell back to 0 ms.
  - That only lands on a beat because these exports start on a beat.
- **The bar's "1" is a guess.** A kick-on-1, snare-on-3 test matched 5 of 18 tracks (measured).
- **Wobbles drive the tempo.** 90–92% of the pulse the rough step listens to comes from the 45 and 135 Hz bands, so
  triplet or dotted wobble rhythms feed straight in (measured on 3 tracks).
- **Bass music confuses the key** (simulated).
  - The sub below 110 Hz is all but invisible.
  - A bass's overtones look like a major chord: the 3rd harmonic is the fifth and the 5th harmonic is a major
    third.
  - So a drop-heavy tune tends to read as its bass note's **major** key. With a clipped or square bass it reads as
    the key **a fifth up**.
  - The minor key wins only when pads, leads or vocals carry the minor third, at roughly 10–20% of the bass level.
  - A pitched or sped-up edit about a quarter-tone off gets an unrelated key.
- **No warning.** Wrong answers look exactly like right ones (read).

### A two-minute check in Tribe

Stream these four from SoundCloud and note the BPM Tribe shows:

| Track | Re-creation predicts | True tempo |
|---|---|---|
| SKINWALKER | 75 | 150 |
| British Gas Ft. Illaman | about 120.15 | 145 |
| ANGST | 140.34 | 140 |
| Hooligans II | 144 | 145 |

- **If Tribe matches the middle column,** the re-creation reproduces Tribe, and SoundCloud supplied no BPM.
- **If it shows the true tempos,** either SoundCloud supplied BPMs or the re-creation differs from Tribe. Loading the
  same tracks as local files (they have no tags) tells the two apart (derived).

---

## Tribe's side: from the menu to the SDK

### 1. What starts an analysis (read)

- **The track browser.**
  - The **Analyze** button opens a confirmation: "Analyze tracks in {folder}?" or "Analyze all tracks?", with an
    **Analyze Subfolders** box.
  - Confirming runs `CurrentFolder.AnalyzeTracks(subfolders)` (read: W_TrackBrowser in `menu_catalog.md`).
  - `TribeFolder::AnalyzeTracks` 0x5139b1c calls `TribeTrack::Analyze(false)` on every track, and recurses into
    subfolders when the box is ticked (read).
- **Loading a deck.**
  - Every track open in `BP_Deck` subscribes to `OnAnalysisReady` and calls `CurrentTrack.Analyze(true)` (read:
    BP_Deck load sequence).
  - If the track already has beat info, `UpdateBeatGridToCurrentTrack` applies its grid straight away (read).
  - A stream track is opened only once its audio is in memory (read: `BP_Deck.OnBufferTrackAudioChanged` →
    `OpenTrack`).
- **`TribeTrack::Analyze` 0x5139bb8 (read).**
  - A track that already has an analysis (`bHasAnalysis`, +0x1d8) is not analysed again. Its ready event fires once
    more (event name assumed: `OnAnalysisReady`).
  - A forced call starts at once.
  - An unforced call starts at once only if fewer than 2 analyses are running. Otherwise it joins the queue (read:
    `TrackLibrary::AnalyzeTrack` 0x5133348; `GetMaxConcurrentAnalyses` 0x1604a34 returns 2).
- **The queue (read: `HandleTrackAnalysisComplete` 0x5133804, `GetAnalysisQueueSize` 0x5133a40,
  `CancelQueuedAnalyses` 0x51332f4).**
  - Each finished analysis lowers the running count, stores its result, and starts the next queued track that still
    has no analysis.
  - The browser's "Analyzing Tracks - N In Queue / Click To Cancel" button shows the count.
  - Cancelling empties the queue. Analyses already running finish.
  - The order is first in, first out (assumed: a UE `TQueue`).

### 2. Which audio the analyzer gets (`TrackLibrary::AnalyzeTrack_Forced` 0x513335c, read)

- **Tags.** The analyzer is asked to read tags only if the track has no metadata yet (`bHasMetadata`, +0xa8).
- **File tracks** (local files, and track packs inside the OBB/APK). The analyzer opens the file by path, byte offset
  and length (`Analyze` 0x4790360). UE's platform-file layer resolves the range (0x4792320).
- **Buffer tracks** (`UTribeBufferTrack`: SoundCloud, Beatport, Tidal, Dropbox):
  - **The track's in-memory audio object** (`AudioInMemory`, +0x1f0, via `Analyze_audioInMemory` 0x47904e0) is used
    in three cases:
    - the file name ends in ".flac" (test 0x5137bc8);
    - there is no compressed download;
    - the track already has metadata and that object exists.
  - **Otherwise, the compressed download** (`Analyze_buffer` 0x4790548; SoundCloud keeps it at +0x230).
  - **With neither,** nothing starts and nothing is reported (read: early exit).
  - **For SoundCloud,** whose metadata flag is always set (section 3), this means (derived):
    - opened tracks are analysed from the in-memory object;
    - downloaded but unopened tracks are analysed from the download;
    - all other tracks are skipped.
- **Completion handlers.** The analyzer's `OnAnalysisComplete` is bound to `TrackLibrary.HandleTrackAnalysisComplete`.
  When tags were requested, `OnMetadataReady` is bound to `TribeTrack.HandleMetadataResults` (read: FName strings at
  0x32ee0e and 0x1d526e). Then the analysis is counted as running and the action is activated.

### 3. SoundCloud's and Beatport's own numbers (read)

- **SoundCloud.** A set-up function at 0x5125164 (name assumed) copies SoundCloud's track data into a Tribe track.
  When the track has no metadata yet:
  - SoundCloud's BPM becomes the metadata BPM if 20 ≤ BPM ≤ 300 (0x5125298–0x51252b8).
  - The key string has ":min" replaced by "m" and ":maj" removed, then goes through `GetKeyIndexFromKeyString`. An
    empty or unknown string gives −1, meaning no key (0x51252bc–0x5125460; strings ":min" 0x2bc14a, ":maj"
    0x2e5132; the names of the string helpers it calls are assumed).
  - The metadata flag is set in every case (0x5125384). So the analyzer is never asked to read tags from a SoundCloud
    stream (derived).
- **Beatport.** The set-up at 0x511f600 stores Beatport's whole-number BPM with no range check, and its key the same
  way (0x511f734–0x511f794).
- **Tidal.** Tidal tracks carry neither field (read by the key agent from the usmap).
- **SoundCloud's fields and API.**
  - The fields are `SoundCloudTrack.BPM` (float) and `SoundCloudTrack.Key` (string) (read by the key agent:
    `pulled/TribeXR_full3.usmap`).
  - Tribe talks to `api-partners.soundcloud.com` and `api.soundcloud.com`. Its SoundCloud search can filter by
    `bpm[from]`/`bpm[to]` (read: UTF-16 strings 0x32a0e6, 0x32a130, 0x15268a), so SoundCloud does hold BPMs for some
    tracks.
  - Whether SoundCloud fills BPM and key for the uploads you play was not checked (assumed: mostly empty).

### 4. The background job (read)

- **`Activate` 0x478fbdc.**
  - Registers the action and sets a looping 0.1 s timer on the game thread.
  - Builds one of six task variants: file, buffer or in-memory, each with or without tags.
  - Queues the task on a thread pool (assumed: `GThreadPool`). If there is no pool, it runs inline.
- **`AnalyzeTask_DoWork` 0x478eeb4 (worker thread).**
  - Opens a Superpowered `Decoder`: on the file range (0x478f244 → Decoder 0x6cfe55c/0x6cfeb44), or on the
    in-memory bytes copied into an `AudioInMemory` and opened as `memory://audiofile.<pointer>` (0x478f0d0).
  - If tags were requested, it reads the ID3 title, artist, album and BPM tag first (0x478f430).
- **`RunAnalyzer` 0x478f694, the driver.**
  - Creates the Analyzer with the file's own sample rate and its duration truncated to whole seconds (fcvtzs at
    0x478f714).
  - Decodes 16-bit stereo in chunks of 16 × the decoder's chunk size, converts each chunk to float and feeds it to
    `Analyzer::process`.
  - Stops at the end (0) or at a short chunk. On decoder error (−3) it gives up and returns an empty result (dis
    0x478f728–0x478f784).
  - Calls `makeResults` with: minimum 60 BPM, maximum 200 BPM, known BPM 0, "around" BPM 0, beat grid on, "around"
    grid start 0, overview on, low/mid/high on, key on.
    - Read: dis 0x478f788–0x478f7b8.
    - What each zero means was read from how `makeResults` uses it (dis 0x6cf9e40–0x6cf9efc).
  - Copies the results into `FSuperPoweredAnalysisResults`: duration, the three dB values, BPM, grid start, key, and
    six arrays. The per-point "notes" array is never fetched.
- **The timer tick 0x479020c** broadcasts `OnAnalysisComplete` on the game thread, then unregisters the action.

### 5. Storing and showing the result (read)

- **`TribeTrack::SetAnalysis` 0x513391c.**
  - It ignores a result that has BPM 0 and no waveform. So a failed decode leaves the track unanalysed and the queue
    moves on (derived).
  - Otherwise it:
    - stores the numbers at track +0x158…+0x173 and the arrays after them;
    - sets `bHasAnalysis`;
    - adds the track to search and fires the ready event;
    - writes the numbers block into the track cache (see the next bullet).
- **The track cache.**
  - SetAnalysis's write goes to `TrackCacheSaveGame.BeatGrids`, keyed by the track's name string at +0x30 (read:
    0x512acf4 writes cache +0x78). The ".flac" test reads the same string, so it is presumably the file name
    (assumed).
  - That offset matches the class's three maps and its 280-byte size (derived).
- **Analysis save and load are switched off.** The dedicated `SaveTrackAnalysis` and `LoadTrackAnalysis` natives do
  nothing in this build (read: 0x3226730 calls an empty function; 0x508ce9c returns false). So those calls don't
  keep the waveforms (derived). Whether they persist some other way was not checked.
- **The getters** that decks, lists and the waveform use (read):

  | Getter | Returns |
  |---|---|
  | `GetBpm` 0x511e7f4 | The metadata BPM if > 0, else the analyzer's |
  | `GetBeatgridStartMs` 0x513c12c | The metadata grid start if ≥ 0, else the analyzer's |
  | `GetKeyIndex` 0x511e808 | The metadata key if ≥ 0, else the analyzer's |

  When a downbeat shift is set, the metadata grid start is moved later by whole beats.
- **Where metadata comes from (read).**
  - SoundCloud and Beatport data (section 3).
  - A file's BPM tag: `HandleMetadataResults` → 0x513a784 copies a tag BPM above 0.
  - Your own edits: `SetBeatGrid` 0x513bc0c, `SetBpm` 0x513b9b4 and `SetBeatStartMs` 0x513badc write the metadata
    and save it to the cache's MetaData map.
  - `ResetBeatGrid` 0x513bd48 sets BPM 0 and start −1, which brings the analyzer's values back.
- **The deck (read: `BP_Deck`, `TimelineWaveformComponent`).**
  - It applies `GetBpm` and `GetBeatgridStartMs` through `Multi_SetBeatGrid` → `AudioPlayer.SetBeatGrid`.
  - It takes the original key from `GetKeyIndex`.
  - The scrolling waveform draws the analyzer's arrays with the deck's grid swapped in.
- **Nothing flows back.** Tribe never passes a known BPM to the analyzer as a hint; the hint arguments are the zeros
  above. So a SoundCloud or Beatport BPM changes what you see, but not what the analyzer computes, including its grid
  start (derived).
- **The dB values go unused.** No Blueprint reads the three dB values (read: search of the decoded Blueprint code).
  Native uses were not searched.

---

## Inside Superpowered's Analyzer

**Where it is (read):**
- The Analyzer core is at 0x6cf7fb0–0x6cfdc54 and its filterbank at 0x6cfb170–0x6cfba20.
- Neither references any strings. The role names (`process`, `makeResults`, the getters) rest on behaviour and on
  the shape of the SDK's public API (assumed).
- The private listings `D:/TribeUE/tribe_native/analyzer/<address>_<role>.c` hold the details. Where `.dis.txt`
  files exist, they are the instruction-level reads.

### Time base (read: constructor 0x6cf7fb0, `process` 0x6cf8694)

- Everything runs on **points of 1/150 s** (6.67 ms). That is 294 frames at 44.1 kHz and 320 at 48 kHz. Any
  remainder is spread one frame at a time.
- The analyzer holds (whole seconds of duration + 1) × 150 points. Audio beyond that is ignored.
- There is no FFT anywhere in the analyzer.

### The filterbank (read: 0x6cfb170, 0x6cfb2e4, NEON kernel 0x6cfb8c0)

- **The filters.** 56 two-pole band-pass filters run sample by sample on the mono mix (L+R)/2. They follow the RBJ
  cookbook, with 0 dB gain at the centre and the bandwidth set in octaves.
  - Each band's absolute output is summed over every point. That is a linear magnitude, not power.
- **Bands 0–47** are one per semitone from A2 (110 Hz) to G#6 (1661 Hz).
  - They use equal temperament on a fixed A4 = 440 Hz, with no tuning step.
  - Each is 1/36 octave wide (Q about 52; derived).
- **Bands 48–55** are:
  - 45 Hz and 135 Hz, half an octave wide;
  - 2 kHz and 9 kHz, 1/48 octave wide, so very narrow;
  - 70 Hz, 565 Hz and 4.55 kHz, three octaves wide;
  - 1 kHz, one octave wide.

  The full list is in `tables/filterbank_bands.txt`.
- **Peak and sum.** The same pass also tracks each point's largest absolute sample and its sum of absolute samples.

### What is recorded every point (read: `process` 0x6cf8694)

| Curve | Made from | Used for |
|---|---|---|
| Peak | Largest absolute sample, either channel | Peak waveform, exact-tempo hits, peak dB, grid attack nudge |
| Average | Mean absolute sample (not RMS) | Average waveform, loudness, the grid's drop-entry boost |
| Tempo pulse | 45 Hz + 135 Hz + 2 kHz + 9 kHz bands | Rough tempo |
| Grid onsets | The level of the eight 110–165 Hz semitone bands, plus the signed point-to-point change of the 2 kHz and 9 kHz bands; doubled on a broadband onset | Grid start |
| Low / mid / high | The 70 Hz, 565 Hz and 4.55 kHz bands; high tripled on a broadband onset | Coloured waveform |
| Notes | A bass root and a mid root per point, from the same key scorer | Nothing: Tribe never fetches them |
| Per-second level | Mean of the second's 150 averages | Overview |
| Whole-track band totals | The 48 note bands | Key |

- **Broadband onset** means at least 7 of the 20 upper bands rose by more than 3 dB since the previous point (read).
  Those 20 bands are the 880–1661 Hz semitones plus the 8 extra bands.
- On 3 of your tracks, the 45 and 135 Hz bands carried 90–92% of the tempo pulse (measured).

### Tempo, stage 1: the rough tempo (read: 0x6cfd454 and its disassembly)

- **Autocorrelation of the tempo pulse.**
  - Each lag's sum is divided by its overlap. The mean is not removed. The result is scaled to a maximum of 1.
  - Lags reach up to 16 beats at the minimum BPM (2,400 points = 16 s). That limit is halved until it fits the
    track. With fewer than 150 lags the stage gives up.
- **Candidates.** Whole-number lags of 45–150 points, which is 200 down to 60 BPM. The rough BPM is 9,000 ÷ lag.
  - Near 140, the only possible values are 138.46, 140.63 and 142.86 (derived).
  - A 149–151 BPM track lands on exactly 150.00 (derived).
- **Metrical comb.** For each candidate, it averages the best autocorrelation value near 1, 4, 8, 16, 32 … times the
  lag.
  - Twice the lag is skipped.
  - The search window grows with the multiple: it runs from a quarter of the multiple below to half of it above.
  - Only multiples that fit inside the lag limit count.
- **Tempo preference.** The comb scores are stretched to the range 0–1, then multiplied by a bell-shaped weight
  centred on 130 BPM.
  - It falls with a power of 2.4. The fall is slightly steeper above 130 than below.
  - Weight by tempo (read; values re-derived for this note): 60 → 0.58, 70 → 0.71, 75 → 0.76, 100 → 0.94,
    120 → 1.00, 140 → 0.99, 150 → 0.96, 160 → 0.91, 174 → 0.76, 180 → 0.68, 200 → 0.27.
  - The exact formula is in the private listing.
- **The pick.** The highest strict local peak wins; the two end lags are excluded and a tie goes to the longer lag.
  This value only chooses where stage 2 searches. It is never returned.

### Tempo, stage 2: the exact tempo (read: 0x6cfc334, 0x6cfcad4 and their disassembly)

- **Search windows.** The window width depends on the track's length. Call it the tolerance: 5 BPM under 60 s,
  4 BPM for 60–119 s, 2 BPM from 120 s.
  - **Rough tempo between 100 and 150:** search the rough value ± the tolerance, kept inside 100–150.
  - **Rough tempo under 75:** search from the minimum up to 75. Nothing ever re-tests double tempo.
  - **Rough tempo 75–100, or 150 and up (the "octave zones"):** search two windows. One is 75–150, where only results
    under 100 count. The other is the 150–200 version of the rough value ± the tolerance.
  - Each window is searched twice, with and without merging neighbouring histogram bins. That gives 2 or 4
    estimates.
- **Hits.** The peak curve is summed into 40 ms frames of 6 points each.
  - A frame is a hit when it beats a threshold.
  - The threshold jumps to each hit's level and otherwise sinks by about 5 dB per second.
- **Gap histogram.**
  - Gaps between **all** pairs of hits are counted, not just neighbouring ones, in 40 ms bins up to 320 s.
  - Bins above a threshold count as peaks. The threshold is half the histogram's maximum, raised when the histogram
    is flat.
  - A peak at a gap of i frames proposes the tempos 1,500·m/i BPM, for m beats, that fall in the window. Each
    carries a tolerance of ±0.8 frame.
- **One running estimate.**
  - The shortest such peak under 230 frames (9.2 s), with m of at most 4 or a power of two, seeds the estimate.
  - Every later peak whose tempo falls inside the current tolerance replaces both the estimate and the tolerance. So
    the longest gap that still agrees sets the precision, about ±0.8 frame over that gap.
  - In this build only one estimate ever exists, so the code's runner-up bookkeeping changes nothing (read by the
    tempo agent: dis 0x6cfd170–0x6cfd2d4).
  - Each run returns a BPM and its distance to the nearest whole number, in thousandths.

### Choosing, folding and rounding (read: 0x6cfc334, dis 0x6cfc674–0x6cfc940)

- **Roundness vote.** Each estimate earns points for how round it is, in this order:
  1. an exact whole number;
  2. within 0.03 of a whole number;
  3. exactly .5;
  4. within 0.03 of .5;
  5. an exact tenth;
  6. anything else, which gets nothing.

  A failed run scores far below zero.
- **Octave-zone bonuses.** A bonus goes to a window whose two runs agree within 1 BPM, and another to each slow/fast
  pair where slow = fast/2.
- **Ties.** The highest score wins. A tie goes to the value closer to a whole number, then to the earlier run. The
  slow window runs first, so **an octave tie goes to the slow tempo**.
- **Fold.** The winner is halved or doubled into the minimum–maximum range (60–200 for Tribe).
- **Rounding** (corrected at instruction level by the tempo agent):
  - If the rough tempo was 75–100, the result always keeps 2 decimals.
  - Otherwise the result becomes a whole number when it is less than 0.01 above one, or anywhere from x.50 upwards.
    The x.50 and higher fractions snap **up**.
  - Anything else keeps 2 decimals.
- **No estimate at all** gives BPM 0, and then there is no grid either.

### Hints the SDK offers, all left at zero by Tribe (read: dis 0x6cf9e40–0x6cf9efc, 0x6cfc26c–0x6cfc2fc)

- **Known BPM:** used as the answer, skipping detection.
- **"Around" BPM:** if the detected tempo is more than 1 BPM from the hint, stage 2 re-runs centred on the hint. The
  new result is kept if it lands within 2 BPM of it.
- **"Around" grid start:** picks the grid line within 26.67 ms of the hint.

### Beat-grid start (read: `makeResults` 0x6cf9d84, dis 0x6cfa1e4–0x6cfa3c8; 0x6cfbc00 and its disassembly)

- **Preconditions.** The grid needs a BPM of 40–250 and more than 2 s of audio (300 points).
- **Onset curve.**
  - The grid-onset curve is scaled to a maximum of 1. Values above half are squeezed into the top quarter.
  - 1.5 × the mean of the previous second is subtracted, with a floor of 0. The first second uses the next second's
    mean.
  - Only rises lasting 33–133 ms (5–20 points) are kept. The first point of each rise is a **seed**.
- **Drop-entry boost.** Every quiet-to-loud entry gets a large bonus (read: inside the scan loop). The entry is the
  point where the average level reaches half its track maximum after at least 67 ms below it. It counts only if the
  level stays up for more than 3 of the next 10 points.
- **Chains.**
  - From each seed, the analyzer steps one beat at a time.
  - It takes the first seed within ±1 point of the rounded prediction as a hit (about ±7–10 ms with the rounding),
    and erases that window so each hit is used once.
  - It stops after 3 empty beats in a row.
  - A chain must span at least 16 beats to be kept.
- **Merging.** Chains whose starts are a whole number of beats apart, within one point, are merged. Their strengths
  add and the earliest start is kept. The strongest merged chain gives the start.
  - Quirk: when there are 2 or more chains, the last one kept is never considered (read by the tempo agent: dis
    0x6cfbf88–0x6cfc0bc).
- **Fold and nudge.**
  - The start is reduced modulo one bar of 4 beats.
  - Then it is moved earlier by the most common number of points (0–4) that had already reached half the track's
    peak just before each bar line, at most 26.7 ms.
- **Result.** Milliseconds in [0, one bar), meaning under 1,714 ms at 140 BPM. **0 also means "no chain found"**,
  with nothing to tell the two apart.
- **Pinned in the middle (derived).** The grid passes exactly through the winning chain's start, less the attack
  nudge, and that start can be anywhere in the track. When the BPM is slightly off, the grid therefore drifts away on **both** sides of that point,
  not just towards the end.

### Key (read: `makeResults` 0x6cf9d84, scorer 0x6cf9ae8, similarity 0x6cfadc0, triad bonus 0x6cfaf20)

1. **Chroma.**
   - The 48 note bands' whole-track totals are folded into 12 pitch classes by adding the four octaves equally. Bin 0
     is A.
   - The 12 bins are scaled to sum 1.
   - Every moment counts in proportion to its level × its duration. There is no gating and no tonal/percussive
     weighting.
2. **Template similarity.**
   - There are 4 template sets, each with a major and a minor profile. The tables are in the private research
     folder.
   - For each of the 12 possible tonics, the chroma is rotated to that tonic and scored as (1 − Euclidean distance to
     the profile)².
   - In words, the sets are:
     - set 0 is plain scale masks;
     - sets 1 and 2 are smooth "probe-tone" style profiles (tonic highest, then the fifth, then thirds and the fourth);
     - set 3 lies in between, with a strong leading tone (derived from the table).
3. **Triad bonus.**
   - Each key gains chroma credit from three notes: 0.75 × its root, 0.5 × a "third" and 0.5 × its fifth.
   - **The third is swapped.** Major keys are credited with the **minor** third (+3 semitones) and minor keys with the
     **major** third (+4).
     - Read at instruction level: flag 0 for the major half at 0x6cf9b3c, flag 1 for the minor half at 0x6cf9b44,
       third = 3 + flag via `cinc` at 0x6cfaf28.
     - Checked independently for this note.
4. **Circle-of-fifths smoothing.**
   - A key's new score is 0.8 × its own score, plus 0.08 × the same-mode key a fifth up, plus 0.08 × the same-mode
     key a fifth down, plus 0.04 × its relative key.
   - Each mode's 12 scores are then scaled to sum 1 separately. So major against minor compares which half is more
     sharply peaked, not which fits better in absolute terms (derived).
5. **Vote.**
   - Each template set gives its best key 3 votes, and the most votes wins.
   - Both choices use a strict "greater than", so **ties go to the lowest index**: majors beat minors, and A beats A#
     beats B … (derived).
   - There is no confidence value and no runner-up. Silence gives index 0, A major (derived; simulated).
6. **Per-point notes.** Every point, the same scorer also runs on a bass chroma (110–208 Hz) and a mid chroma
   (220–1661 Hz). That is 8 scorer runs per 1/150 s, and Tribe discards the results.

### Loudness (read: `makeResults` 0x6cf9d84)

All three values are 20·log10 of a level, where full scale is 1.0 (dBFS):
- **PeakDb** is the loudest sample, capped at 0 dB.
- **AverageDb** is the mean of the per-point **mean absolute** level. It is not RMS and not LUFS.
- **LoudpartsDb** is the same mean taken only over points whose average level is within 15 dB of the highest one.
  It is used only when more than 1/8 of the points qualify; otherwise it equals AverageDb.

### Waveforms (read: `makeResults` 0x6cf9d84, getters 0x6cfad48–0x6cfadac, `RunAnalyzer` 0x478f694)

- **Peak and average:** one byte per point (150 per second), scaled so 255 is the track's own loudest point.
- **Low, mid and high:** one byte per point each. The three share one scale, so their balance is kept.
- **Overview:** one value per second in whole dB relative to the loudest second (0 at the loudest, down to −128),
  with one extra point at the end.
- **What Tribe stores:** the bytes divided by 255, as floats 0–1 (`Averages`, `Peaks`, `Lows`, `Mids`, `Highs`), and
  the overview as dB floats (`Overviews`).
- **Drawing:** `RenderWaveformToRenderTarget` → types 0 and 1 (0x47928d4, 0x4793594). Decompiled, but the drawing
  was not read.
- **One consequence (derived):** every waveform is relative to its own track's maximum. Quiet and loud masters
  therefore draw at the same height.

### Outputs and numbering

`FSuperPoweredAnalysisResults.BeatGrid` holds the following (read: 0x478f694; field names from the usmap and the
Blueprint code):

| Field | Unit and range | Meaning |
|---|---|---|
| DurationSeconds | Seconds | The decoder's duration |
| PeakDb, AverageDb, LoudpartsDb | dBFS, ≤ 0 | See Loudness |
| Bpm | BPM, 60–200 for Tribe; a whole number or 2 decimals | One constant tempo. 0 = not found |
| BeatgridStartMs | ms from the start of the decoded audio, in [0, 4 beats) | A beat the analyzer treats as a bar line. 0 = no chain. The grid is start + k × 60,000/BPM |
| KeyIndex | 0–23, −1 = not computed | 0–11 are major keys A, A#, B, C, C#, D, D#, E, F, F#, G, G#; 12–23 are the minor keys in the same order. Within the key finder A = 0; the per-point notes use C = 0 |

The arrays sit next to it: `Averages`, `Peaks`, `Lows`, `Mids` and `Highs` at 150 per second (0–1), and `Overviews`
at 1 per second (dB).

**Where "time 0" falls** depends on whether Superpowered's MP3 decoder trims the encoder delay, about 25 ms
(assumed; not checked).

### Tribe's key helpers (read: 0x47937b0, 0x47937e0, 0x47939a8, 0x4793810, 0x47939c8, 0x4793a24, 0x47b6f38, 0x479d224)

- **Names.**
  - Musical names use sharps only ("A" … "G#", "Am" … "G#m"). Anything outside 0–23 shows "--".
  - **Open Key:** a major key with tonic pitch class p (C = 0) is number (7p mod 12) + 1 followed by "d". A minor
    key takes its relative major's number followed by "m". So C = 1d, A = 4d, Am = 1m and Fm = 9m (rule derived and
    checked against all 24 table entries).
  - The browser's sort order runs 1d, 1m, 2d, 2m … 12m.
- **No Camelot.** Tribe has no Camelot names, and its key-format box offers only "Classical" or Open Key (read:
  native strings; `KeyFormatBox` in `menu_catalog.md`).
  - The same wheel in Camelot is the Open Key number + 7, wrapping 1–12, with d → B and m → A. So C = 8B and
    Fm = 4A (convention, assumed).
- **String to index.** `GetKeyIndexFromKeyString` looks the string up, ignoring case, among 44 spellings: sharps,
  flats, enharmonics, and "m" for minor. Anything unknown gives −1.
- **Adjacent keys** are one semitone down and up in the same mode.
- **Key difference** is (current − original) on the root only, in −11 … +11. It ignores the mode and doesn't wrap to
  the shorter direction.
- **Compatible keys** (browser marking, key sync) are the key itself, its relative, and the wheel numbers one step
  either side in both modes. The relation is symmetric (derived).
- **Deck key sync** picks the smallest same-mode shift, within ±6 semitones, onto a key compatible with the target.

---

## Weaknesses on your music

The (measured) items come from the tempo agent's re-creation on your 39 MP3s. Its reference was a generic
spectral-flux tempo with a long comb, which put every track within 0.02 BPM of a whole number: 140 × 11, 145 × 13,
150 × 10, 147 × 3, 144 and 138. None of these items was observed in Tribe.

### Tempo

1. **Octave zone at 150.**
   - Tracks at 149–151 BPM get a rough tempo of exactly 150.00, so they go to the slow/fast vote, where a tie goes to
     slow (read, derived).
   - 10 of 39 tracks took that path, and SKINWALKER came out at 75 (measured).
   - The other nine escaped only because the slow window locked onto a wrong gap (discarded as ≥ 100), or because the
     fast runs agreed while the slow ones didn't. So the outcome is fragile.
2. **Fractions at 145 and 147.**
   - A beat is 10.34 or 10.2 frames of 40 ms, so the single running estimate can follow a slightly wrong chain of
     gaps.
   - 5 of 39 tracks were 0.3–1 BPM off (measured).
   - The snap-up rule rescued Good For Me, where 144.84 became 145 (measured).
3. **A wrong rough lock.**
   - British Gas (145) got a rough 120 and a final 120.15 (measured).
   - The preference barely separates 100 from 160 BPM (0.94 against 0.91), and the comb follows whatever repeats in
     the bass (derived).
4. **Half-time 70 against 140 was handled on these tracks.** None of the 39 picked 70; the 140 candidate scored
   0.94–0.99 against 0.54–0.71 (measured). But a rough value under 75 is never re-tested at double (read). A track
   with a weak pulse would stay at 70.
5. **The sub drives the pulse.** 90–92% of the rough-tempo signal is 45 and 135 Hz energy (measured), so LFO rhythms
   feed the autocorrelation. Hats and snares contribute about 7–10%.
6. **Peak-curve hits on loud masters.**
   - In drops, frames sit 2–4 dB under the track peak and wobble by about 0.5 dB.
   - The hit rule fired on 12–41% of all frames, 3–10 per second against about 2.4 beats per second (measured).
   - The tempo survives only through statistics over long gaps.

### Grid

7. **Half-time patterns break chains.**
   - A chain needs a hit within about ±7–10 ms at least every third beat.
   - 7 of 30 correct-tempo tracks fell back to 0 ms: Mindblow, UMBRA, RESISTANCE, Cabin Fever, Transmutation
     Sequence and two clips (measured).
   - A file that starts with a pickup, silence or a free-time intro would get the wrong phase.
8. **Timing.** On the 23 chain-based grids the results were as follows (measured against a reference that itself
   reads about 10 ms early):
   - 18 within ±15 ms of the attack;
   - 4 were 20–38 ms late;
   - 1 a sixteenth late: Salsa Riddim, +96 ms.

   Inside loud drops the attack nudge rarely fires (derived).
9. **The bar line is not estimated.** Chains merge per beat (read). A kick-on-1, snare-on-3 test matched 5 of 18,
   slipped one beat on 2 (Violence, Project 98), and was unclear on the rest (measured).
10. **One tempo and one phase per file** (read). Tempo ramps, intros at 70 and live edits get a single global answer.
    A beatless intro is harmless as long as the whole file keeps one tempo (derived).
11. **Store BPM against the analyzer's grid (derived).**
    - When SoundCloud or Beatport supplies a BPM that differs from the analyzer's by a non-octave amount, Tribe pairs
      that BPM with a grid start found at the analyzer's tempo.
    - The grid then misses the winning chain by about (beats from the start to the chain) × (beat-length
      difference). For a chain found 60 s in, 144 against 145 gives roughly 0.4 s.
    - Octave differences, such as 75 against 150, line up.

### Key (simulated, through `key_sim/key_sim.py`, unless marked)

12. **The sub is invisible.** The lowest note band is 110 Hz, so a 41–55 Hz fundamental arrives about 40 dB down
    (derived). A clean sine sub contributes nothing, and a sub-only signal gives a meaningless key.
13. **Bass overtones look like chords.**
    - For dubstep-range fundamentals (about 37–55 Hz), the 3rd harmonic, the fifth, is the strongest bin.
    - The 5th and 10th harmonics add a major third.
    - A saw or distorted bass alone reads as its root's **major** key. A clipped or square bass reads as the key a
      **fifth up**. An F-minor drop needed a minor-third pad at about 10–20% of the bass level before Fm won.
14. **The swapped third blurs major against minor** (read, simulated).
    - A lone sine major triad reads as minor in 3 of 4 template sets.
    - A lone sine minor triad flips in only 1 of 4. This was re-run for this note: F-Ab-C and A-C-E each gave one
      set to the parallel major, and still voted minor.
    - Net, the swap leans towards minor. It can flip sparse major-key melodic tracks.
    - Separately, a minor-seventh chord (F-Ab-C-Eb) reads as its relative major, Ab, with or without the swap
      (simulated for this note).
15. **Near-ties.** After normalisation, competing keys differ by about 0.001–0.02 on scores around 0.11. The
    lowest-index tie rule then favours majors and keys early in A … G# (read, simulated).
16. **Fixed A440 grid.** A whole track up to about 35 cents off still works. About 50 cents off gives an unrelated
    key, for example an F-minor mix at +50 cents read as C# major. That matters for pitched or sped-up SoundCloud
    edits.
17. **One linear average over the whole track.** Long loud drops outweigh quiet breakdowns. An F-minor test held up
    to a 3:1 drop-to-breakdown ratio and began to split at 4:1. There are no sections and no key changes (read for
    the method).
18. **Always an answer.** Riddim with no harmony still gets a confident-looking key (read, derived).

### Tribe's handling

19. **No hints.** A SoundCloud or Beatport BPM never steers the analyzer (read).
20. **Metadata always wins.** A wrong uploader BPM or key, or a wrong file tag, beats the analysis (read).
21. **Silent failures.** BPM 0, grid 0 and no confidence anywhere (read). A decode error leaves the track
    unanalysed without a message (derived).
22. **Unopened SoundCloud tracks are skipped.** Analyze ignores SoundCloud tracks that haven't been downloaded
    (derived; not observed).

---

## What our detectors take from this

These are ideas in our own words. None of them copies Superpowered's code or tables.

### Tempo

- **Keep the two-stage shape.**
  - First, a cheap pass on a low-rate envelope (about 150 Hz): autocorrelation plus a comb over 1, 4, 8, 16 and
    32 beats, which suits EDM's 4- and 8-bar phrasing. Use it only to choose a window.
  - Then a precise pass whose accuracy comes from the longest stretch of agreeing hits, not from beat-to-beat gaps.
- **Make the precise pass sub-frame.**
  - Match onset times at about 1 ms resolution to a provisional grid.
  - Fit period and phase across the whole track by robust least squares. On a 3-minute track that gives about
    0.005 BPM and sub-millisecond phase.
  - The fit's residual becomes the confidence.
- **Treat metre as explicit hypotheses** (70/140, 75/150, 120/145 …), tested on beat-position evidence: attacks on
  every beat in the mid/high bands, or a snare every 2 beats.
  - For this library, prefer the faster octave between 135 and 152 BPM.
  - Never let a tie fall to the slow octave.
  - Re-test anything under 75 at double tempo.
- **Use a prior centred on 140–145** rather than 130, or learn it from the library. Keep at least their 1.4:1 margin
  of 140 over 70.
- **Onset function.** Use per-band, log-compressed spectral flux with every band normalised, so drums count as much
  as the sub. Never use the raw peak envelope of a limited master.
- **Snap to whole numbers symmetrically,** and only within the fit's uncertainty. All 39 reference tempos sat within
  0.02 BPM of one. Don't snap x.5 and above upwards.
- **Keep the length-dependent search width:** narrower windows for longer tracks.

### Grid

- **Phase by consensus, borrowed from their chains.** Chain hits along the period, use each hit once, require 16+
  beats, and add up chains that agree in phase. This shrugs off beatless intros and fills.
  - Use wider windows (±15–20 ms) and allow 4+ empty beats for half-time drops.
- **Estimate the downbeat separately.**
  - Keep the quiet-to-loud drop entry as a strong anchor.
  - Ask which beat carries the lone kick against the snare (kick on 1, snare on 3 in half-time).
  - Check phrase boundaries every 16 or 32 bars.
  - Report a downbeat confidence.
- **Attack alignment.** Estimate one offset per track from many beats on a 1 ms envelope, with no 26.7 ms cap.
- **Fold the grid with the final BPM,** and re-fit the phase whenever an outside BPM (store, tag, user) replaces
  ours. That avoids the pairing problem in weakness 11.

### Key

- **Give the bass its own register.**
  - Build a separate 27–110 Hz chroma whose strongest sustained pitch class is a tonic cue.
  - Explain bass partials before building the harmony chroma: harmonic summation, or subtracting the 3rd, 5th and
    6th harmonics of strong low notes.
  - Build the harmony chroma from about 200 Hz to 2–4 kHz.
- **Decide major or minor from mid-register thirds** above the chosen tonic. If we use a triad bonus at all, give
  major keys the major third.
- **Estimate tuning first.** Shift the semitone grid by the median deviation of strong peaks, and flag tracks near a
  quarter tone.
- **Weight frames by tonality.** Use log or power compression and down-weight percussive frames. Consider 8–16-bar
  section chromas with a vote, which also exposes key changes.
- **Use one continuous combined score** instead of a 3-vote plurality. Report the margin to the runner-up and to the
  parallel and relative keys, and return "unknown" below a threshold.
- **Use public or self-trained profiles,** such as Krumhansl-Kessler, Temperley, or ones fitted on a small labelled
  set of your tracks. Never use Superpowered's table.

### Output and checks

- **Emit Tribe-compatible numbering:** 0–11 major A … G#, 12–23 minor, −1 none. Include Open Key (d/m) and Camelot
  (B/A) names, so results compare one-to-one with Tribe and feed the same compatibility rule.
- **Loudness.** If the goal is matching levels, measure RMS or K-weighted (LUFS-style) loudness. Superpowered's
  "average" is the mean absolute sample. Keep the "loud parts only" idea as a gate.
- **Waveforms.** 150 points per second, with a peak, an average and three bands, is an adequate and cheap display
  rate. Keep an absolute scale as well as the per-track normalisation.
- **Confidence and fallbacks.** Always return a confidence and a labelled fallback ("rough tempo only", "no grid")
  instead of 0.
- **Cross-check service metadata.** Use a SoundCloud or Beatport BPM as a prior or a cross-check, not as an
  unconditional override.
- **Regression sets:**
  - your folder `C:/Users/Chris/Music/BRAND NEW SHIT` (39 SoundCloud MP3s, 128 kbps, 44.1 kHz) with the reference
    tempos above;
  - hard cases for this method: SKINWALKER (150), British Gas (145), ANGST (140), Hooligans II (145) and
    Salsa Riddim (138, grid);
  - for keys, a synthetic set: saw and clipped basses on each root from C#1 to A#1, a sweep of minor-pad level,
    whole-track detune of 0, 25 and 50 cents, and drop-to-breakdown ratios from 1:1 to 4:1.

---

## How this was established

### Sources

- **The map.** 98 Ghidra 12.0.4 listings in `D:/TribeUE/tribe_native/analyzer/`, named `<address>_<role>.c` with a
  role header each.
  - They come from 7 read-only runs of `scripts/ghidra_probe.sh` + `scripts/FxProbe.java` on project
    `C:/ghidra-work/tribexr`, never saved. Provenance is in `cmds_run1-7.txt` and `ghidra_run1-7.log`.
  - Raw constant tables are in `tables/`: filter bands, key profiles, key names, key-string map, compatible keys and
    rodata constants.
  - Binary: `unpacked/base/lib/arm64-v8a/libUnreal.so` (129,868,152 bytes). The address mapping was checked on the
    licence string at 0x6bea7b.
- **Tempo and grid.** Capstone disassembly (`*.dis.txt`) of the driver, `process`, `makeResults` and the
  tempo/grid functions.
  - The private re-creation is in `harness/`: `coarsecheck*.py`, `finecheck.py` and `gridcheck.py`, which encode
    Superpowered's method and must never go into `D:/VRDJ`.
  - The generic measurement scripts are `envcheck.py`, `refbpm.py` and `barpos.py`.
- **Key.** `key_sim/key_sim.py` is a private re-statement of the scorer. It reads the templates and band centres from
  the `.so` at run time; run it with `python -P`.

### Checks made for this write-up

- **Tribe's flow was read from the decompiled class files** in `D:/TribeUE/tribe_native/classes`: `TrackLibrary`,
  `TribeTrack`, `TribeFolder`, `TribeBufferTrack` and `TribeSoundCloudTrack`. The Blueprint side was read from
  `BP_Deck`, `W_TrackBrowser` and `TimelineWaveformComponent`.
- **New disassembly** went into `D:/TribeUE/tribe_native/analyzer/doc_checks/`:
  - the SoundCloud set-up (BPM range check, key-suffix handling);
  - Beatport's set-up;
  - the track-cache store;
  - the key scorer and triad bonus.
- **Re-read by a second route:**
  - the `makeResults` call registers;
  - the length-dependent tolerance;
  - the 130 BPM preference constants and the values in its table;
  - the swapped third at instruction level;
  - the handler names bound by `AnalyzeTrack_Forced`;
  - the grid-onset curve (dis 0x6cf97b4–0x6cf9900). Its low-band term is a difference of whole-track running totals,
    which makes it the bands' level at that point. The 2 kHz and 9 kHz terms are true point-to-point changes. This
    confirms the tempo agent's reading and its `gridcheck.py`; the decompiled C makes both look like changes;
  - the loudness block: "loud parts" falls back to the plain average;
  - the drop-entry boost applies at every quiet-to-loud entry.
- **Triad checks.** The minor-triad and minor-seventh cases were re-run through `key_sim`.
- **Tag scan.** All 39 MP3s have ID3v2 tags, but none has a BPM (TBPM) or key (TKEY) frame. `tracks.json` in that
  folder holds only titles and URLs.

### Corrections to earlier notes

- **`native_summary.md` line 49** still says the analyzer library has "Camelot and Open Key" names. The binary has
  musical names and Open Key only.
  - `native_reference.md` line 55 already says so, but `native_reference.py` regenerates that file from
    `native_summary.md`. The fix belongs in `native_summary.md`.
  - The same line's "(inferred)" about BPM, key and waveform is now read.
- **The ID3 BPM tag.** The map's statement that the ID3 BPM tag "never reaches the analyzer" is true. But the tag does
  reach the BPM Tribe shows: `HandleMetadataResults` → 0x513a784 stores a tag BPM above 0 as metadata, which wins
  (read).
- **Tempo-agent corrections, read at instruction level.** These supersede the map's decompiler-based summary:
  - the run "fraction" is the distance to the nearest whole number;
  - the final rounding keeps the sign, so x.50 and above snap up;
  - in-phase merging and the chain window centre are rounded, not truncated;
  - the gap histogram only ever holds one estimate;
  - ties at the rough stage go to the longer lag;
  - the grid's last kept chain is skipped when there are 2 or more;
  - the second autocorrelation envelope is only a fallback, and Tribe passes none.

### Not checked (what to watch)

- **Whether SoundCloud fills BPM and key** for the tracks you stream (assumed: rarely). The two-minute check above
  settles it.
- **Whether Superpowered's MP3 decoder trims the encoder delay.** That would shift every grid by about 25 ms.
- **Whether SoundCloud's stream encoding** (format or bitrate from the partner API) changes borderline results, such
  as the 150-against-75 vote, compared with the downloaded MP3s used in the re-creation (assumed: small).
- **Codec internals.** The decoders under `Decoder::open` were not decompiled.
- **Waveform drawing.** The waveform-drawing code was not read.
- **Persistence.** Whether waveforms persist across sessions was not checked.
- **Decoder statuses.** What the decoder returns for a buffer that is still downloading was not checked. Tribe's loop
  only handles 0 and −3 (read).
- **The re-creation itself.** Every (measured) and (simulated) number comes from private re-creations, not from Tribe
  running on the headset.
