# Mod port to Tribe 0.12.6 (2311): the 720p stream and Twitch, address map

Mapping only (2026-10-31). Nothing was built, edited or installed. Inputs: `backup/mod_halloween_work/lib2304/` (libUnreal.so
129,868,152 B, md5 d7c722db) and `lib2311/` (libUnreal.so 142,361,784 B, md5 385f58a9), both libagora-rtc-sdk.so, `hook/stream.cpp`,
the stream notes, and the combo21 device logs (scratchpad of session 9b260986).

## Answer first

- **2311 streams through the same Agora path.** libagora-rtc-sdk.so is byte-identical (md5 81b006ac in both APKs; every other
  libagora*.so has the same zip CRC). Tribe's own calls are unchanged: setVideoEncoderConfiguration (+0xf0) at call start,
  joinChannelEx (+0x8f8), then its own setVideoEncoderConfigurationEx (+0x928) for the live connection. Its values are the same
  (15 fps, bitrate 0 = standard, minBitrate -1, orientation 1, degradation -1, mirror 2, encodingPreference -1, compression -1).
- **stream.cpp needs 5 values changed and 1 new hook.** The engine pointer moved from manager +0x550 to +0x570. The two size pairs,
  Tribe's re-send function and its head bytes moved. Everything else it uses (the Agora slots and heads, the player-controller
  offsets, the reflection names) is unchanged.
- **New in 2311: a second Tribe function re-sends 15 fps and the standard bitrate to the live connection.** It is called from the
  handler for the call's Agora messages (RTM): moveToStage, moveToAudience, changeUserPriority and the channel-state messages.
  Which message takes which branch wasn't traced. combo21 hooks only the join-time re-send, so it would miss this one. Hook it the
  same way.
- **The version check is the video-call protocol version: "3" in 2304, "4" in 2311.** Tribe sends it as `protocol_version` on every
  `/agora/token2` request (the Agora token every call needs, Go Live included). It also compares it with
  `GET /agora/videocall-protocol-version`. A mod built on 2311's libUnreal.so sends "4" without any change. To keep it that way:
  - don't patch the protocol global;
  - change the re-seed and login-fix scripts so they reinstall 2311, not 2304.

## Address convention (applies to every number below)

| Form | Rule | Evidence |
|---|---|---|
| ELF vaddr | the file's own addresses (p_vaddr) | read from the program headers |
| Ghidra | ELF vaddr + 0x100000 | the notes' FUN_ names (e.g. FUN_051d3ce4 = ELF 0x50D3CE4) |
| **hook constant** (what stream.cpp adds to g_base) | **ELF vaddr + 0x1000** | Observed on 2304, see below |

How the hook-constant rule was observed on 2304:
- combo21 logged "Tribe's encoder re-send @0x752c8e0ce4 hooked" (10-27 17:50:09 and 18:11:05). The head check passed at
  g_base + 0x50D4CE4, and that function's ELF vaddr is 0x50D3CE4.
- The stream pair at g_base + 0x7F02DC4 (ELF 0x7F01DC4) read 848x480.
- The off-call pair at g_base + 0x7F02740 (ELF 0x7F01740) read 1280x720.

2311 has the same segment layout: PT_LOAD offset-to-vaddr skews 0 / 0x10000 / 0x20000 / 0x30000, first load at 0. So the same rule
is assumed; the head-byte checks in stream.cpp fail safe if it is wrong.

How targets were matched: function bounds from .eh_frame_hdr, then one or more of:
- the sequence of Agora vtable calls;
- ADRP+ADD references to strings and to the size pair;
- GOT and RELR pointers;
- an instruction-by-instruction diff.

The Agora slots were named from libagora's API-logger strings plus the vtable's RELATIVE relocations (the saved readelf dump).

## The targets in stream.cpp

Notation: 2304 → 2311. Confidence H/M/L.

### S1. The engine pointer (`ST_ENGINE_OFF`): manager +0x550 → **+0x570** (H)
- 2304: the call start (StartCallWithParameters in the notes; ELF 0x50C0400) does `str x0,[x19,#0x550]` at 0x50C0A80. The re-send
  and the join step read it.
- 2311: the matching call-start function (ELF 0x5A6E790) does `str x0,[x19,#0x570]` at 0x5A6F250. The re-send (0x5A80E9C), join
  step, role-change function and push all read +0x570.
- Matched by: the same function shape. It has the same strings ("Agora media engine unavailable", "Call-%s") and the same vtable
  call sequence: +0x90, then +0xf0, then queryInterface(4).
- Port: `#define ST_ENGINE_OFF 0x570`.

### S2. setVideoEncoderConfiguration, slot +0xf0 and its 16 head bytes (H, unchanged)
- Same library. The bytes at libagora vaddr 0x180f150 in 2311's copy are `ff8304d1fc670da9f85f0ea9f6570fa9`, matching
  `ST_SETVEC_HEAD`.
- Tribe's own +0xf0 call: 2304 ELF 0x50C0B08, 2311 ELF 0x5A6F2D4. Both build the config from the size pair and the same two
  16-byte constants: 2304 .rodata 0x447920 / 0x44B590, 2311 0x4C4EC0 / 0x4C9350, values identical.
- Port: nothing.

### S3. setVideoEncoderConfigurationEx, slot +0x928 and its head (H, unchanged)
- The bytes at libagora vaddr 0x180f31c are `ffc306d1fc6f15a9fa6716a9f85f17a9`, matching `ST_SETVECEX_HEAD`.
- Slot names, from the relocation dump plus API-logger strings:
  - +0x0 queryInterface, +0xf0 setVideoEncoderConfiguration, +0x190 enableLocalAudio;
  - +0x8f8 joinChannelEx, +0x920 updateChannelMediaOptionsEx, +0x928 setVideoEncoderConfigurationEx;
  - +0x958 muteLocalVideoStreamEx, +0x960 muteAllRemoteAudioStreamsEx, +0xa10 enableAudioVolumeIndicationEx.
- Port: nothing. The struct layout in stream.cpp (Agora 4.5.2) stays valid, since it is the same library.

### S4. The stream size pair (`ST_DIMS_VADDR`): hook 0x7F02DC4 → **0x8B092C4** (ELF 0x8B082C4, Ghidra 0x8C082C4) (H)
- Each build has 8 references. Seven roles match across the builds:
  - the getter (2304 ELF 0x50D2DCC → 2311 ELF 0x5A7ECB0);
  - the call start (×2);
  - the re-send;
  - the frame push;
  - the aspect getter (0x50D5E98 → 0x5A82C80);
  - the user-list aspect code (0x50F9818 → 0x5A70A64).

  2304's eighth reference is its separate frame producer (0x50FF164). 2311's eighth is the new role-change re-send (S9).
- The 720p mechanism is intact (2311 ELF 0x5A7BB5C):
  - The push still sizes the I420 conversion from the pair: `ldp w0,w1,[pair]` and a buffer of w*h*1.5.
  - The old separate frame producer (2304 FUN_051ff164) is now inside the push (derived: the push does the conversion and no
    separate producer references the pair). The I420 TArray moved from manager +0x908 to +0x880 (the mod doesn't use it).
  - The player-controller tick (S7) still resizes the capture target from the getter.
- Port: `#define ST_DIMS_VADDR 0x8B092C4`.

### S5. The off-call pair (`ST_DIMS_OFFCALL_VADDR`): hook 0x7F02740 → **0x8B08CF0** (ELF 0x8B07CF0) (H)
- It is the only other pair the capture tick reads (2304 0x509B2C4 `add …#0x740` ↔ 2311 0x5A3CF24 `add …#0xcf0`).
- stream.cpp uses it only for one log line.
- Port: `#define ST_DIMS_OFFCALL_VADDR 0x8B08CF0`.

### S6. Tribe's default size (`ST_TRIBE_W/H` = 848x480): assumed unchanged, **not verified** (L/M)
- No code writes either pair directly in either build. Searched: ADRP+ADD, ADD chains, GOT and data pointers within 0x400 before
  the pair, and `mov #848` next to `mov #480`. Only reads were found.
- The 848x480 on 2304 comes from the device log. For 2311: same encoder code and same constants, so probably the same, but unknown.
- If it differs, the mod logs "the stream size reads WxH (not Tribe's 848x480 nor ours): NOT changing it". That is safe; set
  `ST_TRIBE_W/H` from that line.

### S7. TribePlayerController +0x888 (capture) and +0x914 (timer): unchanged (H)
- The capture tick, 2304 ELF 0x509B124 → 2311 ELF 0x5A3CD84, is 185 instructions in both and identical apart from addresses:
  - +0x888, +0x914, +0x880 (manager), +0x2d0, +0x890/+0x898, +0x8a0/+0x8a8, +0x8c0, +0x918/+0x919, +0x920, +0x970/+0x974;
  - the capture target at +0x300, SizeX/SizeY at +0x138/+0x13c, and vtable +0x340.
- It is the only caller of the size getter in both builds, and it sits in a vtable in both (a Tick override).
- The rate function still returns 15: 2304 ELF 0x2238B14 → 2311 ELF 0x23C9B78 (`mov w0,#15; ret`, not patched by the mod).
- Port: nothing. `capture=24` works as on 2304.

### S8. Tribe's re-send (`ST_TRIBE_SEND_VADDR` + `ST_TRIBE_SEND_HEAD`): hook 0x50D4CE4 → **0x5A81E7C** (ELF 0x5A80E7C, Ghidra 0x5B80E7C) (H)
- Matched by the same call sequence, unique in each build:
  - enableAudioVolumeIndicationEx(500,3,false) (+0xa10);
  - muteAllRemoteAudioStreamsEx (+0x960);
  - muteLocalVideoStreamEx (+0x958);
  - then, if the video flag is set, setVideoEncoderConfigurationEx (+0x928) with the pair and the same constants.
- The manager fields moved:

  | Field | 2304 | 2311 |
  |---|---|---|
  | uid | +0x730 | +0x798 |
  | channel string | +0x718 | +0x780 |
  | flags | +0x528/+0x529 | +0x548/+0x549 |
  | (other) | +0x399 | +0x3a9 |

- New head (16 bytes, nothing PC-relative: `sub sp,#0x90; stp x29,x30,[sp,#0x60]; add x29,sp,#0x60; stp x22,x21,[sp,#0x70]`):
  `{0xff,0x43,0x02,0xd1,0xfd,0x7b,0x06,0xa9,0xfd,0x83,0x01,0x91,0xf6,0x57,0x07,0xa9}`.
- It now has **two callers**:
  - the join step (ELF 0x5A80590, `bl` at 0x5A808E4), still only after joinChannelEx returns 0; the "RTC JoinChannel failed" text is
    the same;
  - a lambda (ELF 0x5AA5464) that calls it when the atomic state at manager +0x538 equals 4. The push also requires 4, so 4
    probably means connected, and the lambda looks like a reconnect. That reading is unverified, but the hook counts it the same
    way, which is what's wanted.
- Unverified: combo21's hook was installed on the device (two launches) but never seen firing during a stream.
- Port: change the address and head. The code is unchanged.

### S9. NEW: Tribe's role-change re-send, hook **0x5A82F18** (ELF 0x5A81F18, Ghidra 0x5B81F18) (H that it exists and what it sends; M on when it fires)
- What it does, in order:
  1. Sets the flags byte +0x548 to 0 or 3 from the role byte +0xa40 (0xc0 gives 0).
  2. Calls enableLocalAudio(false) (+0x190).
  3. Calls Tribe's own setVideoEncoderConfigurationEx (+0x928), with the same 15 fps / standard values and the pair, on the live
     connection.
- Its only caller is ELF 0x5A7616C. That function stores the role byte at +0xa40 and then calls updateChannelMediaOptionsEx (+0x920).
- ELF 0x5A7616C is reached from these callers:
  - the RTM message handler ELF 0x5A75050, twice. It compares the message type against moveToStage, moveToAudience,
    changeUserPriority, channelStateSnapshot and others. One call passes the message's "priority", another passes 0x20 or 0x80.
    Which message reaches which call wasn't traced.
  - five more functions: 0x5A78670, 0x5A79110, 0x5A9ED48, 0x5A9EDD8 and 0x5A9EEAC;
  - a tail call from 0x5A78E8C.
- 2304 had no such call: the only +0x928 call site in the video-call code was the re-send.
- Effect without a hook: mid-stream, a role or priority message puts the encoder back to 15 fps, the standard bitrate and the auto
  encoder until the next stream. The size and the capture rate stay ours.
- Head (nothing PC-relative): `{0xff,0xc3,0x01,0xd1,0xfd,0x7b,0x05,0xa9,0xfd,0x43,0x01,0x91,0xf4,0x4f,0x06,0xa9}`. It takes the
  manager only.
- Port: a second `A64HookFunction` with the same replacement (call the original, then `__sync_fetch_and_add(&g_stTribeSends,1)`).
  The tick then re-applies ours about 1 s later, as it does for S8.

### S10. Reflection names stream.cpp looks up: all present (H)
- `TribeVideoCallManager` and `TribePlayerController`: class names present.
- `/Script/TribeXR.TribeVideoCallManager.GetIsChannelStreaming` is still a UFunction:
  - 2304: exec thunk ELF 0x4FE70C0, body `ldrb w0,[x0,#0xbe8]`;
  - 2311: exec thunk ELF 0x53F8860, body `ldrb w0,[x0,#0xb68]`.
  - In 2311 the RTM handler appears to set that byte from the message's "channelStreaming" field (`strb …,#0xb68` at 0x5A75DB0).
    Not traced in full.
- `bInVideoCallReplicated`: same flags, same rep-notify (`OnRep_InVideoCallReplicated` in both). Its SetBit moved from +0x389 to
  +0x399, the same +0x10 shift as the manager field next to it (+0x399 → +0x3a9).
- Port: nothing in stream.cpp; it finds these by name. It depends on the dumper.cpp core working on 2311 (other pieces):
  - find_by_path, find_live_class_sub, find_field and calib_fprop_size;
  - call_ret, obj_alive and A64HookFunction.

### S11. The live connection from Agora's log: unchanged (H)
- Same library, so the API log has the same file names and line format.
- 2311 still joins with joinChannelEx (+0x8f8 at ELF 0x5A808BC). So the last "joinChannelEx(this:" line still carries channelId and
  localUid.
- Port: nothing. Keep reading only channelId and localUid from that line. It also carries a token; never log the line.

## Where the Go Live flow lives in 2311

| Step | 2304 ELF | 2311 ELF | What changed |
|---|---|---|---|
| Call start (engine, default encoder, media engine) | 0x50C0400 | 0x5A6E790 | engine +0x570. New errors: "Agora RTC/RTM unavailable", "You cannot join calls while suspended from rooms.", "Go Pro to go live…" |
| Protocol-version request `GET /agora/videocall-protocol-version` | 0x50C1380 | 0x5A6FA7C | same code |
| Protocol-version reply handler | 0x50D669C | 0x5A834F4 | same code: compares the server's "version" with the client global; a mismatch passes "Incompatible videocall server versions. Your videocall may have unexpected errors." to +0x2b8 of the same object (an event; not traced). It warns; this code doesn't block the call |
| Agora token `/agora/token2?…` (query adds uid, token_type, **protocol_version**) | 0x51149B8 (URL variants 0x511480C, 0x5114EDC) | 0x5B72224 (0x5B72078, 0x5B72748) | same code; the value comes through the GOT from the protocol global |
| Join + re-send | 0x50FD10C | 0x5A80590 | channel/uid fields moved; event handler +0x530 → +0x550 |
| Backend session `PUT /videocall/start` (`?channel=&mode=&oculusid=&email=`, JSON body), `/heartbeat`, `/stop` | 0x50FD7E0, 0x50D6270, 0x50C3EA0 | 0x5AA4410, 0x5A83150, 0x5A71BF8 | same query keys; the body was not decoded |
| Frames: tick → readback ("ReadTexture") → push | 0x509B124 → 0x50D2DDC → 0x50D0564 (+0x50FF164) | 0x5A3CD84 → 0x5A7ECC0 → 0x5A7BB5C | producer merged into the push |
| Go Live menu | Blueprint W_VideoCallMenu | native `UTribeVideoCallMenuWidget` (HandleOnToggleStateChangedTwitchStreamEnabledSlider, GetVideoCallTwitchIngestURL, StreamToTwitch) | moved to C++; the mod doesn't hook it |
| Twitch | `/twitch/auth-code`, `/twitch/alt-login`, `id.twitch.tv/oauth2/validate`, ingest `rtmp://sfo.contribute.live-video.net/app/` | same strings | none found |

The endpoint paths found (`/agora/…`, `/videocall/…`, `/twitch/…`, `/api/…`) are the same in both builds. 2311 adds only
`/api/experiments/evaluate`. Paths under other prefixes were not compared.

### The version check

| Item | 2304 | 2311 |
|---|---|---|
| Protocol global (FString) | ELF 0x7EFA1E8 (GOT 0x7B76248) | ELF 0x8AE7468 (GOT 0x874B2A0) |
| Its lazy static init | ELF 0x4F80838, literal `u"3"` at 0x318E26 | ELF 0x5218280, literal `u"4"` at 0x381748 |
| Users | the token request and the reply handler only | same |

- **Observed:** the protocol string is "3" in 2304 and "4" in 2311, it goes out on the token request, and the reply handler compares
  it with the server's.
- **Derived, not observed:** the backend now expects 4, so 0.12.5.1 can't get a working call. I saw no server reply. This matches the
  store 2311 build streaming while 2304 doesn't, but nothing here proves the server's reason.
- Other version strings are not gates on this path:
  - `app_version` in 2311 is telemetry and session events (fns 0x59EE57C, 0x59EF130, 0x59EFBD0, which read ProjectVersion and
    VersionDisplayName);
  - "Incompatible client version" and `incompatible_version` sit in code outside the video calls (2311 0x485BED4, 0x485C024; not
    traced);
  - "Cannot connect to incompatible version" (new in 2311) has no code reference I could find.
- **What the mod's stream needs to pass it:** run on 2311's own libUnreal.so (APK versionCode 2311, main.2311 OBB) and leave the
  protocol global and the token request alone. No hook is needed.

## What the port must keep working for Twitch

1. **Build from `backup/tribe_2311/apk/base.apk`.** Use its libUnreal.so plus the libhook DT_NEEDED entry, and
   `main.2311.com.TribeXR.TribeXR.obb`. A 2304 libUnreal.so sends protocol 3.
2. **The Meta token re-seed has to install 2311.** These scripts still name 2304, and as written they would put protocol-3 Tribe back
   (I did not edit them):
   - `scripts/reseed.sh` lines 23, 24, 35 and 40;
   - `scripts/fix_login.sh` lines 31-34 and 132;
   - `scripts/push_obb.sh` lines 10, 25 and 71: the patch OBB name and its zip comment `"      2304"`.

   The genuine-login-then-mod logic itself is unchanged: the mod still can't mint a Meta token.
3. **stream.cpp:** S1, S4, S5, S8 and S9 above. It stays inert without `tribemod/stream.txt`. The 720p file is backed up as
   a07e0298 (fps=30, kbps=5000, encoder=hardware, degradation=framerate, capture=24, size=1280x720) in `backup/tribemod_20261006`
   and `backup/tribemod_20261031_preupdate/tribemod_full/tribemod`. The store 2311 install has no tribemod folder, so it has to be
   pushed.
4. **Don't touch** the protocol global, `/agora/token2`, the native Go Live menu or the Twitch login flow.

## Port steps (this piece) and time

1. stream.cpp constants:
   - `ST_ENGINE_OFF 0x570`;
   - `ST_DIMS_VADDR 0x8B092C4`;
   - `ST_DIMS_OFFCALL_VADDR 0x8B08CF0`;
   - `ST_TRIBE_SEND_VADDR 0x5A81E7C` with the new `ST_TRIBE_SEND_HEAD`;
   - refresh the comments (FUN names and Ghidra addresses).
2. Add the second hook (S9): address 0x5A82F18 with its head. Same replacement and counter; its log line names it ("role change").
3. Build and sign together with the other pieces, on the 2311 base.
4. First launch, check these log lines:
   - both "… hooked";
   - "Tribe's video-call manager … bInVideoCallReplicated found";
   - "Tribe's stream size 848x480 (off-call capture size 1280x720)", then "→ 1280x720".
5. One Go Live of at least 5 minutes with `stream_monitor.sh`:
   - "Tribe sent its own encoder settings (it joined; #1)";
   - the apply line at 1280x720, 30 fps, 5000 kbps;
   - agoraapi.log's last setVideoEncoderConfigurationEx is ours;
   - QC2 avcE stats, and Twitch stats at 1280x720 / about 24 fps.
6. Optional: in a room, move to stage or audience while live. Expect "#2" and a re-apply.
7. Re-seed scripts to 2311 names (step 2 of the previous section), if no other piece owns them.

**Time: about 2 hours of work.** Code changes take about 30 minutes; steps 4-6 on the headset take about 1 hour; the script changes
plus one re-seed run take about 30-45 minutes. This assumes the dumper.cpp core already runs on 2311. Add 30-60 minutes per surprise
if step 4 shows a different default size (S6) or a failed head check (the +0x1000 rule).

## Risks and what's unverified

- **S6:** 2311's initial stream size. It fails safe and the first-launch log shows it.
- **The +0x1000 rule on 2311:** expected from the identical layout; the head checks confirm it at first launch.
- **The protocol-3 rejection is inferred,** not seen. Watch for "Incompatible videocall server versions" or a failed Go Live after any
  re-seed.
- **When S9 fires during a solo Twitch stream** (channel-state snapshots versus role changes only). Hooking it is cheap either way.
- **The re-send hook firing during a real stream** has never been observed (combo21: installed, no stream run). Step 5 covers it.
- **Not decoded:** the `/videocall/start` JSON body, and so whether the backend's Twitch push re-encodes. On 2304, Twitch reported
  1280x720 at 24 fps, so it passed the encoder's stream through.
