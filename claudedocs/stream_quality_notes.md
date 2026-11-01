# Stream quality: why the Twitch stream looked laggy, and the fix (2026-10-27)

The user: "while im streaming in the headset, nothing is lagging ... but when im streaming to twitch, its like lagging?
like it dosent look crisp like it does in the headset. this goes for all of our modded stages", then "its also the
lazers. it looks like its at a very low frame rate".

## What Tribe sends

- Tribe streams through Agora, SDK 4.5.2 (libagora-rtc-sdk.so), using WebRTC underneath. The Twitch output comes from
  Agora's side. Tribe hands Agora frames itself: MediaEngine::pushVideoFrame, I420, 848 x 480. These are logged in the
  app's files/agoraapi.log.
- **The stream is 848 x 480 at 15 fps, at Agora's "standard" bitrate (about 0.78 Mbit/s).** This is fixed in Tribe,
  the same on every stage, stock or ours:
  - TribeVideoCallManager::StartCallWithParameters calls IRtcEngine::setVideoEncoderConfiguration at vtable +0xf0 of
    the engine pointer stored at manager+0x550.
  - Width and height come from libUnreal .bss (vaddr 0x7F02DC4; Ghidra 0x08001dc4). Zero in the file, set at run time.
  - frameRate 15 and bitrate 0 come from .rodata at vaddr 0x448920 (Ghidra 0x00547920).
  - The rest of the struct: minBitrate -1, degradationPreference -1, mirrorMode 2, encodingPreference -1 (auto),
    compressionPreference -1.
  - The decompile is in D:/TribeUE/tribe_native/classes/TribeXR.TribeVideoCallManager.c, around line 5715.
- Tribe's menus have no stream-quality setting. NDI in its network menu is input to its monitors, not output.

## What went wrong on the headset (two test streams, logcat QC2 stats + agoraapi.log + a live monitor)

1. **2.4 GHz Wi-Fi.** The first test ran on channel 1 (2412 MHz). WebRTC's frame-rate cap (agoraapi.log
   VideoFrameWatermarker::onSinkWantsChanged max_framerate_fps) bounced between 7 and 15 about once a second. It averaged
   11 fps on the Reactor and on Graveyard alike. On 5 GHz (5765 MHz, 866 Mbit/s link) the stream held about 14.5 fps.
2. **Agora drops the hardware encoder.** The QC2 c2.qti.avc.encoder (log tag avcE_N) was released cleanly by the app:
   - test 1 (2.4 GHz) at 14:17:01, after 1.5 minutes;
   - test 2 (5 GHz) at 15:05:23, after 5 minutes.

   No hardware encoder ran after that, yet frames kept being pushed. A thread GENP.0 went from about 7 % to 16-27 % of a
   core, which looks like Agora's software encoder. The frame-rate cap then sat at 7-12. Agora's own log
   (agorasdk.log) is encrypted, so its reason is not visible.
   - Before both drops the hardware encoder ran over its 0.78 Mbit/s target, at 1-3.4 Mbit/s.
   - Each drop was within 2 s of a hands/controller interaction-profile change. That is probably a coincidence: the
     user switches often and there were only two drops.
3. **Not our stages.** During test 2's hardware stretch, the stock environment and Graveyard were the same:
   14.3-15.4 fps encoded, headset 71-72 fps. Our busy scenes, lasers above all, show a low frame rate the most, but
   they don't cause it.

## The fix: hook/stream.cpp (combo16 = combo15 + stream.cpp)

- tribemod/stream.txt switches it on (`fps=`, `kbps=`, `encoder=auto|software|hardware`,
  `compression=auto|latency|quality`, `degradation=auto|quality|framerate|balanced|resolution`). With no file it does
  nothing.
- 3 s after Tribe reports a live call, it repeats Tribe's own setVideoEncoderConfiguration call with these values,
  keeping Tribe's 848 x 480. "Live" means bInVideoCallReplicated (reflection) or GetIsChannelStreaming. It re-applies
  when stream.txt changes during a call.
- It calls only if the vtable entry points into libagora-rtc-sdk.so's executable mapping. It logs [STREAM] lines.
- The first values: fps=30, kbps=2500, encoder=hardware, degradation=framerate.
- dumper.cpp only gets the include, stream_tick after camview_tick, and stream_poll next to camview_poll.
- combo15's sources rebuild combo15 byte for byte (bf47c27b) with `-llog -lm -ldl`. combo16's lib is 0aa9509a;
  out/hookA/combo16.aligned.apk is 8fb11854, same certificate.
- To check it on the headset:
  - the [STREAM] lines in logcat;
  - "RtcEngine::setVideoEncoderConfiguration" in files/agoraapi.log, which logs the values Agora accepted;
  - the QC2 avcE Stats lines: encoder fps and Mbit/s, and whether the hardware encoder lasts the whole stream.

  scratchpad stream/stream_monitor.sh (session 9b260986) prints all of it every 10 s.
- Open: whether Tribe pushes 30 frames a second (encoder Q rate 14.2/s at 15 fps could be either Tribe or Agora's
  limit); raising 848 x 480 (the .bss pair before StartCall, if Tribe's capture follows it); whether Agora re-encodes
  for Twitch. 848 x 480 and 1280 x 720 are both in Agora's "HD" price tier (up to 921,600 pixels).

## The visuals packs

- The loops were 1080p30 at about 16 Mbit/s (peaks over 20; the decoder logged 22-27 Mbit/s windows). The hour sets
  were already 6 Mbit/s.
- 111 loops re-encoded at 8 Mbit/s (maxrate 10M, bufsize 12M) into D:/TribeUE/Visuals_8M/<pack>/, same names. The
  settings are otherwise the packs' own encode.py: x264 High 4.1, GOP 30, no B-frames, sc_threshold 0, aq-mode 3,
  faststart. Each file was checked for an exact frame count and duration, and scored with SSIM against the source
  (results in scratchpad vj/results.tsv).
- NVENC needs a newer NVIDIA driver than the PC's (the ffmpeg build wants API 13.0; the driver has 12.2), so x264
  medium on the CPU did the work.

## Pushed (2026-10-27, the user: "its closed right now")
- 15:3x: combo16 installed by push_stream.sh (base.apk 8fb11854, firstInstallTime 2026-10-27 14:11:13 unchanged) and
  tribemod/stream.txt 594cfde6 (backed up in backup/tribemod_20261006; reseed.sh restores it, 364afc08). reseed.sh MOD
  is still combo15 until combo16's first stream checks out.
- 15:5x: the 111 re-encoded loops pushed with scripts/push_media.sh into the six Movies folders, every copy md5-verified
  (one RED EYE check failed on the first pass, and the re-run found all 18 matching). Same names, same file counts
  (143). SSIM min 0.979 (Dino Spine Tunnel), averages 0.985-0.997. The originals stay in the packs' deliver folders.

## combo17-19 (2026-10-27): what it took, and the result

- **combo16 never called.** The engine pointer comes from Android's allocator, which tags the top byte (0xb4...). sr()'s
  /proc/self/maps range check never matches a tagged address, so rdptr returned 0, and the module gave up after one try.
  Also, libagora-rtc-sdk.so only appeared in the maps scan after the call started.
- **combo17 called, but it did nothing to the live encoder.** Tribe sets the encoder for the default connection, then
  joins with joinChannelEx({channelId, localUid}), and at the join Agora copies the default into that connection. A
  later setVideoEncoderConfiguration only changes the default. agoraapi.log shows the whole order: setChannelProfile,
  setClientRole, setVideoEncoderConfiguration, Ex(default), joinChannelEx, Ex(connection).
- **combo18 fixed it** with IRtcEngineEx::setVideoEncoderConfigurationEx(config, connection) at vtable +0x928.
  - The slot was found offline: scratchpad stream/agora_slots.py takes the API-logger strings ("virtual int
    agora::rtc::RtcEngine::<name>(...)"), finds the ADRP+ADD references, the function starts (table pointers, since
    .eh_frame_hdr stops part-way), and the RELATIVE relocations of the vtable at 0x1a159e8.
  - Cross-check: queryInterface is +0x0 and setVideoEncoderConfiguration is +0xf0, as Tribe's own calls are.
    joinChannelEx is +0x8f8, setParameters +0x8c0.
  - At run time each call is made only if the slot points into libagora's code and the function's first 16 bytes
    match the file's.
  - The connection comes from Agora's own log: the poll thread reads the last joinChannelEx line in files/agoraapi.log.
  - Tribe keeps the channel name in VideoCallChannel, but not the uid.
  - The result: the live encoder went from 0.78 to 2-4 Mbit/s, and the hardware encoder held for the whole 10-minute
    stream. Before that, it had always fallen back to software within 20 s to 5 min.
- **30 fps changed nothing.** At 16:34:06 Agora's sink asked for 30 (onSinkWantsChanged max_framerate_fps 30), and the
  encoder still received 14.4 frames/s. The limit is Tribe's capture:
  - TribePlayerController::Tick counts a float timer at +0x914 down by DeltaTime. Below 0 it calls CaptureScene
    (FUN_03ce2bd8, whose own warning text names it) on the active capture at +0x888.
  - Then it resets the timer to 1/FUN_02338b14() while streaming, otherwise 0x3d2aaaab = 1/24.
  - FUN_02338b14 is `mov w0,#15; ret` (vaddr 0x2239b14). It isn't patched: it may be folded with other code.
  - At 72 Hz that is every 5th frame: 14.4 fps. The +0x914 loads and stores are checked in the machine code
    (0x509c15c/0x509c168, 0x509c350/0x509c384).
- **combo19:** `capture=24` makes the module clamp that timer, every frame while live, to (N - 0.75) frames, with
  N = round(72 / rate). It does so only when +0x888 is a live SceneCaptureComponent2D. stream.txt is now fps=30,
  kbps=3500, encoder=hardware, degradation=framerate, capture=24 (6c89bd36; backed up; reseed.sh restores it).
  - **Result (16:50-16:55, Graveyard):** the encoder received 22.7-26.3 frames/s, and Twitch's own stats said about
    24 fps. Hardware encoder, 2.3-3.3 Mbit/s, headset 70-72 fps.
  - VrApi GPU% averaged 0.79 at 24 captures/s against 0.83 at 14.4, so the extra captures are lost in the noise.
  - The user: "dude WAY better".
- reseed.sh MOD=combo19 (26f2f4f2; reseed.sh 7e39158b). combo15 is the fallback.
- **Next, if wanted: 1280x720.** Tribe's stream size is the .bss pair at vaddr 0x7F02DC4 (848, 480), used by the
  encoder config, the push and the capture-aspect broadcast.
  - Unknown: whether the capture's render target and the readback follow it. The frame producer that fills
    manager+0x908 has not been found; it is not in Ghidra 0x51b0000-0x51e8000.
  - Estimated cost: about +2-4 % GPU (2.26x the pixels per capture), and about 4.5-5 Mbit/s upload. Same Agora HD
    band (up to 921,600 px).

## combo20 (2026-10-27): 1280x720, live and the default

- `size=1280x720` in stream.txt. Between streams (never during a call) the module writes the pair at vaddr 0x7F02DC4,
  and only if it holds Tribe's 848x480 or our own earlier value.
- How Tribe uses the pair, from Ghidra (DecompXrefs on 0x8001dc4):
  - TribePlayerController::Tick sizes the active capture's TextureTarget from it while streaming: FUN_051d2dcc returns
    it; SizeX is at +0x138, SizeY at +0x13c, then vtable +0x340. On the resize tick it skips the capture.
  - The frame producer FUN_051ff164 (called from the push, FUN_051d0564) converts width x height of the readback into
    the I420 buffer at +0x908. It sizes that buffer as w*h*1.5.
  - StartCallWithParameters and FUN_051d3ce4 build the encoder config from it. FUN_051d3ce4 is Tribe's own
    setVideoEncoderConfigurationEx at +0x928, which confirms the slot. When it runs is covered in the next bullet.
  - When Tribe re-sends its settings (Ghidra, 2026-10-27 evening). FUN_051d3ce4's only caller is FUN_051fd10c (Ghidra
    address; file vaddr 0x50FE10C), the join step. That step:
    - copies the channel id to manager +0x718 (a libc++ string) and the uid to +0x730;
    - calls joinChannelEx (+0x8f8) with the event handler at +0x530;
    - calls FUN_051d3ce4 only if the join returns 0. Otherwise it logs "RTC JoinChannel failed".

    FUN_051fd10c is reached from FUN_051fbc54, a chain of async steps (lambda vtables 0x076e45a8, 0x076e45f0,
    0x076e46c8). So Tribe's 15 fps / standard-bitrate settings come back only when Tribe joins the channel. Today's
    monitors agree: at 16:28 and 16:50, Tribe's Ex line ([A] thread) came at the join and ours ([U], the game thread)
    3-4 s later. The last encoder line in Agora's log stayed ours until Tribe closed.
  - The gap: stream.cpp re-applies when the engine changes or when the live flags go on. Its tick samples them twice
    a second. So it misses a mid-stream re-join only if the flags stay on, or go off for less than about 0.5 s.
    - If that happens, the size and the capture rate stay ours; the encoder's fps, bitrate and hardware preference
      go back to Tribe's. Workaround: stop and restart Go Live.
    - The fix is combo21 (next section): an inline hook on FUN_051d3ce4 (file vaddr 0x50D4CE4, first 16 bytes
      ff0302d1fd7b05a9fd430191f53300f9). The prologue is sub/stp/add/str with nothing PC-relative. The hook calls
      the original, then bumps a counter. The tick treats a bump like a new call: bump g_stLiveSeq so the poll
      thread re-reads the connection, then apply about 1 s later. This also shrinks the 3 s window at each start.
  - On a GENP.0 thread at 14-20 % CPU: the 16:50 (848x480) and 17:16 (720p) monitors show it at the same time as
    QC2 avcE Stats lines, so it isn't only Agora's software encoder. A software fallback shows as the stats column
    reading "none".
  - The rest use it only for aspect ratios.
  - When not streaming, the capture is sized from another pair at vaddr 0x7F02740, which logs 1280x720.
- First stream, 17:16-17:23 on Graveyard:
  - At 17:15:21 the module changed 848x480 to 1280x720. Tribe's own config then used 1280x720, and ours applied 1280x720,
    30 fps, 5000 kbps for the live connection.
  - The hardware encoder logged "Input Format at frame 0: YV12 1280x720". It ran at 21-28 fps, mostly 24-25, for 6
    minutes without falling back.
  - Bitrate 3.5-12 Mbit/s (it overshoots the 5000 target); Wi-Fi upload 5.5-11 Mbit/s.
  - Twitch Video Stats: 1280x720, 24 fps, 5484 kbps (avc1.64001F). With the player on Auto, a viewer got Twitch's
    852x480 rendition (1 Mbit/s).
  - The headset's cost, against 848x480 at 24 fps on the same stage:
    - GPU% average 0.77 against 0.79 (unchanged);
    - app GPU time 9.07 ms against 8.64;
    - frames over 20 ms per 10 s, 104 against 47;
    - seconds below 70 fps, 23 % against 13 %; stale frames 5.4/s against 3.4/s;
    - dips to 52-62 fps with a background worker busy (17:19:40, 17:22:20).

    The user: "honestly it felt fine to me and looks good on twitch".
- reseed.sh MOD=combo20 (2a538da5; reseed.sh e591523d). The stream.txt backup is the 720p one (a07e0298). combo19 is the
  848x480 fallback: put back stream_cap24.txt and combo19.
- If the headset feels juddery in a long set: `size=960x544` (16-pixel multiple) or `capture=18`, or lower kbps if
  Twitch buffers (the user's upload has to carry the encoder's peaks).


## combo21 (2026-10-27): the hook on Tribe's own re-send

- The user, on the mid-stream re-join gap: "im not gonna test that because i HIGHLY doubt i would lose wifi. but you
  can still do it just in case". No Wi-Fi-drop test is needed: Tribe's re-send runs at every join, so every Go Live
  exercises the hook.
- hook/stream.cpp, three changes:
  - st_hook_send (poll thread, once, only with stream.txt) checks the head bytes and runs A64HookFunction on
    g_base + 0x50D4CE4. The library writes the patch only once the trampoline is ready; otherwise it logs "NOT hooked".
  - st_repl_send calls the original, then adds 1 to g_stTribeSends. That is one __aarch64_ldadd4_acq_rel, the same
    helper combo20 already uses.
  - The tick acts on a change only while live: g_stLiveSeq++, apply about 1 s later. The [STREAM] apply line ends
    "(after Tribe's own re-send)".
- Build: combo15.apk + lib with 7z, then sign_apk.sh.

  | Item | Value |
  |---|---|
  | lib | 7b1df5ff |
  | APK | 654b2f7b |
  | Cert | 979d63d7 |
  | Files | 752 |
  | Warnings | 7, same as combo15 |
  | dumper.cpp | unchanged (82e417c8) |

- INSTALLED 2026-10-27 17:47:49 with install -r. base.apk md5 verified; firstInstallTime 14:11:13 unchanged.
  stream.txt unchanged (a07e0298).
- Still pending, then reseed.sh MOD=combo21 (it stays combo20 until then):
  - the first launch, which should log "Tribe's encoder re-send @0x... hooked";
  - a stream, which should log "Tribe sent its own encoder settings (it joined; #1)" and then the apply line.
- Fallback: combo20 (2a538da5) is the same build without the hook.
