# Tribe freezes and the freeze recorder (2026-10-27)

## The symptom

The headset picture freezes for good while the music keeps playing. The audio runs on its own thread. Only closing
Tribe recovers it.

| When | Stage | What was happening |
|---|---|---|
| 2026-10-18 | RED EYE | |
| 2026-10-19 (twice) | Graveyard | |
| 2026-10-27 18:18:29 | Graveyard | combo21, live on Twitch at 720p. 0.2 s after a trigger click while picking a song (SystemButtonHandler key 103 at 18:18:29.0-29.2). |

The 2026-10-27 freeze, from the headset:
- **When it stopped:** the mod's last line came at 18:18:29.16. VrApi's FPS lines stopped repeating new values
  after 18:18:29.
- **The threads:** the GameThread, RenderThread and RHIThread were all asleep (state S, 0 % CPU), so they were waiting,
  not spinning. One TribeXR.TribeXR thread was at 28 %.
- **The decoder:** the visuals decoder kept decoding at 30 fps after the freeze.
- **Memory:** 1.7 GB free; the app used 2.17 GB PSS, 1.28 GB of it graphics.

## Ruled out so far

- **The QC2 "avcD_N queueOutputs: Allocation failed!" warnings.** They appear in every session today, including ones
  that never froze (36,543 in log_all.txt), and the decoder keeps working through them.
- **Running out of memory:** the system had 1.7 GB available.
- **The 8 Mbit/s VJ loops:** the decoder used about 95 MB both before the re-encode (14:12) and after it.
- **Today's stream changes as the root cause:** the freezes on the 18th and 19th came before them. Whether they make
  a freeze more likely is not known.

## Why the cause is still unknown

Nothing outside the app can show where a thread is stuck:
- `debuggerd -b` says "root is required";
- `run-as` says "package not debuggable";
- Tribe's `Saved/Logs` folder is empty.

## The recorder: hook/freeze.cpp (combo22)

dumper.cpp hooks it in at three places:
- `#include "freeze.cpp"` after stream.cpp;
- `freeze_beat()` in both tick lines, after stream_tick;
- `freeze_poll()` in the poll loop, after stream_poll.

**Any later combo must keep all three.**

### What it does

- **Heartbeat:** freeze_beat counts game-thread ticks and records the game thread's id on the first tick.
- **Start:** freeze_poll starts a watchdog thread (`tribemod_frz`) once, after the first tick, on a real-time signal
  that was free then (SIG_DFL, from SIGRTMIN+6). `tribemod/freeze_off` keeps it off.
- **Samples:**
  - after 4 s without a tick (sample 1);
  - again at 30 s (sample 2);
  - then nothing until ticks resume, which logs "ticking again after N s". A headset-off pause does this too, and it
    recovers.
- **Self-test:** one game-thread sample 20 s after the start, so every launch shows the recorder works.
- **Threads per sample:** the game thread, every RenderThread / RHIThread / TribeXR.TribeXR thread, and the 3
  busiest of the rest (CPU over 1 s); at most 12.
- **The handler:** it reads pc / lr / sp / fp from the ucontext and walks the frame records. It reads them through
  process_vm_readv, so a bad fp fails instead of faulting. The calls in its machine code are an atomic swap,
  syscall(gettid), getpid and process_vm_readv. It takes no lock and fills one slot. A thread that doesn't answer in
  300 ms is skipped. The signal is re-checked as ours before every send, because an RT signal's default action ends
  the process.

### Output

- **logcat:** `[FREEZE]` lines, one per thread: name, tid, state, CPU, then its frames.
- **The file:** `tribemod/freeze_log.txt`, with one frame per line. It rotates to freeze_log.1.txt at 512 KB.
- **Address format:**
  - libUnreal frames print as `UE <Ghidra address>` (vaddr + 0xFF000), ready for DecompAt (pass it the Ghidra
    address - 0x100000);
  - other libraries print as `lib.so+<file offset>`.

### The build

| Item | Value |
|---|---|
| lib | b67ec69b |
| APK | 2eb513b7 |
| Cert | 979d63d7 |
| Files | 752 |
| Warnings | 7, the same as combo15 |
| dumper.cpp | b9354b81 |
| freeze.cpp | 3442dfe9 |

- Contents: combo21 (the stream hook) plus the recorder.
- INSTALLED 2026-10-27 18:38:41 with `install -r`. firstInstallTime 14:11:13 unchanged.
- reseed.sh stays MOD=combo20 until combo22's first launch shows the self-test.
- **The check:** after a launch with 20+ s of play, `tribemod/freeze_log.txt` has a
  `== <time> self-test: the game thread (<tid>) while it ticks` block, and logcat has `[FREEZE] recorder on: …`. The
  file stays on the headset, so this works any time after the launch. No file after such a launch means the recorder
  never started. As of 20:09 on 10-27, Tribe had not been opened since the install.
